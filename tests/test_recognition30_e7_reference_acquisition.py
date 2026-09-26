import csv
import hashlib

import pytest

from capture_import.recognition30_e7_reference_acquisition import acquire_batch


def _dataset(tmp_path):
    root = tmp_path / "recognition30_v1"
    images = root / "images"
    images.mkdir(parents=True)
    (images / "a.jpg").write_bytes(b"query-a")
    (images / "b.jpg").write_bytes(b"query-b")
    with (root / "pair_manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "image_1", "image_2"])
        writer.writeheader()
        writer.writerow({"case_id": "CA-R30-001", "image_1": "a.jpg", "image_2": "b.jpg"})
    return root


def _manifest():
    return {
        "schema": "coin-analyzer-recognition30-e7-leakage-manifest-v1",
        "cases": 1,
        "reference_sides": 2,
        "execution_authorized": False,
        "rows": [{
            "case_id": "CA-R30-001",
            "numista_type_id": 7,
            "references": [
                {"role": "obverse", "picture_url": "https://example.test/o.jpg",
                 "copyright": "Owner", "license_name": "CC BY",
                 "license_url": "https://example.test/license"},
                {"role": "reverse", "picture_url": "https://example.test/r.jpg",
                 "copyright": "Owner", "license_name": "CC BY",
                 "license_url": "https://example.test/license"},
            ],
        }],
    }


def test_acquires_hashes_and_keeps_nonmatching_leakage_fail_closed(tmp_path):
    payloads = {
        "https://example.test/o.jpg": b"reference-o",
        "https://example.test/r.jpg": b"reference-r",
    }
    result = acquire_batch(_manifest(), _dataset(tmp_path), tmp_path / "refs", payloads.__getitem__)
    assert result["cases"] == 1
    assert result["reference_sides"] == 2
    assert result["unique_reference_urls"] == 2
    assert result["embedding_inference_run"] is False
    assert result["specimen_independence_inferred"] is False
    ref = result["rows"][0]["references"][0]
    assert ref["reference_sha256"] == hashlib.sha256(b"reference-o").hexdigest()
    assert ref["same_image_as_query"] == "REVIEW_REQUIRED"
    assert ref["derived_from_query"] == "NOT_AUDITED"
    assert ref["same_physical_specimen_as_query"] == "NOT_AUDITED"


def test_exact_byte_match_is_positive_leakage_evidence(tmp_path):
    payloads = {
        "https://example.test/o.jpg": b"query-a",
        "https://example.test/r.jpg": b"reference-r",
    }
    result = acquire_batch(_manifest(), _dataset(tmp_path), tmp_path / "refs", payloads.__getitem__)
    ref = result["rows"][0]["references"][0]
    assert ref["same_image_as_query"] is True
    assert ref["query_exact_sha256_matches"] == ["image_1"]


def test_duplicate_reference_url_is_downloaded_once(tmp_path):
    manifest = _manifest()
    manifest["rows"][0]["references"][1]["picture_url"] = "https://example.test/o.jpg"
    calls = []
    def fetch(url):
        calls.append(url)
        return b"reference"
    result = acquire_batch(manifest, _dataset(tmp_path), tmp_path / "refs", fetch)
    assert calls == ["https://example.test/o.jpg"]
    assert result["unique_reference_urls"] == 1


def test_missing_rights_metadata_fails_closed(tmp_path):
    manifest = _manifest()
    manifest["rows"][0]["references"][0]["license_name"] = None
    with pytest.raises(ValueError, match="lacks URL/rights"):
        acquire_batch(manifest, _dataset(tmp_path), tmp_path / "refs", lambda _: b"x")
