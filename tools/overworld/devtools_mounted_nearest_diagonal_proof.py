"""Independent rows and copied-data controls for the one nearest-diagonal Hop."""
from copy import deepcopy

from .devtools_mounted_nearest_diagonal import KIND, REQUIREMENT, validate_probe
from .devtools_mounted_hop_arc import arc_height
from .devtools_mounted_hop_arc_proof import MountedHopArcNegative
from .devtools_mount_control_stress import LIFECYCLE, require, check_snapshot_pair
from .devtools_records import select_current_actor
from .normal_play_observer import complete_travel

CLAIMS = ('natural-input', 'live-actor-identity', 'rendered-motion', 'control-release')
FAULTS = ('nearest-probe-order', 'nearest-probe-return', 'nearest-probe-service', 'nearest-absent-subject',
          'nearest-stale-subject', 'nearest-missing-start', 'nearest-bad-height', 'nearest-missing-finish')


def contract():
    return {
        'natural-input': [dict(name='nearest-diagonal-input-milestones', operator='eq', type='integer',
                               validator='meaningful-observation', expected=3)],
        'live-actor-identity': [dict(name='nearest-diagonal-mankey-identity', operator='eq', type='array',
                                   validator='meaningful-observation', expected=[1,'MOUNTED',56,1])],
        'rendered-motion': [dict(name='nearest-diagonal-arc-samples', operator='eq', type='object',
                                validator='hop-arc-parabola-v1', caseCount=1, requiredKeys=['cases'])],
        'control-release': [dict(name='nearest-diagonal-terminal-tile', operator='eq', type='object',
                                validator='nearest-diagonal-choice-v1',
                                requiredKeys=['direction','start','orderedNearTargets','equalDiagonalTargets','chosen','final'])],
    }


def measurements(result):
    meter = result.get('measurements', {}).get(KIND, result)
    require(result.get('passed') is True and result.get('failures') == []
            and meter.get('passed') is True and meter.get('closed') is True
            and meter.get('acceptedProof') is False and meter.get('failures') == []
            and meter.get('contract') == REQUIREMENT, 'nearest Hop lacks closed independent replay')
    choice = validate_probe(meter['probeReceipt'], meter['subject'], meter['armSnapshot'])
    require(meter['choice'] == choice and len(meter['cases']) == 1, 'nearest proof choice/count differs')
    case = meter['cases'][0]; motion = case['summary']['motion']; actor = meter['initial']['actor']
    first = case['startSnapshot']; receipt = case['startReceipt']; data = receipt['data']; start = data['start']
    select_current_actor(first, meter['subject'])
    current = next(a for a in first['actors'] if a['handle'] == actor['handle'])
    check_snapshot_pair(first, current)
    require(actor['species'] == 56 and actor['role'] == 'MOUNTED' and actor['inputOwnership'] == 1
            and actor['identityVerified'] is True and actor['presentationAttached'] is True
            and actor['handle'] == meter['subject']['handle'] and current['reservationId'] == start['motionIdentity'] > 0,
            'nearest proof identity differs')
    require(first['context'] == meter['initial']['context'] and first['selector']['rawHeld'] & 0xF0 == 64
            and first['frame'] == receipt['frame'] == motion['startFrame']
            and receipt['kind'] == 'native-observation' and data['observation'] == 'mounted-hop-start'
            and data['subject'] == meter['subject'] and start['elapsed'] == 0
            and case['previousNativeCycle'] <= data['entryNativeCycle'] <= data['returnNativeCycle'] <= first['nativeCycle']
            and start['faceY'] == start['baseFaceY'], 'nearest proof native start differs')
    require(complete_travel(motion) and motion['kind'] == 'HOP'
            and motion['handle'] == actor['handle'] and motion['fingerprint'] == actor['behaviorFingerprint']
            and motion['commitAfter'] == (motion['commitBefore'] + 1) & 0xFFFFFFFF
            and motion['origin'] == choice['start']
            and motion['target'] == motion['terminalLogical'] == choice['chosen']
            and [start['origin'][k] for k in ('x','y')] == choice['start']
            and [start['target'][k] for k in ('x','y')] == choice['chosen']
            and start['duration'] == motion['duration'], 'nearest proof motion/target differs')
    duration = motion['duration']; observations = case['observations']
    expected = [[i, arc_height(i,duration)] for i in range(duration+1)]
    require(case['samples'] == expected and len(observations) == duration
            and [[v['elapsed'],v['faceY']-start['baseFaceY']] for v in observations] == expected[1:]
            and [v['frame'] for v in observations] == list(range(motion['startFrame'],motion['startFrame']+duration)),
            'nearest proof arc differs')
    lifecycle = case['summary']['lifecycle']
    require([e['event'] for e in lifecycle] == list(LIFECYCLE)
            and all(e['reason'] == 'OK' and e['actorHandle'] == actor['handle']['value'] for e in lifecycle)
            and [(e['valueA'],e['valueB']) for e in lifecycle] == [(2,duration),(motion['commitAfter'],2),
                (motion['commitAfter'],2),(1,motion['commitAfter'])]
            and [e['sequence'] for e in lifecycle] == sorted(set(e['sequence'] for e in lifecycle)),
            'nearest proof lifecycle differs')
    terminal = case['terminalActor']
    require(meter['initial']['frame'] < motion['startFrame'] <= motion['commitFrame'] <= motion['finishFrame']
            == case['terminalFrame'] <= meter['initial']['frame'] + meter['frames']
            and terminal['handle'] == actor['handle'] and terminal['species'] == 56
            and terminal['role'] == 'MOUNTED' and terminal['motionPhase'] == 'IDLE'
            and terminal['inputOwnership'] == 1 and terminal['reservationId'] == 0
            and [terminal['logical'][k] for k in ('x','y')] == choice['chosen']
            and [terminal['engineObject'][k] for k in ('pos_x','pos_z')]
                == [(v << 16) + 32768 for v in choice['chosen']],
            'nearest proof terminal differs')
    values = (3, [1,'MOUNTED',56,1], dict(cases=[dict(duration=duration,samples=case['samples'])]), choice)
    return [dict(claim=claim,name=contract()[claim][0]['name'],operator='eq',actual=deepcopy(value),expected=deepcopy(value))
            for claim,value in zip(CLAIMS,values)]


