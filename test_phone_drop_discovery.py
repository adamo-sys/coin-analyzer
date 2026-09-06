from phone_drop_discovery import (
    PHONE_DROP_LAST_DIRECTORY_PREFERENCE,
    choose_phone_drop_initial_directory,
    load_last_phone_drop_directory,
    remember_phone_drop_directory_after_import,
)


def test_valid_remembered_directory_wins(tmp_path):
    remembered = tmp_path / "remembered"
    pictures = tmp_path / "Pictures"
    remembered.mkdir()
    pictures.mkdir()

    selected = choose_phone_drop_initial_directory(
        remembered,
        home_directory=tmp_path,
        environ={},
    )

    assert selected == str(remembered.resolve())


def test_stale_remembered_directory_falls_through(tmp_path):
    pictures = tmp_path / "Pictures"
    pictures.mkdir()

    selected = choose_phone_drop_initial_directory(
        tmp_path / "missing",
        home_directory=tmp_path,
        environ={},
    )

    assert selected == str(pictures.resolve())


def test_pictures_is_preferred_when_available(tmp_path):
    pictures = tmp_path / "Pictures"
    downloads = tmp_path / "Downloads"
    pictures.mkdir()
    downloads.mkdir()

    selected = choose_phone_drop_initial_directory(home_directory=tmp_path, environ={})

    assert selected == str(pictures.resolve())


def test_downloads_is_used_when_pictures_is_missing(tmp_path):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()

    selected = choose_phone_drop_initial_directory(home_directory=tmp_path, environ={})

    assert selected == str(downloads.resolve())


def test_home_onedrive_pictures_is_used_after_local_defaults(tmp_path):
    one_drive_pictures = tmp_path / "OneDrive" / "Pictures"
    one_drive_pictures.mkdir(parents=True)

    selected = choose_phone_drop_initial_directory(home_directory=tmp_path, environ={})

    assert selected == str(one_drive_pictures.resolve())


def test_environment_onedrive_pictures_is_supported(tmp_path):
    home = tmp_path / "home"
    env_one_drive = tmp_path / "synced"
    env_pictures = env_one_drive / "Pictures"
    home.mkdir()
    env_pictures.mkdir(parents=True)

    selected = choose_phone_drop_initial_directory(
        home_directory=home,
        environ={"OneDrive": str(env_one_drive)},
    )

    assert selected == str(env_pictures.resolve())


def test_total_candidate_miss_falls_back_to_existing_home(tmp_path):
    selected = choose_phone_drop_initial_directory(home_directory=tmp_path, environ={})

    assert selected == str(tmp_path.resolve())


def test_cancel_does_not_update_remembered_location(tmp_path):
    preferences = {PHONE_DROP_LAST_DIRECTORY_PREFERENCE: "keep-me"}

    changed = remember_phone_drop_directory_after_import(
        preferences,
        (),
        copied_count=1,
        duplicate_count=0,
    )

    assert changed is False
    assert load_last_phone_drop_directory(preferences) == "keep-me"


def test_rejected_only_import_does_not_update_remembered_location(tmp_path):
    source = tmp_path / "phone" / "bad.heic"
    source.parent.mkdir()
    source.write_bytes(b"not-used")
    preferences = {PHONE_DROP_LAST_DIRECTORY_PREFERENCE: "keep-me"}

    changed = remember_phone_drop_directory_after_import(
        preferences,
        (str(source),),
        copied_count=0,
        duplicate_count=0,
    )

    assert changed is False
    assert load_last_phone_drop_directory(preferences) == "keep-me"


def test_copied_import_updates_remembered_location(tmp_path):
    source = tmp_path / "phone" / "front.jpg"
    source.parent.mkdir()
    source.write_bytes(b"not-used")
    preferences = {}

    changed = remember_phone_drop_directory_after_import(
        preferences,
        (str(source),),
        copied_count=1,
        duplicate_count=0,
    )

    assert changed is True
    assert load_last_phone_drop_directory(preferences) == str(source.parent.resolve())


def test_duplicate_only_import_updates_remembered_location(tmp_path):
    source = tmp_path / "phone" / "front.jpg"
    source.parent.mkdir()
    source.write_bytes(b"not-used")
    preferences = {}

    changed = remember_phone_drop_directory_after_import(
        preferences,
        (str(source),),
        copied_count=0,
        duplicate_count=1,
    )

    assert changed is True
    assert load_last_phone_drop_directory(preferences) == str(source.parent.resolve())
