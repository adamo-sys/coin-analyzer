"""Diagnostic command-line entry point for opt-in OCR imports.

This module is intentionally standalone. Importing it does not register OCR
with the desktop application or alter the default image-processing pipeline.

Example::

    python -m capture_import.workflow_ocr_cli `
        input.ca-package `
        --workspace .diagnostics/ocr-import `
        --raw-text "CANADA 1967"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence, TextIO

from .workflow_execution import ImportWorkflow
from .workflow_models import ImportConfiguration, ImportRequest
from .workflow_ocr_runtime import build_legacy_ocr_pipeline


def build_parser() -> argparse.ArgumentParser:
    """Build the OCR diagnostic CLI argument parser."""

    parser = argparse.ArgumentParser(
        prog="coin-analyzer-ocr-import",
        description=(
            "Run the explicit OCR-enabled capture-package pipeline and emit "
            "a deterministic JSON diagnostic summary."
        ),
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Path to a .ca-package capture package.",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        required=True,
        help="Directory used for generated workflow artifacts.",
    )
    parser.add_argument(
        "--collection-id",
        default="diagnostic-collection",
        help=(
            "Logical collection identifier passed to the import request. "
            "No collection persistence is performed."
        ),
    )
    parser.add_argument(
        "--raw-text",
        default=None,
        help=(
            "Optional deterministic OCR text applied to every processed "
            "image. When omitted, the optional local OCR runtime may be used."
        ),
    )
    return parser


def _raw_text_resolver(
    raw_text: str | None,
):
    if raw_text is None:
        return None

    def resolve(
        _source_coin_id: str,
        _image_role: str,
        _artifact_key: str,
        _image_bytes: bytes,
    ) -> str:
        return raw_text

    return resolve


def _build_summary(
    *,
    source: Path,
    workspace: Path,
    collection_id: str,
    pipeline_stage_ids: tuple[str, ...],
    outcome,
) -> dict[str, object]:
    """Build a bounded JSON-safe diagnostic summary."""

    metadata = outcome.metadata

    return {
        "source": str(source.resolve()),
        "workspace": str(workspace.resolve()),
        "collection_id": collection_id,
        "pipeline_stage_ids": list(pipeline_stage_ids),
        "artifact_keys": sorted(outcome.artifacts),
        "artifact_count": len(outcome.artifacts),
        "ocr": {
            "provider_available": metadata.get(
                "ocr_provider_available",
                False,
            ),
            "provider_id": metadata.get("ocr_provider_id"),
            "processed_image_count": metadata.get(
                "ocr_processed_image_count",
                0,
            ),
            "review_required": metadata.get(
                "ocr_review_required",
                False,
            ),
            "reports": metadata.get("ocr_reports", []),
        },
    }


def run(
    args: argparse.Namespace,
    *,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Execute one diagnostic OCR import."""

    source = args.source.expanduser().resolve()
    workspace = args.workspace.expanduser().resolve()

    if not source.is_file():
        print(
            f"Source package does not exist or is not a file: {source}",
            file=stderr,
        )
        return 2

    workspace.mkdir(parents=True, exist_ok=True)

    resolver = _raw_text_resolver(args.raw_text)
    pipeline = build_legacy_ocr_pipeline(
        raw_text_resolver=resolver,
    )

    request = ImportRequest(
        source=source,
        collection_id=args.collection_id,
        configuration=ImportConfiguration(),
    )

    try:
        outcome = ImportWorkflow(pipeline).execute(
            request,
            workspace,
        )
    except Exception as exc:
        print(
            f"OCR diagnostic import failed: {type(exc).__name__}: {exc}",
            file=stderr,
        )
        return 1

    summary = _build_summary(
        source=source,
        workspace=workspace,
        collection_id=args.collection_id,
        pipeline_stage_ids=pipeline.stage_ids,
        outcome=outcome,
    )

    json.dump(
        summary,
        stdout,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    stdout.write("\n")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)
    return run(
        args,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main())