# Bake-Off V1 Execution Protocol v1.1

Execution Protocol v1.1 applies to privacy-safe contestant runs after its
freeze. It retains the V1 task corpus, task-start commit identity, required
checks, immutable acceptance, and result states. It supersedes only the
contestant completion-commit requirement.

## Candidate completion and freeze

The contestant leaves its worktree and index exactly as produced. A completion
commit is not required. The candidate `HEAD` must remain the frozen task-start
commit. After contestant access has ended, the trusted operator records a
materialization manifest for the clean task-start state and freezes the final
state twice. The authoritative final identity is the SHA-256 of canonical JSON
containing the benchmark/task/run identity, protocol version, task-start SHA,
materialization-policy digest, worktree entries, index entries, and derived
added, modified, and deleted paths.

Worktree entries use normalized candidate-relative UTF-8 paths, regular-file
type, normalized executable mode, byte size, and raw-byte SHA-256. Index entries
use normalized path, stage, mode, and Git object ID. Arrays sort by UTF-8 path
bytes; JSON uses sorted keys and compact separators. Timestamps, absolute paths,
ACLs, and machine-specific metadata are excluded.

The freezer fails closed on state mutation during collection, protected-path
materialization, unsafe types or paths, canonical-path collisions, malformed or
unmerged index state, and required staged-index/worktree disagreement. Protected
historical paths that were deliberately absent from the recorded task-start
materialization are not contestant deletions.

## Trusted grading

`tools.bakeoff_v1_grader.grade_run()` remains the sole authoritative public
grading entry point. For v1.1 it independently recomputes the candidate-state
identity, verifies it against the run record, derives scope changes from the
frozen state, and runs required checks and immutable acceptance against a
separate trusted grading copy. Immutable reference material is available only in
the trusted grader context, never the contestant candidate.

Run records explicitly declare execution protocol version `1.1`, candidate
state and materialization-policy SHA-256 values, candidate start HEAD, observed
worktree status, derived changes, and freezer status. Existing schema-v1.0
records remain historical v1.0 records; they are not rewritten.
