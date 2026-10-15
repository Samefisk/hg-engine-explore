"""Coherent native HP and hit guard reads at the completed field queue.

No guest call, write, input, or extra frame is used. The compiled overlay
descriptor anchors the record; each row must match the live actor identity.
"""

import hashlib
import json
from pathlib import Path
import struct

from tools.overworld.devtools_player_health_observer import _check_descriptor
from tools.overworld.devtools_runtime import DevtoolsFailure, require
from tools.overworld.actor_probe import decode_actor_state
from tools.overworld.devtools_field_cleanup import symbol
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.spawn_identity import live_spawn_flags
from tools.overworld.devtools_application_bank import (
    decode_application_bank, global_application, global_mask, local_application,
)


OFFSETS = dict(personality=0, mapId=4, mapGeneration=6,
    encounterGeneration=8, species=10, maxHp=12, currentHp=14, hitCount=16,
    form=18, level=19, initialized=20, immunityFrames=21,
    knockbackOptions=22, knockbackDirection=23, knockbackPending=24,
    lastDamage=25, crashMotionIdentity=26)
HALFWORDS = frozenset(("mapId", "mapGeneration", "encounterGeneration",
                      "species", "maxHp", "currentHp", "hitCount", "crashMotionIdentity"))
WILD_STATE_SIZE = 952
WILD_SPAWN_SIZE = 20
# Actual ARM header offsets; the focused reader test compiles these assertions.
WILD_MOVEMENT_COOLDOWN = 0xED
WILD_MOVEMENT_SPOT_STATE = 0x108
WILD_MOVEMENT_EMOTE_TIMER = 0x112
WILD_MOVEMENT_ACTOR_CONTROL_MODE = 0x3AD
WILD_TIMER_PREFIX_SIZE = WILD_MOVEMENT_EMOTE_TIMER + 10
WILD_MOVEMENT_CRASH_SHAKE_TIMER = 0x2CA
WILD_MOVEMENT_CRASH_SHAKE_BASE_X = 0x2D4
WILD_MOVEMENT_CRASH_SHAKE_BASE_Z = 0x2FC
WILD_CRASH_SHAKE_SIZE = WILD_MOVEMENT_CRASH_SHAKE_BASE_Z + 10 * 4 - WILD_MOVEMENT_CRASH_SHAKE_TIMER
WILD_FIELD_OFFSET = 0xE0
WILD_RUNTIME_OFFSET = 0xE4
WILD_RUNTIME_SIZE = 2856
RUNTIME_RETURN_MOVES_OFFSET = 0x51C
RETURN_MOVE_SIZE = 144
RUNTIME_MOTION_IDENTITIES_OFFSET = 0xDC
RUNTIME_DESPAWN_PENDING_MASK_OFFSET = 0x270
WILD_SPAWN_RUN_READ_OFFSET = 0x1EC  # Run bytes begin two bytes into this aligned span.
WILD_CAPTURE_MASK_READ_OFFSET = 0x3A4
WILD_CONTROL_READ_OFFSET = 0x3AC
RUNTIME_THROW_OFFSET = 0x220
RUNTIME_CONDITIONS_OFFSET = 0x514
CATALOG_BLOB_VERSION = 95
CONDITIONS_SIZE = 3100
CONDITIONS_BINDINGS_OFFSET = 0x998
PREPARED_ACTOR_SIZE = 88
BINDINGS_SIZE = 60
CONDITION_STATE_SIZE = 16
CONDITIONS_PUBLICATION_OFFSET = 2332
CONDITIONS_PUBLICATION_SIZE = 124
# Existing bindings plus two bounded reads of every possible captured condition state,
# its prepared owner and the published application/target arrays.
INTERACTION_READ_BUDGET = 1160 + 10 * (88 + 32 * 16 * 2) + 124 * 2


def _interaction_layout(session):
    """Bind private reads to the packaged native getter and adapter ABI."""
    key = (session.rom_hash, id(session.emu))
    cached = getattr(session, "pokemon_combat_interaction_layout", None)
    if cached is not None and cached["key"] == key:
        return cached
    build = Path(session.rt.REPO) / "build"
    wild_image = (build / "overworld_wild_spawns_overlay_linked.o").read_bytes()
    getter = symbol(wild_image, "OverworldWildSpawns_GetConditionRuntime", 2, expected_size=24)
    blob_getter = symbol(wild_image, "OverworldWildSpawns_GetBehaviorDataBlob", 2, expected_size=128)
    blob_owner = symbol(wild_image, "sOverworldWildBehaviorDataBlob", 1, ".bss", 4)
    # This exact native getter loads its pointer from the flags base + 16.
    # Keep the private owner read bound to the complete current compiled body.
    require(hashlib.sha256(blob_getter[2]).hexdigest() ==
            "7ba0b931b365ce25288248ae33270818c5bdda21d5e8df6478bb31a41f525494"
            and struct.unpack_from("<I", blob_getter[2], 108)[0] + 16 == blob_owner[0],
            "Pokémon condition catalog owner getter differs", "combat-interaction-identity")
    # Native Thumb getter: state+E4 -> runtime, then literal+514 -> conditions.
    # Reject a different compiled layout before following either private pointer.
    require(getter[2][4:8] == bytes.fromhex("e4300068")
            and getter[2][12:16] == bytes.fromhex("014bc058")
            and struct.unpack_from("<I", getter[2], 20)[0] == RUNTIME_CONDITIONS_OFFSET,
            "Pokémon interaction getter layout differs", "combat-interaction-identity")
    image = (build / "overworld_actor_system_overlay_linked.o").read_bytes()

    def table(name, size):
        address, _, _ = symbol(image, name, 1, expected_size=size)
        offset = struct.unpack_from("<I", image, 32)[0]
        stride, count = struct.unpack_from("<2H", image, 46)
        for n in range(count):
            _, kind, flags, base, start, length = struct.unpack_from(
                "<6I", image, offset + stride * n)
            if kind == 1 and flags & 2 and base <= address <= base + length - size:
                return address, image[start + address - base:start + address - base + size]
        raise DevtoolsFailure("combat-interaction-identity", "interaction table has no linked bytes")

    service = table("gOverworldActorSystemMovementPolicyServiceEntry", 16)
    adapter = table("gOverworldBehaviorConditionAdapterEntry", 28)
    resolver = table("gOverworldActorSystemResolverServiceEntry", 16)
    require(struct.unpack_from("<IHH", service[1]) == (0x504D574F, 5, 16)
            and struct.unpack_from("<I", service[1], 12)[0] == adapter[0]
            and struct.unpack_from("<IHH", adapter[1]) == (0x4143574F, 12, 28),
            "Pokémon interaction adapter layout differs", "combat-interaction-identity")
    cached = dict(key=key, getter=getter, service=service, adapter=adapter, resolver=resolver,
                  blobGetter=blob_getter, blobOwnerAddress=blob_owner[0])
    session.pokemon_combat_interaction_layout = cached
    return cached


