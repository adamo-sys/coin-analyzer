"""Benchmark structured multimodal visual evidence against Benchmark v2.

This experiment sits between open-world identity prediction and text-only
transcription. MiniCPM extracts bounded, non-authoritative visual evidence from
each side (visible text plus script, portrait, motifs, construction, geometry,
and date/denomination-like marks). A deterministic oracle-catalogue scorer then
ranks Benchmark v2 candidates. Ground-truth identities are never supplied to
the model. Retrieval quality is not evaluated because the v2 manifest itself is
used as the candidate catalogue.

Benchmark-only: no production recognition, UI, review, or persistence changes.
"""

from __future__ import annotations

import argparse
import base64
import json
import math
from pathlib import Path
import re
import statistics
from time import perf_counter
from typing import Mapping, Sequence
from urllib import error as urlerror
from urllib import request as urlrequest

from .evidence_candidate_resolver import normalize_country, normalize_denomination, normalize_year
from .minicpm_structured_visual_probe_cli import DEFAULT_MODEL, DEFAULT_URL
from .visual_evaluation_harness import load_visual_manifest


PROMPT = (
    "Extract only visually defensible evidence from this single coin side. "
    "Do not identify the coin and do not guess country, denomination, or year. "
    "Return JSON only with exactly these keys: visible_text, script, portrait, "
    "motifs, construction, shape, date_like, denomination_mark. "
    "visible_text and motifs must be arrays of at most eight short strings. "
    "script, portrait, construction, shape, date_like, denomination_mark must "
    "be strings or null. Copy visible text conservatively; do not reconstruct "
    "unclear legends. portrait should describe only the visible person/effigy "
    "when defensible. motifs should name visible objects such as wreath, beaver, "
    "lotus, ship, building, shield, eagle, or figures. construction may describe "
    "bimetallic or single-metal appearance. date_like may contain only numerals "
    "that visibly resemble a date. denomination_mark may contain only a visible "
    "numeric/unit mark such as 5 CENTS, 2 Fr., 10 PISO, or Rp 100."
)
EXPECTED_KEYS = {
    "visible_text", "script", "portrait", "motifs", "construction", "shape",
    "date_like", "denomination_mark",
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="coin-analyzer-structured-multimodal-evidence-benchmark")
    p.add_argument("manifest", type=Path)
    p.add_argument("source_report", type=Path)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--timeout", type=float, default=90.0)
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--case-id", action="append", dest="case_ids")
    p.add_argument("--json", type=Path)
    return p


def _clean_text(value: object, *, limit: int = 96) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("structured scalar evidence must be string or null")
    text = " ".join(value.strip().split())
    if not text:
        return None
    return text[:limit]


