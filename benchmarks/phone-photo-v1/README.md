# Phone-photo recognition benchmark protocol

This evaluation-only harness measures the existing paired-image AI-Assisted Coin
Images production proposal path. Each pair represents one physical specimen.
It does not change recognition, provider/model, prompts, thresholds, validation,
OCR, confidence, GUI review, or collection persistence. Holdout acquisition and
recognition tuning are outside this benchmark slice.

## Version-control and privacy policy

The real `manifest.json` and `manifest.sha256` are private local artifacts and
must not be staged, committed, or uploaded to CI. Original filenames, image
hashes, roles, ground truth, provenance, raw responses, and run identifiers belong
in local evidence storage. A relative path or hash is not publication permission.
Provider-use authorization is separate from permission to redistribute material.

Only this sanitized README and RESULTS.md are allowlisted in this directory.
Ignore rules exclude all other files and subdirectories here, including alternate
manifests, images, previews, response files, and journals. Runtime evidence remains
under the already ignored `debug_outputs/phone-photo-v1/` directory. Original
photographs remain at the operator's private source location. Do not force-add
ignored artifacts or place private evidence in these public documentation files.

Automated tests construct synthetic manifests and image-byte fixtures in temporary
directories. They require neither the real manifest nor private photographs or
credentials. The public slice contains no real corpus inventory or freeze digest.
Private-corpus byte verification is a separate explicitly authorized local check.

## Architecture and manifest contract

The harness reuses `VisualIdentityRequest`, `VisualIdentityImage`, and the unchanged
`OpenAITerraVisualIdentityProvider`. It scores the public rank-one proposal and
retains raw evidence; diagnostic candidates cannot override public abstention.
Original image bytes are read in place without cropping, rotation, enhancement,
renaming, or overwriting. Manifest validation enforces contained original image
references, exactly one obverse and reverse per specimen, unique specimen/image
identities, image digests, valid difficulty and challenge tags, and explicit
per-field verification. Roles determine request order independently of filename
order. All source hashes are checked before calls and after the run.

The private manifest uses schema `coin-analyzer-phone-photo-v1`, version `1.0`,
and privacy classification `private-local-only`. It records label provenance,
stable specimen IDs, paired original filenames with SHA-256 and roles, difficulty
(`easy`, `medium`, `hard`), challenge tags, and `ground_truth` records for
`jurisdiction`, `denomination`, `year`, and `type_design`. Each truth record has
`value` and `verification`: verified values are nonempty strings; unverified
values are null. Missing identity must never be inferred to complete a benchmark.
Difficulty/cohort assignments should be frozen before observing results.

The private `manifest.sha256` contains the canonical manifest digest: SHA-256 of
UTF-8 JSON with sorted keys and compact separators. The generic loader validates
a sidecar when present. A real frozen execution should retain it; changing labels
or image bytes requires a separately documented new freeze, not silent editing.
The schema and illustrative synthetic fixtures live in code/tests, not in a
sanitized replacement for the private corpus's exact freeze.

Reports retain the manifest, configuration, source fingerprints, runtime metadata,
raw evidence, usage, and response identities locally. Exclusive JSONL journals are
flushed and fsynced per response. Rejection and runtime failure do not stop later
specimens; there is no harness retry, fallback, or repair. Existing SDK retry
behavior is unchanged. Interruption leaves remaining specimens unattempted.
Postflight integrity failure preserves returned evidence but invalidates completeness.

## Scoring

Text matching uses NFKC normalization, trimming, and case-folding only. There are
no new semantic aliases, fuzzy corrections, or generic probability scores.
Equivalent identity strings can therefore score differently; raw values remain
available for private failure analysis.

For each verified field, the result is correct, incorrect, or abstained. Missing,
null, empty, unknown, none, n/a, and unavailable values abstain. Unverified truth
is always unscorable. Field accuracy is correct / (correct + incorrect + abstained).
Field abstention rate uses the same denominator; overall abstention rate is
weighted across eligible verified field opportunities. Empty denominators yield
null, not zero. Rejections, runtime failures, and unattempted specimens are excluded.

Exact identity requires every verified field to be correct. A specimen with no
verified fields or no validated outcome has no exact-match denominator. Partial
failure or abstention fails exact identity. Counts of verified fields remain
visible so incomplete truth cannot imply complete numismatic identification.
Difficulty and challenge cohorts use the same rules, including explicit empty
cohorts. Execution completeness does not guarantee full scoring denominators.

## Execution report contract, version 2

The report retains its corpus schema and adds `execution_contract_version: 2`.
Every specimen must carry one explicit `execution_status`:

