# Agent Engineering Runbook

## Standard bounded change

1. Start from current `main`.
2. Create a dedicated branch.
3. Define one primary objective.
4. Record invariants and acceptance criteria.
5. Inspect the relevant code before editing.
6. Make only changes required by the bounded objective.
7. Add or update focused tests.
8. Run focused validation.
9. Report exactly what passed and what was not run.
10. Push the branch and open a pull request.
11. Treat GitHub CI as authoritative.
12. Merge only when repository governance permits it.

## Scope expansion

If the work requires a materially broader change than the declared objective,
stop and surface the expansion before continuing.

## Evidence

A task is not complete because an agent says it is complete.

Completion requires durable evidence such as:

- test output;
- commit;
- pull request;
- CI result;
- artifact;
- release record.
