"""Synthetic-only tests: never read private photos or execute a live provider."""

import json
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from capture_import.phone_photo_benchmark import (
    FIELDS,
    SCHEMA,
    digest,
    finalize_report,
    load_manifest,
    manifest_digest,
    read_images,
    resume_rejected_rows,
    run_baseline,
    score,
    validate_manifest,
)
from capture_import.visual_identity_provider import (
    VisualIdentityCandidate,
    VisualIdentityReport,
)


def fixture():
    return {"schema": SCHEMA, "version": "1.0", "privacy": "private-local-only",
            "label_provenance": "synthetic test", "specimens": [{
                "specimen_id": "CA-BENCH-001", "difficulty": "easy",
                "challenge_tags": ["phone-photo"], "images": [
                    {"path": "IMG_0001.JPG", "role": "obverse", "sha256": digest(b"first")},
                    {"path": "IMG_0002.JPG", "role": "reverse", "sha256": digest(b"second")}],
                "ground_truth": {field: {"value": value, "verification": "verified"}
                                 for field, value in zip(FIELDS, ("Canada", "5 cents", "1965", "test design"))}}]}


def prediction(manifest):
    return [{"specimen_id": row["specimen_id"], "execution_status": "completed_prediction",
             "prediction": {field: truth["value"] for field, truth in row["ground_truth"].items()}}
            for row in manifest["specimens"]]


def validated_report():
    candidate = VisualIdentityCandidate(1, "Canada", "5 cents", "1965", "test design", .5,
                                       ("visible text",), ("obverse", "reverse"), "synthetic", "synthetic")
    return VisualIdentityReport("CANDIDATES", (candidate,), "synthetic", "synthetic", "response", 1, 2, {"raw": "retained"})


def two_specimens():
    manifest = fixture()
    second = deepcopy(manifest["specimens"][0])
    second["specimen_id"] = "CA-BENCH-002"
    second["images"] = [{"path": f"IMG_000{i}.JPG", "role": role, "sha256": digest(str(i).encode())}
                        for i, role in ((3, "obverse"), (4, "reverse"))]
    manifest["specimens"].append(second)
    return manifest


def write_images(root):
    for number, data in ((1, b"first"), (2, b"second"), (3, b"3"), (4, b"4")):
        (root / f"IMG_000{number}.JPG").write_bytes(data)


def legacy_archive(manifest):
    configuration = {"fixed": True}
    provenance = {
        "schema": SCHEMA, "manifest": manifest, "manifest_sha256": manifest_digest(manifest),
        "provider_configuration": configuration,
        "provider_configuration_sha256": digest(json.dumps(configuration, sort_keys=True).encode()),
        "provider_source_sha256": digest((Path(__file__).resolve().parents[1] / "capture_import/visual_identity_provider.py").read_bytes()),
        "privacy": "private-local-only",
    }
    rows = [{"specimen_id": row["specimen_id"], "prediction": {},
             "ground_truth": row["ground_truth"], "infrastructure_failure": "not_run_after_failure"}
            for row in manifest["specimens"]]
    rows[0].update(infrastructure_failure="VisualIdentityMalformedOutput",
                   raw_provider_output={"outcome": "CANDIDATES", "candidates": []},
                   response_id="archived-response", input_tokens=123, output_tokens=45)
    return provenance, {**deepcopy(provenance), "specimens": rows,
                        "source_integrity_after_run": "verified", "generated_at": "original-time",
                        "git_commit": "original-head", "scorer_source_sha256": "original-scorer"}


