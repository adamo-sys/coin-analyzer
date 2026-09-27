# Phone Entry Local Host Boundary (Packet 2)

## Scope and framework decision

This document defines the local HTTP boundary added in Packet 2. It adapts the
Packet 1 `PhoneEntryService`; it does not add a mobile review interface,
recognition provider, collection schema, or a new persistence path.

The implementation uses **Flask 3.1.x** with its maintained Werkzeug WSGI and
multipart parser. The repository previously had no HTTP framework. Flask 3.1
supports Python 3.9 and newer, including this repository's Python 3.14 runtime,
and provides request-size/form-part limits and a test client. The dependency is
bounded as `Flask>=3.1,<4`; it is intentionally the only new direct HTTP
dependency. Multipart parsing is never hand-written.

## Owner lifecycle and exposure

`LocalPhoneEntryHost` starts stopped. `start_loopback()` is the safe desktop
action: it sets the binding to `127.0.0.1`, clears old sessions, and creates a
fresh pairing secret. `enable_lan(private_numeric_address)` is a distinct,
desktop-only action. Packet 2 accepts only private non-loopback IPv4 numeric
addresses (IPv6 awaits explicit Host-authority parsing); it revokes existing
sessions and creates a fresh secret. `stop()` clears every session and pairing
value before returning the host to idle. None of these controls has an HTTP
route.

The desktop integration is responsible for using `binding.host` when it starts
the local WSGI listener. Packet 2 does not add a desktop control or responsive
phone page; those are expressly Packet 3 work. In all cases the established
transport is constrained trusted-LAN HTTP: no public bind, port forwarding,
autodiscovery, remote administration, or credentialed CORS is permitted.

## Pairing, session, and request policy

- A pairing secret is generated with `secrets.token_urlsafe(32)`, with a
  SHA-256 comparison value and the desktop-display value retained only in host
  memory. It expires after 120 seconds and is consumed exactly once.
- Pairing creates at most one opaque server-side session. The browser receives
  a host-only cookie with `HttpOnly` and `SameSite=Strict`; no `Domain` attribute
  is set. The cookie is intentionally not marked `Secure` because the approved
  LAN posture is HTTP, not TLS.
- Every mutation is POST-only, requires an authenticated session, a
  session-bound CSRF token, an allowed Host, and an exact matching `http` Origin
  (including the Host header's port).
  Allowed loopback hosts are only `localhost` and `127.0.0.1`; an enabled LAN
  session accepts only its owner-selected private address.
- No route emits CORS headers. `GET` routes are read-only.
- The host generates one-use, action-bound approval capabilities internally
  immediately before calling `PhoneEntryService.verify` or `.save`. They are
  never accepted from client JSON and are consumed by the host verifier, so a
  provider/model assertion cannot authorize either transition.

## Upload boundary

`POST /drafts` requires exactly `front` and `reverse` multipart files plus the
CSRF field. Client filenames, MIME claims, and EXIF never control a path or
leave the boundary. Each image is bounded before persistence, decoded by Pillow,
must be a single-frame JPEG or PNG, and is subject to file/request/session byte,
request-count, dimension, and pixel ceilings. It is then re-encoded to a fixed
server-generated name beneath the fixed private staging root, removing inbound
metadata. Duplicate media is rejected before `PhoneIntake.confirm_pair`.

The request adapter calls only this existing sequence:

`PhoneEntryService.create_draft` → `PhoneIntake.confirm_pair` → existing
temporary capture-package bridge → `ReviewedCoinDraft` / guarded persistence.

It never writes collection JSON itself. Packet 1 still detects staged-media
changes before save and enters recovery rather than retrying a potentially
ambiguous save.

## Stable API surface

| Route | Policy |
| --- | --- |
| `POST /session/pair` | Single-use secret exchange; returns CSRF token and host-only session cookie. |
| `POST /drafts` | Authenticated, CSRF-protected bounded image staging and Packet 1 draft creation. |
| `GET /draft/<id>` | Session-scoped, read-only Packet 1 draft representation. |
| `POST /draft/<id>/verify` | Session-scoped explicit identity verification via host-issued approval. |
| `POST /draft/<id>/save` | Session-scoped separate save confirmation via host-issued approval. |
| `GET /items/<id>` | Authenticated, read-only saved-item projection. |

Errors expose only stable categories and status codes. They do not include paths,
filenames, pairing/session values, raw exceptions, or tracebacks.

## Validation limits

The automated suite uses temporary directories and synthetic JPEG/PNG/GIF bytes.
It proves host lifecycle configuration, pairing expiry/reuse, stop revocation,
session/CSRF/Host/Origin rejection, method restriction, decoder and filename
boundaries, duplicate prevention, staged-media tamper recovery, and the real
Packet 1 verify/save seam. It does not replace the future Packet 3 responsive
UI or the owner-performed real-device LAN acceptance run.
