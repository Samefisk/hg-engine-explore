"""melonDS-only compatibility surface for the shared worker's native bridge."""
import ctypes as C
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import TypedDict

REVISION = "b86390e4428bf38ce4c1ce0e9ca446d6d25955e8"
CALLBACK = C.CFUNCTYPE(None, C.c_int, C.c_uint32, C.c_uint32, C.c_void_p)

class GuestClockValue(C.Structure):
    _fields_ = [("version", C.c_uint32), ("flags", C.c_uint32),
                ("arm9_timestamp", C.c_uint64), ("arm7_timestamp", C.c_uint64),
                ("frame_sequence", C.c_uint64)]

class GuestClock(TypedDict):
    version: int
    running: bool
    arm9Timestamp: int
    arm7Timestamp: int
    frameSequence: int
    scope: str

class DispatchCounts(C.Structure):
    _fields_ = [("version", C.c_uint32), ("flags", C.c_uint32),
                ("frame_sequence", C.c_uint64), ("arm9", C.c_uint64), ("arm7", C.c_uint64)]

class InstructionProfile(C.Structure):
    _fields_ = [("version", C.c_uint32), ("flags", C.c_uint32),
                ("frame_sequence", C.c_uint64), ("total", C.c_uint64), ("unmapped", C.c_uint64),
                ("bins", C.c_uint32 * 65536)]

class PhaseRow(C.Structure):
    _fields_ = [("cpu_ns", C.c_uint64), ("calls", C.c_uint64)]

class PhaseTimings(C.Structure):
    _fields_ = [("version", C.c_uint32), ("flags", C.c_uint32),
                ("frame_sequence", C.c_uint64), ("rows", PhaseRow * 3)]


def load_library():
    directory = Path(__file__).resolve().parents[2] / "build/melonds"
    path = directory / ("libow_melonds.dylib" if sys.platform == "darwin" else "libow_melonds.so")
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("sourceRevision") != REVISION or manifest.get("librarySha256") != hashlib.sha256(path.read_bytes()).hexdigest():
        raise RuntimeError("melonDS native build identity differs")
    inputs=manifest.get("bridgeInputs",{})
    expected={"CMakeLists.txt","bridge.cpp","bridge.h","build.py","core_test.cpp","platform.cpp","prepare_source.py","phase_scope.h"}
    source=Path(__file__).with_name("melonds_native")
    if set(inputs)!=expected or any(hashlib.sha256((source/name).read_bytes()).hexdigest()!=value
                                   for name,value in inputs.items()):
        raise RuntimeError("melonDS bridge source changed; rebuild its native library")
    if manifest.get("abiVersion")!=1 or manifest.get("jit") is not False or manifest.get("coreTests")!="passed-no-ROM":
        raise RuntimeError("melonDS interpreter/core checks are missing")
    return configure_library(C.CDLL(str(path)))


def configure_library(lib):
    """Bind a library whose file identity was checked by the caller."""
    H, U, I, P = C.c_void_p, C.c_uint32, C.c_int, C.c_char_p
    specs = {
        "md_abi_version": (U, []), "md_source_revision": (P, []),
        "md_create": (H, []), "md_destroy": (None, [H]), "md_last_error": (P, [H]),
        "md_open_rom": (I, [H,P]), "md_import_save": (I, [H,P]), "md_run_frame": (I,[H]),
        "md_read_bytes": (I,[H,I,U,H,U]), "md_write_bytes": (I,[H,I,U,H,U]),
        "md_get_reg": (U,[H,I,I]), "md_set_reg": (I,[H,I,I,U]),
        "md_next_pc": (U,[H,I]), "md_branch": (I,[H,I,U]), "md_set_keys": (I,[H,U]),
        "md_hook_exec": (I,[H,I,U,CALLBACK,H]), "md_hook_write": (I,[H,I,U,U,CALLBACK,H]),
        "md_abort": (None,[H,P]),
        "md_read_framebuffer": (I,[H,H,U]),
        "md_save_size": (U,[H]), "md_read_save": (I,[H,H,U]),
        "md_touch": (I,[H,I,I]), "md_release_touch": (I,[H]),
        "md_set_dispatch_counts": (I,[H,U]), "md_read_dispatch_counts": (I,[H,H,U]),
        "md_set_phase_timing": (I,[H,U]), "md_read_phase_timing": (I,[H,H,U]),
        "md_read_guest_clock": (I,[H,H,U]),
        "md_profile_enable": (I,[H,U]), "md_profile_read": (I,[H,H,U]),
    }
    for name,(result,args) in specs.items():
        fn=getattr(lib,name);fn.restype=result;fn.argtypes=args
    if lib.md_abi_version()!=1 or lib.md_source_revision().decode()!=REVISION:
        raise RuntimeError("melonDS bridge ABI/source mismatch")
    return lib


