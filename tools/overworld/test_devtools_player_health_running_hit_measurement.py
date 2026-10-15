"""Copied-data controls for the native running-hit terminal boundary."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_player_health_running_hit_measurement import (
    KIND, PlayerHealthRunningHitMeasurement, AMBUSH_BIT,
)
from tools.overworld.devtools_player_health_running_hit_proof import (
    FAULTS, RunningHitNegative, measurements, validate_negative_result,
)
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.test_devtools_player_health_hop_contact_measurement import (
    snapshot as old_snapshot, health, raw, SOURCE, FINGERPRINT,
)

ROOT = Path(__file__).resolve().parents[2]


def snapshot(frame, *, tile=(585, 407), command=0, selector=0, arc=0, moving=False):
    sample = old_snapshot(frame, moving=moving)
    sample["fieldControl"]["fieldPointer"] = 0x02050000
    sample["selector"] = {"rawHeld": 0}
    player = sample["player"]
    player.update(x=tile[0], y=tile[1], x_prev=tile[0], y_prev=tile[1],
                  pos_x=(tile[0] << 16) + 0x8000, pos_z=(tile[1] << 16) + 0x8000,
                  face_y=arc, unk88_y=0, flags=0x21, facing=0,
                  movement_cmd=command, movement_step=0 if command == 255 else 1,
                  movement_animation=selector,
                  movement_render_words=[selector << 16, 0x02108000, 0, 0, 0, 0, 0, 0])
    actor = sample["actors"][0]
    actor.update(species=70, matchedLayerMask=AMBUSH_BIT)
    actor["origin"], actor["target"] = {"x":585,"y":405}, {"x":585,"y":406}
    if moving:
        actor.update(motionElapsed=3, motionDuration=6)
        actor["engineObject"].update(pos_x=player["pos_x"], pos_z=player["pos_z"])
    return sample


def rows():
    initial, placed, bound = snapshot(10), snapshot(11), snapshot(12)
    initial["context"]["mapId"] = 34
    initial["actors"] = placed["actors"] = []
    subject = select_current_actor(bound, bound["actors"][0])
    before = health(bound,100,0,0)
    run = snapshot(13,tile=(585,406),command=88,selector=9)
    run["selector"]["rawHeld"] = 66
    run["player"].update(y_prev=407,pos_z=(407<<16)+0x4000,flags=0x11)
    runrow = raw("run-to-contact",run)
    runrow["events"] = [{"frame":13,"kind":"native-observation","data":{
        "observation":"player-step-admitted","mapId":33,"direction":0,
        "objectPointer":0x02070000,"target":[585,406],"objectAfter":{"movement_cmd":88}}}]
    hit = snapshot(14,tile=(585,406),command=62,selector=2,arc=15120,moving=True)
    hit["selector"]["rawHeld"] = 66
    hitrow = raw("run-to-contact",hit,profile_cache=True)
    profile = hitrow["profileCache"]["resolvedProfiles"][0]
    profile["appliedOverrides"] = AMBUSH_BIT
    data = bytearray.fromhex(profile["resultHex"]); data[79] = 6; profile["resultHex"] = data.hex()
    transit = snapshot(15,tile=(585,407),command=62,selector=2,arc=30240)
    transit["player"].update(y_prev=406,pos_z=(406<<16)+0xC000,flags=0x31)
    terminal = snapshot(16,command=255)
    return [dict(phase="setup",initialSnapshot=initial),
            dict(phase="setup",action="ambush-tile",command="teleport",snapshot=placed,receipt={}),
            dict(phase="setup",action="spawn-weepinbell",command="spawn",snapshot=bound,
                 receipt={"value":{"species":70,"slot":0,"personality":901}}),
            dict(phase="setup",action="bind-weepinbell",command="bind",snapshot=bound,receipt=subject),
            dict(phase="observe",action="before-contact",command="player-health.observe",snapshot=bound,
                 receipt={"playerHealth":before}), runrow, hitrow,
            dict(phase="observe",action="at-contact",command="player-health.observe",snapshot=hit,
                 receipt={"playerHealth":health(hit,80,20,1)}),
            raw("finish-knockback",transit), raw("finish-knockback",terminal),
            *[raw("neutral-after-knockback",snapshot(frame)) for frame in range(17,33)],
            dict(phase="observe",action="after-knockback",command="player-health.observe",snapshot=snapshot(32),
                 receipt={"playerHealth":health(snapshot(32),80,20,1)})]


def evaluate(stream, fault=None):
    meter = PlayerHealthRunningHitMeasurement(SOURCE)
    negative = RunningHitNegative(fault) if fault else None
    for row in stream:
        if negative: row = negative.mutate(row, {"weepinbell": meter.subject} if meter.subject else {})
        result = meter.observe_record(row)
        if result["failures"]: break
    finished = meter.finish()
    return {"passed":finished["passed"],"failures":finished["failures"],
            "observedFrames":meter.observed_frames,"measurements":{KIND:meter.result()}}


class PlayerHealthRunningHitTests(unittest.TestCase):
    def test_real_run_hit_and_same_frame_idle_keep16_neutral_frames(self):
        result = evaluate(rows())
        self.assertTrue(result["passed"],result)
        leaf = result["measurements"][KIND]
        self.assertEqual((leaf["runAdmissionFrame"],leaf["runningFrame"],leaf["crossingFrame"],leaf["terminalFrame"]),(13,13,14,16))
        self.assertEqual((leaf["neutralFrames"],leaf["hpAfter"]),(16,80))
        record = {"sessionId":"copied","sessionCleanup":{"sessionId":"copied","closed":True,"errors":[]}}
        self.assertEqual(len(measurements(result,record)),6)

    def test_each_copied_fault_rejects_its_named_guard(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                result = evaluate(rows(),fault)
                self.assertFalse(result["passed"],result)
                validate_negative_result(result,fault)

    def test_later_idle_cannot_hide_one_bad_native_terminal_frame(self):
        stream = rows()
        terminal = next(row for row in stream if row.get("action")=="finish-knockback"
                        and row["samples"][0]["player"]["movement_cmd"]==255)["samples"][0]
        # Retained native BEFORE789: centered cmd255/step0, A0=2 and R0=131072.
        # The next native790 is idle. Checking only that next frame hides the bug.
        terminal["player"].update(movement_animation=2,movement_render_words=[131072,0x02108000,0,0,0,0,0,0])
        result = evaluate(stream)
        self.assertFalse(result["passed"])
        self.assertIn("same completed frame",str(result["failures"]))

    def test_exact_recipe_factory_and_registry_contract(self):
        from tools.overworld.devtools_test_contract import validate_test, TestEvaluator
        from tools.overworld.proof_adapters import get_adapter
        from tools.overworld.devtools_player_health_running_hit_proof import contract
        recipe = json.loads((ROOT/"tests/overworld/test-recipes/player-hp.running-hit.json").read_text())
        evaluator = TestEvaluator(validate_test(recipe)); evaluator.install_measurements({KIND:SOURCE})
        self.assertIsInstance(evaluator.measurements[KIND],PlayerHealthRunningHitMeasurement)
        self.assertEqual(get_adapter(KIND).contract(),contract())
        registry = json.loads((ROOT/"tools/overworld/runtime_proof_registry.json").read_text())
        self.assertEqual(registry["sharedTests"]["player-hp.running-hit"]["measurementContract"],contract())


if __name__=="__main__": unittest.main()
