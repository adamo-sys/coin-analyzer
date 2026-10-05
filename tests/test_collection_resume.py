"""Synthetic startup Collection projection behavior."""
import unittest
from coin_collection import IdentificationStatus
try:
    from collection_resume import collection_resume_rows
except ModuleNotFoundError:
    collection_resume_rows = None
from tests.test_collector_work_queue_gui import Collection, item

class CollectionResumeTests(unittest.TestCase):
    def test_unidentified_saved_coin_has_truthful_label_status_date_and_reference(self):
        self.assertIsNotNone(collection_resume_rows, 'Collection resume projection is missing')
        specimen = item('stable-id', title='Ignored title', quantity=99,
                        identification_status=IdentificationStatus.UNIDENTIFIED,
                        date_added='2026-10-04T23:59:00')
        collection = Collection([specimen])
        rows = collection_resume_rows(collection)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].label, rows[0].status, rows[0].recorded_date),
                         ('Unidentified coin', 'Unidentified', '2026-10-04'))
        self.assertIs(rows[0].reference.resolve(collection), specimen)

    def test_dates_are_calendar_newest_then_id_and_unknown_last(self):
        self.assertIsNotNone(collection_resume_rows)
        collection = Collection([item('z',date_added='2026-10-01T23:59'), item('b',date_added='2026-10-02 01:00'), item('a',date_added='2026-10-02T20:00'), item('bad',date_added='2026-02-30'), item('missing',date_added='')])
        rows = collection_resume_rows(collection)
        self.assertEqual([r.reference.item_id for r in rows], ['a','b','z','bad','missing'])
        self.assertEqual([r.recorded_date for r in rows], ['2026-10-02','2026-10-02','2026-10-01','Unknown','Unknown'])

    def test_failed_or_ambiguous_refuses_loaded_empty_and_missing_are_empty(self):
        self.assertIsNotNone(collection_resume_rows)
        from coin_collection import CollectionLoadState
        for state in (CollectionLoadState.LOADED, CollectionLoadState.MISSING):
            self.assertEqual(collection_resume_rows(Collection([],state)), ())
        for collection in (Collection([],CollectionLoadState.FAILED),Collection([item('same'),item('same')]),Collection([item('')])):
            with self.assertRaises(ValueError): collection_resume_rows(collection)

    def test_identified_partial_labels_and_no_task_record(self):
        self.assertIsNotNone(collection_resume_rows)
        rows = collection_resume_rows(Collection([item('a',title='Stored title'),item('b',country='Canada',denomination='',year='',identification_status=IdentificationStatus.PARTIAL)]))
        self.assertEqual([(r.label,r.status) for r in rows], [('Stored title','Identified'),('Canada','Partial')])
        self.assertIsNone(rows[0].task)
        self.assertEqual(rows[1].task.title,'Confirm identity')

    def test_photos_and_authoritative_order_not_mutated(self):
        self.assertIsNotNone(collection_resume_rows)
        from copy import deepcopy
        specimen = item('a',photos=[])
        specimen.photos = [{'path':'synthetic.jpg','role':'BACK','order':-9}]
        collection = Collection([item('z',date_added='2026-10-05'),specimen])
        before = deepcopy(collection.items); photo = specimen.photos[0]
        collection_resume_rows(collection)
        self.assertEqual(collection.items,before)
        self.assertIs(specimen.photos[0],photo)


class RevealTests(unittest.TestCase):
    def test_exact_reveal_overrides_old_filter_without_editor(self):
        from collection_item_reference import CollectionItemReference
        from collector_work_queue import derive_work_queue
        from collector_work_queue_gui import WorkQueueFilter
        from tests.test_collector_work_queue_gui import window_for
        collection = Collection([item('target',photos=[])])
        reference = CollectionItemReference.capture(collection,collection.items[0])
        task_id = derive_work_queue(collection).tasks[0].task_id
        window = window_for(collection)
        self.assertTrue(callable(getattr(window,'reveal_task',None)), 'Exact task reveal is missing')
        window.tree.selection_set = lambda row: setattr(window.tree,'selected',(row,))
        window.tree.see = lambda row: None
        window.tree.focus = lambda row: None
        window.tree.focus_set = lambda: None
        window.filter_var.set(WorkQueueFilter.ACQUISITION.value)
        self.assertTrue(window.reveal_task(reference,task_id))
        self.assertEqual(window._selected_task().task_id,task_id)
        self.assertIs(window._task_references[task_id],reference)
        window._open_editor.assert_not_called()

    def test_original_ref_or_resolved_task_refused(self):
        from collection_item_reference import CollectionItemReference
        from collector_work_queue import derive_work_queue
        from coin_collection import ItemType
        from tests.test_collector_work_queue_gui import window_for
        for change in ('replace','reload','duplicate','resolved'):
            with self.subTest(change=change):
                specimen = item('target',photos=[]); collection = Collection([specimen])
                reference = CollectionItemReference.capture(collection,specimen)
                task_id = derive_work_queue(collection).tasks[0].task_id
                window = window_for(collection)
                self.assertTrue(callable(getattr(window,'reveal_task',None)), 'Exact task reveal is missing')
                if change == 'replace': collection.items[:] = [item('target',photos=[])]
                elif change == 'reload': window._collection_provider = lambda: Collection([specimen])
                elif change == 'duplicate': collection.items.append(item('target',photos=[]))
                else: specimen.item_type = ItemType.BANKNOTE
                self.assertFalse(window.reveal_task(reference,task_id))
                window._open_editor.assert_not_called()


