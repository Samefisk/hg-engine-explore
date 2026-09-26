"""Scoped native mounted feedback receipts; memory-only and never acceptance."""
from copy import deepcopy
import struct

from tools.overworld.devtools_mount_pacing_observer import NativeMountedPacingObserver
from tools.overworld.devtools_corner_observer import NativeCornerObserver
from tools.overworld.devtools_observer import public_bytes

# Vanilla named boundaries; full bodies are checked against the ROM, not only
# their prologues. overlay_01_021FF6B0.s, overlay_01_021F1348.s,
# unk_02005D10.s. Descriptor is data, not executable code.
STOCK = {'dust':(0x021FF74C,0x64,True), 'allocate':(0x021F1620,0x20,True),
         'init':(0x021FF7B0,0x44,True), 'sound':(0x0200604C,0x20,False),
         'soundStart':(0x020060BC,0x5C,False), 'descriptor':(0x022091EC,20,True)}
KINDS=('policy','dust','allocate','init','sound','soundStart')
SOUND_ID=1606


class NativeStompObserver(NativeMountedPacingObserver):
    def __init__(self,session,subject,max_frames):
        super().__init__(session,subject,max_frames)
        self.counts=dict.fromkeys(KINDS,0);self.code={};self.active=[]
        self.latest=None;self.linked=self._linked_feedback
        self.calibration=None;self.player_step_count=0

    def _linked_feedback(self,label,path,symbols,name,before,after,**kwargs):
        address,expected=self.code[name]
        self.observer._tap(label,address,self.session.packaged_code(address,32),before,after,**kwargs)

    def _authenticate(self):
        from tools.overworld.devtools_runtime import _elf_function_extent
        s,rt=self.session,self.session.rt
        path=rt.REPO/'build/overworld_mount_overlay_linked.o'
        address,size=_elf_function_extent(path,'OverworldMount_ApplyWalkPolicyOutput')
        expected=self.observer.elf_code(path,address,size)
        self._require(len(expected)==size and s.packaged_code(address,size)==expected,'full mounted feedback code differs')
        self.code['policy']=(address,expected)
        address,size=_elf_function_extent(path,'OverworldMount_PlayerStepBridge')
        expected=self.observer.elf_code(path,address,size)
        self._require(len(expected)==size and s.packaged_code(address,size)==expected,'full mounted step code differs')
        self.code['playerStep']=(address,expected)
        self.mount_state=rt.linked_symbol(rt.MOUNT_SYMBOLS,'sOverworldMountState')
        overlay=(rt.REPO/'base/overlay/overlay_0001.bin').read_bytes()
        table=(rt.REPO/'base/overarm9.bin').read_bytes()
        base=struct.unpack_from('<I',table,32+4)[0]
        arm9=(rt.REPO/'base/arm9.bin').read_bytes()
        for name,(address,size,is_overlay) in STOCK.items():
            blob,origin=(overlay,base) if is_overlay else (arm9,0x02000000)
            expected=blob[address-origin:address-origin+size]
            self._require(len(expected)==size and s.packaged_code(address,size)==expected,'full stock feedback code differs: '+name)
            self.code[name]=(address,expected)
        descriptor=struct.unpack('<5I',self.code['descriptor'][1])
        self._require(descriptor==(36,0x021FF7B1,0x021FF7F5,0x021FF801,0x021FF831),'dust callback descriptor differs')
        self._live_code()

    def _live_code(self):
        for name,(address,expected) in self.code.items():
            self._require(self.session.read(address,len(expected))==expected,'live feedback code differs: '+name)

    def arm(self):
        self._require(not self.armed and not self.closed and type(self.maximum) is int and 1<=self.maximum<=3000,
                      'invalid stomp arm or frame bound')
        s=self.session
        self._require(s.emu is not None and not s.native_bridge_active
            and s.rom.resolve().is_relative_to(s.directory.resolve())
            and s.rom.resolve()!=(s.rt.REPO/'test.nds').resolve(),'stomp requires an owned private session')
        self.started=self.session.completed_frames
        try:
            self.owner=self._current()
            self._require(self.owner['publicSubject']['species']==155,'stomp requires mounted Cyndaquil')
            self._authenticate();self.armed=True
            for kind in KINDS:
                self._install('stomp-'+kind,kind,lambda kind=kind:self._entry(kind),self._returned)
            self._install('stomp-playerStep','playerStep',self._step_before,self._step_after)
        except Exception as error:
            self.failure=self.failure or str(error);self.close();raise
        return self.result()

    def _step_before(self):
        self._check_deadline();self._live_code()
        current=self._current()
        self._require(self.player_step_count<64,'stomp player-step bound exceeded')
        field=self.session.emu.memory.register_arm9.r0
        self._require(field==current['worldContext']['fieldPointer'],'player-step field argument differs')
        value=dict(kind='playerStep',before=current,fieldPointer=field,
            entryClock=self.observer._clock(),completedFrame=self.session.completed_frames)
        self.player_step_count+=1;self.data.append(value)
        return value

    def _step_after(self,value,context):
        self._check_deadline();self._live_code()
        result=super()._after(value,context)
        return dict(result,entryClock=value['entryClock'],completedFrame=value['completedFrame'],
            returnClock=deepcopy(context['returned']),normalReturn=True)

    def completed_boundary(self):
        self._require(self.calibration is None,'stomp calibration cannot resume gameplay')
        self._check_deadline()
        if self.armed and not self.closed:self._live_code()
        super().completed_boundary()

    def _read_profile(self,current):
        """Shared native/paused-control read; no guest mutation or clock advance."""
        NativeCornerObserver._mount_binding(self,current)
        raw=public_bytes(self.session,self.mount_state+8,72)
        self._require(raw[70]<=32,'stomp threshold byte invalid')
        return dict(profileHex=raw.hex(),stompTime=raw[70])

    def _entry(self,kind):
        if kind!='policy' and not self.active:return None
        self._check_deadline();self._live_code()
        self._require(self.counts[kind]<64,'stomp callback bound exceeded')
        current=self._current();regs=self.session.emu.memory.register_arm9
        value=dict(kind=kind,before=current,entryClock=self.observer._clock(),
            completedFrame=self.session.completed_frames,caller=regs.lr,
            args=[regs.r0,regs.r1,regs.r2,regs.r3])
        if kind=='policy':
            self._require(not self.active and regs.r0==current['avatarPointer'] and regs.r1==current['mountPointer'],
                          'mounted feedback arguments differ')
            raw=public_bytes(self.session,regs.r2,28)
            version,size,lane=struct.unpack_from('<HHI',raw)
            self._require(version==1 and size==28 and lane==self.mount_state+8 and raw[8]==self.subject['handle']['slot']
                and raw[21] in (0,1,2,3),'mounted feedback policy ABI differs')
            profile=self._read_profile(current)
            binding=NativeCornerObserver._mount_binding(self,current)
            value.update(policyPointer=regs.r2,policyHex=raw.hex(),**profile,
                effect=raw[21],objectPointer=regs.r1,mountBinding=binding,
                feedback={name:[] for name in KINDS[1:]})
        else:
            parent=self.active[0]
            self._require(current==parent['before'],'feedback nested owner differs')
            allowed={'dust':'policy','allocate':'dust','init':'allocate','sound':'policy','soundStart':'sound'}
            self._require(self.active[-1]['kind']==allowed[kind],'feedback caller nesting differs')
            if kind=='dust':self._require(regs.r0==current['mountPointer'],'dust object differs')
            elif kind=='allocate':
                self._require(regs.r1==STOCK['descriptor'][0],'dust allocation descriptor differs')
                value['positionHex']=public_bytes(self.session,regs.r2,12).hex()
                context=struct.unpack('<I',public_bytes(self.session,regs.sp,4))[0]
                value['contextHex']=public_bytes(self.session,context,16).hex()
                self._require(struct.unpack_from('<I',bytes.fromhex(value['contextHex']),12)[0]==current['mountPointer'],
                              'dust allocation context object differs')
            elif kind=='init':value['effectDataPointer']=regs.r1
            elif kind=='sound':self._require(regs.r0==SOUND_ID,'stomp sound ID differs')
            elif kind=='soundStart':
                value['soundId']=struct.unpack('<I',public_bytes(self.session,regs.sp,4))[0]
                self._require(value['soundId']==SOUND_ID,'native sound-start ID differs')
        self.counts[kind]+=1;self.active.append(value);self.data.append(value)
        return value

    def _returned(self,value,context):
        try:
            self._check_deadline();self._live_code()
            self._require(self.active and self.active[-1] is value,'stomp return nesting differs')
            self._require(self._current()==value['before'],'feedback return owner differs')
            result=dict(value,returnValue=context['returnValue'],returnClock=deepcopy(context['returned']),normalReturn=True)
            kind=value['kind']
            if kind=='allocate':
                self._require(type(result['returnValue']) is int and result['returnValue']%4==0
                    and 0x02000000<=result['returnValue']<0x02400000,'dust allocation failed')
            elif kind=='init':
                raw=public_bytes(self.session,value['effectDataPointer'],36)
                result['effectDataHex']=raw.hex();result['renderPointer']=struct.unpack_from('<I',raw,32)[0]
                self._require(result['returnValue']==1 and 0x02000000<=result['renderPointer']<0x02400000
                    and struct.unpack_from('<I',raw,28)[0]==value['before']['mountPointer'],'dust render initialization failed')
            elif kind=='soundStart':self._require(result['returnValue']==1,'native sound start failed')
            elif kind=='policy':
                self._require(public_bytes(self.session,value['policyPointer'],28).hex()==value['policyHex'],
                              'feedback policy changed during sinks')
                expected=1 if value['effect']==1 else 0 if value['effect']==0 else None
                if expected is not None:
                    self._require(all(len(value['feedback'][name])==expected for name in KINDS[1:]),
                                  'stomp feedback coverage differs')
                    if expected:
                        self._require(value['feedback']['allocate'][0]['returnValue']==value['feedback']['init'][0]['args'][0],
                                      'dust allocation/init object differs')
                self.latest=deepcopy(result)
            self.active.pop()
            if self.active:self.active[0]['feedback'][kind].append(deepcopy(result))
            return result
        except Exception as error:
            self.failure=self.failure or str(error);raise
        finally:
            if value in self.data:self.data.remove(value)

    def close(self,disposing=False):
        if self.active:self.failure=self.failure or 'stomp callback pending at close'
        result=super().close(disposing);self.active.clear();return result

    def result(self):
        return deepcopy(dict(armed=self.armed,closed=self.closed,failure=self.failure,subject=self.subject,
            startFrame=self.started,maxFrames=self.maximum,counts=self.counts,pending=len(self.active),
            latest=self.latest,latestCompletedPose=self.latest_completed_pose,playerStepCount=self.player_step_count,
            calibration=deepcopy(self.calibration),
            guestMemoryWrites=0 if self.calibration is None else self.calibration.get('guestMemoryWrites'),acceptedProof=False,
            scope='scoped native mounted dust and sound receipts; not audible-output proof'))
