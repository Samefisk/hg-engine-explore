"""Exact accepted flow claims and copied faults for T82/T84."""
from copy import deepcopy
from tools.overworld.devtools_party_throw_flow_measurement import CASES,need

CLAIMS=('natural-input','live-actor-identity','profile-resolution','rendered-motion','control-release')
NAMES=('ordinary-notice-pursuit-and-throw','unchanged-party2-follower-and-current-cargo',
       'authored-trigger-cargo-and-native-profile','complete-native-projectile-arc-and-landing',
       'free-cargo-until-held-and-follower-resumes')


def requirement(feature):return CASES[feature]['requirement']
def claims(feature):return CLAIMS
def faults(feature):
    return ('wrong-owner','wrong-binding','early-held','bad-arc','missing-return','wrong-party','resource-limit','missing-target-mask','early-release','held-after-land','wrong-follow-return') \
        + (('frozen-cargo',) if CASES[feature]['cargo']=='mankey' else ())
def contract(feature):
    return {c:[dict(name=n,operator='eq',type='integer',validator='meaningful-observation',expected=1)]
            for c,n in zip(CLAIMS,NAMES)}


def measurements(feature,replay,record):
    m=replay.get('measurements',{}).get(feature,{})
    need(replay.get('passed') is True and replay.get('failures')==[] and m.get('passed') is True
        and m.get('ready') is True and m.get('closed') is True and m.get('acceptedProof') is False
        and m.get('requirements')==[requirement(feature)] and m.get('observedFrames',0)>=2
        and m.get('observedFrames')==replay.get('observedFrames') and m.get('queryReturns',0)>0
        and all(k in m.get('frames',{}) for k in ('claim','pickup','launch','released','landed','follow-start','follow-return'))
        and m['frames']['claim']<m['frames']['pickup']<m['frames']['launch']
            <=m['frames']['released']<=m['frames']['landed']
        and m['frames']['launch']<=m['frames']['follow-start']<m['frames']['follow-return']
        and m.get('claimFrames',0)>0 and m.get('partyIdentity') is not None,
        'full native party Throw flow is incomplete')
    if CASES[feature]['cargo']=='mankey':need(m.get('freeProgress') is True,'follower did not move while pursued')
    need(record.get('sessionCleanup')==dict(sessionId=record.get('sessionId'),closed=True,errors=[]),
         'party Throw private session did not close')
    return [dict(claim=c,name=n,value=1,operator='eq',expected=1,passed=True) for c,n in zip(CLAIMS,NAMES)]


