"""Scoped, read-only IRQ evidence during prepared follower release."""
from collections import deque
from copy import deepcopy
import struct
import hashlib
import json
import os
import time

IRQ_BASE = 0x01FF8000
IRQ_BYTES = 0x1AC
WRITE_WATCHES = (0, IRQ_BASE)


def _effect_pool_diagnostic(session, cpu):
    """One stock effect-init caller, never a general heap inspection."""
    words = cpu.get("stack", {}).get("words", [])
    if cpu.get("pc") != 0x02023F30 or len(words) != 16 or words[3] != 0x021FF21D:
        return None
    result = {"caller": words[3], "environment": words[1], "known": False}
    try:
        root = session.rt.REPO
        table = (root / "base/overarm9.bin").read_bytes()
        overlay_base = struct.unpack_from("<I", table, 32 + 4)[0]
        # Full stock caller plus the field-manager and pool-allocation paths.
        spans = ((0x021FF174, 0xB4), (0x021F16EC, 0x6C),
                 (0x02023D44, 0x60), (0x02024280, 0x2C), (0x02023F1C, 0x18))
        for address, size in spans:
            overlay = address >= 0x021E0000
            path = root / ("base/overlay/overlay_0001.bin" if overlay else "base/arm9.bin")
            offset = address - (overlay_base if overlay else 0x02000000)
            expected = path.read_bytes()[offset:offset + size]
            if len(expected) != size or session.packaged_code(address, size) != expected:
                raise ValueError("stock effect-pool code differs")
        result["codeAuthenticated"] = True
        def pointer(value):
            if type(value) is not int or value % 4 or not 0x02000000 <= value <= 0x023FFFFC:
                raise ValueError("effect-pool pointer is absent or outside public RAM")
            return value
        def word(address):
            data = session.read(pointer(address), 4)
            if len(data) != 4:
                raise ValueError("effect-pool word is incomplete")
            return struct.unpack("<I", data)[0]
        value = pointer(words[1])
        for name, offset in (("manager", 0x28), ("renderer", 0x20), ("pool", 0x0C)):
            value = word(value + offset)
            result[name] = value
            pointer(value)
        result["capacity"] = word(value + 8)
        result["used"] = word(value + 0xD4)
        result["slots"] = word(value + 0xD0)
        capacity, used = result["capacity"], result["used"]
        if not 0 <= used <= capacity <= 4096:
            raise ValueError("effect-pool counters exceed diagnostic bounds")
        result["full"] = used == capacity
        slots = pointer(result["slots"])
        if used < capacity:
            result["nextSlot"] = {"index": used, "pointer": word(slots + 4 * used)}
        if used:
            result["previousSlot"] = {"index": used - 1, "pointer": word(slots + 4 * (used - 1))}
        result["known"] = True
        result["note"] = "used is post-fault; allocation increments it even for a null slot. Slot values do not prove prior call history."
    except Exception as error:
        result["unavailable"] = str(error)
    return result


