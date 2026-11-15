"""T83: normal Select is ignored in flight; a confirmed Y choice waits.

Uses the current Actor, shared Motion bytes, native input/selector queue and
ordered semantic receipts already recorded by the shared worker. No reader,
engine, guest write or game acceptance is owned here.
"""
from copy import deepcopy
from fractions import Fraction
from tools.overworld.devtools_mounted_canopy_hop_measurement import MountedCanopyHopMeasurement
from tools.overworld.devtools_records import select_current_actor, engine_binding_identity
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.normal_play_observer import arc_height

KIND='mount-airborne-input-v1'
TEST='mount.airborne-input'
REQUIREMENT='current.mount-airborne-input'
ORIGIN=(564,375)
FIRST_TARGET=(563,375)
SETUP=(('route30-canopy','teleport',dict(map=34,x=564,z=375,facing=2)),
       ('settle-field','step',dict(frames=24,keys=[])),
       ('mount-saved-mankey','spawn',dict(species=56,form=0,role='mounted',slot=2,level=3)),
       ('bind-mankey','bind',dict(subject='mankey')))
# Bounds are finite; the three typed stage waits stop at their real boundary.
ACTION_SPEC=(('left-to-tree',8,['LEFT'],None),('air-select',1,['SELECT'],None),
    ('land-without-delayed-toggle',32,[],None),('fresh-ground-select',1,['SELECT'],None),
    ('wait-dismounted',64,[],'dismounted'),('release-select-before-remount',1,[],None),
    ('fresh-remount-select',2,['SELECT'],None),
    ('wait-remounted',120,[],'remounted'),('right-hop-for-y',32,['RIGHT'],'second-started'),
    ('open-y-in-flight',1,['Y'],None),('choose-cyndaquil',1,['Y','L'],None),
    ('confirm-y-in-flight',1,[],None),('land-and-switch',180,[],'switched'),
    ('verify-no-repeat',24,[],None))
ORDER=tuple(a[0] for a in ACTION_SPEC)


def need(value,reason):
    if not value:raise ValueError('mounted airborne input: '+reason)


def action_args(spec):
    _name,frames,keys,stage=spec
    args=dict(frames=frames,keys=keys)
    if stage:args['until']=dict(kind='measurement-stage',measurement=KIND,stage=stage,when='final')
    return args


def validate_recipe(test):
    need(test['id']==TEST and test['mode']=='prepared' and test['fixture']==dict(rom='test.nds',save='test.sav')
        and test['requirements']==[REQUIREMENT]
        and test['subjects']==[dict(id='mankey',species=56,role='MOUNTED',acquire='existing')]
        and test['measurements']==[dict(kind=KIND,subject='mankey')]
        and tuple((a['id'],a['op'],a['args']) for a in test['setup'])==SETUP
        and tuple((a['id'],a['op'],a['args']) for a in test['actions'])
            ==tuple((s[0],'step',action_args(s)) for s in ACTION_SPEC)
        and test['assertions']==[dict(kind='measurement-complete',measurement=KIND,when='final')]
        and test['budgets']==dict(maxSeconds=240,maxFrames=900,noProgressFrames=180,minObservedFrames=70),
        'recipe differs from the finite normal Select/Y trigger')


