"""CLI for the fixed prospective GPT-5.6 Terra visual experiment."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from inference_telemetry import get_default_telemetry_sink

from .visual_evaluation_harness import load_visual_manifest
from .visual_evaluation_runner import (
    render_visual_summary,
    run_visual_benchmark,
    write_visual_report,
)
from .visual_identity_provider import OpenAITerraVisualIdentityProvider


def build_parser() -> argparse.ArgumentParser:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parser = argparse.ArgumentParser(prog="coin-analyzer-terra-v2-prospective")
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--json",
        type=Path,
        default=Path(f"artifacts/reruns/terra-{stamp}-report.json"),
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path(f"artifacts/reruns/terra-{stamp}-summary.txt"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = load_visual_manifest(args.manifest)
    provider = OpenAITerraVisualIdentityProvider(
        telemetry_sink=get_default_telemetry_sink()
    )
    report = run_visual_benchmark(manifest, provider)
    write_visual_report(report, json_path=args.json, summary_path=args.summary)
    print(render_visual_summary(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
