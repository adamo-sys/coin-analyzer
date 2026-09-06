from dataclasses import FrozenInstanceError
import unittest

from retrieval_contracts import (
    CURRENT_RETRIEVAL_SCHEMA_VERSION,
    RankedRetrievalResult,
    RetrievalContext,
    RetrievalProvenance,
    RetrievalQuery,
    RetrievalValidationDecision,
    RetrievalValidationOutcome,
    RetrievableEvidenceItem,
)


class RetrievalContractTests(unittest.TestCase):
    def _provenance(self) -> RetrievalProvenance:
        return RetrievalProvenance(
            source_type="confirmed_observation",
            source_id="coin-1:year",
            source_fingerprint="sha256:abc",
            evidence_refs=("capture/package-1", "ocr/result-1"),
        )

    def _item(self) -> RetrievableEvidenceItem:
        return RetrievableEvidenceItem(
            schema_version=CURRENT_RETRIEVAL_SCHEMA_VERSION,
            item_id="evidence-1",
            text="1947 Canadian one cent confirmed by collector review.",
            provenance=self._provenance(),
            metadata=(("country", "Canada"), ("year", "1947")),
        )

    def test_valid_contract_graph(self) -> None:
        query = RetrievalQuery(
            query_text="Canadian 1947 one cent",
            max_results=5,
            source_types=("confirmed_observation",),
            metadata_filters=(("country", "Canada"),),
        )
        context = RetrievalContext(query=query, candidate_item_ids=("evidence-1", "evidence-2"))
        result = RankedRetrievalResult(item=self._item(), rank=1, rationale="Exact metadata match.")
        outcome = RetrievalValidationOutcome(item_id="evidence-1", decision=RetrievalValidationDecision.ACCEPT)
        self._provenance().validate()
        self._item().validate()
        query.validate()
        context.validate()
        result.validate()
        outcome.validate()

    def test_contracts_are_frozen(self) -> None:
        item = self._item()
        with self.assertRaises(FrozenInstanceError):
            item.item_id = "changed"  # type: ignore[misc]

    def test_provenance_requires_sorted_unique_evidence_refs(self) -> None:
        unsorted = RetrievalProvenance(source_type="confirmed_observation", source_id="coin-1:year", evidence_refs=("z", "a"))
        duplicate = RetrievalProvenance(source_type="confirmed_observation", source_id="coin-1:year", evidence_refs=("a", "a"))
        with self.assertRaisesRegex(ValueError, "sorted order"):
            unsorted.validate()
        with self.assertRaisesRegex(ValueError, "duplicates"):
            duplicate.validate()

    def test_item_rejects_unknown_schema_version(self) -> None:
        item = RetrievableEvidenceItem(schema_version="999", item_id="evidence-1", text="text", provenance=self._provenance())
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            item.validate()

    def test_item_metadata_requires_sorted_unique_keys(self) -> None:
        unsorted = RetrievableEvidenceItem(schema_version=CURRENT_RETRIEVAL_SCHEMA_VERSION, item_id="evidence-1", text="text", provenance=self._provenance(), metadata=(("year", "1947"), ("country", "Canada")))
        duplicate = RetrievableEvidenceItem(schema_version=CURRENT_RETRIEVAL_SCHEMA_VERSION, item_id="evidence-1", text="text", provenance=self._provenance(), metadata=(("country", "Canada"), ("country", "CA")))
        with self.assertRaisesRegex(ValueError, "key order"):
            unsorted.validate()
        with self.assertRaisesRegex(ValueError, "duplicate keys"):
            duplicate.validate()

    def test_query_is_bounded_and_rejects_boolean_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 1 and 100"):
            RetrievalQuery(query_text="coin", max_results=101).validate()
        with self.assertRaisesRegex(TypeError, "integer"):
            RetrievalQuery(query_text="coin", max_results=True).validate()

    def test_query_source_types_are_sorted_and_unique(self) -> None:
        with self.assertRaisesRegex(ValueError, "sorted order"):
            RetrievalQuery(query_text="coin", source_types=("diagnostic", "collection")).validate()
        with self.assertRaisesRegex(ValueError, "duplicates"):
            RetrievalQuery(query_text="coin", source_types=("collection", "collection")).validate()

    def test_empty_candidate_context_is_valid(self) -> None:
        RetrievalContext(query=RetrievalQuery(query_text="coin"), candidate_item_ids=()).validate()

    def test_candidate_ids_are_sorted_and_unique(self) -> None:
        with self.assertRaisesRegex(ValueError, "sorted order"):
            RetrievalContext(query=RetrievalQuery(query_text="coin"), candidate_item_ids=("item-b", "item-a")).validate()
        with self.assertRaisesRegex(ValueError, "duplicates"):
            RetrievalContext(query=RetrievalQuery(query_text="coin"), candidate_item_ids=("item-a", "item-a")).validate()

    def test_rank_must_be_positive_integer(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            RankedRetrievalResult(item=self._item(), rank=0).validate()
        with self.assertRaisesRegex(TypeError, "integer"):
            RankedRetrievalResult(item=self._item(), rank=True).validate()

    def test_validation_decision_must_use_enum(self) -> None:
        outcome = RetrievalValidationOutcome(
            item_id="evidence-1",
            decision="ACCEPT",  # type: ignore[arg-type]
        )

        with self.assertRaisesRegex(
            TypeError,
            "RetrievalValidationDecision",
        ):
            outcome.validate()
    def test_reject_outcome_requires_reason(self) -> None:
        outcome = RetrievalValidationOutcome(item_id="evidence-1", decision=RetrievalValidationDecision.REJECT)
        with self.assertRaisesRegex(ValueError, "require a reason"):
            outcome.validate()

    def test_reject_reason_codes_are_deterministic(self) -> None:
        outcome = RetrievalValidationOutcome(item_id="evidence-1", decision=RetrievalValidationDecision.REJECT, reason_codes=("weak_match", "irrelevant"))
        with self.assertRaisesRegex(ValueError, "sorted order"):
            outcome.validate()


if __name__ == "__main__":
    unittest.main()
