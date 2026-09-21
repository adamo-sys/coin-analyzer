from capture_import.observation_quality_evaluation import (
    compare_view_pairs,
    evaluate_view_quality,
    evaluate_execution_accounting,
)


def _row(view, role, text=(), date=None, denomination=None, tokens=100):
    return {
        "view": view,
        "role": role,
        "visible_text": list(text),
        "date_like": date,
        "denomination_mark": denomination,
        "input_tokens": tokens,
        "output_tokens": 10,
    }


def test_view_quality_measures_yield_and_cost_without_identity_truth():
    rows = (
        _row("full_face", "obverse", ("1968", "2 NT$"), "1968", "2 NT$", 110),
        _row("rim", "obverse", (), tokens=90),
        _row("full_face", "reverse", ("LIBERTAS",), tokens=100),
        _row("rim", "reverse", ("LIBERTAS",), tokens=80),
    )

    quality = {item.view: item for item in evaluate_view_quality(rows)}

    assert quality["full_face"].observations == 2
    assert quality["full_face"].observations_with_text == 2
    assert quality["full_face"].unique_text_items == 3
    assert quality["full_face"].date_yield == 1
    assert quality["full_face"].denomination_yield == 1
    assert quality["full_face"].input_tokens == 210
    assert quality["rim"].observations_with_text == 1
    assert quality["rim"].unique_text_items == 1
    assert quality["rim"].input_tokens == 170


def test_pair_comparison_exposes_incremental_and_duplicate_rim_text():
    rows = (
        _row("full_face", "obverse", ("1968", "2 NT$"), "1968", "2 NT$", 110),
        _row("rim", "obverse", ("HELVETIA",), tokens=90),
        _row("full_face", "reverse", ("LIBERTAS",), tokens=100),
        _row("rim", "reverse", ("LIBERTAS",), tokens=80),
    )

    pairs = {item.role: item for item in compare_view_pairs(rows)}

    assert pairs["obverse"].incremental_comparison_text == ("HELVETIA",)
    assert pairs["obverse"].shared_text == ()
    assert pairs["reverse"].incremental_comparison_text == ()
    assert pairs["reverse"].shared_text == ("LIBERTAS",)
    assert pairs["obverse"].comparison_input_tokens == 90


def test_pair_comparison_reports_structured_agreement_without_forcing_missing():
    rows = (
        _row("full_face", "obverse", ("1968",), "1968"),
        _row("rim", "obverse", ("1968",), "1968"),
        _row("full_face", "reverse", ("5 FR",), denomination="5 FR"),
        _row("rim", "reverse", ()),
    )

    pairs = {item.role: item for item in compare_view_pairs(rows)}

    assert pairs["obverse"].date_agreement is True
    assert pairs["reverse"].denomination_agreement is None


def test_pair_comparison_is_truth_free_and_does_not_score_identity():
    rows = (
        _row("full_face", "obverse", ("WRONG",)),
        _row("rim", "obverse", ("ALSO WRONG",)),
    )

    pair = compare_view_pairs(rows)[0]

    assert pair.incremental_comparison_text == ("ALSO WRONG",)
    assert not hasattr(pair, "correct")
    assert not hasattr(pair, "candidate_id")


def test_execution_accounting_counts_success_failures_and_avoided_calls():
    rows = (
        {
            "view_provenance": (
                {"view": "full_face", "input_tokens": 100, "output_tokens": 10},
                {"view": "rim", "input_tokens": 90, "output_tokens": 9},
            ),
            "provider_failures": (),
        },
        {
            "view_provenance": (
                {"view": "full_face", "input_tokens": 110, "output_tokens": 11},
            ),
            "provider_failures": (
                {"view": "rim", "error_type": "Malformed"},
            ),
        },
    )

    accounting = evaluate_execution_accounting(rows)

    assert accounting.cases == 2
    assert accounting.successful_calls == 3
    assert accounting.failed_calls == 1
    assert accounting.attempted_calls == 4
    assert accounting.maximum_two_view_calls == 8
    assert accounting.avoided_calls == 4
    assert accounting.input_tokens == 300
    assert accounting.output_tokens == 30
