import unittest

from corrective_retrieval_validation import (
    CorrectiveRetrievalPolicy,
    validate_and_rerank_retrieval_results,
)
from local_retrieval import retrieve_local
from multimodal_evidence_references import (
    CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
    MultimodalEvidenceKind,
    MultimodalEvidenceReference,
)
from multimodal_retrieval_binding import MultimodalRetrievalBinding
from retrieval_contracts import (
    CURRENT_RETRIEVAL_SCHEMA_VERSION,
    RetrievalContext,
    RetrievalProvenance,
    RetrievalQuery,
    RetrievalValidationDecision,
    RetrievableEvidenceItem,
)


class Issue93MultimodalRetrievalPipelineTests(unittest.TestCase):
    def _binding(
        self,
        *,
        item_id: str,
        text: str,
        reference_id: str,
    ) -> MultimodalRetrievalBinding:
        reference = MultimodalEvidenceReference(
            schema_version=CURRENT_MULTIMODAL_REFERENCE_SCHEMA_VERSION,
            reference_id=reference_id,
            kind=MultimodalEvidenceKind.OCR_TEXT,
            source_id=f"source:{item_id}",
            locator=f"ocr:{item_id}",
            source_fingerprint=f"sha256:{item_id}",
        )
        item = RetrievableEvidenceItem(
            schema_version=CURRENT_RETRIEVAL_SCHEMA_VERSION,
            item_id=item_id,
            text=text,
            provenance=RetrievalProvenance(
                source_type="confirmed_observation",
                source_id=f"observation:{item_id}",
                source_fingerprint=f"sha256:{item_id}",
                evidence_refs=(reference_id,),
            ),
            metadata=(("jurisdiction", "Canada"),),
        )
        binding = MultimodalRetrievalBinding(
            item=item,
            references=(reference,),
        )
        binding.validate()
        return binding

    def _context(self) -> RetrievalContext:
        context = RetrievalContext(
            query=RetrievalQuery(
                query_text="canada cent reverse",
                max_results=10,
                source_types=("confirmed_observation",),
                metadata_filters=(("jurisdiction", "Canada"),),
            )
        )
        context.validate()
        return context

    def test_multimodal_lineage_survives_local_retrieval_verbatim(self) -> None:
        strong = self._binding(
            item_id="item:strong",
            text="canada cent reverse maple",
            reference_id="ref:ocr:strong",
        )
        weak = self._binding(
            item_id="item:weak",
            text="canada token",
            reference_id="ref:ocr:weak",
        )

        results = retrieve_local(
            self._context(),
            (strong.item, weak.item),
        )

        self.assertEqual(
            tuple(result.item.item_id for result in results),
            ("item:strong", "item:weak"),
        )
        self.assertIs(results[0].item, strong.item)
        self.assertIs(results[1].item, weak.item)
        self.assertEqual(
            results[0].item.provenance.evidence_refs,
            strong.reference_ids,
        )
        self.assertEqual(
            results[1].item.provenance.evidence_refs,
            weak.reference_ids,
        )
        strong.validate()
        weak.validate()

    def test_corrective_reranking_preserves_accepted_multimodal_lineage(self) -> None:
        strong = self._binding(
            item_id="item:strong",
            text="canada cent reverse maple",
            reference_id="ref:ocr:strong",
        )
        weak = self._binding(
            item_id="item:weak",
            text="canada token",
            reference_id="ref:ocr:weak",
        )
        context = self._context()
        retrieved = retrieve_local(context, (strong.item, weak.item))

        accepted, outcomes = validate_and_rerank_retrieval_results(
            context,
            retrieved,
            policy=CorrectiveRetrievalPolicy(minimum_shared_query_tokens=2),
        )

        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0].rank, 1)
        self.assertIs(accepted[0].item, strong.item)
        self.assertEqual(
            accepted[0].item.provenance.evidence_refs,
            strong.reference_ids,
        )
        self.assertEqual(
            tuple(outcome.decision for outcome in outcomes),
            (
                RetrievalValidationDecision.ACCEPT,
                RetrievalValidationDecision.REJECT,
            ),
        )
        self.assertEqual(
            outcomes[1].reason_codes,
            ("insufficient_query_overlap",),
        )
        strong.validate()
        weak.validate()


if __name__ == "__main__":
    unittest.main()
