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
The CI checkout excludes `test_coins/`, and CI does not upload separate raw-log
or image artifacts.

## Adding Tests

When adding tests:

1. Use `unittest.TestCase`.
2. Keep test files named `test_*.py`.
3. Put reusable fixture files in `test_data/`.
4. Copy fixture files into a temporary directory before mutating them.
5. Do not modify production files under `data/`.
6. Do not commit generated files from `debug_outputs/`.
