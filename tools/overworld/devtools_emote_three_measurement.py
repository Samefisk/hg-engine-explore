"""Independent raw-record rules for the native three-emote burst."""
from copy import deepcopy
import struct

from tools.overworld.devtools_emote_vram_diagnostics import STOCK_SEALS, decode_emote_owner
from tools.overworld.devtools_emote_three_probe import QUIET, EXTRA_SEALS, ORDER, need
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_actor_inspect_probe import ENGINE_OWNER_KEYS, GENERATION_KEYS
from tools.overworld.devtools_raw_chunk import validate_raw_chunk

KIND = 'emote-three-slots-v1'
REQUIREMENT = 'current.emote-three-slots'
SUBJECTS = [dict(id=name,species=155,role='WILD',acquire='spawn') for name in 'abcd']
SETUP = [('emote-tile', 'teleport', dict(map=33,x=585,z=407,facing=0))]
for name,(x,z) in zip('abcd',((584,402),(586,402),(584,405),(586,405))):
    SETUP.extend([('spawn-'+name,'spawn',dict(species=155,form=0,level=50,role='wild',x=x,z=z)),
                  ('bind-'+name,'bind',dict(subject=name))])
ACTIONS = [('six-quiet-requests','emote-three.arm',{n:n for n in 'abcd'}),
           ('ordinary-emote-lifetimes','step',dict(frames=240,keys=[])),
           ('drained-cleanup','emote-three.close',{})]


def same_subject(current, expected):
    need(all(current.get(k)==expected.get(k) for k in
             ("handle", "subjectIdentity", "species", "role", *GENERATION_KEYS))
         and current.get("identityVerified") is True
         and all(k in current.get("engineIdentity", {}) and k in expected.get("engineIdentity", {})
                 and current["engineIdentity"][k]==expected["engineIdentity"][k] for k in ENGINE_OWNER_KEYS),
         "full subject/engine owner differs")


def clock(value):
    need(isinstance(value,dict) and set(value)=={'frame','nativeCycle'}
         and all(type(x) is int and x>=0 for x in value.values()),'native clock differs')
    return value['frame'],value['nativeCycle']


def inside(child, parent):
    return parent['sequence']<child['sequence']<child['returnSequence']<parent['returnSequence']


def owner(value, context):
    decoded=decode_emote_owner(value['ownerPointer'],context,bytes.fromhex(value['rawHex']))
    need(value==decoded,'decoded owner differs from native bytes')
    return decoded


def binding(value, subjects, expected_owner):
    raw=bytes.fromhex(value['dataHex']);need(len(raw)==104,'native effect data size differs')
    words=struct.unpack('<26I',raw);subject=value['subject']
    need(subject in 'abc' and value['handle']==subjects[subject]['handle']
         and value['object']==subjects[subject]['engineIdentity']['pointer'],'full effect identity differs')
    slot=next((s for s in expected_owner['slots'] if s['object']==value['object']),None)
    need(slot is not None and slot['state']==2 and value['slot']==slot['pointer']
         and value['effect']==slot['effect'] and value['model']==slot['model']
         and (words[11],words[12],words[13],words[14],words[15])==
           (slot['pointer'],expected_owner['contextPointer'],expected_owner['ownerPointer'],slot['object'],slot['model'])
         and (value['textureKey'],value['paletteKey'])==(slot['textureKey'],slot['paletteKey'])
         and value['modelKeys']==[slot['textureKey'],0,slot['paletteKey']] and value['modelActive']==3,
         'effect/slot/model key binding differs')
    need(words[20:25]==(slot['texture'],slot['animationFile'],slot['iconFile'],
          (slot['textureKey']&0xFFFF)<<3,512)
         and value['textureDestination']==words[23] and value['frameBytes']==512
         and value['paletteDestination']==(slot['paletteKey']&0xFFFF)<<3,
         'per-slot frame destination differs')
    return slot


