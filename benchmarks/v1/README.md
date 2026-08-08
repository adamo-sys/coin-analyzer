# OCR Benchmark v1

Benchmark v1 is a fixed baseline, not a training set. Do not remove difficult
cases or replace images after observing results. Add a new version when the
dataset contract or cases change.

Run the real production OCR and persistence paths from the repository root:

```powershell
python -m capture_import.evaluation_cli benchmarks/v1/manifest.json `
  --exercise-persistence `
  --json artifacts/benchmark-v1-report.json `
  --summary artifacts/benchmark-v1-summary.txt
```

The Python `pytesseract` package and the native Tesseract executable must both
be installed and discoverable. A missing executable is reported as an
infrastructure failure and is excluded from accuracy and latency denominators;
it is never converted into a zero-accuracy OCR result.

The source images were obtained from Wikimedia Commons at the URLs recorded in
`manifest.json`. Every source has a public-domain, CC BY 4.0, or CC BY-SA 4.0
reuse statement on its file page. The committed derivative generator records
all benchmark transformations. CC BY-SA derivatives remain under CC BY-SA 4.0.

The six-case dataset intentionally remains small. It covers three countries,
three denominations, modern and older issues, rotation, glare, low contrast,
weak focus, wear, and partial obstruction. It does not support statistical
significance claims and is not representative of the full worldwide coin
population.
