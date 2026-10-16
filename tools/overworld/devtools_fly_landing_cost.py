"""Map67 Hoothoot Fly In around retained queue3532; passive guest-call costs only.

No guest call, write, input, extra frame, changed recipe or acceptance verdict.
The existing NativeObservation tap owns return matching, guest clocks and flush.
"""
from copy import deepcopy
import hashlib
import struct
from tools.overworld.devtools_observer import NativeObservationError, public_bytes
from tools.overworld.devtools_runtime import _elf_function_extent, actor_identity_checks
from tools.overworld.devtools_emote_vram_diagnostics import decode_emote_owner
from tools.overworld.devtools_resolver_parity import packaged_query_identity, current_query_owner
from tools.overworld.devtools_query_observer import relocated_image

PINS = {
    "frame": ("overworld_wild_spawns_overlay_linked.o", "OverworldWildSpawns_FrameMovementTask", 0x023D7890, 1296, "fc3bca5b9cd7d809ee7a6c12de51fcba565bd91e95a54fc160f34acd7391606e"),
    "height": ("overworld_wild_spawns_overlay_linked.o", "OverworldWildSpawns_ResolveObjectLandingHeight", 0x023CEDDC, 48, "07b5e87dd59897bf611c604faf04eede4b50dc8c8f937ccc923edb3e4496dd60"),
    "finish": ("overworld_wild_spawns_overlay_linked.o", "OverworldWildSpawns_HandleFinishedMovementCommand", 0x023D2E06, 930, "c7682486010ecc943701331fef031d05ccddc7595a3372f532f10c52343374fa"),
    "resolver": ("overworld_actor_system_overlay_linked.o", "BehaviorResolver_Resolve", 0x023B84A8, 84, "be15a7659f1ec76cedb1b0ecc686ae00a408511c9b9e2522cf48865c9c6819f9"),
    "admit": ("overworld_actor_system_overlay_linked.o", "OverworldEmoteSlots_Admit", 0x023B9110, 272, "d1210539d613061cbee646211a77522a3a00605f346cef68ae90575cd1c1ee8d"),
    "prepare": ("overworld_actor_system_overlay_linked.o", "OverworldEmoteSlots_Prepare", 0x023BA01C, 128, "f1950ff831f0571f620d85623b2412a394d682732f5b349d6f8f8760ad287763"),
    "initialize": ("overworld_actor_system_overlay_linked.o", "OverworldEmoteSlots_Initialize", 0x02203B28, 316, "5529dd0bea1f91d2694c3fa340466cedffc78f186db49b1ea29db55e32e4b921"),
    "condition": ("overworld_actor_system_overlay_linked.o", "OverworldBehaviorConditionAdapter_EvaluateActor", 0x023B65C0, 880, "11cfb506614679d6aee37fbea2fcdefe71fc7a3c1d8713dd328b1a9aac2f1c64"),
}
QUERY_NATIVE = (37116, 1580, 'b917228445052ec3fe2b26f7befd00f2aaada86e3ff4e436d1d7c4bf3d9c712b')
FRAME_WORLD, WORLD_BYTES, RUNTIME_CONDITIONS = 0x6BC, 248, 0x514


def need(ok, reason):
    if not ok:
        raise NativeObservationError("Fly In cost: " + reason)


