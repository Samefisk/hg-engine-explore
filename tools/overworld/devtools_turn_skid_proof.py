"""Exact legacy turn-skid proof rows over independently replayed native data."""
from copy import deepcopy
from tools.overworld.devtools_turn_skid_measurement import (
    ACCELERATION_MOTION_COUNT, KIND, MOTION_COUNT, REQUIREMENT, require,
    validate_motion, validate_dust,
)

CLAIMS = ('natural-input', 'live-actor-identity', 'logical-commit',
          'rendered-motion', 'frame-pacing', 'feedback-effect', 'control-release')
CONTRACT = {'natural-input': [{'name': 'turn-skid-acceleration-durations', 'operator': 'eq', 'type': 'array', 'validator': 'meaningful-observation', 'expected': [8, 8, 8, 7, 7, 7, 6, 6, 6, 5, 5, 5, 4]}], 'live-actor-identity': [{'name': 'mounted-cyndaquil-identity-flags', 'operator': 'eq', 'type': 'array', 'validator': 'meaningful-observation', 'expected': [1, 'MOUNTED', 155, 1, 1, 1]}], 'logical-commit': [{'name': 'turn-skid-terminal-boundaries-and-target', 'operator': 'eq', 'type': 'object', 'validator': 'terminal-boundary-target-v1', 'requiredCount': 3, 'requiredKeys': ['boundaryCount', 'final', 'target']}], 'rendered-motion': [{'name': 'turn-skid-pair-and-facing', 'operator': 'eq', 'type': 'array', 'validator': 'meaningful-observation', 'expected': [0, 2, 2]}, {'name': 'turn-skid-facing-through-drift', 'operator': 'eq', 'type': 'array', 'validator': 'meaningful-observation', 'expected': [3, 2, 16]}], 'frame-pacing': [{'name': 'turn-skid-motion-schedules', 'operator': 'eq', 'type': 'array', 'validator': 'meaningful-observation', 'expected': [[0, 1, 2, 3, 4, 5, 6, 7], [0, 1, 2, 3, 4, 5, 6, 7], [0, 1, 2, 3, 4]]}], 'feedback-effect': [{'name': 'turn-skid-dust-effect-count', 'operator': 'eq', 'type': 'integer', 'validator': 'meaningful-observation', 'expected': 1}], 'control-release': [{'name': 'turn-skid-recovery-state', 'operator': 'eq', 'type': 'array', 'validator': 'turn-skid-recovery-v1'}]}


def contract():
    return deepcopy(CONTRACT)


