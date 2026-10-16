"""Copied-data checks for the prepared Wild Throw contact proof."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_player_health_throw_contact_measurement import (
    CROSS_FRAMES, KIND, MIN_FRAMES, THROW_APPLICATION_BIT, THROW_RELEASE_BIT,
    THROW_MAX_RANGE,
    PlayerHealthThrowContactMeasurement,
)
from tools.overworld.devtools_player_health_throw_contact_proof import (
    FAULTS, contract, faulted_rows,
)


REPO = Path(__file__).resolve().parents[2]
RECIPE = REPO / "tests/overworld/test-recipes/player-hp.throw-contact.json"
SCENARIO = REPO / "tests/overworld/scenarios/player-hp.throw-contact.json"
ROM = hashlib.sha256(b"Throw ROM").hexdigest()
OVERLAY = "a" * 64
SOURCE = {"contractVersion": 1, "romSha256": ROM, "overlaySha256": OVERLAY}


def actor(species, slot, identity, y, *, hop=False, elapsed=0):
    handle = {"value": (1 << 16) | slot, "slot": slot, "generation": 1,
              "fieldEpoch": 1, "mapGeneration": 1, "encounterGeneration": 1}
    result = {"handle": handle, "subjectIdentity": identity,
              "species": species, "role": "WILD", "form": 0, "level": 5,
              "active": True, "presentationAttached": True,
              "identityVerified": True, "authorityGeneration": 1,
              "engineAnchorGeneration": 1, "presentationGeneration": 1,
              "engineIdentity": {"pointer": 0x02100000 + slot * 0x100},
              "logical": {"x": 585, "y": y},
              "render": {"x": 585, "y": y},
              "origin": {"x": 585, "y": y},
              "target": {"x": 585, "y": y},
              "motionKind": "NONE", "motionPhase": "IDLE",
              "motionElapsed": 0, "motionDuration": 0,
              "reservationId": 0, "commitSequence": 0,
              "engineObject": {"x": 585, "y": y,
                               "pos_x": (585 << 16) + 0x8000,
                               "pos_z": (y << 16) + 0x8000},
              "matchedLayerMask": THROW_APPLICATION_BIT if species == 74 else 0}
    if hop:
        result.update(motionKind="HOP", motionPhase="MOVING",
                      reservationId=9, commitSequence=0,
                      motionElapsed=elapsed, motionDuration=24,
                      logical={"x": 585, "y": 401},
                      render={"x": 585, "y": 401 + min(6, (elapsed * 6) // 24)},
                      origin={"x": 585, "y": 401},
                      target={"x": 585, "y": 407})
    elif species == 70 and elapsed >= 24:
        # The native owner keeps the completed plan after releasing its reservation.
        result.update(motionElapsed=24, motionDuration=24, commitSequence=1,
                      origin={"x": 585, "y": 401}, target={"x": 585, "y": 407})
    return result


def snapshot(frame, *, player_map=33, target_y=400, source_y=402,
             target_present=False, source_present=False, hop=False,
             elapsed=0, knocked=False):
    actors = []
    if target_present:
        actors.append(actor(70, 0, 700, target_y, hop=hop, elapsed=elapsed))
    if source_present:
        actors.append(actor(74, 1, 740, source_y))
        if hop:
            actors[-1]["matchedLayerMask"] = THROW_RELEASE_BIT
    return {"frame": frame, "nativeCycle": frame + 1000,
            "observationBoundary": "main-task-queue-completion",
            "fieldAvailable": True, "romSha256": ROM,
            "context": {"mapId": player_map, "fieldEpoch": 1,
                        "mapGeneration": 1},
            "fieldControl": {"taskPointer": 0},
            "player": {"x": 585, "y": 408 if knocked else 407,
                       "face_y": 0, "movement_cmd": 0},
            "actors": actors}


def health(snap, hp, damage, hits):
    return {"schemaVersion": 1,
            "identity": {"descriptorVersion": 1, "overlayId": 161,
                         "overlaySha256": OVERLAY, "romSha256": ROM},
            "frame": snap["frame"], "nativeCycle": snap["nativeCycle"],
            "lastHealthFrame": snap["frame"], "maxHp": 100,
            "hp": hp, "savedHp": hp, "lastDamage": damage,
            "acceptedHits": hits, "frameActive": False,
            "recoveryPending": False}


def step_row(name, samples):
    return {"phase": "observe", "action": name,
            "completedGameFrames": len(samples),
            "observedFieldFrames": len(samples), "nativeCycles": len(samples),
            "samples": samples, "events": [],
            "cycleIntervals": [{"completedGameFrame": sample["frame"],
                                "cpuNs": 1, "wallNs": 1}
                               for sample in samples]}


def rows():
    initial = snapshot(10, player_map=34)
    tile = snapshot(11)
    target = snapshot(12, target_present=True)
    both = snapshot(13, target_present=True, source_present=True)
    target_bound = select_current_actor(target, target["actors"][0])
    source_bound = select_current_actor(both, both["actors"][1])
    start = [snapshot(frame, target_present=True, source_present=True,
                      target_y=400 if frame < 18 else 401,
                      source_y=402 if frame < 15 else 401,
                      hop=frame == 19)
             for frame in range(14, 20)]
    crossing = []
    for frame in range(20, 84):
        elapsed = frame - 19
        crossing.append(snapshot(frame, target_present=True,
                                 source_present=True, target_y=407,
                                 source_y=401, hop=elapsed < 24,
                                 elapsed=elapsed, knocked=frame >= 38))
    for sample in crossing:
        if 34 <= sample["frame"] <= 41:
            sample["player"]["movement_cmd"] = 62

    def read(name, snap, hp, damage, hits):
        return {"phase": "observe", "action": name,
                "command": "player-health.observe", "snapshot": snap,
                "receipt": {"playerHealth": health(snap, hp, damage, hits)}}

    return [
        {"phase": "setup", "initialSnapshot": initial},
        {"phase": "setup", "action": "throw-tile", "command": "teleport",
         "snapshot": tile, "receipt": {}},
        {"phase": "setup", "action": "spawn-weepinbell", "command": "spawn",
         "snapshot": target,
         "receipt": {"value": {"species": 70, "slot": 0, "personality": 700}}},
        {"phase": "setup", "action": "bind-weepinbell", "command": "bind",
         "snapshot": target, "receipt": target_bound},
        {"phase": "setup", "action": "spawn-geodude", "command": "spawn",
         "snapshot": both,
         "receipt": {"value": {"species": 74, "slot": 1, "personality": 740}}},
        {"phase": "setup", "action": "bind-geodude", "command": "bind",
         "snapshot": both, "receipt": source_bound},
        read("before-throw", both, 100, 0, 0),
        step_row("launch-natural-throw", start),
        read("at-launch", start[-1], 100, 0, 0),
        step_row("cross-player", crossing),
        read("after-contact", crossing[-1], 80, 20, 1),
    ]



def set_flight(stream, *, origin_y=401, duration=24, cargo_species=70):
    """Copy the native plan shape; do not infer completion from an idle tile."""
    launch = next(row for row in stream if row.get("action") == "launch-natural-throw")
    crossing = next(row for row in stream if row.get("action") == "cross-player")
    samples = [launch["samples"][-1]] + crossing["samples"]
    launch_frame = samples[0]["frame"]
    for sample in samples:
        elapsed = min(duration, sample["frame"] - launch_frame)
        target = next(a for a in sample["actors"] if a["species"] == cargo_species)
        source = next(a for a in sample["actors"] if a["species"] == 74)
        source["logical"] = {"x": 585, "y": origin_y}
        source["engineObject"].update(x=585, y=origin_y,
                                      pos_x=(585 << 16) + 0x8000,
                                      pos_z=(origin_y << 16) + 0x8000)
        source["matchedLayerMask"] = THROW_RELEASE_BIT
        target.update(origin={"x": 585, "y": origin_y},
                      target={"x": 585, "y": 407}, motionDuration=duration,
                      motionElapsed=elapsed,
                      motionKind="HOP" if elapsed < duration else "NONE",
                      motionPhase="MOVING" if elapsed < duration else "IDLE",
                      reservationId=9 if elapsed < duration else 0,
                      commitSequence=0 if elapsed < duration else 1,
                      logical={"x": 585, "y": origin_y if elapsed < duration else 407},
                      render={"x": 585, "y": origin_y + (407-origin_y)*elapsed//duration})
        target["engineObject"] = {
            "x": target["logical"]["x"], "y": target["logical"]["y"],
            "pos_x": (585 << 16) + 0x8000,
            "pos_z": (origin_y << 16) + 0x8000 + (407-origin_y)*65536*elapsed//duration,
            "unk88_y": 10000 if elapsed < duration else 0,
        }
    return stream


def evaluate(stream):
    meter = PlayerHealthThrowContactMeasurement(SOURCE)
    for row in stream:
        progress = meter.observe_record(row)
        if progress["failures"]:
            break
    return meter.finish(), meter.result()


class PlayerHealthThrowContactMeasurementTest(unittest.TestCase):
    def test_authored_files_have_the_exact_fixture(self):
        recipe = json.loads(RECIPE.read_text())
        scenario = json.loads(SCENARIO.read_text())
        self.assertEqual(recipe["measurements"],
                         [{"kind": KIND, "subjects": ["weepinbell", "geodude"]}])
        self.assertEqual([(s["args"]["species"], s["args"]["x"], s["args"]["z"])
                          for s in recipe["setup"] if s["op"] == "spawn"],
                         [(70, 585, 400), (74, 585, 402)])
        self.assertEqual(recipe["budgets"]["minObservedFrames"], MIN_FRAMES)
        self.assertEqual(scenario["adapter"]["minimumFrames"], MIN_FRAMES)
        self.assertEqual(set(contract()), set(scenario["adapter"]["claims"]))
        catalog = json.loads((REPO / "data/overworld_behavior_profiles.json").read_text())
        indexes = {row["id"]: i for i, row in enumerate(catalog["applications"])}
        self.assertEqual(THROW_APPLICATION_BIT, 1 << indexes["apply-throw"])
        self.assertEqual(THROW_RELEASE_BIT, 1 << indexes["apply-throw-release"])
        find_position = next(p for p in catalog["profiles"]
                             if p["id"] == "throw-find-position")
        self.assertEqual(THROW_MAX_RANGE, find_position["fields"]["throwMaxRange"]["value"])

    def test_current_two_actor_flight_and_hp_change_pass(self):
        finished, result = evaluate(rows())
        self.assertTrue(finished["passed"], finished["failures"])
        self.assertEqual((result["launchFrame"], result["observedFrames"],
                          result["hpAfterThrow"], result["landed"]),
                         (19, 6 + CROSS_FRAMES, 80, True))
        self.assertGreater(result["flightFrames"], 0)

    def test_completed_first_flight_allows_later_current_ambush_hop(self):
        # Native 3505: first plan duration19 finishes before a distinct duration6 Hop.
        stream = set_flight(rows(), duration=19)
        target = next(a for a in stream[-2]["samples"][33]["actors"] if a["species"] == 70)
        target.update(motionKind="HOP", motionPhase="MOVING", motionElapsed=0,
                      motionDuration=6, reservationId=10, commitSequence=1,
                      origin={"x": 585, "y": 407}, target={"x": 585, "y": 408},
                      matchedLayerMask=1 << 26)
        finished, result = evaluate(stream)
        self.assertTrue(finished["passed"], result["failures"])
        self.assertTrue(result["landed"])
        self.assertEqual(result["flightFrames"], 18)
        # Ending the first-flight plan check does not end full current-actor checks.
        target["subjectIdentity"] += 1
        finished, result = evaluate(stream)
        self.assertFalse(finished["passed"], result)

    def test_eight_tile_launch_uses_the_current_carrier_pose(self):
        stream = set_flight(rows(), origin_y=399, duration=25)
        finished, result = evaluate(stream)
        self.assertTrue(finished["passed"], result["failures"])
        for fault in ("too-far", "wrong-pose", "wrong-owner"):
            with self.subTest(fault=fault):
                bad = set_flight(rows(), origin_y=398 if fault == "too-far" else 399,
                                 duration=25)
                launch = next(row for row in bad if row.get("action") == "launch-natural-throw")
                source = next(a for a in launch["samples"][-1]["actors"] if a["species"] == 74)
                if fault == "wrong-pose": source["engineObject"]["pos_z"] += 65536
                if fault == "wrong-owner": source["handle"]["generation"] += 1
                finished, result = evaluate(bad)
                self.assertFalse(finished["passed"], result)

    def test_idle_before_first_commit_cannot_end_the_flight_guard(self):
        for fault in ("elapsed", "duration", "reservation", "commit"):
            with self.subTest(fault=fault):
                stream = set_flight(rows(), duration=19)
                target = next(a for a in stream[-2]["samples"][18]["actors"] if a["species"] == 70)
                if fault == "elapsed": target["motionElapsed"] = 18
                if fault == "duration": target["motionDuration"] = 18
                if fault == "reservation": target["reservationId"] = 9
                if fault == "commit": target["commitSequence"] = 0
                finished, result = evaluate(stream)
                self.assertFalse(finished["passed"], result)
                self.assertIn("completed first flight", " ".join(result["failures"]))

    def test_positioning_application_is_not_a_throw_release(self):
        stream = rows()
        stream[7]["samples"][-1]["actors"][1]["matchedLayerMask"] = 1 << 21
        finished, result = evaluate(stream)
        self.assertFalse(finished["passed"])
        self.assertIsNone(result["launchFrame"])

    def test_ordinary_hop_waits_for_exact_release_before_launched_stage(self):
        from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
        recipe = validate_test(json.loads(RECIPE.read_text()))
        predicate = recipe["actions"][1]["args"]["until"]
        self.assertEqual(predicate, {"kind": "measurement-stage", "measurement": KIND,
                                     "stage": "launched", "when": "final"})
        stream = rows()
        launch = stream[7]
        ordinary = launch["samples"][0]["actors"][0]
        ordinary.update(motionKind="HOP", motionPhase="MOVING", motionDuration=7,
                        origin={"x": 585, "y": 400}, target={"x": 587, "y": 400})
        meter = PlayerHealthThrowContactMeasurement(SOURCE)
        for row in stream[:7]: meter.observe_record(row)
        meter.observe_record(step_row("launch-natural-throw", launch["samples"][:1]))
        self.assertEqual(meter.result()["failures"], [])
        evaluator = SimpleNamespace(specs={}, latest=meter.latest, uses_raw_records=False,
                                    measurements={KIND: meter})
        self.assertFalse(TestEvaluator.check(evaluator, predicate))
        meter.observe_record(step_row("launch-natural-throw", launch["samples"][1:]))
        evaluator.latest = meter.latest
        self.assertTrue(TestEvaluator.check(evaluator, predicate))
        self.assertFalse(meter.result()["ready"])
        for row in stream[8:]: meter.observe_record(row)
        self.assertTrue(meter.finish()["passed"], meter.result()["failures"])

    def test_hp_clock_offset_is_stable_across_launch_and_flight(self):
        stream = rows()
        reads = [row["receipt"]["playerHealth"] for row in stream
                 if row.get("command") == "player-health.observe"]
        for read in reads:
            read["lastHealthFrame"] += 460
        finished, result = evaluate(stream)
        self.assertTrue(finished["passed"], result["failures"])
        reads[-1]["lastHealthFrame"] -= 1
        finished, result = evaluate(stream)
        self.assertFalse(finished["passed"])
        self.assertIn("clock did not advance", " ".join(result["failures"]))

    def test_copied_faults_reject_at_the_intended_boundary(self):
        baseline = rows()
        for fault in FAULTS:
            with self.subTest(fault=fault):
                finished, result = evaluate(faulted_rows(baseline, fault))
                self.assertFalse(finished["passed"])
                self.assertTrue(result["failures"])

    def test_copied_faults_reject_chunked_live_frame_stream(self):
        baseline = rows()
        launch = [step_row("launch-natural-throw", [sample])
                  for sample in baseline[7]["samples"]]
        crossing = [step_row("cross-player", baseline[9]["samples"][i:i + 8])
                    for i in range(0, CROSS_FRAMES, 8)]
        chunked = baseline[:7] + launch + [baseline[8]] + crossing + baseline[10:]
        finished, result = evaluate(chunked)
        self.assertTrue(finished["passed"], result["failures"])
        for fault in FAULTS:
            with self.subTest(fault=fault):
                finished, result = evaluate(faulted_rows(chunked, fault))
                self.assertFalse(finished["passed"])
                self.assertTrue(result["failures"])

    def test_missing_frame_and_missing_flight_reject(self):
        stream = rows()
        stream[7]["samples"][2]["frame"] += 1
        finished, _ = evaluate(stream)
        self.assertFalse(finished["passed"])
        self.assertIn("skip", " ".join(finished["failures"]))
        stream = rows()
        stream[7]["samples"][-1]["actors"][0]["motionKind"] = "NONE"
        finished, _ = evaluate(stream)
        self.assertFalse(finished["passed"])

    def test_early_hp_change_without_flight_is_not_credited(self):
        stream = rows()
        launch_hp = next(row["receipt"]["playerHealth"] for row in stream
                         if row.get("action") == "at-launch")
        launch_hp["hp"] = launch_hp["savedHp"] = 80
        launch_hp["lastDamage"] = 20
        launch_hp["acceptedHits"] = 1
        finished, _ = evaluate(stream)
        self.assertFalse(finished["passed"])


if __name__ == "__main__":
    unittest.main()
