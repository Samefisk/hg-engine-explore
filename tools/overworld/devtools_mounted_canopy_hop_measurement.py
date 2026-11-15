"""One normal directional Hop onto the exact adjacent tree top (TKT-0078).

Uses existing current Actor, shared Motion, resolver, terrain and raw queue
readers. The catalog offset alone never counts as a final world height.
"""
from copy import deepcopy
from fractions import Fraction
from tools.overworld.normal_play_observer import arc_height
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor, engine_binding_identity
from tools.overworld.devtools_walk_matrix_observer import decode_motion

KIND='mounted-mankey-adjacent-canopy-v1'
TEST='mount.mankey-adjacent-canopy'
REQUIREMENT='current.mounted-mankey-adjacent-canopy'
ORIGIN=(561,364)
TARGET=(562,364)
OFFSET=0x31580
SETUP=(('route30-tree','teleport',dict(map=34,x=561,z=364,facing=3)),
       ('settle-field','step',dict(frames=24,keys=[])),
       ('mount-saved-mankey','spawn',dict(species=56,form=0,role='mounted',slot=2,level=3)),
       ('bind-mankey','bind',dict(subject='mankey')))
ORDER=('right-to-adjacent-tree','release-through-canopy-terminal')


def need(value, reason):
    if not value:raise ValueError('mounted canopy Hop: '+reason)


def validate_recipe(test):
    stage=dict(kind='measurement-stage',measurement=KIND,stage='started',when='final')
    need(test['id']==TEST and test['mode']=='prepared' and test['requirements']==[REQUIREMENT]
         and test['subjects']==[dict(id='mankey',species=56,role='MOUNTED',acquire='existing')]
         and test['measurements']==[dict(kind=KIND,subject='mankey')]
         and tuple((a['id'],a['op'],a['args']) for a in test['setup'])==SETUP
         and tuple((a['id'],a['op'],a['args']) for a in test['actions'])==(
             (ORDER[0],'step',dict(frames=32,keys=['RIGHT'],until=stage)),
             (ORDER[1],'step',dict(frames=64,keys=[])))
         and test['assertions']==[dict(kind='measurement-complete',measurement=KIND,when='final')]
         and test['budgets']['maxFrames']<=480 and test['budgets']['minObservedFrames']>=24,
         'recipe differs from exact RIGHT-only adjacent-tree trigger')


