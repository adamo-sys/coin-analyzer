# AI Tool Evaluation Log

Purpose: evaluate developer tooling empirically before adopting it into the normal Coin Analyzer workflow.

## Evaluation rules

- A tool must solve a specific workflow problem; novelty alone is not sufficient.
- Experiments use bounded branches and existing acceptance criteria.
- The primary implementation agent and independent reviewer should be separated where practical.
- Existing CI, regression, privacy, provenance, and scope boundaries remain authoritative.
- Tool cost includes subscription/API spend, setup time, intervention time, and review burden.
- A tool is not adopted until it demonstrates measurable value across repeated real tasks.

## Standard scorecard

For each tool or configuration, record:

- role/purpose;
- software cost and model/API cost;
- tasks evaluated;
- task completion rate;
- defects or scope violations found;
- false-positive review comments;
- tests selected and outcomes;
- files changed and unnecessary churn;
- human interventions required;
- approximate completion time;
- decision: adopt, optional, retry later, or reject.

## Current stack

### Codex

- Role: primary implementation agent for bounded vertical slices.
- Status: adopted.
- Guardrails: explicit scope/invariants, focused tests, full regression, changed-file/test/risk reporting, stop conditions on failed gates, and user merge authority.

### GitHub Actions

- Role: authoritative automated verification on pushes and pull requests.
- Status: adopted.
- Current gates: Windows and Ubuntu tests, Gitleaks history scanning, syntax-level Ruff checks, and bounded Pyright checks for deliberately cleaned modules.

### Gitleaks

- Role: secret scanning.
- Status: adopted.
- Baseline: full working tree and 470-commit history scanned clean after a narrow allowlist for known non-secret processed-artifact fixture identifiers.

### Ruff

- Role: static lint/syntax checking.
- Status: adopted at syntax-only baseline.
- Current gate: E9 only.
- Ratchet plan: expand rule coverage only after existing lint debt is measured and cleaned in bounded work.

### Pyright

- Role: static type analysis.
- Status: evaluation.
- Whole-repository mode remains advisory/non-blocking because the captured baseline is 3,076 errors and 1 warning across 584 files.
- Cleaned modules may be added to a focused blocking boundary one at a time.

### Hypothesis

- Role: property-based testing for edge cases and invariants.
- Status: evaluation.
- Initial pilot: bounded invariant testing of deterministic deduplication behavior.

### OpenCode

- Role: candidate independent reviewer/second opinion, not primary implementer initially.
- Status: evaluation.
- First experiment: review-only on several real pull requests; track useful findings, hallucinated issues, missed defects, intervention time, and cost.

#### Pilot 1: PR #60 bounded Pyright ratchet

- Candidate change: PR #60, `types: ratchet image analyzer to zero Pyright errors`.
- Exact review range: `87c0097e1fbca2260957081a93d2eb96b3107888..90073eaf765ea9d69e34532ed05bd4811f2c291c`.
- Why suitable: two-file, annotation/CI-only change; no intended runtime behavior change; noncritical and covered by the normal CI workflows.
- Review mode: read-only. The reviewer must not edit files, create commits, or broaden scope beyond the exact range.
- Required review dimensions: correctness, runtime-behavior change, typing accuracy, regression risk, CI correctness, test adequacy, architecture/governance, privacy/provenance risk, and scope creep.
- Finding severity: `BLOCKER`, `MAJOR`, `MINOR`, or `NIT`. Each substantive finding should identify file/line, failure mode, why it matters, and recommended fix.
- Acceptance criteria for the reviewer: inspect only the bounded diff; distinguish real defects from style preference; avoid unrelated pre-existing debt; explicitly state merge recommendation, confidence, and substantive-finding count.

Observed local OpenCode result:

- Execution boundary satisfied: the OpenCode CLI was actually run locally outside GitHub-side tooling against the frozen range.
- Model/configuration evidence available from the run: Qwen3-Coder-Next through OpenCode; exact CLI build/version was not captured and remains an evidence gap.
- Findings returned: one `MINOR` concern that `Dict[str, Any]` is broader than the concrete return structure, plus one `NIT` about workflow-comment wording/scope.
- Overall recommendation: approve/merge; no blocker was reported.
- Positive signal: the typing comment was grounded in the changed code and identified a real precision trade-off rather than unrelated debt.
- Low-value signal: the workflow-comment observation had negligible operational consequence.

Authoritative comparison after the run:

- The reviewed head `90073eaf765ea9d69e34532ed05bd4811f2c291c` had Ruff, Gitleaks, Windows tests, and Ubuntu tests passing, but the focused `pyright-event-bus` job failed.
- The failure persisted on later branches based on the same `main` state, showing the blocking typed-boundary workflow was not healthy after `image_analyzer.py` was added.
- Root CI configuration mismatch identified in follow-up: the focused Pyright job installed only Pyright, while `image_analyzer.py` imports runtime dependencies; the advisory Pyright workflow already installs `requirements.txt` before analysis. Follow-up PR #62 adds those runtime dependencies to the focused job without changing production code.
- OpenCode did not identify this CI correctness defect. Codex/self-review also failed to stop PR #60 despite the red focused Pyright job. GitHub Actions provided the decisive signal.

Pilot 1 scorecard:

- Useful independent findings: 1 minor typing-precision observation.
- False-positive/noise burden: 1 low-value nit.
- Missed known issue: 1 material CI correctness defect in the exact reviewed change.
- Scope discipline: good; no unrelated broad cleanup was proposed.
- Human intervention: required to compare the review against authoritative CI and discover the missed gate failure.
- Cost/time: exact OpenCode runtime/cost was not captured in durable evidence and should be recorded in future pilots.
- Decision after one task: continue evaluation, not yet authoritative. OpenCode may be useful as a second opinion, but this pilot does not justify treating it as a merge gate or replacement for CI.

Exact OpenCode review prompt:

```text
Read-only review. Do not edit files or create commits.

Review only:
87c0097e1fbca2260957081a93d2eb96b3107888..90073eaf765ea9d69e34532ed05bd4811f2c291c

Check correctness, runtime behavior changes, typing accuracy, regression risk, CI correctness, test adequacy, architecture/governance, privacy/provenance risk, and scope creep.

Classify findings BLOCKER / MAJOR / MINOR / NIT.
For each real finding give file/line, failure mode, why it matters, and recommended fix.
Do not invent issues or discuss unrelated pre-existing code.

End with:
MERGE RECOMMENDATION
CONFIDENCE
SUBSTANTIVE FINDINGS
```

### Goose

- Role: candidate automation/MCP orchestration layer.
- Status: later evaluation.
- Constraint: do not grant broad autonomous access until CI/security/tool boundaries are established.

### Ollama/local models

- Role: inexpensive local grunt work where hardware permits.
- Status: later evaluation.
- Candidate tasks: summarization, log classification, documentation cleanup, and other low-risk repetitive work.

### OpenHands

- Role: autonomous issue-to-solution experiment.
- Status: deferred.
- Entry condition: mature CI gates, isolated environment, bounded issue, and explicit comparison against the existing Codex workflow.

## Planned experiments

1. Continue the bounded Pyright ratchet only after the focused CI job is healthy and deterministic.
2. Run the Hypothesis pilot and expand only if it finds useful edge cases or strengthens invariants.
3. Run OpenCode as a read-only independent reviewer on at least two additional bounded PRs, explicitly checking whether it catches known seeded/historical defects without manufacturing issues.
4. Evaluate Goose for controlled MCP/tool orchestration.
5. Later benchmark autonomous agents on a small set of historical bounded tasks using task success, test pass rate, scope compliance, human intervention, time, and cost.
