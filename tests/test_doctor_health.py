"""Synthetic health checks: no live records, locks, images, or services."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import doctor_health as health
from runtime_readiness import Status, evaluate_readiness


def runtime():
    return evaluate_readiness(importer=lambda _: object(), which=lambda _: None,
                              environ={}, version=(3, 12))


class DoctorHealthTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "collection.json"

    def write(self, rows):
        self.path.write_text(json.dumps(rows), encoding="utf-8")

    def test_missing_and_valid_collection_without_instantiating_collection(self):
        check, items = health.inspect_collection(self.path)
        self.assertEqual(check.status, Status.READY)
        self.assertIn("first-run", check.message)
        self.assertFalse(self.path.exists())
        nested = self.root / "absent" / "collection.json"
        self.assertEqual(health.inspect_collection(nested)[0].status, Status.READY)
        self.assertFalse(nested.parent.exists())
        self.write([{"id": "synthetic", "notes": "private-sentinel"}])
        before = self.path.read_bytes()
        with patch("coin_collection.CoinCollection", side_effect=AssertionError("must not construct")):
            check, items = health.inspect_collection(self.path)
        self.assertEqual(check.status, Status.READY)
        self.assertEqual(len(items), 1)
        self.assertNotIn("private-sentinel", repr(check))
        self.assertEqual(self.path.read_bytes(), before)

    def test_malformed_and_wrong_structure_are_unavailable(self):
        for raw in (b"{", b"{}", b"[1]", b"\xff"):
            with self.subTest(raw=raw):
                self.path.write_bytes(raw)
                self.assertEqual(health.inspect_collection(self.path)[0].status, Status.UNAVAILABLE)
                self.assertEqual(self.path.read_bytes(), raw)

    def test_changed_bytes_are_unverified(self):
        self.write([])
        capture = health.capture_collection_baseline
        count = 0
        def changed(path):
            nonlocal count
            count += 1
            if count == 2:
                path.write_bytes(b"[{}]")
            return capture(path)
        with patch.object(health, "capture_collection_baseline", side_effect=changed):
            self.assertEqual(health.inspect_collection(self.path)[0].status, Status.UNVERIFIED)

    def test_image_presence_and_containment(self):
        images = self.root / "images"
        images.mkdir()
        (images / "image.jpg").write_bytes(b"not decoded")
        for reference, expected in (("image.jpg", Status.READY),
                                    ("coin_photos/collection/image.jpg", Status.READY),
                                    ("../image.jpg", Status.UNAVAILABLE),
                                    (str(images / "image.jpg"), Status.UNAVAILABLE),
                                    ("missing.jpg", Status.UNAVAILABLE)):
            with self.subTest(reference=reference):
                self.write([{"id": "test", "image_path": reference}])
                _, items = health.inspect_collection(self.path)
                self.assertEqual(health.inspect_images(images, items).status, expected)
        self.assertEqual((images / "image.jpg").read_bytes(), b"not decoded")

    def test_symlink_files_and_directories_are_rejected(self):
        target = self.root / "target"
        target.mkdir()
        (target / "real.json").write_bytes(b"[]")
        link = self.root / "linked.json"
        try:
            link.symlink_to(target / "real.json")
            (self.root / "linked-dir").symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest("Symlink creation unavailable on this host")
        self.assertEqual(health.inspect_collection(link)[0].status, Status.UNAVAILABLE)
        self.assertEqual(health.inspect_collection(self.root / "linked-dir" / "real.json")[0].status, Status.UNAVAILABLE)
        self.write([{"image_path": "linked.json"}])
        _, items = health.inspect_collection(self.path)
        self.assertEqual(health.inspect_images(self.root, items).status, Status.UNAVAILABLE)

    def test_existing_live_lock_is_preserved(self):
        self.write([])
        imports = self.root / "imports"
        imports.mkdir()
        lock = imports / "package_import.lock"
        lock.write_bytes(b"private-lock-sentinel")
        with patch("capture_import.lock.PackageImportLock.acquire", side_effect=AssertionError()):
            check = health.inspect_lock(self.path)
        self.assertEqual(check.status, Status.UNVERIFIED)
        self.assertEqual(lock.read_bytes(), b"private-lock-sentinel")

    def test_disposable_probe_succeeds_and_preserves_existing_files(self):
        self.path.write_bytes(b"live-sentinel")
        lock = self.root / "package_import.lock"
        lock.write_bytes(b"live-lock")
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        check = health.probe_directory(self.root)
        self.assertEqual(check.status, Status.READY, check)
        self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir()}, before)

    def test_probe_write_failure_cleans_owned_directory(self):
        with patch("atomic_json.write_json_atomically", side_effect=OSError("private-sentinel")):
            check = health.probe_directory(self.root)
        self.assertEqual(check.status, Status.UNAVAILABLE)
        self.assertNotIn("private-sentinel", repr(check))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_probe_cleanup_failure_is_reported_without_recursive_deletion(self):
        with patch.object(Path, "rmdir", side_effect=OSError("private-sentinel")):
            check = health.probe_directory(self.root)
        self.assertEqual(check.status, Status.UNAVAILABLE)
        self.assertIn("cleanup", check.message)
        self.assertNotIn("private-sentinel", repr(check))
        leftovers = list(self.root.iterdir())
        self.assertEqual(len(leftovers), 1)
        self.assertEqual(list(leftovers[0].iterdir()), [])

    def test_ocr_bounded_runner_success_timeout_and_output_limit(self):
        code, output = health.run_bounded([sys.executable, "-c", "print('synthetic')"])
        self.assertEqual((code, output.strip()), (0, b"synthetic"))
        with patch.object(health, "OCR_TIMEOUT", 0.1):
            with self.assertRaises(TimeoutError):
                health.run_bounded([sys.executable, "-c", "import time; time.sleep(3)"])
        with self.assertRaises(TimeoutError):
            health.run_bounded([sys.executable, "-c", "print('x' * 70000)"])

    def test_ocr_outcomes_never_emit_raw_output(self):
        report = Mock()
        report.status_for.return_value = Status.UNVERIFIED
        module = SimpleNamespace(pytesseract=SimpleNamespace(tesseract_cmd="synthetic"))
        scenarios = (
            ([ (0, b"tesseract 5\n"), (0, b"List of available languages (1):\neng\n") ], Status.READY),
            ([ (0, b"tesseract 5\n"), (0, b"fra\n") ], Status.UNAVAILABLE),
            ([ (1, b"private-sentinel") ], Status.UNVERIFIED),
            ([ (0, b"tesseract 5\n"), (1, b"private-sentinel") ], Status.UNVERIFIED),
            (TimeoutError("private-sentinel"), Status.UNVERIFIED),
            (FileNotFoundError("private-sentinel"), Status.UNAVAILABLE),
        )
        with patch.dict(sys.modules, {"pytesseract": module}):
            for outcomes, expected in scenarios:
                with self.subTest(expected=expected, outcomes=outcomes):
                    check = health.inspect_ocr(report, runner=Mock(side_effect=outcomes))
                    self.assertEqual(check.status, expected)
                    self.assertNotIn("private-sentinel", repr(check))

    def test_default_health_never_inspects_storage_or_writes(self):
        with patch.object(health, "inspect_collection", side_effect=AssertionError()), patch.object(
            health, "probe_directory", side_effect=AssertionError()
        ), patch.object(health, "inspect_lock", side_effect=AssertionError()):
            checks = health.evaluate_health(runtime())
        self.assertTrue(all(c.status == Status.UNVERIFIED for c in checks[:4]))


if __name__ == "__main__":
    unittest.main()
