from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from capture_import.desktop_acceptance_canonicalization import (
    DEFAULT_POLICY_PATH,
    DesktopAcceptanceCanonicalizationError,
    canonicalize_complete_identity,
    canonicalize_country,
    canonicalize_denomination,
    canonicalize_year,
    complete_identities_equivalent,
    diagnostic_exact_identity_match,
    diagnostic_normalize,
    load_desktop_acceptance_canonicalization_policy,
)


class DesktopAcceptanceCanonicalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_desktop_acceptance_canonicalization_policy()

    def test_diagnostic_normalization_is_nfkc_space_and_case_only(self):
        self.assertEqual(diagnostic_normalize("  ＣＡＮ\t\n  Quarter!  "), "can quarter!")
        self.assertEqual(diagnostic_normalize("CAN."), "can.")
        self.assertNotEqual(diagnostic_normalize("CAN."), diagnostic_normalize("CAN"))

    def test_accepts_explicit_canada_aliases(self):
        for value in ("CAN", "canada", "  CaNaDa  ", "ＣＡＮ"):
            with self.subTest(value=value):
                self.assertEqual(canonicalize_country(value, self.policy), "CAN")

    def test_rejects_deliberately_unmapped_country_aliases(self):
        for value in ("CA", "CDN", "Canadian", "Canada!", "United States", None, ""):
            with self.subTest(value=value):
                self.assertIsNone(canonicalize_country(value, self.policy))

    def test_policy_version_cannot_silently_add_ca_alias(self):
        payload = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))
        payload["jurisdiction_aliases"].insert(
            0, {"normalized": "ca", "canonical": "CAN"}
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                DesktopAcceptanceCanonicalizationError, "frozen policy"
            ):
                load_desktop_acceptance_canonicalization_policy(path)

    def test_quarter_requires_independently_established_canadian_context(self):
        self.assertEqual(
            canonicalize_denomination("quarter", canonical_country="CAN", policy=self.policy),
            "25 cents",
        )
        for context in (None, "CA", "US"):
            with self.subTest(context=context):
                self.assertIsNone(canonicalize_denomination(
                    "quarter", canonical_country=context, policy=self.policy
                ))

    def test_maps_only_explicit_denomination_representations(self):
        for value in ("25 cents", "25 CENT", "quarter"):
            with self.subTest(value=value):
                self.assertEqual(canonicalize_denomination(
                    value, canonical_country="CAN", policy=self.policy
                ), "25 cents")
        for value in ("1/4 dollar", "0.25 dollar", "$0.25", "twenty-five cents", "25c"):
            with self.subTest(value=value):
                self.assertIsNone(canonicalize_denomination(
                    value, canonical_country="CAN", policy=self.policy
                ))

    def test_year_requires_four_ascii_gregorian_digits_after_nfkc(self):
        self.assertEqual(canonicalize_year("１９６４"), "1964")
        self.assertEqual(canonicalize_year(" 1964 "), "1964")
        for value in ("0000", "964", "01964", "1964-01", "MCMLXIV", 1964, None):
            with self.subTest(value=value):
                self.assertIsNone(canonicalize_year(value))

    def test_complete_identity_requires_all_three_mapped_fields(self):
        identity = {"country": "Canada", "denomination": "quarter", "year": "1964"}
        self.assertEqual(
            canonicalize_complete_identity(identity, self.policy).to_dict(),
            {"country": "CAN", "denomination": "25 cents", "year": "1964"},
        )
        for partial in (
            {"country": "Canada", "denomination": "quarter"},
            {"country": "CA", "denomination": "25 cents", "year": "1964"},
            {"country": "Canada", "denomination": "unknown", "year": "1964"},
        ):
            with self.subTest(partial=partial):
                self.assertIsNone(canonicalize_complete_identity(partial, self.policy))

    def test_authoritative_equivalence_and_exact_diagnostic_remain_separate(self):
        expected = {"country": "CAN", "denomination": "25 cents", "year": "1964"}
        alias = {"country": "Canada", "denomination": "quarter", "year": "１９６４"}
        self.assertTrue(complete_identities_equivalent(expected, alias, self.policy))
        self.assertFalse(diagnostic_exact_identity_match(expected, alias))
        self.assertTrue(diagnostic_exact_identity_match(
            expected, {"country": " can ", "denomination": "25 CENTS", "year": "1964"}
        ))

    def test_unknown_or_partial_proposal_never_receives_complete_credit(self):
        expected = {"country": "CAN", "denomination": "25 cents", "year": "1964"}
        for proposed in (
            {"country": "CAN", "denomination": "25 cents"},
            {"country": "CDN", "denomination": "25 cents", "year": "1964"},
            {"country": "CAN", "denomination": "1/4 dollar", "year": "1964"},
            None,
        ):
            with self.subTest(proposed=proposed):
                self.assertFalse(complete_identities_equivalent(expected, proposed, self.policy))


if __name__ == "__main__":
    unittest.main()
