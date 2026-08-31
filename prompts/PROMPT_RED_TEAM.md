# Coin Analyzer — Red Team Prompt

```text
MODE: RED TEAM

Read:
- AI_PROJECT_CONTEXT.md
- CURRENT_STATE.md
- DECISIONS.md

Review the current uncommitted implementation.

Assume it contains defects.

Do not modify code.

Attempt to identify failures involving:
- stable identity
- stale references
- restore/reload
- serialization
- missing files
- corrupt files
- empty collections
- duplicate records
- sparse records
- PARTIAL records
- UNIDENTIFIED records
- banknotes
- ordering/filtering
- deletion/state races
- evaluation-ground-truth contamination
- unsupported assumptions

For every plausible defect report:

SEVERITY:
CRITICAL / HIGH / MEDIUM / LOW

SCENARIO:
Concrete reproduction case.

CAUSE:
Why the implementation may fail.

CURRENT COVERAGE:
Whether an existing test catches it.

RECOMMENDATION:
Smallest appropriate correction.

Do not invent hypothetical concerns without a realistic execution path.

Finish with:

RELEASE RECOMMENDATION:
PASS
PASS WITH MINOR FIXES
FAIL
```
