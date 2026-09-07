"""Privacy-bounded, observational AI execution audit contract.

The audit record observes existing execution, verification, evaluation, human,
and persistence outcomes. It does not authorize mutation, invoke providers,
persist data, retry work, or carry secret/raw payload material.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json
import re

from ai_evaluation_contracts import EvaluationOutcomeClassification
from identification_specialist import IdentificationSpecialistRequest
from identification_specialist_execution import IdentificationSpecialistExecutionReport


AI_EXECUTION_AUDIT_SCHEMA_VERSION = "1"
_MAX_LABEL_CHARS = 128
_MAX_ID_CHARS = 16_384
_MAX_REFERENCE_CHARS = 4_096
_MAX_REFERENCES = 64
_MAX_REASON_CODES = 32
_MAX_REASON_CODE_CHARS = 128
_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_LABEL_RE = re.compile(r"[A-Za-z0-9_.:-]{1,128}")


class HumanDisposition(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"
    NOT_REACHED = "not_reached"


class PersistenceDisposition(str, Enum):
    COMMITTED = "committed"
    REJECTED_STALE = "rejected_stale"
    BLOCKED_LOAD_FAILURE = "blocked_load_failure"
    FAILED = "failed"
    NOT_ATTEMPTED = "not_attempted"


def _validate_label(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if len(value) > _MAX_LABEL_CHARS or _LABEL_RE.fullmatch(value) is None:
        raise ValueError(
            f"{name} must be 1-{_MAX_LABEL_CHARS} ASCII label characters."
        )


def _validate_required_text(
    value: object,
    name: str,
    *,
    maximum: int,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value:
        raise ValueError(f"{name} must not be empty.")
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds maximum length {maximum}.")


def _validate_timestamp(value: object) -> None:
    if not isinstance(value, str):
        raise TypeError("occurred_at must be a string.")
    if _TIMESTAMP_RE.fullmatch(value) is None:
        raise ValueError(
            "occurred_at must be UTC RFC3339 seconds in "
            "YYYY-MM-DDTHH:MM:SSZ form."
        )
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError("occurred_at must contain a valid UTC date/time.") from exc


def _validate_sorted_unique_strings(
    values: object,
    name: str,
    *,
    maximum_items: int,
    maximum_chars: int,
) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{name} must be a tuple.")
    if len(values) > maximum_items:
        raise ValueError(f"{name} contains too many items.")

    for index, value in enumerate(values):
        _validate_required_text(
            value,
            f"{name}[{index}]",
            maximum=maximum_chars,
        )

    if values != tuple(sorted(values)):
        raise ValueError(f"{name} must be sorted.")
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must be unique.")


@dataclass(frozen=True, slots=True)
class AIExecutionAuditRecord:
    """One immutable, non-authoritative execution audit record."""

    schema_version: str
    execution_id: str
    occurred_at: str
    workflow_id: str
    executor_id: str
    case_id: str
    evidence_refs: tuple[str, ...]
    authorized_candidate_ids: tuple[str, ...]
    selected_candidate_id: str | None
    abstained: bool
    verifier_accepted: bool
    verifier_reason_codes: tuple[str, ...]
    evaluation_classification: EvaluationOutcomeClassification
    evaluation_reason_codes: tuple[str, ...]
    human_disposition: HumanDisposition
    persistence_disposition: PersistenceDisposition

    def validate(self) -> None:
        if self.schema_version != AI_EXECUTION_AUDIT_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported AI execution audit schema version: "
                f"{self.schema_version!r}."
            )
        _validate_label(self.execution_id, "execution_id")
        _validate_timestamp(self.occurred_at)
        _validate_label(self.workflow_id, "workflow_id")
        _validate_label(self.executor_id, "executor_id")
        _validate_required_text(
            self.case_id,
            "case_id",
            maximum=_MAX_ID_CHARS,
        )
        _validate_sorted_unique_strings(
            self.evidence_refs,
            "evidence_refs",
            maximum_items=_MAX_REFERENCES,
            maximum_chars=_MAX_REFERENCE_CHARS,
        )
        _validate_sorted_unique_strings(
            self.authorized_candidate_ids,
            "authorized_candidate_ids",
            maximum_items=_MAX_REFERENCES,
            maximum_chars=_MAX_ID_CHARS,
        )

        if not isinstance(self.abstained, bool):
            raise TypeError("abstained must be a bool.")
        if self.selected_candidate_id is not None:
            _validate_required_text(
                self.selected_candidate_id,
                "selected_candidate_id",
                maximum=_MAX_ID_CHARS,
            )
            if self.selected_candidate_id not in self.authorized_candidate_ids:
                raise ValueError(
                    "selected_candidate_id must be caller-authorized."
                )
        if self.abstained and self.selected_candidate_id is not None:
            raise ValueError(
                "abstained records must not include selected_candidate_id."
            )
        if not self.abstained and self.selected_candidate_id is None:
            raise ValueError(
                "non-abstained records require selected_candidate_id."
            )

        if not isinstance(self.verifier_accepted, bool):
            raise TypeError("verifier_accepted must be a bool.")
        _validate_sorted_unique_strings(
            self.verifier_reason_codes,
            "verifier_reason_codes",
            maximum_items=_MAX_REASON_CODES,
            maximum_chars=_MAX_REASON_CODE_CHARS,
        )
        if self.verifier_accepted and self.verifier_reason_codes:
            raise ValueError(
                "accepted verification must not contain reason codes."
            )
        if not self.verifier_accepted and not self.verifier_reason_codes:
            raise ValueError(
                "rejected verification requires at least one reason code."
            )

        if not isinstance(
            self.evaluation_classification,
            EvaluationOutcomeClassification,
        ):
            raise TypeError(
                "evaluation_classification must be an "
                "EvaluationOutcomeClassification."
            )
        _validate_sorted_unique_strings(
            self.evaluation_reason_codes,
            "evaluation_reason_codes",
            maximum_items=_MAX_REASON_CODES,
            maximum_chars=_MAX_REASON_CODE_CHARS,
        )
        if not isinstance(self.human_disposition, HumanDisposition):
            raise TypeError("human_disposition must be a HumanDisposition.")
        if not isinstance(
            self.persistence_disposition,
            PersistenceDisposition,
        ):
            raise TypeError(
                "persistence_disposition must be a PersistenceDisposition."
            )

        if self.persistence_disposition is PersistenceDisposition.COMMITTED:
            if self.human_disposition is not HumanDisposition.ACCEPTED:
                raise ValueError(
                    "committed persistence requires accepted human disposition."
                )
        if self.human_disposition is not HumanDisposition.ACCEPTED:
            if (
                self.persistence_disposition
                is not PersistenceDisposition.NOT_ATTEMPTED
            ):
                raise ValueError(
                    "non-accepted human dispositions require persistence "
                    "not_attempted."
                )


def build_ai_execution_audit_record(
    *,
    execution_id: str,
    occurred_at: str,
    workflow_id: str,
    request: IdentificationSpecialistRequest,
    report: IdentificationSpecialistExecutionReport,
    human_disposition: HumanDisposition,
    persistence_disposition: PersistenceDisposition,
) -> AIExecutionAuditRecord:
    """Build an audit record from existing authoritative workflow contracts."""

    if not isinstance(request, IdentificationSpecialistRequest):
        raise TypeError("request must be an IdentificationSpecialistRequest.")
    request.validate()
    if not isinstance(report, IdentificationSpecialistExecutionReport):
        raise TypeError(
            "report must be an IdentificationSpecialistExecutionReport."
        )

    report.execution.validate(request)
    report.comparison.validate()
    if report.comparison.specialist_result != report.execution.specialist_result:
        raise ValueError(
            "report comparison must preserve the executed specialist result."
        )

    result = report.execution.specialist_result
    verification = report.comparison.verification
    evaluation = report.comparison.evaluation_outcome

    record = AIExecutionAuditRecord(
        schema_version=AI_EXECUTION_AUDIT_SCHEMA_VERSION,
        execution_id=execution_id,
        occurred_at=occurred_at,
        workflow_id=workflow_id,
        executor_id=report.execution.executor_id,
        case_id=request.case_id,
        evidence_refs=request.evidence_refs,
        authorized_candidate_ids=request.candidate_ids,
        selected_candidate_id=result.candidate_id,
        abstained=result.abstained,
        verifier_accepted=verification.accepted,
        verifier_reason_codes=verification.reason_codes,
        evaluation_classification=evaluation.classification,
        evaluation_reason_codes=evaluation.reason_codes,
        human_disposition=human_disposition,
        persistence_disposition=persistence_disposition,
    )
    record.validate()
    return record


def serialize_ai_execution_audit_record(record: AIExecutionAuditRecord) -> str:
    """Return deterministic schema-v1 JSON with no arbitrary metadata channel."""

    if not isinstance(record, AIExecutionAuditRecord):
        raise TypeError("record must be an AIExecutionAuditRecord.")
    record.validate()

    payload = {
        "schema_version": record.schema_version,
        "execution_id": record.execution_id,
        "occurred_at": record.occurred_at,
        "workflow_id": record.workflow_id,
        "executor_id": record.executor_id,
        "case_id": record.case_id,
        "evidence_refs": list(record.evidence_refs),
        "authorized_candidate_ids": list(record.authorized_candidate_ids),
        "selected_candidate_id": record.selected_candidate_id,
        "abstained": record.abstained,
        "verifier_accepted": record.verifier_accepted,
        "verifier_reason_codes": list(record.verifier_reason_codes),
        "evaluation_classification": record.evaluation_classification.value,
        "evaluation_reason_codes": list(record.evaluation_reason_codes),
        "human_disposition": record.human_disposition.value,
        "persistence_disposition": record.persistence_disposition.value,
    }
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
