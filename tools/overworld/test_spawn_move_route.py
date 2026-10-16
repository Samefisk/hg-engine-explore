"""Actual-C Move entry route, END/stall, START order and final origin gates.

Host checks use the existing Pickup/Cargo fixtures. They do not prove native
layout, available heap, game loading, or frame pacing.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest
from scripts import verify_overworld_spawn_move_entry as host

PRODUCT_ROOT = host.ROOT


class SpawnMoveRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='ow-spawn-move-route-')
        cls.work = Path(cls.tmp.name)
        cls.binaries = {}
        builders = {'route': host.route_program, 'guided': host.guided_program, 'origin': host.origin_program}
        for name, builder in builders.items():
            cls.binaries[name] = host.compile_program(cls.work / name, builder(PRODUCT_ROOT), PRODUCT_ROOT, linked=name != 'origin')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_binary(self, binary):
        return subprocess.run([str(binary)], cwd=binary.parent, capture_output=True, text=True)

    def test_directed_route_bounded_reads_actual_end_stall_and_complete_96_step_witness(self):
        result = self.run_binary(self.binaries['route'])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('actual Entry route/ledger/full-handle/commit/offscreen controls PASS', result.stdout)
        self.assertIn('actual96-step witness bound: exact96 copied;97 rejected without partial output PASS', result.stdout)

    def test_actual_start_caller_credits_async_and_zero_time_teleport_end(self):
        result = self.run_binary(self.binaries['guided'])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('failed untouched; asynchronous END waits; synchronous Teleport END credited; stale sequence rejects PASS', result.stdout)

    def test_ready_origin_is_current_before_slot_prepare_or_visible_constructor(self):
        result = self.run_binary(self.binaries['origin'])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('moved Player rejects before PrepareSlot; occupied/null origin rejects;13/11 boundary admits; normal spawn unchanged PASS', result.stdout)

    def test_compact_witness_keeps_tags_endpoints_and_all_admissible_slots(self):
        route = self.run_binary(self.binaries['route'])
        self.assertEqual(route.returncode, 0, route.stdout + route.stderr)
        self.assertIn('72 forward/reverse native tag and full-height/surface copies PASS', route.stdout)
        self.assertIn('28 directed Walk/Hop/Ledge/Teleport edges', route.stdout)
        self.assertIn('height/surface rejects and8 pre-cast bounds PASS', route.stdout)
        guided = self.run_binary(self.binaries['guided'])
        self.assertEqual(guided.returncode, 0, guided.stdout + guided.stderr)
        self.assertIn('all9 admissible Wild slots including8/9; follower7 rejected', guided.stdout)
        self.assertIn('full ADOPT/arrival/RETIRE;96 endpoints and tags retained PASS', guided.stdout)

    def test_copied_compact_witness_regressions_reject(self):
        entry = 'lib/overworld/overworld_entry_route.c'
        copier = 'lib/overworld/overworld_pickup_route.c'
        faults = {
            'narrow-before-bound': (entry,
                'if ((((u32)dx + 32768u) | ((u32)dy + 32768u)) > 65535u)',
                'if (0)', 'reads==before && !memcmp(&prior,&receipt'),
            'lose-native-kind': (copier,
                '(tag&~7u)|opposite[tag&7]', 'opposite[tag&7]', 'got==tag'),
            'lose-forward-direction': (copier,
                '(tag&~7u)|opposite[tag&7]', 'tag', 'path.edgeTags[i]==3'),
            'partial-capacity-output': (copier,
                'node=s->goalNode;\n  /* Count and validate first.',
                'node=s->goalNode;edgeTags[0]=0xDEAD;\n  /* Count and validate first.',
                '!memcmp(&path.edgeTags,&saved.edgeTags'),
        }
        for fault, (relative, old, new, reason) in faults.items():
            with self.subTest(control=fault):
                copied = self.work / (fault + '-product')
                for owned in ('include/overworld_entry_route.h', entry,
                              'include/overworld_pickup_route.h', copier):
                    target = copied / owned
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source = host.product(PRODUCT_ROOT, owned)
                    if owned == relative:
                        source = host.mutate(source, old, new)
                    target.write_text(source)
                binary = host.compile_program(self.work / fault, host.route_program(copied), copied, linked=True)
                result = self.run_binary(binary)
                self.assertNotEqual(result.returncode, 0, 'known-bad compact witness passed: ' + fault)
                self.assertIn(reason, result.stderr)

    def test_copied_route_regressions_fail_for_the_named_rule(self):
        reasons = {'height-budget': 'reads-before<=8',
                   'same-commit': '!OverworldEntryRoute_Confirm',
                   'on-screen': '!OverworldEntryRoute_IdleStall',
                   'proof-stall-reset': 'path.noProgress==73'}
        for fault, reason in reasons.items():
            with self.subTest(control=fault):
                binary = host.compile_program(self.work / fault, host.route_program(PRODUCT_ROOT, fault), PRODUCT_ROOT, linked=True)
                result = self.run_binary(binary)
                self.assertNotEqual(result.returncode, 0, 'known-bad copied route passed: ' + fault)
                self.assertIn(reason, result.stderr)

    def test_copied_post_start_sequence_cannot_credit_zero_time_end(self):
        binary = host.compile_program(self.work / 'post-start-sequence', host.guided_program(PRODUCT_ROOT, 'post-start-sequence'), PRODUCT_ROOT, linked=True)
        result = self.run_binary(binary)
        self.assertNotEqual(result.returncode, 0, 'known-bad post-START sequence passed')
        self.assertIn('path->acceptedSequence==10', result.stderr)

    def test_copied_queue_order_and_full_guard_regressions_reject(self):
        for fault,reason in [('consume-order','queue not consumed before guard'),('guard-tail','!constructors && !placements && !spawns.justSpawned')]:
            with self.subTest(control=fault):
                binary=host.compile_program(self.work/fault,host.guided_program(PRODUCT_ROOT,fault),PRODUCT_ROOT,linked=True)
                result=self.run_binary(binary)
                self.assertNotEqual(result.returncode,0,'known-bad queue rule passed: '+fault)
                self.assertIn(reason,result.stderr)

    def test_copied_old_ready_origin_cannot_create_after_player_moves(self):
        binary = host.compile_program(self.work / 'stale-ready-origin', host.origin_program(PRODUCT_ROOT, 'stale-ready-origin'), PRODUCT_ROOT)
        result = self.run_binary(binary)
        self.assertNotEqual(result.returncode, 0, 'known-bad stale READY origin passed')
        self.assertIn('!OverworldWildSpawns_SpawnPreparedEncounter', result.stderr)


if __name__ == '__main__':
    unittest.main()
