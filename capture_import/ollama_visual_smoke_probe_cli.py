"""Minimal one-image benchmark-only smoke probe for local Ollama vision.

This diagnostic isolates image ingestion/runtime behavior from Coin Analyzer's
structured visual contract and from full coin-identification prompting. It is
not imported by production composition and does not modify OCR, UI, review, or
persistence behavior.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
from pathlib import Path
from time import perf_counter
from typing import Sequence
from urllib import error as urlerror
from urllib import request as urlrequest

from PIL import Image

from .visual_evaluation_harness import load_visual_manifest


DEFAULT_MODEL = "qwen2.5vl:7b"
DEFAULT_URL = "http://127.0.0.1:11434/api/chat"
PROMPT = "Reply with one short sentence describing what is visible in this image."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="coin-analyzer-ollama-visual-smoke-probe")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--role", choices=("obverse", "reverse"), default="obverse")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument(
        "--max-side",
        type=int,
        help="Downscale the selected image in memory so its longest side is at most this many pixels.",
    )
    return parser


def _select_case(manifest, case_id: str):
    for case in manifest.cases:
        if case.case_id == case_id:
            return case
    available = ", ".join(case.case_id for case in manifest.cases)
    raise SystemExit(f"unknown --case-id {case_id!r}; available: {available}")


def _image_bytes(path: Path, max_side: int | None) -> tuple[bytes, tuple[int, int], tuple[int, int]]:
    with Image.open(path) as source:
        original_size = source.size
        if max_side is None or max(source.size) <= max_side:
            return path.read_bytes(), original_size, original_size
        image = source.copy()
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.convert("RGB").save(output, format="JPEG", quality=90)
        return output.getvalue(), original_size, image.size


def _probe(
    case,
    *,
    role: str,
    model: str,
    url: str,
    timeout: float,
    max_side: int | None,
) -> dict[str, object]:
    image = case.obverse if role == "obverse" else case.reverse
    encoded_bytes, original_size, submitted_size = _image_bytes(image.path, max_side)
    payload = {
        "model": model,
        "stream": False,
        "options": {"temperature": 0, "num_predict": 48},
        "messages": [
            {
                "role": "user",
                "content": PROMPT,
                "images": [base64.b64encode(encoded_bytes).decode("ascii")],
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
            "role": role,
            "model": model,
            "original_size": original_size,
            "submitted_size": submitted_size,
            "max_side": max_side,
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
        "role": role,
        "model": model,
        "original_size": original_size,
        "submitted_size": submitted_size,
        "max_side": max_side,
        "latency_seconds": elapsed,
        "prompt_eval_count": envelope.get("prompt_eval_count") if isinstance(envelope, dict) else None,
        "eval_count": envelope.get("eval_count") if isinstance(envelope, dict) else None,
        "response": content,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive")
    if args.max_side is not None and args.max_side <= 0:
        raise SystemExit("--max-side must be positive")
    manifest = load_visual_manifest(args.manifest)
    case = _select_case(manifest, args.case_id)
    result = _probe(
        case,
        role=args.role,
        model=str(args.model).strip(),
        url=str(args.url).strip(),
        timeout=float(args.timeout),
        max_side=args.max_side,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
