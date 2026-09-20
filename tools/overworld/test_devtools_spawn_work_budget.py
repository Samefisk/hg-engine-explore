import unittest

from tools.overworld.devtools_spawn_work_budget_measurement import (
    EXPECTED_DESTINATION_UPDATES,
    KIND,
    MAX_CANDIDATE_QUERIES_PER_UPDATE,
    SpawnWorkBudgetMeasurement,
)
from tools.overworld.devtools_spawn_work_budget_proof import (
    FAULTS,
    SpawnWorkBudgetNegative,
    measurements,
    validate_negative_result,
)
from tools.overworld.devtools_main_loop_probe import (
    NORMAL_MAIN_LOOP_ARM9_TICKS,
    NORMAL_MAIN_LOOP_NATIVE_CYCLES,
    RETURN_SITE,
    SCOPE,
)


SOURCE_HASH = "a" * 64
HANDLE = {"value": "0x00010001", "slot": 1, "generation": 1}
SPAWN_HANDLE = {"value": 0x00010002, "slot": 2, "generation": 1}
SUBJECT = {
    "id": "mankey", "species": 56, "role": "FOLLOWER",
    "handle": HANDLE, "subjectIdentity": 9876, "identityVerified": True,
}
WORLD = {
    "fieldPointer": 0x02231000,
    "statePointer": 0x023DEF48,
    "mapId": 67,
    "fieldEpoch": 3,
    "mapGeneration": 3,
}
INITIAL_CONTEXT = {"mapId": 33, "fieldEpoch": 2, "mapGeneration": 2}
ENCOUNTER = {"species": 163, "form": 0, "level": 3, "personality": 12345}
RESUMED_QUERY_COUNTS = (12,) + (10,) * 8 + (9,) * 11


def recipe():
    return {
        "mode": "normal",
        "fixture": {"rom": "test.nds", "save": "test.sav"},
        "subjects": [{
            "id": "mankey", "species": 56,
            "role": "FOLLOWER", "acquire": "existing",
        }],
    }


def snapshot(index):
    frame = 100 + index
    x = 585 if index == 0 else 574 + index
    y = 406 if index == 0 else 398
    actors = [{
        "handle": HANDLE,
        "subjectIdentity": SUBJECT["subjectIdentity"],
        "active": True,
        "species": 56,
        "role": "FOLLOWER",
        "identityVerified": True,
    }]
    if index >= EXPECTED_DESTINATION_UPDATES + 1:
        stage = index - (EXPECTED_DESTINATION_UPDATES + 1)
        actor_y = [382, 383, 384, 385, 386, 387][min(stage, 5)]
        actors.append({
            "handle": SPAWN_HANDLE,
            "subjectIdentity": ENCOUNTER["personality"],
            "active": True,
            "species": ENCOUNTER["species"],
            "role": "WILD",
            "identityVerified": True,
            "logical": {"x": 596, "y": actor_y},
            "render": {"x": 596, "y": actor_y},
            "lane": "OWNER",
            "motionKind": "HOP",
        })
    return {
        "frame": frame,
        "nativeCycle": 1000 + index,
        "actorFrame": 200 if index <= 1 else 199 + index,
        "context": INITIAL_CONTEXT if index == 0 else {
            key: WORLD[key] for key in ("mapId", "fieldEpoch", "mapGeneration")},
        "player": {"x": x, "y": y, "x_prev": x if index == 0 else x - 1,
                   "y_prev": y, "pos_x": (x << 16) + 32768,
                   "pos_z": (y << 16) + 32768, "movement_cmd": 91,
                   "movement_step": 1},
        "observationBoundary": "main-task-queue-completion",
        "fieldAvailable": True,
        "fieldControl": {"taskPointer": 0},
        "nativeObservation": {
            "sequence": 10 + index,
            "coverageComplete": True,
            "error": None,
            "eventsDropped": 0,
        },
        "actors": actors,
    }