def _interaction_handle(raw):
    slot, generation, field, map_generation, encounter, reserved = struct.unpack("<6H", raw)
    require(slot < 10 and generation and field and map_generation and encounter and not reserved,
            "Pokémon interaction handle is invalid", "combat-interaction-state")
    return dict(value=(generation << 16) | slot, slot=slot, generation=generation,
                fieldEpoch=field, mapGeneration=map_generation, encounterGeneration=encounter)


def _catalog_owner_pointer(session, layout, *, read=None):
    """Read the current native owner, not a pointer retained across a map exit."""
    read = session.read if read is None else read
    address, size, code = layout["blobGetter"]
    owner = layout["blobOwnerAddress"]
    require(type(owner) is int and owner % 4 == 0
            and 0x02000000 <= owner <= 0x023FFFFC
            and session.packaged_code(address, size) == code
            and read(address, size) == code,
            "Pokémon condition catalog owner code differs", "combat-interaction-identity")
    raw = read(owner, 4)
    require(isinstance(raw, bytes) and len(raw) == 4,
            "Pokémon condition catalog owner read is incomplete", "combat-interaction-owner")
    return struct.unpack("<I", raw)[0]


def _interaction_catalog(session, layout, field, native_cycle, *, context, read=None):
    """Authenticate the current native source; never call the guest."""
    discovery = getattr(getattr(session, "native_observation", None), "resolver_discovery", None)
    if not isinstance(discovery, dict) or discovery.get("status") != 0:
        return None
    heap = getattr(session, "native_heap_generation", None)
    require(heap is not None and discovery.get("fieldPointer") == field
            and discovery.get("heapGeneration") == heap
            and type(discovery.get("returnNativeCycle")) is int
            and discovery["returnNativeCycle"] <= native_cycle,
            "Pokémon condition catalog owner is stale", "combat-interaction-owner")
    address, code = layout["resolver"]
    require(struct.unpack_from("<IHH", code) == (0x5250574F, 3, 16)
            and session.packaged_code(address, len(code)) == code,
            "Pokémon condition resolver differs from package", "combat-interaction-identity")
    blob = (Path(session.rt.REPO) / "build/OverworldWildBehaviorData.bin").read_bytes()
    require(isinstance(context, dict)
            and all(type(context.get(key)) is int and context[key] > 0
                    for key in ("fieldEpoch", "mapGeneration"))
            and type(context.get("mapId")) is int and context["mapId"] >= 0,
            "Pokémon condition catalog context is missing", "combat-interaction-owner")
    pointer = _catalog_owner_pointer(session, layout, read=read)
    if pointer == 0:
        # Cleanup released the Blob. No catalog, binding or graph credit.
        return None
    discovered = discovery.get("blobAddress")
    require(84 <= len(blob) <= 1024 * 1024 and discovery.get("blobSize") == len(blob)
            and type(discovered) is int and discovered % 4 == 0
            and 0x02000000 <= discovered <= 0x02400000 - len(blob)
            and type(pointer) is int and pointer % 4 == 0
            and 0x02000000 <= pointer <= 0x02400000 - len(blob),
            "Pokémon condition catalog pointer is invalid", "combat-interaction-owner")
    offset, count, stride, size = struct.unpack_from("<IHHI", blob, 52)
    require(struct.unpack_from("<IHH", blob) == (0x4F574244, CATALOG_BLOB_VERSION, 84)
            and struct.unpack_from("<I", blob, 8)[0] == len(blob)
            and stride == 48 and count <= 65535 and offset >= 84
            and offset + count * stride <= size <= len(blob),
            "Pokémon condition catalog layout differs", "combat-interaction-identity")
    digest = hashlib.sha256(blob).hexdigest()
    key = (session.rom_hash, id(session.emu), field, heap,
           context["fieldEpoch"], context["mapGeneration"], context["mapId"],
           pointer, len(blob), digest)
    cached = getattr(session, "pokemon_combat_condition_catalog", None)
    authenticated_bytes = 0
    if cached is None or cached["key"] != key:
        for start in range(0, len(blob), 4096):
            expected = blob[start:start + 4096]
            require(session.read(pointer + start, len(expected)) == expected,
                    "Pokémon live condition catalog differs from package "
                    f"(current=0x{pointer:08X}, discovered=0x{discovery.get('blobAddress', 0):08X}, "
                    f"offset={start})", "combat-interaction-identity")
        bank = decode_application_bank(blob, Path(session.rt.REPO))
        cached = dict(key=key, blob=blob, offset=offset, count=count, bank=bank,
                      identity=dict(blobAddress=pointer, blobSize=len(blob), blobSha256=digest,
                                    fieldSystem=field, heapGeneration=heap,
                                    fieldEpoch=context["fieldEpoch"], mapGeneration=context["mapGeneration"],
                                    mapId=context["mapId"],
                                    blobOwnerAddress=layout["blobOwnerAddress"],
                                    naturalDiscoveryBlobAddress=discovery.get("blobAddress")))
        session.pokemon_combat_condition_catalog = cached
        authenticated_bytes = len(blob)
    require(_catalog_owner_pointer(session, layout, read=read) == pointer,
            "Pokémon condition catalog owner changed during read", "combat-interaction-owner")
    return dict(cached, authenticatedBytes=authenticated_bytes)


