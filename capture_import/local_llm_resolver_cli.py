"""Command-line entry point for the standalone local LLM resolver experiment."""

from __future__ import annotations

import argparse
import json
import sys

from capture_import.local_llm_resolver import LocalLLMResolver, ResolverEvidence
from capture_import.local_llm_resolver_ollama import OllamaLocalResolverRuntime


def _csv_tuple(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the opt-in local Ollama resolver against bounded recognition evidence."
    )
    parser.add_argument("--model", default="qwen3:8b", help="Local Ollama model tag")
    parser.add_argument("--ocr-text", action="append", default=[], help="OCR text fragment; repeatable")
    parser.add_argument("--countries", default="", help="Comma-separated candidate countries")
    parser.add_argument("--denominations", default="", help="Comma-separated candidate denominations")
    parser.add_argument("--years", default="", help="Comma-separated candidate years")
    parser.add_argument("--candidate-ids", default="", help="Comma-separated candidate identity IDs")
    parser.add_argument("--timeout", type=float, default=30.0, help="Local Ollama request timeout in seconds")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    evidence = ResolverEvidence(
        ocr_text=tuple(args.ocr_text),
        candidate_countries=_csv_tuple(args.countries),
        candidate_denominations=_csv_tuple(args.denominations),
        candidate_years=_csv_tuple(args.years),
        candidate_ids=_csv_tuple(args.candidate_ids),
    )
    runtime = OllamaLocalResolverRuntime(model=args.model, timeout_seconds=args.timeout)
    resolver = LocalLLMResolver(runtime, enabled=True)

    try:
        result = resolver.resolve(evidence)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__, "message": str(exc)}, indent=2))
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "result": {
                    "country": result.country,
                    "denomination": result.denomination,
                    "year": result.year,
                    "candidate_id": result.candidate_id,
                    "confidence": result.confidence,
                    "reason": result.reason,
                    "abstain": result.abstain,
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