def events(index):
    rows = []
    if index >= 1:
        rows.append({"kind": "native-observation", "data": {
            "observation": "stock-main-loop-pacing",
            "setupMode": "normal",
            "returnSite": RETURN_SITE,
            "scope": SCOPE,
            "diagnosticOnly": False,
            "acceptedProof": False,
            "afterQueueFrame": 100 + index,
            "flushedAtQueueFrame": 101 + index,
            "frameCounter": 2,
            "intervalFromPrevious": None if index == 1 else {
                "arm9Ticks": NORMAL_MAIN_LOOP_ARM9_TICKS,
                "arm7Ticks": NORMAL_MAIN_LOOP_ARM9_TICKS // 2,
                "frameSequence": NORMAL_MAIN_LOOP_NATIVE_CYCLES,
                "actorFrames": 1,
                "nativeCycles": NORMAL_MAIN_LOOP_NATIVE_CYCLES,
            },
        }})
    if index == EXPECTED_DESTINATION_UPDATES:
        finalization_id = 1000 + index
        rows.extend([{"kind": "native-observation", "data": {
            "observation": "spawn-finalized",
            "spawnAttemptId": 7,
            "finalizationId": finalization_id,
            "slot": 0,
            "terrain": 0,
            "worldContext": WORLD,
            "returnWorldContext": WORLD,
            "statePointer": WORLD["statePointer"],
            "fieldPointer": WORLD["fieldPointer"],
            "inputEncounter": ENCOUNTER,
            "resolverReceipts": [],
            "guestTiming": {"arm9Ticks": 600},
            "returnValue": 1,
            "position": [596, 398],
            "startup": {"target": [596, 398], "origin": [596, 382], "locomotion": 4},
        }}, {"kind": "native-observation", "data": {
            "observation": "spawn-object-create",
            "slot": 0,
            "returnValue": 0x02240000,
            "arguments": [0x02230000, 596, 382, 1],
        }}, {"kind": "native-observation", "data": {
            "observation": "spawn-prepared",
            "slot": 0,
            "returnValue": 1,
            "worldContext": WORLD,
            "preparedEncounter": ENCOUNTER,
            "finalization": {"status": "matched", "receipt": {
                "finalizationId": finalization_id,
            }},
            "startup": {"target": [596, 398], "origin": [596, 382], "locomotion": 4},
            "publicSubject": {
                "handle": SPAWN_HANDLE,
                "subjectIdentity": ENCOUNTER["personality"],
                "identityVerified": True,
                "role": "WILD",
                "species": ENCOUNTER["species"],
            },
        }}])
        return rows
    if index > EXPECTED_DESTINATION_UPDATES:
        return rows
    finalization_id = 1000 + index
    result = int(index == EXPECTED_DESTINATION_UPDATES - 1)
    final = {
        "observation": "spawn-finalized",
        "spawnAttemptId": 7,
        "finalizationId": finalization_id,
        "slot": 0,
        "terrain": 0,
        "worldContext": WORLD,
        "returnWorldContext": WORLD,
        "statePointer": WORLD["statePointer"],
        "fieldPointer": WORLD["fieldPointer"],
        "inputEncounter": ENCOUNTER,
        "resolverReceipts": [{
            "resolved": True,
            "finalizationId": finalization_id,
            "inputEncounter": ENCOUNTER,
            "sourceSha256": SOURCE_HASH,
        }] if index == 0 else [],
        "guestTiming": {"arm9Ticks": 36000 if index == 0 else 600},
        "returnValue": 0,
    }
    destination = {
        "observation": "spawn-destination-search",
        "spawnAttemptId": 7,
        "finalizationId": finalization_id,
        "slot": 0,
        "destinationMask": 8,
        "setupMode": "normal",
        "entryActorFrame": 200 + index,
        "returnActorFrame": 200 + index,
        "entryNativeCycle": 1000 + index,
        "returnNativeCycle": 1000 + index,
        "candidateQueryCount": 0 if index == 0 else RESUMED_QUERY_COUNTS[index - 1],
        "worldContext": WORLD,
        "returnValue": result,
    }
    rows.extend([
        {"kind": "native-observation", "data": final},
        {"kind": "native-observation", "data": destination},
    ])
    if index == 0:
        rows.extend([
            {"kind": "native-observation", "data": {
                "observation": "spawn-metadata", "finalizationId": finalization_id,
            }},
            {"kind": "native-observation", "data": {
                "observation": "spawn-class-selection", "finalizationId": finalization_id,
            }},
        ])
        rows.append({"kind": "native-observation", "data": {
            "observation": "spawn-queued",
            "spawnAttemptId": 7,
            "queued": True,
            "pendingDestination": True,
        }})
    return rows


def replay(fault=None):
    meter = SpawnWorkBudgetMeasurement(
        recipe(), {"schema": {}, "sourceSha256": SOURCE_HASH}, max_frames=520)
    meter.arm(SUBJECT, snapshot(0))
    negative = SpawnWorkBudgetNegative(fault) if fault else None
    for index in range(125):
        row = {"phase": "observe", "events": events(index),
               "samples": [snapshot(index + 1)]}
        if negative:
            row = negative.mutate(row, {"mankey": SUBJECT})
        meter.observe(row["samples"][0], row["events"])
    return meter.finish()


