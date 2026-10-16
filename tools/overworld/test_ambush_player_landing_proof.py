"""Host checks for exact Wild Ambush landing and shared overlap recovery."""

from copy import deepcopy
import unittest

from tools.overworld.devtools_profile_feature_measurement import (
    AMBUSH, FEATURES, ProfileFeatureMeasurement,
)
from tools.overworld.devtools_profile_feature_proof import (
    ProfileFeatureNegative, faults, measurements, values,
)


HANDLE = {"value": 131072, "slot": 0, "generation": 2,
          "fieldEpoch": 3, "mapGeneration": 3, "encounterGeneration": 1}
SUBJECT = {"handle": HANDLE, "subjectIdentity": 77, "species": 70, "role": "WILD",
           "authorityGeneration": 2, "engineAnchorGeneration": 2, "presentationGeneration": 2}
APPLICATION = FEATURES[AMBUSH]["application"]
PLAYER = [585, 408]


def event(frame, sequence, name):
    return {"frame": frame, "kind": "native", "data": {
        "actorHandle": HANDLE["value"], "actor": {k: v for k, v in HANDLE.items() if k != "value"},
        "sequence": sequence, "event": name}}


def observer():
    origin = [584, 407]
    center = lambda tile: [(tile[0] << 16) + 0x8000,
                           (tile[1] << 16) + 0x8000]
    x0, z0 = center(origin)
    x1, z1 = center(PLAYER)
    hop = {
        "kind": "HOP", "handle": HANDLE, "origin": origin,
        "target": PLAYER[:], "terminalLogical": PLAYER[:],
        "startFrame": 10, "finishFrame": 16, "duration": 6,
        "fingerprint": 777, "commitBefore": 1, "commitAfter": 2,
        "terminalRender": [x1, 65536, z1],
        "travelEnd": {"frame": 16, "elapsed": 6, "render": [x1, z1]},
        "samples": [{"frame": 10 + tick, "elapsed": tick,
                     "render": [x0 + (x1 - x0) * tick // 6, 65536,
                                z0 + (z1 - z0) * tick // 6]}
                    for tick in range(6)],
    }
    meter = ProfileFeatureMeasurement(AMBUSH)
    meter.subjects = {"weepinbell": deepcopy(SUBJECT)}
    meter.subject = meter.subjects["weepinbell"]
    meter.initial = {"frame": 9}
    meter.terminal = {"actors": [{"handle": HANDLE, "role": "WILD",
                                  "species": 70, "identityVerified": True,
                                  "presentationAttached": True}]}
    meter.motion.completed = [hop]
    meter.conditions = [{"frame": 10, "application": APPLICATION,
                         "targetSourceApplication": APPLICATION,
                         "conditionId": 49529, "targetKind": 1,
                         "triggered": True, "active": True, "timed": True}]
    meter.samples = [{"frame": 10, "behaviorFingerprint": 777,
                      "matchedLayerMask": 1 << APPLICATION,
                      "player": {"tile": PLAYER[:]}}]
    meter.events = [event(10, 1, "INTENT_CREATED"),
                    event(10, 2, "MOTION_STARTED"),
                    event(16, 3, "LOGICAL_COMMIT"),
                    event(16, 4, "MOTION_FINISHED"),
                    event(16, 5, "CONTROL_RETURNED")]
    # Six settled overlap rows, then the native UP exit owns eight rendered
    # travel steps. Actor commit stays unchanged until its next profile Hop.
    for frame in range(16, 31):
        progress = max(0, frame - 22) * 8192
        tile = PLAYER[:] if frame <= 22 else [585, 407]
        row = {"frame": frame, "owner": deepcopy(SUBJECT),
               "context": {"fieldEpoch": 3, "mapGeneration": 3, "mapId": 33},
               "logical": tile, "origin": tile[:], "target": tile[:],
               "motionKind": "NONE", "motionPhase": "IDLE", "elapsed": 0,
               "duration": 0, "reservationId": 0, "commitSequence": 2,
               "behaviorFingerprint": 777, "matchedLayerMask": 1 << APPLICATION,
               "profileCurrent": True,
               "render": [x1, 65536, z1 - progress], "offsetY": 0,
               "player": {"tile": PLAYER[:], "render": [x1, 65536, z1], "offsetY": 0},
               "otherActorTiles": [], "native": {"command": 255, "flags": 1}}
        if 22 <= frame < 30:
            row["native"] = {"command": 52, "flags": 3}
        if frame == 30:
            row.update(motionKind="HOP", motionPhase="MOVING", duration=6,
                       origin=[585, 407], target=PLAYER[:])
        meter.samples.append(row)
    meter.events.extend([event(30, 6, "INTENT_CREATED"), event(30, 7, "MOTION_STARTED")])
    return meter


def raw_sample(row):
    actor = {**deepcopy(row["owner"]), "active": True,
             "identityVerified": True, "presentationAttached": True,
             "logical": dict(zip(("x", "y"), row["logical"])),
             "origin": dict(zip(("x", "y"), row["origin"])),
             "target": dict(zip(("x", "y"), row["target"])),
             "motionKind": row["motionKind"], "motionPhase": row["motionPhase"],
             "motionElapsed": row["elapsed"], "motionDuration": row["duration"],
             "reservationId": row["reservationId"], "commitSequence": row["commitSequence"],
             "behaviorFingerprint": row["behaviorFingerprint"],
             "matchedLayerMask": row["matchedLayerMask"],
             "engineObject": {"pos_x": row["render"][0], "pos_y": row["render"][1],
                              "pos_z": row["render"][2], "unk88_y": row["offsetY"],
                              "facing": 0, "movement_cmd": row["native"]["command"],
                              "flags": row["native"]["flags"]}}
    return {"frame": row["frame"], "context": row["context"], "actors": [actor],
            "nativeObservation": {"coverageComplete": True, "profilesEvicted": 0,
                                  "profileFingerprints": [row["behaviorFingerprint"]]},
            "player": {"x": row["player"]["tile"][0], "y": row["player"]["tile"][1],
                       "pos_x": row["player"]["render"][0], "pos_y": row["player"]["render"][1],
                       "pos_z": row["player"]["render"][2], "unk88_y": row["player"]["offsetY"],
                       "facing": 0}}


class AmbushPlayerLandingProofTests(unittest.TestCase):
    def test_exact_hop_with_active_ambush_commits_and_returns_control(self):
        meter = observer()
        self.assertTrue(meter.ready)
        result = meter.result()
        self.assertEqual(values(AMBUSH, result)["ambush-exact-player-tile-commit"],
                         [1, *PLAYER])
        rows = measurements(AMBUSH,
                            {"passed": True, "failures": [],
                             "measurements": {AMBUSH: result}},
                            {"sessionId": "copied", "sessionCleanup": {
                                "sessionId": "copied", "closed": True,
                                "errors": []}})
        self.assertEqual(len(rows), 7)

    def test_near_miss_and_missing_lifecycle_cannot_complete(self):
        for name in ("target", "condition", "commit", "control", "layer"):
            with self.subTest(missing=name):
                meter = observer()
                if name == "target":
                    hop = meter.motion.completed[0]
                    hop["target"] = hop["terminalLogical"] = [585, 407]
                elif name == "condition":
                    meter.conditions.clear()
                elif name == "commit":
                    meter.events = [row for row in meter.events
                                    if row["data"]["event"] != "LOGICAL_COMMIT"]
                elif name == "control":
                    meter.events = [row for row in meter.events
                                    if row["data"]["event"] != "CONTROL_RETURNED"]
                else:
                    meter.samples[0]["matchedLayerMask"] = 0
                self.assertFalse(meter.ready)

    def test_missing_wrong_actor_and_blocked_exit_do_not_complete(self):
        for fault in ("missing-exit", "wrong-actor", "blocked-exit", "missing-next-start",
                      "wrong-height", "gap", "occupied", "canceled", "stale-event", "missing-profile"):
            with self.subTest(fault=fault):
                meter = observer()
                if fault == "missing-exit":
                    meter.samples = [row for row in meter.samples if row["frame"] < 22]
                elif fault == "wrong-actor":
                    meter.samples[7]["owner"]["handle"]["encounterGeneration"] = 2
                elif fault == "blocked-exit":
                    meter.samples[7]["native"]["flags"] &= ~2
                elif fault == "missing-next-start":
                    meter.events.pop()
                elif fault == "wrong-height":
                    meter.samples[6]["player"]["render"][1] += 1
                elif fault == "gap":
                    meter.samples = [row for row in meter.samples if row["frame"] != 24]
                elif fault == "occupied":
                    meter.samples[7]["otherActorTiles"] = [[585, 407]]
                elif fault == "canceled":
                    meter.events.append(event(25, 8, "MOTION_CANCELED"))
                elif fault == "stale-event":
                    meter.events[-1]["data"]["actor"]["fieldEpoch"] = 2
                else:
                    meter.samples[-1]["profileCurrent"] = False
                self.assertFalse(meter.ready)
                copied = meter.result()
                copied.update(passed=True, ready=True, closed=True)
                with self.assertRaisesRegex(ValueError, "same-actor legal shared exit"):
                    values(AMBUSH, copied)

    def test_exit_samples_use_current_actor_not_player_knockback(self):
        meter = observer()
        rows = deepcopy(meter.samples[1:])
        meter.samples = [deepcopy(meter.samples[0])]
        # These are native exits, so the Actor motion recorder has no open Hop.
        meter.motion.current = None
        for row in rows:
            snapshot = raw_sample(row)
            actors = meter._actors(snapshot)
            meter._sample(snapshot, actors)
        self.assertTrue(meter.ready)
        # Retain an actual Player displacement, while the actor stays at its
        # overlap center. That alone cannot stand in for the native exit.
        for row in meter.samples:
            row["render"] = [(585 << 16) + 0x8000, 65536, (408 << 16) + 0x8000]
        self.assertFalse(meter.ready)

    def test_exit_faults_wait_for_bound_subject_without_consuming_the_fault(self):
        meter = observer()
        row = {"samples": [raw_sample(item) for item in meter.samples[1:]], "events": []}
        original = deepcopy(row)
        for suffix in ("missing-exit", "wrong-exit-actor", "blocked-exit"):
            with self.subTest(fault=suffix):
                fault = ProfileFeatureNegative(AMBUSH, AMBUSH + ":" + suffix)
                for unbound in ({}, {"weepinbell": {}}, {"weepinbell": {"handle": {"value": 131072}}}):
                    self.assertIs(fault.mutate(row, unbound), row)
                    self.assertFalse(fault.applied)
                    self.assertEqual(row, original)
                changed = fault.mutate(row, {"weepinbell": deepcopy(SUBJECT)})
                self.assertTrue(fault.applied)
                self.assertNotEqual(changed, original)
                self.assertEqual(row, original)

    def test_all_registered_copied_faults_change_only_the_copy(self):
        meter = observer()
        source = {"samples": [raw_sample(row) for row in meter.samples[1:]],
                  "events": [event(10, 1, "CONDITIONAL_RESOLVED"),
                             event(16, 3, "LOGICAL_COMMIT"),
                             event(16, 5, "CONTROL_RETURNED")]}
        original = deepcopy(source)
        subjects = {"weepinbell": deepcopy(SUBJECT)}
        for name in faults(AMBUSH):
            with self.subTest(fault=name):
                fault = ProfileFeatureNegative(AMBUSH, name)
                changed = fault.mutate(source, subjects)
                self.assertTrue(fault.applied)
                self.assertNotEqual(changed, original)
                self.assertEqual(source, original)


if __name__ == "__main__":
    unittest.main()
