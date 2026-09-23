"""Observation-only A/B experiment support for Recognition30.

This module deliberately stops before retrieval, matching, verification, and
ground-truth evaluation.  A dry run only constructs deterministic request
metadata and evidence views; it never constructs a provider.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Literal, cast

from .openai_grounded_visual_observation_provider import (
    OPENAI_GROUNDED_OBSERVATION_PROMPT,
    OpenAIGroundedVisualObservationProvider,
)
from .grounded_visual_observation import (
    GroundedVisualObservationContractError,
    GroundedVisualObservationImage,
    GroundedVisualObservationRequest,
)
from .recognition30_grounded_benchmark_cli import (
    _dataset_fingerprint,
    _load_dataset,
    _localized_evidence_views,
)


EXPERIMENT_5_CASE_IDS = (
    "CA-R30-005",
    "CA-R30-007",
    "CA-R30-009",
    "CA-R30-011",
    "CA-R30-013",
    "CA-R30-019",
    "CA-R30-023",
    "CA-R30-030",
)

TREATMENT_PROMPT_DELTA = (
    "After transcribing visible_text, make two separate literal-evidence "
    "checks. For denomination_mark, return one complete, visibly readable "
    "numeral-plus-unit or numeral-plus-currency-mark expression when present; "
    "do not return a bare numeral, infer a missing unit, translate, or combine "
    "fragments from different locations. Otherwise return null. For date_like, "
    "return one complete, visibly readable date-like numeral only when all "
    "visible digits of that numeral are readable; do not return a truncated "
    "numeral or complete missing digits. Otherwise return null. "
)


@dataclass(frozen=True, slots=True)
class ExperimentCase:
    case_id: str
    obverse: Path
    reverse: Path


@dataclass(frozen=True, slots=True)
class PlannedObservationRequest:
    sequence: int
    arm: Literal["control", "treatment"]
    case_id: str
    role: Literal["obverse", "reverse"]
    view: Literal["full_face", "rim"]
    media_type: str
    image_data: bytes
    image_sha256: str

    def public_record(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "arm": self.arm,
            "case_id": self.case_id,
            "role": self.role,
            "view": self.view,
            "media_type": self.media_type,
            "image_sha256": self.image_sha256,
        }


@dataclass(frozen=True, slots=True)
class ExperimentManifest:
    dataset_fingerprint: str
    requests: tuple[PlannedObservationRequest, ...]
    case_ids: tuple[str, ...] = ()

    def public_record(self) -> dict[str, object]:
        return {
            "schema": "coin-analyzer-recognition30-observation-experiment-v1",
            "dataset_fingerprint_scheme": "recognition30-dataset-fingerprint-v1",
            "dataset_fingerprint": self.dataset_fingerprint,
            "case_ids": list(self.case_ids),
            "case_selection_sha256": _sha256_text("\n".join(self.case_ids)),
            "planned_call_count": len(self.requests),
            "control_prompt_sha256": _sha256_text(OPENAI_GROUNDED_OBSERVATION_PROMPT),
            "treatment_prompt_sha256": _sha256_text(treatment_prompt()),
            "requests": [request.public_record() for request in self.requests],
        }


def treatment_prompt() -> str:
    """Return the bounded Experiment 5 treatment without changing production."""

    return OPENAI_GROUNDED_OBSERVATION_PROMPT + " " + TREATMENT_PROMPT_DELTA


def load_cases(dataset_root: Path) -> tuple[ExperimentCase, ...]:
    """Load only the eight pre-registered Experiment 5 image pairs."""

    dataset = _load_dataset(dataset_root)
    by_id = {case.case_id: case for case in dataset.cases}
    missing = tuple(case_id for case_id in EXPERIMENT_5_CASE_IDS if case_id not in by_id)
    if missing:
        raise ValueError(f"Experiment 5 dataset is missing cases: {', '.join(missing)}")
    return tuple(
        ExperimentCase(
            case_id=case_id,
            obverse=by_id[case_id].obverse.path,
            reverse=by_id[case_id].reverse.path,
        )
        for case_id in EXPERIMENT_5_CASE_IDS
    )


def build_evidence_views(path: Path) -> tuple[tuple[str, bytes, str], ...]:
    """Reuse the current deterministic localized full-face/rim view builder."""

    return _localized_evidence_views(path)


def build_manifest(
    dataset_root: Path, *, case_ids: tuple[str, ...] | None = None
) -> ExperimentManifest:
    """Build a deterministic selected-case plan without contacting a provider."""

    requests: list[PlannedObservationRequest] = []
    cases = _select_cases(load_cases(dataset_root), case_ids)
    for case_index, case in enumerate(cases):
        arms: tuple[Literal["control", "treatment"], ...] = (
            ("control", "treatment")
            if case_index % 2 == 0
            else ("treatment", "control")
        )
        side_paths: tuple[tuple[Literal["obverse", "reverse"], Path], ...] = (
            ("obverse", case.obverse),
            ("reverse", case.reverse),
        )
        for role, path in side_paths:
            views = build_evidence_views(path)
            if tuple(item[0] for item in views) != ("full_face", "rim"):
                raise ValueError(
                    f"Experiment 5 requires full_face and rim views for {case.case_id}/{role}."
                )
            for view_name, image_data, media_type in views:
                view = cast(Literal["full_face", "rim"], view_name)
                for arm in arms:
                    requests.append(
                        PlannedObservationRequest(
                            sequence=len(requests) + 1,
                            arm=arm,
                            case_id=case.case_id,
                            role=role,
                            view=view,
                            media_type=media_type,
                            image_data=image_data,
                            image_sha256=_sha256_bytes(image_data),
                        )
                    )
    return ExperimentManifest(
        dataset_fingerprint=_dataset_fingerprint(dataset_root),
        requests=tuple(requests),
        case_ids=tuple(case.case_id for case in cases),
    )


def _select_cases(
    cases: tuple[ExperimentCase, ...], case_ids: tuple[str, ...] | None
) -> tuple[ExperimentCase, ...]:
    if case_ids is None:
        return cases
    if not case_ids:
        raise ValueError("explicit case selection must not be empty.")
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("duplicate case IDs are not permitted.")
    selected = set(case_ids)
    by_id = {case.case_id: case for case in cases}
    unknown = sorted(selected - set(by_id))
    if unknown:
        raise ValueError(f"unknown experiment case IDs: {', '.join(unknown)}")
    return tuple(case for case in cases if case.case_id in selected)


def run_dry_run(
    dataset_root: Path, output: Path, *, case_ids: tuple[str, ...] | None = None
) -> ExperimentManifest:
    """Write a non-sensitive request manifest without provider construction."""

    manifest = build_manifest(dataset_root, case_ids=case_ids)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest.public_record(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def execute_manifest(manifest: ExperimentManifest, *, provider_factory, output: Path) -> tuple[dict[str, object], ...]:
    """Execute a fixed manifest once per request; no retries or recognition."""

    providers = {
        "control": provider_factory(OPENAI_GROUNDED_OBSERVATION_PROMPT),
        "treatment": provider_factory(treatment_prompt()),
    }
    records = []
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for planned in manifest.requests:
            record = planned.public_record()
            try:
                report = providers[planned.arm].observe(
                    GroundedVisualObservationRequest(
                        scan_id=planned.case_id,
                        image=GroundedVisualObservationImage(
                            role=planned.role,
                            media_type=planned.media_type,
                            data=planned.image_data,
                        ),
                    )
                )
            except GroundedVisualObservationContractError as exc:
                record.update({"status": "malformed_output", "error_type": type(exc).__name__})
            else:
                observation = report.observation
                record.update({
                    "status": "success",
                    "visible_text": list(observation.visible_text),
                    "date_like": observation.date_like,
                    "denomination_mark": observation.denomination_mark,
                })
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            records.append(record)
    return tuple(records)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    """Create a safe manifest by default; live calls require explicit opt-in."""

    parser = argparse.ArgumentParser(
        prog="coin-analyzer-recognition30-observation-contract-experiment"
    )
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--case-id", action="append", dest="case_ids")
    parser.add_argument("--max-attempts", type=int)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="make the fixed provider calls; omitted means dry run only",
    )
    args = parser.parse_args(argv)
    manifest_path = args.output_dir / "request_manifest.json"
    selected_case_ids = tuple(args.case_ids) if args.case_ids is not None else None
    manifest = run_dry_run(args.dataset, manifest_path, case_ids=selected_case_ids)
    if args.max_attempts is not None and len(manifest.requests) > args.max_attempts:
        raise SystemExit("planned requests exceed --max-attempts")
    if args.execute:
        execute_manifest(
            manifest,
            provider_factory=lambda prompt: OpenAIGroundedVisualObservationProvider(prompt=prompt),
            output=args.output_dir / "observation_records.jsonl",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
