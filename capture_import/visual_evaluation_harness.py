"""Dataset and scoring contracts for visual-identification Benchmark v2.

This module does not import, select, or execute a visual model.  It validates
the frozen paired-image dataset and scores externally supplied raw provider
results without invoking OCR, fusion, review, or persistence.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import statistics
from typing import Iterable, Mapping

from PIL import Image


SCHEMA = "coin-analyzer-visual-benchmark"
REQUIRED_IDENTITY_FIELDS = ("country", "denomination", "year")
OPTIONAL_IDENTITY_FIELDS = ("type_design",)
ALLOWED_OUTCOMES = frozenset(
    {"PREDICTED", "ABSTAINED", "INFRASTRUCTURE_FAILURE"}
)
ALLOWED_LICENSES = frozenset(
    {
        "CC0-1.0",
        "CC-BY-2.0",
        "CC-BY-3.0",
        "CC-BY-4.0",
        "CC-BY-SA-2.0",
        "CC-BY-SA-3.0",
        "CC-BY-SA-4.0",
        "PUBLIC-DOMAIN",
    }
)


class VisualBenchmarkManifestError(ValueError):
    """The visual benchmark manifest is unsafe or incomplete."""


@dataclass(frozen=True, slots=True)
class VisualBenchmarkImage:
    role: str
    path: Path
    source_asset_path: Path
    source_page: str
    source_file_url: str
    author: str
    license: str
    retrieved_at: str
    source_sha256: str
    transformation: str


@dataclass(frozen=True, slots=True)
class VisualBenchmarkCase:
    case_id: str
    underlying_identity: str
    obverse: VisualBenchmarkImage
    reverse: VisualBenchmarkImage
    expected: Mapping[str, str]
    identity_certain: bool
    era: str
    difficulty: tuple[str, ...]
    previously_used: bool
    notes: str


@dataclass(frozen=True, slots=True)
class VisualBenchmarkManifest:
    version: str
    root: Path
    cases: tuple[VisualBenchmarkCase, ...]


def _text(value: object, name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise VisualBenchmarkManifestError(f"{name} must be a non-empty string.")
    return value.strip()


def _contained_image(root: Path, value: object, name: str) -> Path:
    text = _text(value, name)
    if "\\" in text:
        raise VisualBenchmarkManifestError(f"{name} must use POSIX separators.")
    relative = PurePosixPath(text)
    if relative.is_absolute() or ".." in relative.parts:
        raise VisualBenchmarkManifestError(f"{name} must be a contained relative path.")
    path = root.joinpath(*relative.parts).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as error:
        raise VisualBenchmarkManifestError(f"{name} escapes the benchmark root.") from error
    if path.suffix.casefold() not in {".jpg", ".jpeg", ".png"}:
        raise VisualBenchmarkManifestError(f"{name} must be JPG, JPEG, or PNG.")
    if not path.is_file():
        raise VisualBenchmarkManifestError(f"{name} does not exist: {text}.")
    return path


def _image(root: Path, raw: object, name: str, role: str) -> VisualBenchmarkImage:
    if not isinstance(raw, Mapping):
        raise VisualBenchmarkManifestError(f"{name} must be an object.")
    actual_role = _text(raw.get("role"), f"{name}.role")
    if actual_role != role:
        raise VisualBenchmarkManifestError(f"{name}.role must be {role!r}.")
    license_name = _text(raw.get("license"), f"{name}.license")
    if license_name not in ALLOWED_LICENSES:
        raise VisualBenchmarkManifestError(f"{name}.license is not allowlisted.")
    digest = _text(raw.get("source_sha256"), f"{name}.source_sha256")
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise VisualBenchmarkManifestError(f"{name}.source_sha256 must be lowercase SHA-256.")
    source_asset_path = _contained_image(
        root, raw.get("source_asset_path"), f"{name}.source_asset_path"
    )
    if hashlib.sha256(source_asset_path.read_bytes()).hexdigest() != digest:
        raise VisualBenchmarkManifestError(
            f"{name}.source_sha256 does not match source_asset_path."
        )
    return VisualBenchmarkImage(
        role=actual_role,
        path=_contained_image(root, raw.get("path"), f"{name}.path"),
        source_asset_path=source_asset_path,
        source_page=_text(raw.get("source_page"), f"{name}.source_page"),
        source_file_url=_text(raw.get("source_file_url"), f"{name}.source_file_url"),
        author=_text(raw.get("author"), f"{name}.author"),
        license=license_name,
        retrieved_at=_text(raw.get("retrieved_at"), f"{name}.retrieved_at"),
        source_sha256=digest,
        transformation=_text(raw.get("transformation"), f"{name}.transformation"),
    )


def load_visual_manifest(path: str | Path) -> VisualBenchmarkManifest:
    manifest_path = Path(path).resolve()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VisualBenchmarkManifestError(f"Cannot read visual benchmark: {error}") from error
    if not isinstance(payload, Mapping) or payload.get("schema") != SCHEMA:
        raise VisualBenchmarkManifestError(f"schema must be {SCHEMA!r}.")
    version = _text(payload.get("version"), "version")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise VisualBenchmarkManifestError("cases must be a non-empty list.")
    root = manifest_path.parent
    case_ids: set[str] = set()
    cases: list[VisualBenchmarkCase] = []
    for index, raw in enumerate(raw_cases):
        name = f"cases[{index}]"
        if not isinstance(raw, Mapping):
            raise VisualBenchmarkManifestError(f"{name} must be an object.")
        case_id = _text(raw.get("id"), f"{name}.id")
        if case_id in case_ids:
            raise VisualBenchmarkManifestError(f"duplicate case id: {case_id}.")
        case_ids.add(case_id)
        expected_raw = raw.get("expected")
        if not isinstance(expected_raw, Mapping):
            raise VisualBenchmarkManifestError(f"{name}.expected must be an object.")
        expected = {
            field: _text(expected_raw.get(field), f"{name}.expected.{field}")
            for field in REQUIRED_IDENTITY_FIELDS
        }
        for field in OPTIONAL_IDENTITY_FIELDS:
            if field in expected_raw:
                expected[field] = _text(expected_raw[field], f"{name}.expected.{field}")
        certain = raw.get("identity_certain")
        if not isinstance(certain, bool):
            raise VisualBenchmarkManifestError(f"{name}.identity_certain must be boolean.")
        difficulty_raw = raw.get("difficulty")
        if not isinstance(difficulty_raw, list) or not difficulty_raw:
            raise VisualBenchmarkManifestError(f"{name}.difficulty must be non-empty.")
        difficulty = tuple(sorted({_text(item, f"{name}.difficulty") for item in difficulty_raw}))
        previously_used = raw.get("previously_used")
        if not isinstance(previously_used, bool):
            raise VisualBenchmarkManifestError(f"{name}.previously_used must be boolean.")
        cases.append(
            VisualBenchmarkCase(
                case_id=case_id,
                underlying_identity=_text(raw.get("underlying_identity"), f"{name}.underlying_identity"),
                obverse=_image(root, raw.get("obverse"), f"{name}.obverse", "obverse"),
                reverse=_image(root, raw.get("reverse"), f"{name}.reverse", "reverse"),
                expected=expected,
                identity_certain=certain,
                era=_text(raw.get("era"), f"{name}.era"),
                difficulty=difficulty,
                previously_used=previously_used,
                notes=_text(raw.get("notes", ""), f"{name}.notes", allow_empty=True),
            )
        )
    return VisualBenchmarkManifest(version=version, root=root, cases=tuple(cases))


def _normalized(value: object) -> str:
    return " ".join(str(value).strip().casefold().split())


def _matches(prediction: Mapping[str, object], expected: Mapping[str, str], fields: Iterable[str]) -> bool:
    return all(field in prediction and _normalized(prediction[field]) == _normalized(expected[field]) for field in fields)


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


def score_visual_results(results: Iterable[Mapping[str, object]], *, top_k: int = 3) -> dict[str, object]:
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top_k must be a positive integer.")
    rows = list(results)
    outcomes = Counter()
    field_correct = Counter()
    field_eligible = Counter()
    top_k_correct = 0
    costs: list[float] = []
    latencies: list[float] = []
    for row in rows:
        outcome = row.get("outcome")
        if outcome not in ALLOWED_OUTCOMES:
            raise ValueError("result outcome is unsupported.")
        outcomes[str(outcome)] += 1
        latency = row.get("latency_seconds")
        if isinstance(latency, (int, float)) and not isinstance(latency, bool) and math.isfinite(latency) and latency >= 0:
            latencies.append(float(latency))
        cost = row.get("estimated_cost_usd")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool) and math.isfinite(cost) and cost >= 0:
            costs.append(float(cost))
        if row.get("identity_certain") is not True or outcome == "INFRASTRUCTURE_FAILURE":
            continue
        expected = row.get("expected")
        if not isinstance(expected, Mapping):
            raise ValueError("evaluated certain results require expected values.")
        for field in (*REQUIRED_IDENTITY_FIELDS, *OPTIONAL_IDENTITY_FIELDS):
            if field in expected:
                field_eligible[field] += 1
        field_eligible["full_required_identity"] += 1
        field_eligible["top_k_identity"] += 1
        if outcome != "PREDICTED":
            continue
        predictions = row.get("predictions")
        if not isinstance(predictions, list) or not predictions:
            raise ValueError("predicted certain results require expected values and predictions.")
        if any(not isinstance(item, Mapping) for item in predictions):
            raise ValueError("predictions must contain objects.")
        first = predictions[0]
        for field in (*REQUIRED_IDENTITY_FIELDS, *OPTIONAL_IDENTITY_FIELDS):
            if field in expected:
                field_correct[field] += _matches(first, expected, (field,))
        required = tuple(field for field in REQUIRED_IDENTITY_FIELDS if field in expected)
        field_correct["full_required_identity"] += _matches(first, expected, required)
        identity_fields = tuple(field for field in (*REQUIRED_IDENTITY_FIELDS, *OPTIONAL_IDENTITY_FIELDS) if field in expected)
        top_k_correct += any(_matches(candidate, expected, identity_fields) for candidate in predictions[:top_k])
    return {
        "total_cases": len(rows),
        "predicted_cases": outcomes["PREDICTED"],
        "abstained_cases": outcomes["ABSTAINED"],
        "infrastructure_failures": outcomes["INFRASTRUCTURE_FAILURE"],
        "country_accuracy": _rate(field_correct["country"], field_eligible["country"]),
        "denomination_accuracy": _rate(field_correct["denomination"], field_eligible["denomination"]),
        "year_accuracy": _rate(field_correct["year"], field_eligible["year"]),
        "type_design_accuracy": _rate(field_correct["type_design"], field_eligible["type_design"]),
        "full_required_identity_accuracy": _rate(field_correct["full_required_identity"], field_eligible["full_required_identity"]),
        "top_k": top_k,
        "top_k_identity_recall": _rate(top_k_correct, field_eligible["top_k_identity"]),
        "abstention_rate": _rate(outcomes["ABSTAINED"], len(rows)),
        "infrastructure_failure_rate": _rate(outcomes["INFRASTRUCTURE_FAILURE"], len(rows)),
        "latency": _latencies(latencies),
        "estimated_cost_usd": {"total": sum(costs), "mean_per_case": _rate(sum(costs), len(costs))},
    }


def audit_visual_manifest(manifest: VisualBenchmarkManifest) -> dict[str, object]:
    identities = Counter(case.underlying_identity for case in manifest.cases)
    countries = Counter(case.expected["country"] for case in manifest.cases)
    eras = Counter(case.era for case in manifest.cases)
    difficulties = Counter(tag for case in manifest.cases for tag in case.difficulty)
    hashes: dict[str, list[str]] = {}
    perceptual_hashes: list[tuple[str, int, str]] = []
    source_pages: dict[str, set[str]] = {}
    for case in manifest.cases:
        for image in (case.obverse, case.reverse):
            digest = hashlib.sha256(image.path.read_bytes()).hexdigest()
            reference = f"{case.case_id}:{image.role}"
            hashes.setdefault(digest, []).append(reference)
            source_pages.setdefault(image.source_page, set()).add(case.case_id)
            with Image.open(image.path) as opened:
                reduced = opened.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
                pixels = list(reduced.get_flattened_data())
            difference_hash = sum(
                (pixels[row * 9 + column] > pixels[row * 9 + column + 1])
                << (row * 8 + column)
                for row in range(8)
                for column in range(8)
            )
            perceptual_hashes.append((reference, difference_hash, digest))
    duplicates = {digest: refs for digest, refs in hashes.items() if len(refs) > 1}
    near_duplicates = []
    for index, (left_ref, left_hash, left_digest) in enumerate(perceptual_hashes):
        for right_ref, right_hash, right_digest in perceptual_hashes[index + 1 :]:
            distance = (left_hash ^ right_hash).bit_count()
            if left_digest != right_digest and distance <= 4:
                near_duplicates.append(
                    {"left": left_ref, "right": right_ref, "distance": distance}
                )
    repeated_sources = {
        page: sorted(case_ids)
        for page, case_ids in source_pages.items()
        if len(case_ids) > 1
    }
    total = len(manifest.cases)
    largest_country = max(countries.values(), default=0)
    largest_identity = max(identities.values(), default=0)
    return {
        "cases": total,
        "unique_identities": len(identities),
        "countries": dict(sorted(countries.items())),
        "eras": dict(sorted(eras.items())),
        "difficulty": dict(sorted(difficulties.items())),
        "reused_v1_cases": sum(case.previously_used for case in manifest.cases),
        "duplicate_image_hashes": duplicates,
        "near_duplicate_candidates": near_duplicates,
        "repeated_source_pages_across_cases": repeated_sources,
        "largest_country_share": _rate(largest_country, total),
        "largest_identity_share": _rate(largest_identity, total),
    }
