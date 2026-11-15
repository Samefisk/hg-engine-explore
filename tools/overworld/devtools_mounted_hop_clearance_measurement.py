"""T80: normal mounted Hop must respect the Route30 crossed tree heights.

Current full Actor, resolver bytes, native Motion, native paired poses and queue
clock are shared readers. The fixture accepts any legal RIGHT Hop1..6; it never
requires the old six-tile endpoint or infers support from the actor's own Y.
"""
from copy import deepcopy
from fractions import Fraction
from tools.overworld.normal_play_observer import arc_height
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_mounted_canopy_hop_measurement import MountedCanopyHopMeasurement

KIND='mounted-hop-vertical-clearance-v1'
TEST='mount.hop-vertical-clearance'
REQUIREMENT='current.mounted-hop-vertical-clearance'
ORIGIN=(558,375)
OFFSET=0x31580
GROUND=0x10000
TOP=0x41580
CANOPY=((562,375),(563,375))
# Fixed before the run from the independently checked Route30 tree footprint
# and actual native ground base. The current loaded cells must match that map.
HEIGHTS={(x,375):(TOP if (x,375) in CANOPY else GROUND) for x in range(558,565)}
SETUP=(('route30-tree-path','teleport',dict(map=34,x=558,z=375,facing=3)),
       ('settle-field','step',dict(frames=24,keys=[])),
       ('mount-saved-mankey','spawn',dict(species=56,form=0,role='mounted',slot=2,level=3)),
       ('bind-mankey','bind',dict(subject='mankey')))
ORDER=('right-to-first-legal-hop','release-through-hop-terminal')


def need(value,reason):
    if not value:raise ValueError('mounted Hop clearance: '+reason)


def validate_recipe(test):
    stage=dict(kind='measurement-stage',measurement=KIND,stage='started',when='final')
    need(test['id']==TEST and test['mode']=='prepared'
        and test['fixture']==dict(rom='test.nds',save='test.sav')
        and test['requirements']==[REQUIREMENT]
        and test['subjects']==[dict(id='mankey',species=56,role='MOUNTED',acquire='existing')]
        and test['measurements']==[dict(kind=KIND,subject='mankey')]
        and tuple((a['id'],a['op'],a['args']) for a in test['setup'])==SETUP
        and tuple((a['id'],a['op'],a['args']) for a in test['actions'])==(
            (ORDER[0],'step',dict(frames=32,keys=['RIGHT'],until=stage)),
            (ORDER[1],'step',dict(frames=96,keys=[])))
        and test['assertions']==[dict(kind='measurement-complete',measurement=KIND,when='final')]
        and test['budgets']==dict(maxSeconds=180,maxFrames=520,noProgressFrames=180,minObservedFrames=24),
        'recipe differs from normal RIGHT/release across the fixed native canopy')


