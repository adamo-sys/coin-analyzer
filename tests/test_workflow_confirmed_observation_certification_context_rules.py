from __future__ import annotations

from dataclasses import FrozenInstanceError
import ast
import inspect
from pathlib import Path
import unicodedata
import unittest

import capture_import.workflow_confirmed_observation_certification_context_rules as module
from capture_import.workflow_confirmed_observation_certification_context_rules import (
    AmbiguousCertificationContextRuleError,
    CertificationContextRule,
    CertificationContextRuleCatalog,
    CertificationContextRuleContractError,
    CertificationEvaluationContext,
    DuplicateCertificationContextRuleError,
    InvalidCertificationContextRuleContextError,
)


PUBLIC_API = {
    "CertificationContextRuleContractError",
    "InvalidCertificationContextRuleContextError",
    "DuplicateCertificationContextRuleError",
    "AmbiguousCertificationContextRuleError",
    "CertificationContextRule",
    "CertificationContextRuleCatalog",
    "CertificationEvaluationContext",
}


def rule(
    rule_id: str = "certification-context.pcgs.canada.1-cent-v1",
    *,
    grading_company: str = "PCGS",
    country: str = "Canada",
    denomination: str = "1 Cent",
    series_type: str | None = None,
) -> CertificationContextRule:
    return CertificationContextRule(
        rule_id=rule_id,
        grading_company=grading_company,
        country=country,
        denomination=denomination,
        series_type=series_type,
    )


def evaluation_context(
    *,
    grading_company: str | None = None,
) -> CertificationEvaluationContext:
    return CertificationEvaluationContext(grading_company=grading_company)


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
            "assess_certification_context",
            "evaluate_certification_context",
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
            self.assertNotIsInstance(value, CertificationContextRule)
            self.assertNotIsInstance(value, CertificationContextRuleCatalog)
            self.assertNotIsInstance(value, CertificationEvaluationContext)


class ErrorHierarchyTests(unittest.TestCase):
    def test_exact_hierarchy(self) -> None:
        self.assertTrue(issubclass(CertificationContextRuleContractError, ValueError))
        for error_type in (
            InvalidCertificationContextRuleContextError,
            DuplicateCertificationContextRuleError,
            AmbiguousCertificationContextRuleError,
        ):
            self.assertIs(error_type.__base__, CertificationContextRuleContractError)

    def test_errors_have_no_mutable_public_attributes(self) -> None:
        for error_type in (
            CertificationContextRuleContractError,
            InvalidCertificationContextRuleContextError,
            DuplicateCertificationContextRuleError,
            AmbiguousCertificationContextRuleError,
        ):
            error = error_type("bounded")
            with self.assertRaises(AttributeError):
                error.detail = "changed"  # type: ignore[attr-defined]

    def test_error_attributes_are_immutable(self) -> None:
        error = DuplicateCertificationContextRuleError("bounded")
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
        value = "certification-context.pcgs_canada_1-cent-v1"
        self.assertEqual(rule(value).rule_id, value)

    def test_rejects_malformed_ids(self) -> None:
        invalid = (
            "",
            "A",
            "1rule",
            "certification context",
            "certification/context",
            r"certification\context",
            "certification:context",
            "https://certification-context",
            "certification\ncontext",
            "a" * 129,
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    InvalidCertificationContextRuleContextError,
                    "rule_id must match",
                ):
                    rule(value)

    def test_rejects_non_string_ids(self) -> None:
        for value in (None, 1, True, b"a"):
            with self.subTest(value=value):
                with self.assertRaises(InvalidCertificationContextRuleContextError):
                    rule(value)  # type: ignore[arg-type]

    def test_does_not_trim_or_normalize_id(self) -> None:
        with self.assertRaises(InvalidCertificationContextRuleContextError):
            rule(" certification-context")
        with self.assertRaises(InvalidCertificationContextRuleContextError):
            rule("certification-context ")


class ScopeTextTests(unittest.TestCase):
    def test_preserves_exact_scope_values(self) -> None:
        value = rule(
            grading_company="PCGS",
            country="Côte d'Ivoire",
            denomination="$2.50",
            series_type="Type II — Proof-Like",
        )
        self.assertEqual(value.grading_company, "PCGS")
        self.assertEqual(value.country, "Côte d'Ivoire")
        self.assertEqual(value.denomination, "$2.50")
        self.assertEqual(value.series_type, "Type II — Proof-Like")

    def test_none_series_is_valid_generic_scope(self) -> None:
        self.assertIsNone(rule(series_type=None).series_type)

    def test_accepts_128_character_scope_values(self) -> None:
        maximum = "é" * 128
        value = rule(
            grading_company=maximum,
            country=maximum,
            denomination=maximum,
            series_type=maximum,
        )
        self.assertEqual(value.grading_company, maximum)
        self.assertEqual(value.country, maximum)
        self.assertEqual(value.denomination, maximum)
        self.assertEqual(value.series_type, maximum)

    def test_rejects_invalid_grading_company(self) -> None:
        self._assert_invalid_text("grading_company")

    def test_rejects_invalid_country(self) -> None:
        self._assert_invalid_text("country")

    def test_rejects_invalid_denomination(self) -> None:
        self._assert_invalid_text("denomination")

    def test_rejects_invalid_series_type(self) -> None:
        self._assert_invalid_text("series_type")

    def test_rejects_non_nfc_without_normalizing(self) -> None:
        decomposed = unicodedata.normalize("NFD", "Montréal")
        for field_name in (
            "grading_company",
            "country",
            "denomination",
            "series_type",
        ):
            with self.subTest(field_name=field_name):
                kwargs = {field_name: decomposed}
                with self.assertRaisesRegex(
                    InvalidCertificationContextRuleContextError,
                    "NFC-normalized",
                ):
                    rule(**kwargs)  # type: ignore[arg-type]

    def test_scope_values_are_case_sensitive(self) -> None:
        upper = rule("a", grading_company="PCGS")
        lower = rule("b", grading_company="pcgs")
        catalog = CertificationContextRuleCatalog((upper, lower))
        self.assertIs(catalog.rules[0], upper)
        self.assertIs(catalog.rules[1], lower)

    def _assert_invalid_text(self, field_name: str) -> None:
        invalid = (
            "",
            " ",
            " PCGS",
            "PCGS ",
            "Can\nada",
            "Can\tada",
            "Can\x00ada",
            "Can\x85ada",
            "Can\ud800ada",
            "x" * 129,
            1,
            True,
            b"PCGS",
        )
        for value in invalid:
            with self.subTest(field_name=field_name, value=value):
                kwargs = {field_name: value}
                with self.assertRaises(InvalidCertificationContextRuleContextError):
                    rule(**kwargs)  # type: ignore[arg-type]


