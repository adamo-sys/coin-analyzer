"""Synthetic contract tests for the pure issue-equivalence boundary."""

import unittest
from dataclasses import FrozenInstanceError, fields, replace
from enum import Enum
from itertools import product
from typing import cast

from issue_equivalence import (
    EffectiveStatus,
    IssueDecision,
    IssueEquivalenceResult,
    IssueIdentity,
    IssueReason,
    ItemType,
    NormalizedIssueIdentity,
    compare_issue_identity,
)


def identity(**changes: object) -> IssueIdentity:
    base = IssueIdentity(
        subject_key="record: A ", item_type=ItemType.COIN,
        effective_status=EffectiveStatus.IDENTIFIED,
        country="Canada", denomination="1 dollar", year="1967",
        type_design="Goose",
    )
    return replace(base, **changes)


class RuntimeClassSpoof:
    """Actual non-enum/non-string object reproducing the review bypasses."""

    def __init__(self, claimed: type, agrees: bool = True):
        self.claimed = claimed
        self.agrees = agrees
        self.payload: list[str] = []

    @property
    def __class__(self) -> type:
        return self.claimed

    @__class__.setter
    def __class__(self, value: type) -> None:
        raise AssertionError("Runtime class assignment must not run")

    def __eq__(self, other: object) -> bool:
        return self.agrees

    def __ne__(self, other: object) -> bool:
        return not self.agrees

    def __lt__(self, other: object) -> bool:
        return False

    def __gt__(self, other: object) -> bool:
        return False

    def __str__(self) -> str:
        return "Canada"


class ProjectionSpoof(RuntimeClassSpoof):
    def __init__(self):
        super().__init__(IssueIdentity)
        valid = identity()
        for field in fields(valid):
            setattr(self, field.name, getattr(valid, field.name))


class HostileObject:
    @property
    def __class__(self) -> type:
        raise AssertionError("Instance-controlled class must not be read")

    @__class__.setter
    def __class__(self, value: type) -> None:
        raise AssertionError("Runtime class assignment must not run")

    def __eq__(self, other: object) -> bool:
        raise AssertionError("Unsupported equality must not run")

    def __ne__(self, other: object) -> bool:
        raise AssertionError("Unsupported inequality must not run")

    def __str__(self) -> str:
        raise AssertionError("Unsupported string conversion must not run")

    def __bool__(self) -> bool:
        raise AssertionError("Unsupported truthiness must not run")


class HostileString(str):
    def __eq__(self, other: object) -> bool:
        raise AssertionError("String-subclass equality must not run")

    def __ne__(self, other: object) -> bool:
        raise AssertionError("String-subclass inequality must not run")

    def __str__(self) -> str:
        raise AssertionError("String-subclass conversion must not run")


class DerivedIdentity(IssueIdentity):
    """Subclasses are outside the exact immutable projection boundary."""


