"""Read-only bounded forward-Hop (B Jump/ledge) return receipts for prepared diagnostics."""
from copy import deepcopy
import hashlib
import struct

from tools.overworld.devtools_observer import NativeObservationError, public_bytes

SYMBOL = "Chain_StartForwardHop"
STATE_ADDRESS, STATE_BYTES = 0x023BC744, 184
MAX_CALLS = 256


def require(value, message):
    if not value:
        raise NativeObservationError("forward Hop reader: " + message)


class NativeMountForwardHopObserver:
    def __init__(self, observer, linked):
        from tools.overworld.devtools_runtime import _elf_function_extent
        self.observer, self.session = observer, observer.session
        self.count = 0
        s, rt = self.session, self.session.rt
        path = rt.REPO / "build/overworld_mount_chain_overlay_linked.o"
        symbols = rt.linked_symbols(path)
        address, size = _elf_function_extent(path, SYMBOL)
        self.code = observer.elf_code(path, address, size)
        require(rt.linked_symbol(symbols, SYMBOL) & ~1 == address
                and rt.linked_symbol(rt.MOUNT_SYMBOLS, "sOverworldMountState") == STATE_ADDRESS
                and 32 <= size <= 0x18C and len(self.code) == size
                and any(base <= address and address + size <= base + len(data)
                        and data[address-base:address-base+size] == self.code
                        for base, data in s.code_regions),
                "linked body or packaged owner differs")
        self.address = address
        self.provenance = dict(symbol=SYMBOL, address=address, size=size,
            sha256=hashlib.sha256(self.code).hexdigest(), stateAddress=STATE_ADDRESS,
            stateBytes=STATE_BYTES, stateScope="guard prefix; excludes trailing face-Y field")
        linked("mounted-forward-hop", path, symbols, SYMBOL, self.before, self.after,
               scope=lambda: bool(s.prepared))
        observer.calls["mounted-forward-hop"]["diagnosticCallsDropped"] = 0

    def live_code(self):
        require(self.observer._live_code(self.address, self.code) == self.code,
                "complete live body differs")

    def state(self, owner):
        raw = public_bytes(self.session, STATE_ADDRESS, STATE_BYTES)
        actor, source = owner["publicSubject"], owner["sourceIdentity"]
        binding = struct.unpack_from("<IHHHHBBBB", raw, 88)
        require(struct.unpack_from("<I", raw)[0] == owner["fieldPointer"]
                and raw[108] == 3 and struct.unpack_from("<I", raw, 104)[0] > 0
                and binding[:7] == (source["personality"], actor["species"],
                    owner["context"]["mapId"], actor["handle"]["mapGeneration"],
                    actor["handle"]["encounterGeneration"], actor["form"], actor["level"])
                and binding[7] < 6, "current mount binding differs")
        return raw

    def before(self):
        if self.count >= MAX_CALLS:
            # The first bounded diagnostic window cannot prove later calls.
            self.observer.calls["mounted-forward-hop"]["diagnosticCallsDropped"] += 1
            return None
        self.live_code()
        s, rt = self.session, self.session.rt
        registers = s.emu.memory.register_arm9
        owner = self.observer.role_profiles._owner()
        require(owner is not None and owner["publicSubject"]["role"] == "MOUNTED"
                and rt.actor_state(s.emu, 7).get("inputOwnership") == 1,
                "current mounted subject differs")
        avatar = rt.unsigned(s.emu, owner["fieldPointer"] + 0x40)
        require(registers.r0 == STATE_ADDRESS and registers.r1 == avatar,
                "state or current avatar argument differs")
        public_bytes(s, avatar, 0x40)
        # The fifth argument is this frame's raw new-key mask (B starts a Jump).
        new_keys, = struct.unpack("<I", public_bytes(s, registers.sp, 4))
        require(new_keys & ~0x0FFF == 0 and (0 <= registers.r3 <= 7 or registers.r3 == 255),
                "direction or fifth argument differs")
        self.count += 1
        return dict(owner=owner, args=dict(state=registers.r0, avatar=registers.r1,
                    policy=registers.r2, direction=registers.r3, newKeys=new_keys),
                    callerReturn=registers.lr, beforeStateHex=self.state(owner).hex(),
                    completedFrame=s.completed_frames)

    def after(self, before, context):
        self.live_code()
        require(context["returnValue"] in (0, 1, 2), "return is not 0, 1 or 2")
        owner = self.observer.role_profiles._same(before["owner"])
        require(self.session.completed_frames == before["completedFrame"],
                "call crossed a completed frame")
        return dict(**before, afterOwner=owner, afterStateHex=self.state(owner).hex(),
                    provenance=deepcopy(self.provenance), normalReturn=True,
                    diagnosticOnly=True, acceptedProof=False)


def install_mount_forward_hop(observer, linked):
    # Small generic host fixtures omit the Mount capability. Real sessions
    # initialize MOUNT_SYMBOLS before NativeObservation.install.
    if not hasattr(observer.session.rt, "MOUNT_SYMBOLS"):
        return None
    return NativeMountForwardHopObserver(observer, linked)
