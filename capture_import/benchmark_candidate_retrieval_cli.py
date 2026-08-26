"""Benchmark a deterministic candidate-retrieval layer on saved multimodal evidence.

This experiment is offline: it does not invoke a VLM. It uses the frozen v2
manifest as an oracle catalogue and the saved structured multimodal evidence as
query evidence. The goal is to test whether narrowing the candidate set before
final resolution improves the accuracy/coverage/safety tradeoff.

Retrieval quality here is still benchmark-scaffold quality, not production
catalogue retrieval. The correct candidate is present in the oracle catalogue.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Mapping, Sequence

from .evidence_candidate_resolver import normalize_country, normalize_denomination, normalize_year
from .visual_evaluation_harness import load_visual_manifest


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="coin-analyzer-benchmark-candidate-retrieval")
    p.add_argument("manifest", type=Path)
    p.add_argument("evidence_report", type=Path)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--json", type=Path)
    return p


def _key(value: object) -> str:
    if value is None:
        return ""
    return " ".join(re.findall(r"[a-z0-9]+", str(value).casefold()))


def _tokens(value: object) -> set[str]:
    return set(_key(value).split())


def _row_evidence(row: Mapping[str, object]) -> dict[str, object]:
    texts: list[str] = []
    visuals: list[str] = []
    for role in ("obverse", "reverse"):
        side = row.get(role)
        result = side.get("result") if isinstance(side, Mapping) and isinstance(side.get("result"), Mapping) else {}
        visible = result.get("visible_text")
        if isinstance(visible, list):
            texts.extend(str(v) for v in visible if isinstance(v, str))
        for field in ("date_like", "denomination_mark"):
            value = result.get(field)
            if isinstance(value, str):
                texts.append(value)
        for field in ("script", "portrait", "construction", "shape"):
            value = result.get(field)
            if isinstance(value, str):
                visuals.append(value)
        motifs = result.get("motifs")
        if isinstance(motifs, list):
            visuals.extend(str(v) for v in motifs if isinstance(v, str))
    return {
        "text": " | ".join(texts),
        "visual": " | ".join(visuals),
    }


def _retrieval_score(case, evidence: Mapping[str, object]) -> tuple[float, list[str]]:
    text = _key(evidence.get("text"))
    text_tokens = set(text.split())
    visual_tokens = _tokens(evidence.get("visual"))
    score = 0.0
    reasons: list[str] = []

    country = normalize_country(case.expected["country"])
    denomination = normalize_denomination(case.expected["denomination"])
    year = normalize_year(case.expected["year"])
    design = case.expected.get("type_design")

    if country:
        ck = _key(country)
        if ck and ck in text:
            score += 4.0
            reasons.append("country_text")

    if denomination:
        dk = _key(denomination)
        dt = set(dk.split())
        if dk and dk in text:
            score += 4.0
            reasons.append("denomination_text")
        elif dt and dt <= text_tokens:
            score += 3.0
            reasons.append("denomination_tokens")
        elif dt:
            overlap = len(dt & text_tokens) / len(dt)
            if overlap > 0:
                score += 1.5 * overlap
                reasons.append("denomination_partial")

    if year:
        if year in text_tokens:
            score += 5.0
            reasons.append("year_text")
        else:
            # Weak near-year signal, useful for OCR/VLM digit confusion without
            # allowing it to dominate retrieval.
            four_digits = [t for t in text_tokens if len(t) == 4 and t.isdigit()]
            if four_digits:
                target = int(year)
                distance = min(abs(int(t) - target) for t in four_digits)
                if distance <= 1:
                    score += 1.5
                    reasons.append("near_year")

    if design:
        dt = _tokens(design)
        if dt and visual_tokens:
            overlap = len(dt & visual_tokens) / len(dt | visual_tokens)
            if overlap > 0:
                score += min(3.0, 1.0 + 4.0 * overlap)
                reasons.append("design_visual")

    difficulty = " ".join(case.difficulty).casefold()
    if "bimetallic" in difficulty and "bimetallic" in visual_tokens:
        score += 0.75
        reasons.append("construction")

    return score, reasons


def _resolve_shortlist(shortlist: list[tuple[float, object, list[str]]]) -> tuple[str | None, float, float, int]:
    if not shortlist:
        return None, 0.0, 0.0, 0
    best_score, best_case, best_reasons = shortlist[0]
    runner = shortlist[1][0] if len(shortlist) > 1 else 0.0
    margin = best_score - runner
    # Safety-biased resolver policy chosen from the prior Pareto sweep.
    accept = best_score >= 2.0 and margin >= 0.5 and len(best_reasons) >= 1
    return best_case.case_id if accept else None, best_score, margin, len(best_reasons)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.top_k < 1:
        raise SystemExit("--top-k must be >= 1")

    manifest = load_visual_manifest(args.manifest)
    report = json.loads(args.evidence_report.read_text(encoding="utf-8"))
    raw_rows = report.get("rows")
    if not isinstance(raw_rows, list):
        raise ValueError("evidence report rows must be a list")

    rows = []
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            continue
        case_id = str(raw.get("case_id"))
        evidence = _row_evidence(raw)
        ranked = []
        for candidate in manifest.cases:
            score, reasons = _retrieval_score(candidate, evidence)
            ranked.append((score, candidate, reasons))
        ranked.sort(key=lambda x: (-x[0], x[1].case_id))
        shortlist = ranked[: args.top_k]
        retrieved_ids = [c.case_id for _, c, _ in shortlist]
        retrieval_hit = case_id in retrieved_ids
        accepted, best_score, margin, match_count = _resolve_shortlist(shortlist)
        correct = accepted == case_id
        rows.append({
            "case_id": case_id,
            "retrieval_hit": retrieval_hit,
            "retrieved_candidate_ids": retrieved_ids,
            "accepted_candidate_id": accepted,
            "correct": correct,
            "abstain": accepted is None,
            "best_score": best_score,
            "margin": margin,
            "matched_dimensions": match_count,
            "top_ranked": [
                {"candidate_id": c.case_id, "score": score, "reasons": reasons}
                for score, c, reasons in shortlist
            ],
        })
        print(
            f"{case_id} | retrieval_hit={retrieval_hit} | top{args.top_k}={','.join(retrieved_ids)} | "
            f"accepted={accepted} | correct={correct} | score={best_score:.2f} margin={margin:.2f}",
            flush=True,
        )

    total = len(rows)
    hits = sum(r["retrieval_hit"] for r in rows)
    accepted_rows = [r for r in rows if r["accepted_candidate_id"] is not None]
    correct_count = sum(r["correct"] for r in rows)
    unsafe = sum(r["accepted_candidate_id"] is not None and not r["correct"] for r in rows)
    metrics = {
        "total_cases": total,
        "top_k": args.top_k,
        "retrieval_recall_at_k": hits / total if total else None,
        "candidate_accuracy": correct_count / total if total else None,
        "coverage": len(accepted_rows) / total if total else None,
        "selective_accuracy": (
            sum(r["correct"] for r in accepted_rows) / len(accepted_rows) if accepted_rows else None
        ),
        "unsafe_wrong_resolution_rate": unsafe / total if total else None,
    }
    output = {
        "schema": "coin-analyzer-benchmark-candidate-retrieval-v1",
        "dataset_version": manifest.version,
        "source_schema": report.get("schema"),
        "experiment": "offline multimodal evidence retrieval + safety-biased shortlist resolver",
        "rows": rows,
        "metrics": metrics,
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Benchmark candidate retrieval: {manifest.version}")
    print(f"Cases: {total}; top-k: {args.top_k}")
    print(f"Retrieval recall@{args.top_k}: {metrics['retrieval_recall_at_k'] * 100:.1f}%")
    print(f"Candidate accuracy: {metrics['candidate_accuracy'] * 100:.1f}%")
    print(f"Coverage: {metrics['coverage'] * 100:.1f}%")
    sel = metrics['selective_accuracy']
    print(f"Selective accuracy: {'n/a' if sel is None else f'{sel * 100:.1f}%'}")
    print(f"Unsafe wrong-resolution rate: {metrics['unsafe_wrong_resolution_rate'] * 100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
