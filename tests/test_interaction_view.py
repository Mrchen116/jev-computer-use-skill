import tempfile
import unittest

from jev_computer_use.computer import describe_window, action_menu
from jev_computer_use.tasks import model_view, TaskRunner
from test_tasks import ComputerDouble, JevDouble


class InteractionViewTests(unittest.TestCase):
    def test_combined_menu_uses_observed_selection_and_keyboard(self):
        raw = ('Window: Test\n0 window Test\n\t1 web area Form\n\t\t2 listbox Ticket\n'
               '\t\t\t3 text (selected) Alpha Beta Gamma\n\t4 tab Unrelated\n'
               'The focused UI element is 3 text (selected) Alpha')
        view, _, _ = model_view(describe_window(raw, 'test', []), 0)
        actions = action_menu(view, {})
        self.assertNotIn('click_3', actions)
        self.assertNotIn('click_4', actions)
        self.assertEqual(view['controls']['3']['selected_option'], 'Alpha')
        self.assertIn('key_Down', actions)
        self.assertIn('key_Return', actions)
        chrome, _, _ = model_view(describe_window(raw, 'test', []), 1)
        self.assertIn('4', chrome['controls'])

    def test_dense_table_pages_keep_commit_control_and_all_rows(self):
        raw = 'Window: Test\n0 window Test\n\t1 web area Form\n\t\t2 text field (settable) Date\n\t\t3 table\n'
        raw += '\n'.join(f'\t\t\t{10+i*2} row\n\t\t\t\t{11+i*2} button Day {i}: ' + 'x'*100 for i in range(200))
        raw += '\n\t\t500 button Apply\n\t501 tab Browser tab'
        obs = describe_window(raw, 'test', [])
        first, _, count = model_view(obs, 0)
        self.assertIn('500', first['controls'])
        self.assertNotIn('501', first['controls'])
        retained = set()
        for i in range(count):
            view, _, _ = model_view(obs, i)
            retained.update(view['controls'])
            if 'Day ' in view['ui_tree']:
                self.assertIn('500', view['controls'])
        self.assertTrue(all(str(11+i*2) in retained for i in range(200)))
        self.assertIn('501', retained)

    def test_input_can_be_verified_when_temporarily_readonly(self):
        class Popup(ComputerDouble):
            def observe(self):
                editable = '(settable)' if not self.value else ''
                return describe_window(f'0 window Form\n1 text field {editable} City, Value: {self.value}', 'test', [])
        with tempfile.TemporaryDirectory() as root:
            computer = Popup()
            result = TaskRunner(computer, JevDouble(['replace_1_city', 'review_completion']), root).run(
                task='Enter city', input_texts={'city': {'text': 'Example', 'purpose': 'City'}})
            self.assertEqual(result['reason'], 'review_completion')
            self.assertEqual(result['history'][1]['result']['verification'], 'exact_value')

    def test_input_moves_into_new_popup_while_suggestion_receives_focus(self):
        class Popup(ComputerDouble):
            def observe(self):
                raw = ('0 window Form\n1 text field (settable) City' if not self.value else
                       f'0 window Form\n1 tab Other, Value: off\n4 text field (settable) Search, Value: {self.value}\n5 text {self.value}, Country\nThe focused UI element is 5')
                return describe_window(raw, 'test', [])
        with tempfile.TemporaryDirectory() as root:
            result = TaskRunner(Popup(), JevDouble(['replace_1_city', 'review_completion']), root).run(
                task='Enter city', input_texts={'city': {'text': 'Example', 'purpose': 'City'}})
            self.assertEqual(result['reason'], 'review_completion')
            self.assertEqual(result['history'][1]['result']['observed_value'], 'Example')

    def test_two_state_cycle_stops_before_another_mutation(self):
        class Toggle(ComputerDouble):
            def observe(self):
                return describe_window('0 window Form\n1 button Toggle\n2 text State: ' + str(len(self.calls) % 2), 'test', [])
        with tempfile.TemporaryDirectory() as root:
            computer = Toggle()
            result = TaskRunner(computer, JevDouble(['click_1']*8), root).run(task='Continue')
            self.assertEqual(result['reason'], 'repeated_no_effect')
            self.assertEqual(len(computer.calls), 6)

    def test_combobox_retains_choice_semantics_and_current_value(self):
        obs = describe_window('0 window Form\n1 组合框 (settable) Mode, Value: Round trip', 'test', [])
        self.assertEqual(obs['controls']['1']['role'], 'combobox')
        self.assertEqual(action_menu(obs, {})['click_1']['target']['value'], 'Round trip')

    def test_date_display_requires_matching_selected_year(self):
        class DatePicker(ComputerDouble):
            year = 2027
            def observe(self):
                raw = ('0 window Form\n1 text field (settable) Departure' if not self.value else
                       f'0 window Form\n4 text field (settable) Departure, Value: Tue, Oct 20\n5 cell (selected)\n 6 button Tuesday, October 20, {self.year}, selected date')
                return describe_window(raw, 'test', [])
        for year in (2026, 2027):
            with tempfile.TemporaryDirectory() as root:
                computer = DatePicker()
                computer.year = year
                result = TaskRunner(computer, JevDouble(['replace_1_date', 'review_completion']), root).run(
                    task='Set date', input_texts={'date': {'text': '2026-10-20', 'purpose': 'Departure'}})
                self.assertEqual(result['reason'], 'review_completion' if year == 2026 else 'input_unverified')

    def test_suggestions_arriving_before_handoff_are_decided_without_host(self):
        class Suggestions(ComputerDouble):
            reads = 0
            def observe(self):
                self.reads += 1
                raw = '0 window Form\n1 text field (settable) Query\nThe focused UI element is 1'
                if self.reads > 1:
                    raw += '\n5 button Matching result'
                return describe_window(raw, 'test', [])
        with tempfile.TemporaryDirectory() as root:
            computer = Suggestions()
            result = TaskRunner(computer, JevDouble(['help_input', 'click_5', 'review_completion']), root).run(task='Select matching result')
            self.assertEqual(result['reason'], 'review_completion')
            self.assertEqual(len(computer.calls), 1)
            self.assertEqual(computer.calls[0]['target']['id'], '5')
            self.assertNotIn('help_input', [e['action'].get('type') for e in result['history']])

    def test_focus_summary_only_does_not_hide_document_for_browser_chrome(self):
        raw = ('0 window Form\n 1 web area Page\n  2 listbox Menu\n   3 text Alpha Beta\n 4 tab Other\n'
               'The focused UI element is 99 text Beta')
        view, _, _ = model_view(describe_window(raw, 'test', []), 0)
        self.assertIn('2', view['controls'])
        self.assertNotIn('4', view['controls'])


