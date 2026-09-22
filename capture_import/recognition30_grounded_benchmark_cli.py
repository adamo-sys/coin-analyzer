"""Recognition30 runner for the grounded recognition architecture.

Benchmark-only. Ground truth is used only after each final IDENTIFY/ABSTAIN
decision has been produced.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
import json

import cv2

from pathlib import Path
from typing import Mapping, Sequence

from .adaptive_grounded_observation import decide_secondary_observation
from .evidence_candidate_resolver import CatalogueCandidate
from .grounded_recognition_pipeline import run_grounded_recognition_pipeline
from .grounded_visual_observation import (
    GroundedVisualObservation,
    GroundedVisualObservationContractError,
    GroundedVisualObservationImage,
    GroundedVisualObservationRequest,
)
from .in_memory_catalogue_retriever import InMemoryCatalogueRetriever
from .multiview_grounded_observation import (
    GroundedObservationViewReport,
    union_grounded_observation_views,
    view_provenance,
)
from .phone_photo_coin_localization import (
    build_coin_evidence_views,
    crop_localized_coin,
    localize_coin_circle,
)
from .openai_grounded_visual_observation_provider import (
    OpenAIGroundedVisualObservationProvider,
)
from .recognition_decision_gate import RecognitionDecision, RecognitionGateResult
from .recognition30_grounded_evaluation import (
    aggregate_metrics,
    compare_to_baseline,
    evaluate_case,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coin-analyzer-recognition30-grounded-benchmark",
        description=(
            "Recognition30 benchmark under oracle candidate availability; "
            "it measures downstream evidence and verification, not production retrieval."
        ),
    )
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--case-id", action="append", dest="case_ids")
    parser.add_argument("--retrieval-limit", type=int, default=10)
    parser.add_argument(
        "--evidence-report",
        type=Path,
        help="write a compact deterministic per-case evidence/provenance report",
    )
    parser.add_argument(
        "--adaptive-views",
        action="store_true",
        help=(
            "observe full_face first and request rim only when deterministic "
            "primary evidence is insufficient"
        ),
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="print deterministic verification diagnostics for each case",
    )
    return parser



@dataclass(frozen=True, slots=True)
class _BenchmarkImage:
    path: Path


@dataclass(frozen=True, slots=True)
class _BenchmarkCase:
    case_id: str
    obverse: _BenchmarkImage
    reverse: _BenchmarkImage
    expected: dict[str, str]


@dataclass(frozen=True, slots=True)
class _BenchmarkDataset:
    version: str
    cases: tuple[_BenchmarkCase, ...]


def _load_dataset(root: Path) -> _BenchmarkDataset:
    pair_path = root / "pair_manifest.csv"
    truth_path = root / "ground_truth.csv"
    images_root = root / "images"
    if not pair_path.is_file() or not truth_path.is_file() or not images_root.is_dir():
        raise ValueError(
            "dataset must contain pair_manifest.csv, ground_truth.csv, and images/."
        )

    with truth_path.open("r", encoding="utf-8-sig", newline="") as handle:
        truth_rows = tuple(csv.DictReader(handle))
    truth_by_id = {row.get("case_id", "").strip(): row for row in truth_rows}
    if "" in truth_by_id or len(truth_by_id) != len(truth_rows):
        raise ValueError("ground_truth.csv case_id values must be non-empty and unique.")

    cases = []
    with pair_path.open("r", encoding="utf-8-sig", newline="") as handle:
        pair_rows = tuple(csv.DictReader(handle))
    seen = set()
    for row in pair_rows:
        case_id = (row.get("case_id") or "").strip()
        image_1 = (row.get("image_1") or "").strip()
        image_2 = (row.get("image_2") or "").strip()
        if not case_id or case_id in seen or not image_1 or not image_2:
            raise ValueError("pair_manifest.csv rows require unique case_id and two images.")
        seen.add(case_id)
        truth = truth_by_id.get(case_id)
        if truth is None:
            raise ValueError(f"missing ground truth for {case_id}.")
        if truth.get("image_1", "").strip() != image_1 or truth.get("image_2", "").strip() != image_2:
            raise ValueError(f"pair/truth image mismatch for {case_id}.")
        expected = {
            "country": (truth.get("country") or "").strip(),
            "denomination": (truth.get("denomination") or "").strip(),
            "year": (truth.get("year") or "").strip(),
        }
        variety = (truth.get("variety") or "").strip()
        if variety:
            expected["type_design"] = variety
        if any(not expected[field] for field in ("country", "denomination", "year")):
            raise ValueError(f"incomplete identity truth for {case_id}.")
        obverse = images_root / image_1
        reverse = images_root / image_2
        if not obverse.is_file() or not reverse.is_file():
            raise ValueError(f"missing benchmark image for {case_id}.")
        cases.append(
            _BenchmarkCase(
                case_id=case_id,
                obverse=_BenchmarkImage(obverse),
                reverse=_BenchmarkImage(reverse),
                expected=expected,
            )
        )
    if set(truth_by_id) != seen:
        raise ValueError("pair_manifest.csv and ground_truth.csv case IDs must match.")
    return _BenchmarkDataset(version=root.name, cases=tuple(cases))


def _select_cases(dataset, case_ids: Sequence[str] | None):
    if not case_ids:
        return dataset.cases
    requested = tuple(dict.fromkeys(case_ids))
    by_id = {case.case_id: case for case in dataset.cases}
    missing = tuple(case_id for case_id in requested if case_id not in by_id)
    if missing:
        raise SystemExit(f"unknown --case-id(s): {', '.join(missing)}")
    return tuple(by_id[case_id] for case_id in requested)


def _catalogue(dataset) -> tuple[CatalogueCandidate, ...]:
    return tuple(
        CatalogueCandidate(
            candidate_id=case.case_id,
            country=case.expected["country"],
            denomination=case.expected["denomination"],
            year=case.expected["year"],
            type_design=case.expected.get("type_design"),
        )
        for case in dataset.cases
    )

def _media_type(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    raise ValueError(f"unsupported benchmark image type: {path.suffix}")


def _localized_image_bytes(path: Path) -> tuple[bytes, str, dict[str, object]]:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"unable to decode benchmark image: {path}")
    localization = localize_coin_circle(image)
    if localization is None:
        return path.read_bytes(), _media_type(path), {"localized": False}

    crop = crop_localized_coin(image, localization)
    ok, encoded = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not ok:
        raise ValueError(f"unable to encode localized benchmark crop: {path}")
    return encoded.tobytes(), "image/jpeg", {
        "localized": True,
        "crop_x": localization.crop_x,
        "crop_y": localization.crop_y,
        "crop_width": localization.crop_width,
        "crop_height": localization.crop_height,
        "score": localization.score,
    }


def _localized_evidence_views(
    path: Path,
) -> tuple[tuple[str, bytes, str], ...]:
    """Return deterministic observation views without provider-dependent routing."""

    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"unable to decode benchmark image: {path}")
    localization = localize_coin_circle(image)
    if localization is None:
        return (("source", path.read_bytes(), _media_type(path)),)

    encoded_views = []
    for view_name, view in build_coin_evidence_views(image, localization):
        ok, encoded = cv2.imencode(".jpg", view, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not ok:
            raise ValueError(f"unable to encode {view_name} evidence view: {path}")
        encoded_views.append((view_name, encoded.tobytes(), "image/jpeg"))
    return tuple(encoded_views)


def run_case(
    case,
    *,
    provider,
    retriever,
    retrieval_limit: int,
    adaptive_views: bool = False,
):
    reports = []
    localizations = []
    provider_failures = []
    provenance = []
    adaptive_routing = []
    for role, image in (("obverse", case.obverse), ("reverse", case.reverse)):
        _, _, localization = _localized_image_bytes(image.path)
        localizations.append({"role": role, **localization})
        view_reports = []
        evidence_views = _localized_evidence_views(image.path)
        for view_index, (view_name, image_bytes, media_type) in enumerate(evidence_views):
            if adaptive_views and view_index > 0:
                primary = view_reports[0].report.observation if view_reports else None
                if primary is None:
                    break
                routing = decide_secondary_observation(primary)
                adaptive_routing.append(
                    {
                        "role": role,
                        "primary_view": evidence_views[0][0],
                        "secondary_view": view_name,
                        "requested": routing.request_secondary,
                        "reason": routing.reason,
                        "missing_evidence": list(routing.missing_evidence),
                    }
                )
                if not routing.request_secondary:
                    break
            try:
                report = provider.observe(
                    GroundedVisualObservationRequest(
                        scan_id=case.case_id,
                        image=GroundedVisualObservationImage(
                            role=role,
                            media_type=media_type,
                            data=image_bytes,
                        ),
                    )
                )
            except GroundedVisualObservationContractError as exc:
                failure = {
                    "role": role,
                    "view": view_name,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
                diagnostics = getattr(exc, "diagnostics", None)
                if isinstance(diagnostics, Mapping):
                    failure["diagnostics"] = dict(diagnostics)
                provider_failures.append(failure)
                break
            view_reports.append(
                GroundedObservationViewReport(view=view_name, report=report)
            )
        if view_reports:
            provenance.extend(view_provenance(tuple(view_reports)))
            unioned = union_grounded_observation_views(tuple(view_reports))
            first = view_reports[0].report
            reports.append(
                type(first)(
                    observation=unioned,
                    provider_id=first.provider_id,
                    model_id=first.model_id,
                    response_id=first.response_id,
                    input_tokens=sum(
                        item.report.input_tokens or 0 for item in view_reports
                    ),
                    output_tokens=sum(
                        item.report.output_tokens or 0 for item in view_reports
                    ),
                )
            )

    if provider_failures:
        decision = RecognitionGateResult(
            decision=RecognitionDecision.ABSTAIN,
            candidate_id=None,
            reason="provider_observation_failure",
            observation_roles=tuple(
                report.observation.role for report in reports
            ),
        )
        outcome = evaluate_case(
            case_id=case.case_id,
            expected_candidate_id=case.case_id,
            decision=decision,
        )
        return (
            outcome,
            reports,
            None,
            tuple(localizations),
            tuple(provider_failures),
            tuple(provenance),
        )

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
    return (
        outcome,
        reports,
        pipeline,
        tuple(localizations),
        tuple(provider_failures),
        tuple(provenance),
    )



def _adaptive_routing_provenance(
    provenance: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    """Reconstruct deterministic routing decisions from successful primary views."""

    rows = []
    for item in provenance:
        if str(item.get("view")) != "full_face":
            continue
        observation = GroundedVisualObservation(
            role=str(item["role"]),
            visible_text=tuple(str(value) for value in item.get("visible_text") or ()),
            date_like=(
                str(item["date_like"]) if item.get("date_like") is not None else None
            ),
            denomination_mark=(
                str(item["denomination_mark"])
                if item.get("denomination_mark") is not None
                else None
            ),
        )
        decision = decide_secondary_observation(observation)
        rows.append(
            {
                "role": observation.role,
                "primary_view": "full_face",
                "secondary_view": "rim",
                "requested": decision.request_secondary,
                "reason": decision.reason,
                "missing_evidence": list(decision.missing_evidence),
            }
        )
    return tuple(rows)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 1 <= args.retrieval_limit <= 25:
        raise SystemExit("--retrieval-limit must be between 1 and 25")

    dataset = _load_dataset(args.dataset)
    cases = _select_cases(dataset, args.case_ids)
    provider = OpenAIGroundedVisualObservationProvider()
    retriever = InMemoryCatalogueRetriever(
        _catalogue(dataset),
        retriever_id=f"recognition30-{dataset.version}-oracle-catalogue",
    )

    outcomes = []
    rows = []
    for case in cases:
        (
            outcome,
            reports,
            pipeline,
            localizations,
            provider_failures,
            provenance,
        ) = run_case(
            case,
            provider=provider,
            retriever=retriever,
            retrieval_limit=args.retrieval_limit,
            adaptive_views=args.adaptive_views,
        )
        outcomes.append(outcome)
        adaptive_routing = (
            _adaptive_routing_provenance(provenance) if args.adaptive_views else ()
        )
        rows.append(
            {
                "case_id": case.case_id,
                "decision": outcome.decision.value,
                "predicted_candidate_id": outcome.predicted_candidate_id,
                "correct": outcome.correct,
                "abstain": outcome.abstain,
                "unsafe_wrong_identification": outcome.unsafe_wrong_identification,
                "reason": outcome.reason,
                "localizations": list(localizations),
                "provider_failures": list(provider_failures),
                "view_provenance": list(provenance),
                "adaptive_routing": list(adaptive_routing),
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
                    if pipeline is not None and pipeline.retrieval is not None
                    else None
                ),
                "query_id": (
                    pipeline.retrieval.query_id
                    if pipeline is not None and pipeline.retrieval is not None
                    else None
                ),
                "retrieved_candidate_ids": (
                    [candidate.candidate_id for candidate in pipeline.retrieval.candidates]
                    if pipeline is not None and pipeline.retrieval is not None
                    else []
                ),
                "verified_candidate_ids": (
                    list(pipeline.summary.verified_candidate_ids)
                    if pipeline is not None and pipeline.summary is not None
                    else []
                ),
                "verification_rows": (
                    [
                        {
                            "candidate_id": row.candidate.candidate_id,
                            "matched_fields": list(row.matched_fields),
                            "conflicting_fields": list(row.conflicting_fields),
                            "supporting_roles": list(row.supporting_roles),
                            "supporting_text": list(row.supporting_text),
                            "verified": row.verified,
                        }
                        for row in pipeline.verification.rows
                    ]
                    if pipeline is not None and pipeline.verification is not None
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
        if args.diagnostics and provider_failures:
            for failure in provider_failures:
                print(
                    "  provider_failure: "
                    f"role={failure['role']} "
                    f"view={failure.get('view', 'source')} "
                    f"type={failure['error_type']} "
                    f"message={failure['message']}",
                    flush=True,
                )
        if (
            args.diagnostics
            and pipeline is not None
            and pipeline.verification is not None
        ):
            if not pipeline.verification.rows:
                print("  verification: no candidate rows", flush=True)
            for verification_row in pipeline.verification.rows:
                print(
                    "  verification: "
                    f"candidate={verification_row.candidate.candidate_id} "
                    f"verified={verification_row.verified} "
                    f"matched={list(verification_row.matched_fields)} "
                    f"conflicts={list(verification_row.conflicting_fields)} "
                    f"roles={list(verification_row.supporting_roles)} "
                    f"text={list(verification_row.supporting_text)}",
                    flush=True,
                )

    metrics = aggregate_metrics(outcomes)
    comparison = compare_to_baseline(metrics)
    report = {
        "schema": "coin-analyzer-recognition30-grounded-v1",
        "dataset_version": dataset.version,
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

    if args.evidence_report is not None:
        evidence_rows = [
            {
                "case_id": row["case_id"],
                "localized_roles": [
                    item["role"]
                    for item in row["localizations"]
                    if item["localized"]
                ],
                "observed_roles": [
                    item["role"]
                    for item in row["observations"]
                    if (
                        item["visible_text"]
                        or item["date_like"] is not None
                        or item["denomination_mark"] is not None
                    )
                ],
                "provider_failures": row["provider_failures"],
                "retrieved_candidate_ids": row["retrieved_candidate_ids"],
                "verified_candidate_ids": row["verified_candidate_ids"],
                "decision": row["decision"],
                "predicted_candidate_id": row["predicted_candidate_id"],
                "reason": row["reason"],
            }
            for row in rows
        ]
        evidence_report = {
            "schema": "coin-analyzer-recognition30-evidence-report-v1",
            "dataset_version": dataset.version,
            "rows": evidence_rows,
        }
        args.evidence_report.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_report.write_text(
            json.dumps(evidence_report, indent=2, ensure_ascii=False) + "\n",
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
