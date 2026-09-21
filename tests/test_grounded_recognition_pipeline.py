from capture_import.catalogue_retrieval import CatalogueRetrievalResult
from capture_import.evidence_candidate_resolver import CatalogueCandidate
from capture_import.grounded_recognition_pipeline import run_grounded_recognition_pipeline
from capture_import.grounded_visual_observation import GroundedVisualObservation
from capture_import.in_memory_catalogue_retriever import InMemoryCatalogueRetriever
from capture_import.recognition_decision_gate import RecognitionDecision


def _candidate(candidate_id="coin", *, denomination="25 cents", year="1955"):
    return CatalogueCandidate(
        candidate_id,
        "Canada",
        denomination,
        year,
        legends=("ELIZABETH II", "CANADA"),
    )


def _sides():
    return (
        GroundedVisualObservation(
            role="obverse",
            date_like="1955",
            visible_text=("ELIZABETH",),
        ),
        GroundedVisualObservation(
            role="reverse",
            denomination_mark="25 CENTS",
            visible_text=("CANADA",),
        ),
    )


def test_pipeline_identifies_unique_two_side_supported_candidate():
    result = run_grounded_recognition_pipeline(
        _sides(),
        InMemoryCatalogueRetriever((_candidate(),)),
    )

    assert result.decision.decision is RecognitionDecision.IDENTIFY
    assert result.decision.candidate_id == "coin"
    assert result.retrieval is not None
    assert result.verification is not None
    assert result.summary is not None


def test_pipeline_abstains_when_retrieval_is_ambiguous():
    result = run_grounded_recognition_pipeline(
        _sides(),
        InMemoryCatalogueRetriever((_candidate("a"), _candidate("b"))),
    )

    assert result.decision.decision is RecognitionDecision.ABSTAIN
    assert result.decision.reason == "ambiguous_verified"


def test_pipeline_abstains_when_catalogue_has_no_matching_candidate():
    result = run_grounded_recognition_pipeline(
        _sides(),
        InMemoryCatalogueRetriever(
            (_candidate("wrong", denomination="10 cents", year="1968"),)
        ),
    )

    assert result.decision.decision is RecognitionDecision.ABSTAIN
    assert result.decision.reason == "no_candidates"


def test_pipeline_abstains_before_retrieval_on_conflicting_evidence():
    class MustNotRun:
        @property
        def retriever_id(self):
            return "must-not-run"

        def retrieve(self, request):
            raise AssertionError("retrieval must not run")

    sides = (
        GroundedVisualObservation(role="obverse", date_like="1955"),
        GroundedVisualObservation(role="reverse", date_like="1956"),
    )
    result = run_grounded_recognition_pipeline(sides, MustNotRun())

    assert result.decision.decision is RecognitionDecision.ABSTAIN
    assert result.retrieval is None
    assert result.verification is None
    assert result.summary is None


def test_pipeline_abstains_before_retrieval_on_empty_evidence():
    class MustNotRun:
        @property
        def retriever_id(self):
            return "must-not-run"

        def retrieve(self, request):
            raise AssertionError("retrieval must not run")

    result = run_grounded_recognition_pipeline(
        (GroundedVisualObservation(role="obverse"),),
        MustNotRun(),
    )

    assert result.decision.decision is RecognitionDecision.ABSTAIN
    assert result.retrieval is None


def test_pipeline_one_side_evidence_cannot_identify():
    result = run_grounded_recognition_pipeline(
        (
            GroundedVisualObservation(
                role="obverse",
                date_like="1955",
                visible_text=("CANADA",),
            ),
        ),
        InMemoryCatalogueRetriever((_candidate(),)),
    )

    assert result.decision.decision is RecognitionDecision.ABSTAIN
    assert result.decision.reason == "two_side_support_required"


def test_pipeline_preserves_retriever_provenance():
    result = run_grounded_recognition_pipeline(
        _sides(),
        InMemoryCatalogueRetriever(
            (_candidate(),),
            retriever_id="fixture-catalogue",
        ),
        retrieval_limit=5,
    )

    assert result.retrieval is not None
    assert result.retrieval.retriever_id == "fixture-catalogue"
    assert result.retrieval.query_id is not None


def test_pipeline_rejects_invalid_retriever_result_type():
    class BadRetriever:
        @property
        def retriever_id(self):
            return "bad"

        def retrieve(self, request):
            return object()

    try:
        run_grounded_recognition_pipeline(_sides(), BadRetriever())
    except TypeError as exc:
        assert "CatalogueRetrievalResult" in str(exc)
    else:
        raise AssertionError("expected TypeError")


def test_pipeline_has_no_model_confidence_surface():
    result = run_grounded_recognition_pipeline(
        _sides(),
        InMemoryCatalogueRetriever((_candidate(),)),
    )

    assert not hasattr(result, "confidence")
    assert not hasattr(result.decision, "confidence")
