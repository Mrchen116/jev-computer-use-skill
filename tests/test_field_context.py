import unittest

from jev_computer_use.computer import action_menu, describe_window


class FieldContextTests(unittest.TestCase):
    def test_unnamed_input_options_quote_the_visible_sibling_without_renaming(self):
        raw = ('0 standard window Form\n'
               ' 1 text Destination\n 2 text field (settable)\n'
               ' 3 text Reference\n 4 text field (settable)\n'
               'The focused UI element is 4 text field')
        observation = describe_window(raw, 'test', [])
        menu = action_menu(observation, {'code': {'text': 'X7', 'purpose': 'reference code'}})
        self.assertEqual(observation['ui_tree'], raw)
        self.assertEqual(observation['controls']['2']['name'], '')
        self.assertEqual(observation['controls']['4']['preceding_text'], 'Reference')
        self.assertIn("AX sibling text: 'Destination'", menu['click_2']['label'])
        self.assertIn("AX sibling text: 'Reference'", menu['replace_code']['label'])
        self.assertIn("AX sibling text: 'Reference'", menu['help_input']['label'])
        self.assertEqual(menu['replace_2_code']['target']['preceding_text'], 'Destination')
        self.assertEqual(menu['replace_code']['target']['preceding_text'], 'Reference')
        self.assertNotIn('Destination', menu['replace_code']['label'])

    def test_text_from_another_level_is_not_presented_as_a_field_sibling(self):
        observation = describe_window(
            '0 standard window Form\n 1 container\n  2 text Unrelated\n 3 text field (settable)',
            'test', [])
        self.assertNotIn('preceding_text', observation['controls']['3'])
        self.assertNotIn('Unrelated', action_menu(observation, {})['click_3']['label'])



