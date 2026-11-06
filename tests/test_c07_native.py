"""Scanner-free tests of native-driver preparation, never native receipts."""

import copy
from decimal import localcontext
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools import c07_synthetic

try:
    from tools import c07_native as driver
except ImportError:
    driver = None


class NativePreparationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(driver, "native preparation components are missing")

    def test_materializes_exact_history_and_refuses_reuse_or_changed_catalog(self):
        case = next(c for c in c07_synthetic.build_cases() if c.case_id == "P05/path-0/fixture-A-B")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            receipt = driver.materialize(case, root)
            self.assertFalse(receipt["qualified"])
            for revision in case.revisions:
                result = subprocess.run(["git", "-C", str(root), "show", revision.commit + ":" + revision.path],
                                        capture_output=True, check=True, timeout=10)
                self.assertEqual(result.stdout, revision.content)
            self.assertEqual((root / case.revisions[-1].path).read_bytes(), case.revisions[-1].content)
            self.assertFalse((root / ".git/hooks").exists())
            with self.assertRaises(ValueError):
                driver.materialize(case, root)
            from dataclasses import replace
            broken = replace(case, case_id="unknown")
            with self.assertRaises(ValueError):
                driver.materialize(broken, Path(temp) / "bad")

    def test_raw_adapter_preserves_columns_commit_separator_and_multiplicity(self):
        raw = {"RuleID": "inert", "File": "tests\\inert.py", "Commit": "a" * 40,
               "StartLine": 41, "EndLine": 41, "StartColumn": 12, "EndColumn": 22,
               "Secret": "inert-value", "Match": 'key="inert-value"'}
        records = driver.adapt_report(json.dumps([raw, raw]).encode(), allowed_values={"inert-value"})
        expected = {"rule": "inert", "path": "tests/inert.py", "commit": "a" * 40,
                    "start_line": 41, "end_line": 41, "start_column": 12, "end_column": 22,
                    "value": "inert-value"}
        self.assertEqual(records, [expected, expected])
        mutations = {"Secret": "REDACTED", "Commit": "short", "File": "../escape",
                     "StartColumn": 0, "StartLine": True, "EndColumn": 3,
                     "UnknownField": "unexpected"}
        for field, value in mutations.items():
            changed = copy.deepcopy(raw)
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError) as caught:
                driver.adapt_report(json.dumps([changed]).encode(), allowed_values={"inert-value"})
            self.assertNotIn("inert-value", str(caught.exception))
        for field in raw.keys() - {"Match"}:
            changed = dict(raw)
            del changed[field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                driver.adapt_report(json.dumps([changed]).encode(), allowed_values={"inert-value"})
        for invalid in ("prefix-inert-value-suffix", ["inert-value"], {"inert-value": True}, {""}, {True}):
            with self.subTest(allowed_values=invalid), self.assertRaises(ValueError):
                driver.adapt_report(json.dumps([raw]).encode(), allowed_values=invalid)

    def test_resource_reconciliation_never_certifies_unknown_or_overallocated_time(self):
        base = {"ceiling_seconds": "36000", "charged_seconds": "5000.25",
                "reserved_seconds": "1000", "requested_seconds": "7200",
                "accounting_reconciliation": "reviewed-ledger-sha256:" + "a" * 64,
                "unmetered_intervals": [], "counter_state": "reviewed-counters-sha256:" + "b" * 64}
        self.assertEqual(driver.check_resources(base), "22799.75")
        for field, value in (("unmetered_intervals", ["unresolved"]), ("charged_seconds", None),
                             ("requested_seconds", "31000"), ("requested_seconds", "0"),
                             ("charged_seconds", "NaN"), ("ceiling_seconds", "36001"),
                             ("charged_seconds", "35999.0000000000000000000000000001"),
                             ("accounting_reconciliation", "UNBOUND"), ("counter_state", "UNBOUND")):
            changed = dict(base)
            changed[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                driver.check_resources(changed)
        with localcontext() as context:
            context.prec = 4
            changed = dict(base, charged_seconds="35999", requested_seconds="2", reserved_seconds="0")
            with self.assertRaises(ValueError):
                driver.check_resources(changed)

    def test_manifest_is_deterministic_and_never_supplies_execution_admission(self):
        manifest = driver.preparation_manifest()
        self.assertEqual(manifest, driver.preparation_manifest())
        self.assertEqual(len(manifest["cases"]), 157)
        self.assertEqual(manifest["execution_status"], "NOT_ADMITTED")
        self.assertFalse(manifest["qualified"])
        self.assertIn("NATIVE_COLUMN_SEMANTICS", manifest["required_external_bindings"])
        self.assertIn("R2_BACKEND_AND_ALL_C12", manifest["required_external_bindings"])
        self.assertEqual(manifest["criterion_sha256"], "B85ACAB6B686F63665947E546F54C1586D5DEE4BCCCD405CA6A53B03D61B14D8")
        self.assertTrue(all(len(c["snapshot_sha256"]) == 64 for c in manifest["cases"]))
        self.assertEqual(manifest["manifest_sha256"], hashlib.sha256(json.dumps(
            {k: v for k, v in manifest.items() if k != "manifest_sha256"},
            sort_keys=True, separators=(",", ":")).encode()).hexdigest())

    def test_manifest_binds_actual_source_bytes_and_distinguishes_missing_native_backend(self):
        manifest = driver.preparation_manifest()
        sources = {row["path"]: row for row in manifest["source_package"]}
        for name in ("tools/c07_capture.py", "tools/c07_backend.py", "tools/c07_faults.py"):
            raw = (Path(__file__).resolve().parents[1] / name).read_bytes()
            self.assertEqual(sources[name]["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(sources[name]["bytes"], len(raw))
        self.assertEqual(sources["tools/c07_capture.py"]["lf_canonical_sha256"],
                         "13da006f18d8ea5ace45821554dadc88b0e7eaf234f338dc37292d7f441dcecf")
        self.assertEqual(manifest["fault_driver_counts"], {"CLEAN": 1, "P11": 10, "P12": 34, "P14": 13})
        self.assertEqual(manifest["native_backend"], "UNIMPLEMENTED_UNQUALIFIED")
        self.assertIn("NATIVE_PROCESS_AND_FILESYSTEM_BACKEND", manifest["required_external_bindings"])

    def test_retained_source_identity_explicitly_normalizes_checkout_line_endings(self):
        raw = (Path(__file__).resolve().parents[1] / "tools/c07_capture.py").read_bytes().replace(b"\r\n", b"\n")
        lf = driver.capture_source_identity(raw)
        crlf = driver.capture_source_identity(raw.replace(b"\n", b"\r\n"))
        self.assertEqual(lf["lf_canonical_sha256"], crlf["lf_canonical_sha256"])
        self.assertNotEqual(lf["sha256"], crlf["sha256"])
        self.assertEqual(lf["lf_canonical_bytes"], 24464)
        with self.assertRaises(ValueError):
            driver.capture_source_identity(raw + b"# changed source\n")

    def test_resource_bytes_must_match_review_references_without_claiming_provenance(self):
        ledger, counters = b"inert reviewed ledger bytes", b"inert counter record"
        accounting = {"ceiling_seconds": "36000", "charged_seconds": "5000.25",
                      "reserved_seconds": "1000", "requested_seconds": "7200",
                      "accounting_reconciliation": "reviewed-ledger-sha256:" + hashlib.sha256(ledger).hexdigest(),
                      "unmetered_intervals": [],
                      "counter_state": "reviewed-counters-sha256:" + hashlib.sha256(counters).hexdigest()}
        result = driver.check_resource_evidence(accounting, ledger=ledger, counters=counters)
        self.assertEqual(result["arithmetic_remainder_seconds"], "22799.75")
        self.assertEqual(result["provenance"], "NOT_AUTHENTICATED")
        self.assertEqual(result["execution_status"], "NOT_ADMITTED")
        with self.assertRaises(ValueError):
            driver.check_resource_evidence(accounting, ledger=ledger + b"x", counters=counters)
        with self.assertRaises(ValueError):
            driver.check_resource_evidence(accounting, ledger=ledger, counters=b"")


if __name__ == "__main__":
    unittest.main()
