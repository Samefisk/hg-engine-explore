"""Host-only checks for the saved mounted Stantler speed claim."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_mount_speed_slew_measurement import (
    MountedSpeedSlewMeasurement, walk_step_fx32, require_one_frame_callbacks,
    require_continuous_one_frame_cadence, keyed_walk_duration,
    stop_skid_tail, variance_width, linear_walk_reference, validate_linear_walks, linear_tuning,
)
from tools.overworld.devtools_mount_speed_slew_proof import (
    KIND, REQUIREMENT, FAULTS, MountedSpeedNegative, contract, measurements,
    validate_negative_result,
)
from tools.overworld.devtools_test_contract import validate_test
from tools.overworld.test_devtools_mount_pacing_measurement import pacing_fixture
from tools.overworld.normal_play_observer import MotionRecorder, complete_travel
from tools.overworld.devtools_mount_gait import POSE_KEYS, STATE_ADDRESS, expected_pose


GOOD = (6, 6, 5, 5, 3, 3, 2, 2, 2, 2, 2, 2, 2)
PERSISTENT_VARIANCE = (6, 6, 5, 5, 3, 3, 3, 3, 4, 2, 2, 2, 4)
ZERO_VARIANCE = (6, 5, 4, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2)


def ease_copied_pair(rows, durations, first_commit=2):
    previous = None
    previous_ground = None
    for snapshot, events in rows:
        actor = snapshot["actors"][0]
        index = actor["commitSequence"] - first_commit
        pair = snapshot["mountPacing"]["latestCompletedPose"]
        if actor["motionKind"] in ("WALK", "SKID") and 0 <= index < len(durations):
            prior = durations[index - 1] if index and actor["motionKind"] == "WALK" else 0
            position = (actor["origin"]["x"] << 16) + 32768 \
                + walk_step_fx32(actor["motionElapsed"], actor["motionDuration"], prior)
            snapshot["player"]["pos_x"] = position
            actor["engineObject"]["pos_x"] = position
            pair["player"]["pos_x"] = pair["mount"]["pos_x"] = position
        if previous is None:
            previous = dict.fromkeys(POSE_KEYS, 0)
            previous.update(x=pair["player"]["pos_x"], z=pair["player"]["pos_z"])
        input = dict(x=pair["player"]["pos_x"], z=pair["player"]["pos_z"],
                     stamp=snapshot["nativeCycle"], session=1, owner=pair["playerPointer"],
                     mode=int(actor["motionKind"] in ("WALK", "SKID") and actor["motionPhase"] != "IDLE"), options=0x5A)
        gait_pose = expected_pose(previous, input)
        pair["gait"] = dict(schemaVersion=1, address=STATE_ADDRESS, previous=deepcopy(previous),
                            pose=deepcopy(gait_pose), stamp=input["stamp"], session=1,
                            owner=input["owner"], initialized=1, input=input)
        previous = gait_pose
        pair["player"]["unk88_y"] = gait_pose["riderY"]
        pair["mount"]["unk88_y"] = gait_pose["bodyY"]
        pair["player"]["face_x"] = -32768 + gait_pose["leanX"]
        pair["player"]["face_z"] = gait_pose["leanZ"]
        snapshot["player"]["unk88_y"] = gait_pose["riderY"]
        actor["engineObject"]["unk88_y"] = gait_pose["bodyY"]
        ground = [pair["player"]["pos_" + key] for key in "xyz"]
        snapshot["camera"] = {"targetPointer": actor["engineIdentity"]["anchorPointer"] + 0x70,
                              "lastTarget": previous_ground or ground,
                              "lookAtTarget": previous_ground or ground}
        previous_ground = ground
        draw = {}
        for key, pointer in (("player", actor["engineIdentity"]["anchorPointer"]),
                             ("mount", actor["engineIdentity"]["pointer"])):
            source = pair[key]
            vectors = {name: [source[prefix + axis] for axis in "xyz"]
                       for name, prefix in (("position", "pos_"), ("face", "face_"),
                                            ("extra", "unk88_"), ("jump", "unk94_"))}
            draw[key] = dict(objectPointer=pointer, graphicsPointer=0x02350000,
                             graphics=[sum(vector[axis] for vector in vectors.values())
                                       + (0x6000 if axis == 2 else 0)
                                       for axis in range(3)], **vectors)
        draw["shadows"] = [
            dict(index=3, pointer=0x02351000,
                 owner=draw["mount"]["objectPointer"], callback=0x021FD719,
                 flags=1, hidden=0,
                 position=[pair["mount"]["pos_" + axis] for axis in "xyz"]),
            dict(index=4, pointer=0x023510C8,
                 owner=draw["player"]["objectPointer"], callback=0x021FD92D,
                 flags=1, hidden=1,
                 position=[pair["player"]["pos_" + axis] for axis in "xyz"]),
        ]
        snapshot["mountedDrawPose"] = draw
        if actor["motionKind"] == "WALK" and 0 <= index < len(durations):
            for event in events:
                if event["kind"] == "native-observation":
                    event["data"]["player"]["pos_x"] = position
                    event["data"]["mount"]["pos_x"] = position
        for event in events:
            if event["kind"] == "native-observation":
                event["data"].update(gait=deepcopy(pair["gait"]),
                    player=deepcopy(pair["player"]), mount=deepcopy(pair["mount"]))


def replay(durations=GOOD, fault=None, tail_fault=None, *, linear=False, linear_ramp=12, policy_fault=None):
    first_commit = 4 if linear else 2
    reference = linear_walk_reference(55, 1, first_commit, linear_ramp) if linear else None
    if linear:
        durations = tuple(row["duration"] for row in reference)

    count, skid_duration = stop_skid_tail(durations[-1])
    durations = durations + (skid_duration,) * (count + int(tail_fault == "extra"))
    baseline, subject, receipt, rows = pacing_fixture(
        durations, species=234, initial_commit=first_commit)
    if linear:
        shift_linear_fixture(baseline, rows)
    for snapshot, events in rows:
        actor = snapshot["actors"][0]
        pair = snapshot["mountPacing"]["latestCompletedPose"]
        pair["input"] = dict(heldKeys=16 if actor["origin"]["x"] < (597 if linear else 12) else 0, newKeys=0)
        if actor["origin"]["x"] >= (598 if linear else 13):
            if actor["motionKind"] == "WALK":
                actor["motionKind"] = "WALK" if tail_fault == "walk" else "SKID"
            pair["publicSubject"] = deepcopy(actor)
            for event in events:
                data = event["data"]
                if event["kind"] == "native-observation":
                    data["publicSubject"] = deepcopy(actor)
                elif data.get("event") == "MOTION_STARTED":
                    data["valueA"] = 4
                elif data.get("event") in ("LOGICAL_COMMIT", "MOTION_FINISHED"):
                    data["valueB"] = 4
    for _ in range(32):
        snapshot = deepcopy(rows[-1][0])
        snapshot["frame"] += 1
        snapshot["nativeCycle"] += 1
        snapshot["actorFrame"] += 1
        pose = snapshot["mountPacing"]["latestCompletedPose"]
        pose.update(frame=snapshot["frame"], nativeCycle=snapshot["nativeCycle"])
        rows.append((snapshot, []))
    ease_copied_pair(rows, durations, first_commit)
    if linear:
        add_linear_policy_receipts(baseline, rows, reference, first_commit, policy_fault, linear_ramp)
    meter = MountedSpeedSlewMeasurement(220, linear_ramp=linear_ramp if linear else None)
    meter.arm(subject, baseline, receipt)
    negative = MountedSpeedNegative(fault) if fault else None
    for snapshot, events in rows:
        row = dict(phase="observe", samples=[snapshot], events=events)
        if negative:
            row = negative.mutate(row, {"mounted": subject})
        meter.observe(row["samples"][0], row["events"])
        if meter.failures:
            break
    if not meter.failures and meter.ready:
        reader = dict(receipt, closed=True, counts=meter.counts,
                      latestCompletedPose=rows[-1][0]["mountPacing"]["latestCompletedPose"])
        meter.close(dict(closed=True, advancedFrames=0, acceptedProof=False,
                         mountPacing=reader), rows[-1][0])
    value = meter.result()
    return dict(passed=value["passed"], failures=[], measurements={KIND: value})


def shift_linear_fixture(baseline, rows):
    """Place copied poses on the recipe lane; this is host data, never guest setup."""
    def actor_pose(actor):
        for key in ("logical", "origin", "target"):
            actor[key]["x"] += 585
            actor[key]["y"] += 402
        object_pose(actor["engineObject"])
    def object_pose(obj):
        obj["pos_x"] += 585 << 16
        obj["pos_z"] += 402 << 16
        obj["x"] += 585
        obj["y"] += 402
    actor_pose(baseline["actors"][0])
    object_pose(baseline["player"])
    for snapshot, events in rows:
        actor_pose(snapshot["actors"][0]); object_pose(snapshot["player"])
        pair = snapshot["mountPacing"]["latestCompletedPose"]
        actor_pose(pair["publicSubject"])
        for obj in (pair["player"], pair["mount"]): object_pose(obj)
        for event in events:
            if event["kind"] == "native-observation":
                data = event["data"]
                actor_pose(data["publicSubject"])
                for obj in (data["player"], data["mount"]): object_pose(obj)


def add_linear_policy_receipts(baseline, rows, reference, first_commit, fault=None, ramp=12):
    from tools.overworld.devtools_acceleration_measurement import POLICY_FIELDS, LINEAR_POLICY_FIELDS
    fields = {**POLICY_FIELDS, **LINEAR_POLICY_FIELDS}
    base, fastest = linear_tuning(ramp)
    sequence = baseline["nativeObservation"]["sequence"]
    changed = False
    for snapshot, events in rows:
        actor = snapshot["actors"][0]
        beginning = actor["motionKind"] == "WALK" and actor["motionElapsed"] == 0
        committing = actor["motionKind"] == "NONE" and any(e.get("data", {}).get("event") == "LOGICAL_COMMIT" and e["data"]["valueB"] == 1 for e in events)
        index = actor["commitSequence"] - first_commit - int(committing)
        for op in ((1, 2) if beginning else (3,) if committing else ()):
            if not 0 <= index < 13:
                continue
            expected = reference[index]
            subject = deepcopy(actor); subject["commitSequence"] = first_commit + index
            request = bytearray(28); request[:4] = b"\x01\x00\x1c\x00"
            request[4:8] = (0x023BC74C).to_bytes(4, "little")
            request[8:12] = bytes((7, op, 0 if op == 2 else 3, int(op == 3)))
            request[14] = 4 if op == 3 else 16 if op == 2 else 9
            if op == 2:
                request[15] = 1
                request[17:20] = bytes((3, 3, expected["duration"]))
                request[20] = 1
                request[24:27] = bytes((expected["nominal"], expected["nextCarry"], expected["elapsed"]))
            response = bytearray(request)
            if op == 1:
                response[16:20] = bytes((2, 3, 3, expected["duration"]))
                response[20] = 1
                response[24:27] = bytes((expected["nominal"], expected["nextCarry"], expected["elapsed"]))
            else:
                response[16] = 1
            before = bytearray(36); before[0] = 3; before[3] = base; before[22] = 2 if op == 3 else 0
            before[32:35] = bytes((expected["elapsed"], expected["nextCarry"] if op == 3 else expected["carry"], int(index != 0 or op == 3)))
            after = bytearray(before)
            after[22] = 0 if op == 3 else 1
            after[32:35] = bytes((expected["nextElapsed"] if op == 3 else expected["elapsed"], expected["nextCarry"] if op == 3 else expected["carry"], 1))
            lane = bytearray(80)
            for offset,value in ((7,base),(50,ramp),(51,fastest),(64,4),(71,34)): lane[offset]=value
            data = dict(observation="walk-policy", slot=7, operation=op, returnValue=1,
                publicSubject=subject, publicSubjectAfter=deepcopy(subject), requestHex=request.hex(),
                responseHex=response.hex(),
                entryActorFrame=snapshot["actorFrame"], returnActorFrame=snapshot["actorFrame"],
                entryNativeCycle=snapshot["nativeCycle"], returnNativeCycle=snapshot["nativeCycle"])
            if op != 2:
                data.update(laneHex=lane.hex(), policyBeforeHex=before.hex(), policyAfterHex=after.hex(),
                    policyBefore={key:before[offset] for key,offset in fields.items()},
                    policyAfter={key:after[offset] for key,offset in fields.items()})
            target_op = 2 if fault in ("missing-start", "rejected-start") else 1 if fault == "post-deadline-jitter" else 3
            eligible = expected["elapsed"] == ramp if fault == "post-deadline-jitter" else True
            if not changed and fault and op == target_op and eligible:
                if fault == "frozen-elapsed":
                    after[32] = expected["elapsed"]
                elif fault == "early-full":
                    after[32] = ramp
                elif fault == "stale-owner":
                    data["publicSubject"]["handle"]["fieldEpoch"] += 1
                elif fault == "wrong-width":
                    lane[64] = 6; data["laneHex"] = lane.hex()
                elif fault in ("missing-commit", "missing-start"):
                    op = None
                elif fault == "failed-call":
                    data["returnValue"] = 0
                elif fault == "rejected-start":
                    request[15] = 2; data["requestHex"] = request.hex()
                elif fault == "post-deadline-jitter":
                    response[19] += 1
                changed = True
                data["responseHex"] = response.hex()
                if op != 2 and "policyAfterHex" in data:
                    data.update(policyAfterHex=after.hex(), policyAfter={key:after[offset] for key,offset in fields.items()})
            if op:
                events.append(dict(kind="native-observation", frame=snapshot["frame"], data=data))
        for event in events:
            if event["kind"] == "native-observation":
                sequence += 1; event["data"]["sequence"] = sequence
        snapshot["nativeObservation"]["sequence"] = sequence



class MountedSpeedSlewTests(unittest.TestCase):

    def test_linear12_idle_configuration_receipt_and_faults(self):
        import struct
        from tools.overworld.devtools_records import select_current_actor
        snapshot, subject, _, _ = pacing_fixture(species=234)
        subject = select_current_actor(snapshot, subject)
        actor = snapshot["actors"][0]
        actor["movementPolicy"] = dict(pending=0)
        raw = bytearray(192)
        raw[8:88] = bytes(range(80))
        struct.pack_into("<IHHHHBBBB", raw, 88, actor["subjectIdentity"], actor["species"],
            snapshot["context"]["mapId"], actor["handle"]["mapGeneration"],
            actor["handle"]["encounterGeneration"], actor["form"], actor["level"], 0, 0)
        struct.pack_into("<IBBBB", raw, 104, 1, 3, 0, 0, 0)
        raw[122] = 1
        actual = bytearray(raw)
        for offset, value in ((7, 6), (19, 0), (50, 12), (51, 2), (64, 4), (71, 34)):
            actual[8 + offset] = value
        ready = dict(subject=deepcopy(subject), actor=deepcopy(actor), snapshot={k: deepcopy(snapshot.get(k))
            for k in ("frame", "nativeCycle", "actorFrame", "context", "player")})
        def state(data):
            return dict(mountStateHex=data.hex(), profileHex=data[8:88].hex(), bindingHex=data[88:104].hex(),
                sessionGeneration=1, clock={k:snapshot[k] for k in ("frame", "nativeCycle")}, readiness=deepcopy(ready))
        receipt = dict(completed=True, prepared=True, acceptedProof=False, guestAdvanced=False,
            scope="prepared-idle-mounted-walk-fixture", subject=deepcopy(subject), directionMode=0,
            travelTime=6, fastestTime=2, timeToFullSpeed=12, timeVariance=2,
            changedOffsets=[7,19,50,51,64,71], before=state(raw), after=state(actual), expectedStateHex=actual.hex())
        meter = MountedSpeedSlewMeasurement(300, linear_ramp=12)
        meter.configure(receipt, snapshot, subject)
        with self.assertRaises(ValueError): meter.configure(receipt, snapshot, subject)
        for fault in ("knob", "clock", "owner", "unrelated-byte", "readiness", "binding", "advanced"):
            changed = deepcopy(receipt)
            if fault == "knob": changed["timeToFullSpeed"] = 120
            elif fault == "clock": changed["after"]["clock"]["nativeCycle"] += 1
            elif fault == "owner": changed["subject"]["handle"]["generation"] += 1
            elif fault in ("unrelated-byte", "binding"):
                data = bytearray(actual); data[150 if fault == "unrelated-byte" else 88] ^= 1
                changed["after"].update(state(data)); changed["expectedStateHex"] = data.hex()
            elif fault == "readiness": changed["after"]["readiness"]["actor"]["commitSequence"] += 1
            else: changed["guestAdvanced"] = True
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                MountedSpeedSlewMeasurement(300, linear_ramp=12).configure(changed, snapshot, subject)
        with self.assertRaises(ValueError):
            MountedSpeedSlewMeasurement(300).configure(receipt, snapshot, subject)

    def test_sprint60_reaches_one_full_speed_deadline(self):
        result = replay(linear=True, linear_ramp=60)
        meter = result["measurements"][KIND]
        self.assertTrue(result["passed"], meter["failures"])
        record = dict(sessionId="host", sessionCleanup=dict(sessionId="host", closed=True, errors=[]))
        self.assertEqual(len(measurements(result, record)), 16)
        actor = meter["initial"]["actors"][0]
        reference = validate_linear_walks(actor, meter["windows"][0]["motions"], meter["linearPolicies"], 60)
        first = next(i for i, row in enumerate(reference) if row["elapsed"] >= 60)
        self.assertEqual((reference[first]["nominal"], reference[first]["width"], reference[first]["duration"]), (4, 0, 4))
        self.assertGreaterEqual(len(reference) - first, 2)
        self.assertEqual(sorted(set(row["width"] for row in reference)), [0, 1, 2])
        self.assertEqual({op:sum(e["data"]["operation"] == op for e in meter["linearPolicies"]) for op in (1,2,3)}, {1:13,2:13,3:13})
        # Same ramp and native receipt checks reject the old second fade clock.
        for fault, reason in (("post-deadline-jitter", "ramp deadline"),
                              ("missing-start", "real accepted and committed"),
                              ("rejected-start", "normal Walk admission")):
            with self.subTest(fault=fault):
                failed = replay(linear=True, linear_ramp=60, policy_fault=fault)["measurements"][KIND]
                self.assertFalse(failed["passed"])
                self.assertTrue(any(reason in message for message in failed["failures"]), failed["failures"])
        failed = replay(linear=True, linear_ramp=60, fault="mounted-speed-persistent-variance")
        validate_negative_result(failed, "mounted-speed-persistent-variance")

    def test_sprint60_exact_idle_recipe_and_registration(self):
        import hashlib
        from tools.overworld.control import _shared_test_registration
        from tools.overworld.devtools_test_contract import TestEvaluator
        from tools.overworld.validation import ValidationFailure
        root = Path(__file__).resolve().parents[2]
        path = root / "tests/overworld/test-recipes/mount.stantler-sprint-full-speed.json"
        recipe = json.loads(path.read_text())
        self.assertEqual(validate_test(recipe)["id"], "mount.stantler-sprint-full-speed")
        value = TestEvaluator(recipe); value.install_measurements({KIND:{"contractVersion":1}})
        self.assertEqual(value.measurements[KIND].linear_ramp, 60)
        registry = json.loads((root / "tools/overworld/runtime_proof_registry.json").read_text())
        self.assertEqual(registry["sharedTests"][recipe["id"]]["measurementContract"], contract())
        self.assertEqual(_shared_test_registration(recipe, root)[1], hashlib.sha256(path.read_bytes()).hexdigest())
        for key, wrong in (("travelTime",6),("fastestTime",2),("timeToFullSpeed",12),("timeVariance",0)):
            changed = deepcopy(recipe); changed["setup"][-1]["args"][key] = wrong
            with self.subTest(key=key), self.assertRaises(ValueError): validate_test(changed)
        changed = deepcopy(recipe); changed["measurements"][0]["linearRamp"] = 12
        with self.assertRaises(ValueError): validate_test(changed)
        changed["setup"][-1]["args"].update(travelTime=6,fastestTime=2,timeToFullSpeed=12)
        with self.assertRaises(ValidationFailure): _shared_test_registration(changed, root)

    def test_linear12_real_policy_boundaries_and_independent_replay(self):
        result = replay(linear=True)
        meter = result["measurements"][KIND]
        self.assertTrue(result["passed"], meter["failures"])
        record = dict(sessionId="host", sessionCleanup=dict(sessionId="host", closed=True, errors=[]))
        self.assertEqual(len(measurements(result, record)), 16)
        actor = meter["initial"]["actors"][0]
        reference = validate_linear_walks(actor, meter["windows"][0]["motions"], meter["linearPolicies"])
        self.assertEqual(sorted(set(row["width"] for row in reference)), [0,1,2])
        self.assertEqual(reference[-1]["elapsed"], 12)
        self.assertGreaterEqual(sum(row["width"] == 0 and row["duration"] == 2 for row in reference), 2)
        # Dynamic starting commit is deliberately4, rather than the old fixture's2.
        self.assertEqual(actor["commitSequence"], 4)

    def test_linear12_rejects_real_counter_lane_and_owner_faults(self):
        for fault,reason in (("frozen-elapsed","shared clock"),("early-full","shared clock"),
                             ("stale-owner","subject differs"),("wrong-width","native lane"),
                             ("missing-commit","real accepted and committed"),("failed-call","policy ABI")):
            with self.subTest(fault=fault):
                value = replay(linear=True, policy_fault=fault)["measurements"][KIND]
                self.assertFalse(value["passed"])
                self.assertTrue(any(reason in error for error in value["failures"]), value["failures"])
        copied = replay(linear=True)
        copied["measurements"][KIND]["linearPolicies"].pop()
        record = dict(sessionId="host", sessionCleanup=dict(sessionId="host", closed=True, errors=[]))
        with self.assertRaises(ValueError): measurements(copied, record)

    def test_linear12_existing_persistent_variance_control(self):
        result = replay(linear=True, fault="mounted-speed-persistent-variance")
        value = result["measurements"][KIND]
        self.assertFalse(value["passed"])
        self.assertIn("mounted Linear did not reach full speed and zero variance at its ramp deadline", value["failures"])
        validate_negative_result(result, "mounted-speed-persistent-variance")

    def test_linear12_recipe_and_exact_idle_setup(self):
        import hashlib
        root = Path(__file__).resolve().parents[2]
        path = root / "tests/overworld/test-recipes/mount.stantler-linear-variance.json"
        recipe = json.loads(path.read_text())
        self.assertEqual(validate_test(recipe)["id"], "mount.stantler-linear-variance")
        from tools.overworld.devtools_test_contract import TestEvaluator
        value = TestEvaluator(recipe)
        value.install_measurements({KIND: {"contractVersion": 1}})
        self.assertEqual(value.measurements[KIND].linear_ramp, 12)
        registry = json.loads((root / "tools/overworld/runtime_proof_registry.json").read_text())
        self.assertEqual(registry["sharedTests"][recipe["id"]]["recipeSha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(registry["sharedTests"][recipe["id"]]["measurementContract"], contract())
        from tools.overworld.control import _shared_test_registration
        from tools.overworld.validation import ValidationFailure
        self.assertEqual(_shared_test_registration(recipe, root)[1], registry["sharedTests"][recipe["id"]]["recipeSha256"])
        wrong_variant = deepcopy(recipe)
        wrong_variant["measurements"][0].pop("linearRamp")
        wrong_variant["setup"].pop()
        with self.assertRaises(ValidationFailure): _shared_test_registration(wrong_variant, root)
        for key,value in (("timeToFullSpeed",120),("timeVariance",0),("travelTime",5)):
            changed = deepcopy(recipe); changed["setup"][-1]["args"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): validate_test(changed)
        changed = deepcopy(recipe);changed["measurements"][0]["linearRamp"]=True
        with self.assertRaises(ValueError):validate_test(changed)

    def test_camera_fault_waits_for_two_real_graphics_samples(self):
        negative = MountedSpeedNegative("mounted-gait-camera-bob")
        empty = dict(phase="observe", action="arm-reader")
        self.assertEqual(negative.mutate(empty, {}), empty)
        def row(pointer, frame):
            return dict(phase="observe", samples=[dict(frame=frame,
                camera=dict(lookAtTarget=[0, 65536, 0]),
                mountedDrawPose=dict(player=dict(graphicsPointer=pointer)))])
        for sample in (row(0, 804), row(37025864, 805)):
            self.assertEqual(negative.mutate(sample, {}), sample)
            self.assertFalse(negative.applied)
        sample = row(37025864, 806)
        changed = negative.mutate(sample, {})
        self.assertTrue(negative.applied)
        self.assertEqual(changed["samples"][0]["camera"]["lookAtTarget"][1], 65536 + 4096)
        self.assertEqual(sample["samples"][0]["camera"]["lookAtTarget"][1], 65536)

    def test_stop_tail_uses_displayed_time_not_nominal_speed(self):
        self.assertEqual([stop_skid_tail(time) for time in (1, 2, 3, 4, 5, 6, 7)],
                         [(4, 2), (2, 4), (2, 6), (2, 8), (1, 10), (1, 12), (0, 14)])

    def test_independent_proof_rejects_changed_stop_tail(self):
        result = replay()
        record = dict(sessionId="host", sessionCleanup=dict(sessionId="host", closed=True, errors=[]))
        for fault in ("missing", "duration", "kind", "input"):
            copied = deepcopy(result)
            window = copied["measurements"][KIND]["windows"][0]
            if fault == "missing":
                window["motions"].pop()
            elif fault == "duration":
                window["motions"][-1]["duration"] += 1
            elif fault == "kind":
                window["motions"][-1]["kind"] = "WALK"
            else:
                window["gaitFrames"][-1]["pair"]["input"]["heldKeys"] = 16
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                measurements(copied, record)

    def test_stop_tail_rejects_extra_motion_or_walk(self):
        for fault in ("extra", "walk"):
            value = replay(tail_fault=fault)["measurements"][KIND]
            self.assertFalse(value["passed"])
            self.assertTrue(value["failures"])

    @staticmethod
    def fast_successor(snap=False, *, second=False, skip_hold=False, snap_hold=False,
                       no_hold=False):
        recorder = MotionRecorder()
        actor = dict(handle={"value": 7}, behaviorFingerprint=123,
                     motionKind="WALK", motionPhase="MOVING", motionDuration=2,
                     motionElapsed=0, origin={"x": 594, "y": 402},
                     target={"x": 595, "y": 402}, logical={"x": 594, "y": 402},
                     commitSequence=0)
        engine = dict(pos_x=(594 << 16)+32768, pos_y=0,
                      pos_z=(402 << 16)+32768, unk88_y=0,
                      facing=3, flags=0)
        recorder.observe(0, actor, engine)
        actor["motionElapsed"] = 1
        actor["logical"]["x"] = 595
        engine["pos_x"] += 32768
        recorder.observe(1, actor, engine)
        actor["motionPhase"] = "COMMIT_PENDING"
        actor["motionElapsed"] = 2
        engine["pos_x"] += 32768
        recorder.observe(2, actor, engine)
        actor.update(motionDuration=1, motionElapsed=1, motionPhase="COMMIT_PENDING",
                     origin={"x": 595, "y": 402}, target={"x": 596, "y": 402},
                     logical={"x": 596, "y": 402}, commitSequence=1)
        engine["pos_x"] = (596 + int(snap) << 16) + 32768
        recorder.observe(3, actor, engine)
        if second:
            if not skip_hold and not no_hold:
                if snap_hold:
                    engine["pos_x"] += 65536
                recorder.observe(4, actor, engine)
            actor.update(motionDuration=1, motionElapsed=1, motionPhase="COMMIT_PENDING",
                         origin={"x": 596, "y": 402}, target={"x": 597, "y": 402},
                         logical={"x": 597, "y": 402}, commitSequence=2)
            engine["pos_x"] = (597 << 16) + 32768
            next_frame = 4 if no_hold else 5
            recorder.observe(next_frame, actor, engine)
            actor.update(motionKind="NONE", motionPhase="IDLE", commitSequence=3)
            recorder.observe(next_frame + 1, actor, engine)
        else:
            actor.update(motionKind="NONE", motionPhase="IDLE", commitSequence=2)
            recorder.observe(4, actor, engine)
        return recorder

    def test_one_frame_commit_pending_successor_keeps_both_real_tiles(self):
        recorder = self.fast_successor()
        self.assertEqual(recorder.failures, [])
        self.assertEqual(len(recorder.completed), 2)
        self.assertEqual([motion["duration"] for motion in recorder.completed], [2, 1])
        self.assertEqual(recorder.completed[0]["terminalRender"][0], (595 << 16)+32768)
        self.assertEqual(recorder.completed[1]["samples"][0]["elapsed"], 1)
        self.assertEqual(recorder.completed[1]["travelEnd"]["observedBy"], "one-frame-successor")
        self.assertTrue(all(complete_travel(motion) for motion in recorder.completed))

    def test_common_mode_snap_is_not_a_fast_successor(self):
        recorder = self.fast_successor(snap=True)
        self.assertIn("terminal-render-target", [failure["reason"] for failure in recorder.failures])

    def test_one_frame_endpoint_hold_then_next_one_frame_walk(self):
        recorder = self.fast_successor(second=True)
        self.assertEqual(recorder.failures, [])
        self.assertEqual([motion["duration"] for motion in recorder.completed], [2, 1, 1])
        self.assertEqual(recorder.completed[1]["lastEndpointFrame"], 4)
        self.assertTrue(all(complete_travel(motion) for motion in recorder.completed))
        with self.assertRaisesRegex(ValueError, "paused before the next tile"):
            require_continuous_one_frame_cadence(recorder.completed[1], recorder.completed[2])

    def test_adjacent_one_frame_targets_have_no_stationary_frame(self):
        recorder = self.fast_successor(second=True, no_hold=True)
        self.assertEqual(recorder.failures, [])
        self.assertTrue(require_continuous_one_frame_cadence(
            recorder.completed[1], recorder.completed[2]))

    def test_one_frame_hold_cannot_hide_skipped_frame_or_snap(self):
        for changes in (dict(skip_hold=True), dict(snap_hold=True)):
            with self.subTest(changes=changes):
                recorder = self.fast_successor(second=True, **changes)
                reasons = [failure["reason"] for failure in recorder.failures]
                self.assertIn("terminal-render-target", reasons)

    def test_one_frame_native_callbacks_need_exact_origin_and_endpoint(self):
        motion = dict(origin=[595, 402], target=[596, 402], startFrame=830,
                      travelEnd=dict(observedBy="one-frame-successor"))
        def callback(phase, elapsed, actor_frame, pos_x):
            return dict(frame=830, data=dict(returnActorFrame=actor_frame,
                returnNativeCycle=2130,
                publicSubject=dict(origin=dict(x=595, y=402), target=dict(x=596, y=402),
                                   motionDuration=1, motionPhase=phase, motionElapsed=elapsed),
                player=dict(pos_x=pos_x, pos_z=(402 << 16)+32768)))
        origin = callback("MOVING", 0, 394, (595 << 16)+32768)
        target = callback("COMMIT_PENDING", 1, 395, (596 << 16)+32768)
        self.assertTrue(require_one_frame_callbacks(motion, [origin, target]))
        for changed in ([target], [origin], [origin, {**target, "frame": 831}],
                        [origin, {**target, "data": {**target["data"], "player": {
                            "pos_x": (597 << 16)+32768, "pos_z": (402 << 16)+32768}}}]):
            with self.subTest(callbacks=changed), self.assertRaisesRegex(ValueError, "origin and endpoint"):
                require_one_frame_callbacks(motion, changed)

    def test_recipe_and_registry_contract(self):
        root = Path(__file__).resolve().parents[2]
        recipe = json.loads((root / "tests/overworld/test-recipes/mount.stantler-speed-slew.json").read_text())
        registry = json.loads((root / "tools/overworld/runtime_proof_registry.json").read_text())
        self.assertEqual(validate_test(recipe)["id"], "mount.stantler-speed-slew")
        self.assertEqual(registry["sharedTests"]["mount.stantler-speed-slew"]["measurementContract"], contract())
        self.assertEqual(registry["measurementContracts"][REQUIREMENT], contract())

    def test_variance_fades_only_after_nominal_maximum(self):
        self.assertEqual([variance_width(i) for i in range(13)],
                         [2, 2, 2, 2, 2, 1, 0, 0, 0, 0, 0, 0, 0])
        self.assertEqual([keyed_walk_duration(i, 2744495732, 1, i + 2) for i in range(13)],
                         [7, 5, 4, 4, 2, 3, 2, 2, 2, 2, 2, 2, 2])
        # Prior accepted live run: Walk9/commit10 remained at four frames.
        self.assertEqual(keyed_walk_duration(8, 2744495732, 1, 10, fade=False), 4)
        self.assertEqual(keyed_walk_duration(8, 2744495732, 1, 10), 2)
        value = replay(PERSISTENT_VARIANCE)["measurements"][KIND]
        self.assertIn("mounted speed variance did not fade at nominal maximum", value["failures"])

    def test_fading_variance_and_eased_positions_pass(self):
        self.assertEqual(tuple(keyed_walk_duration(index, 55, 1, index + 2)
                               for index in range(len(GOOD))), GOOD)
        result = replay()
        self.assertTrue(result["passed"], result["measurements"][KIND]["failures"])
        record = dict(sessionId="host", sessionCleanup=dict(sessionId="host", closed=True, errors=[]))
        self.assertEqual(len(measurements(result, record)), 16)

    def test_stale_visible_sprite_fails_even_when_pair_matches(self):
        baseline, subject, receipt, rows = pacing_fixture(GOOD, species=234, initial_commit=2)
        ease_copied_pair(rows, GOOD)
        rows[0][0]["mountedDrawPose"]["player"]["graphics"][0] -= 6553
        meter = MountedSpeedSlewMeasurement(220)
        meter.arm(subject, baseline, receipt)
        meter.observe(*rows[0])
        self.assertIn("mounted visible sprite lags the camera target", meter.failures)

    def test_stale_mount_shadow_fails_even_when_sprites_match(self):
        result = replay(fault="mounted-speed-shadow-lag")
        self.assertFalse(result["passed"])
        validate_negative_result(result, "mounted-speed-shadow-lag")

    def test_visible_player_shadow_fails(self):
        baseline, subject, receipt, rows = pacing_fixture(GOOD, species=234, initial_commit=2)
        ease_copied_pair(rows, GOOD)
        rows[0][0]["mountedDrawPose"]["shadows"][1]["hidden"] = 0
        meter = MountedSpeedSlewMeasurement(220)
        meter.arm(subject, baseline, receipt)
        meter.observe(*rows[0])
        self.assertIn("player shadow is visible while mounted", meter.failures)

    def test_idle_graphics_setup_frame_is_not_a_walk_frame(self):
        baseline, subject, receipt, rows = pacing_fixture(GOOD, species=234, initial_commit=2)
        ease_copied_pair(rows, GOOD)
        warmup = deepcopy(rows[0][0])
        warmup["actors"][0].update(motionKind="NONE", motionPhase="IDLE")
        warmup["mountedDrawPose"]["player"].update(graphicsPointer=0, graphics=None)
        warmup["mountedDrawPose"]["shadows"][1]["hidden"] = 0
        meter = MountedSpeedSlewMeasurement(220)
        meter.arm(subject, baseline, receipt)
        meter.observe(warmup, rows[0][1])
        self.assertEqual(meter.failures, [])

    def test_proof_allows_only_one_idle_setup_frame(self):
        record = dict(sessionId="host", sessionCleanup=dict(
            sessionId="host", closed=True, errors=[]))
        replayed = replay()
        meter = replayed["measurements"][KIND]
        meter["frames"] += 1
        self.assertEqual(len(measurements(replayed, record)), 16)
        meter["frames"] += 1
        with self.assertRaisesRegex(ValueError, "62 completed shadow frames"):
            measurements(replayed, record)

    def test_duration_above_authored_variance_fails(self):
        result = replay(GOOD[:7] + (5,) + GOOD[8:])
        self.assertFalse(result["passed"])
        self.assertIn("mounted speed variance did not fade at nominal maximum",
                      result["measurements"][KIND]["failures"])

    def test_duration_below_nominal_fails(self):
        result = replay((7,) + GOOD[1:])
        self.assertFalse(result["passed"])

    def test_all_zero_variance_fails(self):
        result = replay(ZERO_VARIANCE)
        self.assertFalse(result["passed"])
        self.assertIn("mounted speed lost its keyed variance value",
                      result["measurements"][KIND]["failures"])

    def test_independent_proof_rejects_copied_zero_variance_tile(self):
        copied = deepcopy(replay())
        motion = copied["measurements"][KIND]["windows"][0]["motions"][1]
        motion["duration"] = ZERO_VARIANCE[1]
        record = dict(sessionId="host", sessionCleanup=dict(sessionId="host", closed=True, errors=[]))
        with self.assertRaisesRegex(ValueError, "lost its keyed variance value"):
            measurements(copied, record)

    def test_common_mode_snap_fails_with_pair_still_aligned(self):
        result = replay(fault="mounted-speed-common-snap")
        self.assertFalse(result["passed"])
        validate_negative_result(result, "mounted-speed-common-snap")

    def test_all_copied_controls_reject_for_expected_reason(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                validate_negative_result(replay(fault=fault), fault)


if __name__ == "__main__":
    unittest.main()
