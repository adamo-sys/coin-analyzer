"""Execute the ordinary advice renderers without creating a Tk window."""

import ast
import unittest
from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from buy_advisor import BuyAdvisor
from acquisition_workflow import AcquisitionWorkflow
from focused_collection_intelligence import CandidateItem, MatchStatus
from listing_analyzer import ListingAnalyzer, ListingCandidate
from shopping_explainability import ShoppingExplanationEngine


def nested_function(method, name, namespace):
    # Load only the actual renderer source: unrelated GUI bootstrap dependencies
    # are unnecessary for these in-memory callbacks.
    module = ast.parse(Path(__file__).with_name("coin_collection_gui.py").read_text(encoding="utf-8"))
    gui = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "CoinCollectionGUI")
    tree = next(node for node in gui.body if isinstance(node, ast.FunctionDef) and node.name == method)
    function = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.FunctionDef) and node.name == name)
    exec(compile(ast.Module(body=[function], type_ignores=[]), "<GUI callback>", "exec"), namespace)
    return namespace[name]


class Display:
    def __init__(self, *args, **kwargs):
        self.text = ""

    def title(self, *args):
        pass

    def geometry(self, *args):
        pass

    def pack(self, **kwargs):
        pass

    def config(self, **kwargs):
        pass

    def insert(self, position, text):
        self.text += text


class TestNullableAdviceGUI(unittest.TestCase):
    def recommendation(self):
        collection = SimpleNamespace(items=[], get_all_items=lambda: [])
        return BuyAdvisor(collection).advise("Canada", "dollar", "1936", asking_price=10, shipping=2)

    def render_buy(self, rec):
        output = Display()
        namespace = {
            "self": SimpleNamespace(app=SimpleNamespace(collection=SimpleNamespace(get_all_items=lambda: []))),
            "staged_want_list_intents": [], "dialog": None,
            "tk": SimpleNamespace(Toplevel=Display, Text=lambda *a, **k: output,
                                  WORD="word", BOTH="both", END="end", DISABLED="disabled"),
        }
        for name in ("asking_price", "shipping", "tax_fees", "estimated_value", "country",
                     "denom", "year", "ref", "numista", "grade"):
            namespace[name + "_var"] = SimpleNamespace(get=lambda: "")
        callback = nested_function("open_buy_advisor", "get_advice", namespace)
        with patch("buy_advisor.BuyAdvisor.advise", return_value=rec):
            callback()
        return output.text

    def test_buy_callback_unavailable_is_not_empty_matching_evidence(self):
        text = self.render_buy(self.recommendation())
        self.assertIn("Series Completion: unavailable", text)
        self.assertIn("Country Completion: unavailable", text)
        self.assertIn("Matching evidence unavailable", text)
        self.assertNotIn("No matching items found", text)
        self.assertIn("Max Rational Bid: unavailable", text)
        self.assertIn("Strategic Category: review required", text)
        self.assertIn("Landed Cost: $12.00", text)

    def test_buy_callback_supported_zero_and_positive(self):
        rec = self.recommendation()
        for number, percent, money in ((0, "0.0%", "$0.00"), (0.5, "50.0%", "$0.50")):
            with self.subTest(number=number):
                text = self.render_buy(replace(
                    rec, series_completion=number, country_completion=number, matching_items=[],
                    max_rational_bid=number, value_data_available=True, adam_priority_score=0,
                    liquidity_score=0, confidence_score=0, already_owned=False, duplicate_count=0,
                ))
                self.assertIn("Series Completion: " + percent, text)
                self.assertIn("Max Rational Bid: " + money, text)
                self.assertIn("No matching items found", text)
                self.assertIn("Already Owned: False", text)
                self.assertIn("Confidence Score: 0/100", text)

    def test_collection_intelligence_nullable_price_and_confidence(self):
        decision = AcquisitionWorkflow([]).evaluate(CandidateItem(asking_price=10))
        formatter = nested_function("open_collection_intelligence_lookup",
                                    "format_result", {"MatchStatus": MatchStatus})
        for value, rendered in ((None, "unavailable"), (0, "$0.00"), (12.5, "$12.50")):
            with self.subTest(value=value):
                text = formatter(decision.intelligence_result, replace(decision, max_rational_price=value))
                self.assertIn("Max Rational Price: " + rendered, text)
                self.assertIn("Asking Price: $10.00", text)
                self.assertIn("Confidence Score: unavailable", text)

    def test_listing_formatter_nullable_zero_and_positive_consequences(self):
        result = ListingAnalyzer([]).analyze(ListingCandidate("Canada dollar", price=10, shipping=2))
        formatter = nested_function("open_listing_analyzer", "format_listing_result",
                                    {"ShoppingExplanationEngine": ShoppingExplanationEngine})
        for value, signed, percent, money in ((None, "unavailable", "unavailable", "unavailable"),
                                            (0, "+0", "+0.0%", "$0.00"),
                                            (2, "+2", "+2.0%", "$2.00")):
            with self.subTest(value=value):
                text = formatter(replace(result, quality_impact=value, completion_impact=value,
                                         max_rational_price=value))
                self.assertIn("Quality Impact: " + signed, text)
                self.assertIn("Completion Impact: " + percent, text)
                self.assertIn("Max Rational Price: " + money, text)
                self.assertIn("Total Cost: $12.00", text)
                self.assertIn("Recommendation: REVIEW", text)


if __name__ == "__main__":
    unittest.main()
