"""Regression tests for the main collection table layout."""

import ast
import inspect
import textwrap
import unittest

from coin_collection_gui import CoinCollectionGUI


class CollectionLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = textwrap.dedent(inspect.getsource(CoinCollectionGUI.create_widgets))
        cls.tree = ast.parse(source)

    def _calls(self, object_name, method_name):
        calls = []
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            owner = node.func.value
            if (
                node.func.attr == method_name
                and isinstance(owner, ast.Name)
                and owner.id == object_name
            ):
                calls.append(node)
        return calls

    @staticmethod
    def _keyword(call, name):
        keyword = next(item for item in call.keywords if item.arg == name)
        return ast.literal_eval(keyword.value)

    def test_toolbar_sits_between_search_and_expandable_collection_table(self):
        search_grid = self._calls("search_frame", "grid")[0]
        toolbar_grid = self._calls("collection_buttons", "grid")[0]
        list_grid = self._calls("list_frame", "grid")[0]

        self.assertEqual(0, self._keyword(search_grid, "row"))
        self.assertEqual(1, self._keyword(toolbar_grid, "row"))
        self.assertEqual(2, self._keyword(list_grid, "row"))
        self.assertEqual((0, 10), self._keyword(toolbar_grid, "pady"))

        row_configure = self._calls("collection_frame", "rowconfigure")
        self.assertTrue(
            any(ast.literal_eval(call.args[0]) == 2 and self._keyword(call, "weight") == 1
                for call in row_configure)
        )

    def test_collection_toolbar_preserves_button_order_and_commands(self):
        expected = [
            ("View Details", "view_item_details"),
            ("Edit Item", "edit_item"),
            ("Delete Item", "delete_item"),
            ("Buy Advisor", "open_buy_advisor"),
            ("Import Numista", "import_numista"),
            ("Analyze Collection", "analyze_collection"),
            ("Gap Report", "open_collection_gap_report"),
            ("Export CSV", "export_csv"),
        ]
        actual = []
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            button_call = node.func.value
            if node.func.attr != "pack" or not isinstance(button_call, ast.Call):
                continue
            if not button_call.args or not isinstance(button_call.args[0], ast.Name):
                continue
            if button_call.args[0].id != "collection_buttons":
                continue
            keywords = {keyword.arg: keyword.value for keyword in button_call.keywords}
            actual.append((
                ast.literal_eval(keywords["text"]),
                keywords["command"].attr,
            ))

        self.assertEqual(expected, actual)

    def test_photo_and_detection_column_is_vertically_scrollable(self):
        canvas_calls = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "tk"
            and node.func.attr == "Canvas"
        ]
        self.assertEqual(1, len(canvas_calls))

        create_window_calls = self._calls("left_canvas", "create_window")
        self.assertEqual(1, len(create_window_calls))
        window_keyword = next(
            keyword for keyword in create_window_calls[0].keywords if keyword.arg == "window"
        )
        self.assertIsInstance(window_keyword.value, ast.Name)
        self.assertEqual("left_panel", window_keyword.value.id)

        scrollbar_calls = [
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "ttk"
            and node.func.attr == "Scrollbar"
        ]
        self.assertTrue(
            any(
                any(
                    keyword.arg == "command"
                    and isinstance(keyword.value, ast.Attribute)
                    and isinstance(keyword.value.value, ast.Name)
                    and keyword.value.value.id == "left_canvas"
                    and keyword.value.attr == "yview"
                    for keyword in call.keywords
                )
                for call in scrollbar_calls
            )
        )


if __name__ == "__main__":
    unittest.main()