class SpawnWorkBudgetTests(unittest.TestCase):
    @staticmethod
    def _control_row(context, *, x, x_prev, pos_x):
        return {
            "phase": "observe",
            "samples": [{
                "context": context,
                "player": {
                    "x": x, "x_prev": x_prev, "y": 398, "y_prev": 398,
                    "pos_x": pos_x, "pos_z": 398 << 16,
                },
            }],
            "events": [{"kind": "native-observation", "data": {
                "observation": "stock-main-loop-pacing",
                "frameCounter": 2,
                "intervalFromPrevious": {
                    "arm9Ticks": NORMAL_MAIN_LOOP_ARM9_TICKS,
                    "nativeCycles": NORMAL_MAIN_LOOP_NATIVE_CYCLES,
                    "frameSequence": NORMAL_MAIN_LOOP_NATIVE_CYCLES,
                },
            }}],
        }

    def test_pacing_controls_begin_after_the_route_transition(self):
        pre = self._control_row(INITIAL_CONTEXT, x=576, x_prev=577, pos_x=576 << 16)
        transition = self._control_row(
            {key: WORLD[key] for key in ("mapId", "fieldEpoch", "mapGeneration")},
            x=575, x_prev=575, pos_x=575 << 16)
        post = self._control_row(
            {key: WORLD[key] for key in ("mapId", "fieldEpoch", "mapGeneration")},
            x=574, x_prev=575, pos_x=574 << 16)
        post_two = self._control_row(
            {key: WORLD[key] for key in ("mapId", "fieldEpoch", "mapGeneration")},
            x=573, x_prev=574, pos_x=573 << 16)

        late = SpawnWorkBudgetNegative("spawn-work-budget-late-main-loop")
        late.mutate(pre, {"mankey": SUBJECT})
        late.mutate(transition, {"mankey": SUBJECT})
        self.assertFalse(late.applied)
        late.mutate(post, {"mankey": SUBJECT})
        self.assertFalse(late.applied)
        late_result = late.mutate(post_two, {"mankey": SUBJECT})
        self.assertTrue(late.applied)
        self.assertEqual(late_result["events"][0]["data"]["frameCounter"], 3)

        stall = SpawnWorkBudgetNegative("spawn-work-budget-player-render-stall")
        stall.mutate(pre, {"mankey": SUBJECT})
        stall.mutate(transition, {"mankey": SUBJECT})
        self.assertFalse(stall.applied)
        stall_result = stall.mutate(post, {"mankey": SUBJECT})
        self.assertTrue(stall.applied)
        self.assertEqual(
            stall_result["samples"][0]["player"]["pos_x"], 575 << 16)

    def test_complete_incremental_scan_produces_acceptance_rows(self):
        result = replay()
        self.assertTrue(result["passed"])
        self.assertEqual(result["attempt"]["callCount"], EXPECTED_DESTINATION_UPDATES)
        self.assertEqual(result["attempt"]["finalizerCallCount"],
                         EXPECTED_DESTINATION_UPDATES + 1)
        self.assertEqual(result["attempt"]["candidateQueryCount"],
                         sum(RESUMED_QUERY_COUNTS))
        self.assertEqual(result["attempt"]["resolverReceiptCount"], 1)
        self.assertEqual(result["attempt"]["metadataReceiptCount"], 1)
        self.assertEqual(result["attempt"]["classSelectionReceiptCount"], 1)
        self.assertEqual(result["attempt"]["maxResumedFinalizerArm9Ticks"], 600)
        self.assertEqual(result["attempt"]["successfulSpawnCount"], 1)
        self.assertEqual(result["entry"]["startDistance"], 16)
        self.assertEqual(result["entry"]["targetDistance"], 16)
        self.assertEqual(result["entry"]["offscreenClearance"], 10)
        self.assertTrue(result["entry"]["spawnHopObserved"])
        self.assertGreater(result["entry"]["ownerHopFrames"], 0)
        self.assertGreaterEqual(result["entry"]["distanceProgress"], 4)
        self.assertGreaterEqual(result["entry"]["maximumRenderDisplacement"], 4)
        self.assertEqual(result["pacing"]["lateMainLoopCount"], 0)
        self.assertGreaterEqual(result["pacing"]["postSpawnSampleCount"], 4)
        self.assertGreaterEqual(result["pacing"]["interiorMovingFrameCount"], 120)
        self.assertEqual(result["pacing"]["interiorRenderStallCount"], 0)
        rows = measurements(
            {"passed": True, "failures": [], "measurements": {KIND: result}},
            {"sessionId": "session-test", "sessionCleanup": {
                "sessionId": "session-test", "closed": True, "errors": [],
            }},
        )
        self.assertEqual([row["passed"] for row in rows], [True] * 23)

    def test_all_copied_faults_fail_for_their_named_reason(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                result = replay(fault)
                self.assertFalse(result["passed"])
                validate_negative_result(
                    {"passed": False, "failures": [], "measurements": {KIND: result}},
                    fault,
                )


if __name__ == "__main__":
    unittest.main()
