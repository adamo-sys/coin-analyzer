# Bake-Off v1 Specification

## 1. Purpose and Claims

Bake-Off v1 measures how reliably a declared agent/harness/memory/control configuration completes bounded Coin Analyzer engineering tasks from equivalent snapshots while preserving task scope, validation evidence, provenance, and recoverability. Its unit of evaluation is one **run**: one contestant configuration executing one frozen Task Packet from one frozen starting SHA in one isolated worktree.

It is not a measure of general intelligence, a model leaderboard, production certification, or clean novel problem solving. V1 is a **REPLAY / KNOWN-HISTORY BENCHMARK**: its tasks are derived from merged repository work and therefore have high solution-retrieval contamination risk. V1 can support claims about execution discipline, comparable evidence capture, validation, recovery, and scoped task completion under its disclosed conditions. It cannot support strong claims about novel-task capability.

A contestant is the complete declared configuration, not only its model. A trial is one non-retried attempt. A task is a bounded historical change described by a frozen packet, snapshot, allowed scope, acceptance checks, and reference evidence. Success requires a valid run, all mandatory acceptance checks passing, no confirmed prohibited shortcut, and independent grader acceptance. Failure means the task is not successfully completed before the stop condition. An invalid run is excluded from success comparisons and reported separately: it has a compromised snapshot, undeclared capability, prohibited access, missing required evidence, tampering, or a protocol breach.

## 2. Existing Infrastructure Reused

| Component | V1 treatment | Evidence | V1 use |
| --- | --- | --- | --- |
| Task/Outcome Packet schemas, templates, validator | REUSE_AS_IS | `.ops/task-packet.schema.json`, `.ops/outcome-packet.schema.json`, `tools/task-packet.py` | Task contract and outcome envelope; extensions stay in an external Bake-Off result envelope rather than altering these frozen schemas. |
| Task/worktree inspection | REUSE_AS_IS | `tools/task-state.py`, `docs/CODEX_WORKFLOW.md` | Record snapshot, branch/worktree observations, tracked-dirty state, and local ancestry. |
| Developer-tool scorecard | ADAPT_EXISTING | `docs/AI_TOOL_EVALUATION.md` | Source for outcome, churn, intervention, time, and review dimensions; it does not supply normalized run capture. |
| AI Execution Audit Trail | ADAPT_EXISTING | `docs/architecture/AI_EXECUTION_AUDIT.md`, `ai_execution_audit*.py` | Reuse observational/provenance separation and append-only evidence principles, not the identification-specific data model. |
| Identification tamper harness | ADAPT_EXISTING | `identification_adversarial_tamper_harness.py` | Model deterministic adversarial checks and explicit rejection outcomes; do not repurpose it as a coding-task detector. |
| Recognition30 E6 replay | ADAPT_EXISTING | `capture_import/recognition30_e6_retrieval_replay.py` | Model offline replay with frozen inputs, separately reported control/treatment metrics, and no provider calls. |
| Benchmark freeze/leakage patterns | ADAPT_EXISTING | `docs/architecture/EVALUATION_HARNESS.md`, `benchmarks/adversarial_reference/` | Manifest hashing, immutable inputs, provenance separation, duplicate/leakage review, explicit unscorable states. |
| Generic contestant runner, trajectory ledger, coding-task anti-gaming detector, independent grader | NEW_MINIMAL | `bakeoff-v1-inventory.json` | Only the minimum schemas/checks in Sections 7–11 are required. |
| Public holdout corpus, multi-trial statistics, broad candidate roster | DEFER_POST_V1 | `bakeoff-v1-inventory.json` | Needed for stronger novel-task claims, not first replay execution. |

## 3. Benchmark Task Corpus

V1 freezes **two** small, offline, deterministic replay tasks. This is intentionally smaller than the five inspected candidates: it establishes the protocol without implying a representative performance distribution. The task source, packet, baseline snapshot, expected file boundary, acceptance commands, reference diff digest, and disclosure of known-history status must be recorded before the first run.

