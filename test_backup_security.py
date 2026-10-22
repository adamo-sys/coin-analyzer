"""SEC-001/002: bounded synthetic archives; never read real collection data."""

import hashlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import tempfile
import unittest
import warnings
import zipfile
from unittest.mock import patch

import backup_manager as bm
from persistence_manager import PersistenceManager


class BackupSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.destination = self.root / "restore"
        self.destination.mkdir()
        self.manager = bm.BackupManager(
            backup_dir=str(self.root / "backups"),
            persistence_manager=PersistenceManager(state_dir=str(self.root / "state")),
            collection_json_path=str(self.root / "source.json"),
        )
        self.package = self.root / "input.zip"

    def archive(self, entries, manifest=None, extra=()):
        rows = [dict(source_path="synthetic", archive_path=name, size_bytes=len(data),
                     sha256=hashlib.sha256(data).hexdigest()) for name, data in entries]
        payload = dict(backup_created_at="2026-10-21", included_files=rows)
        if manifest is not None:
            payload = manifest
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.package, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, data in [*entries, *extra]:
                    archive.writestr(name, data)
                archive.writestr(bm.MANIFEST_NAME, json.dumps(payload))
        return self.package

    def restore(self):
        return self.manager.restore_from_backup_package(
            str(self.package), str(self.destination), overwrite=True)

    def test_traversal_and_windows_names_fail_before_restore(self):
        for name in (
            "collection_data/app_state/../../escape.txt", "../escape", "/absolute",
            "C:/drive", "C:relative", "//server/share", "\\\\server\\share",
            "data\\collection.json", "data//collection.json", "data/./collection.json",
            "data/collection.json:stream", "data/NUL.json", "data/file.",
            "data/file ", "data/COM1.txt", "data/\x01bad", "data/CONIN$",
        ):
            with self.subTest(name=name):
                self.archive([(name, b"synthetic")])
                self.assertFalse(self.manager.verify_backup_package(str(self.package)).success)
                self.assertFalse(self.restore().success)
                self.assertEqual(list(self.destination.iterdir()), [])

    def test_prefix_lookalikes_and_unintended_subtrees_are_never_restored(self):
        self.archive([(name, b"synthetic") for name in (
            "data/collection.json.evil", "data/collection.json/subtree",
            "collection_data/app_state/unintended/payload.json",
            "collection_data/app_state/unexpected.json")])
        result = self.restore()
        self.assertTrue(result.success, result.errors)
        self.assertEqual(result.restored_files, [])
        self.assertEqual(len(result.skipped_files), 4)
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_duplicates_case_aliases_and_file_directory_conflicts_fail(self):
        for names in (("data/collection.json", "data/collection.json"),
                      ("data/collection.json", "DATA/collection.json"),
                      ("data/collection.json", "data/collection.json/child")):
            with self.subTest(names=names):
                self.archive([(name, b"x") for name in names])
                self.assertFalse(self.manager.verify_backup_package(str(self.package)).success)

    def test_archive_symlink_is_rejected(self):
        link = zipfile.ZipInfo("data/collection.json")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.archive([])
        with zipfile.ZipFile(self.package, "a") as archive:
            archive.writestr(link, b"../sentinel")
        self.assertFalse(self.manager.verify_backup_package(str(self.package)).success)

    def test_traversal_restore_preserves_root_sentinel(self):
        sentinel = self.destination / "sentinel.txt"
        sentinel.write_bytes(b"sentinel")
        self.archive([("collection_data/app_state/../../sentinel.txt", b"replacement")])
        result = self.restore()
        self.assertEqual(sentinel.read_bytes(), b"sentinel")
        self.assertFalse(result.success)

    def test_manifest_schema_and_duplicate_rows_fail(self):
        for payload in ([], {"included_files": "wrong"}, {"included_files": [None]},
                        {"included_files": [{"archive_path": "data/collection.json",
                                             "size_bytes": -1}]},
                        {"included_files": [{"archive_path": "data/collection.json"}] * 2}):
            with self.subTest(payload=payload):
                self.archive([("data/collection.json", b"x")], manifest=payload)
                self.assertFalse(self.manager.verify_backup_package(str(self.package)).success)

    def test_resource_limits_with_small_fixtures(self):
        cases = (
            ("MAX_BACKUP_ENTRIES", 2, [("a", b"x"), ("b", b"y")]),
            ("MAX_BACKUP_MANIFEST_BYTES", 16, [("data/collection.json", b"x")]),
            ("MAX_BACKUP_FILE_BYTES", 1000, [("data/collection.json", b"x" * 1001)]),
            ("MAX_BACKUP_EXPANDED_BYTES", 1500, [("a", b"x" * 800), ("b", b"y" * 800)]),
            ("MAX_BACKUP_ARCHIVE_BYTES", 32, [("data/collection.json", b"x")]),
            ("MAX_BACKUP_RATIO", 2, [("data/collection.json", b"x" * 8192)]),
        )
        for limit, value, entries in cases:
            with self.subTest(limit=limit):
                self.archive(entries)
                with patch.object(bm, limit, value, create=True):
                    self.assertFalse(self.manager.verify_backup_package(str(self.package)).success)
                    self.assertFalse(self.restore().success)
                self.assertEqual(list(self.destination.iterdir()), [])

    def test_corrupt_archive_and_failed_verification_preserve_sentinel(self):
        target = self.destination / "data" / "collection.json"
        target.parent.mkdir()
        target.write_bytes(b"sentinel")
        self.archive([("data/collection.json", b"replacement")], manifest={
            "included_files": [dict(archive_path="data/collection.json", size_bytes=11,
                                     sha256="0" * 64)]})
        self.assertFalse(self.manager.verify_backup_package(str(self.package)).success)
        self.assertFalse(self.restore().success)
        self.assertEqual(target.read_bytes(), b"sentinel")
        self.package.write_bytes(self.package.read_bytes()[:-25])
        self.assertFalse(self.restore().success)
        self.assertEqual(target.read_bytes(), b"sentinel")

    def test_valid_legacy_package_missing_optional_metadata_and_checksum(self):
        self.archive([("data/collection.json", b"[]")], manifest={
            "included_files": [dict(archive_path="data/collection.json", size_bytes=2)]})
        result = self.restore()
        self.assertTrue(result.success, result.errors)
        self.assertEqual((self.destination / "data/collection.json").read_bytes(), b"[]")

    def test_existing_source_and_destination_remain_compatible(self):
        from test_backup_manager import make_managers, write_collection_json
        from persistence_manager import AppState
        persistence, manager, collection = make_managers(str(self.destination))
        write_collection_json(collection)
        self.assertTrue(persistence.save_state(AppState()).success)
        package = manager.create_backup_package()
        result = manager.restore_from_backup_package(package.package_path, str(self.destination), True)
        self.assertTrue(result.success, result.errors)

    def test_second_publication_failure_rolls_back_originals(self):
        entries = [("data/collection.json", b"new-collection"),
                   ("collection_data/app_state/app_state.json", b"new-state")]
        for name, _ in entries:
            target = self.destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"sentinel")
        self.archive(entries)
        rename = bm._rename_restore_file
        publications = 0

        def fail_second(handle, parent, source, destination):
            nonlocal publications
            if source.endswith(".new"):
                publications += 1
                if publications == 2:
                    raise OSError("injected second publication failure")
            return rename(handle, parent, source, destination)

        with patch.object(bm, "_rename_restore_file", side_effect=fail_second):
            result = self.restore()
        self.assertFalse(result.success)
        for name, _ in entries:
            self.assertEqual((self.destination / name).read_bytes(), b"sentinel")
        self.assertEqual(list(self.destination.rglob(".backup-restore-*")), [])

    def test_failed_pre_restore_backup_preserves_original(self):
        target = self.destination / "data/collection.json"
        target.parent.mkdir()
        target.write_bytes(b"sentinel")
        self.archive([("data/collection.json", b"new")])
        with patch.object(self.manager, "create_backup_package", return_value=bm.BackupResult(False, "injected")):
            self.assertFalse(self.restore().success)
        self.assertEqual(target.read_bytes(), b"sentinel")
        self.assertEqual(list(self.destination.rglob(".backup-restore-*")), [])

    def test_package_substitution_after_validation_cannot_change_staged_bytes(self):
        self.archive([("data/collection.json", b"verified")])
        create = self.manager.create_backup_package

        def substitute(*args, **kwargs):
            self.archive([("data/collection.json", b"substituted")])
            return create(*args, **kwargs)

        with patch.object(self.manager, "create_backup_package", side_effect=substitute):
            result = self.restore()
        self.assertTrue(result.success, result.errors)
        self.assertEqual((self.destination / "data/collection.json").read_bytes(), b"verified")

    def test_actual_stream_bytes_are_enforced_even_if_metadata_lies(self):
        from types import SimpleNamespace
        class Archive:
            def open(self, info):
                return io.BytesIO(b"x" * 65)
        info = SimpleNamespace(filename="data/collection.json", file_size=1)
        with self.assertRaises(ValueError):
            bm._read_backup_member(Archive(), info, 64)

    def test_new_destination_race_preserves_competing_file(self):
        self.archive([("data/collection.json", b"replacement")])
        rename = bm._rename_restore_file
        injected = False

        def introduce_sentinel(handle, parent, source, destination):
            nonlocal injected
            if source.endswith(".new") and not injected:
                injected = True
                (parent.path / destination).write_bytes(b"competing-sentinel")
            return rename(handle, parent, source, destination)

        with patch.object(bm, "_rename_restore_file", side_effect=introduce_sentinel):
            self.assertFalse(self.restore().success)
        self.assertEqual((self.destination / "data/collection.json").read_bytes(), b"competing-sentinel")
        self.assertEqual(list(self.destination.rglob(".backup-restore-*")), [])

    def test_existing_destination_substitution_during_pre_backup_fails_closed(self):
        target = self.destination / "data/collection.json"
        target.parent.mkdir()
        target.write_bytes(b"original")
        self.archive([("data/collection.json", b"replacement")])
        create = self.manager.create_backup_package

        def substitute(*args, **kwargs):
            target.rename(target.with_name("moved-original"))
            target.write_bytes(b"competing-sentinel")
            return create(*args, **kwargs)

        with patch.object(self.manager, "create_backup_package", side_effect=substitute):
            self.assertFalse(self.restore().success)
        self.assertEqual(target.read_bytes(), b"competing-sentinel")
        self.assertEqual(target.with_name("moved-original").read_bytes(), b"original")
        self.assertEqual(list(self.destination.rglob(".backup-restore-*")), [])

    @unittest.skipUnless(os.name == "nt", "Windows directory sharing contract")
    def test_windows_ancestor_rename_is_blocked_during_publication(self):
        self.archive([("data/collection.json", b"verified")])
        rename = bm._rename_restore_file
        blocked = False

        def substitute(handle, parent, source, destination):
            nonlocal blocked
            try:
                parent.path.rename(parent.path.with_name("moved-parent"))
            except OSError:
                blocked = True
            return rename(handle, parent, source, destination)

        with patch.object(bm, "_rename_restore_file", side_effect=substitute):
            result = self.restore()
        self.assertTrue(result.success, result.errors)
        self.assertTrue(blocked)
        self.assertFalse((self.destination / "moved-parent").exists())
        self.assertEqual((self.destination / "data/collection.json").read_bytes(), b"verified")

    def test_corrupt_member_data_fails_before_destination_changes(self):
        self.archive([("data/collection.json", b"synthetic content")])
        with zipfile.ZipFile(self.package) as archive:
            offset = archive.getinfo("data/collection.json").header_offset
        raw = bytearray(self.package.read_bytes())
        name_length, extra_length = struct.unpack_from("<HH", raw, offset + 26)
        raw[offset + 30 + name_length + extra_length] ^= 0xFF
        self.package.write_bytes(raw)
        self.assertFalse(self.restore().success)
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_dishonest_entry_count_and_oversized_central_directory_fail(self):
        self.archive([("a", b"x"), ("b", b"y")])
        original = self.package.read_bytes()
        marker = original.rfind(b"PK\x05\x06")
        raw = bytearray(original)
        struct.pack_into("<HH", raw, marker + 8, 1, 1)
        self.package.write_bytes(raw)
        self.assertFalse(self.manager.verify_backup_package(str(self.package)).success)
        self.package.write_bytes(original)
        with patch.object(bm, "MAX_BACKUP_CENTRAL_BYTES", 46):
            self.assertFalse(self.manager.verify_backup_package(str(self.package)).success)

    def test_alternate_zip64_directory_is_rejected_before_reader_allocation(self):
        # Independent review reproduction: the locator is hidden inside a
        # classic central-entry comment, redirecting ZipFile to a second index.
        with io.BytesIO() as buffer:
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr(bm.MANIFEST_NAME, b'{"included_files": []}')
                archive.writestr("u0", b"")
            raw = buffer.getvalue()
        end = struct.unpack("<4s4H2LH", raw[-22:])
        central_size, central_offset = end[5:7]
        base = raw[:-22]
        header = bytearray(raw[central_offset:central_offset + 46])
        struct.pack_into("<3H", header, 28, 1, 0, 20)
        decoy = bytes(header) + b"x" + struct.pack("<4sLQL", b"PK\x06\x07", 0, len(base), 1)
        zip64 = struct.pack("<4sQ2H2L4Q", b"PK\x06\x06", 44 + len(decoy) - 20,
                            45, 45, 0, 0, 2, 2, central_size, central_offset)
        for comment in (b"", b"X" * 65535):
            with self.subTest(comment_length=len(comment)):
                classic_end = struct.pack("<4s4H2LH", b"PK\x05\x06", 0, 0, 1, 1,
                                          len(decoy), len(base) + len(zip64), len(comment))
                self.package.write_bytes(base + zip64 + decoy + classic_end + comment)
                with patch.object(bm.zipfile, "ZipFile", side_effect=AssertionError("reader allocated")):
                    result = self.manager.verify_backup_package(str(self.package))
                self.assertFalse(result.success)
                self.assertIn("ZIP64", " ".join(result.errors))

    def test_duplicate_json_fields_and_deep_manifest_fail(self):
        for payload in (b'{"included_files":[],"included_files":[]}',
                        b'{"included_files":[],"unknown":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}'):
            with self.subTest(length=len(payload)):
                with zipfile.ZipFile(self.package, "w") as archive:
                    archive.writestr(bm.MANIFEST_NAME, payload)
                self.assertFalse(self.restore().success)
                self.assertEqual(list(self.destination.iterdir()), [])

    def test_small_force_zip64_and_highly_compressible_data_remain_compatible(self):
        self.archive([("data/collection.json", b"0" * 100000)])
        self.assertTrue(self.manager.verify_backup_package(str(self.package)).success)
        self.assertTrue(self.restore().success)
        with zipfile.ZipFile(self.package, "w") as archive:
            with archive.open("data/collection.json", "w", force_zip64=True) as member:
                member.write(b"[]")
            archive.writestr(bm.MANIFEST_NAME, json.dumps({"included_files": [
                dict(archive_path="data/collection.json", size_bytes=2)]}))
        self.assertTrue(self.manager.verify_backup_package(str(self.package)).success)

    def test_destination_hard_link_is_rejected_without_changing_linked_file(self):
        sentinel = self.root / "sentinel"
        sentinel.write_bytes(b"sentinel")
        target = self.destination / "data/collection.json"
        target.parent.mkdir()
        try:
            target.hardlink_to(sentinel)
        except OSError as exc:
            self.skipTest(f"hard link fixture unavailable: {exc}")
        self.archive([("data/collection.json", b"replacement")])
        self.assertFalse(self.restore().success)
        self.assertEqual(sentinel.read_bytes(), b"sentinel")

    def test_destination_symlink_or_junction_preserves_outside_sentinel(self):
        outside = self.root / "outside"
        outside.mkdir()
        sentinel = outside / "collection.json"
        sentinel.write_bytes(b"sentinel")
        link = self.destination / "data"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            if os.name != "nt":
                self.skipTest(f"symlink unavailable: {exc}")
            import subprocess
            completed = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)],
                                       capture_output=True, text=True)
            if completed.returncode:
                self.skipTest("Windows junction fixture unavailable: " + completed.stderr)
        self.archive([("data/collection.json", b"replacement")])
        self.assertFalse(self.restore().success)
        self.assertEqual(sentinel.read_bytes(), b"sentinel")


if __name__ == "__main__":
    unittest.main()