def _return_diagnostics(read, read_bytes, state, runtime, throw, field, snapshot, carriers):
    """Optional raw diagnostics; they never grant a movement or condition claim."""
    rows = [row for row in carriers if row["available"]]
    cost = 328 * len(rows) + 140 if rows else 0
    if read_bytes + cost + 12 > INTERACTION_READ_BUDGET:
        return dict(available=False, diagnosticOnly=True, acceptedProof=False,
                    reason="interaction read budget has no room for return diagnostics", readBytes=0)
    if not rows:
        return dict(available=True, diagnosticOnly=True, acceptedProof=False, readBytes=0)
    spans = ((state + WILD_MOVEMENT_SPOT_STATE, 10),
             (state + WILD_SPAWN_RUN_READ_OFFSET, 12),
             (state + WILD_CAPTURE_MASK_READ_OFFSET, 4),
             (state + WILD_CONTROL_READ_OFFSET, 12),
             (runtime + RUNTIME_MOTION_IDENTITIES_OFFSET, 20),
             (runtime + RUNTIME_DESPAWN_PENDING_MASK_OFFSET, 4))
    inputs = [read(address, size) for address, size in spans]
    spot, run, capture, control, identities, despawn = inputs
    actors = {actor["handle"]["slot"]: actor for actor in snapshot["actors"]
              if actor.get("active") is True and actor.get("identityVerified") is True}
    checked_rows = []
    for row in rows:
        slot = row["slot"]
        address = runtime + RUNTIME_RETURN_MOVES_OFFSET + slot * RETURN_MOVE_SIZE
        raw = read(address, RETURN_MOVE_SIZE)
        spawn_address = state + slot * WILD_SPAWN_SIZE
        spawn = read(spawn_address, WILD_SPAWN_SIZE)
        checked_rows.extend(((address, raw), (spawn_address, spawn)))
        subject = dict(zip(("slot", "generation", "fieldEpoch", "mapGeneration",
                            "encounterGeneration", "reserved"), struct.unpack_from("<6H", raw)))
        phase = raw[139]
        alias = struct.unpack_from("<H", raw, 142)[0]
        actor = actors[slot]
        row["returnMove"] = dict(available=True, diagnosticOnly=True, acceptedProof=False,
            pointer=address, rawHex=raw.hex(), phaseId=phase,
            phase=("NONE", "OUTWARD", "PENDING", "RETURNING")[phase] if phase < 4 else "UNKNOWN",
            subject=subject, subjectMatchesActor=all(subject[key] == row["handle"][key]
                for key in ("slot", "generation", "fieldEpoch", "mapGeneration", "encounterGeneration"))
                and subject["reserved"] == 0,
            planRawHex=raw[12:52].hex(), laneRawHex=raw[52:132].hex(),
            fieldSystem=struct.unpack_from("<I", raw, 132)[0],
            originSurfaceId=struct.unpack_from("<H", raw, 136)[0], laneState=raw[138],
            deferredPause=raw[140], retryFrames=raw[141], identityOrRetryFrame=alias,
            ownerInputs=dict(actorFrame=snapshot.get("actorFrame"), fieldSystem=field,
                actorRole=actor.get("role"), inputOwnership=actor.get("inputOwnership"),
                movementSpotState=spot[slot], movementActorControlMode=control[1 + slot],
                spawnRunActive=run[2 + slot], captureTargetMask=struct.unpack_from("<H", capture, 2)[0],
                distanceDespawnPendingMask=struct.unpack_from("<H", despawn)[0],
                movementMotionIdentity=struct.unpack_from("<H", identities, slot * 2)[0],
                spawnEntryPointer=spawn_address, spawnEntryRawHex=spawn.hex(), throwRawHex=throw.hex()))
    for (address, size), expected in zip(spans, inputs):
        require(read(address, size) == expected,
                "Pokémon return owner inputs changed during read", "combat-interaction-owner")
    for address, expected in checked_rows:
        require(read(address, len(expected)) == expected,
                "Pokémon return record changed during read", "combat-interaction-owner")
    require(read(runtime + RUNTIME_THROW_OFFSET, 16) == throw,
            "Pokémon return Throw owner changed during read", "combat-interaction-owner")
    return dict(available=True, diagnosticOnly=True, acceptedProof=False, readBytes=cost)


