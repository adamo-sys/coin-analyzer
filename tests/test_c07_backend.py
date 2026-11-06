"""Actual retained C11 integration with inert binary handles, never native IO."""

from dataclasses import dataclass
import unittest

from tools import c07_capture as capture, c07_backend as backend


@dataclass
class Clock:
    ticks: int = 1000
    frequency: int = 10
    boot: str = "inert-boot"

    def __call__(self):
        return backend.ClockSample(self.ticks, self.frequency, self.boot)


def settle(adapter, passes=300):
    for _ in range(passes):
        adapter.advance()
        receipt = adapter.receipt()
        if adapter.finished or (adapter.rejected and not receipt["pending_operations"]
                                and not adapter.cleanup_ops):
            return receipt
    return adapter.receipt()


class BackendIntegrationTests(unittest.TestCase):
    def adapter(self, *, faults=(), stdout=b'{"inert":true}\n', stderr=b"\xff\0", **options):
        clock = Clock()
        ports = backend.OfflineCapturePorts(capture, clock=clock, stdout=stdout,
                                           stderr=stderr, faults=faults, **options)
        adapter = capture.CaptureAdapter(ports, "a" * 64, "b" * 64, "inert-guest", b"admission\n")
        return clock, ports, adapter

    def test_partial_binary_io_drains_then_flushes_closes_and_reopens(self):
        _, ports, adapter = self.adapter(write_limit=2, read_limit=3)
        receipt = settle(adapter)
        self.assertEqual(receipt["state"], "CAPTURE_COMPLETE_SOURCE_INTERFACE")
        self.assertFalse(receipt["rejected"])
        self.assertEqual([bytes(s.raw) for s in adapter.streams], [b'{"inert":true}\n', b"\xff\0"])
        self.assertEqual(ports.stdin_bytes, b"admission\n")
        self.assertFalse(receipt["pending_operations"])
        self.assertFalse(receipt["unclosed_resources"])
        events = ports.events
        for stream in ("stdout", "stderr"):
            flush = events.index(("FLUSH", stream + "_writer"))
            close = events.index(("CLOSE", stream + "_writer"))
            reopen = events.index(("OPEN_READER", stream + "_writer"))
            self.assertLess(flush, close)
            self.assertLess(close, reopen)
        self.assertEqual(ports.manifest()["runtime_acceptance"], "NOT_ESTABLISHED")

    def test_combined_primary_and_cleanup_errors_retain_payload_and_close_other_resources(self):
        faults = (backend.Fault("READ", "stdout", "partial-error", b"inert-partial\0"),
                  backend.Fault("FLUSH", "stdout_writer", "error"),
                  backend.Fault("CLOSE", "stderr_writer", "error"))
        _, ports, adapter = self.adapter(faults=faults)
        receipt = settle(adapter)
        self.assertTrue(receipt["rejected"])
        failures = {op.kind for op in receipt["failed_operations"]}
        self.assertTrue({"READ", "FLUSH", "CLOSE"} <= failures)
        read = next(op for op in receipt["failed_operations"] if op.kind == "READ")
        self.assertEqual(read.completion.value, b"inert-partial\0")
        self.assertIn(("CLOSE", "stdout_writer"), ports.events)
        self.assertIn(("CLOSE", "process"), ports.events)
        self.assertNotIn(("OPEN_READER", "stdout_writer"), ports.events)
        self.assertIn("stderr_writer", {r.kind for r in receipt["unclosed_resources"]})

    def test_partial_acquisition_and_uncertain_start_keep_ownership(self):
        for fault in (backend.Fault("CONSTRUCT", "", "partial-acquire"),
                      backend.Fault("START", "process", "error")):
            with self.subTest(fault=fault):
                _, ports, adapter = self.adapter(faults=(fault,))
                receipt = settle(adapter)
                self.assertTrue(receipt["rejected"])
                self.assertTrue(adapter.resources)
                self.assertIn(("CLOSE", "process"), ports.events)
                if fault.operation == "START":
                    self.assertIn(("CANCEL", "process"), ports.events)

    def test_descendant_pipe_stays_pending_after_parent_exit_until_deadline(self):
        clock, ports, adapter = self.adapter(hold_stdout_open=True)
        receipt = settle(adapter, 80)
        self.assertIsNotNone(adapter.exit)
        self.assertFalse(adapter.finished)
        self.assertTrue(receipt["pending_operations"])
        clock.ticks = 5200  # T0 + 420 * frequency, equality rejects.
        receipt = settle(adapter, 10)
        self.assertTrue(receipt["rejected"])
        self.assertIn(("CANCEL", "process"), ports.events)
        self.assertTrue(receipt["pending_operations"])
        self.assertEqual(ports.manifest()["deadline_detected_ticks"], 5200)

    def test_counter_discontinuity_and_expired_allowance_cannot_be_reset(self):
        clock, ports, _ = self.adapter()
        self.assertTrue(ports.allowed("OBSERVE"))
        clock.ticks = 999
        self.assertFalse(ports.allowed("OBSERVE"))
        clock.ticks = 1001
        self.assertFalse(ports.allowed("OBSERVE"))
        self.assertIn("CLOCK_DISCONTINUITY", ports.manifest()["rejection_flags"])
        self.assertEqual(ports.manifest()["deadline_ticks"], 5200)
        for change in ({"frequency": True}, {"frequency": 0}, {"ticks": -1}):
            bad = Clock()
            for key, value in change.items():
                setattr(bad, key, value)
            with self.assertRaises(ValueError):
                backend.OfflineCapturePorts(capture, clock=bad, stdout=b"", stderr=b"")


if __name__ == "__main__":
    unittest.main()
