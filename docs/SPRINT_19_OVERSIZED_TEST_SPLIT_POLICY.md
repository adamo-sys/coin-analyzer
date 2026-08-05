# Sprint 19 - Oversized Test Split Policy

## Purpose

This document freezes the fifth bounded architecture unit of Sprint 19: oversized test split policy for the OCR review and desktop test surface.

This unit is intentionally architecture-only. Its job is to define the split boundaries and validation policy for test-file decomposition before any test move is authorized. It does not change production behavior, does not change test assertions, and does not introduce new helpers or factories.

## Scope statement

This unit governs only the mechanical decomposition of oversized test modules into smaller, behavior-oriented test modules.

In scope:

- identifying which oversized modules are included in Sprint 19
- defining the split boundaries by behavior/domain
- defining destination-module naming and ownership
- preserving unittest discovery and import behavior
- validating that each split is mechanical only

Out of scope:

- production refactors
- builder-module expansion beyond the current test-only contract
- persistence or migration implementation
- test semantics changes, assertion rewrites, or behavioral looseness
- broad repository cleanup beyond the approved test split

## Included modules

The current architecture unit is limited to the following oversized OCR/review-related test files:

- `tests/test_desktop_ocr_candidate_review.py`
  - current line count: 1844
  - current test count: 99
- `tests/test_schema3_runtime.py`
  - current line count: 1468
  - current test count: 24
- `tests/test_workflow_ocr_confidence_calibration.py`
  - current line count: 1333
  - current test count: 73

Important note:

This document does not authorize splitting all three modules at once. The first split must be limited to exactly one source file, and only the file that is most clearly behavior-partitionable should be moved first.

## First authorized split target

The first implementation slice must be:

- `tests/test_desktop_ocr_candidate_review.py`

Rationale:

- it is the most behaviorally partitionable file in the current Sprint 19 scope
- it already has strong internal boundaries around model/controller behavior, preview behavior, keyboard shortcut behavior, and state integration
- it does not depend on the same runtime or persistence concerns as the other two candidates

## Split policy

Each split must be a pure test-file reorganization. The architecture unit allows only the following kinds of changes:

1. moving existing test methods into a new destination file
2. adjusting import lines required by the destination file
3. preserving the same test names and same unittest discovery pattern
4. keeping the same assertions, fixtures, and setup semantics

The split must not:

- change a test’s expected outcome
- change a test’s class or method identity in a way that alters discovery
- introduce new production dependency paths
- fold unrelated behavior into a shared test utility for convenience

`TestCase` class names must also be preserved unless a compelling reason exists to rename them. IDEs, failure grouping, and CI reporting frequently surface failures by class name, so split mechanics should keep those names stable.

## Proposed destination module map for the first split

The first split of `tests/test_desktop_ocr_candidate_review.py` must be organized by behavior, not by arbitrary line count.

### A. Model and controller behavior

Destination file:

- `tests/test_desktop_ocr_candidate_review_model.py`

Ownership:

- `OCRCandidateReviewModelTests`
- controller wiring and review-state bootstrap tests
- candidate display setup and deterministic ordering behavior

This file should contain the tests that exercise the model as the primary contract and keep controller lifecycle behavior close to the model-level expectations.

### B. Preview, crop, and image adjustment behavior

Destination file:

- `tests/test_desktop_ocr_candidate_review_preview.py`

Ownership:

- preview rendering behavior
- crop and normalized-crop behavior
- zoom, contrast, and preview adjustment behavior
- image review adjustment store behavior

This file should remain focused on preview and rendering semantics instead of mixing them into controller or model wiring tests.

### C. Navigation, selection, and shortcut behavior

Destination file:

- `tests/test_desktop_ocr_candidate_review_shortcuts.py`

Ownership:

- shortcut window binding behavior
- focus and key handling
- navigation and keyboard selection behavior
- accessibility-sensitive navigation tests

This file should keep the Tk/Tkinter-like UI coordinate and shortcut assertions together.

### D. Callback and review-state integration behavior

Destination file:

- `tests/test_desktop_ocr_candidate_review_callbacks.py`

Ownership:

- callback integration tests
- review-state transitions
- async callback or idempotence-sensitive integration concerns
- any behavior that couples model decisions to controller side effects

