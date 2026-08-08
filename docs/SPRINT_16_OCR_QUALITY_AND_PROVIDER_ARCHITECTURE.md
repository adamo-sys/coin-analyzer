# Sprint 16 — OCR Quality and Provider Architecture

## Status

**Architecture closure: COMPLETE**

**Production provider expansion: DEFERRED**

Sprint 16 closes the locked OCR quality and provider-architecture scope at
commit `567a59a`. The delivered architecture is explicit, opt-in,
deterministic, immutable at its public value boundaries, and transient.

Only `legacy-ocr` is currently integrated as a production OCR provider.
Multi-provider behavior is architecture-complete and tested with deterministic
test doubles; this document does not claim that multiple production providers
or vendors are shipped.

The authoritative repository regression has one known unrelated failure in the
historical melt-value cache-persistence test. No Sprint 16 OCR failure, error,
or other new regression was identified.

## Objective

Sprint 16 establishes a provider-neutral OCR architecture that can:

- describe configured OCR providers truthfully;
- select providers deterministically from exact capability requirements;
- invoke multiple explicitly bound providers in deterministic order;
- preserve each provider's success or typed failure independently;
- compare exact provider output without selecting a winner;
- normalize raw confidence through explicit deterministic profiles;
- retain sanitized cleanup degradation beside valid OCR evidence; and
- connect capability snapshots to executable provider bindings without hidden
  discovery or default activation.

Sprint 16 does not make OCR authoritative. OCR output remains advisory and
subject to the existing human-review boundaries.

## Locked-roadmap acceptance mapping

The locked roadmap states:

```text
Sprint 16 — OCR quality and provider architecture
- Provider-specific exceptions.
- Multiple OCR providers.
- Ensemble comparison.
- Deterministic provider selection.
- Confidence calibration.
- Artifact cleanup diagnostics.
- Provider capability reporting.
```

The locked roadmap remains unchanged. The implementation evidence is:

| Locked item | Committed evidence | Closure status | Delivered boundary |
| --- | --- | --- | --- |
| Provider-specific exceptions | `workflow_ocr_provider_contracts.py`; `2f34827` | COMPLETE | Provider-neutral typed categories with bounded provider IDs and diagnostic codes |
| Multiple OCR providers | Registry, bindings, selection, execution, and ensemble modules; `8324e93` through `196c64e` | COMPLETE WITH DISCLAIMER | Multiple explicit providers are supported and tested; only `legacy-ocr` is a production implementation |
| Ensemble comparison | `workflow_ocr_ensemble.py`; `196c64e` | COMPLETE | Exact field-value comparison with explicit agreement, disagreement, missing, and failed states; no winner |
| Deterministic provider selection | `workflow_ocr_provider_selection.py`; `8324e93` | COMPLETE | Exact fail-closed criteria and lexical registry order; multiple matches remain explicit |
| Confidence calibration | `workflow_ocr_confidence_calibration.py`; `ed06536` | COMPLETE WITH DISCLAIMER | Explicit deterministic profile transformation to integer basis points; no empirical probability claim |
| Artifact cleanup diagnostics | `workflow_ocr_cleanup_diagnostics.py` and the legacy adapter edit; `567a59a` | COMPLETE WITH DISCLAIMER | Sanitized transient warning beside valid output; explicit sink required for legacy warning emission |
| Provider capability reporting | `workflow_ocr_provider_contracts.py` and `workflow_ocr_provider_integration.py`; `2f34827`, `567a59a` | COMPLETE WITH DISCLAIMER | Immutable caller-supplied snapshots for configured providers; no automatic probing |

The phrase “Multiple OCR providers” is satisfied as a provider-neutral
architecture capability, not as a claim that two vendor implementations ship.
The roadmap contains no explicit requirement to deliver two production
vendors. Claiming “multiple production OCR providers” would be inaccurate.

## Controlled architecture chain

