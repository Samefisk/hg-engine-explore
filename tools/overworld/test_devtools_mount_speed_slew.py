"""Host-only checks for the saved mounted Stantler speed claim."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_mount_speed_slew_measurement import (
    MountedSpeedSlewMeasurement, walk_step_fx32, require_one_frame_callbacks,
    require_continuous_one_frame_cadence, keyed_walk_duration,
    stop_skid_tail, variance_width,
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


def ease_copied_pair(rows, durations):
    previous = None
    previous_ground = None
    for snapshot, events in rows:
        actor = snapshot["actors"][0]
        index = actor["commitSequence"] - 2
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


def replay(durations=GOOD, fault=None, tail_fault=None):
    count, skid_duration = stop_skid_tail(durations[-1])
    durations = durations + (skid_duration,) * (count + int(tail_fault == "extra"))
    baseline, subject, receipt, rows = pacing_fixture(
        durations, species=234, initial_commit=2)
    for snapshot, events in rows:
        actor = snapshot["actors"][0]
        pair = snapshot["mountPacing"]["latestCompletedPose"]
        pair["input"] = dict(heldKeys=16 if actor["origin"]["x"] < 12 else 0, newKeys=0)
        if actor["origin"]["x"] >= 13:
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
    ease_copied_pair(rows, durations)
    meter = MountedSpeedSlewMeasurement(220)
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


class MountedSpeedSlewTests(unittest.TestCase):
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
