"""Exact corner proof and copied-data controls through the shared evaluator."""
from copy import deepcopy
from pathlib import Path

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_corner_measurement import CornerMeasurement, DIAGONALS, CARDINALS, LIFECYCLE

KIND='diagonal-corner-v1'
REQUIREMENT='legacy.diagonal-corner-block'
RULES=(('natural-input','natural-input-motion-count',2),
    ('live-actor-identity','diagonal-corner-cyndaquil-identity',[1,'MOUNTED',155,1]),
    ('collision-decision','blocked-commit-sequence',None),
    ('collision-decision','blocked-final-tile',None),
    ('logical-commit','cardinal-logical-commit-count',1),
    ('engine-boundary','cardinal-lifecycle-counts',[1,1,0,1]),
    ('control-release','cardinal-terminal-result',1))
CLAIMS=tuple(dict.fromkeys(r[0] for r in RULES))
MEANINGS={'corner-missing-side-tile':'CANDIDATE_REJECTED','corner-missing-start':'MOTION_STARTED',
    'corner-missing-commit':'LOGICAL_COMMIT','corner-missing-finish':'MOTION_FINISHED','corner-missing-return':'CONTROL_RETURNED'}
FAULTS=('corner-absent-subject','corner-stale-subject','corner-bad-collision','corner-bad-landing',
    'corner-blocked-pose','corner-blocked-commit','corner-recovery-count',*MEANINGS)


def contract():
    result={}
    for claim,name,expected in RULES:
        row=dict(name=name,operator='eq',type='array' if isinstance(expected,list) or expected is None else 'integer',
            validator='blocked-state-unchanged-v1' if expected is None else 'meaningful-observation')
        if expected is not None:row['expected']=deepcopy(expected)
        result.setdefault(claim,[]).append(row)
    return result


def need(ok,reason):
    if not ok:raise ValueError(reason)


def measurements(replay,record):
    value=replay.get('measurements',{}).get(KIND,{})
    need(replay.get('passed') is True and replay.get('failures')==[] and value.get('passed') is True
        and value.get('ready') is True and value.get('closed') is True and value.get('acceptedProof') is False
        and value.get('failures')==[], 'corner lacks closed independent replay')
    need(record.get('sessionCleanup')==dict(sessionId=record.get('sessionId'),closed=True,errors=[]),
         'corner private session did not close cleanly')
    initial,terminal,subject=value['initial'],value['terminal'],value['subject']
    selected=select_current_actor(initial,subject)
    actor=next(a for a in initial['actors'] if a['handle']==selected['handle'])
    # Recheck native query, exact callback arguments and all semantic outcomes.
    # A forged seven-row summary or strict false return cannot replace SIDE_TILE.
    checker=CornerMeasurement(600)
    checker.probe(value['query'],initial)
    checker.subject=deepcopy(subject);checker.initial=deepcopy(initial);checker.actor=deepcopy(actor)
    checker.last=deepcopy(terminal)
    checker._actor(initial);end=checker._actor(terminal)
    need(actor.get('identityVerified') is True and actor.get('presentationAttached') is True,
         'corner live identity is missing')
    for call in value['strictCalls']:checker._strict(call)
    need(checker.calls,'corner native strict call missing')
    checker.traces=deepcopy(value['traces']);checker.commands=deepcopy(value['commands'])
    checker.inputs=deepcopy(value['inputs']);checker.blocked=deepcopy(value['blocked'])
    checker.recovery_frame=value['recoveryFrame'];checker.recovery_target=value['recoveryTarget']
    for event in checker.traces:
        data=event['data']
        need(event.get('kind')=='native' and data.get('actorHandle')==actor['handle']['value']
            and data.get('actor')=={k:v for k,v in actor['handle'].items() if k!='value'},
            'corner semantic event identity differs')
    checker._complete()
    blocked=value['blocked']
    need(blocked['logical']==actor['logical'] and blocked['commitSequence']==actor['commitSequence']
        and blocked['motionKind']=='NONE' and blocked['motionPhase']=='IDLE' and blocked['reservationId']==0,
        'blocked corner moved or committed')
    cleanup=value['cleanup'];reader=cleanup.get('walkCorner',cleanup)
    checker._reader(reader,True)
    need(cleanup.get('closed') is True and cleanup.get('advancedFrames')==0 and cleanup.get('acceptedProof') is False,
         'corner close receipt differs')
    native={name:[e for e in checker.traces if e['data'].get('event')==name] for name in (*LIFECYCLE,'MOTION_CANCELED')}
    identity=[int(actor['identityVerified']),actor['role'],actor['species'],int(actor['presentationAttached'])]
    before_tile=[actor['logical'][k] for k in ('x','y')];blocked_tile=[blocked['logical'][k] for k in ('x','y')]
    values=[sum(bool(c['mask']) for c in checker.commands),identity,
        [actor['commitSequence'],blocked['commitSequence']],[before_tile,blocked_tile],len(native['LOGICAL_COMMIT']),
        [len(native[k]) for k in ('MOTION_STARTED','MOTION_FINISHED','MOTION_CANCELED','CONTROL_RETURNED')],
        int(end['motionPhase']=='IDLE' and end['motionKind']=='NONE' and end['reservationId']==0
            and end['logical']==checker.recovery_target and len(native['CONTROL_RETURNED'])==1)]
    rows=[]
    for (claim,name,expected),actual in zip(RULES,values):
        need(actual==expected if expected is not None else len(actual)==2 and actual[0]==actual[1],
             'corner original metric differs: '+name)
        measured=[r for r in value['proofEvidence'].get(claim,[]) if r.get('name')==name]
        need(len(measured)==1 and measured[0].get('actual')==actual,'corner metric summary differs: '+name)
        rows.append(dict(claim=claim,name=name,value=actual,expected=deepcopy(actual),operator='eq',passed=True))
    return rows


