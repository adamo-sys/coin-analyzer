## Summary

Describe the bounded change and why it is needed.

## Scope

- In scope:
- Explicitly out of scope:
- Production behavior changed: yes / no

## Validation

- [ ] Focused tests/checks were run for the changed area.
- [ ] Full GitHub Actions regression is green before merge.
- [ ] Windows and Ubuntu behavior is unchanged unless this PR explicitly says otherwise.
- [ ] Ruff syntax gate is green.
- [ ] Gitleaks is green.

CI status: pending / running / passed / failed (link the run; distinguish advisory findings).

## Risk / boundaries

Describe the concrete risks, or state none identified.

- [ ] No secrets, private corpus material, or unauthorized evidence were added.
- [ ] Privacy, provenance, licensing, and evidence boundaries remain intact.
- [ ] Existing acceptance-set identity/abstention semantics were not broadened unintentionally.
- [ ] Collection mutation and collector-decision authority are unchanged unless explicitly authorized above.
- [ ] Existing lint/type debt was not converted into an unrelated blocker.
- [ ] Any deferred debt or follow-up work is listed below.

## Changed files

List the important files and the reason each changed.

## Stop conditions

Record any independent review against the exact head SHA. Claim an OpenCode
review only after an actual returned result. If the head changes, review evidence
must be refreshed. Whole-repository Pyright remains advisory; only the explicitly
cleaned bounded type check is required unless this PR deliberately changes policy.

None encountered, or list the violation, resolution, and any unresolved blocker.
Do not mark unresolved blocking validation or authority violations ready for merge.

## Follow-up / deferred work

None, or list the bounded follow-up items.
