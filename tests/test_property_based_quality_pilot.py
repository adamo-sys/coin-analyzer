import unittest

from hypothesis import given, strategies as st

from market_intelligence_automation import _dedupe


class TestPropertyBasedQualityPilot(unittest.TestCase):
    @given(st.lists(st.text(max_size=40), max_size=30))
    def test_dedupe_is_idempotent_and_case_insensitive(self, values):
        once = _dedupe(values)
        twice = _dedupe(once)
        self.assertEqual(once, twice)
        self.assertEqual(len(once), len({value.lower() for value in once}))
        self.assertTrue(all(value == value.strip() and value for value in once))


if __name__ == "__main__":
    unittest.main()
