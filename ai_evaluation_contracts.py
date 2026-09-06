"""Immutable contracts for bounded product-side AI evaluation.

Issue #169 Slice A defines deterministic local evaluation contracts only.
These contracts do not call models, create truth labels, mutate collection
state, promote evidence, persist data, or authorize agent orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


CURRENT_AI_EVALUATION_SCHEMA_VERSION = "1"

_MAX_ID_CHARS = 16_384
_MAX_REFERENCE_CHARS = 4_096
_MAX_REFERENCES = 64
_MAX_REASON_CODES = 32
_MAX_REASON_CODE_CHARS = 128
_MAX_CASES = 100_000


class EvaluationOutcomeClassification(str, Enum):
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    ABSTAINED = "ABSTAINED"
    INVALID_OR_MISSING = "INVALID_OR_MISSING"


def _required_text(value: object, name: str, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value.strip():
        raise ValueError(f"{name} must not be empty.")
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds maximum length {maximum}.")
    return value


def _sorted_unique_strings(
    values: object,
    name: str,
    *,
    maximum_items: int,
    maximum_chars: int,
) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{name} must be a tuple.")
    if len(values) > maximum_items:
        raise ValueError(f"{name} contains too many items.")

    for index, value in enumerate(values):
        _required_text(
            value,
            f"{name}[{index}]",
            maximum=maximum_chars,
        )

    if values != tuple(sorted(values)):
        raise ValueError(f"{name} must be in deterministic sorted order.")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must not contain duplicates.")

    return values


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    """One caller-supplied authoritative evaluation case."""

    schema_version: str
    case_id: str
    allowed_candidate_ids: tuple[str, ...] = ()
    require_abstention: bool = False
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.schema_version != CURRENT_AI_EVALUATION_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported AI evaluation schema version: "
                f"{self.schema_version!r}."
            )

        _required_text(self.case_id, "case_id", maximum=_MAX_ID_CHARS)

        _sorted_unique_strings(
            self.allowed_candidate_ids,
            "allowed_candidate_ids",
            maximum_items=_MAX_REFERENCES,
            maximum_chars=_MAX_ID_CHARS,
        )

        if not isinstance(self.require_abstention, bool):
            raise TypeError("require_abstention must be a bool.")

        if self.require_abstention and self.allowed_candidate_ids:
            raise ValueError(
                "A case requiring abstention must not define "
                "allowed_candidate_ids."
            )

        if not self.require_abstention and not self.allowed_candidate_ids:
            raise ValueError(
                "A non-abstention case requires at least one "
                "allowed_candidate_id."
            )

        _sorted_unique_strings(
            self.evidence_refs,
            "evidence_refs",
            maximum_items=_MAX_REFERENCES,
            maximum_chars=_MAX_REFERENCE_CHARS,
        )


@dataclass(frozen=True, slots=True)
class ObservedEvaluationResult:
    """One observed candidate result or explicit abstention."""

    schema_version: str
    case_id: str
    candidate_id: str | None = None
    abstained: bool = False
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.schema_version != CURRENT_AI_EVALUATION_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported AI evaluation schema version: "
                f"{self.schema_version!r}."
            )

        _required_text(self.case_id, "case_id", maximum=_MAX_ID_CHARS)

        if not isinstance(self.abstained, bool):
            raise TypeError("abstained must be a bool.")

        if self.candidate_id is not None:
            _required_text(
                self.candidate_id,
                "candidate_id",
                maximum=_MAX_ID_CHARS,
            )

        if self.abstained and self.candidate_id is not None:
            raise ValueError(
                "An abstained result must not include candidate_id."
            )

        if not self.abstained and self.candidate_id is None:
            raise ValueError(
                "A non-abstained observed result requires candidate_id."
            )

        _sorted_unique_strings(
            self.evidence_refs,
            "evidence_refs",
            maximum_items=_MAX_REFERENCES,
            maximum_chars=_MAX_REFERENCE_CHARS,
        )


@dataclass(frozen=True, slots=True)
class EvaluationCaseOutcome:
    """One explicit outcome classification for one evaluation case."""

    schema_version: str
    case_id: str
    classification: EvaluationOutcomeClassification
    observed_candidate_id: str | None = None
    evidence_refs: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.schema_version != CURRENT_AI_EVALUATION_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported AI evaluation schema version: "
                f"{self.schema_version!r}."
            )

        _required_text(self.case_id, "case_id", maximum=_MAX_ID_CHARS)

        if not isinstance(
            self.classification,
            EvaluationOutcomeClassification,
        ):
            raise TypeError(
                "classification must be an "
                "EvaluationOutcomeClassification."
            )

        if self.observed_candidate_id is not None:
            _required_text(
                self.observed_candidate_id,
                "observed_candidate_id",
                maximum=_MAX_ID_CHARS,
            )

        if (
            self.classification
            in {
                EvaluationOutcomeClassification.ABSTAINED,
                EvaluationOutcomeClassification.INVALID_OR_MISSING,
            }
            and self.observed_candidate_id is not None
        ):
            raise ValueError(
                f"{self.classification.value} outcomes must not include "
                "observed_candidate_id."
            )

        if (
            self.classification
            in {
                EvaluationOutcomeClassification.CORRECT,
                EvaluationOutcomeClassification.INCORRECT,
            }
            and self.observed_candidate_id is None
        ):
            raise ValueError(
                f"{self.classification.value} outcomes require "
                "observed_candidate_id."
            )

        _sorted_unique_strings(
            self.evidence_refs,
            "evidence_refs",
            maximum_items=_MAX_REFERENCES,
            maximum_chars=_MAX_REFERENCE_CHARS,
        )

        _sorted_unique_strings(
            self.reason_codes,
            "reason_codes",
            maximum_items=_MAX_REASON_CODES,
            maximum_chars=_MAX_REASON_CODE_CHARS,
        )

        if (
            self.classification
            is EvaluationOutcomeClassification.INVALID_OR_MISSING
            and not self.reason_codes
        ):
            raise ValueError(
                "INVALID_OR_MISSING outcomes require at least one reason code."
            )


@dataclass(frozen=True, slots=True)
class EvaluationAggregate:
    total: int
    correct: int
    incorrect: int
    abstained: int
    invalid_or_missing: int

    def validate(self) -> None:
        values = {
            "total": self.total,
            "correct": self.correct,
            "incorrect": self.incorrect,
            "abstained": self.abstained,
            "invalid_or_missing": self.invalid_or_missing,
        }

        for name, value in values.items():
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer.")
            if value < 0:
                raise ValueError(f"{name} must not be negative.")

        if self.total > _MAX_CASES:
            raise ValueError(
                f"total exceeds maximum case count {_MAX_CASES}."
            )

        if (
            self.correct
            + self.incorrect
            + self.abstained
            + self.invalid_or_missing
            != self.total
        ):
            raise ValueError(
                "Outcome counts must sum exactly to total."
            )


def aggregate_evaluation_outcomes(
    outcomes: tuple[EvaluationCaseOutcome, ...],
) -> EvaluationAggregate:
    """Aggregate explicit outcomes without inferring or creating truth."""

    if not isinstance(outcomes, tuple):
        raise TypeError("outcomes must be a tuple.")

    if len(outcomes) > _MAX_CASES:
        raise ValueError(
            f"outcomes contains more than {_MAX_CASES} cases."
        )

    seen_case_ids: set[str] = set()

    counts = {
        EvaluationOutcomeClassification.CORRECT: 0,
        EvaluationOutcomeClassification.INCORRECT: 0,
        EvaluationOutcomeClassification.ABSTAINED: 0,
        EvaluationOutcomeClassification.INVALID_OR_MISSING: 0,
    }

    for outcome in outcomes:
        if not isinstance(outcome, EvaluationCaseOutcome):
            raise TypeError(
                "outcomes must contain EvaluationCaseOutcome values."
            )

        outcome.validate()

        if outcome.case_id in seen_case_ids:
            raise ValueError(
                f"Duplicate evaluation case_id: {outcome.case_id!r}."
            )

        seen_case_ids.add(outcome.case_id)
        counts[outcome.classification] += 1

    aggregate = EvaluationAggregate(
        total=len(outcomes),
        correct=counts[EvaluationOutcomeClassification.CORRECT],
        incorrect=counts[EvaluationOutcomeClassification.INCORRECT],
        abstained=counts[EvaluationOutcomeClassification.ABSTAINED],
        invalid_or_missing=counts[
            EvaluationOutcomeClassification.INVALID_OR_MISSING
        ],
    )

    aggregate.validate()
    return aggregate