def _interactions(session, snapshot, field):
    layout = _interaction_layout(session)
    require(snapshot.get("observationBoundary") == "main-task-queue-completion"
            and snapshot.get("fieldAvailable") is True,
            "Pokémon interactions require the completed field queue", "combat-interaction-owner")
    # Cached ELF metadata never grants permission to read an unloaded/replaced owner.
    for address, expected in ((layout["getter"][0], layout["getter"][2]),
                              layout["service"], layout["adapter"], layout["resolver"]):
        require(session.packaged_code(address, len(expected)) == expected,
                "Pokémon interaction code differs from package", "combat-interaction-identity")
    read_bytes = 0

    def read(address, size):
        nonlocal read_bytes
        require(type(address) is int and address % 4 == 0
                and 0x02000000 <= address <= 0x02400000 - size,
                "Pokémon interaction pointer is invalid", "combat-interaction-owner")
        read_bytes += size
        require(read_bytes <= INTERACTION_READ_BUDGET,
                "Pokémon interaction read budget exceeded", "combat-interaction-state")
        raw = session.read(address, size)
        require(isinstance(raw, bytes) and len(raw) == size,
                "Pokémon interaction read is incomplete", "combat-interaction-state")
        return raw

    def pointer(address, size):
        require(address % 4 == 0 and 0x02000000 <= address <= 0x02400000 - size,
                "Pokémon interaction pointer is invalid", "combat-interaction-owner")

    owner = read(session.rt.WILD_STATE + WILD_FIELD_OFFSET, 8)
    current_field, runtime = struct.unpack("<2I", owner)
    result = dict(schemaVersion=1, available=False, reason=None, frame=snapshot["frame"],
                  nativeCycle=snapshot["nativeCycle"], observationBoundary="main-task-queue-completion",
                  fieldSystem=field, runtimePointer=runtime, conditionsPointer=0,
                  identity=dict(romSha256=session.rom_hash, adapterVersion=12,
                                getterSha256=hashlib.sha256(layout["getter"][2]).hexdigest()),
                  carriers=[])
    # Context detach clears the field owner while retaining its allocation.
    # With no active actor, this is absence; it grants no runtime read.
    if current_field == 0 and not any(actor.get("active") is True
                                      for actor in snapshot.get("actors", [])):
        if runtime:
            pointer(runtime, WILD_RUNTIME_SIZE)
        require(read(session.rt.WILD_STATE + WILD_FIELD_OFFSET, 8) == owner,
                "Pokémon interaction owner changed during read", "combat-interaction-owner")
        result.update(reason="wild field owner is unbound", readBytes=read_bytes)
        return result
    if current_field != field:
        # The sampler wraps this exception as text; retain the measured words
        # there as well as in details without widening private-read admission.
        raise DevtoolsFailure("combat-interaction-owner",
            f"Pokémon interaction field owner changed (field=0x{field:08X}, "
            f"current=0x{current_field:08X}, runtime=0x{runtime:08X}, "
            f"ownerHex={owner.hex()}, frame={snapshot['frame']}, "
            f"nativeCycle={snapshot['nativeCycle']})",
            details=dict(fieldSystem=field, currentFieldSystem=current_field,
                         runtimePointer=runtime, ownerHex=owner.hex(),
                         wildStateAddress=session.rt.WILD_STATE,
                         frame=snapshot["frame"], nativeCycle=snapshot["nativeCycle"]))
    if runtime == 0:
        result.update(reason="wild runtime is not loaded", readBytes=read_bytes)
        return result
    pointer(runtime, WILD_RUNTIME_SIZE)
    conditions = struct.unpack("<I", read(runtime + RUNTIME_CONDITIONS_OFFSET, 4))[0]
    result["conditionsPointer"] = conditions
    if conditions == 0:
        result.update(reason="conditions are not prepared", readBytes=read_bytes)
        return result
    pointer(conditions, CONDITIONS_SIZE)
    throw = read(runtime + RUNTIME_THROW_OFFSET, 16)
    targets = list(throw[:10])
    target_mask, carrier_mask, recovering_mask = struct.unpack_from("<3H", throw, 10)
    require(not (target_mask | carrier_mask | recovering_mask) & ~0x3FF,
            "Pokémon interaction Throw masks are invalid", "combat-interaction-state")
    result["throwState"] = dict(targets=targets, targetMask=target_mask,
                                carrierMask=carrier_mask, recoveringMask=recovering_mask, rawHex=throw.hex())
    actors = [actor for actor in snapshot.get("actors", [])
              if actor.get("active") is True and actor.get("identityVerified") is True]
    slots = [actor.get("handle", {}).get("slot") for actor in actors]
    require(len(actors) <= 10 and len(set(slots)) == len(slots),
            "Pokémon interaction subjects are ambiguous", "combat-interaction-owner")

    catalog = _interaction_catalog(session, layout, field, snapshot["nativeCycle"],
                                   context=snapshot["context"], read=read)

    def binding(raw, species):
        kind, reserved = raw[12:14]
        source, expires, application, lifetime, flags, reason = struct.unpack_from("<HIBBBB", raw, 14)
        require(kind <= 2 and reserved == 0 and lifetime <= 1 and flags in (0, 1)
                and (reason <= 8 or 16 <= reason <= 22),
                "Pokémon interaction binding fields are invalid", "combat-interaction-state")
        actor_handle = _interaction_handle(raw[:12]) if kind == 2 else None
        require(kind == 2 or raw[:12] == bytes(12),
                "Pokémon interaction non-actor target has a handle", "combat-interaction-state")
        require((flags == 0 and kind == 0) or (flags == 1 and kind != 0
                and source != 0xFFFF and application < 32),
                "Pokémon interaction binding admission is invalid", "combat-interaction-state")
        matches = [actor for actor in actors if actor.get("handle") == actor_handle] if kind == 2 else []
        require(not flags or catalog is not None,
                "Pokémon binding lacks authenticated catalog", "combat-interaction-owner")
        mapped = global_application(catalog["bank"], species, application) if flags else None
        return dict(bound=bool(flags), flags=flags, sourceConditionId=source,
                    sourceApplication=mapped, sourceApplicationLocal=application,
                    expiresAt=expires, lifetime=lifetime, reason=reason,
                    target=dict(kind=("NONE", "PLAYER", "ACTOR")[kind], actor=actor_handle),
                    targetCurrent=(len(matches) == 1 if kind == 2 else kind == 1), rawHex=raw.hex())

    publication = None
    checked_states = []
    checked_prepared = []
    for actor in actors:
        slot = actor["handle"]["slot"]
        prepared = read(conditions + slot * PREPARED_ACTOR_SIZE, PREPARED_ACTOR_SIZE)
        count, valid, capacity = struct.unpack_from("<BBH", prepared, 80)
        require(valid <= 1 and count <= capacity <= 32,
                "Pokémon interaction prepared record is invalid", "combat-interaction-state")
        row = dict(slot=slot, handle=dict(actor["handle"]), role=actor["role"], available=False)
        if not valid:
            row["reason"] = "actor conditions are not prepared"
            result["carriers"].append(row)
            continue
        require(_interaction_handle(prepared[:12]) == actor["handle"],
                "Pokémon interaction prepared subject is stale", "combat-interaction-owner")
        subject_damage_pending = struct.unpack_from("<H", prepared, 86)[0]
        require(struct.unpack_from("<H", prepared, 84)[0] == actor["species"]
                and subject_damage_pending in (0, 1),
                "Pokémon interaction prepared species differs", "combat-interaction-owner")
        row["conditionCaptures"] = []
        if count:
            state_pointer = struct.unpack_from("<I", prepared, 12)[0]
            pointer(state_pointer, capacity * CONDITION_STATE_SIZE)
            if catalog is None:
                row["conditionCaptureReason"] = "no successful natural resolver discovery"
            else:
                indexes = struct.unpack_from(f"<{count}H", prepared, 16)
                require(len(set(indexes)) == count and all(i < catalog["count"] for i in indexes),
                        "Pokémon prepared condition catalog index is invalid", "combat-interaction-state")
                for index, source in enumerate(indexes):
                    start = catalog["offset"] + source * 48
                    entry = catalog["blob"][start:start + 48]
                    # Existing UntilCrash captures and transient while-true
                    # actor targets use the same authenticated prepared state.
                    if entry[38] != 2 and not (entry[38] == 0 and entry[39] == 2):
                        continue
                    application = catalog["bank"]["conditionOwners"][source]
                    application_local = local_application(catalog["bank"], actor["species"], application)
                    if publication is None:
                        publication = read(conditions + CONDITIONS_PUBLICATION_OFFSET,
                                           CONDITIONS_PUBLICATION_SIZE)
                        require(not struct.unpack_from("<H", publication, 120)[0] & ~0x3FF,
                                "Pokémon condition target mask is invalid", "combat-interaction-state")
                    local = global_mask(catalog["bank"], actor["species"],
                        struct.unpack_from("<I", publication, slot * 4)[0])
                    state_address = state_pointer + index * CONDITION_STATE_SIZE
                    state = read(state_address, CONDITION_STATE_SIZE)
                    active, cooldown, target_slot, generation, encounter, kind, flags = struct.unpack(
                        "<II3H2B", state)
                    require(kind <= 2 and not flags & ~127,
                            "Pokémon condition capture fields are invalid", "combat-interaction-state")
                    target_handle = None
                    if kind == 2:
                        target_handle = _interaction_handle(struct.pack("<6H", target_slot, generation,
                            actor["handle"]["fieldEpoch"], actor["handle"]["mapGeneration"], encounter, 0))
                    # Native Clear changes kind only; inactive entries retain
                    # previous target IDs. They never grant a target handle.
                    matches = [a for a in actors if a.get("handle") == target_handle] if kind == 2 else []
                    row["conditionCaptures"].append(dict(preparedIndex=index, catalogIndex=source,
                        conditionId=struct.unpack_from("<H", entry, 32)[0], application=application,
                        applicationLocal=application_local,
                        activationMode=entry[38], durationFrames=struct.unpack_from("<H", entry, 20)[0],
                        cooldownFrames=struct.unpack_from("<H", entry, 22)[0],
                        activeUntil=active, cooldownUntil=cooldown, flags=flags,
                        target=dict(kind=("NONE", "PLAYER", "ACTOR")[kind], actor=target_handle),
                        targetCurrent=(len(matches) == 1 if kind == 2 else kind == 1),
                        targetValid=bool(struct.unpack_from("<H", publication, 120)[0] & (1 << slot)),
                        targetPosition=[struct.unpack_from("<h", publication, 80 + slot * 2)[0],
                                        struct.unpack_from("<h", publication, 100 + slot * 2)[0]],
                        activeApplicationMask=struct.unpack_from("<I", publication, slot * 4)[0],
                        activeGlobalApplications=local,
                        preparedPointer=conditions + slot * PREPARED_ACTOR_SIZE,
                        statesPointer=state_pointer, preparedRawHex=prepared.hex(), rawHex=state.hex()))
                    checked_states.append((state_address, state))
                if row["conditionCaptures"]:
                    checked_prepared.append((conditions + slot * PREPARED_ACTOR_SIZE, prepared))
        raw = read(conditions + CONDITIONS_BINDINGS_OFFSET + slot * BINDINGS_SIZE, BINDINGS_SIZE)
        require(_interaction_handle(raw[:12]) == actor["handle"],
                "Pokémon interaction binding subject is stale", "combat-interaction-owner")
        encoded = targets[slot]
        target_slot = (encoded & 0x3F) - 1 if encoded else None
        require(encoded == 0 or 0 <= target_slot < 10,
                "Pokémon interaction Throw target is invalid", "combat-interaction-state")
        row.update(available=True, reason=None, bindings=dict(trigger=binding(raw[12:36], actor["species"]),
                   cargo=binding(raw[36:60], actor["species"])),
                   rawBindingsHex=raw.hex(), throw=dict(targetRaw=encoded, targetSlot=target_slot,
                       carried=bool(encoded & 0x80), windup=bool(encoded & 0x40),
                       targeted=bool(target_mask & (1 << slot)), carrier=bool(carrier_mask & (1 << slot)),
                       recovering=bool(recovering_mask & (1 << slot))))
        result["carriers"].append(row)
    for address, expected in checked_states:
        require(read(address, len(expected)) == expected,
                "Pokémon condition capture changed during read", "combat-interaction-owner")
    for address, expected in checked_prepared:
        require(read(address, len(expected)) == expected,
                "Pokémon condition prepared owner changed during read", "combat-interaction-owner")
    if publication is not None:
        require(read(conditions + CONDITIONS_PUBLICATION_OFFSET, CONDITIONS_PUBLICATION_SIZE) == publication,
                "Pokémon condition target publication changed during read", "combat-interaction-owner")
        result["conditionCatalog"] = dict(catalog["identity"])
        require(catalog["identity"]["heapGeneration"] == session.native_heap_generation,
                "Pokémon condition catalog owner changed during read", "combat-interaction-owner")
    if catalog is not None:
        require(_catalog_owner_pointer(session, layout, read=read) == catalog["identity"]["blobAddress"],
                "Pokémon condition catalog owner changed during read", "combat-interaction-owner")
    result["catalogReadBytes"] = catalog["authenticatedBytes"] if catalog is not None else 0
    result["returnMoveDiagnostics"] = _return_diagnostics(
        read, read_bytes, session.rt.WILD_STATE, runtime, throw, field, snapshot, result["carriers"])
    require(read(session.rt.WILD_STATE + WILD_FIELD_OFFSET, 8) == owner
            and read(runtime + RUNTIME_CONDITIONS_OFFSET, 4) == struct.pack("<I", conditions),
            "Pokémon interaction owner changed during read", "combat-interaction-owner")
    result.update(available=True, readBytes=read_bytes)
    return result