class CollectionControllerTests(unittest.TestCase):
    def gui(self, collection):
        from types import SimpleNamespace
        from coin_collection_gui import CoinCollectionGUI
        from tests.test_collector_work_queue_gui import Var, Tree, Button
        collection.get_all_items = lambda: list(collection.items)
        collection.search_items = lambda text: list(collection.items)
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.app = SimpleNamespace(collection=collection)
        class CompatibleTree(Tree):
            def insert(self, parent, where, iid=None, **options):
                return super().insert(parent, where, iid or f"row-{len(self.rows)}", **options)
        gui.collection_tree = CompatibleTree()
        gui.search_var = Var()
        gui.collection_resume_state_var = Var()
        gui.collection_task_var = Var()
        gui.show_collection_task_button = Button()
        return gui

    def test_record_count_and_distinct_load_states(self):
        from coin_collection import CollectionLoadState
        for state, text in ((CollectionLoadState.MISSING,'No collection'),(CollectionLoadState.FAILED,'unavailable'),(CollectionLoadState.LOADED,'0 collection records')):
            gui = self.gui(Collection([],state)); gui.refresh_collection_list()
            self.assertIn(text,gui.collection_resume_state_var.get())
        gui = self.gui(Collection([item('a',quantity=99),item('b')]))
        gui.refresh_collection_list()
        self.assertIn('2 collection records',gui.collection_resume_state_var.get())

    def test_selection_retains_display_ref_then_refuses_reused_id(self):
        from unittest.mock import Mock
        specimen=item('target',photos=[],identification_status=IdentificationStatus.PARTIAL)
        collection=Collection([specimen]); gui=self.gui(collection)
        gui.refresh_collection_list()
        gui.collection_tree.selected=(next(iter(gui.collection_tree.rows)),)
        collection.items[:]=[item('target',photos=[])]
        gui.on_collection_select(None)
        self.assertIn('changed',gui.collection_task_var.get())
        gui.open_work_queue=Mock()
        gui.show_collection_task()
        gui.open_work_queue.assert_not_called()

    def test_selection_current_first_task_and_resolved_show_refusal(self):
        from unittest.mock import Mock
        specimen=item('target',photos=[],identification_status=IdentificationStatus.PARTIAL)
        collection=Collection([specimen]); gui=self.gui(collection)
        gui.refresh_collection_list()
        gui.collection_tree.selected=(next(iter(gui.collection_tree.rows)),)
        gui.on_collection_select(None)
        self.assertIn('Maintenance task: Confirm identity',gui.collection_task_var.get())
        specimen.identification_status=IdentificationStatus.IDENTIFIED
        gui.open_work_queue=Mock()
        gui.show_collection_task()
        gui.open_work_queue.assert_not_called()
        self.assertIn('changed',gui.collection_task_var.get())

    def test_no_task_selected_record_remains_usable(self):
        gui=self.gui(Collection([item('done')]))
        gui.refresh_collection_list()
        gui.collection_tree.selected=(next(iter(gui.collection_tree.rows)),)
        gui.on_collection_select(None)
        self.assertIn('No current Work Queue tasks',gui.collection_task_var.get())
        self.assertEqual(gui.show_collection_task_button.options['state'],'disabled')


class AdditionalResumeTests(unittest.TestCase):
    gui = CollectionControllerTests.gui
    def test_two_unidentified_records_stay_distinct_and_keep_original_reveal_reference(self):
        from tests.test_collector_work_queue_gui import window_for
        collection=Collection([item('first',identification_status=IdentificationStatus.UNIDENTIFIED),item('second',identification_status=IdentificationStatus.UNIDENTIFIED)])
        gui=self.gui(collection); gui.refresh_collection_list()
        self.assertEqual([r['values'][0] for r in gui.collection_tree.rows.values()],['first','second'])
        self.assertEqual([r['values'][1] for r in gui.collection_tree.rows.values()],['Unidentified coin','Unidentified coin'])
        row_id=next(iter(gui.collection_tree.rows)); original=gui._collection_resume_rows[row_id].reference
        gui.collection_tree.selected=(row_id,);gui.on_collection_select(None)
        queue=window_for(collection)
        queue.tree.selection_set=lambda row:setattr(queue.tree,'selected',(row,))
        queue.tree.see=lambda row:None;queue.tree.focus=lambda row:None;queue.tree.focus_set=lambda:None
        gui.open_work_queue=lambda:queue
        gui.show_collection_task()
        task_id=queue._selected_task().task_id
        self.assertIs(queue._task_references[task_id],original)
        queue._open_editor.assert_not_called()

    def test_mismatched_other_item_task_cannot_be_revealed(self):
        from tests.test_collector_work_queue_gui import window_for
        from collection_item_reference import CollectionItemReference
        from collector_work_queue import derive_work_queue
        collection=Collection([item('a',photos=[]),item('b',photos=[])])
        queue=window_for(collection)
        self.assertTrue(callable(getattr(queue,'reveal_task',None)))
        reference=CollectionItemReference.capture(collection,collection.items[0])
        task_id=next(t.task_id for t in derive_work_queue(collection).tasks if t.item_id=='b')
        self.assertFalse(queue.reveal_task(reference,task_id))
        queue._open_editor.assert_not_called()

    def test_render_never_normalizes_photos_serializes_or_persists(self):
        from unittest.mock import patch
        from coin_collection import CoinItem
        self.assertIsNotNone(collection_resume_rows)
        collection=Collection([item('synthetic',photos=[])])
        def forbidden(*args,**kwargs): raise AssertionError('Forbidden render side effect')
        collection.save_collection=forbidden
        collection.reconcile=forbidden
        with patch.object(CoinItem,'normalized_photos',forbidden),patch.object(CoinItem,'primary_photo',forbidden),patch.object(CoinItem,'to_dict',forbidden):
            gui=self.gui(collection);gui.refresh_collection_list()
            self.assertEqual(len(gui.collection_tree.rows),1)
