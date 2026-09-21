"""Offline quality report for grounded benchmark JSON; makes no provider calls."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Sequence

from .observation_quality_evaluation import (
    compare_view_pairs,
    evaluate_execution_accounting,
    evaluate_secondary_view_policy,
    evaluate_view_quality,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coin-analyzer-observation-quality")
    parser.add_argument("report", type=Path)
    parser.add_argument("--json", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = json.loads(args.report.read_text(encoding="utf-8"))
    provenance = tuple(
        item
        for row in source.get("rows", ())
        for item in row.get("view_provenance", ())
    )
    quality = evaluate_view_quality(provenance)
    pairs = compare_view_pairs(provenance)
    accounting = evaluate_execution_accounting(tuple(source.get("rows", ())))
    policy = evaluate_secondary_view_policy(provenance)

    result = {
        "schema": "coin-analyzer-observation-quality-v1",
        "source_schema": source.get("schema"),
        "views": [asdict(item) for item in quality],
        "pairs": [asdict(item) for item in pairs],
        "execution": asdict(accounting),
        "adaptive_policy": asdict(policy),
    }
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    for item in quality:
        print(
            f"{item.view}: observations={item.observations} "
            f"with_text={item.observations_with_text} "
            f"unique_text={item.unique_text_items} "
            f"dates={item.date_yield} denominations={item.denomination_yield} "
            f"input_tokens={item.input_tokens}"
        )
    print(
        f"execution: attempted={accounting.attempted_calls} "
        f"successful={accounting.successful_calls} failed={accounting.failed_calls} "
        f"maximum={accounting.maximum_two_view_calls} "
        f"avoided={accounting.avoided_calls} "
        f"input_tokens={accounting.input_tokens} "
        f"output_tokens={accounting.output_tokens}"
    )
    print(
        f"adaptive_policy: paired_roles={policy.paired_roles} "
        f"requested={policy.secondary_requested} avoided={policy.secondary_avoided} "
        f"useful={policy.useful_secondary} "
        f"useful_rate={policy.useful_secondary_rate} "
        f"secondary_input_tokens={policy.secondary_input_tokens} "
        f"useful_secondary_input_tokens={policy.useful_secondary_input_tokens}"
    )
    incremental = sum(len(item.incremental_comparison_text) for item in pairs)
    comparison_tokens = sum(item.comparison_input_tokens for item in pairs)
    print(
        f"comparison_incremental_text={incremental} "
        f"comparison_input_tokens={comparison_tokens}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
