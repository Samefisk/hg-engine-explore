"""Two original Stomp cases, using measured native values only.

The stream meter owns raw frame/sequence validation and partitions calls by
the bound actor reservation. It must retain all scoped policy/feedback calls,
including zero-effect calls, and every completed paired pose in each window.
This pure contract never grants accepted ROM proof.
"""
from copy import deepcopy
import struct

from tools.overworld.devtools_records import select_current_actor, engine_binding_identity
from tools.overworld.devtools_mount_pacing_measurement import check_pair_pose
from tools.overworld.devtools_mount_pacing_observer import ENGINE
from tools.overworld.devtools_walk_matrix_contract import LIFECYCLE
from tools.overworld.devtools_wild_walk_measurement import IDENTITY

KIND='mounted-stomp-v1'
REQUIREMENT='legacy.stomp'
CASES=(dict(index=0,duration=2,threshold=2),dict(index=1,duration=3,threshold=2))
RULES=(
    ('natural-input','stomp-walk-input-results',[1,1]),
    ('live-actor-identity','stomp-cyndaquil-identity-flags',[1,'MOUNTED',155,1,1]),
    ('logical-commit','stomp-player-step-count',2),
    ('rendered-motion','stomp-pair-sync-results',[1,1]),
    ('feedback-effect','stomp-positive-negative-feedback',[1,1,1,0,0,0]),
    ('control-release','stomp-terminal-control-state',['IDLE',0,0,1]),
)


def require(value,reason):
    if not value:raise ValueError('Stomp: '+reason)


def same_completed_object(snapshot,native_pose):
    """Only the native reader adds the two actual z-offset components."""
    return isinstance(snapshot,dict) and isinstance(native_pose,dict) \
        and set(native_pose)-set(snapshot)<={'unk88_z','unk94_z'} \
        and all(k in native_pose and v==native_pose[k] for k,v in snapshot.items())


def contract():
    return {claim:[dict(name=name,operator='eq',type='array' if isinstance(expected,list) else 'integer',
        validator='meaningful-observation',expected=deepcopy(expected))] for claim,name,expected in RULES}


def _actor(snapshot,subject):
    select_current_actor(snapshot,subject)
    actor=next(a for a in snapshot['actors'] if a['handle']==subject['handle'])
    require(actor['species']==155 and actor['role']=='MOUNTED' and actor.get('inputOwnership')==1,
        'requires current mounted Cyndaquil')
    reservations=[]
    for a in snapshot['actors']:
        if not a.get('active'):continue
        require(a.get('presentationAttached') is True and a['handle']['fieldEpoch']==snapshot['context']['fieldEpoch'],
            'active actor presentation or epoch differs')
        if a.get('reservationId'):reservations.append(a['reservationId'])
    require(len(reservations)==len(set(reservations)),'active reservation duplicated')
    return actor


def _idle(actor):
    return actor['motionKind']=='NONE' and actor['motionPhase']=='IDLE' and actor['reservationId']==0 \
        and actor['movementPolicy']['pending']==0


def validate_lifecycle(case):
    events=case['events']
    require(isinstance(events,list) and not any(e.get('event')=='MOTION_CANCELED' for e in events),'motion canceled')
    selected=[e for e in events if e.get('event') in LIFECYCLE]
    require([e.get('event') for e in selected]==list(LIFECYCLE),'exact lifecycle count or order differs')
    previous=None
    for event in selected:
        name=event['event'];field='valueA' if name=='MOTION_STARTED' else 'valueB'
        require(event.get('subject')==case['subject'] and event.get('reason')=='OK'
            and (name=='CONTROL_RETURNED' or type(event.get(field)) is int and event[field]==1),
            'lifecycle owner or meaning differs')
        require(type(event.get('sequence')) is int and event['sequence']>0
            and all(type(event.get(k)) is int and case['initial'][k]<=event[k]<=case['terminal'][k]
                for k in ('frame','actorFrame'))
            and (previous is None or event['sequence']>previous['sequence']
                and event['frame']>=previous['frame'] and event['actorFrame']>=previous['actorFrame']),
            'lifecycle clock or order differs')
        previous=event


