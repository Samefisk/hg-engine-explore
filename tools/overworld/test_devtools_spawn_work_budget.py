import unittest
from copy import deepcopy

from tools.overworld.devtools_spawn_work_budget_measurement import (
    EXPECTED_DESTINATION_UPDATES,
    KIND,
    MAX_CANDIDATE_QUERIES_PER_UPDATE,
    MAX_RESUMED_FINALIZER_ARM9_TICKS,
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
RESUMED_QUERY_COUNTS = (MAX_CANDIDATE_QUERIES_PER_UPDATE,) * (EXPECTED_DESTINATION_UPDATES - 1)
SETUP_RETIRE_OFFSET = EXPECTED_DESTINATION_UPDATES + 1
ENTRY_X = 565 + EXPECTED_DESTINATION_UPDATES


def recipe():
    return {
        "mode": "normal",
        "fixture": {"rom": "test.nds", "save": "test.sav"},
        "subjects": [{
            "id": "mankey", "species": 56,
            "role": "FOLLOWER", "acquire": "existing",
        }],
    }


def snapshot(index, *, entry_start=EXPECTED_DESTINATION_UPDATES + 1):
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
    if index >= entry_start:
        stage = index - entry_start
        actor_y = [382, 383, 384, 385, 386, 387][min(stage, 5)]
        actors.append({
            "handle": SPAWN_HANDLE,
            "subjectIdentity": ENCOUNTER["personality"],
            "active": True,
            "species": ENCOUNTER["species"],
            "role": "WILD",
            "identityVerified": True,
            "logical": {"x": ENTRY_X, "y": actor_y},
            "render": {"x": ENTRY_X, "y": actor_y},
            "lane": "OWNER",
            "motionKind": "FLY_IN",
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
            "position": [ENTRY_X, 398],
            "startup": {"target": [ENTRY_X, 398], "origin": [ENTRY_X, 382], "locomotion": 9},
        }}, {"kind": "native-observation", "data": {
            "observation": "spawn-object-create",
            "slot": 0,
            "returnValue": 0x02240000,
            "arguments": [0x02230000, ENTRY_X, 382, 1],
        }}, {"kind": "native-observation", "data": {
            "observation": "spawn-prepared",
            "slot": 0,
            "returnValue": 1,
            "worldContext": WORLD,
            "preparedEncounter": ENCOUNTER,
            "finalization": {"status": "matched", "receipt": {
                "finalizationId": finalization_id,
            }},
            "startup": {"target": [ENTRY_X, 398], "origin": [ENTRY_X, 382], "locomotion": 9},
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
    negative = SpawnWorkBudgetNegative(fault, measurement=meter) if fault else None
    for index in range(125):
        row = {"phase": "observe", "events": events(index),
               "samples": [snapshot(index + 1)]}
        if negative:
            row = negative.mutate(row, {"mankey": SUBJECT})
        meter.observe(row["samples"][0], row["events"])
    return meter.finish()


def refused_then_spawn_events(index):
    if index <= EXPECTED_DESTINATION_UPDATES:
        rows = events(index)
        if index == EXPECTED_DESTINATION_UPDATES:
            rows = [event for event in rows
                    if event.get("data", {}).get("observation") not in (
                        "spawn-prepared", "spawn-object-create")]
            final = next(event["data"] for event in rows
                         if event["data"].get("observation") == "spawn-finalized")
            final["returnValue"] = 0
            final["pairEligible"] = False
            final["guestTiming"]["arm9Ticks"] = 3378
            final.pop("startup", None)
            final.pop("position", None)
        for event in rows:
            if event.get("data", {}).get("observation") == "spawn-destination-search" \
                    and index > 0:
                event["data"]["candidateQueryCount"] = MAX_CANDIDATE_QUERIES_PER_UPDATE
        return rows
    rows = events(index)
    offset = EXPECTED_DESTINATION_UPDATES + 2
    if index < offset:
        return rows
    for event in events(index - offset):
        data = event.get("data", {})
        if data.get("observation") == "stock-main-loop-pacing":
            continue
        copied = deepcopy(event)
        data = copied["data"]
        if "spawnAttemptId" in data:
            data["spawnAttemptId"] = 8
        if "finalizationId" in data:
            data["finalizationId"] += 1000
        if "entryActorFrame" in data:
            data["entryActorFrame"] += offset
            data["returnActorFrame"] += offset
        if "entryNativeCycle" in data:
            data["entryNativeCycle"] += offset
            data["returnNativeCycle"] += offset
        if data.get("observation") == "spawn-finalized":
            for receipt in data.get("resolverReceipts", []):
                receipt["finalizationId"] += 1000
        if data.get("observation") == "spawn-destination-search" \
                and index > offset:
            data["candidateQueryCount"] = MAX_CANDIDATE_QUERIES_PER_UPDATE
        if data.get("observation") == "spawn-prepared":
            data["finalization"]["receipt"]["finalizationId"] += 1000
        rows.append(copied)
    return rows


def replay_refusal(fault=None):
    meter = SpawnWorkBudgetMeasurement(
        recipe(), {"schema": {}, "sourceSha256": SOURCE_HASH}, max_frames=520)
    meter.arm(SUBJECT, snapshot(0))
    negative = SpawnWorkBudgetNegative(fault, measurement=meter) if fault else None
    entry_start = 2 * EXPECTED_DESTINATION_UPDATES + 3
    for index in range(150):
        row = {"phase": "observe", "events": refused_then_spawn_events(index),
               "samples": [snapshot(index + 1, entry_start=entry_start)]}
        if negative:
            row = negative.mutate(row, {"mankey": SUBJECT})
        meter.observe(row["samples"][0], row["events"])
    return meter.finish()


def setup_snapshot(index):
    row = snapshot(index)
    row["context"] = deepcopy(INITIAL_CONTEXT)
    row["actorFrame"] = 200 + index
    row["player"].update(x=585, y=406, x_prev=585, y_prev=406,
                         pos_x=585 << 16, pos_z=406 << 16)
    return row


def setup_events(index):
    rows = events(index)
    world = {**WORLD, **INITIAL_CONTEXT}
    for event in rows:
        data = event["data"]
        data["setupMode"] = "normal"
        for key in ("worldContext", "returnWorldContext"):
            if key in data:
                data[key] = deepcopy(world)
        if data.get("observation") == "spawn-destination-search":
            data["positionPointer"] = 0x023D9000
            if index > 0:
                data["candidateQueryCount"] = MAX_CANDIDATE_QUERIES_PER_UPDATE
        if data.get("observation") == "spawn-finalized":
            data["preparedPointer"] = 0x023D9000
    return rows


def setup_meter():
    meter = SpawnWorkBudgetMeasurement(
        recipe(), {"schema": {}, "sourceSha256": SOURCE_HASH}, max_frames=520)
    for index in range(13):
        meter.observe_setup(setup_snapshot(index), setup_events(index))
    meter.arm(SUBJECT, setup_snapshot(12))
    return meter


def travel_row(index):
    sample = setup_snapshot(index)
    rows = setup_events(index - 1)
    for event in rows:
        data = event["data"]
        for key in ("entryActorFrame", "returnActorFrame", "entryNativeCycle", "returnNativeCycle"):
            if key in data: data[key] += 1
    return sample, rows


def travel_meter():
    meter = SpawnWorkBudgetMeasurement(
        recipe(), {"schema": {}, "sourceSha256": SOURCE_HASH}, max_frames=520)
    meter.arm(SUBJECT, setup_snapshot(0))
    return meter


class SpawnWorkBudgetTests(unittest.TestCase):
    def test_post_arm_route29_scan_is_exact_uncredited_travel_setup(self):
        meter = travel_meter()
        for index in range(1, SETUP_RETIRE_OFFSET + 2):
            sample, rows = travel_row(index)
            self.assertEqual(meter.observe(sample, rows)["failures"], [])
        result = meter.result()
        self.assertFalse(result["setupRetired"]["credited"])
        self.assertEqual(result["setupRetired"]["retiredFrame"], 101 + SETUP_RETIRE_OFFSET)
        self.assertEqual(result["uncreditedSetupFrames"], EXPECTED_DESTINATION_UPDATES + 1)
        self.assertIsNone(result["attempt"])
        self.assertIsNone(result["entry"])
        self.assertEqual(result["destinationFrames"], [])
        self.assertEqual(meter.profile_receipts, 0)
        self.assertFalse(result["ready"])
        crossing = snapshot(1)
        crossing.update(frame=meter.last_frame + 1,
                        nativeCycle=meter.last_native_cycle + 1,
                        actorFrame=meter.last_actor_frame)
        self.assertEqual(meter.observe(crossing, [])["failures"], [])
        self.assertEqual(meter.result()["contextTransition"]["to"]["mapId"], 67)
        self.assertFalse(meter.ready)

    def test_travel_setup_keeps_pointer_preparation_timing_and_crossing_faults(self):
        cases = (("pointer", "exact prepared value"),
                 ("preparation", "resumed scan repeated profile resolution"),
                 ("timing", "resumed finalizer exceeds guest work budget"),
                 ("unknown-start", "lacks its exact native start"),
                 ("crossing", "outside its reviewed crossing"))
        for fault, reason in cases:
            with self.subTest(fault=fault):
                meter = travel_meter()
                if fault != "unknown-start":
                    sample, rows = travel_row(1)
                    self.assertEqual(meter.observe(sample, rows)["failures"], [])
                sample, rows = travel_row(2)
                if fault == "unknown-start":
                    sample, rows = setup_snapshot(1), setup_events(1)
                final = next(e["data"] for e in rows if e["data"]["observation"] == "spawn-finalized")
                if fault == "pointer": final["preparedPointer"] += 4
                elif fault == "preparation": final["resolverReceipts"] = [{
                    "resolved": True, "finalizationId": final["finalizationId"],
                    "inputEncounter": ENCOUNTER, "sourceSha256": SOURCE_HASH}]
                elif fault == "timing": final["guestTiming"]["arm9Ticks"] = MAX_RESUMED_FINALIZER_ARM9_TICKS + 1
                elif fault == "crossing":
                    sample = snapshot(1)
                    sample.update(frame=meter.last_frame + 1,
                                  nativeCycle=meter.last_native_cycle + 1,
                                  actorFrame=meter.last_actor_frame)
                    sample["player"]["x"] = 574
                    rows = []
                self.assertIn(reason, meter.observe(sample, rows)["failures"][0])

    def test_serialized_route29_scan_cannot_earn_city_proof(self):
        result = replay()
        result["attempt"]["worldContext"]["mapId"] = 33
        with self.assertRaisesRegex(ValueError, "lacks one complete bounded destination scan"):
            measurements({"passed": True, "failures": [], "measurements": {KIND: result}},
                         {"sessionId": "session", "sessionCleanup": {
                             "sessionId": "session", "closed": True, "errors": []}})

    def test_setup_scan_drains_without_credit_then_exact_fresh_scan_passes(self):
        meter = setup_meter()
        for index in range(13, EXPECTED_DESTINATION_UPDATES + 2):
            meter.observe(setup_snapshot(index), setup_events(index))
        result = meter.result()
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["setupRetired"]["spawnAttemptId"], 7)
        self.assertFalse(result["setupRetired"]["credited"])
        self.assertEqual(result["setupRetired"]["candidateQueryCount"], 240)
        self.assertEqual(result["setupRetired"]["retiredFrame"], 100 + SETUP_RETIRE_OFFSET)
        self.assertIsNone(result["attempt"])
        self.assertIsNone(result["entry"])
        self.assertEqual(result["destinationFrames"], [])
        self.assertEqual(result["pacing"]["sampleCount"], 0)
        self.assertEqual(meter.profile_receipts, 0)
        self.assertEqual(meter.metadata_receipts, 0)
        self.assertEqual(meter.class_selection_receipts, 0)
        self.assertFalse(result["ready"])
        for index in range(125):
            sample = snapshot(index + 1)
            sample["frame"] += SETUP_RETIRE_OFFSET
            sample["nativeCycle"] += SETUP_RETIRE_OFFSET
            sample["actorFrame"] += SETUP_RETIRE_OFFSET
            rows = events(index)
            for event in rows:
                data = event["data"]
                if "spawnAttemptId" in data:
                    data["spawnAttemptId"] = 8
                for key in ("entryActorFrame", "returnActorFrame", "entryNativeCycle",
                            "returnNativeCycle", "afterQueueFrame", "flushedAtQueueFrame"):
                    if key in data:
                        data[key] += SETUP_RETIRE_OFFSET
                if data.get("observation") == "spawn-destination-search" and index > 0:
                    data["candidateQueryCount"] = MAX_CANDIDATE_QUERIES_PER_UPDATE
            meter.observe(sample, rows)
        result = meter.finish()
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["attempt"]["spawnAttemptId"], 8)
        self.assertEqual(result["attempt"]["candidateQueryCount"], 240)
        self.assertEqual(result["attempt"]["resolverReceiptCount"], 1)
        self.assertEqual(result["attempt"]["metadataReceiptCount"], 1)
        self.assertEqual(result["attempt"]["classSelectionReceiptCount"], 1)

    def test_entry_outcome_controls_require_adopted_context_and_full_attempt(self):
        names = ("spawn-work-budget-missing-post-spawn-pacing",
                 "spawn-work-budget-missing-natural-spawn",
                 "spawn-work-budget-entry-special-path",
                 "spawn-work-budget-entry-onscreen-origin")
        for name in names:
            with self.subTest(fault=name):
                meter = travel_meter()
                control = SpawnWorkBudgetNegative(name, measurement=meter)
                boot = {"phase": "observe", "samples": [snapshot(1)], "events": events(0)}
                self.assertEqual(control.mutate(boot, {}), boot)
                self.assertIsNone(control.attempt_owner)
                self.assertFalse(control.applied)
                meter.observe(snapshot(1), events(0))
                self.assertIsNotNone(meter.context_transition)
                for key in ("fieldEpoch", "mapGeneration", "mapId"):
                    current = snapshot(2)
                    current["context"][key] += 1
                    row = {"phase": "observe", "samples": [current], "events": events(1)}
                    control = SpawnWorkBudgetNegative(name, measurement=meter)
                    self.assertEqual(control.mutate(row, {}), row)
                    self.assertIsNone(control.attempt_owner)
                    self.assertFalse(control.applied)
                for key in ("spawnAttemptId", "slot", *WORLD):
                    foreign = deepcopy(events(1))
                    for event in foreign:
                        data = event["data"]
                        if key in WORLD and "worldContext" in data:
                            data["worldContext"][key] += 1
                        elif key not in WORLD and key in data:
                            data[key] += 1
                    row = {"phase": "observe", "samples": [snapshot(2)], "events": foreign}
                    control = SpawnWorkBudgetNegative(name, measurement=meter)
                    self.assertEqual(control.mutate(row, {}), row)
                    self.assertEqual(control.seen_destinations, len(meter.calls))
                    self.assertEqual(control.attempt_owner,
                                     SpawnWorkBudgetNegative._attempt_owner(meter.attempt))
                    self.assertFalse(control.applied)

    def test_entry_outcome_controls_skip_travel_scan_then_hit_fresh_attempt(self):
        for name in ("spawn-work-budget-missing-post-spawn-pacing",
                     "spawn-work-budget-missing-natural-spawn",
                     "spawn-work-budget-entry-special-path",
                     "spawn-work-budget-entry-onscreen-origin"):
            with self.subTest(fault=name):
                meter = setup_meter()
                fault = SpawnWorkBudgetNegative(name, measurement=meter)
                for index in range(13, EXPECTED_DESTINATION_UPDATES + 2):
                    row = {"phase": "observe", "samples": [setup_snapshot(index)],
                           "events": setup_events(index)}
                    copied = fault.mutate(row, {"mankey": SUBJECT})
                    self.assertEqual(copied, row)
                    self.assertFalse(fault.applied)
                    self.assertIsNone(fault.attempt_owner)
                    meter.observe(copied["samples"][0], copied["events"])
                self.assertFalse(meter.result()["setupRetired"]["credited"])
                self.assertIsNone(meter.result()["entry"])
                for index in range(125):
                    sample = snapshot(index + 1)
                    sample["frame"] += SETUP_RETIRE_OFFSET
                    sample["nativeCycle"] += SETUP_RETIRE_OFFSET
                    sample["actorFrame"] += SETUP_RETIRE_OFFSET
                    rows = events(index)
                    for event in rows:
                        data = event["data"]
                        if "spawnAttemptId" in data:
                            data["spawnAttemptId"] = 8
                        for key in ("entryActorFrame", "returnActorFrame", "entryNativeCycle",
                                    "returnNativeCycle", "afterQueueFrame", "flushedAtQueueFrame"):
                            if key in data:
                                data[key] += SETUP_RETIRE_OFFSET
                        if data.get("observation") == "spawn-destination-search" and index > 0:
                            data["candidateQueryCount"] = MAX_CANDIDATE_QUERIES_PER_UPDATE
                    copied = fault.mutate({"phase": "observe", "samples": [sample],
                                           "events": rows}, {"mankey": SUBJECT})
                    meter.observe(copied["samples"][0], copied["events"])
                result = meter.finish()
                self.assertTrue(fault.applied)
                self.assertEqual(fault.attempt_owner[0], 8)
                self.assertEqual(fault.attempt_owner[2]["mapId"], 67)
                validate_negative_result({"passed": False, "failures": [],
                                          "measurements": {KIND: result}}, name)

    def test_repeated_refusal_control_waits_for_fresh_start_after_setup_scan(self):
        meter = setup_meter()
        fault = SpawnWorkBudgetNegative("spawn-work-budget-repeated-refused-attempt")
        for index in range(13, EXPECTED_DESTINATION_UPDATES + 2):
            row = {"phase": "observe", "samples": [setup_snapshot(index)],
                   "events": setup_events(index)}
            copied = fault.mutate(row, {"mankey": SUBJECT})
            self.assertEqual(copied, row)
            self.assertIsNone(fault.attempt_owner)
            self.assertFalse(fault.applied)
            meter.observe(copied["samples"][0], copied["events"])
        self.assertFalse(meter.result()["setupRetired"]["credited"])
        self.assertIsNone(meter.result()["attempt"])
        for index in range(EXPECTED_DESTINATION_UPDATES + 2):
            sample = snapshot(index + 1)
            sample["frame"] += SETUP_RETIRE_OFFSET
            sample["nativeCycle"] += SETUP_RETIRE_OFFSET
            sample["actorFrame"] += SETUP_RETIRE_OFFSET
            rows = events(index)
            for event in rows:
                data = event["data"]
                if "spawnAttemptId" in data:
                    data["spawnAttemptId"] = 8
                for key in ("entryActorFrame", "returnActorFrame", "entryNativeCycle",
                            "returnNativeCycle", "afterQueueFrame", "flushedAtQueueFrame"):
                    if key in data:
                        data[key] += SETUP_RETIRE_OFFSET
                if data.get("observation") == "spawn-destination-search" and index > 0:
                    data["candidateQueryCount"] = MAX_CANDIDATE_QUERIES_PER_UPDATE
            copied = fault.mutate({"phase": "observe", "samples": [sample],
                                   "events": rows}, {"mankey": SUBJECT})
            if index == 0:
                self.assertEqual(fault.attempt_owner[0], 8)
                self.assertEqual(fault.seen_destinations, 1)
            meter.observe(sample, copied["events"])
        self.assertTrue(fault.applied)
        result = meter.finish()
        self.assertFalse(result["passed"])
        validate_negative_result({"passed": False, "failures": [],
                                  "measurements": {KIND: result}}, fault.fault)

    def test_setup_resume_requires_known_start_and_exact_owner(self):
        meter = SpawnWorkBudgetMeasurement(
            recipe(), {"schema": {}, "sourceSha256": SOURCE_HASH}, max_frames=520)
        meter.observe_setup(setup_snapshot(12), setup_events(12))
        with self.assertRaisesRegex(ValueError, "lacks its exact native start"):
            meter.arm(SUBJECT, setup_snapshot(12))
        for key in ("spawnAttemptId", "slot", "preparedPointer", "worldContext"):
            with self.subTest(changed=key):
                meter = setup_meter()
                rows = setup_events(13)
                for event in rows:
                    data = event["data"]
                    if key in data:
                        if key == "worldContext":
                            data[key]["mapGeneration"] += 1
                        else:
                            data[key] += 1
                self.assertTrue(meter.observe(setup_snapshot(13), rows)["failures"])

    def test_setup_resume_keeps_existing_named_budget_failures(self):
        cases = (
            ("queries", "destination receipt exceeds the candidate batch"),
            ("resolution", "resumed scan repeated profile resolution"),
            ("metadata", "resumed scan repeated metadata preparation"),
            ("class", "resumed scan repeated class selection"),
            ("slow", "resumed finalizer exceeds guest work budget"),
            ("missing", "setup queued scan skipped a completed game update"),
        )
        for fault, reason in cases:
            with self.subTest(fault=fault):
                meter = setup_meter()
                rows = setup_events(13)
                final = next(e["data"] for e in rows
                             if e["data"]["observation"] == "spawn-finalized")
                destination = next(e["data"] for e in rows
                                   if e["data"]["observation"] == "spawn-destination-search")
                if fault == "queries":
                    destination["candidateQueryCount"] = 17
                elif fault == "resolution":
                    final["resolverReceipts"] = [{
                        "resolved": True, "finalizationId": final["finalizationId"],
                        "inputEncounter": ENCOUNTER, "sourceSha256": SOURCE_HASH,
                    }]
                elif fault in ("metadata", "class"):
                    rows.append({"kind": "native-observation", "data": {
                        "observation": "spawn-metadata" if fault == "metadata"
                            else "spawn-class-selection",
                        "finalizationId": final["finalizationId"],
                    }})
                elif fault == "slow":
                    final["guestTiming"]["arm9Ticks"] = MAX_RESUMED_FINALIZER_ARM9_TICKS + 1
                elif fault == "missing":
                    rows = []
                result = meter.observe(setup_snapshot(13), rows)
                self.assertIn(reason, result["failures"][0])

    def test_setup_terminal_attempt_cannot_resume_or_earn_readiness(self):
        meter = setup_meter()
        for index in range(13, EXPECTED_DESTINATION_UPDATES + 1):
            meter.observe(setup_snapshot(index), setup_events(index))
        rows = setup_events(EXPECTED_DESTINATION_UPDATES)
        result = meter.observe(setup_snapshot(EXPECTED_DESTINATION_UPDATES + 1), rows)
        self.assertIn("setup attempt repeated after terminal work", result["failures"][0])
        self.assertFalse(result["ready"])

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
        self.assertTrue(result["entry"]["spawnMotionObserved"])
        self.assertGreater(result["entry"]["ownerEntryFrames"], 0)
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

    def test_terminal_refusal_retires_then_later_full_scan_spawns(self):
        result = replay_refusal()
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(len(result["rejectedAttempts"]), 1)
        refused = result["rejectedAttempts"][0]
        self.assertEqual(refused["callCount"], EXPECTED_DESTINATION_UPDATES)
        self.assertEqual(refused["candidateQueryCount"], 240)
        self.assertEqual(refused["finalizerCallCount"], EXPECTED_DESTINATION_UPDATES + 1)
        self.assertEqual(refused["retiredFrame"], refused["refusalFrame"] + 1)
        self.assertEqual(refused["maxResumedFinalizerArm9Ticks"], 3378)
        self.assertEqual(result["attempt"]["candidateQueryCount"], 240)
        self.assertEqual(result["attempt"]["successfulSpawnCount"], 1)
        rows = measurements(
            {"passed": True, "failures": [], "measurements": {KIND: result}},
            {"sessionId": "session-test", "sessionCleanup": {
                "sessionId": "session-test", "closed": True, "errors": [],
            }},
        )
        self.assertEqual([row["passed"] for row in rows], [True] * 23)

    def test_actual_refused_attempt_repetition_is_red(self):
        result = replay_refusal("spawn-work-budget-repeated-refused-attempt")
        self.assertFalse(result["passed"])
        validate_negative_result(
            {"passed": False, "failures": [], "measurements": {KIND: result}},
            "spawn-work-budget-repeated-refused-attempt",
        )

    def test_natural_spawn_controls_reach_success_after_a_refused_attempt(self):
        for fault in ("spawn-work-budget-missing-natural-spawn",
                      "spawn-work-budget-missing-post-spawn-pacing"):
            with self.subTest(fault=fault):
                result = replay_refusal(fault)
                self.assertFalse(result["passed"])
                validate_negative_result(
                    {"passed": False, "failures": [], "measurements": {KIND: result}},
                    fault,
                )

    def test_scan_templates_reset_for_each_full_attempt_owner(self):
        changes = [("spawnAttemptId", 8), ("slot", 1)] + [
            (key, value + 1) for key, value in WORLD.items()]
        for key, value in changes:
            with self.subTest(owner_part=key):
                control = SpawnWorkBudgetNegative("spawn-work-budget-missing-natural-spawn")
                control.mutate({"phase": "observe", "events": events(0)}, {})
                self.assertIsNotNone(control.source_sha256)
                self.assertIsNotNone(control.metadata_template)
                self.assertIsNotNone(control.class_selection_template)
                refused_history = {"data": {"spawnAttemptId": 7}}
                control.refused_final = deepcopy(refused_history)
                next_scan = [event for event in events(0)
                             if event["data"]["observation"] in (
                                 "spawn-finalized", "spawn-destination-search")]
                for event in next_scan:
                    data = event["data"]
                    if key in WORLD:
                        data["worldContext"] = {**WORLD, key: value}
                    else:
                        data[key] = value
                    if data["observation"] == "spawn-finalized":
                        data["resolverReceipts"] = []
                control.mutate({"phase": "observe", "events": next_scan}, {})
                self.assertEqual(control.seen_destinations, 1)
                self.assertIsNone(control.source_sha256)
                self.assertIsNone(control.metadata_template)
                self.assertIsNone(control.class_selection_template)
                self.assertEqual(control.refused_final, refused_history)

    def test_spawn_controls_ignore_foreign_success_and_refused_startup(self):
        for fault in ("spawn-work-budget-missing-natural-spawn",
                      "spawn-work-budget-missing-post-spawn-pacing"):
            for key in ("spawnAttemptId", "slot", *WORLD):
                with self.subTest(fault=fault, owner_part=key):
                    control = SpawnWorkBudgetNegative(fault)
                    for index in range(EXPECTED_DESTINATION_UPDATES):
                        control.mutate({"phase": "observe", "events": events(index),
                                        "samples": [snapshot(index + 1)]}, {})
                    foreign = events(EXPECTED_DESTINATION_UPDATES)
                    final = next(event["data"] for event in foreign
                                 if event["data"]["observation"] == "spawn-finalized")
                    if key in WORLD:
                        final["worldContext"] = {**WORLD, key: WORLD[key] + 1}
                    else:
                        final[key] += 1
                    control.mutate({"phase": "observe", "events": foreign,
                                    "samples": [snapshot(EXPECTED_DESTINATION_UPDATES + 1)]}, {})
                    control.mutate({"phase": "observe", "events": events(EXPECTED_DESTINATION_UPDATES + 1),
                                    "samples": [snapshot(EXPECTED_DESTINATION_UPDATES + 2)]}, {})
                    self.assertFalse(control.applied)
                    self.assertIsNone(control.successful_start_frame)

        control = SpawnWorkBudgetNegative("spawn-work-budget-missing-post-spawn-pacing")
        for index in range(2 * EXPECTED_DESTINATION_UPDATES + 3):
            control.mutate({"phase": "observe", "events": refused_then_spawn_events(index),
                            "samples": [snapshot(index + 1)]}, {})
            self.assertFalse(control.applied)
        self.assertIsNotNone(control.successful_start_frame)
        index = 2 * EXPECTED_DESTINATION_UPDATES + 3
        copied = control.mutate({"phase": "observe", "events": refused_then_spawn_events(index),
                                 "samples": [snapshot(index + 1)]}, {})
        self.assertTrue(control.applied)
        self.assertFalse(any(event["data"]["observation"] == "stock-main-loop-pacing"
                             for event in copied["events"]))

    def test_repeated_refusal_copy_keeps_the_next_raw_frame_sequence(self):
        fault = SpawnWorkBudgetNegative("spawn-work-budget-repeated-refused-attempt")
        fault.refused_final = {"frame": 999, "kind": "native-observation", "data": {
            "observation": "spawn-finalized", "sequence": 884,
            "spawnAttemptId": 10, "finalizationId": 114,
            "entryActorFrame": 585, "returnActorFrame": 585,
            "entryNativeCycle": 2445, "returnNativeCycle": 2445,
            "returnValue": 0,
        }}
        row = {"phase": "observe", "samples": [{"frame": 1000}], "events": [
            {"frame": 1000, "kind": "native-observation", "data": {
                "observation": "sound-play", "sequence": 893,
                "entryActorFrame": 585, "returnActorFrame": 585,
                "entryNativeCycle": 2447, "returnNativeCycle": 2447,
            }},
            {"frame": 1000, "kind": "native-observation", "data": {
                "observation": "player-step-admitted", "sequence": 894,
            }},
            {"frame": 1000, "kind": "native-observation", "data": {
                "observation": "stock-main-loop-pacing", "sequence": 895,
            }},
        ]}
        copied = fault.mutate(row, {})
        self.assertTrue(fault.applied)
        self.assertEqual([event["frame"] for event in copied["events"]],
                         [1000, 1000, 1000])
        self.assertEqual([event["data"]["sequence"] for event in copied["events"]],
                         [893, 894, 895])
        self.assertEqual([event["data"]["observation"] for event in copied["events"]],
                         ["spawn-finalized", "player-step-admitted",
                          "stock-main-loop-pacing"])
        self.assertEqual(copied["events"][0]["data"]["spawnAttemptId"], 10)
        self.assertEqual(copied["events"][0]["data"]["finalizationId"], 115)
        self.assertEqual(row["events"][0]["data"]["observation"], "sound-play")

    def test_acceptance_uses_the_prepared_encounter_species(self):
        result = deepcopy(replay())
        result["attempt"]["encounter"]["species"] = 16
        result["entry"]["species"] = 16
        rows = measurements(
            {"passed": True, "failures": [], "measurements": {KIND: result}},
            {"sessionId": "session-test", "sessionCleanup": {
                "sessionId": "session-test", "closed": True, "errors": [],
            }},
        )
        identity = next(row for row in rows
                        if row["name"] == "spawn-work-entry-actor-identity")
        self.assertEqual(identity["value"], [1, "WILD", 1, 1])
        self.assertTrue(identity["passed"])

    def test_five_and_old_nine_query_batches_fail_for_the_batch_reason(self):
        for count in (5, 9):
            with self.subTest(count=count):
                meter = SpawnWorkBudgetMeasurement(
                    recipe(), {"schema": {}, "sourceSha256": SOURCE_HASH}, max_frames=520)
                meter.arm(SUBJECT, snapshot(0))
                for index in range(2):
                    rows = events(index)
                    if index == 1:
                        destination = next(e["data"] for e in rows
                            if e["data"].get("observation") == "spawn-destination-search")
                        destination["candidateQueryCount"] = count
                    meter.observe(snapshot(index + 1), rows)
                result = meter.finish()
                self.assertFalse(result["passed"])
                self.assertIn("destination receipt exceeds the candidate batch", result["failures"][0])
        fault = SpawnWorkBudgetNegative("spawn-work-budget-over-query-batch")
        fault.mutate({"phase": "observe", "samples": [snapshot(1)], "events": events(0)},
                     {"mankey": SUBJECT})
        copied = fault.mutate({"phase": "observe", "samples": [snapshot(2)], "events": events(1)},
                              {"mankey": SUBJECT})
        self.assertTrue(fault.applied)
        destination = next(e["data"] for e in copied["events"]
            if e["data"].get("observation") == "spawn-destination-search")
        self.assertEqual(destination["candidateQueryCount"], 5)

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
