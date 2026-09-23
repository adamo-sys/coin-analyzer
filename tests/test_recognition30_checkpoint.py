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
from capture_import import recognition30_checkpoint as checkpoint


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


def test_reconciliation_substitutes_authorized_provider_failures_and_preserves_provenance(
    tmp_path,
):
    replacement_case_ids = (
        "CA-R30-009",
        "CA-R30-017",
        "CA-R30-022",
        "CA-R30-026",
        "CA-R30-029",
    )
    original = tmp_path / "official"
    original_journal = CheckpointJournal(original, _identity(run_id="official-run"))
    for completion_order, case_id in enumerate(
        (f"CA-R30-{number:03d}" for number in range(1, 31)), start=1
    ):
        record = _record(case_id)
        record["completion_order"] = completion_order
        if case_id in replacement_case_ids:
            record["terminal_outcome"] = "PIPELINE_FAILURE"
            record["diagnostics"] = {
                "reason": "provider_observation_failure",
                "provider_failures": [{"failure_kind": "provider_timeout"}],
            }
        original_journal.append_terminal(record)
    original_bytes = (original / "checkpoints.jsonl").read_bytes()

    replacement = tmp_path / "replacement"
    replacement_journal = CheckpointJournal(
        replacement, _identity(run_id="replacement-run")
    )
    for completion_order, case_id in enumerate(replacement_case_ids, start=1):
        record = _record(case_id)
        record["completion_order"] = completion_order
        replacement_journal.append_terminal(record)

    authorization = checkpoint.Recognition30ReplacementAuthorization(
        original_run_id="official-run",
        replacement_run_id="replacement-run",
        case_ids=replacement_case_ids,
        reason="authorized infrastructure-invalid provider observations",
    )

    reconciled = checkpoint.reconcile_checkpoint_runs(
        original, replacement, authorization
    )

    assert [record["case_id"] for record in reconciled["effective_records"]] == [
        f"CA-R30-{number:03d}" for number in range(1, 31)
    ]
    assert reconciled["replacement_case_ids"] == list(replacement_case_ids)
    assert reconciled["terminal_outcome_counts"] == {
        "IDENTIFY": 30,
        "ABSTAIN": 0,
        "PIPELINE_FAILURE": 0,
    }
    assert reconciled["correctness_breakdown"] == "unavailable"
    assert set(reconciled["input_artifact_hashes"]["original"]) == {
        "run.json",
        "checkpoints.jsonl",
    }
    replacement_row = reconciled["effective_records"][8]
    assert replacement_row["case_id"] == "CA-R30-009"
    assert replacement_row["provenance"]["original_record"]["terminal_outcome"] == (
        "PIPELINE_FAILURE"
    )
    assert replacement_row["provenance"]["replacement_record"]["terminal_outcome"] == (
        "IDENTIFY"
    )
    assert (original / "checkpoints.jsonl").read_bytes() == original_bytes


def _reconciliation_fixture(tmp_path):
    replacement_case_ids = ("CA-R30-009",)
    original = tmp_path / "official"
    original_journal = CheckpointJournal(original, _identity(run_id="official-run"))
    for completion_order, case_id in enumerate(
        (f"CA-R30-{number:03d}" for number in range(1, 31)), start=1
    ):
        record = _record(case_id)
        record["completion_order"] = completion_order
        if case_id in replacement_case_ids:
            record["terminal_outcome"] = "PIPELINE_FAILURE"
            record["diagnostics"] = {
                "reason": "provider_observation_failure",
                "provider_failures": [{"failure_kind": "provider_timeout"}],
            }
        original_journal.append_terminal(record)
    replacement = tmp_path / "replacement"
    replacement_journal = CheckpointJournal(
        replacement, _identity(run_id="replacement-run")
    )
    replacement_record = _record("CA-R30-009")
    replacement_journal.append_terminal(replacement_record)
    authorization = checkpoint.Recognition30ReplacementAuthorization(
        original_run_id="official-run",
        replacement_run_id="replacement-run",
        case_ids=replacement_case_ids,
        reason="authorized infrastructure-invalid provider observations",
    )
    return original, replacement, authorization


def test_reconciliation_rejects_replacement_of_valid_original_case(tmp_path):
    original, replacement, authorization = _reconciliation_fixture(tmp_path)
    original = tmp_path / "valid-original"
    journal = CheckpointJournal(original, _identity(run_id="official-run"))
    for number in range(1, 31):
        record = _record(f"CA-R30-{number:03d}")
        record["completion_order"] = number
        journal.append_terminal(record)

    with pytest.raises(CheckpointValidationError, match="only infrastructure-invalid"):
        checkpoint.reconcile_checkpoint_runs(original, replacement, authorization)


