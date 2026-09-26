"""Pure bounded turn-skid replay using existing native Tick and dust receipts."""
from copy import deepcopy
import struct

from tools.overworld.devtools_walk_matrix_measurement import WalkMatrixMeasurement
from tools.overworld.devtools_walk_matrix_observer import decode_motion, decode_sample
from tools.overworld.devtools_mount_control_stress import check_snapshot_pair
from tools.overworld.devtools_wild_walk_measurement import IDENTITY, LIFECYCLE

KIND = 'turn-skid-v1'
REQUIREMENT = 'current.turn-deceleration'
ACCELERATION_MOTION_COUNT = 13
MOTION_COUNT = 16
DURATIONS = [8, 8, 8, 7, 7, 7, 6, 6, 6, 5, 5, 5, 4, 8, 8, 5]
KINDS = [1] * ACCELERATION_MOTION_COUNT + [4, 4, 1]


def require(ok, reason):
    if not ok:
        raise ValueError('turn skid: ' + reason)


def validate_motion(motion, index):
    ticks, events = motion['ticks'], motion['events']
    require(0 <= index < MOTION_COUNT and len(ticks) == DURATIONS[index], 'native duration differs')
    plan = ticks[0]['before']['plan']
    require(plan['kind'] == KINDS[index] and plan['duration'] == DURATIONS[index], 'motion kind/time differs')
    require(plan['direction'] == (3 if index < MOTION_COUNT - 1 else 2), 'travel direction differs')
    facing = 3 if index < ACCELERATION_MOTION_COUNT else 2
    require(plan['facing'] == facing, 'turn-skid facing differs from requested turn')
    delta = 1 if index < MOTION_COUNT - 1 else -1
    require(plan['target'] == [plan['origin'][0] + delta, plan['origin'][1]], 'motion target differs')
    require(plan['reservationId'] > 0, 'missing reservation')
    for elapsed, tick in enumerate(ticks):
        before, after = tick['before'], tick['after']
        require(before == decode_motion(bytes.fromhex(before['rawHex']))
                and after == decode_motion(bytes.fromhex(after['rawHex']))
                and tick['sample'] == decode_sample(bytes.fromhex(tick['sample']['rawHex'])), 'raw Tick differs')
        require(before['plan'] == after['plan'] == plan and before['phase'] == 'MOVING'
                and before['elapsed'] == elapsed and after['elapsed'] == elapsed + 1
                and tick['sample']['elapsed'] == elapsed + 1
                and tick['sample']['duration'] == plan['duration'], 'native elapsed sequence differs')
        require(tick['sample']['facing'] == facing, 'turn-skid sample facing differs')
    require([e['event'] for e in events] == list(LIFECYCLE), 'exact lifecycle missing')
    require(all(e['reason'] == 'OK' for e in events), 'non-OK lifecycle')
    start, commit, finish, control = events
    require((start['valueA'], start['valueB']) == (plan['kind'], plan['duration'])
            and commit['valueA'] == finish['valueA'] == motion['commitBefore'] + 1
            and commit['valueB'] == finish['valueB'] == plan['kind']
            and (control['valueA'], control['valueB']) == (1, commit['valueA']), 'lifecycle values differ')
    require([e['sequence'] for e in events] == sorted(set(e['sequence'] for e in events)), 'lifecycle order differs')
    return plan


def validate_skid_presentation(snapshot, actor):
    if actor['motionKind'] != 'SKID':
        return False
    require(actor['motionPhase'] in ('MOVING', 'COMMIT_PENDING')
            and snapshot['player']['facing'] == actor['engineObject']['facing'] == 2,
            'mounted skid keeps old facing until recovery')
    return True