def _motion_layout(session):
    cached = getattr(session, "pokemon_combat_motion_layout", None)
    if cached is not None:
        return cached
    descriptor = session.rt.ACTOR_DESCRIPTOR
    state, sizes, facade = (descriptor[key] for key in ("state", "structures", "facade"))
    native_size, actor_stride, policy_size = (state["size"], state["actorStride"],
                                             sizes.get("actorPolicyState"))
    require((native_size, actor_stride, policy_size, state["capacity"])
            in ((2448, 172, 32, 2448), (2440, 176, 36, 2448)),
            "Pokémon combat motion descriptor differs from linked Actor state", "combat-motion-identity")
    image = (Path(session.rt.REPO) / "build/overworld_actor_system_overlay_linked.o").read_bytes()
    address, length, _ = symbol(image, "gOverworldActorSystemState", 1,
                                section_name=".bss", expected_size=native_size)
    entry_address, entry_size, _ = symbol(image, "gOverworldActorSystemEntry", 1,
                                         expected_size=24)
    require(state["address"] == address and state["size"] == length
            and state["actorPolicyOffset"] == 140
            and state["offsets"]["actors"] == 68
            and state["offsets"]["fieldEpoch"] == 12
            and state["offsets"]["mapGeneration"] == 46
            and descriptor["capacities"]["actors"] == 10
            and descriptor["publicLayouts"]["actorState"]["size"] == 88
            and all(sizes.get(key) == size for key, size in
                    (("actorState", 88), ("motionPlan", 40), ("motionState", 52)))
            and (facade["address"], facade["version"], facade["size"]) == (entry_address, 2, entry_size),
            "Pokémon combat motion descriptor differs from linked Actor state", "combat-motion-identity")
    entry = struct.pack("<IHH4I", 0x5341574F, 2, 24,
                        *(facade["callbacks"][key] for key in ("validate", "apply", "tick", "inspect")))
    require(session.packaged_code(entry_address, 24) == entry,
            "Pokémon combat Actor facade differs from package", "combat-motion-identity")
    cached = dict(descriptor=descriptor, address=address, size=length, actorStride=actor_stride,
                  entryAddress=entry_address, entry=entry)
    session.pokemon_combat_motion_layout = cached
    return cached


