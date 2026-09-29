"""Month-grid semantics must come from AX structure, not a task-specific route."""
import unittest

from jev_computer_use.computer import action_menu, describe_window


def month_grid(month='December 2030', days=('1', '19'), weekdays=True):
    return ('0 window Form\n 1 text Departure\n 2 text field\n 3 container\n'
            '  4 link Prev\n  5 text Next ' + month + '\n 6 table\n'
            + ''.join(f'  {10+i} text {day}\n' for i, day in enumerate(('Su','Mo','Tu','We','Th','Fr','Sa') if weekdays else ()))
            + ''.join(f'  {30+i} link {day}\n' for i, day in enumerate(days))
            + 'The focused UI element is 2')


class CalendarViewTests(unittest.TestCase):
    def test_observed_month_supplies_day_and_navigation_meaning(self):
        obs = describe_window(month_grid(), 'test', [])
        menu = action_menu(obs, {})
        self.assertIn('December 19, 2030', menu['click_31']['label'])
        self.assertIn('November 2030', menu['click_4']['label'])
        self.assertNotIn('click_2', menu)
        self.assertNotIn('click_1', menu)
        self.assertIn('December 2030', obs['ui_tree'])

    def test_year_boundary_and_non_calendar_tables(self):
        obs = describe_window(month_grid('January 2031'), 'test', [])
        self.assertIn('December 2030', action_menu(obs,{})['click_4']['label'])
        for raw in (month_grid(weekdays=False), month_grid('December 2030 January 2031')):
            obs = describe_window(raw, 'test', [])
            self.assertFalse(any(c.get('calendar_context') for c in obs['controls'].values()))
            self.assertIn('click_2', action_menu(obs,{}))

    def test_unfocused_readonly_picker_remains_openable(self):
        raw = month_grid().replace('The focused UI element is 2', 'The focused UI element is 4')
        self.assertIn('click_2', action_menu(describe_window(raw,'test',[]),{}))