class PhonePhotoBenchmarkTests(unittest.TestCase):
    def test_incomplete_run_is_not_complete_and_not_attempted_is_unscored(self):
        manifest = two_specimens()
        result = finalize_report({"manifest": manifest}, prediction(manifest)[:1], "verified")
        self.assertFalse(result["baseline_complete"])
        self.assertFalse(result["execution"]["execution_complete"])
        self.assertEqual(result["execution"]["specimens_attempted"], 1)
        self.assertEqual(result["execution"]["specimens_not_attempted"], 1)
        self.assertEqual(result["specimens"][1]["results"]["year"], "not_attempted")
        self.assertEqual(result["metrics"]["fields"]["year"]["denominator"], 1)
        empty = finalize_report({"manifest": manifest}, [], "verified")
        self.assertFalse(empty["baseline_complete"])
        self.assertEqual(empty["execution"]["specimens_not_attempted"], 2)

    def test_runtime_failure_continues_and_is_not_rejection_or_abstention(self):
        manifest = two_specimens()
        provider = Mock(configuration={"fixed": True})
        provider.identify.side_effect = [RuntimeError("sensitive exception text"), validated_report()]
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_images(root)
            result = run_baseline(manifest, root, provider, upload_authorized=True)
        self.assertEqual(provider.identify.call_count, 2)
        self.assertTrue(result["baseline_complete"])  # All attempts recorded, not all recognized.
        self.assertEqual(result["execution"]["specimens_with_provider_runtime_failure"], 1)
        self.assertEqual(result["execution"]["specimens_rejected_before_scoring"], 0)
        self.assertEqual(result["execution"]["specimens_with_validated_predictions"], 1)
        self.assertNotIn("sensitive exception text", json.dumps(result))

    def test_interruption_leaves_unattempted_rows_and_incomplete_baseline(self):
        manifest = two_specimens()
        provider = Mock(configuration={"fixed": True})
        provider.identify.side_effect = KeyboardInterrupt()
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_images(root)
            result = run_baseline(manifest, root, provider, upload_authorized=True)
        provider.identify.assert_called_once()
        self.assertFalse(result["baseline_complete"])
        self.assertEqual(result["execution"]["specimens_attempted"], 1)
        self.assertEqual(result["execution"]["specimens_not_attempted"], 1)
        self.assertTrue(result["interrupted"])

    def test_complete_abstention_is_scored_separately_from_rejection(self):
        manifest = fixture()
        values = [{"specimen_id": "CA-BENCH-001", "execution_status": "completed_abstention", "prediction": {}}]
        result = finalize_report({"manifest": manifest}, values, "verified")
        self.assertTrue(result["baseline_complete"])
        self.assertEqual(result["execution"]["specimens_with_validated_abstentions"], 1)
        self.assertEqual(result["metrics"]["abstention_rate"], 1)
        self.assertEqual(result["metrics"]["exact_identity_accuracy"], 0)

    def test_rejected_rows_cannot_fabricate_predictions_or_omit_reason(self):
        manifest = fixture()
        for values in ({"year": "1965"}, {}):
            row = {"specimen_id": "CA-BENCH-001", "execution_status": "validation_rejected", "prediction": values}
            with self.assertRaises(ValueError):
                score(manifest, [row])

    def test_safe_archive_reuse_skips_first_call_and_keeps_original_evidence(self):
        manifest = two_specimens()
        _, archive = legacy_archive(manifest)
        provider = Mock(configuration={"fixed": True})
        provider.identify.return_value = validated_report()
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_images(root)
            path = root / "archive.json"
            data = json.dumps(archive).encode()
            path.write_bytes(data)
            result = run_baseline(manifest, root, provider, upload_authorized=True,
                                  resume_report=path, resume_sha256=digest(data))
            self.assertEqual(path.read_bytes(), data)
        provider.identify.assert_called_once()
        self.assertEqual(provider.identify.call_args.args[0].scan_id, "CA-BENCH-002")
        first = result["specimens"][0]
        self.assertEqual(first["execution_status"], "validation_rejected")
        self.assertEqual(first["raw_provider_output"], archive["specimens"][0]["raw_provider_output"])
        self.assertEqual(first["response_id"], "archived-response")
        self.assertEqual(first["validator_failure"], "outcome and candidates disagree.")
        self.assertEqual(result["resume"]["report_sha256"], digest(data))
        self.assertEqual(result["execution"]["specimens_attempted"], 2)
        self.assertEqual(result["metrics"]["exact_identity_denominator"], 1)

    def test_archive_mismatches_fail_before_any_new_call(self):
        manifest = two_specimens()
        _, original = legacy_archive(manifest)
        mutations = {
            "manifest_hash": lambda a: a.update(manifest_sha256="0" * 64),
            "image_hash": lambda a: a["manifest"]["specimens"][0]["images"][0].update(sha256="0" * 64),
            "image_role": lambda a: a["manifest"]["specimens"][0]["images"][0].update(role="reverse"),
            "config": lambda a: a.update(provider_configuration={"fixed": False}),
            "config_hash": lambda a: a.update(provider_configuration_sha256="0" * 64),
            "provider_source": lambda a: a.update(provider_source_sha256="0" * 64),
            "specimen_id": lambda a: a["specimens"][0].update(specimen_id="CA-BENCH-999"),
            "row_label": lambda a: a["specimens"][0].update(ground_truth={}),
            "duplicate_id": lambda a: a["specimens"][1].update(specimen_id="CA-BENCH-001"),
            "missing_row": lambda a: a["specimens"].pop(),
            "source_integrity": lambda a: a.update(source_integrity_after_run="failed"),
            "missing_raw": lambda a: a["specimens"][0].pop("raw_provider_output"),
            "no_response_id": lambda a: a["specimens"][0].pop("response_id"),
            "valid_raw": lambda a: a["specimens"][0].update(raw_provider_output={"outcome": "ABSTAINED", "candidates": []}),
            "wrong_failure": lambda a: a["specimens"][0].update(infrastructure_failure="RuntimeError"),
            "invented_prediction": lambda a: a["specimens"][0].update(prediction={"year": "1965"}),
        }
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_images(root)
            path = root / "archive.json"
            for name, mutate in mutations.items():
                with self.subTest(name=name):
                    archive = deepcopy(original)
                    mutate(archive)
                    data = json.dumps(archive).encode()
                    path.write_bytes(data)
                    provider = Mock(configuration={"fixed": True})
                    with self.assertRaises(ValueError):
                        run_baseline(manifest, root, provider, upload_authorized=True,
                                     resume_report=path, resume_sha256=digest(data))
                    provider.identify.assert_not_called()

    def test_archive_pin_and_resume_pair_are_mandatory(self):
        manifest = fixture()
        provenance, archive = legacy_archive(manifest)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_images(root)
            path = root / "archive.json"
            path.write_text(json.dumps(archive), encoding="utf-8")
            with self.assertRaises(ValueError):
                resume_rejected_rows(path, "0" * 64, provenance)
            provider = Mock(configuration={"fixed": True})
            with self.assertRaises(ValueError):
                run_baseline(manifest, root, provider, upload_authorized=True, resume_report=path)
            provider.identify.assert_not_called()

    def test_evidence_conflict_blocks_execution_before_any_file_or_provider_access(self):
        manifest = fixture()
        manifest["execution_blocker"] = "disputed jurisdiction"
        provider = Mock()
        with self.assertRaises(ValueError):
            run_baseline(manifest, Path("nonexistent"), provider, upload_authorized=True)
        provider.identify.assert_not_called()

    def test_correct_prediction(self):
        manifest = fixture()
        values = prediction(manifest)
        values[0]["prediction"]["jurisdiction"] = " CANADA "
        result = score(manifest, values)
        self.assertEqual(result["metrics"]["exact_identity_accuracy"], 1)
        self.assertEqual(result["metrics"]["fields"]["year"]["accuracy"], 1)

    def test_partial_failure(self):
        manifest = fixture()
        values = prediction(manifest)
        values[0]["prediction"]["year"] = "1964"
        result = score(manifest, values)
        self.assertEqual(result["specimens"][0]["results"]["year"], "incorrect")
        self.assertEqual(result["metrics"]["exact_identity_accuracy"], 0)
        self.assertEqual(result["metrics"]["fields"]["jurisdiction"]["accuracy"], 1)

    def test_abstention_is_not_accuracy_success(self):
        manifest = fixture()
        values = prediction(manifest)
        values[0]["prediction"] = {"jurisdiction": "Unknown", "year": None}
        result = score(manifest, values)["metrics"]
        self.assertEqual(result["abstention_rate"], 1)
        self.assertEqual(result["exact_identity_accuracy"], 0)
        self.assertEqual(result["fields"]["year"]["denominator"], 1)

    def test_unverified_truth_excluded_even_when_predicted(self):
        manifest = fixture()
        values = prediction(manifest)
        manifest["specimens"][0]["ground_truth"]["year"] = {"value": None, "verification": "unverified"}
        result = score(manifest, values)
        self.assertEqual(result["metrics"]["exact_identity_accuracy"], 1)
        self.assertEqual(result["specimens"][0]["verified_field_count"], 3)
        self.assertIsNone(result["metrics"]["fields"]["year"]["accuracy"])
        self.assertEqual(result["metrics"]["fields"]["year"]["unscorable"], 1)

    def test_no_verified_fields_is_not_vacuous_exact_match(self):
        manifest = fixture()
        for item in manifest["specimens"][0]["ground_truth"].values():
            item.update(value=None, verification="unverified")
        result = score(manifest, prediction(manifest))["metrics"]
        self.assertEqual(result["exact_identity_denominator"], 0)
        self.assertIsNone(result["exact_identity_accuracy"])

    def test_execution_failure_is_not_abstention(self):
        manifest = fixture()
        values = prediction(manifest)
        values[0].update(infrastructure_failure="unavailable", execution_status="provider_runtime_failure", prediction={})
        result = score(manifest, values)["metrics"]
        self.assertEqual(result["infrastructure_failures"], 1)
        self.assertEqual(result["fields"]["year"]["execution_failed"], 1)
        self.assertIsNone(result["abstention_rate"])

    def test_duplicate_specimen_and_images(self):
        for mode in ("specimen", "path", "hash"):
            with self.subTest(mode=mode):
                manifest = fixture()
                if mode == "specimen":
                    manifest["specimens"].append(deepcopy(manifest["specimens"][0]))
                else:
                    images = manifest["specimens"][0]["images"]
                    field = "path" if mode == "path" else "sha256"
                    images[1][field] = images[0][field]
                with self.assertRaises(ValueError):
                    validate_manifest(manifest)

    def test_malformed_manifest(self):
        for mutate in (
            lambda m: m.update(schema="wrong"),
            lambda m: m.update(privacy="public"),
            lambda m: m.update(specimens=[]),
            lambda m: m["specimens"][0].update(difficulty="impossible"),
            lambda m: m["specimens"][0].update(challenge_tags=["x", "x"]),
            lambda m: m["specimens"][0]["images"][0].update(path="../IMG_0001.JPG"),
            lambda m: m["specimens"][0]["ground_truth"]["year"].update(value=True),
            lambda m: m["specimens"][0]["ground_truth"]["year"].update(verification="unverified"),
        ):
            manifest = fixture()
            mutate(manifest)
            with self.assertRaises(ValueError):
                validate_manifest(manifest)
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.json"
            path.write_text("{bad", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_manifest(path)

    def test_difficulty_and_tag_aggregation(self):
        manifest = fixture()
        second = deepcopy(manifest["specimens"][0])
        second.update(specimen_id="CA-BENCH-002", difficulty="hard", challenge_tags=["phone-photo", "holder"])
        second["images"] = [{"path": f"IMG_000{i}.JPG", "role": "obverse" if i == 3 else "reverse", "sha256": digest(str(i).encode())} for i in (3, 4)]
        manifest["specimens"].append(second)
        values = prediction(manifest)
        values[1].update(prediction={}, execution_status="completed_abstention")
        result = score(manifest, values)
        self.assertEqual(result["metrics"]["exact_identity_accuracy"], .5)
        self.assertEqual(result["by_difficulty"]["easy"]["exact_identity_accuracy"], 1)
        self.assertEqual(result["by_difficulty"]["hard"]["abstention_rate"], 1)
        self.assertIsNone(result["by_difficulty"]["medium"]["exact_identity_accuracy"])
        self.assertEqual(result["by_challenge_tag"]["holder"]["specimen_count"], 1)

    def test_prediction_inventory_and_types(self):
        manifest = fixture()
        for rows in ([], prediction(manifest) * 2, [{"specimen_id": "CA-BENCH-001", "prediction": {"year": 1965}}]):
            with self.assertRaises(ValueError):
                score(manifest, rows)

    def test_image_integrity_and_pair_execution(self):
        manifest = fixture()
        provider = Mock(configuration={"fixed": True})
        candidate = VisualIdentityCandidate(1, "Canada", "5 cents", "1965", "test design", .5,
                                            ("visible text",), ("obverse", "reverse"), "synthetic", "synthetic")
        provider.identify.return_value = VisualIdentityReport("CANDIDATES", (candidate,), "synthetic", "synthetic", "response", 1, 2, {"raw": "retained"})
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for image, data in zip(manifest["specimens"][0]["images"], (b"first", b"second")):
                (root / image["path"]).write_bytes(data)
            with self.assertRaises(PermissionError):
                run_baseline(manifest, root, provider)
            provider.identify.assert_not_called()
            result = run_baseline(manifest, root, provider, upload_authorized=True)
            provider.identify.assert_called_once()
            request = provider.identify.call_args.args[0]
            self.assertEqual(tuple(i.data for i in request.images), (b"first", b"second"))
            self.assertEqual(result["specimens"][0]["raw_provider_output"]["raw_structured_result"], {"raw": "retained"})
            self.assertEqual(result["manifest_sha256"], manifest_digest(manifest))
            self.assertEqual(result["metrics"]["specimen_count"], 1)
            (root / "IMG_0001.JPG").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                read_images(manifest, root)

    def test_role_order_is_explicit_not_filename_order(self):
        manifest = fixture()
        manifest["specimens"][0]["images"].reverse()
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "IMG_0001.JPG").write_bytes(b"first")
            (root / "IMG_0002.JPG").write_bytes(b"second")
            self.assertEqual(read_images(manifest, root), [(b"first", b"second")])
        manifest["specimens"][0]["images"][0]["role"] = "obverse"
        with self.assertRaises(ValueError):
            validate_manifest(manifest)

    def test_rejection_retains_evidence_and_continues_to_validated_prediction(self):
        from capture_import.visual_identity_provider import (
            VisualIdentityMalformedOutput,
        )
        manifest = fixture()
        second = deepcopy(manifest["specimens"][0])
        second["specimen_id"] = "CA-BENCH-002"
        second["images"] = [{"path": f"IMG_000{i}.JPG", "role": role, "sha256": digest(str(i).encode())}
                            for i, role in ((3, "obverse"), (4, "reverse"))]
        manifest["specimens"].append(second)
        error = VisualIdentityMalformedOutput("do not retain arbitrary exception text")
        error.raw_provider_output = {"incomplete": True}
        error.response_id, error.input_tokens, error.output_tokens = "response", 123, 45
        provider = Mock(configuration={"fixed": True})
        provider.identify.side_effect = [error, validated_report()]
        journal = []
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, data in ((1, b"first"), (2, b"second"), (3, b"3"), (4, b"4")):
                (root / f"IMG_000{name}.JPG").write_bytes(data)
            result = run_baseline(manifest, root, provider, upload_authorized=True, checkpoint=journal.append)
        self.assertEqual(provider.identify.call_count, 2)
        self.assertTrue(result["baseline_complete"])
        self.assertEqual(result["specimens"][1]["execution_status"], "completed_prediction")
        self.assertEqual(result["specimens"][0]["execution_status"], "validation_rejected")
        self.assertEqual(result["specimens"][0]["validator_failure"], str(error))
        self.assertEqual(result["metrics"]["fields"]["year"]["denominator"], 1)
        self.assertEqual(result["metrics"]["fields"]["year"]["validation_rejected"], 1)
        self.assertEqual(result["metrics"]["fields"]["year"]["abstained"], 0)
        self.assertEqual(result["metrics"]["fields"]["year"]["incorrect"], 0)
        self.assertEqual(result["execution"]["specimens_attempted"], 2)
        self.assertEqual(result["execution"]["specimens_rejected_before_scoring"], 1)
        self.assertEqual(journal[1]["raw_provider_output"], {"incomplete": True})
        self.assertEqual(journal[1]["input_tokens"], 123)
        self.assertEqual(journal[1]["response_id"], "response")
        self.assertEqual(journal[0]["run_provenance"]["manifest_sha256"], manifest_digest(manifest))

    def test_postflight_failure_does_not_discard_returned_evidence(self):
        manifest = fixture()
        provider = Mock(configuration={"fixed": True})
        report = VisualIdentityReport("ABSTAINED", (), "synthetic", "synthetic", "response", 1, 2, {"outcome": "ABSTAINED"})
        journal = []
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "IMG_0001.JPG").write_bytes(b"first")
            (root / "IMG_0002.JPG").write_bytes(b"second")
            def identify(request):
                (root / "IMG_0001.JPG").write_bytes(b"changed")
                return report
            provider.identify.side_effect = identify
            result = run_baseline(manifest, root, provider, upload_authorized=True, checkpoint=journal.append)
        self.assertEqual(result["source_integrity_after_run"], "failed")
        self.assertFalse(result["baseline_complete"])
        self.assertEqual(journal[1]["raw_provider_output"]["response_id"], "response")

    def test_manifest_digest_and_duplicate_json_keys(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            manifest = fixture()
            path.write_text(json.dumps(manifest), encoding="utf-8")
            path.with_suffix(".sha256").write_text(manifest_digest(manifest), encoding="ascii")
            self.assertEqual(load_manifest(path), manifest)
            manifest["specimens"][0]["ground_truth"]["year"]["value"] = "1964"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_manifest(path)
            path.write_text('{"schema":"a", "schema":"b"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_manifest(path)

    def test_frozen_synthetic_inventory_metadata_only(self):
        manifest = fixture()
        specimen = manifest["specimens"][0]
        manifest["specimens"] = []
        for index in range(10):
            row = deepcopy(specimen)
            row["specimen_id"] = f"CA-BENCH-{index + 1:03d}"
            row["images"] = [
                {"path": f"IMG_{1000 + index * 2 + side}.JPG", "role": role,
                 "sha256": digest(f"synthetic-{index}-{side}".encode())}
                for side, role in enumerate(("obverse", "reverse"))
            ]
            manifest["specimens"].append(row)
        manifest["specimens"][3]["ground_truth"]["year"] = {
            "value": None, "verification": "unverified"}
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            path.with_suffix(".sha256").write_text(manifest_digest(manifest), encoding="ascii")
            loaded = load_manifest(path)
        self.assertEqual(loaded, manifest)
        self.assertEqual([r["specimen_id"] for r in loaded["specimens"]],
                         [f"CA-BENCH-{i:03d}" for i in range(1, 11)])
        self.assertEqual({image["path"] for row in loaded["specimens"] for image in row["images"]},
                         {f"IMG_{i}.JPG" for i in range(1000, 1020)})
        self.assertEqual(loaded["specimens"][3]["ground_truth"]["year"]["verification"], "unverified")