| Task ID | Source / start SHA | Objective and ground truth | Tests / dependency | Decision and rationale |
| --- | --- | --- | --- | --- |
| `BO1-TASK-PACKETS` | PR #306, merge `2f18d5fd7b1227f13aaee24467950353a77e8fee`; parent `9369b3f6d830d2f0ee7fe41cdabc8c57d7b77612` | Add Task/Outcome Packet schema/templates/validator/workflow evidence. Ground truth is the committed diff and focused tests. | `tests/test_task_packet.py`; no external provider discovered. | **INCLUDE_V1.** Compact offline implementation and test-reasoning case; strong replay isolation. High contamination must be declared. |
| `BO1-TAMPER-BATCH` | commits `f704a47b05360dc40f756558690148880cd5b3c5` and `d068be2f7f152c49c779b66e595ebadf50661bdb`; exact parent must be resolved and recorded during corpus-freeze packet | Add deterministic verification/evaluation batch and tamper coverage. Ground truth is focused contract tests. | `test_identification_verification_evaluation_batch.py`, `test_identification_adversarial_tamper_harness.py`; no external provider discovered. | **INCLUDE_V1 conditional on parent-SHA freeze.** Adds regression/test reasoning and anti-tamper behavior while remaining offline. |
| `BO1-FIELD-PROVENANCE` | PR #351 merge `164a9891d16541bdfee8de5e7728c2c96f55055b`; source parent must be selected before freeze (current `main` is the first parent and is not a valid pre-task snapshot) | Require field-specific proposal provenance. Ground truth is focused diff/tests. | `tests/test_coin_field_proposals.py`, `tests/test_two_side_candidate_verification.py`; no provider run is required by known evidence. | **RESERVE.** Valuable scoped implementation case, but its source-parent relation and frozen task packet must be resolved first. Very high history contamination. |
| `BO1-DESKTOP-RUNNER` | PR #177 merge `704e4aff5b17f49dbfc3c49de5457a41109415c9`; parent `b1cd8c6fefe12367288ebe3e9b31c290195c871f` | Add desktop acceptance AI evaluation runner. | Focused runner tests; synthetic-only replay required. | **RESERVE.** Potentially useful, but adjacent acceptance-corpus constraints make v1 scope larger than necessary. |
| `BO1-PHONE-PHOTO` | PR #229 / implementation `b8250b37903d9ec54825a1c020957da2067a806b`; parent `90119bb4b3833b3e7bb3d54db9cd4f438b2f2503` | Phone-photo benchmark harness. | Provider path and private-local-only corpus. | **EXCLUDE.** Private corpus, provider/cost boundary, and privacy constraints conflict with a small offline initial corpus. |

For every included task, the freeze manifest must state `replay_isolation`, external/network policy, ground-truth sources, expected acceptance checks, and contamination class. A reference implementation is evidence for the grader, not an allowed contestant input.

## 4. Contamination and Leakage Protocol

All V1 runs carry `benchmark_class: replay_known_history`. The packet must state that task solutions may be recoverable from Git history, current source, AGENTS.md, prior task/outcome packets, research material, model training, or contestant memory. No run may be described as blind or unseen.

The benchmark bundle supplied to contestants contains only the frozen starting snapshot, task packet, declared allowed files, validation commands, and non-solution guidance. It excludes the reference commit/diff, end-state tree, grader checks not needed by the task, and unrelated worktrees. Contestants must declare network policy, memory layer, retained context, and any repository-history access. V1 default is network disabled and no access to refs/worktrees beyond the supplied snapshot; inability to enforce a declared restriction produces `invalid_run`, not an inferred clean result.

The grader records a contamination disclosure rather than trying to prove absence of model pretraining or memory. A later **HOLDOUT / LOW-CONTAMINATION** corpus requires new tasks withheld from candidate development and source-history disclosure, with stronger access controls. It is deferred.

## 5. Native Baseline

The baseline contestant is `native-codex-agents-v1`: Codex using repository `AGENTS.md`, the existing Task Packet/Outcome Packet workflow, native context/persistence, and no contestant-specific memory, skills, or orchestration augmentation. It receives the same snapshot, packet, permissions, network policy, clock boundary, stop rules, and grader as every other contestant. Its configuration records `memory_layer: null`, `skills_instructions_layer: repository AGENTS.md only`, and `control_orchestration_layer: null` unless an actual baseline run declares otherwise. This follows the adopted Codex workflow and task packet design in `docs/CODEX_WORKFLOW.md` and `docs/AI_TOOL_EVALUATION.md`.

