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

Do not supply changed-path or check-result claims as success evidence. If retained claims are supplied for comparison, they are marked unverified and cannot override Git or independently executed check evidence. Retain the evidence object, its output digests, and the grader result outside the candidate worktree.

`INVALID` means a protocol or prohibited benchmark/grader mutation breach. `FAILED_TASK` means a valid attempt has failed/missing required validation. `VALID_WITH_FINDINGS` means corpus/run identity and required checks passed; scope findings remain separately reported. Do not report `INVALID` as an ordinary task failure. Immutable historical test bytes alone are insufficient: every acceptance invocation must also observe the Task Packet's expected implementation path(s) resolved under the candidate repository. Synthetic test/`__main__` paths never satisfy that gate. Missing or outside-candidate implementation provenance makes independent acceptance unavailable and prevents successful grading; historical patch equality remains unnecessary.

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
