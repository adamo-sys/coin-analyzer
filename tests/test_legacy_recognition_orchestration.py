import ast
from pathlib import Path
import re
import unittest

from legacy_recognition_orchestration import (
    LEGACY_COIN_RECOGNITION,
    DeterministicRecognitionRouter,
    RecognitionCapabilityRegistry,
    RecognitionCapabilityResult,
    RecognitionOrchestrator,
    RecognitionRoute,
    RecognitionRouteDecision,
    RecognitionStage,
    RecognitionState,
    RecognitionStatus,
)


def successful_result(confidence=None, findings=None):
    return RecognitionCapabilityResult(
        capability=LEGACY_COIN_RECOGNITION,
        success=True,
        findings=findings
        or {"country": "Canada", "denomination": "25 cents", "year": "1907"},
        confidence=confidence,
        evidence=("private full evidence",),
    )


class FakeCapability:
    name = LEGACY_COIN_RECOGNITION

    def __init__(self, result=None, error=None):
        self.result = result or successful_result()
        self.error = error
        self.calls = []

    def execute(self, image_reference):
        self.calls.append(image_reference)
        if self.error:
            raise self.error
        return self.result


class RegistryAndRouterTests(unittest.TestCase):
    def test_registry_allowlists_known_capability_and_rejects_duplicate_unknown(self):
        capability = FakeCapability()
        registry = RecognitionCapabilityRegistry((capability,))

        self.assertEqual((LEGACY_COIN_RECOGNITION,), registry.names())
        self.assertIs(capability, registry.get(LEGACY_COIN_RECOGNITION))
        with self.assertRaises(ValueError):
            registry.register(FakeCapability())
        with self.assertRaises(KeyError):
            registry.get("invented-specialist")

    def test_router_is_deterministic_for_every_stage_outcome(self):
        router = DeterministicRecognitionRouter()
        missing = RecognitionState("scan_test", "")
        fresh = RecognitionState("scan_test", "coin.jpg")
        failed = RecognitionState("scan_test", "coin.jpg")
        failed.results.append(RecognitionCapabilityResult(LEGACY_COIN_RECOGNITION, False))
        incomplete = RecognitionState("scan_test", "coin.jpg")
        incomplete.results.append(
            successful_result(findings={"country": "Canada", "denomination": "", "year": None})
        )
        unknown_confidence = RecognitionState("scan_test", "coin.jpg")
        unknown_confidence.results.append(successful_result())

        self.assertIs(RecognitionRoute.REQUEST_IMAGE, router.route(missing).route)
        self.assertIs(RecognitionRoute.RUN_CAPABILITY, router.route(fresh).route)
        self.assertIs(RecognitionRoute.REQUIRE_COLLECTOR_REVIEW, router.route(failed).route)
        self.assertIn("denomination", router.route(incomplete).reason)
        self.assertIn("unavailable", router.route(unknown_confidence).reason)


