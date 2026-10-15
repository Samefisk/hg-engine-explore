"""Six fixed quiet admissions, followed by passive native lifetime observations.

Only the existing FieldReturnBridge invokes the quiet entry. All other hooks
read registers/memory and retain bounded receipts; they never call guest code.
"""
from copy import deepcopy
import hashlib
import struct

from tools.overworld.devtools_emote_vram_diagnostics import (
    STOCK_SEALS, decode_emote_owner, observe_emote_vram_diagnostics)
from tools.overworld.devtools_records import select_current_actor

QUIET = (0x01FFF3B0, 34, '6bcdc6654759ee28e034fafb4ce2787c7d699f4a0e0b4cd93cdfd89e9f315fef')
EXTRA_SEALS = (
    (0x020205D8, 76, '2eafcbb790f66a15407db8d240e60bdfec8399e56527d6d386390dba0b2e3065', 'transfer'),
    (0x02020638, 28, '1e51a5923bec99a80e41e91973624dd3cc89987e3a8f417e35c6fcabb574f206', 'pending'),
    (0x0200604C, 32, '450aa068194ad9eb69d59218414b67d48aa21f6d96fc11a3c7e06bda9301675b', 'play'),
    (0x02006154, 8, '87f3539e18f621b73d09b3657c5c6ed6cf2f0f61710a80852e8780fabb778e0a', 'stop'),
    (0x021F16EC, 84, 'f65c466a47b92fee19509f24240115a27cdb5b17fc71ecdfac3cc2ddec26e412', 'model-constructor'),
    (0x02023A20, 128, '7f0e368df37887cb0b192d830a45d05d1e4be67f1a109ff80319f564e3915864', 'borrowed-model'),
    (0x021F1448, 8, 'df5277dbd8d95a7ae061b511ad12ba6efd5b819260e384fbe76a33bfdc3008cb', 'source-free'),
    (0x02023D44, 96, 'e13bfe1d71ffd3c31287e8ad9916e648991b2aeaf8d7ce195be9a8871df02228', 'model-pool-admission'),
)
NATIVE = {name: (address, size, digest) for address,size,digest,name in STOCK_SEALS + EXTRA_SEALS}
ORDER = (('a',0), ('a',1), ('b',1), ('c',2), ('d',3), ('c',3))
QUEUE_GLOBAL = 0x021D2194  # literal at sealed GF_Get...+0x18
EVENT_LIMIT = 2048
READ_LIMIT = 1024  # one callback; named code authentication is separate


def need(ok, reason):
    if not ok:
        raise ValueError('emote-three: ' + reason)


def current_owner(session, owner, context):
    return decode_emote_owner(owner, context, session.read(owner, 148))


