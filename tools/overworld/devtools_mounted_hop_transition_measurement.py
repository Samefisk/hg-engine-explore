"""Mankey Hop rebind and post-transition input soak from shared memory data."""
from copy import deepcopy

from tools.overworld.devtools_mounted_walk_transition_measurement import (
    MountedWalkTransitionMeasurement, same_lifetime, full_event_handle, LIFECYCLE,
)
from tools.overworld.devtools_mount_control_stress import (
    MountControlStressMeasurement, check_snapshot_pair,
)
from tools.overworld.devtools_records import select_current_actor

KIND = 'mounted-hop-transition-v1'
REQUIREMENT = 'legacy.mounted-transition'


def require(ok, reason):
    if not ok:
        raise ValueError('mounted Hop transition: ' + reason)


def validate_elapsed(start, duration, elapsed):
    require(type(start) is int and type(duration) is int and 0 < start < duration
            and elapsed == list(range(start, duration+1)), 'in-flight elapsed schedule differs')


class MountedHopTransitionMeasurement:
    _current_actor = staticmethod(MountedWalkTransitionMeasurement._current_actor)
    _current_population = staticmethod(MountedWalkTransitionMeasurement._current_population)

    def __init__(self, test, *, max_frames=8000):
        require(type(max_frames) is int and 5001 <= max_frames <= 40000, 'invalid frame bound')
        require(test.get('mode') == 'prepared' and test.get('fixture') == {'rom':'test.nds','save':'test.sav'}
                and test.get('subjects') == [dict(id='mankey',species=56,role='MOUNTED',acquire='existing')],
                'requires prepared current Mankey')
        self.max_frames = max_frames; self.subject_id = 'mankey'
        self.initial = self.last = self.transition = self.transition_terminal = self.terminal = None
        self.subject = self.initial_subject = self.initial_actor = None
        self.frames = self.input_frames = self.pair_count = 0
        self.sequence = 0; self.streams = {}; self.commands = []; self.command_end = None
        self.start_event = None; self.start_actor = None; self.context_events = []; self.lifecycle = []
        self.elapsed = []; self.pair_samples = []; self.stress = None
        self.failures = []; self.closed = False

    def _validate_actor(self, snapshot, actor):
        source, engine = actor['sourceIdentity'], actor['engineIdentity']
        require(actor.get('active') is True and actor.get('role') == 'MOUNTED'
                and actor.get('species') == 56 and actor.get('identityVerified') is True
                and actor.get('presentationAttached') is True and actor.get('inputOwnership') == 1
                and actor.get('subjectIdentity') == self.initial_actor['subjectIdentity']
                and same_lifetime(actor['handle'], self.initial_actor['handle'])
                and actor['behaviorFingerprint'] == self.initial_actor['behaviorFingerprint']
                and source.get('species') == 56 and source.get('personality') == actor['subjectIdentity']
                and source.get('object') == engine.get('pointer') and source.get('map_id') == snapshot['context']['mapId']
                and engine.get('active') is True and engine.get('in_manager') is True
                and engine.get('anchorInCurrentManager') is True
                and engine.get('current_map_id') == engine.get('object_map_id') == snapshot['context']['mapId'],
                'mounted identity/ownership differs')
        self._current_population(snapshot)
        check_snapshot_pair(snapshot, actor)

    def arm(self, subject, snapshot, trace_sequences=None):
        require(self.initial is None, 'already armed')
        self.subject = self.initial_subject = deepcopy(select_current_actor(snapshot, subject))
        actor = self._current_actor(snapshot, self.subject)
        self.initial_actor = deepcopy(actor)
        require(snapshot['context']['mapId'] == 33 and actor['motionKind'] == 'NONE'
                and actor['motionPhase'] == 'IDLE' and actor['reservationId'] == 0, 'arm requires idle map33 mount')
        self._validate_actor(snapshot, actor)
        self.initial = self.last = deepcopy(snapshot)
        self.sequence = snapshot['nativeObservation']['sequence']; self.streams = dict(trace_sequences or {})
        self.command_end = snapshot['frame']
        return self.result()

    def command(self, request, receipt):
        args = request['args']; n = args['frames']; r = receipt.get('receipt',receipt)
        require(not self.closed and request['op'] == 'step' and type(n) is int and 1 <= n <= self.max_frames
                and request['startFrame'] == self.command_end
                and all(r.get(k) == n for k in ('requestedGameFrames','completedGameFrames','observedFieldFrames')),
                'natural command boundary differs')
        keys = args['keys']; require(keys in ([],['RIGHT'],['LEFT'],['UP'],['DOWN']), 'non-cardinal input')
        mask = {'RIGHT':16,'LEFT':32,'UP':64,'DOWN':128}.get(keys[0],0) if keys else 0
        self.commands.append(dict(start=self.command_end,end=self.command_end+n,mask=mask))
        self.command_end += n

    def _input(self, snapshot):
        frame = snapshot['frame']; selector = snapshot['selector']
        rows = [c for c in self.commands if c['start'] < frame <= c['end']]
        require(len(rows) == 1, 'missing normal input command')
        row = rows[0]; mask = selector['heldKeys']
        require(mask == selector['rawHeld'] and selector['simulatedKeys'] == 0, 'simulated or mismatched input')
        prior = next((c for c in self.commands if c['end'] == row['start']), None)
        require(mask == row['mask'] or frame == row['start']+1 and prior and mask == prior['mask'],
                'input does not match requested command')
        return mask

    def _rebind(self, snapshot):
        before, context = self.initial['context'], snapshot['context']
        require(context['mapId'] == 60
                and context['fieldEpoch'] == ((before['fieldEpoch']+1)&0xffff or 1)
                and context['mapGeneration'] == ((before['mapGeneration']+1)&0xffff or 1), 'not exact map33-to60 transition')
        candidates = [a for a in snapshot['actors'] if a.get('active') is True
                      and same_lifetime(a.get('handle',{}), self.initial_subject['handle'])
                      and a.get('subjectIdentity') == self.initial_actor['subjectIdentity']]
        require(len(candidates) == 1, 'missing or duplicate rebound Mankey')
        actor = candidates[0]
        require(actor['motionKind'] == 'HOP' and actor['motionPhase'] == 'MOVING'
                and 0 < actor['motionElapsed'] < actor['motionDuration']
                and actor['engineObject']['face_y'] != 0 and self.start_event is not None
                and actor['origin'] == self.start_actor['origin'] and actor['target'] == self.start_actor['target']
                and actor['motionDuration'] == self.start_actor['motionDuration']
                and actor['commitSequence'] == self.start_actor['commitSequence'], 'rebind did not preserve in-flight Hop')
        require(0 <= snapshot['frame']-self.initial['frame']-1 <= 2499, 'transition input frame exceeds bound')
        self.subject = deepcopy(select_current_actor(snapshot, actor)); self.transition = deepcopy(snapshot)
        self.lifecycle = [deepcopy(self.start_event)]
        return actor

    def _events(self, snapshot, events, actor):
        for event in events:
            require(event.get('frame') == snapshot['frame'], 'event frame differs')
            data = event['data']
            if event['kind'] == 'native-observation':
                require(data['sequence'] == self.sequence+1, 'native sequence gap'); self.sequence += 1
            elif event['kind'] == 'trace-status':
                if data.get('code') == 'ring-overwrite':
                    valid = (set(data) == {'code','traceStream','diagnosticOnly','count','unreadEventsLost'}
                             and type(data.get('count')) is int and data['count'] >= 1
                             and data.get('unreadEventsLost') == 0
                             and data.get('diagnosticOnly') is True)
                elif data.get('code') == 'field-epoch-changed':
                    before, current = self.initial['context'], snapshot['context']
                    valid = (set(data) == {'code','traceStream','diagnosticOnly','previousEpoch',
                                           'fieldEpoch','sequenceReset'}
                             and self.transition is not None
                             and data.get('diagnosticOnly') is True
                             and data.get('sequenceReset') is False
                             and data.get('previousEpoch') == before['fieldEpoch']
                             and data.get('fieldEpoch') == current['fieldEpoch'])
                else:
                    valid = False
                require(valid, 'trace coverage gap')
            elif event['kind'] == 'native':
                stream = data['traceStream']; require(data['sequence'] == self.streams.get(stream,0)+1, 'trace sequence gap')
                self.streams[stream] = data['sequence']
                handle = full_event_handle(data)
                if not same_lifetime(handle,self.initial_subject['handle']): continue
                name = data['event']
                if name == 'CONTEXT_CHANGED':
                    require(self.transition is not None and handle == self.initial_subject['handle']
                            and data['reason'] == 'CONTEXT_LOST'
                            and [data['valueA'],data['valueB']] == [self.initial['context']['fieldEpoch'],snapshot['context']['fieldEpoch']],
                            'context receipt differs')
                    self.context_events.append(deepcopy(event))
                elif name == 'ACTOR_REBOUND':
                    require(self.transition is not None and handle == self.subject['handle']
                            and data['reason'] == 'OK' and [data['valueA'],data['valueB']] == [33,60], 'rebind receipt differs')
                    self.context_events.append(deepcopy(event))
                else:
                    require(handle == self.subject['handle'] and name != 'MOTION_CANCELED', 'stale or canceled Hop')
                    if name == 'MOTION_STARTED':
                        require(self.transition is None and data['reason'] == 'OK' and data['valueA'] == 2
                                and actor['motionKind'] == 'HOP', 'unexpected motion start')
                        self.start_event = deepcopy(event); self.start_actor = deepcopy(actor)
                    elif self.transition is not None and name in LIFECYCLE:
                        self.lifecycle.append(deepcopy(event))
        require(snapshot['nativeObservation']['sequence'] == self.sequence, 'missing native receipt')

    def observe(self, snapshot, events):
        if self.failures or self.closed: return self.result()
        try:
            require(self.initial is not None and snapshot['observationBoundary'] == 'main-task-queue-completion'
                    and snapshot['fieldAvailable'] is True and snapshot['frame'] == self.last['frame']+1
                    and snapshot['nativeCycle'] > self.last['nativeCycle'], 'completed frame gap')
            n = snapshot['nativeObservation']
            require(n.get('installedBeforeBoot') is True and n.get('coverageComplete') is True
                    and n.get('error') is None and n.get('eventsDropped') == n.get('profilesEvicted') == 0, 'native coverage gap')
            mask = self._input(snapshot)
            if self.transition is None and snapshot['context'] != self.initial['context']:
                actor = self._rebind(snapshot)
            else:
                require(snapshot['context'] == (self.transition or self.initial)['context'], 'extra field transition')
                actor = self._current_actor(snapshot,self.subject)
            self._validate_actor(snapshot,actor)
            self.frames += 1; require(self.frames <= self.max_frames, 'frame bound exceeded')
            if self.transition is not None and snapshot['frame'] > self.transition['frame'] and mask:
                self.input_frames += 1
            if self.stress is not None:
                self.stress.observe(snapshot,events)
                require(not self.stress.failures, 'post-transition Hop: '+str(self.stress.failures))
            else:
                self._events(snapshot,events,actor)
                if self.transition is not None:
                    self.pair_count += 1
                    self.pair_samples.append(dict(frame=snapshot['frame'],player=[snapshot['player'][k] for k in ('pos_x','pos_y','pos_z')],
                                                  mount=[actor['engineObject'][k] for k in ('pos_x','pos_y','pos_z')]))
                    if actor['motionKind'] == 'HOP':
                        elapsed = actor['motionElapsed']
                        if not self.elapsed or self.elapsed[-1] != elapsed:self.elapsed.append(elapsed)
                    if actor['motionPhase'] == 'IDLE' and actor['reservationId'] == 0:
                        self._finish_transition(snapshot,actor)
            self.last = deepcopy(snapshot)
            if self.ready:self.terminal = deepcopy(snapshot)
        except (ValueError,KeyError,TypeError,StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def _finish_transition(self,snapshot,actor):
        start = self._current_actor(self.transition,self.subject)
        validate_elapsed(start['motionElapsed'],start['motionDuration'],self.elapsed)
        require(actor['logical'] == start['target'] and actor['commitSequence'] == start['commitSequence']+1,
                'transition terminal commit/target differs')
        require([e['data']['event'] for e in self.context_events] == ['CONTEXT_CHANGED','ACTOR_REBOUND'], 'missing transition lifecycle')
        require([e['data']['event'] for e in self.lifecycle] == list(LIFECYCLE), 'missing Hop lifecycle')
        started,commit,finished,control = [e['data'] for e in self.lifecycle]
        require(started['valueA'] == 2 and started['valueB'] == start['motionDuration']
                and commit['reason'] == finished['reason'] == control['reason'] == 'OK'
                and commit['valueA'] == finished['valueA'] == actor['commitSequence']
                and commit['valueB'] == finished['valueB'] == 2
                and [control['valueA'],control['valueB']] == [1,actor['commitSequence']], 'Hop lifecycle values differ')
        require([e['data']['sequence'] for e in self.lifecycle] == sorted(set(e['data']['sequence'] for e in self.lifecycle)),
                'Hop lifecycle order differs')
        self.transition_terminal = deepcopy(snapshot)
        self.stress = MountControlStressMeasurement('hop',self.max_frames)
        self.stress.arm(self.subject,snapshot,self.streams)

    @property
    def ready(self):
        if self.failures or self.stress is None or self.last is None:return False
        actor = self._current_actor(self.last,self.subject)
        return (self.input_frames >= 5000 and self.stress.motions >= 1 and self.stress.recorder.current is None
                and actor['motionKind'] == 'NONE' and actor['motionPhase'] == 'IDLE'
                and actor['reservationId'] == 0 and actor['inputOwnership'] == 1 and not self.stress.traces)

    def stage(self,name):
        if name == 'context-changed':return self.transition is not None and not self.failures
        if name == 'transition-motion-complete':return self.stress is not None and not self.failures
        if name == 'soak-complete':return self.input_frames >= 5000 and not self.failures
        if name == 'recovered':return self.ready
        raise ValueError('unknown mounted Hop transition stage')

    def finish(self):
        if not self.ready and not self.failures:self.failures.append('mounted Hop transition: transition/recovery/input soak incomplete')
        self.closed = True
        return self.result()

    def result(self):
        return deepcopy(dict(kind=KIND,requirements=[REQUIREMENT],passed=self.closed and self.ready,
            ready=self.ready,closed=self.closed,acceptedProof=False,failures=self.failures,frames=self.frames,
            subject=self.subject,initialSubject=self.initial_subject,initial=self.initial,transition=self.transition,
            transitionTerminal=self.transition_terminal,terminal=self.terminal,postTransitionInputFrames=self.input_frames,
            elapsed=self.elapsed,pairSamples=self.pair_samples,lifecycle=self.lifecycle,contextEvents=self.context_events,
            recoveryMotions=self.stress.motion_summaries if self.stress else []))
