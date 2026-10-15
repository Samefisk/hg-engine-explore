"""Copied-data checks for ordinary Mankey Hop contact proof."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_player_health_hop_contact_measurement import (
    KIND, PlayerHealthHopContactMeasurement,
)
from tools.overworld.devtools_player_health_hop_contact_proof import (
    FAULTS, contract, faulted_rows, measurements,
)
from tools.overworld.devtools_test_contract import (
    TestEvaluator, _wild_spawn_setup, validate_test,
)
from tools.overworld.test_devtools_wild_walk_contract import spawn_setup


ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / "tests/overworld/test-recipes/player-hp.hop-contact.json"
SCENARIO = ROOT / "tests/overworld/scenarios/player-hp.hop-contact.json"
ROM = "a" * 64
OVERLAY = "b" * 64
PROFILE = "c" * 64
SOURCE = {"contractVersion": 1, "romSha256": ROM,
          "overlaySha256": OVERLAY, "profileSha256": PROFILE}
FINGERPRINT = 901
MASK = (1 << 17) | (1 << 19)
HANDLE = {"value": 1 << 16, "slot": 0, "generation": 1, "fieldEpoch": 1,
          "mapGeneration": 1, "encounterGeneration": 1}


def actor(*, moving=False):
    pose = {"pos_x": 585 << 16 if moving else 586 << 16,
            "pos_y": 0x8000 if moving else 0,
            "pos_z": 407 << 16 if moving else 406 << 16}
    return {"handle": deepcopy(HANDLE), "subjectIdentity": 901, "species": 56,
            "role": "WILD", "active": True, "identityVerified": True,
            "presentationAttached": True, "authorityGeneration": 1,
            "engineAnchorGeneration": 1, "presentationGeneration": 1,
            "engineIdentity": {"pointer": 0x02100000}, "behaviorFingerprint": FINGERPRINT,
            "matchedLayerMask": MASK, "origin": {"x": 586, "y": 406},
            "target": {"x": 585, "y": 407},
            "motionKind": "HOP" if moving else "NONE",
            "motionPhase": "MOVING" if moving else "IDLE",
            "motionElapsed": 1 if moving else 0,
            "motionDuration": 7 if moving else 0,
            "engineObject": pose}


def snapshot(frame, *, map_id=33, has_actor=True, moving=False):
    return {"frame": frame, "nativeCycle": frame + 1000,
            "observationBoundary": "main-task-queue-completion",
            "fieldAvailable": True, "romSha256": ROM,
            "context": {"mapId": map_id, "fieldEpoch": 1, "mapGeneration": 1},
            "fieldControl": {"taskPointer": 0},
            "player": {"x": 585, "y": 407, "pos_x": 585 << 16,
                       "pos_y": 0, "pos_z": 407 << 16,
                       "face_x": 0, "face_y": 0, "face_z": 0},
            "actors": [actor(moving=moving)] if has_actor else [],
            "nativeObservation": {"profileFingerprints": [FINGERPRINT]}}


def health(snap, hp, damage, hits):
    return {"schemaVersion": 1, "identity": {"descriptorVersion": 1,
            "overlayId": 161, "romSha256": ROM, "overlaySha256": OVERLAY},
            "frame": snap["frame"], "nativeCycle": snap["nativeCycle"],
            "lastHealthFrame": snap["frame"], "maxHp": 100,
            "hp": hp, "savedHp": hp, "lastDamage": damage,
            "acceptedHits": hits, "frameActive": False, "recoveryPending": False}


def raw(name, sample, *, profile_cache=False):
    row = {"phase": "observe", "action": name, "samples": [sample],
           "completedGameFrames": 1, "observedFieldFrames": 1,
           "nativeCycles": 1, "events": [],
           "cycleIntervals": [{"completedGameFrame": sample["frame"],
                               "cpuNs": 1, "wallNs": 1}]}
    if profile_cache:
        data = bytearray(216)
        data[12], data[72], data[73], data[74] = 2, 1, 16, 20
        row["profileCache"] = {"frame": sample["frame"],
            "nativeCycle": sample["nativeCycle"], "resolvedProfiles": [{
                "resolved": True, "fingerprint": FINGERPRINT,
                "sourceSha256": PROFILE, "appliedOverrides": MASK,
                "resultHex": data.hex()}]}
    return row


def rows(*, settle=True):
    initial = snapshot(10, map_id=34, has_actor=False)
    placed = snapshot(11, has_actor=False)
    spawned = snapshot(12)
    settled = snapshot(13) if settle else spawned
    crossed = snapshot(14 if settle else 13, moving=True)
    bound = select_current_actor(spawned, spawned["actors"][0])
    stream = [
        {"phase": "setup", "initialSnapshot": initial},
        {"phase": "setup", "action": "open-area", "command": "teleport",
         "snapshot": placed, "receipt": {}},
        {"phase": "setup", "action": "spawn-mankey", "command": "spawn",
         "snapshot": spawned,
         "receipt": {"value": {"species": 56, "slot": 0, "personality": 901}}},
        {"phase": "setup", "action": "bind-mankey", "command": "bind",
         "snapshot": spawned, "receipt": bound},
        *([raw("settle-spawn", settled)] if settle else []),
        {"phase": "observe", "action": "before-hop", "command": "player-health.observe",
         "snapshot": settled, "receipt": {"playerHealth": health(settled, 100, 0, 0)}},
        raw("wait-crossing-hop", crossed, profile_cache=True),
        {"phase": "observe", "action": "after-contact", "command": "player-health.observe",
         "snapshot": deepcopy(crossed), "receipt": {"playerHealth": health(crossed, 80, 20, 1)}},
    ]
    return stream


def with_other_wild(stream, *, attacking=False, hop=False):
    extra = actor()
    extra["handle"].update(value=(1 << 16) | 1, slot=1)
    extra.update(species=74, subjectIdentity=740,
                 behaviorFingerprint=902, matchedLayerMask=1024,
                 engineIdentity={"pointer": 0x02100100},
                 motionKind="HOP" if hop else "NONE")
    wait = next(row for row in stream if row.get("action") == "wait-crossing-hop")
    end = next(row for row in stream if row.get("action") == "after-contact")
    for snapshot_row in (wait["samples"][0], end["snapshot"]):
        snapshot_row["actors"].append(deepcopy(extra))
        snapshot_row["nativeObservation"]["profileFingerprints"].append(902)
    profile = bytearray(216)
    if attacking:
        profile[72], profile[73], profile[74] = 1, 16, 20
    row = {"resolved": True, "fingerprint": 902, "sourceSha256": PROFILE,
           "appliedOverrides": 1024, "resultHex": profile.hex()}
    wait["profileCache"]["resolvedProfiles"].append(deepcopy(row))
    end["snapshot"]["nativeObservation"]["resolvedProfiles"] = [deepcopy(row)]
    return stream


def evaluate(stream):
    meter = PlayerHealthHopContactMeasurement(SOURCE)
    for row in stream:
        result = meter.observe_record(row)
        if result["failures"]:
            break
    return meter.finish(), meter.result()


class PlayerHealthHopContactMeasurementTest(unittest.TestCase):
    def test_recipe_and_scenario_are_registered_shaped(self):
        recipe = validate_test(json.loads(RECIPE.read_text()))
        scenario = json.loads(SCENARIO.read_text())
        self.assertEqual(recipe["measurements"], [{"kind": KIND, "subject": "mankey"}])
        self.assertEqual(set(contract()), set(scenario["adapter"]["claims"]))

    def test_mankey_spawn_accepts_its_native_appear_hop(self):
        receipt, observed = spawn_setup(species=56, locomotion=7)
        self.assertEqual(_wild_spawn_setup(receipt, observed,
                         species=56, locomotion=7)["destination"], [0, 0])
        with self.assertRaisesRegex(ValueError, "identity or own native destination"):
            _wild_spawn_setup(receipt, observed, species=56, locomotion=3)
        evaluator = TestEvaluator(validate_test(json.loads(RECIPE.read_text())))
        evaluator.install_measurements({KIND: SOURCE})
        initial = snapshot(10, map_id=34, has_actor=False)
        self.assertNotEqual(evaluator.observe_record({
            "phase": "setup", "initialSnapshot": initial})["state"], "failed")
        # The command path must use the same exact startup code as the native
        # receipt. Other spawn fields remain checked by _wild_spawn_setup.
        observed["romSha256"] = ROM
        observed["observationBoundary"] = "main-task-queue-completion"
        observed["fieldAvailable"] = True
        observed["fieldControl"] = {"taskPointer": 0}
        observed["player"] = deepcopy(initial["player"])
        observed["player"].update(x=585, y=407)
        observed["context"]["mapId"] = 33
        observed["actors"][0]["species"] = 56
        observed["actors"][0]["role"] = "WILD"
        observed["actors"][0]["active"] = True
        observed["actors"][0]["identityVerified"] = True
        observed["actors"][0]["presentationAttached"] = True
        observed["actors"][0]["subjectIdentity"] = receipt["value"]["personality"]
        observed["actors"][0]["handle"]["fieldEpoch"] = observed["context"]["fieldEpoch"]
        observed["actors"][0]["handle"]["mapGeneration"] = observed["context"]["mapGeneration"]
        native = receipt["events"][0]["data"]
        native["worldContext"]["mapId"] = 33
        native["finalization"]["receipt"]["worldContext"]["mapId"] = 33
        native["finalization"]["receipt"]["returnWorldContext"]["mapId"] = 33
        self.assertNotEqual(evaluator.observe_record({
            "phase": "setup", "action": "open-area", "command": "teleport",
            "snapshot": observed, "receipt": {}})["state"], "failed")
        self.assertNotEqual(evaluator.observe_record({
            "phase": "setup", "action": "spawn-mankey", "command": "spawn",
            "snapshot": observed, "receipt": receipt})["state"], "failed")

    def test_one_current_ordinary_hop_crossing_and_hp_pass(self):
        stream = rows()
        finished, result = evaluate(stream)
        self.assertTrue(finished["passed"], finished["failures"])
        self.assertTrue(result["ordinaryHop"])
        self.assertEqual((result["crossingFrame"], result["hpAfterHop"]), (14, 80))
        replay = {"passed": True, "observedFrames": result["observedFrames"],
                  "measurements": {KIND: result}}
        self.assertEqual(measurements(stream, replay)["crossingFrame"], 14)

    def test_already_idle_spawn_skips_settle_without_losing_proof(self):
        stream = rows(settle=False)
        finished, result = evaluate(stream)
        self.assertTrue(finished["passed"], finished["failures"])
        self.assertTrue(result["settledAtBind"])
        self.assertEqual((result["observedFrames"], result["crossingFrame"]), (1, 13))
        replay = {"passed": True, "observedFrames": 1,
                  "measurements": {KIND: result}}
        self.assertEqual(measurements(stream, replay)["crossingFrame"], 13)

    def test_natural_other_wild_needs_zero_damage_and_no_hop(self):
        stream = with_other_wild(rows(settle=False))
        self.assertTrue(evaluate(stream)[0]["passed"])
        for change in ({"attacking": True}, {"hop": True}):
            with self.subTest(change=change):
                finished, result = evaluate(with_other_wild(rows(settle=False), **change))
                self.assertFalse(finished["passed"])
                self.assertTrue(result["failures"])

    def test_copied_faults_fail_closed(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                finished, result = evaluate(faulted_rows(rows(), fault))
                self.assertFalse(finished["passed"])
                self.assertTrue(result["failures"])

    def test_missing_or_stale_profile_receipt_rejects(self):
        for change in (lambda row: row.pop("profileCache"),
                       lambda row: row["profileCache"].update(frame=13),
                       lambda row: row["samples"][0]["nativeObservation"].update(
                           profileFingerprints=[])):
            with self.subTest(change=change):
                stream = rows()
                change(stream[6])
                self.assertFalse(evaluate(stream)[0]["passed"])


if __name__ == "__main__":
    unittest.main()
