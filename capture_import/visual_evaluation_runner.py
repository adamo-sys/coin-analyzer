"""Headless prospective Terra evaluation with exact and canonical score views."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
from time import perf_counter
from typing import Callable, Mapping

from inference_pricing import (
    MODEL_PRICING_USD_PER_MILLION,
    estimate_inference_cost_usd,
)

from .canonical_identity import (
    CanonicalizedField,
    canonicalize_denomination,
    canonicalize_jurisdiction,
)
from .visual_evaluation_harness import (
    OPTIONAL_IDENTITY_FIELDS,
    REQUIRED_IDENTITY_FIELDS,
    VisualBenchmarkManifest,
    load_visual_manifest,
    score_selective_safety,
    score_visual_results,
)
from .visual_identity_provider import (
    VisualIdentityImage,
    VisualIdentityProvider,
    VisualIdentityRequest,
)


REPORT_SCHEMA = "coin-analyzer-terra-v2-prospective-experiment"
TIMING_BOUNDARY = (
    "provider.identify(request), including API call, structured-output "
    "validation, and telemetry write"
)
RETENTION_THRESHOLDS = {
    "canonical_country_accuracy": 0.75,
    "canonical_denomination_accuracy": 0.70,
    "canonical_full_required_identity_accuracy": 0.50,
    "maximum_abstention_rate": 0.50,
    "maximum_mean_latency_seconds": 5.0,
    "maximum_infrastructure_failures": 0,
}


def run_visual_benchmark(
    manifest: VisualBenchmarkManifest,
    provider: VisualIdentityProvider,
    *,
    clock: Callable[[], float] = perf_counter,
    git_commit: str | None = None,
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for case in manifest.cases:
        request = VisualIdentityRequest(
            scan_id=f"visual-v2-prospective-{case.case_id}",
            images=(
                VisualIdentityImage(
                    "obverse",
                    _media_type(case.obverse.path),
                    case.obverse.path.read_bytes(),
                ),
                VisualIdentityImage(
                    "reverse",
                    _media_type(case.reverse.path),
                    case.reverse.path.read_bytes(),
                ),
            ),
        )
        started = clock()
        try:
            provider_report = provider.identify(request)
        except Exception as error:
            elapsed = max(0.0, clock() - started)
            input_tokens = getattr(error, "input_tokens", None)
            output_tokens = getattr(error, "output_tokens", None)
            rows.append(
                _failure_row(
                    case,
                    error,
                    latency_seconds=elapsed,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost_usd=estimate_inference_cost_usd(
                        provider="OpenAI",
                        model=provider.model_id,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    ),
                )
            )
            continue

        elapsed = max(0.0, clock() - started)
        public_candidates = (
            provider_report.candidates
            if provider_report.outcome == "CANDIDATES"
            else ()
        )
        diagnostic_candidates = (
            provider_report.diagnostic_candidates or provider_report.candidates
        )
        predictions = [candidate.as_prediction() for candidate in public_candidates]
        ranked_diagnostics = [
            {
                "candidate_id": f"candidate-{index}",
                **_candidate_record(candidate),
            }
            for index, candidate in enumerate(diagnostic_candidates, start=1)
        ]
        row: dict[str, object] = {
            "case_id": case.case_id,
            "identity_certain": case.identity_certain,
            "expected": dict(case.expected),
            "outcome": (
                "PREDICTED"
                if provider_report.outcome == "CANDIDATES"
                else "ABSTAINED"
            ),
            "predictions": predictions,
            "ranked_candidates": [
                _candidate_record(candidate) for candidate in public_candidates
            ],
            "diagnostic_candidates": ranked_diagnostics,
            "best_candidate_id": (
                ranked_diagnostics[0]["candidate_id"]
                if ranked_diagnostics
                else None
            ),
            "raw_structured_provider_result": dict(
                provider_report.raw_structured_result
            ),
            "provider_failure": None,
            "latency_seconds": elapsed,
            "input_tokens": provider_report.input_tokens,
            "output_tokens": provider_report.output_tokens,
            "estimated_cost_usd": estimate_inference_cost_usd(
                provider="OpenAI",
                model=provider_report.model_id,
                input_tokens=provider_report.input_tokens,
                output_tokens=provider_report.output_tokens,
            ),
        }
        _attach_score_views(row)
        rows.append(row)

    exact_metrics = score_visual_results(rows, top_k=3)
    canonical_metrics = score_canonical_results(rows, top_k=3)
    total_input = sum(
        row["input_tokens"]
        for row in rows
        if isinstance(row.get("input_tokens"), int)
    )
    total_output = sum(
        row["output_tokens"]
        for row in rows
        if isinstance(row.get("output_tokens"), int)
    )
    configuration = getattr(provider, "configuration", {})
    report: dict[str, object] = {
        "schema": REPORT_SCHEMA,
        "benchmark_version": manifest.version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit or _git_commit(),
        "execution_provenance": execution_provenance(),
        "timing_boundary": TIMING_BOUNDARY,
        "provider": {
            "provider_id": provider.provider_id,
            "model_id": provider.model_id,
            "configuration": (
                dict(configuration) if isinstance(configuration, Mapping) else {}
            ),
        },
        "retention_thresholds": dict(RETENTION_THRESHOLDS),
        "exact_metrics": exact_metrics,
        "canonical_metrics": canonical_metrics,
        "usage": {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_estimated_cost_usd": exact_metrics["estimated_cost_usd"]["total"],
            "mean_estimated_cost_usd": exact_metrics["estimated_cost_usd"][
                "mean_per_case"
            ],
        },
        "pricing": _pricing_provenance(provider.model_id),
        "retention": retention_results(exact_metrics, canonical_metrics),
        "cases": rows,
    }
    report["experiment_passes"] = all(report["retention"].values())
    return report


def _failure_row(
    case: object,
    error: Exception,
    *,
    latency_seconds: float,
    input_tokens: object,
    output_tokens: object,
    estimated_cost_usd: float | None,
) -> dict[str, object]:
    return {
        "case_id": case.case_id,
        "identity_certain": case.identity_certain,
        "expected": dict(case.expected),
        "outcome": "INFRASTRUCTURE_FAILURE",
        "predictions": [],
        "diagnostic_candidates": [],
        "best_candidate_id": None,
        "canonicalized_expected": _canonicalized_identity(case.expected),
        "canonicalized_predictions": [],
        "exact_scores": None,
        "canonical_scores": None,
        "type_design_label_result": "NOT_SCORED",
        "required_identity_correct_but_type_design_label_differs": False,
        "raw_structured_provider_result": getattr(
            error, "raw_provider_output", None
        ),
        "provider_failure": error.__class__.__name__,
        "latency_seconds": latency_seconds,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": estimated_cost_usd,
    }


def _attach_score_views(row: dict[str, object]) -> None:
    expected = row["expected"]
    predictions = row["predictions"]
    row["canonicalized_expected"] = _canonicalized_identity(expected)
    row["canonicalized_predictions"] = [
        _canonicalized_identity(prediction) for prediction in predictions
    ]
    if row["outcome"] != "PREDICTED":
        row["exact_scores"] = None
        row["canonical_scores"] = None
        row["type_design_label_result"] = "NOT_SCORED"
        row["required_identity_correct_but_type_design_label_differs"] = False
        return
    first = predictions[0]
    exact_scores = {
        field: _exact_field_match(first, expected, field)
        for field in (*REQUIRED_IDENTITY_FIELDS, *OPTIONAL_IDENTITY_FIELDS)
        if field in expected
    }
    exact_scores["full_required_identity"] = all(
        exact_scores[field] for field in REQUIRED_IDENTITY_FIELDS
    )
    canonical_scores = {
        field: _canonical_field_match(first, expected, field)
        for field in REQUIRED_IDENTITY_FIELDS
    }
    canonical_scores["type_design"] = exact_scores.get("type_design")
    canonical_scores["full_required_identity"] = all(
        canonical_scores[field] for field in REQUIRED_IDENTITY_FIELDS
    )
    type_result = _type_design_label_result(first, expected)
    row["exact_scores"] = exact_scores
    row["canonical_scores"] = canonical_scores
    row["type_design_label_result"] = type_result
    row["required_identity_correct_but_type_design_label_differs"] = bool(
        canonical_scores["full_required_identity"] and type_result == "LABEL_DIFFERS"
    )


def score_canonical_results(
    rows: list[Mapping[str, object]],
    *,
    top_k: int,
) -> dict[str, object]:
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top_k must be a positive integer.")
    outcomes = Counter()
    correct = Counter()
    eligible = Counter()
    rules = Counter()
    diagnostic_cases: list[str] = []
    latencies: list[float] = []
    for row in rows:
        outcome = str(row.get("outcome"))
        outcomes[outcome] += 1
        latency = row.get("latency_seconds")
        if (
            isinstance(latency, (int, float))
            and not isinstance(latency, bool)
            and math.isfinite(latency)
            and latency >= 0
        ):
            latencies.append(float(latency))
        if row.get("identity_certain") is not True or outcome == "INFRASTRUCTURE_FAILURE":
            continue
        expected = row.get("expected")
        if not isinstance(expected, Mapping):
            raise ValueError("evaluated certain results require expected values.")
        for field in REQUIRED_IDENTITY_FIELDS:
            eligible[field] += 1
        eligible["full_required_identity"] += 1
        eligible["top_k_identity"] += 1
        if "type_design" in expected:
            eligible["type_design"] += 1
        if outcome != "PREDICTED":
            continue
        predictions = row.get("predictions")
        if not isinstance(predictions, list) or not predictions:
            raise ValueError("predicted results require predictions.")
        first = predictions[0]
        if not isinstance(first, Mapping):
            raise ValueError("predictions must contain objects.")
        for field in REQUIRED_IDENTITY_FIELDS:
            correct[field] += _canonical_field_match(first, expected, field)
        required_match = all(
            _canonical_field_match(first, expected, field)
            for field in REQUIRED_IDENTITY_FIELDS
        )
        correct["full_required_identity"] += required_match
        if "type_design" in expected:
            correct["type_design"] += _exact_field_match(
                first, expected, "type_design"
            )
        if row.get("required_identity_correct_but_type_design_label_differs") is True:
            diagnostic_cases.append(str(row.get("case_id")))
        correct["top_k_identity"] += any(
            all(
                _canonical_field_match(candidate, expected, field)
                for field in REQUIRED_IDENTITY_FIELDS
            )
            and (
                "type_design" not in expected
                or _exact_field_match(candidate, expected, "type_design")
            )
            for candidate in predictions[:top_k]
            if isinstance(candidate, Mapping)
        )
        for canonical in row.get("canonicalized_predictions", []):
            if not isinstance(canonical, Mapping):
                continue
            for field in ("country", "denomination"):
                value = canonical.get(field)
                if isinstance(value, Mapping):
                    for rule in value.get("normalization_rules", []):
                        rules[str(rule)] += 1
    safety = score_selective_safety(rows, field_matcher=_canonical_field_match)
    return {
        "total_cases": len(rows),
        "predicted_cases": outcomes["PREDICTED"],
        "abstained_cases": outcomes["ABSTAINED"],
        "infrastructure_failures": outcomes["INFRASTRUCTURE_FAILURE"],
        "country_accuracy": _rate(correct["country"], eligible["country"]),
        "denomination_accuracy": _rate(
            correct["denomination"], eligible["denomination"]
        ),
        "year_accuracy": _rate(correct["year"], eligible["year"]),
        "type_design_accuracy": _rate(
            correct["type_design"], eligible["type_design"]
        ),
        "full_required_identity_accuracy": _rate(
            correct["full_required_identity"], eligible["full_required_identity"]
        ),
        "top_k": top_k,
        "top_k_identity_recall": _rate(
            correct["top_k_identity"], eligible["top_k_identity"]
        ),
        "abstention_rate": _rate(outcomes["ABSTAINED"], len(rows)),
        "infrastructure_failure_rate": _rate(
            outcomes["INFRASTRUCTURE_FAILURE"], len(rows)
        ),
        "required_identity_correct_but_type_design_label_differs": {
            "count": len(diagnostic_cases),
            "case_ids": diagnostic_cases,
        },
        "canonicalization_rules_exercised": dict(sorted(rules.items())),
        "latency": _latencies(latencies),
        **safety,
    }


def retention_results(
    exact_metrics: Mapping[str, object],
    canonical_metrics: Mapping[str, object],
) -> dict[str, bool]:
    latency = exact_metrics.get("latency")
    mean_latency = latency.get("mean_seconds") if isinstance(latency, Mapping) else None
    return {
        "canonical_country_accuracy": _at_least(
            canonical_metrics.get("country_accuracy"), 0.75
        ),
        "canonical_denomination_accuracy": _at_least(
            canonical_metrics.get("denomination_accuracy"), 0.70
        ),
        "canonical_full_required_identity_accuracy": _at_least(
            canonical_metrics.get("full_required_identity_accuracy"), 0.50
        ),
        "infrastructure_failures": exact_metrics.get("infrastructure_failures") == 0,
        "abstention_rate": _at_most(exact_metrics.get("abstention_rate"), 0.50),
        "mean_latency_seconds": _at_most(mean_latency, 5.0),
    }


def _canonicalized_identity(identity: Mapping[str, object]) -> dict[str, object]:
    country = canonicalize_jurisdiction(_optional_text(identity.get("country")))
    jurisdiction_id = (
        country.canonical_value.canonical_id if country.is_mapped else None
    )
    denomination = canonicalize_denomination(
        _optional_text(identity.get("denomination")),
        jurisdiction_id=jurisdiction_id,
    )
    return {
        "country": country.to_dict(),
        "denomination": denomination.to_dict(),
        "year_raw": _optional_text(identity.get("year")),
        "type_design_raw": _optional_text(identity.get("type_design")),
    }


def _canonical_field_match(
    prediction: Mapping[str, object],
    expected: Mapping[str, object],
    field: str,
) -> bool:
    if _exact_field_match(prediction, expected, field):
        return True
    if field == "country":
        predicted = canonicalize_jurisdiction(_optional_text(prediction.get(field)))
        reference = canonicalize_jurisdiction(_optional_text(expected.get(field)))
        return _mapped_equal(predicted, reference)
    if field == "denomination":
        predicted_country = canonicalize_jurisdiction(
            _optional_text(prediction.get("country"))
        )
        expected_country = canonicalize_jurisdiction(
            _optional_text(expected.get("country"))
        )
        predicted = canonicalize_denomination(
            _optional_text(prediction.get(field)),
            jurisdiction_id=(
                predicted_country.canonical_value.canonical_id
                if predicted_country.is_mapped
                else None
            ),
        )
        reference = canonicalize_denomination(
            _optional_text(expected.get(field)),
            jurisdiction_id=(
                expected_country.canonical_value.canonical_id
                if expected_country.is_mapped
                else None
            ),
        )
        return _mapped_equal(predicted, reference)
    return False


def _mapped_equal(left: CanonicalizedField, right: CanonicalizedField) -> bool:
    return bool(
        left.is_mapped
        and right.is_mapped
        and left.canonical_value == right.canonical_value
    )


def _exact_field_match(
    prediction: Mapping[str, object],
    expected: Mapping[str, object],
    field: str,
) -> bool:
    return field in prediction and field in expected and _normalized(
        prediction[field]
    ) == _normalized(expected[field])


def _type_design_label_result(
    prediction: Mapping[str, object], expected: Mapping[str, object]
) -> str:
    if "type_design" not in expected:
        return "NOT_APPLICABLE"
    if not _optional_text(prediction.get("type_design")):
        return "MISSING"
    return (
        "LABEL_MATCH"
        if _exact_field_match(prediction, expected, "type_design")
        else "LABEL_DIFFERS"
    )


def _candidate_record(candidate: object) -> dict[str, object]:
    return {
        "rank": candidate.rank,
        "country": candidate.country,
        "denomination": candidate.denomination,
        "year": candidate.year,
        "type_design": candidate.type_design,
        "source_score": candidate.source_score,
        "source_score_semantics": "uncalibrated_provider_source_score",
        "confidence": candidate.confidence,
        "observed_text": list(candidate.observed_text),
        "field_evidence": {
            field: list(observations)
            for field, observations in candidate.field_evidence
        },
        "evidence_observations": list(candidate.evidence_observations),
        "supporting_image_roles": list(candidate.supporting_image_roles),
        "provider_id": candidate.provider_id,
        "model_id": candidate.model_id,
    }


def write_visual_report(
    report: Mapping[str, object],
    *,
    json_path: str | Path,
    summary_path: str | Path,
) -> None:
    json_output = Path(json_path)
    summary_output = Path(summary_path)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    summary_output.write_text(render_visual_summary(report), encoding="utf-8")


def render_visual_summary(report: Mapping[str, object]) -> str:
    exact = report["exact_metrics"]
    canonical = report["canonical_metrics"]
    usage = report["usage"]
    retention = report["retention"]
    return "\n".join(
        [
            f"Visual benchmark: {report['benchmark_version']}",
            f"Provider: {report['provider']['provider_id']} / {report['provider']['model_id']}",
            f"Cases: {exact['total_cases']}",
            f"Infrastructure failures: {exact['infrastructure_failures']}",
            f"Exact country accuracy: {_percent(exact['country_accuracy'])}",
            f"Canonical country accuracy: {_percent(canonical['country_accuracy'])}",
            f"Exact denomination accuracy: {_percent(exact['denomination_accuracy'])}",
            f"Canonical denomination accuracy: {_percent(canonical['denomination_accuracy'])}",
            f"Exact full required identity: {_percent(exact['full_required_identity_accuracy'])}",
            f"Canonical full required identity: {_percent(canonical['full_required_identity_accuracy'])}",
            "Exact full-identity coverage: "
            + _percent(exact["field_coverage"]["full_required_identity"]),
            "Exact selective full-identity accuracy: "
            + _percent(exact["selective_accuracy"]["full_required_identity"]),
            "Exact high-source-score incomplete identities: "
            + str(exact["source_score_safety"]["high_score_incomplete"]),
            "Exact high-source-score incorrect identities: "
            + str(exact["source_score_safety"]["high_score_incorrect"]),
            "Exact high-source-score unsafe rate: "
            + _percent(exact["source_score_safety"]["high_score_unsafe_rate"]),
            "Canonical high-source-score incomplete identities: "
            + str(canonical["source_score_safety"]["high_score_incomplete"]),
            "Canonical high-source-score incorrect identities: "
            + str(canonical["source_score_safety"]["high_score_incorrect"]),
            "Canonical high-source-score unsafe rate: "
            + _percent(canonical["source_score_safety"]["high_score_unsafe_rate"]),
            f"Type/design exact-label differences: {canonical['required_identity_correct_but_type_design_label_differs']['count']}",
            f"Abstention rate: {_percent(exact['abstention_rate'])}",
            f"Mean latency: {_seconds(exact['latency']['mean_seconds'])}",
            f"Input tokens: {usage['input_tokens']}",
            f"Output tokens: {usage['output_tokens']}",
            f"Estimated cost: ${usage['total_estimated_cost_usd']:.6f}",
            f"Retention: {'PASS' if all(retention.values()) else 'FAIL'}",
            "",
        ]
    )


def load_and_run_visual_benchmark(
    manifest_path: str | Path, provider: VisualIdentityProvider
) -> dict[str, object]:
    return run_visual_benchmark(load_visual_manifest(manifest_path), provider)


def execution_provenance() -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    relative_files = (
        "capture_import/canonical_identity.py",
        "capture_import/visual_identity_provider.py",
        "capture_import/visual_evaluation_runner.py",
        "capture_import/visual_evaluation_harness.py",
        "inference_pricing.py",
        "inference_telemetry.py",
    )
    digest = hashlib.sha256()
    for relative in relative_files:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update((root / relative).read_bytes())
        digest.update(b"\0")
    try:
        import openai

        openai_version = openai.__version__
    except (ImportError, AttributeError):
        openai_version = None
    return {
        "implementation_sha256": digest.hexdigest(),
        "implementation_files": list(relative_files),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "openai_sdk": openai_version,
        "git_worktree_dirty": _git_dirty(),
    }


def _pricing_provenance(model_id: str) -> dict[str, object]:
    pricing = MODEL_PRICING_USD_PER_MILLION.get(("openai", model_id))
    return {
        "provider": "OpenAI",
        "model": model_id,
        "input_usd_per_million": (
            None if pricing is None else str(pricing.input_usd_per_million)
        ),
        "output_usd_per_million": (
            None if pricing is None else str(pricing.output_usd_per_million)
        ),
        "verified_at": "2026-08-09",
        "source": "https://developers.openai.com/api/docs/models/gpt-5.6-terra",
    }


def _media_type(path: Path) -> str:
    return "image/png" if path.suffix.casefold() == ".png" else "image/jpeg"


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _normalized(value: object) -> str:
    return " ".join(str(value).strip().casefold().split())


def _rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _latencies(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean_seconds": None, "median_seconds": None, "p95_seconds": None}
    ordered = sorted(values)
    return {
        "mean_seconds": statistics.fmean(ordered),
        "median_seconds": statistics.median(ordered),
        "p95_seconds": ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)],
    }


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def _git_dirty() -> bool | None:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return bool(result.stdout.strip())


def _at_least(value: object, threshold: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value >= threshold
    )


def _at_most(value: object, threshold: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value <= threshold
    )


def _percent(value: object) -> str:
    return "n/a" if value is None else f"{float(value) * 100:.1f}%"


def _seconds(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.3f}s"
