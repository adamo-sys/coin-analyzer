import json
from types import SimpleNamespace

import pytest

from capture_import.grounded_visual_observation import (
    GroundedVisualObservationContractError,
    GroundedVisualObservationImage,
    GroundedVisualObservationRequest,
)
from capture_import.openai_grounded_visual_observation_provider import (
    OPENAI_GROUNDED_OBSERVATION_PROMPT,
    OpenAIGroundedVisualObservationProvider,
    GroundedVisualObservationMalformedOutput,
)


class FakeResponses:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeClient:
    def __init__(self, response):
        self.responses = FakeResponses(response)


def _request(role="obverse"):
    return GroundedVisualObservationRequest(
        scan_id="rq01-001",
        image=GroundedVisualObservationImage(
            role=role,
            media_type="image/jpeg",
            data=b"coin-image",
        ),
    )


def _response(payload=None):
    if payload is None:
        payload = {
            "visible_text": ["1918", "BRITT"],
            "script": "Latin",
            "portrait": "left-facing portrait",
            "motifs": ["wreath"],
            "construction": "single-metal appearance",
            "shape": "round",
            "date_like": "1918",
            "denomination_mark": None,
        }
    return SimpleNamespace(
        output_text=json.dumps(payload),
        id="resp-1",
        usage=SimpleNamespace(input_tokens=123, output_tokens=45),
    )


def test_provider_returns_contract_report_and_preserves_role():
    client = FakeClient(_response())
    provider = OpenAIGroundedVisualObservationProvider(client=client)

    report = provider.observe(_request(role="reverse"))

    assert report.observation.role == "reverse"
    assert report.observation.visible_text == ("1918", "BRITT")
    assert report.observation.date_like == "1918"
    assert report.provider_id == provider.provider_id
    assert report.model_id == provider.model_id
    assert report.response_id == "resp-1"
    assert report.input_tokens == 123
    assert report.output_tokens == 45


def test_provider_sends_exactly_one_image_and_disables_tools_and_storage():
    client = FakeClient(_response())
    provider = OpenAIGroundedVisualObservationProvider(client=client)

    provider.observe(_request())

    assert len(client.responses.calls) == 1
    call = client.responses.calls[0]
    content = call["input"][0]["content"]
    images = [item for item in content if item["type"] == "input_image"]
    assert len(images) == 1
    assert images[0]["image_url"].startswith("data:image/jpeg;base64,")
    assert call["tools"] == []
    assert call["store"] is False


def test_prompt_forbids_identity_guessing_and_prefers_missing_evidence():
    prompt = OPENAI_GROUNDED_OBSERVATION_PROMPT.casefold()
    for forbidden in (
        "do not identify",
        "do not guess",
        "country",
        "jurisdiction",
        "denomination",
        "year",
        "ruler",
        "catalogue",
        "mint",
        "authority",
    ):
        assert forbidden in prompt
    assert "missing evidence is preferred" in prompt


def test_prompt_requires_literal_full_face_transcription_without_reconstruction():
    prompt = OPENAI_GROUNDED_OBSERVATION_PROMPT.casefold()

    for required in (
        "literal transcription",
        "full coin face",
        "rim legend",
        "separate item",
        "alphabetic legends",
        "readable fragment",
        "do not fill",
        "second copy",
        "bare numeral",
    ):
        assert required in prompt
    for prohibited_behavior in (
        "do not translate",
        "normalize",
        "reconstruct",
        "silently correct",
        "complete",
    ):
        assert prohibited_behavior in prompt


def test_prompt_keeps_date_and_denomination_pixel_grounded():
    prompt = OPENAI_GROUNDED_OBSERVATION_PROMPT.casefold()

    assert "not permission to infer a year" in prompt
    assert "preserve a visible unit or currency mark" in prompt
    assert "do not turn a bare numeral into a denomination" in prompt


def test_schema_has_no_identity_or_confidence_fields():
    provider = OpenAIGroundedVisualObservationProvider(client=FakeClient(_response()))
    schema = provider.configuration["structured_output_schema"]
    properties = set(schema["properties"])
    assert properties == {
        "visible_text",
        "script",
        "portrait",
        "motifs",
        "construction",
        "shape",
        "date_like",
        "denomination_mark",
    }
    assert properties.isdisjoint(
        {"country", "jurisdiction", "identity", "candidates", "confidence"}
    )


def test_provider_rejects_wrong_request_type_before_api_call():
    client = FakeClient(_response())
    provider = OpenAIGroundedVisualObservationProvider(client=client)

    with pytest.raises(GroundedVisualObservationContractError):
        provider.observe(object())
    assert client.responses.calls == []


@pytest.mark.parametrize(
    "payload",
    [
        {"visible_text": []},
        {
            "visible_text": [""],
            "script": None,
            "portrait": None,
            "motifs": [],
            "construction": None,
            "shape": None,
            "date_like": None,
            "denomination_mark": None,
        },
        {
            "visible_text": ["ONE", "ONE"],
            "script": None,
            "portrait": None,
            "motifs": [],
            "construction": None,
            "shape": None,
            "date_like": None,
            "denomination_mark": None,
        },
    ],
)
def test_provider_rejects_malformed_structured_output(payload):
    provider = OpenAIGroundedVisualObservationProvider(
        client=FakeClient(_response(payload))
    )
    with pytest.raises(GroundedVisualObservationMalformedOutput):
        provider.observe(_request())


def test_provider_rejects_non_json_output():
    response = SimpleNamespace(
        output_text="not json",
        id="resp-1",
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
    )
    provider = OpenAIGroundedVisualObservationProvider(client=FakeClient(response))

    with pytest.raises(GroundedVisualObservationMalformedOutput):
        provider.observe(_request())


def test_invalid_usage_metadata_is_not_coerced():
    response = _response()
    response.usage = SimpleNamespace(input_tokens=True, output_tokens=-1)
    provider = OpenAIGroundedVisualObservationProvider(client=FakeClient(response))

    report = provider.observe(_request())

    assert report.input_tokens is None
    assert report.output_tokens is None


def test_non_json_failure_retains_safe_response_diagnostics():
    response = SimpleNamespace(
        output_text="",
        id="resp-malformed",
        status="incomplete",
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
        usage=SimpleNamespace(input_tokens=10, output_tokens=8),
    )
    provider = OpenAIGroundedVisualObservationProvider(client=FakeClient(response))

    with pytest.raises(GroundedVisualObservationMalformedOutput) as caught:
        provider.observe(_request())

    assert caught.value.diagnostics == {
        "response_id": "resp-malformed",
        "output_text_length": 0,
        "output_text_empty": True,
        "finish_reason": "max_output_tokens",
    }
    assert "output_text" not in caught.value.diagnostics
