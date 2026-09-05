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

## Execution record

Graphify 0.9.54 was installed with `uv tool install graphifyy`, outside `.venv312` and outside the repository lockfiles.

The deterministic local baseline used:

```text
graphify extract . --code-only --no-cluster
```

Result:

- 618 code files scanned
- 382 non-code files deliberately skipped by `--code-only`
- 14 unclassified files skipped
- 18,621 nodes and 57,838 edges written on the initial extraction
- no hosted-model/LLM extraction
- generated `graphify-out/` remained untracked and was deleted after the experiment
- no hooks, MCP integration, assistant configuration, CI wiring, or repository dependencies were added

## Findings

### 1. Architectural hubs: useful

`graphify god-nodes --top 20` surfaced plausible high-coupling symbols including `CoinCollectionGUI`, `CoinItem`, `CollectorWorkspace`, `CoinCollection`, `OCRMetadataReport`, `OCRFieldCandidate`, `MarketAwarenessEngine`, `ProcessingPipeline`, `ImportWorkflow`, `ConfirmedFieldObservation`, and `ConfirmedObservationSet`.

This is useful as a rapid architecture/blast-radius orientation mechanism, although hub ranking alone is not sufficient justification for permanent integration.

### 2. Confirmed-observation impact analysis: useful but noisy

`graphify affected "ConfirmedFieldObservation" --depth 2` found a broad downstream surface spanning canonicalization, compatibility, field-intelligence evaluators, mapping, collection-change planning/mutation, and their tests.

The signal was real, but a shared contract produced hundreds of lines of output. Broad `affected` queries therefore require deliberate symbol/depth selection and should not be treated as a concise remediation package by themselves.

### 3. Cross-subsystem dependency: verified true positive

An undirected path query reported a direct relationship:

```text
CollectionFieldChangeProposal --uses [INFERRED]--> ConfirmedFieldObservation
```

`graphify explain "CollectionFieldChangeProposal"` located the edge at `collection_management/workflow_collection_change_plan_models.py:L161`.

Manual source inspection verified the relationship: `CollectionFieldChangeProposal.source_observation` is explicitly typed as `ConfirmedFieldObservation`.

This is a true-positive cross-boundary dependency between collection-management planning and the confirmed-observation contract.

### 4. Focused-test discovery: strongest result

For bounded functions, reverse impact analysis produced concise, directly useful test targeting.

`graphify affected "assess_confirmed_observation_field_intelligence" --depth 2` concentrated on the field-intelligence orchestrator tests.

More importantly, `graphify affected "assess_mintmark" --depth 2` traced a leaf evaluator upward to:

- the field-intelligence orchestrator
- the leaf evaluator's direct test module
- orchestrator tests exercising the integration path

This is actionable incremental signal for bounded implementation packages: it can help select focused tests before the full regression suite while preserving the repository's existing gates as authoritative.

### 5. Central pipeline blast radius: useful

`graphify affected "ProcessingPipeline" --depth 1` surfaced production composition/execution consumers plus the relevant pipeline, OCR, image-processing, cancellation, event-ordering, handoff, and workspace integration tests.

For a central symbol, depth 1 remained interpretable enough to support pre-change scoping.

### 6. Natural-language graph query: weak/noisy

`graphify query "What code is affected if ConfirmedFieldObservation changes?" --budget 800` expanded to 806 nodes, selected multiple starting nodes, and truncated to 18 displayed nodes.

This was materially worse than symbol-specific `affected`, `path`, and `explain` operations. The natural-language query interface should not be relied upon for deterministic change-impact evidence in the current repository.

### 7. Directed-path semantics require care

A directed path from `ConfirmedFieldObservation` to `CollectionFieldChangeProposal` was not found, while the undirected query immediately exposed the one-hop `uses` relationship. Users/agents must understand edge direction before interpreting a missing directed path as absence of dependency.

## Assessment against keep criteria

Graphify met the keep threshold for an **optional local engineering aid**. Its strongest repeatable capability is dependency-aware blast-radius and focused-test discovery for bounded symbols. This can improve Diagnostic Agent/Codex planning and independent review scoping in a way that Ruff, Pyright, CodeQL, vulnerability auditing, and the test suite do not directly summarize.

It did **not** justify permanent runtime/development integration, generated-artifact ownership, CI wiring, hooks, MCP configuration, or assistant-specific repository configuration.

## Decision

**KEEP — optional/local only.**

Recommended use:

- pre-change blast-radius analysis
- focused-test discovery
- architecture review of high-coupling symbols
- verification of cross-subsystem dependency paths
- supporting evidence for bounded Diagnostic Agent/Codex remediation packages

Do not use Graphify as:

- an authoritative correctness gate
- a replacement for focused tests or full regression
- an autonomous code/configuration changer
- a source of production changes without manual/source verification
- a reason to commit `graphify-out/`

Prefer deterministic symbol-specific commands such as `god-nodes`, `affected`, `path`, and `explain`. Treat broad natural-language `query` results as exploratory only unless independently verified.

## Operational policy

Graphify remains externally installed through `uv` and outside project dependency locks. Generated `graphify-out/` is disposable local evidence and should be deleted after use unless a future, separately approved experiment demonstrates a repository-owned artifact is necessary.

No Graphify hooks, watchers, merge drivers, MCP wiring, CI jobs, or Codex/assistant configuration are approved by this experiment.

## Promotion boundary

No Graphify-derived finding changes production behavior by itself. Any proposed code/configuration change must enter the normal guarded flow: explicit remediation package, bounded implementation, focused validation, full required gates, independent review evidence where applicable, and repository-owner promotion authority.
