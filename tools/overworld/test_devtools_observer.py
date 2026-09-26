"""Exercise installed shared observer callbacks, with no native core or game writes."""
from copy import deepcopy
from pathlib import Path
import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_engine import Hooks
from tools.overworld.devtools_observer import (FRIENDSHIP_WAIT_WINDOW,
    MON_APPLY_FRIENDSHIP_MOD, NativeObservation, NativeObservationError,
    PLAYER_STEP_ADMISSION, SPAWN_REFRESH_HEIGHT, SPAWN_CREATE_OBJECT,
    public_bytes)
from tools.overworld.devtools_spawn_cost_probe import enable_spawn_cost_probe
from tools.overworld.devtools_spawn_measurement import check_pool_spawn_receipt


class Fixture:
    def __init__(self, directory, *, authored_profiles=None):
        root = Path(directory)
        (root / "data").mkdir()
        (root / "base").mkdir()
        (root / "data/overworld_behavior_profiles.json").write_text(json.dumps(authored_profiles or {}))
        stock = bytearray(max(SPAWN_REFRESH_HEIGHT, MON_APPLY_FRIENDSHIP_MOD) - 0x02000000 + 32)
        stock[0x1FD44:0x1FD64] = b"R" * 32
        stock[PLAYER_STEP_ADMISSION - 0x02000000:PLAYER_STEP_ADMISSION - 0x02000000 + 32] = b"S" * 32
        stock[SPAWN_REFRESH_HEIGHT - 0x02000000:SPAWN_REFRESH_HEIGHT - 0x02000000 + 32] = b"H" * 32
        stock[SPAWN_CREATE_OBJECT - 0x02000000:SPAWN_CREATE_OBJECT - 0x02000000 + 32] = b"C" * 32
        stock[MON_APPLY_FRIENDSHIP_MOD - 0x02000000:MON_APPLY_FRIENDSHIP_MOD - 0x02000000 + 32] = b"F" * 32
        (root / "base/arm9.bin").write_bytes(stock)
        names = ("OverworldWildSpawns_SpawnPreparedEncounter", "OverworldWildSpawns_StartPreparedCustomJumpCommand",
                 "BehaviorResolver_Resolve", "ActorSystem_ReduceWalk", "OverworldWildSpawns_FinalizePreparedSpawn",
                 "OverworldWildSpawns_RunChainReposition", "OverworldWildSpawns_IsBehaviorAllowedHopLandingTile",
                 "OverworldWildRuntime_RequestMotion", "OverworldWildSpawns_StartPreparedCustomJumpCommandTimed",
                 "OverworldActorHopPlanner_Plan", "ActorSystem_RequestMotion",
                 "OverworldWildSpawns_QuerySurface", "OverworldWildSpawns_DoesAllowedTileMatch",
                 "OverworldWildSpawns_IsTileOccupiedByObject", "OverworldWildSpawns_IsTileOccupiedByNonPlayerObject",
                 "OverworldWildSpawns_IsTileOccupiedOnSurface", "OverworldWildSpawns_ClassifyBehaviorHopLandingTile",
                 "OverworldWildSpawns_ResolveObjectLandingHeight", "OverworldWildSpawns_ApplySurfaceHeight",
                 "OverworldWildSpawns_TryPickSpawnDestinationMask",
                 "OverworldWildBehavior_TryGetSpawnMetadata", "BehaviorResolver_InspectClass",
                 "OverworldWildSpawns_SpawnOne", "OverworldWildSpawns_TryRefill",
                 "OverworldWildHelper_TryPrepareSpawn", "OverworldWildSpawns_HelperLoadArchiveData",
                 "OverworldWildSpawns_FrameMovementTask", "OverworldWildSpawns_TickMovementParams.constprop.0",
                 "OverworldWildSpawns_OverlayOnPlayerStep", "OverworldWildSpawns_TrySpawnFollower",
                 "OverworldWildSpawns_RequestBattleScript",
                 )
        self.symbols = {name: 0x02300000 + index * 0x40 for index, name in enumerate(names)}
        self.memory, self.callbacks = {}, {}
        self.regs = SimpleNamespace(r0=0, r1=0, r2=0, r3=0, sp=0x027E3800, lr=0x02001001)
        self.emu = SimpleNamespace(memory=SimpleNamespace(register_arm9=self.regs, register_exec=self.register))
        self.guest_clock = {"version": 1, "running": True, "arm9Timestamp": 1000,
                            "arm7Timestamp": 500, "frameSequence": 10,
                            "scope": "nds-scheduler-ticks-not-cpu-or-instructions"}
        self.emu.guest_clock = lambda: dict(self.guest_clock)
        self.actor = {"active": True, "handle": {"value": 0x10000, "slot": 0, "generation": 1,
                      "fieldEpoch": 2, "mapGeneration": 3, "encounterGeneration": 4},
                      "species": 165, "form": 0, "level": 5, "subjectIdentity": 99, "role": "WILD",
                      "behaviorFingerprint": 44, "matchedLayerMask": 7, "commitSequence": 1,
                      "motionPhase": "IDLE", "motionKind": "NONE", "authorityGeneration": 1,
                      "engineAnchorGeneration": 1, "presentationGeneration": 1}
        self.player = {"x": 550, "y": 381, "x_prev": 550, "y_prev": 381,
                       "flags": 0x11, "pos_x": (550 << 16) + 0x8000,
                       "pos_z": (381 << 16) + 0x8000, "movement_cmd": 12}
        self.player_pointer, self.map_id = 0x02210000, 34
        self.rt = SimpleNamespace(REPO=root, WILD_SYMBOLS=self.symbols, EXECUTED_FRAME_COUNT=10,
             G_FIELD_SYS_PTR=0x02230000, WILD_STATE=0x02230100,
             ACTOR_DESCRIPTOR={"state": {"address": 0x02200000,
                 "offsets": {"fieldEpoch": 12, "mapGeneration": 46}}, "capacities": {"actors": 10}},
             linked_symbols=lambda path: self.symbols, linked_symbol=lambda symbols, name: symbols[name],
             unsigned=lambda emu, address, size=4: int.from_bytes(self.read(address, size), "little"),
             actor_state=lambda emu, slot: deepcopy(self.actor),
             wild_spawn=lambda emu, slot: {"object": 0x02210000, "species": 165, "personality": 99},
             object_state=lambda emu, pointer: deepcopy(self.player),
             player_ptr=lambda emu: self.player_pointer, field_map_id=lambda emu: self.map_id)
        self.code_regions = [(0x02000000, bytes(stock))] + [
            (address, bytes((index + 1,)) * 32) for index, address in enumerate(self.symbols.values())]
        for address, data in self.code_regions:
            if address != 0x02000000:
                self.put(address, data)
        self.put(0x0201FD44, b"R" * 32)
        self.put(PLAYER_STEP_ADMISSION, b"S" * 32)
        self.put(SPAWN_REFRESH_HEIGHT, b"H" * 32)
        self.put(SPAWN_CREATE_OBJECT, b"C" * 32)
        self.put(MON_APPLY_FRIENDSHIP_MOD, b"F" * 32)
        self.put(0x02200008, struct.pack("<I", 100))
        self.put(self.rt.G_FIELD_SYS_PTR, struct.pack("<I", 0x02231000))
        self.put(0x0220000C, struct.pack("<H", 2))
        self.put(0x0220002E, struct.pack("<H", 3))
        self.prepare_spawn()
        self.prepared = False
        self.hooks = Hooks(self.rt, self.emu)
        self.observer = NativeObservation(self, self.hooks, lambda path, address, size: self.read(address, size))
        self.observer.install()

    def read(self, address, size):
        return bytes(self.memory.get(address + index, 0) for index in range(size))

    def put(self, address, data):
        self.memory.update({address + index: value for index, value in enumerate(data)})

    def prepare_spawn(self, *, origin=(550, 381), target=(552, 383), locomotion=4,
                      pointer=0x02224000, sp=0x027E3800):
        """The caller's real prepared-argument bytes, separate from actor state."""
        data = struct.pack("<iiB3xIHBBhhhhBB", *target, 0,
            self.actor["subjectIdentity"], self.actor["species"], self.actor["form"], self.actor["level"],
            *target, *origin, locomotion, 0)
        self.put(pointer, data)
        self.put(sp, struct.pack("<I", pointer))
        return data

    def register(self, address, callback):
        if callback is None:
            self.callbacks.pop(address, None)
        else:
            self.callbacks[address] = callback

    def enter(self, name, *, sp=0x027E3800, lr=0x02001001, **registers):
        self.regs.sp, self.regs.lr = sp, lr
        for key, value in registers.items(): setattr(self.regs, key, value)
        address = self.observer.calls[name]["address"]
        self.callbacks[address](address, 2)

    def returned(self, value, *, sp=0x027E3800, address=0x02001000):
        self.regs.r0, self.regs.sp = value, sp
        self.callbacks[address](address, 2)

    def admit_player_step(self, direction=3):
        self.enter("player-step-admitted", r0=self.player_pointer, r1=direction)
        dx, dz = ((0, -1), (0, 1), (-1, 0), (1, 0))[direction]
        self.player.update(x_prev=self.player["x"], y_prev=self.player["y"],
                           x=self.player["x"] + dx, y=self.player["y"] + dz)
        self.returned(self.player_pointer)


class SharedNativeObserverTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="native-observer-")
        self.addCleanup(self.directory.cleanup)
        self.f = Fixture(self.directory.name)

    def test_wild_battle_request_retains_primed_live_identity_and_input(self):
        f = self.f
        source = {"object": f.player_pointer, "personality": 99, "map_id": f.map_id,
                  "species": 165, "form": 0, "level": 5, "active": 1,
                  "object_id": 0xE0, "encounter_generation": 4}
        actor = deepcopy(f.actor)
        actor.update(presentationAttached=True, inputOwnership=0, reservationId=0,
                     logical={"x": 550, "y": 381}, identityVerified=True,
                     sourceIdentity=deepcopy(source), engineIdentity={"pointer": f.player_pointer,
                     "in_manager": True, "active": True, "object_manager": 1,
                     "current_manager": 1, "object_id": 0xE0, "spawn_object_id": 0xE0,
                     "object_map_id": f.map_id, "spawn_map_id": f.map_id,
                     "current_map_id": f.map_id, "encounter_generation": 4,
                     "script_id": 2074})
        context = {"fieldEpoch": 2, "mapGeneration": 3, "mapId": f.map_id}
        f.observer._battle_current = lambda slot: (
            f.observer._subject(slot), deepcopy(actor), deepcopy(source), deepcopy(context))
        f.put(f.rt.WILD_STATE + 252, struct.pack("<I", 99))
        f.put(f.rt.WILD_STATE + 256, struct.pack("<H", 165))
        f.put(f.rt.WILD_STATE + 262, bytes((0,)))
        f.put(f.rt.WILD_STATE + 948, struct.pack("<HH", 3, 4))
        for address in (0x04000130, 0x027FFFA8):
            f.put(address, struct.pack("<H", 0x2FFF))
        f.put(0x021D1144, struct.pack("<II", 1, 1))
        f.put(0x021D1150, struct.pack("<II", 1, 1))
        f.prepared = True
        f.enter("wild-battle-request", r0=0x02231000,
                r1=f.rt.WILD_STATE, r2=0)
        f.returned(1)
        f.observer.completed_frame(11)
        data = f.observer.drain()[0]["data"]
        self.assertEqual(data["observation"], "wild-battle-request")
        self.assertEqual(data["pending"], {"slot": 0, "species": 165,
                         "personality": 99, "encounterGeneration": 4})
        self.assertEqual(data["subject"]["handle"], f.actor["handle"])
        self.assertEqual(data["currentActor"]["sourceIdentity"], source)
        self.assertEqual(data["player"], f.player)
        self.assertEqual(data["input"]["physicalPressed"], 0)
        self.assertEqual((data["setupMode"], data["returnValue"]), ("prepared", 1))

    def test_wild_battle_request_rejects_unprimed_pending_identity(self):
        f = self.f
        f.observer._battle_current = lambda slot: (
            f.observer._subject(slot), deepcopy(f.actor),
            {"species": 165, "form": 0, "personality": 99,
             "encounter_generation": 4},
            {"fieldEpoch": 2, "mapGeneration": 3, "mapId": f.map_id})
        f.put(f.rt.WILD_STATE + 252, struct.pack("<I", 100))
        f.put(f.rt.WILD_STATE + 256, struct.pack("<H", 165))
        f.put(f.rt.WILD_STATE + 262, bytes((0,)))
        f.put(f.rt.WILD_STATE + 948, struct.pack("<HH", 3, 4))
        f.enter("wild-battle-request", r0=0x02231000,
                r1=f.rt.WILD_STATE, r2=0)
        f.returned(1)
        self.assertIn("NativeObservationError: battle pending identity differs",
                      f.hooks.error)

    def test_friendship_probe_is_late_diagnostic_only_and_times_real_return(self):
        f = self.f
        for mode, frame in ((None, 4641), ("omit-spawn-details", 4641),
                            ("baseline", 1307), ("baseline", 4645)):
            f.spawn_cost_probe = SimpleNamespace(mode=mode, gate=lambda observer, label: True)
            f.observer.wait_probe = SimpleNamespace(active={"afterQueueFrame": frame})
            f.enter("friendship-mod")
            self.assertEqual(f.observer.calls["friendship-mod"]["entered"], 0)
        f.spawn_cost_probe = SimpleNamespace(mode="baseline", gate=lambda observer, label: True)
        f.observer.wait_probe = SimpleNamespace(active={"afterQueueFrame": 4641})
        f.enter("friendship-mod", r0=0x02210000, r1=5, r2=67, lr=0x021E7943)
        f.guest_clock["arm9Timestamp"] += 900123
        f.returned(0, address=0x021E7942)
        row = f.observer.pending[-1]
        self.assertEqual((row["monPointer"], row["kind"], row["location"], row["callerReturn"]),
                         (0x02210000, 5, 67, 0x021E7943))
        self.assertEqual(row["guestTiming"]["arm9Ticks"], 900123)
        self.assertIsNone(f.hooks.error)
        f.put(MON_APPLY_FRIENDSHIP_MOD, b"X" * 32)
        f.enter("friendship-mod")
        self.assertIn("resident code identity differs", f.hooks.error)

    def test_archive_cost_is_opt_in_and_keeps_caller_arguments_without_spawn_parent(self):
        f = self.f
        for mode in (None, "omit-spawn-details"):
            f.spawn_cost_probe = SimpleNamespace(mode=mode, gate=lambda observer, label: True)
            f.enter("archive-open-cost")
            self.assertEqual(f.observer.calls["archive-open-cost"]["entered"], 0)
        f.spawn_cost_probe = SimpleNamespace(mode="baseline", gate=lambda observer, label: True)
        f.enter("archive-open-cost", r0=28, r1=4, r2=7, r3=9, lr=0x023C1235)
        f.guest_clock["arm9Timestamp"] += 999
        f.returned(0x02244000, address=0x023C1234)
        row = f.observer.pending[-1]
        self.assertEqual(row["arguments"], [28, 4, 7, 9])
        self.assertEqual(row["caller"], 0x023C1234)
        self.assertEqual(row["returnValue"], 0x02244000)
        self.assertEqual(row["guestTiming"]["arm9Ticks"], 999)
        self.assertFalse(row["acceptedProof"])
        self.assertFalse(f.observer.spawn_contexts)
        self.assertIsNone(f.hooks.error)

    def test_spawn_clock_measures_native_ticks_not_host_reads(self):
        f = self.f
        f.enter("spawn-prepared", r2=0, r3=0)
        for _ in range(20):
            f.emu.guest_clock()
        f.guest_clock["arm9Timestamp"] += 12345
        f.returned(0)
        row = f.observer.pending[-1]
        self.assertEqual(row["guestTiming"]["arm9Ticks"], 12345)
        self.assertIn("including-waits-and-irqs", row["guestTiming"]["scope"])

    def test_spawn_clock_rejects_paused_and_backward_readings(self):
        f = self.f
        f.guest_clock["running"] = False
        f.enter("spawn-prepared", r2=0, r3=0)
        self.assertIn("active native callback", f.hooks.error)
        f.hooks.error = None
        f.guest_clock["running"] = True
        f.enter("spawn-prepared", r2=0, r3=0)
        f.guest_clock["arm9Timestamp"] -= 1
        f.returned(0)
        self.assertIn("backwards", f.hooks.error)

    def test_destination_timing_is_scoped_to_exact_parent(self):
        f = self.f
        f.enter("spawn-destination-search", r0=f.rt.WILD_STATE, r1=0x02231000,
                r2=0xC0, r3=0x02224000)
        self.assertEqual(f.observer.calls["spawn-destination-search"]["entered"], 0)
        f.enter("spawn-queued", r0=f.rt.WILD_STATE, r1=0x02231000, r2=0, r3=0)
        f.put(0x027E37C0, struct.pack("<I", 0x02224000))
        f.enter("spawn-finalized", sp=0x027E37C0, lr=0x02001081,
                r0=f.rt.WILD_STATE, r1=0x02231000, r2=0, r3=0)
        f.enter("spawn-destination-search", sp=0x027E3780, lr=0x02001041,
                r0=f.rt.WILD_STATE, r1=0x02231000, r2=0xC0, r3=0x02224000)
        f.put(0x027E3740, struct.pack("<i", 383))
        f.enter("chain-landing-terrain", sp=0x027E3740, lr=0x02001101,
                r0=0x02231000, r1=0, r2=0, r3=552)
        f.returned(1, sp=0x027E3740, address=0x02001100)
        f.guest_clock["arm9Timestamp"] += 700
        f.returned(1, sp=0x027E3780, address=0x02001040)
        f.returned(0, sp=0x027E37C0, address=0x02001080)
        f.guest_clock["arm9Timestamp"] += 300
        f.returned(0)
        search, final, attempt = list(f.observer.pending)
        self.assertEqual(search["spawnAttemptId"], attempt["spawnAttemptId"])
        self.assertEqual(search["finalizationId"], final["finalizationId"])
        self.assertEqual(search["destinationMask"], 0xC0)
        self.assertEqual(search["candidateQueryCount"], 1)
        self.assertEqual(search["guestTiming"]["arm9Ticks"], 700)
        self.assertEqual(attempt["guestTiming"]["arm9Ticks"], 1000)
        self.assertFalse(attempt["queued"])

    def test_spawn_cost_children_require_live_parent_and_preserve_arguments(self):
        f = self.f
        for name in ("spawn-metadata", "spawn-class-selection", "spawn-object-create"):
            f.enter(name)
            self.assertEqual(f.observer.calls[name]["entered"], 0)
        f.enter("spawn-finalized", r0=f.rt.WILD_STATE, r1=0x02231000, r2=0, r3=0)
        for name in ("spawn-metadata", "spawn-class-selection", "spawn-object-create"):
            f.enter(name, sp=0x027E3780, lr=0x02001041, r0=163, r1=0, r2=123, r3=456)
            f.guest_clock["arm9Timestamp"] += 12
            f.returned(1, sp=0x027E3780, address=0x02001040)
            row = f.observer.pending[-1]
            self.assertEqual(row["arguments"], [163, 0, 123, 456])
            self.assertEqual(row["finalizationId"], 1)
            self.assertEqual(row["guestTiming"]["arm9Ticks"], 12)
        f.returned(0)
        self.assertIsNone(f.hooks.error)

    def test_preboot_resolution_and_nested_spawn_are_framed_only_at_complete_queue(self):
        f = self.f
        request, result = bytearray(44), bytearray(200)
        request[:2] = struct.pack("<H", 165)
        request[38] = 2
        result[:144] = bytes(range(72)) * 2
        struct.pack_into("<II", result, 172, 7, 44)
        f.put(0x02220000, request); f.put(0x02220100, result)
        f.enter("behavior-resolved", r2=0x02220000, r3=0x02220100)
        f.returned(0)
        f.enter("spawn-prepared", r2=0, r3=0)
        f.put(0x027E3788, struct.pack("<ii", 552, 383))
        f.enter("spawn-motion", sp=0x027E3780, lr=0x02001041, r2=0, r3=0x02210000)
        f.returned(1, sp=0x027E3780, address=0x02001040)
        f.returned(1)
        self.assertEqual(f.observer.drain(), [], "native return is not a coherent frame")
        f.observer.completed_frame(12)
        events = f.observer.drain()
        self.assertEqual([event["data"]["observation"] for event in events],
                         ["behavior-resolved", "spawn-motion", "spawn-prepared"])
        self.assertTrue(all(event["frame"] == 12 and event["data"]["setupMode"] == "normal" for event in events))
        spawn = events[-1]["data"]
        self.assertEqual(spawn["publicSubject"]["subjectIdentity"], 99)
        self.assertEqual(spawn["jumpReceipts"][0]["target"], [552, 383])
        self.assertEqual(spawn["jumpReceipts"][0]["origin"], [550, 381])
        self.assertEqual(spawn["preparedPointer"], 0x02224000)
        self.assertEqual(len(bytes.fromhex(spawn["preparedPrefixHex"])), 30)
        self.assertEqual(spawn["preparedEncounter"], {"personality": 99, "species": 165, "form": 0, "level": 5})
        self.assertEqual(spawn["startup"], {"target": [552, 383], "origin": [550, 381],
                                         "locomotion": 4, "hopDirection": 0,
                                         "targetBaseY": 0})
        self.assertEqual(spawn["jumpReceipts"][0]["playerAtEntry"],
                         {"pointer": 0x02210000, "mapId": 34, "tile": [550, 381]})
        profiles = f.observer.snapshot(include_profiles=True)["resolvedProfiles"]
        self.assertEqual(profiles[0]["fingerprint"], 44)
        self.assertEqual(profiles[0]["lanes"], [bytes(range(72)).hex()] * 2)
        self.assertEqual(f.hooks.error, None)

    def test_prepared_bytes_and_player_entry_tile_do_not_follow_later_changes(self):
        f = self.f
        raw = f.prepare_spawn(origin=(-12, 300), target=(4, 300))
        f.enter("spawn-prepared", r2=0, r3=0)
        f.put(0x02224000, bytes(30))
        f.put(0x027E3788, struct.pack("<ii", 4, 300))
        f.enter("spawn-motion", sp=0x027E3780, lr=0x02001041, r2=0, r3=0x02210000)
        f.player["x"] = 551
        f.returned(1, sp=0x027E3780, address=0x02001040); f.returned(1)
        f.observer.completed_frame(12)
        receipt = f.observer.drain()[-1]["data"]
        self.assertEqual(receipt["preparedPrefixHex"], raw.hex())
        self.assertEqual(receipt["startup"]["origin"], [-12, 300])
        self.assertEqual(receipt["jumpReceipts"][0]["playerAtEntry"]["tile"], [550, 381])
        self.assertIsNone(f.hooks.error)

    def resolve_profile(self, conditional_mask=0, *, sp=0x027E3740, lr=0x02001081):
        f = self.f
        request, result = bytearray(44), bytearray(200)
        struct.pack_into("<H", request, 0, 165)
        struct.pack_into("<I", request, 16, conditional_mask)
        request[38] = 2
        result[:144] = bytes(range(72)) * 2
        struct.pack_into("<II", result, 172, 7, 44)
        f.put(0x02220000, request); f.put(0x02220100, result)
        f.enter("behavior-resolved", sp=sp, lr=lr, r2=0x02220000, r3=0x02220100)
        return request, result

    def test_nested_spawn_resolvers_retain_both_same_output_requests_and_actual_source(self):
        f = self.f
        source = {"object": 0x02210000, "species": 165, "personality": 99,
                  "form": 0, "level": 5, "active": 1, "encounter_generation": 4}
        reads = []
        def wild_spawn(_emu, slot):
            reads.append(slot)
            return deepcopy(source)
        f.rt.wild_spawn = wild_spawn
        self.resolve_profile(); f.returned(0, sp=0x027E3740, address=0x02001080)
        f.enter("spawn-prepared", r2=0, r3=0)
        requests = []
        for conditional_mask in (0, 0x40):
            request, result = self.resolve_profile(conditional_mask)
            requests.append(request.hex())
            f.returned(0, sp=0x027E3740, address=0x02001080)
        source["personality"] = 100  # The completed receipts must not change.
        f.returned(1)
        self.assertEqual(f.observer.drain(), [])
        f.observer.completed_frame(12)
        events = f.observer.drain()
        self.assertEqual([e["data"]["observation"] for e in events],
                         ["behavior-resolved"] * 3 + ["spawn-prepared"])
        nested = events[-1]["data"]["resolverReceipts"]
        self.assertEqual([r["requestHex"] for r in nested], requests)
        self.assertEqual([r["slot"] for r in nested], [0, 0])
        self.assertEqual([r["sourceIdentity"]["personality"] for r in nested], [99, 99])
        self.assertEqual(reads, [0, 0])
        for receipt, event in zip(nested, events[1:3]):
            for key in ("requestHex", "resultHex", "resolved", "fingerprint", "sourceSha256", "lanes", "appliedOverrides"):
                self.assertEqual(receipt[key], event["data"][key])
        self.assertIsNone(f.hooks.error)

    def test_nested_resolver_uses_entry_spawn_context_not_current_top_slot(self):
        f = self.f
        f.rt.wild_spawn = lambda _emu, slot: {"object": 0x02210000 + slot * 0x12C,
            "species": 165, "personality": 99 + slot}
        f.enter("spawn-prepared", r2=0, r3=0)
        self.resolve_profile()
        f.prepare_spawn(pointer=0x02224100, sp=0x027E3700)
        f.enter("spawn-prepared", sp=0x027E3700, lr=0x020010C1, r2=0, r3=1)
        # Deliberately deliver a matching return while another spawn is top.
        # Ownership must remain the entry context, not mutable stack[-1].
        f.returned(0, sp=0x027E3740, address=0x02001080)
        f.returned(0, sp=0x027E3700, address=0x020010C0)
        f.returned(1)
        f.observer.completed_frame(12)
        events = f.observer.drain()
        spawns = [e["data"] for e in events if e["data"]["observation"] == "spawn-prepared"]
        self.assertEqual(spawns[0]["slot"], 1)
        self.assertEqual(spawns[0]["resolverReceipts"], [])
        self.assertEqual(spawns[1]["resolverReceipts"][0]["slot"], 0)
        self.assertEqual(spawns[1]["resolverReceipts"][0]["sourceIdentity"]["personality"], 99)
        self.assertIsNone(f.hooks.error)

    def test_failed_resolve_is_not_nested_success_and_source_pid_is_never_replaced(self):
        f = self.f
        f.rt.wild_spawn = lambda _emu, slot: {"object": 0x02210000, "species": 166, "personality": 17}
        f.enter("spawn-prepared", r2=0, r3=0)
        self.resolve_profile(); f.returned(3, sp=0x027E3740, address=0x02001080)
        self.resolve_profile(); f.returned(0, sp=0x027E3740, address=0x02001080)
        f.returned(1)
        f.observer.completed_frame(12)
        events = f.observer.drain()
        self.assertFalse(events[0]["data"]["resolved"])
        nested = events[-1]["data"]["resolverReceipts"]
        self.assertEqual(len(nested), 1)
        self.assertEqual(nested[0]["sourceIdentity"], {"object": 0x02210000, "species": 166, "personality": 17})
        self.assertEqual(events[-1]["data"]["preparedEncounter"]["personality"], 99)
        self.assertIsNone(f.hooks.error)

    def test_bad_prepared_pointer_fails_installed_entry_and_preserves_first_error(self):
        f = self.f
        f.put(0x027E3800, struct.pack("<I", 0x023FFFF0))
        f.enter("spawn-prepared", r2=0, r3=0)
        self.assertIn("outside aligned RAM/stack", f.hooks.error)
        first = f.hooks.error
        f.prepare_spawn(); f.enter("spawn-prepared", r2=0, r3=0)
        self.assertEqual(f.hooks.error, first)
        self.assertEqual(f.observer.calls["spawn-prepared"]["entered"], 0)
        self.assertFalse(f.observer.snapshot()["coverageComplete"])

    def test_successful_spawn_cannot_return_a_different_prepared_subject_or_slot(self):
        for key in ("subjectIdentity", "species", "form", "level", "slot"):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                f = Fixture(directory)
                f.enter("spawn-prepared", r2=0, r3=0)
                if key == "slot": f.actor["handle"]["slot"] = 1
                else: f.actor[key] += 1
                f.returned(1)
                self.assertIn("prepared encounter", f.hooks.error)
                f.observer.completed_frame(12)
                self.assertEqual(f.observer.drain(), [])
                f.observer.close()

    def test_nonwild_slot_is_ignored_and_wrong_nested_slot_is_not_attributed(self):
        f = self.f
        f.put(0x027E3800, bytes(4))
        f.enter("spawn-prepared", r2=0, r3=7)
        self.assertEqual(f.observer.calls["spawn-prepared"]["entered"], 0)
        self.assertIsNone(f.hooks.error)
        f.prepare_spawn(); f.enter("spawn-prepared", r2=0, r3=0)
        f.enter("spawn-motion", sp=0x027E3780, lr=0x02001041, r2=1, r3=0x02210000)
        self.assertEqual(f.observer.calls["spawn-motion"]["entered"], 0)
        f.returned(1)
        f.observer.completed_frame(12)
        self.assertEqual(f.observer.drain()[0]["data"]["jumpReceipts"], [])

    def test_bad_player_pointer_fails_installed_nested_call(self):
        f = self.f
        f.enter("spawn-prepared", r2=0, r3=0)
        f.player_pointer = 0
        f.put(0x027E3788, struct.pack("<ii", 552, 383))
        f.enter("spawn-motion", sp=0x027E3780, lr=0x02001041, r2=0, r3=0x02210000)
        self.assertIn("current player object", f.hooks.error)
        self.assertFalse(f.observer.snapshot()["coverageComplete"])

    def test_policy_request_response_and_scoped_rng_keep_actual_values(self):
        f = self.f
        call = bytearray(28)
        struct.pack_into("<HHI", call, 0, 1, 28, 0x02221000)
        call[8:10] = bytes((0, 4))
        f.put(0x02220000, call); f.put(0x02221000, bytes(range(72)))
        f.enter("walk-rng")  # Unrelated game RNG is not part of this contract.
        f.enter("walk-policy", r0=0x02220000)
        f.enter("walk-rng", sp=0x027E3780, lr=0x02001041)
        f.returned(0xFFFFFFFF, sp=0x027E3780, address=0x02001040)
        call[22:24] = bytes((5, 8)); f.put(0x02220000, call)
        f.returned(1)
        f.observer.completed_frame(11)
        data = f.observer.drain()[0]["data"]
        self.assertEqual(data["rngReturns"], [{"value": 0xFFFFFFFF, "actorFrame": 100, "nativeCycle": 10}])
        self.assertEqual(bytes.fromhex(data["responseHex"])[22:24], bytes((5, 8)))
        self.assertEqual(bytes.fromhex(data["requestHex"])[22:24], bytes((0, 0)))
        self.assertEqual(data["laneHex"], bytes(range(72)).hex())
        self.assertEqual(f.observer.calls["walk-rng"]["entered"], 1)
        # RESET has no lane; preserve that actual call, without inventing a
        # chain-reset reason or reading a null profile buffer.
        call = bytearray(28); struct.pack_into("<HH", call, 0, 1, 28)
        f.put(0x02220000, call); f.enter("walk-policy", r0=0x02220000); f.returned(1)
        f.observer.completed_frame(12)
        self.assertEqual(f.observer.drain()[0]["data"]["operation"], 0)
        self.assertIsNone(f.hooks.error)

    def test_rejections_and_unknown_subject_are_observations_not_false_success(self):
        f = self.f
        f.actor["active"] = False
        f.prepared = True
        f.enter("spawn-prepared", r2=0, r3=0); f.returned(0)
        f.observer.completed_frame(12)
        data = f.observer.drain()[0]["data"]
        self.assertEqual(data["returnValue"], 0)
        self.assertEqual(data["publicSubject"], {"status": "not-active", "slot": 0})
        self.assertEqual(data["jumpReceipts"], [])
        self.assertEqual(data["setupMode"], "prepared")

    def test_wrong_object_and_invalid_public_buffers_fail_same_installed_callbacks(self):
        f = self.f
        f.enter("spawn-prepared", r2=0, r3=0)
        f.enter("spawn-motion", sp=0x027E3780, lr=0x02001041, r2=0, r3=0x02210004)
        self.assertIn("current native object", f.hooks.error)
        self.assertFalse(f.observer.snapshot()["coverageComplete"])
        for address, size in ((0, 20), (0x02220001, 20), (0x027E3FB8, 20)):
            with self.subTest(address=address), self.assertRaises(NativeObservationError):
                public_bytes(f, address, size)

    def test_wrong_return_context_does_not_publish_a_receipt(self):
        f = self.f
        f.enter("spawn-prepared", r2=0, r3=0)
        f.returned(1, sp=0x027E37FC)
        f.observer.completed_frame(12)
        self.assertEqual(f.observer.drain(), [])
        self.assertEqual(f.observer.snapshot()["pendingCalls"], 1)
        f.returned(1)
        f.observer.completed_frame(13)
        self.assertEqual(len(f.observer.drain()), 1)

    def test_wrong_code_is_not_a_matching_native_call_and_loss_is_explicit(self):
        f = self.f
        address = f.observer.calls["spawn-prepared"]["address"]
        expected = f.read(address, 32)
        f.put(address, b"?" * 32)
        f.enter("spawn-prepared", r2=0, r3=0)
        self.assertEqual(f.observer.calls["spawn-prepared"]["entered"], 0)
        self.assertEqual(f.observer.calls["spawn-prepared"]["nonmatchingEntries"], 1)
        f.put(address, expected)
        f.observer.MAX_EVENTS = 1
        for _ in range(3):
            f.enter("spawn-prepared", r2=0, r3=0); f.returned(0)
        f.observer.completed_frame(12)
        self.assertEqual(f.observer.snapshot()["eventsDropped"], 2)
        self.assertFalse(f.observer.snapshot()["coverageComplete"])
        self.assertEqual(f.observer.drain()[0]["data"]["sequence"], 3)
        f.observer.close()
        self.assertEqual(f.callbacks, {})

    def test_chain_caller_accepts_only_authenticated_thumb_blx_target(self):
        f = self.f
        name = "OverworldWildSpawns_ResolveObjectLandingHeight"
        address = f.symbols[name] + 4
        instruction = struct.pack("<H", 0x4798)  # blx r3
        f.put(address, instruction)
        f.code_regions.append((address, instruction))
        f.regs.lr = (address + 2) | 1
        f.regs.r3 = SPAWN_REFRESH_HEIGHT | 1
        cache = {}

        f.observer._chain_caller(
            name, cache=cache, target=SPAWN_REFRESH_HEIGHT)
        self.assertEqual(cache, {address: instruction})

        f.regs.r3 = SPAWN_REFRESH_HEIGHT + 4 | 1
        with self.assertRaisesRegex(NativeObservationError, "BLX target differs"):
            f.observer._chain_caller(
                name, cache=cache, target=SPAWN_REFRESH_HEIGHT)

    def test_player_admission_is_not_completion_and_is_published_at_complete_queue(self):
        f = self.f
        f.observer.completed_frame(11)
        before = deepcopy(f.player)
        f.admit_player_step()
        self.assertIsNone(f.hooks.error)
        self.assertEqual(f.observer.drain(), [])
        self.assertEqual(f.observer.snapshot()["playerStepCount"], 0)
        self.assertEqual(f.observer.snapshot()["pendingPlayerSteps"], 1)
        self.assertEqual(f.observer.snapshot()["playerStepFrame"], 11)
        f.observer.completed_frame(12)
        receipt = f.observer.drain()[0]
        self.assertEqual(receipt["frame"], 12)
        self.assertEqual(receipt["data"]["observation"], "player-step-admitted")
        self.assertEqual(receipt["data"]["origin"], [550, 381])
        self.assertEqual(receipt["data"]["target"], [551, 381])
        self.assertEqual(receipt["data"]["objectBefore"], before)
        self.assertEqual(f.player["pos_x"], before["pos_x"], "admission does not move presentation")
        self.assertEqual(f.observer.snapshot()["playerStepCount"], 1)
        self.assertEqual(f.observer.snapshot()["playerStepFrame"], 12)

    def test_same_frame_second_admission_is_not_lost_and_npc_is_not_counted(self):
        f = self.f
        f.enter("player-step-admitted", r0=f.player_pointer + 0x12C, r1=0)
        self.assertEqual(f.observer.calls["player-step-admitted"]["entered"], 0)
        f.admit_player_step(0)
        f.admit_player_step(2)
        f.observer.completed_frame(12)
        receipts = f.observer.drain()
        self.assertEqual([event["data"]["stepIndex"] for event in receipts], [1, 2])
        self.assertEqual(f.observer.snapshot()["playerStepCount"], 2)
        f.admit_player_step(1)
        self.assertEqual(f.observer.snapshot()["playerStepCount"], 2,
                         "a later native endpoint cannot update the coherent counter")
        self.assertEqual(f.observer.snapshot()["pendingPlayerSteps"], 1)

    def test_wrong_live_admission_data_fails_the_same_installed_recorder(self):
        f = self.f
        f.enter("player-step-admitted", r0=f.player_pointer, r1=3)
        # Actual callback input has a two-tile reservation, not copied JSON.
        f.player.update(x_prev=550, y_prev=381, x=552)
        f.returned(0)
        self.assertIn("exactly one cardinal tile", f.hooks.error)
        self.assertEqual(f.observer.player_steps_admitted, 0)
        self.assertFalse(f.observer.snapshot()["coverageComplete"])

    def test_changed_player_identity_and_stock_code_are_recorder_failures(self):
        f = self.f
        f.enter("player-step-admitted", r0=f.player_pointer, r1=3)
        f.player_pointer += 0x12C
        f.returned(0)
        self.assertIn("current field/object", f.hooks.error)
        f.hooks.error = None
        f.put(PLAYER_STEP_ADMISSION, b"?" * 32)
        f.enter("player-step-admitted", r0=f.player_pointer, r1=3)
        self.assertIn("resident code identity differs", f.hooks.error)
        self.assertFalse(f.observer.snapshot()["coverageComplete"])


