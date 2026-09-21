from capture_import.catalogue_retrieval import CatalogueRetrievalResult
from capture_import.evidence_candidate_resolver import CatalogueCandidate
from capture_import.grounded_visual_observation import GroundedVisualObservation
from capture_import.two_side_candidate_verification import verify_retrieved_candidates


def _candidate(candidate_id="coin", *, denomination="25 cents", year="1955", legends=("CANADA", "ELIZABETH II")):
    return CatalogueCandidate(candidate_id, "Canada", denomination, year, legends=legends)


def _result(*candidates):
    return CatalogueRetrievalResult(tuple(candidates), "fixture")


def test_candidate_with_structured_match_and_text_support_verifies():
    report = verify_retrieved_candidates(
        _result(_candidate()),
        (
            GroundedVisualObservation(
                role="obverse", date_like="1955", visible_text=("ELIZABETH",)
            ),
            GroundedVisualObservation(
                role="reverse", denomination_mark="25 CENTS", visible_text=("CANADA",)
            ),
        ),
    )

    row = report.rows[0]
    assert row.verified
    assert row.matched_fields == ("year", "denomination", "visible_text")
    assert row.supporting_roles == ("obverse", "reverse")


def test_single_side_can_verify_but_role_provenance_is_explicit():
    report = verify_retrieved_candidates(
        _result(_candidate()),
        (
            GroundedVisualObservation(
                role="obverse",
                date_like="1955",
                visible_text=("CANADA",),
            ),
        ),
    )

    assert report.rows[0].verified
    assert report.rows[0].supporting_roles == ("obverse",)
    assert report.observation_roles == ("obverse",)


def test_structured_conflict_prevents_verification():
    report = verify_retrieved_candidates(
        _result(_candidate(year="1956")),
        (
            GroundedVisualObservation(
                role="obverse", date_like="1955", visible_text=("CANADA",)
            ),
        ),
    )

    row = report.rows[0]
    assert not row.verified
    assert row.conflicting_fields == ("year",)


def test_text_without_strong_structured_match_is_not_verified():
    report = verify_retrieved_candidates(
        _result(_candidate()),
        (GroundedVisualObservation(role="obverse", visible_text=("CANADA",)),),
    )

    row = report.rows[0]
    assert row.matched_fields == ("visible_text",)
    assert not row.verified


def test_strong_match_without_text_support_is_not_verified():
    report = verify_retrieved_candidates(
        _result(_candidate()),
        (GroundedVisualObservation(role="obverse", date_like="1955"),),
    )

    row = report.rows[0]
    assert row.matched_fields == ("year",)
    assert not row.verified


def test_multiple_candidates_are_verified_independently_in_retrieval_order():
    report = verify_retrieved_candidates(
        _result(
            _candidate("match"),
            _candidate("wrong-year", year="1956"),
        ),
        (
            GroundedVisualObservation(
                role="obverse", date_like="1955", visible_text=("CANADA",)
            ),
        ),
    )

    assert [row.candidate.candidate_id for row in report.rows] == ["match", "wrong-year"]
    assert report.rows[0].verified
    assert not report.rows[1].verified


def test_conflicting_observed_dates_fail_closed_before_candidate_verification():
    report = verify_retrieved_candidates(
        _result(_candidate()),
        (
            GroundedVisualObservation(role="obverse", date_like="1955"),
            GroundedVisualObservation(role="reverse", date_like="1956"),
        ),
    )

    assert report.has_evidence_conflict
    assert report.rows == ()


def test_duplicate_roles_are_rejected_by_grounded_evidence_contract():
    try:
        verify_retrieved_candidates(
            _result(_candidate()),
            (
                GroundedVisualObservation(role="obverse", date_like="1955"),
                GroundedVisualObservation(role="obverse", visible_text=("CANADA",)),
            ),
        )
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_empty_retrieval_result_produces_empty_verification_rows():
    report = verify_retrieved_candidates(
        _result(),
        (GroundedVisualObservation(role="obverse", visible_text=("CANADA",)),),
    )

    assert report.rows == ()
    assert not report.has_evidence_conflict


def test_verification_has_no_acceptance_identity_or_confidence_fields():
    report = verify_retrieved_candidates(
        _result(_candidate()),
        (
            GroundedVisualObservation(
                role="obverse", date_like="1955", visible_text=("CANADA",)
            ),
        ),
    )

    assert not hasattr(report, "accepted")
    assert not hasattr(report, "identity")
    assert not hasattr(report, "confidence")
    assert not hasattr(report.rows[0], "accepted")
    assert not hasattr(report.rows[0], "confidence")
