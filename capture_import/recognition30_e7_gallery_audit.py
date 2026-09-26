"""Recognition30 E7 Numista metadata-only gallery audit.

Preflight only: reads frozen identity truth, queries Numista catalogue metadata,
and writes candidate/reference provenance. It never downloads image bytes and
never runs an embedding model.

Ambiguous identity resolution is fail-closed. A type is auto-resolved only when
exactly one returned candidate has the expected issuer, contains the expected
year, and has a normalized value matching the expected denomination. Otherwise
the row remains unresolved for explicit review.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence


API_ROOT = "https://api.numista.com/api/v3"
USER_AGENT = "coin-analyzer-recognition30-e7-preflight/1"
JsonGet = Callable[[str], Mapping[str, object]]


@dataclass(frozen=True, slots=True)
class Identity:
    case_id: str
    country: str
    denomination: str
    year: str
    type_design: str | None = None


def load_identities(dataset: Path) -> tuple[Identity, ...]:
    path = dataset / "ground_truth.csv"
    rows: list[Identity] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            case_id = (row.get("case_id") or "").strip()
            country = (row.get("country") or "").strip()
            denomination = (row.get("denomination") or "").strip()
            year = (row.get("year") or "").strip()
            type_design = (
                (row.get("type_design") or row.get("variety") or "").strip() or None
            )
            if not case_id or not country or not denomination or not year:
                raise ValueError(f"incomplete Recognition30 identity row: {row!r}")
            rows.append(Identity(case_id, country, denomination, year, type_design))
    if len(rows) != 30 or len({row.case_id for row in rows}) != 30:
        raise ValueError("E7 requires exactly 30 unique Recognition30 identities")
    return tuple(rows)


def _norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def _year_in_range(expected: str, candidate: Mapping[str, object]) -> bool:
    try:
        year = int(expected)
        lo = int(candidate["min_year"])
        hi = int(candidate["max_year"])
    except (KeyError, TypeError, ValueError):
        return False
    return lo <= year <= hi


def _issuer_name(candidate: Mapping[str, object]) -> str:
    issuer = candidate.get("issuer")
    return str(issuer.get("name", "")) if isinstance(issuer, Mapping) else ""


def _value_text(candidate: Mapping[str, object]) -> str:
    value = candidate.get("value")
    return str(value.get("text", "")) if isinstance(value, Mapping) else ""


def exact_identity_match(identity: Identity, detail: Mapping[str, object]) -> bool:
    return (
        _norm(_issuer_name(detail)) == _norm(identity.country)
        and _year_in_range(identity.year, detail)
        and _norm(_value_text(detail)) == _norm(identity.denomination)
    )


def reference_side(detail: Mapping[str, object], side: str) -> dict[str, object] | None:
    raw = detail.get(side)
    if not isinstance(raw, Mapping):
        return None
    return {
        "role": side,
        "picture_url": raw.get("picture"),
        "thumbnail_url": raw.get("thumbnail"),
        "copyright": raw.get("picture_copyright"),
        "license_name": raw.get("picture_license_name"),
        "license_url": raw.get("picture_license_url"),
        "image_bytes_downloaded": False,
        "image_digest": None,
        "same_image_as_query": "NOT_AUDITED",
        "derived_from_query": "NOT_AUDITED",
        "same_physical_specimen_as_query": "NOT_AUDITED",
    }


def audit_identity(identity: Identity, get_json: JsonGet) -> dict[str, object]:
    query = f"{identity.country} {identity.denomination} {identity.year}"
    search_url = (
        f"{API_ROOT}/types?category=coin&q="
        + urllib.parse.quote(query, safe="")
    )
    search = get_json(search_url)
    raw_types = search.get("types")
    if not isinstance(raw_types, list):
        raise ValueError("Numista search response missing types list")

    candidates: list[dict[str, object]] = []
    exact: list[tuple[int, Mapping[str, object]]] = []
    for raw in raw_types:
        if not isinstance(raw, Mapping) or not isinstance(raw.get("id"), int):
            continue
        type_id = int(raw["id"])
        detail = get_json(f"{API_ROOT}/types/{type_id}")
        is_exact = exact_identity_match(identity, detail)
        candidates.append(
            {
                "numista_type_id": type_id,
                "title": detail.get("title"),
                "issuer": _issuer_name(detail),
                "value": _value_text(detail),
                "min_year": detail.get("min_year"),
                "max_year": detail.get("max_year"),
                "exact_identity_match": is_exact,
            }
        )
        if is_exact:
            exact.append((type_id, detail))

    resolved = len(exact) == 1
    selected = None
    if resolved:
        type_id, detail = exact[0]
        selected = {
            "numista_type_id": type_id,
            "numista_url": detail.get("url"),
            "title": detail.get("title"),
            "issuer": _issuer_name(detail),
            "value": _value_text(detail),
            "min_year": detail.get("min_year"),
            "max_year": detail.get("max_year"),
            "references": [
                side
                for side in (
                    reference_side(detail, "obverse"),
                    reference_side(detail, "reverse"),
                )
                if side is not None
            ],
        }

    return {
        "identity": asdict(identity),
        "query": query,
        "resolution": "AUTO_EXACT_UNIQUE" if resolved else "REVIEW_REQUIRED",
        "selected": selected,
        "candidates": candidates,
    }


def summarize(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    resolved = sum(row.get("resolution") == "AUTO_EXACT_UNIQUE" for row in rows)
    refs = [
        ref
        for row in rows
        if isinstance(row.get("selected"), Mapping)
        for ref in row["selected"].get("references", [])
        if isinstance(ref, Mapping)
    ]
    licensed = sum(
        bool(ref.get("copyright") and ref.get("license_name") and ref.get("license_url"))
        for ref in refs
    )
    return {
        "schema": "coin-analyzer-recognition30-e7-gallery-audit-v1",
        "mode": "NUMISTA_METADATA_ONLY_ZERO_INFERENCE",
        "cases": len(rows),
        "auto_resolved_cases": resolved,
        "review_required_cases": len(rows) - resolved,
        "reference_sides_exposed": len(refs),
        "reference_sides_with_explicit_rights_metadata": licensed,
        "image_bytes_downloaded": 0,
        "embedding_inference_run": False,
        "execution_authorized": False,
        "rows": list(rows),
    }


def make_http_get(api_key: str) -> JsonGet:
    if not api_key:
        raise ValueError("NUMISTA_API_KEY is not loaded")

    def get_json(url: str) -> Mapping[str, object]:
        request = urllib.request.Request(
            url,
            headers={"Numista-API-Key": api_key, "User-Agent": USER_AGENT},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Numista API HTTP {exc.code} for {url}") from exc
        if not isinstance(payload, Mapping):
            raise ValueError(f"Numista API returned non-object JSON for {url}")
        return payload

    return get_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coin-analyzer-recognition30-e7-gallery-audit",
        description=(
            "Metadata-only Numista preflight for E7; no image downloads or embeddings."
        ),
    )
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--json", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    identities = load_identities(args.dataset)
    get_json = make_http_get(os.environ.get("NUMISTA_API_KEY", ""))
    rows = [audit_identity(identity, get_json) for identity in identities]
    result = summarize(rows)
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
