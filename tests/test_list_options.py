"""Autocomplete meaning comes from observed list structure and focused query."""
import unittest

from jev_computer_use.computer import action_menu, describe_window
from jev_computer_use.decisions import action_space


class ListOptionTests(unittest.TestCase):
    def menu(self, query='Oslo', focus='2'):
        raw = ('0 window Form\n 1 text Oslo instructions\n'
               f' 2 text field (settable) City, Value: {query}\n'
               ' 3 内容列表\n  4 text OSLO, Norway\n  5 text Paris, France\n'
               f'The focused UI element is {focus}')
        return action_menu(describe_window(raw, 'test', []), {})

    def test_matching_list_text_is_an_option_but_executes_native_click(self):
        menu = self.menu()
        self.assertEqual(menu['click_4']['semantic_operation'], 'select_option')
        self.assertEqual(menu['click_4']['type'], 'click')
        self.assertEqual(menu['click_4']['target']['id'], '4')
        self.assertIn('click_4', action_space(menu)['select_option'])
        for key in ('click_1', 'click_5'):
            self.assertNotIn('semantic_operation', menu[key])
            self.assertIn(key, action_space(menu)['click'])

    def test_empty_or_unfocused_query_does_not_invent_suggestions(self):
        for menu in (self.menu(query=''), self.menu(focus='1')):
            self.assertNotIn('select_option', action_space(menu))
