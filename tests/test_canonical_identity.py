from __future__ import annotations

from fractions import Fraction
import unittest

from capture_import.canonical_identity import (
    CanonicalizationStatus,
    canonicalize_denomination,
    canonicalize_jurisdiction,
)


class CanonicalJurisdictionTests(unittest.TestCase):
    def test_safe_country_aliases_share_one_canonical_identity(self) -> None:
        canonical = canonicalize_jurisdiction("United States")
        for raw in ("United States of America", "USA", "U.S.A."):
            with self.subTest(raw=raw):
                result = canonicalize_jurisdiction(raw)
                self.assertEqual(result.canonical_value, canonical.canonical_value)
                self.assertEqual(result.raw_value, raw)
                self.assertTrue(result.is_mapped)
                self.assertTrue(result.normalization_rules)

    def test_case_punctuation_and_whitespace_are_deterministic(self) -> None:
        first = canonicalize_jurisdiction("  UNITED STATES OF AMERICA! ")
        second = canonicalize_jurisdiction("  UNITED STATES OF AMERICA! ")
        self.assertEqual(first, second)
        self.assertEqual(first.canonical_value.canonical_id, "US")

    def test_historical_or_substantive_country_relations_are_not_mapped(self) -> None:
        for raw in (
            "British India",
            "India",
            "United Kingdom (Australia)",
            "Australia",
            "Belgium",
            "Congo Free State",
        ):
            with self.subTest(raw=raw):
                result = canonicalize_jurisdiction(raw)
                self.assertEqual(result.status, CanonicalizationStatus.UNMAPPED)
                self.assertIsNone(result.canonical_value)
                self.assertEqual(result.raw_value, raw)

    def test_fuzzy_country_spelling_is_rejected(self) -> None:
        self.assertFalse(canonicalize_jurisdiction("Untied States").is_mapped)


class CanonicalDenominationTests(unittest.TestCase):
    def assertDenomination(self, raw, value, unit, display, **kwargs) -> None:
        result = canonicalize_denomination(raw, **kwargs)
        self.assertTrue(result.is_mapped)
        self.assertEqual(result.raw_value, raw)
        self.assertEqual(result.canonical_value.numeric_value, Fraction(value))
        self.assertEqual(result.canonical_value.unit_id, unit)
        self.assertEqual(result.canonical_value.display_name, display)
        self.assertTrue(result.normalization_rules)

    def test_word_to_number_and_plural_normalization(self) -> None:
        self.assertDenomination("One Rupee", 1, "rupee", "1 rupee")
        self.assertDenomination("Two cents", 2, "cent", "2 cents")
        self.assertEqual(
            canonicalize_denomination("1 rupees").canonical_value,
            canonicalize_denomination("one rupee").canonical_value,
        )

    def test_fraction_and_unicode_fraction_normalization(self) -> None:
        expected = canonicalize_denomination("1/2 dollar")
        for raw in ("Half Dollar", "½ dollar"):
            with self.subTest(raw=raw):
                self.assertEqual(
                    canonicalize_denomination(raw).canonical_value,
                    expected.canonical_value,
                )
        self.assertEqual(expected.canonical_value.display_name, "1/2 dollar")

    def test_compound_sixpence_is_a_controlled_equivalence(self) -> None:
        self.assertEqual(
            canonicalize_denomination("Sixpence").canonical_value,
            canonicalize_denomination("6 pence").canonical_value,
        )

    def test_piso_alias_requires_explicit_philippine_context(self) -> None:
        piso = canonicalize_denomination("10 piso", jurisdiction_id="PH")
        pesos = canonicalize_denomination("10 pesos", jurisdiction_id="PH")
        self.assertEqual(piso.canonical_value, pesos.canonical_value)
        self.assertIn("denomination.unit-alias.ph-piso-peso", piso.normalization_rules)
        self.assertFalse(canonicalize_denomination("10 piso").is_mapped)

    def test_raw_value_and_rule_provenance_serialize(self) -> None:
        result = canonicalize_denomination("Two cents")
        serialized = result.to_dict()
        self.assertEqual(serialized["raw_value"], "Two cents")
        self.assertEqual(serialized["status"], "MAPPED")
        self.assertIn("denomination.number-word", serialized["normalization_rules"])
        self.assertEqual(
            serialized["canonical_value"]["numeric_value"],
            {"numerator": 2, "denominator": 1},
        )

    def test_unknown_ambiguous_and_fuzzy_values_remain_unmapped(self) -> None:
        for raw in (
            None,
            "",
            "ten-ish dollars",
            "1 doller",
            "10 naye paise",
            "half sovereign",
        ):
            with self.subTest(raw=raw):
                result = canonicalize_denomination(raw)
                self.assertEqual(result.status, CanonicalizationStatus.UNMAPPED)
                self.assertIsNone(result.canonical_value)
                self.assertEqual(result.raw_value, raw)
                self.assertEqual(result.normalization_rules, ())

    def test_unrelated_units_are_not_merged(self) -> None:
        self.assertNotEqual(
            canonicalize_denomination("1 franc").canonical_value,
            canonicalize_denomination("1 dollar").canonical_value,
        )

    def test_output_is_immutable_and_deterministic(self) -> None:
        first = canonicalize_denomination(" TWO   CENTS. ")
        second = canonicalize_denomination(" TWO   CENTS. ")
        self.assertEqual(first, second)
        with self.assertRaises(AttributeError):
            first.raw_value = "changed"


if __name__ == "__main__":
    unittest.main()
