from __future__ import annotations

import csv
from pathlib import Path

import pytest

from capture_import.recognition30_e7_gallery_audit import (
    Identity,
    audit_identity,
    exact_identity_match,
    load_identities,
    summarize,
)


def detail(type_id=734, issuer="Netherlands", value="10 Cents", lo=1950, hi=1980):
    return {
        "id": type_id,
        "url": f"https://en.numista.com/{type_id}",
        "title": "10 Cents - Juliana",
        "issuer": {"name": issuer},
        "value": {"text": value},
        "min_year": lo,
        "max_year": hi,
        "obverse": {
            "picture": "https://example.invalid/o.jpg",
            "thumbnail": "https://example.invalid/o-180.jpg",
            "picture_copyright": "brismike",
            "picture_license_name": "CC BY-NC",
            "picture_license_url": "https://creativecommons.org/licenses/by-nc/4.0/deed.en",
        },
        "reverse": {
            "picture": "https://example.invalid/r.jpg",
            "thumbnail": "https://example.invalid/r-180.jpg",
            "picture_copyright": "brismike",
            "picture_license_name": "CC BY-NC",
            "picture_license_url": "https://creativecommons.org/licenses/by-nc/4.0/deed.en",
        },
    }


def test_exact_identity_match_requires_issuer_value_and_year_range():
    identity = Identity("CA-R30-001", "Netherlands", "10 Cents", "1974")
    assert exact_identity_match(identity, detail())
    assert not exact_identity_match(identity, detail(issuer="Netherlands Antilles"))
    assert not exact_identity_match(identity, detail(value="25 Cents"))
    assert not exact_identity_match(identity, detail(lo=1950, hi=1970))


def test_audit_unique_exact_match_records_rights_without_downloading():
    identity = Identity("CA-R30-001", "Netherlands", "10 Cents", "1974")

    def fake_get(url):
        if "/types?" in url:
            return {"types": [{"id": 3444}, {"id": 734}]}
        if url.endswith("/3444"):
            return detail(3444, issuer="Netherlands Antilles")
        if url.endswith("/734"):
            return detail()
        raise AssertionError(url)

    row = audit_identity(identity, fake_get)
    assert row["resolution"] == "AUTO_EXACT_UNIQUE"
    assert row["selected"]["numista_type_id"] == 734
    assert len(row["selected"]["references"]) == 2
    assert row["selected"]["references"][0]["license_name"] == "CC BY-NC"
    assert row["selected"]["references"][0]["image_bytes_downloaded"] is False


def test_audit_ambiguous_exact_matches_fails_closed():
    identity = Identity("CA-R30-001", "Netherlands", "10 Cents", "1974")

    def fake_get(url):
        if "/types?" in url:
            return {"types": [{"id": 734}, {"id": 735}]}
        return detail(734 if url.endswith("/734") else 735)

    row = audit_identity(identity, fake_get)
    assert row["resolution"] == "REVIEW_REQUIRED"
    assert row["selected"] is None


def test_summary_is_explicitly_zero_inference():
    rows = [{"resolution": "REVIEW_REQUIRED", "selected": None}]
    result = summarize(rows)
    assert result["image_bytes_downloaded"] == 0
    assert result["embedding_inference_run"] is False
    assert result["execution_authorized"] is False


def test_load_identities_requires_exactly_30_unique_rows(tmp_path: Path):
    path = tmp_path / "ground_truth.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["case_id", "country", "denomination", "year"]
        )
        writer.writeheader()
        for i in range(30):
            writer.writerow(
                {
                    "case_id": f"CA-R30-{i + 1:03d}",
                    "country": "Example",
                    "denomination": "1 Unit",
                    "year": "2000",
                }
            )
    assert len(load_identities(tmp_path)) == 30

    path.write_text("case_id,country,denomination,year\nX,Example,1 Unit,2000\n")
    with pytest.raises(ValueError, match="exactly 30"):
        load_identities(tmp_path)
