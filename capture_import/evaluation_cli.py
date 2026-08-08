"""Command-line entry point for the versioned OCR evaluation harness."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .evaluation_harness import load_manifest, render_summary, run_benchmark, write_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coin-analyzer-evaluate")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--json", type=Path, default=Path("artifacts/benchmark-report.json"))
    parser.add_argument("--summary", type=Path, default=Path("artifacts/benchmark-summary.txt"))
    parser.add_argument("--exercise-persistence", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = load_manifest(args.manifest)
    report = run_benchmark(
        manifest, exercise_persistence=args.exercise_persistence
    )
    write_report(report, json_path=args.json, summary_path=args.summary)
    print(render_summary(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
