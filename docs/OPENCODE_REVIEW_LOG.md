# OpenCode Review Log

Purpose: record completed and incomplete OpenCode reviewer-pilot evidence without treating setup or prepared prompts as successful reviews.

## Evidence rules

- A completed review requires an actual successful OpenCode execution and a returned review result for the recorded exact base/head pair.
- Prepared prompts, quota/provider failures, setup attempts, or reviews of a different head are not completed review evidence.
- GitHub Actions and repository governance remain authoritative; OpenCode is advisory only.
- Whole-repository Pyright remains advisory unless a pull request intentionally ratchets a cleaned bounded module into the blocking boundary.

## Recorded runs and attempts

### Historical controlled benchmark — PR #60

- Status: completed successfully.
- Base: `87c0097e1fbca2260957081a93d2eb96b3107888`.
- Head: `90073eaf765ea9d69e34532ed05bd4811f2c291c`.
- Model/provider: Qwen3-Coder-Next through OpenCode.
- Result: merge recommendation with one useful non-blocking type-precision observation and one low-value workflow-label nit; no fabricated blocker.
- Authority: advisory evidence only; CI remained authoritative.

### PR #149 — bounded domain relationship selector

- Status: review package prepared, but no successful OpenCode execution was recorded before merge.
- Base: `4eeb2382ae504e721e8d3a841a30900077e97bd4`.
- Head: `20f08d306292164a38498870e212c43cacfbc498`.
- Changed files: `domain_relationship_query.py`, `test_domain_relationship_query.py`.
- Prepared review scope: correctness defects, regressions, scope violations, unsafe assumptions, missing tests, and governance-boundary violations; distinguish blockers from non-blocking observations and cite supplied evidence.
- Prepared acceptance criteria: actual successful execution; exact recorded base/head; no invented CI/test/runtime claims; traceable findings; blockers separated from optional improvements; no recommendation to weaken repository boundaries; internally consistent final verdict.
- Evidence available at preparation time: Tests, Quality Advisory, and CodeQL Advisory were green for the recorded PR head.
- Outcome: PR #149 later merged into `main` as merge commit `1e5a877cf5fa08b9359b233dea33865aef533c71` without a recorded successful OpenCode run. Do not assign or infer an OpenCode verdict for this PR.

### PR #153 — OpenCode reviewer evidence log

- Status: completed successfully.
- Base: `1e5a877cf5fa08b9359b233dea33865aef533c71`.
- Head: `67883b5754526e4c5e8f24bdca8650fb71f8ecea`.
- Changed files: `docs/OPENCODE_REVIEW_LOG.md` only.
- Model/provider: `opencode/nemotron-3.5-lightning-free` through OpenCode.
- Execution environment: local Windows PowerShell 5.1 checkout after fetching the exact base/head objects.
- Review result: no blockers; the reviewer reported the documentation factually accurate and consistent with OpenCode-advisory/GitHub-Actions-authoritative governance, with whole-repository Pyright remaining advisory.
- Reviewer checks reported pass for factual accuracy, no fabricated OpenCode execution claim, advisory authority wording, Pyright policy preservation, scope discipline, and documentation clarity.
- Authoritative CI for the reviewed head: Tests, Quality Advisory, and CodeQL Advisory completed successfully; the required Ruff, Gitleaks, Ubuntu, Windows, and bounded `pyright-event-bus` jobs were green.
- Scope note: this records the actual returned OpenCode verdict for the exact reviewed head; it does not generalize model quality beyond this bounded documentation review.

### PR #160 — PowerShell execution guidance

