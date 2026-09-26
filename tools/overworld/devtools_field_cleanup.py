"""Bounded, read-only cleanup state. No inferred cleanup return values."""
import struct

ACTOR_ELF = "overworld_actor_system_overlay_linked.o"
ACTOR_REGION = (0x023B65A0, 0x023BAB00)
ACTOR_STATE_ADDRESS = 0x023BA170

DATA = (
    ("fieldTransition", "field_linked.o", "sOverworldFieldTransition", ".bss", 24),
    ("readyTaskMapId", "linked.o", "sFieldReadyTaskMapId", ".text", 2),
    ("selectorState", "field_linked.o", "gOverworldFollowerSelectorStateStorage", ".text", 1),
    ("wildFlags", "overworld_wild_spawns_overlay_linked.o", "sOverworldWildFlags", ".bss", 6),
    ("actorState", "overworld_actor_system_overlay_linked.o", "gOverworldActorSystemState", ".bss", 2448),
)
CODE = (
    ("linked.o", "OverworldFieldService_ShutdownTransientServices"),
    ("field_linked.o", "OverworldFieldService_PollFrameImpl"),
    ("field_linked.o", "OverworldFieldService_OnMapHeaderChangedImpl"),
    ("overworld_wild_spawns_overlay_linked.o", "OverworldWildSpawns_CleanupResidentData"),
    ("overworld_actor_system_overlay_linked.o", "ActorSystem_EnsureInitialized"),
    ("overworld_actor_system_overlay_linked.o", "OverworldActorSystem_CompatibilityTransitionImpl"),
)


def symbol(image, name, kind, section_name=None, expected_size=None):
    if image[:7] != b"\x7fELF\x01\x01\x01":
        raise ValueError("invalid-linked-elf")
    offset = struct.unpack_from("<I", image, 32)[0]
    stride, count, names_index = struct.unpack_from("<3H", image, 46)
    if stride != 40:
        raise ValueError("invalid-section-stride")
    sections = [struct.unpack_from("<10I", image, offset + i * stride) for i in range(count)]
    row = sections[names_index]
    section_names = image[row[4]:row[4] + row[5]]
    matches = []
    for row in sections:
        if row[1] != 2:
            continue
        if row[9] != 16 or row[5] % 16:
            raise ValueError("invalid-symbol-table")
        strings = sections[row[6]]
        names = image[strings[4]:strings[4] + strings[5]]
        for pos in range(row[4], row[4] + row[5], 16):
            label, address, size, info, _, index = struct.unpack_from("<IIIBBH", image, pos)
            if names[label:].split(b"\0", 1)[0] != name.encode():
                continue
            if not 0 < index < count or info & 15 != kind:
                raise ValueError("wrong-symbol-kind-or-owner: " + name)
            owner = sections[index]
            label = section_names[owner[0]:].split(b"\0", 1)[0].decode()
            address = address & ~1 if kind == 2 else address
            if not owner[2] & 2 or not size or not owner[3] <= address <= owner[3] + owner[5] - size:
                raise ValueError("symbol-outside-owner: " + name)
            if section_name is not None and label != section_name:
                raise ValueError("wrong-symbol-section: " + name)
            if expected_size is not None and size != expected_size:
                raise ValueError("wrong-symbol-size: " + name)
            code = None
            if kind == 2:
                if owner[1] != 1 or not owner[2] & 4 or size > 2048:
                    raise ValueError("invalid-code-extent: " + name)
                start = owner[4] + address - owner[3]
                code = image[start:start + size]
                if len(code) != size:
                    raise ValueError("short-code")
            matches.append((address, size, code))
    if len(matches) != 1:
        raise ValueError("missing-or-ambiguous-symbol: " + name)
    return matches[0]


def observe_field_cleanup(read, authenticate, load_elf, loaded_overlays, frame, native_cycle):
    result = {"known": False, "reason": "unread", "diagnosticOnly": True,
              "acceptedProof": False, "boundary": "paused-native-cycle-end",
              "frame": frame, "nativeCycle": native_cycle, "readBytes": 0}
    try:
        # Boot loads Actor 158 through LoadOverlayNoInit, not the SDK tracked
        # table. Its resident bytes and state header establish identity below.
        if not {131, 149}.issubset(loaded_overlays):
            raise ValueError("required-overlay-missing")
        images = {name: load_elf(name) for name in {row[1] for row in DATA}}
        bindings = {key: symbol(images[file], name, 1, section, size)
                    for key, file, name, section, size in DATA}
        actor_address, actor_size, _ = bindings["actorState"]
        if actor_address != ACTOR_STATE_ADDRESS or actor_address + actor_size > ACTOR_REGION[1]:
            raise ValueError("actor-state-outside-resident-region")
        for file, name in CODE:
            address, size, expected = symbol(images[file], name, 2)
            if file == ACTOR_ELF and not ACTOR_REGION[0] <= address <= ACTOR_STATE_ADDRESS - size:
                raise ValueError("actor-code-outside-resident-region")
            if authenticate(address, size, expected) is not True:
                raise ValueError("code-identity-mismatch: " + name)
        def value(key, prefix=None):
            address, size, _ = bindings[key]
            if not 0x02000000 <= address <= 0x02400000 - size:
                raise ValueError("invalid-data-range")
            if prefix is not None:
                size = min(size, prefix)
            result["readBytes"] += size
            data = read(address, size)
            if not isinstance(data, (bytes, bytearray)) or len(data) != size:
                raise ValueError("short-data: " + key)
            return data
        fields = struct.unpack("<3I4H4B", value("fieldTransition"))
        result["fieldTransition"] = dict(zip(("fieldSystem", "manager", "sequence",
            "expectedFieldEpoch", "previousMapId", "currentMapId", "previousMapGeneration",
            "disposition", "acknowledgements", "active", "reserved"), fields))
        result["readyTaskMapId"] = struct.unpack("<H", value("readyTaskMapId"))[0]
        result["selectorState"] = value("selectorState")[0]
        result["wildFlags"] = dict(zip(("behaviorDataLoadAttempted", "helperOverlayReady",
            "movementFrameDecisionCounter", "movementFrameTaskExecuting", "spawnHopPreparing"), value("wildFlags")))
        # Public internal layout: 24-byte state prefix, then 20-byte transition.
        actor = value("actorState", 44)
        if struct.unpack_from("<IHH", actor) != (0x5353574F, 2, bindings["actorState"][1]):
            raise ValueError("actor-state-header-mismatch")
        result["actorTransition"] = dict(zip(("sequence", "previousMapId", "currentMapId",
            "previousFieldEpoch", "previousMapGeneration", "actorMask", "resumeMotionMask",
            "phase", "disposition"), struct.unpack_from("<I6H2B", actor, 24)))
        if result["actorTransition"]["phase"] not in range(5):
            raise ValueError("invalid-actor-transition-phase")
        if fields[-2] not in (0, 1) or result["wildFlags"]["helperOverlayReady"] not in (0, 1):
            raise ValueError("invalid-state-flag")
        result.update(known=True, reason="authenticated-state-only")
    except Exception as error:
        result.update(known=False, reason=str(error)[:240])
    return result
