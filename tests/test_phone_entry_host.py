"""Synthetic HTTP boundary tests for Packet 2 local phone entry."""

from __future__ import annotations

import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from coin_collection import CoinCollection
from phone_entry_host import LocalPhoneEntryHost
from phone_entry_service import PhoneEntryAuditStore, PhoneEntryService
from phone_intake import PhoneIntake


class LocalPhoneEntryHostTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        previous_cwd = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, previous_cwd)
        self.service = PhoneEntryService(
            collection=CoinCollection(str(self.root / "collection.json")),
            intake=PhoneIntake(str(self.root / "phone-intake.json")),
            audit_store=PhoneEntryAuditStore(str(self.root / "phone-entry-audit.json")),
            approval_verifier=_UnusedApprovalVerifier(),
        )
        self.host = LocalPhoneEntryHost(
            service=self.service,
            staging_root=self.root / "staging",
            now=lambda: 1_000,
        )
        self.host.start_loopback()
        self.client = self.host.app.test_client()

    def test_loopback_is_default_and_lan_requires_explicit_owner_action(self) -> None:
        self.assertEqual(self.host.binding.host, "127.0.0.1")
        self.assertFalse(self.host.binding.lan_enabled)

        secret = self.host.enable_lan("192.168.50.3")

        self.assertEqual(self.host.binding.host, "192.168.50.3")
        self.assertTrue(self.host.binding.lan_enabled)
        self.assertGreaterEqual(len(secret), 32)

    def test_lan_binding_rejects_ipv6_until_host_authority_parsing_is_added(self) -> None:
        with self.assertRaises(ValueError):
            self.host.enable_lan("fd00::1")

    def test_pairing_is_single_use_and_stop_revokes_session(self) -> None:
        secret = self.host.pairing_secret
        response = self._pair(secret)
        self.assertEqual(response.status_code, 201)
        self.assertIn("phone_entry_session=", response.headers["Set-Cookie"])
        self.assertIn("HttpOnly", response.headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", response.headers["Set-Cookie"])
        self.assertNotIn("Domain=", response.headers["Set-Cookie"])
        csrf = response.get_json()["csrf_token"]

        self.assertEqual(self._pair(secret).status_code, 403)
        self.host.stop()
        rejected = self.client.post(
            "/drafts",
            data={"csrf_token": csrf},
            headers={"Origin": "http://localhost"},
        )
        self.assertEqual(rejected.status_code, 401)

    def test_pairing_expiry_and_bad_host_or_origin_fail_closed(self) -> None:
        self.host.advance_for_test(121)
        self.assertEqual(self._pair(self.host.pairing_secret).status_code, 403)

        self.host.start_loopback()
        bad_host = self.client.post(
            "/session/pair",
            json={"pairing_secret": self.host.pairing_secret},
            headers={"Host": "evil.example", "Origin": "http://evil.example"},
        )
        self.assertEqual(bad_host.status_code, 400)

        self.host.start_loopback()
        wrong_port = self.client.post(
            "/session/pair",
            json={"pairing_secret": self.host.pairing_secret},
            headers={"Origin": "http://localhost:9999"},
        )
        self.assertEqual(wrong_port.status_code, 403)

    def test_upload_requires_session_csrf_origin_and_exact_roles(self) -> None:
        self.assertEqual(self.client.post("/drafts").status_code, 403)
        csrf = self._pair(self.host.pairing_secret).get_json()["csrf_token"]
        missing_csrf = self.client.post(
            "/drafts", data=self._uploads(), headers={"Origin": "http://localhost"}
        )
        self.assertEqual(missing_csrf.status_code, 403)
        wrong_origin = self.client.post(
            "/drafts",
            data=self._uploads(csrf),
            headers={"Origin": "http://elsewhere"},
        )
        self.assertEqual(wrong_origin.status_code, 403)
        unexpected_role = self.client.post(
            "/drafts",
            data={**self._uploads(csrf), "extra": (BytesIO(b"x"), "extra.jpg")},
            headers={"Origin": "http://localhost"},
        )
        self.assertEqual(unexpected_role.status_code, 400)

    def test_upload_decodes_only_single_frame_jpeg_or_png_and_hides_filenames(self) -> None:
        csrf = self._pair(self.host.pairing_secret).get_json()["csrf_token"]
        unsupported = self.client.post(
            "/drafts",
            data={
                "csrf_token": csrf,
                "front": (BytesIO(b"not-a-jpeg"), "../../private.heic"),
                "reverse": (BytesIO(_image_bytes("PNG", "blue")), "reverse.png"),
            },
            headers={"Origin": "http://localhost"},
        )
        self.assertEqual(unsupported.status_code, 400)
        self.assertNotIn("private.heic", unsupported.get_data(as_text=True))

        response = self.client.post(
            "/drafts",
            data=self._uploads(csrf, front_name="../../private-front.jpg"),
            headers={"Origin": "http://localhost"},
        )
        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertEqual(set(payload), {"entry_id", "state", "media"})
        self.assertNotIn("private-front.jpg", response.get_data(as_text=True))
        self.assertEqual(len([path for path in (self.root / "staging").rglob("*") if path.is_file()]), 2)

    def test_duplicate_image_hash_and_non_post_mutation_are_rejected(self) -> None:
        csrf = self._pair(self.host.pairing_secret).get_json()["csrf_token"]
        identical = _image_bytes("PNG", "red")
        response = self.client.post(
            "/drafts",
            data={
                "csrf_token": csrf,
                "front": (BytesIO(identical), "front.png"),
                "reverse": (BytesIO(identical), "reverse.png"),
            },
            headers={"Origin": "http://localhost"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/session/pair").status_code, 405)

    def test_animation_malformed_and_dimension_bombs_are_rejected_before_staging(self) -> None:
        csrf = self._pair(self.host.pairing_secret).get_json()["csrf_token"]
        animated = BytesIO()
        first = Image.new("RGB", (16, 16), "red")
        first.save(animated, format="GIF", save_all=True, append_images=[Image.new("RGB", (16, 16), "blue")])
        for payload, name in ((animated.getvalue(), "animated.gif"), (b"broken", "broken.png"), (_image_bytes("PNG", "green", (8_001, 1)), "wide.png")):
            response = self.client.post(
                "/drafts",
                data={
                    "csrf_token": csrf,
                    "front": (BytesIO(payload), name),
                    "reverse": (BytesIO(_image_bytes("PNG", "blue")), "reverse.png"),
                },
                headers={"Origin": "http://localhost"},
            )
            self.assertEqual(response.status_code, 400)
        self.assertFalse((self.root / "staging").exists())

    def test_staged_media_tampering_forces_recovery_and_never_saves(self) -> None:
        csrf = self._pair(self.host.pairing_secret).get_json()["csrf_token"]
        entry_id = self.client.post(
            "/drafts", data=self._uploads(csrf), headers={"Origin": "http://localhost"}
        ).get_json()["entry_id"]
        self.client.post(
            f"/draft/{entry_id}/verify",
            json={"csrf_token": csrf, "country": "Canada", "denomination": "25 cents", "year": "1967", "type_design": ""},
            headers={"Origin": "http://localhost"},
        )
        next(path for path in (self.root / "staging").rglob("*") if path.is_file()).write_bytes(b"tampered")
        response = self.client.post(
            f"/draft/{entry_id}/save", json={"csrf_token": csrf}, headers={"Origin": "http://localhost"}
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.service.collection.items, [])

    def test_client_cannot_supply_a_model_or_raw_approval_token(self) -> None:
        csrf = self._pair(self.host.pairing_secret).get_json()["csrf_token"]
        entry_id = self.client.post(
            "/drafts", data=self._uploads(csrf), headers={"Origin": "http://localhost"}
        ).get_json()["entry_id"]
        response = self.client.post(
            f"/draft/{entry_id}/verify",
            json={
                "csrf_token": csrf,
                "country": "Canada",
                "denomination": "25 cents",
                "year": "1967",
                "type_design": "",
                "verification_approval": "model-says-yes",
            },
            headers={"Origin": "http://localhost"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.service.reopen(entry_id)["state"], "DRAFT")

    def test_session_aggregate_upload_budget_is_enforced_before_second_staging(self) -> None:
        csrf = self._pair(self.host.pairing_secret).get_json()["csrf_token"]
        with patch("phone_entry_host._MAX_SESSION_BYTES", 1_000):
            first = self.client.post(
                "/drafts", data=self._uploads(csrf), headers={"Origin": "http://localhost"}
            )
            self.assertEqual(first.status_code, 201)
            second = self.client.post(
                "/drafts",
                data={
                    "csrf_token": csrf,
                    "front": (BytesIO(_image_bytes("JPEG", "green")), "next.jpg"),
                    "reverse": (BytesIO(_image_bytes("PNG", "yellow")), "next.png"),
                },
                headers={"Origin": "http://localhost"},
            )
        self.assertEqual(second.status_code, 413)

    def test_host_issues_one_use_human_approvals_to_packet_one_service(self) -> None:
        csrf = self._pair(self.host.pairing_secret).get_json()["csrf_token"]
        created = self.client.post(
            "/drafts", data=self._uploads(csrf), headers={"Origin": "http://localhost"}
        ).get_json()
        entry_id = created["entry_id"]
        verified = self.client.post(
            f"/draft/{entry_id}/verify",
            json={
                "csrf_token": csrf,
                "country": "Canada",
                "denomination": "25 cents",
                "year": "1967",
                "type_design": "Centennial",
            },
            headers={"Origin": "http://localhost"},
        )
        self.assertEqual(verified.status_code, 200)
        saved = self.client.post(
            f"/draft/{entry_id}/save",
            json={"csrf_token": csrf},
            headers={"Origin": "http://localhost"},
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(len(self.service.collection.items), 1)

    def _pair(self, secret: str):
        return self.client.post(
            "/session/pair",
            json={"pairing_secret": secret},
            headers={"Origin": "http://localhost"},
        )

    def _uploads(self, csrf: str = "", front_name: str = "front.jpg") -> dict[str, object]:
        data: dict[str, object] = {
            "front": (BytesIO(_image_bytes("JPEG", "red")), front_name),
            "reverse": (BytesIO(_image_bytes("PNG", "blue")), "reverse.png"),
        }
        if csrf:
            data["csrf_token"] = csrf
        return data


class _UnusedApprovalVerifier:
    def verify(self, *, entry_id: str, action: str, approval: str) -> bool:
        raise AssertionError("the host must supply its own one-use approval verifier")


def _image_bytes(image_format: str, color: str, size: tuple[int, int] = (32, 32)) -> bytes:
    data = BytesIO()
    Image.new("RGB", size, color).save(data, format=image_format)
    return data.getvalue()


if __name__ == "__main__":
    unittest.main()
