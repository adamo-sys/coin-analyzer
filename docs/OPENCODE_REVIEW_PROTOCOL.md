# OpenCode Independent Review Protocol

Purpose: define the exact bounded evidence package for optional OpenCode read-only reviews without making OpenCode an authoritative merge gate.

## Authority

GitHub Actions and repository governance remain authoritative. OpenCode review is advisory only. A review result cannot override failing blocking CI, privacy/provenance restrictions, security rules, benchmark boundaries, architecture governance, or the human merge/release authority defined elsewhere in the repository.

Never record an OpenCode review as completed unless an actual successful OpenCode execution produced a review result. Setup attempts, quota failures, provider failures, partial prompts, and copied expectations are not completed reviews.

## Eligible review scope

Use this protocol only for a bounded pull request with:

- a stable base SHA and head SHA;
- a small, inspectable diff;
- explicit scope and invariants in the PR description;
- available focused-test or CI evidence;
- no unresolved provenance or authorization question requiring evidence outside the repository;
- no request for the reviewer to modify files, push commits, merge, or change repository settings.

Prefer CI, documentation, typing, deterministic test, and clearly behavior-neutral changes while the pilot remains provisional. Production-behavior changes may be reviewed only when their architecture contract and acceptance criteria are already explicit.

## Exact evidence package

Before invoking OpenCode, record or provide all of the following:

1. Repository: `adamo-sys/coin-analyzer`.
2. PR number and title.
3. Base SHA.
4. Head SHA.
5. Exact changed-file list and unified diff/patch for that head.
6. PR scope statement and declared invariants.
7. Focused validation already performed, including command names and outcomes when available.
8. Authoritative GitHub Actions state for the same head SHA.
9. Relevant repository guardrails: no test weakening, no privacy/provenance weakening, no security weakening, no benchmark inflation, no architecture-governance bypass, and no unrelated broad refactor.
10. Known limitations or intentionally advisory evidence, such as whole-repository Pyright debt.

If any item materially changes after the review, the review no longer covers the current head and must not be treated as an exact-head review.

## Reviewer instructions

Ask OpenCode to perform a read-only independent review of the supplied exact diff. Require it to:

- identify correctness defects, regressions, scope violations, unsafe assumptions, missing tests, and governance-boundary violations;
- distinguish blocking findings from non-blocking observations;
- cite the relevant changed file/hunk or supplied evidence for each finding;
- avoid inventing test results, CI results, runtime behavior, repository state, or external evidence;
- avoid suggesting broad cleanup unrelated to the PR;
- treat whole-repository Pyright as advisory unless the PR intentionally changes that policy;
- state when a concern cannot be verified from the supplied evidence;
- finish with one of: `MERGE`, `MERGE WITH NONBLOCKING FINDINGS`, or `BLOCK`, with a concise rationale.

## Acceptance criteria for a useful pilot review

A completed OpenCode review is acceptable pilot evidence when:

- the execution actually completed successfully;
- it reviewed the recorded base/head pair;
- it did not claim tests or CI passed unless those results were supplied;
- findings are traceable to the diff or evidence package;
- it separates blockers from optional improvements;
- it does not recommend weakening tests or repository boundaries;
- its final recommendation is internally consistent with its findings;
- useful findings, false positives, intervention friction, and model/provider used are recorded afterward.

A review is not acceptable evidence when it fabricates repository state, treats advisory signals as authoritative, materially reviews a different head, or requires unsafe/broad changes to reach a verdict.

## Post-review record

For each successful run, record:

- date;
- PR number;
- base SHA and reviewed head SHA;
- OpenCode version if readily available;
- model/provider;
- final recommendation;
- blocking findings count;
- useful non-blocking findings count;
- false-positive or low-value findings count;
- human intervention/setup friction;
- whether subsequent CI or human review confirmed or contradicted any finding.

For an unsuccessful attempt, record only the attempt and failure mode if it is useful operational evidence. Do not assign a review verdict.

## Merge discipline

OpenCode success is never sufficient by itself. Merge only when:

- the reviewed head SHA is still the PR head;
- all authoritative blocking checks are green for that head;
- scope remains bounded;
- no unresolved review blocker remains;
- any required human approval has been obtained;
- the merge operation uses expected-head-SHA protection where available.

This protocol advances the reviewer pilot without making OpenCode mandatory or changing the existing CI authority model.
