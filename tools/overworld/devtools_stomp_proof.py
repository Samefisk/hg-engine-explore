"""Original Stomp measurements and copied-data controls, never recorder proof."""
from copy import deepcopy
from pathlib import Path

from tools.overworld.devtools_stomp_contract import KIND, REQUIREMENT, RULES, contract, validate_stomp

CLAIMS=tuple(row[0] for row in RULES)
MEANINGS={'stomp-missing-start':'MOTION_STARTED','stomp-missing-commit':'LOGICAL_COMMIT',
    'stomp-missing-finish':'MOTION_FINISHED','stomp-missing-return':'CONTROL_RETURNED'}
FAULTS=('stomp-absent-subject','stomp-stale-subject','stomp-missing-dust','stomp-missing-sound',
    'stomp-negative-effect','stomp-input','stomp-pose','stomp-coverage','stomp-fixture',
    'stomp-step',*MEANINGS)


def need(value,reason):
    if not value:raise ValueError(reason)


def measurements(replay,record):
    value=replay.get('measurements',{}).get(KIND,{})
    need(replay.get('passed') is True and replay.get('failures')==[]
        and all(value.get(k) is True for k in ('passed','ready','closed'))
        and value.get('acceptedProof') is False and value.get('failures')==[],
        'Stomp lacks closed independent replay')
    need(record.get('sessionCleanup')==dict(sessionId=record.get('sessionId'),closed=True,errors=[]),
        'Stomp private session did not close cleanly')
    checked=validate_stomp(value['cases'],value['subject'],value['terminalSnapshot'])
    need(value.get('initial')==value['cases'][0]['initial'],'Stomp initial snapshot differs')
    need(value.get('proofEvidence')==checked['proofEvidence'],'Stomp metric summary differs')
    return [dict(claim=claim,name=name,value=deepcopy(actual),expected=deepcopy(expected),
        operator='eq',passed=True) for (claim,name,expected),actual in zip(RULES,checked['actuals'])]


def replay_records(test,rows,*,repo=None,fault=None):
    """Rows must already have their shared artifact references hash-checked and expanded."""
    from tools.overworld.devtools_test_contract import TestEvaluator
    from tools.overworld.devtools_test_inputs import measurement_inputs
    evaluator=TestEvaluator(test)
    evaluator.install_measurements(measurement_inputs(test,repo or Path(__file__).resolve().parents[2]))
    need(KIND in evaluator.measurements,'Stomp replay needs exact typed measurement')
    negative=StompNegative(fault) if fault else None
    for row in rows:
        report=evaluator.observe_record(negative.mutate(row,evaluator.subjects) if negative else row,full_report=False)
        if report['state']=='failed':break
    result=evaluator.finish()
    if negative:need(negative.applied,'Stomp copied control had no matching raw observation')
    return result


class StompNegative:
    def __init__(self,fault):
        need(fault in FAULTS,'unknown Stomp copied fault')
        self.fault=fault;self.applied=False

    def mutate(self,row,subjects):
        if self.applied:return row
        changed=deepcopy(row);fault=self.fault
        if row.get('command')=='mount-walk.configure' and fault=='stomp-fixture':
            receipt=changed.get('receipt',{});receipt=receipt.get('value',receipt)
            after=receipt.get('after',{})
            if 'profileHex' in after:
                raw=bytearray.fromhex(after['profileHex']);raw[70]=3;after['profileHex']=raw.hex()
                self.applied=True;return changed
        if row.get('phase')!='observe' or not subjects:return row
        handles={s['handle']['value'] for s in subjects.values()}
        for sample in changed.get('samples',[]):
            actor=next((a for a in sample.get('actors',[]) if a.get('handle',{}).get('value') in handles),None)
            if actor is None:continue
            if fault=='stomp-absent-subject':sample['actors'].remove(actor)
            elif fault=='stomp-stale-subject':actor['authorityGeneration']+=1
            elif fault=='stomp-pose':actor['engineObject']['pos_x']+=1
            elif fault=='stomp-input':sample['selector']['heldKeys']=sample['selector']['rawHeld']=128
            elif fault=='stomp-coverage':sample['stompFeedback']['counts']['policy']+=1
            else:continue
            self.applied=True;return changed
        for event in changed.get('events',[]):
            data=event.get('data',{});observation=data.get('observation')
            native_subject=data.get('before',{}).get('subject',data.get('subject',{}))
            scoped=native_subject.get('handle',{}).get('value') in handles
            if data.get('actorHandle') in handles and fault in MEANINGS and data.get('event')==MEANINGS[fault]:
                data['event']='WORLD_EFFECT'
            elif observation=='stomp-playerStep' and scoped and fault=='stomp-step':data['eventConsumed']=1
            elif observation=='stomp-policy' and scoped:
                if fault in ('stomp-missing-dust','stomp-missing-sound') and data.get('effect')==1:
                    data['feedback']['dust' if fault=='stomp-missing-dust' else 'sound']=[]
                elif fault=='stomp-negative-effect' and data.get('stompTime')==2 and \
                        bytes.fromhex(data.get('profileHex',''))[7:8]==b'\x03':
                    raw=bytearray.fromhex(data['policyHex'])
                    if raw[9]!=3:continue
                    raw[21]=1;data['policyHex']=raw.hex();data['effect']=1
                else:continue
            else:continue
            self.applied=True;break
        return changed if self.applied else row


def validate_negative_result(result,fault):
    need(fault in FAULTS and result.get('passed') is False,'Stomp copied control did not fail')
    failures=result.get('failures',[])+result.get('measurements',{}).get(KIND,{}).get('failures',[])
    reasons=set()
    for failure in failures:
        if isinstance(failure,str):reasons.add(failure)
        elif isinstance(failure,dict):
            reasons.update(failure[k] for k in ('detail','message') if isinstance(failure.get(k),str))
    expected={
        'stomp-absent-subject':{'selected handle must name exactly one current active actor'},
        'stomp-stale-subject':{'selected actor has a stale authorityGeneration'},
        'stomp-missing-dust':{'Stomp: feedback sink count differs: dust','Stomp stream: nested feedback stream differs'},
        'stomp-missing-sound':{'Stomp: feedback sink count differs: sound','Stomp stream: nested feedback stream differs'},
        'stomp-negative-effect':{'Stomp: feedback sink count differs: dust','Stomp: positive/negative feedback differs',
            'Stomp stream: reader last policy differs'},
        'stomp-input':{'matrix native input differs'},
        'stomp-pose':{'mounted base, facing or rider offset differs','Stomp stream: native completed pose differs'},
        'stomp-coverage':{'Stomp stream: reader coverage/counts differ','Stomp: feedback scoped counts differ'},
        'stomp-fixture':{'Stomp stream: fixture changed unrelated native state'},
        'stomp-step':{'Stomp: native player step owner or boundary differs','Stomp stream: player step result differs'},
    }
    for name,meaning in MEANINGS.items():
        expected[name]={'Stomp: exact lifecycle count or order differs','Stomp stream: exact lifecycle missing: '+meaning}
    need(bool(reasons & expected[fault]),'Stomp copied control failed for unrelated reason: '+fault)
