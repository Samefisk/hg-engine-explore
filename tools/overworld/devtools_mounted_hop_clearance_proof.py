"""Current native Hop clearance claims and precise copied-data controls."""
from copy import deepcopy
import struct
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.devtools_mounted_hop_clearance_measurement import KIND,REQUIREMENT,ORIGIN,CANOPY,legal_plan,need

CLAIMS=('natural-input','live-actor-identity','profile-resolution','rendered-motion','logical-commit','control-release')
NAMES=dict(zip(CLAIMS,('normal-right-then-release-no-B','same-saved-mounted-party2-mankey',
    'normal-hop7-longhop1to6-canopy-jump-off','safe-native-hop-every-paired-pose',
    'one-real-commit-at-legal-selected-support','ordered-return-without-height-offset')))
FAULTS=('wrong-owner','wrong-profile','wrong-support','unsafe-plan','bad-height','dropped-frame','no-hop','missing-commit','missing-return','B-input')


def contract():
    return {c:[dict(name=NAMES[c],operator='eq',type='integer',validator='meaningful-observation',expected=1)] for c in CLAIMS}


def measurements(replay,record):
    r=replay.get('measurements',{}).get(KIND,{})
    hop=r.get('hop') or {};plan=hop.get('plan',{});release=r.get('release') or {}
    need(replay.get('passed') is True and replay.get('failures')==[] and r.get('passed') is True
        and r.get('ready') is True and r.get('acceptedProof') is False and r.get('requirements')==[REQUIREMENT]
        and r.get('observedFrames')==replay.get('observedFrames') and r.get('observedFrames',0)>=24
        and (r.get('subject',{}).get('species'),r.get('subject',{}).get('role'))==(56,'MOUNTED')
        and hop.get('actor')==r['subject'].get('handle') and plan.get('origin')==list(ORIGIN)
        and hop.get('safety')==legal_plan(plan)
        and [s['elapsed'] for s in hop.get('samples',[])]==list(range(1,plan['duration']+1))
        and [e['event'] for e in release.get('events',[])]==['LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED']
        and r.get('finalActor',{}).get('logical')==dict(zip(('x','y'),plan['target'])),
        'complete safe native Hop/commit/input return is missing')
    need(record.get('sessionCleanup')==dict(sessionId=record.get('sessionId'),closed=True,errors=[]),
        'owned Hop-clearance session cleanup is missing')
    return [dict(claim=c,name=NAMES[c],value=1,operator='eq',expected=1,passed=True) for c in CLAIMS]


class MountedHopClearanceNegative:
    def __init__(self,fault):
        need(fault in FAULTS,'unknown copied clearance control');self.fault,self.applied=fault,False

    def mutate(self,row,subjects):
        value=deepcopy(row)
        if self.applied:return value
        if self.fault=='wrong-support' and value.get('command')=='bind':
            cell=next(c for c in value['snapshot']['terrain']['cells'] if (c['x'],c['z'])==CANOPY[0])
            cell['surface']['surfaceId']=0xFFFF;self.applied=True;return value
        if value.get('phase')!='observe' or not value.get('samples'):return value
        for sample in value['samples']:
            actor=next(a for a in sample['actors'] if a.get('role')=='MOUNTED')
            if self.fault=='wrong-owner':actor['handle']['encounterGeneration']+=1
            elif self.fault=='wrong-profile':
                if actor['motionKind']!='HOP':continue
                profiles=[p for p in value.get('profileCache',{}).get('resolvedProfiles',[]) if p.get('fingerprint')==actor['behaviorFingerprint']]
                need(bool(profiles),'copied clearance control has no source profile')
                for profile in profiles:
                    raw=bytearray.fromhex(profile['resultHex']);raw[136]|=1;profile['resultHex']=raw.hex()
            elif self.fault=='unsafe-plan':
                if actor['motionKind']!='HOP':continue
                motion=next(t['motion'] for t in sample['pokemonCombat']['targets'] if t['handle']==actor['handle'])
                raw=bytearray.fromhex(motion['rawHex']);struct.pack_into('<hh',raw,12,564,375);struct.pack_into('<i',raw,20,0x10000);struct.pack_into('<H',raw,24,37);raw[29]=6;raw[30]=16
                motion.clear();motion.update(decode_motion(bytes(raw)))
                actor.update(target=dict(x=564,y=375),motionDuration=37)
            elif self.fault=='bad-height':
                if actor['motionKind']!='HOP':continue
                actor['engineObject']['pos_y']+=1;sample['player']['pos_y']+=1
            elif self.fault=='dropped-frame':value['samples'].remove(sample)
            elif self.fault=='no-hop':
                if actor['motionKind']!='HOP':continue
                actor['motionKind']='NONE'
            elif self.fault in ('missing-commit','missing-return'):
                name='LOGICAL_COMMIT' if self.fault=='missing-commit' else 'CONTROL_RETURNED'
                event=next((e for e in value.get('events',[]) if e.get('kind')=='native'
                    and e.get('data',{}).get('actorHandle')==actor['handle']['value'] and e['data'].get('event')==name),None)
                if event is None:continue
                value['events'].remove(event)
            elif self.fault=='B-input':sample['selector'].update(rawHeld=18,heldKeys=18)
            else:continue
            self.applied=True;break
        return value


def validate_negative_result(result,fault):
    expected={'wrong-owner':('exactly one current active actor',),
        'wrong-profile':('Jump off',),'wrong-support':('canopy footprint/support',),
        'unsafe-plan':('underpasses the crossed native canopy',),
        'bad-height':('apply its safe native arc/base',),'dropped-frame':('raw chunk has missing',),
        'no-hop':('native Hop/public motion kind',),'missing-commit':('semantic native sequence','ordered landed Hop'),
        'missing-return':('semantic native sequence','ordered landed Hop'),
        'B-input':('RIGHT-only/released input',)}
    need(fault in FAULTS and result.get('passed') is False
        and any(reason in str(result.get('failures',[])) for reason in expected[fault]),
        'copied clearance control did not reject its exact fault: '+str(fault))
