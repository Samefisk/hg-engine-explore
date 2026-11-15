import unittest
from copy import deepcopy
from pathlib import Path
import json
import re
import subprocess
import tempfile

from tools.overworld.devtools_main_loop_probe import (
    NORMAL_MAIN_LOOP_ARM9_TICKS,
    NORMAL_MAIN_LOOP_NATIVE_CYCLES,
    RETURN_SITE,
    SCOPE,
)
from tools.overworld.devtools_unmounted_zero_stutter_measurement import (
    KIND,
    MINIMUM_FRAMES,
    MAX_DESTINATION_SCAN_FRAME_SPAN,
    UnmountedZeroStutterMeasurement,
)
from tools.overworld.devtools_unmounted_zero_stutter_proof import (
    FAULTS,
    UnmountedZeroStutterNegative,
    contract,
    measurements,
    validate_negative_result,
)
from tools.overworld.test_spawn_spatial import extract_function
from tools.overworld.test_devtools_spawn_priority import creation_fixture


HANDLE = {
    "value": 65543, "slot": 7, "generation": 1,
    "fieldEpoch": 2, "mapGeneration": 2, "encounterGeneration": 1,
}
SOURCE = "a" * 64
FINGERPRINT = 12345678
MATCHED_MASK = 32
ROOT = Path(__file__).resolve().parents[2]
SPAWNER_SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
SCHEMA = {
    "compactSize": 80,
    "fields": [
        {"key": "hopMaxDistance", "cType": "u8", "offset": 21},
        {"key": "hopPause", "cType": "u8", "offset": 22},
    ],
}
PROFILE = bytearray(216)
PROFILE[21] = 6
PROFILE[22] = 5
PROFILE[188:192] = MATCHED_MASK.to_bytes(4, "little")
PROFILE[192:196] = FINGERPRINT.to_bytes(4, "little")
REQUEST = bytearray(44)
REQUEST[:2] = (56).to_bytes(2, "little")
REQUEST[38] = 2
PROFILE_RECEIPT = {
    "requestHex": REQUEST.hex(), "resultHex": PROFILE.hex(),
    "resolved": True, "fingerprint": FINGERPRINT,
    "sourceSha256": SOURCE,
    "lanes": [PROFILE[offset:offset + 80].hex() for offset in (0, 80)],
    "appliedOverrides": MATCHED_MASK,
}


def profile_receipt(fingerprint, mask):
    profile = bytearray(PROFILE)
    profile[188:192] = mask.to_bytes(4, "little")
    profile[192:196] = fingerprint.to_bytes(4, "little")
    return {
        "requestHex": REQUEST.hex(), "resultHex": profile.hex(),
        "resolved": True, "fingerprint": fingerprint,
        "sourceSha256": SOURCE,
        "lanes": [profile[offset:offset + 80].hex()
                  for offset in (0, 80)],
        "appliedOverrides": mask,
    }
SUBJECT = {
    "id": "mankey", "species": 56, "role": "FOLLOWER",
    "subjectIdentity": 2920357538, "identityVerified": True, "active": True,
    "handle": HANDLE, "authorityGeneration": 1,
    "engineAnchorGeneration": 1, "presentationGeneration": 1,
    "behaviorFingerprint": FINGERPRINT, "matchedLayerMask": MATCHED_MASK,
}


def recipe():
    return {
        "mode": "normal",
        "fixture": {"rom": "test.nds", "save": "test.sav"},
        "subjects": [{
            "id": "mankey", "species": 56,
            "role": "FOLLOWER", "acquire": "existing",
        }],
    }


BIRTH_ACTOR = creation_fixture()[0]["actors"][-1]
NEXT_REFILL_FRAME = 300 + MAX_DESTINATION_SCAN_FRAME_SPAN - 1 + 70


