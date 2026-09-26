"""Focused contracts for PB9 feature-specific live observers."""

from copy import deepcopy
import unittest

from tools.overworld.devtools_profile_feature_measurement import (
    BLOCKED_FACING, BLOCKED_FACING_FRAMES, FLY_IN, FLY_IN_DURATION_FRAMES,
    HELD, PLAYFUL, STALKER, WADDLE,
    ProfileFeatureMeasurement,
)
from tools.overworld.devtools_profile_feature_proof import ProfileFeatureNegative


def fly_motion():
    return {
        "kind": "FLY_IN",
        "handle": {"value": 77},
        "duration": FLY_IN_DURATION_FRAMES,
        "origin": [565, 397],
        "target": [581, 397],
        "terminalLogical": [581, 397],
        "samples": [
            {"elapsed": elapsed, "frame": 100 + elapsed,
             "render": [elapsed, 0, 397]}
            for elapsed in range(2, FLY_IN_DURATION_FRAMES)
        ],
        "travelEnd": {
            "elapsed": FLY_IN_DURATION_FRAMES,
            "frame": 100 + FLY_IN_DURATION_FRAMES,
            "render": [FLY_IN_DURATION_FRAMES, 397],
        },
    }


class FlyInPreparedBoundaryTests(unittest.TestCase):
    def fixture(self):
        meter = ProfileFeatureMeasurement(FLY_IN)
        meter.prepared = [{
            "observation": "spawn-prepared",
            "setupMode": "prepared",
            "startup": {"locomotion": 9, "origin": [565, 397],
                        "target": [581, 397]},
            "publicSubject": {"handle": {"value": 77},
                              "motionKind": "FLY_IN", "motionPhase": "MOVING"},
        }]
        meter.events = [
            {"kind": "native", "frame": 100 + FLY_IN_DURATION_FRAMES,
             "data": {"event": "LOGICAL_COMMIT", "actorHandle": 77}},
            {"kind": "native", "frame": 100 + FLY_IN_DURATION_FRAMES,
             "data": {"event": "CONTROL_RETURNED", "actorHandle": 77}},
        ]
        return meter

    def test_exact_elapsed_two_prepared_boundary_is_complete(self):
        meter = self.fixture()
        motion = fly_motion()
        self.assertTrue(meter._complete_motion(motion))
        meter.motion.completed = [motion]
        meter.motion.failures = [
            {"reason": "missed-motion-start", "elapsed": 2},
            {"reason": "incomplete-travel", "motion": "FLY_IN",
             "duration": FLY_IN_DURATION_FRAMES,
             "elapsed": list(range(2, FLY_IN_DURATION_FRAMES))},
        ]
        meter.subjects = {"pidgey": {"handle": {"value": 77}}}
        self.assertEqual(meter.finish()["failures"], [])

        missing_commit = self.fixture()
        missing_commit.subjects = {"pidgey": {"handle": {"value": 77}}}
        missing_commit.motion.completed = [fly_motion()]
        missing_commit.events = [event for event in missing_commit.events
                                 if event["data"]["event"] != "LOGICAL_COMMIT"]
        self.assertFalse(missing_commit.ready)

    def test_gap_or_unrelated_prepared_motion_cannot_fill_prepared_frames(self):
        meter = self.fixture()
        missing = fly_motion()
        missing["samples"].pop(10)
        self.assertFalse(meter._complete_motion(missing))

        meter.prepared[0]["publicSubject"]["handle"]["value"] = 78
        self.assertFalse(meter._complete_motion(fly_motion()))

        meter = self.fixture()
        wrong_end = deepcopy(fly_motion())
        wrong_end["terminalLogical"] = [581, 398]
        self.assertFalse(meter._complete_motion(wrong_end))


