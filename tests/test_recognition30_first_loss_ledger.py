import json
import tempfile
import unittest
from pathlib import Path

from capture_import.recognition30_first_loss_ledger import build_first_loss_ledger, main


def _row(case_id, *, decision="abstain", reason="unexplained"):
    return {
        "case_id": case_id,
        "decision": decision,
        "reason": reason,
        "provider_failures": [],
        "retriever_id": "recognition30-v2-oracle",
        "query_id": case_id,
        "retrieved_candidate_ids": [],
        "verified_candidate_ids": [],
        "verification_rows": [],
        "observations": [],
    }


class Recognition30FirstLossLedgerTests(unittest.TestCase):
    def test_classifies_thirty_rows_from_explicit_terminal_evidence_without_guessing(self):
        rows = [_row(f"CA-R30-{number:03d}") for number in range(1, 31)]
        rows[0] = _row(
            "CA-R30-001",
            decision="identify",
            reason="unique_verified_candidate_with_two_side_support",
        )
        rows[0]["retrieved_candidate_ids"] = ["CA-R30-001"]
        rows[0]["verified_candidate_ids"] = ["CA-R30-001"]
        rows[0]["predicted_candidate_id"] = "CA-R30-001"
        rows[0]["verification_rows"] = [
            {"candidate_id": "CA-R30-001", "verified": True}
        ]
        rows[1] = _row(
            "CA-R30-002",
            reason="conflicting evidence cannot be sent to catalogue retrieval.",
        )
        rows[2] = _row("CA-R30-003", reason="no_candidates")
        rows[3] = _row("CA-R30-004", reason="none_verified")
        rows[3]["retrieved_candidate_ids"] = ["CA-R30-004"]
        rows[3]["verification_rows"] = [
            {"candidate_id": "CA-R30-004", "verified": False}
        ]
        rows[4] = _row("CA-R30-005", reason="no_candidates")
        rows[4]["retrieved_candidate_ids"] = ["CA-R30-005"]

        ledger = build_first_loss_ledger(
            {
                "schema": "coin-analyzer-recognition30-grounded-v1",
                "dataset_version": "recognition30_v2",
                "rows": rows,
            }
        )

        self.assertEqual(30, ledger["summary"]["total_cases"])
        self.assertEqual(1, ledger["summary"]["classes"]["IDENTIFIED"])
        self.assertEqual(
            1,
            ledger["summary"]["classes"][
                "CONFLICTING_EVIDENCE_BEFORE_RETRIEVAL"
            ],
        )
        self.assertEqual(1, ledger["summary"]["classes"]["NO_CANDIDATES"])
        self.assertEqual(1, ledger["summary"]["classes"]["NONE_VERIFIED"])
        self.assertEqual(
            "CA-R30-001",
            ledger["rows"][0]["provenance"]["predicted_candidate_id"],
        )
        self.assertEqual("UNCLASSIFIED", ledger["rows"][4]["terminal_classification"])
        self.assertEqual(
            "no_candidates_with_retrieved_candidates",
            ledger["rows"][4]["unclassified_reason"],
        )

    def test_identified_without_verified_candidate_evidence_is_unclassified(self):
        rows = [_row(f"CA-R30-{number:03d}", reason="no_candidates") for number in range(1, 31)]
        rows[0] = _row(
            "CA-R30-001",
            decision="identify",
            reason="unique_verified_candidate_with_two_side_support",
        )

        ledger = build_first_loss_ledger(
            {
                "schema": "coin-analyzer-recognition30-grounded-v1",
                "dataset_version": "recognition30_v2",
                "rows": rows,
            }
        )

        self.assertEqual("UNCLASSIFIED", ledger["rows"][0]["terminal_classification"])
        self.assertEqual(
            "identified_without_consistent_verified_candidate",
            ledger["rows"][0]["unclassified_reason"],
        )

    def test_none_verified_with_mismatched_verification_row_is_unclassified(self):
        rows = [_row(f"CA-R30-{number:03d}", reason="no_candidates") for number in range(1, 31)]
        rows[0] = _row("CA-R30-001", reason="none_verified")
        rows[0]["retrieved_candidate_ids"] = ["CA-R30-001"]
        rows[0]["verification_rows"] = [
            {"candidate_id": "CA-R30-002", "verified": False}
        ]

        ledger = build_first_loss_ledger(
            {
                "schema": "coin-analyzer-recognition30-grounded-v1",
                "dataset_version": "recognition30_v2",
                "rows": rows,
            }
        )

        self.assertEqual("UNCLASSIFIED", ledger["rows"][0]["terminal_classification"])
        self.assertEqual(
            "none_verified_without_complete_verification_trace",
            ledger["rows"][0]["unclassified_reason"],
        )

    def test_no_candidates_with_verified_candidate_is_unclassified(self):
        rows = [_row(f"CA-R30-{number:03d}", reason="no_candidates") for number in range(1, 31)]
        rows[0]["verified_candidate_ids"] = ["CA-R30-001"]

        ledger = build_first_loss_ledger(
            {
                "schema": "coin-analyzer-recognition30-grounded-v1",
                "dataset_version": "recognition30_v2",
                "rows": rows,
            }
        )

        self.assertEqual("UNCLASSIFIED", ledger["rows"][0]["terminal_classification"])
        self.assertEqual(
            "no_candidates_with_verification_evidence",
            ledger["rows"][0]["unclassified_reason"],
        )

    def test_provider_failure_with_verified_candidate_is_unclassified(self):
        rows = [_row(f"CA-R30-{number:03d}", reason="no_candidates") for number in range(1, 31)]
        rows[0] = _row("CA-R30-001", reason="provider_observation_failure")
        rows[0]["provider_failures"] = [{"failure_kind": "provider_timeout"}]
        rows[0]["verified_candidate_ids"] = ["CA-R30-001"]

        ledger = build_first_loss_ledger(
            {
                "schema": "coin-analyzer-recognition30-grounded-v1",
                "dataset_version": "recognition30_v2",
                "rows": rows,
            }
        )

        self.assertEqual("UNCLASSIFIED", ledger["rows"][0]["terminal_classification"])

    def test_identified_with_two_verified_candidates_is_unclassified(self):
        rows = [_row(f"CA-R30-{number:03d}", reason="no_candidates") for number in range(1, 31)]
        rows[0] = _row(
            "CA-R30-001",
            decision="identify",
            reason="unique_verified_candidate_with_two_side_support",
        )
        rows[0]["retrieved_candidate_ids"] = ["CA-R30-001", "CA-R30-002"]
        rows[0]["verified_candidate_ids"] = ["CA-R30-001"]
        rows[0]["predicted_candidate_id"] = "CA-R30-001"
        rows[0]["verification_rows"] = [
            {"candidate_id": "CA-R30-001", "verified": True},
            {"candidate_id": "CA-R30-002", "verified": True},
        ]

        ledger = build_first_loss_ledger(
            {
                "schema": "coin-analyzer-recognition30-grounded-v1",
                "dataset_version": "recognition30_v2",
                "rows": rows,
            }
        )

        self.assertEqual("UNCLASSIFIED", ledger["rows"][0]["terminal_classification"])

    def test_cli_writes_offline_ledger_without_observation_contents(self):
        rows = [_row(f"CA-R30-{number:03d}", reason="no_candidates") for number in range(1, 31)]
        rows[0]["observations"] = [
            {
                "role": "obverse",
                "visible_text": ["PRIVATE LEGEND"],
                "date_like": "1967",
                "denomination_mark": "10 CENTS",
            }
        ]
        report = {
            "schema": "coin-analyzer-recognition30-grounded-v1",
            "dataset_version": "recognition30_v2",
            "rows": rows,
        }

        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "report.json"
            ledger_path = Path(directory) / "ledger.json"
            source_path.write_text(json.dumps(report), encoding="utf-8")

            self.assertEqual(0, main([str(source_path), str(ledger_path)]))

            written = json.loads(ledger_path.read_text(encoding="utf-8"))

        self.assertEqual("coin-analyzer-recognition30-first-loss-ledger-v1", written["schema"])
        self.assertEqual(["obverse"], written["rows"][0]["provenance"]["observed_roles"])
        self.assertNotIn("PRIVATE LEGEND", json.dumps(written))
        self.assertNotIn("1967", json.dumps(written))


if __name__ == "__main__":
    unittest.main()
