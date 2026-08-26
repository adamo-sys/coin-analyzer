"""Benchmark-only structured MiniCPM visual probe.

This experiment tests whether the useful free-form MiniCPM visual signal can be
converted into bounded machine-readable evidence. It is not imported by
production composition and does not modify OCR, UI, review, or persistence.
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from time import perf_counter
from typing import Mapping, Sequence
from urllib import error as urlerror
from urllib import request as urlrequest

from .visual_evaluation_harness import load_visual_manifest


DEFAULT_MODEL = "minicpm-v:8b"
DEFAULT_URL = "http://127.0.0.1:11434/api/chat"
BASE_PROMPT = (
    "Extract evidence from this single coin side. Return JSON only with exactly "
    "these keys: country, denomination, year, type_design, visible_text, abstain. "
    "country, denomination, year, and type_design must be strings or null. "
    "visible_text must be an array of at most six short strings transcribed from "
    "the image. abstain must be boolean. Do not infer a field merely from the "
    "portrait, monarch, general coin style, or general numismatic knowledge. "
    "Only emit a field when this image itself visibly supports it. Do not invent "
    "or reconstruct text. Leave unsupported fields null. Set abstain true only "
    "when no identity or design field is visibly defensible. "
)
ROLE_PROMPTS = {
    "obverse": BASE_PROMPT + (
        "This is the obverse. Prioritize portrait/effigy identity, issuer or "
        "country only when supported by visible legend or unmistakable issuer "
        "symbolism, and any date only when numerals are visibly present. Do not "
        "supply denomination unless denomination text or an unmistakable "
        "denomination symbol is visibly present on this side. A monarch portrait "
        "alone does not establish country, denomination, or year."
    ),
    "reverse": BASE_PROMPT + (
        "This is the reverse. Prioritize denomination, visible date, issuer or "
        "country text/symbols, and reverse design. Country may be supplied when "
        "the country or issuing authority is visibly written or uniquely "
        "identified by explicit reverse-side evidence. Do not fill missing "
        "fields from assumptions about what usually appears on the other side."
    ),
}
EXPECTED_KEYS = {
    "country",
    "denomination",
    "year",
    "type_design",
    "visible_text",
    "abstain",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coin-analyzer-minicpm-structured-visual-probe")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--role", choices=("obverse", "reverse"), default="reverse")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--url", default=DEFAULT_URL)
    return parser


def _select_case(manifest, case_id: str):
    for case in manifest.cases:
        if case.case_id == case_id:
            return case
    available = ", ".join(case.case_id for case in manifest.cases)
    raise SystemExit(f"unknown --case-id {case_id!r}; available: {available}")


def _nullable_text(value: object, *, field: str, limit: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(f"{field} must be null or a non-empty string <= {limit} chars")
    return value.strip()


def _validated_result(raw: object) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        raise ValueError("structured result must be a JSON object")
    unknown = set(raw) - EXPECTED_KEYS
    if unknown:
        raise ValueError(f"structured result contains unknown keys: {sorted(unknown)}")

    raw_abstain = raw.get("abstain", False)
    if not isinstance(raw_abstain, bool):
        raise ValueError("abstain must be boolean when present")
    abstain = raw_abstain

    country = _nullable_text(raw.get("country"), field="country", limit=48)
    denomination = _nullable_text(raw.get("denomination"), field="denomination", limit=40)
    year = _nullable_text(raw.get("year"), field="year", limit=16)
    type_design = _nullable_text(raw.get("type_design"), field="type_design", limit=80)

    visible = raw.get("visible_text", [])
    if not isinstance(visible, list) or len(visible) > 6:
        raise ValueError("visible_text must be an array of at most six strings")
    visible_text: list[str] = []
    for item in visible:
        if not isinstance(item, str) or not item.strip() or len(item.strip()) > 48:
            raise ValueError("visible_text items must be non-empty strings <= 48 chars")
        text = item.strip()
        if text in visible_text:
            raise ValueError("visible_text must not contain duplicates")
        visible_text.append(text)

    identity = (country, denomination, year, type_design)
    if abstain or all(value is None for value in identity):
        abstain = True
        country = denomination = year = type_design = None

    return {
        "country": country,
        "denomination": denomination,
        "year": year,
        "type_design": type_design,
        "visible_text": visible_text,
        "abstain": abstain,
    }


def _probe(case, *, role: str, model: str, url: str, timeout: float) -> dict[str, object]:
    if role not in ROLE_PROMPTS:
        raise ValueError(f"unsupported role: {role}")
    image = case.obverse if role == "obverse" else case.reverse
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "num_predict": 180},
        "messages": [
            {
                "role": "user",
                "content": ROLE_PROMPTS[role],
                "images": [base64.b64encode(image.path.read_bytes()).decode("ascii")],
            }
        ],
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
        result = _validated_result(json.loads(content))
    except (TimeoutError, OSError, UnicodeError, json.JSONDecodeError, urlerror.URLError, ValueError) as exc:
        return {
            "ok": False,
            "case_id": case.case_id,
            "role": role,
            "model": model,
            "latency_seconds": max(0.0, perf_counter() - started),
            "error": exc.__class__.__name__,
            "message": str(exc),
        }

    return {
        "ok": True,
        "case_id": case.case_id,
        "role": role,
        "model": model,
        "latency_seconds": max(0.0, perf_counter() - started),
        "prompt_eval_count": envelope.get("prompt_eval_count"),
        "eval_count": envelope.get("eval_count"),
        "result": result,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    manifest = load_visual_manifest(args.manifest)
    case = _select_case(manifest, args.case_id)
    result = _probe(
        case,
        role=args.role,
        model=str(args.model).strip(),
        url=str(args.url).strip(),
        timeout=float(args.timeout),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
