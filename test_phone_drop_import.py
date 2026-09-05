import os
from pathlib import Path

from phone_drop_import import PhoneDropImporter
from photo_inbox import PhotoInboxConfig, PhotoInboxManager


def _write(path: Path, content: bytes, *, mtime: float | None = None) -> None:
    path.write_bytes(content)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def test_import_copies_without_modifying_or_deleting_sources(tmp_path):
    source_dir = tmp_path / "phone"
    inbox_dir = tmp_path / "incoming"
    source_dir.mkdir()
    first = source_dir / "coin front.jpg"
    second = source_dir / "coin back.jpg"
    _write(first, b"front")
    _write(second, b"back")

    before = {first: first.read_bytes(), second: second.read_bytes()}
    result = PhoneDropImporter(str(inbox_dir)).import_files([str(first), str(second)])

    assert result.copied_count == 2
    assert result.duplicate_count == 0
    assert result.rejected_count == 0
    assert first.exists() and second.exists()
    assert first.read_bytes() == before[first]
    assert second.read_bytes() == before[second]
    assert all(Path(path).parent == inbox_dir for path in result.imported_paths)
    assert sorted(Path(path).read_bytes() for path in result.imported_paths) == [b"back", b"front"]


def test_same_stem_different_content_gets_distinct_collision_safe_names(tmp_path):
    source_a = tmp_path / "a"
    source_b = tmp_path / "b"
    inbox_dir = tmp_path / "incoming"
    source_a.mkdir()
    source_b.mkdir()
    first = source_a / "IMG_0001.JPG"
    second = source_b / "IMG_0001.JPG"
    _write(first, b"first-content")
    _write(second, b"second-content")

    result = PhoneDropImporter(str(inbox_dir)).import_files([str(first), str(second)])

    assert result.copied_count == 2
    destinations = [Path(item.destination_path) for item in result.imported]
    assert destinations[0].name != destinations[1].name
    assert all(path.exists() for path in destinations)
    assert all("--" in path.name for path in destinations)


def test_reimport_of_identical_source_is_reported_as_duplicate_without_overwrite(tmp_path):
    source = tmp_path / "coin.jpg"
    inbox_dir = tmp_path / "incoming"
    _write(source, b"same-image")
    importer = PhoneDropImporter(str(inbox_dir))

    first = importer.import_files([str(source)])
    destination = Path(first.imported[0].destination_path)
    original_destination_bytes = destination.read_bytes()
    second = importer.import_files([str(source)])

    assert first.copied_count == 1
    assert second.copied_count == 0
    assert second.duplicate_count == 1
    assert Path(second.duplicates[0].destination_path) == destination
    assert destination.read_bytes() == original_destination_bytes


def test_heic_and_heif_are_rejected_with_useful_conversion_message(tmp_path):
    heic = tmp_path / "phone.heic"
    heif = tmp_path / "phone.heif"
    _write(heic, b"heic")
    _write(heif, b"heif")

    result = PhoneDropImporter(str(tmp_path / "incoming")).import_files([str(heic), str(heif)])

    assert result.copied_count == 0
    assert result.rejected_count == 2
    for rejected in result.rejected:
        reason = rejected.reason.lower()
        assert "unsupported phone image format" in reason
        assert "jpeg" in reason
        assert "export or share" in reason


def test_imported_pair_is_discovered_and_grouped_by_photo_inbox(tmp_path):
    source_dir = tmp_path / "phone"
    inbox_dir = tmp_path / "incoming"
    state_path = tmp_path / "photo_inbox_state.json"
    source_dir.mkdir()
    front = source_dir / "1967-dollar-front.jpg"
    back = source_dir / "1967-dollar-back.jpg"
    shared_mtime = 1_800_000_000.0
    _write(front, b"front-photo", mtime=shared_mtime)
    _write(back, b"back-photo", mtime=shared_mtime + 1)

    import_result = PhoneDropImporter(str(inbox_dir)).import_files([str(front), str(back)])
    assert import_result.copied_count == 2

    manager = PhotoInboxManager(
        config=PhotoInboxConfig(
            inbox_folder=str(inbox_dir),
            state_path=str(state_path),
            file_stability_seconds=0,
            grouping_window_seconds=90,
        )
    )
    scan = manager.refresh()
    pending = manager.get_pending_sets()

    assert scan.discovered == 2
    assert len(pending) == 1
    photos = manager.get_photo_set_photos(pending[0].id)
    assert len(photos) == 2
    assert {Path(photo.path).read_bytes() for photo in photos} == {b"front-photo", b"back-photo"}
