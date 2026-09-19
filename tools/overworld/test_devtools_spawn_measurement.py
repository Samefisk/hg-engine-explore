"""Synthetic receipt checks, not live placement or native ABI proof."""
from copy import deepcopy
import struct
import unittest
import os
from pathlib import Path
import shutil
import subprocess

from tools.overworld.devtools_spawn_measurement import check_pool_spawn_receipt, PoolSpawnMeasurement
from tools.overworld.test_devtools_chain_measurement import SOURCE, SCHEMA, Stream


AUTHORED = {"overrideProfiles": [
    {"name": "Flying insect", "fields": {"spawnDestination": {
        "operator": "replace", "value": "OW_WILD_SPAWN_DESTINATION_POOL"}}},
    {"name": "Active", "fields": {}},
]}


def fixture():
    stream = Stream()
    stream.motion("HOP", (16, 0), pause=2, spawn=True)
    spawn = deepcopy(next(event["data"] for _, events in stream.items for event in events
                          if event["data"].get("observation") == "spawn-prepared"))
    context = {"mapId": 34, "fieldEpoch": 2, "mapGeneration": 4,
               "statePointer": 0x023B0000, "fieldPointer": 0x02230000}
    spawn.update(statePointer=0x023B0000, fieldPointer=0x02230000, worldContext=context, sequence=20)
    receipt = {"observation": "spawn-finalized", "sequence": 19, "finalizationId": 1,
        "returnValue": 1, "setupMode": "normal", "worldContext": deepcopy(context),
        "returnWorldContext": deepcopy(context), "pairEligible": True,
        "entryActorFrame": 0, "returnActorFrame": 0, "entryNativeCycle": 0, "returnNativeCycle": 0,
        **{key: deepcopy(spawn[key]) for key in ("statePointer", "fieldPointer", "slot", "terrain",
               "preparedPointer", "preparedPrefixHex", "preparedEncounter", "startup")},
        "inputPrefixHex": spawn["preparedPrefixHex"][:40],
        "inputEncounter": deepcopy(spawn["preparedEncounter"]), "inputPosition": [16, 0],
        "position": [16, 0], "resolverReceipts": [deepcopy(stream.profile)]}
    receipt["resolverReceipts"][0].update(finalizationId=1,
        inputEncounter=deepcopy(receipt["inputEncounter"]))
    profile = receipt["resolverReceipts"][0]
    raw = bytearray.fromhex(profile["resultHex"])
    struct.pack_into("<I", raw, 236, 1)
    raw[218] = raw[222] = 0
    profile["resultHex"] = raw.hex()
    spawn["finalization"] = {"status": "matched", "receipt": receipt}
    return spawn


def check(spawn, source=AUTHORED):
    return check_pool_spawn_receipt(spawn, source_sha256=SOURCE, authored_profiles=source)


def landing_stream(*, replaced=False):
    stream = Stream()
    raw = bytearray.fromhex(stream.profile["resultHex"])
    struct.pack_into("<I", raw, 236, 1)
    stream.profile["resultHex"] = raw.hex()
    stream.items[0][0]["nativeObservation"]["resolvedProfiles"] = [deepcopy(stream.profile)]
    stream.motion("HOP", (16, 0), pause=2, spawn=True)
    receipt = deepcopy(fixture()["finalization"]["receipt"])
    receipt["sequence"] = 1
    receipt["resolverReceipts"][0] = {**deepcopy(stream.profile), "finalizationId": 1,
                                    "inputEncounter": deepcopy(receipt["inputEncounter"])}
    if replaced:
        raw = bytearray.fromhex(receipt["inputPrefixHex"])
        struct.pack_into("<ii", raw, 0, 12, 4)
        receipt.update(inputPrefixHex=raw.hex(), inputPosition=[12, 4])
    for snapshot, events in stream.items[1:]:
        snapshot["nativeObservation"]["sequence"] += 1
        for event in events:
            if event["kind"] != "native-observation":
                continue
            data = event["data"]
            data["sequence"] += 1
            if data["observation"] == "spawn-prepared":
                data.update({key: deepcopy(receipt[key]) for key in ("statePointer", "fieldPointer", "worldContext")})
                data["finalization"] = {"status": "matched", "receipt": deepcopy(receipt)}
    stream.items[1][1].insert(0, {"kind": "native-observation", "frame": stream.items[1][0]["frame"],
                               "data": receipt})
    return stream


