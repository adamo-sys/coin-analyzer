"""Deterministic, bounded failure clustering over confirmed observation evidence.

This module is read-only. It consumes the structural observation contract used by
``confirmed_observation_evaluator`` and produces diagnostic evidence only. It does
not mutate collection records, observations, recognition engines, prompts,
configuration, models, or repository state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Tuple

from confirmed_observation_evaluator import ObservationLike, _enumish_value


FAILURE_OUTCOMES = frozenset({"CORRECTED", "REJECTED"})
PARTITION_KEY = "evaluation_partition"
PARTITION_ALIASES = {
    "DEV": "DEVELOPMENT",
    "DEVELOPMENT": "DEVELOPMENT",
    "VALIDATION": "VALIDATION",
    "VAL": "VALIDATION",
    "GOLDEN": "GOLDEN",
    "FROZEN_GOLDEN": "GOLDEN",
}


@dataclass(frozen=True)
class FailureCluster:
    dimension: str
    key: str
    count: int
    observation_ids: Tuple[str, ...]


@dataclass(frozen=True)
class FailureClusteringReport:
    total_records: int
    failure_records: int
    clusters: Tuple[FailureCluster, ...]
    partition_counts: Mapping[str, int]
    truncated_clusters: int
    max_clusters: int
    sample_ids_per_cluster: int


def _normalized_value(value: object) -> str:
    return str(value).strip().casefold()


def _partition(record: ObservationLike) -> str:
    raw = record.evidence_snapshot.get(PARTITION_KEY)
    if raw is None:
        return "UNSPECIFIED"
    normalized = str(raw).strip().upper().replace("-", "_").replace(" ", "_")
    return PARTITION_ALIASES.get(normalized, "UNSPECIFIED")


def _add_cluster(
    buckets: Dict[Tuple[str, str], list[str]],
    dimension: str,
    key: str,
    observation_id: str,
) -> None:
    bucket = buckets.setdefault((dimension, key), [])
    bucket.append(observation_id)


def cluster_confirmed_failures(
    records: Iterable[ObservationLike],
    *,
    max_clusters: int = 25,
    sample_ids_per_cluster: int = 5,
) -> FailureClusteringReport:
    """Return bounded recurring-failure clusters from collector-confirmed evidence.

    ``CORRECTED`` and ``REJECTED`` observations are treated as confirmed failure
    evidence. ``ACCEPTED`` observations remain useful to aggregate evaluation but
    are not failure evidence; ``DEFERRED`` observations are intentionally excluded
    because no collector-confirmed correction/rejection exists yet.

    Clusters are emitted for:
    - mismatched fields on corrected observations,
    - feedback category,
    - recognition engine and version,
    - recognition method.

    Results are deterministic: clusters sort by descending count, then dimension,
    then key. Observation-id samples sort lexically and are capped. Report size is
    capped by ``max_clusters`` so downstream diagnostic agents cannot receive an
    unbounded evidence payload.

    Optional evidence partitions are read from
    ``evidence_snapshot['evaluation_partition']``. Recognized values are
    DEVELOPMENT, VALIDATION, and GOLDEN (with a few explicit aliases); absent or
    unknown values are counted as UNSPECIFIED. No source schema migration occurs.
    """

    if max_clusters < 0:
        raise ValueError("max_clusters must be >= 0")
    if sample_ids_per_cluster < 0:
        raise ValueError("sample_ids_per_cluster must be >= 0")

    rows = tuple(records)
    buckets: Dict[Tuple[str, str], list[str]] = {}
    partition_counts: Dict[str, int] = {}
    failure_records = 0

    for record in rows:
        partition = _partition(record)
        partition_counts[partition] = partition_counts.get(partition, 0) + 1

        outcome = _enumish_value(record.outcome)
        if outcome not in FAILURE_OUTCOMES:
            continue

        failure_records += 1
        observation_id = record.observation_id
        category = _enumish_value(record.category)
        engine = f"{record.engine_name}@{record.engine_version}"
        method = record.recognition_method

        _add_cluster(buckets, "category", category, observation_id)
        _add_cluster(buckets, "engine", engine, observation_id)
        _add_cluster(buckets, "method", method, observation_id)

        if outcome == "CORRECTED":
            shared_fields = sorted(
                set(record.suggested_values) & set(record.confirmed_values)
            )
            for field_name in shared_fields:
                if _normalized_value(record.suggested_values[field_name]) != _normalized_value(
                    record.confirmed_values[field_name]
                ):
                    _add_cluster(buckets, "field", field_name, observation_id)

    all_clusters = tuple(
        sorted(
            (
                FailureCluster(
                    dimension=dimension,
                    key=key,
                    count=len(observation_ids),
                    observation_ids=tuple(sorted(observation_ids)[:sample_ids_per_cluster]),
                )
                for (dimension, key), observation_ids in buckets.items()
            ),
            key=lambda item: (-item.count, item.dimension, item.key),
        )
    )
    visible_clusters = all_clusters[:max_clusters]

    return FailureClusteringReport(
        total_records=len(rows),
        failure_records=failure_records,
        clusters=visible_clusters,
        partition_counts=dict(sorted(partition_counts.items())),
        truncated_clusters=max(0, len(all_clusters) - len(visible_clusters)),
        max_clusters=max_clusters,
        sample_ids_per_cluster=sample_ids_per_cluster,
    )
