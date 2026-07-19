"""Exact-byte media and end-to-end read-only package validation tests."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from capture_import.errors import InvalidManifest, InvalidMedia, MediaMissing, PackageChanged, PackageTooLarge, UnreferencedArchiveEntry
from capture_import.media import CapturePackageMediaValidator
from capture_import.package import CapturePackageValidator
from capture_import.snapshot import CapturePackageSnapshotService
from capture_import.validation_limits import ValidationLimits
from tests.capture_package_fixtures import image_bytes, manifest_dict, package_bytes


class CapturePackageMediaValidatorTests(unittest.TestCase):
    def validate(self, payload: bytes, limits: ValidationLimits | None = None):
        return CapturePackageValidator(limits).validate_stream(
            BytesIO(payload),
            "show.ca-package",
            package_sha256=sha256(payload).hexdigest(),
            package_byte_length=len(payload),
        )

    def test_constructs_canonical_validated_package_for_jpeg_and_png(self) -> None:
        payload = package_bytes()
        result = self.validate(payload)
        self.assertEqual([item.role.value for item in result.media], ["front", "reverse"])
        self.assertEqual(result.package_sha256, sha256(payload).hexdigest())
        self.assertEqual(result.media[0].sha256, sha256(image_bytes()).hexdigest())
        self.assertEqual(result.media[0].archive_path, "images/front.png")

    def test_rejects_untrusted_stream_identity_metadata(self) -> None:
        payload = package_bytes()
        with self.assertRaises(PackageChanged):
            CapturePackageValidator().validate_stream(
                BytesIO(payload),
                "show.ca-package",
                package_sha256="0" * 64,
                package_byte_length=len(payload),
            )

    def test_rejects_missing_reused_and_unreferenced_entries(self) -> None:
        value = manifest_dict()
        value["coins"][0]["photos"]["reverse"]["path"] = "images/missing.jpg"  # type: ignore[index]
        with self.assertRaises(MediaMissing):
            self.validate(package_bytes(manifest=value))
        value = manifest_dict()
        value["coins"][0]["photos"]["reverse"] = {  # type: ignore[index]
            **value["coins"][0]["photos"]["front"],  # type: ignore[index]
            "mime_type": "image/png",
        }
        with self.assertRaises(InvalidManifest):
            self.validate(package_bytes(manifest=value))
        with self.assertRaises(UnreferencedArchiveEntry):
            self.validate(package_bytes(extras={"hidden.txt": b"payload"}))

    def test_rejects_declared_mismatch_corruption_and_trailing_payload(self) -> None:
        value = manifest_dict()
        value["coins"][0]["photos"]["front"]["byte_length"] += 1  # type: ignore[index,operator]
        with self.assertRaises(InvalidMedia):
            self.validate(package_bytes(manifest=value))
        corrupt = b"\x89PNG\r\n\x1a\ncorrupt"
        value = manifest_dict(corrupt, image_bytes("JPEG"))
        with self.assertRaises(InvalidMedia):
            self.validate(package_bytes(manifest=value, front=corrupt))
        trailing = image_bytes() + b"hidden"
        value = manifest_dict(trailing, image_bytes("JPEG"))
        with self.assertRaises(InvalidMedia):
            self.validate(package_bytes(manifest=value, front=trailing))

    def test_jpeg_parser_requires_first_image_to_consume_exact_payload(self) -> None:
        jpeg = image_bytes("JPEG")
        cases = (
            ("bytes-after-eoi", jpeg + b"hidden"),
            ("payload-plus-second-eoi", jpeg + b"hidden\xff\xd9"),
            ("concatenated-jpeg", jpeg + jpeg),
            ("truncated-entropy-stream", jpeg[:-2]),
        )
        for label, hostile in cases:
            with self.subTest(label=label):
                value = manifest_dict(image_bytes(), hostile)
                with self.assertRaises(InvalidMedia):
                    self.validate(
                        package_bytes(manifest=value, reverse=hostile)
                    )
        value = manifest_dict(image_bytes(), jpeg)
        result = self.validate(package_bytes(manifest=value, reverse=jpeg))
        self.assertEqual(result.media[1].mime_type, "image/jpeg")

    def test_jpeg_parser_preserves_supported_marker_and_scan_behavior(self) -> None:
        progressive_output = BytesIO()
        Image.new("RGB", (2, 3), (20, 40, 60)).save(
            progressive_output, format="JPEG", progressive=True
        )
        progressive = progressive_output.getvalue()
        app_segment = b"\xff\xe1\x00\x06APP!"
        comment_segment = b"\xff\xfe\x00\x06COM!"
        baseline = image_bytes("JPEG")
        for label, accepted in (
            ("progressive-multiple-sos", progressive),
            ("app-segment", baseline[:2] + app_segment + baseline[2:]),
            ("comment-segment", baseline[:2] + comment_segment + baseline[2:]),
        ):
            with self.subTest(label=label):
                value = manifest_dict(image_bytes(), accepted)
                result = self.validate(
                    package_bytes(manifest=value, reverse=accepted)
                )
                self.assertEqual(result.media[1].sha256, sha256(accepted).hexdigest())

        parser_only_valid = (
            b"\xff\xd8"
            b"\xff\xda\x00\x02"
            b"entropy\xff\x00stuffed\xff\xd0restart"
            b"\xff\xda\x00\x02second-scan"
            b"\xff\xd9"
        )
        CapturePackageMediaValidator._require_complete_jpeg(parser_only_valid)

    def test_jpeg_parser_rejects_malformed_and_unsupported_streams_cleanly(self) -> None:
        hostile = (
            b"\xff\xd8\xff\xe1\x00\x01\xff\xd9",  # Invalid segment length.
            b"\xff\xd8\xff\xe1\x00\x10short",  # Premature EOF.
            b"\xff\xd8\xff\xd9",  # EOI before any scan.
            b"\xff\xd8\xff\xda\x00\x02entropy\xff\xd9hidden",  # Early EOI.
            b"\xff\xd8\xff\xc9\x00\x02\xff\xda\x00\x02\xff\xd9",  # Arithmetic SOF.
        )
        for payload in hostile:
            with self.subTest(payload=payload):
                with self.assertRaises(InvalidMedia):
                    CapturePackageMediaValidator()._validate_image(payload)

    def test_rejects_actual_dimension_and_pixel_limit_mismatch(self) -> None:
        large = image_bytes(size=(4, 4))
        value = manifest_dict(large, image_bytes("JPEG"))
        value["coins"][0]["photos"]["front"]["width"] = 4  # type: ignore[index]
        value["coins"][0]["photos"]["front"]["height"] = 4  # type: ignore[index]
        with self.assertRaises(PackageTooLarge):
            self.validate(
                package_bytes(manifest=value, front=large),
                ValidationLimits(image_pixels=15),
            )

    def test_validates_only_the_snapshot_and_detects_snapshot_change(self) -> None:
        payload = package_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "personal-name.ca-package"
            source.write_bytes(payload)
            service = CapturePackageSnapshotService(base / "snapshots")
            handle = service.create_snapshot(source, sha256(payload).hexdigest())
            try:
                result = CapturePackageValidator().validate_snapshot(handle, source.name)
                self.assertEqual(result.package_basename, source.name)
                source.write_bytes(b"changed original")
                CapturePackageValidator().validate_snapshot(handle, source.name)
                snapshot = base / "snapshots" / handle.descriptor.snapshot_token / "package.ca-package"
                snapshot.chmod(0o600)
                snapshot.write_bytes(payload[:-1] + b"x")
                with self.assertRaises(PackageChanged):
                    CapturePackageValidator().validate_snapshot(handle, source.name)
            finally:
                try:
                    snapshot = base / "snapshots" / handle.descriptor.snapshot_token / "package.ca-package"
                    if snapshot.exists():
                        snapshot.chmod(0o600)
                        snapshot.write_bytes(payload)
                    handle.cleanup()
                except Exception:
                    pass


if __name__ == "__main__":
    unittest.main()
