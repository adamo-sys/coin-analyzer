import unittest

from hypothesis import given, strategies as st
from hypothesis.internal.conjecture.providers import _get_local_constants

from market_intelligence_automation import _dedupe
from photo_inbox import PhotoInboxConfig


class TestPropertyBasedQualityPilot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Prepare Hypothesis's source-constant cache outside timed generation.
        # Root discovery imports many local modules; scanning them on the first
        # draw can trigger too_slow even though the strategies themselves are fast.
        _get_local_constants()

    @given(st.lists(st.text(max_size=40), max_size=30))
    def test_dedupe_is_idempotent_and_case_insensitive(self, values):
        once = _dedupe(values)
        twice = _dedupe(once)
        self.assertEqual(once, twice)
        self.assertEqual(len(once), len({value.lower() for value in once}))
        self.assertTrue(all(value == value.strip() and value for value in once))


    @given(st.text(max_size=40))
    def test_extension_normalization_is_idempotent_and_canonical(self, value):
        once = PhotoInboxConfig._normalize_extension(value)
        twice = PhotoInboxConfig._normalize_extension(once)

        self.assertEqual(once, twice)

        if once:
            self.assertTrue(once.startswith("."))
            self.assertEqual(once, once.strip())
            self.assertEqual(once, once.lower())


if __name__ == "__main__":
    unittest.main()
