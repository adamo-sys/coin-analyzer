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

The supported Tkinter manager keeps the photo, detection, and optional advanced
identification controls in one vertically scrollable column so collector actions
remain reachable when photo previews exceed the available window height.

### Platform, fixtures, and experiments

- `backup_manager.py` and `sync_backup_engine.py` provide local backup,
  validation, and simulated synchronization workflows.
- `test_coins/` contains uncertain-provenance, local-only inputs retained solely
  for their existing local test role. They are not public benchmark fixtures.
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

### Primary collection load-state contract

Loading the authoritative `data/collection.json` document has exactly three
semantic outcomes:

| State | Meaning | Permitted behavior |
|---|---|---|
| `MISSING` | No authoritative collection file exists. | Initialize a new empty in-memory collection. Normal mutation may create the authoritative file on its first successful save. |
| `VALID` | The authoritative file exists and its complete contents load and validate successfully. | Permit normal read and collection-mutation operations. |
| `INVALID_OR_UNSUPPORTED` | The authoritative file exists but cannot be read, parsed, or trusted as a supported collection document. | Fail closed, preserve the source file unchanged, expose the load failure to the caller and GUI, and prohibit ordinary collection mutation. |

`INVALID_OR_UNSUPPORTED` includes malformed JSON, an invalid root structure,
structurally invalid records, duplicate authoritative item IDs, an unsupported
future schema or version once versioning exists, and any other condition that
prevents the existing authoritative state from being trusted. It must never be
converted into, displayed as, or saved over with an apparently empty replacement
collection.

While this state is active, add, update, delete, and save operations must fail
without rewriting the authoritative file. Diagnostics may describe the failure
but must not repair, normalize, migrate, or otherwise alter the source as a side
effect of loading. Returning to normal operation requires an explicit safe
recovery action followed by a successful load and validation; ordinary mutation
is not a recovery mechanism. A missing file remains categorically distinct from
an unreadable, malformed, invalid, or unsupported existing file.

### Authoritative numismatic record contract

The collection record is type-aware without splitting coins and banknotes into
separate authoritative stores. The following fields are authoritative:

| Field | Supported values and semantics |
|---|---|
| `item_type` | Closed values `COIN` and `BANKNOTE`. A legacy record without the field is interpreted as `COIN`. |
| `disposition` | Closed values `KEEP`, `UPGRADE`, `SELL_TRADE`, and `UNDECIDED`. A legacy record without the field is interpreted as `UNDECIDED`. |
| `identification_status` | Closed values `IDENTIFIED`, `PARTIAL`, and `UNIDENTIFIED`. A legacy record without the field is `IDENTIFIED` only when its existing `country`, `denomination`, and `year` identity fields are all nonblank; it is `PARTIAL` when at least one but not all are nonblank, and `UNIDENTIFIED` when all three are blank. This interpretation never supplies or fabricates a missing identity value. |
| `updated_at` | Optional for legacy records. When present, a normalized UTC RFC 3339 timestamp ending in `Z`. Creating a new record or normally mutating an authoritative record sets it to the mutation time. Loading or read-only use does not synthesize or persist it. An unchanged legacy-origin record may therefore retain an absent `updated_at` after collection-format transition until that record is mutated. |

An explicitly present value for any closed enum must match its vocabulary
exactly. Invalid enum values are authoritative-data errors and place the
collection in `INVALID_OR_UNSUPPORTED`; they are never coerced to compatibility
defaults. The defaults above apply only when the corresponding field is absent
from a valid legacy record.

`item_type` distinguishes numismatic form, not geography. `country` and
`issuer` remain flexible and must not be restricted to Canada. `denomination`
remains flexible text. `year` or other date descriptions must not be constrained
architecturally to a mandatory Gregorian integer for every coin or banknote.
Existing neutral metadata such as `issuer`, `title`, and `reference` remains
valid for either item type. This record contract does not imply automatic
banknote or world-coin recognition.

### Truthful incomplete manual-entry contract

Manual creation and editing must represent the collector's current factual
knowledge without inventing identity values. At the manual-save boundary,
`identification_status` has these semantics:

- `IDENTIFIED` means the saved reliable factual identity is sufficient to
  distinguish the numismatic issue. Ordinary coin or banknote identity may use
  the applicable issuer or country, denomination, and date, year, or series
  fields. A recognized catalogue or reference anchor may instead be sufficient
  for a token, historical issuer, colonial or provincial issue, or another item
  for which ordinary modern-coin fields are not appropriate. No Canada-specific
  field combination is required.
- `PARTIAL` means at least one reliable factual identity attribute is known,
  but the saved facts are not sufficient to identify the issue.
