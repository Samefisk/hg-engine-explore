"""One current held-Cargo search, with the measured pocket and normal Select exit.

No reader, guest clock, profile edit, reservation or motion is owned here.
Prepared placement earns no behavior credit. Completed queue bindings, resolver
bytes and native motion/events decide the held-search and release result.
"""
from copy import deepcopy
import struct
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.devtools_movement_predicates import player_settled_at
from tools.overworld.devtools_mount_control_stress import check_snapshot_pair
from tools.overworld.devtools_blocked_notice_hop_measurement import walk_leg
from tools.overworld.devtools_profile_feature_measurement import application_index
from scripts.overworld_behavior_profile_viewer import _stable_condition_id

KIND='held-throw-search-v1'
REQUIREMENT='current.held-throw-search'
SUBJECTS=(('geodude',74,'WILD','spawn'),('mareep',179,'WILD','spawn'),('stantler',234,'FOLLOWER','existing'))
BOUNDARY='main-task-queue-completion'
THROW_APP=application_index('apply-throw')
FIND_CARGO=1<<THROW_APP
POSITION=1<<application_index('apply-throw-find-position')
RELEASE=1<<application_index('apply-throw-release')
TRIGGER=_stable_condition_id('throw','condition-throw-notices-player')
CARGO=_stable_condition_id('throw','condition-throw-selects-cargo')
POCKET=((573,394),(573,395))
HELD_FRAMES=201
SETUP=(('prepare-stantler','party',dict(slot=0,species=234,level=50)),
 ('garden-tile','teleport',dict(map=67,x=572,z=394,facing=1)),
 ('create-passive-follower','spawn',dict(species=234,form=0,role='follower',slot=0,level=50)),
 ('bind-stantler','bind',dict(subject='stantler')),
 ('spawn-geodude','spawn',dict(species=74,form=0,role='wild',level=5,x=573,z=394)),
 ('bind-geodude','bind',dict(subject='geodude')),
 ('normal-pocket-exit','held-throw-pocket.prepare',{}),
 ('spawn-mareep','spawn',dict(species=179,form=0,role='wild',level=5,x=572,z=395)),
 ('bind-mareep','bind',dict(subject='mareep')))
ACTIONS=(('natural-pickup','step',dict(frames=300,keys=[],until=dict(kind='measurement-stage',measurement=KIND,stage='carried',when='final'))),
 ('hold-without-line','step',dict(frames=201,keys=[],until=dict(kind='measurement-stage',measurement=KIND,stage='held201',when='final'))),
 ('open-current-line','held-throw-line.prepare',{}),
 ('normal-windup-and-release','step',dict(frames=80,keys=[],until=dict(kind='measurement-stage',measurement=KIND,stage='launched',when='final'))))

def need(ok,message):
    if not ok:raise ValueError('held Throw: '+message)

def validate_recipe(test):
    need(test['id']=='wild.throw-held-search' and test['mode']=='prepared'
         and test['requirements']==[REQUIREMENT]
         and test['subjects']==[dict(id=n,species=s,role=r,acquire=a) for n,s,r,a in SUBJECTS]
         and tuple((a['id'],a['op'],a['args']) for a in test['setup'])==SETUP
         and tuple((a['id'],a['op'],a['args']) for a in test['actions'])==ACTIONS
         and test['assertions']==[dict(kind='measurement-complete',measurement=KIND,when='final')]
         and test['budgets']['maxFrames']==1000 and test['budgets']['minObservedFrames']==202,
         'exact pocket, 201 held frames or bounded normal input differs')