This file should specifically capture behavior that is not purely display rendering or keyboard action.

## Rules for destination naming

Destination names must follow the same test discovery contract already in use by the repository:

- file name must begin with `test_`
- module ownership must be obvious from the name
- destination names must remain behavior-oriented and readable
- destination names must not become generic buckets such as `test_desktop_ocr_candidate_review_2.py`

The preferred pattern is:

- `test_<domain>_<behavior>.py`

Examples:

- `test_desktop_ocr_candidate_review_model.py`
- `test_desktop_ocr_candidate_review_preview.py`
- `test_desktop_ocr_candidate_review_shortcuts.py`

## Fixture and import strategy

The split must preserve current direct imports and fixture semantics.

Rules:

1. Move tests only, not production support code.
2. Keep shared helper usage local to the test cluster where the helper is genuinely required.
3. Do not introduce a new global test utility just to support the split.
4. Preserve existing `unittest`-style class layout where possible.
5. If a helper is genuinely reused across the new destination modules, promote it only if it remains behavior-neutral and clearly test-only.
6. Do not create a catch-all test fixture module for the split.

The split should remain mechanical unless a test requires a small import adjustment to satisfy the new file boundary.

A helper should live with the behavior that conceptually owns it. Promotion to shared scope is permitted only when at least two destination modules require the helper without introducing behavioral coupling.

## Target thresholds

The split is considered acceptable only when all of the following are true:

- a source file is split into smaller domain-oriented modules
- no destination module exceeds a scope that makes it difficult to read quickly
- no destination module becomes a generic grab-bag for unrelated functionality
- test discovery remains unchanged from the unittest perspective
- no assertion semantics are altered

The target threshold for the first split is intentionally conservative:

- split one oversized file only
- preserve behavior-by-domain partitioning
- validate the new module layout before authorizing any additional file moves

## Validation protocol

Before any move is made, the architecture baseline must be captured by running the existing source test file:

```bash
python -m unittest tests.test_desktop_ocr_candidate_review
```

After the first split is complete, validate the new module layout with focused command(s) that preserve the same test coverage and discovery contract. The exact post-split validation must be limited to the newly created destination modules and the original source-module identity after renaming is completed.

The sum of tests discovered across the destination modules must equal the number of tests discovered in the original source module immediately prior to the split. This threshold is the primary guard against accidentally dropping a test during test-file reorganization.

The expected validation outcome is:

- all moved tests still execute
- the summed destination-module test count equals the pre-split source-module count
- same test names are preserved where possible
- `TestCase` class names are preserved unless there is a compelling reason to rename them
- no new failures appear from import, fixture, or discovery changes
- no behavioral assertions are weakened or rewritten

## Mechanical-only split rule

A split is mechanical only when the following are true:

- the split does not alter object construction semantics
- the split does not create new runtime behavior
- the split does not change controller or model expectations
- the split does not change the underlying test case intent
- the split does not introduce production-side import or factory changes

If any split requires production code movement, new fixture classes, shared setup abstraction, or assertion simplification that is not strictly file placement, it is out of scope for this architecture unit.

## Stop conditions

This architecture unit must stop and require a new approval gate if any of the following occur:

- shared setup or shared fixture state becomes order-dependent across the new destination files
- one new file starts to depend on another file’s local test helpers in a way that creates hidden coupling
- a destination module becomes a catch-all for unrelated behaviors
- the split would require production-code changes to make the test boundaries clean
- discovery semantics would change in a way that makes the split non-mechanical
- a test ordering or side-effect problem appears that cannot be explained by simple file movement
- the split introduces additional setup duplication that exceeds the removed duplication, which must be treated as a stop-and-review condition rather than an invitation to continue abstracting

## Non-goals

This document does not authorize:

- replacing existing tests with a new abstraction layer
- moving runtime builders or factories into test support code
- broad test refactoring for style or readability alone
- turning the split into a repository-wide fixture consolidation effort
- starting multiple overlapping test-file moves before the first split passes validation

## Freeze note

This document freezes the oversized test split policy unit for Sprint 19.

It establishes the architecture baseline for one bounded mechanical split, beginning with `tests/test_desktop_ocr_candidate_review.py`, and explicitly forbids expanding the scope into broader test reorganization before the first split has been reviewed and validated.
