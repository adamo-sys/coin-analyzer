import copy

from confirmed_observation_failure_report import FailureCluster, FailureClusteringReport
from diagnostic_agent import RepositoryContextItem, diagnose_failure_report


def _report(*clusters, total_records=6, failure_records=4, truncated_clusters=0):
    return FailureClusteringReport(
        total_records=total_records,
        failure_records=failure_records,
        clusters=tuple(clusters),
        partition_counts={"DEVELOPMENT": 3, "GOLDEN": 1, "UNSPECIFIED": 2},
        truncated_clusters=truncated_clusters,
        max_clusters=25,
        sample_ids_per_cluster=5,
    )


def test_empty_report_returns_empty_diagnosis():
    report = _report(total_records=0, failure_records=0)

    diagnosis = diagnose_failure_report(report)

    assert diagnosis.total_records == 0
    assert diagnosis.failure_records == 0
    assert diagnosis.findings == ()
    assert diagnosis.source_clusters_considered == 0
    assert diagnosis.truncated_findings == 0
    assert diagnosis.warnings == ()


def test_field_cluster_produces_bounded_advisory_finding():
    report = _report(
        FailureCluster(
            dimension="field",
            key="year",
            count=3,
            observation_ids=("obs-1", "obs-2", "obs-3"),
        )
    )

    diagnosis = diagnose_failure_report(report)
    finding = diagnosis.findings[0]

    assert finding.dimension == "field"
    assert finding.key == "year"
    assert finding.failure_count == 3
    assert finding.observation_ids == ("obs-1", "obs-2", "obs-3")
    assert "suggest" in finding.hypothesis.casefold()
    assert "inspect" in finding.recommended_action.casefold()


def test_repository_context_is_ranked_by_key_then_relevant_tags():
    report = _report(
        FailureCluster(
            dimension="field",
            key="year",
            count=2,
            observation_ids=("a", "b"),
        )
    )
    context = [
        RepositoryContextItem(
            path="z_generic.py",
            summary="generic recognition helper",
            tags=("recognition",),
        ),
        RepositoryContextItem(
            path="year_normalizer.py",
            summary="normalizes detected year values",
            tags=("normalization", "field"),
        ),
        RepositoryContextItem(
            path="ocr_pipeline.py",
            summary="OCR extraction pipeline",
            tags=("ocr", "recognition"),
        ),
    ]

    diagnosis = diagnose_failure_report(report, context, max_paths_per_finding=2)

    assert diagnosis.findings[0].relevant_paths == (
        "year_normalizer.py",
        "ocr_pipeline.py",
    )


def test_findings_preserve_evaluator_cluster_order_and_are_bounded():
    clusters = (
        FailureCluster("category", "OCR_MISREAD", 5, ("1",)),
        FailureCluster("engine", "engine@1", 4, ("2",)),
        FailureCluster("method", "ocr", 3, ("3",)),
    )
    report = _report(*clusters)

    diagnosis = diagnose_failure_report(report, max_findings=2)

    assert [(item.dimension, item.key) for item in diagnosis.findings] == [
        ("category", "OCR_MISREAD"),
        ("engine", "engine@1"),
    ]
    assert diagnosis.source_clusters_considered == 3
    assert diagnosis.truncated_findings == 1
    assert diagnosis.warnings == (
        "diagnostic report omitted 1 visible cluster(s) due to max_findings",
    )


def test_source_evaluator_truncation_is_reported():
    report = _report(
        FailureCluster("method", "ocr", 2, ("x", "y")),
        truncated_clusters=7,
    )

    diagnosis = diagnose_failure_report(report)

    assert diagnosis.warnings == (
        "source evaluator report omitted 7 cluster(s) due to its bound",
    )


def test_failure_evidence_without_visible_findings_is_warned():
    report = _report(
        FailureCluster("field", "year", 3, ("a",)),
        failure_records=3,
    )

    diagnosis = diagnose_failure_report(report, max_findings=0)

    assert diagnosis.findings == ()
    assert diagnosis.truncated_findings == 1
    assert diagnosis.warnings == (
        "diagnostic report omitted 1 visible cluster(s) due to max_findings",
        "failure evidence exists but no diagnostic findings were emitted",
    )


def test_unknown_dimension_uses_cautious_fallback_language():
    report = _report(
        FailureCluster("custom", "mystery", 2, ("a", "b")),
    )

    finding = diagnose_failure_report(report).findings[0]

    assert "does not support a narrower causal claim" in finding.hypothesis
    assert "gather additional repository context" in finding.recommended_action
    assert finding.relevant_paths == ()


def test_partition_counts_are_sorted_and_preserved():
    report = FailureClusteringReport(
        total_records=3,
        failure_records=1,
        clusters=(),
        partition_counts={"UNSPECIFIED": 1, "GOLDEN": 1, "DEVELOPMENT": 1},
        truncated_clusters=0,
        max_clusters=25,
        sample_ids_per_cluster=5,
    )

    diagnosis = diagnose_failure_report(report)

    assert list(diagnosis.evidence_partition_counts) == [
        "DEVELOPMENT",
        "GOLDEN",
        "UNSPECIFIED",
    ]


def test_negative_bounds_are_rejected():
    report = _report()

    try:
        diagnose_failure_report(report, max_findings=-1)
    except ValueError:
        pass
    else:
        raise AssertionError("negative max_findings should raise ValueError")

    try:
        diagnose_failure_report(report, max_paths_per_finding=-1)
    except ValueError:
        pass
    else:
        raise AssertionError("negative max_paths_per_finding should raise ValueError")


def test_diagnosis_does_not_mutate_report_or_context():
    report = _report(
        FailureCluster("engine", "coin_recognition@1", 2, ("1", "2")),
    )
    context = [
        RepositoryContextItem(
            path="image_analyzer.py",
            summary="recognition engine integration",
            tags=("engine", "recognition"),
        )
    ]
    report_before = copy.deepcopy(report)
    context_before = copy.deepcopy(context)

    diagnose_failure_report(report, context)

    assert report == report_before
    assert context == context_before