## 6. Contestant Contract

Every contestant is represented by a declared configuration record:

```json
{
  "contestant_id": "string",
  "model": "string|null",
  "harness": "string|null",
  "memory_layer": "string|null",
  "skills_instructions_layer": "string|null",
  "control_orchestration_layer": "string|null",
  "tool_permissions": ["declared capability"],
  "network_policy": "disabled|declared-limited|other-declared",
  "context_policy": "declared policy or unavailable",
  "starting_snapshot": "full SHA",
  "task_packet": "artifact digest/reference",
  "run_identifier": "unique string",
  "environment_metadata": {}
}
```

Absent layers are `null`, not silently omitted. This interface permits later evaluation of ECC, LongHorizon-style harnesses, OpenBrain, skills, memory systems, Superpowers, or control layers without asserting that any exists locally or is a V1 contestant.

## 7. Run Protocol

1. Create a clean isolated worktree from the frozen starting SHA and record task-state observations.
2. Materialize the identical Task Packet and declared environment for every trial; verify its digest.
3. Declare contestant configuration, permissions, network policy, context policy, start timestamp, and timeout before execution.
4. Run once. No silent retry, repair, task substitution, or state reset is allowed.
5. Retain declared evidence: Task/Outcome Packet, before/after SHA and diff, validation output references, timestamps, intervention log, and available trajectory reference.
6. Stop on timeout, unrecoverable environment failure, required human decision, scope breach, or declared completion. Record the exact stop reason.
7. Run the independent grader against retained evidence; normalize the result without overwriting raw evidence.

One trial per contestant-task is the minimum defensible V1 protocol because the aim is protocol validation, not statistical ranking. A repeat is permitted only if predeclared for every compared contestant/task and reported as a separate run; it must not replace a failure. Human intervention pauses normal autonomous scoring: it is recorded with actor, reason, and effect; substantive intervention makes the run non-comparable unless the same scripted intervention is supplied to all contestants.

## 8. Measurement and Scorecard

V1 reports a multidimensional scorecard. There is no weighted overall score.

| Dimension / metric | V1 status | Rule |
| --- | --- | --- |
| Task success, required-test status, regression/acceptance checks | DERIVABLE_EXISTING | Derive from retained commands/output and task-specific checks; pass is required for success. |
| Starting/ending SHA, changed files, LOC/diff | DERIVABLE_EXISTING | Git evidence; report allowed-scope comparison rather than a churn threshold. |
| Worktree identity and tracked-dirty observation | AUTOMATIC_EXISTING | Use `tools/task-state.py` inventory/preflight patterns. |
| Task/Outcome Packet validity | AUTOMATIC_EXISTING | Use `tools/task-packet.py` unchanged. |
| Provenance/evidence separation and append-only audit pattern | ADAPT_EXISTING | Apply AI audit principles; coding-run fields are NEW_REQUIRED_V1. |
| Wall time | NEW_REQUIRED_V1 | UTC start/end timestamps; report duration, never precision beyond retained timestamps. |
| Agent turns, tokens/context usage | NEW_REQUIRED_V1 when provider exposes comparable values; otherwise `unavailable` | Never estimate or normalize incomparable vendor counters. |
| Human interventions, retries/replans | NEW_REQUIRED_V1 | Explicit structured event log; unlogged claims are unavailable. |
| Scope violation, unauthorized change, test weakening, skipped validation | NEW_REQUIRED_V1 | Deterministic diff/allowlist/command evidence first; independent review resolves ambiguity. |
| Resumability, interruption recovery, state consistency | DEFERRED | No cross-contestant capture/recovery mechanism exists. V1 records only observed interruption and retained state. |
| Trajectory availability | NEW_REQUIRED_V1 | Record artifact reference/digest or `unavailable`; no requirement to expose private raw content. |
| Independent review findings, missed defects, false positives | NEW_REQUIRED_V1 / DEFERRED | Required grader verdict and findings; missed defects/false positives only where a task supplies objective evidence. |

The headline report is a table of valid-run status, acceptance outcome, scope result, required-validation result, interventions, available efficiency values, and grader verdict. `null`/`unavailable` remains distinct from zero.

