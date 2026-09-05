# Coin Analyzer Self-Improvement Roadmap

## Purpose

This roadmap defines the dependency order for Coin Analyzer's guarded self-improvement work. It is intentionally sequence-driven rather than date-driven: major stages advance only after the prior stage is merged, green, and sufficiently understood.

The goal is to build progressively stronger automation without weakening repository discipline, evaluation independence, or human promotion authority.

## Standing guardrails

1. **Human merge authority remains mandatory.** No agent, evaluator, reviewer, or orchestrator may silently promote changes into `main` or production behavior.
2. **Evidence before adaptation.** Candidate improvements must be measured against explicit evidence and tests before promotion.
3. **No silent collection mutation.** Self-improvement components may analyze confirmed observations and propose changes, but may not silently rewrite authoritative collection data.
4. **No silent model, prompt, or configuration mutation.** Any such change must be explicit, reviewable, testable, and promoted through the normal repository workflow.
5. **Major stages are sequential.** Do not begin the next major stage until the current one is merged and green unless an explicit architectural reason is documented.
6. **Maintenance work may proceed opportunistically.** Bounded Pyright ratchets, CodeQL follow-up, security hardening, dependency hygiene, and property-based tests may occur without changing the main roadmap order.
7. **Prefer bounded vertical slices.** Each implementation package should have explicit scope, invariants, focused tests, regression evidence, changed-file reporting, risks, and stop conditions when gates fail.

## Roadmap

### 1. Self-Improvement Foundation v1 — COMPLETE

Established the guarded evidence loop and deterministic, read-only evaluation over collector-confirmed observations.

Completion reference: PR #90.

### 2. Phone Drop Import v1 — COMPLETE

Delivered the bounded phone-photo import workflow while preserving copy-only source handling and existing review boundaries.

### 3. Evaluator v2 — Failure Clustering and Reporting — COMPLETE

Extended evaluation into deterministic diagnostic evidence suitable for bounded downstream analysis.

### 4. Diagnostic Agent — COMPLETE

Added the bounded diagnostic role. It investigates evaluator evidence and produces structured findings without code, collection, prompt, model, or configuration mutation authority.

### 5. Dependency Vulnerability Audit — COMPLETE

Established the reproducible dependency/audit boundary and documented bounded remediation handling.

### 6. Graphify Sandbox Experiment — COMPLETE

Evaluated graph-oriented analysis as a sandbox experiment without granting it permanent architectural authority merely for novelty.

### 7. Codex Improvement Agent — COMPLETE

The Stage 7 contract and operational handoff are now implemented.

Responsibilities now covered:
- receive a specific frozen remediation package;
- render the bounded implementation task;
- invoke exactly one caller-supplied Codex execution role;
- require a structured `ImprovementResult`;
- validate explicit scope and required gates fail-closed;
- convert execution/malformed-result failures into deterministic STOPPED evidence;
- report changed files, validation, risks, unresolved issues, and stopped gate;
- expose no merge, deploy, promotion, retry-loop, or silent scope-expansion authority.

Completion references: Stage 7 contract work plus PR #104 operational handoff.

### 8. Independent Reviewer Agent — COMPLETE

Added a deterministic independent review boundary over the frozen remediation package, implementation result, and independently supplied invariant evidence.

Responsibilities now covered:
- independently re-check changed-file scope;
- independently verify required gate evidence;
- verify invariant evidence;
- reject malformed, contradictory, missing, stopped, unresolved, or scope-broadening evidence;
- emit PASS/FAIL evidence only;
- expose no repair, merge, deploy, or promotion authority.

Completion reference: PR #103, integrated with the operational handoff in PR #104.

### 9. Orchestrator — NEXT / ARCHITECTURE FROZEN

Coordinate the now-bounded sequential pipeline without introducing autonomous improvement loops or promotion authority.

Canonical flow:

`evaluator evidence -> Diagnostic Agent -> RemediationPackage -> bounded Codex handoff -> ImprovementResult -> Independent Reviewer -> HUMAN`

Responsibilities:
- sequence one explicitly selected work package;
- pass structured evidence between existing roles;
- enforce forward-only state transitions and stop conditions;
- preserve deterministic traceability;
- surface malformed evidence, failures, and unresolved conflicts to the repository owner;
- terminate successful machine-side work at `READY_FOR_HUMAN_REVIEW`.

Still prohibited:
- automatic retry or repair loops;
- autonomous target selection;
- silent scope expansion;
- collection/model/prompt/config mutation authority;
- bypassing reviewer or required gates;
- merge, deploy, release, or promotion authority;
- Stage 10 parallel/swarm behavior.

Architecture authority: `docs/STAGE_9_ORCHESTRATOR_CONTRACT.md`.

### 10. Parallel Swarm Experiments

Experiment with multiple agents only after the sequential pipeline is trustworthy.

Potential uses:
- parallel diagnosis hypotheses;
- competing bounded implementation candidates;
- independent review paths;
- specialized agents for OCR, UI, persistence, security, or market intelligence.

Rules:
- agents communicate through structured evidence/results rather than unbounded group-chat behavior;
- parallel candidates are evaluated against the same gates;
- no agent gains merge authority;
- human repository-owner approval remains the final promotion boundary.

## Operating principle

The roadmap is deliberately conservative about autonomy and aggressive about evidence. Coin Analyzer should become more capable at diagnosing and improving itself only as fast as its measurement, review, and rollback discipline can support.
