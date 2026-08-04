# Sprint 19 - Test Builder Policy Stabilization

## Purpose

This document freezes the fourth bounded architecture unit of Sprint 19: test builder policy stabilization for the OCR review pipeline.

This unit is intentionally architecture-only. Its job is to define the policy for shared test-construction helpers before any test-code refactor is authorized. It does not change production behavior, does not introduce dependency injection, and does not create runtime factory objects.

## Scope statement

This unit governs only test-code construction for OCR/review persistence and reconciliation suites.

In scope:

- repeated test helper construction such as `_candidate()`, `_review()`, `_report()`, and similar local fixtures
- helper ownership and reuse rules inside the relevant test modules
- negative-test object construction rules
- readability and coverage preservation rules

Out of scope:

- production factory classes
- dependency injection or runtime wiring changes
- persistence migration logic
- any production behavior change
- any test behavior rewrite beyond helper centralization

## Architectural rule

Test builders are an architecture concern only when they are used to centralize repeated object construction in test code without changing the meaning of the object or the semantics of the assertions that consume it.

A builder may reduce duplication only when it preserves:

- object field intent
- explicit identity semantics
- version semantics
- persistence-envelope boundaries
- negative-test invalidity

## Inventory of repeated test construction patterns

The current repeated test-construction work is expected to live in the OCR/review model, service, presenter, persistence, and reconciliation test modules.

Common repeated local patterns to inventory before refactoring:

- candidate construction helpers
- review decision construction helpers
- report aggregation helpers
- persistence-envelope test payload builders
- invalid-object constructors for negative tests

The architecture policy for this unit must identify the repeated helper functions by module and ensure that they are treated as test-only scaffolding rather than production-domain objects.

## Builder rules

The following rules are required for any shared test builder in this unit:

1. Sensible defaults must be chosen for the common happy-path object shape.
2. Explicit overrides must remain available for targeted test assertions.
3. Builders must not hide identity, version, or persistence semantics.
4. Builders must preserve tuple-compatible identity contracts where those contracts are part of the test behavior.
5. Builders must be able to construct intentionally invalid objects for negative tests.
6. Builders must not silently collapse distinction between:
   - candidate identity
   - review identity
   - persisted envelope identity
7. Builders must keep the object payload readable enough that tests remain clear about what is being asserted.
8. Builders must not remove the need for focused assertions about serialization, validation, or schema versioning.

## Required builder policy outcomes

A shared test builder is valid only when it makes the test intent clearer, not when it hides the semantic shape of the underlying object.

The accepted outcome is:

- one or more shared builder helpers for repeated object construction
- no production change to factories, services, or repository contracts
- the same test object shapes remain easy to inspect and reason about

The rejected outcome is:

- production factory classes moved into test code
- runtime builders replacing domain constructors
- general-purpose “magic object” builders that obscure identity, version, or persistence boundaries

## Non-goals

This document does not:

- define production factory classes
- change dependency injection boundaries
- add runtime builders to application code
- alter any persistence or migration behavior
- change assertion semantics or expected outcomes

## Validation gate for the architecture unit

The architecture-only deliverable is complete when:

- the repeated helper inventory is explicitly listed by test-module ownership
- builder defaults and override rules are documented
- negative-test construction is explicitly allowed
- the document states that builders must preserve identity, version, and persistence semantics
- the unit explicitly forbids production-code refactor or runtime-factory churn

## Freeze note

This document freezes only the test builder policy stabilization unit for Sprint 19.

It does not authorize any production refactor, any runtime builder introduction, or any behavior change. It only establishes the architectural guardrails that the next implementation unit must satisfy.
