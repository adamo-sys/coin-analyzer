# ADR-010: Bounded Legacy Recognition Orchestration

- Status: Accepted (implemented and verified)
- Date: 2026-08-21

## Context

The supported Tk workflow historically called `CoinRecognizer.detect_coin()`
directly from `CoinCollectionApp.run_denomination_detector()`, translated the
result into a stable GUI dictionary, and left acceptance and saving to the
collector. The remote lineage also contains a much more mature `capture_import`
subsystem with its own durability, OCR, visual-identification, and human-review
architecture.

The legacy detector needs a controlled execution boundary without changing its
behavior or making that boundary authoritative for the independent import
system.

## Decision

Wrap only the legacy GUI detector path in a runtime-only orchestration shell.
The shell has an explicit capability allowlist, one capability, a hard one-call
limit, at most two routing decisions, and deterministic terminal routes. Every
completed detector attempt ends at collector review; a missing image requests
input without invoking the detector.

`CoinRecognizer` remains authoritative for detector behavior and is imported
lazily by a narrow adapter. The adapter preserves source-specific scores as
metadata, exposes no generic confidence unless its semantics are defensible,
and maps back to the exact historical GUI dictionary.

Opaque scan IDs are generated internally. Optional telemetry is injected and
contains only bounded status, routing, count, timing, and failure-category
metadata. It contains no image path, OCR text, evidence body, notes, collection
record, or credential. The existing runtime EventBus is the default GUI sink;
the provider-oriented inference telemetry schema is not reused because token,
model, and cost fields do not describe this detector honestly.

The shell has no persistence, GUI, provider, OpenCV, pytesseract,
confirmed-observation, or `capture_import` dependency. `capture_import` does not
depend on the shell and remains independently composed.

## Consequences

- Legacy behavior can be benchmarked before and after the architectural wrap.
- A faulty repeating router cannot cause a loop or a second detector call.
- Recognition remains advisory and cannot write collection state.
- The application retains a small extra runtime contract and adapter.
- Future specialists require a separate approved decision; this ADR does not
  authorize multi-capability routing.

## Rejected Alternatives

- Rewriting `CoinRecognizer`: unnecessary risk to established behavior.
- Reusing `capture_import` as the legacy shell: would conflate independent
  workflows and authority boundaries.
- Reusing provider inference telemetry directly: would manufacture provider,
  model, token, and cost semantics.
- Adding an agent framework or model-selected tools: unjustified for one
  deterministic capability and incompatible with the bounded execution goal.

## Reconsider When

Reconsider only when a measured workflow requires more than one capability or
durable pause/resume behavior. Any expansion must preserve collector authority,
privacy, deterministic limits, and compatibility evidence.
