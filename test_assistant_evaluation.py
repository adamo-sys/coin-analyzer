"""Evaluation corpus and metric-scoring regression tests."""

import unittest
from pathlib import Path

from assistant_evaluation import aggregate_scores, load_evaluation_cases, score_evaluation_case
from grounded_collection_assistant import AssistantEvidenceReference, AssistantToolCall, GroundedAssistantResponse


class AssistantEvaluationTests(unittest.TestCase):
    def test_sanitized_corpus_covers_supported_and_refusal_intents(self):
        cases = load_evaluation_cases(Path("test_data") / "assistant_eval_cases.json")
        self.assertGreaterEqual(len(cases), 8)
        statuses = {case.expected_status for case in cases}
        self.assertEqual({"answered", "clarification", "unsupported"}, statuses)
        self.assertTrue(any("portfolio" in tool for case in cases for tool in case.expected_tools))
        self.assertTrue(any("collection" in tool for case in cases for tool in case.expected_tools))

    def test_metric_score_covers_grounding_privacy_order_and_latency(self):
        case = load_evaluation_cases(Path("test_data") / "assistant_eval_cases.json")[0]
        call = AssistantToolCall("inventory_count", {"country": "Canada", "denomination": "1 cent"})
        response = GroundedAssistantResponse(
            answer_text="Matched 1 collection record.",
            status="answered",
            tool_calls_used=(call,),
            evidence_references=(AssistantEvidenceReference("inventory_count:1", "inventory_count", "count"),),
        )
        score = score_evaluation_case(case, response, elapsed_seconds=0.01, cloud_payloads=[])
        self.assertTrue(score.passed)
        aggregate = aggregate_scores([score])
        self.assertTrue(all(value == 1.0 for value in aggregate.values()))


if __name__ == "__main__":
    unittest.main()
