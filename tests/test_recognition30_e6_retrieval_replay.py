import pytest

from capture_import.evidence_candidate_resolver import CatalogueCandidate
from capture_import.recognition30_e6_retrieval_replay import (
    enrich_catalogue,
    replay,
    summarize,
)


def _candidate(candidate_id, country, denomination="10 cents", year="1970"):
    return CatalogueCandidate(
        candidate_id=candidate_id,
        country=country,
        denomination=denomination,
        year=year,
    )


def _report(case_id, *, visible_text=(), date_like=None, denomination_mark=None):
    return {
        "rows": [
            {
                "case_id": case_id,
                "observations": [
                    {
                        "role": "obverse",
                        "visible_text": list(visible_text),
                        "date_like": date_like,
                        "denomination_mark": denomination_mark,
                    },
                    {
                        "role": "reverse",
                        "visible_text": [],
                        "date_like": None,
                        "denomination_mark": None,
                    },
                ],
            }
        ]
    }


def test_enrichment_adds_known_country_alias_without_using_observation():
    candidate = _candidate("sweden", "Sweden")

    enriched = enrich_catalogue((candidate,))

    assert "sverige" in enriched[0].legends
    assert candidate.legends == ()


def test_treatment_can_rescue_alias_only_retrieval():
    rows = replay(
        _report("sweden", visible_text=("SVERIGE",)),
        (
            _candidate("sweden", "Sweden"),
            _candidate("canada", "Canada"),
        ),
    )

    assert rows[0].control_hit is False
    assert rows[0].treatment_hit is True
    assert rows[0].treatment_ids == ("sweden",)


def test_control_is_same_sparse_exact_signal_retrieval():
    rows = replay(
        _report("sweden", date_like="1970", denomination_mark="10 cents"),
        (
            _candidate("sweden", "Sweden"),
            _candidate("other", "Canada", year="1971"),
        ),
    )

    assert rows[0].control_hit is True
    assert rows[0].treatment_hit is True


def test_conflicting_observations_fail_closed_for_both_arms():
    report = {
        "rows": [
            {
                "case_id": "sweden",
                "observations": [
                    {
                        "role": "obverse",
                        "visible_text": [],
                        "date_like": "1970",
                        "denomination_mark": None,
                    },
                    {
                        "role": "reverse",
                        "visible_text": [],
                        "date_like": "1971",
                        "denomination_mark": None,
                    },
                ],
            }
        ]
    }

    rows = replay(report, (_candidate("sweden", "Sweden"),))

    assert rows[0].control_ids == ()
    assert rows[0].treatment_ids == ()
    assert rows[0].request_error is not None


def test_summary_reports_recall_delta_without_identity_claims():
    rows = replay(
        _report("sweden", visible_text=("SVERIGE",)),
        (_candidate("sweden", "Sweden"),),
    )

    result = summarize(rows)

    assert result["cases"] == 1
    assert result["control_hits_at_10"] == 0
    assert result["treatment_hits_at_10"] == 1
    assert result["control_recall_at_10"] == pytest.approx(0.0)
    assert result["treatment_recall_at_10"] == pytest.approx(1.0)
    assert result["delta_hits_at_10"] == 1
    assert "accuracy" not in result
