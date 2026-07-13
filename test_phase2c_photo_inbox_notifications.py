import unittest
from types import SimpleNamespace

from coin_collection_gui import (
    PHOTO_INBOX_SETTING_AUTO_REFRESH_ON_OPEN,
    PHOTO_INBOX_SETTING_SCAN_ON_STARTUP,
    PHOTO_INBOX_SETTING_STARTUP_NOTIFICATION,
    CoinCollectionGUI,
)


class DummyVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class DummyRoot:
    def __init__(self):
        self.after_calls = []

    def after(self, delay_ms, callback):
        self.after_calls.append((delay_ms, callback))


class DummyManager:
    def __init__(self, pending_ids=None, fail_refresh=False):
        self.pending_ids = list(pending_ids or [])
        self.fail_refresh = fail_refresh
        self.refresh_calls = 0

    def refresh(self):
        self.refresh_calls += 1
        if self.fail_refresh:
            raise RuntimeError("scan failed")
        return SimpleNamespace(errors=[])

    def get_pending_sets(self):
        return [
            SimpleNamespace(
                id=photo_set_id,
                state=SimpleNamespace(value="NEW"),
                suggested_label=f"Set {photo_set_id}",
                created_at="2026-07-12T10:00:00",
                updated_at="2026-07-12T10:00:00",
            )
            for photo_set_id in self.pending_ids
        ]

    def get_photo_set_photos(self, photo_set_id):
        return [SimpleNamespace(path=f"{photo_set_id}.jpg")]


def make_gui(preferences=None):
    gui = CoinCollectionGUI.__new__(CoinCollectionGUI)
    gui.root = DummyRoot()
    gui.app_preferences = dict(preferences or {})
    gui.photo_inbox_pending_count = 0
    gui.photo_inbox_last_error = ""
    gui.photo_inbox_active_notification_signature = ""
    gui.photo_inbox_dismissed_notification_signature = ""
    gui.photo_inbox_indicator_var = DummyVar("")
    gui.photo_inbox_notification_var = DummyVar("")
    return gui