class CatalogTests(unittest.TestCase):
    def test_empty_catalog_is_allowed(self) -> None:
        catalog = CertificationContextRuleCatalog(())
        self.assertEqual(catalog.rules, ())
        self.assertEqual(catalog.rule_ids, ())

    def test_rules_must_be_in_lexical_rule_id_order(self) -> None:
        with self.assertRaises(InvalidCertificationContextRuleContextError):
            CertificationContextRuleCatalog(
                (
                    rule(
                        "b",
                        grading_company="PCGS",
                        country="Canada",
                        denomination="1 Cent",
                    ),
                    rule(
                        "a",
                        grading_company="NGC",
                        country="United States",
                        denomination="1 Cent",
                    ),
                )
            )

    def test_duplicate_rule_ids_and_duplicate_scopes_fail(self) -> None:
        with self.assertRaises(DuplicateCertificationContextRuleError):
            CertificationContextRuleCatalog((rule("a"), rule("a")))

        with self.assertRaises(DuplicateCertificationContextRuleError):
            CertificationContextRuleCatalog(
                (
                    rule(
                        "a",
                        grading_company="PCGS",
                        country="Canada",
                        denomination="1 Cent",
                    ),
                    rule(
                        "b",
                        grading_company="PCGS",
                        country="Canada",
                        denomination="1 Cent",
                    ),
                )
            )

    def test_generic_and_specific_scope_may_not_coexist_for_same_country_and_denomination(self) -> None:
        generic = rule(
            "generic.canada.1-cent-v1",
            grading_company="PCGS",
            country="Canada",
            denomination="1 Cent",
            series_type=None,
        )
        specific = rule(
            "specific.canada.1-cent.v1",
            grading_company="PCGS",
            country="Canada",
            denomination="1 Cent",
            series_type="Type I",
        )
        with self.assertRaises(AmbiguousCertificationContextRuleError):
            CertificationContextRuleCatalog((generic, specific))

    def test_rule_ids_property_preserves_catalog_order(self) -> None:
        catalog = CertificationContextRuleCatalog(
            (
                rule(
                    "a",
                    grading_company="NGC",
                    country="United States",
                    denomination="1 Cent",
                ),
                rule(
                    "b",
                    grading_company="PCGS",
                    country="Canada",
                    denomination="1 Cent",
                ),
            )
        )
        self.assertEqual(catalog.rule_ids, ("a", "b"))


class EvaluationContextTests(unittest.TestCase):
    def test_optional_grading_company_is_preserved(self) -> None:
        value = evaluation_context(grading_company="PCGS")
        self.assertEqual(value.grading_company, "PCGS")

    def test_none_grading_company_is_allowed(self) -> None:
        value = evaluation_context()
        self.assertIsNone(value.grading_company)

    def test_invalid_context_values_raise_typed_error(self) -> None:
        for value in ("", " ", "PCGS ", "Can\nada", 1, True, b"PCGS"):
            with self.subTest(value=value):
                with self.assertRaises(InvalidCertificationContextRuleContextError):
                    evaluation_context(grading_company=value)  # type: ignore[arg-type]

    def test_evaluation_context_is_frozen_and_slotted(self) -> None:
        value = evaluation_context(grading_company="PCGS")
        self.assertFalse(hasattr(value, "__dict__"))
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            value.grading_company = "NGC"  # type: ignore[misc]


class ArchitectureTests(unittest.TestCase):
    def test_module_has_no_forbidden_imports_or_evaluator_dependencies(self) -> None:
        path = Path(inspect.getfile(CertificationContextRuleCatalog))
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        forbidden = (
            "collection",
            "persistence",
            "storage",
            "gui",
            "tkinter",
            "os",
            "pathlib",
            "requests",
            "urllib",
            "ocr",
        )
        for fragment in forbidden:
            with self.subTest(fragment=fragment):
                self.assertFalse(
                    any(fragment in name.casefold() for name in imported),
                    imported,
                )

    def test_rule_and_catalog_are_immutable_and_non_persistent(self) -> None:
        rule_value = rule()
        catalog = CertificationContextRuleCatalog((rule_value,))
        self.assertIs(rule_value, rule_value)
        self.assertIs(catalog.rules[0], rule_value)
        self.assertEqual(catalog.rule_ids, (rule_value.rule_id,))


if __name__ == "__main__":
    unittest.main()
