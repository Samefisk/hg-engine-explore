"""Exact retained Wild Walk rows; native Local clear is never inferred from idle."""
from copy import deepcopy

from tools.overworld.devtools_records import select_current_actor, engine_binding_identity
from tools.overworld.devtools_wild_walk_measurement import IDENTITY, LIFECYCLE
from tools.overworld.devtools_wild_walk_observer import ENGINE, check_cleared_state
from tools.overworld.normal_play_observer import complete_travel

KIND='wild-walk-v1'
REQUIREMENT='legacy.wild-walk'
RULES=(('natural-input','natural-wild-walk-count','gte'),
    ('live-actor-identity','wild-rattata-identity-flags','eq'),
    ('logical-commit','wild-walk-target-commit-count','eq'),
    ('rendered-motion','wild-walk-render-sample-counts','eq'),
    ('frame-pacing','wild-walk-elapsed-schedules','eq'),
    ('engine-boundary','wild-walk-clear-count','eq'),
    ('control-release','wild-walk-idle-terminal-count','eq'))
CLAIMS=tuple(r[0] for r in RULES)
MEANINGS={'wild-walk-missing-start':'MOTION_STARTED','wild-walk-missing-commit':'LOGICAL_COMMIT',
    'wild-walk-missing-finish':'MOTION_FINISHED','wild-walk-missing-return':'CONTROL_RETURNED'}
FAULTS=('wild-walk-absent-subject','wild-walk-stale-subject','wild-walk-bad-render',
    'wild-walk-held-input','wild-walk-clear-active','wild-walk-clear-wrong-owner','wild-walk-missing-clear','wild-walk-missing-reader',*MEANINGS)


def contract():
    result={}
    for claim,name,operator in RULES:
        row=dict(name=name,operator=operator,type='integer',validator='meaningful-observation',minimum=1)
        if claim in ('rendered-motion','frame-pacing'):
            row.pop('minimum')
            row.update(type='object',validator='motion-sample-counts-v1' if claim=='rendered-motion' else 'motion-elapsed-schedules-v1',
                requiredKeys=['durations','sampleCounts' if claim=='rendered-motion' else 'sequences'])
        result[claim]=[row]
    return result


def need(value,reason):
    if not value:raise ValueError(reason)


