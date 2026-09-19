"""Pure copied memory tests; no emulator or runtime acceptance."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.test_devtools_acceleration_measurement import fixture
from tools.overworld.devtools_test_contract import validate_test
from tools.overworld.devtools_wild_battle_handoff_measurement import WildBattleHandoffMeasurement, replay
from tools.overworld.devtools_wild_battle_handoff_proof import (
    REQUIREMENT, FAULTS, contract, measurements, negative, validate_negative_result,
)


def sample():
    initial, reset, rows = fixture(species=19, delta=(2,0), durations=(4,), counters=(0,), speeds=(4,), base=4, fastest=4)
    for snapshot in [initial] + [s for s, _ in rows]:
        snapshot['selector'] = dict(heldKeys=0,newKeys=0,rawHeld=0,rawNew=0,
                                    physicalPressed=0,simulatedKeys=0)
    tail = deepcopy(rows[-1][0])
    actor = tail['actors'][0]
    for held, edge in ((16,16),(1,1)):
        snapshot = deepcopy(tail)
        snapshot['frame'] += 1; snapshot['actorFrame'] += 1; snapshot['nativeCycle'] += 2
        snapshot['player'].update(x=actor['logical']['x']-1,y=actor['logical']['y'],facing=3)
        snapshot['selector'].update(heldKeys=held,newKeys=edge,rawHeld=held,rawNew=edge,
                                    physicalPressed=held)
        events = []
        if edge == 1:
            snapshot['nativeObservation']['sequence'] += 1
            events.append(dict(frame=snapshot['frame'],kind='native-observation',data=dict(
                observation='wild-battle-request',sequence=snapshot['nativeObservation']['sequence'],
                entryNativeCycle=tail['nativeCycle'],returnNativeCycle=snapshot['nativeCycle'],
                subject=deepcopy(reset['subject']),currentActor=deepcopy(actor),
                pending=dict(slot=actor['handle']['slot'],species=19,personality=actor['subjectIdentity'],
                             encounterGeneration=actor['handle']['encounterGeneration']),
                player=deepcopy(snapshot['player']),input=deepcopy(snapshot['selector']),
                setupMode='prepared',returnValue=1)))
        rows.append((snapshot,events)); tail=snapshot
    meter=WildBattleHandoffMeasurement()
    meter.arm(reset['subject'],initial)
    for snapshot,events in rows: meter.observe(snapshot,events)
    return meter.finish()


class BattleHandoffTests(unittest.TestCase):
    def test_recipe_waits_for_idle_before_binding(self):
        recipe=validate_test(json.loads(Path('tests/overworld/test-recipes/battle.capture.wild-handoff.json').read_text()))
        setup={row['id']:index for index,row in enumerate(recipe['setup'])}
        self.assertLess(setup['idle-own-rattata'],setup['bind-new-rattata'])

    def test_contract_is_exact(self):
        registry=json.loads(Path('tools/overworld/runtime_proof_registry.json').read_text())
        self.assertEqual(contract(),registry['measurementContracts'][REQUIREMENT])

    def test_full_receipt_and_independent_replay(self):
        result=sample()
        self.assertTrue(result['passed'],result['failures'])
        self.assertTrue(replay(result)['passed'])
        rows=measurements(result,dict(sessionId='x',sessionCleanup=dict(sessionId='x',closed=True,errors=[])))
        self.assertEqual(len(rows),8)
        self.assertEqual(rows[5]['value'],[1,1])

    def test_lossless_ring_reuse_and_saved_stream_keys_replay(self):
        result=sample()
        result['traceSequences']={1:7}
        for _,events in result['journal']:
            for event in events:
                if event['kind']=='native': event['data']['sequence']+=7
        snapshot,events=next((snapshot,events) for snapshot,events in result['journal']
                             if any(event['kind']=='native' for event in events))
        events.append(dict(frame=snapshot['frame'],kind='trace-status',data=dict(
            code='ring-overwrite',traceStream=1,diagnosticOnly=True,count=1,unreadEventsLost=0)))
        saved=json.loads(json.dumps(result))
        self.assertTrue(replay(saved)['passed'],replay(saved)['failures'])

    def test_commit_trace_uses_counter_and_walk_kind(self):
        result=sample()
        result['initial']['actors'][0]['commitSequence']=5
        for _,events in result['journal']:
            for event in events:
                if event.get('data',{}).get('event') in ('LOGICAL_COMMIT','MOTION_FINISHED'):
                    event['data'].update(valueA=6,valueB=1)
        self.assertTrue(replay(result)['passed'],replay(result)['failures'])
        for field,value in (('valueA',5),('valueB',2)):
            changed=deepcopy(result)
            for _,events in changed['journal']:
                for event in events:
                    if event.get('data',{}).get('event')=='LOGICAL_COMMIT':
                        event['data'][field]=value
            with self.subTest(field=field): self.assertFalse(replay(changed)['passed'])

    def test_wrapped_runtime_negative_reason_is_accepted(self):
        self.assertTrue(validate_negative_result({
            'passed': False,
            'failures': [{'code': 'measurement-failed',
                          'details': {'failures': [
                              'missing native wild-battle-request receipt']}}],
        }, 'battle-missing-request'))

    def test_all_named_copied_faults(self):
        result=sample()
        self.assertTrue(result['passed'],result['failures'])
        for fault in FAULTS:
            with self.subTest(fault=fault):
                changed=negative(result,fault)
                self.assertTrue(validate_negative_result(replay(changed),fault))
                self.assertEqual(result,sample())

    def test_missing_observation_and_cleanup_fail_closed(self):
        result=sample()
        changed=negative(result,'battle-missing-request')
        with self.assertRaisesRegex(ValueError,'independent replay failed'):
            measurements(changed,dict(sessionId='x',sessionCleanup=dict(sessionId='x',closed=True,errors=[])))
        with self.assertRaisesRegex(ValueError,'close cleanly'):
            measurements(result,{})

    def test_frame_identity_return_and_trace_loss_rejected(self):
        for fault in ('frame', 'species', 'return', 'trace-loss', 'wrong-motion'):
            with self.subTest(fault=fault):
                result=sample()
                if fault == 'frame': result['journal'][0][0]['frame'] += 1
                elif fault == 'species': result['journal'][-1][1][0]['data']['currentActor']['species'] = 20
                elif fault == 'return': result['journal'][-1][1][0]['data']['returnValue'] = 0
                elif fault == 'trace-loss':
                    snapshot, events=result['journal'][0]
                    events.append(dict(frame=snapshot['frame'],kind='trace-status',
                                       data=dict(code='ring-overwrite',unreadEventsLost=1,coverageComplete=False)))
                else:
                    for _, events in result['journal']:
                        for event in events:
                            if event.get('data',{}).get('event') == 'MOTION_STARTED':
                                event['data']['valueA'] = 2
                self.assertFalse(replay(result)['passed'])

    def test_competing_physical_input_is_rejected(self):
        result=sample()
        result['journal'][-1][0]['selector']['physicalPressed'] |= 2
        self.assertFalse(replay(result)['passed'])

    def test_request_without_native_a_receipt_is_rejected(self):
        result=sample()
        result['journal'][-1][0]['selector']['rawNew'] = 0
        self.assertFalse(replay(result)['passed'])

    def test_absent_subject_rejected(self):
        result=sample(); result['initial']['actors']=[]
        with self.assertRaises(ValueError): replay(result)


if __name__ == '__main__': unittest.main()
