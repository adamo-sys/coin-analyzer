"""Deterministic validation tests for Task and Outcome Packet artifacts."""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('task_packet', ROOT / 'tools/task-packet.py')
assert SPEC is not None and SPEC.loader is not None
task_packet = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(task_packet)


class PacketValidationTests(unittest.TestCase):
    def invoke(self, kind, path):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = task_packet.main(['validate', '--kind', kind, '--path', str(path)])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_repository_templates_are_valid(self):
        for kind, filename in (
            ('task', '.ops/task-packet.template.json'),
            ('outcome', '.ops/outcome-packet.template.json'),
        ):
            with self.subTest(kind=kind):
                code, stdout, stderr = self.invoke(kind, ROOT / filename)
                self.assertEqual(code, 0, stderr)
                self.assertEqual(stdout, f'valid {kind} packet\n')

    def test_task_packet_rejects_missing_required_field(self):
        packet = json.loads((ROOT / '.ops/task-packet.template.json').read_text(encoding='utf-8'))
        del packet['objective']
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'task.json'
            path.write_text(json.dumps(packet), encoding='utf-8')
            code, _, stderr = self.invoke('task', path)
        self.assertEqual(code, 2)
        self.assertIn('missing required field: objective', stderr)

    def test_task_packet_rejects_unknown_execution_class(self):
        packet = json.loads((ROOT / '.ops/task-packet.template.json').read_text(encoding='utf-8'))
        packet['execution_class'] = 'CODEX_EXPERIMENT'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'task.json'
            path.write_text(json.dumps(packet), encoding='utf-8')
            code, _, stderr = self.invoke('task', path)
        self.assertEqual(code, 2)
        self.assertIn('invalid execution_class', stderr)

    def test_outcome_packet_rejects_malformed_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'outcome.json'
            path.write_text('{', encoding='utf-8')
            code, _, stderr = self.invoke('outcome', path)
        self.assertEqual(code, 2)
        self.assertIn('malformed JSON', stderr)


if __name__ == '__main__':
    unittest.main()