def scoped_cleanup_events(events, active):
    """Retain the burst's cleanup, allowing later use of the same native slots."""
    slots = {slot['pointer']: slot for slot in active['slots']}
    objects = {slot['object'] for slot in active['slots']}
    foreign = []
    for event in events:
        if event['kind'] != 'release': continue
        words = struct.unpack('<10I', bytes.fromhex(event['slotHex']))
        need(event['args'][0] in slots and words[0] == active['ownerPointer']
             and words[2] == words[3] == 0 and words[9] == 3
             and words[1] % 4 == 0 and 0x02000000 <= words[1] < 0x02400000,
             'native retirement slot owner/state differs')
        if words[1] not in objects: foreign.append(event)
    # Old retained recordings include ambient frees nested in these releases.
    # Do not discard a stray/duplicate own free or a child outside its release.
    return [event for event in events if event not in foreign and not (
        event['kind'] in ('freeTexture', 'freePalette', 'freeSource')
        and event.get('parent') == 'release'
        and any(event.get('slot') == release['args'][0] and inside(event, release)
                for release in foreign))]


def checked_burst(value, subjects, *, start=None, end=None):
    need(value['schema']=='emote-three-slots-v1' and value['acceptedProof'] is False
         and value['diagnosticOnly'] is True and set(value['subjects'])==set(subjects) and value['closed'] is True,
         'burst schema/subject/closed boundary differs')
    for name in subjects:same_subject(value['subjects'][name],subjects[name])
    baseline,final=value['baseline'],value['final']
    identity=[dict(name=name,address=a,size=n,sha256=h) for a,n,h,name in STOCK_SEALS]
    need(all(facts['known'] is True and facts['acceptedProof'] is False
             and facts['codeIdentity']==identity and facts['bytesRead']<=facts['readBudgetBytes']==24576
             for facts in (baseline,final)),'native reader code/byte budget differs')
    need((baseline['fieldPointer'],baseline['contextPointer'])==(final['fieldPointer'],final['contextPointer'])
         and baseline['fieldPointer']==value['fieldPointer'],'current field/context differs')
    context=baseline['contextPointer'];before=owner(baseline['bubble'],context);after=owner(final['bubble'],context)
    active=owner(value['activeOwner'],context)
    need(before['activeCount']==0 and before['retirementTask']==0
         and before['closing']==after['closing']==active['closing']==0
         and (before['ownerPointer'],before['modelFile'],before['animationFile'],before['texture'])==
             (after['ownerPointer'],after['modelFile'],after['animationFile'],after['texture']), 'cleanup/owner assets differ')
    need(active['activeCount']==3 and all(s['state']==2 for s in active['slots'])
         and {s['object'] for s in active['slots']}=={subjects[n]['engineIdentity']['pointer'] for n in 'abc'},
         'three independent active slots missing')
    need(not any(slot['state'] and slot['object'] in {s['object'] for s in active['slots']}
                 for slot in after['slots']), 'owned cleanup still active or retiring')
    need(value['codeIdentity']==[dict(address=a,size=n,sha256=h,name=name) for a,n,h,name in EXTRA_SEALS], 'native transfer/model/sound code identity differs')
    need(value['quietIdentity']==dict(address=QUIET[0],size=QUIET[1],sha256=QUIET[2]),'quiet native identity differs')
    requests=value['requests'];need(len(requests)==6,'six native admission returns missing')
    effects=[]
    for i,(row,(name,icon)) in enumerate(zip(requests,ORDER)):
        need(row['kind']=='admit' and row['request']==i and row['subject']==name
             and row['handle']==subjects[name]['handle'] and row['args'][:3]==
                 [context,subjects[name]['engineIdentity']['pointer'],icon],'fixed native admission arguments differ')
        accepted=i in (0,2,3)
        need((row['result']!=0)==accepted,'duplicate/fourth admission rule differs')
        if accepted:
            slot=next(s for s in active['slots'] if s['object']==row['args'][1])
            need(row['result']==slot['effect'],'actual native Admit return differs');effects.append(row['result'])
        raw=decode_emote_owner(active['ownerPointer'],context,bytes.fromhex(row['ownerHex']))
        need(raw['activeCount']==(1 if i<2 else 2 if i==2 else 3),'admission-time slot count differs')
        need(clock(row['entry'])<=clock(row['returnClock']),'native admission return precedes entry')
    need(len(set(effects))==3,'accepted effects alias')
    events=value['events'];need(isinstance(events,list) and len(events)<=2048,'native event bound differs')
    need(all(type(e.get('sequence')) is int and type(e.get('returnSequence')) is int
             and 0<e['sequence']<e['returnSequence'] for e in events+requests),
         'native callback entry/return sequence differs')
    scoped=scoped_cleanup_events(events,active)
    kinds={k:[e for e in scoped if e['kind']==k] for k in ('init','play','stop','transfer','release','freeTexture','freePalette','freeSource','destroy')}
    need(len(kinds['init'])==3 and {r['request'] for r in kinds['init']}=={0,2,3}
         and all(r['result']==1 for r in kinds['init']),'accepted native initialization missing')
    for row in kinds['init']:binding(row['binding'],subjects,active)
    need(len(kinds['play'])==3 and all(e['args'][0]==1501 and e['parent']=='init' for e in kinds['play'])
         and len(kinds['stop'])==6 and {e['request'] for e in kinds['stop']}==set(range(6))
         and all(e['args'][0]==1501 for e in kinds['stop']),
         'quiet sound sequence/rejected PlaySE differs')
    need(all(sum(inside(p,init) for init in kinds['init'])==1 for p in kinds['play']),
         'PlaySE not nested in one accepted init')
    transfers=kinds['transfer'];need(len(transfers)>=6 and all(e['result']==1 for e in transfers),'native transfer failed/missing')
    tex_destinations={(s['textureKey']&0xFFFF)<<3 for s in active['slots']}
    pal_destinations={(s['paletteKey']&0xFFFF)<<3 for s in active['slots']}
    need(len(tex_destinations)==len(pal_destinations)==3, 'native private VRAM destinations alias')
    need(all((e['args'][0],e['args'][3]) in ((0,512),(1,32))
             and e['args'][1] in (tex_destinations if e['args'][0]==0 else pal_destinations)
             and e['args'][2]!=0 for e in transfers), 'later native transfer destination differs')
    for slot in active['slots']:
        destinations={0:(slot['textureKey']&0xFFFF)<<3,1:(slot['paletteKey']&0xFFFF)<<3}
        init=next(e for e in kinds['init'] if e['effect']==slot['effect'])
        initial=[e for e in transfers if inside(e,init)]
        need(len(initial)==2 and [(e['args'][0],e['args'][1],e['args'][3]) for e in initial]==
             [(0,destinations[0],512),(1,destinations[1],32)]
             and all(e['args'][2]!=0 for e in initial),'independent initial texture/palette transfers differ')
    normal_start,normal_end=clock(value['normalStart']),clock(value['end'])
    need(0<normal_end[0]-normal_start[0]<=240 and normal_end[1]>=normal_start[1],
         'normal completed-update window differs')
    if start is not None:need(normal_start==clock(start),'normal starting boundary differs')
    if end is not None:need(normal_end==clock(end),'normal end boundary differs')
    for kind in ('updates','draws'):
        entries=value[kind];need(len(entries)==3,'native '+kind+' missing')
        need({e['first']['binding']['effect'] for e in entries}==set(effects),'native '+kind+' effect set differs')
        for entry in entries:
            need(type(entry['count']) is int and 1<=entry['count']<=240,'native '+kind+' count differs')
            for boundary in (entry['first'],entry['last']):binding(boundary['binding'],subjects,active)
            if kind=='draws':need(struct.unpack_from('<I',bytes.fromhex(entry['last']['binding']['dataHex']),16)[0]!=1,'native draw remains hidden')
            need(normal_start<=clock(entry['last']['entry'])<=clock(entry['last']['returnClock'])<=normal_end,
                 'native '+kind+' outside ordinary updates')
    releases=kinds['release'];need(len(releases)==3 and len(kinds['freeTexture'])==len(kinds['freePalette'])==3
        and len(kinds['freeSource'])==6 and len(kinds['destroy'])==3
        and {e['args'][0] for e in kinds['destroy']}==set(effects),'cleanup retire/release missing')
    for row in kinds['destroy']:binding(row['binding'],subjects,active)
    need({e['args'][0] for e in releases}=={s['pointer'] for s in active['slots']},'cleanup slot set differs')
    for release in releases:
        need(normal_start<=clock(release['entry'])<=clock(release['returnClock'])<=normal_end,
             'native cleanup outside ordinary updates')
        need(release['queue']['count']==0 and release['parent']=='collect','source/key retired before queue drain')
        words=struct.unpack('<10I',bytes.fromhex(release['slotHex']))
        slot=next(s for s in active['slots'] if s['pointer']==release['args'][0])
        destroy=next(e for e in kinds['destroy'] if e['args'][0]==slot['effect'])
        need(destroy['returnSequence']<release['sequence']
             and normal_start<=clock(destroy['entry'])<=clock(destroy['returnClock'])<=clock(release['entry']),
             'native release precedes exact effect retirement')
        need(words[9]==3 and words[2]==words[3]==0 and words[:2]==(slot['owner'],slot['object'])
             and words[4:9]==tuple(slot[k] for k in ('iconFile','animationFile','texture','textureKey','paletteKey')),
             'release before native retirement or wrong slot assets')
        children={k:[e for e in kinds[k] if e['slot']==release['args'][0]
                    and inside(e,release)]
                  for k in ('freeTexture','freePalette','freeSource')}
        need(len(children['freeTexture'])==len(children['freePalette'])==1
             and children['freeTexture'][0]['args'][0]==words[7]
             and children['freePalette'][0]['args'][0]==words[8]
             and len(children['freeSource'])==2 and {e['args'][0] for e in children['freeSource']}=={words[4],words[5]}
             and all(e['queue']['count']==0 for rows in children.values() for e in rows),
             'exact once-only native key/source cleanup differs')
        need(all(t['returnSequence']<release['sequence'] and clock(t['returnClock'])<=clock(release['entry']) for t in transfers
                 if t['args'][1] in ((words[7]&0xFFFF)<<3,(words[8]&0xFFFF)<<3)),
             'release precedes last queued transfer')
    model_before,model_after=value['modelBefore'],value['modelAfter']
    need(all(type(model[k]) is int and model[k] % 4 == 0
                 and 0x02000000 <= model[k] < 0x02400000
                 for model in (model_before,model_after) for k in ('resourcePointer','managerPointer'))
         and all(0 <= model['count'] <= model['capacity'] <= 64 for model in (model_before,model_after))
         and all(model_before[k] == model_after[k] for k in ('resourcePointer','managerPointer','capacity')),
         'native model manager owner/capacity differs')
    # Other field actors can allocate/retire models or emotes during normal play.
    # Their global model/VRAM totals remain diagnostics. The exact three borrowed
    # model retirements and once-only drained private frees above supply cleanup.
    return normal_end[0]-normal_start[0]


