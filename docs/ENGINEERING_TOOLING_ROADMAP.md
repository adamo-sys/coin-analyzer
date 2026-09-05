# Engineering Tooling Roadmap

This track is intentionally separate from the self-improvement stage numbering. It strengthens testing, dependency hygiene, agent evaluation, observability, mutation testing, and external research without expanding agent promotion authority.

## T1 Property-Based Testing — COMPLETE

Hypothesis now probes deterministic self-improvement contracts for cases conventional example tests may miss.

Initial coverage includes:
- remediation-package path normalization and traversal rejection;
- independent reviewer determinism under evidence reordering;
- required-gate fail-closed behavior;
- malformed or scope-broadening changed-file evidence.

Completion reference: PR #115.

## T2 Local Quality Gate — COMPLETE

Pre-commit provides a cheap local gate without duplicating authoritative GitHub Actions.

Initial hook set:
- Python AST parsing;
- YAML syntax validation;
- merge-conflict marker detection;
- case-conflicting filename detection;
- oversized-file guard at 1 MiB;
- Ruff checks pinned to the same `0.16.5` version used by CI.

The initial gate is intentionally non-mutating: Ruff runs with `--no-fix`, and whitespace/format rewriting remains outside the local commit path.

Install/use locally with pre-commit 4.6.2 or newer:

```text
python -m pip install pre-commit==4.6.2
pre-commit install
pre-commit run --all-files
```

Completion reference: PR #116.

## T3 Dependency Automation — COMPLETE / PILOT ACTIVE

Renovate is configured as a proposal-and-evidence tool, not as a promotion authority.

Initial policy:
- use the recommended Renovate baseline;
- keep the Dependency Dashboard enabled;
- allow dependency branches only in a weekly Monday-before-06:00 America/Toronto window;
- group patch and minor dependency updates to reduce PR noise;
- keep major updates separate and require explicit Dependency Dashboard approval before Renovate creates their PRs;
- cap Renovate at five concurrent PRs and two PRs per hour;
- disable automerge globally.

Repository CI and human merge authority remain mandatory for every Renovate PR. The repository's custom `requirements*.lock` files remain outside generic Renovate lock-file maintenance until compatibility with that custom lock scheme is explicitly proven.

Completion reference: PR #117. The first real Renovate cycle remains observational evidence for whether the pilot stays enabled or needs tuning.

## T4 Agent Adversarial Evaluation — IN PROGRESS

Pilot Promptfoo first as a local, deterministic, network-free adversarial harness around the frozen self-improvement authority boundaries.

Initial cases cover:
- attempted merge/deploy/release/promotion authority;
- failed-gate or reviewer bypass;
- scope broadening and unrelated-file mutation;
- prohibited retry/repair/replacement loops;
- autonomous target selection;
- candidate communication or synthesis;
- protected collection/model/prompt/config policy mutation;
- the valid terminal behavior of stopping at human review.

The first provider is deliberately a deterministic local policy oracle rather than a live LLM. This proves the Promptfoo harness, file/provider boundary, and adversarial dataset without API keys, network calls, or new runtime authority. A later slice may point Promptfoo at a real agent/model only after this pilot is stable.

Run locally with Node.js 22.22+ using the pinned pilot version:

```text
npx promptfoo@0.122.2 eval -c evals/promptfoo/promptfooconfig.yaml
```

Exit gate: the local adversarial suite is reproducible and useful, CI remains authoritative, and any later live-model integration is separately reviewed before being allowed to influence self-improvement decisions.

## T5 Agent Observability — PLANNED

Pilot Arize Phoenix as an optional tracing/experiment layer. Core execution must remain valid when Phoenix is absent.

## T6 Mutation Testing — PLANNED

Pilot mutmut against critical safety modules under a suitable environment such as WSL. Mutation testing remains advisory until runtime cost and signal quality are understood.

## T7 External Browser Research Sandbox — PLANNED

Evaluate Playwright MCP only as an external research utility. Browser findings do not become authoritative collection or self-improvement evidence without explicit validation and human review.

## Standing authority boundary

None of these tooling phases grants autonomous target selection, silent collection/model/prompt/config mutation, automatic retries, candidate synthesis, merge, deploy, release, or promotion authority. Repository CI and human merge authority remain mandatory.
