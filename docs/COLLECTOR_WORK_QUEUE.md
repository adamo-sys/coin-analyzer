# Collector Work Queue contract

Work Queue derives immutable, read-only tasks from the current authoritative
collection. It performs no persistence, inference from filenames, provider calls,
or collection/media mutation. The supported rules are exactly:

| Task | Eligibility | Resolution | Priority |
|---|---|---|---|
| Confirm identity | Explicit PARTIAL or UNIDENTIFIED status | Explicit IDENTIFIED status | P1 |
| Add reverse photo | COIN without a normalized BACK role, including no photos | BACK role present; BANKNOTE exempt | P2 |
| Record purchase price | Price absent and any shipping/premium/tax explicitly present, including zero | Price present, including zero | P3 |

Country/year/title/free text do not independently determine identity tasks.
Acquisition date/source alone do not establish missing price. Photo normalization
uses detached metadata; unavailable files, paths and provenance do not determine
role. Evidence is bounded and does not display private paths.

Task IDs contain rule version, task type, and opaque stable item ID. They are not
authorization tokens. Sorting is deterministic by priority/type, valid leading ISO
date (invalid dates last), then stable ID. Duplicate/blank IDs and invalid load
states fail closed. MISSING is distinct from LOADED with zero tasks.

The GUI captures `CollectionItemReference` for every displayed projection at
refresh time, retaining these references across filters. Activation resolves the
original reference against the active collection before recomputing eligibility.
Replacement collection/record, reload, reused or ambiguous ID, or resolved task
refuses the old action and refreshes. It never looks up a new target by ID alone.
The existing editor independently captures/checks a reference at open/save and
uses main's media-safe update service. Successful saves refresh the queue; failed
saves do not report resolution. No task state is persisted.

One reusable native Tk window provides exact counts, All/Identity/Photos/Acquisition
filters, selection, button/double-click/Return activation and refresh. Empty,
missing and invalid states have distinct copy. Native automated behavior and
visual/manual acceptance must be reported separately.

Scope excludes Command Center, Sprint wording, schema migration, AI, ranking
experiments, and the local browser/restore ancestors. Reconstructed from committed
Work Queue behavior at dbf6de6/c98dffc, with fresh metadata, on merged main
dcf5bb3b7599f9a839221a2d3912615e04de265f. Original commits are not replayed.

## Acceptance evidence (2026-09-09)

Windows Python 3.14.6 / Tk 8.6, synthetic data only:

- 107 focused tests passed across the projection, GUI/controller, foundation,
  confirmed observations and Photo Inbox entry modules. After adding strict
  non-enum refusal and duplicate-ID coverage, all 45 projection tests passed.
- Two opt-in native Tk tests passed in 6.947 seconds. They create mapped real Tk
  widgets, invoke their actual callbacks, and use the real collection/editor/media
  service. They cover filtering, selection, repeated opening, identity save,
  failed-save retention, zero-price save, adding a reverse photo, source-byte
  preservation/managed copy, queue resolution, collection reload and queue reopen,
  and stale collection replacement refusal. Dialog/file-picker responses and the
  host collection-list refresh are harness-controlled; this is not a full-app
  manual usability run.
- Run native tests explicitly with `RUN_WORK_QUEUE_NATIVE=1` and
  `python -B -m unittest tests.test_work_queue_native_acceptance -v` on a desktop
  with Tk available. They skip during ordinary headless discovery.
- Ruff 0.16.5 E9 passed. Pyright 1.1.411 found zero diagnostics in the new modules;
  70 GUI diagnostics match the merged foundation's file/rule/message baseline.
  The editor and whole repository are not claimed type-clean.
- Separate native launch was observed through the OS accessibility tree. Screenshot
  capture failed twice with `SetIsBorderRequired failed: No such interface
  supported (0x80004002)`; Tk controls appeared as unnamed panes. Visual layout,
  mouse-driven usability, minimum-size visibility and manual keyboard navigation
  remain unverified. No screenshot is claimed.

Local evidence is preserved beside the reconstruction checkout in
`work-queue-focused.log`, `work-queue-projection-final.log`,
`work-queue-native-behavior.log`, `work-queue-reconstructed-accessibility.json`,
`work-queue-ruff-final.log` and `work-queue-pyright-final.json`.
Normal PR CI supplies broader regression evidence before merge.
