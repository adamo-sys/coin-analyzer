# SEC-003 dependency-management contract

Status: SEC-003-0 documentation deliverable; implementation and owner decisions
remain gated below. This contract does not declare SEC-003 remediated, change
installation behavior, narrow Python support, or grant publication authority.

Evidence baseline: authoritative `main`
`4e785c43fd92932cf1f7e3290b15a9202907295b`, verified against GitHub before
drafting. Existing CI evidence was inspected on 2026-10-22 UTC. Future packages
must reverify their authorized base and refresh evidence when declarations change.

## 1. Authority and ownership

Follow [AGENTS](../../AGENTS.md), [CONTRACT](../agent-ops/CONTRACT.md),
[RUNBOOK](../agent-ops/RUNBOOK.md), [STANDARDS](../agent-ops/STANDARDS.md),
[TESTING](../../TESTING.md), and [SECURITY](../../SECURITY.md). The
[SEC-001/002 report](SEC-001-002-phase1.md#sec-003-separate-read-only-recommendation)
establishes declaration drift, not dependency exploitability.

SEC-003-0 creates only this document. No manifests, locks, source, tests,
workflows, PWA files, frozen baselines, or protected material may change. Only
bounded static documentation checks and independent review run here. No installs,
resolution, regeneration, application tests, audits, or CI triggers are permitted.
The authorized conditional commit is local only; push, PR, and merge are excluded.

The owner approves supported targets, material compatibility changes, risk
exceptions, and each implementation package. A package maintainer owns source
requirements, generated outputs, change rationale, and evidence as one reviewed
unit. An independent reviewer verifies that unit. There is no separate hand-edited
lockfile authority or automatic acceptance through Dependabot/Renovate proposals.

## 2. Authoritative inputs and installation profiles

The root `requirements*.txt` files express direct dependency intent; existing
`-r` inclusions compose profiles. They remain pip-compatible. The
[pyproject](../../pyproject.toml) configures mutmut and declares neither project
dependencies nor `requires-python`. Do not migrate packaging systems in SEC-003.

| Profile | Authoritative input and direct additions | Existing derived output / required treatment |
| --- | --- | --- |
| Core | [requirements.txt](../../requirements.txt): numpy, opencv-python, openpyxl, pandas==3.0.6, Pillow, Flask>=3.1.3,<4, qrcode[pil]==8.2 | [requirements.lock](../../requirements.lock); currently stale |
| Desktop/GUI | [requirements-gui.txt](../../requirements-gui.txt) includes core only | May alias the core lock while evaluated closures are equal; record the alias explicitly |
| Development/test | [requirements-dev.txt](../../requirements-dev.txt) includes core plus coverage, pytest, hypothesis, PyYAML | [requirements-dev.lock](../../requirements-dev.lock); currently stale |
| Optional OCR | [requirements-ocr.txt](../../requirements-ocr.txt) includes core plus pytesseract | No OCR lock exists; needs a reviewed complete closure, not just a pytesseract pin |
| Optional AI | [requirements-ai.txt](../../requirements-ai.txt) includes core plus openai>=3.13.0 | [requirements-ai.lock](../../requirements-ai.lock); currently stale |
| Combined optional use | Core + OCR + AI; also development + OCR and/or AI for feature validation | No combined lock exists; approve a bounded composition strategy before implementation |

Each supported combination must resolve to a complete consistent environment.
Recommended strategy: compile complete profile locks constrained to the reviewed
core versions; compile supported unions together, sharing locks only when equality
is demonstrated. Alternatives are separately named union locks or approved
composable overlays with a verified combined closure. Independent installation of
two locks must not silently replace each other's pins. Choosing output names and
additional files requires SEC-003-1 authorization. Until then, combinations are
documented use cases with unqualified reproducibility, not silently dropped scope.

Tkinter/Tcl/Tk and a usable display are desktop prerequisites outside pip. Ubuntu
may require OS-provided Tk/display support; Windows installer components must be
checked. Optional OCR also needs the Tesseract executable and language data with
recorded versions, origin, and configuration. A successful Python import alone
does not qualify OCR execution. Preserve core startup with OCR and AI absent;
dependency policy must not make provider access, credentials, or network mandatory.

The [dependency explanation](../../DEPENDENCIES.md) is contextual, not another
version authority. Its requests-only-POC statement does not create a supported
profile. Optional external runtimes/observability and experiments without source
manifests are outside these reproducible profiles; do not silently add their SDKs
to core. Any promotion requires feature inventory and explicit scope approval.

## 3. Interpreter and platform compatibility

[README](../../README.md#requirements) recommends Python 3.12 or newer, says CI
verifies 3.12, and reports optional live-provider acceptance on 3.14. Its setup
instructions require the selected executable to report 3.12 or newer.
`coin_analyzer_startup.py` and `runtime_readiness.py` accept Python 3.x >=3.12.
This is positive evidence against treating 3.12 as the exclusive supported minor.
No support promise changes in this package.

Use CPython 3.12 as the initial resolution/planning reference, with the exact
patch/build recorded for every run. A minor-only setup selector is not an exact
interpreter pin. Proposed qualification matrix, pending owner approval:

| Interpreter | Existing evidence | Proposed treatment |
| --- | --- | --- |
| CPython 3.12 | Passing Windows/Ubuntu install and unittest jobs; Ubuntu runtime and AI floor jobs, section 4 | First required qualification lane on both OS targets, for every supported profile/union |
| CPython 3.13 | No explicit 3.13 execution evidence found in current workflows, README, or inspected project documentation | Candidate qualification lane on both OS targets; compatibility unknown, not excluded |
| CPython 3.14 | README provider claim; retained Windows 3.14.6 evidence below | Preserve as a candidate supported lane on both OS targets; bounded Windows success does not qualify every profile or Ubuntu |
| Newer Python 3.x | Bootstrap accepts these versions; no execution evidence found in the inspected sources | Retain the existing broad promise; owner must choose required qualification, an explicitly provisional policy, or an authorized promise revision |
| Older than 3.12 / other implementations | Current bootstrap rejects older versions; no alternate-implementation qualification inspected | No new support claim; changing this boundary requires owner approval |

Retained 3.14.6 evidence includes the synthetic bounded Windows validation in
[first-coin workflow](../agent-ops/first-coin-workflow-2026-10-15.md#validation),
the [Windows CI investigation](../agent-ops/pr410-windows-ci-investigation-2026-10-15.md),
the [SEC-001/002 report](SEC-001-002-phase1.md), and the Python shell-builder use
in [PWA acceptance](../OFFLINE_PWA_POST_MERGE_ACCEPTANCE_2026-10-21.md).
These are retained reports, not fresh runs or proof of complete dependency closure.
PWA shell-builder success tests standard-library Python use, not application SDKs.
No protected worktree or private fixture was entered to corroborate them.

Propose Windows x86-64 and Ubuntu x86-64 as initial native targets based on current
CI; confirm architecture and exact OS image in each future lane. The inspected
jobs use Windows 2025 and Ubuntu 24.04, while `*-latest` selectors can move.
The desktop product remains Windows-oriented; Ubuntu unittest success alone does
not promise Ubuntu GUI operation. Owner must approve precise OS/architecture and
Python/profile coverage before SEC-003-1. Other platforms remain unqualified.

For each proposed lane inspect the chosen distributions' `Requires-Python`,
wheel tags/ABI, dependency metadata, extras, and markers, then prove native clean
installation and applicable synthetic behavior. Focus on numpy/OpenCV/pandas,
Pillow/Tk, pydantic-core/jiter and OCR native prerequisites. Do not infer 3.13/3.14
compatibility from a 3.12 solve or invent metadata floors from successful imports.
Unavailable wheels, source builds, and raised Python/OS minima require an explicit
compatibility decision. Changing README support requires separate authorization.

## 4. Reviewed-version starting evidence and mandatory corrections

Existing [Tests run 39710454473](https://github.com/adamo-sys/coin-analyzer/actions/runs/39710454473)
is for the exact baseline SHA. The aggregate run **failed** in Offline PWA browser;
no overall green baseline is claimed. These individual jobs and installation
steps succeeded:

| Retained job | Interpreter/platform | Installation consumer / outcome |
| --- | --- | --- |
| [Windows unittest](https://github.com/adamo-sys/coin-analyzer/actions/runs/39710454473/job/119600277356) | CPython 3.12.10, Windows 2025 x64 | requirements-dev.txt; installation, boundaries, and unittest succeeded |
| [Ubuntu unittest](https://github.com/adamo-sys/coin-analyzer/actions/runs/39710454473/job/119600277437) | CPython 3.12.15, Ubuntu 24.04 | requirements-dev.txt; installation, boundaries, and unittest succeeded |
| [Runtime Pyright](https://github.com/adamo-sys/coin-analyzer/actions/runs/39710454473/job/119600277469) | CPython 3.12.15, Ubuntu 24.04 | requirements.txt then pyright==1.1.411; installation and bounded check succeeded |
| [AI floor smoke](https://github.com/adamo-sys/coin-analyzer/actions/runs/39710454473/job/119600277285) | CPython 3.12.15, Ubuntu 24.04 | requirements-ai.txt plus openai==3.13.0; SDK/transport checks succeeded without provider calls |

Installation logs record pip 26.2.2 after upgrade. They establish selected versions
and successful execution, not an approved lock, full artifact provenance, or a
complete pristine environment inventory. Windows already contained colorama
0.4.6, click 8.5.0, and packaging 26.3; omit none merely because absent from the
`Successfully installed` line. Ubuntu/Windows platform closures need not match.

| Dependency evidence | Existing locks | Passing CI installation evidence / disposition |
| --- | --- | --- |
| pandas | 3.0.5 in all three | 3.0.6, matching the manifest; mandatory correction unless owner explicitly authorizes changing source intent |
| Flask and qrcode[pil] | Absent in all three | Flask 3.1.3, qrcode 8.2; mandatory complete direct/transitive inclusion |
| OpenAI | AI lock 3.8.0 | 3.13.0, matching the declared minimum; mandatory removal of the below-floor pin |
| Shared existing pins | numpy 2.5.2, Pillow 12.3.0, python-dateutil 2.9.0.post0, tzdata 2026.3 | CI used 2.5.4, 13.0.0, 3.0.0, 2026.5 respectively; evaluate preservation first, do not copy CI wholesale |
| Shared matching pins | opencv-python 5.0.0.93, openpyxl 3.1.5, et-xmlfile 2.0.0, six 1.17.0 | Same selected versions observed; preservation candidates, not a security clearance |
| Dev examples | coverage 7.16.0, hypothesis 6.167.1, iniconfig 2.3.0, pluggy 1.6.0 | CI used 7.16.2, 6.170.5, 2.3.1, 1.7.0; review each difference, including unchanged pytest/PyYAML dependencies |
| AI transport/native examples | httpx2/httpcore2 2.12.0, pydantic 2.13.5, pydantic-core 2.46.5, jiter 0.16.0 | Floor job used 2.16.0/2.16.0, 2.14.1, 2.50.1, 0.17.0; re-evaluate the full OpenAI closure |

The table is a starting comparison, not an exhaustive change ledger. Missing
Flask closure includes blinker, click, itsdangerous, jinja2, markupsafe and
werkzeug in observed installations; qrcode's Windows colorama dependency needs
marker evidence. Do not declare a transitive package unnecessary by inspecting
only the direct manifests or a single OS. OCR and combined closures are absent.
No advisory assessment ran here; mandatory corrections above concern consistency,
not a claim of a known exploitable package.

Controlled update rule: preserve a reviewed pin wherever it satisfies current
source intent, complete metadata, target compatibility, and security gates. Where
old pins lack recorded review, treat them as preservation candidates requiring
review, not trusted versions. Compare candidates against passing CI versions.
If preservation fails, record the exact constraint/advisory/platform reason and
choose the smallest justified correction. Do not use a blanket upgrade or latest
available packages as a default. Review **every added, removed, or changed direct
and transitive distribution**, its reason, provenance, compatibility, and advisory
result; retain a per-package delta ledger in the future package's authorized
evidence. Unchanged pins still require current audit and target qualification.
Material major/minor compatibility changes, Python/OS floors, feature removal,
source builds, index changes, or exceptions require owner approval before adoption.

## 5. Resolver, index, and reproducibility policy

Retain `uv pip compile` and requirements-format outputs. Headers record these
recipes, but no uv version or complete target/index context:

```text
uv pip compile requirements.txt -o requirements.lock
uv pip compile requirements-dev.txt -o requirements-dev.lock --no-python-downloads
uv pip compile requirements-ai.txt -o requirements-ai.lock
```

They are historical recipes, not commands to execute in SEC-003-0. Before the
first future solve, select and record an exact reviewed uv release; also pin the
pip/audit tool environment and its closure. Do not invent the historic generator
version or choose an unspecified latest release. Record exact argv, interpreter
path/build, OS/architecture, resolver flags, input/output Git identities/digests,
constraints, timestamp, index identity, and sanitized effective configuration.
Disable automatic Python downloads; selecting an interpreter is explicit.

Use a reviewed seed of compatible old pins and explicit constraints for preservation
where needed. [uv documentation](https://docs.astral.sh/uv/pip/compile/) states
that an existing output supplies version preferences. Therefore regeneration
into an empty temporary output is not equivalent to regeneration with a reviewed
seed. The recipe must define its seed, not depend on an ambient checkout or cache.
Allow targeted upgrades only with an approved delta; never hide incompatibility
with dependency overrides.

Existing files do not declare an alternate package index. Treat public PyPI over
verified HTTPS as the proposed default, **not proof of historical artifact
origin**. Owner must approve the source policy before solving. Ensure uv and pip
use the same approved logical sources and candidate set: account for environment,
user/system config, proxy/CA policy, mirrors, caches, extra indexes, find-links,
and resolver differences. Do not dump credentials/configuration into evidence.
Reject unexpected sources, editable/VCS/local-path/direct-URL requirements and
prereleases unless specifically reviewed. An authorized mirror must retain
verifiable upstream identity; never mix an unreviewed extra index to fix a solve.

Prefer available wheels for native targets. Any required source build needs
reviewed build backend/dependency closure, toolchain, isolation, source origin and
repeatability evidence. This is a prerequisite to acceptance, not a detail hidden
behind an otherwise pinned runtime lock. Full artifact hashes, retained wheel
bundles, and attestations may be added in SEC-003-3; their absence must be disclosed.
[pip's repeatable-install guidance](https://pip.pypa.io/en/stable/topics/repeatable-installs/)
distinguishes version pinning, artifact integrity, and platform-specific bundles.
Do not claim byte-identical artifacts, offline reinstallability, or identical
future audit results from version pins alone.

## 6. Closure equality, markers, and lock drift

For each approved profile and native target `t`, define:

- `M(t)`: all recursively included direct requirements, requested extras, and
  applicable environment markers from the authoritative inputs.
- `L(t)`: normalized name/version pairs selected by the reviewed lock after
  evaluating markers for the exact interpreter/OS/architecture.
- `I(t)`: installed distribution inventory from a fresh isolated profile
  environment, excluding only explicitly enumerated bootstrap tools.
- `A(t)`: name/version pairs actually submitted for vulnerability lookup, with
  a recorded result for every distribution.

Acceptance requires `L(t)` satisfy `M(t)` and every applicable recursive metadata
requirement, and **`L(t) = I(t) = A(t)`**. Compare normalized distribution names,
exact versions, and origins; retain extras/marker edges separately because an
inventory alone cannot prove them. Bootstrap tools and their transitive closure
must have a separate pinned inventory/audit, not an open-ended exemption. A
bootstrap distribution also required by the application belongs in `L/I/A` and
must satisfy both environments. No extra application packages or missing edges.

Use clean temporary virtual environments; do not validate a developer's existing
environment. A future pip install must not fetch unreviewed transitives to repair
an incomplete lock. Validate the locked closure and install the complete evaluated
set with dependency fetching disabled, then require `pip check` and a complete
inventory comparison. `pip check` alone cannot detect all undeclared extras or
profile omissions. Audit tooling lives outside the application environment, so
installing the scanner cannot mutate the target it is meant to verify.

Preserve `qrcode[pil]` and future explicitly requested extras. Evaluate `sys_platform`,
Python version, architecture and other relevant markers, including Windows-only
dependencies. Prefer one marker-aware lock per profile if pinned uv can represent
all approved lanes and native evidence proves equality. Otherwise use explicit
target locks with an unambiguous consumer mapping. Do not treat a host-generated
lock as universal or remove a conditional dependency because one host omits it.
Owner approval of this strategy precedes lock creation and consumer changes.

Drift detection must cover every input/include, profile/union, and target mapping.
Regenerate with the exact toolchain, approved configuration, and recorded seed in
a disposable path, then compare canonical generated content with the committed
output. Preserve stable headers; permit only explicitly defined non-semantic
normalization such as line endings. Run twice from the same seed to require stable
output and require an unchanged-input regeneration to produce no diff. Separately
validate metadata closure and `L/I/A` equality: a repeatable stale seed can still
omit a direct requirement. Any mismatch, missing lock, missing target, unresolved
marker, or unknown source fails the gate. Do not regenerate merely to silence it.
Index mutation/withdrawal can prevent exact replay; report failure and seek review
rather than silently selecting replacements.

## 7. Vulnerability audits and independent profile reporting

Current [Dependency Audit](../../.github/workflows/dependency-audit.yml) installs
pip-audit 2.10.1 on Ubuntu Python 3.12 and sequentially audits the three existing
locks using `--no-deps`. It does not install those application locks, cover OCR,
prove closure equality, or request `--strict`. A prior step failure can prevent
later profile steps from running. No fresh audit or current clean bill of health
is claimed here.

Future audit enforcement must use an exact reviewed scanner/tool closure, explicit
advisory service, and the **same evaluated package set installed in each lane**.
[pip-audit documentation](https://github.com/pypa/pip-audit#usage) distinguishes
`--no-deps` (no resolution; exact pins required) from `--strict` (collection
failure is fatal). Neither proves transitive completeness; section 6 does.
Validate the selected release's flags and machine-readable output before adoption.
Require strict collection, preserve nonzero exits, and reject skipped/unknown/
unsupported packages, lookup failures, malformed/partial reports, service outages,
missing results and count/set mismatches. Unknown is not zero vulnerabilities.
Do not use `--fix`, broad ignores, `|| true`, success fallbacks, or application
network calls as acceptance mechanisms.

Default security acceptance is no reported known vulnerabilities and complete
coverage of `L(t)`. Any proposed exception requires an owner-approved record with
advisory aliases, affected package/versions/profile/targets, applicability and
exposure evidence, mitigation, accountable owner, expiry/recheck date and removal
condition. Unfixed or disputed advisories are not automatically waived. An
exception permits only its explicit qualified acceptance; report the vulnerability
and exception visibly rather than presenting an unqualified clean result.

Each profile/target produces its own install, closure, drift, audit and behavior
status, even when another fails. Use independent jobs or equivalent always-run
collection with an aggregate gate that fails on any failed, cancelled, missing
or unapproved-skipped required lane. Deduplicate identical evaluated sets only
with an explicit alias and separate visible profile status. Missing OCR tooling
or AI coverage must not be hidden by core success. Report advisory service,
scanner version, lookup timestamp, input digest, covered set and exceptions.
Advisory data changes over time; reproducibility of installation does not freeze
future vulnerability findings.

## 8. CI tools, consumers, and privacy

Inventory for future consumer alignment (no changes here):

| Environment / consumer | Current declaration | Required future treatment |
| --- | --- | --- |
| Tests OS matrix; E7 focused; Mutmut Advisory | requirements-dev.txt; mutmut additionally 3.7.0 | Explicit dev/target lock mapping; separate tool closure where practical |
| Bounded Pyright and advisory Pyright | requirements.txt then pyright 1.1.411 | Application closure verified separately from pinned analyzer/tool closure |
| Property advisory | requirements.txt then unpinned hypothesis | Explicit tested combination, not an unaudited post-install addition |
| Ruff | Standalone ruff 0.16.5 | Independent pinned tooling environment |
| AI compatibility floor | requirements-ai.txt plus openai==3.13.0 | Preserve floor testing alongside reviewed default AI lock; each needs its own verified closure/audit |
| Dependency Audit | Standalone pip-audit 2.10.1 | Scanner closure isolated; audit exact target sets |
| Local README / DEPENDENCIES / setup_dev.ps1 | Installs source .txt; bootstrap upgrades pip and runs tests | Deliberate, documented migration preserving user workflows and interpreter selection |
| pre-commit | Minimum pre-commit 4.6.2; hook refs v6.0.0 and Ruff v0.16.5 | Separate hook environments/version provenance; no implicit application profile |
| CodeQL / Gitleaks | Action-managed analysis/binary environments | Record action SHA and managed-version limits; do not pretend Python application locks cover them |
| Offline PWA browser | Separate Node/npm/Playwright lock, Python stdlib builder, browser/OS packages | Preserve its existing independent contract; no PWA file changes in SEC-003 |

An isolated analyzer environment may include a checked application environment
for imports; its tool packages must be separately accounted for and must not
silently change application pins. Preserve existing required checks and advisory
classifications. Advisory workflow success is not proof that every diagnostic
passed. Branch-protection/settings changes need separate owner authority.

Future network access is limited to approved dependency/advisory metadata and
artifacts. Record sanitized package/tool evidence only: no keys, credential-bearing
URLs, home paths, private index configuration, collection records, backups,
exports, notes, photos, or raw application logs. Tests use synthetic fixtures and
temporary directories. Protected `test_coins` JPEGs remain local-only; do not
read, materialize, upload, or use them for this work. Respect workflow checkout
exclusions and artifact allowlists in TESTING; package tooling does not authorize
new artifacts. Core absence-of-OCR/AI and optional import/transport checks must
avoid provider calls; actual OCR smoke uses synthetic imagery and explicitly
approved native prerequisites. Live AI acceptance is separate and opt-in.

## 9. Security acceptance gates and rollback

SEC-003 implementation acceptance requires all applicable gates, with exact
base/head, commands, results, platform, and retained privacy-safe evidence:

1. Owner-approved target/profile matrix, output layout, source/index policy and
   package scope; README promise and existing features preserved or explicitly
   amended. No unresolved policy decision may be silently selected by an agent.
2. Complete direct/transitive delta review; mandatory corrections from section 4;
   justified preservation/updates and explicit material-change approvals.
3. Recorded exact resolver/interpreter/toolchain and deterministic no-drift replay
   for every profile/target; complete metadata, extras and marker validation.
4. Native clean installation, `pip check`, and `L=I=A` evidence, including aliases,
   supported unions, bootstrap/tool inventories, and any reviewed source builds.
5. Strict, complete audits with zero unapproved findings or coverage gaps; all
   independent required lanes accounted for. No missing lane counted as passing.
6. Privacy-safe offline feature checks for core/GUI, Excel imports, image
   processing, Flask/qrcode consumers, OCR and AI where applicable; preserve the
   AI floor and behavior with optional dependencies absent. Applicable regression
   and static gates remain as specified by TESTING in authorized future packages.
7. Independent review returns PASS or PASS WITH NOTES containing no blockers;
   blocking corrections confirmed against the final snapshot. Current required
   GitHub gates and explicit human authority are prerequisites to any later merge.
8. Reviewed rollback mapping to the previous **coherent** manifest/lock/consumer/
   toolchain set. Test recreation in a fresh environment; do not mutate a user's
   collection or run a dependency downgrade in their existing environment.

Retain previous pins, source identities, target mapping and recipes in Git.
Rollback of a failed proposed reconciliation can restore the pre-package files,
but the already-stale baseline is not a security-approved fallback. Returning to
a vulnerable or inconsistent set requires explicit owner risk disposition and
does not close SEC-003. Version pins without retained artifacts cannot guarantee
reinstall after withdrawal; document that limit until SEC-003-3 or an equivalent
authorized retention policy provides stronger replay evidence.

## 10. Separately authorized implementation roadmap

### SEC-003-1: reconcile source manifests and reviewed lockfiles

**Exact component scope:** root requirements manifests and their reviewed derived
locks for the approved profiles, targets and unions; this contract only as needed
to record approved choices and recipes. Output filenames, evidence paths, and any
new OCR/union/target files must be enumerated in the owner's package authorization.
No consumer, workflow, PWA, production-source or test changes in this package.

**Prerequisites:** owner decisions in section 11; reverified base and baseline CI
evidence; exact resolver/tool versions, approved index policy and privacy-safe
validation environment. Permission to solve/install/audit and run bounded native
checks is required and is not supplied by SEC-003-0.

**Deterministic acceptance:** approved profile/target inventory has no missing
outputs; mandatory drift corrected; every delta reviewed; two same-seed runs and
unchanged-input replay give identical canonical locks; complete metadata closure,
native clean installs, `pip check`, inventories and strict audit coverage prove
section 6 equality on every approved lane. Approved synthetic feature checks pass;
review confirms no unapproved compatibility change. Consumer drift remains
explicitly open until SEC-003-2; this package alone cannot close SEC-003.

**Rollback:** restore the entire package's prior manifest/lock set and discard only
its disposable environments; keep failed evidence. Do not bless stale baseline
locks or alter existing user environments. **Owner gate:** approve exact files,
matrix, compatibility choices, tool/index policy, validation and local/publication
actions separately; review any new material incompatibility before adoption.

### SEC-003-2: align installs, audits, and CI enforcement

**Exact component scope:** Python installation/audit steps in the workflows listed
in section 8, README/DEPENDENCIES/setup_dev.ps1 consumer instructions, and narrowly
scoped drift/equality enforcement tooling and synthetic tests. File list and new
tool/test/evidence paths require explicit authorization. Keep the PWA job and its
Node/browser dependencies unchanged. Do not add application behavior changes.

**Prerequisites:** accepted SEC-003-1 outputs and approved consumer-to-lock mapping;
preserved AI floor strategy; explicit CI/tooling/test and trigger authority. Audit
bootstrap environments and version pins must be reviewed before enforcement.

**Deterministic acceptance:** every supported consumer maps to an approved target
closure; installs use that closure and inventories equal audited sets; each
profile/target reports independently. Synthetic negative cases for manifest drift,
missing transitive edge, marker/extra mismatch, unexpected installed package,
unauditable dependency, advisory outage and failed/cancelled/missing lane make the
aggregate gate fail. Clean unchanged input passes drift checks. All approved
native feature/regression gates pass, with optional-absence and AI floor coverage.
Required current-head GitHub gates pass before any authorized merge; no weakening
of existing gates or privacy policy. Independent reviewer confirms effectiveness
and maintenance cost, rather than just matching command strings.

**Rollback:** restore consumers and enforcement together to the prior mapping;
recreate disposable environments and visibly reopen any resulting SEC-003 gap.
Do not roll back privacy safeguards. **Owner gate:** approve exact edits, CI runs,
settings changes if needed, publication actions, and each merge separately.

### SEC-003-3: optional stronger supply-chain assurance

**Exact component scope:** owner-selected artifact hash generation/enforcement,
SBOM generation and verification, and optionally approved artifact retention and
attestations for Python profiles. Exact files, formats, destinations, retention
and access rules must be approved; no automatic PWA/supply-chain expansion.

**Prerequisites:** accepted SEC-003-1/2 mapping and closure evidence; owner decision
on benefit versus maintenance, native wheel/source-build coverage, distribution
rights, storage cost/privacy, and an integrity/availability threat model.

**Deterministic acceptance:** all artifacts for every approved native target have
verified allowed hashes; missing or changed bytes fail; a clean install using
hash enforcement reproduces the approved inventory; SBOM components/versions
match `L/I/A` without private paths or unrelated packages. If offline replay is
promised, prove it from the authorized retained bundle with network disabled;
otherwise state its absence. Review source-build/build-tool coverage and record
the limits of hashes/SBOMs (neither establishes absence of malicious code).

**Rollback:** atomically restore the prior accepted hash/SBOM/consumer policy,
preserving the section 6 equality and strict audits; retain approved evidence
under its retention policy. **Owner gate:** separately authorize artifacts,
storage/publication and enforcement; this package is optional, not a prerequisite
for accurately reporting bounded SEC-003-1/2 results.

## 11. Owner decisions required before implementation

| Decision | Proposed option / alternatives | Approval boundary |
| --- | --- | --- |
| Python promise and lanes | Qualify 3.12 first and add 3.13/3.14 native lanes; explicitly define treatment of newer 3.x. Alternatively approve a narrower documented guarantee while preserving provisional use | Owner must approve matrix and any README change; no version is silently excluded here |
| OS/architecture and feature coverage | Windows/Ubuntu x86-64 initial targets; distinguish Ubuntu test support from desktop support; select exact supported OS releases | Owner approves coverage and unsupported/unqualified boundaries |
| Lock composition | Full profile locks with shared core constraints and explicitly verified unions; alternative reviewed overlays/target locks | Owner approves file layout, aliases, unions and platform strategy |
| Version reconciliation | Preserve compatible reviewed pins; mandatory consistency corrections; compare observed CI candidates without opportunistic upgrades | Owner approves material compatibility changes and any departure from source intent |
| Toolchain and provenance | Exact uv/pip/scanner and tool closures; public PyPI/verified TLS; reviewed mirror alternative | Owner approves chosen releases, source policy and any required source builds before resolution |
| Audit exceptions | Default no known vulnerabilities or coverage gaps; narrowly scoped, expiring owner risk acceptance if justified | No exception is granted here; each requires explicit approval |
| Stronger assurance | Hashes/SBOM/retention after closure consistency; optional earlier adoption if justified | Separate SEC-003-3 authority, costs, paths and publication policy |

These pending choices are implementation prerequisites, not evidence failures
hidden by this documentation deliverable. Approval to commit SEC-003-0 does not
approve an alternative, authorize SEC-003-1, accept production security, or resolve
the independently failed baseline PWA browser job.