class NativeCapabilityTests(unittest.TestCase):
    def test_unfamiliar_editable_role_does_not_lose_input_capability(self):
        for role in ('文本输入区', '搜索文本栏', 'VendorComposeEditor'):
            obs = describe_window(f'0 standard window Form\n 1 {role} (settable) Compose\nThe focused UI element is 1', 'test', [])
            self.assertIn('insert_message', action_menu(obs, {'message': {'text': 'hello', 'purpose': 'message'}}))
            obs['focused_element'] = None
            self.assertIn('replace_1_message', action_menu(obs, {'message': {'text': 'hello', 'purpose': 'message'}}))

    def test_date_field_is_editable_and_metadata_is_not_part_of_value(self):
        obs = describe_window('0 standard window Form\n 1 日期时间区域 (settable, date) Value: 4/12/27, ID: start-datepicker\nThe focused UI element is 1', 'test', [])
        self.assertEqual(obs['controls']['1']['value'], '4/12/27')
        self.assertIn('replace_date', action_menu(obs, {'date': {'text': '2027-08-19', 'purpose': 'date'}}))

    def test_append_preserves_observed_text_and_tracks_changes(self):
        obs = describe_window('0 standard window Form\n 1 text field (settable) Query, Value: train\nThe focused UI element is 1', 'test', [])
        inputs = {'destination': {'text': 'Oslo', 'purpose': 'destination'}}
        action = action_menu(obs, inputs)['append_destination']
        self.assertEqual(action['text'], 'train Oslo')
        obs['controls']['1']['value'] = 'bus'
        self.assertNotEqual(action, action_menu(obs, inputs)['append_destination'])
        obs['controls']['1']['value'] = 'train Oslo'
        self.assertNotIn('append_destination', action_menu(obs, inputs))

    def test_date_only_and_time_only_fields_offer_matching_components(self):
        inputs = {'time': {'text': '07:30', 'purpose': 'time'}, 'date': {'text': '2027-08-19', 'purpose': 'date'}, 'name': {'text': 'Workshop', 'purpose': 'title'}}
        obs = describe_window('0 standard window Form\n 1 日期时间区域 (settable, date) Value: 4/12/27\n 2 text Arrival\n 3 日期时间区域 (settable, date) Value: 8:00 AM\nThe focused UI element is 1', 'test', [])
        actions = action_menu(obs, inputs)
        self.assertNotIn('replace_time', actions)
        self.assertNotIn('replace_name', actions)
        self.assertIn('replace_date', actions)
        self.assertIn('replace_3_time', actions)
        self.assertNotIn('replace_3_date', actions)
        self.assertIn('following AX sibling text', actions['replace_date']['label'])
        self.assertNotIn('append_date', actions)

    def test_checkbox_action_describes_state_transition(self):
        for value, label in [('0', 'Check (currently unchecked)'), ('1', 'Uncheck (currently checked)')]:
            obs = describe_window(f'0 standard window Form\n 1 checkbox Value: {value}\n 2 text Include attachment', 'test', [])
            action = action_menu(obs, {})['click_1']
            self.assertTrue(action['label'].startswith(label))
            self.assertIn('Include attachment', action['label'])

    def test_numeric_and_boolean_controls_are_not_text_fields(self):
        for attr in ('boolean', 'float'):
            obs = describe_window(f'0 standard window Form\n 1 VendorControl (settable, {attr}) Value: 1\nThe focused UI element is 1', 'test', [])
            self.assertNotIn('replace_x', action_menu(obs, {'x': {'text': 'hello', 'purpose': 'text'}}))

    def test_native_time_conversion_keeps_ordinary_text_literal(self):
        from unittest.mock import Mock
        from jev_computer_use.computer import Computer
        native = Mock()
        computer = Computer(native)
        computer.execute({'type': 'replace', 'target': {'id': '2', 'role': 'datefield'}, 'text': '19:30'})
        self.assertIn('"7:30 PM"', native.js.call_args.args[0])
        computer.execute({'type': 'replace', 'target': {'id': '2', 'role': 'textbox'}, 'text': '19:30'})
        self.assertIn('"19:30"', native.js.call_args.args[0])

    def test_normalized_time_verification_rejects_different_time(self):
        from jev_computer_use.computer import equivalent_value
        self.assertTrue(equivalent_value('07:30', '7:30\u202fAM'))
        self.assertFalse(equivalent_value('07:30', '7:30 PM'))
        self.assertTrue(equivalent_value('2027-08-19', '8/19/27'))
        self.assertFalse(equivalent_value('2027-08-19', '8/20/27'))

    def test_no_effect_click_removed_only_on_unchanged_screen(self):
        from jev_computer_use.tasks import decision_payload
        from jev_computer_use.observations import observation_id
        obs = describe_window('0 standard window Browser\n 1 text Multiple suggestions\nThe focused UI element is 1', 'test', [])
        action = action_menu(obs, {})['click_1']
        history = [{'action': action, 'result': {'status': 'executed', 'interface_changed': False, 'observation_id': observation_id(obs)}}]
        self.assertNotIn('click_1', decision_payload('Navigate', history, obs, {}, [])[1])
        obs['ui_tree'] += '\n 2 text New result'
        self.assertIn('click_1', decision_payload('Navigate', history, obs, {}, [])[1])

    def test_large_tree_paging_keeps_every_control_reachable(self):
        from jev_computer_use.tasks import model_view
        raw = '0 standard window Large\n' + '\n'.join(f' {i} button Option {i} ' + 'x' * 150 for i in range(1, 250))
        obs = describe_window(raw, 'test', [])
        first, _, count = model_view(obs, 0)
        self.assertGreater(count, 1)
        found = set()
        for page in range(count):
            view, _, _ = model_view(obs, page)
            found.update(action_menu(view, {}))
        self.assertTrue(all(f'click_{i}' in found for i in range(1, 250)))
        self.assertEqual(obs['ui_tree'], raw)

    def test_accumulated_ui_dates_are_paged_without_losing_values(self):
        from jev_computer_use.tasks import input_view
        values = {'name': {'text': 'Workshop', 'purpose': 'title'}}
        values.update({f'observed_date_{i}': {'text': str(i), 'purpose': 'source'} for i in range(40)})
        first, _, count = input_view(values, 0)
        self.assertIn('observed_date_39', first)
        found = {}
        for page in range(count):
            view, _, _ = input_view(values, page)
            self.assertIn('name', view)
            self.assertLessEqual(len(view), 13)
            found.update(view)
        self.assertEqual(found, values)

    def test_observed_date_carries_source_not_holiday_knowledge(self):
        from jev_computer_use.computer import observed_dates
        values = observed_dates('4 event Description: Workshop. 2027-08-19, all day')
        self.assertEqual(values['observed_date_20270819']['text'], '8/19/27')
        self.assertIn('Workshop', values['observed_date_20270819']['purpose'])
        self.assertEqual(observed_dates('4 日程 Description: Workshop'), {})


if __name__ == '__main__':
    unittest.main()
