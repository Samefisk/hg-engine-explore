"""Installed, read-only native chain probes; synthetic memory is not game proof."""
from copy import deepcopy
from pathlib import Path
import os
import re
import shutil
import struct
import subprocess
import tempfile
import unittest

from tools.overworld.devtools_observer import NativeObservation, MOTION_DECISIONS, CHAIN_OUTCOMES
from tools.overworld.test_devtools_observer import Fixture


class RepositionFixture(Fixture):
    def __init__(self, directory):
        super().__init__(directory)
        self.observer.close()
        self.actor.update(presentationAttached=True, inputOwnership=0, reservationId=0)
        self.source = dict(object=0x02210000, species=165, personality=99, form=0, level=5,
                           active=1, encounter_generation=4, map_id=self.map_id, object_id=0xE0)
        self.engine = dict(pointer=self.source['object'], in_manager=True, active=True,
                           current_manager=0x02211000, object_manager=0x02211000,
                           manager_index=2, object_id=0xE0, object_map_id=self.map_id, script_id=2074,
                           id_lookup=dict(status='complete', pointer_matches=True, eligible_count=1))
        self.rt.wild_spawn = lambda _emu, _slot: deepcopy(self.source)
        self.rt.live_wild_object_identity = lambda _emu, _slot: deepcopy(self.engine)
        self.run = self.symbols['OverworldWildSpawns_RunChainReposition']
        self.timed = self.symbols['OverworldWildSpawns_StartPreparedCustomJumpCommandTimed']
        self.plan_caller = self.symbols['ActorSystem_RequestMotion']
        self.landing_caller = self.symbols['OverworldWildSpawns_ClassifyBehaviorHopLandingTile']
        # A next-symbol bound for the last fixture function, as in the real nm map.
        self.symbols['fixture_end'] = max(self.symbols.values()) + 64
        regions = []
        for address, data in self.code_regions:
            if address in (self.run, self.timed, self.plan_caller, self.landing_caller):
                data = bytearray(data)
                for offset in (8, 16):
                    data[offset:offset + 4] = struct.pack('<HH', 0xF000, 0xF800)
                data = bytes(data)
                self.put(address, data)
            regions.append((address, data))
        self.code_regions = regions
        self.profile, self.lane = 0x02226000, 0x02227000
        self.put(self.lane, bytes(range(72)))
        self.observer = NativeObservation(self, self.hooks, lambda path, address, size: self.read(address, size))
        self.observer.install()

    def begin(self, *, encoded=0x20):
        self.put(0x027E3800, struct.pack('<I', 0x027E3820))
        self.put(0x027E3820, bytes((encoded, 0, 0, 8)))
        self.enter('chain-reposition-attempt', r0=self.rt.WILD_STATE, r1=0,
                   r2=self.profile, r3=encoded)

    def landing(self, accepted, *, target=(552, 383), overrides=None, complete=True):
        self.put(0x027E37A0, struct.pack('<4i', *target, *target))
        args = dict(r0=self.rt.WILD_STATE, r1=0, r2=0x02231000, r3=1)
        args.update(overrides or {})
        self.enter('chain-landing', sp=0x027E37A0, lr=self.run + 13, **args)
        if complete and self.hooks.error is None:
            if accepted:
                self.detail('surface', False, target=target)
                self.detail('terrain', True, target=target)
                self.detail('objects', False, target=target)
            self.returned(0 if accepted else 2, sp=0x027E37A0, address=self.run + 12)

    def detail(self, kind, result, *, target=(552, 383), hit=(-4096, 12, 2, 4), complete=True):
        args = dict(r0=0x02231000)
        if kind == 'surface':
            args.update(r1=target[0], r2=target[1], r3=0x027E3600)
            self.put(0x027E3600, struct.pack('<iHBB', *hit))
        elif kind == 'terrain':
            args.update(r1=1, r2=2, r3=target[0])
            self.put(0x027E3700, struct.pack('<i', target[1]))
        elif kind == 'objects':
            args.update(r1=target[0], r2=target[1])
        elif kind == 'nonplayer':
            args.update(r1=self.source['object'], r2=target[0], r3=target[1])
        else:
            args.update(r1=self.source['object'], r2=1, r3=target[0])
            self.put(0x027E3700, struct.pack('<ii', target[1], hit[0]))
        self.enter('chain-landing-' + kind, sp=0x027E3700, lr=self.landing_caller + 13, **args)
        if complete and self.hooks.error is None:
            self.returned(int(result), sp=0x027E3700, address=self.landing_caller + 12)

    def start(self, *, target=(552, 383), overrides=None):
        self.put(0x027E37A0, struct.pack('<IIiiIII', 4, 2, *target, self.profile, 1, 0))
        args = dict(r0=self.rt.WILD_STATE, r1=0x02231000, r2=0, r3=self.source['object'])
        args.update(overrides or {})
        self.enter('chain-prepared-start', sp=0x027E37A0, lr=self.run + 21, **args)

    def request(self, decision, *, overrides=None):
        start = self.observer.reposition_contexts[-1]['_activeStart']
        if not start['hopPlans']:
            self.plan(0, target=start['target'])
        self.put(0x027E3600, struct.pack('<7I', 0, 0, 2, 8, 0, 0, 3))
        args = dict(r0=self.rt.WILD_STATE, r1=0, r2=self.lane, r3=5)
        args.update(overrides or {})
        self.enter('chain-motion-request', sp=0x027E3600, lr=self.timed + 13, **args)
        if self.hooks.error is None:
            self.returned(decision, sp=0x027E3600, address=self.timed + 12)

    def finish_start(self, accepted):
        start = self.observer.reposition_contexts[-1]['_activeStart']
        reason = 0 if accepted else ((start['motionRequests'] or start['hopPlans'] or [{'decision': 8}])[-1].get('decision', 8))
        if start['motionRequests'] and reason in (2, 3, 4, 5):
            reason = 8
        self.returned(reason, sp=0x027E37A0, address=self.run + 20)
        self.put(self.observer.reposition_contexts[-1]['resultPointer'] + 3, bytes((reason,)))

    def plan(self, decision, *, target=(552, 383), operation=2, complete=True):
        self.plan_pointer = 0x027E3500
        self.put(self.plan_pointer, struct.pack('<5I2i6hI4B',
                 0, self.lane, 0x02231000, 0x02228000, self.source['object'],
                 -4096, 8192, 550, 381, *target, 0, 0, 8, operation, 0, 0, 2))
        self.enter('chain-hop-plan', sp=0x027E3400, lr=self.plan_caller + 13,
                   r0=self.plan_pointer)
        if complete and self.hooks.error is None:
            self.returned(decision, sp=0x027E3400, address=self.plan_caller + 12)

    def finish(self, accepted, *, native_result=None):
        if native_result is not None:
            self.put(0x027E3820, bytes(native_result))
        elif accepted:
            self.put(0x027E3820, bytes((0xA4, 1, 1, 0)))
        self.returned(int(accepted))
        self.observer.completed_frame(12)
        rows = self.observer.drain()
        return next(row['data'] for row in rows if row['data']['observation'] == 'chain-reposition-attempt')


class RepositionObserverTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='reposition-observer-')
        self.addCleanup(self.directory.cleanup)
        self.f = RepositionFixture(self.directory.name)

    def test_all_landing_rejections_have_no_invented_request(self):
        f = self.f
        f.begin()
        for target in ((552, 379), (552, 383), (548, 379), (548, 383)):
            f.landing(False, target=target)
        receipt = f.finish(False)
        self.assertEqual(receipt['outcomeStage'], 'landing-search-exhausted')
        self.assertEqual(len(receipt['landings']), 4)
        self.assertEqual(receipt['preparedStarts'], [])
        self.assertEqual(receipt['landings'][0]['rejectionStage'], 'pre-terrain-rejected')
        self.assertEqual(receipt['landings'][0]['surfaceQueries'], [])
        self.assertEqual(receipt['publicSubject']['handle'], f.actor['handle'])
        self.assertIsNone(f.hooks.error)

    def test_typed_result_separates_retry_abort_complete_without_motion_credit(self):
        for outcome, reason, name in ((0, 8, 'RETRY'), (2, 0, 'COMPLETE'), (3, 12, 'ABORT')):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                f = RepositionFixture(directory)
                f.begin(encoded=0xA3)
                if outcome == 3:
                    for target in ((548, 379), (552, 379), (548, 383), (552, 383)):
                        f.landing(False, target=target)
                row = f.finish(False, native_result=(0xA3, 0, outcome, reason))
                self.assertEqual(row['observationVersion'], 2)
                self.assertEqual(row['nativeResult']['outcomeName'], name)
                self.assertEqual(row['nativeResult']['reason'], reason)
                self.assertEqual(row['resultHex'], bytes((0xA3, 0, outcome, reason)).hex())
                self.assertEqual(row['returnValue'], 0)
                self.assertEqual(row['preparedStarts'], [])
                self.assertEqual(row['nativeControlAfter']['inputOwnership'], 0)
                self.assertEqual(row['nativeControlAfter']['reservationId'], 0)

    def test_typed_native_reason_cannot_be_replaced_by_a_boolean(self):
        f = self.f
        f.begin(); f.landing(False)
        row = f.finish(False)
        self.assertEqual(row['landings'][0]['returnValue'], 2)
        self.assertEqual(row['landings'][0]['decisionName'], 'BLOCKED')
        self.assertIs(row['landings'][0]['accepted'], False)

    def test_invalid_typed_result_or_changed_retry_remainder_fails(self):
        for raw in ((0x20, 0, 99, 0), (0x20, 0, 0, 99), (0x21, 0, 0, 8),
                    (0x20, 0, 3, 5), (0x20, 0, 1, 0)):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as directory:
                f = RepositionFixture(directory)
                f.begin(); f.put(0x027E3820, bytes(raw)); f.returned(0)
                self.assertIsNotNone(f.hooks.error)
                self.assertFalse(f.observer.snapshot()['coverageComplete'])
                self.assertEqual(f.observer.drain(), [])

    def test_typed_busy_decision_is_not_landing_rejection(self):
        f = self.f
        f.begin(); f.landing(True); f.start(); f.request(1); f.finish_start(False)
        receipt = f.finish(False)
        request = receipt['preparedStarts'][0]['motionRequests'][0]
        self.assertEqual(receipt['preparedStarts'][0]['returnValue'], 1)
        self.assertIs(receipt['preparedStarts'][0]['accepted'], False)
        self.assertEqual(receipt['outcomeStage'], 'motion-request-rejected')
        self.assertEqual((request['decision'], request['decisionName']), (1, 'RETRY_WORLD_BUSY'))
        self.assertEqual(request['duration'], 8)
        self.assertEqual(request['laneHex'], bytes(range(72)).hex())
        self.assertIsNone(f.hooks.error)

    def test_post_preparation_blocking_is_retry_reason_not_structural_plan_denial(self):
        for decision in (2, 3, 4, 5):
            with self.subTest(decision=decision), tempfile.TemporaryDirectory() as directory:
                f = RepositionFixture(directory)
                f.begin(); f.landing(True); f.start(); f.request(decision); f.finish_start(False)
                self.assertIsNone(f.hooks.error)
                start = f.finish(False)['preparedStarts'][0]
                self.assertEqual(start['hopPlans'][0]['decisionName'], 'ACCEPTED')
                self.assertEqual(start['motionRequests'][0]['decision'], decision)
                self.assertEqual(start['startReasonName'], 'PROFILE')
                self.assertNotIn('reasonPointer', start)
                self.assertEqual(start['returnValue'], 8)
                self.assertIs(start['accepted'], False)

    def test_all_admission_decisions_keep_the_exact_native_value(self):
        # Native Timed never searches another candidate after preparation.
        # Only its finite geometric/occupancy range maps to retry-only PROFILE;
        # the nested RequestMotion receipt must retain every original value.
        expected = {0: 0, 1: 1, 2: 8, 3: 8, 4: 8, 5: 8,
                    6: 6, 7: 7, 8: 8, 9: 9, 10: 10, 11: 11, 12: 12}
        self.assertEqual(set(expected), set(range(len(MOTION_DECISIONS))))
        for decision, reason in expected.items():
            with self.subTest(decision=MOTION_DECISIONS[decision]), tempfile.TemporaryDirectory() as directory:
                f = RepositionFixture(directory)
                f.begin(); f.landing(True); f.start(); f.request(decision)
                f.returned(reason, sp=0x027E37A0, address=f.run + 20)
                self.assertIsNone(f.hooks.error)
                row = f.finish(decision == 0, native_result=(0xA4, 1, 1, 0) if decision == 0 else (0x20, 0, 0, reason))
                start = row['preparedStarts'][0]
                self.assertEqual(start['motionRequests'][0]['decision'], decision)
                self.assertEqual(start['motionRequests'][0]['decisionName'], MOTION_DECISIONS[decision])
                self.assertEqual(start['startReason'], reason)
                self.assertEqual(start['accepted'], decision == 0)

    def test_wrong_admission_mapping_and_unknown_decisions_fail_closed(self):
        for decision, reason in ((3, 3), (5, 5), (1, 8), (6, 8), (0, 8)):
            with self.subTest(decision=decision, reason=reason), tempfile.TemporaryDirectory() as directory:
                f = RepositionFixture(directory)
                f.begin(); f.landing(True); f.start(); f.request(decision)
                f.returned(reason, sp=0x027E37A0, address=f.run + 20)
                self.assertIsNotNone(f.hooks.error)
                self.assertFalse(f.observer.snapshot()['coverageComplete'])
                self.assertEqual(f.observer.drain(), [])
        for decision in (len(MOTION_DECISIONS), 99, 0xFFFFFFFF):
            for stage in ('request', 'start'):
                with self.subTest(decision=decision, stage=stage), tempfile.TemporaryDirectory() as directory:
                    f = RepositionFixture(directory)
                    f.begin(); f.landing(True); f.start()
                    if stage == 'request':
                        f.request(decision)
                        self.assertIn('decision enum differs', f.hooks.error)
                    else:
                        f.request(1)
                        f.returned(decision, sp=0x027E37A0, address=f.run + 20)
                        self.assertIn('start reason differs', f.hooks.error)
                    self.assertFalse(f.observer.snapshot()['coverageComplete'])
                    self.assertEqual(f.observer.drain(), [])

    def test_unobserved_permanent_start_reason_fails_closed(self):
        f = self.f
        f.begin(); f.landing(True); f.start()
        f.returned(2, sp=0x027E37A0, address=f.run + 20)
        self.assertIn('lacks matching native stage', f.hooks.error)

    def test_native_single_movement_guard_allows_only_observed_early_retry(self):
        f = self.f
        f.begin(); f.landing(True)
        f.player['flags'] |= 2
        f.start()
        f.returned(9, sp=0x027E37A0, address=f.run + 20)
        row = f.finish(False, native_result=(0x20, 0, 0, 9))
        start = row['preparedStarts'][0]
        self.assertEqual(start['startReasonName'], 'ALREADY_ACTIVE')
        self.assertIs(start['accepted'], False)
        self.assertEqual(start['engineFlagsAtEntry'] & 2, 2)
        self.assertEqual(start['hopPlans'], [])
        self.assertEqual(start['motionRequests'], [])
        self.assertIsNone(f.hooks.error)
        for flags, reason in ((1, 9), (1 | 16, 9), (1 | 2, 2)):
            with self.subTest(flags=flags, reason=reason), tempfile.TemporaryDirectory() as directory:
                g = RepositionFixture(directory)
                g.begin(); g.landing(True); g.player['flags'] = flags; g.start()
                g.returned(reason, sp=0x027E37A0, address=g.run + 20)
                self.assertIn('lacks matching native stage', g.hooks.error)
                self.assertFalse(g.observer.snapshot()['coverageComplete'])

    def test_later_flag_change_cannot_repair_missing_single_movement_at_entry(self):
        f = self.f
        f.begin(); f.landing(True); f.start()
        f.player['flags'] |= 2
        f.returned(9, sp=0x027E37A0, address=f.run + 20)
        self.assertIn('lacks matching native stage', f.hooks.error)

    def test_accepted_request_preserves_signed_target_and_exact_identity(self):
        f = self.f
        f.begin(); f.landing(True, target=(-2, 383)); f.start(target=(-2, 383))
        f.request(0); f.finish_start(True)
        receipt = f.finish(True)
        self.assertEqual(receipt['outcomeStage'], 'started')
        self.assertEqual(receipt['preparedStarts'][0]['target'], [-2, 383])
        self.assertEqual(receipt['preparedStarts'][0]['returnValue'], 0)
        self.assertIs(receipt['preparedStarts'][0]['accepted'], True)
        self.assertEqual(receipt['publicSubjectAfter']['handle'], receipt['publicSubject']['handle'])
        self.assertEqual(receipt['returnNativeCycle'], 10)
        self.assertNotIn('_activeStart', receipt)
        self.assertIsNone(f.hooks.error)

    def test_missing_request_is_an_explicit_pre_admission_rejection(self):
        f = self.f
        f.begin(); f.landing(True); f.start(); f.finish_start(False)
        receipt = f.finish(False)
        self.assertEqual(receipt['outcomeStage'], 'prepared-before-request-rejected')
        self.assertEqual(receipt['preparedStarts'][0]['motionRequests'], [])

    def test_wrong_state_slot_field_object_target_or_profile_rejects(self):
        cases = (('landing', {'r0': 0x02230200}), ('landing', {'r1': 1}),
                 ('landing', {'r2': 0x02232000}), ('start', {'r3': 0x0221012C}),
                 ('request', {'r1': 1}), ('request', {'r3': 2}))
        for method, overrides in cases:
            with self.subTest(method=method, overrides=overrides), tempfile.TemporaryDirectory() as directory:
                f = RepositionFixture(directory)
                f.begin()
                if method == 'landing':
                    f.landing(True, overrides=overrides)
                else:
                    f.landing(True)
                    if method == 'start':
                        f.start(overrides=overrides)
                    else:
                        f.start(); f.request(0, overrides=overrides)
                self.assertIn('arguments do not match attempt', f.hooks.error)
                self.assertFalse(f.observer.snapshot()['coverageComplete'])
        f = self.f
        f.begin(); f.landing(True); f.start(target=(553, 383))
        self.assertIn('no matching accepted landing', f.hooks.error)

    def test_changed_actor_generation_or_native_binding_cannot_complete(self):
        f = self.f
        f.begin(); f.actor['handle']['generation'] += 1
        f.landing(False)
        self.assertIn('subject or world identity changed', f.hooks.error)
        with tempfile.TemporaryDirectory() as directory:
            g = RepositionFixture(directory)
            g.begin(); g.engine['current_manager'] += 4
            g.returned(0)
            self.assertIn('native identity differs', g.hooks.error)
            self.assertEqual(g.observer.drain(), [])

    def test_wrong_native_caller_and_modified_caller_code_reject(self):
        f = self.f
        f.begin()
        f.enter('chain-landing', sp=0x027E37A0, lr=0x02001081)
        self.assertIn('wrong native caller', f.hooks.error)
        with tempfile.TemporaryDirectory() as directory:
            g = RepositionFixture(directory)
            g.begin(); g.landing(False)  # Cache the authenticated first BL.
            g.put(g.run + 8, b'\x00' * 4)
            g.landing(False)
            self.assertIn('caller live code differs', g.hooks.error)

    def test_missing_return_and_candidate_limit_fail_without_success_receipt(self):
        f = self.f
        f.begin(); f.landing(True); f.start()
        f.returned(0)  # Run cannot finish while its child is still running.
        self.assertIn('missing child return', f.hooks.error)
        with tempfile.TemporaryDirectory() as directory:
            g = RepositionFixture(directory)
            g.begin()
            for _ in range(9): g.landing(False)
            self.assertIn('landing count/order differs', g.hooks.error)

    def test_children_outside_chain_scope_do_no_reads_or_extra_hooks(self):
        f = self.f
        # Unlike the existing independent spawn-motion tap, these three child
        # taps must reject their scope before reading code or native data.
        def unexpected(*args): raise AssertionError('unscoped native read')
        f.read = unexpected
        for label in ('chain-landing', 'chain-motion-request', 'chain-hop-plan',
                      'chain-landing-surface', 'chain-landing-terrain', 'chain-landing-objects',
                      'chain-landing-nonplayer', 'chain-landing-surface-occupancy'):
            f.enter(label)
        self.assertIsNone(f.hooks.error)
        self.assertEqual(f.observer.calls['chain-landing']['entered'], 0)
        self.assertEqual(f.observer.calls['chain-motion-request']['entered'], 0)
        self.assertEqual(f.observer.calls['chain-hop-plan']['entered'], 0)

    def test_native_terrain_rejection_does_not_read_uninitialized_hit(self):
        f = self.f
        f.begin(); f.landing(False, complete=False)
        f.detail('surface', False); f.detail('terrain', False)
        f.returned(4, sp=0x027E37A0, address=f.run + 12)
        landing = f.finish(False)['landings'][0]
        self.assertEqual(landing['rejectionStage'], 'terrain-permission-rejected')
        self.assertIsNone(landing['surfaceQueries'][0]['hit'])
        self.assertEqual(landing['terrainMatches'][0]['behavior'], 2)
        self.assertEqual(landing['occupancyQueries'], [])

    def test_surface_identity_rejection_retains_both_actual_points_and_hits(self):
        f = self.f
        f.begin(); f.landing(False, complete=False)
        f.detail('surface', True, hit=(8192, 12, 2, 4))
        f.detail('surface', True, target=(550, 381), hit=(4096, 13, 1, 5))
        f.returned(4, sp=0x027E37A0, address=f.run + 12)
        landing = f.finish(False)['landings'][0]
        self.assertEqual(landing['rejectionStage'], 'surface-validation-rejected')
        self.assertEqual([r['pointRole'] for r in landing['surfaceQueries']], ['target', 'source'])
        self.assertEqual([r['hit']['surfaceId'] for r in landing['surfaceQueries']], [12, 13])
        self.assertEqual(landing['terrainMatches'], [])
        self.assertIsNone(f.hooks.error)

    def test_actual_occupancy_variants_retain_result_and_surface_height(self):
        for kind in ('objects', 'nonplayer', 'surface-occupancy'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                f = RepositionFixture(directory)
                f.begin(); f.landing(False, complete=False)
                f.detail('surface', True)
                f.detail(kind, True)
                f.returned(5, sp=0x027E37A0, address=f.run + 12)
                landing = f.finish(False)['landings'][0]
                self.assertEqual(landing['rejectionStage'], 'occupied')
                self.assertEqual(landing['occupancyQueries'][0]['kind'], kind)
                if kind == 'surface-occupancy':
                    self.assertEqual(landing['occupancyQueries'][0]['targetBaseY'], -4096)
                self.assertIsNone(f.hooks.error)

    def test_child_surface_queries_inside_terrain_match_are_not_borrowed(self):
        f = self.f
        f.begin(); f.landing(False, complete=False)
        f.detail('surface', False); f.detail('terrain', False, complete=False)
        original = f.read
        def unexpected(*args): raise AssertionError('nested native read')
        f.read = unexpected
        f.enter('chain-landing-surface', lr=0x02001201)
        f.read = original
        self.assertIsNone(f.hooks.error)
        f.returned(0, sp=0x027E3700, address=f.landing_caller + 12)
        f.returned(4, sp=0x027E37A0, address=f.run + 12)
        self.assertEqual(len(f.finish(False)['landings'][0]['surfaceQueries']), 1)

    def test_landing_detail_wrong_point_caller_and_changed_code_fail(self):
        f = self.f
        f.begin(); f.landing(False, complete=False)
        f.detail('surface', True, target=(555, 383))
        self.assertIn('point differs', f.hooks.error)
        with tempfile.TemporaryDirectory() as directory:
            g = RepositionFixture(directory)
            g.begin(); g.landing(False, complete=False)
            g.enter('chain-landing-surface', lr=g.run + 13)
            self.assertIn('wrong native caller', g.hooks.error)
        with tempfile.TemporaryDirectory() as directory:
            g = RepositionFixture(directory)
            g.begin(); g.landing(False, complete=False)
            g.put(g.observer.calls['chain-landing-surface']['address'], bytes(32))
            g.detail('surface', True)
            self.assertIn('resident code identity differs', g.hooks.error)

    def test_missing_and_inconsistent_landing_details_fail_closed(self):
        f = self.f
        f.begin(); f.landing(False, complete=False); f.detail('surface', True, complete=False)
        f.returned(0, sp=0x027E37A0, address=f.run + 12)
        self.assertIn('missing detail return', f.hooks.error)
        for case, message in (('missing-terrain', 'missing terrain match'),
                              ('missing-occupancy', 'no occupancy receipt'),
                              ('duplicate-occupancy', 'count/order differs'),
                              ('wrong-height', 'surface height differs'),
                              ('wrong-result', 'results disagree')):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                g = RepositionFixture(directory)
                g.begin(); g.landing(False, complete=False)
                g.detail('surface', case != 'missing-terrain')
                if case == 'duplicate-occupancy':
                    g.detail('objects', True); g.detail('nonplayer', True)
                elif case == 'wrong-height':
                    g.detail('surface-occupancy', True, hit=(4096, 12, 2, 4))
                elif case == 'wrong-result':
                    g.detail('objects', True)
                if g.hooks.error is None:
                    g.returned(0 if case in ('missing-occupancy', 'wrong-result') else 4,
                               sp=0x027E37A0, address=g.run + 12)
                self.assertIn(message, g.hooks.error)

    def test_plan_outside_prepared_start_does_no_reads(self):
        f = self.f
        f.begin()
        def unexpected(*args): raise AssertionError('unscoped native read')
        f.read = unexpected
        f.enter('chain-hop-plan')
        self.assertIsNone(f.hooks.error)
        self.assertEqual(f.observer.calls['chain-hop-plan']['entered'], 0)

    def test_actual_blocked_plan_is_not_an_invented_motion_rejection(self):
        f = self.f
        f.begin(); f.landing(True); f.start(); f.plan(2); f.finish_start(False)
        receipt = f.finish(False)
        start = receipt['preparedStarts'][0]
        plan = start['hopPlans'][0]
        self.assertEqual(receipt['outcomeStage'], 'prepared-before-request-rejected')
        self.assertEqual(start['motionRequests'], [])
        self.assertEqual((plan['decision'], plan['decisionName']), (2, 'BLOCKED'))
        self.assertEqual((plan['startBaseY'], plan['targetBaseY']), (-4096, 8192))
        self.assertEqual((plan['operation'], plan['distance']), (2, 2))
        self.assertEqual((plan['origin'], plan['target']), ([550, 381], [552, 383]))
        self.assertEqual(plan['laneHex'], bytes(range(72)).hex())
        self.assertNotIn('_activePlan', start)
        self.assertIsNone(f.hooks.error)

    def test_multiple_blocked_plans_pair_to_distinct_candidates_before_one_start(self):
        f = self.f
        f.begin(); f.landing(True); f.start(); f.plan(2); f.finish_start(False)
        f.landing(True, target=(548, 383)); f.start(target=(548, 383))
        f.request(0); f.finish_start(True)
        receipt = f.finish(True)
        self.assertEqual(receipt['outcomeStage'], 'started')
        self.assertEqual([r['landingIndex'] for r in receipt['preparedStarts']], [0, 1])
        self.assertEqual([r['hopPlans'][0]['decisionName'] for r in receipt['preparedStarts']], ['BLOCKED', 'ACCEPTED'])
        self.assertIsNone(f.hooks.error)

    def test_candidate_search_cannot_continue_after_accepted_start(self):
        f = self.f
        f.begin(); f.landing(True); f.start(); f.request(0); f.finish_start(True)
        f.landing(False)
        self.assertIn('landing count/order differs', f.hooks.error)

    def test_accepted_plan_retains_output_separate_from_input(self):
        f = self.f
        f.begin(); f.landing(True); f.start(); f.plan(0, operation=1, complete=False)
        f.put(f.plan_pointer + 40, struct.pack('<I', 0x40008))
        f.returned(0, sp=0x027E3400, address=f.plan_caller + 12)
        f.request(0); f.finish_start(True)
        plan = f.finish(True)['preparedStarts'][0]['hopPlans'][0]
        self.assertEqual(plan['inputTrajectory'], 8)
        self.assertEqual(plan['outputTrajectory'], 0x40008)
        self.assertEqual(plan['decisionName'], 'ACCEPTED')
        self.assertIsNone(f.hooks.error)

    def test_missing_plan_is_not_accepted_and_missing_return_fails(self):
        f = self.f
        f.begin(); f.landing(True); f.start(); f.finish_start(False)
        self.assertEqual(f.finish(False)['preparedStarts'][0]['hopPlans'], [])
        with tempfile.TemporaryDirectory() as directory:
            g = RepositionFixture(directory)
            g.begin(); g.landing(True); g.start(); g.plan(0, complete=False)
            g.finish_start(False)
            self.assertIn('missing request return', g.hooks.error)
            self.assertFalse(g.observer.snapshot()['coverageComplete'])

    def test_plan_wrong_target_operation_decision_and_input_mutation_fail(self):
        for overrides, message in (({'target': (551, 383)}, 'arguments do not match'),
                                   ({'operation': 0}, 'arguments do not match'),
                                   ({'decision': 99}, 'decision enum differs')):
            with self.subTest(overrides=overrides), tempfile.TemporaryDirectory() as directory:
                g = RepositionFixture(directory)
                g.begin(); g.landing(True); g.start()
                g.plan(**({'decision': 0} | overrides))
                self.assertIn(message, g.hooks.error)
        f = self.f
        f.begin(); f.landing(True); f.start(); f.plan(0, complete=False)
        f.put(f.plan_pointer + 28, struct.pack('<h', 123))
        f.returned(0, sp=0x027E3400, address=f.plan_caller + 12)
        self.assertIn('inputs changed', f.hooks.error)

    def test_plan_wrong_caller_subject_and_second_plan_fail(self):
        f = self.f
        f.begin(); f.landing(True); f.start()
        f.enter('chain-hop-plan', lr=f.timed + 13)
        self.assertIn('wrong native caller', f.hooks.error)
        with tempfile.TemporaryDirectory() as directory:
            g = RepositionFixture(directory)
            g.begin(); g.landing(True); g.start(); g.plan(0, complete=False)
            g.actor['handle']['generation'] += 1
            g.returned(0, sp=0x027E3400, address=g.plan_caller + 12)
            self.assertIn('subject or world identity changed', g.hooks.error)
        with tempfile.TemporaryDirectory() as directory:
            g = RepositionFixture(directory)
            g.begin(); g.landing(True); g.start(); g.plan(2); g.plan(0)
            self.assertIn('count/order differs', g.hooks.error)

    def test_request_without_observed_accepted_plan_fails_closed(self):
        f = self.f
        f.begin(); f.landing(True); f.start()
        f.enter('chain-motion-request', lr=f.timed + 13)
        self.assertIn('no returned accepted Hop plan', f.hooks.error)
        with tempfile.TemporaryDirectory() as directory:
            g = RepositionFixture(directory)
            g.begin(); g.landing(True); g.start(); g.plan(2); g.request(0)
            self.assertIn('no returned accepted Hop plan', g.hooks.error)
        with tempfile.TemporaryDirectory() as directory:
            g = RepositionFixture(directory)
            g.begin(); g.landing(True); g.start(); g.plan(0, complete=False)
            g.request(0)
            self.assertIn('no returned accepted Hop plan', g.hooks.error)

    def test_nonmatching_plan_code_cannot_grant_request_receipt(self):
        f = self.f
        f.begin(); f.landing(True); f.start()
        address = f.observer.calls['chain-hop-plan']['address']
        f.put(address, bytes(32))
        f.plan(0, complete=False)
        self.assertEqual(f.observer.calls['chain-hop-plan']['nonmatchingEntries'], 1)
        self.assertEqual(f.observer.reposition_contexts[-1]['_activeStart']['hopPlans'], [])
        f.enter('chain-motion-request', lr=f.timed + 13)
        self.assertIn('no returned accepted Hop plan', f.hooks.error)

    def test_one_attempt_has_two_full_manager_reads_and_one_bounded_event(self):
        f = self.f
        reads = []
        f.rt.live_wild_object_identity = lambda _emu, slot: (reads.append(slot) or deepcopy(f.engine))
        f.begin()
        for _ in range(8): f.landing(False)
        receipt = f.finish(False)
        self.assertEqual(reads, [0, 0])
        self.assertEqual(len(receipt['landings']), 8)
        self.assertEqual(f.observer.sequence, 1)
        self.assertEqual(len(f.observer.reposition_call_sites), 1)

    def test_nested_other_actor_keeps_each_parent_and_attempt_identity(self):
        f = self.f
        f.begin()
        original = deepcopy((f.actor, f.source, f.engine))
        f.actor['handle'].update(slot=1, value=0x10001)
        f.actor['subjectIdentity'] = 100
        f.source.update(personality=100, object_id=0xE1, object=0x0221012C)
        f.engine.update(object_id=0xE1, pointer=0x0221012C, manager_index=3)
        f.put(0x027E3700, struct.pack('<I', 0x027E3720))
        f.put(0x027E3720, bytes((0xA2, 0, 0, 8)))
        f.enter('chain-reposition-attempt', sp=0x027E3700, lr=0x02001201,
                r0=f.rt.WILD_STATE, r1=1, r2=f.profile, r3=0xA2)
        f.returned(0, sp=0x027E3700, address=0x02001200)
        f.actor, f.source, f.engine = original
        f.landing(False); f.returned(0)
        f.observer.completed_frame(12)
        receipts = [row['data'] for row in f.observer.drain()]
        self.assertEqual([item['slot'] for item in receipts], [1, 0])
        self.assertEqual([item['attemptId'] for item in receipts], [2, 1])
        self.assertEqual([len(item['landings']) for item in receipts], [0, 1])
        self.assertEqual([item['publicSubject']['subjectIdentity'] for item in receipts], [100, 99])
        self.assertIsNone(f.hooks.error)

    def test_real_arm_signatures_parameter_order_and_decision_enum(self):
        root = Path(__file__).resolve().parents[2]
        wild = (root / 'src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c').read_text()
        runtime = (root / 'src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c').read_text()
        result = re.search(r'typedef struct OverworldWildChainRepositionResult \{[^}]+\} OverworldWildChainRepositionResult;', wild)
        self.assertIsNotNone(result)
        specs = (
            ('OverworldWildSpawns_RunChainReposition', wild, 'BOOL',
             ['state', 'slot', 'profile', 'encodedRemaining', 'result'],
             'BOOL (*)(OverworldWildSpawnState *, int, const OverworldWildBehaviorProfile *, u8, OverworldWildChainRepositionResult *)'),
            ('OverworldWildSpawns_IsBehaviorAllowedHopLandingTile', wild, 'BOOL',
             ['state', 'slot', 'fieldSystem', 'allowedTile', 'x', 'y', 'finalTargetX', 'finalTargetY'],
             'BOOL (*)(OverworldWildSpawnState *, int, FieldSystem *, u16, int, int, int, int)'),
            ('OverworldWildSpawns_ClassifyBehaviorHopLandingTile', wild, 'OverworldMotionDecision',
             ['state', 'slot', 'fieldSystem', 'allowedTile', 'x', 'y', 'finalTargetX', 'finalTargetY'],
             'OverworldMotionDecision (*)(OverworldWildSpawnState *, int, FieldSystem *, u16, int, int, int, int)'),
            ('OverworldWildSpawns_StartPreparedCustomJumpCommand', wild, 'BOOL',
             ['state', 'fieldSystem', 'slot', 'object', 'direction', 'distance', 'targetX', 'targetY', 'profile', 'suppressHopStartSound'],
             'BOOL (*)(OverworldWildSpawnState *, FieldSystem *, int, LocalMapObject *, u8, u8, int, int, const OverworldWildBehaviorProfile *, BOOL)'),
            ('OverworldWildSpawns_StartPreparedCustomJumpCommandTimed', wild, 'OverworldMotionDecision',
             ['state', 'fieldSystem', 'slot', 'object', 'direction', 'distance', 'targetX', 'targetY', 'profile', 'suppressHopStartSound', 'walkTime'],
             'OverworldMotionDecision (*)(OverworldWildSpawnState *, FieldSystem *, int, LocalMapObject *, u8, u8, int, int, const OverworldWildBehaviorProfile *, BOOL, u8)'),
            ('OverworldWildRuntime_RequestMotion', runtime, 'OverworldMotionDecision',
             ['state', 'slot', 'lane', 'kind', 'visibilityPolicy', 'arcHeightQ4', 'facing', 'duration', 'spinSpeed', 'swayWidth', 'targetSurfaceId'],
             'OverworldWildRuntimeRequestMotionFunc'),
            ('OverworldWildSpawns_QuerySurface', wild, 'BOOL',
             ['fieldSystem', 'x', 'y', 'hit'],
             'BOOL (*)(FieldSystem *, int, int, OverworldWildSurfaceHit *)'),
            ('OverworldWildSpawns_DoesAllowedTileMatch', wild, 'BOOL',
             ['fieldSystem', 'allowedTerrainMask', 'behavior', 'x', 'y'],
             'BOOL (*)(FieldSystem *, u16, u8, int, int)'),
            ('OverworldWildSpawns_IsTileOccupiedByObject', wild, 'BOOL',
             ['fieldSystem', 'x', 'y'], 'BOOL (*)(FieldSystem *, int, int)'),
            ('OverworldWildSpawns_IsTileOccupiedByNonPlayerObject', wild, 'BOOL',
             ['fieldSystem', 'ignoredObject', 'x', 'y'],
             'BOOL (*)(FieldSystem *, LocalMapObject *, int, int)'),
            ('OverworldWildSpawns_IsTileOccupiedOnSurface', wild, 'BOOL',
             ['fieldSystem', 'ignoredObject', 'includePlayer', 'x', 'y', 'targetBaseY'],
             'BOOL (*)(FieldSystem *, LocalMapObject *, BOOL, int, int, s32)'))
        program = '#include "overworld_wild_helper.h"\n#include "overworld_wild_runtime.h"\n#include "overworld_actor_system_internal.h"\n#include "map_events_internal.h"\n#include <stddef.h>\n' + result[0] + '\n'
        for name, source, returns, names, signature in specs:
            match = re.search(r'static\s+' + returns + r'\s+[^;{}]*?\b' + name + r'\(([^;{}]+)\)\s*\{', source)
            self.assertIsNotNone(match, name)
            actual = [re.search(r'(\w+)\s*$', item)[1] for item in match[1].split(',')]
            self.assertEqual(actual, names, name + ' register/stack order')
            program += f'static {returns} {name}({match[1]});\n'
            program += f'_Static_assert(__builtin_types_compatible_p(__typeof__(&{name}), {signature}), "{name} ABI");\n'
        program += '_Static_assert(sizeof(void *) == 4 && sizeof(BOOL) == 4 && sizeof(int) == 4, "AAPCS words");\n'
        program += '_Static_assert(sizeof(OverworldWildChainRepositionResult) == 4, "result ABI");\n'
        for member, offset in dict(encodedRemaining=0, gridDelta=1, outcome=2, reason=3).items():
            program += f'_Static_assert(offsetof(OverworldWildChainRepositionResult, {member}) == {offset}, "result {member}");\n'
        for value, name in enumerate(CHAIN_OUTCOMES):
            definition = re.search(r'^#define OW_WILD_CHAIN_' + name + r'\s+\d+\s*$', wild, re.MULTILINE)
            self.assertIsNotNone(definition, 'actual native ' + name + ' outcome')
            program += definition[0] + '\n'
            program += f'_Static_assert(OW_WILD_CHAIN_{name} == {value}, "result {name}");\n'
        program += '_Static_assert(sizeof(OverworldWildBehaviorProfileData) == 72, "lane ABI");\n'
        program += '_Static_assert(offsetof(LocalMapObject, flags) == 0 && MAPOBJECTFLAG_SINGLE_MOVEMENT == 2, "native SingleMovement flag");\n'
        program += '_Static_assert(sizeof(OverworldWildSurfaceHit) == 8, "surface hit ABI");\n'
        for member, offset in dict(height=0, surfaceId=4, surfaceType=6, nodeId=7).items():
            program += f'_Static_assert(offsetof(OverworldWildSurfaceHit, {member}) == {offset}, "surface {member}");\n'
        program += '_Static_assert(OVERWORLD_MOTION_KIND_REPOSITION == 5, "kind");\n'
        program += '_Static_assert(sizeof(OverworldActorHopPlanCall) == 48, "Hop plan ABI");\n'
        for member, offset in dict(profile=0, lane=4, fieldSystem=8, surfaceCatalog=12,
                object=16, startBaseY=20, targetBaseY=24, startX=28, startY=30,
                targetX=32, targetY=34, deltaX=36, deltaY=38, trajectory=40,
                operation=44, spotState=45, direction=46, distance=47).items():
            program += f'_Static_assert(offsetof(OverworldActorHopPlanCall, {member}) == {offset}, "Hop {member}");\n'
        program += '_Static_assert(__builtin_types_compatible_p(__typeof__(&OverworldActorHopPlanner_Plan), OverworldMotionDecision (*)(OverworldActorHopPlanCall *)), "Hop signature");\n'
        program += '_Static_assert(OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY == 1 && OVERWORLD_ACTOR_HOP_PLAN_FLAT_TRAJECTORY == 2, "Hop operations");\n'
        for value, name in enumerate(MOTION_DECISIONS):
            program += f'_Static_assert(OVERWORLD_MOTION_DECISION_{name} == {value}, "{name}");\n'
        compiler = shutil.which(os.environ.get('ARM_NONE_EABI_CC', 'arm-none-eabi-gcc'))
        if not compiler and Path('/opt/homebrew/bin/arm-none-eabi-gcc').is_file():
            compiler = '/opt/homebrew/bin/arm-none-eabi-gcc'
        self.assertIsNotNone(compiler, 'native header check needs the ARM compiler')
        command = [compiler, '-x', 'c', '-std=c11', '-mthumb', '-mcpu=arm946e-s', '-I' + str(root / 'include'), '-fsyntax-only', '-']
        checked = subprocess.run(command, input=program, text=True, capture_output=True, timeout=20)
        self.assertEqual(checked.returncode, 0, checked.stderr[-3000:])
        wrong = subprocess.run(command, input=program.replace('== 1, "RETRY_WORLD_BUSY"', '== 0, "RETRY_WORLD_BUSY"'),
                               text=True, capture_output=True, timeout=20)
        self.assertNotEqual(wrong.returncode, 0, 'wrong decision must fail against the real native enum')
        wrong_offset = subprocess.run(command, input=program.replace('== 44, "Hop operation"', '== 40, "Hop operation"'),
                                      text=True, capture_output=True, timeout=20)
        self.assertNotEqual(wrong_offset.returncode, 0, 'wrong offset must fail against the real native layout')
        wrong_hit = subprocess.run(command, input=program.replace('== 4, "surface surfaceId"', '== 0, "surface surfaceId"'),
                                   text=True, capture_output=True, timeout=20)
        self.assertNotEqual(wrong_hit.returncode, 0, 'wrong surface hit offset must fail against the real native layout')
