"""Independent bounded replay and copied-data controls for Teleport timing."""
from copy import deepcopy
from .devtools_mounted_teleport_matrix import CASES, KIND, REQUIREMENT, configuration, expected_visibility
from .devtools_mount_control_stress import require

CLAIMS=('natural-input','live-actor-identity','logical-commit','rendered-motion','frame-pacing','control-release')
FAULTS=('teleport-absent-subject','teleport-stale-subject','teleport-missing-first','teleport-wrong-visibility',
        'teleport-wrong-duration','teleport-missing-finish','teleport-config-state')


def contract():
    def row(name,type,validator='meaningful-observation',**kw):return dict(name=name,operator='eq',type=type,validator=validator,**kw)
    return {'natural-input':[row('started-input-case-count','integer',expected=10)],
        'live-actor-identity':[row('teleport-cyndaquil-identity','array',expected=[1,'MOUNTED',155,1])],
        'logical-commit':[row('commit-deltas','array',expected=[1]*10)],
        'rendered-motion':[row('render-endpoints','array','teleport-timing-matrix-v1',aspect='endpoints'),
                           row('visibility-sample-counts','array','teleport-timing-matrix-v1',aspect='visibility')],
        'frame-pacing':[row('elapsed-frame-sequences','array','teleport-timing-matrix-v1',aspect='elapsed')],
        'control-release':[row('settled-case-count','integer',expected=10)]}


def measurements(result, record=None):
    meter=result.get('measurements',{}).get(KIND,result)
    require(result.get('passed') is True and not result.get('failures') and meter.get('passed') is True
            and meter.get('closed') is True and meter.get('acceptedProof') is False
            and meter.get('contract')==REQUIREMENT,'Teleport proof is not complete')
    if record is not None:
        require(record.get('sessionCleanup')=={
            'sessionId':record.get('sessionId'),'closed':True,'errors':[]},
            'Teleport private session did not close cleanly')
    require(meter.get('ready') is True and meter.get('failures')==[]
            and meter.get('frames',0)<=meter.get('maxFrames',0)
            and len(meter.get('cases',[]))==10,
            'Teleport matrix replay is incomplete')
    rows=[]
    distances={'fixed':set(),'per_tile':set()}
    for index,case in enumerate(meter['cases']):
        motion=case['summary'];config=case['configuration']
        require(case['name']==CASES[index] and config==configuration(index),
                'Teleport case order or configuration differs')
        distance=sum(abs(a-b) for a,b in zip(motion['origin'],motion['target']))
        duration=config['teleportTime']*(distance if index>=5 else 1)
        elapsed=[sample['elapsed'] for sample in case['samples']]
        visibility=[sample['visible'] for sample in case['samples']]
        require(motion['kind']=='TELEPORT' and motion['duration']==duration
                and motion['commitAfter']==((motion['commitBefore']+1)&0xffffffff)
                and motion['motion']['terminalLogical']==motion['target']
                and elapsed==list(range(1,duration+1))
                and visibility==expected_visibility(index,duration),
                'Teleport compact matrix evidence differs')
        if index%5<4:distances['per_tile' if index>=5 else 'fixed'].add(distance)
        rows.append(dict(name=case['name'],start=motion['origin'],target=motion['target'],final=motion['motion']['terminalLogical'],
            perTile=case['name'].startswith('per_tile'),travelTime=config['teleportTime'],frames=motion['duration'],
            visibility=visibility,elapsed=elapsed))
    require(len(distances['fixed'])>=2,
            'fixed Teleport cases need two distances')
    require(any(distance>1 for distance in distances['per_tile']),
            'per-tile Teleport needs one non-unit distance')
    actual={'natural-input':[10],'live-actor-identity':[[1,'MOUNTED',155,1]],'logical-commit':[[1]*10],
            'rendered-motion':[rows,rows],'frame-pacing':[rows],'control-release':[10]}
    return [dict(claim=claim,name=spec['name'],operator='eq',value=deepcopy(value),expected=deepcopy(value),passed=True)
            for claim,specs in contract().items() for spec,value in zip(specs,actual[claim])]


class MountedTeleportMatrixNegative:
    def __init__(self,fault):
        require(fault in FAULTS,'unknown Teleport copied fault');self.fault=fault;self.applied=False

    def mutate(self,row,subjects=None):
        if self.applied:return row
        changed=deepcopy(row);snapshot=changed.get('snapshot');events=changed.get('events',[])
        if self.fault=='teleport-config-state':
            receipt=changed.get('receipt',{});value=receipt.get('value',receipt)
            if not value.get('completed'):return row
            raw=bytearray.fromhex(value['after']['mountStateHex']);raw[0]^=1;value['after']['mountStateHex']=raw.hex()
        elif self.fault=='teleport-missing-finish':
            finish=next((e for e in events if e.get('data',{}).get('event')=='MOTION_FINISHED'),None)
            if finish is None:return row
            finish['data']['event']='WORLD_EFFECT'
        elif snapshot is not None or changed.get('samples'):
            snapshots=([snapshot] if snapshot is not None else changed['samples'])
            snapshot=next((value for value in snapshots
                if any(actor.get('species')==155 and actor.get('motionKind')=='TELEPORT'
                       for actor in value.get('actors',[]))),None)
            if snapshot is None:return row
            actors=snapshot.get('actors',[]);actor=next((a for a in actors if a.get('species')==155),None)
            if actor is None or actor.get('motionKind')!='TELEPORT':return row
            if self.fault=='teleport-absent-subject':snapshot['actors']=[]
            elif self.fault=='teleport-stale-subject':actor['authorityGeneration']+=1
            elif self.fault=='teleport-missing-first':
                if actor['motionElapsed']!=1:return row
                actor['motionElapsed']=2
            elif self.fault=='teleport-wrong-duration':actor['motionDuration']+=1
            elif self.fault=='teleport-wrong-visibility':actor['engineObject'].pop('flags',None)
            elif self.fault=='teleport-missing-finish':return row
        else:return row
        self.applied=True;return changed


Negative=MountedTeleportMatrixNegative


def validate_negative_result(result,fault):
    require(fault in FAULTS and result.get('passed') is False,'Teleport copied control did not fail')
    failures=str(result.get('failures',[]))+str(result.get('measurements',{}).get(KIND,{}).get('failures',[]))
    expected={'teleport-absent-subject':'missing or duplicate mounted subject','teleport-stale-subject':'ownership changed',
        'teleport-missing-first':'missing first completed-frame sample','teleport-wrong-visibility':'visibility missing',
        'teleport-wrong-duration':'duration differs','teleport-missing-finish':'missing/duplicate native MOTION_FINISHED',
        'teleport-config-state':'configure changed unrelated state'}[fault]
    require(expected in failures,'Teleport copied control failed for unrelated reason')
