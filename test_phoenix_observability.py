from __future__ import annotations

from types import SimpleNamespace
import unittest

from phoenix_observability import PhoenixTraceSnapshot, emit_to_phoenix, snapshot_specialized_experiment


class _Span:
    def __init__(self) -> None:
        self.attributes: dict[str, object] = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value


class _Tracer:
    def __init__(self, span: _Span) -> None:
        self.span = span
        self.name = None

    def start_as_current_span(self, name: str):
        self.name = name
        return self.span


class _Provider:
    def __init__(self, tracer: _Tracer) -> None:
        self.tracer = tracer
        self.instrumentation_name = None

    def get_tracer(self, name: str):
        self.instrumentation_name = name
        return self.tracer


class PhoenixObservabilityTests(unittest.TestCase):
    def test_snapshot_contains_only_bounded_decision_metadata(self) -> None:
        result = SimpleNamespace(
            experiment=SimpleNamespace(
                experiment_id="experiment-1",
                state=SimpleNamespace(value="multiple_viable_candidates"),
                candidate_ids=("minimal", "alternative"),
                viable_candidate_ids=("minimal", "alternative"),
                preferred_candidate_id=None,
                human_review_required=True,
            ),
            strategy_metadata=(
                SimpleNamespace(strategy=SimpleNamespace(value="minimal_change")),
                SimpleNamespace(strategy=SimpleNamespace(value="alternative_design")),
            ),
        )

        snapshot = snapshot_specialized_experiment(result)

        self.assertEqual(snapshot.experiment_id, "experiment-1")
        self.assertEqual(snapshot.candidate_ids, ("minimal", "alternative"))
        self.assertEqual(
            snapshot.strategies,
            ("minimal_change", "alternative_design"),
        )
        self.assertTrue(snapshot.human_review_required)

    def test_emission_is_advisory_when_phoenix_is_unavailable(self) -> None:
        snapshot = PhoenixTraceSnapshot(
            "experiment-1",
            "stopped",
            ("a", "b"),
            (),
            None,
            False,
            ("minimal_change", "alternative_design"),
        )

        def unavailable(**kwargs):
            raise ModuleNotFoundError("phoenix")

        report = emit_to_phoenix(snapshot, register_fn=unavailable)

        self.assertFalse(report.emitted)
        self.assertEqual(report.reason, "ModuleNotFoundError")

    def test_emission_sets_only_bounded_span_attributes(self) -> None:
        span = _Span()
        tracer = _Tracer(span)
        provider = _Provider(tracer)
        calls: list[dict[str, object]] = []

        def register(**kwargs):
            calls.append(kwargs)
            return provider

        snapshot = PhoenixTraceSnapshot(
            "experiment-7",
            "one_viable_candidate",
            ("minimal", "alternative"),
            ("minimal",),
            "minimal",
            True,
            ("minimal_change", "alternative_design"),
        )
        report = emit_to_phoenix(snapshot, register_fn=register)

        self.assertTrue(report.emitted)
        self.assertEqual(calls[0]["auto_instrument"], False)
        self.assertEqual(calls[0]["set_global_tracer_provider"], False)
        self.assertEqual(tracer.name, "stage11.specialized_parallel_experiment")
        self.assertEqual(
            provider.instrumentation_name,
            "coin-analyzer.self-improvement",
        )
        self.assertEqual(
            span.attributes["coin_analyzer.preferred_candidate_id"],
            "minimal",
        )
        self.assertTrue(span.attributes["coin_analyzer.human_review_required"])
        self.assertNotIn("package", " ".join(span.attributes))
        self.assertNotIn("terminal_reason", " ".join(span.attributes))


if __name__ == "__main__":
    unittest.main()
