# Lightweight Inference Telemetry

Status: `VERIFIED`

## Scope

Coin Analyzer records best-effort operational telemetry at the active production
inference boundaries without changing OCR, model, review, persistence, or GUI
behavior. The instrumented boundaries are:

- local Tesseract OCR (`pytesseract.image_to_string --psm 11`); and
- OpenAI Responses calls used by Ask My Collection planning and explanation.

Telemetry is not part of the collection schema and is strictly best-effort. No
telemetry-side failure, including timing, pricing, validation, serialization,
directory creation, or persistence, may alter an inference result or replace
the original provider exception.

## Record Contract

Each JSON Lines record contains:

- `scan_id`
- `stage`
- `provider`
- `model`
- `duration_ms`
- `success`
- `error_type`
- `input_tokens`
- `output_tokens`
- `estimated_cost_usd`

Durations use a monotonic clock and cover only the provider call. They exclude
the subsequent telemetry write. A successful operation has a null error type;
a failed operation records the exception class before the original exception is
re-raised. Local-provider cost is zero. Token counts and remote cost estimates
remain null when the provider does not supply usage or the model has no entry in
the centralized offline pricing catalog.

## Correlation

The OCR workflow reuses the existing `workflow-<token>` workspace identifier as
its scan ID. Non-standard workspaces receive a stable hash so operational paths
are not persisted. Ask My Collection reuses its existing request ID, allowing
the planning and explanation calls for one request to be correlated.

## Persistence and Failure Isolation

Production telemetry is appended to
`collection_data/telemetry/inference.jsonl`. Storage is independent of the
collection persistence format. Directory creation and writes are lazy. Any
telemetry serialization or storage error is swallowed after the primary call
has completed or failed, so telemetry cannot replace a return value, suppress a
provider exception, or prevent the normal error path.

## Pricing

Pricing lives in `inference_pricing.py` as one offline provider/model catalog.
Unknown pricing is represented as null rather than inferred or fetched at
runtime. Updating that catalog is an independent maintenance change and must not
change inference behavior.

## Benchmark Boundary

Benchmark v1 inputs, labels, manifest, scoring, and committed reports are
unchanged. Provider `duration_ms` excludes telemetry persistence. The existing
benchmark latency boundary surrounds the production pipeline and therefore
includes the small best-effort append cost when telemetry is enabled.

## Verification

- telemetry tests: 17 passed;
- OCR provider tests: 12 passed;
- OpenAI adapter tests: 5 passed;
- focused workflow/correlation tests: 25 passed;
- full regression: 4,442 run; 4,419 passed; 23 skipped.

Independent review conclusion: **PASS WITH NOTES**. JSONL writes are serialized
within one process, not coordinated across multiple application processes;
multi-process locking remains explicitly deferred. Ask My Collection request
IDs are scoped to the current GUI session. Neither limitation changes
collection or inference correctness.
