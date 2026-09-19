"""Policy-reader calibration only; not a live collision-reader control."""
from copy import deepcopy

from tools.overworld.devtools_corner_control_measurement import KIND, validate_control, native_call
from tools.overworld.devtools_corner_measurement import CornerMeasurement
from tools.overworld.devtools_corner_proof import CornerNegative, FAULTS as BASELINE_FAULTS, RULES as BASELINE_RULES
from tools.overworld.devtools_corner_proof import validate_negative_result as validate_baseline_negative
from tools.overworld.devtools_records import select_current_actor

REQUIREMENT='shared.corner-recorder-control-v1'
RULES=(('live-actor-identity','bound-corner-control-subject'),
    ('controlled-action','same-reader-policy-fault'),('controlled-action','exact-policy-restoration'))
CLAIMS=tuple(dict.fromkeys(c for c,_ in RULES))
CONTROL_FAULTS=('corner-control-missing-control','corner-control-wrong-byte','corner-control-unrestored',
    'corner-control-clock','corner-control-registers','corner-control-address')
FAULTS=(*BASELINE_FAULTS,*CONTROL_FAULTS)


def contract():
    result={}
    for claim,name in RULES:
        result.setdefault(claim,[]).append(dict(name=name,operator='eq',type='integer',validator='meaningful-observation',expected=1))
    return result


def need(ok,reason):
    if not ok:raise ValueError(reason)


def validate_baseline(natural):
    need(natural.get('ready') is True and natural.get('failures')==[]
        and natural.get('acceptedProof') is False,'corner control lacks original complete baseline')
    initial,subject=natural['initial'],natural['subject']
    selected=select_current_actor(initial,subject)
    checker=CornerMeasurement(600)
    checker.probe(natural['query'],initial)
    checker.initial=deepcopy(initial);checker.subject=deepcopy(subject)
    checker.actor=deepcopy(next(a for a in initial['actors'] if a['handle']==selected['handle']))
    checker.last=deepcopy(natural['terminal']);checker._actor(initial);checker._actor(checker.last)
    for call in natural['strictCalls']:checker._strict(call)
    need(checker.calls,'corner control lacks real strict call')
    checker.traces=deepcopy(natural['traces']);checker.commands=deepcopy(natural['commands'])
    checker.inputs=deepcopy(natural['inputs']);checker.blocked=deepcopy(natural['blocked'])
    checker.recovery_frame=natural['recoveryFrame'];checker.recovery_target=natural['recoveryTarget']
    checker._complete()
    evidence=checker.result()['proofEvidence']
    for claim,name,expected in BASELINE_RULES:
        rows=[r for r in evidence.get(claim,[]) if r['name']==name]
        need(len(rows)==1,'corner control baseline row missing')
        actual=rows[0]['actual']
        need(actual==expected if expected is not None else len(actual)==2 and actual[0]==actual[1],
            'corner control baseline row differs: '+name)
    need(evidence==natural['proofEvidence'],'corner control baseline summary differs')


def measurements(replay,record):
    meter=replay.get('measurements',{}).get(KIND,{})
    need(replay.get('passed') is True and replay.get('failures')==[] and meter.get('passed') is True
        and meter.get('closed') is True and meter.get('ready') is True and meter.get('acceptedProof') is False
        and meter.get('failures')==[],'corner control lacks complete independent replay')
    natural=meter['natural'];validate_baseline(natural)
    need(meter.get('subject')==natural['subject'] and meter.get('terminal')==natural['terminal'],
        'corner control baseline owner differs')
    validate_control(meter['control'],natural['strictCalls'][-1],meter['terminal'],meter['subject'])
    cleanup=meter.get('cleanup',{});reader=cleanup.get('walkCorner',{})
    need(cleanup.get('closed') is True and cleanup.get('advancedFrames')==0 and cleanup.get('acceptedProof') is False
        and reader.get('armed') is True and reader.get('closed') is True and reader.get('failure') is None
        and reader.get('subject')==meter['subject'] and isinstance(reader.get('calls'),list)
        and [native_call(call) for call in reader['calls']]==[native_call(call) for call in natural['strictCalls']]
        and reader.get('counts')==dict(strict=len(natural['strictCalls']),
            collision=sum(len(c['collisions']) for c in natural['strictCalls']),
            landing=sum(len(c['landings']) for c in natural['strictCalls']))
        and reader.get('guestMemoryWrites')==2 and reader.get('policyCalibration')==meter['control'],
        'corner control cleanup differs')
    need(record.get('sessionCleanup')==dict(sessionId=record.get('sessionId'),closed=True,errors=[]),
        'corner control private session did not close')
    return [dict(claim=c,name=n,value=1,expected=1,operator='eq',passed=True) for c,n in RULES]


class CornerControlNegative:
    def __init__(self,fault):
        need(fault in FAULTS,'unknown corner control fault')
        self.fault,self.applied=fault,False
        self.baseline=CornerNegative(fault) if fault in BASELINE_FAULTS else None
    def mutate(self,row,subjects):
        if self.baseline:
            result=self.baseline.mutate(row,subjects);self.applied=self.baseline.applied;return result
        if self.applied or row.get('command')!='walk-corner.calibrate':return row
        result=deepcopy(row);receipt=result.get('receipt',{});control=receipt.get('calibration')
        if self.fault=='corner-control-missing-control':receipt.pop('calibration',None);self.applied=True
        elif isinstance(control,dict):
            if self.fault=='corner-control-wrong-byte':control['bad']=deepcopy(control['clean'])
            elif self.fault=='corner-control-unrestored':control['restored']=deepcopy(control['bad'])
            elif self.fault=='corner-control-clock':control['restoredClock']['nativeCycle']+=1
            elif self.fault=='corner-control-registers':control['restoredRegisters']['r0']^=1
            elif self.fault=='corner-control-address':control['changedAddress']+=1
            self.applied=True
        return result if self.applied else row


def validate_negative_result(result,fault):
    if fault in BASELINE_FAULTS:
        copied=deepcopy(result);meter=copied.get('measurements',{}).get(KIND,{})
        from tools.overworld.devtools_corner_proof import KIND as BASELINE_KIND
        copied.setdefault('measurements',{})[BASELINE_KIND]=meter.get('natural',meter)
        return validate_baseline_negative(copied,fault)
    need(fault in CONTROL_FAULTS and result.get('passed') is False,'corner control copied fault did not fail')
    failures=result.get('failures',[])+result.get('measurements',{}).get(KIND,{}).get('failures',[])
    reasons=set()
    for value in failures:
        if isinstance(value,str):reasons.add(value)
        elif isinstance(value,dict):reasons.update(value.get(k) for k in ('detail','message') if isinstance(value.get(k),str))
    expected={'corner-control-missing-control':'corner control is missing or not restored',
        'corner-control-wrong-byte':'corner policy fault or restoration differs',
        'corner-control-unrestored':'corner policy fault or restoration differs',
        'corner-control-clock':'corner control clocks differ',
        'corner-control-registers':'corner control registers differ',
        'corner-control-address':'corner control policy address differs'}[fault]
    need(expected in reasons,'corner control copied fault failed for unrelated reason: '+fault)
