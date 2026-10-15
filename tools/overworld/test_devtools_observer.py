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
from unittest.mock import patch
import unittest

from tools.overworld.devtools_engine import Hooks
from tools.overworld.devtools_observer import (FRIENDSHIP_WAIT_WINDOW,
    HEART_BUBBLE, MODEL_DATA_GETTER, MODEL_DATA_GETTER_CODE,
    MODEL_VISIBILITY_SETTER, MODEL_VISIBILITY_SETTER_CODE, MON_APPLY_FRIENDSHIP_MOD, PLAY_CRY,
    MODEL_POSITION_SETTER, MODEL_POSITION_SETTER_CODE,
    NativeObservation, NativeObservationError, QUERY_SPAWN_OWNERS, QUERY_SPAWN_READ_CAP, QUERY_SPAWN_CALLERS,
    PLAYER_STEP_ADMISSION, SPAWN_REFRESH_HEIGHT, SPAWN_CREATE_OBJECT,
    public_bytes)
from tools.overworld.devtools_spawn_cost_probe import enable_spawn_cost_probe
from tools.overworld.devtools_spawn_measurement import check_pool_spawn_receipt
from tools.overworld.devtools_runtime import DevtoolsFailure, DevtoolsSession


class Fixture:
    def __init__(self, directory, *, authored_profiles=None,
                 battle_symbols=("OverworldWildSpawns_TryStartBattleForSlot",), missing_spawn_wrapper=False):
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        (root / "data").mkdir()
        (root / "base").mkdir()
        (root / "data/overworld_behavior_profiles.json").write_text(json.dumps(authored_profiles or {}))
        stock = bytearray(max(SPAWN_REFRESH_HEIGHT, MON_APPLY_FRIENDSHIP_MOD) - 0x02000000 + 32)
        stock[0x1FD44:0x1FD64] = b"R" * 32
        stock[0x78D8:0x78F8] = b"Q" * 32
        stock[PLAYER_STEP_ADMISSION - 0x02000000:PLAYER_STEP_ADMISSION - 0x02000000 + 32] = b"S" * 32
        stock[SPAWN_REFRESH_HEIGHT - 0x02000000:SPAWN_REFRESH_HEIGHT - 0x02000000 + 32] = b"H" * 32
        stock[SPAWN_CREATE_OBJECT - 0x02000000:SPAWN_CREATE_OBJECT - 0x02000000 + 32] = b"C" * 32
        stock[MON_APPLY_FRIENDSHIP_MOD - 0x02000000:MON_APPLY_FRIENDSHIP_MOD - 0x02000000 + 32] = b"F" * 32
        stock[PLAY_CRY - 0x02000000:PLAY_CRY - 0x02000000 + 32] = b"Y" * 32
        stock[MODEL_DATA_GETTER - 0x02000000:
              MODEL_DATA_GETTER - 0x02000000 + len(MODEL_DATA_GETTER_CODE)] = MODEL_DATA_GETTER_CODE
        stock[MODEL_VISIBILITY_SETTER - 0x02000000:
              MODEL_VISIBILITY_SETTER - 0x02000000 + len(MODEL_VISIBILITY_SETTER_CODE)] = MODEL_VISIBILITY_SETTER_CODE
        stock[MODEL_POSITION_SETTER - 0x02000000:
              MODEL_POSITION_SETTER - 0x02000000 + len(MODEL_POSITION_SETTER_CODE)] = MODEL_POSITION_SETTER_CODE
        # Real retail Walk BL plus its two unchanged continuation instructions.
        offset = 0x0205DA34 - 0x0205D4C6
        stock[0x5D4C2:0x5D4CA] = struct.pack(
            "<HH", 0xF000 | ((offset >> 12) & 0x7FF),
            0xF800 | ((offset >> 1) & 0x7FF)) + bytes.fromhex("041c301c")
        (root / "base/arm9.bin").write_bytes(stock)
        names = ("OverworldWildSpawns_SpawnPreparedEncounter", "OverworldWildSpawns_StartPreparedCustomJumpCommand",
                 "BehaviorResolver_Resolve", "ActorSystem_ReduceWalk", "OverworldWildSpawns_FinalizePreparedSpawn",
                 "OverworldWildSpawns_RunChainReposition", "OverworldWildSpawns_IsBehaviorAllowedHopLandingTile",
                 "OverworldWildRuntime_RequestMotion", "OverworldWildSpawns_StartPreparedCustomJumpCommandTimed",
                 "OverworldWildSpawns_StartPreparedCustomJumpCommandWithArc",
                 "OverworldActorHopPlanner_Plan", "ActorSystem_RequestMotion",
                 "OverworldWildSpawns_QuerySurface",
                 "OverworldWildSpawns_IsTileOccupiedByObject", "OverworldWildSpawns_IsTileOccupiedByNonPlayerObject",
                 "OverworldWildSpawns_ClassifyBehaviorHopLandingTile",
                 "OverworldWildSpawns_ResolveObjectLandingHeight", "OverworldWildSpawns_ApplySurfaceHeight",
                 "OverworldWildSpawns_TryPickSpawnDestinationMask",
                 "OverworldWildBehavior_TryGetSpawnMetadata", "BehaviorResolver_InspectClass",
                 "OverworldWildSpawns_SpawnOne", "OverworldWildSpawns_TryRefill",
                 "OverworldWildHelper_TryPrepareSpawn", "OverworldWildSpawns_HelperLoadArchiveData",
                 "OverworldWildSpawns_FrameMovementTask", "OverworldWildSpawns_TickMovementParams.constprop.0",
                 "OverworldWildSpawns_OverlayOnPlayerStep", "OverworldWildSpawns_TrySpawnFollower",
                 "OverworldWildSpawns_TryStartDirectedBehaviorHopCommand",
                 "OverworldWildSpawns_QueryAddon", "OverworldWildRuntime_QuerySurface",
                 "OverworldWildSpawns_IsLandMapTile",
                 "OverworldWildHelper_DespawnFarEncounters",
                 "OverworldWildSpawns_TryStartChainPauseAction",
                 "OverworldWildSpawns_StartNextSpotEmoteStep",
                 *battle_symbols,
                 "OverworldWildRuntime_ResolveBaseYAt", "OverworldWildOccupancy_Query",
                 "OverworldSpawnSpatial_IsPlayerFrontTile", "memset",
                 )
        self.symbols = {name: 0x02300000 + index * 0x40 for index, name in enumerate(names)}
        if missing_spawn_wrapper:
            del self.symbols["OverworldWildSpawns_SpawnOne"]
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
                 "offsets": {"fieldEpoch": 12, "mapGeneration": 46, "actors": 68},
                 "size": 2488, "actorStride": 176, "actorPolicyOffset": 140},
             "structures": {"actorPolicyState": 36}, "capacities": {"actors": 10}},
             linked_symbols=lambda path: self.symbols, linked_symbol=lambda symbols, name: symbols[name],
             unsigned=lambda emu, address, size=4: int.from_bytes(self.read(address, size), "little"),
             actor_state=lambda emu, slot: deepcopy(self.actor),
             wild_spawn=lambda emu, slot: {"object": 0x02210000, "species": self.actor["species"],
                                           "form": self.actor["form"], "active": 1, "personality": 99},
             object_state=lambda emu, pointer: deepcopy(self.player),
             player_ptr=lambda emu: self.player_pointer, field_map_id=lambda emu: self.map_id)
        self.dialogue_overlay_regions = {1: (HEART_BUBBLE, b"B" * (0x02203DC0 - HEART_BUBBLE + 32))}
        self.code_regions = [(0x02000000, bytes(stock)), self.dialogue_overlay_regions[1]] + [
            (address, bytes((index + 1,)) * 32) for index, address in enumerate(self.symbols.values())]
        caller = self.symbols["OverworldWildSpawns_TryPickSpawnDestinationMask"]
        target = self.symbols["OverworldWildSpawns_ClassifyBehaviorHopLandingTile"]
        self.destination_query_return = caller + 12
        displacement = target - (caller + 8 + 4)
        for index, (address, data) in enumerate(self.code_regions):
            if address == caller:
                code = bytearray(data)
                struct.pack_into("<HH", code, 8, 0xF000 | ((displacement >> 12) & 0x7FF),
                                 0xF800 | ((displacement >> 1) & 0x7FF))
                self.code_regions[index] = (address, bytes(code))
        for address, data in self.code_regions:
            if address != 0x02000000:
                self.put(address, data)
        self.put(0x0201FD44, b"R" * 32)
        self.put(0x020078D8, b"Q" * 32)
        self.put(PLAYER_STEP_ADMISSION, b"S" * 32)
        self.put(SPAWN_REFRESH_HEIGHT, b"H" * 32)
        self.put(SPAWN_CREATE_OBJECT, b"C" * 32)
        self.put(MON_APPLY_FRIENDSHIP_MOD, b"F" * 32)
        self.put(PLAY_CRY, b"Y" * 32)
        self.put(MODEL_DATA_GETTER, MODEL_DATA_GETTER_CODE)
        self.put(MODEL_VISIBILITY_SETTER, MODEL_VISIBILITY_SETTER_CODE)
        self.put(MODEL_POSITION_SETTER, MODEL_POSITION_SETTER_CODE)
        self.put(0x0205D4C2, stock[0x5D4C2:0x5D4CA])
        self.put(0x02200008, struct.pack("<I", 100))
        self.put(self.rt.G_FIELD_SYS_PTR, struct.pack("<I", 0x02231000))
        self.put(0x0220000C, struct.pack("<H", 2))
        self.put(0x0220002E, struct.pack("<H", 3))
        self.prepare_spawn()
        self.prepared = False
        self.hooks = Hooks(self.rt, self.emu)
        self.observer = NativeObservation(self, self.hooks, lambda path, address, size: self.read(address, size))
        # Fly timing has separate full-ROM fixtures. It is outside these
        # synthetic callback tests; fail if any test tries to use that reader.
        class UnselectedFlyCost:
            def __init__(self, observer):
                self.frame, self.bubbles = None, []
            def __getattr__(self, name):
                raise AssertionError("unselected Fly cost fixture was reached: " + name)
        with patch("tools.overworld.devtools_fly_landing_cost.FlyLandingCost", UnselectedFlyCost):
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

    def destination_query(self, mask, *, sp, target=(552, 383), result=0):
        self.put(sp, struct.pack("<iiII", *target, 0xFFFFFFFF, 0xFFFFFFFF))
        self.enter("spawn-destination-query", sp=sp, lr=self.destination_query_return | 1,
                   r0=0, r1=0xFFFFFFFF, r2=0x02231000, r3=mask)
        self.returned(result, sp=sp, address=self.destination_query_return)

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

    def model_getter_entry(self, *, callback=None, **changes):
        f = self.f
        values = {"r0": 0, **{"r" + str(i): 0x100 + i for i in range(1, 8)},
                  "pc": MODEL_DATA_GETTER + 4, "cpsr": 0x3F}
        values.update(changes)
        f.hooks.current_callback = callback or {"address": MODEL_DATA_GETTER, "size": 2}
        f.enter("model-data-getter-null", **values)

    def test_null_model_visibility_retains_real_caller_before_abort(self):
        f = self.f
        words = [0x022B0000 + i * 4 for i in range(8)]
        f.put(0x027E3800, struct.pack("<8I", *words))
        f.hooks.current_callback = {"address": MODEL_VISIBILITY_SETTER, "size": 2}
        values = {"r0": 0, **{"r" + str(i): 0x100 + i for i in range(1, 8)},
                  "pc": MODEL_VISIBILITY_SETTER + 4, "cpsr": 0x3F,
                  "lr": 0x021FFAF7}
        # Non-NULL calls produce no record or return hook.
        f.enter("model-visibility-null", **{**values, "r0": 0x02210000})
        self.assertNotIn("nullModelVisibility", f.observer.snapshot())
        self.assertIsNone(f.hooks.error)
        f.enter("model-visibility-null", **values)
        receipt = f.observer.snapshot()["nullModelVisibility"]
        self.assertEqual(receipt["symbol"], "sub_02023EA4")
        self.assertEqual(receipt["codeBytes"], 20)
        self.assertEqual(receipt["callerReturn"], 0x021FFAF7)
        self.assertEqual(receipt["systemSp"], 0x027E3800)
        self.assertEqual(receipt["stack"]["words"], words)
        self.assertEqual(receipt["registers"]["r0"], 0)
        self.assertFalse(receipt["acceptedProof"])
        self.assertIn("received NULL", f.hooks.error)
        self.assertEqual(f.observer.drain(), [])
        self.assertEqual(f.observer.calls["model-visibility-null"]["returned"], 0)
        self.assertNotIn("nullModelDataGetter", f.observer.snapshot())
        f.hooks.error = None
        f.enter("model-visibility-null", **{**values, "lr": 0x02001001})
        self.assertEqual(f.observer.snapshot()["nullModelVisibility"], receipt)

    def test_null_model_position_uses_same_guard_and_retains_one_caller(self):
        f = self.f
        words = [0x022B0000 + i * 4 for i in range(8)]
        f.put(0x027E3800, struct.pack("<8I", *words))
        f.hooks.current_callback = {"address": MODEL_POSITION_SETTER, "size": 2}
        values = {"r0": 0, **{"r" + str(i): 0x100 + i for i in range(1, 8)},
                  "pc": MODEL_POSITION_SETTER + 4, "cpsr": 0x3F,
                  "lr": 0x021FFA01}
        f.enter("model-position-null", **{**values, "r0": 0x02210000})
        self.assertNotIn("nullModelPosition", f.observer.snapshot())
        self.assertIsNone(f.hooks.error)
        f.enter("model-position-null", **values)
        receipt = f.observer.snapshot()["nullModelPosition"]
        self.assertEqual(receipt["symbol"], "sub_02023E50")
        self.assertEqual(receipt["codeBytes"], 24)
        self.assertEqual(receipt["callerReturn"], values["lr"])
        self.assertEqual(receipt["stack"]["words"], words)
        self.assertEqual(receipt["registers"]["r0"], 0)
        self.assertFalse(receipt["acceptedProof"])
        self.assertIn("received NULL", f.hooks.error)
        self.assertEqual(f.observer.drain(), [])
        self.assertEqual(f.observer.calls["model-position-null"]["returned"], 0)
        f.hooks.error = None
        f.enter("model-position-null", **{**values, "lr": 0x02001001})
        self.assertEqual(f.observer.snapshot()["nullModelPosition"], receipt)

    def test_null_model_position_rejects_wrong_entry_or_resident_code(self):
        f = self.f
        f.hooks.current_callback = {"address": MODEL_POSITION_SETTER, "size": 2}
        values = {"r0": 0, "pc": MODEL_POSITION_SETTER + 4, "cpsr": 0x1F}
        f.enter("model-position-null", **values)
        self.assertIn("not an ARM9 Thumb/System entry", f.hooks.error)
        self.assertNotIn("nullModelPosition", f.observer.snapshot())
        f.hooks.error = None
        f.put(MODEL_POSITION_SETTER, b"\x00\x00")
        f.enter("model-position-null", **{**values, "cpsr": 0x3F})
        self.assertIn("resident code identity differs", f.hooks.error)
        self.assertNotIn("nullModelPosition", f.observer.snapshot())

    def test_null_model_visibility_rejects_wrong_entry_or_resident_code(self):
        f = self.f
        f.hooks.current_callback = {"address": MODEL_VISIBILITY_SETTER, "size": 2}
        values = {"r0": 0, "pc": MODEL_VISIBILITY_SETTER + 4, "cpsr": 0x1F}
        f.enter("model-visibility-null", **values)
        self.assertIn("not an ARM9 Thumb/System entry", f.hooks.error)
        self.assertNotIn("nullModelVisibility", f.observer.snapshot())
        f.hooks.error = None
        f.put(MODEL_VISIBILITY_SETTER, b"\x00\x00")
        f.enter("model-visibility-null", **{**values, "cpsr": 0x3F})
        self.assertIn("resident code identity differs", f.hooks.error)
        self.assertNotIn("nullModelVisibility", f.observer.snapshot())

    def test_null_model_getter_retains_one_exact_entry_and_fault_diagnostics(self):
        f = self.f
        words = [0x02210000 + i * 4 for i in range(8)]
        f.put(0x027E3800, struct.pack("<8I", *words))
        last_complete = {"frame": 99, "nativeObservation": {"sequence": 5}}
        self.model_getter_entry()
        receipt = f.observer.snapshot()["nullModelDataGetter"]
        self.assertIn("received NULL", f.hooks.error)
        self.assertFalse(f.observer.snapshot()["coverageComplete"])
        self.assertEqual(receipt["address"], MODEL_DATA_GETTER)
        self.assertEqual(receipt["codeBytes"], 16)
        self.assertEqual(receipt["callerReturn"], 0x02001001)
        self.assertEqual(receipt["systemSp"], 0x027E3800)
        self.assertEqual(receipt["registers"]["r0"], 0)
        self.assertEqual({key: receipt["registers"][key] for key in
                          ("r" + str(i) for i in range(1, 8))},
                         {"r" + str(i): 0x100 + i for i in range(1, 8)})
        self.assertEqual(receipt["stack"]["words"], words)
        self.assertEqual(receipt["stack"]["readBytes"], 32)
        self.assertTrue(receipt["stack"]["known"])
        self.assertEqual(receipt["actorFrame"], 100)
        self.assertEqual(receipt["nativeCycle"], 10)
        self.assertFalse(receipt["acceptedProof"])
        # There is no terminal receipt or game-frame credit for this call.
        self.assertEqual(f.observer.drain(), [])
        self.assertEqual(f.observer.calls["model-data-getter-null"]["returned"], 0)
        self.assertEqual(f.observer.contexts, [])

        session = SimpleNamespace(native_observation=f.observer, latest_frame=last_complete,
            emu=f.emu, _native_irq_vector=lambda: {}, _control_diagnostics=lambda: {},
            _mount_toggle_diagnostics=lambda: {}, _heap_diagnostics=lambda: {},
            _query_owner_diagnostics=lambda: {}, _query_allocation_diagnostics=lambda: {})
        diagnostic = DevtoolsSession.diagnostics(session)
        self.assertEqual(diagnostic["nativeObserverFault"]["nullModelDataGetter"], receipt)
        self.assertEqual(diagnostic["lastCompleteSnapshot"], last_complete)
        self.assertNotIn("nullModelDataGetter", last_complete["nativeObservation"])
        diagnostic["nativeObserverFault"]["nullModelDataGetter"]["registers"]["r0"] = 9
        self.assertEqual(f.observer.snapshot()["nullModelDataGetter"], receipt)
        # Even a forced host re-entry cannot replace the first receipt.
        f.hooks.error = None
        self.model_getter_entry(r1=0x999)
        self.assertEqual(f.observer.snapshot()["nullModelDataGetter"], receipt)
        self.assertEqual(f.observer.calls["model-data-getter-null"]["entered"], 1)

    def test_nonzero_model_getter_argument_creates_no_receipt_or_return_hook(self):
        f = self.f
        callbacks = tuple(f.callbacks)
        self.model_getter_entry(r0=0x02210000)
        self.assertIsNone(f.hooks.error)
        self.assertNotIn("nullModelDataGetter", f.observer.snapshot())
        self.assertEqual(f.observer.calls["model-data-getter-null"]["entered"], 0)
        self.assertEqual(tuple(f.callbacks), callbacks)

    def test_null_model_getter_does_not_read_an_invalid_system_stack(self):
        f = self.f
        reads, original = [], f.read
        def read(address, size):
            reads.append((address, size))
            return original(address, size)
        f.read = read
        self.model_getter_entry(sp=0)
        receipt = f.observer.snapshot()["nullModelDataGetter"]
        self.assertIn("received NULL", f.hooks.error)
        self.assertEqual(receipt["systemSp"], 0)
        self.assertFalse(receipt["stack"]["known"])
        self.assertEqual(receipt["stack"]["readBytes"], 0)
        self.assertIn("outside aligned RAM/stack", receipt["stack"]["reason"])
        self.assertNotIn((0, 32), reads)

    def test_null_model_getter_rejects_changed_resident_body(self):
        f = self.f
        f.put(MODEL_DATA_GETTER + 12, b"\x00\x00")
        self.model_getter_entry()
        self.assertIn("resident code identity differs", f.hooks.error)
        self.assertNotIn("nullModelDataGetter", f.observer.snapshot())
        call = f.observer.calls["model-data-getter-null"]
        self.assertEqual((call["entered"], call["nonmatchingEntries"]), (0, 1))

    def test_null_model_getter_rejects_wrong_stock_or_packaged_body(self):
        f = self.f
        f.observer.close()
        stock = bytearray((f.rt.REPO / "base/arm9.bin").read_bytes())
        stock[MODEL_DATA_GETTER - 0x02000000] ^= 1
        with self.assertRaisesRegex(NativeObservationError, "stock model data getter body differs"):
            f.observer._install_null_model_getter(bytes(stock))
        self.assertNotIn(MODEL_DATA_GETTER, f.callbacks)
        stock[MODEL_DATA_GETTER - 0x02000000] ^= 1
        packaged = bytearray(f.code_regions[0][1])
        packaged[MODEL_DATA_GETTER - 0x02000000] ^= 1
        f.code_regions[0] = (0x02000000, bytes(packaged))
        with self.assertRaisesRegex(NativeObservationError, "differs from the packaged ROM"):
            f.observer._install_null_model_getter(bytes(stock))
        self.assertNotIn(MODEL_DATA_GETTER, f.callbacks)

    def test_null_model_getter_rejects_wrong_cpu_entry(self):
        for changes in ({"cpsr": 0x1F}, {"cpsr": 0x33}, {"pc": MODEL_DATA_GETTER + 8},
                        {"callback": {"address": MODEL_DATA_GETTER, "size": 4}}):
            with self.subTest(changes=changes):
                self.f.hooks.error = None
                self.model_getter_entry(**changes)
                self.assertIn("not an ARM9 Thumb/System entry", self.f.hooks.error)
                self.assertNotIn("nullModelDataGetter", self.f.observer.snapshot())

    def test_current_rom_install_uses_real_classifier_and_rejects_missing_or_wrong_code(self):
        from tools.overworld.devtools_engine import linked_symbols, linked_symbol
        from tools.overworld.devtools_runtime import _elf_code
        repo = Path(__file__).resolve().parents[2]
        f = self.f
        f.observer.close()
        package = SimpleNamespace(rom=repo / "test.nds")
        DevtoolsSession._load_package(package)
        f.rt.REPO = repo
        f.rt.linked_symbols, f.rt.linked_symbol = linked_symbols, linked_symbol
        f.rt.WILD_SYMBOLS = linked_symbols(repo / "build/overworld_wild_spawns_overlay_linked.o")
        f.code_regions = package.code_regions
        f.dialogue_overlay_regions = package.dialogue_overlay_regions
        name = "OverworldWildSpawns_ClassifyBehaviorHopLandingTile"
        address = linked_symbol(f.rt.WILD_SYMBOLS, name) & ~1
        expected = _elf_code(repo / "build/overworld_wild_spawns_overlay_linked.o", address, 32)
        f.observer = NativeObservation(f, f.hooks, _elf_code)
        f.observer.install()
        self.assertTrue(f.observer.installed)
        self.assertEqual(f.observer.calls["spawn-destination-query"]["address"], address)
        self.assertNotIn("chain-landing-terrain", f.observer.calls)
        self.assertNotIn("OverworldWildSpawns_DoesAllowedTileMatch", f.rt.WILD_SYMBOLS)
        f.observer.close()

        corrupted = []
        for base, code in package.code_regions:
            if base <= address and address + 32 <= base + len(code) \
                    and code[address - base:address - base + 32] == expected:
                changed = bytearray(code)
                changed[address - base] ^= 1
                code = bytes(changed)
            corrupted.append((base, code))
        f.code_regions = corrupted
        f.observer = NativeObservation(f, f.hooks, _elf_code)
        with self.assertRaisesRegex(NativeObservationError, "linked entry differs from the packaged ROM"):
            f.observer.install()
        f.observer.close()
        f.code_regions = package.code_regions
        f.rt.WILD_SYMBOLS = dict(f.rt.WILD_SYMBOLS)
        del f.rt.WILD_SYMBOLS[name]
        f.observer = NativeObservation(f, f.hooks, _elf_code)
        with self.assertRaises(KeyError):
            f.observer.install()
        f.observer.close()

    def test_destination_classifier_rejects_wrong_owner_stack_caller_and_decision(self):
        f = self.f
        world = f.observer._world_context()
        owner = dict(destinationMask=0xC0, worldContext=world, candidateQueryCount=0)
        f.observer.destination_contexts.append(owner)
        f.regs.sp, f.regs.lr = 0x027E3740, f.destination_query_return | 1
        f.regs.r0, f.regs.r1, f.regs.r2, f.regs.r3 = 0, 0xFFFFFFFF, world["fieldPointer"], 0xC0
        f.put(f.regs.sp, struct.pack("<iiII", 552, 383, 0xFFFFFFFF, 0xFFFFFFFF))
        self.assertIs(f.observer._destination_query_before(), owner)
        for register, wrong in (("r0", f.rt.WILD_STATE), ("r1", 0),
                ("r2", world["fieldPointer"] + 4), ("r3", 0)):
            original = getattr(f.regs, register)
            setattr(f.regs, register, wrong)
            with self.assertRaisesRegex(NativeObservationError, "scanner owner"):
                f.observer._destination_query_before()
            setattr(f.regs, register, original)
        f.put(f.regs.sp + 8, struct.pack("<I", 0))
        with self.assertRaisesRegex(NativeObservationError, "scanner owner"):
            f.observer._destination_query_before()
        f.put(f.regs.sp + 8, struct.pack("<I", 0xFFFFFFFF))
        f.regs.lr = 0x02001101
        with self.assertRaisesRegex(NativeObservationError, "wrong native caller"):
            f.observer._destination_query_before()
        for decision in (0, 1, 12):
            self.assertIsNone(f.observer._destination_query_after(owner, {"returnValue": decision}))
        with self.assertRaisesRegex(NativeObservationError, "lost its scanner owner"):
            f.observer._destination_query_after(owner, {"returnValue": 13})

    def guarded_code_fixture(self, address=0x01FFF980, *, resident=True):
        f=self.f
        raw_read=lambda address,size: bytes(f.memory.get(address+i,0) for i in range(size))
        reads=[]
        def native_read(_emu, pointer, size):
            reads.append((pointer,size))
            return raw_read(pointer,size)
        f.rt.actor_memory_read=native_read
        f.read=DevtoolsSession.read.__get__(f)
        expected=bytes(range(32))
        f.code_regions.append((address,expected))
        f.put(address,expected)
        f.observer._tap('packaged-code-control',address,expected,
            lambda: dict(address=address),lambda data,context: dict(data),resident=resident)
        return f,expected,reads,raw_read

    def test_packaged_main_ram_and_itcm_taps_authenticate_entry_and_return(self):
        for address in (0x02301000,0x01FFF980):
            with self.subTest(address=address):
                f,_,reads,_=self.guarded_code_fixture(address)
                f.enter('packaged-code-control')
                f.returned(123)
                self.assertIsNone(f.hooks.error)
                call=f.observer.calls['packaged-code-control']
                self.assertEqual((call['entered'],call['returned']),(1,1))
                self.assertEqual(reads.count((address,32)),2)
                self.assertEqual(f.observer.pending[-1]['address'],address)
        with self.assertRaisesRegex(DevtoolsFailure,'outside main RAM/public stack'):
            f.read(0x01FFF980,32)
        with self.assertRaisesRegex(NativeObservationError,'outside aligned RAM/stack'):
            public_bytes(f,0x01FFF980,32)

    def test_itcm_tap_rejects_corrupt_resident_entry_and_return(self):
        f,expected,_,_=self.guarded_code_fixture()
        f.put(0x01FFF980,b'?'*32)
        f.enter('packaged-code-control')
        self.assertIn('resident code identity differs',f.hooks.error)
        call=f.observer.calls['packaged-code-control']
        self.assertEqual((call['entered'],call['nonmatchingEntries']),(0,1))
        f.hooks.error=None
        f.put(0x01FFF980,expected)
        f.enter('packaged-code-control')
        f.put(0x01FFF980,b'?'*32)
        f.returned(123)
        self.assertIn('lost code identity before return',f.hooks.error)
        self.assertEqual(call['returned'],0)
        self.assertFalse(f.observer.pending)

    def test_nonresident_itcm_tap_keeps_nonmatching_overlay_semantics(self):
        f,_,_,_=self.guarded_code_fixture(resident=False)
        f.put(0x01FFF980,b'?'*32)
        f.enter('packaged-code-control')
        self.assertIsNone(f.hooks.error)
        call=f.observer.calls['packaged-code-control']
        self.assertEqual((call['entered'],call['nonmatchingEntries']),(0,1))
        self.assertFalse(f.observer.contexts)

    def test_packaged_code_rejects_wrong_bytes_or_unmatched_spans_before_native_read(self):
        f,expected,reads,_=self.guarded_code_fixture()
        for address,data in ((0x01FFF980,b'?'*32),(0x01FFF990,expected),
                             (0x01FFF9C0,expected),(0x01FFF980,b'')):
            with self.subTest(address=address,size=len(data)):
                with self.assertRaisesRegex(NativeObservationError,'packaged ROM'):
                    f.observer._live_code(address,data)
                self.assertFalse(reads)
        with self.assertRaisesRegex(NativeObservationError,'linked entry differs'):
            f.observer._tap('wrong-package',0x01FFF980,b'?'*32,lambda: {},lambda d,c: d)
        self.assertFalse(reads)

    def test_itcm_chain_callsite_uses_the_same_authenticated_code_read(self):
        f,_,reads,raw_read=self.guarded_code_fixture()
        name='OverworldWildSpawns_ResolveObjectLandingHeight'
        f.symbols[name]=0x01FFF980
        expected=bytearray(range(32))
        instruction=struct.pack('<H',0x4798)
        expected[4:6]=instruction
        f.code_regions[-1]=(0x01FFF980,bytes(expected))
        f.put(0x01FFF980,expected)
        f.observer.elf_code=lambda _path,address,size: raw_read(address,size)
        f.regs.lr=0x01FFF987;f.regs.r3=SPAWN_REFRESH_HEIGHT|1
        cache={}
        f.observer._chain_caller(name,cache=cache,target=SPAWN_REFRESH_HEIGHT)
        self.assertEqual(cache,{0x01FFF984:instruction})
        self.assertEqual(reads,[(0x01FFF984,2)])
        f.put(0x01FFF984,b'??')
        with self.assertRaisesRegex(NativeObservationError,'caller live code differs'):
            f.observer._chain_caller(name,cache=cache,target=SPAWN_REFRESH_HEIGHT)

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
        self.assertEqual(f.observer.calls["wild-battle-request"]["address"],
                         f.symbols["OverworldWildSpawns_TryStartBattleForSlot"])
        f.enter("wild-battle-request", r0=f.rt.WILD_STATE,
                r1=0x02231000, r2=0)
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
        f.enter("wild-battle-request", r0=f.rt.WILD_STATE,
                r1=0x02231000, r2=0)
        f.returned(1)
        self.assertIn("NativeObservationError: battle pending identity differs",
                      f.hooks.error)

    def test_wild_battle_request_rejects_old_abi_at_current_symbol(self):
        f = self.f
        f.enter("wild-battle-request", r0=0x02231000,
                r1=f.rt.WILD_STATE, r2=0)
        self.assertIn("NativeObservationError: battle request arguments differ",
                      f.hooks.error)

    def test_wild_battle_request_legacy_symbol_keeps_field_first_abi(self):
        f = Fixture(Path(self.directory.name) / "legacy",
                    battle_symbols=("OverworldWildSpawns_RequestBattleScript",))
        self.assertEqual(f.observer.calls["wild-battle-request"]["address"],
                         f.symbols["OverworldWildSpawns_RequestBattleScript"])
        f.enter("wild-battle-request", r0=0x02231000,
                r1=f.rt.WILD_STATE, r2=0)
        f.returned(0)
        self.assertIsNone(f.hooks.error)
        self.assertEqual(f.observer.drain(), [])

    def test_wild_battle_request_prefers_original_symbol_when_both_exist(self):
        f = Fixture(Path(self.directory.name) / "both", battle_symbols=(
            "OverworldWildSpawns_RequestBattleScript",
            "OverworldWildSpawns_TryStartBattleForSlot"))
        self.assertEqual(f.observer.calls["wild-battle-request"]["address"],
                         f.symbols["OverworldWildSpawns_RequestBattleScript"])
        f.enter("wild-battle-request", r0=0x02231000,
                r1=f.rt.WILD_STATE, r2=0)
        f.returned(0)
        self.assertIsNone(f.hooks.error)

    def test_wild_battle_request_requires_a_supported_symbol(self):
        with self.assertRaisesRegex(NativeObservationError,
                                    "wild battle request symbol unavailable"):
            Fixture(Path(self.directory.name) / "missing", battle_symbols=())

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

    def test_sequential_archive_cost_is_baseline_only_and_keeps_exact_entry_return(self):
        f = self.f
        label, address = "archive-sequential-read-cost", 0x020078D8
        self.assertEqual(f.observer.calls[label]["address"], address)
        self.assertIn(label, f.observer.TIMED_CALLS)
        before = dict(f.memory)
        clocks = (f.rt.EXECUTED_FRAME_COUNT, f.guest_clock["frameSequence"])
        for mode in (None, "omit-spawn-details"):
            f.spawn_cost_probe = SimpleNamespace(mode=mode, gate=lambda observer, label: True)
            f.enter(label)
            self.assertEqual(f.observer.calls[label]["entered"], 0)
            self.assertFalse(f.observer.return_tokens)
        f.spawn_cost_probe = SimpleNamespace(mode="baseline", gate=lambda observer, label: True)
        f.enter(label, r0=0x02332074, r1=0xE000, r2=0x02264000, r3=0,
                lr=0x021F6679)
        f.guest_clock["arm9Timestamp"] += 1750000
        f.returned(0x12345678, address=0x021F6678)
        row = f.observer.pending[-1]
        self.assertEqual(row["arguments"], [0x02332074, 0xE000, 0x02264000, 0])
        self.assertEqual(row["caller"], 0x021F6678)
        self.assertEqual(row["guestTiming"]["arm9Ticks"], 1750000)
        self.assertFalse(row["acceptedProof"])
        self.assertFalse(f.observer.spawn_contexts)
        self.assertEqual(f.memory, before)
        self.assertEqual((f.rt.EXECUTED_FRAME_COUNT, f.guest_clock["frameSequence"]), clocks)
        self.assertIsNone(f.hooks.error)
        # NARC_ReadFile is void: its sampled r0 is not a byte-count claim.
        with self.assertRaisesRegex(NativeObservationError, "no complete packaged entry"):
            f.observer._tap(label, address, b"Q" * 31, f.observer._archive_cost_before,
                            f.observer._archive_cost_after, resident=True)
        f.enter(label, lr=0x021F6679)
        f.put(address, b"X" * 32)
        f.returned(0, address=0x021F6678)
        self.assertIn("lost code identity before return", f.hooks.error)
        self.assertEqual(f.observer.calls[label]["returned"], 1)
        f.observer.close()
        # A missing or wrong packaged anchor cannot install the new tap.
        for replacement in (b"", b"X" * 32):
            with tempfile.TemporaryDirectory(prefix="archive-anchor-") as directory:
                g = Fixture(directory)
                g.observer.close()
                regions = []
                for origin, code in g.code_regions:
                    if origin == 0x02000000:
                        end = address - origin
                        code = code[:end] if not replacement else code[:end] + replacement + code[end + 32:]
                    regions.append((origin, code))
                g.code_regions = regions
                g.observer = NativeObservation(g, g.hooks, lambda path, entry, size: g.read(entry, size))
                with self.assertRaisesRegex(NativeObservationError,
                        "archive-sequential-read-cost linked entry differs from the packaged ROM"):
                    g.observer.install()
                g.observer.close()

    def test_follower_hop_cost_is_baseline_only_and_authenticates_the_whole_call(self):
        f = self.f
        label = "follower-hop-start-cost"
        address = f.symbols["OverworldWildSpawns_TryStartDirectedBehaviorHopCommand"]
        self.assertEqual(f.observer.calls[label]["address"], address)
        before = dict(f.memory)
        clocks = (f.rt.EXECUTED_FRAME_COUNT, f.guest_clock["frameSequence"])
        for mode in (None, "omit-spawn-details"):
            f.spawn_cost_probe = SimpleNamespace(mode=mode, gate=lambda observer, label: True)
            f.enter(label)
            self.assertEqual(f.observer.calls[label]["entered"], 0)
            self.assertFalse(f.observer.return_tokens)
        f.spawn_cost_probe = SimpleNamespace(mode="baseline", gate=lambda observer, label: True)
        f.enter(label, r0=f.rt.WILD_STATE, r1=0x02231000, r2=7, r3=0x02224000)
        f.guest_clock["arm9Timestamp"] += 876543
        f.returned(1)
        row = f.observer.pending[-1]
        self.assertEqual(row["arguments"], [f.rt.WILD_STATE, 0x02231000, 7, 0x02224000])
        self.assertEqual(row["returnValue"], 1)
        self.assertEqual(row["guestTiming"]["arm9Ticks"], 876543)
        self.assertEqual(row["worldContext"], f.observer._world_context())
        self.assertFalse(row["acceptedProof"])
        self.assertEqual(f.memory, before)
        self.assertEqual((f.rt.EXECUTED_FRAME_COUNT, f.guest_clock["frameSequence"]), clocks)
        self.assertIsNone(f.hooks.error)

        f.enter(label, r0=f.rt.WILD_STATE, r1=0x02231000, r2=7, r3=0x02224000)
        f.put(address, b"X" * 32)
        f.returned(1)
        self.assertIn("lost code identity before return", f.hooks.error)
        self.assertEqual(f.observer.calls[label]["returned"], 1)

    def test_spawn_candidate_cost_split_is_scoped_nested_and_package_bound(self):
        from tools.overworld.devtools_engine import linked_symbols, linked_symbol
        from tools.overworld.devtools_runtime import _elf_code
        f = self.f
        # Destination scans run inside a finalizer. Discovery of the shared
        # Query lease has already occurred; it is tested by its own fixture.
        f.observer.finalization_contexts.append({})
        names = (
            ("spawn-candidate-cost", "overworld_wild_spawns_overlay_linked.o",
             "OverworldWildSpawns_ClassifyBehaviorHopLandingTile"),
            ("spawn-query-admission-cost", "overworld_wild_spawns_overlay_linked.o",
             "OverworldWildSpawns_QueryAddon"),
            ("spawn-surface-query-cost", "overworld_wild_runtime_overlay_linked.o",
             "OverworldWildRuntime_QuerySurface"),
            ("spawn-native-land-cost", "overworld_wild_spawns_overlay_linked.o",
             "OverworldWildSpawns_IsLandMapTile"),
            ("spawn-native-height-cost", "overworld_wild_runtime_overlay_linked.o",
             "OverworldWildRuntime_ResolveBaseYAt"),
            ("spawn-native-occupancy-cost", "pokemon_move_history_overlay_linked.o",
             "OverworldWildOccupancy_Query"),
            ("spawn-player-front-cost", "overworld_wild_helper_overlay_linked.o",
             "OverworldSpawnSpatial_IsPlayerFrontTile"),
            ("spawn-stack-clear-cost", "linked.o", "memset"),
        )
        repo = Path(__file__).resolve().parents[2]
        package = SimpleNamespace(rom=repo / "test.nds")
        DevtoolsSession._load_package(package)
        for label, filename, name in names:
            image = repo / "build" / filename
            address = linked_symbol(linked_symbols(image), name) & ~1
            expected = _elf_code(image, address, 32)
            self.assertEqual(len(expected), 32)
            self.assertTrue(any(base <= address and address + 32 <= base + len(code)
                and code[address - base:address - base + 32] == expected
                for base, code in package.code_regions), label)
            self.assertEqual(f.observer.calls[label]["address"], f.symbols[name])
            self.assertIn(label, f.observer.TIMED_CALLS)

        owner = dict(destinationMask=448, worldContext=f.observer._world_context(),
                     candidateQueryCount=0)
        for mode in (None, "omit-spawn-details"):
            f.spawn_cost_probe = SimpleNamespace(mode=mode, gate=lambda observer, label: True)
            f.observer.destination_contexts.append(owner)
            for label, _, _ in names:
                if label == "spawn-candidate-cost":
                    # Its address also owns the unchanged real scanner tap.
                    f.destination_query(448, sp=0x027E3800, target=(559, 400), result=4)
                else:
                    f.enter(label)
                self.assertEqual(f.observer.calls[label]["entered"], 0)
            f.observer.destination_contexts.clear()
            owner["candidateQueryCount"] = 0
        f.spawn_cost_probe = SimpleNamespace(mode="baseline", gate=lambda observer, label: True)
        for label, _, _ in names:
            f.enter(label)
            self.assertEqual(f.observer.calls[label]["entered"], 0)
        self.assertFalse(f.observer.return_tokens)

        f.observer.destination_contexts.append(owner)
        f.put(0x027E3800, struct.pack("<iiII", 559, 400, 0xFFFFFFFF, 0xFFFFFFFF))
        before = dict(f.memory)
        clocks = (f.rt.EXECUTED_FRAME_COUNT, f.guest_clock["frameSequence"])
        f.enter("spawn-candidate-cost", lr=f.destination_query_return | 1,
                r0=0, r1=0xFFFFFFFF, r2=0x02231000, r3=448)
        f.guest_clock["arm9Timestamp"] += 10
        f.enter("spawn-query-admission-cost", sp=0x027E3780, lr=0x02001041,
                r0=0x02231000, r1=0)
        f.guest_clock["arm9Timestamp"] += 20
        f.returned(0x02240001, sp=0x027E3780, address=0x02001040)
        f.guest_clock["arm9Timestamp"] += 10
        f.enter("spawn-surface-query-cost", sp=0x027E3780, lr=0x02001041,
                r0=0x02231000, r1=0x02250000, r2=559, r3=400)
        f.guest_clock["arm9Timestamp"] += 30
        f.returned(0, sp=0x027E3780, address=0x02001040)
        f.guest_clock["arm9Timestamp"] += 10
        # This synthetic callback checks the timing tap, not native LAND use.
        # The real surface-only scan is expected to have no LAND entries.
        f.enter("spawn-native-land-cost", sp=0x027E3780, lr=0x02001041,
                r0=0x02231000, r1=559, r2=400)
        f.guest_clock["arm9Timestamp"] += 5
        f.returned(0, sp=0x027E3780, address=0x02001040)
        f.guest_clock["arm9Timestamp"] += 5
        f.enter("spawn-native-height-cost", sp=0x027E3780, lr=0x02001041,
                r0=0x02231000, r1=0x02250000, r2=559, r3=400)
        f.guest_clock["arm9Timestamp"] += 5
        f.returned(1, sp=0x027E3780, address=0x02001040)
        f.enter("spawn-native-occupancy-cost", sp=0x027E3780, lr=0x02001041,
                r0=0x02231000, r1=559, r2=400, r3=0)
        f.guest_clock["arm9Timestamp"] += 5
        f.returned(0, sp=0x027E3780, address=0x02001040)
        f.enter("spawn-player-front-cost", sp=0x027E3780, lr=0x02001041,
                r0=0x02231000, r1=559, r2=400)
        f.guest_clock["arm9Timestamp"] += 5
        f.returned(0, sp=0x027E3780, address=0x02001040)
        f.enter("spawn-stack-clear-cost", sp=0x027E3780, lr=0x02001041,
                r0=0x027E3700, r1=0, r2=84)
        f.guest_clock["arm9Timestamp"] += 5
        f.returned(0x027E3700, sp=0x027E3780, address=0x02001040)
        f.returned(4, address=f.destination_query_return)
        rows = {row["observation"]: row for row in f.observer.pending}
        self.assertEqual({label: rows[label]["guestTiming"]["arm9Ticks"]
                          for label, _, _ in names}, {
            "spawn-candidate-cost": 110, "spawn-query-admission-cost": 20,
            "spawn-surface-query-cost": 30, "spawn-native-land-cost": 5,
            "spawn-native-height-cost": 5, "spawn-native-occupancy-cost": 5,
            "spawn-player-front-cost": 5, "spawn-stack-clear-cost": 5})
        self.assertEqual(rows["spawn-candidate-cost"]["arguments"],
                         [0, 0xFFFFFFFF, 0x02231000, 448])
        self.assertEqual(rows["spawn-surface-query-cost"]["arguments"],
                         [0x02231000, 0x02250000, 559, 400])
        self.assertTrue(all(rows[label]["worldContext"] == owner["worldContext"]
                            and not rows[label]["acceptedProof"] for label, _, _ in names))
        self.assertEqual(owner["candidateQueryCount"], 1)
        self.assertEqual(f.memory, before)
        self.assertEqual((f.rt.EXECUTED_FRAME_COUNT, f.guest_clock["frameSequence"]), clocks)
        self.assertFalse(f.observer.contexts)
        self.assertFalse(f.observer.return_tokens)
        self.assertIsNone(f.hooks.error)

        for label in ("spawn-surface-query-cost", "spawn-native-height-cost", "spawn-native-occupancy-cost",
                      "spawn-player-front-cost", "spawn-stack-clear-cost"):
            f.hooks.error = None
            f.enter(label, sp=0x027E3780, lr=0x02001041)
            f.put(f.observer.calls[label]["address"], b"X" * 32)
            f.returned(0, sp=0x027E3780, address=0x02001040)
            self.assertIn("lost code identity before return", f.hooks.error)
            self.assertEqual(f.observer.calls[label]["returned"], 1)

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
        f.destination_query(0xC0, sp=0x027E3740)
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
        request, result = bytearray(44), bytearray(216)
        request[:2] = struct.pack("<H", 165)
        request[38] = 2
        result[:160] = bytes(range(80)) * 2
        struct.pack_into("<II", result, 188, 7, 44)
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
        self.assertEqual(profiles[0]["lanes"], [bytes(range(80)).hex()] * 2)
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
        request, result = bytearray(44), bytearray(216)
        struct.pack_into("<H", request, 0, 165)
        struct.pack_into("<I", request, 16, conditional_mask)
        request[38] = 2
        result[:160] = bytes(range(80)) * 2
        struct.pack_into("<II", result, 188, 7, 44)
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
        f.put(0x02220000, call); f.put(0x02221000, bytes(range(80)))
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
        self.assertEqual(data["laneHex"], bytes(range(80)).hex())
        self.assertEqual(f.observer.calls["walk-rng"]["entered"], 1)
        # RESET has no lane; preserve that actual call, without inventing a
        # chain-reset reason or reading a null profile buffer.
        call = bytearray(28); struct.pack_into("<HH", call, 0, 1, 28)
        f.put(0x02220000, call); f.enter("walk-policy", r0=0x02220000); f.returned(1)
        f.observer.completed_frame(12)
        self.assertEqual(f.observer.drain()[0]["data"]["operation"], 0)
        self.assertIsNone(f.hooks.error)

    def test_playful_sequence_draws_and_visible_jump_effects_are_scoped(self):
        f = self.f
        f.actor.update(species=35, form=0)
        f.enter("walk-rng")
        f.enter("playful-heart", r0=0x02210000, r1=0)
        self.assertEqual(f.observer.calls["playful-heart"]["entered"], 0)
        f.enter("playful-sequence", r0=f.rt.WILD_STATE, r1=0, r3=1, lr=0x02001101)
        for draw in (74, 19):
            f.enter("walk-rng", sp=0x027E3780, lr=0x02001201)
            f.returned(draw, sp=0x027E3780, address=0x02001200)
        f.returned(1, address=0x02001100)
        f.enter("playful-step", r0=f.rt.WILD_STATE, r1=0, r2=0x02210000,
                lr=0x02001301)
        f.player["movement_cmd"] = 0x30
        f.enter("playful-heart", r0=0x02210000, r1=0, lr=0x02001401)
        f.returned(1, address=0x02001400)
        f.enter("playful-cry", r0=35, r1=0, lr=0x02001501)
        f.returned(0, address=0x02001500)
        f.returned(1, address=0x02001300)
        f.observer.completed_frame(11)
        values = {row["data"]["observation"]: row["data"] for row in f.observer.drain()}
        self.assertEqual([d["value"] for d in values["playful-sequence"]["rngReturns"]], [74, 19])
        self.assertEqual(values["playful-step"]["command"], 0x30)
        self.assertEqual(values["playful-heart"]["returnValue"], 1)
        self.assertEqual(values["playful-heart"]["stepId"], values["playful-step"]["stepId"])
        self.assertEqual(values["playful-cry"]["stepId"], values["playful-step"]["stepId"])
        self.assertEqual(f.observer.calls["walk-rng"]["entered"], 2)
        self.assertIsNone(f.hooks.error)

    def test_playful_stock_draw_tracks_admitted_pointer_and_current_visible_owner(self):
        f = self.f
        f.actor.update(species=35, form=0)
        f.enter("playful-step", r0=f.rt.WILD_STATE, r1=0, r2=0x02210000,
                lr=0x02001301)
        f.player["movement_cmd"] = 0x30
        f.enter("playful-heart", r0=0x02210000, r1=0, lr=0x02001401)
        f.returned(0x02337860, address=0x02001400)
        f.returned(1, address=0x02001300)
        raw = bytearray(64)
        struct.pack_into("<II", raw, 0x38, 0x02210000, 0x02340000)
        f.put(0x02220000, raw)
        for hidden in (0, 1):
            struct.pack_into("<I", raw, 0x10, hidden)
            f.put(0x02220000, raw)
            f.enter("playful-heart-draw", r0=0x02337860, r1=0x02220000, lr=0x02001601)
            f.returned(0, address=0x02001600)
        # A reused pointer with another map object cannot earn same-owner credit.
        struct.pack_into("<I", raw, 0x38, 0x02210004)
        f.put(0x02220000, raw)
        f.enter("playful-heart-draw", r0=0x02337860, r1=0x02220000, lr=0x02001601)
        f.observer.completed_frame(11)
        draws = [row["data"] for row in f.observer.drain()
                 if row["data"].get("observation") == "playful-heart-draw"]
        self.assertEqual([row["visible"] for row in draws], [True, False])
        self.assertTrue(all(row["effectPointer"] == 0x02337860 for row in draws))
        self.assertEqual(f.observer.calls["playful-heart-draw"]["entered"], 2)
        self.assertIsNone(f.hooks.error)

    def test_playful_prep_keeps_real_call_even_when_jump_starts_in_same_frame(self):
        f = self.f
        f.actor.update(species=35, form=0)
        f.player.update(pos_y=65536, face_y=0, unk88_y=0)
        f.enter("playful-step", r0=f.rt.WILD_STATE, r1=0, r2=0x02210000,
                lr=0x02001301)
        f.player["movement_cmd"] = 0x49
        f.returned(1, address=0x02001300)
        f.enter("playful-step", r0=f.rt.WILD_STATE, r1=0, r2=0x02210000,
                lr=0x02001301)
        f.player["movement_cmd"] = 0x30
        f.returned(1, address=0x02001300)
        f.observer.completed_frame(11)
        steps = [row["data"] for row in f.observer.drain()
                 if row["data"].get("observation") == "playful-step"]
        self.assertEqual([row["command"] for row in steps], [0x49, 0x30])
        self.assertEqual(steps[0]["objectPose"], {key: f.player[key] for key in
                         ("pos_x", "pos_y", "pos_z", "face_y", "unk88_y")})
        self.assertIsNone(f.hooks.error)

    def test_playful_rejected_prep_cannot_earn_native_acceptance(self):
        f = self.f
        f.actor.update(species=35, form=0)
        f.player["movement_cmd"] = 0x49
        f.enter("playful-step", r0=f.rt.WILD_STATE, r1=0, r2=0x02210000,
                lr=0x02001301)
        f.returned(0, address=0x02001300)
        f.observer.completed_frame(11)
        self.assertFalse([row for row in f.observer.drain()
                          if row["data"].get("observation") == "playful-step"])

    def test_safety_bubble_uses_same_stock_call_and_exact_current_object(self):
        f = self.f
        subject = {"handle": {"value": 0x10007, "slot": 7}}
        source = {"object": 0x02210000}
        engine = {"pointer": 0x02210000}
        f.observer._safety_bubble_current = lambda obj: ((subject, source, engine)
                                                       if obj == source["object"] else None)
        f.enter("safety-bubble", r0=0x02210004, r1=3)
        self.assertEqual(f.observer.calls["safety-bubble"]["entered"], 0)
        f.enter("safety-bubble", r0=0x02210000, r1=3, lr=0x02001601)
        f.returned(1, address=0x02001600)
        f.observer.completed_frame(11)
        data = [row["data"] for row in f.observer.drain()
                if row["data"]["observation"] == "safety-bubble"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["publicSubject"], subject)
        self.assertEqual(data[0]["publicSubjectAfter"], subject)
        self.assertEqual(data[0]["bubbleId"], 3)
        self.assertEqual(data[0]["returnValue"], 1)
        self.assertEqual(data[0]["objectPointer"], 0x02210000)
        self.assertIsNone(f.hooks.error)

    def fear_bubble_fixture(self, *, species=174, slot=0, role="WILD"):
        f = self.f
        f.actor.update(species=species, role=role, presentationAttached=True)
        f.actor["handle"].update(slot=slot, value=0x10000 + slot)
        source = dict(object=0x02210000, species=species, form=0, active=1,
                      personality=99, encounter_generation=4, object_id=0xE0 + slot,
                      map_id=34)
        engine = dict(pointer=source["object"], in_manager=True, active=True,
                      object_manager=0x02220000, current_manager=0x02220000,
                      object_id=source["object_id"], object_map_id=34, script_id=2074,
                      id_lookup=dict(status="complete", eligible_count=1, pointer_matches=True))
        f.rt.actor_state = lambda emu, n: deepcopy(f.actor) if n == slot else {"active": False}
        f.rt.wild_spawn = lambda emu, n: deepcopy(source)
        f.rt.live_wild_object_identity = lambda emu, n: deepcopy(engine)
        return source, engine

    def test_wild_igglybuff_bubble_records_question_and_cry_without_guest_writes(self):
        f = self.f
        self.fear_bubble_fixture()
        before = deepcopy(f.memory)
        for bubble in (7, 3):
            f.enter("safety-bubble", r0=0x02210000, r1=bubble, lr=0x02001601)
            f.returned(0x02337860, address=0x02001600)
        f.observer.completed_frame(11)
        rows = [r["data"] for r in f.observer.drain()
                if r["data"].get("observation") == "safety-bubble"]
        self.assertEqual([r["bubbleId"] for r in rows], [7, 3])
        self.assertTrue(all(r["publicSubject"]["species"] == 174
                            and r["publicSubject"]["role"] == "WILD"
                            and r["publicSubjectAfter"] == r["publicSubject"]
                            and r["worldContext"]["fieldEpoch"] == 2 for r in rows))
        self.assertEqual(before, f.memory)
        self.assertIsNone(f.hooks.error)

    def test_cry_observer_preserves_cleffa_follower_and_excludes_other_subjects(self):
        for species, slot, role, expected in (
                (173, 7, "FOLLOWER", True), (174, 2, "WILD", True),
                (174, 7, "FOLLOWER", False), (173, 0, "WILD", False),
                (174, 7, "MOUNTED", False)):
            with self.subTest(species=species, slot=slot, role=role):
                self.fear_bubble_fixture(species=species, slot=slot, role=role)
                self.assertEqual(self.f.observer._safety_bubble_current(0x02210000) is not None, expected)
        self.assertIsNone(self.f.observer._safety_bubble_current(0x02210004))

    def test_cry_observer_rejects_stale_field_identity_and_nonunique_object(self):
        source, engine = self.fear_bubble_fixture()
        faults = ((source, "encounter_generation", 5), (source, "form", 1),
                  (engine, "object_map_id", 33),
                  (engine["id_lookup"], "eligible_count", 2))
        for owner, key, bad in faults:
            with self.subTest(key=key):
                original = owner[key]
                owner[key] = bad
                with self.assertRaises(NativeObservationError):
                    self.f.observer._safety_bubble_current(0x02210000)
                owner[key] = original

    def test_cry_observer_return_requires_same_subject_and_field(self):
        f = self.f
        self.fear_bubble_fixture()
        f.regs.r0, f.regs.r1 = 0x02210000, 3
        before = f.observer._safety_bubble_before()
        f.actor["presentationGeneration"] += 1
        with self.assertRaises(NativeObservationError):
            f.observer._safety_bubble_after(before, {})
        f.actor["presentationGeneration"] -= 1
        f.put(f.rt.G_FIELD_SYS_PTR, struct.pack("<I", 0x02232000))
        with self.assertRaises(NativeObservationError):
            f.observer._safety_bubble_after(before, {})

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
    def prepare_commit(f, operation=3):
        state = f.rt.ACTOR_DESCRIPTOR["state"]
        state.update(size=2488, actorStride=176, actorPolicyOffset=140)
        state["offsets"]["actors"] = 68
        f.rt.ACTOR_DESCRIPTOR["structures"] = {"actorPolicyState": 36}
        call = WalkChainPolicyObserverTests.packet(operation)
        struct.pack_into("<I", call, 4, 0x02221000)
        f.put(0x02220000, call)
        f.put(0x02221000, bytes(range(80)))
        f.put(0x02200000 + 208, bytes(range(36)))
        return call

    def test_commit_records_exact_lane_and_policy_for_both_roles_without_rng(self):
        for role in ("WILD", "MOUNTED"):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as directory:
                f = Fixture(directory)
                f.actor["role"] = role
                self.prepare_commit(f)
                f.enter("walk-policy", r0=0x02220000)
                self.assertEqual(f.observer.policy_contexts, [])
                f.put(0x02200000 + 208, bytes(reversed(range(36))))
                f.returned(1); f.observer.completed_frame(12)
                self.assertIsNone(f.hooks.error)
                data = f.observer.drain()[0]["data"]
                self.assertEqual(data["laneHex"], bytes(range(80)).hex())
                self.assertEqual(data["policyBeforeHex"], bytes(range(36)).hex())
                self.assertEqual(data["policyAfterHex"], bytes(reversed(range(36))).hex())
                self.assertEqual(data["policyBefore"]["counter"], 1)
                self.assertEqual(data["policyAfter"]["pending"], 13)
                self.assertEqual(data["policyBefore"]["linearElapsed"], 32)
                self.assertEqual(data["policyAfter"]["linearCapFrames"], 0)
                self.assertEqual(data["publicSubject"]["role"], role)
                self.assertEqual(data["rngReturns"], [])
                f.observer.close()

    def test_input_records_current_policy_before_and_after_and_keeps_rng_owner(self):
        for role in ("WILD", "MOUNTED"):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as directory:
                f = Fixture(directory)
                f.actor["role"] = role
                self.prepare_commit(f, 1)
                f.enter("walk-policy", r0=0x02220000)
                self.assertEqual(len(f.observer.policy_contexts), 1)
                f.enter("walk-rng", sp=0x027E3780, lr=0x02001041)
                f.returned(123, sp=0x027E3780, address=0x02001040)
                f.put(0x02200000 + 208, bytes(reversed(range(36))))
                f.returned(1); f.observer.completed_frame(12)
                self.assertIsNone(f.hooks.error)
                data = f.observer.drain()[0]["data"]
                self.assertEqual(data["operation"], 1)
                self.assertEqual(data["policyBeforeHex"], bytes(range(36)).hex())
                self.assertEqual(data["policyAfterHex"], bytes(reversed(range(36))).hex())
                self.assertEqual(data["rngReturns"][0]["value"], 123)
                self.assertEqual(f.observer.policy_contexts, [])
                f.observer.close()

    def test_input_rejects_changed_owner_or_lane_at_return(self):
        for change in (lambda f: f.actor.update(subjectIdentity=123),
                       lambda f: f.put(0x02221000, b"bad!")):
            with tempfile.TemporaryDirectory() as directory:
                f = Fixture(directory); self.prepare_commit(f, 1)
                f.enter("walk-policy", r0=0x02220000); change(f); f.returned(1)
                self.assertIsNotNone(f.hooks.error)
                self.assertEqual(f.observer.drain(), [])
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
        program += '_Static_assert(sizeof(OverworldActorPolicyState) == 36, "policy size");\n'
        for offset, name in enumerate(("direction", "tileCounter", "speed", "baseSpeed", "spotState",
                                       "skidRemaining", "turnDirection", "resumeSpeed")):
            program += f'_Static_assert(offsetof(OverworldWildWalkMomentumState, {name}) == {offset}, "momentum {name}");\n'
        program += '_Static_assert(sizeof(struct OverworldWildBehaviorProfileData) == 80, "lane size");\n'
        program += '_Static_assert(offsetof(OverworldActorRuntimeSlot, policy) == sizeof(OverworldActorStateSnapshot) + sizeof(OverworldMotionState), "policy follows actor motion");\n'
        for name, offset in (("walkMomentum", 0), ("chainStepsRemaining", 16), ("deferredChainPauseTicks", 17),
                             ("deferredChainPauseAction", 18), ("variancePhase", 19), ("bufferedDirection", 20),
                             ("stopPending", 21), ("pendingStep", 22), ("pendingSkid", 23), ("streamState", 24),
                             ("linearElapsed", 32), ("linearCarry", 33),
                             ("linearMode", 34), ("linearCapFrames", 35)):
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
        f.destination_query(448, sp=0x027E36E0)
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


