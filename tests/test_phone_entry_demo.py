"""Security tests for the local-owner Packet 3 demo presenter."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import ANY, Mock, patch

import phone_entry_demo
from phone_entry_demo import show_pairing_details


class PhoneEntryDemoTests(unittest.TestCase):
    def test_pairing_secret_is_presented_to_owner_without_stdout_logging(self) -> None:
        owner_window = Mock()
        with patch("phone_entry_demo.messagebox.showinfo") as shown, patch("builtins.print") as printed:
            show_pairing_details(owner_window, "http://192.168.1.42:8765/", "secret-sentinel")

        shown.assert_called_once()
        self.assertIn("secret-sentinel", shown.call_args.args[1])
        self.assertNotIn("secret-sentinel", str(printed.call_args_list))

    def test_main_never_prints_pairing_secret(self) -> None:
        host = Mock(binding=SimpleNamespace(host="192.168.1.42"))
        host.enable_lan.return_value = "secret-sentinel"
        server = Mock()
        server.serve_forever.side_effect = KeyboardInterrupt
        with (
            self.assertRaises(KeyboardInterrupt),
            patch("sys.argv", ["phone_entry_demo.py", "--lan-host", "192.168.1.42", "--collection", "test.json", "--state-root", "state"]),
            patch("phone_entry_demo.build_host", return_value=host),
            patch("phone_entry_demo.tk.Tk", return_value=Mock()),
            patch("phone_entry_demo.show_pairing_details") as shown,
            patch("phone_entry_demo.make_server", return_value=server),
            patch("builtins.print") as printed,
        ):
            phone_entry_demo.main()

        shown.assert_called_once_with(ANY, "http://192.168.1.42:8765/", "secret-sentinel")
        self.assertNotIn("secret-sentinel", str(printed.call_args_list))


if __name__ == "__main__":
    unittest.main()
