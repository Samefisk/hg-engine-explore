"""Opt-in, read-only Snorlax Slam admission and nested occupancy receipts.

This diagnostic owns only its record-window hooks. It makes no guest calls,
writes, inputs or extra frames. Synthetic host receipts are not game proof.
"""
from copy import deepcopy
import hashlib
import struct

from tools.overworld.devtools_observer import NativeObservationError, MOTION_DECISIONS
from tools.overworld.devtools_runtime import _elf_function_extent

PINS = {
    "owner": ("overworld_wild_spawns_overlay_linked.o", "OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand", 0x023D6334, 2698, "11c6e0643b1634b9c8e280c27498f9955876c53b79f43f0f1a4523f8ef09a8a9"),
    "attempt": ("overworld_wild_spawns_overlay_linked.o", "OverworldWildSpawns_TryStartBehaviorHopToPlannedTileWithArc", 0x023D0F4C, 484, "73655a74901f6792c5a13ca3767e1da1796488d72258434eb26f1f8eae172584"),
    "landing": ("overworld_wild_spawns_overlay_linked.o", "OverworldWildSpawns_ClassifyBehaviorHopLandingTile", 0x023CE638, 188, "bd03028730af0b13d01ade584d053bfac0b5adde1c8981f33437fde70531de08"),
    "occupancy": ("pokemon_move_history_overlay_linked.o", "OverworldWildOccupancy_Query", 0x023C0184, 214, "b09b014858b6e88d9e699d29d9db7eb25a2c1a654c22a0eb45e7f641eb45e78b"),
}
QUERY_OCCUPANCY = (9356, 436, 'ce26746f2668f9f511c9d5e8a7ce19e05b75817ccdf9337d24a26e21141004e1')
QUERY_OCCUPANCY_CALL = 0x15C


def need(ok, reason):
    if not ok:
        raise NativeObservationError("slam admission reader: " + reason)


def _query_occupancy_owner(path):
    # Entry admission has a separate local function with the same name.
    # Select the exact linked route owner; a duplicate exact selector fails.
    data = path.read_bytes()
    need(len(data) >= 52 and data[:7] == b"\x7fELF\x01\x01\x01"
         and struct.unpack_from("<HH", data, 16) == (2, 40), "Query ELF type differs")
    table = struct.unpack_from("<I", data, 32)[0]
    stride, count, names_index = struct.unpack_from("<HHH", data, 46)
    need(stride == 40 and names_index < count and table <= len(data)
         and count * stride <= len(data) - table, "Query section table differs")
    sections = [struct.unpack_from("<10I", data, table + i * stride) for i in range(count)]
    names = sections[names_index]
    need(names[1] == 3 and names[4] <= len(data) and names[5] <= len(data) - names[4],
         "Query section names differ")
    section_names = data[names[4]:names[4] + names[5]]
    matches = []
    address, size = 0x02080000 + QUERY_OCCUPANCY[0], QUERY_OCCUPANCY[1]
    for row in sections:
        if row[1] != 2:
            continue
        need(row[9] == 16 and row[5] % 16 == 0 and row[6] < count
             and row[4] <= len(data) and row[5] <= len(data) - row[4], "Query symbol table differs")
        strings = sections[row[6]]
        need(strings[4] <= len(data) and strings[5] <= len(data) - strings[4], "Query symbol names differ")
        symbols = data[strings[4]:strings[4] + strings[5]]
        for offset in range(row[4], row[4] + row[5], 16):
            label, value, extent, info, _other, index = struct.unpack_from("<IIIBBH", data, offset)
            need(label < len(symbols) and b"\0" in symbols[label:], "Query symbol name differs")
            if symbols[label:].split(b"\0", 1)[0] != b"Occupancy":
                continue
            need(info & 15 == 2 and value & 1 and 0 < index < count and extent > 0,
                 "Query Occupancy symbol type differs")
            owner = sections[index]
            need(owner[1] == 1 and owner[2] & 6 == 6
                 and owner[0] < len(section_names) and b"\0" in section_names[owner[0]:]
                 and owner[4] <= len(data) and owner[5] <= len(data) - owner[4]
                 and section_names[owner[0]:].split(b"\0", 1)[0] == b".text"
                 and owner[3] <= value & ~1 <= owner[3] + owner[5] - extent,
                 "Query Occupancy executable owner differs")
            if (value & ~1, extent) == (address, size):
                start = owner[4] + address - owner[3]
                code = data[start:start + size]
                need(len(code) == size and hashlib.sha256(code).hexdigest() == QUERY_OCCUPANCY[2],
                     "Query Occupancy full linked body differs")
                matches.append((address, size))
    need(len(matches) == 1, "Query Occupancy exact owner missing or ambiguous")
    return matches[0]


