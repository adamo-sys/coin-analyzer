"""Recognition30 runner for the grounded recognition architecture.

Benchmark-only. Ground truth is used only after each final IDENTIFY/ABSTAIN
decision has been produced.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Sequence

from .evidence_candidate_resolver import CatalogueCandidate
from .grounded_recognition_pipeline import run_grounded_recognition_pipeline
from .grounded_visual_observation import (
    GroundedVisualObservationImage,
    GroundedVisualObservationRequest,
)
from .in_memory_catalogue_retriever import InMemoryCatalogueRetriever
from .openai_grounded_visual_observation_provider import (
    OpenAIGroundedVisualObservationProvider,
)
from .recognition30_grounded_evaluation import (
    aggregate_metrics,
    compare_to_baseline,
    evaluate_case,
)
from .visual_evaluation_harness import load_visual_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coin-analyzer-recognition30-grounded-benchmark"
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--case-id", action="append", dest="case_ids")
    parser.add_argument("--retrieval-limit", type=int, default=10)
    return parser


def _select_cases(manifest, case_ids: Sequence[str] | None):
    if not case_ids:
        return manifest.cases
    requested = tuple(dict.fromkeys(case_ids))
    by_id = {case.case_id: case for case in manifest.cases}
    missing = tuple(case_id for case_id in requested if case_id not in by_id)
    if missing:
        raise SystemExit(f"unknown --case-id(s): {', '.join(missing)}")
    return tuple(by_id[case_id] for case_id in requested)


def _catalogue(manifest) -> tuple[CatalogueCandidate, ...]:
    return tuple(
        CatalogueCandidate(
            candidate_id=case.case_id,
            country=case.expected["country"],
            denomination=case.expected["denomination"],
            year=case.expected["year"],
            type_design=case.expected.get("type_design"),
        )
        for case in manifest.cases
    )


def _media_type(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    raise ValueError(f"unsupported benchmark image type: {path.suffix}")


def run_case(case, *, provider, retriever, retrieval_limit: int):
    reports = []
    for role, image in (("obverse", case.obverse), ("reverse", case.reverse)):
        report = provider.observe(
            GroundedVisualObservationRequest(
                scan_id=case.case_id,
                image=GroundedVisualObservationImage(
                    role=role,
                    media_type=_media_type(image.path),
                    data=image.path.read_bytes(),
                ),
            )
        )
        reports.append(report)

    pipeline = run_grounded_recognition_pipeline(
        tuple(report.observation for report in reports),
        retriever,
        retrieval_limit=retrieval_limit,
    )
    outcome = evaluate_case(
        case_id=case.case_id,
        expected_candidate_id=case.case_id,
        decision=pipeline.decision,
    )
    return outcome, reports, pipeline


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 1 <= args.retrieval_limit <= 25:
        raise SystemExit("--retrieval-limit must be between 1 and 25")

    manifest = load_visual_manifest(args.manifest)
    cases = _select_cases(manifest, args.case_ids)
    provider = OpenAIGroundedVisualObservationProvider()
    retriever = InMemoryCatalogueRetriever(
        _catalogue(manifest),
        retriever_id=f"recognition30-{manifest.version}-oracle-catalogue",
    )

    outcomes = []
    rows = []
    for case in cases:
        outcome, reports, pipeline = run_case(
            case,
            provider=provider,
            retriever=retriever,
            retrieval_limit=args.retrieval_limit,
        )
        outcomes.append(outcome)
        rows.append(
            {
                "case_id": case.case_id,
                "decision": outcome.decision.value,
                "predicted_candidate_id": outcome.predicted_candidate_id,
                "correct": outcome.correct,
                "abstain": outcome.abstain,
                "unsafe_wrong_identification": outcome.unsafe_wrong_identification,
                "reason": outcome.reason,
                "observations": [
                    {
                        "role": report.observation.role,
                        "visible_text": report.observation.visible_text,
                        "date_like": report.observation.date_like,
                        "denomination_mark": report.observation.denomination_mark,
                        "provider_id": report.provider_id,
                        "model_id": report.model_id,
                        "response_id": report.response_id,
                        "input_tokens": report.input_tokens,
                        "output_tokens": report.output_tokens,
                    }
                    for report in reports
                ],
                "retriever_id": (
                    pipeline.retrieval.retriever_id
                    if pipeline.retrieval is not None
                    else None
                ),
                "query_id": (
                    pipeline.retrieval.query_id
                    if pipeline.retrieval is not None
                    else None
                ),
                "retrieved_candidate_ids": (
                    [candidate.candidate_id for candidate in pipeline.retrieval.candidates]
                    if pipeline.retrieval is not None
                    else []
                ),
                "verified_candidate_ids": (
                    list(pipeline.summary.verified_candidate_ids)
                    if pipeline.summary is not None
                    else []
                ),
            }
        )
        print(
            f"{case.case_id} | {outcome.decision.value.upper()} | "
            f"candidate={outcome.predicted_candidate_id} | "
            f"correct={outcome.correct} | reason={outcome.reason}",
            flush=True,
        )

    metrics = aggregate_metrics(outcomes)
    comparison = compare_to_baseline(metrics)
    report = {
        "schema": "coin-analyzer-recognition30-grounded-v1",
        "dataset_version": manifest.version,
        "provider_id": provider.provider_id,
        "model_id": provider.model_id,
        "retrieval_limit": args.retrieval_limit,
        "rows": rows,
        "metrics": asdict(metrics),
        "baseline_comparison": dict(comparison),
    }

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    print(f"Cases: {metrics.total_cases}")
    print(f"Correct: {metrics.correct_cases}")
    print(f"Identified: {metrics.identified_cases}")
    print(f"Abstained: {metrics.abstained_cases}")
    print(f"Unsafe wrong identifications: {metrics.unsafe_wrong_identifications}")
    print(
        "Full identity accuracy: "
        + (
            "n/a"
            if metrics.full_identity_accuracy is None
            else f"{metrics.full_identity_accuracy * 100:.1f}%"
        )
    )
    print(
        "Coverage: "
        + ("n/a" if metrics.coverage is None else f"{metrics.coverage * 100:.1f}%")
    )
    print(
        "Selective accuracy: "
        + (
            "n/a"
            if metrics.selective_accuracy is None
            else f"{metrics.selective_accuracy * 100:.1f}%"
        )
    )
    print(
        "Unsafe wrong-identification rate: "
        + (
            "n/a"
            if metrics.unsafe_wrong_identification_rate is None
            else f"{metrics.unsafe_wrong_identification_rate * 100:.1f}%"
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
