"""Bounded native mounted crash callbacks; diagnostic memory data only."""
from copy import deepcopy
import struct

from tools.overworld.devtools_mount_pacing_observer import NativeMountedPacingObserver
from tools.overworld.devtools_corner_observer import NativeCornerObserver
from tools.overworld.devtools_observer import public_bytes

STATE_ADDRESS, STATE_BYTES = 0x023BC744, 184
MODE_OFFSET, DURATION_OFFSET, ELAPSED_OFFSET = 102, 144, 146
SYMBOLS = dict(start='OverworldMount_StartWalkCrash', update='OverworldMount_UpdateCustomMotion',
    presentation='OverworldMount_ApplyCrashPresentation', finish='OverworldMount_FinishCustomMotion',
    crashSound='OverworldMount_PlayCrashSound')
STOCK = dict(sound=(0x0200604C,0x20),soundStart=(0x020060BC,0x5C))
KINDS = (*SYMBOLS,*STOCK)


class NativeMountedCrashObserver(NativeMountedPacingObserver):
    def __init__(self,session,subject,max_frames):
        super().__init__(session,subject,max_frames)
        self.code={};self.active=[];self.counts=dict.fromkeys(KINDS,0)
        self.latest=None;self.latest_completed=None;self.mount_state=STATE_ADDRESS
        self.linked=self._linked_crash

    def _linked_crash(self,label,path,symbols,name,before,after,**kwargs):
        address,expected=self.code[name]
        self.observer._tap(label,address,expected[:32],before,after,**kwargs)

    def _authenticate(self):
        from tools.overworld.devtools_runtime import _elf_function_extent
        s=self.session;path=s.rt.REPO/'build/overworld_mount_overlay_linked.o'
        self._require(s.rt.linked_symbol(s.rt.MOUNT_SYMBOLS,'sOverworldMountState')==STATE_ADDRESS,
            'crash state address differs')
        for name,symbol in SYMBOLS.items():
            address,size=_elf_function_extent(path,symbol)
            expected=self.observer.elf_code(path,address,size)
            self._require(size>=32 and len(expected)==size and s.packaged_code(address,size)==expected,
                'full mounted crash code differs: '+name)
            self.code[name]=(address,expected)
        arm9=(s.rt.REPO/'base/arm9.bin').read_bytes()
        for name,(address,size) in STOCK.items():
            expected=arm9[address-0x02000000:address-0x02000000+size]
            self._require(len(expected)==size and s.packaged_code(address,size)==expected,
                'full stock crash code differs: '+name)
            self.code[name]=(address,expected)
        self._live_code()

    def _live_code(self):
        for name,(address,expected) in self.code.items():
            self._require(self.session.read(address,len(expected))==expected,'live crash code differs: '+name)

    def _sample(self):
        current=self._current()
        binding=NativeCornerObserver._mount_binding(self,current)
        raw=public_bytes(self.session,self.mount_state,STATE_BYTES)
        mode=raw[MODE_OFFSET];duration,elapsed=struct.unpack_from('<HH',raw,DURATION_OFFSET)
        self._require(mode<=4 and (mode!=3 or duration==32 and elapsed<=32),'crash state fields invalid')
        return dict(current=current,mountBinding=binding,mountStateHex=raw.hex(),mode=mode,
            duration=duration,elapsed=elapsed,pose=self._read_pose(current))

    def arm(self):
        self._require(not self.armed and not self.closed and type(self.maximum) is int and 1<=self.maximum<=600,
            'invalid crash arm or frame bound')
        s=self.session
        self._require(s.emu is not None and not s.native_bridge_active
            and s.rom.resolve().is_relative_to(s.directory.resolve())
            and s.rom.resolve()!=(s.rt.REPO/'test.nds').resolve(),'crash requires an owned private session')
        self.started=s.completed_frames
        try:
            self.owner=self._current()
            self._require(self.owner['publicSubject']['species']==155,'crash requires mounted Cyndaquil')
            self._authenticate();self._sample();self.armed=True
            for kind in KINDS:
                self._install('mounted-crash-'+kind,kind,lambda kind=kind:self._entry(kind),self._returned)
        except Exception as error:
            self.failure=self.failure or str(error);self.close();raise
        return self.result()

    def _entry(self,kind):
        # Normal Walk update/presentation/finish calls do not add crash events.
        if kind in ('update','presentation','finish') and public_bytes(self.session,self.mount_state,STATE_BYTES)[MODE_OFFSET]!=3:
            return None
        if kind in STOCK and not any(v['kind']=='crashSound' for v in self.active):return None
        self._check_deadline();self._live_code()
        self._require(sum(self.counts.values())<4096 and self.counts[kind]<1200,'crash callback bound exceeded')
        sample=self._sample();regs=self.session.emu.memory.register_arm9
        if kind=='presentation':
            self._require(regs.r0==sample['current']['playerPointer'] and regs.r1==sample['current']['mountPointer'],
                'crash presentation arguments differ')
        if kind in ('sound','crashSound'):self._require(regs.r0==1536,'crash sound ID differs')
        if kind=='soundStart':
            self._require(self.active and self.active[-1]['kind']=='sound'
                and struct.unpack('<I',public_bytes(self.session,regs.sp,4))[0]==1536,'crash sound-start arguments differ')
        if kind=='sound':self._require(self.active[-1]['kind']=='crashSound','crash sound nesting differs')
        value=dict(kind=kind,before=sample,entryClock=self.observer._clock(),
            completedFrame=self.session.completed_frames,caller=regs.lr,args=[regs.r0,regs.r1,regs.r2,regs.r3])
        self.counts[kind]+=1;self.active.append(value);self.data.append(value)
        return value

    def _returned(self,value,context):
        try:
            self._check_deadline();self._live_code()
            self._require(self.active and self.active[-1] is value,'crash return nesting differs')
            sample=self._sample()  # _current validates stable owner, not mutable motion fields.
            self._require(sample['mountBinding']==value['before']['mountBinding'],'crash return binding differs')
            if value['kind']=='soundStart':self._require(context['returnValue']==1,'crash native sound start failed')
            result=dict(value,after=sample,returnClock=deepcopy(context['returned']),
                returnValue=context['returnValue'],normalReturn=True)
            self.active.pop();self.latest=deepcopy(result)
            return result
        except Exception as error:
            self.failure=self.failure or str(error);raise
        finally:
            if value in self.data:self.data.remove(value)

    def completed_boundary(self):
        self._check_deadline()
        if self.armed and not self.closed:
            self._live_code();super().completed_boundary()
            self.latest_completed=dict(self._sample(),frame=self.session.completed_frames,
                boundary='main-task-queue-completion',**self.observer._clock())

    def close(self,disposing=False):
        if self.active:self.failure=self.failure or 'mounted crash callback pending at close'
        super().close(disposing);self.active.clear()
        return self.result()

    def result(self):
        return deepcopy(dict(armed=self.armed,closed=self.closed,failure=self.failure,subject=self.subject,
            startFrame=self.started,maxFrames=self.maximum,counts=self.counts,pending=len(self.active),
            latest=self.latest,latestCompleted=self.latest_completed,latestCompletedPose=self.latest_completed_pose,
            guestMemoryWrites=(getattr(self,'calibration',None) or {}).get('guestMemoryWrites',0),
            calibration=getattr(self,'calibration',None),acceptedProof=False,
            scope='mounted crash native receipts; not audible-output proof'))
