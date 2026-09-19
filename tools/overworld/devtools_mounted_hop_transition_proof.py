"""Exact legacy mounted Hop transition acceptance rows and copied-data faults."""
from copy import deepcopy
from tools.overworld.devtools_mounted_hop_transition_measurement import KIND, REQUIREMENT, require, validate_elapsed
from tools.overworld.devtools_mounted_walk_transition_measurement import same_lifetime
from tools.overworld.normal_play_observer import complete_travel

CONTRACT = {'natural-input': [{'name': 'map-transition-input-frame', 'operator': 'gte', 'type': 'integer', 'validator': 'meaningful-observation', 'minimum': 0, 'maximum': 2499}, {'name': 'transition-stress-input-frame-count', 'operator': 'gte', 'type': 'integer', 'validator': 'meaningful-observation', 'minimum': 5000}], 'live-actor-identity': [{'name': 'mounted-transition-mankey-identity', 'operator': 'eq', 'type': 'array', 'validator': 'meaningful-observation', 'expected': [1, 'MOUNTED', 56, 1]}, {'name': 'transition-actor-ownership-mismatch-count', 'operator': 'eq', 'type': 'integer', 'validator': 'meaningful-observation', 'expected': 0}], 'rendered-motion': [{'name': 'transition-motion-elapsed', 'operator': 'eq', 'type': 'object', 'validator': 'contiguous-elapsed-v1', 'requiredKeys': ['start', 'duration', 'elapsed']}, {'name': 'transition-pair-sync-samples', 'operator': 'eq', 'type': 'array', 'validator': 'all-render-samples-synced-v1'}], 'world-transition': [{'name': 'mounted-map-change', 'operator': 'eq', 'type': 'array', 'validator': 'meaningful-observation', 'expected': [33, 60]}], 'control-release': [{'name': 'post-transition-recovery', 'operator': 'eq', 'type': 'array', 'validator': 'meaningful-observation', 'expected': ['IDLE', 0, 1]}]}


CLAIMS = tuple(CONTRACT)


def contract():return deepcopy(CONTRACT)


def measurements(replay, record):
    m = replay.get('measurements',{}).get(KIND,{})
    require(replay.get('passed') is True and replay.get('failures') == []
            and m.get('passed') is True and m.get('closed') is True and m.get('ready') is True
            and m.get('acceptedProof') is False and m.get('failures') == []
            and m.get('requirements') == [REQUIREMENT], 'closed independent replay missing')
    require(record.get('sessionCleanup') == dict(sessionId=record.get('sessionId'),closed=True,errors=[]), 'private session did not close')
    def actor(snapshot, subject):
        matches=[a for a in snapshot['actors'] if a['handle']==subject['handle']]
        require(len(matches)==1, 'missing exact actor')
        return matches[0]
    before=actor(m['initial'],m['initialSubject']); crossing=actor(m['transition'],m['subject']); final=actor(m['terminal'],m['subject'])
    validate_elapsed(crossing['motionElapsed'],crossing['motionDuration'],m['elapsed'])
    require(same_lifetime(before['handle'],final['handle']) and before['subjectIdentity']==final['subjectIdentity']
            and before['species']==crossing['species']==final['species']==56
            and [m['initial']['context']['mapId'],m['transition']['context']['mapId']]==[33,60], 'identity/map differs')
    require(m['postTransitionInputFrames']>=5000 and m['recoveryMotions']
            and all(x['kind']=='HOP' and complete_travel(x['motion']) for x in m['recoveryMotions']), 'post-transition input/recovery missing')
    pair=m['pairSamples'];require(pair and all(x['player']==x['mount'] for x in pair), 'paired render differs')
    require(final['motionPhase']=='IDLE' and final['reservationId']==0 and final['inputOwnership']==1, 'control did not recover')
    values={
        'map-transition-input-frame':m['transition']['frame']-m['initial']['frame']-1,
        'transition-stress-input-frame-count':m['postTransitionInputFrames'],
        'mounted-transition-mankey-identity':[1,final['role'],final['species'],int(final['presentationAttached'])],
        'transition-actor-ownership-mismatch-count':0,
        'transition-motion-elapsed':dict(start=crossing['motionElapsed'],duration=crossing['motionDuration'],elapsed=m['elapsed']),
        'transition-pair-sync-samples':[sum(x['player']==x['mount'] for x in pair),len(pair)],
        'mounted-map-change':[m['initial']['context']['mapId'],m['transition']['context']['mapId']],
        'post-transition-recovery':[final['motionPhase'],final['reservationId'],final['inputOwnership']],
    }
    return [dict(claim=claim,name=spec['name'],value=deepcopy(values[spec['name']]),operator=spec['operator'],
                 expected=deepcopy(spec.get('expected')),passed=True) for claim,rows in CONTRACT.items() for spec in rows]


FAULTS=('mounted-hop-transition-absent-subject','mounted-hop-transition-bad-elapsed',
        'mounted-hop-transition-bad-pair','mounted-hop-transition-missing-rebind')


class MountedHopTransitionNegative:
    def __init__(self, fault):
        require(fault in FAULTS, 'unknown negative fault')
        self.fault = fault
        self.applied = False

    def mutate(self, row, subjects):
        if self.applied or row.get('phase') != 'observe' or not subjects:
            return row
        changed = deepcopy(row)
        subject = next(iter(subjects.values()))
        identity = subject['subjectIdentity']
        for sample in changed.get('samples', []):
            actor = next((a for a in sample.get('actors', [])
                          if a.get('subjectIdentity') == identity and a.get('role') == 'MOUNTED'), None)
            if actor is None: continue
            if self.fault == FAULTS[0]:
                sample['actors'].remove(actor); self.applied = True
            elif sample['context']['mapId'] == 60:
                if self.fault == FAULTS[1]:actor['motionElapsed'] = 0; self.applied = True
                elif self.fault == FAULTS[2]:sample['player']['pos_x'] += 1; self.applied = True
            if self.applied: return changed
        if self.fault == FAULTS[3]:
            for event in changed.get('events', []):
                data = event.get('data', {})
                handle = dict(value=data.get('actorHandle'), **data.get('actor', {}))
                if data.get('event') == 'ACTOR_REBOUND' and same_lifetime(handle, subject['handle']):
                    data['event'] = 'WORLD_EFFECT'; self.applied = True; return changed
        return row


Negative = MountedHopTransitionNegative


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get('passed') is False, 'copied control did not reject')
    text = repr(result.get('failures', [])) + repr(result.get('measurements', {}).get(KIND, {}).get('failures', []))
    expected = {
        FAULTS[0]: 'selected handle must name exactly one current active actor',
        FAULTS[1]: 'rebind did not preserve in-flight Hop',
        FAULTS[2]: 'player/presentation base positions differ',
        FAULTS[3]: 'missing transition lifecycle',
    }[fault]
    require(expected in text, 'copied control failed for unrelated reason: ' + fault)
