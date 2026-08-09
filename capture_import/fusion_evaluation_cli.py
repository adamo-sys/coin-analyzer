"""CLI for the archived-Terra plus production-Tesseract fusion experiment."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .fusion_evaluation_runner import (
    load_archived_visual_report,
    render_fusion_summary,
    run_fusion_benchmark,
    write_fusion_report,
)
from .visual_evaluation_harness import load_visual_manifest


def build_parser() -> argparse.ArgumentParser:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parser = argparse.ArgumentParser(prog="coin-analyzer-visual-ocr-fusion")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--visual-report", type=Path, required=True)
    parser.add_argument("--json", type=Path, default=Path(f"artifacts/reruns/fusion-{stamp}-report.json"))
    parser.add_argument("--summary", type=Path, default=Path(f"artifacts/reruns/fusion-{stamp}-summary.txt"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = load_visual_manifest(args.manifest)
    visual_report = load_archived_visual_report(args.visual_report, manifest)
    report = run_fusion_benchmark(manifest, visual_report)
    write_fusion_report(report, json_path=args.json, summary_path=args.summary)
    print(render_fusion_summary(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
