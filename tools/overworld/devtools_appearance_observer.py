"""Opt-in, read-only receipts from the real Pokémon palette owner and SDK.

No guest call, write, input, timer or profile evaluation lives here. The existing
record.start window owns the hooks; ordinary recordings pay no palette cost.
"""
from copy import deepcopy
import hashlib
import struct

from tools.overworld.devtools_field_cleanup import symbol
from tools.overworld.devtools_observer import public_bytes
from tools.overworld.devtools_runtime import actor_identity_checks
from tools.overworld.devtools_application_bank import (
    decode_application_bank, local_application,
)

BASE, END = 0x022074A8, 0x022089CC
ENTRY = struct.pack("<IHH", 0x5041574F, 2, 28)
HANDLE_KEYS = ("slot", "generation", "fieldEpoch", "mapGeneration", "encounterGeneration")
GEN_KEYS = ("authorityGeneration", "engineAnchorGeneration", "presentationGeneration")
POINTER_KEYS = ("actorPointer", "objectPointer", "drawPointer", "modelPointer",
                "texturePointer", "originalPalettePointer", "tintedPalettePointer")


def need(ok, reason):
    if not ok:
        raise ValueError("appearance reader: " + reason)


def decode_view(raw):
    need(isinstance(raw, bytes) and len(raw) == 88, "snapshot size differs")
    h = struct.unpack_from("<6H", raw)
    need(h[5] == 0 and h[0] < 10 and all(h[1:5]), "full handle differs")
    handle = dict(zip(HANDLE_KEYS, h[:5]))
    handle["value"] = h[0] | h[1] << 16
    names = ("subjectIdentity", *GEN_KEYS, *POINTER_KEYS,
             "originalPaletteKey", "privatePaletteKey", "appliedMaterials",
             "lastOriginalBase", "lastTintedBase")
    view = dict(zip(names, struct.unpack_from("<16I", raw, 12)))
    view.update(handle=handle, paletteBytes=struct.unpack_from("<H", raw, 76)[0],
                species=struct.unpack_from("<H", raw, 78)[0],
                **dict(zip(("form", "level", "roleId", "mode", "strength", "yielded"), raw[80:86])))
    need(raw[86:] == b"\0\0" and view["roleId"] in (1, 2, 3)
         and view["mode"] in (0, 1, 2) and 0 <= view["strength"] <= 16
         and view["yielded"] in (0, 1)
         and 32 <= view["paletteBytes"] <= 512 and view["paletteBytes"] % 32 == 0,
         "snapshot values differ")
    return view


def decode_conditions(read, pointer, actor, blob, frame, enabled, bank=None):
    unavailable = dict(available=False, frame=frame, enabledMask=enabled, states=[],
                       preparedPointer=pointer, rawHex="", statesHex="")
    if pointer == 0:
        return dict(unavailable, reason="no-prepared-owner")
    current = struct.unpack_from("<H", blob, 4)[0] == 95
    if current:
        need(bank is not None, "current bank provenance is missing")
    raw = read(pointer, 88 if current else 52)
    h = struct.unpack_from("<6H", raw)
    count, valid, capacity = struct.unpack_from("<BBH", raw, 80 if current else 48)
    if valid == 0:
        return dict(unavailable, rawHex=raw.hex(), reason="prepared-not-ready")
    need(valid == 1 and 0 <= count <= capacity <= 32, "prepared count differs")
    if h[5] != 0 or dict(zip(HANDLE_KEYS, h[:5])) != {k: actor["handle"][k] for k in HANDLE_KEYS}:
        return dict(unavailable, rawHex=raw.hex(), reason="prepared-owner-mismatch")
    if current:
        subject_damage_pending = struct.unpack_from("<H", raw, 86)[0]
        need(struct.unpack_from("<H", raw, 84)[0] == actor["species"]
             and subject_damage_pending in (0, 1), "prepared subject species differs")
    offset, entries, stride = struct.unpack_from("<IHH", blob, 52)
    need(stride == 48 and offset + entries * stride <= struct.unpack_from("<I", blob, 60)[0],
         "catalog condition directory differs")
    state_pointer = struct.unpack_from("<I", raw, 12)[0]
    if count == 0 or state_pointer == 0:
        return dict(unavailable, rawHex=raw.hex(), reason="no-condition-states")
    states = read(state_pointer, count * 16)
    result = []
    for i in range(count):
        source = struct.unpack_from("<H", raw, 16 + i * 2)[0] if current else raw[16 + i]
        need(source < entries, "prepared catalog index differs")
        entry = blob[offset + source * stride:offset + (source + 1) * stride]
        application = bank["conditionOwners"][source] if current else entry[34]
        application_local = local_application(bank, actor["species"], application) if current else application
        active, cooldown, target, generation, encounter, kind, flags = struct.unpack_from("<II3H2B", states, i * 16)
        need(application_local < 32 and flags & ~127 == 0, "condition state values differ")
        result.append(dict(catalogIndex=source, application=application,
            applicationLocal=application_local,
            conditionId=struct.unpack_from("<H", entry, 32)[0], activationMode=entry[38],
            durationFrames=struct.unpack_from("<H", entry, 20)[0],
            cooldownFrames=struct.unpack_from("<H", entry, 22)[0],
            activeUntil=active, cooldownUntil=cooldown, targetSlot=target,
            targetGeneration=generation, targetEncounterGeneration=encounter,
            targetKind=kind, flags=flags, enabled=bool(enabled & (1 << application_local))))
    return dict(available=True, frame=frame, enabledMask=enabled, states=result,
                preparedPointer=pointer, rawHex=raw.hex(), statesHex=states.hex())