def checked_trigger(receipt, subjects):
    need(receipt.get("boundary") == "native-field-command-trampoline" and receipt.get("preparedOnly") is True
         and receipt.get("acceptedProof") is False and not receipt.get("fatal") and not receipt.get("error")
         and receipt.get("firstBadCheckpoint") is None and receipt.get("firstInvalidThreadSwitch") is None
         and receipt.get("nativeHeapAdaptation") == [], "native Bridge fault or foreign operation")
    trampoline,stack=receipt["trampoline"],receipt["stackOwnership"]
    address=trampoline["address"];sp=stack["callSp"]
    need(type(address) is int and address%4==0 and 0x02000000<=address<=0x02400000-1536
         and trampoline["bytes"]==1536 and trampoline["heapId"]==11
         and trampoline["lifetime"]=="field-system-heap11"
         and type(sp) is int and sp%8==0 and 0x02000000<=sp<0x02800000-32
         and stack["hostRestoredFrameBytes"]==0 and stack["nativeFrameBytes"]==80
         and stack["scratchBytes"]==268 and stack["thread"]["mode"]==31 and stack["thread"]["irqDepth"]==0
         and stack["thread"]["stackTop"]<sp<stack["thread"]["stackBottom"]-32,
         "native Bridge trampoline/stack owner differs")
    calls=receipt["calls"];need(len(calls)==6,"fixed Bridge call list differs")
    for call,(name,icon) in zip(calls,ORDER):
        need(call["routine"]=="emote_quiet" and call["address"]==QUIET[0]
             and call["requestedArguments"]==call["entryArguments"]==[subjects[name]["engineIdentity"]["pointer"],icon]
             and call["entryStack"]==sp and call["entryLink"]==address+0x4C
             and call["entryCpsr"]&0x3F==0x3F
             and call["entryBoundary"]=="native-trampoline-BLX-entry", "fixed Bridge entry differs")
    need(receipt["value"]==dict(scope="six-fixed-native-quiet-admissions",acceptedProof=False),
         "prepared trigger scope differs")


