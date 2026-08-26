"""Benchmark-only two-side MiniCPM evidence probe with field provenance.

Each coin side is independently asked to extract only visibly supported evidence.
A deterministic merge then combines compatible evidence and records provenance.
Conflicting values remain unresolved rather than being guessed. This module is
experimental and is not imported by production recognition, OCR, UI, review, or
persistence code.
"""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from .minicpm_structured_visual_probe_cli import (
    DEFAULT_MODEL,
    DEFAULT_URL,
    _probe,
    _select_case,
)
from .visual_evaluation_harness import load_visual_manifest


FIELDS = ("country", "denomination", "year", "type_design")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coin-analyzer-minicpm-two-side-evidence-probe")
    parser.add_argument("manifest")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--url", default=DEFAULT_URL)
    return parser


def _normalized(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return " ".join(value.casefold().split())


def _merge_side_results(obverse: dict[str, object], reverse: dict[str, object]) -> dict[str, object]:
    merged: dict[str, object] = {}
    provenance: dict[str, list[str]] = {}
    conflicts: dict[str, dict[str, object]] = {}

    ob_result = obverse.get("result") if obverse.get("ok") is True else None
    rev_result = reverse.get("result") if reverse.get("ok") is True else None
    ob_result = ob_result if isinstance(ob_result, dict) else {}
    rev_result = rev_result if isinstance(rev_result, dict) else {}

    for field in FIELDS:
        ob_value = ob_result.get(field)
        rev_value = rev_result.get(field)
        ob_norm = _normalized(ob_value)
        rev_norm = _normalized(rev_value)
        if ob_norm and rev_norm and ob_norm != rev_norm:
            merged[field] = None
            provenance[field] = []
            conflicts[field] = {"obverse": ob_value, "reverse": rev_value}
        elif ob_norm and rev_norm:
            merged[field] = rev_value
            provenance[field] = ["obverse", "reverse"]
        elif ob_norm:
            merged[field] = ob_value
            provenance[field] = ["obverse"]
        elif rev_norm:
            merged[field] = rev_value
            provenance[field] = ["reverse"]
        else:
            merged[field] = None
            provenance[field] = []

    visible_text: list[dict[str, str]] = []
    for role, result in (("obverse", ob_result), ("reverse", rev_result)):
        values = result.get("visible_text")
        if isinstance(values, list):
            for value in values:
                if isinstance(value, str) and value.strip():
                    visible_text.append({"text": value.strip(), "source": role})

    required = (merged.get("country"), merged.get("denomination"), merged.get("year"))
    return {
        "identity": merged,
        "provenance": provenance,
        "visible_text": visible_text,
        "conflicts": conflicts,
        "abstain": bool(conflicts) or any(value is None for value in required),
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    manifest = load_visual_manifest(args.manifest)
    case = _select_case(manifest, args.case_id)
    common = {
        "model": str(args.model).strip(),
        "url": str(args.url).strip(),
        "timeout": float(args.timeout),
    }
    obverse = _probe(case, role="obverse", **common)
    reverse = _probe(case, role="reverse", **common)
    merged = _merge_side_results(obverse, reverse)
    output = {
        "ok": obverse.get("ok") is True and reverse.get("ok") is True,
        "schema": "coin-analyzer-minicpm-two-side-evidence-v1",
        "case_id": case.case_id,
        "model": common["model"],
        "sides": {"obverse": obverse, "reverse": reverse},
        "merged": merged,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
