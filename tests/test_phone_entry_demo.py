"""Security tests for the local-owner Packet 3 demo presenter."""
from __future__ import annotations

import unittest
from urllib.request import urlopen
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask

import phone_entry_demo
from phone_entry_demo import redact_bootstrap_request_target, show_pairing_details


class PhoneEntryDemoTests(unittest.TestCase):
    def test_bootstrap_request_target_is_redacted_for_server_logs(self) -> None:
        for target, expected in (
            ("/bootstrap/bootstrap-sentinel?ignored=yes", "/bootstrap/[redacted]"),
            ("/?next=/bootstrap/bootstrap-sentinel", "/"),
            ("/%62ootstrap%2Fbootstrap-sentinel", "/bootstrap/[redacted]"),
        ):
            with self.subTest(target=target):
                redacted = redact_bootstrap_request_target(target)
                self.assertEqual(redacted, expected)
                self.assertNotIn("bootstrap-sentinel", redacted)

    def test_qr_bootstrap_uses_a_visible_owner_window_without_stdout_logging(self) -> None:
        owner_window = Mock()
        dialog = Mock()
        with (
            patch("phone_entry_demo.tk.Toplevel", return_value=dialog) as toplevel,
            patch("phone_entry_demo.tk.Label", return_value=Mock()),
            patch("phone_entry_demo.tk.Button", return_value=Mock()),
            patch("phone_entry_demo.qrcode.make") as made,
            patch("phone_entry_demo.ImageTk.PhotoImage", return_value=Mock()),
            patch("builtins.print") as printed,
        ):
            show_pairing_details(owner_window, "http://192.168.1.42:8765/", "http://192.168.1.42:8765/bootstrap/bootstrap-sentinel")

        made.assert_called_once_with("http://192.168.1.42:8765/bootstrap/bootstrap-sentinel")
        owner_window.deiconify.assert_called_once_with()
        owner_window.lift.assert_called_once_with()
        owner_window.focus_force.assert_called_once_with()
        owner_window.wait_window.assert_called_once_with(owner_window)
        toplevel.assert_not_called()
        self.assertNotIn("secret-sentinel", str(printed.call_args_list))

    def test_main_never_prints_pairing_secret(self) -> None:
        host = Mock(binding=SimpleNamespace(host="192.168.1.42"))
        host.enable_lan.return_value = "secret-sentinel"
        server = Mock()
        server.serve_forever.side_effect = KeyboardInterrupt
        owner_window = Mock()
        with (
            self.assertRaises(KeyboardInterrupt),
            patch("sys.argv", ["phone_entry_demo.py", "--lan-host", "192.168.1.42", "--collection", "test.json", "--state-root", "state"]),
            patch("phone_entry_demo.build_host", return_value=host),
            patch("phone_entry_demo.tk.Tk", return_value=owner_window),
            patch("phone_entry_demo.show_pairing_details", side_effect=KeyboardInterrupt),
            patch("phone_entry_demo.make_server", return_value=server) as make_server,
            patch("phone_entry_demo.wait_for_listener"),
            patch("phone_entry_demo.threading.Thread"),
            patch("builtins.print") as printed,
        ):
            phone_entry_demo.main()

        self.assertNotIn("secret-sentinel", str(printed.call_args_list))
        self.assertIs(make_server.call_args.kwargs["request_handler"], phone_entry_demo._PrivacySafeRequestHandler)
        owner_window.withdraw.assert_not_called()

    def test_listener_serves_before_pairing_ui_instructs_phone_to_connect(self) -> None:
        app = Flask(__name__)

        @app.get("/")
        def home():
            return "ready"

        host = Mock(binding=SimpleNamespace(host="127.0.0.1"), app=app)
        host.enable_lan.return_value = "manual-secret"
        host.issue_bootstrap_url.return_value = "http://127.0.0.1:0/bootstrap/bootstrap-sentinel"

        def pairing_ui(_window, url, bootstrap_url):
            self.assertEqual(urlopen(url, timeout=2).read(), b"ready")
            self.assertIn("/bootstrap/", bootstrap_url)
            raise KeyboardInterrupt

        with (
            self.assertRaises(KeyboardInterrupt),
            patch("sys.argv", ["phone_entry_demo.py", "--lan-host", "127.0.0.1", "--collection", "test.json", "--state-root", "state", "--port", "0"]),
            patch("phone_entry_demo.build_host", return_value=host),
            patch("phone_entry_demo.tk.Tk", return_value=Mock()),
            patch("phone_entry_demo.show_pairing_details", side_effect=pairing_ui),
            patch("builtins.print"),
        ):
            phone_entry_demo.main()

    def test_main_never_prints_bootstrap_url_or_manual_pairing_secret(self) -> None:
        host = Mock(binding=SimpleNamespace(host="192.168.1.42"))
        host.enable_lan.return_value = "manual-secret-sentinel"
        host.issue_bootstrap_url.return_value = "http://192.168.1.42:8765/bootstrap/bootstrap-sentinel"
        server = Mock(); server.server_port = 8765; server.serve_forever.side_effect = KeyboardInterrupt
        with (
            self.assertRaises(KeyboardInterrupt),
            patch("sys.argv", ["phone_entry_demo.py", "--lan-host", "192.168.1.42", "--collection", "test.json", "--state-root", "state"]),
            patch("phone_entry_demo.build_host", return_value=host),
            patch("phone_entry_demo.tk.Tk", return_value=Mock()),
            patch("phone_entry_demo.make_server", return_value=server),
            patch("phone_entry_demo.show_pairing_details", side_effect=KeyboardInterrupt),
            patch("phone_entry_demo.wait_for_listener"),
            patch("phone_entry_demo.threading.Thread"),
            patch("builtins.print") as printed,
        ):
            phone_entry_demo.main()

        output = str(printed.call_args_list)
        self.assertNotIn("manual-secret-sentinel", output)
        self.assertNotIn("bootstrap-sentinel", output)


if __name__ == "__main__":
    unittest.main()
