# PR #410 Windows CI investigation — 2026-10-15

## Scope and revisions

- PR #410 authorized head: `cbc4b5159f8b13e4842a28c7ca42b89e7821f752`.
- Verified main / repair base: `070b4030be92c127994abacc719b7ab3c2bc1ece`.
- Repair branch: `fix/stale-detection-fixture-signature`.
- Only test correction: `tests/test_stale_detection_invalidation.py`; this report records evidence.
- No production, dependency, CI, recognition, persistence, or PR #410 branch changes.
- The original dirty checkout was left untouched. All fixture work used synthetic PNGs and temporary storage in an isolated worktree.

## CI evidence

The [failing Windows push job](https://github.com/adamo-sys/coin-analyzer/actions/runs/38809997078/job/116680523925) checked out the exact authorized head on `windows-2025-vs2026`, CPython 3.12.10. Root discovery ran 6,319 tests: one failure, 30 skipped. Complete failure traceback:

```text
FAIL: test_same_path_nested_newer_results_survive_obsolete_outer_completions
  (operation='advanced')
File tests/test_stale_detection_invalidation.py, line 296:
  error.assert_not_called()
File unittest/mock.py, line 910, in assert_not_called:
  raise AssertionError(msg)
AssertionError: Expected 'showerror' to not have been called. Called 1 times.
Calls: [call('Error', "Advanced identification failed: 'types.SimpleNamespace' object is not subscriptable")].
```

The application catches the underlying exception, so CI contains no deeper exception traceback. Local exception tracing identified `coin_collection_gui.py:3095`, `if result['success']`, as the caught TypeError site.

The [Ubuntu push job](https://github.com/adamo-sys/coin-analyzer/actions/runs/38809997078/job/116680523976) checked out the same exact head with CPython 3.12.15 and passed 6,319 tests, 62 skipped. The target test has no platform skip. The [later Windows PR job](https://github.com/adamo-sys/coin-analyzer/actions/runs/38810460727/job/116682078636) passed 6,319 tests, 30 skipped, testing GitHub's merge commit `0cc55ee558ee02a40317c2759fd98a1342badb0e` of this head into the verified main base. Both commits have the same source tree, `82c401624d0eddf86e8a9d15714de105bea0541a`, verified through the GitHub Git API. A later pass does not remove the demonstrated fixture weakness.

## Cause and bounded reproduction

The test's first two green replacements are 32×17 and 31×17 pixels. Both encode to **97 bytes** with the installed Pillow. The fixture expects each replacement to advance the source revision but originally checked neither distinct file size nor revision advance.

`CoinCollectionApp.current_image_path` compares normalized path and `(st_dev, st_ino, st_size, st_mtime_ns, st_ctime_ns)`. On local Windows, overwriting this synthetic file leaves its identity and creation timestamp unchanged. When modification times coincide, these two different PNGs have identical source signatures. The outer advanced completion then remains current, reaches dictionary access, and exposes the callback's `SimpleNamespace(results=[])` sentinel. That sentinel normally must be discarded before rendering.

Reproduction on Windows 10 / CPython 3.14.6 with existing dependencies:

1. Exact authorized PR revision: one ordinary focused pass, 50 traced repetitions and 100 untraced repetitions passed. An uncontrolled local failure was not observed.
2. Wrap `PIL.Image.Image.save` in memory: after each overwrite, use `os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))`. This controls only synthetic fixture timestamps; production and test source at the PR revision remain unchanged.
3. The exact `advanced` subcase failure and message reproduce. Recorded consecutive sizes are 97 and 97 bytes; both timestamps and file identity coincide. Exception tracing reaches GUI line 3095.
4. The same controlled reproduction fails on verified main. `git diff` confirms the target test, its production source, and governance are unchanged between main and PR #410. PR #410 adds only its first-coin test module and evidence document. Reproduction uses the target test alone, so neither PR #410's added tests nor preceding test execution is necessary.

**Classification:** demonstrated fixture precondition defect with a platform/timing trigger. The reused callback payload explains the exception text; changing only that payload would conceal a failure to establish obsolescence. No production correction is justified by this investigation. Original CI did not retain stat values, so the exact timestamp collision in that hosted run is inferred from the matching controlled reproduction, not directly observed. Ubuntu filesystem metadata was not instrumented.

## Smallest correction and validation

Use progressively larger replacement dimensions, `(32 + 16 * index, 17 + 16 * index)`, deliberately retain the previous modification time, and assert both changed encoded size and advanced source revision. All existing nested-result identity, form-origin, rendered-year, and suppressed-error assertions remain intact. No sleeps or production guards change.

- Red: adding timestamp preservation while retaining the old dimensions reproduces the exact failure on main.
- Green: corrected stale-detection and Canadian-date suites pass **27 tests** on local Windows.
- Corrected timestamp-preserving target passes **100 repetitions** on local Windows.
- In-memory mutation removing the advanced-result revision guards makes the corrected test fail for both `advanced` and `advanced_error`; no production file was modified.
- Focused Ruff E9 and `git diff --check` pass.
- One initial validation command incorrectly named nonexistent `tests.test_detection_source_revision`; the resulting loader error was corrected by rerunning the actual two suites. It is not a source defect.
- Full local root regression: pending.
- Independent review: pending.
- Repair iterations: **one**; maximum authorized: two.

## Publication and PR #410 recommendation

A separate draft repair PR is appropriate because the defect exists on verified main independently of PR #410. Do not change PR #410's branch in this task. Hosted Windows CI on the repair revision is required before calling the Windows failure resolved; local Windows 3.14 evidence is not equivalent to the affected hosted Windows 3.12 environment.

**PR #410: HOLD** while the fixture correction and its hosted Windows evidence are pending. After the separately reviewed correction is merged with explicit human authorization, the owner can authorize updating PR #410 from main and require fresh blocking gates for its new exact head. No automatic merge is authorized.