def _clean_list(value: object, *, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("structured list evidence must be an array")
    out: list[str] = []
    for item in value:
        text = _clean_text(item, limit=64)
        if text and text.casefold() not in {x.casefold() for x in out}:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _validated(raw: object) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        raise ValueError("structured result must be a JSON object")
    unknown = set(raw) - EXPECTED_KEYS
    if unknown:
        raise ValueError(f"unknown structured evidence keys: {sorted(unknown)}")
    return {
        "visible_text": _clean_list(raw.get("visible_text", [])),
        "script": _clean_text(raw.get("script")),
        "portrait": _clean_text(raw.get("portrait")),
        "motifs": _clean_list(raw.get("motifs", [])),
        "construction": _clean_text(raw.get("construction")),
        "shape": _clean_text(raw.get("shape")),
        "date_like": _clean_text(raw.get("date_like")),
        "denomination_mark": _clean_text(raw.get("denomination_mark")),
    }


def _extract(case, *, role: str, model: str, url: str, timeout: float) -> dict[str, object]:
    image = case.obverse if role == "obverse" else case.reverse
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "num_predict": 220},
        "messages": [{
            "role": "user",
            "content": PROMPT,
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
        result = _validated(json.loads(content))
        return {
            "ok": True,
            "role": role,
            "latency_seconds": max(0.0, perf_counter() - started),
            "result": result,
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
            "result": {},
        }


def _key(value: object) -> str:
    if value is None:
        return ""
    return " ".join(re.findall(r"[a-z0-9]+", str(value).casefold()))


def _token_overlap(a: object, b: object) -> float:
    aa = set(_key(a).split())
    bb = set(_key(b).split())
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / len(aa | bb)


def _all_text(evidence: Sequence[Mapping[str, object]]) -> str:
    chunks: list[str] = []
    for side in evidence:
        result = side.get("result") if isinstance(side.get("result"), Mapping) else {}
        for value in result.get("visible_text", []) if isinstance(result.get("visible_text"), list) else []:
            chunks.append(str(value))
        for field in ("date_like", "denomination_mark"):
            value = result.get(field)
            if isinstance(value, str) and value.strip():
                chunks.append(value)
    return " | ".join(chunks)


def _candidate_score(case, evidence: Sequence[Mapping[str, object]]) -> tuple[float, dict[str, object]]:
    text = _all_text(evidence)
    text_key = _key(text)
    country = normalize_country(case.expected["country"])
    denomination = normalize_denomination(case.expected["denomination"])
    year = normalize_year(case.expected["year"])

    score = 0.0
    matched: list[str] = []
    if country and _key(country) and _key(country) in text_key:
        score += 3.0
        matched.append("country_text")
    if denomination:
        denom_key = _key(denomination)
        denom_tokens = denom_key.split()
        if denom_key and denom_key in text_key:
            score += 3.0
            matched.append("denomination_text")
        elif denom_tokens and all(token in text_key.split() for token in denom_tokens):
            score += 2.0
            matched.append("denomination_tokens")
    if year and year in text_key.split():
        score += 4.0
        matched.append("year_text")

    expected_design = case.expected.get("type_design")
    visual_chunks: list[str] = []
    for side in evidence:
        result = side.get("result") if isinstance(side.get("result"), Mapping) else {}
        for field in ("portrait", "script", "construction", "shape"):
            value = result.get(field)
            if isinstance(value, str):
                visual_chunks.append(value)
        motifs = result.get("motifs")
        if isinstance(motifs, list):
            visual_chunks.extend(str(v) for v in motifs)
    visual_summary = " | ".join(visual_chunks)
    design_overlap = _token_overlap(expected_design, visual_summary)
    if design_overlap > 0:
        score += min(3.0, 1.0 + 4.0 * design_overlap)
        matched.append("design_visual")

    # Weak structural hints only; never enough to accept alone.
    difficulty = " ".join(case.difficulty).casefold()
    if "bimetallic" in difficulty and "bimetallic" in _key(visual_summary):
        score += 0.75
        matched.append("construction")

    return score, {
        "matched": matched,
        "text": text,
        "visual_summary": visual_summary,
        "design_overlap": design_overlap,
    }


def _select_cases(manifest, case_ids: Sequence[str] | None):
    if not case_ids:
        return manifest.cases
    requested = list(dict.fromkeys(case_ids))
    by_id = {case.case_id: case for case in manifest.cases}
    missing = [case_id for case_id in requested if case_id not in by_id]
    if missing:
        raise SystemExit(f"unknown --case-id(s): {', '.join(missing)}")
    return tuple(by_id[cid] for cid in requested)


def _latency(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean_seconds": None, "median_seconds": None, "p95_seconds": None}
    ordered = sorted(values)
    return {
        "mean_seconds": statistics.fmean(ordered),
        "median_seconds": statistics.median(ordered),
        "p95_seconds": ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)],
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    manifest = load_visual_manifest(args.manifest)
    source = json.loads(args.source_report.read_text(encoding="utf-8"))
    source_rows = {
        str(r.get("case_id")): r for r in source.get("rows", []) if isinstance(r, Mapping)
    }
    cases = _select_cases(manifest, args.case_ids)

    rows: list[dict[str, object]] = []
    for target in cases:
        started = perf_counter()
        obverse = _extract(target, role="obverse", model=args.model, url=args.url, timeout=args.timeout)
        reverse = _extract(target, role="reverse", model=args.model, url=args.url, timeout=args.timeout)
        evidence = (obverse, reverse)
        ranked = []
        for candidate in manifest.cases:
            score, detail = _candidate_score(candidate, evidence)
            ranked.append((score, candidate.case_id, detail))
        ranked.sort(key=lambda row: (-row[0], row[1]))
        best_score, best_id, best_detail = ranked[0]
        runner_score = ranked[1][0] if len(ranked) > 1 else float("-inf")
        margin = best_score - runner_score
        # Require multiple independent evidence dimensions or one extremely strong
        # identity combination. This is intentionally safety-biased.
        accept = best_score >= 5.0 and margin >= 1.0 and len(best_detail["matched"]) >= 2
        accepted_id = best_id if accept else None
        correct = accepted_id == target.case_id
        baseline = source_rows.get(target.case_id, {})
        baseline_correct = bool(
            baseline.get("full_required_identity_exact") or baseline.get("full_identity_exact")
        )
        row = {
            "case_id": target.case_id,
            "baseline_correct": baseline_correct,
            "accepted_candidate_id": accepted_id,
            "correct": correct,
            "abstain": not accept,
            "best_score": best_score,
            "runner_up_score": runner_score,
            "margin": margin,
            "best_detail": best_detail,
            "obverse": obverse,
            "reverse": reverse,
            "latency_seconds": max(0.0, perf_counter() - started),
        }
        rows.append(row)
        print(
            f"{target.case_id} | accepted={accepted_id} | correct={correct} | "
            f"score={best_score:.2f} margin={margin:.2f} | {row['latency_seconds']:.3f}s",
            flush=True,
        )

    total = len(rows)
    accepted = [r for r in rows if r["accepted_candidate_id"] is not None]
    correct = sum(r["correct"] is True for r in rows)
    baseline_correct = sum(r["baseline_correct"] is True for r in rows)
    unsafe = sum(r["accepted_candidate_id"] is not None and r["correct"] is not True for r in rows)
    recovered = sum(r["correct"] is True and r["baseline_correct"] is not True for r in rows)
    regressed = sum(r["correct"] is not True and r["baseline_correct"] is True for r in rows)
    metrics = {
        "total_cases": total,
        "baseline_full_identity_accuracy": baseline_correct / total if total else None,
        "multimodal_candidate_accuracy": correct / total if total else None,
        "coverage": len(accepted) / total if total else None,
        "selective_accuracy": (
            sum(r["correct"] is True for r in accepted) / len(accepted) if accepted else None
        ),
        "unsafe_wrong_resolution_rate": unsafe / total if total else None,
        "recovered_from_baseline": recovered,
        "regressed_from_baseline": regressed,
        "latency": _latency([float(r["latency_seconds"]) for r in rows]),
    }
    report = {
        "schema": "coin-analyzer-structured-multimodal-evidence-benchmark-v1",
        "dataset_version": manifest.version,
        "source_model": source.get("model"),
        "evidence_model": args.model,
        "experiment": "structured multimodal evidence + oracle catalogue",
        "rows": rows,
        "metrics": metrics,
    }
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Structured multimodal evidence benchmark: {manifest.version}")
    print(f"Cases: {total}")
    print(f"Baseline full required identity: {metrics['baseline_full_identity_accuracy'] * 100:.1f}%")
    print(f"Multimodal candidate accuracy: {metrics['multimodal_candidate_accuracy'] * 100:.1f}%")
    print(f"Coverage: {metrics['coverage'] * 100:.1f}%")
    sel = metrics["selective_accuracy"]
    print(f"Selective accuracy: {'n/a' if sel is None else f'{sel * 100:.1f}%'}")
    print(f"Unsafe wrong-resolution rate: {metrics['unsafe_wrong_resolution_rate'] * 100:.1f}%")
    print(f"Recovered from baseline: {recovered}")
    print(f"Regressed from baseline: {regressed}")
    lat = metrics["latency"]
    print(
        f"Latency mean/median/p95: {lat['mean_seconds']:.3f}s / "
        f"{lat['median_seconds']:.3f}s / {lat['p95_seconds']:.3f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
