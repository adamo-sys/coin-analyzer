"""Shared per-session context for workbook and WANT_LIST state."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, List, Optional

from legacy_portfolio_importer import LegacyPortfolioImporter


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


@dataclass
class LoadedCollectionContext:
    """Previewed collection workbook state for the current app session."""

    source_path: str
    item_count: int = 0
    rows_found: int = 0
    importable_count: int = 0
    duplicate_count: int = 0
    skipped_count: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    loaded_at: str = ""


@dataclass
class LoadedWantListContext:
    """Previewed WANT_LIST state for the current app session."""

    source_path: str
    want_list_count: int = 0
    intents: List[Any] = field(default_factory=list)
    rows_found: int = 0
    skipped_count: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    loaded_at: str = ""


@dataclass
class SessionLoadResult:
    """Result of loading or clearing shared session context."""

    success: bool
    status: str
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class SessionContext:
    """Shared runtime state used by GUI tools during a single app session."""

    loaded_collection: Optional[LoadedCollectionContext] = None
    loaded_want_list: Optional[LoadedWantListContext] = None
    last_loaded_at: str = ""
    load_status: str = "No collection context loaded"
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def loaded_collection_workbook_path(self) -> str:
        if self.loaded_collection:
            return self.loaded_collection.source_path
        if self.loaded_want_list:
            return self.loaded_want_list.source_path
        return ""

    @property
    def loaded_collection_item_count(self) -> int:
        return self.loaded_collection.item_count if self.loaded_collection else 0

    @property
    def want_list_count(self) -> int:
        return self.loaded_want_list.want_list_count if self.loaded_want_list else 0

    def has_want_list_context(self) -> bool:
        return bool(self.loaded_want_list and self.loaded_want_list.intents)

    def get_want_list_intents(self) -> List[Any]:
        if not self.loaded_want_list:
            return []
        return list(self.loaded_want_list.intents)

    def load_collection_context(
        self,
        workbook_path: str,
        existing_collection_items: Optional[Iterable[Any]] = None,
    ) -> SessionLoadResult:
        """Preview CORE_RAW/SLABS workbook rows into session state."""

        self._prepare_load()
        if not workbook_path or not os.path.exists(workbook_path):
            return self._fail(f"Workbook not found: {workbook_path}")

        loaded_at = _now_iso()
        try:
            importer = LegacyPortfolioImporter(existing_collection_items or [])
            summary = importer.preview_workbook(workbook_path)
            item_count = summary.items_importable + summary.duplicates_detected
            self.loaded_collection = LoadedCollectionContext(
                source_path=workbook_path,
                item_count=item_count,
                rows_found=summary.rows_found,
                importable_count=summary.items_importable,
                duplicate_count=summary.duplicates_detected,
                skipped_count=summary.rows_skipped,
                warnings=list(summary.warnings),
                loaded_at=loaded_at,
            )
            self.last_loaded_at = loaded_at
            self.warnings = list(summary.warnings)
            self.load_status = "Collection context loaded"
            return SessionLoadResult(True, self.load_status, warnings=list(self.warnings))
        except Exception as exc:
            return self._fail(f"Failed to load collection context: {exc}")

    def load_want_list_context(
        self,
        workbook_path: str,
        existing_collection_items: Optional[Iterable[Any]] = None,
    ) -> SessionLoadResult:
        """Preview workbook WANT_LIST rows into session state."""

        self._prepare_load(clear_collection=False)
        if not workbook_path or not os.path.exists(workbook_path):
            return self._fail(f"Workbook not found: {workbook_path}", clear_collection=False)

        loaded_at = _now_iso()
        try:
            importer = LegacyPortfolioImporter(existing_collection_items or [])
            preview = importer.preview_want_list(workbook_path)
            self.loaded_want_list = LoadedWantListContext(
                source_path=workbook_path,
                want_list_count=preview.intents_staged,
                intents=list(preview.staged_intents),
                rows_found=preview.rows_found,
                skipped_count=preview.rows_skipped,
                warnings=list(preview.warnings),
                loaded_at=loaded_at,
            )
            self.last_loaded_at = loaded_at
            self.warnings = list(preview.warnings)
            self.load_status = "WANT_LIST context loaded"
            return SessionLoadResult(True, self.load_status, warnings=list(self.warnings))
        except Exception as exc:
            return self._fail(f"Failed to load WANT_LIST context: {exc}", clear_collection=False)

    def load_workbook_context(
        self,
        workbook_path: str,
        existing_collection_items: Optional[Iterable[Any]] = None,
    ) -> SessionLoadResult:
        """Load collection preview and WANT_LIST preview from one workbook selection."""

        collection_result = self.load_collection_context(workbook_path, existing_collection_items)
        want_result = self.load_want_list_context(workbook_path, existing_collection_items)
        warnings = list(collection_result.warnings) + list(want_result.warnings)
        errors = list(collection_result.errors) + list(want_result.errors)
        success = collection_result.success or want_result.success
        if success:
            self.load_status = self.format_status_line()
        return SessionLoadResult(success, self.load_status, warnings=warnings, errors=errors)

    def clear(self) -> SessionLoadResult:
        self.loaded_collection = None
        self.loaded_want_list = None
        self.last_loaded_at = ""
        self.load_status = "No collection context loaded"
        self.warnings = []
        self.errors = []
        return SessionLoadResult(True, "Session context cleared")

    def format_status_line(self) -> str:
        if not self.loaded_collection and not self.loaded_want_list:
            return "Session context: none loaded"

        path = self.loaded_collection_workbook_path
        source = os.path.basename(path) if path else "unknown workbook"
        parts = [f"Session context: {source}"]
        if self.loaded_collection:
            parts.append(f"collection rows {self.loaded_collection.rows_found}")
            parts.append(f"items {self.loaded_collection.item_count}")
        if self.loaded_want_list:
            parts.append(f"WANT_LIST {self.loaded_want_list.want_list_count}")
        if self.last_loaded_at:
            parts.append(f"loaded {self.last_loaded_at}")
        return " | ".join(parts)

    def _prepare_load(self, clear_collection: bool = True) -> None:
        if clear_collection:
            self.loaded_collection = None
        self.warnings = []
        self.errors = []

    def _fail(self, error: str, clear_collection: bool = True) -> SessionLoadResult:
        if clear_collection:
            self.loaded_collection = None
        self.loaded_want_list = None
        self.errors = [error]
        self.warnings = []
        self.load_status = "Context load failed"
        return SessionLoadResult(False, self.load_status, errors=list(self.errors))
