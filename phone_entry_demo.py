"""Desktop-local command for the first trusted-LAN phone-entry demo."""
from __future__ import annotations

import argparse
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from werkzeug.serving import make_server

from coin_collection import CoinCollection
from phone_entry_host import LocalPhoneEntryHost
from phone_entry_service import PhoneEntryAuditStore, PhoneEntryService
from phone_intake import PhoneIntake


class _NoApproval:
    def verify(self, **_kwargs: object) -> bool:
        return False


def build_host(collection_path: str, state_root: str) -> LocalPhoneEntryHost:
    root = Path(state_root).absolute()
    service = PhoneEntryService(
        collection=CoinCollection(collection_path), intake=PhoneIntake(str(root / "phone-intake.json")),
        audit_store=PhoneEntryAuditStore(str(root / "phone-entry-audit.json")), approval_verifier=_NoApproval(),
    )
    return LocalPhoneEntryHost(service=service, staging_root=root / "staging")


def show_pairing_details(owner_window: tk.Tk, url: str, pairing_secret: str) -> None:
    """Show the secret locally without writing it to an external log stream."""
    messagebox.showinfo(
        "Phone entry LAN mode active",
        f"Open on the paired phone:\n{url}\n\nPairing secret (expires in 120 seconds):\n{pairing_secret}",
        parent=owner_window,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one explicit trusted-LAN phone-entry session.")
    parser.add_argument("--lan-host", required=True, help="Desktop's private IPv4 address, for example 192.168.1.42")
    parser.add_argument("--collection", required=True, help="Collection JSON to use for this deliberate session")
    parser.add_argument("--state-root", required=True, help="Private local state directory for this session")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    host = build_host(args.collection, args.state_root)
    secret = host.enable_lan(args.lan_host)
    url = f"http://{host.binding.host}:{args.port}/"
    owner_window = tk.Tk(); owner_window.withdraw()
    show_pairing_details(owner_window, url, secret)
    print(f"LAN mode active: {url}. Pairing details are displayed locally. Press Ctrl+C to stop and revoke access.")
    server = make_server(host.binding.host, args.port, host.app)
    try:
        server.serve_forever()
    finally:
        server.shutdown(); host.stop(); owner_window.destroy()


if __name__ == "__main__":
    main()