def _motion(session, snapshot, actor):
    layout = _motion_layout(session)
    header = session.read(layout["address"], 48)
    require(session.read(layout["entryAddress"], 24) == layout["entry"]
            and struct.unpack_from("<IHH", header) == (0x5353574F, 2, layout["size"])
            and struct.unpack_from("<H", header, 12)[0] == snapshot["context"]["fieldEpoch"]
            and struct.unpack_from("<H", header, 46)[0] == snapshot["context"]["mapGeneration"]
            and struct.unpack_from("<I", header, 8)[0] == snapshot["actorFrame"],
            "Pokémon combat motion owner is not the current Actor queue", "combat-motion-owner")
    pointer = layout["address"] + 68 + actor["handle"]["slot"] * layout["actorStride"]
    raw = session.read(pointer, 140)
    public = decode_actor_state(raw[:88], layout["descriptor"])
    keys = ("handle", "subjectIdentity", "species", "form", "level", "role", "active",
            "authorityGeneration", "engineAnchorGeneration", "presentationGeneration",
            "origin", "target", "motionKind", "motionPhase", "motionElapsed", "motionDuration", "reservationId",
            "inputOwnership")
    require(all(public.get(key) == actor.get(key) for key in keys),
            "Pokémon combat motion belongs to a different public actor", "combat-motion-owner")
    motion = decode_motion(raw[88:140])
    if motion["phase"] not in ("IDLE", "CANCELED"):
        plan = motion["plan"]
        values = dict(fieldEpoch=(plan["fieldEpoch"], actor["handle"]["fieldEpoch"]),
            origin=(plan["origin"], [actor["origin"][key] for key in ("x", "y")]),
            target=(plan["target"], [actor["target"][key] for key in ("x", "y")]),
            kind=(plan["kind"], actor.get("motionKindId")),
            phase=(motion["phaseId"], actor.get("motionPhaseId")),
            elapsed=(motion["elapsed"], actor["motionElapsed"]),
            duration=(plan["duration"], actor["motionDuration"]),
            reservationId=(plan["reservationId"], actor["reservationId"]))
        # AcknowledgeCommit retains the immutable plan during its pause, while
        # ActorSystem_ReleaseTarget clears the public reservation. Suspension
        # preserves that committed pause and its released reservation.
        committed_pause = (motion["phase"] == "SETTLING"
            or (motion["phase"] == "SUSPENDED" and motion["phaseBeforeSuspend"] == 4))
        expected_reservation = 0 if committed_pause else plan["reservationId"]
        checks = {key: native == published for key, (native, published) in values.items()}
        checks["reservationId"] = actor["reservationId"] == expected_reservation
        if committed_pause:
            checks.update(commitPublished=motion["commitPublished"] == 1,
                commitSequence=motion["commitSequence"] == 1,
                completedElapsed=motion["elapsed"] == plan["duration"],
                settleRemaining=0 < motion["settleRemaining"] <= plan["pauseFrames"])
        failed = [key for key, valid in checks.items() if not valid]
        if failed:
            diagnostic = dict(species=actor.get("species"), role=actor.get("role"),
                handle=actor["handle"], frame=snapshot["frame"], actorFrame=snapshot["actorFrame"],
                nativeCycle=snapshot["nativeCycle"], actorPointer=pointer, raw140Hex=raw.hex(),
                public=public, native=motion,
                actor={key: actor.get(key) for key in (*keys, "motionKindId", "motionPhaseId")},
                failedPredicates=failed,
                reservationContract=dict(committedPause=committed_pause,
                    expectedPublicReservationId=expected_reservation),
                predicateValues={key: dict(native=native, published=published)
                                 for key, (native, published) in values.items()})
            # The sampler wraps str(error) before it has a lastSnapshot. Keep
            # these bounded values in the message as well as structured details.
            raise DevtoolsFailure("combat-motion-owner",
                "Pokémon combat native motion differs from its public actor: "
                + json.dumps(diagnostic, separators=(",", ":")), details=diagnostic)
    return motion


