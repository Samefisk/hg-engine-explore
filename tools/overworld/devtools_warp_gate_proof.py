"""Five retained warp-gate rows and bounded copied-data controls."""
from copy import deepcopy
from .devtools_warp_gate_measurement import KIND,REQUIREMENT,replay,require

CLAIMS=('natural-input','live-actor-identity','logical-commit','world-transition','control-release')
LIFECYCLE=dict(started=1,finished=1,canceled=0,controlReturned=1,ordered=True,complete=True)
FAULTS=('warp-mid-teleport','warp-wrong-door','warp-missing-finish','warp-no-walk-input','warp-wrong-destination')


def contract():
    def fixed(name,value,typ='array'):
        return dict(name=name,operator='eq',type=typ,validator='meaningful-observation',expected=value)
    return {
        'natural-input':[dict(name='completed-input-route-steps',operator='eq',type='array',validator='completed-route-v1')],
        'live-actor-identity':[fixed('warp-gate-cyndaquil-identity',[1,'MOUNTED',155,1])],
        'logical-commit':[fixed('teleport-commit-deltas',[1,1])],
        'world-transition':[dict(name='normal-walk-warp-destination',operator='eq',type='object',validator='warp-destination-v1',
                                 requiredKeys=['sourceMap','destinationMap','door'])],
        'control-release':[fixed('teleport-lifecycle-counts',[deepcopy(LIFECYCLE),deepcopy(LIFECYCLE)])]}


def measurements(result,record):
    require(result.get('passed') is True and not result.get('failures'), 'warp replay failed')
    result=result.get('measurements',{}).get(KIND,result)
    require(result.get('passed') is True and result.get('closed') is True and result.get('acceptedProof') is False,
            'warp requires closed measurement')
    checked=replay(result)
    require(checked['passed'],'warp independent replay failed: '+str(checked['failures']))
    require(record.get('sessionCleanup')==dict(sessionId=record.get('sessionId'),closed=True,errors=[]),'warp session did not close')
    cases=checked['cases'];require(len(cases)==2,'warp requires two cases')
    values=[[3,3],[1,'MOUNTED',155,1],[(c['commitAfter']-c['commitBefore'])&0xffffffff for c in cases],
            dict(sourceMap=67,destinationMap=checked['destination'],door=checked['door']),[deepcopy(LIFECYCLE),deepcopy(LIFECYCLE)]]
    return [dict(claim=claim,name=rules[0]['name'],operator='eq',value=value,expected=deepcopy(value),passed=True) for (claim,rules),value in zip(contract().items(),values)]


def negative(result,fault):
    require(fault in FAULTS,'unknown warp fault');copy=deepcopy(result)
    if fault=='warp-wrong-door':copy['door']=[564,392];return copy
    restored=False
    for row in copy['journal']:
        if row['op']=='restore':restored=True
        if row['op']!='observe':continue
        snapshot=row['snapshot']
        if fault=='warp-mid-teleport' and not restored:snapshot['context']['mapId']=69;break
        if fault=='warp-no-walk-input' and restored:
            snapshot['selector'].update(heldKeys=0,rawHeld=0)
        if fault=='warp-wrong-destination' and snapshot['context'].get('mapId')!=67:snapshot['context']['mapId']=69
        if fault=='warp-missing-finish':
            for event in row['events']:
                if event.get('data',{}).get('event')=='MOTION_FINISHED':event['data']['event']='WORLD_EFFECT'
    return copy


def validate_negative_result(result,fault):
    require(fault in FAULTS,'unknown warp fault')
    reason={'warp-mid-teleport':'warp fired during Teleport','warp-wrong-door':'unknown warp door fixture',
            'warp-missing-finish':'missing/duplicate native MOTION_FINISHED',
            'warp-no-walk-input':'warp normal entry lacks UP input','warp-wrong-destination':'warp reached wrong destination'}[fault]
    failures=str(result.get('failures',[]))+str(result.get('measurements',{}).get(KIND,{}).get('failures',[]))
    require(result.get('passed') is False and (reason in failures or (fault=='warp-wrong-door' and 'loaded warp table does not match door' in failures)),'warp negative missed named failure')
    return True


class WarpGateNegative:
    def __init__(self,fault):
        require(fault in FAULTS,'unknown warp fault')
        self.fault=fault;self.applied=False;self.restored=False

    def mutate(self,row,subjects=None):
        if row.get('command')=='mount-teleport.restore':self.restored=True
        if self.applied and self.fault!='warp-no-walk-input':return row
        changed=deepcopy(row)
        if self.fault=='warp-wrong-door':
            receipt=changed.get('receipt',{})
            if changed.get('command')!='mount-teleport.configure' or not receipt.get('loadedWarps'):return row
            receipt['loadedWarps']=[];self.applied=True;return changed
        events=changed.get('events',[])
        if self.fault=='warp-missing-finish':
            event=next((e for e in events if e.get('data',{}).get('event')=='MOTION_FINISHED'),None)
            if event is None:return row
            event['data']['event']='WORLD_EFFECT';self.applied=True;return changed
        snapshots=([changed['snapshot']] if changed.get('snapshot') is not None else changed.get('samples',[]))
        for snapshot in snapshots:
            actor=next((a for a in snapshot.get('actors',[]) if a.get('species')==155 and a.get('role')=='MOUNTED'),None)
            if self.fault=='warp-mid-teleport' and actor and actor.get('motionKind')=='TELEPORT':
                snapshot['context']['mapId']=69
            elif self.fault=='warp-wrong-destination' and self.restored and snapshot.get('context',{}).get('mapId')==68:
                snapshot['context']['mapId']=69
            elif self.fault=='warp-no-walk-input' and self.restored and snapshot.get('context',{}).get('mapId')==67 \
                    and (snapshot.get('selector',{}).get('heldKeys',0)==64
                         or snapshot.get('selector',{}).get('rawHeld',0)==64):
                snapshot['selector'].update(heldKeys=0,rawHeld=0,physicalPressed=0)
            else:continue
            self.applied=True;return changed
        return row
