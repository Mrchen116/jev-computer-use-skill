"""Operation/target protocol contracts independent of scripted task journeys."""

import unittest

from jev_computer_use.computer import describe_window
from jev_computer_use.decisions import ask_decision
from jev_computer_use.models import validate_answers
from jev_computer_use.tasks import decision_payload


class Model:
    def __init__(self, overrides):
        self.overrides = iter(overrides)
        self.requests = []

    def ask(self, payload):
        self.requests.append(payload)
        overrides = next(self.overrides)
        answers = {}
        for head, question in payload['questions'].items():
            choice = overrides.get(head, next(iter(question['criteria'])))
            answers[head] = {'choice': choice, 'confidence': 1,
                             'probabilities': {k: float(k == choice) for k in question['criteria']}}
        response = {'answers': answers}
        validate_answers(payload, response)
        return response, .01


class DecisionTests(unittest.TestCase):
    def payload(self, raw, texts=None, history=None):
        return decision_payload('Fill the requested fields, then apply', history or [],
                                describe_window(raw, 'test', []), texts or {}, [])

    def decide(self, model, payload, actions, cancelled=lambda: False):
        return ask_decision(model, payload, actions, lambda *args: None, 100000, cancelled)

    def test_fields_and_values_are_not_a_cartesian_model_menu(self):
        texts = {f'v{i}': {'text': f'value {i}', 'purpose': f'field {i}'} for i in range(16)}
        history = [{'step': i, 'action': {'type': 'wait'}} for i in range(30)]
        payload, actions = self.payload('\n'.join(f'{i} text field (settable) Field {i}' for i in range(12)), texts, history)
        self.assertEqual(len([a for a in actions.values() if a['type'] == 'replace']), 192)
        self.assertEqual(len(payload['questions']['target_replace']['criteria']), 12)
        self.assertNotIn('next_action', payload['questions'])
        self.assertEqual(payload['state']['history'], history)
        model = Model([{'pause_now': 'continue', 'operation': 'replace', 'target_replace': 'field_9'},
                       {'input_value': 'replace_9_v9'}])
        selected, _, _, _ = self.decide(model, payload, actions)
        self.assertEqual(actions[selected]['target']['id'], '9')
        self.assertEqual(actions[selected]['text'], 'value 9')
        values = model.requests[1]['questions']['input_value']['criteria']
        self.assertEqual(len(values), 18)  # 16 supplied values, missing-text handoff and branch rejection
        self.assertTrue(all(k in ('help_input', 'reselect_action') or k.startswith('replace_9_') for k in values))

    def test_unused_input_head_cannot_trigger_input_or_a_second_request(self):
        payload, actions = self.payload('1 text field (settable) Name\n2 button Apply',
                                       {'name': {'text': 'Lin', 'purpose': 'Name'}})
        model = Model([{'pause_now': 'continue', 'operation': 'click', 'target_click': 'click_2',
                        'target_replace': 'field_1'}])
        selected, _, _, _ = self.decide(model, payload, actions)
        self.assertEqual(selected, 'click_2')
        self.assertEqual(len(model.requests), 1)

    def test_even_one_supplied_value_can_be_rejected_for_selected_unfocused_field(self):
        payload, actions = self.payload('1 text field (settable) Name\n2 text field (settable) City',
                                       {'name': {'text': 'Lin', 'purpose': 'Name'}})
        model = Model([{'pause_now': 'continue', 'operation': 'replace', 'target_replace': 'field_2'},
                       {'input_value': 'help_input'}])
        selected, _, _, _ = self.decide(model, payload, actions)
        self.assertEqual(actions[selected]['type'], 'help_input')
        self.assertEqual(actions[selected]['target']['id'], '2')

    def test_pause_or_stop_does_not_request_text(self):
        payload, actions = self.payload('1 text field (settable) Name',
                                       {'name': {'text': 'Lin', 'purpose': 'Name'}})
        model = Model([{'operation': 'review_completion'}])
        selected, pause, _, _ = self.decide(model, payload, actions)
        self.assertEqual(selected, 'review_completion')
        self.assertEqual(pause['choice'], 'pause')
        self.assertNotIn('pause_now', payload['questions'])
        self.assertEqual(len(model.requests), 1)
        model = Model([{'operation': 'replace', 'target_replace': 'field_1'}])
        selected, _, _, _ = self.decide(model, payload, actions, lambda: True)
        self.assertIsNone(selected)
        self.assertEqual(len(model.requests), 1)

    def test_input_choices_preserve_date_time_compatibility(self):
        payload, actions = self.payload('1 日期时间区域 (settable, date) Value: 8:00 AM\n2 日期时间区域 (settable, date) Value: 4/12/27',
                                       {'date': {'text': '2027-08-19', 'purpose': 'Date'},
                                        'time': {'text': '07:30', 'purpose': 'Start time'}})
        model = Model([{'pause_now': 'continue', 'operation': 'replace', 'target_replace': 'field_1'},
                       {'input_value': 'replace_1_time'}])
        selected, _, _, _ = self.decide(model, payload, actions)
        self.assertEqual(actions[selected]['text'], '07:30')
        self.assertNotIn('replace_1_date', model.requests[1]['questions']['input_value']['criteria'])