class HeldThrowSearchMeasurement:
    def __init__(self,source):
        need(set(source)=={'contractVersion','romSha256','overlaySha256','profileSha256'} and source['contractVersion']==1,'source identity differs')
        self.source=source;self.latest=None;self.subjects={};self.failures=[]
        self.observed_frames=0;self.profiles={};self.events=[];self.prep_samples=[]
        self.setup_index=0;self.carried_frame=None;self.position_profile=None;self.escape=None;self.hop=None;self.windup_timer=None
        self.data=dict(carrier=None,cargo=None,passive=None,context=None,held=[],lastHeld=None,pickupTransient=[],windup=None,launch=None,triggerCaptured=False)

    def _boundary(self,sample):
        need(sample.get('fieldAvailable') is True and sample.get('observationBoundary')==BOUNDARY
             and sample.get('romSha256')==self.source['romSha256'] and type(sample.get('frame')) is int
             and type(sample.get('nativeCycle')) is int and sample.get('fieldControl',{}).get('taskPointer')==0,
             'completed Field boundary or ROM differs')
        if self.data['context'] is not None:need(sample['context']==self.data['context'],'current Field context differs')
        combat=sample.get('pokemonCombat',{})
        if self.data['carrier'] is not None:
            need(combat.get('identity',{}).get('overlaySha256')==self.source['overlaySha256'],'combat owner package differs')

    def _profile_events(self,events):
        for event in events:
            if event.get('kind')=='trace-status':
                d=event.get('data',{})
                need(d.get('code') not in ('unread-events-lost','sequence-reset','invalid-native-ring','trace-filter-changed') and d.get('unreadEventsLost',0)==0,'semantic trace is incomplete')
            d=event.get('data',{})
            if event.get('kind')=='native-observation' and d.get('observation')=='behavior-resolved' and d.get('resolved') is True:
                raw=bytes.fromhex(d['resultHex'])
                need(len(raw)==216 and struct.unpack_from('<I',raw,192)[0]==d['fingerprint'],'native resolver bytes differ')
                self.profiles[d['fingerprint']]=deepcopy(d)
        self.events.extend(deepcopy(events))

    def _position_profile(self,sample,geo):
        profile=self.profiles.get(geo['behaviorFingerprint'])
        need(profile is not None and profile['appliedOverrides']==geo['matchedLayerMask'] and profile['appliedOverrides']&POSITION,'held position has no native resolved receipt')
        lane=bytes.fromhex(profile['resultHex'])[:80]
        need(lane[0]==3 and lane[13]==13 and lane[76]==8,'held resolved owner lacks CHASE/saved Trigger line/range8')
        if self.position_profile is None:self.position_profile=deepcopy(profile)

    def _escape_sample(self,sample):
        if self.escape is not None:return
        mounted=self.current_stantler(sample,'MOUNTED',required=False)
        if mounted is None:return
        if mounted['motionKind']=='HOP' and mounted['motionPhase'] in ('MOVING','COMMIT_PENDING'):
            need(mounted['origin']==dict(x=568,y=394) and mounted['target']==dict(x=566,y=394),'normal Select exit admitted another Hop')
            profile=self.mounted_profile(sample,mounted)
            need(mounted['motionDuration']==2*bytes.fromhex(profile['lanes'][0])[7],'standing fence Hop duration differs from resolved Walk time')
            if self.hop is None:self.hop=dict(frame=sample['frame'],commit=mounted['commitSequence'],profile=profile,subject=deepcopy(mounted['handle']),duration=mounted['motionDuration'])
        if self.hop is not None and self.escape is None and mounted['motionPhase']=='IDLE' and mounted['reservationId']==0 and player_settled_at(sample,67,566,394):
            need(mounted['commitSequence']==self.hop['commit']+1,'fence Hop has no fresh native commit')
            identity={k:v for k,v in mounted['handle'].items() if k!='value'}
            lifecycle=[e for e in self.events if self.hop['frame']<=e.get('frame',0)<=sample['frame'] and e.get('kind')=='native' and e.get('data',{}).get('actorHandle')==mounted['handle']['value'] and e['data'].get('event') in ('MOTION_STARTED','LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED')]
            need([e['data']['event'] for e in lifecycle]==['MOTION_STARTED','LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED'] and all(e['data'].get('actor')==identity and e['data'].get('reason')=='OK' for e in lifecycle) and lifecycle[0]['data'].get('valueA')==2 and lifecycle[0]['data'].get('valueB')==self.hop['duration'],'fence Hop native full-owner lifecycle differs')
            self.escape=dict(profile=deepcopy(self.hop['profile']),landing=deepcopy(sample),lifecycle=deepcopy(lifecycle))

    def _sample(self,sample,events,action,phase):
        self._boundary(sample);self._profile_events(events)
        if phase=='setup':
            self.prep_samples.append(deepcopy(sample))
            if action=='normal-pocket-exit':self._escape_sample(sample)
            if self.data['carrier'] is not None:
                geo,row,_=self.interaction(sample)
                need(not row['throw']['carried'] and not row['throw']['windup'] and not row['throw']['recovering'],'pickup or release preceded the safe pocket setup')
                if self.data['triggerCaptured'] or row['bindings']['trigger']['bound']:
                    self.trigger(sample);self.data['triggerCaptured']=True
            return
        self.observed_frames+=1
        need(self.observed_frames<=300+201+64+80,'observed input exceeded bounded pickup/hold/line/release')
        if action=='natural-pickup':
            geo,row,_=self.trigger(sample)
            need(not row['throw']['windup'] and not row['throw']['recovering'],'release preceded held search')
            if row['throw']['carried']:
                if self.carried_frame is None:self.carried_frame=sample['frame']
                self.held_sample(sample)
        elif action=='hold-without-line':
            need(self.carried_frame is not None,'held observation preceded pickup')
            geo=self.actor(sample,self.data['carrier'])
            need(geo['matchedLayerMask']&POSITION,'held search lost its resolved Find Position profile')
            self.held_sample(sample)
        elif action in ('open-current-line','normal-windup-and-release'):
            need(len(self.data['held'])>=HELD_FRAMES,'line opened before 201 held frames')
            self.release_sample(sample,self.events)
            geo,row,_=self.interaction(sample)
            timers=[t for t in sample['pokemonCombat'].get('movementTimers',[]) if t.get('handle')==geo['handle']]
            need(len(timers)==1 and timers[0].get('sourceIdentity',{}).get('object')==geo['engineIdentity']['pointer'],'native windup timer owner differs')
            timer=timers[0]
            if row['throw']['windup']:
                profile=self.profiles.get(geo['behaviorFingerprint'])
                need(profile is not None and profile['appliedOverrides']==geo['matchedLayerMask'],'windup lacks current native release profile')
                lane=bytes.fromhex(profile['resultHex'])[:80]
                need(lane[77]==20 and lane[78]==60,'separately authored windup/recovery changed')
                if self.windup_timer is None:self.windup_timer=dict(actorFrame=sample['actorFrame'],start=timer['movementCooldown'],profile=deepcopy(profile))
                need(self.windup_timer['start']==20 and timer['movementCooldown']==max(0,20-(sample['actorFrame']-self.windup_timer['actorFrame'])),'native windup changed its authored countdown')
            if self.data['launch'] is not None:
                need(self.windup_timer is not None and sample['actorFrame']>self.windup_timer['actorFrame']+20 and timer['movementEmoteTimer']==60,'release preceded authored windup or omitted authored recovery')
        else:need(False,'undeclared observed input')
        if self.data['held'] and sample['frame']==self.data['held'][-1]['frame']:
            geo=self.actor(sample,self.data['carrier']);self._position_profile(sample,geo)

    def observe_record(self,row,on_sample=None):
        try:
            if 'initialSnapshot' in row:
                need(self.latest is None and row.get('phase')=='setup','initial boundary differs')
                self.latest=deepcopy(row['initialSnapshot']);self._boundary(self.latest);self._profile_events(row.get('initialEvents',[]));return self.result()
            need(self.latest is not None,'initial boundary missing')
            if row.get('command') is not None:
                phase=row.get('phase');action=row.get('action');command=row['command'];snap=row['snapshot']
                if phase=='setup':
                    need(self.setup_index<len(SETUP) and (action,command)==SETUP[self.setup_index][:2],'setup command order differs')
                    self._boundary(snap);self._profile_events(row.get('receipt',{}).get('events',[]))
                    if command=='bind':
                        name=SETUP[self.setup_index][2]['subject'];bound=deepcopy(row['receipt'])
                        select_current_actor(snap,bound);self.subjects[name]=bound
                        if name=='stantler':self.data['passive']=bound;need(player_settled_at(snap,67,572,394),'initial follower/player not settled')
                        if name=='geodude':self.data['carrier']=bound;self.data['context']=deepcopy(snap['context']);need(tuple(self.actor(snap,bound)['engineObject'][k] for k in ('x','y'))==(573,394),'actual Geodude finalized tile differs')
                        if name=='mareep':self.data['cargo']=bound;need(tuple(self.actor(snap,bound)['engineObject'][k] for k in ('x','y'))==(572,395),'actual Cargo finalized tile differs')
                    if command=='held-throw-pocket.prepare':
                        receipt=row['receipt'];need(receipt.get('normalInputOnly') is True and receipt.get('gardenEscape')==self.escape,'pocket preparation did not return its independently observed escape')
                        current=self.current_stantler(snap,'FOLLOWER')
                        need(player_settled_at(snap,67,566,396),'safe off-line endpoint differs')
                        geo,claim,_=self.interaction(snap)
                        need(not claim['throw']['carried'] and not claim['throw']['windup'] and not claim['throw']['recovering'],'Cargo preceded completed normal pocket setup')
                        # Normal Select changes control/presentation generations.
                        # Publish the same full handle/PID at its proved Follower
                        # return, before any Cargo or observed held-search frame.
                        self.data['passive']=select_current_actor(snap,current)
                        self.subjects['stantler']=deepcopy(self.data['passive'])
                    self.setup_index+=1
                else:
                    need(command=='held-throw-line.prepare' and action=='open-current-line','undeclared command after binding')
                    need(row['receipt'].get('normalInputOnly') is True,'line opening was not normal input')
                self.latest=deepcopy(snap);return self.result()
            need(self.setup_index>=6,'frame stream preceded bound carrier')
            for sample,events,_ in validate_raw_chunk(row,self.latest):
                self._sample(sample,events,row.get('action'),row.get('phase'))
                self.latest=deepcopy(sample)
                if on_sample is not None:on_sample(sample,self.observed_frames)
        except (ValueError,KeyError,TypeError,StopIteration,struct.error) as error:self.failures.append(str(error))
        return self.result()

    def stage(self,name,snapshot=None):
        return not self.failures and {'carried':self.carried_frame is not None,'held201':len(self.data['held'])>=HELD_FRAMES,'launched':self.data['launch'] is not None}.get(name,False)

    def result(self):
        ready=not self.failures and self.data['launch'] is not None and len(self.data['held'])>=201 and self.position_profile is not None and self.escape is not None
        return dict(kind=KIND,acceptedProof=False,passed=ready,ready=ready,requirements=[REQUIREMENT],failures=list(self.failures),subjects=deepcopy(self.subjects),observedFrames=self.observed_frames,observedFrameUnit='completed-game-frame',continuousHeldFrames=len(self.data['held']),heldStart=self.data['held'][0]['frame'] if self.data['held'] else None,heldEnd=self.data['held'][-1]['frame'] if self.data['held'] else None,windup=deepcopy(self.data['windup']),launch=deepcopy(self.data['launch']),positionProfile=deepcopy(self.position_profile),windupTimer=deepcopy(self.windup_timer),gardenEscape=deepcopy(self.escape))

    def finish(self):
        need_ready=self.result()['ready']
        if not need_ready and not self.failures:self.failures.append('held Throw: final201 held search and accepted release is incomplete')
        return self.result()

    def actor(self,sample, subject):
            current = select_current_actor(sample, subject)
            value = next(a for a in sample['actors'] if a['handle'] == current['handle'])
            need(value.get('active') is True and value.get('presentationAttached') is True
                 and value.get('role') == 'WILD', 'current actor owner is unavailable')
            return value

    def current_stantler(self,sample, role, *, required=True):
            # Role/control generations can change at normal mount/dismount. The
            # full Actor handle, Pokemon identity, and native source stay exact.
            selected=dict(self.data['passive'],role=role)
            for key in ('authorityGeneration','engineAnchorGeneration','presentationGeneration'):
                selected.pop(key,None)
            matches=[a for a in sample['actors'] if a['handle']==selected['handle'] and a.get('role')==role]
            if not matches and not required:return None
            need(len(matches)==1,'same Stantler full handle/role is unavailable')
            q=matches[0]
            if not required and (q.get('presentationAttached') is not True
                    or q.get('identityVerified') is not True
                    or q.get('inputOwnership')!=(1 if role=='MOUNTED' else 0)):
                return None
            select_current_actor(sample,selected)
            selector=sample['selector']
            need(sample['context']==self.data['context'] and q['species']==234 and q['level']==50 and q['form']==0
                 and q['subjectIdentity']==selected['subjectIdentity'] and q['presentationAttached'] is True
                 and selector['activeFollowerPartySlot']==0 and selector['followerReleaseState']==0
                 and selector['queue']['count']==0 and selector['queue']['request']==0
                 and selector['captureTargetMask']==0, 'Stantler identity/selector/Field ownership differs')
            if role=='MOUNTED':
                need(q['inputOwnership']==1 and q['engineIdentity']['anchorInCurrentManager'] is True
                     and q['engineIdentity']['anchorPointer']==sample['mountedPair']['playerPointer']
                     and q['engineIdentity']['pointer']==sample['mountedPair']['mountPointer'],
                     'mounted Stantler does not own the current native player anchor')
                check_snapshot_pair(sample,q)
            return q

    def mounted_profile(self,sample, mounted):
            rows=[p for p in self.profiles.values()
                  if p.get('resolved') is True and p.get('fingerprint')==mounted['behaviorFingerprint']]
            need(len(rows)==1,'current Mounted policy has no actual native resolved Owner receipt')
            p=rows[0];raw=bytes.fromhex(p['lanes'][0]);result=bytes.fromhex(p['resultHex'])
            need(len(raw)==80 and len(result)==216 and result[:80]==raw
                 and int.from_bytes(result[192:196],'little')==mounted['behaviorFingerprint']
                 and p['appliedOverrides']==mounted['matchedLayerMask']
                 and raw[12]==1 and raw[20]==raw[21]==2 and raw[56]==1 and 1<=raw[7]<=6
                 and struct.unpack_from('<H',raw,32)[0]&1,
                 'actual Mounted Owner lacks Walk/two-tile vertical obstacle Hop/clear Land permission')
            return deepcopy(p)

    def interaction(self,sample):
            geo = self.actor(sample, self.data['carrier'])
            combat = sample.get('pokemonCombat', {})
            data = combat.get('interactions', {})
            need(sample.get('observationBoundary') == BOUNDARY and sample.get('fieldAvailable') is True
                 and sample.get('romSha256') == self.source['romSha256'] and sample['context'] == self.data['context']
                 and sample['fieldControl'].get('taskPointer') == 0
                 and combat.get('available') is True and combat.get('frame') == sample['frame']
                 and combat.get('nativeCycle') == sample['nativeCycle']
                 and combat.get('identity',{}).get('romSha256') == self.source['romSha256']
             and combat.get('identity',{}).get('overlaySha256') == self.source['overlaySha256']
                 and data.get('available') is True and data.get('schemaVersion') == 1
                 and data.get('frame') == sample['frame'] and data.get('nativeCycle') == sample['nativeCycle']
                 and data.get('observationBoundary') == BOUNDARY
                 and data.get('fieldSystem') == sample['fieldControl']['fieldPointer']
                 and data.get('identity',{}).get('romSha256') == self.source['romSha256'],
                 'binding receipt or current Field clock differs')
            rows = [r for r in data['carriers'] if r.get('handle') == geo['handle']]
            need(len(rows) == 1 and rows[0].get('available') is True and rows[0].get('role') == 'WILD',
                 'full-current Geodude interaction is missing')
            row = rows[0]
            raw = bytes.fromhex(row['rawBindingsHex'])
            need(len(raw) == 60 and raw[:12] == raw_handle(geo['handle']), 'native binding owner differs')
            for name, offset in (('trigger',12),('cargo',36)):
                b = row['bindings'][name]; r = raw[offset:offset+24]
                need(r.hex() == b['rawHex'] and r[13] == 0
                     and r[12] == {'NONE':0,'PLAYER':1,'ACTOR':2}.get(b['target']['kind'])
                     and struct.unpack_from('<HIBBBB',r,14) == (b['sourceConditionId'],b['expiresAt'],
                         b['sourceApplication'],b['lifetime'],b['flags'],b['reason'])
                     and b['bound'] is bool(b['flags']), 'native binding bytes differ')
                if b['target']['kind'] == 'ACTOR':
                    need(r[:12] == raw_handle(b['target']['actor']), 'native Cargo handle differs')
                if b['bound']:
                    need(b['targetCurrent'] is True and b['lifetime'] == 0
                         and b['sourceApplication'] == THROW_APP and b['sourceConditionId'] == (TRIGGER if name=='trigger' else CARGO),
                         'binding identity or until-clear provenance differs')
            throw = data['throwState']; native = bytes.fromhex(throw['rawHex'])
            need(len(native) == 16 and list(native[:10]) == throw['targets']
                 and struct.unpack_from('<3H',native,10) == (throw['targetMask'],throw['carrierMask'],throw['recoveringMask']),
                 'native Throw masks differ')
            slot = geo['handle']['slot']; encoded = native[slot]
            expected = dict(targetRaw=encoded,targetSlot=(encoded&63)-1 if encoded else None,
                            carried=bool(encoded&128),windup=bool(encoded&64),
                            targeted=bool(throw['targetMask']&(1<<slot)),
                            carrier=bool(throw['carrierMask']&(1<<slot)),recovering=bool(throw['recoveringMask']&(1<<slot)))
            need(row['throw'] == expected, 'encoded claim differs')
            return geo, row, throw

    def trigger(self,sample):
            geo, row, throw = self.interaction(sample)
            b = row['bindings']['trigger']
            need(b['bound'] and b['targetCurrent'] and b['target'] == {'kind':'PLAYER','actor':None},
                 'saved current Player Trigger is missing')
            need(not row['throw']['recovering'], 'entered recovery before release')
            return geo, row, throw

    def held_sample(self,sample):
            geo,row,throw = self.trigger(sample); cargo = self.actor(sample,self.data['cargo'])
            b = row['bindings']['cargo']; flags=row['throw']; slot=geo['handle']['slot']; target=cargo['handle']['slot']
            need(b['bound'] and b['targetCurrent'] and b['target'] == dict(kind='ACTOR',actor=cargo['handle'])
                 and flags['targetRaw'] == (target+1)|128 and flags['carried'] and not flags['windup']
                 and not flags['recovering'] and flags['carrier'] and throw['targetMask']&(1<<target)
                 and throw['carrierMask']&(1<<slot), 'lost held Cargo/claim or entered windup/recovery')
            gx,gy=(geo['engineObject'][k] for k in ('x','y')); px,py=(sample['player'][k] for k in ('x','y'))
            need((gx,gy) in POCKET and (px,py)==(566,396)
                 and not ((gx==px or gy==py) and 0<abs(gx-px)+abs(gy-py)<=8),
                 'held search has a real line or left its current pocket')
            need(not geo['matchedLayerMask']&RELEASE,'held no-line search admitted release')
            if not geo['matchedLayerMask']&POSITION:
                need(not self.data['held'] and geo['matchedLayerMask']&FIND_CARGO,
                     'held search lost its resolved Find Position profile')
                self.data['pickupTransient'].append(dict(frame=sample['frame'],nativeCycle=sample['nativeCycle'],
                    carrier=deepcopy(geo['handle']),cargo=deepcopy(cargo['handle']),
                    player=[px,py],carrierTile=[gx,gy],targetRaw=flags['targetRaw'],
                    matchedLayerMask=geo['matchedLayerMask'],rawBindingsHex=row['rawBindingsHex'],throwRawHex=throw['rawHex']))
                return
            if self.data['lastHeld'] is not None:
                need(sample['frame']==self.data['lastHeld']+1, '201 held frames are not continuous')
            self.data['lastHeld']=sample['frame']
            self.data['held'].append(dict(frame=sample['frame'],nativeCycle=sample['nativeCycle'],
                 carrier=deepcopy(geo['handle']),cargo=deepcopy(cargo['handle']),
                 player=[px,py],carrierTile=[gx,gy],targetRaw=flags['targetRaw'],
                 matchedLayerMask=geo['matchedLayerMask'],rawBindingsHex=row['rawBindingsHex'],throwRawHex=throw['rawHex']))

    def release_sample(self,sample, events):
            geo,row,throw=self.interaction(sample); cargo=self.actor(sample,self.data['cargo']); flags=row['throw']
            if flags['targetRaw']:
                self.trigger(sample)
                need(row['bindings']['cargo']['bound'] and row['bindings']['cargo']['targetCurrent']
                     and row['bindings']['cargo']['target']==dict(kind='ACTOR',actor=cargo['handle']), 'Cargo changed before release')
            if flags['windup'] and self.data['windup'] is None:
                need(len(self.data['held'])>=201 and geo['matchedLayerMask']&RELEASE and flags['carried'],
                     'windup occurred without 201 valid held frames and release profile')
                aim=[sample['player'][k] for k in ('x','y')]; source=[geo['engineObject'][k] for k in ('x','y')]
                need((aim[0]==source[0] or aim[1]==source[1]) and 1<=sum(abs(a-b) for a,b in zip(aim,source))<=8,
                     'normal line-opening input did not make a cardinal in-range aim')
                self.data['windup']=dict(frame=sample['frame'],nativeCycle=sample['nativeCycle'],aim=aim,carrierTile=source,
                                     rawBindingsHex=row['rawBindingsHex'])
            if self.data['windup'] is not None and self.data['launch'] is None and flags['recovering'] and not flags['carried'] and flags['targetRaw']==0:
                hp=[h for h in sample['pokemonCombat']['targets'] if h['handle']==cargo['handle']]
                need(len(hp)==1, 'released Cargo lacks native motion state')
                motion=hp[0]['motion'];need(decode_motion(bytes.fromhex(motion['rawHex']))==motion, 'native motion bytes differ')
                starts=[e for e in events if e.get('frame')==sample['frame'] and e.get('kind')=='native'
                    and e.get('data',{}).get('event')=='MOTION_STARTED'
                    and e['data'].get('actorHandle')==cargo['handle']['value']
                    and e['data'].get('actor')=={k:v for k,v in cargo['handle'].items() if k!='value'}]
                need(cargo['motionKind']=='HOP' and cargo['motionPhase']=='MOVING' and motion['plan']['kind']==2
                     and motion['plan']['target']==self.data['windup']['aim'] and motion['plan']['duration']>1
                     and motion['phase']=='MOVING' and motion['plan']['reservationId']!=0
                     and len(starts)==1 and starts[0]['data'].get('valueA')==2
                     and starts[0]['data'].get('reason')=='OK'
                     and not row['bindings']['trigger']['bound'] and not row['bindings']['cargo']['bound']
                     and not flags['carrier'] and throw['targetMask']&(1<<cargo['handle']['slot']),
                     'release did not produce an accepted native Cargo Throw START')
                if self.data['launch'] is None:
                    self.data['launch']=dict(frame=sample['frame'],nativeCycle=sample['nativeCycle'],cargo=deepcopy(cargo['handle']),
                                         motion=motion,start=deepcopy(starts[0]))

