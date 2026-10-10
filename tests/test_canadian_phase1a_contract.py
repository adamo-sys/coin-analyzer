"""Synthetic-only adversarial tests for the offline Phase 1A foundation."""

import copy
import importlib
import json
from pathlib import Path
import unittest


def review():
    return {"state": "APPROVED", "author": "synthetic-author", "reviewer": "synthetic-reviewer",
            "reviewed_at": "2026-10-10T12:00:00Z", "review_ref": "synthetic-review-only"}


def source():
    return {"source_id": "synthetic-source", "kind": "SYNTHETIC", "title": "SYNTHETIC ONLY",
            "locator": "synthetic://contract-test", "edition": "synthetic-v1",
            "content_sha256": "1" * 64, "licence": "synthetic-test-only",
            "attribution": "Generated synthetic contract fixture; no real-world evidence",
            "retrieved_at": "2026-10-10T12:00:00Z", "permission": "LOCAL_METADATA",
            "review": review()}


def ref(field):
    return {"field": field, "source_id": "synthetic-source", "source_record": "synthetic-row",
            "locator": "synthetic-section"}


def metadata():
    fields = ("denomination", "monarch", "years", "obverse_design", "reverse_design", "disposition")
    return {"schema_version": "ca-phase1a-metadata-v1", "policy_version": "ca-phase1a-policy-v1",
            "normalization_version": "ca-phase1a-normalization-v1", "classification": "SYNTHETIC",
            "sources": [source()], "issues": [{"issue_id": "synthetic-issue", "denomination": "25c",
                "monarch": "ELIZABETH_II", "year_start": 2000, "year_end": 2001,
                "obverse_design": "synthetic portrait", "reverse_design": "synthetic alternate",
                "disposition": "ALTERNATE", "unsupported": False, "review": review(),
                "source_refs": [ref(f) for f in fields]}],
            "coverage": [{"denomination": "25c", "monarch": "ELIZABETH_II", "disposition": "ALTERNATE",
                "year_start": 2000, "year_end": 2001, "state": "COVERED",
                "issue_ids": ["synthetic-issue"], "rationale": "Synthetic coverage only"}]}


def evidence(eid="synthetic-date", value="2000", side="REVERSE", origin="DIRECT"):
    return {"evidence_id": eid, "side": side, "origin": origin, "value": value}


def benchmark():
    return {"schema_version": "ca-phase1a-benchmark-v1", "policy_version": "ca-phase1a-policy-v1",
            "normalization_version": "ca-phase1a-normalization-v1", "classification": "SYNTHETIC",
            "sources": [source()], "policy": {"evaluation_split": "HOLDOUT", "review": review(),
                "thresholds": [{"field": "year", "min_truth": 1, "min_supported": 1,
                                "min_precision": 1.0, "min_coverage": 1.0}]},
            "freeze": {"manifest_sha256": "0" * 64, "metadata_sha256": "0" * 64,
                       "policy_sha256": "0" * 64, "producer_ref": "synthetic-recorded-producer-v1"},
            "cases": [{"case_id": "synthetic-case", "coin_group_id": "synthetic-coin",
                "capture_group_id": "synthetic-capture", "split": "HOLDOUT",
                "input_ref": "synthetic/no-image.json", "input_sha256": "2" * 64,
                "privacy": "SYNTHETIC", "issue_ids": ["synthetic-issue"],
                "design_disposition": "ALTERNATE", "fields": [{"field": "year",
                    "expected_state": "SUPPORTED", "truth": {"state": "VERIFIED", "value": "2000",
                        "review": review(), "source_refs": [ref("year")]},
                    "required_evidence": [evidence()]}]}]}


def outcomes():
    return {"schema_version": "ca-phase1a-outcomes-v1", "producer_ref": "synthetic-recorded-producer-v1",
            "manifest_sha256": "0" * 64, "cases": [{"case_id": "synthetic-case", "execution": "SUCCESS",
                "fields": [{"field": "year", "state": "SUPPORTED", "value": "2000",
                            "candidate_ids": ["synthetic-issue"], "evidence": [evidence()]}]}]}


