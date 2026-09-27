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
        "obverse": {"picture": "https://example.invalid/o.jpg", "thumbnail": "https://example.invalid/o-180.jpg", "picture_copyright": "brismike", "picture_license_name": "CC BY-NC", "picture_license_url": "https://creativecommons.org/licenses/by-nc/4.0/deed.en"},
        "reverse": {"picture": "https://example.invalid/r.jpg", "thumbnail": "https://example.invalid/r-180.jpg", "picture_copyright": "brismike", "picture_license_name": "CC BY-NC", "picture_license_url": "https://creativecommons.org/licenses/by-nc/4.0/deed.en"},
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
        if "/types?" in url: return {"types": [{"id": 3444}, {"id": 734}]}
        if url.endswith("/3444"): return detail(3444, issuer="Netherlands Antilles")
        if url.endswith("/734"): return detail()
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
        if "/types?" in url: return {"types": [{"id": 734}, {"id": 735}]}
        return detail(734 if url.endswith("/734") else 735)
    row = audit_identity(identity, fake_get)
    assert row["resolution"] == "REVIEW_REQUIRED"
    assert row["selected"] is None


def test_summary_is_explicitly_zero_inference():
    result = summarize([{"resolution": "REVIEW_REQUIRED", "selected": None}])
    assert result["image_bytes_downloaded"] == 0
    assert result["embedding_inference_run"] is False
    assert result["execution_authorized"] is False


def test_load_identities_requires_exactly_30_unique_rows(tmp_path: Path):
    path = tmp_path / "ground_truth.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "country", "denomination", "year"])
        writer.writeheader()
        for i in range(30): writer.writerow({"case_id": f"CA-R30-{i + 1:03d}", "country": "Example", "denomination": "1 Unit", "year": "2000"})
    assert len(load_identities(tmp_path)) == 30
    path.write_text("case_id,country,denomination,year\nX,Example,1 Unit,2000\n")
    with pytest.raises(ValueError, match="exactly 30"): load_identities(tmp_path)


def test_exact_identity_match_normalizes_diacritic_and_plural():
    assert exact_identity_match(Identity("CA-R30-X", "Sweden", "10 ore", "1970"), detail(1504, issuer="Sweden", value="10 Öre", lo=1962, hi=1973))
    assert exact_identity_match(Identity("CA-R30-Y", "Philippines", "25 sentimo", "1990"), detail(2462, issuer="Philippines", value="25 Sentimos", lo=1983, hi=1990))


def test_exact_identity_match_normalizes_frozen_historical_issuer_alias():
    identity = Identity("CA-R30-017", "British Caribbean Territories, Eastern Group", "25 cents", "1955")
    assert exact_identity_match(identity, detail(2283, issuer="Eastern Caribbean States", value="25 Cents", lo=1955, hi=1965))


def test_ambiguous_nominal_match_uses_unique_catalogue_reference():
    identity = Identity("CA-R30-004", "Netherlands", "1 gulden", "1980", "Juliana; nickel; KM#184a")
    juliana = detail(738, value="1 Gulden", lo=1967, hi=1980); juliana["title"] = "1 Gulden - Juliana"; juliana["references"] = [{"catalogue": {"code": "KM"}, "number": "184a"}]
    beatrix = detail(5278, value="1 Gulden", lo=1980, hi=1980); beatrix["title"] = "1 Gulden - Beatrix (Investiture of New Queen)"; beatrix["references"] = [{"catalogue": {"code": "KM"}, "number": "195"}]
    def fake_get(url):
        if "/types?" in url: return {"types": [{"id": 738}, {"id": 5278}]}
        if url.endswith("/738"): return juliana
        if url.endswith("/5278"): return beatrix
        raise AssertionError(url)
    row = audit_identity(identity, fake_get)
    assert row["resolution"] == "AUTO_DESIGN_REFERENCE_UNIQUE"
    assert row["selected"]["numista_type_id"] == 738


def test_ambiguous_nominal_match_without_unique_reference_stays_closed():
    identity = Identity("CA-R30-X", "Example", "1 Unit", "2000", "Special design")
    a = detail(1, issuer="Example", value="1 Unit", lo=2000, hi=2000); b = detail(2, issuer="Example", value="1 Unit", lo=2000, hi=2000)
    def fake_get(url):
        if "/types?" in url: return {"types": [{"id": 1}, {"id": 2}]}
        return a if url.endswith("/1") else b
    row = audit_identity(identity, fake_get)
    assert row["resolution"] == "REVIEW_REQUIRED" and row["selected"] is None


