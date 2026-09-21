from capture_import.catalogue_retrieval import CatalogueRetrievalResult
from capture_import.catalogue_retrieval_diagnostics import (
    RetrievalDisposition,
    diagnose_retrieval,
)
from capture_import.evidence_candidate_resolver import CatalogueCandidate, NormalizedEvidence


def _candidate(candidate_id, *, denomination="25 cents", year="1955"):
    return CatalogueCandidate(
        candidate_id=candidate_id,
        country="Canada",
        denomination=denomination,
        year=year,
    )


def _result(*candidates):
    return CatalogueRetrievalResult(
        candidates=tuple(candidates),
        retriever_id="fixture",
    )


def _evidence(*, denomination="25 cents", year="1955"):
    return NormalizedEvidence(
        country=None,
        denomination=denomination,
        year=year,
    )


def test_no_match_is_explicit_and_needs_no_candidate_verification():
    diagnostics = diagnose_retrieval(_result(), _evidence())

    assert diagnostics.disposition is RetrievalDisposition.NO_MATCH
    assert diagnostics.candidate_count == 0
    assert diagnostics.candidate_ids == ()
    assert not diagnostics.needs_verification


def test_single_candidate_is_not_accepted_implicitly():
    diagnostics = diagnose_retrieval(
        _result(_candidate("only")),
        _evidence(),
    )

    assert diagnostics.disposition is RetrievalDisposition.SINGLE
    assert diagnostics.candidate_count == 1
    assert diagnostics.joint_match_count == 1
    assert diagnostics.needs_verification
    assert not hasattr(diagnostics, "accepted")


def test_two_to_five_candidates_are_narrow():
    diagnostics = diagnose_retrieval(
        _result(_candidate("a"), _candidate("b"), _candidate("c")),
        _evidence(),
    )

    assert diagnostics.disposition is RetrievalDisposition.NARROW
    assert diagnostics.candidate_count == 3
    assert diagnostics.joint_match_count == 3


def test_more_than_five_candidates_are_broad():
    diagnostics = diagnose_retrieval(
        _result(*(_candidate(str(index)) for index in range(6))),
        _evidence(),
    )

    assert diagnostics.disposition is RetrievalDisposition.BROAD
    assert diagnostics.candidate_count == 6


def test_match_counts_distinguish_exact_from_partial_candidates():
    diagnostics = diagnose_retrieval(
        _result(
            _candidate("joint"),
            _candidate("year-only", denomination="10 cents"),
            _candidate("denom-only", year="1956"),
            _candidate("neither", denomination="10 cents", year="1956"),
        ),
        _evidence(),
    )

    assert diagnostics.year_match_count == 2
    assert diagnostics.denomination_match_count == 2
    assert diagnostics.joint_match_count == 1


def test_year_only_evidence_counts_joint_matches_on_supplied_fields():
    diagnostics = diagnose_retrieval(
        _result(
            _candidate("match", denomination="10 cents"),
            _candidate("miss", denomination="25 cents", year="1956"),
        ),
        _evidence(denomination=None),
    )

    assert diagnostics.year_match_count == 1
    assert diagnostics.denomination_match_count == 0
    assert diagnostics.joint_match_count == 1


def test_denomination_only_evidence_counts_joint_matches_on_supplied_fields():
    diagnostics = diagnose_retrieval(
        _result(
            _candidate("match", year="1956"),
            _candidate("miss", denomination="10 cents", year="1955"),
        ),
        _evidence(year=None),
    )

    assert diagnostics.year_match_count == 0
    assert diagnostics.denomination_match_count == 1
    assert diagnostics.joint_match_count == 1


def test_candidate_order_is_preserved_for_diagnostics():
    diagnostics = diagnose_retrieval(
        _result(_candidate("z"), _candidate("a")),
        _evidence(),
    )

    assert diagnostics.candidate_ids == ("z", "a")


def test_diagnostics_have_no_identity_confidence_or_winner_semantics():
    diagnostics = diagnose_retrieval(
        _result(_candidate("a")),
        _evidence(),
    )

    assert not hasattr(diagnostics, "identity")
    assert not hasattr(diagnostics, "confidence")
    assert not hasattr(diagnostics, "winner")
    assert not hasattr(diagnostics, "accepted")


def test_wrong_input_types_fail_closed():
    try:
        diagnose_retrieval(object(), _evidence())
    except TypeError as exc:
        assert "CatalogueRetrievalResult" in str(exc)
    else:
        raise AssertionError("expected TypeError")

    try:
        diagnose_retrieval(_result(), object())
    except TypeError as exc:
        assert "NormalizedEvidence" in str(exc)
    else:
        raise AssertionError("expected TypeError")
