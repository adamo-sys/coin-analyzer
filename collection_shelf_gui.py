"""Read-only visual shelf; record actions retain runtime identity authority."""
import tkinter as tk
from tkinter import messagebox, ttk

from coin_collection import CollectionLoadState
from collection_shelf import shelf_page


class ShelfActions:
    def __init__(self, collection_provider, open_details, open_editor):
        self.collection_provider = collection_provider
        self.open_details = open_details
        self.open_editor = open_editor

    def open(self, card, action):
        if action not in ("details", "edit"):
            raise ValueError("Unsupported shelf action")
        item = card.reference.resolve(self.collection_provider())
        callback = self.open_details if action == "details" else self.open_editor
        callback(item)


class CollectionShelfWindow:
    def __init__(self, parent, collection_provider, open_details, open_editor, on_close=None):
        self.actions = ShelfActions(collection_provider, open_details, open_editor)
        self.on_close = on_close
        self.window = tk.Toplevel(parent)
        self.window.title("Visual Collection Shelf")
        self.window.geometry("940x740")
        self.window.minsize(780, 480)
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.query = tk.StringVar(self.window)
        self.summary = tk.StringVar(self.window)
        self.page = None
        self.images = []
        self.card_frames = []
        self.card_buttons = []
        controls = ttk.Frame(self.window, padding=10)
        controls.pack(fill=tk.X)
        ttk.Label(controls, text="Search collection:").pack(side=tk.LEFT)
        entry = ttk.Entry(controls, textvariable=self.query)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        entry.bind("<Return>", lambda event: self.search())
        ttk.Button(controls, text="Search", command=self.search).pack(side=tk.LEFT)
        ttk.Button(controls, text="Clear", command=self.clear_search).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="Refresh", command=self.refresh).pack(side=tk.LEFT)
        ttk.Label(self.window, textvariable=self.summary, padding=(10, 0)).pack(anchor=tk.W)
        body = ttk.Frame(self.window, padding=10)
        body.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(body, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.cards = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window(0, 0, window=self.cards, anchor=tk.NW)
        self.cards.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._resize_canvas)
        self.window.bind("<MouseWheel>", lambda event: self.canvas.yview_scroll(-int(event.delta / 120), "units"))
        footer = ttk.Frame(self.window, padding=10)
        footer.pack(fill=tk.X)
        self.previous_button = ttk.Button(footer, text="Previous", command=lambda: self.turn_page(-1))
        self.previous_button.pack(side=tk.LEFT)
        self.next_button = ttk.Button(footer, text="Next", command=lambda: self.turn_page(1))
        self.next_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(footer, text="Close", command=self.close).pack(side=tk.RIGHT)
        self.refresh()

    def is_open(self):
        return bool(self.window.winfo_exists())

    def _resize_canvas(self, event):
        self.canvas.itemconfigure(self.canvas_window, width=event.width)
        self.window.after_idle(self._show_focused_action)

    def _show_focused_action(self, event=None):
        focused = self.window.focus_get()
        if focused is None or not any(focused in pair for pair in self.card_buttons):
            return
        top = focused.winfo_rooty() - self.canvas.winfo_rooty()
        bottom = top + focused.winfo_height()
        height = self.canvas.winfo_height()
        delta = top if top < 0 else bottom - height if bottom > height else 0
        if delta:
            region = self.canvas.bbox("all")
            if region and region[3] > region[1]:
                self.canvas.yview_moveto((self.canvas.canvasy(0) + delta - region[1]) /
                                         (region[3] - region[1]))

    def focus(self):
        self.window.deiconify()
        self.window.lift()
        self.window.focus_set()

    def clear_search(self):
        self.query.set("")
        self.search()

    def search(self):
        self.refresh(page=0)

    def turn_page(self, offset):
        self.refresh(page=(self.page.index if self.page else 0) + offset)

    def refresh(self, page=None):
        for child in self.cards.winfo_children():
            child.destroy()
        self.images.clear()
        self.card_frames.clear()
        self.card_buttons.clear()
        self.previous_button.configure(state=tk.DISABLED)
        self.next_button.configure(state=tk.DISABLED)
        collection = self.actions.collection_provider()
        index = page if page is not None else self.page.index if self.page else 0
        try:
            self.page = shelf_page(collection, self.query.get(), index)
        except ValueError:
            self.page = None
            self.summary.set("Collection unavailable. Refresh before opening a record.")
            return
        if collection.load_state is CollectionLoadState.MISSING:
            self.summary.set("No collection is available yet.")
        elif not self.page.total:
            self.summary.set("No matching collection records." if self.query.get().strip() else "0 collection records")
        else:
            self.summary.set(f"{self.page.total} collection records · Page {self.page.index + 1} of {self.page.pages}")
        self.previous_button.configure(state=tk.NORMAL if self.page.index > 0 else tk.DISABLED)
        self.next_button.configure(state=tk.NORMAL if self.page.index + 1 < self.page.pages else tk.DISABLED)
        for column in range(4):
            self.cards.columnconfigure(column, weight=1, uniform="card")
        for index, card in enumerate(self.page.cards):
            frame = ttk.LabelFrame(self.cards, text=card.reference.item_id, padding=8)
            frame.grid(row=index // 4, column=index % 4, sticky=tk.NSEW, padx=4, pady=4)
            self.card_frames.append(frame)
            preview = ttk.Label(frame, text=card.photo.status, anchor=tk.CENTER, wraplength=160)
            preview.pack(fill=tk.X)
            ttk.Label(frame, text=card.label, wraplength=170).pack(anchor=tk.W, pady=(6, 0))
            ttk.Label(frame, text=card.status).pack(anchor=tk.W)
            ttk.Label(frame, text=f"Recorded: {card.recorded_date}").pack(anchor=tk.W)
            buttons = ttk.Frame(frame)
            buttons.pack(fill=tk.X, pady=(6, 0))
            details = ttk.Button(buttons, text="Details", command=lambda value=card: self.open_card(value, "details"))
            details.pack(side=tk.LEFT)
            edit = ttk.Button(buttons, text="Edit", command=lambda value=card: self.open_card(value, "edit"))
            edit.pack(side=tk.LEFT, padx=3)
            details.bind("<FocusIn>", self._show_focused_action)
            edit.bind("<FocusIn>", self._show_focused_action)
            self.card_buttons.append((details, edit))
        self.canvas.yview_moveto(0)

    def open_card(self, card, action):
        try:
            self.actions.open(card, action)
        except ValueError as error:
            messagebox.showwarning("Record unavailable", str(error), parent=self.window)

    def close(self):
        self.window.destroy()
        self.images.clear()
        self.card_frames.clear()
        self.card_buttons.clear()
        self.page = None
        if self.on_close is not None:
            self.on_close()