- `UNIDENTIFIED` means no reliable factual identity attribute is known.

Photos, notes, acquisition data, disposition, temporary collector titles, and
similar descriptive or ownership metadata do not by themselves promote an item
from `UNIDENTIFIED`. Placeholder or sentinel text such as `Unknown`, `N/A`, or
an equivalent non-fact is not a reliable identity attribute and must not count
toward status derivation.

For a newly created manual record, the GUI derives `identification_status` from
the factual identity values being saved. It must not use an unrestricted status
selector to create a new record whose explicit status contradicts those facts.
For manual edit/save, the GUI recomputes the status from the then-current factual
identity. Corrected facts may therefore cause any justified transition,
including `UNIDENTIFIED` to `PARTIAL`, `PARTIAL` to `IDENTIFIED`, `IDENTIFIED` to
`PARTIAL`, or `PARTIAL` to `UNIDENTIFIED`. Recomputing status changes only that
status: it does not fabricate, normalize, or silently modify collector-entered
identity fields, and the stable item ID remains unchanged.

A manual creation must contain at least one meaningful collector artifact, such
as a photo, a reliable identity fact, a temporary descriptive title, a catalogue
or reference value, or meaningful notes. Default values, blank fields, and
placeholder identity text do not make a completely empty record meaningful; a
completely empty record is rejected. Acquisition or disposition information is
not identity evidence: when it is present on an otherwise incomplete record, it
does not make that record `PARTIAL` or `IDENTIFIED`.

Recognition and other automation remain advisory. Automation-prefilled values
are reviewed under the same manual-save derivation rule and cannot silently
promote an item to `IDENTIFIED` outside that boundary. Manual save is the
authoritative collector action.

These rules govern new and edited manual saves only. They do not change the
frozen compatibility derivation for a legacy record whose
`identification_status` field is absent, and they do not make an existing V1
record with an explicit, vocabulary-valid but semantically inconsistent status
unloadable. This contract adds no field, schema version, persistence-format
change, Canada-only validation, recognition redesign, browser or media-edit
redesign, grading or valuation logic, or Unit 4 benchmark change.

### Collection format versions

The pre-versioning format is named `LEGACY_V0`: the JSON root is an array of
item objects. `LEGACY_V0` remains a supported read format unless a later
architecture decision explicitly removes it. Its absence of an explicit
version is not interpreted as `MISSING`, malformed, or unsupported.

The current write format is V1, with this closed envelope shape:

```json
{
  "schema_version": 1,
  "items": []
}
```

For V1, the root must be an object containing exactly `schema_version` and
`items`; `schema_version` must be the JSON integer `1`, and `items` must be an
array of valid authoritative item objects with unique, nonblank string IDs. V1
items carry explicit `item_type`, `disposition`, and `identification_status`
values. `updated_at` follows the optional legacy-origin and mutation rules above.
Malformed envelopes, malformed records, duplicate IDs, invalid enum values, and
any explicit `schema_version` other than integer `1` fail closed as
`INVALID_OR_UNSUPPORTED`. A JSON boolean is not an integer version for this
contract.

Unknown item fields outside the documented record contract have no preservation
promise under the current serializer. V1 does not introduce generic unknown-
field round-tripping, and callers must not claim that such fields survive a
write.

### Legacy-to-V1 write transition

Loading or using a `LEGACY_V0` collection read-only never rewrites it. The first
successful authoritative mutation or save after a legacy load writes the
complete collection as a V1 envelope through the existing atomic save boundary.
That transition may materialize the legacy compatibility defaults as explicit
V1 enum fields, but it must not change any existing item ID or fabricate missing
identity data. If serialization or atomic replacement fails, the prior
authoritative file remains recoverable under the existing fail-closed and atomic-
write guarantees.

A first save from `MISSING` writes V1. After a successful transition or V1
creation, subsequent loads and saves remain V1. Every authoritative pathway
that replaces complete collection state, including ordinary save and existing
import/replacement operations, writes the supported V1 envelope. Conditional
item mutation must first validate either `LEGACY_V0` or V1, perform its bounded
record change, and persist the complete result with the same V1 and atomic-write
semantics; it cannot bypass version or item validation.

All existing item IDs are immutable across load, mutation, and the
`LEGACY_V0`-to-V1 transition. Existing `coin_<uuid>` IDs remain byte-for-byte
unchanged. This contract does not select a prefix for newly generated IDs and
does not define a generalized migration engine or any transition beyond
`LEGACY_V0` to V1.

### Local store ownership

