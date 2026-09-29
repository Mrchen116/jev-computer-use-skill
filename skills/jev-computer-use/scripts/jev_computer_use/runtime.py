"""Call Codex's installed CUA runtime directly over MCP, without LLM dispatch."""
import json
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import sys
import threading


def runtime_configuration(config=None):
    """Resolve the installed plugin manifest without bundling its runtime."""
    config = config or os.environ.get('JEV_CUA_CONFIG')
    if config is None:
        home = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex'))
        configs = list((home / 'plugins/cache/openai-bundled/unified-computer-use').glob('*/.mcp.json'))
        if not configs:
            raise RuntimeError('Install Codex Computer Use, or pass --runtime-config /path/to/.mcp.json')
        config = max(configs, key=lambda p: tuple(int(n) for n in re.findall(r'\d+', p.parent.name)))
    path = Path(config).expanduser()
    cfg = json.loads(path.read_text())['mcpServers']['cua_repl']
    if not Path(cfg['command']).is_file():
        raise RuntimeError('The runtime executable in the plugin manifest is missing; update/reinstall the plugin')
    return path, cfg


class NativeCUA:
    """Single-threaded client; native app permissions remain enforced by CUA."""

    def __init__(self, config=None, permission_handler=None):
        self.permission_handler = permission_handler
        self._app_approvals = set()
        self.config, cfg = runtime_configuration(config)
        # No Codex thread metadata, login tokens, or API keys are needed for transport.
        env = {k: os.environ[k] for k in ('HOME', 'PATH', 'TMPDIR', 'USER', 'SHELL') if k in os.environ}
        env.update(cfg.get('env', {}))
        self.process = subprocess.Popen(
            [cfg['command'], *cfg.get('args', [])], env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            start_new_session=True,
        )
        self.responses = queue.Queue()
        self.sequence = 0
        self.tool_calls = 0
        self.request_meta = None

        def read():
            try:
                for line in self.process.stdout:
                    self.responses.put(json.loads(line))
            except Exception as error:
                self.responses.put(error)
            finally:
                self.responses.put(None)

        threading.Thread(target=read, daemon=True).start()
        try:
            self.server = self.request('initialize', {
                'protocolVersion': '2024-11-05',
                'capabilities': {'elicitation': {'form': {}}},
                'clientInfo': {'name': 'jev-computer-use', 'version': '0.2.0'},
            })
            self.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        except BaseException:
            self.close()
            raise

    def send(self, message):
        self.process.stdin.write(json.dumps(message) + '\n')
        self.process.stdin.flush()

    def _elicitation(self, request):
        """Relay native permission forms to the human; never silently approve."""
        params = request['params']
        if self.permission_handler:
            self.send({'jsonrpc': '2.0', 'id': request['id'], 'result': self.permission_handler(params)})
            return
        schema = params.get('requestedSchema', {})
        # Reuse only this process's explicit approval of the identical, empty
        # app-access form. Other permission forms always go back to the user.
        app_form = bool(re.fullmatch(r'Allow Computer Use to use "[^"]+"\?', params.get('message', '')) and schema == {'properties': {}, 'type': 'object'})
        approval = params.get('message', '')
        if app_form and approval in self._app_approvals:
            self.send({'jsonrpc': '2.0', 'id': request['id'], 'result': {'action': 'accept', 'content': {}}})
            return
        print('\nComputer Use permission request:', params.get('message', ''), file=sys.stderr)
        result = {'action': 'cancel'}
        if sys.stdin.isatty():
            print(json.dumps(schema, ensure_ascii=False, indent=2), file=sys.stderr)
            print('Enter form fields as JSON to approve, or press Enter to cancel: ', end='', file=sys.stderr, flush=True)
            raw = input().strip()
            if raw:
                content = json.loads(raw)
                if not isinstance(content, dict):
                    raise ValueError('Permission form response must be a JSON object')
                result = {'action': 'accept', 'content': content}
                if app_form and content == {}:
                    self._app_approvals.add(approval)
        self.send({'jsonrpc': '2.0', 'id': request['id'], 'result': result})

    def request(self, method, params):
        if method == 'tools/call' and self.request_meta:
            params = {**params, '_meta': self.request_meta}
        self.sequence += 1
        self.send({'jsonrpc': '2.0', 'id': self.sequence, 'method': method, 'params': params})
        while True:
            try:
                response = self.responses.get(timeout=65)
            except queue.Empty:
                raise RuntimeError('CUA response timed out; inspect the app before retrying') from None
            if isinstance(response, Exception):
                raise response
            if response is None:
                raise RuntimeError('CUA runtime exited')
            if 'method' in response:
                if response['method'] == 'elicitation/create':
                    self._elicitation(response)
                elif 'id' in response:
                    self.send({'jsonrpc': '2.0', 'id': response['id'],
                               'error': {'code': -32601, 'message': 'Unsupported client request'}})
                continue
            if response.get('id') == self.sequence:
                if 'error' in response:
                    raise RuntimeError(response['error'])
                return response['result']

    def js(self, code):
        self.tool_calls += 1
        result = self.request('tools/call', {
            'name': 'js', 'arguments': {'code': code, 'timeout_ms': 60000},
        })
        text = '\n'.join(block['text'] for block in result.get('content', []) if block['type'] == 'text')
        if result.get('isError'):
            raise RuntimeError(text)
        return text

    def select_app(self, app):
        return self.js('var app = await cua.getApp(' + json.dumps(app) + ');')

    def observe(self):
        return self.js('await app.getAXState({disableDiffing: true});')

    def click(self, target):
        return self.js('await app.click(' + json.dumps(target) + '); await app.getAXState();')

    def type_text(self, text):
        return self.js('await app.typeText(' + json.dumps(text) + '); await app.getAXState();')

    def press_key(self, key):
        return self.js('await app.pressKey(' + json.dumps(key) + '); await app.getAXState();')

    def close(self):
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
