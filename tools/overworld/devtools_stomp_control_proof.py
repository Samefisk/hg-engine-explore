"""Original two-case baseline plus terminal threshold-reader proof mapping."""
from copy import deepcopy

from tools.overworld.devtools_stomp_control_measurement import KIND, validate_control
from tools.overworld.devtools_stomp_contract import validate_stomp
from tools.overworld.devtools_stomp_control import BAD_THRESHOLD
from tools.overworld.devtools_stomp_proof import StompNegative, FAULTS as BASELINE_FAULTS
from tools.overworld.devtools_stomp_proof import validate_negative_result as validate_baseline_negative

REQUIREMENT='shared.stomp-recorder-control-v1'
RULES=(('live-actor-identity','bound-stomp-control-subject'),
    ('controlled-action','same-reader-threshold-fault'),('controlled-action','exact-threshold-restoration'))
CLAIMS=tuple(dict.fromkeys(c for c,_ in RULES))
CONTROL_FAULTS=('stomp-control-missing-control','stomp-control-wrong-byte','stomp-control-unrestored',
    'stomp-control-clock','stomp-control-registers','stomp-control-address','stomp-control-prior-policy',
    'stomp-control-missing-guard','stomp-control-cleared-latch')
FAULTS=(*BASELINE_FAULTS,*CONTROL_FAULTS)


def need(value,reason):
    if not value:raise ValueError(reason)


def contract():
    result={}
    for claim,name in RULES:
        result.setdefault(claim,[]).append(dict(name=name,operator='eq',type='integer',
            validator='meaningful-observation',expected=1))
    return result


def measurements(replay,record):
    meter=replay.get('measurements',{}).get(KIND,{})
    need(replay.get('passed') is True and replay.get('failures')==[]
        and all(meter.get(k) is True for k in ('passed','ready','closed'))
        and meter.get('acceptedProof') is False and meter.get('failures')==[],
        'stomp control lacks complete independent replay')
    natural=meter['natural']
    need(natural.get('ready') is True and natural.get('failures')==[] and natural.get('acceptedProof') is False
        and meter['subject']==natural['subject'] and meter['terminal']==natural['terminalSnapshot'],
        'stomp control lacks original complete baseline')
    baseline=validate_stomp(natural['cases'],natural['subject'],natural['terminalSnapshot'])
    need(baseline['proofEvidence']==natural['proofEvidence'],'stomp control baseline summary differs')
    validate_control(meter['control'],natural['cases'][-1]['feedback']['calls'][-1],meter['terminal'],meter['subject'])
    calibration=meter['calibrationReceipt'];cleanup=meter['cleanup'];reader=cleanup['stompFeedback']
    need(calibration.get('terminalGuard') is True and calibration.get('advancedFrames')==0
        and calibration.get('acceptedProof') is False and calibration.get('prepared') is True
        and calibration.get('calibration')==meter['control'],'stomp control runtime guard differs')
    need(cleanup.get('closed') is True and cleanup.get('advancedFrames')==0 and cleanup.get('acceptedProof') is False
        and reader==calibration['stompFeedback'] and reader.get('armed') is True and reader.get('closed') is True
        and reader.get('failure')==BAD_THRESHOLD and reader.get('guestMemoryWrites')==2
        and reader.get('calibration')==meter['control'] and reader.get('subject')==meter['subject'],
        'stomp control terminal reader differs')
    for receipt in (calibration,cleanup):
        need(all(receipt['snapshot'].get(k)==meter['terminal'].get(k) for k in
            ('frame','actorFrame','nativeCycle','actors','player','context','selector')),
            'stomp control terminal snapshot differs')
    need(record.get('sessionCleanup')==dict(sessionId=record.get('sessionId'),closed=True,errors=[]),
        'stomp control private session did not close')
    return [dict(claim=c,name=n,value=1,expected=1,operator='eq',passed=True) for c,n in RULES]


class StompControlNegative:
    def __init__(self,fault):
        need(fault in FAULTS,'unknown stomp control copied fault')
        self.fault,self.applied=fault,False
        self.baseline=StompNegative(fault) if fault in BASELINE_FAULTS else None
    def mutate(self,row,subjects):
        if self.baseline:
            changed=self.baseline.mutate(row,subjects);self.applied=self.baseline.applied;return changed
        if self.applied or row.get('command')!='stomp.calibrate':return row
        changed=deepcopy(row);receipt=changed.get('receipt',{});control=receipt.get('calibration')
        if self.fault=='stomp-control-missing-guard':receipt['terminalGuard']=False;self.applied=True
        elif self.fault=='stomp-control-missing-control':receipt.pop('calibration',None);self.applied=True
        elif isinstance(control,dict):
            if self.fault=='stomp-control-wrong-byte':control['bad']['mountStateHex']=control['clean']['mountStateHex']
            elif self.fault=='stomp-control-unrestored':control['restored']['mountStateHex']=control['bad']['mountStateHex']
            elif self.fault=='stomp-control-clock':control['restoredClock']['nativeCycle']+=1
            elif self.fault=='stomp-control-registers':control['restoredRegisters']['r0']^=1
            elif self.fault=='stomp-control-address':control['changedAddress']+=1
            elif self.fault=='stomp-control-prior-policy':control['policyReceipt']['stompTime']+=1
            elif self.fault=='stomp-control-cleared-latch':control['readerFailure']=None
            self.applied=True
        return changed if self.applied else row


def validate_negative_result(result,fault):
    if fault in BASELINE_FAULTS:
        from tools.overworld.devtools_stomp_proof import KIND as BASELINE_KIND
        copied=deepcopy(result);meter=copied.get('measurements',{}).get(KIND,{})
        baseline=deepcopy(meter.get('natural',meter))
        baseline['failures']=list(dict.fromkeys(baseline.get('failures',[])+meter.get('failures',[])))
        copied.setdefault('measurements',{})[BASELINE_KIND]=baseline
        return validate_baseline_negative(copied,fault)
    need(fault in CONTROL_FAULTS and result.get('passed') is False,'stomp control copied fault did not fail')
    reasons=set()
    for failure in result.get('failures',[])+result.get('measurements',{}).get(KIND,{}).get('failures',[]):
        if isinstance(failure,str):reasons.add(failure)
        elif isinstance(failure,dict):
            reasons.update(failure[k] for k in ('detail','message') if isinstance(failure.get(k),str))
    expected={
        'stomp-control-missing-control':'is missing, not restored, or not terminal',
        'stomp-control-wrong-byte':'threshold fault or restoration differs',
        'stomp-control-unrestored':'threshold fault or restoration differs',
        'stomp-control-clock':'clocks differ','stomp-control-registers':'registers differ',
        'stomp-control-address':'address differs','stomp-control-prior-policy':'lacks matching native policy call',
        'stomp-control-missing-guard':'runtime terminal guard or boundary differs',
        'stomp-control-cleared-latch':'is missing, not restored, or not terminal'}[fault]
    need('stomp control '+expected in reasons,'stomp control copied fault failed for unrelated reason: '+fault)
