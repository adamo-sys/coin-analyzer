# Stage 9 Reliability Gate

## Purpose

Stage 10 parallel-agent experiments must not begin merely because the Stage 9 orchestrator exists. The sequential pipeline should first demonstrate that its deterministic, fail-closed behavior remains stable under repeated and adversarial structured scenarios.

This document defines the bounded entry gate for Stage 10.

## Evidence required

Before Stage 10 architecture is frozen, the repository should have green evidence that Stage 9:

- produces identical run artifacts from identical structured inputs;
- preserves run identity without changing decisions when only the caller-supplied run ID changes;
- invokes the implementation execution role no more than once per run;
- never retries a failed implementation automatically;
- never crosses `READY_FOR_HUMAN_REVIEW` into merge, deploy, release, or promotion authority;
- terminates fail-closed on failed invariant evidence;
- terminates fail-closed on missing or failed required validation;
- rejects out-of-scope changes before `IMPLEMENTATION_COMPLETE`;
- preserves forward-only transition ordering;
- keeps independent runs independent rather than turning them into an autonomous loop.

## Current evidence slice

`test_orchestrator_reliability.py` provides focused deterministic evidence for these properties without changing production/runtime behavior.

## Stage 10 entry condition

Stage 10 may move to architecture-freeze work only after:

1. this reliability evidence is merged;
2. focused tests are green;
3. the full repository regression is green;
4. blocking CI/security/quality checks are green;
5. no unresolved review finding contradicts the frozen Stage 9 authority boundary.

Passing this gate does not grant agents additional authority. It only establishes that the sequential orchestration boundary is sufficiently stable to justify designing bounded parallel experiments.

## Still prohibited

Even after this gate passes, Stage 10 must not introduce:

- autonomous merge or promotion;
- unbounded agent group chat;
- automatic repeated remediation cycles;
- silent scope expansion;
- self-selected production targets without an explicit caller-owned work package;
- collection, model, prompt, or configuration mutation outside explicit reviewable scope.
