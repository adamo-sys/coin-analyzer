# Benchmark implementation status and aggregate validation

The execution-contract v2 harness and synthetic tests are implemented. The frozen
baseline execution is complete: every specimen has an attempted outcome, with
rejections kept separate from recognition accuracy. No calls were made during
resilience validation or cleanup; the subsequent authorized baseline made nine
new identification calls and reused one provenance-verified prior rejection.
Production recognition behavior is unchanged.

This public document intentionally excludes real specimen identities, filenames,
image/manifest/archive fingerprints, labels, provider evidence, response IDs,
private filesystem paths, and individual run identifiers. Detailed evidence,
photographs, manifests, freeze sidecars, raw responses and journals remain local
and ignored. The companion README documents the publication boundary.

## Aggregate baseline status

| Execution category | Specimens |
|---|---:|
| Attempted | 10 |
| Validated predictions | 8 |
| Validated abstentions | 0 |
| Validation rejected | 2 |
| Provider/runtime failures | 0 |
| Not attempted | 0 |

Execution and baseline completeness are true. Both rejection reasons and all raw
outputs are retained locally. Rejections are neither abstentions nor ordinary
incorrect predictions, and are excluded from normal scoring. Three field-level
abstentions occur within the validated partial predictions; these differ from a
validated whole-specimen abstention. Original source hashes match after execution.

| Field | Correct | Incorrect | Abstained | Scored denominator | Accuracy |
|---|---:|---:|---:|---:|---:|
| jurisdiction | 5 | 3 | 0 | 8 | 62.5% |
| denomination | 5 | 2 | 1 | 8 | 62.5% |
| year | 4 | 2 | 2 | 8 | 50.0% |
| type_design | 0 | 0 | 0 | 0 | unavailable |

Exact identity across verified fields: **2/8 (25%)**. Overall field abstention
rate: **3/24 (12.5%)**. Unverified ground truth is excluded; type/design accuracy
is unavailable. These are frozen strict normalized-text scores, not a semantic
adjudication. No representation aliases or scoring adjustments were added after
seeing outcomes. Execution completeness does not imply accurate recognition.

### Aggregate cohorts

All cohort figures exclude rejected/unverified observations from their normal
accuracy denominators. Counts are descriptive; small and overlapping cohorts do
not establish statistical reliability. Field columns show correct/denominator.
Type/design has no scorable ground truth in any cohort.

| Difficulty | Attempted | Rejected | Jurisdiction | Denomination | Year | Exact identity | Field abstention |
|---|---:|---:|---|---|---|---|---|
| easy | 2 | 0 | 2/2 | 0/2 | 1/2 | 0/2 | 16.7% |
| medium | 6 | 1 | 2/5 | 4/5 | 2/5 | 1/5 | 13.3% |
| hard | 2 | 1 | 1/1 | 1/1 | 1/1 | 1/1 | 0.0% |

| Challenge tag | Attempted | Rejected | Jurisdiction | Denomination | Year | Exact identity | Field abstention |
|---|---:|---:|---|---|---|---|---|
| historical-jurisdiction | 4 | 1 | 0/3 | 2/3 | 1/3 | 0/3 | 11.1% |
| holder-documentation | 1 | 0 | 1/1 | 1/1 | 1/1 | 1/1 | 0.0% |
| paired-images | 10 | 2 | 5/8 | 5/8 | 4/8 | 2/8 | 12.5% |
| phone-photo | 10 | 2 | 5/8 | 5/8 | 4/8 | 2/8 | 12.5% |
| unverified-identity | 1 | 1 | 0/0 | 0/0 | 0/0 | 0/0 | unavailable |

A 0/0 cell means unavailable, never 0% accuracy. Detailed specimen predictions,
individual rejection reasons, evidence, usage and private identifiers remain only
in ignored local reports/journals. The earlier immutable report was not modified.
Its first rejection was reused only after matching the pinned archive, manifest,
provider configuration/source, image bytes, and unchanged validator behavior.

The final report was rescored offline and matched the saved field/exact/cohort
metrics exactly. Journal inventory confirms one record per specimen, one reused
rejection and nine new outcomes. No retries, recognition tuning, model changes,
threshold changes, or production-validator changes were made by this harness run.

## Existing validation evidence

- Resilience benchmark suite: 25 tests passed.
- Ruff on the benchmark harness and tests: passed.
- Bounded Pyright on those two files: 0 errors, 0 warnings, 0 informations.
- Root unittest discovery: 5,442 tests run; 9 failures; 26 skipped.
- All nine failures reproduced in the unchanged doctor-health suite inside the
  sandbox. Outside the sandbox, that suite passed: 12 tests run, 1 skipped.
  Doctor-health tests and core filesystem dependencies matched baseline/current
  main; main's Windows and Ubuntu CI were passing at verification time. These
  are pre-existing sandbox restrictions, not demonstrated benchmark regressions
  or evidence that main is failing. No doctor-health code was changed.
- Independent resilience review: PASS WITH NOTES, no blocking implementation
  findings. Documentation clarifies attempted coverage versus scoring coverage.
