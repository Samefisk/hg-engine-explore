"""Focused host checks for the mounted Stantler facing/travel split."""

from copy import deepcopy
import unittest

from tools.overworld.devtools_mount_gait import STATE_ADDRESS, POSE_KEYS, expected_pose
from tools.overworld.devtools_mounted_stantler_turn_skid_proof import (
    ACTIONS, contract, validate_skid_pose, run, negative_controls,
)


def skid_samples():
    """Synthetic static poses for the pure pose unit, without native proof credit."""
    mount = {key: 0 for key in (
        "pos_x", "pos_y", "pos_z", "face_x", "face_y", "face_z",
        "unk88_x", "unk88_y", "unk94_x", "unk94_y")}
    mount["facing"] = 1
    player = dict(mount, face_y=32768, face_z=-40960)
    return [(
        {"player": deepcopy(player), "frame": 40 + tile * 8 + elapsed - 1},
        {"motionElapsed": elapsed, "motionDuration": 6, "commitSequence": 10 + tile,
         "origin": {"x": 590 + tile, "y": 402},
         "target": {"x": 591 + tile, "y": 402},
         "engineObject": deepcopy(mount)},
    ) for tile in range(2) for elapsed in range(1, 7)]


def proof_rows():
    """Synthetic current pair/gait packets for full proof rejection checks."""
    skid = skid_samples()
    def sample(frame, actor, player, kind, key):
        actor = deepcopy(actor)
        actor.update(active=True, role="MOUNTED", species=234, identityVerified=True,
            presentationAttached=True, inputOwnership=1, handle={"value": 7},
            subjectIdentity=55, logical={"x": 586 if frame == 0 else 590, "y": 402},
            engineIdentity={"anchorPointer": 0x02200000, "pointer": 0x02201000},
            motionKind=kind, motionPhase="MOVING")
        return dict(frame=frame, player=deepcopy(player), actors=[actor], context={"mapId": 33},
            observationBoundary="main-task-queue-completion", fieldAvailable=True,
            selector=dict(heldKeys=key, rawHeld=key, simulatedKeys=0))
    straight = []
    for frame in range(40):
        value = sample(frame, skid[0][1], skid[0][0]["player"], "WALK", 16)
        value["player"].update(x=590, y=402, facing=3, face_x=-32768, face_z=0)
        value["actors"][0]["engineObject"]["facing"] = 3
        value["actors"][0]["motionDuration"] = 3
        straight.append(value)
    turn = [sample(s["frame"], a, s["player"], "SKID", 128) for s, a in skid]
    for frame in (46, 47):
        value = sample(frame, skid[0][1], skid[0][0]["player"], "NONE", 128)
        value["player"].update(x=591, y=402)
        value["actors"][0].update(motionPhase="IDLE", motionElapsed=6, commitSequence=11,
            logical={"x": 591, "y": 402},
            movementPolicy=dict(pending=1, pendingSkid=0, skid=1))
        turn.append(value)
    for frame in range(54, 58):
        value = sample(frame, skid[-1][1], skid[-1][0]["player"], "WALK", 128)
        step = (frame - 54) // 2
        elapsed = (frame - 54) % 2 + 1
        value["actors"][0].update(motionPhase="COMMIT_PENDING" if frame == 55 else "MOVING",
            motionElapsed=elapsed, motionDuration=2 if step == 0 else 3,
            origin={"x": 592, "y": 402 + step}, target={"x": 592, "y": 403 + step},
            commitSequence=12 + step)
        turn.append(value)
    turn.sort(key=lambda value: value["frame"])
    for value in straight + turn:
        actor, player = value["actors"][0], value["player"]
        previous = dict.fromkeys(POSE_KEYS, 0)
        previous["x"] = player["pos_x"] - 8192
        input = dict(x=player["pos_x"], z=player["pos_z"], stamp=value["frame"] + 1,
                     session=1, owner=actor["engineIdentity"]["anchorPointer"],
                     mode=0 if actor["motionKind"] == "NONE" else 1, options=90)
        pose = expected_pose(previous, input)
        player["unk88_y"] += pose["riderY"]
        actor["engineObject"]["unk88_y"] += pose["bodyY"]
        player["face_x"] += pose["leanX"]
        player["face_z"] += pose["leanZ"]
        value["mountedPair"] = dict(playerPointer=input["owner"],
            mountPointer=actor["engineIdentity"]["pointer"],
            player=deepcopy(player), mount=deepcopy(actor["engineObject"]),
            gait=dict(schemaVersion=1, address=STATE_ADDRESS, initialized=1,
                      stamp=input["stamp"], session=input["session"], owner=input["owner"],
                      input=input, previous=previous, pose=pose))
    events = []
    for tile in range(2):
        start, finish, commit = 40 + tile * 8, 46 + tile * 8, 11 + tile
        for name, frame, a, b in (("MOTION_STARTED", start, 4, 6),
            ("LOGICAL_COMMIT", finish, commit, 4), ("MOTION_FINISHED", finish, commit, 4),
            ("CONTROL_RETURNED", finish, 1, commit)):
            events.append(dict(kind="native", frame=frame,
                data=dict(actorHandle=7, event=name, reason="OK", valueA=a, valueB=b)))
    events.append(dict(kind="native", frame=54,
        data=dict(actorHandle=7, event="MOTION_STARTED", reason="OK", valueA=1, valueB=2)))
    return [dict(phase="observe", action=name, completedGameFrames=len(values), samples=values, events=trace)
            for name, values, trace in (("run-right", straight, []), ("turn-down", turn, events))]


