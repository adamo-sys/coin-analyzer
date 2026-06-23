"""
UI Patterns - Consistent UI Component Patterns

This module provides consistent UI patterns for the Collector Platform,
standardizing dialogs, reports, and workflows across the application.
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import tkinter as tk
from tkinter import ttk, messagebox, filedialog


class UIComponentType(Enum):
    """Types of UI components."""
    DIALOG = "dialog"
    REPORT = "report"
    WORKFLOW = "workflow"
    PANEL = "panel"
    FORM = "form"


@dataclass
class UIComponent:
    """Base class for UI components."""
    component_type: UIComponentType
    component_id: str
    title: str
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert component to dictionary."""
        return {
            "component_type": self.component_type.value,
            "component_id": self.component_id,
            "title": self.title,
            "description": self.description
        }


class PlatformUI:
    """Platform UI manager for consistent UI patterns."""
    
    def __init__(self, platform):
        self.platform = platform
        self._components: Dict[str, UIComponent] = {}
    
    def register_component(self, component: UIComponent) -> bool:
        """Register a UI component."""
        if component.component_id in self._components:
            return False
        
        self._components[component.component_id] = component
        return True
    
    def get_component(self, component_id: str) -> Optional[UIComponent]:
        """Get a registered component."""
        return self._components.get(component_id)
    
    def get_all_components(self) -> List[UIComponent]:
        """Get all registered components."""
        return list(self._components.values())
    
    def create_dialog(self, parent: tk.Tk, title: str, 
                     content: Callable, **kwargs) -> tk.Toplevel:
        """Create a consistent dialog window."""
        dialog = tk.Toplevel(parent)
        dialog.title(title)
        dialog.geometry("800x600")
        
        # Add consistent styling
        style = ttk.Style()
        style.configure("Platform.TFrame", background="#f0f0f0")
        style.configure("Platform.TLabel", background="#f0f0f0", font=("Arial", 10))
        style.configure("Platform.TButton", font=("Arial", 10))
        
        main_frame = ttk.Frame(dialog, style="Platform.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Call content function to populate dialog
        content(main_frame, **kwargs)
        
        return dialog
    
    def create_report_dialog(self, parent: tk.Tk, title: str, 
                           report_data: Dict[str, Any],
                           export_callback: Optional[Callable] = None) -> tk.Toplevel:
        """Create a consistent report dialog."""
        dialog = self.create_dialog(parent, title, self._report_content, 
                                    report_data=report_data, 
                                    export_callback=export_callback)
        return dialog
    
    def _report_content(self, parent: tk.Frame, report_data: Dict[str, Any],
                       export_callback: Optional[Callable] = None):
        """Content for report dialogs."""
        # Create scrollable text widget
        text_frame = ttk.Frame(parent)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text_widget = tk.Text(text_frame, wrap=tk.WORD, 
                             yscrollcommand=scrollbar.set,
                             font=("Courier New", 9))
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        scrollbar.config(command=text_widget.yview)
        
        # Insert report data
        text_widget.insert(tk.END, self._format_report_data(report_data))
        text_widget.config(state=tk.DISABLED)
        
        # Add export button if callback provided
        if export_callback:
            button_frame = ttk.Frame(parent)
            button_frame.pack(fill=tk.X, pady=10)
            
            ttk.Button(button_frame, text="Export CSV", 
                      command=lambda: export_callback("csv")).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Export Markdown", 
                      command=lambda: export_callback("markdown")).pack(side=tk.LEFT, padx=5)
    
    def _format_report_data(self, data: Dict[str, Any], indent: int = 0) -> str:
        """Format report data as text."""
        lines = []
        prefix = "  " * indent
        
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(self._format_report_data(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{prefix}{key}:")
                for item in value:
                    if isinstance(item, dict):
                        lines.append(self._format_report_data(item, indent + 1))
                    else:
                        lines.append(f"{prefix}  - {item}")
            else:
                lines.append(f"{prefix}{key}: {value}")
        
        return "\n".join(lines)
    
    def create_workflow_dialog(self, parent: tk.Tk, title: str,
                              steps: List[Dict[str, Any]],
                              complete_callback: Callable) -> tk.Toplevel:
        """Create a consistent workflow dialog."""
        dialog = self.create_dialog(parent, title, self._workflow_content,
                                    steps=steps, complete_callback=complete_callback)
        return dialog
    
    def _workflow_content(self, parent: tk.Frame, steps: List[Dict[str, Any]],
                         complete_callback: Callable):
        """Content for workflow dialogs."""
        current_step = [0]
        
        def next_step():
            if current_step[0] < len(steps) - 1:
                current_step[0] += 1
                update_step_display()
            else:
                complete_callback()
                parent.winfo_toplevel().destroy()
        
        def prev_step():
            if current_step[0] > 0:
                current_step[0] -= 1
                update_step_display()
        
        def update_step_display():
            step = steps[current_step[0]]
            step_label.config(text=f"Step {current_step[0] + 1} of {len(steps)}: {step['title']}")
            
            # Clear content frame
            for widget in content_frame.winfo_children():
                widget.destroy()
            
            # Call step content function
            if 'content' in step:
                step['content'](content_frame)
        
        # Step indicator
        step_frame = ttk.Frame(parent)
        step_frame.pack(fill=tk.X, pady=5)
        
        step_label = ttk.Label(step_frame, text="")
        step_label.pack()
        
        # Content frame
        content_frame = ttk.Frame(parent)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Navigation buttons
        nav_frame = ttk.Frame(parent)
        nav_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(nav_frame, text="Previous", command=prev_step).pack(side=tk.LEFT, padx=5)
        ttk.Button(nav_frame, text="Next", command=next_step).pack(side=tk.LEFT, padx=5)
        
        # Initialize first step
        update_step_display()
    
    def show_info_dialog(self, parent: tk.Tk, title: str, message: str):
        """Show a consistent info dialog."""
        messagebox.showinfo(title, message, parent=parent)
    
    def show_warning_dialog(self, parent: tk.Tk, title: str, message: str):
        """Show a consistent warning dialog."""
        messagebox.showwarning(title, message, parent=parent)
    
    def show_error_dialog(self, parent: tk.Tk, title: str, message: str):
        """Show a consistent error dialog."""
        messagebox.showerror(title, message, parent=parent)
    
    def show_confirmation_dialog(self, parent: tk.Tk, title: str, message: str) -> bool:
        """Show a consistent confirmation dialog."""
        return messagebox.askyesno(title, message, parent=parent)
    
    def show_file_open_dialog(self, parent: tk.Tk, title: str, 
                             filetypes: List[tuple] = None) -> Optional[str]:
        """Show a consistent file open dialog."""
        if filetypes is None:
            filetypes = [("All Files", "*.*")]
        
        return filedialog.askopenfilename(title=title, filetypes=filetypes, parent=parent)
    
    def show_file_save_dialog(self, parent: tk.Tk, title: str,
                             defaultextension: str = "",
                             filetypes: List[tuple] = None) -> Optional[str]:
        """Show a consistent file save dialog."""
        if filetypes is None:
            filetypes = [("All Files", "*.*")]
        
        return filedialog.asksaveasfilename(title=title, defaultextension=defaultextension,
                                          filetypes=filetypes, parent=parent)


class UIController:
    """Controller for UI components and state."""
    
    def __init__(self, platform_ui: PlatformUI):
        self.platform_ui = platform_ui
        self._state: Dict[str, Any] = {}
    
    def set_state(self, key: str, value: Any):
        """Set UI state."""
        self._state[key] = value
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get UI state."""
        return self._state.get(key, default)
    
    def clear_state(self):
        """Clear all UI state."""
        self._state.clear()


class UIStateManager:
    """Manager for UI state across components."""
    
    def __init__(self):
        self._controllers: Dict[str, UIController] = {}
    
    def register_controller(self, name: str, controller: UIController) -> bool:
        """Register a UI controller."""
        if name in self._controllers:
            return False
        
        self._controllers[name] = controller
        return True
    
    def get_controller(self, name: str) -> Optional[UIController]:
        """Get a registered controller."""
        return self._controllers.get(name)
    
    def get_all_controllers(self) -> List[UIController]:
        """Get all controllers."""
        return list(self._controllers.values())
    
    def unregister_controller(self, name: str) -> bool:
        """Unregister a controller."""
        if name not in self._controllers:
            return False
        
        del self._controllers[name]
        return True
