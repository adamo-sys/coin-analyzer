## Scope

Describe the bounded change and why it belongs in this pull request.

## Changed files

List the files intentionally changed. Call out any generated or dependency files separately.

## Validation

Record the exact checks/tests run and their results. Distinguish authoritative blocking CI from advisory evidence.

## Risk and invariants

- [ ] Scope is bounded; no unrelated cleanup or refactor is included.
- [ ] Tests and required CI/security gates are not weakened.
- [ ] Privacy, provenance, and no-secret/no-private-corpus boundaries are preserved.
- [ ] Benchmark/evaluation claims remain tied to the exact measured scope.
- [ ] Architecture/collection-authority boundaries are unchanged unless an approved architecture path explicitly authorizes the change.
- [ ] Whole-repo Pyright remains advisory unless this PR intentionally and explicitly ratchets a demonstrated-clean bounded slice.

## Review evidence

Record reviewer evidence against the exact head SHA. Do not claim an AI/OpenCode review unless an actual completed execution produced that evidence.

Reviewed head SHA: `TODO`

## Stop conditions

Stop and reassess rather than merge if the reviewed head moves, an authoritative blocking check is not green, an unresolved review blocker remains, or the change would weaken the invariants above.
