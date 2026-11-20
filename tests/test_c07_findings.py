"""Offline synthetic controls; these do not qualify C07-P1 or approve E."""

import unittest
from copy import deepcopy

from tools.c07_findings import ReconciliationError, reconcile


def finding(**changes):
    item = {
        "rule": "synthetic-rule",
        "path": "synthetic/fixture.txt",
        "commit": "a" * 40,
        "start_line": 7,
        "end_line": 7,
        "start_column": 3,
        "end_column": 12,
        "value": "INERT-FIXTURE",
    }
    item.update(changes)
    return item


def fixture(baseline=None, exceptions=None, candidate=None):
    baseline = [finding(), finding(value="INERT-CONTROL")] if baseline is None else baseline
    exceptions = [finding()] if exceptions is None else exceptions
    candidate = [finding(value="INERT-CONTROL")] if candidate is None else candidate
    case = {
        "case_id": "synthetic-case",
        "snapshot_sha256": "b" * 64,
        "baseline_execution_id": "synthetic-B",
        "candidate_execution_id": "synthetic-C",
        "expected_baseline": deepcopy(baseline),
        "exceptions": deepcopy(exceptions),
    }

    def report(execution_id, findings):
        return {
            "execution_id": execution_id,
            "status": "completed",
            "started_at": "2026-11-06T12:00:00Z",
            "finished_at": "2026-11-06T12:00:01Z",
            "exit_code": 2 if findings else 0,
            "findings": deepcopy(findings),
        }

    plan = {
        "schema": "c07-findings-v1",
        "criterion_sha256": "B85ACAB6B686F63665947E546F54C1586D5DEE4BCCCD405CA6A53B03D61B14D8",
        "cases": [case],
    }
    reports = [{
        "case_id": "synthetic-case",
        "snapshot_sha256": "b" * 64,
        "baseline": report("synthetic-B", baseline),
        "candidate": report("synthetic-C", candidate),
    }]
    return plan, reports


