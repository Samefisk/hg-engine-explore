"""Host controls run the installed entry/return callback, never a game core."""
from copy import deepcopy
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import unittest

from tools.overworld.test_devtools_observer import Fixture
from tools.overworld.devtools_walk_intent import NativeWalkIntent, WalkIntentError


class WalkIntentTests(unittest.TestCase):
    def test_seventh_settle_is_not_suppressed_as_an_eighth_start(self):
        with tempfile.TemporaryDirectory() as directory:
            f, c = self.fixture(directory)
            c.accepted = 7
            f.actor.update(motionKind="WALK", motionPhase="SETTLING")
            f.policy["pending"] = 0
            f.enter("walk-direction-intent", r0=0x02220000, r1=7)
            self.assertIsNone(c.failure)
            self.assertEqual(f.regs.r0, 0x02220000)
            self.assertEqual(f.regs.r1, 7)
            self.assertFalse(c.inflight)
            self.assertEqual(c.rows, [])
            f.actor.update(motionKind="NONE", motionPhase="IDLE")
            f.emu.memory.set_next_instruction = lambda address: None
            f.enter("walk-direction-intent", r0=0x02220000, r1=7)
            self.assertEqual(f.regs.r0, 0)
            f.returned(0)
            self.assertTrue(c.rows[-1]["suppressed"])
            c.completed_boundary()
            c.close()

    def test_busy_walk_attempt_keeps_native_input_and_earns_no_start(self):
        for phase in ("PLANNED", "MOVING", "COMMIT_PENDING", "SETTLING"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as directory:
                f, c = self.fixture(directory)
                f.actor.update(motionKind="WALK", motionPhase=phase)
                f.policy["pending"] = 0 if phase == "SETTLING" else 2
                f.enter("walk-direction-intent", r0=0x02220000, r1=7)
                self.assertIsNone(c.failure)
                self.assertEqual(f.regs.r1, 7)
                self.assertEqual(c.rows, [])
                self.assertEqual(c.accepted, 0)
                self.assertFalse(c.inflight)
                f.actor.update(motionKind="NONE", motionPhase="IDLE")
                f.policy["pending"] = 0
                f.enter("walk-direction-intent", r0=0x02220000, r1=7)
                self.assertEqual(f.regs.r1, 4)
                f.actor.update(motionKind="WALK", motionPhase="MOVING")
                f.policy["pending"] = 2
                f.returned(1)
                self.assertEqual(c.accepted, 1)
                c.close(disposing=True)

    def fixture(self, directory):
        f = Fixture(directory)
        f.completed_frames = 10
        f.native_bridge_active = False
        f.abort_native_control = lambda error: (_ for _ in ()).throw(error)
        f.actor["engineIdentity"] = dict(pointer=0x02210000, current_manager=4, object_manager=4, manager_index=0)
        for index in range(15):
            setattr(f.regs, "r" + str(index), 100 + index)
        f.policy = dict(pending=0)
        f.rt.movement_policy_state = lambda emu, slot: deepcopy(f.policy)
        f.observer._chain_current = lambda slot: (deepcopy(f.actor), {}, deepcopy(f.actor["engineIdentity"]), {})
        f.native_observation = f.observer
        resolved = bytearray(256); resolved[19] = 1
        f.observer.profiles[44] = dict(resolved=True, resultHex=resolved.hex())
        f.put(0x02221000, resolved[:216])
        name = "OverworldWildSpawns_TryStartAcceleratedWalkStep"
        f.symbols[name] = 0x02301000
        f.put(0x02301000, b"W" * 32)
        f.code_regions.append((0x02301000, b"W" * 32))
        f.put(0x02220000, struct.pack("<5IBxHBB2x", f.rt.WILD_STATE, 0x02231000,
              0x02210000, 0x02221000, 0x02222000, 0, 0, 0, 0))
        control = NativeWalkIntent(f, f.actor, 4, 100)
        control.install()
        return f, control

    def test_seven_real_starts_then_false_return_preserves_registers(self):
        with tempfile.TemporaryDirectory() as directory:
            f, c = self.fixture(directory)
            for index in range(7):
                f.actor.update(motionKind="NONE", motionPhase="IDLE"); f.policy["pending"] = 0
                f.enter("walk-direction-intent", r0=0x02220000, r1=7)
                self.assertEqual(f.regs.r1, 4)
                f.actor.update(motionKind="WALK", motionPhase="MOVING"); f.policy["pending"] = 2
                f.returned(1)
                self.assertIsNone(f.hooks.error)
                self.assertEqual(c.accepted, index + 1)
                self.assertEqual(c.rows[-1]["before"]["publicSubject"]["motionKind"], "NONE")
                row = c.rows[-1]
                self.assertEqual({k: v for k, v in row["registersBefore"].items() if k != "r1"},
                                 {k: v for k, v in row["registersAfter"].items() if k != "r1"})
            redirects = []
            f.emu.memory.set_next_instruction = redirects.append
            f.actor.update(motionKind="NONE", motionPhase="IDLE")
            f.policy["pending"] = 0
            f.enter("walk-direction-intent", r0=0x02220000, r1=7)
            self.assertEqual(f.regs.r0, 0)
            self.assertEqual(f.regs.r1, 7)
            self.assertEqual(redirects, [0x02001001])
            f.returned(0)
            self.assertEqual(c.accepted, 7)
            self.assertTrue(c.rows[-1]["suppressed"])
            row = c.rows[-1]
            self.assertEqual({k: v for k, v in row["registersBefore"].items() if k != "r0"},
                             {k: v for k, v in row["registersAfter"].items() if k != "r0"})
            f.actor.update(motionKind="NONE", motionPhase="IDLE")
            c.completed_boundary(); c.close()
            self.assertTrue(c.result()["closed"])
            self.assertEqual(c.result()["guestMemoryWrites"], 0)

    def test_true_without_walk_is_not_an_accepted_start(self):
        with tempfile.TemporaryDirectory() as directory:
            f, c = self.fixture(directory)
            f.enter("walk-direction-intent", r0=0x02220000, r1=4); f.returned(1)
            self.assertEqual(c.accepted, 0)
            self.assertIn("actual Walk", c.failure)
            c.close(disposing=True)

    def test_flat_walk_nullable_primitives_keeps_exact_null_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            f, c = self.fixture(directory)
            f.put(0x02220010, bytes(4))
            f.enter("walk-direction-intent", r0=0x02220000, r1=7)
            self.assertIsNone(c.failure)
            self.assertEqual(f.regs.r1, 4)
            f.actor.update(motionKind="WALK", motionPhase="MOVING"); f.policy["pending"] = 2
            f.returned(1)
            self.assertIsNone(c.failure)
            self.assertEqual(c.accepted, 1)
            self.assertEqual(c.rows[0]["primitivesPointer"], 0)
            self.assertIsNone(c.rows[0]["primitivesHex"])
            c.close(disposing=True)

    def test_nonnull_invalid_primitives_still_fails_before_write(self):
        for pointer in (1, 0x03000000, 0x02222000):
            with self.subTest(pointer=pointer), tempfile.TemporaryDirectory() as directory:
                f, c = self.fixture(directory)
                f.put(0x02220010, struct.pack("<I", pointer))
                if pointer == 0x02222000: f.put(pointer, b"wrong")
                f.enter("walk-direction-intent", r0=0x02220000, r1=7)
                self.assertIsNotNone(c.failure)
                self.assertEqual(f.regs.r1, 7)
                c.close(disposing=True)

    def test_wrong_owner_profile_and_deadline_fail_before_direction_write(self):
        for fault in ("owner", "profile", "deadline", "missing-profile", "direction", "context"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as directory:
                f, c = self.fixture(directory)
                if fault == "owner": f.actor["authorityGeneration"] += 1
                if fault == "profile": f.put(0x02221000, b"bad!")
                if fault == "deadline": f.completed_frames = 111
                if fault == "missing-profile": f.observer.profiles.clear()
                if fault == "direction":
                    f.put(0x02221013, b"\x00")
                    f.observer.profiles[44]["resultHex"] = bytes(256).hex()
                if fault == "context": f.put(0x02220008, struct.pack("<I", 0x02210004))
                f.enter("walk-direction-intent", r0=0x02220000, r1=7)
                self.assertIsNotNone(c.failure)
                self.assertEqual(f.regs.r1, 7)
                c.close(disposing=True)

    def test_unrelated_slot_is_untouched_and_early_close_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            f, c = self.fixture(directory)
            f.put(0x02220014, b"\x01")
            f.enter("walk-direction-intent", r0=0x02220000, r1=7)
            self.assertEqual(f.regs.r1, 7)
            self.assertEqual(c.rows, [])
            with self.assertRaises(WalkIntentError): c.close()
            c.close(disposing=True)

    def test_fixed_argument_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            f, c = self.fixture(directory)
            for direction, frames in ((-1, 100), (8, 100), (True, 100), (4, 0), (4, 601)):
                with self.assertRaises(ValueError): NativeWalkIntent(f, f.actor, direction, frames)
            c.close(disposing=True)

    def test_cardinal_and_diagonal_lane_rules(self):
        for mode in range(3):
            for direction in range(8):
                with self.subTest(mode=mode, direction=direction), tempfile.TemporaryDirectory() as directory:
                    f, c = self.fixture(directory)
                    c.direction = direction
                    data = bytearray(256); data[19] = mode
                    f.put(0x02221000, data[:216])
                    f.observer.profiles[44]["resultHex"] = data.hex()
                    f.enter("walk-direction-intent", r0=0x02220000, r1=7)
                    allowed = mode == 1 or (direction < 4 and mode == 0) or (direction >= 4 and mode == 2)
                    self.assertEqual(c.failure is None, allowed)
                    if allowed: self.assertEqual(f.regs.r1, direction)
                    c.close(disposing=True)

    def test_arm_layout_and_dispatch_contract(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
        self.assertRegex(source, r"stepContext\.primitives = NULL;\s*stepContext\.slot = \(u8\)slot;[\s\S]{0,350}OverworldWildSpawns_TryStartAcceleratedWalkStep\(\s*&stepContext,")
        declaration = re.search(r"typedef struct OverworldWildDirectionStepContext \{.*?\} OverworldWildDirectionStepContext;", source, re.S)[0]
        program = '#include "overworld_wild_spawns_internal.h"\n#include "overworld_wild_movement.h"\n#include <stddef.h>\n' + declaration
        for name, offset in (("state", 0), ("fieldSystem", 4), ("object", 8), ("profile", 12),
                             ("primitives", 16), ("slot", 20), ("allowedTile", 22), ("jumpLevel", 24), ("avoidPreviousTile", 25)):
            program += f'\n_Static_assert(offsetof(OverworldWildDirectionStepContext,{name})=={offset},"{name}");'
        program += '\n_Static_assert(sizeof(OverworldWildDirectionStepContext)==28,"context size");'
        program += '\n_Static_assert(sizeof(OverworldWildBehaviorProfile)==216,"profile size");'
        program += '\n_Static_assert(sizeof(OverworldWildBehaviorPrimitives)==11,"primitives size");'
        program += '\n_Static_assert(OVERWORLD_ACTOR_WALK_PENDING_ACTIVE==2,"pending active");'
        program += '\n_Static_assert(offsetof(OverworldWildSpawnState,movementSpawnRunActive)==514,"spawn run");'
        program += '\n_Static_assert(offsetof(OverworldWildSpawnState,movementSpotStates)==264,"spot state");'
        program += '\n_Static_assert(offsetof(OverworldWildBehaviorProfileData,hopAllowNonCardinal)==19,"directions");'
        program += '\n_Static_assert(OW_WILD_SPOT_STATE_ACTIVE==2 && OW_WILD_SPOT_STATE_TIRED==3,"lane selection");'
        program += '\n_Static_assert(OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY==0 && OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_AND_DIAGONAL==1 && OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_DIAGONAL_ONLY==2,"direction modes");'
        cc = shutil.which("arm-none-eabi-gcc") or "/opt/homebrew/bin/arm-none-eabi-gcc"
        result = subprocess.run([cc, "-x", "c", "-std=c11", "-I" + str(root / "include"), "-fsyntax-only", "-"],
                                input=program, text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
