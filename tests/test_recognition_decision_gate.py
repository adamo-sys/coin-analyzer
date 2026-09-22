from capture_import.candidate_verification_summary import summarize_candidate_verification
from capture_import.evidence_candidate_resolver import CatalogueCandidate
from capture_import.recognition_decision_gate import RecognitionDecision, decide_identity
from capture_import.two_side_candidate_verification import CandidateVerification, CandidateVerificationReport


def _row(candidate_id="coin", *, verified=True, roles=("obverse", "reverse"), matched=("year", "visible_text"), conflicts=()):
    return CandidateVerification(
        candidate=CatalogueCandidate(candidate_id, "Canada", "25 cents", "1955"),
        matched_fields=matched,
        conflicting_fields=conflicts,
        supporting_roles=roles,
        supporting_text=("ELIZABETH", "CANADA") if roles else (),
        verified=verified,
    )


def _report(*rows, roles=("obverse", "reverse"), conflict=False):
    return CandidateVerificationReport(tuple(rows), roles, conflict)


def _decide(report):
    return decide_identity(report, summarize_candidate_verification(report))


def test_unique_verified_candidate_with_two_side_support_identifies():
    result = _decide(_report(_row()))

    assert result.decision is RecognitionDecision.IDENTIFY
    assert result.candidate_id == "coin"
    assert result.reason == "unique_verified_candidate_with_two_side_support"


def test_one_side_support_abstains_even_when_candidate_verified():
    result = _decide(_report(_row(roles=("obverse",)), roles=("obverse",)))

    assert result.decision is RecognitionDecision.ABSTAIN
    assert result.candidate_id is None
    assert result.reason == "two_side_support_required"


def test_ambiguous_verified_candidates_abstain():
    result = _decide(_report(_row("a"), _row("b")))

    assert result.decision is RecognitionDecision.ABSTAIN
    assert result.reason == "ambiguous_verified"


def test_no_verified_candidate_abstains():
    result = _decide(_report(_row(verified=False, roles=(), matched=())))

    assert result.decision is RecognitionDecision.ABSTAIN
    assert result.reason == "none_verified"


def test_no_candidates_abstains():
    result = _decide(_report())

    assert result.decision is RecognitionDecision.ABSTAIN
    assert result.reason == "no_candidates"


def test_evidence_conflict_abstains():
    result = _decide(_report(conflict=True))

    assert result.decision is RecognitionDecision.ABSTAIN
    assert result.reason == "evidence_conflict"


def test_missing_strong_structured_match_abstains():
    report = _report(_row(matched=("visible_text",)))
    summary = summarize_candidate_verification(report)

    result = decide_identity(report, summary)

    assert result.decision is RecognitionDecision.ABSTAIN
    assert result.reason == "insufficient_consistent_evidence"


def test_conflicting_verified_row_abstains_fail_closed():
    report = _report(_row(conflicts=("year",)))
    summary = summarize_candidate_verification(report)

    result = decide_identity(report, summary)

    assert result.decision is RecognitionDecision.ABSTAIN
    assert result.reason == "insufficient_consistent_evidence"


def test_summary_report_role_mismatch_is_rejected():
    report = _report(_row())
    summary = summarize_candidate_verification(report)
    mismatched_report = _report(_row(), roles=("obverse",))

    try:
        decide_identity(mismatched_report, summary)
    except ValueError as exc:
        assert "roles" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_summary_candidate_mismatch_abstains():
    report = _report(_row("actual"))
    other_report = _report(_row("other"))
    summary = summarize_candidate_verification(other_report)

    result = decide_identity(report, summary)

    assert result.decision is RecognitionDecision.ABSTAIN
    assert result.reason == "verification_summary_mismatch"


def test_gate_exposes_no_model_confidence():
    result = _decide(_report(_row()))

    assert not hasattr(result, "confidence")
    assert not hasattr(result, "model_score")
