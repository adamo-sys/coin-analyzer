"""Exercise the real Buy Advisor form callback with synthetic widget boundaries."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from buy_advisor import BuyAdvisor
from coin_collection_gui import CoinCollectionGUI


class Variable:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class BuyAdvisorInputValidationTests(unittest.TestCase):
    def setUp(self):
        self.variables = []
        self.entries = []
        self.buttons = {}
        self.windows = []

        def variable(value=""):
            result = Variable(value)
            self.variables.append(result)
            return result

        def entry(*args, **kwargs):
            result = MagicMock()
            result.variable = kwargs["textvariable"]
            self.entries.append(result)
            return result

        def button(*args, **kwargs):
            self.buttons[kwargs["text"]] = kwargs["command"]
            return MagicMock()

        def window(*args):
            result = MagicMock()
            self.windows.append(result)
            return result

        # Keep form composition and its actual registered callback. Replace only
        # native widget/message boundaries; never construct the live application.
        for target, replacement in (
            ("coin_collection_gui.tk.StringVar", variable),
            ("coin_collection_gui.tk.Toplevel", window),
            ("coin_collection_gui.tk.Text", MagicMock()),
            ("coin_collection_gui.ttk.Frame", MagicMock()),
            ("coin_collection_gui.ttk.Label", MagicMock()),
            ("coin_collection_gui.ttk.Entry", entry),
            ("coin_collection_gui.ttk.Combobox", entry),
            ("coin_collection_gui.ttk.Button", button),
        ):
            patcher = patch(target, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.messages = self.enterContext(patch("coin_collection_gui.messagebox.showerror"))
        collection = SimpleNamespace(items=[], get_all_items=list)
        recommendation = BuyAdvisor(collection).advise("Canada", "dollar", "1936")
        self.advisor = self.enterContext(patch("buy_advisor.BuyAdvisor"))
        self.advisor.return_value.advise.return_value = recommendation
        gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
        gui.root = MagicMock()
        gui.app = SimpleNamespace(collection=collection)
        gui._active_want_list_intents = list
        gui.open_buy_advisor()
        self.identity = self.variables[:6]
        self.money = self.variables[6:10]
        self.money_entries = self.entries[6:10]
        for variable, value in zip(self.identity, ("Canada", "dollar", "1936", "ref", "123", "VF-20")):
            variable.set(value)

    def submit(self):
        self.buttons["Get Advice"]()

    def assert_rejected(self, index, value, label):
        self.money[index].set(value)
        before = [variable.get() for variable in self.variables]
        self.submit()
        self.advisor.assert_not_called()
        self.messages.assert_called_once()
        self.assertIn(label.lower(), self.messages.call_args.args[1].lower())
        self.money_entries[index].focus_set.assert_called_once()
        self.assertEqual([variable.get() for variable in self.variables], before)
        self.assertEqual(len(self.windows), 1)
        self.windows[0].destroy.assert_not_called()

    def test_valid_numeric_conversion_preserves_identity_and_values(self):
        for values, expected in (
            (("12.50", "2", "0.75", "2e2"), (12.5, 2.0, 0.75, 200.0)),
            ((" -1 ", "+2.5", "0", "1_000"), (-1.0, 2.5, 0.0, 1000.0)),
        ):
            with self.subTest(values=values):
                self.advisor.reset_mock()
                for variable, value in zip(self.money, values):
                    variable.set(value)
                self.submit()
                self.advisor.return_value.advise.assert_called_once_with(
                    "Canada", "dollar", "1936", "ref", "123", "VF-20",
                    asking_price=expected[0], shipping=expected[1],
                    tax_fees=expected[2], estimated_market_value=expected[3],
                )
                self.assertEqual(tuple(variable.get() for variable in self.money), values)
        self.messages.assert_not_called()

    def test_empty_fields_keep_zero_defaults(self):
        self.submit()
        self.assertEqual(self.advisor.return_value.advise.call_args.kwargs, {
            "asking_price": 0.0, "shipping": 0.0,
            "tax_fees": 0.0, "estimated_market_value": 0.0,
        })
        self.messages.assert_not_called()

    def test_invalid_asking_price(self):
        self.assert_rejected(0, "twelve", "asking price")

    def test_invalid_shipping(self):
        self.assert_rejected(1, "$5", "shipping")

    def test_invalid_tax_fees(self):
        self.assert_rejected(2, "1,2", "tax/fees")

    def test_invalid_estimated_value(self):
        self.assert_rejected(3, "unknown", "estimated value")

    def test_nonfinite_values_in_every_field(self):
        labels = ("asking price", "shipping", "tax/fees", "estimated value")
        for index, label in enumerate(labels):
            for value in ("NaN", "inf", "+Infinity", "-Infinity", "1e999"):
                with self.subTest(field=label, value=value):
                    self.advisor.reset_mock()
                    self.messages.reset_mock()
                    for entry in self.money_entries:
                        entry.reset_mock()
                    for variable in self.money:
                        variable.set("")
                    self.assert_rejected(index, value, label)

    def test_correction_retries_same_form_and_preserves_other_fields(self):
        for variable, value in zip(self.money, ("25", "bad", "3", "40")):
            variable.set(value)
        self.assert_rejected(1, "bad", "shipping")
        self.money[1].set("2.5")
        self.submit()
        self.advisor.return_value.advise.assert_called_once_with(
            "Canada", "dollar", "1936", "ref", "123", "VF-20",
            asking_price=25.0, shipping=2.5, tax_fees=3.0, estimated_market_value=40.0,
        )
        self.assertEqual(len(self.windows), 2)
        self.assertEqual([variable.get() for variable in self.money], ["25", "2.5", "3", "40"])


if __name__ == "__main__":
    unittest.main()
