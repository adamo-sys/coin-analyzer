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
- Current gates: Windows and Ubuntu tests, Gitleaks history scanning, and syntax-level Ruff checks.

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
- Initial mode: advisory/non-blocking CI so existing type debt is measured without blocking unrelated work.

### Hypothesis

- Role: property-based testing for edge cases and invariants.
- Status: evaluation.
- Initial pilot: bounded invariant testing of deterministic deduplication behavior.

### OpenCode

- Role: candidate independent reviewer/second opinion, not primary implementer initially.
- Status: planned evaluation.
- First experiment: review-only on several real pull requests; track useful findings, hallucinated issues, intervention time, and cost.

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

1. Run Pyright advisory CI and inventory the highest-value type-error clusters.
2. Run the Hypothesis pilot and expand only if it finds useful edge cases or strengthens invariants.
3. Use OpenCode as a read-only independent reviewer across multiple real PRs.
4. Evaluate Goose for controlled MCP/tool orchestration.
5. Later benchmark autonomous agents on a small set of historical bounded tasks using task success, test pass rate, scope compliance, human intervention, time, and cost.
