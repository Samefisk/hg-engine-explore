"""Finite Throw flow with the unchanged saved follower on either side.

Uses the existing native bindings, held-control and shared Motion readers.
No prepared binding, profile, motion, or party value may replace the trigger.
"""
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import struct

from scripts.overworld_behavior_profile_viewer import _stable_condition_id
from tools.overworld.devtools_application_bank import canonical_bank, local_application
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_moving_cargo_pickup import pickup_motion, checked_moving_pickup
from tools.overworld.devtools_movement_predicates import check_movement_predicate
from tools.overworld.devtools_profile_feature_measurement import application_index
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor, engine_binding_identity
from tools.overworld.normal_play_observer import arc_height

ROUTE34 = 'party-throw-route34-v1'
FOLLOWER_CARGO = 'party-throw-follower-cargo-v1'
CASES = {
    ROUTE34: dict(test='follower.route34-throw', requirement='current.follower-route34-throw',
                  map=38, carrier='mankey', cargo='bellsprout',
                  subjects=(('mankey',56,'FOLLOWER','existing'),('bellsprout',69,'WILD','spawn'))),
    FOLLOWER_CARGO: dict(test='wild.throw-follower', requirement='current.wild-throw-follower',
                  map=101, carrier='geodude', cargo='mankey',
                  subjects=(('mankey',56,'FOLLOWER','existing'),('geodude',74,'WILD','spawn'))),
}


def need(value, reason):
    if not value: raise ValueError('party Throw: '+reason)


def source_inputs(root):
    from tools.overworld.devtools_test_inputs import cargo_query_image
    descriptor=json.loads((root/'build/player-health.debug.json').read_text())
    return dict(contractVersion=1,
        romSha256=hashlib.sha256((root/'test.nds').read_bytes()).hexdigest(),
        sourceSaveSha256=hashlib.sha256((root/'test.sav').read_bytes()).hexdigest(),
        profileSha256=hashlib.sha256((root/'data/overworld_behavior_profiles.json').read_bytes()).hexdigest(),
        overlaySha256=descriptor['overlay']['sha256'],queryImage=cargo_query_image())


def check_query_returns(events,subject,source):
    for event in events:
        data=event.get('data',{})
        if data.get('observation')!='throw-cargo-query' or data.get('subject')!=subject['handle']:continue
        image=data.get('imageIdentity',{})
        need(all(image.get(k)==source['queryImage'].get(k) for k in ('elfSha256','packageSha256')),
             'query return belongs to another code image')
        need(data.get('status')!='RESOURCE_LIMIT' and data.get('returnValue')!=4,
             'Cargo search exhausted memory in this fixture')


def recipe(feature):
    case=CASES[feature]
    def action(name,op,args,frames=120,seconds=90):
        return dict(id=name,op=op,args=args,budget=dict(maxSeconds=seconds,maxFrames=frames,noProgressFrames=frames))
    if feature==ROUTE34:
        setup=[action('saved-goldenrod-start','wait',dict(predicate=dict(kind='player-settled-at',map=76,x=358,z=366,when='final')),1),
            action('walk-goldenrod','step',dict(frames=32,keys=['DOWN']),32),
            action('release-goldenrod','step',dict(frames=64,keys=[]),64),
            action('enter-route34','step',dict(frames=120,keys=['DOWN'],until=dict(kind='player-field',path='y',operator='eq',value=385,when='final')),120),
            action('settle-route34','step',dict(frames=64,keys=[]),64),
            action('bind-mankey','bind',dict(subject='mankey'),1),
            action('spawn-bellsprout','spawn',dict(species=69,form=0,role='wild',level=5,x=358,z=387),360),
            action('bind-bellsprout','bind',dict(subject='bellsprout'),1)]
    else:
        setup=[action('throw-tile','teleport',dict(map=101,x=5,z=8,facing=1)),
            action('settle-field','step',dict(frames=24,keys=[]),24),
            action('saved-follower','wait',dict(predicate=dict(kind='follower-settled',species=56,partySlot=2,when='final')),64),
            action('bind-mankey','bind',dict(subject='mankey'),1),
            action('spawn-geodude','spawn',dict(species=74,form=0,role='wild',level=5,x=5,z=4),360),
            action('bind-geodude','bind',dict(subject='geodude'),1)]
    actions=[]
    if feature==FOLLOWER_CARGO:
        actions += [action('normal-follower-move','step',dict(frames=8,keys=['RIGHT']),8),
            action('walk-player-left','step',dict(frames=40,keys=['LEFT']),40),
            action('move-away-during-pursuit','step',dict(frames=32,keys=['RIGHT']),32)]
    # Native frame limits bound behavior. The Route34 readback measured394
    # launch-wait frames in90 seconds; allow the full600-frame window to run.
    actions += [action('natural-pickup-and-launch','step',dict(frames=600,keys=[],until=dict(kind='measurement-stage',measurement=feature,stage='launched',when='final')),600,seconds=300 if feature==FOLLOWER_CARGO else 180),
        action('walk-player-right','step',dict(frames=32,keys=['RIGHT']),32),
        action('follow-after-throw','step',dict(frames=300,keys=[],until=dict(kind='measurement-stage',measurement=feature,stage='resumed',when='final')),300)]
    return dict(schemaVersion=1,id=case['test'],title='Saved follower Throw flow on Route34' if feature==ROUTE34 else 'Wild Geodude throws the unchanged follower',
        mode='prepared',fixture=dict(rom='test.nds',save='test.sav'),expectationSource='TICKETS.md',requirements=[case['requirement']],
        budgets=dict(maxSeconds=600,maxFrames=1800,noProgressFrames=360,minObservedFrames=2),
        subjects=[dict(id=n,species=s,role=r,acquire=a) for n,s,r,a in case['subjects']],
        measurements=[dict(kind=feature,subjects=[s[0] for s in case['subjects']])],setup=setup,actions=actions,
        assertions=[dict(kind='measurement-complete',measurement=feature,when='final')])


