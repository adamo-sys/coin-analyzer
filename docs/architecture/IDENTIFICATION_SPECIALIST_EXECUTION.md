# Identification Specialist Execution Amendment

Status: APPROVED — bounded provider-neutral execution seam

## Scope and authority

This amendment authorizes `identification_specialist_execution.py` and its
synthetic tests. It adds an injectable execution boundary around the existing
deterministic specialist without changing downstream contracts or policy.
Execution success means only that a structurally valid, identity-compatible
result was returned. It grants no verification, correctness, truth, collection
mutation, evidence promotion, or merge authority.

The caller owns request case identity, candidates, eligibility, and evidence.
A separately supplied EvaluationCase owns evaluation expectations; its allowed
candidate IDs and evidence need not equal the request's. Neither source is
rewritten, inferred, normalized, hashed, or manufactured by this seam.

## Executor contract

A frozen, slotted IdentificationSpecialistExecutor descriptor pairs an explicit
executor_id with a synchronous Callable[[IdentificationSpecialistRequest],
IdentificationSpecialistResult]. The ID is a stable non-secret implementation
label, 1–128 ASCII letters, digits, dots, underscores, or hyphens. It is not a
domain identity or proof of implementation authenticity. Callers must not put
secrets in it; syntax validation cannot establish secrecy or authenticity.

DETERMINISTIC_IDENTIFICATION_EXECUTOR binds the existing
run_identification_specialist function directly with the static ID
`deterministic-identification-v1`. This is the adapter: selection and abstention
policy have exactly one implementation. No registry or implementation-kind
field is needed. Alternative implementations supply another descriptor.

The executor is invoked once with the original validated request. Exceptions
propagate; no retries, repairs, fallbacks, or successful failure records exist.
Injected Python code is trusted application code, not sandboxed by this API.

## Boundary validation

execute_identification_specialist validates the request and descriptor before
invocation, then validates the returned specialist result using the existing
result contract. Wrong types, malformed fields, unsupported schema, incompatible
case identity, or evidence refs differing from the request's exact tuple fail
closed before any downstream comparison. Empty evidence is valid only when it
matches the request. No output is repaired or normalized.

Candidate authorization, sole-eligible selection, and required-abstention policy
remain exclusively verifier decisions. Structurally valid unauthorized or wrong
candidates, forced selection, and forced abstention can pass this boundary and
reach the existing verifier and independent evaluator. The seam never creates
such candidates itself. The existing verifier and tamper harness retain their
ability to diagnose evidence tampering directly; this stricter execution gate
does not change those APIs.

## Immutable records and composition

IdentificationSpecialistExecution stores only executor_id and the original
specialist_result object. Its validate(request) checks the boundary invariants.
There are no timestamps, random IDs, derived IDs, provider settings, or secrets.

execute_and_compare_identification validates the separate evaluation case and
its case identity before execution. It calls the execution boundary, then
compare_identification_verification_and_evaluation unchanged. It returns a
frozen, slotted IdentificationSpecialistExecutionReport containing execution
and comparison. Both retain the original result; no truth is passed to the
executor. Equal deterministic inputs and implementation labels yield equal
records and reports.

Report validate(request, evaluation_case) validates execution, validates stored
comparison structure, and recomputes the existing comparison to reject forged
result/verifier/evaluation composition. It does not rerun the executor or attest
that a claimed executor actually ran. The caller must supply the original
authoritative inputs; the report is not self-authenticating.

## Exclusions and validation

No real models/providers, network calls, prompts, parsing, confidence semantics,
collection persistence, GUI, retry/repair, routing, async, or orchestration are
introduced. Future provider implementations require separate authorization.

Acceptance tests use synthetic IDs and references only. They prove deterministic
reuse, exact preservation, immutability, injection, non-mutation, independent
policy/correctness outcomes, early contract rejection, and forged-report
rejection. Focused tests precede all eight existing specialist/evaluation
regression suites, compilation, available changed-surface static checks, and
Git diff checks. GitHub Actions remains the authoritative cross-platform gate.
