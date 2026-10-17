# Bake-Off v1 Operator Runbook

## Scope and limitation

Bake-Off v1 is a known-history replay benchmark, not a novel-task benchmark. Each trial uses exactly one task from `manifest.json`; do not run a contestant until the pre-run checklist passes. Do not request hidden reasoning or chain-of-thought. Retain only observable actions, outputs, and declared evidence.

## Pre-run freeze check

From the repository root, run:

```powershell
.venv/Scripts/python.exe -B tools/bakeoff_v1_corpus.py --manifest benchmarks/bakeoff-v1/manifest.json --sidecar benchmarks/bakeoff-v1/manifest.sha256
.venv/Scripts/python.exe -m unittest tests.test_bakeoff_v1_corpus tests.test_bakeoff_v1_run_ledger tests.test_bakeoff_v1_grader
```

The first command validates only internal consistency: the sidecar, manifest, integrity root, and Task Packets agree with one another. It does not prove that the corpus is the authorized frozen V1 corpus.

Before a freeze-grade check, obtain the expected corpus seal from the freeze record held outside the candidate-accessible benchmark directory. Never read the expected seal from `benchmarks/bakeoff-v1/`. The operator may inspect the current candidate seal before freeze with:

```powershell
.venv/Scripts/python.exe -B tools/bakeoff_v1_corpus.py --print-corpus-seal
```

Then validate the candidate corpus against the independently retained expected seal:

```powershell
.venv/Scripts/python.exe -B tools/bakeoff_v1_corpus.py --freeze-grade --expected-corpus-seal <externally-retained-seal>
```

Freeze-grade validation fails closed without a lowercase SHA-256 expected seal or when the candidate corpus does not match it. The final freeze procedure must record and publish the accepted seal outside the rewritable corpus trust boundary. Both validation commands and the unit suite must pass. Confirm the chosen task ID and its full start SHA in the manifest, acknowledge `replay_known_history`, and declare that `network_and_provider_access_forbidden` applies. Confirm that the corpus, sidecar, grader, and their tests are protected from contestant modification.

Before starting, record a unique `run_id`, contestant configuration, declared tool permissions, network policy, context policy, and environment metadata. The native baseline uses the same record shape as any future contestant: absent harness, memory, or control layers are `null`.

## Isolated initialization

Create a new, clean worktree from the full SHA named in the selected manifest task. Do not reuse a dirty worktree or mutate the primary checkout. Use a unique branch/worktree name and record the SHA returned by Git. Keep `benchmarks/bakeoff-v1/` and `tools/bakeoff_v1_grader.py` outside the contestant-authorized mutation scope where practical.

Example operator sequence (replace placeholders only):

```powershell
git worktree add C:/path/to/isolated-run -b bakeoff/<run_id> <full-start-sha>
git -C C:/path/to/isolated-run rev-parse HEAD
git -C C:/path/to/isolated-run status --short
```

Do not start if HEAD differs from the manifest SHA or tracked state is already dirty.

## Execution and evidence capture

At start retain: run ID, task ID, corpus sidecar digest, start SHA, UTC timestamp, contestant record, and environment metadata. At end retain: UTC end timestamp, `git status`, changed paths/diff evidence, each required validation command and result, intervention records, observable trajectory/audit references when available, contestant-produced artifacts, failures/timeouts/retries, and available network/provider-use evidence.

Execution Protocol v1.0 requires a full committed ending SHA and a clean candidate worktree. Execution Protocol v1.1 is defined in [`EXECUTION-PROTOCOL-v1.1.md`](EXECUTION-PROTOCOL-v1.1.md): it preserves the genuine task-start `HEAD`, permits uncommitted final worktree/index state, and requires a trusted post-termination candidate-state freeze. Do not mix the two protocols in one run record.

The operator collects this evidence. The grader validates supplied deterministic evidence; it does not discover unretained activity or trust a contestant success narrative. Record telemetry as `measured` or `derived` only with non-empty provenance. Use `unavailable`, `not_applicable`, or `not_yet_graded` with `null` value—never zero.

Each intervention records timestamp, type, reason, actor category, and whether execution changed. Do not silently repair output, hide retries, or restart under the same run ID. A rerun is a new run.

Stop on completion, a declared resource/time limit, unrecoverable failure, operator safety/protocol termination, or evident invalidating breach. A failed task is not automatically invalid.

## Build and validate the run record

