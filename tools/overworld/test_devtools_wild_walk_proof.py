"""Host checks of seven retained rows and raw-data negative controls."""
from copy import deepcopy
from pathlib import Path
import json
import unittest

from tools.overworld.test_devtools_wild_walk_measurement import wild_fixture, replay
from tools.overworld.devtools_wild_walk_proof import (KIND, REQUIREMENT, FAULTS,
    WildWalkNegative, contract, measurements, validate_negative_result)


def good_result():
    fixture=wild_fixture();meter=replay(fixture)
    meter.close(dict(closed=True,advancedFrames=0,acceptedProof=False,snapshot=deepcopy(fixture[3][-1][0]),
        wildWalk=dict(fixture[2],closed=True,counts={'clear':1})),fixture[3][-1][0])
    result=meter.result()
    return dict(passed=True,failures=[],measurements={KIND:result}),dict(
        sessionId='private',sessionCleanup=dict(sessionId='private',closed=True,errors=[]))


class WildWalkProofTests(unittest.TestCase):
    def test_command_profile_cache_is_not_a_native_boundary_change(self):
        result,record=good_result()
        result['measurements'][KIND]['cleanup']['snapshot']['nativeObservation']['resolvedProfiles']=[{'cached':True}]
        self.assertEqual(len(measurements(result,record)),7)

    def test_cleanup_still_rejects_clock_actor_and_native_event_changes(self):
        for field in ('frame','nativeCycle','actorFrame','actors','nativeObservation'):
            result,record=good_result()
            snapshot=result['measurements'][KIND]['cleanup']['snapshot']
            if field=='nativeObservation':snapshot[field]['sequence']+=1
            elif field=='actors':snapshot[field][0]['commitSequence']+=1
            else:snapshot[field]+=1
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'terminal boundary'):
                measurements(result,record)

    def idle_noop_result(self):
        result,record=good_result();meter=result['measurements'][KIND]
        noop=deepcopy(meter['clearReceipts'][0]);data=noop['data']
        initial=meter['initial'];start=next(e for e in meter['traces'] if e['data']['event']=='MOTION_STARTED')
        noop['frame']=start['frame']
        data.update(entryActorFrame=start['data']['actorFrame'],returnActorFrame=start['data']['actorFrame'],
            entryNativeCycle=initial['nativeCycle']+2,returnNativeCycle=initial['nativeCycle']+2,sequence=1)
        data['before']['current']['publicSubject']=deepcopy(initial['actors'][0])
        data['before'].update(active=0,mode=0,objectFlags=1)
        data['after']=deepcopy(data['before'])
        meter['idleNoopClears']=[noop]
        meter['clearReceipts'][0]['data']['sequence']=2
        meter['cleanup']['wildWalk']['counts']['clear']=2
        return result,record

    def test_idle_noop_is_retained_but_never_counts_as_terminal_clear(self):
        result,record=self.idle_noop_result()
        values={r['name']:r['value'] for r in measurements(result,record)}
        self.assertEqual(values['wild-walk-clear-count'],1)
        self.assertEqual(result['measurements'][KIND]['cleanup']['wildWalk']['counts']['clear'],2)

    def test_idle_noop_wrong_flags_after_change_and_late_commit_fail(self):
        for fault in ('flags','after','commit','late','count'):
            result,record=self.idle_noop_result();meter=result['measurements'][KIND]
            data=meter['idleNoopClears'][0]['data']
            if fault=='flags':
                for side in ('before','after'):data[side]['objectFlags']|=4
            elif fault=='after':data['after']['objectFlags']|=2
            elif fault=='commit':
                for side in ('before','after'):data[side]['current']['publicSubject']['commitSequence']+=1
            elif fault=='late':meter['idleNoopClears'][0]['frame']=meter['motion']['finishFrame']
            else:meter['cleanup']['wildWalk']['counts']['clear']=1
            with self.subTest(fault=fault),self.assertRaises(ValueError):measurements(result,record)

    def test_contract_exactly_preserves_original_seven_rows(self):
        registry=json.loads((Path(__file__).resolve().parents[2]/'tools/overworld/runtime_proof_registry.json').read_text())
        contracts=next(v for v in registry.values() if isinstance(v,dict) and isinstance(v.get(REQUIREMENT),dict)
            and 'natural-input' in v[REQUIREMENT])
        self.assertEqual(contract(),contracts[REQUIREMENT])
        data,record=good_result();rows=measurements(data,record)
        self.assertEqual(len(rows),7)
        actual={r['name']:r['value'] for r in rows}
        self.assertEqual(actual['wild-walk-render-sample-counts'],dict(durations=[4],sampleCounts=[4]))
        self.assertEqual(actual['wild-walk-elapsed-schedules'],dict(durations=[4],sequences=[[1,2,3,4]]))
        self.assertEqual(actual['wild-walk-clear-count'],1)

    def test_missing_or_changed_actual_evidence_rejects_even_green_meter(self):
        faults=(lambda m:m.update(clearReceipts=[]),
            lambda m:m['clearReceipts'][0]['data']['after'].update(active=1),
            lambda m:m['clearReceipts'][0]['data']['after']['current'].update(slot=5),
            lambda m:m['motion']['samples'][1]['render'].__setitem__(0,1),
            lambda m:m['motion'].pop('travelEnd'),
            lambda m:m['terminal']['actors'][0].update(motionPhase='SETTLING'),
            lambda m:m['cleanup']['wildWalk'].update(guestMemoryWrites=2),
            lambda m:m['traces'].pop())
        for fault in faults:
            result,record=good_result();fault(result['measurements'][KIND])
            with self.assertRaises((ValueError,KeyError,TypeError)):measurements(result,record)
        result,record=good_result();record['sessionCleanup']['closed']=False
        with self.assertRaises(ValueError):measurements(result,record)

    def test_raw_controls_reach_same_meter_and_fail_for_named_meaning(self):
        for fault in FAULTS:
            fixture=wild_fixture();control=WildWalkNegative(fault)
            changed=[]
            for sample,events in fixture[3]:
                row=dict(phase='observe',samples=[sample],events=events)
                mutated=control.mutate(row,{'rattata':fixture[1]})
                changed.append((mutated['samples'][0],mutated['events']))
            data=(*fixture[:3],changed)
            meter=replay(data)
            with self.subTest(fault=fault):
                self.assertTrue(control.applied)
                self.assertTrue(meter.failures)
                result=dict(passed=False,failures=[],measurements={KIND:meter.result()})
                validate_negative_result(result,fault)

    def test_controls_never_accept_unrelated_failure(self):
        for fault in FAULTS:
            with self.assertRaises(ValueError):validate_negative_result(dict(passed=False,failures=['setup failed']),fault)


if __name__=='__main__':unittest.main()
