"""Headless, manifest-driven evaluation of the production OCR workflow."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path, PurePosixPath
import platform
import statistics
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Callable, Iterable, Mapping
from uuid import uuid4

from coin_collection import CoinCollection
from ocr_experiment import (
    TESSERACT_COIN_CONFIG,
    TESSERACT_COIN_ENGINE,
    TESSERACT_COIN_PAGE_SEGMENTATION_MODE,
    TESSERACT_COIN_PREPROCESSING,
)

from .desktop_ocr_review_composition import create_desktop_ocr_review_composition
from .desktop_ocr_review_handoff import create_desktop_ocr_review_handoff
from .evaluation_case_contract import (
    EvaluationCase,
    EvaluationInput,
    EvaluationProvenance,
    ExpectedFinding,
)
from .image_store import ManagedCollectionImageStore
from .reviewed_coin_collection_entry import ReviewedCoinDraft, persist_reviewed_coin
from .snapshot import CapturePackageSnapshotService
from .standalone_image_intake import create_temporary_capture_package
from .workflow_execution import ImportWorkflow
from .workflow_models import ImportConfiguration, ImportRequest


SCHEMA = "coin-analyzer-ocr-benchmark"
REQUIRED_FIELDS = ("country", "denomination", "year")
TIMING_BOUNDARY = (
    "temporary-package creation through OCR handoff decoding; when enabled, "
    "confirmed-reference persistence and collection reload are also included"
)


class BenchmarkManifestError(ValueError):
    """The benchmark manifest is unsafe or malformed."""


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    obverse: Path
    reverse: Path
    expected: Mapping[str, str]
    identity_certain: bool
    difficulty: tuple[str, ...]
    provenance: Mapping[str, object]
    notes: str


@dataclass(frozen=True, slots=True)
class BenchmarkManifest:
    version: str
    root: Path
    cases: tuple[BenchmarkCase, ...]


def to_evaluation_case(
    manifest: BenchmarkManifest,
    case: BenchmarkCase,
    *,
    allowed_abstention: bool,
    privacy_classification: str,
) -> EvaluationCase:
    """Project one validated OCR case into the common comparison contract."""

    provenance = case.provenance
    return EvaluationCase(
        case_id=case.case_id,
        specimen_id=None,
        inputs=tuple(
            sorted(
                (
                    EvaluationInput(
                        role="obverse",
                        reference=case.obverse.relative_to(manifest.root).as_posix(),
                    ),
                    EvaluationInput(
                        role="reverse",
                        reference=case.reverse.relative_to(manifest.root).as_posix(),
                    ),
                ),
                key=lambda item: item.role,
            )
        ),
        expected_findings=tuple(
            ExpectedFinding(field=field, value=value)
            for field, value in sorted(case.expected.items())
        ),
        allowed_abstention=allowed_abstention,
        provenance=(
            EvaluationProvenance(
                role="case",
                source_reference=str(provenance["source_url"]),
                license=str(provenance["license"]),
                author=str(provenance["author"]),
                label_method="manifest_ground_truth",
            ),
        ),
        privacy_classification=privacy_classification,
    )


def _require_text(value: object, name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise BenchmarkManifestError(f"{name} must be a non-empty string.")
    return value.strip()


def _contained_image(root: Path, value: object, name: str) -> Path:
    text = _require_text(value, name)
    if "\\" in text:
        raise BenchmarkManifestError(f"{name} must use POSIX relative separators.")
    relative = PurePosixPath(text)
    if relative.is_absolute() or ".." in relative.parts:
        raise BenchmarkManifestError(f"{name} must be a contained relative path.")
    candidate = root.joinpath(*relative.parts).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise BenchmarkManifestError(f"{name} escapes the benchmark root.") from exc
    if candidate.suffix.casefold() not in {".jpg", ".jpeg", ".png"}:
        raise BenchmarkManifestError(f"{name} must reference JPG, JPEG, or PNG.")
    if not candidate.is_file():
        raise BenchmarkManifestError(f"{name} does not exist: {text}.")
    return candidate


def load_manifest(path: str | Path) -> BenchmarkManifest:
    manifest_path = Path(path).resolve()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkManifestError(f"Cannot read benchmark manifest: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise BenchmarkManifestError(f"schema must be {SCHEMA!r}.")
    version = _require_text(payload.get("version"), "version")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise BenchmarkManifestError("cases must be a non-empty list.")

    root = manifest_path.parent
    seen: set[str] = set()
    cases: list[BenchmarkCase] = []
    for index, raw in enumerate(raw_cases):
        name = f"cases[{index}]"
        if not isinstance(raw, dict):
            raise BenchmarkManifestError(f"{name} must be an object.")
        case_id = _require_text(raw.get("id"), f"{name}.id")
        if case_id in seen:
            raise BenchmarkManifestError(f"duplicate case id: {case_id}.")
        seen.add(case_id)
        expected_raw = raw.get("expected")
        if not isinstance(expected_raw, dict):
            raise BenchmarkManifestError(f"{name}.expected must be an object.")
        expected = {
            field: _require_text(expected_raw.get(field), f"{name}.expected.{field}")
            for field in REQUIRED_FIELDS
        }
        for optional in ("variety", "monarch"):
            if optional in expected_raw:
                expected[optional] = _require_text(
                    expected_raw[optional], f"{name}.expected.{optional}"
                )
        certain = raw.get("identity_certain")
        if not isinstance(certain, bool):
            raise BenchmarkManifestError(f"{name}.identity_certain must be boolean.")
        difficulty_raw = raw.get("difficulty")
        if (
            not isinstance(difficulty_raw, list)
            or not difficulty_raw
            or any(not isinstance(item, str) or not item.strip() for item in difficulty_raw)
        ):
            raise BenchmarkManifestError(f"{name}.difficulty must be non-empty strings.")
        difficulty = tuple(sorted(set(item.strip() for item in difficulty_raw)))
        provenance = raw.get("provenance")
        if not isinstance(provenance, dict):
            raise BenchmarkManifestError(f"{name}.provenance must be an object.")
        for required in ("source_url", "license", "author"):
            _require_text(provenance.get(required), f"{name}.provenance.{required}")
        notes = _require_text(raw.get("notes", ""), f"{name}.notes", allow_empty=True)
        cases.append(
            BenchmarkCase(
                case_id=case_id,
                obverse=_contained_image(root, raw.get("obverse"), f"{name}.obverse"),
                reverse=_contained_image(root, raw.get("reverse"), f"{name}.reverse"),
                expected=expected,
                identity_certain=certain,
                difficulty=difficulty,
                provenance=dict(provenance),
                notes=notes,
            )
        )
    return BenchmarkManifest(version=version, root=root, cases=tuple(cases))


def _normalized(value: object) -> str:
    return " ".join(str(value).strip().casefold().split())


def exact_match(actual: object, expected: object) -> bool:
    return _normalized(actual) == _normalized(expected)


def _nearest_rank_p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def aggregate_latencies(values: Iterable[float]) -> dict[str, float | None]:
    data = [float(value) for value in values]
    return {
        "mean_seconds": statistics.fmean(data) if data else None,
        "median_seconds": statistics.median(data) if data else None,
        "p95_seconds": _nearest_rank_p95(data),
    }


def _rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def score_results(results: Iterable[Mapping[str, object]]) -> dict[str, object]:
    rows = list(results)
    evaluated = [row for row in rows if row.get("ocr_evaluated") is True]
    certain = [row for row in evaluated if row.get("identity_certain") is True]
    correct = Counter()
    for row in certain:
        field_scores = row.get("field_scores", {})
        if isinstance(field_scores, Mapping):
            for field in REQUIRED_FIELDS:
                correct[field] += bool(field_scores.get(field))
            correct["full_identity"] += all(field_scores.get(field) is True for field in REQUIRED_FIELDS)
    infrastructure = sum(row.get("infrastructure_failure") is not None for row in rows)
    unresolved = sum(row.get("unresolved") is True for row in evaluated)
    corrected = sum(row.get("correction_required") is True for row in certain)
    persisted = [row for row in rows if row.get("persistence_exercised") is True]
    persistence_success = sum(row.get("persistence_success") is True for row in persisted)
    return {
        "total_cases": len(rows),
        "evaluated_cases": len(evaluated),
        "certain_scored_cases": len(certain),
        "infrastructure_failures": infrastructure,
        "country_accuracy": _rate(correct["country"], len(certain)),
        "denomination_accuracy": _rate(correct["denomination"], len(certain)),
        "year_accuracy": _rate(correct["year"], len(certain)),
        "full_identity_accuracy": _rate(correct["full_identity"], len(certain)),
        "unresolved_rate": _rate(unresolved, len(evaluated)),
        "correction_required_rate": _rate(corrected, len(certain)),
        "failure_rate": _rate(infrastructure, len(rows)),
        "persistence_success_rate": _rate(persistence_success, len(persisted)),
        "latency": aggregate_latencies(
            row["latency_seconds"]
            for row in evaluated
            if isinstance(row.get("latency_seconds"), (int, float))
        ),
    }


def _select_raw_prediction(report) -> tuple[dict[str, str], list[str]]:
    by_field: dict[str, set[str]] = defaultdict(set)
    for candidate in report.candidates:
        if candidate.field_name in REQUIRED_FIELDS:
            by_field[candidate.field_name].add(candidate.normalized_value)
    prediction: dict[str, str] = {}
    unresolved: list[str] = []
    conflict_fields = {conflict.field_name for conflict in report.conflicts}
    for field in REQUIRED_FIELDS:
        values = by_field[field]
        if len(values) == 1 and field not in conflict_fields:
            prediction[field] = next(iter(values))
        else:
            unresolved.append(field)
    return prediction, unresolved


def _persist_reference(case: BenchmarkCase, package_path: Path, root: Path) -> bool:
    collection_path = root / "collection.json"
    managed = ManagedCollectionImageStore(
        root / "managed", collection_path_prefix="managed"
    )
    item = persist_reviewed_coin(
        collection=CoinCollection(str(collection_path)),
        draft=ReviewedCoinDraft(
            source_coin_id="coin-1",
            country=case.expected["country"],
            denomination=case.expected["denomination"],
            year=case.expected["year"],
        ),
        item_id=str(uuid4()),
        source_package_path=package_path,
        managed_image_store=managed,
        snapshot_service=CapturePackageSnapshotService(root / "snapshots"),
        import_lock_path=root / "import.lock",
    )
    reopened = CoinCollection(str(collection_path)).get_item(item.id)
    if reopened is None or len(reopened.photos) != 2:
        return False
    return all(
        managed.root.joinpath(*Path(photo.path).parts[1:]).is_file()
        for photo in reopened.photos
    )


def _run_case(
    case: BenchmarkCase,
    *,
    composition,
    exercise_persistence: bool,
    clock: Callable[[], float],
) -> dict[str, object]:
    result: dict[str, object] = {
        "case_id": case.case_id,
        "difficulty": list(case.difficulty),
        "expected": dict(case.expected),
        "identity_certain": case.identity_certain,
        "provenance": dict(case.provenance),
        "raw_prediction": {},
        "reference_corrected_result": dict(case.expected) if case.identity_certain else None,
        "ocr_evaluated": False,
        "unresolved": True,
        "correction_required": None,
        "persistence_exercised": False,
        "persistence_success": None,
        "infrastructure_failure": None,
    }
    source = None
    started = clock()
    try:
        source = create_temporary_capture_package(
            front_path=case.obverse, reverse_path=case.reverse
        )
        with TemporaryDirectory(prefix="coin-analyzer-benchmark-") as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            workspace.mkdir()
            outcome = ImportWorkflow(composition.pipeline).execute(
                ImportRequest(
                    source=source.path,
                    collection_id=f"benchmark-{case.case_id}",
                    configuration=ImportConfiguration(),
                ),
                workspace.resolve(),
            )
            handoff = create_desktop_ocr_review_handoff(
                composition=composition, outcome=outcome
            )
            prediction, unresolved_fields = _select_raw_prediction(handoff.report)
            result.update(
                {
                    "raw_prediction": prediction,
                    "raw_observations": [item.to_dict() for item in handoff.report.observations],
                    "raw_candidates": [item.to_dict() for item in handoff.report.candidates],
                    "raw_conflicts": [item.to_dict() for item in handoff.report.conflicts],
                    "provider_available": handoff.report.provider_available,
                    "ocr_evaluated": True,
                    "unresolved_fields": unresolved_fields,
                    "unresolved": bool(unresolved_fields) or not handoff.report.provider_available,
                }
            )
            scores = {
                field: field in prediction and exact_match(prediction[field], case.expected[field])
                for field in REQUIRED_FIELDS
            }
            result["field_scores"] = scores
            if case.identity_certain:
                result["correction_required"] = not all(scores.values())
            result["review_outcome"] = (
                "unresolved"
                if result["unresolved"]
                else (
                    "correction_required"
                    if result["correction_required"]
                    else "accepted_without_correction"
                )
            )
            if exercise_persistence and case.identity_certain:
                result["persistence_exercised"] = True
                result["persistence_success"] = _persist_reference(
                    case, source.path, root / "persistence"
                )
                if result["persistence_success"] is not True:
                    raise RuntimeError("persisted collection did not reload with both images")
    except Exception as exc:
        result["infrastructure_failure"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
    finally:
        result["latency_seconds"] = clock() - started
        if source is not None:
            source.release()
    return result


def _runtime_configuration() -> dict[str, object]:
    configuration: dict[str, object] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "ocr_provider": "legacy-ocr",
        "ocr_engine": TESSERACT_COIN_ENGINE,
        "ocr_configuration": TESSERACT_COIN_CONFIG,
        "ocr_page_segmentation_mode": (
            TESSERACT_COIN_PAGE_SEGMENTATION_MODE
        ),
        "ocr_preprocessing": TESSERACT_COIN_PREPROCESSING,
        "pipeline": "create_desktop_ocr_review_composition",
    }
    try:
        import pytesseract

        configuration["pytesseract_version"] = getattr(
            pytesseract, "__version__", "unknown"
        )
        configuration["tesseract_version"] = str(
            pytesseract.get_tesseract_version()
        ).splitlines()[0]
        configuration["tesseract_available"] = True
    except Exception as exc:
        configuration["tesseract_version"] = f"unavailable: {type(exc).__name__}"
        configuration["tesseract_available"] = False
    return configuration


def analyze_failures(results: Iterable[Mapping[str, object]]) -> dict[str, object]:
    rows = list(results)
    classes = Counter()
    missing = Counter()
    correction_cases: list[str] = []
    for row in rows:
        if row.get("infrastructure_failure") is not None:
            failure = row["infrastructure_failure"]
            kind = failure.get("type", "unknown") if isinstance(failure, Mapping) else "unknown"
            classes[f"infrastructure:{kind}"] += 1
        if row.get("ocr_evaluated") is True:
            candidates = row.get("raw_candidates", [])
            if not candidates:
                classes["no_structured_candidates"] += 1
            for field in row.get("unresolved_fields", []):
                missing[str(field)] += 1
            if row.get("correction_required") is True:
                correction_cases.append(str(row.get("case_id")))
    return {
        "error_classes": dict(sorted(classes.items())),
        "unresolved_required_fields": dict(sorted(missing.items())),
        "cases_requiring_human_correction": sorted(correction_cases),
    }


def _git_state(root: Path) -> dict[str, object]:
    def command(*args: str) -> str:
        return subprocess.check_output(
            ["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    try:
        return {
            "commit": command("rev-parse", "HEAD"),
            "dirty": bool(command("status", "--porcelain")),
        }
    except (OSError, subprocess.SubprocessError):
        return {"commit": "unknown", "dirty": None}


def run_benchmark(
    manifest: BenchmarkManifest,
    *,
    exercise_persistence: bool = False,
    clock: Callable[[], float] = perf_counter,
    composition_factory: Callable[[], object] = create_desktop_ocr_review_composition,
) -> dict[str, object]:
    runtime = _runtime_configuration()
    composition = composition_factory()
    results = [
        _run_case(
            case,
            composition=composition,
            exercise_persistence=exercise_persistence,
            clock=clock,
        )
        for case in manifest.cases
    ]
    if runtime["tesseract_available"] is not True:
        for result in results:
            if result["infrastructure_failure"] is None:
                result["infrastructure_failure"] = {
                    "type": "OCRRuntimeUnavailable",
                    "message": str(runtime["tesseract_version"]),
                }
            result["ocr_evaluated"] = False
    summary = score_results(results)
    difficulty: dict[str, object] = {}
    tags = sorted({tag for case in manifest.cases for tag in case.difficulty})
    for tag in tags:
        difficulty[tag] = score_results(
            row for row in results if tag in row.get("difficulty", [])
        )
    return {
        "schema": "coin-analyzer-ocr-evaluation-report",
        "dataset_version": manifest.version,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git": _git_state(manifest.root),
        "runtime": {
            **runtime,
            "persistence_exercised": exercise_persistence,
        },
        "timing_boundary": TIMING_BOUNDARY,
        "summary": summary,
        "difficulty_breakdown": difficulty,
        "failure_analysis": analyze_failures(results),
        "cases": results,
        "limitations": [
            "Benchmark v1 is small and does not support statistical-significance claims.",
            "Reference-corrected results are manifest ground truth, not automated review output.",
            "The dataset is a fixed baseline and is not a training set.",
        ],
    }


def _percent(value: object) -> str:
    return "n/a" if value is None else f"{float(value) * 100:.1f}%"


def render_summary(report: Mapping[str, object]) -> str:
    summary = report["summary"]
    assert isinstance(summary, Mapping)
    latency = summary["latency"]
    assert isinstance(latency, Mapping)
    failure_analysis = report.get("failure_analysis", {})
    error_classes = (
        failure_analysis.get("error_classes", {})
        if isinstance(failure_analysis, Mapping)
        else {}
    )
    def seconds(name: str) -> str:
        value = latency.get(name)
        return "n/a" if value is None else f"{float(value):.3f}s"
    lines = [
        f"Coin Analyzer OCR Benchmark {report['dataset_version']}",
        f"Total/evaluated: {summary['total_cases']}/{summary['evaluated_cases']}",
        f"Infrastructure failures: {summary['infrastructure_failures']}",
        f"Country accuracy: {_percent(summary['country_accuracy'])}",
        f"Denomination accuracy: {_percent(summary['denomination_accuracy'])}",
        f"Year accuracy: {_percent(summary['year_accuracy'])}",
        f"Full identity accuracy: {_percent(summary['full_identity_accuracy'])}",
        f"Unresolved rate: {_percent(summary['unresolved_rate'])}",
        f"Correction-required rate: {_percent(summary['correction_required_rate'])}",
        f"Failure rate: {_percent(summary['failure_rate'])}",
        f"Latency mean/median/p95: {seconds('mean_seconds')} / {seconds('median_seconds')} / {seconds('p95_seconds')}",
        f"Persistence success: {_percent(summary['persistence_success_rate'])}",
        "Error classes: "
        + (
            ", ".join(f"{name}={count}" for name, count in error_classes.items())
            if isinstance(error_classes, Mapping) and error_classes
            else "none"
        ),
    ]
    return "\n".join(lines) + "\n"


def write_report(
    report: Mapping[str, object], *, json_path: Path, summary_path: Path
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(render_summary(report), encoding="utf-8")
