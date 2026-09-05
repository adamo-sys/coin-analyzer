# Graphify Sandbox Experiment

## Purpose

Evaluate whether Graphify adds actionable architecture and change-impact signal beyond Coin Analyzer's existing Ruff, Pyright, CodeQL, test suite, repository search, and dependency tooling.

This is an experiment, not an integration decision.

## Guardrails

- Run Graphify locally against a disposable experiment branch/worktree.
- Do not give Graphify write authority over application code, collection data, prompts, models, or configuration.
- Do not install Graphify into Coin Analyzer's runtime or development lockfiles for this experiment.
- Do not enable hosted-model enrichment for the initial pass; prefer deterministic local code extraction first.
- Do not commit generated graph artifacts unless they prove useful enough to justify repository ownership.
- Do not add hooks, MCP wiring, merge drivers, CI jobs, or permanent assistant configuration during the sandbox pass.
- Existing repository gates remain authoritative.

## Baseline

Coin Analyzer already has:

- Ruff linting
- Pyright type checking
- CodeQL advisory analysis
- gitleaks
- Windows and Ubuntu tests
- dependency vulnerability auditing
- repository documentation and architectural guardrails
- deterministic evaluator and Diagnostic Agent evidence

Graphify must therefore provide incremental signal rather than duplicate these controls.

## Questions to answer

1. Does the graph identify high-coupling or high-blast-radius nodes that are not already obvious from repository structure and current diagnostics?
2. Does it surface cross-module dependencies or surprising connections that are actionable?
3. Can it answer multi-hop architecture questions with useful file/symbol paths faster or more reliably than ordinary repository search?
4. Does it reveal test-gap or change-impact information that would improve bounded implementation/review packages?
5. Is the output sufficiently deterministic, local, inspectable, and cheap to regenerate?
6. Would maintaining Graphify introduce meaningful dependency, artifact, workflow, or cognitive overhead?

## Initial experiment

Use the current Graphify CLI as an external tool, not a project dependency.

Initial pass:

1. Install Graphify outside Coin Analyzer's `.venv312` environment.
2. Build a graph from the repository using local deterministic code extraction only.
3. Inspect the generated architecture report and graph statistics.
4. Test a small fixed question set against the graph.
5. Compare findings with existing repository/search/tooling evidence.
6. Record actionable findings, false positives, duplicate findings, runtime, and operational friction.

### Fixed question set

- What are the highest-blast-radius symbols/modules in Coin Analyzer?
- What crosses the GUI/headless boundary?
- What are the strongest unexpected dependencies between otherwise separate subsystems?
- Which tests are structurally closest to the self-improvement/evaluator/diagnostic path?
- If a confirmed-observation contract changes, what appears downstream in the dependency graph?
- Which modules look like bridge nodes whose failure or refactor would affect multiple communities?

## Keep criteria

Keep or integrate Graphify only if the experiment produces at least one repeatable, actionable capability that materially improves one of:

- diagnostic quality
- blast-radius analysis
- architecture review
- test targeting
- bounded remediation scoping
- independent review evidence

and that capability is not already available with comparable effort from existing tooling.

## Reject criteria

Reject permanent integration if the result is primarily:

- a visualization of already-known structure
- noisy or weakly-resolved call/import edges
- findings already covered by Pyright, CodeQL, Ruff, tests, or simple repository search
- output requiring substantial manual interpretation without better decisions
- recurring generated-file churn
- extra hooks, services, credentials, or dependency burden disproportionate to the signal

## Promotion boundary

No Graphify-derived finding changes production behavior by itself. Any proposed code/configuration change must enter the normal guarded flow: explicit remediation package, bounded implementation, focused validation, full required gates, independent review evidence where applicable, and repository-owner promotion authority.
