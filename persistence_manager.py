"""Lightweight JSON persistence for app runtime state.

This module stores local application state only. It does not store credentials,
sync to cloud services, scrape listings, or modify collection workbooks.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from focused_collection_intelligence import CandidateItem
from legacy_portfolio_importer import LegacyWantListIntent
from listing_analyzer import ListingCandidate
from market_awareness import (
    AuctionRecord,
    MarketAwarenessEngine,
    ObservedPriceRecord,
    PurchaseRecord,
    SaleRecord,
)
from photo_vault import PhotoRecord
from session_context import (
    LoadedCollectionContext,
    LoadedWantListContext,
    SessionContext,
    SessionLoadResult,
)
from smart_shopping_assistant import ShoppingCandidate


APP_STATE_VERSION = "2.1"
DEFAULT_STATE_DIR = os.path.join("collection_data", "app_state")
DEFAULT_STATE_FILENAME = "app_state.json"


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _split_ids(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value or "").split(";") if part.strip()]


@dataclass
class AppState:
    """Structured state saved by PersistenceManager."""

    version: str = APP_STATE_VERSION
    saved_at: str = ""
    collection_workbook_path: str = ""
    want_list_path: str = ""
    want_list_source: str = ""
    session_context: Optional[SessionContext] = None
    market_awareness: MarketAwarenessEngine = field(default_factory=MarketAwarenessEngine)
    photo_records: List[PhotoRecord] = field(default_factory=list)
    shopping_candidates: List[ShoppingCandidate] = field(default_factory=list)
    app_preferences: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        market = self.market_awareness
        return {
            "version": self.version,
            "saved_at": self.saved_at,
            "collection_workbook_path": self.collection_workbook_path,
            "want_list_path": self.want_list_path,
            "want_list_source": self.want_list_source,
            "session_context": PersistenceManager.session_context_to_dict(self.session_context),
            "market_records": {
                "observations": [record.to_dict() for record in market.observations],
                "purchases": [record.to_dict() for record in market.purchases],
                "sales": [record.to_dict() for record in market.sales],
                "auctions": [record.to_dict() for record in market.auctions],
            },
            "photo_records": [record.to_dict() for record in self.photo_records],
            "shopping_candidates": [
                PersistenceManager.shopping_candidate_to_dict(candidate)
                for candidate in self.shopping_candidates
            ],
            "app_preferences": dict(self.app_preferences),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


@dataclass
class PersistenceResult:
    success: bool
    status: str
    state: Optional[AppState] = None
    path: str = ""
    backup_path: str = ""
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class PersistenceManager:
    """Save, load, validate, import, export, clear, and back up app state."""

    def __init__(
        self,
        state_dir: str = DEFAULT_STATE_DIR,
        state_filename: str = DEFAULT_STATE_FILENAME,
    ):
        self.state_dir = state_dir
        self.state_filename = state_filename
        self.state_path = os.path.join(self.state_dir, self.state_filename)
        self.backup_dir = os.path.join(self.state_dir, "backups")

    def save_state(self, state: AppState) -> PersistenceResult:
        """Save state to the default JSON file, backing up the previous file first."""

        try:
            os.makedirs(self.state_dir, exist_ok=True)
            backup_path = self.backup_state().backup_path if os.path.exists(self.state_path) else ""
            state.saved_at = state.saved_at or _now_iso()
            payload = state.to_dict()
            validation = self.validate_state(payload)
            warnings = list(validation.warnings)
            if not validation.success:
                return PersistenceResult(False, "State validation failed", state=state, path=self.state_path, backup_path=backup_path, warnings=warnings, errors=validation.errors)
            self._write_json(self.state_path, payload)
            return PersistenceResult(True, "State saved", state=state, path=self.state_path, backup_path=backup_path, warnings=warnings)
        except Exception as exc:
            return PersistenceResult(False, "State save failed", state=state, path=self.state_path, errors=[str(exc)])

    def load_state(self, path: Optional[str] = None) -> PersistenceResult:
        """Load state from JSON, returning empty state when no file exists."""

        target = path or self.state_path
        if not os.path.exists(target):
            return PersistenceResult(True, "No saved state found", state=AppState(), path=target, warnings=[f"State file not found: {target}"])
        try:
            with open(target, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            validation = self.validate_state(payload)
            if not validation.success:
                return PersistenceResult(False, "State validation failed", path=target, warnings=validation.warnings, errors=validation.errors)
            state = self.state_from_dict(payload)
            return PersistenceResult(True, "State loaded", state=state, path=target, warnings=validation.warnings)
        except json.JSONDecodeError as exc:
            return PersistenceResult(False, "State JSON is corrupt", path=target, errors=[str(exc)])
        except Exception as exc:
            return PersistenceResult(False, "State load failed", path=target, errors=[str(exc)])

    def clear_state(self) -> PersistenceResult:
        """Remove the default saved state after backing it up."""

        if not os.path.exists(self.state_path):
            return PersistenceResult(True, "No saved state to clear", path=self.state_path)
        backup = self.backup_state()
        try:
            os.remove(self.state_path)
            return PersistenceResult(True, "State cleared", path=self.state_path, backup_path=backup.backup_path, warnings=backup.warnings, errors=backup.errors)
        except Exception as exc:
            return PersistenceResult(False, "State clear failed", path=self.state_path, backup_path=backup.backup_path, errors=[str(exc)])

    def backup_state(self) -> PersistenceResult:
        """Create a timestamped backup of the current default state file."""

        if not os.path.exists(self.state_path):
            return PersistenceResult(True, "No state file to back up", path=self.state_path, warnings=[f"State file not found: {self.state_path}"])
        try:
            os.makedirs(self.backup_dir, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = os.path.join(self.backup_dir, f"app_state-{stamp}.json")
            shutil.copy2(self.state_path, backup_path)
            return PersistenceResult(True, "State backed up", path=self.state_path, backup_path=backup_path)
        except Exception as exc:
            return PersistenceResult(False, "State backup failed", path=self.state_path, errors=[str(exc)])

    def export_state(self, output_path: str, state: Optional[AppState] = None) -> PersistenceResult:
        """Export supplied or currently saved state to another JSON file."""

        try:
            export_state = state
            warnings = []
            if export_state is None:
                loaded = self.load_state()
                if not loaded.success:
                    return loaded
                export_state = loaded.state or AppState()
                warnings.extend(loaded.warnings)
            export_state.saved_at = export_state.saved_at or _now_iso()
            self._write_json(output_path, export_state.to_dict())
            return PersistenceResult(True, "State exported", state=export_state, path=output_path, warnings=warnings)
        except Exception as exc:
            return PersistenceResult(False, "State export failed", path=output_path, errors=[str(exc)])

    def import_state(self, input_path: str) -> PersistenceResult:
        """Validate and copy an external JSON state file into the app state location."""

        loaded = self.load_state(input_path)
        if not loaded.success:
            return loaded
        return self.save_state(loaded.state or AppState())

    def validate_state(self, payload: Any) -> PersistenceResult:
        """Validate the app-state schema lightly and report missing referenced files."""

        if not isinstance(payload, dict):
            return PersistenceResult(False, "Invalid state payload", errors=["State root must be a JSON object"])
        errors = []
        warnings = []
        if not isinstance(payload.get("version", ""), str):
            errors.append("version must be a string")
        market = payload.get("market_records", {})
        if market and not isinstance(market, dict):
            errors.append("market_records must be an object")
        for key in ["photo_records", "shopping_candidates", "warnings", "errors"]:
            if key in payload and not isinstance(payload.get(key), list):
                errors.append(f"{key} must be a list")
        for key in ["collection_workbook_path", "want_list_path"]:
            path = str(payload.get(key, "") or "")
            if path and not os.path.exists(path):
                warnings.append(f"Referenced file is missing: {path}")
        status = "State valid" if not errors else "State invalid"
        return PersistenceResult(not errors, status, warnings=warnings, errors=errors)

    def create_state(
        self,
        session_context: Optional[SessionContext] = None,
        market_awareness_engine: Optional[MarketAwarenessEngine] = None,
        photo_records: Optional[Iterable[PhotoRecord]] = None,
        shopping_candidates: Optional[Iterable[ShoppingCandidate]] = None,
        app_preferences: Optional[Dict[str, Any]] = None,
    ) -> AppState:
        """Build AppState from current runtime objects."""

        session = session_context or SessionContext()
        workbook_path = session.loaded_collection.source_path if session.loaded_collection else session.loaded_collection_workbook_path
        want_path = session.loaded_want_list.source_path if session.loaded_want_list else ""
        return AppState(
            saved_at=_now_iso(),
            collection_workbook_path=workbook_path,
            want_list_path=want_path,
            want_list_source=os.path.basename(want_path) if want_path else "",
            session_context=session,
            market_awareness=market_awareness_engine or MarketAwarenessEngine(),
            photo_records=list(photo_records or []),
            shopping_candidates=list(shopping_candidates or []),
            app_preferences=dict(app_preferences or {}),
            warnings=list(getattr(session, "warnings", []) or []),
            errors=list(getattr(session, "errors", []) or []),
        )

    def restore_session_context(
        self,
        state: AppState,
        existing_collection_items: Optional[Iterable[Any]] = None,
        reload_workbook: bool = True,
    ) -> SessionLoadResult:
        """Restore session context from saved metadata, reloading workbook if present."""

        if reload_workbook and state.collection_workbook_path and os.path.exists(state.collection_workbook_path):
            context = SessionContext()
            return context.load_workbook_context(state.collection_workbook_path, existing_collection_items)
        if state.session_context:
            return SessionLoadResult(True, "Session context restored from saved metadata", warnings=list(state.warnings))
        if state.collection_workbook_path and not os.path.exists(state.collection_workbook_path):
            return SessionLoadResult(False, "Saved workbook path is missing", errors=[f"Workbook not found: {state.collection_workbook_path}"])
        return SessionLoadResult(True, "No session context to restore")

    @staticmethod
    def state_from_dict(payload: Dict[str, Any]) -> AppState:
        market = payload.get("market_records", {}) or {}
        session_context = PersistenceManager.session_context_from_dict(payload.get("session_context") or {})
        return AppState(
            version=str(payload.get("version") or APP_STATE_VERSION),
            saved_at=str(payload.get("saved_at") or ""),
            collection_workbook_path=str(payload.get("collection_workbook_path") or ""),
            want_list_path=str(payload.get("want_list_path") or ""),
            want_list_source=str(payload.get("want_list_source") or ""),
            session_context=session_context,
            market_awareness=MarketAwarenessEngine(
                observations=[PersistenceManager.observation_from_dict(row) for row in market.get("observations", [])],
                purchases=[PersistenceManager.purchase_from_dict(row) for row in market.get("purchases", [])],
                sales=[PersistenceManager.sale_from_dict(row) for row in market.get("sales", [])],
                auctions=[PersistenceManager.auction_from_dict(row) for row in market.get("auctions", [])],
            ),
            photo_records=[PersistenceManager.photo_record_from_dict(row) for row in payload.get("photo_records", [])],
            shopping_candidates=[PersistenceManager.shopping_candidate_from_dict(row) for row in payload.get("shopping_candidates", [])],
            app_preferences=dict(payload.get("app_preferences") or {}),
            warnings=list(payload.get("warnings") or []),
            errors=list(payload.get("errors") or []),
        )

    @staticmethod
    def session_context_to_dict(context: Optional[SessionContext]) -> Dict[str, Any]:
        if not context:
            return {}
        loaded_collection = None
        if context.loaded_collection:
            loaded_collection = {
                "source_path": context.loaded_collection.source_path,
                "item_count": context.loaded_collection.item_count,
                "rows_found": context.loaded_collection.rows_found,
                "importable_count": context.loaded_collection.importable_count,
                "duplicate_count": context.loaded_collection.duplicate_count,
                "skipped_count": context.loaded_collection.skipped_count,
                "warnings": list(context.loaded_collection.warnings),
                "errors": list(context.loaded_collection.errors),
                "loaded_at": context.loaded_collection.loaded_at,
            }
        loaded_want_list = None
        if context.loaded_want_list:
            loaded_want_list = {
                "source_path": context.loaded_want_list.source_path,
                "want_list_count": context.loaded_want_list.want_list_count,
                "intents": [intent.to_dict() if hasattr(intent, "to_dict") else dict(intent) for intent in context.loaded_want_list.intents],
                "rows_found": context.loaded_want_list.rows_found,
                "skipped_count": context.loaded_want_list.skipped_count,
                "warnings": list(context.loaded_want_list.warnings),
                "errors": list(context.loaded_want_list.errors),
                "loaded_at": context.loaded_want_list.loaded_at,
            }
        return {
            "loaded_collection": loaded_collection,
            "loaded_want_list": loaded_want_list,
            "last_loaded_at": context.last_loaded_at,
            "load_status": context.load_status,
            "warnings": list(context.warnings),
            "errors": list(context.errors),
        }

    @staticmethod
    def session_context_from_dict(payload: Dict[str, Any]) -> SessionContext:
        context = SessionContext()
        if not payload:
            return context
        loaded_collection = payload.get("loaded_collection") or None
        if loaded_collection:
            context.loaded_collection = LoadedCollectionContext(
                source_path=str(loaded_collection.get("source_path") or ""),
                item_count=int(loaded_collection.get("item_count") or 0),
                rows_found=int(loaded_collection.get("rows_found") or 0),
                importable_count=int(loaded_collection.get("importable_count") or 0),
                duplicate_count=int(loaded_collection.get("duplicate_count") or 0),
                skipped_count=int(loaded_collection.get("skipped_count") or 0),
                warnings=list(loaded_collection.get("warnings") or []),
                errors=list(loaded_collection.get("errors") or []),
                loaded_at=str(loaded_collection.get("loaded_at") or ""),
            )
        loaded_want_list = payload.get("loaded_want_list") or None
        if loaded_want_list:
            intents = [PersistenceManager.intent_from_dict(row) for row in loaded_want_list.get("intents", [])]
            context.loaded_want_list = LoadedWantListContext(
                source_path=str(loaded_want_list.get("source_path") or ""),
                want_list_count=int(loaded_want_list.get("want_list_count") or len(intents)),
                intents=intents,
                rows_found=int(loaded_want_list.get("rows_found") or 0),
                skipped_count=int(loaded_want_list.get("skipped_count") or 0),
                warnings=list(loaded_want_list.get("warnings") or []),
                errors=list(loaded_want_list.get("errors") or []),
                loaded_at=str(loaded_want_list.get("loaded_at") or ""),
            )
        context.last_loaded_at = str(payload.get("last_loaded_at") or "")
        context.load_status = str(payload.get("load_status") or context.format_status_line())
        context.warnings = list(payload.get("warnings") or [])
        context.errors = list(payload.get("errors") or [])
        return context

    @staticmethod
    def intent_from_dict(row: Dict[str, Any]) -> LegacyWantListIntent:
        return LegacyWantListIntent(
            sheet_name=str(row.get("sheet_name") or "WANT_LIST"),
            row_number=int(row.get("row_number") or 0),
            legacy_id=str(row.get("legacy_id") or ""),
            target_coin=str(row.get("target_coin") or ""),
            priority=str(row.get("priority") or ""),
            target_grade=str(row.get("target_grade") or ""),
            budget=float(row.get("budget") or 0.0),
            why_wanted=str(row.get("why_wanted") or ""),
            status=str(row.get("status") or ""),
            priority_score=int(row.get("priority_score") or 0),
            warnings=list(row.get("warnings") or []),
        )

    @staticmethod
    def observation_from_dict(row: Dict[str, Any]) -> ObservedPriceRecord:
        return ObservedPriceRecord(
            item_name=str(row.get("item_name") or ""),
            country=str(row.get("country") or ""),
            denomination=str(row.get("denomination") or ""),
            year=str(row.get("year") or ""),
            grade=str(row.get("grade") or ""),
            observed_price=float(row.get("observed_price") or 0.0),
            shipping=float(row.get("shipping") or 0.0),
            source=str(row.get("source") or ""),
            date_observed=str(row.get("date_observed") or ""),
            notes=str(row.get("notes") or ""),
            linked_photo_ids=_split_ids(row.get("linked_photo_ids")),
        )

    @staticmethod
    def purchase_from_dict(row: Dict[str, Any]) -> PurchaseRecord:
        return PurchaseRecord(
            item=str(row.get("item") or ""),
            purchase_price=float(row.get("purchase_price") or 0.0),
            shipping=float(row.get("shipping") or 0.0),
            seller=str(row.get("seller") or ""),
            source=str(row.get("source") or ""),
            purchase_date=str(row.get("purchase_date") or ""),
            notes=str(row.get("notes") or ""),
            country=str(row.get("country") or ""),
            denomination=str(row.get("denomination") or ""),
            year=str(row.get("year") or ""),
            grade=str(row.get("grade") or ""),
            linked_photo_ids=_split_ids(row.get("linked_photo_ids")),
        )

    @staticmethod
    def sale_from_dict(row: Dict[str, Any]) -> SaleRecord:
        return SaleRecord(
            item=str(row.get("item") or ""),
            sale_price=float(row.get("sale_price") or 0.0),
            fees=float(row.get("fees") or 0.0),
            buyer_source=str(row.get("buyer_source") or ""),
            sale_date=str(row.get("sale_date") or ""),
            notes=str(row.get("notes") or ""),
            country=str(row.get("country") or ""),
            denomination=str(row.get("denomination") or ""),
            year=str(row.get("year") or ""),
            grade=str(row.get("grade") or ""),
            linked_photo_ids=_split_ids(row.get("linked_photo_ids")),
        )

    @staticmethod
    def auction_from_dict(row: Dict[str, Any]) -> AuctionRecord:
        return AuctionRecord(
            item=str(row.get("item") or ""),
            bid_amount=float(row.get("bid_amount") or 0.0),
            winning_bid=float(row.get("winning_bid") or 0.0),
            auction_result=str(row.get("auction_result") or "Passed"),
            source=str(row.get("source") or ""),
            auction_date=str(row.get("auction_date") or ""),
            notes=str(row.get("notes") or ""),
            country=str(row.get("country") or ""),
            denomination=str(row.get("denomination") or ""),
            year=str(row.get("year") or ""),
            grade=str(row.get("grade") or ""),
            linked_photo_ids=_split_ids(row.get("linked_photo_ids")),
        )

    @staticmethod
    def photo_record_from_dict(row: Dict[str, Any]) -> PhotoRecord:
        return PhotoRecord(
            file_path=str(row.get("file_path") or ""),
            photo_type=str(row.get("photo_type") or "Reference Photo"),
            linked_collection_item_id=str(row.get("linked_collection_item_id") or ""),
            linked_candidate_id=str(row.get("linked_candidate_id") or ""),
            linked_coin_name=str(row.get("linked_coin_name") or ""),
            created_date=str(row.get("created_date") or ""),
            notes=str(row.get("notes") or ""),
            iccs_number=str(row.get("iccs_number") or ""),
            pcgs_number=str(row.get("pcgs_number") or ""),
            ngc_number=str(row.get("ngc_number") or ""),
        )

    @staticmethod
    def shopping_candidate_to_dict(candidate: ShoppingCandidate) -> Dict[str, Any]:
        data = candidate.to_dict()
        data["photo_reference_ids"] = list(candidate.photo_reference_ids)
        if candidate.candidate:
            data["candidate"] = candidate.candidate.__dict__.copy()
        if candidate.listing:
            data["listing"] = candidate.listing.to_dict()
        return data

    @staticmethod
    def shopping_candidate_from_dict(row: Dict[str, Any]) -> ShoppingCandidate:
        candidate = None
        if row.get("candidate"):
            candidate = CandidateItem(**{
                key: value
                for key, value in row["candidate"].items()
                if key in CandidateItem.__dataclass_fields__
            })
        listing = None
        if row.get("listing"):
            listing_data = {
                key: value
                for key, value in row["listing"].items()
                if key in ListingCandidate.__dataclass_fields__ and key != "total_cost"
            }
            listing = ListingCandidate(**listing_data)
        return ShoppingCandidate(
            item_name=str(row.get("item_name") or ""),
            source=str(row.get("source") or ""),
            asking_price=float(row.get("asking_price") or 0.0),
            shipping=float(row.get("shipping") or 0.0),
            recommendation_source=str(row.get("recommendation_source") or "Manual"),
            notes=str(row.get("notes") or ""),
            url=str(row.get("url") or ""),
            seller=str(row.get("seller") or ""),
            candidate=candidate,
            listing=listing,
            want_list_priority=int(row.get("want_list_priority") or 0),
            photo_reference_ids=_split_ids(row.get("photo_reference_ids")),
        )

    @staticmethod
    def _write_json(path: str, payload: Dict[str, Any]) -> None:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
