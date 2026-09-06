from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import cast
import unittest

from corrective_retrieval_validation import (
    CANDIDATE_SCOPE_MISMATCH,
    INSUFFICIENT_QUERY_OVERLAP,
    METADATA_FILTER_MISMATCH,
    SOURCE_TYPE_MISMATCH,
    CorrectiveRetrievalPolicy,
    validate_and_rerank_retrieval_results,
    validate_ranked_retrieval_result,
)
from retrieval_contracts import (
    CURRENT_RETRIEVAL_SCHEMA_VERSION,
    RankedRetrievalResult,
    RetrievalContext,
    RetrievalProvenance,
    RetrievalQuery,
    RetrievalValidationDecision,
    RetrievableEvidenceItem,
)


class CorrectiveRetrievalValidationTests(unittest.TestCase):
    def _item(
        self,
        identifier: str,
        text: str,
        *,
        source_type: str = "confirmed_observation",
        metadata: tuple[tuple[str, str], ...] = (("country", "Canada"),),
    ) -> RetrievableEvidenceItem:
        item = RetrievableEvidenceItem(
            schema_version=CURRENT_RETRIEVAL_SCHEMA_VERSION,
            item_id=identifier,
            text=text,
            provenance=RetrievalProvenance(
                source_type=source_type,
                source_id=f"source-{identifier}",
            ),
            metadata=metadata,
        )
        item.validate()
        return item

    def _context(
        self,
        *,
        query_text: str = "canada dollar silver",
        candidate_item_ids: tuple[str, ...] = (),
        source_types: tuple[str, ...] = (),
        metadata_filters: tuple[tuple[str, str], ...] = (),
    ) -> RetrievalContext:
        context = RetrievalContext(
            query=RetrievalQuery(
                query_text=query_text,
                source_types=source_types,
                metadata_filters=metadata_filters,
            ),
            candidate_item_ids=candidate_item_ids,
        )
        context.validate()
        return context

    def test_accepts_result_that_satisfies_context_and_policy(self) -> None:
        result = RankedRetrievalResult(
            item=self._item("evidence-1", "Canadian silver dollar diagnostic"),
            rank=1,
            rationale="untrusted descriptive rationale",
        )

        outcome = validate_ranked_retrieval_result(self._context(), result)

        self.assertEqual(outcome.item_id, "evidence-1")
        self.assertIs(outcome.decision, RetrievalValidationDecision.ACCEPT)
        self.assertEqual(outcome.reason_codes, ())

    def test_rejects_insufficient_query_overlap(self) -> None:
        result = RankedRetrievalResult(
            item=self._item("evidence-1", "Canadian silver dollar diagnostic"),
            rank=1,
        )

        outcome = validate_ranked_retrieval_result(
            self._context(),
            result,
            policy=CorrectiveRetrievalPolicy(minimum_shared_query_tokens=4),
        )

        self.assertIs(outcome.decision, RetrievalValidationDecision.REJECT)
        self.assertEqual(outcome.reason_codes, (INSUFFICIENT_QUERY_OVERLAP,))

    def test_rejects_candidate_scope_mismatch(self) -> None:
        result = RankedRetrievalResult(
            item=self._item("evidence-2", "Canada dollar silver"),
            rank=1,
        )

        outcome = validate_ranked_retrieval_result(
            self._context(candidate_item_ids=("evidence-1",)),
            result,
        )

        self.assertEqual(outcome.reason_codes, (CANDIDATE_SCOPE_MISMATCH,))

    def test_rejects_source_type_mismatch(self) -> None:
        result = RankedRetrievalResult(
            item=self._item(
                "evidence-1",
                "Canada dollar silver",
                source_type="diagnostic_note",
            ),
            rank=1,
        )

        outcome = validate_ranked_retrieval_result(
            self._context(source_types=("confirmed_observation",)),
            result,
        )

        self.assertEqual(outcome.reason_codes, (SOURCE_TYPE_MISMATCH,))

    def test_rejects_metadata_filter_mismatch(self) -> None:
        result = RankedRetrievalResult(
            item=self._item(
                "evidence-1",
                "Canada dollar silver",
                metadata=(("country", "United States"),),
            ),
            rank=1,
        )

        outcome = validate_ranked_retrieval_result(
            self._context(metadata_filters=(("country", "Canada"),)),
            result,
        )

        self.assertEqual(outcome.reason_codes, (METADATA_FILTER_MISMATCH,))

    def test_reason_codes_are_sorted_when_multiple_checks_fail(self) -> None:
        result = RankedRetrievalResult(
            item=self._item(
                "evidence-9",
                "unrelated token",
                source_type="diagnostic_note",
                metadata=(("country", "United States"),),
            ),
            rank=1,
        )

        outcome = validate_ranked_retrieval_result(
            self._context(
                candidate_item_ids=("evidence-1",),
                source_types=("confirmed_observation",),
                metadata_filters=(("country", "Canada"),),
            ),
            result,
        )

        self.assertEqual(
            outcome.reason_codes,
            tuple(
                sorted(
                    (
                        CANDIDATE_SCOPE_MISMATCH,
                        INSUFFICIENT_QUERY_OVERLAP,
                        METADATA_FILTER_MISMATCH,
                        SOURCE_TYPE_MISMATCH,
                    )
                )
            ),
        )

    def test_rationale_is_not_trusted_as_validation_input(self) -> None:
        result = RankedRetrievalResult(
            item=self._item("evidence-1", "completely unrelated material"),
            rank=1,
            rationale="matched_query_tokens=999;matched_metadata_filters=999",
        )

        outcome = validate_ranked_retrieval_result(self._context(), result)

        self.assertIs(outcome.decision, RetrievalValidationDecision.REJECT)
        self.assertEqual(outcome.reason_codes, (INSUFFICIENT_QUERY_OVERLAP,))

    def test_batch_filters_rejected_results_and_compacts_ranks(self) -> None:
        results = (
            RankedRetrievalResult(
                item=self._item("evidence-1", "Canada silver dollar"),
                rank=1,
                rationale="first",
            ),
            RankedRetrievalResult(
                item=self._item("evidence-2", "unrelated bronze token"),
                rank=2,
                rationale="second",
            ),
            RankedRetrievalResult(
                item=self._item("evidence-3", "silver Canada dollar variety"),
                rank=3,
                rationale="third",
            ),
        )

        accepted, outcomes = validate_and_rerank_retrieval_results(
            self._context(),
            results,
        )

        self.assertEqual(tuple(result.item.item_id for result in accepted), ("evidence-1", "evidence-3"))
        self.assertEqual(tuple(result.rank for result in accepted), (1, 2))
        self.assertEqual(tuple(result.rationale for result in accepted), ("first", "third"))
        self.assertEqual(
            tuple(outcome.decision for outcome in outcomes),
            (
                RetrievalValidationDecision.ACCEPT,
                RetrievalValidationDecision.REJECT,
                RetrievalValidationDecision.ACCEPT,
            ),
        )

    def test_batch_preserves_evidence_item_identity(self) -> None:
        item = self._item("evidence-1", "Canada silver dollar")
        result = RankedRetrievalResult(item=item, rank=7, rationale="source rank")

        accepted, _ = validate_and_rerank_retrieval_results(
            self._context(),
            (result,),
        )

        self.assertIs(accepted[0].item, item)
        self.assertEqual(accepted[0].rank, 1)
        self.assertEqual(accepted[0].rationale, "source rank")

    def test_batch_rejects_duplicate_item_ids(self) -> None:
        item = self._item("evidence-1", "Canada silver dollar")
        results = (
            RankedRetrievalResult(item=item, rank=1),
            RankedRetrievalResult(item=item, rank=2),
        )

        with self.assertRaisesRegex(ValueError, "duplicate item IDs"):
            validate_and_rerank_retrieval_results(self._context(), results)

    def test_batch_requires_strictly_increasing_source_ranks(self) -> None:
        results = (
            RankedRetrievalResult(
                item=self._item("evidence-1", "Canada silver dollar"),
                rank=2,
            ),
            RankedRetrievalResult(
                item=self._item("evidence-2", "Canada dollar silver"),
                rank=1,
            ),
        )

        with self.assertRaisesRegex(ValueError, "strictly increasing rank"):
            validate_and_rerank_retrieval_results(self._context(), results)

    def test_policy_rejects_bool_and_out_of_range_values(self) -> None:
        with self.assertRaisesRegex(TypeError, "integer"):
            CorrectiveRetrievalPolicy(
                minimum_shared_query_tokens=cast(int, True)
            ).validate()
        with self.assertRaisesRegex(ValueError, "between"):
            CorrectiveRetrievalPolicy(minimum_shared_query_tokens=0).validate()

    def test_policy_is_frozen(self) -> None:
        policy = CorrectiveRetrievalPolicy()
        with self.assertRaises(FrozenInstanceError):
            policy.minimum_shared_query_tokens = 2  # type: ignore[misc]

    def test_invalid_context_and_result_types_fail_closed(self) -> None:
        valid_result = RankedRetrievalResult(
            item=self._item("evidence-1", "Canada silver dollar"),
            rank=1,
        )
        with self.assertRaisesRegex(TypeError, "context"):
            validate_ranked_retrieval_result(cast(RetrievalContext, object()), valid_result)
        with self.assertRaisesRegex(TypeError, "result"):
            validate_ranked_retrieval_result(
                self._context(),
                cast(RankedRetrievalResult, object()),
            )

    def test_batch_requires_immutable_tuple_input(self) -> None:
        result = RankedRetrievalResult(
            item=self._item("evidence-1", "Canada silver dollar"),
            rank=1,
        )
        with self.assertRaisesRegex(TypeError, "tuple"):
            validate_and_rerank_retrieval_results(
                self._context(),
                cast(tuple[RankedRetrievalResult, ...], [result]),
            )


if __name__ == "__main__":
    unittest.main()
