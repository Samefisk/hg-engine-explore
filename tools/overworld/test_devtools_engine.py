"""Engine extraction, isolated startup and boot contracts; no emulator runs."""
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "tools/overworld/devtools_engine.py"
NATIVE = ROOT / "tools/overworld/devtools_native.py"
WORKER = ROOT / "scripts/overworld_devtools_worker.py"


def fresh_engine():
    spec = importlib.util.spec_from_file_location("fixture_engine", ENGINE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WildStagedMotionTests(unittest.TestCase):
    def fixture(self):
        engine = fresh_engine()
        engine.WILD_STATE = 0x02300000
        memory = {0x02310000 + index: value for index, value in enumerate(b"CODE")}
        class Values:
            def __getitem__(self, key):
                return bytes(memory.get(index, 0) for index in range(key.start, key.stop))
        emu = SimpleNamespace(memory=SimpleNamespace(unsigned=Values()))
        engine._wild_staged_layout = lambda: (engine.WILD_STATE, 0x02310000, b"CODE")
        return engine, emu, memory

    def test_staged_pending_or_distance_prevents_idle_and_reads_exact_slot(self):
        for slot in (0, 7, 9):
            engine, emu, memory = self.fixture()
            for pending, distance in ((0, 0), (1, 0), (0, 2), (2, 3)):
                memory[engine.WILD_STATE + 704 + slot] = pending
                memory[engine.WILD_STATE + 684 + slot] = distance
                memory[engine.WILD_STATE + slot * 20] = 4
                value = engine.wild_staged_motion(emu, slot)
                self.assertTrue(value["known"])
                self.assertEqual((value["pending"], value["distance"]), (pending, distance))
                self.assertEqual(value["idle"], pending == distance == 0)
                self.assertEqual(value["objectPointer"], 4)

    def test_bounds_missing_code_owner_and_partial_reads_are_unknown(self):
        engine, emu, memory = self.fixture()
        for slot in (-1, 10, True, None):
            self.assertFalse(engine.wild_staged_motion(emu, slot)["known"])
        memory[0x02310000] = 0
        self.assertIn("live-code", engine.wild_staged_motion(emu, 0)["reason"])
        engine._wild_staged_layout = lambda: (0x02300004, 0x02310000, b"CODE")
        self.assertIn("owner", engine.wild_staged_motion(emu, 0)["reason"])
        engine, emu, memory = self.fixture()
        class Short:
            def __getitem__(self, key):
                return b""
        emu.memory.unsigned = Short()
        self.assertIn("short-read", engine.wild_staged_motion(emu, 0)["reason"])

    def test_current_linked_layout_and_actual_arm_header(self):
        engine = fresh_engine()
        address, entry, code = engine._wild_staged_layout()
        self.assertGreater(address, 0x02000000)
        self.assertGreater(entry, 0x02000000)
        self.assertEqual(len(code), 116)
        compiler = shutil.which("arm-none-eabi-gcc") or "/opt/homebrew/bin/arm-none-eabi-gcc"
        source = '#include "overworld_wild_spawns_internal.h"\n#include <stddef.h>\n'
        source += '_Static_assert(sizeof(OverworldWildSpawnState)==964,"size");\n'
        source += '_Static_assert(OW_WILD_MAX_SPAWNS==10,"slots");\n'
        for name, offset in (("movementStagedHopPending", 704), ("movementStagedHopDistances", 684),
                             ("movementPendingDirections", 434), ("movementPendingDistances", 444),
                             ("pendingPersonality", 252), ("pendingSpecies", 256),
                             ("pendingSlot", 262), ("pendingMapGeneration", 948),
                             ("pendingEncounterGeneration", 950)):
            source += f'_Static_assert(offsetof(OverworldWildSpawnState,{name})=={offset},"{name}");\n'
        command = [compiler, "-x", "c", "-std=c11", "-mthumb", "-mcpu=arm946e-s", "-I" + str(ROOT / "include"), "-fsyntax-only", "-"]
        result = subprocess.run(command, input=source, text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        wrong = subprocess.run(command, input=source.replace("==704", "==703"), text=True, capture_output=True, timeout=20)
        self.assertNotEqual(wrong.returncode, 0)

    def test_unknown_linked_code_is_not_a_known_layout(self):
        engine, emu, _ = self.fixture()
        real = fresh_engine()
        real.WILD_STATE = engine.WILD_STATE
        with patch("tools.overworld.devtools_field_cleanup.symbol", side_effect=[
                (engine.WILD_STATE, 964, None), (0x02310000, 116, bytes(116))]), \
                patch.object(Path, "read_bytes", return_value=b"unused fixture"):
            value = real.wild_staged_motion(emu, 0)
        self.assertFalse(value["known"])
        self.assertEqual(value["reason"], "staged-motion-layout-code-unknown")

    def test_only_two_named_bl_relocations_may_change(self):
        from tools.overworld.devtools_field_cleanup import symbol
        image = (ROOT / "build/overworld_wild_spawns_overlay_linked.o").read_bytes()
        original_entry, _, original_code = symbol(image,
            "OverworldWildSpawns_ClearStagedHopTargetLocal", 2, expected_size=116)
        names = ("OverworldWildSpawns_ClearStagedHopMovementListTask",
                 "OverworldWildSpawns_ClearCustomJumpLocal")
        originals = [symbol(image, name, 2)[0] for name in names]
        for relocation in (0, 0x2000, -0x4000):
            for fault in (None, "first-target", "second-target", "opcode", "other-byte"):
                engine = fresh_engine()
                entry = original_entry + relocation
                code = bytearray(original_code)
                targets = [originals[0] - relocation, originals[1] + relocation // 2]
                for i, offset in enumerate((14, 22)):
                    displacement = targets[i] - (entry + offset + 4)
                    self.assertTrue(-0x400000 <= displacement < 0x400000)
                    bits = displacement & 0x7FFFFF
                    struct.pack_into("<HH", code, offset,
                                     0xF000 | bits >> 12, 0xF800 | (bits >> 1 & 0x7FF))
                if fault == "first-target": targets[0] += 2
                elif fault == "second-target": targets[1] += 2
                elif fault == "opcode": code[17] ^= 0x08
                elif fault == "other-byte": code[40] ^= 1
                table = {
                    "sOverworldWildSpawnState": (0x02300000, 964, None),
                    "OverworldWildSpawns_ClearStagedHopTargetLocal": (entry, 116, bytes(code)),
                    names[0]: (targets[0], 2, b"\x70\x47"),
                    names[1]: (targets[1], 2, b"\x70\x47"),
                }
                with self.subTest(relocation=relocation, fault=fault), \
                     patch("tools.overworld.devtools_field_cleanup.symbol", side_effect=lambda _, name, *a, **k: table[name]), \
                     patch.object(Path, "read_bytes", return_value=b"fixture"):
                    if fault is None:
                        self.assertEqual(engine._wild_staged_layout(), (0x02300000, entry, bytes(code)))
                    else:
                        with self.assertRaisesRegex(ValueError, "staged-motion-layout-"):
                            engine._wild_staged_layout()


class EngineDependencyTests(unittest.TestCase):
    def test_runtime_dependency_closure_has_no_legacy_driver(self):
        engine = fresh_engine()
        runtime = ROOT / "tools/overworld/devtools_runtime.py"
        observer = ROOT / "tools/overworld/devtools_observer.py"
        trees = [ast.parse(path.read_text()) for path in (runtime, observer)]
        requested = {node.attr for tree in trees for node in ast.walk(tree)
                     if isinstance(node, ast.Attribute) and (
                         isinstance(node.value, ast.Name) and node.value.id == "rt"
                         or isinstance(node.value, ast.Attribute) and node.value.attr == "rt")}
        # The fixed native-call bridge also uses getattr(rt, table). Include
        # that real data-driven dependency instead of trusting direct syntax.
        from tools.overworld.devtools_runtime import ELF_FILES, LINKED_CALLS
        requested.update(ELF_FILES)
        requested.update(value[0] for value in LINKED_CALLS.values())
        self.assertGreater(len(requested), 20, "runtime dependency scan is empty or incomplete")
        self.assertEqual(sorted(name for name in requested if not hasattr(engine, name)), [])
        for path in (ENGINE, NATIVE, WORKER, runtime, observer):
            source = path.read_text()
            for forbidden in ("verify_overworld_walk_runtime", "headless-overworld-test",
                              "runtime_normal_play", "runtime_proof_registry",
                              "verify_pokemon_move_history_party_integrity"):
                self.assertNotIn(forbidden, source, str(path))
        for path in (ENGINE, NATIVE):
            tree = ast.parse(path.read_text())
            definitions = [node.name for node in tree.body
                           if isinstance(node, (ast.FunctionDef, ast.ClassDef))]
            self.assertFalse(any(name.startswith(("scenario_", "fault_inject_"))
                                 for name in definitions), definitions)
            self.assertFalse(any(isinstance(node, ast.ImportFrom)
                                 and node.module and node.module.startswith("scripts.")
                                 for node in ast.walk(tree)))
        self.assertIsNone(engine.h)
        self.assertIsNone(engine.ACTOR_DESCRIPTOR)

    def test_initialization_only_loads_needed_symbols_and_counts_native_cycles(self):
        engine = fresh_engine()
        calls = []
        native = SimpleNamespace(ISOLATED_STARTUP_AUTHENTICATED=True,
                                 cycle=lambda *args: calls.append(args))
        mount = {"gFieldSysPtr": 0x02100000, "sOverworldWildSpawnState": 0x02300000}
        selector = {"sFollowerRecall": 0x02310000, "sFollowerSelectorInputState": 0x02320000}
        descriptor = {"publicLayouts": {"actorState": {"size": 80}}}
        with patch.object(engine, "linked_symbols", side_effect=[mount, selector, {}, {}, {}]) as symbols, \
                patch("tools.overworld.actor_probe.load_debug_descriptor", return_value=descriptor):
            engine.initialize(native)
        self.assertEqual([call.args[0].name for call in symbols.call_args_list],
                         ["overworld_mount_overlay_linked.o", "overworld_follower_selector_overlay_linked.o",
                          "overworld_wild_spawns_overlay_linked.o", "pokemon_move_history_overlay_linked.o",
                          "pokemon_move_history_task6_overlay_linked.o"])
        self.assertEqual(engine.ACTOR_STATE_SIZE, 80)
        self.assertEqual(engine.SELECTOR_HIGHLIGHT, 0x02310063)
        self.assertEqual(engine.G_FIELD_SYS_PTR, 0x02100000)
        self.assertEqual(engine.WILD_STATE, 0x02300000)
        self.assertEqual(engine.SELECTOR_STATE, 0x02320000)
        self.assertEqual(calls, [], "initializing transport must not create or cycle a core")
        native.cycle("fake-core", 3, 4)
        self.assertEqual(calls, [("fake-core", 3, 4)])
        self.assertEqual(engine.EXECUTED_FRAME_COUNT, 3)
        with self.assertRaisesRegex(RuntimeError, "already initialized"):
            engine.initialize(native)

    def test_missing_authentication_rejects_before_symbol_or_native_access(self):
        engine = fresh_engine()
        with patch.object(engine, "linked_symbols") as symbols:
            with self.assertRaisesRegex(RuntimeError, "did not authenticate"):
                engine.initialize(SimpleNamespace())
        symbols.assert_not_called()

    def test_party_permutations_match_vanilla_and_keep_checksum_rejection(self):
        from tools.overworld.devtools_runtime import DevtoolsFailure, _crypt, decode_party
        path = ROOT / ".codex-reference/pokeheartgold/src/pokemon.c"
        if not path.is_file():
            self.skipTest("optional local vanilla source is not installed")
        source = path.read_text().split("PokemonDataBlock *GetSubstruct(", 1)[1]
        table = source.split("static const u8 offsets[32][4] = {", 1)[1].split("};", 1)[0]
        reference = tuple(tuple(int(value, 16) for value in re.findall(r"0x[0-9A-Fa-f]+", row))
                          for row in re.findall(r"\{([^{}]+)\}", table))
        offsets = fresh_engine().SUBSTRUCT_OFFSETS
        self.assertEqual(len(reference), 32)
        self.assertEqual(offsets, reference)
        for permutation, (a, b, _c, _d) in enumerate(reference):
            with self.subTest(permutation=permutation):
                pid = permutation << 13 | 123
                box = bytearray(128)
                struct.pack_into("<H", box, a, 155)
                struct.pack_into("<4H", box, b, 33, 45, 52, 0)
                box[b + 24] = 3 << 3
                checksum = sum(struct.unpack("<64H", box)) & 0xFFFF
                party = bytearray(100)
                party[4] = 12
                struct.pack_into("<HH", party, 6, 20, 30)
                record = struct.pack("<IHH", pid, 0, checksum) + _crypt(box, checksum) + _crypt(party, pid)
                data = struct.pack("<II", 6, 1) + record + bytes(5 * 236)
                decoded = decode_party(data, offsets)[0]
                self.assertEqual((decoded["species"], decoded["personality"], decoded["form"], decoded["level"]),
                                 (155, pid, 3, 12))
                self.assertEqual(decoded["moves"], [33, 45, 52, 0])
                self.assertEqual((decoded["hp"], decoded["maxHp"]), (20, 30))
                bad = bytearray(data)
                bad[24] ^= 1
                with self.assertRaisesRegex(DevtoolsFailure, "checksum"):
                    decode_party(bad, offsets)


# Import authentication does not load a native library or create a core.
# Authentication itself is the real source entry path.
AUTH_PROBE = r'''
import importlib.util, json, sys, types
if sys.argv[2] == "extra-path": sys.path.append("/unexpected-startup-path")
if sys.argv[2] == "site": sys.modules["site"] = types.ModuleType("site")
if sys.argv[2] == "wrong-interpreter": sys.executable = "/not-the-repository/bin/python3"
spec = importlib.util.spec_from_file_location("isolated_native_fixture", sys.argv[1])
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
print(json.dumps({"authenticated": native.ISOLATED_STARTUP_AUTHENTICATED,
                  "repo": str(native.REPO_ROOT), "keys": len(native.KEYS),
                  "path": sys.path}))
'''


class ObjectLookupReceiptTests(unittest.TestCase):
    """Read-only stock lookup semantics, with no emulator or game writes."""

    def fixture(self, rows, *, count=64, objects=0x02210000):
        engine = fresh_engine()
        engine.G_FIELD_SYS_PTR = 0x02100000
        manager, field = 0x02200000, 0x02110000
        own = objects + 17 * 0x12C
        values = {engine.G_FIELD_SYS_PTR: field, field + 0x3C: manager,
                  field + engine.FIELD_LOCATION_OFFSET: 0x02120000,
                  0x02120000: 33, manager + 4: count,
                  manager + 0x124: objects}
        for index, flags, object_id, map_id, script in rows:
            pointer = objects + index * 0x12C
            values.update({pointer: flags, pointer + 8: object_id,
                           pointer + 12: map_id, pointer + 32: script,
                           pointer + 0xB4: manager})
        reads = []

        def read(_emu, address, size=4):
            reads.append((address, size))
            return values.get(address, 0)

        engine.unsigned = read
        engine.wild_spawn = lambda _emu, _slot: {
            "object": own, "object_id": 0xE7, "map_id": 33,
            "encounter_generation": 2}
        return engine, reads, values, own

    def test_earlier_duplicate_exposes_stock_first_match_without_changing_identity(self):
        engine, reads, _values, own = self.fixture(
            [(2, 1, 0xE7, 33, 2074), (17, 1, 0xE7, 33, 2074)])
        result = engine.live_wild_object_identity(None, 7)
        lookup = result["id_lookup"]
        self.assertEqual(lookup["status"], "complete")
        self.assertEqual(lookup["first_active_pointer"], own - 15 * 0x12C)
        self.assertEqual(lookup["first_active_index"], 2)
        self.assertEqual(lookup["eligible_count"], 2)
        self.assertFalse(lookup["pointer_matches"])
        self.assertTrue(result["active"])
        self.assertTrue(result["in_manager"], "diagnostic must not rewrite prior identity fields")
        self.assertEqual([row["manager_index"] for row in lookup["matching_objects"]], [2, 17])
        self.assertLess(len(reads), 130, "do not copy all 19 KiB of object storage per actor")

    def test_stock_ignores_inactive_and_flag25_but_not_script_or_map(self):
        engine, _reads, _values, own = self.fixture([
            (0, 0, 0xE7, 33, 2074), (1, 1 | (1 << 25), 0xE7, 33, 2074),
            (2, 1, 0xE7, 99, 18), (17, 1, 0xE7, 33, 2074)])
        lookup = engine.live_wild_object_identity(None, 7)["id_lookup"]
        self.assertEqual(lookup["first_active_index"], 2)
        self.assertEqual(lookup["eligible_count"], 2)
        rows = lookup["matching_objects"]
        self.assertEqual([row["lookup_eligible"] for row in rows], [False, False, True, True])
        self.assertEqual((rows[2]["object_map_id"], rows[2]["script_id"]), (99, 18))
        self.assertEqual(rows[3]["pointer"], own)

    def test_single_live_match_and_no_match_have_distinct_results(self):
        for rows, expected in (([(17, 1, 0xE7, 33, 2074)], True), ([], False)):
            with self.subTest(rows=rows):
                engine, _reads, _values, own = self.fixture(rows)
                lookup = engine.live_wild_object_identity(None, 7)["id_lookup"]
                self.assertEqual(lookup["pointer_matches"], expected)
                self.assertEqual(lookup["first_active_pointer"], own if expected else 0)
                self.assertEqual(lookup["first_active_index"], 17 if expected else None)

    def test_invalid_capacity_or_span_never_scans_unbounded_storage(self):
        for count, objects in ((0, 0x02210000), (65, 0x02210000),
                               (0xFFFFFFFF, 0x02210000), (64, 0x023FF000),
                               (64, 0x02210001), (64, 0)):
            with self.subTest(count=count, objects=objects):
                engine, reads, _values, _own = self.fixture([], count=count, objects=objects)
                lookup = engine.live_wild_object_identity(None, 7)["id_lookup"]
                self.assertEqual(lookup["status"], "invalid-manager-bounds")
                self.assertIsNone(lookup["pointer_matches"])
                self.assertEqual(lookup["matching_objects"], [])
                self.assertLess(len(reads), 20)

    def test_partial_read_failure_is_not_a_complete_or_empty_lookup(self):
        engine, _reads, _values, _own = self.fixture([(17, 1, 0xE7, 33, 2074)])
        original = engine.unsigned

        def read(emu, address, size=4):
            if address == 0x02210000 + 40 * 0x12C + 8:
                raise RuntimeError("test read failed")
            return original(emu, address, size)

        engine.unsigned = read
        lookup = engine.live_wild_object_identity(None, 7)["id_lookup"]
        self.assertEqual(lookup["status"], "read-error")
        self.assertIsNone(lookup["pointer_matches"])
        self.assertIsNone(lookup["eligible_count"])
        self.assertIn("test read failed", lookup["error"])

    def test_paused_id_cache_scans_once_preserving_complete_receipts(self):
        engine,reads,values,own=self.fixture([
            (0,0,0xE7,33,2074),(1,1|(1<<25),0xE7,33,2074),
            (2,1,0xE7,99,18),(17,1,0xE7,33,2074),(3,1,0xE6,33,2074)])
        original=engine.wild_spawn
        engine.wild_spawn=lambda emu,slot: original(emu,slot) if slot==7 else {
            **original(emu,slot),"object":0x02210000+3*0x12C,"object_id":0xE6}
        expected=[engine.live_wild_object_identity(None,slot) for slot in (7,3)]
        reads.clear();cache={}
        actual=[engine.live_wild_object_identity(None,slot,id_scan_cache=cache) for slot in (7,3)]
        self.assertEqual(actual,expected)
        self.assertEqual(reads.count((0x02210000+50*0x12C+8,4)),1)
        self.assertEqual(len(cache),1);self.assertIsInstance(next(iter(cache.values())),tuple)
        self.assertEqual(len(next(iter(cache.values()))),64)
        values[own]=1|(1<<25);values[own+12]=55;values[own+32]=9
        changed=engine.live_wild_object_identity(None,7,id_scan_cache=cache)
        self.assertTrue(changed["id_lookup"]["matching_objects"][-1]["flag25"])
        self.assertEqual((changed["object_map_id"],changed["script_id"]),(55,9))
        prior_spawn=engine.wild_spawn
        engine.wild_spawn=lambda emu,slot:{**prior_spawn(emu,slot),"map_id":77,"encounter_generation":3}
        changed=engine.live_wild_object_identity(None,7,id_scan_cache=cache)
        self.assertEqual((changed["spawn_map_id"],changed["encounter_generation"]),(77,3))
        self.assertEqual(reads.count((0x02210000+50*0x12C+8,4)),1)

    def test_fresh_cache_and_each_manager_key_change_reread_ids(self):
        engine,reads,values,own=self.fixture([(17,1,0xE7,33,2074)])
        cache={};engine.live_wild_object_identity(None,7,id_scan_cache=cache)
        values[0x02210000+5*0x12C+8]=0xE7;values[0x02210000+5*0x12C]=1
        fresh=engine.live_wild_object_identity(None,7,id_scan_cache={})
        self.assertEqual(fresh["id_lookup"]["first_active_index"],5)
        # Same paused cache cannot be reused for another field/manager/span.
        for field,manager,objects,count in ((0x02110004,0x02200000,0x02210000,64),
                (0x02110004,0x02200010,0x02210000,64),
                (0x02110004,0x02200010,0x02220000,64),
                (0x02110004,0x02200010,0x02220000,63)):
            values.update({engine.G_FIELD_SYS_PTR:field,field+0x3C:manager,manager+4:count,manager+0x124:objects})
            reads.clear();engine.live_wild_object_identity(None,7,id_scan_cache=cache)
            self.assertIn((objects+50*0x12C+8,4),reads)

    def test_partial_or_invalid_id_scan_does_not_publish_cache(self):
        engine,reads,values,own=self.fixture([(17,1,0xE7,33,2074)])
        original=engine.unsigned;cache={}
        def read(emu,address,size=4):
            if address==0x02210000+40*0x12C+8:raise RuntimeError("partial ID scan")
            return original(emu,address,size)
        engine.unsigned=read
        result=engine.live_wild_object_identity(None,7,id_scan_cache=cache)
        self.assertEqual(result["id_lookup"]["status"],"read-error");self.assertEqual(cache,{})
        engine.unsigned=original;values[0x02200000+4]=65
        result=engine.live_wild_object_identity(None,7,id_scan_cache=cache)
        self.assertEqual(result["id_lookup"]["status"],"invalid-manager-bounds");self.assertEqual(cache,{})


class NativeStartupTests(unittest.TestCase):
    def probe(self, mode="normal", flags=("-I", "-S", "-B", "-X", "pycache_prefix=/dev/null")):
        python = ROOT / ".venv/bin/python3"
        self.assertTrue(python.is_file(), "the repository Python is required for startup contract checks")
        return subprocess.run([str(python), *flags, "-c", AUTH_PROBE, str(NATIVE), mode],
                              capture_output=True, text=True, timeout=15)

    def test_exact_isolated_startup_authenticates_without_loading_a_core(self):
        result = self.probe()
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertTrue(value["authenticated"])
        self.assertEqual(value["repo"], str(ROOT))
        self.assertEqual(value["keys"], 12)
        self.assertNotIn(str(ROOT), value["path"], "repo path must be added only AFTER native authentication")

    def test_invalid_startup_controls(self):
        for mode in ("extra-path", "site", "wrong-interpreter"):
            with self.subTest(mode=mode):
                result = self.probe(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("requires exact repository Python", result.stderr)
        result = self.probe(flags=("-B", "-X", "pycache_prefix=/dev/null"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires exact repository Python", result.stderr)


class BootTests(unittest.TestCase):
    def fixture(self, *, field_ready=True, clock_moves=True):
        engine = fresh_engine()
        engine.G_FIELD_SYS_PTR, engine.WILD_STATE = 0x1000, 0x2000
        engine.ACTOR_DESCRIPTOR = {"state": {"address": 0x3000}}
        values = {0x1000: 0x4000 if field_ready else 0,
                  0x20E0: 0x4000 if field_ready else 0, 0x20E4: 0x5000 if field_ready else 0,
                  0x3008: 1, 0x4000: 0x6000, 0x4010: 0x7000, 0x406C: 1,
                  0x6008: 1, 0x7004: 0x02012345, 0x7008: 3}
        calls = []

        def cycle(_emu, frames, mask=None):
            calls.append(("cycle", frames, mask))
            if clock_moves:
                values[0x3008] += frames

        def import_save(path, force_size):
            calls.append(("import", Path(path).read_bytes(), force_size))

        engine.h = SimpleNamespace(cycle=cycle,
            tap_key=lambda _emu, key, hold, release: calls.append(("tap", key, hold, release)),
            extract_raw_save=lambda path: path.read_bytes().split(b"FOOTER", 1)[0])
        engine.unsigned = lambda _emu, address, size=4: values.get(address, 0)
        emu = SimpleNamespace(volume_set=lambda value: calls.append(("volume", value)),
                             open=lambda path: calls.append(("open", path)),
                             backup=SimpleNamespace(import_file=import_save))
        return engine, emu, calls

    def test_save_import_hook_order_and_observed_clock_readiness(self):
        for dsv in (False, True):
            with self.subTest(dsv=dsv), tempfile.TemporaryDirectory(prefix="engine-boot-") as directory:
                save = Path(directory) / ("fixture.dsv" if dsv else "fixture.sav")
                before = b"source-save" + (b"FOOTERunchanged" if dsv else b"")
                save.write_bytes(before)
                engine, emu, calls = self.fixture()
                engine.boot(emu, save, dsv, on_rom_open=lambda: calls.append(("hook",)))
                self.assertEqual(calls[:4], [("volume", 0), ("open", str(engine.ROM)),
                                           ("hook",), ("import", b"source-save", 0)])
                self.assertEqual([call for call in calls if call[0] == "tap"], [("tap", "A", 2, 34)])
                self.assertEqual(calls[-1], ("cycle", 1, 0), "ready field is not enough; actor clock must advance")
                self.assertEqual(save.read_bytes(), before)

    def test_missing_field_and_paused_clock_are_bounded_failures(self):
        for ready, message, expected_taps in ((False, "input limit", 8), (True, "actor clock stalled", 1)):
            with self.subTest(field_ready=ready), tempfile.TemporaryDirectory(prefix="engine-boot-") as directory:
                save = Path(directory) / "fixture.sav"
                save.write_bytes(b"save")
                engine, emu, calls = self.fixture(field_ready=ready, clock_moves=False)
                with self.assertRaisesRegex(RuntimeError, message) as error:
                    engine.boot(emu, save, False)
                taps = [call for call in calls if call[0] == "tap"]
                self.assertEqual(len(taps), expected_taps)
                if ready:
                    self.assertEqual([call[1] for call in taps], ["A"])
                    for evidence in ("field=0x00004000", "taskman=0x00007000",
                                     "taskFunction=0x02012345", "taskState=3", "isPaused=1",
                                     "fieldReady=1", "actorFrameBefore=1", "actorFrameAfter=1",
                                     "boundary=paused-native-cycle-end"):
                        self.assertIn(evidence, str(error.exception))
                self.assertLess(sum(call[1] for call in calls if call[0] == "cycle"), 4000)
                self.assertEqual(save.read_bytes(), b"save")

    def test_stalled_field_never_heals_with_menu_input(self):
        with tempfile.TemporaryDirectory(prefix="engine-boot-") as directory:
            save = Path(directory) / "fixture.sav"
            save.write_bytes(b"save")
            engine, emu, calls = self.fixture(clock_moves=False)
            old_read = engine.unsigned
            healed = False

            def tap(_emu, key, hold, release):
                nonlocal healed
                calls.append(("tap", key, hold, release))
                if key in ("B", "X"):
                    healed = True

            engine.h.tap_key = tap
            engine.unsigned = lambda emu, address, size=4: (
                2 if healed and address == 0x3008 else old_read(emu, address, size))
            with self.assertRaisesRegex(RuntimeError, "actor clock stalled"):
                engine.boot(emu, save, False)
            self.assertFalse(healed)
            self.assertEqual([call[1] for call in calls if call[0] == "tap"], ["A"])

    def test_failed_diagnostic_read_keeps_original_stall_failure(self):
        with tempfile.TemporaryDirectory(prefix="engine-boot-") as directory:
            save = Path(directory) / "fixture.sav"
            save.write_bytes(b"save")
            engine, emu, calls = self.fixture(clock_moves=False)
            old_read = engine.unsigned

            def read(emu, address, size=4):
                if address == 0x6008:
                    raise ValueError("pause read unavailable")
                return old_read(emu, address, size)

            engine.unsigned = read
            with self.assertRaisesRegex(RuntimeError, "actor clock stalled") as error:
                engine.boot(emu, save, False)
            self.assertIn("diagnosticReadError=pause read unavailable", str(error.exception))
            self.assertEqual([call[1] for call in calls if call[0] == "tap"], ["A"])


if __name__ == "__main__":
    unittest.main()
