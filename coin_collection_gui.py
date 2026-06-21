"""
Coin Collection Manager GUI
MVP app for managing coin collection with manual editing and optional automatic identification.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk
import os
import cv2
from acquisition_workflow import AcquisitionWorkflow
from coin_collection import CoinCollectionApp, CoinItem
from collection_intelligence import CollectionIntelligenceEngine
from deal_hunter import DealHunter, DealListing
from deal_hunter_calibration import DealHunterCalibrationEngine
from deal_hunter_ranking import CandidatePool, DealHunterRankingEngine, ImportProfile
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
from market_intelligence import MarketIntelligenceEngine
from portfolio_performance import PortfolioPerformanceEngine
from coin_identifier_interface import CoinIdentifierFactory
from upgrade_advisor import UpgradeAdvisor
from portfolio_dashboard import PortfolioDashboard
from session_context import SessionContext
from listing_analyzer import ListingAnalyzer, ListingCandidate
from backup_manager import BackupManager, DataSafetyValidator
from collection_dashboard import CollectionDashboard
from collector_companion_readiness import CollectorCompanionReadinessAuditor
from collector_home_dashboard import CollectorHomeDashboard
from collection_integrity import CollectionIntegrityAudit
from collection_snapshot import CollectionSnapshotManager
from collector_operating_system import CollectorHome, CollectionHealthReportEngine
from collector_workflows import CollectorWorkflowEngine
from market_awareness import MarketAwarenessEngine
from ocr_experiment import OCRExperiment
from ocr_validation import OCRValidationEngine
from opportunity_engine import OpportunityEngine
from persistence_manager import PersistenceManager
from photo_assisted_entry import PhotoAssistedEntry, PhotoCandidate
from photo_vault import PhotoVaultIntegrityAudit
from shopping_explainability import ShoppingExplanationEngine
from smart_shopping_assistant import SmartShoppingAssistant, ShoppingCandidate


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
        self.snapshot_manager = CollectionSnapshotManager()
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
        self.session_status_var = tk.StringVar(value=self.session_context.format_status_line())
        
        # Initialize optional identifier
        self.identifier = None
        self.use_identifier = False
        
        # Current state
        self.current_image = None
        self.current_photo = None
        self.detection_result = None
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create GUI
        self.create_widgets()
        self.refresh_collection_list()
    
    def create_menu_bar(self):
        """Create the menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Import Collection CSV", command=self.import_collection_csv)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)

        # Collector Home menu
        home_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Collector Home", menu=home_menu)
        home_menu.add_command(label="Collector Home Dashboard", command=self.open_collector_home_dashboard)
        home_menu.add_command(label="Collector Home", command=self.open_collector_home)
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
        tools_menu.add_command(label="Deal Hunter Ranking", command=self.open_deal_hunter_ranking)
        tools_menu.add_command(label="Deal Hunter Calibration", command=self.open_deal_hunter_calibration)
        tools_menu.add_command(label="External Listing Connectors", command=self.open_external_listing_connectors)
        tools_menu.add_command(label="Live Deal Hunter", command=self.open_live_deal_hunter)
        tools_menu.add_command(label="Live Deal Hunter Readiness", command=self.open_live_deal_hunter_readiness)
        tools_menu.add_command(label="Market Intelligence", command=self.open_market_intelligence)
        tools_menu.add_command(label="Portfolio Performance", command=self.open_portfolio_performance)
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
        left_panel = ttk.Frame(main_frame)
        left_panel.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        # Image section
        image_frame = ttk.LabelFrame(left_panel, text="Coin Image", padding="10")
        image_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Image display
        self.image_label = ttk.Label(image_frame, text="No image loaded", anchor=tk.CENTER)
        self.image_label.pack(fill=tk.BOTH, expand=True)
        
        # Image buttons
        button_frame = ttk.Frame(image_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="Upload Image", command=self.upload_image).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Clear", command=self.clear_image).pack(side=tk.LEFT)
        
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
        edit_frame = ttk.LabelFrame(right_panel, text="Coin Details", padding="10")
        edit_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        edit_frame.columnconfigure(1, weight=1)
        
        # Form fields
        ttk.Label(edit_frame, text="Country:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.country_var = tk.StringVar()
        country_entry = ttk.Entry(edit_frame, textvariable=self.country_var)
        country_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        country_entry.bind('<KeyRelease>', lambda e: self.on_autocomplete('country', self.country_var.get()))
        
        ttk.Label(edit_frame, text="Denomination:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.denomination_var = tk.StringVar()
        denom_entry = ttk.Entry(edit_frame, textvariable=self.denomination_var)
        denom_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        denom_entry.bind('<KeyRelease>', lambda e: self.on_autocomplete('denomination', self.denomination_var.get()))
        
        ttk.Label(edit_frame, text="Year:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.year_var = tk.StringVar()
        year_entry = ttk.Entry(edit_frame, textvariable=self.year_var)
        year_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        year_entry.bind('<KeyRelease>', lambda e: self.on_autocomplete('year', self.year_var.get()))
        
        ttk.Label(edit_frame, text="Grade:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.grade_var = tk.StringVar()
        grade_combo = ttk.Combobox(edit_frame, textvariable=self.grade_var, 
                                   values=["", "PO-1", "FR-2", "AG-3", "G-4", "VG-8", "F-12", "VF-20", "VF-30", "EF-40", "EF-45", "AU-50", "AU-53", "AU-55", "AU-58", "MS-60", "MS-61", "MS-62", "MS-63", "MS-64", "MS-65", "MS-66", "MS-67", "MS-68", "MS-69", "MS-70"])
        grade_combo.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        ttk.Label(edit_frame, text="Notes:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.notes_text = tk.Text(edit_frame, height=3, wrap=tk.WORD)
        self.notes_text.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        # Action buttons
        action_frame = ttk.Frame(edit_frame)
        action_frame.grid(row=5, column=0, columnspan=2, pady=(10, 0))
        
        ttk.Button(action_frame, text="Use Detection Results", command=self.use_detection_results).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_frame, text="Save to Collection", command=self.save_to_collection).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_frame, text="Clear Form", command=self.clear_form).pack(side=tk.LEFT)
        
        # Collection list
        collection_frame = ttk.LabelFrame(right_panel, text="Collection", padding="10")
        collection_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        collection_frame.columnconfigure(0, weight=1)
        collection_frame.rowconfigure(1, weight=1)
        
        # Search box
        search_frame = ttk.Frame(collection_frame)
        search_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        search_entry.bind('<KeyRelease>', self.on_search)
        ttk.Button(search_frame, text="Clear", command=self.clear_search).pack(side=tk.LEFT)
        
        # Collection list with scrollbar
        list_frame = ttk.Frame(collection_frame)
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        self.collection_tree = ttk.Treeview(list_frame, columns=("ID", "Country", "Denom", "Year", "Grade"), 
                                          show="headings", yscrollcommand=scrollbar.set)
        self.collection_tree.heading("ID", text="ID")
        self.collection_tree.heading("Country", text="Country")
        self.collection_tree.heading("Denom", text="Denomination")
        self.collection_tree.heading("Year", text="Year")
        self.collection_tree.heading("Grade", text="Grade")
        
        self.collection_tree.column("ID", width=80)
        self.collection_tree.column("Country", width=100)
        self.collection_tree.column("Denom", width=100)
        self.collection_tree.column("Year", width=60)
        self.collection_tree.column("Grade", width=60)
        
        self.collection_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.config(command=self.collection_tree.yview)
        
        self.collection_tree.bind("<<TreeviewSelect>>", self.on_collection_select)
        
        # Collection buttons
        collection_buttons = ttk.Frame(collection_frame)
        collection_buttons.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        ttk.Button(collection_buttons, text="View Details", command=self.view_item_details).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(collection_buttons, text="Edit Item", command=self.edit_item).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(collection_buttons, text="Delete Item", command=self.delete_item).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(collection_buttons, text="Buy Advisor", command=self.open_buy_advisor).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(collection_buttons, text="Import Numista", command=self.import_numista).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(collection_buttons, text="Analyze Collection", command=self.analyze_collection).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(collection_buttons, text="Gap Report", command=self.open_collection_gap_report).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(collection_buttons, text="Export CSV", command=self.export_csv).pack(side=tk.LEFT)

        ttk.Label(
            main_frame,
            textvariable=self.session_status_var,
            anchor=tk.W,
            relief=tk.SUNKEN,
            padding=(6, 3),
        ).grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))

    def _collection_items(self):
        return self.app.collection.get_all_items()

    def _active_want_list_intents(self):
        return self.session_context.get_want_list_intents()

    def refresh_session_status(self):
        self.session_status_var.set(self.session_context.format_status_line())

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
        """Restore app state from a selected backup package."""
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
            "Restore app-state files from this backup?\n\nA pre-restore backup will be created first."
        ):
            return
        result = self.backup_manager.restore_from_backup_package(file_path, overwrite=True)
        if result.success:
            load_result = self.persistence_manager.load_state()
            if load_result.success:
                self._apply_loaded_app_state(load_result.state)
            detail = f"Restored files: {len(result.restored_files)}\nSkipped files: {len(result.skipped_files)}"
            if result.pre_restore_backup_path:
                detail += f"\nPre-restore backup: {result.pre_restore_backup_path}"
            messagebox.showinfo("Restore Complete", detail)
        else:
            messagebox.showerror("Restore Error", "\n".join(result.errors))
    
    def upload_image(self):
        """Upload coin image."""
        file_path = filedialog.askopenfilename(
            title="Select Coin Image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp")]
        )
        
        if file_path:
            if self.app.upload_image(file_path):
                self.display_image(file_path)
                messagebox.showinfo("Success", "Image uploaded successfully")
            else:
                messagebox.showerror("Error", "Failed to upload image")
    
    def display_image(self, image_path):
        """Display image in GUI."""
        try:
            # Load and resize image
            img = Image.open(image_path)
            img.thumbnail((400, 400))
            self.current_photo = ImageTk.PhotoImage(img)
            self.current_image = image_path
            
            self.image_label.config(image=self.current_photo, text="")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to display image: {str(e)}")
    
    def clear_image(self):
        """Clear current image."""
        self.current_image = None
        self.current_photo = None
        self.image_label.config(image="", text="No image loaded")
        self.app.current_image_path = None
        self.detection_result = None
        self.detection_label.config(text="No detection results")
    
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
            self.detection_label.config(text=text)
            
            confidence_text = f"Denomination Confidence: {result['confidence']:.2%}\n"
            confidence_text += f"Year Confidence: {result['year_confidence']:.2%}"
            self.confidence_label.config(text=confidence_text)
            
            # Log detection for debugging
            self.log_detection(result)
        else:
            self.detection_label.config(text=f"Detection failed: {result.get('error', 'Unknown error')}")
            self.confidence_label.config(text="")
    
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
        """Save current coin to collection."""
        if not self.app.current_image_path:
            messagebox.showwarning("Warning", "Please upload an image first")
            return
        
        country = self.country_var.get().strip()
        denomination = self.denomination_var.get().strip()
        year = self.year_var.get().strip()
        grade = self.grade_var.get().strip()
        notes = self.notes_text.get("1.0", tk.END).strip()
        
        if not country or not denomination:
            messagebox.showwarning("Warning", "Country and denomination are required")
            return
        
        # Never auto-save detector results as truth - manual fields are source of truth
        use_detection = False  # Always false - manual fields are source of truth
        
        if self.app.add_to_collection(country, denomination, year, grade, notes, use_detection):
            # Log the corrected values if detection was used
            if self.detection_result and self.detection_result['success']:
                self.log_correction(country, denomination, year)
            
            messagebox.showinfo("Success", "Coin added to collection")
            self.clear_form()
            self.refresh_collection_list()
        else:
            messagebox.showerror("Error", "Failed to add coin to collection")
    
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
        self.country_var.set("")
        self.denomination_var.set("")
        self.year_var.set("")
        self.grade_var.set("")
        self.notes_text.delete("1.0", tk.END)
    
    def refresh_collection_list(self):
        """Refresh collection list view."""
        # Clear existing items
        for item in self.collection_tree.get_children():
            self.collection_tree.delete(item)
        
        # Get items based on search
        search_query = self.search_var.get().strip()
        if search_query:
            items = self.app.collection.search_items(search_query)
        else:
            items = self.app.collection.get_all_items()
        
        # Add items to tree
        for item in items:
            self.collection_tree.insert("", tk.END, values=(
                item.id,
                item.country,
                item.denomination,
                item.year,
                item.grade
            ))
    
    def on_search(self, event):
        """Handle search input."""
        self.refresh_collection_list()
    
    def clear_search(self):
        """Clear search and show all items."""
        self.search_var.set("")
        self.refresh_collection_list()
    
    def on_autocomplete(self, field: str, query: str):
        """Handle autocomplete for form fields."""
        if len(query) < 2:  # Only trigger after 2 characters
            return
        
        suggestions = self.app.collection.get_autocomplete_suggestions(field, query)
        if suggestions:
            # For now, just print suggestions - could implement dropdown in future
            print(f"Autocomplete suggestions for {field}: {suggestions[:5]}")
    
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
        """Handle collection item selection."""
        selection = self.collection_tree.selection()
        if selection:
            item_id = self.collection_tree.item(selection[0])['values'][0]
            # Could load item details here
            pass
    
    def view_item_details(self):
        """View selected item details."""
        selection = self.collection_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an item")
            return
        
        item_id = self.collection_tree.item(selection[0])['values'][0]
        item = self.app.collection.get_item(item_id)
        
        if item:
            details = f"ID: {item.id}\n"
            details += f"Image: {item.image_path}\n"
            details += f"Country: {item.country}\n"
            details += f"Denomination: {item.denomination}\n"
            details += f"Year: {item.year}\n"
            details += f"Grade: {item.grade}\n"
            details += f"Notes: {item.notes}\n"
            details += f"Date Added: {item.date_added}\n"
            
            # Numista fields
            if item.from_numista:
                details += "\n--- Numista Details ---\n"
                details += f"Title: {item.title}\n"
                details += f"Numista N#: {item.numista_n}\n"
                details += f"Reference: {item.reference}\n"
                details += f"Issuer: {item.issuer}\n"
                details += f"Currency: {item.currency}\n"
                details += f"Face Value: {item.face_value}\n"
                details += f"Quantity: {item.quantity}\n"
                details += f"Estimate (CAD): ${item.estimate_cad:.2f}\n"
                details += f"Comments: {item.comments}\n"
            
            details += f"\n--- Detection Info ---\n"
            details += f"Auto Detected: {item.auto_detected}\n"
            details += f"Detection Confidence: {item.detection_confidence}"
            
            messagebox.showinfo("Item Details", details)
        else:
            messagebox.showerror("Error", "Item not found")
    
    def edit_item(self):
        """Edit selected item."""
        selection = self.collection_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an item")
            return
        
        item_id = self.collection_tree.item(selection[0])['values'][0]
        item = self.app.collection.get_item(item_id)
        
        if item:
            # Simple edit dialog
            new_country = simpledialog.askstring("Edit Country", "Enter country:", initialvalue=item.country)
            if new_country:
                new_denomination = simpledialog.askstring("Edit Denomination", "Enter denomination:", initialvalue=item.denomination)
                if new_denomination:
                    new_year = simpledialog.askstring("Edit Year", "Enter year:", initialvalue=item.year)
                    if new_year is not None:
                        new_grade = simpledialog.askstring("Edit Grade", "Enter grade:", initialvalue=item.grade)
                        if new_grade is not None:
                            new_notes = simpledialog.askstring("Edit Notes", "Enter notes:", initialvalue=item.notes)
                            if new_notes is not None:
                                # Update item
                                self.app.collection.update_item(item_id, {
                                    'country': new_country,
                                    'denomination': new_denomination,
                                    'year': new_year,
                                    'grade': new_grade,
                                    'notes': new_notes
                                })
                                self.refresh_collection_list()
                                messagebox.showinfo("Success", "Item updated")
        else:
            messagebox.showerror("Error", "Item not found")
    
    def delete_item(self):
        """Delete selected item."""
        selection = self.collection_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an item")
            return
        
        item_id = self.collection_tree.item(selection[0])['values'][0]
        
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this item?"):
            if self.app.collection.delete_item(item_id):
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
                supplied_text = raw_text.get("1.0", tk.END).strip()
                report = OCRExperiment().run(
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

    def open_portfolio_performance(self):
        """Open deterministic portfolio-level performance report."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Portfolio Performance")
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

        summary_frame = ttk.LabelFrame(main_frame, text="Portfolio Summary", padding="10")
        summary_frame.pack(fill=tk.X, pady=(0, 10))
        report = current_report["report"]
        ttk.Label(
            summary_frame,
            text=(
                f"Items: {report.growth_report.collection_size}   "
                f"Health: {report.health_score.score}/100   "
                f"Estimated local value: ${report.growth_report.estimated_collection_value:.2f}"
            ),
        ).pack(anchor=tk.W)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        result_frame = ttk.LabelFrame(main_frame, text="Portfolio Performance Report", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        result_text = tk.Text(result_frame, wrap=tk.WORD)
        result_text.pack(fill=tk.BOTH, expand=True)
        result_text.insert(tk.END, report.format_markdown())

        def refresh():
            current_report["report"] = engine.generate_report()
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, current_report["report"].format_markdown())

        def export_csv():
            file_path = filedialog.asksaveasfilename(
                title="Export Portfolio Performance CSV",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if not file_path:
                return
            current_report["report"].export_csv(file_path)
            messagebox.showinfo("Export Complete", f"Portfolio Performance CSV exported to {file_path}")

        def export_markdown():
            file_path = filedialog.asksaveasfilename(
                title="Export Portfolio Performance Markdown",
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
            )
            if not file_path:
                return
            current_report["report"].export_markdown(file_path)
            messagebox.showinfo("Export Complete", f"Portfolio Performance Markdown exported to {file_path}")

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


def main():
    """Main application entry point."""
    root = tk.Tk()
    app = CoinCollectionGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
