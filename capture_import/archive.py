"""Read-only ZIP boundary validation for immutable capture-package snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
import stat
import struct
from typing import BinaryIO
import unicodedata
import zipfile
import zlib

from .errors import (
    ArchiveNameCollision,
    ManifestMissing,
    PackageNotZip,
    PackageTooLarge,
    UnsafeArchiveEntry,
)
from .validation_limits import ValidationLimits

MANIFEST_NAME = "capture_package.json"
_SUPPORTED_COMPRESSION = frozenset({zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED})
# Deflate compression options (bits 1-2) and UTF-8 names (bit 11) are the only
# general-purpose features understood by v0.2. Data descriptors are rejected:
# the mobile writer records CRC and sizes directly in each local header.
_SUPPORTED_FLAG_MASK = 0x0806
_WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)


@dataclass(frozen=True, slots=True)
class ArchiveEntry:
    """One canonical central-directory record with no extraction path."""

    name: str
    is_directory: bool
    compressed_size: int
    uncompressed_size: int
    compression_type: int
    crc32: int


@dataclass(frozen=True, slots=True)
class ValidatedArchiveIndex:
    """Immutable, collision-free view of an accepted ZIP directory."""

    package_basename: str
    entries: tuple[ArchiveEntry, ...]

    def entry(self, name: str) -> ArchiveEntry | None:
        return next((entry for entry in self.entries if entry.name == name), None)

    @property
    def files(self) -> tuple[ArchiveEntry, ...]:
        return tuple(entry for entry in self.entries if not entry.is_directory)

    @property
    def directories(self) -> tuple[ArchiveEntry, ...]:
        return tuple(entry for entry in self.entries if entry.is_directory)


class CapturePackageArchiveReader:
    """Validate ZIP metadata and expose only bounded entry reads."""

    def __init__(self, limits: ValidationLimits | None = None) -> None:
        self.limits = limits or ValidationLimits()

    def validate(self, package: BinaryIO, package_basename: str) -> tuple[zipfile.ZipFile, ValidatedArchiveIndex]:
        if not isinstance(package_basename, str) or not package_basename.lower().endswith(".ca-package"):
            raise PackageNotZip()
        if "/" in package_basename or "\\" in package_basename or "\x00" in package_basename:
            raise PackageNotZip()
        try:
            package.seek(0, 2)
            package_size = package.tell()
            if not 1 <= package_size <= self.limits.package_size:
                raise PackageTooLarge()
            package.seek(0)
            archive = zipfile.ZipFile(package, mode="r")
            infos = archive.infolist()
        except PackageTooLarge:
            raise
        except (OSError, ValueError, zipfile.BadZipFile) as error:
            raise PackageNotZip(error) from error
        try:
            if not infos or len(infos) > self.limits.archive_entries:
                raise PackageTooLarge()
            if archive.comment:
                raise UnsafeArchiveEntry()
            self._require_single_disk_eof(package, len(infos))
            if min(info.header_offset for info in infos) != 0:
                raise PackageNotZip()
            records = self._validate_records(infos)
            self._validate_local_headers(package, infos, archive.start_dir)
            return archive, ValidatedArchiveIndex(package_basename, records)
        except Exception:
            archive.close()
            raise

    def read_entry(
        self,
        archive: zipfile.ZipFile,
        entry: ArchiveEntry,
        maximum_bytes: int,
    ) -> bytes:
        """Read one regular entry with independent streamed-size enforcement."""

        if entry.is_directory:
            raise UnsafeArchiveEntry()
        payload = bytearray()
        try:
            with archive.open(entry.name, "r") as stream:
                while True:
                    chunk = stream.read(min(1024 * 1024, maximum_bytes + 1 - len(payload)))
                    if not chunk:
                        break
                    payload.extend(chunk)
                    if len(payload) > maximum_bytes:
                        raise PackageTooLarge()
        except PackageTooLarge:
            raise
        except (
            EOFError,
            OSError,
            RuntimeError,
            ValueError,
            zipfile.BadZipFile,
            zlib.error,
        ) as error:
            raise UnsafeArchiveEntry(error) from error
        if len(payload) != entry.uncompressed_size:
            raise UnsafeArchiveEntry()
        return bytes(payload)

    def _validate_records(self, infos: list[zipfile.ZipInfo]) -> tuple[ArchiveEntry, ...]:
        raw_names: set[str] = set()
        canonical_names: set[str] = set()
        path_kinds: dict[str, bool] = {}
        records: list[ArchiveEntry] = []
        total_compressed = 0
        total_uncompressed = 0
        manifest_count = 0
        for info in infos:
            name = self._validate_name(info.orig_filename)
            normalized = unicodedata.normalize("NFC", name)
            canonical = self._windows_path_key(name)
            if name in raw_names or canonical in canonical_names:
                raise ArchiveNameCollision()
            raw_names.add(name)
            canonical_names.add(canonical)
            is_directory = info.is_dir()
            self._validate_metadata(info, is_directory)
            canonical_path = canonical[:-1] if is_directory else canonical
            if canonical_path in path_kinds or any(
                prefix in path_kinds and not path_kinds[prefix]
                for prefix in self._parent_prefixes(canonical_path)
            ):
                raise ArchiveNameCollision()
            if not is_directory and any(
                existing.startswith(canonical_path + "/") for existing in path_kinds
            ):
                raise ArchiveNameCollision()
            path_kinds[canonical_path] = is_directory
            total_compressed += info.compress_size
            total_uncompressed += info.file_size
            if total_uncompressed > self.limits.total_uncompressed_bytes:
                raise PackageTooLarge()
            if total_uncompressed > max(total_compressed, 1) * self.limits.compression_ratio:
                raise PackageTooLarge()
            if canonical == self._windows_path_key(MANIFEST_NAME):
                if normalized != MANIFEST_NAME or is_directory:
                    raise ArchiveNameCollision()
                manifest_count += 1
            records.append(
                ArchiveEntry(
                    name=name,
                    is_directory=is_directory,
                    compressed_size=info.compress_size,
                    uncompressed_size=info.file_size,
                    compression_type=info.compress_type,
                    crc32=info.CRC,
                )
            )
        if manifest_count != 1:
            raise ManifestMissing()
        manifest = next(record for record in records if record.name == MANIFEST_NAME)
        if manifest.uncompressed_size > self.limits.manifest_bytes:
            raise PackageTooLarge()
        return tuple(
            sorted(
                records,
                key=lambda item: (self._windows_path_key(item.name), item.name),
            )
        )

    def _validate_metadata(self, info: zipfile.ZipInfo, is_directory: bool) -> None:
        sizes = (
            info.file_size,
            info.compress_size,
            info.header_offset,
            info.CRC,
            getattr(info, "volume", 0),
        )
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in sizes):
            raise UnsafeArchiveEntry()
        if getattr(info, "volume", 0) != 0:
            raise UnsafeArchiveEntry()
        if info.compress_type not in _SUPPORTED_COMPRESSION:
            raise UnsafeArchiveEntry()
        if info.flag_bits & ~_SUPPORTED_FLAG_MASK:
            raise UnsafeArchiveEntry()
        if info.compress_type != zipfile.ZIP_DEFLATED and info.flag_bits & 0x0006:
            raise UnsafeArchiveEntry()
        if info.compress_size > self.limits.compressed_entry_bytes:
            raise PackageTooLarge()
        if info.file_size and not info.compress_size:
            raise PackageTooLarge()
        if info.file_size > max(info.compress_size, 1) * self.limits.compression_ratio:
            raise PackageTooLarge()
        if info.comment or info.extra:
            raise UnsafeArchiveEntry()
        mode = (info.external_attr >> 16) & 0xFFFF
        kind = stat.S_IFMT(mode)
        if is_directory:
            if (
                not info.orig_filename.endswith("/")
                or kind not in {0, stat.S_IFDIR}
                or info.file_size != 0
                or info.CRC != 0
            ):
                raise UnsafeArchiveEntry()
        elif info.orig_filename.endswith("/") or kind not in {0, stat.S_IFREG}:
            raise UnsafeArchiveEntry()

    @staticmethod
    def _validate_name(name: str) -> str:
        if not name or "\x00" in name or name.startswith(("/", "\\")) or "\\" in name or ":" in name:
            raise UnsafeArchiveEntry()
        if any(ord(character) < 32 for character in name):
            raise UnsafeArchiveEntry()
        components = name[:-1].split("/") if name.endswith("/") else name.split("/")
        if not components or any(part in {"", ".", ".."} for part in components):
            raise UnsafeArchiveEntry()
        for component in components:
            if component.endswith((".", " ")):
                raise UnsafeArchiveEntry()
            if component.split(".", 1)[0].upper() in _WINDOWS_RESERVED:
                raise UnsafeArchiveEntry()
        return name

    @staticmethod
    def _parent_prefixes(name: str) -> tuple[str, ...]:
        parts = PurePosixPath(name).parts
        return tuple("/".join(parts[:index]) for index in range(1, len(parts)))

    @staticmethod
    def _windows_path_key(name: str) -> str:
        """Return the one namespace key used for every collision comparison."""

        return unicodedata.normalize("NFC", name).casefold()

    def _validate_local_headers(
        self,
        package: BinaryIO,
        infos: list[zipfile.ZipInfo],
        central_offset: int,
    ) -> None:
        """Require local records to agree with their central-directory records."""

        expected_offset = 0
        for info in sorted(infos, key=lambda item: item.header_offset):
            try:
                if info.header_offset != expected_offset:
                    raise UnsafeArchiveEntry()
                package.seek(info.header_offset)
                fixed = package.read(30)
                if len(fixed) != 30:
                    raise UnsafeArchiveEntry()
                (
                    signature,
                    _extract_version,
                    local_flags,
                    local_compression,
                    _modified_time,
                    _modified_date,
                    local_crc,
                    local_compressed,
                    local_uncompressed,
                    name_length,
                    extra_length,
                ) = struct.unpack("<4s5H3L2H", fixed)
                if signature != b"PK\x03\x04":
                    raise UnsafeArchiveEntry()
                local_name = package.read(name_length)
                if len(local_name) != name_length:
                    raise UnsafeArchiveEntry()
                local_extra = package.read(extra_length)
                if len(local_extra) != extra_length:
                    raise UnsafeArchiveEntry()
                data_start = info.header_offset + 30 + name_length + extra_length
                data_end = data_start + info.compress_size
                if data_end > central_offset:
                    raise UnsafeArchiveEntry()
                encoding = "utf-8" if info.flag_bits & 0x0800 else "cp437"
                if local_name != info.orig_filename.encode(encoding):
                    raise UnsafeArchiveEntry()
                if local_flags != info.flag_bits or local_compression != info.compress_type:
                    raise UnsafeArchiveEntry()
                if (
                    local_crc != info.CRC
                    or local_compressed != info.compress_size
                    or local_uncompressed != info.file_size
                ):
                    raise UnsafeArchiveEntry()
                if local_extra != info.extra or local_extra:
                    raise UnsafeArchiveEntry()
                year, month, day, hour, minute, second = info.date_time
                datetime(year, month, day, hour, minute, second)
                central_time = (hour << 11) | (minute << 5) | (second // 2)
                central_date = ((year - 1980) << 9) | (month << 5) | day
                if (
                    _modified_time != central_time
                    or _modified_date != central_date
                ):
                    raise UnsafeArchiveEntry()
                if info.is_dir():
                    self._validate_directory_payload(
                        package,
                        info,
                        data_start,
                    )
                expected_offset = data_end
            except UnsafeArchiveEntry:
                raise
            except (OSError, OverflowError, UnicodeError, struct.error, ValueError) as error:
                raise UnsafeArchiveEntry(error) from error
        if expected_offset != central_offset:
            raise UnsafeArchiveEntry()

    @staticmethod
    def _validate_directory_payload(
        package: BinaryIO,
        info: zipfile.ZipInfo,
        data_start: int,
    ) -> None:
        """Require a directory entry to encode exactly one empty stream."""

        try:
            package.seek(data_start)
            compressed = package.read(info.compress_size)
            if len(compressed) != info.compress_size:
                raise UnsafeArchiveEntry()
            if info.compress_type == zipfile.ZIP_STORED:
                if compressed:
                    raise UnsafeArchiveEntry()
                return
            if info.compress_type != zipfile.ZIP_DEFLATED:
                raise UnsafeArchiveEntry()
            decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
            output = decompressor.decompress(compressed, 1)
            if (
                output
                or not decompressor.eof
                or decompressor.unconsumed_tail
                or decompressor.unused_data
                or decompressor.flush(1)
            ):
                raise UnsafeArchiveEntry()
        except UnsafeArchiveEntry:
            raise
        except (EOFError, OSError, ValueError, zlib.error) as error:
            raise UnsafeArchiveEntry(error) from error

    @staticmethod
    def _require_single_disk_eof(package: BinaryIO, expected_entries: int) -> None:
        package.seek(0, 2)
        size = package.tell()
        tail_size = min(size, 65_557)
        package.seek(size - tail_size)
        tail = package.read(tail_size)
        marker = tail.rfind(b"PK\x05\x06")
        if marker < 0 or marker + 22 > len(tail):
            raise PackageNotZip()
        comment_length = int.from_bytes(tail[marker + 20 : marker + 22], "little")
        if marker + 22 + comment_length != len(tail):
            raise PackageNotZip()
        disk_number = int.from_bytes(tail[marker + 4 : marker + 6], "little")
        central_disk = int.from_bytes(tail[marker + 6 : marker + 8], "little")
        disk_entries = int.from_bytes(tail[marker + 8 : marker + 10], "little")
        total_entries = int.from_bytes(tail[marker + 10 : marker + 12], "little")
        central_size = int.from_bytes(tail[marker + 12 : marker + 16], "little")
        central_offset = int.from_bytes(tail[marker + 16 : marker + 20], "little")
        marker_offset = size - tail_size + marker
        if (
            disk_number != 0
            or central_disk != 0
            or disk_entries != expected_entries
            or total_entries != expected_entries
            or total_entries == 0xFFFF
            or central_size == 0xFFFFFFFF
            or central_offset == 0xFFFFFFFF
            or central_offset + central_size != marker_offset
        ):
            raise PackageNotZip()
