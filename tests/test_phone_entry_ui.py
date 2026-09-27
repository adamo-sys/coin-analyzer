"""Synthetic browser acceptance coverage for the Packet 3 phone flow."""
from __future__ import annotations

import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image

from coin_collection import CoinCollection
from phone_entry_host import LocalPhoneEntryHost
from phone_entry_service import PhoneEntryAuditStore, PhoneEntryService
from phone_intake import PhoneIntake


class PhoneEntryUiTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name); old = Path.cwd(); os.chdir(self.root); self.addCleanup(os.chdir, old)
        service = PhoneEntryService(collection=CoinCollection(str(self.root / "collection.json")), intake=PhoneIntake(str(self.root / "intake.json")), audit_store=PhoneEntryAuditStore(str(self.root / "audit.json")), approval_verifier=_Unused())
        self.host = LocalPhoneEntryHost(service=service, staging_root=self.root / "staging", now=lambda: 1_000)
        self.host.start_loopback(); self.client = self.host.app.test_client()

    def test_manual_browser_flow_pairs_uploads_verifies_saves_reopens_and_revokes(self) -> None:
        pair = self.client.get("/", headers={"Host": "localhost"})
        self.assertEqual(pair.status_code, 200); self.assertIn(b"Pair this phone", pair.data)
        paired = self.client.post("/pair", data={"pairing_secret": self.host.pairing_secret}, headers={"Host": "localhost", "Origin": "http://localhost"}, follow_redirects=True)
        self.assertIn(b"Capture obverse and reverse", paired.data)
        csrf = _csrf(paired.data)
        uploaded = self.client.post("/capture", data={"csrf_token": csrf, "front": (BytesIO(_image("JPEG", "red")), "front.jpg"), "reverse": (BytesIO(_image("PNG", "blue")), "reverse.png")}, headers={"Host": "localhost", "Origin": "http://localhost"}, follow_redirects=True)
        self.assertIn(b"Manual entry", uploaded.data); self.assertIn(b"HUMAN VERIFY", uploaded.data)
        entry_id = _entry_id(uploaded.data); csrf = _csrf(uploaded.data)
        verified = self.client.post(f"/draft/{entry_id}/verify", data={"csrf_token": csrf, "country": "Canada", "denomination": "25 cents", "year": "1967", "type_design": "Centennial"}, headers={"Host": "localhost", "Origin": "http://localhost"}, follow_redirects=True)
        self.assertIn(b"Verified; not saved", verified.data); self.assertIn(b"CONFIRM SAVE", verified.data)
        saved = self.client.post(f"/draft/{entry_id}/save", data={"csrf_token": _csrf(verified.data)}, headers={"Host": "localhost", "Origin": "http://localhost"}, follow_redirects=True)
        self.assertIn(b"Saved", saved.data); self.assertIn(b"Canada", saved.data); self.assertNotIn(str(self.root).encode(), saved.data)
        self.host.stop()
        self.assertEqual(self.client.get(f"/draft/{entry_id}", headers={"Host": "localhost"}).status_code, 401)

    def test_browser_capture_preserves_packet_two_request_ceiling(self) -> None:
        paired = self.client.post("/pair", data={"pairing_secret": self.host.pairing_secret}, headers={"Host": "localhost", "Origin": "http://localhost"}, follow_redirects=True)
        next(iter(self.host._sessions.values())).request_count = 10
        response = self.client.post("/capture", data={"csrf_token": _csrf(paired.data), "front": (BytesIO(_image("JPEG", "red")), "a.jpg"), "reverse": (BytesIO(_image("PNG", "blue")), "b.png")}, headers={"Host": "localhost", "Origin": "http://localhost"})
        self.assertEqual(response.status_code, 429)


class _Unused:
    def verify(self, **_kwargs): raise AssertionError("host issues approvals")

def _image(fmt, color):
    out = BytesIO(); Image.new("RGB", (24, 24), color).save(out, fmt); return out.getvalue()
def _csrf(body):
    import re
    return re.search(rb'name="csrf_token" value="([^"]+)"', body).group(1).decode()
def _entry_id(body):
    import re
    return re.search(rb'name="entry_id" value="([^"]+)"', body).group(1).decode()
