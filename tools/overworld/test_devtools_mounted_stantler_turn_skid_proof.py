"""Focused host checks for the mounted Stantler facing/travel split."""

from copy import deepcopy
import unittest

from tools.overworld.devtools_mounted_stantler_turn_skid_proof import (
    contract, validate_skid_pose, run, negative_controls,
)


def skid_samples():
    mount = {key: 0 for key in (
        "pos_x", "pos_y", "pos_z", "face_x", "face_y", "face_z",
        "unk88_x", "unk88_y", "unk94_x", "unk94_y")}
    mount["facing"] = 1
    player = dict(mount, face_y=32768, face_z=-40960)
    return [(
        {"player": deepcopy(player), "frame": 49 + tile * 8 + elapsed - 1},
        {"motionElapsed": elapsed, "motionDuration": 8, "commitSequence": 10 + tile,
         "origin": {"x": 590 + tile, "y": 402},
         "target": {"x": 591 + tile, "y": 402},
         "engineObject": deepcopy(mount)},
    ) for tile in range(2) for elapsed in range(1, 9)]


def proof_rows():
    skid = skid_samples()
    def sample(frame, actor, player, kind, key):
        actor = deepcopy(actor)
        actor.update(active=True, role="MOUNTED", species=234, identityVerified=True,
            presentationAttached=True, inputOwnership=1, handle={"value": 7},
            subjectIdentity=55, logical={"x": 586 if frame == 0 else 590, "y": 402},
            motionKind=kind, motionPhase="MOVING")
        return dict(frame=frame, player=deepcopy(player), actors=[actor], context={"mapId": 33},
            observationBoundary="main-task-queue-completion", fieldAvailable=True,
            selector=dict(heldKeys=key, rawHeld=key, simulatedKeys=0))
    straight = []
    for frame in range(49):
        value = sample(frame, skid[0][1], skid[0][0]["player"], "WALK", 16)
        value["player"].update(x=590, y=402, facing=3, face_x=-32768, face_z=0)
        value["actors"][0]["engineObject"]["facing"] = 3
        value["actors"][0]["motionDuration"] = 4
        straight.append(value)
    turn = [sample(s["frame"], a, s["player"], "SKID", 128) for s, a in skid]
    for frame, kind in ((65, "NONE"), (66, "WALK")):
        value = sample(frame, skid[-1][1], skid[-1][0]["player"], kind, 128)
        value["actors"][0].update(motionPhase="IDLE" if kind == "NONE" else "MOVING",
            motionElapsed=1, target={"x": 592, "y": 403}, commitSequence=12)
        turn.append(value)
    events = []
    for tile in range(2):
        start, finish, commit = 49 + tile * 8, 57 + tile * 8, 11 + tile
        for name, frame, a, b in (("MOTION_STARTED", start, 4, 8),
            ("LOGICAL_COMMIT", finish, commit, 4), ("MOTION_FINISHED", finish, commit, 4),
            ("CONTROL_RETURNED", finish, 1, commit)):
            events.append(dict(kind="native", frame=frame,
                data=dict(actorHandle=7, event=name, reason="OK", valueA=a, valueB=b)))
    return [dict(phase="observe", action=name, completedGameFrames=len(values), samples=values, events=trace)
            for name, values, trace in (("run-right", straight, []), ("turn-down", turn, events))]


class MountedStantlerTurnSkidProofTests(unittest.TestCase):
    def test_all_sixteen_skid_frames_face_down_and_travel_east(self):
        self.assertEqual(validate_skid_pose(skid_samples()),
                         ({"x": 590, "y": 402}, {"x": 592, "y": 402}))
        self.assertEqual(contract()["rendered-motion"][0]["name"],
                         "down-facing-east-skid-pair")

    def test_two_exact_lifecycles_and_all_copied_controls(self):
        rows = proof_rows()
        result = run(rows)
        self.assertTrue(result["passed"], result["failures"])
        self.assertTrue(negative_controls(rows)["passed"])

    def test_one_tile_gap_or_wrong_second_commit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "two eight-frame"):
            validate_skid_pose(skid_samples()[:8])
        samples = skid_samples()
        samples[8][0]["frame"] += 1
        with self.assertRaisesRegex(ValueError, "not continuous"):
            validate_skid_pose(samples)
        samples = skid_samples()
        samples[8][1]["commitSequence"] -= 1
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
