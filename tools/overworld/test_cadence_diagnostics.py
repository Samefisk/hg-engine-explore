"""Guest-bin diagnostics are independent of host CPU cost and never proof."""
import unittest
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile

from .cadence_diagnostics import inspect_manifest, main, summarize
from .runtime_cadence import guest_queue_delay


def snapshot(frame, cycle):
    return {"frame": frame, "nativeCycle": cycle, "fieldAvailable": True,
            "observationBoundary": "main-task-queue-completion",
            "fieldControl": {"fieldPointer": 0x02200000, "taskPointer": 0},
            "context": {"mapId": 34, "fieldEpoch": 1}, "player": {"x": 1}}


class CadenceDiagnosticsTests(unittest.TestCase):
    def rows(self, cycles):
        return [{"phase": "observe", "samples": [snapshot(i + 1, c)]}
                for i, c in enumerate(cycles)]

    def clock_rows(self, cycles, ticks):
        rows = self.rows(cycles)
        for row, tick in zip(rows, ticks):
            sample = row["samples"][0]
            sample["guestQueueClock"] = dict(version=1, running=True,
                scope="nds-scheduler-ticks-not-cpu-or-instructions",
                arm9Timestamp=tick, arm7Timestamp=tick // 2,
                frameSequence=sample["nativeCycle"])
        return rows

    def run_budget(self, rows, budget):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = root / "observations.jsonl"
            data = "\n".join(json.dumps(row) for row in rows) + "\n"
            evidence.write_text(data)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"state": "completed", "runId": "test-budget",
                "observationsArtifact": {"path": str(evidence), "size": len(data.encode()),
                "sha256": hashlib.sha256(data.encode()).hexdigest()}}))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = main([str(manifest), "--max-two-queue-ticks", str(budget)])
            return status, json.loads(output.getvalue())

    def test_old_data_has_missing_clock_coverage_not_zero_time(self):
        report = summarize(self.rows([10, 12, 14]))["guestQueueClock"]
        self.assertEqual(report["missingClockPairs"], 2)
        self.assertEqual(report["observedIntervals"], 0)
        self.assertFalse(report["coverageComplete"])
        self.assertIsNone(report["maximumArm9Ticks"])
        self.assertIsNone(report["medianArm9Ticks"])

    def test_exact_intervals_distinguish_time_inside_three_bins(self):
        result = summarize(self.clock_rows([10, 13, 14, 16], [0, 290, 400, 600]))
        self.assertEqual(result["longGaps"], [])
        clock = result["guestQueueClock"]
        self.assertTrue(clock["coverageComplete"])
        self.assertEqual(clock["observedIntervals"], 3)
        self.assertEqual((clock["minimumArm9Ticks"], clock["medianArm9Ticks"], clock["maximumArm9Ticks"]), (110, 200, 290))
        self.assertEqual(clock["topIntervals"][0]["frames"], [1, 2])
        self.assertEqual(clock["topIntervals"][0]["nativeFrameBins"], 3)
        self.assertFalse(result["acceptedProof"])

    def test_two_queue_budget_passes_with_actual_eligible_triple(self):
        status, result = self.run_budget(
            self.clock_rows([10, 12, 14], [0, 100, 250]), 250)
        self.assertEqual(status, 0)
        clock = result["guestQueueClock"]
        self.assertEqual(clock["observedTwoQueueIntervals"], 1)
        self.assertEqual(clock["missingClockTriples"], 0)
        self.assertTrue(clock["twoQueueCoverageComplete"])
        self.assertEqual(clock["maximumTwoQueueArm9Ticks"], 250)
        self.assertEqual(clock["topTwoQueueIntervals"][0]["frames"], [1, 3])
        self.assertEqual(result["maxTwoQueueTicksCheck"]["reason"], "within-budget")

    def test_two_queue_budget_fails_when_maximum_is_exceeded(self):
        status, result = self.run_budget(
            self.clock_rows([10, 12, 14], [0, 100, 251]), 250)
        self.assertEqual(status, 1)
        self.assertEqual(result["guestQueueClock"]["maximumTwoQueueArm9Ticks"], 251)
        self.assertEqual(result["maxTwoQueueTicksCheck"]["reason"], "budget-exceeded")

    def test_two_queue_budget_missing_clocks_cannot_pass(self):
        status, result = self.run_budget(self.rows([10, 12, 14]), 999999)
        self.assertEqual(status, 1)
        self.assertEqual(result["guestQueueClock"]["observedTwoQueueIntervals"], 0)
        self.assertEqual(result["guestQueueClock"]["missingClockTriples"], 1)
        self.assertEqual(result["maxTwoQueueTicksCheck"]["reason"], "missing-clock-triples")

    def test_two_queue_window_does_not_cross_context_break(self):
        rows = self.clock_rows([10, 12, 14], [0, 100, 1000])
        rows[2]["samples"][0]["context"] = {"mapId": 99}
        status, result = self.run_budget(rows, 250)
        self.assertEqual(status, 1)
        self.assertEqual(result["guestQueueClock"]["eligibleTwoQueueIntervals"], 0)
        self.assertEqual(result["maxTwoQueueTicksCheck"]["reason"], "no-eligible-triples")

    def test_two_queue_window_does_not_cross_command_break(self):
        rows = self.clock_rows([10, 12, 14], [0, 100, 1000])
        rows.insert(2, {"phase": "observe", "command": {"type": "setup"}, "samples": []})
        status, result = self.run_budget(rows, 250)
        self.assertEqual(status, 1)
        self.assertEqual(result["guestQueueClock"]["eligibleTwoQueueIntervals"], 0)
        self.assertEqual(result["maxTwoQueueTicksCheck"]["reason"], "no-eligible-triples")

    def test_clock_context_and_field_breaks_do_not_create_intervals(self):
        for field in ("context", "fieldAvailable"):
            rows = self.clock_rows([10, 12, 14, 16, 18], [0, 200, 400, 600, 800])
            rows[2]["samples"][0][field] = {"mapId": 99} if field == "context" else False
            self.assertEqual(summarize(rows)["guestQueueClock"]["observedIntervals"], 2)

    def test_invalid_and_backwards_raw_clocks_fail_closed(self):
        for key, value in (("version", True), ("running", False), ("scope", "cpu"),
                           ("arm9Timestamp", -1), ("arm7Timestamp", 1 << 64),
                           ("frameSequence", None)):
            rows = self.clock_rows([10, 12], [100, 300])
            rows[1]["samples"][0]["guestQueueClock"][key] = value
            with self.assertRaisesRegex(ValueError, "invalid guest queue"):
                summarize(rows)
        for key in ("arm9Timestamp", "arm7Timestamp", "frameSequence"):
            rows = self.clock_rows([10, 12], [100, 300])
            rows[1]["samples"][0]["guestQueueClock"][key] = 0
            with self.assertRaisesRegex(ValueError, "backwards"):
                summarize(rows)

    def test_top_intervals_bounded_and_even_median(self):
        ticks = [0]
        for delta in range(1, 21): ticks.append(ticks[-1] + delta)
        clock = summarize(self.clock_rows(list(range(21)), ticks))["guestQueueClock"]
        self.assertEqual(len(clock["topIntervals"]), 8)
        self.assertEqual(clock["medianArm9Ticks"], 10.5)
        self.assertEqual(clock["topIntervals"][0]["arm9Ticks"], 20)
        self.assertEqual(len(clock["topTwoQueueIntervals"]), 8)
        self.assertEqual(clock["maximumTwoQueueArm9Ticks"], 39)

    def test_phase_recovery_is_not_individual_dropped_frame_claim(self):
        result = summarize(self.rows([10, 13, 14, 16]))
        self.assertEqual(result["nativeFrameBinHistogram"], {1: 1, 2: 1, 3: 1})
        self.assertEqual(result["sumPairExcessBinsAgainstTwoPerQueue"], 0)
        self.assertEqual(result["longGaps"], [])
        self.assertFalse(result["acceptedProof"])

    def test_checked_route_rejects_clear_delay_not_phase_recovery(self):
        self.assertIsNone(guest_queue_delay(snapshot(1, 10), snapshot(2, 13)))
        self.assertIsNone(guest_queue_delay(snapshot(2, 13), snapshot(3, 14)))
        delayed = guest_queue_delay(snapshot(1, 10), snapshot(2, 14))
        self.assertEqual(delayed["nativeFrameBins"], 4)
        self.assertEqual(delayed["toFrame"], 2)
        for field, value in (("frame", 4), ("context", {"mapId": 99}), ("fieldAvailable", False)):
            other = snapshot(2, 14)
            other[field] = value
            self.assertIsNone(guest_queue_delay(snapshot(1, 10), other))

    def test_four_bins_keep_exact_evidence_and_phase_bound(self):
        rows = self.rows([10, 12, 16])
        result = summarize(rows)
        gap = result["longGaps"][0]
        self.assertEqual(gap["frames"], [2, 3])
        self.assertEqual(gap["conditionalElapsedFrameLowerBoundExclusive"], 3)
        rows[2]["cycleIntervals"] = [{"cpuNs": 999999999}]
        self.assertEqual(result, summarize(rows))

    def test_checked_route_missing_control_is_not_a_clean_sample(self):
        for key in ("fieldPointer", "taskPointer"):
            other = snapshot(2, 14)
            del other["fieldControl"][key]
            with self.assertRaisesRegex(ValueError, "control identity"):
                guest_queue_delay(snapshot(1, 10), other)

    def test_missing_context_or_sample_never_creates_lag_credit(self):
        for kind in ("frame", "context", "fieldAvailable", "taskPointer"):
            rows = self.rows([10, 12, 40])
            value = rows[2]["samples"][0]
            if kind == "frame": value[kind] = 9
            elif kind == "context": value[kind] = {"mapId": 99}
            elif kind == "taskPointer": value["fieldControl"][kind] = 5
            else: value[kind] = False
            self.assertEqual(summarize(rows)["longGaps"], [])

    def test_setup_boundary_and_clock_fail_closed(self):
        rows = self.rows([10, 12, 40])
        rows.insert(2, {"phase": "setup"})
        self.assertEqual(summarize(rows)["longGaps"], [])
        with self.assertRaisesRegex(ValueError, "backwards"):
            summarize(self.rows([10, 9]))
        with self.assertRaisesRegex(ValueError, "no continuous"):
            summarize([])

    def test_owned_artifact_integrity_and_read_only_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = root / "observations.jsonl"
            data = "\n".join(json.dumps(row) for row in self.rows([10, 12, 16])) + "\n"
            evidence.write_text(data)
            manifest = root / "manifest.json"
            record = {"state": "completed", "runId": "test-owned", "observationsArtifact": {
                "path": str(evidence), "size": len(data.encode()),
                "sha256": hashlib.sha256(data.encode()).hexdigest()}}
            manifest.write_text(json.dumps(record))
            before = manifest.read_bytes(), evidence.read_bytes()
            self.assertEqual(inspect_manifest(manifest), inspect_manifest(manifest))
            self.assertEqual(before, (manifest.read_bytes(), evidence.read_bytes()))
            record["state"] = "running"
            manifest.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, "terminal"):
                inspect_manifest(manifest)
            record["state"] = "completed"
            manifest.write_text(json.dumps(record))
            evidence.write_text(data.replace('"nativeCycle": 16', '"nativeCycle": 18'))
            with self.assertRaisesRegex(ValueError, "identity differs"):
                inspect_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
