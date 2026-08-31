# Coin Analyzer — Unit Implementation Prompt

```text
MODE: IMPLEMENT

Read first:
- AI_PROJECT_CONTEXT.md
- CURRENT_STATE.md
- ROADMAP.md
- DECISIONS.md

Repository:
C:\Users\adamo\OneDrive\Documentos\Projects\coin-analyzer

EXPECTED BRANCH:
[INSERT]

EXPECTED HEAD:
[INSERT]

UNIT:
[INSERT UNIT NAME]

OBJECTIVE:
[ONE SENTENCE]

ACCEPTANCE CRITERIA:
1.
2.
3.
4.

ALLOWED FILES:
[LIST OR "determine minimum required set"]

NON-GOALS:
- unrelated refactoring
- architecture redesign
- new dependencies unless required
- weakening tests
- modification of authored ground truth
- speculative future features
- cosmetic work unrelated to acceptance

PROJECT INVARIANTS:
Follow AI_PROJECT_CONTEXT.md and DECISIONS.md.

PROCESS

Before editing:
1. Verify repository, branch, and HEAD.
2. Stop if branch or HEAD differs.
3. Read only the files required to understand this unit.
4. Output a concise UNDERSTANDING section:
   - objective
   - relevant invariants
   - likely files
   - highest-risk failure modes
   - tests required

Implementation:
5. Prefer the smallest correct patch.
6. Add regression tests derived from acceptance criteria.
7. Do not alter expected behaviour merely to make tests pass.
8. Do not broaden scope.

Validation:
9. Run focused tests.
10. Run relevant regression/full suite.
11. Run git diff --check.
12. Run git status --short.
13. Run git diff --stat.

FINAL REPORT

STATUS:
COMPLETE / BLOCKED / PARTIAL

CHANGES:
- ...

VALIDATION:
- tests collected:
- tests passed:
- tests failed:
- skipped:
- warnings:
- exit code:

CLAIMS

VERIFIED:
- ...

INFERRED:
- ...

UNVERIFIED:
- ...

RISKS:
- ...

SCOPE DEVIATIONS:
- none / explain

DO NOT COMMIT unless explicitly instructed.
```
