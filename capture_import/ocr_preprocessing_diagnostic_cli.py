"""Benchmark-only OCR preprocessing/configuration diagnostic matrix.

This module is intentionally isolated from production recognition. It runs a small
set of local Pillow/pytesseract variants against an existing benchmark manifest
and reports diagnostic token recovery plus deterministic suggestion yield.
Ground truth is used only for measurement and never fed into OCR or recognition.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Callable, Iterable, Sequence

from ocr_experiment import OCRExperiment
from .evaluation_harness import BenchmarkCase, BenchmarkManifest, load_manifest


@dataclass(frozen=True, slots=True)
class OCRVariant:
    name: str
    psm: int
    transform: str


VARIANTS: tuple[OCRVariant, ...] = (
    OCRVariant("baseline-psm11", 11, "original"),
    OCRVariant("grayscale-contrast-psm11", 11, "grayscale_contrast"),
    OCRVariant("adaptive-threshold-psm11", 11, "adaptive_threshold"),
    OCRVariant("upscale2x-psm11", 11, "upscale2x"),
    OCRVariant("grayscale-contrast-psm6", 6, "grayscale_contrast"),
    OCRVariant("grayscale-contrast-psm12", 12, "grayscale_contrast"),
)


def _normalize(value: object) -> str:
    return " ".join(str(value).casefold().split())


def _expected_token_presence(text: str, case: BenchmarkCase) -> dict[str, bool]:
    haystack = _normalize(text)
    return {
        field: _normalize(case.expected[field]) in haystack
        for field in ("country", "denomination", "year")
    }


def _transform_image(image, transform: str):
    from PIL import ImageEnhance, ImageOps, ImageFilter

    if transform == "original":
        return image.convert("RGB")
    if transform == "grayscale_contrast":
        gray = ImageOps.grayscale(image)
        return ImageEnhance.Contrast(gray).enhance(2.0)
    if transform == "adaptive_threshold":
        gray = ImageOps.grayscale(image).filter(ImageFilter.MedianFilter(size=3))
        # Pillow-only local threshold approximation using a global midpoint after
        # autocontrast; diagnostic only, not production preprocessing.
        gray = ImageOps.autocontrast(gray)
        return gray.point(lambda px: 255 if px >= 145 else 0)
    if transform == "upscale2x":
        return image.convert("RGB").resize(
            (image.width * 2, image.height * 2),
            resample=getattr(__import__("PIL.Image", fromlist=["Image"]).Resampling, "LANCZOS"),
        )
    raise ValueError(f"unknown transform: {transform}")


def _ocr_image(path: Path, variant: OCRVariant) -> str:
    from PIL import Image
    import pytesseract

    with Image.open(path) as source:
        prepared = _transform_image(source, variant.transform)
        return pytesseract.image_to_string(prepared, config=f"--psm {variant.psm}")


def _diagnose_case(
    case: BenchmarkCase,
    *,
    variant: OCRVariant,
    ocr: Callable[[Path, OCRVariant], str] = _ocr_image,
) -> dict[str, object]:
    started = perf_counter()
    front = ocr(case.obverse, variant)
    reverse = ocr(case.reverse, variant)
    combined = "\n".join((front, reverse)).strip()
    suggestions = OCRExperiment().extract_suggestions(combined)
    token_presence = _expected_token_presence(combined, case)
    latency = perf_counter() - started
    yield_by_field = {
        "country": len(suggestions["possible_countries"]),
        "denomination": len(suggestions["possible_denominations"]),
        "year": len(suggestions["possible_years"]),
    }
    return {
        "case_id": case.case_id,
        "difficulty": list(case.difficulty),
        "raw_text": {"front": front.strip(), "reverse": reverse.strip()},
        "expected_token_presence_diagnostic_only": token_presence,
        "suggestion_yield_by_field": yield_by_field,
        "suggestions": {
            "countries": suggestions["possible_countries"],
            "denominations": suggestions["possible_denominations"],
            "years": suggestions["possible_years"],
        },
        "recovered_required_token_count": sum(token_presence.values()),
        "structured_suggestion_count": sum(yield_by_field.values()),
        "latency_seconds": latency,
    }


def run_matrix(
    manifest: BenchmarkManifest,
    *,
    variants: Iterable[OCRVariant] = VARIANTS,
    ocr: Callable[[Path, OCRVariant], str] = _ocr_image,
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for variant in variants:
        cases = [_diagnose_case(case, variant=variant, ocr=ocr) for case in manifest.cases]
        rows.append(
            {
                "variant": {
                    "name": variant.name,
                    "psm": variant.psm,
                    "transform": variant.transform,
                },
                "cases": cases,
                "summary": {
                    "case_count": len(cases),
                    "required_tokens_recovered": sum(
                        int(item["recovered_required_token_count"]) for item in cases
                    ),
                    "structured_suggestions": sum(
                        int(item["structured_suggestion_count"]) for item in cases
                    ),
                    "cases_with_any_required_token": sum(
                        int(item["recovered_required_token_count"]) > 0 for item in cases
                    ),
                    "mean_latency_seconds": (
                        sum(float(item["latency_seconds"]) for item in cases) / len(cases)
                        if cases else None
                    ),
                },
            }
        )
    return {
        "schema": "coin-analyzer-ocr-preprocessing-diagnostic-v1",
        "source_dataset_version": manifest.version,
        "variants": rows,
        "warning": (
            "benchmark expected values are used only to score token recovery; they are never "
            "provided to OCR, suggestion extraction, resolver, UI, persistence, or production flow"
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coin-analyzer-ocr-preprocessing-diagnostic")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--json", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_matrix(load_manifest(args.manifest))
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