class MountedStantlerTurnSkidProofTests(unittest.TestCase):
    def test_all_twelve_skid_frames_face_down_and_travel_east(self):
        self.assertEqual(validate_skid_pose(skid_samples()),
                         ({"x": 590, "y": 402}, {"x": 592, "y": 402}))
        self.assertEqual(contract()["rendered-motion"][0]["name"],
                         "down-facing-east-skid-pair")
        self.assertEqual(contract()["frame-pacing"][0]["name"], "twelve-skid-frames")

    def test_two_exact_lifecycles_and_all_copied_controls(self):
        rows = proof_rows()
        result = run(rows)
        self.assertTrue(result["passed"], result["failures"])
        controls = negative_controls(rows)
        self.assertTrue(controls["passed"], controls)
        self.assertTrue({"old-facing", "short-skid", "missing-second-tile",
                         "missing-commit", "wrong-actor"} <= controls["controls"].keys())
        self.assertEqual(ACTIONS, (("run-right", 40, 16), ("turn-down", 18, 128)))

    def test_full_run_requires_current_gait_and_the_bound_pair(self):
        reasons = {
            "missing-pair": "native mounted pair is missing",
            "missing-gait": "native observation is missing",
            "wrong-gait-owner": "input, state, or owner differs",
            "wrong-gait-pose": "distance and frame reference",
            "wrong-gait-stamp": "input, state, or owner differs",
            "wrong-pair-pointer": "bound to another object",
            "stale-pair": "differs from its completed snapshot",
            "wrong-seat": "rider offsets differ",
            "wrong-height": "rider offsets differ",
        }
        for fault, reason in reasons.items():
            with self.subTest(fault=fault):
                result = run(proof_rows(), fault=fault)
                self.assertTrue(result["faultApplied"])
                self.assertFalse(result["passed"])
                self.assertIn(reason, result["failures"][0])

    def test_full_run_rejects_changed_snapshot_pointer_and_last_walk_time(self):
        rows = proof_rows()
        rows[1]["samples"][3]["actors"][0]["engineIdentity"]["pointer"] ^= 4
        result = run(rows)
        self.assertFalse(result["passed"])
        self.assertIn("Stantler identity differs", result["failures"][0])
        rows = proof_rows()
        rows[0]["samples"][-1]["actors"][0]["motionDuration"] = 4
        result = run(rows)
        self.assertFalse(result["passed"])
        self.assertIn("turn boundary differs", result["failures"][0])

    def test_interim_return_pending_continuation_and_down_start_are_required(self):
        for fault, reason in (
            ("missing-first-return", "exact native CONTROL_RETURNED"),
            ("wrong-gap-state", "interim skid return"),
            ("wrong-gap-commit", "interim skid return"),
            ("missing-down-start", "exact native Down Walk start"),
        ):
            with self.subTest(fault=fault):
                result = run(proof_rows(), fault=fault)
                self.assertTrue(result["faultApplied"])
                self.assertFalse(result["passed"])
                self.assertIn(reason, result["failures"][0])

    def test_one_tile_gap_or_wrong_second_commit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "two six-frame"):
            validate_skid_pose(skid_samples()[:6])
        samples = skid_samples()
        samples[6][0]["frame"] += 1
        with self.assertRaisesRegex(ValueError, "completion gap differ"):
            validate_skid_pose(samples)
        samples = skid_samples()
        samples[6][1]["commitSequence"] -= 1
        with self.assertRaisesRegex(ValueError, "did not face Down"):
            validate_skid_pose(samples)

    def test_old_facing_is_rejected_even_when_pair_offsets_are_coherent(self):
        samples = skid_samples()
        sample, actor = samples[3]
        sample["player"].update(facing=3, face_x=-32768, face_z=0)
        actor["engineObject"]["facing"] = 3
        with self.assertRaisesRegex(ValueError, "did not face Down"):
            validate_skid_pose(samples)

    def test_short_or_wrong_heading_skid_is_rejected(self):
        samples = skid_samples()
        samples[-1][1]["motionDuration"] = 7
        with self.assertRaisesRegex(ValueError, "did not face Down"):
            validate_skid_pose(samples)
        samples = skid_samples()
        samples[0][1]["target"] = {"x": 590, "y": 403}
        with self.assertRaisesRegex(ValueError, "did not face Down"):
            validate_skid_pose(samples)

    def test_old_south_depth_is_rejected(self):
        samples = skid_samples()
        samples[0][0]["player"]["face_z"] = -32768
        with self.assertRaisesRegex(ValueError, "did not stay behind"):
            validate_skid_pose(samples)

    def test_full_tile_gap_is_rejected(self):
        samples = skid_samples()
        samples[0][0]["player"]["face_z"] = -65536
        with self.assertRaisesRegex(ValueError, "did not stay behind"):
            validate_skid_pose(samples)


if __name__ == "__main__":
    unittest.main()