class MountedNearestDiagonalNegative:
    def __init__(self, fault):
        require(fault in FAULTS, 'unknown nearest Hop fault')
        self.fault, self.applied = fault, False
        self.delegate = None if fault.startswith('nearest-probe-') else MountedHopArcNegative(fault.replace('nearest-','hop-arc-',1))

    def mutate(self, row, subjects):
        if self.applied:
            return row
        if self.delegate is not None:
            changed = self.delegate.mutate(row, subjects)
            self.applied = self.delegate.applied
            return changed
        changed = deepcopy(row)
        receipt = changed.get('receipt', {})
        q = receipt.get('value', receipt)
        if not q.get('rows'):
            return row
        if self.fault == 'nearest-probe-order':
            q['rows'][0],q['rows'][1] = q['rows'][1],q['rows'][0]
        elif self.fault == 'nearest-probe-return':
            calls = receipt.get('calls',q.get('calls',[]))
            if not calls:return row
            calls[0]['returnValue'] = 1-calls[0]['returnValue']
        else:
            service = q.get('serviceIdentity', {}).get('OverworldMount_TryNextHopLandingCandidate.constprop.0')
            if not isinstance(service, dict): return row
            service['sha256'] = '0' * 64
        self.applied = True
        return changed


Negative = MountedNearestDiagonalNegative


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get('passed') is False, 'nearest copied control did not fail')
    strings=[]
    def visit(value):
        if isinstance(value,str):strings.append(value)
        elif isinstance(value,dict):
            for item in value.values():visit(item)
        elif isinstance(value,list):
            for item in value:visit(item)
    visit(result.get('failures',[]));visit(result.get('measurements',{}).get(KIND,{}).get('failures',[]))
    expected = {'nearest-probe-order':'nearest probe candidate order differs',
                'nearest-probe-return':'nearest probe native landing receipt differs',
                'nearest-probe-service':'nearest probe service identity differs',
                'nearest-absent-subject':'missing or duplicate mounted subject',
                'nearest-stale-subject':'ownership changed',
                'nearest-missing-start':'missing real native Hop start receipt',
                'nearest-bad-height':'Hop arc parabola differs',
                'nearest-missing-finish':'missing/duplicate native MOTION_FINISHED'}[fault]
    require(any(expected in value for value in strings), 'nearest control failed for an unrelated reason: '+fault)
