"""Focused tests for Sprint 7 workflow domain models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import tempfile
import unittest

from capture_import.workflow_models import (
    ImportConfiguration,
    ImportRequest,
    JsonValue,
    PreparedArtifactDescriptor,
    PreparedFile,
    PreparedImport,
    StageArtifact,
    StageInput,
    StageResult,
)


def make_request() -> ImportRequest:
    return ImportRequest(
        source=Path(tempfile.gettempdir()),
        collection_id="collection-1",
        configuration=ImportConfiguration(),
    )


def make_artifact(*, path: str = "test.txt") -> StageArtifact:
    return StageArtifact(relative_path=path, content_type="text/plain")


class ConstructionTests(unittest.TestCase):
    def test_import_configuration_construction(self) -> None:
        config = ImportConfiguration()
        config.validate()

    def test_import_request_construction(self) -> None:
        request = make_request()
        request.validate()
        self.assertTrue(request.source.is_absolute())
        self.assertEqual(request.collection_id, "collection-1")

    def test_stage_artifact_construction(self) -> None:
        artifact = make_artifact()
        artifact.validate()
        self.assertEqual(artifact.relative_path, "test.txt")
        self.assertEqual(artifact.content_type, "text/plain")

    def test_prepared_file_legacy_defaults_remain_valid(self) -> None:
        value = PreparedFile(relative_path="legacy.txt", expected_size=0)
        value.validate()
        self.assertIsNone(value.artifact_key)
        self.assertIsNone(value.producer_stage)
        self.assertEqual(value.durability_classification, "EPHEMERAL")

    def test_prepared_artifact_descriptor_is_immutable_and_closed(self) -> None:
        descriptor = PreparedArtifactDescriptor(
            artifact_key="normalized-coin-front",
            source_coin_id="coin",
            role="front",
            variant="NORMALIZED",
            content_type="image/jpeg",
            expected_byte_length=1,
            expected_sha256="a" * 64,
            workspace_relative_path="normalized/coin/front.jpg",
            root_identity=(1, 2),
            parent_identity=(1, 3),
            file_identity=(1, 4),
        )
        descriptor.validate()
        with self.assertRaises(FrozenInstanceError):
            descriptor.role = "reverse"  # type: ignore[misc]

    def test_prepared_artifact_descriptor_rejects_noncanonical_values(self) -> None:
        descriptor = PreparedArtifactDescriptor(
            artifact_key="key",
            source_coin_id="coin",
            role="front",
            variant="NORMALIZED",
            content_type="image/jpeg",
            expected_byte_length=1,
            expected_sha256="a" * 64,
            workspace_relative_path="normalized/coin/front.jpg",
            root_identity=(1, 2),
            parent_identity=(1, 3),
            file_identity=(1, 4),
        )
        invalid_values = (
            ("artifact_key", "e\u0301"),
            ("artifact_key", "x" * 256),
            ("source_coin_id", "bad\u0085"),
            ("role", "obverse"),
            ("variant", "RAW"),
            ("content_type", "image/png"),
            ("workspace_relative_path", "../escape.jpg"),
            ("workspace_relative_path", "normalized//front.jpg"),
            ("workspace_relative_path", "normalized/front.jpg "),
            ("workspace_relative_path", "normalized\\front.jpg"),
        )
        for field, invalid in invalid_values:
            with self.subTest(field=field, invalid=repr(invalid)):
                with self.assertRaises(ValueError):
                    replace(descriptor, **{field: invalid}).validate()

    def test_stage_input_construction(self) -> None:
        request = make_request()
        workspace = Path(tempfile.gettempdir())
        artifact = make_artifact()
        stage_input = StageInput(
            request=request,
            workspace=workspace,
            artifacts={"test": artifact},
        )
        stage_input.validate()
        self.assertEqual(stage_input.request, request)
        self.assertEqual(stage_input.workspace, workspace)
        self.assertEqual(stage_input.artifacts["test"], artifact)

    def test_stage_result_construction(self) -> None:
        artifact = make_artifact()
        result = StageResult(
            artifacts={"test": artifact},
            metadata={"key": "value"},
        )
        result.validate()
        self.assertEqual(result.artifacts["test"], artifact)
        self.assertEqual(result.metadata["key"], "value")

    def test_prepared_file_construction(self) -> None:
        file = PreparedFile(relative_path="images/test.jpg", expected_size=1024)
        file.validate()
        self.assertEqual(file.relative_path, "images/test.jpg")
        self.assertEqual(file.expected_size, 1024)
        self.assertIsNone(file.sha256)

    def test_prepared_file_with_sha256(self) -> None:
        sha = "a" * 64
        file = PreparedFile(
            relative_path="images/test.jpg",
            expected_size=1024,
            sha256=sha,
        )
        file.validate()
        self.assertEqual(file.sha256, sha)

    def test_prepared_import_construction(self) -> None:
        request = make_request()
        file = PreparedFile(relative_path="images/test.jpg", expected_size=1024)
        prepared = PreparedImport(
            request=request,
            files=(file,),
            metadata={"batch": 1},
        )
        prepared.validate()
        self.assertEqual(prepared.request, request)
        self.assertEqual(len(prepared.files), 1)


class ImmutabilityTests(unittest.TestCase):
    def test_all_models_with_fields_are_frozen(self) -> None:
        cases = [
            make_request(),
            make_artifact(),
            StageInput(
                request=make_request(),
                workspace=Path(tempfile.gettempdir()),
                artifacts={"test": make_artifact()},
            ),
            StageResult(
                artifacts={"test": make_artifact()},
                metadata={},
            ),
            PreparedFile(relative_path="test.txt", expected_size=0),
            PreparedImport(
                request=make_request(),
                files=(),
                metadata={},
            ),
        ]
        for value in cases:
            with self.subTest(model=type(value).__name__):
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, next(iter(value.__dataclass_fields__)), "changed")

    def test_import_configuration_is_frozen(self) -> None:
        config = ImportConfiguration()
        self.assertTrue(config.__dataclass_params__.frozen)


class PathValidationTests(unittest.TestCase):
    def test_relative_path_rejects_absolute(self) -> None:
        for invalid in ("/foo", "C:\\foo", "\\\\share\\foo"):
            with self.subTest(path=invalid):
                artifact = StageArtifact(relative_path=invalid)
                with self.assertRaises(ValueError):
                    artifact.validate()

    def test_relative_path_rejects_parent_traversal(self) -> None:
        for invalid in ("../foo", "foo/../bar", "foo/../../bar"):
            with self.subTest(path=invalid):
                artifact = StageArtifact(relative_path=invalid)
                with self.assertRaises(ValueError):
                    artifact.validate()

    def test_relative_path_rejects_empty_and_dot_components(self) -> None:
        for invalid in ("", ".", "./foo", "foo/./bar", "foo/", "foo//bar"):
            with self.subTest(path=invalid):
                artifact = StageArtifact(relative_path=invalid)
                with self.assertRaises(ValueError):
                    artifact.validate()

    def test_prepared_file_rejects_invalid_paths(self) -> None:
        for invalid in ("/foo", "../foo", "foo/./bar"):
            with self.subTest(path=invalid):
                file = PreparedFile(relative_path=invalid, expected_size=1)
                with self.assertRaises(ValueError):
                    file.validate()

    def test_import_request_rejects_relative_source(self) -> None:
        request = replace(make_request(), source=Path("relative/path"))
        with self.assertRaises(ValueError):
            request.validate()

    def test_stage_input_rejects_relative_workspace(self) -> None:
        stage_input = StageInput(
            request=make_request(),
            workspace=Path("relative/path"),
            artifacts={},
        )
        with self.assertRaises(ValueError):
            stage_input.validate()


class ArtifactMappingTests(unittest.TestCase):
    def test_artifact_mapping_rejects_non_string_keys(self) -> None:
        stage_input = StageInput(
            request=make_request(),
            workspace=Path(tempfile.gettempdir()),
            artifacts={1: make_artifact()},  # type: ignore[dict-item]
        )
        with self.assertRaises(ValueError):
            stage_input.validate()

    def test_artifact_mapping_rejects_non_artifact_values(self) -> None:
        stage_input = StageInput(
            request=make_request(),
            workspace=Path(tempfile.gettempdir()),
            artifacts={"test": "not-an-artifact"},  # type: ignore[dict-item]
        )
        with self.assertRaises(ValueError):
            stage_input.validate()


class MetadataValidationTests(unittest.TestCase):
    def test_valid_json_metadata(self) -> None:
        result = StageResult(
            artifacts={},
            metadata={
                "string": "value",
                "int": 42,
                "float": 3.14,
                "bool": True,
                "null": None,
                "list": [1, 2, 3],
                "nested": {"a": 1},
            },
        )
        result.validate()

    def test_metadata_rejects_non_string_keys(self) -> None:
        result = StageResult(
            artifacts={},
            metadata={1: "value"},  # type: ignore[dict-item]
        )
        with self.assertRaises(ValueError):
            result.validate()

    def test_metadata_rejects_invalid_value_types(self) -> None:
        for invalid in ({"key": object()}, {"key": b"bytes"}, {"key": {1: 2}}):
            with self.subTest(value=invalid):
                result = StageResult(artifacts={}, metadata=invalid)  # type: ignore[arg-type]
                with self.assertRaises(ValueError):
                    result.validate()

    def test_metadata_rejects_non_finite_float(self) -> None:
        result = StageResult(
            artifacts={},
            metadata={"inf": float("inf")},
        )
        with self.assertRaises(ValueError):
            result.validate()


class PreparedFileValidationTests(unittest.TestCase):
    def test_expected_size_must_be_non_negative_integer(self) -> None:
        for invalid in (-1, True, "string", 3.14):
            with self.subTest(value=invalid):
                file = PreparedFile(relative_path="test.txt", expected_size=invalid)  # type: ignore[arg-type]
                with self.assertRaises(ValueError):
                    file.validate()

    def test_sha256_must_be_valid_hex(self) -> None:
        for invalid in ("short", "G" * 64, "A" * 64):
            with self.subTest(value=invalid):
                file = PreparedFile(
                    relative_path="test.txt",
                    expected_size=1,
                    sha256=invalid,
                )
                with self.assertRaises(ValueError):
                    file.validate()


class DefensiveCollectionTests(unittest.TestCase):
    def test_tuple_field_rejects_list(self) -> None:
        file = PreparedFile(relative_path="test.txt", expected_size=1)
        prepared = PreparedImport(
            request=make_request(),
            files=[file],  # type: ignore[list-item]
            metadata={},
        )
        with self.assertRaises(ValueError):
            prepared.validate()

    def test_dict_accepted_for_mapping(self) -> None:
        result = StageResult(
            artifacts={"test": make_artifact()},
            metadata={"key": "value"},
        )
        result.validate()  # Should not raise


class EqualityTests(unittest.TestCase):
    def test_hashable_models_equal_when_values_equal(self) -> None:
        a = make_request()
        b = ImportRequest(
            source=Path(tempfile.gettempdir()),
            collection_id="collection-1",
            configuration=ImportConfiguration(),
        )
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))

    def test_models_are_not_equal_when_values_differ(self) -> None:
        a = make_request()
        b = replace(a, collection_id="different")
        self.assertNotEqual(a, b)

    def test_stage_artifact_equality(self) -> None:
        a = make_artifact(path="a.txt")
        b = make_artifact(path="a.txt")
        c = make_artifact(path="b.txt")
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))
        self.assertNotEqual(a, c)

    def test_prepared_file_equality(self) -> None:
        a = PreparedFile(relative_path="test.txt", expected_size=1)
        b = PreparedFile(relative_path="test.txt", expected_size=1)
        c = PreparedFile(relative_path="test.txt", expected_size=2)
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))
        self.assertNotEqual(a, c)


class JsonValueTypeTests(unittest.TestCase):
    def test_json_value_accepts_primitive_types(self) -> None:
        primitives: list[JsonValue] = [
            "string",
            42,
            3.14,
            True,
            False,
            None,
            [1, 2, 3],
            {"a": 1},
            {"nested": {"list": [1, 2, 3]}},
        ]
        for value in primitives:
            with self.subTest(value=value):
                result = StageResult(artifacts={}, metadata={"test": value})
                result.validate()


class NestedArtifactRegressionTests(unittest.TestCase):
    def test_stage_result_rejects_nested_parent_traversal(self) -> None:
        result = StageResult(
            artifacts={"bad": StageArtifact(relative_path="../escape")},
            metadata={},
        )
        with self.assertRaisesRegex(ValueError, "safe relative"):
            result.validate()

    def test_stage_result_rejects_nested_absolute_path(self) -> None:
        result = StageResult(
            artifacts={"bad": StageArtifact(relative_path="/etc/passwd")},
            metadata={},
        )
        with self.assertRaisesRegex(ValueError, "safe relative"):
            result.validate()

    def test_stage_input_rejects_nested_invalid_artifact(self) -> None:
        stage_input = StageInput(
            request=make_request(),
            workspace=Path(tempfile.gettempdir()),
            artifacts={"bad": StageArtifact(relative_path="foo/../../bar")},
        )
        with self.assertRaisesRegex(ValueError, "safe relative"):
            stage_input.validate()

    def test_nested_valid_artifact_still_passes(self) -> None:
        result = StageResult(
            artifacts={"good": StageArtifact(relative_path="images/coin/front.jpg")},
            metadata={},
        )
        result.validate()  # Should not raise


if __name__ == "__main__":
    unittest.main()
