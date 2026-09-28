from __future__ import annotations

import unittest

from capture_import.date_numeral_extraction import extract_date_numerals
from capture_import.denomination_mark_extraction import extract_denomination_marks
from capture_import.grounded_visual_observation import GroundedVisualObservation


class CoinFieldProposalContractTests(unittest.TestCase):
    def test_public_field_proposal_cannot_represent_supported(self) -> None:
        from capture_import.coin_field_proposals import (
            EvidenceReference,
            FieldProposal,
            FieldProposalStatus,
            ProposalScope,
        )
        with self.assertRaises(ValueError):
            FieldProposal("country", FieldProposalStatus.SUPPORTED, "Canada", "canada", (EvidenceReference("legend", "OBVERSE", "x", "Canada"),), ("x",), ProposalScope.DIRECT_OBSERVATION)
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
        self.assertEqual(result.field("denomination").status.value, "ABSTAIN")
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

    def test_direct_year_outside_candidate_range_is_conflicting(self) -> None:
        from capture_import.coin_field_proposals import project_coin_field_proposals
        observation = GroundedVisualObservation(role="obverse", date_like="1955")
        result = project_coin_field_proposals(
            source_coin_id="year-range",
            date=extract_date_numerals((observation,)),
            denomination=extract_denomination_marks((observation,)),
            candidate_metadata=(("candidate-range", "year", "1965-1989"),),
        )
        self.assertEqual(result.field("year").status.value, "CONFLICTING")
        self.assertIsNone(result.field("year").proposed_value)

    def test_direct_field_derives_normalization_from_observed_values(self) -> None:
        from capture_import.coin_field_proposals import project_coin_field_proposals
        observation = GroundedVisualObservation(role="obverse")
        result = project_coin_field_proposals(
            source_coin_id="masked-normalization",
            date=extract_date_numerals((observation,)),
            denomination=extract_denomination_marks((observation,)),
            direct_evidence=(
                ("country", "Canada", "canada", "obverse", "legend", "canada"),
                ("country", "Other", "canada", "reverse", "legend", "other"),
            ),
        )
        self.assertEqual(result.field("country").status.value, "CONFLICTING")
        self.assertIsNone(result.field("country").proposed_value)

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
        from capture_import.coin_field_proposals import project_coin_field_proposals
        observation = GroundedVisualObservation(role="obverse", visible_text=("Province of Canada",))
        result = project_coin_field_proposals(source_coin_id="historical", date=extract_date_numerals((observation,)), denomination=extract_denomination_marks((observation,)), direct_evidence=(("country", "Province of Canada", "province of canada", "obverse", "legend", "issuer"),))
        self.assertEqual(result.field("country").proposed_value, "Province of Canada")
        self.assertEqual(result.field("country").evidence[0].image_role, "OBVERSE")
        self.assertEqual(result.field("denomination").status.value, "ABSTAIN")

    def test_candidate_country_metadata_is_rejected_not_silently_ignored(self) -> None:
        from capture_import.coin_field_proposals import project_coin_field_proposals
        observation = GroundedVisualObservation(role="obverse")
        with self.assertRaises(ValueError):
            project_coin_field_proposals(source_coin_id="country-meta", date=extract_date_numerals((observation,)), denomination=extract_denomination_marks((observation,)), candidate_metadata=(("candidate", "country", "Canada"),))

    def test_proposal_has_no_authority_or_persistence_surface(self) -> None:
        from capture_import.coin_field_proposals import CoinFieldProposalSet
        self.assertFalse(hasattr(CoinFieldProposalSet, "verify"))
        self.assertFalse(hasattr(CoinFieldProposalSet, "save"))
        self.assertFalse(hasattr(CoinFieldProposalSet, "persist"))
        self.assertFalse(hasattr(CoinFieldProposalSet, "to_reviewed_coin_draft"))

    def test_public_supported_constructor_cannot_forge_semantic_support(self) -> None:
        from capture_import.coin_field_proposals import (
            EvidenceReference,
            FieldProposal,
            ProposalScope,
        )
        with self.assertRaises(ValueError):
            FieldProposal.supported("monarch", "Elizabeth II", "elizabeth ii", (EvidenceReference("portrait", "OBVERSE", "x", "George VI"),), scope=ProposalScope.CROSS_SIDE_AGREEMENT, candidate_ids=("arbitrary",))

    def test_bounded_contract_rejects_unbounded_evidence_and_non_supported_selection(self) -> None:
        from capture_import.coin_field_proposals import (
            EvidenceReference,
            FieldProposal,
            FieldProposalStatus,
        )
        with self.assertRaises(ValueError):
            EvidenceReference("x", "OBVERSE", "a" * 256, "value")
        with self.assertRaises(ValueError):
            FieldProposal.unresolved("country", FieldProposalStatus.ABSTAIN, reasons=("no_evidence",), candidate_ids=tuple("x" for _ in range(26)))
        with self.assertRaises(ValueError):
            FieldProposal("country", FieldProposalStatus.AMBIGUOUS, "Canada", "canada", (), ("bad",), __import__("capture_import.coin_field_proposals", fromlist=["ProposalScope"]).ProposalScope.DIRECT_OBSERVATION)

    def test_monarch_values_are_data_not_schema_branches(self) -> None:
        for value in ("Elizabeth II", "Charles III", "George VI", "George V", "Edward VII", "Victoria"):
            with self.subTest(value=value):
                self.assertEqual(value.casefold(), value.casefold())

    def test_denomination_requires_explicit_mark_and_issuer_context(self) -> None:
        from capture_import.coin_field_proposals import project_coin_field_proposals
        observation = GroundedVisualObservation(role="reverse", visible_text=("10",))
        result = project_coin_field_proposals(source_coin_id="bare", date=extract_date_numerals((observation,)), denomination=extract_denomination_marks((observation,)))
        self.assertEqual(result.field("denomination").status.value, "ABSTAIN")

    def test_mapped_jurisdiction_rejects_unmapped_denomination(self) -> None:
        from capture_import.coin_field_proposals import project_coin_field_proposals

        observations = (GroundedVisualObservation(role="reverse", denomination_mark="10 piso"),)
        result = project_coin_field_proposals(
            source_coin_id="us-piso",
            date=extract_date_numerals(observations),
            denomination=extract_denomination_marks(observations),
            direct_evidence=(("country", "United States", "united states", "obverse", "legend", "us"),),
        )

        self.assertEqual(result.field("country").status.value, "SUPPORTED")
        self.assertEqual(result.field("denomination").status.value, "ABSTAIN")

    def test_mapped_jurisdiction_supports_valid_mapped_denomination(self) -> None:
        from capture_import.coin_field_proposals import project_coin_field_proposals

        observations = (GroundedVisualObservation(role="reverse", denomination_mark="10 cents"),)
        result = project_coin_field_proposals(
            source_coin_id="us-cents",
            date=extract_date_numerals(observations),
            denomination=extract_denomination_marks(observations),
            direct_evidence=(("country", "United States", "united states", "obverse", "legend", "us"),),
        )

        self.assertEqual(result.field("denomination").status.value, "SUPPORTED")
        self.assertEqual(result.field("denomination").proposed_value, "10 cents")

    def test_mapped_jurisdiction_rejects_unmapped_denomination_spelling_variants(self) -> None:
        from capture_import.coin_field_proposals import project_coin_field_proposals

        for mark in ("TEN PISO", "10 PISO"):
            with self.subTest(mark=mark):
                observations = (GroundedVisualObservation(role="reverse", denomination_mark=mark),)
                result = project_coin_field_proposals(
                    source_coin_id="us-piso-variant",
                    date=extract_date_numerals(observations),
                    denomination=extract_denomination_marks(observations),
                    direct_evidence=(("country", "U.S.A.", "united states", "obverse", "legend", "us"),),
                )
                self.assertNotEqual(result.field("denomination").status.value, "SUPPORTED")
    def test_monarch_and_reverse_require_correct_side_and_matching_candidate(self) -> None:
        from capture_import.coin_field_proposals import project_coin_field_proposals
        observation = GroundedVisualObservation(role="obverse")
        result = project_coin_field_proposals(source_coin_id="semantic", date=extract_date_numerals((observation,)), denomination=extract_denomination_marks((observation,)), direct_evidence=(("monarch", "Elizabeth II", "elizabeth ii", "reverse", "portrait", "r"), ("reverse_design", "Bluenose", "bluenose", "obverse", "motif", "o")), candidate_metadata=(("candidate", "monarch", "Elizabeth II"), ("candidate", "reverse_design", "Bluenose")))
        self.assertEqual(result.field("monarch").status.value, "ABSTAIN")
        self.assertEqual(result.field("reverse_design").status.value, "ABSTAIN")

    def test_unique_candidate_support_is_collected_and_requires_one_matching_candidate(self) -> None:
        from capture_import.catalogue_retrieval import CatalogueRetrievalResult
        from capture_import.evidence_candidate_resolver import CatalogueCandidate
        from capture_import.two_side_candidate_verification import (
            derive_unique_verified_denomination_support,
        )
        sides = (GroundedVisualObservation(role="reverse", denomination_mark="25 CENTS", visible_text=("25 CENTS", "CANADA")),)
        result = CatalogueRetrievalResult((CatalogueCandidate("one", "Canada", "25 cents", "1955", legends=("CANADA",)),), "fixture")
        support = derive_unique_verified_denomination_support(result, sides, extract_denomination_marks(sides), validation_context_id="capture-1")
        self.assertIsNotNone(support)
        assert support is not None
        self.assertEqual(support.candidate_id, "one")
        self.assertEqual(support.validation_context_id, "capture-1")

    def test_unique_candidate_support_rejects_zero_multiple_and_mismatch(self) -> None:
        from capture_import.catalogue_retrieval import CatalogueRetrievalResult
        from capture_import.evidence_candidate_resolver import CatalogueCandidate
        from capture_import.two_side_candidate_verification import (
            derive_unique_verified_denomination_support,
        )
        sides = (GroundedVisualObservation(role="reverse", denomination_mark="25 CENTS", visible_text=("25 CENTS", "CANADA")),)
        extraction = extract_denomination_marks(sides)
        make = lambda *rows: CatalogueRetrievalResult(rows, "fixture")
        matching = CatalogueCandidate("one", "Canada", "25 cents", "1955", legends=("CANADA",))
        mismatch = CatalogueCandidate("bad", "Canada", "10 cents", "1955", legends=("CANADA",))
        self.assertIsNone(derive_unique_verified_denomination_support(make(), sides, extraction, validation_context_id="capture-1"))
        other_matching = CatalogueCandidate("two", "Canada", "25 cents", "1955", legends=("CANADA",))
        self.assertIsNone(derive_unique_verified_denomination_support(make(matching, other_matching), sides, extraction, validation_context_id="capture-1"))
        self.assertIsNone(derive_unique_verified_denomination_support(make(mismatch), sides, extraction, validation_context_id="capture-1"))

    def test_candidate_support_cannot_be_reused_for_another_projection_context(self) -> None:
        from capture_import.catalogue_retrieval import CatalogueRetrievalResult
        from capture_import.coin_field_proposals import project_coin_field_proposals
        from capture_import.evidence_candidate_resolver import CatalogueCandidate
        from capture_import.two_side_candidate_verification import (
            derive_unique_verified_denomination_support,
        )
        sides = (GroundedVisualObservation(role="reverse", denomination_mark="25 CENTS", visible_text=("25 CENTS", "CANADA")),)
        extraction = extract_denomination_marks(sides)
        support = derive_unique_verified_denomination_support(CatalogueRetrievalResult((CatalogueCandidate("one", "Canada", "25 cents", "1955", legends=("CANADA",)),), "fixture"), sides, extraction, validation_context_id="capture-1")
        result = project_coin_field_proposals(source_coin_id="capture-2", date=extract_date_numerals(sides), denomination=extraction, candidate_support=support)
        self.assertEqual(result.field("denomination").status.value, "CONFLICTING")


    def test_candidate_support_cannot_be_reused_for_different_observations_in_same_context(self) -> None:
        from capture_import.catalogue_retrieval import CatalogueRetrievalResult
        from capture_import.coin_field_proposals import project_coin_field_proposals
        from capture_import.evidence_candidate_resolver import CatalogueCandidate
        from capture_import.two_side_candidate_verification import (
            derive_unique_verified_denomination_support,
        )
        source_sides = (
            GroundedVisualObservation(role="reverse", denomination_mark="25 CENTS", visible_text=("25 CENTS", "CANADA")),
        )
        replay_sides = (
            GroundedVisualObservation(role="reverse", denomination_mark="25 CENTS", visible_text=("25 CENTS",)),
        )
        support = derive_unique_verified_denomination_support(
            CatalogueRetrievalResult((CatalogueCandidate("one", "Canada", "25 cents", "1955", legends=("CANADA",)),), "fixture"),
            source_sides,
            extract_denomination_marks(source_sides),
            validation_context_id="capture-1",
        )
        result = project_coin_field_proposals(
            source_coin_id="capture-1",
            date=extract_date_numerals(replay_sides),
            denomination=extract_denomination_marks(replay_sides),
            candidate_support=support,
            observations=replay_sides,
        )
        self.assertEqual(result.field("denomination").status.value, "CONFLICTING")

    def test_candidate_support_projects_only_with_matching_observations(self) -> None:
        from capture_import.catalogue_retrieval import CatalogueRetrievalResult
        from capture_import.coin_field_proposals import project_coin_field_proposals
        from capture_import.evidence_candidate_resolver import CatalogueCandidate
        from capture_import.two_side_candidate_verification import (
            derive_unique_verified_denomination_support,
        )
        sides = (
            GroundedVisualObservation(role="reverse", denomination_mark="25 CENTS", visible_text=("25 CENTS", "CANADA")),
        )
        support = derive_unique_verified_denomination_support(
            CatalogueRetrievalResult((CatalogueCandidate("one", "Canada", "25 cents", "1955", legends=("CANADA",)),), "fixture"),
            sides,
            extract_denomination_marks(sides),
            validation_context_id="capture-1",
        )
        result = project_coin_field_proposals(
            source_coin_id="capture-1",
            date=extract_date_numerals(sides),
            denomination=extract_denomination_marks(sides),
            candidate_support=support,
            observations=sides,
        )
        self.assertEqual(result.field("denomination").status.value, "SUPPORTED")
        self.assertEqual(result.field("denomination").candidate_ids, ("one",))

if __name__ == "__main__":
    unittest.main()
