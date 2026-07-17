# Coin Analyzer Architecture

> **Baseline:** current implemented repository, reconciled 2026-07-16
> **Status:** living description of the system as it exists
> **Scope:** supported desktop collection manager, its local data stores, reusable engines, selected workspace integrations, and clearly isolated experiments

This document describes implemented structure. Desired rules for future changes are
listed separately under [Dependency Direction and Guardrails](#dependency-direction-and-guardrails);
they must not be mistaken for coupling that has already been removed.

## System Context

Coin Analyzer is a local-first desktop application for coin and banknote collectors.
It manages a user-owned collection, photos and evidence; runs deterministic,
explainable analysis; and supports deliberate import, export, backup, and review
workflows. Core collection work remains usable without an account, cloud service,
or live provider.

The supported GUI entry point is:

```text
coin_collection_gui.py -> CoinCollectionGUI -> Tk main loop
```

`main.py` launches `gui.py`, an older folder-analysis prototype. That path remains
in the repository as legacy/experimental code and is not the supported collection
manager described by the user guide.

## Current Implemented Structure

```text
CoinCollectionGUI
  |-- directly owns collection entry, editing, import/export, and many tool dialogs
  |-- directly invokes some workflow and intelligence engines
  `-- uses CollectorWorkspace for selected unified panels and workflows
          |
          `-- lazily composes existing engines and returns report DTOs

Workflow/orchestration modules
  |-- coordinate deterministic intelligence engines and domain models
  `-- Ask My Collection validates model plans and invokes read-only tools

Domain and local state
  |-- CoinItem / ItemPhoto / CoinCollection
  |-- app-state and workflow stores
  `-- repository-relative fixtures and optional experimental outputs
```

The GUI is therefore a legacy-integrated presentation/controller layer, not a
display-only shell. `CollectorWorkspace` is a useful unified service layer for
selected panels, but it is not the exclusive dependency of the GUI. New work
should reduce unnecessary coupling when doing so serves an approved user-facing
change; this document does not claim that separation is already complete.

## Major Modules and Ownership

### Domain and persistence

| Module | Implemented responsibility |
|---|---|
| `coin_collection.py` | `CoinItem`, item-owned `ItemPhoto` metadata, collection CRUD, backward-compatible JSON loading, CSV import/export, and collection analysis entry points |
| `atomic_json.py` | Atomic whole-document JSON replacement used by the primary collection and confirmed-observation store |
| `persistence_manager.py` | Broader application/session state, validation, import/export, and backup integration |
| `photo_inbox.py` | Incoming-photo grouping workflow and its local state |
| `confirmed_observations.py` | Durable collector-confirmed outcomes for later offline evaluation; it does not automatically retrain or alter recognition engines |
| `photo_vault.py` | Metadata-only photo records, links, coverage, and integrity reporting |
| `session_context.py` | Loaded workbook and WANT_LIST context shared by selected workflows |

### Intelligence and advisory engines

Representative modules include:

- `collection_intelligence.py`, `collection_quality.py`, and
  `collection_integrity.py` for collection analysis;
- `acquisition_workflow.py`, `deal_hunter.py`, `opportunity_engine.py`, and
  `market_intelligence.py` for local, explainable acquisition guidance;
- `ai_grading_assistant.py` for deterministic advisory grading guidance;
- `image_assessment.py` for deterministic photo-quality and downstream-readiness
  assessment;
- `canadian_reference_provider.py` for provider contracts, local/manual
  providers, validation, aggregation, provenance, and conflict reporting; and
- `connected_data.py` for deterministic cross-references among existing local
  records and workflow context.

These engines advise. Collection state changes only through an explicit workflow
or collection-management action.

### Workflow and orchestration

Representative modules include `batch_processing.py`,
`smart_phone_cataloguer.py`, `collection_assistant.py`,
`collector_workflows.py`, `collector_workflow_integration.py`,
`mobile_collection_entry.py`, and `photo_capture_workflow.py`. They coordinate
existing models and engines, prepare reviewable results, and should not silently
create authoritative collection facts.

### Workspace and presentation

| Module | Implemented responsibility |
|---|---|
| `collector_workspace.py` | Lazy composition, caching, lifecycle, and report DTOs for selected dashboard, workflow, data-safety, Connected Data, Image Assessment, and Canadian-reference surfaces |
| `coin_collection_gui.py` | Supported Tkinter collection manager and controller for collection mutation, dialogs, reports, workspace panels, and tool entry points |
| `grounded_collection_assistant.py` | Dependency-free assistant contracts, strict read-only tool registry, bounded evidence, orchestration, and grounded-response validation |
| `openai_collection_assistant.py` | Optional OpenAI Responses structured-output adapter; imported only when explicitly configured |
| `gui.py` / `main.py` | Older experimental folder-analysis GUI and launcher |

### Platform, fixtures, and experiments

- `backup_manager.py` and `sync_backup_engine.py` provide local backup,
  validation, and simulated synchronization workflows.
- `test_coins/` contains stable source fixtures used by recognition and
  experiment tests.
- `extract_date_regions.py`, `year_ocr_experiment.py`,
  `template_matching_year.py`, and `label_years.py` are research utilities, not
  supported application workflows.
- `debug_outputs/` contains generated, ignored diagnostics. Output ordering,
  locations, filenames, and artifact counts can be predictable without promising
  byte-identical images across OpenCV versions.
- `pytesseract` and the Tesseract executable remain optional experiment
  dependencies and are not required by normal application startup.

## Subsystem Characteristics

| Subsystem | Advisory | Persistent | Workspace-integrated | Experimental |
|---|:---:|:---:|:---:|:---:|
| Primary collection management | No | Yes | Collection items are consumed | No |
| Connected Data | Yes | No new store | Yes | No |
| Image Assessment | Yes | Reports may be included in app state | Yes | No |
| Photo Inbox | Review-driven | Yes | No; the GUI owns this workflow directly | No |
| Canadian reference providers and aggregation | Yes | Providers may read local reference data; aggregation is not a collection store | Yes | No |
| Confirmed observations | Evidence only | Yes | No; currently written by the collection GUI | No; it is a future evaluation foundation, not a learning pipeline |
| Ask My Collection | Yes; deterministic tools are authoritative | Session display only; no chat store | Uses a read-only `CollectorWorkspace` collection snapshot | No; optional cloud provider |
| OCR and template-matching experiment scripts | Yes | Generated outputs only | No | Yes |

“Persistent” means the subsystem owns or participates in local saved state; it
does not imply that its output becomes an authoritative `CoinItem` field.

## Collection Model and Persistence Flow

```text
GUI or import boundary
  -> backend normalization and validation
  -> CoinItem
       |-- legacy scalar fields
       |-- ItemPhoto list plus legacy image_path compatibility
       `-- optional acquisition fields
             |-- Decimal component values
             `-- read-only derived total_cost
  -> CoinCollection
  -> atomic_json.write_json_atomically(...)
  -> local data/collection.json
```

`CoinItem.from_dict()` accepts legacy records with absent optional fields.
`ItemPhoto` provides structured photo roles, primary selection, notes, and stable
display order while preserving compatibility with legacy `image_path` records.

Acquisition money uses `Decimal`; `total_cost` is derived from purchase price,
shipping, buyer's premium, and tax. If all four components are absent, the total
is `None`; otherwise absent components count as zero. Acquisition fields remain
optional and blank values are omitted where supported by collection
serialization. See:

- [ADR-002: JSON over SQLite](docs/adr/ADR-002-json-over-sqlite.md)
- [ADR-003: Decimal money](docs/adr/ADR-003-decimal-money.md)
- [ADR-004: Derived acquisition totals](docs/adr/ADR-004-derived-acquisition-totals.md)
- [ADR-005: Portfolio financial comparability](docs/adr/ADR-005-portfolio-financial-comparability.md)

The primary collection file is local runtime data, excluded from Git, created on
the first successful save, and backed up independently by the collector.

### Local store ownership

| Data | Default owner/path | Notes |
|---|---|---|
| Primary collection | `CoinCollection` / `data/collection.json` | Authoritative local collection document; missing file means an empty collection |
| Application/session state | `PersistenceManager` / `collection_data/app_state/app_state.json` | Workflow context and selected report/application state |
| Photo Inbox state | `PhotoInboxManager` / `data/photo_inbox_state.json` | Local runtime queue/grouping state; excluded from Git |
| Confirmed observations | `ConfirmedObservationStore` / `collection_data/app_state/confirmed_observations.json` | Collector-confirmed evidence, atomically written and separate from collection records |

All stores are local-first. Personal records and absolute local paths must not be
added to repository fixtures or documentation. A new persistence mechanism needs
explicit design approval and, when it establishes a lasting architectural
decision, an ADR. See [ADR-001: Local-first architecture](docs/adr/ADR-001-local-first.md).

## Representative Data Flows

### Collection mutation

```text
User action in CoinCollectionGUI
  -> backend validation
  -> CoinCollection add/update/delete
  -> atomic save
  -> GUI refresh
```

Validation must complete before an existing record is mutated. Reports,
dashboards, and advisory engines do not independently write collection records.

### Photos, assessment, and OCR

```text
ItemPhoto / Photo Inbox / Photo Vault metadata
  -> deterministic Image Assessment
  -> advisory readiness and issues
  -> optional review or OCR/recognition workflow
  -> collector confirmation before authoritative collection mutation
```

OCR and recognition experiments exist, and the application performs deterministic
image-quality assessment. Pixel-derived identification, grade, and attribution
are not authoritative collection facts without collector review. Experimental
scripts remain isolated from core startup and core dependency requirements.

### Canadian references

```text
ReferenceQuery / ReferenceFilters
  -> local or manual ReferenceProvider implementations
  -> ReferenceProviderAggregator
  -> normalized claims, provenance, validation, and conflicts
  -> CollectorWorkspace report
  -> read-only Canadian References GUI
```

External providers may be added later through explicit adapters, but the local
core must continue to degrade safely when external services are unavailable.

### Connected Data and workspace

```text
Existing collection and workflow context
  -> CollectorWorkspace lazy engine creation
  -> selected engine or ConnectedDataEngine query
  -> report DTO cached in that workspace instance
  -> GUI rendering
```

`CollectorWorkspace.refresh()` clears report caches while preserving initialized
engine instances. It keeps a reference to collection items rather than creating a
second collection store.

### Ask My Collection

```text
Standalone question
  -> optional LanguageModelAdapter creates a structured query plan
  -> local schema and allowlist validation (one bounded repair attempt)
  -> ReadOnlyAssistantToolRegistry
       |-- inventory queries over a CollectorWorkspace item snapshot
       |-- existing CollectionIntelligenceEngine
       `-- existing PortfolioPerformanceEngine
  -> bounded, sanitized, deterministically ordered evidence
  -> optional model explanation plus deterministic verified facts
  -> session-only GUI response and expandable evidence
```

The planning call receives no collection records. The explanation call receives
only allowlisted tool output with row and field limits. Raw `CoinItem` objects,
notes, images, absolute paths, credentials, and local state files never enter the
provider payload. Tk provider calls run on a worker that writes to a queue; Tk
polls the queue on its own event loop. The assistant has no mutation or
persistence tool. See [ADR-006: Grounded collection assistant](docs/adr/ADR-006-grounded-collection-assistant.md).

## Representative Public Surfaces

The supported application surface is `CoinCollectionGUI`. Representative
`CollectorWorkspace` methods include:

- dashboard, inbox, collection-summary, workflow, and data-safety reports;
- Connected Data, Image Assessment, and Canadian-reference reports;
- advisor and workflow access;
- lazy report generation and export; and
- lifecycle inspection and cache refresh.

This list intentionally describes capabilities rather than duplicating every
method signature. Source and focused tests remain authoritative for exact APIs.

## Dependency Direction and Guardrails

The following are rules for new changes, not claims that all legacy coupling has
already been removed:

- Keep validation and business rules in backend models or engines. GUI helpers
  should collect input, delegate validation, and present results.
- Reuse existing models and engines before adding parallel concepts.
- Keep workflow modules focused on orchestration; do not duplicate engine logic.
- Avoid circular imports. A workflow may compose engines; lower-level models
  should not depend on GUI modules.
- Keep `CollectorWorkspace` focused on composition, caching, and report DTOs.
  Do not add unrelated business rules merely to route a GUI feature through it.
- Do not create a second authoritative collection representation or silently copy
  collection state into a new store.
- Preserve backward compatibility for optional persisted fields and imports unless
  an approved migration explicitly changes the contract.
- Do not introduce a persistence mechanism, network dependency, background job,
  or cloud authority without explicit design review and appropriate failure,
  privacy, ownership, and migration policies.
- Deterministic analysis may advise; uncertain or pixel-derived results require
  review before collection mutation.
- Optional model adapters must degrade safely, keep credentials out of local
  stores, and preserve deterministic tools as the authority for numeric and
  collection-specific facts.

## Extension Points

### Workspace-integrated capability

1. Confirm that an existing model or engine cannot provide the capability.
2. Define a stable report DTO or provider contract at the appropriate boundary.
3. Add lazy workspace composition only when a unified panel or workflow needs it.
4. Add focused engine/workspace tests and headless GUI integration coverage.
5. Perform manual Tk acceptance testing for interactive behavior that automation
   cannot reliably validate.

### Reference provider

Implement the `ReferenceProvider` contract, declare capabilities and source
identity, return normalized records with provenance, and verify aggregation,
validation, conflict handling, and unavailable-provider behavior. A provider must
not become a hidden requirement for local core operation.

### Import, export, or persistence change

Reuse `CoinItem` and existing normalization boundaries. Preserve older files and
blank optional values. New authoritative storage or a costly-to-reverse format
decision requires approval, compatibility tests, and normally an ADR.

### Experimental image work

Use stable fixtures from `test_coins/`, write generated diagnostics only beneath
ignored `debug_outputs/`, keep optional dependencies lazy, and do not change
supported recognition behavior as a side effect of experiment maintenance.

## Testing Strategy

- **Backend unit tests** cover normalization, validation, calculations,
  serialization, persistence failure modes, and backward compatibility.
- **Engine and integration tests** cover deterministic analysis, provider
  aggregation, orchestration, and cross-module contracts.
- **Grounded-assistant tests** use fake adapters to cover plan/tool schemas,
  evidence and privacy limits, exact engine agreement, prompt-injection data,
  failure handling, evaluation metrics, and non-blocking GUI helpers without
  network calls.
- **Focused workflow tests** exercise import/export, collection mutation,
  acquisition, photo, reference, and observation paths with temporary data.
- **Headless GUI/helper/layout tests** cover presentation helpers, delegated
  validation, layout contracts, and selected GUI/workspace integration without
  requiring routine interactive windows.
- **Manual interactive Tk acceptance tests** remain necessary for discoverability,
  resizing, disclosure behavior, keyboard/focus behavior, and platform-specific
  rendering.

Tests must use temporary directories or sanitized fixtures and must never read or
mutate live `data/collection.json`. The durable commands and fixture conventions
are in [TESTING.md](TESTING.md).

## Engineering and Release Governance

[The Engineering Playbook](docs/ENGINEERING_PLAYBOOK.md) is the normal authority
for inspection, approval gates, implementation, verification, documentation, and
commit scope. Lasting architectural decisions are recorded as individual files in
`docs/adr/`, following the ADR process defined by the playbook.

The detailed [release checklist](RELEASE_CHECKLIST.md) and historical
[release-governance process](project_docs/release_prompts/RELEASE_GOVERNANCE.md)
remain relevant when preparing an official tagged release. Their historical phase
structure does not replace the playbook for ordinary contributions. Pushes, tags,
and publication always require explicit authorization.

## Maintenance Rule

Update this document when a change alters a durable ownership boundary, supported
entry point, authoritative data flow, persistence mechanism, or extension
contract. Prefer stable responsibilities and links to ADRs over release-specific
method inventories, module counts, or test totals.
