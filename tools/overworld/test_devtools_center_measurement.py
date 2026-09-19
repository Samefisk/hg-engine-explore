"""Real shared evaluator controls for the small Center lifecycle regression."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.devtools_test_inputs import measurement_inputs
from tools.overworld.test_devtools_cadence_measurement import Route, player

ROOT = Path(__file__).resolve().parents[2]
KIND = "center-entry-exit-v1"


def recipe():
    return json.loads((ROOT / "tests/overworld/test-recipes/world.center-entry-exit.json").read_text())


def records():
    base = Route().snapshot()
    base["actors"] = []  # No actor, follower or party eligibility is claimed.
    output = []
    def sample(map_id, x, z, *, task=0, absent=False, steps=0):
        value = deepcopy(base)
        frame = len(output)
        value.update(frame=frame, nativeCycle=frame * 2)
        value["context"]["mapId"] = map_id
        value["player"] = player(x, z)
        value["fieldControl"]["taskPointer"] = task
        value["nativeObservation"].update(playerStepCount=steps, playerStepFrame=frame)
        if absent:
            for key in ("actors", "player", "party", "partyObservation", "context", "actorFrame", "selector", "fieldControl"):
                value.pop(key)
            value.update(fieldAvailable=False, observationErrors=[], fieldAvailability={
                "fieldPointer": 0, "actorStateMagic": 0x5353574F, "reasons": ["null-field-pointer"]})
        return value
    output.append({"phase": "setup", "initialSnapshot": sample(67, 564, 391, task=0x02040000)})
    def row(action, map_id, x, z, phase="setup", **kwargs):
        value = sample(map_id, x, z, **kwargs)
        output.append({"phase": phase, "action": action, "samples": [value], "events": [],
            "cycleIntervals": [{"cpuNs": 1000, "wallNs": 1000, "completedGameFrame": value["frame"] - 1},
                               {"cpuNs": 1000, "wallNs": 1000, "completedGameFrame": value["frame"]}],
            "nativeCycles": 2, "completedGameFrames": 1, "observedFieldFrames": int(not kwargs.get("absent"))})
    row("enter-arrival", 67, 564, 392, absent=True)
    row("enter-arrival", 69, 8, 19)
    row("exit-door", 69, 8, 19, task=0x02040004)
    row("exit-arrival", 69, 8, 19, absent=True)
    row("exit-arrival", 67, 564, 392)
    row("returned-control-admit", 67, 564, 393, phase="observe", steps=1)
    row("returned-control-settle", 67, 564, 393, phase="observe", steps=1)
    return output


def evaluate(stream):
    test = validate_test(recipe())
    evaluator = TestEvaluator(test)
    evaluator.install_measurements(measurement_inputs(test, ROOT))
    for row in stream:
        evaluator.observe_record(row)
    return evaluator


class CenterTests(unittest.TestCase):
    def test_authenticated_unowned_field_is_absence_not_stale_player(self):
        from tools.overworld.devtools_records import validate_field_absence
        for reason, control, manager, execution, procedure in (
                ("field-control-absent", 0, 0, None, None),
                ("field-manager-absent", 0x02050000, 0, None, None),
                ("field-initializing", 0x02050000, 0x02060000, 0, 0),
                ("field-initializing", 0x02050000, 0x02060000, 1, 3),
                ("field-exiting", 0x02050000, 0x02060000, 2, 0),
                ("field-exiting", 0x02050000, 0x02060000, 3, 2)):
            with self.subTest(reason=reason, execution=execution):
                stream = records()
                sample = stream[4]["samples"][0]
                sample["fieldAvailability"] = {
                    "fieldPointer": 0x02040000, "actorStateMagic": 0x5353574F,
                    "reasons": [reason], "lifecycle": {
                        "authenticated": True, "fieldReady": 0,
                        "controlPointer": control, "managerPointer": manager,
                        "managerExecState": execution, "managerProcState": procedure}}
                validate_field_absence(sample)
                result = evaluate(stream).finish()
                self.assertTrue(result["passed"], result["failures"])
                self.assertEqual(result["measurements"][KIND]["setupTransitions"][1]["absentFrames"], 1)
                for key, value in (("authenticated", False), ("fieldReady", 1),
                                   ("fieldReady", False),
                                   ("controlPointer", 7), ("managerPointer", True),
                                   ("controlPointer", 0x023FFFF4), ("managerPointer", 0x023FFFE0),
                                   ("managerExecState", 4), ("managerExecState", False),
                                   ("managerProcState", -1), ("managerProcState", False),
                                   ("managerProcState", 4)):
                    bad = deepcopy(sample)
                    bad["fieldAvailability"]["lifecycle"][key] = value
                    with self.subTest(key=key), self.assertRaises(ValueError):
                        validate_field_absence(bad)
                for fault in ("unarmed", "wrong-arrival"):
                    bad = deepcopy(stream)
                    if fault == "unarmed": bad[3]["samples"][0]["fieldControl"]["taskPointer"] = 0
                    else: bad[5]["samples"][0]["player"]["x"] = 565
                    with self.subTest(fault=fault):
                        self.assertFalse(evaluate(bad).finish()["passed"])

                for fault in ("stale-player", "wrong-reason", "missing-lifecycle", "wrong-magic", "null-root"):
                    bad = deepcopy(sample)
                    if fault == "stale-player": bad["player"] = {"x": 157440, "facing": 369098754}
                    elif fault == "wrong-reason": bad["fieldAvailability"]["reasons"] = ["null-field-pointer"]
                    elif fault == "missing-lifecycle": bad["fieldAvailability"].pop("lifecycle")
                    elif fault == "wrong-magic": bad["fieldAvailability"]["actorStateMagic"] = 0
                    else: bad["fieldAvailability"]["fieldPointer"] = 0
                    with self.subTest(fault=fault), self.assertRaises(ValueError):
                        validate_field_absence(bad)

    def test_freed_player_bytes_cannot_be_treated_as_live_transition_pose(self):
        stream = records()
        stale = deepcopy(stream[3]["samples"][0])
        previous_absence = stream[4]["samples"][0]
        stale.update(frame=previous_absence["frame"], nativeCycle=previous_absence["nativeCycle"])
        stale["nativeObservation"]["playerStepFrame"] = stale["frame"]
        stale["context"]["mapId"] = 67
        stale["player"].update(x=157440, y=3473408, facing=369098754)
        stream[4]["samples"] = [stale]
        stream[4]["observedFieldFrames"] = 1
        result = evaluate(stream).finish()
        self.assertFalse(result["passed"])
        self.assertIn("player.x", result["measurements"][KIND]["failures"][0]["detail"])

    def test_retained_complete_phase_allows_control_but_active_phases_do_not(self):
        for phase in (0, 1, 2, 3, 4, False):
            with self.subTest(phase=phase):
                stream = records()
                for row in stream[6:]:
                    row["samples"][0]["fieldControl"]["actorTransitionPhase"] = phase
                self.assertEqual(evaluate(stream).finish()["passed"], type(phase) is int and phase in (0, 4))

    def test_zero_player_transition_row_requires_armed_task_and_exact_maps(self):
        stream = records()
        previous, old = stream[0]["initialSnapshot"], stream[1]["samples"][0]
        sample = deepcopy(previous)
        sample.update(frame=old["frame"], nativeCycle=old["nativeCycle"])
        sample["nativeObservation"]["playerStepFrame"] = sample["frame"]
        sample["player"] = {key: 0 for key in sample["player"]}
        stream[1]["samples"] = [sample]
        stream[1]["observedFieldFrames"] = 1
        result = evaluate(stream).finish()
        self.assertTrue(result["passed"], result["failures"])
        transition = result["measurements"][KIND]["setupTransitions"][0]
        self.assertEqual(transition["unreadyPlayerFrames"], 1)
        self.assertEqual(transition["absentFrames"], 0)
        for fault in ("no-task", "wrong-map", "populated-wrong-point", "unarmed"):
            bad = deepcopy(stream)
            row = bad[1]["samples"][0]
            if fault == "no-task": row["fieldControl"]["taskPointer"] = 0
            elif fault == "wrong-map": row["context"]["mapId"] = 68
            elif fault == "populated-wrong-point": row["player"]["x"] = 1
            else: bad[0]["initialSnapshot"]["fieldControl"]["taskPointer"] = 0
            self.assertFalse(evaluate(bad).finish()["passed"])

    def test_live_doorways_can_finish_without_any_null_field_queue(self):
        stream = records()
        for index in (1, 4):
            prior = stream[index - 1].get("initialSnapshot", stream[index - 1].get("samples", [None])[0])
            old = stream[index]["samples"][0]
            sample = deepcopy(prior)
            sample.update(frame=old["frame"], nativeCycle=old["nativeCycle"])
            sample["nativeObservation"]["playerStepFrame"] = sample["frame"]
            stream[index]["samples"] = [sample]
            stream[index]["observedFieldFrames"] = 1
        result = evaluate(stream).finish()
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["measurements"][KIND]["absentSetupFrames"], 0)
        self.assertEqual(len(result["measurements"][KIND]["setupTransitions"]), 2)
        for index, field, value in ((0, "task", 0), (2, "x", 9)):
            broken = deepcopy(stream)
            sample = broken[index].get("initialSnapshot", broken[index].get("samples", [None])[0])
            if field == "task":
                sample["fieldControl"]["taskPointer"] = value
                broken[1]["samples"][0]["fieldControl"]["taskPointer"] = value
            else:
                sample["player"][field] = value
            self.assertFalse(evaluate(broken).finish()["passed"])

    def test_recipe_keeps_saved_route_no_actor_or_prepared_shortcuts(self):
        value = validate_test(recipe())
        self.assertEqual(value["subjects"], [])
        self.assertEqual(value["requirements"], [])
        old = json.loads((ROOT / "tests/overworld/test-recipes/chain.ledyba-witness.json").read_text())
        for index in range(2, 62):
            action = deepcopy(old["setup"][index]); action.pop("skipIf", None)
            self.assertEqual(recipe()["setup"][index], action)

    def test_exact_entry_exit_and_one_returned_control_step_pass(self):
        result = evaluate(records()).finish()
        self.assertTrue(result["passed"], result["failures"])
        self.assertFalse(result["acceptedProof"])
        self.assertEqual(result["measurements"][KIND]["absentSetupFrames"], 2)
        self.assertEqual(len(result["measurements"][KIND]["setupTransitions"]), 2)

    def test_old_exit_task_stays_active_without_absence_cannot_pass(self):
        stream = records()[:4]
        stuck = deepcopy(stream[-1]); stuck["action"] = "exit-arrival"
        for frame in range(4, 245):
            row = deepcopy(stuck)
            row["samples"][0].update(frame=frame, nativeCycle=frame * 2)
            row["samples"][0]["nativeObservation"]["playerStepFrame"] = frame
            row["cycleIntervals"][0]["completedGameFrame"] = frame - 1
            row["cycleIntervals"][1]["completedGameFrame"] = frame
            stream.append(row)
        result = evaluate(stream).finish()
        self.assertFalse(result["passed"])
        self.assertFalse(result["measurements"][KIND]["ready"])
        self.assertIn("raw action exceeds its frame budget", str(result["failures"]))

    def test_exact_absence_meaning_and_control_deletion_controls(self):
        for fault in ("no-task", "wrong-departure", "wrong-arrival", "outside-setup",
                      "wrong-action", "stale-clock", "prepared", "no-exit", "no-control", "no-step-receipt"):
            with self.subTest(fault=fault):
                stream = records()
                if fault == "no-task": stream[0]["initialSnapshot"]["fieldControl"]["taskPointer"] = 0
                elif fault == "wrong-departure": stream[0]["initialSnapshot"]["player"]["x"] = 565
                elif fault == "wrong-arrival": stream[2]["samples"][0]["player"]["x"] = 9
                elif fault == "outside-setup": stream[1]["phase"] = "observe"
                elif fault == "wrong-action": stream[1]["action"] = "exit-arrival"
                elif fault == "stale-clock": stream[2]["samples"][0]["nativeCycle"] = 0
                elif fault == "prepared": stream[2]["samples"][0]["prepared"] = True
                elif fault == "no-exit": stream = stream[:4]
                elif fault == "no-control": stream = stream[:6]
                elif fault == "no-step-receipt":
                    for row in stream[6:]: row["samples"][0]["nativeObservation"]["playerStepCount"] = 0
                self.assertFalse(evaluate(stream).finish()["passed"])

    def test_stock_reveal_then_auto_step_down_is_retained_not_settled(self):
        stream = records()
        revealed = deepcopy(stream[5])
        revealed["samples"][0]["player"] = player(564, 391)
        revealed["samples"][0]["fieldControl"]["taskPointer"] = 0x02040004
        stream.insert(5, revealed)
        for frame, row in enumerate(stream[1:], 1):
            row["samples"][0].update(frame=frame, nativeCycle=frame * 2)
            row["samples"][0]["nativeObservation"]["playerStepFrame"] = frame
            row["cycleIntervals"][0]["completedGameFrame"] = frame - 1
            row["cycleIntervals"][1]["completedGameFrame"] = frame
        self.assertTrue(evaluate(stream).finish()["passed"])
        stream[5]["samples"][0]["player"] = player(565, 391)
        self.assertFalse(evaluate(stream).finish()["passed"])


if __name__ == "__main__":
    unittest.main()
