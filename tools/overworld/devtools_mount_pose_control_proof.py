"""Controller rules for restored same-reader pose calibration only."""
from copy import deepcopy
from tools.overworld.devtools_mount_pose_control_measurement import KIND, validate_control

REQUIREMENT='shared.mounted-pose-recorder-control-v1'
RULES=(('live-actor-identity','bound-mounted-control-subject'),
       ('controlled-action','same-reader-pose-fault'),
       ('controlled-action','exact-pose-restoration'))
FAULTS=('mounted-pose-absent-subject','mounted-pose-stale-subject',
        'mounted-pose-missing-control','mounted-pose-wrong-byte',
        'mounted-pose-unrestored','mounted-pose-clock','mounted-pose-missing-completed-sample')


def contract():
    result={}
    for claim,name in RULES:
        result.setdefault(claim,[]).append(dict(name=name,operator='eq',type='integer',
            validator='meaningful-observation',expected=1))
    return result


def measurements(replay, record):
    meter=replay.get('measurements',{}).get(KIND,{})
    if replay.get('passed') is not True or replay.get('failures')!=[] or meter.get('passed') is not True \
            or meter.get('ready') is not True or meter.get('acceptedProof') is not False \
            or meter.get('failures')!=[] or type(meter.get('observedFrames')) is not int or meter['observedFrames']<1:
        raise ValueError('mounted pose calibration lacks complete replay')
    subject=meter.get('subject',{})
    if subject.get('species')!=155 or subject.get('role')!='MOUNTED' or meter['pose'].get('subject')!=subject:
        raise ValueError('mounted pose calibration has wrong subject')
    validate_control(meter['control'],meter['pose'])
    cleanup=meter.get('cleanup',{})
    reader=cleanup.get('mountPacing',{})
    if cleanup.get('closed') is not True or cleanup.get('advancedFrames')!=0 or cleanup.get('acceptedProof') is not False \
            or reader.get('closed') is not True or reader.get('failure') is not None \
            or reader.get('poseCalibration')!=meter['control'] or reader.get('latestCompletedPose')!=meter['pose']:
        raise ValueError('mounted pose calibration cleanup differs')
    if record.get('sessionCleanup')!=dict(sessionId=record.get('sessionId'),closed=True,errors=[]):
        raise ValueError('mounted pose calibration private session did not close')
    return [dict(claim=c,name=n,value=1,operator='eq',expected=1,passed=True) for c,n in RULES]


class MountedPoseControlNegative:
    def __init__(self,fault):
        if fault not in FAULTS:raise ValueError('unknown mounted pose fault')
        self.fault,self.applied=fault,False

    def mutate(self,row,subjects):
        if self.applied or row.get('phase')!='observe' or not subjects:return row
        result=deepcopy(row)
        handles={s['handle']['value'] for s in subjects.values()}
        for sample in result.get('samples',[]):
            actor=next((a for a in sample.get('actors',[]) if a.get('handle',{}).get('value') in handles),None)
            if actor and self.fault=='mounted-pose-absent-subject':sample['actors'].remove(actor);self.applied=True
            elif actor and self.fault=='mounted-pose-stale-subject':actor['authorityGeneration']+=1;self.applied=True
            elif self.fault=='mounted-pose-missing-completed-sample':sample.get('mountPacing',{}).pop('latestCompletedPose',None);self.applied=True
            if self.applied:break
        if result.get('command')=='mount-pacing.calibrate':
            receipt=result.get('receipt',{})
            control=receipt.get('mountedPoseControl')
            if self.fault=='mounted-pose-missing-control':receipt.pop('mountedPoseControl',None);self.applied=True
            elif control and self.fault in ('mounted-pose-wrong-byte','mounted-pose-unrestored','mounted-pose-clock'):
                if self.fault=='mounted-pose-wrong-byte':control['bad']=deepcopy(control['clean'])
                elif self.fault=='mounted-pose-unrestored':control['restored']=deepcopy(control['bad'])
                else:control['restoredClock']['nativeCycle']+=1
                self.applied=True
        return result if self.applied else row


def validate_negative_result(result,fault):
    if fault not in FAULTS or result.get('passed') is not False:raise ValueError('mounted pose copied fault did not fail')
    errors=result.get('failures',[])+result.get('measurements',{}).get(KIND,{}).get('failures',[])
    reasons={e.get(k) for e in errors for k in ('detail','message') if isinstance(e.get(k),str)}
    expected={'mounted-pose-absent-subject':'selected handle must name exactly one current active actor',
        'mounted-pose-stale-subject':'selected actor has a stale authorityGeneration',
        'mounted-pose-missing-control':'mounted pose control is missing or not restored',
        'mounted-pose-wrong-byte':'mounted pose fault or restoration differs',
        'mounted-pose-unrestored':'mounted pose fault or restoration differs',
        'mounted-pose-clock':'mounted pose control clocks differ',
        'mounted-pose-missing-completed-sample':"'latestCompletedPose'"}[fault]
    if expected not in reasons:raise ValueError('mounted pose copied fault failed for unrelated reason: '+fault)
