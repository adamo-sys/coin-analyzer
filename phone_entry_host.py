"""Local-only HTTP boundary for the Packet 1 phone-entry service.

This module owns listener policy, pairing, request authentication, and private
image staging.  It deliberately owns neither collection persistence nor human
review UI: the existing ``PhoneEntryService`` remains the only save authority.
"""

from __future__ import annotations

import ipaddress
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from flask import Flask, jsonify, redirect, render_template, request, url_for
from PIL import Image, UnidentifiedImageError
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from phone_entry_service import PhoneEntryError, PhoneEntrySaveResult, PhoneEntryService

_COOKIE_NAME = "phone_entry_session"
_PAIRING_LIFETIME_SECONDS = 120
_UPLOAD_BODY_OVERHEAD_BYTES = 64 * 1024
# Werkzeug feeds multipart parsing in 64 KiB chunks. Keep enough bounded parser
# buffer for a chunk plus an unfinished multipart boundary; file bytes remain
# constrained separately by ``UploadLimits`` before image decoding.
_MAX_FORM_MEMORY_BYTES = 128 * 1024
_MAX_FORM_PARTS = 4


@dataclass(frozen=True, slots=True)
class UploadLimits:
    """Bounded mobile-photo intake limits for one explicit obverse/reverse pair."""

    max_file_bytes: int = 16 * 1024 * 1024
    max_total_bytes: int = 32 * 1024 * 1024
    max_session_bytes: int = 32 * 1024 * 1024
    max_pixels: int = 30_000_000
    max_dimension: int = 8_000


DEFAULT_UPLOAD_LIMITS = UploadLimits()


class PhoneEntryHostError(ValueError):
    """A local host request violates its fixed security contract."""


@dataclass(frozen=True, slots=True)
class HostBinding:
    """The address selected by the desktop-owned host lifecycle."""

    host: str
    lan_enabled: bool


@dataclass(slots=True)
class _Session:
    csrf_token: str
    entries: set[str]
    approvals: dict[str, str]
    request_count: int = 0
    staged_bytes: int = 0


