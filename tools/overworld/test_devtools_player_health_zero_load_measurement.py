"""Copied-data controls only; no claim of live recorder acceptance."""
from copy import deepcopy
import unittest
from tools.overworld.player_health_zero_load_fixture import prepare_bytes
from tools.overworld.test_player_health_zero_load_fixture import source
from tools.overworld.devtools_player_health_zero_load_measurement import (
    evaluate_known_receipts, require_complete,
)


def receipts():
    raw = source()
    fixture, manifest = prepare_bytes(raw)
    boot = {'romSha256': 'a' * 64, 'sourceSaveSha256': manifest['fixtureSha256'],
            'nativeCycle': 100,
            'bootRecovery': {'kind': 'player-health-pending-blackout',
                'boundary': 'paused-native-cycle-end', 'acceptedProof': False,
                'actorClockReady': False, 'recoveryInputSent': False,
                'saveSha256': manifest['fixtureSha256'], 'copyBase': 0, 'saveCount': 10,
                'hp': 0, 'checkpointSpawn': 3,
                'tasks': [{'pointer': 0x2100100, 'callback': 0x1FFA601, 'state': 4},
                          {'pointer': 0x2100200, 'callback': 0x1FFA501, 'state': 2}]}}
    final = {'romSha256': 'a' * 64, 'sourceSaveSha256': manifest['fixtureSha256'],
             'nativeCycle': 200, 'frame': 80, 'fieldAvailable': True,
             'observationBoundary': 'main-task-queue-completion',
             'fieldControl': {'taskPointer': 0},
             'party': [{'identityVerified': True, 'hp': 20, 'maxHp': 20, 'status': 0}]}
    hp = {'schemaVersion': 1, 'identity': {'romSha256': 'a' * 64, 'overlayId': 161,
           'overlaySha256': 'b' * 64, 'descriptorVersion': 1},
          'frame': 80, 'nativeCycle': 200,
          'observationBoundary': 'main-task-queue-completion',
          'hp': 100, 'savedHp': 100, 'recoveryPending': False,
          'pause': {'fieldTaskActive': False}, 'checkpointSpawn': 3,
          'economy': manifest['baselineEconomy']}
    return raw, fixture, boot, final, hp


class ZeroLoadMeasurementTests(unittest.TestCase):
    def test_complete_known_receipts_still_cannot_claim_acceptance(self):
        result = evaluate_known_receipts(*receipts())
        self.assertFalse(result['ready'])
        self.assertFalse(result['acceptedProof'])
        self.assertEqual(len(result['missingLiveFacts']), 2)
        with self.assertRaisesRegex(ValueError, 'acceptance is blocked'):
            require_complete(result)

    def test_missing_or_wrong_zero_identity_rejected(self):
        for fault in ('missing', 'healed-at-load', 'wrong-save', 'wrong-checkpoint', 'duplicate'):
            args = list(receipts()); boot = args[2]['bootRecovery']
            if fault == 'missing': args[2].pop('bootRecovery')
            elif fault == 'healed-at-load': boot['hp'] = 100
            elif fault == 'wrong-save': boot['saveSha256'] = 'd' * 64
            elif fault == 'wrong-checkpoint': boot['checkpointSpawn'] = 4
            else: boot['tasks'].insert(0, deepcopy(boot['tasks'][0]))
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                evaluate_known_receipts(*args)

    def test_final_state_faults_rejected(self):
        for fault in ('task', 'party-missing', 'party-hurt', 'party-status',
                      'hp', 'checkpoint', 'economy', 'boundary', 'rom', 'stale'):
            args = list(receipts()); final, hp = args[3:]
            if fault == 'task': final['fieldControl']['taskPointer'] = 123
            elif fault == 'party-missing': final.pop('party')
            elif fault == 'party-hurt': final['party'][0]['hp'] = 1
            elif fault == 'party-status': final['party'][0]['status'] = 1
            elif fault == 'hp': hp['hp'] = 99
            elif fault == 'checkpoint': hp['checkpointSpawn'] = 4
            elif fault == 'economy': hp['economy']['money'] += 1
            elif fault == 'boundary': final['fieldAvailable'] = False
            elif fault == 'rom': final['romSha256'] = 'd' * 64
            else: hp['nativeCycle'] -= 1
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                evaluate_known_receipts(*args)


if __name__ == '__main__':
    unittest.main()