def test_reconciliation_rejects_replacement_cases_outside_explicit_authorization(tmp_path):
    original, replacement, authorization = _reconciliation_fixture(tmp_path)
    extra = tmp_path / "extra-replacement"
    journal = CheckpointJournal(extra, _identity(run_id="replacement-run"))
    for case_id in ("CA-R30-009", "CA-R30-010"):
        journal.append_terminal(_record(case_id))

    with pytest.raises(CheckpointValidationError, match="exactly match authorization"):
        checkpoint.reconcile_checkpoint_runs(original, extra, authorization)


def test_reconciliation_rejects_missing_required_replacement_case(tmp_path):
    original, replacement, authorization = _reconciliation_fixture(tmp_path)
    missing = tmp_path / "missing-replacement"
    CheckpointJournal(missing, _identity(run_id="replacement-run"))

    with pytest.raises(CheckpointValidationError, match="exactly match authorization"):
        checkpoint.reconcile_checkpoint_runs(original, missing, authorization)


def test_reconciliation_rejects_incompatible_fingerprint_and_execution_metadata(tmp_path):
    original, replacement, authorization = _reconciliation_fixture(tmp_path)
    fingerprint_mismatch = tmp_path / "fingerprint-mismatch"
    CheckpointJournal(
        fingerprint_mismatch,
        _identity(run_id="replacement-run", dataset_fingerprint="different"),
    ).append_terminal(_record("CA-R30-009"))
    with pytest.raises(CheckpointValidationError, match="dataset"):
        checkpoint.reconcile_checkpoint_runs(
            original, fingerprint_mismatch, authorization
        )

    metadata_mismatch = tmp_path / "metadata-mismatch"
    CheckpointJournal(
        metadata_mismatch,
        _identity(
            run_id="replacement-run",
            execution_metadata={"provider_timeout_seconds": 60.0},
        ),
    ).append_terminal(_record("CA-R30-009"))
    with pytest.raises(CheckpointValidationError, match="execution metadata"):
        checkpoint.reconcile_checkpoint_runs(original, metadata_mismatch, authorization)


@pytest.mark.parametrize(
    "terminal_outcome, diagnostics, message",
    [
        ("PIPELINE_FAILURE", {"reason": "fixture"}, "valid terminal recognition"),
        (
            "IDENTIFY",
            {"reason": "fixture", "provider_failures": [{"failure_kind": "timeout"}]},
            "infrastructure-invalid",
        ),
    ],
)
def test_reconciliation_rejects_nonterminal_or_infrastructure_invalid_replacement(
    tmp_path, terminal_outcome, diagnostics, message
):
    original, replacement, authorization = _reconciliation_fixture(tmp_path)
    invalid = tmp_path / "invalid-replacement"
    record = _record("CA-R30-009", terminal_outcome)
    record["diagnostics"] = diagnostics
    CheckpointJournal(invalid, _identity(run_id="replacement-run")).append_terminal(
        record
    )

    with pytest.raises(CheckpointValidationError, match=message):
        checkpoint.reconcile_checkpoint_runs(original, invalid, authorization)


def test_reconciliation_rejects_malformed_replacement_record(tmp_path):
    original, replacement, authorization = _reconciliation_fixture(tmp_path)
    journal = replacement / "checkpoints.jsonl"
    journal.write_text('{"case_id":"CA-R30-009"}\n', encoding="utf-8")

    with pytest.raises(CheckpointValidationError, match="malformed"):
        checkpoint.reconcile_checkpoint_runs(original, replacement, authorization)


def test_reconciliation_rejects_duplicate_replacement_record(tmp_path):
    original, replacement, authorization = _reconciliation_fixture(tmp_path)
    journal = replacement / "checkpoints.jsonl"
    journal.write_bytes(journal.read_bytes() + journal.read_bytes())

    with pytest.raises(CheckpointValidationError, match="duplicate"):
        checkpoint.reconcile_checkpoint_runs(original, replacement, authorization)


def test_reconciliation_rejects_unrecognized_original_terminal_outcome(tmp_path):
    original, replacement, authorization = _reconciliation_fixture(tmp_path)
    journal = original / "checkpoints.jsonl"
    records = journal.read_text(encoding="utf-8").splitlines()
    corrupted = json.loads(records[0])
    corrupted["terminal_outcome"] = "IN_PROGRESS"
    records[0] = json.dumps(corrupted, sort_keys=True)
    journal.write_text("\n".join(records) + "\n", encoding="utf-8")

    with pytest.raises(CheckpointValidationError, match="valid terminal outcome"):
        checkpoint.reconcile_checkpoint_runs(original, replacement, authorization)