class SlamAdmissionObserver:
    MAX_ATTEMPTS = 256

    def __init__(self, observer):
        self.observer, self.session = observer, observer.session
        self.active, self.count = True, 0
        self.tokens, self.returns, self.contexts = [], [], []
        self.attempts, self.landings, self.code = [], [], {}
        try:
            for key, (file, name, address, size, sha) in PINS.items():
                path = self.session.rt.REPO / "build" / file
                need(_elf_function_extent(path, name) == (address, size), key + " typed owner differs")
                code = observer.elf_code(path, address, size)
                need(hashlib.sha256(code).hexdigest() == sha, key + " full body differs")
                need(self.session.packaged_code(address, size) == code, key + " ROM body differs")
                self.code[key] = code
            query_path = self.session.rt.REPO / "build/overworld_query_code_addon/image.elf"
            _query_occupancy_owner(query_path)
            self._tap("attempt", self._attempt_before, self._attempt_after)
            self._tap("landing", self._landing_before, self._landing_after)
            self._tap("occupancy", self._occupancy_before, self._occupancy_after)
        except Exception:
            self.close()
            raise

    def _live(self, key):
        need(self.observer._live_code(PINS[key][2], self.code[key]) == self.code[key],
             key + " live full body differs")

    def _direct(self, key, site, target):
        regs = self.session.emu.memory.register_arm9
        need(regs.lr & ~1 == site + 4, "direct caller site differs")
        offset = site - PINS[key][2]
        raw = self.code[key][offset:offset + 4]
        high, low = struct.unpack("<HH", raw)
        delta = (high & 0x7FF) << 12 | (low & 0x7FF) << 1
        if delta & 0x400000:
            delta -= 0x800000
        need(high & 0xF800 == 0xF000 and low & 0xF800 == 0xF800
             and site + 4 + delta == PINS[target][2], "direct Thumb call target differs")
        need(self.observer._live_code(site, raw) == raw, "direct live caller differs")

    def _check(self, parent, *, full=False):
        need(any(item is parent for item in self.attempts), "lost attempt owner")
        obs, rt, emu = self.observer, self.session.rt, self.session.emu
        if full:
            subject, source, engine, world = obs._chain_current(parent["slot"])
            need(all(engine.get(key) == parent["engineIdentity"].get(key) for key in
                     ("pointer", "current_manager", "manager_index", "object_manager")), "engine owner changed")
        else:
            subject, source, world = obs._subject(parent["slot"]), rt.wild_spawn(emu, parent["slot"]), obs._world_context()
        need(obs._chain_identity(subject) == obs._chain_identity(parent["subject"])
             and source == parent["sourceIdentity"] and world == parent["worldContext"],
             "full subject or world owner changed")

    def _attempt_before(self):
        obs, regs = self.observer, self.session.emu.memory.register_arm9
        words = obs._chain_words(7)
        slot = regs.r2 & 0xFFFFFFFF
        if words[6] == 0 or slot >= 7:
            return None
        if obs._subject(slot).get("species") != 143:
            return None
        self._live("owner")
        self._direct("owner", 0x023D687E, "attempt")
        subject, source, engine, world = obs._chain_current(slot)
        need((regs.r0 & 0xFFFFFFFF, regs.r1 & 0xFFFFFFFF) ==
             (world["statePointer"], world["fieldPointer"]), "attempt field/state differs")
        need(words[0] <= 0xFFFF and words[5] == 0 and words[1:3] == words[3:5]
             and all(words[6] >> shift & 255 for shift in (0, 8, 16, 24)), "Slam arguments differ")
        need(self.count < self.MAX_ATTEMPTS, "window attempt cap reached")
        self.count += 1
        value = dict(attemptId=self.count, slot=slot, subject=subject, sourceIdentity=source,
                     engineIdentity=engine, worldContext=world, profilePointer=regs.r3 & 0xFFFFFFFF,
                     allowedTile=words[0], landing=list(map(obs._chain_signed, words[1:3])),
                     finalTarget=list(map(obs._chain_signed, words[3:5])), pendingMarker=words[5],
                     arcPacked=words[6], landings=[])
        self.attempts.append(value)
        return value

    def _attempt_after(self, value, context):
        self._check(value, full=True)
        need(self.attempts[-1] is value and context["returnValue"] in (0, 1), "attempt return differs")
        self.attempts.pop()
        return {**value, "started": bool(context["returnValue"]), "diagnosticOnly": True,
                "acceptedProof": False, "nativeOwners": {key: list(pin[2:]) for key, pin in PINS.items()}}

    def _landing_before(self):
        if not self.attempts:
            return None
        parent = self.attempts[-1]
        self._check(parent)
        self._direct("attempt", 0x023D0FBA, "landing")
        regs = self.session.emu.memory.register_arm9
        words = list(map(self.observer._chain_signed, self.observer._chain_words(4)))
        need([regs.r0 & 0xFFFFFFFF, regs.r1 & 0xFFFFFFFF, regs.r2 & 0xFFFFFFFF] ==
             [parent["worldContext"]["statePointer"], parent["slot"], parent["worldContext"]["fieldPointer"]]
             and regs.r3 & 0xFFFFFFFF == parent["allowedTile"] | 0x4000
             and words == parent["landing"] + parent["finalTarget"], "landing exact arguments differ")
        need(len(parent["landings"]) == 0, "Slam landing count differs")
        value = dict(attemptId=parent["attemptId"], allowedTile=regs.r3 & 0xFFFFFFFF,
                     landing=words[:2], finalTarget=words[2:], occupancy=[])
        parent["landings"].append(value)
        self.landings.append(value)
        return value

    def _landing_after(self, value, context):
        self._check(self.attempts[-1])
        need(self.landings and self.landings[-1] is value and context["returnValue"] < len(MOTION_DECISIONS),
             "landing return/owner differs")
        self.landings.pop()
        value.update(returnValue=context["returnValue"], entry=deepcopy(context["entry"]), returned=deepcopy(context["returned"]),
                     decision=context["returnValue"], decisionName=MOTION_DECISIONS[context["returnValue"]])
        return None

    def _query_caller(self, parent):
        query = getattr(self.observer, "query", None)
        owner = getattr(query, "loaded", None)
        need(query is not None and query.active and isinstance(owner, dict), "no authenticated loaded Query owner")
        world = parent["worldContext"]
        need((owner["field"], owner["fieldEpoch"], owner["mapGeneration"]) ==
             (world["fieldPointer"], world["fieldEpoch"], world["mapGeneration"])
             and self.session.read(query.state, 28) == bytes.fromhex(owner["rawHex"]), "loaded Query owner changed")
        offset, size, sha = QUERY_OCCUPANCY
        need(hashlib.sha256(query.image[offset:offset + size]).hexdigest() == sha, "Query Occupancy typed body differs")
        need(owner["entry"] % 4 == 0 and 0x02000000 <= owner["entry"] <= 0x02400000 - len(owner["expected"]),
             "loaded Query image outside RAM")
        base = owner["entry"] + offset
        expected = owner["expected"][offset:offset + size]
        need(len(expected) == size and self.session.read(base, size) == expected, "relocated Query Occupancy body differs")
        regs = self.session.emu.memory.register_arm9
        returned = regs.lr & ~1
        need(base + 2 <= returned <= base + size, "occupancy caller outside Query owner")
        need(returned == base + QUERY_OCCUPANCY_CALL + 2, "occupancy caller site differs")
        instruction = struct.unpack_from("<H", expected, returned - 2 - base)[0]
        register = instruction >> 3 & 15
        need(instruction & 0xFF87 == 0x4780 and register <= 12
             and getattr(regs, "r" + str(register)) & ~1 == PINS["occupancy"][2], "occupancy BLX target differs")
        return dict(imageEntry=owner["entry"], caller=returned - 2, ownerRawHex=owner["rawHex"])

    def _object(self, pointer):
        need(pointer % 4 == 0 and 0x02000000 <= pointer <= 0x02400000 - 0x128, "object pointer outside RAM")
        return dict(pointer=pointer, pose=self.session.rt.object_state(self.session.emu, pointer))

    def _occupancy_before(self):
        if not self.landings:
            return None
        parent, landing = self.attempts[-1], self.landings[-1]
        self._check(parent)
        caller = self._query_caller(parent)
        rt, emu, regs = self.session.rt, self.session.emu, self.session.emu.memory.register_arm9
        words = self.observer._chain_words(3)
        need(regs.r0 & 0xFFFFFFFF == parent["worldContext"]["fieldPointer"]
             and [self.observer._chain_signed(regs.r3), self.observer._chain_signed(words[0])] == landing["landing"]
             and words[2] in range(4) and len(landing["occupancy"]) < 4, "occupancy arguments/count differ")
        value = dict(fieldPointer=regs.r0 & 0xFFFFFFFF, ignoredObject=regs.r1 & 0xFFFFFFFF,
                     collisionIgnoredObject=regs.r2 & 0xFFFFFFFF, x=self.observer._chain_signed(regs.r3),
                     y=self.observer._chain_signed(words[0]), targetBaseY=self.observer._chain_signed(words[1]),
                     mode=words[2], queryCaller=caller, player=self._object(rt.player_ptr(emu)))
        actor, source = rt.actor_state(emu, 7), rt.wild_spawn(emu, 7)
        value["followerSlot"] = dict(actor=actor, source=source)
        if actor.get("active") is True and source.get("object"):
            value["followerSlot"].update(engineIdentity=rt.live_wild_object_identity(emu, 7),
                                          object=self._object(source["object"]))
        landing["occupancy"].append(value)
        return value

    def _occupancy_after(self, value, context):
        self._check(self.attempts[-1])
        need(context["returnValue"] in (0, 1), "occupancy BOOL return differs")
        value.update(returnValue=context["returnValue"], entry=deepcopy(context["entry"]), returned=deepcopy(context["returned"]),
                     occupied=bool(context["returnValue"]))
        return None

    def _tap(self, key, before, after):
        address = PINS[key][2]
        def entered():
            if not self.active or not getattr(self.session, "_throw_interactions_window", False):
                return
            if self.observer._live_code(address, self.code[key][:32]) != self.code[key][:32]:
                return  # A different overlay may occupy this address.
            value = before()
            if value is None:
                return
            self._live(key)
            need(len(self.contexts) < 4, "nested callback cap reached")
            regs = self.session.emu.memory.register_arm9
            context = dict(entry=self.observer._clock(), setupMode="prepared" if self.session.prepared else "normal",
                           sp=regs.sp & 0xFFFFFFFF, data=value)
            self.contexts.append(context)
            token = None
            def returned():
                if regs.sp & 0xFFFFFFFF != context["sp"]:
                    return
                self.observer.hooks.remove(token)
                self.returns.remove(token)
                self.observer.return_tokens.remove(token)
                self.contexts.remove(context)
                self._live(key)
                context.update(returned=self.observer._clock(), returnValue=regs.r0 & 0xFFFFFFFF)
                result = after(value, context)
                if result is not None:
                    self.observer._queue("slam-admission", context, result)
            token = self.observer.hooks.add(regs.lr, returned)
            self.returns.append(token)
            self.observer.return_tokens.append(token)
        token = self.observer.hooks.add(address, entered)
        self.tokens.append(token)
        self.observer.tokens.append(token)

    def close(self):
        self.active = False
        for own, shared in ((self.tokens, self.observer.tokens), (self.returns, self.observer.return_tokens)):
            for token in own:
                self.observer.hooks.remove(token)
                if token in shared:
                    shared.remove(token)
            own.clear()
        self.contexts.clear()
        self.attempts.clear()
        self.landings.clear()
