"""Headless GUI helper and asynchronous-boundary tests."""

import inspect
import queue
import threading
import unittest

from coin_collection_gui import CoinCollectionGUI
from grounded_collection_assistant import (
    AssistantEvidenceReference,
    AssistantToolCall,
    GroundedAssistantResponse,
)


class FakeAssistant:
    class Adapter:
        provider_name = "Fake"
        model_name = "fake-v1"

    adapter = Adapter()

    def ask(self, question):
        return GroundedAssistantResponse(answer_text=f"Answered: {question}", status="answered")


class AskMyCollectionGUITests(unittest.TestCase):
    def test_distinct_name_and_required_controls_are_present(self):
        menu_source = inspect.getsource(CoinCollectionGUI.create_menu_bar)
        dialog_source = inspect.getsource(CoinCollectionGUI.open_ask_my_collection)
        self.assertIn('label="Ask My Collection"', menu_source)
        self.assertIn('dialog.title("Ask My Collection")', dialog_source)
        for label in ("Submit", "Cancel", "Show Evidence", "Clear Session", "Provider status"):
            self.assertIn(label, dialog_source)
        self.assertNotIn('text="Apply', dialog_source)

    def test_gui_declares_privacy_and_session_only_behavior(self):
        source = inspect.getsource(CoinCollectionGUI.open_ask_my_collection)
        self.assertIn("question and bounded", source)
        self.assertIn("allowlisted tool evidence", source)
        self.assertIn("Images, paths, notes, credentials, and complete records", source)
        self.assertIn("does not save chat history", source)

    def test_worker_uses_queue_and_does_not_require_tk(self):
        results = queue.Queue()
        worker = threading.Thread(
            target=CoinCollectionGUI.run_ask_my_collection_request,
            args=(FakeAssistant(), "standalone", results, 7),
        )
        worker.start()
        worker.join(timeout=1)
        request_id, question, response = results.get_nowait()
        self.assertEqual((7, "standalone", "answered"), (request_id, question, response.status))
        source = inspect.getsource(CoinCollectionGUI.open_ask_my_collection)
        self.assertIn("queue.Queue()", source)
        self.assertIn("threading.Thread", source)
        self.assertIn("dialog.after(50, poll_results)", source)
        self.assertIn("request_assistant = self.create_ask_my_collection_service()", source)

    def test_response_and_evidence_helpers_preserve_backend_text(self):
        response = GroundedAssistantResponse(
            answer_text="Exact cost CAD 10.500.",
            status="answered",
            tool_calls_used=(AssistantToolCall("portfolio_cost_by_currency", {}),),
            evidence_references=(AssistantEvidenceReference("portfolio_cost_by_currency:1", "portfolio_cost_by_currency", "CAD 10.500"),),
            provider_name="Fake",
            model_name="fake-v1",
            truncated=True,
        )
        answer = CoinCollectionGUI.ask_my_collection_response_text(response)
        evidence = CoinCollectionGUI.ask_my_collection_evidence_text(response)
        self.assertIn("CAD 10.500", answer)
        self.assertIn("evidence was truncated", answer)
        self.assertIn("portfolio_cost_by_currency", evidence)
        self.assertIn("Fake", evidence)

    def test_provider_error_does_not_display_exception_message(self):
        class BrokenAssistant(FakeAssistant):
            def ask(self, question):
                raise RuntimeError("secret request data")

        results = queue.Queue()
        CoinCollectionGUI.run_ask_my_collection_request(BrokenAssistant(), "question", results, 1)
        response = results.get_nowait()[2]
        self.assertEqual("error", response.status)
        self.assertNotIn("secret request data", response.answer_text)
        self.assertIn("RuntimeError", response.limitations[0])


if __name__ == "__main__":
    unittest.main()
