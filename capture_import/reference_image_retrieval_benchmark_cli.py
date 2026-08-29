"""Benchmark independent reference-image retrieval for Coin Analyzer Benchmark v2.

This experiment is intentionally separate from the VLM/evidence resolver. It
compares each benchmark query coin against independently sourced catalogue
reference images using OpenCV ORB features plus coarse colour-histogram
similarity. It rejects exact-image leakage: reference files must not be byte-for-
byte identical to the benchmark query images.

Reference manifest schema:
{
  "schema": "coin-analyzer-reference-image-catalogue",
  "version": "v1",
  "candidates": [
    {
      "id": "canada-5-cents-1964",
      "obverse": ["refs/canada-5-cents-1964-obv.jpg"],
      "reverse": ["refs/canada-5-cents-1964-rev.jpg"]
    }
  ]
}

Paths are resolved relative to the reference manifest. Use genuinely independent
reference photographs; reusing Benchmark v2 query derivatives would invalidate
the result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

import cv2
import numpy as np

from .visual_evaluation_harness import load_visual_manifest

REFERENCE_SCHEMA = "coin-analyzer-reference-image-catalogue"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coin-analyzer-reference-image-retrieval-benchmark")
    parser.add_argument("benchmark_manifest", type=Path)
    parser.add_argument("reference_manifest", type=Path)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json", type=Path)
    return parser


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_image(root: Path, raw: object, label: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{label} must be a non-empty string")
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label} must be a contained relative path")
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} escapes the reference-manifest directory") from exc
    if path.suffix.casefold() not in IMAGE_SUFFIXES or not path.is_file():
        raise ValueError(f"{label} must point to an existing image: {raw}")
    return path


def _load_references(path: Path) -> tuple[str, dict[str, dict[str, tuple[Path, ...]]]]:
    manifest_path = path.resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or payload.get("schema") != REFERENCE_SCHEMA:
        raise ValueError(f"reference schema must be {REFERENCE_SCHEMA!r}")
    version = str(payload.get("version") or "").strip()
    raw_candidates = payload.get("candidates")
    if not version or not isinstance(raw_candidates, list) or not raw_candidates:
        raise ValueError("reference manifest requires version and non-empty candidates")
    root = manifest_path.parent
    out: dict[str, dict[str, tuple[Path, ...]]] = {}
    for index, raw in enumerate(raw_candidates):
        if not isinstance(raw, Mapping):
            raise ValueError(f"candidates[{index}] must be an object")
        candidate_id = str(raw.get("id") or "").strip()
        if not candidate_id or candidate_id in out:
            raise ValueError(f"invalid or duplicate candidate id at index {index}")
        sides: dict[str, tuple[Path, ...]] = {}
        for role in ("obverse", "reverse"):
            values = raw.get(role)
            if not isinstance(values, list) or not values:
                raise ValueError(f"{candidate_id}.{role} must be a non-empty array")
            sides[role] = tuple(
                _resolve_image(root, value, f"{candidate_id}.{role}[{i}]")
                for i, value in enumerate(values)
            )
        out[candidate_id] = sides
    return version, out


def _read(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"cannot decode image: {path}")
    return image


def _prepare(image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    size = min(h, w)
    y = max(0, (h - size) // 2)
    x = max(0, (w - size) // 2)
    square = image[y:y + size, x:x + size]
    return cv2.resize(square, (320, 320), interpolation=cv2.INTER_AREA)


def _rotations(image: np.ndarray) -> tuple[np.ndarray, ...]:
    return (
        image,
        cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE),
        cv2.rotate(image, cv2.ROTATE_180),
        cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE),
    )


def _orb_score(a: np.ndarray, b: np.ndarray) -> float:
    gray_a = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(nfeatures=1200, fastThreshold=8)
    key_a, desc_a = orb.detectAndCompute(gray_a, None)
    key_b, desc_b = orb.detectAndCompute(gray_b, None)
    if desc_a is None or desc_b is None or not key_a or not key_b:
        return 0.0
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = matcher.match(desc_a, desc_b)
    if not matches:
        return 0.0
    good = [m for m in matches if m.distance <= 55]
    denominator = max(1, min(len(key_a), len(key_b), 180))
    density = min(1.0, len(good) / denominator)
    if not good:
        return 0.0
    quality = 1.0 - min(1.0, float(np.mean([m.distance for m in good])) / 80.0)
    return 0.70 * density + 0.30 * quality


def _hist_score(a: np.ndarray, b: np.ndarray) -> float:
    hsv_a = cv2.cvtColor(a, cv2.COLOR_BGR2HSV)
    hsv_b = cv2.cvtColor(b, cv2.COLOR_BGR2HSV)
    hist_a = cv2.calcHist([hsv_a], [0, 1], None, [24, 24], [0, 180, 0, 256])
    hist_b = cv2.calcHist([hsv_b], [0, 1], None, [24, 24], [0, 180, 0, 256])
    cv2.normalize(hist_a, hist_a)
    cv2.normalize(hist_b, hist_b)
    correlation = cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL)
    return max(0.0, min(1.0, (correlation + 1.0) / 2.0))


def _image_similarity(query_path: Path, reference_path: Path) -> tuple[float, dict[str, float]]:
    query = _prepare(_read(query_path))
    reference = _prepare(_read(reference_path))
    best_orb = 0.0
    best_hist = 0.0
    best = 0.0
    for rotated in _rotations(reference):
        orb = _orb_score(query, rotated)
        hist = _hist_score(query, rotated)
        score = 0.78 * orb + 0.22 * hist
        if score > best:
            best, best_orb, best_hist = score, orb, hist
    return best, {"orb": best_orb, "histogram": best_hist}


def _side_score(query_path: Path, refs: tuple[Path, ...]) -> tuple[float, dict[str, object]]:
    ranked: list[tuple[float, Path, dict[str, float]]] = []
    for ref in refs:
        score, detail = _image_similarity(query_path, ref)
        ranked.append((score, ref, detail))
    ranked.sort(key=lambda item: -item[0])
    score, ref, detail = ranked[0]
    return score, {"reference": ref.as_posix(), **detail}


def _candidate_score(case, refs: dict[str, tuple[Path, ...]]) -> tuple[float, dict[str, object]]:
    obv, obv_detail = _side_score(case.obverse.path, refs["obverse"])
    rev, rev_detail = _side_score(case.reverse.path, refs["reverse"])
    # Require both sides to contribute; geometric mean punishes one-side coincidences.
    combined = math.sqrt(max(0.0, obv) * max(0.0, rev))
    return combined, {"obverse": obv, "reverse": rev, "obverse_detail": obv_detail, "reverse_detail": rev_detail}


def _validate_no_leakage(benchmark, references: Mapping[str, Mapping[str, tuple[Path, ...]]]) -> None:
    query_hashes = {
        _sha256(case.obverse.path) for case in benchmark.cases
    } | {
        _sha256(case.reverse.path) for case in benchmark.cases
    }
    duplicates: list[str] = []
    for candidate_id, sides in references.items():
        for role in ("obverse", "reverse"):
            for path in sides[role]:
                if _sha256(path) in query_hashes:
                    duplicates.append(f"{candidate_id}:{role}:{path}")
    if duplicates:
        raise SystemExit(
            "Reference-image leakage detected; benchmark query images cannot be used as references:\n  "
            + "\n  ".join(duplicates[:20])
        )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.top_k < 1:
        raise SystemExit("--top-k must be >= 1")
    benchmark = load_visual_manifest(args.benchmark_manifest)
    ref_version, references = _load_references(args.reference_manifest)
    missing = [case.case_id for case in benchmark.cases if case.case_id not in references]
    if missing:
        raise SystemExit("reference catalogue missing benchmark IDs: " + ", ".join(missing))
    _validate_no_leakage(benchmark, references)

    rows: list[dict[str, object]] = []
    for query in benchmark.cases:
        ranked: list[tuple[float, str, dict[str, object]]] = []
        for candidate in benchmark.cases:
            score, detail = _candidate_score(query, references[candidate.case_id])
            ranked.append((score, candidate.case_id, detail))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        top = ranked[: args.top_k]
        ids = [candidate_id for _, candidate_id, _ in top]
        best_score, best_id, _ = ranked[0]
        runner = ranked[1][0] if len(ranked) > 1 else 0.0
        hit = query.case_id in ids
        correct_top1 = best_id == query.case_id
        rows.append({
            "case_id": query.case_id,
            "top1_candidate_id": best_id,
            "top1_correct": correct_top1,
            "retrieval_hit": hit,
            "top1_score": best_score,
            "margin": best_score - runner,
            "top_k": [
                {"candidate_id": cid, "score": score, "detail": detail}
                for score, cid, detail in top
            ],
        })
        print(
            f"{query.case_id} | top1={best_id} | correct={correct_top1} | "
            f"hit@{args.top_k}={hit} | score={best_score:.4f} margin={best_score-runner:.4f}",
            flush=True,
        )

    total = len(rows)
    top1 = sum(bool(row["top1_correct"]) for row in rows)
    recall = sum(bool(row["retrieval_hit"]) for row in rows)
    metrics = {
        "total_cases": total,
        "top_k": args.top_k,
        "top1_accuracy": top1 / total if total else None,
        "recall_at_k": recall / total if total else None,
    }
    output = {
        "schema": "coin-analyzer-reference-image-retrieval-benchmark-v1",
        "dataset_version": benchmark.version,
        "reference_catalogue_version": ref_version,
        "backend": "opencv-orb-plus-hsv-histogram-rotation-invariant",
        "leakage_guard": "exact benchmark query bytes rejected",
        "rows": rows,
        "metrics": metrics,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Reference-image retrieval benchmark: {benchmark.version}")
    print(f"Cases: {total}; top-k: {args.top_k}")
    print(f"Top-1 accuracy: {metrics['top1_accuracy'] * 100:.1f}%")
    print(f"Recall@{args.top_k}: {metrics['recall_at_k'] * 100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