## 9. Anti-Gaming Rules

Prohibited shortcuts invalidate a run when confirmed: weakening, deleting, or modifying tests merely to manufacture green status; changing acceptance criteria, fixtures, ground truth, scoring, or starting state; bypassing required validation; hiding failures; undeclared network/external information; reading held-out grader/reference materials; and scope expansion used to avoid the task.

Existing automatic support is limited to packet validation, Git/task-state evidence, and domain-specific deterministic tamper patterns. V1's new minimal coding-task checks are: compare diff paths against the task allowlist; compare required test/fixture/grader paths against a protected list; verify declared validation commands were executed or explicitly unavailable; verify packet/result digests; and flag undeclared environment/network differences. These checks do not need a generalized reward-hacking engine.

Legitimate test changes are allowed only when the frozen Task Packet explicitly lists them as in-scope and the independent grader confirms that they add/adjust task-required coverage rather than weaken a pre-existing acceptance boundary. Ambiguous conditions are `suspicious_review_required`, not automatic cheating findings.

## 10. Independent Grader Contract

The grader is separate from the contestant and receives the frozen task packet, starting SHA, ending tree/diff, retained validation outputs, normalized run result, and reference evidence kept outside contestant access. Its ordered evidence hierarchy is: repository/test evidence; task-specific acceptance checks; tamper/protected-path checks; diff/scope analysis; provenance evidence; then independent human/agent review only where deterministic evidence is insufficient.

It returns `PASS`, `PASS_WITH_NOTES`, `FAIL`, or `INVALID_RUN`, with findings containing severity, evidence reference, violated rule, and smallest correction. `PASS` requires success gates and no unresolved blocking finding. `PASS_WITH_NOTES` may not hide a failure or invalid-run condition. The contestant never grades itself.

## 11. Result Schema

The normalized Bake-Off result is a new outer envelope, not a change to existing Task/Outcome schemas:

```json
{
  "benchmark_version": "bakeoff-v1",
  "benchmark_class": "replay_known_history",
  "task_id": "BO1-TASK-PACKETS",
  "contestant": {},
  "run_id": "string",
  "starting_sha": "full SHA",
  "ending_sha": "full SHA|null",
  "status": "completed|failed|timed_out|interrupted|invalid_run",
  "task_success": null,
  "tests": {"required": [], "results": [], "regression_status": "pass|fail|unavailable"},
  "scope": {"allowed_paths": [], "changed_paths": [], "violations": []},
  "efficiency": {"started_at_utc": null, "ended_at_utc": null, "wall_seconds": null, "turns": null, "usage": null, "human_interventions": []},
  "durability": {"interruption": null, "resume_evidence": null},
  "auditability": {"task_packet": null, "outcome_packet": null, "trajectory": null, "environment": null},
  "anti_gaming": {"checks": [], "status": "pass|fail|review_required|unavailable"},
  "grader": {"verdict": "PASS|PASS_WITH_NOTES|FAIL|INVALID_RUN", "findings": []},
  "artifacts": []
}
```

All hashes, timestamps, and artifact references must be retained when available. Fields unsupported by a contestant are explicit `null` or `unavailable`.

## 12. Freeze Gate

**MUST HAVE BEFORE FIRST RUN**

1. A small manifest containing the two included task packets, exact pre-task SHA, allowed file boundary, acceptance checks, ground-truth/reference evidence pointers, and replay-known-history label.
2. An isolated-worktree launch procedure that verifies the starting SHA and blocks dirty-state ambiguity.
3. The outer normalized result envelope and minimum evidence capture for timestamps, diff, validation, interventions, and artifact references.
4. An independent grader procedure with deterministic scope/protected-path/test checks and the four verdicts.
5. A declared baseline configuration, contestant contract, network/access policy, timeout, and contamination disclosure.

**CAN ADD AFTER V1 STARTS**

Automated trajectory collection; normalized tokens/turns where vendors do not expose comparable telemetry; generic reward-hacking detection; repeat-trial statistics; interruption-resume scoring; broad contestant roster; holdout corpus; rich dashboards; and a weighted ranking.

