"""Desktop-local command for the first trusted-LAN phone-entry demo."""
from __future__ import annotations

import argparse
import threading
import tkinter as tk
from pathlib import Path
from time import monotonic, sleep
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen

import qrcode
from PIL import ImageTk
from werkzeug.serving import WSGIRequestHandler, make_server

from coin_collection import CoinCollection
from phone_entry_host import LocalPhoneEntryHost
from phone_entry_service import PhoneEntryAuditStore, PhoneEntryService
from phone_intake import PhoneIntake


class _NoApproval:
    def verify(self, **_kwargs: object) -> bool:
        return False


def redact_bootstrap_request_target(target: str) -> str:
    """Remove the bearer bootstrap path value before access logging."""
    path = unquote(urlsplit(target).path)
    if path.startswith("/bootstrap/"):
        return "/bootstrap/[redacted]"
    return path


class _PrivacySafeRequestHandler(WSGIRequestHandler):
    """Avoid writing QR bootstrap bearer values to the console access log."""

    def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
        try:
            message = f"{self.command} {redact_bootstrap_request_target(self.path)} {self.request_version}"
        except AttributeError:
            message = self.requestline
        self.log("info", '"%s" %s %s', message.translate(self._control_char_table), str(code), size)


def build_host(collection_path: str, state_root: str) -> LocalPhoneEntryHost:
    root = Path(state_root).absolute()
    service = PhoneEntryService(
        collection=CoinCollection(collection_path), intake=PhoneIntake(str(root / "phone-intake.json")),
        audit_store=PhoneEntryAuditStore(str(root / "phone-entry-audit.json")), approval_verifier=_NoApproval(),
    )
    return LocalPhoneEntryHost(service=service, staging_root=root / "staging")


def show_pairing_details(owner_window: tk.Tk, url: str, bootstrap_url: str) -> None:
    """Show a visible desktop-local QR bootstrap without external logging."""
    owner_window.title("Phone entry LAN mode active")
    qr_image = ImageTk.PhotoImage(qrcode.make(bootstrap_url))
    label = tk.Label(owner_window, text="Scan this code with the paired iPhone to begin.")
    label.pack(padx=16, pady=(16, 8))
    qr_label = tk.Label(owner_window, image=qr_image)
    qr_label.image = qr_image
    qr_label.pack(padx=16, pady=8)
    tk.Label(owner_window, text=f"Trusted private LAN only: {url}").pack(padx=16, pady=(0, 8))
    tk.Button(owner_window, text="Close", command=owner_window.destroy).pack(pady=(0, 16))
    owner_window.deiconify()
    owner_window.lift()
    owner_window.focus_force()
    owner_window.wait_window(owner_window)


def wait_for_listener(url: str) -> None:
    """Require an HTTP response before the desktop asks the phone to scan."""
    deadline = monotonic() + 2.0
    while monotonic() < deadline:
        try:
            with urlopen(url, timeout=0.2) as response:
                if response.status == 200:
                    return
        except OSError:
            sleep(0.02)
    raise RuntimeError("The local phone-entry listener did not become ready.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one explicit trusted-LAN phone-entry session.")
    parser.add_argument("--lan-host", required=True, help="Desktop's private IPv4 address, for example 192.168.1.42")
    parser.add_argument("--collection", required=True, help="Collection JSON to use for this deliberate session")
    parser.add_argument("--state-root", required=True, help="Private local state directory for this session")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    host = build_host(args.collection, args.state_root)
    host.enable_lan(args.lan_host)
    server = make_server(host.binding.host, args.port, host.app, request_handler=_PrivacySafeRequestHandler)
    url = f"http://{host.binding.host}:{server.server_port}/"
    bootstrap_url = host.issue_bootstrap_url(url)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    wait_for_listener(url)
    owner_window = tk.Tk()
    try:
        show_pairing_details(owner_window, url, bootstrap_url)
        print(f"LAN mode active: {url}. Scan the local QR display to pair. Press Ctrl+C to stop and revoke access.")
        server_thread.join()
    finally:
        server.shutdown(); host.stop()
        try:
            owner_window.destroy()
        except tk.TclError:
            pass


if __name__ == "__main__":
    main()
