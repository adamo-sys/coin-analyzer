import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "benchmarks"
    / "adversarial_reference"
    / "build_targeted_two_side_acquisition_manifest.py"
)
SPEC = importlib.util.spec_from_file_location("targeted_manifest", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class TargetedManifestTests(unittest.TestCase):
    def test_collect_pages_preserves_provenance_metadata_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "candidates.json"
            row = {
                "case_id": "example-coin-2001",
                "side": "reference",
                "provider": "Example Catalog",
                "url": "https://example.invalid/coin/2001",
                "identity_evidence": "Exact country, denomination, and year.",
                "asset_note": "Asset review pending.",
                "license_or_permitted_use": "Permission pending.",
                "provenance_retrieved_at": "2026-08-26",
                "source_record_id": "record-2001",
                "required_coin_sides": ["obverse", "reverse"],
            }
            source.write_text(json.dumps({"items": [row, row]}), encoding="utf-8")

            pages = MODULE.collect_pages(((source, "items", "test-fixture"),))

        candidates = pages[("example-coin-2001", "reference")]
        self.assertEqual(1, len(candidates))
        self.assertEqual("Permission pending.", candidates[0]["license_or_permitted_use"])
        self.assertEqual("2026-08-26", candidates[0]["provenance_retrieved_at"])
        self.assertEqual("record-2001", candidates[0]["source_record_id"])
        self.assertEqual(["obverse", "reverse"], candidates[0]["required_coin_sides"])

    def test_build_artifact_is_deterministic_and_resolves_both_coin_sides(self):
        queue = {
            "queue": [
                {
                    "case_id": "example-coin-2001",
                    "expected": {"country": "Example", "denomination": "1", "year": "2001"},
                    "source_group": "reference",
                    "coin_side": coin_side,
                    "asset_role": f"reference.{coin_side}",
                }
                for coin_side in ("obverse", "reverse")
            ]
        }
        candidate = {
            "provider": "Example Catalog",
            "source_page_url": "https://example.invalid/coin/2001",
            "identity_evidence": "Exact identity.",
            "asset_note": "Asset review pending.",
            "license_or_permitted_use": "Permission pending.",
            "provenance_retrieved_at": "2026-08-26",
            "source_record_id": "record-2001",
            "required_coin_sides": ["obverse", "reverse"],
            "source_artifact": "test-fixture",
        }
        pages = {("example-coin-2001", "reference"): [candidate]}

        first = MODULE.build_artifact(queue, pages)
        second = MODULE.build_artifact(queue, pages)

        self.assertEqual(first, second)
        self.assertEqual(2, first["summary"]["roles_with_known_page_candidates"])
        self.assertEqual(0, first["summary"]["roles_without_known_page_candidates"])
        self.assertEqual(0, first["summary"]["cases_still_requiring_page_discovery"])
        self.assertTrue(all(role["page_candidates"] == [candidate] for role in first["roles"]))


if __name__ == "__main__":
    unittest.main()