class PartyThrowFlowNegative:
    def __init__(self,feature,fault):
        need(fault in faults(feature),'unknown copied flow fault')
        self.feature,self.fault,self.applied=feature,fault,False
        self.previous=None
        self.held=self.launched=False
        self.projectile_return_commit=None

    def mutate(self,row,subjects):
        if self.applied or row.get('phase')!='observe' or not row.get('samples'):return row
        value=deepcopy(row);case=CASES[self.feature]
        bound=subjects.get(case['cargo'])
        carrier=subjects.get(case['carrier'])
        if bound is None or carrier is None:return value
        for sample in value['samples']:
            actor=next((a for a in sample['actors'] if a.get('handle')==bound['handle']),None)
            if actor is None:continue
            targets=sample.get('pokemonCombat',{}).get('interactions',{}).get('throwState',{}).get('targets',[])
            code=targets[carrier['handle']['slot']] if len(targets)==10 else 0
            self.held |= bool(code&128)
            if not self.launched and self.held and code==0 and actor.get('motionKind')=='HOP':
                self.projectile_return_commit=actor['commitSequence']+1
                self.launched=True
            if self.fault=='wrong-owner':actor['handle']['encounterGeneration']+=1
            elif self.fault=='wrong-party':
                next(p for p in sample['party'] if p['slot']==2)['personality']+=1
            elif self.fault=='resource-limit':
                event=next((e for e in value.get('events',[]) if e.get('data',{}).get('observation')=='throw-cargo-query'
                    and e['data'].get('subject')==carrier['handle']),None)
                if event is None:continue
                event['data'].update(status='RESOURCE_LIMIT',returnValue=4)
            elif self.fault=='early-held':
                if not code or code&128:continue
                next(t for t in sample['pokemonCombat']['movementTimers'] if t['handle']==bound['handle'])['movementActorControlMode']=1
            elif self.fault=='wrong-binding':
                if not code:continue
                c=next(c for c in sample['pokemonCombat']['interactions']['carriers'] if c['handle']==carrier['handle'])
                c['bindings']['cargo']['target']['actor']['encounterGeneration']+=1
            elif self.fault=='frozen-cargo':
                if not code or code&128 or actor.get('motionPhase')!='MOVING':continue
                if self.previous is None:self.previous=deepcopy(actor);continue
                if actor.get('reservationId')!=self.previous.get('reservationId'):
                    self.previous=deepcopy(actor);continue
                for k in ('pos_x','pos_z'):actor['engineObject'][k]=self.previous['engineObject'][k]
            elif self.fault=='missing-target-mask':
                if not code or code&128:continue
                state=sample['pokemonCombat']['interactions']['throwState']
                state['targetMask'] &= ~(1<<bound['handle']['slot'])
                raw=bytearray.fromhex(state['rawHex']);raw[10:12]=state['targetMask'].to_bytes(2,'little');state['rawHex']=raw.hex()
            elif self.fault in ('early-release','held-after-land'):
                if not self.launched or code:continue
                motion=next(t['motion'] for t in sample['pokemonCombat']['targets'] if t['handle']==bound['handle'])
                returned=any(e.get('kind')=='native' and e.get('data',{}).get('actorHandle')==bound['handle']['value']
                    and e['data'].get('event')=='CONTROL_RETURNED' and e.get('frame')==sample['frame'] for e in value.get('events',[]))
                if self.fault=='early-release' and not 0<motion['elapsed']<motion['plan']['duration']:continue
                if self.fault=='held-after-land' and not returned:continue
                mode=int(self.fault=='held-after-land')
                next(t for t in sample['pokemonCombat']['movementTimers'] if t['handle']==bound['handle'])['movementActorControlMode']=mode
                state=sample['pokemonCombat']['interactions']['throwState'];bit=1<<bound['handle']['slot']
                state['targetMask']=(state['targetMask']|bit) if mode else (state['targetMask']&~bit)
                raw=bytearray.fromhex(state['rawHex']);raw[10:12]=state['targetMask'].to_bytes(2,'little');state['rawHex']=raw.hex()
            elif self.fault=='wrong-follow-return':
                if not self.launched:continue
                mankey=subjects['mankey']
                event=next((e for e in value.get('events',[]) if e.get('kind')=='native' and e.get('frame')==sample['frame']
                    and e.get('data',{}).get('actorHandle')==mankey['handle']['value'] and e['data'].get('event')=='CONTROL_RETURNED'
                    and (case['cargo']!='mankey'
                        or self.projectile_return_commit is not None
                        and e['data'].get('valueB',0)>self.projectile_return_commit)),None)
                if event is None:continue
                event['data']['valueB']+=1
            elif self.fault=='bad-arc':
                if not self.launched or code or actor.get('motionKind')!='HOP' or actor.get('motionPhase')!='MOVING':continue
                actor['engineObject']['unk88_y']+=4096
            elif self.fault=='missing-return':
                if not self.launched:continue
                event=next((e for e in value.get('events',[]) if e.get('kind')=='native'
                    and e.get('data',{}).get('actorHandle')==bound['handle']['value']
                    and e['data'].get('event')=='CONTROL_RETURNED' and e.get('frame')==sample['frame']),None)
                if event is None:continue
                value['events'].remove(event)
            self.applied=True;break
        return value


def validate_negative_result(feature,result,fault):
    expected={'wrong-owner':('current active actor',),'wrong-party':('unchanged living party2',),
        'wrong-binding':('raw binding target','wrong authored current'),
        'early-held':('selection took free Cargo control',),'frozen-cargo':('selection froze Cargo pose',),
        'bad-arc':('wrong actual projectile pose/arc',),'missing-return':('missing exact projectile terminal','projectile did not return control on time','semantic native sequence'),
        'missing-target-mask':('claimed Cargo lacks its exact target mask',),
        'early-release':('projectile released HELD before landing',),
        'held-after-land':('landed follower remains HELD after return',),
        'wrong-follow-return':('missing exact follow terminal',),
        'resource-limit':('Cargo search exhausted memory',)}
    need(fault in faults(feature) and result.get('passed') is False
        and any(s in str(result.get('failures',[])) for s in expected[fault]),
        'copied party Throw fault did not fail at its intended check: '+fault)