def validate_dust(call, subject, actor, context):
    require(call.get('kind') == 'policy' and call.get('effect') == 2, 'missing skid dust policy')
    raw = bytes.fromhex(call['policyHex'])
    require(len(raw) == 28 and struct.unpack_from('<HH', raw) == (1, 28)
            and raw[8] == subject['handle']['slot'] and raw[9] == 3 and raw[21] == 2,
            'skid dust policy bytes differ')
    feedback = call['feedback']
    require(set(feedback) == {'dust', 'allocate', 'init', 'sound', 'soundStart'}
            and [len(feedback[k]) for k in ('dust', 'allocate', 'init', 'sound', 'soundStart')]
                == [1, 1, 1, 0, 0], 'skid dust sink coverage differs')
    dust, alloc, init = (feedback[k][0] for k in ('dust', 'allocate', 'init'))
    for value in (call, dust, alloc, init):
        owner = value['before']
        require(value.get('normalReturn') is True and owner['subject'] == subject
                and owner['sourceIdentity'] == actor['sourceIdentity']
                and all(owner['publicSubject'].get(k) == actor.get(k) for k in IDENTITY)
                and owner['mountPointer'] == actor['engineIdentity']['pointer']
                and owner['playerPointer'] == actor['engineIdentity']['anchorPointer']
                and all(owner['worldContext'].get(k) == v for k, v in context.items()), 'dust owner differs')
        require(call['entryClock']['nativeCycle'] <= value['entryClock']['nativeCycle']
                <= value['returnClock']['nativeCycle'] <= call['returnClock']['nativeCycle'], 'dust clock nesting differs')
    for parent, child in ((call, dust), (dust, alloc), (alloc, init)):
        require(parent['entryClock']['nativeCycle'] <= child['entryClock']['nativeCycle']
                <= child['returnClock']['nativeCycle'] <= parent['returnClock']['nativeCycle'], 'dust parent differs')
    pointer = actor['engineIdentity']['pointer']
    require(dust['args'][0] == pointer and alloc['returnValue'] == init['args'][0]
            and type(alloc['returnValue']) is int and alloc['returnValue'] % 4 == 0
            and 0x02000000 <= alloc['returnValue'] < 0x02400000, 'dust allocation failed')
    context_raw, data = bytes.fromhex(alloc['contextHex']), bytes.fromhex(init['effectDataHex'])
    require(len(context_raw) == 16 and len(data) == 36
            and struct.unpack_from('<I', context_raw, 12)[0] == pointer
            and struct.unpack_from('<I', data, 28)[0] == pointer
            and struct.unpack_from('<I', data, 32)[0] == init['renderPointer']
            and 0x02000000 <= init['renderPointer'] < 0x02400000 and init['returnValue'] == 1,
            'dust render initialization failed')


