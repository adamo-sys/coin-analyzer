"""Deterministic adversarial harness for identification specialist results.

The harness applies explicit caller-supplied tamper definitions to an otherwise
valid identification specialist result and observes how the existing verifier
and verification/evaluation comparison seam respond.

It does not infer truth, manufacture semantic identities, repair output,
mutate collection state, or call a model/provider.

Verification and evaluation remain independent:

- verification determines policy compliance;
- evaluation determines correctness against a separately supplied
  authoritative EvaluationCase.

Some structural tampering, such as changing case identity, is intentionally
rejected by the comparison seam before an evaluation outcome can exist.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from ai_evaluation_contracts import (
    EvaluationCase,
    EvaluationCaseOutcome,
)
from identification_specialist import (
    IdentificationSpecialistRequest,
    IdentificationSpecialistResult,
)
from identification_specialist_verifier import (
    IdentificationSpecialistVerification,
    verify_identification_specialist_result,
)
from identification_verification_evaluation_report import (
    compare_identification_verification_and_evaluation,
)


class IdentificationTamperKind(str, Enum):
    """Supported explicit deterministic result mutations."""

    CANDIDATE = "CANDIDATE"
    EVIDENCE_REFS = "EVIDENCE_REFS"
    CASE_ID = "CASE_ID"
    ABSTAIN = "ABSTAIN"
    SELECT = "SELECT"


@dataclass(frozen=True, slots=True)
class IdentificationTamperDefinition:
    """One explicit caller-defined tamper operation."""

    name: str
    kind: IdentificationTamperKind
    candidate_id: str | None = None
    evidence_refs: tuple[str, ...] | None = None
    case_id: str | None = None

    def validate(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError("name must be a string.")
        if not self.name.strip():
            raise ValueError("name must not be empty.")

        if not isinstance(self.kind, IdentificationTamperKind):
            raise TypeError(
                "kind must be an IdentificationTamperKind."
            )

        if self.candidate_id is not None:
            if not isinstance(self.candidate_id, str):
                raise TypeError(
                    "candidate_id must be a string when supplied."
                )
            if not self.candidate_id.strip():
                raise ValueError(
                    "candidate_id must not be empty when supplied."
                )

        if self.case_id is not None:
            if not isinstance(self.case_id, str):
                raise TypeError(
                    "case_id must be a string when supplied."
                )
            if not self.case_id.strip():
                raise ValueError(
                    "case_id must not be empty when supplied."
                )

        if self.evidence_refs is not None:
            if not isinstance(self.evidence_refs, tuple):
                raise TypeError(
                    "evidence_refs must be a tuple when supplied."
                )

            for index, ref in enumerate(self.evidence_refs):
                if not isinstance(ref, str):
                    raise TypeError(
                        f"evidence_refs[{index}] must be a string."
                    )
                if not ref.strip():
                    raise ValueError(
                        f"evidence_refs[{index}] must not be empty."
                    )

            if self.evidence_refs != tuple(
                sorted(self.evidence_refs)
            ):
                raise ValueError(
                    "evidence_refs must be in deterministic "
                    "sorted order."
                )

            if len(set(self.evidence_refs)) != len(
                self.evidence_refs
            ):
                raise ValueError(
                    "evidence_refs must not contain duplicates."
                )

        if self.kind is IdentificationTamperKind.CANDIDATE:
            if self.candidate_id is None:
                raise ValueError(
                    "CANDIDATE tamper requires candidate_id."
                )
            if (
                self.evidence_refs is not None
                or self.case_id is not None
            ):
                raise ValueError(
                    "CANDIDATE tamper accepts only candidate_id."
                )

        elif self.kind is IdentificationTamperKind.EVIDENCE_REFS:
            if self.evidence_refs is None:
                raise ValueError(
                    "EVIDENCE_REFS tamper requires evidence_refs."
                )
            if (
                self.candidate_id is not None
                or self.case_id is not None
            ):
                raise ValueError(
                    "EVIDENCE_REFS tamper accepts only "
                    "evidence_refs."
                )

        elif self.kind is IdentificationTamperKind.CASE_ID:
            if self.case_id is None:
                raise ValueError(
                    "CASE_ID tamper requires case_id."
                )
            if (
                self.candidate_id is not None
                or self.evidence_refs is not None
            ):
                raise ValueError(
                    "CASE_ID tamper accepts only case_id."
                )

        elif self.kind is IdentificationTamperKind.ABSTAIN:
            if (
                self.candidate_id is not None
                or self.evidence_refs is not None
                or self.case_id is not None
            ):
                raise ValueError(
                    "ABSTAIN tamper accepts no additional values."
                )

        elif self.kind is IdentificationTamperKind.SELECT:
            if self.candidate_id is None:
                raise ValueError(
                    "SELECT tamper requires candidate_id."
                )
            if (
                self.evidence_refs is not None
                or self.case_id is not None
            ):
                raise ValueError(
                    "SELECT tamper accepts only candidate_id."
                )


@dataclass(frozen=True, slots=True)
class IdentificationTamperObservation:
    """Observed response to one explicit tamper operation."""

    name: str
    kind: IdentificationTamperKind
    tampered_result: IdentificationSpecialistResult
    verification: IdentificationSpecialistVerification
    evaluation_outcome: EvaluationCaseOutcome | None
    comparison_rejected: bool
    comparison_rejection_code: str | None

    def validate(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError("name must be a string.")
        if not self.name.strip():
            raise ValueError("name must not be empty.")

        if not isinstance(self.kind, IdentificationTamperKind):
            raise TypeError(
                "kind must be an IdentificationTamperKind."
            )

        if not isinstance(
            self.tampered_result,
            IdentificationSpecialistResult,
        ):
            raise TypeError(
                "tampered_result must be an "
                "IdentificationSpecialistResult."
            )
        self.tampered_result.validate()

        if not isinstance(
            self.verification,
            IdentificationSpecialistVerification,
        ):
            raise TypeError(
                "verification must be an "
                "IdentificationSpecialistVerification."
            )
        self.verification.validate()

        if not isinstance(self.comparison_rejected, bool):
            raise TypeError(
                "comparison_rejected must be a bool."
            )

        if self.comparison_rejected:
            if self.evaluation_outcome is not None:
                raise ValueError(
                    "Rejected comparison must not include "
                    "evaluation_outcome."
                )

            if not isinstance(
                self.comparison_rejection_code,
                str,
            ):
                raise TypeError(
                    "Rejected comparison requires a string "
                    "comparison_rejection_code."
                )

            if not self.comparison_rejection_code.strip():
                raise ValueError(
                    "comparison_rejection_code must not be empty."
                )

        else:
            if self.comparison_rejection_code is not None:
                raise ValueError(
                    "Successful comparison must not include "
                    "comparison_rejection_code."
                )

            if not isinstance(
                self.evaluation_outcome,
                EvaluationCaseOutcome,
            ):
                raise TypeError(
                    "Successful comparison requires an "
                    "EvaluationCaseOutcome."
                )

            self.evaluation_outcome.validate()


@dataclass(frozen=True, slots=True)
class IdentificationTamperHarnessReport:
    """Immutable ordered report over explicit tamper definitions."""

    observations: tuple[IdentificationTamperObservation, ...]

    def validate(self) -> None:
        if not isinstance(self.observations, tuple):
            raise TypeError(
                "observations must be a tuple."
            )

        if not self.observations:
            raise ValueError(
                "observations must not be empty."
            )

        seen_names: set[str] = set()

        for observation in self.observations:
            if not isinstance(
                observation,
                IdentificationTamperObservation,
            ):
                raise TypeError(
                    "observations must contain "
                    "IdentificationTamperObservation values."
                )

            observation.validate()

            if observation.name in seen_names:
                raise ValueError(
                    f"Duplicate tamper name: "
                    f"{observation.name!r}."
                )

            seen_names.add(observation.name)


def _apply_tamper(
    base_result: IdentificationSpecialistResult,
    definition: IdentificationTamperDefinition,
) -> IdentificationSpecialistResult:
    definition.validate()

    if definition.kind is IdentificationTamperKind.CANDIDATE:
        tampered = replace(
            base_result,
            candidate_id=definition.candidate_id,
            abstained=False,
        )

    elif (
        definition.kind
        is IdentificationTamperKind.EVIDENCE_REFS
    ):
        tampered = replace(
            base_result,
            evidence_refs=definition.evidence_refs,
        )

    elif definition.kind is IdentificationTamperKind.CASE_ID:
        tampered = replace(
            base_result,
            case_id=definition.case_id,
        )

    elif definition.kind is IdentificationTamperKind.ABSTAIN:
        tampered = replace(
            base_result,
            candidate_id=None,
            abstained=True,
        )

    elif definition.kind is IdentificationTamperKind.SELECT:
        tampered = replace(
            base_result,
            candidate_id=definition.candidate_id,
            abstained=False,
        )

    else:
        raise ValueError(
            f"Unsupported tamper kind: {definition.kind!r}."
        )

    tampered.validate()
    return tampered


def _comparison_rejection_code(
    exc: ValueError,
) -> str:
    message = str(exc)

    if (
        "evaluation_case case_id must match request"
        in message
    ):
        return "evaluation_case_request_case_id_mismatch"

    if (
        "evaluation_case case_id must match result"
        in message
    ):
        return "evaluation_case_result_case_id_mismatch"

    return "comparison_rejected"


def run_identification_tamper_harness(
    request: IdentificationSpecialistRequest,
    base_result: IdentificationSpecialistResult,
    evaluation_case: EvaluationCase,
    definitions: tuple[IdentificationTamperDefinition, ...],
) -> IdentificationTamperHarnessReport:
    """Run explicit deterministic tamper definitions in caller order."""

    if not isinstance(
        request,
        IdentificationSpecialistRequest,
    ):
        raise TypeError(
            "request must be an IdentificationSpecialistRequest."
        )

    if not isinstance(
        base_result,
        IdentificationSpecialistResult,
    ):
        raise TypeError(
            "base_result must be an "
            "IdentificationSpecialistResult."
        )

    if not isinstance(evaluation_case, EvaluationCase):
        raise TypeError(
            "evaluation_case must be an EvaluationCase."
        )

    if not isinstance(definitions, tuple):
        raise TypeError(
            "definitions must be a tuple."
        )

    if not definitions:
        raise ValueError(
            "definitions must not be empty."
        )

    request.validate()
    base_result.validate()
    evaluation_case.validate()

    # Establish that the untampered base triple itself is valid for
    # comparison before performing adversarial mutations.
    compare_identification_verification_and_evaluation(
        request,
        base_result,
        evaluation_case,
    )

    seen_names: set[str] = set()
    observations: list[IdentificationTamperObservation] = []

    for index, definition in enumerate(definitions):
        if not isinstance(
            definition,
            IdentificationTamperDefinition,
        ):
            raise TypeError(
                f"definitions[{index}] must be an "
                "IdentificationTamperDefinition."
            )

        definition.validate()

        if definition.name in seen_names:
            raise ValueError(
                f"Duplicate tamper name: {definition.name!r}."
            )
        seen_names.add(definition.name)

        tampered_result = _apply_tamper(
            base_result,
            definition,
        )

        verification = verify_identification_specialist_result(
            request,
            tampered_result,
        )

        try:
            comparison = (
                compare_identification_verification_and_evaluation(
                    request,
                    tampered_result,
                    evaluation_case,
                )
            )
        except ValueError as exc:
            observation = IdentificationTamperObservation(
                name=definition.name,
                kind=definition.kind,
                tampered_result=tampered_result,
                verification=verification,
                evaluation_outcome=None,
                comparison_rejected=True,
                comparison_rejection_code=(
                    _comparison_rejection_code(exc)
                ),
            )
        else:
            observation = IdentificationTamperObservation(
                name=definition.name,
                kind=definition.kind,
                tampered_result=tampered_result,
                verification=verification,
                evaluation_outcome=(
                    comparison.evaluation_outcome
                ),
                comparison_rejected=False,
                comparison_rejection_code=None,
            )

        observation.validate()
        observations.append(observation)

    report = IdentificationTamperHarnessReport(
        observations=tuple(observations),
    )
    report.validate()
    return report