def snapshot(frame, *, anchor=False):
    offset = max(0, frame - 101)
    hop_index = offset // 10
    x = 565 if anchor else 566 + offset // 4
    previous = x if anchor else x - 1
    result = {
        "frame": frame,
        "nativeCycle": frame * 2,
        "actorFrame": frame,
        "context": {"mapId": 67, "fieldEpoch": 2, "mapGeneration": 2},
        "player": {
            "x": x, "y": 398, "x_prev": previous, "y_prev": 398,
            "pos_x": (565 << 16) + 32768 + offset * 16384,
            "pos_z": (398 << 16) + 32768,
            "movement_cmd": 91, "movement_step": 1,
        },
        "observationBoundary": "main-task-queue-completion",
        "fieldAvailable": True,
        "fieldControl": {"taskPointer": 0, "fieldPointer": 0x2200000},
        "nativeObservation": {
            "sequence": frame, "coverageComplete": True,
            "error": None, "eventsDropped": 0,
            "resolvedProfiles": [deepcopy(PROFILE_RECEIPT)],
        },
        "actors": [{
            **SUBJECT,
            "logical": {"x": x - 10, "y": 398},
            "origin": {"x": x - 10 + hop_index, "y": 398},
            "target": {"x": x - 9 + hop_index, "y": 398},
            "reservationId": hop_index + 1,
            "commitSequence": hop_index,
            "motionKind": "HOP",
            "motionPhase": "MOVING" if offset % 10 < 5 else "SETTLING",
            "motionDuration": 5,
            "motionElapsed": min(offset % 10, 5),
        }] + ([{
            "active": True, "species": 19, "role": "WILD",
        }] if frame < 300 or frame >= 300 + MAX_DESTINATION_SCAN_FRAME_SPAN else []),
    }

    if frame >= 300 + MAX_DESTINATION_SCAN_FRAME_SPAN - 1:
        result["actors"] = [a for a in result["actors"] if a.get("role") != "WILD"] + [deepcopy(BIRTH_ACTOR)]
    return result


def pacing_event(frame):
    return {"frame": frame, "kind": "native-observation", "data": {
        "observation": "stock-main-loop-pacing",
        "setupMode": "normal", "returnSite": RETURN_SITE, "scope": SCOPE,
        "diagnosticOnly": False, "acceptedProof": False,
        "afterQueueFrame": frame - 1, "flushedAtQueueFrame": frame,
        "frameCounter": 2,
        "intervalFromPrevious": {
            "arm9Ticks": NORMAL_MAIN_LOOP_ARM9_TICKS,
            "arm7Ticks": NORMAL_MAIN_LOOP_ARM9_TICKS // 2,
            "frameSequence": NORMAL_MAIN_LOOP_NATIVE_CYCLES,
            "actorFrames": 1,
            "nativeCycles": NORMAL_MAIN_LOOP_NATIVE_CYCLES,
        },
    }}


def refill_event(frame, attempt, *, queued=False):
    return {"frame": frame, "kind": "native-observation", "data": {
        "observation": "spawn-queued", "setupMode": "normal",
        "spawnAttemptId": attempt, "sequence": frame * 10, "terrain": 0,
        "slot": 1, "entryActorFrame": frame, "returnActorFrame": frame,
        "entryNativeCycle": frame * 2, "returnNativeCycle": frame * 2,
        "returnValue": int(queued), "queued": queued,
        **({"finalizationId": attempt, "pendingDestination": True} if queued else {}),
        "worldContext": {"fieldEpoch": 2, "mapGeneration": 2, "mapId": 67,
                         "fieldPointer": 0x2200000, "statePointer": 0x2300000},
    }}


def run(fault=None):
    meter = UnmountedZeroStutterMeasurement(
        recipe(), {"schema": SCHEMA, "sourceSha256": SOURCE}, max_frames=4000)
    initial = snapshot(100)
    initial["context"]["mapId"] = 33
    initial["player"].update(x=585, y=406, x_prev=585, y_prev=406)
    meter.arm(SUBJECT, initial)
    negative = UnmountedZeroStutterNegative(fault) if fault else None
    for frame in range(101, 102 + MINIMUM_FRAMES):
        sample = snapshot(frame, anchor=frame == 101)
        events = [pacing_event(frame)]
        if 300 <= frame <= 300 + MAX_DESTINATION_SCAN_FRAME_SPAN:
            attempt_id = 1 if frame < 300 + MAX_DESTINATION_SCAN_FRAME_SPAN else 2
            identity = {
                "setupMode": "normal", "spawnAttemptId": attempt_id,
                "finalizationId": frame - 299, "slot": 1,
                "worldContext": {
                    "fieldEpoch": 2, "mapGeneration": 2, "mapId": 67,
                    "fieldPointer": 0x2200000, "statePointer": 0x2300000,
                },
            }
            events.extend([
                {"frame": frame, "kind": "native-observation", "data": {
                    "observation": "spawn-destination-search", **identity}},
                {"frame": frame, "kind": "native-observation", "data": {
                    "observation": "spawn-finalized", **identity}},
            ])
        scan_end = 300 + MAX_DESTINATION_SCAN_FRAME_SPAN - 1
        if frame in (scan_end, NEXT_REFILL_FRAME, NEXT_REFILL_FRAME + 1):
            events.append(refill_event(frame, {scan_end: 1, NEXT_REFILL_FRAME: 2, NEXT_REFILL_FRAME + 1: 3}[frame],
                                       queued=frame == scan_end))
        if frame == scan_end:
            sample, birth_events = creation_fixture(frame, sample=sample)
            events.extend(birth_events)
        row = {"phase": "observe", "samples": [sample], "events": events}
        if negative:
            row = negative.mutate(row, {"mankey": SUBJECT})
        meter.observe(row["samples"][0], row["events"])
    return meter.finish()