def test_unique_nominal_match_with_conflicting_frozen_catalogue_ref_fails_closed():
    identity = Identity("CA-R30-009", "Spain", "1 peseta", "1975", "Juan Carlos I; KM#806")
    franco = detail(786, issuer="Spain", value="1 Peseta", lo=1967, hi=1975); franco["title"] = "1 Peseta - Francisco Franco (Ávalos)"; franco["references"] = [{"catalogue": {"code": "KM"}, "number": "796"}]
    def fake_get(url): return {"types": [{"id": 786}]} if "/types?" in url else franco
    row = audit_identity(identity, fake_get)
    assert row["resolution"] == "REVIEW_REQUIRED" and row["selected"] is None
    assert row["candidates"][0]["design_evidence"]["catalogue_reference_match"] is False


def test_unique_nominal_match_with_matching_frozen_catalogue_ref_resolves():
    identity = Identity("CA-R30-009", "Spain", "1 peseta", "1975", "Juan Carlos I; KM#806")
    candidate = detail(787, issuer="Spain", value="1 Peseta", lo=1975, hi=1980); candidate["title"] = "1 Peseta - Juan Carlos I"; candidate["references"] = [{"catalogue": {"code": "KM"}, "number": "806"}]
    def fake_get(url): return {"types": [{"id": 787}]} if "/types?" in url else candidate
    row = audit_identity(identity, fake_get)
    assert row["resolution"] == "AUTO_DESIGN_REFERENCE_UNIQUE" and row["selected"]["numista_type_id"] == 787


def test_catalogue_reference_parser_accepts_decimal_and_suffix():
    identity = Identity("CA-R30-X", "Example", "1 Unit", "2000", "Design; KM#241.1")
    candidate = detail(1, issuer="Example", value="1 Unit", lo=2000, hi=2000); candidate["references"] = [{"catalogue": {"code": "KM"}, "number": "241.1"}]
    def fake_get(url): return {"types": [{"id": 1}]} if "/types?" in url else candidate
    assert audit_identity(identity, fake_get)["resolution"] == "AUTO_DESIGN_REFERENCE_UNIQUE"


def test_exact_identity_match_normalizes_numista_half_sol_short_label():
    identity = Identity("CA-R30-006", "Peru", "1/2 Sol de Oro", "1972", "Large Coat of Arms; KM#247")
    assert exact_identity_match(identity, detail(909, issuer="Peru", value="½ Sol", lo=1966, hi=1973))


def test_value_normalization_remains_fail_closed_for_other_sol_values():
    assert not exact_identity_match(Identity("CA-R30-X", "Peru", "1/2 Sol de Oro", "1972"), detail(1, issuer="Peru", value="1 Sol", lo=1966, hi=1973))


def test_audit_philippines_sentimo_alias_resolves_through_full_path():
    identity = Identity("CA-R30-005", "Philippines", "25 sentimo", "1990", "Flora & Fauna; large type; KM#241.1")
    candidate = detail(2462, issuer="Philippines", value="25 Sentimos", lo=1983, hi=1990); candidate["title"] = "25 Sentimo (Large type)"; candidate["references"] = [{"catalogue": {"code": "KM"}, "number": "241.1"}]
    def fake_get(url): return {"types": [{"id": 2462}]} if "/types?" in url else candidate
    row = audit_identity(identity, fake_get)
    assert row["resolution"] == "AUTO_DESIGN_REFERENCE_UNIQUE" and row["candidates"][0]["exact_identity_match"] is True


def test_audit_peru_half_sol_alias_resolves_through_full_path():
    identity = Identity("CA-R30-006", "Peru", "1/2 Sol de Oro", "1972", "Large Coat of Arms; KM#247")
    candidate = detail(909, issuer="Peru", value="½ Sol", lo=1966, hi=1973); candidate["title"] = "½ Sol de Oro (Large Coat of Arms)"; candidate["references"] = [{"catalogue": {"code": "KM"}, "number": "247"}]
    def fake_get(url): return {"types": [{"id": 909}]} if "/types?" in url else candidate
    row = audit_identity(identity, fake_get)
    assert row["resolution"] == "AUTO_DESIGN_REFERENCE_UNIQUE" and row["candidates"][0]["exact_identity_match"] is True