class StalkerStageTests(unittest.TestCase):
    @staticmethod
    def motion(fingerprint, start, origin, target):
        return {
            "kind": "TELEPORT", "duration": 2, "startFrame": start,
            "finishFrame": start + 2, "fingerprint": fingerprint,
            "origin": origin, "target": target,
            "samples": [
                {"elapsed": 1, "frame": start, "render": [1, 0, 0]},
                {"elapsed": 2, "frame": start + 1, "render": [2, 0, 0]},
            ],
            "travelEnd": {"elapsed": 2, "frame": start + 1,
                          "render": [2, 0]},
        }

    def complete_fixture(self):
        meter = ProfileFeatureMeasurement(STALKER)
        meter.subjects = {"gastly": {"handle": {"value": 1}}}
        meter.conditions = [{"active": True, "triggered": True, "frame": 100}]
        meter.motion.completed = [
            self.motion(10, 101, [0, 0], [0, 3]),
            self.motion(20, 130, [0, 3], [1, 3]),
        ]
        meter.samples = [
            {"frame": 101, "logical": [0, 0],
             "player": {"tile": [0, 4]}, "behaviorFingerprint": 10,
             "matchedLayerMask": 8},
            {"frame": 120, "logical": [0, 3],
             "player": {"tile": [0, 4]}, "behaviorFingerprint": 20,
             "matchedLayerMask": 0},
        ]
        return meter

    def test_unseen_stage_needs_active_condition_and_complete_motion(self):
        meter = ProfileFeatureMeasurement(STALKER)
        meter.conditions = [{"active": True, "frame": 100}]
        motion = {
            "kind": "TELEPORT", "duration": 2, "startFrame": 101,
            "origin": [0, 0], "target": [1, 0],
            "samples": [
                {"elapsed": 1, "frame": 101, "render": [1, 0, 0]},
                {"elapsed": 2, "frame": 102, "render": [2, 0, 0]},
            ],
            "travelEnd": {"elapsed": 2, "frame": 102, "render": [2, 0]},
        }
        meter.motion.completed = [motion]
        self.assertTrue(meter.stage("unseen-motion-complete"))
        motion["samples"].pop()
        motion["samples"][0]["elapsed"] = 2
        self.assertFalse(meter.stage("unseen-motion-complete"))

    def test_completion_uses_profile_transition_not_missing_inactive_trace(self):
        self.assertTrue(self.complete_fixture().ready)

    def test_condition_or_same_profile_motion_does_not_prove_seen_routine(self):
        condition_only = self.complete_fixture()
        condition_only.motion.completed.pop()
        self.assertFalse(condition_only.ready)

        same_profile = self.complete_fixture()
        same_profile.motion.completed[1]["fingerprint"] = 10
        self.assertFalse(same_profile.ready)

        no_layer_change = self.complete_fixture()
        no_layer_change.samples[1]["matchedLayerMask"] = 8
        self.assertFalse(no_layer_change.ready)


class PlayfulStageTests(unittest.TestCase):
    @staticmethod
    def complete_motion(start):
        return {
            "kind": "WALK", "duration": 2, "startFrame": start,
            "origin": [0, 0], "target": [1, 0],
            "samples": [
                {"elapsed": 1, "frame": start, "render": [1, 0, 0]},
                {"elapsed": 2, "frame": start + 1, "render": [2, 0, 0]},
            ],
            "travelEnd": {"elapsed": 2, "frame": start + 1,
                          "render": [2, 0]},
        }

    def test_actor_stage_closes_before_the_player_case_starts(self):
        meter = ProfileFeatureMeasurement(PLAYFUL)
        meter.conditions = [{"conditionId": 31250, "triggered": True,
                             "active": True, "frame": 100}]
        meter.motion.completed = [self.complete_motion(101)]
        self.assertTrue(meter.stage("actor-play-complete"))

        meter.conditions.append({"conditionId": 38737, "triggered": True,
                                 "active": True, "frame": 103})
        self.assertFalse(meter.stage("actor-play-complete"))

    def test_actor_stage_needs_its_completed_motion(self):
        meter = ProfileFeatureMeasurement(PLAYFUL)
        meter.conditions = [{"conditionId": 31250, "triggered": True,
                             "active": True, "frame": 100}]
        self.assertFalse(meter.stage("actor-play-complete"))


class HeldStateTests(unittest.TestCase):
    @staticmethod
    def actors(carrier, target, *, carrier_motion="HOP",
               target_motion="NONE"):
        def actor(render, kind, phase):
            return {
                "engineObject": dict(zip(("pos_x", "pos_y", "pos_z"), render)),
                "motionKind": kind,
                "motionPhase": phase,
            }
        return {
            "mankey": actor(carrier, carrier_motion, "MOVING"),
            "rattata": actor(target, target_motion,
                              "IDLE" if target_motion == "NONE" else "MOVING"),
        }

    def test_overlap_does_not_open_held_until_target_moves_with_carrier(self):
        meter = ProfileFeatureMeasurement(HELD)
        meter._observe_held_state({"frame": 10}, self.actors((1, 2, 3), (1, 2, 3)))
        meter._observe_held_state({"frame": 11}, self.actors((1, 2, 3), (1, 2, 3)))
        self.assertIsNone(meter.held_open_frame)

        meter._observe_held_state({"frame": 12}, self.actors((2, 3, 4), (2, 3, 4)))
        self.assertEqual(meter.held_open_frame, 12)

        meter._observe_held_state({"frame": 13}, self.actors((3, 4, 5), (4, 4, 5)))
        self.assertEqual(meter.held_closed_frame, 13)

    def test_throw_start_closes_held_before_render_positions_diverge(self):
        meter = ProfileFeatureMeasurement(HELD)
        meter._observe_held_state({"frame": 20}, self.actors((1, 2, 3), (1, 2, 3)))
        meter._observe_held_state({"frame": 21}, self.actors((2, 3, 4), (2, 3, 4)))
        self.assertEqual(meter.held_open_frame, 21)

        meter._observe_held_state(
            {"frame": 22},
            self.actors((2, 3, 4), (2, 3, 4), target_motion="HOP"),
        )
        self.assertEqual(meter.held_closed_frame, 22)

