from __future__ import annotations

from capture_import.recognition30_e7_gallery_audit import Identity, audit_identity, exact_identity_match


def _detail(*, issuer: str, title: str = "2 Deutsche Mark - Theodor Heuss") -> dict[str, object]:
    return {"id": 1208, "url": "https://en.numista.com/1208", "title": title, "issuer": {"name": issuer}, "value": {"text": "2 Deutsche Mark"}, "min_year": 1970, "max_year": 1987}


def _identity() -> Identity:
    return Identity("CA-R30-023", "West Germany", "2 Deutsche Mark", "1976", "Theodor Heuss; D mintmark")


def test_observed_numista_issuer_spelling_matches_bounded_alias() -> None:
    assert exact_identity_match(_identity(), _detail(issuer="Germany, Federal Republic of"))
    assert not exact_identity_match(_identity(), _detail(issuer="Germany, Democratic Republic"))


def test_retry_resolves_only_with_required_theodor_heuss_evidence() -> None:
    candidate = _detail(issuer="Germany, Federal Republic of")
    calls: list[str] = []
    def fake_get(url: str) -> dict[str, object]:
        calls.append(url)
        if "/types?" in url:
            if "West%20Germany" in url: return {"types": []}
            assert "Federal%20Republic%20of%20Germany" in url and "Theodor%20Heuss" in url
            return {"types": [{"id": 1208}]}
        return candidate
    row = audit_identity(_identity(), fake_get)
    assert row["resolution"] == "AUTO_DESIGN_TOKEN_UNIQUE"
    assert row["selected"]["numista_type_id"] == 1208
    assert row["candidates"][0]["exact_identity_match"] is True
    assert len([url for url in calls if "/types?" in url]) == 2


def test_retry_stays_closed_for_wrong_portrait() -> None:
    candidate = _detail(issuer="Germany, Federal Republic of", title="2 Deutsche Mark - Konrad Adenauer")
    def fake_get(url: str) -> dict[str, object]:
        if "/types?" in url: return {"types": []} if "West%20Germany" in url else {"types": [{"id": 1208}]}
        return candidate
    row = audit_identity(_identity(), fake_get)
    assert row["resolution"] == "REVIEW_REQUIRED"
    assert row["selected"] is None


def test_unrelated_west_germany_identity_does_not_get_special_retry() -> None:
    identity = Identity("CA-R30-X", "West Germany", "1 Deutsche Mark", "1976", "Eagle")
    calls: list[str] = []
    def fake_get(url: str) -> dict[str, object]:
        calls.append(url); return {"types": []}
    row = audit_identity(identity, fake_get)
    assert row["resolution"] == "REVIEW_REQUIRED"
    assert row["discovery_retry_query"] is None
    assert len(calls) == 1
