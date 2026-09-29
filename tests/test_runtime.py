import json
import io
from unittest.mock import Mock, patch
from pathlib import Path
import sys
import tempfile
import unittest

from jev_computer_use.runtime import runtime_configuration


class RuntimeTests(unittest.TestCase):
    def test_explicit_manifest_uses_installed_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'.mcp.json'
            config = {'command': sys.executable, 'args': ['runtime.py'], 'env': {'EXAMPLE': 'value'}}
            path.write_text(json.dumps({'mcpServers': {'cua_repl': config}}))
            observed_path, observed = runtime_configuration(path)
            self.assertEqual(observed_path, path)
            self.assertEqual(observed, config)

    def test_stale_manifest_fails_with_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'.mcp.json'
            path.write_text(json.dumps({'mcpServers': {'cua_repl': {'command': str(Path(directory)/'missing')}}}))
            with self.assertRaisesRegex(RuntimeError, 'missing'):
                runtime_configuration(path)


class PermissionTests(unittest.TestCase):
    def test_app_approval_is_process_scoped_and_other_forms_are_not_cached(self):
        from jev_computer_use.runtime import NativeCUA
        native = NativeCUA.__new__(NativeCUA)
        native.permission_handler = None
        native._app_approvals = set()
        native.send = Mock()
        request = {'id': 1, 'params': {'message': 'Allow Computer Use to use "Test"?', 'requestedSchema': {'properties': {}, 'type': 'object'}}}
        with patch('sys.stdin.isatty', return_value=True), patch('builtins.input', return_value='{}') as answer, patch('sys.stderr', new_callable=io.StringIO):
            native._elicitation(request)
            native._elicitation(request)
            self.assertEqual(answer.call_count, 1)
            request['params']['message'] = 'Grant a new permission?'
            native._elicitation(request)
            native._elicitation(request)
            self.assertEqual(answer.call_count, 3)


if __name__ == '__main__':
    unittest.main()
