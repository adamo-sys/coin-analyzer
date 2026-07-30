from __future__ import annotations

from dataclasses import FrozenInstanceError
import ast
import inspect
from pathlib import Path
import types
import unicodedata
import unittest

import capture_import.workflow_confirmed_observation_coin_year_rules as module
from capture_import.workflow_confirmed_observation_coin_year_rules import (
    AmbiguousCoinYearRuleError,
    CoinYearRule,
    CoinYearRuleCatalog,
    CoinYearRuleContractError,
    DuplicateCoinYearRuleError,
    InvalidCoinYearRuleContextError,
)


PUBLIC_API = {
    "CoinYearRuleContractError",
    "InvalidCoinYearRuleContextError",
    "DuplicateCoinYearRuleError",
    "AmbiguousCoinYearRuleError",
    "CoinYearRule",
    "CoinYearRuleCatalog",
}


def rule(
    rule_id: str = "coin-year.canada.1-cent-v1",
    *,
    country: str = "Canada",
    denomination: str = "1 Cent",
    series_type: str | None = None,
    allowed_years: tuple[int, ...] = (1920, 1921),
) -> CoinYearRule:
    return CoinYearRule(
        rule_id=rule_id,
        country=country,
        denomination=denomination,
        series_type=series_type,
        allowed_years=allowed_years,
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
            "assess_coin_specific_year",
            "evaluate_coin_year",
            "find_rule",
            "default_catalog",
            "to_dict",
            "from_dict",
            "save",
            "load",
        }
        self.assertTrue(prohibited.isdisjoint(vars(module)))

    def test_no_global_catalog_or_rules(self) -> None:
        for name, value in vars(module).items():
            if name.startswith("_"):
                continue
            self.assertNotIsInstance(value, CoinYearRule)
            self.assertNotIsInstance(value, CoinYearRuleCatalog)


class ErrorHierarchyTests(unittest.TestCase):
    def test_exact_hierarchy(self) -> None:
        self.assertTrue(issubclass(CoinYearRuleContractError, ValueError))
        for error_type in (
            InvalidCoinYearRuleContextError,
            DuplicateCoinYearRuleError,
            AmbiguousCoinYearRuleError,
        ):
            self.assertIs(error_type.__base__, CoinYearRuleContractError)

    def test_errors_have_no_mutable_public_attributes(self) -> None:
        for error_type in (
            CoinYearRuleContractError,
            InvalidCoinYearRuleContextError,
            DuplicateCoinYearRuleError,
            AmbiguousCoinYearRuleError,
        ):
            error = error_type("bounded")
            with self.assertRaises(AttributeError):
                error.detail = "changed"  # type: ignore[attr-defined]

    def test_error_attributes_are_immutable(self) -> None:
        error = DuplicateCoinYearRuleError("bounded")
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
        value = "coin-year.canada_1-cent-v1"
        self.assertEqual(rule(value).rule_id, value)

    def test_rejects_malformed_ids(self) -> None:
        invalid = (
            "",
            "A",
            "1rule",
            "coin year",
            "coin/year",
            r"coin\year",
            "coin:year",
            "https://coin-year",
            "coin\nyear",
            "coin\tyear",
            "a" * 129,
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    InvalidCoinYearRuleContextError,
                    "rule_id must match",
                ):
                    rule(value)

    def test_rejects_non_string_ids(self) -> None:
        for value in (None, 1, True, b"a"):
            with self.subTest(value=value):
                with self.assertRaises(InvalidCoinYearRuleContextError):
                    rule(value)  # type: ignore[arg-type]

    def test_does_not_trim_or_normalize_id(self) -> None:
        with self.assertRaises(InvalidCoinYearRuleContextError):
            rule(" coin-year")
        with self.assertRaises(InvalidCoinYearRuleContextError):
            rule("coin-year ")


