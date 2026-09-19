"""Disposable, prepared-only overworld development session.

There is deliberately no public address, memory-write, eval, or native-call
operation. The private bridge runs a fixed list of engine routines from the
return of the normal field diagnostic poll. It is not normal-play proof.
"""

from __future__ import annotations

from copy import deepcopy
from contextlib import nullcontext
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import struct
import time
import math
import uuid

from tools.overworld.devtools_engine import Hooks as EngineHooks, SUBSTRUCT_OFFSETS
from tools.overworld.spawn_identity import live_spawn_flags
from tools.overworld.devtools_callback_costs import CallbackCosts
from tools.overworld.devtools_dispatch_counts import validate_dispatch_counts
from tools.overworld.devtools_host_probe import measure_host_probe
from tools.overworld.devtools_phase_timings import validate_phase_timings


class DevtoolsFailure(RuntimeError):
    def __init__(self, code, message, *, fatal=False, details=None):
        super().__init__(message)
        self.code, self.fatal = code, fatal
        self.details = details


class DevtoolsHooks(EngineHooks):
    """One native dispatcher per bounded address for this disposable core.

    Keep dispatchers alive with empty listener lists between calls rather
    than registering a fresh native hook at every natural return. Listener
    changes do not replace the shared melonDS dispatcher.
    """
    MAX_ADDRESSES = 2048

    def __init__(self, rt, emu, callback_costs=None):
        super().__init__(rt, emu)
        self.current_callback = None
        self.callback_costs = callback_costs if callback_costs is not None else CallbackCosts()

    def add(self, address, callback):
        address &= ~1
        if address not in self.callbacks:
            require(len(self.callbacks) < self.MAX_ADDRESSES,
                    "native observer address budget exceeded", "observation-limit")
            self.callbacks[address] = []
            def invoke(actual_address, actual_size):
                if self.error is not None:
                    return
                previous = self.current_callback
                self.current_callback = {"address": actual_address & 0xFFFFFFFF, "size": actual_size}
                try:
                    for item in tuple(self.callbacks.get(address, ())):
                        item()
                except Exception as error:
                    self.error = f"observation callback at {address:#010x}: {type(error).__name__}: {error}"
                finally:
                    self.current_callback = previous
            label = f"native:{address:#010x}"
            def dispatch(actual_address, actual_size):
                # The C dispatcher is retained to bound callback allocations.
                # A removed IRQ/return tap has no work, including no timing.
                if self.error is not None or not self.callbacks.get(address):
                    return
                try:
                    self.callback_costs.call(label, invoke, actual_address, actual_size)
                except Exception as error:
                    if self.error is None:
                        self.error = f"callback timing at {address:#010x}: {type(error).__name__}: {error}"
            try:
                self.emu.memory.register_exec(address, dispatch)
            except Exception:
                # A failed native registration is not an installed dispatcher.
                # Retrying must register again, not append to a dead list.
                del self.callbacks[address]
                raise
        self.callbacks[address].append(callback)
        return address, callback

    def remove(self, token):
        address, callback = token
        callbacks = self.callbacks.get(address, [])
        if callback in callbacks:
            callbacks.remove(callback)

    def retire_empty(self, address):
        """Unregister one unused setup dispatcher; never remove a listener."""
        address &= ~1
        if address not in self.callbacks or self.callbacks[address]:
            return False
        # The public binding retains the old C callback until core teardown.
        # Delete the cache only after native unregister succeeds, so one later
        # add can safely install a new dispatcher instead of a dead listener.
        self.emu.memory.register_exec(address, None)
        del self.callbacks[address]
        return True


def require(value, message, code="invalid-state"):
    if not value:
        raise DevtoolsFailure(code, message)


def integer(value, name, minimum, maximum):
    require(type(value) is int and minimum <= value <= maximum,
            f"{name} must be an integer from {minimum} to {maximum}", "invalid-argument")
    return value


def owned_path(value, directory, *, exists=True):
    require(isinstance(value, str) and value, "file path is missing", "invalid-argument")
    path = Path(value).resolve()
    require(path.is_relative_to(directory) and path != directory,
            "file must be inside this copied session", "invalid-path")
    if exists:
        require(path.is_file() and path.stat().st_nlink == 1,
                "session input must be a separate regular file, not a hard link", "invalid-path")
    else:
        require(not path.exists(), "output already exists", "output-exists")
        require(path.parent.is_dir(), "output folder does not exist", "invalid-path")
    return path


def _crypt(data, seed):
    result = bytearray(data)
    for offset in range(0, len(result), 2):
        seed = (seed * 1103515245 + 24691) & 0xFFFFFFFF
        value = struct.unpack_from("<H", result, offset)[0] ^ (seed >> 16)
        struct.pack_into("<H", result, offset, value)
    return bytes(result)


def decode_party(data, offsets):
    """Decode a copy. Never decrypt or repair live game data in place."""
    require(len(data) == 8 + 6 * 236, "party byte count differs")
    capacity, count = struct.unpack_from("<II", data)
    require(capacity == 6 and count <= 6, "party header is invalid")
    result = []
    for slot in range(count):
        record = data[8 + slot * 236:8 + (slot + 1) * 236]
        pid, flags, checksum = struct.unpack_from("<IHH", record)
        require(not flags & 4, f"party slot {slot} has a failed checksum")
        box = record[8:136] if flags & 2 else _crypt(record[8:136], checksum)
        require(sum(struct.unpack("<64H", box)) & 0xFFFF == checksum,
                f"party slot {slot} checksum differs")
        party = record[136:] if flags & 1 else _crypt(record[136:], pid)
        a, b, _, _ = offsets[(pid & 0x3E000) >> 13]
        species = struct.unpack_from("<H", box, a)[0]
        moves = list(struct.unpack_from("<4H", box, b))
        ivs = struct.unpack_from("<I", box, b + 16)[0]
        result.append({"slot": slot, "species": species, "personality": pid,
                       "identityVerified": True, "isEgg": bool(ivs & (1 << 30)),
                       "form": box[b + 24] >> 3, "level": party[4],
                       "hp": struct.unpack_from("<H", party, 6)[0],
                       "maxHp": struct.unpack_from("<H", party, 8)[0],
                       "status": struct.unpack_from("<I", party)[0], "moves": moves,
                       "pp": list(box[b + 8:b + 12]), "checksum": checksum})
    return result


def actor_identity_checks(actor, source, engine, context, slot):
    """Keep every failed binding test visible; never accept species alone."""
    handle = actor["handle"]
    return {
        "roleSlot": (actor["role"] == "WILD" and slot < 7) or
                    (actor["role"] in ("FOLLOWER", "MOUNTED") and slot == 7),
        "presentationAttached": bool(actor["presentationAttached"]),
        "sourceActive": live_spawn_flags(source.get("active")),
        "species": actor["species"] == source["species"],
        "personality": actor["subjectIdentity"] == source["personality"],
        "fieldEpoch": handle["fieldEpoch"] == context["fieldEpoch"],
        "mapGeneration": handle["mapGeneration"] == context["mapGeneration"],
        "encounterGeneration": handle["encounterGeneration"] == source["encounter_generation"],
        "engineInManager": bool(engine["in_manager"]),
        "engineActive": bool(engine["active"]),
        "engineManager": engine["object_manager"] == engine["current_manager"],
        "engineObjectId": engine["object_id"] == source["object_id"] == 0xE0 + slot,
        "engineMap": engine["object_map_id"] == source["map_id"] == context["mapId"],
        "engineScript": engine["script_id"] == 2074,
        **{key: actor.get(key, 0) > 0 for key in
           ("authorityGeneration", "engineAnchorGeneration", "presentationGeneration")},
    }


# Fixed stock Thumb entry points, checked against the local vanilla source and
# stock ARM9 disassembly. Live bytes must also match this session's packaged ROM.
STOCK_CALLS = {
    "corner_collision": (0x0205DA34, 3),
    "transition": (0x02055C9C, 7),  # NewFieldTransitionEnvironment
    "allocate_task_environment": (0x0201AACC, 2),  # Heap_AllocAtEnd
    "allocate_work_memory": (0x0201AA8C, 2),  # Heap_Alloc, fixed prepared capacity probe
    "create_field_task": (0x020504F0, 3),
    "allocate_mon": (0x0206DD2C, 1),
    "create_mon": (0x0206DE38, 8),
    "set_mon": (0x0206EC40, 3),
    "get_mon": (0x0206E540, 3),
    "level_exp": (0x0206FD00, 2),
    "recalc_mon": (0x0206E250, 1),
    "copy_party_mon": (0x02074740, 3),
    "add_party_mon": (0x02074524, 2),
    "free": (0x0201AB0C, 1),
}
STOCK_CALLBACKS = {"script_warp_task": 0x0205380C}
LINKED_CALLS = {
    "corner_landing": ("WILD_SYMBOLS", "OverworldWildSpawns_ValidateHopLandingValue", 8),
    "mount_hop_landing": ("MOUNT_SYMBOLS", "OverworldMount_IsLandingTileAllowed", 2),
    "reduce_walk": ("ACTOR_SYMBOLS", "ActorSystem_ReduceWalk", 1),
    "resolve_behavior": ("ACTOR_SYMBOLS", "BehaviorResolver_Resolve", 5),
    "inspect_actor": ("ACTOR_SYMBOLS", "OverworldActorSystem_InspectImpl", 2),
    "poll": ("TASK6_SYMBOLS", "PokemonMoveHistoryTask6_FieldReadyDiagnosticPollImpl", 1),
    "finalize_spawn": ("WILD_SYMBOLS", "OverworldWildSpawns_FinalizePreparedSpawn", 5),
    "spawn_encounter": ("WILD_SYMBOLS", "OverworldWildSpawns_SpawnPreparedEncounter", 5),
    "selector_close": ("SELECTOR_SYMBOLS", "OverworldFollowerSelectorUI_Close", 0),
    "selector_refresh": ("SELECTOR_SYMBOLS", "OverworldFollowerSelectorUI_BeginPartySnapshot", 0),
    "replace_move": ("WALK_SYMBOLS", "PokemonMoveHistory_ReplaceMoveImpl", 3),
    "delete_move": ("WALK_SYMBOLS", "PokemonMoveHistory_DeleteMoveSlotImpl", 2),
    "seed_history": ("WALK_SYMBOLS", "PokemonMoveHistory_SeedImpl", 2),
    "recall_follower": ("SELECTOR_SYMBOLS", "OverworldWildSpawns_SelectFollowerPartySlot", 2),
    "selected_follower_slot": ("SELECTOR_SYMBOLS", "OverworldWildSpawns_GetSelectedFollowerPartySlot", 1),
    "mount_selected_follower": ("WILD_SYMBOLS", "OverworldWildSpawns_BeginMountSelectedFollower", 2),
    "cancel_mount": ("MOUNT_SYMBOLS", "OverworldMount_Cancel", 1),
}
ELF_FILES = {
    "ACTOR_SYMBOLS": "overworld_actor_system_overlay_linked.o",
    "TASK6_SYMBOLS": "pokemon_move_history_task6_overlay_linked.o",
    "WILD_SYMBOLS": "overworld_wild_spawns_overlay_linked.o",
    "SELECTOR_SYMBOLS": "overworld_follower_selector_overlay_linked.o",
    "WALK_SYMBOLS": "pokemon_move_history_overlay_linked.o",
    "MOUNT_SYMBOLS": "overworld_mount_overlay_linked.o",
}


def _elf_code(path, address, size):
    """Read an allocated executable ELF32 section; no objdump text guessing."""
    data = path.read_bytes()
    require(data[:7] == b"\x7fELF\x01\x01\x01", "linked file is not little-endian ELF32")
    shoff = struct.unpack_from("<I", data, 32)[0]
    stride, count = struct.unpack_from("<HH", data, 46)
    for index in range(count):
        _, kind, flags, base, offset, length = struct.unpack_from("<6I", data, shoff + stride * index)
        if kind == 1 and flags & 6 == 6 and base <= address and address + size <= base + length:
            return data[offset + address - base:offset + address - base + size]
    raise DevtoolsFailure("abi-mismatch", f"linked function {address:#x} has no executable bytes")


def _elf_function_extent(path, name):
    """Use the linked FUNC extent, not a prologue-only dependency check."""
    data = path.read_bytes()
    require(data[:7] == b"\x7fELF\x01\x01\x01", "linked file is not little-endian ELF32")
    shoff = struct.unpack_from("<I", data, 32)[0]
    stride, count = struct.unpack_from("<HH", data, 46)
    matches = []
    for index in range(count):
        section = struct.unpack_from("<10I", data, shoff + stride * index)
        if section[1] != 2:
            continue
        require(section[9] == 16 and section[5] % 16 == 0, "linked symbol layout differs", "abi-mismatch")
        strings = struct.unpack_from("<10I", data, shoff + stride * section[6])
        names = data[strings[4]:strings[4] + strings[5]]
        for offset in range(section[4], section[4] + section[5], 16):
            label, address, size, info, _other, _section = struct.unpack_from("<IIIBBH", data, offset)
            if names[label:].split(b"\0", 1)[0] == name.encode("ascii"):
                require(info & 15 == 2 and size > 0, "linked function has no typed extent", "abi-mismatch")
                matches.append((address & ~1, size))
    require(len(matches) == 1, f"linked function {name} is not unique", "abi-mismatch")
    return matches[0]


@dataclass(frozen=True)
class Call:
    name: str
    args: tuple


def native_cpu_diagnostics(session):
    """Capture the stopped native call BEFORE destruction, never after it."""
    result = {"boundary": "failed-native-call-before-core-close"}
    try:
        registers = session.emu.memory.register_arm9
        values = {name: getattr(registers, name) & 0xFFFFFFFF
                  for name in [*(f"r{i}" for i in range(13)), "sp", "lr", "pc", "cpsr", "spsr"]}
        result["registers"] = values
        result["irqVector"] = session._native_irq_vector()
        result["instructionSet"] = "Thumb" if values["cpsr"] & 0x20 else "ARM"
        get_next = getattr(session.emu.memory, "get_next_instruction", None)
        if get_next is not None:
            result["nextInstruction"] = get_next() & 0xFFFFFFFF
        candidates = [(address & ~1, name, "stock-call") for name, (address, _count) in STOCK_CALLS.items()]
        for table in ("ACTOR_SYMBOLS", "WILD_SYMBOLS", "MOUNT_SYMBOLS", "WALK_SYMBOLS", "TASK6_SYMBOLS", "SELECTOR_SYMBOLS"):
            candidates.extend((address & ~1, name, table) for name, address in getattr(session.rt, table, {}).items())
        result["nearestSymbols"] = {}
        for register in ("pc", "lr"):
            address = values[register] & ~1
            lower = [item for item in candidates if item[0] <= address]
            if lower:
                base, name, table = max(lower)
                result["nearestSymbols"][register] = {"name": name, "address": base, "offset": address - base,
                                                       "table": table, "scope": "nearest-name-not-function-size-proof"}
        for label, address, size in (("instructionBytes", values["pc"] & ~1, 16), ("stackBytes", values["sp"], 64)):
            try:
                result[label] = {"address": address, "hex": session.read(address, size).hex()}
            except Exception as error:
                result[label] = {"address": address, "error": f"{type(error).__name__}: {error}"}
    except Exception as error:
        result["diagnosticError"] = f"{type(error).__name__}: {error}"
    return result


def native_callback_cpu_observation(session, registered_address):
    """Record CPU/pipeline evidence; do not infer CPU from a hook's label."""
    memory = session.emu.memory
    result = {"registeredAddress": registered_address,
              "actualCallback": deepcopy(getattr(session.party_getter_hooks, "current_callback", None))}
    for label, attribute in (("arm9", "register_arm9"), ("arm7", "register_arm7")):
        registers = getattr(memory, attribute, None)
        if registers is None:
            result[label] = {"available": False}
            continue
        pc, cpsr = registers.pc & 0xFFFFFFFF, registers.cpsr & 0xFFFFFFFF
        width = 2 if cpsr & 0x20 else 4
        result[label] = {"pc": pc, "cpsr": cpsr,
                         "executionAddressFromPc": (pc - 2 * width) & 0xFFFFFFFF}
    get_next = getattr(memory, "get_next_instruction", None)
    if get_next is not None:
        result["arm9"]["nextInstruction"] = get_next() & 0xFFFFFFFF
    return result


TRAMPOLINE_BYTES = 0x600
TRAMPOLINE_HEAP = 11
TRAMPOLINE_CONTROL = 0x100
TRAMPOLINE_SCRATCH = 0x200
TRAMPOLINE_LOOP = 0x18
TRAMPOLINE_GUARD = b"OWDEVTOOLS-GUARD"
# Stack depth below CreateBoxMonData's EXP call site. Each stock function's
# push is fixed in the authenticated 0x0206FD00..0x0206FD68 code span.
EXP_INTERNAL_POINTS = (
    ("personal-call", 0x0206FD06, 8), ("personal-return", 0x0206FD0A, 8),
    ("growth-call", 0x0206FD0C, 8), ("growth-return", 0x0206FD10, 8),
    ("allocate-call", 0x0206FD4C, 24), ("allocate-return", 0x0206FD50, 24),
    ("load-call", 0x0206FD56, 24), ("load-return", 0x0206FD5A, 24),
    ("archive-call", 0x0206FD28, 40), ("archive-return", 0x0206FD2C, 40),
    ("free-call", 0x0206FD60, 24), ("free-return", 0x0206FD64, 24),
)
MOVESET_INTERNAL_POINTS = (
    ("allocate-call", 0x020712E2), ("allocate-return", 0x020712E6),
    ("load-call", 0x0207131A), ("load-return", 0x0207131E),
    ("free-call", 0x02071362), ("free-return", 0x02071366),
)


def native_trampoline_code(base):
    """Fixed ARMv5 instructions, independently assembled in the host test.

    Thumb BX PC enters ARM without changing CPU mode/interrupt masks. Native
    STM/LDM and BLX own the real stack and calls. Only flags are restored by
    MSR CPSR_f. ARMv5 LDR PC returns to the separate Thumb continuation;
    LR retains its original value, which a POP-PC callee need not preserve.
    """
    words = [0xE59F3120, 0xE92D5FFF, 0xE59F411C, 0xE24DD018, 0xE59F5050,
             0xE595C000, 0xE35C0000, 0x0A00000D,
             0xE5950014, 0xE58D0000, 0xE5950018, 0xE58D0004,
             0xE595001C, 0xE58D0008, 0xE5950020, 0xE58D000C,
             0xE995000F, 0xE12FFF3C, 0xE5850024, 0xE3A00001,
             0xE5850028, 0xEAFFFFEE, 0xE28DD018, 0xE128F004,
             0xE8BD5FFF, 0xE59FF0C4, base + TRAMPOLINE_CONTROL]
    return bytes.fromhex("7847c046") + struct.pack("<27I", *words)


PARTY_WORK_HEAP_SITES = (
    # name, owning native function, allocator, size, allocation return,
    # allocation depth, free return, free depth (below owning function entry).
    ("exp", 0x0206FD30, 0x0201AA8C, 404, 0x0206FD50, 16, 0x0206FD64, 16),
    ("moveset", 0x020712D8, 0x0201AA8C, 164, 0x020712E6, 32, 0x02071366, 32),
    ("personal", 0x0206FA8C, 0x0201AA8C, 44, 0x0206FA98, 16, 0x0206FBC0, 8),
    ("stats", 0x0206E27C, 0x0201AA8C, 44, 0x0206E35C, 112, 0x0206E4E8, 112),
    ("mail", 0x0202B0C8, 0x0201AACC, 56, 0x0202B0D0, 8, 0x0206DE9E, 0),
)


class PreparedPartyWorkHeap:
    """Finite prepared-party temporary buffers; never a general heap rewrite.

    Each row is a source-reviewed native lifetime, including buffers whose
    allocating helper returns before its caller frees them. Nested pointers
    remain tracked separately (moveset contains a personal-data allocation).
    """
    def __init__(self, session, state):
        self.session, self.state = session, state
        self.owners, self.open = {}, []
        self.receipts = []

    def scope(self):
        s, state = self.session, self.state
        if (not s.prepared or not state["started"] or state["done"] or not state["callee_active"]
                or not state["calls"] or state["calls"][-1]["routine"] not in ("create_mon", "level_exp", "recalc_mon")):
            return None
        owner, expected = s._native_thread_ownership(), state["thread"]
        block = s.native_trampoline
        if (owner["mode"] != 0x1F or owner["irqDepth"] != 0 or owner["state"] != 1
                or any(owner[key] != expected[key] for key in ("pointer", "id", "stackTop", "stackBottom"))
                or block is None or block["fieldPointer"] != s.field_pointer()
                or block["heapGeneration"] != s.native_heap_generation):
            return None
        return state["calls"][-1]

    def owner_entry(self, site):
        token = self.scope()
        if token is not None:
            self.owners[site[0]] = {"token": token, "sp": self.session.emu.memory.register_arm9.sp & 0xFFFFFFFF}

    def growth_entry(self):
        self.owner_entry(PARTY_WORK_HEAP_SITES[0])

    def owned_frame(self, owner, depth):
        return (owner is not None and self.scope() is owner["token"]
                and self.session.emu.memory.register_arm9.sp & 0xFFFFFFFF == owner["sp"] - depth)

    def allocate_entry(self, allocator=0x0201AA8C):
        regs = self.session.emu.memory.register_arm9
        site = next((site for site in PARTY_WORK_HEAP_SITES if site[2] == allocator
                     and regs.lr & 0xFFFFFFFF == site[4] | 1 and regs.r1 == site[3]), None)
        if site is None or regs.r0 != 0:
            return
        owner = self.owners.get(site[0])
        if not self.owned_frame(owner, site[5]):
            return
        receipt = {"kind": "prepared-party-work-heap", "buffer": site[0], "preparedOnly": True,
            "routine": owner["token"]["routine"], "allocator": allocator, "callerReturn": site[4] | 1,
            "originalHeap": 0, "workHeap": 11, "bytes": site[3], "stack": regs.sp & 0xFFFFFFFF,
            "thread": self.state["thread"]["pointer"], "released": False}
        self.open.append({"site": site, "owner": dict(owner), "receipt": receipt})
        self.receipts.append(receipt)
        regs.r0 = 11

    def allocate_return(self, address=0x0206FD50):
        entry = next((entry for entry in self.open if entry["site"][4] == address
                      and "allocation" not in entry["receipt"] and self.owned_frame(entry["owner"], entry["site"][5])), None)
        if entry is None:
            return
        pointer = self.session.emu.memory.register_arm9.r0 & 0xFFFFFFFF
        receipt = entry["receipt"]
        receipt["allocation"] = pointer
        if pointer % 4 != 0 or not 0x02000004 <= pointer <= 0x02400000 - entry["site"][3]:
            raise DevtoolsFailure("native-party-work-allocation", "prepared party work allocation failed after capacity check", fatal=True)
        require(sum(item["receipt"].get("allocation") == pointer for item in self.open) == 1,
                "prepared buffers reused an outstanding pointer", "native-party-work-state")
        heap_id = self.session.read(pointer - 4, 1)[0]
        receipt["nativeHeaderHeap"] = heap_id
        require(heap_id == 11, "party allocation header differs from work heap", "native-party-work-state")

    def free_entry(self):
        regs = self.session.emu.memory.register_arm9
        for entry in self.open:
            site, receipt = entry["site"], entry["receipt"]
            if (self.owned_frame(entry["owner"], site[7]) and regs.lr & 0xFFFFFFFF == site[6] | 1
                    and regs.r0 & 0xFFFFFFFF == receipt.get("allocation")):
                receipt["freeEntry"] = {"pointer": regs.r0 & 0xFFFFFFFF, "callerReturn": site[6] | 1}

    def free_return(self, address=0x0206FD64):
        for entry in tuple(self.open):
            if entry["site"][6] == address and self.owned_frame(entry["owner"], entry["site"][7]):
                require("freeEntry" in entry["receipt"], "party work allocation has no matching native free", "native-party-work-state")
                entry["receipt"]["released"] = True
                self.open.remove(entry)


