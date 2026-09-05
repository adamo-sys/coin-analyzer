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

## T2 Local Quality Gate — IN PROGRESS

Adopt pre-commit as a cheap local gate without duplicating authoritative GitHub Actions.

Initial hook set:
- Python AST parsing;
- YAML syntax validation;
- merge-conflict marker detection;
- case-conflicting filename detection;
- oversized-file guard at 1 MiB;
- Ruff checks pinned to the same `0.16.5` version used by CI.

The initial gate is intentionally non-mutating: Ruff runs with `--no-fix`, and whitespace/format rewriting is deferred until the local workflow proves low-friction on Windows.

Install/use locally with pre-commit 4.6.2 or newer:

```text
python -m pip install pre-commit==4.6.2
pre-commit install
pre-commit run --all-files
```

Exit gate: configuration is merged green, the hooks run predictably on the Windows development workflow, and the local commit path remains materially faster than the full regression suite.

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
