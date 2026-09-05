# Engineering Tooling Roadmap

This track is intentionally separate from the self-improvement stage numbering. It strengthens testing, dependency hygiene, agent evaluation, observability, mutation testing, and external research without expanding agent promotion authority.

## T1 Property-Based Testing — IN PROGRESS

Use Hypothesis to probe deterministic self-improvement contracts for cases conventional example tests may miss.

Initial targets:
- remediation-package path normalization and traversal rejection;
- independent reviewer determinism under evidence reordering;
- required-gate fail-closed behavior;
- malformed or scope-broadening changed-file evidence.

Exit gate: focused property tests are merged, stable, and green in authoritative CI without material runtime or flakiness regressions.

## T2 Local Quality Gate — PLANNED

Use pre-commit for cheap local checks such as Ruff, whitespace/EOF hygiene, and YAML validation. Do not put the full repository regression suite in the commit path.

## T3 Dependency Automation — PLANNED

Pilot Renovate with a Dependency Dashboard, grouped patch/minor updates, separate major updates, scheduled lockfile maintenance, and no dependency automerge.

## T4 Agent Adversarial Evaluation — PLANNED

After Stage 11 runtime is stable, pilot Promptfoo against scope broadening, failed-gate bypass, fabricated evidence, prohibited retries, malformed evidence, and attempted promotion-boundary violations.

## T5 Agent Observability — PLANNED

Pilot Arize Phoenix as an optional tracing/experiment layer. Core execution must remain valid when Phoenix is absent.

## T6 Mutation Testing — PLANNED

Pilot mutmut against critical safety modules under a suitable environment such as WSL. Mutation testing remains advisory until runtime cost and signal quality are understood.

## T7 External Browser Research Sandbox — PLANNED

Evaluate Playwright MCP only as an external research utility. Browser findings do not become authoritative collection or self-improvement evidence without explicit validation and human review.

## Standing authority boundary

None of these tooling phases grants autonomous target selection, silent collection/model/prompt/config mutation, automatic retries, candidate synthesis, merge, deploy, release, or promotion authority. Repository CI and human merge authority remain mandatory.
