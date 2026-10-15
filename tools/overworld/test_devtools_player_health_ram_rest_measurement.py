"""Production Ram/rest meter and copied-data rejection checks."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

from tools.overworld.control import _replay_shared_test
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_player_health_ram_rest_measurement import (
    PlayerHealthRamRestMeasurement, STEPS, RAM_MASK,
)
from tools.overworld.devtools_player_health_ram_rest_proof import (
    FAULTS, contract, faulted_rows,
)
from tools.overworld.devtools_test_contract import validate_test


RECIPE = Path(__file__).resolve().parents[2] / \
    "tests/overworld/test-recipes/player-hp.ram-rest.json"
OVERLAY = "a" * 64
ROM = hashlib.sha256(b"test-ROM").hexdigest()
SOURCE = {"contractVersion": 1, "overlaySha256": OVERLAY,
          "romSha256": ROM}
HANDLE = {"value": 0x10000, "slot": 0, "generation": 1,
          "fieldEpoch": 1, "mapGeneration": 1,
          "encounterGeneration": 1}
ONIX = {"handle": HANDLE, "subjectIdentity": 123, "species": 95,
        "role": "WILD", "active": True, "presentationAttached": True,
        "identityVerified": True, "authorityGeneration": 1,
        "engineAnchorGeneration": 1, "presentationGeneration": 1,
        "form": 0, "level": 5, "motionPhase": "IDLE",
        "logical": {"x": 585, "y": 411},
        "sourceIdentity": {"active": 1, "species": 95, "personality": 123,
                           "encounter_generation": 1, "object_id": 0xE0,
                           "map_id": 33, "object": 0x02100000},
        "engineIdentity": {"in_manager": True, "active": True,
                           "script_id": 2074, "object_id": 0xE0,
                           "object_map_id": 33, "current_map_id": 33,
                           "pointer": 0x02100000,
                           "current_manager": 0x02110000,
                           "object_manager": 0x02110000,
                           "manager_index": 0}}


def snapshot(frame, map_id, *, moved=False, knocked=False,
             onix=True, onix_y=411):
    actors = [deepcopy(ONIX)] if map_id == 33 and onix else []
    if actors:
        actors[0]["logical"]["y"] = onix_y
    return {"frame": frame, "nativeCycle": frame + 1000,
            "observationBoundary": "main-task-queue-completion",
            "fieldAvailable": True, "fieldControl": {"taskPointer": 0},
            "context": {"mapId": map_id, "fieldEpoch": 1 if map_id == 33 else 2,
                        "mapGeneration": 1 if map_id == 33 else 2},
            "player": {"x": 585 if map_id == 33 else 551 if moved else 550,
                       "y": 404 if map_id == 33 and knocked
                            else 407 if map_id == 33 else 381,
                       "face_y": 0, "movement_cmd": 0},
            "actors": actors}


def health(snap, hp, damage, hits, rest, remainder=0):
    return {"schemaVersion": 1,
            "identity": {"descriptorVersion": 1, "overlayId": 161,
                         "overlaySha256": OVERLAY, "romSha256": ROM},
            "frame": snap["frame"], "nativeCycle": snap["nativeCycle"],
            "hp": hp, "savedHp": hp, "maxHp": 100,
            "lastDamage": damage, "acceptedHits": hits, "restFrames": rest,
            "healRemainder": remainder,
            "lastHealthFrame": snap["frame"], "frameActive": False,
            "recoveryPending": False, "protectionFrames": 0}


def step_row(action, first, count, map_id, *, moved=False, onix_y=411):
    events = []
    samples = [snapshot(first + n, map_id,
                        moved=moved and n == count - 1,
                        knocked=action == "allow-natural-ram" and n >= 87,
                        onix_y=onix_y)
               for n in range(count)]
    if action == "allow-natural-ram":
        for n in range(87, 110):
            player = samples[n]["player"]
            player["y"] = 406 if n < 95 else 405 if n < 103 else 404
            player["face_y"] = 1024 if n < 105 else 0
            player["movement_cmd"] = 62 if n < 109 else 0
        for offset, duration, target_y in ((20, 16, 410), (40, 16, 409),
                                           (60, 12, 408), (80, 8, 407)):
            actor = samples[offset]["actors"][0]
            actor["origin"] = {"x": 585, "y": target_y + 1}
            actor["target"] = {"x": 585, "y": target_y}
            actor["motionDuration"] = duration
            actor["motionElapsed"] = duration
            actor["motionKind"] = "WALK"
            actor["matchedLayerMask"] = RAM_MASK
            request = bytearray(28)
            request[:4] = b"\x01\x00\x1c\x00"
            request[9] = 3
            request[11] = 1
            lane = bytearray(80)
            lane[72:74] = bytes((1, 32))
            before = bytearray(36)
            before[2] = before[25] = duration
            events.append({"kind": "native-observation", "frame": samples[offset]["frame"],
                "data": {"observation": "walk-policy", "slot": 0, "operation": 3,
                    "returnValue": 1, "publicSubject": deepcopy(actor),
                    "requestHex": request.hex(), "laneHex": lane.hex(),
                    "policyBeforeHex": before.hex()}})
    return {"phase": "observe", "action": action,
            "completedGameFrames": count, "observedFieldFrames": count,
            "nativeCycles": count, "samples": samples, "events": events,
            "cycleIntervals": [{"completedGameFrame": sample["frame"],
                                "cpuNs": 1, "wallNs": 1}
                               for sample in samples]}


def rows(*, onix_y=411):
    ram_extra = STEPS["allow-natural-ram"] - 105
    initial = snapshot(10, 33, onix=False)
    ram_tile = snapshot(11, 33, onix=False)
    spawn_tile = snapshot(12, 33, onix_y=onix_y)
    safe = snapshot(125 + ram_extra, 34)
    ram = snapshot(117 + ram_extra, 33, knocked=True, onix_y=onix_y)
    five = snapshot(427 + ram_extra, 34)
    healed = snapshot(487 + ram_extra, 34)
    moving = snapshot(503 + ram_extra, 34, moved=True)
    bound = select_current_actor(spawn_tile, ONIX)
    raw = bytearray(30)
    struct.pack_into("<ii", raw, 0, 585, onix_y)
    struct.pack_into("<IHB B hhhhBB", raw, 12, 123, 95, 0, 5,
                     585, onix_y, 585, onix_y, 7, 0)
    world = spawn_tile["context"]
    prepared = {"slot": 0, "terrain": 0, "statePointer": 0x02120000,
                "fieldPointer": 0x02130000, "preparedPointer": 0x02140000,
                "worldContext": world, "preparedPrefixHex": raw.hex(),
                "preparedEncounter": {"personality": 123, "species": 95,
                                      "form": 0, "level": 5},
                "startup": {"target": [585, onix_y], "origin": [585, onix_y],
                            "locomotion": 7, "hopDirection": 0, "targetBaseY": 0},
                "position": [585, onix_y]}
    final = {**prepared, "returnWorldContext": world, "sequence": 1,
             "returnValue": 1, "pairEligible": True}
    native_spawn = {**prepared, "observation": "spawn-prepared",
                    "returnValue": 1, "sequence": 2,
                    "publicSubject": bound,
                    "finalization": {"status": "matched", "receipt": final}}
    spawn_receipt = {"value": {"species": 95, "slot": 0,
                               "personality": 123},
                     "preparedOnly": True, "snapshot": spawn_tile,
                     "events": [{"kind": "native-observation",
                                 "data": native_spawn}]}
    def read(action, snap, hp, damage, hits, rest, remainder=0):
        return {"phase": "observe", "action": action,
                "command": "player-health.observe", "snapshot": snap,
                "receipt": {"playerHealth": health(snap, hp, damage, hits,
                                                     rest, remainder)}}
    return [
        {"phase": "setup", "initialSnapshot": initial},
        {"phase": "setup", "action": "ram-tile", "command": "teleport",
         "snapshot": ram_tile, "receipt": {}},
        {"phase": "setup", "action": "spawn-onix", "command": "spawn",
         "snapshot": spawn_tile, "receipt": spawn_receipt},
        {"phase": "setup", "action": "bind-onix", "command": "bind",
         "snapshot": spawn_tile, "receipt": bound},
        read("before-ram", spawn_tile, 100, 0, 0, 0),
        step_row("allow-natural-ram", 13, STEPS["allow-natural-ram"], 33, onix_y=onix_y),
        read("after-ram", ram, 67, 33, 1, 0),
        {"phase": "observe", "action": "safe-rest-tile", "command": "teleport",
         "snapshot": safe, "receipt": {"preparedOnly": True, "snapshot": safe}},
        step_row("settle-safe-field", 126 + ram_extra, 2, 34),
        read("before-rest", snapshot(127 + ram_extra, 34), 67, 33, 1, 3),
        step_row("stand-five-seconds", 128 + ram_extra, 300, 34),
        read("after-five-seconds", five, 67, 33, 1, 300, 30),
        step_row("stand-one-more-second", 428 + ram_extra, 60, 34),
        read("after-heal", healed, 77, 33, 1, 300, 30),
        step_row("move-again", 488 + ram_extra, 16, 34, moved=True),
        read("after-move", moving, 80, 33, 1, 300, 10),
    ]


def evaluate(stream):
    meter = PlayerHealthRamRestMeasurement(SOURCE)
    for row in stream:
        progress = meter.observe_record(row)
        if progress["failures"]:
            break
    return meter.finish(), meter.result()


class PlayerHealthRamRestMeasurementTest(unittest.TestCase):
    def test_recipe_and_claims_are_exact(self):
        recipe = validate_test(json.loads(RECIPE.read_text()))
        self.assertEqual(recipe["measurements"],
                         [{"kind": "player-health-ram-rest-v1", "subject": "onix"}])
        self.assertEqual(recipe["budgets"]["minObservedFrames"], sum(STEPS.values()))
        self.assertEqual(set(contract()), {"live-actor-identity", "engine-boundary",
                                           "natural-input", "control-release"})

    def test_exact_game_frames_damage_healing_and_movement(self):
        finished, result = evaluate(rows())
        self.assertTrue(finished["passed"], finished["failures"])
        self.assertEqual((result["observedFrames"], result["hpAfterRam"],
                          result["hpAfterRest"], result["movementHealing"]),
                         (548, 67, 77, True))

    def test_resolved_impact_threshold_accepts_seven_frame_walk(self):
        stream = rows()
        charge = next(row for row in stream if row.get("action") == "allow-natural-ram")
        fast = charge["events"][-1]["data"]
        fast["publicSubject"]["motionDuration"] = fast["publicSubject"]["motionElapsed"] = 7
        before = bytearray.fromhex(fast["policyBeforeHex"])
        before[2] = before[25] = 7
        fast["policyBeforeHex"] = before.hex()
        finished, result = evaluate(stream)
        self.assertTrue(finished["passed"], finished["failures"])
        self.assertEqual(result["completedChargeThresholds"][-1],
                         {"frame": charge["events"][-1]["frame"],
                          "travelTime": 7, "minimumImpactSpeed": 32})

    def test_copied_faults_each_reject(self):
        baseline = rows()
        for fault in FAULTS:
            with self.subTest(fault=fault):
                finished, _ = evaluate(faulted_rows(baseline, fault))
                self.assertFalse(finished["passed"])
                self.assertTrue(finished["failures"])

    def test_missing_completed_frame_fails(self):
        stream = rows()
        stream[5]["samples"][3]["frame"] += 1
        finished, _ = evaluate(stream)
        self.assertFalse(finished["passed"])
        self.assertTrue(any("skip" in failure for failure in finished["failures"]))

    def test_same_boundary_accepts_diagnostic_metadata_but_not_player_change(self):
        stream = rows()
        after_ram = next(row for row in stream if row.get("action") == "after-ram")
        after_ram["snapshot"]["terrain"] = {"readOnly": True}
        after_ram["snapshot"]["nativeObservation"] = {"sequence": 2}
        finished, _ = evaluate(stream)
        self.assertTrue(finished["passed"], finished["failures"])
        after_ram["snapshot"]["player"]["x"] += 1
        finished, _ = evaluate(stream)
        self.assertFalse(finished["passed"])

    def test_controller_replay_uses_the_same_meter_and_controls(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "build").mkdir()
            (root / "test.nds").write_bytes(b"test-ROM")
            (root / "test.sav").write_bytes(b"old save")
            (root / "build/player-health.debug.json").write_text(json.dumps({
                "formatVersion": 1,
                "overlay": {"id": 161, "sha256": OVERLAY},
            }))
            recipe = json.loads(RECIPE.read_text())
            baseline = rows()
            replay = _replay_shared_test(recipe, baseline, repo=root)
            self.assertTrue(replay["passed"], replay["failures"])
            for fault in FAULTS:
                with self.subTest(fault=fault):
                    failed = _replay_shared_test(recipe, faulted_rows(baseline, fault),
                                                 repo=root)
                    self.assertFalse(failed["passed"])
                    self.assertTrue(failed["failures"])


if __name__ == "__main__":
    unittest.main()
