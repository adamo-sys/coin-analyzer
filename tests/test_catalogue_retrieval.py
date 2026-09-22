import pytest

from capture_import.catalogue_retrieval import (
    CatalogueRetrievalContractError,
    CatalogueRetrievalRequest,
    CatalogueRetrievalResult,
    CatalogueRetriever,
    request_from_numeral_envelope,
)
from capture_import.evidence_candidate_resolver import CatalogueCandidate, NormalizedEvidence
from capture_import.grounded_visual_observation import GroundedVisualObservation
from capture_import.numeral_evidence_envelope import build_numeral_evidence_envelope


def _candidate(candidate_id="coin-1"):
    return CatalogueCandidate(
        candidate_id=candidate_id,
        country="Canada",
        denomination="25 cents",
        year="1955",
    )


def test_request_accepts_bounded_grounded_evidence():
    request = CatalogueRetrievalRequest(
        evidence=NormalizedEvidence(
            country=None,
            denomination="25 cents",
            year="1955",
            visible_text=("CANADA",),
        ),
        limit=5,
    )

    assert request.limit == 5
    assert request.evidence.country is None


@pytest.mark.parametrize("limit", [0, 26, -1])
def test_request_rejects_out_of_bounds_limits(limit):
    with pytest.raises(CatalogueRetrievalContractError, match="limit"):
        CatalogueRetrievalRequest(
            evidence=NormalizedEvidence(None, None, "1955"),
            limit=limit,
        )


def test_request_rejects_empty_evidence():
    with pytest.raises(CatalogueRetrievalContractError, match="signal"):
        CatalogueRetrievalRequest(
            evidence=NormalizedEvidence(None, None, None),
        )


def test_request_from_ready_envelope_preserves_normalized_evidence():
    envelope = build_numeral_evidence_envelope(
        (
            GroundedVisualObservation(
                role="obverse",
                date_like="1955",
                denomination_mark="25 CENTS",
                visible_text=("CANADA",),
            ),
        )
    )

    request = request_from_numeral_envelope(envelope, limit=7)

    assert request.evidence is envelope.normalized
    assert request.limit == 7


def test_conflicting_envelope_fails_closed_before_retrieval():
    envelope = build_numeral_evidence_envelope(
        (
            GroundedVisualObservation(role="obverse", date_like="1955"),
            GroundedVisualObservation(role="reverse", date_like="1956"),
        )
    )

    with pytest.raises(CatalogueRetrievalContractError, match="conflicting"):
        request_from_numeral_envelope(envelope)


def test_empty_envelope_fails_closed_before_retrieval():
    envelope = build_numeral_evidence_envelope(
        (GroundedVisualObservation(role="obverse"),)
    )

    with pytest.raises(CatalogueRetrievalContractError, match="not retrieval-ready"):
        request_from_numeral_envelope(envelope)


def test_result_preserves_order_and_provenance():
    first = _candidate("a")
    second = _candidate("b")
    result = CatalogueRetrievalResult(
        candidates=(first, second),
        retriever_id="fixture-catalogue",
        query_id="query-123",
    )

    assert result.candidates == (first, second)
    assert result.retriever_id == "fixture-catalogue"
    assert result.query_id == "query-123"


def test_result_rejects_duplicate_candidate_ids():
    with pytest.raises(CatalogueRetrievalContractError, match="unique"):
        CatalogueRetrievalResult(
            candidates=(_candidate("same"), _candidate("same")),
            retriever_id="fixture-catalogue",
        )


def test_result_allows_empty_candidate_set_for_no_match():
    result = CatalogueRetrievalResult(
        candidates=(),
        retriever_id="fixture-catalogue",
    )

    assert result.candidates == ()


def test_runtime_protocol_is_provider_neutral():
    class FixtureRetriever:
        @property
        def retriever_id(self):
            return "fixture"

        def retrieve(self, request):
            return CatalogueRetrievalResult((), self.retriever_id)

    assert isinstance(FixtureRetriever(), CatalogueRetriever)


def test_contract_has_no_acceptance_or_confidence_semantics():
    result = CatalogueRetrievalResult(
        candidates=(_candidate(),),
        retriever_id="fixture",
    )

    assert not hasattr(result, "accepted")
    assert not hasattr(result, "confidence")
    assert not hasattr(result, "identity")
