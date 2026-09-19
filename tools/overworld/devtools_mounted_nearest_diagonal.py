"""One measured UP Hop through the sealed nearest-diagonal landing fixture."""
from copy import deepcopy
from pathlib import Path

from .devtools_mounted_hop_arc import MountedHopArcMeasurement
from .devtools_mount_control_stress import require
from .devtools_mounted_hop_candidate_probe import linked_identity
from .devtools_records import select_current_actor

KIND = 'mounted-nearest-diagonal-v1'
REQUIREMENT = 'legacy.mankey-nearest-diagonal'
ORIGIN = [545, 392]


def candidate_order(minimum, maximum):
    """Straight, near heading (lateral first), then equal diagonals; UP frame."""
    targets = []
    for lateral in range(maximum + 1):
        for distance in range(maximum, minimum - 1, -1):
            magnitude = distance if lateral == maximum else lateral
            if lateral != maximum and magnitude >= distance:
                continue
            for sign in ((1,) if magnitude == 0 else (1, -1)):
                side = magnitude * sign
                targets.append(dict(target=[ORIGIN[0] + side, ORIGIN[1] - distance],
                                    category='straight' if side == 0 else 'equal' if magnitude == distance else 'near',
                                    distance=distance, lateral=side))
    return targets


def validate_probe(receipt, subject, snapshot):
    q = receipt.get('value', receipt)
    require(q.get('completed') is True and q.get('prepared') is True
            and q.get('acceptedProof') is False and q.get('batchAdvancedFrames') == 0
            and q.get('direction') == 'UP'
            and q.get('origin') == ORIGIN and q.get('scope') == 'prepared-mounted-hop-candidate-query'
            and receipt.get('preparedOnly') is True and receipt.get('acceptedProof') is False
            and q.get('guestMemoryWrites') == 0, 'nearest probe owner/scope differs')
    current = select_current_actor(snapshot, q.get('subject', {}))
    require(all(current.get(key) == value for key, value in subject.items()
                if key != 'observedFrame'), 'nearest probe subject differs')
    before, after = q.get('before'), q.get('after')
    require(isinstance(before, dict) and before == after, 'nearest probe changed state')
    require(receipt.get('snapshot') == snapshot
            and snapshot['frame'] in (before.get('frame'), before.get('frame', -2) + 1)
            and before.get('player') == snapshot['player'], 'nearest probe arm boundary differs')
    actor = next(a for a in snapshot['actors'] if a['handle'] == subject['handle'])
    require(all(before.get('actor', {}).get(k) == actor.get(k) for k in
                ('handle','subjectIdentity','species','role','sourceIdentity','engineIdentity','logical',
                 'motionPhase','reservationId','commitSequence','inputOwnership')),
            'nearest probe bound actor differs')
    profile = bytes.fromhex(q.get('profileHex', ''))
    raw = bytes.fromhex(before.get('mountStateHex',''))
    require(len(profile) == 72 and len(raw) == 184 and raw[8:80] == profile
            and profile[12] == 2 and (profile[19] & 0x03) == 1, 'nearest probe profile differs')
    minimum, maximum = profile[20] or 1, min(16, max(profile[20] or 1, profile[21]))
    require(1 <= minimum <= maximum <= 16
            and q.get('minDistance') == minimum and q.get('maxDistance') == maximum,
            'nearest probe profile differs')
    require(q.get('serviceIdentity') == linked_identity(Path(__file__).resolve().parents[2]),
            'nearest probe service identity differs')
    expected = candidate_order(minimum, maximum)
    queries = q.get('rows', [])
    calls = receipt.get('calls', q.get('calls', []))
    require(len(queries) == len(expected) == len(calls), 'nearest probe candidate coverage differs')
    addresses = set()
    for query, target, call in zip(queries, expected, calls):
        require(all(query.get('kind' if k == 'category' else k) == value for k, value in target.items())
                and type(query.get('result')) is int and query['result'] in (0,1), 'nearest probe candidate order differs')
        require(call.get('routine') == 'mount_hop_landing'
                and call.get('requestedArguments') == target['target']
                and type(call.get('returnValue')) is int and call['returnValue'] in (0, 1)
                and query['result'] == call['returnValue']
                and type(call.get('address')) is int and 0x02000000 <= call['address'] < 0x02400000,
                'nearest probe native landing receipt differs')
        addresses.add(call['address'])
    require(addresses == {q.get('serviceIdentity',{}).get('OverworldMount_IsLandingTileAllowed',{}).get('address')},
            'nearest probe native entry changed')
    require(not any(v['result'] == 1 for v in queries if v['kind'] == 'straight'),
            'nearest probe straight landing remains open')
    near = [v['target'] for v in queries if v['kind'] == 'near' and v['result'] == 1]
    equal = [v['target'] for v in queries if v['kind'] == 'equal' and v['result'] == 1]
    require(near and equal and q.get('orderedNearTargets') == near and q.get('equalDiagonalTargets') == equal,
            'nearest probe missing or reordered alternatives')
    return deepcopy(dict(direction='UP', start=ORIGIN, orderedNearTargets=near,
                         equalDiagonalTargets=equal, chosen=near[0], final=near[0]))


