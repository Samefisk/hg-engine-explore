"""Small native-byte controls for the exact turn-skid contract."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import unittest
from tools.overworld.devtools_turn_skid_measurement import (
    ACCELERATION_MOTION_COUNT, MOTION_COUNT, TurnSkidMeasurement,
    validate_motion, DURATIONS, KINDS,
)
from tools.overworld.devtools_walk_matrix_observer import decode_motion, decode_sample
from tools.overworld.devtools_turn_skid_proof import contract, TurnSkidNegative, FAULTS, validate_negative_result


def motion(index):
    duration, kind = DURATIONS[index], KINDS[index]
    direction = 3 if index < MOTION_COUNT - 1 else 2
    ticks = []
    def state(elapsed):
        raw = bytearray(52)
        struct.pack_into('<HBBHH', raw, 0, 1, kind, direction, 1, 2)
        struct.pack_into('<4h2i', raw, 8, 580, 400, 581 if direction == 3 else 579, 400, 0, 0)
        struct.pack_into('<HH', raw, 24, duration, 44)
        raw[28:30] = bytes((direction, 1))
        struct.pack_into('<4H4B', raw, 40, elapsed, 0, 0, 0, 2 if elapsed < duration else 3, 0, 0, 0)
        return decode_motion(bytes(raw))
    for elapsed in range(duration):
        sample = decode_sample(struct.pack('<6i5H2B', *([0]*6), elapsed+1, duration, 0, 0, 0, direction, 1))
        ticks.append(dict(before=state(elapsed), after=state(elapsed+1), sample=sample))
    rows = [('MOTION_STARTED',kind,duration),('LOGICAL_COMMIT',11,kind),
            ('MOTION_FINISHED',11,kind),('CONTROL_RETURNED',1,11)]
    return dict(ticks=ticks, commitBefore=10,
                events=[dict(event=n,valueA=a,valueB=b,reason='OK',sequence=i+1) for i,(n,a,b) in enumerate(rows)])


class TurnSkidTests(unittest.TestCase):
    def test_all_native_schedules_and_raw_byte_faults(self):
        for index in range(MOTION_COUNT):
            original = motion(index)
            self.assertEqual(validate_motion(original,index)['duration'], DURATIONS[index])
            for fault in ('elapsed','raw','commit','kind','missing-start'):
                changed = deepcopy(original)
                if fault == 'elapsed': changed['ticks'][0]['before']['elapsed'] += 1
                elif fault == 'raw': changed['ticks'][0]['before']['rawHex'] = '00'*52
                elif fault == 'commit': changed['events'][1]['valueA'] += 1
                elif fault == 'kind': changed['ticks'][0]['before']['plan']['kind'] = 2
                else: changed['events'].pop(0)
                with self.subTest(index=index,fault=fault),self.assertRaises(ValueError): validate_motion(changed,index)

    def test_contract_is_exact_registry_contract(self):
        registry=json.loads((Path(__file__).resolve().parents[2]/'tools/overworld/runtime_proof_registry.json').read_text())
        expected=registry['sharedTests']['walk.turn-skid.control-release']['measurementContract']
        self.assertEqual(contract(),expected)
        by_name={spec['name']:spec for specs in expected.values() for spec in specs}
        self.assertEqual(
            DURATIONS[:ACCELERATION_MOTION_COUNT],
            by_name['turn-skid-acceleration-durations']['expected'])
        self.assertEqual([
            list(range(duration))
            for duration in DURATIONS[ACCELERATION_MOTION_COUNT:]],
                         by_name['turn-skid-motion-schedules']['expected'])

    def test_incomplete_window_never_passes(self):
        meter=TurnSkidMeasurement()
        self.assertFalse(meter.finish()['passed'])
        self.assertFalse(meter.result()['acceptedProof'])
        for value in (0,1201,True):
            with self.assertRaises(ValueError): TurnSkidMeasurement(value)

    def test_acceleration_stage_stops_input_when_last_acceleration_motion_starts(self):
        meter=TurnSkidMeasurement()
        meter.motions = [object()] * (ACCELERATION_MOTION_COUNT - 1)
        self.assertFalse(meter.stage('acceleration-complete'))
        meter.pending_events = [dict(event='MOTION_STARTED')]
        self.assertTrue(meter.stage('acceleration-complete'))

    def test_recovery_stage_releases_input_when_recovery_motion_starts(self):
        meter=TurnSkidMeasurement()
        meter.motions = [object()] * (MOTION_COUNT - 1)
        self.assertFalse(meter.stage('recovery-started'))
        meter.pending_events = [dict(event='MOTION_STARTED')]
        self.assertTrue(meter.stage('recovery-started'))

    def test_copied_data_controls_are_not_source_mutations(self):
        events=[dict(data=dict(observation='walk-matrix-tick',movingWalk=True,before=dict(elapsed=0))),
                dict(data=dict(observation='stomp-policy',effect=2,feedback=dict(dust=[{}]))),
                dict(data=dict(event='LOGICAL_COMMIT'))]
        snapshot=dict(actors=[dict(species=155,role='MOUNTED',handle=dict(value=7))])
        original=deepcopy(events)
        for fault in FAULTS:
            negative=TurnSkidNegative(fault)
            negative.mutate(dict(samples=[snapshot],events=events),
                            {'cyndaquil':dict(handle=dict(value=7))})
            self.assertTrue(validate_negative_result(negative.result(dict(passed=False,failures=['expected rejection']))))
        self.assertEqual(events,original)
        self.assertEqual(len(snapshot['actors']),1)
        with self.assertRaises(ValueError):TurnSkidNegative(FAULTS[0]).result(dict(passed=False,failures=['x']))


if __name__=='__main__':unittest.main()
