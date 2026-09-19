"""Real cadence replay controls; no emulator or full-route soak."""
from copy import deepcopy
import unittest

from tools.overworld.devtools_cadence_measurement import UnmountedCadenceMeasurement
from tools.overworld.route_cadence_negatives import CadenceNegative, FAULTS, KIND, validate_negative_result
from tools.overworld.test_devtools_cadence_measurement import Route


class CadenceNegativeTests(unittest.TestCase):
    def test_cpu_fault_with_callback_costs_still_reaches_cpu_checker(self):
        from tools.overworld.devtools_callback_costs import CallbackCosts
        route = self.fixture()
        for row in route.records:
            for interval in row.get("cycleIntervals", []):
                interval["callbackCosts"] = CallbackCosts().result(interval["cpuNs"])
        control = CadenceNegative("cadence-cpu-hitch")
        meter = UnmountedCadenceMeasurement(route.test, max_frames=1000)
        for row in route.records:
            meter.observe_record(control.mutate(row, [meter.subject] if meter.subject else []), full_report=False)
            if meter.failures: break
        self.assertTrue(validate_negative_result("cadence-cpu-hitch",
            {"passed": False, "measurements": {KIND: meter.result()}}))

    def fixture(self):
        route = Route(); route.setup_bind()
        for tile in range(1, 6):
            route.move(tile)
        return route

    def test_all_faults_reach_their_own_checker_early_without_changing_input(self):
        route = self.fixture()
        for fault in FAULTS:
            with self.subTest(fault=fault):
                original = deepcopy(route.records)
                control = CadenceNegative(fault)
                meter = UnmountedCadenceMeasurement(route.test, max_frames=1000)
                for count, row in enumerate(route.records, 1):
                    changed = control.mutate(row, {"cyndaquil": meter.subject} if meter.subject else {})
                    meter.observe_record(changed, full_report=False)
                    if meter.failures:
                        break
                self.assertTrue(control.applied)
                self.assertLess(count, len(route.records))
                self.assertEqual(route.records, original)
                result = {"passed": False, "measurements": {KIND: meter.result()}}
                self.assertTrue(validate_negative_result(fault, result))
                for bad in ({**result, "passed": True}, {**result, "passed": 0},
                            {"passed": False, "measurements": None},
                            {"passed": False, "measurements": {KIND: {"failures": [{"code": "other"}]}}}):
                    with self.assertRaises(ValueError):
                        validate_negative_result(fault, bad)

    def test_player_pin_is_exactly_four_frames_and_only_xz(self):
        route = self.fixture(); control = CadenceNegative("cadence-player-start-stall")
        rows = [row for row in route.records if row.get("samples") and row["phase"] == "observe"]
        subject = route.actor
        origin = rows[0]["events"][0]["data"]["objectBefore"]
        for index, row in enumerate(rows[:6]):
            changed = control.mutate(row, [subject])
            if index < 4:
                expected = deepcopy(row)
                expected["samples"][0]["player"].update(pos_x=origin["pos_x"], pos_z=origin["pos_z"])
                self.assertEqual(changed, expected)
                self.assertIsNot(changed, row)
            else:
                self.assertIs(changed, row)
        self.assertEqual(control.pin_count, 4)

    def test_cpu_changes_only_one_actual_interval(self):
        route = self.fixture(); control = CadenceNegative("cadence-cpu-hitch")
        row = next(row for row in route.records if row.get("samples") and row["phase"] == "observe")
        changed = control.mutate(row, [route.actor]); expected = deepcopy(row)
        expected["cycleIntervals"][0]["cpuNs"] = 10**12
        self.assertEqual(changed, expected)
        self.assertIs(control.mutate(row, [route.actor]), row)

    def test_multisample_row_pins_only_first_four_completed_samples(self):
        route = self.fixture()
        rows = [row for row in route.records if row.get("samples") and row["phase"] == "observe"][:6]
        row = {**rows[0], "samples": [r["samples"][0] for r in rows],
               "events": [e for r in rows for e in r["events"]]}
        original = deepcopy(row)
        control = CadenceNegative("cadence-player-start-stall")
        changed = control.mutate(row, [route.actor])
        expected = deepcopy(row)
        before = row["events"][0]["data"]["objectBefore"]
        for sample in expected["samples"][:4]:
            sample["player"].update(pos_x=before["pos_x"], pos_z=before["pos_z"])
        self.assertEqual(changed, expected)
        self.assertEqual(row, original)
        self.assertEqual(control.pin_count, 4)

    def test_unbound_unknown_and_broken_pin_window(self):
        route = self.fixture()
        rows = [row for row in route.records if row.get("samples") and row["phase"] == "observe"]
        for fault in FAULTS:
            control = CadenceNegative(fault)
            self.assertIs(control.mutate(rows[0], {}), rows[0])
            self.assertFalse(control.applied)
        with self.assertRaises(ValueError):
            CadenceNegative("other")
        for failure in ("gap", "subject", "context"):
            control = CadenceNegative("cadence-player-start-stall")
            control.mutate(rows[0], [route.actor])
            row = deepcopy(rows[1]); subject = deepcopy(route.actor)
            if failure == "gap": row["samples"][0]["frame"] += 1
            if failure == "subject": subject["handle"]["generation"] += 1
            if failure == "context": row["samples"][0]["context"]["fieldEpoch"] += 1
            with self.assertRaises(ValueError):
                control.mutate(row, [subject])
