"""
Coin Collection Manager GUI
MVP app for managing coin collection with manual editing and optional automatic identification.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk
import os
import cv2
from coin_collection import CoinCollectionApp, CoinItem
from collection_intelligence import CollectionIntelligenceEngine
from legacy_portfolio_importer import (
    LegacyPortfolioImporter,
    export_import_summary_csv,
    export_want_list_preview_csv,
)
from coin_identifier_interface import CoinIdentifierFactory


class CoinCollectionGUI:
    """GUI for coin collection management."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Coin Collection Manager")
        self.root.geometry("1000x700")
        
        # Initialize backend
        self.app = CoinCollectionApp()
        
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

        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Collection Gap Report", command=self.open_collection_gap_report)
        tools_menu.add_command(label="Want List Generator", command=self.open_want_list_generator)
        tools_menu.add_command(label="Portfolio Import Preview", command=self.open_portfolio_import_preview)
        tools_menu.add_command(label="Want List Preview", command=self.open_want_list_preview)
    
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
        staged_want_list_intents = []

        dialog = tk.Toplevel(self.root)
        dialog.title("Want List Generator")
        dialog.geometry("1000x600")

        main_frame = ttk.Frame(dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        status_var = tk.StringVar(value="Using current collection analysis only.")
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
        staged_want_list_intents = []

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

        want_list_status_var = tk.StringVar(value="No staged WANT_LIST context loaded.")
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


def main():
    """Main application entry point."""
    root = tk.Tk()
    app = CoinCollectionGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