class EmoteThreeMeasurement:
    def __init__(self,test=None,**_):
        self.test=test;self.subjects={};self.before=None;self.latest=None;self.receipt=None
        self.failures=[];self.frames=0;self.closed=False;self.setup_count=0;self.action_count=0

    def observe_record(self,row,*,on_sample=None,full_report=True):
        if self.failures:return self.result()
        try:
            need(not self.closed,'closed measurement')
            if row.get('command') is not None:
                if row.get('phase')=='setup':
                    need(self.setup_count<len(SETUP) and
                         (row.get('action'),row['command'])==SETUP[self.setup_count][:2],
                         'fixed setup action/order differs')
                    self.setup_count+=1
                else:
                    need(self.setup_count==len(SETUP) and self.action_count<len(ACTIONS)
                         and row.get('phase')=='observe' and
                         (row.get('action'),row['command'])==ACTIONS[self.action_count][:2],
                         'fixed observed action/order differs')
                    self.action_count+=1
            if 'initialSnapshot' in row:
                need(self.latest is None,'duplicate initial boundary');self.latest=deepcopy(row['initialSnapshot'])
            elif row.get('command')=='bind':
                name=next(a['args']['subject'] for a in self.test['setup'] if a['id']==row['action'])
                need(name not in self.subjects,'duplicate bind')
                self.subjects[name]=select_current_actor(row['snapshot'],row['receipt']);self.latest=deepcopy(row['snapshot'])
            elif row.get('command')=='emote-three.arm':
                need(set(self.subjects)==set('abcd') and self.before is None,'missing binds/repeated arm')
                self.before=deepcopy(row['receipt']);self.latest=deepcopy(row['snapshot'])
                checked_trigger(self.before,self.subjects)
                for name in self.subjects:same_subject(self.before['emotes']['subjects'][name],self.subjects[name])
                need(clock(self.before['emotes']['normalStart'])==(self.latest['frame'],self.latest['nativeCycle']),
                     'prepared trigger credited ordinary work')
            elif row.get('command')=='emote-three.close':
                need(self.before is not None and self.receipt is None,'missing arm/repeated close')
                self.receipt=deepcopy(row['receipt']);value=self.receipt['emotes']
                need(row['snapshot']['frame']==self.latest['frame'] and row['snapshot']['nativeCycle']==self.latest['nativeCycle'],
                     'close advances ordinary clock')
                measured=checked_burst(value,self.subjects,start=self.before['emotes']['normalStart'],
                    end=dict(frame=self.latest['frame'],nativeCycle=self.latest['nativeCycle']))
                need(measured==self.frames==240,'native normal frame count differs')
            elif row.get('phase')=='setup':
                need(self.before is None and row.get('command') in ('teleport','spawn'), 'foreign setup action')
                self.latest=deepcopy(row['snapshot'])
            else:
                if self.action_count==1 and row.get('action')=='ordinary-emote-lifetimes':
                    self.action_count=2
                need(self.before is not None and self.receipt is None and row.get('phase')=='observe'
                     and self.action_count==2 and row.get('action')=='ordinary-emote-lifetimes',
                     'normal chunk outside burst')
                for sample,_events,_costs in validate_raw_chunk(row,self.latest):
                    need(sample['fieldAvailable'] is True,'field unavailable during burst')
                    for name,subject in self.subjects.items():
                        same_subject(select_current_actor(sample,subject),subject)
                    self.frames+=1;need(self.frames<=240,'normal frame bound exceeded')
                    self.latest=deepcopy(sample)
                    if on_sample is not None:on_sample(sample,self.frames)
        except (ValueError,KeyError,TypeError,AttributeError,IndexError,struct.error) as error:
            self.failures.append(dict(code='emote-three-invalid',detail=str(error)))
        return self.result()

    def result(self):
        ready=self.receipt is not None and self.action_count==len(ACTIONS) and not self.failures
        return dict(state='failed' if self.failures else 'passed' if ready else 'running',ready=ready,passed=ready,
            acceptedProof=False,failures=deepcopy(self.failures),observedFrames=self.frames,
            observedFrameUnit='completed-game-frame',requirements=[REQUIREMENT],subjects=deepcopy(self.subjects),
            burst=None if self.receipt is None else deepcopy(self.receipt['emotes']))

    def finish(self):
        if self.receipt is None and not self.failures:self.failures.append(dict(code='emote-three-missing',detail='native burst not closed'))
        self.closed=True;return self.result()
