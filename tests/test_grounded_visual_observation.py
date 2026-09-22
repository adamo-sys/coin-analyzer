from dataclasses import fields

import pytest

from capture_import.grounded_visual_observation import (
    GroundedVisualObservation,
    GroundedVisualObservationContractError,
    GroundedVisualObservationImage,
    GroundedVisualObservationProvider,
    GroundedVisualObservationReport,
    GroundedVisualObservationRequest,
)


def _image(**overrides):
    values = {"role": "obverse", "media_type": "image/jpeg", "data": b"coin"}
    values.update(overrides)
    return GroundedVisualObservationImage(**values)


def _observation(**overrides):
    values = {"role": "obverse"}
    values.update(overrides)
    return GroundedVisualObservation(**values)


def _report(**overrides):
    values = {
        "observation": _observation(),
        "provider_id": "test-provider",
        "model_id": "test-model",
        "response_id": None,
        "input_tokens": None,
        "output_tokens": None,
    }
    values.update(overrides)
    return GroundedVisualObservationReport(**values)


@pytest.mark.parametrize("media_type", ["image/jpeg", "image/png"])
def test_image_accepts_supported_media_types(media_type):
    assert _image(media_type=media_type).media_type == media_type


@pytest.mark.parametrize("role", ["edge", "", "OBVERSE"])
def test_image_rejects_invalid_role(role):
    with pytest.raises(GroundedVisualObservationContractError):
        _image(role=role)


@pytest.mark.parametrize("media_type", ["image/gif", "jpeg", ""])
def test_image_rejects_invalid_media_type(media_type):
    with pytest.raises(GroundedVisualObservationContractError):
        _image(media_type=media_type)


@pytest.mark.parametrize("data", [b"", "coin", None])
def test_image_rejects_invalid_data(data):
    with pytest.raises(GroundedVisualObservationContractError):
        _image(data=data)


@pytest.mark.parametrize(
    "scan_id", ["scan-001", "SCAN_2", "a" * 64, "Recognition30_017"]
)
def test_request_accepts_safe_scan_id(scan_id):
    request = GroundedVisualObservationRequest(scan_id=scan_id, image=_image())
    assert request.image.role == "obverse"


@pytest.mark.parametrize(
    "scan_id", ["", "has space", "../scan", "a" * 65, None]
)
def test_request_rejects_invalid_scan_id(scan_id):
    with pytest.raises(GroundedVisualObservationContractError):
        GroundedVisualObservationRequest(scan_id=scan_id, image=_image())


def test_request_contains_exactly_one_image_by_construction():
    request = GroundedVisualObservationRequest(scan_id="scan-1", image=_image())
    assert {field.name for field in fields(request)} == {"scan_id", "image"}
    assert isinstance(request.image, GroundedVisualObservationImage)


def test_request_rejects_non_image_value():
    with pytest.raises(GroundedVisualObservationContractError):
        GroundedVisualObservationRequest(scan_id="scan-1", image=("bad",))


def test_observation_accepts_empty_and_partial_evidence():
    empty = _observation()
    partial = _observation(
        visible_text=("1955", "25"),
        script="Latin",
        motifs=("ship",),
        date_like="1955",
        denomination_mark="25",
    )
    assert empty.visible_text == ()
    assert partial.date_like == "1955"
    assert partial.denomination_mark == "25"


def test_observation_accepts_eight_list_entries():
    eight = tuple(str(i) for i in range(8))
    observation = _observation(visible_text=eight, motifs=eight)
    assert len(observation.visible_text) == 8
    assert len(observation.motifs) == 8


@pytest.mark.parametrize("name", ["visible_text", "motifs"])
def test_observation_rejects_more_than_eight_entries(name):
    with pytest.raises(GroundedVisualObservationContractError):
        _observation(**{name: tuple(str(i) for i in range(9))})


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("visible_text", ["1955"]),
        ("visible_text", ("",)),
        ("visible_text", ("   ",)),
        ("visible_text", (7,)),
        ("motifs", ["ship"]),
        ("motifs", ("",)),
        ("motifs", (None,)),
    ],
)
def test_observation_rejects_malformed_evidence_sequences(name, value):
    with pytest.raises(GroundedVisualObservationContractError):
        _observation(**{name: value})


@pytest.mark.parametrize(
    "name",
    [
        "script",
        "portrait",
        "construction",
        "shape",
        "date_like",
        "denomination_mark",
    ],
)
@pytest.mark.parametrize("value", ["", "   ", 7, False])
def test_observation_rejects_malformed_optional_strings(name, value):
    with pytest.raises(GroundedVisualObservationContractError):
        _observation(**{name: value})


def test_report_accepts_valid_metadata():
    report = _report(response_id="resp-1", input_tokens=0, output_tokens=12)
    assert report.provider_id == "test-provider"
    assert report.input_tokens == 0


@pytest.mark.parametrize("name", ["provider_id", "model_id"])
@pytest.mark.parametrize("value", ["", "   ", None, 7])
def test_report_rejects_invalid_required_metadata(name, value):
    with pytest.raises(GroundedVisualObservationContractError):
        _report(**{name: value})


@pytest.mark.parametrize("value", ["", "   ", 7])
def test_report_rejects_invalid_response_id(value):
    with pytest.raises(GroundedVisualObservationContractError):
        _report(response_id=value)


@pytest.mark.parametrize("name", ["input_tokens", "output_tokens"])
@pytest.mark.parametrize("value", [-1, 1.5, True, "1"])
def test_report_rejects_invalid_token_count(name, value):
    with pytest.raises(GroundedVisualObservationContractError):
        _report(**{name: value})


def test_runtime_protocol_conformance():
    class FakeProvider:
        provider_id = "fake"
        model_id = "fake-model"

        def observe(self, request):
            return GroundedVisualObservationReport(
                observation=GroundedVisualObservation(role=request.image.role),
                provider_id=self.provider_id,
                model_id=self.model_id,
                response_id=None,
                input_tokens=None,
                output_tokens=None,
            )

    provider = FakeProvider()
    assert isinstance(provider, GroundedVisualObservationProvider)
    report = provider.observe(
        GroundedVisualObservationRequest(scan_id="scan-1", image=_image())
    )
    assert report.observation.role == "obverse"


def test_observation_contract_excludes_identity_and_confidence_fields():
    names = {field.name for field in fields(GroundedVisualObservation)}
    forbidden = {
        "country",
        "jurisdiction",
        "identity",
        "candidates",
        "year",
        "ruler",
        "catalogue_id",
        "confidence",
        "accepted",
        "rejected",
    }
    assert names.isdisjoint(forbidden)
    assert names == {
        "role",
        "visible_text",
        "script",
        "portrait",
        "motifs",
        "construction",
        "shape",
        "date_like",
        "denomination_mark",
    }