def prepare_pocket(command,snapshot,meter):
    state=meter.data;state['snapshot']=deepcopy(snapshot)
    calls=[]
    def call(op,args=None):
        need(op in ('step','terrain'),'pocket helper only permits normal input and terrain read')
        args=args or {};calls.append(dict(op=op,args=deepcopy(args)))
        need(len(calls)<=256,'bounded pocket command count exceeded')
        result=command(op,args)
        sample=result.get('snapshot',result)
        if 'actors' in sample:state['snapshot']=deepcopy(sample)
        return sample if op=='step' and 'actors' in sample else result
    def step(keys):
        return call('step',dict(frames=1,keys=keys))
    def recorded_slice(before,last):
        samples=[s for s in meter.prep_samples if before<s['frame']<=last]
        need([s['frame'] for s in samples]==list(range(before+1,last+1)),'normal exit raw stream has a gap')
        return samples,meter.events
    trigger=meter.trigger;interaction=meter.interaction
    current_stantler=meter.current_stantler;mounted_profile=meter.mounted_profile
    followers=[current_stantler(snapshot,'FOLLOWER')]
    terrain=call('terrain',dict(radius=7,x=569,z=395))['terrain']
    need(terrain['observation']['context']==state['context'], 'terrain current owner differs')
    cells={(c['x'],c.get('z',c['y'])):c for c in terrain['cells']}
    points=[(x,394) for x in range(568,573)]+[(566,394),(566,395),(566,396)]+[(572,y) for y in (397,398,399)]+list(POCKET)
    for point in points:
        c=cells[point];s=c['surface']
        need(c.get('loaded') is True and c.get('collision') is False and s.get('known') is True,
             'normal approach/pocket terrain is not loaded clear at'+str(point))
        if point in POCKET:need(s.get('present') is False,'carrier pocket is not Land')
    follower_tile=tuple(followers[0]['engineObject'][k] for k in ('x','y'))
    need(follower_tile in {(572,y) for y in (397,398,399)}
         and cells[follower_tile]['surface']['present'] is False,
         'normal five-tile South release did not retain current Stantler on clear Land')
    for point in [(x,394) for x in range(568,573)]+[(572,395)]:
        s=cells[point]['surface'];need(s.get('present') and s.get('typeId')==3 and s.get('heightMode')=='native-ground',
                                     'west pocket exit is not authored FlowerBed')
    for point in ((567,394),(573,393),(574,394),(574,395),(573,396)):
        need(cells[point].get('loaded') is True and cells[point].get('collision') is True,
             'outer pocket exit is not a current blocked tile')
    for _ in range(120):
        _,row,_=interaction(state['snapshot'])
        if row['bindings']['trigger']['bound']:
            trigger(state['snapshot']);state['triggerCaptured']=True;break
        step([])
    else:need(False,'native Player Vision did not capture Trigger within120 frames')
    # Foot input crosses only the clear Flowers. Sprint's destination
    # permissions are used only for its two-tile Hop onto clear Land.
    for x in range(571,567,-1):walk_leg(step,67,'LEFT',[x,394])
    trigger(state['snapshot'])
    step(['SELECT'])
    for _ in range(64):
        mounted=current_stantler(state['snapshot'],'MOUNTED',required=False)
        if mounted is not None and mounted['motionPhase']=='IDLE' and mounted['reservationId']==0:
            break
        step([])
    else:need(False,'normal Select did not produce a current idle mounted Stantler')
    # Release Select even if its public endpoint already shows MOUNTED.
    step([])
    mounted=current_stantler(state['snapshot'],'MOUNTED')
    need(mounted['motionPhase']=='IDLE' and mounted['reservationId']==0
         and mounted['movementPolicy']['pending']==0 and mounted['movementPolicy']['speed']==0
         and player_settled_at(state['snapshot'],67,568,394),
         'mounted fence source is not current and settled')
    profile=mounted_profile(state['snapshot'],mounted)
    mount_source=deepcopy(state['snapshot'])
    hop_before=state['snapshot']['frame']
    for _ in range(16):
        step(['LEFT']); mounted=current_stantler(state['snapshot'],'MOUNTED')
        if mounted['motionKind']=='HOP' and mounted['motionPhase'] in ('MOVING','COMMIT_PENDING'):
            need(mounted['origin']==dict(x=568,y=394) and mounted['target']==dict(x=566,y=394),
                 'normal Left did not admit the exact two-tile fence Hop')
            hop_started=deepcopy(mounted)
            need(hop_started['motionDuration']==2*bytes.fromhex(profile['lanes'][0])[7],
                 'standing two-tile chain Hop did not take twice the current Mounted Walk time')
            break
        need(mounted['motionPhase']=='IDLE' and player_settled_at(state['snapshot'],67,568,394),
             'mount entered a different movement before the fence Hop')
    else:need(False,'normal Left did not start an opted-in fence Hop')
    for _ in range(32):
        step([]); mounted=current_stantler(state['snapshot'],'MOUNTED')
        if mounted['motionPhase']=='IDLE' and mounted['reservationId']==0:
            break
    else:need(False,'accepted fence Hop did not finish within32 release frames')
    need(player_settled_at(state['snapshot'],67,566,394)
         and mounted['logical']==dict(x=566,y=394), 'fence Hop did not land at the clear outside tile')
    samples,events=recorded_slice(hop_before,state['snapshot']['frame'])
    for sample in samples:
        trigger(sample); current_stantler(sample,'MOUNTED')
    lifecycle=[e for e in events if hop_before<e.get('frame',0)<=state['snapshot']['frame']
        and e.get('kind')=='native' and e.get('data',{}).get('actorHandle')==mounted['handle']['value']
        and e['data'].get('event') in ('MOTION_STARTED','LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED')]
    for event in lifecycle:
        need(event['data'].get('actor')=={k:v for k,v in mounted['handle'].items() if k!='value'}
             and event['data'].get('reason')=='OK', 'fence Hop native lifecycle owner/reason differs')
    need([e['data']['event'] for e in lifecycle]==[
            'MOTION_STARTED','LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED']
         and lifecycle[0]['data'].get('valueA')==2
         and lifecycle[0]['data'].get('valueB')==hop_started['motionDuration'],
         'fence Hop lacks its exact native START/COMMIT/FINISH/control lifecycle')
    state['escape']=dict(profile=profile,source=mount_source,
        landing=deepcopy(state['snapshot']),lifecycle=deepcopy(lifecycle))
    step(['SELECT'])
    for _ in range(64):
        follower=current_stantler(state['snapshot'],'FOLLOWER',required=False)
        if follower is not None and follower['inputOwnership']==0 and player_settled_at(state['snapshot'],67,566,394):
            break
        step([])
    else:need(False,'normal Select did not return current foot control')
    step([]); trigger(state['snapshot']);current_stantler(state['snapshot'],'FOLLOWER')
    for y in (395,396):walk_leg(step,67,'DOWN',[566,y])
    geo,_,_=trigger(state['snapshot'])
    # The public native spawn needs the separate Follower owner idle.
    # Geo keeps its ordinary accepted Walk throughout this wait.
    for _ in range(64):
        follower=current_stantler(state['snapshot'],'FOLLOWER')
        if follower['motionPhase']=='IDLE' and follower['reservationId']==0:
            break
        step([])
    else:need(False,'normal passive Follower did not settle for native Cargo creation')
    # Both Land cells can belong to one accepted zero-pause Walk. Keep
    # that motion and put Cargo on clear ground beside the pocket.
    geo,_,_=trigger(state['snapshot'])
    source=tuple(geo['engineObject'][k] for k in ('x','y'));need(source in POCKET,'carrier left the source-backed Land pocket')
    need(meter.escape is not None,'normal fence Hop was not independently completed')
    return dict(snapshot=deepcopy(state['snapshot']),normalInputOnly=True,
                terrain=terrain,gardenEscape=deepcopy(meter.escape),commands=calls)


def prepare_line(command,snapshot,meter):
    need(len(meter.data['held'])>=201,'line opening preceded 201 held frames')
    calls=[]
    def step(keys):
        calls.append(dict(frames=1,keys=keys));need(len(calls)<=64,'normal line input exceeded64 frames')
        result=command('step',dict(frames=1,keys=keys))
        return result.get('snapshot',result)
    for y in (395,394):
        walk_leg(step,67,'UP',[566,y])
        if meter.data['windup'] is not None:break
    return dict(snapshot=deepcopy(meter.latest),normalInputOnly=True,commands=calls)