class OrchestratorTests(unittest.TestCase):
    @staticmethod
    def orchestrator(capability, events=None, router=None):
        telemetry = None
        if events is not None:
            telemetry = lambda name, payload: events.append((name, dict(payload)))
        return RecognitionOrchestrator(
            RecognitionCapabilityRegistry((capability,)),
            router=router,
            telemetry=telemetry,
            clock=iter((10.0, 10.025)).__next__,
        )

    def test_one_call_and_terminal_collector_review(self):
        capability = FakeCapability()

        state = self.orchestrator(capability).run("coin.jpg")

        self.assertEqual(["coin.jpg"], capability.calls)
        self.assertEqual(1, state.capability_calls)
        self.assertEqual(1, len(state.results))
        self.assertIs(RecognitionStage.REVIEW, state.stage)
        self.assertIs(RecognitionStatus.AWAITING_COLLECTOR_REVIEW, state.status)

    def test_repeating_router_cannot_loop_or_bypass_call_limit(self):
        class AlwaysRun:
            def route(self, _state):
                return RecognitionRouteDecision(
                    RecognitionRoute.RUN_CAPABILITY,
                    "repeat",
                    LEGACY_COIN_RECOGNITION,
                )

        capability = FakeCapability()
        state = self.orchestrator(capability, router=AlwaysRun()).run("coin.jpg")

        self.assertEqual(["coin.jpg"], capability.calls)
        self.assertEqual(1, state.capability_calls)
        self.assertEqual("call_limit", state.results[-1].failure_category)
        self.assertIs(RecognitionRoute.REQUIRE_COLLECTOR_REVIEW, state.last_route.route)

    def test_missing_image_terminates_without_capability_call(self):
        capability = FakeCapability()

        state = self.orchestrator(capability).run("")

        self.assertEqual([], capability.calls)
        self.assertIs(RecognitionStatus.NEEDS_INPUT, state.status)

    def test_capability_exception_becomes_bounded_private_failure(self):
        capability = FakeCapability(error=RuntimeError("C:/collector/private/coin.jpg"))

        state = self.orchestrator(capability).run("coin.jpg")

        self.assertFalse(state.results[0].success)
        self.assertEqual("RuntimeError", state.results[0].failure_category)
        self.assertNotIn("collector", " ".join(state.results[0].warnings))
        self.assertIs(RecognitionStatus.AWAITING_COLLECTOR_REVIEW, state.status)

    def test_scan_id_is_internal_and_caller_cannot_supply_one(self):
        state = self.orchestrator(FakeCapability()).run("coin.jpg")

        self.assertRegex(state.scan_id, r"^scan_[0-9a-f]{32}$")
        with self.assertRaises(TypeError):
            self.orchestrator(FakeCapability()).run("coin.jpg", scan_id="C:/private.jpg")

    def test_telemetry_order_payload_and_privacy(self):
        events = []

        self.orchestrator(FakeCapability(), events).run("C:/collector/private/coin.jpg")

        self.assertEqual(
            [name for name, _ in events],
            [
                "recognition.started",
                "recognition.routed",
                "recognition.capability_completed",
                "recognition.routed",
                "recognition.awaiting_review",
            ],
        )
        allowed = {
            "scan_id",
            "stage",
            "status",
            "warning_count",
            "evidence_count",
            "confidence",
            "capability",
            "route",
            "success",
            "duration_ms",
            "failure_category",
        }
        self.assertTrue(all(set(payload) <= allowed for _, payload in events))
        serialized = repr(events)
        self.assertNotIn("private/coin.jpg", serialized)
        self.assertNotIn("private full evidence", serialized)
        self.assertEqual({25}, {p["duration_ms"] for n, p in events if n.endswith("completed")})
        self.assertEqual(1, len({payload["scan_id"] for _, payload in events}))

    def test_telemetry_failure_cannot_change_recognition(self):
        def fail(_name, _payload):
            raise RuntimeError("telemetry unavailable")

        orchestrator = RecognitionOrchestrator(
            RecognitionCapabilityRegistry((FakeCapability(),)), telemetry=fail
        )

        self.assertTrue(orchestrator.run("coin.jpg").results[0].success)

    def test_one_call_limit_cannot_be_configured_higher(self):
        with self.assertRaises(ValueError):
            RecognitionOrchestrator(RecognitionCapabilityRegistry(), max_capability_calls=2)

    def test_core_import_boundary_is_standard_library_only(self):
        tree = ast.parse(Path("legacy_recognition_orchestration.py").read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")
        allowed = {
            "__future__",
            "dataclasses",
            "enum",
            "math",
            "time",
            "types",
            "typing",
            "uuid",
        }
        self.assertLessEqual(imports, allowed)
        self.assertFalse(any(re.search("gui|persist|provider|capture_import|confirmed", name) for name in imports))


if __name__ == "__main__":
    unittest.main()
