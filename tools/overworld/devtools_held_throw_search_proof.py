"""Exactly one valid held search followed by its normal line, windup and launch."""
from copy import deepcopy
import struct
from tools.overworld.devtools_held_throw_search_measurement import KIND, REQUIREMENT, need, POSITION

NAMES={'live-actor-identity':('same-current-carrier-cargo-and-player-trigger',),
       'natural-input':('normal-select-fence-exit-and-line-opening',),
       'engine-boundary':('201-held-search-frames-without-line', 'accepted-current-cargo-throw-start', 'authored-windup-and-recovery')}
CLAIMS=tuple(NAMES)
FAULTS=('stale-trigger','premature-recovery','missing-position','false-line','wrong-aim','missing-start','missing-flight-protection','wrong-windup')

def contract():
    return {c:[dict(name=n,operator='eq',type='integer',validator='meaningful-observation',expected=1) for n in ns] for c,ns in NAMES.items()}

def measurements(replay,record):
    result=replay.get('measurements',{}).get(KIND,{})
    need(replay.get('passed') is True and result.get('ready') is True and result.get('passed') is True
         and not result.get('failures') and result.get('continuousHeldFrames',0)>=201
         and result.get('heldEnd',0)-result.get('heldStart',0)==result['continuousHeldFrames']-1
         and result.get('positionProfile') and result.get('gardenEscape')
         and result.get('windupTimer',{}).get('start')==20
         and result.get('launch',{}).get('frame',0)>result.get('windup',{}).get('frame',0)
         and result.get('observedFrames')==replay.get('observedFrames')
         and result.get('observedFrameUnit')=='completed-game-frame'
         and set(result.get('subjects',{}))=={'geodude','mareep','stantler'},'required exact held-search result missing')
    need(record.get('sessionCleanup')==dict(sessionId=record.get('sessionId'),closed=True,errors=[]),'owned cleanup missing')
    return [dict(claim=c,name=n,value=1,operator='eq',expected=1,passed=True) for c,ns in NAMES.items() for n in ns]

class HeldThrowSearchNegative:
    def __init__(self,fault):
        need(fault in FAULTS,'unknown copied fault');self.fault=fault;self.applied=False
    def mutate(self,row,subjects):
        if row.get('phase')!='observe':return row
        changed=deepcopy(row);geo=subjects['geodude']['handle'];cargo=subjects['mareep']['handle']
        if self.fault=='missing-start':
            for e in list(changed.get('events',[])):
                if e.get('kind')=='native' and e.get('data',{}).get('event')=='MOTION_STARTED' and e['data'].get('actorHandle')==cargo['value']:
                    changed['events'].remove(e);self.applied=True
        for sample in changed.get('samples',[]):
            rows=sample.get('pokemonCombat',{}).get('interactions',{}).get('carriers',[])
            carrier=next((r for r in rows if r.get('handle')==geo),None)
            if carrier is None:continue
            held=row.get('action')=='hold-without-line'
            if held and self.fault=='stale-trigger':carrier['bindings']['trigger']['targetCurrent']=False;self.applied=True
            if held and self.fault=='premature-recovery':
                throw=sample['pokemonCombat']['interactions']['throwState'];throw['recoveringMask']|=1<<geo['slot']
                raw=bytearray.fromhex(throw['rawHex']);struct.pack_into('<H',raw,14,throw['recoveringMask']);throw['rawHex']=raw.hex();carrier['throw']['recovering']=True;self.applied=True
            if held and self.fault=='missing-position':
                next(a for a in sample['actors'] if a['handle']==geo)['matchedLayerMask']&=~POSITION;self.applied=True
            if held and self.fault=='false-line':sample['player']['y']=395;self.applied=True
            if carrier['throw']['windup'] and self.fault=='wrong-windup':
                next(t for t in sample['pokemonCombat']['movementTimers'] if t['handle']==geo)['movementCooldown']+=1;self.applied=True
            if carrier['throw']['recovering'] and carrier['throw']['targetRaw']==0:
                if self.fault=='missing-flight-protection':
                    throw=sample['pokemonCombat']['interactions']['throwState'];throw['targetMask']&=~(1<<cargo['slot'])
                    raw=bytearray.fromhex(throw['rawHex']);struct.pack_into('<H',raw,10,throw['targetMask']);throw['rawHex']=raw.hex();self.applied=True
                if self.fault=='wrong-aim':
                    motion=next(h for h in sample['pokemonCombat']['targets'] if h['handle']==cargo)['motion']
                    raw=bytearray.fromhex(motion['rawHex']);x=motion['plan']['target'][0]+1;struct.pack_into('<h',raw,12,x);motion['rawHex']=raw.hex();motion['plan']['target'][0]=x
                    next(a for a in sample['actors'] if a['handle']==cargo)['target']['x']=x;self.applied=True
        return changed

def validate_negative_result(result,fault):
    need(fault in FAULTS and result.get('passed') is False and result.get('failures'),'copied fault did not reject')
    expected={'stale-trigger':'binding identity', 'premature-recovery':'recovery before release',
              'missing-position':'Find Position', 'false-line':'real line', 'wrong-aim':'accepted native Cargo Throw START',
              'missing-start':'accepted native Cargo Throw START', 'missing-flight-protection':'accepted native Cargo Throw START',
              'wrong-windup':'authored countdown'}[fault]
    errors=result.get('measurements',{}).get(KIND,{}).get('failures',result.get('failures',[]))
    need(any(expected in str(e) for e in errors),'copied fault rejected at another guard')