def sealed(contract, meta=None, bench=None, recorded=None):
    meta = metadata() if meta is None else meta
    bench = benchmark() if bench is None else bench
    recorded = outcomes() if recorded is None else recorded
    bench["freeze"]["metadata_sha256"] = contract.canonical_digest(meta)
    bench["freeze"]["policy_sha256"] = contract.canonical_digest(bench["policy"])
    bench["freeze"]["manifest_sha256"] = contract.benchmark_digest(bench)
    recorded["manifest_sha256"] = bench["freeze"]["manifest_sha256"]
    return meta, bench, recorded


class FoundationImportTests(unittest.TestCase):
    def test_offline_foundation_exposes_validation_and_recorded_scoring(self):
        try:
            contract = importlib.import_module("capture_import.canadian_phase1a_contract")
        except ModuleNotFoundError:
            self.fail("the authorized offline contract foundation is absent")
        self.assertTrue(callable(contract.validate_metadata))
        self.assertTrue(callable(contract.validate_benchmark))
        self.assertTrue(callable(contract.score_recorded_outcomes))


class OfflineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = importlib.import_module("capture_import.canadian_phase1a_contract")

    def score(self, meta=None, bench=None, recorded=None):
        return self.contract.score_recorded_outcomes(*sealed(self.contract, meta, bench, recorded))

    def codes(self, report):
        return {item.code for item in report.diagnostics}

    def test_synthetic_contracts_are_valid_but_never_real_ready(self):
        meta, bench, _ = sealed(self.contract)
        for report in (self.contract.validate_metadata(meta), self.contract.validate_benchmark(meta, bench)):
            self.assertTrue(report.valid)
            self.assertFalse(report.ready)
            self.assertIn("SYNTHETIC_NOT_REAL_EVIDENCE", self.codes(report))
        result = self.score()
        self.assertEqual(result.fields[0].precision, 1.0)
        self.assertEqual(result.fields[0].coverage, 1.0)
        self.assertFalse(result.evaluation_pass)
        self.assertTrue(result.synthetic)

    def test_normalization_is_stable_order_independent_and_preserves_duplicates(self):
        a = {"z": [" b ", "a", "a"], "x": "e\u0301"}
        self.assertEqual(self.contract.normalize_document(a), {"x": "é", "z": ["a", "a", "b"]})
        self.assertEqual(self.contract.canonical_digest(a), self.contract.canonical_digest({"x": "é", "z": ["a", "b", "a"]}))
        self.assertEqual(self.score(), self.score())
        b = benchmark()
        b["cases"][0]["fields"][0]["required_evidence"].reverse()
        self.assertEqual(self.score(), self.score(bench=b))

    def test_missing_provenance_pending_review_self_review_and_unknown_versions_block(self):
        for mutation in ("refs", "pending", "self", "schema", "policy", "normalization", "unknown", "retrieved", "license"):
            with self.subTest(mutation=mutation):
                m = metadata()
                if mutation == "refs":
                    m["issues"][0]["source_refs"] = []
                elif mutation == "pending":
                    m["sources"][0]["review"]["state"] = "PENDING"
                elif mutation == "self":
                    m["issues"][0]["review"]["reviewer"] = "synthetic-author"
                elif mutation in ("schema", "policy", "normalization"):
                    m[mutation + "_version"] = "unknown"
                elif mutation == "unknown":
                    m["accept_identity"] = True
                elif mutation == "retrieved":
                    m["sources"][0]["retrieved_at"] = "not-a-date"
                else:
                    m["sources"][0]["licence"] = ""
                report = self.contract.validate_metadata(m)
                self.assertFalse(report.valid)
                self.assertFalse(report.ready)

    def test_synthetic_cannot_be_relabelled_as_real(self):
        m, b, _ = sealed(self.contract)
        m["classification"] = "REAL_METADATA"
        b["classification"] = "REAL_HOLDOUT"
        self.assertFalse(self.contract.validate_metadata(m).valid)
        self.assertFalse(self.contract.validate_benchmark(m, b).ready)

    def test_unsupported_historical_combinations_and_coverage_lies_block(self):
        for denomination, monarch, start, end in (("1c", "CHARLES_III", 2023, 2023),
                ("$1", "ELIZABETH_II", 1986, 1987), ("$2", "ELIZABETH_II", 1995, 1996),
                ("1c", "ELIZABETH_II", 2012, 2013), ("25c", "CHARLES_III", 2022, 2023)):
            m = metadata()
            m["issues"][0].update(denomination=denomination, monarch=monarch, year_start=start, year_end=end)
            self.assertFalse(self.contract.validate_metadata(m).valid)
        m = metadata()
        m["coverage"][0]["year_end"] = 2002
        self.assertIn("COVERAGE_MISMATCH", self.codes(self.contract.validate_metadata(m)))

    def test_split_leakage_and_changed_or_missing_freezes_block(self):
        for key in ("coin_group_id", "capture_group_id", "input_ref", "input_sha256"):
            b = benchmark()
            other = copy.deepcopy(b["cases"][0])
            other.update(case_id="synthetic-other", split="DEVELOPMENT", coin_group_id="other-coin",
                         capture_group_id="other-capture", input_ref="synthetic/other.json", input_sha256="3" * 64)
            other[key] = b["cases"][0][key]
            b["cases"].append(other)
            m, b, _ = sealed(self.contract, bench=b)
            self.assertIn("SPLIT_LEAKAGE", self.codes(self.contract.validate_benchmark(m, b)))
        m, b, _ = sealed(self.contract)
        b["cases"][0]["input_ref"] = "synthetic/changed.json"
        self.assertIn("FREEZE_MISMATCH", self.codes(self.contract.validate_benchmark(m, b)))
        b["freeze"]["metadata_sha256"] = ""
        self.assertFalse(self.contract.validate_benchmark(m, b).valid)

    def test_unreviewed_truth_and_empty_denominators_are_unscorable(self):
        b = benchmark()
        b["cases"][0]["fields"][0]["truth"]["state"] = "UNVERIFIED"
        result = self.score(bench=b)
        self.assertEqual(result.fields[0].truth_count, 0)
        self.assertIsNone(result.fields[0].precision)
        self.assertIsNone(result.fields[0].coverage)
        self.assertFalse(result.fields[0].gate_pass)
        self.assertFalse(result.evaluation_pass)
        self.assertIn("UNSCORABLE_TRUTH", self.codes(result))

    def test_metadata_partial_range_conflicting_and_non_ascii_dates_are_unsafe_support(self):
        for ev in ([evidence(origin="CANDIDATE_METADATA", side="NONE")],
                   [evidence(value="200?")], [evidence(value="2000-2001")],
                   [evidence(), evidence("other", "2001", "OBVERSE")],
                   [evidence(value="２０００")], []):
            with self.subTest(evidence=ev):
                out = outcomes()
                out["cases"][0]["fields"][0]["evidence"] = ev
                result = self.score(recorded=out)
                self.assertEqual(result.false_supported_years, 1)
                self.assertEqual(result.fields[0].correct_supported, 0)
                self.assertFalse(result.fields[0].gate_pass)

    def test_wrong_side_unresolved_and_alternate_to_standard_design_support_block(self):
        b = benchmark()
        b["policy"]["thresholds"][0]["field"] = "reverse_design"
        f = b["cases"][0]["fields"][0]
        f.update(field="reverse_design", required_evidence=[evidence(value="synthetic alternate")])
        f["truth"].update(value="synthetic alternate", source_refs=[ref("reverse_design")])
        for side, candidates, value in (("OBVERSE", ["synthetic-issue"], "synthetic alternate"),
                ("REVERSE", ["synthetic-issue", "unresolved"], "synthetic alternate"),
                ("REVERSE", ["synthetic-issue"], "synthetic standard")):
            out = outcomes()
            out["cases"][0]["fields"][0].update(field="reverse_design", value=value,
                candidate_ids=candidates, evidence=[evidence(value=value, side=side)])
            result = self.score(bench=copy.deepcopy(b), recorded=out)
            self.assertEqual(result.fields[0].correct_supported, 0)
            self.assertFalse(result.evaluation_pass)

    def test_conflict_evidence_is_retained_and_loss_is_counted(self):
        b = benchmark()
        f = b["cases"][0]["fields"][0]
        ev = [evidence(), evidence("synthetic-other-date", "2001", "OBVERSE")]
        f.update(expected_state="CONFLICTING", required_evidence=ev)
        f["truth"]["value"] = None
        out = outcomes()
        out["cases"][0]["fields"][0].update(state="CONFLICTING", value=None, evidence=ev)
        good = self.score(bench=copy.deepcopy(b), recorded=copy.deepcopy(out))
        self.assertEqual(good.conflict_evidence_loss, 0)
        self.assertEqual(len(good.recorded_outcomes["cases"][0]["fields"][0]["evidence"]), 2)
        out["cases"][0]["fields"][0]["evidence"] = ev[:1]
        bad = self.score(bench=b, recorded=out)
        self.assertEqual(bad.conflict_evidence_loss, 1)
        self.assertEqual(bad.fields[0].correct_routes, 0)

    def test_abstention_malformed_failure_and_unattempted_are_distinct(self):
        for execution in ("SUCCESS", "MALFORMED_OUTPUT", "RUNTIME_FAILURE", "UNATTEMPTED"):
            out = outcomes()
            row = out["cases"][0]
            row["execution"] = execution
            row["fields"] = [] if execution != "SUCCESS" else row["fields"]
            if execution == "SUCCESS":
                row["fields"][0].update(state="ABSTAIN", value=None, candidate_ids=[], evidence=[])
            result = self.score(recorded=out)
            counts = dict(result.execution_counts)
            self.assertEqual(counts[execution], 1)
            self.assertEqual(result.fields[0].abstentions, int(execution == "SUCCESS"))
        out = outcomes()
        out["cases"][0]["fields"][0]["state"] = "ACCEPT"
        self.assertEqual(dict(self.score(recorded=out).execution_counts)["MALFORMED_OUTPUT"], 1)

    def test_input_paths_and_output_authority_fields_fail_closed(self):
        for path in ("../private.jpg", "C:/private.jpg", "/private.jpg", "synthetic\\private.jpg", "https://example.org/a.jpg"):
            b = benchmark()
            b["cases"][0]["input_ref"] = path
            m, b, _ = sealed(self.contract, bench=b)
            self.assertFalse(self.contract.validate_benchmark(m, b).valid)
        out = outcomes()
        out["cases"][0]["save"] = True
        self.assertEqual(dict(self.score(recorded=out).execution_counts)["MALFORMED_OUTPUT"], 1)

    def test_packaged_fixture_is_synthetic_and_schema_conformant(self):
        path = Path(__file__).parents[1] / "benchmarks/canadian_common_coin_phase1a/synthetic-contract-fixtures.json"
        fixture = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(fixture["classification"], "SYNTHETIC_ONLY_NOT_REAL_EVIDENCE")
        result = self.contract.score_recorded_outcomes(fixture["metadata"], fixture["benchmark"], fixture["outcomes"])
        self.assertTrue(result.synthetic)
        self.assertFalse(result.evaluation_pass)

    def test_malformed_envelopes_fail_closed_without_crashes(self):
        for value in (None, [], {}, {"cases": []}, {"cases": "bad"},
                      {"schema_version": "unknown", "cases": []}):
            with self.subTest(value=value):
                m, b, _ = sealed(self.contract)
                result = self.contract.score_recorded_outcomes(m, b, value)
                self.assertFalse(result.evaluation_pass)
                self.assertEqual(dict(result.execution_counts)["MALFORMED_OUTPUT"], 1)

    def test_unverified_truth_is_not_labelled_false_ground_truth(self):
        b = benchmark()
        b["cases"][0]["fields"][0]["truth"]["state"] = "UNVERIFIED"
        result = self.score(bench=b)
        self.assertEqual(result.false_supported_years, 0)
        self.assertIn("UNSCORABLE_SUPPORTED", self.codes(result))

    def test_scoring_is_order_independent_for_multiple_cases(self):
        b, out = benchmark(), outcomes()
        second = copy.deepcopy(b["cases"][0])
        second.update(case_id="synthetic-second", coin_group_id="synthetic-second-coin",
                      capture_group_id="synthetic-second-capture", input_ref="synthetic/second.json",
                      input_sha256="4" * 64)
        b["cases"].append(second)
        second_out = copy.deepcopy(out["cases"][0])
        second_out["case_id"] = "synthetic-second"
        out["cases"].append(second_out)
        first = self.score(bench=copy.deepcopy(b), recorded=copy.deepcopy(out))
        b["cases"].reverse()
        out["cases"].reverse()
        self.assertEqual(first, self.score(bench=b, recorded=out))

    def test_direct_dates_with_unresolved_side_cannot_hide_conflict_or_partial_date(self):
        for value in ("2001", "200?", "2000-2001"):
            out = outcomes()
            out["cases"][0]["fields"][0]["evidence"].append(evidence("synthetic-unsided", value, "NONE"))
            result = self.score(recorded=out)
            self.assertEqual(result.false_supported_years, 1)
            self.assertEqual(result.fields[0].correct_supported, 0)
            self.assertFalse(result.fields[0].gate_pass)

    def test_required_evidence_cannot_disappear_from_ambiguous_or_supported_routes(self):
        for state in ("AMBIGUOUS", "SUPPORTED"):
            b, out = benchmark(), outcomes()
            f = b["cases"][0]["fields"][0]
            f.update(expected_state=state)
            if state == "AMBIGUOUS":
                f["truth"]["value"] = None
                f["required_evidence"].append(evidence("synthetic-other", "2001", "OBVERSE"))
                out["cases"][0]["fields"][0].update(state=state, value=None, evidence=[])
            else:
                out["cases"][0]["fields"][0]["evidence"] = [evidence("changed-id")]
            result = self.score(bench=b, recorded=out)
            self.assertGreater(result.conflict_evidence_loss, 0)
            self.assertEqual(result.fields[0].correct_routes, 0)
            self.assertEqual(result.fields[0].correct_supported, 0)

    def test_huge_malformed_integers_are_diagnostics_not_runtime_exceptions(self):
        m = metadata()
        m["issues"][0]["year_start"] = 10**1000
        self.assertFalse(self.contract.validate_metadata(m).valid)
        out = outcomes()
        out["cases"][0]["fields"][0]["value"] = 10**1000
        result = self.score(recorded=out)
        self.assertEqual(dict(result.execution_counts)["MALFORMED_OUTPUT"], 1)

    def test_selected_issue_metadata_cannot_conflict_with_supported_denomination(self):
        b, out = benchmark(), outcomes()
        b["policy"]["thresholds"][0]["field"] = "denomination"
        f = b["cases"][0]["fields"][0]
        f.update(field="denomination", required_evidence=[evidence(value="10c")])
        f["truth"].update(value="10c", source_refs=[ref("denomination")])
        out["cases"][0]["fields"][0].update(field="denomination", value="10c", evidence=[evidence(value="10c")])
        result = self.score(bench=b, recorded=out)
        self.assertEqual(result.fields[0].correct_supported, 0)
        self.assertFalse(result.fields[0].gate_pass)
        self.assertIn("CONFLICTING_FIELD_METADATA", self.codes(result))


if __name__ == "__main__":
    unittest.main()
