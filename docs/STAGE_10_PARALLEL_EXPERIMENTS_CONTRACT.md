# Stage 10 Parallel Experiments Contract

## Status

Architecture freeze for Stage 10. This document defines the permitted boundary for bounded parallel-agent experiments after the Stage 9 reliability gate passed.

Stage 10 is an experiment layer over the existing guarded pipeline. It does not replace Stage 9, weaken human review, or grant any agent additional promotion authority.

## Objective

Allow multiple bounded candidate roles to work on the same explicitly caller-selected problem so Coin Analyzer can compare alternatives without turning the system into an autonomous swarm.

Initial canonical experiment:

`one frozen RemediationPackage -> N bounded candidate implementations -> independent evaluation/review of each -> deterministic comparison -> HUMAN`

The first implementation slice should use a small fixed candidate count, preferably two.

## Core authority boundary

The parallel experiment layer MAY:

- accept one caller-owned, frozen work package;
- dispatch that exact package to a fixed bounded set of candidate execution roles;
- require each role to return the same structured `ImprovementResult` contract;
- evaluate each candidate independently against the same allowed paths, invariants, tests, and required gates;
- preserve candidate identity and traceability;
- compare passing candidates using explicit caller-supplied comparison criteria;
- surface zero, one, or multiple viable candidates for human review;
- terminate fail-closed when experiment-level evidence is malformed or contradictory.

It MUST NOT:

- let one candidate modify another candidate's scope or evidence;
- let candidates converse freely or negotiate scope;
- create recursive or repeated remediation loops;
- spawn additional agents dynamically;
- select a new target after the experiment starts;
- silently alter the frozen package between candidates;
- merge candidate changes together automatically;
- promote, merge, deploy, release, or approve any candidate;
- mutate collection data, prompts, models, configuration, or evaluation policy outside explicit reviewable scope;
- bypass Stage 7 validation, Stage 8 independent review, Stage 9 authority boundaries, or repository CI.

## Isolation model

Each candidate must be logically independent.

Required properties:

- unique caller-supplied candidate identifier;
- same frozen remediation package for every candidate;
- independent execution result;
- independent validation/review evidence;
- no candidate receives another candidate's output before producing its own result;
- no shared mutable experiment state that can alter candidate behavior mid-run;
- candidate failure does not trigger retry or replacement automatically.

A candidate may fail without invalidating the evidence from other candidates, but the experiment result must record the failure explicitly.

## Candidate states

Each candidate should use an explicit bounded state model:

1. `PENDING`
2. `EXECUTED`
3. `VALIDATED`
4. `REVIEWED`
5. `VIABLE`
6. `REJECTED`

Transitions are forward-only. `VIABLE` and `REJECTED` are terminal candidate states.

The experiment itself should terminate in one of:

- `NO_VIABLE_CANDIDATES`
- `ONE_VIABLE_CANDIDATE`
- `MULTIPLE_VIABLE_CANDIDATES`
- `STOPPED`

None of these states grants merge or promotion authority.

## Structured experiment artifact

The first implementation should return one immutable/deterministic experiment result containing at minimum:

- experiment identifier supplied by the caller;
- frozen remediation package;
- ordered candidate identifiers;
- per-candidate implementation result;
- per-candidate Stage 7 implementation review;
- per-candidate Stage 8 reviewer report;
- per-candidate terminal state and terminal reason;
- experiment-level terminal state;
- viable candidate identifiers;
- deterministic comparison result when more than one candidate is viable;
- explicit `human_review_required = true` whenever any candidate is viable.

Do not persist hidden chain-of-thought or free-form inter-agent transcripts. Store structured evidence and concise bounded reasons only.

## Deterministic comparison

Stage 10 must not invent a subjective winner from unstructured reasoning.

For the initial slice, comparison criteria must be explicit and caller-supplied or frozen by the contract. Suitable deterministic criteria include:

- all required gates passed;
- all invariants passed;
- no unresolved blocking issues;
- fewer changed files when scope/effect is otherwise equivalent;
- fewer reported risks when risk entries are structured and comparable;
- stable caller-supplied priority order as a final tie-breaker.

If the evidence cannot distinguish viable candidates deterministically, the result should preserve multiple viable candidates and defer selection to the human repository owner.

## Fail-closed rules

The experiment must enter `STOPPED` when experiment-level integrity fails, including:

- empty or duplicate candidate identifiers;
- candidate count outside the frozen bound;
- package mismatch across candidates;
- malformed experiment request;
- attempted dynamic candidate creation;
- evidence assigned to the wrong candidate;
- duplicate/contradictory experiment-level evidence;
- attempted automatic merge/composition of candidate changes;
- attempted scope broadening;
- attempted autonomous retry or replacement.

Candidate-local implementation or review failures should normally mark that candidate `REJECTED`, not automatically stop other already-authorized candidates.

## Initial implementation scope

The first Stage 10 runtime slice should be intentionally narrow:

- exactly two caller-supplied candidate execution roles;
- one frozen `RemediationPackage`;
- same invariant evidence contract for both candidates, supplied independently per candidate;
- reuse existing Stage 7 operational handoff and Stage 8 independent reviewer;
- deterministic aggregate result;
- no real concurrency requirement; sequential invocation is acceptable for the first implementation because the experiment is about independent candidates, not throughput;
- no agent-to-agent communication;
- no candidate code merging;
- no autonomous loop.

Prefer a small module such as `parallel_experiment.py` plus focused tests.

## Required focused tests

At minimum cover:

- two valid independent candidates produce `MULTIPLE_VIABLE_CANDIDATES`;
- one valid and one rejected candidate produces `ONE_VIABLE_CANDIDATE`;
- two rejected candidates produce `NO_VIABLE_CANDIDATES`;
- each candidate executes exactly once;
- one candidate's failure does not retry or replace it;
- one candidate's evidence cannot mutate or broaden the other's scope;
- duplicate candidate IDs stop the experiment;
- package mismatch stops the experiment;
- missing/failed gates reject only the affected candidate;
- failed/missing invariant evidence rejects only the affected candidate;
- out-of-scope changes reject only the affected candidate;
- unresolved blocking issues reject only the affected candidate;
- deterministic comparison gives the same result from identical structured evidence;
- ties remain multiple viable candidates for human selection;
- no candidate result can trigger merge, deployment, promotion, or automatic code composition;
- experiment success still requires human review.

## Explicit exclusions

This contract does not authorize:

- open-ended swarms;
- agent group chat;
- recursive delegation;
- dynamic agent creation;
- autonomous target discovery;
- repeated self-improvement cycles;
- automatic candidate synthesis/merging;
- production deployment;
- autonomous pull-request merge;
- self-modification of the orchestration or evaluation policy.

Any future move beyond a fixed bounded candidate experiment requires a separate architecture decision and new evidence gate.

## Promotion boundary

The strongest Stage 10 outcome is evidence that one or more candidates are viable for human review.

Human repository-owner selection, normal CI, and explicit merge/promotion remain mandatory.