class TurnSkidMeasurement:
    _actor = WalkMatrixMeasurement._actor
    _reader = WalkMatrixMeasurement._reader

    def __init__(self, max_frames=600):
        require(type(max_frames) is int and 1 <= max_frames <= 1200, 'invalid frame bound')
        self.max_frames = max_frames
        self.initial = self.last = self.actor = self.subject = self.current = None
        self.reader_layout = self.tick_owner = self.last_tick = None
        self.ticks = self.moving = self.frames = self.sequence = 0
        self.streams = {}; self.motions = []; self.commands = []; self.dust = []
        self.skid_facing_frames = []
        self.tick_groups = {}; self.pending_events = []
        self.failures = []; self.closed = False; self.command_end = None

    def arm(self, subject, snapshot, receipt, trace_sequences=None):
        require(self.initial is None, 'already armed')
        self.subject = deepcopy(subject); self.actor = deepcopy(self._actor(snapshot))
        require(WalkMatrixMeasurement._idle(self.actor), 'arm requires idle mounted Cyndaquil')
        self.initial = self.last = deepcopy(snapshot)
        self.command_end = snapshot['frame']; self.sequence = snapshot['nativeObservation']['sequence']
        self.streams = dict(trace_sequences or {})
        self._reader(receipt, False)
        return self.result()

    def command(self, request, receipt):
        r = receipt.get('receipt', receipt); args = request['args']; n = args['frames']
        require(not self.closed and request['op'] == 'step' and type(n) is int and 1 <= n <= self.max_frames
                and request['startFrame'] == self.command_end
                and all(r.get(k) == n for k in ('requestedGameFrames', 'completedGameFrames', 'observedFieldFrames')),
                'normal input boundary differs')
        require(args['keys'] in ([], ['RIGHT'], ['LEFT']), 'unexpected input')
        self.commands.append(dict(start=self.command_end, end=self.command_end+n,
                                  mask=16 if args['keys'] == ['RIGHT'] else 32 if args['keys'] else 0))
        self.command_end += n

    def _tick(self, data):
        require(data.get('normalReturn') is True and data['motionPointer'] == self.motion_pointer
                and data['completedFrame'] == self.last['frame'], 'native Tick boundary differs')
        for key in ('beforeCurrent', 'afterCurrent'):
            owner = data[key]
            require(owner['subject'] == self.subject
                    and all(owner['publicSubject'].get(k) == self.actor.get(k) for k in IDENTITY)
                    and owner['sourceIdentity'] == self.actor['sourceIdentity']
                    and owner['playerPointer'] == self.actor['engineIdentity']['anchorPointer']
                    and owner['mountPointer'] == self.actor['engineIdentity']['pointer']
                    and all(owner['worldContext'].get(k) == v for k,v in self.initial['context'].items()), 'Tick owner differs')
        before, after = data['before'], data['after']
        require(data['entryClock'] == dict(actorFrame=data['entryActorFrame'], nativeCycle=data['entryNativeCycle'])
                and data['returnClock'] == dict(actorFrame=data['returnActorFrame'], nativeCycle=data['returnNativeCycle'])
                and data['returnFlags'] == data['returnValue'] == data['sample']['flags'], 'Tick return/clock differs')
        self.ticks += 1; self.moving += int(data['movingWalk'])
        self.last_tick = dict(completedFrame=data['completedFrame'], entryElapsed=before['elapsed'],
            returnElapsed=after['elapsed'], reservationId=after['plan']['reservationId'], qualification=data['qualification'])
        if before['phase'] != 'MOVING': return
        require(len(self.motions) < MOTION_COUNT, 'unrequested moving Tick')
        reservation = before['plan']['reservationId']
        group = self.tick_groups.setdefault(reservation, [])
        require(len(self.tick_groups) <= MOTION_COUNT, 'extra motion group')
        require(data['movingWalk'] == (before['plan']['kind'] == 1)
                and before['plan']['fieldEpoch'] == self.initial['context']['fieldEpoch']
                and all(data[k]['publicSubject']['reservationId'] == reservation for k in ('beforeCurrent','afterCurrent')), 'Tick kind/identity differs')
        group.append(deepcopy(data))
        require(len(group) <= before['plan']['duration'], 'extra Tick')

    def observe(self, snapshot, events):
        if self.failures: return self.result()
        try:
            require(self.initial is not None and not self.closed, 'observation outside window')
            actor = self._actor(snapshot)
            require(snapshot['fieldAvailable'] is True and snapshot['observationBoundary'] == 'main-task-queue-completion'
                    and snapshot['frame'] == self.last['frame'] + 1
                    and snapshot['nativeCycle'] > self.last['nativeCycle'], 'completed frame gap')
            self.frames += 1; require(self.frames <= self.max_frames, 'frame bound exceeded')
            n = snapshot['nativeObservation']
            require(n.get('installedBeforeBoot') is True and n.get('coverageComplete') is True
                    and n.get('error') is None and n.get('eventsDropped') == n.get('profilesEvicted') == 0, 'native coverage gap')
            command = [c for c in self.commands if c['start'] < snapshot['frame'] <= c['end']]
            require(len(command) == 1, 'missing input command')
            mask = snapshot['selector']['heldKeys']
            require(mask == snapshot['selector']['rawHeld'] and snapshot['selector']['simulatedKeys'] == 0,
                    'input is not natural')
            previous = next((c for c in self.commands if c['end'] == command[0]['start']), None)
            require(mask == command[0]['mask'] or snapshot['frame'] == command[0]['start'] + 1
                    and previous is not None and mask == previous['mask'], 'input differs from command')
            check_snapshot_pair(snapshot, actor)
            if validate_skid_presentation(snapshot, actor):
                self.skid_facing_frames.append(snapshot['frame'])
            for event in events:
                d = event['data']; require(event['frame'] == snapshot['frame'], 'event frame differs')
                if event['kind'] == 'native-observation':
                    require(d['sequence'] == self.sequence+1, 'native sequence gap'); self.sequence += 1
                    require(self.last['nativeCycle'] <= d['entryNativeCycle'] <= d['returnNativeCycle'] <= snapshot['nativeCycle'], 'native clock gap')
                    if d.get('observation') == 'walk-matrix-tick': self._tick(d)
                    elif d.get('observation') == 'stomp-policy' and d.get('effect') == 2:
                        validate_dust(d, self.subject, self.actor, self.initial['context'])
                        require(len(self.motions) in (ACCELERATION_MOTION_COUNT + 1,
                                ACCELERATION_MOTION_COUNT + 2), 'dust outside final skid')
                        self.dust.append(deepcopy(d)); require(len(self.dust) == 1, 'duplicate skid dust')
                elif event['kind'] == 'native':
                    stream = d['traceStream']; require(d['sequence'] == self.streams.get(stream, 0)+1, 'trace sequence gap')
                    self.streams[stream] = d['sequence']
                    if d['actorHandle'] != self.subject['handle']['value']: continue
                    require(d['actor'] == {k:v for k,v in self.subject['handle'].items() if k != 'value'}, 'trace identity differs')
                    require(d['event'] not in ('MOTION_CANCELED','ACTOR_REBOUND','CONTEXT_CHANGED'), 'motion canceled or rebound')
                    if d['event'] == 'MOTION_STARTED':
                        started = len(self.motions) + sum(e['event']=='MOTION_STARTED' for e in self.pending_events)
                        require(started < MOTION_COUNT and mask == (
                            16 if started < ACCELERATION_MOTION_COUNT else 32),
                            'motion lacks directional input')
                    if d['event'] in LIFECYCLE:
                        self.pending_events.append(deepcopy(d))
                        require(len(self.pending_events) <= 16, 'unjoined lifecycle bound')
                elif event['kind'] == 'trace-status':
                    require(d.get('code') == 'ring-overwrite' and d.get('unreadEventsLost') == 0
                            and d.get('diagnosticOnly') is True, 'trace loss')
            require(n['sequence'] == self.sequence, 'missing receipt')
            self._reader(snapshot['walkMatrix'], False)
            while len(self.pending_events) >= 4 and self.tick_groups:
                reservation = next(iter(self.tick_groups))
                ticks = self.tick_groups[reservation]
                if len(ticks) < ticks[0]['before']['plan']['duration']: break
                current = dict(ticks=ticks, events=self.pending_events[:4],
                               commitBefore=self.initial['actors'][next(i for i,a in enumerate(self.initial['actors'])
                                   if a['handle']==self.subject['handle'])]['commitSequence']+len(self.motions))
                plan = validate_motion(current, len(self.motions))
                if self.motions:
                    require(plan['origin'] == self.motions[-1]['plan']['target'], 'motion chain target differs')
                current['plan'] = deepcopy(plan); self.motions.append(current)
                del self.pending_events[:4]; del self.tick_groups[reservation]
            expected_commit = next(a for a in self.initial['actors'] if a['handle']==self.subject['handle'])['commitSequence']+len(self.motions)
            require(expected_commit <= actor['commitSequence'] <= expected_commit+2, 'public commit differs')
            self.actor = deepcopy(actor); self.last = deepcopy(snapshot)
            return self.result()
        except (ValueError, KeyError, TypeError, IndexError) as error:
            self.failures.append(str(error)); return self.result()

    @property
    def ready(self):
        return not self.failures and len(self.motions) == MOTION_COUNT and not self.tick_groups and not self.pending_events and len(self.dust) == 1 \
            and len(self.skid_facing_frames) == sum(DURATIONS[ACCELERATION_MOTION_COUNT:-1]) \
            and WalkMatrixMeasurement._idle(self.actor) and self.actor['movementPolicy']['pending'] == 0 \
            and self.actor['movementPolicy']['skid'] == 0 and self.actor['engineObject']['facing'] == 2 \
            and self.actor['logical'] == dict(zip(('x','y'), self.motions[-1]['plan']['target'])) \
            and self.actor['commitSequence'] == self.motions[-1]['commitBefore']+1

    def stage(self, name):
        started = len(self.motions) + sum(event['event'] == 'MOTION_STARTED'
                                         for event in self.pending_events)
        return {'acceleration-complete': started >= ACCELERATION_MOTION_COUNT and not self.failures,
                'recovery-started': started >= MOTION_COUNT and not self.failures,
                'complete': self.ready}.get(name, False)

    def close(self, receipt, snapshot):
        closed_snapshot = receipt.get('snapshot', {})
        native = lambda value: {key: item for key, item in
                                value.get('nativeObservation', {}).items()
                                if key != 'resolvedProfiles'}
        require(snapshot == self.last and self.ready
                and all(closed_snapshot.get(key) == snapshot.get(key) for key in
                    ('frame', 'nativeCycle', 'actorFrame', 'context', 'player',
                     'actors')) and native(closed_snapshot) == native(snapshot),
                'close before exact recovery')
        self._reader(receipt, True); self.closed = True
        return self.result()

    def finish(self):
        if not self.ready and not self.failures: self.failures.append('turn skid: exact sequence incomplete')
        return self.result()

    def result(self):
        return deepcopy(dict(kind=KIND, requirements=[REQUIREMENT], ready=self.ready, closed=self.closed,
            passed=self.ready and self.closed, acceptedProof=False, failures=self.failures,
            frames=self.frames, motions=self.motions, dust=self.dust,
            skidFacingFrames=self.skid_facing_frames, initial=self.initial, terminal=self.last,
            subject=self.subject))