class PoolSpawnMeasurementTests(unittest.TestCase):
    def meter(self):
        return PoolSpawnMeasurement(SCHEMA, SOURCE, authored_profiles=AUTHORED, max_frames=100)

    def test_kept_site_requires_the_complete_same_actor_spawn_hop(self):
        meter = self.meter()
        stream = landing_stream()
        for snapshot, events in stream.items[:-1]:
            result = meter.observe(snapshot, events)
            self.assertFalse(result["ready"])
        result = meter.observe(*stream.items[-1])
        self.assertTrue(result["ready"], result)
        self.assertTrue(meter.finish()["passed"])
        self.assertEqual(result["completeMotions"], 1)

    def test_wrong_site_is_retained_then_fails_at_actual_landing(self):
        meter = self.meter()
        for snapshot, events in landing_stream(replaced=True).items:
            result = meter.observe(snapshot, events)
        self.assertTrue(result["spawnPassed"], result)
        self.assertFalse(meter.finish()["passed"])
        self.assertEqual(result["failures"][0]["code"], "pool-destination-replaced")

    def test_finalizer_from_prior_update_must_be_observed_not_just_embedded(self):
        for omit in (False, True):
            stream = landing_stream()
            final = stream.items[1][1].pop(0)
            if not omit:
                final["frame"] = stream.items[0][0]["frame"]
                stream.items[0][0]["nativeObservation"]["sequence"] = final["data"]["sequence"]
                stream.items[0][1].append(final)
            meter = self.meter()
            for snapshot, events in stream.items:
                meter.observe(snapshot, events)
            self.assertEqual(meter.finish()["passed"], not omit)

    def test_missing_terminal_or_finalization_cannot_pass(self):
        for fault in ("terminal", "finalization", "no-arc", "wrong-actor"):
            with self.subTest(fault=fault):
                stream = landing_stream()
                for snapshot, events in stream.items:
                    if fault == "no-arc":
                        for actor in snapshot["actors"]: actor["engineObject"]["unk88_y"] = 0
                    if fault == "wrong-actor" and snapshot["frame"] > 3:
                        for actor in snapshot["actors"]: actor["subjectIdentity"] += 1
                    for event in events:
                        data = event["data"]
                        if fault == "terminal" and data.get("event") == "MOTION_FINISHED":
                            data["event"] = "WORLD_EFFECT"
                        if fault == "finalization" and data.get("observation") == "spawn-prepared":
                            data["finalization"] = {"status": "missing"}
                meter = self.meter()
                for snapshot, events in stream.items: meter.observe(snapshot, events)
                self.assertFalse(meter.finish()["passed"])