class IssueEquivalenceTests(unittest.TestCase):
    def assert_decision(
        self, left: IssueIdentity, right: IssueIdentity,
        decision: IssueDecision, *reasons: IssueReason,
    ) -> IssueEquivalenceResult:
        result = compare_issue_identity(left, right)
        self.assertEqual(result.decision, decision)
        self.assertEqual(result.reason_codes, reasons)
        return result

    def test_blank_unidentified(self):
        blank = IssueIdentity(subject_key="blank", item_type="COIN",
                             effective_status="UNIDENTIFIED")
        self.assert_decision(blank, blank, IssueDecision.ABSTAIN,
                             IssueReason.INELIGIBLE_STATUS)

    def test_country_only_unidentified(self):
        value = IssueIdentity(subject_key="country", item_type="COIN",
                              effective_status="UNIDENTIFIED", country="Canada")
        self.assert_decision(value, value, IssueDecision.ABSTAIN,
                             IssueReason.INELIGIBLE_STATUS)

    def test_partial_country_denomination(self):
        value = identity(effective_status="PARTIAL", year=None, type_design=None)
        self.assert_decision(value, value, IssueDecision.ABSTAIN,
                             IssueReason.INELIGIBLE_STATUS)

    def test_missing_design(self):
        value = identity(type_design=None)
        self.assert_decision(value, value, IssueDecision.ABSTAIN,
                             IssueReason.MISSING_REQUIRED_IDENTITY)

    def test_complete_ordinary_identity(self):
        for item_type in ItemType:
            with self.subTest(item_type=item_type):
                value = identity(item_type=item_type)
                self.assert_decision(value, value, IssueDecision.SAME_ISSUE,
                                     IssueReason.COMPLETE_OPERATIVE_IDENTITY)

    def test_different_design(self):
        self.assert_decision(identity(), identity(type_design="Voyageur"),
                             IssueDecision.DIFFERENT_ISSUE,
                             IssueReason.TYPE_DESIGN_CONFLICT)

    def test_design_one_side(self):
        self.assert_decision(identity(), identity(type_design=None),
                             IssueDecision.ABSTAIN,
                             IssueReason.MISSING_REQUIRED_IDENTITY)

    def test_reference_cannot_rescue_missing_design(self):
        value = identity(reference="KM#70", type_design=None)
        self.assert_decision(value, value, IssueDecision.ABSTAIN,
                             IssueReason.MISSING_REQUIRED_IDENTITY)

    def test_reference_with_complete_match(self):
        value = identity(reference="KM#70")
        self.assert_decision(value, value, IssueDecision.SAME_ISSUE,
                             IssueReason.COMPLETE_OPERATIVE_IDENTITY)

    def test_reference_with_year_or_design_conflict(self):
        left = identity(reference="KM#70")
        for change, reasons in (
            ({"year": "1968"}, (IssueReason.ORDINARY_IDENTITY_CONFLICT,)),
            ({"type_design": "Voyageur"}, (IssueReason.TYPE_DESIGN_CONFLICT,)),
        ):
            with self.subTest(change=change):
                self.assert_decision(left, replace(left, **change),
                                     IssueDecision.DIFFERENT_ISSUE, *reasons)

    def test_numista_only(self):
        value = IssueIdentity(subject_key="catalogue", item_type="COIN",
                              effective_status="IDENTIFIED", numista_n="123")
        self.assert_decision(value, value, IssueDecision.ABSTAIN,
                             IssueReason.MISSING_REQUIRED_IDENTITY)

    def test_numista_with_complete_match(self):
        value = identity(numista_n="123")
        self.assert_decision(value, value, IssueDecision.SAME_ISSUE,
                             IssueReason.COMPLETE_OPERATIVE_IDENTITY)

    def test_numista_with_each_core_conflict(self):
        left = identity(numista_n="123", reference="KM#70")
        for field, value in (("country", "USA"), ("denomination", "2 dollars"),
                             ("year", "1968"), ("type_design", "Voyageur")):
            with self.subTest(field=field):
                reason = (IssueReason.TYPE_DESIGN_CONFLICT if field == "type_design"
                          else IssueReason.ORDINARY_IDENTITY_CONFLICT)
                self.assert_decision(left, replace(left, **{field: value}),
                                     IssueDecision.ABSTAIN,
                                     IssueReason.CONTRADICTORY_IDENTITY_EVIDENCE, reason)

    def test_item_type_conflict(self):
        self.assert_decision(identity(), identity(item_type="BANKNOTE"),
                             IssueDecision.DIFFERENT_ISSUE,
                             IssueReason.ITEM_TYPE_CONFLICT)

    def test_placeholders_and_empty_cannot_supply_required_evidence(self):
        placeholders = (None, "", " \t\n", "unknown", "n/a", "na", "none",
                        "not applicable", "unidentified", "null", "nan", "<na>",
                        "?", "-", "not known")
        for field, value in product(("country", "denomination", "year", "type_design"),
                                    placeholders):
            with self.subTest(field=field, value=value):
                pair = identity(**{field: value})
                result = self.assert_decision(pair, pair, IssueDecision.ABSTAIN,
                                              IssueReason.MISSING_REQUIRED_IDENTITY)
                self.assertIsNone(getattr(result.compared_values[0], field))

    def test_optional_asymmetry(self):
        for field, value in (("issuer", "Royal Mint"), ("reference", "KM#70"),
                             ("numista_n", "123")):
            with self.subTest(field=field):
                self.assert_decision(identity(), identity(**{field: value}),
                                     IssueDecision.ABSTAIN, IssueReason.QUALIFIER_MISSING)

    def test_reference_disagreement(self):
        self.assert_decision(identity(reference="KM#70"), identity(reference="KM#71"),
                             IssueDecision.ABSTAIN,
                             IssueReason.UNSCOPED_REFERENCE_DISAGREEMENT)

    def test_numista_disagreement(self):
        self.assert_decision(identity(numista_n="123"), identity(numista_n="124"),
                             IssueDecision.ABSTAIN, IssueReason.NUMISTA_DISAGREEMENT)

    def test_issuer_conflict(self):
        self.assert_decision(identity(issuer="Mint A"), identity(issuer="Mint B"),
                             IssueDecision.DIFFERENT_ISSUE, IssueReason.ISSUER_CONFLICT)

    def test_issuer_conflict_with_same_numista(self):
        self.assert_decision(identity(issuer="Mint A", numista_n="123"),
                             identity(issuer="Mint B", numista_n="N#123"),
                             IssueDecision.ABSTAIN,
                             IssueReason.CONTRADICTORY_IDENTITY_EVIDENCE,
                             IssueReason.ISSUER_CONFLICT)

    def test_complete_but_ineligible_status(self):
        for status in ("PARTIAL", "UNIDENTIFIED"):
            with self.subTest(status=status):
                self.assert_decision(identity(), identity(effective_status=status),
                                     IssueDecision.ABSTAIN, IssueReason.INELIGIBLE_STATUS)

    def test_status_malformed_or_null(self):
        for status in (None, "", "identified", " IDENTIFIED ", "LEGACY", 1, True):
            with self.subTest(status=status):
                self.assert_decision(identity(), identity(effective_status=status),
                                     IssueDecision.ABSTAIN, IssueReason.INVALID_VALUE)

    def test_item_type_unavailable_or_unsupported(self):
        for value in (None, "", "coin", " COIN ", "MEDAL", 1, True):
            with self.subTest(value=value):
                reason = (IssueReason.MISSING_ITEM_TYPE if value in (None, "")
                          else IssueReason.INVALID_VALUE)
                self.assert_decision(identity(), identity(item_type=value),
                                     IssueDecision.ABSTAIN, reason)

    def test_non_string_ordinary_or_qualifier_evidence_is_invalid(self):
        for field, value in product(
            ("country", "denomination", "year", "type_design", "issuer", "reference",
             "numista_n"), (1967, False, float("nan"), [], {}),
        ):
            with self.subTest(field=field, value=value):
                self.assert_decision(identity(), identity(**{field: value}),
                                     IssueDecision.ABSTAIN, IssueReason.INVALID_VALUE)

    def test_malformed_year(self):
        for year in ("0", "000", "-1967", "+1967", "1967.0", "19 67", "1967 AD",
                     "c.1967", "１９６７", "١٩٦٧"):
            with self.subTest(year=year):
                self.assert_decision(identity(), identity(year=year),
                                     IssueDecision.ABSTAIN, IssueReason.INVALID_VALUE)

    def test_year_retains_decimal_spelling(self):
        self.assert_decision(identity(year="01967"), identity(year="1967"),
                             IssueDecision.DIFFERENT_ISSUE,
                             IssueReason.ORDINARY_IDENTITY_CONFLICT)

    def test_numista_normalization(self):
        result = self.assert_decision(identity(numista_n="123"),
                                      identity(numista_n=" N#123 "),
                                      IssueDecision.SAME_ISSUE,
                                      IssueReason.COMPLETE_OPERATIVE_IDENTITY)
        self.assertEqual(tuple(v.numista_n for v in result.compared_values),
                         ("123", "123"))

    def test_malformed_numista(self):
        for value in ("0", "N#0", "000", "n#123", "N# 123", "#123", "+123", "123.0",
                      "https://numista.com/123", "ID 123", "１２３", "١٢٣"):
            with self.subTest(value=value):
                pair = identity(numista_n=value)
                self.assert_decision(pair, pair, IssueDecision.ABSTAIN,
                                     IssueReason.INVALID_VALUE)

    def test_text_normalization(self):
        result = self.assert_decision(
            identity(country=" \tCANADA\n", denomination=" 1\t DOLLAR ",
                     year=" 1967 ", type_design=" Arctic\nGOOSE ", issuer=" MINT A ",
                     reference=" KM#  70 "),
            identity(type_design="arctic goose", issuer="mint a", reference="km# 70"),
            IssueDecision.SAME_ISSUE, IssueReason.COMPLETE_OPERATIVE_IDENTITY,
        )
        self.assertEqual(result.compared_values[0].country, "canada")
        self.assertEqual(result.compared_values[0].type_design, "arctic goose")

    def test_unicode_nfc(self):
        result = self.assert_decision(identity(type_design="Caf\u00e9"),
                                      identity(type_design="Cafe\u0301"),
                                      IssueDecision.SAME_ISSUE,
                                      IssueReason.COMPLETE_OPERATIVE_IDENTITY)
        self.assertEqual(result.compared_values[0].type_design, "caf\u00e9")

    def test_no_punctuation_erasure_substrings_aliases_or_transliteration(self):
        for field, left, right in (("type_design", "Goose-1967", "Goose 1967"),
                                   ("type_design", "Goose", "Arctic Goose"),
                                   ("denomination", "1 dollar", "$1"),
                                   ("country", "\u00c9ire", "Eire")):
            with self.subTest(field=field):
                reason = (IssueReason.TYPE_DESIGN_CONFLICT if field == "type_design"
                          else IssueReason.ORDINARY_IDENTITY_CONFLICT)
                self.assert_decision(identity(**{field: left}), identity(**{field: right}),
                                     IssueDecision.DIFFERENT_ISSUE, reason)

    def test_precedence_all_eight_tiers(self):
        cases = (
            (identity(year="bad"), identity(item_type="BANKNOTE"),
             IssueDecision.ABSTAIN, (IssueReason.INVALID_VALUE,)),
            (identity(type_design=None, numista_n="123"),
             identity(item_type="BANKNOTE", effective_status="PARTIAL", numista_n="123"),
             IssueDecision.DIFFERENT_ISSUE, (IssueReason.ITEM_TYPE_CONFLICT,)),
            (identity(year="1968", issuer="A", reference="A", numista_n="123"),
             identity(issuer="B", reference="B", numista_n="124", effective_status="PARTIAL"),
             IssueDecision.DIFFERENT_ISSUE, (IssueReason.ORDINARY_IDENTITY_CONFLICT,)),
            (identity(year="1968", numista_n="123"),
             identity(effective_status="PARTIAL", numista_n="N#123"),
             IssueDecision.ABSTAIN, (IssueReason.CONTRADICTORY_IDENTITY_EVIDENCE,
                                     IssueReason.ORDINARY_IDENTITY_CONFLICT)),
            (identity(issuer="A", reference="A", numista_n="123", type_design=None),
             identity(issuer="B", reference="B", numista_n="124", effective_status="PARTIAL"),
             IssueDecision.DIFFERENT_ISSUE, (IssueReason.ISSUER_CONFLICT,)),
            (identity(reference="A", type_design=None, effective_status="PARTIAL"),
             identity(reference="B"), IssueDecision.ABSTAIN,
             (IssueReason.UNSCOPED_REFERENCE_DISAGREEMENT,)),
            (identity(effective_status="PARTIAL", type_design=None), identity(),
             IssueDecision.ABSTAIN, (IssueReason.INELIGIBLE_STATUS,)),
            (identity(type_design=None), identity(), IssueDecision.ABSTAIN,
             (IssueReason.MISSING_REQUIRED_IDENTITY,)),
            (identity(), identity(), IssueDecision.SAME_ISSUE,
             (IssueReason.COMPLETE_OPERATIVE_IDENTITY,)),
        )
        for left, right, decision, reasons in cases:
            with self.subTest(left=left, right=right):
                self.assert_decision(left, right, decision, *reasons)

    def test_deterministic_reason_order(self):
        cases = (
            (identity(country="USA", type_design="Other"), identity(),
             (IssueReason.ORDINARY_IDENTITY_CONFLICT, IssueReason.TYPE_DESIGN_CONFLICT)),
            (identity(numista_n="123", reference="A", issuer="A"),
             identity(numista_n="124", reference="B"),
             (IssueReason.NUMISTA_DISAGREEMENT, IssueReason.UNSCOPED_REFERENCE_DISAGREEMENT,
              IssueReason.QUALIFIER_MISSING)),
            (identity(item_type=None), identity(effective_status=None),
             (IssueReason.MISSING_ITEM_TYPE, IssueReason.INVALID_VALUE)),
        )
        for left, right, reasons in cases:
            with self.subTest(reasons=reasons):
                for _ in range(3):
                    self.assertEqual(compare_issue_identity(left, right).reason_codes, reasons)
                    self.assertEqual(compare_issue_identity(right, left).reason_codes, reasons)

    def test_symmetry(self):
        values = (identity(), identity(subject_key="B", country="USA"),
                  identity(subject_key="C", type_design=None),
                  identity(subject_key="D", numista_n="123"),
                  identity(subject_key="E", numista_n="123", country="USA"),
                  identity(item_type="BANKNOTE"), identity(effective_status="PARTIAL"),
                  identity(year="bad"), identity(issuer="A", reference="A"))
        for left, right in product(values, repeat=2):
            with self.subTest(left=left, right=right):
                forward = compare_issue_identity(left, right)
                reverse = compare_issue_identity(right, left)
                self.assertEqual(forward.decision, reverse.decision)
                self.assertEqual(forward.reason_codes, reverse.reason_codes)
                self.assertEqual(forward.compared_values, reverse.compared_values)
                self.assertEqual(forward.subject_keys, tuple(reversed(reverse.subject_keys)))

    def test_non_mutation_and_immutable_result(self):
        left, right = identity(country=" CANADA "), identity(subject_key="B")
        before = (replace(left), replace(right))
        result = compare_issue_identity(left, right)
        self.assertEqual((left, right), before)
        for value, field, replacement in (
            (left, "country", "USA"), (result, "decision", IssueDecision.DIFFERENT_ISSUE),
            (result.compared_values[0], "country", "USA"),
        ):
            with self.subTest(field=field), self.assertRaises(FrozenInstanceError):
                setattr(value, field, replacement)
        self.assertIsInstance(result.reason_codes, tuple)
        self.assertIsInstance(result.compared_values, tuple)
        self.assertIsInstance(result.subject_keys, tuple)

    def test_subject_keys_exact(self):
        keys = (" record:\tA \n", "candidate:e\u0301/#375")
        result = compare_issue_identity(identity(subject_key=keys[0]),
                                        identity(subject_key=keys[1]))
        self.assertEqual(result.subject_keys, keys)

    def test_truthiness_invalid_for_every_decision(self):
        for right in (identity(), identity(year="1968"), identity(type_design=None)):
            with self.subTest(right=right), self.assertRaises(TypeError):
                bool(compare_issue_identity(identity(), right))

    def test_no_free_text_or_detection_input_route(self):
        self.assertEqual({field.name for field in fields(IssueIdentity)},
                         {"subject_key", "item_type", "effective_status", "country",
                          "denomination", "year", "type_design", "issuer", "reference",
                          "numista_n"})
        for excluded in ("title", "notes", "comments", "history", "auto_detected",
                         "detection_confidence", "from_numista", "ocr_output",
                         "recognition_score"):
            with self.subTest(excluded=excluded), self.assertRaises(TypeError):
                identity(**{excluded: "Goose 1967 N#123"})

    def test_explicit_status_and_type_required(self):
        for missing in ("effective_status", "item_type"):
            args = {"subject_key": "A", "item_type": "COIN", "effective_status": "IDENTIFIED"}
            del args[missing]
            with self.subTest(missing=missing), self.assertRaises(TypeError):
                IssueIdentity(**args)  # type: ignore[call-arg]

    def test_wrong_projection_and_key_representation(self):
        result = compare_issue_identity(cast(IssueIdentity, {"title": "Goose"}), identity())
        self.assertEqual(result.decision, IssueDecision.ABSTAIN)
        self.assertEqual(result.reason_codes, (IssueReason.INVALID_VALUE,))
        self.assertEqual(result.compared_values, ())
        for key in (None, 123, []):
            with self.subTest(key=key):
                self.assert_decision(identity(subject_key=key), identity(),
                                     IssueDecision.ABSTAIN, IssueReason.INVALID_VALUE)

    def test_unrelated_enum_not_reinterpreted_as_evidence(self):
        class Other(Enum):
            COIN = "COIN"
            IDENTIFIED = "IDENTIFIED"
        for field, value in (("item_type", Other.COIN),
                             ("effective_status", Other.IDENTIFIED)):
            with self.subTest(field=field):
                self.assert_decision(identity(**{field: value}), identity(),
                                     IssueDecision.ABSTAIN, IssueReason.INVALID_VALUE)

    def test_malformed_type_does_not_execute_equality(self):
        class MalformedType:
            def __eq__(self, other: object) -> bool:
                raise AssertionError("Malformed evidence must not be compared")
        self.assert_decision(identity(item_type=MalformedType()), identity(),
                             IssueDecision.ABSTAIN, IssueReason.INVALID_VALUE)

    def assert_immutable_value_types(self, result: IssueEquivalenceResult) -> None:
        self.assertIs(type(result), IssueEquivalenceResult)
        self.assertIs(type(result.decision), IssueDecision)
        for container in (result.reason_codes, result.compared_values, result.subject_keys):
            self.assertIs(type(container), tuple)
        for reason in result.reason_codes:
            self.assertIs(type(reason), IssueReason)
        for key in result.subject_keys:
            self.assertTrue(key is None or type(key) is str)
        for value in result.compared_values:
            self.assertIs(type(value), NormalizedIssueIdentity)
            self.assertTrue(value.item_type is None or type(value.item_type) is ItemType)
            self.assertTrue(value.effective_status is None
                            or type(value.effective_status) is EffectiveStatus)
            for field in ("country", "denomination", "year", "type_design", "issuer",
                          "reference", "numista_n"):
                text = getattr(value, field)
                self.assertTrue(text is None or type(text) is str)

    def assert_invalid_in_both_orders(
        self, malformed: IssueIdentity, valid: IssueIdentity | None = None,
    ) -> None:
        other = identity(subject_key="other") if valid is None else valid
        forward = self.assert_decision(malformed, other, IssueDecision.ABSTAIN,
                                       IssueReason.INVALID_VALUE)
        reverse = self.assert_decision(other, malformed, IssueDecision.ABSTAIN,
                                       IssueReason.INVALID_VALUE)
        self.assertEqual(forward.compared_values, reverse.compared_values)
        self.assertEqual(forward.subject_keys, tuple(reversed(reverse.subject_keys)))
        for result in (forward, reverse):
            self.assert_immutable_value_types(result)
            with self.assertRaises(TypeError):
                bool(result)

    def test_enum_class_spoof_false_same(self):
        spoof = RuntimeClassSpoof(ItemType)
        self.assert_invalid_in_both_orders(identity(item_type=spoof))
        self.assertEqual(spoof.payload, [])

    def test_enum_class_spoof_false_different(self):
        self.assert_invalid_in_both_orders(
            identity(item_type=RuntimeClassSpoof(ItemType, agrees=False)))

    def test_status_class_spoof(self):
        self.assert_invalid_in_both_orders(
            identity(effective_status=RuntimeClassSpoof(EffectiveStatus)))

    def test_fabricated_local_enum_instances_are_rejected(self):
        for field, enum, text in (("item_type", ItemType, "COIN"),
                                   ("effective_status", EffectiveStatus, "IDENTIFIED")):
            with self.subTest(field=field):
                fabricated = str.__new__(enum, text)
                self.assert_invalid_in_both_orders(identity(**{field: fabricated}))

    def test_string_class_spoof_all_identity_fields(self):
        for field in ("country", "denomination", "year", "type_design", "issuer",
                      "reference", "numista_n"):
            with self.subTest(field=field):
                self.assert_invalid_in_both_orders(identity(**{field: RuntimeClassSpoof(str)}))

    def test_subject_key_class_spoof_not_retained(self):
        result = self.assert_decision(identity(subject_key=RuntimeClassSpoof(str)), identity(),
                                      IssueDecision.ABSTAIN, IssueReason.INVALID_VALUE)
        self.assertEqual(result.subject_keys, (None, "record: A "))
        self.assert_invalid_in_both_orders(identity(subject_key=RuntimeClassSpoof(str)))

    def test_projection_class_spoof_not_admitted(self):
        spoof = ProjectionSpoof()
        self.assert_invalid_in_both_orders(cast(IssueIdentity, spoof))
        result = compare_issue_identity(cast(IssueIdentity, spoof), identity())
        self.assertEqual(result.compared_values, ())
        self.assertEqual(result.subject_keys, (None, "record: A "))

    def test_hostile_runtime_protocols_never_executed(self):
        for field in ("item_type", "effective_status", "subject_key", "country",
                      "denomination", "year", "type_design", "issuer", "reference",
                      "numista_n"):
            with self.subTest(field=field):
                self.assert_invalid_in_both_orders(identity(**{field: HostileObject()}))
        self.assert_invalid_in_both_orders(cast(IssueIdentity, HostileObject()))

    def test_enum_and_string_like_attributes_do_not_establish_type(self):
        class LooksValid:
            name = "COIN"
            value = "COIN"

            def __str__(self) -> str:
                return "Canada"
        for field in ("item_type", "effective_status", "country", "year", "reference"):
            with self.subTest(field=field):
                self.assert_invalid_in_both_orders(identity(**{field: LooksValid()}))

    def test_user_defined_string_subclasses_are_rejected(self):
        values = {"item_type": "COIN", "effective_status": "IDENTIFIED",
                  "subject_key": "A", "country": "Canada", "denomination": "1 dollar",
                  "year": "1967", "type_design": "Goose", "issuer": "Mint A",
                  "reference": "KM#70", "numista_n": "N#123"}
        for field, text in values.items():
            with self.subTest(field=field):
                self.assert_invalid_in_both_orders(identity(**{field: HostileString(text)}))

    def test_projection_subclasses_are_rejected(self):
        values = {field.name: getattr(identity(), field.name) for field in fields(IssueIdentity)}
        self.assert_invalid_in_both_orders(DerivedIdentity(**values))

    def test_string_enums_are_not_ordinary_text(self):
        class OtherText(str, Enum):
            COUNTRY = "Canada"
            DESIGN = "Goose"
        for field, value in (("country", OtherText.COUNTRY),
                             ("type_design", OtherText.DESIGN),
                             ("reference", ItemType.COIN)):
            with self.subTest(field=field):
                self.assert_invalid_in_both_orders(identity(**{field: value}))

    def test_malformed_runtime_objects_outrank_supported_conflicts(self):
        other = identity(item_type="BANKNOTE", effective_status="PARTIAL", country="USA",
                         reference="B", numista_n="124", type_design=None)
        for field, claimed in (("item_type", ItemType), ("effective_status", EffectiveStatus),
                               ("subject_key", str), ("country", str), ("year", str),
                               ("reference", str), ("numista_n", str)):
            with self.subTest(field=field):
                self.assert_invalid_in_both_orders(
                    identity(**{field: RuntimeClassSpoof(claimed)}), other)

    def test_supported_runtime_representations_preserved(self):
        for item_type, status in product((ItemType.COIN, "COIN"),
                                        (EffectiveStatus.IDENTIFIED, "IDENTIFIED")):
            with self.subTest(item_type=item_type, status=status):
                valid = identity(item_type=item_type, effective_status=status)
                result = self.assert_decision(valid, identity(), IssueDecision.SAME_ISSUE,
                                              IssueReason.COMPLETE_OPERATIVE_IDENTITY)
                self.assert_immutable_value_types(result)
        self.assert_decision(identity(), identity(item_type=ItemType.BANKNOTE),
                             IssueDecision.DIFFERENT_ISSUE, IssueReason.ITEM_TYPE_CONFLICT)
        self.assert_decision(identity(numista_n="123"),
                             identity(numista_n="N#00123", year="1968"),
                             IssueDecision.ABSTAIN, IssueReason.CONTRADICTORY_IDENTITY_EVIDENCE,
                             IssueReason.ORDINARY_IDENTITY_CONFLICT)

    def test_malformed_object_comparison_does_not_mutate_inputs(self):
        spoof = RuntimeClassSpoof(ItemType)
        left, right = identity(item_type=spoof), identity(subject_key="B")
        before = [(value, {field.name: getattr(value, field.name) for field in fields(value)})
                  for value in (left, right)]
        self.assert_invalid_in_both_orders(left, right)
        for value, saved in before:
            for field, original in saved.items():
                self.assertIs(getattr(value, field), original)
        self.assertEqual(spoof.payload, [])


if __name__ == "__main__":
    unittest.main()
