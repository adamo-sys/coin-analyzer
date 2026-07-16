# Testing

This project uses Python's standard `unittest` test runner. Tests are discovered from root-level files named `test_*.py`.

## Run All Tests

On Windows:

```bat
run_tests.bat
```

Cross-platform:

```bash
python -m unittest discover -s . -p "test_*.py"
```

## Test Data Isolation

Tests must not read from or write to `data/collection.json`. Shared fixtures live in `test_data/`, and tests copy those fixtures into temporary directories before running.

Current fixtures:

- `test_data/sample_collection.json`
- `test_data/sample_import.csv`
- `test_coins/IMG_3460.jpeg` through `test_coins/IMG_3469.jpeg`

The ten `test_coins` images are stable source fixtures for recognition experiments. Crops, contour overlays, OCR diagnostics, and other files under `debug_outputs/` are generated artifacts: they are ignored by Git and must be regenerated from the source fixtures when needed.

Temporary files are created with Python's `tempfile` module and removed after each test.

## Continuous Integration

GitHub Actions runs the full test suite on every push and pull request using:

```bash
python -m unittest discover -s . -p "test_*.py"
```

The workflow is defined in `.github/workflows/tests.yml`.

## Adding Tests

When adding tests:

1. Use `unittest.TestCase`.
2. Keep test files named `test_*.py`.
3. Put reusable fixture files in `test_data/`.
4. Copy fixture files into a temporary directory before mutating them.
5. Do not modify production files under `data/`.
6. Do not commit generated files from `debug_outputs/`.
