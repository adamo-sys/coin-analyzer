from __future__ import annotations

from dataclasses import FrozenInstanceError
import ast
import inspect
from pathlib import Path
import unicodedata
import unittest

import capture_import.workflow_confirmed_observation_mintmark_rules as module
from capture_import.workflow_confirmed_observation_mintmark_rules import (
    AmbiguousMintmarkRuleError,
    DuplicateMintmarkRuleError,
    InvalidMintmarkRuleContextError,
    MintmarkRule,
    MintmarkRuleCatalog,
    MintmarkRuleContractError,
)


PUBLIC_API = {
    "MintmarkRuleContractError",
    "InvalidMintmarkRuleContextError",
    "DuplicateMintmarkRuleError",
    "AmbiguousMintmarkRuleError",
    "MintmarkRule",
    "MintmarkRuleCatalog",
}


def rule(
    rule_id: str = "mintmark.canada.1-cent-v1",
    *,
    country: str = "Canada",
    denomination: str = "1 Cent",
    series_type: str | None = None,
    year: int | None = None,
    monarch: str | None = None,
    mintmark: str = "P",
) -> MintmarkRule:
    return MintmarkRule(
        rule_id=rule_id,
        country=country,
        denomination=denomination,
        series_type=series_type,
        year=year,
        monarch=monarch,
        mintmark=mintmark,
    )


class PublicAPITests(unittest.TestCase):
    def test_exact_exported_api(self) -> None:
        self.assertEqual(set(module.__all__), PUBLIC_API)

    def test_exact_module_defined_public_names(self) -> None:
        defined = {
            name
            for name, value in vars(module).items()
            if not name.startswith("_")
            and (
                inspect.isclass(value)
                or inspect.isfunction(value)
            )
            and getattr(value, "__module__", None) == module.__name__
        }
        self.assertEqual(defined, PUBLIC_API)

    def test_no_evaluator_or_storage_api(self) -> None:
        prohibited = {
            "assess_mintmark",
            "evaluate_mintmark",
            "find_rule",
            "default_catalog",
            "to_dict",
            "from_dict",
            "save",
            "load",
            "serialize",
            "deserialize",
        }
        self.assertTrue(prohibited.isdisjoint(vars(module)))

    def test_no_global_catalog_or_rules(self) -> None:
        for name, value in vars(module).items():
            if name.startswith("_"):
                continue
            self.assertNotIsInstance(value, MintmarkRule)
            self.assertNotIsInstance(value, MintmarkRuleCatalog)


class ErrorHierarchyTests(unittest.TestCase):
    def test_exact_hierarchy(self) -> None:
        self.assertTrue(issubclass(MintmarkRuleContractError, ValueError))
        for error_type in (
            InvalidMintmarkRuleContextError,
            DuplicateMintmarkRuleError,
            AmbiguousMintmarkRuleError,
        ):
            self.assertIs(error_type.__base__, MintmarkRuleContractError)

    def test_errors_have_no_mutable_public_attributes(self) -> None:
        for error_type in (
            MintmarkRuleContractError,
            InvalidMintmarkRuleContextError,
            DuplicateMintmarkRuleError,
            AmbiguousMintmarkRuleError,
        ):
            error = error_type("bounded")
            with self.assertRaises(AttributeError):
                error.detail = "changed"  # type: ignore[attr-defined]

    def test_error_attributes_are_immutable(self) -> None:
        error = DuplicateMintmarkRuleError("bounded")
        with self.assertRaises(AttributeError):
            error.extra = "value"  # type: ignore[attr-defined]
        with self.assertRaises(AttributeError):
            error.args = ("changed",)


class RuleIdentifierTests(unittest.TestCase):
    def test_accepts_shortest_and_longest_ids(self) -> None:
        self.assertEqual(rule("a").rule_id, "a")
        longest = "a" + ("0" * 127)
        self.assertEqual(rule(longest).rule_id, longest)

    def test_accepts_opaque_punctuation(self) -> None:
        self.assertEqual(
            rule("mintmark.canada_1-cent-v1").rule_id,
            "mintmark.canada_1-cent-v1",
        )

    def test_rejects_malformed_ids(self) -> None:
        invalid = (
            "",
            "A",
            "1rule",
            "mint mark",
            "mint/mark",
            r"mint\mark",
            "mint:mark",
            "https://mintmark",
            "mint\nmark",
            "a" * 129,
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    InvalidMintmarkRuleContextError,
                    "rule_id must match",
                ):
                    rule(value)

    def test_rejects_non_string_ids(self) -> None:
        for value in (None, 1, True, b"a"):
            with self.subTest(value=value):
                with self.assertRaises(InvalidMintmarkRuleContextError):
                    rule(value)  # type: ignore[arg-type]

    def test_does_not_trim_or_normalize_id(self) -> None:
        with self.assertRaises(InvalidMintmarkRuleContextError):
            rule(" mintmark")
        with self.assertRaises(InvalidMintmarkRuleContextError):
            rule("mintmark ")


