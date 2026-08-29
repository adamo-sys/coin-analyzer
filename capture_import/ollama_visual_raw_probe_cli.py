"""Free-form benchmark-only probe for local Ollama visual recognition.

This diagnostic intentionally bypasses the strict visual identity schema so we
can distinguish model capability from structured-output/prompt constraints. It
is not imported by production composition and does not modify OCR, UI, review,
or persistence behavior.
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from time import perf_counter
from typing import Sequence
from urllib import error as urlerror
from urllib import request as urlrequest

from .visual_evaluation_harness import load_visual_manifest


DEFAULT_MODEL = "qwen2.5vl:7b"
DEFAULT_URL = "http://127.0.0.1:11434/api/chat"
PROMPT = (
    "Identify the single physical coin shown in these two images. The first "
    "image is the obverse and the second is the reverse. State the most likely "
    "country or issuing authority, denomination, year/date, and type/design if "
    "recognizable. Briefly describe the visible evidence you used. If a field "
    "cannot be determined, say unknown. Do not use external tools or sources."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coin-analyzer-ollama-visual-raw-probe")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--url", default=DEFAULT_URL)
    return parser


def _select_case(manifest, case_id: str):
    for case in manifest.cases:
        if case.case_id == case_id:
            return case
    available = ", ".join(case.case_id for case in manifest.cases)
    raise SystemExit(f"unknown --case-id {case_id!r}; available: {available}")


def _probe(case, *, model: str, url: str, timeout: float) -> dict[str, object]:
    payload = {
        "model": model,
        "stream": False,
        "options": {"temperature": 0},
        "messages": [
            {
                "role": "user",
                "content": PROMPT,
                "images": [
                    base64.b64encode(case.obverse.path.read_bytes()).decode("ascii"),
                    base64.b64encode(case.reverse.path.read_bytes()).decode("ascii"),
                ],
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
    except (TimeoutError, OSError, UnicodeError, json.JSONDecodeError, urlerror.URLError) as exc:
        return {
            "ok": False,
            "case_id": case.case_id,
            "model": model,
            "latency_seconds": max(0.0, perf_counter() - started),
            "error": exc.__class__.__name__,
            "message": str(exc),
        }

    elapsed = max(0.0, perf_counter() - started)
    message = envelope.get("message") if isinstance(envelope, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    return {
        "ok": isinstance(content, str),
        "case_id": case.case_id,
        "model": model,
        "latency_seconds": elapsed,
        "prompt_eval_count": envelope.get("prompt_eval_count") if isinstance(envelope, dict) else None,
        "eval_count": envelope.get("eval_count") if isinstance(envelope, dict) else None,
        "response": content,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    manifest = load_visual_manifest(args.manifest)
    case = _select_case(manifest, args.case_id)
    result = _probe(
        case,
        model=str(args.model).strip(),
        url=str(args.url).strip(),
        timeout=float(args.timeout),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
