"""Describe conventional month grids from observed AX text, without UI scripting."""

import calendar
import re


MONTH = re.compile(r'\b(' + '|'.join(calendar.month_name[1:]) + r')\s+(\d{4})\b', re.I)
WEEKDAYS = {'Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'}


def annotate_month_grids(parsed, controls):
    """Attach dates to numbered day links only inside a recognized month grid."""
    for index, table in enumerate(parsed):
        if table['role'] != 'table':
            continue
        end = next((i for i in range(index + 1, len(parsed))
                    if parsed[i]['depth'] <= table['depth']), len(parsed))
        children = parsed[index + 1:end]
        if not WEEKDAYS.issubset({n['detail'] for n in children if n['role'] == 'text'}):
            continue
        # A calendar header precedes its table at the same container level.
        start = index - 1
        while start >= 0 and parsed[start]['depth'] >= table['depth'] and parsed[start]['role'] != 'table':
            start -= 1
        header = parsed[start + 1:index]
        periods = {(m[1].lower(), int(m[2])) for n in header for m in MONTH.finditer(n['detail'])}
        if len(periods) != 1:
            continue
        name, year = periods.pop()
        month = next(i for i in range(1, 13) if calendar.month_name[i].lower() == name)
        if not 1 < year < 9999:
            continue
        period = f'{calendar.month_name[month]} {year}'
        for node in children:
            control = controls.get(node['ref'])
            if not control or control['role'] not in ('link', 'button') or not re.fullmatch(r'\d{1,2}', control['name']):
                continue
            day = int(control['name'])
            if 1 <= day <= calendar.monthrange(year, month)[1]:
                control['calendar_context'] = f'Calendar date: {calendar.month_name[month]} {day}, {year}.'
        for node in header:
            control = controls.get(node['ref'])
            if not control or control['role'] not in ('link', 'button'):
                continue
            direction = {'prev': -1, 'previous': -1, 'previous month': -1,
                         'next': 1, 'next month': 1}.get(control['name'].lower())
            if direction:
                offset = year * 12 + month - 1 + direction
                target_year, target_month = divmod(offset, 12)
                control['calendar_context'] = (f'Currently {period}; changes displayed month to '
                                               f'{calendar.month_name[target_month + 1]} {target_year}.')
