"""Hostile and happy-path tests for the ZIP archive boundary."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import struct
from unittest import mock
import unittest
import warnings
import zipfile
import zlib

from capture_import.archive import CapturePackageArchiveReader
from capture_import.errors import (
    ArchiveNameCollision,
    ManifestMissing,
    PackageNotZip,
    PackageTooLarge,
    UnsafeArchiveEntry,
)
from capture_import.enums import ErrorCategory
from capture_import.package import CapturePackageValidator
from capture_import.validation_limits import ValidationLimits
from tests.capture_package_fixtures import package_bytes


def _entry_data_range(payload: bytes, name: str) -> tuple[int, int]:
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        info = archive.getinfo(name)
        offset = info.header_offset
        fixed = payload[offset : offset + 30]
        name_length, extra_length = struct.unpack("<HH", fixed[26:30])
        start = offset + 30 + name_length + extra_length
        return start, start + info.compress_size


def _corrupt_entry(payload: bytes, name: str, mode: str) -> bytes:
    start, end = _entry_data_range(payload, name)
    changed = bytearray(payload)
    if mode == "zeros":
        changed[start:end] = b"\x00" * (end - start)
    elif mode == "last-byte":
        changed[end - 1] ^= 0xFF
    else:
        changed[start] ^= 0x01
    return bytes(changed)


class _UnseekableBytesIO(BytesIO):
    def seek(self, *args: object, **kwargs: object) -> int:
        raise OSError("stream is not seekable")


def _descriptor_archive() -> bytes:
    output = _UnseekableBytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("capture_package.json", b"{}")
    return output.getvalue()


def _eocd_and_central_offset(payload: bytes) -> tuple[int, int]:
    eocd = payload.rfind(b"PK\x05\x06")
    if eocd < 0:
        raise AssertionError("fixture has no EOCD")
    return eocd, struct.unpack_from("<L", payload, eocd + 16)[0]


def _replace_signed_descriptor(payload: bytes, replacement: bytes) -> bytes:
    _, central = _eocd_and_central_offset(payload)
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        info = archive.getinfo("capture_package.json")
    data_end = _entry_data_range(payload, info.filename)[1]
    if payload[data_end : data_end + 4] != b"PK\x07\x08":
        raise AssertionError("fixture has no signed descriptor")
    changed = bytearray(payload[:data_end] + replacement + payload[data_end + 16 :])
    new_eocd = changed.rfind(b"PK\x05\x06")
    struct.pack_into("<L", changed, new_eocd + 16, central + len(replacement) - 16)
    return bytes(changed)


def _insert_before_central(payload: bytes, hidden: bytes) -> bytes:
    _, central = _eocd_and_central_offset(payload)
    changed = bytearray(payload[:central] + hidden + payload[central:])
    new_eocd = changed.rfind(b"PK\x05\x06")
    struct.pack_into("<L", changed, new_eocd + 16, central + len(hidden))
    return bytes(changed)


def _insert_between_local_records(payload: bytes, hidden: bytes) -> bytes:
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        offsets = sorted(info.header_offset for info in archive.infolist())
    insertion = offsets[1]
    _, central = _eocd_and_central_offset(payload)
    changed = bytearray(payload[:insertion] + hidden + payload[insertion:])
    new_central = central + len(hidden)
    cursor = new_central
    while changed[cursor : cursor + 4] == b"PK\x01\x02":
        local_offset = struct.unpack_from("<L", changed, cursor + 42)[0]
        if local_offset >= insertion:
            struct.pack_into("<L", changed, cursor + 42, local_offset + len(hidden))
        name_length, extra_length, comment_length = struct.unpack_from(
            "<HHH", changed, cursor + 28
        )
        cursor += 46 + name_length + extra_length + comment_length
    new_eocd = changed.rfind(b"PK\x05\x06")
    struct.pack_into("<L", changed, new_eocd + 16, new_central)
    return bytes(changed)


def _replace_entry_payload(payload: bytes, name: str, replacement: bytes) -> bytes:
    """Replace one compressed payload while keeping ZIP offsets self-consistent."""

    with zipfile.ZipFile(BytesIO(payload)) as archive:
        target = archive.getinfo(name)
    start, end = _entry_data_range(payload, name)
    delta = len(replacement) - (end - start)
    _, central = _eocd_and_central_offset(payload)
    changed = bytearray(payload[:start] + replacement + payload[end:])
    struct.pack_into("<L", changed, target.header_offset + 18, len(replacement))
    new_central = central + delta
    cursor = new_central
    while changed[cursor : cursor + 4] == b"PK\x01\x02":
        name_length, extra_length, comment_length = struct.unpack_from(
            "<HHH", changed, cursor + 28
        )
        entry_name = bytes(changed[cursor + 46 : cursor + 46 + name_length])
        flags = struct.unpack_from("<H", changed, cursor + 8)[0]
        encoding = "utf-8" if flags & 0x0800 else "cp437"
        if entry_name.decode(encoding) == name:
            struct.pack_into("<L", changed, cursor + 20, len(replacement))
        local_offset = struct.unpack_from("<L", changed, cursor + 42)[0]
        if local_offset > target.header_offset:
            struct.pack_into("<L", changed, cursor + 42, local_offset + delta)
        cursor += 46 + name_length + extra_length + comment_length
    new_eocd = changed.rfind(b"PK\x05\x06")
    struct.pack_into("<L", changed, new_eocd + 16, new_central)
    return bytes(changed)


def _set_entry_crc(payload: bytes, name: str, crc: int) -> bytes:
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        target = archive.getinfo(name)
    changed = bytearray(payload)
    struct.pack_into("<L", changed, target.header_offset + 14, crc)
    _, central = _eocd_and_central_offset(payload)
    cursor = central
    while changed[cursor : cursor + 4] == b"PK\x01\x02":
        name_length, extra_length, comment_length = struct.unpack_from(
            "<HHH", changed, cursor + 28
        )
        entry_name = bytes(changed[cursor + 46 : cursor + 46 + name_length])
        flags = struct.unpack_from("<H", changed, cursor + 8)[0]
        encoding = "utf-8" if flags & 0x0800 else "cp437"
        if entry_name.decode(encoding) == name:
            struct.pack_into("<L", changed, cursor + 16, crc)
            break
        cursor += 46 + name_length + extra_length + comment_length
    return bytes(changed)


class CapturePackageArchiveReaderTests(unittest.TestCase):
    def test_accepts_valid_package_without_extracting(self) -> None:
        reader = CapturePackageArchiveReader()
        with mock.patch.object(zipfile.ZipFile, "extractall", side_effect=AssertionError):
            archive, index = reader.validate(BytesIO(package_bytes()), "show.ca-package")
            try:
                self.assertIsNotNone(index.entry("capture_package.json"))
                self.assertEqual(len(index.entries), 4)
            finally:
                archive.close()

    def test_rejects_wrong_extension_non_zip_and_trailing_payload(self) -> None:
        reader = CapturePackageArchiveReader()
        with self.assertRaises(PackageNotZip):
            reader.validate(BytesIO(package_bytes()), "show.zip")
        with self.assertRaises(PackageNotZip):
            reader.validate(BytesIO(b"not zip"), "show.ca-package")
        with self.assertRaises(PackageNotZip):
            reader.validate(BytesIO(package_bytes() + b"hidden"), "show.ca-package")
        with self.assertRaises(PackageNotZip):
            reader.validate(BytesIO(b"prefix" + package_bytes()), "show.ca-package")

    def test_enforces_entry_and_compression_budgets(self) -> None:
        payload = package_bytes()
        with self.assertRaises(PackageTooLarge):
            CapturePackageArchiveReader(
                ValidationLimits(package_size=len(payload) - 1)
            ).validate(BytesIO(payload), "show.ca-package")
        with self.assertRaises(PackageTooLarge):
            CapturePackageArchiveReader(ValidationLimits(archive_entries=3)).validate(
                BytesIO(package_bytes()), "show.ca-package"
            )
        compressed = package_bytes(extras={"bomb.bin": b"A" * 5000})
        with self.assertRaises(PackageTooLarge):
            CapturePackageArchiveReader(ValidationLimits(compression_ratio=2)).validate(
                BytesIO(compressed), "show.ca-package"
            )

    def test_requires_exact_root_manifest(self) -> None:
        output = BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("nested/capture_package.json", b"{}")
        with self.assertRaises(ManifestMissing):
            CapturePackageArchiveReader().validate(output, "show.ca-package")

    def test_rejects_duplicate_case_unicode_and_prefix_collisions(self) -> None:
        cases = (
            ("images/front.png", "images/front.png"),
            ("images/front.png", "IMAGES/FRONT.PNG"),
            ("images/caf\u00e9.png", "images/cafe\u0301.png"),
            ("images", "images/front.png"),
            ("images/front.png", "IMAGES"),
            ("IMAGES.jpg", "images.JPG/front.jpg"),
            ("images.JPG/front.jpg", "IMAGES.jpg"),
            ("CAF\u00c9", "cafe\u0301/child.jpg"),
            ("cafe\u0301/child.jpg", "CAF\u00c9"),
            ("images/I.jpg", "images/i.jpg"),
        )
        for first, second in cases:
            with self.subTest(first=first, second=second):
                output = BytesIO()
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    with zipfile.ZipFile(output, "w") as archive:
                        archive.writestr("capture_package.json", b"{}")
                        archive.writestr(first, b"x")
                        archive.writestr(second, b"x")
                with self.assertRaises(ArchiveNameCollision):
                    CapturePackageArchiveReader().validate(output, "show.ca-package")

    def test_rejects_unsafe_names_and_special_entries(self) -> None:
        unsafe_names = (
            "/absolute",
            "../escape",
            "a/../../escape",
            "a//empty",
            "C:/drive",
            "NUL.txt",
            "trail. /file",
        )
        for name in unsafe_names:
            with self.subTest(name=name):
                output = BytesIO()
                with zipfile.ZipFile(output, "w") as archive:
                    archive.writestr("capture_package.json", b"{}")
                    archive.writestr(name, b"x")
                with self.assertRaises(UnsafeArchiveEntry):
                    CapturePackageArchiveReader().validate(output, "show.ca-package")
        with self.assertRaises(UnsafeArchiveEntry):
            CapturePackageArchiveReader._validate_name("server\\share")
        with self.assertRaises(UnsafeArchiveEntry):
            CapturePackageArchiveReader._validate_name("nul\x00payload")
        for name in ("tail.", "tail ", "//start", "a//middle", "a//"):
            with self.subTest(name=name):
                with self.assertRaises(UnsafeArchiveEntry):
                    CapturePackageArchiveReader._validate_name(name)
        self.assertEqual(
            tuple(
                CapturePackageArchiveReader._windows_path_key(value)
                for value in ("I", "\u0130", "\u0131", "i")
            ),
            ("i", "i\u0307", "\u0131", "i"),
        )
        output = BytesIO()
        link = zipfile.ZipInfo("images/link.jpg")
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("capture_package.json", b"{}")
            archive.writestr(link, b"target")
        with self.assertRaises(UnsafeArchiveEntry):
            CapturePackageArchiveReader().validate(output, "show.ca-package")

    def test_rejects_unexpected_directory_during_complete_validation(self) -> None:
        from capture_import.errors import UnreferencedArchiveEntry
        from capture_import.package import CapturePackageValidator
        from hashlib import sha256

        payload = package_bytes(extras={"empty/": b""})
        with self.assertRaises(UnreferencedArchiveEntry):
            CapturePackageValidator().validate_stream(
                BytesIO(payload),
                "show.ca-package",
                package_sha256=sha256(payload).hexdigest(),
                package_byte_length=len(payload),
            )

    def test_rejects_encrypted_impossible_and_nonempty_directory_metadata(self) -> None:
        reader = CapturePackageArchiveReader()
        encrypted = zipfile.ZipInfo("image.jpg")
        encrypted.header_offset = 0
        encrypted.CRC = 0
        encrypted.flag_bits = 1
        with self.assertRaises(UnsafeArchiveEntry):
            reader._validate_metadata(encrypted, False)
        impossible = zipfile.ZipInfo("image.jpg")
        impossible.header_offset = 0
        impossible.CRC = 0
        impossible.file_size = -1
        with self.assertRaises(UnsafeArchiveEntry):
            reader._validate_metadata(impossible, False)
        directory = zipfile.ZipInfo("images/")
        directory.header_offset = 0
        directory.CRC = 0
        directory.file_size = 1
        directory.compress_size = 1
        with self.assertRaises(UnsafeArchiveEntry):
            reader._validate_metadata(directory, True)

    def test_defines_supported_flags_and_requires_zero_volume(self) -> None:
        reader = CapturePackageArchiveReader()
        for flags in (0x0002, 0x0004, 0x0800, 0x0806):
            with self.subTest(flags=hex(flags)):
                info = zipfile.ZipInfo("image.jpg")
                info.compress_type = zipfile.ZIP_DEFLATED
                info.flag_bits = flags
                info.file_size = 1
                info.compress_size = 1
                info.header_offset = 0
                info.CRC = 0
                info.volume = 0
                reader._validate_metadata(info, False)
        for flags in (0x0001, 0x0008, 0x0010, 0x0040, 0x2000):
            with self.subTest(flags=hex(flags)):
                info = zipfile.ZipInfo("image.jpg")
                info.flag_bits = flags
                info.header_offset = 0
                info.CRC = 0
                with self.assertRaises(UnsafeArchiveEntry):
                    reader._validate_metadata(info, False)
        nonzero_volume = zipfile.ZipInfo("image.jpg")
        nonzero_volume.header_offset = 0
        nonzero_volume.CRC = 0
        nonzero_volume.volume = 1
        with self.assertRaises(UnsafeArchiveEntry):
            reader._validate_metadata(nonzero_volume, False)

    def test_rejects_every_data_descriptor_form(self) -> None:
        signed = _descriptor_archive()
        with zipfile.ZipFile(BytesIO(signed)) as archive:
            info = archive.getinfo("capture_package.json")
        self.assertTrue(info.flag_bits & 0x0008)
        data_end = _entry_data_range(signed, info.filename)[1]
        descriptor = signed[data_end : data_end + 16]
        crc, compressed, uncompressed = struct.unpack_from("<LLL", descriptor, 4)
        variants = {
            "signed": signed,
            "unsigned": _replace_signed_descriptor(signed, descriptor[4:]),
            "corrupt-crc": _replace_signed_descriptor(
                signed, b"PK\x07\x08" + struct.pack("<LLL", crc ^ 1, compressed, uncompressed)
            ),
            "corrupt-compressed": _replace_signed_descriptor(
                signed, b"PK\x07\x08" + struct.pack("<LLL", crc, compressed + 1, uncompressed)
            ),
            "corrupt-uncompressed": _replace_signed_descriptor(
                signed, b"PK\x07\x08" + struct.pack("<LLL", crc, compressed, uncompressed + 1)
            ),
            "truncated": _replace_signed_descriptor(signed, descriptor[:8]),
            "zip64": _replace_signed_descriptor(
                signed, b"PK\x07\x08" + struct.pack("<LQQ", crc, compressed, uncompressed)
            ),
        }
        for label, payload in variants.items():
            with self.subTest(label=label):
                with self.assertRaises(UnsafeArchiveEntry):
                    CapturePackageArchiveReader().validate(
                        BytesIO(payload), "show.ca-package"
                    )

    def test_rejects_comments_extras_and_timestamp_disagreement(self) -> None:
        reader = CapturePackageArchiveReader()
        for attribute, value in (
            ("comment", b"comment"),
            ("extra", b"\x01\x00\x00\x00"),
            ("extra", b"\x01\x00\xff"),
        ):
            with self.subTest(attribute=attribute, value=value):
                info = zipfile.ZipInfo("capture_package.json")
                info.header_offset = 0
                info.CRC = 0
                setattr(info, attribute, value)
                with self.assertRaises(UnsafeArchiveEntry):
                    reader._validate_metadata(info, False)
        output = BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("capture_package.json", b"{}")
            archive.comment = b"archive comment"
        with self.assertRaises(UnsafeArchiveEntry):
            reader.validate(output, "show.ca-package")
        timestamp = bytearray(package_bytes())
        with zipfile.ZipFile(BytesIO(timestamp)) as archive:
            info = archive.getinfo("capture_package.json")
        local_time = struct.unpack_from("<H", timestamp, info.header_offset + 10)[0]
        struct.pack_into("<H", timestamp, info.header_offset + 10, local_time ^ 0x20)
        with self.assertRaises(UnsafeArchiveEntry):
            reader.validate(BytesIO(timestamp), "show.ca-package")

    def test_requires_contiguous_local_record_coverage(self) -> None:
        payload = package_bytes()
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            ordered = sorted(archive.infolist(), key=lambda item: item.header_offset)
        first_end = ordered[1].header_offset
        orphan = payload[:first_end]
        variants = {
            "inter-record-gap": _insert_between_local_records(payload, b"hidden"),
            "final-gap": _insert_before_central(payload, b"hidden"),
            "orphan-local-record": _insert_before_central(payload, orphan),
        }
        for label, hostile in variants.items():
            with self.subTest(label=label):
                with self.assertRaises(UnsafeArchiveEntry):
                    CapturePackageArchiveReader().validate(
                        BytesIO(hostile), "show.ca-package"
                    )

    def test_rejects_local_and_central_header_inconsistency(self) -> None:
        payload = bytearray(package_bytes())
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            info = archive.getinfo("capture_package.json")
        struct.pack_into("<H", payload, info.header_offset + 6, info.flag_bits ^ 0x0800)
        with self.assertRaises(UnsafeArchiveEntry):
            CapturePackageArchiveReader().validate(
                BytesIO(payload), "show.ca-package"
            )

    def test_validates_directory_compressed_stream_exactly(self) -> None:
        valid_cases = {
            "stored-empty": package_bytes(compression=zipfile.ZIP_STORED),
            "deflate-empty": package_bytes(),
        }
        for label, payload in valid_cases.items():
            with self.subTest(label=label):
                archive, _ = CapturePackageArchiveReader().validate(
                    BytesIO(payload), "show.ca-package"
                )
                archive.close()

        compressor = zlib.compressobj(level=6, wbits=-zlib.MAX_WBITS)
        nonempty_stream = compressor.compress(b"x") + compressor.flush()
        base = package_bytes()
        hostile_cases = {
            "corrupt": _replace_entry_payload(base, "images/", b"HI"),
            "truncated": _replace_entry_payload(base, "images/", b"\x03"),
            "no-eof": _replace_entry_payload(base, "images/", b"\x00\x00"),
            "trailing": _replace_entry_payload(base, "images/", b"\x03\x00hidden"),
            "nonempty-output": _replace_entry_payload(
                base, "images/", nonempty_stream
            ),
            "crc-mismatch": _set_entry_crc(base, "images/", 1),
        }
        for label, payload in hostile_cases.items():
            with self.subTest(label=label):
                with self.assertRaises(UnsafeArchiveEntry) as raised:
                    CapturePackageArchiveReader().validate(
                        BytesIO(payload), "show.ca-package"
                    )
                self.assertEqual(
                    raised.exception.category, ErrorCategory.ARCHIVE_ENTRY_UNSAFE
                )
                self.assertEqual(
                    str(raised.exception),
                    "The capture package contains an unsafe entry.",
                )
                self.assertNotIn("images/", str(raised.exception))

    def test_rejects_oversized_directory_payload_before_manifest_parsing(self) -> None:
        payload = package_bytes()
        validator = CapturePackageValidator(
            ValidationLimits(compressed_entry_bytes=1)
        )
        with mock.patch.object(
            validator.manifest_parser,
            "parse",
            side_effect=AssertionError("manifest parsing must not begin"),
        ) as parse:
            with self.assertRaises(PackageTooLarge):
                validator.validate_stream(
                    BytesIO(payload),
                    "show.ca-package",
                    package_sha256=sha256(payload).hexdigest(),
                    package_byte_length=len(payload),
                )
        parse.assert_not_called()

    def test_rejects_corrupt_directory_before_manifest_parsing(self) -> None:
        payload = _replace_entry_payload(package_bytes(), "images/", b"HI")
        validator = CapturePackageValidator()
        with mock.patch.object(
            validator.manifest_parser,
            "parse",
            side_effect=AssertionError("manifest parsing must not begin"),
        ) as parse:
            with self.assertRaises(UnsafeArchiveEntry):
                validator.validate_stream(
                    BytesIO(payload),
                    "show.ca-package",
                    package_sha256=sha256(payload).hexdigest(),
                    package_byte_length=len(payload),
                )
        parse.assert_not_called()

    def test_translates_corrupt_entry_streams_to_sanitized_error(self) -> None:
        cases = (
            ("invalid-deflate", _corrupt_entry(package_bytes(), "images/front.png", "zeros")),
            ("truncated-deflate", _corrupt_entry(package_bytes(), "images/front.png", "last-byte")),
            (
                "bad-crc",
                _corrupt_entry(
                    package_bytes(compression=zipfile.ZIP_STORED),
                    "images/front.png",
                    "first-byte",
                ),
            ),
        )
        for label, payload in cases:
            with self.subTest(label=label):
                with self.assertRaises(UnsafeArchiveEntry) as raised:
                    CapturePackageValidator().validate_stream(
                        BytesIO(payload),
                        "show.ca-package",
                        package_sha256=sha256(payload).hexdigest(),
                        package_byte_length=len(payload),
                    )
                self.assertEqual(
                    raised.exception.category, ErrorCategory.ARCHIVE_ENTRY_UNSAFE
                )
                self.assertEqual(
                    str(raised.exception),
                    "The capture package contains an unsafe entry.",
                )


if __name__ == "__main__":
    unittest.main()