class ReleaseObserver:
    def __init__(self, session, mode="write"):
        if mode not in ("write", "irq"):
            raise ValueError("release diagnostics must be write or irq")
        self.session = session
        self.mode = mode
        self.tokens = []
        self.recent = deque(maxlen=32)
        self.count = 0
        self.first_invalid = None
        self.thread = None
        self.failure = None
        self.write_watches = []
        self.write_count = 0
        self.write_baseline = None
        self.write_memory = None
        self._next_progress_time = 0.0

    def install(self):
        try:
            for kind, address in self.session._native_checkpoint_points():
                if self.mode == "irq" and kind.startswith("irq-"):
                    self.tokens.append(self.session.party_getter_hooks.add(
                        address, lambda kind=kind, address=address: self.observe(kind, address)))
            # Bridge setup can refresh the session baseline. This probe owns
            # the unchanged bytes from its own start, across all bridge calls.
            self.write_baseline = bytes(self.session.native_irq_live_baseline)
            if len(self.write_baseline) != IRQ_BYTES:
                raise ValueError("release IRQ write baseline is incomplete")
            self.write_memory = self.session.emu.memory
            for address in WRITE_WATCHES:
                self.write_watches.append(address)
                self.write_memory.register_write(address, self.observe_write, size=IRQ_BYTES)
        except Exception:
            self.close()
            raise

    def close(self):
        # A failed bridge may already have destroyed the core. Its callback
        # table is gone; never call into that destroyed native object.
        for address in self.write_watches:
            if self.session.emu is not None:
                self.write_memory.register_write(address, None, size=IRQ_BYTES)
        self.write_watches.clear()
        for token in self.tokens:
            self.session.party_getter_hooks.remove(token)
        self.tokens.clear()

    def receipt(self):
        return {"boundary": "prepared-follower-release-irq", "readOnly": True,
                "mode": self.mode, "coverage": {"irqExecutionCheckpoints": self.mode == "irq",
                                                "irqCodeWriteWatches": True},
                "checkpointCount": self.count, "checkpoints": list(self.recent),
                "firstInvalid": deepcopy(self.first_invalid),
                "writeProbe": {"ranges": [{"address": address, "bytes": IRQ_BYTES}
                                          for address in WRITE_WATCHES],
                               "callbackCount": self.write_count,
                               "callbackBoundary": "after-write", "writerCpu": "unknown",
                               "limitations": "Other ITCM aliases and non-hook writes are not covered; callback supplies no CPU or written value.",
                               "baselineSha256": hashlib.sha256(self.write_baseline).hexdigest()
                                   if self.write_baseline is not None else None}}

    def observe_write(self, address, size):
        """The binding reports the original bus address after the write.

        ARM7 rejected writes can also call this hook. Neither a callback nor
        either CPU's current PC alone identifies the writer of changed ITCM.
        """
        from tools.overworld.devtools_runtime import DevtoolsFailure
        if self.failure is not None:
            return
        s = self.session
        self.write_count += 1
        item = {"kind": "irq-code-write-observation", "address": address, "size": size,
                "frame": s.completed_frames, "nativeCycle": s.rt.EXECUTED_FRAME_COUNT,
                "nativeBridgeActive": bool(getattr(s, "native_bridge_active", False)),
                "callbackBoundary": "after-write", "writerCpu": "unknown"}
        try:
            if (type(address) is not int or type(size) is not int or size not in (1, 2, 4)
                    or not any(address < start + IRQ_BYTES and address + size > start
                               for start in WRITE_WATCHES)):
                raise ValueError("IRQ write callback is outside the watched ranges")
            actual = bytes(s.rt.actor_memory_read(s.emu, IRQ_BASE, IRQ_BYTES))
            if len(actual) != IRQ_BYTES or self.write_baseline is None:
                raise ValueError("IRQ write observation is incomplete")
            if actual == self.write_baseline:
                return
            changes = [{"offset": offset,
                        "expected": struct.unpack_from("<I", self.write_baseline, offset)[0],
                        "actual": struct.unpack_from("<I", actual, offset)[0]}
                       for offset in range(0, IRQ_BYTES, 4)
                       if actual[offset:offset + 4] != self.write_baseline[offset:offset + 4]]
            item.update(canonicalAddress=IRQ_BASE + (address & 0x7FFF),
                        changedWordCount=len(changes), changedWords=changes[:16],
                        changedWordsTruncated=len(changes) > 16,
                        actualSha256=hashlib.sha256(actual).hexdigest())
            for name in ("arm9", "arm7"):
                try:
                    registers = getattr(s.emu.memory, "register_" + name)
                    item[name] = {key: getattr(registers, key) & 0xFFFFFFFF
                                  for key in ("pc", "cpsr", "spsr", "sp", "lr")
                                  + tuple("r" + str(i) for i in range(13))}
                except Exception as error:
                    item[name] = {"unavailable": str(error)}
                if "sp" in item[name]:
                    stack = {"address": item[name]["sp"], "bytes": 64,
                             "memoryView": "shared-public-stack"}
                    try:
                        # Reuse the shared public RAM/stack bounds. ARM7
                        # private RAM is deliberately not made readable here.
                        data = bytes(s.read(stack["address"], 64))
                        if len(data) != 64:
                            raise ValueError("native stack observation is incomplete")
                        stack["words"] = list(struct.unpack("<16I", data))
                    except Exception as error:
                        stack["unavailable"] = str(error)
                    item[name]["stack"] = stack
            pool = _effect_pool_diagnostic(s, item.get("arm9", {}))
            if pool is not None:
                item["effectPool"] = pool
            reason = "IRQ code differs from release probe start after a watched write"
        except Exception as error:
            reason = str(error)
        item["invalidReason"] = reason
        self.first_invalid = deepcopy(item)
        self.failure = DevtoolsFailure("prepared-release-irq-code-write", reason, fatal=True, details={})
        self.failure.details["releaseObservation"] = self.receipt()

    def observe(self, kind, address):
        from tools.overworld.devtools_runtime import (
            DevtoolsFailure, native_callback_cpu_observation, native_cpu_diagnostics)
        s = self.session
        if self.mode != "irq" or self.failure is not None or getattr(s, "native_bridge_active", False):
            return
        item = {"kind": kind, "address": address,
                "frame": s.completed_frames, "nativeCycle": s.rt.EXECUTED_FRAME_COUNT}
        try:
            cpu = native_callback_cpu_observation(s, address)
            item["callbackCpu"] = cpu
            if (cpu.get("actualCallback") != {"address": address, "size": 4}
                    or cpu["arm9"].get("executionAddressFromPc") != address
                    or cpu["arm9"].get("cpsr", 0) & 0x20):
                raise ValueError("IRQ callback is not attributable to ARM9 ARM execution")
            regs = s.emu.memory.register_arm9
            cpsr, sp = regs.cpsr & 0xFFFFFFFF, regs.sp & 0xFFFFFFFF
            if kind == "irq-return-if-idle" and not cpsr & 0x40000000:
                return
            item.update(cpsr=cpsr, sp=sp, spsr=regs.spsr & 0xFFFFFFFF,
                        lr=regs.lr & 0xFFFFFFFF, irqVector=s._native_irq_vector())
            target = None
            if kind == "irq-dispatch":
                target = regs.r0 & 0xFFFFFFFF
            elif kind.startswith("irq-return"):
                words = list(struct.unpack("<7I", s.read(sp, 28)))
                item.update(irqStackWords=words, savedInterruptedLink=words[6],
                            savedInterruptedResume=(words[6] - 4) & 0xFFFFFFFF)
                target = words[0]
            elif kind == "irq-entry":
                words = list(struct.unpack("<6I", s.read(sp, 24)))
                item.update(biosStackWords=words, savedInterruptedLink=words[5],
                            savedInterruptedResume=(words[5] - 4) & 0xFFFFFFFF)
            elif kind == "irq-thread-chosen":
                item["chosenThread"] = s._native_thread_snapshot(regs.r1 & 0xFFFFFFFF)
                self.thread = {"chosen": deepcopy(item)}
                if not item["chosenThread"].get("validContext"):
                    raise ValueError("selected SDK thread has an invalid context")
            elif kind == "irq-thread-svc-pop":
                item["savedChosenPointer"] = struct.unpack("<I", s.read(sp, 4))[0]
                if self.thread is None:
                    raise ValueError("SDK thread pop has no observed selection")
                self.thread["svcPop"] = deepcopy(item)
            elif kind == "irq-thread-restore":
                actual = s._native_thread_snapshot(regs.r1 & 0xFFFFFFFF)
                item["restoreThread"] = actual
                bundle = self.thread or {}
                item["threadSwitch"] = deepcopy(bundle)
                if (not actual.get("validContext")
                        or bundle.get("chosen", {}).get("chosenThread", {}).get("pointer") != actual["pointer"]
                        or bundle.get("svcPop", {}).get("savedChosenPointer") != actual["pointer"]):
                    raise ValueError("SDK restored thread differs from the selected valid thread")
            if target is not None:
                item.update(target=target, targetInMappedCode=s._native_target_is_mapped_code(target))
                if not item["targetInMappedCode"]:
                    raise ValueError("IRQ target is outside mapped code")
        except Exception as error:
            item["invalidReason"] = str(error)
            # Range membership is not function identity. Keep the immediate
            # CPU/code evidence only on failure, without replacing its cause.
            for name, reader in (("cpu", lambda: native_cpu_diagnostics(s)),
                                 ("irqCodeIdentity", s._native_irq_code_identity)):
                try:
                    item[name] = reader()
                except Exception as diagnostic_error:
                    item[name] = {"unavailable": str(diagnostic_error)}
            self.first_invalid = deepcopy(item)
            self.failure = DevtoolsFailure("prepared-release-invalid-native-target", str(error),
                                          fatal=True, details={})
        self.count += 1
        self.recent.append(deepcopy(item))
        if self.failure is not None:
            # Store the first callback evidence before any endpoint/cleanup.
            self.failure.details["releaseObservation"] = self.receipt()

    def check(self):
        if self.failure is not None:
            raise self.failure
        # Only the cycle endpoint emits progress, never an IRQ/write callback.
        # Best-effort diagnostics must neither replace a fault nor change play.
        try:
            now = time.monotonic()
            if now < self._next_progress_time:
                return
            self._next_progress_time = now + 1.0
            s = self.session
            bridge = bool(getattr(s, "native_bridge_active", False))
            cached = getattr(s, "latest_frame", None) or {}
            selector = cached.get("selector") or {}
            release = selector.get("followerReleaseState")
            regs = getattr(getattr(getattr(s, "emu", None), "memory", None), "register_arm9", None)
            cpu = {}
            for name in ("pc", "cpsr", "sp"):
                try:
                    cpu[name] = getattr(regs, name) & 0xFFFFFFFF
                except Exception:
                    cpu[name] = None
            value = {"kind": "prepared-release-progress", "frame": getattr(s, "completed_frames", None),
                     "mode": self.mode,
                     "nativeCycle": getattr(s.rt, "EXECUTED_FRAME_COUNT", None),
                     "checkpointCount": self.count, "writeCount": self.write_count,
                     "phase": "native-bridge" if bridge else "release-wait",
                     "nativeBridgeActive": bridge, "arm9": cpu,
                     "cachedSelector": {"snapshotFrame": cached.get("frame"),
                         "followerReleaseState": release,
                         "releasePhase": release & 0x7F if type(release) is int else None}}
            os.write(2, (json.dumps(value, separators=(",", ":")) + "\n").encode("ascii"))
        except Exception:
            pass
