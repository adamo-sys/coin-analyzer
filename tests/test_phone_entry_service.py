"""Synthetic contract tests for the Tk-independent phone-entry save boundary."""

from __future__ import annotations

import tempfile
import unittest
import os
import json
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from coin_collection import CoinCollection, CoinItem
from capture_import.reviewed_coin_collection_entry import ReviewedCoinPersistenceError
from phone_entry_service import (
    PhoneEntryAuditError,
    PhoneEntryAuditStore,
    PhoneEntryRecoveryRequired,
    PhoneEntryService,
    PhoneEntryStateError,
)
from phone_intake import PhoneIntake


class PhoneEntryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        previous_cwd = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, previous_cwd)
        self.front = self.root / "front.jpg"
        self.reverse = self.root / "reverse.png"
        Image.new("RGB", (24, 24), "red").save(self.front)
        Image.new("RGB", (24, 24), "blue").save(self.reverse)
        self.collection = CoinCollection(str(self.root / "collection.json"))
        self.intake = PhoneIntake(str(self.root / "phone-intake.json"))
        self.audit = PhoneEntryAuditStore(str(self.root / "phone-entry-audit.json"))
        self.service = PhoneEntryService(
            collection=self.collection,
            intake=self.intake,
            audit_store=self.audit,
            approval_verifier=_TestApprovalVerifier(),
        )

    def test_manual_entry_requires_verification_and_separate_save_confirmation(self) -> None:
        """Removing either confirmation must prevent collection mutation."""
        draft = self.service.create_draft(
            front_path=str(self.front),
            reverse_path=str(self.reverse),
            session_id="session-opaque-1",
        )

        with self.assertRaises(PhoneEntryStateError):
            self.service.save(draft.entry_id, save_approval="trusted-save")

        with self.assertRaises(PhoneEntryStateError):
            self.service.verify(
                draft.entry_id,
                country="Canada",
                denomination="25 cents",
                year="1967",
                type_design="Centennial",
                verification_approval="model-assertion",
            )

        self.service.verify(
            draft.entry_id,
            country="Canada",
            denomination="25 cents",
            year="1967",
            type_design="Centennial",
            verification_approval="trusted-verify",
        )
        with self.assertRaises(PhoneEntryStateError):
            self.service.save(draft.entry_id, save_approval="model-assertion")

        result = self.service.save(draft.entry_id, save_approval="trusted-save")

        self.assertEqual(result.state, "SAVED")
        self.assertEqual(len(self.collection.items), 1)
        saved = self.collection.get_item(result.item_id)
        assert saved is not None
        self.assertEqual((saved.country, saved.denomination, saved.year), ("Canada", "25 cents", "1967"))
        self.assertEqual(saved.type_design, "Centennial")
        self.assertEqual([photo.role.value for photo in saved.photos], ["FRONT", "BACK"])
        reopened = self.service.reopen(draft.entry_id)
        self.assertEqual(reopened["state"], "SAVED")
        self.assertEqual(reopened["human_final"], {
            "country": "Canada",
            "denomination": "25 cents",
            "year": "1967",
            "type_design": "Centennial",
        })

    def test_stale_collection_rejection_enters_recovery_without_a_repeat_save(self) -> None:
        """A stale collection must remain unchanged and a second save must be blocked."""
        draft = self._verified_draft()
        other = CoinCollection(self.collection.storage_path)
        self.assertTrue(other.add_item(CoinItem(
            id="other-item",
            image_path="",
            country="United States",
            denomination="1 cent",
            year="1964",
            grade="",
            notes="",
            date_added="2026-09-27T00:00:00+00:00",
        )))

        with self.assertRaises(PhoneEntryRecoveryRequired):
            self.service.save(draft.entry_id, save_approval="trusted-save")

        self.assertEqual(len(CoinCollection(self.collection.storage_path).items), 1)
        self.assertEqual(self.service.reopen(draft.entry_id)["state"], "RECOVERY_REQUIRED")
        with self.assertRaises(PhoneEntryStateError):
            self.service.save(draft.entry_id, save_approval="trusted-save")

    def test_persistence_failure_never_auto_retries_or_marks_a_collection_item_saved(self) -> None:
        """Removing the underlying save must leave recovery, never an implicit retry."""
        draft = self._verified_draft()
        with patch("phone_entry_service.persist_reviewed_coin", side_effect=ReviewedCoinPersistenceError("synthetic failure")):
            with self.assertRaises(PhoneEntryRecoveryRequired):
                self.service.save(draft.entry_id, save_approval="trusted-save")

        self.assertEqual(self.collection.items, [])
        self.assertEqual(self.service.reopen(draft.entry_id)["state"], "RECOVERY_REQUIRED")
        with self.assertRaises(PhoneEntryStateError):
            self.service.save(draft.entry_id, save_approval="trusted-save")

    def test_audit_finalization_failure_requires_reconciliation_without_resaving(self) -> None:
        """A saved collection item plus failed audit finalization is recovery-only."""
        draft = self._verified_draft()
        with patch.object(self.audit, "finalize", side_effect=PhoneEntryAuditError("synthetic audit outage")):
            with self.assertRaises(PhoneEntryRecoveryRequired):
                self.service.save(draft.entry_id, save_approval="trusted-save")

        self.assertEqual(len(self.collection.items), 1)
        self.assertEqual(self.service.reopen(draft.entry_id)["state"], "RECOVERY_REQUIRED")
        with self.assertRaises(PhoneEntryStateError):
            self.service.save(draft.entry_id, save_approval="trusted-save")

        result = self.service.reconcile(draft.entry_id)
        self.assertEqual(result.state, "SAVED")
        self.assertEqual(len(self.collection.items), 1)

    def test_reopen_representation_omits_session_and_all_paths(self) -> None:
        """Removing the projection's privacy filter must expose this test's sentinel."""
        draft = self.service.create_draft(
            front_path=str(self.front),
            reverse_path=str(self.reverse),
            session_id="session-private-sentinel",
        )

        representation = self.service.reopen(draft.entry_id)

        serialized = str(representation)
        self.assertNotIn("session-private-sentinel", serialized)
        self.assertNotIn(str(self.root), serialized)
        self.assertNotIn(self.front.name, serialized)
        raw_audit = self.audit.path.read_text(encoding="utf-8")
        self.assertNotIn("session-private-sentinel", raw_audit)
        self.assertIn("session_reference", json.loads(raw_audit)["entries"][draft.entry_id])

    def test_absent_producer_records_and_reopens_all_abstentions(self) -> None:
        draft = self.service.create_draft(
            front_path=str(self.front), reverse_path=str(self.reverse), session_id="session-opaque-absent"
        )

        proposal = self.service.reopen(draft.entry_id)["proposal"]
        self.assertEqual(proposal["source_coin_id"], draft.entry_id)
        self.assertTrue(all(field["status"] == "ABSTAIN" for field in proposal["fields"]))
        self.assertEqual(self.service.reopen(draft.entry_id)["human_final"], {})

    def test_valid_injected_proposal_is_snapshot_only_and_records_field_comparison(self) -> None:
        service = PhoneEntryService(
            collection=self.collection,
            intake=self.intake,
            audit_store=self.audit,
            approval_verifier=_TestApprovalVerifier(),
            proposal_producer=_ValidProposalProducer(),
        )
        draft = service.create_draft(front_path=str(self.front), reverse_path=str(self.reverse), session_id="private-session")
        self.assertEqual(service.reopen(draft.entry_id)["proposal"]["producer_ids"], ["fixture-producer"])
        service.verify(draft.entry_id, country="Canada", denomination="25 cents", year="1967", verification_approval="trusted-verify")
        record = self.audit.get(draft.entry_id)
        comparison = record["field_changes"]["country"]
        self.assertEqual(comparison["proposal"]["status"], "ABSTAIN")
        self.assertEqual(comparison["human_final"], "Canada")
        self.assertNotIn("disposition", comparison)
        serialized = self.audit.path.read_text(encoding="utf-8")
        reopened = service.reopen(draft.entry_id)
        self.assertNotIn("private-session", serialized)
        self.assertNotIn(str(self.root), serialized)
        self.assertNotIn(str(self.root), str(reopened))

    def test_explicit_treatment_retains_the_snapshot_and_final_human_value(self) -> None:
        """Removing the explicit action must not create a treatment audit row."""
        draft = self.service.create_draft(
            front_path=str(self.front), reverse_path=str(self.reverse), session_id="opaque-treatment"
        )
        proposal = _proposal_with_supported_country(draft.entry_id)
        with self.audit._edit() as entries:
            entries[draft.entry_id]["proposal"] = proposal

        self.service.record_treatment(draft.entry_id, proposal_field="country", disposition="used")

        before_verify = self.audit.get(draft.entry_id)
        self.assertEqual(before_verify["state"], "DRAFT")
        self.assertEqual(self.collection.items, [])
        self.assertEqual(before_verify["field_treatments"]["country"][0]["proposal"], proposal["fields"][0])
        self.assertIsNone(before_verify["field_treatments"]["country"][0]["human_final"])
        self.service.verify(
            draft.entry_id,
            country="Canada",
            denomination="25 cents",
            year="1967",
            verification_approval="trusted-verify",
        )

        treatment = self.audit.get(draft.entry_id)["field_treatments"]["country"][0]
        self.assertEqual(treatment["disposition"], "used")
        self.assertEqual(treatment["human_final"], "Canada")
        self.assertEqual(treatment["proposal"], proposal["fields"][0])
        serialized = self.audit.path.read_text(encoding="utf-8")
        reopened = self.service.reopen(draft.entry_id)
        self.assertNotIn("opaque-treatment", serialized)
        self.assertNotIn(str(self.root), serialized)
        self.assertNotIn(str(self.root), str(reopened))

    def test_manual_after_abstention_requires_an_explicit_treatment_action(self) -> None:
        """Deleting the manual action must leave the audit without an inferred disposition."""
        draft = self.service.create_draft(
            front_path=str(self.front), reverse_path=str(self.reverse), session_id="opaque-abstention"
        )

        self.assertEqual(self.audit.get(draft.entry_id).get("field_treatments", {}), {})
        self.service.record_treatment(
            draft.entry_id, proposal_field="year", disposition="manual_after_abstention"
        )

        treatment = self.audit.get(draft.entry_id)["field_treatments"]["year"][0]
        self.assertEqual(treatment["disposition"], "manual_after_abstention")
        self.assertEqual(treatment["proposal"]["status"], "ABSTAIN")

    def test_explicit_edit_and_ignore_are_recorded_without_authorization(self) -> None:
        """Changing review treatment to an approval must fail this state/authority check."""
        draft = self.service.create_draft(
            front_path=str(self.front), reverse_path=str(self.reverse), session_id="opaque-edit-ignore"
        )

        self.service.record_treatment(draft.entry_id, proposal_field="country", disposition="edited")
        self.service.record_treatment(draft.entry_id, proposal_field="denomination", disposition="ignored")

        record = self.audit.get(draft.entry_id)
        self.assertEqual(record["state"], "DRAFT")
        self.assertEqual(record["field_treatments"]["country"][0]["disposition"], "edited")
        self.assertEqual(record["field_treatments"]["denomination"][0]["disposition"], "ignored")
        with self.assertRaises(PhoneEntryStateError):
            self.service.save(draft.entry_id, save_approval="trusted-save")

    def test_exception_malformed_and_mismatched_producers_fail_closed(self) -> None:
        for producer in (_RaisingProposalProducer(), _MalformedProposalProducer(), _MismatchedProposalProducer()):
            with self.subTest(producer=type(producer).__name__):
                self.setUp()
                service = PhoneEntryService(
                    collection=self.collection,
                    intake=self.intake,
                    audit_store=self.audit,
                    approval_verifier=_TestApprovalVerifier(),
                    proposal_producer=producer,
                )
                draft = service.create_draft(front_path=str(self.front), reverse_path=str(self.reverse), session_id="opaque")
                proposal = service.reopen(draft.entry_id)["proposal"]
                self.assertEqual(proposal["source_coin_id"], draft.entry_id)
                self.assertEqual(proposal["producer_ids"], [])
                self.assertTrue(all(field["status"] == "ABSTAIN" for field in proposal["fields"]))

    def test_legacy_audit_record_without_proposal_fields_reopens_safely(self) -> None:
        draft = self.service.create_draft(front_path=str(self.front), reverse_path=str(self.reverse), session_id="opaque")
        raw = json.loads(self.audit.path.read_text(encoding="utf-8"))
        raw["entries"][draft.entry_id].pop("proposal")
        raw["entries"][draft.entry_id].pop("field_changes")
        self.audit.path.write_text(json.dumps(raw), encoding="utf-8")
        reopened = self.service.reopen(draft.entry_id)
        self.assertTrue(all(field["status"] == "ABSTAIN" for field in reopened["proposal"]["fields"]))
        self.assertEqual(reopened["human_final"], {})
    def _verified_draft(self):
        draft = self.service.create_draft(
            front_path=str(self.front),
            reverse_path=str(self.reverse),
            session_id="session-opaque-2",
        )
        self.service.verify(
            draft.entry_id,
            country="Canada",
            denomination="25 cents",
            year="1967",
            type_design="Centennial",
            verification_approval="trusted-verify",
        )
        return draft


