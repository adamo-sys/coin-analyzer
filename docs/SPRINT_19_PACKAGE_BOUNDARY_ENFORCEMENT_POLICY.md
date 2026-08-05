# Sprint 19 - Package-Boundary Enforcement Policy

## Purpose

This document freezes the sixth bounded architecture unit of Sprint 19: formal
package-boundary enforcement for the OCR review surface.

This unit defines boundary contracts and enforcement expectations. It does not
change OCR review behavior, does not change persisted payload shape, and does
not authorize GUI, persistence, or collection behavior expansion.

## Scope statement

This unit governs runtime import boundaries for OCR review modules under
`capture_import`.

In scope:

- explicit module-layer boundaries for OCR review workflow, persistence, and
  desktop composition
- fail-closed import allowlist enforcement policy
- validation expectations for boundary drift

Out of scope:

- feature changes
- DTO schema changes
- migration behavior
- test assertion rewrites unrelated to import boundaries
- repository-wide import policy beyond OCR review modules

## Current repository evidence

The OCR review surface already contains architecture boundary checks distributed
across focused suites, including:

- `tests/test_workflow_ocr_review_controller.py`
- `tests/test_workflow_ocr_review_presenter.py`
- `tests/test_workflow_ocr_review_session.py`
- `tests/test_workflow_ocr_review_persistence_models.py`
- `tests/test_workflow_ocr_review_persistence_service.py`
- `tests/test_workflow_ocr_review_local_repository.py`
- `tests/test_desktop_ocr_review_composition.py`
- `tests/test_desktop_ocr_review_integration.py`
- `tests/test_desktop_ocr_review_persistence.py`
- `tests/test_desktop_ocr_review_persistence_controls.py`
- `tests/test_desktop_ocr_conflict_review.py`
- `tests/test_desktop_ocr_candidate_review.py`

These checks prove intent, but they are fragmented and not yet expressed as one
formalized boundary-enforcement unit for Sprint 19.

## Boundary model

### Layer A - OCR review domain/workflow

Primary modules include:

- `capture_import.workflow_ocr_models`
- `capture_import.workflow_ocr_review_models`
- `capture_import.workflow_ocr_review_service`
- `capture_import.workflow_ocr_review_session`
- `capture_import.workflow_ocr_review_presenter`
- `capture_import.workflow_ocr_review_controller`

Required boundary:

- must not import desktop modules (`capture_import.desktop_*`)
- must not import GUI frameworks (`tkinter`, `PyQt`)
- must not perform filesystem/environment side effects unless explicitly owned
  by a persistence module

### Layer B - OCR review persistence boundary

Primary modules include:

- `capture_import.workflow_ocr_review_persistence_models`
- `capture_import.workflow_ocr_review_persistence_service`
- `capture_import.workflow_ocr_review_local_repository`

Required boundary:

- persistence models/service remain headless (no desktop imports)
- repository owns local file I/O mechanics; service/models do not absorb those
  responsibilities
- persistence modules must not import collection mutation or confirmed
  observation modules

### Layer C - Desktop OCR review integration boundary

Primary modules include:

- `capture_import.desktop_ocr_review_composition`
- `capture_import.desktop_ocr_review_handoff`
- `capture_import.desktop_ocr_candidate_review`
- `capture_import.desktop_ocr_conflict_review`
- `capture_import.desktop_ocr_review_persistence`
- `capture_import.desktop_ocr_review_persistence_controls`

Required boundary:

- desktop modules may depend on workflow contracts
- default desktop path must remain OCR-review opt-in
- desktop integration modules must not absorb collection persistence ownership
  or confirmed-observation ownership

## Enforcement policy

Package-boundary enforcement must be fail-closed:

1. each in-scope module receives an explicit runtime import allowlist
2. any non-allowlisted runtime import fails tests
3. allowlist drift (missing expected imports or newly added imports) fails tests
4. `TYPE_CHECKING`-only imports are excluded from runtime boundary accounting

### Deterministic boundary accounting rules

Boundary checks compare resolved module names, not substring fragments. For
example, `collections.abc` is treated as the stdlib module `collections.abc`
and must not be flagged by string-fragment rules such as `"collection"`.

Import-boundary enforcement for this unit is limited to runtime import surface
verification. It does not claim to prove non-import side-effect behavior such
as filesystem writes, environment mutation, or runtime state mutation.

Function-local imports are part of the runtime import surface and are included
in boundary accounting.

### Import category handling

Enforcement must handle categories explicitly:

- standard library imports: allowed only when present in each module's explicit
  stdlib allowlist
- third-party imports: allowed only when present in each module's explicit
  third-party allowlist
- project imports (`capture_import.*`): allowed only when present in each
  module's explicit package allowlist
- relative imports: resolved to canonical absolute module names before allowlist
  comparison
- `TYPE_CHECKING` imports: excluded from runtime boundary accounting
- wildcard imports (`from x import *`): rejected fail-closed by the resolver

The preferred enforcement style is the existing AST-based runtime-import
resolver approach already used in `tests/test_workflow_reference_stages.py`.

## Validation gate for this unit

This architecture unit is complete when:

- OCR review module groups are explicitly listed by boundary layer
- import-direction rules are explicit and fail-closed
- enforcement style and drift behavior are defined
- scope exclusions are explicit

## Implementation unit expectation (next unit)

The follow-on implementation unit may add or consolidate tests to enforce the
above boundary model. It must:

- preserve existing behavior
- remain test-only
- avoid production refactors
- use focused module validation for touched OCR review suites

## Non-goals

This document does not:

- authorize production dependency rewiring
- authorize persistence schema changes
- authorize migration mechanics
- authorize broader package-policy rewrites outside OCR review scope

## Freeze note

This document freezes only the Sprint 19 package-boundary enforcement policy
unit for OCR review modules.

No behavioral, persistence, or migration change is authorized by this document.