class UnmountedZeroStutterTests(unittest.TestCase):
    def refill_interval(self, raw_delay, gap):
        meter = UnmountedZeroStutterMeasurement(
            recipe(), {"schema": SCHEMA, "sourceSha256": SOURCE}, max_frames=4000)
        sample, events = creation_fixture(320, sample=snapshot(320))
        entry = events[-1]["data"]["entry"]
        entry.update(refillDelay=raw_delay, value=3 | (raw_delay << 8))
        meter._observe_refill_interval(sample, events)
        meter._observe_refill_interval(snapshot(320 + gap), [refill_event(320 + gap, 2)])
        return meter.result()["refillIntervals"]

    def test_sparse_refill_uses_eight_frames_and_rejects_seven(self):
        for raw_delay in (60, 120, 180):
            with self.subTest(raw_delay=raw_delay):
                result = self.refill_interval(raw_delay, 8)
                self.assertEqual(result["count"], 1)
                self.assertEqual(result["minimumActorFrames"], 8)
                self.assertEqual(result["witnesses"][0]["rawRefillDelay"], raw_delay)
                self.assertEqual(result["witnesses"][0]["requiredActorFrames"], 8)
                with self.assertRaisesRegex(ValueError, "bypassed its base interval"):
                    self.refill_interval(raw_delay, 7)

    def test_dense_refill_keeps_its_full_native_delay(self):
        for raw_delay in (240, 300, 360):
            with self.subTest(raw_delay=raw_delay):
                result = self.refill_interval(raw_delay, raw_delay)
                self.assertEqual(result["witnesses"][0]["requiredActorFrames"], raw_delay)
                with self.assertRaisesRegex(ValueError, "bypassed its base interval"):
                    self.refill_interval(raw_delay, raw_delay - 1)

    def test_refill_mapping_matches_current_resident_schedule(self):
        source = SPAWNER_SOURCE.read_text()
        names = ("OW_WILD_REFILL_BASE_INTERVAL_FRAMES",
                 "OW_WILD_REFILL_FULL_DENSITY_COUNT",
                 "OW_WILD_REFILL_SPARSE_INTERVAL_FRAMES")
        constants = []
        for name in names:
            found = re.findall(r"^#define " + name + r" \d+$", source, re.M)
            self.assertEqual(len(found), 1)
            constants.extend(found)
        function = extract_function(source, "OverworldWildSpawns_ApplyRefillDelay", "void")
        native = "\n".join(constants) + r'''
#include <stdio.h>
typedef unsigned short u16;
#define OVERWORLD_ACTOR_POPULATION_CONTROL_SCHEDULE_REFILL 1
static unsigned scheduled;
static int OverworldWildSpawns_PopulationControl(int operation, unsigned value)
{ if (operation != 1) return 0; scheduled = value; return 1; }
''' + function + r'''
int main(void) {
    for (unsigned raw = 60; raw <= 360; raw += 60) {
        OverworldWildSpawns_ApplyRefillDelay(raw);
        printf("%u\n", scheduled + 1);
    }
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix="zero-refill-policy-") as temp:
            source_path, binary = Path(temp) / "check.c", Path(temp) / "check"
            source_path.write_text(native)
            subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                            str(source_path), "-o", str(binary)],
                           check=True, capture_output=True, text=True)
            scheduled = list(map(int, subprocess.run(
                [str(binary)], check=True, capture_output=True, text=True).stdout.split()))
        self.assertEqual(scheduled, [8, 8, 8, 240, 300, 360])
        for raw_delay, interval in zip(range(60, 361, 60), scheduled):
            self.assertEqual(self.refill_interval(raw_delay, interval)["witnesses"][0][
                "requiredActorFrames"], interval)

    def test_refill_anchor_stays_strict_for_raw_delay_owner_and_constructor(self):
        faults = {
            "retry-delay": lambda d: d["entry"].update(refillDelay=15, value=3 | (15 << 8)),
            "non-density-delay": lambda d: d["entry"].update(refillDelay=8, value=3 | (8 << 8)),
            "packed-delay": lambda d: d["entry"].update(refillDelay=120),
            "wrong-owner": lambda d: d["admission"]["actor"].update(fieldEpoch=3),
            "missing-constructor": lambda d: d["admission"].update(constructorSequence=0),
        }
        for name, mutate in faults.items():
            with self.subTest(fault=name):
                meter = UnmountedZeroStutterMeasurement(
                    recipe(), {"schema": SCHEMA, "sourceSha256": SOURCE}, max_frames=4000)
                sample, events = creation_fixture(320, sample=snapshot(320))
                mutate(events[-1]["data"])
                with self.assertRaisesRegex(ValueError, "creation refill anchor"):
                    meter._observe_refill_interval(sample, events)

    def test_short_refill_fault_applies_seven_frame_copied_clock(self):
        negative = UnmountedZeroStutterNegative("zero-stutter-short-refill-interval")
        negative.active = True
        sample, events = creation_fixture(320, sample=snapshot(320))
        birth = {"phase": "observe", "samples": [sample], "events": events}
        self.assertEqual(negative.mutate(birth, {}), birth)
        queued = {"phase": "observe", "samples": [snapshot(380)],
                  "events": [refill_event(380, 2)]}
        changed = negative.mutate(queued, {})
        self.assertTrue(negative.applied)
        self.assertEqual(changed["samples"][0]["actorFrame"], 327)
        self.assertEqual(changed["events"][0]["data"]["entryActorFrame"], 327)
        self.assertEqual(changed["events"][0]["data"]["returnActorFrame"], 327)
        self.assertEqual(changed["samples"][0]["nativeCycle"], queued["samples"][0]["nativeCycle"])
        self.assertEqual(queued["samples"][0]["actorFrame"], 380)
        meter = UnmountedZeroStutterMeasurement(
            recipe(), {"schema": SCHEMA, "sourceSha256": SOURCE}, max_frames=4000)
        meter._observe_refill_interval(sample, events)
        with self.assertRaisesRegex(ValueError, "bypassed its base interval"):
            meter._observe_refill_interval(changed["samples"][0], changed["events"])

    def test_registered_refill_contract_matches_checked_rows(self):
        table = json.loads((ROOT / "tools/overworld/runtime_proof_registry.json").read_text())
        self.assertEqual(table["sharedTests"]["world.unmounted.spawn-zero-stutter"][
            "measurementContract"], contract())

    def test_refill_fault_ignores_nonordinary_success_until_real_constructor(self):
        for fault in ("zero-stutter-short-refill-interval", "zero-stutter-stale-refill-owner"):
            with self.subTest(fault=fault):
                negative = UnmountedZeroStutterNegative(fault)
                negative.active = True
                nonordinary = {"phase": "observe", "samples": [snapshot(300)], "events": [{
                    "frame": 300, "kind": "native-observation", "data": {
                        "observation": "entry-native-control", "returnActorFrame": 300,
                        "entry": {"operation": 7, "outcome": 3, "value": 3, "refillDelay": 0}}}]}
                self.assertEqual(negative.mutate(nonordinary, {}), nonordinary)
                queue = {"phase": "observe", "samples": [snapshot(301)],
                         "events": [refill_event(301, 1)]}
                self.assertEqual(negative.mutate(queue, {}), queue)
                self.assertFalse(negative.applied)
                self.assertIsNone(negative.refill_success_frame)
                sample, events = creation_fixture(320, sample=snapshot(320))
                with self.assertRaisesRegex(ValueError, "lacks its exact constructor"):
                    negative.mutate({"phase": "observe", "samples": [sample],
                                     "events": [events[-1]]}, {})
                self.assertFalse(negative.applied)
                self.assertIsNone(negative.refill_success_frame)
                negative.mutate({"phase": "observe", "samples": [sample], "events": events}, {})
                queue = {"phase": "observe", "samples": [snapshot(380)],
                         "events": [refill_event(380, 2)]}
                changed = negative.mutate(queue, {})
                self.assertTrue(negative.applied)
                self.assertNotEqual(changed, queue)
                self.assertEqual(negative.refill_success_frame, 320)

    def test_proof_checks_each_native_density_wait_and_its_summary(self):
        result = run()
        record = {"sessionId": "test", "sessionCleanup": {
            "sessionId": "test", "closed": True, "errors": []}}
        def checked(refill):
            copied = deepcopy(result)
            copied["refillIntervals"] = refill
            return measurements({"passed": True, "failures": [],
                                 "measurements": {KIND: copied}}, record)
        for raw_delay, gap in ((60, 8), (120, 8), (180, 8), (240, 240)):
            self.assertTrue(all(row["passed"] for row in checked(
                self.refill_interval(raw_delay, gap))))
        valid = self.refill_interval(240, 240)
        faults = {
            "missing-native-delay": lambda r: r["witnesses"][0].pop("rawRefillDelay"),
            "retry-delay": lambda r: r["witnesses"][0].update(rawRefillDelay=15),
            "invented-sparse-delay": lambda r: r["witnesses"][0].update(rawRefillDelay=8),
            "dense-as-sparse": lambda r: r["witnesses"][0].update(requiredActorFrames=8),
            "dense-early": lambda r: r["witnesses"][0].update(
                actorFrames=239, nextEntryActorFrame=559),
            "false-actor-gap": lambda r: r["witnesses"][0].update(nextEntryActorFrame=561),
            "false-minimum": lambda r: r.update(minimumActorFrames=241),
            "missing-witness": lambda r: r.update(witnesses=[]),
        }
        for name, mutate in faults.items():
            with self.subTest(fault=name):
                copied = deepcopy(valid)
                mutate(copied)
                with self.assertRaisesRegex(ValueError, "zero-stutter refill"):
                    checked(copied)

    def test_due_actor_choices_are_not_round_robin_serialized(self):
        source = SPAWNER_SOURCE.read_text()
        function = extract_function(
            source, "OverworldWildSpawns_SelectIdleAiWork", "u16")
        self.assertIn("return eligibleMask;", function)
        self.assertNotIn("eligibleMask & slotMask", function)

    def test_blocked_hops_keep_the_resolved_lane_clock(self):
        source = SPAWNER_SOURCE.read_text()
        directed = extract_function(
            source,
            "OverworldWildSpawns_TryStartDirectedBehaviorHopCommand",
            "BOOL")
        blocked = directed.split("blocked:", 1)[1]
        self.assertIn("->hopPause", blocked)
        self.assertNotIn("OW_WILD_SPAWNER_DEFAULT_MOVEMENT_PAUSE_FRAMES", blocked)

        chill = extract_function(
            source, "OverworldWildSpawns_TryStartChillWanderCommand", "BOOL")
        self.assertIn("lane->hopPause", chill)
        self.assertIn("lane->walkPause", chill)
        self.assertNotIn("OW_WILD_SPAWNER_DEFAULT_MOVEMENT_PAUSE_FRAMES", chill)

        startup = extract_function(
            source, "OverworldWildSpawns_SetPostSpawnStartupCooldown", "void")
        self.assertIn("lane->hopPause", startup)
        self.assertIn("lane->walkPause", startup)
        self.assertIn("lane->teleportPause", startup)
        self.assertNotIn("OW_WILD_SPAWNER_DEFAULT_MOVEMENT_PAUSE_FRAMES", startup)

    def test_arm_uses_the_excluded_initial_profile_cache(self):
        meter = UnmountedZeroStutterMeasurement(
            recipe(), {"schema": SCHEMA, "sourceSha256": SOURCE}, max_frames=4000)
        initial = snapshot(100)
        initial["context"]["mapId"] = 33
        initial["player"].update(x=585, y=406, x_prev=585, y_prev=406)
        initial["nativeObservation"]["resolvedProfiles"] = []
        result = meter.arm(
            SUBJECT, initial, resolved_profiles=[deepcopy(PROFILE_RECEIPT)])
        self.assertEqual(result["hopRhythm"]["profilePauseFrames"], 5)
        self.assertEqual(result["hopRhythm"]["profileMaxDistance"], 6)

    def test_arm_rejects_wrong_hop_pause(self):
        meter = UnmountedZeroStutterMeasurement(
            recipe(), {"schema": SCHEMA, "sourceSha256": SOURCE}, max_frames=4000)
        initial = snapshot(100)
        initial["context"]["mapId"] = 33
        initial["player"].update(x=585, y=406, x_prev=585, y_prev=406)
        profile = bytearray(PROFILE)
        profile[22] = 4
        receipt = {
            **PROFILE_RECEIPT,
            "resultHex": profile.hex(),
            "lanes": [profile[offset:offset + 80].hex()
                      for offset in (0, 80)],
        }
        initial["nativeObservation"]["resolvedProfiles"] = [receipt]
        with self.assertRaisesRegex(ValueError, "resolved Mankey profile changed"):
            meter.arm(SUBJECT, initial)

    def test_pre_window_field_rebind_keeps_same_follower_current(self):
        meter = UnmountedZeroStutterMeasurement(
            recipe(), {"schema": SCHEMA, "sourceSha256": SOURCE}, max_frames=4000)
        initial = snapshot(100)
        initial["context"]["mapId"] = 33
        initial["player"].update(x=585, y=406, x_prev=585, y_prev=406)
        meter.arm(SUBJECT, initial)
        arrived = snapshot(101)
        arrived["context"].update(fieldEpoch=3, mapGeneration=3)
        arrived["actors"][0] = {
            **SUBJECT,
            "handle": {**HANDLE, "fieldEpoch": 3, "mapGeneration": 3},
        }
        result = meter.observe(arrived, [pacing_event(101)])
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["subject"]["handle"]["fieldEpoch"], 3)

    def test_conditional_profile_change_preserves_verified_base_profile(self):
        meter = UnmountedZeroStutterMeasurement(
            recipe(), {"schema": SCHEMA, "sourceSha256": SOURCE}, max_frames=4000)
        initial = snapshot(100)
        initial["context"]["mapId"] = 33
        initial["player"].update(x=585, y=406, x_prev=585, y_prev=406)
        meter.arm(SUBJECT, initial)
        fingerprint = FINGERPRINT + 1
        mask = MATCHED_MASK + 1
        rebound = {
            **SUBJECT,
            "behaviorFingerprint": fingerprint,
            "matchedLayerMask": mask,
            "handle": {**HANDLE, "fieldEpoch": 3, "mapGeneration": 3},
        }
        arrived = snapshot(101, anchor=True)
        arrived["context"].update(fieldEpoch=3, mapGeneration=3)
        arrived["actors"][0] = rebound
        arrived["nativeObservation"]["resolvedProfiles"] = [
            profile_receipt(fingerprint, mask)
        ]
        result = meter.observe(arrived, [pacing_event(101)])
        self.assertEqual(result["failures"], [])
        current = snapshot(102)
        current["context"].update(fieldEpoch=3, mapGeneration=3)
        current["actors"][0] = rebound
        current["nativeObservation"]["resolvedProfiles"] = [
            profile_receipt(fingerprint, mask)
        ]
        result = meter.observe(current, [pacing_event(102)])
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["hopRhythm"]["profileFingerprint"], FINGERPRINT)
        self.assertEqual(result["hopRhythm"]["profileMask"], MATCHED_MASK)
        self.assertEqual(
            result["hopRhythm"]["profileSubjectIdentity"],
            SUBJECT["subjectIdentity"],
        )
        self.assertEqual(result["hopRhythm"]["profileSourceSha256"], SOURCE)

    def test_pre_window_field_rebind_rejects_replacement_actor(self):
        meter = UnmountedZeroStutterMeasurement(
            recipe(), {"schema": SCHEMA, "sourceSha256": SOURCE}, max_frames=4000)
        initial = snapshot(100)
        initial["context"]["mapId"] = 33
        initial["player"].update(x=585, y=406, x_prev=585, y_prev=406)
        meter.arm(SUBJECT, initial)
        arrived = snapshot(101)
        arrived["context"].update(fieldEpoch=3, mapGeneration=3)
        arrived["actors"][0] = {
            **SUBJECT,
            "handle": {
                **HANDLE, "value": 131079, "generation": 2,
                "fieldEpoch": 3, "mapGeneration": 3,
            },
        }
        result = meter.observe(arrived, [pacing_event(101)])
        self.assertIn("changed instead of rebinding", result["failures"][0])

    def test_profile_chain_pause_does_not_gate_spawn_stutter(self):
        meter = UnmountedZeroStutterMeasurement(
            recipe(), {"schema": SCHEMA, "sourceSha256": SOURCE}, max_frames=4000)
        initial = snapshot(100)
        initial["context"]["mapId"] = 33
        initial["player"].update(x=585, y=406, x_prev=585, y_prev=406)
        meter.arm(SUBJECT, initial)
        for frame in range(101, 112):
            sample = snapshot(frame, anchor=frame == 101)
            if frame >= 106:
                sample["actors"][0].update(
                    motionKind="NONE", motionPhase="IDLE", reservationId=0)
            result = meter.observe(sample, [pacing_event(frame)])
        self.assertEqual(result["failures"], [])

    def test_hitch_free_spawn_route_produces_acceptance_rows(self):
        result = run()
        self.assertTrue(result["passed"])
        self.assertEqual(result["frames"], MINIMUM_FRAMES)
        self.assertEqual(result["pacing"]["lateMainLoopCount"], 0)
        self.assertEqual(result["pacing"]["sampleCount"], MINIMUM_FRAMES)
        self.assertGreaterEqual(result["spawnWork"]["joinedWitnessCount"], 1)
        rows = measurements(
            {"passed": True, "failures": [], "measurements": {KIND: result}},
            {"sessionId": "test", "sessionCleanup": {
                "sessionId": "test", "closed": True, "errors": [],
            }},
        )
        self.assertEqual([row["passed"] for row in rows], [True] * 13)

    def test_conditional_final_profile_still_accepts_bound_base_profile(self):
        result = run()
        result["subject"]["behaviorFingerprint"] = FINGERPRINT + 1
        result["subject"]["matchedLayerMask"] = MATCHED_MASK + 1
        rows = measurements(
            {"passed": True, "failures": [], "measurements": {KIND: result}},
            {"sessionId": "test", "sessionCleanup": {
                "sessionId": "test", "closed": True, "errors": [],
            }},
        )
        self.assertEqual([row["passed"] for row in rows], [True] * 13)

    def test_each_copied_fault_fails_for_its_named_reason(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                result = run(fault)
                self.assertFalse(result["passed"])
                validate_negative_result(
                    {"passed": False, "failures": [],
                     "measurements": {KIND: result}},
                    fault,
                )

    def test_refill_counts_next_batch_not_resumed_scan_or_later_terrain(self):
        meter = UnmountedZeroStutterMeasurement(
            recipe(), {"schema": SCHEMA, "sourceSha256": SOURCE}, max_frames=4000)
        meter._observe_refill_interval(snapshot(320), [refill_event(320, 1, queued=True)])
        self.assertEqual(meter.result()["refillIntervals"]["count"], 0)
        birth_sample, birth_events = creation_fixture(320, sample=snapshot(320))
        meter._observe_refill_interval(birth_sample, birth_events)
        # Pending finalizers keep their original attempt and do not admit a batch.
        meter._observe_refill_interval(snapshot(321), [{
            "frame": 321, "kind": "native-observation", "data": {
                "observation": "spawn-finalized", "spawnAttemptId": 1}}])
        meter._observe_refill_interval(snapshot(380), [refill_event(380, 2)])
        # A failed next terrain group can continue one frame later in this batch.
        meter._observe_refill_interval(snapshot(381), [refill_event(381, 3)])
        self.assertEqual(meter.result()["refillIntervals"]["count"], 1)
        self.assertEqual(meter.result()["refillIntervals"]["minimumActorFrames"], 60)
        optional = refill_event(382, 4, queued=True)
        optional["data"].update(terrain=2, slot=6)
        meter._observe_refill_interval(snapshot(382), [optional])
        birth_sample, birth_events = creation_fixture(382, attempt=4, sample=snapshot(382))
        meter._observe_refill_interval(birth_sample, birth_events)
        meter._observe_refill_interval(snapshot(442), [refill_event(442, 5)])
        self.assertEqual(meter.result()["refillIntervals"]["count"], 2)
        self.assertIn("#define OW_WILD_REFILL_BASE_INTERVAL_FRAMES 60", SPAWNER_SOURCE.read_text())

    def test_refill_accepts_native_terrain_slot_pairs(self):
        pairs = [(terrain, slot) for terrain in (0, 1) for slot in range(6)]
        pairs += [(2, 6), (3, 8), (3, 9)]
        for terrain, slot in pairs:
            with self.subTest(terrain=terrain, slot=slot):
                meter = UnmountedZeroStutterMeasurement(
                    recipe(), {"schema": SCHEMA, "sourceSha256": SOURCE}, max_frames=4000)
                event = refill_event(380, 1)
                event["data"].update(terrain=terrain, slot=slot)
                meter._observe_refill_interval(snapshot(380), [event])
                self.assertEqual(meter.refill_last_attempt, 1)
                # A valid failed attempt is still not a real constructor.
                self.assertEqual(meter.result()["refillIntervals"]["count"], 0)

    def test_refill_rejects_follower_and_wrong_terrain_slots(self):
        valid = {(terrain, slot) for terrain in (0, 1) for slot in range(6)}
        valid.update({(2, 6), (3, 8), (3, 9)})
        pairs = [(terrain, slot) for terrain in range(5) for slot in range(-1, 11)
                 if (terrain, slot) not in valid]
        pairs += [(3, True), (True, 8)]
        for terrain, slot in pairs:
            with self.subTest(terrain=terrain, slot=slot):
                meter = UnmountedZeroStutterMeasurement(
                    recipe(), {"schema": SCHEMA, "sourceSha256": SOURCE}, max_frames=4000)
                event = refill_event(380, 1)
                event["data"].update(terrain=terrain, slot=slot)
                with self.assertRaisesRegex(ValueError, "refill interval receipt is invalid"):
                    meter._observe_refill_interval(snapshot(380), [event])

    def test_fishing_refill_keeps_owner_clock_and_reply_guards(self):
        faults = {
            "field": lambda d: d["worldContext"].update(fieldPointer=0x2200004),
            "state": lambda d: d["worldContext"].update(statePointer=0x2300004),
            "epoch": lambda d: d["worldContext"].update(fieldEpoch=3),
            "map-generation": lambda d: d["worldContext"].update(mapGeneration=3),
            "map": lambda d: d["worldContext"].update(mapId=34),
            "actor-clock": lambda d: d.update(returnActorFrame=381),
            "native-clock": lambda d: d.update(entryNativeCycle=761),
            "queue-type": lambda d: d.update(queued=0),
            "reply": lambda d: d.update(returnValue=1),
            "attempt": lambda d: d.update(spawnAttemptId=1),
            "sequence": lambda d: d.update(sequence=3790),
        }
        for name, mutate in faults.items():
            with self.subTest(fault=name):
                meter = UnmountedZeroStutterMeasurement(
                    recipe(), {"schema": SCHEMA, "sourceSha256": SOURCE}, max_frames=4000)
                previous = refill_event(379, 1)
                previous["data"].update(terrain=3, slot=8)
                meter._observe_refill_interval(snapshot(379), [previous])
                event = refill_event(380, 2)
                event["data"].update(terrain=3, slot=8)
                mutate(event["data"])
                reason = ("stale Field owner" if name in
                          ("field", "state", "epoch", "map-generation", "map")
                          else "refill interval receipt is invalid")
                with self.assertRaisesRegex(ValueError, reason):
                    meter._observe_refill_interval(snapshot(380), [event])

    def test_refill_rejects_missing_success_or_stale_state_pointer(self):
        meter = UnmountedZeroStutterMeasurement(
            recipe(), {"schema": SCHEMA, "sourceSha256": SOURCE}, max_frames=4000)
        meter._observe_refill_interval(snapshot(320), [refill_event(320, 1)])
        meter._observe_refill_interval(snapshot(380), [refill_event(380, 2)])
        self.assertEqual(meter.result()["refillIntervals"]["count"], 0)
        bad = refill_event(381, 3)
        bad["data"]["worldContext"]["statePointer"] += 4
        with self.assertRaisesRegex(ValueError, "stale Field owner"):
            meter._observe_refill_interval(snapshot(381), [bad])

    def test_copied_live_hitch_is_five_frame_times(self):
        result = run("zero-stutter-extra-game-frame")
        late = result["pacing"]["firstLateMainLoop"]
        self.assertEqual(late["frameCounter"], 5)
        self.assertEqual(late["intervalFromPrevious"]["nativeCycles"], 5)
        self.assertEqual(late["intervalFromPrevious"]["frameSequence"], 5)
        self.assertEqual(late["intervalFromPrevious"]["arm9Ticks"], 5601900)


if __name__ == "__main__":
    unittest.main()
