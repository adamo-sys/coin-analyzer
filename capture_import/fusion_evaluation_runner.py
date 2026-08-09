"""Headless evaluation of deterministic visual and production OCR evidence fusion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Callable, Mapping, Sequence

from inference_telemetry import InferenceTelemetryRecord
from legacy_ocr_workflow_provider import LegacyOCRWorkflowProvider
from ocr_experiment import (
    OCRExperiment,
    TESSERACT_COIN_CONFIG,
    TESSERACT_COIN_PREPROCESSING,
)

from .desktop_ocr_review_composition import create_desktop_ocr_review_composition
from .desktop_ocr_review_handoff import create_desktop_ocr_review_handoff
from .evidence_fusion import (
    REQUIRED_FUSION_FIELDS,
    FusionFieldStatus,
    comparable_identity_value,
    fuse_identity_evidence,
)
from .standalone_image_intake import create_temporary_capture_package
from .visual_evaluation_harness import VisualBenchmarkManifest
from .workflow_execution import ImportWorkflow
from .workflow_models import ImportConfiguration, ImportRequest


REPORT_SCHEMA = "coin-analyzer-visual-ocr-fusion-experiment"
EXPECTED_VISUAL_SCHEMA = "coin-analyzer-terra-v2-prospective-experiment"
EXPECTED_TERRA_REPORT_SHA256 = (
    "0d9e55524e1ec988236a63df3ba062646d71a7434a6e85ea0d7267e11c27b943"
)
EXPECTED_TERRA_CONFIGURATION_SHA256 = (
    "e12964f62e61b507f102c98be421d4207ddcc84a75cd94d0ac0d44540e6b62b9"
)
EXPECTED_BENCHMARK_MANIFEST_SHA256 = (
    "94ebc1a596d9ab147132cc5b6e89d81054725737edf399a87c7b881b0d8a8c68"
)
EXPECTED_TERRA_PASS_METRICS = {
    "country_accuracy": 0.75,
    "denomination_accuracy": 0.85,
    "year_accuracy": 0.65,
    "full_required_identity_accuracy": 0.50,
}
FUSION_RETENTION_THRESHOLDS = {
    "country_accuracy": 0.75,
    "denomination_accuracy": 0.85,
    "year_accuracy": 0.65,
    "full_required_identity_accuracy": 0.50,
    "maximum_silent_incorrect_resolutions": 0,
    "maximum_infrastructure_failures": 0,
    "maximum_mean_fusion_latency_seconds": 0.050,
}


class FusionEvaluationError(ValueError):
    """The archived input or evaluator contract is invalid."""


@dataclass(slots=True)
class MemoryTelemetrySink:
    records: list[InferenceTelemetryRecord]

    def __init__(self) -> None:
        self.records = []

    def write(self, record: InferenceTelemetryRecord) -> None:
        self.records.append(record)


def load_archived_visual_report(
    path: str | Path,
    manifest: VisualBenchmarkManifest,
    *,
    expected_sha256: str = EXPECTED_TERRA_REPORT_SHA256,
) -> dict[str, object]:
    report_path = Path(path)
    try:
        raw = report_path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FusionEvaluationError(f"cannot read archived visual report: {error}") from error
    actual_sha256 = _portable_text_sha256(raw)
    if actual_sha256 != expected_sha256:
        raise FusionEvaluationError(
            "archived visual report SHA-256 does not match the frozen Terra artifact"
        )
    if not isinstance(payload, dict) or payload.get("schema") != EXPECTED_VISUAL_SCHEMA:
        raise FusionEvaluationError("archived visual report schema is not prospective Terra")
    if payload.get("benchmark_version") != manifest.version:
        raise FusionEvaluationError("visual report and benchmark versions differ")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise FusionEvaluationError("archived visual report cases must be a list")
    expected_ids = [case.case_id for case in manifest.cases]
    actual_ids = [row.get("case_id") for row in cases if isinstance(row, Mapping)]
    if actual_ids != expected_ids:
        raise FusionEvaluationError("archived visual report case inventory/order changed")
    failures = payload.get("canonical_metrics", {}).get("infrastructure_failures")
    if failures != 0:
        raise FusionEvaluationError("archived visual report must have zero failures")
    provider = payload.get("provider")
    if not isinstance(provider, Mapping) or provider.get("model_id") != "gpt-5.6-terra":
        raise FusionEvaluationError("archived visual report is not GPT-5.6 Terra")
    configuration = provider.get("configuration")
    if not isinstance(configuration, Mapping) or _mapping_sha256(configuration) != EXPECTED_TERRA_CONFIGURATION_SHA256:
        raise FusionEvaluationError("archived Terra configuration fingerprint changed")
    canonical = payload.get("canonical_metrics")
    if not isinstance(canonical, Mapping) or any(
        canonical.get(name) != expected
        for name, expected in EXPECTED_TERRA_PASS_METRICS.items()
    ):
        raise FusionEvaluationError("archived Terra PASS metrics changed")
    if payload.get("experiment_passes") is not True:
        raise FusionEvaluationError("archived Terra PASS verdict changed")
    manifest_path = manifest.root / "manifest.json"
    try:
        manifest_sha256 = _portable_text_sha256(manifest_path.read_bytes())
    except OSError as error:
        raise FusionEvaluationError(f"cannot hash Benchmark v2 manifest: {error}") from error
    if manifest_sha256 != EXPECTED_BENCHMARK_MANIFEST_SHA256:
        raise FusionEvaluationError("Benchmark v2.0 manifest SHA-256 changed")
    return payload


def run_fusion_benchmark(
    manifest: VisualBenchmarkManifest,
    archived_visual_report: Mapping[str, object],
    *,
    clock: Callable[[], float] = perf_counter,
    composition_factory: Callable[[MemoryTelemetrySink], object] | None = None,
    terra_report_sha256: str = EXPECTED_TERRA_REPORT_SHA256,
) -> dict[str, object]:
    visual_rows = archived_visual_report["cases"]
    assert isinstance(visual_rows, list)
    visual_by_id = {str(row["case_id"]): row for row in visual_rows}
    sink = MemoryTelemetrySink()
    composition = (
        composition_factory(sink)
        if composition_factory is not None
        else _production_ocr_composition(sink)
    )
    rows = [
        _run_case(case, visual_by_id[case.case_id], composition, sink, clock)
        for case in manifest.cases
    ]
    visual_metrics = dict(archived_visual_report["canonical_metrics"])
    ocr_metrics = score_evidence_rows(rows, view="ocr")
    fused_metrics = score_evidence_rows(rows, view="fused")
    safety = analyze_safety(rows)
    latencies = {
        "terra_provider": dict(archived_visual_report["exact_metrics"]["latency"]),
        "tesseract_provider": aggregate_latencies(
            row["latency"]["tesseract_provider_seconds"] for row in rows
        ),
        "ocr_workflow": aggregate_latencies(
            row["latency"]["ocr_workflow_seconds"] for row in rows
        ),
        "fusion": aggregate_latencies(
            row["latency"]["fusion_seconds"] for row in rows
        ),
        "total_machine_analysis": aggregate_latencies(
            row["latency"]["total_machine_analysis_seconds"] for row in rows
        ),
    }
    infrastructure_failures = sum(row["infrastructure_failure"] is not None for row in rows)
    retention = fusion_retention_results(
        fused_metrics,
        safety,
        latencies["fusion"],
        infrastructure_failures=infrastructure_failures,
    )
    return {
        "schema": REPORT_SCHEMA,
        "benchmark_version": manifest.version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "terra_report_sha256": terra_report_sha256,
            "terra_configuration_sha256": EXPECTED_TERRA_CONFIGURATION_SHA256,
            "benchmark_manifest_sha256": EXPECTED_BENCHMARK_MANIFEST_SHA256,
            "terra_pass_metrics_required_by_fusion": dict(
                EXPECTED_TERRA_PASS_METRICS
            ),
            "visual_report_schema": archived_visual_report["schema"],
            "visual_report_generated_at": archived_visual_report["generated_at"],
            "visual_provider": archived_visual_report["provider"],
            "visual_usage_and_cost": archived_visual_report["usage"],
            "ocr_provider": "legacy-ocr / pytesseract",
            "ocr_configuration": TESSERACT_COIN_CONFIG,
            "ocr_preprocessing": TESSERACT_COIN_PREPROCESSING,
        },
        "execution_provenance": fusion_execution_provenance(),
        "timing_boundaries": {
            "terra_provider": archived_visual_report["timing_boundary"],
            "tesseract_provider": "sum of two production pytesseract calls",
            "ocr_workflow": "temporary package creation through OCR handoff decoding",
            "fusion": "fuse_identity_evidence only",
            "total_machine_analysis": "archived Terra provider + current OCR workflow + fusion",
        },
        "visual_only_metrics": visual_metrics,
        "ocr_only_metrics": ocr_metrics,
        "fused_metrics": fused_metrics,
        "safety_analysis": safety,
        "latency": latencies,
        "infrastructure_failures": infrastructure_failures,
        "retention_thresholds": dict(FUSION_RETENTION_THRESHOLDS),
        "retention": retention,
        "experiment_passes": all(retention.values()),
        "cases": rows,
    }


def _production_ocr_composition(sink: MemoryTelemetrySink):
    provider = LegacyOCRWorkflowProvider(experiment=OCRExperiment(telemetry_sink=sink))
    return create_desktop_ocr_review_composition(provider=provider)


def _run_case(case, visual_row, composition, sink, clock):
    source = None
    started = clock()
    before = len(sink.records)
    failure = None
    observations: list[dict[str, object]] = []
    candidates: list[dict[str, object]] = []
    conflicts: list[dict[str, object]] = []
    provider_available = False
    try:
        source = create_temporary_capture_package(
            front_path=case.obverse.path,
            reverse_path=case.reverse.path,
        )
        with TemporaryDirectory(prefix="coin-analyzer-fusion-") as temporary:
            workspace = Path(temporary) / "workspace"
            workspace.mkdir()
            outcome = ImportWorkflow(composition.pipeline).execute(
                ImportRequest(
                    source=source.path,
                    collection_id=f"fusion-{case.case_id}",
                    configuration=ImportConfiguration(),
                ),
                workspace.resolve(),
            )
            handoff = create_desktop_ocr_review_handoff(
                composition=composition,
                outcome=outcome,
            )
            observations = [item.to_dict() for item in handoff.report.observations]
            candidates = [item.to_dict() for item in handoff.report.candidates]
            conflicts = [item.to_dict() for item in handoff.report.conflicts]
            provider_available = handoff.report.provider_available
    except Exception as error:  # infrastructure is reported, never converted to abstention
        failure = {"type": type(error).__name__, "message": str(error)}
    finally:
        ocr_workflow_seconds = max(0.0, clock() - started)
        if source is not None:
            source.release()

    tesseract_records = sink.records[before:]
    tesseract_seconds = sum(record.duration_ms for record in tesseract_records) / 1000.0
    failed_tesseract_records = [record for record in tesseract_records if not record.success]
    if failure is None and failed_tesseract_records:
        failure = {
            "type": "OCRRuntimeUnavailable",
            "message": ", ".join(
                sorted({record.error_type or "TesseractFailure" for record in failed_tesseract_records})
            ),
        }
    fusion_started = clock()
    fused = fuse_identity_evidence(
        visual_candidates=visual_row.get("ranked_candidates", []),
        ocr_candidates=candidates,
        ocr_conflicts=conflicts,
    )
    fusion_seconds = max(0.0, clock() - fusion_started)
    ocr_only = fuse_identity_evidence(
        visual_candidates=[],
        ocr_candidates=candidates,
        ocr_conflicts=conflicts,
    )
    terra_seconds = float(visual_row["latency_seconds"])
    row = {
        "case_id": case.case_id,
        "expected": dict(case.expected),
        "visual": {
            "ranked_candidates": visual_row.get("ranked_candidates", []),
            "top_1": (visual_row.get("ranked_candidates") or [None])[0],
            "raw_structured_provider_result": visual_row.get("raw_structured_provider_result"),
            "canonical_scores": visual_row.get("canonical_scores"),
        },
        "ocr": {
            "provider_available": provider_available,
            "observations": observations,
            "candidates": candidates,
            "conflicts": conflicts,
            "telemetry": [record.to_dict() for record in tesseract_records],
            "identity": ocr_only.to_dict(),
        },
        "fused": fused.to_dict(),
        "infrastructure_failure": failure,
        "latency": {
            "terra_provider_seconds": terra_seconds,
            "tesseract_provider_seconds": tesseract_seconds,
            "ocr_workflow_seconds": ocr_workflow_seconds,
            "fusion_seconds": fusion_seconds,
            "total_machine_analysis_seconds": terra_seconds + ocr_workflow_seconds + fusion_seconds,
        },
    }
    _attach_field_scores(row, case.expected, visual_row)
    return row


def _attach_field_scores(row, expected, visual_row):
    visual_top = (visual_row.get("ranked_candidates") or [{}])[0]
    visual_keys = _identity_keys(visual_top)
    expected_keys = _identity_keys(expected)
    ocr_fields = {item["field_name"]: item for item in row["ocr"]["identity"]["fields"]}
    fused_fields = {item["field_name"]: item for item in row["fused"]["fields"]}
    row["field_scores"] = {
        "visual": {field: visual_keys[field] == expected_keys[field] for field in REQUIRED_FUSION_FIELDS},
        "ocr": {field: ocr_fields[field]["selected_comparable_value"] == expected_keys[field] for field in REQUIRED_FUSION_FIELDS},
        "fused": {field: fused_fields[field]["selected_comparable_value"] == expected_keys[field] for field in REQUIRED_FUSION_FIELDS},
    }
    for view in ("visual", "ocr", "fused"):
        row["field_scores"][view]["full_required_identity"] = all(
            row["field_scores"][view][field] for field in REQUIRED_FUSION_FIELDS
        )


def _identity_keys(identity: Mapping[str, object]) -> dict[str, str | None]:
    return {
        field: comparable_identity_value(field, identity.get(field), country_raw=identity.get("country"))[0]
        for field in REQUIRED_FUSION_FIELDS
    }


def score_evidence_rows(rows: Sequence[Mapping[str, object]], *, view: str) -> dict[str, object]:
    correct = {field: 0 for field in REQUIRED_FUSION_FIELDS}
    full = unresolved = conflict = correction = usable = 0
    for row in rows:
        scores = row["field_scores"][view]
        for field in REQUIRED_FUSION_FIELDS:
            correct[field] += bool(scores[field])
        full += bool(scores["full_required_identity"])
        identity = row["ocr"]["identity"] if view == "ocr" else row["fused"]
        fields = identity["fields"]
        usable += sum(item["selected_comparable_value"] is not None for item in fields)
        unresolved += any(item["selected_comparable_value"] is None for item in fields)
        conflict += any(item["status"] == FusionFieldStatus.CONFLICT.value for item in fields)
        correction += (
            not scores["full_required_identity"]
            or any(item["status"] in {FusionFieldStatus.OCR_ONLY.value, FusionFieldStatus.CONFLICT.value, FusionFieldStatus.UNRESOLVED.value} for item in fields)
        )
    total = len(rows)
    return {
        "total_cases": total,
        "country_accuracy": _rate(correct["country"], total),
        "denomination_accuracy": _rate(correct["denomination"], total),
        "year_accuracy": _rate(correct["year"], total),
        "full_required_identity_accuracy": _rate(full, total),
        "usable_required_field_evidence_rate": _rate(usable, total * len(REQUIRED_FUSION_FIELDS)),
        "unresolved_rate": _rate(unresolved, total),
        "conflict_rate": _rate(conflict, total),
        "correction_required_rate": _rate(correction, total),
    }


def analyze_safety(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    improved: set[str] = set()
    degraded: set[str] = set()
    unchanged: set[str] = set()
    no_value: set[str] = set()
    corrected = challenged = correct_visual_contradicted = silent = 0
    unmarked_disagreements = 0
    conflict_fields = 0
    conflict_cases: list[dict[str, object]] = []
    for row in rows:
        case_id = str(row["case_id"])
        visual_scores = row["field_scores"]["visual"]
        fused_scores = row["field_scores"]["fused"]
        expected_keys = _identity_keys(row["expected"])
        case_conflicts = []
        usable_ocr = False
        for field in row["fused"]["fields"]:
            name = field["field_name"]
            ocr_keys = {item["comparable_value"] for item in field["ocr_values"]}
            usable_ocr = usable_ocr or bool(ocr_keys)
            if not visual_scores[name] and expected_keys[name] in ocr_keys:
                if field["status"] == FusionFieldStatus.OCR_ONLY.value and fused_scores[name]:
                    corrected += 1
                elif field["status"] == FusionFieldStatus.CONFLICT.value:
                    challenged += 1
            if visual_scores[name] and any(key != expected_keys[name] for key in ocr_keys):
                correct_visual_contradicted += 1
            if field["status"] == FusionFieldStatus.CONFLICT.value:
                conflict_fields += 1
                case_conflicts.append(name)
            visual_values = [item for item in field["visual_values"] if item.get("rank") == 1]
            if visual_values and ocr_keys and visual_values[0]["comparable_value"] not in ocr_keys:
                unmarked_disagreements += field["status"] != FusionFieldStatus.CONFLICT.value
            if (
                fused_scores[name] is False
                and field["selected_comparable_value"] is not None
                and not visual_values
            ):
                silent += 1
        if case_conflicts:
            conflict_cases.append({"case_id": case_id, "fields": case_conflicts})
        if not usable_ocr:
            no_value.add(case_id)
        if sum(fused_scores[field] for field in REQUIRED_FUSION_FIELDS) > sum(visual_scores[field] for field in REQUIRED_FUSION_FIELDS):
            improved.add(case_id)
        elif sum(fused_scores[field] for field in REQUIRED_FUSION_FIELDS) < sum(visual_scores[field] for field in REQUIRED_FUSION_FIELDS):
            degraded.add(case_id)
        else:
            unchanged.add(case_id)
    return {
        "visual_errors_corrected_by_ocr_fields": corrected,
        "visual_errors_safely_challenged_by_ocr_fields": challenged,
        "correct_visual_fields_contradicted_by_incorrect_ocr": correct_visual_contradicted,
        "conflict_fields_preventing_silent_acceptance": conflict_fields,
        "new_silent_incorrect_resolutions": silent,
        "unmarked_visual_ocr_disagreements": unmarked_disagreements,
        "cases_improved": sorted(improved),
        "cases_degraded_to_explicit_review": sorted(degraded),
        "cases_unchanged": sorted(unchanged),
        "cases_where_ocr_added_no_required_field_evidence": sorted(no_value),
        "conflicts": conflict_cases,
    }


def fusion_retention_results(metrics, safety, latency, *, infrastructure_failures):
    return {
        "country_accuracy": metrics["country_accuracy"] >= 0.75,
        "denomination_accuracy": metrics["denomination_accuracy"] >= 0.85,
        "year_accuracy": metrics["year_accuracy"] >= 0.65,
        "full_required_identity_accuracy": metrics["full_required_identity_accuracy"] >= 0.50,
        "zero_silent_incorrect_resolutions": safety["new_silent_incorrect_resolutions"] == 0,
        "all_disagreements_explicit": safety["unmarked_visual_ocr_disagreements"] == 0,
        "zero_infrastructure_failures": infrastructure_failures == 0,
        "mean_fusion_latency": latency["mean_seconds"] is not None and latency["mean_seconds"] <= 0.050,
    }


def aggregate_latencies(values: Sequence[float]) -> dict[str, float | None]:
    data = [float(value) for value in values]
    if not data:
        return {"mean_seconds": None, "median_seconds": None, "p95_seconds": None}
    ordered = sorted(data)
    return {
        "mean_seconds": statistics.fmean(ordered),
        "median_seconds": statistics.median(ordered),
        "p95_seconds": ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)],
    }


def fusion_execution_provenance() -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    relative_files = (
        "capture_import/canonical_identity.py",
        "capture_import/evidence_fusion.py",
        "capture_import/fusion_evaluation_runner.py",
        "capture_import/visual_evaluation_harness.py",
        "capture_import/desktop_ocr_review_composition.py",
        "legacy_ocr_workflow_provider.py",
        "ocr_experiment.py",
    )
    digest = hashlib.sha256()
    for relative in relative_files:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update((root / relative).read_bytes())
        digest.update(b"\0")
    pytesseract_version = native_tesseract_version = None
    try:
        import pytesseract

        pytesseract_version = getattr(pytesseract, "__version__", None)
        native_tesseract_version = str(
            pytesseract.get_tesseract_version()
        ).splitlines()[0]
    except Exception:
        pass
    return {
        "implementation_sha256": digest.hexdigest(),
        "implementation_files": list(relative_files),
        "git_commit": _git_value("rev-parse", "HEAD"),
        "git_worktree_dirty": bool(_git_value("status", "--porcelain")),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "pytesseract": pytesseract_version,
        "native_tesseract": native_tesseract_version,
    }


def _mapping_sha256(value: Mapping[str, object]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _portable_text_sha256(value: bytes) -> str:
    """Hash exact UTF-8 text while treating CRLF and LF checkouts equally."""

    return hashlib.sha256(value.replace(b"\r\n", b"\n")).hexdigest()


def _git_value(*arguments: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=Path(__file__).resolve().parents[1],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip()


def render_fusion_summary(report: Mapping[str, object]) -> str:
    visual = report["visual_only_metrics"]
    ocr = report["ocr_only_metrics"]
    fused = report["fused_metrics"]
    safety = report["safety_analysis"]
    latency = report["latency"]
    lines = [
        f"Visual + OCR fusion benchmark: {report['benchmark_version']}",
        f"Cases: {fused['total_cases']}",
        f"Infrastructure failures: {report['infrastructure_failures']}",
        f"Visual canonical country/denomination/year/full: {_pct(visual['country_accuracy'])} / {_pct(visual['denomination_accuracy'])} / {_pct(visual['year_accuracy'])} / {_pct(visual['full_required_identity_accuracy'])}",
        f"OCR country/denomination/year/full: {_pct(ocr['country_accuracy'])} / {_pct(ocr['denomination_accuracy'])} / {_pct(ocr['year_accuracy'])} / {_pct(ocr['full_required_identity_accuracy'])}",
        f"Fused country/denomination/year/full: {_pct(fused['country_accuracy'])} / {_pct(fused['denomination_accuracy'])} / {_pct(fused['year_accuracy'])} / {_pct(fused['full_required_identity_accuracy'])}",
        f"Fused unresolved/conflict/correction required: {_pct(fused['unresolved_rate'])} / {_pct(fused['conflict_rate'])} / {_pct(fused['correction_required_rate'])}",
        f"Silent incorrect resolutions: {safety['new_silent_incorrect_resolutions']}",
        f"Mean Tesseract/fusion/total latency: {latency['tesseract_provider']['mean_seconds']:.6f}s / {latency['fusion']['mean_seconds']:.6f}s / {latency['total_machine_analysis']['mean_seconds']:.6f}s",
        f"Disposition: {'PASS' if report['experiment_passes'] else 'FAIL'}",
        "",
    ]
    return "\n".join(lines)


def write_fusion_report(report, *, json_path: str | Path, summary_path: str | Path) -> None:
    json_target = Path(json_path)
    summary_target = Path(summary_path)
    json_target.parent.mkdir(parents=True, exist_ok=True)
    summary_target.parent.mkdir(parents=True, exist_ok=True)
    json_target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_target.write_text(render_fusion_summary(report), encoding="utf-8")


def _rate(value: int, total: int) -> float | None:
    return None if total == 0 else value / total


def _pct(value: object) -> str:
    return "n/a" if value is None else f"{float(value) * 100:.1f}%"
