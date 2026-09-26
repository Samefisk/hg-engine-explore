from copy import deepcopy
import unittest

from tools.overworld.devtools_mount_detach_follower_resume import (
    MountDetachFollowerResumeMeasurement,
)
from tools.overworld.test_devtools_mount_control_stress import StressFixture


class DetachResumeFixture(StressFixture):
    def __init__(self):
        super().__init__("legacy.cyndaquil-control-stress")

    def detach(self):
        actor = self.actor
        actor.update(role="FOLLOWER", inputOwnership=0,
                     behaviorFingerprint=actor["behaviorFingerprint"] + 1,
                     matchedLayerMask=actor["matchedLayerMask"] ^ 3,
                     authorityGeneration=actor["authorityGeneration"] + 1,
                     engineAnchorGeneration=actor["engineAnchorGeneration"] + 1,
                     reservationId=0)
        yield self.frame((
            ("ACTOR_REBOUND", 3, 2),
            ("CONTROL_REBOUND", 1, 0),
        ), select=True)

    def separate_and_walk(self, successor_same_frame=False):
        actor = self.actor
        origin = [actor["logical"]["x"], actor["logical"]["y"]]
        target = [origin[0], origin[1] + 1]
        before = actor["commitSequence"]
        self.xy[0] += 2
        for elapsed in range(1, 4):
            actor.update(
                origin={"x": origin[0], "y": origin[1]},
                target={"x": target[0], "y": target[1]},
                logical={"x": target[0] if elapsed == 3 else origin[0],
                         "y": target[1] if elapsed == 3 else origin[1]},
                motionKind="WALK", motionKindId=1, motionPhase="MOVING",
                motionElapsed=elapsed, motionDuration=3,
                reservationId=before + 1,
            )
            if elapsed == 3:
                actor["commitSequence"] = before + 1
            self.pose()
            actor["engineObject"]["pos_x"] = (origin[0] << 16) + 32768
            actor["engineObject"]["pos_z"] = ((origin[1] << 16) + 32768
                                                 + 65536 * elapsed // 3)
            events = []
            if elapsed == 1:
                events.extend((
                    ("INTENT_CREATED", 1, 0),
                    ("PLAN_ACCEPTED", 1, 0),
                    ("MOTION_STARTED", 1, 3),
                ))
            if elapsed == 3:
                events.append(("LOGICAL_COMMIT", before + 1, 1))
            yield self.frame(events)
        actor.update(motionKind="NONE", motionKindId=0, motionPhase="IDLE",
                     motionElapsed=0, motionDuration=0, reservationId=0)
        self.pose()
        actor["engineObject"]["pos_x"] = (target[0] << 16) + 32768
        actor["engineObject"]["pos_z"] = (target[1] << 16) + 32768
        terminal_events = [
            ("MOTION_FINISHED", before + 1, 1),
            ("CONTROL_RETURNED", 0, before + 1),
        ]
        if successor_same_frame:
            terminal_events.extend((
                ("INTENT_CREATED", 1, 1),
                ("PLAN_ACCEPTED", before + 2, 3),
                ("MOTION_STARTED", 1, 3),
            ))
        yield self.frame(terminal_events)

    def delayed_idle(self, frames=4):
        self.xy[0] += 2
        for _ in range(frames):
            self.pose()
            yield self.frame()


def completed_meter():
    fixture = DetachResumeFixture()
    meter = MountDetachFollowerResumeMeasurement()
    meter.arm(fixture.subject, fixture.snapshot)
    for snapshot, events in (*fixture.detach(), *fixture.separate_and_walk()):
        meter.observe(snapshot, events)
    return meter.finish(), fixture


class MountDetachFollowerResumeTests(unittest.TestCase):
    def test_same_actor_rebounds_and_finishes_prompt_follower_walk(self):
        result, _ = completed_meter()
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["motion"]["kind"], "WALK")
        self.assertLessEqual(
            max(0, result["motionStartFrame"] - result["clearanceFrame"]), 1)
        self.assertEqual(result["terminal"]["actors"][0]["inputOwnership"], 0)

    def test_old_ff_cooldown_shape_fails_the_resume_bound(self):
        fixture = DetachResumeFixture()
        meter = MountDetachFollowerResumeMeasurement()
        meter.arm(fixture.subject, fixture.snapshot)
        for snapshot, events in fixture.detach():
            meter.observe(snapshot, events)
        for snapshot, events in fixture.delayed_idle():
            meter.observe(snapshot, events)
        result = meter.finish()
        self.assertFalse(result["passed"])
        self.assertIn("follower resume latency exceeded", result["failures"])

    def test_successor_start_on_terminal_frame_is_not_part_of_first_walk(self):
        fixture = DetachResumeFixture()
        meter = MountDetachFollowerResumeMeasurement()
        meter.arm(fixture.subject, fixture.snapshot)
        for snapshot, events in (
                *fixture.detach(), *fixture.separate_and_walk(successor_same_frame=True)):
            meter.observe(snapshot, events)
        result = meter.finish()
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(
            [event["data"]["event"] for event in result["motionEvents"]].count(
                "MOTION_STARTED"),
            1,
        )

    def test_missing_detach_receipts_and_wrong_terminal_control_fail(self):
        for fault in ("ACTOR_REBOUND", "CONTROL_REBOUND", "CONTROL_RETURNED"):
            with self.subTest(fault=fault):
                fixture = DetachResumeFixture()
                meter = MountDetachFollowerResumeMeasurement()
                meter.arm(fixture.subject, fixture.snapshot)
                rows = [*fixture.detach(), *fixture.separate_and_walk()]
                for snapshot, events in rows:
                    copied = deepcopy(events)
                    for event in copied:
                        if event["data"]["event"] == fault:
                            if fault == "CONTROL_RETURNED":
                                event["data"]["valueA"] = 1
                            else:
                                event["data"]["event"] = "WORLD_EFFECT"
                    meter.observe(snapshot, copied)
                self.assertFalse(meter.finish()["passed"])


if __name__ == "__main__":
    unittest.main()