def validate_feedback(window,case,bindings):
    """window={complete,startFrame,endFrame,counts,calls}; calls are unchanged
    stomp-policy receipts. counts is the enclosing scoped reader's count delta,
    not a count inferred by the collector after dropping unwanted callbacks.
    Nested dust/allocate/init/sound/soundStart fields are native reader receipts.
    """
    names=('dust','allocate','init','sound','soundStart')
    require(window.get('complete') is True and window.get('startFrame')==case['initial']['frame']
        and window.get('endFrame')==case['terminal']['frame'],'feedback coverage window missing')
    calls=window.get('calls')
    require(isinstance(calls,list) and 1<=len(calls)<=64,'complete scoped policy calls missing')
    counts=dict.fromkeys(('policy',*names),0);effects=0;commits=0;starts=0
    initial_actor=next(a for a in case['initial']['actors'] if a['handle']==case['subject']['handle'])
    reference=calls[0]['before']
    def native(value,parent=None):
        current=value['before']
        require(value.get('normalReturn') is True and current['subject']==case['subject']
            and current['mountPointer']==bindings['pointer'] and current['playerPointer']==bindings['anchorPointer']
            and bindings.get('anchorInCurrentManager') is True
            and set(current['engineIdentity'])==set(ENGINE)
            and all(k in bindings and current['engineIdentity'][k]==bindings[k] for k in ENGINE)
            and current['sourceIdentity']==initial_actor['sourceIdentity']
            and all(current['publicSubject'].get(k)==initial_actor.get(k) for k in IDENTITY)
            and all(current['worldContext'].get(k)==v for k,v in case['initial']['context'].items())
            and current['worldContext']==reference['worldContext']
            and current['avatarPointer']==reference['avatarPointer']
            and all(type(pointer) is int and pointer%4==0 and 0x02000000<=pointer<0x02400000
                for pointer in (current['avatarPointer'],current['worldContext'].get('fieldPointer'),
                    current['worldContext'].get('statePointer'))),'feedback native owner differs')
        require(all(type(value['args'][i]) is int for i in range(4)),'feedback native arguments missing')
        entry,returned=value['entryClock'],value['returnClock']
        require(all(type(clock.get(k)) is int for clock in (entry,returned) for k in ('actorFrame','nativeCycle'))
            and entry['actorFrame']==returned['actorFrame'] and entry['nativeCycle']<=returned['nativeCycle']
            and case['initial']['actorFrame']<=entry['actorFrame']<=case['terminal']['actorFrame']
            and case['initial']['nativeCycle']<=entry['nativeCycle']<=returned['nativeCycle']<=case['terminal']['nativeCycle']
            and case['initial']['frame']<=value['completedFrame']<case['terminal']['frame'],
            'feedback native clock differs')
        if parent is not None:
            require(current==parent['before'] and entry['actorFrame']==parent['entryClock']['actorFrame']
                and parent['entryClock']['nativeCycle']<=entry['nativeCycle']<=returned['nativeCycle']<=parent['returnClock']['nativeCycle'],
                'feedback native nesting differs')
    for call in calls:
        native(call);counts['policy']+=1
        raw=bytes.fromhex(call['policyHex']);profile=bytes.fromhex(call['profileHex'])
        require(call.get('kind')=='policy' and len(raw)==28 and struct.unpack_from('<HH',raw)==(1,28)
            and raw[8]==case['subject']['handle']['slot'] and raw[21]==call['effect']
            and len(profile)==72 and profile[70]==call['stompTime']==case['case']['threshold']
            and profile[7]==case['case']['duration'] and call['effect'] in (0,1)
            and call['objectPointer']==bindings['pointer'] and call['args'][0]==call['before']['avatarPointer']
            and call['args'][1]==bindings['pointer'],'feedback policy/profile bytes differ')
        require(set(call['feedback'])==set(names),'feedback sink coverage missing')
        if raw[9]==2:  # The mounted output sink receives START_RESULT, not INPUT.
            starts+=1
            require(raw[16]==1 and raw[19]==case['case']['duration'],'native START_RESULT time/decision differs')
        if raw[9]==3:
            commits+=1
            require(raw[16]==1,'native commit was not consumed')
        require(call['effect']==0 or raw[9]==3,'Stomp effect outside native commit')
        effects+=int(call['effect']==1)
        for name in names:
            rows=call['feedback'][name]
            require(isinstance(rows,list) and len(rows)==call['effect'],'feedback sink count differs: '+name)
            counts[name]+=len(rows)
            for row in rows:
                native(row,call);require(row['kind']==name,'feedback sink kind differs')
        if call['effect']:
            dust,alloc,init,sound,start=(call['feedback'][k][0] for k in names)
            require(dust['args'][0]==bindings['pointer'] and alloc['returnValue']==init['args'][0]
                and type(alloc['returnValue']) is int and alloc['returnValue']%4==0
                and 0x02000000<=alloc['returnValue']<0x02400000,'dust native allocation failed')
            context=bytes.fromhex(alloc['contextHex']);data=bytes.fromhex(init['effectDataHex'])
            require(len(bytes.fromhex(alloc['positionHex']))==12 and len(context)==16
                and struct.unpack_from('<I',context,12)[0]==bindings['pointer'] and len(data)==36
                and struct.unpack_from('<I',data,28)[0]==bindings['pointer']
                and struct.unpack_from('<I',data,32)[0]==init['renderPointer']
                and 0x02000000<=init['renderPointer']<0x02400000 and type(init['returnValue']) is int
                and init['returnValue']==1,'dust native render initialization failed')
            require(sound['args'][0]==2183 and start['soundId']==2183
                and type(start['returnValue']) is int and start['returnValue']==1,'native stomp sound start failed')
    require(window.get('counts')==counts,'feedback scoped counts differ')
    require(starts==1,'native START_RESULT count differs')
    require(commits==1,'native policy commit count differs')
    expected=1 if case['case']['index']==0 else 0
    require(effects==counts['dust']==counts['sound']==expected,'positive/negative feedback differs')
    return [effects,counts['dust'],counts['sound']]


