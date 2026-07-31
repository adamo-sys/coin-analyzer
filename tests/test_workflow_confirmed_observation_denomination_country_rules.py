from __future__ import annotations

from dataclasses import FrozenInstanceError
import ast
import inspect
from pathlib import Path
import types
import unicodedata
import unittest

import capture_import.workflow_confirmed_observation_denomination_country_rules as module
from capture_import.workflow_confirmed_observation_denomination_country_rules import (
    DenominationCountryCompatibility,
    DenominationCountryRule,
    DenominationCountryRuleCatalog,
    DenominationCountryRuleContractError,
    DuplicateDenominationCountryRuleError,
    InvalidDenominationCountryRuleContextError,
)


PUBLIC_API = {
    "DenominationCountryRuleContractError",
    "InvalidDenominationCountryRuleContextError",
    "DuplicateDenominationCountryRuleError",
    "DenominationCountryCompatibility",
    "DenominationCountryRule",
    "DenominationCountryRuleCatalog",
}


def rule(
    rule_id: str = "coin.canada.1-cent-v1",
    *,
    country: str = "Canada",
    denomination: str = "1 Cent",
    compatibility: DenominationCountryCompatibility = (
        DenominationCountryCompatibility.COMPATIBLE
    ),
) -> DenominationCountryRule:
    return DenominationCountryRule(
        rule_id=rule_id,
        country=country,
        denomination=denomination,
        compatibility=compatibility,
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
            "evaluate",
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
            self.assertNotIsInstance(value, DenominationCountryRule)
            self.assertNotIsInstance(value, DenominationCountryRuleCatalog)


class ErrorHierarchyTests(unittest.TestCase):
    def test_exact_hierarchy(self) -> None:
        self.assertTrue(issubclass(DenominationCountryRuleContractError, ValueError))
        for error_type in (
            InvalidDenominationCountryRuleContextError,
            DuplicateDenominationCountryRuleError,
        ):
            self.assertIs(error_type.__base__, DenominationCountryRuleContractError)

    def test_errors_have_no_mutable_public_attributes(self) -> None:
        for error_type in (
            DenominationCountryRuleContractError,
            InvalidDenominationCountryRuleContextError,
            DuplicateDenominationCountryRuleError,
        ):
            error = error_type("bounded")
            with self.assertRaises(AttributeError):
                error.detail = "changed"  # type: ignore[attr-defined]

    def test_error_attributes_are_immutable(self) -> None:
        error = DuplicateDenominationCountryRuleError("bounded")
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
        value = "coin.canada_1-cent-v1"
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
            "https://coin",
            "coin\nyear",
            "coin\tyear",
            "a" * 129,
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    InvalidDenominationCountryRuleContextError,
                    "rule_id must match",
                ):
                    rule(value)

    def test_rejects_non_string_ids(self) -> None:
        for value in (None, 1, True, b"a"):
            with self.subTest(value=value):
                with self.assertRaises(InvalidDenominationCountryRuleContextError):
                    rule(value)  # type: ignore[arg-type]

    def test_does_not_trim_or_normalize_id(self) -> None:
        with self.assertRaises(InvalidDenominationCountryRuleContextError):
            rule(" coin")
        with self.assertRaises(InvalidDenominationCountryRuleContextError):
            rule("coin ")


class ScopeTextTests(unittest.TestCase):
    def test_preserves_exact_scope_values(self) -> None:
        value = rule(
            country="Côte d'Ivoire",
            denomination="$2.50",
        )
        self.assertEqual(value.country, "Côte d'Ivoire")
        self.assertEqual(value.denomination, "$2.50")

    def test_accepts_128_character_scope_values(self) -> None:
        maximum = "é" * 128
        value = rule(country=maximum, denomination=maximum)
        self.assertEqual(value.country, maximum)
        self.assertEqual(value.denomination, maximum)

    def test_rejects_invalid_country(self) -> None:
        self._assert_invalid_text("country")

    def test_rejects_invalid_denomination(self) -> None:
        self._assert_invalid_text("denomination")

    def test_rejects_non_nfc_without_normalizing(self) -> None:
        decomposed = unicodedata.normalize("NFD", "Montréal")
        for field_name in ("country", "denomination"):
            with self.subTest(field_name=field_name):
                kwargs = {field_name: decomposed}
                with self.assertRaisesRegex(
                    InvalidDenominationCountryRuleContextError,
                    "NFC-normalized",
                ):
                    rule(**kwargs)  # type: ignore[arg-type]

    def test_scope_values_are_case_sensitive(self) -> None:
        upper = rule("a", country="Canada")
        lower = rule("b", country="canada")
        catalog = DenominationCountryRuleCatalog((upper, lower))
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
                with self.assertRaises(InvalidDenominationCountryRuleContextError):
                    rule(**kwargs)  # type: ignore[arg-type]