class MountedCanopyHopMeasurement:
    def __init__(self,source):
        self.source=source
        self.latest=self.subject=self.baseline=self.hop=self.release=None
        self.setup_index=self.action_index=self.observed_frames=self.neutral_frames=self.setup_frames=0
        self.events=[]
        self.failures=[]
        self.trace_stream=self.trace_sequence=None

    def _boundary(self,sample,fixture=True):
        coverage=sample.get('nativeObservation',{})
        need(sample.get('fieldAvailable') is True
             and sample.get('observationBoundary')=='main-task-queue-completion'
             and sample.get('romSha256')==self.source['romSha256']
             and sample.get('fieldControl',{}).get('taskPointer')==0
             and coverage.get('coverageComplete') is True and coverage.get('installedBeforeBoot') is True
             and all(coverage.get(k)==0 for k in ('eventsDropped','profilesEvicted','pendingUnframedEvents'))
             and coverage.get('error') is None,'completed current field/native coverage differs')
        if fixture:need(sample.get('context',{}).get('mapId')==34,'left Route30 tree fixture')

    def _actor(self,sample):
        selected=select_current_actor(sample,self.subject)
        actor=next(a for a in sample['actors'] if a['handle']==selected['handle'])
        need((actor['species'],actor['role'])==(56,'MOUNTED') and actor.get('inputOwnership')==1
             and actor['handle']['slot']==7
             and engine_binding_identity(selected['engineIdentity'])
                 ==engine_binding_identity(self.subject['engineIdentity']), 'current mount binding/input owner differs')
        engine,player=actor['engineObject'],sample['player']
        need(all(engine.get(k)==player.get(k) for k in ('pos_x','pos_y','pos_z','unk88_y'))
             and player.get('face_y')-engine.get('face_y')==32768,
             'mount and rider split their shared anchor/seat')
        return actor

    def _profile(self,sample,actor,cache):
        coverage=sample['nativeObservation']
        need(isinstance(cache,dict) and cache.get('frame',-1)>=sample['frame']
             and cache.get('nativeCycle',-1)>=sample['nativeCycle']
             and actor['behaviorFingerprint'] in coverage.get('profileFingerprints',[]),
             'missing current native resolver cache')
        rows=[r for r in cache.get('resolvedProfiles',[]) if r.get('resolved') is True
              and r.get('fingerprint')==actor['behaviorFingerprint']]
        need(rows and len({r.get('resultHex') for r in rows})==1
             and all(r.get('sourceSha256')==self.source['profileSha256'] for r in rows),
             'resolved profile differs from sealed current source')
        raw=bytes.fromhex(rows[0]['resultHex']);lane=raw[80:160]
        need(len(raw)==216 and lane[12]==2 and tuple(lane[20:22])==(1,6)
             and int.from_bytes(lane[32:34],'little')==69 and tuple(lane[48:50])==(30,150)
             and lane[58]&1==0
             and int.from_bytes(raw[192:196],'little')==actor['behaviorFingerprint'],
             'requires normal Hop/LongHop1..6/CanopyAccess/elevation30:150/chainOff')
        return deepcopy(rows[0])

    def _native(self,sample,actor):
        combat=sample.get('pokemonCombat',{})
        need(combat.get('available') is True and combat.get('schemaVersion')==1
             and combat.get('frame')==sample['frame'] and combat.get('nativeCycle')==sample['nativeCycle']
             and combat.get('identity',{}).get('romSha256')==self.source['romSha256']
             and combat['identity'].get('overlaySha256')==self.source['overlaySha256'],
             'missing coherent shared native Motion owner')
        rows=[r for r in combat.get('targets',[]) if r.get('handle')==actor['handle']]
        need(len(rows)==1 and (rows[0].get('species'),rows[0].get('role'),rows[0].get('personality'))
             ==(56,'MOUNTED',actor['subjectIdentity']) and rows[0].get('hpSource')=='party'
             and rows[0].get('hp',0)>0 and rows[0].get('knockbackPending')==0,
             'native Motion has another living party owner or pending hit')
        motion=rows[0].get('motion')
        need(isinstance(motion,dict) and motion==decode_motion(bytes.fromhex(motion.get('rawHex',''))),
             'native Motion bytes differ')
        return motion

    def _terrain(self,sample):
        terrain=sample.get('terrain',{});stamp=terrain.get('observation',{})
        need(stamp.get('boundary')=='paused-native-cycle-end' and stamp.get('context')==sample['context']
             and stamp.get('lastCompletedGameFrame')==sample['frame']
             and stamp.get('nativeCycle')==sample['nativeCycle'], 'current native terrain stamp differs')
        cells={(c.get('x'),c.get('z')):c for c in terrain.get('cells',[])}
        origin,target=cells.get(ORIGIN,{}),cells.get(TARGET,{})
        for cell in (origin,target):
            p=cell.get('provenance',{})
            need(cell.get('loaded') is True and p.get('mapHeaderId')==34
                 and p.get('fieldPointer')==sample['fieldControl'].get('fieldPointer')
                 and p.get('landDataIdentity')=='current-map-matrix'
                 and p.get('rawWord')==cell.get('attribute'), 'loaded terrain provenance differs')
        surface=target.get('surface',{})
        need(origin.get('collision') is False and origin.get('surface',{}).get('known') is True
             and origin['surface'].get('present') is False
             and target.get('behavior')==6 and target.get('collision') is True
             and surface.get('known') is True and surface.get('present') is True
             and surface.get('type')=='canopy' and surface.get('surfaceId')==0xFFFE
             and surface.get('heightMode')=='native-ground-offset'
             and surface.get('heightOffsetFx32')==OFFSET,
             'exact adjacent tree footprint/support is absent or wrong')
        return deepcopy(origin),deepcopy(target)

    def arm(self,sample,subject):
        self._boundary(sample)
        self.subject=deepcopy(select_current_actor(sample,subject))
        actor=self._actor(sample)
        need(actor.get('motionKind')=='NONE' and actor.get('motionPhase')=='IDLE'
             and actor.get('reservationId')==0 and actor.get('logical')==dict(zip(('x','y'),ORIGIN))
             and (sample['player']['x'],sample['player']['y'])==ORIGIN
             and actor['engineObject'].get('pos_y')==0x20000
             and actor['engineObject'].get('face_y')==actor['engineObject'].get('unk88_y')==0,
             'baseline is not the real idle ground-mounted Mankey at561364')
        party=[p for p in sample.get('party',[]) if p.get('slot')==2]
        need(len(party)==1 and party[0].get('identityVerified') is True
             and party[0].get('species')==56 and party[0].get('personality')==actor['subjectIdentity']
             and sample.get('selector',{}).get('activeFollowerPartySlot')==2,
             'mounted subject is not the unchanged current party2 Mankey')
        origin,target=self._terrain(sample)
        self.baseline=dict(actor=deepcopy(actor),player=deepcopy(sample['player']),origin=origin,target=target)
        self.latest=deepcopy(sample)

    def _events(self,sample,events):
        for event in events:
            d=event.get('data',{})
            if event.get('kind')=='trace-status':
                need(d.get('code')=='ring-overwrite' and d.get('unreadEventsLost')==0
                     and type(d.get('traceStream')) is int
                     and (self.trace_stream is None or d['traceStream']==self.trace_stream),
                     'semantic trace expired/lost/reset or changed')
                if self.trace_stream is None:self.trace_stream=d['traceStream']
            if event.get('kind')!='native':continue
            need(type(d.get('sequence')) is int and type(d.get('traceStream')) is int
                 and d.get('traceFieldEpoch')==sample['context']['fieldEpoch'], 'semantic native owner/sequence missing')
            if self.trace_stream is None:self.trace_stream=d['traceStream']
            need(d['traceStream']==self.trace_stream
                 and (self.trace_sequence is None or d['sequence']==self.trace_sequence+1),
                 'semantic native sequence has loss/reset/duplicate')
            self.trace_sequence=d['sequence']
            if d.get('actorHandle')!=self.subject['handle']['value']:continue
            need(d.get('actor')=={k:v for k,v in self.subject['handle'].items() if k!='value'},
                 'semantic event has another full Actor owner')
            need(d.get('event') not in ('MOTION_CANCELED','ACTOR_REBOUND','CONTEXT_CHANGED')
                 and not(d.get('event')=='WORLD_EFFECT' and d.get('valueA')==3),
                 'crash, cancel or rebound during canopy Hop')
            self.events.append(dict(d,frame=event['frame']))

    def _terminal_wait(self,sample,actor,motion):
        # Travel coverage is already complete. A native stream wait repeats
        # its exact landed pose; it is neither another travel frame nor a commit.
        plan=self.hop['plan'];engine=actor['engineObject']
        need([r['elapsed'] for r in self.hop['samples']]==list(range(1,plan['duration']+1))
             and motion['plan']==plan and actor['motionKind']=='HOP'
             and motion['elapsed']==actor['motionElapsed']==plan['duration']
             and actor['motionPhase']==motion['phase']=='COMMIT_PENDING'
             and actor['streamState']==1 and actor['reservationId']==plan['reservationId']
             and actor['origin']==dict(zip(('x','y'),plan['origin']))
             and actor['target']==actor['logical']==dict(zip(('x','y'),plan['target']))
             and (sample['player']['x'],sample['player']['y'])==tuple(plan['target'])
             and actor['commitSequence']==self.baseline['actor']['commitSequence']
             and motion['commitPublished']==0
             and not any(e['sequence']>self.hop['startSequence']
                 and e['event'] in ('LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED') for e in self.events)
             and engine.get('pos_x')==(plan['target'][0]<<16)+32768
             and engine.get('pos_z')==(plan['target'][1]<<16)+32768
             and engine.get('pos_y')==plan['targetBaseY']
             and engine.get('face_y')==engine.get('unk88_y')==0,
             'terminal stream wait changed locked pose/plan/reservation or committed early')
        self.hop.setdefault('terminalWaitSamples',[]).append(
            dict(frame=sample['frame'],elapsed=motion['elapsed'],nativeCycle=sample['nativeCycle']))

    def _sample(self,sample,events,cache):
        self._boundary(sample);need(sample['context']==self.latest['context'],'field context changed')
        actor=self._actor(sample)
        held=sample.get('selector',{})
        # The first physical queue may precede the native key poll. It is
        # not a Hop witness; the actual start must see RIGHT and no B.
        allowed=(0,16) if self.action_index==0 and self.observed_frames==0 else (16,) if self.action_index==0 else (0,16) if self.neutral_frames==0 else (0,)
        need(held.get('rawHeld')==held.get('heldKeys') and held.get('rawHeld') in allowed
             and held.get('simulatedKeys')==0,'normal RIGHT-only/released input differs')
        self._events(sample,events)
        motion=self._native(sample,actor)
        if self.hop is None and motion['plan']['kind']==2 and motion['phase'] in ('PLANNED','MOVING','COMMIT_PENDING'):
            need(actor['motionKind']=='HOP','native Hop/public motion kind differs')
        if self.hop is None and actor['motionKind']=='HOP':
            need(held.get('rawHeld')==16,'actual Hop start did not consume RIGHT-only input')
            profile=self._profile(sample,actor,cache);plan=motion['plan']
            need(motion['elapsed']==actor['motionElapsed']==1 and plan['version']==1 and plan['kind']==2
                 and plan['flags']==0 and plan['fieldEpoch']==actor['handle']['fieldEpoch']
                 and plan['behaviorFingerprint']==actor['behaviorFingerprint']&65535
                 and plan['origin']==list(ORIGIN) and plan['target']==list(TARGET)
                 and plan['distance']==1 and plan['direction']==plan['facing']==3
                 and type(plan['duration']) is int and 1<=plan['duration']<=60
                 and type(plan['arcHeightQ4']) is int and 16<=plan['arcHeightQ4']<=255
                 and plan['startBaseY']==self.baseline['actor']['engineObject']['pos_y']
                 and plan['targetBaseY']==plan['startBaseY']+OFFSET,
                 'one adjacent raised shared Hop plan/native base differs')
            starts=[e for e in self.events if e['frame']==sample['frame'] and e['event']=='MOTION_STARTED'
                    and (e.get('valueA'),e.get('valueB'))==(2,plan['duration']) and e.get('reasonId')==0]
            need(len(starts)==1 and any(e['event']=='INTENT_CREATED' and e['frame']==sample['frame']
                 and e['sequence']<starts[0]['sequence'] for e in self.events), 'Hop lacks a new normal input intent/start')
            self.hop=dict(actor=deepcopy(actor['handle']),plan=deepcopy(plan),sourceProfile=profile,
                startFrame=sample['frame'],startSequence=starts[0]['sequence'],samples=[])
        if self.hop is None:
            need(actor['motionKind']=='NONE' and actor['logical']==dict(zip(('x','y'),ORIGIN)),
                 'walked/moved without the required native Hop')
        elif self.release is None:
            plan=self.hop['plan'];duration=plan['duration']
            need(motion['plan']==plan,'native Hop plan/endpoint changed in flight')
            elapsed=motion['elapsed'];previous=self.hop['samples'][-1]['elapsed'] if self.hop['samples'] else 0
            engine=actor['engineObject']
            if actor['motionKind']=='HOP' and elapsed==previous==duration:
                self._terminal_wait(sample,actor,motion)
            elif actor['motionKind']=='HOP':
                need(elapsed==actor['motionElapsed']==previous+1 and elapsed<=duration
                     and actor['reservationId']==plan['reservationId'] and actor['origin']==dict(zip(('x','y'),ORIGIN))
                     and actor['target']==dict(zip(('x','y'),TARGET)), 'Hop skipped a native flight sample')
                expected_base=plan['startBaseY']+int(Fraction(OFFSET*elapsed,duration))
                expected_arc=arc_height(elapsed,duration)//16*plan['arcHeightQ4']
                need(engine.get('pos_x')==(ORIGIN[0]<<16)+32768+int(Fraction(65536*elapsed,duration))
                     and engine.get('pos_z')==(ORIGIN[1]<<16)+32768
                     and engine.get('pos_y')==expected_base and engine.get('face_y')==expected_arc
                     and engine.get('unk88_y')==0,'Hop rendered arc/native base differs')
                self.hop['samples'].append(dict(frame=sample['frame'],elapsed=elapsed,engine=deepcopy(engine)))
            else:
                terminal=[e for e in self.events if e['sequence']>self.hop['startSequence']
                          and e['event'] in ('LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED')]
                commit=self.baseline['actor']['commitSequence']+1
                need(previous==duration and [e['event'] for e in terminal]
                     ==['LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED']
                     and all(e['frame']==sample['frame'] and e.get('reasonId')==0 for e in terminal)
                     and terminal[0]['sequence']<terminal[1]['sequence']<terminal[2]['sequence']
                     and [(e.get('valueA'),e.get('valueB')) for e in terminal]==[(commit,2),(commit,2),(1,commit)]
                     and actor['commitSequence']==commit and actor['motionKind']=='NONE'
                     and actor['motionPhase']=='IDLE' and actor['reservationId']==0,
                     'Hop lacks one ordered normal commit/finish/input return')
                self.release=dict(frame=sample['frame'],events=deepcopy(terminal),commitSequence=commit)
        if self.release is not None:
            engine=actor['engineObject'];plan=self.hop['plan']
            need(actor['logical']==dict(zip(('x','y'),TARGET))
                 and (sample['player']['x'],sample['player']['y'])==TARGET
                 and actor['motionKind']=='NONE' and actor['motionPhase']=='IDLE' and actor['reservationId']==0
                 and actor['commitSequence']==self.release['commitSequence']
                 and engine.get('pos_x')==(TARGET[0]<<16)+32768 and engine.get('pos_z')==(TARGET[1]<<16)+32768
                 and engine.get('pos_y')==plan['targetBaseY'] and engine.get('face_y')==engine.get('unk88_y')==0,
                 'released pair did not stay at exact adjacent canopy/base')
        self.latest=deepcopy(sample);self.observed_frames+=1
        if self.action_index==1:self.neutral_frames+=1

    def stage(self,name):
        need(name in ('started','finished'),'unknown stage')
        return not self.failures and (self.hop is not None if name=='started' else self.release is not None and self.neutral_frames==64)

    def observe_record(self,row,on_sample=None):
        try:
            if 'initialSnapshot' in row:
                need(self.latest is None and row.get('phase')=='setup','initial boundary differs')
                self._boundary(row['initialSnapshot'],False);self.latest=deepcopy(row['initialSnapshot'])
            elif row.get('phase')=='setup':
                need(self.setup_index<len(SETUP) and row.get('action')==SETUP[self.setup_index][0],
                     'setup order differs')
                if SETUP[self.setup_index][1]=='step':
                    need('command' not in row and row.get('requestedInput',{}).get('keys')==[],
                         'field-settle setup is not normal neutral input')
                    for sample,events,_ in validate_raw_chunk(row,self.latest):
                        self._boundary(sample);self.latest=deepcopy(sample);self.setup_frames+=1
                    need(self.setup_frames<=24,'field settle exceeded24 frames')
                    if self.setup_frames<24:return self.result()
                else:
                    need(row.get('command')==SETUP[self.setup_index][1],'setup command differs')
                    self._boundary(row['snapshot'])
                    if row['action']=='mount-saved-mankey':
                        need(row.get('receipt',{}).get('lifecycle')=='prepared-native-follower-lifecycle',
                             'normal native mount lifecycle differs')
                    if row['command']=='bind':self.arm(row['snapshot'],row['receipt'])
                    self.latest=deepcopy(row['snapshot'])
                self.setup_index+=1
            else:
                need(self.setup_index==len(SETUP) and row.get('phase')=='observe'
                     and self.action_index<len(ORDER) and row.get('action')==ORDER[self.action_index]
                     and 'command' not in row,'observation order differs')
                for sample,events,_ in validate_raw_chunk(row,self.latest):
                    need(self.observed_frames<96,'observation exceeds its bound')
                    self._sample(sample,events,row.get('profileCache'))
                    if on_sample:on_sample(sample,self.observed_frames)
                if self.stage('started' if self.action_index==0 else 'finished'):self.action_index+=1
        except (ValueError,KeyError,TypeError,StopIteration,IndexError) as error:self.failures.append(str(error))
        return self.result()

    def result(self):
        ready=not self.failures and self.action_index==len(ORDER) and self.stage('finished') and self.observed_frames>=24
        return dict(kind=KIND,requirements=[REQUIREMENT],ready=ready,passed=ready,acceptedProof=False,
            observedFrames=self.observed_frames,observedFrameUnit='completed-game-frame',
            subject=deepcopy(self.subject),baseline=deepcopy(self.baseline),hop=deepcopy(self.hop),release=deepcopy(self.release),
            finalActor=deepcopy(self._actor(self.latest)) if ready else None,failures=list(self.failures))

    def finish(self):
        if not self.result()['ready'] and not self.failures:self.failures.append('mounted canopy Hop: no complete adjacent canopy Hop/input return')
        return self.result()
