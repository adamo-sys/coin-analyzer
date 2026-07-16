"""
Manual year labeling script for coin date regions.
Opens each crop image and allows user to enter the visible year.
"""

import csv
import os
import cv2
import tkinter as tk
from tkinter import simpledialog, messagebox
from PIL import Image, ImageTk
import numpy as np
import sys


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LABELS_CSV = os.path.join(PROJECT_ROOT, "debug_outputs", "year_labels.csv")


def resolve_label_image_path(csv_path: str, label_entry: dict) -> str:
    """Resolve a crop or source-image reference without depending on the current directory."""
    reference = str(label_entry.get('crop_path') or label_entry.get('image_path') or '').strip()
    if not reference or os.path.isabs(reference):
        return reference
    return os.path.normpath(os.path.join(PROJECT_ROOT, reference))


class YearLabeler:
    """Manual year labeling tool."""
    
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.labels = []
        self.current_index = 0
        self.load_labels()
    
    def load_labels(self):
        """Load labels from CSV file."""
        try:
            with open(self.csv_path, 'r', newline='') as f:
                reader = csv.DictReader(f)
                self.labels = list(reader)
        except FileNotFoundError:
            print(f"CSV file not found: {self.csv_path}")
            self.labels = []
    
    def save_labels(self):
        """Save labels back to CSV file."""
        directory = os.path.dirname(os.path.abspath(self.csv_path))
        os.makedirs(directory, exist_ok=True)
        with open(self.csv_path, 'w', newline='') as f:
            fieldnames = ['image_path', 'crop_path', 'year', 'denomination', 'country']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.labels)
        print(f"Labels saved to {self.csv_path}")
    
    def show_image_and_get_label(self, label_entry: dict) -> str:
        """Show image with zoom capability and get year label from user."""
        crop_path = resolve_label_image_path(self.csv_path, label_entry)
        
        print(f"  Loading image: {crop_path}")
        
        # Load image
        img = cv2.imread(crop_path)
        if img is None:
            print(f"  ERROR: Failed to load image: {crop_path}")
            return label_entry.get('year', '')
        
        print(f"  Image loaded successfully: {img.shape}")
        
        # Convert to RGB for display
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Create window with zoom capability
        class ZoomableImageLabeler(tk.Tk):
            def __init__(self, img_array, title, current_year):
                super().__init__()
                self.title(title)
                self.img_array = img_array
                self.current_year = current_year
                self.zoom_level = 1.0
                self.pan_x = 0
                self.pan_y = 0
                self.result = None
                
                # Canvas for image
                self.canvas = tk.Canvas(self, width=1000, height=800)
                self.canvas.pack(fill=tk.BOTH, expand=True)
                
                # Bind mouse events for zooming and panning
                self.canvas.bind("<Button-1>", self.on_click)
                self.canvas.bind("<B1-Motion>", self.on_drag)
                self.canvas.bind("<MouseWheel>", self.on_zoom)  # Windows
                self.canvas.bind("<Button-4>", self.on_zoom)    # Linux scroll up
                self.canvas.bind("<Button-5>", self.on_zoom)    # Linux scroll down
                
                # Control panel
                control_frame = tk.Frame(self)
                control_frame.pack(fill=tk.X, padx=5, pady=5)
                
                tk.Button(control_frame, text="Zoom In (+)", command=lambda: self.zoom(1.2)).pack(side=tk.LEFT, padx=2)
                tk.Button(control_frame, text="Zoom Out (-)", command=lambda: self.zoom(0.8)).pack(side=tk.LEFT, padx=2)
                tk.Button(control_frame, text="Reset View", command=self.reset_view).pack(side=tk.LEFT, padx=2)
                tk.Button(control_frame, text="Enter Year", command=self.enter_year).pack(side=tk.LEFT, padx=2)
                tk.Button(control_frame, text="Skip", command=self.skip).pack(side=tk.LEFT, padx=2)
                
                # Instructions
                tk.Label(control_frame, text="| Scroll to zoom, drag to pan").pack(side=tk.LEFT, padx=10)
                
                # Initial display
                self.display_image()
                
                # Center the window
                self.center_window()
            
            def center_window(self):
                self.update_idletasks()
                width = self.winfo_width()
                height = self.winfo_height()
                x = (self.winfo_screenwidth() // 2) - (width // 2)
                y = (self.winfo_screenheight() // 2) - (height // 2)
                self.geometry(f'{width}x{height}+{x}+{y}')
            
            def display_image(self):
                self.canvas.delete("all")
                
                # Apply zoom and pan
                h, w = self.img_array.shape[:2]
                new_w = int(w * self.zoom_level)
                new_h = int(h * self.zoom_level)
                
                if new_w > 0 and new_h > 0:
                    resized = cv2.resize(self.img_array, (new_w, new_h))
                    pil_img = Image.fromarray(resized)
                    self.photo = ImageTk.PhotoImage(pil_img)
                    
                    # Calculate position with pan
                    x = self.canvas.winfo_width() // 2 - new_w // 2 + self.pan_x
                    y = self.canvas.winfo_height() // 2 - new_h // 2 + self.pan_y
                    
                    self.canvas.create_image(x, y, anchor=tk.NW, image=self.photo)
            
            def zoom(self, factor):
                self.zoom_level *= factor
                self.display_image()
            
            def on_zoom(self, event):
                if event.num == 5 or event.delta < 0:
                    self.zoom(0.8)
                else:
                    self.zoom(1.2)
            
            def on_click(self, event):
                self.last_x = event.x
                self.last_y = event.y
            
            def on_drag(self, event):
                dx = event.x - self.last_x
                dy = event.y - self.last_y
                self.pan_x += dx
                self.pan_y += dy
                self.last_x = event.x
                self.last_y = event.y
                self.display_image()
            
            def reset_view(self):
                self.zoom_level = 1.0
                self.pan_x = 0
                self.pan_y = 0
                self.display_image()
            
            def enter_year(self):
                year = simpledialog.askstring(
                    "Enter Year",
                    f"Enter the visible 4-digit year (e.g., 1967):",
                    initialvalue=self.current_year if self.current_year else ''
                )
                if year:
                    self.result = year
                self.destroy()
            
            def skip(self):
                self.result = self.current_year
                self.destroy()
        
        # Run the zoomable labeler
        app = ZoomableImageLabeler(
            img_rgb,
            f"Label Year - {os.path.basename(label_entry['image_path'])}",
            label_entry.get('year', '')
        )
        app.mainloop()
        
        return app.result if app.result else label_entry.get('year', '')
    
    def label_all(self):
        """Label all unlabeled images."""
        unlabeled = [i for i, label in enumerate(self.labels) if not label.get('year')]
        
        if not unlabeled:
            print("All images are already labeled!")
            return
        
        print(f"\nFound {len(unlabeled)} unlabeled images")
        print("=" * 60)
        
        for i in unlabeled:
            image_name = os.path.basename(self.labels[i]['image_path'])
            print(f"\n[{i+1}/{len(unlabeled)}] Processing: {image_name}")
            print(f"  Crop: {os.path.basename(self.labels[i]['crop_path'])}")
            
            year = self.show_image_and_get_label(self.labels[i])
            
            if year:
                self.labels[i]['year'] = year
                print(f"  ✓ Year entered: {year}")
                
                # Save after each label
                self.save_labels()
                
                # Confirm save with specific format
                print(f"  ✓ Saved year {year} for {image_name}")
            else:
                print(f"  ✗ Skipped (no year entered)")
            
            print("-" * 60)
        
        print("\n" + "=" * 60)
        print("Labeling complete!")
        
        # Re-run validation after labeling
        print("\nRunning validation...")
        self.validate_labels()
    
    def validate_labels(self) -> bool:
        """Validate that all labels have year values."""
        missing = [label for label in self.labels if not label.get('year')]
        
        if missing:
            print(f"Validation failed: {len(missing)} images missing year labels")
            for label in missing:
                print(f"  Missing: {label['crop_path']}")
            return False
        
        print(f"Validation passed: All {len(self.labels)} images have year labels")
        return True


def main():
    """Run the year labeling tool."""
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    csv_path = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_LABELS_CSV
    
    if not os.path.exists(csv_path):
        print(f"CSV file not found: {csv_path}")
        print("Provide a generated label manifest as the second argument.")
        return
    
    labeler = YearLabeler(csv_path)
    
    print(f"Loaded {len(labeler.labels)} label entries from {csv_path}")
    
    # Check validation status
    labeler.validate_labels()
    
    # Check for command-line arguments
    if mode:
        if mode == 'label':
            print("\nStarting automatic labeling...")
            labeler.label_all()
        elif mode == 'validate':
            print("\nValidating labels...")
            labeler.validate_labels()
        elif mode == 'clear':
            print("\nClearing all labels...")
            for label in labeler.labels:
                label['year'] = ''
            labeler.save_labels()
            print("All labels cleared.")
        else:
            print(f"Unknown mode: {mode}")
            print("Usage: python label_years.py [label|validate|clear] [csv_path]")
    else:
        # Interactive mode
        print("\nOptions:")
        print("1. Label all unlabeled images")
        print("2. Re-label all images")
        print("3. Validate labels only")
        print("4. Exit")
        
        try:
            choice = input("\nEnter choice (1-4): ").strip()
        except EOFError:
            print("\nNo input detected. Use command-line arguments:")
            print("  python label_years.py label   - Start labeling")
            print("  python label_years.py validate - Validate labels")
            print("  python label_years.py clear   - Clear all labels")
            return
        
        if choice == '1':
            labeler.label_all()
        elif choice == '2':
            # Clear all years and re-label
            for label in labeler.labels:
                label['year'] = ''
            labeler.save_labels()
            print("All years cleared. Starting labeling...")
            labeler.label_all()
        elif choice == '3':
            labeler.validate_labels()
        elif choice == '4':
            print("Exiting...")
        else:
            print("Invalid choice")


if __name__ == "__main__":
    main()
