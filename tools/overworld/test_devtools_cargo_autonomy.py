"""Copied native receipts detect pre-pickup control/profile/motion changes.

These host controls exercise the shared reader. They are not game proof.
Both registered moving-cargo cases still need fresh current-ROM acceptance.
"""
from copy import deepcopy
import struct
import unittest

from tools.overworld.devtools_moving_cargo_pickup import CargoAutonomy, verify_cargo_autonomy
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.test_devtools_wild_throw_moving_candidate_measurement import current, pickup_events, SOURCE
from tools.overworld.test_devtools_follower_throw_measurement import moving_stream, evaluate, KIND


def wild_fixture():
    samples = [current(f, target=True, source=True) for f in range(19, 24)]
    for sample in samples:
        next(a for a in sample['actors'] if a['species'] == 234).update(behaviorFingerprint=0, matchedLayerMask=0)
    actor = next(a for a in samples[0]['actors'] if a['species'] == 234)
    lane = bytearray(80); lane[0] = 1; lane[7] = 14
    raw = bytearray(lane + lane + bytes(56))
    struct.pack_into('<II', raw, 188, actor.get('matchedLayerMask', 0), actor['behaviorFingerprint'])
    source = dict(SOURCE, contractVersion=2, profileSha256='c'*64)
    profile = dict(observation='behavior-resolved', resolved=True, sourceSha256=source['profileSha256'],
        resultHex=raw.hex(), fingerprint=actor['behaviorFingerprint'], appliedOverrides=actor.get('matchedLayerMask',0),
        lanes=[lane.hex(),lane.hex()])
    events = [dict(frame=19, kind='native-observation', data=profile)] + pickup_events(samples[-1])
    return samples, events, source, profile


def wild_read(samples, events, source, profile):
    meter = CargoAutonomy(source)
    for sample in samples:
        actor = next(a for a in sample['actors'] if a['species'] == 234)
        value = sample['pokemonCombat']['interactions']['throwState']['targets'][1]
        meter.observe(sample, actor, [e for e in events if e['frame'] == sample['frame']],
                      {profile['fingerprint']: profile}, claimed=bool(value), held=bool(value & 128))
    return meter.result()


class CargoAutonomyTest(unittest.TestCase):
    def test_wild_target_keeps_profile_auto_and_motion_until_actual_held(self):
        samples, events, source, profile = wild_fixture()
        witness = wild_read(samples, events, source, profile)
        self.assertTrue(witness['ready'])
        self.assertEqual(witness['freeClaimFrames'], 3)
        subject = select_current_actor(samples[0], samples[0]['actors'][0])
        self.assertEqual(verify_cargo_autonomy(witness, [dict(samples=samples, events=events)], source, subject), witness)

    def test_claim_cannot_take_control_change_profile_stop_or_cancel_target(self):
        for fault in ('held-before-pickup', 'changed-profile', 'stopped-motion', 'stopped-body', 'early-cancel'):
            samples, events, source, profile = wild_fixture()
            sample = samples[2]; actor = next(a for a in sample['actors'] if a['species'] == 234)
            if fault == 'held-before-pickup':
                timer = next(t for t in sample['pokemonCombat']['movementTimers'] if t['handle'] == actor['handle'])
                timer['movementActorControlMode'] = 1
            elif fault == 'changed-profile':
                actor['behaviorFingerprint'] += 1
            elif fault == 'stopped-motion':
                row = next(t for t in sample['pokemonCombat']['targets'] if t['handle'] == actor['handle'])
                raw = bytearray.fromhex(row['motion']['rawHex']); struct.pack_into('<H',raw,40,2)
                row['motion'] = decode_motion(bytes(raw)); actor['motionElapsed'] = 2
            elif fault == 'stopped-body':
                previous = next(a for a in samples[1]['actors'] if a['species'] == 234)
                actor['engineObject'].update({k:previous['engineObject'][k] for k in ('pos_x','pos_z')})
            else:
                event = deepcopy(pickup_events(samples[-1])[0]); event['frame'] = sample['frame']; events.append(event)
            with self.subTest(fault=fault), self.assertRaisesRegex(ValueError, 'pickup'):
                wild_read(samples, events, source, profile)

    def test_follower_target_uses_same_free_target_and_held_checks(self):
        rows = moving_stream(); result = evaluate(rows)
        self.assertTrue(result['passed'], result['failures'])
        value = result['measurements'][KIND]; witness = value['cargoAutonomy']
        self.assertTrue(witness['ready'])
        self.assertEqual(verify_cargo_autonomy(witness, None, value['source'], value['subjects']['cargo']), witness)
        for fault in ('missing-baseline', 'early-held-control', 'changed-profile', 'stopped-motion'):
            copied = deepcopy(witness)
            if fault == 'missing-baseline': copied['baseline']['profile']['resultHex'] = ''
            else:
                sample = copied['movingProgress']['current']
                actor = next(a for a in sample['actors'] if a['handle'] == value['subjects']['cargo']['handle'])
                if fault == 'changed-profile': actor['behaviorFingerprint'] += 1
                elif fault == 'early-held-control':
                    next(t for t in sample['pokemonCombat']['movementTimers'] if t['handle'] == actor['handle'])['movementActorControlMode'] = 1
                else:
                    row = next(t for t in sample['pokemonCombat']['targets'] if t['handle'] == actor['handle'])
                    raw = bytearray.fromhex(row['motion']['rawHex']); struct.pack_into('<H',raw,40,row['motion']['elapsed']-1)
                    row['motion'] = decode_motion(bytes(raw))
            with self.subTest(fault=fault), self.assertRaisesRegex(ValueError, 'pickup'):
                verify_cargo_autonomy(copied, None, value['source'], value['subjects']['cargo'])


if __name__ == '__main__': unittest.main()
