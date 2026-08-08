from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import inference_telemetry
from inference_pricing import (
    MODEL_PRICING_USD_PER_MILLION,
    TokenPricing,
    estimate_inference_cost_usd,
)
from inference_telemetry import (
    InferenceTelemetryRecord,
    JsonlTelemetryStore,
    current_scan_id,
    get_default_telemetry_sink,
    instrument_inference,
    response_token_usage,
    scan_id_from_workspace,
    telemetry_scan,
)


class _Sink:
    def __init__(self) -> None:
        self.records: list[InferenceTelemetryRecord] = []

    def write(self, record: InferenceTelemetryRecord) -> None:
        self.records.append(record)


class _FailingSink:
    def write(self, _record: InferenceTelemetryRecord) -> None:
        raise OSError("telemetry disk unavailable")


class _Clock:
    def __init__(self, *values: float) -> None:
        self.values = iter(values)

    def __call__(self) -> float:
        return next(self.values)


class InferenceTelemetryTests(unittest.TestCase):
    def test_success_preserves_return_and_records_duration_and_local_cost(self) -> None:
        sink = _Sink()
        marker = object()

        with telemetry_scan("scan-1"):
            result = instrument_inference(
                lambda: marker,
                stage="tesseract-ocr",
                provider="Tesseract",
                model="pytesseract.image_to_string --psm 11",
                sink=sink,
                clock=_Clock(10.0, 10.025),
            )

        self.assertIs(result, marker)
        self.assertEqual(len(sink.records), 1)
        record = sink.records[0]
        self.assertEqual(record.scan_id, "scan-1")
        self.assertEqual(record.stage, "tesseract-ocr")
        self.assertEqual(record.provider, "Tesseract")
        self.assertEqual(record.model, "pytesseract.image_to_string --psm 11")
        self.assertAlmostEqual(record.duration_ms, 25.0)
        self.assertTrue(record.success)
        self.assertIsNone(record.error_type)
        self.assertIsNone(record.input_tokens)
        self.assertIsNone(record.output_tokens)
        self.assertEqual(record.estimated_cost_usd, 0.0)

    def test_failure_is_recorded_and_original_exception_is_reraised(self) -> None:
        sink = _Sink()
        failure = RuntimeError("provider failed")

        with self.assertRaises(RuntimeError) as raised:
            instrument_inference(
                lambda: (_ for _ in ()).throw(failure),
                scan_id="scan-2",
                stage="cloud-plan",
                provider="OpenAI",
                model="unknown-model",
                sink=sink,
                clock=_Clock(4.0, 4.01),
            )

        self.assertIs(raised.exception, failure)
        self.assertFalse(sink.records[0].success)
        self.assertEqual(sink.records[0].error_type, "RuntimeError")
        self.assertIsNone(sink.records[0].estimated_cost_usd)

    def test_telemetry_failure_never_changes_primary_outcome(self) -> None:
        self.assertEqual(
            instrument_inference(
                lambda: "primary-result",
                scan_id="scan-3",
                stage="test",
                provider="Tesseract",
                model="local",
                sink=_FailingSink(),
            ),
            "primary-result",
        )

    def test_pricing_failure_after_success_preserves_provider_result(self) -> None:
        marker = object()
        with patch(
            "inference_telemetry.estimate_inference_cost_usd",
            side_effect=RuntimeError("pricing unavailable"),
        ):
            result = instrument_inference(
                lambda: marker,
                scan_id="scan-pricing-success",
                stage="cloud",
                provider="OpenAI",
                model="model",
                sink=_Sink(),
            )

        self.assertIs(result, marker)

    def test_pricing_failure_during_provider_failure_preserves_original(self) -> None:
        provider_error = LookupError("provider failed")
        with (
            patch(
                "inference_telemetry.estimate_inference_cost_usd",
                side_effect=RuntimeError("pricing unavailable"),
            ),
            self.assertRaises(LookupError) as raised,
        ):
            instrument_inference(
                lambda: (_ for _ in ()).throw(provider_error),
                scan_id="scan-pricing-failure",
                stage="cloud",
                provider="OpenAI",
                model="model",
                sink=_Sink(),
            )

        self.assertIs(raised.exception, provider_error)

    def test_invalid_record_construction_preserves_success_and_failure(self) -> None:
        marker = object()
        provider_error = RuntimeError("provider failed")
        with patch(
            "inference_telemetry.InferenceTelemetryRecord",
            side_effect=ValueError("invalid telemetry record"),
        ):
            self.assertIs(
                instrument_inference(
                    lambda: marker,
                    scan_id="scan-invalid-success",
                    stage="stage",
                    provider="Tesseract",
                    model="local",
                    sink=_Sink(),
                ),
                marker,
            )
            with self.assertRaises(RuntimeError) as raised:
                instrument_inference(
                    lambda: (_ for _ in ()).throw(provider_error),
                    scan_id="scan-invalid-failure",
                    stage="stage",
                    provider="Tesseract",
                    model="local",
                    sink=_Sink(),
                )

        self.assertIs(raised.exception, provider_error)

    def test_sink_failure_preserves_original_provider_exception(self) -> None:
        provider_error = RuntimeError("provider failed")
        with self.assertRaises(RuntimeError) as raised:
            instrument_inference(
                lambda: (_ for _ in ()).throw(provider_error),
                scan_id="scan-sink-failure",
                stage="stage",
                provider="Tesseract",
                model="local",
                sink=_FailingSink(),
            )

        self.assertIs(raised.exception, provider_error)

    def test_serialization_failure_preserves_success_and_provider_failure(self) -> None:
        marker = object()
        provider_error = RuntimeError("provider failed")
        with tempfile.TemporaryDirectory() as temporary:
            store = JsonlTelemetryStore(Path(temporary) / "inference.jsonl")
            with patch(
                "inference_telemetry.json.dumps",
                side_effect=TypeError("serialization failed"),
            ):
                self.assertIs(
                    instrument_inference(
                        lambda: marker,
                        scan_id="scan-serialization-success",
                        stage="stage",
                        provider="Tesseract",
                        model="local",
                        sink=store,
                    ),
                    marker,
                )
                with self.assertRaises(RuntimeError) as raised:
                    instrument_inference(
                        lambda: (_ for _ in ()).throw(provider_error),
                        scan_id="scan-serialization-failure",
                        stage="stage",
                        provider="Tesseract",
                        model="local",
                        sink=store,
                    )

        self.assertIs(raised.exception, provider_error)

    def test_supplied_tokens_use_one_centralized_price_catalog(self) -> None:
        class Usage:
            input_tokens = 1_000
            output_tokens = 500

        class Response:
            usage = Usage()

        sink = _Sink()
        key = ("openai", "priced-test-model")
        with patch.dict(
            MODEL_PRICING_USD_PER_MILLION,
            {
                key: TokenPricing(
                    input_usd_per_million=Decimal("2"),
                    output_usd_per_million=Decimal("8"),
                )
            },
        ):
            instrument_inference(
                Response,
                scan_id="scan-4",
                stage="cloud",
                provider="OpenAI",
                model="priced-test-model",
                sink=sink,
                usage_resolver=response_token_usage,
            )

        record = sink.records[0]
        self.assertEqual(record.input_tokens, 1_000)
        self.assertEqual(record.output_tokens, 500)
        self.assertAlmostEqual(record.estimated_cost_usd, 0.006)

    def test_unknown_pricing_is_safe(self) -> None:
        self.assertIsNone(
            estimate_inference_cost_usd(
                provider="OpenAI",
                model="not-in-catalog",
                input_tokens=10,
                output_tokens=5,
            )
        )

    def test_jsonl_store_persists_one_closed_record_per_line(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "telemetry" / "inference.jsonl"
            store = JsonlTelemetryStore(path)
            record = InferenceTelemetryRecord(
                scan_id="scan-5",
                stage="test",
                provider="Tesseract",
                model="local",
                duration_ms=1.0,
                success=True,
                error_type=None,
                input_tokens=None,
                output_tokens=None,
                estimated_cost_usd=0.0,
            )
            store.write(record)

            lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0]), record.to_dict())

    def test_record_validation_rejects_non_finite_or_unstable_values(self) -> None:
        def record(**overrides):
            values = {
                "scan_id": "scan-validation",
                "stage": "stage",
                "provider": "Tesseract",
                "model": "local",
                "duration_ms": 1.0,
                "success": True,
                "error_type": None,
                "input_tokens": None,
                "output_tokens": None,
                "estimated_cost_usd": 0.0,
            }
            values.update(overrides)
            return InferenceTelemetryRecord(**values)

        for duration in (math.nan, math.inf, -math.inf, -0.1):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                record(duration_ms=duration)
        for cost in (math.nan, math.inf, -math.inf, -0.1):
            with self.subTest(cost=cost), self.assertRaises(ValueError):
                record(estimated_cost_usd=cost)
        for field in ("input_tokens", "output_tokens"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                record(**{field: -1})
        for error_type in (
            "Runtime error message",
            "RuntimeError: secret",
            "RuntimeError\ntraceback",
            "",
        ):
            with self.subTest(error_type=error_type), self.assertRaises(ValueError):
                record(success=False, error_type=error_type)

        valid = record(success=False, error_type="providers.RuntimeUnavailable")
        self.assertEqual(valid.error_type, "providers.RuntimeUnavailable")

    def test_default_sink_is_singleton_and_each_operation_records_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "inference.jsonl"
            with (
                patch.object(inference_telemetry, "DEFAULT_TELEMETRY_PATH", path),
                patch.object(inference_telemetry, "_DEFAULT_SINK", None),
            ):
                first = get_default_telemetry_sink()
                second = get_default_telemetry_sink()
                self.assertIs(first, second)
                for scan_id in ("entry-1", "entry-2"):
                    instrument_inference(
                        lambda: "result",
                        scan_id=scan_id,
                        stage="stage",
                        provider="Tesseract",
                        model="local",
                        sink=get_default_telemetry_sink(),
                    )

            lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(
            [json.loads(line)["scan_id"] for line in lines],
            ["entry-1", "entry-2"],
        )

    def test_nested_context_restores_and_does_not_leak(self) -> None:
        self.assertEqual(current_scan_id(), "unscoped")
        with telemetry_scan("outer"):
            self.assertEqual(current_scan_id(), "outer")
            with telemetry_scan("inner"):
                self.assertEqual(current_scan_id(), "inner")
            self.assertEqual(current_scan_id(), "outer")
        self.assertEqual(current_scan_id(), "unscoped")

    def test_concurrent_contexts_and_jsonl_writes_remain_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "inference.jsonl"
            store = JsonlTelemetryStore(path)

            def write(index: int) -> None:
                with telemetry_scan(f"scan-{index}"):
                    instrument_inference(
                        lambda: index,
                        stage="stage",
                        provider="Tesseract",
                        model="local",
                        sink=store,
                    )

            with ThreadPoolExecutor(max_workers=16) as pool:
                list(pool.map(write, range(100)))

            lines = path.read_text(encoding="utf-8").splitlines()
        records = [json.loads(line) for line in lines]
        self.assertEqual(len(records), 100)
        self.assertEqual(
            {record["scan_id"] for record in records},
            {f"scan-{index}" for index in range(100)},
        )

    def test_existing_workspace_id_is_reused_for_scan_correlation(self) -> None:
        token = "0123456789abcdef0123456789abcdef"
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / f"workflow-{token}"
            workspace.mkdir()

            self.assertEqual(scan_id_from_workspace(workspace), token)

    def test_nonstandard_workspace_uses_stable_non_path_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            workspace.mkdir()
            first = scan_id_from_workspace(workspace)
            second = scan_id_from_workspace(workspace)

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("workspace-"))
        self.assertNotIn(temporary, first)


if __name__ == "__main__":
    unittest.main()
