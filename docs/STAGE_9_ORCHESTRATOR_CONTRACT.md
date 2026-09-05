# Stage 9 Orchestrator Contract

## Status

Architecture freeze for Stage 9. This document defines the permitted orchestration boundary before implementation begins.

Stage 9 coordinates existing bounded roles. It does not create a new source of implementation, review, or promotion authority.

## Objective

Provide a deterministic coordinator that sequences one self-improvement work package through the existing guarded pipeline while preserving explicit evidence, fail-closed transitions, and human promotion authority.

Canonical flow:

`evaluator evidence -> Diagnostic Agent -> RemediationPackage -> bounded Codex handoff -> ImprovementResult -> Independent Reviewer -> HUMAN`

## Authority boundary

The Orchestrator MAY:

- accept one explicitly selected work package/evidence input;
- invoke existing bounded roles in the frozen sequence;
- pass structured artifacts between those roles;
- record deterministic state transitions and terminal reasons;
- stop immediately when a required role or gate fails;
- surface successful machine-side evidence as ready for human review;
- surface conflicts, malformed evidence, and unresolved issues to the repository owner.

The Orchestrator MUST NOT:

- merge, deploy, release, promote, or approve changes on behalf of the repository owner;
- silently expand allowed implementation or review scope;
- repair implementation failures itself;
- manufacture missing diagnostic, validation, or invariant evidence;
- retry failed implementation/review work automatically;
- create an autonomous improvement loop;
- mutate authoritative collection data;
- silently mutate models, prompts, configuration, or evaluation policy;
- select a new remediation target after a terminal result;
- bypass the Independent Reviewer or required repository gates.

## State model

Stage 9 must use explicit states rather than free-form agent conversation. Initial implementation should remain intentionally small.

Required states:

1. `PENDING` — package accepted but no role invoked.
2. `DIAGNOSED` — bounded diagnostic evidence accepted.
3. `PACKAGE_FROZEN` — implementation scope, invariants, focused tests, and required gates are immutable for this run.
4. `IMPLEMENTATION_COMPLETE` — the bounded operational handoff returned a completed result that passed its implementation-side review.
5. `REVIEW_COMPLETE` — independent reviewer returned PASS with required invariant evidence.
6. `READY_FOR_HUMAN_REVIEW` — machine-side orchestration completed; no promotion authority is implied.
7. `STOPPED` — terminal fail-closed state with an explicit reason and last successful state.

A run may move only forward through the authorized sequence or to `STOPPED`.

## Structured run artifact

The implementation should produce one immutable/deterministic run result containing at minimum:

- run identifier supplied by the caller;
- current/terminal state;
- diagnostic evidence reference or structured diagnostic result;
- frozen remediation package;
- implementation result;
- implementation review result;
- independent reviewer report;
- transition history;
- terminal reason when stopped;
- explicit `human_review_required = true` for successful runs.

Missing artifacts must remain missing; the Orchestrator may not synthesize evidence to advance state.

## Fail-closed rules

The run must enter `STOPPED` when any of the following occurs:

- malformed or missing required input;
- diagnostic role failure;
- invalid remediation package;
- executor exception or malformed `ImprovementResult`;
- implementation status `STOPPED`;
- out-of-scope changed files;
- missing or failed required validation;
- unresolved blocking issues;
- missing, contradictory, unexpected, or failed invariant evidence;
- Independent Reviewer recommendation `FAIL`;
- attempted state skip, retry, scope broadening, or evidence replacement.

No transition may occur after `STOPPED`.

## Determinism and traceability

Given the same structured role outputs, the Orchestrator must produce the same state transitions and terminal decision.

Transition records should identify:

- from-state;
- to-state;
- bounded reason/event;
- evidence type used for the transition.

Do not store hidden chain-of-thought or require free-form inter-agent transcripts. Persist/report structured evidence and concise reasons only.

## Initial implementation scope

The first Stage 9 code slice should be orchestration logic only. Prefer a small module such as `orchestrator.py` plus focused tests.

It should compose the existing contracts rather than duplicate their logic:

- evaluator/diagnostic artifacts;
- `RemediationPackage` and `ImprovementResult`;
- operational Codex handoff;
- Stage 7 fail-closed implementation review;
- Stage 8 independent reviewer.

## Required focused tests

At minimum cover:

- valid sequential run reaches `READY_FOR_HUMAN_REVIEW`;
- each authorized state transition is recorded in order;
- malformed input stops before execution;
- diagnostic/package failure stops before implementation;
- executor exception stops the run;
- malformed implementation result stops the run;
- out-of-scope changes stop the run;
- failed/missing required gate stops the run;
- implementation `STOPPED` cannot advance;
- unresolved blocking issue cannot advance;
- reviewer FAIL cannot advance;
- failed/missing/contradictory invariant evidence cannot advance;
- attempted scope broadening cannot advance;
- attempted state skip/retry cannot advance;
- terminal STOPPED runs cannot resume automatically;
- successful runs still require human review and expose no merge/promotion authority.

## Explicit Stage 10 exclusions

Stage 9 does not include:

- parallel agents;
- competing remediation candidates;
- swarm/group-chat behavior;
- automatic repeated diagnosis/remediation cycles;
- autonomous target selection;
- autonomous PR creation or merge;
- adaptive agent routing based on self-generated policy.

Those remain Stage 10+ concerns and require a separate architecture decision after the sequential pipeline demonstrates reliable behavior.

## Promotion boundary

`READY_FOR_HUMAN_REVIEW` is the strongest successful Stage 9 terminal state.

It means only that the bounded machine-side pipeline completed with the required structured evidence. Repository-owner review and normal repository/CI promotion gates remain mandatory.
