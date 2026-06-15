"""
GUI Module
This module creates the graphical user interface for the coin analyzer application.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from typing import List, Dict
from image_analyzer import CoinAnalyzer
from csv_exporter import CSVExporter


class CoinAnalyzerGUI:
    """Main GUI application for coin analysis."""
    
    def __init__(self, root):
        """
        Initialize the GUI.
        
        Args:
            root: Tkinter root window
        """
        self.root = root
        self.root.title("Canadian Coin Analyzer (PROTOTYPE)")
        self.root.geometry("1000x700")
        
        # Initialize analyzer and exporter
        self.analyzer = CoinAnalyzer()
        self.exporter = CSVExporter()
        
        # Store selected folder and results
        self.selected_folder = None
        self.analysis_results = []
        
        # Create GUI elements
        self.create_widgets()
    
    def create_widgets(self):
        """Create all GUI widgets."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        # Title
        title_label = ttk.Label(
            main_frame,
            text="Canadian Coin Analyzer (PROTOTYPE)",
            font=('Helvetica', 16, 'bold')
        )
        title_label.grid(row=0, column=0, pady=(0, 10))
        
        # Warning label
        warning_label = ttk.Label(
            main_frame,
            text="⚠️ EXPERIMENTAL PROTOTYPE - Results require manual verification",
            font=('Helvetica', 10),
            foreground='red'
        )
        warning_label.grid(row=1, column=0, pady=(0, 20))
        
        # Folder selection section
        folder_frame = ttk.LabelFrame(main_frame, text="Select Coin Images Folder", padding="10")
        folder_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        folder_frame.columnconfigure(0, weight=1)
        
        self.folder_label = ttk.Label(folder_frame, text="No folder selected")
        self.folder_label.grid(row=0, column=0, sticky=(tk.W), padx=(0, 10))
        
        select_button = ttk.Button(
            folder_frame,
            text="Browse",
            command=self.select_folder
        )
        select_button.grid(row=0, column=1)
        
        # Analysis section
        analysis_frame = ttk.LabelFrame(main_frame, text="Analysis", padding="10")
        analysis_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.analyze_button = ttk.Button(
            analysis_frame,
            text="Analyze Coins",
            command=self.analyze_coins,
            state=tk.DISABLED
        )
        self.analyze_button.grid(row=0, column=0, sticky=(tk.W))
        
        # Progress bar
        self.progress = ttk.Progressbar(
            analysis_frame,
            mode='determinate',
            length=400
        )
        self.progress.grid(row=1, column=0, sticky=(tk.W), pady=(10, 0))
        
        # Status label
        self.status_label = ttk.Label(analysis_frame, text="Ready")
        self.status_label.grid(row=2, column=0, sticky=(tk.W), pady=(5, 0))
        
        # Export section
        export_frame = ttk.LabelFrame(main_frame, text="Export Results", padding="10")
        export_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.export_button = ttk.Button(
            export_frame,
            text="Export to CSV",
            command=self.export_csv,
            state=tk.DISABLED
        )
        self.export_button.grid(row=0, column=0, sticky=(tk.W))
        
        # Results section
        results_frame = ttk.LabelFrame(main_frame, text="Results Preview (Double-click to edit)", padding="10")
        results_frame.grid(row=5, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(5, weight=1)
        
        # Create treeview for results
        columns = ('filename', 'country', 'country_conf', 'denomination', 'denom_conf', 
                  'year', 'year_conf', 'orientation', 'grade', 'confidence', 'status')
        self.tree = ttk.Treeview(results_frame, columns=columns, show='headings')
        
        # Define column headings
        self.tree.heading('filename', text='Filename')
        self.tree.heading('country', text='Country')
        self.tree.heading('country_conf', text='C-Conf %')
        self.tree.heading('denomination', text='Denom')
        self.tree.heading('denom_conf', text='D-Conf %')
        self.tree.heading('year', text='Year')
        self.tree.heading('year_conf', text='Y-Conf %')
        self.tree.heading('orientation', text='Side')
        self.tree.heading('grade', text='Grade')
        self.tree.heading('confidence', text='G-Conf %')
        self.tree.heading('status', text='Status')
        
        # Configure column widths
        self.tree.column('filename', width=70)
        self.tree.column('country', width=50)
        self.tree.column('country_conf', width=50)
        self.tree.column('denomination', width=50)
        self.tree.column('denom_conf', width=50)
        self.tree.column('year', width=40)
        self.tree.column('year_conf', width=50)
        self.tree.column('orientation', width=40)
        self.tree.column('grade', width=40)
        self.tree.column('confidence', width=50)
        self.tree.column('status', width=70)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Bind double-click event for editing
        self.tree.bind('<Double-1>', self.edit_result)
    
    def select_folder(self):
        """Open folder selection dialog."""
        folder = filedialog.askdirectory(title="Select folder containing coin images")
        
        if folder:
            self.selected_folder = folder
            self.folder_label.config(text=folder)
            self.analyze_button.config(state=tk.NORMAL)
            self.status_label.config(text="Folder selected. Ready to analyze.")
    
    def edit_result(self, event):
        """Open edit dialog for selected result."""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = selection[0]
        values = self.tree.item(item, 'values')
        index = self.tree.index(item)
        
        # Create edit dialog
        edit_window = tk.Toplevel(self.root)
        edit_window.title("Edit Coin Information")
        edit_window.geometry("400x350")
        
        # Create form fields
        ttk.Label(edit_window, text="Filename:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        filename_entry = ttk.Entry(edit_window, width=30)
        filename_entry.insert(0, values[0])
        filename_entry.config(state='readonly')
        filename_entry.grid(row=0, column=1, padx=10, pady=5)
        
        ttk.Label(edit_window, text="Country:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        country_entry = ttk.Entry(edit_window, width=30)
        country_entry.insert(0, values[1])
        country_entry.grid(row=1, column=1, padx=10, pady=5)
        
        ttk.Label(edit_window, text="Denomination:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        denomination_entry = ttk.Entry(edit_window, width=30)
        denomination_entry.insert(0, values[3])
        denomination_entry.grid(row=2, column=1, padx=10, pady=5)
        
        ttk.Label(edit_window, text="Year:").grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)
        year_entry = ttk.Entry(edit_window, width=30)
        year_entry.insert(0, values[5])
        year_entry.grid(row=3, column=1, padx=10, pady=5)
        
        ttk.Label(edit_window, text="Side:").grid(row=4, column=0, sticky=tk.W, padx=10, pady=5)
        orientation_entry = ttk.Entry(edit_window, width=30)
        orientation_entry.insert(0, values[7])
        orientation_entry.grid(row=4, column=1, padx=10, pady=5)
        
        ttk.Label(edit_window, text="Grade Range:").grid(row=5, column=0, sticky=tk.W, padx=10, pady=5)
        grade_entry = ttk.Entry(edit_window, width=30)
        grade_entry.insert(0, values[8])
        grade_entry.grid(row=5, column=1, padx=10, pady=5)
        
        def save_changes():
            # Update the result in memory
            self.analysis_results[index]['country'] = country_entry.get()
            self.analysis_results[index]['denomination'] = denomination_entry.get()
            self.analysis_results[index]['year'] = year_entry.get()
            self.analysis_results[index]['orientation'] = orientation_entry.get()
            self.analysis_results[index]['grade_range'] = grade_entry.get()
            
            # Update the treeview
            self.tree.item(item, values=(
                values[0],
                country_entry.get(),
                values[2],  # Keep original country confidence
                denomination_entry.get(),
                values[4],  # Keep original denomination confidence
                year_entry.get(),
                values[6],  # Keep original year confidence
                orientation_entry.get(),
                grade_entry.get(),
                values[9],  # Keep original grade confidence
                "Reviewed"
            ))
            
            edit_window.destroy()
        
        def cancel_changes():
            edit_window.destroy()
        
        # Buttons
        button_frame = ttk.Frame(edit_window)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Save", command=save_changes).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="Cancel", command=cancel_changes).grid(row=0, column=1, padx=5)
    
    def analyze_coins(self):
        """Analyze all images in the selected folder."""
        if not self.selected_folder:
            messagebox.showerror("Error", "Please select a folder first")
            return
        
        # Get all image files
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
        image_files = [
            f for f in os.listdir(self.selected_folder)
            if os.path.splitext(f)[1].lower() in image_extensions
        ]
        
        if not image_files:
            messagebox.showwarning("Warning", "No image files found in selected folder")
            return
        
        # Clear previous results
        self.analysis_results = []
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Analyze each image
        total_files = len(image_files)
        self.progress['maximum'] = total_files
        
        for i, filename in enumerate(image_files):
            image_path = os.path.join(self.selected_folder, filename)
            
            # Update status
            self.status_label.config(text=f"Analyzing {filename} ({i+1}/{total_files})")
            self.root.update()
            
            # Analyze image
            result = self.analyzer.analyze_coin(image_path)
            self.analysis_results.append(result)
            
            # Determine status based on confidence
            if result['confidence_score'] < 50:
                status = "Needs Review"
            elif result['confidence_score'] < 70:
                status = "Uncertain"
            else:
                status = "Preliminary"
            
            # Add status to result for export
            result['status'] = status
            
            # Add to treeview
            self.tree.insert('', tk.END, values=(
                result['filename'],
                result['country'],
                f"{result.get('country_confidence', 0)}%",
                result['denomination'],
                f"{result.get('denomination_confidence', 0)}%",
                result['year'],
                f"{result.get('year_confidence', 0)}%",
                result.get('orientation', 'unknown'),
                result['grade_range'],
                f"{result['confidence_score']}%",
                status
            ))
            
            # Update progress
            self.progress['value'] = i + 1
            self.root.update()
        
        # Update UI
        self.status_label.config(text=f"Analysis complete. {total_files} coins analyzed.")
        self.export_button.config(state=tk.NORMAL)
        
        messagebox.showinfo("Success", f"Analysis complete! {total_files} coins analyzed.")
    
    def export_csv(self):
        """Export results to CSV file."""
        if not self.analysis_results:
            messagebox.showerror("Error", "No results to export")
            return
        
        # Ask for save location
        output_path = filedialog.asksaveasfilename(
            title="Save CSV file",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if output_path:
            self.exporter.export_to_csv(self.analysis_results, output_path)
            messagebox.showinfo("Success", f"Results exported to {output_path}")


def main():
    """Main entry point for the GUI application."""
    root = tk.Tk()
    app = CoinAnalyzerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