```text
explicit OCRProviderCapabilities snapshot
    |
    v
OCRProviderRegistry
    |
    v
deterministic OCRProviderSelectionResult
    |
    v
explicit OCRProviderExecutionBinding
    |
    v
deterministic OCRProviderExecutionBatch
    |
    +-----------------------------+
    |                             |
    v                             v
OCRProviderExecutionWithCleanup   OCRProviderEnsembleResult
                                  |
                                  v
                         OCRCalibratedExecutionConfidence
```

Cleanup diagnostics and calibrated confidence are referential views over an
unchanged execution batch. Neither rewrites reports, candidates, execution
status, ensemble status, or review state.

Selection and execution remain separate:

- the registry contains immutable capability snapshots;
- selection evaluates exact requirements without invoking providers;
- bindings connect exact capability objects to analyze-compatible providers;
- execution invokes every selected provider once in exact selection order;
- one provider failure does not stop a later selected provider;
- ensemble comparison consumes the complete batch without provider ranking;
- calibration consumes successful candidates without changing ensemble
  policy; and
- cleanup warnings do not trigger retry, fallback, or reselection.

## Unit and commit inventory

| Unit | Commit | Subject | Primary output |
| --- | --- | --- | --- |
| 1A | `2f34827` | `feat: add OCR provider contracts` | Capability snapshots and typed provider errors |
| 1B | `8324e93` | `feat: add deterministic OCR provider selection` | Registry, criteria, findings, and deterministic selection |
| 1C-A | `27e6e84` | `feat: add multi-provider OCR execution` | Explicit bindings, requests, outcomes, and execution batches |
| 1C-B | `196c64e` | `feat: add deterministic OCR ensemble comparison` | Exact field evidence, value groups, and ensemble findings |
| 1D | `ed06536` | `feat: add deterministic OCR confidence calibration` | Explicit calibration profiles and calibrated evidence |
| 1E | `567a59a` | `feat: add OCR cleanup diagnostics and provider integration` | Cleanup warnings and capability-to-binding integration |

## Unit 1A — Provider contracts

Module:
`capture_import/workflow_ocr_provider_contracts.py`

Unit 1A defines:

- bounded provider IDs;
- bounded machine-readable diagnostic codes;
- caller-supplied availability snapshots;
- declared or unknown field-support modes;
- immutable capability snapshots; and
- a provider-neutral typed operational error hierarchy.

The operational categories are:

- provider unavailable;
- invalid provider input;
- provider execution failure;
- invalid provider output; and
- provider cleanup failure.

The contracts do not inspect optional dependencies, discover providers,
persist snapshots, rank providers, or activate OCR.

## Unit 1B — Deterministic provider selection

Module:
`capture_import/workflow_ocr_provider_selection.py`

Unit 1B supplies:

- an immutable lexically ordered provider registry;
- exact image-role, media-type, field, availability, and allowlist criteria;
- one finding per registered capability;
- an ordered tuple of every eligible capability; and
- strict helpers for registered-provider and single-provider requirements.

Selection is fail-closed. Unknown provider references are rejected. No eligible
provider and multiple eligible providers remain distinct conditions. The
selector does not rank or invoke providers and does not silently choose the
first match.

`UNKNOWN` availability can be excluded or admitted only through the explicit
selection policy. `UNAVAILABLE` is always excluded.

## Unit 1C-A — Multi-provider execution

Module:
`capture_import/workflow_ocr_provider_execution.py`

Unit 1C-A binds exact capability objects to providers satisfying the current
`OCRMetadataProvider.analyze()` runtime seam.

Execution:

- requires a nonempty selection;
- requires an exact binding for every selected provider;
- preserves selection order;
- invokes each provider once, sequentially;
- preserves every provider outcome;
- sanitizes typed and unexpected failures;
- validates returned reports and their source/provider identity; and
- continues after one provider fails.

Execution performs no selection, discovery, retry, fallback, persistence,
parallelism, timeout management, or confidence policy.

## Unit 1C-B — Ensemble comparison

Module:
`capture_import/workflow_ocr_ensemble.py`

Ensemble comparison derives exact field evidence across the complete execution
batch. The field-level vocabulary includes:

- consensus;
- single source;
- conflict;
- no observation; and
- all providers failed.

Values are compared exactly. Case, whitespace, punctuation, Unicode code
points, and normalized candidate text are not rewritten by the ensemble
service.