class FocusTransitionTests(unittest.TestCase):
    def test_replace_uses_popup_editor_reference_after_focus(self):
        from jev_computer_use.computer import Computer
        class Native:
            def __init__(self): self.calls = []
            def js(self, code): self.calls.append(code)
        native = Native()
        computer = Computer(native)
        computer.current_observation = describe_window('1 text field (settable) Date\n2 button Open\nThe focused UI element is 2', 'test', [])
        computer.observe = lambda: describe_window('9 text field (settable) Date\nThe focused UI element is 9', 'test', [])
        computer.execute({'type':'replace', 'target':{'id':'1','role':'textbox','name':'Date'}, 'text':'2026-10-20'})
        self.assertIn('click(1)', native.calls[0])
        self.assertIn('setValue(9,', native.calls[1])

    def test_focus_on_unrelated_field_does_not_receive_text(self):
        from jev_computer_use.computer import Computer
        class Native:
            def __init__(self): self.calls = []
            def js(self, code): self.calls.append(code)
        native = Native()
        computer = Computer(native)
        computer.current_observation = describe_window('1 text field (settable) Name', 'test', [])
        computer.observe = lambda: describe_window('9 text field (settable) Password\nThe focused UI element is 9', 'test', [])
        result = computer.execute({'type':'replace', 'target':{'id':'1','role':'textbox','name':'Name'}, 'text':'hello'})
        self.assertTrue(result['input_deferred'])
        self.assertEqual(len(native.calls), 1)

    def test_focused_text_replacement_pastes_without_autocomplete_typing(self):
        from jev_computer_use.computer import Computer
        class Native:
            def __init__(self): self.calls = []
            def js(self, code): self.calls.append(code)
        native = Native()
        computer = Computer(native)
        computer.current_observation = describe_window('1 text field (settable) Address\nThe focused UI element is 1', 'test', [])
        computer.execute({'type':'replace', 'target':{'id':'1','role':'textbox','name':'Address'}, 'text':'https://example.test/'})
        self.assertIn('pressKey("super+a")', native.calls[0])
        self.assertIn('paste("https://example.test/", {format:"text"})', native.calls[0])
        self.assertNotIn('setValue', native.calls[0])

    def test_deferred_input_returns_new_state_to_jev_without_claiming_fill(self):
        class Popup(ComputerDouble):
            def execute(self, action):
                if action['type'] == 'replace' and not self.focus:
                    self.focus = '1'
                    return {'input_deferred': True, 'detail': 'Editor opened; no text entered'}
                return super().execute(action)
        with tempfile.TemporaryDirectory() as root:
            computer = Popup()
            computer.application = 'test'
            jev = JevDouble(['replace_1_message', 'replace_message', 'review_completion'])
            result = TaskRunner(computer, jev, root).run(task='Fill the message', input_texts={'message':{'text':'hello','purpose':'Message'}})
            self.assertEqual(result['reason'], 'review_completion')
            self.assertEqual(computer.value, 'hello')
            events = [x for x in result['history'] if x['actor'] == 'jev']
            self.assertTrue(events[0]['result']['input_deferred'])
            self.assertNotIn('verification', events[0]['result'])
            self.assertEqual(events[1]['result']['verification'], 'exact_value')

    def test_multiline_editor_uses_addressed_value_instead_of_clipboard(self):
        from jev_computer_use.computer import Computer
        class Native:
            def __init__(self): self.calls = []
            def js(self, code): self.calls.append(code)
        native = Native()
        computer = Computer(native)
        computer.current_observation = describe_window('1 文本输入区 (settable) Message\nThe focused UI element is 1', 'test', [])
        computer.execute({'type':'replace', 'target':{'id':'1','role':'textbox','name':'Message'}, 'text':'hello'})
        self.assertIn('setValue(1, "hello")', native.calls[0])
        self.assertNotIn('paste', native.calls[0])