| Data | Default owner/path | Notes |
|---|---|---|
| Primary collection | `CoinCollection` / `data/collection.json` | Authoritative local collection document; only the `MISSING` load state may initialize a new empty collection |
| Application/session state | `PersistenceManager` / `collection_data/app_state/app_state.json` | Workflow context and selected report/application state |
| Photo Inbox state | `PhotoInboxManager` / `data/photo_inbox_state.json` | Local runtime queue/grouping state; excluded from Git |
| Confirmed observations | `ConfirmedObservationStore` / `collection_data/app_state/confirmed_observations.json` | Collector-confirmed evidence, atomically written and separate from collection records |

All stores are local-first. Personal records and absolute local paths must not be
added to repository fixtures or documentation. A new persistence mechanism needs
explicit design approval and, when it establishes a lasting architectural
decision, an ADR. See [ADR-001: Local-first architecture](docs/adr/ADR-001-local-first.md).

### Portable collection backup and restore contract

> **Status:** planned architecture contract for Product Unit 5. Existing
> unversioned `BackupManager` packages predate this contract, omit managed photo
> bytes, and must not be represented as complete portable collection backups.

A portable collection backup is a local package whose manifest contains the
explicit JSON integer `portable_collection_backup_version`. Version `1` is the
only format defined here. An absent, non-integer, or unsupported value identifies
a legacy or unsupported package, not version 1, and fails closed at the portable
restore boundary. A package may be called a **complete portable collection
backup** only after version-1 verification succeeds; merely creating a ZIP or
including `data/collection.json` is insufficient.

A complete version-1 package contains the authoritative collection document,
every collection-managed photograph referenced by its records, and the
ownership or provenance material required by the media's existing owner. A
record with no photographs is valid and requires no synthetic image or media
entry. Ordinary-entry media remains owned under
`<collection-directory>/managed_media/ordinary/`. Capture-import media remains
owned by `capture_import`; its collection-record provenance and required import
ownership material, including the applicable `.import-owner.json`, travel with
the referenced media when the existing capture-import contract requires them.
Packaging does not convert capture-import media to ordinary-entry media, change
its provenance, or redesign capture-package recovery.

Before producing a successful package, creation must load and semantically
validate the collection through the existing collection parser, establish the
complete stable-ID roster and authoritative item count, classify every nonblank
photo reference by its existing owner, and verify every required source file.
Missing, unreadable, unsafe, or changing referenced managed media fails creation
closed. An external or otherwise unmanaged photo reference also prevents a
complete-portability claim: creation fails with a local diagnostic identifying
the affected item and reference classification, and must neither omit the
reference nor copy arbitrary external content under an implied ownership rule.
No successful complete package may remain after such a failure.

Portable verification is independent of creation and covers at least:

- the supported package-format version and closed manifest structure;
- safe, unique archive paths with no absolute, drive-qualified, parent-traversal,
  separator-alias, or normalized-name collision;
- the declared byte length and SHA-256 digest of every packaged file;
- semantic validity of the complete collection document under a supported
  collection format, including unique nonblank stable item IDs;
- agreement between the manifest's authoritative item count and the parsed
  collection;
- a complete mapping from every managed photo reference to exactly one verified
  packaged media object; and
- the ownership and provenance records required for each referenced
  capture-import media root.

Backup is observational. Reading either `LEGACY_V0` or V1 for backup must not
rewrite, normalize, migrate, timestamp, or otherwise mutate the live collection
or any source media. A collection or media source that changes while it is being
inventoried or copied invalidates the attempt rather than producing a
mixed-instant package.

Restore has a preflight, staging, publication, and reload boundary. It first
verifies the package, then extracts only declared safe members into a fresh
staging area and repeats collection, roster, media-reference, ownership, size,
and hash validation against that staged tree. It must create and verify a
pre-restore safety artifact before altering an existing authoritative path. For
a valid current collection this is a complete portable backup. For an
`INVALID_OR_UNSUPPORTED` current collection, the safety artifact preserves and
verifies the exact existing authoritative bytes and any safely inventoried
material without claiming semantic validity or automatic restorability. For a
`MISSING` current collection, it records and verifies that no authoritative file
existed. Failure to create or verify the applicable safety artifact aborts the
restore.

All destination collisions are resolved before authoritative publication.
Existing managed files may be reused only when their bytes match the staged
length and SHA-256 exactly. A differing file, unsafe object, ownership mismatch,
or other collision fails closed; restore never silently overwrites unrelated or
differently owned content. Required restored media and ownership material must
be installed and verified before restored collection JSON can become
authoritative.