class LocalPhoneEntryHost:
    """A desktop-controlled, one-device local HTTP adapter.

    ``start_loopback``, ``enable_lan`` and ``stop`` are desktop integration
    methods.  They are intentionally not HTTP routes.
    """

    def __init__(
        self,
        *,
        service: PhoneEntryService,
        staging_root: str | Path,
        now: Callable[[], float] | None = None,
        upload_limits: UploadLimits = DEFAULT_UPLOAD_LIMITS,
    ) -> None:
        self.service = service
        # Packet 1 accepts only a trusted host-issued, action-bound approval.
        # The request payload never supplies this capability.
        self.service.approval_verifier = self
        self.staging_root = Path(staging_root).absolute()
        self._clock = now or __import__("time").time
        self.upload_limits = upload_limits
        self._test_offset = 0.0
        self._binding: HostBinding | None = None
        self._pairing_hash = ""
        self._pairing_expires_at = 0.0
        self._bootstrap_hash = ""
        self._bootstrap_expires_at = 0.0
        self._sessions: dict[str, _Session] = {}
        self.app = self._create_app()

    @property
    def binding(self) -> HostBinding:
        if self._binding is None:
            raise PhoneEntryHostError("The local phone host is stopped.")
        return self._binding

    @property
    def pairing_secret(self) -> str:
        """Desktop-only pairing display value for testable controller wiring."""
        if not hasattr(self, "_pairing_secret"):
            raise PhoneEntryHostError("The local phone host is stopped.")
        return self._pairing_secret

    def start_loopback(self) -> str:
        """Start in the safe loopback-only mode and issue a fresh pairing secret."""
        self._binding = HostBinding(host="127.0.0.1", lan_enabled=False)
        self._clear_bootstrap_token()
        return self._replace_pairing_secret()

    def enable_lan(self, host: str) -> str:
        """Explicit desktop-owner action for a constrained trusted-LAN bind."""
        try:
            address = ipaddress.ip_address(host)
        except ValueError as error:
            raise PhoneEntryHostError("LAN binding requires a numeric private address.") from error
        if address.version != 4 or not address.is_private or address.is_loopback or address.is_unspecified:
            raise PhoneEntryHostError("LAN binding requires a private IPv4, non-loopback address.")
        self._sessions.clear()
        self._binding = HostBinding(host=str(address), lan_enabled=True)
        self._clear_bootstrap_token()
        return self._replace_pairing_secret()

    def issue_bootstrap_url(self, base_url: str) -> str:
        """Create the desktop-only, one-use QR bootstrap URL for this binding."""
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or not parsed.netloc or not self._bootstrap_host_matches(parsed.hostname):
            raise PhoneEntryHostError("Bootstrap URL must use the active local host binding.")
        token = secrets.token_urlsafe(32)
        self._bootstrap_hash = _digest(token)
        self._bootstrap_expires_at = self._now() + _PAIRING_LIFETIME_SECONDS
        return f"{base_url.rstrip('/')}/bootstrap/{token}"

    def stop(self) -> None:
        """Revoke pairing and every session before returning to the idle state."""
        self._sessions.clear()
        self._pairing_hash = ""
        self._pairing_expires_at = 0.0
        self._pairing_secret = ""
        self._clear_bootstrap_token()
        self._binding = None

    def advance_for_test(self, seconds: float) -> None:
        """Test-only deterministic clock hook; never used by the HTTP API."""
        self._test_offset += seconds

    def verify(self, *, entry_id: str, action: str, approval: str) -> bool:
        """Packet 1 approval verifier: consume a host-issued action-bound token."""
        digest = _digest(approval)
        for session in self._sessions.values():
            expected = session.approvals.pop(f"{entry_id}:{action}", None)
            if expected is not None:
                return secrets.compare_digest(expected, digest)
        return False

    def _create_app(self) -> Flask:
        app = Flask(__name__)
        app.config.update(
            MAX_CONTENT_LENGTH=self.upload_limits.max_total_bytes + _UPLOAD_BODY_OVERHEAD_BYTES,
            MAX_FORM_MEMORY_SIZE=_MAX_FORM_MEMORY_BYTES,
            MAX_FORM_PARTS=_MAX_FORM_PARTS,
        )

        @app.before_request
        def _request_boundary() -> None:
            if self._binding is None:
                raise _RequestError("session_required", 401)
            if not self._valid_host(request.host):
                raise _RequestError("invalid_host", 400)
            if request.method == "POST" and not self._valid_origin(request.headers.get("Origin")):
                raise _RequestError("invalid_origin", 403)

        @app.errorhandler(_RequestError)
        def _request_error(error: _RequestError):
            return jsonify(error=error.category), error.status

        @app.errorhandler(RequestEntityTooLarge)
        def _too_large(_error: RequestEntityTooLarge):
            return jsonify(error="payload_too_large"), 413

        @app.errorhandler(HTTPException)
        def _http_error(error: HTTPException):
            return jsonify(error="method_not_allowed" if error.code == 405 else "request_rejected"), error.code

        @app.errorhandler(Exception)
        def _unexpected(_error: Exception):
            return jsonify(error="request_rejected"), 400

        @app.post("/session/pair")
        def pair_session():
            body = request.get_json(silent=True)
            if not isinstance(body, dict) or set(body) != {"pairing_secret"}:
                raise _RequestError("invalid_pairing", 400)
            secret = body["pairing_secret"]
            if not isinstance(secret, str) or not self._consume_pairing_secret(secret):
                raise _RequestError("pairing_rejected", 403)
            if self._sessions:
                raise _RequestError("pairing_rejected", 403)
            session_id = secrets.token_urlsafe(32)
            csrf_token = secrets.token_urlsafe(32)
            self._sessions[session_id] = _Session(csrf_token=csrf_token, entries=set(), approvals={})
            response = jsonify(csrf_token=csrf_token)
            response.status_code = 201
            response.set_cookie(_COOKIE_NAME, session_id, httponly=True, samesite="Strict")
            return response

        @app.get("/bootstrap/<token>")
        def bootstrap_session(token: str):
            if self._sessions or not self._consume_bootstrap_token(token):
                raise _RequestError("pairing_rejected", 403)
            session_id, _csrf_token = self._create_session()
            response = redirect(url_for("capture_page"))
            response.set_cookie(_COOKIE_NAME, session_id, httponly=True, samesite="Strict")
            return response

        @app.get("/")
        def phone_home():
            session = self._sessions.get(request.cookies.get(_COOKIE_NAME, ""))
            if session is not None:
                return redirect(url_for("capture_page"))
            return self._page("PAIR", pairing=True)

        @app.post("/pair")
        def pair_page():
            secret = request.form.get("pairing_secret", "")
            if not isinstance(secret, str) or not self._consume_pairing_secret(secret) or self._sessions:
                return self._page("PAIR", pairing=True, error="Pairing was not accepted."), 403
            session_id, csrf_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            self._sessions[session_id] = _Session(csrf_token=csrf_token, entries=set(), approvals={})
            response = redirect(url_for("capture_page"))
            response.set_cookie(_COOKIE_NAME, session_id, httponly=True, samesite="Strict")
            return response

        @app.get("/capture")
        def capture_page():
            return self._page("CAPTURE", csrf=self._authenticated_session().csrf_token)

        @app.post("/capture")
        def capture_upload():
            session = self._authenticated_session(); self._require_csrf(session)
            if set(request.files) != {"front", "reverse"} or set(request.form) != {"csrf_token"}:
                return self._page("CAPTURE", csrf=session.csrf_token, error="Select both explicit image roles."), 400
            session.request_count += 1
            if session.request_count > 10:
                return self._page("CAPTURE", csrf=session.csrf_token, error="Capture request limit reached."), 429
            staged, size = self._stage_pair(session=session, session_id=request.cookies[_COOKIE_NAME])
            try:
                draft = self.service.create_draft(front_path=str(staged["front"]), reverse_path=str(staged["reverse"]), session_id=request.cookies[_COOKIE_NAME])
            except PhoneEntryError:
                self._remove_paths(staged.values())
                return self._page("CAPTURE", csrf=session.csrf_token, error="Images could not be accepted."), 400
            session.entries.add(draft.entry_id); session.staged_bytes += size
            return redirect(url_for("review_page", entry_id=draft.entry_id))

        @app.get("/review/<entry_id>")
        def review_page(entry_id: str):
            session = self._authenticated_session(); self._require_entry(session, entry_id)
            draft = self.service.reopen(entry_id)
            return self._page("VERIFIED" if draft["state"] == "VERIFIED" else "REVIEW", csrf=session.csrf_token, draft=draft)

        @app.post("/drafts")
        def create_draft():
            session = self._authenticated_session()
            self._require_csrf(session)
            if set(request.files) != {"front", "reverse"} or set(request.form) != {"csrf_token"}:
                raise _RequestError("invalid_upload", 400)
            session.request_count += 1
            if session.request_count > 10:
                raise _RequestError("request_limit", 429)
            staged, staged_bytes = self._stage_pair(session=session, session_id=request.cookies[_COOKIE_NAME])
            try:
                draft = self.service.create_draft(
                    front_path=str(staged["front"]),
                    reverse_path=str(staged["reverse"]),
                    session_id=request.cookies[_COOKIE_NAME],
                )
            except PhoneEntryError as error:
                self._remove_paths(staged.values())
                raise _RequestError("draft_rejected", 400) from error
            session.entries.add(draft.entry_id)
            session.staged_bytes += staged_bytes
            return jsonify(entry_id=draft.entry_id, state=draft.state, media=draft.to_dict()["media"]), 201

        @app.get("/draft/<entry_id>")
        def get_draft(entry_id: str):
            session = self._authenticated_session()
            self._require_entry(session, entry_id)
            try:
                return jsonify(self.service.reopen(entry_id))
            except PhoneEntryError as error:
                raise _RequestError("draft_unavailable", 404) from error

        @app.post("/draft/<entry_id>/verify")
        def verify_draft(entry_id: str):
            session = self._authenticated_session()
            self._require_csrf(session)
            self._require_entry(session, entry_id)
            body = request.get_json(silent=True) if request.is_json else request.form.to_dict()
            if not request.is_json:
                body.pop("entry_id", None)
            if not isinstance(body, dict) or set(body) != {"csrf_token", "country", "denomination", "year", "type_design"}:
                if request.is_json: raise _RequestError("invalid_identity", 400)
                return self._page("REVIEW", csrf=session.csrf_token, draft=self.service.reopen(entry_id), error="Enter all required identity fields."), 400
            approval = self._issue_approval(session, entry_id, "VERIFY")
            try:
                draft = self.service.verify(
                    entry_id,
                    country=str(body["country"]),
                    denomination=str(body["denomination"]),
                    year=str(body["year"]),
                    type_design=str(body["type_design"]),
                    verification_approval=approval,
                )
            except PhoneEntryError as error:
                if request.is_json: raise _RequestError("verification_rejected", 400) from error
                return self._page("REVIEW", csrf=session.csrf_token, draft=self.service.reopen(entry_id), error="Verification was not accepted."), 400
            return jsonify(draft.to_dict()) if request.is_json else redirect(url_for("review_page", entry_id=entry_id))

        @app.post("/draft/<entry_id>/save")
        def save_draft(entry_id: str):
            session = self._authenticated_session()
            self._require_csrf(session)
            self._require_entry(session, entry_id)
            body = request.get_json(silent=True) if request.is_json else request.form.to_dict()
            if not isinstance(body, dict) or set(body) != {"csrf_token"}:
                if request.is_json: raise _RequestError("invalid_save", 400)
                return self._page("VERIFIED", csrf=session.csrf_token, draft=self.service.reopen(entry_id), error="Save confirmation was not accepted."), 400
            approval = self._issue_approval(session, entry_id, "SAVE")
            try:
                result: PhoneEntrySaveResult = self.service.save(entry_id, save_approval=approval)
            except PhoneEntryError as error:
                if request.is_json: raise _RequestError("save_recovery_required", 409) from error
                return self._page("RECOVERY", csrf=session.csrf_token, draft=self.service.reopen(entry_id), error="Recovery is required; do not retry save."), 409
            return jsonify(entry_id=result.entry_id, state=result.state, item_id=result.item_id) if request.is_json else redirect(url_for("saved_page", entry_id=entry_id))

        @app.get("/saved/<entry_id>")
        def saved_page(entry_id: str):
            session = self._authenticated_session(); self._require_entry(session, entry_id)
            return self._page("SAVED", csrf=session.csrf_token, draft=self.service.reopen(entry_id))

        @app.get("/items/<item_id>")
        def get_item(item_id: str):
            self._authenticated_session()
            item = self.service.collection.get_item(item_id)
            if item is None:
                raise _RequestError("item_unavailable", 404)
            return jsonify(id=item.id, country=item.country, denomination=item.denomination, year=item.year, type_design=item.type_design)

        return app

    def _page(self, state: str, *, csrf: str = "", draft: dict[str, Any] | None = None, pairing: bool = False, error: str = ""):
        return render_template("phone_entry.html", state=state, csrf=csrf, draft=draft or {}, pairing=pairing, error=error)

    def _now(self) -> float:
        return self._clock() + self._test_offset

    def _replace_pairing_secret(self) -> str:
        self._sessions.clear()
        self._pairing_secret = secrets.token_urlsafe(32)
        self._pairing_hash = _digest(self._pairing_secret)
        self._pairing_expires_at = self._now() + _PAIRING_LIFETIME_SECONDS
        return self._pairing_secret

    def _create_session(self) -> tuple[str, str]:
        session_id = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        self._sessions[session_id] = _Session(csrf_token=csrf_token, entries=set(), approvals={})
        return session_id, csrf_token

    def _bootstrap_host_matches(self, host: str | None) -> bool:
        if host is None:
            return False
        if self.binding.lan_enabled:
            return host == self.binding.host
        return host in {"127.0.0.1", "localhost"}

    def _clear_bootstrap_token(self) -> None:
        self._bootstrap_hash = ""
        self._bootstrap_expires_at = 0.0

    def _consume_bootstrap_token(self, value: str) -> bool:
        if not self._bootstrap_hash or self._now() > self._bootstrap_expires_at:
            self._clear_bootstrap_token()
            return False
        valid = secrets.compare_digest(self._bootstrap_hash, _digest(value))
        if valid:
            self._clear_bootstrap_token()
        return valid

    def _consume_pairing_secret(self, value: str) -> bool:
        valid = (
            bool(self._pairing_hash)
            and self._now() <= self._pairing_expires_at
            and secrets.compare_digest(self._pairing_hash, _digest(value))
        )
        if valid:
            self._pairing_hash = ""
            self._pairing_secret = ""
        return valid

    def _valid_host(self, host_header: str) -> bool:
        host = host_header.split(":", 1)[0].lower()
        if self.binding.lan_enabled:
            return host == self.binding.host
        return host in {"127.0.0.1", "localhost"}

    def _valid_origin(self, origin: str | None) -> bool:
        if not origin or not origin.startswith("http://"):
            return False
        return origin == f"http://{request.host}" and self._valid_host(request.host)

    def _authenticated_session(self) -> _Session:
        session_id = request.cookies.get(_COOKIE_NAME, "")
        session = self._sessions.get(session_id)
        if session is None:
            raise _RequestError("session_required", 401)
        return session

    @staticmethod
    def _require_csrf(session: _Session) -> None:
        supplied = (request.get_json(silent=True) or {}).get("csrf_token") if request.is_json else request.form.get("csrf_token")
        if not isinstance(supplied, str) or not secrets.compare_digest(session.csrf_token, supplied):
            raise _RequestError("csrf_rejected", 403)

    @staticmethod
    def _require_entry(session: _Session, entry_id: str) -> None:
        if entry_id not in session.entries:
            raise _RequestError("draft_unavailable", 404)

    @staticmethod
    def _issue_approval(session: _Session, entry_id: str, action: str) -> str:
        approval = secrets.token_urlsafe(32)
        session.approvals[f"{entry_id}:{action}"] = _digest(approval)
        return approval

    def _stage_pair(self, *, session: _Session, session_id: str) -> tuple[dict[str, Path], int]:
        payloads = {
            role: request.files[role].read(self.upload_limits.max_file_bytes + 1)
            for role in ("front", "reverse")
        }
        total_bytes = sum(map(len, payloads.values()))
        if (
            any(len(payload) > self.upload_limits.max_file_bytes for payload in payloads.values())
            or total_bytes > self.upload_limits.max_total_bytes
            or session.staged_bytes + total_bytes > self.upload_limits.max_session_bytes
        ):
            raise _RequestError("upload_too_large", 413)
        normalized = {role: _normalize_image(payload, self.upload_limits) for role, payload in payloads.items()}
        if _digest(normalized["front"][0]) == _digest(normalized["reverse"][0]):
            raise _RequestError("duplicate_media", 400)
        root = self.staging_root / _digest(session_id) / uuid4().hex
        root.mkdir(parents=True, exist_ok=False)
        result: dict[str, Path] = {}
        try:
            for role, (payload, suffix) in normalized.items():
                path = root / f"{uuid4().hex}{suffix}"
                path.write_bytes(payload)
                result[role] = path
            return result, total_bytes
        except OSError as error:
            self._remove_paths(result.values())
            raise _RequestError("staging_unavailable", 503) from error

    @staticmethod
    def _remove_paths(paths: Any) -> None:
        for path in paths:
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass


class _RequestError(Exception):
    def __init__(self, category: str, status: int) -> None:
        self.category = category
        self.status = status


def _normalize_image(payload: bytes, limits: UploadLimits) -> tuple[bytes, str]:
    """Decode a supported still image and re-encode it without input metadata."""
    try:
        with Image.open(BytesIO(payload)) as probe:
            image_format = probe.format
            frames = getattr(probe, "n_frames", 1)
            probe.verify()
        if image_format not in {"JPEG", "PNG"} or frames != 1:
            raise ValueError("unsupported image")
        with Image.open(BytesIO(payload)) as source:
            if (
                source.width > limits.max_dimension
                or source.height > limits.max_dimension
                or source.width * source.height > limits.max_pixels
            ):
                raise ValueError("image dimensions exceed limit")
            mode = "RGBA" if image_format == "PNG" and "A" in source.getbands() else "RGB"
            normalized = source.convert(mode)
            output = BytesIO()
            normalized.save(output, format=image_format)
            return output.getvalue(), ".jpg" if image_format == "JPEG" else ".png"
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        raise _RequestError("unsupported_image", 400) from error


def _digest(value: str | bytes) -> str:
    return sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()
