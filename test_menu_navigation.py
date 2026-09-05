import inspect
import unittest

from coin_collection_gui import CoinCollectionGUI


class MenuNavigationTests(unittest.TestCase):
    def test_tools_menu_is_grouped_into_expected_submenus(self):
        source = inspect.getsource(CoinCollectionGUI.create_menu_bar)

        for label in (
            "Session & Data",
            "Collection Intelligence",
            "OCR & AI",
            "Mobile & Sync",
            "Market & Deal Tools",
            "Platform & Diagnostics",
        ):
            self.assertIn(f'label="{label}"', source)

    def test_representative_commands_remain_wired_to_existing_handlers(self):
        source = inspect.getsource(CoinCollectionGUI.create_menu_bar)

        expected_pairs = (
            ('label="Save Session State"', "command=self.save_session_state"),
            ('label="Buy Advisor"', "command=self.open_buy_advisor"),
            ('label="OCR Experiment"', "command=self.open_ocr_experiment"),
            ('label="Mobile Collection Entry"', "command=self.open_mobile_collection_entry"),
            ('label="Market Intelligence Automation"', "command=self.open_market_intelligence_automation"),
            ('label="Platform Management"', "command=self.open_platform_management"),
        )

        for label, handler in expected_pairs:
            self.assertIn(label, source)
            self.assertIn(handler, source)

    def test_collector_companion_readiness_is_help_only(self):
        source = inspect.getsource(CoinCollectionGUI.create_menu_bar)

        self.assertEqual(source.count('label="Collector Companion Readiness"'), 1)
        self.assertIn(
            'help_menu.add_command(label="Collector Companion Readiness"',
            source,
        )
        self.assertIn(
            "command=self.open_collector_companion_readiness",
            source,
        )

    def test_existing_top_level_navigation_entries_remain_present(self):
        source = inspect.getsource(CoinCollectionGUI.create_menu_bar)

        for label in (
            "Import Collection CSV",
            "Collector Home Dashboard",
            "Acquisition Workflow",
            "Collection Dashboard",
        ):
            self.assertIn(f'label="{label}"', source)


if __name__ == "__main__":
    unittest.main()