class _TestApprovalVerifier:
    def verify(self, *, entry_id: str, action: str, approval: str) -> bool:
        return (action, approval) in {
            ("VERIFY", "trusted-verify"),
            ("SAVE", "trusted-save"),
        }

class _ValidProposalProducer:
    def propose(self, *, entry_id, pair_id, media):
        from capture_import.coin_field_proposals import all_abstain_coin_field_proposal_set
        return all_abstain_coin_field_proposal_set(entry_id, producer_ids=("fixture-producer",))


class _RaisingProposalProducer:
    def propose(self, **kwargs):
        raise RuntimeError("private producer error")


class _MalformedProposalProducer:
    def propose(self, **kwargs):
        return object()


class _MismatchedProposalProducer:
    def propose(self, **kwargs):
        from capture_import.coin_field_proposals import all_abstain_coin_field_proposal_set
        return all_abstain_coin_field_proposal_set("other-entry")


def _proposal_with_supported_country(entry_id: str) -> dict[str, object]:
    fields = []
    for field_name in ("country", "denomination", "year", "monarch", "reverse_design", "variety"):
        supported = field_name == "country"
        fields.append({
            "field_name": field_name,
            "status": "SUPPORTED" if supported else "ABSTAIN",
            "proposed_value": "Canada" if supported else None,
            "normalized_value": "canada" if supported else None,
            "evidence": ([{"source": "DIRECT_OBSERVATION", "image_role": "OBVERSE", "artifact_id": "safe-artifact", "observed_value": "Canada", "producer_id": "fixture"}] if supported else []),
            "reasons": ["direct_field_evidence"] if supported else ["no_advisory_evidence"],
            "scope": "DIRECT_OBSERVATION",
            "candidate_ids": [],
        })
    return {"schema_version": 1, "source_coin_id": entry_id, "producer_ids": ["fixture"], "fields": fields}

if __name__ == "__main__":
    unittest.main()
