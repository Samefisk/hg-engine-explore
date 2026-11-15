"""Bounded adjacent-tree Hop claims and copied-data rejection controls."""
from copy import deepcopy
from tools.overworld.devtools_mounted_canopy_hop_measurement import KIND,REQUIREMENT,ORIGIN,TARGET,OFFSET,need

CLAIMS=('natural-input','live-actor-identity','profile-resolution','rendered-motion','logical-commit','control-release')
NAMES=dict(zip(CLAIMS,('normal-right-then-release-no-B','same-current-mounted-party2-mankey',
    'normal-hop-longhop-canopy-permission','native-adjacent-raised-hop-full-arc',
    'one-real-commit-at-exact-adjacent-canopy','ordered-return-and-exact-mounted-pair-height')))
FAULTS=('wrong-owner','wrong-profile','wrong-support','bad-height','dropped-frame','no-hop','missing-commit','missing-return','B-input')


def contract():
    return {c:[dict(name=NAMES[c],operator='eq',type='integer',validator='meaningful-observation',expected=1)] for c in CLAIMS}


def measurements(replay,record):
    result=replay.get('measurements',{}).get(KIND,{})
    hop=result.get('hop') or {};plan=hop.get('plan',{});release=result.get('release') or {}
    need(replay.get('passed') is True and replay.get('failures')==[] and result.get('passed') is True
         and result.get('ready') is True and result.get('acceptedProof') is False
         and result.get('requirements')==[REQUIREMENT]
         and result.get('observedFrames')==replay.get('observedFrames') and result.get('observedFrames',0)>=24
         and result.get('subject',{}).get('species')==56 and result['subject'].get('role')=='MOUNTED'
         and hop.get('actor')==result['subject'].get('handle') and plan.get('origin')==list(ORIGIN)
         and plan.get('target')==list(TARGET) and plan.get('distance')==1
         and plan.get('targetBaseY')==plan.get('startBaseY',-OFFSET)+OFFSET
         and [s['elapsed'] for s in hop.get('samples',[])]==list(range(1,plan.get('duration',-1)+1))
         and [e['event'] for e in release.get('events',[])]==['LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED']
         and result.get('finalActor',{}).get('logical')==dict(zip(('x','y'),TARGET)),
         'complete exact adjacent-canopy native Hop/input return is missing')
    need(record.get('sessionCleanup')==dict(sessionId=record.get('sessionId'),closed=True,errors=[]),
         'owned canopy session cleanup is missing')
    return [dict(claim=c,name=NAMES[c],value=1,operator='eq',expected=1,passed=True) for c in CLAIMS]


class MountedCanopyHopNegative:
    def __init__(self,fault):
        need(fault in FAULTS,'unknown copied canopy control')
        self.fault,self.applied=fault,False

    def mutate(self,row,subjects):
        value=deepcopy(row)
        if self.applied:return value
        if self.fault=='wrong-support' and value.get('command')=='bind':
            cell=next(c for c in value['snapshot']['terrain']['cells'] if (c['x'],c['z'])==TARGET)
            cell['surface']['surfaceId']=0xFFFF;self.applied=True;return value
        if value.get('phase')!='observe' or not value.get('samples'):return value
        for sample in value['samples']:
            actor=next(a for a in sample['actors'] if a.get('role')=='MOUNTED')
            if self.fault=='wrong-owner':actor['handle']['encounterGeneration']+=1
            elif self.fault=='wrong-profile':
                if actor['motionKind']!='HOP':continue
                rows=[p for p in value.get('profileCache',{}).get('resolvedProfiles',[]) if p.get('fingerprint')==actor['behaviorFingerprint']]
                need(bool(rows),'copied control has no matching profile')
                for profile in rows:
                    raw=bytearray.fromhex(profile['resultHex']);raw[92]=1;profile['resultHex']=raw.hex()
            elif self.fault=='bad-height':
                if actor['motionKind']!='HOP':continue
                actor['engineObject']['pos_y']+=1;sample['player']['pos_y']+=1
            elif self.fault=='dropped-frame':value['samples'].remove(sample)
            elif self.fault=='no-hop':
                if actor['motionKind']!='HOP':continue
                actor['motionKind']='NONE'
            elif self.fault in ('missing-commit','missing-return'):
                name='LOGICAL_COMMIT' if self.fault=='missing-commit' else 'CONTROL_RETURNED'
                owner=actor['handle']['value']
                event=next((e for e in value.get('events',[]) if e.get('kind')=='native'
                    and e.get('data',{}).get('actorHandle')==owner and e['data'].get('event')==name),None)
                if event is None:continue
                value['events'].remove(event)
            elif self.fault=='B-input':sample['selector'].update(rawHeld=18,heldKeys=18)
            else:continue
            self.applied=True;break
        return value


def validate_negative_result(result,fault):
    expected={'wrong-owner':('exactly one current active actor',),
        'wrong-profile':('normal Hop/LongHop',),'wrong-support':('tree footprint/support',),
        'bad-height':('rendered arc/native base',),'dropped-frame':('raw chunk has missing',),
        'no-hop':('native Hop/public motion kind',),'missing-commit':('semantic native sequence','ordered normal commit'),
        'missing-return':('semantic native sequence','ordered normal commit'),
        'B-input':('RIGHT-only/released input',)}
    need(fault in FAULTS and result.get('passed') is False
         and any(reason in str(result.get('failures',[])) for reason in expected[fault]),
         'copied canopy control did not reject its exact fault: '+str(fault))
