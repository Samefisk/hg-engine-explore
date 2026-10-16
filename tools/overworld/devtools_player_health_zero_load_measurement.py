"""Fail-closed partial evaluator for retained zero-load native receipts.

This is deliberately not registered as accepted proof. Current receipts prove
one pending chain at boot, not a count of starts over the complete transition.
Do not turn a final healthy snapshot into proof of a complete recovery history.
"""
from tools.overworld.player_health_zero_load_fixture import verify_fixture

KIND = 'player-health-zero-load-v1'
MISSING_LIVE_FACTS = (
    'complete native recovery-start/end history from Continue through movement',
    'stock checkpoint destination and bounded normal movement/input-release trace',
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def evaluate_known_receipts(source_save, fixture_save, boot_snapshot,
                            final_snapshot, player_health):
    """Validate existing shapes, return partial facts, never an acceptance pass.

    Inputs are unmodified snapshot/HP observer results plus the two raw saves.
    Callers must retain ROM identity and source files with the eventual trace.
    """
    fixture = verify_fixture(source_save, fixture_save)
    boot = boot_snapshot.get('bootRecovery', {})
    require(boot.get('kind') == 'player-health-pending-blackout'
            and boot.get('boundary') == 'paused-native-cycle-end'
            and boot.get('acceptedProof') is False
            and boot.get('actorClockReady') is False
            and boot.get('recoveryInputSent') is False,
            'missing authenticated pending-blackout boundary')
    require(boot.get('saveSha256') == fixture['fixtureSha256']
            and boot_snapshot.get('sourceSaveSha256') == fixture['fixtureSha256']
            and boot.get('copyBase') == fixture['copyBase']
            and boot.get('saveCount') == fixture['saveCount']
            and boot.get('hp') == 0
            and boot.get('checkpointSpawn') == fixture['checkpointSpawn'],
            'loaded zero/save/checkpoint differs from checked fixture')
    tasks = boot.get('tasks')
    require(isinstance(tasks, list) and 2 <= len(tasks) <= 8,
            'pending blackout task chain missing')
    require(all(type(t.get('pointer')) is int and t['pointer'] > 0
                and type(t.get('callback')) is int and t['callback'] & 1
                and type(t.get('state')) is int for t in tasks)
            and len({t['pointer'] for t in tasks}) == len(tasks)
            and tasks[-1]['state'] == 2
            and 1 <= tasks[-2]['state'] <= 6
            and tasks[-1]['callback'] != tasks[-2]['callback']
            and all(sum(t['callback'] == target['callback'] for t in tasks) == 1
                    for target in tasks[-2:]),
            'pending blackout chain is duplicate or invalid')
    rom = boot_snapshot.get('romSha256')
    require(isinstance(rom, str) and len(rom) == 64
            and final_snapshot.get('romSha256') == rom
            and final_snapshot.get('sourceSaveSha256') == fixture['fixtureSha256'],
            'ROM/save identity changed across recovery')
    require(final_snapshot.get('observationBoundary') == 'main-task-queue-completion'
            and final_snapshot.get('fieldAvailable') is True
            and final_snapshot.get('fieldControl', {}).get('taskPointer') == 0
            and type(final_snapshot.get('nativeCycle')) is int
            and type(boot_snapshot.get('nativeCycle')) is int
            and final_snapshot['nativeCycle'] > boot_snapshot['nativeCycle'],
            'recovery has no later free-field boundary')
    identity = player_health.get('identity', {})
    require(player_health.get('schemaVersion') == 1
            and identity.get('romSha256') == rom
            and identity.get('overlayId') == 161
            and identity.get('descriptorVersion') == 1
            and isinstance(identity.get('overlaySha256'), str)
            and len(identity['overlaySha256']) == 64
            and player_health.get('frame') == final_snapshot.get('frame')
            and player_health.get('nativeCycle') == final_snapshot.get('nativeCycle')
            and player_health.get('observationBoundary') == final_snapshot.get('observationBoundary'),
            'HP receipt is not bound to final native boundary')
    require(player_health.get('hp') == 100 and player_health.get('savedHp') == 100
            and player_health.get('recoveryPending') is False
            and player_health.get('pause', {}).get('fieldTaskActive') is False
            and player_health.get('checkpointSpawn') == fixture['checkpointSpawn'],
            'player HP/checkpoint did not restore at task release')
    economy = player_health.get('economy', {})
    require(economy.get('version') == 1 and type(economy.get('money')) is int
            and 0 <= economy['money'] <= 999999 and economy.get('bagSize') == 2448
            and isinstance(economy.get('bagSha256'), str)
            and len(economy['bagSha256']) == 64
            and economy == fixture['baselineEconomy'],
            'money or bag differs from the loaded fixture')
    party = final_snapshot.get('party')
    require(isinstance(party, list) and 1 <= len(party) <= 6,
            'final party observation missing')
    require(all(p.get('identityVerified') is True
                and type(p.get('maxHp')) is int and p['maxHp'] > 0
                and p.get('hp') == p['maxHp'] and p.get('status') == 0
                for p in party), 'party is not fully healed')
    return {'kind': KIND, 'ready': False, 'acceptedProof': False,
            'checkedFacts': ['fixture-byte-preservation', 'observed-zero-pending-blackout',
                             'one-concurrent-blackout-chain', 'player-restored-at-task-release',
                             'party-full-at-final-boundary', 'money-and-bag-unchanged'],
            'missingLiveFacts': list(MISSING_LIVE_FACTS)}


def require_complete(result):
    """Do not let callers mistake partial evidence for runtime acceptance."""
    raise ValueError('zero-load acceptance is blocked: ' + '; '.join(MISSING_LIVE_FACTS))