def test_dominican_republic_historical_label_and_half_peso_are_bounded_aliases():
    identity = Identity("CA-R30-020", "Dominican Republic", "1/2 peso", "1973")
    assert exact_identity_match(identity, detail(5900, issuer="Dominican Republic (1844-date)", value="½ Peso", lo=1967, hi=1975))
    assert not exact_identity_match(identity, detail(5900, issuer="Dominican Republic (1844-date)", value="1 Peso", lo=1967, hi=1975))


def test_ireland_half_crown_alias_is_bounded():
    identity = Identity("CA-R30-022", "Ireland", "half crown", "1954")
    assert exact_identity_match(identity, detail(5188, issuer="Ireland", value="½ Crown", lo=1951, hi=1967))
    assert not exact_identity_match(identity, detail(5188, issuer="Ireland", value="1 Crown", lo=1951, hi=1967))


def test_switzerland_historical_label_does_not_override_catalogue_reference():
    identity = Identity("CA-R30-028", "Switzerland", "2 francs", "1968", "Standing Helvetia; copper-nickel; KM#21a.1")
    candidate = detail(189, issuer="Switzerland (1848-date)", value="2 Francs", lo=1968, hi=1968); candidate["title"] = "2 Francs - Standing Helvetia"; candidate["references"] = [{"catalogue": {"code": "KM"}, "number": "21a"}]
    def fake_get(url): return {"types": [{"id": 189}]} if "/types?" in url else candidate
    row = audit_identity(identity, fake_get)
    assert row["candidates"][0]["exact_identity_match"] is True
    assert row["resolution"] == "REVIEW_REQUIRED" and row["selected"] is None


def test_west_germany_observed_numista_issuer_spelling_matches_bounded_alias():
    identity = Identity("CA-R30-023", "West Germany", "2 Deutsche Mark", "1976", "Theodor Heuss; D mintmark")
    candidate = detail(1208, issuer="Germany, Federal Republic of", value="2 Deutsche Mark", lo=1970, hi=1987)
    candidate["title"] = "2 Deutsche Mark - Theodor Heuss"
    assert exact_identity_match(identity, candidate)
    assert not exact_identity_match(identity, detail(1208, issuer="Germany, Democratic Republic", value="2 Deutsche Mark", lo=1970, hi=1987))


def test_west_germany_retry_resolves_only_with_required_theodor_heuss_evidence():
    identity = Identity("CA-R30-023", "West Germany", "2 Deutsche Mark", "1976", "Theodor Heuss; D mintmark")
    candidate = detail(1208, issuer="Germany, Federal Republic of", value="2 Deutsche Mark", lo=1970, hi=1987); candidate["title"] = "2 Deutsche Mark - Theodor Heuss"
    calls = []
    def fake_get(url):
        calls.append(url)
        if "/types?" in url:
            if "West%20Germany" in url: return {"types": []}
            assert "Federal%20Republic%20of%20Germany" in url and "Theodor%20Heuss" in url
            return {"types": [{"id": 1208}]}
        return candidate
    row = audit_identity(identity, fake_get)
    assert row["resolution"] == "AUTO_DESIGN_TOKEN_UNIQUE"
    assert row["selected"]["numista_type_id"] == 1208
    assert row["candidates"][0]["exact_identity_match"] is True
    assert len([url for url in calls if "/types?" in url]) == 2


def test_west_germany_retry_stays_closed_for_wrong_portrait():
    identity = Identity("CA-R30-023", "West Germany", "2 Deutsche Mark", "1976", "Theodor Heuss; D mintmark")
    candidate = detail(9999, issuer="Germany, Federal Republic of", value="2 Deutsche Mark", lo=1970, hi=1987); candidate["title"] = "2 Deutsche Mark - Konrad Adenauer"
    def fake_get(url):
        if "/types?" in url: return {"types": []} if "West%20Germany" in url else {"types": [{"id": 9999}]}
        return candidate
    row = audit_identity(identity, fake_get)
    assert row["resolution"] == "REVIEW_REQUIRED" and row["selected"] is None


def test_unrelated_west_germany_identity_does_not_get_special_retry():
    identity = Identity("CA-R30-X", "West Germany", "1 Deutsche Mark", "1976", "Eagle")
    calls = []
    def fake_get(url):
        calls.append(url); return {"types": []}
    row = audit_identity(identity, fake_get)
    assert row["resolution"] == "REVIEW_REQUIRED"
    assert row["discovery_retry_query"] is None
    assert len(calls) == 1
