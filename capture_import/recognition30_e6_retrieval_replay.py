"""Offline Recognition30 Experiment 6 retrieval-representation evaluator.

Replays already-recorded grounded observations. It performs no provider/model calls
and does not run candidate verification or the final identity gate.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .catalogue_retrieval import CatalogueRetrievalContractError, request_from_numeral_envelope
from .evidence_candidate_resolver import COUNTRY_ALIASES, CatalogueCandidate
from .grounded_visual_observation import GroundedVisualObservation
from .in_memory_catalogue_retriever import InMemoryCatalogueRetriever
from .numeral_evidence_envelope import build_numeral_evidence_envelope


@dataclass(frozen=True, slots=True)
class RetrievalReplayRow:
    case_id: str
    control_ids: tuple[str, ...]
    treatment_ids: tuple[str, ...]
    control_hit: bool
    treatment_hit: bool
    request_error: str | None = None


def _load_catalogue(dataset: Path) -> tuple[CatalogueCandidate, ...]:
    rows: list[CatalogueCandidate] = []
    with (dataset / "ground_truth.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            case_id = (row.get("case_id") or "").strip()
            if not case_id:
                raise ValueError("ground_truth.csv row missing case_id")
            rows.append(
                CatalogueCandidate(
                    candidate_id=case_id,
                    country=(row.get("country") or "").strip(),
                    denomination=(row.get("denomination") or "").strip(),
                    year=(row.get("year") or "").strip(),
                    type_design=(row.get("type_design") or "").strip() or None,
                )
            )
    return tuple(rows)


def _country_reference_aliases(country: str) -> tuple[str, ...]:
    canonical = country.casefold()
    aliases = {
        alias
        for alias, target in COUNTRY_ALIASES.items()
        if target.casefold() == canonical
    }
    return tuple(sorted(aliases))


def enrich_catalogue(candidates: Iterable[CatalogueCandidate]) -> tuple[CatalogueCandidate, ...]:
    """Add only deterministic lexical reference material; never query observations."""

    enriched = []
    for candidate in candidates:
        legends = list(candidate.legends)
        legends.extend(_country_reference_aliases(candidate.country))
        if candidate.type_design:
            legends.append(candidate.type_design)
        enriched.append(
            CatalogueCandidate(
                candidate_id=candidate.candidate_id,
                country=candidate.country,
                denomination=candidate.denomination,
                year=candidate.year,
                type_design=candidate.type_design,
                legends=tuple(dict.fromkeys(legends)),
            )
        )
    return tuple(enriched)


def _observations(row: Mapping[str, object]) -> tuple[GroundedVisualObservation, ...]:
    result = []
    raw = row.get("observations")
    if not isinstance(raw, list):
        raise ValueError("report row observations must be a list")
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("report observation must be an object")
        visible = item.get("visible_text") or ()
        result.append(
            GroundedVisualObservation(
                role=str(item["role"]),
                visible_text=tuple(str(value) for value in visible),
                date_like=str(item["date_like"]) if item.get("date_like") is not None else None,
                denomination_mark=(
                    str(item["denomination_mark"])
                    if item.get("denomination_mark") is not None
                    else None
                ),
            )
        )
    return tuple(result)


def replay(
    report: Mapping[str, object],
    catalogue: Sequence[CatalogueCandidate],
    *,
    limit: int = 10,
) -> tuple[RetrievalReplayRow, ...]:
    control = InMemoryCatalogueRetriever(catalogue, retriever_id="recognition30-e6-control")
    treatment = InMemoryCatalogueRetriever(
        enrich_catalogue(catalogue), retriever_id="recognition30-e6-lexical-reference"
    )
    output = []
    raw_rows = report.get("rows")
    if not isinstance(raw_rows, list):
        raise ValueError("report rows must be a list")

    for raw_row in raw_rows:
        if not isinstance(raw_row, dict):
            raise ValueError("report row must be an object")
        case_id = str(raw_row["case_id"])
        try:
            envelope = build_numeral_evidence_envelope(_observations(raw_row))
            request = request_from_numeral_envelope(envelope, limit=limit)
        except CatalogueRetrievalContractError as exc:
            output.append(RetrievalReplayRow(case_id, (), (), False, False, str(exc)))
            continue

        control_ids = tuple(item.candidate_id for item in control.retrieve(request).candidates)
        treatment_ids = tuple(item.candidate_id for item in treatment.retrieve(request).candidates)
        output.append(
            RetrievalReplayRow(
                case_id=case_id,
                control_ids=control_ids,
                treatment_ids=treatment_ids,
                control_hit=case_id in control_ids,
                treatment_hit=case_id in treatment_ids,
            )
        )
    return tuple(output)


def summarize(rows: Sequence[RetrievalReplayRow]) -> dict[str, object]:
    total = len(rows)
    control_hits = sum(row.control_hit for row in rows)
    treatment_hits = sum(row.treatment_hit for row in rows)
    return {
        "schema": "coin-analyzer-recognition30-e6-retrieval-replay-v1",
        "cases": total,
        "control_hits_at_10": control_hits,
        "treatment_hits_at_10": treatment_hits,
        "control_recall_at_10": control_hits / total if total else 0.0,
        "treatment_recall_at_10": treatment_hits / total if total else 0.0,
        "delta_hits_at_10": treatment_hits - control_hits,
        "request_errors": sum(row.request_error is not None for row in rows),
        "rows": [
            {
                "case_id": row.case_id,
                "control_ids": list(row.control_ids),
                "treatment_ids": list(row.treatment_ids),
                "control_hit": row.control_hit,
                "treatment_hit": row.treatment_hit,
                "request_error": row.request_error,
            }
            for row in rows
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coin-analyzer-recognition30-e6-retrieval-replay",
        description="Offline E6 replay of frozen Recognition30 observations; no provider calls.",
    )
    parser.add_argument("report", type=Path)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--json", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = json.loads(args.report.read_text(encoding="utf-8"))
    result = summarize(replay(report, _load_catalogue(args.dataset)))
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
