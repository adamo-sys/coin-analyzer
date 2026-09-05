"""Deterministic, read-only evaluation over collector-confirmed observations.

This module intentionally does not mutate observations, collection records,
recognition engines, prompts, configuration, or model state. It summarizes
existing evidence so future improvement work can be measured before promotion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Mapping, Optional, Tuple

from confirmed_observations import ConfirmedObservationRecord, ObservationOutcome


@dataclass(frozen=True)
class FieldAgreement:
    field_name: str
    compared: int
    matched: int

    @property
    def accuracy(self) -> Optional[float]:
        if self.compared == 0:
            return None
        return self.matched / self.compared


@dataclass(frozen=True)
class ConfidenceSummary:
    available: int
    unavailable: int
    minimum: Optional[float]
    maximum: Optional[float]
    mean: Optional[float]


@dataclass(frozen=True)
class ObservationEvaluationReport:
    total_records: int
    outcome_counts: Mapping[str, int]
    evaluable_records: int
    exact_match_records: int
    field_agreements: Tuple[FieldAgreement, ...]
    category_counts: Mapping[str, int]
    engine_version_counts: Mapping[str, int]
    recognition_method_counts: Mapping[str, int]
    confidence: ConfidenceSummary
    warnings: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def exact_match_accuracy(self) -> Optional[float]:
        if self.evaluable_records == 0:
            return None
        return self.exact_match_records / self.evaluable_records


def evaluate_confirmed_observations(
    records: Iterable[ConfirmedObservationRecord],
) -> ObservationEvaluationReport:
    """Return a deterministic summary without mutating source records.

    Only ACCEPTED and CORRECTED observations with confirmed values participate
    in agreement metrics. Suggested/confirmed comparisons are case-insensitive
    string comparisons after the normalization already owned by
    ``ConfirmedObservationRecord``.

    Confidence is summarized only when ``evidence_snapshot['confidence']`` is a
    numeric value in the closed interval [0, 1]. Values outside that range or
    non-numeric values are treated as unavailable and reported through warnings.
    The evaluator does not interpret a score as a calibrated probability.
    """

    rows = tuple(records)
    outcome_counts: Dict[str, int] = {}
    category_counts: Dict[str, int] = {}
    engine_version_counts: Dict[str, int] = {}
    method_counts: Dict[str, int] = {}
    field_compared: Dict[str, int] = {}
    field_matched: Dict[str, int] = {}
    confidence_values = []
    unavailable_confidence = 0
    warnings = []
    evaluable_records = 0
    exact_match_records = 0

    for record in rows:
        outcome_counts[record.outcome.value] = outcome_counts.get(record.outcome.value, 0) + 1
        category_counts[record.category.value] = category_counts.get(record.category.value, 0) + 1

        engine_key = f"{record.engine_name}@{record.engine_version}"
        engine_version_counts[engine_key] = engine_version_counts.get(engine_key, 0) + 1
        method_counts[record.recognition_method] = method_counts.get(record.recognition_method, 0) + 1

        confidence = record.evidence_snapshot.get("confidence")
        if isinstance(confidence, bool):
            unavailable_confidence += 1
            warnings.append(f"{record.observation_id}: boolean confidence ignored")
        elif isinstance(confidence, (int, float)):
            numeric_confidence = float(confidence)
            if 0.0 <= numeric_confidence <= 1.0:
                confidence_values.append(numeric_confidence)
            else:
                unavailable_confidence += 1
                warnings.append(f"{record.observation_id}: out-of-range confidence ignored")
        else:
            unavailable_confidence += 1
            if confidence is not None:
                warnings.append(f"{record.observation_id}: non-numeric confidence ignored")

        if record.outcome not in {ObservationOutcome.ACCEPTED, ObservationOutcome.CORRECTED}:
            continue
        if not record.confirmed_values:
            continue

        evaluable_records += 1
        shared_fields = sorted(set(record.suggested_values) & set(record.confirmed_values))
        record_exact = bool(shared_fields)

        for field_name in shared_fields:
            suggested = str(record.suggested_values[field_name]).strip().casefold()
            confirmed = str(record.confirmed_values[field_name]).strip().casefold()
            field_compared[field_name] = field_compared.get(field_name, 0) + 1
            if suggested == confirmed:
                field_matched[field_name] = field_matched.get(field_name, 0) + 1
            else:
                record_exact = False

        if record_exact:
            exact_match_records += 1

    agreements = tuple(
        FieldAgreement(
            field_name=field_name,
            compared=field_compared[field_name],
            matched=field_matched.get(field_name, 0),
        )
        for field_name in sorted(field_compared)
    )

    if confidence_values:
        confidence_summary = ConfidenceSummary(
            available=len(confidence_values),
            unavailable=unavailable_confidence,
            minimum=min(confidence_values),
            maximum=max(confidence_values),
            mean=sum(confidence_values) / len(confidence_values),
        )
    else:
        confidence_summary = ConfidenceSummary(
            available=0,
            unavailable=unavailable_confidence,
            minimum=None,
            maximum=None,
            mean=None,
        )

    return ObservationEvaluationReport(
        total_records=len(rows),
        outcome_counts=dict(sorted(outcome_counts.items())),
        evaluable_records=evaluable_records,
        exact_match_records=exact_match_records,
        field_agreements=agreements,
        category_counts=dict(sorted(category_counts.items())),
        engine_version_counts=dict(sorted(engine_version_counts.items())),
        recognition_method_counts=dict(sorted(method_counts.items())),
        confidence=confidence_summary,
        warnings=tuple(sorted(warnings)),
    )
