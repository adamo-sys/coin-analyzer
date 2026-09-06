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

## Next pilot rule

The next OpenCode pilot must use a new open bounded PR with a stable exact head. Record the base SHA, head SHA, changed-file list, unified diff, declared invariants, focused validation, authoritative CI state, and relevant guardrails before execution. If the head changes, the prepared package is stale and must be regenerated.
