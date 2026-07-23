"""Focused tests for Sprint 8 Unit 6 image duplicate detection."""

from __future__ import annotations

import ast
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from unittest import mock

import capture_import.workflow_image_duplicates as duplicate_module
from capture_import.enums import (
    DuplicateCategory,
    DuplicateConfidence,
    ImageRole,
)
from capture_import.workflow_execution import ImportWorkflow
from capture_import.workflow_image_duplicates import (
    IMAGE_DUPLICATE_DETECTION_STAGE_ID,
    PREPARED_MANIFEST_ARTIFACT,
    PREPARED_MANIFEST_NAME,
    CollectionImageDescriptor,
    ImageDuplicateDetectionStage,
)
from capture_import.workflow_models import (
    ImportConfiguration,
    ImportRequest,
    StageArtifact,
    StageInput,
    StageResult,
)
from capture_import.workflow_pipeline import (
    ProcessingPipeline,
    StageContractError,
    StageExecutionError,
    WorkflowCancelledError,
)
from tests.capture_package_fixtures import image_bytes, manifest_dict


class FakeDescriptorSource:
    def __init__(
        self,
        values: tuple[CollectionImageDescriptor, ...] = (),
        *,
        error: Exception | None = None,
    ) -> None:
        self.values = values
        self.error = error
        self.calls = 0
        self.consumed = 0

    def iter_descriptors(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        for value in self.values:
            self.consumed += 1
            yield value


def _manifest_for(coin_ids: tuple[str, ...]) -> dict[str, object]:
    value = manifest_dict()
    template = value["coins"][0]  # type: ignore[index]
    coins: list[object] = []
    for position, coin_id in enumerate(coin_ids):
        coin = copy.deepcopy(template)
        coin["id"] = coin_id  # type: ignore[index]
        coin["position"] = position  # type: ignore[index]
        coin["photos"]["front"]["path"] = f"images/{coin_id}-front.jpg"  # type: ignore[index]
        coin["photos"]["front"]["mime_type"] = "image/jpeg"  # type: ignore[index]
        coin["photos"]["reverse"]["path"] = f"images/{coin_id}-reverse.jpg"  # type: ignore[index]
        coins.append(coin)
    value["coins"] = coins
    return value


def _write_inputs(
    workspace: Path,
    *,
    images: dict[tuple[str, str], bytes],
    manifest: dict[str, object] | None = None,
) -> dict[str, StageArtifact]:
    coin_ids = tuple(sorted({coin_id for coin_id, _ in images}))
    manifest_value = manifest or _manifest_for(coin_ids)
    manifest_path = workspace / PREPARED_MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(
            manifest_value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    artifacts = {
        PREPARED_MANIFEST_ARTIFACT: StageArtifact(
            relative_path=PREPARED_MANIFEST_NAME,
            content_type="application/json",
        )
    }
    for (coin_id, role), payload in images.items():
        relative_path = f"normalized/{coin_id}/{role}.jpg"
        target = workspace / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        artifacts[f"normalized-{coin_id}-{role}"] = StageArtifact(
            relative_path=relative_path,
            content_type="image/jpeg",
        )
    return artifacts


def _stage_input(
    workspace: Path,
    artifacts: dict[str, StageArtifact],
) -> StageInput:
    return StageInput(
        request=ImportRequest(
            source=workspace / "source.ca-package",
            collection_id="collection-1",
            configuration=ImportConfiguration(),
        ),
        workspace=workspace,
        artifacts=artifacts,
    )


def _jpeg(color: tuple[int, int, int]) -> bytes:
    from PIL import Image

    output = BytesIO()
    Image.new("RGB", (40, 40), color).save(
        output,
        format="JPEG",
        quality=92,
        progressive=False,
    )
    return output.getvalue()


def _noncanonical_jpeg(kind: str) -> bytes:
    from PIL import Image

    output = BytesIO()
    if kind == "progressive":
        Image.new("RGB", (40, 40), (10, 20, 30)).save(
            output, format="JPEG", progressive=True
        )
    elif kind == "exif":
        exif = Image.Exif()
        exif[0x010E] = "not canonical"
        Image.new("RGB", (40, 40), (10, 20, 30)).save(
            output, format="JPEG", exif=exif
        )
    elif kind == "icc":
        Image.new("RGB", (40, 40), (10, 20, 30)).save(
            output, format="JPEG", icc_profile=b"test-profile"
        )
    elif kind == "cmyk":
        Image.new("CMYK", (40, 40), (10, 20, 30, 40)).save(
            output, format="JPEG"
        )
    else:
        raise AssertionError(f"unknown noncanonical JPEG kind: {kind}")
    return output.getvalue()


def _descriptor(
    desktop_id: str,
    *,
    front: bytes | None = None,
    reverse: bytes | None = None,
) -> CollectionImageDescriptor:
    pairs: list[tuple[ImageRole, str]] = []
    if front is not None:
        pairs.append((ImageRole.FRONT, sha256(front).hexdigest()))
    if reverse is not None:
        pairs.append((ImageRole.REVERSE, sha256(reverse).hexdigest()))
    return CollectionImageDescriptor(desktop_id, tuple(pairs))


class CollectionImageDescriptorTests(unittest.TestCase):
    def test_valid_descriptor(self) -> None:
        _descriptor(
            "desktop-1",
            front=b"front",
            reverse=b"reverse",
        ).validate()

    def test_rejects_unsafe_desktop_id(self) -> None:
        with self.assertRaises(ValueError):
            _descriptor("../desktop", front=b"front").validate()

    def test_rejects_invalid_hash(self) -> None:
        value = CollectionImageDescriptor(
            "desktop-1",
            ((ImageRole.FRONT, "not-a-sha"),),
        )
        with self.assertRaises(ValueError):
            value.validate()

    def test_rejects_duplicate_or_unsorted_roles(self) -> None:
        digest = sha256(b"x").hexdigest()
        with self.assertRaises(ValueError):
            CollectionImageDescriptor(
                "desktop-1",
                (
                    (ImageRole.FRONT, digest),
                    (ImageRole.FRONT, digest),
                ),
            ).validate()
        with self.assertRaises(ValueError):
            CollectionImageDescriptor(
                "desktop-1",
                (
                    (ImageRole.REVERSE, digest),
                    (ImageRole.FRONT, digest),
                ),
            ).validate()


class ImageDuplicateDetectionStageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        self.front_a = _jpeg((180, 120, 80))
        self.reverse_a = _jpeg((80, 120, 180))
        self.front_b = _jpeg((20, 40, 60))
        self.reverse_b = _jpeg((60, 40, 20))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def execute(
        self,
        images: dict[tuple[str, str], bytes],
        *,
        source: FakeDescriptorSource | None = None,
        manifest: dict[str, object] | None = None,
    ) -> StageResult:
        artifacts = _write_inputs(
            self.workspace,
            images=images,
            manifest=manifest,
        )
        return ImageDuplicateDetectionStage(
            descriptor_source=source
        ).execute(_stage_input(self.workspace, artifacts))

    def test_category_is_additive_and_stable(self) -> None:
        self.assertEqual(
            DuplicateCategory.NORMALIZED_MEDIA_HASHES.value,
            "NORMALIZED_MEDIA_HASHES",
        )
        self.assertEqual(DuplicateCategory.PACKAGE_REPLAY.value, "PACKAGE_REPLAY")
        self.assertEqual(DuplicateCategory.MEDIA_HASHES.value, "MEDIA_HASHES")

    def test_within_package_front_and_reverse_match_is_exact(self) -> None:
        result = self.execute(
            {
                ("coin-1", "front"): self.front_a,
                ("coin-1", "reverse"): self.reverse_a,
                ("coin-2", "front"): self.front_a,
                ("coin-2", "reverse"): self.reverse_a,
            }
        )
        candidates = result.metadata["image_duplicate_candidates"]
        self.assertEqual(result.metadata["image_duplicate_candidate_count"], 2)
        self.assertEqual(
            [value["source_coin_id"] for value in candidates],
            ["coin-1", "coin-2"],
        )
        for candidate in candidates:
            self.assertEqual(candidate["category"], "NORMALIZED_MEDIA_HASHES")
            self.assertEqual(candidate["confidence"], "EXACT")
            self.assertEqual(candidate["matched_desktop_ids"], [])
            self.assertEqual(candidate["total_matches"], 1)

    def test_within_package_one_role_match_is_medium(self) -> None:
        result = self.execute(
            {
                ("coin-1", "front"): self.front_a,
                ("coin-1", "reverse"): self.reverse_a,
                ("coin-2", "front"): self.front_a,
                ("coin-2", "reverse"): self.reverse_b,
            }
        )
        candidates = result.metadata["image_duplicate_candidates"]
        self.assertEqual(len(candidates), 2)
        self.assertTrue(
            all(value["confidence"] == DuplicateConfidence.MEDIUM.value for value in candidates)
        )
        self.assertTrue(
            all("front" in value["reasons"][0] for value in candidates)
        )

    def test_collection_front_and_reverse_match_is_exact(self) -> None:
        source = FakeDescriptorSource(
            (
                _descriptor(
                    "desktop-1",
                    front=self.front_a,
                    reverse=self.reverse_a,
                ),
            )
        )
        result = self.execute(
            {
                ("coin-1", "front"): self.front_a,
                ("coin-1", "reverse"): self.reverse_a,
            },
            source=source,
        )
        candidate = result.metadata["image_duplicate_candidates"][0]
        self.assertEqual(candidate["confidence"], "EXACT")
        self.assertEqual(candidate["matched_desktop_ids"], ["desktop-1"])
        self.assertEqual(source.calls, 1)

    def test_collection_one_role_match_is_medium(self) -> None:
        source = FakeDescriptorSource(
            (
                _descriptor(
                    "desktop-1",
                    front=self.front_a,
                    reverse=self.reverse_b,
                ),
            )
        )
        result = self.execute(
            {
                ("coin-1", "front"): self.front_a,
                ("coin-1", "reverse"): self.reverse_a,
            },
            source=source,
        )
        candidate = result.metadata["image_duplicate_candidates"][0]
        self.assertEqual(candidate["confidence"], "MEDIUM")
        self.assertEqual(candidate["matched_desktop_ids"], ["desktop-1"])

    def test_nonidentical_normalized_bytes_do_not_match(self) -> None:
        result = self.execute(
            {
                ("coin-1", "front"): self.front_a,
                ("coin-1", "reverse"): self.reverse_a,
                ("coin-2", "front"): self.front_b,
                ("coin-2", "reverse"): self.reverse_b,
            }
        )
        self.assertEqual(result.metadata["image_duplicate_candidate_count"], 0)
        self.assertEqual(result.metadata["image_duplicate_candidates"], [])

    def test_valid_normalization_stage_jpeg_is_accepted(self) -> None:
        result = self.execute(
            {
                ("coin-1", "front"): self.front_a,
                ("coin-1", "reverse"): self.reverse_a,
            }
        )
        self.assertEqual(result.metadata["image_duplicate_candidates"], [])

    def test_rejects_noncanonical_normalized_jpegs(self) -> None:
        invalid_values = {
            "appended": self.front_a + b"hidden",
            "concatenated": self.front_a + self.reverse_a,
            "progressive": _noncanonical_jpeg("progressive"),
            "exif": _noncanonical_jpeg("exif"),
            "icc": _noncanonical_jpeg("icc"),
            "cmyk": _noncanonical_jpeg("cmyk"),
        }
        for label, payload in invalid_values.items():
            with self.subTest(label=label), self.assertRaises(StageContractError):
                self.execute(
                    {
                        ("coin-1", "front"): payload,
                        ("coin-1", "reverse"): self.reverse_a,
                    }
                )

    def test_truncated_normalized_jpeg_is_an_execution_failure(self) -> None:
        with self.assertRaises(StageExecutionError):
            self.execute(
                {
                    ("coin-1", "front"): self.front_a[:-2],
                    ("coin-1", "reverse"): self.reverse_a,
                }
            )

    def test_unexpected_jpeg_validator_failure_is_not_mislabeled(self) -> None:
        with (
            mock.patch.object(
                duplicate_module,
                "require_complete_jpeg",
                side_effect=RuntimeError("unexpected validator failure"),
            ),
            self.assertRaises(StageExecutionError),
        ):
            self.execute(
                {
                    ("coin-1", "front"): self.front_a,
                    ("coin-1", "reverse"): self.reverse_a,
                }
            )

    def test_malformed_prepared_json_fails_closed(self) -> None:
        artifacts = _write_inputs(
            self.workspace,
            images={
                ("coin-1", "front"): self.front_a,
                ("coin-1", "reverse"): self.reverse_a,
            },
        )
        (self.workspace / PREPARED_MANIFEST_NAME).write_bytes(b"{not-json")
        with self.assertRaises(StageContractError):
            ImageDuplicateDetectionStage().execute(
                _stage_input(self.workspace, artifacts)
            )

    def test_cropped_artifacts_do_not_replace_normalized_hash_inputs(self) -> None:
        images = {
            ("coin-1", "front"): self.front_a,
            ("coin-1", "reverse"): self.reverse_a,
            ("coin-2", "front"): self.front_b,
            ("coin-2", "reverse"): self.reverse_b,
        }
        artifacts = _write_inputs(self.workspace, images=images)
        for coin_id in ("coin-1", "coin-2"):
            for role, payload in (
                ("front", self.front_a),
                ("reverse", self.reverse_a),
            ):
                path = self.workspace / f"cropped/{coin_id}/{role}.jpg"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
                artifacts[f"cropped-{coin_id}-{role}"] = StageArtifact(
                    relative_path=f"cropped/{coin_id}/{role}.jpg",
                    content_type="image/jpeg",
                )
        result = ImageDuplicateDetectionStage().execute(
            _stage_input(self.workspace, artifacts)
        )
        self.assertEqual(result.metadata["image_duplicate_candidate_count"], 0)

    def test_output_is_deterministic_for_reversed_inputs(self) -> None:
        descriptors = (
            _descriptor("desktop-b", front=self.front_a),
            _descriptor("desktop-a", front=self.front_a),
        )
        images = {
            ("coin-2", "reverse"): self.reverse_b,
            ("coin-1", "front"): self.front_a,
            ("coin-2", "front"): self.front_a,
            ("coin-1", "reverse"): self.reverse_a,
        }
        first_artifacts = _write_inputs(self.workspace, images=images)
        first = ImageDuplicateDetectionStage(
            descriptor_source=FakeDescriptorSource(descriptors)
        ).execute(_stage_input(self.workspace, first_artifacts))
        second = ImageDuplicateDetectionStage(
            descriptor_source=FakeDescriptorSource(tuple(reversed(descriptors)))
        ).execute(
            _stage_input(
                self.workspace,
                dict(reversed(tuple(first_artifacts.items()))),
            )
        )
        self.assertEqual(first.metadata, second.metadata)

    def test_descriptor_lookup_is_bounded_one_beyond_limit(self) -> None:
        source = FakeDescriptorSource(
            tuple(
                _descriptor(f"desktop-{index}", front=self.front_b)
                for index in range(3)
            )
        )
        with (
            mock.patch.object(
                duplicate_module,
                "MAX_DUPLICATE_EXISTING_ITEMS",
                2,
            ),
            self.assertRaises(StageContractError),
        ):
            self.execute(
                {
                    ("coin-1", "front"): self.front_a,
                    ("coin-1", "reverse"): self.reverse_a,
                },
                source=source,
            )
        self.assertEqual(source.consumed, 3)

    def test_candidate_ids_are_bounded_but_total_matches_remains_exact(self) -> None:
        descriptors = tuple(
            _descriptor(
                f"desktop-{index:02d}",
                front=self.front_a,
                reverse=self.reverse_a,
            )
            for index in range(duplicate_module.MAX_DUPLICATE_MATCHED_IDS + 3)
        )
        result = self.execute(
            {
                ("coin-1", "front"): self.front_a,
                ("coin-1", "reverse"): self.reverse_a,
            },
            source=FakeDescriptorSource(tuple(reversed(descriptors))),
        )
        candidate = result.metadata["image_duplicate_candidates"][0]
        self.assertEqual(
            len(candidate["matched_desktop_ids"]),
            duplicate_module.MAX_DUPLICATE_MATCHED_IDS,
        )
        self.assertEqual(candidate["total_matches"], len(descriptors))
        self.assertEqual(
            candidate["matched_desktop_ids"],
            sorted(candidate["matched_desktop_ids"]),
        )

    def test_exact_precedes_medium_for_the_same_source(self) -> None:
        source = FakeDescriptorSource(
            (
                _descriptor(
                    "desktop-medium",
                    front=self.front_a,
                    reverse=self.reverse_b,
                ),
                _descriptor(
                    "desktop-exact",
                    front=self.front_a,
                    reverse=self.reverse_a,
                ),
            )
        )
        result = self.execute(
            {
                ("coin-1", "front"): self.front_a,
                ("coin-1", "reverse"): self.reverse_a,
            },
            source=source,
        )
        self.assertEqual(
            [
                candidate["confidence"]
                for candidate in result.metadata["image_duplicate_candidates"]
            ],
            ["EXACT", "MEDIUM"],
        )

    def test_descriptor_source_failure_is_not_silently_ignored(self) -> None:
        source = FakeDescriptorSource(error=RuntimeError("lookup failed"))
        with self.assertRaises(StageExecutionError) as raised:
            self.execute(
                {
                    ("coin-1", "front"): self.front_a,
                    ("coin-1", "reverse"): self.reverse_a,
                },
                source=source,
            )
        self.assertEqual(
            raised.exception.stage_id,
            IMAGE_DUPLICATE_DETECTION_STAGE_ID,
        )

    def test_duplicate_desktop_ids_fail_closed(self) -> None:
        descriptor = _descriptor("desktop-1", front=self.front_a)
        source = FakeDescriptorSource((descriptor, descriptor))
        with self.assertRaises(StageContractError):
            self.execute(
                {
                    ("coin-1", "front"): self.front_a,
                    ("coin-1", "reverse"): self.reverse_a,
                },
                source=source,
            )

    def test_missing_manifest_artifact_raises(self) -> None:
        with self.assertRaises(StageContractError):
            ImageDuplicateDetectionStage().execute(
                _stage_input(self.workspace, {})
            )

    def test_missing_required_normalized_artifact_raises(self) -> None:
        artifacts = _write_inputs(
            self.workspace,
            images={
                ("coin-1", "front"): self.front_a,
                ("coin-1", "reverse"): self.reverse_a,
            },
        )
        artifacts.pop("normalized-coin-1-reverse")
        with self.assertRaises(StageContractError):
            ImageDuplicateDetectionStage().execute(
                _stage_input(self.workspace, artifacts)
            )

    def test_missing_declared_file_raises(self) -> None:
        artifacts = _write_inputs(
            self.workspace,
            images={
                ("coin-1", "front"): self.front_a,
                ("coin-1", "reverse"): self.reverse_a,
            },
        )
        (self.workspace / "normalized/coin-1/reverse.jpg").unlink()
        with self.assertRaises(StageContractError):
            ImageDuplicateDetectionStage().execute(
                _stage_input(self.workspace, artifacts)
            )

    def test_invalid_normalized_mime_raises(self) -> None:
        artifacts = _write_inputs(
            self.workspace,
            images={
                ("coin-1", "front"): self.front_a,
                ("coin-1", "reverse"): self.reverse_a,
            },
        )
        artifacts["normalized-coin-1-front"] = StageArtifact(
            relative_path="normalized/coin-1/front.jpg",
            content_type="image/png",
        )
        with self.assertRaises(StageContractError):
            ImageDuplicateDetectionStage().execute(
                _stage_input(self.workspace, artifacts)
            )

    def test_unexpected_normalized_artifact_raises(self) -> None:
        artifacts = _write_inputs(
            self.workspace,
            images={
                ("coin-1", "front"): self.front_a,
                ("coin-1", "reverse"): self.reverse_a,
            },
        )
        artifacts["normalized-unknown-front"] = StageArtifact(
            relative_path="normalized/unknown/front.jpg",
            content_type="image/jpeg",
        )
        with self.assertRaises(StageContractError):
            ImageDuplicateDetectionStage().execute(
                _stage_input(self.workspace, artifacts)
            )


class ImageDuplicatePipelineTests(unittest.TestCase):
    def test_stage_conforms_to_protocol(self) -> None:
        stage = ImageDuplicateDetectionStage()
        pipeline = ProcessingPipeline((stage,))
        self.assertEqual(
            pipeline.stage_ids,
            (IMAGE_DUPLICATE_DETECTION_STAGE_ID,),
        )

    def test_stage_module_does_not_import_collection_models(self) -> None:
        source = Path(duplicate_module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        } | {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        self.assertNotIn("coin_collection", imported_modules)

    def test_clean_import_does_not_load_collection_modules(self) -> None:
        command = (
            "import importlib, pathlib, sys, types; "
            "package=types.ModuleType('capture_import'); "
            "package.__path__=[str(pathlib.Path.cwd() / 'capture_import')]; "
            "sys.modules['capture_import']=package; "
            "import capture_import.workflow_image_duplicates; "
            "blocked=[name for name in sys.modules "
            "if name == 'coin_collection' or name.startswith('coin_collection.')]; "
            "print(','.join(sorted(blocked)))"
        )
        completed = subprocess.run(
            [sys.executable, "-B", "-c", command],
            cwd=Path(__file__).resolve().parents[1],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.stdout.strip(), "")

    def test_post_stage_cancellation_prevents_transaction_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            artifacts = _write_inputs(
                workspace,
                images={
                    ("coin-1", "front"): image_bytes("JPEG", (40, 40)),
                    ("coin-1", "reverse"): image_bytes("JPEG", (40, 40)),
                },
            )

            class ArtifactFeeder:
                stage_id = "artifact-feeder"

                def execute(self, stage_input: StageInput) -> StageResult:
                    return StageResult(artifacts=artifacts, metadata={})

            checks = {"count": 0}
            transaction_calls: list[object] = []

            def is_cancelled() -> bool:
                checks["count"] += 1
                return checks["count"] >= 4

            workflow = ImportWorkflow(
                ProcessingPipeline(
                    (
                        ArtifactFeeder(),
                        ImageDuplicateDetectionStage(),
                    )
                ),
                is_cancelled=is_cancelled,
            )
            request = _stage_input(workspace, {}).request
            with self.assertRaises(WorkflowCancelledError):
                workflow.execute(
                    request,
                    workspace,
                    transaction=transaction_calls.append,
                )
            self.assertEqual(transaction_calls, [])


if __name__ == "__main__":
    unittest.main()