The service does not:

- vote;
- choose a majority or winner;
- weight provider confidence;
- rank providers;
- normalize candidate values;
- suppress disagreement; or
- mutate the execution batch.

## Unit 1D — Confidence calibration

Module:
`capture_import/workflow_ocr_confidence_calibration.py`

Unit 1D defines immutable profiles containing exact integer basis-point
calibration points. A registry resolves an exact provider/field profile or an
explicit provider-level fallback. Calibration uses deterministic integer
arithmetic and returns referential evidence retaining the exact provider,
report, and candidate objects.

Calibration is deterministic profile-based normalization. It is not:

- an empirically validated probability of correctness;
- a statistical accuracy claim;
- learned calibration;
- provider ranking;
- winner selection;
- automatic thresholding; or
- runtime profile discovery or persistence.

No calibration profile is loaded automatically by the default runtime.

## Unit 1E — Cleanup diagnostics and provider integration

Modules:

- `capture_import/workflow_ocr_cleanup_diagnostics.py`
- `capture_import/workflow_ocr_provider_integration.py`
- `legacy_ocr_workflow_provider.py`

Cleanup diagnostics distinguish two structural severity values:

- `WARNING`; and
- `FAILURE`.

Only a warning can be attached to
`OCRProviderExecutionWithCleanup`. A warning:

- belongs to an exact successful provider capability;
- retains an optional bounded artifact identifier;
- follows execution-batch provider order;
- preserves the successful report and all candidate identities; and
- does not alter consensus, conflict, or calibrated confidence.

Fatal cleanup remains exclusively represented by Unit 1C as
`FAILED/CLEANUP`. A fatal outcome retains no report, does not acquire a
duplicate cleanup diagnostic, and does not stop a later provider.

The legacy provider can emit
`TEMPORARY_IMAGE_DELETE_FAILED` when deletion of its temporary image fails.
Emission requires an explicitly supplied immutable capability snapshot and an
explicit diagnostic sink. The diagnostic contains no temporary path, raw
exception, exception message, traceback, or image bytes. Sink return values
are ignored, and ordinary sink exceptions cannot replace valid OCR output.

Provider integration retains an exact registry and optional exact execution
bindings. Its availability-to-binding policy is:

| Availability | Binding policy |
| --- | --- |
| `AVAILABLE` | An executable binding is required |
| `UNAVAILABLE` | An executable binding is forbidden |
| `UNKNOWN` | A binding may be present or absent |

Every binding capability must be the identical capability object stored in the
registry. Equal-but-distinct substitutions and foreign bindings fail closed.

The truthful legacy capability snapshot is:

| Property | Value |
| --- | --- |
| Provider ID | `legacy-ocr` |
| Image roles | `front`, `reverse`, `edge` |
| Media types | `image/jpeg` |
| Field support | `DECLARED` |
| Fields | `banknote_prefix`, `certification_number`, `country`, `denomination`, `year` |
| Availability | Exact caller-supplied snapshot |

The integration helper does not construct or invoke the legacy provider and
does not probe its dependencies.

## Public API inventory

### Provider contracts

- `OCRProviderContractError`
- `InvalidOCRProviderContractError`
- `OCRProviderError`
- `OCRProviderUnavailableError`
- `OCRProviderInputError`
- `OCRProviderExecutionError`
- `OCRProviderOutputError`
- `OCRProviderCleanupError`
- `OCRProviderAvailability`
- `OCRProviderFieldSupportMode`
- `OCRProviderCapabilities`

### Provider selection

- `OCRProviderSelectionContractError`
- `InvalidOCRProviderSelectionContextError`
- `OCRProviderSelectionError`
- `UnknownOCRProviderSelectionReferenceError`
- `NoEligibleOCRProviderError`
- `AmbiguousOCRProviderSelectionError`
- `OCRProviderAvailabilityPolicy`
- `OCRProviderSelectionStatus`
- `OCRProviderSelectionReason`
- `OCRProviderRegistry`
- `OCRProviderSelectionCriteria`
- `OCRProviderSelectionFinding`
- `OCRProviderSelectionResult`
- `require_registered_ocr_provider`
- `select_ocr_providers`
- `require_single_selected_ocr_provider`