def _layout(session):
    cached = getattr(session, "pokemon_combat_layout", None)
    if cached is not None:
        return cached
    descriptor = json.loads((Path(session.rt.REPO)
                             / "build/player-health.debug.json").read_text())
    overlay, _, _, _ = _check_descriptor(descriptor)
    package = session.overlay_code_regions.get(161)
    require(package is not None and package[0] == overlay["base"]
            and len(package[1]) == overlay["fileSize"]
            and hashlib.sha256(package[1]).hexdigest() == overlay["sha256"],
            "Pokémon combat package differs from its native descriptor", "combat-identity")
    layout = descriptor.get("combat", {})
    require(layout.get("version") == 1 and layout.get("size") == 292
            and layout.get("ownerOffsets") == {"fieldSystem": 0, "saveData": 4, "frameState": 8}
            and layout.get("targetOffset") == 12
            and layout.get("targetCount") == 10 and layout.get("targetSize") == 28
            and layout.get("targetOffsets") == OFFSETS
            and type(layout.get("address")) is int and layout["address"] % 4 == 0
            and 0x01FFD5B4 <= layout["address"]
            and layout["address"] + 292 <= package[0] + len(package[1])
            and type(layout.get("wildSavedHpAddress")) is int
            and 0x02000000 <= layout["wildSavedHpAddress"] <= 0x02400000 - 20,
            "Pokémon combat native layout differs", "combat-identity")
    entry = layout.get("entry", {})
    require(entry.get("address") == 0x01FFD580 and entry.get("size") == 52,
            "Pokémon combat entry range differs", "combat-identity")
    code = bytes.fromhex(entry.get("bytesHex", ""))
    require(len(code) == 52 and struct.unpack_from("<IHH", code) == (0x434F4D42, 1, 52)
            and code == package[1][0x3000:0x3034],
            "Pokémon combat entry differs from the package", "combat-identity")
    wild_address, _, _ = symbol((Path(session.rt.REPO) / "build/linked.o").read_bytes(),
                                "sOverworldWildSpawnState", 1, expected_size=WILD_STATE_SIZE)
    require(wild_address == session.rt.WILD_STATE and wild_address % 4 == 0
            and 0x02000000 <= wild_address <= 0x02400000 - WILD_STATE_SIZE
            and WILD_MOVEMENT_CRASH_SHAKE_TIMER + 10 == WILD_MOVEMENT_CRASH_SHAKE_BASE_X
            and WILD_MOVEMENT_CRASH_SHAKE_BASE_X + 40 == WILD_MOVEMENT_CRASH_SHAKE_BASE_Z
            and WILD_MOVEMENT_CRASH_SHAKE_TIMER + WILD_CRASH_SHAKE_SIZE <= WILD_STATE_SIZE,
            "Pokémon combat Wild state differs from its linked owner", "combat-identity")
    cached = dict(layout=layout, entry=code, overlaySha256=overlay["sha256"],
                  wildStateAddress=wild_address)
    session.pokemon_combat_layout = cached
    return cached


