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


if __name__ == "__main__":
    unittest.main()
