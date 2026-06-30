"""
Connected Data Engine — v8.4 Phase 1

Thin cross-reference facade that connects existing engine outputs without
computing, scoring, ranking, grading, pricing, or persisting.

OWNERSHIP BOUNDARIES
====================

OWNED BY ConnectedDataEngine:
    - Connection (dataclass)
    - ConnectedReport (dataclass)
    - CrossReferenceReport (dataclass)
    - ConnectionSummary (dataclass)
    - MatchType (enum)
    - ConnectionType (enum)
    - _DISPATCH_TABLE (class-level constant)
    - Matching logic (exact, fuzzy, derived)
    - generate_summary() derivation logic

BORROWED FROM ConnectedContext:
    - photo_records (owned by PhotoVault)
    - ocr_reports (owned by OCRExperiment)
    - grading_assessments (owned by AIGradingAssistant)
    - market_records (owned by MarketAwarenessEngine)
    - shopping_candidates (owned by SmartShoppingAssistant)
    - want_list_intents (owned by SessionContext / importer)
    - watchlists (owned by WatchlistEngine)
    - workflow_statuses (owned by CollectorWorkflowEngine)
    - batch_candidates (owned by BatchProcessingEngine)
    - collection_items (owned by CoinCollection)
    - session_context (owned by SessionContext)
    - photo_candidates (owned by Photo-Assisted Entry)
    - acknowledged_action_ids (owned by CollectorHomeDashboard)

NEVER OWNED:
    - Collection data
    - Engine outputs
    - Photo files
    - Market data
    - Any business logic

Constraints:
    - No persistence (no JSON, no database, no new storage format)
    - No mutation (read-only cross-referencing)
    - No scoring / ranking / grading / pricing / deciding
    - No duplicated business logic
    - No ML, no computer vision, no cloud
    - Deterministic matching only (exact, fuzzy by country/denom/year, derived)
    - Fuzzy matching: exact year only (no tolerance)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ConnectionType(Enum):
    """Valid connection types for cross-referencing.
    
    These are the only types that can be passed to connect().
    Invalid types raise ValueError immediately.
    """
    PHOTO = "photo"
    OCR = "ocr"
    GRADING = "grading"
    INTELLIGENCE = "intelligence"
    MARKET = "market"
    WATCHLIST = "watchlist"
    BATCH = "batch"
    SHOPPING = "shopping"
    WANT_LIST = "want_list"
    ENTRY = "entry"
    DEAL = "deal"
    ACQUISITION = "acquisition"


class MatchType(Enum):
    """How two records were matched. Deterministic only."""
    EXACT = "exact"       # certification number, ID, or photo path exact match
    FUZZY = "fuzzy"       # country + denomination + exact year match
    DERIVED = "derived"   # one record derived from another (e.g., OCR → grading)
    NONE = "none"         # no match found


# ---------------------------------------------------------------------------
# DTOs (dataclasses)
# ---------------------------------------------------------------------------

@dataclass
class Connection:
    """A single cross-reference between two records from different engines.
    
    Pure metadata. No computed scores. No business logic.
    """
    source_type: str
    target_type: str
    source_id: str
    target_id: str
    match_type: MatchType
    match_key: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class ConnectedReport:
    """Summary of cross-references between two data types."""
    source_type: str
    target_type: str
    total_source: int
    total_target: int
    connections: List[Connection] = field(default_factory=list)
    unmatched_sources: List[str] = field(default_factory=list)
    unmatched_targets: List[str] = field(default_factory=list)
    
    @property
    def match_count(self) -> int:
        return len(self.connections)
    
    @property
    def match_rate(self) -> float:
        if self.total_source == 0:
            return 0.0
        return self.match_count / self.total_source


@dataclass
class CrossReferenceReport:
    """Complete summary of all cross-references in the system."""
    reports: List[ConnectedReport] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def by_source_target(self, source_type: str, target_type: str) -> Optional[ConnectedReport]:
        for report in self.reports:
            if report.source_type == source_type and report.target_type == target_type:
                return report
        return None


@dataclass
class ConnectionSummary:
    """Dashboard DTO with connection counts per source type.
    
    Derived from CrossReferenceReport. No new queries.
    """
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Photos
    total_photos: int = 0
    photos_linked: int = 0
    photos_unmatched: int = 0
    
    # OCR
    total_ocr: int = 0
    ocr_linked: int = 0
    ocr_unmatched: int = 0
    
    # Grading
    total_grading: int = 0
    grading_linked: int = 0
    grading_unmatched: int = 0
    
    # Intelligence
    total_intelligence: int = 0
    intelligence_linked: int = 0
    intelligence_unmatched: int = 0
    
    # Batch
    total_batch: int = 0
    batch_linked: int = 0
    batch_unmatched: int = 0
    
    # Market
    total_market: int = 0
    market_linked: int = 0
    market_unmatched: int = 0
    
    # Watchlist
    total_watchlist: int = 0
    watchlist_linked: int = 0
    watchlist_unmatched: int = 0
    
    @property
    def overall_link_rate(self) -> float:
        total = (self.total_photos + self.total_ocr + self.total_grading +
                self.total_intelligence + self.total_batch + 
                self.total_market + self.total_watchlist)
        linked = (self.photos_linked + self.ocr_linked + self.grading_linked +
                 self.intelligence_linked + self.batch_linked +
                 self.market_linked + self.watchlist_linked)
        if total == 0:
            return 0.0
        return linked / total


@dataclass
class ConnectedContext:
    """Shared references to all active data sources. No copies. No persistence.
    
    Mirrors CollectorWorkspace constructor parameters exactly.
    One field per workspace parameter — no standalone context fields.
    """
    collection_items: List[Any]
    photo_records: Optional[List[Any]] = None
    ocr_reports: Optional[List[Any]] = None
    grading_assessments: Optional[List[Any]] = None
    market_records: Optional[List[Any]] = None
    shopping_candidates: Optional[List[Any]] = None
    want_list_intents: Optional[List[Any]] = None
    watchlists: Optional[List[Any]] = None
    workflow_statuses: Optional[List[Any]] = None
    session_context: Optional[Any] = None
    photo_candidates: Optional[List[Any]] = None
    acknowledged_action_ids: Optional[List[str]] = None
    batch_candidates: Optional[List[Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for passing between engines. Stores counts only."""
        return {
            "collection_item_count": len(self.collection_items) if self.collection_items else 0,
            "photo_record_count": len(self.photo_records) if self.photo_records else 0,
            "ocr_report_count": len(self.ocr_reports) if self.ocr_reports else 0,
            "grading_assessment_count": len(self.grading_assessments) if self.grading_assessments else 0,
            "market_record_count": len(self.market_records) if self.market_records else 0,
            "shopping_candidate_count": len(self.shopping_candidates) if self.shopping_candidates else 0,
            "want_list_intent_count": len(self.want_list_intents) if self.want_list_intents else 0,
            "watchlist_count": len(self.watchlists) if self.watchlists else 0,
            "workflow_status_count": len(self.workflow_statuses) if self.workflow_statuses else 0,
            "photo_candidate_count": len(self.photo_candidates) if self.photo_candidates else 0,
            "batch_candidate_count": len(self.batch_candidates) if self.batch_candidates else 0,
            "acknowledged_action_count": len(self.acknowledged_action_ids) if self.acknowledged_action_ids else 0,
        }
    
    @property
    def analysis_context(self) -> Dict[str, Any]:
        """OCR + grading + intelligence — analysis-related context."""
        return {
            "ocr_reports": self.ocr_reports,
            "grading_assessments": self.grading_assessments,
        }
    
    @property
    def shopping_context(self) -> Dict[str, Any]:
        """Shopping + deals + watchlist — acquisition-related context."""
        return {
            "shopping_candidates": self.shopping_candidates,
            "want_list_intents": self.want_list_intents,
            "watchlists": self.watchlists,
        }


