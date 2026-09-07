"""Bounded deterministic identification specialist pilot.

This module is deliberately local, read-only, and advisory.

It does not invoke a model or provider, create candidate identities, interpret
confidence, mutate collection state, promote evidence, or perform learning.

The pilot consumes explicit caller-supplied candidate IDs, explicit caller-
supplied eligibility, and explicit evidence references. Its intentionally
narrow policy selects a candidate only when exactly one eligible candidate
remains; otherwise it explicitly abstains.
"""

from __future__ import annotations

from dataclasses import dataclass

from ai_evaluation_contracts import (
    CURRENT_AI_EVALUATION_SCHEMA_VERSION,
    EvaluationCase,
    ObservedEvaluationResult,
)


@dataclass(frozen=True, slots=True)
class IdentificationSpecialistRequest:
    """Immutable caller-authorized input for one specialist decision."""

    schema_version: str
    case_id: str
    candidate_ids: tuple[str, ...]
    eligible_candidate_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        """Validate identities without inventing or normalizing them."""

        # Reuse the frozen evaluation contract for the common case identity,
        # candidate identity, evidence identity, ordering, uniqueness, and
        # bounded-size rules.
        EvaluationCase(
            schema_version=self.schema_version,
            case_id=self.case_id,
            allowed_candidate_ids=self.candidate_ids,
            evidence_refs=self.evidence_refs,
        ).validate()

        if not isinstance(self.eligible_candidate_ids, tuple):
            raise TypeError("eligible_candidate_ids must be a tuple.")

        for candidate_id in self.eligible_candidate_ids:
            if not isinstance(candidate_id, str):
                raise TypeError(
                    "eligible_candidate_ids must contain only strings."
                )
            if not candidate_id:
                raise ValueError(
                    "eligible_candidate_ids must not contain empty IDs."
                )

        if self.eligible_candidate_ids != tuple(
            sorted(self.eligible_candidate_ids)
        ):
            raise ValueError("eligible_candidate_ids must be sorted.")

        if len(self.eligible_candidate_ids) != len(
            set(self.eligible_candidate_ids)
        ):
            raise ValueError("eligible_candidate_ids must be unique.")

        candidate_set = set(self.candidate_ids)
        unknown = tuple(
            candidate_id
            for candidate_id in self.eligible_candidate_ids
            if candidate_id not in candidate_set
        )
        if unknown:
            raise ValueError(
                "eligible_candidate_ids must be a subset of candidate_ids; "
                f"unknown={unknown!r}."
            )


@dataclass(frozen=True, slots=True)
class IdentificationSpecialistResult:
    """Immutable advisory decision emitted by the specialist."""

    schema_version: str
    case_id: str
    candidate_id: str | None = None
    abstained: bool = False
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        """Reuse the frozen observed-result contract."""

        ObservedEvaluationResult(
            schema_version=self.schema_version,
            case_id=self.case_id,
            candidate_id=self.candidate_id,
            abstained=self.abstained,
            evidence_refs=self.evidence_refs,
        ).validate()


def run_identification_specialist(
    request: IdentificationSpecialistRequest,
) -> IdentificationSpecialistResult:
    """Run the deliberately narrow deterministic pilot policy.

    Exactly one caller-supplied eligible candidate -> select it.

    Zero or multiple eligible candidates -> explicit abstention.

    No identity is created, inferred, ranked, normalized, hashed, concatenated,
    or derived from evidence.
    """

    if not isinstance(request, IdentificationSpecialistRequest):
        raise TypeError(
            "request must be an IdentificationSpecialistRequest."
        )

    request.validate()

    if len(request.eligible_candidate_ids) == 1:
        result = IdentificationSpecialistResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id=request.case_id,
            candidate_id=request.eligible_candidate_ids[0],
            abstained=False,
            evidence_refs=request.evidence_refs,
        )
    else:
        result = IdentificationSpecialistResult(
            schema_version=CURRENT_AI_EVALUATION_SCHEMA_VERSION,
            case_id=request.case_id,
            candidate_id=None,
            abstained=True,
            evidence_refs=request.evidence_refs,
        )

    result.validate()
    return result