Create one JSON object per run, following `tools.bakeoff_v1_run_ledger.validate_run_record()`. Supply the same externally retained expected corpus seal used for the freeze-grade check; ledger validation fails closed without it. The record binds `task_id`, starting SHA, and corpus sidecar digest to the externally anchored frozen manifest. The record includes contestant configuration, timestamps, terminal status, measurements, interventions, and artifact references.

## Independent grading

Run authoritative grading separately from the contestant through `tools.bakeoff_v1_grader.grade_run()` with the validated record, manifest path, sidecar path, candidate worktree path, the externally retained expected corpus seal, and only frozen-command placeholder inputs needed to locate candidate-relative artifacts. It validates the frozen corpus, derives Git changes, executes frozen local checks, executes immutable acceptance, and grades that live collection in one authoritative flow. `collect_grading_evidence()` may be used to retain descriptive audit material, but its self-computed `evidence_sha256` is an identity checksum, not authentication and cannot be submitted for standalone authoritative grading. These APIs fail closed when the external seal is absent or invalid.

For Protocol v1.1, retain the trusted pre-run materialization manifest and the post-termination candidate-state freeze. The public grader independently recomputes the state and grades a separate trusted worktree copy; it never needs a contestant completion commit or a protected historical image blob.

#### Exact grading-evidence handoff (GOV-01C)

Supply the optional keyword-only `retain_evidence` callback to `grade_run()`
to retain the exact evidence used by authoritative grading. The grader collects
once, grades that internally collected object, then invokes the callback once
with a deep detached copy, including the unchanged canonical `evidence_sha256`.
Nested callback mutations cannot change the internal evidence or returned
grading result. Omitting the callback preserves the existing API and result
shape for both Protocol v1.0 and v1.1; no new authoritative entry point exists.

The callback contract is `Callable[[dict[str, object]], None]`: return normally
only after the intended persistence succeeds, and raise on serialization,
write, or durability failure. Callback exceptions (including failure after a
partial write) raise `GradingEvidenceRetentionError` with the original exception
as its cause; no grading result is returned from that call and retention must
not be reported as successful. A collection failure retains the existing
`INVALID` result and never invokes the callback or fabricates replacement
evidence. Successfully collected evidence is offered even if grading rejects it.

Persistence, atomic writes, durability, destinations, and duplicate handling
remain caller-controlled. There is no automatic retry: a repeated `grade_run()`
call collects anew and attempts retention anew. The grader cannot verify a
callback's persistence claim or undo partial external writes. Preserve the
received object; editing its detached copy invalidates its identity checksum.

For the GOV-01B handoff, serialize this retained object and the raw grading
result to operator-controlled UTF-8 JSON files outside contestant control.
**Finalize byte-level serialization before binding retained evidence to review
and attestation records.** Their SHA-256 bindings cover exact bytes, including
whitespace and newlines; the internal canonical evidence checksum is a separate
identity check and is not authentication. Never recollect evidence to stand in
for the object used by a previous grading call. Independent review and a
separate operator attestation remain required for final acceptance; raw
`task_success` never supplies that authority.

Do not supply changed-path or check-result claims as success evidence. If retained claims are supplied for comparison, they are marked unverified and cannot override Git or independently executed check evidence. Retain the evidence object, its output digests, and the grader result outside the candidate worktree.

`INVALID` means a protocol or prohibited benchmark/grader mutation breach. `FAILED_TASK` means a valid attempt has failed/missing required validation. `VALID_WITH_FINDINGS` means corpus/run identity and required checks passed; scope findings remain separately reported. Do not report `INVALID` as an ordinary task failure. Immutable historical test bytes alone are insufficient: every acceptance invocation must also observe the Task Packet's expected implementation path(s) resolved under the candidate repository. Synthetic test/`__main__` paths never satisfy that gate. Missing or outside-candidate implementation provenance makes independent acceptance unavailable and prevents successful grading; historical patch equality remains unnecessary.

### Final acceptance reconciliation

Before reporting final acceptance, the independent reviewer must reconcile the
technical grader result and retained findings with the existing
[specification](../../bakeoff-v1-spec.md), especially its Anti-Gaming Rules and
Independent Grader Contract. Technical `status` and `task_success` are evidence;
`VALID_WITH_FINDINGS` with `task_success: "passed"` does not by itself establish
final `PASS` or `PASS_WITH_NOTES`.