class Phase2CPhotoInboxNotificationTests(unittest.TestCase):
    def test_startup_scan_runs_once_and_updates_pending_count(self):
        gui = make_gui()
        manager = DummyManager(["set-1", "set-2"])

        result = gui.refresh_photo_inbox_awareness(manager=manager, scan=True, startup=True)

        self.assertTrue(result["success"])
        self.assertEqual(1, manager.refresh_calls)
        self.assertEqual(2, result["pending_count"])
        self.assertEqual("Photo Inbox (2)", gui.photo_inbox_indicator_var.get())

    def test_startup_scan_disabled_schedules_no_scan(self):
        gui = make_gui({PHOTO_INBOX_SETTING_SCAN_ON_STARTUP: False})

        scheduled = gui.schedule_startup_photo_inbox_scan()

        self.assertFalse(scheduled)
        self.assertEqual([], gui.root.after_calls)

    def test_startup_scan_enabled_schedules_one_scan(self):
        gui = make_gui()

        scheduled = gui.schedule_startup_photo_inbox_scan()

        self.assertTrue(scheduled)
        self.assertEqual(1, len(gui.root.after_calls))
        self.assertEqual(250, gui.root.after_calls[0][0])

    def test_notification_enabled_shows_passive_message_for_pending_sets(self):
        gui = make_gui()
        manager = DummyManager(["set-1"])

        gui.refresh_photo_inbox_awareness(manager=manager, scan=True, startup=True)

        self.assertEqual("1 pending Photo Set ready to review.", gui.photo_inbox_notification_var.get())

    def test_notification_disabled_updates_count_without_message(self):
        gui = make_gui({PHOTO_INBOX_SETTING_STARTUP_NOTIFICATION: False})
        manager = DummyManager(["set-1", "set-2"])

        gui.refresh_photo_inbox_awareness(manager=manager, scan=True, startup=True)

        self.assertEqual("Photo Inbox (2)", gui.photo_inbox_indicator_var.get())
        self.assertEqual("", gui.photo_inbox_notification_var.get())

    def test_zero_pending_sets_remain_silent(self):
        gui = make_gui()
        manager = DummyManager([])

        gui.refresh_photo_inbox_awareness(manager=manager, scan=True, startup=True)

        self.assertEqual("Photo Inbox", gui.photo_inbox_indicator_var.get())
        self.assertEqual("", gui.photo_inbox_notification_var.get())

    def test_notification_dismissal_suppresses_same_pending_signature(self):
        gui = make_gui()
        rows = [{"id": "set-1"}, {"id": "set-2"}]

        self.assertTrue(gui.show_photo_inbox_startup_notification(rows))
        gui.dismiss_photo_inbox_notification()

        self.assertFalse(gui.show_photo_inbox_startup_notification(rows))
        self.assertEqual("", gui.photo_inbox_notification_var.get())

    def test_changed_pending_signature_can_show_new_notification(self):
        gui = make_gui()
        gui.show_photo_inbox_startup_notification([{"id": "set-1"}])
        gui.dismiss_photo_inbox_notification()

        shown = gui.show_photo_inbox_startup_notification([{"id": "set-2"}])

        self.assertTrue(shown)
        self.assertEqual("1 pending Photo Set ready to review.", gui.photo_inbox_notification_var.get())

    def test_opening_from_indicator_dismisses_notification_and_opens_inbox(self):
        gui = make_gui()
        gui.photo_inbox_active_notification_signature = "set-1"
        gui.photo_inbox_notification_var.set("1 pending Photo Set ready to review.")
        opened = []
        gui.open_photo_inbox = lambda: opened.append("open")

        gui.open_photo_inbox_from_indicator()

        self.assertEqual(["open"], opened)
        self.assertEqual("", gui.photo_inbox_notification_var.get())
        self.assertEqual("set-1", gui.photo_inbox_dismissed_notification_signature)

    def test_auto_refresh_setting_defaults_on_and_can_be_disabled(self):
        gui = make_gui()

        self.assertTrue(gui.get_photo_inbox_setting(PHOTO_INBOX_SETTING_AUTO_REFRESH_ON_OPEN))
        gui.set_photo_inbox_setting(PHOTO_INBOX_SETTING_AUTO_REFRESH_ON_OPEN, False)

        self.assertFalse(gui.get_photo_inbox_setting(PHOTO_INBOX_SETTING_AUTO_REFRESH_ON_OPEN))

    def test_settings_persist_in_existing_app_preferences(self):
        gui = make_gui()

        gui.set_photo_inbox_setting(PHOTO_INBOX_SETTING_SCAN_ON_STARTUP, False)
        gui.set_photo_inbox_setting(PHOTO_INBOX_SETTING_STARTUP_NOTIFICATION, False)
        gui.set_photo_inbox_setting(PHOTO_INBOX_SETTING_AUTO_REFRESH_ON_OPEN, True)

        self.assertEqual(
            {
                PHOTO_INBOX_SETTING_SCAN_ON_STARTUP: False,
                PHOTO_INBOX_SETTING_STARTUP_NOTIFICATION: False,
                PHOTO_INBOX_SETTING_AUTO_REFRESH_ON_OPEN: True,
            },
            gui.photo_inbox_settings_snapshot(),
        )

    def test_scan_failure_does_not_block_awareness_update(self):
        gui = make_gui()
        manager = DummyManager(["set-1"], fail_refresh=True)

        result = gui.refresh_photo_inbox_awareness(manager=manager, scan=True, startup=True)

        self.assertFalse(result["success"])
        self.assertEqual("Photo Inbox (!)", gui.photo_inbox_indicator_var.get())
        self.assertEqual("Photo Inbox unavailable.", gui.photo_inbox_notification_var.get())


if __name__ == "__main__":
    unittest.main()
