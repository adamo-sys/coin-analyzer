"""Small benchmark-only local Ollama visual model shootout.

Runs the existing one-image smoke probe across a bounded set of manifest cases,
roles, and models. This is diagnostic only and does not affect production
recognition, OCR, UI, review, or persistence behavior.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .ollama_visual_smoke_probe_cli import _probe, _select_case
from .visual_evaluation_harness import load_visual_manifest


DEFAULT_MODELS = ("qwen2.5vl:7b", "llava:7b", "minicpm-v:8b")
DEFAULT_CASES = (
    "canada-25-cents-1967",
    "canada-5-cents-1964",
    "switzerland-2-francs-1980",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coin-analyzer-ollama-visual-shootout")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--model", action="append", dest="models")
    parser.add_argument("--case-id", action="append", dest="case_ids")
    parser.add_argument("--role", action="append", choices=("obverse", "reverse"), dest="roles")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--url", default="http://127.0.0.1:11434/api/chat")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    manifest = load_visual_manifest(args.manifest)
    models = tuple(args.models or DEFAULT_MODELS)
    case_ids = tuple(args.case_ids or DEFAULT_CASES)
    roles = tuple(args.roles or ("obverse", "reverse"))

    rows: list[dict[str, object]] = []
    for model in models:
        for case_id in case_ids:
            case = _select_case(manifest, case_id)
            for role in roles:
                result = _probe(
                    case,
                    role=role,
                    model=model,
                    url=str(args.url).strip(),
                    timeout=float(args.timeout),
                    max_side=None,
                    transform="original",
                )
                rows.append(result)
                status = "OK" if result.get("ok") is True else "FAIL"
                latency = float(result.get("latency_seconds") or 0.0)
                response = result.get("response")
                if isinstance(response, str):
                    response = " ".join(response.split())[:120]
                else:
                    response = result.get("error")
                print(f"{model} | {case_id} | {role} | {status} | {latency:.3f}s | {response}", flush=True)

    successes = [row for row in rows if row.get("ok") is True]
    failures = [row for row in rows if row.get("ok") is not True]
    summary = {
        "schema": "coin-analyzer-local-visual-model-shootout-v1",
        "models": list(models),
        "case_ids": list(case_ids),
        "roles": list(roles),
        "total_runs": len(rows),
        "successes": len(successes),
        "failures": len(failures),
        "rows": rows,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