- Status: completed successfully.
- Base: `6feb29a9e27265d1a6fbcc1a331aef1e52a0fc21`.
- Head: `d39d6d670395bb0333a0c963ff6051e6d846af87`.
- Changed files: `docs/OPENCODE_REVIEW_PROTOCOL.md` only.
- Model/provider: `opencode/nemotron-3.5-lightning-free` through OpenCode.
- Execution environment: local Windows PowerShell 5.1 from the repository root after fetching and verifying the exact base/head objects.
- Review result: `MERGE WITH NONBLOCKING FINDINGS`; the reviewer reported zero blockers and found the PowerShell guidance consistent with the existing advisory-authority model, exact-head evidence discipline, whole-repository Pyright advisory policy, and merge guardrails.
- Reviewer checks reported pass for factual consistency, PowerShell 5.1 execution guidance, exact-head discipline, Pyright policy preservation, no authority broadening, and documentation clarity.
- Authoritative CI for the reviewed head: Tests, Quality Advisory, and CodeQL Advisory completed successfully.
- Scope note: this records the actual returned OpenCode verdict for the exact reviewed head only and does not generalize model quality beyond this bounded documentation review.

### PR #166 — repeated-review evidence synthesis

- Status: completed successfully.
- Base: `fb67112777de02e49a49990b2f74d04ec849a2a2`.
- Head: `dc8a31588edf19535b21b4bbce15073957be8858`.
- Changed files: `docs/OPENCODE_REVIEW_LOG.md` only.
- Model/provider: `opencode/nemotron-3.5-lightning-free` through OpenCode.
- Execution environment: local Windows PowerShell 5.1 from the repository root after fetching and verifying the exact base/head objects.
- Review result: `MERGE`; no blockers.
- Reviewer confirmed the historical PR #60/Qwen benchmark remained distinct from the later PR #153/#160 Nemotron runs, OpenCode remained advisory, whole-repository Pyright remained advisory, and the documentation did not overclaim production-review reliability.
- Authoritative CI on the unchanged reviewed head: Tests, Quality Advisory, and CodeQL Advisory completed successfully; Ruff, Gitleaks, Ubuntu, Windows, and bounded `pyright-event-bus` were green.
- Scope note: this is advisory evidence for the exact reviewed documentation head only.

### PR #168 — current bounded Pyright documentation refresh

- Status: completed successfully on the corrected exact head.
- Base: `7a04e7e910ecc2f90d7131f37e692975449062d1`.
- Head: `55200cdaf4a7e057b034a9ec368774496f81ec06`.
- Changed files: `docs/AI_TOOL_EVALUATION.md` only.
- Model/provider: `opencode/nemotron-3.5-lightning-free` through OpenCode.
- Execution environment: local Windows PowerShell 5.1 from the repository root.
- Review result: `MERGE WITH NONBLOCKING FINDINGS`; no blocking findings.
- Reviewer verified the documented 10-module bounded Pyright list against `.github/workflows/tests.yml`, preserved whole-repository Pyright as advisory and Pyright 1.1.411 advisory pinning, found no weakened CI/testing/security/privacy/provenance/benchmark/architecture guardrail, and confirmed no unrelated Markdown/table/content change remained.
- A prior review of head `94ebad3b8b64bc976e055efacfb7ba8230582d1f` became stale after a GitHub-side correction restored an unrelated Markdown table separator; that prior verdict is not merge evidence for the corrected head.
- During the stale-head attempt, OpenCode attempted a local merge despite read-only instructions and then reset it; no push or remote mutation was observed. Record this as execution-protocol friction, not reviewer authority.
- Scope note: this records only the actual returned verdict for the corrected exact head; GitHub Actions and repository governance remained authoritative.

## Repetition status

Four later successful documentation-only reviews (#153, #160, #166, and #168) now supplement the historical PR #60 benchmark. They strengthen evidence that exact-head packaging and the Windows PowerShell 5.1 execution path are repeatable, while still not establishing production-code reviewer reliability and not justifying OpenCode as an authoritative merge gate.

Observed setup and execution friction remains part of the evidence: start from the repository root, fetch and verify the recorded base/head objects, avoid Bash-only `&&` and Unix-only helpers under Windows PowerShell 5.1, treat provider/shell/setup failures as unsuccessful attempts rather than verdicts, and explicitly prohibit repository-mutating Git commands during read-only reviews.

## Next pilot rule

The next OpenCode pilot must use a new open bounded PR with a stable exact head. Record the base SHA, head SHA, changed-file list, unified diff, declared invariants, focused validation, authoritative CI state, and relevant guardrails before execution. If the head changes, the prepared package is stale and must be regenerated.
