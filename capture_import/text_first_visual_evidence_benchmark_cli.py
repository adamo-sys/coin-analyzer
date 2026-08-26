"""Benchmark text-first visual evidence extraction against MiniCPM v2 failures.

This diagnostic reuses the saved MiniCPM Benchmark v2 report and the frozen v2
manifest. It asks MiniCPM to transcribe visible coin text only (no identity
fields), combines those transcriptions with optional OCR-like text already
present in the saved side results, and evaluates whether the resulting textual
evidence is sufficient to recover required identity fields using a bounded
oracle catalogue built from the benchmark manifest.

The experiment is benchmark-only and does not affect production recognition,
UI, persistence, or default model composition.
"""

from __future__ import annotations

import argparse
import base64
import json
import math
from pathlib import Path
import statistics
from time import perf_counter
from typing import Mapping, Sequence
from urllib import error as urlerror
from urllib import request as urlrequest

from .evidence_candidate_resolver import (
    CatalogueCandidate,
    normalize_evidence,
    resolve_candidates,
)
from .minicpm_structured_visual_probe_cli import DEFAULT_MODEL, DEFAULT_URL
from .visual_evaluation_harness import load_visual_manifest


TEXT_PROMPT = (
    "Transcribe only text that is actually visible on this single coin side. "
    "Return JSON only with exactly one key: visible_text. visible_text must be an "
    "array of at most eight short strings copied from the image. Do not identify "
    "the country, denomination, year, ruler, design, or coin type. Do not infer, "
    "translate, normalize, reconstruct, or correct uncertain text. If text is "
    "unclear, omit it."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coin-analyzer-text-first-visual-evidence-benchmark")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("source_report", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--case-id", action="append", dest="case_ids")
    parser.add_argument("--json", type=Path)
    return parser


def _clean_visible(raw: object) -> list[str]:
    if not isinstance(raw, list):
        raise ValueError("visible_text must be an array")
    visible: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise ValueError("visible_text entries must be strings")
        text = " ".join(item.strip().split())
        if text and text not in visible:
            visible.append(text)
    if len(visible) > 8:
        visible = visible[:8]
    return visible


def _transcribe(case, *, role: str, model: str, url: str, timeout: float) -> dict[str, object]:
    image = case.obverse if role == "obverse" else case.reverse
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "num_predict": 120},
        "messages": [{
            "role": "user",
            "content": TEXT_PROMPT,
            "images": [base64.b64encode(image.path.read_bytes()).decode("ascii")],
        }],
    }
    req = urlrequest.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = perf_counter()
    try:
        with urlrequest.urlopen(req, timeout=timeout) as response:
            envelope = json.loads(response.read().decode("utf-8"))
        message = envelope.get("message") if isinstance(envelope, Mapping) else None
        content = message.get("content") if isinstance(message, Mapping) else None
        if not isinstance(content, str):
            raise ValueError("Ollama response is missing message.content")
        decoded = json.loads(content)
        if not isinstance(decoded, Mapping) or set(decoded) != {"visible_text"}:
            raise ValueError("structured text result must contain only visible_text")
        visible_text = _clean_visible(decoded.get("visible_text"))
        return {
            "ok": True,
            "role": role,
            "latency_seconds": max(0.0, perf_counter() - started),
            "visible_text": visible_text,
            "prompt_eval_count": envelope.get("prompt_eval_count"),
            "eval_count": envelope.get("eval_count"),
        }
    except (TimeoutError, OSError, UnicodeError, json.JSONDecodeError, urlerror.URLError, ValueError) as exc:
        return {
            "ok": False,
            "role": role,
            "latency_seconds": max(0.0, perf_counter() - started),
            "error": exc.__class__.__name__,
            "message": str(exc),
            "visible_text": [],
        }


def _catalogue(manifest) -> tuple[CatalogueCandidate, ...]:
    return tuple(
        CatalogueCandidate(
            candidate_id=case.case_id,
            country=case.expected["country"],
            denomination=case.expected["denomination"],
            year=case.expected["year"],
            type_design=case.expected.get("type_design"),
            legends=(),
        )
        for case in manifest.cases
    )


def _source_rows(report: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    rows = report.get("rows")
    if not isinstance(rows, list):
        raise ValueError("source report rows must be a list")
    return {
        str(row.get("case_id")): row
        for row in rows
        if isinstance(row, Mapping) and row.get("case_id") is not None
    }


def _latency(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean_seconds": None, "median_seconds": None, "p95_seconds": None}
    ordered = sorted(values)
    return {
        "mean_seconds": statistics.fmean(ordered),
        "median_seconds": statistics.median(ordered),
        "p95_seconds": ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)],
    }


