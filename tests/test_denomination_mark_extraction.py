import pytest

from capture_import.denomination_mark_extraction import extract_denomination_marks
from capture_import.grounded_visual_observation import GroundedVisualObservation


def _observation(role="obverse", **kwargs):
    return GroundedVisualObservation(role=role, **kwargs)


@pytest.mark.parametrize("mark", ["5 CENTS", "2 Fr.", "10 PISO", "Rp 100", "$1", "2 1/2 Fr"])
def test_explicit_numeric_unit_marks_resolve(mark):
    result = extract_denomination_marks((_observation(denomination_mark=mark, visible_text=(mark,)),))

    assert result.resolved_value == mark
    assert not result.conflict
    assert not result.unresolved
    assert result.candidates[0].source_field == "denomination_mark"


@pytest.mark.parametrize(
    "mark",
    ["10 ÖRE", "5 öre", "10 ORE", "5 ore"],
)
def test_numeric_ore_marks_resolve(mark):
    result = extract_denomination_marks(
        (_observation(denomination_mark=mark, visible_text=(mark,)),)
    )

    assert result.resolved_value == mark
    assert not result.conflict
    assert not result.unresolved


def test_visible_text_can_supply_explicit_mark():
    result = extract_denomination_marks(
        (_observation(visible_text=("LIBERTY", "25 CENTS", "1968")),)
    )

    assert result.resolved_value == "25 CENTS"
    assert result.candidates[0].source_field == "visible_text"


@pytest.mark.parametrize("value", ["25", "100", "1968", "ONE", "CENT"])
def test_ambiguous_bare_number_or_unit_does_not_resolve(value):
    result = extract_denomination_marks(
        (_observation(denomination_mark=value),)
    )

    assert result.candidates == ()
    assert result.resolved_value is None
    assert result.unresolved


@pytest.mark.parametrize("value", ["V027", "X123", "7 Q", "10 ÖL", "5 café"])
def test_arbitrary_latin_letters_are_not_denomination_units(value):
    result = extract_denomination_marks(
        (_observation(denomination_mark=value, visible_text=(value,)),)
    )

    assert result.candidates == ()
    assert result.resolved_value is None
    assert result.unresolved


def test_matching_marks_across_sides_resolve_without_normalizing_currency():
    result = extract_denomination_marks(
        (
            _observation("obverse", denomination_mark="10 PISO", visible_text=("10 PISO",)),
            _observation("reverse", visible_text=("10 piso",)),
        )
    )

    assert result.resolved_value == "10 PISO"
    assert not result.conflict
    assert len(result.candidates) == 2


def test_incompatible_explicit_marks_conflict_and_abstain():
    result = extract_denomination_marks(
        (
            _observation("obverse", denomination_mark="5 CENTS", visible_text=("5 CENTS",)),
            _observation("reverse", denomination_mark="10 CENTS", visible_text=("10 CENTS",)),
        )
    )

    assert result.resolved_value is None
    assert result.conflict
    assert result.unresolved


def test_whitespace_and_case_are_comparison_only_not_output_rewriting():
    result = extract_denomination_marks(
        (
            _observation("obverse", denomination_mark="Rp   100", visible_text=("rp 100",)),
            _observation("reverse", visible_text=("rp 100",)),
        )
    )

    assert result.resolved_value == "Rp 100"
    assert not result.conflict


def test_date_text_is_not_misclassified_as_denomination():
    result = extract_denomination_marks(
        (_observation(visible_text=("1918", "BRITT")),)
    )

    assert result.candidates == ()


def test_duplicate_same_source_mark_is_deduplicated():
    result = extract_denomination_marks(
        (_observation(visible_text=("25 CENTS", "25 CENTS")),)
    )

    assert len(result.candidates) == 1


def test_matching_field_precedes_duplicate_visible_text_evidence():
    result = extract_denomination_marks(
        (
            _observation(
                denomination_mark="25 CENTS",
                visible_text=("25 CENTS",),
            ),
        )
    )

    assert len(result.candidates) == 1
    assert result.candidates[0].source_field == "denomination_mark"


def test_empty_evidence_abstains():
    result = extract_denomination_marks((_observation(),))

    assert result.candidates == ()
    assert result.resolved_value is None
    assert not result.conflict
    assert result.unresolved


def test_duplicate_roles_and_too_many_sides_are_rejected():
    with pytest.raises(ValueError, match="unique"):
        extract_denomination_marks((_observation(), _observation()))
    with pytest.raises(ValueError, match="at most two"):
        extract_denomination_marks(
            (
                _observation("obverse"),
                _observation("reverse"),
                _observation("obverse"),
            )
        )


def test_extractor_has_no_identity_or_currency_inference_fields():
    result = extract_denomination_marks(
        (_observation(denomination_mark="25 CENTS", visible_text=("25 CENTS",)),)
    )

    assert not hasattr(result, "country")
    assert not hasattr(result, "currency")
    assert not hasattr(result, "identity")
    assert not hasattr(result, "confidence")


def test_uncorroborated_denomination_mark_is_not_promoted():
    result = extract_denomination_marks(
        (
            _observation(
                denomination_mark="2 NT",
                visible_text=("5 FR", "1968"),
            ),
        )
    )

    assert result.resolved_value == "5 FR"
    assert all(item.value != "2 NT" for item in result.candidates)
    assert not result.conflict


def test_structured_mark_is_not_discarded_for_cross_side_visible_text():
    result = extract_denomination_marks(
        (
            _observation("obverse", denomination_mark="25 CENTS"),
            _observation("reverse", visible_text=("25 CENTS",)),
        )
    )

    assert len(result.candidates) == 2
    assert {item.role for item in result.candidates} == {"obverse", "reverse"}
    assert {item.source_field for item in result.candidates} == {
        "denomination_mark",
        "visible_text",
    }


@pytest.mark.parametrize("mark", ["SIXPENCE", "Sixpence", "sixpence"])
def test_controlled_compound_sixpence_resolves_from_visible_text(mark):
    result = extract_denomination_marks(
        (_observation(visible_text=(mark,)),)
    )

    assert result.resolved_value == mark
    assert not result.conflict
    assert not result.unresolved
    assert result.candidates[0].source_field == "visible_text"


@pytest.mark.parametrize("value", ["PENCE", "SHILLING", "SHILLINGS", "CROWN", "MARK"])
def test_bare_denomination_words_are_not_promoted(value):
    result = extract_denomination_marks(
        (_observation(visible_text=(value,)),)
    )

    assert result.candidates == ()
    assert result.resolved_value is None
    assert result.unresolved
