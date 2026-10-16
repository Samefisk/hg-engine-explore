"""Portable checks for partial mounted skids at the first blocked tile."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_mounted_stantler_skid_obstacle_proof import (
    CASES, CLAIMS, FIRST, MAX_RUN_FRAMES, SECOND, TWO_KEYS, contract,
    negative_controls, run, run_until,
)
from tools.overworld.devtools_test_contract import validate_test
from tools.overworld import control


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_RUN_FRAMES = 24


def _event(frame, sequence, name, a, b):
    return {"kind": "native", "frame": frame, "data": {
        "event": name, "reason": "OK", "actorHandle": 7,
        "sequence": sequence, "valueA": a, "valueB": b}}


def _walk_event(frame, sequence, operation, start_result=0, facing=1):
    request = bytearray(28)
    response = bytearray(28)
    request[9] = response[9] = operation
    if operation == 1:
        response[11] = 2
        response[16:21] = bytes((2, 3, facing, 8, 0x83))
    else:
        request[20] = response[20] = 0x83
        response[15] = start_result
    return {"kind": "native-observation", "frame": frame, "data": {
        "observation": "walk-policy", "operation": operation,
        "sequence": sequence, "publicSubject": {"handle": {"value": 7}},
        "requestHex": request.hex(), "responseHex": response.hex()}}


def _sample(frame, case, *, skid=0, idle=False):
    start, end = case["start"], case["runEnd"]
    facing = case.get("facing", 1)
    offset_x, offset_z = case.get("faceOffset", (0, -40960))
    right = frame <= FIXTURE_RUN_FRAMES
    walk = frame <= FIXTURE_RUN_FRAMES + 3
    run_commit = 6
    logical = start if frame == 1 else end - 1 if right else \
              end if walk or skid < 4 and not idle else 589
    render_x = ((end - 1 if walk else end) << 16) + 0x8000
    if skid:
        render_x += (skid * 65536) // 4
    elif idle and case["clearSkids"]:
        render_x = (589 << 16) + 0x8000
    motion = "WALK" if walk else "SKID" if skid else "NONE"
    commit = run_commit if walk else run_commit + 1 if skid else \
             run_commit + 1 + case["clearSkids"]
    actor = {
        "active": True, "role": "MOUNTED", "species": 234,
        "identityVerified": True, "presentationAttached": True,
        "inputOwnership": 1, "handle": {"value": 7},
        "subjectIdentity": 77, "behaviorFingerprint": 888,
        "engineIdentity": {"anchorPointer": 0x02230000, "pointer": 0x02231000},
        "logical": {"x": logical, "y": 406},
        "origin": {"x": end - (2 if right and frame < FIXTURE_RUN_FRAMES
                         else 1) if walk else end, "y": 406},
        "target": {"x": end - 1 if right and frame < FIXTURE_RUN_FRAMES
                   else end if walk else 589, "y": 406},
        "motionKind": motion, "motionPhase": "COMMIT_PENDING"
                       if walk and frame == FIXTURE_RUN_FRAMES + 3 else
                       "MOVING" if walk or skid else "IDLE",
        "motionElapsed": skid if skid else
                         1 + frame - FIXTURE_RUN_FRAMES if walk and not right
                         else 1 if walk else 0,
        "motionDuration": 4,
        "commitSequence": commit,
        "movementPolicy": {"pending": 2 if skid else 0,
                           "speed": 4 if skid else 0},
        "engineObject": {"pos_x": render_x, "pos_y": 65536,
                         "pos_z": (406 << 16) + 0x8000,
                         "face_x": render_x,
                         "face_z": (406 << 16) + 0x8000,
                         "facing": facing if not right else 3},
    }
    player = {"x": start if frame == 1 else end - 1 if right else
              589 if skid == 4 or idle else end,
              "y": 406, "facing": facing if not right else 3,
              "pos_x": render_x, "pos_y": 65536,
              "pos_z": (406 << 16) + 0x8000,
              "face_x": render_x + offset_x,
              "face_z": (406 << 16) + 0x8000 + offset_z}
    for obj, height in ((player, 32768), (actor["engineObject"], 0)):
        obj["face_y"] = height
        obj.update({prefix + axis: 0 for prefix in ("unk88_", "unk94_")
                    for axis in "xyz"})
    pose = dict(x=player["pos_x"], z=player["pos_z"], velocityX=0, velocityZ=0,
                bodyY=0, riderY=0, leanX=0, leanZ=0, phase=0, walking=1)
    pair = dict(playerPointer=0x02230000, mountPointer=0x02231000,
                player=deepcopy(player), mount=deepcopy(actor["engineObject"]),
                gait=dict(schemaVersion=1, address=0x01FFA500,
                          previous=deepcopy(pose), pose=deepcopy(pose),
                          stamp=frame, session=1, owner=0x02230000, initialized=1,
                          input=dict(x=pose["x"], z=pose["z"], stamp=frame,
                                     session=1, owner=0x02230000, mode=1, options=90)))
    held = 16 if right else case.get("turnMask", 128)
    return {"frame": frame, "actors": [actor], "player": player,
            "mountedPair": pair,
            "context": {"mapId": 33}, "fieldAvailable": True,
            "observationBoundary": "main-task-queue-completion",
            "selector": {"rawHeld": held, "heldKeys": held,
                         "simulatedKeys": 0}}


def _rows(case_id):
    case = CASES[case_id]
    right = [_sample(frame, case) for frame in range(1, FIXTURE_RUN_FRAMES + 1)]
    down = [_sample(frame, case,
                    skid=frame - FIXTURE_RUN_FRAMES - 3
                         if case["clearSkids"]
                         and FIXTURE_RUN_FRAMES + 4 <= frame <= FIXTURE_RUN_FRAMES + 7
                         else 0,
                    idle=frame > FIXTURE_RUN_FRAMES
                         + (7 if case["clearSkids"] else 3))
            for frame in range(FIXTURE_RUN_FRAMES + 1, FIXTURE_RUN_FRAMES + 19)]
    first = FIXTURE_RUN_FRAMES + 4
    finish = FIXTURE_RUN_FRAMES + 8
    events = [_event(first, 1, "LOGICAL_COMMIT", 7, 1),
              _event(first, 2, "MOTION_FINISHED", 7, 1),
              _event(first, 3, "CONTROL_RETURNED", 1, 7),
              _walk_event(first, 1, 1, facing=case.get("facing", 1))]
    if case["clearSkids"]:
        commit = 8
        events += [_walk_event(first, 2, 2, 1),
                   _event(first, 4, "MOTION_STARTED", 4, 4),
                   _event(finish, 5, "LOGICAL_COMMIT", commit, 4),
                   _event(finish, 6, "MOTION_FINISHED", commit, 4),
                   _event(finish, 7, "CONTROL_RETURNED", 1, commit),
                   _walk_event(finish, 3, 2, 2),
                   _event(finish, 8, "WORLD_EFFECT", 3, 1)]
    else:
        events += [_walk_event(first, 2, 2, 2),
                   _event(first, 4, "WORLD_EFFECT", 3, 1)]
    if case_id == TWO_KEYS:
        final = down[-1]
        actor = final["actors"][0]
        actor.update(motionKind="WALK", motionPhase="MOVING", motionElapsed=1,
                     motionDuration=7, origin={"x": 589, "y": 406},
                     target={"x": 588, "y": 406})
        actor["movementPolicy"].update(pending=2, direction=2, speed=6)
        events.append(_event(final["frame"], 9, "MOTION_STARTED", 1, 7))
        for operation in (1, 2):
            receipt = _walk_event(final["frame"], 9 + operation, operation, 1, 2)
            request, response = (bytearray.fromhex(receipt["data"][key])
                                 for key in ("requestHex", "responseHex"))
            if operation == 1:
                request[10] = 2
                response[16:21] = bytes((2, 2, 2, 7, 9))
            else:
                request[17:21] = bytes((2, 2, 7, 9))
            receipt["data"].update(requestHex=request.hex(), responseHex=response.hex())
            events.append(receipt)
    return [
        {"phase": "observe", "action": "run-right", "samples": right,
         "completedGameFrames": FIXTURE_RUN_FRAMES, "events": []},
        {"phase": "observe", "action": case.get("turnAction", "turn-down"), "samples": down,
         "completedGameFrames": 18, "events": events},
    ]


def _test(case_id):
    case = CASES[case_id]
    return {"id": case_id, "actions": [
        {"id": "run-right", "op": "step", "args": {"frames": MAX_RUN_FRAMES,
            "keys": ["RIGHT"], "until": run_until(case_id)}},
        {"id": case.get("turnAction", "turn-down"), "op": "step", "args": {
            "frames": 18, "keys": list(case.get("turnKeys", ("DOWN",)))}}]}


class MountedStantlerSkidObstacleProofTests(unittest.TestCase):
    def test_measured_lean_and_bounce_keep_exact_seat_and_height(self):
        # ROM3481 frame848: measured native distance8192, lean443, and two
        # distinct bounce offsets. Keep its exact integer transition.
        rows = _rows(SECOND)
        sample = next(s for s in rows[-1]["samples"]
                      if s["actors"][0]["motionKind"] == "SKID")
        pair, player, mount = sample["mountedPair"], sample["player"], sample["actors"][0]["engineObject"]
        gait = pair["gait"]
        gait["previous"].update(x=player["pos_x"] - 8192, velocityX=16617,
                                bodyY=7310, riderY=7541, leanX=-69, phase=43683,
                                walking=0)
        gait["pose"].update(velocityX=12405, bodyY=6787, riderY=7164,
                            leanX=443, phase=46413)
        player["face_x"] += 443
        player["unk88_y"], mount["unk88_y"] = 7164, 6787
        pair.update(player=deepcopy(player), mount=deepcopy(mount))
        self.assertTrue(run(rows, _test(SECOND))["passed"])
        controls = negative_controls(rows, _test(SECOND))
        self.assertTrue(controls["passed"], controls)
        reasons = {"missing-gait": "native observation is missing",
                   "wrong-gait-owner": "input, state, or owner differs",
                   "wrong-gait-pose": "distance and frame reference",
                   "wrong-gait-stamp": "input, state, or owner differs",
                   "wrong-pair-pointer": "bound to another object",
                   "wrong-seat": "base, facing or rider offset differs",
                   "wrong-height": "base, facing or rider offset differs"}
        for fault, reason in reasons.items():
            self.assertIn(reason, controls["controls"][fault]["failures"][0])
        for missing in ("mountedPair",):
            bad = deepcopy(rows)
            next(s for s in bad[-1]["samples"]
                 if s["actors"][0]["motionKind"] == "SKID").pop(missing)
            self.assertIn("lacks the native mounted pair", run(bad, _test(SECOND))["failures"][0])

    def test_clear_then_blocked_and_immediately_blocked_cases(self):
        for case_id in (SECOND, FIRST, TWO_KEYS):
            with self.subTest(case=case_id):
                rows, test = _rows(case_id), _test(case_id)
                result = run(rows, test)
                self.assertTrue(result["passed"], result["failures"])
                controls = negative_controls(rows, test)
                self.assertTrue(controls["passed"], controls)
                self.assertEqual(len(controls["controls"]),
                                 len(CASES[case_id]["faults"]))
                self.assertEqual(rows, _rows(case_id))

    def test_wall_cross_and_early_crash_are_independent_failures(self):
        rows = _rows(SECOND)
        crossed = deepcopy(rows)
        crossed[-1]["samples"][-1]["actors"][0]["logical"]["x"] = 590
        self.assertIn("crossed or moved into the blocked tile",
                      run(crossed, _test(SECOND))["failures"][0])
        early = deepcopy(rows)
        early[-1]["events"][-1]["frame"] = FIXTURE_RUN_FRAMES + 1
        self.assertIn("Crash preceded the blocked skid admission",
                      run(early, _test(SECOND))["failures"][0])

    def test_two_key_recovery_requires_idle_crash_then_native_west_walk(self):
        rows, test = _rows(TWO_KEYS), _test(TWO_KEYS)
        result = run(rows, test)
        self.assertTrue(result["passed"], result)
        self.assertGreater(result["heldRecoveryFrame"], result["idleCrashFrame"])
        controls = negative_controls(rows, test)
        self.assertTrue(controls["passed"], controls)
        self.assertIn("Crash did not stop", controls["controls"]["missing-control"]["failures"][0])
        self.assertIn("normal West Walk", controls["controls"]["wrong-recovery"]["failures"][0])
        self.assertIn("native MOTION_STARTED", controls["controls"]["missing-recovery-start"]["failures"][0])
        self.assertIn("native ordinary West Walk admission",
                      controls["controls"]["missing-recovery-admission"]["failures"][0])

    def test_recovery_cannot_silently_return_idle_without_finishing(self):
        rows, test = _rows(TWO_KEYS), _test(TWO_KEYS)
        earlier, final = rows[-1]["samples"][-2:]
        earlier["actors"][0] = deepcopy(final["actors"][0])
        final["actors"][0]["motionElapsed"] = 2
        for event in rows[-1]["events"]:
            if event["frame"] == final["frame"]:
                event["frame"] = earlier["frame"]
        self.assertTrue(run(rows, test)["passed"])
        bad = deepcopy(rows)
        actor = bad[-1]["samples"][-1]["actors"][0]
        actor.update(motionKind="NONE", motionPhase="IDLE")
        actor["movementPolicy"].update(pending=0, speed=0)
        self.assertIn("silently returned idle", run(bad, test)["failures"][0])

    def test_rendered_arrival_still_requires_the_native_walk_commit(self):
        rows = _rows(SECOND)
        actor = rows[0]["samples"][-1]["actors"][0]
        actor.update(motionPhase="COMMIT_PENDING", motionElapsed=4,
                     logical=dict(actor["target"]))
        self.assertTrue(run(rows, _test(SECOND))["passed"])
        pending_before_arrival = deepcopy(rows)
        pending_before_arrival[0]["samples"][-1]["actors"][0]["motionElapsed"] = 3
        self.assertFalse(run(pending_before_arrival, _test(SECOND))["passed"])
        no_commit = deepcopy(rows)
        no_commit[-1]["events"][0]["data"]["event"] = "REMOVED_LOGICAL_COMMIT"
        self.assertIn("Right Walk did not commit", run(no_commit, _test(SECOND))["failures"][0])

    def test_receipt_controls_target_the_skid_among_ordinary_walk_receipts(self):
        for case_id in (SECOND, FIRST, TWO_KEYS):
            rows = _rows(case_id)
            first = rows[-1]["samples"][0]["frame"]
            ordinary_input = _walk_event(first, 50, 1)
            ordinary_blocked = _walk_event(first, 51, 2, 2)
            for receipt in (ordinary_input, ordinary_blocked):
                for field in ("requestHex", "responseHex"):
                    data = bytearray.fromhex(receipt["data"][field])
                    data[20] &= ~2
                    receipt["data"][field] = data.hex()
            rows[-1]["events"].insert(0, ordinary_input)
            rows[-1]["events"].append(ordinary_blocked)
            self.assertTrue(run(rows, _test(case_id))["passed"])
            self.assertTrue(negative_controls(rows, _test(case_id))["passed"])

    def test_registered_recipes_and_contracts_match_the_checker(self):
        registry = json.loads((ROOT / "tools/overworld/runtime_proof_registry.json")
                              .read_text())
        features = json.loads((ROOT / "tools/overworld/system_features.yaml")
                              .read_text())
        mapped = {item["id"]: item["scenarios"]
                  for item in features["capabilities"]}
        for case_id, case in CASES.items():
            with self.subTest(case=case_id):
                recipe_path = ROOT / "tests/overworld/test-recipes" / (case_id + ".json")
                recipe = validate_test(json.loads(recipe_path.read_text()))
                control._shared_test_registration(recipe, ROOT)
                wrong_keys = deepcopy(recipe)
                wrong_keys["actions"][1]["args"]["keys"] = ["UP"]
                with self.assertRaisesRegex(control.ValidationFailure,
                                            "measured route"):
                    control._shared_test_registration(wrong_keys, ROOT)
                wrong_until = deepcopy(recipe)
                wrong_until["actions"][0]["args"]["until"]["value"] += 1
                with self.assertRaisesRegex(control.ValidationFailure,
                                            "measured route"):
                    control._shared_test_registration(wrong_until, ROOT)
                scenario = json.loads((ROOT / "tests/overworld/scenarios" /
                                       (case_id + ".json")).read_text())
                registration = registry["sharedTests"][case_id]
                requirement = case["requirement"]
                self.assertEqual(registration["recipeSha256"],
                                 hashlib.sha256(recipe_path.read_bytes()).hexdigest())
                self.assertEqual(recipe["requirements"], [requirement])
                self.assertEqual(scenario["adapter"]["claims"], list(CLAIMS))
                self.assertEqual(registry["measurementContracts"][requirement],
                                 contract(case_id))
                for capability in scenario["capabilities"]:
                    self.assertIn(case_id, mapped[capability])


if __name__ == "__main__":
    unittest.main()
