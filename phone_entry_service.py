"""Tk-independent, manual-first phone-entry save service.

This module owns no collection model and never treats proposals as save authority.
It binds one explicit ``PhoneIntake`` pair to the existing reviewed-save bridge
and keeps a path-free local audit sidecar for later HTTP/UI presentation.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterator, Mapping, Protocol
from uuid import uuid4

from atomic_json import write_json_atomically
from capture_import.coin_field_proposals import CoinFieldProposalSet, all_abstain_coin_field_proposal_set
from capture_import.lock import PackageImportLock
from capture_import.reviewed_coin_collection_entry import (
    ReviewedCoinDraft,
    ReviewedCoinPersistenceError,
    persist_reviewed_coin,
)
from capture_import.standalone_image_intake import create_temporary_capture_package
from coin_collection import CoinCollection
from phone_intake import PhoneIntake, PhoneIntakeError


_OPAQUE_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
_STATES = frozenset({"DRAFT", "VERIFIED", "SAVING", "SAVED", "RECOVERY_REQUIRED"})
_IDENTITY_FIELDS = ("country", "denomination", "year", "type_design")


class PhoneEntryError(ValueError):
    """The phone-entry contract cannot safely proceed."""


class PhoneEntryStateError(PhoneEntryError):
    """An action is not permitted in the draft's current state."""


class PhoneEntryRecoveryRequired(PhoneEntryError):
    """A collection save may have succeeded; it must be reconciled, not retried."""


class PhoneEntryAuditError(PhoneEntryError):
    """The local audit sidecar is unreadable or cannot be finalized."""


class PhoneEntryApprovalVerifier(Protocol):
    """Trusted host boundary for one explicit human approval action."""

    def verify(self, *, entry_id: str, action: str, approval: str) -> bool:
        """Return true only for a host-issued, action-bound approval."""


class PhoneEntryProposalProducer(Protocol):
    """Optional bounded advisory producer; never a save authority."""

    def propose(self, *, entry_id: str, pair_id: str, media: tuple[tuple[str, str], ...]) -> CoinFieldProposalSet:
        """Return an immutable proposal snapshot bound to this entry."""


@dataclass(frozen=True, slots=True)
class PhoneEntryDraft:
    """Safe representation for a future mobile client; it exposes no paths."""

    entry_id: str
    pair_id: str
    state: str
    media: tuple[tuple[str, str], ...]
    proposal: dict[str, Any] | None = None
    human_final: tuple[tuple[str, str], ...] = ()
    item_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "pair_id": self.pair_id,
            "state": self.state,
            "media": [{"role": role, "sha256": digest} for role, digest in self.media],
            "proposal": self.proposal,
            "human_final": dict(self.human_final),
            "item_id": self.item_id,
        }


@dataclass(frozen=True, slots=True)
class PhoneEntrySaveResult:
    entry_id: str
    state: str
    item_id: str