def validate_shared_policies(case):
    """Authenticate retained shared reducer calls and join each output sink."""
    calls=case.get('policies',[]);require(isinstance(calls,list) and 1<=len(calls)<=128,'shared policy coverage missing')
    actor=next(a for a in case['initial']['actors'] if a['handle']==case['subject']['handle'])
    inputs=[];outputs={2:[],3:[]}
    for call in calls:
        request,response=(bytes.fromhex(call[k]) for k in ('requestHex','responseHex'))
        require(call.get('observation')=='walk-policy' and len(request)==len(response)==28
            and request[:4]==b'\x01\x00\x1c\x00' and request[:10]==response[:10]
            and request[8]==call['slot']==case['subject']['handle']['slot'] and request[9]==call['operation']
            and type(call.get('returnValue')) is int and call['returnValue']==1,'shared policy ABI/result differs')
        require(all(call[k].get('status')=='observed-public-subject'
            and all(call[k].get(field)==actor.get(field) for field in IDENTITY)
            for k in ('publicSubject','publicSubjectAfter')),'shared policy public identity differs')
        require(all(type(call.get(k)) is int for k in ('sequence','entryActorFrame','returnActorFrame','entryNativeCycle','returnNativeCycle','frame'))
            and call['entryActorFrame']==call['returnActorFrame']
            and case['initial']['nativeCycle']<=call['entryNativeCycle']<=call['returnNativeCycle']<=case['terminal']['nativeCycle']
            and case['initial']['frame']<call['frame']<=case['terminal']['frame'],'shared policy clock differs')
        if call['operation'] in (1,3):
            require(call.get('laneHex')==case['feedback']['calls'][0]['profileHex'],'shared policy lane differs')
        if call['operation']==1 and response[16]==2:
            inputs.append(call)
            require(response[19]==case['case']['duration'],'native input travel time differs')
            require(request[10]==response[17]=={'UP':0,'DOWN':1,'LEFT':2,'RIGHT':3}[case['input']['keys'][0]],
                'shared input direction differs')
        if call['operation'] in outputs:outputs[call['operation']].append(call)
    require(len(inputs)==1,'native INPUT TRY_STEP count differs')
    for operation in (2,3):
        outer=[c for c in case['feedback']['calls'] if bytes.fromhex(c['policyHex'])[9]==operation]
        require(len(outputs[operation])==len(outer)==1,'shared/output policy count differs')
        shared,output=outputs[operation][0],outer[0]
        require(shared['responseHex']==output['policyHex'] and shared['frame']==output['completedFrame']+1
            and shared['returnActorFrame']==output['entryClock']['actorFrame']
            and shared['returnNativeCycle']<=output['entryClock']['nativeCycle'], 'shared/output policy linkage differs')
    start=outputs[2][0]
    require(inputs[0]['sequence']<start['sequence']<outputs[3][0]['sequence']
        and inputs[0]['returnActorFrame']==start['entryActorFrame']
        and inputs[0]['returnNativeCycle']<=start['entryNativeCycle']
        and inputs[0]['responseHex'][8:16]==start['requestHex'][8:16], 'INPUT/START_RESULT linkage differs')