class WaddleCompletionTests(unittest.TestCase):
    @staticmethod
    def complete_walk():
        return {
            "kind": "WALK", "duration": 2, "startFrame": 100,
            "origin": [0, 0], "target": [1, 0],
            "samples": [
                {"elapsed": 1, "frame": 100, "render": [1, 0, 0]},
                {"elapsed": 2, "frame": 101, "render": [2, 0, 0]},
            ],
            "travelEnd": {"elapsed": 2, "frame": 101,
                          "render": [2, 0]},
        }

    def fixture(self):
        meter = ProfileFeatureMeasurement(WADDLE)
        meter.subjects = {"bellsprout": {"handle": {"value": 1}}}
        meter.motion.completed = [self.complete_walk()]
        meter.events = [
            {"kind": "native", "frame": 101,
             "data": {"event": "LOGICAL_COMMIT", "actorHandle": 1}},
            {"kind": "native", "frame": 102,
             "data": {"event": "CONTROL_RETURNED", "actorHandle": 1}},
        ]
        return meter

    def test_idle_is_the_non_walk_presentation_control(self):
        meter = self.fixture()
        meter.samples = [{"motionKind": "NONE", "motionPhase": "IDLE",
                          "swayOffset": 0}]
        self.assertTrue(meter.ready)
        meter.samples = [{"motionKind": "WALK", "motionPhase": "MOVING",
                          "swayOffset": 4}]
        self.assertFalse(meter.ready)


class BlockedFacingCompletionTests(unittest.TestCase):
    def test_requires_the_full_stable_window(self):
        meter = ProfileFeatureMeasurement(BLOCKED_FACING)
        meter.subjects = {"exeggcute": {"handle": {"value": 1}}}
        meter.samples = [
            {"facing": 1, "logical": [580, 409], "commitSequence": 0}
            for _ in range(BLOCKED_FACING_FRAMES - 1)
        ]
        self.assertFalse(meter.ready)
        meter.samples.append(
            {"facing": 1, "logical": [580, 409], "commitSequence": 0})
        self.assertTrue(meter.ready)

    def test_known_bad_facing_change_uses_the_bound_actor(self):
        control = ProfileFeatureNegative(
            BLOCKED_FACING, BLOCKED_FACING + ":facing-change")
        source = {"samples": [{"actors": [
            {"handle": {"value": 1}, "engineObject": {"facing": 1}},
            {"handle": {"value": 2}, "engineObject": {"facing": 3}},
        ]}], "events": []}
        changed = control.mutate(
            source, {"exeggcute": {"handle": {"value": 1}}})
        self.assertTrue(control.applied)
        self.assertEqual(changed["samples"][0]["actors"][0]["engineObject"]["facing"], 2)
        self.assertEqual(changed["samples"][0]["actors"][1]["engineObject"]["facing"], 3)
        self.assertEqual(source["samples"][0]["actors"][0]["engineObject"]["facing"], 1)

class ProfileFeatureNegativeTests(unittest.TestCase):
    def test_missing_feature_evidence_removes_every_condition_record(self):
        control = ProfileFeatureNegative(
            STALKER, STALKER + ":missing-feature-evidence")
        subjects = {"gastly": {"handle": {"value": 1}}}
        rows = [
            {"events": [{"kind": "native", "data": {
                "event": "CONDITIONAL_RESOLVED", "actorHandle": 1}}]},
            {"events": [{"kind": "native", "data": {
                "event": "CONDITIONAL_RESOLVED", "actorHandle": 1}}]},
        ]

        changed = [control.mutate(row, subjects) for row in rows]

        self.assertTrue(control.applied)
        self.assertEqual(
            [row["events"][0]["data"]["event"] for row in changed],
            ["WORLD_EFFECT", "WORLD_EFFECT"],
        )


if __name__ == "__main__":
    unittest.main()
