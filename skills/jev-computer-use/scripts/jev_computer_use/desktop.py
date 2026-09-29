"""Native desktop observation and execution; no model calls or website routes."""
import json
import re
import time
from .runtime import NativeCUA

# These are macOS AX role descriptions, not website-specific selectors.
ROLE_NAMES = {
    '文本输入区': 'textbox', '搜索文本栏': 'textbox', 'search text field': 'textbox',
    '日期时间区域': 'datefield', 'date time area': 'datefield',
    '日程': 'event', '列表': 'list', '内容列表': 'list', 'list': 'list',
    '文本栏': 'textbox', '文本字段': 'textbox', '文本框': 'textbox', '文本区域': 'textbox',
    'text field': 'textbox', 'text area': 'textbox', 'combo box': 'textbox', '组合框': 'textbox',
    '按钮': 'button', 'button': 'button', '弹出式按钮': 'button', 'pop up button': 'button',
    '菜单按钮': 'button', 'menu button': 'button', '链接': 'link', 'link': 'link',
    '复选框': 'checkbox', 'checkbox': 'checkbox', '单选按钮': 'radio', 'radio button': 'radio',
    '标签': 'tab', 'tab': 'tab', '菜单项': 'menuitem', 'menu item': 'menuitem',
    '滚动区': 'scrollarea', 'scroll area': 'scrollarea',
    'HTML 内容': 'webarea', 'web area': 'webarea',
    '菜单栏': 'menubar', 'menu bar': 'menubar',
    '文本': 'text', 'text': 'text', 'static text': 'text', '标题': 'heading', 'heading': 'heading',
    'container': 'container', '列表框': 'listbox', 'list box': 'listbox', 'listbox': 'listbox',
    '表格': 'table', 'table': 'table', 'row': 'row', '行': 'row', '单元格': 'cell', 'cell': 'cell',
}
ROLE_NAMES = {k.lower(): v for k, v in ROLE_NAMES.items()}
ROLE_PATTERN = '|'.join(re.escape(s) for s in sorted(ROLE_NAMES, key=len, reverse=True))
NODE = re.compile(r'^(\s*)(\d+)\s+(.+)$')
ROLE = re.compile(r'(' + ROLE_PATTERN + r')(?=\s|$)(.*)', re.I)
PAGE_SIZE = 130


def nodes(raw):
    parsed = []
    for line in raw.splitlines():
        if line.startswith("The focused UI element is "):
            continue
        match = NODE.match(line)
        if not match:
            # AX text values can span lines (e.g. a receipt or saved JSON). Keeping
            # only the numbered first line would silently discard final evidence.
            if parsed and parsed[-1]['role'] in ('text', 'textbox') and line.strip():
                parsed[-1]['detail'] += '\n' + line.strip()
                parsed[-1]['line'] += '\n' + line
            continue
        space, ref, rest = match.groups()
        role = ROLE.match(rest)
        name, detail = (ROLE_NAMES[role[1].lower()], role[2].strip()) if role else ('other', rest)
        parsed.append({'ref': ref, 'role': name, 'detail': detail, 'depth': len(space.expandtabs(4)), 'line': line})
    return parsed


def visible_page_url(raw):
    """Read the page URL from native metadata or an unfocused browser address bar."""
    parsed = nodes(raw)
    root = next((n for n in parsed if n['role'] == 'webarea'), None)
    metadata = root['detail'] if root else raw.splitlines()[0] if raw else ''
    match = re.search(r'\bURL: ([^\s,]+)', metadata)
    url = match[1] if match else ''
    if url and '…' not in url:
        return url
    # Native AX sometimes elides URL attributes while retaining the browser's
    # visible address. Never use a page-owned input or an address being edited.
    if root and url == '…':
        focused = re.search(r'The focused UI element is (\d+)\b', raw)
        for node in parsed:
            if node is root:
                break
            if node['role'] != 'textbox' or (focused and focused[1] == node['ref']):
                continue
            detail = re.sub(r'^(?:\([^)]*\)\s*)+', '', node['detail'])
            address = re.match(
                r'(?:Address and search bar|地址和搜索栏), Value: (.*?)(?=, (?:Placeholder|Help):|$)',
                detail,
                re.I,
            )
            if address and '…' not in address[1]:
                return address[1]
    return ''