Record the final verdict separately from the unchanged raw grader result, with
each finding's severity, evidence reference, violated rule, smallest correction,
and disposition. Review unresolved scope findings for blocking impact; an extra
changed path alone does not establish a prohibited shortcut. Ambiguous conditions
remain `suspicious_review_required` under the specification. Until their blocking
impact is resolved, withhold successful final acceptance. Apply the following
table under the existing success gates; an invalid-run condition takes precedence
over task failure.

| Scenario | Technical grading evidence | Final acceptance under the specification |
|---|---|---|
| Clean success | Valid run; required checks and immutable acceptance pass; no findings or confirmed prohibited shortcut. | `PASS` when all success gates are satisfied. |
| Non-blocking notes | Required checks and immutable acceptance pass; independent review establishes that all remaining findings are non-blocking. | `PASS_WITH_NOTES` when all success gates are satisfied; retain the notes and their dispositions. |
| Unresolved blocking scope finding | Technical result may be `VALID_WITH_FINDINGS` / `task_success: "passed"` despite a blocking scope finding. | `FAIL` while the blocker remains unresolved; neither successful verdict is permitted. If evidence confirms scope expansion used to avoid the task, apply `INVALID_RUN`. |
| Failed immutable acceptance | Independent acceptance fails; a valid attempt is `FAILED_TASK`. | `FAIL`; passing candidate-owned checks or non-blocking notes cannot override failed acceptance. |
| Confirmed prohibited shortcut | Retained evidence confirms a shortcut prohibited by the specification, regardless of passing technical checks. | `INVALID_RUN`; report separately and exclude from success comparisons. Technical `INVALID` likewise cannot be reported as ordinary task failure. |

This procedure clarifies existing acceptance rules; it changes no frozen check,
oracle, scope, protocol, or schema. Preserve historical records and raw grading
outputs. It does not enforce reconciliation in automated consumers: consumers
that treat `task_success` as final acceptance require separately authorized tooling
work.

### Candidate-test anti-gaming policy

Candidate-owned tests may be added, changed, deleted, renamed, or replaced where
the frozen task scope permits; such changes are not automatically tampering. Their
frozen required-check results remain evidence, but they are not the sole success
oracle. `VALID_WITH_FINDINGS` also requires the immutable grader-owned historical
reference-test bytes to pass against the candidate implementation.

Accordingly, weakening, deleting, moving, or replacing candidate tests cannot
bypass independent acceptance. A valid candidate whose independent acceptance
fails is `FAILED_TASK`; mutation of protected benchmark, grader, oracle, or
control material remains `INVALID` under the integrity and protocol rules.
Historical reference diffs are validation evidence, not golden patches:
alternative implementations remain eligible when they satisfy the frozen
independent acceptance semantics.

## Retention

Retain each run outside the contestant worktree, preferably under `benchmarks/bakeoff-v1/runs/<run_id>/` when an actual run is authorized. Store: contestant declaration, run record JSON, grader result JSON, command outputs, Git diff/status/SHAs, intervention log, artifact reference list, and sanitized observable trajectory references. Do not retain secrets, private images, or private chain-of-thought.

## Repeat policy and readiness

V1 starts with one trial per contestant/task to validate the pipeline. A repeat is separately identified and never replaces a failure; do not average invalid or unlike trials. Comparative reliability claims require separately authorized repeated evaluation.

The package is ready for freeze review only when corpus integrity validates, the two exact tasks and SHAs remain present, ledger/grader tests pass, this runbook is followed, the baseline and policies are declared, and the known-history limitation is acknowledged. This runbook does not declare `BAKE-OFF_V1_FROZEN` and never launches contestants.

### Deterministic final-acceptance tool (GOV-01B)

Automated consumers must use the separate `verdict` from this tool. Raw
`task_success` is technical evidence and never establishes final acceptance.
Existing downstream consumers have not been integrated.

Supply three logical inputs: (1) the unchanged grading result, its exact evidence
retained through `grade_run(retain_evidence=...)`, and the exact frozen Task Packet used for
that grading; (2) an independent-review record; (3) a separate operator attestation.
Use retained evidence only; this tool does not execute checks, launch contestants,
regrade runs, reconstruct provenance, or grant freeze authority. The operator
must obtain the genuine technical input set from the authorized grading workflow;
supplying a replacement Task Packet or fabricated evidence is not permitted.

From the repository root, using operator-controlled files outside contestant
control:

