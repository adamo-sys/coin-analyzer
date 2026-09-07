# Identification Specialist Model Output Amendment

Status: APPROVED — minimal synthetic execution contract and strict result parser

## Authorization and limits

This amendment authorizes `identification_specialist_model_output.py` and
synthetic tests building on the approved identification execution seam. It
adds no real provider, network, SDK, credentials, environment lookup, prompts,
confidence, persistence, collection mutation, retry, repair, or orchestration.

The transport request is a MINIMAL SYNTHETIC EXECUTION CONTRACT used only to
establish and test the trust boundary. It is not the final payload contract
for a future real provider. Candidate IDs alone must not be assumed sufficient
for real identification. No images, actual evidence/content payload, private
collection content, prompt content, or provider-specific shape are authorized.
Exposing any actual image/evidence content requires a separate explicit
architecture amendment and authorization.

## Transport request and adapter

A frozen, slotted IdentificationModelRequest contains only schema_version
(the independent model-output protocol string `1`) and candidate_ids (the
original immutable tuple from the validated IdentificationSpecialistRequest).
Case ID, evidence refs, eligibility, and EvaluationCase truth are omitted.
This is an adapter-created projection, not a second domain authority.

IdentificationModelTransport is a synchronous callable from this projection
to raw JSON text. Fakes remain test-local and return explicit synthetic data.
The injected callable is trusted application code, not a sandboxed plugin.

create_model_identification_executor(executor_id, transport) validates the
callable and reuses IdentificationSpecialistExecutor and its provenance
validation. Its adapter validates the original request before invoking the
transport exactly once, then parses the response against that same request.
No execution/verifier/evaluator policy is duplicated. Transport exceptions
propagate unchanged. No failure is converted to abstention, repaired, or retried.

## Raw response protocol

Version `1` requires exactly these JSON object fields:

- schema_version: string `1`;
- candidate_id: caller-authorized candidate string for selection, null for
  abstention;
- abstained: JSON boolean, false for selection, true for abstention.

All fields are mandatory, including candidate_id when null. Unknown fields,
including case_id, evidence_refs, eligibility, expected truth, confidence,
reason prose, and arbitrary metadata, are rejected even if their values happen
to agree with caller inputs. No aliases, alternative fields, or fallback text
are supported. JSON field order and standard JSON escapes are representation
only; decoded candidate strings must match exactly without normalization.

## Strict parsing and identity

parse_identification_model_output(request, raw_response) validates the caller
request and accepts only JSON text (not bytes, mappings, lists, or pre-decoded
objects). Text is bounded to 262,144 characters before decoding. This permits
the existing 16,384-character candidate bound even with JSON surrogate-pair
escaping, with space for the fixed envelope. Excessively padded output is
rejected. Malformed JSON, a BOM, trailing content, non-object roots, duplicate
keys (including escape-equivalent spellings), NaN/Infinity constants, invalid
field types, unsupported versions, and incompatible selection/abstention fail
closed. Deeply nested decoding failures become ValueError; nested payloads
cannot satisfy the flat schema. Invalid Unicode surrogate strings are rejected.

Existing IdentificationSpecialistResult validation supplies the established
result structure and string bounds. A non-null candidate must additionally
belong exactly to request.candidate_ids. No stripping, case-folding, aliasing,
truncation, hashing, or inferred identity occurs. Empty/whitespace-only IDs
remain invalid. Valid caller IDs with significant surrounding whitespace are
preserved exactly, not normalized.

The result's schema version, case identity, and exact evidence tuple are copied
from the validated caller request. Provider output cannot supply these domain
identities. The protocol version is independent of the evaluation schema, even
though both currently use the string `1`.

## Structural validity, policy, and correctness

This model-output parser is stricter about candidate authorization than the
generic execution seam: unknown candidates fail here. The existing generic
seam remains unchanged and can still represent unauthorized diagnostic results.
An authorized candidate may pass parsing despite not being the sole eligible
candidate. Forced selection and abstention likewise remain verifier policy
decisions when structurally valid. The existing evaluator separately compares
against caller-supplied truth, which never enters the transport request.

The returned executor plugs into execute_identification_specialist and
execute_and_compare_identification unchanged. Parsed output remains exactly
IdentificationSpecialistResult. Records, single-case comparison, batch reports,
and tamper harness retain their established meanings and authority limits.

## Acceptance and validation

Synthetic tests cover strict decoding and size limits, exact identity,
non-mutation, immutable projection, injection and single invocation, no retry,
exception propagation, deterministic equality, downstream composition, and
verifier/evaluator independence. Tests inspect the bounded production imports
and projection fields to guard against accidental I/O, truth, or content access.
Run the new suite, the nine existing downstream suites, compilation, available
static checks, and Git whitespace checks. GitHub Actions remains authoritative
for cross-platform regression; no merge is authorized by this amendment.
