from __future__ import annotations

from urllib.parse import unquote

from capture_import.recognition30_e7_gallery_audit import Identity, audit_identity, exact_identity_match


def _detail(type_id: int, title: str, issuer: str = "Federal Republic of Germany"):
    return {
        "id": type_id,
        "url": f"https://en.numista.com/{type_id}",
        "title": title,
        "issuer": {"name": issuer},
        "value": {"text": "2 Deutsche Mark"},
        "min_year": 1970,
        "max_year": 1987,
    }


def test_west_germany_is_bounded_issuer_alias():
    identity = Identity("CA-R30-023", "West Germany", "2 Deutsche Mark", "1976")
    assert exact_identity_match(identity, _detail(1935, "2 Deutsche Mark (Theodor Heuss)"))
    assert not exact_identity_match(identity, _detail(1935, "2 Deutsche Mark", issuer="Germany"))


def test_023_retries_only_after_zero_results_and_requires_design_evidence():
    identity = Identity(
        "CA-R30-023",
        "West Germany",
        "2 Deutsche Mark",
        "1976",
        "Theodor Heuss; D mintmark",
    )
    calls: list[str] = []
    heuss = _detail(1935, "2 Deutsche Mark (Theodor Heuss)")

    def fake_get(url: str):
        calls.append(unquote(url))
        if "/types?" in url:
            if "West%20Germany" in url:
                return {"types": []}
            assert "Federal%20Republic%20of%20Germany" in url
            assert "Theodor%20Heuss" in url
            return {"types": [{"id": 1935}]}
        if url.endswith("/1935"):
            return heuss
        raise AssertionError(url)

    row = audit_identity(identity, fake_get)
    assert row["resolution"] == "AUTO_DESIGN_TOKEN_UNIQUE"
    assert row["selected"]["numista_type_id"] == 1935
    assert row["query"] == "West Germany 2 Deutsche Mark 1976"
    assert row["query_used"] == "Federal Republic of Germany 2 Deutsche Mark 1976 Theodor Heuss"
    assert len([url for url in calls if "/types?" in url]) == 2


def test_023_retry_stays_closed_when_design_does_not_match():
    identity = Identity(
        "CA-R30-023",
        "West Germany",
        "2 Deutsche Mark",
        "1976",
        "Theodor Heuss; D mintmark",
    )
    wrong_portrait = _detail(844, "2 Deutsche Mark (Konrad Adenauer)")

    def fake_get(url: str):
        if "/types?" in url:
            return {"types": []} if "West%20Germany" in url else {"types": [{"id": 844}]}
        return wrong_portrait

    row = audit_identity(identity, fake_get)
    assert row["resolution"] == "REVIEW_REQUIRED"
    assert row["selected"] is None


def test_non_023_west_germany_identity_does_not_get_special_retry():
    identity = Identity("CA-R30-X", "West Germany", "1 Mark", "1976", "Oak leaves")
    search_calls = 0

    def fake_get(url: str):
        nonlocal search_calls
        if "/types?" in url:
            search_calls += 1
            return {"types": []}
        raise AssertionError(url)

    row = audit_identity(identity, fake_get)
    assert row["resolution"] == "REVIEW_REQUIRED"
    assert row["discovery_retry_query"] is None
    assert search_calls == 1
