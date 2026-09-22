from __future__ import annotations

import json

import pytest

from capture_import.recognition30_checkpoint import (
    CheckpointJournal,
    CheckpointValidationError,
    Recognition30RunIdentity,
    create_continuation,
    join_checkpoint_runs,
    load_checkpoint_records,
)


def _identity(**overrides):
    values = {
        "run_id": "run-a",
        "dataset_version": "recognition30_v1",
        "dataset_fingerprint_scheme": "recognition30-dataset-fingerprint-v1",
        "dataset_fingerprint": "dataset-sha256",
        "provider_id": "fixture-provider",
        "model_id": "fixture-model",
        "recognition_semantics": {
            "adaptive_views": False,
            "retrieval_limit": 10,
            "retrieval_mode": "oracle-catalogue",
            "verification": "two-side-gate-v1",
            "scoring": "recognition30-v1",
        },
        "execution_metadata": {"provider_timeout_seconds": 120.0},
    }
    values.update(overrides)
    return Recognition30RunIdentity(**values)


def _record(case_id: str, outcome: str = "IDENTIFY"):
    return {
        "case_id": case_id,
        "terminal_outcome": outcome,
        "diagnostics": {"reason": "fixture"},
        "execution_metadata": {"provider_timeout_seconds": 120.0},
        "completion_order": 1,
        "provenance": {"source": "test"},
    }


def test_terminal_case_is_immediately_durable_and_in_progress_is_not_recorded(tmp_path):
    journal = CheckpointJournal(tmp_path / "run", _identity())
    journal.append_terminal(_record("CA-R30-001"))

    records = load_checkpoint_records(tmp_path / "run")

    assert [record["case_id"] for record in records] == ["CA-R30-001"]
    assert records[0]["run_identity"]["run_id"] == "run-a"
    assert not (tmp_path / "run" / "in-progress.json").exists()


def test_interruption_after_case_n_keeps_prior_records_durable(tmp_path):
    journal = CheckpointJournal(tmp_path / "run", _identity())
    journal.append_terminal(_record("CA-R30-001"))
    journal.append_terminal(_record("CA-R30-002", "PIPELINE_FAILURE"))

    assert [record["case_id"] for record in load_checkpoint_records(tmp_path / "run")] == [
        "CA-R30-001",
        "CA-R30-002",
    ]


def test_duplicate_completed_case_and_malformed_or_partial_record_fail_closed(tmp_path):
    journal = CheckpointJournal(tmp_path / "run", _identity())
    journal.append_terminal(_record("CA-R30-001"))
    with pytest.raises(CheckpointValidationError, match="duplicate"):
        journal.append_terminal(_record("CA-R30-001"))

    corrupt = tmp_path / "corrupt"
    CheckpointJournal(corrupt, _identity()).append_terminal(_record("CA-R30-001"))
    with (corrupt / "checkpoints.jsonl").open("ab") as handle:
        handle.write(b'{"case_id":')
    with pytest.raises(CheckpointValidationError, match="malformed"):
        load_checkpoint_records(corrupt)


def test_continuation_creates_new_run_skips_completed_and_parent_is_unchanged(tmp_path):
    parent = tmp_path / "parent"
    CheckpointJournal(parent, _identity()).append_terminal(_record("CA-R30-001"))
    parent_bytes = (parent / "checkpoints.jsonl").read_bytes()

    continuation, completed = create_continuation(
        parent,
        tmp_path / "child",
        _identity(run_id="run-b", execution_metadata={"provider_timeout_seconds": 30.0}),
    )
    continuation.append_terminal(_record("CA-R30-002"))

    assert completed == frozenset({"CA-R30-001"})
    assert (parent / "checkpoints.jsonl").read_bytes() == parent_bytes
    assert [row["case_id"] for row in load_checkpoint_records(tmp_path / "child")] == [
        "CA-R30-002"
    ]
    assert json.loads((tmp_path / "child" / "run.json").read_text())["parent_run_id"] == "run-a"


@pytest.mark.parametrize(
    "override, message",
    [
        ({"dataset_fingerprint": "different"}, "dataset"),
        ({"dataset_fingerprint_scheme": "other-scheme"}, "dataset fingerprint scheme"),
        ({"provider_id": "other-provider"}, "provider"),
        ({"model_id": "other-model"}, "model"),
        ({"recognition_semantics": {"adaptive_views": True}}, "recognition semantics"),
    ],
)
def test_continuation_rejects_incompatible_recognition_identity(tmp_path, override, message):
    parent = tmp_path / "parent"
    CheckpointJournal(parent, _identity()).append_terminal(_record("CA-R30-001"))

    with pytest.raises(CheckpointValidationError, match=message):
        create_continuation(parent, tmp_path / "child", _identity(run_id="run-b", **override))


def _complete_run(root, identity, case_ids):
    journal = CheckpointJournal(root, identity)
    for index, case_id in enumerate(case_ids, start=1):
        row = _record(case_id)
        row["completion_order"] = index
        journal.append_terminal(row)
    return root


def test_join_accepts_complete_compatible_thirty_case_run(tmp_path):
    case_ids = [f"CA-R30-{number:03d}" for number in range(1, 31)]
    first = _complete_run(tmp_path / "first", _identity(), case_ids[:15])
    second = _complete_run(tmp_path / "second", _identity(run_id="run-b"), case_ids[15:])

    joined = join_checkpoint_runs((first, second))

    assert [record["case_id"] for record in joined["records"]] == case_ids
    assert joined["segments"] == ["run-a", "run-b"]


@pytest.mark.parametrize(
    "segments, message",
    [
        ((["CA-R30-001"], ["CA-R30-001"]), "duplicate"),
        (([f"CA-R30-{number:03d}" for number in range(1, 30)], []), "missing"),
        (([f"CA-R30-{number:03d}" for number in range(1, 31)], ["CA-R30-031"]), "unexpected"),
    ],
)
def test_join_rejects_duplicate_missing_and_unexpected_cases(tmp_path, segments, message):
    first = _complete_run(tmp_path / "first", _identity(), segments[0])
    second = _complete_run(tmp_path / "second", _identity(run_id="run-b"), segments[1])

    with pytest.raises(CheckpointValidationError, match=message):
        join_checkpoint_runs((first, second))


def test_join_rejects_incompatible_segments(tmp_path):
    first = _complete_run(tmp_path / "first", _identity(), ["CA-R30-001"])
    second = _complete_run(
        tmp_path / "second",
        _identity(run_id="run-b", dataset_fingerprint="other"),
        [f"CA-R30-{number:03d}" for number in range(2, 31)],
    )

    with pytest.raises(CheckpointValidationError, match="dataset"):
        join_checkpoint_runs((first, second))
