import pytest

from capture_import.catalogue_retrieval import (
    CatalogueRetrievalContractError,
    CatalogueRetrievalRequest,
    CatalogueRetriever,
)
from capture_import.evidence_candidate_resolver import CatalogueCandidate, NormalizedEvidence
from capture_import.in_memory_catalogue_retriever import InMemoryCatalogueRetriever


def _candidate(
    candidate_id,
    country="Canada",
    denomination="25 cents",
    year="1955",
    legends=(),
):
    return CatalogueCandidate(
        candidate_id=candidate_id,
        country=country,
        denomination=denomination,
        year=year,
        legends=legends,
    )


def _request(*, year=None, denomination=None, visible_text=(), limit=10):
    return CatalogueRetrievalRequest(
        evidence=NormalizedEvidence(
            country=None,
            denomination=denomination,
            year=year,
            visible_text=visible_text,
        ),
        limit=limit,
    )


def test_retriever_satisfies_provider_neutral_protocol():
    retriever = InMemoryCatalogueRetriever((_candidate("a"),))

    assert isinstance(retriever, CatalogueRetriever)


def test_exact_year_and_denomination_rank_before_partial_matches():
    retriever = InMemoryCatalogueRetriever(
        (
            _candidate("exact"),
            _candidate("year-only", denomination="10 cents"),
            _candidate("denom-only", year="1956"),
        )
    )

    result = retriever.retrieve(
        _request(year="1955", denomination="25 cents")
    )

    assert [item.candidate_id for item in result.candidates] == [
        "exact",
        "year-only",
        "denom-only",
    ]


def test_visible_text_matches_country_and_legend_tokens():
    retriever = InMemoryCatalogueRetriever(
        (
            _candidate("canada", legends=("ELIZABETH II",)),
            _candidate(
                "france",
                country="France",
                denomination="2 francs",
                year="1955",
                legends=("REPUBLIQUE FRANCAISE",),
            ),
        )
    )

    result = retriever.retrieve(
        _request(visible_text=("CANADA", "ELIZABETH"))
    )

    assert [item.candidate_id for item in result.candidates] == ["canada"]


def test_observed_espana_matches_spain_country_token():
    retriever = InMemoryCatalogueRetriever(
        (_candidate("spain", country="Spain", denomination="1 peseta", year="1980"),)
    )

    result = retriever.retrieve(_request(visible_text=("ESPAÑA",)))

    assert [item.candidate_id for item in result.candidates] == ["spain"]


def test_observed_republica_and_dominicana_match_dominican_republic_tokens():
    retriever = InMemoryCatalogueRetriever(
        (_candidate("dominican", country="Dominican Republic", denomination="1/2 peso", year="1973"),)
    )

    result = retriever.retrieve(
        _request(visible_text=("REPUBLICA", "DOMINICANA"))
    )

    assert [item.candidate_id for item in result.candidates] == ["dominican"]


@pytest.mark.parametrize(
    ("observed", "catalogue_denomination"),
    (("SHILLING", "2 shillings"), ("SHILLINGS", "1 shilling")),
)
def test_observed_shilling_number_is_equivalent_to_plural_form(
    observed, catalogue_denomination
):
    retriever = InMemoryCatalogueRetriever(
        (_candidate("sterling", denomination=catalogue_denomination),)
    )

    result = retriever.retrieve(_request(visible_text=(observed,)))

    assert [item.candidate_id for item in result.candidates] == ["sterling"]


@pytest.mark.parametrize(
    "visible_text",
    (
        ("ESPANOL",),
        ("REPUBLICA",),
        ("DOMINICANA",),
        ("SHILLINGWORTH",),
    ),
)
def test_query_normalization_does_not_expand_unrelated_or_incomplete_terms(visible_text):
    retriever = InMemoryCatalogueRetriever(
        (
            _candidate("spain", country="Spain"),
            _candidate("dominican", country="Dominican Republic"),
            _candidate("sterling", denomination="2 shillings"),
        )
    )

    result = retriever.retrieve(_request(visible_text=visible_text))

    assert result.candidates == ()


def test_existing_ascii_country_matching_is_unchanged_outside_bounded_mappings():
    retriever = InMemoryCatalogueRetriever(
        (
            _candidate("canada", country="Canada"),
            _candidate("spain", country="Spain"),
        )
    )

    result = retriever.retrieve(_request(visible_text=("CANADA",)))

    assert [item.candidate_id for item in result.candidates] == ["canada"]


def test_zero_overlap_rows_are_not_returned():
    retriever = InMemoryCatalogueRetriever(
        (_candidate("a", country="Canada", year="1955"),)
    )

    result = retriever.retrieve(_request(year="1968"))

    assert result.candidates == ()


def test_limit_is_applied_after_deterministic_ranking():
    retriever = InMemoryCatalogueRetriever(
        (
            _candidate("c"),
            _candidate("a"),
            _candidate("b"),
        )
    )

    result = retriever.retrieve(_request(year="1955", limit=2))

    assert [item.candidate_id for item in result.candidates] == ["a", "b"]


def test_ties_are_stable_by_candidate_id():
    retriever = InMemoryCatalogueRetriever(
        (
            _candidate("z"),
            _candidate("a"),
        )
    )

    result = retriever.retrieve(_request(year="1955"))

    assert [item.candidate_id for item in result.candidates] == ["a", "z"]


def test_query_id_is_stable_for_same_request():
    retriever = InMemoryCatalogueRetriever((_candidate("a"),))
    request = _request(year="1955", denomination="25 cents")

    first = retriever.retrieve(request)
    second = retriever.retrieve(request)

    assert first.query_id == second.query_id
    assert first.query_id.startswith("catalogue-")


def test_query_id_changes_when_grounded_query_changes():
    retriever = InMemoryCatalogueRetriever((_candidate("a"),))

    first = retriever.retrieve(_request(year="1955"))
    second = retriever.retrieve(_request(year="1956"))

    assert first.query_id != second.query_id


def test_empty_catalogue_returns_no_match_result():
    result = InMemoryCatalogueRetriever(()).retrieve(_request(year="1955"))

    assert result.candidates == ()
    assert result.retriever_id == "in-memory-catalogue-v1"


def test_duplicate_catalogue_ids_fail_closed():
    with pytest.raises(CatalogueRetrievalContractError, match="unique"):
        InMemoryCatalogueRetriever((_candidate("same"), _candidate("same")))


def test_invalid_catalogue_row_fails_closed():
    with pytest.raises(CatalogueRetrievalContractError, match="CatalogueCandidate"):
        InMemoryCatalogueRetriever((_candidate("a"), object()))


def test_wrong_request_type_is_rejected():
    retriever = InMemoryCatalogueRetriever((_candidate("a"),))

    with pytest.raises(TypeError, match="CatalogueRetrievalRequest"):
        retriever.retrieve(object())


def test_retrieval_has_no_identity_acceptance_or_confidence():
    result = InMemoryCatalogueRetriever((_candidate("a"),)).retrieve(
        _request(year="1955")
    )

    assert not hasattr(result, "accepted")
    assert not hasattr(result, "confidence")
    assert not hasattr(result, "identity")