### Provider execution

- `OCRProviderExecutionContractError`
- `InvalidOCRProviderExecutionContextError`
- `OCRProviderBatchError`
- `NoSelectedOCRProvidersError`
- `MissingOCRProviderBindingError`
- `MismatchedOCRProviderBindingError`
- `OCRProviderExecutionStatus`
- `OCRProviderFailureCategory`
- `OCRProviderExecutionBinding`
- `OCRProviderExecutionBindings`
- `OCRProviderExecutionRequest`
- `OCRProviderExecutionOutcome`
- `OCRProviderExecutionBatch`
- `execute_selected_ocr_providers`

### Ensemble comparison

- `OCRProviderEnsembleContractError`
- `InvalidOCRProviderEnsembleContextError`
- `OCRProviderFieldEvidenceStatus`
- `OCRProviderEnsembleFieldStatus`
- `OCRProviderFieldEvidence`
- `OCRProviderEnsembleValueGroup`
- `OCRProviderEnsembleFieldFinding`
- `OCRProviderEnsembleResult`
- `compare_ocr_provider_outcomes`

### Confidence calibration

- `OCRConfidenceCalibrationContractError`
- `InvalidOCRConfidenceCalibrationContextError`
- `OCRConfidenceCalibrationError`
- `OCRConfidenceCalibrationProfileNotFoundError`
- `OCRConfidenceCalibrationCoverageError`
- `OCRConfidenceCalibrationInputError`
- `OCRConfidenceCalibrationPoint`
- `OCRConfidenceCalibrationProfile`
- `OCRConfidenceCalibrationRegistry`
- `OCRCalibratedCandidateConfidence`
- `OCRCalibratedExecutionConfidence`
- `resolve_ocr_confidence_calibration_profile`
- `calibrate_ocr_confidence_value`
- `calibrate_ocr_execution_confidence`

### Cleanup diagnostics

- `OCRProviderCleanupDiagnosticContractError`
- `InvalidOCRProviderCleanupDiagnosticContextError`
- `OCRProviderCleanupDiagnosticSeverity`
- `OCRProviderCleanupDiagnostic`
- `OCRProviderExecutionWithCleanup`

### Provider integration

- `OCRProviderIntegrationContractError`
- `InvalidOCRProviderIntegrationContextError`
- `OCRProviderIntegration`
- `build_ocr_provider_integration`
- `create_legacy_ocr_provider_capabilities`
- `build_legacy_ocr_provider_integration`

## Deterministic guarantees

Sprint 16 guarantees:

- provider IDs and diagnostic codes use bounded grammars;
- capability tuples use validated canonical ordering;
- provider registries use lexical provider-ID order;
- supplied tuples are validated rather than silently sorted;
- selection findings cover every registry entry in registry order;
- eligible providers remain in registry order;
- execution outcomes cover every eligible provider in selection order;
- one provider failure does not suppress later outcomes;
- ensemble fields and evidence have deterministic order;
- exact disagreement remains explicit;
- confidence calibration uses deterministic integer basis-point arithmetic;
- cleanup warnings follow execution-batch provider order;
- at most one cleanup warning exists per provider execution; and
- repeated equivalent inputs produce equivalent outputs.

Identity is also deliberate:

```text
capability snapshot
    -> registry capability
    -> binding capability
    -> selection capability
    -> execution outcome capability
    -> cleanup diagnostic provider
```

The cleanup wrapper retains the exact execution batch. Successful outcomes
retain their exact reports, and reports retain their exact candidate objects.
Ensemble and calibration outputs refer back to those source objects rather
than reconstructing OCR evidence.

## Safety boundaries

Sprint 16 introduces no:

