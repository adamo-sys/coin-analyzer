import pytest

from capture_import.recognition30_e7_leakage_manifest import build_leakage_manifest


def _audit():
    return {
        "schema": "audit-v3",
        "rows": [
            {
                "identity": {
                    "case_id": "CA-R30-001",
                    "country": "Example",
                    "denomination": "1 Unit",
                    "year": "2000",
                    "type_design": "Example",
                },
                "resolution": "AUTO_EXACT_UNIQUE",
                "selected": {
                    "numista_type_id": 7,
                    "numista_url": "https://example.test/7",
                    "title": "Example coin",
                    "references": [
                        {
                            "role": "obverse",
                            "picture_url": "https://example.test/o.jpg",
                            "thumbnail_url": "https://example.test/o-thumb.jpg",
                            "copyright": "Owner",
                            "license_name": "CC BY",
                            "license_url": "https://example.test/license",
                            "image_digest": "must-not-propagate",
                            "same_image_as_query": False,
                            "derived_from_query": False,
                            "same_physical_specimen_as_query": False,
                        }
                    ],
                },
            },
            {
                "identity": {
                    "case_id": "CA-R30-002",
                    "country": "Blocked",
                    "denomination": "2 Units",
                    "year": "2001",
                    "type_design": None,
                },
                "resolution": "AUTO_EXACT_UNIQUE",
                "selected": {"numista_type_id": 8, "references": []},
            },
        ],
    }


def _readiness():
    return {
        "schema": "readiness-v1",
        "rights_eligible_cases": 1,
        "rows": [
            {
                "case_id": "CA-R30-001",
                "identity_resolved": True,
                "rights_eligible": True,
            },
            {
                "case_id": "CA-R30-002",
                "identity_resolved": True,
                "rights_eligible": False,
            },
        ],
    }


def test_manifest_scopes_only_identity_and_rights_eligible_cases():
    result = build_leakage_manifest(_audit(), _readiness())
    assert result["cases"] == 1
    assert result["rows"][0]["case_id"] == "CA-R30-001"
    assert result["execution_authorized"] is False


def test_manifest_resets_leakage_and_digest_fields_fail_closed():
    result = build_leakage_manifest(_audit(), _readiness())
    ref = result["rows"][0]["references"][0]
    assert ref["query_sha256"] is None
    assert ref["reference_sha256"] is None
    assert ref["reference_image_bytes_downloaded"] is False
    assert ref["same_image_as_query"] == "NOT_AUDITED"
    assert ref["derived_from_query"] == "NOT_AUDITED"
    assert ref["same_physical_specimen_as_query"] == "NOT_AUDITED"
    assert ref["provenance_evidence"] == []
    assert ref["specimen_level_evidence"] == []


def test_manifest_does_not_propagate_prior_leakage_claims():
    result = build_leakage_manifest(_audit(), _readiness())
    ref = result["rows"][0]["references"][0]
    assert ref["same_image_as_query"] is not False


def test_scope_count_mismatch_fails_closed():
    readiness = _readiness()
    readiness["rights_eligible_cases"] = 2
    with pytest.raises(ValueError, match="scope mismatch"):
        build_leakage_manifest(_audit(), readiness)