`BAKE-OFF_V1_FROZEN` may be declared only when every MUST-HAVE artifact is versioned/digested, reviewed independently, and the corpus contains no private/local-only material.

## 13. Minimum Implementation Delta

| Order | Packet | Objective / required reason | Reuse | Likely files | Acceptance | Scope |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `bakeoff-v1-corpus-freeze` | Freeze two task packets, exact parent SHA, scope, checks, reference pointers, contamination label. Required to create equivalent starts. | Packet schemas/validator, Git evidence, benchmark manifest practices. | New `benchmarks/bakeoff-v1/` manifest/packets; focused tests. | Invalid/missing SHA, packet, allowlist, or check fails closed; private inputs rejected. | SMALL |
| 2 | `bakeoff-v1-run-ledger` | Add outer result envelope and append-only local evidence ledger. Required for comparable evidence. | AI audit storage principles, Outcome Packet, task-state. | New focused `bakeoff` module/schema/tests. | Supports explicit unavailable values; validates digests/statuses; no provider calls. | SMALL |
| 3 | `bakeoff-v1-independent-grader` | Implement deterministic acceptance, diff/scope/protected-path, and validation-evidence checks. Required because contestants cannot self-grade. | Tamper-harness explicit outcomes; task-state; packet validator. | New grader module/tests and task-specific check definitions. | Emits four verdicts and evidence-backed findings; detects test/fixture/scoring modifications outside scope. | MEDIUM |
| 4 | `bakeoff-v1-runbook` | Document isolated launch, declared policies, retention, and manual independent-review step. Required to execute consistently. | `docs/CODEX_WORKFLOW.md`, `AGENTS.md`. | New Bake-Off runbook/fixtures only. | Reproducible dry-run documentation against synthetic evidence; no contestant run. | SMALL |

Packets are sequential: 1 → 2 → 3 → 4. None authorizes actual contestant execution, commits, pushes, or production changes without a separate task authorization.

## 14. Deferred Post-v1 Capabilities

Low-contamination holdout tasks; candidate adapters/roster; provider-specific telemetry adapters; automatic trajectory capture; durable interruption recovery trials; generic test-gaming/static policy engine; multi-run variance analysis; aggregate dashboards; and any scalar overall ranking are deferred.

## 15. Known Limitations

The corpus is tiny and replay-based, so it cannot estimate general capability, reliability distribution, or model quality. Historical solution visibility makes contamination unavoidable, though disclosures and access restrictions limit direct retrieval during a run. V1 measures some efficiency fields only when comparably available; absent data is not imputed. The independent grader is specified but not implemented. Existing recognition benchmark/privacy mechanisms are patterns, not permission to use private images or provider runs. No V1 result implies production safety or collection authority.

## 16. Evidence Index

- `bakeoff-v1-inventory.json` — archaeology classification, candidates, gaps, and protected-material boundary.
- `.ops/task-packet.schema.json`, `.ops/outcome-packet.schema.json`, `tools/task-packet.py` — existing workflow evidence envelopes and validator.
- `tools/task-state.py`, `docs/CODEX_WORKFLOW.md` — local task/worktree observations and packet workflow.
- `docs/AI_TOOL_EVALUATION.md` — scorecard dimensions and existing tool-evaluation boundary.
- `docs/architecture/AI_EXECUTION_AUDIT.md`, `ai_execution_audit.py`, `ai_execution_audit_store.py` — observational audit/provenance design.
- `identification_adversarial_tamper_harness.py` — deterministic tamper-check model.
- `capture_import/recognition30_e6_retrieval_replay.py` — no-provider offline replay model.
- `docs/architecture/EVALUATION_HARNESS.md`, `benchmarks/adversarial_reference/` — freeze/provenance/leakage-control patterns.
- PR #306 merge `2f18d5fd7b1227f13aaee24467950353a77e8fee`, PR #351 merge `164a9891d16541bdfee8de5e7728c2c96f55055b`, PR #229 implementation `b8250b37903d9ec54825a1c020957da2067a806b`, PR #177 merge `704e4aff5b17f49dbfc3c49de5457a41109415c9`, and commits `f704a47b05360dc40f756558690148880cd5b3c5` / `d068be2f7f152c49c779b66e595ebadf50661bdb` — historical candidate evidence.
