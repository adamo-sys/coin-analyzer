# Mutmut Pilot

## Purpose

Use mutation testing as advisory evidence about whether critical safety tests detect small behavioral regressions. This pilot does not change runtime behavior, CI authority, or promotion authority.

## Initial scope

The first target is deliberately narrow:

- source: `reviewer_agent.py`
- tests: `test_reviewer_agent.py`
- supporting modules copied into the mutation sandbox: `improvement_agent.py`, `diagnostic_agent.py`

The reviewer is a high-value target because it enforces fail-closed scope, gate, invariant, unresolved-issue, and promotion boundaries.

## Tool version

Pilot against `mutmut==3.7.0`.

## Environment

Run under Linux/WSL rather than making mutation testing part of the blocking Windows CI matrix during the pilot.

Example setup:

```text
python -m pip install mutmut==3.7.0
python -m pytest test_reviewer_agent.py -q
mutmut run
mutmut results
```

Inspect survivors individually with `mutmut show <id>`.

## Configuration

`pyproject.toml` uses current mutmut 3.7 configuration names:

- `source_paths` limits mutation to `reviewer_agent.py`;
- `pytest_add_cli_args_test_selection` limits per-mutant test selection to `test_reviewer_agent.py`;
- `also_copy` supplies the small import boundary needed by the reviewer tests;
- `mutate_only_covered_lines = true` avoids spending time on lines the selected tests never execute.

## Evidence to record

For the pilot, record:

1. total generated mutants;
2. killed mutants;
3. surviving mutants;
4. suspicious/time-out mutants;
5. runtime;
6. any survivor representing a real safety-test gap;
7. tests added to kill meaningful survivors.

Do not optimize for a vanity mutation percentage. Equivalent or irrelevant mutants may be documented rather than forcing artificial tests.

## Exit gate

T6 can move to COMPLETE / PILOT ACTIVE when:

- the focused clean test suite passes first;
- mutmut can complete or resume predictably under WSL/Linux;
- meaningful survivors can be inspected reproducibly;
- at least one critical boundary is shown to have useful mutation signal, or the pilot is explicitly rejected as low-value;
- mutation testing remains advisory and non-blocking.

Only after this exit gate should additional modules such as `operational_handoff.py`, `orchestrator.py`, `parallel_experiment.py`, or `specialized_parallel_experiment.py` be added, one bounded target at a time.

## Pilot completion evidence

T6 reached **COMPLETE / PILOT ACTIVE** after bounded reviewer mutation testing demonstrated useful safety-test signal.

Evidence sequence:

- the advisory workflow completed successfully against `reviewer_agent.py`;
- the first successful run generated 135 mutants, with 120 killed and 15 surviving;
- focused hardening reduced the survivor set and made exact survivor inspection reproducible;
- two remaining mutations exposed a genuine gap around Windows drive-relative repository paths;
- PR #128 added the focused regression case `C:drive-relative\path.py`;
- final advisory run `34006677115` removed both meaningful path-normalization survivors;
- six survivors remain in `review_candidate`, classified as equivalent or low-value diagnostic/control-flow mutations.

Those residual survivors are intentionally documented rather than chased for a vanity mutation score.

The exit gate is satisfied:
- the focused reviewer suite passes;
- mutation execution is reproducible;
- survivor diffs are inspectable;
- useful safety-boundary signal was demonstrated;
- mutmut remains advisory and non-blocking.

## Authority boundary

Mutmut may reveal weak tests. It does not select remediation targets autonomously, modify production code, approve candidates, retry agents, merge, deploy, release, or promote changes.

## Evidence report states

The capture helper targets **mutmut 3.7.0** only. Its results parser accepts blank
output or the version's `<mutant>: <status>` lines; unknown lines/statuses fail
closed as UNAVAILABLE. Survivor details must have the version's
`# <mutant>: survived` header. Revisit these assumptions explicitly before a
tool upgrade.

| State | Meaning |
| --- | --- |
| COMPLETE | Primary results retrieval succeeded and was recognized, with successful mutation execution and all requested survivor details available. |
| INCOMPLETE | Primary results are available, but mutation execution was unsuccessful/unknown or a survivor detail was unavailable/unrecognized. |
| UNAVAILABLE | Primary results could not be retrieved or recognized; overrides other states. |

Only COMPLETE may report a survivor count, including `No survivor entries reported`
for successful empty results. This is evidence-capture status, not a mutation
score: mutmut normally omits killed mutants, and other statuses remain in the
raw output. Missing or partial evidence never becomes a claim of zero survivors.

The workflow retains mutation-run output in the Actions log and passes its
outcome and actual exit code to the helper. A skipped/cancelled run can have no
exit code; it is not considered successful. The helper never executes mutations.

Artifacts retain `mutmut-results.txt` and `mutmut-survivor-diffs.txt`, now with
explicit states, command arguments, stdout, stderr, and exit codes.
`mutmut-report.json` contains the structured report. A command that cannot start
has a null exit code and an explicit launch error. Failed survivor details name
the mutant and preserve other details. INCOMPLETE and UNAVAILABLE return exit
code 1; COMPLETE returns 0. Artifact upload remains `if: always()`, and the
workflow remains advisory.

Focused verification (mocked subprocesses and temporary directories; no mutmut
installation or real mutation tests required):

```text
python -m unittest tests.test_mutmut_evidence_capture
```

A manual Ubuntu advisory run remains the integration check for real artifacts.
This repair is CI cleanup; T9 coverage.py + diff-cover remains the next experiment.