class ScopeTextTests(unittest.TestCase):
    def test_preserves_exact_scope_values(self) -> None:
        value = rule(
            country="Côte d'Ivoire",
            denomination="$2.50",
            series_type="Type II — Proof-Like",
        )
        self.assertEqual(value.country, "Côte d'Ivoire")
        self.assertEqual(value.denomination, "$2.50")
        self.assertEqual(value.series_type, "Type II — Proof-Like")

    def test_none_series_is_valid_generic_scope(self) -> None:
        self.assertIsNone(rule(series_type=None).series_type)

    def test_accepts_128_character_scope_values(self) -> None:
        maximum = "é" * 128
        value = rule(
            country=maximum,
            denomination=maximum,
            series_type=maximum,
        )
        self.assertEqual(value.country, maximum)
        self.assertEqual(value.denomination, maximum)
        self.assertEqual(value.series_type, maximum)

    def test_rejects_invalid_country(self) -> None:
        self._assert_invalid_text("country")

    def test_rejects_invalid_denomination(self) -> None:
        self._assert_invalid_text("denomination")

    def test_rejects_invalid_series_type(self) -> None:
        self._assert_invalid_text("series_type")

    def test_rejects_non_nfc_without_normalizing(self) -> None:
        decomposed = unicodedata.normalize("NFD", "Montréal")
        for field_name in ("country", "denomination", "series_type"):
            with self.subTest(field_name=field_name):
                kwargs = {field_name: decomposed}
                with self.assertRaisesRegex(
                    InvalidCoinYearRuleContextError,
                    "NFC-normalized",
                ):
                    rule(**kwargs)  # type: ignore[arg-type]

    def test_scope_values_are_case_sensitive(self) -> None:
        upper = rule("a", country="Canada")
        lower = rule("b", country="canada")
        catalog = CoinYearRuleCatalog((upper, lower))
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
                with self.assertRaises(InvalidCoinYearRuleContextError):
                    rule(**kwargs)  # type: ignore[arg-type]


class AllowedYearTests(unittest.TestCase):
    def test_accepts_single_contiguous_and_gapped_years(self) -> None:
        values = (
            (1967,),
            (1967, 1968, 1969),
            (1920, 1922, 1927),
        )
        for years in values:
            with self.subTest(years=years):
                self.assertIs(rule(allowed_years=years).allowed_years, years)

    def test_accepts_inclusive_structural_bounds(self) -> None:
        years = (1000, 2999)
        self.assertIs(rule(allowed_years=years).allowed_years, years)

    def test_rejects_out_of_bounds_years(self) -> None:
        for years in ((999,), (3000,), (1000, 3000)):
            with self.subTest(years=years):
                with self.assertRaisesRegex(
                    InvalidCoinYearRuleContextError,
                    "between 1000 and 2999",
                ):
                    rule(allowed_years=years)

    def test_rejects_non_integer_years(self) -> None:
        for years in ((True,), (1967.0,), ("1967",), (None,)):
            with self.subTest(years=years):
                with self.assertRaisesRegex(
                    InvalidCoinYearRuleContextError,
                    "exact integers",
                ):
                    rule(allowed_years=years)  # type: ignore[arg-type]

    def test_rejects_non_tuple_and_empty(self) -> None:
        with self.assertRaisesRegex(
            InvalidCoinYearRuleContextError,
            "immutable tuple",
        ):
            rule(allowed_years=[1967])  # type: ignore[arg-type]
        with self.assertRaisesRegex(
            InvalidCoinYearRuleContextError,
            "at least one",
        ):
            rule(allowed_years=())

    def test_rejects_duplicate_years_including_final_position(self) -> None:
        for years in ((1967, 1967), (1967, 1968, 1968)):
            with self.subTest(years=years):
                with self.assertRaisesRegex(
                    InvalidCoinYearRuleContextError,
                    "strictly increasing",
                ):
                    rule(allowed_years=years)

    def test_rejects_descending_and_subtly_misplaced_years(self) -> None:
        for years in ((1968, 1967), (1967, 1969, 1968, 1970)):
            with self.subTest(years=years):
                with self.assertRaisesRegex(
                    InvalidCoinYearRuleContextError,
                    "strictly increasing",
                ):
                    rule(allowed_years=years)

    def test_never_infers_a_range(self) -> None:
        years = (1920, 1925)
        self.assertEqual(rule(allowed_years=years).allowed_years, years)
        self.assertNotIn(1921, rule(allowed_years=years).allowed_years)