class CompatibilityTests(unittest.TestCase):
    def test_enum_values_are_exact_and_transient(self) -> None:
        self.assertEqual(
            DenominationCountryCompatibility.COMPATIBLE.value,
            "COMPATIBLE",
        )
        self.assertEqual(
            DenominationCountryCompatibility.INCOMPATIBLE.value,
            "INCOMPATIBLE",
        )
        self.assertEqual(
            set(DenominationCountryCompatibility),
            {DenominationCountryCompatibility.COMPATIBLE, DenominationCountryCompatibility.INCOMPATIBLE},
        )

    def test_rejects_non_enum_compatibility_values(self) -> None:
        for value in (None, 1, True, "COMPATIBLE", b"COMPATIBLE"):
            with self.subTest(value=value):
                with self.assertRaises(InvalidDenominationCountryRuleContextError):
                    rule(compatibility=value)  # type: ignore[arg-type]


class RuleTests(unittest.TestCase):
    def test_exact_field_and_tuple_identity_retention(self) -> None:
        compatible = DenominationCountryCompatibility.COMPATIBLE
        value = rule(compatibility=compatible)
        self.assertIs(value.compatibility, compatible)
        self.assertEqual(
            (
                value.rule_id,
                value.country,
                value.denomination,
                value.compatibility,
            ),
            (
                "coin.canada.1-cent-v1",
                "Canada",
                "1 Cent",
                DenominationCountryCompatibility.COMPATIBLE,
            ),
        )

    def test_is_frozen_and_slotted(self) -> None:
        value = rule()
        for name in ("rule_id", "country", "denomination", "compatibility"):
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
        malformed = object.__new__(DenominationCountryRule)
        object.__setattr__(malformed, "rule_id", "A")
        object.__setattr__(malformed, "country", "Canada")
        object.__setattr__(malformed, "denomination", "1 Cent")
        object.__setattr__(
            malformed,
            "compatibility",
            DenominationCountryCompatibility.COMPATIBLE,
        )
        with self.assertRaises(InvalidDenominationCountryRuleContextError):
            malformed.validate()

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
        catalog = DenominationCountryRuleCatalog(())
        self.assertEqual(catalog.rules, ())
        self.assertEqual(catalog.rule_ids, ())
        self.assertFalse(hasattr(catalog, "is_valid"))
        self.assertFalse(hasattr(catalog, "all_valid"))

    def test_accepts_multiple_lexically_ordered_rules(self) -> None:
        alpha = rule("a", denomination="1 Cent")
        beta = rule("b", denomination="5 Cents")
        catalog = DenominationCountryRuleCatalog((alpha, beta))
        self.assertEqual(catalog.rule_ids, ("a", "b"))
        self.assertIs(catalog.rules[0], alpha)
        self.assertIs(catalog.rules[1], beta)

    def test_rejects_non_tuple_rules(self) -> None:
        with self.assertRaisesRegex(
            InvalidDenominationCountryRuleContextError,
            "immutable tuple",
        ):
            DenominationCountryRuleCatalog([rule()])  # type: ignore[arg-type]

    def test_rejects_wrong_nested_item_without_attribute_error(self) -> None:
        with self.assertRaisesRegex(
            InvalidDenominationCountryRuleContextError,
            "DenominationCountryRule",
        ):
            DenominationCountryRuleCatalog(("rule",))  # type: ignore[arg-type]

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
                    DuplicateDenominationCountryRuleError,
                    "duplicate rule IDs",
                ):
                    DenominationCountryRuleCatalog(rules)

    def test_rejects_duplicate_exact_scope(self) -> None:
        first = rule("a", country="Canada", denomination="1 Cent")
        second = rule("b", country="Canada", denomination="1 Cent")
        with self.assertRaisesRegex(
            DuplicateDenominationCountryRuleError,
            "duplicate exact scopes",
        ):
            DenominationCountryRuleCatalog((first, second))

    def test_rejects_noncanonical_rule_order_without_sorting(self) -> None:
        beta = rule("b", denomination="5 Cents")
        alpha = rule("a", denomination="1 Cent")
        supplied = (beta, alpha)
        with self.assertRaisesRegex(
            InvalidDenominationCountryRuleContextError,
            "lexical rule_id order",
        ):
            DenominationCountryRuleCatalog(supplied)
        self.assertEqual(supplied, (beta, alpha))

    def test_duplicate_detection_precedes_order_error(self) -> None:
        beta = rule("b", denomination="5 Cents")
        alpha = rule("a", denomination="1 Cent")
        duplicate = rule("b", denomination="10 Cents")
        with self.assertRaises(DuplicateDenominationCountryRuleError):
            DenominationCountryRuleCatalog((beta, alpha, duplicate))

    def test_exact_tuple_and_rule_identity_retention(self) -> None:
        alpha = rule("a", denomination="1 Cent")
        beta = rule("b", denomination="5 Cents")
        rules = (alpha, beta)
        catalog = DenominationCountryRuleCatalog(rules)
        self.assertIs(catalog.rules, rules)
        self.assertIs(catalog.rules[0], alpha)
        self.assertIs(catalog.rules[1], beta)

    def test_equal_but_distinct_rules_can_form_separate_catalogs(self) -> None:
        first = rule()
        second = rule()
        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        first_catalog = DenominationCountryRuleCatalog((first,))
        second_catalog = DenominationCountryRuleCatalog((second,))
        self.assertIs(first_catalog.rules[0], first)
        self.assertIs(second_catalog.rules[0], second)

    def test_equal_rules_are_duplicates_within_one_catalog(self) -> None:
        first = rule()
        second = rule()
        with self.assertRaises(DuplicateDenominationCountryRuleError):
            DenominationCountryRuleCatalog((first, second))

    def test_is_frozen_and_slotted(self) -> None:
        catalog = DenominationCountryRuleCatalog((rule(),))
        with self.assertRaises(FrozenInstanceError):
            catalog.rules = ()  # type: ignore[misc]
        self.assertFalse(hasattr(catalog, "__dict__"))

    def test_validate_rejects_malformed_nested_rule(self) -> None:
        malformed = object.__new__(DenominationCountryRule)
        object.__setattr__(malformed, "rule_id", "A")
        object.__setattr__(malformed, "country", "Canada")
        object.__setattr__(malformed, "denomination", "1 Cent")
        object.__setattr__(
            malformed,
            "compatibility",
            DenominationCountryCompatibility.COMPATIBLE,
        )
        catalog = object.__new__(DenominationCountryRuleCatalog)
        object.__setattr__(catalog, "rules", (malformed,))
        with self.assertRaises(InvalidDenominationCountryRuleContextError):
            catalog.validate()

    def test_validate_rejects_malformed_reconstruction(self) -> None:
        catalog = object.__new__(DenominationCountryRuleCatalog)
        object.__setattr__(catalog, "rules", ["not immutable"])
        with self.assertRaises(InvalidDenominationCountryRuleContextError):
            catalog.validate()

    def test_tuple_subclass_follows_repository_tuple_convention(self) -> None:
        class Rules(tuple):
            pass

        item = rule()
        rules = Rules((item,))
        catalog = DenominationCountryRuleCatalog(rules)
        self.assertIs(catalog.rules, rules)

    def test_has_no_matching_or_storage_behavior(self) -> None:
        catalog = DenominationCountryRuleCatalog(())
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
        self.assertEqual(from_imports, {"__future__", "dataclasses", "enum"})

    def test_no_forbidden_architecture_terms_or_facts(self) -> None:
        source = Path(module.__file__).read_text(encoding="utf-8").casefold()
        prohibited = (
            "default_catalog",
            "historical",
            "ocr",
            "persistence",
            "filesystem",
            "requests",
            "network",
            "collection",
            "mutation",
            "year",
        )
        for term in prohibited:
            with self.subTest(term=term):
                self.assertNotIn(term, source)

    def test_no_mutable_module_containers(self) -> None:
        for name, value in vars(module).items():
            if name.startswith("__"):
                continue
            self.assertNotIsInstance(value, (list, dict, set))

    def test_contracts_are_transient(self) -> None:
        for contract in (DenominationCountryRule, DenominationCountryRuleCatalog):
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
            if isinstance(value, DenominationCountryRuleCatalog)
        ]
        self.assertEqual(catalog_values, [])


if __name__ == "__main__":
    unittest.main()