class ScopeTextTests(unittest.TestCase):
    def test_preserves_exact_scope_values(self) -> None:
        value = rule(
            country="Côte d'Ivoire",
            denomination="$2.50",
            series_type="Type II — Proof-Like",
            monarch="Charles III",
            mintmark="P",
        )
        self.assertEqual(value.country, "Côte d'Ivoire")
        self.assertEqual(value.denomination, "$2.50")
        self.assertEqual(value.series_type, "Type II — Proof-Like")
        self.assertEqual(value.monarch, "Charles III")

    def test_none_series_year_and_monarch_are_valid(self) -> None:
        value = rule(series_type=None, year=None, monarch=None)
        self.assertIsNone(value.series_type)
        self.assertIsNone(value.year)
        self.assertIsNone(value.monarch)

    def test_accepts_128_character_scope_values(self) -> None:
        maximum = "é" * 128
        value = rule(
            country=maximum,
            denomination=maximum,
            series_type=maximum,
            monarch=maximum,
            mintmark=maximum,
        )
        self.assertEqual(value.country, maximum)
        self.assertEqual(value.denomination, maximum)
        self.assertEqual(value.series_type, maximum)
        self.assertEqual(value.monarch, maximum)

    def test_rejects_invalid_country(self) -> None:
        self._assert_invalid_text("country")

    def test_rejects_invalid_denomination(self) -> None:
        self._assert_invalid_text("denomination")

    def test_rejects_invalid_series_type(self) -> None:
        self._assert_invalid_text("series_type")

    def test_rejects_invalid_monarch(self) -> None:
        self._assert_invalid_text("monarch")

    def test_rejects_non_nfc_without_normalizing(self) -> None:
        decomposed = unicodedata.normalize("NFD", "Montréal")
        for field_name in (
            "country",
            "denomination",
            "series_type",
            "monarch",
        ):
            with self.subTest(field_name=field_name):
                kwargs = {field_name: decomposed}
                with self.assertRaisesRegex(
                    InvalidMintmarkRuleContextError,
                    "NFC-normalized",
                ):
                    rule(**kwargs)  # type: ignore[arg-type]

    def test_scope_values_are_case_sensitive(self) -> None:
        upper = rule("a", country="Canada")
        lower = rule("b", country="canada")
        catalog = MintmarkRuleCatalog((upper, lower))
        self.assertIs(catalog.rules[0], upper)
        self.assertIs(catalog.rules[1], lower)

    def _assert_invalid_text(self, field_name: str) -> None:
        invalid = (
            "",
            " ",
            " Canada",
            "Canada ",
            "Can\nada",
            "Can\tada",
            "Can\x00ada",
            "Can\x85ada",
            "Can\ud800ada",
            "x" * 129,
            1,
            True,
            b"Canada",
        )
        for value in invalid:
            with self.subTest(field_name=field_name, value=value):
                kwargs = {field_name: value}
                with self.assertRaises(InvalidMintmarkRuleContextError):
                    rule(**kwargs)  # type: ignore[arg-type]


class YearTests(unittest.TestCase):
    def test_accepts_single_and_structural_bounds(self) -> None:
        self.assertIs(rule(year=1000).year, 1000)
        self.assertIs(rule(year=2999).year, 2999)
        self.assertIs(rule(year=1920).year, 1920)

    def test_rejects_out_of_bounds_years(self) -> None:
        for value in (999, 3000):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    InvalidMintmarkRuleContextError,
                    "between 1000 and 2999",
                ):
                    rule(year=value)

    def test_rejects_non_integer_years(self) -> None:
        for value in (True, 1967.0, "1967"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    InvalidMintmarkRuleContextError,
                    "exact integer",
                ):
                    rule(year=value)  # type: ignore[arg-type]


