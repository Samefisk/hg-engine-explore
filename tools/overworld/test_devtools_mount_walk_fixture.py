"""Prepared mounted lane byte guards, rollback and independent header layout."""
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.overworld.devtools_mount_walk_fixture import (
    MountWalkFixture, MountWalkFixtureError, STATE_ADDRESS, STATE_BYTES, authenticate_mount)
from tools.overworld.test_devtools_walk_reset import Session
from tools.overworld.devtools_records import select_current_actor

ROOT = Path(__file__).resolve().parents[2]


def session():
    s = Session("MOUNTED")
    s.prepared, s.native_bridge_active, s.completed_frames = True, False, 20
    s.directory = ROOT / "build/private-fixture-host-test"
    s.rom, s.save = s.directory / "test.nds", s.directory / "test.sav"
    s.rom_hash, s.save_hash = "rom", "save"
    s.rt.REPO, s.rt.EXECUTED_FRAME_COUNT, s.rt.MOUNT_SYMBOLS = ROOT, 30, {}
    s.actor["sourceIdentity"]["personality"] = 77
    s.actor["engineIdentity"]["anchorInCurrentManager"] = True
    base_snapshot = s._snapshot
    def snapshot(*args, **kwargs):
        value = base_snapshot(*args, **kwargs)
        value["context"]["mapId"] = 33
        return value
    s._snapshot = snapshot
    s.subject = select_current_actor(s._snapshot(), s.actor)
    raw = bytearray(STATE_BYTES)
    struct.pack_into("<II", raw, 0, s.field_pointer(), 0x02080000)
    raw[8:80] = bytes(range(72))
    raw[20] = 1
    struct.pack_into("<IHHHHBBBB", raw, 80, 77, 165, 33, 3, 4, 0, 5, 0, 1)
    struct.pack_into("<IBBBB", raw, 96, 1, 3, 0, 0, 0)
    raw[122] = 1
    s.put(STATE_ADDRESS, raw)
    s.aborted = []
    s.abort_native_control = s.aborted.append
    return s


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.auth = patch("tools.overworld.devtools_mount_walk_fixture.authenticate_mount",
                          return_value={"stateAddress": STATE_ADDRESS})
        self.auth.start()
        self.addCleanup(self.auth.stop)

    def test_direction_only_and_exact_timing_boundaries(self):
        for direction in range(3):
            for timing in (None, 1, 32):
                s = session()
                original = s.read(STATE_ADDRESS, STATE_BYTES)
                r = MountWalkFixture(s, s.subject, direction, timing).run()
                expected = bytearray(original)
                expected[27] = direction
                if timing is not None:
                    expected[15] = expected[59] = timing
                    expected[58] = 0
                self.assertEqual(s.read(STATE_ADDRESS, STATE_BYTES), bytes(expected))
                self.assertTrue(r["completed"])
                self.assertFalse(r["acceptedProof"])
                self.assertEqual(r["before"]["clock"], r["after"]["clock"])
                self.assertNotIn("state", r["before"]["readiness"])
                self.assertNotIn("actors", r["before"]["readiness"]["snapshot"])
                self.assertNotIn("stompTime", r)

    def test_stomp_threshold_changes_only_named_bytes(self):
        for threshold in (0, 1, 2, 32):
            s = session()
            expected = bytearray(s.read(STATE_ADDRESS, STATE_BYTES))
            expected[27], expected[78] = 0, threshold
            r = MountWalkFixture(s, s.subject, 0, stomp_time=threshold).run()
            self.assertEqual(s.read(STATE_ADDRESS, STATE_BYTES), bytes(expected))
            self.assertEqual(r["stompTime"], threshold)
            self.assertEqual(r["changedOffsets"], [19, 70])
            self.assertEqual(r["before"]["clock"], r["after"]["clock"])
        for threshold in (True, -1, 33, 1.5, "2"):
            s = session()
            with self.assertRaises(MountWalkFixtureError):
                MountWalkFixture(s, s.subject, 0, stomp_time=threshold)
            self.assertFalse(s.writes)

    def test_stomp_write_failure_restores_threshold_and_other_bytes(self):
        s = session()
        original, write = s.read(STATE_ADDRESS, STATE_BYTES), s.write
        def failed(address, data):
            write(address, data)
            if len(s.writes) == 5:
                raise ValueError("threshold write failed after mutation")
        s.write = failed
        with self.assertRaises(ValueError) as caught:
            MountWalkFixture(s, s.subject, 0, 2, 2).run()
        self.assertEqual(s.read(STATE_ADDRESS, STATE_BYTES), original)
        self.assertIsNotNone(caught.exception.receipt["restoredOnError"])
        self.assertFalse(s.aborted)

    def test_named_turning_and_crash_sound_preserve_unrelated_bits(self):
        for turning in (None, 'free', 'locked'):
            for sound in (None, 'none', 'wall-hit'):
                s = session()
                original = s.read(STATE_ADDRESS, STATE_BYTES)
                expected = bytearray(original); expected[27] = 0
                if turning is not None:
                    expected[73] = (expected[73] & ~1) | int(turning == 'locked')
                if sound is not None:
                    expected[73] = (expected[73] & ~16) | (16 if sound == 'wall-hit' else 0)
                receipt = MountWalkFixture(s, s.subject, 0, turning=turning, crash_sound=sound).run()
                self.assertEqual(s.read(STATE_ADDRESS, STATE_BYTES), bytes(expected))
                self.assertEqual(receipt['before']['clock'], receipt['after']['clock'])
                for key, value in (('turning', turning), ('crashSound', sound)):
                    if value is None:self.assertNotIn(key, receipt)
                    else:self.assertEqual(receipt[key], value)
        for options in ({'turning':True}, {'turning':'invalid'}, {'crash_sound':1}, {'crash_sound':'invalid'}):
            s = session()
            with self.assertRaises(MountWalkFixtureError):MountWalkFixture(s, s.subject, 0, **options)
            self.assertFalse(s.writes)

    def test_options_write_failure_restores_full_state(self):
        s = session()
        original, write = s.read(STATE_ADDRESS, STATE_BYTES), s.write
        def failed(address, data):
            write(address, data)
            if len(s.writes) == 2:raise ValueError('options write failed after mutation')
        s.write = failed
        with self.assertRaises(ValueError) as caught:
            MountWalkFixture(s, s.subject, 0, turning='locked', crash_sound='wall-hit').run()
        self.assertEqual(s.read(STATE_ADDRESS, STATE_BYTES), original)
        self.assertIsNotNone(caught.exception.receipt['restoredOnError'])
        self.assertFalse(s.aborted)

    def test_named_options_command_schema(self):
        from tools.overworld.devtools_contract import validate_command
        s = session()
        args = dict(subject=s.subject, directionMode=0, turning='locked', crashSound='wall-hit')
        self.assertEqual(validate_command('mount-walk.configure', args), args)
        for key, value in (('turning', True), ('turning', 'turn'), ('crashSound', 1), ('crashSound', 'stomp')):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_command('mount-walk.configure', dict(args, **{key:value}))

    def test_invalid_arguments_and_private_mode_make_no_writes(self):
        for direction, timing in ((True, None), (3, None), (-1, None), (0, True), (0, 0), (0, 33)):
            s = session()
            with self.assertRaises(MountWalkFixtureError): MountWalkFixture(s, s.subject, direction, timing)
            self.assertFalse(s.writes)
        for fault in ("prepared", "bridge", "source"):
            s = session()
            if fault == "prepared": s.prepared = False
            elif fault == "bridge": s.native_bridge_active = True
            else: s.rom = ROOT / "test.nds"
            with self.assertRaises(MountWalkFixtureError): MountWalkFixture(s, s.subject, 1)
            self.assertFalse(s.writes)

    def test_stale_binding_and_busy_state_make_no_writes(self):
        for offset in (20, 80, 84, 86, 88, 90, 92, 93, 100, 102, 120, 122, 128, 148, 150, 180):
            s = session()
            s.put(STATE_ADDRESS + offset, bytes((s.read(STATE_ADDRESS + offset, 1)[0] ^ 1,)))
            with self.assertRaises((ValueError, KeyError)):
                MountWalkFixture(s, s.subject, 1).run()
            self.assertFalse(s.writes)

    def test_reset_readiness_is_used_without_reducer_dispatch(self):
        for fault in ("input", "staged", "policy", "anchor", "role"):
            s = session()
            if fault == "input": s.inputs["heldKeys"] = 1
            elif fault == "staged": s.actor["stagedMovement"]["idle"] = False
            elif fault == "policy": s.put(s.policy_address + 22, b"\x01")
            elif fault == "anchor": s.actor["engineIdentity"]["anchorInCurrentManager"] = False
            else: s.actor["role"] = "WILD"
            with self.assertRaises(ValueError): MountWalkFixture(s, s.subject, 1).run()
            self.assertFalse(s.writes)

    def test_partial_write_failure_rolls_back_with_receipt(self):
        s = session()
        original = s.read(STATE_ADDRESS, STATE_BYTES)
        write = s.write
        def failed(address, data):
            write(address, data)
            if len(s.writes) == 2: raise ValueError("write failed after mutation")
        s.write = failed
        f = MountWalkFixture(s, s.subject, 2, 1)
        with self.assertRaises(ValueError) as caught: f.run()
        self.assertEqual(s.read(STATE_ADDRESS, STATE_BYTES), original)
        self.assertIsNotNone(caught.exception.receipt["restoredOnError"])
        self.assertNotEqual(caught.exception.receipt["failedStateHex"], original.hex())
        self.assertFalse(s.aborted)

    def test_unverified_rollback_aborts_and_preserves_failure_receipt(self):
        for fault in ("clock", "unrelated-byte", "owner"):
            s = session()
            write = s.write
            def changed(address, data):
                write(address, data)
                if len(s.writes) == 1:
                    if fault == "clock": s.rt.EXECUTED_FRAME_COUNT += 1
                    elif fault == "owner": s.native_heap_generation += 1
                    else: s.put(STATE_ADDRESS + 10, b"\xff")
            s.write = changed
            with self.assertRaises(MountWalkFixtureError) as caught:
                MountWalkFixture(s, s.subject, 2).run()
            self.assertTrue(caught.exception.fatal)
            self.assertEqual(s.aborted, [caught.exception])
            self.assertIn("failure", caught.exception.receipt)

    def test_single_use_and_service_recheck(self):
        s = session()
        f = MountWalkFixture(s, s.subject, 1)
        f.run()
        with self.assertRaises(MountWalkFixtureError): f.run()
        s = session()
        f = MountWalkFixture(s, s.subject, 1)
        s.table = bytes(24)
        with self.assertRaises(ValueError): f.run()
        self.assertFalse(s.writes)