def bounded(value, maximum=0xffffffff):
    if type(value) is not int or not 0<=value<=maximum:
        raise ValueError("invalid unsigned native value")
    return value


class Registers:
    NAMES = {**{f"r{i}":i for i in range(16)},"sp":13,"lr":14,"pc":15,"cpsr":16,"spsr":17}
    def __init__(self,core,cpu):
        object.__setattr__(self,"core",core);object.__setattr__(self,"cpu",cpu)
    def __getattr__(self,name):
        if name not in self.NAMES:raise AttributeError(name)
        self.core.require_open()
        return self.core.lib.md_get_reg(self.core.handle,self.cpu,self.NAMES[name])
    def __setattr__(self,name,value):
        if name not in self.NAMES:raise AttributeError(name)
        self.core.call("md_set_reg",self.cpu,self.NAMES[name],bounded(value))


class MemoryValues:
    def __init__(self,core,signed=False):self.core,self.signed=core,signed
    def span(self,key):
        if not isinstance(key,slice):raise TypeError("memory access requires a slice")
        start,stop,width=bounded(key.start),bounded(key.stop),key.step or 1
        if width not in (1,2,4):raise ValueError("memory width must be1,2,4")
        length=width if start==stop else stop-start
        if length<0 or length>0x1000000 or start+length>0x100000000 or length%width:
            raise ValueError("invalid memory span")
        return start,length,width,start==stop
    def __getitem__(self,key):
        start,length,width,scalar=self.span(key)
        data=C.create_string_buffer(length)
        self.core.call("md_read_bytes",0,start,data,length)
        raw=data.raw
        values=[int.from_bytes(raw[i:i+width],"little",signed=self.signed) for i in range(0,length,width)]
        return values[0] if scalar else values
    def __setitem__(self,key,value):
        start,length,width,scalar=self.span(key)
        values=[value] if scalar else value
        data=b"".join(int(v).to_bytes(width,"little",signed=self.signed) for v in values)
        if len(data)!=length:raise ValueError("memory write length differs")
        buffer=C.create_string_buffer(data)
        self.core.call("md_write_bytes",0,start,buffer,length)


class Memory:
    def __init__(self,core):
        self.core=core
        self.unsigned=MemoryValues(core);self.signed=MemoryValues(core,True)
        self.register_arm9=Registers(core,0);self.register_arm7=Registers(core,1)
    def get_next_instruction(self):
        self.core.require_open()
        return self.core.lib.md_next_pc(self.core.handle,0)
    def set_next_instruction(self,address):
        self.core.call("md_branch",0,bounded(address)|(1 if self.register_arm9.cpsr&32 else 0))
    def register_exec(self,address,callback):self.core.hook("exec",address,1,callback)
    def register_write(self,address,callback,size=1):self.core.hook("write",address,size,callback)


