"""Read-only crash-shake ownership at the completed field boundary."""
from copy import deepcopy
import hashlib
import struct

from tools.overworld.devtools_field_cleanup import symbol

STATE_SIZE = 944
OFFSETS = (714, 724, 764)
CODE = (
    ("OverworldWildSpawns_StartMovementCrashShake", 72,
     "f4b00962374934bfeb10cbe154cbab4a0cde6e69820235bce26fc5b6f8ccea15"),
    ("OverworldWildSpawns_RestoreMovementCrashShake", 76,
     "4b10094df7767748b778037336d0b1431e3c255b7394a80d684524f04fbd06b0"),
)
# Reviewed equivalent Start layout from build3096: only these two Thumb BL
# displacements vary with placement. Every other byte, including state offsets,
# remains pinned. The prior Start image is not retained; no old-byte parity is
# inferred. Restore's original full-code digest remains unchanged.
CALLS = {
    "OverworldWildSpawns_StartMovementCrashShake": (
        (22, "OverworldWildSpawns_RestoreMovementCrashShake"),
        (60, "OverworldWildSpawns_EnsureFrameMovementTask"),
    ),
}


def _layout_code(name, code):
    normalized = bytearray(code)
    for offset, _ in CALLS.get(name, ()):
        high, low = struct.unpack_from("<HH", code, offset)
        if high & 0xF800 != 0xF000 or low & 0xF800 != 0xF800:
            raise ValueError("crash-call-opcode-differs")
        struct.pack_into("<HH", normalized, offset, 0xF000, 0xF800)
    return bytes(normalized)


def _call_target(address, code, offset):
    high, low = struct.unpack_from("<HH", code, offset)
    displacement = ((high & 0x7FF) << 12) | ((low & 0x7FF) << 1)
    if displacement & (1 << 22):
        displacement -= 1 << 23
    return (address + offset + 4 + displacement) & 0xFFFFFFFF


class CrashPresentationReader:
    def __init__(self, load_elf, packaged_code):
        self.state, _, _ = symbol(load_elf("linked.o"), "sOverworldWildSpawnState", 1,
                                  expected_size=STATE_SIZE)
        if self.state & 3 or not 0x02000000 <= self.state <= 0x02400000 - STATE_SIZE:
            raise ValueError("invalid-crash-state-range")
        image = load_elf("overworld_wild_spawns_overlay_linked.o")
        self.code = []
        for name, size, digest in CODE:
            address, _, code = symbol(image, name, 2, expected_size=size)
            if hashlib.sha256(_layout_code(name, code)).hexdigest() != digest:
                raise ValueError("unknown-crash-layout-code")
            if packaged_code(address, size) != code:
                raise ValueError("crash-package-code-mismatch")
            self.code.append((address, code))
            for offset, target_name in CALLS.get(name, ()):
                target, target_size, target_code = symbol(image, target_name, 2)
                if _call_target(address, code, offset) != target:
                    raise ValueError("crash-call-target-differs")
                if packaged_code(target, target_size) != target_code:
                    raise ValueError("crash-call-target-package-mismatch")
                self.code.append((target, target_code))
        # Restore is both layout-pinned and a call target. Read it once per
        # boundary while retaining exact live authentication of both callees.
        self.code = list(dict(self.code).items())

    def boundary(self, read):
        for address, code in self.code:
            if read(address, len(code)) != code:
                raise ValueError("crash-live-code-mismatch-or-overlay-absent")

    def observe(self, read, actor, frame, native_cycle):
        result = {"known": False, "reason": "unread", "frame": frame,
                  "nativeCycle": native_cycle, "boundary": "main-task-queue-completion"}
        try:
            handle = actor.get("handle", {})
            slot = handle.get("slot")
            owner = actor.get("engineIdentity", {}).get("pointer")
            if actor.get("identityVerified") is not True or type(slot) is not int or not 0 <= slot < 10 \
                    or type(owner) is not int or owner & 3 or not 0x02000000 <= owner <= 0x02400000 - 0x12C \
                    or actor.get("sourceIdentity", {}).get("object") != owner:
                raise ValueError("crash-owner-unverified")
            def exact(address, size):
                value = read(address, size)
                if not isinstance(value, (bytes, bytearray)) or len(value) != size:
                    raise ValueError("short-crash-state-read")
                return value
            if struct.unpack("<I", exact(self.state + slot * 20, 4))[0] != owner:
                raise ValueError("crash-owner-changed")
            timer = exact(self.state + OFFSETS[0] + slot, 1)[0]
            x = struct.unpack("<i", exact(self.state + OFFSETS[1] + slot * 4, 4))[0]
            z = struct.unpack("<i", exact(self.state + OFFSETS[2] + slot * 4, 4))[0]
            result.update(known=True, reason="observed", timer=timer, baseX=x, baseZ=z,
                          objectPointer=owner, handle=deepcopy(handle))
        except (ValueError, TypeError, KeyError, struct.error) as error:
            result["reason"] = str(error)[:160]
        return result