class IndependentAnchors(unittest.TestCase):
    def test_linked_package_callback_and_state_anchor(self):
        s = session()
        address = 0x023BB700
        code = bytes(36) + struct.pack("<I", STATE_ADDRESS)
        entry = struct.pack("<IHHI", 0x544E554D, 11, 32, address | 1) + bytes(20)
        s.rt.linked_symbol = lambda _, name: STATE_ADDRESS if name == "sOverworldMountState" else address | 1
        s.packaged_code = lambda a, n: entry if a == 0x023BB600 else code
        with patch("tools.overworld.devtools_runtime._elf_function_extent", return_value=(address, 40)), \
             patch("tools.overworld.devtools_runtime._elf_code", return_value=code):
            self.assertEqual(authenticate_mount(s)["beginSize"], 40)
            for fault in ("code", "entry", "state"):
                original = s.packaged_code
                if fault == "code": s.packaged_code = lambda a,n: entry if a == 0x023BB600 else bytes(40)
                elif fault == "entry": s.packaged_code = lambda a,n: bytes(32) if a == 0x023BB600 else code
                else: s.rt.linked_symbol = lambda _, name: STATE_ADDRESS + 4
                with self.assertRaises(MountWalkFixtureError): authenticate_mount(s)
                s.packaged_code = original

    def test_real_headers_compile_profile_and_arm_state_offsets(self):
        header = (ROOT / "include/overworld_mount.h").read_text()
        internal = (ROOT / "include/overworld_mount_internal.h").read_text()
        structs = ""
        for name, source in (("OverworldMountBinding", header), ("OverworldMountSnapshot", header),
                             ("OverworldMountRuntimeState", internal)):
            body = source.split("typedef struct " + name + " {", 1)[1].split("} " + name + ";", 1)[0]
            body = body.replace("FieldSystem *fieldSystem;", "u32 fieldSystem;").replace(
                "const OverworldWildSurfaceCatalog *surfaceCatalog;", "u32 surfaceCatalog;")
            structs += "typedef struct " + name + " {" + body + "} " + name + ";\n"
        code = '#include <stdio.h>\n#include <stddef.h>\n#include "overworld_behavior_resolver.h"\n'
        code += '#undef offsetof\n#define offsetof(t,m) __builtin_offsetof(t,m)\n' + structs
        pairs = [("OverworldWildBehaviorProfileData", x) for x in
                 ("hopAllowNonCardinal", "chillSpeed", "tilesToAccelerate", "maxWalkSpeed", "chillAction", "walkStompTime", "walkOptions")]
        pairs += [("OverworldMountRuntimeState", x) for x in
                  ("snapshot", "directionInputHeld", "presentationAttached", "pendingFieldStep",
                   "motionCooldown", "bufferedTogglePending", "motionStreamPreparing")]
        values = ["sizeof(OverworldMountRuntimeState)", "sizeof(OverworldWildBehaviorProfileData)"]
        values += ["offsetof(" + t + "," + f + ")" for t,f in pairs]
        values += ['(size_t)OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION',
                   '(size_t)OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_MASK']
        code += 'int main(void){printf("' + ' '.join(['%zu'] * len(values)) + '",' + ','.join(values) + ');}\n'
        with tempfile.TemporaryDirectory() as d:
            exe = str(Path(d) / "layout")
            compiled = subprocess.run(["cc", "-DOVERWORLD_BEHAVIOR_HOST", "-I", str(ROOT / "include"),
                "-x", "c", "-", "-o", exe], input=code, text=True, capture_output=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            self.assertEqual(subprocess.check_output([exe]).decode(), "184 72 19 7 50 51 12 70 65 8 120 122 128 148 150 180 1 16")
        self.assertIn("#define OW_WILD_BEHAVIOR_LOCOMOTION_WALK 1", (ROOT / "include/overworld_wild_behavior_data.h").read_text())
        self.assertIn("#define OVERWORLD_MOUNT_RUNTIME_STATE_ADDR 0x023BC744", internal)
        source = (ROOT / "src/overworld_mount_overlay/overworld_mount_overlay.c").read_text()
        self.assertIn("sOverworldMountState.snapshot.profile = profile->owner;", source)
        self.assertIn("sOverworldMountState.snapshot.binding = *binding;", source)


if __name__ == "__main__": unittest.main()