class MountedNearestDiagonalMeasurement(MountedHopArcMeasurement):
    def __init__(self, max_frames=1600):
        super().__init__(max_frames)
        self.rules['motions'] = 1
        self.probe_receipt = None
        self.choice = None
        self.arm_snapshot = None

    def arm(self, subject, snapshot, probe_receipt, trace_sequences=None):
        choice = validate_probe(probe_receipt, subject, snapshot)
        super().arm(subject, snapshot, trace_sequences)
        require([self.actor['logical'][k] for k in ('x', 'y')] == ORIGIN, 'nearest Hop origin differs')
        self.choice = choice
        self.probe_receipt = deepcopy(probe_receipt)
        self.arm_snapshot = deepcopy(snapshot)

    def _start(self, event, snapshot, actor):
        data = event['data']; start = data.get('start', {})
        require(self.pending_start is None and self.recorder.current is None and not self.cases,
                'duplicate or extra nearest Hop start')
        require(event.get('kind') == 'native-observation' and data.get('subject') == self.subject,
                'nearest Hop start subject differs')
        require(type(data.get('entryNativeCycle')) is int and type(data.get('returnNativeCycle')) is int
                and self.last['nativeCycle'] <= data['entryNativeCycle'] <= data['returnNativeCycle'] <= snapshot['nativeCycle'],
                'nearest Hop start clock differs')
        require(type(start.get('elapsed')) is int and start['elapsed'] == 0
                and type(start.get('duration')) is int and 0 < start['duration'] <= self.max_frames
                and start['duration'] == actor['motionDuration']
                and start.get('origin') == actor['origin'] == dict(zip(('x','y'), ORIGIN))
                and start.get('target') == actor['target'] == dict(zip(('x','y'), self.choice['chosen']))
                and type(start.get('motionIdentity')) is int and start['motionIdentity'] > 0
                and start['motionIdentity'] == actor['reservationId']
                and type(start.get('baseFaceY')) is int and type(start.get('faceY')) is int
                and start['faceY'] == start['baseFaceY'], 'nearest Hop native start/choice differs')
        require(snapshot['selector'].get('rawHeld',0) & 0xF0 == 64
                and snapshot['selector'].get('heldKeys',snapshot['selector'].get('rawHeld',0)) & 0xF0 == 64,
                'nearest Hop lacks natural UP input')
        self.pending_start = deepcopy(event)
        self.start_snapshot = deepcopy(snapshot)
        self.previous_native_cycle = self.last['nativeCycle']
        self.arc_samples = [[0, start['faceY'] - start['baseFaceY']]]
        self.arc_frames = []

    @property
    def ready(self):
        return not self.failures and len(self.cases) == 1 and self.pending_start is None and not self.traces

    def finish(self):
        if not self.ready and not self.failures:
            self.failures.append('one complete nearest Hop required')
        self.closed = True
        return self.result()

    def result(self, *_args):
        result = super().result()
        result.update(kind=KIND, contract=REQUIREMENT, probeReceipt=deepcopy(self.probe_receipt),
                      armSnapshot=deepcopy(self.arm_snapshot), choice=deepcopy(self.choice))
        return result
