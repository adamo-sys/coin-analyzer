"""Doctor output/exit contracts, independent of installed optional services."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import unittest
from unittest.mock import Mock

from coin_analyzer_doctor import main
from doctor_health import result
from runtime_readiness import Status, evaluate_readiness


def report():
    return evaluate_readiness(importer=lambda _: object(), which=lambda _: None,
                              environ={}, version=(3, 12))


class DoctorCLITests(unittest.TestCase):
    def invoke(self, arguments=(), checks=(), readiness=report):
        output = StringIO()
        code = main(arguments, readiness=readiness, health=lambda *a, **kw: checks, output=output)
        return code, output.getvalue()

    def test_human_output_labels_optional_and_stable_ids(self):
        code, text = self.invoke()
        self.assertEqual(code, 0)
        self.assertIn("DEGRADED", text)
        self.assertIn("AI (optional): unavailable", text)
        self.assertIn("core.python", text)

    def test_json_schema_order_purity_and_repeatability(self):
        first = self.invoke(["--json"])
        self.assertEqual(first, self.invoke(["--json"]))
        payload = json.loads(first[1])
        self.assertEqual(list(payload), ["schema_version", "overall", "capabilities", "checks"])
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(list(payload["capabilities"]), ["core", "ocr", "ai"])
        self.assertEqual(list(payload["checks"][0]), ["check_id", "capability", "status", "message", "action"])
        self.assertEqual(payload["checks"][0]["check_id"], "core.python")
        stdout = StringIO()
        def noisy(*a, **kw):
            print("synthetic helper output")
            return ()
        with redirect_stdout(stdout):
            self.assertEqual(main(["--json"], readiness=report, health=noisy), 0)
        self.assertNotIn("synthetic helper output", stdout.getvalue())
        json.loads(stdout.getvalue())

    def test_selected_checks_determine_exit_code_and_paths_are_not_rendered(self):
        for flag, name in (("--collection", "storage.collection"),
                           ("--probe-directory", "persistence.probe")):
            for status in Status:
                with self.subTest(flag=flag, status=status):
                    code, text = self.invoke(["--json", flag, "private-path-sentinel"],
                                             (result(name, status, "Fixed safe message."),))
                    self.assertEqual(code, 0 if status == Status.READY else 1)
                    self.assertNotIn("private-path-sentinel", text)
        self.assertEqual(self.invoke(["--collection", "private-path"])[0], 1)
        self.assertEqual(self.invoke(checks=(result("ocr.health", Status.UNAVAILABLE, "Optional"),))[0], 0)

    def test_core_failure_and_internal_error_exit_one_safely(self):
        bad = lambda: evaluate_readiness(version=(3, 11))
        self.assertEqual(self.invoke(readiness=bad)[0], 1)
        code, output = self.invoke(["--json"], readiness=Mock(side_effect=ValueError("private-sentinel")))
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output)["overall"], "blocked")
        self.assertNotIn("private-sentinel", output)

    def test_argument_errors_use_stderr_without_echoing_inputs(self):
        for args in (["--unknown-private-sentinel"], ["--collection"], ["--managed-images", "private-sentinel"]):
            with self.subTest(args=args):
                out, err = StringIO(), StringIO()
                with redirect_stdout(out), redirect_stderr(err), self.assertRaises(SystemExit) as raised:
                    main(args)
                self.assertEqual(raised.exception.code, 2)
                self.assertEqual(out.getvalue(), "")
                self.assertNotIn("private-sentinel", err.getvalue())


if __name__ == "__main__":
    unittest.main()
