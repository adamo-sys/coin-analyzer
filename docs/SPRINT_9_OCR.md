# Sprint 9 — Advisory OCR Import Pipeline

## Status

Sprint 9 adds an explicit, review-only OCR path for capture-package imports.

OCR is not enabled in the default desktop workflow. Callers must opt in through the dedicated runtime factory or diagnostic CLI.

## Safety boundaries

- OCR output is advisory evidence.
- Every OCR candidate requires human review.
- OCR does not assign or persist grades.
- OCR does not mutate the collection.
- OCR does not create application-state or confirmed-observation files.
- Tesseract and pytesseract remain optional.
- The default desktop pipeline remains OCR-free.

## Architecture

### Contracts

`capture_import/workflow_ocr_models.py`

Defines immutable OCR observations, candidates, conflicts, reports, review status, and the provider protocol.

### Legacy adapter

`ocr_workflow_adapter.py`

Converts legacy OCR and validation output into hardened workflow contracts.

### Advisory stage

`capture_import/workflow_ocr_stage.py`

Adds the `ocr-metadata-extraction` stage. It prefers cropped images, falls back to normalized images, and emits JSON-safe metadata only.

### Provider bridge

`legacy_ocr_workflow_provider.py`

Wraps the legacy OCR experiment and validation components behind the new provider contract.

### Opt-in composition

`capture_import/workflow_ocr_composition.py`

Builds the OCR-enabled pipeline separately from the default image pipeline.

Pipeline order:

1. `package-validation`
2. `manifest-preparation`
3. `image-normalization`
4. `image-quality-scoring`
5. `crop-detection`
6. `ocr-metadata-extraction`
7. `obverse-reverse-pairing`
8. `image-duplicate-detection`

### Runtime factory

`capture_import/workflow_ocr_runtime.py`

Provides `build_legacy_ocr_pipeline(...)`.

### Diagnostic CLI

`capture_import/workflow_ocr_cli.py`

Example:

```powershell
python -m capture_import.workflow_ocr_cli `
    C:\path\to\input.ca-package `
    --workspace C:\path\to\ocr-diagnostics `
    --raw-text "CANADA 1967"
```

Omit `--raw-text` to permit the optional local OCR runtime.

## Optional dependencies

```powershell
python -m pip install -r requirements-ocr.txt
```

The application and default image pipeline must continue to work without these optional dependencies.

## Deferred work

- human review UI;
- desktop feature flag;
- confirmed-observation integration;
- collection persistence after explicit approval;
- external OCR providers;
- OCR-driven grading.

## Known technical debt

- The legacy OCR subsystem still contains mutable internal models.
- Provider error reporting is coupled to the workflow stage identifier.
- Temporary image cleanup tolerates unlink failure.
- OCR metadata has no dedicated desktop presentation model yet.

## Sprint 9 commits

```text
c48d3a1 feat: add OCR metadata contracts
c9e374f feat: adapt legacy OCR to workflow metadata
cd7193a feat: add advisory OCR workflow stage
8a04dde feat: bridge legacy OCR into workflow provider
852caf1 feat: add opt-in OCR pipeline composition
c34bf79 feat: add legacy OCR runtime factory
caa69ed feat: add OCR diagnostic CLI
```