def measurements(replay,record):
    meter=replay.get('measurements',{}).get(KIND,{})
    need(replay.get('passed') is True and replay.get('failures')==[] and meter.get('passed') is True
        and meter.get('ready') is True and meter.get('closed') is True
        and meter.get('acceptedProof') is False and meter.get('failures')==[], 'wild Walk lacks closed independent replay')
    need(record.get('sessionCleanup')==dict(sessionId=record.get('sessionId'),closed=True,errors=[]),
         'wild Walk private session did not close cleanly')
    initial,subject=meter['initial'],meter['subject']
    selected=select_current_actor(initial,subject)
    actor=next(a for a in initial['actors'] if a['handle']==selected['handle'])
    need(actor.get('identityVerified') is True and actor['species']==19 and actor['role']=='WILD'
        and actor.get('inputOwnership')==0 and 0<=actor['handle']['slot']<6,
        'wild Walk lacks current Rattata identity')
    terminal=meter['terminal']
    current=select_current_actor(terminal,subject)
    end=next(a for a in terminal['actors'] if a['handle']==current['handle'])
    need(terminal['context']==initial['context'] and all(end.get(k)==actor.get(k) for k in (*IDENTITY,'sourceIdentity'))
        and engine_binding_identity(end['engineIdentity'])==engine_binding_identity(actor['engineIdentity'])
        and end['motionPhase']=='IDLE' and end['motionKind']=='NONE' and end['reservationId']==0,
        'wild Walk terminal owner or idle state differs')
    cleanup=meter.get('cleanup',{})
    need(cleanup.get('closed') is True and type(cleanup.get('advancedFrames')) is int
        and cleanup['advancedFrames']==0 and cleanup.get('acceptedProof') is False
        and all(cleanup.get('snapshot',{}).get(k)==terminal.get(k) for k in
            ('frame','nativeCycle','actorFrame','context','actors','player'))
        # Commands attach the host's profile cache; completed queue samples do
        # not. This is not a native event or a change to the terminal endpoint.
        and {k:v for k,v in cleanup.get('snapshot',{}).get('nativeObservation',{}).items() if k!='resolvedProfiles'}
            == {k:v for k,v in terminal.get('nativeObservation',{}).items() if k!='resolvedProfiles'},
        'wild Walk cleanup changed the terminal boundary')
    reader=cleanup.get('wildWalk',{})
    noops=meter.get('idleNoopClears',[])
    need(isinstance(noops,list) and len(noops)<=64,'wild Walk idle clear bound differs')
    need(reader.get('armed') is True and reader.get('closed') is True and reader.get('failure') is None
        and reader.get('acceptedProof') is False and reader.get('guestMemoryWrites')==0
        and reader.get('subject')==subject and reader.get('counts')=={'clear':1+len(noops)}
        and reader.get('startFrame')==initial['frame'],'wild Walk reader cleanup differs')
    motion=meter['motion']
    need(meter.get('completeMotions')==1 and motion['kind']=='WALK' and motion['duration']==4
        and motion['handle']==actor['handle'] and motion['fingerprint']==actor['behaviorFingerprint']
        and complete_travel(motion) and motion['commitAfter']==(motion['commitBefore']+1)&0xFFFFFFFF,
        'wild Walk lacks one complete four-frame motion')
    delta=[b-a for a,b in zip(motion['origin'],motion['target'])]
    need(len(delta)==2 and max(map(abs,delta))==1,'wild Walk target is not adjacent')
    samples=motion['samples']
    positive=[s for s in samples if s['elapsed']>0]
    for sample in samples:
        elapsed=sample['elapsed']
        need(type(elapsed) is int and 0<=elapsed<=4 and sample['jumpOffset']==0
            and [sample['render'][0],sample['render'][2]]==[(motion['origin'][i]<<16)+0x8000+delta[i]*0x10000*elapsed//4 for i in (0,1)],
            'wild Walk rendered sample differs')
    # TravelEnd is a separately retained real sample, not a fabricated elapsed4.
    if not positive or positive[-1]['elapsed']!=4:
        finish=motion.get('travelEnd',{})
        need(finish.get('elapsed')==4 and finish.get('render')==[(v<<16)+0x8000 for v in motion['target']]
            and motion.get('travelEndRender')==motion.get('terminalRender'), 'wild Walk missing measured travel end')
        positive.append(finish)
    elapsed=[s['elapsed'] for s in positive]
    need(elapsed==[1,2,3,4] and len(positive)==4,'wild Walk elapsed schedule differs')
    positions=[[s['logical'][k] for k in ('x','y')] for s in meter['logicalSamples']]
    need(positions and positions[0]==motion['origin'] and positions[-1]==motion['target']
        and all(p in (motion['origin'],motion['target']) for p in positions)
        and sum(a!=b for a,b in zip(positions,positions[1:]))==1,'wild Walk logical transition differs')
    need(end['logical']==dict(zip(('x','y'),motion['target'])) and end['commitSequence']==motion['commitAfter'],
         'wild Walk terminal target differs')
    traces=meter['traces']; native={}
    expected=(('MOTION_STARTED','startFrame',1,4),('LOGICAL_COMMIT','commitFrame',motion['commitAfter'],1),
        ('MOTION_FINISHED','finishFrame',motion['commitAfter'],1),('CONTROL_RETURNED','finishFrame',0,motion['commitAfter']))
    for name,frame,a,b in expected:
        rows=[e for e in traces if e.get('data',{}).get('event')==name]
        need(len(rows)==1,'missing native '+name)
        event=rows[0];data=event['data'];native[name]=data
        need(event['kind']=='native' and event['frame']==motion[frame] and data.get('reason')=='OK'
            and data.get('actorHandle')==actor['handle']['value']
            and data.get('actor')=={k:v for k,v in actor['handle'].items() if k!='value'}
            and (data.get('valueA'),data.get('valueB'))==(a,b),'wild Walk lifecycle differs: '+name)
    sequence=[native[name]['sequence'] for name in LIFECYCLE]
    need(sequence==sorted(set(sequence)) and not any(e['data'].get('event')=='MOTION_CANCELED' for e in traces),
         'wild Walk lifecycle order or cancellation differs')
    noop_sequences=validate_idle_noop_clears(noops,subject,initial,motion,
        next(e for e in traces if e['data'].get('event')=='MOTION_STARTED'))
    clears=meter['clearReceipts'];need(len(clears)==1,'missing native wild Walk clear')
    event=clears[0];clear=event['data']
    need(all(sequence<clear['sequence'] for sequence in noop_sequences), 'wild Walk idle clear occurs after terminal clear')
    need(event['kind']=='native-observation' and clear.get('observation')=='wild-walk-clear'
        and clear.get('subject')==subject,'wild Walk clear receipt differs')
    before,after=clear['before'],clear['after']
    need(before['current']==after['current'],'wild Walk clear changed authority')
    owner=before['current'];public=owner['publicSubject']
    need(owner.get('subject')==subject and all(public.get(k)==actor.get(k) for k in IDENTITY)
        and owner['sourceIdentity']==actor['sourceIdentity']
        and owner['engineIdentity']=={k:actor['engineIdentity'].get(k) for k in ENGINE}
        and owner['objectPointer']==actor['engineIdentity']['pointer'] and owner['slot']==actor['handle']['slot']
        and all(owner['worldContext'].get(k)==initial['context'][k] for k in ('mapId','fieldEpoch','mapGeneration'))
        and owner['statePointer']==owner['worldContext']['statePointer']
        and all(type(owner.get(k)) is int and 0x02000000<=owner[k]<0x02400000 and owner[k]%4==0
            for k in ('statePointer','runtimePointer','objectPointer')), 'wild Walk clear binding differs')
    need(type(before.get('active')) is int and before['active']==1 and type(before.get('mode')) is int and before['mode']==1,
         'wild Walk clear lacks active Walk entry')
    need(all(type(after.get(k)) is int for k in ('active','mode','objectFlags')),'wild Walk clear state types differ')
    check_cleared_state(after)
    need(public['commitSequence']==motion['commitAfter'] and public['logical']==end['logical']
        and native['LOGICAL_COMMIT']['actorFrame']<=clear['entryActorFrame']<=clear['returnActorFrame']<=native['MOTION_FINISHED']['actorFrame'],
        'wild Walk clear outside committed terminal window')
    values=[sum(e['data'].get('event')=='MOTION_STARTED' for e in traces),
        int(actor.get('identityVerified') is True),
        sum(e['data'].get('event')=='LOGICAL_COMMIT' for e in traces),
        {'durations':[motion['duration']],'sampleCounts':[len(positive)]},
        {'durations':[motion['duration']],'sequences':[elapsed]},len(clears),
        int(end['motionPhase']=='IDLE' and end['motionKind']=='NONE' and end['reservationId']==0)]
    return [dict(claim=claim,name=name,value=value,operator=operator,expected=deepcopy(value),passed=True)
        for (claim,name,operator),value in zip(RULES,values)]


def validate_idle_noop_clears(noops,subject,initial,motion,start_trace):
    """Validate retained pre-motion calls; return their native receipt sequences."""
    bound=select_current_actor(initial,subject)
    actor=next(a for a in initial['actors'] if a['handle']==bound['handle'])
    need(isinstance(noops,list) and len(noops)<=64,'wild Walk idle clear bound differs')
    need(start_trace.get('kind')=='native' and start_trace['data'].get('event')=='MOTION_STARTED'
        and start_trace['data'].get('actorHandle')==actor['handle']['value']
        and start_trace['frame']==motion['startFrame'],'wild Walk idle clear lacks native motion start')
    sequences=[]
    for event in noops:
        data=event['data'];before,after=data['before'],data['after'];owner=before['current']
        public=owner['publicSubject']
        need(event.get('kind')=='native-observation' and data.get('observation')=='wild-walk-clear'
            and data.get('subject')==subject and before==after
            and type(before.get('active')) is int and before['active']==0
            and type(before.get('mode')) is int and before['mode']==0,
            'wild Walk idle clear changed state')
        check_cleared_state(before)
        need(owner.get('subject')==subject and all(public.get(k)==actor.get(k) for k in IDENTITY)
            and public.get('motionPhase')=='IDLE' and public.get('motionKind')=='NONE'
            and public.get('commitSequence')==actor['commitSequence']
            and public.get('logical')==actor['logical'] and public.get('reservationId')==0
            and owner.get('sourceIdentity')==actor['sourceIdentity']
            and owner.get('engineIdentity')=={k:actor['engineIdentity'].get(k) for k in ENGINE}
            and owner.get('objectPointer')==actor['engineIdentity']['pointer'] and owner.get('slot')==actor['handle']['slot']
            and all(owner['worldContext'].get(k)==initial['context'][k] for k in ('mapId','fieldEpoch','mapGeneration'))
            and owner.get('statePointer')==owner['worldContext'].get('statePointer')
            and all(type(owner.get(k)) is int and 0x02000000<=owner[k]<0x02400000 and owner[k]%4==0
                for k in ('statePointer','runtimePointer','objectPointer')),
            'wild Walk idle clear lacks initial idle owner')
        need(type(event.get('frame')) is int and initial['frame']<event['frame']<=motion['startFrame']
            and initial['actorFrame']<=data['entryActorFrame']<=data['returnActorFrame']<=start_trace['data']['actorFrame']
            and initial['nativeCycle']<=data['entryNativeCycle']<=data['returnNativeCycle']
            and type(data.get('sequence')) is int and data['sequence']>0,
            'wild Walk idle clear is outside pre-motion window')
        sequences.append(data['sequence'])
    need(sequences==sorted(set(sequences)),'wild Walk duplicate idle clear receipt')
    return sequences


class WildWalkNegative:
    def __init__(self,fault):
        if fault not in FAULTS:raise ValueError('unknown wild Walk fault')
        self.fault,self.applied=fault,False

    def mutate(self,row,subjects):
        if self.applied or row.get('phase')!='observe' or not subjects:return row
        changed=deepcopy(row);handles={s['handle']['value'] for s in subjects.values()}
        for sample in changed.get('samples',[]):
            actor=next((a for a in sample.get('actors',[]) if a.get('handle',{}).get('value') in handles),None)
            if actor is not None and self.fault=='wild-walk-absent-subject':sample['actors'].remove(actor);self.applied=True
            elif actor is not None and self.fault=='wild-walk-stale-subject':actor['authorityGeneration']+=1;self.applied=True
            elif actor is not None and actor.get('motionKind')=='WALK' \
                    and actor.get('motionPhase')=='MOVING' and actor.get('motionElapsed',0)>0 \
                    and self.fault=='wild-walk-bad-render':
                actor['engineObject']['pos_x']+=1;self.applied=True
            elif self.fault=='wild-walk-missing-reader' and 'wildWalk' in sample:sample.pop('wildWalk');self.applied=True
            elif self.fault=='wild-walk-held-input' and sample.get('wildWalk',{}).get('latestCompletedInput'):
                sample['wildWalk']['latestCompletedInput']['heldKeys']=16;self.applied=True
            if self.applied:break
        if not self.applied:
            for event in changed.get('events',[]):
                data=event.get('data',{})
                if self.fault in MEANINGS and data.get('actorHandle') in handles and data.get('event')==MEANINGS[self.fault]:
                    data['event']='WORLD_EFFECT';self.applied=True
                elif data.get('observation')=='wild-walk-clear' and data.get('before',{}).get('active')==1 \
                        and data.get('before',{}).get('mode')==1:
                    if self.fault=='wild-walk-clear-active':data['after']['active']=1;self.applied=True
                    elif self.fault=='wild-walk-clear-wrong-owner':data['after']['current']['slot']+=1;self.applied=True
                    elif self.fault=='wild-walk-missing-clear':data['observation']='unrelated-clear';self.applied=True
                if self.applied:break
        return changed if self.applied else row


def validate_negative_result(result,fault):
    need(fault in FAULTS and result.get('passed') is False,'wild Walk copied control did not fail')
    failures=result.get('failures',[])+result.get('measurements',{}).get(KIND,{}).get('failures',[])
    reasons=set()
    for value in failures:
        if isinstance(value,str):reasons.add(value)
        elif isinstance(value,dict):reasons.update(value.get(k) for k in ('detail','message') if isinstance(value.get(k),str))
    expected=('missing native '+MEANINGS[fault]) if fault in MEANINGS else {
        'wild-walk-absent-subject':'selected handle must name exactly one current active actor',
        'wild-walk-stale-subject':'selected actor has a stale authorityGeneration',
        'wild-walk-bad-render':'wild Walk nonlinear render', 'wild-walk-held-input':'wild Walk requires measured neutral input',
        'wild-walk-clear-active':'Wild Walk clear state remains active',
        'wild-walk-missing-clear':'wild Walk clear receipts lost',
        'wild-walk-clear-wrong-owner':'wild Walk clear binding differs','wild-walk-missing-reader':"'wildWalk'"}[fault]
    need(expected in reasons,
         'wild Walk copied control failed for an unrelated reason: '+fault)
