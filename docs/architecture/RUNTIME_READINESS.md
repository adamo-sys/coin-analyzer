# Runtime readiness and Doctor boundary

Status: APPROVED for the bounded #199/#200 epic. #199 implements startup
prerequisites only; Doctor remains a follow-up.

## Shared contract (#199)

`runtime_readiness.evaluate_readiness()` returns a frozen `ReadinessReport` of
frozen `DiagnosticResult(check_id, capability, status, message, action)` records.
`Capability` is CORE, OCR, or AI. `Status` is READY, UNAVAILABLE, or UNVERIFIED.
`report.status_for(capability)` fails closed for absent checks and incorporates
core prerequisites; incomplete required check sets cannot be READY. READY means the named local prerequisite was checked, not
that the entire application or a remote service was exercised.

Python 3.12+ is the documented baseline. Core checks import Tk, Pillow (including
ImageTk), NumPy, OpenCV, pandas, and openpyxl in the selected interpreter; finding
module metadata alone is insufficient. A failed required import blocks launch
with a fixed dependency-specific repair instruction. No exception payload,
credential, collection value, or filesystem path enters diagnostic records.

OCR checks the optional pytesseract import and discovery of its configured
Tesseract command. Discovery cannot prove executable health or language data;
OCR therefore remains UNVERIFIED even when these prerequisites are present.
AI checks the optional OpenAI SDK import and whether OPENAI_API_KEY is nonblank.
A configured SDK/key remains UNVERIFIED: no client, authentication request,
network call, or inference is performed. Optional failures never block CORE.
No confidence semantics are introduced. Probe dependencies are injectable.

`coin_analyzer_startup.main()` checks the runtime before importing the readiness
module, renders safe diagnostics, and imports/starts the existing GUI only when
core prerequisites pass. Unexpected GUI import/startup failures produce a fixed
message and nonzero exit, never a raw traceback. Normal GUI imports remain inert;
the direct script entry delegates before dependency imports. The launcher prefers
its adjacent .venv interpreter, otherwise PATH python then py, and runs the same
bootstrap synchronously so errors remain visible. It does not silently fall back
from a broken .venv. No installer, configuration, persistence, or recovery changes.

Core readiness does not certify a working display, successful collection loading,
write permission, or successful startup. Existing load-failure, stale-save,
recovery, cancellation, and upload disclosure guards remain authoritative.

## Implementation-ready #200 handoff

Entry point: `python -m coin_analyzer_doctor` (flat module matches this repository;
no package reorganization). Default human output; `--json` selects JSON only.
Use the exact #199 `evaluate_readiness`, `DiagnosticResult`, `ReadinessReport`,
`Capability`, `Status`, and `status_for` API. Do not duplicate runtime/dependency
checks. Keep the original runtime report for capability summaries and a
separate tuple of health results for overall/exit policy. Additional doctor
checks remain separate records, grouped by stable
check_id prefixes; they do not redefine CORE prerequisite readiness.

Add `coin_analyzer_doctor.py` for argparse/rendering/exit policy and
`doctor_health.py` for bounded checks. Add `tests/test_coin_analyzer_doctor.py`
and `tests/test_doctor_health.py`; update this document and README.md (six files).

Additional checks:
- Default: runtime results plus UNVERIFIED storage/image/lock checks, without
  reading private data or writing probe files.
- Explicit `--collection PATH`: opt-in read-only collection inspection. Reuse
  `capture_import.baseline.capture_collection_baseline` before/after the read
  (changed bytes mean UNVERIFIED), reject unsafe files using existing
  `capture_import._filesystem` plain-file/handle checks, validate list-of-dict
  shape and `CoinItem.from_dict` just as load_collection does; do not instantiate
  CoinCollection (which prints and establishes mutable state). Report missing
  first-run storage separately from malformed/unreadable storage. Never emit
  records, notes, filenames, image content, or raw exceptions.
- Explicit `--managed-images PATH` together with collection selection: validate
  referenced-path containment and file presence through existing image path
  rules; never follow unsafe links or modify/delete images. No image decoding
  or uploads by default.
- Persistence/locking: inspect selected directory/lock state without acquiring,
  breaking, deleting, or repairing the live package lock. Mere access flags
  cannot establish writability. Optional `--probe-directory PATH` authorizes a
  bounded disposable subdirectory for atomic write/readback and PackageImportLock
  acquire/release probes. Never use live storage or its live lock as test targets;
  remove only owned probe files. Report cleanup failure safely.
- OCR: bounded local subprocess checks for configured Tesseract --version and
  --list-langs, fixed timeout, no shell, bounded captured output, expected language
  availability. No user images. Missing engine/language is UNAVAILABLE; timeout
  or inability to verify is UNVERIFIED. Do not relay process output verbatim.
- AI: retain UNVERIFIED for configured prerequisites. No credential validation,
  client construction, network checks, or model/schema churn.

Human output: overall summary, then each stable check ID, status, safe message,
and action; explicitly label optional unavailable/unverified capabilities.
JSON v1: {"schema_version": 1, "overall": "ready|degraded|blocked",
"capabilities": {"core": "...", "ocr": "...", "ai": "..."},
"checks": [{"check_id": "...", "capability": "...", "status": "...",
"message": "...", "action": "..."}]}. Enum values are lowercase. Stable order;
no timestamps, paths, environment values, raw subprocess output, or exceptions.
Exactly one JSON document on stdout; argparse errors use stderr.
Exit 0: core ready and every explicitly requested required health check ready
(optional unavailable/unverified may make summary degraded). Exit 1: core or
explicitly requested required check unavailable/unverified. Exit 2: invalid CLI
arguments. Unrequested checks do not cause failure. Missing first-run storage is
not corruption; it cannot prove future writeability without an explicit probe.

Tests: injected runtime results, stdout JSON purity/schema/order, all exit paths,
secret sentinel redaction, missing/corrupt synthetic collection, containment and
symlink rejection, existing lock preservation, disposable probe cleanup/failure,
OCR timeout/nonzero/missing-language responses. Fixtures stay synthetic and temp.
No network, private corpus, automatic repair, lock takeover, schema change,
recovery/journal redesign, installer work, or broad local regression.