class CornerNegative:
    def __init__(self,fault):
        need(fault in FAULTS,'unknown corner copied fault')
        self.fault,self.applied=fault,False

    def mutate(self,row,subjects):
        if self.applied:return row
        changed=deepcopy(row)
        if self.fault=='corner-bad-landing' and row.get('command')=='walk-corner.probe':
            q=changed.get('receipt',{});q=q.get('value',q)
            for candidate in q.get('diagonals',[]):
                if candidate.get('oneSideCorner'):
                    candidate['result']=0;self.applied=True;return changed
        if row.get('phase')!='observe' or not subjects:return row
        handles={s['handle']['value'] for s in subjects.values()}
        for sample in changed.get('samples',[]):
            actor=next((a for a in sample.get('actors',[]) if a.get('handle',{}).get('value') in handles),None)
            if actor is None:continue
            if self.fault=='corner-absent-subject':sample['actors'].remove(actor);self.applied=True
            elif self.fault=='corner-stale-subject':actor['authorityGeneration']+=1;self.applied=True
            elif actor.get('motionKind')=='NONE' and not self.applied:
                if self.fault=='corner-blocked-pose':sample['player']['pos_x']+=1;self.applied=True
                elif self.fault=='corner-blocked-commit':actor['commitSequence']+=1;self.applied=True
            elif self.fault=='corner-recovery-count' and actor.get('motionKind')=='WALK':actor['commitSequence']+=2;self.applied=True
            if self.applied:break
        if not self.applied:
            for event in changed.get('events',[]):
                data=event.get('data',{})
                if self.fault in MEANINGS and data.get('actorHandle') in handles and data.get('event')==MEANINGS[self.fault]:
                    data['event']='WORLD_EFFECT';self.applied=True
                elif self.fault=='corner-bad-collision' and data.get('observation')=='walk-corner-strict' and data.get('collisions'):
                    data['collisions'][0]['rawMask']^=1;self.applied=True
                if self.applied:break
        return changed if self.applied else row


def replay_records(test,rows,*,repo=None,fault=None):
    """Replay sealed, artifact-expanded raw rows through the live job evaluator."""
    from tools.overworld.devtools_test_contract import TestEvaluator
    from tools.overworld.devtools_test_inputs import measurement_inputs
    evaluator=TestEvaluator(test)
    evaluator.install_measurements(measurement_inputs(test,repo or Path(__file__).resolve().parents[2]))
    need(KIND in evaluator.measurements,'corner replay needs exact typed measurement')
    negative=CornerNegative(fault) if fault else None
    for row in rows:
        value=negative.mutate(row,evaluator.subjects) if negative else row
        report=evaluator.observe_record(value,full_report=False)
        if report['state']=='failed':break
    result=evaluator.finish()
    if negative:need(negative.applied,'corner copied control had no matching raw observation')
    return result


def validate_negative_result(result,fault):
    need(fault in FAULTS and result.get('passed') is False,'corner copied control did not fail')
    failures=result.get('failures',[])+result.get('measurements',{}).get(KIND,{}).get('failures',[])
    reasons=set()
    for value in failures:
        if isinstance(value,str):reasons.add(value)
        elif isinstance(value,dict):reasons.update(value.get(k) for k in ('detail','message') if isinstance(value.get(k),str))
    expected=('missing exact CANDIDATE_REJECTED REJECTED_SIDE_TILE' if fault=='corner-missing-side-tile'
        else 'corner exact lifecycle missing: '+MEANINGS[fault]) if fault in MEANINGS else {
        'corner-absent-subject':'selected handle must name exactly one current active actor',
        'corner-stale-subject':'selected actor has a stale authorityGeneration',
        'corner-bad-collision':'corner nested collision binding, clock or mask differs',
        'corner-bad-landing':'corner destination or side query differs',
        'corner-blocked-pose':'blocked corner rendered pose changed',
        'corner-blocked-commit':'blocked corner moved or committed',
        'corner-recovery-count':'extra corner recovery commit or motion'}[fault]
    need(expected in reasons,'corner copied control failed for unrelated reason: '+fault)