class WalkChainPolicyObserverTests(unittest.TestCase):
    """The installed policy hook observes commands; it does not execute them."""
    setUp = SharedNativeObserverTests.setUp

    @staticmethod
    def prepare_commit(f):
        state = f.rt.ACTOR_DESCRIPTOR["state"]
        state.update(size=2448, actorStride=172, actorPolicyOffset=140)
        state["offsets"]["actors"] = 68
        f.rt.ACTOR_DESCRIPTOR["structures"] = {"actorPolicyState": 32}
        call = WalkChainPolicyObserverTests.packet(3)
        struct.pack_into("<I", call, 4, 0x02221000)
        f.put(0x02220000, call)
        f.put(0x02221000, bytes(range(72)))
        f.put(0x02200000 + 208, bytes(range(32)))
        return call

    def test_commit_records_exact_lane_and_policy_for_both_roles_without_rng(self):
        for role in ("WILD", "MOUNTED"):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as directory:
                f = Fixture(directory)
                f.actor["role"] = role
                self.prepare_commit(f)
                f.enter("walk-policy", r0=0x02220000)
                self.assertEqual(f.observer.policy_contexts, [])
                f.put(0x02200000 + 208, bytes(reversed(range(32))))
                f.returned(1); f.observer.completed_frame(12)
                self.assertIsNone(f.hooks.error)
                data = f.observer.drain()[0]["data"]
                self.assertEqual(data["laneHex"], bytes(range(72)).hex())
                self.assertEqual(data["policyBeforeHex"], bytes(range(32)).hex())
                self.assertEqual(data["policyAfterHex"], bytes(reversed(range(32))).hex())
                self.assertEqual(data["policyBefore"]["counter"], 1)
                self.assertEqual(data["policyAfter"]["pending"], 9)
                self.assertEqual(data["publicSubject"]["role"], role)
                self.assertEqual(data["rngReturns"], [])
                f.observer.close()

    def test_commit_rejects_missing_subject_or_layout_before_call(self):
        changes = (lambda f: f.actor.update(active=False),
                   lambda f: f.actor.pop("authorityGeneration"),
                   lambda f: f.actor["handle"].update(slot=1),
                   lambda f: f.rt.ACTOR_DESCRIPTOR["state"].pop("actorStride"),
                   lambda f: f.rt.ACTOR_DESCRIPTOR["state"].update(actorStride=1),
                   lambda f: f.rt.ACTOR_DESCRIPTOR["state"].update(size=1787))
        for change in changes:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                f = Fixture(directory); self.prepare_commit(f); change(f)
                f.enter("walk-policy", r0=0x02220000)
                self.assertIsNotNone(f.hooks.error)
                self.assertFalse(f.observer.snapshot()["coverageComplete"])
                f.observer.close()

    def test_commit_rejects_changed_identity_lane_or_partial_policy_at_return(self):
        changes = [lambda f: f.actor.update(active=False),
                   lambda f: f.put(0x02221000, b"bad!"),
                   lambda f: f.put(0x02220004, struct.pack("<I", 0x02222000))]
        changes += [(lambda f, key=key: f.actor.update({key: f.actor[key] + 1}))
                    for key in ("subjectIdentity", "authorityGeneration", "engineAnchorGeneration", "presentationGeneration")]
        for change in changes:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                f = Fixture(directory); self.prepare_commit(f)
                f.enter("walk-policy", r0=0x02220000); change(f); f.returned(1)
                self.assertIsNotNone(f.hooks.error)
                f.observer.completed_frame(12)
                self.assertEqual(f.observer.drain(), [])
                f.observer.close()
        f = self.f; self.prepare_commit(f); f.enter("walk-policy", r0=0x02220000)
        original = f.read
        f.read = lambda address, size: original(address, size)[:-1] if address == 0x022000D0 else original(address, size)
        f.returned(1)
        self.assertIsNotNone(f.hooks.error)

    @staticmethod
    def packet(operation, slot=0):
        call = bytearray(28)
        struct.pack_into("<HHI", call, 0, 1, 28, 0)
        call[8:12] = bytes((slot, operation, 0xFD, 0x23))
        call[22:24] = bytes((5, 8))
        return call

    def test_all_five_retry_operations_keep_exact_bytes_without_lane_or_rng(self):
        for operation in range(9, 14):
            for accepted in (0, 1):
                with self.subTest(operation=operation, accepted=accepted), tempfile.TemporaryDirectory() as directory:
                    f = Fixture(directory)
                    request = self.packet(operation)
                    f.put(0x02220000, request)
                    f.enter("walk-policy", r0=0x02220000)
                    self.assertEqual(f.observer.calls["walk-policy"]["entered"], 1)
                    self.assertEqual(f.observer.policy_contexts, [], "no RNG lane belongs to this operation")
                    f.enter("walk-rng", sp=0x027E3780, lr=0x02001041)
                    self.assertEqual(f.observer.calls["walk-rng"]["entered"], 0)
                    response = bytearray(request); response[16] = accepted
                    response[22:24] = bytes((4, 7))
                    f.put(0x02220000, response); f.returned(accepted)
                    self.assertIsNone(f.hooks.error)
                    self.assertEqual(f.observer.drain(), [])
                    f.observer.completed_frame(12)
                    events = f.observer.drain()
                    self.assertEqual(len(events), 1)
                    data = events[0]["data"]
                    self.assertEqual((events[0]["frame"], data["operation"], data["slot"], data["returnValue"]),
                                     (12, operation, 0, accepted))
                    self.assertEqual(data["requestHex"], request.hex())
                    self.assertEqual(data["responseHex"], response.hex())
                    self.assertEqual(data["publicSubject"], data["publicSubjectAfter"])
                    self.assertEqual(data["publicSubject"]["subjectIdentity"], 99)
                    self.assertNotIn("laneHex", data)
                    self.assertEqual(data["rngReturns"], [])
                    self.assertTrue(f.observer.snapshot()["coverageComplete"])
                    f.observer.close()

    def test_retry_response_cannot_change_packet_or_public_subject_identity(self):
        changes = {
            "packet-version": lambda f, call: call.__setitem__(0, 2),
            "packet-size": lambda f, call: call.__setitem__(2, 24),
            "packet-slot": lambda f, call: call.__setitem__(8, 1),
            "packet-operation": lambda f, call: call.__setitem__(9, 12),
            "active": lambda f, call: f.actor.update(active=False),
            **{key: (lambda f, call, key=key: f.actor.update({key: f.actor[key] + 1}))
               for key in ("species", "form", "level", "subjectIdentity", "authorityGeneration",
                           "engineAnchorGeneration", "presentationGeneration")},
            "role": lambda f, call: f.actor.update(role="FOLLOWER"),
            **{"handle-" + key: (lambda f, call, key=key: f.actor["handle"].update({key: f.actor["handle"][key] + 1}))
               for key in ("value", "slot", "generation", "fieldEpoch", "mapGeneration", "encounterGeneration")},
        }
        for name, change in changes.items():
            with self.subTest(change=name), tempfile.TemporaryDirectory() as directory:
                f = Fixture(directory); call = self.packet(13)
                f.put(0x02220000, call); f.enter("walk-policy", r0=0x02220000)
                self.assertEqual(f.observer.calls["walk-policy"]["entered"], 1)
                change(f, call); f.put(0x02220000, call); f.returned(1)
                self.assertIsNotNone(f.hooks.error)
                self.assertFalse(f.observer.snapshot()["coverageComplete"])
                f.observer.completed_frame(12)
                self.assertEqual(f.observer.drain(), [])
                f.observer.close()

    def test_unknown_retry_subject_stays_unknown_and_unrequested_operations_stay_out(self):
        f = self.f
        f.actor["active"] = False
        f.put(0x02220000, self.packet(9)); f.enter("walk-policy", r0=0x02220000)
        self.assertEqual(f.observer.calls["walk-policy"]["entered"], 1)
        f.returned(0); f.observer.completed_frame(12)
        data = f.observer.drain()[0]["data"]
        self.assertEqual(data["publicSubject"], {"status": "not-active", "slot": 0})
        self.assertEqual(data["publicSubjectAfter"], data["publicSubject"])
        for operation in (5, 6, 7, 8, 14, 255):
            f.put(0x02220000, self.packet(operation)); f.enter("walk-policy", r0=0x02220000)
        self.assertEqual(f.observer.calls["walk-policy"]["entered"], 1)
        self.assertIsNone(f.hooks.error)

    def test_real_arm_header_anchors_retry_ids_packet_offsets_and_callback_signature(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c").read_text()
        declaration = re.search(r"static BOOL ActorSystem_ReduceWalk\([^;{]+\)\n", source)
        self.assertIsNotNone(declaration)
        compiler = shutil.which(os.environ.get("ARM_NONE_EABI_CC", "arm-none-eabi-gcc"))
        if compiler is None and Path("/opt/homebrew/bin/arm-none-eabi-gcc").is_file():
            compiler = "/opt/homebrew/bin/arm-none-eabi-gcc"
        self.assertIsNotNone(compiler, "the real ARM public ABI must be compiled")
        program = '#include "overworld_actor_system_internal.h"\n#include <stddef.h>\n' + declaration[0] + ';\n'
        program += '_Static_assert(sizeof(OverworldActorPolicyState) == 32, "policy size");\n'
        for offset, name in enumerate(("direction", "tileCounter", "speed", "baseSpeed", "spotState",
                                       "skidRemaining", "turnDirection", "resumeSpeed")):
            program += f'_Static_assert(offsetof(OverworldWildWalkMomentumState, {name}) == {offset}, "momentum {name}");\n'
        program += '_Static_assert(sizeof(struct OverworldWildBehaviorProfileData) == 72, "lane size");\n'
        program += '_Static_assert(offsetof(OverworldActorRuntimeSlot, policy) == sizeof(OverworldActorStateSnapshot) + sizeof(OverworldMotionState), "policy follows actor motion");\n'
        for name, offset in (("walkMomentum", 0), ("chainStepsRemaining", 16), ("deferredChainPauseTicks", 17),
                             ("deferredChainPauseAction", 18), ("variancePhase", 19), ("bufferedDirection", 20),
                             ("stopPending", 21), ("pendingStep", 22), ("pendingSkid", 23), ("streamState", 24)):
            program += f'_Static_assert(offsetof(OverworldActorPolicyState, {name}) == {offset}, "policy {name}");\n'
        self.assertIn("->reduceWalk(walkPolicy)", source)
        self.assertRegex(source, r"sActorMovementPolicy = \{[^}]*ActorSystem_ReduceWalk")
        self.assertRegex(source, r"gOverworldActorSystemMovementPolicyServiceEntry\s*[^=]*=\s*\{[^}]*&sActorMovementPolicy")
        operations = ("RESET", "INPUT", "START_RESULT", "COMMIT", "CHAIN_COMMIT", "INSPECT",
                      "BIND_PROFILE", "SAMPLE_VARIANCE", "BUFFER_DIRECTION", "CHAIN_TAKE_PENDING",
                      "CHAIN_REPOSITION_BEGIN", "CHAIN_REPOSITION_ADVANCE", "CHAIN_REPOSITION_FINISH",
                      "CHAIN_PUT_PENDING", "PUBLISH_EFFECT")
        for expected, name in enumerate(operations):
            program += f'_Static_assert(OVERWORLD_ACTOR_WALK_POLICY_{name} == {expected}, "{name}");\n'
        program += '_Static_assert(OVERWORLD_ACTOR_WALK_POLICY_VERSION == 1, "version");\n'
        program += '_Static_assert(sizeof(OverworldActorWalkPolicyCall) == 28, "size");\n'
        for name, offset in (("version", 0), ("size", 2), ("lane", 4), ("actorSlot", 8), ("operation", 9),
                             ("direction", 10), ("distance", 11), ("decision", 16), ("chainAction", 22), ("chainTicks", 23)):
            program += f'_Static_assert(offsetof(OverworldActorWalkPolicyCall, {name}) == {offset}, "{name} offset");\n'
        program += '_Static_assert(__builtin_types_compatible_p(__typeof__(&ActorSystem_ReduceWalk), BOOL (*)(OverworldActorWalkPolicyCall *)), "callback ABI");\n'
        command = [compiler, "-x", "c", "-std=c11", "-mthumb", "-mcpu=arm946e-s",
                   "-I" + str(root / "include"), "-fsyntax-only", "-"]
        checked = subprocess.run(command, input=program, text=True, capture_output=True, timeout=20)
        self.assertEqual(checked.returncode, 0, checked.stderr[-3000:])
        for old, new in (('== 9, "CHAIN_TAKE_PENDING"', '== 8, "CHAIN_TAKE_PENDING"'),
                         ('== 22, "chainAction offset"', '== 21, "chainAction offset"')):
            self.assertIn(old, program)
            wrong = subprocess.run(command, input=program.replace(old, new), text=True, capture_output=True, timeout=20)
            self.assertNotEqual(wrong.returncode, 0)


class SpawnFinalizationObserverTests(unittest.TestCase):
    setUp = SharedNativeObserverTests.setUp
    resolve_profile = SharedNativeObserverTests.resolve_profile

    def test_profile_timing_only_during_spawn_work(self):
        f = self.f
        self.resolve_profile()
        f.returned(0, sp=0x027E3740, address=0x02001080)
        self.assertNotIn("guestTiming", f.observer.pending[-1])
        f.enter("spawn-finalized", r0=f.rt.WILD_STATE, r1=0x02231000, r2=0, r3=0)
        self.resolve_profile()
        f.guest_clock["arm9Timestamp"] += 456
        f.returned(0, sp=0x027E3740, address=0x02001080)
        self.assertEqual(f.observer.pending[-1]["guestTiming"]["arm9Ticks"], 456)
        f.returned(0)
        self.assertIsNone(f.hooks.error)

    def finalize(self, *, incoming=(553, 382), outgoing=(552, 383), input_pid=98,
                 result=1, resolver=True, pointer=0x02224000, slot=0):
        f = self.f
        f.prepare_spawn(target=incoming, pointer=pointer)
        f.put(pointer + 12, struct.pack("<I", input_pid))
        f.enter("spawn-finalized", r0=f.rt.WILD_STATE, r1=0x02231000, r2=0, r3=slot)
        if resolver:
            self.resolve_profile()
            f.returned(0, sp=0x027E3740, address=0x02001080)
        if result:
            f.prepare_spawn(target=outgoing, pointer=pointer)
        f.returned(result)

    def spawn(self, *, result=1, **overrides):
        f = self.f
        args = dict(r0=f.rt.WILD_STATE, r1=0x02231000, r2=0, r3=0)
        args.update(overrides)
        f.enter("spawn-prepared", **args)
        f.returned(result)
        f.observer.completed_frame(12)
        events = f.observer.drain()
        self.assertIsNone(f.hooks.error)
        return events[-1]["data"], events

    def test_real_arm_public_layout_and_function_signature_anchor(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
        declaration = re.search(
            r"static BOOL __attribute__\(\(noinline, optimize\(\"Os\""
            r"(?:, \"tree-dominator-opts\")?\)\)\)\s+"
            r"OverworldWildSpawns_FinalizePreparedSpawn\([^;{]+\)\n", source)
        self.assertIsNotNone(declaration, "the observed native signature must remain explicit")
        compiler = shutil.which(os.environ.get("ARM_NONE_EABI_CC", "arm-none-eabi-gcc"))
        if compiler is None and Path("/opt/homebrew/bin/arm-none-eabi-gcc").is_file():
            compiler = "/opt/homebrew/bin/arm-none-eabi-gcc"
        self.assertIsNotNone(compiler, "ARM header check is required; missing compiler is not a pass")
        program = '#include "overworld_wild_helper.h"\n#include <stddef.h>\n' + declaration[0] + ';\n' + '''
_Static_assert(sizeof(OverworldWildSpawnPosition) == 12, "position");
_Static_assert(sizeof(OverworldWildRolledEncounter) == 8, "encounter");
_Static_assert(sizeof(OverworldWildSpawnStartup) == 16, "startup");
_Static_assert(offsetof(OverworldWildPreparedSpawn, encounter) == 12, "input encounter");
_Static_assert(offsetof(OverworldWildPreparedSpawn, startup) == 20, "input boundary");
_Static_assert(offsetof(OverworldWildPreparedSpawn, startup) + sizeof(OverworldWildSpawnStartup) == 36, "final boundary");
_Static_assert(__builtin_types_compatible_p(__typeof__(&OverworldWildSpawns_FinalizePreparedSpawn),
    BOOL (*)(OverworldWildSpawnState *, FieldSystem *, OverworldWildSpawnTerrain, int, OverworldWildPreparedSpawn *)), "native ABI");
'''
        command = [compiler, "-x", "c", "-std=c11", "-mthumb", "-mcpu=arm946e-s",
                   "-I" + str(root / "include"), "-fsyntax-only", "-"]
        checked = subprocess.run(command, input=program, text=True, capture_output=True, timeout=20)
        self.assertEqual(checked.returncode, 0, checked.stderr[-3000:])
        wrong = subprocess.run(command, input=program.replace('== 20, "input boundary"', '== 21, "input boundary"'),
                               text=True, capture_output=True, timeout=20)
        self.assertNotEqual(wrong.returncode, 0, "a changed public offset must reject the decoder")

    def test_installed_finalizer_retains_incoming_and_final_pid_with_nested_provenance(self):
        self.finalize(input_pid=99 ^ 0x10000000)
        receipt, events = self.spawn()
        final = next(row["data"] for row in events if row["data"]["observation"] == "spawn-finalized")
        self.assertEqual(receipt["finalization"], {"status": "matched", "receipt": final})
        self.assertLess(final["sequence"], receipt["sequence"])
        self.assertEqual(final["inputEncounter"]["personality"], 99 ^ 0x10000000)
        self.assertEqual(final["preparedEncounter"]["personality"], 99)
        self.assertEqual(final["inputPosition"], [553, 382])
        self.assertEqual(final["position"], [552, 383])
        self.assertEqual(final["startup"]["target"], [552, 383])
        self.assertEqual(len(bytes.fromhex(final["inputPrefixHex"])), 20)
        self.assertEqual(len(bytes.fromhex(final["preparedPrefixHex"])), 30)
        self.assertEqual(final["resolverReceipts"][0]["finalizationId"], final["finalizationId"])
        self.assertEqual(final["resolverReceipts"][0]["inputEncounter"], final["inputEncounter"])
        self.assertEqual(final["resolverReceipts"][0]["sourceSha256"], self.f.observer.source_hash)
        self.assertEqual(receipt["resolverReceipts"], [], "do not relabel finalizer calls as later spawn calls")

    def test_failed_finalizer_reads_no_uninitialized_startup_and_cannot_pair(self):
        f = self.f
        reads, original = [], f.read
        def read(pointer, size):
            reads.append((pointer, size))
            return original(pointer, size)
        f.read = read
        self.finalize(result=0)
        self.assertIn((0x02224000, 20), reads)
        self.assertNotIn((0x02224000, 30), reads)
        receipt, events = self.spawn(result=0)
        final = next(row["data"] for row in events if row["data"]["observation"] == "spawn-finalized")
        self.assertFalse(final["pairEligible"])
        self.assertNotIn("preparedPrefixHex", final)
        self.assertEqual(receipt["finalization"]["status"], "missing")

    def test_missing_consumed_and_completed_queue_old_receipts_cannot_pair(self):
        receipt, _ = self.spawn()
        self.assertEqual(receipt["finalization"]["status"], "missing")
        self.finalize()
        receipt, _ = self.spawn(result=0)
        self.assertEqual(receipt["finalization"]["status"], "matched")
        receipt, _ = self.spawn()
        self.assertEqual(receipt["finalization"]["status"], "missing", "failed creation also consumes its input")
        self.finalize()
        self.f.observer.completed_frame(13)
        receipt, _ = self.spawn()
        self.assertEqual(receipt["finalization"]["status"], "missing")

    def test_wrong_pid_or_other_prefix_byte_rejects_and_consumes_pair(self):
        for offset in (0, 8, 12, 16, 18, 19, 20, 24, 28, 29):
            with self.subTest(offset=offset):
                self.finalize(resolver=False)
                f = self.f
                f.put(0x02224000 + offset, bytes((f.read(0x02224000 + offset, 1)[0] ^ 1,)))
                receipt, _ = self.spawn(result=0)
                self.assertEqual(receipt["finalization"]["status"], "prefix-mismatch")
                f.prepare_spawn()
                receipt, _ = self.spawn()
                self.assertEqual(receipt["finalization"]["status"], "missing")

    def test_only_successful_enqueue_can_carry_exact_receipt_one_queue(self):
        f = self.f
        for boundaries, expected in ((1, "matched"), (2, "missing")):
            f.regs.r0, f.regs.r1, f.regs.r2, f.regs.r3 = f.rt.WILD_STATE, 0x02231000, 0, 0
            before = f.observer._spawn_queue_before()
            self.finalize(resolver=False)
            f.observer._spawn_queue_after(before, {"returnValue": 1})
            for index in range(boundaries):
                f.observer.completed_frame(20 + index)
            receipt, _ = self.spawn()
            self.assertEqual(receipt["finalization"]["status"], expected)

    def test_queued_destination_scan_keeps_one_attempt_across_completed_frames(self):
        f = self.f

        f.enter("spawn-queued", r0=f.rt.WILD_STATE, r1=0x02231000, r2=0, r3=0)
        f.put(0x027E37C0, struct.pack("<I", 0x02224000))
        f.enter("spawn-finalized", sp=0x027E37C0, lr=0x02001081,
                r0=f.rt.WILD_STATE, r1=0x02231000, r2=0, r3=0)
        self.resolve_profile(sp=0x027E3760, lr=0x020010C1)
        f.returned(0, sp=0x027E3760, address=0x020010C0)
        f.enter("spawn-destination-search", sp=0x027E3720, lr=0x02001041,
                r0=f.rt.WILD_STATE, r1=0x02231000, r2=448, r3=0x02224000)
        f.returned(0, sp=0x027E3720, address=0x02001040)
        f.returned(0, sp=0x027E37C0, address=0x02001080)
        f.returned(1)
        f.observer.completed_frame(12)
        first = f.observer.drain()
        queued = next(row["data"] for row in first
                      if row["data"]["observation"] == "spawn-queued")
        attempt_id = queued["spawnAttemptId"]
        self.assertTrue(queued["pendingDestination"])
        self.assertEqual(next(row["data"] for row in first
                             if row["data"]["observation"] == "spawn-destination-search")
                         ["candidateQueryCount"], 0)

        f.enter("spawn-finalized", sp=0x027E37C0, lr=0x02001081,
                r0=f.rt.WILD_STATE, r1=0x02231000, r2=0, r3=0)
        self.resolve_profile(sp=0x027E3760, lr=0x020010C1)
        f.returned(0, sp=0x027E3760, address=0x020010C0)
        f.enter("spawn-destination-search", sp=0x027E3720, lr=0x02001041,
                r0=f.rt.WILD_STATE, r1=0x02231000, r2=448, r3=0x02224000)
        f.enter("chain-landing-terrain", sp=0x027E36E0, lr=0x02001101,
                r0=0x02231000, r1=0, r2=0, r3=552)
        f.returned(1, sp=0x027E36E0, address=0x02001100)
        f.returned(0, sp=0x027E3720, address=0x02001040)
        f.returned(0, sp=0x027E37C0, address=0x02001080)
        f.observer.completed_frame(13)
        second = f.observer.drain()
        destination = next(row["data"] for row in second
                           if row["data"]["observation"] == "spawn-destination-search")
        final = next(row["data"] for row in second
                     if row["data"]["observation"] == "spawn-finalized")
        self.assertEqual(destination["spawnAttemptId"], attempt_id)
        self.assertEqual(destination["candidateQueryCount"], 1)
        self.assertEqual(destination["finalizationId"], final["finalizationId"])
        self.assertIsNone(f.hooks.error)
        # No nested fresh finalizer: an old value cannot be promoted to queued.
        self.finalize(resolver=False)
        f.regs.r0, f.regs.r1, f.regs.r2, f.regs.r3 = f.rt.WILD_STATE, 0x02231000, 0, 0
        before = f.observer._spawn_queue_before()
        with self.assertRaisesRegex(NativeObservationError, "exact finalizer or pending destination scan"):
            f.observer._spawn_queue_after(before, {"returnValue": 1})

    def test_state_field_terrain_pointer_map_epoch_and_mode_mismatch_reject(self):
        f = self.f
        for change in ("state", "field", "terrain", "pointer", "map", "epoch", "generation", "mode"):
            with self.subTest(change=change):
                f.map_id, f.prepared = 34, False
                f.put(0x0220000C, struct.pack("<H", 2)); f.put(0x0220002E, struct.pack("<H", 3))
                self.finalize(resolver=False)
                args = {}
                if change == "state": args["r0"] = f.rt.WILD_STATE + 4
                if change == "field": args["r1"] = 0x02231004
                if change == "terrain": args["r2"] = 1
                if change == "pointer": f.prepare_spawn(pointer=0x02224100)
                if change == "map": f.map_id = 35
                if change == "epoch": f.put(0x0220000C, struct.pack("<H", 3))
                if change == "generation": f.put(0x0220002E, struct.pack("<H", 4))
                if change == "mode": f.prepared = True
                receipt, _ = self.spawn(result=0, **args)
                self.assertEqual(receipt["finalization"]["status"], "context-mismatch")

    def test_fresh_failed_finalizer_invalidates_old_success_even_with_reused_bytes(self):
        self.finalize(resolver=False)
        self.finalize(result=0, resolver=False)
        self.f.prepare_spawn()
        receipt, _ = self.spawn()
        self.assertEqual(receipt["finalization"]["status"], "missing")

    def test_reused_pointer_in_another_slot_invalidates_old_pair(self):
        self.finalize(resolver=False)
        self.finalize(slot=1, resolver=False)
        receipt, _ = self.spawn(result=0)
        self.assertEqual(receipt["finalization"]["status"], "missing")
        receipt, _ = self.spawn(result=0, r3=1)
        self.assertEqual(receipt["finalization"]["status"], "missing")

    def test_finalizer_world_change_or_nested_supersession_cannot_restore_old_pair(self):
        f = self.f
        f.enter("spawn-finalized", r0=f.rt.WILD_STATE, r1=0x02231000, r2=0, r3=0)
        f.map_id = 35
        f.returned(1)
        receipt, _ = self.spawn(result=0)
        self.assertEqual(receipt["finalization"]["status"], "missing")
        f.prepare_spawn()
        f.enter("spawn-finalized", r0=f.rt.WILD_STATE, r1=0x02231000, r2=0, r3=0)
        f.prepare_spawn(sp=0x027E3700)
        f.enter("spawn-finalized", sp=0x027E3700, lr=0x02001041,
                r0=f.rt.WILD_STATE, r1=0x02231000, r2=0, r3=0)
        f.returned(1, sp=0x027E3700, address=0x02001040)
        f.returned(1)
        receipt, events = self.spawn()
        finals = [row["data"] for row in events if row["data"]["observation"] == "spawn-finalized"]
        self.assertTrue(finals[0]["pairEligible"])
        self.assertFalse(finals[1]["pairEligible"])
        self.assertEqual(receipt["finalization"]["receipt"]["finalizationId"], finals[0]["finalizationId"])

    def test_finalizer_authentication_and_wild_scope_use_installed_callbacks(self):
        f = self.f
        address = f.observer.calls["spawn-finalized"]["address"]
        expected = f.read(address, 32)
        f.put(address, b"?" * 32)
        f.enter("spawn-finalized", r0=f.rt.WILD_STATE, r1=0x02231000, r2=0, r3=0)
        self.assertEqual(f.observer.calls["spawn-finalized"]["entered"], 0)
        f.put(address, expected)
        f.enter("spawn-finalized", r3=7)
        self.assertEqual(f.observer.calls["spawn-finalized"]["entered"], 0)
        self.finalize(resolver=False)
        self.assertEqual(f.observer.calls["spawn-finalized"]["returned"], 1)
        f.observer.close()
        self.assertEqual(f.callbacks, {})
        self.assertEqual(f.observer.finalizations, {})


class CallbackPoolPlacementTests(unittest.TestCase):
    """Installed native callbacks feed the checker without editing any receipt."""
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="callback-pool-placement-")
        self.addCleanup(self.directory.cleanup)
        self.authored = {"overrideProfiles": [
            {"name": "Flying insect", "fields": {"spawnDestination": {
                "operator": "replace", "value": "OW_WILD_SPAWN_DESTINATION_POOL"}}},
            {"name": "Default active", "fields": {}},
        ]}
        self.f = Fixture(self.directory.name, authored_profiles=self.authored)
        self.addCleanup(self.f.observer.close)

    def observe_spawn(self, *, incoming=(552, 383), outgoing=(552, 383),
                      pointer=0x02224000, terrain=0):
        f = self.f
        # The real SpawnOne uses a stack-local OverworldWildPreparedSpawn.
        # This memory is distinct from the active call's [sp] argument slot
        # and from its nested resolver frame. The other test also covers RAM.
        f.prepare_spawn(target=incoming, pointer=pointer)
        f.put(pointer + 12, struct.pack("<I", f.actor["subjectIdentity"] ^ 0x10000000))
        args = dict(r0=f.rt.WILD_STATE, r1=0x02231000, r2=terrain, r3=0)
        f.enter("spawn-finalized", **args)
        request, result = bytearray(44), bytearray(200)
        struct.pack_into("<H", request, 0, f.actor["species"])
        request[8:10] = bytes((f.actor["level"], terrain))
        request[38] = 2
        for lane in (0, 72):
            # Observe the known broad native compatibility result, rather
            # than substituting the expected POOL-preservation rule into it.
            struct.pack_into("<HH", result, lane + 52, 15, 1023)
        struct.pack_into("<IIIII", result, 160, 1, 0, 0, 3, f.actor["behaviorFingerprint"])
        f.put(0x02220000, request); f.put(0x02220100, result)
        f.enter("behavior-resolved", sp=0x027E3740, lr=0x02001081,
                r2=0x02220000, r3=0x02220100)
        f.returned(0, sp=0x027E3740, address=0x02001080)
        f.prepare_spawn(target=outgoing, origin=(outgoing[0] - 16, outgoing[1]), pointer=pointer)
        f.returned(1)
        f.enter("spawn-prepared", **args)
        f.returned(1)
        f.observer.completed_frame(12)
        events = f.observer.drain()
        self.assertIsNone(f.hooks.error)
        self.assertEqual([row["data"]["observation"] for row in events],
                         ["behavior-resolved", "spawn-finalized", "spawn-prepared"])
        spawn = events[-1]["data"]
        self.assertEqual(spawn["finalization"], {"status": "matched", "receipt": events[-2]["data"]})
        return spawn

    def check_untouched_receipt(self, spawn):
        before = deepcopy(spawn)
        try:
            return check_pool_spawn_receipt(spawn, source_sha256=self.f.observer.source_hash,
                                           authored_profiles=self.authored)
        finally:
            self.assertEqual(spawn, before, "the callback record is not rewritten for the checker")

    def test_preserved_site_callback_to_checker_with_native_pid_change(self):
        spawn = self.observe_spawn()
        result = self.check_untouched_receipt(spawn)
        self.assertTrue(result["passed"])
        self.assertEqual(result["sourcePosition"], result["landingTarget"])
        self.assertNotEqual(result["inputPersonality"], result["finalPersonality"])
        self.assertEqual(result["authoredLayer"], {"index": 0, "name": "Flying insect"})

    def test_changed_own_site_reaches_checker_as_measured_failure(self):
        spawn = self.observe_spawn(incoming=(553, 382), outgoing=(552, 383))
        result = self.check_untouched_receipt(spawn)
        self.assertFalse(result["passed"])
        self.assertEqual(result["reason"], "pool-destination-replaced")
        self.assertEqual(result["sourcePosition"], [553, 382])
        self.assertEqual(result["destination"], [552, 383])

    def test_native_stack_prepared_value_reaches_checker_for_surf_pool(self):
        spawn = self.observe_spawn(pointer=0x027E3900, terrain=1)
        self.assertEqual(spawn["preparedPointer"], 0x027E3900)
        result = self.check_untouched_receipt(spawn)
        self.assertTrue(result["passed"], "a native stack argument is not an invalid prepared pointer")
        self.assertEqual(result["terrain"], 1, "an authored Surf pool is not rewritten as Land")


if __name__ == "__main__":
    unittest.main()
