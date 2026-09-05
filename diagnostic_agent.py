"""Deterministic diagnostic agent over bounded evaluator failure evidence.

The agent is advisory only. It consumes a ``FailureClusteringReport`` plus an
explicit, caller-supplied repository context inventory and produces a bounded,
structured diagnostic report. It does not mutate repository files, collection
records, observations, recognition engines, prompts, configuration, models, or
runtime state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence, Tuple

from confirmed_observation_failure_report import FailureCluster, FailureClusteringReport


@dataclass(frozen=True)
class RepositoryContextItem:
    """Small read-only repository context item supplied by the caller."""

    path: str
    summary: str
    tags: Tuple[str, ...] = ()


@dataclass(frozen=True)
class DiagnosticFinding:
    """One bounded diagnostic finding derived from evaluator evidence."""

    dimension: str
    key: str
    failure_count: int
    observation_ids: Tuple[str, ...]
    hypothesis: str
    recommended_action: str
    relevant_paths: Tuple[str, ...]


@dataclass(frozen=True)
class DiagnosticReport:
    """Deterministic advisory output for downstream human or agent review."""

    total_records: int
    failure_records: int
    findings: Tuple[DiagnosticFinding, ...]
    evidence_partition_counts: Mapping[str, int]
    source_clusters_considered: int
    truncated_findings: int
    warnings: Tuple[str, ...]


_DIMENSION_RULES = {
    "field": (
        "Repeated mismatches on field '{key}' suggest a field-specific extraction, normalization, reference-data, or mapping weakness.",
        "Inspect the extraction/normalization path for '{key}', reproduce the sampled observations, and add focused regression cases before proposing a change.",
        ("recognition", "ocr", "normalization", "reference", "field"),
    ),
    "category": (
        "Repeated failures in category '{key}' indicate a recurring workflow-class problem rather than an isolated observation.",
        "Trace the workflow that emits category '{key}', inspect representative evidence, and identify the narrowest reproducible failure condition.",
        ("workflow", "recognition", "evaluation", "feedback"),
    ),
    "engine": (
        "Failures concentrated under engine '{key}' may indicate an engine/version-specific regression or capability gap.",
        "Compare this engine/version against adjacent versions or methods using the same evidence partition before changing production behavior.",
        ("engine", "recognition", "model", "provider"),
    ),
    "method": (
        "Failures concentrated under recognition method '{key}' may indicate a method-specific weakness or routing problem.",
        "Reproduce sampled failures through method '{key}' and compare with alternative recognition paths before proposing remediation.",
        ("recognition", "ocr", "vision", "routing", "method"),
    ),
}


def _normalize_tag(value: str) -> str:
    return str(value).strip().casefold()


def _context_paths_for_cluster(
    cluster: FailureCluster,
    context: Sequence[RepositoryContextItem],
    *,
    max_paths: int,
) -> Tuple[str, ...]:
    if max_paths <= 0:
        return ()

    rule = _DIMENSION_RULES.get(cluster.dimension)
    preferred_tags = tuple(_normalize_tag(tag) for tag in (rule[2] if rule else ()))
    key_token = _normalize_tag(cluster.key)

    ranked = []
    for item in context:
        tags = tuple(_normalize_tag(tag) for tag in item.tags)
        haystack = " ".join((item.path, item.summary, *item.tags)).casefold()
        score = 0
        if key_token and key_token in haystack:
            score += 3
        score += sum(1 for tag in preferred_tags if tag and tag in tags)
        if score:
            ranked.append((-score, item.path))

    return tuple(path for _, path in sorted(ranked)[:max_paths])


def _finding_for_cluster(
    cluster: FailureCluster,
    context: Sequence[RepositoryContextItem],
    *,
    max_paths_per_finding: int,
) -> DiagnosticFinding:
    hypothesis_template, action_template, _ = _DIMENSION_RULES.get(
        cluster.dimension,
        (
            "Recurring failures for '{key}' require targeted investigation; the current evidence does not support a narrower causal claim.",
            "Reproduce representative observations for '{key}' and gather additional repository context before proposing remediation.",
            (),
        ),
    )
    return DiagnosticFinding(
        dimension=cluster.dimension,
        key=cluster.key,
        failure_count=cluster.count,
        observation_ids=cluster.observation_ids,
        hypothesis=hypothesis_template.format(key=cluster.key),
        recommended_action=action_template.format(key=cluster.key),
        relevant_paths=_context_paths_for_cluster(
            cluster,
            context,
            max_paths=max_paths_per_finding,
        ),
    )


def diagnose_failure_report(
    report: FailureClusteringReport,
    repository_context: Iterable[RepositoryContextItem] = (),
    *,
    max_findings: int = 10,
    max_paths_per_finding: int = 5,
) -> DiagnosticReport:
    """Produce a deterministic, bounded advisory diagnosis.

    The evaluator report remains authoritative evidence. This function does not
    infer that correlation proves causation: hypotheses are explicitly framed as
    investigation targets. ``repository_context`` is supplied by the caller and
    is never discovered or mutated by this module.
    """

    if max_findings < 0:
        raise ValueError("max_findings must be >= 0")
    if max_paths_per_finding < 0:
        raise ValueError("max_paths_per_finding must be >= 0")

    context = tuple(sorted(repository_context, key=lambda item: item.path))
    visible_clusters = report.clusters[:max_findings]
    findings = tuple(
        _finding_for_cluster(
            cluster,
            context,
            max_paths_per_finding=max_paths_per_finding,
        )
        for cluster in visible_clusters
    )

    warnings = []
    if report.truncated_clusters:
        warnings.append(
            f"source evaluator report omitted {report.truncated_clusters} cluster(s) due to its bound"
        )
    if len(report.clusters) > len(visible_clusters):
        warnings.append(
            f"diagnostic report omitted {len(report.clusters) - len(visible_clusters)} visible cluster(s) due to max_findings"
        )
    if report.failure_records and not findings:
        warnings.append("failure evidence exists but no diagnostic findings were emitted")

    return DiagnosticReport(
        total_records=report.total_records,
        failure_records=report.failure_records,
        findings=findings,
        evidence_partition_counts=dict(sorted(report.partition_counts.items())),
        source_clusters_considered=len(report.clusters),
        truncated_findings=max(0, len(report.clusters) - len(findings)),
        warnings=tuple(sorted(warnings)),
    )