class FieldReturnBridge:
    """Fixed ABI calls from a captured, quiescent native field-poll return.

    A private native trampoline owns push/pop, argument setup, BLX and return.
    The host never writes SP/CPSR or fabricates a callee return. Its bootstrap
    supplies only two allocation arguments using the unchanged native stack.
    An incomplete call closes the whole disposable core;
    it never attempts to resume an interrupted callee by guessing registers.
    """

    def __init__(self, session):
        self.session = session

    def run(self, recipe, *, prepared_party_work_heap=False):
        s, rt, emu = self.session, self.session.rt, self.session.emu
        s.require_quiescent()
        poll = s.target("poll")
        state = {"error": None, "done": False, "entry": None, "return": None,
                 "registers": None, "calls": [], "started": False, "callee_active": False,
                 "dispatch_pending": False, "checkpoints": [], "checkpointCount": 0,
                 "firstBadCheckpoint": None, "firstCreateBoxEntry": None,
                 "lastThreadSwitch": None, "firstInvalidThreadSwitch": None,
                 "boxCallBoundaries": [], "boxCallBoundaryCount": 0,
                 "exp_owner_sp": None,
                 "moveset_owner_sp": None,
                 "bootstrap": None,
                 "pending_error": None, "stage": None, "waiting_return": False}
        regs = emu.memory.register_arm9
        require(type(prepared_party_work_heap) is bool and (not prepared_party_work_heap or s.prepared),
                "party work heap requires an explicit prepared party operation")
        exp_work = PreparedPartyWorkHeap(s, state) if prepared_party_work_heap else None
        # Reuse the existing dispatcher: overriding GetMonData's entry hook
        # would silently discard the independent natural getter observation.
        hooks, tokens = s.party_getter_hooks, []
        require(hooks.error is None, f"native observer already failed: {hooks.error}", "observation-failed")
        s.native_bridge_active = True
        health_exclusion_started = False

        def hook(address, callback, *, first=False):
            key = address & ~1
            existed = key in hooks.callbacks
            try:
                token = hooks.add(address, callback)
            except Exception:
                if not existed:
                    try:
                        emu.memory.register_exec(key, None)
                        hooks.callbacks.pop(key, None)
                    except Exception as cleanup_error:
                        raise DevtoolsFailure("native-hook-cleanup-failed", str(cleanup_error), fatal=True) from cleanup_error
                raise
            tokens.append(token)
            if first:
                callbacks = hooks.callbacks[token[0]]
                callbacks.remove(token[1])
                callbacks.insert(0, token[1])
            return token

        def validate_owner():
            owner = s._native_thread_ownership()
            expected = state["thread"]
            require(all(owner[key] == expected[key] for key in ("pointer", "id", "stackTop", "stackBottom"))
                    and owner["mode"] == 0x1F and owner["irqDepth"] == 0 and owner["state"] == 1,
                    "native call left its owning SDK thread", "native-thread-mismatch")
            require(owner["topGuard"] == 0x7BF9DD5B and owner["bottomGuard"] == 0xFDDB597D,
                    "native SDK thread stack guard changed", "native-stack-corrupt")

        def guarded(callback):
            def invoke():
                if state["error"] is not None:
                    return
                try:
                    callback()
                except Exception as error:
                    state["error"] = error
            return invoke

        def check_trampoline():
            block = s.native_trampoline
            require(block["fieldPointer"] == s.field_pointer()
                    and block["heapGeneration"] == s.native_heap_generation,
                    "native trampoline field/heap owner changed", "native-code-lifetime")
            require(s.read(block["address"], len(block["code"])) == block["code"]
                    and s.read(block["address"] + TRAMPOLINE_BYTES - 16, 16) == TRAMPOLINE_GUARD,
                    "owned native trampoline identity changed", "native-code-lifetime")

        def stop_native(error=None, result=None):
            state["pending_error"], state["result"] = error, result
            state["waiting_return"] = True
            s.write(state["control"], struct.pack("<I", 0))

        def command_boundary():
            validate_owner()
            check_trampoline()
            require(regs.sp & 0xFFFFFFFF == state["sp"], "native command frame differs", "native-stack-ownership")
            value = None
            if state["callee_active"]:
                result, completed = struct.unpack("<II", s.read(state["control"] + 36, 8))
                require(completed == 1, "native BLX did not produce a completion", "native-entry-missing")
                state["callee_active"] = False
                state["calls"][-1]["returnValue"] = result
                value = result
            require(not state["dispatch_pending"], "native call entry was not observed", "native-entry-missing")
            try:
                call = state["recipe"].send(value)
            except StopIteration as result:
                stop_native(result=result.value)
                return
            except Exception as error:
                stop_native(error=error)
                return
            try:
                require(isinstance(call, Call) and call.name != "poll", "unlisted bridge request")
                target = s.target(call.name)
                count = STOCK_CALLS.get(call.name, (None, LINKED_CALLS.get(call.name, (None, None, -1))[2]))[1]
                require(len(call.args) == count and 0 <= count <= 8, "native argument count differs")
                require(all(type(arg) is int and -0x80000000 <= arg <= 0xFFFFFFFF for arg in call.args),
                        "native argument is not a 32-bit value")
            except Exception as error:
                stop_native(error=error)
                return
            call_receipt = {"routine": call.name, "address": target,
                            "requestedArguments": [arg & 0xFFFFFFFF for arg in call.args]}
            state["calls"].append(call_receipt)
            state["dispatch_pending"] = True
            token = None

            def callee_entry():
                require(state["dispatch_pending"] and not state["callee_active"],
                        "unexpected native call entry", "native-entry-mismatch")
                validate_owner()
                require(regs.sp & 0xFFFFFFFF == state["sp"]
                        and regs.lr & 0xFFFFFFFF == s.native_trampoline["address"] + 0x4C,
                        "native BLX call frame/link differs", "native-entry-mismatch")
                observed = [getattr(regs, f"r{i}") & 0xFFFFFFFF for i in range(min(4, count))]
                if count > 4:
                    observed += list(struct.unpack("<" + "I" * (count - 4), s.read(state["sp"], (count - 4) * 4)))
                call_receipt.update(entryArguments=observed, entryStack=regs.sp & 0xFFFFFFFF,
                                    entryLink=regs.lr & 0xFFFFFFFF, entryCpsr=regs.cpsr & 0xFFFFFFFF,
                                    entryBoundary="native-trampoline-BLX-entry")
                require(observed == call_receipt["requestedArguments"],
                        "native entry arguments differ", "native-entry-mismatch")
                state["dispatch_pending"], state["callee_active"] = False, True
                hooks.remove(token)

            token = hook(target, guarded(callee_entry), first=True)
            arguments = [arg & 0xFFFFFFFF for arg in call.args] + [0] * (8 - count)
            s.write(state["control"], struct.pack("<11I", target | 1, *arguments, 0, 0))

        def start_trampoline():
            check_trampoline()
            block = s.native_trampoline["address"]
            state["control"] = block + TRAMPOLINE_CONTROL
            s.write(state["control"], struct.pack("<14I", *([0] * 11), state["registers"][3],
                                                state["cpsr"], state["return"] | 1))
            state["recipe"] = recipe(block + TRAMPOLINE_SCRATCH)
            state["stage"] = "native"
            hook(block + TRAMPOLINE_LOOP, guarded(command_boundary), first=True)
            regs.pc = block
            emu.memory.set_next_instruction(block)

        def bootstrap():
            # Heap11 belongs to FieldSystem_New/Delete, not a single map.
            # ScriptWarp keeps its own heap11 environment through the entire
            # transition. The persistent destroy observer expires this block
            # before a full field teardown; no self-free or heap0 pressure.
            # This is the only direct
            # bootstrap call: unchanged native SP/CPSR, two input registers.
            # Poll itself returns with POP PC, so its leftover LR is not the
            # continuation. Give the allocator that separate native return.
            target = s.target("allocate_task_environment")
            state["stage"] = "bootstrap"
            state["bootstrap"] = {"routine": "allocate_task_environment", "address": target,
                                  "requestedArguments": [TRAMPOLINE_HEAP, TRAMPOLINE_BYTES]}
            token = None
            def allocation_entry():
                validate_owner()
                require(regs.sp == state["original_sp"] and regs.lr & ~1 == state["return"],
                        "native allocation bootstrap frame differs", "native-entry-mismatch")
                regs.r0, regs.r1 = TRAMPOLINE_HEAP, TRAMPOLINE_BYTES
                state["bootstrap"].update(entryArguments=[regs.r0, regs.r1], entryStack=regs.sp & 0xFFFFFFFF,
                                          entryLink=regs.lr & 0xFFFFFFFF, entryCpsr=regs.cpsr & 0xFFFFFFFF)
                state["callee_active"] = True
                hooks.remove(token)
            token = hook(target, guarded(allocation_entry), first=True)
            regs.lr = state["return"] | 1
            regs.pc = target
            emu.memory.set_next_instruction(target)

        def returned():
            nonlocal health_exclusion_started
            if state["done"]:
                return
            if not state["started"]:
                if regs.sp != state["entry"]:
                    return
                s.require_quiescent()
                require(regs.cpsr & 0x20 and regs.cpsr & 0x1F == 0x1F,
                        "field callback is not Thumb system mode")
                old_sp = regs.sp
                owner = s._native_thread_ownership()
                call_sp = old_sp - 80  # native push14 registers + 24 argument bytes
                require(owner["stackTop"] + 4 + 0x1000 <= call_sp < old_sp <= owner["stackBottom"] - 4
                        and old_sp % 8 == 0,
                        "current SDK thread stack cannot fit the bounded call frame", "native-stack-ownership")
                state.update(registers=[getattr(regs, f"r{i}") & 0xFFFFFFFF for i in range(15)],
                             cpsr=regs.cpsr & 0xFFFFFFFF, original_sp=old_sp, thread=owner,
                             sp=call_sp, started=True)
                s.native_trampoline_in_use = True
                validate_owner()
                # Waiting for this natural return is normal game execution.
                # Exclude cycles only once the bridge is about to take over.
                if getattr(s, "runtime_health", None) is not None:
                    s._check_runtime_health("begin_native_call")
                    health_exclusion_started = True
                    s.native_health_exclusion_active = True
                if getattr(s, "native_trampoline", None) is None:
                    bootstrap()
                else:
                    start_trampoline()
            elif regs.sp == state["original_sp"] and state["stage"] == "bootstrap":
                validate_owner()
                require(state["callee_active"], "bootstrap entry was not observed", "native-entry-missing")
                pointer = regs.r0 & 0xFFFFFFFF
                state["bootstrap"].update(returnValue=pointer, returnStack=regs.sp & 0xFFFFFFFF,
                                          returnLink=regs.lr & 0xFFFFFFFF, returnCpsr=regs.cpsr & 0xFFFFFFFF,
                                          returnPc=regs.pc & 0xFFFFFFFF, continuation=state["return"],
                                          returnBoundary="observed-allocator-return-before-validation")
                require(pointer % 4 == 0 and 0x02000000 <= pointer <= 0x02400000 - TRAMPOLINE_BYTES,
                        f"native trampoline allocation failed: heap {TRAMPOLINE_HEAP}, pointer {pointer:#010x}",
                        "allocation-failed")
                state["callee_active"] = False
                # Restore only bootstrap-clobbered GPRs. Native allocation has
                # already returned on the unchanged stack; never write SP/PSR.
                for index in range(13):
                    setattr(regs, f"r{index}", state["registers"][index])
                regs.lr = state["registers"][14]
                code = native_trampoline_code(pointer)
                s.write(pointer, code)
                s.write(pointer + TRAMPOLINE_BYTES - 16, TRAMPOLINE_GUARD)
                s.native_trampoline = {"address": pointer, "bytes": TRAMPOLINE_BYTES, "heapId": TRAMPOLINE_HEAP,
                                       "code": code, "lifetime": "field-system-heap11",
                                       "fieldPointer": s.field_pointer(), "heapGeneration": s.native_heap_generation}
                start_trampoline()
            elif regs.sp == state["original_sp"] and state["stage"] == "native":
                validate_owner()
                require(state["waiting_return"] and not state["callee_active"] and not state["dispatch_pending"],
                        "native trampoline returned before completing commands", "native-entry-missing")
                require([getattr(regs, f"r{i}") & 0xFFFFFFFF for i in range(15)] == state["registers"]
                        and regs.cpsr & 0xFFFFFFFF == state["cpsr"],
                        "native trampoline caller restoration differs", "native-caller-corrupt")
                block = s.native_trampoline
                state["completed_trampoline"] = {"address": block["address"], "bytes": TRAMPOLINE_BYTES,
                    "heapId": TRAMPOLINE_HEAP, "lifetime": block["lifetime"], "fieldPointer": block["fieldPointer"],
                    "heapGeneration": block["heapGeneration"], "codeSha256": hashlib.sha256(block["code"]).hexdigest()}
                s.native_trampoline_in_use = False
                state["done"] = True

        def entry():
            if state["entry"] is not None:
                return
            if regs.r0 != s.field_pointer():
                return
            s.require_quiescent()
            address = regs.lr & ~1
            code = s.packaged_code(address, 4)
            require(regs.lr & 1 and code == s.read(address, 4),
                    "natural poll return is not authenticated Thumb code")
            # Only the reviewed literal-load return seam is safe to redirect:
            # it reads code and changes one low register, not SP or game data.
            require(code == bytes.fromhex("244b254a"),
                    "native poll return is not a safe Thumb literal-load seam", "abi-mismatch")
            state["entry"], state["return"] = regs.sp, address
            hook(address, guarded(returned), first=True)

        def checkpoint(kind, address):
            if not state["started"] or state["done"]:
                return
            cpsr, sp = regs.cpsr & 0xFFFFFFFF, regs.sp & 0xFFFFFFFF
            if kind.startswith("level-exp-internal-"):
                depth = next(depth for name, site, depth in EXP_INTERNAL_POINTS if site == address)
                if (state["exp_owner_sp"] is None or sp != state["exp_owner_sp"] - depth
                        or not state["callee_active"] or state["calls"][-1]["routine"] != "create_mon"):
                    return
            if kind.startswith("moveset-internal-"):
                if (state["moveset_owner_sp"] is None or sp != state["moveset_owner_sp"] - 32
                        or not state["callee_active"] or state["calls"][-1]["routine"] != "create_mon"):
                    return
            # This conditional pop only executes when Z is set.
            if kind == "irq-return-if-idle" and not cpsr & 0x40000000:
                return
            item = {"kind": kind, "address": address, "cpsr": cpsr, "sp": sp,
                    "spsr": regs.spsr & 0xFFFFFFFF,
                    "irqVector": s._native_irq_vector(),
                    "lr": regs.lr & 0xFFFFFFFF,
                    "registers": [getattr(regs, f"r{i}") & 0xFFFFFFFF for i in range(4)],
                    "call": state["calls"][-1]["routine"] if state["calls"] else None}
            item["callbackCpu"] = native_callback_cpu_observation(s, address)
            target = None
            if kind == "irq-dispatch":
                target = regs.r0 & 0xFFFFFFFF
            elif kind.startswith("irq-return"):
                # The stock IRQ wrapper saves its BIOS return above the six
                # BIOS-saved registers (r0-r3, r12, interrupted LR). Keep the
                # raw frame as well as its documented interpretation: a later
                # bad pop must not hide whether the first frame was damaged.
                words = list(struct.unpack("<7I", s.read(sp, 28)))
                item["irqStackWords"] = words
                item["savedInterruptedLink"] = words[6]
                item["savedInterruptedResume"] = (words[6] - 4) & 0xFFFFFFFF
                target = words[0]
            elif kind == "irq-entry":
                words = list(struct.unpack("<6I", s.read(sp, 24)))
                item["biosStackWords"] = words
                item["savedInterruptedLink"] = words[5]
                item["savedInterruptedResume"] = (words[5] - 4) & 0xFFFFFFFF
            elif kind == "create-box-mon-entry":
                item["stackArguments"] = list(struct.unpack("<4I", s.read(sp, 16)))
                if state["firstCreateBoxEntry"] is None:
                    state["firstCreateBoxEntry"] = deepcopy(item)
            elif kind.startswith(("create-box-internal-", "level-exp-internal-", "moveset-internal-")):
                if kind.startswith("level-exp-internal-"):
                    item["workingRegisters"] = {f"r{index}": getattr(regs, f"r{index}") & 0xFFFFFFFF
                                                for index in (4, 5, 6)}
                if kind == "create-box-internal-level-exp-call":
                    state["exp_owner_sp"] = sp
                elif kind == "create-box-internal-level-exp-return":
                    state["exp_owner_sp"] = None
                elif kind == "create-box-internal-moveset-call":
                    state["moveset_owner_sp"] = sp
                elif kind == "create-box-internal-moveset-return":
                    state["moveset_owner_sp"] = None
                elif kind == "moveset-internal-allocate-return":
                    item["allocatedPointer"] = regs.r0 & 0xFFFFFFFF
                elif kind == "moveset-internal-load-call":
                    item.update(species=regs.r0 & 0xFFFFFFFF, form=regs.r1 & 0xFFFFFFFF,
                                destination=regs.r2 & 0xFFFFFFFF)
                elif kind == "level-exp-internal-allocate-return":
                    item["allocatedPointer"] = regs.r0 & 0xFFFFFFFF
                elif kind == "level-exp-internal-personal-return":
                    item["growthGroup"] = regs.r0 & 0xFFFFFFFF
                elif kind == "level-exp-internal-archive-call":
                    item.update(destination=regs.r0 & 0xFFFFFFFF, archiveId=regs.r1 & 0xFFFFFFFF,
                                memberId=regs.r2 & 0xFFFFFFFF)
                state["boxCallBoundaryCount"] += 1
                state["boxCallBoundaries"].append(deepcopy(item))
                if len(state["boxCallBoundaries"]) > 64:
                    state["boxCallBoundaries"].pop(0)
            elif kind == "irq-thread-chosen":
                item["chosenThread"] = s._native_thread_snapshot(regs.r1 & 0xFFFFFFFF)
                item["previousThreadPointer"] = regs.r0 & 0xFFFFFFFF
                state["lastThreadSwitch"] = {"chosen": deepcopy(item)}
            elif kind == "irq-thread-svc-pop":
                item["savedChosenPointer"] = struct.unpack("<I", s.read(sp, 4))[0]
                bundle = state["lastThreadSwitch"]
                if bundle is None:
                    state["lastThreadSwitch"] = bundle = {"chosenMissing": True}
                bundle["svcPop"] = deepcopy(item)
            elif kind == "irq-thread-restore":
                item["restoreThread"] = s._native_thread_snapshot(regs.r1 & 0xFFFFFFFF)
                bundle = state["lastThreadSwitch"]
                if bundle is None:
                    state["lastThreadSwitch"] = bundle = {"chosenMissing": True}
                bundle["restore"] = deepcopy(item)
                chosen = bundle.get("chosen", {}).get("chosenThread", {})
                actual = item["restoreThread"]
                bundle["sameChosenPointer"] = chosen.get("pointer") == actual["pointer"]
                bundle["sameChosenContext"] = chosen.get("contextHex") == actual.get("contextHex")
                if (not actual.get("validContext") or not bundle["sameChosenPointer"]
                        or bundle.get("svcPop", {}).get("savedChosenPointer") != actual["pointer"]):
                    if state["firstInvalidThreadSwitch"] is None:
                        state["firstInvalidThreadSwitch"] = deepcopy(bundle)
            if target is not None:
                item["target"] = target
                item["targetInMappedCode"] = s._native_target_is_mapped_code(target)
                if not item["targetInMappedCode"] and state["firstBadCheckpoint"] is None:
                    if hasattr(s, "_native_irq_code_identity"):
                        item["irqCodeIdentity"] = s._native_irq_code_identity()
                    state["firstBadCheckpoint"] = deepcopy(item)
            state["checkpointCount"] += 1
            state["checkpoints"].append(item)
            if len(state["checkpoints"]) > 32:
                state["checkpoints"].pop(0)

        try:
            for kind, address in getattr(s, "_native_checkpoint_points", lambda: [])():
                hook(address, guarded(lambda kind=kind, address=address: checkpoint(kind, address)))
            if exp_work is not None:
                s.target("allocate_work_memory")
                s._authenticate_party_work_heap()
                for site in PARTY_WORK_HEAP_SITES:
                    hook(site[1], guarded(lambda site=site: exp_work.owner_entry(site)), first=True)
                    hook(site[4], guarded(lambda site=site: exp_work.allocate_return(site[4])), first=True)
                    hook(site[6], guarded(lambda site=site: exp_work.free_return(site[6])), first=True)
                for allocator in (0x0201AA8C, 0x0201AACC):
                    hook(allocator, guarded(lambda allocator=allocator: exp_work.allocate_entry(allocator)), first=True)
                hook(0x0201AB0C, guarded(exp_work.free_entry), first=True)
            hook(poll, guarded(entry), first=True)
            for _ in range(180):
                s.cycle(1)
                require(hooks.error is None, f"native observer failed: {hooks.error}", "observation-failed")
                if state["error"] is not None or state["done"]:
                    break
            if state["error"] is not None:
                raise state["error"]
            require(state["done"], "native field call exceeded 180 native cycles", "native-timeout")
            if exp_work is not None and not all(item["released"] for item in exp_work.receipts):
                raise DevtoolsFailure("native-party-work-state", "prepared party allocation was not freed", fatal=True)
            if state["pending_error"] is not None:
                raise state["pending_error"]
            return {"value": state["result"], "calls": state["calls"],
                    "bootstrap": state["bootstrap"],
                    "nativeHeapAdaptation": [] if exp_work is None else exp_work.receipts,
                    "nativeCheckpoints": state["checkpoints"], "checkpointCount": state["checkpointCount"],
                    "firstBadCheckpoint": state["firstBadCheckpoint"],
                    "firstCreateBoxEntry": state["firstCreateBoxEntry"],
                    "boxCallBoundaries": state["boxCallBoundaries"],
                    "boxCallBoundaryCount": state["boxCallBoundaryCount"],
                    "lastThreadSwitch": state["lastThreadSwitch"],
                    "firstInvalidThreadSwitch": state["firstInvalidThreadSwitch"],
                    "nativeDependencies": deepcopy(getattr(s, "native_dependency_checks", {})),
                    "stackOwnership": {"thread": state["thread"], "callSp": state["sp"],
                                       "hostRestoredFrameBytes": 0, "nativeFrameBytes": 80, "scratchBytes": 268},
                    "trampoline": state["completed_trampoline"],
                    "boundary": "native-field-command-trampoline", "preparedOnly": True}
        except Exception as error:
            details = {"calls": state["calls"], "boundary": "natural-field-ready-poll-return",
                       "bootstrap": state["bootstrap"],
                       "nativeHeapAdaptation": [] if exp_work is None else exp_work.receipts,
                       "nativeCallActive": state["callee_active"], "dispatchPending": state["dispatch_pending"],
                       "registersRestored": state["done"], "cpu": native_cpu_diagnostics(s),
                       "nativeCheckpoints": state["checkpoints"], "checkpointCount": state["checkpointCount"],
                       "firstBadCheckpoint": state["firstBadCheckpoint"],
                       "firstCreateBoxEntry": state["firstCreateBoxEntry"],
                       "boxCallBoundaries": state["boxCallBoundaries"],
                       "boxCallBoundaryCount": state["boxCallBoundaryCount"],
                       "lastThreadSwitch": state["lastThreadSwitch"],
                       "firstInvalidThreadSwitch": state["firstInvalidThreadSwitch"],
                       "nativeDependencies": deepcopy(getattr(s, "native_dependency_checks", {})),
                       "stackOwnership": {"thread": state.get("thread"), "callSp": state.get("sp"),
                                          "hostRestoredFrameBytes": 0, "nativeFrameBytes": 80},
                       "ownedAllocations": deepcopy(getattr(s, "native_allocations", {}))}
            if isinstance(error, DevtoolsFailure):
                error.details = {**(error.details or {}), "bridge": details}
            if getattr(error, "fatal", False) or state["started"] and not state["done"] or details["ownedAllocations"]:
                s.close()
                if error is getattr(s, "runtime_health_failure", None):
                    # Closing an unsafe bridge must not replace the first
                    # health failure or its original CPU/queue evidence.
                    raise
                raise DevtoolsFailure("native-call-aborted", str(error), fatal=True, details=details) from error
            raise
        finally:
            s.native_bridge_active = False
            s.native_health_exclusion_active = False
            s.native_trampoline_in_use = False
            if s.emu is not None:
                for token in tokens:
                    hooks.remove(token)
                rt.h.set_key_mask(emu, 0)
                if health_exclusion_started:
                    s._check_runtime_health("complete_native_call")