def validate_recipe(test,feature):
    expected=recipe(feature)
    need(all(test.get(key)==value for key,value in expected.items() if key!='title'),
         'recipe changed the saved follower, ordinary trigger, or finite bounds')


class PartyThrowFlowMeasurement:
    def __init__(self,source,feature):
        need(feature in CASES and source.get('contractVersion')==1,'unknown case/source')
        self.source,self.kind,self.case=source,feature,CASES[feature]
        self.latest=None;self.subjects={};self.failures=[];self.frames={};self.flight=None
        self.observed_frames=0;self.setup_index=self.action_index=0
        self.claim_frames=0;self.free_progress=False;self.resumed=False;self.closed=False
        self.party_identity=None;self.final=None
        self.bank=canonical_bank(Path(__file__).resolve().parents[2])
        self.throw_application=application_index('apply-throw')
        self.profiles={}
        self.test=recipe(feature)
        self.action_frames=0
        self.setup_frames=0;self.trace_stream=self.trace_sequence=None
        self.follow_motion=None;self.query_returns=0
        self.setup_waits=[]
        self.pickup_profile_edge=None

    def _setup_predicate(self,predicate):
        # The runner emits no record for an already-true wait/until. Only
        # the retained current native boundary may establish that truth.
        sample=self.latest
        if sample is None or sample.get('fieldAvailable') is False:return False
        n=sample.get('nativeObservation',{})
        need(sample.get('fieldAvailable') is True
            and sample.get('observationBoundary')=='main-task-queue-completion'
            and sample.get('romSha256')==self.source['romSha256']
            and sample.get('sourceSaveSha256')==self.source['sourceSaveSha256']
            and n.get('coverageComplete') is True and n.get('installedBeforeBoot') is True
            and n.get('error') is None and all(n.get(k)==0 for k in
                ('eventsDropped','profilesEvicted','pendingUnframedEvents')),
            'setup guard lacks its current native boundary')
        if predicate['kind']=='player-field':
            # This exact recipe's route-entry stop is a logical y value.
            need(predicate==dict(kind='player-field',path='y',operator='eq',value=385,when='final'),
                 'unknown setup input stop')
            return sample.get('player',{}).get('y')==385
        return check_movement_predicate(predicate,sample)

    def _advance_setup_guards(self):
        while self.setup_index<len(self.test['setup']):
            expected=self.test['setup'][self.setup_index]
            predicate=expected['args'].get('predicate' if expected['op']=='wait' else 'until')
            if predicate is None or not self._setup_predicate(predicate):break
            self.setup_waits.append(dict(action=expected['id'],frame=self.latest['frame'],
                observedFrames=self.setup_frames,predicate=deepcopy(predicate)))
            self.setup_index+=1;self.setup_frames=0

    def _boundary(self,sample):
        n=sample.get('nativeObservation',{})
        need(sample.get('fieldAvailable') is True
            and sample.get('observationBoundary')=='main-task-queue-completion'
            and sample.get('romSha256')==self.source['romSha256']
            and sample.get('sourceSaveSha256')==self.source['sourceSaveSha256']
            and sample.get('context',{}).get('mapId')==self.case['map']
            and sample.get('fieldControl',{}).get('taskPointer')==0
            and n.get('coverageComplete') is True and n.get('installedBeforeBoot') is True
            and n.get('error') is None and all(n.get(k)==0 for k in
                ('eventsDropped','profilesEvicted','pendingUnframedEvents')),
            'missing current native field/coverage')

    def _actor(self,sample,name):
        selected=select_current_actor(sample,self.subjects[name])
        need(engine_binding_identity(selected['engineIdentity'])
            ==engine_binding_identity(self.subjects[name]['engineIdentity']),'changed current engine binding')
        return next(a for a in sample['actors'] if a['handle']==selected['handle'])

    def _party(self,sample):
        actor=self._actor(sample,'mankey')
        party=[p for p in sample.get('party',[]) if p.get('slot')==2]
        need(len(party)==1 and party[0].get('identityVerified') is True
            and party[0].get('species')==56 and party[0].get('hp',0)>0
            and actor['role']=='FOLLOWER' and actor['handle']['slot']==7
            and actor['subjectIdentity']==party[0]['personality'],
            'lost the unchanged living party2 follower')
        identity=(party[0]['personality'],party[0]['level'],party[0].get('form',0))
        if self.party_identity is None:self.party_identity=identity
        need(identity==self.party_identity,'changed saved party identity')

    def _carrier(self,sample,actor):
        c=sample['pokemonCombat'];v=c.get('interactions',{})
        need(c.get('available') is True and c.get('frame')==sample['frame']
            and c.get('nativeCycle')==sample['nativeCycle']
            and c.get('identity',{}).get('romSha256')==self.source['romSha256']
            and c['identity'].get('overlaySha256')==self.source['overlaySha256']
            and v.get('available') is True and v.get('schemaVersion')==1
            and v.get('frame')==sample['frame'] and v.get('nativeCycle')==sample['nativeCycle']
            and v.get('fieldSystem')==sample['fieldControl']['fieldPointer'],
            'missing authenticated native Throw owner')
        rows=[r for r in v['carriers'] if r.get('handle')==actor['handle']]
        need(len(rows)==1 and rows[0].get('available') is True
            and rows[0].get('role')==actor['role'],'wrong native carrier')
        row=rows[0];raw=bytes.fromhex(row['rawBindingsHex']);state=v['throwState']
        need(len(raw)==60 and raw[:12]==raw_handle(actor['handle']),'wrong binding owner')
        mask=bytes.fromhex(state['rawHex'])
        need(len(mask)==16 and list(mask[:10])==state['targets']
            and struct.unpack_from('<3H',mask,10)==tuple(state[k] for k in
                ('targetMask','carrierMask','recoveringMask')),'invalid raw held masks')
        encoded=mask[actor['handle']['slot']];slot=actor['handle']['slot']
        flags=dict(targetRaw=encoded,targetSlot=((encoded&63)-1 if encoded else None),
            carried=bool(encoded&128),windup=bool(encoded&64),
            targeted=bool(state['targetMask']&(1<<slot)),carrier=bool(state['carrierMask']&(1<<slot)),
            recovering=bool(state['recoveringMask']&(1<<slot)))
        need(row['throw']==flags,'decoded held control differs')
        for key,offset in (('trigger',12),('cargo',36)):
            b=row['bindings'][key];data=raw[offset:offset+24]
            need(data.hex()==b['rawHex'] and data[13]==0
                and data[12]==dict(NONE=0,PLAYER=1,ACTOR=2)[b['target']['kind']]
                and struct.unpack_from('<HIBBBB',data,14)==tuple(b[k] for k in
                    ('sourceConditionId','expiresAt','sourceApplicationLocal','lifetime','flags','reason'))
                and b['bound'] is bool(b['flags']),'raw binding differs')
            if b['target']['kind']=='ACTOR':
                need(data[:12]==raw_handle(b['target']['actor']),'raw binding target differs')
        return row,flags

    def _bound(self,row,carrier,cargo):
        app=self.throw_application;bank=self.bank
        for key,cid in (('trigger','condition-throw-notices-pokemon' if carrier['role']=='FOLLOWER'
                        else 'condition-throw-notices-player'),('cargo',
                        'condition-throw-picks-up-object-of-interest' if carrier['role']=='FOLLOWER'
                        else 'condition-throw-selects-cargo')):
            b=row['bindings'][key]
            expected=dict(kind='PLAYER',actor=None) if key=='trigger' and carrier['role']=='WILD' \
                else dict(kind='ACTOR',actor=cargo['handle'])
            need(b['bound'] is True and b['targetCurrent'] is True
                and b['sourceApplication']==app and b['sourceApplicationLocal']==local_application(bank,carrier['species'],app)
                and b['sourceConditionId']==_stable_condition_id('throw',cid)
                and b['flags']==1 and b['lifetime']==b['expiresAt']==b['reason']==0
                and b['target']==expected,'wrong authored current Trigger/Cargo binding')

    def _cache_profiles(self,row):
        events=row.get('events',[])+row.get('initialEvents',[])+row.get('receipt',{}).get('events',[])
        rows=list(row.get('profileCache',{}).get('resolvedProfiles',[]))
        for key in ('initialSnapshot','snapshot'):
            rows += row.get(key,{}).get('nativeObservation',{}).get('resolvedProfiles',[])
        rows += [e['data'] for e in events if e.get('kind')=='native-observation'
                 and e.get('data',{}).get('observation')=='behavior-resolved']
        for profile in rows:
            if profile.get('resolved') is not True:continue
            raw=bytes.fromhex(profile.get('resultHex',''))
            need(len(raw)==216 and profile.get('sourceSha256')==self.source['profileSha256']
                and struct.unpack_from('<II',raw,188)==(profile['appliedOverrides'],profile['fingerprint'])
                and profile.get('lanes')==[raw[:80].hex(),raw[80:160].hex()],
                'invalid native profile receipt')
            self.profiles[profile['fingerprint']]=deepcopy(profile)

    def _events(self,sample,events):
        for event in events:
            d=event.get('data',{})
            if event.get('kind')=='trace-status':
                need(d.get('unreadEventsLost',0)==0 and d.get('coverageComplete',True) is True
                    and d.get('code') not in ('unread-events-lost','sequence-reset','invalid-native-ring','trace-filter-changed'),
                    'semantic native sequence lost observations')
            if event.get('kind')!='native':continue
            need(type(d.get('sequence')) is int and type(d.get('traceStream')) is int
                and d.get('traceFieldEpoch')==sample['context']['fieldEpoch'], 'semantic native sequence owner is missing')
            if self.trace_stream is None:self.trace_stream=d['traceStream']
            need(d['traceStream']==self.trace_stream and (self.trace_sequence is None
                or d['sequence']==self.trace_sequence+1),'semantic native sequence has a gap/reset/duplicate')
            self.trace_sequence=d['sequence']

    def _bit(self,actor,name):
        return 1<<local_application(self.bank,actor['species'],application_index(name))

    def _own(self,events,actor):
        own=[e['data'] for e in events if e.get('kind')=='native'
            and e.get('data',{}).get('actorHandle')==actor['handle']['value']]
        need(all(e.get('actor')=={k:v for k,v in actor['handle'].items() if k!='value'} for e in own),
            'stale semantic actor')
        return own

    def _travel(self,sample,actor,motion,active,own,label):
        plan=active['plan'];elapsed=sample['frame']-active['frame']+active.get('firstElapsed',0)
        duration=plan['duration'];commit=active['commit']+1
        terminal=[e for e in own if e['event'] in ('LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED')]
        active['events']+=deepcopy(terminal)
        need(not any(e['event']=='MOTION_CANCELED' for e in own),label+' canceled accepted movement')
        returning=[e for e in own if e['event']=='CONTROL_RETURNED']
        if returning:
            # Tick can finish this lease and admit a new AUTO lease in the
            # same queue. Authenticate the old terminal before inspecting
            # the current plan, which can already belong to that successor.
            endpoint=[(v<<16)+32768 for v in plan['target']]
            need(elapsed==duration+plan['pauseFrames']
                and active['events']==sorted(active['events'],key=lambda e:e['sequence'])
                and [(e['event'],e['valueA'],e['valueB']) for e in active['events']]==[
                    ('LOGICAL_COMMIT',commit,plan['kind']),('MOTION_FINISHED',commit,plan['kind']),('CONTROL_RETURNED',0,commit)]
                and all(e.get('reasonId')==0 for e in active['events'])
                and actor['commitSequence']==commit and actor['inputOwnership']==0
                and [actor['logical'][k] for k in ('x','y')]==plan['target']
                and [actor['engineObject'][k] for k in ('pos_x','pos_z')]==endpoint
                and actor['engineObject']['pos_y']==plan['targetBaseY'] and actor['engineObject']['unk88_y']==0,
                'missing exact '+label+' terminal')
            if elapsed==duration:
                active['samples'].append(dict(frame=sample['frame'],elapsed=duration,
                    pose=endpoint+[plan['targetBaseY'],0]))
            need([p['elapsed'] for p in active['samples']]==list(range(active.get('firstElapsed',0),duration+1)),
                 'missing exact '+label+' terminal travel samples')
            if motion['plan']==plan:
                need(motion['elapsed']==duration and motion['phase']=='IDLE'
                    and actor['motionPhase']=='IDLE' and actor['motionKind']=='NONE'
                    and actor['reservationId']==0,'missing exact '+label+' idle return')
            else:
                selected=select_current_actor(self.latest,actor)
                before=next(a for a in self.latest['actors'] if a['handle']==selected['handle'])
                previous,_=pickup_motion(self.latest,before,self.source)
                following=motion['plan'];starts=[e for e in own if e['event']=='MOTION_STARTED']
                accepts=[e for e in own if e['event']=='PLAN_ACCEPTED']
                previous_elapsed=min(duration,elapsed-1)
                previous_landed=previous_elapsed==duration
                need(self.latest['frame']+1==sample['frame'] and previous['plan']==plan
                    and previous['elapsed']==previous_elapsed and before['commitSequence']==commit-int(not previous_landed)
                    and (not previous_landed or previous['phase']=='SETTLING'
                        and previous['settleRemaining']==1
                        and [before['engineObject'][k] for k in ('pos_x','pos_z')]==endpoint
                        and before['engineObject']['pos_y']==plan['targetBaseY'] and before['engineObject']['unk88_y']==0)
                    and motion['phase']==actor['motionPhase']=='MOVING'
                    and motion['elapsed']==actor['motionElapsed']==0
                    and following['version']==1 and following['kind'] in (1,2)
                    and actor['motionKind']=={1:'WALK',2:'HOP'}[following['kind']]
                    and following['fieldEpoch']==actor['handle']['fieldEpoch']
                    and following['behaviorFingerprint']==actor['behaviorFingerprint']&65535
                    and following['flags']==0 and following['visibilityPolicy']==0
                    and following['origin']==plan['target'] and following['startBaseY']==plan['targetBaseY']
                    and following['target']!=following['origin'] and 1<=following['duration']<=600
                    and actor['origin']==dict(zip(('x','y'),following['origin']))
                    and actor['target']==dict(zip(('x','y'),following['target']))
                    and actor['motionDuration']==following['duration']
                    and following['reservationId']==actor['reservationId']>0
                    and following['reservationId']!=plan['reservationId']
                    and len(starts)==len(accepts)==1
                    and [(e['valueA'],e['valueB'],e.get('reasonId')) for e in starts]==[(following['kind'],following['duration'],0)]
                    and [(e['valueA'],e['valueB'],e.get('reasonId')) for e in accepts]==[
                        (((following['target'][0]&65535)<<16)|(following['target'][1]&65535),following['duration'],0)]
                    and returning[0]['sequence']<accepts[0]['sequence']<starts[0]['sequence'],
                    'missing exact '+label+' autonomous successor after return')
                active['successor']=dict(frame=sample['frame'],handle=deepcopy(actor['handle']),
                    plan=deepcopy(following),pose=endpoint+[plan['targetBaseY'],0],
                    returnedSequence=returning[0]['sequence'],startedSequence=starts[0]['sequence'])
            return True
        if elapsed<=duration:
            need(motion['plan']==plan and motion['elapsed']==actor['motionElapsed']==elapsed
                and actor['motionDuration']==duration and actor['origin']==dict(zip(('x','y'),plan['origin']))
                and actor['target']==dict(zip(('x','y'),plan['target']))
                and actor['motionKind']=={1:'WALK',2:'HOP'}[plan['kind']]
                and actor['commitSequence']==active['commit']+int(elapsed==duration),
                label+' replaced or paused accepted movement')
            engine=actor['engineObject']
            xy=[(plan['origin'][i]<<16)+0x8000+int(Fraction((plan['target'][i]-plan['origin'][i])*65536*elapsed,duration)) for i in (0,1)]
            base=plan['startBaseY']+int(Fraction((plan['targetBaseY']-plan['startBaseY'])*elapsed,duration))
            height=arc_height(elapsed,duration)//16*plan['arcHeightQ4']
            if label=='projectile' and elapsed==0:
                height=active.get('launchHeightOffset',height)
            need([engine['pos_x'],engine['pos_z']]==xy and engine['pos_y']==base
                and engine['unk88_y']==height,
                'wrong actual '+label+' pose/arc')
            active['samples'].append(dict(frame=sample['frame'],elapsed=elapsed,pose=xy+[base,engine['unk88_y']]))
        else:
            need(motion['plan']==plan and motion['elapsed']==duration
                and [actor['engineObject'][k] for k in ('pos_x','pos_z')]==[(v<<16)+32768 for v in plan['target']]
                and actor['engineObject']['pos_y']==plan['targetBaseY'] and actor['engineObject']['unk88_y']==0,
                label+' changed its landed pause pose/plan')
        need(elapsed<duration+plan['pauseFrames'],label+' did not return control on time')
        return False

    def _sample(self,sample,events):
        self._boundary(sample);self._party(sample);self._events(sample,events)
        expected_keys=sum(dict(RIGHT=16,LEFT=32)[k] for k in self.test['actions'][self.action_index]['args']['keys'])
        keys=sample.get('selector',{})
        prior_keys=(self.latest or {}).get('selector',{}).get('rawHeld')
        need(keys.get('rawHeld')==keys.get('heldKeys') and keys.get('simulatedKeys')==0
            and (keys.get('rawHeld')==expected_keys or self.action_frames==0 and keys.get('rawHeld')==prior_keys),
            'native ordinary input differs')
        carrier=self._actor(sample,self.case['carrier']);cargo=self._actor(sample,self.case['cargo'])
        check_query_returns(events,carrier,self.source)
        self.query_returns+=sum(e.get('data',{}).get('observation')=='throw-cargo-query'
            and e['data'].get('subject')==carrier['handle'] for e in events)
        row,flags=self._carrier(sample,carrier);motion,timer=pickup_motion(sample,cargo,self.source)
        profile=self.profiles.get(carrier['behaviorFingerprint'])
        need(profile is not None and profile['appliedOverrides']==carrier['matchedLayerMask'], 'missing current carrier profile')
        own=self._own(events,cargo);frame=sample['frame'];state=sample['pokemonCombat']['interactions']['throwState']
        target_bit=1<<cargo['handle']['slot'];carrier_slot=carrier['handle']['slot']
        held_profile=any(carrier['matchedLayerMask']&self._bit(carrier,n)
            for n in ('apply-throw-find-position','apply-throw-release'))
        if self.pickup_profile_edge is not None and frame==self.pickup_profile_edge['frame']+1:
            need(held_profile,
                 'held Cargo did not resolve position/release on the next queue')
        need(self.latest is None or frame==self.latest['frame']+1,'missing completed frame')
        self.observed_frames+=1
        if self.flight is None and flags['targetRaw']:
            need(flags['targetSlot']==cargo['handle']['slot'] and flags['carrier']
                and state['targetMask']&target_bit,'claimed Cargo lacks its exact target mask')
            self._bound(row,carrier,cargo);self.frames.setdefault('claim',frame)
            if not flags['carried']:
                need(carrier['matchedLayerMask']&self._bit(carrier,'apply-throw'), 'free Cargo claim lacks Find Cargo profile')
                need(timer['movementActorControlMode']==0 and not any(e['event']=='MOTION_CANCELED' for e in own),
                    'selection took free Cargo control')
                self.claim_frames+=1
                if self.latest is not None:
                    before=self._actor(self.latest,self.case['cargo'])
                    bmotion,_=pickup_motion(self.latest,before,self.source)
                    if bmotion['phase']=='MOVING':
                        same_plan=motion['plan']==bmotion['plan']
                        need((same_plan and motion['elapsed']==bmotion['elapsed']+1
                                and motion['elapsed']<=motion['plan']['duration']
                                and (motion['phase']=='MOVING' or motion['elapsed']==motion['plan']['duration']
                                    and motion['phase'] in ('SETTLING','IDLE')))
                            or (not same_plan and bmotion['elapsed']+1==bmotion['plan']['duration']
                                and any(e['event']=='CONTROL_RETURNED' and e.get('reasonId')==0
                                    and e.get('valueB')==before['commitSequence']+1 for e in own)),
                            'selection stopped accepted motion')
                        if same_plan and motion['phase']=='MOVING':
                            need([cargo['engineObject'][k] for k in ('pos_x','pos_z')]
                                !=[before['engineObject'][k] for k in ('pos_x','pos_z')], 'selection froze Cargo pose')
                            self.free_progress=True
            else:
                need('claim' in self.frames and self.claim_frames>0 and timer['movementActorControlMode']==1,
                    'pickup lacks free claim then HELD')
                if not held_profile:
                    # Conditions resolve before AtomicPickup writes HELD in
                    # this same queue. Only that exact free->held boundary may
                    # retain FindCargo; the next queue must resolve held work.
                    need(self.latest is not None
                        and self.claim_frames>0 and not flags['windup']
                        and carrier['motionPhase']=='IDLE' and carrier['reservationId']==0
                        and carrier['inputOwnership']==0
                        and carrier['matchedLayerMask']&self._bit(carrier,'apply-throw'),
                        'held Cargo lacks authored position/release profile')
                    previous_carrier=self._actor(self.latest,self.case['carrier'])
                    previous_cargo=self._actor(self.latest,self.case['cargo'])
                    previous_row,previous_flags=self._carrier(self.latest,previous_carrier)
                    self._bound(previous_row,previous_carrier,previous_cargo)
                    _,previous_timer=pickup_motion(self.latest,previous_cargo,self.source)
                    carrier_events=self._own(events,carrier)
                    need(previous_flags['targetRaw']==cargo['handle']['slot']+1
                        and previous_flags['carrier'] and not previous_flags['carried']
                        and previous_timer['movementActorControlMode']==0
                        and previous_carrier['behaviorFingerprint']==carrier['behaviorFingerprint']
                        and any(e['event']=='CONDITIONAL_RESOLVED'
                            and e.get('frame')==e.get('actorFrame')==sample.get('actorFrame')
                            for e in carrier_events),
                        'pickup profile edge lacks its exact native free-to-HELD handoff')
                    self.pickup_profile_edge=dict(frame=frame,actorFrame=sample['actorFrame'],
                        carrier=deepcopy(carrier['handle']),cargo=deepcopy(cargo['handle']))
                if self.latest is not None:
                    before=self._actor(self.latest,self.case['cargo'])
                    bmotion,_=pickup_motion(self.latest,before,self.source)
                    if bmotion['phase']=='MOVING' and bmotion['elapsed']<bmotion['plan']['duration']:
                        previous_carrier=self._actor(self.latest,self.case['carrier'])
                        self.moving_pickup=checked_moving_pickup(self.latest,sample,events,self.source,before,cargo,previous_carrier,carrier)
                self.frames.setdefault('pickup',frame)
        if 'pickup' in self.frames and self.flight is None and flags['recovering'] and not flags['targetRaw'] \
                and motion['phase']=='MOVING' and motion['plan']['kind']==2:
            plan=motion['plan'];starts=[e for e in own if e['event']=='MOTION_STARTED']
            need(motion['elapsed']==cargo['motionElapsed']==0 and plan['version']==1 and plan['kind']==2
                and plan['flags']==0 and plan['fieldEpoch']==cargo['handle']['fieldEpoch']
                and plan['behaviorFingerprint']==cargo['behaviorFingerprint']&65535
                and plan['duration']==cargo['motionDuration'] and 1<=plan['duration']<=600
                and plan['origin']==[cargo['origin'][k] for k in ('x','y')]
                and plan['target']==[cargo['target'][k] for k in ('x','y')]
                and plan['origin']!=plan['target'] and plan['reservationId']==cargo['reservationId']>0
                and [(e['valueA'],e['valueB'],e.get('reasonId')) for e in starts]==[(2,plan['duration'],0)]
                and not flags['carrier'] and state['targetMask']&target_bit and timer['movementActorControlMode']==1,
                'missing actual native Throw launch with held target')
            self.flight=dict(plan=deepcopy(plan),frame=frame,commit=cargo['commitSequence'],samples=[],events=[])
            if cargo['engineObject']['unk88_y']!=0:
                # START admits elapsed0 without applying the first render.
                # That boundary can still show the exact preceding carried
                # lift. TickCustomJump replaces it with the native arc at1.
                previous_carrier=self._actor(self.latest,self.case['carrier'])
                previous_cargo=self._actor(self.latest,self.case['cargo'])
                previous_row,previous_flags=self._carrier(self.latest,previous_carrier)
                self._bound(previous_row,previous_carrier,previous_cargo)
                _,previous_timer=pickup_motion(self.latest,previous_cargo,self.source)
                old=previous_cargo['engineObject'];anchor=previous_carrier['engineObject']
                pose=('pos_x','pos_y','pos_z','unk88_y')
                need(previous_flags['targetSlot']==cargo['handle']['slot']
                    and previous_flags['carrier'] and previous_flags['carried'] and previous_flags['windup']
                    and previous_timer['movementActorControlMode']==1
                    and [old[k] for k in pose[:3]]==[anchor[k] for k in pose[:3]]
                    and old['unk88_y']==anchor['unk88_y']+0x8000
                    and [cargo['engineObject'][k] for k in pose]==[old[k] for k in pose],
                    'wrong actual projectile pose/arc at carried launch boundary')
                self.flight['launchHeightOffset']=old['unk88_y']
            self.frames['launch']=frame
        if self.flight is not None and 'landed' not in self.frames:
            f=self.flight;elapsed=frame-f['frame'];duration=f['plan']['duration'];mode=timer['movementActorControlMode']
            need(not flags['targetRaw'] and not flags['carrier'],'carrier retained Cargo after launch')
            if elapsed<duration:
                need(mode==1 and state['targetMask']&target_bit,'projectile released HELD before landing')
            else:
                need(mode in (0,1) and bool(state['targetMask']&target_bit)==bool(mode), 'landed target mask/control differs')
                if mode==0:self.frames.setdefault('released',frame)
            if self._travel(sample,cargo,motion,f,own,'projectile'):
                need(mode==0 and not state['targetMask']&target_bit,'landed follower remains HELD after return')
                self.frames['landed']=frame
        # A free carrier may follow while its Cargo is still in flight. A
        # thrown follower must first finish and release that same flight.
        if self.flight is not None:
            mankey=self._actor(sample,'mankey');mm,mt=pickup_motion(sample,mankey,self.source);me=self._own(events,mankey)
            starts=[e for e in me if e['event']=='MOTION_STARTED']
            eligible='landed' in self.frames if self.kind==FOLLOWER_CARGO else not flags['recovering']
            if self.follow_motion is None and eligible and mm['phase']=='MOVING' and starts:
                throw_mask=sum(self._bit(mankey,n) for n in ('apply-throw','apply-throw-find-position','apply-throw-release','apply-throw-away'))
                follower_profile=self.profiles.get(mankey['behaviorFingerprint'])
                need(follower_profile is not None and follower_profile['appliedOverrides']==mankey['matchedLayerMask']
                    and mt['movementActorControlMode']==0 and mankey['matchedLayerMask']&self._bit(mankey,'apply-follower')
                    and not mankey['matchedLayerMask']&throw_mask and mm['plan']['kind'] in (1,2)
                    and mm['plan']['flags']==0 and mm['plan']['fieldEpoch']==mankey['handle']['fieldEpoch']
                    and mm['plan']['behaviorFingerprint']==mankey['behaviorFingerprint']&65535
                    and mm['elapsed'] in (0,1) and mm['plan']['duration']>0
                    and mm['plan']['origin']!=mm['plan']['target']
                    and mm['plan']['reservationId']==mankey['reservationId']>0
                    and [(e['valueA'],e['valueB'],e.get('reasonId')) for e in starts]==[(mm['plan']['kind'],mm['plan']['duration'],0)],
                    'Mankey next move is not a free normal Follower admission')
                self.follow_motion=dict(plan=deepcopy(mm['plan']),frame=frame,firstElapsed=mm['elapsed'],commit=mankey['commitSequence'],startSequence=starts[0]['sequence'],samples=[],events=[])
                self.frames['follow-start']=frame
            if self.follow_motion is not None and not self.resumed:
                need(mt['movementActorControlMode']==0,'Mankey follow returned to HELD control')
                # Landing may return the projectile and admit normal Follow
                # in one queue. Its earlier terminal belongs only to the
                # projectile; the new lease starts at this exact admission.
                follow_events=[e for e in me if e['sequence']>=self.follow_motion['startSequence']]
                if self._travel(sample,mankey,mm,self.follow_motion,follow_events,'follow'):
                    self.resumed=True;self.frames['follow-return']=frame
        self.latest=self.final=deepcopy(sample)

    def observe_record(self,row,on_sample=None):
        try:
            self._cache_profiles(row)
            if 'initialSnapshot' in row:
                need(self.latest is None,'duplicate initial boundary');self.latest=deepcopy(row['initialSnapshot'])
                self._advance_setup_guards()
                return self.result()
            if row.get('phase')=='setup':
                need(self.setup_index<len(self.test['setup']),'extra setup action')
                expected=self.test['setup'][self.setup_index]
                need(row.get('action')==expected['id'],'setup action order differs')
                retry=row.get('command')=='spawn-refused' or expected['op']=='spawn' and bool(row.get('samples'))
                if retry:need(expected['op']=='spawn','unexpected setup retry')
                elif expected['op'] in ('step','wait'):
                    need(not row.get('command'),'step/wait replaced by a setup mutation')
                else:need(row.get('command')==expected['op'],'setup operation differs')
                if row.get('command')=='bind':
                    selected=select_current_actor(row['snapshot'],row['receipt'])
                    name=row['action'].removeprefix('bind-')
                    expected_subject=next(s for s in self.case['subjects'] if s[0]==name)
                    need((selected['species'],selected['role'])==expected_subject[1:3],'bound wrong species/role')
                    self.subjects[name]=deepcopy(row['receipt'])
                if row.get('samples'):
                    samples=list(validate_raw_chunk(row,self.latest))
                    self.setup_frames+=len(samples)
                    need(self.setup_frames<=expected['budget']['maxFrames'],'setup exceeded its finite frame bound')
                    need(row.get('requestedInput',{}).get('keys')==([] if retry else expected['args'].get('keys',[])),
                         'spawn retry used nonneutral input' if retry else 'setup input differs')
                self.latest=deepcopy(row.get('snapshot',(row.get('samples') or [self.latest])[-1]))
                if 'mankey' in self.subjects and self.latest.get('fieldAvailable'):self._party(self.latest)
                if self.case['carrier'] in self.subjects and self.latest.get('fieldAvailable'):
                    carrier=self._actor(self.latest,self.case['carrier'])
                    events=row.get('events',[])+row.get('receipt',{}).get('events',[])
                    check_query_returns(events,carrier,self.source)
                    self.query_returns+=sum(e.get('data',{}).get('observation')=='throw-cargo-query'
                        and e['data'].get('subject')==carrier['handle'] for e in events)
                if retry:return self.result()
                if expected['op']=='wait' or expected['op']=='step' and expected['args'].get('until'):
                    self._advance_setup_guards()
                    return self.result()
                if expected['op']=='step' and self.setup_frames<expected['args']['frames']:return self.result()
                self.setup_index+=1;self.setup_frames=0
                self._advance_setup_guards()
                return self.result()
            need(row.get('phase')=='observe' and self.setup_index==len(self.test['setup']) and len(self.subjects)==2
                 and self.action_index<len(self.test['actions']),
                 'flow lacks its declared setup')
            expected=self.test['actions'][self.action_index]
            need(row.get('action')==expected['id'] and row.get('requestedInput',{}).get('keys')==expected['args']['keys'],
                 'ordinary input/action differs')
            for sample,events,_ in validate_raw_chunk(row,self.latest):
                self._sample(sample,events)
                self.action_frames+=1
                need(self.action_frames<=expected['args']['frames'],'action exceeded its finite bound')
                if on_sample:on_sample(sample,self.observed_frames)
            stop=expected['args'].get('until',{}).get('stage')
            if self.stage(stop) if stop else self.action_frames==expected['args']['frames']:
                self.action_index+=1;self.action_frames=0
                # The runner emits no row for an already-proven stage wait.
                # Retain every finite input action, then consume only those
                # guards established by the native samples already checked.
                while self.action_index<len(self.test['actions']):
                    guard=self.test['actions'][self.action_index]['args'].get('until',{}).get('stage')
                    if not guard or not self.stage(guard):break
                    self.action_index+=1
        except (ValueError,KeyError,TypeError,StopIteration,struct.error) as error:self.failures.append(str(error))
        return self.result()

    def stage(self,name):
        need(name in ('launched','resumed'),'unknown flow stage')
        return not self.failures and ('launch' in self.frames if name=='launched' else self.resumed)

    def result(self):
        ready=not self.failures and self.action_index==len(self.test['actions']) and self.resumed and self.flight is not None and 'landed' in self.frames and 'released' in self.frames and self.query_returns>0
        if self.kind==FOLLOWER_CARGO:ready=ready and self.free_progress
        return dict(kind=self.kind,requirements=[self.case['requirement']],acceptedProof=False,
            passed=ready,ready=ready,closed=self.closed,observedFrames=self.observed_frames,
            failures=deepcopy(self.failures),subject=deepcopy(self.subjects.get(self.case['subjects'][0][0])),
            subjects=deepcopy(self.subjects),frames=deepcopy(self.frames),
            flight=deepcopy(self.flight),followMotion=deepcopy(self.follow_motion),queryReturns=self.query_returns,
            claimFrames=self.claim_frames,freeProgress=self.free_progress,
            partyIdentity=self.party_identity,setupWaits=deepcopy(self.setup_waits),pickupProfileEdge=deepcopy(self.pickup_profile_edge),final=deepcopy(self.final))

    def finish(self):
        if not self.result()['ready'] and not self.failures:self.failures.append('complete pickup, flight, landing and follower return missing')
        self.closed=True
        return self.result()