- default OCR activation;
- provider discovery or plugin loading;
- environment-based provider configuration;
- automatic availability probing;
- filesystem provider scanning;
- dynamic provider imports;
- global registry or binding table;
- default provider preference;
- provider ranking;
- first-success or fallback behavior;
- automatic retry;
- timeout or cancellation policy;
- parallel or asynchronous execution;
- confidence-weighted consensus;
- automatic winner selection;
- persistent provider configuration;
- persistent calibration profile registry;
- persistent cleanup diagnostic;
- timestamp or generated diagnostic ID;
- cleanup path or exception-text retention;
- review approval authority;
- collection read, write, or mutation authority;
- desktop/UI activation; or
- durable OCR schema change.

OCR remains disabled in the default image-processing and desktop composition.
The existing opt-in composition requires an explicit provider or an explicit
call to the legacy OCR runtime factory.

## Truthful limitations

1. `legacy-ocr` is the only production OCR provider currently integrated.
2. Multi-provider behavior is validated with deterministic test doubles, not
   multiple shipped production providers.
3. Provider availability is an explicit caller-supplied snapshot. It is not
   detected, refreshed, or aged automatically.
4. Confidence calibration is deterministic profile-based normalization. It is
   not an empirically validated probability of correctness.
5. Cleanup diagnostics are transient. The legacy provider emits them only
   when an explicit diagnostic sink is supplied.
6. Fatal cleanup remains Unit 1C `FAILED/CLEANUP`.
7. `OCRMetadataProvider.analyze()` is the authoritative current runtime seam.
8. Historical `workflow_ocr_models.OCRProvider.observe()` remains bounded
   compatibility debt.
9. OCR remains opt-in and disabled by default.
10. Provider discovery, retries, fallback, concurrency, timeout policy,
    durable diagnostics, profile persistence, metrics, and UI presentation
    remain deferred.

This architecture is not described as a production-ready OCR platform.

## Protocol boundary

The current execution architecture depends on the analyze-compatible
`OCRMetadataProvider` protocol from `workflow_ocr_stage.py`. Unit 1C bindings
and Unit 1E integration both validate that seam.

The older `OCRProvider.observe()` protocol remains in
`workflow_ocr_models.py`. Sprint 16 does not migrate production execution to
it, add another generic provider protocol, or delete it. A later usage audit
may deprecate or remove it after compatibility consumers are understood.

## Validation baseline

The authoritative Sprint 16 focused group recorded:

```text
314 total
314 passed
0 skipped
0 failures
0 errors
```

The discovered OCR suite recorded:

```text
814 total
814 passed
0 failures
0 errors
```

The authoritative repository regression recorded:

```text
3,884 total
3,861 passed
22 skipped
1 known unrelated failure
0 errors
```

The sole failure was:

```text
test_melt_value_engine.TestApiSpotPriceProvider.test_cache_persistence
expected: 40.0
actual:   None
```

This is the existing repository-root-relative cache-path issue. It was
independently reproducible before Sprint 16 and is unrelated to OCR provider
architecture. No OCR regression or other new non-OCR regression was found.
The generated `data/test_silver_spot_cache.json` artifact was absent after the
closure regression.

The full repository suite is therefore not described as green.

## Deferred work

### Sprint 16 closure debt

- integrate a real second production OCR provider;
- resolve or deprecate the historical `observe()` seam after a usage audit;
- refresh provider availability through an explicit application service;
- load calibration profiles through an explicit runtime boundary;
- present cleanup diagnostics to an operator;
- improve reusable Sprint 16 test fixtures; and
- maintain the historical melt-value cache test separately.

### Post-Sprint 16 provider evolution

- retry and fallback policy;
- timeout and cancellation behavior;
- parallel or asynchronous execution;
- durable cleanup or provider diagnostics;
- empirical or learned confidence calibration;
- provider quality history and metrics;
- persistent profile repositories;
- provider discovery or plugin architecture;
- vendor credentials and endpoint configuration; and
- desktop/UI provider configuration.

None of these deferred items is silently implemented by the current modules.

### Separate Sprint 15 rollout obligations

The following remain Sprint 15 production-rollout work and are not Sprint 16
provider-architecture gaps:

- recoverable old-file backup;
- post-replacement recovery;
- durable mutation audit evidence; and
- end-to-end apply orchestration.

Sprint 16 does not modify or claim completion of those mutation obligations.

## Deliberate exclusions