class DevtoolsSession:
    def __init__(self, rt, rom, save, session_dir):
        self.rt = rt
        self.directory = Path(session_dir).resolve()
        require(self.directory.is_dir(), "session folder is missing", "invalid-path")
        self.rom = owned_path(rom, self.directory)
        self.save = owned_path(save, self.directory)
        require(self.rom != self.save, "ROM and save must be different files")
        self.rom_hash = hashlib.sha256(self.rom.read_bytes()).hexdigest()
        require(self.rom_hash == hashlib.sha256((rt.REPO / "test.nds").read_bytes()).hexdigest(),
                "copied ROM differs from the current linked candidate", "stale-rom")
        self.save_hash = hashlib.sha256(self.save.read_bytes()).hexdigest()
        self._load_package()
        self.party_offsets = SUBSTRUCT_OFFSETS
        self.emu = None
        self.prepared = False
        self.personality_sequence = 0
        self.closed = False
        self.completed_frames = 0
        self.latest_frame = None
        self.latest_party = None
        self.latest_party_frame = None
        self.party_getter_checks = {}
        self.party_getter_hooks = None
        self.native_bridge_active = False
        self.native_health_exclusion_active = False
        self.native_allocations = {}
        self.native_heap_generation = 0
        self.native_trampoline = None
        self.native_trampoline_in_use = False
        self.pending_samples = None
        self.sample_error = None
        self.sampling_hook = None
        self.call_targets = {}
        self.semantic_trace = None
        self.native_observation = None
        self.script_warp_heap_free_observer = None
        self.observer_control = None
        self.route_control = None
        self.chain_retry_control = None
        self.walk_intent = None
        self.walk_policy_control = None
        self.mount_pacing = None
        self.wild_walk = None
        self.wild_ledge = None
        self.walk_corner = None
        self.walk_matrix = None
        self.stomp_feedback = None
        self.crash_feedback = None
        self.trace_request = None
        self.trace_events = []
        self.trace_events_dropped = 0
        self.trace_observing = False
        self.step_release_at_frame = None
        require(rt.ACTOR_DESCRIPTOR["state"]["offsets"]["actors"] == 68
                and rt.ACTOR_DESCRIPTOR["state"]["offsets"]["fieldEpoch"] == 12,
                "diagnostic actor context layout changed", "abi-mismatch")
        rt.ROM = self.rom
        self.emu = rt.h.create_emulator()
        try:
            rt.boot(self.emu, self.save, self.save.suffix.lower() == ".dsv", on_rom_open=self._install_sampler)
        except Exception:
            self.close()
            raise
        self.bridge = FieldReturnBridge(self)
        from tools.overworld.devtools_runtime_health import RuntimeHealthMonitor
        self.runtime_health = RuntimeHealthMonitor(self.completed_frames, rt.EXECUTED_FRAME_COUNT)
        self.runtime_health_failure = None

    def _prepared_personality(self, args):
        if "personality" in args:
            return integer(args["personality"], "personality", 1, 0xFFFFFFFF)
        self.personality_sequence += 1
        digest = hashlib.sha256((self.rom_hash + ":" + self.save_hash + ":" +
                                 str(self.personality_sequence)).encode("ascii")).digest()
        return int.from_bytes(digest[:4], "little") or 1

    def prepare_observation(self):
        """Retire empty setup IRQ hooks once; no native calls or frame credit."""
        require(self.emu is not None, "session is closed", "closed")
        require(not any(getattr(self, name, False) for name in (
            "native_bridge_active", "native_trampoline_in_use", "native_health_exclusion_active")),
            "observation preparation during a native call", "observation-prepare-active")
        if getattr(self, "_observation_prepare_error", None) is not None:
            raise self._observation_prepare_error
        if getattr(self, "_observation_setup", None) is not None:
            return deepcopy(self._observation_setup)
        # Exactly the stock IRQ subset of _native_checkpoint_points. Other
        # persistent entry/return observers are not part of this retirement.
        points = (("irq-entry", 0x01FF8000), ("irq-dispatch", 0x01FF804C),
                  ("irq-return-if-idle", 0x01FF80B4), ("irq-after-idle-return", 0x01FF80B8),
                  ("irq-return-no-switch", 0x01FF80F4), ("irq-thread-chosen", 0x01FF8120),
                  ("irq-thread-svc-pop", 0x01FF8178), ("irq-thread-restore", 0x01FF8188),
                  ("irq-return-thread-switch", 0x01FF81A0))
        receipt = {"schemaVersion": 1, "frame": self.completed_frames,
                   "nativeCycle": self.rt.EXECUTED_FRAME_COUNT, "advancedFrames": 0,
                   "onePassPerCore": True,
                   "removed": [], "retained": [],
                   "scope": "one-time empty setup IRQ dispatcher retirement; no gameplay mutation"}
        self._observation_setup = receipt
        try:
            hooks = self.party_getter_hooks
            for name, address in points:
                row = {"name": name, "address": address}
                if hooks.retire_empty(address):
                    receipt["removed"].append(row)
                elif address in hooks.callbacks:
                    receipt["retained"].append({**row, "reason": "active-listeners"})
            return deepcopy(receipt)
        except Exception as error:
            # No retry of a partial pass: at most nine replacement C callbacks
            # can be allocated if later prepared work re-adds these addresses.
            failure = DevtoolsFailure("observation-prepare-failed", str(error),
                                      details={"observationSetup": deepcopy(receipt)})
            self._observation_prepare_error = failure
            raise failure from error

    def _install_sampler(self):
        """The complete main task queue is the shared observation boundary."""
        self.callback_costs = CallbackCosts()
        address = self.rt.MAIN_TASK_QUEUE_RETURN
        expected = (self.rt.REPO / "base/arm9.bin").read_bytes()[address - 0x02000000 - 8:address - 0x02000000 + 4]
        require(self.packaged_code(address - 8, 12) == expected,
                "main-queue completion opcode identity differs", "abi-mismatch")
        self.sampling_hook = address
        self._install_party_getter_checks()
        self._install_heap_lifetime_observer()
        self._install_native_free_guard()
        from tools.overworld.devtools_observer import NativeObservation
        self.native_observation = NativeObservation(self, self.party_getter_hooks, _elf_code)
        self.native_observation.install()
        def completed(_address, _size):
            self.completed_frames += 1
            phase = getattr(self, "input_step_phase", None)
            if phase is not None and phase["polled"]:
                phase["consumed"] += 1
                phase["polled"] = False
                if phase["consumed"] >= phase["requested"]:
                    self.rt.h.set_key_mask(self.emu, 0)
            self.native_observation.completed_frame(self.completed_frames)
            if self.step_release_at_frame is not None and self.completed_frames >= self.step_release_at_frame:
                self.rt.h.set_key_mask(self.emu, 0)
            if self.sample_error is not None:
                return
            try:
                guest_queue_clock = self._read_guest_queue_clock()
                # A completed queue still exists during title/map teardown.
                # Record its absence, not the last field's actors or pose.
                rt, emu = self.rt, self.emu
                state = rt.ACTOR_DESCRIPTOR["state"]["address"]
                magic, field = rt.unsigned(emu, state), rt.unsigned(emu, rt.G_FIELD_SYS_PTR)
                if magic != 0x5353574F or not field:
                    self._record_field_absence(field, magic, guest_queue_clock=guest_queue_clock)
                    return
                availability = self._field_actor_availability(field)
                if availability["reason"] is not None:
                    self._record_field_absence(field, magic, availability, guest_queue_clock=guest_queue_clock)
                    return
                if getattr(self, "observer_control", None) is not None:
                    self.observer_control.completed_boundary()
                if getattr(self, "route_control", None) is not None:
                    self.route_control.completed_boundary()
                if getattr(self, "chain_retry_control", None) is not None:
                    self.chain_retry_control.completed_boundary()
                if getattr(self, "walk_intent", None) is not None:
                    self.walk_intent.completed_boundary()
                if getattr(self, "mount_pacing", None) is not None:
                    self.mount_pacing.completed_boundary()
                if getattr(self, "hop_arc", None) is not None:
                    self.hop_arc.completed_boundary()
                if getattr(self, "wild_walk", None) is not None:
                    self.wild_walk.completed_boundary()
                if getattr(self, "wild_ledge", None) is not None:
                    self.wild_ledge.completed_boundary()
                if getattr(self, "walk_corner", None) is not None:
                    self.walk_corner.completed_boundary()
                if getattr(self, "walk_matrix", None) is not None:
                    self.walk_matrix.completed_boundary()
                if getattr(self, "stomp_feedback", None) is not None:
                    self.stomp_feedback.completed_boundary()
                if getattr(self, "crash_feedback", None) is not None:
                    self.crash_feedback.completed_boundary()
                if self.party_getter_hooks.error is not None:
                    raise DevtoolsFailure("party-getter-mismatch", self.party_getter_hooks.error)
                party = self.callback_costs.call("sampler:party-read", self._read_party_at_boundary)
                value = self.callback_costs.call("sampler:snapshot", self._snapshot, 0, details=False)
                if getattr(self, "observer_control", None) is not None:
                    value["observerControl"] = self.observer_control.result()
                if getattr(self, "route_control", None) is not None:
                    value["routeControl"] = self.route_control.result()
                if getattr(self, "chain_retry_control", None) is not None:
                    value["chainRetryControl"] = self.chain_retry_control.result()
                if getattr(self, "walk_intent", None) is not None:
                    value["walkIntent"] = self.walk_intent.result()
                if getattr(self, "walk_policy_control", None) is not None:
                    value["walkPolicyControl"] = self.walk_policy_control.result()
                if getattr(self, "mount_pacing", None) is not None:
                    value["mountPacing"] = self.mount_pacing.result()
                if getattr(self, "wild_walk", None) is not None:
                    value["wildWalk"] = self.wild_walk.result()
                if getattr(self, "wild_ledge", None) is not None:
                    value["wildLedge"] = self.wild_ledge.result()
                if getattr(self, "walk_corner", None) is not None:
                    value["walkCorner"] = self.walk_corner.result()
                if getattr(self, "walk_matrix", None) is not None:
                    value["walkMatrix"] = self.walk_matrix.result()
                if getattr(self, "stomp_feedback", None) is not None:
                    value["stompFeedback"] = self.stomp_feedback.result()
                if getattr(self, "crash_feedback", None) is not None:
                    value["crashFeedback"] = self.crash_feedback.result()
                value["observationBoundary"] = "main-task-queue-completion"
                value["guestQueueClock"] = guest_queue_clock
                value["fieldAvailable"] = True
                value["selector"] = self.callback_costs.call("sampler:selector", self._selector_observation)
                value["dialogue"] = self.callback_costs.call("sampler:dialogue", self._dialogue_observation, field)
                value["party"] = party
                value["partyObservation"] = {"frame": self.completed_frames,
                    "boundary": "main-task-queue-completion",
                    "nativeGetterChecks": list(self.party_getter_checks.values())}
                profile_keys = tuple(value["nativeObservation"]["profileFingerprints"])
                if profile_keys != getattr(self, "latest_profile_keys", None):
                    self.latest_resolved_profiles = self.callback_costs.call(
                        "sampler:profile-cache", self.native_observation.snapshot,
                        include_profiles=True)["resolvedProfiles"]
                    self.latest_profile_keys = profile_keys
                self.latest_party = party
                self.latest_party_frame = self.completed_frames
                self.latest_frame = value
                self.callback_costs.call("sampler:trace-publication", self._complete_trace_boundary)
                if self.pending_samples is not None:
                    self.pending_samples.append(self.callback_costs.call("sampler:pending-copy", deepcopy, value))
            except Exception as error:
                self.sample_error = error
        def timed_completed(*args):
            try:
                self.callback_costs.call("main-queue-sampler", completed, *args)
            except Exception as error:
                if self.sample_error is None:
                    self.sample_error = error
        self.emu.memory.register_exec(address, timed_completed)

    def _field_actor_availability(self, field):
        """Stock field readiness, before any engine actor is dereferenced.

        sub_0203DF8C uses the field manager and field+0x6C. Manager lifecycle
        states come from overlay_manager.h/c. Package bytes are session-owned;
        only the 24-byte ARM9 predicate and bounded live data are read here.
        """
        from tools.overworld.devtools_field_lifecycle import FIELD_TEMPLATE
        base, arm9 = self.arm9_code_region
        require(arm9[0x0203DF8C - base:0x0203DFA4 - base]
                == bytes.fromhex("01680968002904d0c06e002801d001207047002070470000"),
                "stock field-ready predicate identity differs", "abi-mismatch")
        self._authenticate_field_reader_code(0x0203DF8C, 24)
        def pointer(address, size):
            require(type(address) is int and address % 4 == 0
                    and 0x02000000 <= address <= 0x02400000 - size,
                    "field availability pointer is invalid", "field-lifecycle-invalid")
            return address
        def words(address, count):
            data = self.read(pointer(address, 4 * count), 4 * count)
            require(isinstance(data, (bytes, bytearray)) and len(data) == 4 * count,
                    "field availability read is short", "field-lifecycle-invalid")
            return struct.unpack("<" + "I" * count, data)
        pointer(field, 0x70)
        ready, = words(field + 0x6C, 1)
        require(ready in (0, 1), "field ready flag is invalid", "field-lifecycle-invalid")
        control, = words(field, 1)
        value = {"authenticated": True, "fieldReady": ready, "controlPointer": control,
                 "managerPointer": 0, "managerExecState": None, "managerProcState": None,
                 "reason": None}
        if not control:
            require(not ready, "ready field has no control", "field-lifecycle-invalid")
            value["reason"] = "field-control-absent"
            return value
        pointer(control, 16)
        manager, = words(control, 1)
        value["managerPointer"] = manager
        if not manager:
            require(not ready, "ready field has no manager", "field-lifecycle-invalid")
            value["reason"] = "field-manager-absent"
            return value
        data = words(manager, 10)
        require(data[:4] == FIELD_TEMPLATE and data[6] == field,
                "field manager template or owner differs", "field-lifecycle-invalid")
        execute, process = data[4:6]
        require(execute in (0, 1, 2, 3) and
                (process <= 3 if execute in (0, 1) else process == 0 if execute == 2 else process <= 2),
                "field manager lifecycle state is invalid", "field-lifecycle-invalid")
        value.update(managerExecState=execute, managerProcState=process)
        require(not ready or execute == 2,
                "ready field manager is not executing", "field-lifecycle-invalid")
        if not ready:
            value["reason"] = "field-initializing" if execute in (0, 1) else "field-exiting"
        return value

    def _read_guest_queue_clock(self):
        """Read only inside the authenticated main-queue execution callback."""
        value = self.emu.guest_clock()
        require(isinstance(value, dict)
                and type(value.get("version")) is int and value["version"] == 1
                and value.get("running") is True
                and value.get("scope") == "nds-scheduler-ticks-not-cpu-or-instructions"
                and all(type(value.get(key)) is int and 0 <= value[key] < (1 << 64)
                        for key in ("arm9Timestamp", "arm7Timestamp", "frameSequence")),
                "guest queue clock is not an active native callback reading", "guest-queue-clock-invalid")
        return {key: value[key] for key in ("version", "running", "scope",
                "arm9Timestamp", "arm7Timestamp", "frameSequence")}

    def _record_field_absence(self, field, magic, lifecycle=None, *, guest_queue_clock):
        """Retain one real queue boundary without dereferencing field objects.

        This is missing field evidence, never permission to pass a transition.
        Trace coverage and observer errors remain separate, fail-closed facts.
        """
        reasons = ([] if field else ["null-field-pointer"])
        if magic != 0x5353574F:
            reasons.append("actor-system-uninitialized")
        if lifecycle is not None:
            reasons.append(lifecycle["reason"])
        value = {"frame": self.completed_frames, "nativeCycle": self.rt.EXECUTED_FRAME_COUNT,
                 "guestQueueClock": guest_queue_clock,
                 "observationBoundary": "main-task-queue-completion", "fieldAvailable": False,
                 "fieldAvailability": {"fieldPointer": field, "actorStateMagic": magic, "reasons": reasons},
                 "prepared": self.prepared, "proofStatus": "diagnostic-only",
                 "romSha256": self.rom_hash, "sourceSaveSha256": self.save_hash,
                 "nativeObservation": self.native_observation.snapshot(), "observationErrors": []}
        if lifecycle is not None:
            value["fieldAvailability"]["lifecycle"] = {
                key: item for key, item in lifecycle.items() if key != "reason"}
        control = getattr(self, "observer_control", None)
        if control is not None:
            receipt = control.result()
            if receipt.get("cleanupPending"):
                self.abort_native_control(DevtoolsFailure("observer-control-field-unavailable",
                    "field became unavailable before owned observer fault restoration"))
            if not receipt.get("closed") and receipt.get("state") in ("armed", "applying"):
                self.sample_error = DevtoolsFailure("observer-control-field-unavailable",
                    "field became unavailable during native observer control")
                value["observationErrors"].append({"code": "observer-control-field-unavailable",
                                                   "message": str(self.sample_error)})
        if self.party_getter_hooks.error is not None:
            value["observationErrors"].append({"code": "party-getter-mismatch",
                                               "message": self.party_getter_hooks.error})
            self.sample_error = DevtoolsFailure("party-getter-mismatch", self.party_getter_hooks.error)
        try:
            # Flush already published events at their real queue frame, but
            # never arm/reset a trace in an uninitialized field.
            self._complete_trace_boundary(allow_control=False)
        except Exception as error:
            value["observationErrors"].append({"code": "trace-observation-failed",
                                               "message": f"{type(error).__name__}: {error}"})
            if self.sample_error is None:
                self.sample_error = error
        self.latest_frame = value
        if self.pending_samples is not None:
            self.pending_samples.append(deepcopy(value))

    def _trace_write(self, address, data):
        """Instrumentation-only transport, separate from prepared game writes."""
        descriptor = self.rt.ACTOR_DESCRIPTOR
        state = descriptor["state"]
        header = state["address"] + state["offsets"]["traceHeader"]
        events = state["address"] + state["offsets"]["traceEvents"]
        header_size = descriptor["structures"]["traceHeader"]
        events_size = descriptor["structures"]["traceEvent"] * descriptor["capacities"]["traceEvents"]
        require((address == header and len(data) == header_size)
                or (address == events and len(data) == events_size and data == bytes(events_size)),
                "trace instrumentation write is outside its public header/reset ring", "invalid-trace-write")
        self.rt.actor_memory_write(self.emu, address, data)

    def _ensure_trace(self):
        if self.semantic_trace is None:
            from tools.overworld.devtools_trace import SemanticTrace
            from tools.overworld.trace import load_trace_schema
            schema = load_trace_schema(self.rt.REPO / "tools/overworld/schemas/semantic-trace-v1.json")
            trace = SemanticTrace(self.read, self._trace_write, self.rt.ACTOR_DESCRIPTOR, schema)
            self._install_trace_publication()
            self.semantic_trace = trace

    def _install_trace_publication(self):
        """Read committed public trace records before the small ring wraps.

        This adds no game write, caller, clock, or frame sampler. The native
        writer publishes its record and all header counters before returning.
        Stage bursts here, then expose them at the existing completed queue.
        """
        linked = self.rt.REPO / "build/overworld_actor_system_overlay_linked.o"
        address, size = _elf_function_extent(linked, "ActorSystem_WriteTrace")
        expected = _elf_code(linked, address, size)
        require(size >= 32 and self.packaged_code(address, size) == expected,
                "trace publication body differs from the packaged writer", "abi-mismatch")
        self.trace_pending, self.trace_pending_dropped = [], 0
        def before():
            if not self.trace_observing:
                return None
            require(self.read(address, 32) == expected[:32],
                    "trace publication entry changed while recording", "abi-mismatch")
            return True
        def after(_context):
            for event in self.semantic_trace.capture_publication():
                if len(self.trace_pending) < 4096:
                    self.trace_pending.append(event)
                else:
                    self.trace_pending_dropped += 1
        self.party_getter_hooks.observe_call(address, before, after)

    def _complete_trace_boundary(self, *, allow_control=True):
        request = self.trace_request
        if allow_control and request is not None and not request["complete"]:
            try:
                if request["operation"] == "start":
                    self.semantic_trace.start(request["maxFrames"])
                    self.trace_observing = True
                else:
                    self.semantic_trace.stop()
                request["complete"] = True
            except Exception as error:
                request["error"], request["complete"] = error, True
        if self.trace_observing and self.semantic_trace is not None:
            pending = getattr(self, "trace_pending", [])
            self.trace_pending = []
            self.trace_events_dropped += getattr(self, "trace_pending_dropped", 0)
            self.trace_pending_dropped = 0
            for event in pending:
                event["frame"] = self.completed_frames
            for event in pending + self.semantic_trace.sample(self.completed_frames):
                if len(self.trace_events) < 4096:
                    self.trace_events.append(event)
                else:
                    self.trace_events_dropped += 1
        if request is not None and request["complete"] and request["operation"] == "stop":
            self.trace_observing = False

    def drain_events(self):
        events, self.trace_events = self.trace_events, []
        if self.native_observation is not None:
            events.extend(self.native_observation.drain())
        if self.trace_events_dropped:
            events.append({"frame": self.completed_frames, "kind": "trace-status", "data": {
                "code": "worker-event-buffer-overflow", "count": self.trace_events_dropped,
                "coverageComplete": False, "diagnosticOnly": True}})
            self.trace_events_dropped = 0
        return events

    def _retain_prepared_events(self):
        """Drain completed queues only; keep the ordinary rings unchanged.

        Prepared release already has a native-cycle bound. This independent
        transport bound prevents a dense producer from growing one receipt
        without limit: eight ordinary 4096-event buffers and 32 MiB of JSON.
        """
        retained = getattr(self, "_prepared_retained_events", None)
        if retained is None:
            return
        batch = self.drain_events()
        if not batch:
            return
        retained.extend(batch)
        self._prepared_retained_bytes += len(json.dumps(batch, separators=(",", ":"), allow_nan=False).encode())
        require(len(retained) <= 32768 and self._prepared_retained_bytes <= 32 * 1024 * 1024,
                "prepared command event retention exceeded its bounded receipt", "prepared-event-retention-limit")

    def _record_control(self, operation, max_frames=None):
        require(self.emu is not None, "session is closed", "closed")
        self._ensure_trace()
        require(self.trace_request is None, "trace control is already pending", "busy")
        request = {"operation": operation, "maxFrames": max_frames, "complete": False, "error": None}
        self.trace_request = request
        try:
            for _ in range(120):
                self.cycle(1)
                require(self.sample_error is None, f"coherent sampler failed: {self.sample_error}", "observation-failed")
                if request["complete"]:
                    break
            require(request["complete"], "trace control did not reach a complete field frame", "trace-boundary-timeout")
            if request["error"] is not None:
                raise request["error"]
            return {"snapshot": self.snapshot(), "events": self.drain_events(),
                    "recording": self.semantic_trace.running, "frame": self.completed_frames,
                    "instrumentationOnly": True, "prepared": self.prepared}
        finally:
            self.trace_request = None

    def record_start(self, max_frames=1800, binding_context=False, role_profile=False):
        integer(max_frames, "maxFrames", 1, 65535)
        require(type(binding_context) is bool, "bindingContext must be boolean")
        require(type(role_profile) is bool, "roleProfile must be boolean")
        require(getattr(self, "_role_profile_window", None) is None,
                "role profile recording window is already active")
        if role_profile:
            require(self.prepared, "role profile recording requires prepared setup")
        result = self._record_control("start", max_frames)
        if binding_context:
            self.native_observation.binding_context.enable()
        if role_profile:
            window = self.native_observation.role_profiles.capture(control=False)
            window.__enter__()
            self._role_profile_window = window
        return result

    def _close_role_profile_window(self):
        import sys
        window = getattr(self, "_role_profile_window", None)
        if window is not None:
            # Clear ownership before cleanup, including a failing cleanup.
            self._role_profile_window = None
            window.__exit__(*sys.exc_info())

    def record_stop(self):
        try:
            return self._record_control("stop")
        finally:
            self._close_role_profile_window()

    def observer_control_arm(self, args):
        """Internal checked-job operation; no frame or input is advanced here."""
        from tools.overworld.devtools_records import select_current_actor
        from tools.overworld.devtools_observer_control import NativeObserverControl
        require(isinstance(args, dict) and set(args) == {"subject", "kind", "maxFrames"},
                "observer control arguments differ", "invalid-argument")
        require(args["kind"] in ("render-stall", "inactive-object"),
                "unknown observer control", "invalid-argument")
        max_frames = integer(args["maxFrames"], "observer control maxFrames", 1, 1200)
        subject = select_current_actor(self.snapshot(), args["subject"])
        old = getattr(self, "observer_control", None)
        if old is not None:
            old.close()
        self.observer_control = NativeObserverControl(self, subject)
        self.prepared = True
        self.observer_control.arm(args["kind"], max_frames=max_frames)
        control = self.observer_control.result()
        value = self.snapshot()
        value["observerControl"] = deepcopy(control)
        return {"snapshot": value, "observerControl": control, "prepared": True,
                "frame": self.completed_frames, "armed": True}

    def spawn_height_control_arm(self, args):
        """Internal checked-job calibration; never a public raw-memory command."""
        from tools.overworld.devtools_spawn_height_control import NativeSpawnHeightReadControl
        require(args == {} and not self.prepared and not self.native_bridge_active
                and getattr(self, "spawn_height_control", None) is None,
                "spawn height control must arm once before normal spawn", "invalid-argument")
        self.spawn_height_control = NativeSpawnHeightReadControl()
        return self.spawn_height_control.arm()

    def chain_retry_arm(self, args):
        from tools.overworld.devtools_records import select_current_actor
        from tools.overworld.devtools_chain_retry_control import NativeChainRetryControl
        require(isinstance(args, dict) and set(args) == {"subject", "maxFrames"}
                and not self.prepared and not self.native_bridge_active
                and self.chain_retry_control is None, "chain retry must arm once after natural acquisition", "invalid-argument")
        subject = select_current_actor(self.snapshot(diagnostic_details=False), args["subject"])
        control = NativeChainRetryControl(self, subject, args["maxFrames"])
        control.current()
        control.install()
        self.chain_retry_control = control
        self.prepared = True
        return dict(armed=True, prepared=True, frame=self.completed_frames,
                    snapshot=self.snapshot(diagnostic_details=False), chainRetryControl=control.result())

    def walk_corner_probe(self, args):
        from tools.overworld.devtools_contract import validate_command
        from tools.overworld.devtools_corner_probe import CornerProbe
        args = validate_command("walk-corner.probe", args)
        self.prepared = True
        probe = CornerProbe(self, args["subject"])
        receipt = self.bridge.run(lambda scratch: probe.recipe(scratch, Call))
        receipt["acceptedProof"] = False
        receipt["snapshot"] = self.snapshot(0, diagnostic_details=False)
        return self._prepared_result_boundary(receipt)

    def hop_candidate_probe(self, args):
        """Read the current Mankey Hop candidate results without advancing a frame."""
        from tools.overworld.devtools_contract import validate_command
        from tools.overworld.devtools_mounted_hop_candidate_probe import MountedHopCandidateProbe
        args = validate_command("hop-candidate.probe", args)
        self.prepared = True
        probe = MountedHopCandidateProbe(self, args["subject"])
        receipt = self.bridge.run(lambda scratch: probe.recipe(scratch, Call))
        receipt["acceptedProof"] = False
        receipt["snapshot"] = self.snapshot(0, diagnostic_details=False)
        return self._prepared_result_boundary(receipt)

    def crash_arm(self, args):
        """Opt-in mounted crash observations, not accepted gameplay proof."""
        from tools.overworld.devtools_contract import validate_command
        from tools.overworld.devtools_records import select_current_actor
        from tools.overworld.devtools_mounted_crash_observer import NativeMountedCrashObserver
        args = validate_command("crash.arm", args)
        require(getattr(self, "crash_feedback", None) is None,
                "Crash reader can be armed only once per session", "invalid-argument")
        subject = select_current_actor(self.snapshot(diagnostic_details=False), args["subject"])
        self.prepared = True
        reader = NativeMountedCrashObserver(self, subject, args["maxFrames"])
        self.crash_feedback = reader
        reader.arm()
        return dict(armed=True, prepared=True, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), crashFeedback=reader.result())

    def crash_close(self):
        reader = getattr(self, "crash_feedback", None)
        require(reader is not None, "Crash reader was not armed", "invalid-argument")
        reader.close()
        return dict(closed=True, advancedFrames=0, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), crashFeedback=reader.result())

    def stomp_arm(self, args):
        """Bounded native dust/sound observations; not gameplay acceptance."""
        from tools.overworld.devtools_contract import validate_command
        from tools.overworld.devtools_records import select_current_actor
        from tools.overworld.devtools_stomp_observer import NativeStompObserver
        args = validate_command("stomp.arm", args)
        require(getattr(self, "stomp_feedback", None) is None,
                "Stomp reader can be armed only once per session", "invalid-argument")
        subject = select_current_actor(self.snapshot(diagnostic_details=False), args["subject"])
        self.prepared = True
        reader = NativeStompObserver(self, subject, args["maxFrames"])
        self.stomp_feedback = reader
        reader.arm()
        return dict(armed=True, prepared=True, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), stompFeedback=reader.result())

    def crash_calibrate(self):
        from tools.overworld.devtools_mounted_crash_control import calibrate_mounted_crash
        reader = getattr(self, "crash_feedback", None)
        require(reader is not None and not getattr(self, "crash_calibrated", False),
                "Crash calibration needs one armed reader", "invalid-argument")
        # Terminal even if validation or restoration fails. Never resume a
        # private core after presenting invalid state to this reader.
        self.crash_calibrated = True
        control = calibrate_mounted_crash(reader)
        return dict(prepared=True, advancedFrames=0, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), calibration=control,
                    terminalGuard=self.crash_calibrated, crashFeedback=reader.result())

    def stomp_close(self):
        reader = getattr(self, "stomp_feedback", None)
        require(reader is not None, "Stomp reader was not armed", "invalid-argument")
        reader.close()
        return dict(closed=True, advancedFrames=0, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), stompFeedback=reader.result())

    def stomp_calibrate(self):
        from tools.overworld.devtools_stomp_control import calibrate_stomp_policy
        reader = getattr(self, "stomp_feedback", None)
        require(reader is not None and not getattr(self, "stomp_calibrated", False),
                "Stomp calibration needs one armed reader", "invalid-argument")
        self.stomp_calibrated = True
        control = calibrate_stomp_policy(reader)
        return dict(prepared=True, advancedFrames=0, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), calibration=control,
                    terminalGuard=self.stomp_calibrated, stompFeedback=reader.result())

    def walk_matrix_arm(self, args):
        """Read real Tick entry/return elapsed values, including one-frame Walk."""
        from tools.overworld.devtools_contract import validate_command
        from tools.overworld.devtools_records import select_current_actor
        from tools.overworld.devtools_walk_matrix_observer import NativeWalkMatrixObserver
        args = validate_command("walk-matrix.arm", args)
        require(getattr(self, "walk_matrix", None) is None,
                "Walk matrix can be armed only once per session", "invalid-argument")
        subject = select_current_actor(self.snapshot(diagnostic_details=False), args["subject"])
        self.prepared = True
        reader = NativeWalkMatrixObserver(self, subject, args["maxFrames"])
        self.walk_matrix = reader
        reader.arm()
        return dict(armed=True, prepared=True, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), walkMatrix=reader.result())

    def walk_matrix_close(self):
        reader = getattr(self, "walk_matrix", None)
        require(reader is not None, "Walk matrix was not armed", "invalid-argument")
        reader.close()
        return dict(closed=True, advancedFrames=0, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), walkMatrix=reader.result())

    def walk_matrix_calibrate(self):
        from tools.overworld.devtools_walk_matrix_control import calibrate_walk_matrix
        reader = getattr(self, "walk_matrix", None)
        require(reader is not None and not getattr(self, "walk_matrix_calibrated", False),
                "matrix calibration needs one armed reader", "invalid-argument")
        self.walk_matrix_calibrated = True
        control = calibrate_walk_matrix(reader)
        return dict(prepared=True, advancedFrames=0, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), calibration=control)

    def walk_corner_arm(self, args):
        from tools.overworld.devtools_contract import validate_command
        from tools.overworld.devtools_records import select_current_actor
        from tools.overworld.devtools_corner_observer import NativeCornerObserver
        args = validate_command("walk-corner.arm", args)
        require(getattr(self, "walk_corner", None) is None,
                "Walk corner can be armed only once per session", "invalid-argument")
        subject = select_current_actor(self.snapshot(diagnostic_details=False), args["subject"])
        self.prepared = True
        reader = NativeCornerObserver(self, subject, args["maxFrames"])
        self.walk_corner = reader
        reader.arm()
        return dict(armed=True, prepared=True, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), walkCorner=reader.result())

    def walk_corner_close(self):
        reader = getattr(self, "walk_corner", None)
        require(reader is not None, "Walk corner was not armed", "invalid-argument")
        reader.close()
        return dict(closed=True, advancedFrames=0, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), walkCorner=reader.result())

    def walk_corner_calibrate(self):
        from tools.overworld.devtools_corner_control import calibrate_corner_policy
        reader = getattr(self, "walk_corner", None)
        require(reader is not None and not getattr(self, "walk_corner_calibrated", False),
                "corner calibration needs one armed reader", "invalid-argument")
        self.walk_corner_calibrated = True
        control = calibrate_corner_policy(reader)
        return dict(prepared=True, advancedFrames=0, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), calibration=control)

    def wild_walk_arm(self, args):
        """Observe actual native clear returns for one current Wild subject."""
        from tools.overworld.devtools_contract import validate_command
        from tools.overworld.devtools_records import select_current_actor
        from tools.overworld.devtools_wild_walk_observer import NativeWildWalkObserver
        args = validate_command("wild-walk.arm", args)
        require(getattr(self, "wild_walk", None) is None,
                "Wild Walk can be armed only once per session", "invalid-argument")
        subject = select_current_actor(self.snapshot(diagnostic_details=False), args["subject"])
        self.prepared = True
        reader = NativeWildWalkObserver(self, subject, args["maxFrames"])
        self.wild_walk = reader
        reader.arm()
        return dict(armed=True, prepared=True, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), wildWalk=reader.result())

    def wild_walk_calibrate(self):
        from tools.overworld.devtools_wild_walk_control import calibrate_wild_walk_clear
        reader = getattr(self, "wild_walk", None)
        require(reader is not None, "Wild Walk was not armed", "invalid-argument")
        self.prepared = True
        control = calibrate_wild_walk_clear(reader)
        return dict(prepared=True, advancedFrames=0, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), wildWalkControl=control)

    def wild_walk_close(self):
        reader = getattr(self, "wild_walk", None)
        require(reader is not None, "Wild Walk was not armed", "invalid-argument")
        reader.close()
        return dict(closed=True, advancedFrames=0, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), wildWalk=reader.result())

    def wild_ledge_arm(self, args):
        """Select two directions at the actual Wild ledge planner."""
        from tools.overworld.devtools_contract import validate_command
        from tools.overworld.devtools_records import select_current_actor
        from tools.overworld.devtools_wild_ledge_observer import NativeWildLedgeObserver
        args = validate_command("wild-ledge.arm", args)
        require(getattr(self, "wild_ledge", None) is None,
                "Wild ledge can be armed only once per session", "invalid-argument")
        subject = select_current_actor(self.snapshot(diagnostic_details=False), args["subject"])
        self.prepared = True
        reader = NativeWildLedgeObserver(self, subject, args["maxFrames"])
        self.wild_ledge = reader
        reader.arm()
        return dict(armed=True, prepared=True, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), wildLedge=reader.result())

    def wild_ledge_close(self):
        reader = getattr(self, "wild_ledge", None)
        require(reader is not None, "Wild ledge was not armed", "invalid-argument")
        reader.close()
        return dict(closed=True, advancedFrames=0, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), wildLedge=reader.result())

    def mount_pacing_arm(self, args):
        """Bounded read-only native pair/step observations, not acceptance."""
        from tools.overworld.devtools_contract import validate_command
        from tools.overworld.devtools_records import select_current_actor
        from tools.overworld.devtools_mount_pacing_observer import NativeMountedPacingObserver
        args = validate_command("mount-pacing.arm", args)
        require(getattr(self, "mount_pacing", None) is None,
                "Mount pacing can be armed only once per session", "invalid-argument")
        subject = select_current_actor(self.snapshot(diagnostic_details=False), args["subject"])
        self.prepared = True
        reader = NativeMountedPacingObserver(self, subject, args["maxFrames"])
        self.mount_pacing = reader
        reader.arm()
        return dict(armed=True, prepared=True, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), mountPacing=reader.result())

    def hop_arc_arm(self, args):
        """Read the exact native elapsed-zero boundary for mounted Mankey Hops."""
        from tools.overworld.devtools_contract import validate_command
        from tools.overworld.devtools_records import select_current_actor
        from tools.overworld.devtools_mounted_hop_start_observer import NativeMountedHopStartObserver
        args = validate_command("hop-arc.arm", args)
        require(getattr(self, "hop_arc", None) is None,
                "Hop arc can be armed only once per session", "invalid-argument")
        subject = select_current_actor(self.snapshot(diagnostic_details=False), args["subject"])
        self.prepared = True
        reader = NativeMountedHopStartObserver(self, subject, args["maxFrames"])
        self.hop_arc = reader
        reader.arm()
        return dict(armed=True, prepared=True, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), hopArc=reader.result())

    def hop_arc_close(self):
        reader = getattr(self, "hop_arc", None)
        require(reader is not None, "Hop arc was not armed", "invalid-argument")
        reader.close()
        return dict(closed=True, advancedFrames=0, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), hopArc=reader.result())

    def mount_pacing_calibrate(self):
        """Explicit restored memory fault; never include this session in normal pacing proof."""
        from tools.overworld.devtools_mount_pacing_control import calibrate_mounted_pose
        reader = getattr(self, "mount_pacing", None)
        require(reader is not None, "Mount pacing was not armed", "invalid-argument")
        self.prepared = True
        control = calibrate_mounted_pose(reader)
        return dict(prepared=True, advancedFrames=0, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), mountedPoseControl=control)

    def mount_pacing_close(self):
        reader = getattr(self, "mount_pacing", None)
        require(reader is not None, "Mount pacing was not armed", "invalid-argument")
        reader.close()
        return dict(closed=True, advancedFrames=0, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), mountPacing=reader.result())

    def walk_policy_control_arm(self, args):
        """One explicit live reader fault; a checked control, never normal play."""
        from tools.overworld.devtools_records import select_current_actor
        from tools.overworld.devtools_walk_policy_control import NativeWalkPolicyReadControl
        require(isinstance(args, dict) and set(args) == {"subject"}
                and getattr(self, "walk_policy_control", None) is None,
                "Walk policy control requires one bound subject", "invalid-argument")
        subject = select_current_actor(self.snapshot(diagnostic_details=False), args["subject"])
        self.prepared = True
        control = NativeWalkPolicyReadControl(self, subject)
        self.walk_policy_control = control
        control.arm()
        return dict(armed=True, prepared=True, acceptedProof=False,
                    snapshot=self.snapshot(diagnostic_details=False), walkPolicyControl=control.result())

    def walk_policy_control_close(self):
        control = getattr(self, "walk_policy_control", None)
        require(control is not None, "Walk policy control was not armed", "invalid-argument")
        result = control.close()
        return dict(closed=True, advancedFrames=0, acceptedProof=False, walkPolicyControl=result)

    def walk_intent_arm(self, args):
        from tools.overworld.devtools_records import select_current_actor
        from tools.overworld.devtools_walk_intent import NativeWalkIntent
        require(isinstance(args, dict) and set(args) == {"subject", "direction", "maxFrames"}
                and self.prepared and not self.native_bridge_active
                and getattr(self, "walk_intent", None) is None,
                "Walk intent requires one prepared bound subject", "invalid-argument")
        subject = select_current_actor(self.snapshot(diagnostic_details=False), args["subject"])
        control = NativeWalkIntent(self, subject, args["direction"], args["maxFrames"])
        control.current()
        control.install()
        self.walk_intent = control
        return dict(armed=True, prepared=True, frame=self.completed_frames,
                    snapshot=self.snapshot(diagnostic_details=False), walkIntent=control.result())

    def walk_intent_close(self):
        if getattr(self, "walk_intent", None) is not None:
            self.walk_intent.close()
        return dict(closed=True, advancedFrames=0, walkIntent=self.walk_intent.result()
                    if getattr(self, "walk_intent", None) is not None else None)

    def chain_retry_close(self):
        if self.chain_retry_control is not None:
            self.chain_retry_control.close()
        return dict(closed=True, advancedFrames=0, chainRetryControl=self.chain_retry_control.result()
                    if self.chain_retry_control is not None else None)

    def route_control_arm(self, args):
        """Checked-job-only fault; no input, frame, or caller address here."""
        from tools.overworld.devtools_records import select_current_actor, _subject
        from tools.overworld.devtools_route_control import NativeRouteControl
        require(isinstance(args, dict) and set(args) == {"subject", "kind", "maxFrames"},
                "route control arguments differ", "invalid-argument")
        subject = select_current_actor(self.snapshot(), args["subject"])
        control = getattr(self, "route_control", None)
        if control is None:
            control = self.route_control = NativeRouteControl(self, subject)
        require(control.subject == _subject(subject), "route control subject changed", "wrong-subject")
        control.arm(args["kind"], max_frames=integer(args["maxFrames"], "route control maxFrames", 1, 120))
        self.prepared = True
        state = control.result()
        value = self.snapshot()
        value["routeControl"] = deepcopy(state)
        return {"snapshot": value, "routeControl": state, "prepared": True,
                "frame": self.completed_frames, "armed": True}

    def route_control_close(self):
        """Release input and close the fault without resuming altered play."""
        control = getattr(self, "route_control", None)
        self.rt.h.set_key_mask(self.emu, 0)
        if control is not None:
            control.close()
        state = control.result() if control is not None else None
        value = self.snapshot(diagnostic_details=False)
        value["routeControl"] = deepcopy(state)
        return {"routeControl": state, "frame": self.completed_frames,
                "closed": True, "advancedFrames": 0, "released": True, "snapshot": value}

    def abort_native_control(self, error):
        """A failed restoration cannot return through the C callback into play."""
        import os
        try:
            os.write(2, ("FATAL native observer control: " + str(error)[:500] + "\n").encode())
        finally:
            os._exit(70)  # Only the disposable worker exits; never the service.

    def observer_control_close(self):
        """Restore the owned fault and retain its receipt without a game tick."""
        control = getattr(self, "observer_control", None)
        if control is not None:
            control.close()
        result = control.result() if control is not None else None
        receipt = {"observerControl": result, "frame": self.completed_frames,
                   "closed": True, "advancedFrames": 0}
        try:
            # Read the restored native object now. The cached complete-frame
            # sample intentionally still contains the injected inactive bit.
            # This is an explicit readback, never an extra completed frame.
            value = self._snapshot(0, details=False)
            value["observationBoundary"] = "observer-control-restoration-readback"
            value["observedFrameCredit"] = 0
            value["observerControl"] = deepcopy(result)
            receipt["snapshot"] = value
        except Exception as error:
            # A failed sampler must not erase the actual restoration receipt.
            receipt["snapshotError"] = str(error)
        return receipt

    def _install_party_getter_checks(self):
        """Compare the decoder with natural, read-only native getter returns.

        At a normal GetMonData return its temporary decryption is finished (or
        an explicit caller lock remains recorded in the flags). This is NOT a
        synthetic native call. Keep the latest receipt for each slot/field.
        Unchanged full records reuse their validated decode, not an old native
        return or its timestamp. This bounds storage and the hot-path cost.
        """
        self.party_getter_hooks = DevtoolsHooks(self.rt, self.emu, getattr(self, "callback_costs", None))
        # Stock MON_DATA_MAX_HP is 164 (pokemon.h/GetMonDataInternal).
        fields = {5: "species", 161: "level", 163: "hp", 164: "maxHp"}
        decoded_records = {}  # At most six restored 236-byte party records.
        def before():
            # Synthetic prepared calls are not natural getter evidence. The
            # original observer remains installed before/after every bridge.
            if self.native_bridge_active:
                return None
            registers = self.emu.memory.register_arm9
            attr, pointer = registers.r1, registers.r0
            if attr not in fields:
                return None
            save = self.rt.unsigned(self.emu, 0x021D2228)
            if not 0x02000000 <= save < 0x02400000:
                return None
            party = save + 0xA0
            delta = pointer - party - 8
            if delta < 0 or delta % 236 or delta // 236 >= 6:
                return None
            slot = delta // 236
            return pointer, slot, attr
        def after(context):
            pointer, slot, attr = context
            actual = self.emu.memory.register_arm9.r0 & 0xFFFFFFFF
            record = bytes(self.read(pointer, 236))
            frame = self.completed_frames + 1
            cached = decoded_records.get(slot)
            unchanged = cached is not None and record == cached[0]
            if unchanged:
                _, mon, decoded_frame = cached
            else:
                mon = decode_party(struct.pack("<II", 6, 1) + record + bytes(5 * 236), self.party_offsets)[0]
                decoded_frame = frame
                decoded_records[slot] = record, mon, decoded_frame
                # A slot can now contain a different subject. Earlier field
                # checks must not remain in the current subject's receipt set.
                for key, previous in tuple(self.party_getter_checks.items()):
                    if key[0] == slot and (previous["personality"], previous["species"]) != (
                            mon["personality"], mon["species"]):
                        del self.party_getter_checks[key]
            expected = mon[fields[attr]]
            receipt = {"slot": slot, "field": fields[attr], "native": actual,
                       "decoded": expected, "passed": actual == expected,
                       "personality": mon["personality"], "species": mon["species"],
                       "nativeCycle": self.rt.EXECUTED_FRAME_COUNT, "frame": frame,
                       "validation": "unchanged-record" if unchanged else "fresh-decode",
                       "decodedAtFrame": decoded_frame,
                       "boundary": "natural-GetMonData-return"}
            self.party_getter_checks[slot, attr] = receipt
            require(actual == expected, f"party slot {slot} {fields[attr]} differs from native getter",
                    "party-getter-mismatch")
        self.party_getter_hooks.observe_call(self.target("get_mon"), before, after)

    def _ensure_selector_getter_observer(self):
        # Overlay 152 is not present when on_rom_open installs the resident
        # party getter. A visible menu is the first required setup boundary
        # here; authenticate its current code before adding any selector tap.
        address = self.target("selected_follower_slot")
        expected = self.read(address, 32)
        if getattr(self, "selector_getter_observer_installed", False):
            return
        def selected_before():
            # A persistent callback address can later be reused by another
            # overlay. Do not interpret that execution as this getter.
            if self.native_bridge_active or self.read(address, 32) != expected:
                self.selected_follower_observation = None
                return None
            field = self.field_pointer()
            return field if self.emu.memory.register_arm9.r0 == field else None
        def selected_after(field):
            if self.read(address, 32) != expected or self.field_pointer() != field:
                self.selected_follower_observation = None
                return
            self.selected_follower_observation = {
                "slot": self.emu.memory.register_arm9.r0 & 0xFFFFFFFF,
                "fieldPointer": field, "frame": self.completed_frames,
                "nativeCycle": self.rt.EXECUTED_FRAME_COUNT,
                "boundary": "natural-GetSelectedFollowerPartySlot-return"}
        self.party_getter_hooks.observe_call(address, selected_before, selected_after)
        self.selector_getter_observer_installed = True

    def _install_heap_lifetime_observer(self):
        # Stock Heap_Destroy: heap.c156; its full 116-byte implementation is
        # authenticated before observing the heap ID in r0. This hook only
        # invalidates host ownership; it never changes the game teardown.
        address, size = 0x0201A9C4, 0x74
        expected = (self.rt.REPO / "base/arm9.bin").read_bytes()[address - 0x02000000:address - 0x02000000 + size]
        require(len(expected) == size and self.packaged_code(address, size) == expected,
                "stock Heap_Destroy lifetime observer differs", "abi-mismatch")
        self.party_getter_hooks.add(address, self._observe_heap_destroy)

    def _observe_heap_destroy(self):
        if self.emu.memory.register_arm9.r0 != TRAMPOLINE_HEAP:
            return
        previous = self.native_trampoline
        self.native_heap_generation += 1
        self.native_trampoline = None
        if self.native_trampoline_in_use:
            raise DevtoolsFailure("native-heap-destroyed", "field heap was destroyed during a native tool call",
                                  fatal=True, details={"previousAllocation": None if previous is None else {
                                      key: previous[key] for key in ("address", "bytes", "fieldPointer", "heapGeneration")},
                                                       "heapGeneration": self.native_heap_generation})

    def _install_native_free_guard(self):
        # Stock Heap_Free immediately reads the header at ptr-4. It is NOT
        # libc free(NULL). Some emulator cores tolerate the invalid read;
        # rejecting it here keeps their behavior from hiding an ARM9 abort.
        # Include the sHeapInfo literal used by the scoped ScriptWarp reader.
        address, size = 0x0201AB0C, 0x74
        expected = (self.rt.REPO / "base/arm9.bin").read_bytes()[address - 0x02000000:address - 0x02000000 + size]
        require(len(expected) == size and struct.unpack_from("<I", expected, 0x70)[0] == 0x021D1584
                and self.packaged_code(address, size) == expected,
                "stock Heap_Free observer differs", "abi-mismatch")
        self.party_getter_hooks.add(address, self._observe_native_free)

    def _observe_native_free(self):
        registers = self.emu.memory.register_arm9
        pointer = registers.r0 & 0xFFFFFFFF
        observer = getattr(self, "script_warp_heap_free_observer", None)
        if observer is not None:
            observer.observe(pointer, registers.lr & 0xFFFFFFFF, registers.sp & 0xFFFFFFFF)
        if pointer:
            return
        raise DevtoolsFailure("native-null-free",
            f"stock Heap_Free(NULL): caller=0x{registers.lr & 0xFFFFFFFF:08X}, "
            f"sp=0x{registers.sp & 0xFFFFFFFF:08X}, frame={self.completed_frames}",
            details={"caller": registers.lr & 0xFFFFFFFF, "sp": registers.sp & 0xFFFFFFFF,
                     "frame": self.completed_frames, "pointer": 0})

    def _load_package(self):
        import ndspy.codeCompression
        data = self.rom.read_bytes()
        offset, _, address, size = struct.unpack_from("<4I", data, 0x20)
        self.code_regions = [(address, ndspy.codeCompression.decompress(data[offset:offset + size]))]
        self.arm9_code_region = self.code_regions[0]
        self.dialogue_overlay_regions = {}
        fat, fat_size = struct.unpack_from("<II", data, 0x48)
        y9, y9_size = struct.unpack_from("<II", data, 0x50)
        require(y9_size % 32 == 0 and fat + fat_size <= len(data), "ROM overlay tables are invalid")
        for entry in range(y9, y9 + y9_size, 32):
            overlay_id, base, size, _, _, _, file_id, flags = struct.unpack_from("<8I", data, entry)
            require(file_id * 8 + 8 <= fat_size, "overlay file index is invalid")
            start, end = struct.unpack_from("<II", data, fat + file_id * 8)
            require(start <= end <= len(data), "overlay file bounds are invalid")
            code = data[start:end]
            if flags & 0x01000000:
                code = ndspy.codeCompression.decompress(code)
            require(len(code) >= size, "overlay is shorter than its RAM image")
            self.code_regions.append((base, code[:size]))
            if overlay_id in (1, 2, 27):
                self.dialogue_overlay_regions[overlay_id] = (base, code[:size])

    def _authenticate_field_reader_code(self, address, size):
        regions = [self.arm9_code_region, *self.dialogue_overlay_regions.values()]
        matches = [code[address - base:address - base + size] for base, code in regions
                   if base <= address and address + size <= base + len(code)]
        require(len(matches) == 1 and self.read(address, size) == matches[0],
                "field reader code differs from its exact package", "abi-mismatch")
        return True

    def _dialogue_observation(self, field):
        """Bounded read-only input-state observation at the completed queue.

        Match the exact ARM9/overlay package, not any overlapping code region.
        No task means no printer/menu scan; unknown state never grants input.
        """
        from tools.overworld.devtools_dialogue import observe_dialogue

        authenticate = self._authenticate_field_reader_code

        try:
            loaded = set()
            if struct.unpack("<I", self.read(field + 0x10, 4))[0]:
                # GetLoadedOverlaysInRegion, poke_overlay.c: eight MAIN slots.
                authenticate(0x02007124, 36)
                table = struct.unpack("<I", self.read(0x0200713C, 4))[0]
                require(table % 4 == 0 and 0x02000000 <= table <= 0x02400000 - 64,
                        "dialogue overlay table is outside main RAM", "abi-mismatch")
                slots = struct.unpack("<16I", self.read(table, 64))
                require(all(slots[index + 1] in (0, 1) for index in range(0, 16, 2)),
                        "dialogue overlay active flag is invalid", "abi-mismatch")
                loaded = {slots[index] for index in range(0, 16, 2) if slots[index + 1] == 1}
            return observe_dialogue(self.read, authenticate, field, self.completed_frames,
                                    self.rt.EXECUTED_FRAME_COUNT, loaded)
        except Exception as error:
            return {"frame": self.completed_frames, "nativeCycle": self.rt.EXECUTED_FRAME_COUNT,
                    "boundary": "main-task-queue-completion", "fieldPointer": field,
                    "known": False, "state": "unknown", "reason": str(error)[:300]}

    def packaged_code(self, address, size):
        candidates = [data[address - base:address - base + size] for base, data in self.code_regions
                      if base <= address and address + size <= base + len(data)]
        require(candidates, f"address {address:#x} is outside packaged code", "abi-mismatch")
        live = self.read(address, size)
        require(live in candidates, f"live code at {address:#x} differs from ROM", "abi-mismatch")
        return live

    def target(self, name):
        require(name in STOCK_CALLS or name in STOCK_CALLBACKS or name in LINKED_CALLS, "routine is not permitted")
        if name in STOCK_CALLS or name in STOCK_CALLBACKS:
            address = STOCK_CALLS[name][0] if name in STOCK_CALLS else STOCK_CALLBACKS[name]
            expected = (self.rt.REPO / "base/arm9.bin").read_bytes()[address - 0x02000000:address - 0x02000000 + 32]
        else:
            table, symbol, _ = LINKED_CALLS[name]
            address = self.rt.linked_symbol(getattr(self.rt, table), symbol) & ~1
            expected = _elf_code(self.rt.REPO / "build" / ELF_FILES[table], address, 32)
        require(len(expected) == 32 and self.packaged_code(address, 32) == expected,
                f"routine {name} does not match its linked/stock identity", "abi-mismatch")
        return address

    def _native_checkpoint_points(self):
        """Read-only, authenticated checkpoints for native-call/IRQ faults."""
        stock = (self.rt.REPO / "base/arm9.bin").read_bytes()
        params = struct.unpack_from("<I", stock, 0x940)[0] - 0x02000000
        begin, end, payload = struct.unpack_from("<3I", stock, params)
        itcm = None
        for offset in range(begin - 0x02000000, end - 0x02000000, 12):
            base, size, _bss = struct.unpack_from("<3I", stock, offset)
            if base == 0x01FF8000:
                itcm = stock[payload - 0x02000000:payload - 0x02000000 + size]
            payload += size
        require(itcm is not None and len(itcm) >= 0x1AC, "stock IRQ autoload image is missing", "abi-mismatch")
        self.native_irq_code = itcm[:0x1AC]
        self.native_irq_live_baseline = bytes(self.rt.actor_memory_read(self.emu, 0x01FF8000, 0x1AC))
        require(len(self.native_irq_live_baseline) == 0x1AC,
                "IRQ baseline observation is incomplete", "abi-mismatch")
        require(self.rt.actor_memory_read(self.emu, 0x01FF81A8, 4) == itcm[0x1A8:0x1AC]
                and struct.unpack_from("<I", itcm, 0x1A8)[0] == 0x021E16A0,
                "SDK thread-info literal differs", "abi-mismatch")
        self.native_thread_info_address = 0x021E16A0
        points = [("irq-entry", 0x01FF8000), ("irq-dispatch", 0x01FF804C),
                  ("irq-return-if-idle", 0x01FF80B4), ("irq-after-idle-return", 0x01FF80B8),
                  ("irq-return-no-switch", 0x01FF80F4),
                  ("irq-thread-chosen", 0x01FF8120), ("irq-thread-svc-pop", 0x01FF8178),
                  ("irq-thread-restore", 0x01FF8188),
                  ("irq-return-thread-switch", 0x01FF81A0)]
        for _name, address in points:
            expected = itcm[address - 0x01FF8000:address - 0x01FF8000 + 4]
            # Fixed ITCM code observation only; this does not broaden the
            # public diagnostic read API or authorize any ITCM writes.
            require(self.rt.actor_memory_read(self.emu, address, 4) == expected,
                    f"stock IRQ checkpoint {address:#x} differs", "abi-mismatch")
        linked = self.rt.REPO / "build/linked.o"
        box, box_size = _elf_function_extent(linked, "CreateBoxMonData")
        require(box == self.rt.linked_symbol(self.rt.MOUNT_SYMBOLS, "CreateBoxMonData") & ~1,
                "CreateBoxMonData entry differs", "abi-mismatch")
        live_box = self.packaged_code(box, box_size)
        require(live_box == _elf_code(linked, box, box_size),
                "CreateBoxMonData checkpoint differs", "abi-mismatch")
        # Stock GetLoadedOverlaysInRegion's main-table literal is part of this
        # authenticated code span. Some hg-engine services are deliberately
        # untracked, so this is supporting metadata, not a complete live list.
        overlay_lookup = self.packaged_code(0x02007124, 36)
        require(overlay_lookup == stock[0x7124:0x7148], "overlay table accessor differs", "abi-mismatch")
        table = struct.unpack_from("<I", overlay_lookup, 24)[0]
        entries = struct.unpack("<16I", self.read(table, 64))
        self.native_dependency_checks = {
            "boundary": "before-native-bridge-entry",
            "irqVector": self._native_irq_vector(),
            "createBoxMonData": {"address": box, "size": box_size,
                                 "sha256": hashlib.sha256(live_box).hexdigest(), "liveMatchesLinkedAndRom": True},
            "trackedMainOverlayTable": {"address": table,
                "entries": [{"slot": index, "id": entries[index * 2], "active": entries[index * 2 + 1]}
                            for index in range(8)], "includesUntrackedServices": False}}
        points.append(("create-box-mon-entry", box))
        # Narrow diagnostic: preserve which CreateBox native call actually
        # entered/returned, separately from the rolling IRQ trace. These are
        # reviewed call-site offsets in the fully authenticated 584-byte body.
        # The linker may move this unchanged function when unrelated ROM code
        # changes. The authenticated symbol, packaged bytes, size, and relative
        # Thumb BL sites above are the stable contract.
        require(box_size == 584,
                "CreateBoxMonData internal observation layout differs", "abi-mismatch")
        for name, offset in (("init", 0x18), ("fast-mode", 0x20), ("personality-override", 0x2E),
                             ("species-name", 0xBA), ("level-exp", 0xC4),
                             ("personal-data", 0xDA), ("moveset", 0x194)):
            high, low = struct.unpack_from("<HH", live_box, offset)
            require(high & 0xF800 == 0xF000 and low & 0xF800 == 0xF800,
                    f"CreateBoxMonData {name} is not a Thumb BL", "abi-mismatch")
            points.append((f"create-box-internal-{name}-call", box + offset))
            points.append((f"create-box-internal-{name}-return", box + offset + 4))
        require(self.packaged_code(0x0206FD00, 0x68) == stock[0x6FD00:0x6FD68],
                "stock EXP allocation/archive code differs", "abi-mismatch")
        points.extend((f"level-exp-internal-{name}", address) for name, address, _depth in EXP_INTERNAL_POINTS)
        require(self.packaged_code(0x020712D8, 0xA0) == stock[0x712D8:0x71378],
                "stock moveset allocation/load code differs", "abi-mismatch")
        points.extend((f"moveset-internal-{name}", address) for name, address in MOVESET_INTERNAL_POINTS)
        return points

    def _native_irq_code_identity(self):
        """Read-only check for a changed IRQ body; the vector alone is not enough."""
        expected, baseline = self.native_irq_code, self.native_irq_live_baseline
        require(len(expected) == len(baseline) == 0x1AC, "IRQ baseline size differs", "abi-mismatch")
        actual = self.rt.actor_memory_read(self.emu, 0x01FF8000, len(expected))
        require(len(actual) == len(expected), "IRQ code observation is incomplete", "abi-mismatch")
        def changed_words(reference):
            return [{"offset": offset, "expected": struct.unpack_from("<I", reference, offset)[0],
                     "actual": struct.unpack_from("<I", actual, offset)[0]}
                    for offset in range(0, len(actual), 4)
                    if reference[offset:offset + 4] != actual[offset:offset + 4]]
        stock_changes, live_changes = changed_words(expected), changed_words(baseline)
        return {"address": 0x01FF8000, "bytes": len(actual), "matchesBeforeCall": actual == baseline,
                "matchesStock": actual == expected, "comparisonSource": "stock-autoload-image",
                "changedWordCount": len(stock_changes), "changedWords": stock_changes[:16],
                "changedWordsTruncated": len(stock_changes) > 16,
                "baselineChangedWordCount": len(live_changes), "baselineChangedWords": live_changes[:16],
                "baselineChangedWordsTruncated": len(live_changes) > 16,
                "baselineSha256": hashlib.sha256(baseline).hexdigest(),
                "expectedSha256": hashlib.sha256(self.native_irq_code).hexdigest(),
                "actualSha256": hashlib.sha256(actual).hexdigest()}

    def _authenticate_party_work_heap(self):
        stock = (self.rt.REPO / "base/arm9.bin").read_bytes()
        for name, entry, allocator, _size, alloc_return, _alloc_depth, free_return, _free_depth in PARTY_WORK_HEAP_SITES:
            for address, count in ((entry, 16), (alloc_return - 8, 12), (free_return - 8, 12)):
                require(self.packaged_code(address, count) == stock[address - 0x02000000:address - 0x02000000 + count],
                        f"prepared {name} work-buffer native code differs", "abi-mismatch")
            for returned, expected in ((alloc_return, allocator), (free_return, 0x0201AB0C)):
                high, low = struct.unpack_from("<HH", stock, returned - 4 - 0x02000000)
                require(high & 0xF800 == 0xF000 and low & 0xF800 == 0xF800,
                        f"prepared {name} work-buffer call is not Thumb BL", "abi-mismatch")
                offset = ((high & 0x7FF) << 12) | ((low & 0x7FF) << 1)
                if offset & 0x400000:
                    offset -= 0x800000
                require(returned + offset == expected,
                        f"prepared {name} work-buffer caller target differs", "abi-mismatch")

    def _native_irq_vector(self):
        # crt0 stores OS_IrqHandler at DTCM sysrv + 0x3C. Observe this
        # one fixed native dispatch word; never change it or expose a write.
        data = self.rt.actor_memory_read(self.emu, 0x027E3FFC, 4)
        require(len(data) == 4, "IRQ vector observation is incomplete", "abi-mismatch")
        return {"address": 0x027E3FFC, "target": struct.unpack("<I", data)[0],
                "expectedStockTarget": 0x01FF8000}

    def _native_thread_ownership(self):
        # Exact NitroSDK OSThreadInfo/OSThread layouts, authenticated through
        # the live IRQ dispatcher's thread-info literal before bridge entry.
        info = self.read(self.native_thread_info_address, 16)
        _reschedule, depth, pointer, _head, _callback = struct.unpack("<HHIII", info)
        require(pointer % 4 == 0 and 0x02000000 <= pointer <= 0x02400000 - 0x98,
                "SDK current thread pointer is invalid", "native-stack-ownership")
        data = self.read(pointer, 0x98)
        top, bottom = struct.unpack_from("<II", data, 0x90)
        require(top % 4 == bottom % 4 == 0 and top < bottom
                and ((0x027E0000 <= top < bottom <= 0x027E3FC0)
                     or (0x02000000 <= top < bottom <= 0x02400000)),
                "SDK thread stack bounds are invalid", "native-stack-ownership")
        return {"pointer": pointer, "id": struct.unpack_from("<I", data, 0x6C)[0],
                "state": struct.unpack_from("<I", data, 0x64)[0], "irqDepth": depth,
                "mode": self.emu.memory.register_arm9.cpsr & 0x1F,
                "stackTop": top, "stackBottom": bottom,
                "topGuard": struct.unpack("<I", self.read(top, 4))[0],
                "bottomGuard": struct.unpack("<I", self.read(bottom - 4, 4))[0]}

    def _native_thread_snapshot(self, pointer):
        """Read the one selected SDK context at an authenticated IRQ boundary."""
        item = {"pointer": pointer, "validContext": False}
        if pointer % 4 or not 0x02000000 <= pointer <= 0x02400000 - 0x98:
            item["invalidReason"] = "selected-thread-address"
            return item
        data = self.read(pointer, 0x98)
        cpsr = struct.unpack_from("<I", data)[0]
        sp, lr, pc, svc_sp = struct.unpack_from("<4I", data, 0x38)
        top, bottom = struct.unpack_from("<II", data, 0x90)
        item.update(contextHex=data[:0x64].hex(), cpsr=cpsr, sp=sp, lr=lr,
                    pcPlus4=pc, svcSp=svc_sp, stackTop=top, stackBottom=bottom,
                    state=struct.unpack_from("<I", data, 0x64)[0],
                    id=struct.unpack_from("<I", data, 0x6C)[0])
        item["checks"] = {
            "systemMode": cpsr & 0x1F == 0x1F,
            "ready": item["state"] == 1,
            "stackInsideOwner": top < sp < bottom,
            "resumeInMappedCode": pc >= 4 and self._native_target_is_mapped_code((pc - 4) & 0xFFFFFFFF)}
        item["validContext"] = all(item["checks"].values())
        return item

    def _native_target_is_mapped_code(self, address):
        address &= ~1
        return (0x01FF8000 <= address < 0x01FF8620 or 0xFFFF0000 <= address < 0xFFFF1000
                or any(base <= address < base + len(data) for base, data in self.code_regions))

    def read(self, address, size):
        require(self.emu is not None, "session is closed", "closed")
        require(type(size) is int and 0 <= size <= 0x10000
                and ((0x02000000 <= address <= address + size <= 0x02400000)
                     or (0x027E0000 <= address <= address + size <= 0x027E3FC0)),
                "diagnostic read is outside main RAM/public stack")
        return self.rt.actor_memory_read(self.emu, address, size) if size else b""

    def write(self, address, data):
        # Only private bridge recipes call this: reserved stack or the exact
        # 24-byte environment returned by their native allocation operation.
        require(self.prepared, "state writes require prepared mode")
        if data:
            self.rt.actor_memory_write(self.emu, address, data)

    def field_pointer(self):
        value = self.rt.unsigned(self.emu, self.rt.G_FIELD_SYS_PTR)
        require(0x02000000 <= value < 0x02400000, "no live field system")
        return value

    def party_pointer(self):
        save = self.rt.unsigned(self.emu, 0x021D2228)
        require(0x02000000 <= save < 0x02400000, "no live save data")
        return save + 0xA0

    def _read_party_at_boundary(self):
        return decode_party(self.read(self.party_pointer(), 8 + 6 * 236), self.party_offsets)

    def party_snapshot(self):
        # GetMonData temporarily decrypts in place WITHOUT setting its lock
        # flags. A native-cycle endpoint can stop in that function. Never read
        # raw party bytes here; use only the completed-main-queue observation.
        require(self.sample_error is None, f"coherent sampler failed: {self.sample_error}", "observation-failed")
        require(self.latest_party is not None and self.latest_party_frame == self.latest_frame["frame"],
                "no current complete party frame was observed", "observation-missing")
        return deepcopy(self.latest_party)

    def cycle(self, frames, mask=0):
        if self.runtime_health_failure is not None:
            raise self.runtime_health_failure
        require(self.emu is not None, "session is closed", "closed")
        for _ in range(frames):
            policy_control = getattr(self, "walk_policy_control", None)
            require(policy_control is None or policy_control.failure is None,
                    "Walk policy reader control failed", "walk-policy-control-invalid")
            intent = getattr(self, "walk_intent", None)
            pacing = getattr(self, "mount_pacing", None)
            require(pacing is None or pacing.failure is None,
                    "Mount pacing reader failed", "mount-pacing-invalid")
            wild_walk = getattr(self, "wild_walk", None)
            require(wild_walk is None or wild_walk.failure is None,
                    "Wild Walk reader failed", "wild-walk-invalid")
            wild_ledge = getattr(self, "wild_ledge", None)
            require(wild_ledge is None or wild_ledge.failure is None,
                    "Wild ledge reader failed", "wild-ledge-invalid")
            corner = getattr(self, "walk_corner", None)
            require(not getattr(self, "walk_corner_calibrated", False),
                    "corner calibration is terminal; close this private session", "walk-corner-invalid")
            require(corner is None or corner.failure is None,
                    "Walk corner reader failed", "walk-corner-invalid")
            matrix = getattr(self, "walk_matrix", None)
            stomp = getattr(self, "stomp_feedback", None)
            crash = getattr(self, "crash_feedback", None)
            require(not getattr(self, "crash_calibrated", False),
                    "Crash calibration is terminal; close this private session", "crash-invalid")
            require(crash is None or crash.failure is None,
                    "Crash reader failed", "crash-invalid")
            require(not getattr(self, "stomp_calibrated", False),
                    "Stomp calibration is terminal; close this private session", "stomp-invalid")
            require(stomp is None or stomp.failure is None,
                    "Stomp reader failed", "stomp-invalid")
            require(not getattr(self, "walk_matrix_calibrated", False),
                    "matrix calibration is terminal; close this private session", "walk-matrix-invalid")
            require(matrix is None or matrix.failure is None,
                    "Walk matrix reader failed", "walk-matrix-invalid")
            require(intent is None or intent.failure is None, "Walk intent control failed", "walk-intent-invalid")
            if intent is not None and not intent.closed and self.completed_frames - intent.start_frame > intent.max_frames:
                intent.fail("Walk intent frame budget exceeded")
            retry = getattr(self, "chain_retry_control", None)
            require(retry is None or retry.failure is None, "chain retry control failed", "chain-retry-control-invalid")
            control = getattr(self, "route_control", None)
            require(not (control is not None and (control.failure is not None
                         or getattr(self, "route_control_nonresumable", False) and control.closed)),
                    "fault-injected route session must be disposed", "route-control-nonresumable")
            self.rt.h.cycle(self.emu, 1, mask)
            heap_free_observer = getattr(self, "script_warp_heap_free_observer", None)
            if heap_free_observer is not None:
                heap_free_observer.check()
            cpu_work = getattr(self, "cpu_work_probe", None)
            if cpu_work is not None:
                cpu_work.observe_cycle()
            release_observer = getattr(self, "release_observer", None)
            if release_observer is not None:
                release_observer.check()
            if not getattr(self, "native_health_exclusion_active", False):
                self._check_runtime_health()
            self._retain_prepared_events()

    def _check_runtime_health(self, operation="observe"):
        """Cheap endpoint checks; capture full state only at the first fault."""
        from tools.overworld.devtools_runtime_health import RuntimeHealthFailure
        if self.runtime_health_failure is not None:
            raise self.runtime_health_failure
        try:
            getattr(self.runtime_health, operation)(self.rt.EXECUTED_FRAME_COUNT,
                self.completed_frames, self.emu.memory.register_arm9.cpsr & 0xFFFFFFFF)
        except RuntimeHealthFailure as error:
            failure = DevtoolsFailure(error.code, "Automatic runtime freeze check: " + error.code,
                fatal=True, details={**error.details, "diagnostics": self.diagnostics()})
            self.runtime_health_failure = failure
            raise failure from error

    def _wait_new_frame(self, after_frame, predicate, *, native_limit, code, message):
        """Wait for fresh field readback after a native command.

        Absence stays in the sampler/trace stream and consumes the native
        budget, but cannot satisfy a predicate that needs field objects.
        """
        for _ in range(native_limit):
            self.cycle(1)
            require(self.sample_error is None, f"coherent sampler failed: {self.sample_error}", "observation-failed")
            value = self.latest_frame
            if value is not None and value.get("fieldAvailable") is not False \
                    and value["frame"] > after_frame and predicate(value):
                return self.snapshot()
        raise DevtoolsFailure(code, message, details={
            "afterFrame": after_frame, "nativeCycleLimit": native_limit,
            "latestCompleteFrame": deepcopy(self.latest_frame),
            "nativeEndpoint": self._control_diagnostics(),
        })

    def _field_cleanup_diagnostics(self):
        from tools.overworld.devtools_field_cleanup import observe_field_cleanup
        try:
            self._authenticate_field_reader_code(0x02007124, 36)
            table = struct.unpack("<I", self.read(0x0200713C, 4))[0]
            require(table % 4 == 0 and 0x02000000 <= table <= 0x02400000 - 64,
                    "cleanup overlay table is invalid", "abi-mismatch")
            slots = struct.unpack("<16I", self.read(table, 64))
            require(all(slots[i + 1] in (0, 1) for i in range(0, 16, 2)),
                    "cleanup overlay flags are invalid", "abi-mismatch")
            loaded = {slots[i] for i in range(0, 16, 2) if slots[i + 1]}
            def authenticate(address, size, expected):
                require(self.packaged_code(address, size) == expected
                        and self.read(address, size) == expected,
                        "cleanup live/package/ELF code differs", "abi-mismatch")
                return True
            return observe_field_cleanup(self.read, authenticate,
                lambda name: (self.rt.REPO / "build" / name).read_bytes(), loaded,
                self.completed_frames, self.rt.EXECUTED_FRAME_COUNT)
        except Exception as error:
            return {"known": False, "reason": str(error)[:240], "diagnosticOnly": True,
                    "acceptedProof": False, "boundary": "paused-native-cycle-end",
                    "frame": self.completed_frames, "nativeCycle": self.rt.EXECUTED_FRAME_COUNT}

    def _control_diagnostics(self, *, boundary="paused-native-cycle-end"):
        """Paused endpoint state, explicitly NOT a completed-frame observation.

        TaskManager and FieldTransitionEnvironment layouts are the stock public
        task.h and unk_02055BF0.c layouts. Decode an environment only for that
        exact transition callback, never as a guessed arbitrary task payload.
        """
        rt, emu = self.rt, self.emu
        result = {"boundary": boundary, "nativeCycle": rt.EXECUTED_FRAME_COUNT,
                  "lastCompletedGameFrame": self.completed_frames, "tasks": []}
        try:
            field = self.field_pointer()
            from tools.overworld.devtools_field_lifecycle import observe_field_lifecycle
            result["fieldLifecycle"] = observe_field_lifecycle(
                self.read, self._authenticate_field_reader_code, field,
                self.completed_frames, rt.EXECUTED_FRAME_COUNT)
            result["fieldCleanup"] = self._field_cleanup_diagnostics()
            task = rt.unsigned(emu, field + 0x10)
            result.update(fieldPointer=field, taskPointer=task, mapId=rt.field_map_id(emu),
                          player=rt.object_state(emu, rt.player_ptr(emu)),
                          actorTransitionPhase=rt.unsigned(emu, rt.ACTOR_DESCRIPTOR["state"]["address"] + 40, 1))
            seen = set()
            while task and len(result["tasks"]) < 8:
                require(task not in seen and task % 4 == 0, "native task chain is invalid")
                seen.add(task)
                prev, function, state, env, _, _, owner, _ = struct.unpack("<8I", self.read(task, 32))
                item = {"pointer": task, "previous": prev, "function": function,
                        "state": state, "environment": env, "fieldPointer": owner}
                if function & ~1 == 0x02055DBC:
                    data = self.read(env, 40)
                    map_id, warp_id, x, z, facing = struct.unpack_from("<5i", data, 4)
                    item["transition"] = {"state": data[0], "substate": struct.unpack_from("<H", data, 2)[0],
                                          "mapId": map_id, "warpId": warp_id, "x": x, "z": z, "facing": facing,
                                          "transitionNo": struct.unpack_from("<I", data, 28)[0]}
                elif function & ~1 == STOCK_CALLBACKS["script_warp_task"]:
                    phase, map_id, warp_id, x, z, facing = struct.unpack("<6i", self.read(env, 24))
                    item["transition"] = {"kind": "script-warp", "state": phase, "mapId": map_id,
                                          "warpId": warp_id, "x": x, "z": z, "facing": facing}
                result["tasks"].append(item)
                task = prev
            if task:
                result["taskChainTruncated"] = True
        except Exception as error:
            result["diagnosticError"] = f"{type(error).__name__}: {error}"
        return result

    def require_quiescent(self):
        field = self.field_pointer()
        require(self.rt.unsigned(self.emu, field + 0x10) == 0, "a native field task is active", "busy")
        actor = self.rt.actor_state(self.emu, 7)
        require(not actor["active"] or (actor["motionPhase"] in ("IDLE", "CANCELED")
                and actor["reservationId"] == 0), "follower/mount motion is active", "busy")
        require(self.rt.unsigned(self.emu, self.rt.SELECTOR_STATE, 1) == 0,
                "the follower menu is active", "busy")
        transition_phase = self.rt.unsigned(self.emu, self.rt.ACTOR_DESCRIPTOR["state"]["address"] + 40, 1)
        # COMPLETE is a retained successful receipt, not active transition work.
        require(transition_phase in (0, 4),
                f"an actor map transition is active (phase={transition_phase})", "busy")
        player = self.rt.object_state(self.emu, self.rt.player_ptr(self.emu))
        flags = player["flags"]
        native_idle = flags & 1 and not flags & 2 and (not flags & 0x10 or flags & 0x20)
        require(native_idle and [player["pos_x"], player["pos_z"]] ==
                [(player[key] << 16) + 0x8000 for key in ("x", "y")],
                "player movement has not settled", "busy")

    def snapshot(self, radius=7, *, diagnostic_details=True):
        require(type(diagnostic_details) is bool, "diagnostic_details must be boolean", "invalid-argument")
        require(self.sample_error is None, f"coherent sampler failed: {self.sample_error}", "observation-failed")
        require(self.latest_frame is not None, "no complete live field frame was observed", "observation-missing")
        value = deepcopy(self.latest_frame)
        if self.native_observation is not None:
            require(self.native_observation.hooks.error is None,
                    f"native observer failed: {self.native_observation.hooks.error}", "observation-failed")
        if value.get("fieldAvailable") is False:
            return value
        if self.native_observation is not None:
            # A native cycle may end in the next main update. Keep the last
            # completed frame's receipt watermark and profile cache together.
            value["nativeObservation"]["resolvedProfiles"] = deepcopy(self.latest_resolved_profiles)
        value["prepared"] = self.prepared
        if getattr(self, "chain_retry_control", None) is not None:
            value["chainRetryControl"] = self.chain_retry_control.result()
        if getattr(self, "walk_intent", None) is not None:
            value["walkIntent"] = self.walk_intent.result()
        if getattr(self, "walk_policy_control", None) is not None:
            value["walkPolicyControl"] = self.walk_policy_control.result()
        if getattr(self, "mount_pacing", None) is not None:
            value["mountPacing"] = self.mount_pacing.result()
        if getattr(self, "wild_walk", None) is not None:
            value["wildWalk"] = self.wild_walk.result()
        if getattr(self, "wild_ledge", None) is not None:
            value["wildLedge"] = self.wild_ledge.result()
        if getattr(self, "walk_corner", None) is not None:
            value["walkCorner"] = self.walk_corner.result()
        if getattr(self, "walk_matrix", None) is not None:
            value["walkMatrix"] = self.walk_matrix.result()
        if getattr(self, "stomp_feedback", None) is not None:
            value["stompFeedback"] = self.stomp_feedback.result()
        if getattr(self, "crash_feedback", None) is not None:
            value["crashFeedback"] = self.crash_feedback.result()
        if diagnostic_details:
            value.update(party=self.party_snapshot(), terrain=self.terrain(radius)["terrain"])
        return value

    def _snapshot(self, radius=7, *, details=True):
        integer(radius, "terrain radius", 0, 12)
        rt, emu = self.rt, self.emu
        require(emu is not None, "session is closed", "closed")
        player = rt.object_state(emu, rt.player_ptr(emu))
        address = rt.ACTOR_DESCRIPTOR["state"]["address"]
        context = {"fieldEpoch": rt.unsigned(emu, address + 12, 2),
                   "mapGeneration": rt.unsigned(emu, address + 46, 2),
                   "mapId": rt.field_map_id(emu)}
        require(context["fieldEpoch"] > 0 and context["mapGeneration"] > 0,
                "actor context is not initialized")
        from tools.overworld.devtools_crash_presentation import CrashPresentationReader
        crash_reader, crash_error = None, None
        try:
            if not hasattr(self, "_crash_presentation_reader"):
                self._crash_presentation_reader = CrashPresentationReader(
                    lambda name: (rt.REPO / "build" / name).read_bytes(), self.packaged_code)
            crash_reader = self._crash_presentation_reader
            crash_reader.boundary(self.read)
        except Exception as error:
            crash_reader, crash_error = None, str(error)[:160]
        actors = []
        # This reader never advances the guest. Share ID scans only within this
        # one snapshot; flags and each actor's live binding are still reread.
        id_scan_cache = {}
        for slot in range(rt.ACTOR_DESCRIPTOR["capacities"]["actors"]):
            actor = rt.actor_state(emu, slot)
            if not actor["active"]:
                continue
            if slot >= 8:
                actor.update(identityVerified=False, engineIdentity={"status": "unsupported-non-population-role"})
                actors.append(actor)
                continue
            source = rt.wild_spawn(emu, slot)
            engine = rt.live_wild_object_identity(emu, slot, id_scan_cache=id_scan_cache)
            checks = actor_identity_checks(actor, source, engine, context, slot)
            if actor["role"] == "MOUNTED":
                pointer = rt.player_ptr(emu)
                manager = engine["current_manager"]
                objects = rt.unsigned(emu, manager + 0x124) if manager else 0
                count = rt.unsigned(emu, manager + 4) if manager else 0
                delta = pointer - objects
                anchor = bool(objects and delta >= 0 and delta % 0x12C == 0 and delta // 0x12C < count
                              and rt.unsigned(emu, pointer) & 1
                              and rt.unsigned(emu, pointer + 0xB4) == manager)
                engine.update(anchorPointer=pointer, anchorInCurrentManager=anchor)
                checks["mountedAnchorInCurrentManager"] = anchor
            actor.update(identityVerified=all(checks.values()), identityChecks=checks,
                         identityFailures=[key for key, passed in checks.items() if not passed],
                         engineIdentity=engine, sourceIdentity=source,
                         movementPolicy=rt.movement_policy_state(emu, slot))
            actor["lastDecisionName"] = rt.actor_probe._enum_name(rt.ACTOR_DESCRIPTOR, "OverworldActorReason", actor["lastDecision"], "OVERWORLD_ACTOR_REASON")
            actor["lastCancelReasonName"] = rt.actor_probe._enum_name(rt.ACTOR_DESCRIPTOR, "OverworldActorReason", actor["lastCancelReason"], "OVERWORLD_ACTOR_REASON")
            if engine["in_manager"]:
                actor["engineObject"] = rt.object_state(emu, engine["pointer"])
            actor["crashPresentation"] = crash_reader.observe(
                self.read, actor, self.completed_frames, rt.EXECUTED_FRAME_COUNT) if crash_reader is not None else {
                    "known": False, "reason": crash_error, "frame": self.completed_frames,
                    "nativeCycle": rt.EXECUTED_FRAME_COUNT, "boundary": "main-task-queue-completion"}
            actors.append(actor)
        result = {"frame": self.completed_frames, "nativeCycle": rt.EXECUTED_FRAME_COUNT,
                  "actorFrame": rt.unsigned(emu, address + 8),
                  "player": player, "actors": actors, "context": context,
                  "prepared": self.prepared, "proofStatus": "diagnostic-only",
                  "romSha256": self.rom_hash, "sourceSaveSha256": self.save_hash}
        result["fieldControl"] = {"fieldPointer": self.field_pointer(),
                                  "taskPointer": rt.unsigned(emu, self.field_pointer() + 0x10),
                                  "actorTransitionPhase": rt.unsigned(emu, address + 40, 1)}
        if self.native_observation is not None:
            result["nativeObservation"] = self.native_observation.snapshot(include_profiles=details)
        if getattr(self, "spawn_cost_probe", None) is not None:
            result["spawnObserverCost"] = self.spawn_cost_probe.result()
        if details:
            result.update(party=self.party_snapshot(), terrain=self.terrain(radius)["terrain"])
        return result

    def terrain(self, radius=7, *, x=None, z=None):
        integer(radius, "terrain radius", 0, 12)
        require((x is None) == (z is None), "terrain x and z must be supplied together", "invalid-argument")
        if x is not None:
            integer(x, "terrain x", 0, 32767)
            integer(z, "terrain z", 0, 32767)
        rt, emu = self.rt, self.emu
        if x is None:
            player = rt.object_state(emu, rt.player_ptr(emu))
            x, z = player["x"], player["y"]
        center = {"x": x, "z": z}
        cells = []
        for tile_z in range(z - radius, z + radius + 1):
            for tile_x in range(x - radius, x + radius + 1):
                cell = rt.loaded_terrain_cell(emu, tile_x, tile_z)
                surface = rt.loaded_surface_cell(emu, tile_x, tile_z, cell)
                cells.append({"x": tile_x, "y": tile_z, "z": tile_z,
                              "loaded": cell is not None, **(cell or {}), "surface": surface})
        address = rt.ACTOR_DESCRIPTOR["state"]["address"]
        return {"terrain": {"cells": cells, "warps": rt.loaded_warp_events(emu),
                            "observation": {"boundary": "paused-native-cycle-end",
                                            "nativeCycle": rt.EXECUTED_FRAME_COUNT,
                                            "lastCompletedGameFrame": self.completed_frames,
                                            "context": {"mapId": rt.field_map_id(emu),
                                                        "fieldEpoch": rt.unsigned(emu, address + 12, 2),
                                                        "mapGeneration": rt.unsigned(emu, address + 46, 2)},
                                            "center": center},
                            "scope": "loaded stock terrain plus live authored surface catalog; unknown cells are not passable evidence"}}

    def diagnostics(self):
        """Bounded paused-endpoint evidence, never a repair or a game tick."""
        result = {"boundary": "paused-native-cycle-end", "captureErrors": []}
        for key, capture in (
            ("cpu", lambda: native_cpu_diagnostics(self)),
            ("fieldControl", self._control_diagnostics),
            ("lastCompleteSnapshot", lambda: deepcopy(self.latest_frame)),
        ):
            try:
                result[key] = capture()
            except Exception as error:
                result["captureErrors"].append(f"{key}: {type(error).__name__}: {error}")
        return result

    def _install_input_poll_fence(self):
        if getattr(self, "input_poll_fence_installed", False):
            return
        # Stock main.c calls ReadKeypadAndTouchpad before the main queue.
        # Arm at its call, not merely its return: a paused partial poll must
        # not be credited to a newly published manual key mask.
        image = (self.rt.REPO / "base/arm9.bin").read_bytes()
        require(image[0xDB4:0xDB8] == bytes.fromhex("19 f0 92 fb")
                and image[0xE64:0xE68] == struct.pack("<I", 0x021D110C),
                "native keypad poll binding differs", "abi-mismatch")
        for offset, size in ((0xDB4, 8), (0xE64, 4), (0x1A4DC, 0x10C)):
            require(self.packaged_code(0x02000000 + offset, size) == image[offset:offset + size],
                    "native keypad poll code differs", "abi-mismatch")
            require(self.read(0x02000000 + offset, size) == image[offset:offset + size],
                    "live native keypad poll code differs", "abi-mismatch")
        self.emu.memory.register_exec(0x02000DB4, lambda *_: self._input_poll_entered())
        self.emu.memory.register_exec(0x02000DB8, lambda *_: self._input_poll_returned())
        self.input_poll_fence_installed = True

    def _input_poll_entered(self):
        phase = getattr(self, "input_step_phase", None)
        if phase is not None:
            phase["entered"] = True

    def _input_poll_returned(self):
        phase = getattr(self, "input_step_phase", None)
        if phase is None or not phase["entered"]:
            return
        phase["entered"] = False
        try:
            # system.h: heldKeysRaw +0x38, heldKeys +0x44. The latter is zero
            # in the folded-lid path, which does not update heldKeysRaw.
            raw = struct.unpack("<I", self.read(0x021D1144, 4))[0]
            held = struct.unpack("<I", self.read(0x021D1150, 4))[0]
            phase["polled"] = raw == phase["nativeMask"] and held != 0
        except Exception as error:
            self.sample_error = error

    def step(self, frames, keys, *, release_at_end=True, diagnostic_details=True):
        integer(frames, "frames", 1, 600)
        require(type(diagnostic_details) is bool, "diagnostic_details must be boolean", "invalid-argument")
        require(isinstance(keys, list) and len(keys) <= 12 and len(set(keys)) == len(keys),
                "keys must be a list of distinct button names", "invalid-argument")
        allowed = {"UP", "DOWN", "LEFT", "RIGHT", "A", "B", "X", "Y", "L", "R", "START", "SELECT"}
        require(all(isinstance(key, str) and key in allowed for key in keys), "unknown button", "invalid-argument")
        mask = 0
        for key in keys:
            mask |= self.rt.h.keymask(self.rt.h.key_constant(key))
        first_frame = self.completed_frames
        require(type(release_at_end) is bool, "release_at_end must be boolean", "invalid-argument")
        fenced = release_at_end and bool(keys)
        if fenced:
            self._install_input_poll_fence()
        native_buttons = ("A", "B", "SELECT", "START", "RIGHT", "LEFT", "UP", "DOWN", "R", "L", "X", "Y")
        self.input_step_phase = {"entered": False, "polled": False, "consumed": 0,
                                 "requested": frames,
                                 "nativeMask": sum(1 << native_buttons.index(key) for key in keys)} if fenced else None
        phase = self.input_step_phase
        self.step_release_at_frame = first_frame + frames if release_at_end and not fenced else None
        def credited():
            return phase["consumed"] if phase is not None else self.completed_frames - first_frame
        self.pending_samples = []
        native_cycles = 0
        succeeded = False
        intervals = []
        dispatch_setter = getattr(self.emu, "enable_dispatch_counts", None)
        cpu_clock_resolution = {name: max(1, math.ceil(time.get_clock_info(clock).resolution * 1e9))
                                for name, clock in (("process", "process_time"), ("thread", "thread_time"))}
        dispatch_previous = None
        dispatch_sequence = None
        phase_setter = getattr(self.emu, "enable_phase_timings", None)
        phase_previous = None
        phase_sequence = None
        step_error = None
        last_complete, cycles_without_progress = first_frame, 0
        try:
            if dispatch_setter is not None:
                dispatch_previous = dispatch_setter(True)
                dispatch_sequence = self.emu.dispatch_counts()["frameSequence"]
            if phase_setter is not None:
                phase_previous = phase_setter(True)
                phase_sequence = self.emu.phase_timings()["frameSequence"]
            for _ in range(frames * 6 + 120):
                callback_costs = getattr(self, "callback_costs", None)
                if callback_costs is not None:
                    callback_costs.begin_cycle()
                host_probe_before = measure_host_probe() if dispatch_setter is not None else None
                cpu_start, wall_start = time.process_time_ns(), time.perf_counter_ns()
                # Nested brackets bound real CPU work, but independently
                # quantized clocks can differ by less than their resolution.
                thread_start = time.thread_time_ns()
                cycle_error = None
                try:
                    with callback_costs.measure_gc() if callback_costs is not None else nullcontext():
                        if getattr(self, "route_control", None) is not None:
                            self.route_control.before_cycle()
                        self.cycle(1, mask)
                except BaseException as error:
                    cycle_error = error
                    raise
                finally:
                    thread_error = None
                    try:
                        thread_cpu = time.thread_time_ns() - thread_start
                    except Exception as error:
                        thread_error = error
                    interval = {"cpuNs": time.process_time_ns() - cpu_start,
                                "wallNs": time.perf_counter_ns() - wall_start,
                                "cpuClockResolutionNs": dict(cpu_clock_resolution),
                                "completedGameFrame": self.completed_frames}
                    if thread_error is None:
                        interval["threadCpuNs"] = thread_cpu
                    else:
                        interval["threadCostError"] = str(thread_error)
                    intervals.append(interval)
                    if host_probe_before is not None:
                        try:
                            interval["hostWorkProbe"] = {"before": host_probe_before, "after": measure_host_probe()}
                        except Exception as error:
                            interval["hostWorkProbeError"] = str(error)
                            if cycle_error is None:
                                require(self.sample_error is None,
                                        f"coherent sampler failed: {self.sample_error}", "observation-failed")
                                hook_error = getattr(getattr(self, "party_getter_hooks", None), "error", None)
                                require(hook_error is None, f"native observer failed: {hook_error}", "observation-failed")
                                raise
                    if dispatch_setter is not None:
                        try:
                            counts = self.emu.dispatch_counts()
                            interval["guestDispatches"] = counts
                            validate_dispatch_counts(counts, require_complete=cycle_error is None)
                            if counts["frameSequence"] != dispatch_sequence + 1:
                                raise ValueError("guest dispatch frame sequence differs")
                            dispatch_sequence = counts["frameSequence"]
                        except Exception as error:
                            interval["guestDispatchError"] = str(error)
                            if cycle_error is None:
                                require(self.sample_error is None,
                                        f"coherent sampler failed: {self.sample_error}", "observation-failed")
                                hook_error = getattr(getattr(self, "party_getter_hooks", None), "error", None)
                                require(hook_error is None, f"native observer failed: {hook_error}", "observation-failed")
                                raise
                    if phase_setter is not None:
                        try:
                            timings = self.emu.phase_timings()
                            interval["nativePhases"] = timings
                            validate_phase_timings(timings, cpu_ns=interval["cpuNs"],
                                                   require_complete=cycle_error is None)
                            if timings["frameSequence"] != phase_sequence + 1:
                                raise ValueError("native phase frame sequence differs")
                            phase_sequence = timings["frameSequence"]
                        except Exception as error:
                            interval["nativePhaseError"] = str(error)
                            if cycle_error is None:
                                require(self.sample_error is None,
                                        f"coherent sampler failed: {self.sample_error}", "observation-failed")
                                hook_error = getattr(getattr(self, "party_getter_hooks", None), "error", None)
                                require(hook_error is None, f"native observer failed: {hook_error}", "observation-failed")
                                raise
                    if callback_costs is not None or thread_error is not None:
                        try:
                            if callback_costs is not None:
                                interval["callbackCosts"] = callback_costs.result(interval["cpuNs"])
                            if thread_error is not None:
                                raise thread_error
                        except Exception as error:
                            interval["callbackCostError"] = str(error)
                            if cycle_error is None:
                                require(self.sample_error is None,
                                        f"coherent sampler failed: {self.sample_error}", "observation-failed")
                                hook_error = getattr(getattr(self, "party_getter_hooks", None), "error", None)
                                require(hook_error is None, f"native observer failed: {hook_error}", "observation-failed")
                                raise
                native_cycles += 1
                require(self.sample_error is None, f"coherent sampler failed: {self.sample_error}", "observation-failed")
                cycles_without_progress = cycles_without_progress + 1 if self.completed_frames == last_complete else 0
                last_complete = self.completed_frames
                if credited() >= frames:
                    break
                if cycles_without_progress >= 120:
                    break
            require(credited() >= frames,
                    f"step reached only {credited()}/{frames} complete input-consumed game frames "
                    f"within {native_cycles} native cycles", "game-frame-timeout")
            samples = self.pending_samples
            succeeded = True
        except Exception as error:
            step_error = error
            details = {"diagnostics": self.diagnostics(), "cycleIntervals": intervals,
                       "recentSamples": deepcopy(self.pending_samples[-8:]),
                       "completedGameFrames": self.completed_frames - first_frame,
                       "requestedGameFrames": frames, "nativeCycles": native_cycles}
            if isinstance(error, DevtoolsFailure):
                error.details = {**(error.details or {}), **details}
                raise
            raise DevtoolsFailure("step-failed", str(error), details=details) from error
        finally:
            phase_cleanup_error = None
            if phase_previous is not None:
                try:
                    phase_setter(phase_previous)
                except Exception as error:
                    phase_cleanup_error = error
            dispatch_cleanup_error = None
            if dispatch_previous is not None:
                try:
                    dispatch_setter(dispatch_previous)
                except Exception as error:
                    dispatch_cleanup_error = error
            if release_at_end or not succeeded:
                self.rt.h.set_key_mask(self.emu, 0)
            self.pending_samples = None
            self.step_release_at_frame = None
            self.input_step_phase = None
            if phase_cleanup_error is not None:
                if step_error is None:
                    raise DevtoolsFailure("phase-cleanup-failed", str(phase_cleanup_error),
                                         details={"dispatchCleanupError": str(dispatch_cleanup_error)
                                                  if dispatch_cleanup_error is not None else None})
                if isinstance(step_error, DevtoolsFailure):
                    step_error.details = {**(step_error.details or {}),
                                          "nativePhaseCleanupError": str(phase_cleanup_error)}
            if dispatch_cleanup_error is not None:
                if step_error is None:
                    raise DevtoolsFailure("dispatch-cleanup-failed", str(dispatch_cleanup_error))
                if hasattr(step_error, "add_note"):
                    step_error.add_note("Dispatch counter cleanup also failed: " + str(dispatch_cleanup_error))
                if isinstance(step_error, DevtoolsFailure):
                    step_error.details = {**(step_error.details or {}),
                                          "guestDispatchCleanupError": str(dispatch_cleanup_error)}
        completed = self.completed_frames - first_frame
        events = self.drain_events()
        if len(samples) < completed:
            events.append({"frame": self.completed_frames, "kind": "trace-status", "data": {
                "code": "field-samples-unavailable", "count": completed - len(samples),
                "firstFrame": first_frame + 1, "lastFrame": self.completed_frames,
                "coverageComplete": False, "diagnosticOnly": True}})
        # Checked jobs consume the coherent samples, not an extra paused-end
        # terrain grid. Manual input keeps its full diagnostic endpoint.
        endpoint = self.snapshot() if diagnostic_details else self.snapshot(diagnostic_details=False)
        return {"snapshot": endpoint, "samples": samples, "events": events,
                "cycleIntervals": intervals,
                "nativeCycles": native_cycles, "requestedGameFrames": frames,
                "completedGameFrames": completed,
                "inputConsumedGameFrames": phase["consumed"] if phase is not None else None,
                "observedFieldFrames": sum(sample.get("fieldAvailable") is True for sample in samples)}

    def capture(self, path):
        target = owned_path(path, self.directory, exists=False)
        self.emu.screenshot().save(target)
        data = target.read_bytes()
        return {"path": str(target), "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                "frame": self.completed_frames, "nativeCycle": self.rt.EXECUTED_FRAME_COUNT}

    def _new_script_warp_heap_free_observer(self, constructor):
        from tools.overworld.devtools_heap_free_observer import ScriptWarpHeapFreeObserver
        return ScriptWarpHeapFreeObserver(self, constructor)

    def teleport(self, args):
        map_id = integer(args.get("mapId", args.get("map")), "mapId", 0, 539)
        x = integer(args.get("x"), "x", 0, 32767)
        z = integer(args.get("z", args.get("y")), "z", 0, 32767)
        facing = integer(args.get("facing", 0), "facing", 0, 3)
        self.prepared = True
        def recipe(_scratch):
            # Task_ScriptWarp owns/frees this exact stock ErrorContinueEnv.
            # Unlike transition type 6, it has no arrival step to shift x/z.
            callback = self.target("script_warp_task") | 1
            environment = yield Call("allocate_task_environment", (11, 24))
            require(environment % 4 == 0 and 0x02000000 <= environment <= 0x02400000 - 24,
                    "native script-warp environment allocation failed", "allocation-failed")
            self.write(environment, struct.pack("<6i", 0, map_id, -1, x, z, facing))
            field = self.field_pointer()
            task = yield Call("create_field_task", (field, callback, environment))
            constructor = self._control_diagnostics(boundary="native-task-factory-return")
            expected = {"kind": "script-warp", "state": 0, "mapId": map_id, "warpId": -1,
                        "x": x, "z": z, "facing": facing}
            tasks = constructor["tasks"]
            transition = tasks[0].get("transition", {}) if tasks else {}
            owned_task = (tasks and tasks[0]["pointer"] == task == constructor.get("taskPointer")
                          and tasks[0]["function"] == callback and tasks[0]["environment"] == environment
                          and tasks[0]["fieldPointer"] == field and tasks[0]["previous"] == 0)
            if not owned_task or not all(transition.get(key) == value for key, value in expected.items()):
                raise DevtoolsFailure("transition-constructor-mismatch", "native transition task did not retain the requested arguments",
                                      details=constructor)
            return {"mapId": map_id, "x": x, "z": z, "facing": facing, "constructor": constructor,
                    "environmentOwnership": "transferred-to-native-Task_ScriptWarp", "environmentBytes": 24}
        receipt = self.bridge.run(recipe)
        observer = self._new_script_warp_heap_free_observer(receipt["value"]["constructor"])
        self.script_warp_heap_free_observer = observer
        try:
            receipt["snapshot"] = self._wait_new_frame(self.completed_frames,
                lambda value: (value["context"]["mapId"], value["player"]["x"], value["player"]["y"]) == (map_id, x, z)
                and value["player"]["facing"] == facing and value["fieldControl"]["taskPointer"] == 0,
                native_limit=2400, code="transition-timeout",
                message="native map transition did not finish within 2400 native cycles")
            receipt["heapFreeObservation"] = observer.finish()
            return self._prepared_result_boundary(receipt)
        except DevtoolsFailure as error:
            receipt["heapFreeObservation"] = observer.result()
            error.details = {**(error.details or {}), "nativeCommand": receipt}
            raise
        finally:
            observer.closed = True
            if self.script_warp_heap_free_observer is observer:
                self.script_warp_heap_free_observer = None

    def _selector_observation(self):
        # Published selector ABI: overworld_follower_selector.h. Input fields
        # are gSystem.heldKeys/newKeys (stock system.h), read at the same
        # completed main-queue boundary as the actor and party observations.
        rt, emu = self.rt, self.emu
        commands, count, issued, retries, request = struct.unpack("<IBBBB", self.read(0x023C8130, 8))
        key_input, xy_keys = rt.unsigned(emu, 0x04000130, 2), rt.unsigned(emu, 0x027FFFA8, 2)
        return {"state": rt.unsigned(emu, rt.SELECTOR_STATE, 1),
                "highlight": rt.unsigned(emu, rt.SELECTOR_HIGHLIGHT, 1),
                "flags": rt.unsigned(emu, 0x023C8148, 1),
                "heldKeys": rt.unsigned(emu, 0x021D1150), "newKeys": rt.unsigned(emu, 0x021D1154),
                "rawHeld": rt.unsigned(emu, 0x021D1144), "rawNew": rt.unsigned(emu, 0x021D1148),
                "buttonMode": rt.unsigned(emu, 0x021D1140), "simulatedKeys": rt.unsigned(emu, 0x021D1168),
                "keyInput": key_input, "xyKeys": xy_keys,
                "physicalPressed": ((key_input | xy_keys) ^ 0x2FFF) & 0x2FFF,
                # Current linked native selection routine uses exactly these
                # offsetof(OverworldWildSpawnState, ...) locations (3B9/3C0).
                "activeFollowerPartySlot": rt.unsigned(emu, rt.WILD_STATE + 0x3B9, 1),
                "captureTargetMask": rt.unsigned(emu, rt.WILD_STATE + 0x3BA, 2),
                "followerReleaseState": rt.unsigned(emu, rt.WILD_STATE + 0x3C0, 1),
                "follower": rt.wild_spawn(emu, 7),
                "selectedPartySlotObservation": deepcopy(getattr(self, "selected_follower_observation", None)),
                "queue": {"commands": commands, "count": count, "headIssued": issued,
                          "headRetries": retries, "request": request}}

    def _select_party_subject(self, slot, role):
        """Drive ordinary inputs until the menu observes each edge.

        A native cycle is not a field input frame. Short fixed native taps
        can miss a poll, particularly while the game is loading UI assets.
        Menu close proves only that confirmation was consumed; spawn() still
        requires the exact attached live actor after this method returns.
        """
        receipt = {"passed": False, "selections": [], "inputs": []}
        def observation():
            require(self.latest_frame is not None and "selector" in self.latest_frame,
                    "no complete selector observation", "observation-missing")
            return deepcopy(self.latest_frame["selector"])
        def drive(key, predicate, *, minimum_frames=1):
            mask = self.rt.h.keymask(self.rt.h.key_constant(key)) if key else 0
            start = self.completed_frames
            entry = {"key": key, "firstFrame": start, "before": observation()}
            receipt["inputs"].append(entry)
            for native_cycles in range(1, 841):
                self.cycle(1, mask)
                require(self.sample_error is None, f"coherent sampler failed: {self.sample_error}", "observation-failed")
                current = observation()
                frames = self.completed_frames - start
                entry.update(lastFrame=self.completed_frames, nativeCycles=native_cycles, after=current)
                if frames >= minimum_frames and predicate(current):
                    return current
                if frames >= 120:
                    break
            raise DevtoolsFailure("selector-input-timeout", f"selector did not consume {key or 'button release'}")
        def release(*, require_gate=True):
            return drive(None, lambda value: (not require_gate or not (value["flags"] & 0x80))
                         and value["rawHeld"] == 0 and value["rawNew"] == 0
                         and value["heldKeys"] == 0 and value["newKeys"] == 0, minimum_frames=2)
        try:
            current = release()
            if current["state"] == 0:
                drive("Y", lambda value: value["state"] == 2)
                current = release()
            elif current["state"] == 1:
                current = drive(None, lambda value: value["state"] == 2)
            require(current["state"] == 2, "selector did not become visible", "selector-not-visible")
            self._ensure_selector_getter_observer()
            receipt["selections"].append(current["highlight"])
            while current["highlight"] != slot:
                previous = current["highlight"]
                drive("R", lambda value: value["state"] == 2 and value["highlight"] != previous)
                current = release()
                require(current["state"] == 2, "selector closed during navigation", "selector-closed")
                require(current["highlight"] not in receipt["selections"],
                        "requested party slot is not in the menu's eligible cycle", "ineligible-party")
                receipt["selections"].append(current["highlight"])
                require(len(receipt["selections"]) <= 6, "selector visited too many party slots", "selector-state")
            receipt["confirmation"] = drive("SELECT" if role == "MOUNTED" else "Y",
                                             lambda value: value["state"] == 0)
            # TaskPoll clears 0x80 separately from physical-key release. A
            # pending lifecycle must be judged by live actor readback, not
            # reported as a missed release solely because that poll is gated.
            receipt["afterRelease"] = release(require_gate=False)
            receipt["passed"] = True
        except DevtoolsFailure as error:
            receipt.update(reason=error.code, message=str(error))
        finally:
            self.rt.h.set_key_mask(self.emu, 0)
        return receipt

    def _spawn_party_subject(self, slot, role, mon, release_diagnostics="write"):
        from tools.overworld.devtools_release_observer import ReleaseObserver
        observer = ReleaseObserver(self, mode=release_diagnostics)
        observer.install()
        self.release_observer = observer
        try:
            result = self._spawn_party_subject_observed(slot, role, mon)
            result["releaseObservation"] = observer.receipt()
            return result
        except DevtoolsFailure as error:
            error.details = {**(error.details or {}), "releaseObservation": observer.receipt()}
            raise
        finally:
            self.release_observer = None
            observer.close()

    def _spawn_party_subject_observed(self, slot, role, mon):
        """Prepared fixture setup through native lifecycle APIs, not the UI.

        The normal Y queue remains testable via step(). This operation never
        clears that queue or any release/motion state to manufacture success.
        """
        receipt = {"lifecycle": "prepared-native-follower-lifecycle", "preparedOnly": True,
                   "requestedSubject": {"slot": slot, "role": role, "species": mon["species"],
                                        "personality": mon["personality"], "form": mon["form"],
                                        "level": mon["level"]}, "nativeCommands": []}
        def matches(snapshot, required_role):
            return snapshot["selector"]["activeFollowerPartySlot"] == slot and any(
                       actor["identityVerified"] and actor["role"] == required_role
                       and actor["species"] == mon["species"]
                       and actor["form"] == mon["form"] and actor["level"] == mon["level"]
                       and actor["subjectIdentity"] == mon["personality"] for actor in snapshot["actors"])
        def release_settled(snapshot):
            selector = snapshot["selector"]
            return (selector["queue"]["count"] == 0 and selector["queue"]["request"] == 0
                    and selector["followerReleaseState"] == 0
                    and not (selector["captureTargetMask"] & (1 << 7)))
        def command(name, args, *, boolean=True):
            def recipe(_scratch):
                value = yield Call(name, args)
                return {"routine": name, "returned": value}
            result = self.bridge.run(recipe)
            receipt["nativeCommands"].append(result)
            require(not boolean or result["value"]["returned"] == 1,
                    f"native {name} request was rejected", "spawn-rejected")
        def wait_for(predicate, message):
            return self._wait_new_frame(self.completed_frames, predicate, native_limit=1800,
                                        code="spawn-failed", message=message)
        try:
            snapshot = self.snapshot(0)
            require(release_settled(snapshot), "a follower selection/release is already pending", "busy")
            if matches(snapshot, role):
                return {**receipt, "alreadySelected": True, "snapshot": self.snapshot()}
            self.require_quiescent()
            selector = snapshot["selector"]
            current = [actor for actor in snapshot["actors"] if actor["role"] in ("FOLLOWER", "MOUNTED")]
            if any(actor["role"] == "MOUNTED" for actor in current):
                command("cancel_mount", (1,), boolean=False)
                snapshot = wait_for(lambda value: not any(actor["role"] == "MOUNTED" for actor in value["actors"]),
                                    "native dismount did not finish")
            if not matches(snapshot, "FOLLOWER"):
                if selector["follower"]["active"] or current:
                    command("recall_follower", (self.field_pointer(), 0xFF))
                    snapshot = wait_for(lambda value: not value["selector"]["follower"]["active"]
                                        and not any(actor["role"] in ("FOLLOWER", "MOUNTED") for actor in value["actors"]),
                                        "native follower recall did not finish")
                # SelectFollowerPartySlot toggles an active same-slot follower
                # off. The exact-current check and completed recall above are
                # required before selecting, even if species happen to match.
                command("recall_follower", (self.field_pointer(), slot))
                snapshot = wait_for(lambda value: matches(value, "FOLLOWER"),
                                    "native selection did not produce the exact follower")
            # A visible follower is not necessarily released from its ball
            # yet. Both follower and mounted setup wait for normal ownership
            # to settle, so the next tool command can safely use that actor.
            snapshot = wait_for(lambda value: matches(value, "FOLLOWER") and release_settled(value)
                                    and any(actor["role"] == "FOLLOWER" and actor["motionPhase"] == "IDLE"
                                            and actor["reservationId"] == 0 for actor in value["actors"]),
                                    "selected follower release presentation did not settle")
            if role == "MOUNTED":
                command("mount_selected_follower", (self.field_pointer(), self.rt.WILD_STATE))
                snapshot = wait_for(lambda value: matches(value, "MOUNTED"),
                                    "native mount request did not produce the exact ridden actor")
            require(matches(snapshot, role) and release_settled(snapshot),
                    "native lifecycle has no stable exact requested actor", "spawn-failed")
            receipt["snapshot"] = snapshot
            return receipt
        except DevtoolsFailure as error:
            error.details = {**(error.details or {}), "nativeSetup": receipt,
                             "snapshot": deepcopy(self.latest_frame) if self.emu is None
                                 or getattr(getattr(self, "release_observer", None), "failure", None) is not None
                                 else self.snapshot()}
            raise

    def _prepared_result_boundary(self, receipt):
        """Retain excluded setup events without resetting any native trace.

        The writer tap can already have read the next incomplete queue. Those
        pending events stay pending, and are not included in this watermark.
        """
        snapshot = receipt["snapshot"]
        frame = integer(snapshot.get("frame"), "setup frame", 0, 0xFFFFFFFF)
        cycle = integer(snapshot.get("nativeCycle"), "setup native cycle", 0, 0xFFFFFFFF)
        endpoint = integer(self.rt.EXECUTED_FRAME_COUNT, "setup endpoint cycle", cycle, 0xFFFFFFFF)
        require(frame == self.completed_frames and snapshot.get("prepared") is True,
                "prepared result lacks a current completed snapshot", "observation-failed")
        require(self.sample_error is None, "prepared result sampler failed", "observation-failed")
        if self.native_observation is not None:
            require(self.native_observation.hooks.error is None,
                    "prepared result native observer failed", "observation-failed")
        require("events" not in receipt and "setupBoundary" not in receipt,
                "prepared result was already drained", "observation-failed")
        sequences = {}
        trace = self.semantic_trace
        if trace is not None and trace.running:
            stream = integer(trace.stream, "setup trace stream", 1, 0xFFFFFFFF)
            last = integer(trace._next, "setup next trace sequence", 1, 0xFFFFFFFF) - 1
            pending = [event["data"]["sequence"] for event in self.trace_pending
                       if event.get("kind") == "native" and event.get("data", {}).get("traceStream") == stream]
            if pending:
                for sequence in pending:
                    integer(sequence, "pending trace sequence", 1, last)
                last = min(pending) - 1
            sequences[str(stream)] = last
        self._retain_prepared_events()
        retained = getattr(self, "_prepared_retained_events", None)
        receipt["events"] = list(retained) if retained is not None else self.drain_events()
        retained_sequences = {}
        for event in receipt["events"]:
            if event.get("kind") == "native":
                data = event.get("data", {})
                stream = str(integer(data.get("traceStream"), "retained trace stream", 1, 0xFFFFFFFF))
                sequence = integer(data.get("sequence"), "retained trace sequence", 1, 0xFFFFFFFF)
                retained_sequences[stream] = max(sequence, retained_sequences.get(stream, 0))
        for stream, sequence in retained_sequences.items():
            require(stream not in sequences or sequence <= sequences[stream],
                    "retained event exceeds completed trace watermark", "observation-failed")
            sequences.setdefault(stream, sequence)
        receipt["setupBoundary"] = {"eventsDrained": True, "traceSequences": sequences,
            "frame": frame, "nativeCycle": cycle, "endpointNativeCycle": endpoint}
        return receipt

    def spawn(self, args):
        role = args.get("role", "WILD").upper()
        require(role in ("WILD", "FOLLOWER", "MOUNTED"), "spawn role is invalid", "invalid-argument")
        diagnostics = args.get("releaseDiagnostics", "write")
        require(diagnostics in ("write", "irq"), "release diagnostics must be write or irq", "invalid-argument")
        require(role != "WILD" or "releaseDiagnostics" not in args,
                "release diagnostics apply only to follower/mounted spawn", "invalid-argument")
        profile_diagnostics = args.get("profileDiagnostics")
        require(profile_diagnostics in (None, "owner-transfer", "owner-transfer-control")
                and (role != "WILD" or "profileDiagnostics" not in args)
                and (profile_diagnostics != "owner-transfer-control" or role == "MOUNTED"),
                "profile diagnostics require follower/mounted owner-transfer", "invalid-argument")
        self.prepared = True
        if role != "WILD":
            party = self.party_snapshot()
            requested_slot = args.get("partySlot", args.get("slot"))
            if requested_slot is None:
                matches = [mon["slot"] for mon in party if mon["species"] == args.get("species")]
                require(len(matches) == 1, "choose a party slot for this species", "invalid-argument")
                requested_slot = matches[0]
            slot = integer(requested_slot, "partySlot", 0, 5)
            require(slot < len(party) and not party[slot]["isEgg"] and party[slot]["hp"] > 0,
                    "selected party Pokémon cannot be a follower", "ineligible-party")
            require(args.get("species", party[slot]["species"]) == party[slot]["species"],
                    "requested species differs from the selected party Pokémon", "wrong-subject")
            require(getattr(self, "_prepared_retained_events", None) is None,
                    "prepared event retention is already active", "busy")
            self._prepared_retained_events, self._prepared_retained_bytes = [], 0
            try:
                capture = (self.native_observation.role_profiles.capture(control=True)
                    if profile_diagnostics == "owner-transfer-control" else
                    self.native_observation.role_profiles.capture() if profile_diagnostics else nullcontext())
                with capture:
                    if diagnostics == "irq":
                        result = self._spawn_party_subject(slot, role, party[slot], release_diagnostics="irq")
                    else:
                        result = self._spawn_party_subject(slot, role, party[slot])
                if profile_diagnostics:
                    result["profileDiagnostics"] = profile_diagnostics
                result = self._prepared_result_boundary(result)
                if profile_diagnostics:
                    # The manual command log excludes the general event list.
                    # Keep these bounded, completed-frame receipts explicitly
                    # so diagnostics are replayable after the core is closed.
                    result["profileObservation"] = {
                        "acceptedProof": False,
                        "scope": ("native reader calibration only; not gameplay proof"
                            if profile_diagnostics == "owner-transfer-control" else
                            "prepared follower getter and mount Owner transfer only"),
                        "events": deepcopy([event for event in result["events"]
                            if event.get("kind") == "native-observation"
                            and event.get("data", {}).get("observation") in
                                ("role-profile-getter", "role-profile-mount")])}
                return result
            except Exception as error:
                evidence = self._prepared_retained_events + self.drain_events()
                if isinstance(error, DevtoolsFailure):
                    error.details = {**(error.details or {}), "preparedRetainedEvents": evidence}
                    raise
                raise DevtoolsFailure("prepared-observation-failed", str(error),
                    details={"preparedRetainedEvents": evidence}) from error
            finally:
                self._prepared_retained_events = None
                self._prepared_retained_bytes = 0
        species = integer(args.get("species"), "species", 1, 1075)
        level = integer(args.get("level", 5), "level", 1, 100)
        form = integer(args.get("form", 0), "form", 0, 31)
        pid = self._prepared_personality(args)
        player = self.rt.object_state(self.emu, self.rt.player_ptr(self.emu))
        x = integer(args.get("x", player["x"] + 2), "x", 0, 32767)
        z = integer(args.get("z", args.get("y", player["y"])), "z", 0, 32767)
        terrain = integer(args.get("terrain", 0), "terrain", 0, 3)
        require(self.rt.loaded_terrain_cell(self.emu, x, z) is not None,
                "requested spawn cell is not loaded", "unloaded-terrain")
        slot = next((i for i in range(6) if not self.rt.wild_spawn(self.emu, i)["active"]), None)
        require(slot is not None, "all six regular wild slots are occupied", "population-full")
        def recipe(scratch):
            prepared = bytearray(268)
            struct.pack_into("<ii", prepared, 0, x, z)
            struct.pack_into("<IHBB", prepared, 12, pid, species, form, level)
            struct.pack_into("<i", prepared, 260, -1)
            self.write(scratch, prepared)
            native_args = (self.rt.WILD_STATE, self.field_pointer(), terrain, slot, scratch)
            accepted = yield Call("finalize_spawn", native_args)
            require(accepted == 1, "native profile/terrain/startup rejected this spawn", "spawn-rejected")
            finalized_pid = struct.unpack("<I", self.read(scratch + 12, 4))[0]
            accepted = yield Call("spawn_encounter", native_args)
            require(accepted == 1, "native spawn lifecycle rejected this encounter", "spawn-rejected")
            return {"slot": slot, "species": species, "personality": finalized_pid, "requestedPersonality": pid}
        receipt = self.bridge.run(recipe)
        snapshot = self._wait_new_frame(self.completed_frames,
            lambda value: any(a["identityVerified"] and a["role"] == role and a["handle"]["slot"] == slot
                              and a["subjectIdentity"] == receipt["value"]["personality"] and a["species"] == species
                              for a in value["actors"]),
            native_limit=1200, code="spawn-failed", message="spawn did not produce the requested bound actor")
        receipt["snapshot"] = snapshot
        return self._prepared_result_boundary(receipt)

    def mount_walk_configure(self, args):
        """Bounded private fixture setup; never changes authored profiles."""
        from tools.overworld.devtools_contract import validate_command
        from tools.overworld.devtools_mount_walk_fixture import MountWalkFixture
        args = validate_command("mount-walk.configure", args)
        self.prepared = True
        try:
            receipt = MountWalkFixture(self, args["subject"], args["directionMode"],
                                       args.get("travelTime"), args.get("stompTime"),
                                       turning=args.get("turning"), crash_sound=args.get("crashSound")).run()
        except Exception as error:
            if getattr(error, "receipt", None) is not None:
                error.details = {"mountWalkFixture": error.receipt}
            raise
        receipt["snapshot"] = self.snapshot(0, diagnostic_details=False)
        return self._prepared_result_boundary(receipt)

    def mount_teleport_configure(self, args):
        """Set three Teleport lane fields in one checked private fixture."""
        from tools.overworld.devtools_contract import validate_command
        from tools.overworld.devtools_mount_teleport_fixture import MountTeleportFixture
        args = validate_command("mount-teleport.configure", args)
        self.prepared = True
        try:
            receipt = MountTeleportFixture(
                self, args["subject"], args["locomotion"],
                args["teleportTime"], args["teleportPause"],
            ).run()
        except Exception as error:
            if getattr(error, "receipt", None) is not None:
                error.details = {"mountTeleportFixture": error.receipt}
            raise
        if not hasattr(self, "_mount_teleport_original"):
            profile = bytes.fromhex(receipt["before"]["profileHex"])
            if profile[12] == 1:
                self._mount_teleport_original = (self.emu, deepcopy(args["subject"]["handle"]), profile)
        receipt["snapshot"] = self.snapshot(0, diagnostic_details=False)
        return self._prepared_result_boundary(receipt)

    def mount_teleport_restore(self, args):
        from tools.overworld.devtools_contract import validate_command
        from tools.overworld.devtools_mount_teleport_fixture import MountTeleportRestoreFixture
        args = validate_command("mount-teleport.restore", args)
        saved = getattr(self, "_mount_teleport_original", None)
        require(saved is not None and saved[0] is self.emu and saved[1] == args["subject"]["handle"],
                "restore has no original profile for this session and actor", "invalid-argument")
        receipt = MountTeleportRestoreFixture(self, args["subject"], saved[2]).run()
        del self._mount_teleport_original
        receipt["snapshot"] = self.snapshot(0, diagnostic_details=False)
        return self._prepared_result_boundary(receipt)

    def walk_policy_reset(self, args):
        """Checked public idle RESET; prepared arrangement, never proof."""
        require(isinstance(args, dict) and set(args) == {"subject"},
                "walk-policy.reset requires only the exact subject", "invalid-argument")
        from tools.overworld.devtools_walk_reset import WalkPolicyReset
        self.prepared = True
        reset = WalkPolicyReset(self, args["subject"])
        receipt = self.bridge.run(lambda scratch: reset.recipe(scratch, Call))
        receipt["acceptedProof"] = False
        # The receipt retains the exact native before/after states. This paused
        # endpoint does not advance a new game tick or earn movement credit.
        receipt["snapshot"] = self.snapshot(0, diagnostic_details=False)
        return self._prepared_result_boundary(receipt)

    def _actor_inspect_probe_service(self):
        """Bind the fixed call to the live, packaged public facade."""
        descriptor = self.rt.ACTOR_DESCRIPTOR
        facade, state = descriptor["facade"], descriptor["state"]
        target = self.target("inspect_actor")
        require(facade["version"] == 1 and facade["size"] == 24
                and facade["callbacks"]["inspect"] == target | 1,
                "actor Inspect facade differs from linked target", "abi-mismatch")
        expected = struct.pack("<IHH4I", 0x5341574F, 1, 24,
                               *(facade["callbacks"][name] for name in
                                 ("validate", "apply", "tick", "inspect")))
        require(self.packaged_code(facade["address"], 24) == expected,
                "actor facade differs from package", "abi-mismatch")
        require(self.read(state["address"], 8) == struct.pack("<IHH", 0x5353574F, 1, state["size"]),
                "actor state is not already initialized", "actor-inspect-uninitialized")
        return {"address": facade["address"], "version": 1, "size": 24,
                "facadeHex": expected.hex(), "inspectAddress": target | 1,
                "entrySha256": hashlib.sha256(self.packaged_code(target, 32)).hexdigest()}

    def actor_inspect_probe(self, args):
        """Two fixed prepared Inspect calls for one exact current actor."""
        require(isinstance(args, dict) and set(args) == {"handle"},
                "actor-inspect.probe requires only a handle", "invalid-argument")
        handle = integer(args["handle"], "handle", 1, 0xffffffff)
        self.prepared = True
        self.require_quiescent()
        service = self._actor_inspect_probe_service()
        snapshot = self._snapshot(0, details=False)
        matches = [actor for actor in snapshot["actors"]
                   if actor.get("handle", {}).get("value") == handle]
        require(len(matches) == 1 and matches[0].get("identityVerified") is True,
                "probe handle does not identify one current actor", "actor-inspect-subject-missing")
        from tools.overworld.devtools_actor_inspect_probe import ActorInspectProbe
        probe = ActorInspectProbe(self, expected_actor=matches[0], service_identity=service)
        receipt = self.bridge.run(lambda scratch: probe.recipe(scratch, Call))
        require(self._actor_inspect_probe_service() == service,
                "actor Inspect service changed during probe", "abi-mismatch")
        receipt["acceptedProof"] = False
        receipt["snapshot"] = self._wait_new_frame(self.completed_frames, lambda _value: True,
            native_limit=120, code="actor-inspect-readback-timeout",
            message="actor Inspect probe has no completed frame")
        return self._prepared_result_boundary(receipt)

    def _resolver_probe_inputs(self):
        discovery = getattr(self.native_observation, "resolver_discovery", None)
        require(isinstance(discovery, dict) and discovery.get("status") == 0,
                "no successful natural resolver discovery", "resolver-discovery-missing")
        require(discovery.get("fieldPointer") == self.field_pointer()
                and discovery.get("heapGeneration") == self.native_heap_generation,
                "natural resolver discovery has a stale field owner", "resolver-discovery-stale")
        services = [s for s in self.rt.ACTOR_DESCRIPTOR["privateServices"] if s.get("name") == "resolver"]
        require(len(services) == 1 and services[0].get("status") == "available",
                "packaged resolver service is unavailable", "abi-mismatch")
        service = services[0]
        target = self.target("resolve_behavior")
        expected = struct.pack("<IHHII", 0x5250574F, 1, 16,
                               service["callbacks"]["resolve"], service["callbacks"]["inspectClass"])
        require(service["version"] == 1 and service["size"] == 16
                and service["callbacks"]["resolve"] == target | 1
                and self.packaged_code(service["address"], 16) == expected,
                "native resolver service differs from linked target", "abi-mismatch")
        blob = (self.rt.REPO / "build/OverworldWildBehaviorData.bin").read_bytes()
        address = discovery.get("blobAddress")
        require(0 < len(blob) <= 1024 * 1024 and discovery.get("blobSize") == len(blob)
                and type(address) is int and address % 4 == 0
                and 0x02000000 <= address <= 0x02400000 - len(blob),
                "natural resolver blob extent differs", "resolver-blob-mismatch")
        require(all(self.read(address + offset, len(blob[offset:offset + 4096])) == blob[offset:offset + 4096]
                    for offset in range(0, len(blob), 4096)),
                "live resolver blob differs from packaged data", "resolver-blob-mismatch")
        return {"blob_address": address, "blob_bytes": blob,
                "service_identity": {"magic": 0x5250574F, "version": 1, "size": 16,
                    "resolveAddress": target | 1,
                    "entrySha256": hashlib.sha256(self.packaged_code(target, 32)).hexdigest()}}

    def resolver_probe(self, args):
        """Seven fixed prepared service calls; no actor or acceptance credit."""
        require(args == {}, "resolver.probe takes no arguments", "invalid-argument")
        self.prepared = True
        self.require_quiescent()
        from tools.overworld.devtools_resolver_probe import ResolverProbe
        inputs = self._resolver_probe_inputs()
        probe = ResolverProbe(self, **inputs)
        receipt = self.bridge.run(lambda scratch: probe.recipe(scratch, Call))
        # Recheck service and source after all calls and native allocation free.
        require(self._resolver_probe_inputs() == inputs,
                "resolver inputs changed during probe", "resolver-probe-input-changed")
        receipt["naturalDiscovery"] = deepcopy(self.native_observation.resolver_discovery)
        receipt["acceptedProof"] = False
        receipt["snapshot"] = self._wait_new_frame(self.completed_frames, lambda _value: True,
            native_limit=120, code="resolver-readback-timeout", message="resolver probe has no completed frame")
        return self._prepared_result_boundary(receipt)

    def _probe_exp_work_memory(self):
        pointer = yield Call("allocate_work_memory", (11, 404))
        require(pointer != 0, "not enough EXP work memory for this prepared party change", "insufficient-exp-work-memory")
        if pointer % 4 != 0 or not 0x02000000 <= pointer <= 0x02400000 - 404:
            raise DevtoolsFailure("native-exp-work-allocation", "EXP work memory probe returned an invalid pointer", fatal=True)
        receipt = {"heapId": 11, "bytes": 404, "nativeAllocation": pointer, "released": False}
        self.native_allocations[pointer] = {"purpose": "prepared-exp-capacity-probe", "bytes": 404}
        try:
            return receipt
        finally:
            if self.emu is not None:
                yield Call("free", (pointer,))
                self.native_allocations.pop(pointer)
                receipt["released"] = True

    def party(self, args):
        before = self.party_snapshot()
        action = args.get("action", ("create" if args.get("slot") == len(before) else "replace") if "species" in args else "edit")
        require(action in ("create", "replace", "edit"), "party action is invalid", "invalid-argument")
        slot = integer(args.get("slot", len(before) if action == "create" else None), "slot", 0, 5)
        require((action == "create" and slot == len(before)) or
                (action != "create" and slot < len(before)), "party slot does not match action", "invalid-argument")
        if action != "edit":
            species = integer(args.get("species"), "species", 1, 1075)
            level = integer(args.get("level", 5), "level", 1, 100)
            form = integer(args.get("form", 0), "form", 0, 31)
            pid = self._prepared_personality(args)
        else:
            if "level" in args:
                integer(args["level"], "level", 1, 100)
            if "form" in args:
                integer(args["form"], "form", 0, 31)
        moves = args.get("moves")
        if moves is not None:
            require(isinstance(moves, list) and len(moves) == 4, "moves must contain four move IDs", "invalid-argument")
            for move in moves:
                integer(move, "move", 0, 922)
            require(len([m for m in moves if m]) == len(set(m for m in moves if m)), "moves must not repeat", "invalid-argument")
            require(any(moves), "a Pokémon needs at least one move", "invalid-argument")
        if "hp" in args:
            require(args["hp"] == "max" or type(args["hp"]) is int and 0 <= args["hp"] <= 65535,
                    "hp must be max or a nonnegative integer", "invalid-argument")
        if "status" in args:
            integer(args["status"], "status", 0, 255)
        self.prepared = True
        recall_receipt = None
        follower = self.rt.actor_state(self.emu, 7)
        if follower["active"]:
            self.require_quiescent()
            def recall(_scratch):
                if follower["role"] == "MOUNTED":
                    yield Call("cancel_mount", (1,))
                accepted = yield Call("recall_follower", (self.field_pointer(), 0xFF))
                require(accepted == 1, "native follower recall request was rejected")
                return {"previousSubject": follower["subjectIdentity"]}
            recall_receipt = self.bridge.run(recall)
            for _ in range(1800):
                self.cycle(1)
                if not self.rt.actor_state(self.emu, 7)["active"]:
                    break
            require(not self.rt.actor_state(self.emu, 7)["active"], "follower recall did not finish", "recall-timeout")
        self.native_allocations = getattr(self, "native_allocations", {})
        needs_exp_work = action != "edit" or "level" in args or "form" in args
        memory_preflights = []
        def recipe_body(scratch, ownership):
            temporary = 0
            if action != "edit":
                temporary = yield Call("allocate_mon", (11,))
                require(0x02000000 <= temporary < 0x02400000, "native Pokémon allocation failed")
                ownership[0] = temporary
                self.native_allocations[temporary] = {"purpose": "temporary-party-pokemon", "bytes": 236}
                memory_preflights.append((yield from self._probe_exp_work_memory()))
                yield Call("create_mon", (temporary, species, level, 32, 1, pid, 0, 0))
                mon = temporary
                self.write(scratch, bytes([form]))
                yield Call("set_mon", (mon, 112, scratch))
                yield Call("recalc_mon", (mon,))
            else:
                mon = self.party_pointer() + 8 + slot * 236
                if needs_exp_work:
                    memory_preflights.append((yield from self._probe_exp_work_memory()))
                if "level" in args:
                    exp = yield Call("level_exp", (before[slot]["species"], args["level"]))
                    self.write(scratch, struct.pack("<I", exp))
                    yield Call("set_mon", (mon, 8, scratch))
                if "form" in args:
                    self.write(scratch, bytes([args["form"]]))
                    yield Call("set_mon", (mon, 112, scratch))
                if "level" in args or "form" in args:
                    yield Call("recalc_mon", (mon,))
            if moves is not None:
                # Delete canonically from the end, then install nonzero slots.
                # Existing history is retained by the history service.
                for index in range(3, -1, -1):
                    yield Call("delete_move", (mon, index))
                for index, move in enumerate(moves):
                    if move:
                        accepted = yield Call("replace_move", (mon, move, index))
                        require(accepted == 1, f"native move service rejected move {move}")
            if "status" in args:
                self.write(scratch, struct.pack("<I", args["status"]))
                yield Call("set_mon", (mon, 160, scratch))
            if "hp" in args:
                maximum = yield Call("get_mon", (mon, 164, 0))
                hp = maximum if args["hp"] == "max" else args["hp"]
                require(hp <= maximum, "requested HP is greater than maximum")
                self.write(scratch, struct.pack("<H", hp))
                yield Call("set_mon", (mon, 163, scratch))
            if action == "create":
                accepted = yield Call("add_party_mon", (self.party_pointer(), mon))
                require(accepted == 1, "native party add failed")
            elif action == "replace":
                yield Call("copy_party_mon", (self.party_pointer(), slot, mon))
            if temporary:
                yield Call("free", (temporary,))
                ownership[0] = 0
                self.native_allocations.pop(temporary)
            yield Call("seed_history", (self.party_pointer() - 0xA0, self.party_pointer() + 8 + slot * 236))
            yield Call("selector_close", ())
            yield Call("selector_refresh", ())
            return {"slot": slot, "action": action, "memoryPreflights": memory_preflights}
        def recipe(scratch):
            ownership = [0]
            try:
                return (yield from recipe_body(scratch, ownership))
            finally:
                # A handled rejection (HP, move, party capacity) must free
                # our temporary Pokémon before its error reaches the bridge.
                # If this native cleanup cannot return, the bridge closes the
                # disposable core rather than resume with a leaked allocation.
                if ownership[0] and self.emu is not None:
                    yield Call("free", (ownership[0],))
                    self.native_allocations.pop(ownership[0])
                    ownership[0] = 0
        receipt = self.bridge.run(recipe, prepared_party_work_heap=needs_exp_work)
        receipt["recall"] = recall_receipt
        snapshot = self._wait_new_frame(self.completed_frames, lambda _value: True, native_limit=120,
                                       code="party-readback-timeout", message="party edit has no new complete frame")
        receipt["party"] = snapshot["party"]
        after = receipt["party"][slot]
        receipt["personality"] = after["personality"]
        receipt["preparedIdentitySource"] = "explicit-or-session-command-sequence-sha256"
        for key in ("species", "level", "form", "status", "moves"):
            if key in args:
                require(after[key] == args[key], f"native party {key} readback differs", "party-readback-failed")
        if "hp" in args:
            require(after["hp"] == (after["maxHp"] if args["hp"] == "max" else args["hp"]),
                    "native party HP readback differs", "party-readback-failed")
        receipt["snapshot"] = snapshot
        return self._prepared_result_boundary(receipt)

    def close(self):
        try:
            self._close_role_profile_window()
        finally:
            try:
                self._close_core()
            finally:
                self.closed = True

    def _close_core(self):
        if self.emu is not None:
            emu = self.emu
            try:
                if getattr(self, "observer_control", None) is not None:
                    self.observer_control.close()
                if getattr(self, "route_control", None) is not None:
                    self.route_control.close()
                if getattr(self, "chain_retry_control", None) is not None:
                    self.chain_retry_control.close()
                if getattr(self, "walk_intent", None) is not None:
                    self.walk_intent.close(disposing=True)
                if getattr(self, "walk_policy_control", None) is not None:
                    self.walk_policy_control.close()
                if getattr(self, "mount_pacing", None) is not None:
                    self.mount_pacing.close(disposing=True)
                if getattr(self, "hop_arc", None) is not None:
                    self.hop_arc.close(disposing=True)
                if getattr(self, "wild_walk", None) is not None:
                    self.wild_walk.close(disposing=True)
                if getattr(self, "wild_ledge", None) is not None:
                    self.wild_ledge.close(disposing=True)
                if getattr(self, "walk_corner", None) is not None:
                    self.walk_corner.close(disposing=True)
                if getattr(self, "walk_matrix", None) is not None:
                    self.walk_matrix.close(disposing=True)
                if getattr(self, "stomp_feedback", None) is not None:
                    self.stomp_feedback.close(disposing=True)
                if getattr(self, "crash_feedback", None) is not None:
                    self.crash_feedback.close(disposing=True)
                # No game resumes after this instrumentation shutdown.
                if self.semantic_trace is not None:
                    self.semantic_trace.stop()
                if self.sampling_hook is not None:
                    emu.memory.register_exec(self.sampling_hook, None)
                if self.native_observation is not None:
                    self.native_observation.close()
                if self.party_getter_hooks is not None:
                    self.party_getter_hooks.close()
                self.rt.h.set_key_mask(emu, 0)
            finally:
                self.emu = None
                emu.destroy()
