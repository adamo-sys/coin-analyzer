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

### Phase A evidence

Owner-provided results:

- Serena version: **1.7.0**.
- Semantic symbol/reference discovery confirmed that custom `default_branch`
  is already honored; no production defect was found.
- Completed one authorized test-only semantic edit in `test_command_center.py`.
  No production edits were made.
- Serena diagnostics: clean.
- External focused validation: `RepositoryStatusTests` **5/5 passed**.
- Windows shell-helper and headless approval/session friction required
  interactive Codex.
- Provisional decision: **OPTIONAL**, positive.
- Exact configuration, elapsed time, and tool/model cost were not supplied.

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

### Phase B evidence

Owner-provided results:

- Superpowers version: **6.3.0**.
- Model/configuration: **gpt-5.6-terra**, medium reasoning effort.
- Phase B: complete.
- A bounded independent static review was separated from fresh verification.
- Static review: **PASS WITH NOTES**; no Critical, Important, or Minor findings.
- Fresh focused validation: `RepositoryStatusTests` **5/5 passed**.
- Verification-before-completion was satisfied for the focused class. Historical
  Phase A test evidence was not treated as current verification.
- No broader suite, CI, or PR validation was performed.
- No production-code or configuration changes occurred.
- Plugin installation/marketplace verification and multiple gated
  inspection/review/verification steps added operational ceremony, but provided
  useful verification discipline.
- Timing and token/cost: not measured.
- Provisional decision: **OPTIONAL**, positive.

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

Completed after Serena and Superpowers each showed individual value. The trial reused the bounded repository-status test family without broadening scope. Repository instructions, tests, CI, and human authority remained authoritative.

### Completed combined evidence

- **Task:** added `test_dirty_custom_default_branch_is_stopped` for a dirty `develop` branch when `develop` is the custom `default_branch`, locking STOPPED precedence over DIRTY.
- **Serena contribution:** semantic inspection located the insertion point and confirmed the precedence contract in `project_repository_status()`; Serena also performed the focused test edit. No diagnostics were reported for the affected test file.
- **Superpowers contribution:** bounded workflow, independent read-only review, and evidence-first verification. The reviewer returned **PASS** with no findings.
- **Fresh focused validation:** `python -m unittest test_command_center.RepositoryStatusTests` completed successfully: **6/6 PASS**.
- **Boundaries and interventions:** no production changes, configuration changes, or corrective interventions. A RED-stage run was not performed because the regression locks already-correct production behavior; the fresh focused passing result is retained as validation evidence.
- **Combined value and final pilot recommendation:** **OPTIONAL — positive.** The combined tools added useful bounded signal, but their added ceremony does not justify mandatory routine adoption.

## Scorecard

| Tool | Completion | Useful signal | Defects/scope violations | Unnecessary churn | Human interventions | Time | Cost | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline Codex/OpenCode | TBD | TBD | TBD | TBD | TBD | TBD | TBD | baseline |
| Serena | Phase A complete | Semantic symbol/reference discovery; one test-only semantic edit | No production defect found; no production edits | Windows shell-helper and headless approval/session friction | Interactive Codex required | Not measured | Not measured | OPTIONAL — provisional, positive |
| Superpowers | Phase B complete | Bounded independent review and fresh verification discipline | No Critical, Important, or Minor findings; no production-code or configuration changes | Plugin installation/marketplace verification and gated inspection/review/verification steps | Not measured | Not measured | Not measured | OPTIONAL — provisional, positive |
| Combined | Complete | Dirty custom-default STOPPED-precedence regression; Serena semantic inspection/edit; Superpowers independent review and fresh verification | No production changes; no diagnostics; no interventions | Added process ceremony, but useful bounded signal | None | Not measured | Not measured | OPTIONAL — final, positive |

## Decision rules

- **ADOPT:** repeatable measurable value with acceptable intervention burden and no boundary conflict.
- **OPTIONAL:** useful bounded value, but not strong enough to make routine.
- **REJECT:** no useful signal, material boundary conflict, or disproportionate burden.
- **DEFER:** promising but evidence incomplete; identify the smallest next validation step.

## Evidence boundary

A successful pilot demonstrates the tool's behavior on this task only. It does not establish repository-wide security, reliability, productivity, or model-quality claims. Security concerns discovered during the pilot must follow the repository's evidence standard and be labeled `needs_validation` until retained evidence establishes the relevant behavior.

## Current status

- Scaffold branch: `tooling/serena-superpowers-pilot`
- Pilot task: Serena Phase A complete; external `RepositoryStatusTests` 5/5 passed
- Serena: 1.7.0; provisional OPTIONAL, positive
- Superpowers: 6.3.0 on gpt-5.6-terra (medium); Phase B complete; fresh `RepositoryStatusTests` 5/5 passed; provisional OPTIONAL, positive
- Combined trial: complete; dirty custom-default STOPPED-precedence regression added; Serena semantic inspection/edit and Superpowers independent review completed; no diagnostics, production changes, or interventions; fresh `RepositoryStatusTests` 6/6 PASS; final OPTIONAL, positive
- Merge authority: human