class ReconciliationTests(unittest.TestCase):
    def test_valid_differential(self):
        result = reconcile(*fixture())
        self.assertEqual((result.cases, result.baseline, result.candidate, result.suppressed),
                         (1, 2, 1, 1))

    def test_clean_scan_positive_control(self):
        result = reconcile(*fixture([], [], []))
        self.assertEqual((result.cases, result.baseline, result.candidate, result.suppressed),
                         (1, 0, 0, 0))

    def test_all_approved_occurrences_can_be_removed(self):
        result = reconcile(*fixture([finding()], [finding()], []))
        self.assertEqual((result.baseline, result.candidate, result.suppressed), (1, 0, 1))

    def test_no_exception_preserves_findings(self):
        result = reconcile(*fixture([finding()], [], [finding()]))
        self.assertEqual(result.suppressed, 0)

    def test_multiplicity_and_order_are_preserved(self):
        a, b = finding(), finding(value="INERT-CONTROL")
        result = reconcile(*fixture([a, a, b], [a], [b, a]))
        self.assertEqual((result.baseline, result.candidate, result.suppressed), (3, 2, 1))

    def test_separator_only_normalization(self):
        plan, reports = fixture()
        for lane in ("baseline", "candidate"):
            for item in reports[0][lane]["findings"]:
                item["path"] = "synthetic\\fixture.txt"
        self.assertEqual(reconcile(plan, reports).cases, 1)

    def test_columns_can_be_independently_absent(self):
        for absent in (("start_column",), ("end_column",), ("start_column", "end_column")):
            with self.subTest(absent=absent):
                a = finding()
                for key in absent:
                    del a[key]
                self.assertEqual(reconcile(*fixture([a], [], [a])).candidate, 1)

    def test_multiline_columns_are_not_compared_as_single_line_range(self):
        a = finding(end_line=8, start_column=20, end_column=2)
        self.assertEqual(reconcile(*fixture([a], [], [a])).candidate, 1)

    def test_each_identity_component_prevents_substitution_in_either_lane(self):
        changes = {
            "rule": "other-rule", "path": "synthetic/other.txt", "commit": "c" * 40,
            "start_line": 6, "end_line": 8, "start_column": 2, "end_column": 13,
            "value": "INERT-REPLACEMENT",
        }
        for lane in ("baseline", "candidate"):
            for field, replacement in changes.items():
                with self.subTest(lane=lane, field=field):
                    plan, reports = fixture()
                    reports[0][lane]["findings"][-1][field] = replacement
                    with self.assertRaises(ReconciliationError):
                        reconcile(plan, reports)

    def test_extra_missing_duplicate_and_wrong_suppression_rejected(self):
        a, b = finding(), finding(value="INERT-CONTROL")
        for candidate in ([], [a], [a, b], [b, b], [b, finding(value="INERT-EXTRA")]):
            with self.subTest(candidate=candidate), self.assertRaises(ReconciliationError):
                reconcile(*fixture(candidate=candidate))

    def test_duplicate_lost_baseline_with_unchanged_count_rejected(self):
        plan, reports = fixture()
        reports[0]["baseline"]["findings"] = [finding(), finding()]
        with self.assertRaises(ReconciliationError):
            reconcile(plan, reports)

    def test_baseline_must_match_predeclared_expectation(self):
        for findings in ([], [finding()], [finding(), finding(), finding(value="INERT-CONTROL")]):
            with self.subTest(findings=findings):
                plan, reports = fixture()
                reports[0]["baseline"]["findings"] = findings
                reports[0]["baseline"]["exit_code"] = 2 if findings else 0
                with self.assertRaises(ReconciliationError):
                    reconcile(plan, reports)

    def test_missing_inapplicable_and_excess_exception_occurrences_rejected(self):
        for exceptions in ([finding(value="INERT-ABSENT")], [finding(), finding()],
                           [finding(rule="other-rule")], [finding(path="other.txt")],
                           [finding(commit="d" * 40)]):
            with self.subTest(exceptions=exceptions), self.assertRaises(ReconciliationError):
                reconcile(*fixture(exceptions=exceptions))
        with self.assertRaises(ReconciliationError):
            reconcile(*fixture([], [finding()], []))

    def test_column_presence_is_identity(self):
        for lane in ("baseline", "candidate"):
            for field in ("start_column", "end_column"):
                with self.subTest(lane=lane, field=field):
                    plan, reports = fixture()
                    del reports[0][lane]["findings"][-1][field]
                    with self.assertRaises(ReconciliationError):
                        reconcile(plan, reports)

    def test_path_normalization_never_widens_scope(self):
        for path in ("Synthetic/fixture.txt", "synthetic/fixture.txt.bak", "nested/synthetic/fixture.txt"):
            with self.subTest(path=path):
                plan, reports = fixture()
                reports[0]["candidate"]["findings"][0]["path"] = path
                with self.assertRaises(ReconciliationError):
                    reconcile(plan, reports)

    def test_invalid_paths_fail_closed(self):
        for path in ("/absolute", "C:\\absolute", "../escape", "a/../b", "./a", "a//b",
                     "a/", "\\\\server\\share", "", "a/./b", "a\x00b"):
            with self.subTest(path=path):
                a = finding(path=path)
                with self.assertRaises(ReconciliationError):
                    reconcile(*fixture([a], [], [a]))

    def test_missing_identity_fields_not_invented(self):
        for field in ("rule", "path", "commit", "start_line", "end_line", "value"):
            with self.subTest(field=field):
                a = finding()
                del a[field]
                with self.assertRaises(ReconciliationError):
                    reconcile(*fixture([a], [], [a]))

    def test_malformed_findings_not_discarded_in_any_input(self):
        malformed = [None, {}, "finding", [], finding(start_line=True), finding(start_line=0),
                     finding(end_line=6), finding(start_column=None), finding(end_column=0),
                     finding(start_column=13, end_column=12), finding(rule=""),
                     finding(commit=None), finding(value=""), finding(unknown="ignored?")]
        for item in malformed:
            for location in ("expected_baseline", "exceptions", "baseline", "candidate"):
                with self.subTest(item=item, location=location):
                    plan, reports = fixture()
                    if location in ("expected_baseline", "exceptions"):
                        plan["cases"][0][location].append(item)
                    else:
                        reports[0][location]["findings"].append(item)
                    with self.assertRaises(ReconciliationError):
                        reconcile(plan, reports)

    def test_stale_case_snapshot_and_execution_bindings_rejected(self):
        for field, value in (("case_id", "other-case"), ("snapshot_sha256", "c" * 64)):
            with self.subTest(field=field):
                plan, reports = fixture()
                reports[0][field] = value
                with self.assertRaises(ReconciliationError):
                    reconcile(plan, reports)
        for lane in ("baseline", "candidate"):
            plan, reports = fixture()
            reports[0][lane]["execution_id"] = "stale-execution"
            with self.assertRaises(ReconciliationError):
                reconcile(plan, reports)

    def test_missing_skipped_extra_and_duplicate_cases_rejected(self):
        plan, reports = fixture()
        for observed in ([], reports + reports, None, {}, [None]):
            with self.subTest(observed=observed), self.assertRaises(ReconciliationError):
                reconcile(plan, observed)
        extra = deepcopy(reports[0])
        extra["case_id"] = "unexpected-case"
        with self.assertRaises(ReconciliationError):
            reconcile(plan, reports + [extra])

    def test_missing_execution_evidence_and_noncompletion_rejected(self):
        for lane in ("baseline", "candidate"):
            for field in ("execution_id", "status", "started_at", "finished_at", "exit_code", "findings"):
                with self.subTest(lane=lane, missing=field):
                    plan, reports = fixture()
                    del reports[0][lane][field]
                    with self.assertRaises(ReconciliationError):
                        reconcile(plan, reports)
            for status in ("skipped", "timeout", "cancelled", "crashed", "failed", "running", None):
                with self.subTest(lane=lane, status=status):
                    plan, reports = fixture()
                    reports[0][lane]["status"] = status
                    with self.assertRaises(ReconciliationError):
                        reconcile(plan, reports)

    def test_exit_codes_must_correspond_to_findings(self):
        for lane in ("baseline", "candidate"):
            for code in (0, 1, 3, -1, True, "2", None):
                with self.subTest(lane=lane, code=code):
                    plan, reports = fixture()
                    reports[0][lane]["exit_code"] = code
                    with self.assertRaises(ReconciliationError):
                        reconcile(plan, reports)
        plan, reports = fixture([], [], [])
        reports[0]["candidate"]["exit_code"] = 2
        with self.assertRaises(ReconciliationError):
            reconcile(plan, reports)

    def test_invalid_and_reversed_execution_timestamps_rejected(self):
        for changes in ({"started_at": ""}, {"finished_at": "yesterday"},
                        {"started_at": "2026-11-06T12:00:02Z"},
                        {"finished_at": "2026-02-30T12:00:01Z"},
                        {"started_at": "2026-11-06T12:00:00+00:00"}):
            with self.subTest(changes=changes):
                plan, reports = fixture()
                reports[0]["baseline"].update(changes)
                with self.assertRaises(ReconciliationError):
                    reconcile(plan, reports)

    def test_plan_cannot_be_empty_malformed_or_bound_to_other_criterion(self):
        plan, reports = fixture()
        for changes in ({"cases": []}, {"cases": None}, {"schema": "other"},
                        {"criterion_sha256": "0" * 64}, {"extra": "unknown"}):
            with self.subTest(changes=changes):
                altered = deepcopy(plan)
                altered.update(changes)
                with self.assertRaises(ReconciliationError):
                    reconcile(altered, reports)
        for field in plan:
            altered = deepcopy(plan)
            del altered[field]
            with self.assertRaises(ReconciliationError):
                reconcile(altered, reports)

    def test_duplicate_case_or_execution_declarations_rejected(self):
        plan, reports = fixture()
        plan["cases"].append(deepcopy(plan["cases"][0]))
        with self.assertRaises(ReconciliationError):
            reconcile(plan, reports)
        plan, reports = fixture()
        plan["cases"][0]["candidate_execution_id"] = "synthetic-B"
        with self.assertRaises(ReconciliationError):
            reconcile(plan, reports)

    def test_multiple_cases_are_required_and_report_order_is_irrelevant(self):
        plan, reports = fixture()
        clean_plan, clean_reports = fixture([], [], [])
        clean_case = clean_plan["cases"][0]
        clean_case.update(case_id="clean-case", baseline_execution_id="clean-B",
                          candidate_execution_id="clean-C")
        clean_report = clean_reports[0]
        clean_report["case_id"] = "clean-case"
        clean_report["baseline"]["execution_id"] = "clean-B"
        clean_report["candidate"]["execution_id"] = "clean-C"
        plan["cases"].append(clean_case)
        reports.append(clean_report)
        expected = reconcile(plan, reports)
        self.assertEqual((expected.cases, expected.baseline, expected.candidate, expected.suppressed),
                         (2, 2, 1, 1))
        self.assertEqual(reconcile(plan, list(reversed(reports))), expected)
        with self.assertRaises(ReconciliationError):
            reconcile(plan, reports[:1])

    def test_input_objects_remain_unchanged(self):
        plan, reports = fixture()
        before = deepcopy((plan, reports))
        reconcile(plan, reports)
        self.assertEqual((plan, reports), before)

    def test_diagnostics_do_not_disclose_values(self):
        plan, reports = fixture()
        reports[0]["candidate"]["findings"][0]["value"] = "INERT-PRIVATE-MARKER"
        with self.assertRaises(ReconciliationError) as raised:
            reconcile(plan, reports)
        self.assertNotIn("INERT-PRIVATE-MARKER", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
