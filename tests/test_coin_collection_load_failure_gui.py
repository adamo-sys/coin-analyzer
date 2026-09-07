import unittest
from unittest.mock import Mock, patch

from coin_collection import CollectionLoadState
from coin_collection_gui import CoinCollectionGUI


class TestCoinCollectionLoadFailureGUI(unittest.TestCase):
    def make_gui(self, *, state, load_error=""):
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.root = object()

        collection = Mock()
        collection.load_state = state
        collection.load_error = load_error

        app = Mock()
        app.collection = collection
        gui.app = app

        return gui

    def test_failed_load_shows_recovery_required_message(self):
        gui = self.make_gui(
            state=CollectionLoadState.FAILED,
            load_error="invalid JSON",
        )

        with patch("coin_collection_gui.messagebox.showerror") as showerror:
            shown = gui.notify_collection_load_failure()

        self.assertTrue(shown)
        showerror.assert_called_once()

        title, detail = showerror.call_args.args
        self.assertEqual("Collection Recovery Required", title)
        self.assertIn("could not be loaded", detail)
        self.assertIn("blocked ordinary collection changes", detail)
        self.assertIn("invalid JSON", detail)
        self.assertIs(gui.root, showerror.call_args.kwargs["parent"])

    def test_missing_storage_does_not_show_error(self):
        gui = self.make_gui(state=CollectionLoadState.MISSING)

        with patch("coin_collection_gui.messagebox.showerror") as showerror:
            shown = gui.notify_collection_load_failure()

        self.assertFalse(shown)
        showerror.assert_not_called()

    def test_loaded_storage_does_not_show_error(self):
        gui = self.make_gui(state=CollectionLoadState.LOADED)

        with patch("coin_collection_gui.messagebox.showerror") as showerror:
            shown = gui.notify_collection_load_failure()

        self.assertFalse(shown)
        showerror.assert_not_called()


if __name__ == "__main__":
    unittest.main()