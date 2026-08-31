"""
Coin Collection Manager GUI
MVP app for managing coin collection with manual editing and optional automatic identification.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from decimal import Decimal
from PIL import Image, ImageTk
import os
import logging
import queue
import threading
import cv2
from acquisition_workflow import AcquisitionWorkflow
from collector_cloud import CollectorCloud
from coin_collection import (
    CoinCollection,
    CoinCollectionApp,
    CoinItem,
    CollectionLoadState,
    Disposition,
    IdentificationStatus,
    ItemPhoto,
    ItemType,
    PhotoRole,
    normalize_acquisition_values,
    serialize_money,
)
from collection_browser import (
    CollectionBrowserCriteria,
    CollectionBrowserSort,
    issuer_country_filter_options,
    project_collection,
)
from numista_intelligence import NumistaIntelligenceEngine
from smart_phone_cataloguer import SmartPhoneCataloguer
from collection_intelligence import CollectionIntelligenceEngine
from ai_grading_assistant import AIGradingAssistant, GradingCandidate
from platform_analytics import PlatformAnalyticsEngine
from deal_hunter import DealHunter, DealListing
from deal_hunter_calibration import DealHunterCalibrationEngine
from deal_hunter_ranking import CandidatePool, DealHunterRankingEngine, ImportProfile
from device_linking import DeviceLinkingEngine
from field_test_framework import ScenarioRunner, default_field_test_scenarios
from focused_collection_intelligence import CandidateItem, FocusedCollectionIntelligenceEngine
from legacy_portfolio_importer import (
    LegacyPortfolioImporter,
    export_import_summary_csv,
    export_want_list_preview_csv,
)
from listing_connectors import (
    ConnectorRegistry,
    DuplicateOpportunityDetector,
    SourceSummaryReport,
)
from live_deal_hunter import DEFAULT_EBAY_RSS_URL, LiveDealHunter, RSSListingConnector
from live_deal_hunter_readiness import LiveDealHunterReadinessAudit
from live_source_validation import LiveSourceValidator
from market_intelligence import MarketIntelligenceEngine
from mobile_collector_companion import MobileCollectorCompanion, WORKFLOW_COIN_SHOW
from mobile_collection_entry import (
    APPROVE as ENTRY_APPROVE,
    REJECT as ENTRY_REJECT,
    REVIEW as ENTRY_REVIEW,
    WORKFLOW_ANTIQUE_MARKET as ENTRY_WORKFLOW_ANTIQUE_MARKET,
    WORKFLOW_AUCTION_PREVIEW as ENTRY_WORKFLOW_AUCTION_PREVIEW,
    WORKFLOW_COIN_SHOP as ENTRY_WORKFLOW_COIN_SHOP,
    WORKFLOW_COIN_SHOW as ENTRY_WORKFLOW_COIN_SHOW,
    WORKFLOW_DEALER_VISIT as ENTRY_WORKFLOW_DEALER_VISIT,
    MobileCollectionEntryEngine,
)
from multi_device_workspace import (
    DEVICE_DESKTOP,
    DEVICE_LAPTOP,
    DEVICE_PHONE,
    DEVICE_TABLET,
    MultiDeviceWorkspaceEngine,
)
from portfolio_performance import PortfolioPerformanceEngine
from coin_identifier_interface import CoinIdentifierFactory
from upgrade_advisor import UpgradeAdvisor
from portfolio_dashboard import PortfolioDashboard
from session_context import SessionContext
from listing_analyzer import ListingAnalyzer, ListingCandidate
from backup_manager import BackupManager, DataSafetyValidator
from collector_workflow_integration import (
    APPROVE as WORKFLOW_APPROVE,
    REJECT as WORKFLOW_REJECT,
    REVIEW as WORKFLOW_REVIEW,
    STAGE_FINAL_REVIEW,
    CollectorWorkflowIntegrationEngine,
)
from collection_dashboard import CollectionDashboard
from collector_companion_readiness import CollectorCompanionReadinessAuditor
from collector_home_dashboard import CollectorHomeDashboard
from collector_workspace import CollectorWorkspace
from canadian_reference_provider import ReferenceFilters, ReferenceQuery
from collection_integrity import CollectionIntegrityAudit
from collection_snapshot import CollectionSnapshotManager
from collector_operating_system import CollectorHome, CollectionHealthReportEngine
from collector_workflows import CollectorWorkflowEngine
from market_awareness import MarketAwarenessEngine
from market_intelligence_automation import MarketIntelligenceAutomationEngine
from ocr_assisted_identification import OCRIdentificationEngine
from ocr_experiment import OCRExperiment
from ocr_validation import OCRValidationEngine
from opportunity_engine import OpportunityEngine
from persistence_manager import PersistenceManager
from photo_capture_workflow import (
    ROLE_COIN_BACK,
    ROLE_COIN_FRONT,
    ROLE_LISTING,
    ROLE_NOTE_BACK,
    ROLE_NOTE_FRONT,
    SESSION_COIN_FRONT_BACK,
    SESSION_LISTING_PHOTOS,
    SESSION_NOTE_FRONT_BACK,
    PhotoCaptureWorkflow,
)
from photo_assisted_entry import PhotoAssistedEntry, PhotoCandidate
from photo_inbox import PhotoInboxManager
from photo_vault import PhotoVaultIntegrityAudit
from shopping_explainability import ShoppingExplanationEngine
from smart_shopping_assistant import SmartShoppingAssistant, ShoppingCandidate
from sync_backup_engine import SyncBackupEngine
from watchlist_engine import AlertEngine, Watchlist, WatchlistEngine, WatchlistItem
from platform_core import Platform
from platform_integration import PlatformIntegration
from batch_processing import BatchProcessingEngine, BatchReport
from application_metadata import APPLICATION_VERSION
from confirmed_observations import ConfirmedObservationRecord, ConfirmedObservationStore
from capture_import.desktop_import_pipeline_selection import ImportPipelineMode
from capture_import.errors import CaptureImportError, RecoveryRequired
from capture_import.ui import CapturePackageImportDialog, build_default_import_services


_LOGGER = logging.getLogger(__name__)


def _visual_identity_failure_diagnostic(error):
    """Return bounded provider metadata without rendering exception payloads."""

    error_type = f"{type(error).__module__}.{type(error).__qualname__}"
    parts = [f"error_type={error_type}"]
    try:
        status_code = getattr(error, "status_code", None)
    except Exception:
        status_code = None
    if (
        isinstance(status_code, int)
        and not isinstance(status_code, bool)
        and 100 <= status_code <= 599
    ):
        parts.append(f"status_code={status_code}")
    try:
        request_id = getattr(error, "request_id", None)
    except Exception:
        request_id = None
    if (
        isinstance(request_id, str)
        and 1 <= len(request_id) <= 128
        and all(
            character.isascii()
            and (character.isalnum() or character in "_-")
            for character in request_id
        )
    ):
        parts.append(f"request_id={request_id}")
    return ", ".join(parts)


GRADE_SUGGESTIONS = (
    "",
    "PO-1",
    "FR-2",
    "AG-3",
    "G-4",
    "VG-8",
    "F-12",
    "VF-20",
    "VF-30",
    "EF-40",
    "EF-45",
    "AU-50",
    "AU-53",
    "AU-55",
    "AU-58",
    "MS-60",
    "MS-61",
    "MS-62",
    "MS-63",
    "MS-64",
    "MS-65",
    "MS-66",
    "MS-67",
    "MS-68",
    "MS-69",
    "MS-70",
)

PHOTO_INBOX_SETTING_SCAN_ON_STARTUP = "scan_photo_inbox_on_startup"
PHOTO_INBOX_SETTING_STARTUP_NOTIFICATION = "show_photo_inbox_startup_notification"
PHOTO_INBOX_SETTING_AUTO_REFRESH_ON_OPEN = "auto_refresh_photo_inbox_when_opened"
PHOTO_INBOX_SETTINGS_DEFAULTS = {
    PHOTO_INBOX_SETTING_SCAN_ON_STARTUP: True,
    PHOTO_INBOX_SETTING_STARTUP_NOTIFICATION: True,
    PHOTO_INBOX_SETTING_AUTO_REFRESH_ON_OPEN: True,
}

BROWSER_TYPE_CHOICES = {
    "All": None,
    "Coin": ItemType.COIN,
    "Banknote": ItemType.BANKNOTE,
}
BROWSER_DISPOSITION_CHOICES = {
    "All": None,
    "Keep": Disposition.KEEP,
    "Upgrade": Disposition.UPGRADE,
    "Sell/Trade": Disposition.SELL_TRADE,
    "Undecided": Disposition.UNDECIDED,
}
BROWSER_IDENTIFICATION_CHOICES = {
    "All": None,
    "Identified": IdentificationStatus.IDENTIFIED,
    "Partial": IdentificationStatus.PARTIAL,
    "Unidentified": IdentificationStatus.UNIDENTIFIED,
}
BROWSER_SORT_CHOICES = {
    "Collection order": CollectionBrowserSort.COLLECTION_ORDER,
    "Recently updated": CollectionBrowserSort.RECENTLY_UPDATED,
    "Issuer/Country A-Z": CollectionBrowserSort.ISSUER_COUNTRY,
    "Denomination A-Z": CollectionBrowserSort.DENOMINATION,
    "Date/Year/Series A-Z": CollectionBrowserSort.DATE_SERIES,
}


class CoinCollectionGUI:
    """GUI for coin collection management."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Coin Collection Manager")
        self.root.geometry("1000x700")
        
        # Initialize backend
        self.app = CoinCollectionApp()
        self.session_context = SessionContext()
        self.persistence_manager = PersistenceManager()
        self.backup_manager = BackupManager(persistence_manager=self.persistence_manager)
        self.confirmed_observation_store = ConfirmedObservationStore()
        self.snapshot_manager = CollectionSnapshotManager()
        self.market_awareness_engine = MarketAwarenessEngine()
        self.photo_records = []
        self.photo_capture_workflow = PhotoCaptureWorkflow()
        self.photo_candidates = []
        self.ocr_results = []
        self.ocr_reports = []
        
        # Initialize Platform
        self.platform = Platform()
        self.platform_integration = PlatformIntegration(self.platform)
        self.platform_integration.initialize()
        self.app.set_recognition_orchestrator(
            self._build_default_legacy_recognition_orchestrator()
        )
        self.ocr_identification_reports = []
        self.mobile_entry_reports = []
        self.workflow_completion_reports = []
        self.cloud_snapshots = []
        self.cloud_sync_plans = []
        self.cloud_backup_packages = []
        self.cloud_readiness_reports = []
        self.backup_archives = []
        self.restore_plans = []
        self.backup_histories = []
        self.sync_simulations = []
        self.sync_conflict_reports = []
        self.rollback_plans = []
        self.multi_device_workspaces = []
        self.workspace_snapshots = []
        self.workspace_activities = []
        self.workspace_health_reports = []
        self.device_link_reports = []
        self.workspace_link_maps = []
        self.conflict_resolution_reports = []
        self.device_link_readiness_reports = []
        self.shopping_candidates = []
        self.workflow_statuses = []
        self.workflow_summaries = []
        self.home_reports = []
        self.acknowledged_home_actions = []
        self.readiness_reports = []
        self.audit_summaries = []
        self.recent_deal_listings = []
        self.deal_hunter_reports = []
        self.watchlists = [WatchlistEngine.adam_presets()]
        self.app_preferences = {}
        self.session_status_var = tk.StringVar(value=self.session_context.format_status_line())
        self.photo_inbox_pending_count = 0
        self.photo_inbox_last_error = ""
        self.photo_inbox_active_notification_signature = ""
        self.photo_inbox_dismissed_notification_signature = ""
        self.photo_inbox_indicator_var = tk.StringVar(value=self.photo_inbox_indicator_text(0))
        self.photo_inbox_notification_var = tk.StringVar(value="")
        
        # Initialize optional identifier
        self.identifier = None
        self.use_identifier = False
        
        # Current state
        self.current_image = None
        self.current_photo = None
        self.current_item_photos = []
        self.selected_photo_index = None
        self.pending_inbox_manager = None
        self.pending_inbox_photo_set_id = ""
        self.pending_inbox_refresh_callback = None
        self.pending_inbox_completion_done = False
        self.detection_result = None

        self.capture_import_ready = False
        self.capture_import_recovery_message = RecoveryRequired().safe_message
        self.capture_import_recovery = None
        self.capture_import_coordinator = None
        self._collection_edit_windows = set()
        self._browser_row_item_ids = {}
        self._browser_thumbnail_refs = {}
        self._browser_fallback_thumbnail = None
        self._visual_identity_provider = None
        self.initialize_capture_import_recovery()
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create GUI
        self.create_widgets()
        self.refresh_collection_list()
        self.schedule_startup_photo_inbox_scan()

    def _build_default_legacy_recognition_orchestrator(self):
        """Compose the legacy detector shell with the runtime event bus."""
        from legacy_coin_recognition_capability import LegacyCoinRecognitionCapability
        from legacy_recognition_orchestration import (
            RecognitionCapabilityRegistry,
            RecognitionOrchestrator,
        )

        def emit(event_name, payload):
            self.platform_integration.event_bus.publish_sync(
                event_name,
                dict(payload),
                source="legacy_recognition_orchestrator",
            )

        return RecognitionOrchestrator(
            RecognitionCapabilityRegistry((LegacyCoinRecognitionCapability(),)),
            telemetry=emit,
        )
    
    def create_menu_bar(self):
        """Create the menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Import Collection CSV", command=self.import_collection_csv)
        file_menu.add_command(
            label="Import Capture Package...",
            command=self.import_capture_package,
            state=self.capture_import_menu_state(),
        )
        file_menu.add_command(
            label="OCR-Assisted Capture Package...",
            command=self.import_capture_package_with_ocr,
            state=self.capture_import_menu_state(),
        )
        file_menu.add_command(
            label="Import Coin Images...",
            command=self.import_coin_images_with_ocr,
            state=self.capture_import_menu_state(),
        )
        file_menu.add_command(
            label="AI-Assisted Coin Images...",
            command=self.import_coin_images_with_visual_ai,
            state=self.capture_import_menu_state(),
        )
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        # Collector Home menu
        home_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Collector Home", menu=home_menu)
        home_menu.add_command(label="Collector Home Dashboard", command=self.open_collector_home_dashboard)
        home_menu.add_command(label="Collector Workspace", command=self.open_collector_workspace)
        home_menu.add_command(label="Collector Home", command=self.open_collector_home)
        home_menu.add_command(label="Photo Inbox...", command=self.open_photo_inbox)
        home_menu.add_command(label="Daily Collector Summary", command=self.open_daily_collector_summary)
        home_menu.add_command(label="Collection Health Report", command=self.open_collection_health_report)

        # Workflows menu
        workflows_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Workflows", menu=workflows_menu)
        workflows_menu.add_command(label="Acquisition Workflow", command=self.open_acquisition_workflow)
        workflows_menu.add_command(label="Collection Review Workflow", command=self.open_collection_review_workflow)
        workflows_menu.add_command(label="Photo-Assisted Entry", command=self.open_photo_assisted_entry)
        workflows_menu.add_command(label="Listing Analyzer", command=self.open_listing_analyzer)
        workflows_menu.add_command(label="Smart Shopping Assistant", command=self.open_smart_shopping_assistant)
        workflows_menu.add_command(label="Opportunity Engine", command=self.open_opportunity_engine)
        workflows_menu.add_command(label="Deal Hunter", command=self.open_deal_hunter)
        workflows_menu.add_command(label="Do I Own This?", command=self.open_collection_intelligence_lookup)

        # Reports menu
        reports_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Reports", menu=reports_menu)
        reports_menu.add_command(label="Collection Dashboard", command=self.open_collection_dashboard)
        reports_menu.add_command(label="Collection Gap Report", command=self.open_collection_gap_report)
        reports_menu.add_command(label="Collection Integrity Audit", command=self.open_collection_integrity_audit)
        reports_menu.add_command(label="Portfolio Dashboard", command=self.open_portfolio_dashboard)
        reports_menu.add_command(label="Photo Vault Audit", command=self.open_photo_vault_audit)
        reports_menu.add_command(label="Snapshot Report", command=self.open_snapshot_report)
        reports_menu.add_command(label="Data Safety Check", command=self.open_data_safety_check)
        reports_menu.add_command(label="Collection Recovery Report", command=self.open_collection_recovery_report)

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Load Collection Context", command=self.load_collection_context)
        tools_menu.add_command(label="Clear Session Context", command=self.clear_session_context)
        tools_menu.add_separator()
        tools_menu.add_command(label="Save Session State", command=self.save_session_state)
        tools_menu.add_command(label="Load Session State", command=self.load_session_state)
        tools_menu.add_command(label="Clear Session State", command=self.clear_saved_session_state)
        tools_menu.add_command(label="Export Session State", command=self.export_session_state)
        tools_menu.add_command(label="Import Session State", command=self.import_session_state)
        tools_menu.add_separator()
        tools_menu.add_command(label="Create Backup Package", command=self.create_backup_package)
        tools_menu.add_command(label="List Backups", command=self.list_backup_packages)
        tools_menu.add_command(label="Restore Backup", command=self.restore_backup_package)
        tools_menu.add_command(label="Create Snapshot", command=self.create_collection_snapshot)
        tools_menu.add_separator()
        tools_menu.add_command(label="Buy Advisor", command=self.open_buy_advisor)
        tools_menu.add_command(label="Upgrade Advisor", command=self.open_upgrade_advisor)
        tools_menu.add_command(label="Want List Generator", command=self.open_want_list_generator)
        tools_menu.add_command(label="Portfolio Import Preview", command=self.open_portfolio_import_preview)
        tools_menu.add_command(label="Want List Preview", command=self.open_want_list_preview)
        tools_menu.add_command(label="OCR Experiment", command=self.open_ocr_experiment)
        tools_menu.add_command(label="OCR-Assisted Identification", command=self.open_ocr_assisted_identification)
        tools_menu.add_command(label="Mobile Collection Entry", command=self.open_mobile_collection_entry)
        tools_menu.add_command(label="Collector Workflow Integration", command=self.open_collector_workflow_integration)
        tools_menu.add_command(label="Collector Cloud Foundation", command=self.open_collector_cloud_foundation)
        tools_menu.add_command(label="Sync & Backup", command=self.open_sync_backup)
        tools_menu.add_command(label="Multi-Device Workspace", command=self.open_multi_device_workspace)
        tools_menu.add_command(label="Device Linking & Conflict Resolution", command=self.open_device_linking)
        tools_menu.add_separator()
        tools_menu.add_command(label="Platform Management", command=self.open_platform_management)
        tools_menu.add_command(label="Platform Analytics", command=self.open_platform_analytics)
        tools_menu.add_command(label="Collection Insights", command=self.open_collection_insights)
        tools_menu.add_command(label="Acquisition Strategy", command=self.open_acquisition_strategy)
        tools_menu.add_command(label="Ask My Collection", command=self.open_ask_my_collection)
        tools_menu.add_command(label="Collection Assistant", command=self.open_collection_assistant)
        tools_menu.add_command(label="Deal Hunter Ranking", command=self.open_deal_hunter_ranking)
        tools_menu.add_command(label="Deal Hunter Calibration", command=self.open_deal_hunter_calibration)
        tools_menu.add_command(label="External Listing Connectors", command=self.open_external_listing_connectors)
        tools_menu.add_command(label="Live Deal Hunter", command=self.open_live_deal_hunter)
        tools_menu.add_command(label="Live Source Validation", command=self.open_live_source_validation)
        tools_menu.add_command(label="Live Deal Hunter Readiness", command=self.open_live_deal_hunter_readiness)
        tools_menu.add_command(label="Market Intelligence", command=self.open_market_intelligence)
        tools_menu.add_command(label="Market Intelligence Automation", command=self.open_market_intelligence_automation)
        tools_menu.add_command(label="Watchlists & Alerts", command=self.open_watchlists_and_alerts)
        tools_menu.add_command(label="Field Test & Tuning", command=self.open_field_test_and_tuning)
        tools_menu.add_command(label="Mobile Collector Companion", command=self.open_mobile_collector_companion)
        tools_menu.add_command(label="Phone Photo Capture", command=self.open_phone_photo_capture)
        tools_menu.add_command(label="Portfolio Analytics", command=self.open_portfolio_performance)
        tools_menu.add_command(label="Numista Intelligence", command=self.open_numista_intelligence)
        tools_menu.add_command(label="Smart Phone Cataloguer", command=self.open_smart_phone_cataloguer)
        tools_menu.add_command(label="Batch Processing", command=self.open_batch_processing)
        tools_menu.add_command(label="AI Grading Assistant", command=self.open_ai_grading_assistant)
        tools_menu.add_separator()
        tools_menu.add_command(label="Collector Companion Readiness", command=self.open_collector_companion_readiness)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Collector Companion Readiness", command=self.open_collector_companion_readiness)
    
    def import_collection_csv(self):
        """Import collection from CSV file."""
        # Open file dialog
        file_path = filedialog.askopenfilename(
            title="Import Collection CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
        
        # Import from CSV
        imported_count, total_coins, total_countries, total_unique_dates = self.app.import_from_csv(file_path)
        
        # Display statistics
        stats_message = f"""
Import Complete!

Imported: {imported_count} coins
Total Coins: {total_coins}
Total Countries: {total_countries}
Total Unique Dates: {total_unique_dates}
"""
        messagebox.showinfo("Import Statistics", stats_message)
        
        # Refresh collection list
        self.refresh_collection_list()

    def import_capture_package(self):
        """Select, preview, and explicitly import one local capture package."""

        self._open_capture_package_import(
            import_mode=ImportPipelineMode.DEFAULT,
        )

    def import_capture_package_with_ocr(self):
        """Select one package for advisory OCR review without saving it."""

        self._open_capture_package_import(
            import_mode=ImportPipelineMode.OCR_ENABLED,
        )

    def import_coin_images_with_ocr(self):
        """Select obverse/reverse images for the existing OCR workflow."""

        if not self.capture_import_ready:
            messagebox.showerror(
                "Coin Image OCR",
                self.capture_import_recovery_message,
            )
            return
        image_types = [
            ("Coin images", "*.jpg *.jpeg *.png"),
            ("JPEG images", "*.jpg *.jpeg"),
            ("PNG images", "*.png"),
            ("All files", "*.*"),
        ]
        front_path = filedialog.askopenfilename(
            title="Select Obverse (Front) Coin Image",
            filetypes=image_types,
        )
        if not front_path:
            return
        reverse_path = filedialog.askopenfilename(
            title="Select Reverse Coin Image",
            filetypes=image_types,
        )
        if not reverse_path:
            return

        from capture_import.standalone_image_intake import (
            StandaloneImageIntakeError,
            create_temporary_capture_package,
        )

        try:
            source = create_temporary_capture_package(
                front_path=front_path,
                reverse_path=reverse_path,
            )
        except StandaloneImageIntakeError as error:
            messagebox.showerror(
                "Coin Image OCR",
                error.safe_message,
            )
            return
        try:
            self._launch_capture_package_import(
                package_path=str(source.path),
                import_mode=ImportPipelineMode.OCR_ENABLED,
                on_close=source.release,
                ocr_handoff_callback=(
                    lambda parent, handoff: self.open_ocr_review_handoff(
                        parent,
                        handoff,
                        managed_photo_source=source,
                    )
                ),
            )
        except Exception:
            source.release()
            raise

    def import_coin_images_with_visual_ai(self, front_path=None, reverse_path=None):
        """Send two explicitly selected images to Terra for human review."""

        if not self.capture_import_ready:
            messagebox.showerror(
                "AI-Assisted Coin Images",
                self.capture_import_recovery_message,
            )
            return
        image_types = [
            ("Coin images", "*.jpg *.jpeg *.png"),
            ("JPEG images", "*.jpg *.jpeg"),
            ("PNG images", "*.png"),
            ("All files", "*.*"),
        ]
        front_path = front_path or filedialog.askopenfilename(
            title="Select Obverse (Front) Coin Image for AI Review",
            filetypes=image_types,
        )
        if not front_path:
            return
        reverse_path = reverse_path or filedialog.askopenfilename(
            title="Select Reverse Coin Image for AI Review",
            filetypes=image_types,
        )
        if not reverse_path:
            return

        from capture_import.standalone_image_intake import (
            StandaloneImageIntakeError,
            create_temporary_capture_package,
        )

        try:
            source = create_temporary_capture_package(
                front_path=front_path,
                reverse_path=reverse_path,
            )
        except StandaloneImageIntakeError as error:
            messagebox.showerror(
                "AI-Assisted Coin Images",
                error.safe_message,
            )
            return

        if not messagebox.askyesno(
            "Send Coin Images to OpenAI?",
            (
                "The selected obverse and reverse images will be sent to "
                "OpenAI GPT-5.6 Terra for an identity proposal. The proposal "
                "will not change your collection until you review and "
                "explicitly confirm it. Continue?"
            ),
            parent=self.root,
        ):
            source.release()
            return

        from capture_import.desktop_visual_identity_review import (
            VisualIdentityAvailabilityError,
            VisualReviewError,
            create_visual_identity_proposal,
            create_visual_identity_review_dialog,
            create_visual_request_from_capture_package,
        )
        from capture_import.visual_identity_provider import (
            VisualIdentityContractError,
        )

        try:
            request = create_visual_request_from_capture_package(source.path)
            report = self._get_visual_identity_provider().identify(request)
            proposal = create_visual_identity_proposal(report)
        except (VisualReviewError, VisualIdentityContractError) as error:
            source.release()
            messagebox.showwarning(
                "AI Identity Proposal Unavailable",
                str(error),
                parent=self.root,
            )
            return
        except VisualIdentityAvailabilityError as error:
            source.release()
            messagebox.showerror(
                "AI Identity Service Not Configured",
                str(error),
                parent=self.root,
            )
            return
        except Exception as error:
            source.release()
            _LOGGER.warning(
                "OpenAI visual identity provider failure: %s",
                _visual_identity_failure_diagnostic(error),
            )
            messagebox.showerror(
                "AI Identity Service Unavailable",
                (
                    "No collection data was changed. Verify that the OpenAI "
                    "API key is configured and network access is available, "
                    "then try again."
                ),
                parent=self.root,
            )
            return

        self._visual_review_source = source
        self._visual_review_proposal = proposal
        try:
            self._visual_review_dialog = create_visual_identity_review_dialog(
                parent=self.root,
                proposal=proposal,
                on_confirm=self._confirm_and_save_visual_review,
                on_reject=self._reject_visual_review,
                on_defer=self._defer_visual_review,
            )
        except Exception:
            self._release_visual_review_source()
            raise

    def _get_visual_identity_provider(self):
        """Create Terra lazily, only after the explicit user disclosure."""

        provider = getattr(self, "_visual_identity_provider", None)
        if provider is not None:
            return provider
        factory = getattr(self, "_visual_identity_provider_factory", None)
        if factory is None:
            from capture_import.desktop_visual_identity_review import (
                VisualIdentityAvailabilityError,
            )
            if not os.environ.get("OPENAI_API_KEY", "").strip():
                raise VisualIdentityAvailabilityError(
                    "OPENAI_API_KEY is not configured. No collection data was changed."
                )
            from capture_import.visual_identity_provider import (
                OpenAITerraVisualIdentityProvider,
            )
            from inference_telemetry import get_default_telemetry_sink

            factory = lambda: OpenAITerraVisualIdentityProvider(
                telemetry_sink=get_default_telemetry_sink()
            )
        provider = factory()
        self._visual_identity_provider = provider
        return provider

    def _confirm_and_save_visual_review(self, reviewed):
        """Require a second explicit confirmation before managed persistence."""

        from capture_import.desktop_visual_identity_review import VisualReviewError
        from capture_import.reviewed_coin_collection_entry import (
            ReviewedCoinCollectionEntryError,
            persist_reviewed_coin,
        )

        proposal = self._visual_review_proposal
        try:
            draft = reviewed.to_reviewed_coin_draft(proposal)
        except (VisualReviewError, TypeError, ValueError) as error:
            messagebox.showwarning(
                "Visual Review Incomplete", str(error), parent=self.root
            )
            self._release_visual_review_source()
            return

        duplicates = self.app.collection.find_matching_coins(
            draft.country, draft.denomination, draft.year
        )
        candidate = proposal.candidate
        details = [
            "Save this operator-confirmed AI proposal to the collection?",
            "",
            f"Country: {draft.country}",
            f"Denomination: {draft.denomination}",
            f"Year: {draft.year}",
            f"Type/design: {reviewed.type_design.strip() or 'not recorded'}",
            "Images: obverse and reverse will be retained",
            "",
            f"Provider/model: {proposal.provider_id} / {proposal.model_id}",
            f"Provider confidence: {candidate.confidence:.0%}",
            "Evidence: " + " | ".join(candidate.evidence_observations),
        ]
        if duplicates:
            details.extend(
                ("", f"Possible matching collection record(s): {len(duplicates)}")
            )
        if not messagebox.askyesno(
            "Confirm AI-Reviewed Coin",
            "\n".join(details),
            parent=self.root,
        ):
            self._release_visual_review_source()
            return

        source = getattr(self, "_visual_review_source", None)
        try:
            item = persist_reviewed_coin(
                collection=self.app.collection,
                draft=draft,
                source_package_path=source.path if source is not None else None,
            )
        except (ReviewedCoinCollectionEntryError, TypeError, ValueError) as error:
            messagebox.showerror(
                "Collection Save Failed", str(error), parent=self.root
            )
            self._release_visual_review_source()
            return

        self._release_visual_review_source()
        self.refresh_collection_list()
        messagebox.showinfo(
            "AI-Reviewed Coin Saved",
            f"Saved {item.country} {item.denomination} ({item.year}).",
            parent=self.root,
        )

    def _reject_visual_review(self):
        self._release_visual_review_source()
        messagebox.showinfo(
            "AI Proposal Rejected",
            "The proposal was rejected. No collection data was changed.",
            parent=self.root,
        )

    def _defer_visual_review(self):
        self._release_visual_review_source()

    def _release_visual_review_source(self):
        source = getattr(self, "_visual_review_source", None)
        self._visual_review_source = None
        self._visual_review_proposal = None
        if source is not None:
            source.release()

    def _open_capture_package_import(self, *, import_mode):
        """Open the production package dialog for one explicit pipeline mode."""

        if not self.capture_import_ready:
            messagebox.showerror(
                "Capture Package Import",
                self.capture_import_recovery_message,
            )
            return

        package_path = filedialog.askopenfilename(
            title=(
                "Select Capture Package for OCR Review"
                if import_mode == ImportPipelineMode.OCR_ENABLED
                else "Import Capture Package"
            ),
            filetypes=[
                ("Coin Analyzer capture packages", "*.ca-package"),
                ("All files", "*.*"),
            ],
        )
        if not package_path:
            return
        self._launch_capture_package_import(
            package_path=package_path,
            import_mode=import_mode,
        )

    def _launch_capture_package_import(
        self,
        *,
        package_path,
        import_mode,
        on_source_released=None,
        on_close=None,
        ocr_handoff_callback=None,
    ):
        """Launch the shared package-shaped OCR/import dialog."""

        options = {}
        if on_source_released is not None:
            options["on_source_released"] = on_source_released
        if on_close is not None:
            options["on_close"] = on_close
        callback = (
            ocr_handoff_callback
            if ocr_handoff_callback is not None
            else self.open_ocr_review_handoff
        )
        CapturePackageImportDialog(
            self.root,
            package_path,
            self.app.collection,
            on_success=self.refresh_collection_list,
            import_mode=import_mode,
            on_ocr_handoff=(
                callback
                if import_mode == ImportPipelineMode.OCR_ENABLED
                else None
            ),
            **options,
        )

    def open_ocr_review_handoff(
        self,
        parent,
        handoff,
        managed_photo_source=None,
    ):
        """Display existing OCR review dialogs for one advisory handoff."""

        from capture_import.desktop_ocr_candidate_review import (
            create_ocr_candidate_review_dialog,
        )

        self._ocr_review_parent = parent
        self._ocr_review_handoff = handoff
        self._ocr_managed_photo_source = managed_photo_source
        self._ocr_review_dialog = create_ocr_candidate_review_dialog(
            parent=parent,
            report=handoff.report,
            review_controller=handoff.review_controller,
            reviewer_id="desktop-collector",
            on_close=self._open_ocr_conflict_review,
        )

    def _open_ocr_conflict_review(self, reviews):
        """Open conflict review after candidate review when needed."""

        handoff = self._ocr_review_handoff
        from capture_import.workflow_ocr_review_models import OCRReportReview

        report_review = OCRReportReview(
            reviewer_id="desktop-collector",
            field_reviews=tuple(reviews),
        )
        self._ocr_report_review = report_review
        from capture_import.desktop_ocr_conflict_review import (
            OCRConflictReviewModel,
            create_ocr_conflict_review_dialog,
        )

        conflict_model = OCRConflictReviewModel(
            report=handoff.report,
            review=report_review,
            review_controller=handoff.review_controller,
        )
        if not conflict_model.conflict_count:
            self._confirm_and_save_ocr_review(report_review, ())
            return

        self._ocr_conflict_dialog = create_ocr_conflict_review_dialog(
            parent=self._ocr_review_parent,
            report=handoff.report,
            review=report_review,
            review_controller=handoff.review_controller,
            on_close=lambda resolutions: self._confirm_and_save_ocr_review(
                report_review,
                resolutions,
            ),
        )

    def _confirm_and_save_ocr_review(self, report_review, resolutions):
        """Require explicit confirmation before one reviewed coin is saved."""

        from capture_import.reviewed_coin_collection_entry import (
            ReviewedCoinCollectionEntryError,
            ReviewedCoinRecoveryRequiredError,
            create_reviewed_coin_draft,
            persist_reviewed_coin,
        )

        handoff = self._ocr_review_handoff
        try:
            draft = create_reviewed_coin_draft(
                source_report=handoff.report,
                report_review=report_review,
                conflict_resolutions=tuple(resolutions),
            )
        except (ReviewedCoinCollectionEntryError, TypeError, ValueError) as error:
            messagebox.showwarning(
                "OCR Review Incomplete",
                str(error),
                parent=self._ocr_review_parent,
            )
            self._release_ocr_managed_photo_source()
            return

        duplicates = self.app.collection.find_matching_coins(
            draft.country,
            draft.denomination,
            draft.year,
        )
        details = [
            "Save this operator-confirmed coin to the collection?",
            "",
            f"Country: {draft.country}",
            f"Denomination: {draft.denomination}",
            f"Year: {draft.year}",
            "Grade: not recorded",
            (
                "Images: obverse and reverse will be retained"
                if getattr(self, "_ocr_managed_photo_source", None)
                is not None
                else "Images: not supplied by this workflow"
            ),
        ]
        if draft.unmapped_fields:
            details.extend(
                (
                    "",
                    "Reviewed fields not stored: "
                    + ", ".join(name for name, _value in draft.unmapped_fields),
                )
            )
        if duplicates:
            details.extend(
                (
                    "",
                    f"Possible matching collection record(s): {len(duplicates)}",
                )
            )
        if not messagebox.askyesno(
            "Confirm Reviewed Coin",
            "\n".join(details),
            parent=self._ocr_review_parent,
        ):
            self._release_ocr_managed_photo_source()
            return

        try:
            item = persist_reviewed_coin(
                collection=self.app.collection,
                draft=draft,
                source_package_path=(
                    self._ocr_managed_photo_source.path
                    if getattr(self, "_ocr_managed_photo_source", None)
                    is not None
                    else None
                ),
            )
        except ReviewedCoinRecoveryRequiredError as error:
            messagebox.showerror(
                "Reviewed Coin Recovery Required",
                error.safe_message,
                parent=self._ocr_review_parent,
            )
            self._release_ocr_managed_photo_source()
            return
        except (ReviewedCoinCollectionEntryError, TypeError, ValueError):
            messagebox.showerror(
                "Collection Save Failed",
                "The reviewed coin could not be saved. "
                "No collection changes were confirmed.",
                parent=self._ocr_review_parent,
            )
            self._release_ocr_managed_photo_source()
            return

        self._release_ocr_managed_photo_source()
        self.refresh_collection_list()
        messagebox.showinfo(
            "Reviewed Coin Saved",
            f"Saved {item.country} {item.denomination} ({item.year}).",
            parent=self._ocr_review_parent,
        )

    def _release_ocr_managed_photo_source(self):
        source = getattr(self, "_ocr_managed_photo_source", None)
        self._ocr_managed_photo_source = None
        if source is not None:
            source.release()

    def initialize_capture_import_recovery(self) -> bool:
        """Complete fail-closed importer recovery before enabling package import."""

        self.capture_import_ready = False
        self.capture_import_recovery = None
        self.capture_import_coordinator = None
        try:
            recovery, coordinator = build_default_import_services(self.app.collection)
            recovery.reconcile_pending_imports()
        except CaptureImportError as error:
            self.capture_import_recovery_message = error.safe_message
            return False
        except Exception as error:
            self.capture_import_recovery_message = RecoveryRequired(error).safe_message
            return False
        self.capture_import_recovery = recovery
        self.capture_import_coordinator = coordinator
        self.capture_import_recovery_message = ""
        self.capture_import_ready = True
        return True

    def capture_import_menu_state(self):
        """Return the Tk state that reflects startup recovery readiness."""

        return tk.NORMAL if self.capture_import_ready else tk.DISABLED

    @staticmethod
    def acquisition_values_from_text(values):
        """Validate acquisition-entry strings and return normalized model values."""
        return normalize_acquisition_values(values)

    @classmethod
    def manual_item_values_from_text(cls, values):
        """Map manual form text to validated authoritative record values."""
        item_type = CoinItem._closed_enum(
            ItemType, values.get("item_type", ItemType.COIN.value), "item_type"
        )
        disposition = CoinItem._closed_enum(
            Disposition,
            values.get("disposition", Disposition.UNDECIDED.value),
            "disposition",
        )
        identity = {
            name: str(values.get(name) or "").strip()
            for name in ("country", "issuer", "denomination", "year", "reference")
        }
        mapped = {
            **identity,
            "grade": str(values.get("grade") or "").strip(),
            "notes": str(values.get("notes") or "").strip(),
            "title": str(values.get("title") or "").strip(),
            "item_type": item_type,
            "disposition": disposition,
            "identification_status": cls.truthful_manual_identification_status(
                identity
            ),
        }
        mapped.update(cls.acquisition_values_from_text(values))
        return mapped

    _IDENTITY_PLACEHOLDERS = frozenset({
        "unknown",
        "n/a",
        "na",
        "none",
        "not applicable",
        "unidentified",
    })

    @classmethod
    def reliable_manual_identity_value(cls, value):
        """Return whether manual text is factual identity rather than a sentinel."""
        text = str(value or "").strip()
        return bool(text) and text.casefold() not in cls._IDENTITY_PLACEHOLDERS

    @classmethod
    def truthful_manual_identification_status(cls, values):
        """Derive manual-save status without changing any collector-entered fact."""
        reliable = {
            name: cls.reliable_manual_identity_value(values.get(name))
            for name in ("country", "issuer", "denomination", "year", "reference")
        }
        if reliable["reference"] or (
            (reliable["country"] or reliable["issuer"])
            and reliable["denomination"]
            and reliable["year"]
        ):
            return IdentificationStatus.IDENTIFIED
        if any(reliable.values()):
            return IdentificationStatus.PARTIAL
        return IdentificationStatus.UNIDENTIFIED

    @classmethod
    def manual_item_is_meaningful(cls, values, photos=()):
        """Reject creation drafts containing no collector artifact."""
        def photo_path(photo):
            return photo.get("path") if isinstance(photo, dict) else getattr(photo, "path", photo)

        has_photo = any(str(photo_path(photo) or "").strip() for photo in photos)
        has_identity = any(
            cls.reliable_manual_identity_value(values.get(name))
            for name in ("country", "issuer", "denomination", "year", "reference")
        )
        return bool(
            has_photo
            or has_identity
            or str(values.get("title") or "").strip()
            or str(values.get("notes") or "").strip()
        )

    @classmethod
    def acquisition_total_text(cls, values):
        """Return live total text without allowing a calculated value to become input."""
        try:
            parsed = cls.acquisition_values_from_text(values)
        except ValueError:
            return "Invalid"
        components = [parsed[name] for name in ("purchase_price", "shipping_cost", "buyers_premium", "tax")]
        if all(value is None for value in components):
            return "Not recorded"
        total = sum((value for value in components if value is not None), Decimal("0"))
        currency = parsed["purchase_currency"] or ""
        return " ".join(part for part in (currency, serialize_money(total)) if part)

    @staticmethod
    def portfolio_financial_summary_text(summary):
        """Format exact-cost and approximate-valuation metrics for the GUI."""
        roi = (
            f"{format(summary.estimated_roi_percent, 'f')}%"
            if summary.estimated_roi_percent is not None
            else "Unavailable"
        )
        exclusions = summary.comparison_exclusions
        return "\n".join([
            f"Records: {summary.collection_record_count}   Quantity: {summary.total_quantity_count}",
            (
                f"Acquisition-cost coverage: {summary.acquisition_cost_coverage_percent}% "
                f"({summary.acquisition_cost_record_count}/{summary.collection_record_count})   "
                f"Usable legacy-estimate coverage: {summary.usable_valuation_coverage_percent}% "
                f"({summary.usable_valuation_record_count}/{summary.collection_record_count})"
            ),
            (
                f"Acquisition-date coverage: {summary.acquisition_date_coverage_percent}% "
                f"({summary.acquisition_date_record_count}/{summary.collection_record_count})   "
                f"Acquisition-source coverage: {summary.acquisition_source_coverage_percent}% "
                f"({summary.acquisition_source_record_count}/{summary.collection_record_count})"
            ),
            f"Recorded acquisition costs by currency (no conversion): {summary.currency_totals_text()}",
            (
                f"Comparable CAD records: {summary.comparable_cad_record_count}/{summary.collection_record_count}   "
                f"Cost: CAD {format(summary.comparable_cad_cost, 'f')}   "
                "Approximate legacy estimated value: "
                f"CAD {format(summary.comparable_approximate_estimated_cad_value, 'f')}"
            ),
            (
                f"Estimated gain/loss: CAD {format(summary.estimated_gain_loss, 'f')}   "
                f"Estimated ROI: {roi}"
            ),
            (
                "Primary comparison exclusions: "
                f"no recorded cost {exclusions.get('no_recorded_acquisition_cost', 0)}; "
                f"non-CAD {exclusions.get('non_cad_currency', 0)}; "
                f"unspecified currency {exclusions.get('unspecified_currency', 0)}; "
                f"no usable estimate {exclusions.get('no_usable_valuation_estimate', 0)}."
            ),
        ])

    def create_acquisition_fields(self, parent, initial=None):
        """Create reusable acquisition controls and a read-only live total."""
        initial = initial or {}
        variables = {
            "acquisition_date": tk.StringVar(value=initial.get("acquisition_date") or ""),
            "purchase_price": tk.StringVar(value=serialize_money(initial.get("purchase_price")) or ""),
            "purchase_currency": tk.StringVar(value=initial.get("purchase_currency") or ""),
            "purchase_source": tk.StringVar(value=initial.get("purchase_source") or ""),
            "shipping_cost": tk.StringVar(value=serialize_money(initial.get("shipping_cost")) or ""),
            "buyers_premium": tk.StringVar(value=serialize_money(initial.get("buyers_premium")) or ""),
            "tax": tk.StringVar(value=serialize_money(initial.get("tax")) or ""),
        }
        rows = (
            ("Date (YYYY-MM-DD):", "acquisition_date"),
            ("Price:", "purchase_price"),
            ("Currency:", "purchase_currency"),
            ("Source / Vendor:", "purchase_source"),
            ("Shipping:", "shipping_cost"),
            ("Buyer's Premium:", "buyers_premium"),
            ("Tax:", "tax"),
        )
        for field_index, (label, field_name) in enumerate(rows):
            field_row = field_index // 4
            column_index = field_index % 4
            label_row = field_row * 2
            ttk.Label(parent, text=label).grid(
                row=label_row,
                column=column_index,
                sticky=tk.W,
                padx=(0, 5),
            )
            ttk.Entry(parent, textvariable=variables[field_name], width=10).grid(
                row=label_row + 1,
                column=column_index,
                sticky=tk.W,
                padx=(0, 5),
                pady=(0, 2),
            )
        total_var = tk.StringVar(value="Not recorded")
        ttk.Label(parent, text="Total Cost:").grid(row=2, column=3, sticky=tk.W)
        ttk.Label(parent, textvariable=total_var).grid(
            row=3,
            column=3,
            sticky=tk.W,
            pady=(0, 2),
        )

        def current_text_values():
            return {name: variable.get() for name, variable in variables.items()}

        def refresh_total(*_args):
            total_var.set(self.acquisition_total_text(current_text_values()))

        for variable in variables.values():
            variable.trace_add("write", refresh_total)
        refresh_total()
        return {
            "variables": variables,
            "total_var": total_var,
            "values": current_text_values,
            "refresh_total": refresh_total,
        }
    
    def create_widgets(self):
        """Create all GUI widgets."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        # Left panel - Image and detection
        left_container = ttk.Frame(main_frame)
        left_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        left_container.columnconfigure(0, weight=1)
        left_container.rowconfigure(0, weight=1)

        left_canvas = tk.Canvas(left_container, highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(
            left_container,
            orient=tk.VERTICAL,
            command=left_canvas.yview,
        )
        left_canvas.configure(yscrollcommand=left_scrollbar.set)
        left_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        left_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        left_panel = ttk.Frame(left_canvas)
        left_window = left_canvas.create_window((0, 0), window=left_panel, anchor=tk.NW)
        left_panel.bind(
            "<Configure>",
            lambda _event: left_canvas.configure(scrollregion=left_canvas.bbox("all")),
        )
        left_canvas.bind(
            "<Configure>",
            lambda event: left_canvas.itemconfigure(left_window, width=event.width),
        )
        
        # Image section
        image_frame = ttk.LabelFrame(left_panel, text="Photos", padding="10")
        image_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Image display
        self.image_label = ttk.Label(image_frame, text="No photos selected", anchor=tk.CENTER)
        self.image_label.pack(fill=tk.BOTH, expand=True)
        
        # Image buttons
        button_frame = ttk.Frame(image_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="Add Photos", command=self.upload_image).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Remove", command=self.remove_selected_photo).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Set Primary", command=self.set_selected_photo_primary).pack(side=tk.LEFT)

        order_frame = ttk.Frame(image_frame)
        order_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(order_frame, text="Move Up", command=self.move_selected_photo_up).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(order_frame, text="Move Down", command=self.move_selected_photo_down).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(order_frame, text="Clear", command=self.clear_image).pack(side=tk.LEFT)

        self.photo_tree = ttk.Treeview(
            image_frame,
            columns=("primary", "role", "file"),
            show="headings",
            height=5,
        )
        self.photo_tree.heading("primary", text="Primary")
        self.photo_tree.heading("role", text="Role")
        self.photo_tree.heading("file", text="File")
        self.photo_tree.column("primary", width=55, anchor=tk.CENTER)
        self.photo_tree.column("role", width=105, anchor=tk.W)
        self.photo_tree.column("file", width=175, anchor=tk.W)
        self.photo_tree.pack(fill=tk.X, pady=(10, 0))
        self.photo_tree.bind("<<TreeviewSelect>>", self.on_photo_selected)

        photo_edit_frame = ttk.Frame(image_frame)
        photo_edit_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(photo_edit_frame, text="Role:").grid(row=0, column=0, sticky=tk.W)
        self.photo_role_var = tk.StringVar(value=PhotoRole.OTHER.value)
        self.photo_role_combo = ttk.Combobox(
            photo_edit_frame,
            textvariable=self.photo_role_var,
            values=self.get_photo_role_values(),
        )
        self.photo_role_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        self.photo_role_combo.bind("<<ComboboxSelected>>", self.update_selected_photo_role)
        self.photo_role_combo.bind("<FocusOut>", self.update_selected_photo_role)
        ttk.Label(photo_edit_frame, text="Notes:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.photo_notes_var = tk.StringVar()
        self.photo_notes_entry = ttk.Entry(photo_edit_frame, textvariable=self.photo_notes_var)
        self.photo_notes_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=(5, 0))
        self.photo_notes_entry.bind("<FocusOut>", self.update_selected_photo_notes)
        self.photo_notes_entry.bind("<Return>", self.update_selected_photo_notes)
        photo_edit_frame.columnconfigure(1, weight=1)
        
        # Detection section
        detection_frame = ttk.LabelFrame(left_panel, text="Experimental Detection (Suggestion Only)", padding="10")
        detection_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(detection_frame, text="Run Experimental Detector", command=self.run_detection).pack(fill=tk.X, pady=(0, 5))
        
        # Warning label
        warning_label = ttk.Label(detection_frame, text="⚠️ Results are experimental suggestions only", 
                                 foreground="red", font=("Arial", 9, "bold"))
        warning_label.pack(fill=tk.X, pady=(0, 5))
        
        # Detection results
        self.detection_label = ttk.Label(detection_frame, text="No detection results", wraplength=250)
        self.detection_label.pack(fill=tk.X)
        
        # Confidence display
        self.confidence_label = ttk.Label(detection_frame, text="", wraplength=250)
        self.confidence_label.pack(fill=tk.X)

        self.visual_review_handoff_button = ttk.Button(
            detection_frame,
            text="Review Attached Front + Back with AI...",
            command=self.review_attached_photos_with_visual_ai,
            state=tk.DISABLED,
        )
        self.visual_review_handoff_button.pack(fill=tk.X, pady=(5, 0))
        
        # Optional identifier toggle
        identifier_frame = ttk.LabelFrame(left_panel, text="Optional: Advanced Identification", padding="10")
        identifier_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.use_identifier_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(identifier_frame, text="Enable Template Matching (Experimental)", 
                       variable=self.use_identifier_var, command=self.toggle_identifier).pack(anchor=tk.W)
        
        ttk.Button(identifier_frame, text="Run Advanced ID", command=self.run_advanced_id).pack(fill=tk.X, pady=(5, 0))
        
        self.advanced_id_label = ttk.Label(identifier_frame, text="", wraplength=250)
        self.advanced_id_label.pack(fill=tk.X)
        
        # Right panel - Edit form and collection
        right_panel = ttk.Frame(main_frame)
        right_panel.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)
        
        # Edit form
        edit_frame = ttk.LabelFrame(right_panel, text="Item Details", padding="10")
        edit_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        edit_frame.columnconfigure(1, weight=1)

        type_frame = ttk.Frame(edit_frame)
        type_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        type_frame.columnconfigure(1, weight=1)
        type_frame.columnconfigure(3, weight=1)

        ttk.Label(type_frame, text="Item Type:").grid(row=0, column=0, sticky=tk.W)
        self.item_type_var = tk.StringVar(value=ItemType.COIN.value)
        ttk.Combobox(
            type_frame,
            textvariable=self.item_type_var,
            values=[value.value for value in ItemType],
            state="readonly",
        ).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 12))
        ttk.Label(type_frame, text="Disposition:").grid(row=0, column=2, sticky=tk.W)
        self.disposition_var = tk.StringVar(value=Disposition.UNDECIDED.value)
        ttk.Combobox(
            type_frame,
            textvariable=self.disposition_var,
            values=[value.value for value in Disposition],
            state="readonly",
        ).grid(row=0, column=3, sticky=(tk.W, tk.E), padx=(5, 0))

        ttk.Label(type_frame, text="Issuer:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.issuer_var = tk.StringVar()
        ttk.Entry(type_frame, textvariable=self.issuer_var).grid(
            row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 12), pady=(5, 0)
        )
        ttk.Label(type_frame, text="Identification:").grid(row=1, column=2, sticky=tk.W, pady=(5, 0))
        self.identification_status_var = tk.StringVar(value=IdentificationStatus.UNIDENTIFIED.value)
        ttk.Label(
            type_frame,
            textvariable=self.identification_status_var,
        ).grid(row=1, column=3, sticky=(tk.W, tk.E), padx=(5, 0), pady=(5, 0))

        ttk.Label(type_frame, text="Title:").grid(row=2, column=0, sticky=tk.W, pady=(5, 0))
        self.title_var = tk.StringVar()
        ttk.Entry(type_frame, textvariable=self.title_var).grid(
            row=2, column=1, sticky=(tk.W, tk.E), padx=(5, 12), pady=(5, 0)
        )
        ttk.Label(type_frame, text="Reference:").grid(row=2, column=2, sticky=tk.W, pady=(5, 0))
        self.reference_var = tk.StringVar()
        ttk.Entry(type_frame, textvariable=self.reference_var).grid(
            row=2, column=3, sticky=(tk.W, tk.E), padx=(5, 0), pady=(5, 0)
        )
        
        # Form fields
        ttk.Label(edit_frame, text="Country:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.country_var = tk.StringVar()
        self.country_combo = ttk.Combobox(
            edit_frame,
            textvariable=self.country_var,
            values=self.get_entry_suggestions("country"),
        )
        self.country_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        self.country_combo.bind('<KeyRelease>', lambda e: self.on_autocomplete('country', self.country_var.get()))
        self.country_combo.bind('<<ComboboxSelected>>', lambda e: self.on_country_changed())
        
        ttk.Label(edit_frame, text="Denomination:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.denomination_var = tk.StringVar()
        self.denomination_combo = ttk.Combobox(
            edit_frame,
            textvariable=self.denomination_var,
            values=self.get_entry_suggestions("denomination"),
        )
        self.denomination_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        self.denomination_combo.bind('<KeyRelease>', lambda e: self.on_autocomplete('denomination', self.denomination_var.get()))
        self.denomination_combo.bind('<<ComboboxSelected>>', lambda e: self.on_denomination_changed())
        
        ttk.Label(edit_frame, text="Year / Date / Series:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.year_var = tk.StringVar()
        self.year_combo = ttk.Combobox(
            edit_frame,
            textvariable=self.year_var,
            values=self.get_entry_suggestions("year"),
        )
        self.year_combo.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        self.year_combo.bind('<KeyRelease>', lambda e: self.on_autocomplete('year', self.year_var.get()))
        
        ttk.Label(edit_frame, text="Grade / Condition:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.grade_var = tk.StringVar()
        self.grade_combo = ttk.Combobox(edit_frame, textvariable=self.grade_var, values=GRADE_SUGGESTIONS)
        self.grade_combo.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        ttk.Label(edit_frame, text="Notes:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.notes_text = tk.Text(edit_frame, height=3, wrap=tk.WORD)
        self.notes_text.grid(row=5, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))

        acquisition_expanded = tk.BooleanVar(value=False)
        acquisition_button = ttk.Button(edit_frame, text="Acquisition Details ▸")
        acquisition_button.grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        acquisition_frame = ttk.LabelFrame(edit_frame, text="Acquisition Details", padding="4")
        acquisition_frame.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        self.acquisition_button = acquisition_button
        self.acquisition_frame = acquisition_frame
        self.acquisition_controls = self.create_acquisition_fields(
            acquisition_frame,
            {"purchase_currency": "CAD"},
        )
        acquisition_frame.grid_remove()

        def toggle_acquisition_details():
            expanded = not acquisition_expanded.get()
            acquisition_expanded.set(expanded)
            if expanded:
                acquisition_frame.grid()
                acquisition_button.config(text="Acquisition Details ▾")
            else:
                acquisition_frame.grid_remove()
                acquisition_button.config(text="Acquisition Details ▸")

        acquisition_button.config(command=toggle_acquisition_details)
        
        # Action buttons
        action_frame = ttk.Frame(edit_frame)
        action_frame.grid(row=8, column=0, columnspan=2, pady=(10, 0))
        
        ttk.Button(action_frame, text="Use Detection Results", command=self.use_detection_results).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_frame, text="Save to Collection", command=self.save_to_collection).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_frame, text="Clear Form", command=self.clear_form).pack(side=tk.LEFT)
        
        # Collection list
        collection_frame = ttk.LabelFrame(right_panel, text="Collection", padding="10")
        collection_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        collection_frame.columnconfigure(0, weight=1)
        collection_frame.rowconfigure(3, weight=1)
        
        # Search box
        search_frame = ttk.Frame(collection_frame)
        search_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        search_entry.bind('<KeyRelease>', self.on_search)
        ttk.Button(search_frame, text="Reset", command=self.reset_collection_browser).pack(side=tk.LEFT)

        filter_frame = ttk.Frame(collection_frame)
        filter_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        filter_specs = (
            ("Type:", "browser_type_var", BROWSER_TYPE_CHOICES),
            ("Disposition:", "browser_disposition_var", BROWSER_DISPOSITION_CHOICES),
            ("Identification:", "browser_identification_var", BROWSER_IDENTIFICATION_CHOICES),
        )
        for column, (label, attribute, choices) in enumerate(filter_specs):
            ttk.Label(filter_frame, text=label).grid(row=0, column=column * 2, sticky=tk.W, padx=(0 if column == 0 else 8, 3))
            variable = tk.StringVar(value="All")
            setattr(self, attribute, variable)
            combo = ttk.Combobox(
                filter_frame,
                textvariable=variable,
                values=tuple(choices),
                state="readonly",
                width=13,
            )
            combo.grid(row=0, column=column * 2 + 1, sticky=tk.W)
            combo.bind("<<ComboboxSelected>>", self.on_browser_criteria_changed)

        ttk.Label(filter_frame, text="Issuer/Country:").grid(row=1, column=0, sticky=tk.W, pady=(6, 0), padx=(0, 3))
        self.browser_issuer_country_var = tk.StringVar(value="All")
        self.browser_issuer_country_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.browser_issuer_country_var,
            values=("All",),
            state="readonly",
            width=24,
        )
        self.browser_issuer_country_combo.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=(6, 0))
        self.browser_issuer_country_combo.bind("<<ComboboxSelected>>", self.on_browser_criteria_changed)

        ttk.Label(filter_frame, text="Sort:").grid(row=1, column=3, sticky=tk.W, pady=(6, 0), padx=(8, 3))
        self.browser_sort_var = tk.StringVar(value="Collection order")
        sort_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.browser_sort_var,
            values=tuple(BROWSER_SORT_CHOICES),
            state="readonly",
            width=22,
        )
        sort_combo.grid(row=1, column=4, columnspan=2, sticky=(tk.W, tk.E), pady=(6, 0))
        sort_combo.bind("<<ComboboxSelected>>", self.on_browser_criteria_changed)
        filter_frame.columnconfigure(2, weight=1)

        # Collection buttons
        collection_buttons = ttk.Frame(collection_frame)
        collection_buttons.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Button(collection_buttons, text="View Details", command=self.view_item_details).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(collection_buttons, text="Edit Item", command=self.edit_item).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(collection_buttons, text="Delete Item", command=self.delete_item).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(collection_buttons, text="Buy Advisor", command=self.open_buy_advisor).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(collection_buttons, text="Import Numista", command=self.import_numista).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(collection_buttons, text="Analyze Collection", command=self.analyze_collection).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(collection_buttons, text="Gap Report", command=self.open_collection_gap_report).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(collection_buttons, text="Export CSV", command=self.export_csv).pack(side=tk.LEFT)

        # Collection list with scrollbar
        list_frame = ttk.Frame(collection_frame)
        list_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        horizontal_scrollbar = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL)
        horizontal_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))

        browser_columns = (
            "type", "issuer_country", "denomination", "date_series", "grade",
            "acquisition", "disposition", "identification_status",
        )
        self.collection_tree = ttk.Treeview(
            list_frame,
            columns=browser_columns,
            show="tree headings",
            yscrollcommand=scrollbar.set,
            xscrollcommand=horizontal_scrollbar.set,
        )
        headings = {
            "#0": "Photo", "type": "Type", "issuer_country": "Issuer / Country",
            "denomination": "Denomination", "date_series": "Date / Year / Series",
            "grade": "Grade / Condition", "acquisition": "Acquisition",
            "disposition": "Disposition", "identification_status": "Identification",
        }
        widths = {
            "#0": 64, "type": 72, "issuer_country": 170, "denomination": 110,
            "date_series": 125, "grade": 105, "acquisition": 175,
            "disposition": 95, "identification_status": 100,
        }
        for column in ("#0",) + browser_columns:
            self.collection_tree.heading(column, text=headings[column])
            self.collection_tree.column(column, width=widths[column], minwidth=55, stretch=column != "#0")
        
        self.collection_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.config(command=self.collection_tree.yview)
        horizontal_scrollbar.config(command=self.collection_tree.xview)
        
        self.collection_tree.bind("<<TreeviewSelect>>", self.on_collection_select)
        self.collection_tree.bind("<Double-1>", lambda _event: self.view_item_details())

        self.browser_result_count_var = tk.StringVar(value="0 items")
        ttk.Label(collection_frame, textvariable=self.browser_result_count_var, anchor=tk.E).grid(
            row=4, column=0, sticky=tk.E, pady=(5, 0)
        )

        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        status_frame.columnconfigure(0, weight=1)

        ttk.Label(
            status_frame,
            textvariable=self.session_status_var,
            anchor=tk.W,
            relief=tk.SUNKEN,
            padding=(6, 3),
        ).grid(row=0, column=0, sticky=(tk.W, tk.E))
        ttk.Label(
            status_frame,
            textvariable=self.photo_inbox_notification_var,
            anchor=tk.E,
            padding=(6, 3),
        ).grid(row=0, column=1, sticky=tk.E, padx=(8, 4))
        ttk.Button(
            status_frame,
            textvariable=self.photo_inbox_indicator_var,
            command=self.open_photo_inbox_from_indicator,
        ).grid(row=0, column=2, sticky=tk.E)

    def _collection_items(self):
        return self.app.collection.get_all_items()

    def _active_want_list_intents(self):
        return self.session_context.get_want_list_intents()

    def refresh_session_status(self):
        self.session_status_var.set(self.session_context.format_status_line())

    @staticmethod
    def photo_inbox_indicator_text(pending_count=0, error=""):
        """Return compact Photo Inbox indicator text."""
        if error:
            return "Photo Inbox (!)"
        try:
            count = int(pending_count or 0)
        except (TypeError, ValueError):
            count = 0
        return f"Photo Inbox ({count})" if count > 0 else "Photo Inbox"

    @staticmethod
    def photo_inbox_notification_text(pending_count):
        """Return passive startup notification text."""
        try:
            count = int(pending_count or 0)
        except (TypeError, ValueError):
            count = 0
        if count <= 0:
            return ""
        noun = "Photo Set" if count == 1 else "Photo Sets"
        return f"{count} pending {noun} ready to review."

    def get_photo_inbox_setting(self, key):
        """Read a Photo Inbox preference using Phase 2C defaults."""
        default = PHOTO_INBOX_SETTINGS_DEFAULTS.get(key, False)
        value = self.app_preferences.get(key, default)
        if isinstance(value, str):
            return value.strip().lower() not in {"0", "false", "no", "off"}
        return bool(value)

    def set_photo_inbox_setting(self, key, value):
        """Store a Photo Inbox preference in the existing app preference bag."""
        if key in PHOTO_INBOX_SETTINGS_DEFAULTS:
            self.app_preferences[key] = bool(value)
        return self.get_photo_inbox_setting(key)

    def photo_inbox_settings_snapshot(self):
        """Return current Photo Inbox notification settings."""
        return {
            key: self.get_photo_inbox_setting(key)
            for key in PHOTO_INBOX_SETTINGS_DEFAULTS
        }

    def update_photo_inbox_indicator(self, pending_count=0, error=""):
        """Update passive Photo Inbox awareness state."""
        try:
            count = int(pending_count or 0)
        except (TypeError, ValueError):
            count = 0
        self.photo_inbox_pending_count = max(0, count)
        self.photo_inbox_last_error = str(error or "")
        if hasattr(self, "photo_inbox_indicator_var"):
            self.photo_inbox_indicator_var.set(
                self.photo_inbox_indicator_text(self.photo_inbox_pending_count, self.photo_inbox_last_error)
            )
        if self.photo_inbox_last_error and hasattr(self, "photo_inbox_notification_var"):
            self.photo_inbox_notification_var.set("Photo Inbox unavailable.")

    @staticmethod
    def photo_inbox_pending_signature(rows):
        """Build a session-only signature for pending notification dismissal."""
        ids = sorted(str(row.get("id", "")) for row in rows or [] if row.get("id"))
        return "|".join(ids)

    def should_show_photo_inbox_startup_notification(self, rows):
        """Return whether a passive startup notification should be shown."""
        if not rows:
            return False
        if not self.get_photo_inbox_setting(PHOTO_INBOX_SETTING_STARTUP_NOTIFICATION):
            return False
        signature = self.photo_inbox_pending_signature(rows)
        return bool(signature and signature != self.photo_inbox_dismissed_notification_signature)

    def show_photo_inbox_startup_notification(self, rows):
        """Show a passive notification without opening windows or importing photos."""
        if not self.should_show_photo_inbox_startup_notification(rows):
            if hasattr(self, "photo_inbox_notification_var"):
                self.photo_inbox_notification_var.set("")
            return False
        signature = self.photo_inbox_pending_signature(rows)
        self.photo_inbox_active_notification_signature = signature
        if hasattr(self, "photo_inbox_notification_var"):
            self.photo_inbox_notification_var.set(self.photo_inbox_notification_text(len(rows)))
        return True

    def dismiss_photo_inbox_notification(self, signature=None):
        """Dismiss the current passive Photo Inbox notification for this session."""
        dismissed = signature or self.photo_inbox_active_notification_signature
        if dismissed:
            self.photo_inbox_dismissed_notification_signature = dismissed
        self.photo_inbox_active_notification_signature = ""
        if hasattr(self, "photo_inbox_notification_var"):
            self.photo_inbox_notification_var.set("")

    def refresh_photo_inbox_awareness(self, manager=None, scan=False, startup=False):
        """Refresh Photo Inbox count and optional startup notification."""
        manager = manager or PhotoInboxManager()
        try:
            if scan:
                manager.refresh()
            rows = self.photo_inbox_set_rows(manager)
            self.update_photo_inbox_indicator(len(rows))
            if startup:
                self.show_photo_inbox_startup_notification(rows)
            elif not rows and hasattr(self, "photo_inbox_notification_var"):
                self.photo_inbox_notification_var.set("")
            return {
                "success": True,
                "pending_count": len(rows),
                "error": "",
            }
        except Exception as exc:
            self.update_photo_inbox_indicator(0, error=str(exc))
            return {
                "success": False,
                "pending_count": 0,
                "error": str(exc),
            }

    def schedule_startup_photo_inbox_scan(self):
        """Schedule one startup scan after the main window has initialized."""
        if not self.get_photo_inbox_setting(PHOTO_INBOX_SETTING_SCAN_ON_STARTUP):
            self.refresh_photo_inbox_awareness(scan=False, startup=False)
            return False
        if hasattr(self.root, "after"):
            self.root.after(250, self.run_startup_photo_inbox_scan)
            return True
        self.run_startup_photo_inbox_scan()
        return True

    def run_startup_photo_inbox_scan(self):
        """Run the Phase 2C one-time startup Photo Inbox scan."""
        return self.refresh_photo_inbox_awareness(scan=True, startup=True)

    def open_photo_inbox_from_indicator(self):
        """Open Photo Inbox from the passive indicator and dismiss the notice."""
        self.dismiss_photo_inbox_notification()
        self.open_photo_inbox()

    def load_collection_context(self):
        """Load shared workbook and WANT_LIST context for this app session."""
        file_path = filedialog.askopenfilename(
            title="Select Collection Context Workbook",
            filetypes=[("Excel files", "*.xlsx *.xlsm *.xls"), ("All files", "*.*")]
        )
        if not file_path:
            return

        result = self.session_context.load_workbook_context(file_path, self._collection_items())
        self.refresh_session_status()
        if result.success:
            detail = self.session_context.format_status_line()
            if result.warnings:
                detail += "\n\nWarnings:\n" + "\n".join(f"- {warning}" for warning in result.warnings[:5])
            messagebox.showinfo("Collection Context Loaded", detail)
        else:
            messagebox.showerror("Collection Context Error", "\n".join(result.errors))

    def clear_session_context(self):
        """Clear workbook and WANT_LIST context for this app session."""
        self.session_context.clear()
        self.refresh_session_status()
        messagebox.showinfo("Session Context", "Session context cleared.")

    def save_session_state(self):
        """Persist current session state to local JSON."""
        state = self.persistence_manager.create_state(
            session_context=self.session_context,
            market_awareness_engine=self.market_awareness_engine,
            photo_records=self.photo_records,
            shopping_candidates=self.shopping_candidates,
            photo_candidates=self.photo_candidates,
            ocr_results=self.ocr_results,
            ocr_reports=self.ocr_reports,
            workflow_statuses=self.workflow_statuses,
            workflow_summaries=self.workflow_summaries,
            home_reports=self.home_reports,
            acknowledged_home_actions=self.acknowledged_home_actions,
            readiness_reports=self.readiness_reports,
            audit_summaries=self.audit_summaries,
            recent_deal_listings=self.recent_deal_listings,
            deal_hunter_reports=self.deal_hunter_reports,
            app_preferences=self.app_preferences,
        )
        result = self.persistence_manager.save_state(state)
        if result.success:
            detail = f"Session state saved to {result.path}"
            if result.backup_path:
                detail += f"\nBackup created: {result.backup_path}"
            if result.warnings:
                detail += "\n\nWarnings:\n" + "\n".join(f"- {warning}" for warning in result.warnings[:5])
            self.app_preferences["last_state_saved_at"] = state.saved_at
            self.refresh_session_status()
            messagebox.showinfo("Session State Saved", detail)
        else:
            messagebox.showerror("Session State Error", "\n".join(result.errors))

    def load_session_state(self):
        """Load previously saved local app state."""
        result = self.persistence_manager.load_state()
        if not result.success:
            messagebox.showerror("Session State Error", "\n".join(result.errors))
            return
        self._apply_loaded_app_state(result.state)
        detail = result.status
        if result.path:
            detail += f"\n{result.path}"
        if result.warnings:
            detail += "\n\nWarnings:\n" + "\n".join(f"- {warning}" for warning in result.warnings[:8])
        messagebox.showinfo("Session State Loaded", detail)

    def clear_saved_session_state(self):
        """Clear saved app state and reset runtime-only persisted context."""
        result = self.persistence_manager.clear_state()
        self.session_context.clear()
        self.market_awareness_engine = MarketAwarenessEngine()
        self.photo_records = []
        self.photo_candidates = []
        self.ocr_results = []
        self.ocr_reports = []
        self.shopping_candidates = []
        self.workflow_statuses = []
        self.workflow_summaries = []
        self.home_reports = []
        self.acknowledged_home_actions = []
        self.readiness_reports = []
        self.audit_summaries = []
        self.recent_deal_listings = []
        self.deal_hunter_reports = []
        self.app_preferences = {}
        self.refresh_session_status()
        if result.success:
            detail = result.status
            if result.backup_path:
                detail += f"\nBackup created: {result.backup_path}"
            messagebox.showinfo("Session State Cleared", detail)
        else:
            messagebox.showerror("Session State Error", "\n".join(result.errors))

    def export_session_state(self):
        """Export current app state to a selected JSON file."""
        file_path = filedialog.asksaveasfilename(
            title="Export Session State JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not file_path:
            return
        state = self.persistence_manager.create_state(
            session_context=self.session_context,
            market_awareness_engine=self.market_awareness_engine,
            photo_records=self.photo_records,
            shopping_candidates=self.shopping_candidates,
            photo_candidates=self.photo_candidates,
            ocr_results=self.ocr_results,
            ocr_reports=self.ocr_reports,
            workflow_statuses=self.workflow_statuses,
            workflow_summaries=self.workflow_summaries,
            home_reports=self.home_reports,
            acknowledged_home_actions=self.acknowledged_home_actions,
            readiness_reports=self.readiness_reports,
            audit_summaries=self.audit_summaries,
            recent_deal_listings=self.recent_deal_listings,
            deal_hunter_reports=self.deal_hunter_reports,
            app_preferences=self.app_preferences,
        )
        result = self.persistence_manager.export_state(file_path, state)
        if result.success:
            messagebox.showinfo("Session State Exported", f"Session state exported to {file_path}")
        else:
            messagebox.showerror("Session State Error", "\n".join(result.errors))

    def import_session_state(self):
        """Import app state from a selected JSON file."""
        file_path = filedialog.askopenfilename(
            title="Import Session State JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not file_path:
            return
        result = self.persistence_manager.import_state(file_path)
        if not result.success:
            messagebox.showerror("Session State Error", "\n".join(result.errors))
            return
        self._apply_loaded_app_state(result.state)
        detail = f"Session state imported from {file_path}"
        if result.warnings:
            detail += "\n\nWarnings:\n" + "\n".join(f"- {warning}" for warning in result.warnings[:8])
        messagebox.showinfo("Session State Imported", detail)

    def _apply_loaded_app_state(self, state):
        """Apply loaded app state to runtime objects without modifying collection data."""
        if not state:
            return
        self.session_context = state.session_context or SessionContext()
        if state.collection_workbook_path and os.path.exists(state.collection_workbook_path):
            self.session_context.load_workbook_context(state.collection_workbook_path, self._collection_items())
        elif state.collection_workbook_path:
            self.session_context.errors = [f"Workbook not found: {state.collection_workbook_path}"]
            self.session_context.load_status = "Saved workbook path missing"
        self.market_awareness_engine = state.market_awareness
        self.photo_records = list(state.photo_records)
        self.photo_candidates = list(getattr(state, "photo_candidates", []) or [])
        self.ocr_results = list(getattr(state, "ocr_results", []) or [])
        self.ocr_reports = list(getattr(state, "ocr_reports", []) or [])
        self.shopping_candidates = list(state.shopping_candidates)
        self.workflow_statuses = list(getattr(state, "workflow_statuses", []) or [])
        self.workflow_summaries = list(getattr(state, "workflow_summaries", []) or [])
        self.home_reports = list(getattr(state, "home_reports", []) or [])
        self.acknowledged_home_actions = list(getattr(state, "acknowledged_home_actions", []) or [])
        self.readiness_reports = list(getattr(state, "readiness_reports", []) or [])
        self.audit_summaries = list(getattr(state, "audit_summaries", []) or [])
        self.recent_deal_listings = list(getattr(state, "recent_deal_listings", []) or [])
        self.deal_hunter_reports = list(getattr(state, "deal_hunter_reports", []) or [])
        self.app_preferences = dict(state.app_preferences)
        self.refresh_session_status()

    def open_data_safety_check(self):
        """Show local app data safety validation report."""
        report = DataSafetyValidator(self.persistence_manager, self.backup_manager.backup_dir).validate()

        dialog = tk.Toplevel(self.root)
        dialog.title("Data Safety Check")
        dialog.geometry("850x650")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        text = tk.Text(main_frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, report.format_markdown())
        text.config(state=tk.DISABLED)

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(anchor=tk.W, pady=(10, 0))

    def open_collection_recovery_report(self):
        """Show what collection data is recoverable from the latest backup package."""
        report = self.backup_manager.collection_recovery_report()

        dialog = tk.Toplevel(self.root)
        dialog.title("Collection Recovery Report")
        dialog.geometry("850x650")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        text = tk.Text(main_frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, report.format_markdown())
        text.config(state=tk.DISABLED)

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(anchor=tk.W, pady=(10, 0))

    def open_collection_integrity_audit(self):
        """Show a read-only integrity audit for collection and related records."""
        report = CollectionIntegrityAudit(
            self._collection_items(),
            photo_records=self.photo_records,
            market_awareness_engine=self.market_awareness_engine,
            shopping_candidates=self.shopping_candidates,
            persistence_manager=self.persistence_manager,
            backup_manager=self.backup_manager,
        ).run()

        dialog = tk.Toplevel(self.root)
        dialog.title("Collection Integrity Audit")
        dialog.geometry("900x700")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        text = tk.Text(main_frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, report.format_markdown())
        text.config(state=tk.DISABLED)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(button_frame, text="Export Markdown", command=lambda: self.export_collection_integrity_report(report, "markdown")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Export CSV", command=lambda: self.export_collection_integrity_report(report, "csv")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_photo_vault_audit(self):
        """Show a read-only audit of Photo Vault metadata reliability."""
        report = PhotoVaultIntegrityAudit(
            self.photo_records,
            self._collection_items(),
            photo_candidates=self.photo_candidates,
        ).run()

        dialog = tk.Toplevel(self.root)
        dialog.title("Photo Vault Audit")
        dialog.geometry("900x700")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        text = tk.Text(main_frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, report.format_markdown())
        text.config(state=tk.DISABLED)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(button_frame, text="Export Markdown", command=lambda: self.export_photo_vault_audit(report, "markdown")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Export CSV", command=lambda: self.export_photo_vault_audit(report, "csv")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def export_photo_vault_audit(self, report, export_type):
        """Export the Photo Vault audit report."""
        extension = ".md" if export_type == "markdown" else ".csv"
        filetypes = [("Markdown files", "*.md")] if export_type == "markdown" else [("CSV files", "*.csv")]
        file_path = filedialog.asksaveasfilename(
            title="Export Photo Vault Audit",
            defaultextension=extension,
            filetypes=filetypes + [("All files", "*.*")],
        )
        if not file_path:
            return
        ok = report.export_markdown(file_path) if export_type == "markdown" else report.export_csv(file_path)
        if ok:
            messagebox.showinfo("Export Complete", f"Photo Vault audit exported to {file_path}")
        else:
            messagebox.showerror("Export Failed", "Could not export the Photo Vault audit.")

    def export_collection_integrity_report(self, report, export_type):
        """Export the current collection integrity report."""
        if export_type == "markdown":
            file_path = filedialog.asksaveasfilename(
                title="Export Collection Integrity Report Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
            )
            if file_path:
                report.export_markdown(file_path)
                messagebox.showinfo("Export Complete", f"Collection integrity report exported:\n{file_path}")
        else:
            file_path = filedialog.asksaveasfilename(
                title="Export Collection Integrity Report CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if file_path:
                report.export_csv(file_path)
                messagebox.showinfo("Export Complete", f"Collection integrity report exported:\n{file_path}")

    def create_collection_snapshot(self):
        """Create and persist a point-in-time collection snapshot."""
        snapshot = self.snapshot_manager.create_snapshot(
            self._collection_items(),
            want_list_intents=self._active_want_list_intents(),
            photo_records=self.photo_records,
            market_awareness_engine=self.market_awareness_engine,
            shopping_candidates=self.shopping_candidates,
        )
        self.snapshot_manager.save_snapshot(snapshot)
        messagebox.showinfo(
            "Snapshot Created",
            f"Snapshot saved:\n{snapshot.snapshot_timestamp}\n\nOwned items: {snapshot.collection_size}\nQuality: {snapshot.quality_score}\nIntegrity: {snapshot.integrity_score}"
        )

    def open_snapshot_report(self):
        """Show collection evolution from saved snapshots."""
        snapshots = self.snapshot_manager.load_snapshots()
        current = self.snapshot_manager.create_snapshot(
            self._collection_items(),
            want_list_intents=self._active_want_list_intents(),
            photo_records=self.photo_records,
            market_awareness_engine=self.market_awareness_engine,
            shopping_candidates=self.shopping_candidates,
        )
        previous = snapshots[-1] if snapshots else None
        first = snapshots[0] if snapshots else current
        report = self.snapshot_manager.compare_snapshots(current, previous, first)

        dialog = tk.Toplevel(self.root)
        dialog.title("Snapshot Report")
        dialog.geometry("900x700")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        text = tk.Text(main_frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, report.format_markdown())
        text.config(state=tk.DISABLED)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(button_frame, text="Export Markdown", command=lambda: self.export_snapshot_report(report, "markdown")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Export CSV", command=lambda: self.export_snapshot_report(report, "csv")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def export_snapshot_report(self, report, export_type):
        """Export the current snapshot report."""
        if export_type == "markdown":
            file_path = filedialog.asksaveasfilename(
                title="Export Snapshot Report Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
            )
            if file_path:
                report.export_markdown(file_path)
                messagebox.showinfo("Export Complete", f"Snapshot report exported:\n{file_path}")
        else:
            file_path = filedialog.asksaveasfilename(
                title="Export Snapshot Report CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if file_path:
                report.export_csv(file_path)
                messagebox.showinfo("Export Complete", f"Snapshot report exported:\n{file_path}")

    def create_backup_package(self):
        """Create a local backup package."""
        result = self.backup_manager.create_backup_package()
        if result.success:
            detail = f"Backup package created:\n{result.package_path}"
            if result.warnings:
                detail += "\n\nWarnings:\n" + "\n".join(f"- {warning}" for warning in result.warnings[:8])
            messagebox.showinfo("Backup Package Created", detail)
        else:
            messagebox.showerror("Backup Error", "\n".join(result.errors))

    def list_backup_packages(self):
        """List available local backup packages."""
        backups = self.backup_manager.list_available_backups()

        dialog = tk.Toplevel(self.root)
        dialog.title("Available Backups")
        dialog.geometry("850x500")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        text = tk.Text(main_frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        if backups:
            for backup in backups:
                text.insert(
                    tk.END,
                    f"{backup['name']}\n  Path: {backup['path']}\n  Size: {backup['size_bytes']} bytes\n  Modified: {backup['modified_at']}\n\n"
                )
        else:
            text.insert(tk.END, "No backup packages found.")
        text.config(state=tk.DISABLED)

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(anchor=tk.W, pady=(10, 0))

    def restore_backup_package(self):
        """Restore a package and activate any published collection fail closed."""
        file_path = filedialog.askopenfilename(
            title="Select Backup Package",
            filetypes=[("Zip files", "*.zip"), ("All files", "*.*")]
        )
        if not file_path:
            return
        verified = self.backup_manager.verify_backup_package(file_path)
        if not verified.success:
            messagebox.showerror("Backup Verification Failed", "\n".join(verified.errors))
            return
        if not messagebox.askyesno(
            "Restore Backup",
            "Restore the verified collection and/or app-state content from this "
            "backup?\n\nA pre-restore safety backup will be created first."
        ):
            return
        result = self.backup_manager.restore_from_backup_package(file_path, overwrite=True)
        collection_changed = self._restore_result_changed_collection(result)
        recovery_required = result.status == "Portable restore requires recovery"

        if recovery_required:
            self._enter_restore_recovery_state(result)
            return

        restored_item_count = None
        if collection_changed:
            try:
                restored_item_count = self._activate_restored_collection()
            except Exception as error:
                self._enter_restore_recovery_state(result, error)
                return

        if not result.success:
            detail = "\n".join(result.errors) or result.status
            if restored_item_count is not None:
                detail += (
                    f"\n\nThe restored authoritative collection was safely reloaded "
                    f"with {restored_item_count} item(s), but another restore step failed."
                )
            messagebox.showerror("Restore Error", detail)
            return

        session_warning = ""
        if self._restore_result_includes_path(
            result, self.persistence_manager.state_path
        ):
            load_result = self.persistence_manager.load_state()
            if load_result.success:
                try:
                    self._apply_loaded_app_state(load_result.state)
                except Exception as error:
                    session_warning = str(error) or type(error).__name__
            else:
                session_warning = "\n".join(load_result.errors) or load_result.status

        detail = (
            f"Restored files: {len(result.restored_files)}\n"
            f"Skipped files: {len(result.skipped_files)}"
        )
        if restored_item_count is not None:
            detail += f"\nActive collection items: {restored_item_count}"
        if result.pre_restore_backup_path:
            detail += f"\nPre-restore backup: {result.pre_restore_backup_path}"
        if session_warning:
            detail += (
                "\n\nThe collection restore is active and valid, but saved session "
                f"state could not be applied:\n{session_warning}"
            )
            messagebox.showwarning("Restore Complete with Warning", detail)
        else:
            messagebox.showinfo("Restore Complete", detail)

    def _restore_result_changed_collection(self, result) -> bool:
        """Return whether backend metadata reports authoritative publication."""

        return self._restore_result_includes_path(
            result, self.backup_manager.collection_json_path
        )

    @staticmethod
    def _restore_result_includes_path(result, expected_path) -> bool:
        """Match a backend-reported restored path independent of path spelling."""

        target = os.path.normcase(os.path.abspath(expected_path))
        return any(
            os.path.normcase(os.path.abspath(path)) == target
            for path in result.restored_files
        )

    @staticmethod
    def _invalidate_collection(collection, reason):
        """Make every retained reference to a superseded collection fail closed."""

        collection.load_state = CollectionLoadState.INVALID_OR_UNSUPPORTED
        collection.load_error = reason
        collection.last_save_error = reason

    @staticmethod
    def _blocked_collection(storage_path, reason):
        """Create a non-loading mutation guard when authoritative reload raises."""

        collection = CoinCollection.__new__(CoinCollection)
        collection.storage_path = storage_path
        collection.items = []
        collection.collection_format = None
        collection.load_state = CollectionLoadState.INVALID_OR_UNSUPPORTED
        collection.load_error = reason
        collection.last_save_error = reason
        return collection

    def _close_collection_edit_windows(self):
        """Invalidate edit dialogs whose controls were built from old records."""

        windows = list(getattr(self, "_collection_edit_windows", set()))
        self._collection_edit_windows = set()
        for dialog in windows:
            try:
                if dialog.winfo_exists():
                    dialog.destroy()
            except Exception:
                continue

    def _track_collection_edit_window(self, dialog):
        """Track an item-edit dialog until it is closed or restore invalidates it."""

        if not hasattr(self, "_collection_edit_windows"):
            self._collection_edit_windows = set()
        self._collection_edit_windows.add(dialog)

        def forget(event=None):
            if event is None or getattr(event, "widget", dialog) is dialog:
                self._collection_edit_windows.discard(dialog)

        dialog.bind("<Destroy>", forget, add="+")

    def _activate_restored_collection(self) -> int:
        """Load, bind, and refresh a published authoritative collection."""

        path = self.backup_manager.collection_json_path
        old_collection = self.app.collection
        superseded = "Superseded by authoritative collection restore"
        self._invalidate_collection(old_collection, superseded)
        self._close_collection_edit_windows()

        try:
            restored = CoinCollection(path)
        except Exception as error:
            reason = f"Restored authoritative collection reload failed: {error}"
            self.app.collection = self._blocked_collection(path, reason)
            raise RuntimeError(reason) from error
        self.app.collection = restored
        if restored.load_state is not CollectionLoadState.VALID:
            reason = (
                "Restored authoritative collection is not VALID: "
                f"{restored.load_error or restored.load_state.value}"
            )
            self._invalidate_collection(restored, reason)
            raise RuntimeError(reason)

        try:
            if not self.initialize_capture_import_recovery():
                raise RuntimeError(self.capture_import_recovery_message)
            self.clear_form()
            self.refresh_collection_list()
            self.refresh_entry_suggestions()
        except Exception as error:
            reason = f"Restored collection activation failed: {error}"
            self._invalidate_collection(restored, reason)
            raise RuntimeError(reason) from error
        return len(restored.items)

    def _enter_restore_recovery_state(self, result, activation_error=None):
        """Block mutation after publication whose GUI activation is not safe."""

        reason_parts = [
            str(error) for error in result.errors if str(error).strip()
        ]
        if activation_error is not None:
            reason_parts.append(str(activation_error) or type(activation_error).__name__)
        reason = "\n".join(reason_parts) or result.status

        current = self.app.collection
        self._invalidate_collection(current, reason)
        self._close_collection_edit_windows()
        self.capture_import_ready = False
        self.capture_import_recovery = None
        self.capture_import_coordinator = None
        safety_detail = (
            f"\nVerified pre-restore safety artifact:\n{result.pre_restore_backup_path}\n"
            if result.pre_restore_backup_path
            else "\n"
        )
        messagebox.showerror(
            "Portable Restore Requires Recovery",
            f"{reason}\n{safety_detail}\nOrdinary collection mutations are blocked. "
            "Retain the verified pre-restore safety artifact and recover the "
            "authoritative collection before continuing.",
        )
    
    @staticmethod
    def get_photo_role_values():
        """Return editable role suggestions for attached photos."""
        return [role.value for role in PhotoRole]

    @staticmethod
    def role_display_label(role):
        """Return collector-facing role text while preserving backend roles."""
        labels = {
            PhotoRole.FRONT: "Front / Obverse",
            PhotoRole.BACK: "Back / Reverse",
            PhotoRole.HOLDER_FRONT: "Holder Front",
            PhotoRole.HOLDER_BACK: "Holder Back",
            PhotoRole.EDGE: "Edge",
            PhotoRole.DETAIL: "Detail",
            PhotoRole.CERT_LABEL: "Certification Label",
            PhotoRole.OTHER: "Other",
        }
        return labels.get(PhotoRole.normalize(role), PhotoRole.OTHER.value)

    @staticmethod
    def default_photo_role(index):
        """Choose conservative first-pass roles for newly attached photos."""
        if index == 0:
            return PhotoRole.FRONT
        if index == 1:
            return PhotoRole.BACK
        return PhotoRole.OTHER

    @staticmethod
    def clone_photos(photos):
        """Copy photo metadata so edit dialogs can be cancelled safely."""
        return [
            ItemPhoto(
                path=photo.path,
                role=photo.role,
                is_primary=photo.is_primary,
                notes=photo.notes,
                display_order=photo.display_order,
            )
            for photo in CoinItem._coerce_photos(photos)
        ]

    @classmethod
    def normalized_photo_state(cls, photos):
        """Normalize GUI photo state without touching image files."""
        normalized = cls.clone_photos(photos)
        normalized = [photo for photo in normalized if photo.path]
        if not normalized:
            return []
        for index, photo in enumerate(normalized):
            photo.display_order = index
            photo.role = PhotoRole.normalize(photo.role)
        primary_index = next((index for index, photo in enumerate(normalized) if photo.is_primary), 0)
        for index, photo in enumerate(normalized):
            photo.is_primary = index == primary_index
        return normalized

    @classmethod
    def photos_from_item(cls, item):
        """Load normalized item photos, including legacy image_path-only records."""
        if not item:
            return []
        return cls.normalized_photo_state(item.normalized_photos())

    @classmethod
    def add_photo_paths_to_list(cls, photos, paths):
        """Add unique file paths to photo metadata and report skipped duplicates."""
        updated = cls.normalized_photo_state(photos)
        seen = {os.path.normcase(os.path.abspath(photo.path)) for photo in updated if photo.path}
        skipped = []
        for path in paths or []:
            clean_path = str(path or "").strip()
            if not clean_path:
                continue
            key = os.path.normcase(os.path.abspath(clean_path))
            if key in seen:
                skipped.append(clean_path)
                continue
            role = cls.default_photo_role(len(updated))
            updated.append(ItemPhoto(clean_path, role=role, is_primary=not updated, display_order=len(updated)))
            seen.add(key)
        return cls.normalized_photo_state(updated), skipped

    @classmethod
    def remove_photo_at_index(cls, photos, index):
        """Remove a photo reference only; source files are never deleted."""
        updated = cls.normalized_photo_state(photos)
        if index is None or index < 0 or index >= len(updated):
            return updated
        del updated[index]
        return cls.normalized_photo_state(updated)

    @classmethod
    def set_primary_photo_at_index(cls, photos, index):
        """Mark exactly one photo as primary."""
        updated = cls.normalized_photo_state(photos)
        if index is None or index < 0 or index >= len(updated):
            return updated
        for photo_index, photo in enumerate(updated):
            photo.is_primary = photo_index == index
        return cls.normalized_photo_state(updated)

    @classmethod
    def move_photo_at_index(cls, photos, index, offset):
        """Move a photo up or down while preserving the selected primary."""
        updated = cls.normalized_photo_state(photos)
        if index is None or index < 0 or index >= len(updated):
            return updated, index
        new_index = index + offset
        if new_index < 0 or new_index >= len(updated):
            return updated, index
        updated[index], updated[new_index] = updated[new_index], updated[index]
        return cls.normalized_photo_state(updated), new_index

    @classmethod
    def update_photo_role_at_index(cls, photos, index, role):
        """Update a selected photo role, normalizing unknown values to OTHER."""
        updated = cls.normalized_photo_state(photos)
        if index is not None and 0 <= index < len(updated):
            updated[index].role = PhotoRole.normalize(role)
        return cls.normalized_photo_state(updated)

    @classmethod
    def update_photo_notes_at_index(cls, photos, index, notes):
        """Update selected photo notes."""
        updated = cls.normalized_photo_state(photos)
        if index is not None and 0 <= index < len(updated):
            updated[index].notes = str(notes or "").strip()
        return cls.normalized_photo_state(updated)

    @staticmethod
    def photo_preview_status(photo):
        """Return display status for previewing a photo path."""
        if not photo or not photo.path:
            return "No photos selected"
        if not os.path.exists(photo.path):
            return "Image file not found"
        return ""

    @classmethod
    def photo_detail_rows(cls, photos):
        """Build stable detail rows for photo lists and tests."""
        return [
            {
                "primary": "*" if photo.is_primary else "",
                "role": photo.role.value,
                "label": cls.role_display_label(photo.role),
                "file": os.path.basename(photo.path),
                "path": photo.path,
                "notes": photo.notes,
                "status": cls.photo_preview_status(photo),
            }
            for photo in cls.normalized_photo_state(photos)
        ]

    @classmethod
    def item_details_text(cls, item):
        """Build details text shared by the gallery window and tests."""
        detail_photos = list(item.photos)
        if not detail_photos and item.image_path:
            detail_photos = [ItemPhoto(item.image_path, is_primary=True)]
        primary_path = project_collection((item,))[0].thumbnail_path
        details = [
            f"ID: {item.id}",
            f"Item Type: {item.item_type.value}",
            f"Disposition: {item.disposition.value}",
            f"Identification Status: {item.identification_status.value}",
            f"Updated At: {item.updated_at or 'Not recorded'}",
            f"Image: {primary_path}",
            f"Country: {item.country}",
            f"Issuer: {item.issuer}",
            f"Denomination: {item.denomination}",
            f"Year / Date / Series: {item.year}",
            f"Title: {item.title}",
            f"Reference: {item.reference}",
            f"Grade / Condition: {item.grade}",
            f"Notes: {item.notes}",
            f"Date Added: {item.date_added}",
        ]
        if item.from_numista:
            details.extend([
                "",
                "--- Numista Details ---",
                f"Numista N#: {item.numista_n}",
                f"Currency: {item.currency}",
                f"Face Value: {item.face_value}",
                f"Quantity: {item.quantity}",
                f"Estimate (CAD): ${item.estimate_cad:.2f}",
                f"Comments: {item.comments}",
            ])
        if item.has_acquisition_details():
            details.extend(["", "--- Acquisition Details ---"])
            if item.acquisition_date:
                details.append(f"Acquisition Date: {item.acquisition_date}")
            if item.purchase_price is not None:
                details.append(f"Purchase Price: {serialize_money(item.purchase_price)}")
            if item.purchase_currency:
                details.append(f"Purchase Currency: {item.purchase_currency}")
            if item.purchase_source:
                details.append(f"Purchase Source: {item.purchase_source}")
            if item.shipping_cost is not None:
                details.append(f"Shipping Cost: {serialize_money(item.shipping_cost)}")
            if item.buyers_premium is not None:
                details.append(f"Buyer's Premium: {serialize_money(item.buyers_premium)}")
            if item.tax is not None:
                details.append(f"Tax: {serialize_money(item.tax)}")
            if item.total_cost is not None:
                total = serialize_money(item.total_cost)
                details.append(f"Total Cost: {' '.join(part for part in (item.purchase_currency, total) if part)}")
        details.extend([
            "",
            "--- Detection Info ---",
            f"Auto Detected: {item.auto_detected}",
            f"Detection Confidence: {item.detection_confidence}",
        ])
        rows = cls.photo_detail_rows(detail_photos)
        details.extend(["", "--- Photos ---"])
        if rows:
            for row in rows:
                marker = "Primary" if row["primary"] else "Photo"
                status = f" ({row['status']})" if row["status"] else ""
                details.append(f"{marker}: {row['role']} - {row['path']}{status}")
                if row["notes"]:
                    details.append(f"Photo Notes: {row['notes']}")
        else:
            details.append("No photos attached")
        return "\n".join(details)

    def sync_current_image_path_from_photos(self):
        """Keep legacy single-image consumers pointed at the primary photo."""
        photos = self.normalized_photo_state(self.current_item_photos)
        self.current_item_photos = photos
        primary = next((photo for photo in photos if photo.is_primary), None)
        self.app.current_image_path = primary.path if primary else None

    def upload_image(self):
        """Attach one or more coin photos."""
        file_paths = filedialog.askopenfilenames(
            title="Select Item Photos",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"),
                ("All files", "*.*"),
            ],
        )
        if not file_paths:
            return
        self.current_item_photos, skipped = self.add_photo_paths_to_list(self.current_item_photos, file_paths)
        self.selected_photo_index = len(self.current_item_photos) - 1 if self.current_item_photos else None
        self.sync_current_image_path_from_photos()
        self.refresh_photo_list()
        self.display_selected_photo()
        if skipped:
            messagebox.showwarning("Duplicate Photos", f"Skipped {len(skipped)} duplicate photo reference(s).")
        elif self.current_item_photos:
            messagebox.showinfo("Success", "Photos attached successfully")
    
    def display_image(self, image_path):
        """Display image in GUI."""
        try:
            if not image_path or not os.path.exists(image_path):
                self.current_image = image_path
                self.current_photo = None
                self.image_label.config(image="", text="Image file not found")
                return
            # Load and resize image
            img = Image.open(image_path)
            img.thumbnail((400, 400))
            self.current_photo = ImageTk.PhotoImage(img)
            self.current_image = image_path
            
            self.image_label.config(image=self.current_photo, text="")
        except Exception as e:
            self.current_photo = None
            self.image_label.config(image="", text=f"Preview unavailable: {str(e)}")

    def refresh_photo_list(self):
        """Refresh attached-photo rows."""
        if not hasattr(self, "photo_tree"):
            return
        for row_id in self.photo_tree.get_children():
            self.photo_tree.delete(row_id)
        rows = self.photo_detail_rows(self.current_item_photos)
        for index, row in enumerate(rows):
            label = row["label"]
            if row["status"]:
                label = f"{label} ({row['status']})"
            self.photo_tree.insert("", tk.END, iid=str(index), values=(row["primary"], row["role"], row["file"] or row["path"]))
        if rows and self.selected_photo_index is not None and 0 <= self.selected_photo_index < len(rows):
            self.photo_tree.selection_set(str(self.selected_photo_index))
            self.photo_tree.focus(str(self.selected_photo_index))
        self.sync_selected_photo_edit_fields()
        self._set_visual_review_handoff_available(
            self.recognition_result_needs_paired_review(
                getattr(self, "detection_result", None)
            )
            and self.paired_visual_review_paths(self.current_item_photos) is not None
        )

    def sync_selected_photo_edit_fields(self):
        """Reflect selected photo metadata in the role and notes controls."""
        if not hasattr(self, "photo_role_var"):
            return
        photos = self.normalized_photo_state(self.current_item_photos)
        if self.selected_photo_index is not None and 0 <= self.selected_photo_index < len(photos):
            photo = photos[self.selected_photo_index]
            self.photo_role_var.set(photo.role.value)
            self.photo_notes_var.set(photo.notes)
        else:
            self.photo_role_var.set(PhotoRole.OTHER.value)
            self.photo_notes_var.set("")

    def on_photo_selected(self, event=None):
        """Handle attached-photo selection."""
        if not hasattr(self, "photo_tree"):
            return
        selection = self.photo_tree.selection()
        if not selection:
            return
        self.selected_photo_index = int(selection[0])
        self.sync_selected_photo_edit_fields()
        self.display_selected_photo()

    def display_selected_photo(self):
        """Display the currently selected photo, or the primary photo by default."""
        photos = self.normalized_photo_state(self.current_item_photos)
        if not photos:
            self.current_image = None
            self.current_photo = None
            self.image_label.config(image="", text="No photos selected")
            return
        if self.selected_photo_index is None or self.selected_photo_index >= len(photos):
            self.selected_photo_index = next((index for index, photo in enumerate(photos) if photo.is_primary), 0)
        self.display_image(photos[self.selected_photo_index].path)

    def remove_selected_photo(self):
        """Remove the selected photo reference from the form state."""
        self.current_item_photos = self.remove_photo_at_index(self.current_item_photos, self.selected_photo_index)
        if self.current_item_photos:
            self.selected_photo_index = min(self.selected_photo_index or 0, len(self.current_item_photos) - 1)
        else:
            self.selected_photo_index = None
        self.sync_current_image_path_from_photos()
        self.refresh_photo_list()
        self.display_selected_photo()

    def set_selected_photo_primary(self):
        """Mark the selected photo as primary."""
        self.current_item_photos = self.set_primary_photo_at_index(self.current_item_photos, self.selected_photo_index)
        self.sync_current_image_path_from_photos()
        self.refresh_photo_list()

    def move_selected_photo_up(self):
        """Move selected photo up."""
        self.current_item_photos, self.selected_photo_index = self.move_photo_at_index(
            self.current_item_photos,
            self.selected_photo_index,
            -1,
        )
        self.sync_current_image_path_from_photos()
        self.refresh_photo_list()
        self.display_selected_photo()

    def move_selected_photo_down(self):
        """Move selected photo down."""
        self.current_item_photos, self.selected_photo_index = self.move_photo_at_index(
            self.current_item_photos,
            self.selected_photo_index,
            1,
        )
        self.sync_current_image_path_from_photos()
        self.refresh_photo_list()
        self.display_selected_photo()

    def update_selected_photo_role(self, event=None):
        """Update selected photo role from the role combobox."""
        role = self.photo_role_var.get() if hasattr(self, "photo_role_var") else PhotoRole.OTHER.value
        self.current_item_photos = self.update_photo_role_at_index(
            self.current_item_photos,
            self.selected_photo_index,
            role,
        )
        self.refresh_photo_list()

    def update_selected_photo_notes(self, event=None):
        """Update selected photo notes from the notes entry."""
        notes = self.photo_notes_var.get() if hasattr(self, "photo_notes_var") else ""
        self.current_item_photos = self.update_photo_notes_at_index(
            self.current_item_photos,
            self.selected_photo_index,
            notes,
        )
        self.refresh_photo_list()
    
    def clear_image(self):
        """Clear current image and attached photo state."""
        self.current_image = None
        self.current_photo = None
        self.current_item_photos = []
        self.selected_photo_index = None
        if hasattr(self, "image_label"):
            self.image_label.config(image="", text="No photos selected")
        self.app.current_image_path = None
        self.detection_result = None
        if hasattr(self, "detection_label"):
            self.detection_label.config(text="No detection results")
        if hasattr(self, "confidence_label"):
            self.confidence_label.config(text="")
        self.refresh_photo_list()
    
    def run_detection(self):
        """Run denomination detector."""
        if not self.app.current_image_path:
            messagebox.showwarning("Warning", "Please upload an image first")
            return
        
        result = self.app.run_denomination_detector()
        self.detection_result = result
        
        if result['success']:
            text = f"Suggested Country: {result['country']}\n"
            text += f"Suggested Denomination: {result['denomination']}\n"
            text += f"Suggested Year: {result['year']}\n"

            needs_review = self.recognition_result_needs_paired_review(result)
            pair = self.paired_visual_review_paths(self.current_item_photos)
            if needs_review and pair:
                text += (
                    "\nLocal evidence is incomplete. You may review the attached "
                    "FRONT and BACK photos with AI."
                )
            elif needs_review:
                text += (
                    "\nLocal evidence is incomplete. Attach and label both FRONT "
                    "and BACK photos to enable paired review."
                )
            self.detection_label.config(text=text)
            self._set_visual_review_handoff_available(bool(needs_review and pair))
            
            confidence_text = f"Denomination Evidence Score: {result['confidence']:.2%}\n"
            confidence_text += f"Year Evidence Score: {result['year_confidence']:.2%}\n"
            confidence_text += "Source scores are not calibrated probabilities."
            self.confidence_label.config(text=confidence_text)
            
            # Log detection for debugging
            self.log_detection(result)
        else:
            self.detection_label.config(text=f"Detection failed: {result.get('error', 'Unknown error')}")
            self.confidence_label.config(text="")
            self._set_visual_review_handoff_available(False)

    @staticmethod
    def recognition_result_needs_paired_review(result):
        """Return whether a successful legacy result lacks a required identity field."""
        if not isinstance(result, dict) or not result.get("success"):
            return False
        missing_markers = {"", "none", "unknown"}
        return any(
            str(result.get(field) or "").strip().lower() in missing_markers
            for field in ("country", "denomination", "year")
        )

    @classmethod
    def paired_visual_review_paths(cls, photos):
        """Return explicitly labelled FRONT/BACK paths, or no pair."""
        by_role = {}
        for photo in cls.normalized_photo_state(photos):
            if photo.role in (PhotoRole.FRONT, PhotoRole.BACK) and photo.role not in by_role:
                by_role[photo.role] = photo.path
        front_path = by_role.get(PhotoRole.FRONT)
        reverse_path = by_role.get(PhotoRole.BACK)
        if not front_path or not reverse_path:
            return None
        return front_path, reverse_path

    def _set_visual_review_handoff_available(self, available):
        """Keep the optional paired-review action fail-closed."""
        button = getattr(self, "visual_review_handoff_button", None)
        if button is not None:
            button.config(state=tk.NORMAL if available else tk.DISABLED)

    def review_attached_photos_with_visual_ai(self):
        """Open the existing consent-controlled visual workflow for attached sides."""
        pair = self.paired_visual_review_paths(self.current_item_photos)
        if not pair:
            self._set_visual_review_handoff_available(False)
            messagebox.showwarning(
                "Paired Photos Required",
                "Attach and label one FRONT and one BACK photo before AI review.",
                parent=self.root,
            )
            return
        self.import_coin_images_with_visual_ai(
            front_path=pair[0],
            reverse_path=pair[1],
        )
    
    def toggle_identifier(self):
        """Toggle advanced identifier."""
        self.use_identifier = self.use_identifier_var.get()
        
        if self.use_identifier:
            try:
                self.identifier = CoinIdentifierFactory.create_identifier("template_matching")
                messagebox.showinfo("Info", "Template matching enabled (experimental)")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to enable identifier: {str(e)}")
                self.use_identifier_var.set(False)
                self.use_identifier = False
        else:
            self.identifier = None
    
    def run_advanced_id(self):
        """Run advanced identification."""
        if not self.use_identifier or not self.identifier:
            messagebox.showwarning("Warning", "Please enable advanced identification first")
            return
        
        if not self.app.current_image_path:
            messagebox.showwarning("Warning", "Please upload an image first")
            return
        
        try:
            result = self.identifier.identify_coin(self.app.current_image_path)
            
            if result['success']:
                text = f"Year: {result['year']}\n"
                text += f"Confidence: {result['confidence']:.2f}\n"
                text += f"Method: {result['method']}"
                self.advanced_id_label.config(text=text)
            else:
                self.advanced_id_label.config(text=f"Identification failed: {result.get('error', 'Unknown error')}")
        except Exception as e:
            messagebox.showerror("Error", f"Advanced identification failed: {str(e)}")
    
    def use_detection_results(self):
        """Use detection results to fill form as suggestions."""
        if not self.detection_result or not self.detection_result['success']:
            messagebox.showwarning("Warning", "No successful detection results available")
            return
        
        # Store original values for comparison
        original_country = self.country_var.get()
        original_denomination = self.denomination_var.get()
        original_year = self.year_var.get()
        
        # Pre-fill fields as suggestions only
        self.country_var.set(self.detection_result['country'])
        self.denomination_var.set(self.detection_result['denomination'])
        self.year_var.set(self.detection_result['year'])
        self.refresh_entry_suggestions()
        
        # Show warning that these are suggestions
        messagebox.showwarning("Experimental Suggestion", 
                             "Detection results pre-filled as suggestions only.\n"
                             "Please verify manually before saving.\n"
                             "These are NOT guaranteed to be correct.")
    
    def log_detection(self, detection_result):
        """Log detection results to debug feedback CSV."""
        import csv
        from datetime import datetime
        
        log_file = "data/debug_feedback.csv"
        
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        
        # Check if file exists, if not create with headers
        file_exists = os.path.exists(log_file)
        
        try:
            with open(log_file, 'a', newline='', encoding='utf-8') as f:
                fieldnames = ['timestamp', 'image_path', 'suggested_country', 
                            'suggested_denomination', 'suggested_year',
                            'denomination_confidence', 'year_confidence',
                            'corrected_country', 'corrected_denomination', 
                            'corrected_year', 'method']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                if not file_exists:
                    writer.writeheader()
                
                writer.writerow({
                    'timestamp': datetime.now().isoformat(),
                    'image_path': self.app.current_image_path,
                    'suggested_country': detection_result.get('country', 'unknown'),
                    'suggested_denomination': detection_result.get('denomination', 'unknown'),
                    'suggested_year': detection_result.get('year', 'unknown'),
                    'denomination_confidence': detection_result.get('confidence', 0.0),
                    'year_confidence': detection_result.get('year_confidence', 0.0),
                    'corrected_country': '',  # Will be filled when user saves
                    'corrected_denomination': '',  # Will be filled when user saves
                    'corrected_year': '',  # Will be filled when user saves
                    'method': detection_result.get('method', 'unknown')
                })
        except Exception as e:
            print(f"Error logging detection: {str(e)}")
    
    def save_to_collection(self):
        """Save the current manually reviewed item to the collection."""
        self.sync_current_image_path_from_photos()
        item_type_text = (
            self.item_type_var.get()
            if hasattr(self, "item_type_var")
            else ItemType.COIN.value
        )
        country = self.country_var.get().strip()
        denomination = self.denomination_var.get().strip()
        year = self.year_var.get().strip()
        grade = self.grade_var.get().strip()
        notes = self.notes_text.get("1.0", tk.END).strip()
        
        try:
            acquisition_text = (
                self.acquisition_controls["values"]()
                if hasattr(self, "acquisition_controls")
                else {"purchase_currency": "CAD"}
            )
            form_values = self.manual_item_values_from_text({
                **acquisition_text,
                "item_type": item_type_text,
                "disposition": (
                    self.disposition_var.get()
                    if hasattr(self, "disposition_var")
                    else Disposition.UNDECIDED.value
                ),
                "country": country,
                "issuer": self.issuer_var.get() if hasattr(self, "issuer_var") else "",
                "denomination": denomination,
                "year": year,
                "title": self.title_var.get() if hasattr(self, "title_var") else "",
                "reference": self.reference_var.get() if hasattr(self, "reference_var") else "",
                "grade": grade,
                "notes": notes,
            })
        except ValueError as error:
            messagebox.showwarning("Invalid Item Details", str(error))
            return
        
        # Never auto-save detector results as truth - manual fields are source of truth
        use_detection = False  # Always false - manual fields are source of truth
        
        photos = self.normalized_photo_state(self.current_item_photos)
        if not self.manual_item_is_meaningful(form_values, photos):
            messagebox.showwarning(
                "Incomplete Item",
                "Add a photo, factual identity, temporary title, reference, or meaningful notes before saving.",
            )
            return
        add_kwargs = {"photos": photos}
        if hasattr(self, "acquisition_controls"):
            add_kwargs.update({
                key: form_values[key]
                for key in (
                    "acquisition_date",
                    "purchase_price",
                    "purchase_currency",
                    "purchase_source",
                    "shipping_cost",
                    "buyers_premium",
                    "tax",
                )
            })
        if hasattr(self, "item_type_var"):
            add_kwargs.update({
                key: form_values[key]
                for key in (
                    "item_type",
                    "issuer",
                    "title",
                    "reference",
                    "disposition",
                    "identification_status",
                )
            })
        if self.app.add_to_collection(
            country,
            denomination,
            year,
            grade,
            notes,
            use_detection,
            **add_kwargs,
        ):
            if self.pending_inbox_manager and self.pending_inbox_photo_set_id:
                if not self.complete_pending_inbox_create(getattr(self.app, "last_added_item_id", "")):
                    messagebox.showwarning(
                        "Photo Inbox",
                        "Coin was saved, but the Photo Inbox set could not be marked attached.",
                    )
            # Log the corrected values if detection was used
            if (
                self.detection_result
                and self.detection_result['success']
                and form_values["identification_status"] is IdentificationStatus.IDENTIFIED
            ):
                self.record_detection_observation_after_save(country, denomination, year, photos)
                self.log_correction(country, denomination, year)
            
            messagebox.showinfo("Success", "Item added to collection")
            self.clear_form()
            self.refresh_collection_list()
        else:
            messagebox.showerror("Error", "Failed to add item to collection")

    def record_detection_observation_after_save(self, country, denomination, year, photos):
        """Persist a confirmed detection outcome after collection persistence succeeds."""
        if not self.detection_result or not self.detection_result.get("success"):
            return None
        observation = ConfirmedObservationRecord.for_detection_save(
            self.detection_result,
            {
                "country": country,
                "denomination": denomination,
                "year": year,
            },
            collection_item_id=getattr(self.app, "last_added_item_id", ""),
            application_version=APPLICATION_VERSION,
            photos=photos,
        )
        result = self.confirmed_observation_store.append(observation)
        if not result.success:
            messagebox.showwarning(
                "Collector Feedback",
                "Coin was saved, but its confirmed observation could not be recorded. "
                + "; ".join(result.errors or result.warnings or [result.status]),
            )
        return result
    
    def log_correction(self, corrected_country, corrected_denomination, corrected_year):
        """Log correction to debug feedback CSV."""
        import csv
        from datetime import datetime
        
        log_file = "data/debug_feedback.csv"
        
        try:
            # Read existing data
            rows = []
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
            
            # Update the last detection entry with corrections
            if rows:
                last_row = rows[-1]
                # Only update if this is the same image and hasn't been corrected yet
                if (last_row['image_path'] == self.app.current_image_path and 
                    not last_row['corrected_country']):
                    
                    last_row['corrected_country'] = corrected_country
                    last_row['corrected_denomination'] = corrected_denomination
                    last_row['corrected_year'] = corrected_year
                    
                    # Write back updated data
                    with open(log_file, 'w', newline='', encoding='utf-8') as f:
                        fieldnames = ['timestamp', 'image_path', 'suggested_country', 
                                    'suggested_denomination', 'suggested_year',
                                    'denomination_confidence', 'year_confidence',
                                    'corrected_country', 'corrected_denomination', 
                                    'corrected_year', 'method']
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(rows)
        except Exception as e:
            print(f"Error logging correction: {str(e)}")
    
    def clear_form(self):
        """Clear form fields."""
        if hasattr(self, "item_type_var"):
            self.item_type_var.set(ItemType.COIN.value)
        if hasattr(self, "disposition_var"):
            self.disposition_var.set(Disposition.UNDECIDED.value)
        if hasattr(self, "identification_status_var"):
            self.identification_status_var.set(IdentificationStatus.UNIDENTIFIED.value)
        for name in ("issuer_var", "title_var", "reference_var"):
            if hasattr(self, name):
                getattr(self, name).set("")
        self.country_var.set("")
        self.denomination_var.set("")
        self.year_var.set("")
        self.grade_var.set("")
        self.notes_text.delete("1.0", tk.END)
        if hasattr(self, "acquisition_controls"):
            for name, variable in self.acquisition_controls["variables"].items():
                variable.set("CAD" if name == "purchase_currency" else "")
        self.clear_image()
        self.clear_pending_inbox_create()
        self.refresh_entry_suggestions()
    
    def refresh_collection_list(self):
        """Rebuild the browser from a detached snapshot of the active collection."""
        for item in self.collection_tree.get_children():
            self.collection_tree.delete(item)
        self._browser_row_item_ids = {}
        self._browser_thumbnail_refs = {}

        collection = self.app.collection
        is_valid = collection.load_state is CollectionLoadState.VALID
        snapshot = tuple(collection.get_all_items()) if is_valid else ()
        self.refresh_browser_filter_options(snapshot)
        rows = project_collection(snapshot, self.browser_criteria()) if is_valid else ()

        for index, row in enumerate(rows):
            tree_id = f"browser-row-{index}"
            thumbnail = self.browser_thumbnail(row.thumbnail_path)
            self.collection_tree.insert(
                "",
                tk.END,
                iid=tree_id,
                text="",
                image=thumbnail,
                values=(
                    row.item_type,
                    row.issuer_country,
                    row.denomination,
                    row.date_series,
                    row.grade,
                    row.acquisition,
                    row.disposition,
                    row.identification_status,
                ),
            )
            self._browser_row_item_ids[tree_id] = row.item_id
            self._browser_thumbnail_refs[tree_id] = thumbnail
        if is_valid or collection.load_state is CollectionLoadState.MISSING:
            self.browser_result_count_var.set(f"{len(rows)} item{'s' if len(rows) != 1 else ''}")
        else:
            self.browser_result_count_var.set("Collection unavailable")

    def browser_criteria(self):
        """Translate controls into the closed Unit 6B criteria vocabulary."""
        issuer_or_country = self.browser_issuer_country_var.get()
        return CollectionBrowserCriteria(
            search_text=self.search_var.get(),
            item_type=BROWSER_TYPE_CHOICES[self.browser_type_var.get()],
            disposition=BROWSER_DISPOSITION_CHOICES[self.browser_disposition_var.get()],
            identification_status=BROWSER_IDENTIFICATION_CHOICES[
                self.browser_identification_var.get()
            ],
            issuer_or_country="" if issuer_or_country == "All" else issuer_or_country,
            sort_order=BROWSER_SORT_CHOICES[self.browser_sort_var.get()],
        )

    def refresh_browser_filter_options(self, snapshot):
        """Refresh the ephemeral issuer/country choices from factual values."""
        values = ("All",) + issuer_country_filter_options(snapshot)
        self.browser_issuer_country_combo.configure(values=values)
        if self.browser_issuer_country_var.get() not in values:
            self.browser_issuer_country_var.set("All")

    def browser_thumbnail(self, path):
        """Create one read-only in-memory browser thumbnail or neutral fallback."""
        if path:
            try:
                with Image.open(path) as source:
                    image = source.convert("RGB")
                    image.thumbnail((48, 48), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(image)
            except Exception:
                pass
        if self._browser_fallback_thumbnail is None:
            fallback = Image.new("RGB", (48, 48), "#d9d9d9")
            self._browser_fallback_thumbnail = ImageTk.PhotoImage(fallback)
        return self._browser_fallback_thumbnail
    
    def on_search(self, event):
        """Handle search input."""
        self.refresh_collection_list()

    def on_browser_criteria_changed(self, event=None):
        """Refresh after a filter or sort selection."""
        self.refresh_collection_list()
    
    def clear_search(self):
        """Clear search and show all items."""
        self.search_var.set("")
        self.refresh_collection_list()

    def reset_collection_browser(self):
        """Restore the default unfiltered collection-order browser state."""
        self.search_var.set("")
        self.browser_type_var.set("All")
        self.browser_disposition_var.set("All")
        self.browser_identification_var.set("All")
        self.browser_issuer_country_var.set("All")
        self.browser_sort_var.set("Collection order")
        self.refresh_collection_list()

    def get_entry_suggestions(self, field: str, query: str = ""):
        """Return main entry suggestions without restricting manual entry."""
        if field == "grade":
            return list(GRADE_SUGGESTIONS)
        country = ""
        denomination = ""
        if field == "denomination":
            country = self.country_var.get() if hasattr(self, "country_var") else ""
        elif field == "year":
            country = self.country_var.get() if hasattr(self, "country_var") else ""
            denomination = self.denomination_var.get() if hasattr(self, "denomination_var") else ""
        return self.app.collection.get_field_suggestions(
            field,
            query=query,
            country=country,
            denomination=denomination,
        )

    def refresh_entry_suggestions(self):
        """Refresh editable combobox values from current collection context."""
        if hasattr(self, "country_combo"):
            self.country_combo["values"] = self.get_entry_suggestions("country")
        if hasattr(self, "denomination_combo"):
            self.denomination_combo["values"] = self.get_entry_suggestions("denomination")
        if hasattr(self, "year_combo"):
            self.year_combo["values"] = self.get_entry_suggestions("year")
        if hasattr(self, "grade_combo"):
            self.grade_combo["values"] = self.get_entry_suggestions("grade")

    def on_country_changed(self):
        """Update dependent suggestions after country changes."""
        if hasattr(self, "denomination_combo"):
            self.denomination_combo["values"] = self.get_entry_suggestions("denomination")
        if hasattr(self, "year_combo"):
            self.year_combo["values"] = self.get_entry_suggestions("year")

    def on_denomination_changed(self):
        """Update year suggestions after denomination changes."""
        if hasattr(self, "year_combo"):
            self.year_combo["values"] = self.get_entry_suggestions("year")
    
    def on_autocomplete(self, field: str, query: str):
        """Handle autocomplete for form fields."""
        if field == "country" and hasattr(self, "country_combo"):
            self.country_combo["values"] = self.get_entry_suggestions("country", query=query)
            self.on_country_changed()
        elif field == "denomination" and hasattr(self, "denomination_combo"):
            self.denomination_combo["values"] = self.get_entry_suggestions("denomination", query=query)
            self.on_denomination_changed()
        elif field == "year" and hasattr(self, "year_combo"):
            self.year_combo["values"] = self.get_entry_suggestions("year", query=query)
    
    def analyze_collection(self):
        """Analyze collection for gaps and patterns."""
        analysis = self.app.collection.analyze_collection_gaps()
        
        # Create analysis dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Collection Analysis")
        dialog.geometry("600x400")
        
        text = tk.Text(dialog, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        
        report = f"=== Collection Analysis ===\n\n"
        report += f"Total Coins: {analysis['total_coins']}\n"
        report += f"Numista Coverage: {analysis['numista_coverage']:.1f}%\n\n"
        
        report += f"=== Countries ({len(analysis['countries'])}) ===\n"
        for country, count in sorted(analysis['countries'].items(), key=lambda x: x[1], reverse=True)[:10]:
            report += f"  {country}: {count}\n"
        
        report += f"\n=== Years ({len(analysis['years'])}) ===\n"
        for year, count in sorted(analysis['years'].items(), key=lambda x: x[0])[:10]:
            report += f"  {year}: {count}\n"
        
        report += f"\n=== Denominations ({len(analysis['denominations'])}) ===\n"
        for denom, count in sorted(analysis['denominations'].items(), key=lambda x: x[1], reverse=True)[:10]:
            report += f"  {denom}: {count}\n"
        
        text.insert(tk.END, report)
        text.config(state=tk.DISABLED)

    def open_collection_gap_report(self):
        """Show collection gap report and allow Markdown/CSV export."""
        engine = CollectionIntelligenceEngine(self.app.collection.get_all_items())
        report_text = engine.format_gap_report_text()

        dialog = tk.Toplevel(self.root)
        dialog.title("Collection Gap Report")
        dialog.geometry("800x600")

        ttk.Label(
            dialog,
            text=self.session_context.format_status_line(),
            padding=(10, 8),
        ).pack(fill=tk.X)

        text = tk.Text(dialog, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, report_text)
        text.config(state=tk.DISABLED)

        button_frame = ttk.Frame(dialog, padding="10")
        button_frame.pack(fill=tk.X)

        def export_markdown():
            file_path = filedialog.asksaveasfilename(
                title="Export Collection Gap Report",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
            )
            if not file_path:
                return
            if engine.export_gap_report_markdown(file_path):
                messagebox.showinfo("Success", f"Gap report exported to {file_path}")
            else:
                messagebox.showerror("Error", "Failed to export gap report")

        def export_csv():
            file_path = filedialog.asksaveasfilename(
                title="Export Collection Gap Report CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not file_path:
                return
            if engine.export_gap_report_csv(file_path):
                messagebox.showinfo("Success", f"Gap report CSV exported to {file_path}")
            else:
                messagebox.showerror("Error", "Failed to export gap report CSV")

        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_want_list_generator(self):
        """Show ranked acquisition targets and allow Markdown/CSV export."""
        engine = CollectionIntelligenceEngine(self.app.collection.get_all_items())
        staged_want_list_intents = self._active_want_list_intents()

        dialog = tk.Toplevel(self.root)
        dialog.title("Want List Generator")
        dialog.geometry("1000x600")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        if staged_want_list_intents:
            status_text = f"Using shared WANT_LIST context: {len(staged_want_list_intents)} active intent(s)."
        else:
            status_text = "Using current collection analysis only. No shared WANT_LIST loaded."
        status_var = tk.StringVar(value=status_text)
        ttk.Label(main_frame, textvariable=status_var).grid(row=0, column=0, sticky=tk.W, pady=(0, 10))

        columns = ("Rank", "Coin", "Priority Score", "Reason")
        target_tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=15)
        for column in columns:
            target_tree.heading(column, text=column)
            width = 90
            if column == "Coin":
                width = 260
            elif column == "Reason":
                width = 520
            target_tree.column(column, width=width, anchor=tk.W)

        y_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=target_tree.yview)
        x_scrollbar = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL, command=target_tree.xview)
        target_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        target_tree.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        y_scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))
        x_scrollbar.grid(row=2, column=0, sticky=(tk.W, tk.E))

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, sticky=tk.W, pady=(10, 0))

        def current_targets():
            return engine.generate_want_list(
                limit=10,
                staged_want_list_intents=staged_want_list_intents,
            )

        def refresh_targets():
            for row in target_tree.get_children():
                target_tree.delete(row)
            for rank, target in enumerate(current_targets(), 1):
                target_tree.insert(
                    "",
                    tk.END,
                    values=(rank, target.coin_label, target.priority_score, target.reason)
                )

        def load_want_list_workbook():
            nonlocal staged_want_list_intents
            file_path = filedialog.askopenfilename(
                title="Select Legacy Portfolio Workbook",
                filetypes=[("Excel files", "*.xlsx *.xlsm *.xls"), ("All files", "*.*")]
            )
            if not file_path:
                return
            try:
                importer = LegacyPortfolioImporter(self.app.collection.get_all_items())
                preview = importer.preview_want_list(file_path)
                staged_want_list_intents = preview.staged_intents
                self.session_context.load_want_list_context(file_path, self._collection_items())
                self.refresh_session_status()
                status_var.set(
                    f"Loaded {preview.intents_staged} staged WANT_LIST intents from {os.path.basename(file_path)}."
                )
                refresh_targets()
            except Exception as e:
                messagebox.showerror(
                    "Want List Generator Error",
                    f"Failed to load workbook WANT_LIST: {str(e)}"
                )

        def export_markdown():
            file_path = filedialog.asksaveasfilename(
                title="Export Want List",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
            )
            if not file_path:
                return
            if engine.export_want_list_markdown(
                file_path,
                limit=10,
                staged_want_list_intents=staged_want_list_intents,
            ):
                messagebox.showinfo("Success", f"Want list exported to {file_path}")
            else:
                messagebox.showerror("Error", "Failed to export want list")

        def export_csv():
            file_path = filedialog.asksaveasfilename(
                title="Export Want List CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not file_path:
                return
            if engine.export_want_list_csv(
                file_path,
                limit=10,
                staged_want_list_intents=staged_want_list_intents,
            ):
                messagebox.showinfo("Success", f"Want list CSV exported to {file_path}")
            else:
                messagebox.showerror("Error", "Failed to export want list CSV")

        ttk.Button(button_frame, text="Load Staged WANT_LIST", command=load_want_list_workbook).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)
        refresh_targets()

    def open_collection_dashboard(self):
        """Open actionable Collection Dashboard dialog."""
        dashboard = CollectionDashboard(
            self._collection_items(),
            self._active_want_list_intents(),
            photo_records=self.photo_records,
            market_awareness_engine=self.market_awareness_engine,
            shopping_candidates=self.shopping_candidates,
        )

        dialog = tk.Toplevel(self.root)
        dialog.title("Collection Dashboard")
        dialog.geometry("900x700")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            main_frame,
            text=self.session_context.format_status_line(),
            padding=(0, 0, 0, 8),
        ).pack(fill=tk.X)

        text = tk.Text(main_frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, dashboard.format_markdown())
        text.config(state=tk.DISABLED)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def export_csv():
            file_path = filedialog.asksaveasfilename(
                title="Export Collection Dashboard CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not file_path:
                return
            if dashboard.export_csv(file_path):
                messagebox.showinfo("Success", f"Collection dashboard CSV exported to {file_path}")
            else:
                messagebox.showerror("Error", "Failed to export collection dashboard CSV")

        def export_markdown():
            file_path = filedialog.asksaveasfilename(
                title="Export Collection Dashboard Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
            )
            if not file_path:
                return
            if dashboard.export_markdown(file_path):
                messagebox.showinfo("Success", f"Collection dashboard Markdown exported to {file_path}")
            else:
                messagebox.showerror("Error", "Failed to export collection dashboard Markdown")

        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_collector_home(self):
        """Open unified Collector Home dialog."""
        home = CollectorHome(
            self._collection_items(),
            self._active_want_list_intents(),
            self.shopping_candidates,
            market_awareness_engine=self.market_awareness_engine,
            photo_records=self.photo_records,
        )

        dialog = tk.Toplevel(self.root)
        dialog.title("Collector Home")
        dialog.geometry("900x700")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            main_frame,
            text=self.session_context.format_status_line(),
            padding=(0, 0, 0, 8),
        ).pack(fill=tk.X)

        text = tk.Text(main_frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, home.format_markdown())
        text.config(state=tk.DISABLED)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def export_csv():
            file_path = filedialog.asksaveasfilename(
                title="Export Collector Home CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not file_path:
                return
            if home.export_csv(file_path):
                messagebox.showinfo("Success", f"Collector Home CSV exported to {file_path}")
            else:
                messagebox.showerror("Error", "Failed to export Collector Home CSV")

        def export_markdown():
            file_path = filedialog.asksaveasfilename(
                title="Export Collector Home Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
            )
            if not file_path:
                return
            if home.export_markdown(file_path):
                messagebox.showinfo("Success", f"Collector Home Markdown exported to {file_path}")
            else:
                messagebox.showerror("Error", "Failed to export Collector Home Markdown")

        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    @staticmethod
    def photo_inbox_set_rows(manager):
        """Build stable rows for pending Photo Inbox sets."""
        rows = []
        for photo_set in manager.get_pending_sets():
            photos = manager.get_photo_set_photos(photo_set.id)
            rows.append({
                "id": photo_set.id,
                "state": photo_set.state.value,
                "photo_count": len(photos),
                "suggested_label": photo_set.suggested_label,
                "created_at": photo_set.created_at,
                "updated_at": photo_set.updated_at,
            })
        return rows

    @staticmethod
    def photo_inbox_photo_rows(manager, photo_set_id):
        """Build stable rows for photos in a selected Photo Inbox set."""
        rows = []
        for photo in manager.get_photo_set_photos(photo_set_id):
            rows.append({
                "filename": photo.filename,
                "state": photo.state.value,
                "path": photo.path,
                "first_seen_at": photo.first_seen_at,
                "error": photo.error,
            })
        return rows

    @staticmethod
    def photo_inbox_scan_summary(scan_result, pending_count):
        """Summarize a manual Photo Inbox refresh."""
        return (
            f"Pending sets: {pending_count} | "
            f"Discovered: {scan_result.discovered} | "
            f"Ready: {scan_result.ready} | "
            f"Stabilizing: {scan_result.stabilizing} | "
            f"Unsupported: {scan_result.unsupported} | "
            f"Duplicates: {scan_result.duplicates} | "
            f"Missing: {scan_result.missing}"
        )

    @staticmethod
    def can_create_new_from_inbox(rows, selected_set_id):
        """Return whether Create New should be available for the inbox selection."""
        return bool(rows and selected_set_id)

    @staticmethod
    def can_attach_existing_from_inbox(rows, selected_set_id):
        """Return whether Attach to Existing should be available for the inbox selection."""
        return bool(rows and selected_set_id)

    @staticmethod
    def normalized_photo_path_key(path):
        """Return a stable key for duplicate photo-reference checks."""
        return os.path.normcase(os.path.abspath(str(path or "").strip()))

    def item_photos_from_inbox_photo_set(self, manager, photo_set_id):
        """Convert a pending Photo Inbox set into entry-form photo metadata."""
        paths = [photo.path for photo in manager.get_photo_set_photos(photo_set_id)]
        return self.add_photo_paths_to_list([], paths)

    def search_attach_targets(self, query="", limit=25):
        """Find possible collection items for Photo Inbox attachment."""
        collection = getattr(self.app, "collection", None)
        if not collection:
            return []
        if str(query or "").strip():
            items = collection.search_items(query)
        else:
            items = collection.get_all_items()
        return list(items)[:limit]

    def attach_target_summary(self, item):
        """Build a concise target-item summary for confirmation and tests."""
        if not item:
            return "No target selected"
        photos = self.photos_from_item(item)
        primary = next((photo for photo in photos if photo.is_primary), None)
        lines = [
            f"ID: {item.id}",
            f"Item: {item.country} {item.denomination} {item.year}".strip(),
            f"Grade: {item.grade}",
            f"Photos: {len(photos)}",
            f"Primary image: {primary.path if primary else 'None'}",
        ]
        return "\n".join(lines)

    def merge_inbox_photos_into_item(self, item, manager, photo_set_id):
        """Append non-duplicate inbox photos while preserving existing item metadata."""
        existing = self.photos_from_item(item)
        seen = {self.normalized_photo_path_key(photo.path) for photo in existing if photo.path}
        merged = self.clone_photos(existing)
        skipped = []
        added = []
        for incoming_index, inbox_photo in enumerate(manager.get_photo_set_photos(photo_set_id)):
            clean_path = str(getattr(inbox_photo, "path", "") or "").strip()
            if not clean_path:
                continue
            key = self.normalized_photo_path_key(clean_path)
            if key in seen:
                skipped.append(clean_path)
                continue
            added.append(clean_path)
            merged.append(
                ItemPhoto(
                    path=clean_path,
                    role=self.default_photo_role(incoming_index),
                    is_primary=False,
                    display_order=len(merged),
                )
            )
            seen.add(key)
        return {
            "photos": self.normalized_photo_state(merged),
            "added_count": len(added),
            "skipped_count": len(skipped),
            "added_paths": added,
            "skipped_paths": skipped,
        }

    def attach_photo_set_to_item(self, manager, photo_set_id, item, refresh_callback=None):
        """Attach a Photo Inbox set to an existing item after a successful save."""
        if not manager or not photo_set_id or not item:
            return {
                "success": False,
                "added_count": 0,
                "skipped_count": 0,
                "error": "Select a collection item first.",
            }
        merge = self.merge_inbox_photos_into_item(item, manager, photo_set_id)
        if merge["added_count"] == 0:
            return {
                "success": False,
                "added_count": 0,
                "skipped_count": merge["skipped_count"],
                "error": "All photos in this Photo Set are already attached to the selected item.",
            }
        primary = next((photo for photo in merge["photos"] if photo.is_primary), None)
        collection = getattr(self.app, "collection", None)
        if not collection or not collection.update_item(
            item.id,
            {
                "photos": merge["photos"],
                "image_path": primary.path if primary else "",
            },
        ):
            return {
                "success": False,
                "added_count": merge["added_count"],
                "skipped_count": merge["skipped_count"],
                "error": "Could not save the attachment to the selected item.",
            }
        if not manager.mark_attached(photo_set_id, item_id=str(item.id or "")):
            return {
                "success": False,
                "added_count": merge["added_count"],
                "skipped_count": merge["skipped_count"],
                "error": "Photos were saved, but the Photo Inbox set could not be marked attached.",
            }
        if refresh_callback:
            refresh_callback()
        if hasattr(self, "refresh_collection_list"):
            self.refresh_collection_list()
        return {
            "success": True,
            "added_count": merge["added_count"],
            "skipped_count": merge["skipped_count"],
            "error": "",
        }

    def load_photo_set_into_entry_form(self, manager, photo_set_id, refresh_callback=None):
        """Preload a Photo Inbox set into the existing collection-entry form."""
        photos, skipped = self.item_photos_from_inbox_photo_set(manager, photo_set_id)
        if not photos:
            return False, skipped
        self.current_item_photos = photos
        self.selected_photo_index = 0
        self.pending_inbox_manager = manager
        self.pending_inbox_photo_set_id = str(photo_set_id)
        self.pending_inbox_refresh_callback = refresh_callback
        self.pending_inbox_completion_done = False
        self.sync_current_image_path_from_photos()
        self.refresh_photo_list()
        self.display_selected_photo()
        return True, skipped

    def complete_pending_inbox_create(self, item_id):
        """Mark the pending inbox set attached after a successful collection save."""
        if self.pending_inbox_completion_done:
            return False
        manager = self.pending_inbox_manager
        photo_set_id = self.pending_inbox_photo_set_id
        if not manager or not photo_set_id:
            return False
        if not manager.mark_attached(photo_set_id, item_id=str(item_id or "")):
            return False
        self.pending_inbox_completion_done = True
        self.pending_inbox_manager = None
        self.pending_inbox_photo_set_id = ""
        callback = self.pending_inbox_refresh_callback
        self.pending_inbox_refresh_callback = None
        if callback:
            callback()
        return True

    def clear_pending_inbox_create(self):
        """Forget pending inbox context without changing inbox state."""
        self.pending_inbox_manager = None
        self.pending_inbox_photo_set_id = ""
        self.pending_inbox_refresh_callback = None
        self.pending_inbox_completion_done = False

    def open_attach_photo_set_dialog(self, manager, photo_set_id, refresh_callback=None):
        """Open a small search/select dialog for attaching a Photo Set."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Attach Photo Set")
        dialog.geometry("760x520")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)

        incoming_count = len(manager.get_photo_set_photos(photo_set_id))
        status_var = tk.StringVar(value=f"Selected Photo Set: {photo_set_id} | Photos: {incoming_count}")
        search_var = tk.StringVar(value="")
        selected_item_id = tk.StringVar(value="")
        item_lookup = {}

        ttk.Label(main_frame, textvariable=status_var).grid(row=0, column=0, columnspan=3, sticky=tk.W)
        ttk.Label(main_frame, text="Search collection:").grid(row=1, column=0, sticky=tk.W, pady=(8, 4))
        search_entry = ttk.Entry(main_frame, textvariable=search_var)
        search_entry.grid(row=1, column=0, sticky=(tk.E, tk.W), padx=(120, 8), pady=(8, 4))

        result_tree = ttk.Treeview(
            main_frame,
            columns=("country", "denomination", "year", "grade", "photos"),
            show="headings",
            height=10,
        )
        result_tree.heading("country", text="Country")
        result_tree.heading("denomination", text="Denomination")
        result_tree.heading("year", text="Year")
        result_tree.heading("grade", text="Grade")
        result_tree.heading("photos", text="Photos")
        result_tree.column("country", width=140, anchor=tk.W)
        result_tree.column("denomination", width=160, anchor=tk.W)
        result_tree.column("year", width=80, anchor=tk.W)
        result_tree.column("grade", width=90, anchor=tk.W)
        result_tree.column("photos", width=70, anchor=tk.CENTER)
        result_tree.grid(row=2, column=0, columnspan=3, sticky=(tk.N, tk.S, tk.E, tk.W), pady=(4, 8))

        preview = tk.Text(main_frame, height=7, wrap=tk.WORD)
        preview.grid(row=3, column=0, columnspan=3, sticky=(tk.E, tk.W), pady=(0, 8))

        def set_preview(text):
            preview.config(state=tk.NORMAL)
            preview.delete("1.0", tk.END)
            preview.insert(tk.END, text)
            preview.config(state=tk.DISABLED)

        def run_search(event=None):
            for row_id in result_tree.get_children():
                result_tree.delete(row_id)
            item_lookup.clear()
            for item in self.search_attach_targets(search_var.get()):
                photos = self.photos_from_item(item)
                item_lookup[item.id] = item
                result_tree.insert(
                    "",
                    tk.END,
                    iid=item.id,
                    values=(item.country, item.denomination, item.year, item.grade, len(photos)),
                )
            selected_item_id.set("")
            attach_button.config(state=tk.DISABLED)
            set_preview("Select an existing collectible to preview the attachment target.")

        def on_target_selected(event=None):
            selection = result_tree.selection()
            if not selection:
                selected_item_id.set("")
                attach_button.config(state=tk.DISABLED)
                return
            selected_item_id.set(selection[0])
            item = item_lookup.get(selection[0])
            set_preview(self.attach_target_summary(item))
            attach_button.config(state=tk.NORMAL if item else tk.DISABLED)

        def attach_selected():
            item = item_lookup.get(selected_item_id.get())
            if not item:
                messagebox.showwarning("Attach Photo Set", "Select a collection item first.")
                return
            merge = self.merge_inbox_photos_into_item(item, manager, photo_set_id)
            if merge["added_count"] == 0:
                messagebox.showwarning(
                    "Attach Photo Set",
                    "All photos in this Photo Set are already attached to the selected item. The Photo Set remains pending.",
                )
                return
            detail = (
                f"Attach {merge['added_count']} photo reference(s) to this item?\n\n"
                f"{self.attach_target_summary(item)}"
            )
            if merge["skipped_count"]:
                detail += f"\n\nSkipped duplicates: {merge['skipped_count']}"
            if not messagebox.askyesno("Confirm Attachment", detail):
                return
            result = self.attach_photo_set_to_item(manager, photo_set_id, item, refresh_callback=refresh_callback)
            if not result["success"]:
                messagebox.showerror("Attach Photo Set", result["error"])
                return
            messagebox.showinfo(
                "Attach Photo Set",
                f"Added {result['added_count']} photo reference(s). Skipped {result['skipped_count']} duplicate(s).",
            )
            dialog.destroy()

        result_tree.bind("<<TreeviewSelect>>", on_target_selected)
        search_entry.bind("<Return>", run_search)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, sticky=tk.E)
        ttk.Button(button_frame, text="Search", command=run_search).pack(side=tk.LEFT, padx=(0, 6))
        attach_button = ttk.Button(button_frame, text="Attach Photos", state=tk.DISABLED, command=attach_selected)
        attach_button.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)

        run_search()

    def entry_form_has_content(self):
        """Return whether the main entry form has unsaved collector input."""
        text_values = [
            self.country_var.get(),
            self.denomination_var.get(),
            self.year_var.get(),
            self.grade_var.get(),
        ]
        notes = self.notes_text.get("1.0", tk.END).strip() if hasattr(self, "notes_text") else ""
        return any(str(value or "").strip() for value in text_values) or bool(notes) or bool(self.current_item_photos)

    def open_photo_inbox(self):
        """Open a manual Photo Inbox review window."""
        manager = PhotoInboxManager()

        dialog = tk.Toplevel(self.root)
        dialog.title("Photo Inbox")
        dialog.geometry("920x640")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)

        folder_var = tk.StringVar(value=f"Inbox Folder: {manager.config.inbox_folder}")
        status_var = tk.StringVar(value="Manual refresh only. Files are referenced in place.")
        selected_set_id = tk.StringVar(value="")
        scan_startup_var = tk.BooleanVar(
            value=self.get_photo_inbox_setting(PHOTO_INBOX_SETTING_SCAN_ON_STARTUP)
        )
        startup_notification_var = tk.BooleanVar(
            value=self.get_photo_inbox_setting(PHOTO_INBOX_SETTING_STARTUP_NOTIFICATION)
        )
        auto_refresh_var = tk.BooleanVar(
            value=self.get_photo_inbox_setting(PHOTO_INBOX_SETTING_AUTO_REFRESH_ON_OPEN)
        )

        ttk.Label(main_frame, textvariable=folder_var).grid(row=0, column=0, columnspan=2, sticky=tk.W)
        ttk.Label(main_frame, textvariable=status_var).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(4, 8))

        set_frame = ttk.LabelFrame(main_frame, text="Pending Photo Sets", padding="8")
        set_frame.grid(row=2, column=0, sticky=(tk.N, tk.S, tk.E, tk.W), padx=(0, 8))
        set_frame.columnconfigure(0, weight=1)
        set_frame.rowconfigure(0, weight=1)

        set_tree = ttk.Treeview(
            set_frame,
            columns=("state", "photos", "label", "updated"),
            show="headings",
            height=12,
        )
        set_tree.heading("state", text="State")
        set_tree.heading("photos", text="Photos")
        set_tree.heading("label", text="Suggested Label")
        set_tree.heading("updated", text="Updated")
        set_tree.column("state", width=90, anchor=tk.W)
        set_tree.column("photos", width=70, anchor=tk.CENTER)
        set_tree.column("label", width=210, anchor=tk.W)
        set_tree.column("updated", width=150, anchor=tk.W)
        set_tree.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))

        photo_frame = ttk.LabelFrame(main_frame, text="Selected Set Photos", padding="8")
        photo_frame.grid(row=2, column=1, sticky=(tk.N, tk.S, tk.E, tk.W))
        photo_frame.columnconfigure(0, weight=1)
        photo_frame.rowconfigure(0, weight=1)

        photo_tree = ttk.Treeview(
            photo_frame,
            columns=("state", "file", "path"),
            show="headings",
            height=12,
        )
        photo_tree.heading("state", text="State")
        photo_tree.heading("file", text="File")
        photo_tree.heading("path", text="Path")
        photo_tree.column("state", width=90, anchor=tk.W)
        photo_tree.column("file", width=150, anchor=tk.W)
        photo_tree.column("path", width=300, anchor=tk.W)
        photo_tree.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))

        def populate_sets(scan_result=None):
            for row_id in set_tree.get_children():
                set_tree.delete(row_id)
            rows = self.photo_inbox_set_rows(manager)
            for row in rows:
                set_tree.insert(
                    "",
                    tk.END,
                    iid=row["id"],
                    values=(row["state"], row["photo_count"], row["suggested_label"], row["updated_at"]),
                )
            if rows:
                selected = selected_set_id.get()
                if selected not in {row["id"] for row in rows}:
                    selected = rows[0]["id"]
                    selected_set_id.set(selected)
                set_tree.selection_set(selected)
                set_tree.focus(selected)
                populate_photos(selected)
            else:
                selected_set_id.set("")
                populate_photos("")
            self.update_photo_inbox_indicator(len(rows))
            create_button.config(
                state=tk.NORMAL if self.can_create_new_from_inbox(rows, selected_set_id.get()) else tk.DISABLED
            )
            attach_button.config(
                state=tk.NORMAL if self.can_attach_existing_from_inbox(rows, selected_set_id.get()) else tk.DISABLED
            )
            if scan_result:
                status_var.set(self.photo_inbox_scan_summary(scan_result, len(rows)))
            else:
                status_var.set(f"Pending sets: {len(rows)} | Manual refresh only. Files are referenced in place.")

        def populate_photos(photo_set_id):
            for row_id in photo_tree.get_children():
                photo_tree.delete(row_id)
            for index, row in enumerate(self.photo_inbox_photo_rows(manager, photo_set_id)):
                status = row["state"]
                if row["error"]:
                    status = f"{status}: {row['error']}"
                photo_tree.insert("", tk.END, iid=str(index), values=(status, row["filename"], row["path"]))

        def refresh_inbox():
            try:
                scan_result = manager.refresh()
                populate_sets(scan_result)
                if scan_result.errors:
                    messagebox.showwarning("Photo Inbox", "\n".join(scan_result.errors))
            except Exception as exc:
                messagebox.showerror("Photo Inbox Error", f"Refresh failed: {exc}")

        def on_set_selected(event=None):
            selection = set_tree.selection()
            if not selection:
                return
            selected_set_id.set(selection[0])
            populate_photos(selection[0])
            create_button.config(state=tk.NORMAL)
            attach_button.config(state=tk.NORMAL)

        def create_new_from_selected():
            photo_set_id = selected_set_id.get()
            if not photo_set_id:
                messagebox.showwarning("Photo Inbox", "Select a Photo Set first.")
                return
            if self.entry_form_has_content():
                if not messagebox.askyesno(
                    "Create From Photo Set",
                    "Replace the current unsaved entry form with this Photo Set?",
                ):
                    return
                self.clear_form()
            loaded, skipped = self.load_photo_set_into_entry_form(manager, photo_set_id, refresh_callback=populate_sets)
            if not loaded:
                messagebox.showerror("Photo Inbox", "Could not load photos from the selected Photo Set.")
                return
            detail = "Photo Set loaded into the collection-entry form."
            if skipped:
                detail += f"\nSkipped {len(skipped)} duplicate photo reference(s)."
            status_var.set(detail)
            messagebox.showinfo("Photo Inbox", detail)

        def attach_existing_from_selected():
            photo_set_id = selected_set_id.get()
            if not photo_set_id:
                messagebox.showwarning("Photo Inbox", "Select a Photo Set first.")
                return
            self.open_attach_photo_set_dialog(manager, photo_set_id, refresh_callback=populate_sets)

        def mark_selected(action):
            photo_set_id = selected_set_id.get()
            if not photo_set_id:
                messagebox.showwarning("Photo Inbox", "Select a Photo Set first.")
                return
            if action == "ignore":
                ok = manager.mark_ignored(photo_set_id)
            else:
                ok = manager.mark_deferred(photo_set_id)
            if not ok:
                messagebox.showerror("Photo Inbox", "Could not update the selected Photo Set.")
                return
            populate_sets()

        def update_inbox_setting(key, variable):
            self.set_photo_inbox_setting(key, variable.get())
            if key == PHOTO_INBOX_SETTING_STARTUP_NOTIFICATION and not variable.get():
                self.dismiss_photo_inbox_notification()

        set_tree.bind("<<TreeviewSelect>>", on_set_selected)

        settings_frame = ttk.LabelFrame(main_frame, text="Photo Inbox Settings", padding="8")
        settings_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        ttk.Checkbutton(
            settings_frame,
            text="Scan Photo Inbox on startup",
            variable=scan_startup_var,
            command=lambda: update_inbox_setting(PHOTO_INBOX_SETTING_SCAN_ON_STARTUP, scan_startup_var),
        ).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Checkbutton(
            settings_frame,
            text="Show startup Photo Inbox notification",
            variable=startup_notification_var,
            command=lambda: update_inbox_setting(
                PHOTO_INBOX_SETTING_STARTUP_NOTIFICATION,
                startup_notification_var,
            ),
        ).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Checkbutton(
            settings_frame,
            text="Auto-refresh inbox when opened",
            variable=auto_refresh_var,
            command=lambda: update_inbox_setting(PHOTO_INBOX_SETTING_AUTO_REFRESH_ON_OPEN, auto_refresh_var),
        ).pack(side=tk.LEFT)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, sticky=tk.E, pady=(10, 0))
        ttk.Button(button_frame, text="Refresh Inbox", command=refresh_inbox).pack(side=tk.LEFT, padx=(0, 6))
        create_button = ttk.Button(button_frame, text="Create New", state=tk.DISABLED, command=create_new_from_selected)
        create_button.pack(side=tk.LEFT, padx=(0, 6))
        attach_button = ttk.Button(
            button_frame,
            text="Attach to Existing",
            state=tk.DISABLED,
            command=attach_existing_from_selected,
        )
        attach_button.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Defer", command=lambda: mark_selected("defer")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Ignore", command=lambda: mark_selected("ignore")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

        if self.get_photo_inbox_setting(PHOTO_INBOX_SETTING_AUTO_REFRESH_ON_OPEN):
            refresh_inbox()
        else:
            populate_sets()

    def open_collection_health_report(self):
        """Open consolidated Collection Health Report dialog."""
        report = CollectionHealthReportEngine(
            self._collection_items(),
            self._active_want_list_intents(),
            self.shopping_candidates,
            market_awareness_engine=self.market_awareness_engine,
            photo_records=self.photo_records,
        )

        dialog = tk.Toplevel(self.root)
        dialog.title("Collection Health Report")
        dialog.geometry("900x700")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            main_frame,
            text=self.session_context.format_status_line(),
            padding=(0, 0, 0, 8),
        ).pack(fill=tk.X)

        text = tk.Text(main_frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, report.format_markdown())
        text.config(state=tk.DISABLED)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def export_csv():
            file_path = filedialog.asksaveasfilename(
                title="Export Collection Health Report CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not file_path:
                return
            if report.export_csv(file_path):
                messagebox.showinfo("Success", f"Collection Health Report CSV exported to {file_path}")
            else:
                messagebox.showerror("Error", "Failed to export Collection Health Report CSV")

        def export_markdown():
            file_path = filedialog.asksaveasfilename(
                title="Export Collection Health Report Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
            )
            if not file_path:
                return
            if report.export_markdown(file_path):
                messagebox.showinfo("Success", f"Collection Health Report Markdown exported to {file_path}")
            else:
                messagebox.showerror("Error", "Failed to export Collection Health Report Markdown")

        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_portfolio_import_preview(self):
        """Preview a legacy portfolio workbook without importing collection data."""
        file_path = filedialog.askopenfilename(
            title="Select Legacy Portfolio Workbook",
            filetypes=[("Excel files", "*.xlsx *.xlsm *.xls"), ("All files", "*.*")]
        )
        if not file_path:
            return

        try:
            importer = LegacyPortfolioImporter(self.app.collection.get_all_items())
            summary = importer.preview_workbook(file_path)
            self.session_context.load_collection_context(file_path, self._collection_items())
            self.refresh_session_status()
            self.show_portfolio_import_preview(summary, file_path)
        except Exception as e:
            messagebox.showerror(
                "Portfolio Import Preview Error",
                f"Failed to preview portfolio workbook: {str(e)}"
            )

    def show_portfolio_import_preview(self, summary, workbook_path):
        """Show staged portfolio rows, duplicates, skipped rows, and warnings."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Portfolio Import Preview")
        dialog.geometry("1050x700")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)

        ttk.Label(main_frame, text=os.path.basename(workbook_path)).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 10)
        )

        summary_frame = ttk.LabelFrame(main_frame, text="Import Summary", padding="10")
        summary_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        for column in range(5):
            summary_frame.columnconfigure(column, weight=1)

        summary_values = [
            ("Rows Found", summary.rows_found),
            ("Importable Items", summary.items_importable),
            ("Duplicates", summary.duplicates_detected),
            ("Skipped Rows", summary.rows_skipped),
            ("Warnings", len(summary.warnings)),
        ]
        for column, (label, value) in enumerate(summary_values):
            cell = ttk.Frame(summary_frame)
            cell.grid(row=0, column=column, sticky=(tk.W, tk.E), padx=(0, 10))
            ttk.Label(cell, text=label).pack(anchor=tk.W)
            ttk.Label(cell, text=str(value), font=("Arial", 12, "bold")).pack(anchor=tk.W)

        notebook = ttk.Notebook(main_frame)
        notebook.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        staged_frame = ttk.Frame(notebook, padding="10")
        duplicate_frame = ttk.Frame(notebook, padding="10")
        skipped_frame = ttk.Frame(notebook, padding="10")
        warnings_frame = ttk.Frame(notebook, padding="10")

        notebook.add(staged_frame, text="Staged Items")
        notebook.add(duplicate_frame, text="Duplicates")
        notebook.add(skipped_frame, text="Skipped Rows")
        notebook.add(warnings_frame, text="Warnings")

        staged_tree = self.create_portfolio_preview_table(staged_frame, include_duplicate=False)
        for staged in summary.staged_items:
            self.insert_portfolio_preview_row(staged_tree, staged, include_duplicate=False)

        duplicate_tree = self.create_portfolio_preview_table(duplicate_frame, include_duplicate=True)
        for duplicate in summary.duplicate_items:
            self.insert_portfolio_preview_row(duplicate_tree, duplicate, include_duplicate=True)

        skipped_tree = self.create_skipped_rows_table(skipped_frame)
        for skipped in summary.skipped_rows:
            skipped_tree.insert(
                "",
                tk.END,
                values=(skipped.sheet_name, skipped.row_number, skipped.reason)
            )

        warnings_text = tk.Text(warnings_frame, wrap=tk.WORD, height=8)
        warnings_text.pack(fill=tk.BOTH, expand=True)
        warnings_text.insert(tk.END, "\n".join(summary.warnings) if summary.warnings else "No warnings.")
        warnings_text.config(state=tk.DISABLED)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, sticky=tk.W, pady=(10, 0))

        def export_report():
            output_path = filedialog.asksaveasfilename(
                title="Export Portfolio Import Preview",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not output_path:
                return
            if export_import_summary_csv(summary, output_path):
                messagebox.showinfo("Success", f"Portfolio import preview exported to {output_path}")
            else:
                messagebox.showerror("Error", "Failed to export portfolio import preview")

        ttk.Button(button_frame, text="Export Report", command=export_report).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_want_list_preview(self):
        """Preview legacy WANT_LIST acquisition-intent rows without importing data."""
        file_path = filedialog.askopenfilename(
            title="Select Legacy Portfolio Workbook",
            filetypes=[("Excel files", "*.xlsx *.xlsm *.xls"), ("All files", "*.*")]
        )
        if not file_path:
            return

        try:
            importer = LegacyPortfolioImporter(self.app.collection.get_all_items())
            preview = importer.preview_want_list(file_path)
            self.session_context.load_want_list_context(file_path, self._collection_items())
            self.refresh_session_status()
            self.show_want_list_preview(preview, file_path)
        except Exception as e:
            messagebox.showerror(
                "Want List Preview Error",
                f"Failed to preview workbook WANT_LIST: {str(e)}"
            )

    def show_want_list_preview(self, preview, workbook_path):
        """Show staged WANT_LIST acquisition intent, skipped rows, and warnings."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Want List Preview")
        dialog.geometry("1000x650")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)

        ttk.Label(main_frame, text=os.path.basename(workbook_path)).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 10)
        )

        summary_frame = ttk.LabelFrame(main_frame, text="Want List Summary", padding="10")
        summary_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        for column in range(4):
            summary_frame.columnconfigure(column, weight=1)

        summary_values = [
            ("Total Intents Found", preview.rows_found),
            ("Valid Intents", preview.intents_staged),
            ("Skipped Rows", preview.rows_skipped),
            ("Warnings", len(preview.warnings)),
        ]
        for column, (label, value) in enumerate(summary_values):
            cell = ttk.Frame(summary_frame)
            cell.grid(row=0, column=column, sticky=(tk.W, tk.E), padx=(0, 10))
            ttk.Label(cell, text=label).pack(anchor=tk.W)
            ttk.Label(cell, text=str(value), font=("Arial", 12, "bold")).pack(anchor=tk.W)

        notebook = ttk.Notebook(main_frame)
        notebook.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        intents_frame = ttk.Frame(notebook, padding="10")
        skipped_frame = ttk.Frame(notebook, padding="10")
        warnings_frame = ttk.Frame(notebook, padding="10")

        notebook.add(intents_frame, text="Staged Intents")
        notebook.add(skipped_frame, text="Skipped Rows")
        notebook.add(warnings_frame, text="Warnings")

        intents_tree = self.create_want_list_preview_table(intents_frame)
        for intent in preview.staged_intents:
            intents_tree.insert(
                "",
                tk.END,
                values=(
                    intent.target_coin,
                    intent.priority,
                    intent.target_grade,
                    f"{intent.budget:.2f}" if intent.budget else "",
                    intent.why_wanted,
                    intent.status,
                )
            )

        skipped_tree = self.create_skipped_rows_table(skipped_frame)
        for skipped in preview.skipped_rows:
            skipped_tree.insert(
                "",
                tk.END,
                values=(skipped.sheet_name, skipped.row_number, skipped.reason)
            )

        warnings_text = tk.Text(warnings_frame, wrap=tk.WORD, height=8)
        warnings_text.pack(fill=tk.BOTH, expand=True)
        warnings_text.insert(tk.END, "\n".join(preview.warnings) if preview.warnings else "No warnings.")
        warnings_text.config(state=tk.DISABLED)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, sticky=tk.W, pady=(10, 0))

        def export_report():
            output_path = filedialog.asksaveasfilename(
                title="Export Want List Preview",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not output_path:
                return
            if export_want_list_preview_csv(preview, output_path):
                messagebox.showinfo("Success", f"Want list preview exported to {output_path}")
            else:
                messagebox.showerror("Error", "Failed to export want list preview")

        ttk.Button(button_frame, text="Export CSV", command=export_report).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def create_want_list_preview_table(self, parent):
        """Create a table for staged WANT_LIST acquisition-intent rows."""
        columns = ("Target Coin", "Priority", "Target Grade", "Budget", "Why Wanted", "Status")
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        tree = ttk.Treeview(container, columns=columns, show="headings", height=12)
        for column in columns:
            tree.heading(column, text=column)
            width = 110
            if column == "Target Coin":
                width = 240
            elif column == "Why Wanted":
                width = 300
            tree.column(column, width=width, anchor=tk.W)

        y_scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=tree.yview)
        x_scrollbar = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
        tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        y_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        x_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        return tree

    def create_portfolio_preview_table(self, parent, include_duplicate=False):
        """Create a table for staged or duplicate portfolio preview rows."""
        columns = ["Sheet", "Row", "Title", "Country", "Denomination", "Year", "Grade", "Estimate CAD", "Numista #"]
        if include_duplicate:
            columns.extend(["Duplicate Of", "Reason"])

        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        tree = ttk.Treeview(container, columns=columns, show="headings", height=12)
        for column in columns:
            tree.heading(column, text=column)
            width = 90
            if column == "Title":
                width = 240
            elif column in ("Duplicate Of", "Reason"):
                width = 160
            tree.column(column, width=width, anchor=tk.W)

        y_scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=tree.yview)
        x_scrollbar = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)

        tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        y_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        x_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        return tree

    def insert_portfolio_preview_row(self, tree, staged, include_duplicate=False):
        """Insert one staged portfolio preview row into a Treeview."""
        item = staged.coin_item
        values = [
            staged.sheet_name,
            staged.row_number,
            item.title,
            item.country,
            item.denomination,
            item.year,
            item.grade,
            f"{item.estimate_cad:.2f}" if item.estimate_cad else "",
            item.numista_n,
        ]
        if include_duplicate:
            values.extend([staged.duplicate_of or "", staged.duplicate_reason])
        tree.insert("", tk.END, values=values)

    def create_skipped_rows_table(self, parent):
        """Create a table for skipped legacy portfolio rows."""
        columns = ("Sheet", "Row", "Reason")
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        tree = ttk.Treeview(container, columns=columns, show="headings", height=8)
        for column in columns:
            tree.heading(column, text=column)
            tree.column(column, width=140 if column != "Reason" else 500, anchor=tk.W)

        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        return tree
    
    def open_buy_advisor(self):
        """Open Buy Advisor dialog."""
        staged_want_list_intents = self._active_want_list_intents()

        dialog = tk.Toplevel(self.root)
        dialog.title("Buy Advisor")
        dialog.geometry("540x500")
        
        # Form frame
        form_frame = ttk.Frame(dialog, padding="20")
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Country
        ttk.Label(form_frame, text="Country:").grid(row=0, column=0, sticky=tk.W, pady=5)
        country_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=country_var).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        # Denomination
        ttk.Label(form_frame, text="Denomination:").grid(row=1, column=0, sticky=tk.W, pady=5)
        denom_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=denom_var).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        # Year
        ttk.Label(form_frame, text="Year:").grid(row=2, column=0, sticky=tk.W, pady=5)
        year_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=year_var).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        # Reference
        ttk.Label(form_frame, text="Reference:").grid(row=3, column=0, sticky=tk.W, pady=5)
        ref_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=ref_var).grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        # Numista N#
        ttk.Label(form_frame, text="Numista N#:").grid(row=4, column=0, sticky=tk.W, pady=5)
        numista_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=numista_var).grid(row=4, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        # Grade
        ttk.Label(form_frame, text="Grade (optional):").grid(row=5, column=0, sticky=tk.W, pady=5)
        grade_var = tk.StringVar()
        grade_combo = ttk.Combobox(form_frame, textvariable=grade_var, 
                                   values=["", "PO-1", "FR-2", "AG-3", "G-4", "VG-8", "F-12", "VF-20", "VF-30", "EF-40", "EF-45", "AU-50", "AU-53", "AU-55", "AU-58", "MS-60", "MS-61", "MS-62", "MS-63", "MS-64", "MS-65", "MS-66", "MS-67", "MS-68", "MS-69", "MS-70"])
        grade_combo.grid(row=5, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        # Asking Price
        ttk.Label(form_frame, text="Asking Price ($):").grid(row=6, column=0, sticky=tk.W, pady=5)
        asking_price_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=asking_price_var).grid(row=6, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        # Shipping
        ttk.Label(form_frame, text="Shipping ($):").grid(row=7, column=0, sticky=tk.W, pady=5)
        shipping_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=shipping_var).grid(row=7, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        # Tax/Fees
        ttk.Label(form_frame, text="Tax/Fees ($):").grid(row=8, column=0, sticky=tk.W, pady=5)
        tax_fees_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=tax_fees_var).grid(row=8, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        # Estimated Market Value
        ttk.Label(form_frame, text="Est. Market Value ($):").grid(row=9, column=0, sticky=tk.W, pady=5)
        estimated_value_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=estimated_value_var).grid(row=9, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))

        if staged_want_list_intents:
            want_list_status = f"Using shared WANT_LIST context: {len(staged_want_list_intents)} active intent(s)."
        else:
            want_list_status = "No staged WANT_LIST context loaded."
        want_list_status_var = tk.StringVar(value=want_list_status)
        ttk.Label(form_frame, textvariable=want_list_status_var).grid(row=10, column=0, columnspan=2, sticky=tk.W, pady=(10, 0))
        
        # Buttons
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=11, column=0, columnspan=2, pady=(20, 0))

        def load_want_list_context():
            nonlocal staged_want_list_intents
            file_path = filedialog.askopenfilename(
                title="Select Legacy Portfolio Workbook",
                filetypes=[("Excel files", "*.xlsx *.xlsm *.xls"), ("All files", "*.*")]
            )
            if not file_path:
                return
            try:
                importer = LegacyPortfolioImporter(self.app.collection.get_all_items())
                preview = importer.preview_want_list(file_path)
                staged_want_list_intents = preview.staged_intents
                self.session_context.load_want_list_context(file_path, self._collection_items())
                self.refresh_session_status()
                want_list_status_var.set(
                    f"Loaded {preview.intents_staged} staged WANT_LIST intents from {os.path.basename(file_path)}."
                )
            except Exception as e:
                messagebox.showerror(
                    "Buy Advisor WANT_LIST Error",
                    f"Failed to load workbook WANT_LIST: {str(e)}"
                )
        
        def get_advice():
            from buy_advisor import BuyAdvisor
            advisor = BuyAdvisor(self.app.collection, staged_want_list_intents=staged_want_list_intents)
            
            # Parse asking price inputs
            try:
                asking_price = float(asking_price_var.get()) if asking_price_var.get() else 0.0
            except ValueError:
                asking_price = 0.0
            try:
                shipping = float(shipping_var.get()) if shipping_var.get() else 0.0
            except ValueError:
                shipping = 0.0
            try:
                tax_fees = float(tax_fees_var.get()) if tax_fees_var.get() else 0.0
            except ValueError:
                tax_fees = 0.0
            try:
                estimated_market_value = float(estimated_value_var.get()) if estimated_value_var.get() else 0.0
            except ValueError:
                estimated_market_value = 0.0
            
            rec = advisor.advise(
                country_var.get(),
                denom_var.get(),
                year_var.get(),
                ref_var.get(),
                numista_var.get(),
                grade_var.get(),
                asking_price=asking_price,
                shipping=shipping,
                tax_fees=tax_fees,
                estimated_market_value=estimated_market_value
            )
            
            # Show results
            result_dialog = tk.Toplevel(dialog)
            result_dialog.title("Buy Recommendation")
            result_dialog.geometry("600x500")
            
            result_text = tk.Text(result_dialog, wrap=tk.WORD, padx=10, pady=10)
            result_text.pack(fill=tk.BOTH, expand=True)
            
            report = f"=== Buy Recommendation ===\n\n"
            report += f"Base Recommendation: {rec.base_recommendation}\n"
            report += f"Final Recommendation: {rec.recommendation}\n\n"
            report += f"=== Analysis ===\n"
            report += f"Already Owned: {rec.already_owned}\n"
            report += f"Duplicate Count: {rec.duplicate_count}\n"
            report += f"Upgrade Candidate: {rec.upgrade_candidate}\n"
            if rec.existing_grade:
                report += f"Existing Grade: {rec.existing_grade}\n"
            report += f"Missing Date in Series: {rec.missing_date_in_series}\n"
            report += f"Missing Denomination in Country: {rec.missing_denomination_in_country}\n"
            report += f"Series Completion: {rec.series_completion:.1%}\n"
            report += f"Country Completion: {rec.country_completion:.1%}\n"
            report += f"Confidence Score: {rec.confidence_score}/100\n"
            report += f"Value Quality: {rec.value_quality}\n\n"
            
            report += f"=== Explanation ===\n"
            report += f"{rec.explanation}\n\n"
            
            report += f"=== Reasons ===\n"
            for reason in rec.reasons:
                report += f"  - {reason}\n"
            
            report += f"\n=== Matching Items ===\n"
            if rec.matching_items:
                for item in rec.matching_items:
                    match_type = item['match_type'].upper()
                    report += f"  [{match_type}] {item['country']} {item['denomination']} {item['year']}"
                    if item['grade']:
                        report += f" - Grade: {item['grade']}"
                    if item['title']:
                        report += f"\n      Title: {item['title']}"
                    if item['numista_n']:
                        report += f"\n      Numista N#: {item['numista_n']}"
                    if item['reference']:
                        report += f"\n      Reference: {item['reference']}"
                    if item['estimate_cad']:
                        report += f"\n      Estimate: ${item['estimate_cad']:.2f}"
                    report += "\n"
            else:
                report += "  No matching items found in collection\n"
            
            report += f"\n=== Value Information ===\n"
            if rec.value_data_available:
                if rec.max_rational_bid > 0:
                    report += f"Max Rational Bid: ${rec.max_rational_bid:.2f}\n"
                else:
                    report += f"Max Rational Bid: Not recommended\n"
            else:
                report += f"Max Rational Bid: No value data available\n"
            report += f"{rec.max_bid_explanation}\n"
            if rec.value_warning:
                report += f"Warning: {rec.value_warning}\n"
            
            report += f"\n=== Warnings ===\n"
            if rec.warnings:
                for warning in rec.warnings:
                    report += f"  - {warning}\n"
            else:
                report += "  No warnings\n"
            
            report += f"\n=== Adam Priority Score ===\n"
            report += f"Score: {rec.adam_priority_score}\n"
            if rec.adam_priority_score >= 80:
                report += f"Strategic Category: Core Target\n"
            elif rec.adam_priority_score >= 50:
                report += f"Strategic Category: Good Fit\n"
            elif rec.adam_priority_score >= 20:
                report += f"Strategic Category: Optional\n"
            else:
                report += f"Strategic Category: Low Priority\n"
            if rec.adam_priority_reasons:
                report += f"Reasons:\n"
                for reason in rec.adam_priority_reasons:
                    report += f"  - {reason}\n"
            else:
                report += f"No priority factors applied\n"

            report += f"\n=== Collection Intelligence Factors ===\n"
            report += f"Collection Impact Score: {rec.collection_impact_score}\n"
            if rec.collection_intelligence_factors:
                for factor in rec.collection_intelligence_factors:
                    report += f"  - {factor}\n"
            else:
                report += f"  No collection intelligence factors applied\n"
            
            report += f"\n=== Liquidity Score ===\n"
            report += f"Score: {rec.liquidity_score}\n"
            if rec.liquidity_score >= 20:
                report += f"Liquidity Category: High Liquidity\n"
            elif rec.liquidity_score >= 10:
                report += f"Liquidity Category: Medium Liquidity\n"
            elif rec.liquidity_score >= 0:
                report += f"Liquidity Category: Low Liquidity\n"
            else:
                report += f"Liquidity Category: Very Low Liquidity\n"
            if rec.liquidity_reasons:
                report += f"Reasoning:\n"
                for reason in rec.liquidity_reasons:
                    report += f"  - {reason}\n"
            else:
                report += f"No liquidity factors applied\n"
            
            report += f"\n=== Price Analysis ===\n"
            if rec.landed_cost > 0:
                report += f"Landed Cost: ${rec.landed_cost:.2f}\n"
                report += f"Max Rational Bid: ${rec.max_rational_bid:.2f}\n"
                if rec.max_rational_bid > 0:
                    over_under = rec.landed_cost - rec.max_rational_bid
                    if over_under >= 0:
                        report += f"Over Max Bid: ${over_under:.2f}\n"
                    else:
                        report += f"Under Max Bid: ${abs(over_under):.2f}\n"
                report += f"Price Verdict: {rec.price_verdict}\n"
            else:
                report += f"No price data provided\n"
            
            report += f"\n=== Purchase Verdict ===\n"
            report += f"{rec.purchase_verdict}\n"
            
            result_text.insert(tk.END, report)
            result_text.config(state=tk.DISABLED)
        
        ttk.Button(button_frame, text="Load WANT_LIST Context", command=load_want_list_context).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Get Advice", command=get_advice).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)
        
        form_frame.columnconfigure(1, weight=1)
    
    def on_collection_select(self, event):
        """Keep selection presentation-only; actions resolve the stable ID later."""

    def selected_browser_item(self):
        """Resolve the selected stable ID against the current active collection."""
        selection = self.collection_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an item")
            return None
        tree_id = selection[0]
        item_id = self._browser_row_item_ids.get(tree_id)
        collection = self.app.collection
        if collection.load_state is not CollectionLoadState.VALID:
            messagebox.showerror("Collection Unavailable", "The active collection is not valid for this action.")
            return None
        item = collection.get_item(item_id) if item_id else None
        if item is None:
            try:
                self.collection_tree.selection_remove(tree_id)
            except tk.TclError:
                pass
            self.refresh_collection_list()
            messagebox.showwarning(
                "Selection Changed",
                "The selected item is no longer available. The collection browser was refreshed.",
            )
            return None
        return item
    
    def view_item_details(self):
        """View selected item details."""
        item = self.selected_browser_item()
        if item:
            self.open_item_details_window(item)

    def open_item_details_window(self, item):
        """Open a read-only item details window with a photo gallery."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Item Details")
        dialog.geometry("760x560")
        dialog.transient(self.root)

        content = ttk.Frame(dialog, padding="10")
        content.pack(fill=tk.BOTH, expand=True)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        details_text = tk.Text(content, width=42, wrap=tk.WORD)
        details_text.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W), padx=(0, 10))
        details_text.insert(tk.END, self.item_details_text(item))
        details_text.config(state=tk.DISABLED)

        gallery = ttk.LabelFrame(content, text="Photos", padding="10")
        gallery.grid(row=0, column=1, sticky=(tk.N, tk.S, tk.E, tk.W))
        gallery.columnconfigure(0, weight=1)
        gallery.rowconfigure(1, weight=1)

        preview_label = ttk.Label(gallery, text="No photos attached", anchor=tk.CENTER)
        preview_label.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        detail_photos = list(item.photos)
        if not detail_photos and item.image_path:
            detail_photos = [ItemPhoto(item.image_path, is_primary=True)]
        rows = self.photo_detail_rows(detail_photos)
        photo_tree = ttk.Treeview(
            gallery,
            columns=("primary", "role", "file"),
            show="headings",
            height=8,
        )
        photo_tree.heading("primary", text="Primary")
        photo_tree.heading("role", text="Role")
        photo_tree.heading("file", text="File")
        photo_tree.column("primary", width=65, anchor=tk.CENTER)
        photo_tree.column("role", width=120, anchor=tk.W)
        photo_tree.column("file", width=220, anchor=tk.W)
        photo_tree.grid(row=1, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))

        path_var = tk.StringVar(value="")
        notes_var = tk.StringVar(value="")
        ttk.Label(gallery, textvariable=path_var, wraplength=360).grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
        ttk.Label(gallery, textvariable=notes_var, wraplength=360).grid(row=3, column=0, sticky=tk.W, pady=(5, 0))

        detail_photo_ref = {"image": None}

        def show_detail_photo(index):
            if not rows or index < 0 or index >= len(rows):
                preview_label.config(image="", text="No photos attached")
                path_var.set("")
                notes_var.set("")
                return
            row = rows[index]
            path_var.set(f"Path: {row['path']}")
            notes_var.set(f"Notes: {row['notes']}" if row["notes"] else "Notes:")
            if row["status"]:
                detail_photo_ref["image"] = None
                preview_label.config(image="", text=row["status"])
                return
            try:
                img = Image.open(row["path"])
                img.thumbnail((320, 260))
                detail_photo_ref["image"] = ImageTk.PhotoImage(img)
                preview_label.config(image=detail_photo_ref["image"], text="")
            except Exception as exc:
                detail_photo_ref["image"] = None
                preview_label.config(image="", text=f"Preview unavailable: {exc}")

        for index, row in enumerate(rows):
            photo_tree.insert("", tk.END, iid=str(index), values=(row["primary"], row["role"], row["file"] or row["path"]))

        def on_detail_select(event=None):
            selection = photo_tree.selection()
            if selection:
                show_detail_photo(int(selection[0]))

        photo_tree.bind("<<TreeviewSelect>>", on_detail_select)
        if rows:
            photo_tree.selection_set("0")
            show_detail_photo(0)

        ttk.Button(content, text="Close", command=dialog.destroy).grid(row=1, column=1, sticky=tk.E, pady=(10, 0))
    
    def edit_item(self):
        """Edit selected item."""
        item = self.selected_browser_item()
        if item:
            self.open_edit_item_window(item)

    def open_edit_item_window(self, item):
        """Open a scoped edit dialog that includes item-owned photo metadata."""
        dialog = tk.Toplevel(self.root)
        self._track_collection_edit_window(dialog)
        dialog.title("Edit Item")
        dialog.geometry("780x760")
        dialog.transient(self.root)
        dialog.grab_set()

        edit_photos = {"photos": self.photos_from_item(item), "selected": 0}

        form = ttk.Frame(dialog, padding="10")
        form.pack(fill=tk.BOTH, expand=True)
        form.columnconfigure(1, weight=1)
        form.rowconfigure(9, weight=1)

        item_type_var = tk.StringVar(value=item.item_type.value)
        disposition_var = tk.StringVar(value=item.disposition.value)
        identification_status_var = tk.StringVar(value=item.identification_status.value)
        issuer_var = tk.StringVar(value=item.issuer)
        title_var = tk.StringVar(value=item.title)
        reference_var = tk.StringVar(value=item.reference)
        country_var = tk.StringVar(value=item.country)
        denomination_var = tk.StringVar(value=item.denomination)
        year_var = tk.StringVar(value=item.year)
        grade_var = tk.StringVar(value=item.grade)
        role_var = tk.StringVar(value=PhotoRole.OTHER.value)
        note_var = tk.StringVar()

        type_frame = ttk.Frame(form)
        type_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 8))
        type_frame.columnconfigure(1, weight=1)
        type_frame.columnconfigure(3, weight=1)
        compact_fields = (
            (0, 0, "Item Type:", item_type_var, [value.value for value in ItemType]),
            (0, 2, "Disposition:", disposition_var, [value.value for value in Disposition]),
        )
        for row_index, column, label, variable, values in compact_fields:
            ttk.Label(type_frame, text=label).grid(row=row_index, column=column, sticky=tk.W, pady=3)
            ttk.Combobox(
                type_frame,
                textvariable=variable,
                values=values,
                state="readonly",
            ).grid(row=row_index, column=column + 1, sticky=(tk.W, tk.E), padx=(5, 12 if column == 0 else 0), pady=3)
        ttk.Label(type_frame, text="Identification:").grid(row=1, column=0, sticky=tk.W, pady=3)
        ttk.Label(type_frame, textvariable=identification_status_var).grid(
            row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 12), pady=3
        )
        ttk.Label(type_frame, text="Issuer:").grid(row=2, column=0, sticky=tk.W, pady=3)
        ttk.Entry(type_frame, textvariable=issuer_var).grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(5, 12), pady=3)
        ttk.Label(type_frame, text="Title:").grid(row=1, column=2, sticky=tk.W, pady=3)
        ttk.Entry(type_frame, textvariable=title_var).grid(row=1, column=3, sticky=(tk.W, tk.E), padx=(5, 0), pady=3)
        ttk.Label(type_frame, text="Reference:").grid(row=2, column=2, sticky=tk.W, pady=3)
        ttk.Entry(type_frame, textvariable=reference_var).grid(row=2, column=3, sticky=(tk.W, tk.E), padx=(5, 0), pady=3)

        fields = [
            ("Country:", country_var, self.get_entry_suggestions("country")),
            ("Denomination:", denomination_var, self.get_entry_suggestions("denomination")),
            ("Year:", year_var, self.get_entry_suggestions("year")),
            ("Grade:", grade_var, GRADE_SUGGESTIONS),
        ]
        for row_index, (label, variable, values) in enumerate(fields, start=1):
            ttk.Label(form, text=label).grid(row=row_index, column=0, sticky=tk.W, pady=4)
            ttk.Combobox(form, textvariable=variable, values=values).grid(
                row=row_index,
                column=1,
                sticky=(tk.W, tk.E),
                pady=4,
                padx=(5, 0),
            )

        ttk.Label(form, text="Notes:").grid(row=5, column=0, sticky=tk.NW, pady=4)
        notes_text = tk.Text(form, height=4)
        notes_text.grid(row=5, column=1, sticky=(tk.W, tk.E), pady=4, padx=(5, 0))
        notes_text.insert(tk.END, item.notes)

        acquisition_expanded = tk.BooleanVar(value=item.has_acquisition_details())
        acquisition_button = ttk.Button(form)
        acquisition_button.grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=(8, 0))
        acquisition_frame = ttk.LabelFrame(form, text="Acquisition Details", padding="4")
        acquisition_frame.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        acquisition_controls = self.create_acquisition_fields(
            acquisition_frame,
            {
                "acquisition_date": item.acquisition_date,
                "purchase_price": item.purchase_price,
                "purchase_currency": item.purchase_currency,
                "purchase_source": item.purchase_source,
                "shipping_cost": item.shipping_cost,
                "buyers_premium": item.buyers_premium,
                "tax": item.tax,
            },
        )

        def set_edit_acquisition_visibility():
            if acquisition_expanded.get():
                acquisition_frame.grid()
                acquisition_button.config(text="Acquisition Details ▾")
            else:
                acquisition_frame.grid_remove()
                acquisition_button.config(text="Acquisition Details ▸")

        def toggle_edit_acquisition():
            acquisition_expanded.set(not acquisition_expanded.get())
            set_edit_acquisition_visibility()

        acquisition_button.config(command=toggle_edit_acquisition)
        set_edit_acquisition_visibility()

        photo_frame = ttk.LabelFrame(form, text="Photos", padding="10")
        photo_frame.grid(row=8, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        photo_frame.columnconfigure(0, weight=1)

        edit_tree = ttk.Treeview(photo_frame, columns=("primary", "role", "file"), show="headings", height=6)
        edit_tree.heading("primary", text="Primary")
        edit_tree.heading("role", text="Role")
        edit_tree.heading("file", text="File")
        edit_tree.column("primary", width=65, anchor=tk.CENTER)
        edit_tree.column("role", width=120, anchor=tk.W)
        edit_tree.column("file", width=360, anchor=tk.W)
        edit_tree.grid(row=0, column=0, columnspan=6, sticky=(tk.W, tk.E))

        def refresh_edit_tree():
            edit_photos["photos"] = self.normalized_photo_state(edit_photos["photos"])
            for row_id in edit_tree.get_children():
                edit_tree.delete(row_id)
            for index, row in enumerate(self.photo_detail_rows(edit_photos["photos"])):
                edit_tree.insert("", tk.END, iid=str(index), values=(row["primary"], row["role"], row["file"] or row["path"]))
            if edit_photos["photos"]:
                edit_photos["selected"] = min(edit_photos["selected"], len(edit_photos["photos"]) - 1)
                edit_tree.selection_set(str(edit_photos["selected"]))
                selected_photo = edit_photos["photos"][edit_photos["selected"]]
                role_var.set(selected_photo.role.value)
                note_var.set(selected_photo.notes)
            else:
                edit_photos["selected"] = None
                role_var.set(PhotoRole.OTHER.value)
                note_var.set("")

        def edit_selection_changed(event=None):
            selection = edit_tree.selection()
            if selection:
                edit_photos["selected"] = int(selection[0])
                selected_photo = edit_photos["photos"][edit_photos["selected"]]
                role_var.set(selected_photo.role.value)
                note_var.set(selected_photo.notes)

        def add_edit_photos():
            paths = filedialog.askopenfilenames(
                title="Select Item Photos",
                filetypes=[
                    ("Image files", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"),
                    ("All files", "*.*"),
                ],
            )
            if not paths:
                return
            edit_photos["photos"], skipped = self.add_photo_paths_to_list(edit_photos["photos"], paths)
            edit_photos["selected"] = len(edit_photos["photos"]) - 1 if edit_photos["photos"] else None
            refresh_edit_tree()
            if skipped:
                messagebox.showwarning("Duplicate Photos", f"Skipped {len(skipped)} duplicate photo reference(s).")

        def remove_edit_photo():
            edit_photos["photos"] = self.remove_photo_at_index(edit_photos["photos"], edit_photos["selected"])
            refresh_edit_tree()

        def set_edit_primary():
            edit_photos["photos"] = self.set_primary_photo_at_index(edit_photos["photos"], edit_photos["selected"])
            refresh_edit_tree()

        def move_edit_photo(offset):
            edit_photos["photos"], edit_photos["selected"] = self.move_photo_at_index(
                edit_photos["photos"],
                edit_photos["selected"],
                offset,
            )
            refresh_edit_tree()

        def update_edit_role(event=None):
            edit_photos["photos"] = self.update_photo_role_at_index(
                edit_photos["photos"],
                edit_photos["selected"],
                role_var.get(),
            )
            refresh_edit_tree()

        def update_edit_notes(event=None):
            edit_photos["photos"] = self.update_photo_notes_at_index(
                edit_photos["photos"],
                edit_photos["selected"],
                note_var.get(),
            )
            refresh_edit_tree()

        edit_tree.bind("<<TreeviewSelect>>", edit_selection_changed)
        ttk.Button(photo_frame, text="Add Photos", command=add_edit_photos).grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        ttk.Button(photo_frame, text="Remove", command=remove_edit_photo).grid(row=1, column=1, sticky=tk.W, padx=(5, 0), pady=(8, 0))
        ttk.Button(photo_frame, text="Set Primary", command=set_edit_primary).grid(row=1, column=2, sticky=tk.W, padx=(5, 0), pady=(8, 0))
        ttk.Button(photo_frame, text="Move Up", command=lambda: move_edit_photo(-1)).grid(row=1, column=3, sticky=tk.W, padx=(5, 0), pady=(8, 0))
        ttk.Button(photo_frame, text="Move Down", command=lambda: move_edit_photo(1)).grid(row=1, column=4, sticky=tk.W, padx=(5, 0), pady=(8, 0))

        ttk.Label(photo_frame, text="Role:").grid(row=2, column=0, sticky=tk.W, pady=(8, 0))
        role_combo = ttk.Combobox(photo_frame, textvariable=role_var, values=self.get_photo_role_values())
        role_combo.grid(row=2, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=(8, 0), padx=(5, 0))
        role_combo.bind("<<ComboboxSelected>>", update_edit_role)
        role_combo.bind("<FocusOut>", update_edit_role)
        ttk.Label(photo_frame, text="Notes:").grid(row=3, column=0, sticky=tk.W, pady=(5, 0))
        note_entry = ttk.Entry(photo_frame, textvariable=note_var)
        note_entry.grid(row=3, column=1, columnspan=4, sticky=(tk.W, tk.E), pady=(5, 0), padx=(5, 0))
        note_entry.bind("<FocusOut>", update_edit_notes)
        note_entry.bind("<Return>", update_edit_notes)

        button_frame = ttk.Frame(form)
        button_frame.grid(row=10, column=0, columnspan=2, sticky=tk.E, pady=(10, 0))

        def save_edit():
            try:
                form_values = self.manual_item_values_from_text({
                    **acquisition_controls["values"](),
                    "item_type": item_type_var.get(),
                    "disposition": disposition_var.get(),
                    "country": country_var.get(),
                    "issuer": issuer_var.get(),
                    "denomination": denomination_var.get(),
                    "year": year_var.get(),
                    "title": title_var.get(),
                    "reference": reference_var.get(),
                    "grade": grade_var.get(),
                    "notes": notes_text.get("1.0", tk.END),
                })
            except ValueError as error:
                messagebox.showwarning("Invalid Item Details", str(error), parent=dialog)
                return
            photos = self.normalized_photo_state(edit_photos["photos"])
            primary = next((photo for photo in photos if photo.is_primary), None)
            updates = {
                **form_values,
                "photos": photos,
                "image_path": primary.path if primary else "",
            }
            if not self.app.collection.update_item(item.id, updates):
                messagebox.showerror(
                    "Save Failed",
                    f"The item was not updated: {self.app.collection.last_save_error or 'collection save failed'}",
                )
                return
            self.refresh_collection_list()
            dialog.destroy()
            messagebox.showinfo("Success", "Item updated")

        ttk.Button(button_frame, text="Save", command=save_edit).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)

        refresh_edit_tree()
    
    def delete_item(self):
        """Delete selected item."""
        item = self.selected_browser_item()
        if item is None:
            return
        selected_collection = self.app.collection
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this item?"):
            active_collection = self.app.collection
            current_item = (
                active_collection.get_item(item.id)
                if active_collection is selected_collection
                and active_collection.load_state is CollectionLoadState.VALID
                else None
            )
            if current_item is None:
                self.refresh_collection_list()
                messagebox.showwarning(
                    "Selection Changed",
                    "The selected item or active collection changed before deletion. Nothing was deleted.",
                )
                return
            if active_collection.delete_item(current_item.id):
                self.refresh_collection_list()
                messagebox.showinfo("Success", "Item deleted")
            else:
                messagebox.showerror("Error", "Failed to delete item")
    
    def export_csv(self):
        """Export collection to CSV."""
        file_path = filedialog.asksaveasfilename(
            title="Export Collection",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        
        if file_path:
            if self.app.export_collection(file_path):
                messagebox.showinfo("Success", f"Collection exported to {file_path}")
            else:
                messagebox.showerror("Error", "Failed to export collection")
    
    def import_numista(self):
        """Import collection from Numista Excel export."""
        file_path = filedialog.askopenfilename(
            title="Select Numista Export File",
            filetypes=[("Excel files", "*.xlsx *.xls")]
        )
        
        if file_path:
            try:
                from numista_importer import NumistaImporter
                
                importer = NumistaImporter(self.app.collection)
                imported, duplicates = importer.import_from_excel(file_path)
                
                # Refresh collection list
                self.refresh_collection_list()
                
                # Show import summary
                message = f"Import completed:\n"
                message += f"  Imported: {imported} items\n"
                message += f"  Duplicates skipped: {duplicates} items"
                
                if duplicates > 0:
                    message += f"\n\nDuplicate items were not imported."
                
                messagebox.showinfo("Import Complete", message)
                
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to import Numista export: {str(e)}")

    def open_collection_intelligence_lookup(self):
        """Open read-only collection intelligence lookup dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Do I Own This?")
        dialog.geometry("720x760")
        staged_want_list_intents = self._active_want_list_intents()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        form_frame = ttk.LabelFrame(main_frame, text="Candidate Item", padding="10")
        form_frame.pack(fill=tk.X, pady=(0, 10))

        fields = [
            ("Country:", tk.StringVar()),
            ("Denomination:", tk.StringVar()),
            ("Year:", tk.StringVar()),
            ("Type / Series:", tk.StringVar()),
            ("Variety:", tk.StringVar()),
            ("Grade:", tk.StringVar()),
            ("Certifier:", tk.StringVar()),
            ("Certification #:", tk.StringVar()),
            ("Asking Price:", tk.StringVar()),
        ]
        field_vars = {}
        for row, (label, variable) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=4)
            key = label.rstrip(":").lower().replace(" / ", "_").replace(" ", "_").replace("#", "number")
            field_vars[key] = variable
            if label == "Grade:":
                ttk.Combobox(
                    form_frame,
                    textvariable=variable,
                    values=[
                        "", "PO-1", "FR-2", "AG-3", "G-4", "VG-8", "F-12",
                        "VF-20", "VF-30", "EF-40", "EF-45", "AU-50", "AU-53",
                        "AU-55", "AU-58", "MS-60", "MS-61", "MS-62", "MS-63",
                        "MS-64", "MS-65", "MS-66", "MS-67", "MS-68", "MS-69",
                        "MS-70",
                    ],
                ).grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)
            else:
                ttk.Entry(form_frame, textvariable=variable).grid(
                    row=row, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4
                )

        ttk.Label(form_frame, text="Notes:").grid(row=len(fields), column=0, sticky=(tk.W, tk.N), pady=4)
        notes_text = tk.Text(form_frame, height=4, wrap=tk.WORD)
        notes_text.grid(row=len(fields), column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)
        if staged_want_list_intents:
            want_list_status = f"WANT_LIST context: {len(staged_want_list_intents)} shared active intent(s) loaded"
        else:
            want_list_status = "WANT_LIST context: unavailable"
        want_list_status_var = tk.StringVar(value=want_list_status)
        ttk.Label(form_frame, textvariable=want_list_status_var).grid(
            row=len(fields) + 1, column=0, columnspan=2, sticky=tk.W, pady=(8, 0)
        )
        form_frame.columnconfigure(1, weight=1)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        result_frame = ttk.LabelFrame(main_frame, text="Analysis", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True)

        def parse_price(value):
            cleaned = value.strip().replace("$", "").replace(",", "")
            if not cleaned:
                return 0.0
            return float(cleaned)

        def format_result(result, acquisition_decision=None):
            lines = [
                "Collection Intelligence",
                "",
                f"Match Status: {result.match_status.value}",
                f"Recommendation: {result.recommendation}",
                f"Confidence Score: {result.confidence_score}/100",
                f"WANT_LIST Status: {result.want_list_status}",
                "",
                "Best Existing Match:",
            ]
            if result.best_existing_match:
                match = result.best_existing_match
                lines.extend([
                    f"  ID: {match.item_id}",
                    f"  Coin: {match.country} {match.denomination} {match.year}",
                    f"  Grade: {match.grade or 'Unknown'}",
                    f"  Match Type: {match.match_type}",
                    f"  Match Score: {match.match_score}/100",
                    f"  Variety Match: {'Yes' if match.variety_match else 'No'}",
                    f"  Certified: {'Yes' if match.certified else 'No'}",
                ])
            else:
                lines.append("  None")
            lines.extend([
                "",
                f"Grade Comparison: {result.grade_comparison}",
                f"Collection Impact: {result.collection_impact}",
                "",
                "Priority Reasons:",
            ])
            lines.extend([f"  - {reason}" for reason in result.priority_reasons] or ["  None"])
            lines.append("")
            lines.append("Warning Flags:")
            lines.extend([f"  - {warning}" for warning in result.warning_flags] or ["  None"])
            if acquisition_decision:
                lines.extend([
                    "",
                    "Acquisition Guidance:",
                    f"  Recommendation: {acquisition_decision.recommendation}",
                    f"  Asking Price: ${acquisition_decision.asking_price:.2f}",
                    f"  Max Rational Price: ${acquisition_decision.max_rational_price:.2f}",
                    f"  Confidence Score: {acquisition_decision.confidence_score}/100",
                ])
            return "\n".join(lines)

        def analyze_candidate():
            try:
                candidate = CandidateItem(
                    country=field_vars["country"].get().strip(),
                    denomination=field_vars["denomination"].get().strip(),
                    year=field_vars["year"].get().strip(),
                    type_series=field_vars["type_series"].get().strip(),
                    variety=field_vars["variety"].get().strip(),
                    grade=field_vars["grade"].get().strip(),
                    certifier=field_vars["certifier"].get().strip(),
                    certification_number=field_vars["certification_number"].get().strip(),
                    asking_price=parse_price(field_vars["asking_price"].get()),
                    notes=notes_text.get("1.0", tk.END).strip(),
                )
                engine = FocusedCollectionIntelligenceEngine(
                    self.app.collection.get_all_items(),
                    staged_want_list_intents,
                )
                result = engine.analyze_candidate(candidate)
                acquisition_decision = None
                if candidate.asking_price > 0:
                    acquisition_decision = AcquisitionWorkflow(
                        self.app.collection.get_all_items(),
                        staged_want_list_intents,
                    ).evaluate(candidate)
                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, format_result(result, acquisition_decision))
            except ValueError:
                messagebox.showerror("Invalid Price", "Please enter a numeric asking price.")
            except Exception as e:
                messagebox.showerror("Analysis Error", f"Collection intelligence failed: {str(e)}")

        def load_want_list_context():
            nonlocal staged_want_list_intents
            file_path = filedialog.askopenfilename(
                title="Select Legacy Portfolio Workbook",
                filetypes=[("Excel files", "*.xlsx *.xlsm *.xls"), ("All files", "*.*")]
            )
            if not file_path:
                return
            try:
                importer = LegacyPortfolioImporter(self.app.collection.get_all_items())
                preview = importer.preview_want_list(file_path)
                staged_want_list_intents = preview.staged_intents
                self.session_context.load_want_list_context(file_path, self._collection_items())
                self.refresh_session_status()
                want_list_status_var.set(
                    f"WANT_LIST context: {preview.intents_staged} active intent(s) loaded"
                )
            except Exception as e:
                staged_want_list_intents = []
                want_list_status_var.set("WANT_LIST context: unavailable")
                messagebox.showerror("WANT_LIST Error", f"Failed to load WANT_LIST context: {str(e)}")

        ttk.Button(button_frame, text="Load WANT_LIST Context", command=load_want_list_context).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Analyze", command=analyze_candidate).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_listing_analyzer(self):
        """Open offline listing analyzer dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Listing Analyzer")
        dialog.geometry("780x760")

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        form_frame = ttk.LabelFrame(main_frame, text="Listing", padding="10")
        form_frame.pack(fill=tk.X, pady=(0, 10))
        form_frame.columnconfigure(1, weight=1)

        title_var = tk.StringVar()
        url_var = tk.StringVar()
        price_var = tk.StringVar()
        shipping_var = tk.StringVar()
        seller_var = tk.StringVar()
        source_var = tk.StringVar()

        fields = [
            ("Title:", title_var),
            ("URL:", url_var),
            ("Price:", price_var),
            ("Shipping:", shipping_var),
            ("Seller:", seller_var),
            ("Source:", source_var),
        ]
        for row, (label, variable) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=4)
            ttk.Entry(form_frame, textvariable=variable).grid(
                row=row, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4
            )

        ttk.Label(form_frame, text="Seller Notes:").grid(row=len(fields), column=0, sticky=(tk.W, tk.N), pady=4)
        notes_text = tk.Text(form_frame, height=3, wrap=tk.WORD)
        notes_text.grid(row=len(fields), column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)

        ttk.Label(form_frame, text="Description:").grid(row=len(fields) + 1, column=0, sticky=(tk.W, tk.N), pady=4)
        description_text = tk.Text(form_frame, height=4, wrap=tk.WORD)
        description_text.grid(row=len(fields) + 1, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)

        context_label = ttk.Label(
            form_frame,
            text=self.session_context.format_status_line(),
            wraplength=680,
        )
        context_label.grid(row=len(fields) + 2, column=0, columnspan=2, sticky=tk.W, pady=(8, 0))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        result_frame = ttk.LabelFrame(main_frame, text="Analysis", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True)

        def parse_money(value):
            cleaned = value.strip().replace("$", "").replace(",", "")
            if not cleaned:
                return 0.0
            return float(cleaned)

        def format_listing_result(result):
            candidate = result.candidate
            lines = [
                "Listing Analyzer",
                "",
                f"Title: {result.listing.title}",
                f"URL: {result.listing.url or 'Not provided'}",
                f"Price: ${result.listing.price:.2f}",
                f"Shipping: ${result.listing.shipping:.2f}",
                f"Total Cost: ${result.listing.total_cost:.2f}",
                "",
                "Parsed Candidate:",
                f"  Country: {candidate.country or 'Unknown'}",
                f"  Denomination: {candidate.denomination or 'Unknown'}",
                f"  Year: {candidate.year or 'Unknown'}",
                f"  Grade: {candidate.grade or 'Unknown'}",
                f"  Variety: {candidate.variety or 'None'}",
                f"  Certifier: {candidate.certifier or 'None'}",
                "",
                "Acquisition Analysis:",
                f"  Ownership Status: {result.ownership_status}",
                f"  Duplicate Status: {result.duplicate_status}",
                f"  Upgrade Status: {result.upgrade_status}",
                f"  WANT_LIST Status: {result.want_list_status}",
                f"  Collection Impact: {result.collection_impact}",
                f"  Priority Score: {result.priority_score}",
                f"  Acquisition Impact Score: {result.acquisition_impact_score}",
                f"  Quality Impact: {result.quality_impact:+d}",
                f"  Completion Impact: {result.completion_impact:+.1f}%",
                f"  Max Rational Price: ${result.max_rational_price:.2f}",
                f"  Recommendation: {result.recommendation}",
            ]
            if result.recommendation_reasoning:
                lines.extend(["", "Recommendation Reasoning:"])
                lines.extend(f"  - {reason}" for reason in result.recommendation_reasoning)
            if result.acquisition_decision.priority_reasons:
                lines.extend(["", "Priority Reasons:"])
                lines.extend(f"  - {reason}" for reason in result.acquisition_decision.priority_reasons)
            explanation = ShoppingExplanationEngine().explain_listing_analysis(result)
            lines.extend([
                "",
                "Why:",
                f"  Confidence: {explanation.explanation.confidence.level} - {explanation.explanation.confidence.explanation}",
                "  Primary Reasons:",
            ])
            lines.extend(f"  - {reason}" for reason in explanation.explanation.primary_reasons)
            if explanation.explanation.supporting_reasons:
                lines.extend(["", "  Supporting Reasons:"])
                lines.extend(f"  - {reason}" for reason in explanation.explanation.supporting_reasons[:6])
            if result.warnings:
                lines.extend(["", "Warnings:"])
                lines.extend(f"  - {warning}" for warning in result.warnings)
            return "\n".join(lines)

        def analyze_listing():
            try:
                listing = ListingCandidate(
                    title=title_var.get(),
                    price=parse_money(price_var.get()),
                    shipping=parse_money(shipping_var.get()),
                    url=url_var.get(),
                    notes=notes_text.get("1.0", tk.END).strip(),
                    seller=seller_var.get(),
                    source=source_var.get(),
                    description=description_text.get("1.0", tk.END).strip(),
                )
                analyzer = ListingAnalyzer(
                    self._collection_items(),
                    self._active_want_list_intents(),
                )
                result = analyzer.analyze(listing)
                self.shopping_candidates.append(ShoppingCandidate.from_listing(listing))
                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, format_listing_result(result))
            except ValueError:
                messagebox.showerror("Invalid Price", "Please enter numeric price and shipping values.")
            except Exception as e:
                messagebox.showerror("Listing Analyzer Error", f"Listing analysis failed: {str(e)}")

        ttk.Button(button_frame, text="Analyze Listing", command=analyze_listing).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_photo_assisted_entry(self):
        """Open metadata-only photo-assisted candidate workflow."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Photo-Assisted Entry")
        dialog.geometry("820x760")

        current_report = {"report": None}

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        form_frame = ttk.LabelFrame(main_frame, text="Photo Candidate", padding="10")
        form_frame.pack(fill=tk.X, pady=(0, 10))
        form_frame.columnconfigure(1, weight=1)

        title_var = tk.StringVar()
        front_var = tk.StringVar()
        reverse_var = tk.StringVar()
        reference_var = tk.StringVar()
        price_var = tk.StringVar()
        source_var = tk.StringVar(value="Photo-Assisted Entry")

        def browse_photo(target_var):
            path = filedialog.askopenfilename(
                title="Select Photo Reference",
                filetypes=[
                    ("Image files", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"),
                    ("All files", "*.*"),
                ],
            )
            if path:
                target_var.set(path)

        fields = [
            ("Title:", title_var, None),
            ("Front Photo:", front_var, browse_photo),
            ("Reverse Photo:", reverse_var, browse_photo),
            ("Reference Photos (;):", reference_var, None),
            ("Asking Price:", price_var, None),
            ("Source:", source_var, None),
        ]
        for row, (label, variable, browse) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=4)
            entry = ttk.Entry(form_frame, textvariable=variable)
            entry.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)
            if browse:
                ttk.Button(form_frame, text="Browse", command=lambda var=variable: browse_photo(var)).grid(
                    row=row, column=2, sticky=tk.W, padx=(6, 0), pady=4
                )

        ttk.Label(form_frame, text="Notes:").grid(row=len(fields), column=0, sticky=(tk.W, tk.N), pady=4)
        notes_text = tk.Text(form_frame, height=4, wrap=tk.WORD)
        notes_text.grid(row=len(fields), column=1, columnspan=2, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)

        result_frame = ttk.LabelFrame(main_frame, text="Photo Review", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def parse_money(value):
            cleaned = value.strip().replace("$", "").replace(",", "")
            if not cleaned:
                return 0.0
            return float(cleaned)

        def analyze_photo_candidate():
            try:
                engine = PhotoAssistedEntry(
                    self._collection_items(),
                    self._active_want_list_intents(),
                    photo_records=self.photo_records,
                    market_awareness_engine=self.market_awareness_engine,
                )
                candidate = engine.create_candidate(
                    title=title_var.get(),
                    front_photo=front_var.get(),
                    reverse_photo=reverse_var.get(),
                    reference_photos=[part.strip() for part in reference_var.get().split(";") if part.strip()],
                    notes=notes_text.get("1.0", tk.END).strip(),
                    asking_price=parse_money(price_var.get()),
                    source=source_var.get(),
                )
                report = engine.analyze_candidate(candidate)
                current_report["report"] = report
                self.photo_candidates.append(candidate)
                self.photo_records = list(engine.photo_vault.records)
                self.shopping_candidates.append(candidate.to_shopping_candidate())
                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, report.format_markdown())
            except ValueError:
                messagebox.showerror("Invalid Price", "Please enter a numeric asking price.")
            except Exception as e:
                messagebox.showerror("Photo-Assisted Entry Error", f"Photo-assisted analysis failed: {str(e)}")

        def export_photo_report(export_type):
            report = current_report.get("report")
            if not report:
                messagebox.showwarning("No Report", "Analyze a photo candidate before exporting.")
                return
            extension = ".md" if export_type == "markdown" else ".csv"
            filetypes = [("Markdown files", "*.md")] if export_type == "markdown" else [("CSV files", "*.csv")]
            file_path = filedialog.asksaveasfilename(
                title="Export Photo Review",
                defaultextension=extension,
                filetypes=filetypes + [("All files", "*.*")],
            )
            if not file_path:
                return
            ok = report.export_markdown(file_path) if export_type == "markdown" else report.export_csv(file_path)
            if ok:
                messagebox.showinfo("Export Complete", f"Photo review exported to {file_path}")
            else:
                messagebox.showerror("Export Failed", "Could not export the photo review report.")

        ttk.Button(button_frame, text="Analyze Photo Candidate", command=analyze_photo_candidate).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=lambda: export_photo_report("markdown")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=lambda: export_photo_report("csv")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_ocr_experiment(self):
        """Open advisory-only OCR experiment workflow."""
        dialog = tk.Toplevel(self.root)
        dialog.title("OCR Experiment")
        dialog.geometry("820x760")

        current_report = {"report": None, "validation": None}

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        form_frame = ttk.LabelFrame(main_frame, text="OCR Source", padding="10")
        form_frame.pack(fill=tk.X, pady=(0, 10))
        form_frame.columnconfigure(1, weight=1)

        image_var = tk.StringVar()

        def browse_image():
            path = filedialog.askopenfilename(
                title="Select Image for OCR Experiment",
                filetypes=[
                    ("Image files", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"),
                    ("All files", "*.*"),
                ],
            )
            if path:
                image_var.set(path)

        ttk.Label(form_frame, text="Image Path:").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Entry(form_frame, textvariable=image_var).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)
        ttk.Button(form_frame, text="Browse", command=browse_image).grid(row=0, column=2, sticky=tk.W, padx=(6, 0), pady=4)

        ttk.Label(form_frame, text="Raw OCR Text:").grid(row=1, column=0, sticky=(tk.W, tk.N), pady=4)
        raw_text = tk.Text(form_frame, height=5, wrap=tk.WORD)
        raw_text.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)

        ttk.Label(
            form_frame,
            text="OCR output is advisory only and requires manual review. It never updates collection records.",
            wraplength=680,
        ).grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(8, 0))

        result_frame = ttk.LabelFrame(main_frame, text="OCR Suggestion Report", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def run_ocr():
            try:
                from inference_telemetry import get_default_telemetry_sink

                supplied_text = raw_text.get("1.0", tk.END).strip()
                report = OCRExperiment(
                    telemetry_sink=get_default_telemetry_sink(),
                ).run(
                    image_path=image_var.get(),
                    raw_text=supplied_text if supplied_text else None,
                )
                validation = OCRValidationEngine().validate(suggestion_report=report)
                current_report["report"] = report
                current_report["validation"] = validation
                self.ocr_results.append(report.result)
                self.ocr_reports.append(report)
                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, report.format_markdown() + "\n" + validation.format_markdown())
            except Exception as e:
                messagebox.showerror("OCR Experiment Error", f"OCR experiment failed: {str(e)}")

        def export_ocr_report(export_type):
            validation = current_report.get("validation")
            if not validation:
                messagebox.showwarning("No Report", "Run an OCR experiment before exporting.")
                return
            extension = ".md" if export_type == "markdown" else ".csv"
            filetypes = [("Markdown files", "*.md")] if export_type == "markdown" else [("CSV files", "*.csv")]
            file_path = filedialog.asksaveasfilename(
                title="Export OCR Validation Report",
                defaultextension=extension,
                filetypes=filetypes + [("All files", "*.*")],
            )
            if not file_path:
                return
            ok = validation.export_markdown(file_path) if export_type == "markdown" else validation.export_csv(file_path)
            if ok:
                messagebox.showinfo("Export Complete", f"OCR validation report exported to {file_path}")
            else:
                messagebox.showerror("Export Failed", "Could not export the OCR validation report.")

        ttk.Button(button_frame, text="Run OCR Experiment", command=run_ocr).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=lambda: export_ocr_report("markdown")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=lambda: export_ocr_report("csv")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_ocr_assisted_identification(self):
        """Open review-only OCR-assisted identification workflow."""
        dialog = tk.Toplevel(self.root)
        dialog.title("OCR-Assisted Identification")
        dialog.geometry("920x820")

        current_report = {"report": None}

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        form_frame = ttk.LabelFrame(main_frame, text="Identification Source", padding="10")
        form_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 10))
        form_frame.columnconfigure(1, weight=1)

        image_var = tk.StringVar()
        use_latest_capture_var = tk.BooleanVar(value=False)

        def browse_image():
            path = filedialog.askopenfilename(
                title="Select Image for OCR-Assisted Identification",
                filetypes=[
                    ("Image files", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"),
                    ("All files", "*.*"),
                ],
            )
            if path:
                image_var.set(path)

        ttk.Label(form_frame, text="Image Path:").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Entry(form_frame, textvariable=image_var).grid(row=0, column=1, sticky=tk.EW, padx=(8, 0), pady=4)
        ttk.Button(form_frame, text="Browse", command=browse_image).grid(row=0, column=2, sticky=tk.W, padx=(6, 0), pady=4)
        ttk.Checkbutton(
            form_frame,
            text="Use latest captured photo",
            variable=use_latest_capture_var,
        ).grid(row=1, column=1, sticky=tk.W, padx=(8, 0), pady=4)

        ttk.Label(form_frame, text="Raw OCR Text:").grid(row=2, column=0, sticky=(tk.W, tk.N), pady=4)
        raw_text = tk.Text(form_frame, height=6, wrap=tk.WORD)
        raw_text.grid(row=2, column=1, columnspan=2, sticky=tk.EW, padx=(8, 0), pady=4)

        ttk.Label(
            form_frame,
            text="Identification candidates are suggestions only. Manual review is mandatory and collection records are never changed.",
            wraplength=760,
        ).grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=(8, 0))

        result_frame = ttk.LabelFrame(main_frame, text="OCR-Assisted Identification Report", padding="10")
        result_frame.grid(row=1, column=0, sticky=tk.NSEW)
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.grid(row=0, column=0, sticky=tk.NSEW)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky=tk.W, pady=(10, 0))

        def latest_captured_photo():
            for session in reversed(self.photo_capture_workflow.sessions):
                if session.photos:
                    return session.photos[-1]
            return None

        def engine():
            from inference_telemetry import get_default_telemetry_sink

            return OCRIdentificationEngine(
                collection_items=self._collection_items(),
                want_list_intents=self._active_want_list_intents(),
                watchlists=self.watchlists,
                ocr_experiment=OCRExperiment(
                    telemetry_sink=get_default_telemetry_sink(),
                ),
            )

        def run_identification():
            try:
                supplied_text = raw_text.get("1.0", tk.END).strip()
                if use_latest_capture_var.get():
                    photo = latest_captured_photo()
                    if not photo:
                        messagebox.showwarning("No Captured Photo", "Add a phone photo capture before using the latest captured photo.")
                        return
                    report = engine().identify_from_captured_photo(photo, raw_text=supplied_text if supplied_text else None)
                else:
                    if not image_var.get().strip() and not supplied_text:
                        messagebox.showwarning("Input Required", "Provide an image path or pasted OCR text before running identification.")
                        return
                    report = engine().identify(
                        image_path=image_var.get(),
                        raw_text=supplied_text if supplied_text else None,
                    )
                current_report["report"] = report
                self.ocr_identification_reports.append(report)
                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, report.format_markdown())
            except Exception as exc:
                messagebox.showerror("OCR-Assisted Identification Error", f"OCR-assisted identification failed: {str(exc)}")

        def export_report(export_type):
            report = current_report.get("report")
            if not report:
                messagebox.showwarning("No Report", "Run OCR-assisted identification before exporting.")
                return
            extension = ".md" if export_type == "markdown" else ".csv"
            filetypes = [("Markdown files", "*.md")] if export_type == "markdown" else [("CSV files", "*.csv")]
            file_path = filedialog.asksaveasfilename(
                title="Export OCR-Assisted Identification",
                defaultextension=extension,
                filetypes=filetypes + [("All files", "*.*")],
            )
            if not file_path:
                return
            ok = report.export_markdown(file_path) if export_type == "markdown" else report.export_csv(file_path)
            if ok:
                messagebox.showinfo("Export Complete", f"OCR-assisted identification exported to {file_path}")
            else:
                messagebox.showerror("Export Failed", "Could not export the OCR-assisted identification report.")

        ttk.Button(button_frame, text="Generate Candidates", command=run_identification).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=lambda: export_report("markdown")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=lambda: export_report("csv")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_mobile_collection_entry(self):
        """Open review-only Mobile Collection Entry workflow."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Mobile Collection Entry")
        dialog.geometry("980x840")

        current_report = {"report": None}

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        form_frame = ttk.LabelFrame(main_frame, text="Entry Candidate Source", padding="10")
        form_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 10))
        form_frame.columnconfigure(1, weight=1)

        source_var = tk.StringVar(value=ENTRY_WORKFLOW_COIN_SHOW)
        use_latest_ocr_var = tk.BooleanVar(value=bool(self.ocr_identification_reports))
        workflow_values = [
            ENTRY_WORKFLOW_COIN_SHOW,
            ENTRY_WORKFLOW_DEALER_VISIT,
            ENTRY_WORKFLOW_COIN_SHOP,
            ENTRY_WORKFLOW_AUCTION_PREVIEW,
            ENTRY_WORKFLOW_ANTIQUE_MARKET,
        ]

        ttk.Label(form_frame, text="Field Workflow:").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Combobox(form_frame, textvariable=source_var, values=workflow_values, state="readonly").grid(row=0, column=1, sticky=tk.EW, padx=(8, 0), pady=4)
        ttk.Checkbutton(
            form_frame,
            text="Use latest OCR-assisted identification report",
            variable=use_latest_ocr_var,
        ).grid(row=1, column=1, sticky=tk.W, padx=(8, 0), pady=4)

        ttk.Label(form_frame, text="Raw OCR Text:").grid(row=2, column=0, sticky=(tk.W, tk.N), pady=4)
        raw_text = tk.Text(form_frame, height=7, wrap=tk.WORD)
        raw_text.grid(row=2, column=1, sticky=tk.EW, padx=(8, 0), pady=4)
        raw_text.insert(tk.END, "Canada 1945 5 cents George VI")

        ttk.Label(
            form_frame,
            text="Entry records are preview-only. Approval prepares a reviewed record but never inserts it into the collection automatically.",
            wraplength=800,
        ).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(8, 0))

        result_frame = ttk.LabelFrame(main_frame, text="Mobile Collection Entry Report", padding="10")
        result_frame.grid(row=1, column=0, sticky=tk.NSEW)
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.grid(row=0, column=0, sticky=tk.NSEW)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky=tk.W, pady=(10, 0))

        def engine():
            return MobileCollectionEntryEngine(
                collection_items=self._collection_items(),
                want_list_intents=self._active_want_list_intents(),
                watchlists=self.watchlists,
            )

        def show_report(report):
            current_report["report"] = report
            if not self.mobile_entry_reports or self.mobile_entry_reports[-1] is not report:
                self.mobile_entry_reports.append(report)
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, report.format_markdown())

        def generate():
            try:
                source = source_var.get() or ENTRY_WORKFLOW_COIN_SHOW
                entry_engine = engine()
                if use_latest_ocr_var.get() and self.ocr_identification_reports:
                    report = entry_engine.from_ocr_report(self.ocr_identification_reports[-1], acquisition_source=source)
                else:
                    supplied_text = raw_text.get("1.0", tk.END).strip()
                    if not supplied_text:
                        messagebox.showwarning("Input Required", "Provide OCR text or use the latest OCR-assisted identification report.")
                        return
                    report = entry_engine.identify_and_prepare(raw_text=supplied_text, acquisition_source=source)
                show_report(report)
            except Exception as exc:
                messagebox.showerror("Mobile Collection Entry Error", f"Mobile collection entry failed: {str(exc)}")

        def review_first(decision):
            report = current_report.get("report")
            if not report:
                generate()
                report = current_report.get("report")
            if not report or not report.candidates:
                return
            review = engine().review_candidate(report.candidates[0], decision)
            report.reviews = [existing for existing in report.reviews if existing.candidate_id != review.candidate_id]
            report.reviews.insert(0, review)
            show_report(report)

        def export_report(export_type):
            report = current_report.get("report")
            if not report:
                messagebox.showwarning("No Report", "Generate mobile entry candidates before exporting.")
                return
            extension = ".md" if export_type == "markdown" else ".csv"
            filetypes = [("Markdown files", "*.md")] if export_type == "markdown" else [("CSV files", "*.csv")]
            file_path = filedialog.asksaveasfilename(
                title="Export Mobile Collection Entry",
                defaultextension=extension,
                filetypes=filetypes + [("All files", "*.*")],
            )
            if not file_path:
                return
            ok = report.export_markdown(file_path) if export_type == "markdown" else report.export_csv(file_path)
            if ok:
                messagebox.showinfo("Export Complete", f"Mobile collection entry exported to {file_path}")
            else:
                messagebox.showerror("Export Failed", "Could not export the mobile collection entry report.")

        ttk.Button(button_frame, text="Generate Entry Candidates", command=generate).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Approve First", command=lambda: review_first(ENTRY_APPROVE)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Reject First", command=lambda: review_first(ENTRY_REJECT)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Review First", command=lambda: review_first(ENTRY_REVIEW)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=lambda: export_report("markdown")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=lambda: export_report("csv")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_collector_workflow_integration(self):
        """Open end-to-end Collector Workflow Integration."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Collector Workflow Integration")
        dialog.geometry("1040x860")

        current_report = {"report": None}

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        form_frame = ttk.LabelFrame(main_frame, text="Workflow Intake", padding="10")
        form_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 10))
        form_frame.columnconfigure(1, weight=1)

        subject_var = tk.StringVar(value="Canada 1945 5 cents")
        front_var = tk.StringVar()
        back_var = tk.StringVar()
        location_var = tk.StringVar(value="Field workflow")

        ttk.Label(form_frame, text="Subject:").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Entry(form_frame, textvariable=subject_var).grid(row=0, column=1, sticky=tk.EW, padx=(8, 0), pady=4)
        ttk.Label(form_frame, text="Front Photo:").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Entry(form_frame, textvariable=front_var).grid(row=1, column=1, sticky=tk.EW, padx=(8, 0), pady=4)
        ttk.Label(form_frame, text="Back Photo:").grid(row=2, column=0, sticky=tk.W, pady=4)
        ttk.Entry(form_frame, textvariable=back_var).grid(row=2, column=1, sticky=tk.EW, padx=(8, 0), pady=4)
        ttk.Label(form_frame, text="Location:").grid(row=3, column=0, sticky=tk.W, pady=4)
        ttk.Entry(form_frame, textvariable=location_var).grid(row=3, column=1, sticky=tk.EW, padx=(8, 0), pady=4)
        ttk.Label(form_frame, text="Raw OCR Text:").grid(row=4, column=0, sticky=(tk.W, tk.N), pady=4)
        raw_text = tk.Text(form_frame, height=5, wrap=tk.WORD)
        raw_text.grid(row=4, column=1, sticky=tk.EW, padx=(8, 0), pady=4)
        raw_text.insert(tk.END, "Canada 1945 5 cents George VI")

        result_frame = ttk.LabelFrame(main_frame, text="Workflow Report", padding="10")
        result_frame.grid(row=1, column=0, sticky=tk.NSEW)
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.grid(row=0, column=0, sticky=tk.NSEW)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky=tk.W, pady=(10, 0))

        def engine():
            return CollectorWorkflowIntegrationEngine(
                collection_items=self._collection_items(),
                want_list_intents=self._active_want_list_intents(),
                watchlists=self.watchlists,
                photo_capture_workflow=self.photo_capture_workflow,
            )

        def show_report(report):
            current_report["report"] = report
            if not self.workflow_completion_reports or self.workflow_completion_reports[-1] is not report:
                self.workflow_completion_reports.append(report)
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, report.format_markdown())

        def generate():
            try:
                supplied_text = raw_text.get("1.0", tk.END).strip()
                if not supplied_text and not front_var.get().strip() and not back_var.get().strip():
                    messagebox.showwarning("Input Required", "Provide OCR text or photo paths before running the workflow.")
                    return
                report = engine().run_workflow(
                    subject=subject_var.get(),
                    raw_text=supplied_text,
                    front_path=front_var.get(),
                    back_path=back_var.get(),
                    location=location_var.get(),
                )
                if report.session.ocr_report:
                    self.ocr_identification_reports.append(report.session.ocr_report)
                if report.session.entry_report:
                    self.mobile_entry_reports.append(report.session.entry_report)
                show_report(report)
            except Exception as exc:
                messagebox.showerror("Collector Workflow Error", f"Collector workflow failed: {str(exc)}")

        def review_final(decision):
            report = current_report.get("report")
            if not report:
                generate()
                report = current_report.get("report")
            if not report:
                return
            engine().review_stage(report.session, STAGE_FINAL_REVIEW, decision, "Collector final review checkpoint")
            show_report(report)

        def export_report(export_type):
            report = current_report.get("report")
            if not report:
                messagebox.showwarning("No Report", "Generate a collector workflow before exporting.")
                return
            extension = ".md" if export_type == "markdown" else ".csv"
            filetypes = [("Markdown files", "*.md")] if export_type == "markdown" else [("CSV files", "*.csv")]
            file_path = filedialog.asksaveasfilename(
                title="Export Collector Workflow",
                defaultextension=extension,
                filetypes=filetypes + [("All files", "*.*")],
            )
            if not file_path:
                return
            ok = report.export_markdown(file_path) if export_type == "markdown" else report.export_csv(file_path)
            if ok:
                messagebox.showinfo("Export Complete", f"Collector workflow exported to {file_path}")

        def export_health(export_type):
            health = engine().health_report([report.session for report in self.workflow_completion_reports])
            extension = ".md" if export_type == "markdown" else ".csv"
            filetypes = [("Markdown files", "*.md")] if export_type == "markdown" else [("CSV files", "*.csv")]
            file_path = filedialog.asksaveasfilename(
                title="Export Collector Workflow Health",
                defaultextension=extension,
                filetypes=filetypes + [("All files", "*.*")],
            )
            if not file_path:
                return
            ok = health.export_markdown(file_path) if export_type == "markdown" else health.export_csv(file_path)
            if ok:
                messagebox.showinfo("Export Complete", f"Collector workflow health exported to {file_path}")

        ttk.Button(button_frame, text="Run Workflow", command=generate).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Approve Final", command=lambda: review_final(WORKFLOW_APPROVE)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Reject Final", command=lambda: review_final(WORKFLOW_REJECT)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Review Final", command=lambda: review_final(WORKFLOW_REVIEW)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=lambda: export_report("markdown")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=lambda: export_report("csv")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Health", command=lambda: export_health("markdown")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)


    def open_collector_cloud_foundation(self):
        """Open offline Collector Cloud Foundation reports."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Collector Cloud Foundation")
        dialog.geometry("1040x820")

        current_report = {"report": None}

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        summary_var = tk.StringVar(value="No cloud foundation report generated.")
        ttk.Label(main_frame, textvariable=summary_var).grid(row=0, column=0, sticky=tk.W, pady=(0, 8))

        result_frame = ttk.LabelFrame(main_frame, text="Collector Cloud Foundation", padding="10")
        result_frame.grid(row=1, column=0, sticky=tk.NSEW)
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.grid(row=0, column=0, sticky=tk.NSEW)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky=tk.W, pady=(10, 0))

        def engine():
            return CollectorCloud(
                collection_items=self._collection_items(),
                want_list_intents=self._active_want_list_intents(),
                workflow_completion_reports=self.workflow_completion_reports,
                mobile_entry_reports=self.mobile_entry_reports,
                settings=self.app_preferences,
            )

        def show_report(report, summary):
            current_report["report"] = report
            summary_var.set(summary)
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, report.format_markdown())

        def create_snapshot():
            try:
                cloud = engine()
                snapshot = cloud.create_snapshot("GUI local workspace")
                self.cloud_snapshots.append(snapshot)
                show_report(snapshot, f"Snapshot records: {snapshot.record_count} | Hash: {snapshot.content_hash[:12]}")
            except Exception as exc:
                messagebox.showerror("Collector Cloud Error", f"Snapshot failed: {str(exc)}")

        def create_sync_plan():
            try:
                if len(self.cloud_snapshots) < 2:
                    create_snapshot()
                    if len(self.cloud_snapshots) < 2:
                        messagebox.showwarning("Snapshots Required", "Create at least two snapshots before generating a sync plan.")
                        return
                cloud = engine()
                plan = cloud.create_sync_plan(self.cloud_snapshots[-2], self.cloud_snapshots[-1])
                self.cloud_sync_plans.append(plan)
                show_report(plan, f"Plan changes: {plan.proposed_change_count} | Conflicts: {plan.conflict_count}")
            except Exception as exc:
                messagebox.showerror("Collector Cloud Error", f"Sync plan failed: {str(exc)}")

        def create_backup_package():
            try:
                cloud = engine()
                snapshot = self.cloud_snapshots[-1] if self.cloud_snapshots else cloud.create_snapshot("GUI backup snapshot")
                if not self.cloud_snapshots:
                    self.cloud_snapshots.append(snapshot)
                package = cloud.create_backup_package(snapshot, "GUI backup package")
                self.cloud_backup_packages.append(package)
                show_report(package, f"Backup package records: {package.snapshot.record_count} | Restore executed: NO")
            except Exception as exc:
                messagebox.showerror("Collector Cloud Error", f"Backup package failed: {str(exc)}")

        def create_readiness_report():
            try:
                cloud = engine()
                for snapshot in self.cloud_snapshots:
                    cloud.snapshots.append(snapshot)
                report = cloud.cloud_readiness_report(self.cloud_snapshots)
                self.cloud_readiness_reports.append(report)
                show_report(report, f"Readiness: {report.readiness_score}/100 | Cloud services configured: NO")
            except Exception as exc:
                messagebox.showerror("Collector Cloud Error", f"Readiness report failed: {str(exc)}")

        def show_conflicts():
            try:
                if not self.cloud_sync_plans:
                    create_sync_plan()
                if not self.cloud_sync_plans:
                    return
                plan = self.cloud_sync_plans[-1]
                show_report(plan, f"Conflict preview: {plan.conflict_count} conflict(s); sync executed: NO")
            except Exception as exc:
                messagebox.showerror("Collector Cloud Error", f"Conflict preview failed: {str(exc)}")

        def export_report(export_type):
            report = current_report.get("report")
            if not report:
                messagebox.showwarning("No Report", "Generate a cloud foundation report before exporting.")
                return
            extension = ".md" if export_type == "markdown" else ".csv"
            filetypes = [("Markdown files", "*.md")] if export_type == "markdown" else [("CSV files", "*.csv")]
            file_path = filedialog.asksaveasfilename(
                title="Export Collector Cloud Foundation",
                defaultextension=extension,
                filetypes=filetypes + [("All files", "*.*")],
            )
            if not file_path:
                return
            ok = report.export_markdown(file_path) if export_type == "markdown" else report.export_csv(file_path)
            if ok:
                messagebox.showinfo("Export Complete", f"Collector Cloud Foundation exported to {file_path}")

        ttk.Button(button_frame, text="Create Snapshot", command=create_snapshot).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Sync Plan", command=create_sync_plan).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Backup Package", command=create_backup_package).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Readiness Report", command=create_readiness_report).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Conflict Preview", command=show_conflicts).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=lambda: export_report("markdown")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=lambda: export_report("csv")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_sync_backup(self):
        """Open offline Sync & Backup planning reports."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Sync & Backup")
        dialog.geometry("1040x820")

        current_report = {"report": None}

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        summary_var = tk.StringVar(value="No sync or backup report generated.")
        ttk.Label(main_frame, textvariable=summary_var).grid(row=0, column=0, sticky=tk.W, pady=(0, 8))

        result_frame = ttk.LabelFrame(main_frame, text="Sync & Backup", padding="10")
        result_frame.grid(row=1, column=0, sticky=tk.NSEW)
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.grid(row=0, column=0, sticky=tk.NSEW)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky=tk.W, pady=(10, 0))

        def cloud():
            return CollectorCloud(
                collection_items=self._collection_items(),
                want_list_intents=self._active_want_list_intents(),
                workflow_completion_reports=self.workflow_completion_reports,
                mobile_entry_reports=self.mobile_entry_reports,
                settings=self.app_preferences,
            )

        def engine():
            return SyncBackupEngine(collector_cloud=cloud())

        def show_report(report, summary):
            current_report["report"] = report
            summary_var.set(summary)
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, report.format_markdown())

        def ensure_snapshot(label):
            if self.cloud_snapshots:
                return self.cloud_snapshots[-1]
            snapshot = cloud().create_snapshot(label)
            self.cloud_snapshots.append(snapshot)
            return snapshot

        def create_archive():
            try:
                backup = engine().create_backup_archive(source_snapshot=ensure_snapshot("sync-backup-gui"))
                self.backup_archives.append(backup)
                show_report(backup, f"Backup archive: {backup.record_count} record(s) | checksum {backup.checksum[:12]}")
            except Exception as exc:
                messagebox.showerror("Sync & Backup Error", f"Backup archive failed: {str(exc)}")

        def create_restore_plan():
            try:
                if not self.backup_archives:
                    create_archive()
                if not self.backup_archives:
                    return
                plan = engine().plan_restore(self.backup_archives[-1], current_snapshot=ensure_snapshot("restore-current-gui"))
                self.restore_plans.append(plan)
                show_report(plan, f"Restore plan: {len(plan.affected_records)} affected record(s); restore executed: NO")
            except Exception as exc:
                messagebox.showerror("Sync & Backup Error", f"Restore plan failed: {str(exc)}")

        def create_history():
            try:
                if not self.backup_archives:
                    create_archive()
                history = engine().backup_history(self.backup_archives)
                self.backup_histories.append(history)
                show_report(history, f"Backup history: {len(history.archives)} archive(s)")
            except Exception as exc:
                messagebox.showerror("Sync & Backup Error", f"Backup history failed: {str(exc)}")

        def create_simulation():
            try:
                if len(self.cloud_snapshots) < 2:
                    self.cloud_snapshots.append(cloud().create_snapshot("device-a-gui"))
                    self.cloud_snapshots.append(cloud().create_snapshot("device-b-gui"))
                simulation = engine().simulate_sync(self.cloud_snapshots[-2], self.cloud_snapshots[-1])
                self.sync_simulations.append(simulation)
                self.sync_conflict_reports.append(simulation.conflict_report)
                show_report(simulation, f"Sync simulation: {simulation.sync_plan.proposed_change_count} change(s), {simulation.conflict_report.conflict_count} conflict(s)")
            except Exception as exc:
                messagebox.showerror("Sync & Backup Error", f"Sync simulation failed: {str(exc)}")

        def create_conflict_report():
            try:
                if not self.sync_simulations:
                    create_simulation()
                if not self.sync_simulations:
                    return
                report = self.sync_simulations[-1].conflict_report
                self.sync_conflict_reports.append(report)
                show_report(report, f"Conflict report: {report.conflict_count} conflict(s); auto-resolution: NO")
            except Exception as exc:
                messagebox.showerror("Sync & Backup Error", f"Conflict report failed: {str(exc)}")

        def create_rollback_plan():
            try:
                if not self.backup_archives:
                    create_archive()
                simulation = self.sync_simulations[-1] if self.sync_simulations else None
                restore_plan = self.restore_plans[-1] if self.restore_plans else None
                plan = engine().plan_rollback(
                    "sync" if simulation else "backup",
                    archive=self.backup_archives[-1] if self.backup_archives else None,
                    restore_plan=restore_plan,
                    sync_simulation=simulation,
                )
                self.rollback_plans.append(plan)
                show_report(plan, f"Rollback plan: {len(plan.rollback_targets)} target(s); rollback executed: NO")
            except Exception as exc:
                messagebox.showerror("Sync & Backup Error", f"Rollback plan failed: {str(exc)}")

        def export_report(export_type):
            report = current_report.get("report")
            if not report:
                messagebox.showwarning("No Report", "Generate a Sync & Backup report before exporting.")
                return
            extension = ".md" if export_type == "markdown" else ".csv"
            filetypes = [("Markdown files", "*.md")] if export_type == "markdown" else [("CSV files", "*.csv")]
            file_path = filedialog.asksaveasfilename(
                title="Export Sync & Backup",
                defaultextension=extension,
                filetypes=filetypes + [("All files", "*.*")],
            )
            if not file_path:
                return
            ok = report.export_markdown(file_path) if export_type == "markdown" else report.export_csv(file_path)
            if ok:
                messagebox.showinfo("Export Complete", f"Sync & Backup exported to {file_path}")

        ttk.Button(button_frame, text="Backup Archive", command=create_archive).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Restore Plan", command=create_restore_plan).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="History", command=create_history).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Sync Simulation", command=create_simulation).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Conflict Report", command=create_conflict_report).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Rollback Plan", command=create_rollback_plan).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=lambda: export_report("markdown")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=lambda: export_report("csv")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_multi_device_workspace(self):
        """Open offline Multi-Device Collector Workspace reports."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Multi-Device Workspace")
        dialog.geometry("1080x840")

        current_report = {"report": None}

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        summary_var = tk.StringVar(value="No multi-device workspace report generated.")
        ttk.Label(main_frame, textvariable=summary_var).grid(row=0, column=0, sticky=tk.W, pady=(0, 8))

        result_frame = ttk.LabelFrame(main_frame, text="Multi-Device Workspace", padding="10")
        result_frame.grid(row=1, column=0, sticky=tk.NSEW)
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.grid(row=0, column=0, sticky=tk.NSEW)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
        button_frame_2 = ttk.Frame(main_frame)
        button_frame_2.grid(row=3, column=0, sticky=tk.W, pady=(6, 0))

        def engine():
            cloud = CollectorCloud(
                collection_items=self._collection_items(),
                want_list_intents=self._active_want_list_intents(),
                workflow_completion_reports=self.workflow_completion_reports,
                mobile_entry_reports=self.mobile_entry_reports,
                settings=self.app_preferences,
            )
            return MultiDeviceWorkspaceEngine(
                collection_items=self._collection_items(),
                want_list_intents=self._active_want_list_intents(),
                workflow_completion_reports=self.workflow_completion_reports,
                mobile_entry_reports=self.mobile_entry_reports,
                settings=self.app_preferences,
                collector_cloud=cloud,
                sync_backup_engine=SyncBackupEngine(collector_cloud=cloud),
            )

        def show_report(report, summary):
            current_report["report"] = report
            summary_var.set(summary)
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, report.format_markdown())

        def show_text(markdown, summary, export_report=None):
            current_report["report"] = export_report
            summary_var.set(summary)
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, markdown)

        def ensure_workspace():
            if self.multi_device_workspaces:
                return self.multi_device_workspaces[-1]
            workspace = engine().default_workspace("Collector Multi-Device Workspace")
            self.multi_device_workspaces.append(workspace)
            return workspace

        def create_workspace():
            try:
                workspace = engine().default_workspace("Collector Multi-Device Workspace")
                self.multi_device_workspaces.append(workspace)
                show_report(workspace, f"Workspace devices: {len(workspace.registered_devices)} | Sync readiness: {workspace.sync_readiness}")
            except Exception as exc:
                messagebox.showerror("Multi-Device Workspace Error", f"Workspace creation failed: {str(exc)}")

        def add_default_devices():
            try:
                workspace = ensure_workspace()
                workspace_engine = engine()
                for device_type, name in [
                    (DEVICE_DESKTOP, "Collector Desktop"),
                    (DEVICE_LAPTOP, "Collector Laptop"),
                    (DEVICE_PHONE, "Collector Phone"),
                    (DEVICE_TABLET, "Collector Tablet"),
                ]:
                    workspace.register_device(workspace_engine.create_device_profile(device_type, name))
                show_report(workspace, f"Devices: {len(workspace.registered_devices)} | Backup readiness: {workspace.backup_readiness}")
            except Exception as exc:
                messagebox.showerror("Multi-Device Workspace Error", f"Device registration failed: {str(exc)}")

        def create_snapshot():
            try:
                workspace = ensure_workspace()
                snapshot = engine().create_snapshot(workspace, "multi-device-gui")
                self.workspace_snapshots.append(snapshot)
                show_report(snapshot, f"Snapshot devices: {len(snapshot.devices)} | Cloud snapshot: {snapshot.cloud_snapshot_id}")
            except Exception as exc:
                messagebox.showerror("Multi-Device Workspace Error", f"Snapshot failed: {str(exc)}")

        def capability_report():
            try:
                workspace = ensure_workspace()
                report = engine().capability_report(workspace.registered_devices)
                lines = [
                    "# Device Capability Report",
                    "",
                    f"- Devices: {report['device_count']}",
                    f"- Readiness: {report['readiness']}",
                    "- Real synchronization configured: NO",
                    "",
                    "## Capability Coverage",
                    "",
                ]
                for capability, count in sorted(report["capability_coverage"].items()):
                    lines.append(f"- {capability}: {count}")
                lines.extend(["", "## Missing Capabilities", ""])
                lines.extend(f"- {capability}" for capability in report["missing_capabilities"]) if report["missing_capabilities"] else lines.append("- None")
                show_text("\n".join(lines).rstrip() + "\n", f"Capabilities covered: {len(report['capability_coverage'])}", workspace)
            except Exception as exc:
                messagebox.showerror("Multi-Device Workspace Error", f"Capability report failed: {str(exc)}")

        def activity_summary():
            try:
                workspace = ensure_workspace()
                workspace_engine = engine()
                if not workspace.activities and workspace.registered_devices:
                    activity = workspace_engine.record_activity(
                        workspace,
                        workspace.registered_devices[0],
                        "workspace",
                        "Opened Multi-Device Workspace report",
                    )
                    self.workspace_activities.append(activity)
                summary = workspace_engine.activity_summary(workspace)
                lines = [
                    "# Workspace Activity Summary",
                    "",
                    f"- Activities: {summary['activity_count']}",
                    f"- Active devices: {summary['devices_active']}",
                    f"- Latest activity: {summary['latest_activity'] or 'None'}",
                    "- Background sync: NO",
                    "",
                    "## Activity By Type",
                    "",
                ]
                lines.extend(f"- {key}: {value}" for key, value in sorted(summary["activity_by_type"].items())) if summary["activity_by_type"] else lines.append("- None")
                lines.extend(["", "## Activity By Device", ""])
                lines.extend(f"- {key}: {value}" for key, value in sorted(summary["activity_by_device"].items())) if summary["activity_by_device"] else lines.append("- None")
                show_text("\n".join(lines).rstrip() + "\n", f"Activities: {summary['activity_count']}", workspace)
            except Exception as exc:
                messagebox.showerror("Multi-Device Workspace Error", f"Activity summary failed: {str(exc)}")

        def health_report():
            try:
                workspace = ensure_workspace()
                if not workspace.workspace_snapshots:
                    snapshot = engine().create_snapshot(workspace, "multi-device-health-gui")
                    self.workspace_snapshots.append(snapshot)
                report = engine().health_report(workspace)
                self.workspace_health_reports.append(report)
                show_report(report, f"Health: {report.health_score}/100 | Sync readiness: {report.sync_readiness.get('status')}")
            except Exception as exc:
                messagebox.showerror("Multi-Device Workspace Error", f"Health report failed: {str(exc)}")

        def scenario_desktop_phone_laptop():
            try:
                result = engine().simulate_desktop_phone_laptop(ensure_workspace())
                self.workspace_snapshots.append(result["snapshot"])
                self.workspace_health_reports.append(result["health_report"])
                show_report(result["health_report"], "Scenario: Desktop -> Phone -> Laptop | sync executed: NO")
            except Exception as exc:
                messagebox.showerror("Multi-Device Workspace Error", f"Scenario failed: {str(exc)}")

        def scenario_phone_tablet_desktop():
            try:
                result = engine().simulate_phone_tablet_desktop(ensure_workspace())
                self.workspace_snapshots.append(result["snapshot"])
                self.workspace_health_reports.append(result["health_report"])
                show_report(result["health_report"], "Scenario: Phone -> Tablet -> Desktop | sync executed: NO")
            except Exception as exc:
                messagebox.showerror("Multi-Device Workspace Error", f"Scenario failed: {str(exc)}")

        def export_report(export_type):
            report = current_report.get("report")
            if not report:
                messagebox.showwarning("No Report", "Generate a Multi-Device Workspace report before exporting.")
                return
            extension = ".md" if export_type == "markdown" else ".csv"
            filetypes = [("Markdown files", "*.md")] if export_type == "markdown" else [("CSV files", "*.csv")]
            file_path = filedialog.asksaveasfilename(
                title="Export Multi-Device Workspace",
                defaultextension=extension,
                filetypes=filetypes + [("All files", "*.*")],
            )
            if not file_path:
                return
            ok = report.export_markdown(file_path) if export_type == "markdown" else report.export_csv(file_path)
            if ok:
                messagebox.showinfo("Export Complete", f"Multi-Device Workspace exported to {file_path}")

        ttk.Button(button_frame, text="Create Workspace", command=create_workspace).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Add Devices", command=add_default_devices).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Snapshot", command=create_snapshot).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Capabilities", command=capability_report).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Activity", command=activity_summary).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Health", command=health_report).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame_2, text="Desktop -> Phone -> Laptop", command=scenario_desktop_phone_laptop).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame_2, text="Phone -> Tablet -> Desktop", command=scenario_phone_tablet_desktop).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame_2, text="Export Markdown", command=lambda: export_report("markdown")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame_2, text="Export CSV", command=lambda: export_report("csv")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame_2, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_device_linking(self):
        """Open offline Device Linking & Conflict Resolution reports."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Device Linking & Conflict Resolution")
        dialog.geometry("1080x840")

        current_report = {"report": None}

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        summary_var = tk.StringVar(value="No device-linking report generated.")
        ttk.Label(main_frame, textvariable=summary_var).grid(row=0, column=0, sticky=tk.W, pady=(0, 8))

        result_frame = ttk.LabelFrame(main_frame, text="Device Linking & Conflict Resolution", padding="10")
        result_frame.grid(row=1, column=0, sticky=tk.NSEW)
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.grid(row=0, column=0, sticky=tk.NSEW)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
        button_frame_2 = ttk.Frame(main_frame)
        button_frame_2.grid(row=3, column=0, sticky=tk.W, pady=(6, 0))

        def cloud_and_sync():
            cloud = CollectorCloud(
                collection_items=self._collection_items(),
                want_list_intents=self._active_want_list_intents(),
                workflow_completion_reports=self.workflow_completion_reports,
                mobile_entry_reports=self.mobile_entry_reports,
                settings=self.app_preferences,
            )
            return cloud, SyncBackupEngine(collector_cloud=cloud)

        def workspace_engine():
            cloud, sync = cloud_and_sync()
            return MultiDeviceWorkspaceEngine(
                collection_items=self._collection_items(),
                want_list_intents=self._active_want_list_intents(),
                workflow_completion_reports=self.workflow_completion_reports,
                mobile_entry_reports=self.mobile_entry_reports,
                settings=self.app_preferences,
                collector_cloud=cloud,
                sync_backup_engine=sync,
            )

        def engine():
            ws_engine = workspace_engine()
            return DeviceLinkingEngine(
                collection_items=self._collection_items(),
                want_list_intents=self._active_want_list_intents(),
                workflow_completion_reports=self.workflow_completion_reports,
                mobile_entry_reports=self.mobile_entry_reports,
                settings=self.app_preferences,
                workspace_engine=ws_engine,
                collector_cloud=ws_engine.collector_cloud,
                sync_backup_engine=ws_engine.sync_backup_engine,
            )

        def show_report(report, summary):
            current_report["report"] = report
            summary_var.set(summary)
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, report.format_markdown())

        def ensure_workspace():
            if self.multi_device_workspaces:
                return self.multi_device_workspaces[-1]
            ws_engine = workspace_engine()
            workspace = ws_engine.default_workspace("Device Linking Workspace")
            self.multi_device_workspaces.append(workspace)
            return workspace

        def ensure_conflict_ready_workspace(workspace):
            ws_engine = workspace_engine()
            if len(workspace.workspace_snapshots) < 2:
                if not workspace.workspace_snapshots:
                    self.workspace_snapshots.append(ws_engine.create_snapshot(workspace, "device-link-primary-gui"))
                workspace.register_device(ws_engine.create_device_profile(DEVICE_TABLET, "Collector Tablet"))
                self.workspace_snapshots.append(ws_engine.create_snapshot(workspace, "device-link-secondary-gui"))
            return workspace

        def create_link_report():
            try:
                workspace = ensure_workspace()
                report = engine().link_workspace(workspace)
                self.device_link_reports.append(report)
                show_report(report, f"Linked devices: {len(report.linked_devices)} | Relationships: {len(report.relationships)}")
            except Exception as exc:
                messagebox.showerror("Device Linking Error", f"Device link report failed: {str(exc)}")

        def create_conflict_report():
            try:
                workspace = ensure_conflict_ready_workspace(ensure_workspace())
                report = engine().analyze_workspace_conflicts(workspace)
                self.conflict_resolution_reports.append(report)
                show_report(report, f"Conflicts: {report.conflict_count} | Automatic resolution: NO")
            except Exception as exc:
                messagebox.showerror("Device Linking Error", f"Conflict report failed: {str(exc)}")

        def create_link_map():
            try:
                workspace = ensure_conflict_ready_workspace(ensure_workspace())
                linking = engine()
                link_report = self.device_link_reports[-1] if self.device_link_reports else linking.link_workspace(workspace)
                conflict_report = self.conflict_resolution_reports[-1] if self.conflict_resolution_reports else linking.analyze_workspace_conflicts(workspace)
                link_map = linking.create_link_map(workspace, link_report, conflict_report)
                self.workspace_link_maps.append(link_map)
                show_report(link_map, f"Workspace map: {len(link_map.linked_devices)} devices | {link_map.sync_readiness}")
            except Exception as exc:
                messagebox.showerror("Device Linking Error", f"Workspace link map failed: {str(exc)}")

        def create_readiness_report():
            try:
                workspace = ensure_conflict_ready_workspace(ensure_workspace())
                linking = engine()
                conflict_report = self.conflict_resolution_reports[-1] if self.conflict_resolution_reports else linking.analyze_workspace_conflicts(workspace)
                link_map = self.workspace_link_maps[-1] if self.workspace_link_maps else linking.create_link_map(workspace, conflict_report=conflict_report)
                report = linking.readiness_report(workspace, link_map, conflict_report)
                self.device_link_readiness_reports.append(report)
                show_report(report, f"Readiness: {report.readiness_score}/100 | Unresolved conflicts: {report.unresolved_conflicts}")
            except Exception as exc:
                messagebox.showerror("Device Linking Error", f"Readiness report failed: {str(exc)}")

        def create_full_review():
            create_link_report()
            create_conflict_report()
            create_link_map()
            create_readiness_report()

        def export_report(export_type):
            report = current_report.get("report")
            if not report:
                messagebox.showwarning("No Report", "Generate a Device Linking report before exporting.")
                return
            extension = ".md" if export_type == "markdown" else ".csv"
            filetypes = [("Markdown files", "*.md")] if export_type == "markdown" else [("CSV files", "*.csv")]
            file_path = filedialog.asksaveasfilename(
                title="Export Device Linking",
                defaultextension=extension,
                filetypes=filetypes,
            )
            if file_path:
                try:
                    if export_type == "markdown":
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(report.format_markdown())
                    else:
                        report.export_csv(file_path)
                    messagebox.showinfo("Export Success", f"Device Linking report exported to {file_path}")
                except Exception as exc:
                    messagebox.showerror("Export Error", f"Failed to export report: {str(exc)}")

        ttk.Button(button_frame, text="Link Devices", command=create_link_report).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Analyze Conflicts", command=create_conflict_report).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Create Link Map", command=create_link_map).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Readiness Report", command=create_readiness_report).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Full Review", command=create_full_review).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame_2, text="Export CSV", command=lambda: export_report("csv")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame_2, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_platform_management(self):
        """Open Platform Management dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Platform Management")
        dialog.geometry("1000x700")

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Create notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Services tab
        services_frame = ttk.Frame(notebook, padding="10")
        notebook.add(services_frame, text="Services")

        services_text = tk.Text(services_frame, wrap=tk.WORD)
        services_text.pack(fill=tk.BOTH, expand=True)

        # Plugins tab
        plugins_frame = ttk.Frame(notebook, padding="10")
        notebook.add(plugins_frame, text="Plugins")

        plugins_text = tk.Text(plugins_frame, wrap=tk.WORD)
        plugins_text.pack(fill=tk.BOTH, expand=True)

        # Event Bus tab
        events_frame = ttk.Frame(notebook, padding="10")
        notebook.add(events_frame, text="Event Bus")

        events_text = tk.Text(events_frame, wrap=tk.WORD)
        events_text.pack(fill=tk.BOTH, expand=True)

        # Commands tab
        commands_frame = ttk.Frame(notebook, padding="10")
        notebook.add(commands_frame, text="Commands")

        commands_text = tk.Text(commands_frame, wrap=tk.WORD)
        commands_text.pack(fill=tk.BOTH, expand=True)

        # Config tab
        config_frame = ttk.Frame(notebook, padding="10")
        notebook.add(config_frame, text="Configuration")

        config_text = tk.Text(config_frame, wrap=tk.WORD)
        config_text.pack(fill=tk.BOTH, expand=True)

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def refresh_all():
            # Refresh services
            services = self.platform.get_all_services()
            services_text.delete("1.0", tk.END)
            services_text.insert(tk.END, f"Registered Services ({len(services)}):\n\n")
            for service in services:
                services_text.insert(tk.END, f"Name: {service.name}\n")
                services_text.insert(tk.END, f"Version: {service.version}\n")
                services_text.insert(tk.END, f"Description: {service.description}\n")
                services_text.insert(tk.END, f"Status: {service.status}\n")
                services_text.insert(tk.END, f"Dependencies: {', '.join(service.dependencies)}\n")
                services_text.insert(tk.END, "-" * 50 + "\n\n")

            # Refresh plugins
            plugins = self.platform_integration.plugin_manager.get_all_plugins()
            plugins_text.delete("1.0", tk.END)
            plugins_text.insert(tk.END, f"Plugins ({len(plugins)}):\n\n")
            for plugin in plugins:
                plugins_text.insert(tk.END, f"Name: {plugin.manifest.name}\n")
                plugins_text.insert(tk.END, f"Version: {plugin.manifest.version}\n")
                plugins_text.insert(tk.END, f"Description: {plugin.manifest.description}\n")
                plugins_text.insert(tk.END, f"Author: {plugin.manifest.author}\n")
                plugins_text.insert(tk.END, f"Status: {plugin.status}\n")
                plugins_text.insert(tk.END, "-" * 50 + "\n\n")

            # Refresh event bus
            event_stats = self.platform_integration.event_bus.get_statistics()
            events_text.delete("1.0", tk.END)
            events_text.insert(tk.END, "Event Bus Statistics:\n\n")
            for key, value in event_stats.items():
                events_text.insert(tk.END, f"{key}: {value}\n")

            # Refresh commands
            commands = self.platform_integration.command_bus.get_all()
            command_stats = self.platform_integration.command_bus.get_statistics()
            commands_text.delete("1.0", tk.END)
            commands_text.insert(tk.END, f"Registered Commands ({len(commands)}):\n\n")
            for command in commands:
                commands_text.insert(tk.END, f"Name: {command.name}\n")
                commands_text.insert(tk.END, f"Description: {command.description}\n")
                commands_text.insert(tk.END, f"Can Rollback: {command.can_rollback}\n")
                commands_text.insert(tk.END, "-" * 50 + "\n\n")
            commands_text.insert(tk.END, "\nCommand Statistics:\n\n")
            for key, value in command_stats.items():
                commands_text.insert(tk.END, f"{key}: {value}\n")

            # Refresh config
            config = self.platform_integration.config_manager.get_all_settings()
            config_text.delete("1.0", tk.END)
            config_text.insert(tk.END, "Platform Configuration:\n\n")
            for key, value in config.items():
                config_text.insert(tk.END, f"{key}: {value}\n")

        ttk.Button(button_frame, text="Refresh", command=refresh_all).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

        # Initial refresh
        refresh_all()

    def open_platform_analytics(self):
        """Open Platform Analytics dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Platform Analytics")
        dialog.geometry("1200x800")

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Create notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Dashboard tab
        dashboard_frame = ttk.Frame(notebook, padding="10")
        notebook.add(dashboard_frame, text="Dashboard")

        dashboard_text = tk.Text(dashboard_frame, wrap=tk.WORD)
        dashboard_text.pack(fill=tk.BOTH, expand=True)

        # Health Score tab
        health_frame = ttk.Frame(notebook, padding="10")
        notebook.add(health_frame, text="Health Score")

        health_text = tk.Text(health_frame, wrap=tk.WORD)
        health_text.pack(fill=tk.BOTH, expand=True)

        # Module Metrics tab
        metrics_frame = ttk.Frame(notebook, padding="10")
        notebook.add(metrics_frame, text="Module Metrics")

        metrics_text = tk.Text(metrics_frame, wrap=tk.WORD)
        metrics_text.pack(fill=tk.BOTH, expand=True)

        # Trends tab
        trends_frame = ttk.Frame(notebook, padding="10")
        notebook.add(trends_frame, text="Trends")

        trends_text = tk.Text(trends_frame, wrap=tk.WORD)
        trends_text.pack(fill=tk.BOTH, expand=True)

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def generate_analytics():
            """Generate and display analytics."""
            engine = PlatformAnalyticsEngine()

            # Gather data from current state
            collection_data = {"items": self._collection_items()} if hasattr(self, '_collection_items') else None
            portfolio_data = {"total_estimated_value": 0, "total_acquisition_cost": 0, "silver_value": 0}
            workflow_data = {"photos_captured": 0, "ocr_sessions": 0, "total_ocr_attempts": 0, 
                          "successful_identifications": 0, "entry_attempts": 0, 
                          "completed_entries": 0, "workflow_sessions": 0, "completed_workflows": 0}
            deal_hunter_data = {"total_listings_processed": 0, "buy_recommendations": 0, 
                             "pass_recommendations": 0, "risk_flags": 0}
            opportunity_data = {"total_opportunities": 0, "high_priority_opportunities": 0}
            market_data = {"total_market_records": 0, "comparable_sales": 0}
            watchlist_data = {"total_watchlists": 0, "total_watchlist_items": 0, "alerts_generated": 0}
            cloud_data = {"snapshots_created": 0, "sync_plans_generated": 0}
            sync_data = {"backup_archives_created": 0, "last_backup_hours_ago": 0, 
                       "sync_simulations_run": 0, "backup_ready": True}
            workspace_data = {"registered_devices": 0, "workspace_snapshots": 0}
            device_data = {"linked_devices": 0, "unresolved_conflicts": 0}

            # Generate snapshot
            snapshot = engine.generate_snapshot(
                collection_data=collection_data,
                portfolio_data=portfolio_data,
                workflow_data=workflow_data,
                deal_hunter_data=deal_hunter_data,
                opportunity_data=opportunity_data,
                market_data=market_data,
                watchlist_data=watchlist_data,
                cloud_data=cloud_data,
                sync_data=sync_data,
                workspace_data=workspace_data,
                device_data=device_data
            )

            # Generate dashboard
            dashboard = engine.generate_dashboard(snapshot)

            # Display dashboard
            dashboard_text.delete("1.0", tk.END)
            dashboard_text.insert(tk.END, "# Platform Analytics Dashboard\n\n")
            dashboard_text.insert(tk.END, f"Generated: {dashboard.generated_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            dashboard_text.insert(tk.END, f"Overall Health Score: {dashboard.health_score.score:.1f}% ({dashboard.health_score.category.upper()})\n\n")
            dashboard_text.insert(tk.END, f"Active Modules: {dashboard.summary.active_modules}/{dashboard.summary.total_modules}\n")
            dashboard_text.insert(tk.END, f"Healthy Modules: {dashboard.summary.healthy_modules}\n\n")
            
            dashboard_text.insert(tk.END, "## Top Strengths\n\n")
            for strength in dashboard.summary.top_strengths:
                dashboard_text.insert(tk.END, f"- {strength}\n")
            
            dashboard_text.insert(tk.END, "\n## Top Improvements\n\n")
            for improvement in dashboard.summary.top_improvements:
                dashboard_text.insert(tk.END, f"- {improvement}\n")

            # Display health score
            health_text.delete("1.0", tk.END)
            health_md = engine.export_health_score_markdown(dashboard.health_score)
            health_text.insert(tk.END, health_md)

            # Display module metrics
            metrics_text.delete("1.0", tk.END)
            metrics_md = engine.export_snapshot_markdown(snapshot)
            metrics_text.insert(tk.END, metrics_md)

            # Display trends
            trends_text.delete("1.0", tk.END)
            trends_text.insert(tk.END, "# Analytics Trends\n\n")
            if dashboard.trends:
                for trend in dashboard.trends:
                    trends_text.insert(tk.END, f"## {trend.metric_name}\n")
                    trends_text.insert(tk.END, f"Direction: {trend.direction}\n")
                    trends_text.insert(tk.END, f"Change: {trend.change_percent:.1f}%\n")
                    trends_text.insert(tk.END, f"Description: {trend.description}\n\n")
            else:
                trends_text.insert(tk.END, "Insufficient data for trend analysis. Generate more snapshots to see trends.\n")

            # Store for export
            dialog.current_dashboard = dashboard
            dialog.current_snapshot = snapshot

        def export_dashboard_markdown():
            """Export dashboard as Markdown."""
            if not hasattr(dialog, 'current_dashboard'):
                messagebox.showwarning("Export", "No analytics data to export. Generate analytics first.")
                return

            file_path = filedialog.asksaveasfilename(
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
                title="Export Dashboard as Markdown"
            )
            
            if file_path:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write("# Platform Analytics Dashboard\n\n")
                        f.write(f"Generated: {dialog.current_dashboard.generated_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                        f.write(f"Overall Health Score: {dialog.current_dashboard.health_score.score:.1f}%\n\n")
                        f.write(engine.export_health_score_markdown(dialog.current_dashboard.health_score))
                        f.write("\n\n---\n\n")
                        f.write(engine.export_snapshot_markdown(dialog.current_snapshot))
                    messagebox.showinfo("Export", f"Dashboard exported to {file_path}")
                except Exception as e:
                    messagebox.showerror("Export Error", f"Failed to export: {str(e)}")

        def export_dashboard_csv():
            """Export dashboard as CSV."""
            if not hasattr(dialog, 'current_snapshot'):
                messagebox.showwarning("Export", "No analytics data to export. Generate analytics first.")
                return

            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Export Dashboard as CSV"
            )
            
            if file_path:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(engine.export_snapshot_csv(dialog.current_snapshot))
                    messagebox.showinfo("Export", f"Dashboard exported to {file_path}")
                except Exception as e:
                    messagebox.showerror("Export Error", f"Failed to export: {str(e)}")

        ttk.Button(button_frame, text="Generate Analytics", command=generate_analytics).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=export_dashboard_markdown).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=export_dashboard_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

        # Initialize analytics engine for export functions
        engine = PlatformAnalyticsEngine()

    def open_collection_insights(self):
        """Open Collection Insights dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Collection Insights")
        dialog.geometry("1200x800")

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Create notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Dashboard tab
        dashboard_frame = ttk.Frame(notebook, padding="10")
        notebook.add(dashboard_frame, text="Dashboard")

        dashboard_text = tk.Text(dashboard_frame, wrap=tk.WORD)
        dashboard_text.pack(fill=tk.BOTH, expand=True)

        # Health Report tab
        health_frame = ttk.Frame(notebook, padding="10")
        notebook.add(health_frame, text="Health Report")

        health_text = tk.Text(health_frame, wrap=tk.WORD)
        health_text.pack(fill=tk.BOTH, expand=True)

        # Collection Insights tab
        collection_frame = ttk.Frame(notebook, padding="10")
        notebook.add(collection_frame, text="Collection Insights")

        collection_text = tk.Text(collection_frame, wrap=tk.WORD)
        collection_text.pack(fill=tk.BOTH, expand=True)

        # Portfolio Insights tab
        portfolio_frame = ttk.Frame(notebook, padding="10")
        notebook.add(portfolio_frame, text="Portfolio Insights")

        portfolio_text = tk.Text(portfolio_frame, wrap=tk.WORD)
        portfolio_text.pack(fill=tk.BOTH, expand=True)

        # Acquisition Insights tab
        acquisition_frame = ttk.Frame(notebook, padding="10")
        notebook.add(acquisition_frame, text="Acquisition Insights")

        acquisition_text = tk.Text(acquisition_frame, wrap=tk.WORD)
        acquisition_text.pack(fill=tk.BOTH, expand=True)

        # Workflow Insights tab
        workflow_frame = ttk.Frame(notebook, padding="10")
        notebook.add(workflow_frame, text="Workflow Insights")

        workflow_text = tk.Text(workflow_frame, wrap=tk.WORD)
        workflow_text.pack(fill=tk.BOTH, expand=True)

        # Top Priorities tab
        priorities_frame = ttk.Frame(notebook, padding="10")
        notebook.add(priorities_frame, text="Top Priorities")

        priorities_text = tk.Text(priorities_frame, wrap=tk.WORD)
        priorities_text.pack(fill=tk.BOTH, expand=True)

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def generate_insights():
            """Generate and display insights."""
            engine = CollectionInsightsEngine()

            # Gather data from current state
            collection_data = {"items": self._collection_items()} if hasattr(self, '_collection_items') else {}
            portfolio_data = {"total_estimated_value": 0, "total_acquisition_cost": 0, "silver_value": 0}
            workflow_data = {"photos_captured": len(self.photo_records) if hasattr(self, 'photo_records') else 0,
                           "ocr_sessions": len(self.ocr_reports) if hasattr(self, 'ocr_reports') else 0,
                           "completed_workflows": 0, "workflow_sessions": 0}
            watchlist_data = {"watchlists": []}
            market_data = {}

            # Generate report
            report = engine.generate_insights(
                collection_data=collection_data,
                portfolio_data=portfolio_data,
                workflow_data=workflow_data,
                watchlist_data=watchlist_data,
                market_data=market_data
            )

            # Generate dashboard
            dashboard = engine.generate_dashboard(report)

            # Display dashboard
            dashboard_text.delete("1.0", tk.END)
            dashboard_text.insert(tk.END, "# Collection Insights Dashboard\n\n")
            dashboard_text.insert(tk.END, f"Generated: {dashboard.report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            dashboard_text.insert(tk.END, f"Summary: {dashboard.summary}\n\n")
            dashboard_text.insert(tk.END, f"Critical Insights: {dashboard.critical_count}\n")
            dashboard_text.insert(tk.END, f"High Priority: {dashboard.high_count}\n")
            dashboard_text.insert(tk.END, f"Medium Priority: {dashboard.medium_count}\n")
            dashboard_text.insert(tk.END, f"Low Priority: {dashboard.low_count}\n")
            dashboard_text.insert(tk.END, f"Informational: {dashboard.informational_count}\n\n")

            dashboard_text.insert(tk.END, "## Category Breakdown\n\n")
            for category, count in dashboard.category_breakdown.items():
                dashboard_text.insert(tk.END, f"- {category}: {count}\n")

            # Display health report
            health_text.delete("1.0", tk.END)
            health_md = engine.export_health_markdown(report.health_report)
            health_text.insert(tk.END, health_md)

            # Display collection insights
            collection_text.delete("1.0", tk.END)
            collection_text.insert(tk.END, "# Collection Insights\n\n")
            for insight in report.collection_insights:
                collection_text.insert(tk.END, f"## {insight.title}\n\n")
                collection_text.insert(tk.END, f"Priority: {insight.priority.value}\n")
                collection_text.insert(tk.END, f"Confidence: {insight.confidence:.1%}\n\n")
                collection_text.insert(tk.END, f"{insight.description}\n\n")
                collection_text.insert(tk.END, f"{insight.explanation}\n\n")

            # Display portfolio insights
            portfolio_text.delete("1.0", tk.END)
            portfolio_text.insert(tk.END, "# Portfolio Insights\n\n")
            for insight in report.portfolio_insights:
                portfolio_text.insert(tk.END, f"## {insight.title}\n\n")
                portfolio_text.insert(tk.END, f"Priority: {insight.priority.value}\n")
                portfolio_text.insert(tk.END, f"Confidence: {insight.confidence:.1%}\n\n")
                portfolio_text.insert(tk.END, f"{insight.description}\n\n")
                portfolio_text.insert(tk.END, f"{insight.explanation}\n\n")

            # Display acquisition insights
            acquisition_text.delete("1.0", tk.END)
            acquisition_text.insert(tk.END, "# Acquisition Insights\n\n")
            for insight in report.acquisition_insights:
                acquisition_text.insert(tk.END, f"## {insight.title}\n\n")
                acquisition_text.insert(tk.END, f"Priority: {insight.priority.value}\n")
                acquisition_text.insert(tk.END, f"Confidence: {insight.confidence:.1%}\n\n")
                acquisition_text.insert(tk.END, f"{insight.description}\n\n")
                acquisition_text.insert(tk.END, f"{insight.explanation}\n\n")

            # Display workflow insights
            workflow_text.delete("1.0", tk.END)
            workflow_text.insert(tk.END, "# Workflow Insights\n\n")
            for insight in report.workflow_insights:
                workflow_text.insert(tk.END, f"## {insight.title}\n\n")
                workflow_text.insert(tk.END, f"Priority: {insight.priority.value}\n")
                workflow_text.insert(tk.END, f"Confidence: {insight.confidence:.1%}\n\n")
                workflow_text.insert(tk.END, f"{insight.description}\n\n")
                workflow_text.insert(tk.END, f"{insight.explanation}\n\n")

            # Display top priorities
            priorities_text.delete("1.0", tk.END)
            priorities_text.insert(tk.END, "# Top Priorities\n\n")
            for insight in report.top_priorities:
                priorities_text.insert(tk.END, f"## {insight.title}\n\n")
                priorities_text.insert(tk.END, f"Priority: {insight.priority.value}\n")
                priorities_text.insert(tk.END, f"Category: {insight.category.value}\n")
                priorities_text.insert(tk.END, f"Confidence: {insight.confidence:.1%}\n\n")
                priorities_text.insert(tk.END, f"{insight.description}\n\n")
                priorities_text.insert(tk.END, f"{insight.explanation}\n\n")
                if insight.evidence:
                    priorities_text.insert(tk.END, "**Evidence:**\n")
                    for evidence in insight.evidence:
                        priorities_text.insert(tk.END, f"- {evidence.metric_name}: {evidence.metric_value} - {evidence.description}\n")
                    priorities_text.insert(tk.END, "\n")

            # Store for export
            dialog.current_report = report
            dialog.current_dashboard = dashboard

        def export_report_markdown():
            """Export report as Markdown."""
            if not hasattr(dialog, 'current_report'):
                messagebox.showwarning("Export", "No insights data to export. Generate insights first.")
                return

            file_path = filedialog.asksaveasfilename(
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
                title="Export Insights Report as Markdown"
            )

            if file_path:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(engine.export_report_markdown(dialog.current_report))
                    messagebox.showinfo("Export", f"Report exported to {file_path}")
                except Exception as e:
                    messagebox.showerror("Export Error", f"Failed to export: {str(e)}")

        def export_report_csv():
            """Export report as CSV."""
            if not hasattr(dialog, 'current_report'):
                messagebox.showwarning("Export", "No insights data to export. Generate insights first.")
                return

            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Export Insights Report as CSV"
            )

            if file_path:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(engine.export_report_csv(dialog.current_report))
                    messagebox.showinfo("Export", f"Report exported to {file_path}")
                except Exception as e:
                    messagebox.showerror("Export Error", f"Failed to export: {str(e)}")

        def export_health_markdown():
            """Export health report as Markdown."""
            if not hasattr(dialog, 'current_report'):
                messagebox.showwarning("Export", "No health data to export. Generate insights first.")
                return

            file_path = filedialog.asksaveasfilename(
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
                title="Export Health Report as Markdown"
            )

            if file_path:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(engine.export_health_markdown(dialog.current_report.health_report))
                    messagebox.showinfo("Export", f"Health report exported to {file_path}")
                except Exception as e:
                    messagebox.showerror("Export Error", f"Failed to export: {str(e)}")

        def export_health_csv():
            """Export health report as CSV."""
            if not hasattr(dialog, 'current_report'):
                messagebox.showwarning("Export", "No health data to export. Generate insights first.")
                return

            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Export Health Report as CSV"
            )

            if file_path:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(engine.export_health_csv(dialog.current_report.health_report))
                    messagebox.showinfo("Export", f"Health report exported to {file_path}")
                except Exception as e:
                    messagebox.showerror("Export Error", f"Failed to export: {str(e)}")

        ttk.Button(button_frame, text="Generate Insights", command=generate_insights).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Report (MD)", command=export_report_markdown).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Report (CSV)", command=export_report_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Health (MD)", command=export_health_markdown).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Health (CSV)", command=export_health_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

        # Initialize insights engine for export functions
        engine = CollectionInsightsEngine()


    def open_acquisition_strategy(self):
        """Open Acquisition Strategy dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Acquisition Strategy")
        dialog.geometry("1200x800")

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Create notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Dashboard tab
        dashboard_frame = ttk.Frame(notebook, padding="10")
        notebook.add(dashboard_frame, text="Dashboard")

        dashboard_text = tk.Text(dashboard_frame, wrap=tk.WORD)
        dashboard_text.pack(fill=tk.BOTH, expand=True)

        # Strategy Overview tab
        overview_frame = ttk.Frame(notebook, padding="10")
        notebook.add(overview_frame, text="Strategy Overview")

        overview_text = tk.Text(overview_frame, wrap=tk.WORD)
        overview_text.pack(fill=tk.BOTH, expand=True)

        # Immediate Priorities tab
        immediate_frame = ttk.Frame(notebook, padding="10")
        notebook.add(immediate_frame, text="Immediate Priorities")

        immediate_text = tk.Text(immediate_frame, wrap=tk.WORD)
        immediate_text.pack(fill=tk.BOTH, expand=True)

        # Short-Term Priorities tab
        short_term_frame = ttk.Frame(notebook, padding="10")
        notebook.add(short_term_frame, text="Short-Term Priorities")

        short_term_text = tk.Text(short_term_frame, wrap=tk.WORD)
        short_term_text.pack(fill=tk.BOTH, expand=True)

        # Long-Term Priorities tab
        long_term_frame = ttk.Frame(notebook, padding="10")
        notebook.add(long_term_frame, text="Long-Term Priorities")

        long_term_text = tk.Text(long_term_frame, wrap=tk.WORD)
        long_term_text.pack(fill=tk.BOTH, expand=True)

        # Portfolio Balance tab
        balance_frame = ttk.Frame(notebook, padding="10")
        notebook.add(balance_frame, text="Portfolio Balance")

        balance_text = tk.Text(balance_frame, wrap=tk.WORD)
        balance_text.pack(fill=tk.BOTH, expand=True)

        # Risk Assessment tab
        risk_frame = ttk.Frame(notebook, padding="10")
        notebook.add(risk_frame, text="Risk Assessment")

        risk_text = tk.Text(risk_frame, wrap=tk.WORD)
        risk_text.pack(fill=tk.BOTH, expand=True)

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def generate_strategy():
            """Generate and display acquisition strategy."""
            from acquisition_strategy import AcquisitionStrategyEngine
            engine = AcquisitionStrategyEngine()

            # Gather data from current state
            collection_data = {"items": self._collection_items()} if hasattr(self, '_collection_items') else {"items": []}
            series_data = {"series_definitions": []}
            opportunity_data = {"upgrade_opportunities": []}

            # Generate report
            report = engine.generate_strategy(
                collection_data=collection_data,
                series_data=series_data,
                opportunity_data=opportunity_data
            )

            # Generate dashboard
            dashboard = engine.generate_dashboard(report)

            # Display dashboard
            dashboard_text.delete("1.0", tk.END)
            dashboard_text.insert(tk.END, "# Acquisition Strategy Dashboard\n\n")
            dashboard_text.insert(tk.END, f"Generated: {dashboard.report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            dashboard_text.insert(tk.END, f"Summary: {dashboard.summary}\n\n")
            dashboard_text.insert(tk.END, f"Critical Priorities: {dashboard.critical_count}\n")
            dashboard_text.insert(tk.END, f"High Priority: {dashboard.high_count}\n")
            dashboard_text.insert(tk.END, f"Medium Priority: {dashboard.medium_count}\n")
            dashboard_text.insert(tk.END, f"Low Priority: {dashboard.low_count}\n\n")

            dashboard_text.insert(tk.END, "## Category Breakdown\n\n")
            for category, count in dashboard.category_breakdown.items():
                dashboard_text.insert(tk.END, f"- {category}: {count}\n")

            dashboard_text.insert(tk.END, f"\n## Total Estimated Budget\n\n")
            dashboard_text.insert(tk.END, f"${dashboard.total_estimated_budget:.0f}\n")

            # Display strategy overview
            overview_text.delete("1.0", tk.END)
            overview_text.insert(tk.END, "# Strategy Overview\n\n")
            overview_text.insert(tk.END, f"{report.strategy_overview}\n\n")
            overview_text.insert(tk.END, "## Collection Context\n\n")
            overview_text.insert(tk.END, f"{report.collection_context}\n\n")

            overview_text.insert(tk.END, "## Strategic Plan\n\n")
            for phase in report.strategic_plan:
                overview_text.insert(tk.END, f"### Phase {phase.phase_number}: {phase.phase_name}\n\n")
                overview_text.insert(tk.END, f"Timeframe: {phase.timeframe.value}\n")
                overview_text.insert(tk.END, f"Estimated Budget: ${phase.estimated_budget:.0f}\n\n")
                overview_text.insert(tk.END, "Expected Outcomes:\n")
                for outcome in phase.expected_outcomes:
                    overview_text.insert(tk.END, f"- {outcome}\n")
                overview_text.insert(tk.END, "\nTargets:\n")
                for target in phase.targets:
                    overview_text.insert(tk.END, f"- {target.target} ({target.priority_level.value}, {target.risk_level.value} risk)\n")
                    overview_text.insert(tk.END, f"  Reason: {target.strategic_reason}\n")
                    overview_text.insert(tk.END, f"  Budget: {target.budget_guidance}\n")
                overview_text.insert(tk.END, "\n")

            # Display immediate priorities
            immediate_text.delete("1.0", tk.END)
            immediate_text.insert(tk.END, "# Immediate Priorities\n\n")
            for p in report.immediate_priorities:
                immediate_text.insert(tk.END, f"## {p.target}\n\n")
                immediate_text.insert(tk.END, f"Category: {p.category.value}\n")
                immediate_text.insert(tk.END, f"Priority: {p.priority_level.value}\n")
                immediate_text.insert(tk.END, f"Risk: {p.risk_level.value}\n")
                immediate_text.insert(tk.END, f"Confidence: {p.confidence:.1%}\n\n")
                immediate_text.insert(tk.END, f"Reason: {p.strategic_reason}\n\n")
                immediate_text.insert(tk.END, f"Impact: {p.estimated_impact}\n\n")
                immediate_text.insert(tk.END, f"Budget: {p.budget_guidance}\n\n")
                if p.prerequisites:
                    immediate_text.insert(tk.END, "Prerequisites:\n")
                    for prereq in p.prerequisites:
                        immediate_text.insert(tk.END, f"- {prereq}\n")
                    immediate_text.insert(tk.END, "\n")

            # Display short-term priorities
            short_term_text.delete("1.0", tk.END)
            short_term_text.insert(tk.END, "# Short-Term Priorities\n\n")
            for p in report.short_term_priorities:
                short_term_text.insert(tk.END, f"## {p.target}\n\n")
                short_term_text.insert(tk.END, f"Category: {p.category.value}\n")
                short_term_text.insert(tk.END, f"Priority: {p.priority_level.value}\n")
                short_term_text.insert(tk.END, f"Risk: {p.risk_level.value}\n")
                short_term_text.insert(tk.END, f"Confidence: {p.confidence:.1%}\n\n")
                short_term_text.insert(tk.END, f"Reason: {p.strategic_reason}\n\n")
                short_term_text.insert(tk.END, f"Impact: {p.estimated_impact}\n\n")
                short_term_text.insert(tk.END, f"Budget: {p.budget_guidance}\n\n")

            # Display long-term priorities
            long_term_text.delete("1.0", tk.END)
            long_term_text.insert(tk.END, "# Long-Term Priorities\n\n")
            for p in report.long_term_priorities:
                long_term_text.insert(tk.END, f"## {p.target}\n\n")
                long_term_text.insert(tk.END, f"Category: {p.category.value}\n")
                long_term_text.insert(tk.END, f"Priority: {p.priority_level.value}\n")
                long_term_text.insert(tk.END, f"Risk: {p.risk_level.value}\n")
                long_term_text.insert(tk.END, f"Confidence: {p.confidence:.1%}\n\n")
                long_term_text.insert(tk.END, f"Reason: {p.strategic_reason}\n\n")
                long_term_text.insert(tk.END, f"Impact: {p.estimated_impact}\n\n")
                long_term_text.insert(tk.END, f"Budget: {p.budget_guidance}\n\n")

            # Display portfolio balance
            balance_text.delete("1.0", tk.END)
            balance_text.insert(tk.END, "# Portfolio Balance Recommendations\n\n")
            for balance in report.portfolio_balance:
                balance_text.insert(tk.END, f"## {balance.category}\n\n")
                balance_text.insert(tk.END, f"Current: {balance.current_percentage:.1f}%\n")
                balance_text.insert(tk.END, f"Recommended: {balance.recommended_percentage:.1f}%\n")
                balance_text.insert(tk.END, f"Priority: {balance.priority.value}\n\n")
                balance_text.insert(tk.END, f"Reasoning: {balance.reasoning}\n\n")

            # Display risk assessment
            risk_text.delete("1.0", tk.END)
            risk_text.insert(tk.END, "# Risk Assessment\n\n")
            risk_text.insert(tk.END, f"Overall Risk: {report.risk_assessment.overall_risk.value}\n\n")

            if report.risk_assessment.risk_factors:
                risk_text.insert(tk.END, "## Risk Factors\n\n")
                for factor in report.risk_assessment.risk_factors:
                    risk_text.insert(tk.END, f"- {factor}\n")
                risk_text.insert(tk.END, "\n")

            if report.risk_assessment.mitigation_strategies:
                risk_text.insert(tk.END, "## Mitigation Strategies\n\n")
                for strategy in report.risk_assessment.mitigation_strategies:
                    risk_text.insert(tk.END, f"- {strategy}\n")
                risk_text.insert(tk.END, "\n")

            if report.risk_assessment.market_risk_notes:
                risk_text.insert(tk.END, "## Market Risk Notes\n\n")
                for note in report.risk_assessment.market_risk_notes:
                    risk_text.insert(tk.END, f"- {note}\n")
                risk_text.insert(tk.END, "\n")

            risk_text.insert(tk.END, "## Recommended Actions\n\n")
            for i, action in enumerate(report.recommended_actions, 1):
                risk_text.insert(tk.END, f"{i}. {action}\n")

            # Store for export
            dialog.current_report = report
            dialog.current_engine = engine

        def export_strategy_markdown():
            """Export strategy report as Markdown."""
            if not hasattr(dialog, 'current_report'):
                messagebox.showwarning("Export", "No strategy data to export. Generate strategy first.")
                return

            file_path = filedialog.asksaveasfilename(
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
                title="Export Strategy Report as Markdown"
            )

            if file_path:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(dialog.current_engine.export_strategy_markdown(dialog.current_report))
                    messagebox.showinfo("Export", f"Strategy report exported to {file_path}")
                except Exception as e:
                    messagebox.showerror("Export Error", f"Failed to export: {str(e)}")

        def export_strategy_csv():
            """Export strategy report as CSV."""
            if not hasattr(dialog, 'current_report'):
                messagebox.showwarning("Export", "No strategy data to export. Generate strategy first.")
                return

            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Export Strategy Report as CSV"
            )

            if file_path:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(dialog.current_engine.export_strategy_csv(dialog.current_report))
                    messagebox.showinfo("Export", f"Strategy report exported to {file_path}")
                except Exception as e:
                    messagebox.showerror("Export Error", f"Failed to export: {str(e)}")

        ttk.Button(button_frame, text="Generate Strategy", command=generate_strategy).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Strategy (MD)", command=export_strategy_markdown).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Strategy (CSV)", command=export_strategy_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

        # Initialize acquisition strategy engine for export functions
        from acquisition_strategy import AcquisitionStrategyEngine
        engine = AcquisitionStrategyEngine()

    @staticmethod
    def ask_my_collection_response_text(response):
        """Format a grounded response without recalculating backend facts."""
        status = str(getattr(response, "status", "error") or "error").replace("_", " ").title()
        answer = str(getattr(response, "answer_text", "") or "No answer was returned.")
        if getattr(response, "truncated", False):
            answer += "\n\nSome evidence was truncated at the configured result limit."
        return f"{status}\n\n{answer}"

    @staticmethod
    def ask_my_collection_evidence_text(response):
        """Format the read-only evidence and diagnostic metadata shown on demand."""
        provider = str(getattr(response, "provider_name", "") or "Not available")
        model = str(getattr(response, "model_name", "") or "Not available")
        calls = getattr(response, "tool_calls_used", ()) or ()
        call_text = ", ".join(str(getattr(call, "name", "")) for call in calls) or "None"
        evidence = response.evidence_text() if hasattr(response, "evidence_text") else "No evidence details."
        return "\n".join([
            f"Provider: {provider}",
            f"Model: {model}",
            f"Tools used: {call_text}",
            "",
            evidence,
        ])

    @staticmethod
    def run_ask_my_collection_request(assistant, question, result_queue, request_id):
        """Run one standalone request without touching Tk from the worker thread."""
        from inference_telemetry import telemetry_scan

        try:
            with telemetry_scan(f"ask-my-collection:{request_id}"):
                response = assistant.ask(question)
        except Exception as error:
            from grounded_collection_assistant import GroundedAssistantResponse

            response = GroundedAssistantResponse(
                answer_text=(
                    "The configured provider could not complete the request. "
                    "No collection data was changed."
                ),
                status="error",
                limitations=(f"Provider error type: {error.__class__.__name__}",),
                provider_name=str(getattr(assistant.adapter, "provider_name", "") or ""),
                model_name=str(getattr(assistant.adapter, "model_name", "") or ""),
            )
        result_queue.put((request_id, question, response))

    def create_ask_my_collection_service(self):
        """Build the optional read-only assistant from current in-memory collection state."""
        from grounded_collection_assistant import (
            GroundedCollectionAssistant,
            ReadOnlyAssistantToolRegistry,
        )
        from openai_collection_assistant import OpenAIResponsesAdapter

        adapter = OpenAIResponsesAdapter.from_environment()
        workspace = CollectorWorkspace(
            self._collection_items(),
            want_list_intents=self._active_want_list_intents(),
            photo_records=self.photo_records,
            shopping_candidates=self.shopping_candidates,
            market_awareness_engine=self.market_awareness_engine,
        )
        registry = ReadOnlyAssistantToolRegistry(
            workspace,
            want_list_intents=self._active_want_list_intents(),
            portfolio_engine_options={
                "market_awareness_engine": self.market_awareness_engine,
                "snapshot_manager": self.snapshot_manager,
                "shopping_candidates": self.shopping_candidates,
                "photo_records": self.photo_records,
            },
        )
        return GroundedCollectionAssistant(adapter, registry)

    def open_ask_my_collection(self):
        """Open the session-only, read-only Ask My Collection dialog."""
        from openai_collection_assistant import OpenAIResponsesAdapter

        dialog = tk.Toplevel(self.root)
        dialog.title("Ask My Collection")
        dialog.geometry("900x720")

        main_frame = ttk.Frame(dialog, padding="12")
        main_frame.pack(fill=tk.BOTH, expand=True)

        configured, provider_message = OpenAIResponsesAdapter.configuration_status()
        provider_var = tk.StringVar(value=f"Provider status: {provider_message}")
        ttk.Label(main_frame, textvariable=provider_var).pack(anchor=tk.W)
        ttk.Label(
            main_frame,
            text=(
                "Cloud privacy: each standalone question sends only the question and bounded, "
                "allowlisted tool evidence. Images, paths, notes, credentials, and complete records "
                "are never sent. Ask My Collection is read-only and does not save chat history."
            ),
            wraplength=850,
        ).pack(anchor=tk.W, pady=(4, 10))

        question_frame = ttk.LabelFrame(main_frame, text="Collection question", padding="8")
        question_frame.pack(fill=tk.X, pady=(0, 8))
        question_text = tk.Text(question_frame, height=3, wrap=tk.WORD)
        question_text.pack(fill=tk.X)

        status_var = tk.StringVar(value="Ready." if configured else provider_message)
        ttk.Label(main_frame, textvariable=status_var).pack(anchor=tk.W, pady=(0, 6))

        session_frame = ttk.LabelFrame(main_frame, text="Session (not saved)", padding="8")
        session_frame.pack(fill=tk.BOTH, expand=True)
        session_text = tk.Text(session_frame, wrap=tk.WORD, state=tk.DISABLED)
        session_text.pack(fill=tk.BOTH, expand=True)

        evidence_visible = tk.BooleanVar(value=False)
        evidence_frame = ttk.LabelFrame(main_frame, text="Evidence and tools used", padding="8")
        evidence_text = tk.Text(evidence_frame, height=9, wrap=tk.WORD, state=tk.DISABLED)
        evidence_text.pack(fill=tk.BOTH, expand=True)

        controls = ttk.Frame(main_frame)
        controls.pack(fill=tk.X, pady=(8, 0))

        result_queue = queue.Queue()
        request_state = {"running": False, "request_id": 0}

        def set_text(widget, value, *, append=False):
            widget.config(state=tk.NORMAL)
            if not append:
                widget.delete("1.0", tk.END)
            widget.insert(tk.END, value)
            widget.see(tk.END)
            widget.config(state=tk.DISABLED)

        def toggle_evidence():
            visible = not evidence_visible.get()
            evidence_visible.set(visible)
            if visible:
                evidence_frame.pack(fill=tk.BOTH, pady=(8, 0), before=controls)
                evidence_button.config(text="Hide Evidence")
            else:
                evidence_frame.pack_forget()
                evidence_button.config(text="Show Evidence")

        def submit():
            if request_state["running"]:
                return
            question = question_text.get("1.0", tk.END).strip()
            if not question:
                status_var.set("Enter a standalone collection question.")
                return
            if not configured:
                status_var.set(provider_message)
                return
            try:
                request_assistant = self.create_ask_my_collection_service()
            except Exception as error:
                status_var.set(
                    "Provider setup could not be completed "
                    f"({error.__class__.__name__}). Review requirements-ai.txt and environment variables."
                )
                return
            request_state["running"] = True
            request_state["request_id"] += 1
            request_id = request_state["request_id"]
            status_var.set("Working…")
            submit_button.config(state=tk.DISABLED)
            cancel_button.config(state=tk.NORMAL)
            set_text(session_text, f"You\n{question}\n\n", append=True)
            question_text.delete("1.0", tk.END)
            worker = threading.Thread(
                target=self.run_ask_my_collection_request,
                args=(request_assistant, question, result_queue, request_id),
                daemon=True,
            )
            worker.start()

        def cancel():
            if not request_state["running"]:
                return
            request_state["request_id"] += 1
            request_state["running"] = False
            status_var.set("Cancelled. Any in-flight provider result will be ignored.")
            submit_button.config(state=tk.NORMAL if configured else tk.DISABLED)
            cancel_button.config(state=tk.DISABLED)

        def clear_session():
            set_text(session_text, "")
            set_text(evidence_text, "No evidence details yet.")
            status_var.set("Session display cleared. No history was persisted.")

        def poll_results():
            try:
                while True:
                    request_id, _question, response = result_queue.get_nowait()
                    if request_id != request_state["request_id"]:
                        continue
                    request_state["running"] = False
                    set_text(
                        session_text,
                        "Ask My Collection\n" + self.ask_my_collection_response_text(response) + "\n\n",
                        append=True,
                    )
                    set_text(evidence_text, self.ask_my_collection_evidence_text(response))
                    status_var.set(f"Completed: {str(response.status).replace('_', ' ')}")
                    submit_button.config(state=tk.NORMAL if configured else tk.DISABLED)
                    cancel_button.config(state=tk.DISABLED)
            except queue.Empty:
                pass
            if dialog.winfo_exists():
                dialog.after(50, poll_results)

        submit_button = ttk.Button(controls, text="Submit", command=submit)
        submit_button.pack(side=tk.LEFT, padx=(0, 6))
        submit_button.config(state=tk.NORMAL if configured else tk.DISABLED)
        cancel_button = ttk.Button(controls, text="Cancel", command=cancel, state=tk.DISABLED)
        cancel_button.pack(side=tk.LEFT, padx=(0, 6))
        evidence_button = ttk.Button(controls, text="Show Evidence", command=toggle_evidence)
        evidence_button.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="Clear Session", command=clear_session).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

        set_text(evidence_text, "No evidence details yet.")
        dialog.after(50, poll_results)
        question_text.focus_set()

    def open_collection_assistant(self):
        """Open Collection Assistant dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Collection Assistant")
        dialog.geometry("1200x800")

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Create notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Review Queue tab
        queue_frame = ttk.Frame(notebook, padding="10")
        notebook.add(queue_frame, text="Review Queue")

        queue_text = tk.Text(queue_frame, wrap=tk.WORD)
        queue_text.pack(fill=tk.BOTH, expand=True)

        # Current Candidate tab
        candidate_frame = ttk.Frame(notebook, padding="10")
        notebook.add(candidate_frame, text="Current Candidate")

        candidate_text = tk.Text(candidate_frame, wrap=tk.WORD)
        candidate_text.pack(fill=tk.BOTH, expand=True)

        # Productivity Metrics tab
        metrics_frame = ttk.Frame(notebook, padding="10")
        notebook.add(metrics_frame, text="Productivity Metrics")

        metrics_text = tk.Text(metrics_frame, wrap=tk.WORD)
        metrics_text.pack(fill=tk.BOTH, expand=True)

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        from collection_assistant import CollectionAssistantEngine, ReviewStatus

        # Initialize engine
        assistant_engine = CollectionAssistantEngine()
        session = assistant_engine.start_session("gui_session")
        dialog.current_engine = assistant_engine
        dialog.current_session = session

        def import_photos():
            """Import photos into the collection assistant session."""
            file_paths = filedialog.askopenfilenames(
                title="Select Photos",
                filetypes=[("Image files", "*.jpg *.jpeg *.png *.gif *.bmp"), ("All files", "*.*")]
            )
            if file_paths:
                assistant_engine.add_photos_to_session("gui_session", list(file_paths), auto_pair=True)
                refresh_display()
                messagebox.showinfo("Import", f"Imported {len(file_paths)} photo(s)")

        def process_ocr():
            """Process OCR for all pending candidates."""
            for candidate in session.queue.candidates:
                if candidate.is_pending and not candidate.ocr_result:
                    # Read image and simulate OCR (in real use, would call OCR engine)
                    assistant_engine.process_ocr_for_candidate("gui_session", candidate.id)
            refresh_display()
            messagebox.showinfo("OCR", "OCR processing complete")

        def approve_candidate():
            """Approve the current candidate."""
            candidate = assistant_engine.get_next_candidate_for_review("gui_session")
            if candidate:
                assistant_engine.review_candidate(
                    "gui_session", candidate.id, ReviewStatus.APPROVED, "Approved by collector"
                )
                refresh_display()
            else:
                messagebox.showinfo("Review", "No pending candidates")

        def reject_candidate():
            """Reject the current candidate."""
            candidate = assistant_engine.get_next_candidate_for_review("gui_session")
            if candidate:
                assistant_engine.review_candidate(
                    "gui_session", candidate.id, ReviewStatus.REJECTED, "Rejected by collector"
                )
                refresh_display()
            else:
                messagebox.showinfo("Review", "No pending candidates")

        def needs_review_candidate():
            """Flag candidate as needs review."""
            candidate = assistant_engine.get_next_candidate_for_review("gui_session")
            if candidate:
                assistant_engine.review_candidate(
                    "gui_session", candidate.id, ReviewStatus.NEEDS_REVIEW, "Needs further review"
                )
                refresh_display()
            else:
                messagebox.showinfo("Review", "No pending candidates")

        def refresh_display():
            """Refresh all display tabs."""
            # Update review queue
            queue_text.delete("1.0", tk.END)
            queue_text.insert(tk.END, "# Collection Assistant Review Queue\n\n")
            queue_text.insert(tk.END, f"Total Candidates: {session.queue.total_count}\n")
            queue_text.insert(tk.END, f"Reviewed: {session.queue.reviewed_count}\n")
            queue_text.insert(tk.END, f"Pending: {session.queue.pending_count}\n")
            queue_text.insert(tk.END, f"Approved: {session.queue.approved_count}\n")
            queue_text.insert(tk.END, f"Rejected: {session.queue.rejected_count}\n")
            queue_text.insert(tk.END, f"Completion: {session.queue.completion_percentage:.1f}%\n\n")

            if session.queue.has_incomplete_reviews:
                queue_text.insert(tk.END, "⚠️ Incomplete reviews detected\n\n")

            queue_text.insert(tk.END, "## Pending Candidates\n\n")
            for candidate in session.queue.candidates:
                if candidate.is_pending:
                    queue_text.insert(tk.END, f"- {candidate.display_label}\n")
                    queue_text.insert(tk.END, f"  Confidence: {candidate.confidence:.1%}\n")
                    queue_text.insert(tk.END, f"  Photos: {len(candidate.photos)}\n")
                    if candidate.fills_collection_gap:
                        queue_text.insert(tk.END, f"  ⚡ Fills collection gap\n")
                    if candidate.is_duplicate_risk:
                        queue_text.insert(tk.END, f"  ⚠️ Duplicate risk: {candidate.collection_match.duplicate_risk}\n")
                    queue_text.insert(tk.END, "\n")

            # Update current candidate
            candidate_text.delete("1.0", tk.END)
            next_candidate = assistant_engine.get_next_candidate_for_review("gui_session")
            if next_candidate:
                comparison = assistant_engine.build_side_by_side_comparison(
                    "gui_session", next_candidate.id
                )
                candidate_text.insert(tk.END, f"# {next_candidate.display_label}\n\n")
                candidate_text.insert(tk.END, f"**ID:** {next_candidate.id}\n")
                candidate_text.insert(tk.END, f"**Confidence:** {next_candidate.confidence:.1%}\n")
                candidate_text.insert(tk.END, f"**Source:** {next_candidate.source.value}\n")
                candidate_text.insert(tk.END, f"**Photos:** {len(next_candidate.photos)}\n\n")

                if next_candidate.suggested_identification:
                    candidate_text.insert(tk.END, "## Suggested Identification\n\n")
                    for key, value in next_candidate.suggested_identification.items():
                        candidate_text.insert(tk.END, f"- {key}: {value}\n")
                    candidate_text.insert(tk.END, "\n")

                if comparison.evidence:
                    candidate_text.insert(tk.END, "## Evidence\n\n")
                    for item in comparison.evidence:
                        candidate_text.insert(tk.END, f"- {item}\n")
                    candidate_text.insert(tk.END, "\n")

                if comparison.recommendations:
                    candidate_text.insert(tk.END, "## Recommendations\n\n")
                    for item in comparison.recommendations:
                        candidate_text.insert(tk.END, f"- {item}\n")
                    candidate_text.insert(tk.END, "\n")

                if comparison.warnings:
                    candidate_text.insert(tk.END, "## Warnings\n\n")
                    for item in comparison.warnings:
                        candidate_text.insert(tk.END, f"⚠️ {item}\n")
                    candidate_text.insert(tk.END, "\n")

                if next_candidate.collection_match.matched:
                    candidate_text.insert(tk.END, "## Collection Match\n\n")
                    candidate_text.insert(tk.END, f"Match Type: {next_candidate.collection_match.match_type}\n")
                    candidate_text.insert(tk.END, f"Duplicate Risk: {next_candidate.collection_match.duplicate_risk}\n")
                    if next_candidate.collection_match.notes:
                        for note in next_candidate.collection_match.notes:
                            candidate_text.insert(tk.END, f"- {note}\n")
                    candidate_text.insert(tk.END, "\n")

                if next_candidate.gap_info.fills_gap:
                    candidate_text.insert(tk.END, "## Gap Analysis\n\n")
                    candidate_text.insert(tk.END, f"Fills Gap: {next_candidate.gap_info.gap_type}\n")
                    candidate_text.insert(tk.END, f"Impact Score: {next_candidate.gap_info.impact_score:.1f}\n\n")

                if next_candidate.acquisition_priority.has_priority:
                    candidate_text.insert(tk.END, "## Acquisition Priority\n\n")
                    candidate_text.insert(tk.END, f"Category: {next_candidate.acquisition_priority.priority_category}\n")
                    candidate_text.insert(tk.END, f"Score: {next_candidate.acquisition_priority.priority_score:.1f}\n")
                    candidate_text.insert(tk.END, f"Reason: {next_candidate.acquisition_priority.strategic_reason}\n\n")
            else:
                candidate_text.insert(tk.END, "# No pending candidates\n\n")
                if session.queue.is_complete:
                    candidate_text.insert(tk.END, "✅ All candidates reviewed!\n")
                else:
                    candidate_text.insert(tk.END, "No pending candidates found.\n")

            # Update productivity metrics
            metrics_text.delete("1.0", tk.END)
            metrics_text.insert(tk.END, "# Productivity Metrics\n\n")
            metrics_text.insert(tk.END, f"Photos Processed: {session.metrics.photos_processed}\n")
            metrics_text.insert(tk.END, f"OCR Attempts: {session.metrics.ocr_attempts}\n")
            metrics_text.insert(tk.END, f"OCR Successes: {session.metrics.ocr_successes}\n")
            metrics_text.insert(tk.END, f"OCR Success Rate: {session.metrics.ocr_success_rate:.1f}%\n\n")
            metrics_text.insert(tk.END, f"Candidates Generated: {session.metrics.candidates_generated}\n")
            metrics_text.insert(tk.END, f"Reviews Completed: {session.metrics.reviews_completed}\n")
            metrics_text.insert(tk.END, f"Approval Rate: {session.metrics.approval_rate:.1f}%\n")
            metrics_text.insert(tk.END, f"Average Confidence: {session.metrics.average_confidence:.1%}\n\n")
            metrics_text.insert(tk.END, f"Estimated Time Saved: {session.metrics.estimated_time_saved_minutes:.1f} minutes\n")
            metrics_text.insert(tk.END, f"Session Duration: {session.duration.total_seconds() / 60:.1f} minutes\n")

        def export_session_markdown():
            """Export session as Markdown."""
            file_path = filedialog.asksaveasfilename(
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
                title="Export Assistant Session as Markdown"
            )
            if file_path:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(assistant_engine.export_session_markdown("gui_session"))
                    messagebox.showinfo("Export", f"Session exported to {file_path}")
                except Exception as e:
                    messagebox.showerror("Export Error", f"Failed to export: {str(e)}")

        def export_session_csv():
            """Export session as CSV."""
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Export Assistant Session as CSV"
            )
            if file_path:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(assistant_engine.export_session_csv("gui_session"))
                    messagebox.showinfo("Export", f"Session exported to {file_path}")
                except Exception as e:
                    messagebox.showerror("Export Error", f"Failed to export: {str(e)}")

        def export_productivity_report():
            """Export productivity report."""
            file_path = filedialog.asksaveasfilename(
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
                title="Export Productivity Report"
            )
            if file_path:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(assistant_engine.export_productivity_report_markdown("gui_session"))
                    messagebox.showinfo("Export", f"Productivity report exported to {file_path}")
                except Exception as e:
                    messagebox.showerror("Export Error", f"Failed to export: {str(e)}")

        ttk.Button(button_frame, text="Import Photos", command=import_photos).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Process OCR", command=process_ocr).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Approve", command=approve_candidate).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Reject", command=reject_candidate).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Needs Review", command=needs_review_candidate).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Session (MD)", command=export_session_markdown).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Session (CSV)", command=export_session_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Productivity", command=export_productivity_report).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

        # Initial display refresh
        refresh_display()

    def _workflow_engine(self):
        """Create a workflow orchestrator from current runtime state."""
        return CollectorWorkflowEngine(
            collection_items=self._collection_items(),
            want_list_intents=self._active_want_list_intents(),
            photo_records=self.photo_records,
            photo_candidates=self.photo_candidates,
            shopping_candidates=self.shopping_candidates,
            ocr_reports=self.ocr_reports,
            market_awareness_engine=self.market_awareness_engine,
            snapshot_manager=self.snapshot_manager,
        )

    def _home_dashboard(self):
        """Create the unified home dashboard from current runtime state."""
        return CollectorHomeDashboard(
            collection_items=self._collection_items(),
            want_list_intents=self._active_want_list_intents(),
            photo_records=self.photo_records,
            photo_candidates=self.photo_candidates,
            shopping_candidates=self.shopping_candidates,
            ocr_reports=self.ocr_reports,
            market_awareness_engine=self.market_awareness_engine,
            snapshot_manager=self.snapshot_manager,
            backup_manager=self.backup_manager,
            workflow_statuses=self.workflow_statuses,
            acknowledged_action_ids=self.acknowledged_home_actions,
        )

    def _remember_workflow_report(self, report):
        """Persist lightweight workflow state in runtime state for later save."""
        summary = getattr(report, "summary", None)
        if not summary:
            return
        self.workflow_summaries.append(summary.to_dict())
        self.workflow_statuses.extend(status.to_dict() for status in summary.statuses)

    def _show_workflow_report(self, title, report):
        """Show a workflow report with export buttons."""
        self._remember_workflow_report(report)
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("900x760")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        text = tk.Text(main_frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, report.format_markdown())
        text.config(state=tk.DISABLED)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def export_report(export_type):
            extension = ".md" if export_type == "markdown" else ".csv"
            filetypes = [("Markdown files", "*.md")] if export_type == "markdown" else [("CSV files", "*.csv")]
            file_path = filedialog.asksaveasfilename(
                title=f"Export {title}",
                defaultextension=extension,
                filetypes=filetypes + [("All files", "*.*")],
            )
            if not file_path:
                return
            ok = report.export_markdown(file_path) if export_type == "markdown" else report.export_csv(file_path)
            if ok:
                messagebox.showinfo("Export Complete", f"{title} exported to {file_path}")
            else:
                messagebox.showerror("Export Failed", f"Could not export {title}.")

        ttk.Button(button_frame, text="Export Markdown", command=lambda: export_report("markdown")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=lambda: export_report("csv")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_collector_home_dashboard(self):
        """Open unified Collector Home Dashboard."""
        try:
            report = self._home_dashboard().generate_report()
            self.home_reports.append(report.to_dict())
        except Exception as e:
            messagebox.showerror("Collector Home Dashboard Error", f"Dashboard failed: {str(e)}")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Collector Home Dashboard")
        dialog.geometry("920x760")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        text = tk.Text(main_frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, report.format_markdown())
        text.config(state=tk.DISABLED)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def export_report(export_type):
            extension = ".md" if export_type == "markdown" else ".csv"
            filetypes = [("Markdown files", "*.md")] if export_type == "markdown" else [("CSV files", "*.csv")]
            file_path = filedialog.asksaveasfilename(
                title="Export Collector Home Dashboard",
                defaultextension=extension,
                filetypes=filetypes + [("All files", "*.*")],
            )
            if not file_path:
                return
            ok = report.export_markdown(file_path) if export_type == "markdown" else report.export_csv(file_path)
            if ok:
                messagebox.showinfo("Export Complete", f"Collector Home Dashboard exported to {file_path}")
            else:
                messagebox.showerror("Export Failed", "Could not export Collector Home Dashboard.")

        ttk.Button(button_frame, text="Export Markdown", command=lambda: export_report("markdown")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=lambda: export_report("csv")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_collector_companion_readiness(self):
        """Open v3.0 readiness and consistency audit report."""
        try:
            auditor = CollectorCompanionReadinessAuditor(
                collection_items=self._collection_items(),
                want_list_intents=self._active_want_list_intents(),
                photo_records=self.photo_records,
                photo_candidates=self.photo_candidates,
                shopping_candidates=self.shopping_candidates,
                ocr_reports=self.ocr_reports,
                market_awareness_engine=self.market_awareness_engine,
                snapshot_manager=self.snapshot_manager,
                backup_manager=self.backup_manager,
            )
            report = auditor.generate_report()
            self.readiness_reports.append(report.to_dict())
            self.audit_summaries.append({
                "report": "Collector Companion Readiness",
                "status": report.status,
                "generated_at": report.generated_at,
                "finding_count": len(report.findings),
            })
        except Exception as e:
            messagebox.showerror("Collector Companion Readiness Error", f"Readiness audit failed: {str(e)}")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Collector Companion Readiness")
        dialog.geometry("920x760")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        text = tk.Text(main_frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, report.format_markdown())
        text.config(state=tk.DISABLED)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def export_report(export_type):
            extension = ".md" if export_type == "markdown" else ".csv"
            filetypes = [("Markdown files", "*.md")] if export_type == "markdown" else [("CSV files", "*.csv")]
            file_path = filedialog.asksaveasfilename(
                title="Export Collector Companion Readiness",
                defaultextension=extension,
                filetypes=filetypes + [("All files", "*.*")],
            )
            if not file_path:
                return
            ok = report.export_markdown(file_path) if export_type == "markdown" else report.export_csv(file_path)
            if ok:
                messagebox.showinfo("Export Complete", f"Collector Companion Readiness exported to {file_path}")
            else:
                messagebox.showerror("Export Failed", "Could not export Collector Companion Readiness.")

        ttk.Button(button_frame, text="Export Markdown", command=lambda: export_report("markdown")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=lambda: export_report("csv")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_acquisition_workflow(self):
        """Open guided Photo -> OCR -> Validation -> Recommendation workflow."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Acquisition Workflow")
        dialog.geometry("820x700")

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        form_frame = ttk.LabelFrame(main_frame, text="Candidate", padding="10")
        form_frame.pack(fill=tk.X, pady=(0, 10))
        form_frame.columnconfigure(1, weight=1)

        title_var = tk.StringVar()
        front_var = tk.StringVar()
        reverse_var = tk.StringVar()
        price_var = tk.StringVar()
        source_var = tk.StringVar(value="Acquisition Workflow")

        def browse_photo(target_var):
            path = filedialog.askopenfilename(
                title="Select Photo Reference",
                filetypes=[("Image files", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"), ("All files", "*.*")],
            )
            if path:
                target_var.set(path)

        fields = [
            ("Title:", title_var, None),
            ("Front Photo:", front_var, browse_photo),
            ("Reverse Photo:", reverse_var, browse_photo),
            ("Asking Price:", price_var, None),
            ("Source:", source_var, None),
        ]
        for row, (label, variable, browse) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=4)
            ttk.Entry(form_frame, textvariable=variable).grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)
            if browse:
                ttk.Button(form_frame, text="Browse", command=lambda var=variable: browse_photo(var)).grid(row=row, column=2, padx=(6, 0), pady=4)

        ttk.Label(form_frame, text="Notes:").grid(row=len(fields), column=0, sticky=(tk.W, tk.N), pady=4)
        notes_text = tk.Text(form_frame, height=3, wrap=tk.WORD)
        notes_text.grid(row=len(fields), column=1, columnspan=2, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)

        ttk.Label(form_frame, text="Raw OCR Text:").grid(row=len(fields) + 1, column=0, sticky=(tk.W, tk.N), pady=4)
        ocr_text = tk.Text(form_frame, height=4, wrap=tk.WORD)
        ocr_text.grid(row=len(fields) + 1, column=1, columnspan=2, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def parse_money(value):
            cleaned = str(value or "").strip().replace("$", "").replace(",", "")
            return float(cleaned) if cleaned else 0.0

        def run_workflow():
            try:
                candidate = PhotoCandidate(
                    title=title_var.get(),
                    front_photo=front_var.get(),
                    reverse_photo=reverse_var.get(),
                    notes=notes_text.get("1.0", tk.END).strip(),
                    asking_price=parse_money(price_var.get()),
                    source=source_var.get(),
                )
                report = self._workflow_engine().acquisition_workflow(candidate, raw_ocr_text=ocr_text.get("1.0", tk.END).strip())
                self.photo_candidates.append(candidate)
                if report.ocr_report:
                    self.ocr_reports.append(report.ocr_report)
                    self.ocr_results.append(report.ocr_report.result)
                if report.photo_review_report:
                    self.photo_records.extend(report.photo_review_report.attached_photos)
                self.shopping_candidates.append(candidate.to_shopping_candidate())
                dialog.destroy()
                self._show_workflow_report("Acquisition Workflow", report)
            except ValueError:
                messagebox.showerror("Invalid Price", "Please enter a numeric asking price.")
            except Exception as e:
                messagebox.showerror("Acquisition Workflow Error", f"Workflow failed: {str(e)}")

        ttk.Button(button_frame, text="Run Workflow", command=run_workflow).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_collection_review_workflow(self):
        """Open guided Dashboard -> Quality -> Integrity -> Snapshot workflow."""
        try:
            report = self._workflow_engine().collection_review_workflow()
            self._show_workflow_report("Collection Review Workflow", report)
        except Exception as e:
            messagebox.showerror("Collection Review Workflow Error", f"Workflow failed: {str(e)}")

    def open_daily_collector_summary(self):
        """Open daily collector summary workflow."""
        try:
            report = self._workflow_engine().daily_summary()
            self._show_workflow_report("Daily Collector Summary", report)
        except Exception as e:
            messagebox.showerror("Daily Collector Summary Error", f"Workflow failed: {str(e)}")

    def open_smart_shopping_assistant(self):
        """Open ranked Smart Shopping Assistant workflow."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Smart Shopping Assistant")
        dialog.geometry("900x760")

        assistant = SmartShoppingAssistant(
            self._collection_items(),
            self._active_want_list_intents(),
            self.market_awareness_engine,
        )
        current_report = {"report": None}

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        input_frame = ttk.LabelFrame(main_frame, text="Shopping Opportunities", padding="10")
        input_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            input_frame,
            text="Enter one opportunity per line: title | price | shipping | source",
        ).pack(anchor=tk.W)
        opportunities_text = tk.Text(input_frame, height=8, wrap=tk.WORD)
        opportunities_text.pack(fill=tk.X, pady=(6, 0))
        if self.shopping_candidates:
            opportunities_text.insert(
                tk.END,
                "\n".join(
                    f"{candidate.item_name} | {candidate.asking_price} | {candidate.shipping} | {candidate.source or candidate.recommendation_source}"
                    for candidate in self.shopping_candidates
                )
            )

        ttk.Label(
            input_frame,
            text=self.session_context.format_status_line(),
            wraplength=760,
        ).pack(anchor=tk.W, pady=(8, 0))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        result_frame = ttk.LabelFrame(main_frame, text="Ranked Recommendations", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True)

        def parse_money(value):
            cleaned = str(value or "").strip().replace("$", "").replace(",", "")
            return float(cleaned) if cleaned else 0.0

        def parse_candidates():
            candidates = []
            for line in opportunities_text.get("1.0", tk.END).splitlines():
                if not line.strip():
                    continue
                parts = [part.strip() for part in line.split("|")]
                title = parts[0] if parts else ""
                price = parse_money(parts[1]) if len(parts) > 1 else 0.0
                shipping = parse_money(parts[2]) if len(parts) > 2 else 0.0
                source = parts[3] if len(parts) > 3 else "Manual"
                candidates.append(ShoppingCandidate(
                    item_name=title,
                    source=source,
                    asking_price=price,
                    shipping=shipping,
                    recommendation_source="Smart Shopping Manual",
                ))
            return candidates

        def analyze():
            try:
                candidates = parse_candidates()
                self.shopping_candidates = candidates
                report = assistant.generate_report(candidates, include_want_list_targets=True, limit=10)
                current_report["report"] = report
                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, assistant.format_markdown(report))
            except ValueError:
                messagebox.showerror("Invalid Price", "Use numeric price and shipping values.")
            except Exception as e:
                messagebox.showerror("Smart Shopping Error", f"Shopping analysis failed: {str(e)}")

        def export_csv():
            if not current_report["report"]:
                analyze()
            file_path = filedialog.asksaveasfilename(
                title="Export Smart Shopping CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not file_path:
                return
            if assistant.export_csv(file_path, current_report["report"]):
                messagebox.showinfo("Success", f"Smart shopping CSV exported to {file_path}")
            else:
                messagebox.showerror("Error", "Failed to export smart shopping CSV")

        def export_markdown():
            if not current_report["report"]:
                analyze()
            file_path = filedialog.asksaveasfilename(
                title="Export Smart Shopping Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
            )
            if not file_path:
                return
            if assistant.export_markdown(file_path, current_report["report"]):
                messagebox.showinfo("Success", f"Smart shopping Markdown exported to {file_path}")
            else:
                messagebox.showerror("Error", "Failed to export smart shopping Markdown")

        ttk.Button(button_frame, text="Analyze Opportunities", command=analyze).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_opportunity_engine(self):
        """Open budget-aware collection opportunity workflow."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Opportunity Engine")
        dialog.geometry("920x760")

        engine = OpportunityEngine(
            self._collection_items(),
            self._active_want_list_intents(),
            self.market_awareness_engine,
        )
        current_report = {"report": None}

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        input_frame = ttk.LabelFrame(main_frame, text="Optional Candidate Opportunities", padding="10")
        input_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            input_frame,
            text="Enter optional candidates one per line: title | price | shipping | source",
        ).pack(anchor=tk.W)
        candidates_text = tk.Text(input_frame, height=7, wrap=tk.WORD)
        candidates_text.pack(fill=tk.X, pady=(6, 0))
        if self.shopping_candidates:
            candidates_text.insert(
                tk.END,
                "\n".join(
                    f"{candidate.item_name} | {candidate.asking_price} | {candidate.shipping} | {candidate.source or candidate.recommendation_source}"
                    for candidate in self.shopping_candidates
                )
            )

        ttk.Label(
            input_frame,
            text="Offline deterministic guidance only: no scraping, APIs, live pricing, market prediction, automatic purchases, or collection writes.",
            wraplength=820,
        ).pack(anchor=tk.W, pady=(8, 0))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        result_frame = ttk.LabelFrame(main_frame, text="Opportunity Report", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True)

        def parse_money(value):
            cleaned = str(value or "").strip().replace("$", "").replace(",", "")
            return float(cleaned) if cleaned else 0.0

        def parse_candidates():
            candidates = []
            for line in candidates_text.get("1.0", tk.END).splitlines():
                if not line.strip():
                    continue
                parts = [part.strip() for part in line.split("|")]
                title = parts[0] if parts else ""
                price = parse_money(parts[1]) if len(parts) > 1 else 0.0
                shipping = parse_money(parts[2]) if len(parts) > 2 else 0.0
                source = parts[3] if len(parts) > 3 else "Manual"
                candidates.append(ShoppingCandidate(
                    item_name=title,
                    source=source,
                    asking_price=price,
                    shipping=shipping,
                    recommendation_source="Opportunity Manual",
                ))
            return candidates

        def analyze():
            try:
                candidates = parse_candidates()
                self.shopping_candidates = candidates
                report = engine.generate_report(candidates, limit=5)
                current_report["report"] = report
                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, report.format_markdown())
            except ValueError:
                messagebox.showerror("Invalid Price", "Use numeric price and shipping values.")
            except Exception as e:
                messagebox.showerror("Opportunity Engine Error", f"Opportunity analysis failed: {str(e)}")

        def export_csv():
            if not current_report["report"]:
                analyze()
            file_path = filedialog.asksaveasfilename(
                title="Export Opportunity CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not file_path:
                return
            current_report["report"].export_csv(file_path)
            messagebox.showinfo("Export Complete", f"Opportunity CSV exported to {file_path}")

        def export_markdown():
            if not current_report["report"]:
                analyze()
            file_path = filedialog.asksaveasfilename(
                title="Export Opportunity Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
            )
            if not file_path:
                return
            current_report["report"].export_markdown(file_path)
            messagebox.showinfo("Export Complete", f"Opportunity Markdown exported to {file_path}")

        ttk.Button(button_frame, text="Analyze Opportunities", command=analyze).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_deal_hunter(self):
        """Open offline eBay.ca-style Deal Hunter workflow."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Deal Hunter")
        dialog.geometry("940x780")

        hunter = DealHunter(
            self._collection_items(),
            self._active_want_list_intents(),
            self.market_awareness_engine,
        )
        current_report = {"report": None}

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        input_frame = ttk.LabelFrame(main_frame, text="Deal Listings", padding="10")
        input_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            input_frame,
            text="Enter one listing per line: title | price_cad | shipping_cad | seller | source | listing_url | description",
        ).pack(anchor=tk.W)
        listings_text = tk.Text(input_frame, height=8, wrap=tk.WORD)
        listings_text.pack(fill=tk.X, pady=(6, 0))
        if self.recent_deal_listings:
            listings_text.insert(
                tk.END,
                "\n".join(
                    f"{listing.title} | {listing.price_cad} | {listing.shipping_cad} | {listing.seller} | {listing.source} | {listing.listing_url} | {listing.description}"
                    for listing in self.recent_deal_listings
                )
            )

        ttk.Label(
            input_frame,
            text="Offline only: URLs are stored as references. No scraping, browser automation, API calls, or live pricing.",
            wraplength=820,
        ).pack(anchor=tk.W, pady=(8, 0))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        result_frame = ttk.LabelFrame(main_frame, text="Deal Hunter Results", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True)

        def parse_money(value):
            cleaned = str(value or "").strip().replace("$", "").replace(",", "")
            return float(cleaned) if cleaned else 0.0

        def parse_manual_listings():
            listings = []
            for line in listings_text.get("1.0", tk.END).splitlines():
                if not line.strip():
                    continue
                parts = [part.strip() for part in line.split("|")]
                listings.append(DealListing(
                    title=parts[0] if parts else "",
                    price_cad=parse_money(parts[1]) if len(parts) > 1 else 0.0,
                    shipping_cad=parse_money(parts[2]) if len(parts) > 2 else 0.0,
                    seller=parts[3] if len(parts) > 3 else "",
                    source=parts[4] if len(parts) > 4 else "Manual",
                    listing_url=parts[5] if len(parts) > 5 else "",
                    description=parts[6] if len(parts) > 6 else "",
                ))
            return listings

        def analyze_listings(listings=None):
            try:
                rows = listings if listings is not None else parse_manual_listings()
                self.recent_deal_listings = list(rows)
                report = hunter.generate_report(rows)
                current_report["report"] = report
                self.deal_hunter_reports.append(report.to_dict())
                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, report.format_markdown())
            except ValueError:
                messagebox.showerror("Invalid Price", "Use numeric CAD price and shipping values.")
            except Exception as e:
                messagebox.showerror("Deal Hunter Error", f"Deal analysis failed: {str(e)}")

        def import_csv():
            file_path = filedialog.askopenfilename(
                title="Import Deal Hunter CSV",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not file_path:
                return
            try:
                import_result = DealHunter.import_csv_with_warnings(file_path)
                listings = import_result.listings
                listings_text.delete("1.0", tk.END)
                listings_text.insert(
                    tk.END,
                    "\n".join(
                        f"{listing.title} | {listing.price_cad} | {listing.shipping_cad} | {listing.seller} | {listing.source} | {listing.listing_url} | {listing.description}"
                        for listing in listings
                    )
                )
                analyze_listings(listings)
                detail = (
                    f"Rows found: {import_result.rows_found}\n"
                    f"Listings importable: {import_result.importable_count}\n"
                    f"Rows skipped: {import_result.skipped_rows}"
                )
                if import_result.warnings:
                    detail += "\n\nWarnings:\n" + "\n".join(f"- {warning}" for warning in import_result.warnings[:8])
                messagebox.showinfo("Deal Hunter CSV Import", detail)
            except Exception as e:
                messagebox.showerror("Deal Hunter CSV Error", f"CSV import failed: {str(e)}")

        def export_csv():
            if not current_report["report"]:
                analyze_listings()
            file_path = filedialog.asksaveasfilename(
                title="Export Deal Hunter CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not file_path:
                return
            current_report["report"].export_csv(file_path)
            messagebox.showinfo("Export Complete", f"Deal Hunter CSV exported to {file_path}")

        def export_markdown():
            if not current_report["report"]:
                analyze_listings()
            file_path = filedialog.asksaveasfilename(
                title="Export Deal Hunter Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
            )
            if not file_path:
                return
            current_report["report"].export_markdown(file_path)
            messagebox.showinfo("Export Complete", f"Deal Hunter Markdown exported to {file_path}")

        ttk.Button(button_frame, text="Analyze Listings", command=analyze_listings).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Import CSV", command=import_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_market_intelligence(self):
        """Open local deterministic Market Intelligence workflow."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Market Intelligence")
        dialog.geometry("960x800")

        engine = MarketIntelligenceEngine(
            self._collection_items(),
            self._active_want_list_intents(),
            self.market_awareness_engine,
        )
        current_report = {"report": None}

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        input_frame = ttk.LabelFrame(main_frame, text="Listing Input", padding="10")
        input_frame.pack(fill=tk.X, pady=(0, 10))

        title_var = tk.StringVar(value="1901 Newfoundland 50 cents VF20")
        price_var = tk.StringVar(value="80")
        shipping_var = tk.StringVar(value="5")
        seller_var = tk.StringVar()
        source_var = tk.StringVar(value="Manual")

        ttk.Label(input_frame, text="Title:").grid(row=0, column=0, sticky=tk.W, pady=3)
        ttk.Entry(input_frame, textvariable=title_var, width=80).grid(row=0, column=1, columnspan=3, sticky=(tk.W, tk.E), pady=3)
        ttk.Label(input_frame, text="Price CAD:").grid(row=1, column=0, sticky=tk.W, pady=3)
        ttk.Entry(input_frame, textvariable=price_var, width=16).grid(row=1, column=1, sticky=tk.W, pady=3)
        ttk.Label(input_frame, text="Shipping CAD:").grid(row=1, column=2, sticky=tk.W, pady=3)
        ttk.Entry(input_frame, textvariable=shipping_var, width=16).grid(row=1, column=3, sticky=tk.W, pady=3)
        ttk.Label(input_frame, text="Seller:").grid(row=2, column=0, sticky=tk.W, pady=3)
        ttk.Entry(input_frame, textvariable=seller_var, width=30).grid(row=2, column=1, sticky=tk.W, pady=3)
        ttk.Label(input_frame, text="Source:").grid(row=2, column=2, sticky=tk.W, pady=3)
        ttk.Entry(input_frame, textvariable=source_var, width=30).grid(row=2, column=3, sticky=tk.W, pady=3)
        ttk.Label(input_frame, text="Description:").grid(row=3, column=0, sticky=tk.NW, pady=3)
        description_text = tk.Text(input_frame, height=4, wrap=tk.WORD)
        description_text.grid(row=3, column=1, columnspan=3, sticky=(tk.W, tk.E), pady=3)
        input_frame.columnconfigure(1, weight=1)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        result_frame = ttk.LabelFrame(main_frame, text="Market Intelligence Report", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True)

        def parse_money(value):
            return float(value) if str(value or "").strip() else 0.0

        def analyze():
            try:
                listing = DealListing(
                    title_var.get(),
                    price_cad=parse_money(price_var.get()),
                    shipping_cad=parse_money(shipping_var.get()),
                    seller=seller_var.get(),
                    source=source_var.get(),
                    description=description_text.get("1.0", tk.END).strip(),
                )
                report = engine.evaluate_listing(listing)
                current_report["report"] = report
                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, report.format_markdown())
            except ValueError:
                messagebox.showerror("Invalid Price", "Use numeric CAD price and shipping values.")
            except Exception as e:
                messagebox.showerror("Market Intelligence Error", f"Analysis failed: {str(e)}")

        def export_csv():
            if not current_report["report"]:
                analyze()
            if not current_report["report"]:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Market Intelligence CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if not file_path:
                return
            current_report["report"].export_csv(file_path)
            messagebox.showinfo("Export Complete", f"Market Intelligence CSV exported to {file_path}")

        def export_markdown():
            if not current_report["report"]:
                analyze()
            if not current_report["report"]:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Market Intelligence Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
            )
            if not file_path:
                return
            current_report["report"].export_markdown(file_path)
            messagebox.showinfo("Export Complete", f"Market Intelligence Markdown exported to {file_path}")

        ttk.Button(button_frame, text="Analyze", command=analyze).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_market_intelligence_automation(self):
        """Open batch Market Intelligence enrichment workflow."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Market Intelligence Automation")
        dialog.geometry("980x800")

        engine = MarketIntelligenceAutomationEngine(
            self._collection_items(),
            self._active_want_list_intents(),
            self.market_awareness_engine,
        )
        current_report = {"report": None}

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        input_frame = ttk.LabelFrame(main_frame, text="Candidate Listings", padding="10")
        input_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            input_frame,
            text="Enter one listing per line: title | price_cad | shipping_cad | seller | source | listing_url | original_recommendation",
        ).pack(anchor=tk.W)
        listings_text = tk.Text(input_frame, height=8, wrap=tk.WORD)
        listings_text.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(
            input_frame,
            text="Uses existing local Market Intelligence only. No scraping, APIs, live pricing, exchange rates, purchases, or collection mutation.",
            wraplength=840,
        ).pack(anchor=tk.W, pady=(8, 0))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        result_frame = ttk.LabelFrame(main_frame, text="Automation Report", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True)

        def parse_money(value):
            cleaned = str(value or "").strip().replace("$", "").replace(",", "")
            return float(cleaned) if cleaned else 0.0

        def parse_rows():
            rows = []
            for line in listings_text.get("1.0", tk.END).splitlines():
                if not line.strip():
                    continue
                parts = [part.strip() for part in line.split("|")]
                listing = DealListing(
                    title=parts[0] if parts else "",
                    price_cad=parse_money(parts[1]) if len(parts) > 1 else 0.0,
                    shipping_cad=parse_money(parts[2]) if len(parts) > 2 else 0.0,
                    seller=parts[3] if len(parts) > 3 else "",
                    source=parts[4] if len(parts) > 4 else "Manual",
                    listing_url=parts[5] if len(parts) > 5 else "",
                )
                rows.append({"listing": listing, "recommendation": parts[6] if len(parts) > 6 else "UNKNOWN"})
            return rows

        def enrich_rows():
            try:
                report = engine.enrich_candidates(parse_rows(), "GUI manual candidates")
                current_report["report"] = report
                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, report.format_markdown())
            except ValueError:
                messagebox.showerror("Invalid Price", "Use numeric CAD price and shipping values.")
            except Exception as e:
                messagebox.showerror("Market Intelligence Automation Error", f"Enrichment failed: {str(e)}")

        def export_csv():
            if not current_report["report"]:
                enrich_rows()
            if not current_report["report"]:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Market Intelligence Automation CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if not file_path:
                return
            current_report["report"].export_csv(file_path)
            messagebox.showinfo("Export Complete", f"Market Intelligence Automation CSV exported to {file_path}")

        def export_markdown():
            if not current_report["report"]:
                enrich_rows()
            if not current_report["report"]:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Market Intelligence Automation Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
            )
            if not file_path:
                return
            current_report["report"].export_markdown(file_path)
            messagebox.showinfo("Export Complete", f"Market Intelligence Automation Markdown exported to {file_path}")

        ttk.Button(button_frame, text="Enrich Candidates", command=enrich_rows).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_watchlists_and_alerts(self):
        """Open report-driven Watchlists & Alerts workflow."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Watchlists & Alerts")
        dialog.geometry("1040x820")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)

        ttk.Label(
            main_frame,
            text="Edit watch rows as: name | type | query | priority | keywords. Alerts are generated only when you run a scan.",
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))

        watch_frame = ttk.LabelFrame(main_frame, text="Watchlists", padding="8")
        watch_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=(0, 6), pady=(0, 8))
        watch_frame.columnconfigure(0, weight=1)
        candidate_frame = ttk.LabelFrame(main_frame, text="Candidate Rows", padding="8")
        candidate_frame.grid(row=1, column=1, sticky=tk.NSEW, padx=(6, 0), pady=(0, 8))
        candidate_frame.columnconfigure(0, weight=1)

        watch_text = tk.Text(watch_frame, height=12, wrap=tk.WORD)
        watch_text.grid(row=0, column=0, sticky=tk.NSEW)
        watch_text.insert(tk.END, self._format_watchlists_for_editor(self.watchlists))

        candidate_text = tk.Text(candidate_frame, height=12, wrap=tk.WORD)
        candidate_text.grid(row=0, column=0, sticky=tk.NSEW)
        candidate_text.insert(
            tk.END,
            "Newfoundland 1904H 50 cents EF40 | 125 | 10 | Dealer | Local candidate | \n"
            "Canada 1926 Near 6 nickel VF | 80 | 5 | Dealer | Local candidate | \n",
        )

        result_frame = ttk.LabelFrame(main_frame, text="Watchlist Report and Alerts", padding="8")
        result_frame.grid(row=2, column=0, columnspan=2, sticky=tk.NSEW)
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.grid(row=0, column=0, sticky=tk.NSEW)

        current = {"watch_report": None, "alert_report": None}

        def load_presets():
            self.watchlists = [WatchlistEngine.adam_presets()]
            watch_text.delete("1.0", tk.END)
            watch_text.insert(tk.END, self._format_watchlists_for_editor(self.watchlists))

        def save_watchlists():
            try:
                parsed = self._parse_watchlists_from_editor(watch_text.get("1.0", tk.END))
                self.watchlists = parsed or [WatchlistEngine.adam_presets()]
                messagebox.showinfo("Watchlists Saved", f"Saved {sum(len(w.items) for w in self.watchlists)} watch item(s).")
            except Exception as exc:
                messagebox.showerror("Watchlist Error", f"Could not save watchlists: {str(exc)}")

        def run_scan():
            try:
                save_watchlists()
                candidates = self._parse_watchlist_candidate_rows(candidate_text.get("1.0", tk.END))
                engine = WatchlistEngine(self.watchlists)
                alert_engine = AlertEngine(engine)
                watch_report = engine.scan(candidates)
                alert_report = alert_engine.generate_alerts(candidates)
                current["watch_report"] = watch_report
                current["alert_report"] = alert_report
                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, watch_report.format_markdown())
                result_text.insert(tk.END, "\n")
                result_text.insert(tk.END, alert_report.format_markdown())
            except Exception as exc:
                messagebox.showerror("Watchlist Scan Error", f"Watchlist scan failed: {str(exc)}")

        def export_csv():
            if not current["alert_report"]:
                run_scan()
            if not current["alert_report"]:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Alert Report CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if not file_path:
                return
            current["alert_report"].export_csv(file_path)
            messagebox.showinfo("Export Complete", f"Alert CSV exported to {file_path}")

        def export_markdown():
            if not current["alert_report"] or not current["watch_report"]:
                run_scan()
            if not current["alert_report"] or not current["watch_report"]:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Watchlists & Alerts Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
            )
            if not file_path:
                return
            with open(file_path, "w", encoding="utf-8") as handle:
                handle.write(current["watch_report"].format_markdown())
                handle.write("\n")
                handle.write(current["alert_report"].format_markdown())
            messagebox.showinfo("Export Complete", f"Watchlists & Alerts Markdown exported to {file_path}")

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(8, 0))
        ttk.Button(button_frame, text="Load Adam Presets", command=load_presets).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Save Watchlists", command=save_watchlists).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Run Watch Scan", command=run_scan).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def _format_watchlists_for_editor(self, watchlists):
        lines = []
        for watchlist in watchlists:
            for item in watchlist.items:
                lines.append(
                    " | ".join([
                        item.name,
                        item.watch_type,
                        item.query,
                        item.priority.value,
                        "; ".join(item.keywords),
                    ])
                )
        return "\n".join(lines) + ("\n" if lines else "")

    def _parse_watchlists_from_editor(self, text):
        watchlist = Watchlist(name="GUI Watchlists")
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [part.strip() for part in line.split("|")]
            while len(parts) < 5:
                parts.append("")
            name, watch_type, query, priority, keywords = parts[:5]
            keyword_list = [keyword.strip() for keyword in keywords.replace(",", ";").split(";") if keyword.strip()]
            watchlist.add_item(WatchlistItem(name=name, watch_type=watch_type, query=query, priority=priority, keywords=keyword_list))
        return [watchlist] if watchlist.items else []

    def _parse_watchlist_candidate_rows(self, text):
        listings = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [part.strip() for part in line.split("|")]
            while len(parts) < 6:
                parts.append("")
            title, price, shipping, seller, source, url = parts[:6]
            try:
                price_value = float(price) if price else 0.0
            except ValueError:
                price_value = 0.0
            try:
                shipping_value = float(shipping) if shipping else 0.0
            except ValueError:
                shipping_value = 0.0
            listings.append(DealListing(
                title=title,
                price_cad=price_value,
                shipping_cad=shipping_value,
                seller=seller,
                source=source,
                listing_url=url,
            ))
        return listings

    def open_field_test_and_tuning(self):
        """Open deterministic live pipeline field-test workflow."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Field Test & Tuning")
        dialog.geometry("980x800")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        scenarios = default_field_test_scenarios()
        summary_var = tk.StringVar(value=f"Loaded {len(scenarios)} deterministic field-test scenario(s).")
        ttk.Label(main_frame, textvariable=summary_var).grid(row=0, column=0, sticky=tk.W, pady=(0, 8))

        result_frame = ttk.LabelFrame(main_frame, text="Field Test Report", padding="8")
        result_frame.grid(row=1, column=0, sticky=tk.NSEW)
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.grid(row=0, column=0, sticky=tk.NSEW)
        result_text.insert(
            tk.END,
            "Run field tests to measure validation failures, duplicates, alert volume, review escalations, and likely false positives.\n",
        )

        current_report = {"report": None}

        def run_tests():
            try:
                runner = ScenarioRunner(
                    collection_items=self._collection_items(),
                    want_list_intents=self._active_want_list_intents(),
                    market_awareness_engine=self.market_awareness_engine,
                    watchlists=self.watchlists,
                )
                report = runner.run_scenarios(scenarios)
                current_report["report"] = report
                summary_var.set(
                    f"Scenarios: {report.scenario_count}   PASS: {report.pass_count}   REVIEW: {report.review_count}"
                )
                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, report.format_markdown())
            except Exception as exc:
                messagebox.showerror("Field Test Error", f"Field test run failed: {str(exc)}")

        def export_csv():
            if not current_report["report"]:
                run_tests()
            if not current_report["report"]:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Field Test CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if not file_path:
                return
            current_report["report"].export_csv(file_path)
            messagebox.showinfo("Export Complete", f"Field test CSV exported to {file_path}")

        def export_markdown():
            if not current_report["report"]:
                run_tests()
            if not current_report["report"]:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Field Test Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
            )
            if not file_path:
                return
            current_report["report"].export_markdown(file_path)
            messagebox.showinfo("Export Complete", f"Field test Markdown exported to {file_path}")

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky=tk.W, pady=(8, 0))
        ttk.Button(button_frame, text="Run Field Tests", command=run_tests).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_phone_photo_capture(self):
        """Open metadata-only phone photo capture workflow."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Phone Photo Capture")
        dialog.geometry("980x760")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)

        form_frame = ttk.LabelFrame(main_frame, text="Capture Session", padding="8")
        form_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 8))
        for col in range(1, 4):
            form_frame.columnconfigure(col, weight=1)

        session_type_var = tk.StringVar(value=SESSION_COIN_FRONT_BACK)
        subject_var = tk.StringVar(value="Field capture")
        location_var = tk.StringVar(value="Field workflow")
        notes_var = tk.StringVar()
        front_var = tk.StringVar()
        back_var = tk.StringVar()
        listing_var = tk.StringVar()

        def browse(target_var):
            file_path = filedialog.askopenfilename(
                title="Select Phone Photo",
                filetypes=[
                    ("Image files", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"),
                    ("All files", "*.*"),
                ],
            )
            if file_path:
                target_var.set(file_path)

        ttk.Label(form_frame, text="Session Type:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Combobox(
            form_frame,
            textvariable=session_type_var,
            values=[SESSION_COIN_FRONT_BACK, SESSION_NOTE_FRONT_BACK, SESSION_LISTING_PHOTOS],
            state="readonly",
            width=24,
        ).grid(row=0, column=1, sticky=tk.EW, pady=2, padx=(4, 8))
        ttk.Label(form_frame, text="Subject:").grid(row=0, column=2, sticky=tk.W, pady=2)
        ttk.Entry(form_frame, textvariable=subject_var).grid(row=0, column=3, sticky=tk.EW, pady=2, padx=(4, 0))

        ttk.Label(form_frame, text="Location:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(form_frame, textvariable=location_var).grid(row=1, column=1, sticky=tk.EW, pady=2, padx=(4, 8))
        ttk.Label(form_frame, text="Notes:").grid(row=1, column=2, sticky=tk.W, pady=2)
        ttk.Entry(form_frame, textvariable=notes_var).grid(row=1, column=3, sticky=tk.EW, pady=2, padx=(4, 0))

        for row, label, variable in [
            (2, "Front Photo:", front_var),
            (3, "Back Photo:", back_var),
            (4, "Listing Photo:", listing_var),
        ]:
            ttk.Label(form_frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
            ttk.Entry(form_frame, textvariable=variable).grid(row=row, column=1, columnspan=2, sticky=tk.EW, pady=2, padx=(4, 8))
            ttk.Button(form_frame, text="Browse", command=lambda var=variable: browse(var)).grid(row=row, column=3, sticky=tk.W, pady=2)

        summary_var = tk.StringVar(value="No capture sessions yet.")
        ttk.Label(main_frame, textvariable=summary_var).grid(row=1, column=0, sticky=tk.W, pady=(0, 8))

        result_frame = ttk.LabelFrame(main_frame, text="Capture Report", padding="8")
        result_frame.grid(row=2, column=0, sticky=tk.NSEW)
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.grid(row=0, column=0, sticky=tk.NSEW)

        def refresh_report():
            report = self.photo_capture_workflow.report()
            summary_var.set(
                f"Sessions: {report.total_sessions}   Photos: {report.total_photos}   "
                f"Missing front/back: {report.missing_front_count}/{report.missing_back_count}   "
                f"OCR-ready: {report.ready_for_ocr_count}   Review-ready: {report.ready_for_review_count}"
            )
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, report.format_markdown())
            return report

        def add_session():
            session_type = session_type_var.get()
            subject = subject_var.get()
            session = None
            if session_type == SESSION_LISTING_PHOTOS:
                if not listing_var.get().strip():
                    messagebox.showwarning("Photo Required", "Select a listing photo before adding this session.")
                    return
                session = self.photo_capture_workflow.capture_listing_photo(subject, listing_var.get(), notes=notes_var.get())
            else:
                if not any([front_var.get().strip(), back_var.get().strip(), listing_var.get().strip()]):
                    messagebox.showwarning("Photo Required", "Select at least one photo before adding this session.")
                    return
                session = self.photo_capture_workflow.start_session(
                    session_type=session_type,
                    subject=subject,
                    location=location_var.get(),
                    notes=notes_var.get(),
                )
                if front_var.get().strip():
                    role = ROLE_NOTE_FRONT if session_type == SESSION_NOTE_FRONT_BACK else ROLE_COIN_FRONT
                    session.add_photo(front_var.get(), role)
                if back_var.get().strip():
                    role = ROLE_NOTE_BACK if session_type == SESSION_NOTE_FRONT_BACK else ROLE_COIN_BACK
                    session.add_photo(back_var.get(), role)
                if listing_var.get().strip():
                    session.add_photo(listing_var.get(), ROLE_LISTING, linked_coin_name=subject)
            self.photo_records.extend(session.to_photo_records())
            refresh_report()

        def export_csv():
            file_path = filedialog.asksaveasfilename(
                title="Export Phone Photo Capture CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if not file_path:
                return
            refresh_report().export_csv(file_path)
            messagebox.showinfo("Export Complete", f"Phone photo capture CSV exported to {file_path}")

        def export_markdown():
            file_path = filedialog.asksaveasfilename(
                title="Export Phone Photo Capture Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
            )
            if not file_path:
                return
            refresh_report().export_markdown(file_path)
            messagebox.showinfo("Export Complete", f"Phone photo capture Markdown exported to {file_path}")

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, sticky=tk.W, pady=(8, 0))
        ttk.Button(button_frame, text="Add Capture Session", command=add_session).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Refresh Report", command=refresh_report).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)
        refresh_report()

    def open_mobile_collector_companion(self):
        """Open mobile-oriented Collector Companion workflow simulation."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Mobile Collector Companion")
        dialog.geometry("980x800")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)

        ttk.Label(
            main_frame,
            text="Enter candidate rows as: title | price | shipping | seller | source | url. This is a desktop/local mobile workflow simulation.",
        ).grid(row=0, column=0, sticky=tk.W, pady=(0, 8))

        candidate_frame = ttk.LabelFrame(main_frame, text="Field Candidates", padding="8")
        candidate_frame.grid(row=1, column=0, sticky=tk.EW, pady=(0, 8))
        candidate_frame.columnconfigure(0, weight=1)
        candidate_text = tk.Text(candidate_frame, height=8, wrap=tk.WORD)
        candidate_text.grid(row=0, column=0, sticky=tk.EW)
        candidate_text.insert(
            tk.END,
            "Newfoundland 1904H 50 cents EF40 | 145 | 12 | Dealer | Coin Show | https://field.test/nfld\n"
            "Canada 1926 Near 6 nickel VF | 95 | 7 | Dealer | Coin Show | https://field.test/near6\n",
        )

        result_frame = ttk.LabelFrame(main_frame, text="Mobile Companion Report", padding="8")
        result_frame.grid(row=2, column=0, sticky=tk.NSEW)
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.grid(row=0, column=0, sticky=tk.NSEW)

        current_report = {"report": None}

        def generate():
            try:
                companion = MobileCollectorCompanion(
                    collection_items=self._collection_items(),
                    want_list_intents=self._active_want_list_intents(),
                    market_awareness_engine=self.market_awareness_engine,
                    watchlists=self.watchlists,
                    photo_capture_workflow=self.photo_capture_workflow,
                )
                listings = self._parse_watchlist_candidate_rows(candidate_text.get("1.0", tk.END))
                report = companion.generate_report(
                    listings,
                    workflow_type=WORKFLOW_COIN_SHOW,
                    location="Field workflow",
                    ocr_identification_report=self.ocr_identification_reports[-1] if self.ocr_identification_reports else None,
                    mobile_entry_report=self.mobile_entry_reports[-1] if self.mobile_entry_reports else None,
                    workflow_completion_report=self.workflow_completion_reports[-1] if self.workflow_completion_reports else None,
                    cloud_readiness_report=self.cloud_readiness_reports[-1] if self.cloud_readiness_reports else None,
                )
                current_report["report"] = report
                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, report.format_markdown())
            except Exception as exc:
                messagebox.showerror("Mobile Companion Error", f"Mobile companion report failed: {str(exc)}")

        def export_csv():
            if not current_report["report"]:
                generate()
            if not current_report["report"]:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Mobile Companion CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if not file_path:
                return
            current_report["report"].export_csv(file_path)
            messagebox.showinfo("Export Complete", f"Mobile Companion CSV exported to {file_path}")

        def export_markdown():
            if not current_report["report"]:
                generate()
            if not current_report["report"]:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Mobile Companion Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
            )
            if not file_path:
                return
            current_report["report"].export_markdown(file_path)
            messagebox.showinfo("Export Complete", f"Mobile Companion Markdown exported to {file_path}")

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, sticky=tk.W, pady=(8, 0))
        ttk.Button(button_frame, text="Generate Report", command=generate).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_portfolio_performance(self):
        """Open deterministic, read-only Portfolio Analytics."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Portfolio Analytics")
        dialog.geometry("960x800")

        engine = PortfolioPerformanceEngine(
            self._collection_items(),
            self._active_want_list_intents(),
            market_awareness_engine=self.market_awareness_engine,
            snapshot_manager=self.snapshot_manager,
            shopping_candidates=self.shopping_candidates,
            photo_records=self.photo_records,
        )
        current_report = {"report": engine.generate_report()}

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        summary_frame = ttk.LabelFrame(main_frame, text="Portfolio Analytics Summary", padding="10")
        summary_frame.pack(fill=tk.X, pady=(0, 10))
        report = current_report["report"]
        summary_var = tk.StringVar(
            value=self.portfolio_financial_summary_text(report.financial_summary)
        )
        ttk.Label(
            summary_frame,
            textvariable=summary_var,
            justify=tk.LEFT,
            wraplength=900,
        ).pack(anchor=tk.W)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        result_frame = ttk.LabelFrame(main_frame, text="Portfolio Analytics Report", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True)
        result_text.insert(tk.END, report.format_markdown())

        def refresh():
            current_report["report"] = engine.generate_report()
            summary_var.set(
                self.portfolio_financial_summary_text(current_report["report"].financial_summary)
            )
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, current_report["report"].format_markdown())

        def export_csv():
            file_path = filedialog.asksaveasfilename(
                title="Export Portfolio Analytics CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if not file_path:
                return
            current_report["report"].export_csv(file_path)
            messagebox.showinfo("Export Complete", f"Portfolio Analytics CSV exported to {file_path}")

        def export_markdown():
            file_path = filedialog.asksaveasfilename(
                title="Export Portfolio Analytics Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
            )
            if not file_path:
                return
            current_report["report"].export_markdown(file_path)
            messagebox.showinfo("Export Complete", f"Portfolio Analytics Markdown exported to {file_path}")

        ttk.Button(button_frame, text="Refresh", command=refresh).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_deal_hunter_calibration(self):
        """Open offline Deal Hunter calibration report workflow."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Deal Hunter Calibration")
        dialog.geometry("940x760")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        summary_var = tk.StringVar(value="No calibration report loaded.")
        ttk.Label(main_frame, textvariable=summary_var).pack(anchor=tk.W, pady=(0, 8))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        result_frame = ttk.LabelFrame(main_frame, text="Calibration Report", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True)

        current_report = {"report": None}

        def run_file(file_path):
            engine = DealHunterCalibrationEngine(
                self._collection_items(),
                self._active_want_list_intents(),
                self.market_awareness_engine,
            )
            cases = engine.load_cases(file_path)
            report = engine.run(cases)
            current_report["report"] = report
            summary_var.set(
                f"Cases: {report.total_cases} | Passed: {report.passed_cases} | "
                f"Failed: {report.failed_cases} | Status: {report.status}"
            )
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, report.format_markdown())

        def load_csv():
            file_path = filedialog.askopenfilename(
                title="Load Deal Hunter Calibration CSV",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if not file_path:
                return
            try:
                run_file(file_path)
            except Exception as e:
                messagebox.showerror("Calibration Error", f"Calibration failed: {str(e)}")

        def run_default_fixture():
            fixture_path = os.path.join("test_data", "deal_hunter", "calibration_cases.csv")
            if not os.path.exists(fixture_path):
                messagebox.showerror("Missing Fixture", f"Default calibration fixture not found: {fixture_path}")
                return
            try:
                run_file(fixture_path)
            except Exception as e:
                messagebox.showerror("Calibration Error", f"Calibration failed: {str(e)}")

        def export_csv():
            if not current_report["report"]:
                run_default_fixture()
            if not current_report["report"]:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Deal Hunter Calibration CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if not file_path:
                return
            current_report["report"].export_csv(file_path)
            messagebox.showinfo("Export Complete", f"Deal Hunter calibration CSV exported to {file_path}")

        def export_markdown():
            if not current_report["report"]:
                run_default_fixture()
            if not current_report["report"]:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Deal Hunter Calibration Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
            )
            if not file_path:
                return
            current_report["report"].export_markdown(file_path)
            messagebox.showinfo("Export Complete", f"Deal Hunter calibration Markdown exported to {file_path}")

        ttk.Button(button_frame, text="Run Default Fixture", command=run_default_fixture).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Load CSV", command=load_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_deal_hunter_ranking(self):
        """Open ranked offline Deal Hunter candidate pool workflow."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Deal Hunter Ranking")
        dialog.geometry("960x800")

        engine = DealHunterRankingEngine(
            self._collection_items(),
            self._active_want_list_intents(),
            self.market_awareness_engine,
        )
        current_report = {"report": None}
        current_pool = {"pool": CandidatePool.from_listings(self.recent_deal_listings)}

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        input_frame = ttk.LabelFrame(main_frame, text="Candidate Pool", padding="10")
        input_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            input_frame,
            text="Enter one listing per line: title | price_cad | shipping_cad | seller | source | listing_url | description",
        ).pack(anchor=tk.W)
        listings_text = tk.Text(input_frame, height=8, wrap=tk.WORD)
        listings_text.pack(fill=tk.X, pady=(6, 0))
        if self.recent_deal_listings:
            listings_text.insert(
                tk.END,
                "\n".join(
                    f"{listing.title} | {listing.price_cad} | {listing.shipping_cad} | {listing.seller} | {listing.source} | {listing.listing_url} | {listing.description}"
                    for listing in self.recent_deal_listings
                )
            )

        ttk.Label(
            input_frame,
            text="Offline ranking only: CSV imports are local files; no scraping, browser automation, APIs, live listing retrieval, or automatic purchasing.",
            wraplength=840,
        ).pack(anchor=tk.W, pady=(8, 0))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        result_frame = ttk.LabelFrame(main_frame, text="Ranked Opportunities", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True)

        def parse_money(value):
            cleaned = str(value or "").strip().replace("$", "").replace(",", "")
            return float(cleaned) if cleaned else 0.0

        def parse_manual_pool():
            listings = []
            for line in listings_text.get("1.0", tk.END).splitlines():
                if not line.strip():
                    continue
                parts = [part.strip() for part in line.split("|")]
                listings.append(DealListing(
                    title=parts[0] if parts else "",
                    price_cad=parse_money(parts[1]) if len(parts) > 1 else 0.0,
                    shipping_cad=parse_money(parts[2]) if len(parts) > 2 else 0.0,
                    seller=parts[3] if len(parts) > 3 else "",
                    source=parts[4] if len(parts) > 4 else "Manual",
                    listing_url=parts[5] if len(parts) > 5 else "",
                    description=parts[6] if len(parts) > 6 else "",
                ))
            return CandidatePool.from_listings(listings)

        def render_pool(pool):
            listings_text.delete("1.0", tk.END)
            listings_text.insert(
                tk.END,
                "\n".join(
                    f"{listing.title} | {listing.price_cad} | {listing.shipping_cad} | {listing.seller} | {listing.source} | {listing.listing_url} | {listing.description}"
                    for listing in pool.listings
                )
            )

        def analyze_pool(pool=None):
            try:
                active_pool = pool if pool is not None else parse_manual_pool()
                current_pool["pool"] = active_pool
                self.recent_deal_listings = list(active_pool.listings)
                report = engine.rank_pool(active_pool)
                current_report["report"] = report
                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, report.format_markdown())
            except ValueError:
                messagebox.showerror("Invalid Price", "Use numeric CAD price and shipping values.")
            except Exception as e:
                messagebox.showerror("Deal Hunter Ranking Error", f"Ranking failed: {str(e)}")

        def import_csv():
            file_path = filedialog.askopenfilename(
                title="Import Deal Hunter Candidate CSV",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not file_path:
                return
            try:
                pool = current_pool["pool"] if current_pool["pool"].candidate_count else parse_manual_pool()
                import_result = pool.import_csv(file_path, ImportProfile.ebay_csv())
                current_pool["pool"] = pool
                render_pool(pool)
                analyze_pool(pool)
                detail = (
                    f"Rows found: {import_result.rows_found}\n"
                    f"Listings imported: {import_result.imported_count}\n"
                    f"Duplicate imports: {import_result.duplicate_count}\n"
                    f"Rows skipped: {import_result.skipped_rows}"
                )
                if import_result.warnings:
                    detail += "\n\nWarnings:\n" + "\n".join(f"- {warning}" for warning in import_result.warnings[:8])
                messagebox.showinfo("Deal Hunter Candidate Import", detail)
            except Exception as e:
                messagebox.showerror("Deal Hunter Ranking CSV Error", f"CSV import failed: {str(e)}")

        def export_csv():
            if not current_report["report"]:
                analyze_pool()
            if not current_report["report"]:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Deal Hunter Ranking CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not file_path:
                return
            current_report["report"].export_csv(file_path)
            messagebox.showinfo("Export Complete", f"Deal Hunter ranking CSV exported to {file_path}")

        def export_markdown():
            if not current_report["report"]:
                analyze_pool()
            if not current_report["report"]:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Deal Hunter Ranking Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
            )
            if not file_path:
                return
            current_report["report"].export_markdown(file_path)
            messagebox.showinfo("Export Complete", f"Deal Hunter ranking Markdown exported to {file_path}")

        ttk.Button(button_frame, text="Rank Pool", command=analyze_pool).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Import CSV", command=import_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_live_deal_hunter(self):
        """Open controlled-beta live RSS Deal Hunter workflow."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Live Deal Hunter")
        dialog.geometry("980x800")

        hunter = LiveDealHunter(
            self._collection_items(),
            self._active_want_list_intents(),
            self.market_awareness_engine,
        )
        current_report = {"report": None}

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        input_frame = ttk.LabelFrame(main_frame, text="Live RSS Source", padding="10")
        input_frame.pack(fill=tk.X, pady=(0, 10))
        input_frame.columnconfigure(1, weight=1)

        source_url_var = tk.StringVar(value=DEFAULT_EBAY_RSS_URL)
        timeout_var = tk.StringVar(value="10")

        ttk.Label(input_frame, text="RSS URL:").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Entry(input_frame, textvariable=source_url_var).grid(
            row=0, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4
        )
        ttk.Label(input_frame, text="Timeout seconds:").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Entry(input_frame, textvariable=timeout_var, width=12).grid(
            row=1, column=1, sticky=tk.W, padx=(8, 0), pady=4
        )
        ttk.Label(
            input_frame,
            text=(
                "Controlled beta: fetches only when Analyze Live Feed is pressed. "
                "No purchases, bids, collection mutation, background polling, scraping, or browser automation."
            ),
            wraplength=840,
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(8, 0))

        status_var = tk.StringVar(value="No live feed analyzed yet.")
        ttk.Label(main_frame, textvariable=status_var).pack(anchor=tk.W, pady=(0, 8))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        result_frame = ttk.LabelFrame(main_frame, text="Live Deal Hunter Report", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True)

        def analyze_live_feed():
            try:
                timeout = float(timeout_var.get() or "10")
            except ValueError:
                messagebox.showerror("Invalid Timeout", "Use a numeric timeout value.")
                return
            source = RSSListingConnector(source_url_var.get().strip(), timeout=timeout)
            report = hunter.run_source(source)
            current_report["report"] = report
            status_var.set(
                f"Listings: {report.listing_count} | Accepted: {report.accepted_count} | "
                f"Rejected: {report.rejected_count} | Errors: {len(report.errors)}"
            )
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, report.format_markdown())

        def export_csv():
            if not current_report["report"]:
                analyze_live_feed()
            if not current_report["report"]:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Live Deal Hunter CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if not file_path:
                return
            current_report["report"].export_csv(file_path)
            messagebox.showinfo("Export Complete", f"Live Deal Hunter CSV exported to {file_path}")

        def export_markdown():
            if not current_report["report"]:
                analyze_live_feed()
            if not current_report["report"]:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Live Deal Hunter Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
            )
            if not file_path:
                return
            current_report["report"].export_markdown(file_path)
            messagebox.showinfo("Export Complete", f"Live Deal Hunter Markdown exported to {file_path}")

        ttk.Button(button_frame, text="Analyze Live Feed", command=analyze_live_feed).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_live_source_validation(self):
        """Open live source validation report workflow."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Live Source Validation")
        dialog.geometry("980x780")

        validator = LiveSourceValidator()
        current_report = {"report": None}

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        input_frame = ttk.LabelFrame(main_frame, text="Live RSS Source", padding="10")
        input_frame.pack(fill=tk.X, pady=(0, 10))
        input_frame.columnconfigure(1, weight=1)

        source_url_var = tk.StringVar(value=DEFAULT_EBAY_RSS_URL)
        timeout_var = tk.StringVar(value="10")

        ttk.Label(input_frame, text="RSS URL:").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Entry(input_frame, textvariable=source_url_var).grid(
            row=0, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4
        )
        ttk.Label(input_frame, text="Timeout seconds:").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Entry(input_frame, textvariable=timeout_var, width=12).grid(
            row=1, column=1, sticky=tk.W, padx=(8, 0), pady=4
        )
        ttk.Label(
            input_frame,
            text=(
                "Validates live source quality before listings enter Deal Hunter, Ranking, "
                "Opportunity, or Market Intelligence. No purchases, bids, background polling, or collection mutation."
            ),
            wraplength=840,
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(8, 0))

        status_var = tk.StringVar(value="No live source validated yet.")
        ttk.Label(main_frame, textvariable=status_var).pack(anchor=tk.W, pady=(0, 8))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        result_frame = ttk.LabelFrame(main_frame, text="Validation Report", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True)

        def validate_source():
            try:
                timeout = float(timeout_var.get() or "10")
            except ValueError:
                messagebox.showerror("Invalid Timeout", "Use a numeric timeout value.")
                return
            connector = RSSListingConnector(source_url_var.get().strip(), timeout_seconds=timeout)
            batch = connector.fetch_listings()
            report = validator.validate_batch(batch)
            current_report["report"] = report
            status_var.set(
                f"Health: {report.source_health.status.value} | Listings: {report.summary.total_listings} | "
                f"Valid: {report.summary.valid_count} | Review: {report.summary.review_count}"
            )
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, report.format_markdown())

        def export_csv():
            if not current_report["report"]:
                validate_source()
            if not current_report["report"]:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Live Source Validation CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if not file_path:
                return
            current_report["report"].export_csv(file_path)
            messagebox.showinfo("Export Complete", f"Live Source Validation CSV exported to {file_path}")

        def export_markdown():
            if not current_report["report"]:
                validate_source()
            if not current_report["report"]:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Live Source Validation Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
            )
            if not file_path:
                return
            current_report["report"].export_markdown(file_path)
            messagebox.showinfo("Export Complete", f"Live Source Validation Markdown exported to {file_path}")

        ttk.Button(button_frame, text="Validate Source", command=validate_source).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_live_deal_hunter_readiness(self):
        """Open future live-source readiness audit report."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Live Deal Hunter Readiness")
        dialog.geometry("940x760")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        status_var = tk.StringVar(value="Run readiness audit to review future live-source guardrails.")
        ttk.Label(main_frame, textvariable=status_var).pack(anchor=tk.W, pady=(0, 8))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        result_frame = ttk.LabelFrame(main_frame, text="Readiness Report", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True)

        current_report = {"report": None}

        def run_audit():
            report = LiveDealHunterReadinessAudit().run()
            current_report["report"] = report
            status_var.set(
                f"Status: {report.status} | Blockers: {len(report.blockers)} | "
                f"Warnings: {len(report.warnings)}"
            )
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, report.format_markdown())

        def export_csv():
            if not current_report["report"]:
                run_audit()
            file_path = filedialog.asksaveasfilename(
                title="Export Live Deal Hunter Readiness CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if not file_path:
                return
            current_report["report"].export_csv(file_path)
            messagebox.showinfo("Export Complete", f"Live Deal Hunter readiness CSV exported to {file_path}")

        def export_markdown():
            if not current_report["report"]:
                run_audit()
            file_path = filedialog.asksaveasfilename(
                title="Export Live Deal Hunter Readiness Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
            )
            if not file_path:
                return
            current_report["report"].export_markdown(file_path)
            messagebox.showinfo("Export Complete", f"Live Deal Hunter readiness Markdown exported to {file_path}")

        ttk.Button(button_frame, text="Run Audit", command=run_audit).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def open_external_listing_connectors(self):
        """Open offline external listing connector import workflow."""
        dialog = tk.Toplevel(self.root)
        dialog.title("External Listing Connectors")
        dialog.geometry("980x800")

        registry = ConnectorRegistry()
        current_imports = {"reports": []}
        current_ranking = {"report": None}

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        input_frame = ttk.LabelFrame(main_frame, text="Local Listing Import", padding="10")
        input_frame.pack(fill=tk.X, pady=(0, 10))
        input_frame.columnconfigure(1, weight=1)

        connector_var = tk.StringVar(value=registry.names()[0])
        source_var = tk.StringVar()
        ttk.Label(input_frame, text="Connector:").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Combobox(input_frame, textvariable=connector_var, values=registry.names(), state="readonly").grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)
        ttk.Label(input_frame, text="Source name:").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Entry(input_frame, textvariable=source_var).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)
        ttk.Label(
            input_frame,
            text="Imports local CSV files only. No scraping, browser automation, APIs, live listing retrieval, or collection mutation.",
            wraplength=840,
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(8, 0))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        result_frame = ttk.LabelFrame(main_frame, text="Connector Results", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True)

        def render_summary():
            reports = current_imports["reports"]
            all_listings = [listing for report in reports for listing in report.listings]
            source_summary = SourceSummaryReport.from_listings(all_listings)
            duplicates = DuplicateOpportunityDetector().detect(all_listings)
            lines = [
                "# External Listing Connectors",
                "",
                f"- Imported reports: {len(reports)}",
                f"- Normalized listings: {len(all_listings)}",
                f"- Duplicate findings: {len(duplicates)}",
                "- Guidance note: offline local-file connector framework only.",
                "",
                "## Imports",
                "",
            ]
            if not reports:
                lines.append("- No files imported yet.")
            for report in reports:
                lines.extend([
                    f"- {report.connector_name}: {report.imported_count} listings from {report.source_path}",
                    f"  - Validation: {report.validation_report.status}",
                    f"  - Skipped rows: {report.validation_report.skipped_rows}",
                ])
                for warning in report.validation_report.warnings[:5]:
                    lines.append(f"  - Warning: {warning}")
            lines.extend(["", "## Source Summary", "", source_summary.format_markdown(), "## Duplicate Findings", ""])
            if duplicates:
                for duplicate in duplicates:
                    lines.append(f"- {duplicate.duplicate_type}: {duplicate.count} records ({duplicate.key})")
            else:
                lines.append("- No duplicate opportunities detected.")
            if current_ranking["report"]:
                lines.extend(["", "## Ranking Preview", ""])
                lines.extend(current_ranking["report"]._format_deals(current_ranking["report"].ranked_deals[:5]))
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, "\n".join(lines).rstrip() + "\n")

        def import_file():
            file_path = filedialog.askopenfilename(
                title="Import External Listing CSV",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not file_path:
                return
            try:
                report = registry.import_file(connector_var.get(), file_path, source_name=source_var.get())
                current_imports["reports"].append(report)
                render_summary()
                detail = (
                    f"Connector: {report.connector_name}\n"
                    f"Rows found: {report.validation_report.rows_found}\n"
                    f"Listings imported: {report.imported_count}\n"
                    f"Rows skipped: {report.validation_report.skipped_rows}\n"
                    f"Warnings: {len(report.validation_report.warnings)}"
                )
                messagebox.showinfo("External Listing Import", detail)
            except Exception as e:
                messagebox.showerror("External Listing Connector Error", f"Import failed: {str(e)}")

        def rank_imports():
            try:
                engine = DealHunterRankingEngine(
                    self._collection_items(),
                    self._active_want_list_intents(),
                    self.market_awareness_engine,
                )
                current_ranking["report"] = registry.rank_reports(current_imports["reports"], engine)
                render_summary()
            except Exception as e:
                messagebox.showerror("External Listing Ranking Error", f"Ranking failed: {str(e)}")

        def export_import_markdown():
            if not current_imports["reports"]:
                messagebox.showwarning("No Imports", "Import at least one listing file first.")
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Connector Import Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
            )
            if not file_path:
                return
            with open(file_path, "w", encoding="utf-8") as handle:
                for report in current_imports["reports"]:
                    handle.write(report.format_markdown())
                    handle.write("\n")
            messagebox.showinfo("Export Complete", f"Connector import report exported to {file_path}")

        def export_ranking_csv():
            if not current_ranking["report"]:
                rank_imports()
            if not current_ranking["report"]:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Multi-Source Ranking CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not file_path:
                return
            current_ranking["report"].export_csv(file_path)
            messagebox.showinfo("Export Complete", f"Multi-source ranking CSV exported to {file_path}")

        ttk.Button(button_frame, text="Import File", command=import_file).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Rank Imported Listings", command=rank_imports).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Import Markdown", command=export_import_markdown).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Ranking CSV", command=export_ranking_csv).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)
        render_summary()

    def open_upgrade_advisor(self):
        """Open Upgrade Advisor dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Upgrade Advisor")
        dialog.geometry("600x700")
        
        # Form frame
        form_frame = ttk.Frame(dialog, padding="20")
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Candidate Coin section
        candidate_frame = ttk.LabelFrame(form_frame, text="Candidate Coin", padding="10")
        candidate_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Country
        ttk.Label(candidate_frame, text="Country:").grid(row=0, column=0, sticky=tk.W, pady=5)
        country_var = tk.StringVar()
        ttk.Entry(candidate_frame, textvariable=country_var).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        # Denomination
        ttk.Label(candidate_frame, text="Denomination:").grid(row=1, column=0, sticky=tk.W, pady=5)
        denom_var = tk.StringVar()
        ttk.Entry(candidate_frame, textvariable=denom_var).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        # Year
        ttk.Label(candidate_frame, text="Year:").grid(row=2, column=0, sticky=tk.W, pady=5)
        year_var = tk.StringVar()
        ttk.Entry(candidate_frame, textvariable=year_var).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        # Grade
        ttk.Label(candidate_frame, text="Grade:").grid(row=3, column=0, sticky=tk.W, pady=5)
        grade_var = tk.StringVar()
        grade_combo = ttk.Combobox(candidate_frame, textvariable=grade_var,
                                   values=["", "PO-1", "FR-2", "AG-3", "G-4", "VG-8", "F-12", "VF-20", "VF-30", "EF-40", "EF-45", "AU-50", "AU-53", "AU-55", "AU-58", "MS-60", "MS-61", "MS-62", "MS-63", "MS-64", "MS-65", "MS-66", "MS-67", "MS-68", "MS-69", "MS-70"])
        grade_combo.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        # Estimated Value
        ttk.Label(candidate_frame, text="Estimated Value ($):").grid(row=4, column=0, sticky=tk.W, pady=5)
        estimate_var = tk.StringVar()
        ttk.Entry(candidate_frame, textvariable=estimate_var).grid(row=4, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        candidate_frame.columnconfigure(1, weight=1)
        
        # Button frame
        button_frame = ttk.Frame(form_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        def analyze_upgrade():
            try:
                country = country_var.get().strip()
                denomination = denom_var.get().strip()
                year = year_var.get().strip()
                grade = grade_var.get().strip()
                estimate = float(estimate_var.get()) if estimate_var.get() else 0.0
                
                if not country or not denomination or not year:
                    messagebox.showwarning("Missing Information", "Please enter Country, Denomination, and Year")
                    return
                
                # Get collection items
                collection_items = self.app.collection.get_all_items()
                
                # Analyze upgrade
                advisor = UpgradeAdvisor(collection_items)
                recommendation = advisor.analyze_upgrade(country, denomination, year, grade, estimate)
                
                # Display results
                result_text.delete(1.0, tk.END)
                result_text.insert(tk.END, recommendation.explanation)
                
                # Store recommendation for export
                dialog.current_recommendation = recommendation
                
            except ValueError as e:
                messagebox.showerror("Error", f"Invalid input: {str(e)}")
            except Exception as e:
                messagebox.showerror("Error", f"Analysis failed: {str(e)}")
        
        def export_csv():
            if not hasattr(dialog, 'current_recommendation'):
                messagebox.showwarning("No Analysis", "Please run an analysis first")
                return
            
            file_path = filedialog.asksaveasfilename(
                title="Export Upgrade Analysis",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if not file_path:
                return
            
            advisor = UpgradeAdvisor(self.app.collection.get_all_items())
            if advisor.export_to_csv([dialog.current_recommendation], file_path):
                messagebox.showinfo("Success", f"Upgrade analysis exported to {file_path}")
            else:
                messagebox.showerror("Error", "Failed to export upgrade analysis")
        
        ttk.Button(button_frame, text="Analyze Upgrade", command=analyze_upgrade).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)
        
        # Results frame
        results_frame = ttk.LabelFrame(form_frame, text="Upgrade Analysis", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        result_text = tk.Text(results_frame, wrap=tk.WORD, height=15)
        result_text.pack(fill=tk.BOTH, expand=True)
    
    def open_portfolio_dashboard(self):
        """Open Portfolio Dashboard dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Portfolio Dashboard")
        dialog.geometry("900x700")
        
        # Get collection items
        items = self.app.collection.get_all_items()
        
        # Create dashboard
        dashboard = PortfolioDashboard(items)
        summary = dashboard.generate_dashboard()
        
        # Main frame
        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Summary section
        summary_frame = ttk.LabelFrame(main_frame, text="Collection Overview", padding="10")
        summary_frame.pack(fill=tk.X, pady=(0, 10))
        
        summary_text = (
            f"Total Items: {summary.total_items} | "
            f"Total Countries: {summary.total_countries} | "
            f"Total Estimated Value: CAD ${summary.total_estimated_value_cad:.2f} | "
            f"Total Melt Value: CAD ${summary.total_melt_value_cad:.2f}"
        )
        ttk.Label(summary_frame, text=summary_text, font=("Arial", 10, "bold")).pack()
        
        # Create notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Priority progress tab
        priority_frame = ttk.Frame(notebook, padding="10")
        notebook.add(priority_frame, text="Priority Progress")
        
        # Newfoundland progress
        nf_frame = ttk.LabelFrame(priority_frame, text="Newfoundland Coinage", padding="10")
        nf_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(nf_frame, text=f"Total Items: {summary.newfoundland_progress['total_items']}").pack(anchor=tk.W)
        ttk.Label(nf_frame, text=f"Denominations: {summary.newfoundland_progress['denominations']}").pack(anchor=tk.W)
        
        nf_tree = ttk.Treeview(nf_frame, columns=("Denomination", "Count", "Years"), show="headings", height=3)
        nf_tree.heading("Denomination", text="Denomination")
        nf_tree.heading("Count", text="Count")
        nf_tree.heading("Years", text="Years")
        nf_tree.pack(fill=tk.X, pady=(5, 0))
        
        for denom, data in summary.newfoundland_progress["series"].items():
            nf_tree.insert("", tk.END, values=(denom, data["count"], data["years"]))
        
        # Canadian silver progress
        cs_frame = ttk.LabelFrame(priority_frame, text="Canadian Silver Coinage", padding="10")
        cs_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(cs_frame, text=f"Total Items: {summary.canadian_silver_progress['total_items']}").pack(anchor=tk.W)
        ttk.Label(cs_frame, text=f"Denominations: {summary.canadian_silver_progress['denominations']}").pack(anchor=tk.W)
        
        cs_tree = ttk.Treeview(cs_frame, columns=("Denomination", "Count", "Years"), show="headings", height=3)
        cs_tree.heading("Denomination", text="Denomination")
        cs_tree.heading("Count", text="Count")
        cs_tree.heading("Years", text="Years")
        cs_tree.pack(fill=tk.X, pady=(5, 0))
        
        for denom, data in summary.canadian_silver_progress["series"].items():
            cs_tree.insert("", tk.END, values=(denom, data["count"], data["years"]))
        
        # 1859 Large Cent progress
        lc_frame = ttk.LabelFrame(priority_frame, text="1859 Large Cent", padding="10")
        lc_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(lc_frame, text=f"Total Items: {summary.large_cent_1859_progress['total_items']}").pack(anchor=tk.W)
        ttk.Label(lc_frame, text=f"Unique Grades: {summary.large_cent_1859_progress['unique_grades']}").pack(anchor=tk.W)
        
        lc_tree = ttk.Treeview(lc_frame, columns=("Grade", "Count"), show="headings", height=3)
        lc_tree.heading("Grade", text="Grade")
        lc_tree.heading("Count", text="Count")
        lc_tree.pack(fill=tk.X, pady=(5, 0))
        
        for grade, count in summary.large_cent_1859_progress["grades"].items():
            lc_tree.insert("", tk.END, values=(grade, count))
        
        # Targets tab
        targets_frame = ttk.Frame(notebook, padding="10")
        notebook.add(targets_frame, text="Targets & Duplicates")
        
        # Top gap targets
        gap_frame = ttk.LabelFrame(targets_frame, text="Top Gap-Fill Targets", padding="10")
        gap_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        gap_tree = ttk.Treeview(gap_frame, columns=("Country", "Denomination", "Year", "Type", "Priority"), show="headings", height=5)
        gap_tree.heading("Country", text="Country")
        gap_tree.heading("Denomination", text="Denomination")
        gap_tree.heading("Year", text="Year")
        gap_tree.heading("Type", text="Type")
        gap_tree.heading("Priority", text="Priority")
        gap_tree.pack(fill=tk.BOTH, expand=True)
        
        for target in summary.top_gap_targets:
            gap_tree.insert("", tk.END, values=(
                target["country"],
                target["denomination"],
                target["year"],
                target["target_type"],
                target["priority_score"]
            ))
        
        # Top upgrade targets
        upgrade_frame = ttk.LabelFrame(targets_frame, text="Top Upgrade Targets", padding="10")
        upgrade_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        upgrade_tree = ttk.Treeview(upgrade_frame, columns=("Country", "Denomination", "Year", "Best Grade"), show="headings", height=5)
        upgrade_tree.heading("Country", text="Country")
        upgrade_tree.heading("Denomination", text="Denomination")
        upgrade_tree.heading("Year", text="Year")
        upgrade_tree.heading("Best Grade", text="Best Grade")
        upgrade_tree.pack(fill=tk.BOTH, expand=True)
        
        for target in summary.top_upgrade_targets:
            upgrade_tree.insert("", tk.END, values=(
                target["country"],
                target["denomination"],
                target["year"],
                target["current_best_grade"]
            ))
        
        # Duplicate-heavy areas
        dup_frame = ttk.LabelFrame(targets_frame, text="Duplicate-Heavy Areas", padding="10")
        dup_frame.pack(fill=tk.BOTH, expand=True)
        
        dup_tree = ttk.Treeview(dup_frame, columns=("Country", "Denomination", "Year", "Count"), show="headings", height=5)
        dup_tree.heading("Country", text="Country")
        dup_tree.heading("Denomination", text="Denomination")
        dup_tree.heading("Year", text="Year")
        dup_tree.heading("Count", text="Count")
        dup_tree.pack(fill=tk.BOTH, expand=True)
        
        for dup in summary.duplicate_heavy_areas:
            dup_tree.insert("", tk.END, values=(
                dup["country"],
                dup["denomination"],
                dup["year"],
                dup["count"]
            ))
        
        # WANT_LIST tab
        want_frame = ttk.Frame(notebook, padding="10")
        notebook.add(want_frame, text="WANT_LIST Progress")
        
        want_label_frame = ttk.LabelFrame(want_frame, text="WANT_LIST Progress", padding="10")
        want_label_frame.pack(fill=tk.X)
        
        ttk.Label(want_label_frame, text=f"Total Intents: {summary.want_list_progress['total_intents']}").pack(anchor=tk.W)
        ttk.Label(want_label_frame, text=f"Fulfilled: {summary.want_list_progress['fulfilled']}").pack(anchor=tk.W)
        ttk.Label(want_label_frame, text=f"Pending: {summary.want_list_progress['pending']}").pack(anchor=tk.W)
        ttk.Label(want_label_frame, text=f"Progress: {summary.want_list_progress['progress_percentage']:.1f}%").pack(anchor=tk.W)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        def export_csv():
            file_path = filedialog.asksaveasfilename(
                title="Export Dashboard to CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")]
            )
            if file_path:
                try:
                    dashboard.export_to_csv(file_path)
                    messagebox.showinfo("Success", f"Dashboard exported to {file_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to export dashboard: {str(e)}")
        
        def export_markdown():
            file_path = filedialog.asksaveasfilename(
                title="Export Dashboard to Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md")]
            )
            if file_path:
                try:
                    dashboard.export_to_markdown(file_path)
                    messagebox.showinfo("Success", f"Dashboard exported to {file_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to export dashboard: {str(e)}")
        
        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)


    def open_numista_intelligence(self):
        """Open Numista Intelligence analysis workflow."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Numista Intelligence")
        dialog.geometry("900x800")

        engine = NumistaIntelligenceEngine.from_items(self._collection_items())
        current_report = {"report": None}

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        file_frame = ttk.LabelFrame(main_frame, text="Numista Export", padding="10")
        file_frame.pack(fill=tk.X, pady=(0, 10))

        file_var = tk.StringVar()

        def browse_file():
            path = filedialog.askopenfilename(
                title="Select Numista Export",
                filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if path:
                file_var.set(path)

        ttk.Label(file_frame, text="File:").grid(row=0, column=0, sticky=tk.W, pady=3)
        ttk.Entry(file_frame, textvariable=file_var, width=70).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=3)
        ttk.Button(file_frame, text="Browse", command=browse_file).grid(row=0, column=2, sticky=tk.W, padx=(6, 0), pady=3)
        file_frame.columnconfigure(1, weight=1)

        result_frame = ttk.LabelFrame(main_frame, text="Numista Intelligence Report", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def analyze():
            try:
                report = engine.analyze_file(file_var.get())
                current_report["report"] = report
                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, "Numista Intelligence Report\n")
                result_text.insert(tk.END, f"Total: {report.total_numista_items}\n")
                result_text.insert(tk.END, f"Owned: {report.owned_count}\n")
                result_text.insert(tk.END, f"Duplicates: {report.duplicate_count}\n")
                result_text.insert(tk.END, f"Upgrades: {report.upgrade_count}\n")
                result_text.insert(tk.END, f"Gaps: {report.gap_count}\n")
                result_text.insert(tk.END, f"Varieties: {report.variety_count}\n")
                result_text.insert(tk.END, f"New Series: {report.new_series_count}\n")
                result_text.insert(tk.END, f"Not Relevant: {report.not_relevant_count}\n")
                result_text.insert(tk.END, "\nRecommendations:\n")
                for rec in report.summary_recommendations:
                    result_text.insert(tk.END, f"- {rec}\n")
                if report.top_priorities:
                    result_text.insert(tk.END, "\nTop Priorities:\n")
                    for i, a in enumerate(report.top_priorities[:10], 1):
                        result_text.insert(tk.END, f"{i}. {a.title} ({a.status.value}, {a.priority.value})\n")
            except Exception as e:
                messagebox.showerror("Numista Intelligence Error", f"Analysis failed: {str(e)}")

        def export_csv():
            if not current_report["report"]:
                analyze()
            if not current_report["report"]:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Numista Intelligence CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if file_path:
                try:
                    engine.export_report_csv(file_path)
                    messagebox.showinfo("Success", f"Report exported to {file_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to export: {str(e)}")

        def export_markdown():
            if not current_report["report"]:
                analyze()
            if not current_report["report"]:
                return
            file_path = filedialog.asksaveasfilename(
                title="Export Numista Intelligence Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
            )
            if file_path:
                try:
                    engine.export_report_markdown(file_path)
                    messagebox.showinfo("Success", f"Report exported to {file_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to export: {str(e)}")

        ttk.Button(button_frame, text="Analyze", command=analyze).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

    def open_smart_phone_cataloguer(self):
        """Open Smart Phone Cataloguer workflow.

        Provides a streamlined interface for cataloguing coins from phone photos
        using the SmartPhoneCataloguer orchestration engine.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Smart Phone Cataloguer")
        dialog.geometry("900x800")

        cataloguer = SmartPhoneCataloguer()
        current_result = {"result": None}

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Photo Selection Section ---
        photo_frame = ttk.LabelFrame(main_frame, text="Photo Selection", padding="10")
        photo_frame.pack(fill=tk.X, pady=(0, 10))

        # Coin Front Photo
        front_var = tk.StringVar()
        ttk.Label(photo_frame, text="Front Photo:").grid(row=0, column=0, sticky=tk.W, pady=3)
        ttk.Entry(photo_frame, textvariable=front_var, width=60).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=3)

        def browse_front():
            path = filedialog.askopenfilename(
                title="Select Front Photo",
                filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]
            )
            if path:
                front_var.set(path)

        ttk.Button(photo_frame, text="Browse", command=browse_front).grid(row=0, column=2, sticky=tk.W, padx=(6, 0), pady=3)

        # Coin Back Photo
        back_var = tk.StringVar()
        ttk.Label(photo_frame, text="Back Photo:").grid(row=1, column=0, sticky=tk.W, pady=3)
        ttk.Entry(photo_frame, textvariable=back_var, width=60).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=3)

        def browse_back():
            path = filedialog.askopenfilename(
                title="Select Back Photo",
                filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]
            )
            if path:
                back_var.set(path)

        ttk.Button(photo_frame, text="Browse", command=browse_back).grid(row=1, column=2, sticky=tk.W, padx=(6, 0), pady=3)
        photo_frame.columnconfigure(1, weight=1)

        # Subject/Description
        subject_frame = ttk.Frame(main_frame)
        subject_frame.pack(fill=tk.X, pady=(0, 10))

        subject_var = tk.StringVar(value="")
        ttk.Label(subject_frame, text="Subject/Description:").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Entry(subject_frame, textvariable=subject_var, width=70).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # --- Results Display ---
        result_frame = ttk.LabelFrame(main_frame, text="Cataloguing Results", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        result_text = tk.Text(result_frame, wrap=tk.WORD, height=20)
        result_text.pack(fill=tk.BOTH, expand=True)

        # --- Button Frame ---
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def run_catalogue_workflow():
            """Run the complete Smart Phone Cataloguer workflow."""
            try:
                front_path = front_var.get()
                back_path = back_var.get()
                subject = subject_var.get() or "Unknown Item"

                if not front_path and not back_path:
                    messagebox.showwarning("No Photos", "Please select at least one photo.")
                    return

                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, "Running Smart Phone Cataloguer Workflow...\n")
                result_text.insert(tk.END, f"Subject: {subject}\n")
                result_text.insert(tk.END, f"Front: {front_path or 'Not provided'}\n")
                result_text.insert(tk.END, f"Back: {back_path or 'Not provided'}\n\n")

                # Step 1: Catalogue photos
                catalogue_result = cataloguer.catalog_coin(
                    subject=subject,
                    front_path=front_path,
                    back_path=back_path,
                )

                result_text.insert(tk.END, f"=== Photo Capture ===\n")
                result_text.insert(tk.END, f"Session ID: {catalogue_result.session_id}\n")
                result_text.insert(tk.END, f"Status: {catalogue_result.status}\n")
                result_text.insert(tk.END, f"Photos: {len(catalogue_result.photos)}\n")
                result_text.insert(tk.END, f"OCR Ready: {catalogue_result.ocr_ready}\n")
                result_text.insert(tk.END, f"Review Ready: {catalogue_result.review_ready}\n\n")

                if not catalogue_result.ocr_ready:
                    result_text.insert(tk.END, "Session not ready for OCR. Please provide both front and back photos.\n")
                    current_result["result"] = catalogue_result
                    return

                # Step 2: Run OCR identification
                result_text.insert(tk.END, "=== OCR Identification ===\n")
                session = cataloguer.workflow.sessions[-1]
                ocr_report = cataloguer.identify_session(session)

                result_text.insert(tk.END, f"OCR Candidates: {len(ocr_report.candidates)}\n")
                if ocr_report.candidates:
                    top = ocr_report.candidates[0]
                    result_text.insert(tk.END, f"Top Candidate: {top.country} {top.denomination} {top.year}\n")
                    result_text.insert(tk.END, f"Confidence: {getattr(top, 'confidence_score', 'N/A')}\n")
                result_text.insert(tk.END, "\n")

                # Step 3: Collection matching
                result_text.insert(tk.END, "=== Collection Matching ===\n")
                collection_items = self._collection_items()
                match_result = cataloguer.match_against_collection(collection_items, session)

                result_text.insert(tk.END, f"Duplicate: {match_result.is_duplicate}\n")
                result_text.insert(tk.END, f"Duplicate Count: {match_result.duplicate_count}\n")
                result_text.insert(tk.END, f"Upgrade Candidate: {match_result.is_upgrade_candidate}\n")
                if match_result.is_upgrade_candidate:
                    result_text.insert(tk.END, f"Current Best Grade: {match_result.current_best_grade}\n")
                result_text.insert(tk.END, "\n")

                # Step 4: Create proposed entry
                result_text.insert(tk.END, "=== Proposed Collection Entry ===\n")
                proposed_entry = cataloguer.create_proposed_entry(session, ocr_report, match_result)

                result_text.insert(tk.END, f"Status: {proposed_entry.status}\n")
                result_text.insert(tk.END, f"Confidence Score: {proposed_entry.confidence_score:.2f}\n")

                if proposed_entry.warnings:
                    result_text.insert(tk.END, "\nWarnings:\n")
                    for warning in proposed_entry.warnings:
                        result_text.insert(tk.END, f"- {warning}\n")

                if proposed_entry.recommendations:
                    result_text.insert(tk.END, "\nRecommendations:\n")
                    for rec in proposed_entry.recommendations:
                        result_text.insert(tk.END, f"- {rec}\n")

                # Step 5: Generate review
                result_text.insert(tk.END, "\n=== Review ===\n")
                review = cataloguer.review_entry(proposed_entry)

                result_text.insert(tk.END, f"Can Add to Collection: {review['can_add_to_collection']}\n")
                result_text.insert(tk.END, f"Requires User Review: {review['requires_user_review']}\n")
                result_text.insert(tk.END, f"\n{review['review_guidance']}\n")

                result_text.insert(tk.END, "\n=== Workflow Complete ===\n")
                result_text.insert(tk.END, "This is a read-only proposed entry. No collection mutation has occurred.\n")
                result_text.insert(tk.END, "Use the Collection Assistant to add items after review.\n")

                current_result["result"] = {
                    "catalogue": catalogue_result,
                    "ocr": ocr_report,
                    "match": match_result,
                    "proposed": proposed_entry,
                    "review": review,
                }

            except Exception as e:
                messagebox.showerror("Cataloguer Error", f"Workflow failed: {str(e)}")
                result_text.insert(tk.END, f"\nError: {str(e)}\n")

        def export_report():
            """Export the current workflow results."""
            if not current_result["result"]:
                messagebox.showwarning("No Results", "Please run the workflow first.")
                return

            file_path = filedialog.asksaveasfilename(
                title="Export Smart Phone Cataloguer Report",
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            if file_path:
                try:
                    with open(file_path, 'w') as f:
                        f.write(result_text.get("1.0", tk.END))
                    messagebox.showinfo("Success", f"Report exported to {file_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to export: {str(e)}")

        def clear_form():
            """Clear all form fields."""
            front_var.set("")
            back_var.set("")
            subject_var.set("")
            result_text.delete("1.0", tk.END)
            current_result["result"] = None

        # Large buttons for mobile-friendly layout
        ttk.Button(button_frame, text="Run Workflow", command=run_catalogue_workflow).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Export Report", command=export_report).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Clear", command=clear_form).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)


    def open_ai_grading_assistant(self):
        """Open AI Grading Assistant dialog.

        Provides deterministic, explainable grading guidance for coin candidates
        using collection grade patterns and evidence-based assessment.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("AI Grading Assistant")
        dialog.geometry("900x800")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Create notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Single Assessment tab
        single_frame = ttk.Frame(notebook, padding="10")
        notebook.add(single_frame, text="Single Assessment")
        single_frame.columnconfigure(1, weight=1)

        # Form fields
        country_var = tk.StringVar()
        denomination_var = tk.StringVar()
        year_var = tk.StringVar()
        series_var = tk.StringVar()
        grade_var = tk.StringVar()
        notes_var = tk.StringVar()
        photo_var = tk.StringVar()

        fields = [
            ("Country:", country_var),
            ("Denomination:", denomination_var),
            ("Year:", year_var),
            ("Series:", series_var),
            ("Claimed Grade:", grade_var),
            ("Notes:", notes_var),
            ("Photo Reference:", photo_var),
        ]

        for row, (label, variable) in enumerate(fields):
            ttk.Label(single_frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=4)
            entry = ttk.Entry(single_frame, textvariable=variable)
            entry.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=4)

        def browse_photo():
            path = filedialog.askopenfilename(
                title="Select Photo Reference",
                filetypes=[
                    ("Image files", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"),
                    ("All files", "*.*"),
                ],
            )
            if path:
                photo_var.set(path)

        ttk.Button(single_frame, text="Browse", command=browse_photo).grid(
            row=6, column=2, sticky=tk.W, padx=(6, 0), pady=4
        )

        # Result display
        result_frame = ttk.LabelFrame(single_frame, text="Assessment Result", padding="10")
        result_frame.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        single_frame.rowconfigure(7, weight=1)

        result_text = tk.Text(result_frame, wrap=tk.WORD, height=12)
        result_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        current_assessment = {"assessment": None}

        def assess_candidate():
            try:
                engine = CollectionIntelligenceEngine(self._collection_items())
                assistant = AIGradingAssistant(engine)
                candidate = GradingCandidate(
                    country=country_var.get().strip(),
                    denomination=denomination_var.get().strip(),
                    year=year_var.get().strip() or None,
                    series=series_var.get().strip() or None,
                    claimed_grade=grade_var.get().strip() or None,
                    notes=notes_var.get().strip() or None,
                    photo_references=[photo_var.get().strip()] if photo_var.get().strip() else [],
                )
                assessment = assistant.assess_candidate(candidate)
                current_assessment["assessment"] = assessment

                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, "# AI Grading Assessment")
                result_text.insert(tk.END, "\n")
                result_text.insert(tk.END, "\n")
                result_text.insert(tk.END, "**Coin:** " + candidate.country + " " + candidate.denomination)
                if candidate.year:
                    result_text.insert(tk.END, " " + candidate.year)
                result_text.insert(tk.END, "\n")
                result_text.insert(tk.END, "\n")
                result_text.insert(tk.END, "**Claimed Grade:** " + (candidate.claimed_grade or "Not provided"))
                result_text.insert(tk.END, "\n")
                result_text.insert(tk.END, "**Estimated Range:** " + (assessment.estimated_range[0] or "Unknown") + " - " + (assessment.estimated_range[1] or "Unknown"))
                result_text.insert(tk.END, "\n")
                result_text.insert(tk.END, "**Most Likely Grade:** " + (assessment.most_likely_grade or "Unknown"))
                result_text.insert(tk.END, "\n")
                result_text.insert(tk.END, "**Recommendation:** " + assessment.recommendation)
                result_text.insert(tk.END, "\n")
                result_text.insert(tk.END, "\n")

                if assessment.evidence:
                    result_text.insert(tk.END, "## Evidence")
                    result_text.insert(tk.END, "\n")
                    result_text.insert(tk.END, "\n")
                    for ev in assessment.evidence:
                        result_text.insert(tk.END, "- " + ev)
                        result_text.insert(tk.END, "\n")
                    result_text.insert(tk.END, "\n")

                if assessment.review_flags:
                    result_text.insert(tk.END, "## Review Flags")
                    result_text.insert(tk.END, "\n")
                    result_text.insert(tk.END, "\n")
                    for flag in assessment.review_flags:
                        result_text.insert(tk.END, "- " + flag)
                        result_text.insert(tk.END, "\n")
                    result_text.insert(tk.END, "\n")

                if assessment.collection_context:
                    result_text.insert(tk.END, "## Collection Context")
                    result_text.insert(tk.END, "\n")
                    result_text.insert(tk.END, "\n")
                    for key, val in assessment.collection_context.items():
                        result_text.insert(tk.END, "- " + key + ": " + str(val))
                        result_text.insert(tk.END, "\n")
                    result_text.insert(tk.END, "\n")

            except Exception as e:
                messagebox.showerror("Assessment Error", "Grading assessment failed: " + str(e))

        single_button_frame = ttk.Frame(single_frame)
        single_button_frame.grid(row=8, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))

        ttk.Button(single_button_frame, text="Assess Candidate", command=assess_candidate).pack(side=tk.LEFT, padx=(0, 5))

        # Batch Assessment tab
        batch_frame = ttk.Frame(notebook, padding="10")
        notebook.add(batch_frame, text="Batch Assessment")
        batch_frame.columnconfigure(0, weight=1)
        batch_frame.rowconfigure(0, weight=1)

        batch_input_frame = ttk.LabelFrame(batch_frame, text="Batch Candidates (one per line: Country,Denomination,Year,ClaimedGrade)", padding="10")
        batch_input_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        batch_input_frame.columnconfigure(0, weight=1)
        batch_input_frame.rowconfigure(0, weight=1)

        batch_text = tk.Text(batch_input_frame, wrap=tk.WORD, height=8)
        batch_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        batch_result_frame = ttk.LabelFrame(batch_frame, text="Batch Results", padding="10")
        batch_result_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        batch_result_frame.columnconfigure(0, weight=1)
        batch_result_frame.rowconfigure(0, weight=1)
        batch_frame.rowconfigure(1, weight=1)

        batch_result_text = tk.Text(batch_result_frame, wrap=tk.WORD, height=12)
        batch_result_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        current_batch_report = {"report": None}

        def run_batch_assessment():
            try:
                lines = batch_text.get("1.0", tk.END).strip().split("\n")
                candidates = []
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) < 2:
                        continue
                    gc = GradingCandidate(
                        country=parts[0],
                        denomination=parts[1],
                        year=parts[2] if len(parts) > 2 and parts[2] else None,
                        claimed_grade=parts[3] if len(parts) > 3 and parts[3] else None,
                    )
                    candidates.append(gc)

                if not candidates:
                    messagebox.showwarning("No Candidates", "Please enter at least one candidate.")
                    return

                engine = CollectionIntelligenceEngine(self._collection_items())
                assistant = AIGradingAssistant(engine)
                report = assistant.assess_batch(candidates)
                current_batch_report["report"] = report

                batch_result_text.delete("1.0", tk.END)
                batch_result_text.insert(tk.END, "# AI Grading Batch Assessment")
                batch_result_text.insert(tk.END, "\n")
                batch_result_text.insert(tk.END, "\n")
                batch_result_text.insert(tk.END, "**Total Candidates:** " + str(len(report.assessments)))
                batch_result_text.insert(tk.END, "\n")
                batch_result_text.insert(tk.END, "\n")

                summary = report.to_dict()["summary"]
                batch_result_text.insert(tk.END, "## Summary")
                batch_result_text.insert(tk.END, "\n")
                batch_result_text.insert(tk.END, "\n")
                batch_result_text.insert(tk.END, "- PROCEED: " + str(summary["PROCEED"]))
                batch_result_text.insert(tk.END, "\n")
                batch_result_text.insert(tk.END, "- CAUTION: " + str(summary["CAUTION"]))
                batch_result_text.insert(tk.END, "\n")
                batch_result_text.insert(tk.END, "- REVIEW: " + str(summary["REVIEW"]))
                batch_result_text.insert(tk.END, "\n")
                batch_result_text.insert(tk.END, "\n")

                batch_result_text.insert(tk.END, "## Assessments")
                batch_result_text.insert(tk.END, "\n")
                batch_result_text.insert(tk.END, "\n")
                for assessment in report.assessments:
                    c = assessment.candidate
                    batch_result_text.insert(tk.END, "### " + c.country + " " + c.denomination + " " + (c.year or ""))
                    batch_result_text.insert(tk.END, "\n")
                    batch_result_text.insert(tk.END, "- Claimed Grade: " + (c.claimed_grade or "Not provided"))
                    batch_result_text.insert(tk.END, "\n")
                    batch_result_text.insert(tk.END, "- Estimated Range: " + (assessment.estimated_range[0] or "Unknown") + " - " + (assessment.estimated_range[1] or "Unknown"))
                    batch_result_text.insert(tk.END, "\n")
                    batch_result_text.insert(tk.END, "- Most Likely: " + (assessment.most_likely_grade or "Unknown"))
                    batch_result_text.insert(tk.END, "\n")
                    batch_result_text.insert(tk.END, "- Recommendation: " + assessment.recommendation)
                    batch_result_text.insert(tk.END, "\n")
                    if assessment.review_flags:
                        batch_result_text.insert(tk.END, "- Flags: " + "; ".join(assessment.review_flags))
                        batch_result_text.insert(tk.END, "\n")
                    batch_result_text.insert(tk.END, "\n")

            except Exception as e:
                messagebox.showerror("Batch Assessment Error", "Batch assessment failed: " + str(e))

        batch_button_frame = ttk.Frame(batch_frame)
        batch_button_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        ttk.Button(batch_button_frame, text="Run Batch Assessment", command=run_batch_assessment).pack(side=tk.LEFT, padx=(0, 5))

        # Export buttons (shared)
        def export_assessment(format_type):
            assessment = current_assessment.get("assessment")
            if not assessment:
                messagebox.showwarning("No Assessment", "Run a single assessment before exporting.")
                return
            if format_type == "markdown":
                path = filedialog.asksaveasfilename(
                    title="Export Assessment Markdown",
                    defaultextension=".md",
                    filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
                )
                if path:
                    engine = CollectionIntelligenceEngine(self._collection_items())
                    assistant = AIGradingAssistant(engine)
                    ok = assistant.export_assessment(assessment, "markdown", path)
                    if ok:
                        messagebox.showinfo("Export Complete", "Assessment exported to " + path)
                    else:
                        messagebox.showerror("Export Failed", "Could not export assessment.")
            else:
                path = filedialog.asksaveasfilename(
                    title="Export Assessment CSV",
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                )
                if path:
                    engine = CollectionIntelligenceEngine(self._collection_items())
                    assistant = AIGradingAssistant(engine)
                    ok = assistant.export_assessment(assessment, "csv", path)
                    if ok:
                        messagebox.showinfo("Export Complete", "Assessment exported to " + path)
                    else:
                        messagebox.showerror("Export Failed", "Could not export assessment.")

        def export_batch_report(format_type):
            report = current_batch_report.get("report")
            if not report:
                messagebox.showwarning("No Report", "Run a batch assessment before exporting.")
                return
            if format_type == "markdown":
                path = filedialog.asksaveasfilename(
                    title="Export Batch Report Markdown",
                    defaultextension=".md",
                    filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
                )
                if path:
                    engine = CollectionIntelligenceEngine(self._collection_items())
                    assistant = AIGradingAssistant(engine)
                    ok = assistant.export_report(report, "markdown", path)
                    if ok:
                        messagebox.showinfo("Export Complete", "Batch report exported to " + path)
                    else:
                        messagebox.showerror("Export Failed", "Could not export batch report.")
            else:
                path = filedialog.asksaveasfilename(
                    title="Export Batch Report CSV",
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                )
                if path:
                    engine = CollectionIntelligenceEngine(self._collection_items())
                    assistant = AIGradingAssistant(engine)
                    ok = assistant.export_report(report, "csv", path)
                    if ok:
                        messagebox.showinfo("Export Complete", "Batch report exported to " + path)
                    else:
                        messagebox.showerror("Export Failed", "Could not export batch report.")

        export_frame = ttk.Frame(main_frame)
        export_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(export_frame, text="Export Single Markdown", command=lambda: export_assessment("markdown")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(export_frame, text="Export Single CSV", command=lambda: export_assessment("csv")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(export_frame, text="Export Batch Markdown", command=lambda: export_batch_report("markdown")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(export_frame, text="Export Batch CSV", command=lambda: export_batch_report("csv")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(export_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

    def open_batch_processing(self):
        """Open Batch Processing dialog.

        Provides a read-only interface for processing a folder of coin photos
        using the BatchProcessingEngine. Results are displayed for review;
        no collection mutation occurs.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Batch Processing")
        dialog.geometry("900x800")

        engine = BatchProcessingEngine()
        current_report = {"report": None}

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Folder Selection Section ---
        folder_frame = ttk.LabelFrame(main_frame, text="Folder Selection", padding="10")
        folder_frame.pack(fill=tk.X, pady=(0, 10))

        folder_var = tk.StringVar()
        ttk.Label(folder_frame, text="Photo Folder:").grid(row=0, column=0, sticky=tk.W, pady=3)
        ttk.Entry(folder_frame, textvariable=folder_var, width=60).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(8, 0), pady=3)

        def browse_folder():
            path = filedialog.askdirectory(title="Select Photo Folder")
            if path:
                folder_var.set(path)

        ttk.Button(folder_frame, text="Browse", command=browse_folder).grid(row=0, column=2, sticky=tk.W, padx=(6, 0), pady=3)
        folder_frame.columnconfigure(1, weight=1)

        # File Pattern
        pattern_var = tk.StringVar(value="*.jpg")
        ttk.Label(folder_frame, text="File Pattern:").grid(row=1, column=0, sticky=tk.W, pady=3)
        ttk.Entry(folder_frame, textvariable=pattern_var, width=20).grid(row=1, column=1, sticky=tk.W, padx=(8, 0), pady=3)

        # Auto-pair checkbox
        auto_pair_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(folder_frame, text="Auto-pair front/back photos", variable=auto_pair_var).grid(row=2, column=1, sticky=tk.W, padx=(8, 0), pady=3)

        # --- Results Display ---
        result_frame = ttk.LabelFrame(main_frame, text="Batch Processing Results", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        result_text = tk.Text(result_frame, wrap=tk.WORD, height=25)
        result_text.pack(fill=tk.BOTH, expand=True)

        # --- Button Frame ---
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def run_batch_processing():
            """Run batch processing on the selected folder."""
            try:
                folder_path = folder_var.get()
                file_pattern = pattern_var.get() or "*.jpg"
                auto_pair = auto_pair_var.get()

                if not folder_path:
                    messagebox.showwarning("No Folder", "Please select a photo folder.")
                    return

                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, "Running Batch Processing...\n")
                result_text.insert(tk.END, "Folder: " + folder_path + "\n")
                result_text.insert(tk.END, "Pattern: " + file_pattern + "\n")
                result_text.insert(tk.END, "Auto-pair: " + str(auto_pair) + "\n\n")

                # Run batch processing — read-only, no collection mutation
                collection_items = self._collection_items()
                report = engine.process_folder(
                    folder_path=folder_path,
                    collection_items=collection_items,
                    file_pattern=file_pattern,
                    auto_pair=auto_pair,
                )
                current_report["report"] = report

                # Display summary
                result_text.insert(tk.END, "=== Batch Summary ===\n")
                result_text.insert(tk.END, "Total photos: " + str(report.summary.total_photos) + "\n")
                result_text.insert(tk.END, "Processed: " + str(report.summary.processed) + "\n")
                result_text.insert(tk.END, "Failed: " + str(report.summary.failed) + "\n")
                result_text.insert(tk.END, "OCR ready: " + str(report.summary.ocr_ready) + "\n")
                result_text.insert(tk.END, "Review ready: " + str(report.summary.review_ready) + "\n")
                result_text.insert(tk.END, "Duplicates detected: " + str(report.summary.duplicates_detected) + "\n")
                result_text.insert(tk.END, "Upgrade opportunities: " + str(report.summary.upgrade_opportunities) + "\n")
                result_text.insert(tk.END, "Gap opportunities: " + str(report.summary.gap_opportunities) + "\n\n")

                # Display review summary
                review = report.review_summary()
                result_text.insert(tk.END, "=== Review Summary ===\n")
                result_text.insert(tk.END, "Total candidates: " + str(review["total_candidates"]) + "\n")
                result_text.insert(tk.END, "Reviewable: " + str(review["reviewable"]) + "\n")
                result_text.insert(tk.END, "Approved: " + str(review["approved"]) + "\n")
                result_text.insert(tk.END, "Rejected: " + str(review["rejected"]) + "\n")
                result_text.insert(tk.END, "Needs review: " + str(review["needs_review"]) + "\n")
                result_text.insert(tk.END, "Unreviewed: " + str(review["unreviewed"]) + "\n")
                result_text.insert(tk.END, "Completion: " + str(round(review["review_completion_pct"], 1)) + "%\n\n")

                # Display candidates
                if report.candidates:
                    result_text.insert(tk.END, "=== Candidates ===\n")
                    for c in report.candidates:
                        result_text.insert(tk.END, c.candidate_id + ": " + c.subject + " — " + c.status.value + " / " + c.review_status.value + "\n")
                        if c.warnings:
                            result_text.insert(tk.END, "  Warnings: " + ", ".join(c.warnings) + "\n")
                        if c.errors:
                            result_text.insert(tk.END, "  Errors: " + ", ".join(c.errors) + "\n")
                        result_text.insert(tk.END, "\n")
                else:
                    result_text.insert(tk.END, "No candidates generated.\n")

                result_text.insert(tk.END, "\nBatch processing complete. Use Export buttons to save the report.\n")

            except Exception as e:
                messagebox.showerror("Batch Processing Error", str(e))
                result_text.insert(tk.END, "\nError: " + str(e) + "\n")

        def export_csv():
            """Export batch report to CSV."""
            report = current_report["report"]
            if not report:
                messagebox.showwarning("No Report", "Run batch processing first.")
                return
            path = filedialog.asksaveasfilename(
                title="Export CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")],
            )
            if path:
                report.export_csv(path)
                messagebox.showinfo("Export Complete", "CSV saved to " + path)

        def export_markdown():
            """Export batch report to Markdown."""
            report = current_report["report"]
            if not report:
                messagebox.showwarning("No Report", "Run batch processing first.")
                return
            path = filedialog.asksaveasfilename(
                title="Export Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md")],
            )
            if path:
                report.export_markdown(path)
                messagebox.showinfo("Export Complete", "Markdown saved to " + path)

        ttk.Button(button_frame, text="Run Batch Processing", command=run_batch_processing).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Export CSV", command=export_csv).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Export Markdown", command=export_markdown).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

    def open_collector_workspace(self):
        """Open Collector Workspace dialog with notebook tabs for all panels.

        Read-only display. All mutation flows through 'Open in Tool...' buttons.
        """
        from collector_workspace import (
            DashboardReport,
            InboxReport,
            CollectionSummaryReport,
            WantListReport,
            OpportunitiesReport,
            AIQueueReport,
            BatchQueueReport,
            PhotoVaultReport,
            WorkflowStatusReport,
            DataSafetyReport,
            ReportsMenu,
        )

        workspace = CollectorWorkspace(
            self._collection_items(),
            want_list_intents=self._active_want_list_intents(),
            photo_records=self.photo_records,
            shopping_candidates=self.shopping_candidates,
            market_awareness_engine=self.market_awareness_engine,
            photo_candidates=getattr(self, "photo_candidates", None),
            watchlists=getattr(self, "watchlists", None),
            ocr_reports=getattr(self, "ocr_reports", None),
            workflow_statuses=getattr(self, "workflow_statuses", None),
            acknowledged_action_ids=getattr(self, "acknowledged_action_ids", None),
            **self._workspace_reference_configuration(),
        )

        dialog = tk.Toplevel(self.root)
        dialog.title("Collector Workspace")
        dialog.geometry("1000x800")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Notebook with tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        tabs = self._create_workspace_tabs(notebook, workspace)

        # Button bar
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def refresh_workspace():
            workspace.refresh()
            self._refresh_workspace_tabs(tabs, workspace)

        ttk.Button(button_frame, text="Refresh Workspace", command=refresh_workspace).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT)

    def _create_workspace_tabs(self, notebook, workspace):
        """Create all workspace tabs. Returns dict of tab widgets for refresh."""
        tabs = {}
        tabs["dashboard"] = self._create_dashboard_tab(notebook, workspace)
        tabs["inbox"] = self._create_inbox_tab(notebook, workspace)
        tabs["collection"] = self._create_collection_tab(notebook, workspace)
        tabs["want_list"] = self._create_want_list_tab(notebook, workspace)
        tabs["opportunities"] = self._create_opportunities_tab(notebook, workspace)
        tabs["ai_queue"] = self._create_ai_queue_tab(notebook, workspace)
        tabs["batch_queue"] = self._create_batch_queue_tab(notebook, workspace)
        tabs["photo_vault"] = self._create_photo_vault_tab(notebook, workspace)
        tabs["image_readiness"] = self._create_image_readiness_tab(notebook, workspace)
        tabs["canadian_references"] = self._create_canadian_references_tab(notebook, workspace)
        tabs["workflow"] = self._create_workflow_tab(notebook, workspace)
        tabs["data_safety"] = self._create_data_safety_tab(notebook, workspace)
        tabs["connected_data"] = self._create_connected_data_tab(notebook, workspace)
        tabs["reports"] = self._create_reports_tab(notebook, workspace)
        return tabs

    def _create_dashboard_tab(self, notebook, workspace):
        """Create Dashboard tab."""
        frame = ttk.Frame(notebook, padding="10")
        notebook.add(frame, text="Dashboard")
        text = tk.Text(frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        report = workspace.get_dashboard()
        text.insert(tk.END, self._format_dashboard(report))
        text.config(state=tk.DISABLED)
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(button_frame, text="Open in Collector Home", command=self.open_collector_home).pack(side=tk.LEFT, padx=(0, 6))
        return {"frame": frame, "text": text}

    def _create_inbox_tab(self, notebook, workspace):
        """Create Inbox tab."""
        frame = ttk.Frame(notebook, padding="10")
        notebook.add(frame, text="Inbox")
        text = tk.Text(frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        report = workspace.get_inbox()
        text.insert(tk.END, self._format_inbox(report))
        text.config(state=tk.DISABLED)
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(button_frame, text="Open in Collection Assistant", command=self.open_collection_assistant).pack(side=tk.LEFT, padx=(0, 6))
        return {"frame": frame, "text": text}

    def _create_collection_tab(self, notebook, workspace):
        """Create Collection tab."""
        frame = ttk.Frame(notebook, padding="10")
        notebook.add(frame, text="Collection")
        text = tk.Text(frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        report = workspace.get_collection_summary()
        text.insert(tk.END, self._format_collection_summary(report))
        text.config(state=tk.DISABLED)
        return {"frame": frame, "text": text}

    def _create_want_list_tab(self, notebook, workspace):
        """Create Want List tab."""
        frame = ttk.Frame(notebook, padding="10")
        notebook.add(frame, text="Want List")
        text = tk.Text(frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        report = workspace.get_want_list()
        text.insert(tk.END, self._format_want_list(report))
        text.config(state=tk.DISABLED)
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(button_frame, text="Open in Want List Generator", command=self.open_want_list_generator).pack(side=tk.LEFT, padx=(0, 6))
        return {"frame": frame, "text": text}

    def _create_opportunities_tab(self, notebook, workspace):
        """Create Opportunities tab."""
        frame = ttk.Frame(notebook, padding="10")
        notebook.add(frame, text="Opportunities")
        text = tk.Text(frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        report = workspace.get_opportunities()
        text.insert(tk.END, self._format_opportunities(report))
        text.config(state=tk.DISABLED)
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(button_frame, text="Open in Smart Shopping", command=self.open_smart_shopping_assistant).pack(side=tk.LEFT, padx=(0, 6))
        return {"frame": frame, "text": text}

    def _create_ai_queue_tab(self, notebook, workspace):
        """Create AI Queue tab."""
        frame = ttk.Frame(notebook, padding="10")
        notebook.add(frame, text="AI Queue")
        text = tk.Text(frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        report = workspace.get_ai_queue()
        text.insert(tk.END, self._format_ai_queue(report))
        text.config(state=tk.DISABLED)
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(button_frame, text="Open in AI Grading Assistant", command=self.open_ai_grading_assistant).pack(side=tk.LEFT, padx=(0, 6))
        return {"frame": frame, "text": text}

    def _create_batch_queue_tab(self, notebook, workspace):
        """Create Batch Queue tab."""
        frame = ttk.Frame(notebook, padding="10")
        notebook.add(frame, text="Batch Queue")
        text = tk.Text(frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        report = workspace.get_batch_queue()
        text.insert(tk.END, self._format_batch_queue(report))
        text.config(state=tk.DISABLED)
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(button_frame, text="Open in Batch Processing", command=self.open_batch_processing).pack(side=tk.LEFT, padx=(0, 6))
        return {"frame": frame, "text": text}

    def _create_photo_vault_tab(self, notebook, workspace):
        """Create Photo Vault tab."""
        frame = ttk.Frame(notebook, padding="10")
        notebook.add(frame, text="Photo Vault")
        text = tk.Text(frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        report = workspace.get_photo_vault()
        text.insert(tk.END, self._format_photo_vault(report))
        text.config(state=tk.DISABLED)
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(button_frame, text="Open in Photo Vault Audit", command=self.open_photo_vault_audit).pack(side=tk.LEFT, padx=(0, 6))
        return {"frame": frame, "text": text}

    def _create_image_readiness_tab(self, notebook, workspace):
        """Create read-only Image Readiness workspace tab."""
        frame = ttk.Frame(notebook, padding="10")
        notebook.add(frame, text="Image Readiness")

        item_options = self._image_readiness_item_options()
        item_var = tk.StringVar(value=item_options[0][0] if item_options else "")
        certified_var = tk.BooleanVar(value=False)

        controls = ttk.Frame(frame)
        controls.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(controls, text="Item:").pack(side=tk.LEFT, padx=(0, 4))
        item_combo = ttk.Combobox(
            controls,
            textvariable=item_var,
            values=[label for label, _item_id in item_options],
            state="readonly",
            width=48,
        )
        item_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Checkbutton(controls, text="Certified item", variable=certified_var).pack(side=tk.LEFT, padx=(0, 6))

        body = ttk.Frame(frame)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(1, weight=1)

        ttk.Label(body, text="Overall").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(body, text="Assessment Details").grid(row=0, column=1, sticky=tk.W, padx=(8, 0))

        text = tk.Text(body, wrap=tk.WORD, padx=10, pady=10, height=22)
        text.grid(row=1, column=0, sticky=tk.NSEW, pady=(2, 0))
        details_text = tk.Text(body, wrap=tk.WORD, padx=10, pady=10, height=22)
        details_text.grid(row=1, column=1, sticky=tk.NSEW, padx=(8, 0), pady=(2, 0))

        ttk.Label(body, text="Photo List").grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(8, 0))
        photo_listbox = tk.Listbox(body, height=5, exportselection=False)
        photo_listbox.grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=(2, 0))

        tab = {
            "frame": frame,
            "text": text,
            "details_text": details_text,
            "photo_listbox": photo_listbox,
            "item_var": item_var,
            "certified_var": certified_var,
            "item_options": item_options,
            "current_report": None,
        }

        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(button_frame, text="Assess", command=lambda: self._assess_image_readiness_tab(tab, workspace)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Refresh Assessment", command=lambda: self._refresh_image_readiness_tab(tab, workspace)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=lambda: self._export_image_readiness_markdown(tab)).pack(side=tk.LEFT, padx=(0, 6))

        photo_listbox.bind("<<ListboxSelect>>", lambda _event: self._update_image_readiness_photo_detail(tab))
        self._assess_image_readiness_tab(tab, workspace)
        return tab

    def _create_canadian_references_tab(self, notebook, workspace):
        """Create the read-only Canadian reference research tab."""
        frame = ttk.Frame(notebook, padding="10")
        notebook.add(frame, text="Canadian References")

        mode_var = tk.StringVar(value="issue_id")
        issue_id_var = tk.StringVar()
        query_vars = {
            key: tk.StringVar()
            for key in ("text", "country", "denomination", "year", "authority", "mintmark", "variety")
        }
        filter_vars = {
            key: tk.StringVar()
            for key in ("country", "denomination", "year", "authority", "monarch", "series")
        }

        mode_frame = ttk.Frame(frame)
        mode_frame.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(mode_frame, text="Research mode:").pack(side=tk.LEFT, padx=(0, 6))

        forms = ttk.Frame(frame)
        forms.pack(fill=tk.X, pady=(0, 8))
        issue_form = ttk.Frame(forms)
        search_form = ttk.Frame(forms)
        filter_form = ttk.Frame(forms)

        ttk.Label(issue_form, text="Issue ID:").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(issue_form, textvariable=issue_id_var, width=42).pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._add_canadian_reference_fields(search_form, query_vars)
        self._add_canadian_reference_fields(filter_form, filter_vars)

        tab = {
            "frame": frame,
            "mode_var": mode_var,
            "issue_id_var": issue_id_var,
            "query_vars": query_vars,
            "filter_vars": filter_vars,
            "forms": {
                "issue_id": issue_form,
                "query": search_form,
                "filters": filter_form,
            },
            "current_report": None,
            "current_request": None,
            "tree_groups": {},
        }

        def switch_mode():
            self._show_canadian_reference_mode(tab)

        for value, label in (
            ("issue_id", "Exact Issue ID"),
            ("query", "Search"),
            ("filters", "Filter / List"),
        ):
            ttk.Radiobutton(
                mode_frame,
                text=label,
                value=value,
                variable=mode_var,
                command=switch_mode,
            ).pack(side=tk.LEFT, padx=(0, 6))

        summary_var = tk.StringVar()
        ttk.Label(frame, textvariable=summary_var).pack(fill=tk.X, pady=(0, 6))
        tab["summary_var"] = summary_var

        body = ttk.PanedWindow(frame, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)

        results_frame = ttk.Frame(body)
        details_frame = ttk.Frame(body)
        body.add(results_frame, weight=1)
        body.add(details_frame, weight=2)

        ttk.Label(results_frame, text="Issue Groups and Records").pack(anchor=tk.W)
        result_tree = ttk.Treeview(results_frame, show="tree", selectmode="browse")
        result_tree.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
        tab["result_tree"] = result_tree

        ttk.Label(details_frame, text="Reference Details").pack(anchor=tk.W)
        detail_notebook = ttk.Notebook(details_frame)
        detail_notebook.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
        for key, label in (
            ("records_text", "Records"),
            ("claims_text", "Claims"),
            ("conflicts_text", "Conflicts"),
            ("diagnostics_text", "Diagnostics"),
        ):
            detail_tab = ttk.Frame(detail_notebook)
            detail_notebook.add(detail_tab, text=label)
            text = tk.Text(detail_tab, wrap=tk.WORD, padx=10, pady=10)
            text.pack(fill=tk.BOTH, expand=True)
            text.config(state=tk.DISABLED)
            tab[key] = text

        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(button_frame, text="Run", command=lambda: self._run_canadian_references_tab(tab, workspace)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Refresh", command=lambda: self._refresh_canadian_references_tab(tab, workspace)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Export Markdown", command=lambda: self._export_canadian_references_markdown(tab)).pack(side=tk.LEFT, padx=(0, 6))

        result_tree.bind("<<TreeviewSelect>>", lambda _event: self._update_canadian_reference_detail(tab))
        self._show_canadian_reference_mode(tab)
        self._render_canadian_reference_prompt(tab)
        return tab

    @staticmethod
    def _add_canadian_reference_fields(parent, variables):
        """Add compact, explicit reference request fields to a form row."""
        for key, variable in variables.items():
            label = key.replace("_", " ").title()
            ttk.Label(parent, text=f"{label}:").pack(side=tk.LEFT, padx=(0, 3))
            ttk.Entry(parent, textvariable=variable, width=12).pack(side=tk.LEFT, padx=(0, 6))

    @staticmethod
    def _workspace_reference_configuration_for(aggregator, providers):
        """Return one explicit workspace reference dependency, if application-owned."""
        if aggregator is not None and providers is not None:
            raise ValueError("Provide reference_provider_aggregator or reference_providers, not both.")
        if aggregator is not None:
            return {"reference_provider_aggregator": aggregator}
        if providers is not None:
            return {"reference_providers": providers}
        return {}

    def _workspace_reference_configuration(self):
        """Expose only already-owned reference dependencies to the workspace."""
        return self._workspace_reference_configuration_for(
            getattr(self, "reference_provider_aggregator", None),
            getattr(self, "reference_providers", None),
        )

    def _show_canadian_reference_mode(self, tab):
        """Show only the explicit request controls for the active research mode."""
        active_mode = tab["mode_var"].get()
        for mode, form in tab.get("forms", {}).items():
            if mode == active_mode:
                form.pack(fill=tk.X)
            else:
                form.pack_forget()

    @staticmethod
    def _canadian_reference_request(tab):
        """Build one approved request mode without collection-derived input."""
        mode = tab["mode_var"].get()
        if mode == "issue_id":
            return {"issue_id": tab["issue_id_var"].get().strip()}
        if mode == "query":
            return {
                "query": ReferenceQuery(
                    **{key: variable.get().strip() for key, variable in tab["query_vars"].items()}
                )
            }
        return {
            "filters": ReferenceFilters(
                **{key: variable.get().strip() for key, variable in tab["filter_vars"].items()}
            )
        }

    def _run_canadian_references_tab(self, tab, workspace, refresh=False):
        """Run one explicit, read-only reference request through the workspace."""
        request = self._canadian_reference_request(tab)
        tab["current_request"] = dict(request)
        self._execute_canadian_reference_request(tab, workspace, request, refresh=refresh)

    def _execute_canadian_reference_request(self, tab, workspace, request, refresh=False):
        """Execute one already-explicit request through the workspace only."""
        request = dict(request)
        if refresh:
            request = {**request, "refresh": True}
        try:
            report = workspace.get_canadian_references(**request)
        except Exception as exc:
            self._render_canadian_reference_failure(tab, f"Canadian References: {exc}")
            return
        tab["current_report"] = report
        self._render_canadian_reference_report(tab, report)

    def _refresh_canadian_references_tab(self, tab, workspace):
        """Refresh the workspace then repeat the current explicit request only."""
        workspace.refresh()
        if tab.get("current_request") is None:
            self._render_canadian_reference_prompt(tab)
            return
        self._execute_canadian_reference_request(
            tab,
            workspace,
            tab["current_request"],
            refresh=True,
        )

    def _rerun_canadian_references_tab(self, tab, workspace):
        """Re-render an active request after a workspace-wide refresh."""
        if tab.get("current_request") is None:
            self._render_canadian_reference_prompt(tab)
            return
        self._execute_canadian_reference_request(
            tab,
            workspace,
            tab["current_request"],
            refresh=True,
        )

    def _export_canadian_references_markdown(self, tab):
        """Export only the currently displayed report using its existing exporter."""
        report = tab.get("current_report")
        if report is None:
            messagebox.showwarning("Canadian References", "Run a reference request before exporting.")
            return
        path = filedialog.asksaveasfilename(
            title="Export Canadian Reference Claims",
            defaultextension=".md",
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            ok = report.export_markdown(path)
            if ok:
                messagebox.showinfo("Export Complete", f"Saved to {path}")
            else:
                messagebox.showerror("Export Failed", "Export returned False")
        except Exception as exc:
            messagebox.showerror("Export Failed", str(exc))

    def _render_canadian_reference_prompt(self, tab):
        """Render the quiet initial state without performing a provider request."""
        tab["current_report"] = None
        self._clear_canadian_reference_tree(tab)
        summary_var = tab.get("summary_var")
        if summary_var is not None:
            summary_var.set("Enter an exact issue ID, search terms, or filters to research configured reference data.")
        self._set_canadian_reference_detail_texts(
            tab,
            "No request has been run.",
            "No source claims available.",
            "No source disagreements available.",
            "No diagnostics available.",
        )

    def _render_canadian_reference_failure(self, tab, message):
        """Keep unexpected GUI-facing failures concise and non-destructive."""
        self._clear_canadian_reference_tree(tab)
        summary_var = tab.get("summary_var")
        if summary_var is not None:
            summary_var.set("Canadian References could not complete this request.")
        self._set_canadian_reference_detail_texts(
            tab,
            "No records available.",
            "No source claims available.",
            "No source disagreements available.",
            message,
        )

    def _render_canadian_reference_report(self, tab, report):
        """Render Phase 5 report DTOs without interpreting their claims."""
        payload = self._canadian_reference_report_payload(report)
        summary = payload.get("summary") or {}
        groups = ((payload.get("aggregate_result") or {}).get("groups") or [])
        summary_var = tab.get("summary_var")
        if summary_var is not None:
            summary_var.set(
                "Request: {0} | Providers: {1} | Groups: {2} | Claims: {3} | Conflicts: {4}".format(
                    payload.get("selection_type") or "none",
                    summary.get("provider_count", len(payload.get("provider_ids") or [])),
                    summary.get("group_count", len(groups)),
                    summary.get("claim_count", 0),
                    summary.get("conflict_count", 0),
                )
            )
        self._populate_canadian_reference_tree(tab, groups)
        if groups:
            self._select_first_canadian_reference_group(tab)
        else:
            self._set_canadian_reference_detail_texts(
                tab,
                "No source records were returned for this request.",
                "No source claims were returned for this request.",
                "No source disagreements reported for this request.",
                self._format_canadian_reference_diagnostics(payload),
            )

    @staticmethod
    def _canadian_reference_report_payload(report):
        return report.to_dict() if hasattr(report, "to_dict") else dict(report or {})

    def _clear_canadian_reference_tree(self, tab):
        tree = tab.get("result_tree")
        if tree is not None:
            children = tree.get_children()
            if children:
                tree.delete(*children)
        tab["tree_groups"] = {}

    def _populate_canadian_reference_tree(self, tab, groups):
        self._clear_canadian_reference_tree(tab)
        tree = tab.get("result_tree")
        if tree is None:
            return
        for group_index, group in enumerate(groups):
            records = group.get("records") or []
            claims = group.get("claims") or []
            conflicts = group.get("conflicts") or []
            issue_key = group.get("issue_key") or "Unspecified issue"
            group_id = tree.insert(
                "",
                tk.END,
                text=f"{issue_key} ({len(records)} records, {len(claims)} claims, {len(conflicts)} conflicts)",
            )
            tab["tree_groups"][group_id] = group_index
            for record in records:
                issue = record.get("issue") or {}
                source = record.get("source") or {}
                label = source.get("source_name") or source.get("source_id") or "Source"
                record_id = record.get("source_record_id") or "N/A"
                child_id = tree.insert(
                    group_id,
                    tk.END,
                    text=f"{label} | {record_id} | {issue.get('issue_id') or issue_key}",
                )
                tab["tree_groups"][child_id] = group_index

    def _select_first_canadian_reference_group(self, tab):
        tree = tab.get("result_tree")
        if tree is None:
            return
        groups = tree.get_children()
        if groups:
            tree.selection_set(groups[0])
            tree.focus(groups[0])
        self._update_canadian_reference_detail(tab)

    def _update_canadian_reference_detail(self, tab):
        report = tab.get("current_report")
        if report is None:
            return
        payload = self._canadian_reference_report_payload(report)
        groups = ((payload.get("aggregate_result") or {}).get("groups") or [])
        tree = tab.get("result_tree")
        selection = tree.selection() if tree is not None else ()
        selected_id = selection[0] if selection else ""
        group_index = tab.get("tree_groups", {}).get(selected_id, 0)
        group = groups[group_index] if groups and group_index < len(groups) else None
        self._set_canadian_reference_detail_texts(
            tab,
            self._format_canadian_reference_records(group),
            self._format_canadian_reference_claims(group),
            self._format_canadian_reference_conflicts(group),
            self._format_canadian_reference_diagnostics(payload),
        )

    def _set_canadian_reference_detail_texts(self, tab, records, claims, conflicts, diagnostics):
        for key, content in (
            ("records_text", records),
            ("claims_text", claims),
            ("conflicts_text", conflicts),
            ("diagnostics_text", diagnostics),
        ):
            widget = tab.get(key)
            if widget is not None:
                self._set_text_widget(widget, content)

    @staticmethod
    def _format_canadian_reference_records(group):
        if not group:
            return "Select an issue group to view source records.\n"
        lines = ["Source Records", "=" * 40]
        records = group.get("records") or []
        if not records:
            return "\n".join(lines + ["", "No source records available."]) + "\n"
        for record in records:
            issue = record.get("issue") or {}
            source = record.get("source") or {}
            lines.extend([
                "",
                f"Issue ID: {issue.get('issue_id') or 'N/A'}",
                f"Source: {source.get('source_name') or source.get('source_id') or 'N/A'}",
                f"Source record: {record.get('source_record_id') or 'N/A'}",
                f"Country: {issue.get('country') or 'N/A'}",
                f"Denomination: {issue.get('denomination') or 'N/A'}",
                f"Year / Date: {issue.get('year') or issue.get('date_text') or 'N/A'}",
                f"Authority: {issue.get('authority') or 'N/A'}",
                f"Mintmark: {issue.get('mintmark') or 'N/A'}",
                f"Variety: {issue.get('variety') or 'N/A'}",
                f"Composition: {issue.get('composition') or 'N/A'}",
                f"Weight: {issue.get('weight') or 'N/A'}",
                f"Diameter: {issue.get('diameter') or 'N/A'}",
                f"Catalogue IDs: {issue.get('catalogue_numbers') or 'N/A'}",
                f"Source type: {source.get('source_type') or 'N/A'}",
                f"Attribution: {source.get('attribution') or 'N/A'}",
                f"Licence: {source.get('licence') or 'N/A'}",
                f"Source URL: {source.get('url') or 'N/A'}",
            ])
            for warning in record.get("warnings") or []:
                lines.append(f"Warning: {warning}")
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _format_canadian_reference_claims(group):
        if not group:
            return "Select an issue group to view source claims.\n"
        lines = ["Source Claims", "=" * 40]
        claims = group.get("claims") or []
        if not claims:
            return "\n".join(lines + ["", "No source claims available."]) + "\n"
        for claim in claims:
            source = claim.get("source") or {}
            source_ref = claim.get("source_ref") or {}
            lines.extend([
                "",
                f"Field: {claim.get('field_name') or 'N/A'}",
                f"Raw value: {claim.get('raw_value') or 'N/A'}",
                f"Normalized value: {claim.get('normalized_value') or 'N/A'}",
                f"Provider: {claim.get('provider_id') or 'N/A'}",
                f"Source: {source.get('source_name') or source.get('source_id') or 'N/A'}",
                f"Source record: {claim.get('source_record_id') or 'N/A'}",
            ])
            if source_ref:
                lines.extend([
                    f"Field reference: {source_ref.get('field_name') or 'N/A'}",
                    f"Reference notes: {source_ref.get('notes') or 'N/A'}",
                ])
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _format_canadian_reference_conflicts(group):
        if not group:
            return "Select an issue group to view source disagreements.\n"
        lines = ["Source Disagreements", "=" * 40]
        conflicts = group.get("conflicts") or []
        if not conflicts:
            return "\n".join(lines + ["", "No source disagreements reported for this request."]) + "\n"
        for conflict in conflicts:
            lines.extend([
                "",
                f"Issue key: {conflict.get('issue_key') or 'N/A'}",
                f"Field: {conflict.get('field_name') or 'N/A'}",
                f"Type: {conflict.get('conflict_type') or 'N/A'}",
            ])
            if conflict.get("notes"):
                lines.append(f"Notes: {conflict['notes']}")
            for claim in conflict.get("claims") or []:
                source = claim.get("source") or {}
                lines.append(
                    "- {0}: raw={1}; normalized={2}; provider={3}; source={4}; record={5}".format(
                        claim.get("field_name") or "N/A",
                        claim.get("raw_value") or "N/A",
                        claim.get("normalized_value") or "N/A",
                        claim.get("provider_id") or "N/A",
                        source.get("source_name") or source.get("source_id") or "N/A",
                        claim.get("source_record_id") or "N/A",
                    )
                )
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _format_canadian_reference_diagnostics(payload):
        lines = ["Diagnostics", "=" * 40]
        result = payload.get("aggregate_result") or {}
        validation = payload.get("validation_report") or {}
        provider_errors = list(result.get("provider_errors") or []) + list(validation.get("provider_errors") or [])
        warnings = list(result.get("warnings") or [])
        findings = validation.get("findings") or []
        engine_errors = payload.get("engine_errors") or []
        if not (provider_errors or warnings or findings or engine_errors):
            return "\n".join(lines + ["", "No diagnostics reported."]) + "\n"
        for error in provider_errors:
            lines.append(f"Provider error [{error.get('provider_id') or 'Provider'}]: {error.get('message') or 'Unknown error'}")
        for warning in warnings:
            lines.append(f"Warning: {warning}")
        for finding in findings:
            lines.append(
                "Validation [{0}] {1}: {2}".format(
                    finding.get("severity") or "INFO",
                    finding.get("code") or "FINDING",
                    finding.get("message") or "",
                )
            )
        for error in engine_errors:
            lines.append(f"Workspace: {error}")
        return "\n".join(lines).rstrip() + "\n"

    def _create_workflow_tab(self, notebook, workspace):
        """Create Workflow tab."""
        frame = ttk.Frame(notebook, padding="10")
        notebook.add(frame, text="Workflow")
        text = tk.Text(frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        report = workspace.get_workflows()
        text.insert(tk.END, self._format_unified_workflow(report))
        text.config(state=tk.DISABLED)
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(6, 0))
        tab = {"frame": frame, "text": text, "button_frame": button_frame}
        self._render_workflow_tool_buttons(
            tab,
            report,
            lambda: self._refresh_workflow_tab(tab, workspace),
        )
        return tab

    def _create_data_safety_tab(self, notebook, workspace):
        """Create Data Safety tab."""
        frame = ttk.Frame(notebook, padding="10")
        notebook.add(frame, text="Data Safety")
        text = tk.Text(frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        report = workspace.get_data_safety()
        text.insert(tk.END, self._format_data_safety(report))
        text.config(state=tk.DISABLED)
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(button_frame, text="Open in Sync & Backup", command=self.open_sync_backup).pack(side=tk.LEFT, padx=(0, 6))
        return {"frame": frame, "text": text}

    def _create_connected_data_tab(self, notebook, workspace):
        """Create Connected Data tab."""
        frame = ttk.Frame(notebook, padding="10")
        notebook.add(frame, text="Connected Data")
        text = tk.Text(frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        report = workspace.get_connected_data()
        text.insert(tk.END, self._format_connected_data(report))
        text.config(state=tk.DISABLED)
        return {"frame": frame, "text": text}

    def _create_reports_tab(self, notebook, workspace):
        """Create Reports tab with list and export buttons."""
        frame = ttk.Frame(notebook, padding="10")
        notebook.add(frame, text="Reports")

        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        menu = workspace.get_reports()
        for category in menu.categories:
            ttk.Label(
                scroll_frame, text=category, font=("TkDefaultFont", 10, "bold")
            ).pack(anchor=tk.W, pady=(12, 2))
            for report in menu.by_category(category):
                row = ttk.Frame(scroll_frame)
                row.pack(fill=tk.X, pady=1)
                status = "✓" if report.available else "✗"
                ttk.Label(row, text=f"  {status} {report.title}").pack(side=tk.LEFT)
                if report.available:
                    ttk.Button(
                        row, text="Generate",
                        command=lambda r=report: self._generate_report_dialog(workspace, r),
                    ).pack(side=tk.RIGHT, padx=(6, 0))
                    if report.has_markdown_export:
                        ttk.Button(
                            row, text="MD",
                            command=lambda r=report: self._export_report_dialog(workspace, r, "markdown"),
                        ).pack(side=tk.RIGHT, padx=(6, 0))
                    if report.has_csv_export:
                        ttk.Button(
                            row, text="CSV",
                            command=lambda r=report: self._export_report_dialog(workspace, r, "csv"),
                        ).pack(side=tk.RIGHT, padx=(6, 0))
                else:
                    ttk.Label(row, text="(unavailable)").pack(side=tk.RIGHT, padx=(6, 0))

        return {"frame": frame, "text": None, "canvas": canvas}

    def _generate_report_dialog(self, workspace, descriptor):
        """Generate a report and show it in a simple text dialog."""
        result = workspace.generate_report(descriptor.name)
        if result.get("error"):
            messagebox.showerror("Report Error", result.get("reason", "Unknown error"))
            return
        dialog = tk.Toplevel(self.root)
        dialog.title(descriptor.title)
        dialog.geometry("800x600")
        text = tk.Text(dialog, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, str(result))
        text.config(state=tk.DISABLED)
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=(0, 10))

    def _export_report_dialog(self, workspace, descriptor, format):
        """Export a report to a file chosen by the user."""
        ext = ".md" if format == "markdown" else ".csv"
        filetypes = [("Markdown files", "*.md")] if format == "markdown" else [("CSV files", "*.csv")]
        path = filedialog.asksaveasfilename(
            title=f"Export {descriptor.title}",
            defaultextension=ext,
            filetypes=filetypes + [("All files", "*.*")],
        )
        if not path:
            return
        try:
            ok = workspace.export_report(descriptor.name, format, path)
            if ok:
                messagebox.showinfo("Export Complete", f"Saved to {path}")
            else:
                messagebox.showerror("Export Failed", "Export returned False")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))

    def _refresh_workspace_tabs(self, tabs, workspace):
        """Refresh all tab content after workspace.refresh()."""
        panel_methods = {
            "dashboard": (workspace.get_dashboard, self._format_dashboard),
            "inbox": (workspace.get_inbox, self._format_inbox),
            "collection": (workspace.get_collection_summary, self._format_collection_summary),
            "want_list": (workspace.get_want_list, self._format_want_list),
            "opportunities": (workspace.get_opportunities, self._format_opportunities),
            "ai_queue": (workspace.get_ai_queue, self._format_ai_queue),
            "batch_queue": (workspace.get_batch_queue, self._format_batch_queue),
            "photo_vault": (workspace.get_photo_vault, self._format_photo_vault),
            "workflow": (workspace.get_workflows, self._format_unified_workflow),
            "data_safety": (workspace.get_data_safety, self._format_data_safety),
            "connected_data": (workspace.get_connected_data, self._format_connected_data),
        }
        for key, (getter, formatter) in panel_methods.items():
            text = tabs[key]["text"]
            report = getter()
            text.config(state=tk.NORMAL)
            text.delete("1.0", tk.END)
            text.insert(tk.END, formatter(report))
            text.config(state=tk.DISABLED)
            if key == "workflow":
                self._render_workflow_tool_buttons(
                    tabs[key],
                    report,
                    lambda tab=tabs[key]: self._refresh_workflow_tab(tab, workspace),
                )
        if "image_readiness" in tabs:
            self._assess_image_readiness_tab(tabs["image_readiness"], workspace)
        if "canadian_references" in tabs:
            self._rerun_canadian_references_tab(tabs["canadian_references"], workspace)
        # Reports tab is rebuilt from scratch
        old_reports = tabs["reports"]["frame"]
        parent = old_reports.master
        old_reports.destroy()
        tabs["reports"] = self._create_reports_tab(parent, workspace)

    def _image_readiness_item_options(self):
        """Return collector-facing item labels for items with attached photos."""
        options = []
        for item in self._collection_items():
            if self._item_has_image_readiness_photos(item):
                options.append((self._image_readiness_item_label(item), str(getattr(item, "id", "") or "")))
        return options

    @staticmethod
    def _item_has_image_readiness_photos(item):
        photos = getattr(item, "photos", []) or []
        if photos:
            return True
        return bool(str(getattr(item, "image_path", "") or "").strip())

    @staticmethod
    def _image_readiness_item_label(item):
        parts = [
            str(getattr(item, "year", "") or "").strip(),
            str(getattr(item, "country", "") or "").strip(),
            str(getattr(item, "denomination", "") or "").strip(),
            str(getattr(item, "grade", "") or "").strip(),
        ]
        label = " ".join(part for part in parts if part)
        item_id = str(getattr(item, "id", "") or "").strip()
        if not label:
            label = item_id or "Untitled item"
        return f"{label} [{item_id}]" if item_id else label

    @staticmethod
    def _image_readiness_selected_item_id(tab):
        selected = tab.get("item_var").get() if tab.get("item_var") else ""
        for label, item_id in tab.get("item_options", []):
            if label == selected:
                return item_id
        return ""

    def _assess_image_readiness_tab(self, tab, workspace, refresh=False):
        """Assess the selected item and render the read-only Image Readiness tab."""
        item_id = self._image_readiness_selected_item_id(tab)
        if not item_id:
            report = workspace.get_image_assessment()
        else:
            report = workspace.get_image_assessment(
                item_id=item_id,
                certified_expected=bool(tab.get("certified_var").get()),
                refresh=bool(refresh),
            )
        tab["current_report"] = report
        self._set_text_widget(tab["text"], self._format_image_readiness(report))
        self._populate_image_readiness_photo_list(tab, report)
        self._update_image_readiness_photo_detail(tab)

    def _refresh_image_readiness_tab(self, tab, workspace):
        """Refresh Image Readiness through the workspace lifecycle."""
        workspace.refresh()
        self._assess_image_readiness_tab(tab, workspace, refresh=True)

    def _export_image_readiness_markdown(self, tab):
        """Export the current Image Readiness report using the report markdown exporter."""
        report = tab.get("current_report")
        if report is None:
            messagebox.showwarning("Image Readiness", "No image readiness report is available to export.")
            return
        path = filedialog.asksaveasfilename(
            title="Export Image Readiness",
            defaultextension=".md",
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            ok = report.export_markdown(path)
            if ok:
                messagebox.showinfo("Export Complete", f"Saved to {path}")
            else:
                messagebox.showerror("Export Failed", "Export returned False")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))

    @staticmethod
    def _set_text_widget(widget, content):
        widget.config(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, content)
        widget.config(state=tk.DISABLED)

    def _populate_image_readiness_photo_list(self, tab, report):
        listbox = tab.get("photo_listbox")
        if listbox is None:
            return
        listbox.delete(0, tk.END)
        for index, assessment in enumerate(self._image_readiness_photo_assessments(report), start=1):
            path = getattr(assessment, "path", "") or ""
            label = os.path.basename(path) or path or "Photo"
            role = getattr(assessment, "role", "OTHER") or "OTHER"
            decision = self._enum_value(getattr(assessment, "decision", ""))
            score = getattr(assessment, "readiness_score", 0)
            listbox.insert(tk.END, f"{index}. {role} | {decision or 'N/A'} | {score} | {label}")
        if listbox.size():
            listbox.selection_set(0)

    def _update_image_readiness_photo_detail(self, tab):
        details = tab.get("details_text")
        if details is None:
            return
        report = tab.get("current_report")
        assessments = self._image_readiness_photo_assessments(report)
        listbox = tab.get("photo_listbox")
        selection = listbox.curselection() if listbox is not None else ()
        index = selection[0] if selection else 0
        assessment = assessments[index] if assessments and index < len(assessments) else None
        self._set_text_widget(details, self._format_image_readiness_photo_detail(assessment))

    def _refresh_workflow_tab(self, tab, workspace):
        """Refresh only the unified workflow tab from CollectorWorkspace."""
        report = workspace.get_workflows()
        text = tab["text"]
        text.config(state=tk.NORMAL)
        text.delete("1.0", tk.END)
        text.insert(tk.END, self._format_unified_workflow(report))
        text.config(state=tk.DISABLED)
        self._render_workflow_tool_buttons(
            tab,
            report,
            lambda: self._refresh_workflow_tab(tab, workspace),
        )

    def _render_workflow_tool_buttons(self, tab, report, refresh_command):
        """Render metadata-driven workflow buttons for existing GUI tools only."""
        button_frame = tab.get("button_frame")
        if button_frame is None:
            return
        for child in button_frame.winfo_children():
            child.destroy()
        for label, command in self._workflow_tool_button_specs(report, refresh_command):
            ttk.Button(button_frame, text=label, command=command).pack(side=tk.LEFT, padx=(0, 6))

    def _workflow_tool_button_specs(self, report, refresh_command=None):
        """Return deduplicated button specs for workflow tool metadata."""
        specs = []
        seen = set()
        tools = [getattr(report, "recommended_tool", None)]
        for action in getattr(report, "next_actions", []) or []:
            tools.append(getattr(action, "recommended_tool", None))
        for tool in tools:
            value = self._workflow_tool_value(tool)
            if value in seen:
                continue
            seen.add(value)
            spec = self._workflow_tool_button_spec(value, refresh_command)
            if spec:
                specs.append(spec)
        return specs

    def _workflow_tool_button_spec(self, tool_value, refresh_command=None):
        """Map a RecommendedTool value to an existing GUI method."""
        mapping = {
            "SMART_SHOPPING": ("Open Smart Shopping", "open_smart_shopping_assistant"),
            "UPGRADE_ADVISOR": ("Open Upgrade Advisor", "open_upgrade_advisor"),
            "DUPLICATE_REVIEW": ("Open Collection Assistant", "open_collection_assistant"),
            "COLLECTION_DASHBOARD": ("Open Collector Home", "open_collector_home"),
            "COLLECTION_INTEGRITY": ("Open Collection Integrity", "open_collection_integrity_audit"),
            "PHOTO_VAULT": ("Open Photo Vault Audit", "open_photo_vault_audit"),
            "OCR_EXPERIMENT": ("Open OCR Experiment", "open_ocr_experiment"),
            "WANT_LIST": ("Open Want List Generator", "open_want_list_generator"),
            "AI_GRADING": ("Open AI Grading Assistant", "open_ai_grading_assistant"),
        }
        value = self._workflow_tool_value(tool_value)
        if value == "WORKFLOW":
            if refresh_command is None:
                return None
            return ("Refresh Workflow", refresh_command)
        label_method = mapping.get(value)
        if not label_method:
            return None
        label, method_name = label_method
        command = getattr(self, method_name, None)
        if command is None:
            return None
        return (label, command)

    @staticmethod
    def _workflow_tool_value(tool):
        """Normalize RecommendedTool enum/string metadata for GUI mapping."""
        value = getattr(tool, "value", tool)
        return str(value or "").strip().upper()

    # -- Formatting helpers (pure formatting, no business logic) -----------

    @staticmethod
    def _enum_value(value):
        return str(getattr(value, "value", value) or "")

    @staticmethod
    def _image_readiness_report_payload(report):
        return report.to_dict() if hasattr(report, "to_dict") else dict(report or {})

    @staticmethod
    def _image_readiness_readiness(report):
        return getattr(report, "readiness_report", None)

    @staticmethod
    def _image_readiness_photo_assessments(report):
        readiness = CoinCollectionGUI._image_readiness_readiness(report)
        return list(getattr(readiness, "photo_assessments", []) or [])

    def _format_image_readiness(self, report):
        """Format Image Readiness report for the workspace tab."""
        payload = self._image_readiness_report_payload(report)
        readiness = payload.get("readiness_report") or {}
        summary = payload.get("summary") or {}
        permissions = readiness.get("downstream_permissions") or {}
        missing_roles = readiness.get("missing_roles") or []
        evidence = readiness.get("evidence") or []
        blocking = readiness.get("blocking_issues") or []
        actions = readiness.get("recommended_actions") or []
        assessments = readiness.get("photo_assessments") or []
        issues = []
        strengths = []
        for assessment in assessments:
            strengths.extend(assessment.get("strengths") or [])
            issues.extend(assessment.get("issues") or [])

        lines = ["Image Readiness", "=" * 40, ""]
        lines.append(f"Selection:          {payload.get('selection_type') or 'none'}")
        lines.append(f"Selection ID:       {payload.get('selection_id') or 'N/A'}")
        lines.append(f"Photos:             {payload.get('photo_count', 0)}")
        lines.append(f"Readiness Score:    {summary.get('overall_readiness_score', readiness.get('overall_readiness_score', 0))}")
        lines.append(f"Decision:           {summary.get('decision') or readiness.get('decision') or 'N/A'}")
        lines.append(f"Confidence:         {summary.get('confidence') or readiness.get('confidence') or 'N/A'}")

        if missing_roles:
            lines.append(f"Missing Roles:      {', '.join(str(role) for role in missing_roles)}")

        lines.extend(["", "Downstream Permissions", "-" * 40])
        if permissions:
            for key, label in self._image_readiness_permission_labels():
                lines.append(f"{label}: {permissions.get(key, 'N/A')}")
        else:
            lines.append("No downstream permission data available.")

        lines.extend(["", "Strengths", "-" * 40])
        lines.extend(self._format_image_readiness_list(strengths, "No strengths reported."))

        lines.extend(["", "Issues", "-" * 40])
        lines.extend(self._format_image_readiness_list(issues, "No non-blocking issues reported."))

        lines.extend(["", "Blocking Issues", "-" * 40])
        lines.extend(self._format_image_readiness_list(blocking, "No blocking issues reported."))

        lines.extend(["", "Recommended Actions", "-" * 40])
        lines.extend(self._format_image_readiness_list(actions, "No corrective actions recommended."))

        lines.extend(["", "Photo Summary", "-" * 40])
        if assessments:
            for assessment in assessments:
                label = os.path.basename(assessment.get("path") or "") or assessment.get("path") or "Photo"
                lines.append(
                    f"- {assessment.get('role', 'OTHER')}: "
                    f"{assessment.get('decision', 'N/A')} "
                    f"({assessment.get('readiness_score', 0)}) - {label}"
                )
        else:
            lines.append("No photo assessments available.")

        lines.append(self._format_engine_errors(payload.get("engine_errors") or []))
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _image_readiness_permission_labels():
        return [
            ("BROAD_IDENTIFICATION", "Broad Identification"),
            ("OCR", "OCR"),
            ("VARIETY_ATTRIBUTION", "Variety Attribution"),
            ("GRADE_ESTIMATION", "Grade Estimation"),
            ("SUBMISSION_READINESS", "Submission Readiness"),
        ]

    @staticmethod
    def _format_image_readiness_list(values, empty_text):
        seen = set()
        lines = []
        for value in values or []:
            text = str(value or "").strip()
            key = text.lower()
            if text and key not in seen:
                seen.add(key)
                lines.append(f"- {text}")
        return lines or [empty_text]

    def _format_image_readiness_photo_detail(self, assessment):
        """Format one selected photo assessment."""
        if assessment is None:
            return "Select a photo to view detailed assessment.\n"
        decision = self._enum_value(getattr(assessment, "decision", ""))
        confidence = self._enum_value(getattr(assessment, "confidence", ""))
        path = getattr(assessment, "path", "") or ""
        lines = [
            "Photo Assessment",
            "=" * 40,
            "",
            f"File:        {os.path.basename(path) or path or 'N/A'}",
            f"Role:        {getattr(assessment, 'role', 'OTHER') or 'OTHER'}",
            f"Readiness:   {decision or 'N/A'}",
            f"Confidence:  {confidence or 'N/A'}",
            f"Score:       {getattr(assessment, 'readiness_score', 0)}",
            "",
            "Strengths",
            "-" * 40,
        ]
        lines.extend(self._format_image_readiness_list(getattr(assessment, "strengths", []), "No strengths reported."))
        lines.extend(["", "Issues", "-" * 40])
        lines.extend(self._format_image_readiness_list(getattr(assessment, "issues", []), "No non-blocking issues reported."))
        lines.extend(["", "Blocking Issues", "-" * 40])
        lines.extend(self._format_image_readiness_list(getattr(assessment, "blocking_issues", []), "No blocking issues reported."))
        lines.extend(["", "Recommended Actions", "-" * 40])
        lines.extend(self._format_image_readiness_list(getattr(assessment, "recommended_actions", []), "No corrective actions recommended."))
        lines.extend(["", "Engine Warnings", "-" * 40])
        lines.extend(self._format_image_readiness_list(getattr(assessment, "engine_errors", []), "No engine warnings reported."))
        return "\n".join(lines).rstrip() + "\n"

    def _format_engine_errors(self, errors):
        """Format engine errors as warning text."""
        if not errors:
            return ""
        lines = ["\n\n⚠️ Warnings", "-" * 40]
        for error in errors:
            lines.append(f"- {error}")
        return "\n".join(lines) + "\n"

    def _format_dashboard(self, report):
        lines = ["Dashboard", "=" * 40, ""]
        lines.append(f"Health Score:     {report.health_score or 'N/A'}")
        lines.append(f"Quality Score:    {report.quality_score or 'N/A'}")
        lines.append(f"Integrity Score:  {report.integrity_score or 'N/A'}")
        lines.append(f"Top Priority:     {report.top_priority or 'None'}")
        lines.append(f"Best Next Purchase: {report.best_next_purchase or 'None'}")
        lines.append(f"Data Safety:      {report.data_safety_status or 'Unknown'}")
        lines.append(f"Backup Ready:     {'Yes' if report.backup_ready else 'No'}")
        if report.todays_tasks:
            lines.extend(["", "Today's Tasks", "-" * 40])
            for task in report.todays_tasks:
                lines.append(f"- {task}")
        if report.recent_activity:
            lines.extend(["", "Recent Activity", "-" * 40])
            for activity in report.recent_activity:
                lines.append(f"- {activity}")
        lines.append(self._format_engine_errors(report.engine_errors))
        return "\n".join(lines) + "\n"

    def _format_inbox(self, report):
        lines = ["Inbox", "=" * 40, ""]
        lines.append(f"Total Pending:              {report.total_pending}")
        lines.append(f"Collection Assistant:       {report.collection_assistant_pending}")
        lines.append(f"Batch Processing:           {report.batch_processing_pending}")
        lines.append(f"AI Grading Review:          {report.ai_grading_review}")
        if report.items:
            lines.extend(["", "Items", "-" * 40])
            for item in report.items:
                lines.append(f"- [{item['source']}] {item['label']} (confidence: {item.get('confidence', 0):.0%})")
        lines.append(self._format_engine_errors(report.engine_errors))
        return "\n".join(lines) + "\n"

    def _format_collection_summary(self, report):
        lines = ["Collection Summary", "=" * 40, ""]
        lines.append(f"Total Items:        {report.total_items}")
        lines.append(f"Countries:          {report.total_countries}")
        lines.append(f"Denominations:      {report.total_denominations}")
        lines.append(f"Years:              {report.total_years}")
        lines.append(f"Grade Coverage:     {report.grade_coverage or 'N/A'}")
        lines.append(f"Recent Additions:   {report.recent_additions}")
        lines.append(f"Quality Score:      {report.quality_score or 'N/A'}")
        lines.append(f"Integrity Score:    {report.integrity_score or 'N/A'}")
        if report.series_completion:
            lines.extend(["", "Series Completion", "-" * 40])
            for series in report.series_completion:
                lines.append(f"- {series.get('series', 'Unknown')}: {series.get('completion_percentage', 0):.1f}%")
        lines.append(self._format_engine_errors(report.engine_errors))
        return "\n".join(lines) + "\n"

    def _format_want_list(self, report):
        lines = ["Want List", "=" * 40, ""]
        lines.append(f"Upgrade Candidates:     {report.total_upgrades}")
        lines.append(f"Gap Targets:            {report.total_gaps}")
        lines.append(f"Watchlist Matches:      {report.total_watchlist_matches}")
        if report.upgrade_candidates:
            lines.extend(["", "Upgrade Candidates", "-" * 40])
            for c in report.upgrade_candidates:
                lines.append(f"- {c}")
        if report.gap_targets:
            lines.extend(["", "Gap Targets", "-" * 40])
            for g in report.gap_targets:
                lines.append(f"- {g}")
        if report.watchlist_matches:
            lines.extend(["", "Watchlist Matches", "-" * 40])
            for m in report.watchlist_matches:
                lines.append(f"- {m}")
        lines.append(self._format_engine_errors(report.engine_errors))
        return "\n".join(lines) + "\n"

    def _format_opportunities(self, report):
        lines = ["Opportunities", "=" * 40, ""]
        lines.append(f"Total Opportunities:    {report.total_opportunities}")
        lines.append(f"Best Next Purchase:     {report.best_next_purchase or 'None'}")
        lines.append(f"Highest Impact:         {report.highest_impact or 'None'}")
        if report.top_recommendations:
            lines.extend(["", "Top Recommendations", "-" * 40])
            for rec in report.top_recommendations:
                lines.append(f"- {rec.get('item_name', rec)}")
        if report.budget_recommendations:
            lines.extend(["", "Budget Recommendations", "-" * 40])
            for rec in report.budget_recommendations:
                lines.append(f"- {rec}")
        lines.append(self._format_engine_errors(report.engine_errors))
        return "\n".join(lines) + "\n"

    def _format_ai_queue(self, report):
        lines = ["AI Grading Queue", "=" * 40, ""]
        lines.append(f"Total Assessments:  {report.total_assessments}")
        lines.append(f"Proceed:            {report.proceed_count}")
        lines.append(f"Caution:            {report.caution_count}")
        lines.append(f"Review:             {report.review_count}")
        if not report.total_assessments:
            lines.append("\nAI Grading queue is not yet persisted.")
        lines.append(self._format_engine_errors(report.engine_errors))
        return "\n".join(lines) + "\n"

    def _format_batch_queue(self, report):
        lines = ["Batch Queue", "=" * 40, ""]
        lines.append(f"Total Sessions:     {report.total_sessions}")
        lines.append(f"Total Candidates:   {report.total_candidates}")
        lines.append(f"Reviewed:           {report.reviewed_count}")
        lines.append(f"Approved:           {report.approved_count}")
        lines.append(f"Rejected:           {report.rejected_count}")
        lines.append(f"Needs Review:       {report.needs_review_count}")
        if not report.total_sessions:
            lines.append("\nBatch processing sessions are not yet persisted.")
        lines.append(self._format_engine_errors(report.engine_errors))
        return "\n".join(lines) + "\n"

    def _format_photo_vault(self, report):
        lines = ["Photo Vault", "=" * 40, ""]
        lines.append(f"Total Items:            {report.total_collection_items}")
        lines.append(f"Items With Photos:      {report.items_with_photos}")
        lines.append(f"Items Without Photos:   {report.items_without_photos}")
        lines.append(f"Coverage:               {report.coverage_percentage:.1f}%")
        lines.append(f"Certified Items:        {report.certified_items}")
        lines.append(f"Certified With Photos:  {report.certified_with_photos}")
        lines.append(f"Missing Photos:         {report.missing_photo_count}")
        lines.append(f"Duplicate Photos:       {report.duplicate_photo_count}")
        if report.recommended_actions:
            lines.extend(["", "Recommended Actions", "-" * 40])
            for action in report.recommended_actions:
                lines.append(f"- {action}")
        lines.append(self._format_engine_errors(report.engine_errors))
        return "\n".join(lines) + "\n"

    def _format_workflow_status(self, report):
        lines = ["Workflow Status", "=" * 40, ""]
        lines.append(f"Pending Reviews:    {report.pending_reviews}")
        lines.append(f"Workflow Health:    {report.workflow_health or 'N/A'}")
        if report.active_workflows:
            lines.extend(["", "Active Workflows", "-" * 40])
            for wf in report.active_workflows:
                lines.append(f"- {wf}")
        if report.todays_tasks:
            lines.extend(["", "Today's Tasks", "-" * 40])
            for task in report.todays_tasks:
                lines.append(f"- {task}")
        if report.next_actions:
            lines.extend(["", "Next Actions", "-" * 40])
            for action in report.next_actions:
                lines.append(f"- {action}")
        lines.append(self._format_engine_errors(report.engine_errors))
        return "\n".join(lines) + "\n"

    def _format_unified_workflow(self, report):
        """Format a UnifiedWorkflowReport for the Workspace Workflow tab."""
        workflow_type = getattr(getattr(report, "workflow_type", None), "value", getattr(report, "workflow_type", ""))
        state = getattr(getattr(report, "state", None), "value", getattr(report, "state", ""))
        recommended_tool = self._workflow_tool_value(getattr(report, "recommended_tool", ""))
        recommended_tool_label = getattr(report, "recommended_tool_label", "") or "N/A"
        lines = [
            getattr(report, "title", "Workflow Review") or "Workflow Review",
            "=" * 40,
            "",
            f"Workflow Type:      {workflow_type or 'N/A'}",
            f"State:              {state or 'N/A'}",
            f"State Reason:       {getattr(report, 'state_reason', '') or 'N/A'}",
            f"Recommended Tool:   {recommended_tool or 'N/A'}",
            f"Tool Label:         {recommended_tool_label}",
            "",
            "Summary",
            "-" * 40,
            getattr(report, "summary", "") or "No workflow summary available.",
            "",
            "Next Actions",
            "-" * 40,
        ]

        actions = getattr(report, "next_actions", []) or []
        if actions:
            for action in actions:
                action_state = getattr(getattr(action, "state", None), "value", getattr(action, "state", ""))
                action_tool = self._workflow_tool_value(getattr(action, "recommended_tool", ""))
                action_tool_label = getattr(action, "recommended_tool_label", "") or "N/A"
                lines.append(f"- {getattr(action, 'label', '') or 'Review workflow action'}")
                reason = getattr(action, "reason", "")
                if reason:
                    lines.append(f"  Reason: {reason}")
                lines.append(f"  State: {action_state or 'N/A'}")
                lines.append(f"  Recommended Tool: {action_tool or 'N/A'}")
                lines.append(f"  Open: {action_tool_label}")
                evidence = getattr(action, "evidence", []) or []
                if evidence:
                    lines.append("  Evidence:")
                    for item in evidence:
                        lines.append(f"    - {self._format_workflow_evidence_item(item)}")
        else:
            lines.append("- No workflow actions available.")

        lines.extend(["", "Evidence", "-" * 40])
        evidence = getattr(report, "evidence", []) or []
        if evidence:
            for item in evidence:
                lines.append(f"- {self._format_workflow_evidence_item(item)}")
        else:
            lines.append("- No workflow evidence available.")

        warnings = getattr(report, "warnings", []) or []
        if warnings:
            lines.extend(["", "Warnings", "-" * 40])
            for warning in warnings:
                lines.append(f"- {warning}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _format_workflow_evidence_item(item):
        """Format one workflow evidence item."""
        severity = getattr(getattr(item, "severity", None), "value", getattr(item, "severity", "INFO"))
        source = getattr(item, "source", "") or "Workflow"
        detail = getattr(item, "detail", "") or "No detail available."
        action = getattr(item, "action", "")
        text = f"[{severity}] {source}: {detail}"
        if action:
            text += f" | Action: {action}"
        return text

    def _format_data_safety(self, report):
        lines = ["Data Safety", "=" * 40, ""]
        lines.append(f"Backup Ready:           {'Yes' if report.backup_ready else 'No'}")
        lines.append(f"Last Snapshot Age:      {report.last_snapshot_age or 'N/A'}")
        lines.append(f"Total Areas:            {report.total_persistence_areas}")
        lines.append(f"Persisted:              {report.persisted_areas}")
        lines.append(f"Session-Only:         {report.session_only_areas}")
        if report.persistence_areas:
            lines.extend(["", "Persistence Areas", "-" * 40])
            for area in report.persistence_areas:
                lines.append(f"- {area.get('area', area)}: {'Persisted' if area.get('survives_restart') else 'Session-only'}")
        if report.integrity_warnings:
            lines.extend(["", "Integrity Warnings", "-" * 40])
            for warning in report.integrity_warnings:
                lines.append(f"- {warning}")
        lines.append(self._format_engine_errors(report.engine_errors))
        return "\n".join(lines) + "\n"

    def _format_connected_data(self, report):
        """Format connected data panel for display."""
        lines = ["Connected Data", "=" * 40, ""]

        if report.summary:
            summary = report.summary
            lines.append(f"Total Connections:      {report.total_connections}")
            lines.append(f"Overall Match Rate:     {summary.overall_link_rate:.0%}")
            lines.append("")
            lines.append("By Source Type")
            lines.append("-" * 40)
            if summary.total_photos:
                lines.append(f"  Photos:    {summary.photos_linked}/{summary.total_photos} linked")
            if summary.total_ocr:
                lines.append(f"  OCR:       {summary.ocr_linked}/{summary.total_ocr} linked")
            if summary.total_grading:
                lines.append(f"  Grading:   {summary.grading_linked}/{summary.total_grading} linked")
            if summary.total_watchlist:
                lines.append(f"  Watchlist: {summary.watchlist_linked}/{summary.total_watchlist} linked")
        else:
            lines.append("No connection data available.")

        if report.top_connections:
            lines.append("")
            lines.append("Top Connections")
            lines.append("-" * 40)
            for c in report.top_connections[:10]:
                match_type = c.match_type.value if c.match_type else "unknown"
                lines.append(f"  {c.source_type} → {c.target_type}: {c.source_id} → {c.target_id} ({match_type})")

        lines.append(self._format_engine_errors(report.engine_errors))
        return "\n".join(lines) + "\n"


def main():
    """Main application entry point."""
    root = tk.Tk()
    app = CoinCollectionGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
