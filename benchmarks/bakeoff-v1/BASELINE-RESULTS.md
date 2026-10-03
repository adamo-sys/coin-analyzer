# Coin Analyzer Bake-Off V1 — Native Codex Baseline Results

## Status

Baseline execution is complete.

Six scheduled runs were performed across the two frozen known-history replay tasks:

- `BO1-TASK-PACKETS`
- `BO1-TAMPER-BATCH`

These results establish the initial `native-codex-agents-v1` control dataset. They are not a general estimate of Codex software-engineering success rate.

## Results

| Run | Task | Protocol / execution generation | Execution result | Candidate changes | Grade | Primary observation |
|---|---|---|---|---:|---|---|
| RUN-001 | TASK-PACKETS | historical v1.0 | Completed but execution-policy constrained | 0 | FAILED_TASK | Repository execution was rejected; no implementation produced |
| RUN-002 | TAMPER-BATCH | v1.1 / pre-Launcher-C | Completed but execution-policy constrained | 0 | FAILED_TASK | Local command execution rejected; no implementation produced |
| RUN-003 | TAMPER-BATCH | v1.1 / pre-Launcher-C | Timed out | 0 | FAILED_TASK | Model transport never established |
| RUN-004 | TASK-PACKETS | v1.1 / Launcher B | Completed but execution-policy constrained | 0 | FAILED_TASK | Repository inspection/execution blocked; no implementation produced |
| RUN-005 | TASK-PACKETS | v1.1 / Launcher C | Completed, launcher exit 0 | 7 | FAILED_TASK | Full in-scope implementation attempted; independent historical acceptance failed |
| RUN-006 | TAMPER-BATCH | v1.1 / Launcher C | Completed, launcher exit 0 | 4 | FAILED_TASK | Full in-scope implementation attempted; both independent historical acceptance suites failed |

## Infrastructure Discontinuity

The six results must not be interpreted as six equivalent observations.

RUN-001 through RUN-004 were materially affected by execution infrastructure, policy, or transport conditions. In those runs, the contestant either could not perform normal repository work or did not establish a usable model session.

Launcher C was qualified before RUN-005 and became the prospective execution configuration for RUN-005 onward.

Accordingly, RUN-005 and RUN-006 are the strongest observations of the native baseline under the current execution architecture.

Historical runs remain part of the benchmark record and must not be discarded or retroactively rerun, but analyses should stratify results by protocol and launcher generation.

## Prospective Launcher-C Baseline

RUN-005 and RUN-006 both:

- completed normally with launcher exit code 0;
- retained the exact task-start HEAD;
- produced changes only within the expected implementation scope;
- were accepted as valid runs by the grader;
- had no invalid-run reasons;
- produced implementation work rather than infrastructure-only failure; and
- failed immutable independent historical acceptance.

RUN-005 changed all seven expected TASK-PACKETS implementation paths.

RUN-006 changed all four expected TAMPER-BATCH implementation paths.

This establishes a useful control observation: successful agent execution, correct scope discipline, and candidate-local validation do not by themselves establish behavioral compatibility with the independently defined acceptance oracle.

## RUN-005

- Task: `BO1-TASK-PACKETS`
- Protocol: `1.1`
- Launcher: Launcher C
- Prompt SHA-256: `e225e05b5318d8a9b4c00874f900776e42aaf6c18e328aa4b6926abda97c9958`
- Starting HEAD: `9369b3f6d830d2f0ee7fe41cdabc8c57d7b77612`
- Launcher exit: `0`
- Wall time: `285.522 s`
- Changed paths: `7`
- Candidate-state SHA-256: `13f3e8bab377ceb4dc883a5857ab5f5b370892b4599520a88d612f9512a1f297`
- Invalid reasons: none
- Final grade: `FAILED_TASK`

The initial grading invocation omitted required placeholder `check_inputs`. A corrected regrade supplied the task and outcome template paths. After correction, the only remaining failure was:

`reference-acceptance:tests/test_task_packet.py`

The run was not retried or modified.

## RUN-006

- Task: `BO1-TAMPER-BATCH`
- Protocol: `1.1`
- Launcher: Launcher C
- Prompt SHA-256: `2de9e4fc28455d242694abda08601578bbeb5537b367bc48de99beb940bd8b80`
- Starting HEAD: `ad1401aa63177ce754212241db6a7c6ee0788a8d`
- Launcher exit: `0`
- Wall time: `279.614 s`
- Changed paths: `4`
- Candidate-state SHA-256: `cbd9345b9353f9ec0c5fa549410094f588764762c4deae375fdb393f3cee5ca2`
- Invalid reasons: none
- Final grade: `FAILED_TASK`

Independent acceptance failures:

- `reference-acceptance:test_identification_adversarial_tamper_harness.py`
- `reference-acceptance:test_identification_verification_evaluation_batch.py`

The run was not retried or modified.

## Interpretation Boundary

The aggregate result must not be summarized simply as "Codex went 0/6."

RUN-001 through RUN-004 include substantial infrastructure, execution-policy, or transport confounding.

The prospective Launcher-C subset currently contains two observations. Both produced complete in-scope implementation attempts, and both failed independent historical acceptance.

The evidence therefore supports the narrower statement:

> Under the qualified Launcher-C configuration, the native baseline successfully executed both frozen replay tasks and produced correctly scoped implementations, but neither implementation satisfied the complete immutable historical acceptance oracle.

The benchmark does not establish a general Codex task-success rate. V1 uses known-history replay tasks and has a small sample.

## Control Configuration Going Forward

Future challenger experiments should preserve, unless the experiment explicitly targets one of these dimensions:

- frozen task definitions;
- frozen task-start SHAs;
- sealed prompts;
- sealed corpus;
- protocol v1.1 candidate freezing;
- trusted deterministic grading;
- immutable historical acceptance;
- Launcher C execution behavior;
- network/provider restrictions; and
- the same bounded task and measurement definitions.

A challenger should change one intended contestant variable at a time wherever practical.

## Next Experimental Phase

The baseline infrastructure is complete. No additional baseline repetition is currently required.

The next phase is controlled challenger evaluation.

The first planned challenger is a purpose-built first-party procedural skill, evaluated against the native baseline on the same bounded task and independent acceptance oracle.

Subsequent retained candidates may include alternate skills, harnesses, orchestration approaches, memory systems, and models. Their results should be compared against the prospective Launcher-C native baseline rather than naively against the pooled six-run history.

---

Baseline complete after `RUN-006`.
