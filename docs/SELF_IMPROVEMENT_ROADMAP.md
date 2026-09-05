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

Establish the guarded evidence loop and a deterministic, read-only evaluator over collector-confirmed observations.

Required properties:
- immutable/append-oriented evidence flow
- evaluator independence from authoritative collection mutation
- deterministic summaries and agreement metrics
- focused synthetic tests
- architectural guardrail tests
- human promotion boundary documented in ADR-011

Completion reference: PR #90.

### 2. Phone Drop Import v1 — NEXT

Deliver the highest-value collector workflow slice before adding more autonomous behavior.

Scope:
- add a desktop action such as `Import Phone Photos…`
- select two or more phone-transferred images
- **copy, never move**, source images into a Coin Analyzer-owned incoming area
- use deterministic/collision-safe filenames
- trigger or offer a Photo Inbox refresh
- preserve existing Photo Inbox review, `Create New`, and `Attach to Existing` workflows
- support formats already handled by Photo Inbox
- provide an explicit useful message for unsupported HEIC/HEIF

Explicit exclusions:
- no networking
- no native iOS/Android app
- no server
- no account system
- no automatic cloud sync
- no background watcher
- no automatic collection mutation

Acceptance criteria:
- originals remain untouched
- re-import cannot silently overwrite
- imported front/back images become a reviewable Photo Set
- unsupported formats fail clearly
- focused import tests pass
- existing Photo Inbox/navigation tests pass
- full regression and blocking quality gates remain green

### 3. Evaluator v2 — Failure Clustering and Reporting

Extend the evaluator from aggregate scoring into useful diagnostic evidence.

Target capabilities:
- cluster recurring failure modes
- summarize high-frequency mismatches by field/category/engine/method
- produce deterministic bounded reports
- distinguish development, validation, and frozen golden evaluation evidence where appropriate

Still prohibited:
- automatic remediation
- automatic retraining
- automatic prompt/config mutation
- deployment authority

### 4. Diagnostic Agent

Introduce the first agent role.

Responsibilities:
- inspect evaluator evidence and failures
- identify likely causes
- gather relevant repository context
- produce bounded diagnostic reports and remediation proposals

The Diagnostic Agent may investigate and recommend. It may not mutate production code, collection data, prompts, models, or configuration on its own.

### 5. Dependency Vulnerability Audit

Use the existing reproducible lockfiles as a stable scan boundary.

Scope:
- audit `requirements.lock`, `requirements-dev.lock`, and `requirements-ai.lock`
- identify actionable vulnerabilities
- separate direct/transitive risk
- document remediation paths and compatibility risk
- keep changes bounded and independently reviewable

### 6. Graphify Sandbox Experiment

Evaluate Graphify or an equivalent graph-oriented code-analysis approach in a disposable sandbox.

Keep it only if it produces actionable signal beyond the existing Ruff/Pyright/CodeQL/tests/dependency tooling. Do not add permanent complexity merely because the tool is novel.

### 7. Codex Improvement Agent

Connect Codex as the bounded implementation role.

Responsibilities:
- receive a specific remediation package from the diagnostic/evaluation layer
- implement within explicit scope and invariants
- run focused tests and required validation
- report changed files, tests, risks, and unresolved issues
- stop when a required gate fails

Still prohibited:
- autonomous merge
- silent scope expansion
- bypassing evaluator/reviewer evidence

### 8. Independent Reviewer Agent

Add an independent review layer, preferably with meaningfully separate context and, where practical, a distinct model or review path.

Responsibilities:
- review candidate changes independently of the implementation agent
- verify architectural invariants
- challenge tests and failure assumptions
- flag regressions, unsafe promotion, or unsupported conclusions

Reviewer approval is evidence, not merge authority.

### 9. Orchestrator

Only after the evaluator, Diagnostic Agent, Improvement Agent, and Reviewer Agent have demonstrated reliable bounded behavior, add orchestration.

Responsibilities:
- sequence work packages
- pass structured evidence between roles
- enforce stop conditions
- preserve traceability
- surface unresolved conflicts to the repository owner

Prefer structured artifacts and explicit state transitions over free-form agent conversation.

### 10. Parallel Swarm Experiments

Experiment with multiple agents only after the sequential pipeline is trustworthy.

Potential uses:
- parallel diagnosis hypotheses
- competing bounded implementation candidates
- independent review paths
- specialized agents for OCR, UI, persistence, security, or market intelligence

Rules:
- agents communicate through structured evidence/results rather than unbounded group-chat behavior
- parallel candidates are evaluated against the same gates
- no agent gains merge authority
- human repository-owner approval remains the final promotion boundary

## Operating principle

The roadmap is deliberately conservative about autonomy and aggressive about evidence. Coin Analyzer should become more capable at diagnosing and improving itself only as fast as its measurement, review, and rollback discipline can support.
