"""Offline readiness and bootstrap acceptance with synthetic dependency probes."""
from dataclasses import FrozenInstanceError
from io import StringIO
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from coin_analyzer_startup import main
from runtime_readiness import (
    CORE_MODULES, Capability, DiagnosticResult, ReadinessReport, Status, evaluate_readiness,
)

ROOT = Path(__file__).resolve().parents[1]
SECRET = "synthetic-private-exception-and-key"


class RuntimeReadinessTests(unittest.TestCase):
    def evaluate(self, *, missing=(), configured=False, found=True, version=(3, 12)):
        def importer(name):
            if name in missing:
                print(SECRET, file=sys.stderr)
                raise ImportError(SECRET)
            return SimpleNamespace(pytesseract=SimpleNamespace(tesseract_cmd="synthetic-tesseract"))
        return evaluate_readiness(importer=importer, which=lambda _: "found" if found else None,
                                  environ={"OPENAI_API_KEY": SECRET if configured else " "},
                                  version=version)

    def test_each_required_import_failure_blocks_core_with_safe_action(self):
        for dependency in CORE_MODULES:
            with self.subTest(dependency=dependency):
                output = StringIO()
                with patch("sys.stderr", output):
                    report = self.evaluate(missing=(dependency,))
                self.assertEqual(report.status_for(Capability.CORE), Status.UNAVAILABLE)
                failed = [check for check in report.checks if check.check_id == "core." + dependency][0]
                self.assertTrue(failed.action)
                self.assertNotIn(SECRET, repr(report) + output.getvalue())

    def test_optional_absence_never_blocks_core_or_launch(self):
        report = self.evaluate(missing=("openai", "pytesseract"))
        self.assertEqual(report.status_for(Capability.CORE), Status.READY)
        self.assertEqual(report.status_for(Capability.OCR), Status.UNAVAILABLE)
        self.assertEqual(report.status_for(Capability.AI), Status.UNAVAILABLE)
        launch = Mock()
        self.assertEqual(main(evaluator=lambda: report, launch=launch, output=StringIO()), 0)
        launch.assert_called_once_with()

    def test_installed_optional_prerequisites_do_not_claim_working_services(self):
        report = self.evaluate(configured=True)
        self.assertEqual(report.status_for(Capability.OCR), Status.UNVERIFIED)
        self.assertEqual(report.status_for(Capability.AI), Status.UNVERIFIED)
        self.assertNotIn(SECRET, repr(report))

    def test_missing_engine_and_blank_key_are_unavailable(self):
        report = self.evaluate(found=False)
        self.assertEqual(report.status_for(Capability.OCR), Status.UNAVAILABLE)
        self.assertEqual(report.status_for(Capability.AI), Status.UNAVAILABLE)

    def test_engine_probe_failure_does_not_leak_exception(self):
        report = evaluate_readiness(
            importer=lambda _: SimpleNamespace(pytesseract=SimpleNamespace(tesseract_cmd="test")),
            which=Mock(side_effect=OSError(SECRET)), environ={}, version=(3, 12))
        self.assertEqual(report.status_for(Capability.OCR), Status.UNAVAILABLE)
        self.assertNotIn(SECRET, repr(report))

    def test_incompatible_runtime_does_not_import_dependencies(self):
        for version in ((2, 7), (3, 11), (4, 0)):
            with self.subTest(version=version):
                importer = Mock()
                report = evaluate_readiness(importer=importer, version=version)
                self.assertEqual(report.status_for(Capability.CORE), Status.UNAVAILABLE)
                importer.assert_not_called()
                evaluator = Mock()
                output = StringIO()
                self.assertEqual(main(version=version, evaluator=evaluator, output=output), 1)
                evaluator.assert_not_called()
                self.assertIn("3.12", output.getvalue())

    def test_compatible_runtimes_and_incomplete_report(self):
        for version in ((3, 12), (3, 14)):
            self.assertEqual(self.evaluate(version=version).status_for(Capability.CORE), Status.READY)
        self.assertEqual(ReadinessReport(()).status_for(Capability.CORE), Status.UNVERIFIED)
        partial = ReadinessReport([DiagnosticResult("core.python", Capability.CORE,
                                                   Status.READY, "runtime only")])
        self.assertIsInstance(partial.checks, tuple)
        self.assertEqual(partial.status_for(Capability.CORE), Status.UNVERIFIED)
        report = self.evaluate()
        with self.assertRaises(FrozenInstanceError):
            report.checks = ()
        with self.assertRaises(FrozenInstanceError):
            report.checks[0].message = "changed"

    def test_core_failure_prevents_gui_and_prints_actionable_diagnostic(self):
        launch = Mock()
        output = StringIO()
        self.assertEqual(main(evaluator=lambda: self.evaluate(missing=("cv2",)),
                              launch=launch, output=output), 1)
        launch.assert_not_called()
        self.assertIn("requirements.txt", output.getvalue())
        self.assertNotIn(SECRET, output.getvalue())

    def test_probe_and_gui_failures_have_safe_nonzero_outcomes(self):
        for evaluator, launch in (
            (Mock(side_effect=RuntimeError(SECRET)), Mock()),
            (lambda: self.evaluate(), Mock(side_effect=RuntimeError(SECRET))),
        ):
            with self.subTest(evaluator=evaluator):
                output = StringIO()
                self.assertEqual(main(evaluator=evaluator, launch=launch, output=output), 1)
                self.assertNotIn(SECRET, output.getvalue())
                self.assertIn("dependencies", output.getvalue())

    def test_direct_gui_script_delegates_before_dependency_imports(self):
        bootstrap = SimpleNamespace(main=Mock(return_value=1))
        with patch.dict(sys.modules, {"coin_analyzer_startup": bootstrap}):
            with self.assertRaises(SystemExit) as raised:
                runpy.run_path(str(ROOT / "coin_collection_gui.py"), run_name="__main__")
        self.assertEqual(raised.exception.code, 1)
        bootstrap.main.assert_called_once_with()

    @unittest.skipUnless(sys.platform == "win32", "Windows batch launcher acceptance")
    def test_windows_launcher_prefers_adjacent_venv_and_preserves_exit_code(self):
        with tempfile.TemporaryDirectory(prefix="readiness space ") as temporary:
            root = Path(temporary)
            subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(root / ".venv")],
                           check=True, capture_output=True, timeout=30)
            shutil.copyfile(ROOT / "Launch_Coin_Analyzer.bat", root / "Launch_Coin_Analyzer.bat")
            (root / "coin_analyzer_startup.py").write_text(
                "import sys\nfrom pathlib import Path\n"
                "print('ADJACENT_VENV' if Path(sys.prefix).name == '.venv' else 'WRONG_RUNTIME')\n"
                "sys.exit(7)\n", encoding="utf-8")
            result = subprocess.run(
                [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", str(root / "Launch_Coin_Analyzer.bat")],
                input="\n", capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
            self.assertIn("ADJACENT_VENV", result.stdout)
            self.assertNotIn("WRONG_RUNTIME", result.stdout)


if __name__ == "__main__":
    unittest.main()
