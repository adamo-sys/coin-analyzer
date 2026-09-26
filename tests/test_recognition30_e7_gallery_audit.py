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


def test_exact_identity_match_normalizes_diacritic_and_plural():
    identity = Identity("CA-R30-X", "Sweden", "10 ore", "1970")
    assert exact_identity_match(
        identity,
        detail(1504, issuer="Sweden", value="10 Öre", lo=1962, hi=1973),
    )
    identity = Identity("CA-R30-Y", "Philippines", "25 sentimo", "1990")
    assert exact_identity_match(
        identity,
        detail(2462, issuer="Philippines", value="25 Sentimos", lo=1983, hi=1990),
    )


def test_exact_identity_match_normalizes_frozen_historical_issuer_alias():
    identity = Identity(
        "CA-R30-017",
        "British Caribbean Territories, Eastern Group",
        "25 cents",
        "1955",
    )
    assert exact_identity_match(
        identity,
        detail(2283, issuer="Eastern Caribbean States", value="25 Cents", lo=1955, hi=1965),
    )


def test_ambiguous_nominal_match_uses_unique_catalogue_reference():
    identity = Identity(
        "CA-R30-004",
        "Netherlands",
        "1 gulden",
        "1980",
        "Juliana; nickel; KM#184a",
    )
    juliana = detail(738, value="1 Gulden", lo=1967, hi=1980)
    juliana["title"] = "1 Gulden - Juliana"
    juliana["references"] = [{"catalogue": {"code": "KM"}, "number": "184a"}]
    beatrix = detail(5278, value="1 Gulden", lo=1980, hi=1980)
    beatrix["title"] = "1 Gulden - Beatrix (Investiture of New Queen)"
    beatrix["references"] = [{"catalogue": {"code": "KM"}, "number": "195"}]

    def fake_get(url):
        if "/types?" in url:
            return {"types": [{"id": 738}, {"id": 5278}]}
        if url.endswith("/738"):
            return juliana
        if url.endswith("/5278"):
            return beatrix
        raise AssertionError(url)

    row = audit_identity(identity, fake_get)
    assert row["resolution"] == "AUTO_DESIGN_REFERENCE_UNIQUE"
    assert row["selected"]["numista_type_id"] == 738


def test_ambiguous_nominal_match_without_unique_reference_stays_closed():
    identity = Identity(
        "CA-R30-X", "Example", "1 Unit", "2000", "Special design"
    )
    a = detail(1, issuer="Example", value="1 Unit", lo=2000, hi=2000)
    b = detail(2, issuer="Example", value="1 Unit", lo=2000, hi=2000)

    def fake_get(url):
        if "/types?" in url:
            return {"types": [{"id": 1}, {"id": 2}]}
        return a if url.endswith("/1") else b

    row = audit_identity(identity, fake_get)
    assert row["resolution"] == "REVIEW_REQUIRED"
    assert row["selected"] is None


def test_unique_nominal_match_with_conflicting_frozen_catalogue_ref_fails_closed():
    identity = Identity(
        "CA-R30-009",
        "Spain",
        "1 peseta",
        "1975",
        "Juan Carlos I; KM#806",
    )
    franco = detail(786, issuer="Spain", value="1 Peseta", lo=1967, hi=1975)
    franco["title"] = "1 Peseta - Francisco Franco (Ávalos)"
    franco["references"] = [{"catalogue": {"code": "KM"}, "number": "796"}]

    def fake_get(url):
        if "/types?" in url:
            return {"types": [{"id": 786}]}
        return franco

    row = audit_identity(identity, fake_get)
    assert row["resolution"] == "REVIEW_REQUIRED"
    assert row["selected"] is None
    assert row["candidates"][0]["design_evidence"]["catalogue_reference_match"] is False


def test_unique_nominal_match_with_matching_frozen_catalogue_ref_resolves():
    identity = Identity(
        "CA-R30-009",
        "Spain",
        "1 peseta",
        "1975",
        "Juan Carlos I; KM#806",
    )
    candidate = detail(787, issuer="Spain", value="1 Peseta", lo=1975, hi=1980)
    candidate["title"] = "1 Peseta - Juan Carlos I"
    candidate["references"] = [{"catalogue": {"code": "KM"}, "number": "806"}]

    def fake_get(url):
        if "/types?" in url:
            return {"types": [{"id": 787}]}
        return candidate

    row = audit_identity(identity, fake_get)
    assert row["resolution"] == "AUTO_DESIGN_REFERENCE_UNIQUE"
    assert row["selected"]["numista_type_id"] == 787
    assert row["candidates"][0]["design_evidence"]["catalogue_reference_match"] is True


def test_catalogue_reference_parser_accepts_decimal_and_suffix():
    identity = Identity(
        "CA-R30-X",
        "Example",
        "1 Unit",
        "2000",
        "Design; KM#241.1",
    )
    candidate = detail(1, issuer="Example", value="1 Unit", lo=2000, hi=2000)
    candidate["references"] = [{"catalogue": {"code": "KM"}, "number": "241.1"}]

    def fake_get(url):
        if "/types?" in url:
            return {"types": [{"id": 1}]}
        return candidate

    row = audit_identity(identity, fake_get)
    assert row["resolution"] == "AUTO_DESIGN_REFERENCE_UNIQUE"
