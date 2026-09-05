import copy
from typing import Any

from confirmed_observation_evaluator import evaluate_confirmed_observations
from confirmed_observations import (
    ConfirmedObservationRecord,
    FeedbackCategory,
    ObservationOutcome,
)


def _record(
    *,
    observation_id="obs-1",
    outcome=ObservationOutcome.ACCEPTED,
    category=FeedbackCategory.OTHER,
    suggested=None,
    confirmed=None,
    confidence: Any = 0.8,
    engine_name="coin_recognition",
    engine_version="1.0",
    method="ocr",
):
    evidence = {} if confidence is ... else {"confidence": confidence}
    return ConfirmedObservationRecord(
        observation_id=observation_id,
        created_at="2026-09-05T12:00:00Z",
        outcome=outcome,
        category=category,
        suggested_values=suggested or {"country": "Canada", "year": "1967"},
        confirmed_values=(
            confirmed
            if confirmed is not None
            else ({"country": "Canada", "year": "1967"} if outcome in {ObservationOutcome.ACCEPTED, ObservationOutcome.CORRECTED} else {})
        ),
        engine_name=engine_name,
        engine_version=engine_version,
        recognition_method=method,
        application_version="1.1.0",
        evidence_snapshot=evidence,
        source_workflow="test",
    )


def test_empty_input_returns_zeroed_report():
    report = evaluate_confirmed_observations([])

    assert report.total_records == 0
    assert report.evaluable_records == 0
    assert report.exact_match_records == 0
    assert report.exact_match_accuracy is None
    assert report.field_agreements == ()
    assert report.outcome_counts == {}
    assert report.confidence.available == 0
    assert report.confidence.unavailable == 0
    assert report.warnings == ()


def test_only_accepted_and_corrected_records_are_evaluable():
    records = [
        _record(observation_id="accepted", outcome=ObservationOutcome.ACCEPTED),
        _record(
            observation_id="corrected",
            outcome=ObservationOutcome.CORRECTED,
            confirmed={"country": "Canada", "year": "1968"},
        ),
        _record(observation_id="deferred", outcome=ObservationOutcome.DEFERRED),
        _record(observation_id="rejected", outcome=ObservationOutcome.REJECTED),
    ]

    report = evaluate_confirmed_observations(records)

    assert report.total_records == 4
    assert report.evaluable_records == 2
    assert report.exact_match_records == 1
    assert report.exact_match_accuracy == 0.5
    assert report.outcome_counts == {
        "ACCEPTED": 1,
        "CORRECTED": 1,
        "DEFERRED": 1,
        "REJECTED": 1,
    }


def test_exact_match_and_field_agreement_are_case_insensitive_and_trimmed():
    records = [
        _record(
            observation_id="a",
            suggested={"country": " Canada ", "year": "1967", "denomination": "1 Dollar"},
            confirmed={"country": "canada", "year": "1967", "denomination": "1 dollar"},
        ),
        _record(
            observation_id="b",
            outcome=ObservationOutcome.CORRECTED,
            suggested={"country": "Canada", "year": "1967", "denomination": "1 Dollar"},
            confirmed={"country": "Canada", "year": "1968", "denomination": "1 Dollar"},
        ),
    ]

    report = evaluate_confirmed_observations(records)
    agreements = {item.field_name: item for item in report.field_agreements}

    assert report.exact_match_records == 1
    assert agreements["country"].compared == 2
    assert agreements["country"].matched == 2
    assert agreements["country"].accuracy == 1.0
    assert agreements["year"].compared == 2
    assert agreements["year"].matched == 1
    assert agreements["year"].accuracy == 0.5
    assert agreements["denomination"].accuracy == 1.0


def test_no_shared_fields_is_evaluable_but_not_an_exact_match():
    record = _record(
        suggested={"country": "Canada"},
        confirmed={"year": "1967"},
    )

    report = evaluate_confirmed_observations([record])

    assert report.evaluable_records == 1
    assert report.exact_match_records == 0
    assert report.exact_match_accuracy == 0.0
    assert report.field_agreements == ()


def test_confidence_summary_accepts_closed_interval_endpoints():
    records = [
        _record(observation_id="zero", confidence=0.0),
        _record(observation_id="one", confidence=1.0),
    ]

    report = evaluate_confirmed_observations(records)

    assert report.confidence.available == 2
    assert report.confidence.unavailable == 0
    assert report.confidence.minimum == 0.0
    assert report.confidence.maximum == 1.0
    assert report.confidence.mean == 0.5


def test_invalid_confidence_values_are_unavailable_and_warned_deterministically():
    records = [
        _record(observation_id="z-string", confidence="high"),
        _record(observation_id="a-bool", confidence=True),
        _record(observation_id="m-low", confidence=-0.1),
        _record(observation_id="n-high", confidence=1.1),
        _record(observation_id="missing", confidence=...),
        _record(observation_id="none", confidence=None),
    ]

    report = evaluate_confirmed_observations(records)

    assert report.confidence.available == 0
    assert report.confidence.unavailable == 6
    assert report.warnings == tuple(sorted(report.warnings))
    assert report.warnings == (
        "a-bool: boolean confidence ignored",
        "m-low: out-of-range confidence ignored",
        "n-high: out-of-range confidence ignored",
        "z-string: non-numeric confidence ignored",
    )


def test_category_engine_version_and_method_counts_are_sorted_and_complete():
    records = [
        _record(
            observation_id="2",
            category=FeedbackCategory.OCR_MISREAD,
            engine_name="zeta",
            engine_version="2",
            method="vision",
        ),
        _record(
            observation_id="1",
            category=FeedbackCategory.IDENTIFICATION_MISMATCH,
            engine_name="alpha",
            engine_version="1",
            method="ocr",
        ),
    ]

    report = evaluate_confirmed_observations(records)

    assert list(report.category_counts) == sorted(report.category_counts)
    assert list(report.engine_version_counts) == sorted(report.engine_version_counts)
    assert list(report.recognition_method_counts) == sorted(report.recognition_method_counts)
    assert report.category_counts == {
        "IDENTIFICATION_MISMATCH": 1,
        "OCR_MISREAD": 1,
    }
    assert report.engine_version_counts == {"alpha@1": 1, "zeta@2": 1}
    assert report.recognition_method_counts == {"ocr": 1, "vision": 1}


def test_evaluation_does_not_mutate_source_records():
    records = [
        _record(
            suggested={"country": "Canada", "year": "1967"},
            confirmed={"country": "Canada", "year": "1968"},
            confidence=0.42,
        )
    ]
    before = copy.deepcopy(records)

    evaluate_confirmed_observations(records)

    assert records == before
