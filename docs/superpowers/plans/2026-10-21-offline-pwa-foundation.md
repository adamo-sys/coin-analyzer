# Offline PWA foundation implementation plan

Goal: independently testable local shell and atomic entry/photo storage, without
enabling production provisioning or any collection operation.

Authority: owner Phase 1 authorization; main/base
`c0dada400991c9be75a72a4a3373816df87b33f6`; prospective design:
`docs/architecture/OFFLINE_COIN_SHOW_DESIGN.md` sections 3, 6, 7, 9 and
`OFFLINE_COIN_SHOW_AMENDMENT_PROPOSAL.md`. Native implementation in this session,
with a fresh read-only verifier against the exact resulting commit.

## Bounded task contract

GOAL: Build and prove offline startup, local persistence and non-destructive migration.
IN SCOPE: New `offline_pwa/` shell, storage/media modules, worker template,
manifest/icons, package/lock, browser tests and README; `tools/build_offline_pwa.py`;
`tests/test_offline_pwa_build.py`; this implementation plan. Commit/push/PR after gates.
OUT OF SCOPE: Production auth/listeners, certificates, deployment, desktop import,
bundles/restore, reconciliation, purchases/comparisons, existing Save behavior.
PROTECTED BOUNDARIES: Primary checkout, private material, test_coins, baselines,
governance, filesystem Phase 1. No production enablement or offline-ready claim.
ACCEPTANCE GATES: Synthetic real-browser offline/persistence/migration/fault tests;
build and JS/Python static checks; root regression and existing CI; exact-commit
independent PASS/PASS WITH NOTES; owner device/security acceptance remains pending.
STOP CONDITIONS: Authority/architecture mismatch, authentication dependency,
privacy risk, blocking review/validation, scope expansion and AGENTS budget stops.

## One independently reviewable work package

- [ ] Write failing browser tests for cached startup with absent cookie/network,
  committed entry/photo readback, v1-to-v2 migration, blocked/future/corrupt DB,
  stale revisions, transaction abort/quota, and rejected/partial shell installation.
- [ ] Run the tests and confirm missing implementation fails. Use only synthetic
  PNGs and loopback test fixtures. The fixture server is not product authentication.
- [ ] Implement `openStore() -> {list, commit, close}` in `storage.js`;
  `normalizePhoto(blob, role)` in `media.js`; minimal app/manifest and worker.
  Version 2 adds metadata to the documented v1 entry/photo stores. Preserve UUIDs,
  revisions and blobs. Reject unknown schemas; never delete/reset a database.
- [ ] Build via `python tools/build_offline_pwa.py OUTPUT` into a new directory.
  Compile a content-addressed shell manifest into the worker; never copy arbitrary
  repository files. All protected fetches remain a future private server boundary.
- [ ] Exercise offline deep links and persistence in a fresh browser page. Exercise
  incomplete/denied/corrupt updates without deleting the previous shell or local data.
- [ ] Run Python build tests, JS syntax checks, browser suite, Ruff and root unittest.
  Review exact path set, commit, obtain fresh independent verdict; resolve any
  blocking findings and re-review exact revised commit per repository runbook.
- [ ] Push the isolated branch, verify current-head blocking CI and open owner PR.
  Never merge/deploy. Report head, review, gates and remaining acceptance limits.

## Limits and review focus

Entry cap 200; total normalized photos 128 MiB; reserve 32 MiB advisory headroom;
8 photos/entry, 16 MiB/photo, 30 MP, 8000 pixels/edge. No automatic eviction.
Persistence requests and estimates are advisory; actual transaction errors control.
Readiness stays blocked: real HTTPS/pairing/session enforcement, iPhone lifecycle,
verified private recovery copy and snapshot/target functionality are not in this slice.

Review focus: blocked opens completing after timeout; commit readback uncertainty;
worker replacement with login/partial assets; protected navigation bypass through
fallback; multi-window revision races. Each receives a browser assertion.

## Execution evidence

Preflight: isolated sparse worktree clean at exact base; protected images excluded.
Existing primary branch/HEAD and four modified-file hashes recorded in task.
Plan interfaces agree: app consumes normalized photos and store commit/list; browser
tests build the identical worker/shell artifact that future provisioning would serve.
No production authentication is available or implemented; deployment is blocked.
