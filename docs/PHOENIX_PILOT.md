# Phoenix Observability Pilot

## Purpose

Arize Phoenix is evaluated only as an optional local observability layer for bounded self-improvement experiments. It does not participate in target selection, implementation, review, merge, deployment, release, or promotion decisions.

The pilot exposes one explicit bridge from a completed Stage 11 specialized experiment into a small OpenTelemetry span containing decision metadata only.

## Privacy and authority boundary

The bridge exports only:
- experiment identifier;
- aggregate experiment state;
- candidate identifiers;
- viable candidate identifiers;
- deterministic preferred-candidate identifier, when present;
- whether human review is required;
- the fixed Stage 11 strategy names.

It deliberately does **not** export remediation-package contents, source diffs, prompts, evidence text, terminal-reason strings, collection data, credentials, or model outputs.

Phoenix is never imported by the Stage 11 execution path automatically. `emit_to_phoenix(...)` uses a lazy import and converts all Phoenix initialization/export failures into an advisory `PhoenixEmissionReport`. Core execution remains valid when Phoenix is absent or unavailable.

## Local pilot

Start a local Phoenix server in a separate terminal:

```text
uvx arize-phoenix serve
```

Install the tracing helper in the development environment used for the pilot:

```text
python -m pip install arize-phoenix-otel
```

For a local Phoenix instance, set the collector endpoint before explicitly calling the bridge:

```text
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006
```

The code uses `phoenix.otel.register(..., auto_instrument=False, set_global_tracer_provider=False)` so the pilot does not globally instrument the application or silently expand telemetry collection.

## Exit gate

T5 may be marked complete after:
- focused bridge tests pass in authoritative CI;
- Phoenix remains optional and absent from core runtime requirements;
- a local Stage 11 result can be rendered as one bounded trace without package/content leakage;
- no observability failure can alter a self-improvement result;
- human merge and promotion authority remain unchanged.

Any broader tracing, automatic instrumentation, remote Phoenix service, prompt/content capture, or CI dependence requires a separate architecture decision.
