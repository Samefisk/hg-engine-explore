"""Host controls for the two-tile Wild stop and turn contracts; no game run."""
from copy import deepcopy
import unittest

from tools.overworld.devtools_runner_stop_skid_measurement import (
    RunnerStopSkidMeasurement, same_public_subject,
)
from tools.overworld.devtools_runner_stop_skid_proof import _check_tile
from tools.overworld.devtools_runner_turn_runway_measurement import RunnerTurnRunwayMeasurement, recovery_time


ACTOR = dict(handle=dict(value=1, encounterGeneration=2), behaviorFingerprint=42, subjectIdentity=99)


def motion(origin, delta, duration, start, commit):
    target = [a + b for a, b in zip(origin, delta)]
    render = lambda elapsed: [(origin[0] << 16) + 32768 + delta[0] * 65536 * elapsed // duration,
                              0, (origin[1] << 16) + 32768 + delta[1] * 65536 * elapsed // duration]
    return dict(kind="WALK", duration=duration, origin=origin, target=target,
                handle=ACTOR["handle"], fingerprint=42, startFrame=start,
                commitBefore=commit, commitAfter=commit + 1, commitFrame=start + duration,
                finishFrame=start + duration + 1, terminalLogical=target,
                samples=[dict(elapsed=i, frame=start + i, render=render(i)) for i in range(duration)],
                travelEnd=dict(elapsed=duration, frame=start + duration,
                               render=[render(duration)[0], render(duration)[2]]))


def traces(motions):
    result = []
    for value in motions:
        for name, frame, a, b in (
            ("MOTION_STARTED", value["startFrame"], 1, value["duration"]),
            ("LOGICAL_COMMIT", value["commitFrame"], value["commitAfter"], 1),
            ("MOTION_FINISHED", value["finishFrame"], value["commitAfter"], 1),
            ("CONTROL_RETURNED", value["finishFrame"], 0, value["commitAfter"]),
        ):
            result.append(dict(frame=frame, data=dict(event=name, valueA=a, valueB=b,
                                                       reason="OK", sequence=len(result) + 1)))
    return result


def stop_meter():
    meter = RunnerStopSkidMeasurement()
    meter.motions = [motion([10, 10], [1, 0], 8, 10, 20), motion([11, 10], [1, 0], 8, 20, 21)]
    meter.motion = meter.motions[-1]
    meter.continuation, meter.continuation_frame, meter.policy_frame = {}, 20, 10
    call = bytearray(28)
    call[0:4] = bytes((1, 0, 28, 0))
    call[17] = 3
    meter.policy_input = dict(responseHex=call.hex())
    meter.traces = traces(meter.motions)
    actor = dict(logical=dict(x=12, y=10), motionKind="NONE", motionPhase="IDLE", reservationId=0)
    return meter, actor


def turn_meter():
    meter = RunnerTurnRunwayMeasurement()
    meter.actor = deepcopy(ACTOR)
    meter.old_direction, meter.turn_direction = 3, 1
    meter.policy_frame, meter.continuation_frame = 10, 20
    meter.motions = [motion([10, 10], [1, 0], 8, 10, 20),
                    motion([11, 10], [1, 0], 8, 20, 21),
                    motion([12, 10], [0, 1], recovery_time(ACTOR, 22), 30, 22)]
    meter.traces = traces(meter.motions)
    return meter, dict(logical=dict(x=12, y=11))


class RunnerSkidSequenceTests(unittest.TestCase):
    def test_stop_keeps_actor_identity_across_normal_profile_change(self):
        actor = {**ACTOR, "species": 234, "role": "WILD",
                 "authorityGeneration": 1, "engineAnchorGeneration": 1,
                 "presentationGeneration": 1, "matchedLayerMask": 1026}
        changed = {**actor, "behaviorFingerprint": 1764908773,
                   "matchedLayerMask": 17410}
        self.assertTrue(same_public_subject(changed, actor))
        changed["authorityGeneration"] = 2
        self.assertFalse(same_public_subject(changed, actor))

    def test_stop_requires_both_full_tiles_and_each_lifecycle(self):
        meter, actor = stop_meter()
        meter._check_motion(actor)
        for value in meter.motions:
            _check_tile(value, ACTOR, 42, meter.traces, 3)
        for index in range(2):
            broken, actor = stop_meter()
            broken.traces = [row for row in broken.traces
                             if not (row["frame"] == broken.motions[index]["finishFrame"]
                                     and row["data"]["event"] == "CONTROL_RETURNED")]
            with self.assertRaisesRegex(ValueError, "CONTROL_RETURNED"):
                broken._check_motion(actor)
            with self.assertRaisesRegex(ValueError, "CONTROL_RETURNED"):
                _check_tile(broken.motions[index], ACTOR, 42, broken.traces, 3)

    def test_stop_rejects_old_one_tile_and_wrong_second_tile(self):
        for change in ("one", "direction", "commit", "sample"):
            meter, actor = stop_meter()
            if change == "one": meter.motions.pop()
            elif change == "direction": meter.motions[1]["target"] = [11, 11]
            elif change == "commit": meter.motions[1]["commitBefore"] += 1
            else: meter.motions[1]["samples"].pop(3)
            with self.assertRaises(ValueError): meter._check_motion(actor)

    def test_turn_requires_two_skids_and_exact_keyed_recovery(self):
        meter, actor = turn_meter()
        meter._check_motions(actor)
        self.assertEqual(len(meter.lifecycle), 12)
        for change in ("old-pair", "direction", "recovery-time", "control"):
            meter, actor = turn_meter()
            if change == "old-pair": meter.motions.pop(1)
            elif change == "direction": meter.motions[1]["target"] = [11, 11]
            elif change == "recovery-time": meter.motions[-1]["duration"] += 1
            else: meter.traces.pop(7)
            with self.assertRaises(ValueError): meter._check_motions(actor)

    def test_recovery_draw_uses_commit_and_identity(self):
        # Fixed vectors are independent of the checker implementation.
        self.assertEqual([recovery_time(ACTOR, commit) for commit in (20, 21, 22, 23)], [7, 5, 5, 6])


if __name__ == "__main__":
    unittest.main()