def legal_plan(plan,jump_enabled=False):
    """Independent physical oracle: declared support, tile footprint, arc poses.

    Entry/exit are the two world-X edges of each strictly crossed tile. Check
    the outer completed frames too, so a narrow tree cannot fall between the
    recorded centres. This is a fixed fixture oracle, not a planner/retry loop.
    """
    d=plan.get('distance');duration=plan.get('duration');target=plan.get('target')
    need(type(d) is int and 1<=d<=6 and plan.get('origin')==list(ORIGIN)
        and target==[ORIGIN[0]+d,ORIGIN[1]] and plan.get('direction')==plan.get('facing')==3,
        'plan is not a normal RIGHT Hop1..6')
    target_height=HEIGHTS[tuple(target)]
    need(plan.get('startBaseY')==GROUND and plan.get('targetBaseY')==target_height,
        'accepted endpoint has the wrong independently declared native support height')
    need(type(duration) is int and 1<=duration<=120 and type(plan.get('arcHeightQ4')) is int
        and 16<=plan['arcHeightQ4']<=255,'invalid Hop duration/arc')
    # Existing visible Hop7 / elevation30:150 contract supplies the ordinary
    # trajectory. Jump off permits no extra obstacle-driven arc increase.
    elevation=abs(target_height-GROUND)>>12
    ordinary_duration=7+(d-1)*6+(elevation*7*30)//1600
    ordinary_arc=min(255,16+(elevation*150)//200)
    need(duration==ordinary_duration,'normal Hop7/elevation30 time differs')
    if not jump_enabled:
        need(plan['arcHeightQ4']==ordinary_arc,'Jump-off profile raised the obstacle arc')
    checks=[]
    for tile in CANOPY:
        if not ORIGIN[0]<tile[0]<target[0]:continue
        # Cell bounds relative to the takeoff centre, in half-tile units.
        entry=Fraction(2*(tile[0]-ORIGIN[0])-1,2*d)
        exit=Fraction(2*(tile[0]-ORIGIN[0])+1,2*d)
        start=max(1,(duration*entry.numerator)//entry.denominator)
        end=min(duration-1,-(-(duration*exit.numerator)//exit.denominator))
        for elapsed in range(start,end+1):
            base=GROUND+int(Fraction((target_height-GROUND)*elapsed,duration))
            foot=base+arc_height(elapsed,duration)//16*plan['arcHeightQ4']
            need(TOP<=base or foot>=TOP+4096,
                'accepted Hop underpasses the crossed native canopy or its clearance margin')
            checks.append(dict(tile=list(tile),elapsed=elapsed,top=TOP,foot=foot))
    return dict(target=list(target),targetBaseY=target_height,jumpEnabled=jump_enabled,checks=checks)


class MountedHopClearanceMeasurement:
    _boundary=MountedCanopyHopMeasurement._boundary
    _actor=MountedCanopyHopMeasurement._actor
    _native=MountedCanopyHopMeasurement._native
    _events=MountedCanopyHopMeasurement._events
    _terminal_wait=MountedCanopyHopMeasurement._terminal_wait

    def __init__(self,source):
        self.source=source
        self.latest=self.subject=self.baseline=self.hop=self.release=None
        self.setup_index=self.action_index=self.observed_frames=self.neutral_frames=self.setup_frames=0
        self.events=[];self.failures=[];self.trace_stream=self.trace_sequence=None

    def _profile(self,sample,actor,cache):
        # Keep the shared source/fingerprint/Owner-lane proof. The T80 fixture
        # additionally freezes the visible Jump switch in its actual OFF state.
        result=MountedCanopyHopMeasurement._profile(self,sample,actor,cache)
        lane=bytes.fromhex(result['resultHex'])[80:160]
        need(lane[36]==7 and lane[56]&1==0,'normal profile is not Hop7 with Jump off')
        return result

    def _terrain(self,sample):
        terrain=sample.get('terrain',{});stamp=terrain.get('observation',{})
        need(stamp.get('boundary')=='paused-native-cycle-end' and stamp.get('context')==sample['context']
            and stamp.get('lastCompletedGameFrame')==sample['frame'] and stamp.get('nativeCycle')==sample['nativeCycle'],
            'current native terrain stamp differs')
        cells={(c.get('x'),c.get('z')):c for c in terrain.get('cells',[])}
        for point in HEIGHTS:
            c=cells.get(point,{});p=c.get('provenance',{});s=c.get('surface',{})
            need(c.get('loaded') is True and p.get('mapHeaderId')==34
                and p.get('fieldPointer')==sample['fieldControl'].get('fieldPointer')
                and p.get('landDataIdentity')=='current-map-matrix' and p.get('rawWord')==c.get('attribute')
                and s.get('known') is True,'loaded Route30 path provenance differs')
            if point in CANOPY:
                need(c.get('behavior')==6 and c.get('collision') is True and s.get('present') is True
                    and s.get('type')=='canopy' and s.get('surfaceId')==0xFFFE
                    and s.get('heightMode')=='native-ground-offset' and s.get('heightOffsetFx32')==OFFSET,
                    'declared native canopy footprint/support differs')
            else:
                need(c.get('collision') is False and s.get('present') is False,
                    'declared ordinary ground support differs')
        return [deepcopy(cells[p]) for p in HEIGHTS]

    def arm(self,sample,subject):
        self._boundary(sample);self.subject=deepcopy(select_current_actor(sample,subject));actor=self._actor(sample)
        need(actor['motionKind']=='NONE' and actor['motionPhase']=='IDLE' and actor['reservationId']==0
            and actor['logical']==dict(zip(('x','y'),ORIGIN)) and (sample['player']['x'],sample['player']['y'])==ORIGIN
            and actor['engineObject']['pos_y']==GROUND
            and actor['engineObject']['face_y']==actor['engineObject']['unk88_y']==0,
            'baseline is not settled native ground-mounted Mankey at558375')
        party=[p for p in sample.get('party',[]) if p.get('slot')==2]
        need(len(party)==1 and party[0].get('identityVerified') is True and party[0].get('species')==56
            and party[0].get('personality')==actor['subjectIdentity'] and party[0].get('hp',0)>0
            and sample['selector']['activeFollowerPartySlot']==2,'unchanged saved party2 identity differs')
        self.baseline=dict(actor=deepcopy(actor),terrain=self._terrain(sample));self.latest=deepcopy(sample)

    def _sample(self,sample,events,cache):
        self._boundary(sample);need(sample['context']==self.latest['context'],'field context changed')
        actor=self._actor(sample);held=sample.get('selector',{})
        allowed=(0,16) if self.action_index==0 and self.observed_frames==0 else (16,) if self.action_index==0 else (0,16) if self.neutral_frames==0 else (0,)
        need(held.get('rawHeld')==held.get('heldKeys') and held.get('rawHeld') in allowed
            and held.get('simulatedKeys')==0,'normal RIGHT-only/released input differs')
        self._events(sample,events);motion=self._native(sample,actor)
        if self.hop is None and motion['plan']['kind']==2 and motion['phase'] in ('PLANNED','MOVING','COMMIT_PENDING'):
            need(actor['motionKind']=='HOP','native Hop/public motion kind differs')
        if self.hop is None and actor['motionKind']=='HOP':
            need(held.get('rawHeld')==16,'actual Hop did not consume RIGHT input')
            profile=self._profile(sample,actor,cache);plan=motion['plan']
            need(motion['elapsed']==actor['motionElapsed']==1 and plan['version']==1 and plan['kind']==2
                and plan['flags']==0 and plan['fieldEpoch']==actor['handle']['fieldEpoch']
                and plan['behaviorFingerprint']==actor['behaviorFingerprint']&65535,'normal shared Hop owner/start differs')
            safety=legal_plan(plan)
            starts=[e for e in self.events if e['frame']==sample['frame'] and e['event']=='MOTION_STARTED'
                and (e.get('valueA'),e.get('valueB'))==(2,plan['duration']) and e.get('reasonId')==0]
            need(len(starts)==1 and any(e['event']=='INTENT_CREATED' and e['frame']==sample['frame']
                and e['sequence']<starts[0]['sequence'] for e in self.events),'normal Hop intent/start receipt is missing')
            self.hop=dict(actor=deepcopy(actor['handle']),plan=deepcopy(plan),sourceProfile=profile,safety=safety,
                startFrame=sample['frame'],startSequence=starts[0]['sequence'],samples=[])
        if self.hop is None:
            need(actor['motionKind']=='NONE' and actor['logical']==dict(zip(('x','y'),ORIGIN)),
                'moved without the required native Hop')
        elif self.release is None:
            plan=self.hop['plan'];duration=plan['duration'];engine=actor['engineObject'];target=tuple(plan['target'])
            need(motion['plan']==plan,'native accepted plan changed')
            elapsed=motion['elapsed'];prior=self.hop['samples'][-1]['elapsed'] if self.hop['samples'] else 0
            if actor['motionKind']=='HOP' and elapsed==prior==duration:self._terminal_wait(sample,actor,motion)
            elif actor['motionKind']=='HOP':
                need(elapsed==actor['motionElapsed']==prior+1 and elapsed<=duration
                    and actor['reservationId']==plan['reservationId'] and actor['origin']==dict(zip(('x','y'),ORIGIN))
                    and actor['target']==dict(zip(('x','y'),target)),'native Hop travel coverage differs')
                def lerp(a,b):return a+int(Fraction((b-a)*elapsed,duration))
                need(engine['pos_x']==lerp((ORIGIN[0]<<16)+32768,(target[0]<<16)+32768)
                    and engine['pos_z']==(ORIGIN[1]<<16)+32768
                    and engine['pos_y']==lerp(plan['startBaseY'],plan['targetBaseY'])
                    and engine['face_y']==arc_height(elapsed,duration)//16*plan['arcHeightQ4'] and engine['unk88_y']==0,
                    'actual mounted pair did not apply its safe native arc/base')
                self.hop['samples'].append(dict(frame=sample['frame'],elapsed=elapsed,engine=deepcopy(engine)))
            else:
                terminal=[e for e in self.events if e['sequence']>self.hop['startSequence']
                    and e['event'] in ('LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED')]
                commit=self.baseline['actor']['commitSequence']+1
                need(prior==duration and [e['event'] for e in terminal]==['LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED']
                    and all(e['frame']==sample['frame'] and e.get('reasonId')==0 for e in terminal)
                    and [(e.get('valueA'),e.get('valueB')) for e in terminal]==[(commit,2),(commit,2),(1,commit)]
                    and actor['commitSequence']==commit and actor['motionKind']=='NONE'
                    and actor['motionPhase']=='IDLE' and actor['reservationId']==0,'ordered landed Hop commit/return is missing')
                self.release=dict(frame=sample['frame'],events=deepcopy(terminal),commitSequence=commit)
        if self.release is not None:
            plan=self.hop['plan'];target=tuple(plan['target']);engine=actor['engineObject']
            need(actor['logical']==dict(zip(('x','y'),target)) and (sample['player']['x'],sample['player']['y'])==target
                and actor['motionKind']=='NONE' and actor['motionPhase']=='IDLE' and actor['reservationId']==0
                and actor['commitSequence']==self.release['commitSequence']
                and engine['pos_x']==(target[0]<<16)+32768 and engine['pos_z']==(target[1]<<16)+32768
                and engine['pos_y']==HEIGHTS[target] and engine['face_y']==engine['unk88_y']==0,
                'released pair left its accepted support or kept a height offset')
        self.latest=deepcopy(sample);self.observed_frames+=1
        if self.action_index==1:self.neutral_frames+=1

    def stage(self,name):
        need(name in ('started','finished'),'unknown stage')
        return not self.failures and (self.hop is not None if name=='started' else self.release is not None and self.neutral_frames==96)

    # Keep the existing raw chunk clock/order/complete-data reader. Only the
    # explicit setup/order and final neutral bound differ for this fixture.
    def observe_record(self,row,on_sample=None):
        try:
            if 'initialSnapshot' in row:
                need(self.latest is None and row.get('phase')=='setup','initial boundary differs')
                self._boundary(row['initialSnapshot'],False);self.latest=deepcopy(row['initialSnapshot'])
            elif row.get('phase')=='setup':
                need(self.setup_index<len(SETUP) and row.get('action')==SETUP[self.setup_index][0],'setup order differs')
                if SETUP[self.setup_index][1]=='step':
                    need('command' not in row and row.get('requestedInput',{}).get('keys')==[],'setup settle input differs')
                    for sample,events,_ in validate_raw_chunk(row,self.latest):
                        self._boundary(sample);self.latest=deepcopy(sample);self.setup_frames+=1
                    need(self.setup_frames<=24,'setup settle exceeds24')
                    if self.setup_frames<24:return self.result()
                else:
                    need(row.get('command')==SETUP[self.setup_index][1],'setup command differs');self._boundary(row['snapshot'])
                    if row['action']=='mount-saved-mankey':need(row.get('receipt',{}).get('lifecycle')=='prepared-native-follower-lifecycle','native mount lifecycle differs')
                    if row['command']=='bind':self.arm(row['snapshot'],row['receipt'])
                    self.latest=deepcopy(row['snapshot'])
                self.setup_index+=1
            else:
                need(self.setup_index==len(SETUP) and row.get('phase')=='observe' and self.action_index<len(ORDER)
                    and row.get('action')==ORDER[self.action_index] and 'command' not in row,'observation order differs')
                for sample,events,_ in validate_raw_chunk(row,self.latest):
                    need(self.observed_frames<128,'observation exceeds128');self._sample(sample,events,row.get('profileCache'))
                    if on_sample:on_sample(sample,self.observed_frames)
                if self.stage('started' if self.action_index==0 else 'finished'):self.action_index+=1
        except (ValueError,KeyError,TypeError,StopIteration,IndexError) as error:self.failures.append(str(error))
        return self.result()

    def result(self):
        ready=not self.failures and self.action_index==len(ORDER) and self.stage('finished') and self.observed_frames>=24
        return dict(kind=KIND,requirements=[REQUIREMENT],ready=ready,passed=ready,acceptedProof=False,
            observedFrames=self.observed_frames,observedFrameUnit='completed-game-frame',subject=deepcopy(self.subject),
            baseline=deepcopy(self.baseline),hop=deepcopy(self.hop),release=deepcopy(self.release),
            finalActor=deepcopy(self._actor(self.latest)) if ready else None,failures=list(self.failures))

    def finish(self):
        if not self.result()['ready'] and not self.failures:self.failures.append('mounted Hop clearance: no safe complete Hop/input return')
        return self.result()