class NativeAppearanceObserver:
    def __init__(self, observer):
        self.observer, self.session = observer, observer.session
        self.active = True
        self.refresh = []
        self.vblank = []
        self.conditions, self.uploads, self.materials, self.clears = {}, {}, {}, {}
        self.upload_count = 0
        self.subject = None
        self.pending_upload = None
        self.material_keys = set()
        self.tokens, self.returns = [], []
        s, rt = self.session, self.session.rt
        self.path = rt.REPO / "build/overworld_field_capsule_linked.o"
        image = self.path.read_bytes()
        self.elf_hash = hashlib.sha256(image).hexdigest()
        self.symbols = rt.linked_symbols(self.path)
        self.head, _, _ = symbol(image, "sAppearance", 1, expected_size=4)
        need(BASE <= self.head <= END - 4, "record head is outside its native owner")
        self.entry = observer.elf_code(self.path, BASE, 28)
        need(self.entry[:8] == ENTRY, "entry ABI differs")
        self.blob = (rt.REPO / "build/OverworldWildBehaviorData.bin").read_bytes()
        need(len(self.blob) >= 88 and struct.unpack_from("<H", self.blob, 4)[0] in (86, 87, 88, 89, 95)
             and struct.unpack_from("<HI", self.blob, 6) == (84, len(self.blob)), "catalog ABI differs")
        template_offset, template_count, template_size = struct.unpack_from("<IHH", self.blob, 76)
        rest_offset = (template_offset + template_count * template_size + 3) & ~3
        condition_count = struct.unpack_from("<H", self.blob, 56)[0]
        options_bytes = max(condition_count, 1) * 12 if struct.unpack_from("<H", self.blob, 4)[0] in (87, 88, 89) else 0
        current = struct.unpack_from("<H", self.blob, 4)[0] == 95
        self.bank = decode_application_bank(self.blob, rt.REPO) if current else None
        need(current or rest_offset + 4 + options_bytes == len(self.blob),
             "catalog appended tint/options layout differs")
        self.blob_hash = hashlib.sha256(self.blob).hexdigest()
        self.enabled = 0xFFFFFFFF if current else struct.unpack_from("<I", self.blob, rest_offset)[0]
        for name, before, after in (("OverworldActorAppearance_RefreshNative", self._refresh_before, self._refresh_after),
                                    ("Appearance_ApplyMaterial", self._material_before, self._material_after)):
            self._tap(name, self.symbols[name], observer.elf_code(self.path, self.symbols[name] & ~1, 32), before, after)
        for name, address, before, after in (("appearance-sdk-upload", 0x020D0B08, self._upload_before, self._upload_after),
                                            ("appearance-sdk-upload-complete", 0x020D0B74, self._end_before, self._end_after),
                                            ("appearance-field-vblank", 0x021E5900, self._vblank_before, self._vblank_after),
                                            ("appearance-native-heal", 0x0206EC40, self._heal_before, self._heal_after)):
            self._tap(name, address, s.packaged_code(address, 32), before, after)

    def select_subject(self, subject):
        from tools.overworld.devtools_records import select_current_actor
        need(self.active and not self.refresh and self.pending_upload is None
             and self.upload_count == 0, "palette owner selection is not a cold completed boundary")
        selected = select_current_actor(self.session.snapshot(diagnostic_details=False), subject)
        need(selected["role"] in ("WILD", "FOLLOWER", "MOUNTED"),
             "palette selection lacks a supported current role")
        need(self.subject is None or self.subject == selected, "palette owner selection changed")
        self.subject = deepcopy(selected)

    def _selected(self, view):
        subject = getattr(self, "subject", None)
        return subject is None or (view["handle"] == subject["handle"]
            and all(view[k] == subject[k] for k in ("subjectIdentity", "species", *GEN_KEYS))
            and view["roleId"] == {"WILD": 1, "FOLLOWER": 2, "MOUNTED": 3}[subject["role"]])

    def _tap(self, name, address, expected, before, after):
        start = len(self.observer.tokens)
        self.observer._tap(name, address, expected, before, after, scope=lambda: self.active)
        self.tokens.extend(self.observer.tokens[start:])

    def _owner(self, slot):
        s, rt = self.session, self.session.rt
        actor = rt.actor_state(s.emu, slot)
        need(actor.get("active") is True and actor.get("presentationAttached"), "actor is not presented")
        state = rt.ACTOR_DESCRIPTOR["state"]
        context = dict(mapId=rt.field_map_id(s.emu),
            fieldEpoch=rt.unsigned(s.emu, state["address"] + state["offsets"]["fieldEpoch"], 2),
            mapGeneration=rt.unsigned(s.emu, state["address"] + state["offsets"]["mapGeneration"], 2))
        spawn = rt.wild_spawn(s.emu, slot)
        engine = rt.live_wild_object_identity(s.emu, slot)
        need(all(actor_identity_checks(actor, spawn, engine, context, slot).values()), "current engine identity differs")
        pointer = state["address"] + state["offsets"]["actors"] + slot * state["actorStride"]
        return dict(actor=actor, actorPointer=pointer, objectPointer=engine["pointer"],
                    fieldPointer=s.field_pointer(), context=context)

    def _records(self):
        s = self.session
        # This is the SDK-tracked Field parent, not a resident Actor overlay.
        s._authenticate_field_reader_code(0x02007124, 36)
        table = struct.unpack("<I", s.read(0x0200713C, 4))[0]
        slots = struct.unpack("<16I", s.read(table, 64))
        if not any(slots[i] == 1 and slots[i + 1] == 1 for i in range(0, 16, 2)):
            return []
        need(s.packaged_code(BASE, 28) == self.entry and s.read(BASE, 28) == self.entry,
             "live Field appearance entry differs")
        pointer = struct.unpack("<I", s.read(self.head, 4))[0]
        records, seen = [], set()
        while pointer:
            need(pointer % 4 == 0 and pointer not in seen and len(seen) < 10, "record list is invalid")
            seen.add(pointer)
            raw = s.read(pointer, 124)
            view = decode_view(raw[:88])
            need(raw[122] in (0, 1) and raw[123] == 0, "private upload state differs")
            view["uploadPending"] = bool(raw[122])
            if view["mode"] == 0 and view["strength"] == 0 and view["uploadPending"]:
                # The stock queue retains its source until VBlank. This record
                # has no material permission and may already have lost its actor.
                pointer = struct.unpack_from("<I", raw, 88)[0]
                continue
            if not self._selected(view):
                pointer = struct.unpack_from("<I", raw, 88)[0]
                continue
            owner = self._owner(view["handle"]["slot"])
            actor = owner["actor"]
            need(view["handle"] == actor["handle"]
                 and all(view[k] == actor[k] for k in ("subjectIdentity", *GEN_KEYS, "species", "form", "level"))
                 and view["roleId"] == actor["roleId"]
                 and view["actorPointer"] == owner["actorPointer"]
                 and view["objectPointer"] == owner["objectPointer"], "record identity is stale")
            draw = s.read(view["drawPointer"], 0xC4)
            need(self._draw(owner)["drawPointer"] == view["drawPointer"], "record draw is not the current Pokémon draw")
            need(struct.unpack_from("<II", draw, 0x88) == (view["modelPointer"], view["texturePointer"])
                 and struct.unpack_from("<I", draw, 0x9C)[0] == view["originalPaletteKey"],
                 "draw resources differ")
            view.update(recordPointer=pointer, role=actor["role"], owner=owner,
                drawCallback=struct.unpack_from("<I", draw, 0x50)[0],
                drawCommand=draw[0x54], drawTiming=draw[0x55],
                originalHex=s.read(view["originalPalettePointer"], view["paletteBytes"]).hex(),
                tintedHex=s.read(view["tintedPalettePointer"], view["paletteBytes"]).hex())
            records.append(view)
            pointer = struct.unpack_from("<I", raw, 88)[0]
        return records

    def _draw(self, owner):
        s = self.session
        raw = s.read(owner["objectPointer"], 0x110)
        callback = struct.unpack_from("<I", raw, 0xC8)[0]
        need(callback in (0x021F7895, 0x021F88F1), "Pokémon has an unsupported native draw owner")
        pointer = struct.unpack_from("<I", raw, 0x108 + (0 if callback == 0x021F7895 else 4))[0]
        draw = s.read(pointer, 0xC4)
        model, texture = struct.unpack_from("<II", draw, 0x88)
        tex = s.read(texture, 0x3C)
        need(struct.unpack_from("<I", tex)[0] == 0x30584554, "current draw texture differs")
        palette_bytes = struct.unpack_from("<H", tex, 0x30)[0] << 3
        offset = struct.unpack_from("<I", tex, 0x38)[0]
        size = struct.unpack_from("<I", tex, 4)[0]
        need(32 <= palette_bytes <= 512 and palette_bytes % 32 == 0
             and 0x3C <= offset <= size - palette_bytes, "current native palette source differs")
        return dict(owner=owner, drawPointer=pointer, modelPointer=model, texturePointer=texture,
            drawCallback=struct.unpack_from("<I", draw, 0x50)[0], drawCommand=draw[0x54], drawTiming=draw[0x55],
            originalPaletteKey=struct.unpack_from("<I", draw, 0x9C)[0],
            paletteBytes=palette_bytes, paletteSourcePointer=texture + offset,
            paletteHex=s.read(texture + offset, palette_bytes).hex())

    def _refresh_before(self):
        regs = self.session.emu.memory.register_arm9
        data = public_bytes(self.session, regs.r0 & 0xFFFFFFFF, 24)
        actor_ptr, state, prepared, blob, enabled, frame = struct.unpack("<6I", data)
        actor_raw = public_bytes(self.session, actor_ptr, 88)
        from tools.overworld.actor_probe import decode_actor_state
        actor = decode_actor_state(actor_raw, self.session.rt.ACTOR_DESCRIPTOR)
        if not actor.get("active") or not actor.get("presentationAttached") or actor.get("roleId") not in (1,2,3):
            return None
        if not self._selected(actor):
            return None
        owner = self._owner(actor["handle"]["slot"])
        need(actor_ptr == owner["actorPointer"] and actor["handle"] == owner["actor"]["handle"], "refresh borrowed a nonresident actor")
        need(self.session.read(blob, len(self.blob)) == self.blob and enabled == self.enabled,
             "refresh catalog or enabled mask differs from package")
        conditions = decode_conditions(self.session.read, prepared, actor, self.blob, frame, enabled, self.bank)
        conditions["owner"] = deepcopy(owner)
        value = dict(owner=owner, inputHex=data.hex(), conditions=conditions)
        self.refresh.append(value)
        return value

    def _refresh_after(self, value, context):
        need(self.refresh and self.refresh.pop() is value, "refresh return order differs")
        slot = value["owner"]["actor"]["handle"]["slot"]
        after = self._owner(slot)
        need(all(after[k] == value["owner"][k] for k in ("actorPointer", "objectPointer", "fieldPointer", "context"))
             and all(after["actor"][k] == value["owner"]["actor"][k] for k in ("handle", "subjectIdentity", *GEN_KEYS)),
             "refresh changed actor lifetime")
        self.conditions[slot] = deepcopy(value["conditions"])
        for cache in (self.uploads, self.materials):
            if slot in cache and cache[slot]["view"]["handle"] != after["actor"]["handle"]:
                cache.pop(slot)
        if context["returnValue"] == 0:
            current = self._draw(after)
            remaining = [r for r in self._records() if r["handle"]["slot"] == slot]
            if current["drawCallback"] == (self.symbols["Appearance_ApplyMaterial"] | 1):
                # CLEAR may defer freeing a queued source for this one frame.
                # Only the later detached draw can count as full-HP clear proof.
                need(not remaining, "CLEAR still permits a tinted record")
                return None
            need(not remaining,
                 "CLEAR still owns a tinted draw or record")
            self.clears[slot] = dict(frame=value["conditions"]["frame"], draw=current)
        else:
            self.clears.pop(slot, None)
        return None

    def _upload_before(self):
        if not self.refresh and not self.vblank:
            return None
        regs = self.session.emu.memory.register_arm9
        source, destination, size = (getattr(regs, k) & 0xFFFFFFFF for k in ("r0", "r1", "r2"))
        records = [r for r in self._records() if r["tintedPalettePointer"] == source]
        if not records and not self.refresh:
            return None # The stock queue also owns unrelated native uploads.
        need(len(records) == 1, "SDK upload lacks one current tint owner")
        view = records[0]
        need(size == view["paletteBytes"] and destination == (view["privatePaletteKey"] & 0xFFFF) << 3,
             "SDK upload arguments differ")
        base = struct.unpack("<I", self.session.read(0x021E1600, 4))[0]
        need(0x06800000 <= base <= 0x068A0000 and base % 0x1000 == 0, "SDK palette bank destination differs")
        return dict(view=view, sourcePointer=source, destinationOffset=destination,
                    destinationAddress=base + destination, paletteBytes=size,
                    dispatch="field-vblank" if self.vblank else "actor-refresh",
                    callback=deepcopy(self.vblank[-1]) if self.vblank else None,
                    uploadedHex=self.session.read(source, size).hex(), completed=False)

    def _upload_after(self, value, context):
        need(self.pending_upload is None, "palette upload overlapped")
        self.pending_upload = value
        return None

    def _end_before(self):
        return self.pending_upload

    def _end_after(self, value, context):
        need(value is self.pending_upload, "SDK completion lost its upload")
        self.pending_upload = None
        self.upload_count += 1
        need(self.upload_count <= 128, "palette upload budget exceeded")
        value.update(completed=True, uploadId=self.upload_count)
        slot = value["view"]["handle"]["slot"]
        self.uploads[slot] = deepcopy(value)
        return value

    def _vblank_before(self):
        regs = self.session.emu.memory.register_arm9
        value = dict(fieldPointer=regs.r0 & 0xFFFFFFFF, caller=regs.lr & 0xFFFFFFFF,
                     callbackAddress=0x021E5900)
        need(value["fieldPointer"] == self.session.field_pointer(), "VBlank Field owner differs")
        self.vblank.append(value)
        return value

    def _vblank_after(self, value, context):
        need(self.vblank and self.vblank.pop() is value and self.pending_upload is None,
             "VBlank return lost its completed upload")
        return None

    def _material_before(self):
        regs = self.session.emu.memory.register_arm9
        address = regs.r0 & 0xFFFFFFFF
        raw = public_bytes(self.session, address, 0xB4)
        render, material = struct.unpack_from("<I", raw, 4)[0], struct.unpack_from("<I", raw, 0xB0)[0]
        records = [r for r in self._records() if r["drawPointer"] + 0x30 == render]
        if not records:
            return None
        need(len(records) == 1, "MAT has multiple owners")
        view = records[0]
        words = struct.unpack("<14I", public_bytes(self.session, material, 0x38))
        return dict(view=view, renderStatePointer=address, renderObjectPointer=render,
                    materialPointer=material, beforeWord=words[5], textureFormat=(words[4] >> 26) & 7)

    def _material_after(self, value, context):
        value["afterWord"] = struct.unpack_from("<I", public_bytes(self.session, value["materialPointer"], 0x38), 20)[0]
        slot = value["view"]["handle"]["slot"]
        upload = self.uploads.get(slot)
        if upload is None or upload["view"]["handle"] != value["view"]["handle"]:
            return None
        # A completed SDK upload can still share a queue with pending native
        # transfers. The real MAT callback then leaves its normal word alone.
        # Read the returned owner: the callback may itself clear pending, so
        # its entry flag alone must not discard a completed legal MAT.
        view = value["view"]
        if view.get("uploadPending") and value["afterWord"] == value["beforeWord"]:
            current = [r for r in self._records() if r["recordPointer"] == view["recordPointer"]]
            need(len(current) == 1, "pending MAT lost its current owner")
            current = current[0]
            fields = ("handle", "subjectIdentity", *GEN_KEYS, "species", "form", "level", "roleId",
                      *POINTER_KEYS, "recordPointer", "originalPaletteKey", "privatePaletteKey",
                      "paletteBytes", "mode", "strength", "yielded", "drawCommand", "drawTiming",
                      "originalHex", "tintedHex")
            identity = ("handle", "subjectIdentity", *GEN_KEYS, "species", "form", "level", "roleId")
            need(all(current[k] == view[k] == upload["view"][k] for k in fields)
                 and all(current["owner"]["actor"][k] == view["owner"]["actor"][k]
                         == upload["view"]["owner"]["actor"][k] for k in identity)
                 and all(current["owner"].get(k) == view["owner"].get(k)
                         == upload["view"]["owner"].get(k) for k in
                         ("actorPointer", "objectPointer", "fieldPointer", "context")),
                 "pending MAT changed its palette owner")
            offset = value["beforeWord"] - ((view["originalPaletteKey"] & 0xFFFF) >> 1)
            if (current.get("uploadPending") and value["textureFormat"] == 3
                    and 0 <= offset <= (view["paletteBytes"] - 32) // 16 and offset % 2 == 0
                    and view["privatePaletteKey"] != 0
                    and (view["strength"] == 0 or ((view["privatePaletteKey"] & 0xFFFF) >> 1)
                         != ((view["originalPaletteKey"] & 0xFFFF) >> 1))
                    and view["mode"] in (1, 2) and view["yielded"] == 0
                    and view["drawCommand"] == 4 and view["drawTiming"] == 2
                    and value["renderObjectPointer"] == view["drawPointer"] + 0x30):
                return None # No permission or receipt yet; the later real MAT owns both.
        key = (slot, upload["uploadId"])
        value["uploadId"] = upload["uploadId"]
        self.materials[slot] = deepcopy(value)
        if key in self.material_keys:
            return None
        self.material_keys.add(key)
        return value

    def _heal_before(self):
        s = self.session
        if s.native_bridge_active or s.rt.field_map_id(s.emu) != 69:
            return None
        regs = s.emu.memory.register_arm9
        if regs.r1 != 163:
            return None
        pointer = regs.r0 & 0xFFFFFFFF
        party = s.party_pointer()
        delta = pointer - party - 8
        if delta < 0 or delta % 236 or delta // 236 >= 6:
            return None
        return dict(mapId=69, partySlot=delta // 236, pokemonPointer=pointer,
            subjectIdentity=struct.unpack("<I", s.read(pointer, 4))[0],
            requestedHp=struct.unpack("<H", public_bytes(s, regs.r2 & 0xFFFFFFFF, 2))[0],
            caller=regs.lr & 0xFFFFFFFF, synthetic=False)

    def _heal_after(self, value, context):
        need(not self.session.native_bridge_active
             and struct.unpack("<I", self.session.read(value["pokemonPointer"], 4))[0] == value["subjectIdentity"],
             "natural healing changed party identity")
        return value

    def sample(self, snapshot):
        if not self.active:
            return
        records = self._records() if snapshot.get("fieldAvailable") else []
        snapshot["pokemonAppearance"] = dict(schemaVersion=1, available=True,
            frame=snapshot["frame"], nativeCycle=snapshot["nativeCycle"],
            observationBoundary="main-task-queue-completion",
            identity=dict(romSha256=self.session.rom_hash, capsuleElfSha256=self.elf_hash,
                          behaviorBlobSha256=self.blob_hash), records=records,
            conditions=self._completed_conditions(snapshot), uploads=deepcopy(self.uploads),
            materials=deepcopy(self.materials), clears=deepcopy(self.clears), uploadCount=self.upload_count)

    def _completed_conditions(self, snapshot):
        # Appearance can refresh before this queue evaluates a new condition.
        # Keep its authenticated pointer, then read state at the named boundary.
        result = {}
        if not snapshot.get("fieldAvailable"):
            return result
        for slot, previous in self.conditions.items():
            old = previous["owner"]
            current = next((a for a in snapshot.get("actors", [])
                if a.get("active") and all(a.get(k) == old["actor"].get(k) for k in
                    ("handle", "subjectIdentity", "species", "role", *GEN_KEYS))), None)
            if current is None or old["context"] != snapshot["context"]:
                continue
            owner = self._owner(slot)
            need(all(owner[k] == old[k] for k in
                ("actorPointer", "objectPointer", "fieldPointer", "context"))
                and all(owner["actor"].get(k) == current.get(k) for k in
                    ("handle", "subjectIdentity", "species", "role", *GEN_KEYS)),
                "completed condition read changed its native owner")
            value = decode_conditions(self.session.read, previous["preparedPointer"],
                owner["actor"], self.blob, snapshot["actorFrame"], self.enabled, self.bank)
            value["owner"] = owner
            result[slot] = value
        return result

    def close(self):
        self.active = False
        for token in self.tokens:
            self.observer.hooks.remove(token)
            if token in self.observer.tokens:
                self.observer.tokens.remove(token)
        self.tokens.clear()