class CoinYearRuleTests(unittest.TestCase):
    def test_exact_field_and_tuple_identity_retention(self) -> None:
        years = (1920, 1921)
        value = rule(allowed_years=years)
        self.assertIs(value.allowed_years, years)
        self.assertEqual(
            (
                value.rule_id,
                value.country,
                value.denomination,
                value.series_type,
            ),
            ("coin-year.canada.1-cent-v1", "Canada", "1 Cent", None),
        )

    def test_is_frozen_and_slotted(self) -> None:
        value = rule()
        for name in (
            "rule_id",
            "country",
            "denomination",
            "series_type",
            "allowed_years",
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
        malformed = object.__new__(CoinYearRule)
        object.__setattr__(malformed, "rule_id", "A")
        object.__setattr__(malformed, "country", "Canada")
        object.__setattr__(malformed, "denomination", "1 Cent")
        object.__setattr__(malformed, "series_type", None)
        object.__setattr__(malformed, "allowed_years", (1920,))
        with self.assertRaises(InvalidCoinYearRuleContextError):
            malformed.validate()

    def test_tuple_subclass_follows_repository_tuple_convention(self) -> None:
        class Years(tuple):
            pass

        years = Years((1920, 1921))
        value = rule(allowed_years=years)
        self.assertIs(value.allowed_years, years)

    def test_has_no_serializer_or_metadata(self) -> None:
        value = rule()
        for name in (
            "to_dict",
            "from_dict",
            "schema_version",
            "metadata",
            "authority_url",
            "catalog_id",
            "version",
        ):
            self.assertFalse(hasattr(value, name))


class CatalogTests(unittest.TestCase):
    def test_accepts_empty_catalog_without_implying_validity(self) -> None:
        catalog = CoinYearRuleCatalog(())
        self.assertEqual(catalog.rules, ())
        self.assertEqual(catalog.rule_ids, ())
        self.assertFalse(hasattr(catalog, "is_valid"))
        self.assertFalse(hasattr(catalog, "all_valid"))

    def test_accepts_one_generic_rule(self) -> None:
        item = rule()
        catalog = CoinYearRuleCatalog((item,))
        self.assertIs(catalog.rules[0], item)
        self.assertEqual(catalog.rule_ids, (item.rule_id,))

    def test_accepts_multiple_lexically_ordered_rules(self) -> None:
        alpha = rule("a", denomination="1 Cent")
        beta = rule("b", denomination="5 Cents")
        catalog = CoinYearRuleCatalog((alpha, beta))
        self.assertEqual(catalog.rule_ids, ("a", "b"))
        self.assertIs(catalog.rules[0], alpha)
        self.assertIs(catalog.rules[1], beta)

    def test_accepts_distinct_specific_scopes_for_same_pair(self) -> None:
        first = rule("a", series_type="Large Cent")
        second = rule("b", series_type="Small Cent")
        catalog = CoinYearRuleCatalog((first, second))
        self.assertEqual(catalog.rules, (first, second))

    def test_accepts_same_denomination_in_different_countries(self) -> None:
        first = rule("a", country="Canada")
        second = rule("b", country="Newfoundland")
        CoinYearRuleCatalog((first, second))

    def test_accepts_same_country_with_different_denominations(self) -> None:
        first = rule("a", denomination="1 Cent")
        second = rule("b", denomination="5 Cents")
        CoinYearRuleCatalog((first, second))

    def test_rejects_non_tuple_rules(self) -> None:
        with self.assertRaisesRegex(
            InvalidCoinYearRuleContextError,
            "immutable tuple",
        ):
            CoinYearRuleCatalog([rule()])  # type: ignore[arg-type]

    def test_rejects_wrong_nested_item_without_attribute_error(self) -> None:
        with self.assertRaisesRegex(
            InvalidCoinYearRuleContextError,
            "CoinYearRule",
        ):
            CoinYearRuleCatalog(("rule",))  # type: ignore[arg-type]

    def test_rejects_duplicate_rule_id_adjacent_and_final(self) -> None:
        cases = (
            (
                rule("a", denomination="1 Cent"),
                rule("a", denomination="5 Cents"),
            ),
            (
                rule("a", denomination="1 Cent"),
                rule("b", denomination="5 Cents"),
                rule("a", denomination="10 Cents"),
            ),
        )
        for rules in cases:
            with self.subTest(rules=rules):
                with self.assertRaisesRegex(
                    DuplicateCoinYearRuleError,
                    "duplicate rule IDs",
                ):
                    CoinYearRuleCatalog(rules)

    def test_rejects_duplicate_exact_generic_scope(self) -> None:
        first = rule("a", allowed_years=(1920,))
        second = rule("b", allowed_years=(1921,))
        with self.assertRaisesRegex(
            DuplicateCoinYearRuleError,
            "duplicate exact scopes",
        ):
            CoinYearRuleCatalog((first, second))

    def test_rejects_duplicate_exact_specific_scope(self) -> None:
        first = rule("a", series_type="Large Cent")
        second = rule("b", series_type="Large Cent", allowed_years=(1921,))
        with self.assertRaises(DuplicateCoinYearRuleError):
            CoinYearRuleCatalog((first, second))

    def test_rejects_ambiguity_in_first_middle_and_final_positions(self) -> None:
        cases = (
            (
                rule("a"),
                rule("b", series_type="Large Cent"),
                rule("c", series_type="Small Cent"),
            ),
            (
                rule("a", series_type="Large Cent"),
                rule("b"),
                rule("c", series_type="Small Cent"),
            ),
            (
                rule("a", series_type="Large Cent"),
                rule("b", series_type="Small Cent"),
                rule("c"),
            ),
        )
        for rules in cases:
            with self.subTest(rule_ids=tuple(item.rule_id for item in rules)):
                with self.assertRaisesRegex(
                    AmbiguousCoinYearRuleError,
                    "must not coexist",
                ):
                    CoinYearRuleCatalog(rules)

    def test_rejects_noncanonical_rule_order_without_sorting(self) -> None:
        beta = rule("b", denomination="5 Cents")
        alpha = rule("a", denomination="1 Cent")
        supplied = (beta, alpha)
        with self.assertRaisesRegex(
            InvalidCoinYearRuleContextError,
            "lexical rule_id order",
        ):
            CoinYearRuleCatalog(supplied)
        self.assertEqual(supplied, (beta, alpha))

    def test_rejects_subtly_misplaced_rule(self) -> None:
        alpha = rule("a", denomination="1 Cent")
        gamma = rule("c", denomination="10 Cents")
        beta = rule("b", denomination="5 Cents")
        with self.assertRaises(InvalidCoinYearRuleContextError):
            CoinYearRuleCatalog((alpha, gamma, beta))

    def test_duplicate_detection_precedes_order_error(self) -> None:
        beta = rule("b", denomination="5 Cents")
        alpha = rule("a", denomination="1 Cent")
        duplicate = rule("b", denomination="10 Cents")
        with self.assertRaises(DuplicateCoinYearRuleError):
            CoinYearRuleCatalog((beta, alpha, duplicate))

    def test_ambiguity_detection_precedes_order_error(self) -> None:
        specific = rule("b", series_type="Large Cent")
        generic = rule("a")
        with self.assertRaises(AmbiguousCoinYearRuleError):
            CoinYearRuleCatalog((specific, generic))

    def test_exact_tuple_and_rule_identity_retention(self) -> None:
        alpha = rule("a", denomination="1 Cent")
        beta = rule("b", denomination="5 Cents")
        rules = (alpha, beta)
        catalog = CoinYearRuleCatalog(rules)
        self.assertIs(catalog.rules, rules)
        self.assertIs(catalog.rules[0], alpha)
        self.assertIs(catalog.rules[1], beta)

    def test_equal_but_distinct_rules_can_form_separate_catalogs(self) -> None:
        first = rule()
        second = rule()
        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        first_catalog = CoinYearRuleCatalog((first,))
        second_catalog = CoinYearRuleCatalog((second,))
        self.assertIs(first_catalog.rules[0], first)
        self.assertIs(second_catalog.rules[0], second)

    def test_equal_rules_are_duplicates_within_one_catalog(self) -> None:
        first = rule()
        second = rule()
        with self.assertRaises(DuplicateCoinYearRuleError):
            CoinYearRuleCatalog((first, second))

    def test_is_frozen_and_slotted(self) -> None:
        catalog = CoinYearRuleCatalog((rule(),))
        with self.assertRaises(FrozenInstanceError):
            catalog.rules = ()  # type: ignore[misc]
        self.assertFalse(hasattr(catalog, "__dict__"))

    def test_validate_rejects_malformed_nested_rule(self) -> None:
        malformed = object.__new__(CoinYearRule)
        object.__setattr__(malformed, "rule_id", "A")
        object.__setattr__(malformed, "country", "Canada")
        object.__setattr__(malformed, "denomination", "1 Cent")
        object.__setattr__(malformed, "series_type", None)
        object.__setattr__(malformed, "allowed_years", (1920,))
        catalog = object.__new__(CoinYearRuleCatalog)
        object.__setattr__(catalog, "rules", (malformed,))
        with self.assertRaises(InvalidCoinYearRuleContextError):
            catalog.validate()

    def test_validate_rejects_malformed_reconstruction(self) -> None:
        catalog = object.__new__(CoinYearRuleCatalog)
        object.__setattr__(catalog, "rules", ["not immutable"])
        with self.assertRaises(InvalidCoinYearRuleContextError):
            catalog.validate()

    def test_tuple_subclass_follows_repository_tuple_convention(self) -> None:
        class Rules(tuple):
            pass

        item = rule()
        rules = Rules((item,))
        catalog = CoinYearRuleCatalog(rules)
        self.assertIs(catalog.rules, rules)

    def test_has_no_matching_or_storage_behavior(self) -> None:
        catalog = CoinYearRuleCatalog(())
        for name in (
            "find_rule",
            "match",
            "evaluate",
            "to_dict",
            "from_dict",
            "save",
            "load",
            "refresh",
            "add_rule",
            "remove_rule",
        ):
            self.assertFalse(hasattr(catalog, name))


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_imports_are_bounded(self) -> None:
        source = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        from_imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        self.assertEqual(imports, {"re", "unicodedata"})
        self.assertEqual(from_imports, {"__future__", "dataclasses"})

    def test_no_forbidden_architecture_terms_or_facts(self) -> None:
        source = Path(module.__file__).read_text(encoding="utf-8").casefold()
        prohibited = (
            "canadian_reference_provider",
            "series_definitions",
            "ocr_validation",
            "numista",
            "fieldintelligencefinding",
            "requests",
            "pathlib",
            "filesystem",
            "default_catalog",
            "built_in",
            "authority_url",
        )
        for term in prohibited:
            with self.subTest(term=term):
                self.assertNotIn(term, source)

    def test_no_policy_years_exist_outside_structural_bounds(self) -> None:
        source = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        numeric_constants = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and type(node.value) is int
            and 1000 <= node.value <= 2999
        }
        self.assertEqual(numeric_constants, {1000, 2999})

    def test_no_mutable_module_containers(self) -> None:
        for name, value in vars(module).items():
            if name.startswith("__"):
                continue
            self.assertNotIsInstance(value, (list, dict, set))

    def test_contracts_are_transient(self) -> None:
        for contract in (CoinYearRule, CoinYearRuleCatalog):
            source = inspect.getsource(contract)
            for term in (
                "schema_version",
                "to_dict",
                "from_dict",
                "repository",
                "timestamp",
                "uuid",
            ):
                self.assertNotIn(term, source.casefold())

    def test_module_has_no_generated_catalog_state(self) -> None:
        catalog_values = [
            value
            for value in vars(module).values()
            if isinstance(value, CoinYearRuleCatalog)
        ]
        self.assertEqual(catalog_values, [])


if __name__ == "__main__":
    unittest.main()
