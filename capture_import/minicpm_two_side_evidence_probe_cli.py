"""Benchmark-only two-side MiniCPM evidence probe with field provenance.

Each coin side is independently asked to extract only visibly supported evidence.
A deterministic merge then combines compatible evidence and records provenance.
For required identity fields, explicit visible-text support outranks unsupported
model inference. Optional type/design disagreement never forces full-identity
abstention. This module is experimental and is not imported by production
recognition, OCR, UI, review, or persistence code.
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Sequence

from .minicpm_structured_visual_probe_cli import (
    DEFAULT_MODEL,
    DEFAULT_URL,
    _probe,
    _select_case,
)
from .visual_evaluation_harness import load_visual_manifest


FIELDS = ("country", "denomination", "year", "type_design")
REQUIRED_FIELDS = ("country", "denomination", "year")
ISSUER_ALIASES = {
    "switzerland": ("helvetia",),
}


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


def _searchable(value: object) -> str:
    text = _normalized(value) or ""
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _visible_text(result: dict[str, object]) -> list[str]:
    values = result.get("visible_text")
    if not isinstance(values, list):
        return []
    return [value.strip() for value in values if isinstance(value, str) and value.strip()]


def _explicitly_supported(field: str, value: object, result: dict[str, object]) -> bool:
    """Return whether the side's transcribed text explicitly supports a field."""
    if field == "type_design":
        return False
    needle = _searchable(value)
    if not needle:
        return False
    haystack = " ".join(_searchable(item) for item in _visible_text(result))
    if needle in haystack:
        return True
    needle_tokens = needle.split()
    haystack_tokens = haystack.split()
    if needle_tokens and all(token in haystack_tokens for token in needle_tokens):
        return True
    if field == "country":
        for alias in ISSUER_ALIASES.get(needle, ()):
            searchable_alias = _searchable(alias)
            if searchable_alias and searchable_alias in haystack:
                return True
    return False


def _merge_side_results(obverse: dict[str, object], reverse: dict[str, object]) -> dict[str, object]:
    merged: dict[str, object] = {field: None for field in FIELDS}
    provenance: dict[str, list[str]] = {field: [] for field in FIELDS}
    conflicts: dict[str, dict[str, object]] = {}
    rejected_weaker_evidence: dict[str, dict[str, object]] = {}

    ob_result = obverse.get("result") if obverse.get("ok") is True else None
    rev_result = reverse.get("result") if reverse.get("ok") is True else None
    ob_result = ob_result if isinstance(ob_result, dict) else {}
    rev_result = rev_result if isinstance(rev_result, dict) else {}

    for field in FIELDS:
        ob_value = ob_result.get(field)
        rev_value = rev_result.get(field)
        ob_norm = _normalized(ob_value)
        rev_norm = _normalized(rev_value)
        ob_explicit = _explicitly_supported(field, ob_value, ob_result)
        rev_explicit = _explicitly_supported(field, rev_value, rev_result)

        if ob_norm and rev_norm and ob_norm != rev_norm:
            if field in REQUIRED_FIELDS and ob_explicit != rev_explicit:
                winner_role = "obverse" if ob_explicit else "reverse"
                winner_value = ob_value if ob_explicit else rev_value
                loser_role = "reverse" if ob_explicit else "obverse"
                loser_value = rev_value if ob_explicit else ob_value
                merged[field] = winner_value
                provenance[field] = [winner_role]
                rejected_weaker_evidence[field] = {
                    "accepted": {"source": winner_role, "value": winner_value, "explicit_visible_text": True},
                    "rejected": {"source": loser_role, "value": loser_value, "explicit_visible_text": False},
                }
            else:
                conflicts[field] = {
                    "obverse": ob_value,
                    "reverse": rev_value,
                    "obverse_explicit_visible_text": ob_explicit,
                    "reverse_explicit_visible_text": rev_explicit,
                }
        elif ob_norm and rev_norm:
            merged[field] = rev_value
            provenance[field] = ["obverse", "reverse"]
        elif ob_norm:
            merged[field] = ob_value
            provenance[field] = ["obverse"]
        elif rev_norm:
            merged[field] = rev_value
            provenance[field] = ["reverse"]

    # Defensive invariant: identity/provenance always expose every contract field.
    merged = {field: merged.get(field) for field in FIELDS}
    provenance = {field: list(provenance.get(field, [])) for field in FIELDS}

    visible_text: list[dict[str, str]] = []
    for role, result in (("obverse", ob_result), ("reverse", rev_result)):
        for value in _visible_text(result):
            visible_text.append({"text": value, "source": role})

    required_missing = any(merged.get(field) is None for field in REQUIRED_FIELDS)
    required_conflicts = {field: value for field, value in conflicts.items() if field in REQUIRED_FIELDS}
    return {
        "identity": merged,
        "provenance": provenance,
        "visible_text": visible_text,
        "conflicts": conflicts,
        "rejected_weaker_evidence": rejected_weaker_evidence,
        "abstain": bool(required_conflicts) or required_missing,
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
