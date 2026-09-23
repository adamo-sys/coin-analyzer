from pathlib import Path
from typing import cast

import pytest

from capture_import import recognition30_observation_contract_experiment as experiment
from capture_import import recognition30_observation_contract_evaluator as evaluator


def test_build_manifest_plans_two_arms_for_each_side_and_view(monkeypatch, tmp_path):
    cases = tuple(
        experiment.ExperimentCase(
            case_id=case_id,
            obverse=tmp_path / f"{case_id}-obverse.jpg",
            reverse=tmp_path / f"{case_id}-reverse.jpg",
        )
        for case_id in experiment.EXPERIMENT_5_CASE_IDS
    )
    for case in cases:
        case.obverse.write_bytes(b"obverse")
        case.reverse.write_bytes(b"reverse")

    monkeypatch.setattr(experiment, "load_cases", lambda _: cases)
    monkeypatch.setattr(experiment, "_dataset_fingerprint", lambda _: "fingerprint")
    monkeypatch.setattr(
        experiment,
        "build_evidence_views",
        lambda path: (("full_face", b"full", "image/jpeg"), ("rim", b"rim", "image/jpeg")),
    )

    manifest = experiment.build_manifest(tmp_path)

    assert len(manifest.requests) == 64
    assert {request.arm for request in manifest.requests} == {"control", "treatment"}
    assert {
        (request.role, request.view)
        for request in manifest.requests
    } == {
        ("obverse", "full_face"),
        ("obverse", "rim"),
        ("reverse", "full_face"),
        ("reverse", "rim"),
    }
    assert all(request.image_sha256 for request in manifest.requests)


def test_selected_cases_build_sixteen_request_manifest_in_canonical_order(monkeypatch, tmp_path):
    cases = _fixture_cases(tmp_path)
    _stub_manifest_dependencies(monkeypatch, cases)

    manifest = experiment.build_manifest(
        tmp_path, case_ids=("CA-R30-011", "CA-R30-030")
    )

    assert len(manifest.requests) == 16
    assert manifest.case_ids == ("CA-R30-011", "CA-R30-030")


def test_reversed_selected_cases_produce_same_manifest(monkeypatch, tmp_path):
    cases = _fixture_cases(tmp_path)
    _stub_manifest_dependencies(monkeypatch, cases)

    forward = experiment.build_manifest(tmp_path, case_ids=("CA-R30-011", "CA-R30-030"))
    reverse = experiment.build_manifest(tmp_path, case_ids=("CA-R30-030", "CA-R30-011"))

    assert forward.public_record() == reverse.public_record()


def test_one_selected_case_builds_eight_request_manifest(monkeypatch, tmp_path):
    cases = _fixture_cases(tmp_path)
    _stub_manifest_dependencies(monkeypatch, cases)

    assert len(experiment.build_manifest(tmp_path, case_ids=("CA-R30-011",)).requests) == 8


def test_selected_dry_run_constructs_no_provider(monkeypatch, tmp_path):
    cases = _fixture_cases(tmp_path)
    _stub_manifest_dependencies(monkeypatch, cases)

    class UnexpectedProvider:
        def __init__(self, *args, **kwargs):
            raise AssertionError("dry run must not construct a provider")

    monkeypatch.setattr(experiment, "OpenAIGroundedVisualObservationProvider", UnexpectedProvider)
    output = tmp_path / "manifest.json"
    experiment.run_dry_run(
        tmp_path, output, case_ids=("CA-R30-011", "CA-R30-030")
    )

    assert '"planned_call_count": 16' in output.read_text(encoding="utf-8")


@pytest.mark.parametrize("case_ids", [("CA-R30-999",), ("CA-R30-011", "CA-R30-011")])
def test_invalid_case_selection_fails_before_provider_construction(monkeypatch, tmp_path, case_ids):
    cases = _fixture_cases(tmp_path)
    _stub_manifest_dependencies(monkeypatch, cases)

    with pytest.raises(ValueError):
        experiment.build_manifest(tmp_path, case_ids=case_ids)