class MelonDS:
    def __init__(self,library=None):
        self.lib=library if library is not None else load_library()
        self.handle=self.lib.md_create()
        if not self.handle:raise RuntimeError("melonDS core creation failed")
        self.callbacks={};self.retired=[];self.callback_error=None
        self.memory=Memory(self)
        self.input=SimpleNamespace(keypad_update=self.set_keys,
                                   touch_set_pos=self.touch, touch_release=self.release_touch)
        self.backup=SimpleNamespace(import_file=self.import_save, export_file=self.export_save)
    def require_open(self):
        if not self.handle:raise RuntimeError("melonDS core is closed")
    def call(self,name,*args):
        self.require_open()
        diagnostic = name in ("md_read_bytes", "md_read_dispatch_counts", "md_set_dispatch_counts", "md_read_phase_timing", "md_profile_read") or (name in ("md_set_phase_timing", "md_profile_enable") and args == (0,))
        if self.callback_error is not None and not diagnostic:
            raise self.callback_error
        result=getattr(self.lib,name)(self.handle,*args)
        if self.callback_error is not None and not diagnostic:raise self.callback_error
        if result!=0:
            message=self.lib.md_last_error(self.handle)
            raise RuntimeError(message.decode(errors="replace") if message else "melonDS native operation failed")
    def open(self,path):self.call("md_open_rom",str(path).encode())
    def import_save(self,path,force_size=0):
        if force_size!=0:raise ValueError("melonDS save size is derived from the cartridge")
        self.call("md_import_save",str(path).encode())
    def set_keys(self,mask):self.call("md_set_keys",bounded(mask,0xfff))
    def touch(self,x,y):self.call("md_touch",bounded(x,255),bounded(y,191))
    def release_touch(self):self.call("md_release_touch")
    def export_save(self,path):
        self.require_open()
        size=bounded(self.lib.md_save_size(self.handle),0x1000000)
        if size==0:raise RuntimeError("melonDS cartridge has no save data")
        data=C.create_string_buffer(size)
        self.call("md_read_save",data,size)
        Path(path).write_bytes(data.raw)
        return True
    def volume_set(self,value):
        if value!=0:raise ValueError("shared melonDS core has no audio output")
    def cycle(self,draw=False):
        try:self.call("md_run_frame")
        finally:self.retired.clear()
    def enable_dispatch_counts(self, enabled=True):
        if type(enabled) is not bool:raise ValueError("dispatch count enable must be boolean")
        previous=self.dispatch_counts()["enabled"]
        self.call("md_set_dispatch_counts",int(enabled))
        return previous
    def dispatch_counts(self):
        value=DispatchCounts()
        self.call("md_read_dispatch_counts",C.byref(value),C.sizeof(value))
        if value.version!=1 or value.flags&~3:
            raise RuntimeError("melonDS dispatch count schema differs")
        if not value.flags&1 and (value.arm9 or value.arm7):
            raise RuntimeError("disabled melonDS dispatch counts are nonzero")
        return dict(version=1,enabled=bool(value.flags&1),complete=bool(value.flags&2),
                    frameSequence=value.frame_sequence,arm9=value.arm9,arm7=value.arm7,
                    scope="interpreter-dispatches-not-retired-instructions")
    def guest_clock(self) -> GuestClock:
        """Raw inclusive scheduler clocks, not CPU cost or instructions.

        Reads do not advance execution. ARM9 exec callbacks observe the clock
        before that instruction. Ticks include IRQ and idle/wait advances;
        on NDS ARM9 has twice ARM7's tick scale. Never subtract across CPUs.
        frameSequence is the bridge's RunFrame attempt, not a game update.
        """
        value=GuestClockValue()
        self.call("md_read_guest_clock",C.byref(value),C.sizeof(value))
        if value.version!=1 or value.flags&~1:
            raise RuntimeError("melonDS guest clock schema differs")
        return dict(version=1,running=bool(value.flags&1),
                    arm9Timestamp=value.arm9_timestamp,arm7Timestamp=value.arm7_timestamp,
                    frameSequence=value.frame_sequence,
                    scope="nds-scheduler-ticks-not-cpu-or-instructions")
    def enable_instruction_profile(self, enabled=True):
        if type(enabled) is not bool:raise ValueError("instruction profile enable must be boolean")
        self.call("md_profile_enable", int(enabled))

    def instruction_profile(self):
        value = InstructionProfile()
        self.call("md_profile_read", C.byref(value), C.sizeof(value))
        if value.version != 1 or value.flags & ~7 or value.flags & 4:
            raise RuntimeError("melonDS instruction profile is invalid")
        bins = [[0x02000000 + i * 64, count] for i, count in enumerate(value.bins) if count]
        if sum(count for _, count in bins) + value.unmapped != value.total:
            raise RuntimeError("melonDS instruction profile totals differ")
        if not value.flags & 1 and value.total:
            raise RuntimeError("disabled melonDS instruction profile is nonzero")
        return dict(version=1, enabled=bool(value.flags & 1), complete=bool(value.flags & 2),
                    frameSequence=value.frame_sequence, total=value.total, unmapped=value.unmapped,
                    bins=bins, scope="arm9-dispatched-instructions-by-64-byte-PC-bin-not-time")
    def enable_phase_timings(self, enabled=True):
        if type(enabled) is not bool:raise ValueError("phase timing enable must be boolean")
        if enabled and self.callback_error is not None:raise self.callback_error
        previous=self.phase_timings()["enabled"]
        self.call("md_set_phase_timing",int(enabled))
        return previous
    def phase_timings(self):
        value=PhaseTimings()
        self.call("md_read_phase_timing",C.byref(value),C.sizeof(value))
        if value.version!=2 or value.flags&~7:
            raise RuntimeError("melonDS phase timing schema differs")
        if not value.flags&1 and any(row.cpu_ns or row.calls for row in value.rows):
            raise RuntimeError("disabled melonDS phase timings are nonzero")
        return dict(version=2,enabled=bool(value.flags&1),complete=bool(value.flags&2),
                    invalid=bool(value.flags&4),frameSequence=value.frame_sequence,
                    phases={name:dict(cpuNs=row.cpu_ns,calls=row.calls) for name,row in
                            zip(("nonRender","render3d","render2d"),value.rows)},
                    scope="native-exclusive-thread-cpu-diagnostic-v2")
    def hook(self,kind,address,size,callback):
        bounded(address);bounded(size)
        key=(kind,address,size)
        def dispatch(cpu,actual,width,user):
            if self.callback_error is not None:return
            try:
                if cpu!=0:raise RuntimeError("ARM9 hook dispatched on another CPU")
                callback(actual,width)
            except BaseException as error:
                if self.callback_error is None:self.callback_error=error
                self.lib.md_abort(self.handle,str(error).encode())
        native=CALLBACK(dispatch) if callback is not None else CALLBACK()
        if callback is None and self.callback_error is not None:
            self.require_open()
            # Remove host hooks for cleanup; no guest instruction can resume.
            result=(self.lib.md_hook_exec(self.handle,0,address,native,None) if kind=="exec"
                else self.lib.md_hook_write(self.handle,0,address,size,native,None))
            if result!=0:raise RuntimeError("melonDS failed to remove a faulted core hook")
        elif kind=="exec":self.call("md_hook_exec",0,address,native,None)
        else:self.call("md_hook_write",0,address,size,native,None)
        old=self.callbacks.pop(key,None)
        if old is not None:self.retired.append(old)
        if callback is not None:self.callbacks[key]=native
    def screenshot(self):
        # Only the explicit Capture command calls this; stepping never does.
        from PIL import Image
        data=C.create_string_buffer(256*384*4)
        self.call("md_read_framebuffer",data,len(data))
        return Image.frombytes("RGBA",(256,384),data.raw)
    def destroy(self):
        if self.handle:
            self.lib.md_destroy(self.handle);self.handle=None
        self.callbacks.clear();self.retired.clear()
