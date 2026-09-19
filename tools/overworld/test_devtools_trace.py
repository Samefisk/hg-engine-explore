"""Real public ring decoder and trace configuration over a bounded host image."""
from copy import deepcopy
from pathlib import Path
import unittest

from tools.overworld.devtools_trace import SemanticTrace
from tools.overworld.trace import HEADER, RECORD, TRACE_MAGIC, TRACE_VERSION, load_trace_schema


SCHEMA = load_trace_schema(Path(__file__).parents[0] / "schemas/semantic-trace-v1.json")


class NativeRing:
    def __init__(self):
        self.base, self.header, self.events, self.capacity = 0x023A0000, 32, 96, 16
        self.memory = bytearray(1024)
        self.writes = []
        self.descriptor = {
            "state": {"address": self.base, "offsets": {"traceHeader": self.header, "traceEvents": self.events}},
            "structures": {"traceHeader": HEADER.size, "traceEvent": RECORD.size},
            "capacities": {"traceEvents": self.capacity, "actors": 10},
        }
        self.reset()

    def reset(self, epoch=4):
        self.memory[self.events:self.events + self.capacity * RECORD.size] = bytes(self.capacity * RECORD.size)
        self.set_header([TRACE_MAGIC, TRACE_VERSION, HEADER.size, 1, 1, 0, 0, epoch, 65535, 0, 0, 0, 0, 0, 0])

    def values(self):
        return list(HEADER.unpack_from(self.memory, self.header))

    def set_header(self, values):
        HEADER.pack_into(self.memory, self.header, *values)

    def read(self, address, size):
        assert self.base <= address <= address + size <= self.base + len(self.memory)
        return bytes(self.memory[address - self.base:address - self.base + size])

    def write(self, address, data):
        assert self.base <= address <= address + len(data) <= self.base + len(self.memory)
        self.writes.append((address, bytes(data)))
        self.memory[address - self.base:address - self.base + len(data)] = data

    def emit(self, event=6, frame=100, epoch=None, value=1):
        values = self.values()
        assert values[13] == 1
        sequence, index = values[4], values[11]
        RECORD.pack_into(self.memory, self.events + index * RECORD.size,
                         sequence, frame, 0, 2, values[7] if epoch is None else epoch,
                         5, 6, 0, event, 0, value, 8)
        values[4] += 1
        values[11] = (index + 1) % self.capacity
        if values[12] == self.capacity:
            values[3] += 1
            values[5] += 1
        else:
            values[12] += 1
        self.set_header(values)

    def tap(self):
        return SemanticTrace(self.read, self.write, self.descriptor, SCHEMA)


def natives(events):
    return [item["data"] for item in events if item["kind"] == "native"]


def notices(events):
    return {item["data"]["code"]: item["data"] for item in events if item["kind"] == "trace-status"}


