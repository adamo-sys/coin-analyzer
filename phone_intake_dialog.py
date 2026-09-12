"""Small manual two-image pairing surface within Photo Inbox."""
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageOps, ImageTk

from phone_intake import PhoneIntake
from photo_inbox import DEFAULT_INBOX_FOLDER


def open_phone_intake(gui):
    store = PhoneIntake()
    window = tk.Toplevel(gui.root)
    window.title("Photo Inbox - Pair and Review Phone Photos")
    window.geometry("960x720")
    window.columnconfigure(0, weight=1)
    window.columnconfigure(1, weight=1)
    window.rowconfigure(1, weight=1)
    ttk.Label(window, text="Select each image and assign Front / Reverse. Filenames and order never confirm a pair.", wraplength=900).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=8)
    files = tk.Listbox(window, exportselection=False)
    files.grid(row=1, column=0, sticky="nsew", padx=10)
    pairs = ttk.Treeview(window, columns=("state", "front", "reverse", "record"), show="headings", height=9)
    for name, width in (("state", 70), ("front", 125), ("reverse", 125), ("record", 110)):
        pairs.heading(name, text=name.title())
        pairs.column(name, width=width)
    pairs.grid(row=1, column=1, sticky="nsew", padx=10)
    previews = ttk.Frame(window)
    previews.grid(row=2, column=0, columnspan=2, pady=8)
    labels = [ttk.Label(previews, text=title) for title in ("Selected image", "Front", "Reverse")]
    for i, label in enumerate(labels):
        label.grid(row=0, column=i, padx=8)
    selection = {"front": "", "reverse": ""}
    paths = []
    thumbnails = {}
    status = tk.StringVar(value="Import files first using Import Phone Photos. Unpaired retakes/orphans can remain here.")
    ttk.Label(window, textvariable=status, wraplength=900).grid(row=4, column=0, columnspan=2, sticky="w", padx=10, pady=10)

    def show(label, path, title):
        if not path:
            label.configure(image="", text=title)
            return
        with Image.open(path) as source:
            picture = ImageOps.exif_transpose(source).copy()
        picture.thumbnail((230, 190))
        thumbnails[title] = ImageTk.PhotoImage(picture, master=window)
        label.configure(image=thumbnails[title], text=title + "\n" + Path(path).name, compound="top")

    def safe(action):
        try:
            action()
        except Exception as error:
            messagebox.showerror("Phone Intake", str(error), parent=window)

    def refresh():
        records = store.records()
        claimed = {image["path"] for pair in records.values() for image in pair["images"].values()}
        paths[:] = [str(p.absolute()) for p in sorted(Path(DEFAULT_INBOX_FOLDER).glob("*"))
                    if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png"} and str(p.absolute()) not in claimed]
        files.delete(0, tk.END)
        for path in paths:
            files.insert(tk.END, Path(path).name)
        old = pairs.selection()
        pairs.delete(*pairs.get_children())
        for pair_id, pair in records.items():
            pairs.insert("", tk.END, iid=pair_id, values=(pair["state"], Path(pair["images"]["front"]["path"]).name,
                         Path(pair["images"]["reverse"]["path"]).name, (pair["save"] or {}).get("item_id", "")))
        if old and old[0] in records:
            pairs.selection_set(old[0])
        status.set(f"Unpaired images: {len(paths)} | Ready pairs: {sum(p['state'] == 'READY' for p in records.values())}. SAVING means reconcile before any resave.")

    def assign(role):
        selected = files.curselection()
        if not selected:
            raise ValueError("Select an unpaired image first.")
        selection[role] = paths[selected[0]]
        show(labels[1 if role == "front" else 2], selection[role], role.title())

    def confirm():
        if not all(selection.values()):
            raise ValueError("Assign both Front and Reverse.")
        if messagebox.askyesno("Confirm one physical coin", "Do these Front and Reverse photos show the same physical coin?", parent=window):
            pair_id = store.confirm_pair(selection["front"], selection["reverse"])
            selection.update(front="", reverse="")
            refresh()
            pairs.selection_set(pair_id)
            display_pair()

    def selected_pair():
        selected = pairs.selection()
        if not selected:
            raise ValueError("Select a confirmed pair first.")
        return selected[0]

    def display_pair():
        pair = store.records()[selected_pair()]
        for label, role in zip(labels[1:], ("front", "reverse")):
            show(label, pair["images"][role]["path"], role.title())

    def swap():
        if selection["front"] or selection["reverse"]:
            selection["front"], selection["reverse"] = selection["reverse"], selection["front"]
            show(labels[1], selection["front"], "Front")
            show(labels[2], selection["reverse"], "Reverse")
        else:
            store.swap(selected_pair())
            refresh()
            display_pair()

    def review():
        pair_id = selected_pair()
        front, reverse = store.review_paths(pair_id)
        gui.import_coin_images_with_visual_ai(front_path=front, reverse_path=reverse,
            intake_context=(store, pair_id, str(Path(gui.app.collection.storage_path).absolute()), (front, reverse)))

    def reconcile():
        item_id = store.complete(selected_pair(), gui.app.collection.storage_path)
        status.set(f"Saved record {item_id} verified. No coin was created by recovery.")
        refresh()

    def next_pending():
        refresh()
        for pair_id, pair in store.records().items():
            if pair["state"] == "READY":
                pairs.selection_set(pair_id)
                pairs.see(pair_id)
                display_pair()
                return
        status.set("No ready pair. Pair more images or reconcile an unfinished save.")

    buttons = ttk.Frame(window)
    buttons.grid(row=3, column=0, columnspan=2, sticky="w", padx=10)
    for title, action in (("Use as Front", lambda: assign("front")), ("Use as Reverse", lambda: assign("reverse")),
                          ("Swap", swap), ("Confirm Pair", confirm), ("Review Pair", review),
                          ("Reconcile Save", reconcile), ("Next Pending", next_pending), ("Refresh", refresh)):
        ttk.Button(buttons, text=title, command=lambda action=action: safe(action)).pack(side=tk.LEFT, padx=2)
    files.bind("<<ListboxSelect>>", lambda event: safe(lambda: show(labels[0], paths[files.curselection()[0]], "Selected image")) if files.curselection() else None)
    pairs.bind("<<TreeviewSelect>>", lambda event: safe(display_pair) if pairs.selection() else None)
    safe(refresh)
    return window
