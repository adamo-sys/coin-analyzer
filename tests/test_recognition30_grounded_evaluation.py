from capture_import.recognition30_grounded_evaluation import (
    aggregate_metrics,
    compare_to_baseline,
    evaluate_case,
)
from capture_import.recognition_decision_gate import RecognitionDecision, RecognitionGateResult


def _decision(kind, candidate_id=None, reason="fixture"):
    return RecognitionGateResult(kind, candidate_id, reason, ("obverse", "reverse"))


def test_correct_identification_is_counted_only_after_final_gate():
    outcome = evaluate_case(
        case_id="CA-R30-017",
        expected_candidate_id="CA-R30-017",
        decision=_decision(RecognitionDecision.IDENTIFY, "CA-R30-017"),
    )

    assert outcome.correct
    assert not outcome.abstain
    assert not outcome.unsafe_wrong_identification


def test_wrong_identification_is_explicitly_unsafe():
    outcome = evaluate_case(
        case_id="CA-R30-017",
        expected_candidate_id="CA-R30-017",
        decision=_decision(RecognitionDecision.IDENTIFY, "CA-R30-014"),
    )

    assert not outcome.correct
    assert outcome.unsafe_wrong_identification


def test_abstention_is_not_scored_as_unsafe_wrong_identity():
    outcome = evaluate_case(
        case_id="CA-R30-001",
        expected_candidate_id="CA-R30-001",
        decision=_decision(RecognitionDecision.ABSTAIN),
    )

    assert outcome.abstain
    assert not outcome.correct
    assert not outcome.unsafe_wrong_identification


def test_metrics_separate_accuracy_coverage_selective_accuracy_and_safety():
    outcomes = (
        evaluate_case(
            case_id="a",
            expected_candidate_id="a",
            decision=_decision(RecognitionDecision.IDENTIFY, "a"),
        ),
        evaluate_case(
            case_id="b",
            expected_candidate_id="b",
            decision=_decision(RecognitionDecision.IDENTIFY, "x"),
        ),
        evaluate_case(
            case_id="c",
            expected_candidate_id="c",
            decision=_decision(RecognitionDecision.ABSTAIN),
        ),
    )
    metrics = aggregate_metrics(outcomes)

    assert metrics.total_cases == 3
    assert metrics.identified_cases == 2
    assert metrics.correct_cases == 1
    assert metrics.abstained_cases == 1
    assert metrics.unsafe_wrong_identifications == 1
    assert metrics.full_identity_accuracy == 1 / 3
    assert metrics.coverage == 2 / 3
    assert metrics.selective_accuracy == 1 / 2
    assert metrics.unsafe_wrong_identification_rate == 1 / 3


def test_all_abstain_has_zero_coverage_and_undefined_selective_accuracy():
    metrics = aggregate_metrics(
        (
            evaluate_case(
                case_id="a",
                expected_candidate_id="a",
                decision=_decision(RecognitionDecision.ABSTAIN),
            ),
        )
    )

    assert metrics.coverage == 0
    assert metrics.selective_accuracy is None
    assert metrics.unsafe_wrong_identification_rate == 0


def test_empty_metrics_are_defined_without_division_by_zero():
    metrics = aggregate_metrics(())

    assert metrics.total_cases == 0
    assert metrics.full_identity_accuracy is None
    assert metrics.coverage is None
    assert metrics.selective_accuracy is None
    assert metrics.unsafe_wrong_identification_rate is None


def test_duplicate_case_ids_fail_closed():
    row = evaluate_case(
        case_id="a",
        expected_candidate_id="a",
        decision=_decision(RecognitionDecision.ABSTAIN),
    )

    try:
        aggregate_metrics((row, row))
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_frozen_baseline_comparison_defaults_to_one_of_thirty():
    metrics = aggregate_metrics(
        (
            evaluate_case(
                case_id="a",
                expected_candidate_id="a",
                decision=_decision(RecognitionDecision.IDENTIFY, "a"),
            ),
        )
    )
    comparison = compare_to_baseline(metrics)

    assert comparison["baseline_correct"] == 1
    assert comparison["baseline_total"] == 30
    assert comparison["baseline_accuracy"] == 1 / 30
    assert comparison["grounded_accuracy"] == 1.0
    assert comparison["accuracy_delta"] == 1.0 - (1 / 30)


def test_evaluation_surface_has_no_model_confidence():
    outcome = evaluate_case(
        case_id="a",
        expected_candidate_id="a",
        decision=_decision(RecognitionDecision.IDENTIFY, "a"),
    )

    assert not hasattr(outcome, "confidence")
    assert not hasattr(outcome, "model_score")
