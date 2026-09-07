# Visual review save acceptance

This bounded offline suite checks the composition of the existing
[visual review contract](architecture/VISUAL_IDENTIFICATION.md) and
[ordinary collection baseline contract](architecture/ORDINARY_COLLECTION_BASELINE.md).
It adds no production authority or architecture behavior.

## Acceptance surface

`tests/test_visual_review_save_acceptance.py` runs four named cases (eight
review/save attempts):

1. Unchanged existing storage: operator-corrected identity and exact paired image
   bytes survive reopening the collection.
2. Another window saves while the review is open: two successive attempts fail
   without replacing newer bytes, changing stale memory, retaining new photos,
   deleting unrelated photos, or announcing success. Only explicit reload then
   permits a new reviewed save; the other window's edit survives.
3. Storage appears after a missing first-run load: the reviewed save fails closed;
   explicit reload then permits a fresh attempt.
4. Storage disappears after load: the reviewed save does not recreate it;
   explicit reload establishes missing storage and permits a fresh attempt.

Every attempt runs real image intake, package validation, request/proposal
construction, daemon execution, GUI callback orchestration, reviewed-draft
creation, managed-photo copy/cleanup, ordinary persistence, and source cleanup.
The test drives the scheduled completion callback on the caller thread and
checks that the provider ran elsewhere. It verifies both disclosure and final
save confirmation, one temporary-source release, removal of snapshots, unchanged
input images, and truthful success/error messages. The stale paths must reach
real image copying, so an earlier unrelated error cannot pass the rollback test.

Only native widgets/dialogs and provider output are synthetic; a wrapper injects
temporary image/snapshot/lock paths into the real reviewed persistence service.
Two generated JPEG/PNG color panels and one unrelated retained PNG form the
entire corpus. The hard-coded answer is a workflow stimulus, not image ground
truth or a claim about recognition quality. No key, SDK, internet, private files,
or existing photographic corpus is needed. Managed paths use an explicit test
prefix; collection data and assets remain in disposable temporary directories.

## Reproduce and interpret

From the repository with configured dependencies:

```text
python -m unittest -v tests.test_visual_review_save_acceptance
python -m unittest tests.test_desktop_visual_identity_review tests.test_desktop_visual_identity_execution tests.test_reviewed_coin_collection_entry tests.test_stale_collection_baseline tests.test_standalone_image_intake
python -m py_compile tests/test_visual_review_save_acceptance.py
```

Verbose unittest output identifies the failed journey and assertion, including
exact-byte comparisons and rollback/source-leak diagnostics. Redirect stdout
and stderr to a local log if an artifact is needed; tests retain no images or
collection exports. No new runner or CI configuration is required: root unittest
discovery includes this module. GitHub Actions remains broad regression authority.

Local verification: 4 acceptance tests passed, 0 skipped, 0 failures. Native Tk
rendering, live-provider quality/availability, crashes, and cross-process lock
contention are outside this suite. Intervening writes use a second real
`CoinCollection` under the existing lock, deterministically before confirmation;
this does not claim protection against arbitrary writers racing after validation.

## Bounded ROI audit (current main after PRs 192-194)

These are acceptance gaps found in a representative sample, not confirmed
production defects or an exhaustive repository audit.

| Rank / gap | User failure and severity | Existing coverage / missing composition | Cost / fixture / impact |
| --- | --- | --- | --- |
| 1. Reviewed visual save across external storage change | Lost newer records, false success, or orphaned images; critical data safety | `test_desktop_visual_identity_review` has a real successful save; `test_reviewed_coin_collection_entry` covers cleanup; `test_stale_collection_baseline` covers stale CRUD. Separate tests cannot establish their combined transaction and GUI outcome. | Small; generated image pair and two collections. Protects the complete reviewed-save journey. Implemented here. |
| 2. CSV stale import through desktop feedback | Batch import appears successful or overwrites a newer collection; high | `test_csv_import` checks parsing/quantities; baseline tests cover CRUD; GUI inspects `last_save_error`. A backend-only test cannot prove the GUI reports the same failed transaction. | Small; synthetic CSV and two collections. Protects batch import trust. |
| 3. OCR conflict resolution through failed final save and retry | Resolution appears saved despite failure, or wrong confirmed fields persist; high | OCR integration tests cover human decisions/corrections; standalone intake covers successful real save/reload. Separate review/persistence tests do not prove the failed final journey. | Medium; generated pair and deterministic OCR evidence. Protects manual correction authority. |
| 4. Cancellation with real temporary assets | Late result or cleanup leaves unwanted records/assets; high | `test_desktop_visual_identity_execution` covers late success/failure and single release with source doubles; intake tests check actual release independently. Doubles do not prove on-disk lifecycle composition. | Small; generated pair and event-gated fake provider. Protects cancellation trust. |
| 5. Launcher uses installed environment and exposes startup failure | Double-click opens nothing despite successful documented venv installation; medium | README uses `.venv`; `Launch_Coin_Analyzer.bat` selects PATH pythonw/python/py and reports process launch rather than app readiness. No launcher acceptance test found in the sample. | Medium; isolated Windows interpreter stubs and native smoke. Improves first-run reliability; separate platform-specific slice. |

The chosen slice crosses the most consequential newly hardened boundaries with
two files and no production changes. Existing frozen recognition benchmarks are
left untouched; this is transaction acceptance, not another accuracy benchmark.
