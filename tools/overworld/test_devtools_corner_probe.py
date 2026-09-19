"""Host checks for the actual fixed prepared query, not runtime movement proof."""
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.overworld.devtools_corner_probe import (
    CornerProbe, CornerProbeError, authenticate, COLLISION_ADDRESS, COLLISION_BYTES,
    LANDING_ENTRY, TERRAIN_OFFSET)
from tools.overworld.devtools_mount_walk_fixture import STATE_ADDRESS
from tools.overworld.test_devtools_mount_walk_fixture import session, ROOT
from tools.overworld.devtools_records import select_current_actor


def ready_session():
    s = session()
    s.actor["species"] = 155
    s.put(STATE_ADDRESS + 84, struct.pack("<H", 155))
    s.put(STATE_ADDRESS + 8 + TERRAIN_OFFSET, struct.pack("<H", 1))
    s.subject = select_current_actor(s._snapshot(), s.actor)
    s.avatar = 0x02090000
    s.put(s.field_pointer() + 0x40, struct.pack("<I", s.avatar))
    s.put(s.avatar + 0x30, struct.pack("<I", s.actor["engineIdentity"]["anchorPointer"]))
    s.rt.player_ptr = lambda _emu: s.actor["engineIdentity"]["anchorPointer"]
    return s


class ProbeTests(unittest.TestCase):
    def setUp(self):
        for name in ("tools.overworld.devtools_mount_walk_fixture.authenticate_mount",
                     "tools.overworld.devtools_corner_probe.authenticate_mount"):
            p = patch(name, return_value={"stateAddress": STATE_ADDRESS})
            p.start(); self.addCleanup(p.stop)
        p = patch("tools.overworld.devtools_corner_probe.authenticate", return_value={"checked": True})
        p.start(); self.addCleanup(p.stop)

    def start(self, s):
        probe = CornerProbe(s, s.subject)
        s.native_bridge_active = True
        return probe.recipe(s.native_trampoline["address"] + 0x200, lambda n, a: (n, a))

    def test_fixed_calls_real_readiness_and_no_writes(self):
        s = ready_session()
        recipe = self.start(s)
        request = next(recipe)
        for direction, result in enumerate((1, 0, 0, 0)):
            self.assertEqual(request, ("corner_collision", (s.avatar, 0x02060000, direction)))
            request = recipe.send(result)
        for index, target in enumerate(((1, 2), (3, 2), (1, 4), (3, 4))):
            self.assertEqual(request, ("corner_landing", (1, 7, s.field_pointer(), 1, *target, *target)))
            if index < 3:
                request = recipe.send(1)
            else:
                with self.assertRaises(StopIteration) as stop: recipe.send(1)
        result = stop.exception.value
        self.assertEqual([d["oneSideCorner"] for d in result["diagonals"]], [True, True, False, False])
        self.assertFalse(result["acceptedProof"])
        self.assertEqual(result["before"], result["after"])
        self.assertFalse(s.writes)

    def test_bridge_arrival_rejects_other_flag_changes(self):
        s = ready_session()
        recipe = self.start(s)
        original = s._snapshot
        def snapshot(*args, **kwargs):
            value = original(*args, **kwargs)
            value["player"]["flags"] ^= 0x100
            return value
        s._snapshot = snapshot
        with self.assertRaisesRegex(CornerProbeError, "beyond observed field housekeeping"):
            next(recipe)
        self.assertFalse(s.writes)

    def test_reject_setup_identity_masks_and_readiness(self):
        for fault in ("species", "identity", "mask", "empty", "input", "staged", "avatar", "anchor", "owner"):
            with self.subTest(fault=fault):
                s = ready_session()
                if fault == "species": s.actor["species"] = 156
                elif fault == "identity": s.actor["identityVerified"] = False
                elif fault == "mask": s.put(STATE_ADDRESS + 40, struct.pack("<H", 0x8001))
                elif fault == "empty": s.put(STATE_ADDRESS + 40, bytes(2))
                elif fault == "input": s.inputs["heldKeys"] = 1
                elif fault == "staged": s.actor["stagedMovement"]["idle"] = False
                elif fault == "avatar": s.put(s.avatar + 0x30, bytes(4))
                elif fault == "anchor": s.actor["engineIdentity"]["anchorInCurrentManager"] = False
                else: s.rom = ROOT / "test.nds"
                with self.assertRaises(ValueError): next(self.start(s))
                self.assertFalse(s.writes)

    def test_each_return_rechecks_owner_state_and_game_clock(self):
        for fault in ("clock", "heap", "mount", "actor", "avatar", "policy", "bridge", "result"):
            with self.subTest(fault=fault):
                s = ready_session(); recipe = self.start(s); next(recipe)
                if fault == "clock": s.completed_frames += 1
                elif fault == "heap": s.native_heap_generation += 1
                elif fault == "mount": s.put(STATE_ADDRESS + 40, struct.pack("<H", 2))
                elif fault == "actor": s.actor["engineAnchorGeneration"] += 1
                elif fault == "avatar": s.put(s.avatar + 0x10, b"\x01")
                elif fault == "policy": s.put(s.policy_address + 8, b"\xff")
                elif fault == "bridge": s.native_bridge_active = False
                with self.assertRaises(ValueError): recipe.send(0x10 if fault == "result" else 0)
                self.assertFalse(s.writes)

    def test_native_cycles_are_not_game_updates_and_invalid_landing_fails(self):
        s = ready_session(); recipe = self.start(s); next(recipe)
        for _ in range(4):
            s.rt.EXECUTED_FRAME_COUNT += 1
            recipe.send(0)
        with self.assertRaises(CornerProbeError): recipe.send(2)

    def test_flags_baseline_is_native_query_entry_not_bridge_arrival(self):
        for housekeeping in (0x4, 0x400000):
            with self.subTest(housekeeping=housekeeping):
                s = ready_session()
                original = s._snapshot
                flags = [original()["player"]["flags"]]
                def snapshot(*args, **kwargs):
                    value = original(*args, **kwargs)
                    value["player"]["flags"] = flags[0]
                    return value
                s._snapshot = snapshot
                before = original()["player"]["flags"]
                recipe = self.start(s)
                flags[0] = before ^ housekeeping
                next(recipe)  # Valid idle housekeeping before the query is allowed.
                flags[0] = before
                with self.assertRaisesRegex(CornerProbeError, "changed actor/policy/input"):
                    recipe.send(0)  # But any flags change inside the batch is refused.
        self.assertFalse(s.writes)