class EmoteThreeProbe:
    def __init__(self, session, subjects):
        self.s = session
        need(set(subjects) == set('abcd'), 'four exact subjects required')
        snapshot = session._snapshot(0, details=False)
        self.subjects = {name: select_current_actor(snapshot, value) for name,value in subjects.items()}
        need(all(a['species'] == 155 and a['role'] == 'WILD' for a in self.subjects.values()),
             'four native Wild Cyndaquil required')
        self.objects = {name:a['engineIdentity']['pointer'] for name,a in self.subjects.items()}
        need(len(set(self.objects.values())) == 4, 'subjects share an object')
        self.field, self.heap = session.field_pointer(), session.native_heap_generation
        self.before = observe_emote_vram_diagnostics(session)
        need(self.before['known'], 'native VRAM baseline unavailable: ' + str(self.before.get('reason')))
        self.owner = self.before['bubble']['ownerPointer']; self.context = self.before['contextPointer']
        self.tokens = []; self.events = []; self.requests = []; self.live = {}; self.owned_slots = {}
        self.active = []; self.reads = 0; self.closed = False; self.trigger_done = False
        self.active_request=None; self.sequence=0
        self.start = self.clock(); self.update_counts = {}; self.draw_counts = {}; self.normal_start = None
        self.after = None; self.models_before = self.model_count(); self.models_after = None
        need(self.before['bubble']['activeCount'] == 0 and self.before['bubble']['retirementTask'] == 0
             and self.before['bubble']['closing'] == 0, 'unrelated active emote or closing owner')
        self.authenticate()

    def clock(self):
        return dict(frame=self.s.completed_frames, nativeCycle=self.s.rt.EXECUTED_FRAME_COUNT)

    def read(self, address, size):
        need(type(address) is int and address % 4 == 0 and 0x02000000 <= address <= 0x02400000-size,
             'native read span differs')
        self.reads += size; need(self.reads <= READ_LIMIT, 'callback read budget exceeded')
        raw = self.s.read(address, size); need(isinstance(raw,bytes) and len(raw)==size, 'short native read')
        return raw

    def word(self, address):
        return struct.unpack('<I', self.read(address,4))[0]

    def authenticate(self):
        for name,(address,size,digest) in NATIVE.items():
            need(hashlib.sha256(self.s.packaged_code(address,size)).hexdigest()==digest,
                 'native full body differs: '+name)
        need(hashlib.sha256(self.s.packaged_code(QUIET[0],QUIET[1])).hexdigest()==QUIET[2],
             'quiet full body differs')

    def model_count(self):
        self.reads = 0
        resources = self.word(self.context+0x20)
        manager = self.word(resources+0xC)
        capacity = self.word(manager+8)
        count = self.word(manager+0xD4)
        need(0 <= count <= capacity <= 64, 'native model pool count differs')
        return dict(resourcePointer=resources, managerPointer=manager, capacity=capacity, count=count)

    def pending(self):
        queue = self.word(QUEUE_GLOBAL)
        capacity,count,tasks = struct.unpack('<3I',self.read(queue,12))
        need(0 <= count < capacity <= 4096 and tasks and tasks%4==0, 'transfer queue differs')
        return dict(pointer=queue, capacity=capacity, count=count, tasks=tasks)

    def owner_now(self):
        need(self.s.field_pointer()==self.field and self.s.native_heap_generation==self.heap,
             'field or heap owner changed')
        return decode_emote_owner(self.owner,self.context,self.read(self.owner,148))

    def binding(self, effect, data_pointer):
        raw = self.read(data_pointer,104)
        words = struct.unpack('<26I',raw)
        slot = words[11]
        need(slot in (self.owner+28,self.owner+68,self.owner+108), 'native effect has wrong slot')
        slot_words = struct.unpack('<10I',self.read(slot,40))
        need((words[12],words[13],words[14],words[15]) ==
             (self.context,self.owner,slot_words[1],slot_words[3])
             and slot_words[0]==self.owner and slot_words[2]==effect and slot_words[9]==2,
             'native effect/model/object/slot differs')
        model = words[15]
        keys = struct.unpack('<3I', self.read(model+0x94,12))
        active = self.word(model+0xB4)&0xFF
        need(keys==(slot_words[7],0,slot_words[8]) and active==3,
             'native borrowed model key binding differs')
        need(words[20:25] == (slot_words[6],slot_words[5],slot_words[4],
              (slot_words[7]&0xFFFF)<<3,512), 'native frame assets/destination differ')
        name = next((name for name,obj in self.objects.items() if obj==words[14]),None)
        need(name is not None, 'effect object is not a full bound subject')
        return dict(subject=name, handle=deepcopy(self.subjects[name]['handle']), effect=effect,
            dataPointer=data_pointer, dataHex=raw.hex(), slot=slot, model=model,
            textureKey=keys[0],paletteKey=keys[2],textureDestination=words[23],
            paletteDestination=(keys[2]&0xFFFF)<<3,frameBytes=words[24],
            modelActive=active, modelKeys=list(keys), owner=self.owner, object=words[14])

    def owned_release_slot(self, pointer):
        """A slot address can be reused after the burst's own effect retires."""
        binding = self.owned_slots.get(pointer)
        if binding is None: return None
        raw = self.read(pointer, 40)
        words = struct.unpack('<10I', raw)
        need(words[0] == self.owner and words[2] == words[3] == 0 and words[9] == 3
             and words[1] % 4 == 0 and 0x02000000 <= words[1] < 0x02400000,
             'native retirement slot owner/state differs')
        # Assets/keys can also be reused. The original object's full identity is
        # checked in every completed snapshot; a different object is ambient.
        return raw if words[1] == binding['object'] else None

    def install(self):
        callbacks = {
            'OverworldEmoteSlots_Admit': 'admit', 'OverworldEmoteSlots_Initialize':'init',
            'OverworldEmoteSlots_Update':'update', 'stock draw':'draw',
            'OverworldEmoteSlots_Destroy':'destroy', 'OverworldEmoteSlots_Release':'release',
            'OverworldEmoteSlots_Collect':'collect', 'transfer':'transfer', 'play':'play', 'stop':'stop',
            'tex-free':'freeTexture', 'palette-free':'freePalette', 'resource-lookup-result':'unused',
        }
        # The resource lookup is already sealed, but it is not another probe.
        callbacks.pop('resource-lookup-result')
        for name,kind in callbacks.items():
            address,size,digest=NATIVE[name]
            def before(name=name,kind=kind,address=address,size=size,digest=digest):
                return self.enter(name,kind,address,size,digest)
            def after(value,kind=kind): return self.returned(kind,value)
            token=self.s.party_getter_hooks.observe_call(address,before,after)
            self.tokens.append(token)
        # Native owner Release invokes stock free twice for the two source files.
        # Full SDK body is verified from package and local stock source, not a prologue.
        address=0x021F1448;size=8
        code=self.s.packaged_code(address,size)
        need(hashlib.sha256(code).hexdigest()==NATIVE['source-free'][2],'native source-free full body differs')
        self.source_free_identity=dict(address=address,size=size,hex=code.hex())
        self.tokens.append(self.s.party_getter_hooks.observe_call(address,
            lambda:self.enter('source-free','freeSource',address,size,hashlib.sha256(code).hexdigest()),
            lambda value:self.returned('freeSource',value)))

    def enter(self,name,kind,address,size,digest):
        r=self.s.emu.memory.register_arm9
        release_raw = None
        # Ignore other field effects, sounds and transfers; scoped to one exact
        # active admission/lifetime or an exact slot/effect owned by this burst.
        if kind=='admit':
            if r.r1 not in self.objects.values(): return None
            need(len(self.requests)<6 and self.trigger_done is False, 'foreign/repeated admission')
        elif kind in ('init','transfer','play','stop'):
            if kind=='stop':
                if not self.active_request: return None
            elif not self.active: return None
        elif kind in ('update','draw','destroy'):
            if r.r0 not in self.live: return None
        elif kind=='collect':
            if r.r1!=self.owner:return None
        elif kind=='release':
            self.reads=0
            release_raw=self.owned_release_slot(r.r0)
            if release_raw is None:return None
        elif not self.active or self.active[-1]['kind']!='release':return None
        need(not self.closed and len(self.events)<EVENT_LIMIT, 'callback/event lifetime bound exceeded')
        need(hashlib.sha256(self.s.packaged_code(address,size)).hexdigest()==digest,
             'native callback owner changed: '+name)
        if release_raw is None:self.reads=0
        self.sequence+=1
        value=dict(kind=kind,sequence=self.sequence,entry=self.clock(),args=[r.r0,r.r1,r.r2,r.r3],caller=r.lr,
                   parent=self.active[-1]['kind'] if self.active else None)
        if kind=='stop':value['request']=self.active_request-1
        if kind=='admit':
            idx=len(self.requests);subject,icon=ORDER[idx]
            need((r.r0,r.r1,r.r2)==(self.context,self.objects[subject],icon), 'fixed admission args differ')
            value.update(request=idx,subject=subject,handle=deepcopy(self.subjects[subject]['handle']))
            self.requests.append(value)
        elif kind=='init':
            need(self.active[-1]['kind']=='admit', 'init not nested in exact admission')
            value.update(effect=r.r0,dataPointer=r.r1,request=self.active[-1]['request'])
        elif kind in ('update','draw'):
            value['binding']=self.binding(r.r0,r.r1)
        elif kind=='destroy':
            value.update(effect=r.r0,dataPointer=r.r1,binding=self.binding(r.r0,r.r1))
        elif kind=='transfer':
            value['queue']=self.pending()
        elif kind=='release':
            value['queue']=self.pending();value['slotHex']=release_raw.hex()
        elif kind=='collect':
            value['queue']=self.pending();value['ownerHex']=self.read(self.owner,148).hex()
        elif kind in ('freeTexture','freePalette','freeSource'):
            value['queue']=self.pending();value['slot']=self.active[-1]['args'][0]
        self.active.append(value)
        return value

    def returned(self,kind,value):
        need(self.active and self.active[-1] is value, 'native callback nesting differs')
        self.sequence+=1
        self.reads=0;value.update(returnSequence=self.sequence,returnClock=self.clock(),result=self.s.emu.memory.register_arm9.r0)
        if kind=='init' and value['result']:
            value['binding']=self.binding(value['effect'],value['dataPointer'])
            self.live[value['effect']]=value['binding']
            self.owned_slots[value['binding']['slot']]=deepcopy(value['binding'])
        elif kind=='destroy':
            self.live.pop(value['effect'])
        elif kind=='admit':
            value['ownerHex']=self.read(self.owner,148).hex()
        self.active.pop()
        if kind in ('update','draw'):
            table=self.update_counts if kind=='update' else self.draw_counts
            key=value['binding']['effect'];item=table.setdefault(key,dict(count=0,first=deepcopy(value),last=None))
            item['count']+=1;item['last']=deepcopy(value)
        elif kind!='collect' or any(struct.unpack('<37I',bytes.fromhex(value['ownerHex']))[i] for i in (16,26,36)):
            self.events.append(value)

    def recipe(self,_scratch,call):
        self.active_request=None
        for index,(name,icon) in enumerate(ORDER):
            self.active_request=index+1
            yield call('emote_quiet',(self.objects[name],icon))
            self.active_request=None
        need(len(self.requests)==6 and not self.active, 'six native returns missing')
        self.reads=0
        self.active_owner=self.owner_now()
        self.trigger_done=True;self.normal_start=self.clock()
        return dict(scope='six-fixed-native-quiet-admissions',acceptedProof=False)

    def completed_boundary(self):
        if self.trigger_done and not self.closed:
            need(self.s.completed_frames-self.normal_start['frame']<=240,'normal frame budget exceeded')
            self.reads=0;self.owner_now()

    def close(self, *, disposing=False):
        if self.closed:return
        try:
            if not disposing:
                need(self.trigger_done and not self.active,'unfinished native probe')
                self.after=observe_emote_vram_diagnostics(self.s)
                need(self.after['known'],'native VRAM cleanup unavailable')
                self.models_after=self.model_count()
        finally:
            for token in self.tokens:self.s.party_getter_hooks.remove(token)
            self.tokens=[];self.closed=True

    def result(self):
        return dict(schema='emote-three-slots-v1',acceptedProof=False,diagnosticOnly=True,
            subjects=deepcopy(self.subjects),fieldPointer=self.field,heapGeneration=self.heap,
            baseline=deepcopy(self.before),final=deepcopy(self.after),activeOwner=deepcopy(getattr(self,'active_owner',None)),
            requests=deepcopy(self.requests),events=deepcopy(self.events),
            updates=deepcopy(list(self.update_counts.values())),draws=deepcopy(list(self.draw_counts.values())),
            modelBefore=deepcopy(self.models_before),modelAfter=deepcopy(self.models_after),
            codeIdentity=[dict(address=a,size=n,sha256=h,name=name) for a,n,h,name in EXTRA_SEALS],
            quietIdentity=dict(address=QUIET[0],size=QUIET[1],sha256=QUIET[2]),
            normalStart=deepcopy(self.normal_start),end=self.clock(),closed=self.closed)