- At the original validation checkpoint, authoritative CI had not run for the
  benchmark slice. A passing main build did not establish CI success for it.

The regression evidence above predates this documentation/ignore/synthetic-fixture
cleanup. Full regression was not repeated for the cleanup; its focused validation
is recorded below. No local Gitleaks result is claimed.

## Commit-readiness cleanup

The real manifest and its freeze digest are explicitly ignored. Only sanitized
README.md and RESULTS.md are allowlisted within the benchmark directory; other
files/subdirectories, including photos, previews, alternate manifests, raw output,
and journals, are ignored. Runtime evidence remains under ignored debug_outputs.
The inventory test now builds and freezes a wholly synthetic inventory in a
temporary directory. It never opens the real private corpus.

The original commit-readiness file set was exactly `.gitignore`,
`capture_import/phone_photo_benchmark.py`, `tests/test_phone_photo_benchmark.py`,
`benchmarks/phone-photo-v1/README.md`, and `benchmarks/phone-photo-v1/RESULTS.md`.
The harness belongs to the earlier implementation and requires no change for
this cleanup. No private metadata or artifacts belong in that set. Nothing had
been staged, committed, or pushed at that cleanup checkpoint.

Cleanup validation:

- Focused benchmark suite: 25 tests passed.
- Ruff on harness and tests: passed with repository-configured rules.
- Bounded Pyright on harness and tests: 0 errors, 0 warnings, 0 informations.
- Isolated public-code copy: all 25 tests passed with no private manifest,
  sidecar, or photographs present. Module origins were checked to ensure the
  isolated harness and tests were used; only read-only Git HEAD provenance came
  from the original checkout.
- Nine explicit private-path and representative artifact ignore checks passed.
- The scoped candidate file inventory is exactly the five proposed files above;
  no files are staged, and neither private metadata file is tracked.
- Checks found no original private image filenames, image/freeze/archive hashes,
  or private source paths in the proposed public files.
- Integrity hashes confirm the harness and both private metadata files are
  byte-for-byte unchanged by this cleanup. No provider calls occurred.

## Frozen execution checkpoint

The five-file public boundary was checked before the authorized baseline. No
private filenames, image hashes, or private metadata files were included. The
harness and production provider remained unchanged during execution. Only this
sanitized results document was updated afterward; detailed run artifacts remain
ignored and local. No files were staged, committed or pushed. Existing focused,
isolated, Ruff and Pyright evidence remains applicable to the unchanged code;
this execution adds measured baseline evidence, not a new CI or tuning claim.

## Offline maintenance verification

The saved JSON report and JSONL checkpoint were rechecked locally after the
interruption. Offline scoring of the ten checkpoint outcomes exactly reproduced
the saved specimen, execution, field, exact-identity, and cohort results. Every
public field and cohort table matches that report. The journal contains one
archive-matched reused rejection and nine new outcomes; both rejection reasons
and raw outputs remain retained locally. The frozen manifest and current harness
and provider fingerprints match the report. Source-image integrity remains the
verified postflight result recorded by the completed run; this maintenance did
not reopen the original photographs.

The bounded synthetic suite passed again: 25 tests. Repository-configured Ruff
passed on the harness and tests; bounded Pyright reported 0 errors, 0 warnings,
and 0 informations. Private-token checks on the five public candidate files and
ignore checks for all existing benchmark evidence files plus representative
private artifact paths passed. No provider calls or prediction regeneration
occurred. Only this sanitized maintenance record was added; the proposed five-file
commit set above is unchanged. Full regression and authoritative CI were not
rerun for this documentation-only maintenance.

## Baseline evidence closeout (2026-09-13)

The persisted evidence supports a complete descriptive baseline under the frozen
scoring contract. It does not establish general recognition reliability: the
corpus is small, cohort memberships overlap, two observations were rejected
before scoring, and type/design ground truth is unverified.

Offline verification reproduced the entire saved report from its provenance and
ten journal outcomes, including specimen scoring, execution counts, field and
exact-identity metrics, and difficulty/challenge-tag aggregates. The frozen
manifest and sidecar agree with the report; current production-provider and
benchmark-scorer source fingerprints and the full provider configuration match
the recorded identities. All twenty original photographs were read locally and
their bytes still match the frozen image hashes.

The archived rejection passed the existing pinned-archive/provenance checks and
local validator replay. Each validated prediction was reconstructed from its
retained structured response using the unchanged validator; the other rejection
retains malformed JSON and its recorded failure reason. No predictions were
regenerated, and no provider/API calls or evidence-file edits occurred.

All public aggregate tables match the persisted report. Rejections remain outside
ordinary accuracy and abstention denominators. The results above are therefore
confirmed observations of this run, with execution completeness separate from
recognition accuracy.

The original five-file benchmark slice is now present in local Git history. This
closeout changes only this sanitized RESULTS.md; historical checkpoint statements
above describe their respective times. Public-table consistency, private-token
exclusion, artifact ignore/tracking checks, and diff whitespace checks passed.
Code tests and static analysis were not repeated for this documentation-only
change; earlier results remain historical evidence. Authoritative CI was not
queried or run during closeout. No staging, commit, push, or merge was performed.
