# Stage 11 Specialized Candidate Roles Contract

## Status

Architecture freeze only. Stage 11 may be implemented only after the Stage 10 two-candidate runtime and reliability gate are merged and green.

Stage 11 does not increase candidate count or promotion authority. It specializes the two existing bounded candidate roles so they can explore meaningfully different implementation strategies against the same frozen work package.

## Objective

Improve the value of the Stage 10 comparison by making candidate intent explicit rather than merely running two indistinguishable implementation roles.

Initial canonical experiment:

`one frozen RemediationPackage -> two explicit strategy roles -> independent Stage 7/8 validation and review -> deterministic aggregate evidence -> HUMAN`

The first specialized pair is:

1. `MINIMAL_CHANGE` — prefer the smallest compliant implementation that satisfies the frozen package.
2. `ALTERNATIVE_DESIGN` — pursue a materially different bounded implementation approach while preserving the exact same scope, invariants, tests, and gates.

These are strategy constraints, not independent authorities.

## Shared authority boundary

Both strategy roles MUST receive the exact same:

- frozen `RemediationPackage`;
- allowed paths;
- invariants;
- focused tests;
- required gates;
- candidate-local invariant evidence contract;
- promotion boundary.

A strategy role MUST NOT:

- rewrite or reinterpret the frozen package;
- broaden allowed paths;
- weaken or replace required gates;
- modify another candidate's strategy or evidence;
- inspect the other candidate's output before completing its own result;
- request additional candidates;
- retry itself automatically;
- merge or synthesize candidate code;
- select a new target;
- mutate collection data, prompts, models, configuration, or evaluation policy outside explicit reviewable scope;
- merge, deploy, release, promote, or approve changes.

## Strategy semantics

### MINIMAL_CHANGE

The role SHOULD:

- minimize changed-file count;
- minimize implementation surface;
- reuse existing repository abstractions when reasonable;
- avoid speculative refactors;
- preserve behavior outside the frozen remediation objective.

The role MUST still satisfy every package invariant, test, and required gate. Minimality never overrides correctness or safety.

### ALTERNATIVE_DESIGN

The role SHOULD:

- pursue a meaningfully different implementation structure from the minimal-change strategy when the frozen package permits it;
- remain within the exact same allowed paths and authority boundaries;
- document concise structured rationale for the chosen bounded alternative;
- avoid architecture expansion unrelated to the remediation objective.

The role MUST NOT intentionally increase scope merely to appear different. If no materially different compliant implementation exists, it may return a normal bounded result that is similar to the minimal candidate.

## Structured strategy evidence

Each candidate artifact should include immutable structured strategy metadata:

- candidate ID;
- strategy kind (`MINIMAL_CHANGE` or `ALTERNATIVE_DESIGN`);
- concise strategy summary;
- implementation result;
- Stage 7 implementation review;
- Stage 8 reviewer report;
- candidate terminal state and reason.

Do not persist hidden chain-of-thought or free-form inter-agent transcripts.

## Deterministic comparison

Stage 11 does not authorize an LLM judge to choose a winner subjectively.

Comparison remains structured and deterministic. The existing Stage 10 rules continue to apply. Strategy metadata may be surfaced to the human reviewer but MUST NOT silently override gate, invariant, scope, or reviewer evidence.

A preferred candidate may be surfaced only when existing deterministic criteria distinguish the viable candidates. Otherwise both remain viable and the repository owner decides.

## Candidate isolation

The two strategy roles remain isolated:

- fixed at exactly two candidates for the initial Stage 11 slice;
- one execution per candidate;
- no automatic retries or replacements;
- no agent-to-agent communication;
- no shared mutable strategy state;
- no candidate output exposure before both complete;
- candidate-local rejection does not automatically invalidate the other candidate.

## Experiment integrity STOP conditions

The experiment must fail closed when:

- strategy kinds are missing, duplicated, or outside the frozen pair;
- candidate IDs are empty or duplicated;
- either candidate receives a different remediation package;
- a role attempts to alter scope, invariants, tests, or required gates;
- strategy metadata is assigned to the wrong candidate;
- dynamic candidate creation or replacement is attempted;
- candidate outputs are automatically composed;
- autonomous retry or target reselection is attempted;
- evidence becomes contradictory or malformed at the experiment level.

## Initial implementation scope

The first Stage 11 runtime slice should be narrow:

- retain exactly two candidates;
- extend the candidate specification with a frozen strategy kind;
- render strategy-specific bounded instructions without changing the `RemediationPackage`;
- reuse the existing Stage 10 execution, Stage 7 validation, and Stage 8 review boundaries;
- add structured strategy metadata to aggregate results;
- preserve existing deterministic comparison and human-review behavior;
- require no real concurrency;
- add no new execution authority.

A small extension to `parallel_experiment.py` plus focused tests is preferred over a new orchestration stack.

## Required focused tests

At minimum cover:

- exactly one `MINIMAL_CHANGE` and one `ALTERNATIVE_DESIGN` candidate are accepted;
- duplicate strategy kinds stop before execution;
- unknown strategy kinds stop before execution;
- strategy metadata is preserved in candidate artifacts;
- both candidates receive the same frozen package;
- strategy instructions cannot broaden allowed paths or required gates;
- each candidate executes exactly once;
- candidate-local failures remain isolated;
- identical structured inputs produce identical aggregate decisions;
- strategy metadata alone never auto-promotes a candidate;
- tied viable candidates remain unresolved for human selection;
- no candidate output is visible to the other before completion;
- no retry, replacement, synthesis, merge, deploy, release, or promotion authority exists.

## Explicit exclusions

Stage 11 does not authorize:

- more than two candidates;
- real-time group chat;
- dynamic routing among specialists;
- recursive delegation;
- autonomous target discovery;
- repeated self-improvement loops;
- automatic candidate synthesis;
- learned routing or self-modifying strategy policy;
- production deployment;
- autonomous pull-request creation or merge.

Any move to more candidates, real concurrency, or multiple specialist domains requires a separate architecture decision and new reliability evidence.

## Promotion boundary

The strongest machine-side outcome remains one or more viable candidates presented for human review.

Human repository-owner selection, normal CI, and explicit merge/promotion remain mandatory.
