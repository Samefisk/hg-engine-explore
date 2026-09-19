"""Physical cycle / completed queue controls, including test5597fae shape."""
from copy import deepcopy
import unittest

from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_center_measurement import CenterEntryExitMeasurement
from tools.overworld.devtools_cadence_measurement import UnmountedCadenceMeasurement
from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.devtools_test_inputs import measurement_inputs
from tools.overworld.test_devtools_center_measurement import recipe, records, ROOT
from tools.overworld.test_devtools_cadence_measurement import Route


def chunk(initial):
    initial = deepcopy(initial)
    initial.update(frame=959, nativeCycle=2362)
    initial["nativeObservation"]["playerStepFrame"] = 959
    initial["partyObservation"]["frame"] = 959
    samples = []
    for frame in (960, 961):
        sample = deepcopy(initial)
        sample.update(frame=frame, nativeCycle=2364)
        sample["nativeObservation"]["playerStepFrame"] = frame
        sample["partyObservation"]["frame"] = frame
        samples.append(sample)
    return initial, {"phase": "setup", "action": "enter-arrival", "requestedGameFrames": 1,
        "completedGameFrames": 2, "observedFieldFrames": 2, "nativeCycles": 2,
        "samples": samples, "events": [], "cycleIntervals": [
            {"completedGameFrame": 959, "cpuNs": 123, "wallNs": 200},
            {"completedGameFrame": 961, "cpuNs": 456, "wallNs": 700}]}


