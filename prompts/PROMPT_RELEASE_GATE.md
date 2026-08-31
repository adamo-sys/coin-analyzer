# Coin Analyzer — Release Gate Prompt

```text
MODE: RELEASE GATE

Do not modify code.

Read:
- AI_PROJECT_CONTEXT.md
- CURRENT_STATE.md
- AI_ROADMAP.md
- DECISIONS.md

Determine whether the current unit can legitimately be declared complete.

Check:
1. acceptance criteria
2. project invariants
3. focused tests
4. relevant regression tests
5. git diff --check
6. unexpected changed files
7. TODO/FIXME placeholders
8. new dependency changes
9. persisted-format compatibility
10. evaluation-integrity risks

Classify every completion claim:

VERIFIED
INFERRED
UNVERIFIED

Return:

GATE:
PASS / FAIL

BLOCKERS:
- ...

NON-BLOCKING RISKS:
- ...

SAFE TO COMMIT:
YES / NO

PROPOSED COMMIT MESSAGE:
...
```
