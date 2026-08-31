# Coin Analyzer AI Project Context

## Product Goal

Build a desktop coin/banknote analysis system supporting:

scan → identify → review → save

Target demo: complete the scan → review → save workflow in under 2 minutes.

## Evaluation Goal

Acceptance Set v1:

- 30 total cases
- 24 identify cases
- 6 abstain cases
- at least 24 distinct specimens
- no more than 2 cases per specimen
- ground truth authored before execution
- specimen-weighted metrics

## Core Invariants

- Stable item IDs are authoritative.
- Visible GUI row/index positions are never authoritative identity.
- Restore/reload invalidates stale GUI mappings.
- Ground truth must never be inferred from model output.
- PARTIAL is a legitimate persisted state.
- UNIDENTIFIED is a legitimate persisted state.
- Missing data must not be fabricated.
- Evaluation evidence must remain reproducible.
- Execution results must remain separate from authored ground truth.

## Engineering Philosophy

Prefer:

- the smallest correct patch
- explicit contracts
- regression tests
- reproducibility
- measurable evidence

Avoid:

- speculative architecture
- unrelated refactors
- new dependencies without justification
- weakening tests
- rewriting working systems unnecessarily
- claiming validation that was not executed

## Definition of Done

A unit is complete only when:

- requested behaviour exists
- acceptance criteria are satisfied
- focused tests pass
- relevant regression tests pass
- no unrelated behaviour changed
- no required TODO remains
- completion claims are supported by evidence

## AI Execution Rules

For implementation work:

1. Verify repository, branch, and expected HEAD before editing.
2. Work only within the requested mode and scope.
3. Prefer the smallest correct patch.
4. Do not weaken existing tests to accommodate new code.
5. Do not infer or rewrite authored ground truth.
6. Do not claim validation that was not actually executed.
7. Treat accepted project decisions as binding unless new evidence proves a contradiction.
8. Report completion claims as VERIFIED, INFERRED, or UNVERIFIED.
