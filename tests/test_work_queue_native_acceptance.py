"""Opt-in real Tk widgets/editor/persistence acceptance using synthetic data."""
import os
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import Mock, patch

from coin_collection import CoinCollection, CoinCollectionApp, IdentificationStatus, PhotoRole
from coin_collection_gui import CoinCollectionGUI
from collector_work_queue import derive_work_queue
from collector_work_queue_gui import WorkQueueFilter
from tests.test_collector_work_queue import make_item


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


@unittest.skipUnless(os.environ.get('RUN_WORK_QUEUE_NATIVE') == '1', 'Opt-in native Tk acceptance')
class NativeWorkQueueAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)
        self.root.title('Synthetic Work Queue acceptance')
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(args)
        self.path = Path(self.temp.name) / 'collection.json'
        self.collection = CoinCollection(str(self.path))
        self.item = make_item('synthetic', country='', photos=[], shipping_cost=Decimal('1'),
                              identification_status=IdentificationStatus.PARTIAL)
        self.assertTrue(self.collection.add_item(self.item))
        self.gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        self.gui.root = self.root
        self.gui.app = CoinCollectionApp(self.collection)
        self.gui.refresh_collection_list = Mock()
        self.queue = self.gui.open_work_queue()
        for name in ('showinfo', 'showwarning', 'showerror'):
            mocked = patch('coin_collection_gui.messagebox.' + name).start()
            self.addCleanup(patch.stopall)
            setattr(self, name, mocked)
        self.root.update()
        self.assertTrue(self.queue.window.winfo_ismapped())

    def button(self, parent, text):
        return next(w for w in descendants(parent) if isinstance(w, ttk.Button) and w.cget('text') == text)

    def open_task(self, category):
        self.queue.filter_buttons[category].invoke()
        self.root.update()
        row = self.queue.tree.get_children()[0]
        self.queue.tree.selection_set(row)
        self.queue.tree.event_generate('<<TreeviewSelect>>')
        self.root.update()
        self.queue.action_button.invoke()
        self.root.update()
        self.assertFalse(self.errors)
        return next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel) and w.title() == 'Edit Item')

    def set_field(self, dialog, label, value, below=False):
        widget = next(w for w in descendants(dialog) if isinstance(w, ttk.Label) and w.cget('text') == label)
        grid = widget.grid_info()
        row, col = int(grid['row']), int(grid['column'])
        entry = widget.master.grid_slaves(row=row + int(below), column=col + int(not below))[0]
        entry.delete(0, tk.END)
        entry.insert(0, value)

    def test_real_editor_save_media_and_reopen(self):
        self.assertEqual(len(self.queue._projection.tasks), 3)
        self.assertIs(self.gui.open_work_queue(), self.queue)
        dialog = self.open_task(WorkQueueFilter.IDENTITY)
        self.set_field(dialog, 'Country:', 'Canada')
        self.button(dialog, 'Save').invoke()
        self.root.update()
        self.assertFalse(self.errors)
        self.assertIs(self.item.identification_status, IdentificationStatus.IDENTIFIED)
        self.assertEqual(len(self.queue._projection.tasks), 2)

        dialog = self.open_task(WorkQueueFilter.ACQUISITION)
        before = self.path.read_bytes()
        self.set_field(dialog, 'Price:', '0', below=True)
        with patch.object(self.collection, 'save_collection', return_value=False):
            self.button(dialog, 'Save').invoke()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertTrue(dialog.winfo_exists())
        self.showerror.assert_called_once()
        self.assertEqual(len(self.queue._projection.tasks), 2)
        self.button(dialog, 'Save').invoke()
        self.root.update()
        self.assertEqual(self.item.purchase_price, Decimal('0'))

        dialog = self.open_task(WorkQueueFilter.PHOTOS)
        source = Path(self.temp.name) / 'synthetic.png'
        from PIL import Image
        Image.new('RGB', (8, 8), 'gray').save(source)
        with patch('coin_collection_gui.filedialog.askopenfilenames', return_value=(str(source),)):
            self.button(dialog, 'Add Photos').invoke()
        role = next(w for w in descendants(dialog) if isinstance(w, ttk.Combobox) and 'BACK' in w.cget('values'))
        role.set('BACK')
        role.event_generate('<<ComboboxSelected>>')
        self.root.update()
        self.button(dialog, 'Save').invoke()
        self.root.update()
        self.assertFalse(self.errors)
        self.assertEqual(len(self.queue._projection.tasks), 0)
        managed = Path(self.item.photos[0].path)
        self.assertNotEqual(managed, source)
        self.assertEqual(managed.read_bytes(), source.read_bytes())
        reopened = CoinCollection(str(self.path))
        self.assertEqual(derive_work_queue(reopened).tasks, ())
        self.assertEqual(reopened.items[0].photos[0].role, PhotoRole.BACK)
        self.queue.close()
        self.gui.app.collection = reopened
        self.queue = self.gui.open_work_queue()
        self.root.update()
        self.assertIn('Nothing needs attention', self.queue.state_var.get())

    def test_stale_native_selection_refuses_replacement(self):
        row = self.queue.tree.get_children()[0]
        self.queue.tree.selection_set(row)
        self.queue.on_selection_changed()
        self.gui.app.collection = CoinCollection(str(self.path))
        self.queue.action_button.invoke()
        self.root.update()
        self.assertFalse(self.errors)
        self.assertIn('stale', self.queue.status_var.get())
        self.assertFalse(any(isinstance(w, tk.Toplevel) and w.title() == 'Edit Item'
                             for w in self.root.winfo_children()))
