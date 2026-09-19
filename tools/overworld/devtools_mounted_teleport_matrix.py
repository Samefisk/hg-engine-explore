"""Ten mounted Teleports measured from existing completed frames only."""
from copy import deepcopy

from .devtools_mount_control_stress import MountControlStressMeasurement, GENERATIONS, check_snapshot_pair, require
from .normal_play_observer import complete_travel

KIND = 'mounted-teleport-matrix-v1'
REQUIREMENT = 'legacy.teleport-timing'
CASES = ('fixed_visible_right','fixed_visible_left','fixed_visible_up','fixed_visible_down','fixed_flicker',
         'per_tile_visible_left','per_tile_visible_right','per_tile_visible_up','per_tile_visible_down','per_tile_flicker')
DIRECTIONS = ((16,(1,0)),(32,(-1,0)),(64,(0,-1)),(128,(0,1)),(16,(1,0)),
              (32,(-1,0)),(16,(1,0)),(64,(0,-1)),(128,(0,1)),(32,(-1,0)))


def configuration(index):
    per_tile = index >= 5
    return dict(locomotion=(10 if per_tile else 6) if index % 5 == 4 else (11 if per_tile else 9),
                teleportTime=3 if per_tile else 7, teleportPause=0)


def expected_visibility(index,duration):
    if configuration(index)['locomotion'] in (9,11):
        return [False]*duration
    return [((elapsed//2)&1)==0 for elapsed in range(1,duration+1)]


class MountedTeleportMatrixMeasurement(MountControlStressMeasurement):
    def __init__(self, max_frames=2400):
        require(type(max_frames) is int and 1 <= max_frames <= 2400, 'invalid Teleport matrix frame bound')
        super().__init__('walk',40000)
        self.max_frames = max_frames
        self.rules.update(motion='TELEPORT',kind=3,motions=10,frames=0)
        self.allowed_motion_kinds = ('TELEPORT',)
        self.cases=[]; self.config=None; self.samples=[]; self.case_started=False
        self.last_profile=None
        self.presentation_generation=None;self.presentation_attached=None
        self.awaiting_attachment=False

    def _terminal_snapshot_lag(self,snapshot,actor):
        target=actor.get('target',{})
        engine=actor.get('engineObject',{});player=snapshot.get('player',{})
        return (self.recorder.current is not None and actor.get('motionKind')=='TELEPORT'
                and actor.get('motionPhase')=='COMMIT_PENDING'
                and actor.get('motionElapsed')==actor.get('motionDuration')
                and actor.get('logical')==target
                and engine.get('x')==target.get('x') and engine.get('y')==target.get('y')
                and player.get('x')==target.get('x') and player.get('y')==target.get('y')
                and not (engine.get('flags',512)&512) and not (player.get('flags',512)&512))

    def _actor(self,snapshot):
        matches=[actor for actor in snapshot.get('actors',[])
                 if self.subject is not None and actor.get('handle')==self.subject.get('handle')]
        if len(matches)==1:
            actor=matches[0];checks=actor.get('identityChecks',{})
            active=(actor.get('motionKind')=='TELEPORT'
                    and actor.get('motionPhase') in ('PLANNED','MOVING','COMMIT_PENDING','SETTLING'))
            target=actor.get('target',{})
            engine=actor.get('engineObject',{})
            terminal=(actor.get('motionKind')=='NONE' and actor.get('motionPhase')=='IDLE'
                    and actor.get('reservationId')==0
                    and actor.get('motionElapsed')==actor.get('motionDuration')
                    and actor.get('logical')==target
                    and engine.get('x')==target.get('x') and engine.get('y')==target.get('y')
                    and not (engine.get('flags',512)&512)
                    and not (snapshot.get('player',{}).get('flags',512)&512))
            transient=((active or terminal)
                    and actor.get('presentationAttached') is False
                    and actor.get('identityVerified') is False
                    and actor.get('identityFailures')==['presentationAttached']
                    and checks.get('presentationAttached') is False
                    and all(value is True for key,value in checks.items()
                            if key!='presentationAttached'))
            if transient:
                checked=deepcopy(snapshot)
                selected=next(item for item in checked['actors']
                              if item.get('handle')==self.subject['handle'])
                selected['presentationAttached']=selected['identityVerified']=True
                super()._actor(checked)
                return actor
        return super()._actor(snapshot)

    def configure(self, receipt, snapshot):
        require(self.phase!='unarmed' and not self.closed and not self.failures,
                'Teleport configure outside open matrix')
        require(self.recorder.current is None and not self.traces and self.config is None
                and not self.awaiting_attachment and len(self.cases)<10,
                'Teleport configure before prior case completes')
        actor=self._actor(snapshot)
        require(actor['motionKind']=='NONE' and actor['motionPhase']=='IDLE' and actor['reservationId']==0,
                'Teleport configure requires idle actor')
        value=receipt.get('value',receipt); expected=configuration(len(self.cases))
        require(value.get('completed') is True and value.get('guestAdvanced') is False
                and value.get('subject')==self.subject and value.get('changedOffsets')==[12,23,24]
                and all(value.get(k)==v for k,v in expected.items()), 'Teleport configuration receipt differs')
        before,after=value['before'],value['after']
        old,new=bytes.fromhex(before['profileHex']),bytes.fromhex(after['profileHex'])
        a,b=bytes.fromhex(before['mountStateHex']),bytes.fromhex(after['mountStateHex'])
        require(len(old)==len(new)==72 and len(a)==len(b)==184 and a[8:80]==old and b[8:80]==new,
                'Teleport configuration raw state differs')
        observed=before['readiness'].get('actor', {})
        require(all(observed.get(k)==actor.get(k) for k in ('handle','subjectIdentity','species','role',*GENERATIONS))
                and before['readiness'].get('subject')==self.subject,
                'Teleport configuration actor receipt differs')
        if self.last_profile is not None:
            require(old==self.last_profile,'Teleport profile changed between cases')
        changed=bytearray(a)
        for offset,key in ((12,'locomotion'),(23,'teleportTime'),(24,'teleportPause')):changed[8+offset]=expected[key]
        require(bytes(changed)==b and before['bindingHex']==after['bindingHex']==a[80:96].hex()
                and before['sessionGeneration']==after['sessionGeneration']>0
                and before['clock']==after['clock']
                and before['readiness']==after['readiness'], 'Teleport configure changed unrelated state')
        require(snapshot['frame']==self.last['frame'] and snapshot['nativeCycle']==self.last['nativeCycle'],
                'Teleport configure advanced observation boundary')
        self.last_profile=new
        self.config=deepcopy(value); self.samples=[]; self.case_started=False
        return self.result()

    def observe(self,snapshot,events):
        if self.phase=='unarmed' or self.failures:return self.result()
        try:
            require(not self.closed and snapshot.get('fieldAvailable') is True
                    and snapshot.get('observationBoundary')=='main-task-queue-completion'
                    and snapshot['context']==self.initial['context'], 'Teleport matrix context differs')
            require(snapshot['frame']==self.last['frame']+1 and snapshot['nativeCycle']>self.last['nativeCycle'],
                    'Teleport completed clock gap')
            self.frames+=1;require(self.frames<=self.max_frames,'Teleport matrix frame bound exceeded')
            native=snapshot['nativeObservation']
            require(native.get('installedBeforeBoot') is True and native.get('coverageComplete') is True
                    and native.get('error') is None and all(native.get(k)==0 for k in ('eventsDropped','profilesEvicted')),
                    'Teleport native coverage incomplete')
            actor=self._actor(snapshot)
            require(actor['role']=='MOUNTED' and actor['inputOwnership']==1
                    and all(actor[k]==self.actor[k] for k in GENERATIONS[:2]),
                    'Teleport ownership changed')
            prior_generation=(self.actor['presentationGeneration'] if self.presentation_generation is None
                              else self.presentation_generation)
            prior_attached=(self.actor['presentationAttached'] if self.presentation_attached is None
                            else self.presentation_attached)
            current_generation=actor['presentationGeneration']
            current_attached=actor['presentationAttached']
            require((current_generation==prior_generation and current_attached==prior_attached)
                    or (current_generation==prior_generation+1 and current_attached is not prior_attached),
                    'Teleport presentation generation changed outside visibility transition')
            self.presentation_generation=current_generation
            self.presentation_attached=current_attached
            self.subject['presentationGeneration']=current_generation
            if actor['identityVerified'] is True:
                for key,value in (('observedFrame',snapshot['frame']),
                                  ('identityVerified',True),
                                  ('engineIdentity',actor['engineIdentity'])):
                    if key in self.subject:
                        self.subject[key]=deepcopy(value)
            check_snapshot_pair(snapshot,actor)
            self._events(snapshot,events,actor)
            if self.awaiting_attachment:
                require(self.config is None and not self.case_started
                        and actor['motionKind']=='NONE' and actor['motionPhase']=='IDLE'
                        and actor['reservationId']==0,
                        'Teleport attachment settle left idle')
                if actor['presentationAttached'] is True and actor['identityVerified'] is True:
                    self.awaiting_attachment=False
            allowed_mask=DIRECTIONS[len(self.cases)][0] if self.config is not None else 0
            held=snapshot['selector'].get('rawHeld',0)
            require(held in (0,allowed_mask) and snapshot['selector'].get('heldKeys',held)==held
                    and all(snapshot['selector'].get(k,0)&~allowed_mask==0 for k in ('newKeys','rawNew')),
                    'Teleport unexpected input')
            terminal_snapshot_lag=self._terminal_snapshot_lag(snapshot,actor)
            active=(actor['motionPhase'] in ('PLANNED','MOVING','COMMIT_PENDING','SETTLING')
                    and not terminal_snapshot_lag)
            if active:
                require(self.config is not None and actor['motionKind']=='TELEPORT' and actor['motionKindId']==3,
                        'wrong or unconfigured Teleport motion')
                mask,axis=DIRECTIONS[len(self.cases)]
                held=snapshot['selector'].get('rawHeld',0)
                require(held in (0,mask) and snapshot['selector'].get('heldKeys',held)==held
                        and snapshot['selector'].get('newKeys',0)&~mask==0, 'Teleport unexpected input')
                if not self.case_started:
                    require(held==mask,'Teleport lacks natural start input')
                    require(actor['motionElapsed']==1,
                            'Teleport missing first completed-frame sample')
                    delta=tuple(actor['target'][k]-actor['origin'][k] for k in ('x','y'))
                    distance=sum(abs(n) for n in delta)
                    require(tuple((n>0)-(n<0) for n in delta)==axis and distance>0,'Teleport requested axis differs')
                    duration=self.config['teleportTime']*(distance if len(self.cases)>=5 else 1)
                    require(actor['motionDuration']==duration,'Teleport duration differs')
                    self.case_started=True
                if len(self.samples)<=actor['motionDuration']:
                    require(actor['motionElapsed']==len(self.samples)+1,
                            'Teleport elapsed sample gap')
                    require(type(actor['engineObject'].get('flags')) is int
                            and type(snapshot['player'].get('flags')) is int,
                            'Teleport visibility missing')
                    require(bool(actor['engineObject']['flags']&512)
                            == bool(snapshot['player']['flags']&512),
                            'Teleport player/presentation visibility differs')
                    self.samples.append(dict(elapsed=actor['motionElapsed'],frame=snapshot['frame'],
                        visible=not bool(actor['engineObject']['flags']&512)))
            elif self.config is None:
                require(held==0,'Teleport idle input is not neutral')
            travel_actor=actor
            if terminal_snapshot_lag:
                # Raw objects have reached the target, but the public actor can
                # still expose the prior endpoint. Retain the endpoint without
                # inventing another elapsed sample; the next frame must expose
                # the real commit and idle state.
                pass
            elif (actor['motionKind']=='TELEPORT' and actor['motionPhase']=='COMMIT_PENDING'
                    and actor['motionElapsed']==actor['motionDuration']):
                # The duration endpoint is an observed Teleport frame. The
                # shared lifecycle commits its opaque rendered move next frame.
                travel_actor=deepcopy(actor);travel_actor['motionPhase']='MOVING'
            self.recorder.observe(snapshot['frame'],travel_actor,snapshot['player'])
            require(not self.recorder.failures,'Teleport travel differs: '+str(self.recorder.failures))
            while self.recorder.completed:
                motion=self.recorder.completed.pop(0)
                require(self.case_started and complete_travel(motion),'Teleport missing complete travel')
                require([v['elapsed'] for v in self.samples]==list(range(1,motion['duration']+1)),
                        'Teleport missing elapsed/visibility endpoint')
                require([v['visible'] for v in self.samples]
                        == expected_visibility(len(self.cases),motion['duration']),
                        'Teleport visibility policy differs')
                super()._join(motion)
                require(travel_actor['motionKind']=='NONE' and travel_actor['motionPhase']=='IDLE'
                        and travel_actor['reservationId']==0
                        and held==0, 'Teleport control not restored')
                self.cases.append(dict(name=CASES[len(self.cases)],configuration=configuration(len(self.cases)),
                    samples=deepcopy(self.samples),summary=deepcopy(self.motion_summaries[-1])))
                self.config=None;self.case_started=False
                self.awaiting_attachment=actor['presentationAttached'] is not True
            self.last=deepcopy(snapshot)
        except (ValueError,KeyError,TypeError,IndexError) as error:self.failures.append(str(error))
        return self.result()

    def stage(self,name):
        require(name in ('case-started','case-complete'),'unknown Teleport matrix stage')
        return not self.failures and (self.case_started if name=='case-started'
            else bool(self.cases) and self.config is None and not self.awaiting_attachment)

    @property
    def ready(self):
        return (len(self.cases)==10 and self.config is None and not self.awaiting_attachment
                and not self.traces and not self.failures)

    def finish(self):
        if not self.ready and not self.failures:self.failures.append('ten complete Teleport cases required')
        if len(self.cases)==10 and not self.failures:
            fixed_distances={sum(abs(a-b) for a,b in zip(c['summary']['origin'],c['summary']['target']))
                             for c in self.cases[:4]}
            per_tile_distances=[sum(abs(a-b) for a,b in zip(c['summary']['origin'],c['summary']['target']))
                                for c in self.cases[5:9]]
            if len(fixed_distances)<2:self.failures.append('fixed Teleport cases need two distances')
            if not any(distance>1 for distance in per_tile_distances):
                self.failures.append('per-tile Teleport needs one non-unit distance')
        self.closed=True
        return self.result()

    def result(self,*_args):
        return dict(kind=KIND,contract=REQUIREMENT,passed=self.closed and self.ready,ready=self.ready,closed=self.closed,
            acceptedProof=False,failures=list(self.failures),frames=self.frames,subject=deepcopy(self.subject),
            cases=deepcopy(self.cases),maxFrames=self.max_frames)
