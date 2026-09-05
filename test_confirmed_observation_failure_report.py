import copy

import pytest

from confirmed_observation_failure_report import cluster_confirmed_failures
from confirmed_observations import (
    ConfirmedObservationRecord,
    FeedbackCategory,
    ObservationOutcome,
)


def _record(
    *,
    observation_id="obs-1",
    outcome=ObservationOutcome.CORRECTED,
    category=FeedbackCategory.IDENTIFICATION_MISMATCH,
    suggested=None,
    confirmed=None,
    engine_name="coin_recognition",
    engine_version="1.0",
    method="ocr",
    partition=None,
):
    evidence = {}
    if partition is not None:
        evidence["evaluation_partition"] = partition
    return ConfirmedObservationRecord(
        observation_id=observation_id,
        created_at="2026-09-05T12:00:00Z",
        outcome=outcome,
        category=category,
        suggested_values=suggested or {"country": "Canada", "year": "1967"},
        confirmed_values=(
            confirmed
            if confirmed is not None
            else (
                {"country": "Canada", "year": "1968"}
                if outcome in {ObservationOutcome.ACCEPTED, ObservationOutcome.CORRECTED}
                else {}
            )
        ),
        engine_name=engine_name,
        engine_version=engine_version,
        recognition_method=method,
        application_version="1.1.0",
        evidence_snapshot=evidence,
        source_workflow="test",
    )


def _cluster_map(report):
    return {(item.dimension, item.key): item for item in report.clusters}


def test_empty_input_returns_empty_bounded_report():
    report = cluster_confirmed_failures([])

    assert report.total_records == 0
    assert report.failure_records == 0
    assert report.clusters == ()
    assert report.partition_counts == {}
    assert report.truncated_clusters == 0
    assert report.max_clusters == 25
    assert report.sample_ids_per_cluster == 5


def test_only_corrected_and_rejected_records_are_failure_evidence():
    records = [
        _record(observation_id="accepted", outcome=ObservationOutcome.ACCEPTED),
        _record(observation_id="corrected", outcome=ObservationOutcome.CORRECTED),
        _record(observation_id="rejected", outcome=ObservationOutcome.REJECTED),
        _record(observation_id="deferred", outcome=ObservationOutcome.DEFERRED),
    ]

    report = cluster_confirmed_failures(records)

    assert report.total_records == 4
    assert report.failure_records == 2
    clusters = _cluster_map(report)
    assert clusters[("category", "IDENTIFICATION_MISMATCH")].count == 2
    assert clusters[("engine", "coin_recognition@1.0")].count == 2
    assert clusters[("method", "ocr")].count == 2


def test_corrected_records_cluster_only_mismatched_shared_fields():
    records = [
        _record(
            observation_id="b",
            suggested={"country": " Canada ", "year": "1967", "denomination": "1 Dollar"},
            confirmed={"country": "canada", "year": "1968", "denomination": "1 dollar"},
        ),
        _record(
            observation_id="a",
            suggested={"country": "Canada", "year": "1966"},
            confirmed={"country": "Canada", "year": "1968"},
        ),
    ]

    report = cluster_confirmed_failures(records)
    clusters = _cluster_map(report)

    assert clusters[("field", "year")].count == 2
    assert clusters[("field", "year")].observation_ids == ("a", "b")
    assert ("field", "country") not in clusters
    assert ("field", "denomination") not in clusters


def test_rejected_record_does_not_invent_field_mismatch_clusters():
    report = cluster_confirmed_failures(
        [_record(observation_id="r", outcome=ObservationOutcome.REJECTED)]
    )

    assert report.failure_records == 1
    assert not any(item.dimension == "field" for item in report.clusters)


def test_clusters_cover_category_engine_method_and_sort_deterministically():
    records = [
        _record(
            observation_id="3",
            category=FeedbackCategory.OCR_MISREAD,
            engine_name="zeta",
            engine_version="2",
            method="vision",
        ),
        _record(observation_id="2"),
        _record(observation_id="1"),
    ]

    report = cluster_confirmed_failures(records)

    assert list(report.clusters) == sorted(
        report.clusters,
        key=lambda item: (-item.count, item.dimension, item.key),
    )
    clusters = _cluster_map(report)
    assert clusters[("category", "IDENTIFICATION_MISMATCH")].count == 2
    assert clusters[("category", "OCR_MISREAD")].count == 1
    assert clusters[("engine", "coin_recognition@1.0")].count == 2
    assert clusters[("engine", "zeta@2")].count == 1
    assert clusters[("method", "ocr")].count == 2
    assert clusters[("method", "vision")].count == 1


def test_cluster_and_sample_bounds_are_enforced_and_reported():
    records = [
        _record(
            observation_id=f"obs-{index}",
            category=FeedbackCategory.OCR_MISREAD,
            suggested={"year": str(1900 + index)},
            confirmed={"year": "2000"},
        )
        for index in range(8)
    ]

    report = cluster_confirmed_failures(
        records,
        max_clusters=2,
        sample_ids_per_cluster=3,
    )

    assert len(report.clusters) == 2
    assert report.truncated_clusters > 0
    assert all(len(item.observation_ids) <= 3 for item in report.clusters)
    assert report.clusters[0].observation_ids == ("obs-0", "obs-1", "obs-2")


def test_partition_counts_distinguish_dev_validation_golden_and_unspecified():
    records = [
        _record(observation_id="dev", partition="dev"),
        _record(observation_id="validation", partition="validation"),
        _record(observation_id="golden", partition="frozen golden"),
        _record(observation_id="unknown", partition="mystery"),
        _record(observation_id="missing", partition=None),
    ]

    report = cluster_confirmed_failures(records)

    assert report.partition_counts == {
        "DEVELOPMENT": 1,
        "GOLDEN": 1,
        "UNSPECIFIED": 2,
        "VALIDATION": 1,
    }


def test_negative_bounds_are_rejected():
    with pytest.raises(ValueError, match="max_clusters"):
        cluster_confirmed_failures([], max_clusters=-1)
    with pytest.raises(ValueError, match="sample_ids_per_cluster"):
        cluster_confirmed_failures([], sample_ids_per_cluster=-1)


def test_failure_clustering_does_not_mutate_source_records():
    records = [
        _record(
            observation_id="obs",
            suggested={"country": "Canada", "year": "1967"},
            confirmed={"country": "Canada", "year": "1968"},
            partition="golden",
        )
    ]
    before = copy.deepcopy(records)

    cluster_confirmed_failures(records)

    assert records == before
