"""Deterministic verifier for bounded identification-specialist results.

The verifier is advisory only.

It does not identify a coin, create truth, call a model or provider, infer
candidate identity, interpret confidence, mutate collection state, promote
evidence, retry specialist execution, or repair specialist output.

It verifies only whether one specialist result is consistent with the explicit
caller-supplied request and the already-frozen deterministic specialist policy.
"""

from __future__ import annotations

from dataclasses import dataclass

from identification_specialist import (
    IdentificationSpecialistRequest,
    IdentificationSpecialistResult,
)


@dataclass(frozen=True, slots=True)
class IdentificationSpecialistVerification:
    """Immutable advisory verification result."""

    accepted: bool
    reason_codes: tuple[str, ...] = ()

    def validate(self) -> None:
        """Validate deterministic verdict structure."""

        if not isinstance(self.accepted, bool):
            raise TypeError("accepted must be a bool.")

        if not isinstance(self.reason_codes, tuple):
            raise TypeError("reason_codes must be a tuple.")

        for reason_code in self.reason_codes:
            if not isinstance(reason_code, str):
                raise TypeError("reason_codes must contain only strings.")
            if not reason_code:
                raise ValueError("reason_codes must not contain empty values.")

        if self.reason_codes != tuple(sorted(self.reason_codes)):
            raise ValueError("reason_codes must be sorted.")

        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("reason_codes must be unique.")

        if self.accepted and self.reason_codes:
            raise ValueError(
                "accepted verification must not contain reason_codes."
            )

        if not self.accepted and not self.reason_codes:
            raise ValueError(
                "rejected verification must contain at least one reason_code."
            )


def verify_identification_specialist_result(
    request: IdentificationSpecialistRequest,
    result: IdentificationSpecialistResult,
) -> IdentificationSpecialistVerification:
    """Verify one result against explicit request authority and pilot policy."""

    if not isinstance(request, IdentificationSpecialistRequest):
        raise TypeError(
            "request must be an IdentificationSpecialistRequest."
        )

    if not isinstance(result, IdentificationSpecialistResult):
        raise TypeError(
            "result must be an IdentificationSpecialistResult."
        )

    request.validate()
    result.validate()

    reasons: set[str] = set()

    if result.case_id != request.case_id:
        reasons.add("case_id_mismatch")

    if result.evidence_refs != request.evidence_refs:
        reasons.add("evidence_refs_mismatch")

    if (
        result.candidate_id is not None
        and result.candidate_id not in set(request.candidate_ids)
    ):
        reasons.add("candidate_not_authorized")

    eligible_count = len(request.eligible_candidate_ids)

    if eligible_count == 1:
        expected_candidate_id = request.eligible_candidate_ids[0]

        if result.abstained:
            reasons.add("unexpected_abstention")
        elif result.candidate_id != expected_candidate_id:
            reasons.add("candidate_does_not_match_sole_eligible")
    else:
        if not result.abstained:
            reasons.add("selection_when_abstention_required")

    verification = IdentificationSpecialistVerification(
        accepted=not reasons,
        reason_codes=tuple(sorted(reasons)),
    )
    verification.validate()
    return verification