class MountAirborneMeasurement:
    # These existing methods authenticate the completed queue, current full
    # mount binding, rider seat and decoded native shared Motion bytes.
    _boundary=MountedCanopyHopMeasurement._boundary
    _actor=MountedCanopyHopMeasurement._actor
    _native=MountedCanopyHopMeasurement._native

    def __init__(self,source):
        self.source=source
        self.subject=self.latest=self.baseline=None
        self.setup_index=self.setup_frames=self.action_index=self.action_frames=self.observed_frames=0
        self.events=[];self.flights=[];self.failures=[]
        self.trace_stream=self.trace_sequence=None
        self.select_frame=self.fresh_frame=self.dismount_frame=self.remount_frame=None
        self.y_confirm=self.queue_start=self.switched=None
        self.remount_select_frame=None
        self.queue_rises=0;self.previous_queue=0;self.idle_after_select=self.no_repeat_frames=0
        self.saved={}

    def _saved_party(self,sample):
        for slot,species in ((2,56),(1,155)):
            rows=[p for p in sample.get('party',[]) if p.get('slot')==slot]
            need(len(rows)==1 and rows[0].get('identityVerified') is True
                and rows[0].get('species')==species and rows[0].get('hp',0)>0
                and rows[0].get('isEgg') is False,'saved living Mankey/Cyndaquil party slots differ')
            pid=rows[0]['personality']
            if slot not in self.saved:self.saved[slot]=pid
            need(pid==self.saved[slot],'saved party identity changed')

    def _find(self,sample,species,role):
        actors=[a for a in sample.get('actors',[]) if a.get('active') is True
                and (a.get('species'),a.get('role'))==(species,role)]
        if len(actors)!=1:return None
        a=actors[0];select_current_actor(sample,a)
        need(a.get('subjectIdentity')==self.saved[2 if species==56 else 1]
             and a.get('identityVerified') is True and a.get('presentationAttached') is True,
             'role transfer changed the saved party Pokemon')
        return a

    def arm(self,sample,subject):
        self._boundary(sample);self._saved_party(sample)
        self.subject=deepcopy(select_current_actor(sample,subject))
        a=self._actor(sample)
        need(a['subjectIdentity']==self.saved[2] and a['motionKind']=='NONE' and a['motionPhase']=='IDLE'
            and a['reservationId']==0 and a['logical']==dict(x=564,y=375)
            and (sample['player']['x'],sample['player']['y'])==ORIGIN
            and sample['selector']['activeFollowerPartySlot']==2
            and sample['selector']['queue']['count']==sample['selector']['queue']['request']==0,
            'baseline is not settled saved party2 mounted Mankey at564375')
        self.baseline=deepcopy(a);self.latest=deepcopy(sample)

    def _events(self,sample,events):
        for event in events:
            d=event.get('data',{})
            if event.get('kind')=='trace-status':
                need(d.get('code')=='ring-overwrite' and d.get('unreadEventsLost')==0,
                     'semantic trace lost observations')
            if event.get('kind')!='native':continue
            need(type(d.get('sequence')) is int and type(d.get('traceStream')) is int
                 and d.get('traceFieldEpoch')==sample['context']['fieldEpoch'], 'native event identity is missing')
            if self.trace_stream is None:self.trace_stream=d['traceStream']
            need(d['traceStream']==self.trace_stream and (self.trace_sequence is None
                 or d['sequence']==self.trace_sequence+1),'semantic native sequence has loss/reset/duplicate')
            self.trace_sequence=d['sequence'];self.events.append(dict(d,frame=event['frame']))

    def _flight(self,sample,actor,number):
        motion=self._native(sample,actor);plan=motion['plan']
        f=self.flights[number] if len(self.flights)>number else None
        if f is None and actor['motionKind']!='HOP':return
        if f is None:
            origin=list(ORIGIN if number==0 else FIRST_TARGET)
            direction=2 if number==0 else 3
            target=list(FIRST_TARGET) if number==0 else [origin[0]+plan['distance'],origin[1]]
            need(motion['elapsed']==actor['motionElapsed']==1 and plan['version']==1 and plan['kind']==2
                and plan['flags']==0 and plan['origin']==origin and plan['target']==target
                and plan['direction']==plan['facing']==direction
                and (plan['distance']==1 if number==0 else 1<=plan['distance']<=6)
                and 6<=plan['duration']<=120 and plan['arcHeightQ4']>0
                and plan['fieldEpoch']==actor['handle']['fieldEpoch']
                and plan['behaviorFingerprint']==actor['behaviorFingerprint']&65535,
                'normal Hop plan/start differs')
            starts=[e for e in self.events if e['frame']==sample['frame'] and e['actorHandle']==actor['handle']['value']
                    and e['event']=='MOTION_STARTED' and e['reasonId']==0 and (e['valueA'],e['valueB'])==(2,plan['duration'])]
            need(len(starts)==1,'normal Hop lacks its current native start receipt')
            f=dict(actor=deepcopy(actor['handle']),plan=deepcopy(plan),startSequence=starts[0]['sequence'],
                startFrame=sample['frame'],commitBefore=actor['commitSequence'],samples=[],release=None)
            self.flights.append(f)
        if f['release'] is not None:return
        own=[e for e in self.events if e['sequence']>f['startSequence'] and e['actorHandle']==f['actor']['value']]
        # Y may use the existing explicit Cancel cleanup at the landed end.
        # It must keep the accepted target, complete the real travel, and
        # return control. Normal END is not a new requirement for that path.
        if number==1 and self.y_confirm is not None and motion['phase']=='CANCELED':
            p=f['plan'];engine=actor['engineObject'];player=sample['player']
            terminal=[e for e in own if e['event'] in ('MOTION_CANCELED','CONTROL_RETURNED')]
            prior=f['samples'][-1]['elapsed'] if f['samples'] else 0
            need(motion['plan']==p and motion['elapsed']==p['duration'] and prior in (p['duration']-1,p['duration'])
                 and motion['cancelReason']==1 and actor['motionPhase']=='CANCELED'
                 and actor['handle']==f['actor'] and actor['inputOwnership']==0 and actor['reservationId']==0
                 and [e['event'] for e in terminal]==['MOTION_CANCELED','CONTROL_RETURNED']
                 and [e['valueA'] for e in terminal]==[2,0]
                 and all(e['frame']==sample['frame'] and e['reasonId']==1
                         and e.get('actor')=={k:v for k,v in f['actor'].items() if k!='value'} for e in terminal)
                 and not any(e['event'] in ('ACTOR_REBOUND','CONTEXT_CHANGED') for e in own),
                 'Y cleanup canceled before the accepted Hop landed')
            need(actor['logical']==dict(zip(('x','y'),p['target']))
                 and (player['x'],player['y'])==tuple(p['target']) and engine['face_y']==0,
                 'landed Y cleanup rewound the accepted logical target')
            for pose in (engine,player):
                need((pose['pos_x'],pose['pos_z'])==tuple((v<<16)+32768 for v in p['target'])
                     and pose['pos_y']==p['targetBaseY'] and pose['unk88_y']==0,
                     'landed Y cleanup rewound the accepted target or height')
            if prior<p['duration']:f['samples'].append(dict(frame=sample['frame'],elapsed=p['duration']))
            f['release']=dict(frame=sample['frame'],events=deepcopy(terminal),kind='landed-explicit-cleanup')
            return
        need(not any(e['event'] in ('MOTION_CANCELED','ACTOR_REBOUND','CONTEXT_CHANGED') for e in own),
             'airborne input canceled or detached the accepted Hop')
        need(actor['handle']==f['actor'] and motion['plan']==f['plan'], 'accepted Hop identity/plan changed')
        for e in own:
            need(e.get('actor')=={k:v for k,v in f['actor'].items() if k!='value'},'native Hop receipt owner differs')
        duration=plan['duration'];elapsed=motion['elapsed'];prior=f['samples'][-1]['elapsed'] if f['samples'] else 0
        if actor['motionKind']=='HOP':
            need(actor['inputOwnership']==1 and actor['motionPhase'] in ('MOVING','COMMIT_PENDING')
                 and elapsed==actor['motionElapsed'] and 1<=elapsed<=duration
                 and (elapsed==prior+1 or elapsed==prior==duration)
                 and actor['reservationId']==plan['reservationId'], 'Hop elapsed/reservation/input continuity differs')
            engine=actor['engineObject']
            def lerp(a,b):return a+int(Fraction((b-a)*elapsed,duration))
            need(engine['pos_x']==lerp((plan['origin'][0]<<16)+32768,(plan['target'][0]<<16)+32768)
                 and engine['pos_z']==lerp((plan['origin'][1]<<16)+32768,(plan['target'][1]<<16)+32768)
                 and engine['pos_y']==lerp(plan['startBaseY'],plan['targetBaseY'])
                 and engine['face_y']==arc_height(elapsed,duration)//16*plan['arcHeightQ4']
                 and engine['unk88_y']==0,'same accepted Hop rendered arc differs')
            if elapsed!=prior:f['samples'].append(dict(frame=sample['frame'],elapsed=elapsed))
        else:
            terminal=[e for e in own if e['event'] in ('LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED')]
            need(prior==duration and [e['event'] for e in terminal]==['LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED']
                 and all(e['frame']==sample['frame'] and e['reasonId']==0 for e in terminal)
                 and actor['commitSequence']==f['commitBefore']+1 and actor['motionKind']=='NONE'
                 and actor['motionPhase']=='IDLE' and actor['reservationId']==0,
                 'Hop lacks its normal landed commit/finish/input return')
            need(actor['logical']==dict(zip(('x','y'),plan['target']))
                 and (sample['player']['x'],sample['player']['y'])==tuple(plan['target'])
                 and all((pose['pos_x'],pose['pos_z'])==tuple((v<<16)+32768 for v in plan['target'])
                         for pose in (actor['engineObject'],sample['player']))
                 and actor['engineObject']['pos_y']==plan['targetBaseY']
                 and actor['engineObject']['face_y']==actor['engineObject']['unk88_y']==0,
                 'landed mount retains height or offset')
            f['release']=dict(frame=sample['frame'],events=deepcopy(terminal))

    def _sample(self,sample,events,action):
        self._boundary(sample);need(sample['context']==self.latest['context'],'field context changed')
        self._saved_party(sample);self._events(sample,events)
        selector=sample['selector'];q=selector['queue'];raw=selector['rawHeld']
        need(selector.get('simulatedKeys')==0,'input was simulated')
        expected=sum(dict(SELECT=4,LEFT=32,RIGHT=16,Y=2048,L=512)[k]
                     for k in ACTION_SPEC[ORDER.index(action)][2])
        prior_raw=self.latest['selector']['rawHeld']
        need(raw==expected or self.action_frames==0 and raw==prior_raw,'native input differs from the declared action')
        if action in ('left-to-tree','air-select','land-without-delayed-toggle'):
            actor=self._actor(sample);self._flight(sample,actor,0)
            if action=='air-select':
                need(self.flights and self.flights[0]['release'] is None and actor['motionElapsed']<actor['motionDuration']
                     and selector['rawNew']==selector['newKeys']==4 and raw==4
                     and q['request']==q['count']==0,'Select was not one ignored airborne press')
                self.select_frame=sample['frame']
            if action=='land-without-delayed-toggle' and self.flights[0]['release'] is not None:
                need(actor['motionKind']=='NONE' and actor['inputOwnership']==1 and q['request']==q['count']==0,
                     'airborne Select became a delayed dismount')
                self.idle_after_select+=1
        elif action=='fresh-ground-select':
            need(self.flights[0]['release'] and self.idle_after_select>=8 and raw==selector['rawNew']==4
                 and selector['newKeys']==4,'fresh grounded Select edge is missing')
            self.fresh_frame=sample['frame']
        elif action=='wait-dismounted':
            follower=self._find(sample,56,'FOLLOWER')
            if follower is not None and not any(a.get('role')=='MOUNTED' and a.get('active') for a in sample['actors']):
                self.dismount_frame=sample['frame']
        elif action=='release-select-before-remount':
            need(self.dismount_frame is not None and raw==selector['heldKeys']==0
                 and selector['rawNew']==selector['newKeys']==0
                 and self._find(sample,56,'FOLLOWER') is not None,
                 'Select was not released before the fresh remount press')
        elif action=='fresh-remount-select':
            need(self.dismount_frame is not None,'remount press preceded the dismount')
            if raw==0:
                need(self.action_frames==0 and self.remount_select_frame is None
                     and prior_raw==selector['heldKeys']==selector['rawNew']==selector['newKeys']==0,
                     'only the first remount queue may still have neutral input')
            elif self.remount_select_frame is None:
                need(prior_raw==0 and raw==selector['heldKeys']==selector['rawNew']==selector['newKeys']==4,
                     'fresh remount Select edge is missing')
                self.remount_select_frame=sample['frame']
            else:
                need(prior_raw==raw==selector['heldKeys']==4
                     and selector['rawNew']==selector['newKeys']==0,
                     'remount Select repeated its press edge')
        elif action=='wait-remounted':
            mount=self._find(sample,56,'MOUNTED')
            if (mount is not None and mount['inputOwnership']==1 and mount['motionKind']=='NONE'
                    and mount['reservationId']==0 and mount['motionPhase'] in ('IDLE','CANCELED')):
                # Begin accepts both terminal phases.  Mounting may cancel an
                # ordinary Follower Hop; only this exact grounded pair is ready.
                selected=select_current_actor(sample,mount)
                need(engine_binding_identity(selected['engineIdentity'])
                     ==engine_binding_identity(self.subject['engineIdentity']),
                     'remount changed its current saved Pokemon engine binding')
                self.subject=deepcopy(selected)
                mount=self._actor(sample);motion=self._native(sample,mount)
                need(motion['phase']==mount['motionPhase'] and motion['settleRemaining']==0,
                     'remounted native motion is not terminal')
                target=self.flights[0]['plan']
                need(mount['logical']==dict(zip(('x','y'),FIRST_TARGET))
                     and (sample['player']['x'],sample['player']['y'])==FIRST_TARGET
                     and all((pose['pos_x'],pose['pos_z'])==tuple((v<<16)+32768 for v in FIRST_TARGET)
                             and pose['pos_y']==target['targetBaseY'] and pose['unk88_y']==0
                             for pose in (mount['engineObject'],sample['player']))
                     and mount['engineObject']['face_y']==0,
                     'remounted Mankey is not at the exact grounded first landing')
                if self.remount_frame is None:
                    self.remount_frame=sample['frame']
        elif action in ('right-hop-for-y','open-y-in-flight','choose-cyndaquil','confirm-y-in-flight','land-and-switch'):
            if len(self.flights)<2 or self.flights[1]['release'] is None:
                actor=self._find(sample,56,'MOUNTED')
                need(actor is not None,'current mounted Mankey vanished before landed Y cleanup')
                if actor['inputOwnership']==1:actor=self._actor(sample)
                else:need(self.y_confirm is not None,'mount input was lost before confirmed Y')
                self._flight(sample,actor,1)
            if action in ('open-y-in-flight','choose-cyndaquil','confirm-y-in-flight'):
                need(len(self.flights)==2 and self.flights[1]['release'] is None
                     and actor['motionElapsed']<actor['motionDuration'],'Y action was not airborne')
                if action=='open-y-in-flight':need(raw==2048 and selector['state']==2 and selector['highlight']==2,'Y did not open at saved Mankey')
                elif action=='choose-cyndaquil':need(raw==2560 and selector['state']==2 and selector['highlight']==1,'L did not choose saved party1 Cyndaquil')
                else:
                    need(raw==0 and selector['state']==0 and q['request']==0x81 and q['count']==0,
                         'confirmed airborne Y choice was dropped or queued early')
                    self.y_confirm=sample['frame']
            if self.y_confirm is not None:
                released=self.flights[1]['release']
                if released is None:
                    need(q['request']==0x81 and q['count']==0,'confirmed Y choice was lost or executed before landing')
                elif q['count']>0 and self.queue_start is None:
                    need(q['request']==0 and q['commands']&63==0x17 and q['count']==2,
                         'landed Y choice did not queue one despawn/spawn pair')
                    self.queue_start=sample['frame']
                if (self.queue_start is not None and selector['activeFollowerPartySlot']==1
                        and q['count']==q['request']==0 and selector['followerReleaseState']&0x7F==0):
                    # SPAWN owns the new actor while its release animation
                    # runs.  Select only after that native queue has finished.
                    follower=self._find(sample,155,'FOLLOWER')
                    if follower is not None:
                        self.switched=dict(frame=sample['frame'],actor=deepcopy(follower),selector=deepcopy(selector))
        elif action=='verify-no-repeat':
            need(self.switched is not None and self._find(sample,155,'FOLLOWER') is not None
                 and not any(a.get('active') and a.get('role')=='MOUNTED' for a in sample['actors'])
                 and selector['activeFollowerPartySlot']==1 and q['count']==q['request']==0
                 and selector['followerReleaseState']&0x7F==0,
                 'confirmed Y choice ran again after completion')
            self.no_repeat_frames+=1
        if self.y_confirm is not None and q['count']>0 and self.previous_queue==0:self.queue_rises+=1
        need(self.queue_rises<=1,'confirmed Y choice queued more than once')
        self.previous_queue=q['count'];self.latest=deepcopy(sample)
        self.observed_frames+=1;self.action_frames+=1

    def stage(self,name):
        need(name in ('dismounted','remounted','second-started','switched'),'unknown airborne input stage')
        return not self.failures and dict(dismounted=self.dismount_frame is not None,
            remounted=self.remount_frame is not None,**{'second-started':len(self.flights)==2},
            switched=self.switched is not None)[name]

    def observe_record(self,row,on_sample=None):
        try:
            if 'initialSnapshot' in row:
                need(self.latest is None and row.get('phase')=='setup','initial boundary differs')
                self._boundary(row['initialSnapshot'],False);self.latest=deepcopy(row['initialSnapshot'])
            elif row.get('phase')=='setup':
                need(self.setup_index<len(SETUP) and row.get('action')==SETUP[self.setup_index][0],'setup order differs')
                if SETUP[self.setup_index][1]=='step':
                    need('command' not in row and row.get('requestedInput',{}).get('keys')==[],'settle setup is not neutral')
                    for sample,_events,_intervals in validate_raw_chunk(row,self.latest):
                        self._boundary(sample);self.latest=deepcopy(sample);self.setup_frames+=1
                    need(self.setup_frames<=24,'settle exceeded24 frames')
                    if self.setup_frames<24:return self.result()
                else:
                    need(row.get('command')==SETUP[self.setup_index][1],'setup command differs')
                    self._boundary(row['snapshot'])
                    if row['action']=='mount-saved-mankey':need(row.get('receipt',{}).get('lifecycle')=='prepared-native-follower-lifecycle','mount setup changed its native lifecycle')
                    if row['command']=='bind':self.arm(row['snapshot'],row['receipt'])
                    self.latest=deepcopy(row['snapshot'])
                self.setup_index+=1
            else:
                need(self.setup_index==len(SETUP) and self.action_index<len(ORDER)
                     and row.get('phase')=='observe' and row.get('action')==ORDER[self.action_index]
                     and 'command' not in row,'observation action/order differs')
                spec=ACTION_SPEC[self.action_index]
                for sample,events,_intervals in validate_raw_chunk(row,self.latest):
                    need(self.observed_frames<600,'observation exceeded600 frames')
                    self._sample(sample,events,spec[0])
                    if on_sample:on_sample(sample,self.observed_frames)
                need(self.action_frames<=spec[1],'action exceeded its bound')
                if self.action_frames==spec[1] or spec[3] and self.stage(spec[3]):
                    need(spec[3] is None or self.stage(spec[3]),'bounded role/landing action did not reach its stage')
                    if spec[0]=='land-without-delayed-toggle':need(self.flights[0]['release'] is not None and self.idle_after_select>=8,'no landed idle interval after ignored Select')
                    if spec[0]=='fresh-remount-select':need(self.remount_select_frame is not None,'bounded remount Select never produced a press edge')
                    self.action_index+=1;self.action_frames=0
        except (ValueError,KeyError,TypeError,StopIteration,IndexError) as error:self.failures.append(str(error))
        return self.result()

    def result(self):
        ready=not self.failures and self.action_index==len(ORDER) and len(self.flights)==2
        ready=ready and all(f['release'] for f in self.flights) and self.select_frame is not None
        ready=bool(ready and self.fresh_frame and self.dismount_frame and self.remount_select_frame and self.remount_frame
                   and self.y_confirm and self.queue_start and self.switched and self.queue_rises==1 and self.no_repeat_frames==24)
        return dict(kind=KIND,requirements=[REQUIREMENT],ready=ready,passed=ready,acceptedProof=False,
            observedFrames=self.observed_frames,observedFrameUnit='completed-game-frame',subject=deepcopy(self.subject),
            flights=deepcopy(self.flights),selectFrame=self.select_frame,idleAfterSelect=self.idle_after_select,
            freshSelectFrame=self.fresh_frame,dismountFrame=self.dismount_frame,remountFrame=self.remount_frame,
            remountSelectFrame=self.remount_select_frame,
            yConfirmFrame=self.y_confirm,queueStartFrame=self.queue_start,queueRises=self.queue_rises,
            switched=deepcopy(self.switched),noRepeatFrames=self.no_repeat_frames,failures=list(self.failures))

    def finish(self):
        if not self.result()['ready'] and not self.failures:self.failures.append('mounted airborne input: incomplete Select/Y landing sequence')
        return self.result()