| Status | Meaning | Ordinary field/exact scoring |
|---|---|---|
| `completed_prediction` | Production-validated public prediction, possibly partial | Verified fields only; absent fields abstain |
| `completed_abstention` | Production-validated abstention | Verified fields abstain; exact identity fails |
| `validation_rejected` | Existing production validator rejected output | Excluded; never an abstention or incorrect prediction |
| `provider_runtime_failure` | Attempt failed at provider/runtime boundary | Excluded |
| `not_attempted` | No attempt recorded | Excluded |

Rejection rows require an empty prediction, retained `raw_provider_output`, and
nonempty `validator_failure` reason. Raw output may itself be malformed; it is
not promoted to predictions. Available response ID, tokens, and latency survive.
Runtime failures retain their exception category and available raw evidence;
arbitrary exception text is omitted. Production validator messages are retained
because they explain the rejected contract. Missing execution records are filled
as `not_attempted` by report finalization, not invented as abstentions.

`execution` records `specimens_total`, `specimens_attempted`,
`specimens_with_validated_predictions`, `specimens_with_validated_abstentions`,
`specimens_rejected_before_scoring`, `specimens_with_provider_runtime_failure`,
`specimens_not_attempted`, and `execution_complete`. Attempted includes reused
verified rejection evidence. The four attempted outcome counts sum to attempted;
attempted + not attempted equals total. `execution_complete` means a nonempty
inventory has an attempt recorded for every specimen. `baseline_complete` also
requires verified postflight source hashes and no interruption. Neither flag
means accurate recognition, absence of runtime failures, or adequate scoring
coverage. Empty denominators stay null. `infrastructure_failures` now counts only
provider/runtime failures; rejection and unattempted counts remain separate.
Difficulty and challenge cohorts expose the same execution breakdown and scoring
rules. A hard process termination may leave only the incomplete checkpoint journal;
absence of a finalized report is never evidence of a complete baseline.

### Narrow reuse of the original rejected attempt

`--resume-rejected-report` and `--resume-sha256` must be supplied together.
This supports only the original stopped-run shape: the first manifest specimen
has a retained structured `VisualIdentityMalformedOutput` rejection and a response
ID; all remaining records are empty `not_run_after_failure` rows. Successful
predictions, arbitrary runtime failures, extra/missing/reordered/duplicate IDs,
or later attempted specimens are not accepted by this migration.

Before any new call, the harness checks the caller-pinned archive byte digest,
exact full manifest (including specimen identities, image filenames, roles,
labels and image hashes), manifest digest, provider configuration and digest,
provider source digest, privacy classification, archived verified source integrity,
ordered specimen inventory, and each row's ground truth. Current original image
bytes are also preflight-verified. The exact unchanged production validator is
replayed locally against the archived structured raw output and must reject it
again. This offline check makes no inference request. The rejection reason is
recovered from that validator; original raw output, response ID, usage and latency
are retained. Archive bytes are never changed.

The new report links the pinned source report digest, original timestamp, original
Git commit and scorer digest, and reused specimen ID. The harness/scorer source
is deliberately allowed to change for this versioned execution-accounting fix;
production provider source/configuration and corpus must match. A mismatch stops
before any new provider call. This is not a general checkpoint or successful-result
resume system. It avoids a second paid call for the first rejected specimen only after the
stated provenance checks pass.

## Reproduction

Run synthetic tests without a private corpus or provider access:

```powershell
.venv/Scripts/python.exe -m unittest tests.test_phone_photo_benchmark
```

To validate a separately prepared private corpus locally, substitute your private
source directory for the illustrative path below. This does not call a provider:

```powershell
.venv/Scripts/python.exe -m capture_import.phone_photo_benchmark benchmarks/phone-photo-v1/manifest.json --source C:/path/to/private/photos
```

Only during a separately authorized execution, with credentials already configured,
add `--execute-openai-upload`. To reuse an eligible prior rejection, also supply
`--resume-rejected-report` with the private archive path and `--resume-sha256`
with its trusted, previously recorded digest. Never substitute a new digest merely
to bypass an integrity failure. The resume checks above run before new calls.

Outputs use unique filenames under ignored `debug_outputs/phone-photo-v1/`.
The CLI returns nonzero for incomplete execution. Exit zero means attempted
coverage and source integrity, not successful recognition or zero runtime failures.
Model reruns may differ; preserved raw evidence supports deterministic rescoring.

## Readiness

See RESULTS.md for aggregate validation evidence. This protocol supports local
measurement and deterministic synthetic regression tests. A small private corpus,
unverified truth, provisional cohorts, and stochastic model output do not by
themselves establish an authoritative recognition gate. Gate thresholds, repeat-run
policy, publication rights, and authoritative CI evidence require separate decisions.