class SelectorTests(unittest.TestCase):
    payload = DecisionTests.payload
    decide = DecisionTests.decide
    def test_selector_text_branch_can_return_existing_click_action(self):
        payload, actions = self.payload('1 combo box (settable) Mode, Value: Alpha', {'name':{'text':'Lin','purpose':'Name'}})
        model = Model([{'operation':'replace','target_replace':'field_1'}, {'input_value':'open_options'}])
        selected, _, _, _ = self.decide(model, payload, actions)
        self.assertEqual(selected, 'click_1')
        self.assertEqual(actions[selected]['type'], 'click')

    def test_operation_state_exposes_readonly_picker_and_actual_input_targets(self):
        payload, actions = self.payload('1 text field (settable) City, Value: Paris\n2 text Departure date\n3 text field', {'city':{'text':'Paris','purpose':'City'}, 'date':{'text':'2026-10-20','purpose':'Departure date'}})
        targets = payload['state']['available_targets']
        self.assertIn('click_3', targets['click'])
        self.assertIn('Departure date', payload['state']['observation']['ui_tree'])
        self.assertEqual(set(targets['replace']), {'field_1'})
        self.assertEqual(targets['replace'], payload['questions']['target_replace']['criteria'])

class ReselectionTests(unittest.TestCase):
    payload = DecisionTests.payload
    decide = DecisionTests.decide

    def test_wrong_input_branch_can_return_to_control_selection(self):
        payload, actions = self.payload('1 text field (settable) Name, Value: Lin\n2 button Next',
                                       {'name': {'text': 'Lin', 'purpose': 'Name'},
                                        'city': {'text': 'Paris', 'purpose': 'City'}})
        model = Model([{'operation': 'replace', 'target_replace': 'field_1'},
                       {'input_value': 'reselect_action'},
                       {'field_1': 'satisfied'},
                       {'operation': 'click', 'target_click': 'click_2'}])
        selected, _, _, seconds = self.decide(model, payload, actions)
        self.assertEqual(selected, 'click_2')
        self.assertAlmostEqual(seconds, .04)
        self.assertNotIn('target_replace', model.requests[-1]['questions'])
        self.assertEqual(model.requests[-1]['state']['rejected_input']['target']['id'], '1')
        self.assertNotIn('replace', model.requests[-1]['state']['available_targets'])

    def test_revised_operation_reuses_the_grounded_value_without_asking_again(self):
        payload, actions = self.payload('1 text field (settable) Name\n2 text field (settable) City',
                                       {'name': {'text': 'Lin', 'purpose': 'Name'}})
        model = Model([{'operation': 'replace', 'target_replace': 'field_1'},
                       {'input_value': 'reselect_action'},
                       {'field_1': 'satisfied', 'field_2': 'input_name'},
                       {'operation': 'replace', 'target_replace': 'field_2'}])
        selected, _, _, _ = self.decide(model, payload, actions)
        self.assertEqual(actions[selected]['target']['id'], '2')
        self.assertEqual(actions[selected]['text'], 'Lin')
        self.assertEqual(len(model.requests), 4)
        self.assertEqual(set(model.requests[2]['state']), {'task', 'input_texts'})
        self.assertEqual(model.requests[2]['model'], payload['model'])

    def test_grounded_missing_text_yields_without_reoffering_unrelated_values(self):
        payload, actions = self.payload('1 text field (settable) City\n2 text field (settable) Name',
                                       {'name': {'text': 'Lin', 'purpose': 'Name'}})
        model = Model([{'operation': 'replace', 'target_replace': 'field_1'},
                       {'input_value': 'reselect_action'},
                       {'field_1': 'missing', 'field_2': 'input_name'}])
        selected, _, _, _ = self.decide(model, payload, actions)
        self.assertEqual(actions[selected]['type'], 'help_input')
        self.assertEqual(actions[selected]['target']['id'], '1')
        self.assertEqual(len(model.requests), 3)

    def test_rejection_checks_all_fields_before_another_input_branch(self):
        payload, actions = self.payload('1 text field (settable) Name, Value: Lin\n2 text field (settable) City, Value: Paris\n3 button Apply',
                                       {'name': {'text': 'Lin', 'purpose': 'Name'},
                                        'city': {'text': 'Paris', 'purpose': 'City'}})
        model = Model([{'operation': 'replace', 'target_replace': 'field_1'},
                       {'input_value': 'reselect_action'},
                       {'field_1': 'satisfied', 'field_2': 'satisfied'},
                       {'operation': 'click', 'target_click': 'click_3'}])
        selected, _, _, _ = self.decide(model, payload, actions)
        self.assertEqual(selected, 'click_3')
        self.assertNotIn('replace', model.requests[-1]['questions']['operation']['criteria'])
        self.assertEqual(model.requests[-1]['state']['input_field_status']['field_2']['status'], 'satisfied')
