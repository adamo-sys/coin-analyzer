# Serena + Superpowers Pilot

Tracking document for Issue #137. This is a bounded developer-tool experiment, not a production dependency or framework migration.

## Pilot contract

**Objective:** determine whether Serena and Superpowers improve one real Coin Analyzer development task enough to justify optional adoption.

**Task:** add one focused regression test for `project_repository_status()` covering a non-`main` custom `default_branch`, preserving the existing STOPPED semantics and authorized-action contract. No production-code change is authorized unless the pilot discovers a concrete defect in the existing implementation and the task is explicitly re-scoped.

**Files expected for the implementation trial:**
- `test_command_center.py`
- this pilot document / evaluation log only as needed for evidence

**Explicitly out of scope:** production behavior changes, Command Center redesign, agent orchestration, collection data, private benchmark material, dependency changes, CI changes, unrelated cleanup/refactors, and reopening Phone Drop UX work.

**Acceptance:**
- test expresses the existing contract rather than weakening it;
- focused test passes;
- no unrelated files change;
- no production dependency on Serena or Superpowers is introduced;
- normal CI remains authoritative;
- the tool's contribution is recorded separately from the correctness of the underlying change.

## Baseline: current Codex/OpenCode workflow

Record before tool-assisted implementation:

| Measure | Baseline |
| --- | --- |
| Task | custom `default_branch` repository-status regression test |
| Agent/tool | current Codex/OpenCode workflow |
| Start/end time | TBD |
| Model/API cost | TBD / visible session accounting |
| Tool calls / repository reads | TBD |
| Files inspected | TBD |
| Files changed | TBD |
| Focused checks | TBD |
| Human interventions | TBD |
| Scope violations | 0 expected |
| Final result | TBD |

The baseline is a measurement target, not permission to spend additional provider calls merely to manufacture a comparison. If an existing recent execution contains sufficient retained evidence, reuse it and mark the limitation.

## Serena trial

### Required evidence

- exact Serena version;
- installation/configuration used;
- files/symbols located;
- navigation/editing steps that were materially useful;
- unnecessary reads/edits or wrong-layer navigation;
- impact-surface description before editing;
- human interventions;
- elapsed time and visible tool/model cost where available;
- final diff and focused validation.

### Decision gate

Serena earns `adopt` or `optional` only if it provides measurable signal such as lower exploratory churn, better symbol/impact discovery, less unnecessary editing, or a useful dependency/defect observation. Novelty alone is not signal.

## Superpowers trial

### Required evidence

- exact Superpowers version/configuration;
- plan produced before implementation;
- explicit invariants and stop conditions;
- tests proposed/run;
- verification claims and actual evidence;
- unnecessary ceremony or scope expansion;
- human interventions;
- elapsed time and visible tool/model cost where available;
- final diff and focused validation.

### Decision gate

Superpowers earns `adopt` or `optional` only if its planning/TDD/verification behavior adds measurable signal beyond the existing repository workflow without disproportionate ceremony.

## Combined trial

Run only if Serena and Superpowers each show individual value. Reuse the same bounded task family; do not broaden scope. Serena supplies semantic repository navigation and Superpowers supplies process discipline. Repository instructions, tests, CI, and human authority remain authoritative.

## Scorecard

| Tool | Completion | Useful signal | Defects/scope violations | Unnecessary churn | Human interventions | Time | Cost | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline Codex/OpenCode | TBD | TBD | TBD | TBD | TBD | TBD | TBD | baseline |
| Serena | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| Superpowers | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| Combined | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

## Decision rules

- **ADOPT:** repeatable measurable value with acceptable intervention burden and no boundary conflict.
- **OPTIONAL:** useful bounded value, but not strong enough to make routine.
- **REJECT:** no useful signal, material boundary conflict, or disproportionate burden.
- **DEFER:** promising but evidence incomplete; identify the smallest next validation step.

## Evidence boundary

A successful pilot demonstrates the tool's behavior on this task only. It does not establish repository-wide security, reliability, productivity, or model-quality claims. Security concerns discovered during the pilot must follow the repository's evidence standard and be labeled `needs_validation` until retained evidence establishes the relevant behavior.

## Current status

- Scaffold branch: `tooling/serena-superpowers-pilot`
- Pilot task: selected; execution pending local Terminus setup
- Serena: not yet installed/measured
- Superpowers: not yet installed/measured
- Combined trial: deferred until individual trials pass
- Merge authority: human