def measurements(replay, record):
    meter = replay.get('measurements', {}).get(KIND, {})
    require(replay.get('passed') is True and replay.get('failures') == []
            and meter.get('passed') is True and meter.get('ready') is True
            and meter.get('closed') is True and meter.get('acceptedProof') is False
            and meter.get('failures') == [] and meter.get('requirements') == [REQUIREMENT],
            'closed independent replay missing')
    require(record.get('sessionCleanup') == dict(sessionId=record.get('sessionId'), closed=True, errors=[]),
            'private session cleanup missing')
    motions = meter['motions']
    require(len(motions) == MOTION_COUNT and len(meter['dust']) == 1, 'exact motions/dust missing')
    plans = [validate_motion(m, i) for i,m in enumerate(motions)]
    initial = next(a for a in meter['initial']['actors'] if a['handle'] == meter['subject']['handle'])
    terminal = next(a for a in meter['terminal']['actors'] if a['handle'] == meter['subject']['handle'])
    validate_dust(meter['dust'][0], meter['subject'], initial, meter['initial']['context'])
    require(initial['species'] == terminal['species'] == 155 and terminal['role'] == 'MOUNTED'
            and terminal['motionPhase'] == 'IDLE' and terminal['reservationId'] == 0
            and terminal['inputOwnership'] == 1 and terminal['presentationAttached'] is True,
            'terminal mounted recovery differs')
    final = [terminal['logical'][k] for k in ('x','y')]
    require(final == plans[-1]['target'] and terminal['engineObject']['facing'] == 2
            and meter['terminal']['player']['facing'] == 2, 'terminal position/facing differs')
    values = {
        'turn-skid-acceleration-durations': [
            p['duration'] for p in plans[:ACCELERATION_MOTION_COUNT]],
        'mounted-cyndaquil-identity-flags': [1, terminal['role'], terminal['species'],
            int(terminal['presentationAttached']), int(terminal['engineIdentity']['anchorInCurrentManager']),
            terminal['inputOwnership']],
        'turn-skid-terminal-boundaries-and-target': dict(boundaryCount=sum(
            sum(e['event']=='LOGICAL_COMMIT' for e in m['events'])
            for m in motions[ACCELERATION_MOTION_COUNT:]),
            final=final, target=plans[-1]['target']),
        'turn-skid-pair-and-facing': [0, meter['terminal']['player']['facing'], terminal['engineObject']['facing']],
        'turn-skid-facing-through-drift': [plans[ACCELERATION_MOTION_COUNT]['direction'],
            plans[ACCELERATION_MOTION_COUNT]['facing'], len(meter['skidFacingFrames'])],
        'turn-skid-motion-schedules': [
            [t['before']['elapsed'] for t in m['ticks']]
            + [m['ticks'][-1]['after']['elapsed']]
            for m in motions[ACCELERATION_MOTION_COUNT:]],
        'turn-skid-dust-effect-count': len(meter['dust']),
        'turn-skid-recovery-state': [int(terminal['motionPhase']=='IDLE'), motions[-1]['commitBefore']+1,
            terminal['commitSequence'], terminal['reservationId'], terminal['inputOwnership']],
    }
    return [dict(claim=claim, name=spec['name'], value=deepcopy(values[spec['name']]),
                 operator=spec['operator'], expected=deepcopy(spec.get('expected')), passed=True)
            for claim, specs in CONTRACT.items() for spec in specs]


FAULTS = ('turn-skid-absent-subject', 'turn-skid-bad-elapsed', 'turn-skid-missing-dust',
          'turn-skid-missing-commit', 'turn-skid-old-facing')


class TurnSkidNegative:
    def __init__(self, fault):
        require(fault in FAULTS, 'unknown copied-data fault')
        self.fault = fault
        self.mutated = False

    @property
    def applied(self):
        return self.mutated

    def mutate(self, row, subjects):
        if self.mutated: return row
        changed = deepcopy(row)
        handles = {subject['handle']['value'] for subject in subjects.values()}
        if self.fault == FAULTS[0]:
            for snapshot in changed.get('samples', []):
                actor = next((a for a in snapshot.get('actors', [])
                              if a.get('handle', {}).get('value') in handles), None)
                if actor is not None:
                    snapshot['actors'].remove(actor); self.mutated = True; return changed
        elif self.fault == FAULTS[4]:
            for snapshot in changed.get('samples', []):
                actor = next((a for a in snapshot.get('actors', [])
                              if a.get('handle', {}).get('value') in handles
                              and a.get('motionKind') == 'SKID'), None)
                if actor is not None:
                    snapshot['player']['facing'] = 3
                    actor['engineObject']['facing'] = 3
                    self.mutated = True
                    return changed
        else:
            for event in changed.get('events', []):
                data = event.get('data', {})
                if self.fault == FAULTS[1] and data.get('observation') == 'walk-matrix-tick' and data.get('movingWalk'):
                    data['before']['elapsed'] += 1; self.mutated = True; break
                if self.fault == FAULTS[2] and data.get('observation') == 'stomp-policy' and data.get('effect') == 2:
                    data['feedback']['dust'] = []; self.mutated = True; break
                if self.fault == FAULTS[3] and data.get('event') == 'LOGICAL_COMMIT':
                    data['event'] = 'WORLD_EFFECT'; self.mutated = True; break
        return changed if self.mutated else row

    def result(self, replay):
        require(self.mutated, 'negative control never reached selected live subject')
        rejected = replay.get('passed') is False and bool(replay.get('failures'))
        return dict(fault=self.fault, mutated=True, rejected=rejected, acceptedProof=False)


def validate_negative_result(value, fault=None):
    return isinstance(value, dict) and value.get('fault') in FAULTS \
        and (fault is None or value.get('fault') == fault) and value.get('mutated') is True \
        and value.get('rejected') is True and value.get('acceptedProof') is False
