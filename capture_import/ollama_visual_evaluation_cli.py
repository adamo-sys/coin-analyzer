"""CLI for the benchmark-only local Ollama visual experiment."""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .ollama_visual_identity_provider import OllamaVisualIdentityProvider
from .visual_evaluation_harness import load_visual_manifest
from .visual_evaluation_runner import (
    render_visual_summary,
    run_visual_benchmark,
    write_visual_report,
)


def build_parser() -> argparse.ArgumentParser:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parser = argparse.ArgumentParser(prog="coin-analyzer-ollama-visual-v2")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--model", default="qwen2.5vl:7b")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--case-id",
        help="Run exactly one manifest case by id (benchmark-only diagnostic).",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=Path(f"artifacts/reruns/ollama-visual-{stamp}-report.json"),
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path(f"artifacts/reruns/ollama-visual-{stamp}-summary.txt"),
    )
    return parser


def _select_case(manifest, case_id: str | None):
    if case_id is None:
        return manifest
    matches = tuple(case for case in manifest.cases if case.case_id == case_id)
    if not matches:
        available = ", ".join(case.case_id for case in manifest.cases)
        raise SystemExit(f"unknown --case-id {case_id!r}; available: {available}")
    return replace(manifest, cases=matches)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = _select_case(load_visual_manifest(args.manifest), args.case_id)
    provider = OllamaVisualIdentityProvider(
        model=args.model,
        timeout_seconds=args.timeout,
    )
    report = run_visual_benchmark(manifest, provider)
    write_visual_report(report, json_path=args.json, summary_path=args.summary)
    print(render_visual_summary(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
