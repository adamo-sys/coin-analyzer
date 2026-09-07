from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "coin_collection_gui.py"


class CoinCollectionGUIEntrypointTests(unittest.TestCase):
    def _entrypoint_guard(self) -> ast.If:
        tree = ast.parse(ENTRYPOINT.read_text(encoding="utf-8"))
        guards = [
            node
            for node in tree.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        ]
        self.assertEqual(len(guards), 1)
        return guards[0]

    def test_importing_supported_gui_does_not_launch_application(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import coin_collection_gui; print('IMPORT_COMPLETED')",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "IMPORT_COMPLETED")

    def test_supported_entrypoint_invokes_main_exactly_once(self) -> None:
        guard = self._entrypoint_guard()
        entry_module = ast.Module(body=[guard], type_ignores=[])
        ast.fix_missing_locations(entry_module)
        main = Mock()

        startup = Mock(return_value=1)
        with patch.dict(sys.modules, {"coin_analyzer_startup": SimpleNamespace(main=startup)}):
            with self.assertRaises(SystemExit) as raised:
                exec(
                    compile(entry_module, str(ENTRYPOINT), "exec"),
                    {"__name__": "__main__", "main": main},
                )

        startup.assert_called_once_with()
        main.assert_not_called()
        self.assertEqual(raised.exception.code, 1)

    def test_import_and_close_path_has_no_second_entrypoint_invocation(self) -> None:
        guard = self._entrypoint_guard()
        startup_calls = [
            node for node in ast.walk(guard)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "startup_main"
        ]
        self.assertEqual(len(startup_calls), 1)
        self.assertIsInstance(guard.body[-1], ast.Raise)
        tree = ast.parse(ENTRYPOINT.read_text(encoding="utf-8"))
        dependency_imports = [
            node for node in tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        self.assertTrue(dependency_imports)
        self.assertLess(guard.lineno, min(node.lineno for node in dependency_imports))


if __name__ == "__main__":
    unittest.main()
