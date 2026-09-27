# Mobile Coin Entry + Human Verification — North Star Plan

Status: planning proposal; no implementation authorization is implied.

Planning base: `origin/main` at `095ccaea66874e7311e4f1218060161d5adf65c2`
(merged PR #342). This plan supersedes no frozen persistence, import, or visual
review contract. E7 optimization, reference-image acquisition, embeddings,
Coin-CLIP, and inference work are expressly out of scope.

## Executive decision

Build the smallest end-to-end slice as a **local, responsive web interface**
served by the desktop application, with a thin localhost/LAN HTTP adapter over
existing application services. It is preferable to a native application or a
PWA because the owner needs a showable phone workflow, not background/offline
mobile behavior, installation, push notifications, or cross-device sync. A
phone browser can use the camera/file chooser without duplicating the domain
model or creating an app-store distribution problem.

When idle, the host binds loopback only. A usable phone session is an explicit,
local-owner action that temporarily enables LAN exposure and requires an
ephemeral pairing secret displayed in the trusted desktop UI. Mobile requests
are untrusted input. Recognition and OCR remain optional proposal producers;
only a human-reviewed, explicitly confirmed save may call the existing
collection persistence path.

## Current-state architecture map and reusable components

```text
Phone image files
  -> new Mobile HTTP/UI boundary (missing)
  -> safe staged files + PhoneIntake.confirm_pair (reuse)
  -> existing visual/OCR proposal construction (reuse when available)
  -> existing review/edit/explicit confirmation semantics (reuse/adapt)
  -> managed-media copy + CoinCollection guarded atomic save (reuse)
  -> reopen by collection item ID + photos/provenance (extend presentation)

Existing desktop/import workflows remain authoritative; no mobile client writes
collection JSON, managed-media paths, or provenance directly.
```

| Concern | Existing evidence to reuse | Milestone-1 implication |
| --- | --- | --- |
| Explicit two-side pairing and recovery | `phone_intake.PhoneIntake`: `confirm_pair`, `swap`, `reserve`, `complete`, `clean_save_failure`; `docs/architecture/PHONE_INTAKE.md` | Preserve its two-distinct-image and READY/SAVING/SAVED state machine. Do not infer roles from filename, time, or adjacency. |
| File inbox/staging | `photo_inbox.PhotoInboxManager`, `phone_drop_import.PhoneDropImporter`, `capture_import.standalone_image_intake` | Reuse only safe staging/validation patterns; mobile uploads need their own bounded request policy rather than a shared-folder watcher. |
| Pair/session abstraction | `photo_capture_workflow.PhotoCaptureSession` and `PhotoCaptureWorkflow.capture_coin_pair` | Adapt its explicit front/back session model for the request-facing draft service. |
| Identity proposal/evidence | `ocr_assisted_identification.OCRIdentificationEngine.identify_from_session`; visual-review contracts in `docs/architecture/VISUAL_IDENTIFICATION.md` | Show available OCR/visual proposals, field evidence, source/model disclosure, and absences separately. No fusion or confidence reinterpretation. |
| Human review | `capture_import.desktop_visual_identity_review.ConfirmedVisualIdentity.to_reviewed_coin_draft`, `capture_import.reviewed_coin_collection_entry.ReviewedCoinDraft` / `persist_reviewed_coin` | The mobile UI needs a review form, not a second decision engine: country, denomination, year, and type/design remain editable and the confirmation is explicit. Do not reuse `MobileCollectionEntryEngine`, which derives new confidence summaries. |
| Collection model | `coin_collection.CoinItem`, `PhotoRole`, `IdentificationStatus`, `ItemPhoto` | Reuse country, denomination, year, `type_design`, front/back photo roles, and identification status. No new collection identity schema in the first slice. |
| Media ownership | `capture_import.standalone_image_intake.create_temporary_capture_package`, `capture_import.image_store.ManagedCollectionImageStore`, and the exercised phone flow in `tests/test_phone_intake.py` | Preserve the existing package → snapshot → validated managed-image transaction. Never retain phone-controlled paths in a saved item. |
| Persistence/rollback | `capture_import.reviewed_coin_collection_entry.persist_reviewed_coin`, `CoinCollection.save_collection` / `add_item`; reviewed-save acceptance suite; `docs/architecture/ORDINARY_COLLECTION_BASELINE.md` | Save through the existing package bridge, lock/baseline/atomic-write guard, snapshot cleanup, and managed-image cleanup. Failed or stale saves are not retried automatically. |
| Audit/provenance | `PhoneIntake` image SHA-256 reservation; `CaptureImportMediaProvenance`; visual-review evidence contracts | First slice needs a small, additive, local entry-audit record; capture-import-only provenance must not be misused for phone uploads. |
| Desktop UI boundary | `gui.CoinAnalyzerGUI`, `phone_intake_dialog.open_phone_intake` | Desktop owns launch, LAN enablement, pairing display, and recovery. Phone UI is a client, not a new authority. |
| Tests | `test_phone_drop_import.py`, `test_photo_inbox.py`, `test_photo_capture_workflow.py`, `test_mobile_collection_entry.py`, `test_persistence_manager.py`, desktop visual review/save tests | Extend synthetic, temporary-directory test patterns; do not use `test_coins/` or collection data. |

No existing HTTP framework or production web route was found in the inspected
Python source/dependency declarations. That is a genuine gap, not a reason to
adopt a native app.

## Gaps and recommended minimum architecture

The current code is desktop/file-workflow oriented. It does not yet provide:

1. a local authenticated HTTP listener or responsive page;
2. request-size, image-decoding, and CSRF controls at a network boundary;
3. a mobile-upload staging owner with the same lifecycle guarantees as desktop
   intake;
4. a request-to-reviewed-draft adapter that exposes *existing* proposal and
   confirmation semantics without Tk widgets; or
5. a durable, path-free audit record that distinguishes machine proposal,
   collector edits, confirmation, and saved item for direct phone entry.

Create one new application boundary, conceptually `mobile_entry_service`, with
four narrow responsibilities:

1. **Desktop host controller** — starts/stops a loopback listener by default;
   enables LAN only after an owner action; creates/revokes a single-use pairing
   secret; reports bound address and active sessions.
2. **Mobile session API/UI** — issues same-origin, cookie-backed sessions only
   after pairing; accepts one obverse and one reverse upload into a private
   staging root; presents a review page.
3. **Reviewed-draft adapter** — turns the verified pair into the existing
   temporary capture package, derives the source coin ID from its validated
   manifest, then calls `ReviewedCoinDraft` / `persist_reviewed_coin` with that
   package. It never accepts a provider result as a save command and does not
   invent a parallel ordinary-entry media transaction.
4. **Audit/reopen adapter** — records the proposal snapshot, source/evidence
   summaries, human field values, confirmation time, pair/media hashes, and
   resulting item ID; reopening is a read-only view composed from the saved
   `CoinItem`, its managed photos, and that audit record.

Use server-rendered, mobile-first HTML with a small amount of progressive
enhancement. Do not add a PWA manifest/service worker in Milestone 1. Choose a
minimal, maintained local Python HTTP dependency only after an implementation
packet compares the existing runtime constraints; the architecture requires a
well-tested multipart parser and request middleware, not a hand-rolled server.

## Proposed mobile flow

1. On the desktop, the owner starts “Phone entry”; the host is loopback-only
   until the owner deliberately starts one paired LAN session.
2. The owner enables that short-lived LAN session and scans/types the pairing
   code from the desktop display on the phone.
3. The phone opens one responsive page, chooses/captures an obverse and reverse
   image, previews both, assigns/switches sides, and submits.
4. After device pairing has already completed, the server validates and stages
   the images, then calls `PhoneIntake.confirm_pair`. Coin pairing is explicit;
   duplicate/changed/unsupported images fail closed.
5. The review page shows initial blank fields plus whatever approved existing
   OCR/visual proposal and evidence is available. If all proposal providers
   abstain or fail, the same page remains fully usable for manual entry.
6. The collector edits country, denomination, year, type/design, and supported
   optional item fields, sees source evidence distinct from edits, and presses
   “I verify this identity.”
7. A second explicit “Save verified coin” confirmation invokes the established
   managed-media plus guarded collection transaction. The mobile UI cannot
   bypass either confirmation.
8. On success, `PhoneIntake.complete` verifies the actual disk record and image
   hashes, marks the pair saved, writes the audit record, and returns a stable
   item URL. On any ambiguous outcome it displays recovery-required status and
   offers no automatic resave.
9. Reopening shows the two managed images, saved collector-owned fields, original
   proposal/evidence snapshot, edits, confirmation, audit identifiers, and item
   ID—not a reconstructed claim of machine certainty.

## Trust and security model

| Boundary | Required safe default / control |
| --- | --- |
| Exposure | Loopback bind while idle. A phone session uses an explicit, visibly active, short-lived LAN bind from the desktop UI and stops/revokes sessions when disabled. Never bind a public interface by default. |
| Authentication/pairing | Per-host-start high-entropy, short-lived pairing secret; single-device session; Secure cookies when HTTPS exists, otherwise SameSite=Strict + host-only cookie and clear LAN-risk copy. No ambient desktop trust from source IP alone. |
| Request forgery | Same-origin POST-only mutations, session-bound CSRF token, Origin/Host validation, no credentialed cross-origin CORS. GET is read-only. |
| Uploads | Allow JPEG/PNG only; reject HEIC/HEIF for M1 consistently with `PhoneIntake`; enforce per-file, aggregate/session, pixel/dimension, decode-time and request-count ceilings before persistent staging. Multipart filenames are discarded. |
| Paths/files | Generate server-side IDs/names; staging and managed roots are fixed; no client path, URL, MIME claim, EXIF text, or filename drives a path. Verify image bytes/decoder format, reject animation/multi-frame inputs, strip or ignore untrusted metadata for display/audit. |
| Resource isolation | Decode/thumbnail work has bounded buffers and a later subprocess decision if real hostile-image risk demands it. Never render unbounded errors, EXIF, OCR, model output, or notes as HTML. |
| Provider/machine authority | Provider output is data only: bounded/validated, preserved as proposal evidence, never interpreted as an authorization token. Only the paired authenticated human session may set `human_verified`; the server rechecks it immediately before save. |
| Persistence | The service calls one reviewed-save adapter that retains `CoinCollection` baseline, lock, atomic publication, media-copy verification, rollback, and no-auto-retry behavior. No HTTP route writes collection JSON directly. |
| Audit/privacy | Store relative/opaque identifiers and hashes, not phone filenames, absolute paths, raw EXIF, cookies, pairing secrets, provider credentials, or raw exceptions. Keep all data local. No telemetry/cloud synchronization. |
| Failure/recovery | Pair READY/SAVING/SAVED and explicit reconciliation remain authoritative. Crashes, stale collection baseline, lost session, provider failure, or failed audit finalization leave a visible local recovery state; none permits a second automatic save. |

The exact LAN transport policy is the only material implementation decision still
open: a plain HTTP LAN listener can be acceptable only for a short-lived,
trusted-home-LAN demo with a conspicuous warning and pairing secret; routine LAN
use should require local TLS or a trusted reverse-proxy boundary. This decision
is required before the LAN host packet: phone access is a Milestone-1 requirement,
while loopback-only remains the safe idle/default state.

## Data and provenance

Do not overload `CaptureImportMediaProvenance`: it is a closed schema for
processed package imports. Add a separate versioned, local-only phone-entry audit
sidecar keyed by pair ID and saved item ID, with:

- opaque entry/pair/session IDs and timestamps;
- SHA-256 and front/back roles for staged and saved managed media;
- proposal source identifiers/version, raw bounded proposed values, field-level
  evidence references/summaries, and explicit `absent` values;
- exact collector-entered final fields, explicit verification/second-save
  confirmations, and a field-change list (`proposal`, `human_final`);
- collection item ID and final persistence/reconciliation state.

It must not contain an asserted probability, invented ground truth, raw provider
payloads beyond the existing bounded contract, absolute paths, device IPs,
filenames, EXIF, secrets, or unrelated collection notes. An unresolved audit
write after collection success is a recovery state, not license to repeat the
collection save.

## API/interface boundary

Keep routes private to the local UI and map them to service methods, not models.
Device authentication and coin-image pairing have deliberately different routes:

- `POST /session/pair` — exchanges the short-lived desktop-displayed pairing
  secret for one session; no image data is accepted.
- `POST /drafts` — requires that authenticated session, accepts two bounded
  uploads, and returns an opaque coin pair/draft ID.
- `GET /draft/{id}` — read-only review representation, including proposal and
  evidence/absence states.
- `POST /draft/{id}/verify` — validates human edits and records explicit human
  verification; does not persist a collection item.
- `POST /draft/{id}/save` — requires a fresh CSRF/session confirmation and runs
  the reviewed-save transaction once.
- `GET /items/{id}` — read-only saved-record/provenance presentation.
- `POST /host/stop` — desktop-local owner control only, not exposed to the phone.

All write responses use opaque IDs and stable error categories. APIs never
return filesystem paths, provider credentials, raw stack traces, or a mutation
capability derived from model output.

## Testing strategy and Milestone-1 definition of done

Use synthetic JPEG/PNG fixtures and temporary directories only. Start with pure
service tests, then local HTTP integration tests, then the existing reviewed-save
acceptance composition pattern.

Required automated coverage:

- pairing, swap, duplicate hash, unsupported/malformed/oversized image, changed
  staging image, retry and restart/SAVING recovery;
- request/session/CSRF/Origin failures, expired/reused pairing secret, loopback
  default, and explicit LAN enable/disable;
- manual-only entry after proposal abstention/failure; proposal values/evidence
  remain distinct from corrections; model output cannot assert verification;
- managed-media copy/hash verification, stale collection and rollback failures,
  exact-once save/reconcile, audit-finalization recovery, reopen view;
- HTML escaping/path traversal/filename/EXIF/oversized error boundaries and
  privacy-safe audit fields;
- a manual phone acceptance run: capture/select both images, edit every identity
  field, verify/save, restart/reopen, inspect images and provenance, and try a
  rejected or interrupted save.

Milestone 1 is done only when the owner can deliberately start a paired local
LAN session and perform that loop on a phone, manual entry works with no
proposal, no direct client-side collection mutation exists, all focused tests
pass, and the normal repository gates pass for the exact implementation head.
It does not claim recognition accuracy or general network hardening beyond the
documented scope.

## Explicit non-goals

- native iOS/Android application, app-store distribution, PWA/offline sync, push
  notifications, background capture, multi-user collaboration, or cloud state;
- automatic pairing, automatic acceptance, confidence calibration, visual/OCR
  fusion, recognition benchmarking, model tuning, E7 work, reference acquisition,
  embeddings, or provider replacement;
- bulk intake, package import redesign, shared-folder watching, collection schema
  migration, backup/sync redesign, or inferred ground truth;
- public internet exposure, remote administration, or retaining sensitive phone
  metadata.

## Tooling queue triage

This triage re-ranks the post-RC queue against this vertical slice; it does not
authorize installation or adoption.

| Disposition | Candidate | Rationale |
| --- | --- | --- |
| NOW | Existing workflow/harness (`tools/task-state.py`, task packets, focused unittest/Ruff/CI) | Already present and directly reduces change/review risk for each M1 packet. Use it; do not create another orchestration layer. |
| NOW | Existing synthetic visual-review/save acceptance pattern | Directly proves the highest-risk composition: explicit review through media transaction, guarded persistence, and reopen/recovery. It is test design, not a new tool adoption. |
| LATER | Browser/computer-use tooling (Playwright MCP / device automation) | Useful after the responsive UI exists for repeatable browser smoke tests, but current T7 is a public-research advisory boundary and is not a phone-authentication or product-test solution. Manual phone acceptance is first. |
| LATER | Architecture visualization / Graphify | Existing Graphify experiment can help orient implementation packets; no evidence it is critical to the thin adapter or merits runtime adoption. |
| LATER | Agent orchestration / Goose / alternate harnesses | Could help independent review after bounded packets exist, but adds no user-visible capability and cannot replace current contracts or CI. |
| LATER | Repository/context packaging, Headroom, Context Mode, OmniRoute, DeepSeek Harness | The post-RC inventory identifies them as unevaluated bake-off candidates. Revisit only if current task packets cannot keep bounded implementation/review work efficient. |
| LATER | Advisory enforcement/testing (selected mutation, Semgrep, SBOM/Harden-Runner follow-up) | Retain existing advisory evidence; consider focused use where the new HTTP parsing/auth code merits it, but do not delay the demo with a new gate. |
| ARCHIVE for M1 | Document ingestion | No document corpus is required to capture, review, or save a coin. |
| ARCHIVE for M1 | New browser research, AI framework, model/retrieval, image-token compression, or automatic-agent tooling | Not on the critical path; adds trust, privacy, or exact-recall risk without enabling manual phone entry. Existing policy already keeps pxpipe research-only. |

## Risks and open questions

1. **LAN transport:** decide the required paired-LAN transport posture for the
   demo: constrained trusted-LAN HTTP with explicit warning and short-lived
   pairing, or TLS/a trusted reverse-proxy boundary. This changes security
   posture and must be explicitly approved before the LAN host is implemented.
2. **HTTP dependency:** select a minimal maintained local framework/multipart
   parser after confirming compatibility, licensing, and update policy; do not
   hand-roll security middleware.
3. **Save adapter seam:** retain the already exercised phone bridge:
   `PhoneIntake.review_paths` → `create_temporary_capture_package` → validated
   manifest source ID → `ReviewedCoinDraft` / `persist_reviewed_coin` →
   `PhoneIntake.complete`. A focused contract packet must prove both
   confirmations and every rollback path survive the request-facing adaptation.
4. **Audit sidecar durability:** define its atomicity/recovery relationship to a
   successful collection save before code exists. It cannot weaken collection
   success or cause a duplicate save.
5. **Real-device UX:** portrait orientation, camera permission, image size, and
   home-LAN reachability need a manual acceptance run; unit tests cannot prove
   them.

## Implementation sequence (bounded PR-sized packets)

1. **Contract and seam extraction:** approve route/session/audit schemas and
   formalize a Tk-independent service around the existing `PhoneIntake` →
   temporary capture package → `persist_reviewed_coin` bridge; tests prove no
   authority regression. No listener yet.
2. **Local host security boundary:** after the owner approves the LAN transport
   posture, add a loopback-idle/explicit-paired-LAN host controller,
   pairing/session/CSRF policy, bounded upload staging, and synthetic HTTP
   security tests. No provider call required.
3. **Responsive pair and manual-review slice:** add server-rendered pages for
   capture/select, front/back swap, manual fields, verification, and save
   confirmation. Wire manual-only reviewed save and reopening; acceptance tests
   exercise full persistence/recovery.
4. **Proposal presentation:** adapt currently available OCR/visual proposal DTOs
   into the same review page as advisory evidence, preserving absence/conflict
   states and no automatic write authority. Manual path remains unchanged.
5. **Real-device acceptance:** verify the opt-in paired LAN lifecycle on the
   target phone, including stop/revocation and recovery. Broader or routine LAN
   use remains deferred until its transport decision is reviewed.

Each packet is independently reviewed and may be stopped without blocking the
manual desktop workflow. No packet starts E7 or changes frozen evaluation data.

## Recommended first implementation packet

**Packet 1: “Phone-entry reviewed-save service contract.”** Its scope is the
smallest proof that phone UI work can reuse existing authority safely: specify a
`PhoneEntryDraft`/service boundary around the existing non-Tk phone bridge:
`PhoneIntake` pair → temporary capture package → manifest source ID →
`ReviewedCoinDraft` / `persist_reviewed_coin`. It produces only a validated,
human-confirmed save request; defines the audit-sidecar recovery states; and
adds synthetic contract tests for manual-only, explicit confirmation, stale
save, rollback, and no-auto-resave. It introduces no HTTP server, LAN binding,
provider call, or browser UI.

This packet should finish with a reviewed API contract and an executable
service-level test suite. Only then should the project select an HTTP framework
and construct the phone-facing surface.
