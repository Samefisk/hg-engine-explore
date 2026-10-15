"""Soak claim boundaries; native lifetime facts remain the meter's duty."""
from copy import deepcopy
import unittest

from tools.overworld.devtools_wild_throw_soak_measurement import KIND, GEODUDES, SOAK_FRAMES
from tools.overworld.devtools_wild_throw_soak_proof import measurements


def proof_result():
    handles = [dict(value=65537+i, slot=1+i, generation=1, fieldEpoch=3,
                    mapGeneration=3, encounterGeneration=1) for i in range(3)]
    subjects = {name: dict(handle=handle) for name, handle in zip(GEODUDES, handles)}
    def cycle(carrier, cargo, start):
        return dict(carrier=carrier, cargo=cargo, credited=True, claim=start,
                    pickup=start+1, launch=start+2, landed=start+14, cleanup=start+20,
                    motion=dict(handle=cargo, commit=dict(frame=start+14), returnFrame=start+14))
    result = dict(passed=True, ready=True, failures=[], acceptedProof=False,
                  observedFrames=SOAK_FRAMES, observedFrameUnit="completed-game-frame",
                  soakFrames=SOAK_FRAMES, windowStart=100, windowEnd=100+SOAK_FRAMES-1,
                  interests=dict.fromkeys(GEODUDES, 1), queries=dict.fromkeys(GEODUDES, 1),
                  motionReturns=dict.fromkeys(GEODUDES, 1), queryCount=3, subjects=subjects,
                  completedThrows=[cycle(handles[1], handles[0], 110), cycle(handles[0], handles[2], 4000)],
                  recoveryPickups=[dict(frame=125)], ownershipCurrent=True,
                  playerBefore=dict(hp=100), playerAfter=dict(hp=100),
                  playerCheckpoints=[dict(leg=leg, soakFrames=leg*24,
                      playerHealth=dict(frame=100+leg*24-1, hp=100, savedHp=100, recoveryPending=False))
                      for leg in (40, 80, 120, 160, 200)],
                  survivors=[GEODUDES[0], GEODUDES[2]],
                  primaryCurrentFrames=dict(zip(GEODUDES, (SOAK_FRAMES, 2900, SOAK_FRAMES))),
                  primaryHealthyFrames=dict(zip(GEODUDES, (SOAK_FRAMES, 2900, SOAK_FRAMES))),
                  primaryRetirements={GEODUDES[1]: dict(handle=handles[1], hitFrame=3000,
                                                        frame=3001, detach=dict(frame=3002))})
    replay = dict(passed=True, failures=[], observedFrames=SOAK_FRAMES, measurements={KIND: result})
    record = dict(sessionId="unit-session", sessionCleanup=dict(sessionId="unit-session", closed=True, errors=[]))
    return replay, record


class SoakLifetimeClaimTests(unittest.TestCase):
    def test_two_continuous_survivors_and_completed_retirement(self):
        replay, record = proof_result()
        self.assertEqual(len(measurements(replay, record)), 5)

    def test_three_survivors_need_no_faint(self):
        replay, record = proof_result(); result = replay["measurements"][KIND]
        result.update(survivors=list(GEODUDES), primaryRetirements={},
                      primaryCurrentFrames=dict.fromkeys(GEODUDES, SOAK_FRAMES),
                      primaryHealthyFrames=dict.fromkeys(GEODUDES, SOAK_FRAMES))
        self.assertEqual(len(measurements(replay, record)), 5)

    def test_missing_stale_dead_or_changed_checkpoint_rejects(self):
        for fault in ("missing", "wrong-leg", "wrong-count", "stale-frame", "zero-hp", "saved-hp", "recovering"):
            replay, record = proof_result(); checkpoints = replay["measurements"][KIND]["playerCheckpoints"]
            if fault == "missing": checkpoints.pop()
            elif fault == "wrong-leg": checkpoints[0]["leg"] += 1
            elif fault == "wrong-count": checkpoints[0]["soakFrames"] -= 1
            elif fault == "stale-frame": checkpoints[0]["playerHealth"]["frame"] -= 1
            elif fault == "zero-hp": checkpoints[0]["playerHealth"].update(hp=0, savedHp=0)
            elif fault == "saved-hp": checkpoints[0]["playerHealth"]["savedHp"] -= 1
            else: checkpoints[0]["playerHealth"]["recoveryPending"] = True
            with self.subTest(fault=fault), self.assertRaises(ValueError): measurements(replay, record)

    def test_short_missing_unhealthy_and_wrong_lifetime_proof_reject(self):
        for fault in ("one-survivor", "short-current", "short-healthy", "retired-survivor",
                      "missing-detach", "wrong-owner", "future-retirement", "retired-frame-credit"):
            replay, record = proof_result(); result = replay["measurements"][KIND]
            lifetime = result["primaryRetirements"][GEODUDES[1]]
            if fault == "one-survivor": result["survivors"] = result["survivors"][:1]
            elif fault == "short-current": result["primaryCurrentFrames"][GEODUDES[0]] -= 1
            elif fault == "short-healthy": result["primaryHealthyFrames"][GEODUDES[0]] -= 1
            elif fault == "retired-survivor": result["survivors"] = list(GEODUDES)
            elif fault == "missing-detach": lifetime["detach"] = None
            elif fault == "wrong-owner": lifetime["handle"] = deepcopy(lifetime["handle"]); lifetime["handle"]["generation"] += 1
            elif fault == "future-retirement": lifetime["frame"] = result["windowEnd"]+1
            else: result["primaryHealthyFrames"][GEODUDES[1]] = result["primaryCurrentFrames"][GEODUDES[1]] = SOAK_FRAMES
            with self.subTest(fault=fault), self.assertRaises(ValueError): measurements(replay, record)

    def test_carrier_or_cargo_faint_frame_cannot_complete_a_credited_throw(self):
        for role in ("carrier", "cargo"):
            replay, record = proof_result(); result = replay["measurements"][KIND]
            cycle = result["completedThrows"][0]; lifetime = result["primaryRetirements"][GEODUDES[1]]
            if role == "cargo":
                cycle["cargo"] = deepcopy(lifetime["handle"])
                cycle["motion"]["handle"] = deepcopy(lifetime["handle"])
                cycle["carrier"] = result["subjects"][GEODUDES[0]]["handle"]
            cycle["cleanup"] = lifetime["hitFrame"]
            with self.subTest(role=role), self.assertRaises(ValueError): measurements(replay, record)


if __name__ == "__main__":
    unittest.main()
