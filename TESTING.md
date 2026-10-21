# Testing

This project uses Python's standard `unittest` test runner. Tests are discovered from root-level files named `test_*.py`.

## Interpreter Requirements

Run tests with the project's configured Python (the interpreter used by `Run_Tests.bat` and CI, with project dependencies installed). The suite imports `cv2` transitively via `coin_collection`; a bare interpreter without project dependencies fails at import time with `ModuleNotFoundError: No module named 'cv2'`.

## Run All Tests

On Windows:

```bat
run_tests.bat
```

Cross-platform:

```bash
python -m unittest discover -s . -p "test_*.py"
```

## Focused OCR Review Boundary and Split Suites

Run the Sprint 19 OCR review package-boundary suite:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_sprint19_ocr_review_package_boundaries
```

Run the split candidate-review modules together when validating the mechanical split family:

```bash
python -m unittest \
  tests.test_desktop_ocr_candidate_review \
  tests.test_desktop_ocr_candidate_review_shortcuts \
  tests.test_desktop_ocr_candidate_review_callbacks \
  tests.test_desktop_ocr_candidate_review_preview
```

Run the bounded legacy-recognition contract, adapter, and integration suites:

```bash
python -m unittest \
  tests.test_legacy_recognition_orchestration \
  tests.test_legacy_coin_recognition_capability \
  tests.test_legacy_recognition_integration
```

## Test Data Isolation

Tests must not read from or write to `data/collection.json`. Shared fixtures live in `test_data/`, and tests copy those fixtures into temporary directories before running.

Current public-safe fixtures:

- `test_data/sample_collection.json`
- `test_data/sample_import.csv`

The ten JPEGs under `test_coins/` are **UNCERTAIN / LOCAL-ONLY** because their
provenance has not been established. Existing local tests may use them, but CI,
external providers, public benchmark manifests, and distributable test artifacts
must not. Crops, contour overlays, OCR diagnostics, and other files under
`debug_outputs/` are generated artifacts: they are ignored by Git.

Temporary files are created with Python's `tempfile` module and removed after each test.

## Continuous Integration

GitHub Actions runs the full test suite on every push and pull request using:

```bash
python -m unittest discover -s . -p "test_*.py"
```

The workflow is defined in `.github/workflows/tests.yml`.
Every checkout in `.github/workflows/*.yml` and `*.yaml` uses non-cone sparse
checkout to exclude all contents of `test_coins/` except `test_coins/README.md`,
and disables credential persistence. This limits worktree materialization; it
does not prove protected Git objects were never transferred. Gitleaks retains
full-history scanning. Historical exposure requires a separate authorized review.

The blocking Tests workflow uploads no artifacts. Quality Advisory permits only
`pyright-report.json`; Mutmut Advisory permits only `artifacts/mutmut-results.txt`,
`artifacts/mutmut-survivor-diffs.txt`, and `artifacts/mutmut-report.json`, generated
by `tools/capture_mutmut_evidence.py`. These advisory reports can contain tool
diagnostics and survivor diffs; directory-wide, image, and unrelated raw-log
uploads are not allowed. CodeQL retains its existing security-analysis reporting.
Checkout exclusions, Git object transfer, and artifact publication are separate
boundaries; an upload path allowlist does not establish report-content provenance.

Run the focused policy suite:

```bash
python -m unittest tests.test_repository_privacy_boundaries
```

It parses every workflow structurally, validates each checkout and artifact upload
against job-specific policy, rejects malformed/duplicate/ambiguous YAML and unsafe
options, and verifies root/nested image exclusions with a temporary synthetic Git
repository. It never uses protected coin images for materialization checks.

## Offline PWA browser CI

The Tests workflow includes the independent `offline-pwa-browser` job, displayed
as **Offline PWA browser**, on every push, pull request and manual dispatch.
Existing Windows/Ubuntu unittest, Ruff, bounded Pyright, security and regression
jobs retain their behavior. Requiring the new check in branch protection is a
separate owner-authorized repository-settings decision.

The job uses Ubuntu 24.04, Node **24.18.0** (including its bundled npm), Python
**3.12.10**, and SHA-pinned checkout/setup actions. `offline_pwa/package-lock.json`
locks Playwright **1.58.2** and its transitive package integrity hashes; `npm ci`
rejects package/lock disagreement. The installed Playwright CLI selects its matching
Chromium revision; it cannot fall back to downloading a different npm CLI package.
No browser-channel override or browser/dependency cache is configured. The hosted
runner image and Ubuntu system packages receive updates, so this is a versioned
runtime/browser setup, not a byte-identical operating-system image.

Exact CI commands, each a separate required step from `offline_pwa/`:

```bash
npm ci --ignore-scripts --no-audit --no-fund
node node_modules/playwright/cli.js install --with-deps chromium
npm run check
npm test
```

The job sets `PWA_PYTHON=python` to use the setup action's interpreter. The builder
uses only Python's standard library; no application Python packages are needed in
this job. Local Windows/macOS runs omit `--with-deps` from the browser installation
and may select the configured project interpreter through `PWA_PYTHON` as described
in [the PWA README](offline_pwa/README.md#tests-and-static-checks).

Expected: every command exits zero, JavaScript syntax checks succeed, and Node's
test summary reports all browser cases passing with zero failures, cancellations
or skips. `npm test` runs the existing `node --test --test-concurrency=1
tests/browser.test.mjs` script without filtering or retries. A test assertion,
missing npm package/browser/Python, failed dependency download, syntax error or
execution error makes its step and job fail. There is no `continue-on-error`,
conditional skip or success fallback. A hung setup/test is bounded by the
15-minute job timeout; cancellation is not a pass.

Dependency acquisition uses the normal Node/Python/npm/Playwright/Ubuntu download
sources. Test execution uses only an ephemeral `127.0.0.1` fixture server, a fresh
temporary shell build, isolated browser contexts and generated synthetic images.
It needs no production services, credentials, devices or real collection data.
The existing suite closes its browser/listener and removes its temporary build
in teardown; a cancelled/timed-out hosted job relies on disposable-runner cleanup.
Checkout retains the protected-image exclusions and disabled credential
persistence. The job inherits `contents: read`, references no secrets, and uploads
no artifacts, screenshots, traces, profiles or raw logs.

Local validation does not establish GitHub-hosted success for the committed head.
P1 does not change PR #429's acceptance classifications or qualify production
authentication, physical devices, recovery, real data or coin-show operation.

## Adding Tests

When adding tests:

1. Use `unittest.TestCase`.
2. Keep test files named `test_*.py`.
3. Put reusable fixture files in `test_data/`.
4. Copy fixture files into a temporary directory before mutating them.
5. Do not modify production files under `data/`.
6. Do not commit generated files from `debug_outputs/`.