class FlyLandingCost:
    MAX_WINDOWS = 8
    MAX_CHILDREN = 32
    FIRST_QUEUE = 3516
    LAST_QUEUE = 3548

    def __init__(self, observer):
        self.observer, self.session = observer, observer.session
        self.frame, self.bubbles, self.code = None, [], {}
        self.windows = 0
        self.conditions, self.native_pending = [], []
        self.native_target = None
        self.query_identity, self.query_blob, self.query_receipt = packaged_query_identity(
            self.session.rt.REPO, self.session.rom)
        self.query_image = self.query_blob[64:64 + self.query_receipt["imageBytes"]]
        self.query_loaded = None
        for key, (file, name, address, size, sha) in PINS.items():
            path = self.session.rt.REPO / "build" / file
            need(_elf_function_extent(path, name) == (address, size), key + " typed extent differs")
            code = observer.elf_code(path, address, size)
            need(hashlib.sha256(code).hexdigest() == sha, key + " full linked body differs")
            # The Wild overlay is not loaded at title-screen setup. Seal the
            # whole packaged body now and authenticate its live body only when
            # the exact selected native call is reached.
            need(any(base <= address and address + size <= base + len(data)
                     and data[address-base:address-base+size] == code
                     for base, data in self.session.code_regions), key + " ROM body differs")
            self.code[key] = code
        for key, pin in PINS.items():
            observer._tap("fly-landing-cost-" + key, pin[2], self.code[key][:32],
                lambda key=key: self.before(key),
                lambda value, context, key=key: self.after(key, value, context),
                scope=lambda key=key: self.windows < self.MAX_WINDOWS if key == "frame" else self.frame is not None,
                resident=key != "frame", timed=True)
        path = self.session.rt.REPO / "build/overworld_query_code_addon/image.elf"
        offset, size, sha = QUERY_NATIVE
        need(_elf_function_extent(path, "OverworldConditionNative_Run") == (0x02080000 + offset, size),
             "condition Native_Run typed extent differs")
        self.native_code = observer.elf_code(path, 0x02080000 + offset, size)
        need(hashlib.sha256(self.native_code).hexdigest() == sha, "condition Native_Run linked body differs")

    def native_owner(self):
        owner = self.query_loaded
        need(isinstance(owner, dict) and self.frame is not None,
             "condition has no authenticated loaded Query")
        world = self.frame["owner"]["world"]
        need((struct.unpack_from("<I", bytes.fromhex(owner["rawHex"]), 12)[0],
              owner["fieldEpoch"], owner["mapGeneration"]) ==
             (world["fieldPointer"], world["fieldEpoch"], world["mapGeneration"])
             and self.session.read(owner["stateAddress"], 28) == bytes.fromhex(owner["rawHex"]),
             "condition loaded Query owner changed")
        offset, size, sha = QUERY_NATIVE
        need(self.query_image[offset:offset + size] == self.native_code
             and hashlib.sha256(self.query_image[offset:offset + size]).hexdigest() == sha
             and struct.unpack_from("<IHH", self.query_image) == (0x51444F57, 9, 196)
             and struct.unpack_from("<I", self.query_image, 152)[0] == (0x02080000 + offset | 1),
             "condition packaged Native_Run or descriptor differs")
        expected = self.query_expected[offset:offset + size]
        address = owner["entry"] + offset
        need(len(expected) == size and owner["entry"] % 4 == 0
             and 0x02000000 <= owner["entry"] <= 0x02400000 - len(self.query_expected)
             and self.session.read(address, size) == expected
             and self.session.read(owner["entry"], 196) == self.query_expected[:196]
             and self.session.read(owner["entry"] + 152, 4) == struct.pack("<I", address | 1),
             "condition live relocated Native_Run differs")
        return address, owner["rawHex"]

    def install_native(self):
        address, owner = self.native_owner()
        if self.native_target is not None:
            need(self.native_target == (address, owner), "condition Query hook owner changed")
            return
        self.native_target = (address, owner)
        o = self.observer
        def entered():
            if self.frame is None or not self.conditions:
                return
            need(len(o.contexts) < o.MAX_DEPTH, "condition observation nesting limit reached")
            value = self.native_before()
            r = self.session.emu.memory.register_arm9
            context = dict(entry=o._clock(), guestEntry=o._guest_clock(), data=value,
                           setupMode="normal", sp=r.sp & 0xFFFFFFFF, depth=len(o.contexts) + 1)
            o.contexts.append(context)
            token = None
            def returned():
                if r.sp & 0xFFFFFFFF != context["sp"]:
                    return
                need(context in o.contexts, "condition return was already consumed")
                need(len(o.contexts) == context["depth"] and o.contexts[-1] is context,
                     "condition return nesting differs")
                o.hooks.remove(token); o.return_tokens.remove(token); o.contexts.remove(context)
                context.update(returned=o._clock(), guestReturn=o._guest_clock(), returnValue=r.r0 & 0xFFFFFFFF)
                o._queue("fly-landing-cost-native-condition", context, self.native_after(value, context))
            token = o.hooks.add(r.lr, returned)
            o.return_tokens.append(token)
        o.tokens.append(o.hooks.add(address, entered))

    def condition_world(self, runtime):
        need(runtime % 4 == 0 and 0x02000000 <= runtime <= 0x02400000 - 3100,
             "condition workspace outside RAM")
        raw = public_bytes(self.session, runtime + FRAME_WORLD, WORLD_BYTES)
        need(raw[247] in range(4), "condition frame mode differs")
        return dict(reservedBinding=raw[247], frame=struct.unpack_from("<I", raw, 12)[0],
                    subjectHandleHex=raw[:12].hex())

    def condition_runtime(self, runtime):
        field, native = struct.unpack("<2I", public_bytes(self.session, self.session.rt.WILD_STATE + 0xE0, 8))
        need(field == self.frame["owner"]["world"]["fieldPointer"] and native % 4 == 0
             and 0x02000000 <= native <= 0x02400000 - 1308
             and struct.unpack("<I", public_bytes(self.session, native + RUNTIME_CONDITIONS, 4))[0] == runtime,
             "condition workspace owner differs")

    def native_before(self):
        address, owner = self.native_owner()
        need(self.native_target == (address, owner) and self.conditions, "condition native caller lost owner")
        parent = self.conditions[-1]
        self.same(parent["conditionOwner"])
        r = self.session.emu.memory.register_arm9
        raw = public_bytes(self.session, r.r0, 56)
        words = struct.unpack_from("<10I", raw)
        need(struct.unpack_from("<HH", raw, 40) == (2, 56) and raw[46] in (0, 1, 2) and raw[47] == 0
             and words[:5] == parent["packetPrefix"] and raw[44] == parent["conditionOwner"]["slot"],
             "condition native typed packet or subject differs")
        self.condition_runtime(words[0])
        world = self.condition_world(words[0])
        self.frame["children"] += 1
        need(self.frame["children"] <= self.MAX_CHILDREN, "condition child receipt bound exceeded")
        value = dict(windowId=parent["windowId"], owner=parent["owner"], conditionOwner=parent["conditionOwner"],
            parent=parent, callPointer=r.r0, packetHex=raw.hex(), operation=raw[46],
            forcedProfileIndex=struct.unpack_from("<i", raw, 36)[0],
            indexFieldMeaning="allowedTerrainMask" if raw[46] == 2 else "forcedProfileIndex",
            forcedOverrideProfileIndex=parent["forcedProfileIndex"],
            evaluationMode=parent["evaluationMode"], worldBefore=world, queryOwner=owner, nativeAddress=address,
            callerReturn=r.lr, arguments=[r.r0,r.r1,r.r2,r.r3])
        self.native_pending.append(value)
        return value

    def native_after(self, value, context):
        need(self.native_pending and self.native_pending[-1] is value and self.conditions
             and self.conditions[-1] is value["parent"] and self.frame is not None
             and value["windowId"] == self.frame["windowId"], "condition native reused or cross-owner return")
        need(self.native_owner() == (value["nativeAddress"], value["queryOwner"]), "condition native lease changed")
        self.same(value["conditionOwner"])
        self.condition_runtime(value["parent"]["packetPrefix"][0])
        raw = public_bytes(self.session, value["callPointer"], 56)
        old = bytes.fromhex(value["packetHex"])
        need(raw[:40] == old[:40] and raw[40:46] == old[40:46] and raw[47] == 0
             and (raw[46] == old[46] or (old[46], raw[46]) == (1, 0))
             and context["returnValue"] in range(5), "condition native return packet/status differs")
        self.native_pending.pop()
        receipt = {k: deepcopy(v) for k,v in value.items() if k != "parent"}
        receipt.update(worldAfter=self.condition_world(value["parent"]["packetPrefix"][0]), operationAfter=raw[46],
            diagnosticOnly=True, acceptedProof=False, costScope="inclusive guest scheduler ticks; nested spans must not be added")
        return receipt

    def live(self, key):
        need(self.observer._live_code(PINS[key][2], self.code[key]) == self.code[key],
             key + " live full body differs")

    def owner(self, slot):
        o, rt, emu = self.observer, self.session.rt, self.session.emu
        subject, source = o._subject(slot), rt.wild_spawn(emu, slot)
        engine, world = rt.live_wild_object_identity(emu, slot), o._world_context()
        actor = rt.actor_state(emu, slot)
        checks = actor_identity_checks(actor, source, engine, world, slot)
        lookup = engine.get("id_lookup", {})
        need(all(checks.values()) and actor.get("active") is True
             and subject.get("role") in ("WILD", "FOLLOWER")
             and source.get("object") == engine.get("pointer")
             and actor.get("form") == source.get("form")
             and actor.get("level") == source.get("level")
             and lookup.get("status") == "complete" and lookup.get("pointer_matches") is True
             and lookup.get("eligible_count") == 1, "native/public owner differs")
        return dict(slot=slot, subject=subject, source=source, engine=engine, world=world)

    def same(self, owner):
        # Full manager binding was checked once at the outer entry. Child
        # checks keep the exact public handle/source/field, without rescanning.
        o, rt, emu = self.observer, self.session.rt, self.session.emu
        need(o._chain_identity(o._subject(owner["slot"])) == o._chain_identity(owner["subject"])
             and rt.wild_spawn(emu, owner["slot"]) == owner["source"]
             and o._world_context() == owner["world"], "subject or world owner changed")

    def before(self, key):
        o, rt, emu = self.observer, self.session.rt, self.session.emu
        r = emu.memory.register_arm9
        if key == "frame":
            if self.windows >= self.MAX_WINDOWS or self.session.prepared:
                return None
            if not self.FIRST_QUEUE <= self.session.completed_frames <= self.LAST_QUEUE:
                return None
            if o._world_context().get("mapId") != 67:
                return None
            need(self.frame is None and r.r1 == rt.WILD_STATE, "frame state or nesting differs")
            chosen = None
            for slot in range(7):
                a = o._subject(slot)
                # Public subject omits elapsed/duration; read the same public
                # actor layout used by coherent snapshots, not private arrays.
                if a.get("species") != 163 or a.get("role") != "WILD":
                    continue
                a = rt.actor_state(emu, slot)
                if a.get("motionKind") == "FLY_IN" and a.get("motionPhase") in ("MOVING", "COMMIT_PENDING") \
                        and 0 < a.get("motionDuration", 0) and 0 <= a["motionDuration"] - a["motionElapsed"] <= 1:
                    chosen = self.owner(slot)
                    chosen["motionBefore"] = {k: a[k] for k in ("motionKind", "motionPhase", "motionElapsed", "motionDuration", "origin", "target")}
                    break
            if chosen is None:
                return None
            self.windows += 1
            value = dict(windowId=self.windows, owner=chosen, children=0)
            self.frame = value
            # The Throw query collector is optional and scoped to its recording
            # window. Authenticate this diagnostic's lease with the existing
            # full package/Field loader check, without enabling that collector.
            self.query_loaded = current_query_owner(self.session, self.query_blob, self.query_receipt)
            self.query_expected = relocated_image(self.query_image, self.query_receipt, self.query_loaded["entry"])
            self.install_native()
        else:
            if self.frame is None:
                return None
            value = dict(windowId=self.frame["windowId"], owner=self.frame["owner"])
            self.same(value["owner"])
            if key == "condition":
                args = struct.unpack("<11I", public_bytes(self.session, r.sp, 44))
                forced = struct.unpack("<i", struct.pack("<I", args[5]))[0]
                need(r.r1 == rt.WILD_STATE and r.r2 == value["owner"]["world"]["fieldPointer"]
                     and args[1] < 8 and args[2] <= 255 and forced in (-3,-2,-1,16),
                     "condition adapter arguments differ")
                value.update(conditionOwner=self.owner(args[1]), packetPrefix=(r.r0,r.r1,r.r2,r.r3,args[0]),
                    forcedProfileIndex=forced, evaluationMode="Warm" if forced == -2 else "Moving" if forced == -3 else "Normal")
                self.condition_runtime(r.r0)
                value["worldBefore"] = self.condition_world(r.r0)
                self.conditions.append(value)
            elif key == "height":
                if r.r1 != value["owner"]["source"]["object"]:
                    return None
                need(r.r0 == value["owner"]["world"]["fieldPointer"], "height field differs")
                value["tile"] = [r.r2, r.r3]
            elif key == "finish":
                if r.r1 != value["owner"]["slot"]:
                    return None
                need(r.r0 == rt.WILD_STATE, "finish state differs")
            elif key == "resolver":
                value["requestHex"] = public_bytes(self.session, r.r2, 44).hex()
            elif key == "admit":
                # Retain the actual bubble actor. It can be another Wild or
                # the Follower in this frame; it is never assumed to be the bird.
                effect_owner = None
                for slot in range(8):
                    source = rt.wild_spawn(emu, slot)
                    if source.get("active") and source.get("object") == r.r1:
                        effect_owner = self.owner(slot)
                        break
                if effect_owner is None:
                    return None
                value["effectOwner"] = effect_owner
                need(0 <= r.r2 < 14, "bubble type differs")
                value.update(context=r.r0, object=r.r1, emote=r.r2, slotPointer=None, bubbleOwner=None)
                self.bubbles.append(value)
            else:
                if not self.bubbles:
                    return None
                bubble = self.bubbles[-1]
                value["bubble"] = bubble
                if key == "prepare":
                    need((r.r1, r.r2) == (bubble["context"], bubble["emote"]), "Prepare context/type differs")
                    words = struct.unpack("<10I", public_bytes(self.session, r.r0, 40))
                    owned = decode_emote_owner(words[0], bubble["context"], public_bytes(self.session, words[0], 148))
                    need(r.r0 in (words[0]+28, words[0]+68, words[0]+108)
                         and words[1] == bubble["object"] and words[9] == 1,
                         "Prepare slot binding differs")
                    value["slotPointer"] = bubble["slotPointer"] = r.r0
                    bubble["bubbleOwner"] = words[0]
                    value["ownerSlotCount"] = owned["activeCount"]
                elif key == "initialize":
                    need(bubble["slotPointer"] is not None, "Initialize lacks prepared slot")
                    value.update(effect=r.r0, dataPointer=r.r1)
            self.frame["children"] += 1
            need(self.frame["children"] <= self.MAX_CHILDREN, "child receipt bound exceeded")
        self.live(key)
        value["arguments"] = [r.r0, r.r1, r.r2, r.r3]
        value["callerReturn"] = r.lr
        return value

    def after(self, key, value, context):
        need(self.frame is not None and value["windowId"] == self.frame["windowId"], "lost frame owner")
        self.live(key)
        self.same(value["owner"])
        if key == "condition":
            need(self.conditions and self.conditions[-1] is value and not self.native_pending,
                 "condition adapter reused or nested return")
            self.same(value["conditionOwner"])
            self.condition_runtime(value["packetPrefix"][0])
            need(context["returnValue"] in range(5), "condition adapter return status differs")
            self.conditions.pop()
        if key in ("admit", "prepare", "initialize"):
            self.same((value if key == "admit" else value["bubble"])["effectOwner"])
        receipt = {k: deepcopy(v) for k, v in value.items() if k != "bubble"}
        receipt.update(diagnosticOnly=True, acceptedProof=False,
                       costScope="inclusive guest scheduler ticks; nested spans must not be added")
        if key == "condition":
            receipt["worldAfter"] = self.condition_world(value["packetPrefix"][0])
        if key == "initialize" and context["returnValue"]:
            raw = public_bytes(self.session, value["dataPointer"]+44, 20)
            slot, field, owner, object, model = struct.unpack("<5I", raw)
            bubble = value["bubble"]
            need((slot, field, owner, object) == (bubble["slotPointer"], bubble["context"],
                 bubble["bubbleOwner"], bubble["object"]) and model != 0,
                 "Initialize result binding differs")
            receipt["bindingHex"] = raw.hex()
        if key == "admit":
            need(self.bubbles and self.bubbles[-1] is value, "bubble return nesting differs")
            self.bubbles.pop()
        if key == "frame":
            need(self.frame is value and not self.bubbles and not self.conditions and not self.native_pending,
                 "frame has a pending child return")
            a = self.session.rt.actor_state(self.session.emu, value["owner"]["slot"])
            receipt["motionAfter"] = {k:a[k] for k in ("motionKind", "motionPhase", "motionElapsed", "motionDuration")}
            self.frame = None
        return receipt
