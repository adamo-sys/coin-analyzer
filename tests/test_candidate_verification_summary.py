from capture_import.candidate_verification_summary import (
    VerificationDisposition,
    summarize_candidate_verification,
)
from capture_import.evidence_candidate_resolver import CatalogueCandidate
from capture_import.two_side_candidate_verification import (
    CandidateVerification,
    CandidateVerificationReport,
)


def _row(candidate_id, *, verified):
    return CandidateVerification(
        candidate=CatalogueCandidate(
            candidate_id=candidate_id,
            country="Canada",
            denomination="25 cents",
            year="1955",
        ),
        matched_fields=("year",) if verified else (),
        conflicting_fields=() if verified else ("year",),
        supporting_roles=("obverse",) if verified else (),
        supporting_text=("CANADA",) if verified else (),
        verified=verified,
    )


def _report(*rows, conflict=False):
    return CandidateVerificationReport(
        rows=tuple(rows),
        observation_roles=("obverse", "reverse"),
        has_evidence_conflict=conflict,
    )


def test_evidence_conflict_takes_precedence():
    summary = summarize_candidate_verification(_report(conflict=True))

    assert summary.disposition is VerificationDisposition.EVIDENCE_CONFLICT
    assert not summary.ready_for_final_gate


def test_no_candidates_is_explicit():
    summary = summarize_candidate_verification(_report())

    assert summary.disposition is VerificationDisposition.NO_CANDIDATES
    assert summary.candidate_count == 0
    assert summary.verified_count == 0
    assert not summary.ready_for_final_gate


def test_none_verified_is_explicit():
    summary = summarize_candidate_verification(
        _report(_row("a", verified=False), _row("b", verified=False))
    )

    assert summary.disposition is VerificationDisposition.NONE_VERIFIED
    assert summary.verified_candidate_ids == ()
    assert summary.rejected_candidate_ids == ("a", "b")
    assert not summary.ready_for_final_gate


def test_unique_verified_is_ready_for_final_gate_but_not_accepted():
    summary = summarize_candidate_verification(
        _report(_row("a", verified=True), _row("b", verified=False))
    )

    assert summary.disposition is VerificationDisposition.UNIQUE_VERIFIED
    assert summary.verified_count == 1
    assert summary.verified_candidate_ids == ("a",)
    assert summary.rejected_candidate_ids == ("b",)
    assert summary.ready_for_final_gate
    assert not hasattr(summary, "accepted")
    assert not hasattr(summary, "identity")


def test_multiple_verified_candidates_remain_ambiguous():
    summary = summarize_candidate_verification(
        _report(_row("a", verified=True), _row("b", verified=True))
    )

    assert summary.disposition is VerificationDisposition.AMBIGUOUS_VERIFIED
    assert summary.verified_count == 2
    assert summary.verified_candidate_ids == ("a", "b")
    assert not summary.ready_for_final_gate


def test_report_order_is_preserved_in_summary_ids():
    summary = summarize_candidate_verification(
        _report(
            _row("z", verified=False),
            _row("b", verified=True),
            _row("a", verified=False),
        )
    )

    assert summary.verified_candidate_ids == ("b",)
    assert summary.rejected_candidate_ids == ("z", "a")
    assert summary.observation_roles == ("obverse", "reverse")


def test_wrong_input_type_is_rejected():
    try:
        summarize_candidate_verification(object())
    except TypeError as exc:
        assert "CandidateVerificationReport" in str(exc)
    else:
        raise AssertionError("expected TypeError")


def test_summary_has_no_confidence_or_winner_semantics():
    summary = summarize_candidate_verification(
        _report(_row("a", verified=True))
    )

    assert not hasattr(summary, "confidence")
    assert not hasattr(summary, "winner")
    assert not hasattr(summary, "accepted")