def _fixture_cases(tmp_path):
    cases = tuple(
        experiment.ExperimentCase(
            case_id=case_id,
            obverse=tmp_path / f"{case_id}-obverse.jpg",
            reverse=tmp_path / f"{case_id}-reverse.jpg",
        )
        for case_id in experiment.EXPERIMENT_5_CASE_IDS
    )
    for case in cases:
        case.obverse.write_bytes(b"obverse")
        case.reverse.write_bytes(b"reverse")
    return cases


def _stub_manifest_dependencies(monkeypatch, cases):
    monkeypatch.setattr(experiment, "load_cases", lambda _: cases)
    monkeypatch.setattr(experiment, "_dataset_fingerprint", lambda _: "fingerprint")
    monkeypatch.setattr(
        experiment,
        "build_evidence_views",
        lambda path: (("full_face", b"full", "image/jpeg"), ("rim", b"rim", "image/jpeg")),
    )


def test_dry_run_writes_manifest_without_constructing_provider(monkeypatch, tmp_path):
    class UnexpectedProvider:
        def __init__(self, *args, **kwargs):
            raise AssertionError("dry run must not construct a provider")

    monkeypatch.setattr(experiment, "OpenAIGroundedVisualObservationProvider", UnexpectedProvider)
    manifest = experiment.ExperimentManifest(
        dataset_fingerprint="fingerprint",
        requests=(),
    )
    monkeypatch.setattr(experiment, "build_manifest", lambda *_, **__: manifest)

    output = tmp_path / "manifest.json"
    experiment.run_dry_run(tmp_path, output)

    assert output.is_file()
    assert '"planned_call_count": 0' in output.read_text(encoding="utf-8")


def test_evaluator_compares_saved_observations_only_after_execution():
    records = (
        {
            "arm": "control",
            "case_id": "CA-R30-005",
            "status": "success",
            "date_like": None,
            "denomination_mark": None,
        },
        {
            "arm": "treatment",
            "case_id": "CA-R30-005",
            "status": "success",
            "date_like": "1990",
            "denomination_mark": "25 sentimo",
        },
        {
            "arm": "treatment",
            "case_id": "CA-R30-009",
            "status": "malformed_output",
            "date_like": None,
            "denomination_mark": None,
        },
    )

    result = evaluator.evaluate_saved_records(
        records,
        {
            "CA-R30-005": {"year": "1990", "denomination": "25 sentimo"},
            "CA-R30-009": {"year": "1975", "denomination": "1 peseta"},
        },
        target_case_ids=("CA-R30-005",),
    )

    arms = cast(dict[str, dict[str, int]], result["arms"])
    assert arms["control"]["complete_correct_field_cells"] == 0
    assert arms["treatment"]["complete_correct_field_cells"] == 2
    assert arms["treatment"]["malformed_call_count"] == 1
    assert arms["treatment"]["wrong_structured_field_count"] == 0


def test_execute_manifest_passes_arm_prompt_to_factory_and_never_retries(tmp_path):
    requested_prompts = []

    class RecordingProvider:
        def observe(self, request):
            return type("Report", (), {"observation": type("Observation", (), {
                "visible_text": ("1990",), "date_like": "1990", "denomination_mark": None,
            })()})()

    manifest = experiment.ExperimentManifest(
        dataset_fingerprint="fingerprint",
        requests=(
            experiment.PlannedObservationRequest(1, "control", "CA-R30-005", "obverse", "full_face", "image/jpeg", b"one", "a"),
            experiment.PlannedObservationRequest(2, "treatment", "CA-R30-005", "obverse", "full_face", "image/jpeg", b"two", "b"),
        ),
    )

    records = experiment.execute_manifest(
        manifest,
        provider_factory=lambda prompt: requested_prompts.append(prompt) or RecordingProvider(),
        output=tmp_path / "records.jsonl",
    )

    assert [record["status"] for record in records] == ["success", "success"]
    assert requested_prompts == [experiment.OPENAI_GROUNDED_OBSERVATION_PROMPT, experiment.treatment_prompt()]
