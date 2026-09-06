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

## T4 Agent Adversarial Evaluation — COMPLETE / PILOT ACTIVE

Promptfoo now has a local, deterministic, network-free adversarial harness around the frozen self-improvement authority boundaries.

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

Completion reference: PR #118. Any live-model Promptfoo integration remains a separate bounded decision.

## T5 Agent Observability — COMPLETE / PILOT ACTIVE

Arize Phoenix now has an optional local tracing bridge around completed Stage 11 experiment results.

Initial boundary:
- Phoenix is never imported automatically by Stage 11 execution;
- the bridge emits bounded decision metadata only;
- remediation packages, prompts, diffs, evidence text, terminal-reason strings, collection data, credentials, and model outputs are excluded;
- `phoenix.otel.register` is loaded lazily;
- automatic/global instrumentation is disabled;
- Phoenix initialization or export failure is advisory and cannot alter a self-improvement result;
- no Phoenix dependency is added to core runtime requirements or CI.

Completion reference: PR #119. See `docs/PHOENIX_PILOT.md` for the local pilot procedure and expansion gate.

## T6 Mutation Testing — COMPLETE / PILOT ACTIVE

Mutmut is now established as advisory evidence about whether critical safety tests actually detect small behavioral regressions.

Initial target remains intentionally narrow:
- mutate only `reviewer_agent.py`;
- select only `test_reviewer_agent.py` for per-mutant testing;
- copy only the small supporting import boundary required by that test;
- run under Linux/WSL rather than expanding the blocking Windows CI matrix;
- mutate covered lines only during the pilot.

Completion evidence:
- the bounded reviewer target completed successfully under Linux GitHub Actions;
- the first successful run generated 135 mutants, killed 120, and left 15 survivors;
- focused survivor hardening reduced the meaningful set;
- exact survivor diffs identified two genuine Windows drive-relative path gaps in reviewer path validation;
- PR #128 added the regression case `C:drive-relative\path.py`;
- final advisory run `34006677115` eliminated both meaningful path-normalization survivors;
- six residual `review_candidate` survivors remain and were classified as equivalent or low-value diagnostic/control-flow mutations rather than targets for percentage chasing.

The pilot demonstrated useful mutation signal while preserving advisory-only authority. It remains non-blocking and does not modify runtime code, CI authority, or promotion authority.

See `docs/MUTMUT_PILOT.md` for the bounded expansion rules.

## T7 External Browser Research Sandbox — COMPLETE / PILOT ACTIVE

The browser-research trust boundary is frozen before implementation.

Initial policy:
- Playwright MCP is the preferred first implementation candidate;
- public unauthenticated web research only;
- caller-supplied bounded research tasks only;
- browser findings begin as advisory and unvalidated;
- source provenance must be retained;
- browser content is treated as untrusted external input;
- no browser tool may enter the Stage 7 through Stage 11 trust chain;
- no collection/model/prompt/config mutation;
- no autonomous target selection, retries, background monitoring, merge, deploy, release, or promotion authority.

See `docs/T7_BROWSER_RESEARCH_SANDBOX.md`.

The manually invoked Playwright MCP pilot is defined in `docs/T7_PLAYWRIGHT_MCP_PILOT.md` with a pinned external MCP configuration under `tools/browser-research/`. It remains outside core runtime and self-improvement orchestration.

Completion evidence:
- pinned `@playwright/mcp@0.0.80` and `--browser=chrome --isolated` configuration validated;
- MCP Inspector successfully enumerated the Playwright tool surface;
- a bounded public navigation to `https://www.microsoft.com` succeeded and resolved to `https://www.microsoft.com/en-ca/`;
- the returned page title was `Microsoft – AI, Cloud, Productivity, Computing, Gaming & Apps`;
- no tracked repository state changed during the smoke;
- browser-derived evidence remained advisory and `UNVALIDATED` rather than entering any repository or self-improvement authority path.

The initial `example.com` probe failed because the host machine's configured DNS resolver returned NXDOMAIN for that domain while public resolvers resolved it correctly. This was classified as an environmental DNS condition, not a Playwright MCP or repository defect.

## Standing authority boundary

None of these tooling phases grants autonomous target selection, silent collection/model/prompt/config mutation, automatic retries, candidate synthesis, merge, deploy, release, or promotion authority. Repository CI and human merge authority remain mandatory.