class PoolSpawnReceiptTests(unittest.TestCase):
    def test_public_arm_resolver_layout_anchors_mask_and_primitive_readers(self):
        root = Path(__file__).resolve().parents[2]
        compiler = shutil.which(os.environ.get("ARM_NONE_EABI_CC", "arm-none-eabi-gcc"))
        if compiler is None and Path("/opt/homebrew/bin/arm-none-eabi-gcc").is_file():
            compiler = "/opt/homebrew/bin/arm-none-eabi-gcc"
        self.assertIsNotNone(compiler, "missing ARM compiler is not an ABI pass")
        program = '''#include "overworld_behavior_resolver.h"
#include <stddef.h>
_Static_assert(sizeof(BehaviorResolveResult) == 256, "result size");
_Static_assert(offsetof(BehaviorResolveResult, matchedOverrideMask) == 236, "Owner matches");
_Static_assert(offsetof(BehaviorResolveResult, forcedOverrideMask) == 240, "Owner forced");
_Static_assert(offsetof(BehaviorResolveResult, conditionalOverrideMask) == 244, "Owner conditional");
_Static_assert(offsetof(BehaviorResolveResult, appliedOverrideMask) == 248, "all applied");
_Static_assert(offsetof(BehaviorResolveResult, primitives.chillTarget) == 218, "chill target");
_Static_assert(offsetof(BehaviorResolveResult, primitives.attentiveTarget) == 222, "attentive target");
'''
        command = [compiler, "-x", "c", "-std=c11", "-mthumb", "-mcpu=arm946e-s",
                   "-I" + str(root / "include"), "-fsyntax-only", "-"]
        correct = subprocess.run(command, input=program, text=True, capture_output=True, timeout=20)
        self.assertEqual(correct.returncode, 0, correct.stderr[-3000:])
        wrong = subprocess.run(command, input=program.replace("== 236", "== 248"),
                               text=True, capture_output=True, timeout=20)
        self.assertNotEqual(wrong.returncode, 0, "combined applied mask is not Owner provenance")

    def test_own_pool_site_is_preserved_without_claiming_surface_or_motion(self):
        result = check(fixture())
        self.assertTrue(result["passed"])
        self.assertEqual(result["sourcePosition"], result["landingTarget"])
        self.assertIn("physical landing and mobility unproved", result["scope"])

    def test_current_four_surface_conversion_cannot_redefine_pool_expectation(self):
        spawn = fixture()
        receipt = spawn["finalization"]["receipt"]
        raw = bytearray.fromhex(receipt["inputPrefixHex"])
        struct.pack_into("<ii", raw, 0, 12, 4)
        receipt.update(inputPrefixHex=raw.hex(), inputPosition=[12, 4])
        # Native result carries the known faulty broad mask. It is evidence,
        # not our expected destination. The output still belongs to this PID.
        profile = receipt["resolverReceipts"][0]
        raw = bytearray.fromhex(profile["resultHex"])
        for offset in (0, 72, 144):
            struct.pack_into("<HH", raw, offset + 52, 15, 1023)
        profile.update(resultHex=raw.hex(), lanes=[raw[n:n + 72].hex() for n in (0, 72, 144)])
        result = check(spawn)
        self.assertFalse(result["passed"])
        self.assertEqual(result["reason"], "pool-destination-replaced")
        self.assertEqual(result["sourcePosition"], [12, 4])
        self.assertEqual(result["destination"], [16, 0])

    def test_legitimate_native_pid_finalization_is_not_a_species_swap(self):
        spawn = fixture()
        receipt = spawn["finalization"]["receipt"]
        raw = bytearray.fromhex(receipt["inputPrefixHex"])
        struct.pack_into("<I", raw, 12, 55 ^ 0x10000000)
        receipt["inputPrefixHex"] = raw.hex()
        receipt["inputEncounter"]["personality"] = 55 ^ 0x10000000
        receipt["resolverReceipts"][0]["inputEncounter"] = deepcopy(receipt["inputEncounter"])
        result = check(spawn)
        self.assertTrue(result["passed"])
        self.assertNotEqual(result["inputPersonality"], result["finalPersonality"])

    def test_authored_surf_pool_is_not_silently_forced_to_land(self):
        spawn = fixture()
        receipt = spawn["finalization"]["receipt"]
        spawn["terrain"] = receipt["terrain"] = 1
        profile = receipt["resolverReceipts"][0]
        request = bytearray.fromhex(profile["requestHex"]); request[9] = 1
        profile["requestHex"] = request.hex()
        self.assertTrue(check(spawn)["passed"])

    def test_missing_stale_reused_or_wrong_subject_receipts_cannot_pass(self):
        for fault in ("missing", "context-mismatch", "prefix-mismatch", "failed", "pointer", "field",
                      "world", "sequence", "pid", "species", "input-species", "profile-source",
                      "profile-request", "profile-bytes", "headbutt", "short-input", "pair-ineligible",
                      "return-world", "profile-owner", "clock", "form", "level"):
            with self.subTest(fault=fault):
                spawn = fixture(); r = spawn["finalization"]["receipt"]
                if fault in ("missing", "context-mismatch", "prefix-mismatch"):
                    spawn["finalization"]["status"] = fault
                elif fault == "failed": r["returnValue"] = 0
                elif fault == "pointer": r["preparedPointer"] += 4
                elif fault == "field": r["fieldPointer"] += 4
                elif fault == "world": r["worldContext"]["fieldEpoch"] += 1
                elif fault == "sequence": r["sequence"] = spawn["sequence"]
                elif fault == "pid": spawn["publicSubject"]["subjectIdentity"] += 1
                elif fault == "species": spawn["publicSubject"]["species"] = 56
                elif fault == "input-species": r["inputEncounter"]["species"] = 56
                elif fault == "profile-source": r["resolverReceipts"][0]["sourceSha256"] = "b" * 64
                elif fault == "profile-request": r["resolverReceipts"][0]["requestHex"] = "00" * 20
                elif fault == "profile-bytes": r["resolverReceipts"][0]["lanes"] = ["00" * 72] * 3
                elif fault == "headbutt": spawn["terrain"] = r["terrain"] = 2
                elif fault == "short-input": r["inputPrefixHex"] = r["inputPrefixHex"][:-2]
                elif fault == "pair-ineligible": r["pairEligible"] = False
                elif fault == "return-world": r["returnWorldContext"]["mapGeneration"] += 1
                elif fault == "profile-owner": r["resolverReceipts"][0]["finalizationId"] += 1
                elif fault == "clock": r["returnNativeCycle"] = 999
                elif fault in ("form", "level"): spawn["publicSubject"][fault] += 1
                with self.assertRaises(ValueError): check(spawn)

    def test_modern_or_later_authored_destination_is_not_called_pool(self):
        for fields in ({"spawnDestinationOverrideMask": {"operator": "replace", "value": "4"}},
                       {"spawnDestination": {"operator": "replace", "value": "OW_WILD_SPAWN_DESTINATION_CANOPY"}}):
            with self.subTest(fields=fields):
                source = deepcopy(AUTHORED); source["overrideProfiles"][1]["fields"] = fields
                spawn = fixture()
                profile = spawn["finalization"]["receipt"]["resolverReceipts"][0]
                raw = bytearray.fromhex(profile["resultHex"])
                struct.pack_into("<I", raw, 236, 3)
                profile["resultHex"] = raw.hex()
                with self.assertRaises(ValueError): check(spawn, source)

    def test_active_only_destination_does_not_replace_owner_pool(self):
        source = deepcopy(AUTHORED)
        source["overrideProfiles"][1]["fields"] = {"spawnDestination": {
            "operator": "replace", "value": "OW_WILD_SPAWN_DESTINATION_CANOPY"}}
        self.assertTrue(check(fixture(), source)["passed"])

    def test_conditional_treetop_and_inconsistent_owner_masks_are_outside_witness(self):
        for offset, value in ((244, 1), (240, 1), (236, 4), (218, 4), (222, 4)):
            with self.subTest(offset=offset):
                spawn = fixture()
                profile = spawn["finalization"]["receipt"]["resolverReceipts"][0]
                raw = bytearray.fromhex(profile["resultHex"])
                if offset >= 236:
                    struct.pack_into("<I", raw, offset, value)
                else:
                    raw[offset] = value
                profile["resultHex"] = raw.hex()
                with self.assertRaises(ValueError): check(spawn)


if __name__ == "__main__":
    unittest.main()