class MintmarkTests(unittest.TestCase):
    def test_preserves_exact_mintmark_token(self) -> None:
        value = rule(mintmark="P")
        self.assertEqual(value.mintmark, "P")
        self.assertEqual(rule(mintmark="P.").mintmark, "P.")

    def test_rejects_empty_marker_aliases(self) -> None:
        for value in ("none", "no mintmark"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    InvalidMintmarkRuleContextError,
                    "empty-marker alias",
                ):
                    rule(mintmark=value)

    def test_rejects_invalid_mintmark_text(self) -> None:
        invalid = (
            "",
            " ",
            " P",
            "P ",
            "P\n",
            "P\t",
            "P\x00",
            "P\ud800",
            "x" * 129,
            1,
            True,
            b"P",
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(InvalidMintmarkRuleContextError):
                    rule(mintmark=value)  # type: ignore[arg-type]


class MintmarkRuleCatalogTests(unittest.TestCase):
    def test_empty_catalog_is_valid(self) -> None:
        catalog = MintmarkRuleCatalog(())
        self.assertEqual(catalog.rules, ())
        self.assertEqual(catalog.rule_ids, ())

    def test_rule_ids_must_be_lexically_ordered(self) -> None:
        first = rule(
            "a",
            country="Canada",
            denomination="1 Cent",
            mintmark="P",
        )
        second = rule(
            "b",
            country="Canada",
            denomination="2 Cents",
            mintmark="R",
        )
        catalog = MintmarkRuleCatalog((first, second))
        self.assertIs(catalog.rules[0], first)
        self.assertIs(catalog.rules[1], second)

    def test_duplicate_rule_ids_are_rejected(self) -> None:
        with self.assertRaises(DuplicateMintmarkRuleError):
            MintmarkRuleCatalog((rule("a"), rule("a")))

    def test_duplicate_exact_scopes_are_rejected(self) -> None:
        with self.assertRaises(DuplicateMintmarkRuleError):
            MintmarkRuleCatalog(
                (
                    rule("a", mintmark="P"),
                    rule("b", mintmark="R"),
                )
            )

    def test_ambiguous_generic_and_specific_scope_pairs_are_rejected(self) -> None:
        with self.assertRaises(AmbiguousMintmarkRuleError):
            MintmarkRuleCatalog(
                (
                    rule(
                        "a",
                        country="Canada",
                        denomination="1 Cent",
                        mintmark="P",
                    ),
                    rule(
                        "b",
                        country="Canada",
                        denomination="1 Cent",
                        series_type="Series Alpha",
                        mintmark="R",
                    ),
                )
            )

    def test_mixed_specific_scope_pairs_are_left_isolated(self) -> None:
        catalog = MintmarkRuleCatalog(
            (
                rule(
                    "a",
                    country="Canada",
                    denomination="1 Cent",
                    year=1901,
                    mintmark="P",
                ),
                rule(
                    "b",
                    country="Canada",
                    denomination="1 Cent",
                    monarch="George VI",
                    mintmark="R",
                ),
            )
        )
        self.assertEqual(catalog.rule_ids, ("a", "b"))


class ContractIdentityTests(unittest.TestCase):
    def test_exact_field_and_tuple_identity_retention(self) -> None:
        value = rule()
        self.assertIs(value.mintmark, "P")
        self.assertEqual(
            (
                value.rule_id,
                value.country,
                value.denomination,
                value.series_type,
                value.year,
                value.monarch,
                value.mintmark,
            ),
            (
                "mintmark.canada.1-cent-v1",
                "Canada",
                "1 Cent",
                None,
                None,
                None,
                "P",
            ),
        )

    def test_is_frozen_and_slotted(self) -> None:
        value = rule()
        for name in (
            "rule_id",
            "country",
            "denomination",
            "series_type",
            "year",
            "monarch",
            "mintmark",
        ):
            with self.subTest(name=name):
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, name, None)
        self.assertFalse(hasattr(value, "__dict__"))

    def test_equality_is_deterministic_and_value_based(self) -> None:
        first = rule()
        second = rule()
        self.assertEqual(first, second)
        self.assertIsNot(first, second)

    def test_validate_rejects_malformed_direct_reconstruction(self) -> None:
        with self.assertRaises(InvalidMintmarkRuleContextError):
            MintmarkRule(
                rule_id="",
                country="Canada",
                denomination="1 Cent",
                series_type=None,
                year=None,
                monarch=None,
                mintmark="P",
            )


if __name__ == "__main__":
    unittest.main()
