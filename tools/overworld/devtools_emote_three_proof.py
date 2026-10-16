"""S3 native three-emote claims and copied-evidence fault controls."""
from copy import deepcopy
import struct
from tools.overworld.devtools_emote_three_measurement import KIND, REQUIREMENT, need

CLAIMS=('live-actor-identity','feedback-effect','controlled-action')
NAMES=dict(zip(CLAIMS,('same-four-current-wild-object-bindings',
    'three-native-draw-models-own-independent-texture-palette-frames-and-quiet-sound',
    'same-actor-and-fourth-reject-then-once-only-drained-cleanup')))
FAULTS=('wrong-full-handle','wrong-slot','wrong-effect','fourth-admitted','same-actor-two-slots',
    'shared-texture-key','shared-palette-key','wrong-frame-destination','missing-native-draw',
    'missing-native-update','rejected-playse','missing-cleanup','early-retirement','missing-task',
    'wrong-native-code','wrong-bridge-entry')


def contract():
    return {claim:[dict(name=NAMES[claim],operator='eq',type='integer',
                       validator='meaningful-observation',expected=1)] for claim in CLAIMS}


def measurements(replay,record):
    value=replay.get('measurements',{}).get(KIND,{})
    need(replay.get('passed') is True and not replay.get('failures')
         and value.get('ready') is True and value.get('passed') is True and value.get('acceptedProof') is False
         and value.get('requirements')==[REQUIREMENT]
         and value.get('observedFrames')==replay.get('observedFrames')
         and value.get('observedFrameUnit')=='completed-game-frame'
         and 1<=value['observedFrames']<=240 and set(value.get('subjects',{}))==set('abcd'),
         'exact native burst proof missing')
    need(record.get('sessionCleanup')==dict(sessionId=record.get('sessionId'),closed=True,errors=[]),
         'owned emote session cleanup missing')
    return [dict(claim=c,name=NAMES[c],value=1,operator='eq',expected=1,passed=True) for c in CLAIMS]


def owner_word(value,index,word):
    raw=bytearray.fromhex(value['rawHex']);struct.pack_into('<I',raw,index*4,word);value['rawHex']=raw.hex()
    if index==5:value['retirementTask']=word
    elif index==1:value['activeCount']=word
    elif index>=7:
        name=('owner','object','effect','model','iconFile','animationFile','texture','textureKey','paletteKey','state')[(index-7)%10]
        value['slots'][(index-7)//10][name]=word


class EmoteThreeNegative:
    def __init__(self,fault):
        need(fault in FAULTS,'unknown copied emote fault');self.fault=fault;self.applied=False

    def mutate(self,row,subjects):
        changed=deepcopy(row)
        if self.applied:return changed
        if self.fault=='wrong-bridge-entry':
            if changed.get('command')=='emote-three.arm':
                changed['receipt']['calls'][1]['entryArguments'][0]^=4;self.applied=True
            return changed
        if changed.get('command')!='emote-three.close':return changed
        v=changed['receipt']['emotes'];f=self.fault
        if f=='wrong-full-handle':v['subjects']['a']['handle']['generation']+=1
        elif f in ('wrong-slot','wrong-effect'):
            binding=next(e['binding'] for e in v['events'] if e['kind']=='init')
            if f=='wrong-effect':binding['effect']^=4
            else:
                raw=bytearray.fromhex(binding['dataHex']);struct.pack_into('<I',raw,44,binding['slot']+40);binding['dataHex']=raw.hex()
        elif f=='fourth-admitted':v['requests'][4]['result']=v['requests'][0]['result']
        elif f in ('same-actor-two-slots','shared-texture-key','shared-palette-key'):
            key,index={'same-actor-two-slots':('object',18),'shared-texture-key':('textureKey',24),
                       'shared-palette-key':('paletteKey',25)}[f]
            owner_word(v['activeOwner'],index,v['activeOwner']['slots'][0][key])
        elif f=='wrong-frame-destination':
            b=v['draws'][0]['last']['binding'];raw=bytearray.fromhex(b['dataHex']);struct.pack_into('<I',raw,92,b['textureDestination']+512);b['dataHex']=raw.hex()
        elif f in ('missing-native-draw','missing-native-update'):v['draws' if f.endswith('draw') else 'updates'].pop()
        elif f=='rejected-playse':v['events'].append(deepcopy(next(e for e in v['events'] if e['kind']=='play')))
        elif f=='missing-cleanup':v['final']['bubble']=deepcopy(v['activeOwner'])
        elif f=='early-retirement':next(e for e in v['events'] if e['kind']=='release')['queue']['count']=1
        elif f=='missing-task':owner_word(v['activeOwner'],5,0)
        elif f=='wrong-native-code':v['baseline']['codeIdentity'][0]['sha256']='ff'*32
        self.applied=True;return changed


def validate_negative_result(result,fault):
    need(fault in FAULTS and result.get('passed') is False and result.get('failures'),
         'copied emote fault did not reject')
    need(any('emote' in str(e) for e in result['failures']), 'copied emote fault rejected for unrelated reason')
    return True
