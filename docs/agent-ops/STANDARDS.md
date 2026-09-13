# Coin Analyzer Agent Operating Standards

## Purpose

This file defines project-specific standards that AI agents must apply when
working in the Coin Analyzer repository.

These standards supplement:
- [Root operating contract](../../AGENTS.md)
- [Task contract](CONTRACT.md)
- [Runbook](RUNBOOK.md)

When rules conflict, follow the stricter boundary.

## Sources of Truth

Use evidence according to the question:

- Actual behavior/state: current source, tests, and branch/head evidence.
- Permitted behavior: applicable frozen architecture/contracts and protected
  boundaries. Existing code does not authorize an architecture deviation.
- Authorized scope/actions: the current bounded user task and repository governance.
- Merge readiness: current blocking GitHub CI for the exact PR head plus explicit
  human merge authorization.
- Historical intent: committed decisions before remembered chat context.

Do not override current repository evidence with remembered assumptions.

## Validation Truth

A claimed result must be supported by evidence.

Use evidence according to the claim:

- Relevant CI for the exact commit is authoritative for merge/required-gate status.
- Actual focused test, static-analysis, and validation output support only the
  behavior or properties checked.

Investigate relevant failure evidence regardless of passing CI; passing CI does
not override a relevant focused failure. Apply the root validation stop condition.
A command that was prepared but not run is not validation evidence.

## Scope Standard

Every implementation uses the six fields in
[CONTRACT.md](CONTRACT.md#bounded-task-contract); do not maintain a second format.

Do not silently expand scope.

## Local-First Standard

Coin Analyzer is local-first.

Do not introduce:
- mandatory cloud services;
- remote state required for normal operation;
- silent upload of coin data, images, or user records;
- hidden external dependencies.

Optional network or AI features must remain optional unless a reviewed product
decision explicitly changes that boundary.

## Collection Mutation Standard

Acquisition, discovery, import, OCR, analysis, retrieval, and recommendation
work must not mutate a user's collection merely as a side effect.

Collection changes require an explicit product workflow and explicit intent.

## Identity and Evidence Standard

Do not manufacture identifiers, provenance, confidence, evidence, or
relationships that the source data does not contain.

If a required value is absent, fail closed or report it as unavailable.

## Git Standard

- Never implement directly on `main`.
- Use a dedicated branch.
- Keep unrelated files out of the change.
- Do not use broad staging when unrelated untracked files are present.
- Prefer reviewable commits and pull requests.
- GitHub CI remains authoritative for merge gates.

## Unexpected Conditions

If authentication, permissions, environment state, repository state, or
runtime behavior differs materially from expectations:

stop and surface the condition.

Do not improvise around security, governance, or trust boundaries.

## Precedence Rules

When multiple tools can answer the same question:

- repository navigation: prefer repository-aware tools over broad filesystem
  guessing;
- exact current code behavior: prefer source and tests over documentation;
- merge readiness: prefer GitHub status and CI over local assumptions;
- historical intent: prefer committed design/decision documents over chat memory;
- current public facts: use current external evidence rather than stale memory.

## Scar-Tissue Rules

When a meaningful failure or near-miss occurs, add a concise rule here only if:
- the failure could plausibly recur;
- the rule protects an important boundary;
- the rule is specific enough to be enforced.

Record the date and incident so the rule can later be reevaluated.

Example format:

`YYYY-MM-DD - Incident: <what happened>. Rule: <new durable guardrail>.`

## Change Control

Update these standards through normal repository review.

Do not rewrite standards merely to make an agent's preferred behavior acceptable.