class PhoneEntryAuditStore:
    """Versioned, path-free local audit state; never a collection authority."""

    def __init__(self, path: str = "data/phone_entry_audit.json") -> None:
        self.path = Path(path).absolute()

    def records(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if raw.get("version") != 1 or not isinstance(raw.get("entries"), dict):
                raise ValueError("unsupported audit schema")
            entries = raw["entries"]
            for entry_id, entry in entries.items():
                self._normalize_v1_entry(entry_id, entry)
                self._validate_entry(entry_id, entry)
            return entries
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise PhoneEntryAuditError("Phone-entry audit state is unreadable; recovery is required.") from error

    @staticmethod
    def _normalize_v1_entry(entry_id: str, entry: dict[str, Any]) -> None:
        """Normalize historical v1 records without a broader schema redesign."""
        entry.setdefault("proposal", None)
        entry.setdefault("field_changes", {})

    @contextmanager
    def _edit(self) -> Iterator[dict[str, dict[str, Any]]]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = PackageImportLock.acquire(self.path.with_suffix(".lock"), import_id=str(uuid4()))
        try:
            entries = self.records()
            yield entries
            for entry_id, entry in entries.items():
                self._validate_entry(entry_id, entry)
            write_json_atomically(str(self.path), {"version": 1, "entries": entries})
        finally:
            lock.release()

    def create(self, *, pair_id: str, session_reference: str, media: Mapping[str, str]) -> dict[str, Any]:
        self._validate_id(pair_id, "pair_id")
        if re.fullmatch(r"[0-9a-f]{64}", session_reference) is None:
            raise PhoneEntryAuditError("session_reference must be a one-way SHA-256 value.")
        normalized_media = self._normalize_media(media)
        entry_id = str(uuid4())
        entry = {
            "entry_id": entry_id,
            "pair_id": pair_id,
            "session_reference": session_reference,
            "created_at": _now(),
            "updated_at": _now(),
            "state": "DRAFT",
            "media": normalized_media,
            "proposal": None,
            "human_final": {},
            "field_changes": {},
            "human_verified_at": None,
            "save_confirmed_at": None,
            "item_id": None,
            "reconciliation_state": "NOT_STARTED",
        }
        with self._edit() as entries:
            entries[entry_id] = entry
        return dict(entry)

    def record_proposal(self, entry_id: str, proposal: CoinFieldProposalSet) -> dict[str, Any]:
        if not isinstance(proposal, CoinFieldProposalSet) or proposal.source_coin_id != entry_id:
            raise PhoneEntryAuditError("Proposal snapshot is not bound to this phone-entry draft.")
        with self._edit() as entries:
            entry = self._entry(entries, entry_id, "DRAFT")
            entry["proposal"] = proposal.to_dict()
            entry["updated_at"] = _now()
            return dict(entry)

    def get(self, entry_id: str) -> dict[str, Any]:
        try:
            return dict(self.records()[entry_id])
        except KeyError as error:
            raise PhoneEntryStateError("Phone-entry draft was not found.") from error

    def verify(self, entry_id: str, human_final: Mapping[str, str]) -> dict[str, Any]:
        normalized = _normalize_identity(human_final)
        with self._edit() as entries:
            entry = self._entry(entries, entry_id, "DRAFT")
            entry["human_final"] = normalized
            proposal_snapshot = entry["proposal"] or all_abstain_coin_field_proposal_set(entry_id).to_dict()
            proposal_fields = {item["field_name"]: item for item in proposal_snapshot["fields"]}
            entry["field_changes"] = {
                field: {"proposal": proposal_fields.get(field), "human_final": value}
                for field, value in normalized.items()
            }
            entry["human_verified_at"] = _now()
            entry["state"] = "VERIFIED"
            entry["updated_at"] = _now()
            return dict(entry)

    def begin_save(self, entry_id: str) -> dict[str, Any]:
        with self._edit() as entries:
            entry = self._entry(entries, entry_id, "VERIFIED")
            entry["state"] = "SAVING"
            entry["save_confirmed_at"] = _now()
            entry["reconciliation_state"] = "PENDING"
            entry["updated_at"] = _now()
            return dict(entry)

    def record_persisted(self, entry_id: str, item_id: str) -> dict[str, Any]:
        self._validate_id(item_id, "item_id")
        with self._edit() as entries:
            entry = self._entry(entries, entry_id, "SAVING")
            entry["item_id"] = item_id
            entry["reconciliation_state"] = "PERSISTED_AWAITING_RECONCILIATION"
            entry["updated_at"] = _now()
            return dict(entry)

    def finalize(self, entry_id: str, item_id: str) -> dict[str, Any]:
        self._validate_id(item_id, "item_id")
        with self._edit() as entries:
            entry = self._entry(entries, entry_id, "SAVING")
            if entry["item_id"] not in (None, item_id):
                raise PhoneEntryAuditError("Audit item identity differs from persisted collection item.")
            entry["item_id"] = item_id
            entry["state"] = "SAVED"
            entry["reconciliation_state"] = "COMPLETE"
            entry["updated_at"] = _now()
            return dict(entry)

    def mark_recovery_required(self, entry_id: str) -> None:
        with self._edit() as entries:
            entry = self._entry(entries, entry_id, "SAVING")
            entry["state"] = "RECOVERY_REQUIRED"
            entry["reconciliation_state"] = "RECOVERY_REQUIRED"
            entry["updated_at"] = _now()

    @staticmethod
    def _entry(entries: dict[str, dict[str, Any]], entry_id: str, expected_state: str) -> dict[str, Any]:
        entry = entries.get(entry_id)
        if entry is None:
            raise PhoneEntryStateError("Phone-entry draft was not found.")
        if entry["state"] != expected_state:
            raise PhoneEntryStateError("Phone-entry action is not available in its current state.")
        return entry

    @staticmethod
    def _validate_id(value: Any, name: str) -> None:
        if not isinstance(value, str) or _OPAQUE_ID.fullmatch(value) is None:
            raise PhoneEntryAuditError(f"{name} must be an opaque identifier.")

    @classmethod
    def _normalize_media(cls, media: Mapping[str, str]) -> dict[str, str]:
        if set(media) != {"front", "reverse"}:
            raise PhoneEntryAuditError("Audit media requires front and reverse roles.")
        result = {role: str(digest) for role, digest in media.items()}
        if any(re.fullmatch(r"[0-9a-f]{64}", digest) is None for digest in result.values()):
            raise PhoneEntryAuditError("Audit media hashes must be lowercase SHA-256 values.")
        return result

    @classmethod
    def _validate_entry(cls, entry_id: Any, entry: Any) -> None:
        cls._validate_id(entry_id, "entry_id")
        if not isinstance(entry, dict) or entry.get("entry_id") != entry_id:
            raise PhoneEntryAuditError("Phone-entry audit record is invalid.")
        cls._validate_id(entry.get("pair_id"), "pair_id")
        if re.fullmatch(r"[0-9a-f]{64}", str(entry.get("session_reference") or "")) is None:
            raise PhoneEntryAuditError("Phone-entry session reference is invalid.")
        if entry.get("state") not in _STATES:
            raise PhoneEntryAuditError("Phone-entry audit state is invalid.")
        cls._normalize_media(entry.get("media"))
        human_final = entry.get("human_final")
        if not isinstance(human_final, dict):
            raise PhoneEntryAuditError("Phone-entry final identity is invalid.")
        if human_final:
            _normalize_identity(human_final)
        if entry.get("item_id") is not None:
            cls._validate_id(entry["item_id"], "item_id")


class PhoneEntryService:
    """Explicitly human-authorized service over existing pair/save authority."""

    def __init__(
        self,
        *,
        collection: CoinCollection,
        intake: PhoneIntake,
        audit_store: PhoneEntryAuditStore,
        approval_verifier: PhoneEntryApprovalVerifier,
        proposal_producer: PhoneEntryProposalProducer | None = None,
    ) -> None:
        if not isinstance(collection, CoinCollection) or not isinstance(intake, PhoneIntake):
            raise TypeError("collection and intake must be their production service types.")
        self.collection = collection
        self.intake = intake
        self.audit_store = audit_store
        self.approval_verifier = approval_verifier
        self.proposal_producer = proposal_producer

    def create_draft(self, *, front_path: str, reverse_path: str, session_id: str) -> PhoneEntryDraft:
        pair_id = self.intake.confirm_pair(front_path, reverse_path)
        images = self.intake.records()[pair_id]["images"]
        media = {"front": images["front"]["sha256"], "reverse": images["reverse"]["sha256"]}
        entry = self.audit_store.create(pair_id=pair_id, session_reference=sha256(session_id.encode("utf-8")).hexdigest(), media=media)
        proposal = self._proposal_for_entry(entry["entry_id"], pair_id, media)
        return _draft_from_entry(self.audit_store.record_proposal(entry["entry_id"], proposal))

    def _proposal_for_entry(self, entry_id: str, pair_id: str, media: Mapping[str, str]) -> CoinFieldProposalSet:
        fallback = all_abstain_coin_field_proposal_set(entry_id)
        if self.proposal_producer is None:
            return fallback
        try:
            proposal = self.proposal_producer.propose(entry_id=entry_id, pair_id=pair_id, media=tuple(sorted(media.items())))
        except Exception:
            return fallback
        return proposal if isinstance(proposal, CoinFieldProposalSet) and proposal.source_coin_id == entry_id else fallback

    def verify(
        self,
        entry_id: str,
        *,
        country: str,
        denomination: str,
        year: str,
        type_design: str = "",
        verification_approval: str,
    ) -> PhoneEntryDraft:
        if not self.approval_verifier.verify(
            entry_id=entry_id,
            action="VERIFY",
            approval=verification_approval,
        ):
            raise PhoneEntryStateError("Explicit human verification is required before saving.")
        entry = self.audit_store.verify(entry_id, {
            "country": country,
            "denomination": denomination,
            "year": year,
            "type_design": type_design,
        })
        return _draft_from_entry(entry)

    def save(self, entry_id: str, *, save_approval: str) -> PhoneEntrySaveResult:
        if not self.approval_verifier.verify(
            entry_id=entry_id,
            action="SAVE",
            approval=save_approval,
        ):
            raise PhoneEntryStateError("Separate save confirmation is required.")
        entry = self.audit_store.begin_save(entry_id)
        try:
            front, reverse = self.intake.review_paths(entry["pair_id"])
            source = create_temporary_capture_package(front_path=front, reverse_path=reverse)
            try:
                source_coin_id = _source_coin_id(source.path)
                fields = entry["human_final"]
                draft = ReviewedCoinDraft(
                    source_coin_id=source_coin_id,
                    country=fields["country"],
                    denomination=fields["denomination"],
                    year=fields["year"],
                    type_design=fields["type_design"],
                )
                intent = self.intake.reserve(entry["pair_id"], self.collection.storage_path, draft)
                item = persist_reviewed_coin(
                    collection=self.collection,
                    draft=draft,
                    source_package_path=source.path,
                    item_id=intent["item_id"],
                    date_added=intent["date_added"],
                )
            finally:
                source.release()
        except (PhoneIntakeError, ReviewedCoinPersistenceError, OSError, ValueError) as error:
            self._recovery_required(entry_id)
            raise PhoneEntryRecoveryRequired("The phone-entry save needs recovery; it was not retried.") from error

        try:
            self.audit_store.record_persisted(entry_id, item.id)
            item_id = self.intake.complete(entry["pair_id"], self.collection.storage_path)
            self.audit_store.finalize(entry_id, item_id)
        except (PhoneIntakeError, PhoneEntryAuditError, OSError, ValueError) as error:
            self._recovery_required(entry_id)
            raise PhoneEntryRecoveryRequired("The coin may be saved; reconcile instead of saving again.") from error
        return PhoneEntrySaveResult(entry_id=entry_id, state="SAVED", item_id=item_id)

    def reconcile(self, entry_id: str) -> PhoneEntrySaveResult:
        entry = self.audit_store.get(entry_id)
        if entry["state"] not in {"SAVING", "RECOVERY_REQUIRED"}:
            raise PhoneEntryStateError("This phone-entry draft does not require reconciliation.")
        try:
            item_id = self.intake.complete(entry["pair_id"], self.collection.storage_path)
            if entry["state"] == "RECOVERY_REQUIRED":
                # Reopen a recovery record only after collection evidence proves the save.
                self._restore_saving_for_reconciliation(entry_id)
            self.audit_store.finalize(entry_id, item_id)
        except (PhoneIntakeError, PhoneEntryAuditError, OSError, ValueError) as error:
            self._recovery_required(entry_id)
            raise PhoneEntryRecoveryRequired("Reconciliation remains unresolved; do not resave.") from error
        return PhoneEntrySaveResult(entry_id=entry_id, state="SAVED", item_id=item_id)

    def reopen(self, entry_id: str) -> dict[str, Any]:
        return _draft_from_entry(self.audit_store.get(entry_id)).to_dict()

    def _restore_saving_for_reconciliation(self, entry_id: str) -> None:
        with self.audit_store._edit() as entries:
            entry = self.audit_store._entry(entries, entry_id, "RECOVERY_REQUIRED")
            entry["state"] = "SAVING"
            entry["updated_at"] = _now()

    def _recovery_required(self, entry_id: str) -> None:
        try:
            self.audit_store.mark_recovery_required(entry_id)
        except PhoneEntryError:
            pass


def _source_coin_id(package_path: str) -> str:
    try:
        import zipfile
        with zipfile.ZipFile(package_path) as archive:
            manifest = json.loads(archive.read("capture_package.json"))
        coins = manifest["coins"]
        if not isinstance(coins, list) or len(coins) != 1:
            raise ValueError("capture package must contain one coin")
        source_coin_id = coins[0]["id"]
        if not isinstance(source_coin_id, str) or not source_coin_id:
            raise ValueError("capture package source identity is invalid")
        return source_coin_id
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise PhoneEntryError("Capture package identity is unavailable.") from error


def _normalize_identity(values: Mapping[str, Any]) -> dict[str, str]:
    if set(values) != set(_IDENTITY_FIELDS):
        raise PhoneEntryStateError("Phone entry requires exactly the supported identity fields.")
    result = {field: str(values[field]).strip() for field in _IDENTITY_FIELDS}
    if any(not result[field] for field in _IDENTITY_FIELDS[:3]):
        raise PhoneEntryStateError("Country, denomination, and year require human values.")
    if any(len(value) > 255 for value in result.values()):
        raise PhoneEntryStateError("Phone-entry identity values are too long.")
    return result


def _draft_from_entry(entry: Mapping[str, Any]) -> PhoneEntryDraft:
    return PhoneEntryDraft(
        entry_id=str(entry["entry_id"]),
        pair_id=str(entry["pair_id"]),
        state=str(entry["state"]),
        media=tuple(sorted((str(role), str(digest)) for role, digest in entry["media"].items())),
        proposal=all_abstain_coin_field_proposal_set(str(entry["entry_id"])).to_dict() if entry.get("proposal") is None else dict(entry["proposal"]),
        human_final=tuple(sorted((str(field), str(value)) for field, value in entry["human_final"].items())),
        item_id="" if entry.get("item_id") is None else str(entry["item_id"]),
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