# ---------------------------------------------------------------------------
# ConnectedDataEngine — thin cross-reference facade
# ---------------------------------------------------------------------------

class ConnectedDataEngine:
    """Thin cross-reference facade.
    
    Public API: 3 methods
    Private dispatch: 12 methods
    
    OWNERSHIP BOUNDARIES
    ====================
    
    OWNED BY ConnectedDataEngine:
        - Connection, ConnectedReport, CrossReferenceReport, ConnectionSummary
        - MatchType, ConnectionType
        - _DISPATCH_TABLE
        - Matching logic (exact, fuzzy, derived)
    
    BORROWED FROM ConnectedContext:
        - All record lists (photos, OCR, grading, market, etc.)
    
    NEVER OWNED:
        - Collection data, engine outputs, photo files, market data, business logic
    """
    
    # -- Class-level dispatch table (initialized once) -----------------------
    
    _DISPATCH_TABLE: Dict[Tuple[ConnectionType, ConnectionType], str] = {
        (ConnectionType.PHOTO, ConnectionType.GRADING): "_connect_photos_to_grading",
        (ConnectionType.PHOTO, ConnectionType.OCR): "_connect_photos_to_ocr",
        (ConnectionType.PHOTO, ConnectionType.BATCH): "_connect_photos_to_batch",
        (ConnectionType.OCR, ConnectionType.GRADING): "_connect_ocr_to_grading",
        (ConnectionType.OCR, ConnectionType.ENTRY): "_connect_ocr_to_entry",
        (ConnectionType.INTELLIGENCE, ConnectionType.SHOPPING): "_connect_intelligence_to_shopping",
        (ConnectionType.INTELLIGENCE, ConnectionType.WANT_LIST): "_connect_intelligence_to_want_list",
        (ConnectionType.MARKET, ConnectionType.ACQUISITION): "_connect_market_to_acquisition",
        (ConnectionType.WATCHLIST, ConnectionType.DEAL): "_connect_watchlist_to_deals",
        (ConnectionType.WATCHLIST, ConnectionType.SHOPPING): "_connect_watchlist_to_shopping",
        (ConnectionType.BATCH, ConnectionType.GRADING): "_connect_batch_to_grading",
        (ConnectionType.BATCH, ConnectionType.ENTRY): "_connect_batch_to_entry",
    }
    
    def __init__(self, context: ConnectedContext):
        self._context = context
    
    # -- Public API (3 methods) --------------------------------------------
    
    def connect(self, source_type: ConnectionType, target_type: ConnectionType) -> ConnectedReport:
        """Cross-reference two data types.
        
        Args:
            source_type: The source data type (e.g., ConnectionType.PHOTO)
            target_type: The target data type (e.g., ConnectionType.GRADING)
        
        Returns:
            ConnectedReport with all matches between source and target.
        
        Raises:
            ValueError: If source_type or target_type is not a ConnectionType.
        """
        if not isinstance(source_type, ConnectionType):
            raise ValueError(
                f"source_type must be a ConnectionType, got {type(source_type).__name__}"
            )
        if not isinstance(target_type, ConnectionType):
            raise ValueError(
                f"target_type must be a ConnectionType, got {type(target_type).__name__}"
            )
        
        key = (source_type, target_type)
        if key not in self._DISPATCH_TABLE:
            return ConnectedReport(
                source_type=source_type.value,
                target_type=target_type.value,
                total_source=0,
                total_target=0,
            )
        
        method_name = self._DISPATCH_TABLE[key]
        method = getattr(self, method_name)
        return method()
    
    def generate_cross_reference_report(self) -> CrossReferenceReport:
        """Generate a complete summary of all cross-references.
        
        Calls connect() for all supported source/target pairs.
        """
        reports = []
        for (source, target) in self._DISPATCH_TABLE.keys():
            reports.append(self.connect(source, target))
        return CrossReferenceReport(reports=reports)
    
    def generate_summary(self) -> ConnectionSummary:
        """Generate a dashboard summary of all connections.
        
        Derived from generate_cross_reference_report(). No new queries.
        """
        report = self.generate_cross_reference_report()
        return self._build_summary(report)
    
    # -- Private dispatch methods (12 methods) -----------------------------
    
    def _connect_photos_to_grading(self) -> ConnectedReport:
        """Match photo records to grading assessments by photo reference path.
        
        MatchType.EXACT when a grading assessment's photo_references contains
        a photo_record's file_path.
        """
        sources = self._context.photo_records or []
        targets = self._context.grading_assessments or []
        
        def photo_key(photo):
            return getattr(photo, "file_path", "") or getattr(photo, "path", "")
        
        def grading_key(grading):
            refs = getattr(grading, "photo_references", []) or []
            return tuple(refs) if refs else ("",)
        
        connections = self._match_exact_multi_target(sources, targets, photo_key, grading_key)
        
        return self._build_report("photo", "grading", sources, targets, connections)
    
    def _connect_photos_to_ocr(self) -> ConnectedReport:
        """Match photo records to OCR reports by image path.
        
        MatchType.EXACT when an OCR report's image_path matches a photo_record's file_path.
        MatchType.DERIVED when OCR was run on a photo from the vault.
        """
        sources = self._context.photo_records or []
        targets = self._context.ocr_reports or []
        
        def photo_key(photo):
            return getattr(photo, "file_path", "") or getattr(photo, "path", "")
        
        def ocr_key(ocr):
            return getattr(ocr, "image_path", "") or getattr(ocr, "file_path", "")
        
        connections = self._match_exact(sources, targets, photo_key, ocr_key, MatchType.DERIVED)
        
        return self._build_report("photo", "ocr", sources, targets, connections)
    
    def _connect_photos_to_batch(self) -> ConnectedReport:
        """Match photo records to batch candidates by photo path.
        
        MatchType.EXACT when a batch candidate's front_path or back_path matches
        a photo_record's file_path.
        """
        sources = self._context.photo_records or []
        targets = self._context.batch_candidates or []
        
        def photo_key(photo):
            return getattr(photo, "file_path", "") or getattr(photo, "path", "")
        
        def batch_key(batch):
            paths = []
            front = getattr(batch, "front_path", None)
            back = getattr(batch, "back_path", None)
            if front:
                paths.append(front)
            if back:
                paths.append(back)
            return tuple(paths) if paths else ("",)
        
        connections = self._match_exact_multi_target(sources, targets, photo_key, batch_key)
        
        return self._build_report("photo", "batch", sources, targets, connections)
    
    def _connect_ocr_to_grading(self) -> ConnectedReport:
        """Match OCR candidates to grading assessments by country/denomination/year.
        
        MatchType.FUZZY when country + denomination + year match exactly.
        MatchType.DERIVED when grading was created from an OCR candidate.
        """
        sources = self._extract_ocr_candidates()
        targets = self._context.grading_assessments or []
        
        connections = self._match_fuzzy(
            sources, targets,
            self._extract_country_denom_year,
            self._extract_country_denom_year
        )
        
        # Also check derived links (grading created from OCR)
        for ocr in sources:
            ocr_id = self._extract_id(ocr)
            for grading in targets:
                grading_id = self._extract_id(grading)
                ocr_source = getattr(grading, "ocr_source", None)
                if ocr_source and ocr_source == ocr_id:
                    # Add DERIVED connection if not already present
                    existing = [c for c in connections 
                               if c.source_id == ocr_id and c.target_id == grading_id]
                    if not existing:
                        connections.append(Connection(
                            source_type="ocr",
                            target_type="grading",
                            source_id=ocr_id,
                            target_id=grading_id,
                            match_type=MatchType.DERIVED,
                            match_key=f"ocr_source:{ocr_id}",
                            notes="Grading created from OCR candidate",
                        ))
        
        return self._build_report("ocr", "grading", sources, targets, connections)
    
    def _connect_ocr_to_entry(self) -> ConnectedReport:
        """Match OCR candidates to collection entry candidates by country/denomination/year.
        
        MatchType.FUZZY when country + denomination + year match exactly.
        """
        sources = self._extract_ocr_candidates()
        targets = self._extract_entry_candidates()
        
        connections = self._match_fuzzy(
            sources, targets,
            self._extract_country_denom_year,
            self._extract_country_denom_year
        )
        
        return self._build_report("ocr", "entry", sources, targets, connections)
    
    def _connect_intelligence_to_shopping(self) -> ConnectedReport:
        """Match collection intelligence targets (gaps, upgrades) to shopping candidates.
        
        MatchType.FUZZY when country + denomination + year match exactly.
        """
        sources = self._extract_intelligence_targets()
        targets = self._context.shopping_candidates or []
        
        connections = self._match_fuzzy(
            sources, targets,
            self._extract_country_denom_year,
            self._extract_country_denom_year
        )
        
        return self._build_report("intelligence", "shopping", sources, targets, connections)
    
    def _connect_intelligence_to_want_list(self) -> ConnectedReport:
        """Match collection intelligence gaps to want list intents.
        
        MatchType.EXACT when country + denomination + year match exactly.
        """
        sources = self._extract_intelligence_targets()
        targets = self._context.want_list_intents or []
        
        connections = self._match_fuzzy(
            sources, targets,
            self._extract_country_denom_year,
            self._extract_country_denom_year
        )
        
        return self._build_report("intelligence", "want_list", sources, targets, connections)
    
    def _connect_market_to_acquisition(self) -> ConnectedReport:
        """Match historical market records to acquisition candidates.
        
        MatchType.FUZZY when country + denomination match; year optional.
        """
        sources = self._context.market_records or []
        targets = self._extract_acquisition_candidates()
        
        # Market records match by country + denomination (year optional)
        def market_key(record):
            country = getattr(record, "country", "") or ""
            denom = getattr(record, "denomination", "") or ""
            return (country.lower().strip(), denom.lower().strip())
        
        def acq_key(record):
            country = getattr(record, "country", "") or ""
            denom = getattr(record, "denomination", "") or ""
            return (country.lower().strip(), denom.lower().strip())
        
        connections = self._match_fuzzy_2tuple(sources, targets, market_key, acq_key)
        
        return self._build_report("market", "acquisition", sources, targets, connections)
    
    def _connect_watchlist_to_deals(self) -> ConnectedReport:
        """Match watchlist entries to deal candidates.
        
        MatchType.FUZZY when watchlist keyword matches deal title or description.
        """
        sources = self._context.watchlists or []
        targets = self._extract_deal_candidates()
        
        def watchlist_key(watch):
            keyword = getattr(watch, "keyword", "") or getattr(watch, "name", "") or ""
            return keyword.lower().strip()
        
        def deal_key(deal):
            title = getattr(deal, "title", "") or ""
            desc = getattr(deal, "description", "") or ""
            return f"{title} {desc}".lower().strip()
        
        connections = self._match_keyword(sources, targets, watchlist_key, deal_key)
        
        return self._build_report("watchlist", "deal", sources, targets, connections)
    
    def _connect_watchlist_to_shopping(self) -> ConnectedReport:
        """Match watchlist entries to shopping candidates.
        
        MatchType.FUZZY when watchlist keyword matches shopping candidate title.
        """
        sources = self._context.watchlists or []
        targets = self._context.shopping_candidates or []
        
        def watchlist_key(watch):
            keyword = getattr(watch, "keyword", "") or getattr(watch, "name", "") or ""
            return keyword.lower().strip()
        
        def shopping_key(candidate):
            title = getattr(candidate, "title", "") or ""
            country = getattr(candidate, "country", "") or ""
            denom = getattr(candidate, "denomination", "") or ""
            return f"{title} {country} {denom}".lower().strip()
        
        connections = self._match_keyword(sources, targets, watchlist_key, shopping_key)
        
        return self._build_report("watchlist", "shopping", sources, targets, connections)
    
    def _connect_batch_to_grading(self) -> ConnectedReport:
        """Match batch candidates to grading assessments.
        
        MatchType.EXACT when batch candidate has a linked grading_assessment_id.
        MatchType.FUZZY when country + denomination + year match.
        """
        sources = self._context.batch_candidates or []
        targets = self._context.grading_assessments or []
        
        connections = []
        
        # Exact match by linked grading ID
        for batch in sources:
            batch_id = self._extract_id(batch)
            linked_id = getattr(batch, "grading_assessment_id", None)
            if linked_id:
                for grading in targets:
                    grading_id = self._extract_id(grading)
                    if grading_id == linked_id:
                        connections.append(Connection(
                            source_type="batch",
                            target_type="grading",
                            source_id=batch_id,
                            target_id=grading_id,
                            match_type=MatchType.EXACT,
                            match_key=f"grading_assessment_id:{linked_id}",
                            notes="Batch candidate linked to grading assessment",
                        ))
        
        # Fuzzy match by country/denom/year
        fuzzy_connections = self._match_fuzzy(
            sources, targets,
            self._extract_country_denom_year,
            self._extract_country_denom_year
        )
        
        # Add fuzzy connections that aren't already exact-matched
        existing_pairs = {(c.source_id, c.target_id) for c in connections}
        for fc in fuzzy_connections:
            if (fc.source_id, fc.target_id) not in existing_pairs:
                connections.append(fc)
        
        return self._build_report("batch", "grading", sources, targets, connections)
    
    def _connect_batch_to_entry(self) -> ConnectedReport:
        """Match batch candidates to collection entry candidates.
        
        MatchType.DERIVED when batch candidate was approved for entry.
        MatchType.FUZZY when country + denomination + year match.
        """
        sources = self._context.batch_candidates or []
        targets = self._extract_entry_candidates()
        
        connections = []
        
        # Derived match by entry status
        for batch in sources:
            batch_id = self._extract_id(batch)
            entry_status = getattr(batch, "entry_status", None)
            if entry_status == "approved":
                entry_id = getattr(batch, "entry_candidate_id", None)
                if entry_id:
                    connections.append(Connection(
                        source_type="batch",
                        target_type="entry",
                        source_id=batch_id,
                        target_id=entry_id,
                        match_type=MatchType.DERIVED,
                        match_key=f"entry_status:approved",
                        notes="Batch candidate approved for collection entry",
                    ))
        
        # Fuzzy match by country/denom/year
        fuzzy_connections = self._match_fuzzy(
            sources, targets,
            self._extract_country_denom_year,
            self._extract_country_denom_year
        )
        
        existing_pairs = {(c.source_id, c.target_id) for c in connections}
        for fc in fuzzy_connections:
            if (fc.source_id, fc.target_id) not in existing_pairs:
                connections.append(fc)
        
        return self._build_report("batch", "entry", sources, targets, connections)
    
    # -- Private helpers ---------------------------------------------------
    
    def _build_summary(self, report: CrossReferenceReport) -> ConnectionSummary:
        """Build ConnectionSummary from CrossReferenceReport.
        
        Totals use max() since total_source is the same across all reports
        of the same source_type. Linked counts accumulate across reports.
        """
        summary = ConnectionSummary()
        
        for r in report.reports:
            if r.source_type == "photo":
                summary.total_photos = max(summary.total_photos, r.total_source)
                summary.photos_linked += r.match_count
                summary.photos_unmatched += len(r.unmatched_sources)
            elif r.source_type == "ocr":
                summary.total_ocr = max(summary.total_ocr, r.total_source)
                summary.ocr_linked += r.match_count
                summary.ocr_unmatched += len(r.unmatched_sources)
            elif r.source_type == "intelligence":
                summary.total_intelligence = max(summary.total_intelligence, r.total_source)
                summary.intelligence_linked += r.match_count
                summary.intelligence_unmatched += len(r.unmatched_sources)
            elif r.source_type == "batch":
                summary.total_batch = max(summary.total_batch, r.total_source)
                summary.batch_linked += r.match_count
                summary.batch_unmatched += len(r.unmatched_sources)
            elif r.source_type == "market":
                summary.total_market = max(summary.total_market, r.total_source)
                summary.market_linked += r.match_count
                summary.market_unmatched += len(r.unmatched_sources)
            elif r.source_type == "watchlist":
                summary.total_watchlist = max(summary.total_watchlist, r.total_source)
                summary.watchlist_linked += r.match_count
                summary.watchlist_unmatched += len(r.unmatched_sources)
        
        # Grading is a target, so count from reports where grading is target
        for r in report.reports:
            if r.target_type == "grading":
                summary.total_grading = max(summary.total_grading, r.total_target)
                summary.grading_linked += r.match_count
                summary.grading_unmatched += len(r.unmatched_targets)
        
        return summary
    
    def _build_report(self, source_type: str, target_type: str,
                     sources: List[Any], targets: List[Any],
                     connections: List[Connection]) -> ConnectedReport:
        """Build a ConnectedReport with unmatched source/target tracking."""
        matched_source_ids = {c.source_id for c in connections}
        matched_target_ids = {c.target_id for c in connections}
        
        unmatched_sources = [self._extract_id(s) for s in sources
                            if self._extract_id(s) not in matched_source_ids]
        unmatched_targets = [self._extract_id(t) for t in targets
                            if self._extract_id(t) not in matched_target_ids]
        
        return ConnectedReport(
            source_type=source_type,
            target_type=target_type,
            total_source=len(sources),
            total_target=len(targets),
            connections=connections,
            unmatched_sources=unmatched_sources,
            unmatched_targets=unmatched_targets,
        )
    
    # -- Extraction helpers ------------------------------------------------
    
    def _extract_id(self, record: Any) -> str:
        """Safely extract an identifier from any record type."""
        if record is None:
            return ""
        if hasattr(record, "id") and record.id is not None:
            return str(record.id)
        if hasattr(record, "candidate_id") and record.candidate_id is not None:
            return str(record.candidate_id)
        if hasattr(record, "assessment_id") and record.assessment_id is not None:
            return str(record.assessment_id)
        if hasattr(record, "record_id") and record.record_id is not None:
            return str(record.record_id)
        return str(id(record))
    
    def _extract_country_denom_year(self, record: Any) -> Tuple[str, str, str]:
        """Safely extract (country, denomination, year) from any record type."""
        if record is None:
            return ("", "", "")
        country = getattr(record, "country", "") or ""
        denom = getattr(record, "denomination", "") or ""
        year = getattr(record, "year", "") or ""
        return (country.lower().strip(), denom.lower().strip(), str(year).strip())
    
    # -- Matching helpers ----------------------------------------------------
    
    def _match_exact(self, sources: List[Any], targets: List[Any],
                    source_key_func, target_key_func,
                    match_type: MatchType = MatchType.EXACT) -> List[Connection]:
        """Exact match: source_key == target_key."""
        connections = []
        for source in sources:
            s_key = source_key_func(source)
            if not s_key:
                continue
            for target in targets:
                t_key = target_key_func(target)
                if s_key == t_key:
                    connections.append(Connection(
                        source_type="",
                        target_type="",
                        source_id=self._extract_id(source),
                        target_id=self._extract_id(target),
                        match_type=match_type,
                        match_key=str(s_key),
                    ))
        return connections
    
    def _match_exact_multi_target(self, sources: List[Any], targets: List[Any],
                                  source_key_func, target_key_func) -> List[Connection]:
        """Exact match where target_key returns a tuple of possible keys."""
        connections = []
        for source in sources:
            s_key = source_key_func(source)
            if not s_key:
                continue
            for target in targets:
                t_keys = target_key_func(target)
                if isinstance(t_keys, str):
                    t_keys = (t_keys,)
                if s_key in t_keys:
                    connections.append(Connection(
                        source_type="",
                        target_type="",
                        source_id=self._extract_id(source),
                        target_id=self._extract_id(target),
                        match_type=MatchType.EXACT,
                        match_key=str(s_key),
                    ))
        return connections
    
    def _match_fuzzy(self, sources: List[Any], targets: List[Any],
                    source_key_func, target_key_func) -> List[Connection]:
        """Fuzzy match: country + denomination + exact year.
        
        All three must match. No year tolerance.
        """
        connections = []
        for source in sources:
            s_country, s_denom, s_year = source_key_func(source)
            if not s_country or not s_denom:
                continue
            for target in targets:
                t_country, t_denom, t_year = target_key_func(target)
                if (s_country == t_country and 
                    s_denom == t_denom and 
                    s_year == t_year):
                    connections.append(Connection(
                        source_type="",
                        target_type="",
                        source_id=self._extract_id(source),
                        target_id=self._extract_id(target),
                        match_type=MatchType.FUZZY,
                        match_key=f"{s_country}:{s_denom}:{s_year}",
                    ))
        return connections
    
    def _match_fuzzy_2tuple(self, sources: List[Any], targets: List[Any],
                            source_key_func, target_key_func) -> List[Connection]:
        """Fuzzy match with 2-tuple keys: country + denomination only.
        
        Used for market-to-acquisition matching where year is optional.
        """
        connections = []
        for source in sources:
            s_country, s_denom = source_key_func(source)
            if not s_country or not s_denom:
                continue
            for target in targets:
                t_country, t_denom = target_key_func(target)
                if s_country == t_country and s_denom == t_denom:
                    connections.append(Connection(
                        source_type="",
                        target_type="",
                        source_id=self._extract_id(source),
                        target_id=self._extract_id(target),
                        match_type=MatchType.FUZZY,
                        match_key=f"{s_country}:{s_denom}",
                    ))
        return connections
    
    def _match_keyword(self, sources: List[Any], targets: List[Any],
                      source_key_func, target_key_func) -> List[Connection]:
        """Keyword match: source keyword appears in target text."""
        connections = []
        for source in sources:
            s_keyword = source_key_func(source)
            if not s_keyword:
                continue
            for target in targets:
                t_text = target_key_func(target)
                if s_keyword in t_text:
                    connections.append(Connection(
                        source_type="",
                        target_type="",
                        source_id=self._extract_id(source),
                        target_id=self._extract_id(target),
                        match_type=MatchType.FUZZY,
                        match_key=f"keyword:{s_keyword}",
                    ))
        return connections
    
    # -- Type-specific extraction helpers ------------------------------------
    
    def _extract_ocr_candidates(self) -> List[Any]:
        """Extract individual OCR candidates from OCR reports."""
        candidates = []
        for report in (self._context.ocr_reports or []):
            report_candidates = getattr(report, "candidates", []) or []
            candidates.extend(report_candidates)
        return candidates
    
    def _extract_entry_candidates(self) -> List[Any]:
        """Extract collection entry candidates from workflow statuses."""
        candidates = []
        for status in (self._context.workflow_statuses or []):
            entry_candidates = getattr(status, "entry_candidates", []) or []
            candidates.extend(entry_candidates)
        return candidates
    
    def _extract_intelligence_targets(self) -> List[Any]:
        """Extract collection intelligence targets (gaps, upgrades)."""
        # For now, extract from want_list_intents and shopping candidates
        # In Phase 2+, this will use CollectionIntelligenceEngine outputs
        targets = []
        targets.extend(self._context.want_list_intents or [])
        return targets
    
    def _extract_acquisition_candidates(self) -> List[Any]:
        """Extract acquisition candidates from shopping or workflow."""
        candidates = []
        candidates.extend(self._context.shopping_candidates or [])
        for status in (self._context.workflow_statuses or []):
            acq_candidates = getattr(status, "acquisition_candidates", []) or []
            candidates.extend(acq_candidates)
        return candidates
    
    def _extract_deal_candidates(self) -> List[Any]:
        """Extract deal candidates from workflow or shopping."""
        candidates = []
        candidates.extend(self._context.shopping_candidates or [])
        for status in (self._context.workflow_statuses or []):
            deal_candidates = getattr(status, "deal_candidates", []) or []
            candidates.extend(deal_candidates)
        return candidates
