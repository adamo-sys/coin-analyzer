from __future__ import annotations

import unittest

from capture_import.date_numeral_extraction import extract_date_numerals
from capture_import.denomination_mark_extraction import extract_denomination_marks
from capture_import.grounded_visual_observation import GroundedVisualObservation


class CoinFieldProposalContractTests(unittest.TestCase):
    def test_projection_supports_fields_independently_and_preserves_side_evidence(self) -> None:
        from capture_import.coin_field_proposals import project_coin_field_proposals

        observations = (
            GroundedVisualObservation(role="obverse", visible_text=("CANADA",)),
            GroundedVisualObservation(role="reverse", denomination_mark="10 cents", visible_text=("10 cents",)),
        )
        result = project_coin_field_proposals(
            source_coin_id="pair-1",
            date=extract_date_numerals(observations),
            denomination=extract_denomination_marks(observations),
            direct_evidence=(
                ("country", "Canada", "Canada", "obverse", "legend", "artifact-obverse"),
            ),
        )

        self.assertEqual(result.field("country").status.value, "SUPPORTED")
        self.assertEqual(result.field("denomination").status.value, "SUPPORTED")
        self.assertEqual(result.field("year").status.value, "ABSTAIN")
        self.assertEqual(result.field("variety").status.value, "ABSTAIN")
        self.assertEqual(result.field("country").evidence[0].image_role, "OBVERSE")
        self.assertEqual(result.field("denomination").evidence[0].image_role, "REVERSE")

    def test_year_requires_exact_direct_date_evidence_and_never_uses_metadata(self) -> None:
        from capture_import.coin_field_proposals import project_coin_field_proposals

        observation = GroundedVisualObservation(role="obverse", date_like="1974", visible_text=("1974",))
        result = project_coin_field_proposals(
            source_coin_id="pair-2",
            date=extract_date_numerals((observation,)),
            denomination=extract_denomination_marks((observation,)),
            candidate_metadata=(("candidate-1974", "year", "1965-1989"),),
        )

        year = result.field("year")
        self.assertEqual(year.status.value, "SUPPORTED")
        self.assertEqual(year.proposed_value, "1974")
        self.assertEqual(year.scope.value, "DIRECT_OBSERVATION")
        self.assertTrue(all(item.observed_value == "1974" for item in year.evidence))

    def test_year_metadata_without_direct_literal_abstains(self) -> None:
        from capture_import.coin_field_proposals import project_coin_field_proposals

        observation = GroundedVisualObservation(role="obverse", visible_text=("ELIZABETH II",))
        result = project_coin_field_proposals(
            source_coin_id="pair-3",
            date=extract_date_numerals((observation,)),
            denomination=extract_denomination_marks((observation,)),
            candidate_metadata=(
                ("candidate-range", "year", "1965-1989"),
                ("candidate-monarch", "monarch", "Elizabeth II"),
                ("candidate-type", "reverse_design", "Bluenose"),
            ),
        )
        year = result.field("year")
        self.assertEqual(year.status.value, "ABSTAIN")
        self.assertIsNone(year.proposed_value)

    def test_conflicting_and_partial_years_never_select_a_value(self) -> None:
        from capture_import.coin_field_proposals import project_coin_field_proposals

        conflicting = (
            GroundedVisualObservation(role="obverse", date_like="1974"),
            GroundedVisualObservation(role="reverse", date_like="1975"),
        )
        partial = GroundedVisualObservation(role="obverse", date_like="19?4")
        for observations, expected in ((conflicting, "CONFLICTING"), ((partial,), "ABSTAIN")):
            with self.subTest(expected=expected):
                result = project_coin_field_proposals(
                    source_coin_id="pair-4",
                    date=extract_date_numerals(observations),
                    denomination=extract_denomination_marks(observations),
                )
                self.assertEqual(result.field("year").status.value, expected)
                self.assertIsNone(result.field("year").proposed_value)

    def test_direct_year_conflicting_with_candidate_metadata_is_preserved_as_conflict(self) -> None:
        from capture_import.coin_field_proposals import project_coin_field_proposals

        observation = GroundedVisualObservation(role="obverse", date_like="1974")
        result = project_coin_field_proposals(
            source_coin_id="pair-5",
            date=extract_date_numerals((observation,)),
            denomination=extract_denomination_marks((observation,)),
            candidate_metadata=(("candidate-1975", "year", "1975"),),
        )
        year = result.field("year")
        self.assertEqual(year.status.value, "CONFLICTING")
        self.assertIsNone(year.proposed_value)
        self.assertEqual(year.candidate_ids, ("candidate-1975",))

    def test_ambiguous_and_conflicting_direct_field_evidence_do_not_select_values(self) -> None:
        from capture_import.coin_field_proposals import project_coin_field_proposals

        observation = GroundedVisualObservation(role="obverse")
        result = project_coin_field_proposals(
            source_coin_id="pair-6",
            date=extract_date_numerals((observation,)),
            denomination=extract_denomination_marks((observation,)),
            direct_evidence=(
                ("reverse_design", "Bluenose", "bluenose", "reverse", "motif", "a"),
                ("reverse_design", "Schooner", "schooner", "reverse", "motif", "b"),
                ("country", "Canada", "Canada", "obverse", "legend", "c"),
                ("country", "Other", "Other", "reverse", "legend", "d"),
            ),
        )
        self.assertEqual(result.field("reverse_design").status.value, "AMBIGUOUS")
        self.assertIsNone(result.field("reverse_design").proposed_value)
        self.assertEqual(result.field("country").status.value, "CONFLICTING")
        self.assertIsNone(result.field("country").proposed_value)

    def test_contract_represents_historical_issuer_and_denominations_without_special_cases(self) -> None:
        from capture_import.coin_field_proposals import (
            FieldProposal,
            FieldProposalStatus,
            ProposalScope,
        )

        issuer = FieldProposal.supported("country", "Province of Canada", "province-of-canada", (), scope=ProposalScope.CANDIDATE_METADATA)
        fifty = FieldProposal.supported("denomination", "50 cents", "50-cents", (), scope=ProposalScope.CANDIDATE_METADATA)
        twenty = FieldProposal.supported("denomination", "20 cents", "20-cents", (), scope=ProposalScope.CANDIDATE_METADATA)
        dollar_design = FieldProposal.supported("reverse_design", "Voyageur", "voyageur", (), scope=ProposalScope.CANDIDATE_METADATA)
        self.assertIs(issuer.status, FieldProposalStatus.SUPPORTED)
        self.assertNotEqual(fifty.normalized_value, twenty.normalized_value)
        self.assertNotEqual(dollar_design.field_name, fifty.field_name)


if __name__ == "__main__":
    unittest.main()