Sprint 16 deliberately excludes:

- production vendor expansion beyond `legacy-ocr`;
- automatic provider discovery or dependency probing;
- provider ranking, preference, voting, or winner selection;
- fallback, retry, timeout, cancellation, and concurrency;
- calibration-profile persistence or automatic loading;
- statistically validated confidence;
- cleanup-diagnostic persistence;
- provider metrics and quality feedback;
- automatic OCR review decisions;
- confirmed-observation construction;
- collection change planning or mutation;
- desktop provider controls; and
- Sprint 17 field-intelligence rules.

## Closure decision

**PASS.**

All seven locked Sprint 16 items have committed, tested architecture evidence.
Provider-specific errors, immutable capability snapshots, deterministic
selection, explicit multi-provider execution, exact ensemble comparison,
deterministic confidence calibration, sanitized cleanup diagnostics, and
capability-to-binding integration form one directional and opt-in
architecture.

Closure is truthful with one production provider because the locked roadmap
requires “Multiple OCR providers” without stating that two production vendors
must ship. The architecture can register, select, execute, compare, and
calibrate multiple explicitly supplied providers, and those behaviors are
tested deterministically. Vendor expansion remains explicit deferred work.

Sprint 16 is complete as the bounded OCR quality and provider architecture.
It is not a claim of a production-ready OCR platform, automatic provider
operation, empirically validated accuracy, durable diagnostics, or UI
integration.

## Approved measured-runtime amendment: fixed sparse-text segmentation

Status: VERIFIED

Benchmark v1 established that the installed `legacy-ocr` Tesseract runtime
completed without infrastructure errors but the default page segmentation
returned empty text for all coin sides. The legacy local OCR call therefore
uses exactly one fixed Tesseract configuration: `--psm 11` (sparse text).

This amendment changes only page segmentation for the existing local
`pytesseract.image_to_string` call. It does not add fallback modes, alter image
preprocessing, change thresholds or candidate scoring, special-case benchmark
assets, or affect injected raw-text providers. Local Tesseract whitespace is
collapsed only because sparse-text output is multiline while the existing OCR
evidence contract rejects control characters. Review remains mandatory.

## Measured-runtime experiment: fixed OCR input rescaling

Status: REJECTED; not enabled in production

Benchmark v1 production Tesseract inputs ranged from 467×474 to 960×963
pixels. A controlled experiment resized every input exactly once to 2× width
and 2× height using Pillow LANCZOS immediately before the fixed PSM 11 call.
No other OCR, preprocessing, candidate, scoring, threshold, or benchmark input
changed.

The experiment reduced year accuracy from 33.3% to 16.7%, left country,
denomination, and full-identity accuracy at 0.0%, and left the unresolved rate
at 100.0%. Mean latency increased from 2.242 seconds to 4.565 seconds (median
2.182 to 4.374; p95 3.003 to 7.584). The additional structured outputs were
false denomination candidates (`$4` and `$2`), while one correct `2013` year
was lost. Fixed 2× input rescaling therefore failed the identity-evidence and
latency acceptance criteria and was removed from the production OCR path.

## Measured-runtime experiment: deterministic Otsu binarization

Status: REJECTED; not enabled in production

All Benchmark v1 inputs reached the OCR provider as RGB images ranging from
467x474 to 960x963 pixels. A controlled experiment converted each image once
to grayscale and applied one deterministic global Otsu threshold, producing a
same-dimension 1-bit image immediately before the unchanged `--psm 11` call.
No rescaling or other preprocessing, candidate, scoring, threshold, or
benchmark change was present.

The experiment reduced year accuracy from 33.3% to 16.7%, left country,
denomination, and full-identity accuracy at 0.0%, and left the unresolved rate
at 100.0%. It lost the clean US-cent `2013` prediction by rendering the token
as `2OL3`, recovered no new identity-bearing structured prediction, and
retained only the glare-case `2013`. Mean latency decreased from 2.268 seconds
to 1.899 seconds (median 2.163 to 1.786; p95 3.289 to 2.753), but the accuracy
regression fails the retention criterion. Otsu binarization was therefore
removed from the production OCR path.