def observe_pokemon_combat(session, snapshot, *, include_interactions=False):
    require(type(include_interactions) is bool, "include_interactions must be boolean")
    layout = _layout(session)
    read = lambda address, size: session.rt.actor_memory_read(session.emu, address, size)
    if read(0x01FFD580, 52) != layout["entry"]:
        return {"available": False, "reason": "resident combat entry is not loaded"}
    record = read(layout["layout"]["address"], 292)
    field, save, frame_state = struct.unpack_from("<III", record)
    current_field = session.field_pointer()
    if field != current_field or not field or frame_state != session.rt.WILD_STATE:
        return {"available": False, "reason": "combat owner has no current field frame"}
    require(session.read(field + 0x0C, 4) == struct.pack("<I", save),
            "Pokémon combat save owner differs", "combat-owner")
    require(frame_state == layout["wildStateAddress"],
            "Pokémon combat Wild state owner changed", "combat-owner")
    wild = session.read(frame_state, WILD_TIMER_PREFIX_SIZE)
    require(len(wild) == WILD_TIMER_PREFIX_SIZE,
            "Pokémon combat Wild timer read is incomplete", "combat-state")
    control_modes = session.read(frame_state + WILD_MOVEMENT_ACTOR_CONTROL_MODE, 10)
    require(isinstance(control_modes, bytes) and len(control_modes) == 10,
            "Pokémon combat Wild control-mode read is incomplete", "combat-state")
    crash_shake = session.read(frame_state + WILD_MOVEMENT_CRASH_SHAKE_TIMER, WILD_CRASH_SHAKE_SIZE)
    require(isinstance(crash_shake, bytes) and len(crash_shake) == WILD_CRASH_SHAKE_SIZE,
            "Pokémon combat Wild crash-shake read is incomplete", "combat-state")
    saved = struct.unpack("<10H", session.read(layout["layout"]["wildSavedHpAddress"], 20))
    targets, movement_timers = [], []
    for actor in snapshot.get("actors", []):
        if actor.get("active") is not True or actor.get("identityVerified") is not True:
            continue
        handle = actor.get("handle", {})
        slot = handle.get("slot")
        require(type(slot) is int and 0 <= slot < 10,
                "Pokémon combat actor slot differs", "combat-identity")
        source = actor.get("sourceIdentity", {})
        spawn = wild[slot * WILD_SPAWN_SIZE:(slot + 1) * WILD_SPAWN_SIZE]
        native_source = dict(zip(("object", "personality", "map_id", "species", "form", "level",
                                  "active", "object_id", "encounter_generation"),
                                 struct.unpack("<IIHHBB2xBBH", spawn)))
        require(all(native_source[key] == source.get(key) for key in native_source)
                and live_spawn_flags(native_source["active"])
                and native_source["personality"] == actor.get("subjectIdentity")
                and native_source["map_id"] == snapshot.get("context", {}).get("mapId")
                and (native_source["species"], native_source["form"], native_source["level"])
                    == (actor.get("species"), actor.get("form"), actor.get("level"))
                and native_source["object_id"] == 0xE0 + slot
                and native_source["encounter_generation"] == handle.get("encounterGeneration")
                and handle.get("fieldEpoch") == snapshot.get("context", {}).get("fieldEpoch")
                and handle.get("mapGeneration") == snapshot.get("context", {}).get("mapGeneration"),
                "Pokémon combat Wild timer source is stale or invalid", "combat-state")
        require(control_modes[slot] in (0, 1),
                "Pokémon combat Wild actor control mode is invalid", "combat-state")
        actor_motion = _motion(session, snapshot, actor)
        base_x_offset = WILD_MOVEMENT_CRASH_SHAKE_BASE_X - WILD_MOVEMENT_CRASH_SHAKE_TIMER + slot * 4
        base_z_offset = WILD_MOVEMENT_CRASH_SHAKE_BASE_Z - WILD_MOVEMENT_CRASH_SHAKE_TIMER + slot * 4
        # Preserve the exact native bytes: timer, signed little-endian fx32 X/Z (<Bii).
        raw_crash_shake = crash_shake[slot:slot + 1] + crash_shake[base_x_offset:base_x_offset + 4] \
            + crash_shake[base_z_offset:base_z_offset + 4]
        shake_timer, shake_base_x, shake_base_z = struct.unpack("<Bii", raw_crash_shake)
        movement_timers.append(dict(slot=slot, handle=dict(handle), sourceIdentity=native_source,
            movementCooldown=wild[WILD_MOVEMENT_COOLDOWN + slot],
            movementEmoteTimer=wild[WILD_MOVEMENT_EMOTE_TIMER + slot],
            movementSpotState=wild[WILD_MOVEMENT_SPOT_STATE + slot],
            movementActorControlMode=control_modes[slot],
            movementCrashShakeTimer=shake_timer,
            movementCrashShakeBaseX=shake_base_x,
            movementCrashShakeBaseZ=shake_base_z,
            rawCrashShakeHex=raw_crash_shake.hex()))
        start = 12 + slot * 28
        data = record[start:start + 28]
        values = {name: struct.unpack_from("<I" if name == "personality"
                   else "<H" if name in HALFWORDS else "<B", data, offset)[0]
                  for name, offset in OFFSETS.items()}
        if values["initialized"] == 0:
            continue
        flags = values["knockbackPending"]
        require(flags & ~15 == 0 and flags & 6 != 6
                and (not flags & 6 or bool(flags & 8) == (actor.get("role") == "MOUNTED"))
                and (flags & 6 or not flags & 8 and values["crashMotionIdentity"] == 0),
                "Pokémon combat Crash flags are stale or invalid", "combat-state")
        values.update(knockbackRawFlags=flags, knockbackPending=flags & 1,
                      crashPhase="NEEDS_SETTLE" if flags & 2 else "PLAYING" if flags & 4 else "NONE")
        require(values["initialized"] == 1
                and values["personality"] == source.get("personality")
                and values["mapId"] == snapshot.get("context", {}).get("mapId")
                and values["mapGeneration"] == handle.get("mapGeneration")
                and values["encounterGeneration"] == handle.get("encounterGeneration")
                and (values["species"], values["form"], values["level"])
                    == (actor.get("species"), actor.get("form"), actor.get("level"))
                and 0 < values["maxHp"] <= 65535
                and values["currentHp"] <= values["maxHp"]
                and values["immunityFrames"] <= 60
                and values["knockbackPending"] in (0, 1)
                and values["lastDamage"] <= 50,
                "Pokémon combat row is stale or invalid", "combat-state")
        if slot == 7:
            matches = [mon for mon in snapshot.get("party", [])
                       if mon.get("personality") == values["personality"]
                       and mon.get("species") == values["species"]
                       and mon.get("form") == values["form"]
                       and mon.get("level") == values["level"]]
            # Party setup/healing can happen while the field service is paused.
            # Keep the actual owner value and the cache agreement separately.
            # A new party identity must first receive a service read.
            if len(matches) != 1:
                continue
            actual_hp = matches[0]["hp"]
            actual_max_hp = matches[0]["maxHp"]
        else:
            actual_hp = saved[slot]
            actual_max_hp = values["maxHp"]
            require(actual_hp == values["currentHp"],
                    "Pokémon combat wild HP differs from its resident value", "combat-hp")
        targets.append(dict(values, slot=slot, handle=dict(handle), role=actor["role"],
                            hp=actual_hp, actualMaxHp=actual_max_hp,
                            hpMirrorMatches=actual_hp == values["currentHp"]
                                and actual_max_hp == values["maxHp"],
                            hpSource="party" if slot == 7 else "wild-resident",
                            motion=actor_motion))
    result = {"schemaVersion": 1, "available": True,
            "frame": snapshot["frame"], "nativeCycle": snapshot["nativeCycle"],
            "observationBoundary": "main-task-queue-completion",
            "identity": {"overlaySha256": layout["overlaySha256"],
                         "romSha256": session.rom_hash, "descriptorVersion": 1},
            "fieldSystem": field, "saveData": save, "targets": targets,
            "movementTimers": movement_timers}
    if include_interactions:
        result["interactions"] = _interactions(session, snapshot, field)
    return result