class RawChunkTests(unittest.TestCase):
    def test_independent_clock_resolution_does_not_change_process_cost(self):
        initial, record = chunk(records()[0]["initialSnapshot"])
        interval = record['cycleIntervals'][0]
        interval.update(cpuNs=11853000, threadCpuNs=11853125, wallNs=11854625)
        with self.assertRaisesRegex(ValueError, 'cycle thread CPU'):
            validate_raw_chunk(record, initial)
        interval['cpuClockResolutionNs'] = dict(process=1000, thread=42)
        rows = validate_raw_chunk(record, initial)
        self.assertEqual(sum(i['cpuNs'] for _, _, values in rows for i in values), 11853456)
        interval['threadCpuNs'] = interval['cpuNs'] + 2084
        self.assertEqual(len(validate_raw_chunk(record, initial)), 2)
        interval['threadCpuNs'] = interval['cpuNs'] + 2085
        with self.assertRaisesRegex(ValueError, 'cycle thread CPU'):
            validate_raw_chunk(record, initial)
        for resolution in ({}, dict(process=True, thread=42), dict(process=0, thread=42),
                           dict(process=-1, thread=42), dict(process=1000001, thread=42)):
            interval['cpuClockResolutionNs'] = resolution
            with self.assertRaisesRegex(ValueError, 'clock resolution'):
                validate_raw_chunk(record, initial)

    def test_thread_cost_is_optional_bounded_and_never_replaces_process_cost(self):
        initial, record = chunk(records()[0]["initialSnapshot"])
        for value in (0, 50, 123):
            record["cycleIntervals"][0]["threadCpuNs"] = value
            rows = validate_raw_chunk(record, initial)
            self.assertEqual(sum(i["cpuNs"] for _, _, values in rows for i in values), 579)
        for value in (-1, 124, True, "50", None):
            record["cycleIntervals"][0]["threadCpuNs"] = value
            with self.assertRaisesRegex(ValueError, "cycle thread CPU"):
                validate_raw_chunk(record, initial)
        del record["cycleIntervals"][0]["threadCpuNs"]
        self.assertEqual(len(validate_raw_chunk(record, initial)), 2)

    def test_callback_attribution_is_optional_checked_and_never_subtracted(self):
        from tools.overworld.devtools_callback_costs import CallbackCosts
        initial, record = chunk(records()[0]["initialSnapshot"])
        clock = iter((0, 50))
        costs = CallbackCosts(lambda: next(clock))
        costs.call("main-queue-sampler", lambda: None)
        record["cycleIntervals"][0]["callbackCosts"] = costs.result(123)
        rows = validate_raw_chunk(record, initial)
        self.assertEqual(sum(i["cpuNs"] for _, _, values in rows for i in values), 579)
        record["cycleIntervals"][0]["callbackCosts"]["measuredCpuNs"] = 49
        with self.assertRaisesRegex(ValueError, "disagree"):
            validate_raw_chunk(record, initial)

    def test_one_cycle_has_two_frames_and_only_one_timing_charge(self):
        initial, record = chunk(records()[0]["initialSnapshot"])
        record["cycleIntervals"].pop(0)
        record["nativeCycles"] = 1
        for sample in record["samples"]:
            sample["nativeCycle"] = 2363
        rows = validate_raw_chunk(record, initial)
        self.assertEqual([len(intervals) for _, _, intervals in rows], [0, 1])

    def test_frame_and_native_limits_stay_strict(self):
        for field, value in (("completedGameFrames", 601), ("nativeCycles", 0),
                             ("observedFieldFrames", 1)):
            initial, record = chunk(records()[0]["initialSnapshot"])
            record[field] = value
            with self.assertRaises(ValueError): validate_raw_chunk(record, initial)
        for idle_count in (119, 120):
            initial, record = chunk(records()[0]["initialSnapshot"])
            record["cycleIntervals"] = [deepcopy(record["cycleIntervals"][0]) for _ in range(idle_count)] + [record["cycleIntervals"][1]]
            record["nativeCycles"] = idle_count + 1
            for sample in record["samples"]:
                sample["nativeCycle"] = 2362 + idle_count + 1
            if idle_count == 120:
                with self.assertRaisesRegex(ValueError, "no completed queue"):
                    validate_raw_chunk(record, initial)
            else:
                self.assertEqual(sum(len(i) for _, _, i in validate_raw_chunk(record, initial)), 120)

    def test_two_callbacks_share_one_native_cycle_without_fake_timing(self):
        initial, record = chunk(records()[0]["initialSnapshot"])
        rows = validate_raw_chunk(record, initial)
        self.assertEqual([s["nativeCycle"] for s, _, _ in rows], [2364, 2364])
        self.assertEqual([[i["cpuNs"] for i in intervals] for _, _, intervals in rows], [[123], [456]])
        self.assertEqual(sum(len(i) for _, _, i in rows), 2)

    def test_missing_duplicate_wrong_native_or_endpoint_fails_before_callbacks(self):
        for fault in ("missing", "duplicate", "native", "reverse-end", "trailing", "bool", "event",
                      "zero-cpu", "wrong-cpu-type", "zero-wall"):
            with self.subTest(fault=fault):
                initial, record = chunk(records()[0]["initialSnapshot"])
                if fault == "missing": record["samples"].pop(0)
                elif fault == "duplicate": record["samples"][1]["frame"] = 960
                elif fault == "native": record["samples"][0]["nativeCycle"] = 2363
                elif fault == "reverse-end": record["cycleIntervals"][0]["completedGameFrame"] = 958
                elif fault == "trailing": record["cycleIntervals"].append(deepcopy(record["cycleIntervals"][-1])); record["nativeCycles"] = 3
                elif fault == "bool": record["samples"][0]["nativeCycle"] = True
                elif fault == "zero-cpu": record["cycleIntervals"][0]["cpuNs"] = 0
                elif fault == "wrong-cpu-type": record["cycleIntervals"][0]["cpuNs"] = "123"
                elif fault == "zero-wall": record["cycleIntervals"][0]["wallNs"] = 0
                else: record["events"] = [{"frame": 962}]
                with self.assertRaises(ValueError): validate_raw_chunk(record, initial)

    def test_real_center_and_cadence_meters_keep_callbacks_in_frame_order(self):
        for kind in ("center", "cadence"):
            with self.subTest(kind=kind):
                if kind == "center":
                    test = recipe()
                    meter = CenterEntryExitMeasurement(test, max_frames=6000,
                        setup_transitions=test["measurements"][0]["setupTransitions"])
                    initial, record = chunk(records()[0]["initialSnapshot"])
                else:
                    route = Route(fainted=True)
                    meter = UnmountedCadenceMeasurement(route.test, max_frames=32000)
                    initial, record = chunk(route.snapshot())
                    record["action"] = "exit"
                meter.observe_record({"initialSnapshot": initial})
                seen = []
                result = meter.observe_record(record, frame_callback=lambda s, e, m:
                    seen.append((s["frame"], m.latest["frame"], m.result()["nativeCycles"])))
                self.assertEqual(result["failures"], [])
                self.assertEqual(seen, [(960, 960, 1), (961, 961, 2)])
                total = result["cpuNs"] if kind == "center" else sum(meter.cpu)
                self.assertEqual(total, 579)

    def test_earlier_callback_failure_stops_before_later_frame(self):
        test = validate_test(recipe())
        evaluator = TestEvaluator(test)
        evaluator.install_measurements(measurement_inputs(test, ROOT))
        initial, record = chunk(records()[0]["initialSnapshot"])
        evaluator.observe_record({"initialSnapshot": initial})
        seen = []
        def fail_first(sample, gate):
            seen.append((sample["frame"], gate.latest["frame"]))
            raise RuntimeError("earlier deadline")
        with self.assertRaisesRegex(RuntimeError, "earlier deadline"):
            evaluator.observe_record(record, frame_callback=fail_first)
        self.assertEqual(seen, [(960, 960)])
        self.assertEqual(evaluator.latest["frame"], 960)
        self.assertEqual(evaluator.measurements["center-entry-exit-v1"].latest["frame"], 960)

    def test_full_chunk_still_obeys_action_budget(self):
        test = recipe()
        next(a for a in test["setup"] if a["id"] == "enter-arrival")["budget"].update(maxFrames=1, noProgressFrames=1)
        evaluator = TestEvaluator(validate_test(test))
        evaluator.install_measurements(measurement_inputs(test, ROOT))
        initial, record = chunk(records()[0]["initialSnapshot"])
        evaluator.observe_record({"initialSnapshot": initial})
        result = evaluator.observe_record(record)
        self.assertEqual(result["state"], "failed")
        self.assertIn("raw action exceeds its frame budget", str(result["failures"]))
        self.assertEqual(evaluator.latest["frame"], 959)

    def test_replay_requested_count_matches_live_neutral_setup_policy(self):
        for case in ("neutral-setup", "legacy-exact", "input-extra", "observe-extra",
                     "short", "zero", "bool", "too-large"):
            with self.subTest(case=case):
                test = validate_test(recipe())
                evaluator = TestEvaluator(test)
                evaluator.install_measurements(measurement_inputs(test, ROOT))
                initial, record = chunk(records()[0]["initialSnapshot"])
                evaluator.observe_record({"initialSnapshot": initial})
                if case == "legacy-exact": record.pop("requestedGameFrames")
                elif case == "input-extra": record["action"] = "enter-door"
                elif case == "observe-extra":
                    record.update(phase="observe", action="returned-control-settle")
                elif case == "short": record["requestedGameFrames"] = 3
                elif case == "zero": record["requestedGameFrames"] = 0
                elif case == "bool": record["requestedGameFrames"] = True
                elif case == "too-large": record["requestedGameFrames"] = 601
                result = evaluator.observe_record(record)
                if case in ("neutral-setup", "legacy-exact"):
                    self.assertEqual(result["failures"], [])
                    self.assertEqual(evaluator.latest["frame"], 961)
                else:
                    self.assertEqual(result["state"], "failed")
                    self.assertEqual(evaluator.latest["frame"], 959)
                    self.assertEqual(result["failures"][0]["code"], "raw-observation-invalid")


if __name__ == "__main__":
    unittest.main()
