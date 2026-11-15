"""Exact T83 claims and copied-data faults; controller grants acceptance."""
from copy import deepcopy
from tools.overworld.devtools_mount_airborne_measurement import KIND,REQUIREMENT,need

CLAIMS=('natural-input','live-actor-identity','rendered-motion','control-release')
NAMES=dict(zip(CLAIMS,('air-select-ignored-and-fresh-ground-select',
    'same-saved-party2-mankey-two-native-hops','two-accepted-hop-targets-and-native-poses',
    'no-delayed-toggle-and-one-landed-y-choice')))
FAULTS=('wrong-owner','air-control-lost','delayed-select','lost-y-choice','early-y-queue',
        'endpoint-rewind','repeat-y-queue','missing-finish','dropped-frame','changed-party')


def contract():
    return {c:[dict(name=NAMES[c],operator='eq',type='integer',validator='meaningful-observation',expected=1)] for c in CLAIMS}


def measurements(replay,record):
    r=replay.get('measurements',{}).get(KIND,{})
    flights=r.get('flights',[])
    need(replay.get('passed') is True and replay.get('failures')==[] and r.get('passed') is True
         and r.get('ready') is True and r.get('acceptedProof') is False and r.get('failures')==[]
         and r.get('requirements')==[REQUIREMENT] and r.get('observedFrames')==replay.get('observedFrames')
         and r.get('observedFrames',0)>=70 and len(flights)==2
         and all([s['elapsed'] for s in f.get('samples',[])]==list(range(1,f['plan']['duration']+1))
                 and f.get('release') for f in flights)
         and r.get('selectFrame',0)<flights[0]['release']['frame']<r.get('freshSelectFrame',0)
         and r.get('freshSelectFrame',0)<=r.get('dismountFrame',0)<r.get('remountFrame',0)
         and r.get('remountFrame',0)<r.get('yConfirmFrame',0)<flights[1]['release']['frame']
         and flights[1]['release']['frame']<=r.get('queueStartFrame',0)<=r.get('switched',{}).get('frame',0)
         and r.get('idleAfterSelect',0)>=8 and r.get('queueRises')==1 and r.get('noRepeatFrames')==24,
         'complete native Select-ignore/land/fresh-press/deferred-Y sequence is missing')
    need(record.get('sessionCleanup')==dict(sessionId=record.get('sessionId'),closed=True,errors=[]),
         'owned airborne-input session cleanup is missing')
    return [dict(claim=c,name=NAMES[c],value=1,operator='eq',expected=1,passed=True) for c in CLAIMS]


class MountAirborneNegative:
    def __init__(self,fault):
        need(fault in FAULTS,'unknown copied airborne-input fault')
        self.fault,self.applied=fault,False

    def mutate(self,row,subjects):
        del subjects
        value=deepcopy(row)
        if self.applied or value.get('phase')!='observe' or not value.get('samples'):return value
        action=value.get('action')
        for sample in value['samples']:
            actor=next((a for a in sample.get('actors',[]) if a.get('role')=='MOUNTED' and a.get('species')==56),None)
            if self.fault=='dropped-frame':value['samples'].remove(sample)
            elif self.fault=='changed-party':
                next(p for p in sample['party'] if p['slot']==2)['personality']^=1
            elif self.fault=='wrong-owner' and actor is not None:actor['handle']['generation']+=1
            elif self.fault=='air-control-lost' and action=='air-select' and actor is not None:actor['inputOwnership']=0
            elif self.fault=='delayed-select' and action=='land-without-delayed-toggle' and actor is not None and actor['motionKind']=='NONE':actor['inputOwnership']=0
            elif self.fault in ('lost-y-choice','early-y-queue') and action=='confirm-y-in-flight':
                sample['selector']['queue'].update(request=0,count=2 if self.fault=='early-y-queue' else 0)
            elif self.fault=='repeat-y-queue' and action=='verify-no-repeat':sample['selector']['queue']['count']=1
            elif self.fault=='endpoint-rewind' and action=='land-and-switch' and actor is not None and actor['motionElapsed']>=actor['motionDuration']:
                actor['engineObject']['pos_x']+=65536;sample['player']['pos_x']+=65536
            elif self.fault=='missing-finish':
                event=next((e for e in value.get('events',[]) if e.get('kind')=='native'
                            and e.get('data',{}).get('event')=='MOTION_FINISHED'
                            and e['data'].get('actorHandle')==(actor or {}).get('handle',{}).get('value')),None)
                if event is None:continue
                value['events'].remove(event)
            else:continue
            self.applied=True;break
        return value


def validate_negative_result(result,fault):
    reasons={
        'wrong-owner':('exactly one current active actor','identity','generation'),
        'air-control-lost':('current mount binding/input owner differs',),
        'delayed-select':('current mount binding/input owner differs','delayed dismount'),
        'lost-y-choice':('confirmed airborne Y choice was dropped','confirmed Y choice was lost'),
        'early-y-queue':('confirmed airborne Y choice was dropped','before landing'),
        'endpoint-rewind':('accepted target','rendered arc differs','landed mount retains'),
        'repeat-y-queue':('ran again after completion','queued more than once'),
        'missing-finish':('semantic native sequence','normal landed commit'),
        'dropped-frame':('raw chunk has missing',),
        'changed-party':('saved party identity changed',)}
    need(fault in FAULTS and result.get('passed') is False
         and any(text in str(result.get('failures',[])) for text in reasons[fault]),
         'copied airborne-input fault did not reject its intended defect: '+str(fault))
