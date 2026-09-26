import pytest

from capture_import.recognition30_e7_gallery_readiness import build_readiness_matrix


def audit_row(
    case_id="CA-R30-001",
    *,
    resolution="AUTO_EXACT_UNIQUE",
    license_name="CC BY",
    license_url="https://example.test/license",
    leakage=False,
):
    selected = None
    if resolution.startswith("AUTO_"):
        selected = {
            "numista_type_id": 1,
            "references": [
                {
                    "picture_url": "https://example.test/obv.jpg",
                    "license_name": license_name,
                    "license_url": license_url,
                    "same_image_as_query": leakage,
                    "derived_from_query": leakage,
                    "same_physical_specimen_as_query": leakage,
                }
            ],
        }
    return {
        "identity": {
            "case_id": case_id,
            "country": "Example",
            "denomination": "1 Unit",
            "year": "2000",
            "type_design": "Example design",
        },
        "resolution": resolution,
        "selected": selected,
    }


def test_ready_requires_identity_rights_and_explicit_clear_leakage():
    result = build_readiness_matrix(
        {"schema": "audit-v3", "cases": 1, "rows": [audit_row()]}
    )
    row = result["rows"][0]
    assert row["identity_resolved"] is True
    assert row["rights_eligible"] is True
    assert row["leakage_audited_clear"] is True
    assert row["execution_ready"] is True
    assert result["execution_authorized"] is False


def test_not_audited_leakage_fails_closed():
    row = audit_row(leakage="NOT_AUDITED")
    result = build_readiness_matrix({"cases": 1, "rows": [row]})
    assert result["rows"][0]["leakage_audited_clear"] is False
    assert result["rows"][0]["execution_ready"] is False
    assert "LEAKAGE_NOT_CLEARED" in result["rows"][0]["blockers"]


def test_missing_license_is_not_rights_eligible():
    row = audit_row(license_name=None, license_url=None)
    result = build_readiness_matrix({"cases": 1, "rows": [row]})
    assert result["rows"][0]["rights_eligible"] is False
    assert "RIGHTS_INELIGIBLE_OR_INCOMPLETE" in result["rows"][0]["blockers"]


def test_review_required_is_identity_unresolved():
    row = audit_row(resolution="REVIEW_REQUIRED")
    result = build_readiness_matrix({"cases": 1, "rows": [row]})
    assert result["rows"][0]["identity_resolved"] is False
    assert result["rows"][0]["rights_eligible"] is False
    assert result["rows"][0]["execution_ready"] is False
    assert result["rows"][0]["blockers"] == ["IDENTITY_UNRESOLVED"]


def test_duplicate_case_ids_fail_closed():
    row = audit_row()
    with pytest.raises(ValueError, match="unique"):
        build_readiness_matrix({"cases": 2, "rows": [row, row]})


def test_case_count_mismatch_fails_closed():
    with pytest.raises(ValueError, match="row count"):
        build_readiness_matrix({"cases": 30, "rows": [audit_row()]})