class SemanticTraceTests(unittest.TestCase):
    def test_real_decode_preserves_actor_identity_clocks_and_native_events(self):
        ring = NativeRing()
        tap = ring.tap()
        tap.start(frame_limit=60)
        self.assertEqual(ring.values()[10], 60)
        for event in (6, 7, 13, 16, 18):
            ring.emit(event, frame=100 + event)
        events = tap.sample(900)
        self.assertEqual([e["event"] for e in natives(events)],
                         ["INTENT_CREATED", "CANDIDATE_REJECTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTEXT_CHANGED"])
        self.assertEqual(natives(events)[0]["actorFrame"], 106)
        self.assertEqual(natives(events)[0]["frame"], 106)
        self.assertEqual(events[-1]["frame"], 900)
        self.assertEqual(natives(events)[0]["actorHandle"], 2 << 16)
        self.assertEqual(natives(events)[0]["actor"]["encounterGeneration"], 6)
        self.assertEqual(tap.sample(901), [])
        self.assertEqual(len(ring.writes), 2)  # Configuration only; sampling is read-only.

    def test_ring_overflow_reports_exact_unread_gap_without_fake_records(self):
        ring = NativeRing()
        tap = ring.tap()
        tap.start()
        for _ in range(20):
            ring.emit()
        events = tap.sample(1)
        self.assertEqual([e["sequence"] for e in natives(events)], list(range(5, 21)))
        self.assertEqual(notices(events)["unread-events-lost"]["count"], 4)
        self.assertEqual(notices(events)["ring-overwrite"]["count"], 4)
        self.assertFalse(notices(events)["unread-events-lost"]["coverageComplete"])
        self.assertEqual(tap.sample(2), [])

    def test_overwriting_already_read_events_is_not_an_unread_gap(self):
        ring = NativeRing()
        tap = ring.tap()
        tap.start()
        for _ in range(16):
            ring.emit()
        tap.sample(1)
        ring.emit()
        result = tap.sample(2)
        self.assertNotIn("unread-events-lost", notices(result))
        self.assertEqual(notices(result)["ring-overwrite"]["unreadEventsLost"], 0)
        self.assertEqual([e["sequence"] for e in natives(result)], [17])

    def test_field_rebind_retains_sequence_and_old_event_identity(self):
        ring = NativeRing()
        tap = ring.tap()
        tap.start()
        ring.emit(18, epoch=4)
        tap.sample(1)
        header = ring.values()
        header[7] = 5
        ring.set_header(header)
        ring.emit(1, epoch=5)
        result = tap.sample(2)
        self.assertEqual([e["sequence"] for e in natives(result)], [2])
        self.assertEqual(natives(result)[0]["actor"]["fieldEpoch"], 5)
        self.assertFalse(notices(result)["field-epoch-changed"]["sequenceReset"])
        self.assertEqual(tap.stream, 1)

    def test_reset_and_sequence_reuse_are_explicit_new_streams(self):
        ring = NativeRing()
        tap = ring.tap()
        tap.start()
        for _ in range(3):
            ring.emit()
        tap.sample(1)
        ring.reset(epoch=5)
        header = ring.values()
        header[13] = 1
        ring.set_header(header)
        # New stream may already contain as many records as the previous one.
        for _ in range(3):
            ring.emit(frame=200)
        result = tap.sample(2)
        self.assertEqual(len(natives(result)), 3)
        self.assertTrue(notices(result)["sequence-reset"]["sequenceReused"])
        self.assertEqual(tap.stream, 2)
        self.assertEqual(tap.sample(3), [])

    def test_known_bad_duplicate_sequence_cannot_pass_real_decoder_window(self):
        ring = NativeRing()
        tap = ring.tap()
        tap.start()
        ring.emit()
        ring.emit()
        first = bytes(ring.memory[ring.events:ring.events + RECORD.size])
        ring.memory[ring.events + RECORD.size:ring.events + 2 * RECORD.size] = first
        result = tap.sample(1)
        self.assertEqual(natives(result), [])
        self.assertIn("invalid-native-ring", notices(result))
        self.assertEqual(tap.sample(2), [])

    def test_known_bad_missing_ring_record_is_reported_not_filled(self):
        ring = NativeRing()
        tap = ring.tap()
        tap.start()
        ring.emit()
        ring.memory[ring.events:ring.events + RECORD.size] = bytes(RECORD.size)
        result = tap.sample(1)
        self.assertEqual(natives(result), [])
        self.assertIn("invalid-native-ring", notices(result))

    def test_stop_keeps_tail_readable_and_restart_is_explicit(self):
        ring = NativeRing()
        tap = ring.tap()
        tap.start()
        ring.emit()
        tap.stop()
        self.assertEqual(ring.values()[13], 0)
        result = tap.sample(1)
        self.assertEqual(len(natives(result)), 1)
        self.assertEqual(notices(result)["window-ended"]["reason"], "stopped")
        tap.start(20)
        result = tap.sample(2)
        self.assertIn("window-restarted", notices(result))
        self.assertEqual(natives(result), [])

    def test_budget_expiry_is_visible_once_and_does_not_rearm(self):
        ring = NativeRing()
        tap = ring.tap()
        tap.start(1)
        header = ring.values()
        header[10], header[13] = 0, 0
        ring.set_header(header)
        writes = len(ring.writes)
        self.assertEqual(notices(tap.sample(1))["window-ended"]["reason"], "budget-expired-or-disarmed")
        self.assertEqual(tap.sample(2), [])
        self.assertEqual(len(ring.writes), writes)

    def test_header_change_during_read_is_not_a_coherent_native_event(self):
        ring = NativeRing()
        tap = ring.tap()
        tap.start()
        original_read = tap.read
        changed = False
        def read(address, size):
            nonlocal changed
            result = original_read(address, size)
            if address == tap.events_address and not changed:
                ring.emit()
                changed = True
            return result
        tap.read = read
        result = tap.sample(1)
        self.assertEqual(natives(result), [])
        self.assertIn("invalid-native-ring", notices(result))
        recovered = tap.sample(2)
        self.assertEqual([e["sequence"] for e in natives(recovered)], [1])
        self.assertIn("read-recovered", notices(recovered))

    def test_external_filter_changes_are_reported_once(self):
        ring = NativeRing()
        tap = ring.tap()
        tap.start()
        tap.sample(0)
        header = ring.values()
        header[6] = 1 << 13
        ring.set_header(header)
        self.assertIn("trace-filter-changed", notices(tap.sample(1)))
        self.assertEqual(tap.sample(2), [])

    def test_restart_reports_discarded_unread_tail(self):
        ring = NativeRing()
        tap = ring.tap()
        tap.start(65535)
        ring.emit()
        ring.emit()
        tap.stop()
        tap.start()
        status = notices(tap.sample(1))["window-restarted"]
        self.assertEqual(status["discardedUnreadBeforeRestart"], 2)

    def test_other_trace_and_bad_layout_or_frame_limits_fail_before_write(self):
        ring = NativeRing()
        tap = ring.tap()
        header = ring.values()
        header[13] = 1
        ring.set_header(header)
        with self.assertRaisesRegex(ValueError, "another trace"):
            tap.start()
        self.assertEqual(ring.writes, [])
        header[13] = 0
        ring.set_header(header)
        for limit in (0, 65536, True):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                tap.start(limit)
        bad = deepcopy(ring.descriptor)
        bad["state"]["offsets"]["traceEvents"] = 32
        with self.assertRaisesRegex(ValueError, "overlaps"):
            SemanticTrace(ring.read, ring.write, bad, SCHEMA)


if __name__ == "__main__":
    unittest.main()