class AutomaticQuerySpawnObserverTests(unittest.TestCase):
    setUp = SharedNativeObserverTests.setUp
    resolve_profile = SharedNativeObserverTests.resolve_profile

    def prepare_query(self):
        f = self.f
        f.actor["active"] = False
        f.rt.WILD_RUNTIME_PTR_OFFSET = 0xE4
        self.runtime, self.control, self.call, self.world, self.command = (
            0x02240000, 0x027E3A00, 0x027E3A40, 0x027E3A80, 0x027E3AE0)
        f.put(f.rt.WILD_STATE + 0xE4, struct.pack("<I", self.runtime))
        self.prepared = self.runtime + 992
        self.ops, self.world_ops = 0x023D7F44, 0x023D7F00
        f.put(self.world_ops, struct.pack("<HH", 3, 84))
        f._field_actor_availability = lambda field: dict(authenticated=True, reason=None)
        self.owner = dict(stateAddress=0x023C2308, entry=0x02100000,
                         fieldEpoch=2, mapGeneration=3)
        raw = struct.pack("<4I2HIB3s", 0x020FFFC0, 67680, self.owner["entry"],
                          0x02231000, 2, 3, 21, 1, bytes(3))
        self.owner["rawHex"] = raw.hex()
        f.put(self.owner["stateAddress"], raw)
        f.put(0x023C8148, bytes((0x40, 0, 0, 0)))
        self.service = 0x023C22F0
        f.put(self.service, struct.pack("<IHHI3I", 0x53444F57, 2, 24,
                                    self.owner["stateAddress"], 1, 3, 5))
        self.expected = bytearray(66216)
        for i, (name, (address, size, _)) in enumerate(QUERY_SPAWN_OWNERS.items()):
            offset = address - 0x02080000
            self.expected[offset:offset + size] = bytes((0x61 + i,)) * size
        f.put(self.owner["entry"], self.expected)
        f.put(self.ops, bytes((0x35,)) * 72)
        f.packaged_code = f.read
        f.observer.query_spawn_identity = dict(owner=self.owner, expected=bytes(self.expected),
            service=self.service, serviceBytes=f.read(self.service, 24),
            ops=(self.ops, f.read(self.ops, 72)), descriptorSize=196)
        for name, label, before, after, output in (
                ("NativeSpawn", "spawn-queued", f.observer._query_spawn_before,
                 f.observer._query_spawn_after, "spawn-queued"),
                ("NativeFinalize", "spawn-query-finalized", f.observer._query_finalize_before,
                 f.observer._query_finalize_after, "spawn-finalized")):
            address, size, _ = QUERY_SPAWN_OWNERS[name]
            address += self.owner["entry"] - 0x02080000
            f.observer.tokens.append(f.observer._query_spawn_tap(label, address,
                f.read(address, size), before, after, output))
        self.selected_slot, self.selected_terrain = 0, 0
        self.set_control(8)
        return f

    def set_control(self, operation):
        f = self.f
        raw = bytearray(52)
        struct.pack_into("<HH3I", raw, 0, 1, 52, self.ops, f.rt.WILD_STATE, 0x02231000)
        raw[44], raw[45], raw[46] = operation, 0, 0
        f.put(self.control, raw)
        command = bytes(84) + struct.pack("<I", self.control)
        f.put(self.command, command)
        call = bytearray(32)
        struct.pack_into("<3I", call, 0, self.world, 0, self.command)
        call[28:30] = bytes((4, 1))
        f.put(self.call, call)
        world = bytearray(84)
        struct.pack_into("<HHII", world, 0, 3, 84, 0x02231000, f.rt.WILD_STATE)
        struct.pack_into("<I", world, 28, self.world_ops)
        f.put(self.world, world)

    def begin(self):
        f = self.f
        f.put(0x027E3800, struct.pack("<2I", self.selected_terrain, self.selected_slot))
        offset = 0xFE38 if f.read(self.control + 47, 1)[0] == 1 else 0xFF62
        f.enter("spawn-queued", r0=self.call, r1=self.control,
                r2=f.rt.WILD_STATE, r3=0x02231000,
                lr=(self.owner["entry"] + offset) | 1)

    def finalize_query(self, *, result=0, stage=0xFD, resolver=False,
                       before_stage=None, locomotion=3):
        f = self.f
        f.put(self.runtime + 240, bytes((self.selected_slot+1, self.selected_terrain, 0, 0)))
        f.put(self.runtime + 2748, struct.pack("<I", 1))
        f.prepare_spawn(pointer=self.prepared, locomotion=locomotion)
        if before_stage is not None:
            f.put(self.runtime + 244, bytes((before_stage, 0, 0, 0)))
        f.put(0x027E3600, struct.pack("<3I", self.selected_terrain, self.selected_slot, self.prepared))
        self.leaf_return = self.owner["entry"] + (0xE1F4 if f.read(self.control + 44, 1)[0] == 8 else 0xF8C6)
        f.enter("spawn-query-finalized", sp=0x027E3600, lr=self.leaf_return | 1,
                r0=self.call, r1=self.control, r2=f.rt.WILD_STATE, r3=0x02231000)
        if resolver:
            self.resolve_profile(sp=0x027E3500, lr=0x020010C1)
            f.returned(0, sp=0x027E3500, address=0x020010C0)
        f.put(self.runtime + 244, bytes((stage, 0, 0, 0)))
        if f.hooks.error is None:
            f.returned(result, sp=0x027E3600, address=self.leaf_return)

    def finish(self):
        f = self.f
        offset = 0xFE38 if f.read(self.control + 47, 1)[0] == 1 else 0xFF62
        f.returned(1, address=self.owner["entry"] + offset)
        f.observer.completed_frame(12)
        return f.observer.drain()

    def test_transaction_callers_are_exact_compiled_named_bl_returns(self):
        from scripts.verify_overworld_field_capsule import packaged_thumb_calls
        from scripts.verify_pokemon_move_history_capture import elf_helper_bindings, elf_bytes_at
        root = Path(__file__).resolve().parents[2]
        linked = root / "build/overworld_query_code_addon/image.elf"
        bindings = elf_helper_bindings(linked, tuple(QUERY_SPAWN_OWNERS))
        for key, caller, target in (
            ("finalizer_from_spawn", "NativeSpawn", "NativeFinalize"),
            ("finalizer_from_commit", "OverworldEntryRoute_NativeControl", "NativeFinalize"),
            ("spawn_from_refill", "OverworldEntryRoute_NativeControl", "NativeSpawn"),
            ("spawn_from_single", "OverworldEntryRoute_NativeControl", "NativeSpawn"),
        ):
            address, size, *_ = bindings[caller]
            address &= ~1
            body = elf_bytes_at(linked, address, size)
            calls = packaged_thumb_calls(body, address, address, size)
            self.assertIn((QUERY_SPAWN_CALLERS[key] - 4, "bl", bindings[target][0] & ~1), calls)

    def test_real_query_finalizer_binds_owned260_and_pending_move_without_a_fake_wrapper(self):
        f = self.prepare_query()
        self.begin()
        self.finalize_query(resolver=True)
        events = self.finish()
        self.assertIsNone(f.hooks.error)
        rows = [e["data"] for e in events]
        final = next(r for r in rows if r["observation"] == "spawn-finalized")
        queued = next(r for r in rows if r["observation"] == "spawn-queued")
        self.assertEqual(f.observer.calls["spawn-finalized"]["entered"], 0)
        self.assertEqual(f.observer.calls["spawn-query-finalized"]["entered"], 1)
        self.assertEqual(final["nativeOwner"], "Query.NativeFinalize")
        self.assertFalse(final["pairEligible"])
        self.assertEqual(final["resolverReceipts"][0]["finalizationId"], final["finalizationId"])
        self.assertEqual(len(bytes.fromhex(queued["nativeEntry"]["queueAfter"]["preparedHex"])), 260)
        self.assertEqual(queued["nativeEntry"]["queueAfter"]["serial"], 1)
        self.assertEqual(final["queryCallbackReadCap"], QUERY_SPAWN_READ_CAP)
        self.assertLessEqual(max(final["queryCallbackReadBytes"].values()), QUERY_SPAWN_READ_CAP)
        self.assertTrue(queued["pendingEntry"])
        self.assertFalse(queued["pendingDestination"])
        self.assertFalse(f.actor["active"])
        self.assertEqual(f.observer.pending_destination_scans[0]["spawnAttemptId"], queued["spawnAttemptId"])

    def test_query_finalizer_success_preserves_exact_helper_counter_until_caller_returns(self):
        root = Path(__file__).resolve().parents[2]
        helper = (root / "include/overworld_wild_helper.h").read_text()
        values = [int(re.search(r"#define " + name + r" (\d+)", helper)[1]) for name in (
            "OW_WILD_HELPER_SPAWN_POSITION_ATTEMPT_CHECKS",
            "OW_WILD_HELPER_SPAWN_POSITION_CHECKS_PER_UPDATE")]
        self.assertEqual((values[0] + values[1] - 1) // values[1], 1)
        for operation, before, after, locomotion in (
                (8, 0, 0, 7), (8, 1, 1, 7), (7, 0xFC, 0, 3), (7, 0xFE, 0, 9)):
            with self.subTest(operation=operation, before=before):
                self.setUp()
                f = self.prepare_query()
                self.set_control(operation)
                if operation == 8:
                    self.begin()
                self.finalize_query(result=1, before_stage=before, stage=after, locomotion=locomotion)
                if operation == 8:
                    events = self.finish()
                else:
                    f.observer.completed_frame(12)
                    events = f.observer.drain()
                self.assertIsNone(f.hooks.error)
                final = next(e["data"] for e in events if e["data"]["observation"] == "spawn-finalized")
                self.assertEqual(final["queryQueueStage"], before)
                self.assertEqual(final["queueAfter"]["stage"], after)
                self.assertTrue(final["pairEligible"])
                self.assertLessEqual(max(final["queryCallbackReadBytes"].values()), QUERY_SPAWN_READ_CAP)

    def test_query_finalizer_success_rejects_changed_unknown_or_pending_counter(self):
        cases = [(8, 1, 0), (8, 0, 1), (8, 1, 2), (8, 1, 0xFC),
                 (7, 0xFC, 1), (7, 0xFE, 0xFE),
                 (7, 0xFB, 0), (7, 0xFD, 0), (7, 0xFF, 0)]
        cases += [(8, stage, stage) for stage in (2, 16, 17, 250, 0xFB, 0xFC, 0xFE, 0xFF)]
        cases += [(7, stage, 0) for stage in (0, 1, 2, 16, 17, 250)]
        for operation, before, after in cases:
            with self.subTest(operation=operation, before=before, after=after):
                self.setUp()
                f = self.prepare_query()
                self.set_control(operation)
                if operation == 8:
                    self.begin()
                self.finalize_query(result=1, before_stage=before, stage=after, locomotion=7)
                self.assertIsNotNone(f.hooks.error)
                self.assertFalse(f.observer.finalizations)
                self.assertNotIn("nativeEntry", f.observer.spawn_queue_contexts[-1] if f.observer.spawn_queue_contexts else {})

    def test_metadata_queue_and_constructor_use_actual_finalizer_receipts(self):
        f = self.prepare_query()
        self.begin()
        self.finalize_query(result=1, stage=0)
        rows = [e["data"] for e in self.finish()]
        queued = next(r for r in rows if r["observation"] == "spawn-queued")
        self.assertFalse(queued["pendingDestination"])
        final = next(r for r in rows if r["observation"] == "spawn-finalized")
        self.assertTrue(final["pairEligible"])
        f.actor["active"] = True
        f.put(0x027E3800, struct.pack("<I", self.prepared))
        f.enter("spawn-prepared", r0=f.rt.WILD_STATE, r1=0x02231000, r2=0, r3=0)
        f.returned(1)
        f.observer.completed_frame(13)
        constructor = f.observer.drain()[-1]["data"]
        self.assertEqual(constructor["finalization"]["status"], "matched")
        self.assertEqual(constructor["finalization"]["receipt"]["finalizationId"], final["finalizationId"])

    def test_missing_wrong_or_reused_query_finalizer_cannot_credit_queue(self):
        for mutation in ("missing", "stage", "serial", "pointer", "world", "actor", "reuse"):
            with self.subTest(mutation=mutation):
                self.setUp()
                f = self.prepare_query()
                self.begin()
                if mutation != "missing":
                    self.finalize_query()
                if mutation == "stage": f.put(self.runtime + 244, bytes(4))
                if mutation == "serial": f.put(self.runtime + 2748, struct.pack("<I", 2))
                if mutation == "pointer": f.observer.spawn_queue_contexts[-1]["nativeEntry"]["queueAfter"]["preparedPointer"] += 4
                if mutation == "world": f.map_id += 1
                if mutation == "actor": f.actor["active"] = True
                if mutation == "reuse": f.observer.spawn_queue_contexts[-1]["nativeEntry"]["spawnAttemptId"] += 1
                self.finish()
                self.assertIsNotNone(f.hooks.error)

    def test_real_current_lease_descriptor_fullbody_ops_and_call_inputs_reject(self):
        for mutation in ("owner", "descriptor", "body", "ops", "control", "command", "call", "world"):
            with self.subTest(mutation=mutation):
                self.setUp()
                f = self.prepare_query()
                if mutation == "owner": f.put(self.owner["stateAddress"] + 20, bytes(4))
                if mutation == "descriptor": f.put(self.owner["entry"] + 4, bytes((1,)))
                if mutation == "body": f.put(self.owner["entry"] + 0xDEF4 + 40, bytes((1,)))
                if mutation == "ops": f.put(self.ops + 8, bytes(4))
                if mutation == "control": f.put(self.control + 8, struct.pack("<I", f.rt.WILD_STATE + 4))
                if mutation == "command": f.put(self.command, bytes((1,)))
                if mutation == "call": f.put(self.call + 28, bytes((4, 0, 0, 0)))
                if mutation == "world": f.put(self.world + 4, bytes(4))
                self.begin()
                self.finalize_query()
                self.assertIsNotNone(f.hooks.error)
                self.assertFalse(f.observer.finalization_contexts)

    def test_query_commit_pending_uses_current_terrain_and_attempt_after_one_boundary(self):
        f = self.prepare_query()
        self.begin()
        self.finalize_query()
        rows = [e["data"] for e in self.finish()]
        attempt = next(r for r in rows if r["observation"] == "spawn-queued")["spawnAttemptId"]
        self.set_control(7)
        self.finalize_query(result=0, stage=0xFC)
        f.observer.completed_frame(13)
        rows = [e["data"] for e in f.observer.drain()]
        self.assertIsNone(f.hooks.error)
        final = next(r for r in rows if r["observation"] == "spawn-finalized")
        self.assertEqual(final["spawnAttemptId"], attempt)
        self.assertEqual(final["returnValue"], 0)
        self.assertFalse(final["pairEligible"])


    def test_current_leaf_return_read_cap_and_moved_input_are_not_silent(self):
        f = self.prepare_query()
        f.observer.query_spawn_read_bytes = QUERY_SPAWN_READ_CAP
        with self.assertRaisesRegex(NativeObservationError, "read cap exceeded"):
            f.observer._query_spawn_owner()
        self.begin()
        f.put(self.runtime + 240, bytes((self.selected_slot+1, self.selected_terrain, 0, 0)))
        f.put(self.runtime + 2748, struct.pack("<I", 1))
        f.prepare_spawn(pointer=self.prepared, locomotion=3)
        f.put(0x027E3600, struct.pack("<3I", self.selected_terrain, self.selected_slot, self.prepared))
        address = self.owner["entry"] + 0xE1F4
        f.enter("spawn-query-finalized", sp=0x027E3600, lr=address | 1,
                r0=self.call, r1=self.control, r2=f.rt.WILD_STATE, r3=0x02231000)
        f.put(self.command, bytes((1,)))
        f.returned(0, sp=0x027E3600, address=address)
        self.assertIn("transaction input/world changed", f.hooks.error)
        self.assertFalse(f.observer.pending)


    def test_boot_installs_without_the_retired_emitted_spawn_wrapper(self):
        directory = tempfile.TemporaryDirectory(prefix="native-spawn-no-wrapper-")
        self.addCleanup(directory.cleanup)
        f = Fixture(directory.name, missing_spawn_wrapper=True)
        self.addCleanup(f.observer.close)
        self.assertNotIn("OverworldWildSpawns_SpawnOne", f.rt.WILD_SYMBOLS)
        self.assertTrue(f.observer.installed)
        self.assertTrue(f.observer.calls["spawn-queued"]["awaitingQueryLease"])
        self.assertEqual(f.observer.calls["spawn-queued"]["entered"], 0)
        self.assertIn("spawn-query-discovery", f.observer.calls)

    def test_ordinary_refill_binds_real_child_slot_including_fishing(self):
        for slot, terrain in ((0,0),(2,1),(6,2),(8,3),(9,3)):
            with self.subTest(slot=slot, terrain=terrain):
                self.setUp()
                f=self.prepare_query()
                self.selected_slot,self.selected_terrain=slot,terrain
                f.put(self.control+47,bytes((1,)))
                self.begin()
                self.finalize_query()
                rows=[e["data"] for e in self.finish()]
                self.assertIsNone(f.hooks.error)
                queued=next(r for r in rows if r["observation"]=="spawn-queued")
                final=next(r for r in rows if r["observation"]=="spawn-finalized")
                self.assertEqual((queued["slot"],queued["terrain"],queued["queryOperation"]),(slot,terrain,1))
                self.assertEqual(final["slot"],slot)
                self.assertEqual(queued["queueAfter"]["queueSlot"],slot+1)
                self.assertEqual(queued["nativeOwner"],"Query.NativeSpawn")
                self.assertEqual(len(bytes.fromhex(queued["queueAfter"]["preparedHex"])),260)
                self.assertLessEqual(max(queued["queryCallbackReadBytes"].values()),QUERY_SPAWN_READ_CAP)
                self.assertIn("guestTiming",queued)

    def test_native_spawn_failed_and_position_pending_do_not_credit_queue_or_birth(self):
        for result in (0,2):
            with self.subTest(result=result):
                self.setUp()
                f=self.prepare_query();self.begin()
                f.returned(result,address=self.owner["entry"]+0xFF62)
                f.observer.completed_frame(12)
                rows=[e["data"] for e in f.observer.drain()]
                self.assertIsNone(f.hooks.error)
                queued=next(r for r in rows if r["observation"]=="spawn-queued")
                self.assertFalse(queued["queued"])
                self.assertEqual(queued["returnValue"],result)
                self.assertFalse(any(r["observation"]=="spawn-prepared" for r in rows))
                self.assertFalse(f.observer.spawn_queue_contexts)

    def test_native_spawn_wrong_caller_subtype_slot_or_changed_return_input_rejects(self):
        for fault in ("caller","subtype","direct-slot","ordinary-slot","ordinary-fields","follower","range","queued","active","returned-input","return-value"):
            with self.subTest(fault=fault):
                self.setUp();f=self.prepare_query()
                if fault=="subtype":f.put(self.control+47,bytes((2,)))
                if fault=="direct-slot":self.selected_slot=2
                if fault=="ordinary-slot":f.put(self.control+47,bytes((1,)));f.put(self.control+45,bytes((2,)));f.put(self.world+52,bytes((2,)))
                if fault=="ordinary-fields":f.put(self.control+47,bytes((1,)));f.put(self.control+28,struct.pack("<I",0x02210000))
                if fault=="follower":self.selected_slot=7
                if fault=="range":self.selected_slot=10
                if fault=="queued":f.put(self.runtime+240,bytes((1,0,0,0)))
                if fault=="active":f.actor["active"]=True
                if fault=="caller":
                    f.put(0x027E3800,bytes(8))
                    f.enter("spawn-queued",r0=self.call,r1=self.control,r2=f.rt.WILD_STATE,r3=0x02231000,
                            lr=(self.owner["entry"]+0xFD30)|1)
                else:self.begin()
                if fault in ("returned-input","return-value"):
                    if fault=="returned-input":f.put(self.command,bytes((1,)))
                    f.returned(3 if fault=="return-value" else 0,address=self.owner["entry"]+0xFF62)
                self.assertIsNotNone(f.hooks.error)
                self.assertFalse(f.observer.pending)

    def test_current_packaged_three_owner_discovery_and_large_control_guards(self):
        import ndspy.narc
        import ndspy.rom
        from tools.overworld.devtools_query_observer import sealed_package,relocated_image
        from tools.overworld.devtools_runtime import _elf_code,_elf_function_extent
        repo=Path(__file__).resolve().parents[2]
        directory=repo/"build/overworld_query_code_addon"
        elf=(directory/"image.elf").read_bytes();staged=(directory/"query.bin").read_bytes()
        member=ndspy.narc.NARC(ndspy.rom.NintendoDSRom.fromFile(str(repo/"test.nds"))
                                .getFileByName("a/0/2/8")).files[21]
        _,image,receipt=sealed_package(elf,staged,member)
        name="OverworldEntryRoute_NativeControl"
        address,size,digest=QUERY_SPAWN_OWNERS[name]
        self.assertEqual(_elf_function_extent(directory/"image.elf",name),(address,size))
        self.assertGreater(size,2048)
        for fault in (None,"extent","digest","loaded"):
            with self.subTest(fault=fault):
                self.setUp();f=self.prepare_query();f.rt.REPO=repo;f.rom=repo/"test.nds"
                f.observer.elf_code=lambda path,address,size:_elf_code(path,address,size)
                expected=relocated_image(image,receipt,self.owner["entry"])
                f.put(self.owner["entry"],expected)
                if fault=="loaded":f.put(self.owner["entry"]+address-0x02080000,b"\0\0")
                pins=dict(QUERY_SPAWN_OWNERS)
                if fault=="digest":pins[name]=(address,size,"0"*64)
                actual_extent=_elf_function_extent
                extent=lambda path,label: (address,size-2) if fault=="extent" and label==name else actual_extent(path,label)
                with patch("tools.overworld.devtools_resolver_parity.current_query_owner",return_value=self.owner), \
                     patch("tools.overworld.devtools_query_observer.native_entry_bindings",return_value={"ops":(self.ops,f.read(self.ops,72))}), \
                     patch("tools.overworld.devtools_runtime._elf_function_extent",side_effect=extent), \
                     patch.dict(NativeObservation._query_spawn_discover_after.__globals__,{"QUERY_SPAWN_OWNERS":pins}):
                    if fault is None:
                        f.observer._query_spawn_discover_after(None,{"returnValue":self.owner["entry"]})
                        self.assertEqual(f.observer.calls["spawn-queued"]["bodyBytes"],188)
                        self.assertEqual(f.observer.calls["spawn-query-finalized"]["bodyBytes"],608)
                        self.assertEqual(len(f.observer.query_spawn_tokens),2)
                    else:
                        with self.assertRaisesRegex(NativeObservationError,"typed full Control owner"):
                            f.observer._query_spawn_discover_after(None,{"returnValue":self.owner["entry"]})

    def test_moved_spawn_cost_group_omits_before_reads_without_unhooking(self):
        f=self.prepare_query()
        f.prepared=True;f.completed_frames=10;f.native_observation=f.observer
        tokens=tuple(f.observer.tokens)
        enable_spawn_cost_probe(f,{"mode":"omit-spawn-details"})
        with patch.object(f,"read",side_effect=AssertionError("cost gate must precede reads")):
            f.enter("spawn-queued",r0=self.call,r1=self.control,r2=f.rt.WILD_STATE,r3=0x02231000,
                    lr=(self.owner["entry"]+0xFF62)|1)
        self.assertIsNone(f.hooks.error)
        self.assertEqual(tuple(f.observer.tokens),tokens)
        self.assertFalse(f.observer.contexts)
        counts=f.spawn_cost_probe.result()["counters"]
        self.assertEqual(counts["spawn-queued"],{"entries":1,"omitted":1})
        self.assertEqual(counts["spawn-finalized"],{"entries":0,"omitted":0})

    def test_query_discovery_is_cached_per_exact_field_lease(self):
        f=self.prepare_query()
        self.assertFalse(f.observer._query_spawn_discovery_needed())
        f.put(0x0220000C,struct.pack("<H",3))
        self.assertTrue(f.observer._query_spawn_discovery_needed())
        f.put(0x0220000C,struct.pack("<H",2))
        # A retired or reloaded owner within this exact Field also rediscovers.
        owner_pointer=self.owner["stateAddress"]
        original=f.read(owner_pointer,28)
        retired=bytearray(original);retired[24]=0
        f.put(owner_pointer,retired)
        self.assertTrue(f.observer._query_spawn_discovery_needed())
        reloaded=bytearray(original);reloaded[:4]=struct.pack("<I",self.owner["entry"]+0x10000-64)
        f.put(owner_pointer,reloaded)
        self.assertTrue(f.observer._query_spawn_discovery_needed())
        f.put(owner_pointer,original)
        self.assertFalse(f.observer._query_spawn_discovery_needed())
        self.begin()
        self.assertFalse(f.observer._query_spawn_discovery_needed())

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
        request, result = bytearray(44), bytearray(216)
        struct.pack_into("<H", request, 0, f.actor["species"])
        request[8:10] = bytes((f.actor["level"], terrain))
        request[38] = 2
        for lane in (0, 80):
            # Observe the known broad native compatibility result, rather
            # than substituting the expected POOL-preservation rule into it.
            struct.pack_into("<HH", result, lane + 52, 15, 1023)
        struct.pack_into("<IIIII", result, 176, 1, 0, 0, 3, f.actor["behaviorFingerprint"])
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


class DistanceMaintenanceObserverTests(unittest.TestCase):
    def setUp(self):
        # Host code doubles exercise read admission, not native ROM proof.
        self.native=(0x023C79C8,332,b"H"*332)
        self.getter=(0x023CD184,24,b"G"*24)
        self.field=0x02210000;self.state=0x023D0000;self.runtime=0x02230000
        self.regs=SimpleNamespace(r0=self.field,r1=self.state,r2=self.runtime+0x23C,
            r3=self.runtime+0x274,sp=0x027E1000)
        self.blocks={self.state+0xE0:self.field.to_bytes(4,'little')+self.runtime.to_bytes(4,'little'),
            self.runtime+0x23C:bytes(54),self.runtime+0x274:bytes.fromhex('5044574f')+bytes(332),
            self.runtime+0x220:bytes(10)+(2).to_bytes(2,'little')+(1).to_bytes(2,'little')+bytes(2),
            self.regs.sp:(0xFFFF).to_bytes(4,'little')+(4).to_bytes(4,'little')+(0x023D3001).to_bytes(4,'little')}
        self.reads=[]
        def read(a,n):
            self.reads.append((a,n));data=self.blocks.get(a)
            if data is None:raise AssertionError('unproved pointer read '+hex(a))
            return data[:n]
        self.session=SimpleNamespace(emu=SimpleNamespace(memory=SimpleNamespace(register_arm9=self.regs)),
            read=read)
        self.observer=object.__new__(NativeObservation);self.observer.session=self.session
        self.observer._distance_native=self.native;self.observer._live_code=lambda a,c:c
        self.world={'fieldPointer':self.field,'statePointer':self.state,'fieldEpoch':3,'mapGeneration':3,'mapId':33}
        self.observer._world_context=lambda:dict(self.world)
        self.observer.calls={'distance-maintenance':{'entered':0}}
        self.clock={'actorFrame':100,'nativeCycle':90}
        self.observer._clock=lambda:dict(self.clock)
        self.observer.distance_count_cycle,self.observer.distance_count=None,0
        from unittest.mock import patch
        self.layout=patch('tools.overworld.devtools_pokemon_combat_observer._interaction_layout',return_value={'getter':self.getter})
        self.layout.start();self.addCleanup(self.layout.stop)
    def test_typed_entry_return_samples_and_bounded_spans(self):
        before=self.observer._distance_before();self.assertEqual(before['hardProtectedMask'],0xFFFF)
        self.assertEqual(before['before']['throwState']['targetMask'],2)
        body=bytearray(self.blocks[self.runtime+0x23C]);body[42]=1;self.blocks[self.runtime+0x23C]=bytes(body)
        row=self.observer._distance_after(before,{})
        self.assertEqual(row['after']['farSamples'][2],1);self.assertEqual(row['before']['farSamples'][2],0)
        self.assertTrue(row['diagnosticOnly']);self.assertFalse(row['acceptedProof'])
        self.assertEqual(sum(n for _,n in self.reads),848)
    def test_unproved_native_owner_span_or_helper_fails_closed(self):
        mutations=(('field',lambda:setattr(self.regs,'r0',0x02210004)),
            ('state',lambda:setattr(self.regs,'r1',0x023D0004)),
            ('presentation',lambda:setattr(self.regs,'r2',self.runtime-4)),
            ('telemetry',lambda:setattr(self.regs,'r3',self.runtime+1308)),
            ('unallocated-runtime',lambda:self.blocks.__setitem__(self.state+0xE0,self.field.to_bytes(4,'little')+bytes(4))),
            ('helper',lambda:setattr(self.observer,'_live_code',lambda a,c:bytes(len(c)))),
            ('receipt-limit',lambda:setattr(self.observer,'distance_count_cycle',90) or
                setattr(self.observer,'distance_count',64)))
        for label,mutate in mutations:
            with self.subTest(label=label):
                self.setUp();mutate()
                with self.assertRaises(NativeObservationError):self.observer._distance_before()
    def test_long_window_uses_native_cycle_budget_with_constant_actor_frame(self):
        for cycle in range(90,190):
            self.clock['nativeCycle']=cycle
            for _ in range(3):
                self.observer._distance_before()
                self.observer.calls['distance-maintenance']['entered']+=1
        self.assertEqual(self.observer.calls['distance-maintenance']['entered'],300)
        self.assertEqual((self.observer.distance_count_cycle,self.observer.distance_count),(189,3))
        self.assertEqual(self.clock['actorFrame'],100)
    def test_65th_call_in_one_native_cycle_fails_even_when_actor_frame_changes(self):
        for actor_frame in range(64):
            self.clock['actorFrame']=actor_frame
            self.observer._distance_before()
        with self.assertRaisesRegex(NativeObservationError,'receipt budget exceeded'):
            self.observer._distance_before()
        self.assertEqual((self.observer.distance_count_cycle,self.observer.distance_count),(90,64))
        self.clock['nativeCycle']=91
        self.observer._distance_before()
        self.assertEqual((self.observer.distance_count_cycle,self.observer.distance_count),(91,1))
        self.clock['nativeCycle']=90
        with self.assertRaisesRegex(NativeObservationError,'native cycle moved backwards'):
            self.observer._distance_before()
    def test_return_owner_epoch_ring_and_short_read_fail_closed(self):
        before=self.observer._distance_before()
        self.world['fieldEpoch']=4
        with self.assertRaises(NativeObservationError):self.observer._distance_after(before,{})
        self.world['fieldEpoch']=3
        b=bytearray(self.blocks[self.runtime+0x274]);b[4:6]=(9).to_bytes(2,'little');self.blocks[self.runtime+0x274]=bytes(b)
        with self.assertRaises(NativeObservationError):self.observer._distance_after(before,{})
        self.blocks[self.runtime+0x274]=bytes(3)
        with self.assertRaises(NativeObservationError):self.observer._distance_after(before,{})




class HelperCandidateDiagnosticTests(unittest.TestCase):
    """Real linked owners with copied memory; no native core or guest work."""
    def fixture(self):
        from tools.overworld.devtools_observer import HELPER_SCAN_OWNERS
        from tools.overworld.devtools_runtime import _elf_code
        root=Path(__file__).resolve().parents[2]
        memory={};reads=[];regions=[];tokens=[]
        def write(address,raw):
            memory.update({address+i:b for i,b in enumerate(raw)})
        def read(address,size):
            reads.append((address,size))
            return bytes(memory.get(address+i,0) for i in range(size))
        regs=SimpleNamespace(**{f'r{i}':0 for i in range(13)},sp=0x027E1400,lr=0)
        session=SimpleNamespace(rt=SimpleNamespace(REPO=root),completed_frames=10,
            emu=SimpleNamespace(memory=SimpleNamespace(register_arm9=regs)),read=read,
            spawn_cost_probe=SimpleNamespace(mode='baseline',gate=lambda *_:True))
        def code(path,address,size):
            body=_elf_code(path,address,size);regions.append((address,body));write(address,body)
            return body
        for home,name,address,size,sha in HELPER_SCAN_OWNERS.values():
            file=('overworld_wild_helper_overlay_linked.o' if home=='helper'
                  else 'overworld_wild_spawns_overlay_linked.o')
            code(root/'build'/file,address,size)
            if home=='wild':code(root/'build'/file,address,32)
        code(root/'build/overworld_wild_spawns_overlay_linked.o',0x023CCFD8,36)
        session.code_regions=regions
        def packaged(address,size):
            matches=[raw[address-base:address-base+size] for base,raw in regions
                     if base<=address<=base+len(raw)-size]
            if not matches:raise NativeObservationError('missing fixture packaged bytes')
            return matches[0]
        session.packaged_code=packaged
        hooks=SimpleNamespace(add=lambda a,cb:tokens.append((a,cb)) or(a,cb),
                              remove=lambda token:tokens.remove(token))
        obs=NativeObservation(session,hooks,code)
        world=dict(fieldPointer=0x02250000,statePointer=0x02230000,mapId=34,
                   fieldEpoch=3,mapGeneration=3)
        obs._world_context=lambda:dict(world)
        write(world['statePointer']+0xE0,struct.pack('<2I',world['fieldPointer'],0x02270000))
        prep=0x027E1200;output=0x027E0FC0
        write(prep,struct.pack('<3I',world['statePointer'],world['fieldPointer'],1))
        write(0x023C7CF4,b'\0\0'+struct.pack('<2H',17,73)+b'\0\0')
        regs.r0=0x023CCFD8;regs.r1=prep;regs.r2=1;regs.r3=0
        return SimpleNamespace(obs=obs,session=session,regs=regs,world=world,reads=reads,
                               write=write,read=read,tokens=tokens,prep=prep,output=output)

    def begin(self,f):
        value=f.obs._helper_spawn_before();f.obs.contexts.append(dict(data=value))
        return value

    def child(self,f,key,result,*,point=(565,362),terrain=1):
        # Exact ordinary BLX sites and aligned SP-relative u32. No code executes.
        from tools.overworld.devtools_observer import HELPER_SCAN_CALL_SITES
        address=f.obs.helper_spawn_layout['owners'][key][0]
        f.regs.r0=f.prep;f.regs.r1,f.regs.r2=point
        f.regs.sp=f.output-0x28
        f.regs.r3=f.output if key=='terrain' else (3 if key=='near' else address|1)
        f.regs.r4=address|1;f.regs.lr=HELPER_SCAN_CALL_SITES[key]+3
        data=f.obs._helper_candidate_before(key)
        if key=='terrain':f.write(f.output,struct.pack('<I',terrain))
        f.obs._helper_candidate_after(data,dict(returnValue=result))
        return data

    def test_current_native_owners_and_all_short_circuit_reasons(self):
        f=self.fixture();value=self.begin(f)
        cases=[(0,None,None,'terrain-unavailable'),(1,None,None,'terrain-mismatch'),
               (1,1,None,'occupied'),(1,0,1,'near-active'),(1,0,0,'selected')]
        for i,(terrainReturn,occupied,near,reason) in enumerate(cases):
            point=(565+i,362);f.reads.clear()
            self.child(f,'terrain',terrainReturn,point=point,
                       terrain=0 if reason=='terrain-mismatch' else (0xFFFFFFFF if not terrainReturn else 1))
            if not terrainReturn:
                self.assertNotIn((f.output & ~3,4),f.reads)
                self.assertNotIn('terrain',value['candidates'][-1])
            if occupied is not None:self.child(f,'occupied',occupied,point=point)
            if near is not None:self.child(f,'near',near,point=point)
            self.assertEqual(value['candidates'][-1]['reason'],reason)
        f.write(0x023C7CF6,struct.pack('<2H',17,146))
        reply=f.obs._helper_spawn_after(value,dict(returnValue=1))
        self.assertEqual(reply['cursorBefore'],[17,73]);self.assertEqual(reply['cursorAfter'],[17,146])
        self.assertEqual(len(reply['candidates']),5);self.assertFalse(reply['acceptedProof'])
        self.assertNotIn('_layout',reply);json.dumps(reply)

    def test_parent_field_table_code_and_pointer_faults_reject(self):
        for fault in ('no-parent','field','context','table','code','pointer','caller','binding'):
            with self.subTest(fault=fault):
                f=self.fixture();self.begin(f)
                address=f.obs.helper_spawn_layout['owners']['terrain'][0]
                f.regs.r0=f.prep;f.regs.r1=565;f.regs.r2=362;f.regs.r3=f.output
                f.regs.sp=f.output-0x28
                f.regs.r4=address|1;f.regs.lr=0x023C748F
                if fault=='no-parent':f.obs.contexts.clear()
                if fault=='field':f.world['fieldPointer']+=4
                if fault=='context':f.write(f.prep+4,struct.pack('<I',0x02250004))
                if fault=='table':f.write(0x023CCFDC,b'\0')
                if fault=='code':f.write(address,b'\0')
                if fault=='pointer':f.regs.r3=3
                if fault=='caller':f.regs.lr=0x023C7301
                if fault=='binding':f.regs.r4+=2
                with self.assertRaises(NativeObservationError):f.obs._helper_candidate_before('terrain')

    def test_child_order_point_radius_and_return_owner_faults_reject(self):
        for fault in ('order','point','radius','return','lost-parent','changed-code','changed-field'):
            with self.subTest(fault=fault):
                f=self.fixture();self.begin(f)
                self.child(f,'terrain',1)
                if fault=='order':
                    with self.assertRaises(NativeObservationError):self.child(f,'near',0)
                    continue
                self.child(f,'occupied',0)
                if fault=='point':
                    with self.assertRaises(NativeObservationError):self.child(f,'near',0,point=(566,362))
                    continue
                address=f.obs.helper_spawn_layout['owners']['near'][0]
                f.regs.r0=f.prep;f.regs.r1=565;f.regs.r2=362;f.regs.r3=3
                f.regs.r4=address|1;f.regs.lr=0x023C74B5
                if fault=='radius':
                    f.regs.r3=4
                    with self.assertRaises(NativeObservationError):f.obs._helper_candidate_before('near')
                    continue
                child=f.obs._helper_candidate_before('near')
                if fault=='lost-parent':f.obs.contexts.clear()
                if fault=='changed-code':f.write(address,b'\0')
                if fault=='changed-field':f.world['mapGeneration']+=1
                with self.assertRaises(NativeObservationError):
                    f.obs._helper_candidate_after(child,dict(returnValue=2 if fault=='return' else 0))

    def test_scanner_u32_output_is_exact_and_stack_word_is_strict(self):
        f=self.fixture();value=self.begin(f)
        f.write(f.output-4,b'\xEF\xCD\xAB\x98')
        f.write(f.output+4,b'\x76\x54\x32\x10')
        self.child(f,'terrain',1)
        self.assertEqual(value['candidates'][-1]['terrain'],1)
        self.assertEqual(f.read(f.output,4),struct.pack('<I',1))
        self.assertEqual(f.read(f.output-4,4),b'\xEF\xCD\xAB\x98')
        self.assertEqual(f.read(f.output+4,4),b'\x76\x54\x32\x10')
        self.assertIn((f.output,4),f.reads)
        for fault in ('before-word','after-word','unaligned-output','unaligned-stack','outside-stack','wrong-site','high-enum'):
            with self.subTest(fault=fault):
                f=self.fixture();self.begin(f)
                address=f.obs.helper_spawn_layout['owners']['terrain'][0]
                f.regs.r0=f.prep;f.regs.r1=565;f.regs.r2=362;f.regs.r3=f.output
                f.regs.r4=address|1;f.regs.sp=f.output-0x28;f.regs.lr=0x023C748F
                if fault=='before-word':f.regs.r3-=4
                if fault=='after-word':f.regs.r3+=4
                if fault=='unaligned-output':f.regs.r3+=1
                if fault=='unaligned-stack':f.regs.sp+=1;f.regs.r3+=1
                if fault=='outside-stack':f.regs.sp=0x02800000;f.regs.r3=f.regs.sp+0x28
                if fault=='wrong-site':f.regs.lr=0x023C74B5
                if fault=='high-enum':
                    child=f.obs._helper_candidate_before('terrain');f.write(f.output,struct.pack('<I',0x100))
                    with self.assertRaisesRegex(NativeObservationError,'enum'):
                        f.obs._helper_candidate_after(child,dict(returnValue=1))
                else:
                    with self.assertRaises(NativeObservationError):f.obs._helper_candidate_before('terrain')

    def test_sixteen_row_limit_cursor_and_incomplete_return_are_strict(self):
        f=self.fixture();value=self.begin(f)
        for i in range(16):self.child(f,'terrain',0,point=(565+i,362))
        self.assertEqual(len(f.obs._helper_spawn_after(value,dict(returnValue=2))['candidates']),16)
        with self.assertRaisesRegex(NativeObservationError,'limit'):self.child(f,'terrain',0)
        f=self.fixture();value=self.begin(f)
        self.child(f,'terrain',1)
        with self.assertRaisesRegex(NativeObservationError,'child order'):
            f.obs._helper_spawn_after(value,dict(returnValue=2))
        f=self.fixture();value=self.begin(f);f.write(0x023C7CF8,struct.pack('<H',290))
        with self.assertRaisesRegex(NativeObservationError,'typed ring'):
            f.obs._helper_spawn_after(value,dict(returnValue=2))

    def test_default_and_nonordinary_selector_have_no_extra_guest_reads(self):
        f=self.fixture();self.begin(f)
        f.session.spawn_cost_probe=None;f.reads.clear()
        for address,callback in list(f.tokens):callback()
        self.assertEqual(f.reads,[])
        f=self.fixture();f.regs.r2=2;f.reads.clear()
        reply=f.obs._helper_spawn_before()
        self.assertNotIn('helperDiagnostic',reply);self.assertEqual(f.reads,[])

    def test_old_body_extent_and_wrong_typed_owners_fail_before_admission(self):
        from tools.overworld.devtools_observer import HELPER_SCAN_OWNERS
        from tools.overworld.devtools_field_cleanup import symbol
        for fault in ('old-body','old-extent','function-kind','cursor-kind','table-kind','package-table'):
            with self.subTest(fault=fault):
                f=self.fixture();owners=dict(HELPER_SCAN_OWNERS)
                home,name,a,n,sha=owners['scanner']
                if fault=='old-body':owners['scanner']=(home,name,a,n,'ac7a001dba2c915ed9dbe5a2f4915c7f26942017bc966b33de241ea6d2295320')
                if fault=='old-extent':owners['scanner']=(home,name,a,512,sha)
                original=f.session.packaged_code
                if fault=='package-table':
                    f.session.packaged_code=lambda address,size: bytes(size) if address==0x023CCFD8 else original(address,size)
                def typed(image,name,kind,*args,**kwargs):
                    if ((fault=='function-kind' and name==owners['scanner'][1])
                            or (fault=='cursor-kind' and name=='sOverworldWildHelperSpawnPositionCursor')
                            or (fault=='table-kind' and name=='sOverworldWildSpawnPrepCallbacks')):
                        kind=1 if kind==2 else 2
                    return symbol(image,name,kind,*args,**kwargs)
                with patch('tools.overworld.devtools_observer.HELPER_SCAN_OWNERS',owners), \
                     patch('tools.overworld.devtools_field_cleanup.symbol',typed):
                    with self.assertRaises(ValueError):f.obs._helper_spawn_before()

    def test_compiled_body_table_and_bss_owner_faults_fail_before_admission(self):
        from tools.overworld.devtools_observer import HELPER_SCAN_OWNERS
        f=self.fixture();changed=dict(HELPER_SCAN_OWNERS)
        home,name,a,n,sha=changed['scanner'];changed['scanner']=(home,name,a,n,'0'*64)
        with patch('tools.overworld.devtools_observer.HELPER_SCAN_OWNERS',changed):
            with self.assertRaisesRegex(NativeObservationError,'full native owner'):
                f.obs._helper_spawn_before()
        for fault in ('context','table','slot','runtime'):
            f=self.fixture()
            if fault=='context':f.regs.r1=3
            if fault=='table':f.regs.r0+=4
            if fault=='slot':f.regs.r3=10
            if fault=='runtime':f.write(f.world['statePointer']+0xE4,bytes(4))
            with self.subTest(fault=fault),self.assertRaises(NativeObservationError):
                f.obs._helper_spawn_before()


if __name__ == "__main__":
    unittest.main()
