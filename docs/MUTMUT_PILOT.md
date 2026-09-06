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

## Authority boundary

Mutmut may reveal weak tests. It does not select remediation targets autonomously, modify production code, approve candidates, retry agents, merge, deploy, release, or promote changes.
