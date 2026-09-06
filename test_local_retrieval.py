import unittest

from local_retrieval import retrieve_local
from retrieval_contracts import (
    CURRENT_RETRIEVAL_SCHEMA_VERSION,
    RetrievalContext,
    RetrievalProvenance,
    RetrievalQuery,
    RetrievableEvidenceItem,
)


class LocalRetrievalTests(unittest.TestCase):
    def _item(
        self,
        item_id: str,
        text: str,
        *,
        source_type: str = "confirmed_observation",
        metadata: tuple[tuple[str, str], ...] = (),
    ) -> RetrievableEvidenceItem:
        return RetrievableEvidenceItem(
            schema_version=CURRENT_RETRIEVAL_SCHEMA_VERSION,
            item_id=item_id,
            text=text,
            provenance=RetrievalProvenance(
                source_type=source_type,
                source_id=f"source:{item_id}",
            ),
            metadata=metadata,
        )

    def test_ranks_by_shared_query_tokens_then_item_id(self) -> None:
        context = RetrievalContext(
            query=RetrievalQuery(
                query_text="canadian 1947 cent",
                max_results=10,
            )
        )

        results = retrieve_local(
            context,
            (
                self._item(
                    "b",
                    "Canadian cent",
                ),
                self._item(
                    "a",
                    "1947 Canadian one cent",
                ),
                self._item(
                    "c",
                    "Canadian cent",
                ),
            ),
        )

        self.assertEqual(
            tuple(result.item.item_id for result in results),
            ("a", "b", "c"),
        )
        self.assertEqual(
            tuple(result.rank for result in results),
            (1, 2, 3),
        )

    def test_requires_at_least_one_query_token_match(self) -> None:
        context = RetrievalContext(
            query=RetrievalQuery(query_text="1947 cent")
        )

        results = retrieve_local(
            context,
            (
                self._item("a", "Canadian dollar"),
                self._item("b", "1947 Canadian cent"),
            ),
        )

        self.assertEqual(
            tuple(result.item.item_id for result in results),
            ("b",),
        )

    def test_source_type_filter_is_exact(self) -> None:
        context = RetrievalContext(
            query=RetrievalQuery(
                query_text="canadian cent",
                source_types=("confirmed_observation",),
            )
        )

        results = retrieve_local(
            context,
            (
                self._item(
                    "a",
                    "Canadian cent",
                    source_type="confirmed_observation",
                ),
                self._item(
                    "b",
                    "Canadian cent",
                    source_type="diagnostic_note",
                ),
            ),
        )

        self.assertEqual(
            tuple(result.item.item_id for result in results),
            ("a",),
        )

    def test_metadata_filters_are_exact_and_required(self) -> None:
        context = RetrievalContext(
            query=RetrievalQuery(
                query_text="canadian cent",
                metadata_filters=(
                    ("country", "Canada"),
                    ("year", "1947"),
                ),
            )
        )

        results = retrieve_local(
            context,
            (
                self._item(
                    "a",
                    "Canadian cent",
                    metadata=(
                        ("country", "Canada"),
                        ("year", "1947"),
                    ),
                ),
                self._item(
                    "b",
                    "Canadian cent",
                    metadata=(
                        ("country", "Canada"),
                        ("year", "1948"),
                    ),
                ),
            ),
        )

        self.assertEqual(
            tuple(result.item.item_id for result in results),
            ("a",),
        )

    def test_candidate_scope_excludes_other_items(self) -> None:
        context = RetrievalContext(
            query=RetrievalQuery(query_text="canadian cent"),
            candidate_item_ids=("b",),
        )

        results = retrieve_local(
            context,
            (
                self._item("a", "Canadian cent"),
                self._item("b", "Canadian cent"),
            ),
        )

        self.assertEqual(
            tuple(result.item.item_id for result in results),
            ("b",),
        )

    def test_empty_candidate_scope_means_unrestricted_corpus(self) -> None:
        context = RetrievalContext(
            query=RetrievalQuery(query_text="canadian cent"),
            candidate_item_ids=(),
        )

        results = retrieve_local(
            context,
            (
                self._item("a", "Canadian cent"),
                self._item("b", "Canadian cent"),
            ),
        )

        self.assertEqual(
            tuple(result.item.item_id for result in results),
            ("a", "b"),
        )

    def test_max_results_bounds_output(self) -> None:
        context = RetrievalContext(
            query=RetrievalQuery(
                query_text="cent",
                max_results=2,
            )
        )

        results = retrieve_local(
            context,
            (
                self._item("a", "cent"),
                self._item("b", "cent"),
                self._item("c", "cent"),
            ),
        )

        self.assertEqual(len(results), 2)
        self.assertEqual(
            tuple(result.item.item_id for result in results),
            ("a", "b"),
        )

    def test_duplicate_item_ids_fail_closed(self) -> None:
        context = RetrievalContext(
            query=RetrievalQuery(query_text="cent")
        )

        with self.assertRaisesRegex(
            ValueError,
            "Duplicate retrievable item_id",
        ):
            retrieve_local(
                context,
                (
                    self._item("a", "cent"),
                    self._item("a", "cent"),
                ),
            )

    def test_non_item_input_fails_closed(self) -> None:
        context = RetrievalContext(
            query=RetrievalQuery(query_text="cent")
        )

        with self.assertRaisesRegex(
            TypeError,
            "RetrievableEvidenceItem",
        ):
            retrieve_local(
                context,
                (object(),),  # type: ignore[arg-type]
            )

    def test_token_matching_is_case_insensitive(self) -> None:
        context = RetrievalContext(
            query=RetrievalQuery(query_text="CANADIAN CENT")
        )

        results = retrieve_local(
            context,
            (
                self._item("a", "Canadian Cent"),
            ),
        )

        self.assertEqual(len(results), 1)

    def test_rationale_is_deterministic_and_not_confidence(self) -> None:
        context = RetrievalContext(
            query=RetrievalQuery(
                query_text="canadian cent",
                metadata_filters=(("country", "Canada"),),
            )
        )

        results = retrieve_local(
            context,
            (
                self._item(
                    "a",
                    "Canadian cent",
                    metadata=(("country", "Canada"),),
                ),
            ),
        )

        self.assertEqual(
            results[0].rationale,
            "matched_query_tokens=2;matched_metadata_filters=1",
        )
        self.assertFalse(hasattr(results[0], "confidence"))

    def test_input_order_does_not_change_result_order(self) -> None:
        context = RetrievalContext(
            query=RetrievalQuery(query_text="cent")
        )

        a = self._item("a", "cent")
        b = self._item("b", "cent")

        forward = retrieve_local(context, (a, b))
        reverse = retrieve_local(context, (b, a))

        self.assertEqual(
            tuple(result.item.item_id for result in forward),
            tuple(result.item.item_id for result in reverse),
        )


if __name__ == "__main__":
    unittest.main()