def _select_cases(manifest, case_ids: Sequence[str] | None):
    if not case_ids:
        return manifest.cases
    requested = list(dict.fromkeys(case_ids))
    by_id = {case.case_id: case for case in manifest.cases}
    missing = [case_id for case_id in requested if case_id not in by_id]
    if missing:
        raise SystemExit(f"unknown --case-id(s): {', '.join(missing)}")
    return tuple(by_id[case_id] for case_id in requested)


def _evidence_from_text(role: str, text: list[str]):
    joined = " | ".join(text)
    return normalize_evidence({
        "country": None,
        "denomination": None,
        "year": None,
        "visible_text": [joined] if joined else [],
    }, source=role)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")

    manifest = load_visual_manifest(args.manifest)
    source_report = json.loads(args.source_report.read_text(encoding="utf-8"))
    source_rows = _source_rows(source_report)
    candidates = _catalogue(manifest)
    cases = _select_cases(manifest, args.case_ids)

    rows: list[dict[str, object]] = []
    for case in cases:
        started = perf_counter()
        obverse = _transcribe(case, role="obverse", model=args.model, url=args.url, timeout=args.timeout)
        reverse = _transcribe(case, role="reverse", model=args.model, url=args.url, timeout=args.timeout)
        evidence = (
            _evidence_from_text("obverse_text", list(obverse.get("visible_text") or [])),
            _evidence_from_text("reverse_text", list(reverse.get("visible_text") or [])),
        )
        resolution = resolve_candidates(candidates, evidence, minimum_score=0.0, minimum_margin=0.5)
        accepted = resolution.accepted
        correct = accepted is not None and accepted.candidate_id == case.case_id
        baseline = source_rows.get(case.case_id, {})
        baseline_correct = bool(
            baseline.get("full_required_identity_exact")
            or baseline.get("full_identity_exact")
        )
        row = {
            "case_id": case.case_id,
            "baseline_correct": baseline_correct,
            "accepted_candidate_id": accepted.candidate_id if accepted else None,
            "correct": correct,
            "abstain": resolution.abstain,
            "reason": resolution.reason,
            "best_score": resolution.ranked[0].score if resolution.ranked else None,
            "runner_up_score": resolution.ranked[1].score if len(resolution.ranked) > 1 else None,
            "obverse": obverse,
            "reverse": reverse,
            "latency_seconds": max(0.0, perf_counter() - started),
        }
        rows.append(row)
        print(
            f"{case.case_id} | accepted={row['accepted_candidate_id']} | correct={correct} | "
            f"abstain={row['abstain']} | {row['latency_seconds']:.3f}s",
            flush=True,
        )

    total = len(rows)
    accepted_rows = [row for row in rows if row["accepted_candidate_id"] is not None]
    correct_count = sum(row["correct"] is True for row in rows)
    baseline_correct_count = sum(row["baseline_correct"] is True for row in rows)
    recovered = sum(row["correct"] is True and row["baseline_correct"] is not True for row in rows)
    regressed = sum(row["correct"] is not True and row["baseline_correct"] is True for row in rows)
    metrics = {
        "total_cases": total,
        "baseline_full_identity_accuracy": baseline_correct_count / total if total else None,
        "text_first_candidate_accuracy": correct_count / total if total else None,
        "text_first_coverage": len(accepted_rows) / total if total else None,
        "text_first_selective_accuracy": (
            sum(row["correct"] is True for row in accepted_rows) / len(accepted_rows)
            if accepted_rows else None
        ),
        "recovered_from_baseline": recovered,
        "regressed_from_baseline": regressed,
        "latency": _latency([float(row["latency_seconds"]) for row in rows]),
    }
    report = {
        "schema": "coin-analyzer-text-first-visual-evidence-benchmark-v1",
        "dataset_version": manifest.version,
        "source_model": source_report.get("model"),
        "transcription_model": args.model,
        "experiment": "text-only MiniCPM transcription + oracle catalogue",
        "rows": rows,
        "metrics": metrics,
    }
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Text-first visual evidence benchmark: {manifest.version}")
    print(f"Cases: {total}")
    print(f"Baseline full required identity: {metrics['baseline_full_identity_accuracy'] * 100:.1f}%")
    print(f"Text-first candidate accuracy: {metrics['text_first_candidate_accuracy'] * 100:.1f}%")
    print(f"Text-first coverage: {metrics['text_first_coverage'] * 100:.1f}%")
    sel = metrics['text_first_selective_accuracy']
    print(f"Text-first selective accuracy: {'n/a' if sel is None else f'{sel * 100:.1f}%'}")
    print(f"Recovered from baseline: {recovered}")
    print(f"Regressed from baseline: {regressed}")
    latency = metrics["latency"]
    print(
        f"Latency mean/median/p95: {latency['mean_seconds']:.3f}s / "
        f"{latency['median_seconds']:.3f}s / {latency['p95_seconds']:.3f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
