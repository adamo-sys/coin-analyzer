# First-coin workflow plan and evidence — 2026-10-15

## Contract

- GOAL: Demonstrate first manual coin save, reopening, stable identity, editing,
  and independent second-coin persistence with synthetic data.
- IN SCOPE: `tests/test_first_coin_workflow.py` and this evidence document;
  isolated branch, commit, push, one draft PR.
- OUT OF SCOPE: Production behavior changes, dependencies, CI changes, broad
  refactors, recognition policy, corpus/oracle work, deployment, and merge.
- PROTECTED BOUNDARIES: Temporary collections and generated RGB PNGs only;
  no live records, private photographs, external providers, or live startup services.
- ACCEPTANCE GATES: Focused lifecycle, persistence, photo, CSV identity, stale
  detection, integrity/privacy, relevant Ruff/Pyright, and independent review.
- STOP CONDITIONS: Blocking findings, unsafe side effects, scope expansion,
  more than two repair iterations, and repository context limits.

## Baseline and finding

Fetched `origin/main`: `070b4030be92c127994abacc719b7ab3c2bc1ece`.
GitHub confirms merged PR #408 at `2c22efd864cd689c69bf80f8a839abbf1cc5c3ca`
and #409 at the base SHA. Original checkout and unrelated edits were preserved.
Worktree: `first-coin-workflow/coin-analyzer`; branch: `test/first-coin-workflow`.

Existing tests exercise photo round trips, OCR-assisted save/reload, CSV identity,
collection integrity, stale detection, and native editor behavior separately.
The missing protection is one manual first-coin lifecycle spanning these stages.
No production defect was demonstrated; this change adds coverage only.
Both new tests pass against unchanged production code at the verified base.

## Implementation plan and result

- [x] Add a service lifecycle using `CoinCollectionApp`, real image validation,
  `CollectionItemReference`, and ordinary edit persistence.
- [x] Add a real Tk callback lifecycle using existing `__new__`/`create_widgets`
  test infrastructure, an injected temporary collection, real entry/editor widgets,
  and a stubbed native file chooser. Skip only when Tk has no display.
- [x] Verify baseline behavior with the new tests; run focused regression/static
  and privacy/integrity gates. No defect was manufactured to create this change.
- [x] Complete independent review; commit/push/open one draft PR and leave
  it unmerged. Publication status belongs in the PR/task report.

## Exercised acceptance

| Step | Evidence |
| --- | --- |
| 1. No collection file | Both tests assert the configured temporary file is absent. |
| 2. Initialize | Real app/collection; Tk test builds real widgets with injected app. |
| 3. Select/import image | Service uses real image validation; Tk invokes Add Photos with generated PNG chooser results and verifies a real preview. |
| 4. Manual details | Literal synthetic fields passed to the app or set in real Tk entry state. |
| 5. First save | Ordinary app save and real Save to Collection button callback. |
| 6. File creation | File absent before save; present at the configured temporary path afterward. |
| 7. Stable ID | Nonblank ID, retrieval by that ID across reopenings, distinct second ID. |
| 8. Close/reopen | New collection/app instances; Tk roots destroyed and recreated. |
| 9. Retrieve metadata | Explicit fields, item/status enums, manual provenance flags, photo paths/roles/primary/order, date, acquisition details, and source bytes checked. |
| 10. Edit/reopen | Ordinary app edit and real editor Save callback; pre-edit snapshots allow only the intended notes change. |
| 11. Independent second coin | Both survive reload; first snapshot unchanged. Service also edits second coin and rechecks the first. |
| 12. Recognition optional | Recognition initialization and socket creation raise if attempted; the manual workflow succeeds. |

## Validation

Configured interpreter: existing project virtual environment, Python 3.14.6;
Tk 8.6, Ruff 0.16.5, Pyright 1.1.411. No dependencies were added.

Baseline: 36 CSV identity, stale-detection, and collection-integrity tests passed.
Final bounded validation: **134 tests passed, no skips**, in 27.135 seconds:

```text
python -m unittest tests.test_first_coin_workflow
  test_phase1c_multi_photo_gui tests.test_standalone_image_intake
  tests.test_stale_collection_baseline tests.test_csv_import_identity
  tests.test_csv_stale_import_acceptance tests.test_stale_detection_invalidation
  test_persistence_manager tests.test_durable_persistence_contracts
  tests.test_durable_persistence_services test_collection_integrity
  tests.test_repository_privacy_boundaries tests.test_evaluation_case_contract -q
```

- Ruff configured checks on `tests/test_first_coin_workflow.py`: passed.
- Pyright on the new test with explicit project interpreter: 0 errors/warnings.
- Ratcheted CI Pyright boundary (all 11 files in `.github/workflows/tests.yml`):
  0 errors/warnings. These production files were unchanged.
- Privacy/evaluation/integrity checks are included in the 134-test run.
- In-memory fault probes produced the expected test failures for omitted disk
  saves, duplicate generated IDs, overwritten manual country, and acquisition
  source lost during edit. No production source was modified for these probes.
- Full local regression was not run; Windows/Ubuntu full regression, Ruff syntax,
  Gitleaks, and bounded Pyright remain authoritative GitHub Actions merge gates.
  No local Gitleaks executable was available; no tool was installed.

Initial sandboxed checks could not write temporary directories/Ruff cache or
resolve installed PIL/cv2 dependencies. Reruns outside the sandbox passed with the
existing interpreter explicitly selected. Those environment failures were not
classified as application defects.

Two repair iterations were used: (1) correct an invalid test enum assertion to the
existing manual-identity contract and make Tk cleanup safe after explicit close;
(2) sort imports and strengthen pre-edit metadata preservation assertions following
review. No further production or test repairs are authorized by this task.

## Independent review

Independent read-only verifier `/root/first_coin_review`: **PASS WITH NOTES** against test SHA-256:
`D9ACE7327FC0C5798715C462B21CC1A5BE7B13046D757B3C709DF9456FD967C4`.
The reviewer identified that the initial test could miss acquisition metadata
loss during edit. An in-memory fault reproduced that gap. Pre-edit snapshots now
pin every serialized field except the intended notes edit; the same fault now
fails the test as expected. The verifier explicitly confirmed resolution in the
final snapshot (Git blob `25a1d00ccebd41944405dc64c886ef773350e560`), with no
remaining blocking findings. Its own optional probe was blocked by sandbox
permissions and was not counted as validation. Review notes match the coverage
limits below. Final evidence-document edits were initially implementer-verified.
The final test file also passed a fresh two-test run after formatting cleanup.
Staged whitespace checks passed for both files.

## Coverage limits and manual acceptance

The GUI constructor is deliberately bypassed to avoid default data/services.
Native file selection is stubbed; packaged startup, physical mouse/keyboard input,
layout usability, and operating-system process restart remain manual acceptance.
Destroying/recreating Tk roots and collection/app instances exercises widget and
storage reload lifecycle, not full packaged desktop end-to-end coverage.
The GUI test skips on hosts without a Tk display; the service test always runs.

Images are referenced at their original synthetic paths in ordinary initial entry;
this change does not promise that deleting or moving an external source image is
safe. Source image bytes remain unchanged throughout the exercised workflow.
No new production filesystem behavior is introduced. Local-first persistence,
recognition abstention, provenance, collection identity, and existing records are
unchanged.
