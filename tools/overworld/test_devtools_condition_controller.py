"""Host-only contract checks; synthetic rows grant no live game proof."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.overworld.devtools_condition_controller import (
    CONDITION_APPLICATION,
    CONDITION_COOLDOWN,
    CONDITION_DURATION,
    CONDITION_ID,
    HOP_DISTANCE,
    HOP_TRAVEL_FRAMES,
    KIND,
    build_live_controller_fixture,
    restore_live_controller_fixture,
    target_generation_address,
)
from tools.overworld.devtools_condition_controller_measurement import (
    ConditionControllerMeasurement,
)
from tools.overworld.devtools_condition_controller_observer import (
    ADAPTER_OUTCOME_STACK_WORD,
    ADAPTER_STACK_ARGUMENT_BYTES,
    LiveConditionControllerFixture,
    PREPARED_CATALOG_INDICES_OFFSET,
    PREPARED_COUNT_OFFSET,
    PREPARED_VALID_OFFSET,
    RUNTIME_ACTOR_SNAPSHOT_OFFSET,
    RUNTIME_ACTIVE_MASKS_OFFSET,
    RUNTIME_RESULT_OFFSET,
    RUNTIME_RESOLUTION_OFFSET,
    RUNTIME_SCRATCH_OFFSET,
    RUNTIME_TARGET_VALID_OFFSET,
)
from tools.overworld.devtools_condition_controller_proof import (
    CLAIMS,
    copied_control_scope,
    measurements,
    replay,
)
from tools.overworld.devtools_records import select_current_actor


ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / "tests/overworld/test-recipes/profile.condition.live-wild-controller.json"
SCENARIO = ROOT / "tests/overworld/scenarios/profile.condition.live-wild-controller.json"


def source_blob():
    profile_offset = 84
    profile_count = 27
    condition_offset = profile_offset + profile_count * 212
    condition_count = 11
    raw = bytearray(condition_offset + condition_count * 48)
    struct.pack_into("<IHHI", raw, 0, 0x4F574244, 80, 84, len(raw))
    struct.pack_into("<IHH", raw, 36, profile_offset, profile_count, 212)
    struct.pack_into("<IHH", raw, 52, condition_offset, condition_count, 48)

    profile = profile_offset + CONDITION_APPLICATION * 212
    raw[profile + 17] = 1
    raw[profile + 18] = 7
    raw[profile + 19] = 1
    struct.pack_into("<I", raw, profile + 20,
                     (1 << 0) | (1 << 12) | (1 << 13))
    data = profile + 32
    raw[data + 0] = 3
    raw[data + 12] = 2
    raw[data + 13] = 2
    raw[data + 20] = 1
    raw[data + 21] = 2
    raw[data + 36] = 6

    condition = condition_offset + 7 * 48
    struct.pack_into("<HH", raw, condition + 20,
                     CONDITION_DURATION, CONDITION_COOLDOWN)
    struct.pack_into("<H", raw, condition + 32, CONDITION_ID)
    raw[condition + 34:condition + 45] = bytes((
        CONDITION_APPLICATION, 1, 0xFF, 0, 1, 1, 0, 0, 5, 0, 100,
    ))
    return bytes(raw)


def handle(slot, generation, encounter):
    return {
        "value": (generation << 16) | slot,
        "slot": slot,
        "generation": generation,
        "fieldEpoch": 3,
        "mapGeneration": 4,
        "encounterGeneration": encounter,
    }


def actor(slot, generation, encounter, species, role, x, y):
    return {
        "active": True,
        "handle": handle(slot, generation, encounter),
        "subjectIdentity": 1000 + slot,
        "species": species,
        "role": role,
        "form": 0,
        "level": 5,
        "authorityGeneration": 10 + slot,
        "engineAnchorGeneration": 20 + slot,
        "presentationGeneration": 30 + slot,
        "identityVerified": True,
        "presentationAttached": True,
        "motionPhase": "IDLE",
        "motionKind": "NONE",
        "motionDuration": 0,
        "motionElapsed": 0,
        "origin": {"x": x, "y": y},
        "target": {"x": x, "y": y},
        "logical": {"x": x, "y": y},
        "commitSequence": 0,
        "reservationId": 0,
        "engineIdentity": {"pointer": 0x02050000 + slot * 0x200},
    }


def native(frame, sequence, name, subject, value_a=0, value_b=0):
    return {
        "frame": frame,
        "kind": "native",
        "data": {
            "event": name,
            "reason": "OK",
            "actorHandle": subject["handle"]["value"],
            "actor": {key: value for key, value in subject["handle"].items()
                      if key != "value"},
            "sequence": sequence,
            "valueA": value_a,
            "valueB": value_b,
        },
    }


def observation(frame, name, data):
    return {"frame": frame, "kind": "native-observation",
            "data": {"observation": name, **deepcopy(data)}}


def profile_hex():
    raw = bytearray(144)
    raw[0], raw[12], raw[13] = 3, 2, 2
    raw[20], raw[21], raw[36] = 1, 2, 6
    return raw.hex()


def live_rows():
    recipe = json.loads(RECIPE.read_text())
    patched, fixture = build_live_controller_fixture(source_blob())
    del patched
    wild = actor(0, 2, 5, 70, "WILD", 583, 406)
    follower = actor(7, 3, 6, 174, "FOLLOWER", 580, 406)
    context = {"mapId": 33, "fieldEpoch": 3, "mapGeneration": 4,
               "fieldPointer": 0x02010000}

    controlled_state_reset = {
        "stateAddress": target_generation_address(0x02081000, 0) - 10,
        "activeApplicationMaskAddress": (
            0x02080000 + RUNTIME_ACTIVE_MASKS_OFFSET),
        "preparedIndex": 0,
        "stateBeforeHex": "01" + "00" * 15,
        "stateAfterHex": "00" * 16,
        "activeApplicationMaskBeforeHex": "00200000",
        "activeApplicationMaskAfterHex": "00000000",
        "bytesWritten": 20,
        "writeOperations": 2,
        "meaning": ("clear the controlled condition state and its cached "
                    "active profile before the first observed call"),
    }

    def snapshot(frame, *, phase="IDLE", elapsed=0, closed=False,
                 restored=False, writes=5, operations=5):
        current = deepcopy(wild)
        if phase == "MOVING":
            current.update(
                motionPhase="MOVING", motionKind="HOP",
                motionDuration=HOP_TRAVEL_FRAMES,
                motionElapsed=elapsed, origin={"x": 583, "y": 406},
                target={"x": 583 - HOP_DISTANCE, "y": 406}, reservationId=1,
            )
            if elapsed >= HOP_TRAVEL_FRAMES // 2:
                current["logical"] = {"x": 583 - HOP_DISTANCE, "y": 406}
        elif frame >= 113:
            current.update(logical={"x": 583 - HOP_DISTANCE, "y": 406},
                           origin={"x": 583 - HOP_DISTANCE, "y": 406},
                           target={"x": 583 - HOP_DISTANCE, "y": 406},
                           commitSequence=1)
        completed_calls = 0 if frame == 100 else 1 if frame == 101 else \
            2 if frame < 114 else 3
        reader = {
            "armed": True,
            "closed": closed,
            "failure": None,
            "acceptedProof": False,
            "subject": deepcopy(subject),
            "startFrame": 100,
            "fixture": deepcopy(fixture),
            "catalogPatch": {
                "applied": True,
                "restored": restored,
                "restoredSha256": fixture["sourceSha256"] if restored else None,
            },
            "callbacks": {
                "adapterEvaluate": {"address": 0x023B6B00,
                                    "entrySha256": "a" * 64,
                                    "entered": completed_calls,
                                    "returned": completed_calls,
                                    "nonmatchingEntries": 0},
                "wildEvaluate": {"address": 0x023D0000,
                                 "entrySha256": "b" * 64,
                                 "entered": completed_calls,
                                 "returned": completed_calls,
                                 "nonmatchingEntries": 0},
            },
            "counts": {"adapter": completed_calls,
                       "wrapper": completed_calls},
            "controlledStateReset": (
                deepcopy(controlled_state_reset) if frame >= 101 else None),
            "guestMemoryWriteBytes": writes,
            "guestMemoryWriteOperations": operations,
            "hookCleanup": {"removed": closed, "errors": []},
        }
        return {
            "frame": frame,
            "nativeCycle": frame * 2,
            "actorFrame": frame,
            "context": deepcopy(context),
            "actors": [current, deepcopy(follower)],
            "conditionController": reader,
        }

    baseline = {
        "frame": 100,
        "nativeCycle": 200,
        "actorFrame": 100,
        "context": deepcopy(context),
        "actors": [deepcopy(wild), deepcopy(follower)],
    }
    subject = select_current_actor(baseline, wild)

    success = {
        "subject": deepcopy(subject),
        "caller": "OverworldWildSpawns_EvaluateConditionsForSlot",
        "slot": 0,
        "status": 0,
        "motionAtEntry": {"phase": "IDLE", "kind": "NONE"},
        "runtimePointer": 0x02080000,
        "statePointer": 0x02081000,
        "condition": {
            "id": CONDITION_ID,
            "applicationIndex": CONDITION_APPLICATION,
            "conditionTrue": True,
            "active": True,
            "timed": True,
            "triggered": True,
            "durationFrames": CONDITION_DURATION,
            "cooldownFrames": CONDITION_COOLDOWN,
        },
        "activeApplicationMask": 1 << CONDITION_APPLICATION,
        "resolvedTarget": {
            "kind": "ACTOR", "role": "FOLLOWER",
            "handle": deepcopy(follower["handle"]),
            "position": [580, 406],
        },
        "targetValid": True,
        "profileHex": profile_hex(),
    }
    wrapper = {
        "subject": deepcopy(subject), "slot": 0,
        "motionAtEntry": {"phase": "IDLE", "kind": "NONE"},
        "resultFlags": 0,
        "activeApplicationMaskAfter": 1 << CONDITION_APPLICATION,
        "targetValidAfter": True,
    }
    prepared_index = 0
    fault = {
        "subject": deepcopy(subject),
        "runtimePointer": 0x02080000,
        "statePointer": 0x02081000,
        "preparedIndex": prepared_index,
        "targetHandle": deepcopy(follower["handle"]),
        "before": follower["handle"]["generation"],
        "after": follower["handle"]["generation"] + 1,
        "address": target_generation_address(0x02081000, prepared_index),
        "bytesWritten": 2,
        "actorTargetUnchanged": True,
        "motionAtWrite": {"phase": "MOVING", "kind": "HOP"},
    }

    samples = []
    events = []
    for frame in range(101, 115):
        moving = 102 <= frame <= 112
        samples.append(snapshot(
            frame,
            phase="MOVING" if moving else "IDLE",
            elapsed=max(0, frame - 102),
            writes=27 if frame >= 102 else 25,
            operations=8 if frame >= 102 else 7,
        ))
    first = deepcopy(success)
    first["condition"]["triggered"] = True
    first_wrapper = deepcopy(wrapper)
    first_wrapper["resultFlags"] = 1
    events.extend([
        observation(101, "condition-controller-evaluate", first),
        observation(101, "condition-controller-wrapper", first_wrapper),
    ])
    second = deepcopy(success)
    second["condition"]["triggered"] = False
    events.extend([
        native(102, 1, "INTENT_CREATED", subject),
        native(102, 2, "MOTION_STARTED", subject, 2, HOP_TRAVEL_FRAMES),
        observation(102, "condition-controller-evaluate", second),
        observation(102, "condition-controller-wrapper", wrapper),
        observation(102, "condition-controller-target-staled", fault),
        native(113, 3, "LOGICAL_COMMIT", subject, 1, 1),
        native(113, 4, "MOTION_FINISHED", subject, 1, 1),
        native(113, 5, "CONTROL_RETURNED", subject, 0, 1),
    ])
    stale = {
        "subject": deepcopy(subject),
        "caller": "OverworldWildSpawns_EvaluateConditionsForSlot",
        "slot": 0,
        "status": 3,
        "motionAtEntry": {"phase": "IDLE", "kind": "NONE"},
        "runtimePointer": 0x02080000,
        "staleTarget": fault["after"],
        "activeApplicationMask": 0,
        "targetValid": False,
    }
    failed_wrapper = deepcopy(wrapper)
    failed_wrapper.update(resultFlags=4, activeApplicationMaskAfter=0,
                          targetValidAfter=False)
    events.extend([
        observation(114, "condition-controller-evaluate", stale),
        observation(114, "condition-controller-wrapper", failed_wrapper),
    ])

    arm_snapshot = snapshot(100)
    close_snapshot = snapshot(114, closed=True, restored=True,
                              writes=32, operations=13)
    rows = [
        {
            "phase": "observe", "action": recipe["actions"][0]["id"],
            "command": "condition-controller.arm",
            "snapshot": arm_snapshot,
            "receipt": {"conditionController":
                        deepcopy(arm_snapshot["conditionController"])},
        },
        {
            "phase": "observe", "action": recipe["actions"][1]["id"],
            "command": "wait", "samples": samples, "events": events,
        },
        {
            "phase": "observe", "action": recipe["actions"][2]["id"],
            "command": "condition-controller.close",
            "snapshot": close_snapshot,
            "receipt": {
                "conditionController":
                    deepcopy(close_snapshot["conditionController"]),
                "advancedFrames": 0,
            },
        },
    ]
    return recipe, rows


def replay_direct(recipe, rows):
    arm, wait, close = rows
    meter = ConditionControllerMeasurement(recipe, max_frames=240)
    reader = arm["receipt"]["conditionController"]
    meter.arm(reader["subject"], arm["snapshot"], arm["receipt"])
    by_frame = {}
    for event in wait["events"]:
        by_frame.setdefault(event["frame"], []).append(event)
    for sample in wait["samples"]:
        meter.observe(sample, by_frame.get(sample["frame"], []))
    meter.close(close["snapshot"], close["receipt"])
    return meter.result()


class FixtureSession:
    def __init__(self, source, root):
        self.prepared = True
        self.emu = object()
        self.native_bridge_active = False
        self.rt = SimpleNamespace(REPO=root)
        self.address = 0x02020000
        self.memory = bytearray(source)
        self.writes = []
        self.native_observation = SimpleNamespace(resolver_discovery={
            "status": 0,
            "blobAddress": self.address,
            "blobSize": len(source),
        })

    def read(self, address, size):
        start = address - self.address
        return bytes(self.memory[start:start + size])

    def write(self, address, value):
        start = address - self.address
        self.memory[start:start + len(value)] = value
        self.writes.append((address, bytes(value)))


class ConditionControllerTests(unittest.TestCase):
    def test_five_byte_fixture_and_exact_restore(self):
        source = source_blob()
        patched, receipt = build_live_controller_fixture(source)
        changed = [index for index, pair in enumerate(zip(source, patched))
                   if pair[0] != pair[1]]
        self.assertEqual(changed,
                         [item["offset"] for item in receipt["changes"]])
        self.assertEqual(len(changed), 5)
        self.assertEqual(restore_live_controller_fixture(patched, receipt),
                         source)
        self.assertEqual(receipt["condition"]["targetRole"], "FOLLOWER")
        self.assertEqual(receipt["profile"]["id"], "ambush")

    def test_fixture_rejects_changed_authored_contract(self):
        source = bytearray(source_blob())
        condition_offset = struct.unpack_from("<I", source, 52)[0] + 7 * 48
        source[condition_offset + 44] = 99
        with self.assertRaisesRegex(ValueError, "authored Ambush"):
            build_live_controller_fixture(bytes(source))

    def test_live_fixture_writes_and_restores_only_five_catalog_bytes(self):
        source = source_blob()
        with tempfile.TemporaryDirectory() as directory:
            build_path = Path(directory) / "build/OverworldWildBehaviorData.bin"
            build_path.parent.mkdir(exist_ok=True)
            build_path.write_bytes(source)
            session = FixtureSession(source, Path(directory))
            fixture = LiveConditionControllerFixture(session)
            applied = fixture.apply()
            self.assertEqual(applied["guestMemoryWriteBytes"], 5)
            self.assertEqual(len(session.writes), 5)
            self.assertNotEqual(bytes(session.memory), source)
            restored = fixture.restore()
            self.assertEqual(restored["guestMemoryWriteBytes"], 10)
            self.assertEqual(len(session.writes), 10)
            self.assertEqual(bytes(session.memory), source)

    def test_runtime_offsets_and_generation_address_are_pinned(self):
        self.assertEqual(ADAPTER_STACK_ARGUMENT_BYTES, 36)
        self.assertEqual(ADAPTER_OUTCOME_STACK_WORD, 8)
        self.assertEqual(PREPARED_CATALOG_INDICES_OFFSET, 16)
        self.assertEqual(PREPARED_COUNT_OFFSET, 48)
        self.assertEqual(PREPARED_VALID_OFFSET, 49)
        self.assertEqual(RUNTIME_SCRATCH_OFFSET, 520)
        self.assertEqual(RUNTIME_RESULT_OFFSET, 552)
        self.assertEqual(RUNTIME_RESOLUTION_OFFSET, 1136)
        self.assertEqual(RUNTIME_ACTOR_SNAPSHOT_OFFSET, 1772)
        self.assertEqual(RUNTIME_ACTIVE_MASKS_OFFSET, 1948)
        self.assertEqual(RUNTIME_TARGET_VALID_OFFSET, 2068)
        self.assertEqual(target_generation_address(0x02081000, 3),
                         0x02081000 + 3 * 16 + 10)

    def test_closed_replay_proves_exact_six_claims(self):
        recipe, rows = live_rows()
        result = replay(recipe, rows)
        self.assertTrue(result["passed"])
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["observedFrames"], 14)
        record = {"sessionId": "synthetic", "sessionCleanup": {
            "sessionId": "synthetic", "closed": True, "errors": []}}
        values = measurements(result, record)
        self.assertEqual(tuple(item["claim"] for item in values), CLAIMS)
        self.assertEqual(copied_control_scope(),
                         "copied evaluator controls only; not live reader calibration")

    def test_closed_replay_accepts_normalized_final_wait(self):
        recipe, rows = live_rows()
        recipe["actions"][1]["args"]["predicate"]["when"] = "final"
        self.assertTrue(replay(recipe, rows)["passed"])

    def test_closed_replay_combines_live_per_frame_wait_rows(self):
        recipe, rows = live_rows()
        arm, wait, close = rows
        split = []
        for sample in wait["samples"]:
            frame = sample["frame"]
            split.append({
                "phase": "observe",
                "action": wait["action"],
                "samples": [sample],
                "events": [event for event in wait["events"]
                           if event["frame"] == frame],
            })
        self.assertTrue(replay(recipe, [arm, *split, close])["passed"])

    def test_copied_row_faults_fail_the_unchanged_meter(self):
        for fault in (
                "missing-subject", "direct-adapter", "mid-motion-evaluation",
                "wrong-profile", "wrong-target", "missing-stale-write",
                "stale-before-motion", "stale-status",
                "motion-after-fail-close", "catalog-not-restored"):
            recipe, rows = live_rows()
            arm, wait, close = rows
            events = wait["events"]
            evaluate = [item for item in events
                        if item["data"].get("observation")
                        == "condition-controller-evaluate"]
            if fault == "missing-subject":
                arm["snapshot"]["actors"] = arm["snapshot"]["actors"][1:]
            elif fault == "direct-adapter":
                evaluate[0]["data"]["caller"] = \
                    "OverworldBehaviorConditionAdapter_EvaluateActor"
            elif fault == "mid-motion-evaluation":
                extra = deepcopy(evaluate[1])
                extra["frame"] = 103
                events.append(extra)
            elif fault == "wrong-profile":
                evaluate[1]["data"]["profileHex"] = "00" * 144
            elif fault == "wrong-target":
                evaluate[1]["data"]["resolvedTarget"]["role"] = "WILD"
            elif fault == "missing-stale-write":
                events[:] = [item for item in events
                             if item["data"].get("observation")
                             != "condition-controller-target-staled"]
            elif fault == "stale-before-motion":
                target = next(item for item in events
                              if item["data"].get("observation")
                              == "condition-controller-target-staled")
                target["frame"] = 101
            elif fault == "stale-status":
                evaluate[-1]["data"]["status"] = 0
            elif fault == "motion-after-fail-close":
                events.append(native(108, 6, "MOTION_STARTED",
                                     evaluate[-1]["data"]["subject"], 2, 6))
            else:
                close["receipt"]["conditionController"]["catalogPatch"] \
                    ["restored"] = False
            with self.subTest(fault=fault):
                result = replay_direct(recipe, rows)
                self.assertFalse(result["passed"])
                self.assertTrue(result["failures"])

    def test_recipe_and_scenario_keep_the_narrow_scope(self):
        recipe = json.loads(RECIPE.read_text())
        scenario = json.loads(SCENARIO.read_text())
        self.assertEqual(recipe["requirements"],
                         ["current.live-condition-controller"])
        self.assertEqual(recipe["measurements"],
                         [{"kind": KIND, "subject": "weepinbell"}])
        self.assertEqual([item["op"] for item in recipe["actions"]],
                         ["condition-controller.arm", "wait",
                          "condition-controller.close"])
        self.assertEqual([item["op"] for item in recipe["setup"]],
                         ["teleport", "spawn", "spawn", "bind",
                          "condition-controller.fixture"])
        limits = " ".join(scenario["verification"]["limits"])
        self.assertIn("Wild controller only", limits)
        self.assertIn("no Follower-caller role credit", limits)
        self.assertIn("does not prove mounted-follower target exclusion", limits)
        self.assertIn("copied-service-input proof only", limits)


if __name__ == "__main__":
    unittest.main()
