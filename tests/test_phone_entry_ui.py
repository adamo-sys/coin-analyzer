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
        self.service = PhoneEntryService(collection=CoinCollection(str(self.root / "collection.json")), intake=PhoneIntake(str(self.root / "intake.json")), audit_store=PhoneEntryAuditStore(str(self.root / "audit.json")), approval_verifier=_Unused())
        self.host = LocalPhoneEntryHost(service=self.service, staging_root=self.root / "staging", now=lambda: 1_000)
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

    def test_supported_proposal_renders_explicit_controls_without_prefilling_human_value(self) -> None:
        """Replacing explicit use with template prefill must fail this browser contract."""
        review = self._uploaded_review()
        entry_id = _entry_id(review.data)
        self._set_proposal(entry_id, _proposal(entry_id, country_status="SUPPORTED"))

        page = self.client.get(f"/review/{entry_id}", headers={"Host": "localhost"})

        self.assertIn(b"Proposed value: Canada", page.data)
        self.assertIn(b"USE SUGGESTION", page.data)
        self.assertIn(b"EDIT MANUALLY", page.data)
        self.assertNotIn(b'name="country" required value="Canada"', page.data)

    def test_unresolved_proposals_render_nonselecting_guidance(self) -> None:
        """Auto-selecting ambiguous, conflicting, or abstaining values must fail this page check."""
        review = self._uploaded_review()
        entry_id = _entry_id(review.data)
        self._set_proposal(entry_id, _proposal(entry_id, denomination_status="AMBIGUOUS", year_status="CONFLICTING"))

        page = self.client.get(f"/review/{entry_id}", headers={"Host": "localhost"})

        self.assertIn(b"AMBIGUOUS: review manually; no value was selected.", page.data)
        self.assertIn(b"CONFLICTING: review manually; no value was selected.", page.data)
        self.assertIn(b"ABSTAIN: enter a value manually if appropriate.", page.data)
        self.assertNotIn(b'proposed_value', page.data)

    def test_use_suggestion_targets_only_its_corresponding_human_input(self) -> None:
        """Pointing a suggestion at another field would copy an advisory value into the wrong human field."""
        review = self._uploaded_review()
        entry_id = _entry_id(review.data)
        proposal = _proposal(entry_id, country_status="SUPPORTED", denomination_status="SUPPORTED")
        self._set_proposal(entry_id, proposal)

        page = self.client.get(f"/review/{entry_id}", headers={"Host": "localhost"})

        self.assertIn(
            b'data-proposal-field="country" data-human-field="country" data-proposed-value="Canada" data-disposition="used"',
            page.data,
        )
        self.assertIn(
            b'data-proposal-field="denomination" data-human-field="denomination" data-proposed-value="Canada" data-disposition="used"',
            page.data,
        )

    def test_explicit_review_actions_record_treatment_without_verifying_or_saving(self) -> None:
        """Making a review action issue approval or persist a collection record must fail this route check."""
        review = self._uploaded_review()
        entry_id = _entry_id(review.data)
        csrf = _csrf(review.data)
        self._set_proposal(entry_id, _proposal(entry_id, country_status="SUPPORTED"))

        used = self.client.post(
            f"/draft/{entry_id}/treatment",
            json={"csrf_token": csrf, "proposal_field": "country", "disposition": "used"},
            headers={"Host": "localhost", "Origin": "http://localhost"},
        )
        abstained = self.client.post(
            f"/draft/{entry_id}/treatment",
            json={"csrf_token": csrf, "proposal_field": "variety", "disposition": "manual_after_abstention"},
            headers={"Host": "localhost", "Origin": "http://localhost"},
        )

        self.assertEqual(used.status_code, 200)
        self.assertEqual(abstained.status_code, 200)
        draft = self.service.reopen(entry_id)
        self.assertEqual(draft["state"], "DRAFT")
        self.assertEqual(draft["field_treatments"]["country"][0]["disposition"], "used")
        self.assertEqual(draft["field_treatments"]["variety"][0]["disposition"], "manual_after_abstention")
        self.assertEqual(self.service.collection.items, [])

    def _uploaded_review(self):
        paired = self.client.post("/pair", data={"pairing_secret": self.host.pairing_secret}, headers={"Host": "localhost", "Origin": "http://localhost"}, follow_redirects=True)
        return self.client.post("/capture", data={"csrf_token": _csrf(paired.data), "front": (BytesIO(_image("JPEG", "red")), "front.jpg"), "reverse": (BytesIO(_image("PNG", "blue")), "reverse.png")}, headers={"Host": "localhost", "Origin": "http://localhost"}, follow_redirects=True)

    def _set_proposal(self, entry_id, proposal):
        with self.service.audit_store._edit() as entries:
            entries[entry_id]["proposal"] = proposal


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


def _proposal(entry_id, *, country_status="ABSTAIN", denomination_status="ABSTAIN", year_status="ABSTAIN"):
    statuses = {"country": country_status, "denomination": denomination_status, "year": year_status}
    fields = []
    for field_name in ("country", "denomination", "year", "monarch", "reverse_design", "variety"):
        status = statuses.get(field_name, "ABSTAIN")
        supported = status == "SUPPORTED"
        fields.append({"field_name": field_name, "status": status, "proposed_value": "Canada" if supported else None, "normalized_value": "canada" if supported else None, "evidence": ([{"source": "DIRECT_OBSERVATION", "image_role": "OBVERSE", "artifact_id": "safe-artifact", "observed_value": "Canada", "producer_id": "fixture"}] if supported else []), "reasons": ["direct_field_evidence"] if supported else ["no_advisory_evidence"], "scope": "DIRECT_OBSERVATION", "candidate_ids": []})
    return {"schema_version": 1, "source_coin_id": entry_id, "producer_ids": ["fixture"], "fields": fields}