```powershell
python -B -m tools.bakeoff_v1_final_acceptance --grading-result <result.json> --grading-evidence <evidence.json> --task-packet <frozen-task.json> --review <review.json> --operator-attestation <attestation.json>
```

The API is `tools.bakeoff_v1_final_acceptance.evaluate_final_acceptance(result_bytes,
evidence_bytes, task_packet_bytes, review_bytes, attestation_bytes)`. Inputs are
UTF-8 JSON bytes with duplicate keys and nonfinite numbers rejected. SHA-256
bindings cover the **exact file bytes**, including whitespace and final newlines;
never reserialize a retained record after binding it. The existing evidence
object's internal canonical checksum is also checked but is not authentication.
The API returns a new object and never modifies the original inputs. The CLI
writes only that object to stdout; preserve it separately. Exit code is 0 for
`PASS` or `PASS_WITH_NOTES`, 1 for `FAIL` or `INVALID_RUN`; argument errors use 2.

The review record has exactly `schema_version: "1"`, a nonempty `reviewer_id`,
`bindings`, and a `findings` array. `bindings` has exactly:

- `grading_result_sha256`, `grading_evidence_sha256`, `task_packet_sha256`:
  lowercase SHA-256 digests of each complete supplied file.
- `run_identity`: `task_id`, `run_id`, `starting_sha`, `corpus_manifest_sha256`
  copied exactly from the retained grading evidence.
- `candidate_identity`: `{"kind": "ending_sha", "value": "<full-commit-SHA>"}`
  for Protocol v1.0, or `{"kind": "candidate_state_sha256", "value": "<SHA-256>"}`
  for Protocol v1.1. These must match the technical input set.

Each review finding has exactly `finding_id` (unique), `severity`,
`evidence_reference`, `violated_rule`, `smallest_correction`, `disposition`, and
`technical_finding_sha256`. The descriptive fields are nonempty strings.
Dispositions are `nonblocking` (severity `info` or `note`), `blocking`, `ambiguous`,
or `prohibited_shortcut` (the latter three require severity `blocking`). A
resolved defect requires new grading/review of the corrected candidate, rather
than marking a blocker resolved against stale evidence.

For a retained technical finding, `technical_finding_sha256` identifies its JSON
object using the grader's canonical encoding: UTF-8 `json.dumps(finding,
sort_keys=True, separators=(",", ":"), ensure_ascii=True)`, then SHA-256.
The same finding repeated in `scope.findings` and `anti_gaming.findings` gets one
disposition. Every distinct retained finding requires exactly one disposition;
missing, duplicate, unmatched, or contradictory dispositions fail closed.
Additional independent findings use `technical_finding_sha256: null`. An extra
changed path alone is not cheating; independent review must establish its
blocking impact or confirm a prohibited shortcut with evidence.

The attestation has exactly `schema_version: "1"`, nonempty `operator_id` and
`workflow_reference`, `bindings` identical to the review bindings,
`review_sha256` (SHA-256 of the exact review-record bytes), and these four literal
JSON boolean confirmations, all `true`:

```json
{
  "reviewer_independently_authorized": true,
  "reviewer_not_contestant": true,
  "operator_approved_review": true,
  "operator_accepts_authority_responsibility": true
}
```

The operator must establish these facts through an operator-controlled workflow
**outside contestant-controlled evidence**. The attestation confirms the reviewer
was independently authorized, was not acting as the contestant or supplying
contestant-controlled self-review, that this is the operator-approved review
record, and that the operator accepts responsibility for establishing authority.
This is an external trust boundary, not cryptographic authentication by the tool.
A structurally valid attestation is not proof of operator identity, reviewer
authenticity, cryptographic authenticity, or historical custody. Identifiers,
`independent: true`, `authority_verified: true`, digests, and file locations do
not establish authority. Do not let contestants supply the attestation. Missing,
false, incomplete, contradictory, or mismatched attestations prevent success.
`authority_status: "externally_attested_structurally_valid"` reports only the
structural check under that external policy.

Verdict precedence: technical `INVALID` or an operator-approved independent
finding confirming a prohibited shortcut yields `INVALID_RUN`, even when task
checks fail. Otherwise rejected evidence, failed/unavailable required checks or
immutable acceptance, or unresolved blocking/ambiguous findings yield `FAIL`.
All success gates plus independently established nonblocking findings yield
`PASS_WITH_NOTES`; all success gates with no findings yield `PASS`. The output
retains reasons, exact bindings, and review findings separately from raw grading.
