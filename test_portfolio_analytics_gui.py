import inspect
import unittest

from coin_collection import CoinItem
from coin_collection_gui import CoinCollectionGUI
from portfolio_performance import PortfolioPerformanceEngine


def make_item(item_id, **kwargs):
    return CoinItem(
        id=item_id,
        image_path="",
        country="Canada",
        denomination="1 cent",
        year="1967",
        grade="VF-20",
        notes="",
        date_added="2026-07-16",
        **kwargs,
    )


class PortfolioAnalyticsGUITests(unittest.TestCase):
    def test_summary_labels_currency_isolation_coverage_and_exclusions(self):
        summary = PortfolioPerformanceEngine([
            make_item("cad", estimate_cad=10, purchase_price="4", purchase_currency="CAD"),
            make_item("usd", estimate_cad=10, purchase_price="2", purchase_currency="USD"),
            make_item("missing", estimate_cad=0, purchase_currency=None),
        ]).portfolio_financial_summary()

        text = CoinCollectionGUI.portfolio_financial_summary_text(summary)
        self.assertIn("Acquisition-cost coverage: 66.7% (2/3)", text)
        self.assertIn("Usable legacy-estimate coverage: 66.7% (2/3)", text)
        self.assertIn("Acquisition-date coverage: 0.0% (0/3)", text)
        self.assertIn("Acquisition-source coverage: 0.0% (0/3)", text)
        self.assertIn("Recorded acquisition costs by currency (no conversion): CAD 4 | USD 2", text)
        self.assertIn("Approximate legacy estimated value", text)
        self.assertIn("Comparable CAD records: 1/3", text)
        self.assertIn("Primary comparison exclusions", text)

    def test_summary_represents_zero_denominator_roi_as_unavailable(self):
        summary = PortfolioPerformanceEngine([
            make_item("free", estimate_cad=10, purchase_price="0", purchase_currency="CAD"),
        ]).portfolio_financial_summary()

        text = CoinCollectionGUI.portfolio_financial_summary_text(summary)
        self.assertIn("Estimated gain/loss: CAD 10", text)
        self.assertIn("Estimated ROI: Unavailable", text)
        self.assertNotIn("Estimated ROI: 0%", text)

    def test_existing_surface_is_promoted_without_a_parallel_window(self):
        menu_source = inspect.getsource(CoinCollectionGUI.create_menu_bar)
        dialog_source = inspect.getsource(CoinCollectionGUI.open_portfolio_performance)

        self.assertIn('label="Portfolio Analytics"', menu_source)
        self.assertIn('dialog.title("Portfolio Analytics")', dialog_source)
        self.assertIn("PortfolioPerformanceEngine", dialog_source)
        self.assertNotIn("PortfolioDashboard(", dialog_source)


if __name__ == "__main__":
    unittest.main()