class AuthenticationTests(unittest.TestCase):
    def test_complete_native_bodies_and_public_callback(self):
        s = ready_session()
        landing, code = 0x023CE000, bytes(range(64))
        entry = bytearray(40); struct.pack_into("<I", entry, 28, landing | 1)
        stock = bytes(COLLISION_ADDRESS - 0x02000000) + bytes(range(COLLISION_BYTES))
        s.arm9_code_region = (0x02000000, stock)
        s.put(COLLISION_ADDRESS, stock[-COLLISION_BYTES:])
        s.target = lambda n: COLLISION_ADDRESS if n == "corner_collision" else landing
        s.rt.WILD_SYMBOLS = {}
        s.rt.linked_symbol = lambda _, n: LANDING_ENTRY if n == "gOverworldWildSpawnsOverlayEntry" else landing | 1
        s.packaged_code = lambda a, n: bytes(entry) if a == LANDING_ENTRY else code
        with patch.object(Path, "read_bytes", return_value=stock), \
             patch("tools.overworld.devtools_runtime._elf_function_extent", return_value=(landing, len(code))), \
             patch("tools.overworld.devtools_runtime._elf_code", side_effect=lambda p,a,n: bytes(entry) if a == LANDING_ENTRY else code):
            self.assertEqual(authenticate(s)["landingSize"], 64)
            for fault in ("stock-tail", "landing-tail", "callback", "target"):
                with self.subTest(fault=fault):
                    s.put(COLLISION_ADDRESS, stock[-COLLISION_BYTES:])
                    struct.pack_into("<I", entry, 28, landing | 1)
                    s.packaged_code = lambda a,n: bytes(entry) if a == LANDING_ENTRY else code
                    s.target = lambda n: COLLISION_ADDRESS if n == "corner_collision" else landing
                    if fault == "stock-tail": s.put(COLLISION_ADDRESS + COLLISION_BYTES - 1, b"\xff")
                    elif fault == "landing-tail": s.packaged_code = lambda a,n: bytes(entry) if a == LANDING_ENTRY else code[:-1] + b"\xff"
                    elif fault == "callback": struct.pack_into("<I", entry, 28, landing + 5)
                    else: s.target = lambda n: COLLISION_ADDRESS + 4 if n == "corner_collision" else landing
                    with self.assertRaises(CornerProbeError): authenticate(s)

    def test_actual_profile_and_avatar_headers(self):
        source = (ROOT / "include/map_events_internal.h").read_text()
        body = source.split("typedef struct FIELD_PLAYER_AVATAR {", 1)[1].split("} FIELD_PLAYER_AVATAR;", 1)[0]
        body = body.replace("LocalMapObject* mapObject;", "u32 mapObject;").replace(
            "FIELD_PLAYER_AVATAR_SUB *avatar_sub;", "u32 avatar_sub;")
        code = '#include "overworld_behavior_resolver.h"\n'
        code += 'typedef struct {' + body + '} Avatar;\n'
        code += '_Static_assert(__builtin_offsetof(OverworldWildBehaviorProfileData,chillAllowedTerrainMask)==32,"mask");\n'
        code += '_Static_assert(__builtin_offsetof(Avatar,mapObject)==0x30,"anchor");\n'
        code += '_Static_assert(sizeof(Avatar)==64,"avatar");\nint main(void){return 0;}\n'
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(["cc", "-DOVERWORLD_BEHAVIOR_HOST", "-I", str(ROOT / "include"),
                                     "-x", "c", "-", "-o", str(Path(directory) / "layout")],
                                    input=code, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        header = (ROOT / "include/overworld_wild_spawns_internal.h").read_text()
        self.assertIn("#define OVERWORLD_WILD_LANDING_VALUE_SERVICE_VERSION 1", header)
        self.assertIn("#define OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY_ADDR 0x023CD000", header)


if __name__ == "__main__": unittest.main()