Collection publication uses the existing supported collection parsing,
serialization, validation, and atomic-write boundary; backup/restore must not
create a second authoritative serializer or write live collection JSON member by
member. Publishing a supported `LEGACY_V0` backup follows the already documented
legacy-to-V1 write transition: the envelope and compatibility defaults may be
materialized, but existing stable item IDs and collector-entered metadata remain
unchanged. V1 values remain V1 values. Any failure before atomic collection
publication leaves the previous authoritative collection unchanged.

Restore cleanup has narrow ownership. It may remove only files created
exclusively by that restore attempt, and only while recorded filesystem identity
still proves that each path names the same created object. It must retain and
report a replaced, pre-existing, differently owned, or identity-ambiguous object.
Pre-existing byte-identical files that were reused are never cleanup targets.
Automatic deletion or garbage collection of unreferenced managed media remains
outside this contract.

After publication, restore reloads the authoritative file through
`CoinCollection`, requires the load state to be `VALID`, and verifies the
expected item count, stable-ID roster, collector-entered values, and availability
of every restored media reference. A successful GUI restore replaces its active
in-memory `CoinCollection` only with that verified reloaded instance before
ordinary add, update, delete, or save operations resume. A reload or comparison
failure is a recovery error and must not permit mutation through a stale or
apparently empty in-memory collection.

This contract does not introduce SQLite or another persistence mechanism, cloud
backup or synchronization, encryption, scheduled or background backup,
recognition or grading behavior, collection-browser behavior, truthful-entry GUI
changes, automatic managed-media garbage collection, Unit 4 benchmark work, or
a capture-package redesign.

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

Ordinary manual entry uses a neutral managed-media ingestion service at the
existing `CoinCollectionApp.add_to_collection()` save boundary. This service is
outside capture-package transactions and supports both `COIN` and `BANKNOTE`
records without changing their shared V1 JSON schema. Before authoritative
collection persistence, it copies every selected source photo into collection-
owned storage using the convention
`<collection-directory>/managed_media/ordinary/<stable-item-id>/<random-token><extension>`.
The item ID is generated once before ingestion and is reused unchanged for the
authoritative record. A safe, bounded source extension is preserved where
reasonable; random destination tokens and exclusive file creation prevent
same-basename collisions and silent overwrite.

Each copy is byte-count and SHA-256 verified from the managed destination before
it may be referenced by an authoritative `ItemPhoto`. The service rebuilds the
photo records with managed paths while preserving role, display order, notes,
and primary status. All copies must verify before the ordinary collection save
begins, so a missing or failed managed copy cannot become an authoritative
reference. Source files are read only and are never modified, moved, or deleted.

The ingestion result records only files newly and exclusively created by that
attempt. If the new-item collection save fails, rollback may remove those files
only while their filesystem identities still match the created objects, then
may remove newly emptied item directories. It must not remove a replaced file,
pre-existing content, a source file, or media owned by another item or workflow.
There is no migration or rewriting of existing photo records.

Reviewed capture/import media remains governed exclusively by `capture_import`,
including its own ownership markers, locking, durability, recovery, and
provenance rules. Ordinary-entry ingestion neither creates capture-package
provenance nor routes manual entry through capture/import semantics.

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

The legacy GUI denomination detector has a separate bounded runtime shell:

```text
CoinCollectionGUI
  -> CoinCollectionApp.run_denomination_detector()
  -> allowlisted legacy recognition capability (maximum one call)
  -> unchanged CoinRecognizer.detect_coin()
  -> exact historical dictionary mapping
  -> advisory GUI suggestions
  -> collector review and existing save flow
```

The shell generates its own opaque scan IDs, routes deterministically, emits
only bounded optional telemetry, and owns no persistence. It does not orchestrate
or import `capture_import`; that mature package retains its independent workflow,
durability, OCR, visual-identification, and review boundaries. See ADR-010.

When the legacy detector returns an incomplete identity, the GUI may expose a
user-controlled handoff to the existing paired-photo visual review action. The
handoff is available only when explicitly labelled FRONT and BACK photos are
attached. It neither invokes a provider automatically nor changes the legacy
orchestration contract: the collector must start the action, accept the existing
external-provider disclosure, review the proposal, and separately confirm any
save. The recognition core remains independent of `capture_import`.

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

When explicitly running legacy local experiments, `test_coins/` may be used in
its existing local-only role. Write generated diagnostics only beneath ignored
`debug_outputs/`, keep optional dependencies lazy, and never send these inputs
to CI, external providers, or public benchmarks.

## Testing Strategy

The OCR and visual benchmark manifests remain task-specific authorities. When
cross-provider comparisons need common metadata, they project validated cases
into the versioned, provider-independent contract in
`capture_import/evaluation_case_contract.py`; the shared contract never loads
images, executes providers, scores results, or persists collection data.

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
