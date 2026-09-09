# T9 coverage and diff-cover pilot — 2026-09-09

Status: **COMPLETE — MANUAL-ONLY ADVISORY**. Tracking: [#213](https://github.com/adamo-sys/coin-analyzer/issues/213).

The corrected Ubuntu baseline and instrumented run both completed before the
session interruption. Recovery verified their saved results without rerunning
tests. Coverage and changed-line reporting are usable, but one sequential pair
with negative observed overhead does not establish stable routine/CI cost.
No percentage gate, workflow, runtime dependency, production code or test changed.

## Frozen inputs

- Head/main: `99934ed078186fc6612cfe17b279fb1cc2ea3e2a`.
- Diff base: `c8f87648587be14b5779a4418be7b947bde720d2` (head's first parent).
- The nonempty diff is merged #218: mutation-evidence capture helper and tests,
  plus workflow/docs changes. Only executable changed Python lines are scored.
- Ubuntu 26.04 LTS, x86_64, WSL2 kernel
  `6.18.33.2-microsoft-standard-WSL2`, glibc 2.43.
- CPython **3.12.11**, managed standalone build installed using **uv 0.8.22**.
- `coverage.py==7.16.0`, `diff-cover==10.5.1`, `hypothesis==6.167.1`.
- Repository `requirements-dev.lock` installed unchanged; SHA-256:
  `ed6bac6be20865a7c7c6ebe38406ddd23e1113dc4ded71d155877f1c0d8123e5`.
- Both runs: `PYTHONHASHSEED=0`, `TZ=UTC`, DISPLAY and WAYLAND_DISPLAY unset,
  `TMPDIR=/home/adamo/coin-analyzer-t9-99934ed/test-tmp`.
- Checkout: `/home/adamo/coin-analyzer-t9-99934ed/repo`; virtual environment:
  `/home/adamo/coin-analyzer-t9-99934ed/venv`. Environment resides outside checkout.

Complete installed freeze (rechecked unchanged during recovery):

```text
chardet==7.6.0
colorama==0.4.6
coverage==7.16.0
diff-cover==10.5.1
et-xmlfile==2.0.0
hypothesis==6.167.1
iniconfig==2.3.0
jinja2==3.1.6
markupsafe==3.0.3
numpy==2.5.2
opencv-python==5.0.0.93
openpyxl==3.1.5
packaging==26.3
pandas==3.0.5
pillow==12.3.0
pluggy==1.6.0
pygments==2.21.0
pytest==9.1.1
python-dateutil==2.9.0.post0
six==1.17.0
sortedcontainers==2.4.0
tzdata==2026.3
```

## Matched execution and timing

The retained external `t9-run.py` harness uses
`unittest.defaultTestLoader.discover('.', pattern='test_*.py')` and a
`TextTestRunner` that records discovered IDs, outcomes and skip reasons. It does
not filter tests or alter their behavior. The same harness runs normally and
under `coverage run --branch --source=.`. Test timing uses `perf_counter()` around
the runner; discovery-plus-test timing includes imports/discovery. Neither figure
includes dependency installation, XML/report generation or WSL startup.

| Measurement | Baseline (`baseline-2`) | Instrumented (`instrumented-2`) |
| --- | ---: | ---: |
| Tests run | 5,417 | 5,417 |
| Skipped | 6 | 6 |
| Failures / errors | 0 / 0 | 0 / 0 |
| Process exit | 0 | 0 |
| Test seconds | 260.380849326 | 211.065061228 |
| Discovery + test seconds | 273.465035975 | 216.201313564 |

Full ordered discovery and recorded outcome/skip lists compare equal, not just
their counts. Discovery-list SHA-256:
`e84b3798ad15b5143fb1df543228c0c466c9cd4ac92d28c9085fc3b5548453ad`.
The corrected Doctor preflight passed 12 tests before the pair.

Observed test-time overhead: `(211.065061228 / 260.380849326 - 1) * 100`
= **-18.94%**, a difference of -49.32 seconds. This is not a coverage speedup
claim. Baseline ran first; caches, scheduling and host load were not controlled.
There is one valid pair, so no robust repeated-pair median or variance estimate.
The proposed roughly 30% median-overhead criterion for routine use remains
unestablished. Repetitions were deliberately not chased after recovery.

## XML and changed-line findings

Coverage XML parsed successfully. Its source root is the exact Linux checkout;
both changed Python filenames resolve to existing files and matching XML class
entries. An independent intersection of Git added-line ranges and XML executable
lines agrees with diff-cover: **206/209 covered**, **3 missing** (98.56%; the
default diff-cover console rounds to 98%). Production behavior is not inferred
from this narrow developer-tool diff or from line coverage alone.

| File | Covered / executable changed | Uncovered lines and assessment |
| --- | ---: | --- |
| `tools/capture_mutmut_evidence.py` | 81 / 83 | **56:** blank/whitespace results-line `continue`, a real unexercised parser branch; a future focused whitespace case could cover it. **141:** direct CLI `SystemExit(main())` entry point; main is invoked directly by the tests, not through that entry point. |
| `tests/test_mutmut_evidence_capture.py` | 125 / 126 | **174:** standalone `unittest.main()` entry point, normally unexecuted by discovery. |

All three were inspected in the frozen source. No test was added to chase the
percentage. Although branch instrumentation was collected, the diff score above
is line coverage; subprocess coverage was not separately configured or claimed.

Retained reporting commands, run from the frozen checkout (ROOT is the pilot
directory and PY is `$ROOT/venv/bin/python`):

```bash
export COVERAGE_FILE="$ROOT/evidence/.coverage"
"$PY" "$ROOT/t9-run.py" "$ROOT/evidence/baseline-2.json"
"$PY" -m coverage run --branch --source=. "$ROOT/t9-run.py" "$ROOT/evidence/instrumented-2.json"
"$PY" -m coverage xml -o "$ROOT/evidence/coverage.xml"
git diff --no-ext-diff --unified=0 c8f87648587be14b5779a4418be7b947bde720d2 99934ed078186fc6612cfe17b279fb1cc2ea3e2a -- '*.py' > "$ROOT/evidence/changed-python.diff"
"$ROOT/venv/bin/diff-cover" "$ROOT/evidence/coverage.xml" --diff-file "$ROOT/evidence/changed-python.diff" --compare-branch c8f87648587be14b5779a4418be7b947bde720d2 --diff-range-notation '..' --ignore-staged --ignore-unstaged
```

The exact runner, setup, environment, analysis and command scripts are retained
with the evidence. Both execution logs were redirected separately. Use new output
names for any future experiment rather than overwriting these artifacts.
The initial diff-cover output used the supplied frozen diff but displayed its
default `origin/main...HEAD` banner. `diff-cover-explicit.txt` regenerates only
the report with the explicit base label; its counts agree. This was not an empty
same-revision comparison.

## Preserved failures and limitations

- Earlier Windows b9e976a logs remain intact and are not the current baseline.
- Initial successful environment setup under `/tmp` was unavailable on the next
  invocation, before tests ran; setup was repeated under the persistent home
  directory. The temporary-directory disappearance was not investigated further.
- First persistent baseline (`baseline-1`): 5,417 tests, 10 failures, 6 skips,
  126.421 seconds. Doctor failed because held traversal into `/tmp` crossed a
  volume. A direct probe reproduced the exception and succeeded under the home
  directory. Setting the same dedicated TMPDIR for both corrected runs resolved
  it without weakening the filesystem boundary or changing tests.
- Historical failed baseline timing is excluded from the successful comparison.
- Six local skips differ from historical hosted CI skips: equivalence is proven
  between this pair, not between local WSL and the GitHub runner environment.
- One narrow diff and one valid pair support manual diagnostic use, not general
  coverage adequacy, steady-state performance or a new CI gate.

## Evidence and decision

Raw logs, full manifests, XML, coverage database, diff, dependency freeze, helper
scripts and SHA-256 inventory are retained at:

- Linux: `/home/adamo/coin-analyzer-t9-99934ed/evidence/`.
- Windows: `C:/Projects/coin-analyzer/artifacts/t9-coverage-diff/ubuntu-99934ed/`.

Recovery checked the original evidence checksums, unchanged dependency freeze
and clean frozen checkout. Raw evidence stays local; public documentation
contains only the bounded result and reproducibility details.

**Recommendation: manual-only advisory.** T9's pilot is complete. A future
proposal for routine CI use would need repeated controlled timing and an explicit
maintenance/reporting decision; it is not remaining work for this bounded task.
No blocking coverage percentage, automatic remediation or next experiment is
authorized by this result.