def validate_stomp(cases,subject,terminal):
    """Validate exact two cases and return the six original measured rows.

    Case fields: case, subject, reservation, events (native lifecycle schema);
    initial/terminal completed snapshots;
    input={keys,requestedGameFrames,completedGameFrames,observedFieldFrames};
    steps=[{subject,playerPointer,normalReturn,eventConsumed,frame,actorFrame,nativeCycle}];
    poses=[completed snapshots] for each frame initial+1 through terminal;
    feedback is the complete actor-scoped native policy window (see validator).
    Raw framing, native input readback, code authentication and stream coverage
    are independently required in the enclosing meter, not asserted by flags.
    """
    require(isinstance(cases,list) and len(cases)==2,'exact positive and negative cases missing')
    require(cases[-1]['terminal']==terminal,'terminal snapshot differs')
    start_actor=_actor(cases[0]['initial'],subject)
    require(_idle(start_actor),'initial actor not released')
    bindings=engine_binding_identity(start_actor['engineIdentity'])
    reservations=set();feedback=[]
    for expected,c in zip(CASES,cases):
        require(c.get('case')==expected and c.get('subject')==subject,'case order or subject differs')
        require(all(type(c['case'][k]) is int for k in ('index','duration','threshold')),'case integer differs')
        initial,end=c['initial'],c['terminal']
        before,after=(_actor(s,subject) for s in (initial,end))
        require(_idle(before) and _idle(after),'case control not released')
        for a in (before,after):
            require(all(a.get(k)==start_actor.get(k) for k in IDENTITY)
                and a['sourceIdentity']==start_actor['sourceIdentity']
                and engine_binding_identity(a['engineIdentity'])==bindings,'case owner changed')
        require(initial['context']==end['context']==cases[0]['initial']['context'],'case context changed')
        if expected['index']:
            previous=cases[0]['terminal']
            require(all(initial.get(k)==previous.get(k) for k in ('frame','actorFrame','nativeCycle','actors','player','context')),
                'case boundary gap')
            native_before=cases[0]['feedback']['calls'][0]['before']
            native_after=c['feedback']['calls'][0]['before']
            require(all(native_before[k]==native_after[k] for k in ('worldContext','avatarPointer',
                'sourceIdentity','engineIdentity','playerPointer','mountPointer')),'native case owner changed')
        require(type(c['reservation']) is int and c['reservation']>0 and c['reservation'] not in reservations,
            'reservation missing or reused')
        reservations.add(c['reservation'])
        validate_lifecycle(c)
        request=c['input'];keys=request.get('keys')
        require(isinstance(keys,list) and len(keys)==1 and keys[0] in ('UP','DOWN','LEFT','RIGHT')
            and all(type(request.get(k)) is int and request[k]==1 for k in
                ('requestedGameFrames','completedGameFrames','observedFieldFrames')),'normal one-frame input differs')
        dx,dy={'UP':(0,-1),'DOWN':(0,1),'LEFT':(-1,0),'RIGHT':(1,0)}[keys[0]]
        require(after['commitSequence']==before['commitSequence']+1
            and after['logical']==dict(x=before['logical']['x']+dx,y=before['logical']['y']+dy),
            'one logical commit or landing differs')
        require(end['player']['pos_x']-initial['player']['pos_x']==dx*65536
            and end['player']['pos_z']-initial['player']['pos_z']==dy*65536
            and end['player']['pos_y']==initial['player']['pos_y'],'rendered displacement differs')
        steps=c['steps']
        require(isinstance(steps,list) and len(steps)==1,'native player step count differs')
        step=steps[0]
        require(step.get('subject')==subject and step.get('normalReturn') is True
            and type(step.get('eventConsumed')) is int and step['eventConsumed']==0
            and step.get('playerPointer')==bindings['anchorPointer']
            and all(type(step.get(k)) is int and initial[k]<=step[k]<=end[k] for k in ('frame','actorFrame','nativeCycle')),
            'native player step owner or boundary differs')
        poses=c['poses']
        require(isinstance(poses,list) and 1<=len(poses)<=3000
            and [p['frame'] for p in poses]==list(range(initial['frame']+1,end['frame']+1))
            and poses[-1]==end,'paired pose coverage differs')
        previous=initial
        for pose in poses:
            a=_actor(pose,subject)
            require(pose['actorFrame']==previous['actorFrame']+1 and pose['nativeCycle']>previous['nativeCycle']
                and engine_binding_identity(a['engineIdentity'])==bindings,'paired pose clock or owner differs')
            pair=pose['stompFeedback']['latestCompletedPose']
            require(pair['boundary']=='main-task-queue-completion' and pair['subject']==subject
                and all(pair[k]==pose[k] for k in ('frame','actorFrame','nativeCycle'))
                and all(pair['publicSubject'].get(k)==a.get(k) for k in IDENTITY)
                and pair['sourceIdentity']==a['sourceIdentity']
                and pair['engineIdentity']=={k:bindings[k] for k in ENGINE}
                and pair['playerPointer']==bindings['anchorPointer'] and pair['mountPointer']==bindings['pointer']
                and all(pair['worldContext'].get(k)==v for k,v in pose['context'].items())
                and same_completed_object(pose['player'],pair['player'])
                and same_completed_object(a['engineObject'],pair['mount']),'native paired pose boundary differs')
            check_pair_pose(pair)
            previous=pose
        feedback.append(validate_feedback(c['feedback'],c,bindings))
        validate_shared_policies(c)
    actuals=[[1,1],[int(start_actor['identityVerified']),start_actor['role'],start_actor['species'],
        int(start_actor['presentationAttached']),start_actor['inputOwnership']],sum(len(c['steps']) for c in cases),
        [1,1],sum(feedback,[]),[after['motionPhase'],after['reservationId'],after['movementPolicy']['pending'],after['inputOwnership']]]
    evidence={}
    for (claim,name,expected),actual in zip(RULES,actuals):
        require(actual==expected,'original metric differs: '+name)
        evidence[claim]=[dict(name=name,actual=actual)]
    return dict(acceptedProof=False,proofEvidence=evidence,actuals=actuals)