def observation(raw, app=None, scope='window', offset=0, url=None):
    """Expose current window or its tabs. All controls remain reachable by paging."""
    all_nodes = nodes(raw)
    tabs = [n for n in all_nodes if n['role'] == 'tab']
    menu_depth = None
    controls = {}
    content = []
    previous_content = None
    for node in all_nodes:
        role, detail, ref = node['role'], node['detail'], node['ref']
        if role == 'menubar':
            menu_depth = node['depth']
        elif menu_depth is not None and node['depth'] <= menu_depth:
            menu_depth = None
        if scope == 'tabs' and role != 'tab':
            continue
        if scope == 'window' and role == 'tab':
            continue
        text = re.sub(r'^(?:\([^)]*\)\s*)+', '', detail)
        if text and role != 'other':
            item = role + ': ' + text
            # Repeated values in different sections carry different meaning:
            # method parameters, timestamps and form state must retain context.
            if item != previous_content:
                content.append(item)
            previous_content = item
        if '(disabled)' in detail:
            continue
        target = {'ref': ref, 'role': role, 'label': text or role,
                  'name': re.split(r', (?:Value|URL|Placeholder|Help|Secondary Actions):', text)[0]}
        value = re.search(r'(?:^|, )Value: (.*?)(?=, (?:Placeholder|URL|Help):|$)', text)
        if value:
            target['value'] = value[1]
        if role == 'textbox':
            controls['fill_' + ref] = {**target, 'verb': 'fill'}
        elif role in ('button', 'link', 'checkbox', 'radio', 'tab', 'menuitem') or (menu_depth is not None and node['depth'] > menu_depth):
            controls['click_' + ref] = {**target, 'verb': 'click'}
        elif role in ('scrollarea', 'webarea'):
            for direction in ('down', 'up'):
                controls[f'scroll_{direction}_{ref}'] = {**target, 'verb': 'scroll', 'direction': direction,
                                                       'label': f'Scroll {direction} in {text or role}'}
    # URLs from window metadata are visible evidence even in a non-web AX root.
    first = raw.splitlines()[0] if raw else ''
    url = visible_page_url(raw) if url is None else url
    pairs = list(controls.items())
    offset = min(offset, max(0, (len(pairs)-1)//PAGE_SIZE*PAGE_SIZE))
    actions = dict(pairs[offset:offset + PAGE_SIZE])
    extra = {
        'switch_app': 'Choose another application from the desktop inventory',
        'enter': 'Press Return in the currently focused control; applies/activates it',
        'escape': 'Press Escape to dismiss the current menu or dialog',
        'keyboard': 'Ask LLM for ONE keyboard shortcut appropriate to the selected app; no text or commands',
        'wait': 'Wait briefly for a pending UI update',
        'help': 'Ask LLM to suggest one of the available actions when unable to decide',
        'done': 'Propose completion for LLM evidence verification',
        'stop': 'Stop because the task cannot be completed from available capabilities or information',
    }
    # Group tab inventory by AX role; no domain or task matching determines visibility.
    if tabs:
        extra['show_tabs' if scope == 'window' else 'show_window'] = (
            f'Inspect/select the {len(tabs)} tabs' if scope == 'window' else 'Return to the selected window content')
    if offset:
        extra['previous_controls'] = 'Inspect the previous batch of controls in this same window'
    if offset + PAGE_SIZE < len(pairs):
        extra['more_controls'] = 'Inspect the next batch of controls in this same window'
    actions.update({k: {'verb': k, 'label': label} for k, label in extra.items()})
    page = '\n'.join([first, 'URL: '+url, *content])
    return {'raw': raw, 'page': page, 'url': url, 'app': app, 'scope': scope,
            'controls_range': [offset, min(offset+PAGE_SIZE, len(pairs)), len(pairs)],
            'actions': actions, 'fields': [a for a in controls.values() if a['verb'] == 'fill']}


def descriptions(actions):
    result = {}
    for key, action in actions.items():
        description = action['label']
        if 'ref' in action:
            description = f"{action['verb']} {action['role']}: {description}"
        if action['verb'] == 'fill':
            description += '; LLM supplies text; replace field content, without pressing Return'
        result[key] = description
    return result


class Desktop:
    def __init__(self, config=None, permission_handler=None):
        self.client = NativeCUA(config, permission_handler=permission_handler)
        self.app = None
        self.scope = 'window'
        self.offset = 0

    def _json(self, expression):
        text = self.client.js('nodeRepl.write("CUA_JSON:" + JSON.stringify(' + expression + '));')
        return json.loads(text.rsplit('CUA_JSON:', 1)[1].strip())

    def observe(self):
        if self.app is None:
            apps = self._json('await cua.listApps({emit: false})')
            public = [{k: a[k] for k in ('id', 'displayName', 'isRunning') if k in a} for a in apps]
            actions = {f'app_{i}': {'verb': 'app', 'app': a['id'], 'label': a.get('displayName', a['id'])}
                       for i, a in enumerate(apps)}
            actions['open_app'] = {'verb': 'open_app', 'label': 'Ask LLM for an app name/bundle ID not listed here, then select that app'}
            actions['stop'] = {'verb': 'stop', 'label': 'Stop if the task cannot be attempted'}
            page = 'Desktop application inventory. No app selected yet.\n' + json.dumps(public, ensure_ascii=False)
            return {'raw': page, 'page': page, 'url': '', 'app': None, 'scope': 'apps', 'actions': actions}
        raw = self._json('await app.getAXState({emit: false, disableDiffing: true})')
        return observation(raw, self.app, self.scope, self.offset)

    def execute(self, action, value=None):
        verb = action['verb']
        if verb in ('app', 'open_app'):
            app = action['app'] if verb == 'app' else value
            self.client.select_app(app)
            self.app = app
            self.scope, self.offset = 'window', 0
        elif verb == 'switch_app':
            self.app = None
        elif verb in ('show_tabs', 'show_window'):
            self.scope = 'tabs' if verb == 'show_tabs' else 'window'
            self.offset = 0
        elif verb in ('more_controls', 'previous_controls'):
            self.offset += PAGE_SIZE if verb == 'more_controls' else -PAGE_SIZE
        elif verb == 'wait':
            time.sleep(1)
        else:
            ref = int(action['ref']) if 'ref' in action else None
            if verb == 'fill':
                code = f'await app.click({ref}); await app.setValue({ref}, {json.dumps(value)});'
            elif verb == 'click':
                code = f'await app.click({ref});'
            elif verb == 'scroll':
                code = f'await app.scroll({ref}, {json.dumps(action["direction"])}, 1);'
            elif verb in ('enter', 'escape', 'keyboard'):
                key = {'enter': 'Return', 'escape': 'Escape'}.get(verb, value)
                code = f'await app.pressKey({json.dumps(key)});'
            else:
                raise ValueError('Unsupported action: ' + verb)
            self.client.js(code)
            self.scope, self.offset = 'window', 0
        result = self.observe()
        if verb == 'fill':
            matches = [a for a in result['fields'] if a.get('name') == action.get('name')]
            same_ref = [a for a in matches if a['ref'] == action['ref']]
            target = same_ref[0] if same_ref else matches[0] if len(matches) == 1 else None
            if target is None or target.get('value', '') != value:
                actual = target.get('value') if target else '[field not found]'
                raise RuntimeError(f'Input value was not verified: expected {value!r}, observed {actual!r}')
        return result

    def close(self):
        self.client.close()
