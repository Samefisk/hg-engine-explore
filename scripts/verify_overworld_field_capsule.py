#!/usr/bin/env python3
"""Check the stock Field code capsule and its unchanged effect delivery guard."""

import argparse
import hashlib
from pathlib import Path
import struct
import subprocess
import tempfile

if __package__:
    from .pack_overworld_actor_slam_jump import verify_shared_slam_jump
    from .pack_overworld_field_capsule import (rest_policy_body, rest_policy_contract,
        REST_POLICY_ADDRESS, REST_POLICY_SIZE, REST_POLICY_SOURCE, REST_POLICY_COPY,
        REST_APPLICABLE_ADDRESS, REST_APPLICABLE_SIZE)
    from .pack_overworld_combat_capsules import section_bytes
    from .verify_pokemon_move_history_capture import (
        elf_bytes_at, elf_helper_bindings, packaged_thumb_calls)
else:
    from pack_overworld_actor_slam_jump import verify_shared_slam_jump
    from pack_overworld_field_capsule import (rest_policy_body, rest_policy_contract,
        REST_POLICY_ADDRESS, REST_POLICY_SIZE, REST_POLICY_SOURCE, REST_POLICY_COPY,
        REST_APPLICABLE_ADDRESS, REST_APPLICABLE_SIZE)
    from pack_overworld_combat_capsules import section_bytes
    from verify_pokemon_move_history_capture import (
        elf_bytes_at, elf_helper_bindings, packaged_thumb_calls)


ROOT = Path(__file__).resolve().parents[1]
BASE, LIMIT = 0x022074A8, 0x022089CC
SUBJECT, DELIVERY = 0x02208200, 0x02208900
ROUTE_BASE_Y = 0x022081E0
RESOLVE_BASE_Y = "OverworldWildSpawns_ResolveRouteBaseY"
APPEARANCE_RELEASE = 0x01FFD250
APPEARANCE_RELEASE_LIMIT = 0x01FFD2CC

# Two private pure helpers use the measured padding after Field release.
PROFILE_PACKED = "OverworldBehaviorPackedOptions_Apply"
PROFILE_PACKED_ADDR, PROFILE_PACKED_SIZE = 0x01FFD2CC, 103
PROFILE_SKID = "OverworldWalk_ProfileSkidTiles"
PROFILE_SKID_ADDR, PROFILE_SKID_SIZE = 0x01FFD336, 74
HOP_EFFECT_CHOICE = "OverworldActorWalkPolicy_SampleHopEffects"
HOP_EFFECT_CHOICE_ADDR, HOP_EFFECT_CHOICE_SIZE = 0x01FFF550, 44
HOP_LEASE = "OverworldHopPresentation_Acquire"
HOP_LEASE_ADDR, HOP_LEASE_SIZE = 0x023DEDF0, 80
HOP_LEASE_CODE = bytes.fromhex(
    "37b5051e01d100203ebd0c4b98470028f9d00b4c0b4b22689a42f4d1"
    "0a4b62689a42f0d12369002bedd0084b0095db6998472369019068469847"
    "e5e7b9223c02f0223c02574f445302001800186b3b02")

CARGO_OBSERVATION = 0x023CCDC8
CARGO_OBSERVATION_SIZE = 184
CARGO_OBSERVATION_CAPACITY = 0xD0
CARGO_OBSERVER = "OverworldWildSpawns_GetInteractionObservation"
NOTICE_CALLERS, NOTICE_CALLERS_SIZE = 0x023C2C1C, 0x164
NOTICE_PHYSICAL_SIZE = 0x14C
NOTICE_CLEAR_PENDING = "OverworldWildSpawns_ClearPendingNotices"
NOTICE_CLEAR_PENDING_ADDR, NOTICE_CLEAR_PENDING_SIZE = 0x023C2C1C, 60
NOTICE_GET_BLOB = "OverworldWildSpawns_GetBehaviorDataBlob"
NOTICE_GET_BLOB_ADDR, NOTICE_GET_BLOB_SIZE = 0x023C2C58, 128
NOTICE_SAMPLE_MOVING = "OverworldWildSpawns_SampleMovingNoticeForSlot"
NOTICE_SAMPLE_MOVING_ADDR, NOTICE_SAMPLE_MOVING_SIZE = 0x023C2CD8, 18
NOTICE_RETIRE_BINDINGS = "OverworldWildSpawns_RetireClearedThrowBindings"
NOTICE_RETIRE_BINDINGS_ADDR, NOTICE_RETIRE_BINDINGS_SIZE = 0x023C2CEC, 124
NOTICE_CLEAR_THROW = "OverworldWildSpawns_ClearThrowStateForSlot"
NOTICE_CLEAR_THROW_ADDR, NOTICE_CLEAR_THROW_SIZE = 0x023C2D68, 10
NOTICE_CLEAR_RELATIONS = "OverworldWildSpawns_ClearThrowRelations"
NOTICE_CLEAR_RELATIONS_ADDR, NOTICE_CLEAR_RELATIONS_SIZE = 0x023D02DC, 228
# Large catalogs use Prepared88, u16 catalog indexes and Blob95/options18.
# Retirement's indexed halfword load adds four bytes within the same reserve;
# capture/uses-binding bytes use reviewed offsets0xB6D1/0xB6D6.
NOTICE_PHYSICAL_SHA256 = "8b4af841b5adfe1988d473f1622bb86710cad5bffd3c4ba66be2648313fd1f45"
# T65 adds two borrowed World pointers (76 -> 84 bytes). Getter locals
# move eight bytes on the stack; its guards, callbacks and extent stay exact.
# The fitted Getter borrows Adapter's validated current Frame. Seal its exact
# native body, the moving/valid guards, and the fixed padding before Bubble.
# Capacity adds 360 bytes to condition runtime offsets. The four named
# Wild targets retain their typed owners and exact reviewed call topology.
CARGO_OBSERVATION_SHA256 = "a4e44080c944e94e4e647613ef0a3a1477bbc152fbc51e8b01f07928ce6b1791"
CARGO_OBSERVATION_CODE = bytes.fromhex(
    'f0b5a9b005000391049205930300f8331888084101210e00084204d1214c2e9e'
    '365d731e9e4100f023fa002803d10024200029b0f0bd2f00e0370021386801f0'
    'd1f9071ef3d0039b1806010e07ac009413ab049a280032f44ffc059a2592002e'
    '04d011492e9b585c0028e0d03a0098321168a1602e9b23620c4860620c4aa262'
    '0c49e162ff6f06a92000b8470400069b002bcdd0002ecbd10399280003f0acfa'
    'c6e7c046b30700005708000080c1ff0145dc3c0249fc3c02'
)
ACTOR_EVALUATE = "OverworldBehaviorConditionAdapter_EvaluateActor"
ACTOR_EVALUATE_ADDR, ACTOR_EVALUATE_SIZE = 0x023B65C0, 880
# Prepared actors use stride 88; Acquire keeps the exact current Field,
# paired epoch/map, null-result gate and borrowed packet dispatch.
ACTOR_EVALUATE_SHA256 = "11cfb506614679d6aee37fbea2fcdefe71fc7a3c1d8713dd328b1a9aac2f1c64"
ACTOR_ACQUIRE_OWNER_CODE = bytes.fromhex(
    "5820684331184c68a24b11941a69109710a80a919047022409900028afd0")
ACTOR_ACQUIRE_SERVICE_WORD = struct.pack("<I", 0x023C22F0)
FRAME_ADDR, FRAME_SIZE = 0x023B6930, 440
FRAME_SHA256 = "320afafc19e1cd88fee6a2d6598600b9fc6fe4ecf8e357e55fed67458a770a08"
SHOW_BUBBLE = "OverworldWildSpawns_ShowBubble"
SHOW_BUBBLE_ADDR, SHOW_BUBBLE_SIZE = 0x023CCE88, 16
SHOW_BUBBLE_CALLEE = "OverworldWildBubble_ShowQuiet"
SHOW_BUBBLE_IMPORT = (0x01FFF3B1, 0, "FUNC", "ABS")
SHOW_BUBBLE_CODE = bytes.fromhex("10 b5 ff 29 01 d0 01 4b 98 47 10 bd") + struct.pack("<I", 0x01FFF3B1)
QUIET_BUBBLE = 0x01FFF3B0
QUIET_BUBBLE_CODE = bytes.fromhex(
    "10 b5 04 4b 00 f0 0c f8 03 48 04 4b 00 f0 08 f8 10 bd c0 46"
) + struct.pack("<III", 0x02203A49, 1501, 0x02006155) + bytes.fromhex("18 47")
WALK_OUTPUT = 0x02208400
WALK_TUNING = 0x02208500
POLICY_INIT = 0x022085D0
SPAWN_ORPHANS = 0x02208360
APPEARANCE_EXIT = 0x02208700
TUNING = "OverworldWalkInput_RefreshTuning"
APPLY_WALK = "OverworldWildSpawns_ApplyWalkPolicyOutput"
NOTIFY = "OverworldWildConditions_NotifyWorldEffect"
FIND = "OverworldBehaviorCondition_FindActor"
CALLERS = (
    ("overworld_mount_overlay_linked.o", 157, "OverworldMount_StartWalkCrash"),
    ("player_health_overlay_linked.o", 161, "OverworldCombat_AcceptedHit"),
    ("overworld_wild_spawns_overlay_linked.o", 161, "OverworldWildSpawns_PublishWalkCrash"),
)
RESIDENT_WALK_LEAVES = {
    "OverworldWildSpawns_PublishWalkCrash": (0x01FFF899, 60, "FUNC"),
    "OverworldWildSpawns_ClearWalkMovementState.constprop.0": (0x01FFF8D5, 54, "FUNC"),
}


def checked(condition, reason):
    if not condition:
        raise ValueError("field capsule: " + reason)


def body_contract(linked, packaged):
    checked(bool(linked) and linked == packaged, "complete linked/package bytes differ")


def hop_lease_contract(hosted, code, packaged):
    checked(hosted is not None
            and hosted[:3] == (HOP_LEASE_ADDR | 1, HOP_LEASE_SIZE, "FUNC")
            and hosted[3] not in ("ABS", "UND"),
            "private Hop lease owner/mode/extent differs")
    body_contract(code, packaged)
    # This exact ARM9 Thumb body checks the current Field lifetime and WODS2
    # entry, then passes Field/epoch/map to acquire. It has no loader or write.
    checked(code == HOP_LEASE_CODE,
            "private Hop lease current-owner guards or read-only body differs")
    checked(packaged_thumb_calls(code, HOP_LEASE_ADDR, HOP_LEASE_ADDR,
                                 HOP_LEASE_SIZE) == [
        (HOP_LEASE_ADDR + 12, "blx_reg", 3),
        (HOP_LEASE_ADDR + 48, "blx_reg", 3),
        (HOP_LEASE_ADDR + 56, "blx_reg", 3)],
        "private Hop lease lifetime/context/acquire dispatch differs")


def verify_hop_lease(build, overlays):
    core = build / "linked.o"
    hosted = elf_helper_bindings(core, (HOP_LEASE,)).get(HOP_LEASE)
    code = elf_bytes_at(core, HOP_LEASE_ADDR, HOP_LEASE_SIZE)
    hop_lease_contract(hosted, code, overlay_span(
        overlays, 129, HOP_LEASE_ADDR, HOP_LEASE_SIZE))
    for filename, overlay_id, caller_name in (
        ("overworld_wild_spawns_overlay_linked.o", 149,
         "OverworldWildSpawns_TryStartManualHopEmote"),
        ("overworld_mount_overlay_linked.o", 1,
         "OverworldMount_TickChainHopEffects"),
        ("overworld_mount_overlay_linked.o", 157,
         "OverworldMount_BeginSharedMotion"),
    ):
        owner = build / filename
        symbols = elf_helper_bindings(owner, (HOP_LEASE, caller_name))
        binding_contract(hosted, symbols.get(HOP_LEASE), HOP_LEASE_ADDR, 84)
        caller = symbols.get(caller_name)
        checked(caller is not None and caller[0] & 1 and caller[1] > 0
                and caller[2] == "FUNC" and caller[3] not in ("ABS", "UND"),
                "private Hop adapter caller owner/mode differs")
        start, size = caller[0] & ~1, caller[1]
        call_contract(elf_bytes_at(owner, start, size), overlay_span(
            overlays, overlay_id, start, size), start, HOP_LEASE_ADDR)


def cargo_observation_contract(hosted, imported_frame, private, field_body, bubble, bubble_callee):
    checked(hosted is not None
            and hosted[:3] == (CARGO_OBSERVATION | 1, CARGO_OBSERVATION_SIZE, "FUNC")
            and hosted[3] not in ("ABS", "UND"),
            "private Wild Cargo observation mode/extent differs")
    checked(imported_frame == (0x023B6931, 0, "FUNC", "ABS"),
            "Cargo observation lost its typed shared frame owner")
    checked(bubble is not None
            and bubble[:3] == (SHOW_BUBBLE_ADDR | 1, SHOW_BUBBLE_SIZE, "FUNC")
            and bubble[3] not in ("ABS", "UND"),
            "private Wild bubble helper mode/extent differs")
    checked(bubble_callee == SHOW_BUBBLE_IMPORT,
            "private Wild bubble helper lost its quiet resident Thumb callee")
    checked(len(private) == CARGO_OBSERVATION_CAPACITY
            and private[CARGO_OBSERVATION_SIZE:SHOW_BUBBLE_ADDR - CARGO_OBSERVATION]
                == bytes(SHOW_BUBBLE_ADDR - CARGO_OBSERVATION - CARGO_OBSERVATION_SIZE)
            and private[SHOW_BUBBLE_ADDR - CARGO_OBSERVATION:] == SHOW_BUBBLE_CODE,
            "Cargo observation reserve/bubble body differs")
    body_contract(private, field_body)
    native = private[:CARGO_OBSERVATION_SIZE]
    checked(native[0x0E:0x26] == bytes.fromhex(
                "f8331888084101210e00084204d1214c2e9e365d731e9e41")
            and native[0xA4:0xA8] == struct.pack("<I", 0x7B3),
            "Cargo observation lost its exact moving slot and binding gate")
    checked(native[0x62:0x6C] == bytes.fromhex("11492e9b585c0028e0d0")
            and native[0xA8:0xAC] == struct.pack("<I", 0x857),
            "Cargo observation lost its exact current valid Frame guard")
    checked(native[0x6C:0x74] == bytes.fromhex("3a0098321168a160"),
            "Cargo observation lost its typed native target-access callback")
    checked(hashlib.sha256(native).hexdigest() == CARGO_OBSERVATION_SHA256,
            "Cargo observation authenticated native body differs")
    calls = [call for call in packaged_thumb_calls(native, CARGO_OBSERVATION,
        CARGO_OBSERVATION, CARGO_OBSERVATION_SIZE) if call[2] == FRAME_ADDR]
    checked(not calls, "Cargo observation repeated Adapter's current Frame build")


def cargo_frame_owner_contract(adapter, frame, subject, linked, packaged):
    checked(adapter is not None
            and adapter[:3] == (ACTOR_EVALUATE_ADDR | 1, ACTOR_EVALUATE_SIZE, "FUNC")
            and adapter[3] not in ("ABS", "UND"),
            "Cargo current Frame Adapter mode/extent/owner differs")
    checked(frame is not None and frame[:3] == (FRAME_ADDR | 1, FRAME_SIZE, "FUNC")
            and frame[3] not in ("ABS", "UND"),
            "Cargo current Frame callee mode/extent/owner differs")
    checked(subject == (SUBJECT | 1, 0, "FUNC", "ABS"),
            "Cargo current Subject callee import differs")
    checked(len(linked) == ACTOR_EVALUATE_SIZE,
            "Cargo current Frame Adapter native extent differs")
    body_contract(linked, packaged)
    calls = [call for call in packaged_thumb_calls(linked, ACTOR_EVALUATE_ADDR,
        ACTOR_EVALUATE_ADDR, ACTOR_EVALUATE_SIZE)
        if call[2] in (FRAME_ADDR, SUBJECT)]
    # Current BuildFrame precedes the observed callback; the ordinary path
    # populates Subject directly from the fixed Field owner.
    checked(calls == [(ACTOR_EVALUATE_ADDR + 0x84, "bl", FRAME_ADDR),
                      (ACTOR_EVALUATE_ADDR + 0x166, "bl", SUBJECT)],
            "Cargo Adapter lacks its direct Frame and Subject Thumb calls")
    # The owner is the current Field plus the prepared subject's paired
    # epoch/map generation. Acquire must precede either native evaluation path.
    checked(linked[0xA4:0xC2] == ACTOR_ACQUIRE_OWNER_CODE
            and linked[0x338:0x33C] == ACTOR_ACQUIRE_SERVICE_WORD,
            "Cargo Adapter lost the current owner Acquire and null-result gate")


def frame_reader_contract(frame, linked, packaged):
    checked(frame is not None and frame[:3] == (FRAME_ADDR | 1, FRAME_SIZE, "FUNC")
            and frame[3] not in ("ABS", "UND"),
            "current Frame reader mode/extent/owner differs")
    checked(len(linked) == FRAME_SIZE, "current Frame reader native extent differs")
    body_contract(linked, packaged)
    checked(hashlib.sha256(linked).hexdigest() == FRAME_SHA256,
            "current Frame reader exact native body differs")
    checked(packaged_thumb_calls(linked, FRAME_ADDR, FRAME_ADDR, FRAME_SIZE) == [
        (FRAME_ADDR + 0x20, "blx_reg", 2),
        (FRAME_ADDR + 0xA0, "blx_reg", 2),
        (FRAME_ADDR + 0xBA, "bl", 0x023DEEBE),
        (FRAME_ADDR + 0x100, "blx_reg", 5),
        (FRAME_ADDR + 0x128, "blx_reg", 5),
        (FRAME_ADDR + 0x13A, "bl", SUBJECT + 0x120)],
        "current Frame reader exact call inventory differs")


def verify_cargo_observation(build, overlays):
    wild = build / "overworld_wild_spawns_overlay_linked.o"
    field = build / "field_linked.o"
    frame = "OverworldBehaviorConditionAdapter_BuildFrame"
    abort, query_target = ("OverworldWildSpawns_AbortThrow",
                          "OverworldWildSpawns_QueryPickupThrowTarget")
    query, identity = "OverworldWildSpawns_QueryAddon", "OverworldWildSpawns_IsCurrentSpawnObject"
    symbols = elf_helper_bindings(wild, (CARGO_OBSERVER, frame, SHOW_BUBBLE,
                                       SHOW_BUBBLE_CALLEE, abort, query_target, query, identity))
    private = section_bytes(wild, ".overworld_field_wild_cargo_observation",
                            CARGO_OBSERVATION, CARGO_OBSERVATION_CAPACITY)
    field_body = elf_bytes_at(field, CARGO_OBSERVATION, CARGO_OBSERVATION_CAPACITY)
    cargo_observation_contract(symbols.get(CARGO_OBSERVER), symbols.get(frame),
                               private, field_body, symbols.get(SHOW_BUBBLE),
                               symbols.get(SHOW_BUBBLE_CALLEE))
    for name, address, size in ((abort, 0x023D03C0, 86),
                               (query_target, 0x023CFC48, 64),
                               (query, 0x023CE1AC, 120),
                               (identity, 0x023CDC44, 72)):
        target = symbols.get(name)
        checked(target is not None and target[:3] == (address | 1, size, "FUNC")
                and target[3] not in ("ABS", "UND"),
                "Cargo observation relocated target owner/mode/extent differs")
        body_contract(elf_bytes_at(wild, address, size),
                      overlay_span(overlays, 149, address, size))
    calls = packaged_thumb_calls(private[:CARGO_OBSERVATION_SIZE],
        CARGO_OBSERVATION, CARGO_OBSERVATION, CARGO_OBSERVATION_SIZE)
    checked((CARGO_OBSERVATION + 0x9C, "bl", symbols[abort][0] & ~1) in calls
            and (CARGO_OBSERVATION + 0x3E, "bl", symbols[query][0] & ~1) in calls
            and struct.unpack_from("<I", private, 0xB0)[0] == symbols[identity][0]
            and struct.unpack_from("<I", private, 0xB4)[0] == symbols[query_target][0],
            "Cargo observation relocated call/pointer differs from its named owner")
    body_contract(private, (build / "overworld_field_cargo_observation.bin").read_bytes())
    binary = (build / "output_field.bin").read_bytes()
    body_contract(private, binary[0x4DC8:0x4E98])
    body_contract(private, overlay_span(overlays, 131, CARGO_OBSERVATION,
                                        CARGO_OBSERVATION_CAPACITY))
    health = build / "player_health_overlay_linked.o"
    quiet = elf_helper_bindings(health, (SHOW_BUBBLE_CALLEE,)).get(SHOW_BUBBLE_CALLEE)
    checked(quiet is not None and quiet[:3] == (QUIET_BUBBLE | 1, len(QUIET_BUBBLE_CODE), "FUNC")
            and quiet[3] not in ("ABS", "UND"),
            "quiet bubble resident owner or extent differs")
    body_contract(QUIET_BUBBLE_CODE, elf_bytes_at(health, QUIET_BUBBLE, len(QUIET_BUBBLE_CODE)))
    body_contract(QUIET_BUBBLE_CODE, overlay_span(overlays, 161, QUIET_BUBBLE, len(QUIET_BUBBLE_CODE)))
    checked(len((build / "output_overworld_wild_spawns_overlay.bin").read_bytes()) == 0xB000,
            "Wild normal output retained the private Field observation section")
    actor = build / "overworld_actor_system_overlay_linked.o"
    subject = "OverworldConditionSubject_Populate"
    owners = elf_helper_bindings(actor, (frame, ACTOR_EVALUATE, subject))
    hosted = owners.get(frame)
    cargo_frame_owner_contract(owners.get(ACTOR_EVALUATE), hosted,
        owners.get(subject),
        elf_bytes_at(actor, ACTOR_EVALUATE_ADDR, ACTOR_EVALUATE_SIZE),
        overlay_span(overlays, 158, ACTOR_EVALUATE_ADDR, ACTOR_EVALUATE_SIZE))
    checked(hashlib.sha256(elf_bytes_at(actor, ACTOR_EVALUATE_ADDR,
                ACTOR_EVALUATE_SIZE)).hexdigest() == ACTOR_EVALUATE_SHA256,
            "Cargo current Frame Adapter exact native body differs")
    binding_contract(hosted, symbols.get(frame), 0x023B6930, 0x1D0)
    frame_reader_contract(hosted, elf_bytes_at(actor, FRAME_ADDR, FRAME_SIZE),
                  overlay_span(overlays, 158, FRAME_ADDR, FRAME_SIZE))


def verify_notice_blob_host(build, overlays):
    wild = build / "overworld_wild_spawns_overlay_linked.o"
    selector = build / "overworld_follower_selector_overlay_linked.o"
    evaluator = "OverworldWildSpawns_EvaluateConditionsForSlot"
    names = (NOTICE_CLEAR_PENDING, NOTICE_GET_BLOB, NOTICE_SAMPLE_MOVING, NOTICE_RETIRE_BINDINGS,
             NOTICE_CLEAR_THROW, NOTICE_CLEAR_RELATIONS, "OverworldWildSpawns_QueryAddon", evaluator)
    symbols = elf_helper_bindings(wild, names)
    clear = symbols.get(NOTICE_CLEAR_PENDING)
    getter = symbols.get(NOTICE_GET_BLOB)
    sample = symbols.get(NOTICE_SAMPLE_MOVING)
    query = symbols.get("OverworldWildSpawns_QueryAddon")
    evaluate = symbols.get(evaluator)
    retirement = symbols.get(NOTICE_RETIRE_BINDINGS)
    clear_throw = symbols.get(NOTICE_CLEAR_THROW)
    clear_relations = symbols.get(NOTICE_CLEAR_RELATIONS)
    checked(clear is not None
            and clear[:3] == (NOTICE_CLEAR_PENDING_ADDR | 1,
                              NOTICE_CLEAR_PENDING_SIZE, "FUNC")
            and clear[3] not in ("ABS", "UND")
            and getter is not None
            and getter[:3] == (NOTICE_GET_BLOB_ADDR | 1, NOTICE_GET_BLOB_SIZE, "FUNC")
            and getter[3] not in ("ABS", "UND")
            and sample is not None
            and sample[:3] == (NOTICE_SAMPLE_MOVING_ADDR | 1,
                               NOTICE_SAMPLE_MOVING_SIZE, "FUNC")
            and sample[3] not in ("ABS", "UND")
            and retirement is not None
            and retirement[:3] == (NOTICE_RETIRE_BINDINGS_ADDR | 1,
                                   NOTICE_RETIRE_BINDINGS_SIZE, "FUNC")
            and retirement[3] not in ("ABS", "UND")
            and NOTICE_RETIRE_BINDINGS_ADDR + NOTICE_RETIRE_BINDINGS_SIZE
                == NOTICE_CALLERS + NOTICE_PHYSICAL_SIZE
            and clear_throw is not None
            and clear_throw[:3] == (NOTICE_CLEAR_THROW_ADDR | 1,
                                    NOTICE_CLEAR_THROW_SIZE, "FUNC")
            and clear_throw[3] not in ("ABS", "UND")
            and clear_relations is not None
            and clear_relations[:3] == (NOTICE_CLEAR_RELATIONS_ADDR | 1,
                                        NOTICE_CLEAR_RELATIONS_SIZE, "FUNC")
            and clear_relations[3] not in ("ABS", "UND")
            and NOTICE_CLEAR_THROW_ADDR == NOTICE_RETIRE_BINDINGS_ADDR + NOTICE_RETIRE_BINDINGS_SIZE
            and query is not None and query[0] & 1 and query[2] == "FUNC"
            and query[3] not in ("ABS", "UND")
            and evaluate is not None and evaluate[0] & 1 and evaluate[1] > 0
            and evaluate[2] == "FUNC" and evaluate[3] not in ("ABS", "UND")
            and NOTICE_SAMPLE_MOVING_ADDR + NOTICE_SAMPLE_MOVING_SIZE
                == NOTICE_RETIRE_BINDINGS_ADDR - 2,
            "Wild notice callers owner/mode/extent differs")
    private = section_bytes(wild, ".overworld_wild_notice_callers",
                            NOTICE_CALLERS, NOTICE_CALLERS_SIZE)
    notice_tail_contract(clear_throw, clear_relations, private,
                         elf_bytes_at(wild, NOTICE_CLEAR_THROW_ADDR, NOTICE_CLEAR_THROW_SIZE))
    notice_tail_controls(clear_throw, clear_relations, private,
                         elf_bytes_at(wild, NOTICE_CLEAR_THROW_ADDR, NOTICE_CLEAR_THROW_SIZE))
    body_contract(elf_bytes_at(wild, NOTICE_CLEAR_RELATIONS_ADDR, NOTICE_CLEAR_RELATIONS_SIZE),
                  overlay_span(overlays, 149, NOTICE_CLEAR_RELATIONS_ADDR,
                               NOTICE_CLEAR_RELATIONS_SIZE))
    body_contract(private, (build / "overworld_notice_callers.bin").read_bytes())
    body_contract(private, elf_bytes_at(selector, NOTICE_CALLERS, NOTICE_CALLERS_SIZE))
    body_contract(private, overlay_span(overlays, 152, NOTICE_CALLERS,
                                        NOTICE_CALLERS_SIZE))
    getter_body = private[NOTICE_GET_BLOB_ADDR - NOTICE_CALLERS:
                          NOTICE_GET_BLOB_ADDR - NOTICE_CALLERS + NOTICE_GET_BLOB_SIZE]
    checked((NOTICE_GET_BLOB_ADDR + 0x12, "bl", query[0] & ~1)
            in packaged_thumb_calls(getter_body, NOTICE_GET_BLOB_ADDR,
                                    NOTICE_GET_BLOB_ADDR, NOTICE_GET_BLOB_SIZE),
            "Wild notice blob getter lost its current query admission")
    sample_body = private[NOTICE_SAMPLE_MOVING_ADDR - NOTICE_CALLERS:
                          NOTICE_SAMPLE_MOVING_ADDR - NOTICE_CALLERS
                          + NOTICE_SAMPLE_MOVING_SIZE]
    checked((NOTICE_SAMPLE_MOVING_ADDR + 0xC, "bl", evaluate[0] & ~1)
            in packaged_thumb_calls(sample_body, NOTICE_SAMPLE_MOVING_ADDR,
                                    NOTICE_SAMPLE_MOVING_ADDR,
                                    NOTICE_SAMPLE_MOVING_SIZE),
            "Wild moving notice caller lost its direct condition evaluation")


def notice_tail_contract(wrapper, target, private, linked_wrapper):
    checked(wrapper is not None
            and wrapper[:3] == (NOTICE_CLEAR_THROW_ADDR | 1, NOTICE_CLEAR_THROW_SIZE, "FUNC")
            and wrapper[3] not in ("ABS", "UND")
            and target is not None
            and target[:3] == (NOTICE_CLEAR_RELATIONS_ADDR | 1,
                               NOTICE_CLEAR_RELATIONS_SIZE, "FUNC")
            and target[3] not in ("ABS", "UND"),
            "Wild notice clear wrapper or relation owner differs")
    checked(len(private) == NOTICE_CALLERS_SIZE
            and hashlib.sha256(private[:NOTICE_PHYSICAL_SIZE]).hexdigest()
                == NOTICE_PHYSICAL_SHA256,
            "Wild notice original caller body differs")
    tail = private[NOTICE_PHYSICAL_SIZE:NOTICE_PHYSICAL_SIZE + NOTICE_CLEAR_THROW_SIZE]
    checked(tail == linked_wrapper
            and hashlib.sha256(tail).hexdigest()
                == "dc84bc5a1ed14df34f7427fbb9dc1bfea6a665b9d57369e69c4e49cfad762fdf"
            and private[NOTICE_PHYSICAL_SIZE + NOTICE_CLEAR_THROW_SIZE:]
                == bytes.fromhex("c046") + bytes(12),
            "Wild notice clear wrapper or bounded filler differs")
    checked((NOTICE_CLEAR_THROW_ADDR + 4, "bl", NOTICE_CLEAR_RELATIONS_ADDR)
            in packaged_thumb_calls(tail, NOTICE_CLEAR_THROW_ADDR,
                                    NOTICE_CLEAR_THROW_ADDR, NOTICE_CLEAR_THROW_SIZE),
            "Wild notice clear wrapper lost its direct relations call")


def notice_tail_controls(wrapper, target, private, linked_wrapper):
    count = 0
    for index, current in enumerate((wrapper, target)):
        for bad in (None, (current[0] & ~1, *current[1:]),
                    (current[0] - 4, *current[1:]),
                    (current[0], current[1] + 2, *current[2:]),
                    (current[0], current[1], "OBJECT", current[3]),
                    (current[0], current[1], "FUNC", "ABS"),
                    (current[0], current[1], "FUNC", "UND")):
            try:
                notice_tail_contract(bad if index == 0 else wrapper,
                    bad if index == 1 else target, private, linked_wrapper)
            except ValueError:
                count += 1
                continue
            raise AssertionError("wrong Notice wrapper/relation typed owner passed")
    # Equal copies must still preserve Prepared88/u16 reads, Blob94 literals,
    # the exact relocated wrapper and every byte of its fixed reserve.
    for offset in (0, 0xA, 0xB0, 0xEC, 0x11C, 0x150, 0x154,
                   NOTICE_PHYSICAL_SIZE, NOTICE_PHYSICAL_SIZE + 4, NOTICE_CALLERS_SIZE - 1):
        changed = bytearray(private)
        changed[offset] ^= 1
        tail = bytes(changed[NOTICE_PHYSICAL_SIZE:NOTICE_PHYSICAL_SIZE + NOTICE_CLEAR_THROW_SIZE])
        try:
            notice_tail_contract(wrapper, target, bytes(changed), tail)
        except ValueError:
            count += 1
            continue
        raise AssertionError("wrong equal-copy Notice body/wrapper/filler passed")
    print(f"PASS {count} exact Notice owner/body rejection controls")


def binding_contract(hosted, imported, address, capacity):
    checked(hosted is not None and hosted[0] == address | 1
            and 0 < hosted[1] <= capacity and hosted[2] == "FUNC"
            and hosted[3] not in ("ABS", "UND"), "hosted Thumb function differs")
    checked(imported == (address | 1, 0, "FUNC", "ABS"),
            "caller lacks the exact typed Thumb import")


def call_contract(linked, packaged, address, target):
    body_contract(linked, packaged)
    calls = [call for call in packaged_thumb_calls(linked, address, address, len(linked))
             if call[2] == target]
    checked(len(calls) == 1 and calls[0][1] == "bl",
            "caller lacks one direct Thumb BL to the hosted function")


def route_base_y_contract(hosted, ops, private):
    checked(hosted is not None and hosted[:3] == (ROUTE_BASE_Y | 1, 28, "FUNC")
            and hosted[3] not in ("ABS", "UND"),
            "private Wild route support mode/extent differs")
    checked(len(ops) == 84 and struct.unpack_from("<HH", ops) == (3, 84)
            and struct.unpack_from("<I", ops, 16)[0] == ROUTE_BASE_Y | 1,
            "Wild route ops lacks the exact typed support callback")
    # The unchanged seven-argument Thumb adapter dispatches Runtime 18 slot 4
    # (entry +24); the complete native body includes its entry literal.
    checked(private == bytes.fromhex(
        "1fb5089c0294079c0194069c0094024ca469a04704b010bd00c83b02") + bytes(4),
        "private Wild route support body/padding or Runtime slot differs")
    checked(packaged_thumb_calls(private[:28], ROUTE_BASE_Y, ROUTE_BASE_Y, 28)
            == [(ROUTE_BASE_Y + 0x12, "blx_reg", 4)],
            "private Wild route support indirect dispatch differs")


def appearance_release_contract(hosted, private, hp_linked, hp_output, hp_package):
    checked(hosted is not None and hosted[:3] == (APPEARANCE_RELEASE | 1, 124, "FUNC")
            and hosted[3] not in ("ABS", "UND"),
            "private appearance release mode/extent differs")
    begin = APPEARANCE_RELEASE - 0x01FFA580
    end = APPEARANCE_RELEASE_LIMIT - 0x01FFA580
    checked(len(hp_linked) == 0x5A80
            and hp_linked[begin:end] == b"\xff" * (end - begin)
            and len(private) == end - begin
            and private[124:] == bytes(end - begin - 124),
            "private appearance release overlaps HP code or exceeds its reserve")
    expected = hp_linked[:begin] + private + hp_linked[end:]
    body_contract(expected, hp_output)
    body_contract(expected, hp_package)



def query_packed_caller_contract(bindings, linked, packaged):
    checked(bindings.get(PROFILE_PACKED) == (PROFILE_PACKED_ADDR | 1, 0, "FUNC", "ABS"),
            "resolver lacks the exact private packed Thumb import")
    caller = bindings.get("BehaviorResolver_ApplyRecorded")
    checked(caller is not None and caller[:3] == (0x2089fe1, 380, "FUNC")
            and caller[3] not in ("ABS", "UND"), "profile merge Query owner differs")
    body_contract(linked, packaged)
    checked(len(linked) == 380 and hashlib.sha256(linked).hexdigest()
            == "a433fbfc55d90f5c317374d236c51187ddfc7d98218f95c034939503b56a06ba"
            and linked[0xCA:0xCE] == bytes.fromhex("2a4b9847")
            and struct.unpack_from("<I", linked, 0x174)[0] == PROFILE_PACKED_ADDR | 1
            and packaged_thumb_calls(linked, 0x2089fe0, 0x2089fe0, 380) == [
                (0x208a03e, "bl", 0x2089810),
                (0x208a04c, "bl", 0x2089810),
                (0x208a076, "bl", 0x2089810),
                (0x208a0ac, "blx_reg", 3),
                (0x208a124, "bl", 0x2089ec0),
                (0x208a136, "bl", 0x20897c8)],
            "profile merge exact Query body/packed dispatch differs")


def query_packed_caller_controls(bindings, linked, packaged):
    count = 0
    for name in (PROFILE_PACKED, "BehaviorResolver_ApplyRecorded"):
        current = bindings[name]
        for bad in (None, (current[0] & ~1, *current[1:]),
                    (current[0] + 2, *current[1:]),
                    (current[0], current[1] + 2, *current[2:]),
                    (current[0], current[1], "OBJECT", current[3]),
                    (current[0], current[1], "FUNC", "UND")):
            changed = dict(bindings)
            changed[name] = bad
            try:
                query_packed_caller_contract(changed, linked, packaged)
            except ValueError:
                count += 1
                continue
            raise AssertionError("wrong Query merge typed import/owner passed")
    changed = dict(bindings)
    current = changed["BehaviorResolver_ApplyRecorded"]
    changed["BehaviorResolver_ApplyRecorded"] = (*current[:3], "ABS")
    try:
        query_packed_caller_contract(changed, linked, packaged)
    except ValueError:
        count += 1
    else:
        raise AssertionError("absolute Query merge caller passed")
    for offset in (0, 0xCA, 0xCC, 0x174, len(linked) - 1):
        changed = bytearray(linked)
        changed[offset] ^= 1
        for left, right in ((bytes(changed), bytes(changed)), (linked, bytes(changed))):
            try:
                query_packed_caller_contract(bindings, left, right)
            except ValueError:
                count += 1
                continue
            raise AssertionError("wrong Query merge equal-copy/package body passed")
    print(f"PASS {count} exact Query merge owner/body rejection controls")


def verify_profile_skid_helpers(build, overlays, rom):
    owner = build / "player_health_overlay_linked.o"
    names = (PROFILE_PACKED, PROFILE_SKID, "OverworldActorWalkPolicy_ReduceInput")
    symbols = elf_helper_bindings(owner, names)
    for name, address, size in ((PROFILE_PACKED, PROFILE_PACKED_ADDR, PROFILE_PACKED_SIZE),
                                (PROFILE_SKID, PROFILE_SKID_ADDR, PROFILE_SKID_SIZE)):
        hosted = symbols.get(name)
        checked(hosted is not None and hosted[:3] == (address | 1, size, "FUNC")
                and hosted[3] not in ("ABS", "UND"),
                "private profile helper mode/extent differs")
        code = elf_bytes_at(owner, address, size)
        body_contract(code, overlay_span(overlays, 161, address, size))
        # Both helpers are pure: no other service owns their work or state.
        checked(not packaged_thumb_calls(code, address, address, size),
                "private profile helper unexpectedly calls another owner")
    # The same Resolver now runs in the authenticated, relocatable Query image.
    # Bind the complete candidate member before checking its one packed merge.
    if __package__:
        from .verify_overworld_query_code_addon import packer
        from .verify_pokemon_move_history import checked_slice, nitrofs_file, narc_members
    else:
        from verify_overworld_query_code_addon import packer
        from verify_pokemon_move_history import checked_slice, nitrofs_file, narc_members
    directory = build / "overworld_query_code_addon"
    query = directory / "image.elf"
    blob, receipt = packer().package(query.read_bytes())
    fnt_offset, fnt_size, fat_offset, fat_size = struct.unpack(
        "<4I", checked_slice(rom, 0x40, 16, "NitroFS header"))
    fnt = checked_slice(rom, fnt_offset, fnt_size, "FNT")
    fat = checked_slice(rom, fat_offset, fat_size, "FAT")
    _file_id, archive = nitrofs_file(rom, fnt, fat, "a/0/2/8")
    members = narc_members(archive, "final ROM a/0/2/8")
    checked(len(members) == 22 and members[21] == blob
            == (directory / "query.bin").read_bytes()
            == (build / "a028/9_21").read_bytes(),
            "profile merge complete Query member differs from linked/generated/staged bytes")
    bindings = elf_helper_bindings(query, (PROFILE_PACKED, "BehaviorResolver_ApplyRecorded"))
    code = elf_bytes_at(query, 0x2089fe0, 380)
    offset = 0x2089fe0 - 0x02080000
    checked(offset + len(code) <= receipt["imageBytes"],
            "profile merge exceeds its Query image")
    query_packed_caller_contract(bindings, code, members[21][64 + offset:64 + offset + len(code)])
    query_packed_caller_controls(bindings, code, members[21][64 + offset:64 + offset + len(code)])
    caller = symbols.get("OverworldActorWalkPolicy_ReduceInput")
    checked(caller is not None and caller[:3] == (0x01FFF041, 726, "FUNC")
            and caller[3] not in ("ABS", "UND"), "profile skid INPUT owner differs")
    code = elf_bytes_at(owner, caller[0] & ~1, caller[1])
    body_contract(code, overlay_span(overlays, 161, caller[0] & ~1, caller[1]))
    calls = [call for call in packaged_thumb_calls(code, caller[0] & ~1,
        caller[0] & ~1, caller[1]) if call[2] == PROFILE_SKID_ADDR]
    checked(len(calls) == 2 and all(call[1] == "bl" for call in calls),
            "turn and stop lack two direct calls to the one profile skid picker")

def verify_appearance_release(build, overlays):
    capsule = build / "overworld_field_capsule_linked.o"
    health = build / "player_health_overlay_linked.o"
    names = ("Appearance_Release", "Appearance_CompleteUpload",
             "Appearance_CurrentDraw", "Appearance_ApplyMaterial",
             "OverworldActorAppearance_Update", "OverworldActorAppearance_Forget",
             "OverworldActorAppearance_Reset")
    symbols = elf_helper_bindings(capsule, names)
    private = section_bytes(capsule, ".overworld_appearance_release",
        APPEARANCE_RELEASE, APPEARANCE_RELEASE_LIMIT - APPEARANCE_RELEASE)
    appearance_release_contract(symbols.get(names[0]), private,
        elf_bytes_at(health, 0x01FFA580, 0x5A80),
        (build / "output_player_health_overlay.bin").read_bytes(),
        overlay_span(overlays, 161, 0x01FFA580, 0x5A80))
    # Release remains synchronous Field-owned code. It may call only the two
    # current Field leaves and the unchanged stock palette/free dispatches.
    for name in names[1:]:
        current = symbols.get(name)
        checked(current is not None and current[0] & 1 and current[1] > 0
                and current[2] == "FUNC" and current[3] not in ("ABS", "UND")
                and BASE + 28 <= (current[0] & ~1) < ROUTE_BASE_Y,
                "appearance release caller/callee is outside its Field owner")
    calls = packaged_thumb_calls(private[:124], APPEARANCE_RELEASE,
                                 APPEARANCE_RELEASE, 124)
    checked([call[1] for call in calls] == ["bl", "bl", "blx_reg", "blx_reg"]
            and [call[2] for call in calls[:2]] == [
                symbols["Appearance_CompleteUpload"][0] & ~1,
                symbols["Appearance_CurrentDraw"][0] & ~1]
            and private[:124].count(struct.pack("<I", 0x02110930)) == 1
            and private[:124].count(struct.pack("<I", 0x0201AB0D)) == 1
            and private[:124].count(struct.pack("<I",
                symbols["Appearance_ApplyMaterial"][0])) == 1,
            "appearance release lost its exact Field/stock Thumb dispatch")
    for name, count in (("OverworldActorAppearance_Update", 2),
                        ("OverworldActorAppearance_Forget", 1),
                        ("OverworldActorAppearance_Reset", 1)):
        start, size = symbols[name][:2]
        start &= ~1
        code = elf_bytes_at(capsule, start, size)
        body_contract(code, overlay_span(overlays, 1, start, size))
        calls = [call for call in packaged_thumb_calls(code, start, start, size)
                 if call[2] == APPEARANCE_RELEASE]
        checked(len(calls) == count and all(call[1] == "bl" for call in calls),
                "appearance release caller lacks its exact synchronous Thumb BL")


def appearance_rest_copy_contract(copied, source, actor_linked, actor_package,
                                  caller, caller_linked, caller_package):
    checked(copied is not None and copied[:3] ==
            (REST_POLICY_ADDRESS | 1, REST_POLICY_SIZE, "FUNC")
            and copied[3] not in ("ABS", "UND"),
            "private Rest tint copy lacks its exact typed Actor owner")
    body_contract(source, actor_linked)
    body_contract(source, actor_package)
    checked(caller is not None and caller[0] & 1 and caller[1] == 576
            and caller[2] == "FUNC" and caller[3] not in ("ABS", "UND")
            and BASE + 28 <= (caller[0] & ~1) < ROUTE_BASE_Y,
            "Rest tint caller is outside its current Field owner")
    call_contract(caller_linked, caller_package, caller[0] & ~1,
                  REST_POLICY_ADDRESS)


def verify_appearance_rest_copy(build, overlays):
    capsule = build / "overworld_field_capsule_linked.o"
    actor = build / "overworld_actor_system_overlay_linked.o"
    source = rest_policy_body(build)
    symbols = elf_helper_bindings(capsule, (
        "OverworldActorAppearance_RefreshNative", "OverworldAppearancePolicy_ApplicableMask"))
    caller = symbols.get("OverworldActorAppearance_RefreshNative")
    checked(caller is not None, "Rest tint current Field caller is absent")
    checked(overlays[158][0][:4] == (158, 0x023B65C0, 0x3BB0, 0x988)
            and overlays[158][0][7] == 0,
            "Rest tint boot Actor owner metadata changed")
    start, size = caller[0] & ~1, caller[1]
    appearance_rest_copy_contract(
        elf_helper_bindings(actor, (REST_POLICY_COPY,)).get(REST_POLICY_COPY), source,
        elf_bytes_at(actor, REST_POLICY_ADDRESS, REST_POLICY_SIZE),
        overlay_span(overlays, 158, REST_POLICY_ADDRESS, REST_POLICY_SIZE), caller,
        elf_bytes_at(capsule, start, size), overlay_span(overlays, 1, start, size))
    applicable = symbols.get("OverworldAppearancePolicy_ApplicableMask")
    checked(applicable is not None, "Rest tint current Field role read is absent")
    body_contract(elf_bytes_at(capsule, REST_APPLICABLE_ADDRESS, REST_APPLICABLE_SIZE),
        overlay_span(overlays, 1, REST_APPLICABLE_ADDRESS, REST_APPLICABLE_SIZE))
    appearance_rest_copy_controls(source, caller,
        elf_bytes_at(capsule, start, size))


def appearance_rest_copy_controls(source, caller, code):
    """Exact native source/copy/call controls, without another policy model."""
    hosted = (REST_POLICY_ADDRESS | 1, REST_POLICY_SIZE, "FUNC", "1")
    applicable = (REST_APPLICABLE_ADDRESS | 1, REST_APPLICABLE_SIZE, "FUNC", "1")
    copied = (REST_POLICY_ADDRESS | 1, REST_POLICY_SIZE, "FUNC", "1")
    rest_policy_contract(hosted, applicable, source)
    appearance_rest_copy_contract(copied, source, source, source, caller, code, code)

    def rejected(operation):
        try:
            operation()
        except ValueError:
            return
        raise AssertionError("wrong Rest tint source/copy/call control passed")

    for owner in ((REST_POLICY_ADDRESS, REST_POLICY_SIZE, "FUNC", "1"),
                  (REST_POLICY_ADDRESS | 1, REST_POLICY_SIZE - 2, "FUNC", "1"),
                  (REST_POLICY_ADDRESS | 1, REST_POLICY_SIZE, "FUNC", "ABS")):
        rejected(lambda: rest_policy_contract(owner, applicable, source))
        rejected(lambda: appearance_rest_copy_contract(owner, source, source,
            source, caller, code, code))
    for leaf in ((REST_APPLICABLE_ADDRESS, REST_APPLICABLE_SIZE, "FUNC", "1"),
                 (REST_APPLICABLE_ADDRESS | 1, REST_APPLICABLE_SIZE, "FUNC", "ABS")):
        rejected(lambda: rest_policy_contract(hosted, leaf, source))
    for bad in (source[:-2], bytes([source[0] ^ 1]) + source[1:],
                source[:0x106] + bytes(4) + source[0x10A:]):
        rejected(lambda: rest_policy_contract(hosted, applicable, bad))
        rejected(lambda: appearance_rest_copy_contract(copied, source, bad,
            source, caller, code, code))
        rejected(lambda: appearance_rest_copy_contract(copied, source, source,
            bad, caller, code, code))
    rejected(lambda: appearance_rest_copy_contract(copied, source, source,
        source, (caller[0] & ~1, *caller[1:]), code, code))
    calls = packaged_thumb_calls(code, caller[0] & ~1, caller[0] & ~1, len(code))
    call = next(c for c in calls if c[2] == REST_POLICY_ADDRESS)
    offset = call[0] - (caller[0] & ~1)
    missing = code[:offset] + bytes(4) + code[offset + 4:]
    rejected(lambda: appearance_rest_copy_contract(copied, source, source,
        source, caller, missing, missing))
    rejected(lambda: appearance_rest_copy_contract(copied, source, source,
        source, caller, code, missing))


def package_controls():
    land_model_task_controls()
    lease_host = (HOP_LEASE_ADDR | 1, HOP_LEASE_SIZE, "FUNC", "1")
    hop_lease_contract(lease_host, HOP_LEASE_CODE, HOP_LEASE_CODE)
    for wrong_host in (None, (HOP_LEASE_ADDR, 80, "FUNC", "1"),
                       (HOP_LEASE_ADDR | 1, 78, "FUNC", "1"),
                       (HOP_LEASE_ADDR | 1, 80, "FUNC", "ABS")):
        try:
            hop_lease_contract(wrong_host, HOP_LEASE_CODE, HOP_LEASE_CODE)
        except ValueError:
            continue
        raise AssertionError("wrong Hop lease owner/mode/extent passed")
    for offset in (12, 18, 26, 34, 48, 56, 60, 64, 68, 72, 76):
        wrong = bytearray(HOP_LEASE_CODE)
        wrong[offset] ^= 1
        try:
            hop_lease_contract(lease_host, bytes(wrong), bytes(wrong))
        except ValueError:
            continue
        raise AssertionError("wrong Hop lease lifetime/owner/acquire guard passed")
    cargo_host = (CARGO_OBSERVATION | 1, CARGO_OBSERVATION_SIZE, "FUNC", "1")
    frame_import = (0x023B6931, 0, "FUNC", "ABS")
    bubble_host = (SHOW_BUBBLE_ADDR | 1, SHOW_BUBBLE_SIZE, "FUNC", "1")
    cargo_code = CARGO_OBSERVATION_CODE + bytes(
        SHOW_BUBBLE_ADDR - CARGO_OBSERVATION - CARGO_OBSERVATION_SIZE) + SHOW_BUBBLE_CODE
    cargo_observation_contract(cargo_host, frame_import, cargo_code, cargo_code, bubble_host, SHOW_BUBBLE_IMPORT)
    for hosted, imported, body, packaged in (
        ((CARGO_OBSERVATION, 176, "FUNC", "1"), frame_import, cargo_code, cargo_code),
        ((CARGO_OBSERVATION | 1, 178, "FUNC", "1"), frame_import, cargo_code, cargo_code),
        (cargo_host, (0x023B6930, 0, "FUNC", "ABS"), cargo_code, cargo_code),
        (cargo_host, frame_import, bytes(CARGO_OBSERVATION_CAPACITY), bytes(CARGO_OBSERVATION_CAPACITY)),
        (cargo_host, frame_import, cargo_code[:-1] + bytes([cargo_code[-1] ^ 1]),
         cargo_code[:-1] + bytes([cargo_code[-1] ^ 1])),
        (cargo_host, frame_import, cargo_code, cargo_code[:4] + b"\1" + cargo_code[5:]),
    ):
        try:
            cargo_observation_contract(hosted, imported, body, packaged, bubble_host, SHOW_BUBBLE_IMPORT)
        except ValueError:
            continue
        raise AssertionError("wrong Cargo observation mode/extent/frame/body/padding passed")
    # Mutate both linked and packaged copies: equality alone must not grant a
    # missing or altered valid-frame/mode guard acceptance.
    for offset, length in ((0x62, 10), (0x66, 2), (0xA8, 4),
                           (0x0E, 24), (0x1C, 2), (0xA4, 4),
                           (0x6C, 8), (0x9C, 4), (0xB4, 4), (0, 2)):
        wrong = cargo_code[:offset] + bytes(length) + cargo_code[offset + length:]
        try:
            cargo_observation_contract(cargo_host, frame_import, wrong, wrong,
                                       bubble_host, SHOW_BUBBLE_IMPORT)
        except ValueError:
            continue
        raise AssertionError("wrong current Cargo Frame/mode guard or native body passed")
    adapter_host = (ACTOR_EVALUATE_ADDR | 1, ACTOR_EVALUATE_SIZE, "FUNC", "1")
    frame_host = (FRAME_ADDR | 1, FRAME_SIZE, "FUNC", "1")
    subject_import = (SUBJECT | 1, 0, "FUNC", "ABS")
    site = ACTOR_EVALUATE_ADDR + 0x84
    delta = FRAME_ADDR - site - 4
    frame_call = struct.pack("<HH", 0xF000 | ((delta >> 12) & 0x7FF),
                            0xF800 | ((delta >> 1) & 0x7FF))
    adapter_code = bytearray(bytes(0x84) + frame_call + bytes(ACTOR_EVALUATE_SIZE - 0x88))
    subject_site = ACTOR_EVALUATE_ADDR + 0x166
    subject_delta = SUBJECT - subject_site - 4
    subject_call = struct.pack("<HH", 0xF000 | ((subject_delta >> 12) & 0x7FF),
                               0xF800 | ((subject_delta >> 1) & 0x7FF))
    adapter_code[0x166:0x16A] = subject_call
    adapter_code[0xA4:0xC2] = ACTOR_ACQUIRE_OWNER_CODE
    adapter_code[0x338:0x33C] = ACTOR_ACQUIRE_SERVICE_WORD
    adapter_code = bytes(adapter_code)
    cargo_frame_owner_contract(adapter_host, frame_host, subject_import,
                               adapter_code, adapter_code)
    for owner, callee in (
        (None, frame_host),
        ((ACTOR_EVALUATE_ADDR, ACTOR_EVALUATE_SIZE, "FUNC", "1"), frame_host),
        ((ACTOR_EVALUATE_ADDR + 3, ACTOR_EVALUATE_SIZE, "FUNC", "1"), frame_host),
        ((ACTOR_EVALUATE_ADDR | 1, ACTOR_EVALUATE_SIZE - 2, "FUNC", "1"), frame_host),
        ((ACTOR_EVALUATE_ADDR | 1, ACTOR_EVALUATE_SIZE, "FUNC", "ABS"), frame_host),
        ((ACTOR_EVALUATE_ADDR | 1, ACTOR_EVALUATE_SIZE, "FUNC", "UND"), frame_host),
        (adapter_host, None),
        (adapter_host, (FRAME_ADDR, FRAME_SIZE, "FUNC", "1")),
        (adapter_host, (FRAME_ADDR + 3, FRAME_SIZE, "FUNC", "1")),
        (adapter_host, (FRAME_ADDR | 1, FRAME_SIZE - 2, "FUNC", "1")),
        (adapter_host, (FRAME_ADDR | 1, FRAME_SIZE, "FUNC", "ABS")),
        (adapter_host, (FRAME_ADDR | 1, FRAME_SIZE, "FUNC", "UND")),
    ):
        try:
            cargo_frame_owner_contract(owner, callee, subject_import,
                                       adapter_code, adapter_code)
        except ValueError:
            continue
        raise AssertionError("wrong Cargo Frame Adapter/callee mode/extent/owner passed")
    for bad_subject in (None, (SUBJECT, 0, "FUNC", "ABS"),
                        (SUBJECT | 1, 0, "NOTYPE", "ABS"),
                        (SUBJECT | 1, 0, "FUNC", "UND")):
        try:
            cargo_frame_owner_contract(adapter_host, frame_host, bad_subject,
                                       adapter_code, adapter_code)
        except ValueError:
            continue
        raise AssertionError("wrong Cargo Subject import passed")
    later_delta = FRAME_ADDR - site - 8
    later_call = struct.pack("<HH", 0xF000 | ((later_delta >> 12) & 0x7FF),
                            0xF800 | ((later_delta >> 1) & 0x7FF))
    moved_call = adapter_code[:0x84] + bytes(4) + later_call + adapter_code[0x8C:]
    duplicate_call = adapter_code[:0x88] + later_call + adapter_code[0x8C:]
    non_thumb_call = adapter_code[:0x86] + struct.pack("<H", 0xE800 | ((delta >> 1) & 0x7FF)) + adapter_code[0x88:]
    for linked, packaged in (
        (bytes(ACTOR_EVALUATE_SIZE), bytes(ACTOR_EVALUATE_SIZE)),
        (moved_call, moved_call), (duplicate_call, duplicate_call),
        (non_thumb_call, non_thumb_call),
        (adapter_code[:-2], adapter_code[:-2]),
        (adapter_code, bytes(ACTOR_EVALUATE_SIZE)),
        (adapter_code[:0xAC] + bytes(2) + adapter_code[0xAE:],
         adapter_code[:0xAC] + bytes(2) + adapter_code[0xAE:]),
        (adapter_code[:0xB8] + bytes(2) + adapter_code[0xBA:],
         adapter_code[:0xB8] + bytes(2) + adapter_code[0xBA:]),
        (adapter_code[:0xBE] + bytes(2) + adapter_code[0xC0:],
         adapter_code[:0xBE] + bytes(2) + adapter_code[0xC0:]),
        (adapter_code[:0x338] + bytes(4) + adapter_code[0x33C:],
         adapter_code[:0x338] + bytes(4) + adapter_code[0x33C:]),
        (adapter_code[:0x166] + bytes(4) + adapter_code[0x16A:],
         adapter_code[:0x166] + bytes(4) + adapter_code[0x16A:]),
    ):
        try:
            cargo_frame_owner_contract(adapter_host, frame_host, subject_import,
                                       linked, packaged)
        except ValueError:
            continue
        raise AssertionError("wrong Cargo pre-observation Frame call/package body passed")
    for bubble, callee in (
        (None, SHOW_BUBBLE_IMPORT),
        ((SHOW_BUBBLE_ADDR, 16, "FUNC", "1"), SHOW_BUBBLE_IMPORT),
        ((SHOW_BUBBLE_ADDR | 1, 14, "FUNC", "1"), SHOW_BUBBLE_IMPORT),
        ((SHOW_BUBBLE_ADDR | 1, 16, "FUNC", "ABS"), SHOW_BUBBLE_IMPORT),
        ((SHOW_BUBBLE_ADDR | 1, 16, "FUNC", "UND"), SHOW_BUBBLE_IMPORT),
        (bubble_host, (0x02203A48, 0, "NOTYPE", "ABS")),
        (bubble_host, (0x02203A4B, 0, "NOTYPE", "ABS")),
    ):
        try:
            cargo_observation_contract(cargo_host, frame_import, cargo_code, cargo_code, bubble, callee)
        except ValueError:
            continue
        raise AssertionError("wrong private bubble mode/extent/stock callee passed")
    hosted = (DELIVERY | 1, 112, "FUNC", "1")
    imported = (DELIVERY | 1, 0, "FUNC", "ABS")
    binding_contract(hosted, imported, DELIVERY, LIMIT - DELIVERY)
    for bad_hosted, bad_imported in (
        (None, imported), ((DELIVERY, 112, "FUNC", "1"), imported),
        ((DELIVERY | 1, 205, "FUNC", "1"), imported),
        ((DELIVERY | 1, 112, "FUNC", "ABS"), imported),
        (hosted, (DELIVERY, 0, "FUNC", "ABS")),
        (hosted, (DELIVERY | 1, 0, "NOTYPE", "ABS")),
    ):
        try:
            binding_contract(bad_hosted, bad_imported, DELIVERY, LIMIT - DELIVERY)
        except ValueError:
            continue
        raise AssertionError("wrong mode/extent/import control passed")
    site = 0x023BC300
    delta = DELIVERY - site - 4
    code = struct.pack("<HH", 0xF000 | ((delta >> 12) & 0x7FF),
                       0xF800 | ((delta >> 1) & 0x7FF))
    next_delta = DELIVERY - site - 8
    second_call = struct.pack("<HH", 0xF000 | ((next_delta >> 12) & 0x7FF),
                              0xF800 | ((next_delta >> 1) & 0x7FF))
    call_contract(code, code, site, DELIVERY)
    for linked, packaged in ((code, bytes(4)), (bytes(4), bytes(4)),
                             (b"", b""), (code + second_call, code + second_call)):
        try:
            call_contract(linked, packaged, site, DELIVERY)
        except ValueError:
            continue
        raise AssertionError("wrong code/direct-call control passed")
    route = (ROUTE_BASE_Y | 1, 28, "FUNC", "1")
    ops = bytearray(84)
    struct.pack_into("<HH", ops, 0, 3, 84)
    struct.pack_into("<I", ops, 16, ROUTE_BASE_Y | 1)
    private = bytes.fromhex(
        "1fb5089c0294079c0194069c0094024ca469a04704b010bd00c83b02") + bytes(4)
    route_base_y_contract(route, ops, private)
    wrong_ops = bytearray(ops)
    struct.pack_into("<I", wrong_ops, 16, ROUTE_BASE_Y)
    for hosted, table, body in (
        ((ROUTE_BASE_Y, 28, "FUNC", "1"), ops, private),
        ((ROUTE_BASE_Y | 1, 33, "FUNC", "1"), ops, private),
        ((ROUTE_BASE_Y | 1, 28, "FUNC", "ABS"), ops, private),
        (route, wrong_ops, private), (route, ops[:80], private),
        (route, struct.pack("<HH", 2, 76) + bytes(72), private),
        (route, ops, private[:28]),
        (route, ops, private[:16] + bytes(2) + private[18:]),
        (route, ops, private[:-1] + b"\x01"),
    ):
        try:
            route_base_y_contract(hosted, table, body)
        except ValueError:
            continue
        raise AssertionError("wrong route mode/extent/ops/body/padding control passed")
    release = (APPEARANCE_RELEASE | 1, 124, "FUNC", "1")
    begin, end = APPEARANCE_RELEASE - 0x01FFA580, APPEARANCE_RELEASE_LIMIT - 0x01FFA580
    hp = bytes(begin) + b"\xff" * (end - begin) + bytes(0x5A80 - end)
    helper = bytes(end - begin)
    merged = hp[:begin] + helper + hp[end:]
    appearance_release_contract(release, helper, hp, merged, merged)
    for host, native, original, output, package in (
        ((APPEARANCE_RELEASE, 124, "FUNC", "1"), helper, hp, merged, merged),
        ((APPEARANCE_RELEASE | 1, 126, "FUNC", "1"), helper, hp, merged, merged),
        ((APPEARANCE_RELEASE | 1, 124, "FUNC", "ABS"), helper, hp, merged, merged),
        (release, helper, hp[:begin] + b"\0" + hp[begin + 1:], merged, merged),
        (release, helper, hp, b"\1" + merged[1:], merged),
        (release, helper, hp, merged, merged[:begin] + b"\1" + merged[begin + 1:]),
    ):
        try:
            appearance_release_contract(host, native, original, output, package)
        except ValueError:
            continue
        raise AssertionError("wrong appearance release owner/body/HP extent control passed")
    print("PASS field capsule mode, extent, bytes and direct-call rejection controls")


def rom_overlays(rom):
    checked(len(rom) >= 0x60, "ROM header is absent")
    fat, fat_size, y9, y9_size = struct.unpack_from("<4I", rom, 0x48)
    checked(fat_size % 8 == 0 and fat + fat_size <= len(rom)
            and y9_size % 32 == 0 and y9 + y9_size <= len(rom), "ROM tables differ")
    result = {}
    for offset in range(y9, y9 + y9_size, 32):
        row = struct.unpack_from("<8I", rom, offset)
        checked(row[0] not in result and row[6] < fat_size // 8,
                "overlay identity/file index differs")
        start, end = struct.unpack_from("<II", rom, fat + row[6] * 8)
        checked(start <= end <= len(rom), "overlay file bounds differ")
        result[row[0]] = row, rom[start:end]
    return result


def overlay_span(overlays, number, address, size):
    checked(number in overlays, "owning overlay is missing")
    row, image = overlays[number]
    offset = address - row[1]
    checked(not row[7] & 0x01000000 and len(image) == row[2]
            and 0 <= offset <= len(image) - size, "code exceeds its owning overlay")
    return image[offset:offset + size]


LAND_MODEL_TASK = 0x021F6620
LAND_MODEL_TASK_SIZE = 0x14C
LAND_MODEL_READ_SITES = (0x021F6654, 0x021F6686)
LAND_MODEL_STOCK_SHA256 = "71ece23494eb8e4f3395d3d39b2586b738b97482e4d5724c51a4251996bf820e"


def land_model_task_contract(body):
    checked(len(body) == LAND_MODEL_TASK_SIZE, "Land model task extent differs")
    normalized = bytearray(body)
    for site in LAND_MODEL_READ_SITES:
        offset = site - LAND_MODEL_TASK
        checked(struct.unpack_from("<H", body, offset)[0] == 0x2001,
                "Land model read quantum is not 4 KB")
        struct.pack_into("<H", normalized, offset, 0x200E)
    # The complete original task retains the same offset arithmetic, phase
    # table, sequential calls, ready flag, cancellation and cleanup instructions.
    checked(hashlib.sha256(normalized).hexdigest() == LAND_MODEL_STOCK_SHA256,
            "Land model progress/ready/cancel/native task body differs")


def land_model_task_controls():
    stock = (ROOT / "base/overlay/overlay_0001.bin").read_bytes()
    start = LAND_MODEL_TASK - 0x021E5900
    body = bytearray(stock[start:start + LAND_MODEL_TASK_SIZE])
    for site in LAND_MODEL_READ_SITES:
        offset = site - LAND_MODEL_TASK
        checked(struct.unpack_from("<H", body, offset)[0] in (0x200E, 0x2001),
                "Land model control input quantum differs")
        struct.pack_into("<H", body, offset, 0x2001)
    land_model_task_contract(body)
    for site in (0x021F6654, 0x021F6686, 0x021F6628, 0x021F667A,
                 0x021F66B0, 0x021F6750, 0x021F6760):
        changed = bytearray(body)
        changed[site - LAND_MODEL_TASK] ^= 1
        try:
            land_model_task_contract(changed)
        except ValueError:
            continue
        raise AssertionError("Land model wrong quantum/progress/ready/cancel body passed")
    try:
        land_model_task_contract(body[:-2])
    except ValueError:
        return
    raise AssertionError("Land model truncated body passed")


def verify_stock_field_exit(overlays):
    # The stock template at 02206378 is named in vanilla
    # src/field/overlay_01_021E66E4.c. Only its Exit pointer changes. The full
    # original Exit, including its literal pool, ends at the next function.
    checked(overlay_span(overlays, 1, 0x02206378, 16)
            == struct.pack("<4I", 0x021E5925, 0x021E5BE5,
                           APPEARANCE_EXIT | 1, 0xFFFFFFFF),
            "stock Field template init/exec/Exit/overlay identity differs")
    checked(hashlib.sha256(overlay_span(overlays, 1, 0x021E5C24, 0x294)).hexdigest()
            == "0ff209e9c9c846fbddfc89e4eb61b84876dcf8293ebe2cc557d432f73b2d4ee6",
            "complete original stock Field Exit changed")


def verify_wild_walk_output(build, linked, overlays):
    owner = build / "overworld_wild_spawns_overlay_linked.o"
    expected = ("OverworldWildSpawns_SetObjectFacing", "OverworldActor_PlayStompSound",
                "OverworldWildSpawns_PublishWalkCrash",
                "OverworldWildSpawns_PlayMovementCrashFeedback",
                "OverworldWildSpawns_StartMovementCrashShake")
    bindings = elf_helper_bindings(owner, (APPLY_WALK,
        "OverworldWildSpawns_ExecuteWalkPolicy", *expected))
    function = bindings.get(APPLY_WALK)
    checked(function is not None and function[:3] == (WALK_OUTPUT | 1, 192, "FUNC")
            and function[3] not in ("ABS", "UND"),
            "private Wild walk output mode/extent differs")
    private = section_bytes(owner, ".overworld_field_wild_walk_output", WALK_OUTPUT, 0x100)
    body_contract(private, linked[WALK_OUTPUT - BASE:WALK_OUTPUT - BASE + 0x100])
    body_contract(private, (build / "overworld_field_wild_walk.bin").read_bytes())
    caller = bindings.get("OverworldWildSpawns_ExecuteWalkPolicy")
    checked(caller is not None and caller[2] == "FUNC" and caller[0] & 1
            and caller[1] > 0 and caller[3] not in ("ABS", "UND"),
            "private Wild walk caller is not hosted Thumb code")
    start, size = caller[0] & ~1, caller[1]
    code = elf_bytes_at(owner, start, size)
    body_contract(code, overlay_span(overlays, 149, start, size))
    calls = [call for call in packaged_thumb_calls(code, start, start, size)
             if call[2] == WALK_OUTPUT]
    checked(len(calls) == 3 and all(kind == "bl" for _, kind, _ in calls),
            "private Wild walk output lacks three direct Thumb calls")
    outgoing = packaged_thumb_calls(private[:192], WALK_OUTPUT, WALK_OUTPUT, 192)
    checked(len(outgoing) == 6 and outgoing[1] == (WALK_OUTPUT + 0x5A, "blx_reg", 1),
            "private Wild walk runtime callback inventory differs")
    outgoing = outgoing[:1] + outgoing[2:]
    for (_, kind, target), name in zip(outgoing, expected):
        overlay_id = 149
        callee = owner
        if name == "OverworldActor_PlayStompSound":
            overlay_id, callee = 158, build / "overworld_actor_system_overlay_linked.o"
            binding = elf_helper_bindings(callee, (name,)).get(name)
        else:
            binding = bindings.get(name)
            if name in RESIDENT_WALK_LEAVES:
                overlay_id = 161
                checked(binding is not None and binding[:3] == RESIDENT_WALK_LEAVES[name],
                        "resident Wild Walk leaf moved or changed extent")
        checked(binding is not None and binding[2] == "FUNC" and binding[0] & 1
                and binding[1] > 0 and binding[3] not in ("ABS", "UND")
                and kind == "bl" and target == binding[0] & ~1,
                "private Wild walk calls an untyped target or mode veneer")
        body_contract(elf_bytes_at(callee, target, binding[1]),
                      overlay_span(overlays, overlay_id, target, binding[1]))
    checked(private[188:192] == struct.pack("<I", 0x023BC800),
            "private Wild walk runtime entry literal differs")


def verify_wild_route_base_y(build, linked, overlays):
    owner = build / "overworld_wild_spawns_overlay_linked.o"
    names = (RESOLVE_BASE_Y, "sOverworldWildRouteOps")
    bindings = elf_helper_bindings(owner, names)
    table = bindings.get(names[1])
    checked(table is not None and table[1:3] == (84, "OBJECT")
            and table[3] not in ("ABS", "UND"),
            "Wild route ops is not a hosted typed table")
    ops = elf_bytes_at(owner, table[0], table[1])
    body_contract(ops, overlay_span(overlays, 149, table[0], table[1]))
    private = section_bytes(owner, ".overworld_field_wild_route_base_y",
                            ROUTE_BASE_Y, SUBJECT - ROUTE_BASE_Y)
    route_base_y_contract(bindings.get(RESOLVE_BASE_Y), ops, private)
    body_contract(private, linked[ROUTE_BASE_Y - BASE:SUBJECT - BASE])
    body_contract(private, (build / "overworld_field_wild_route_base_y.bin").read_bytes())
    body_contract(private, overlay_span(overlays, 1, ROUTE_BASE_Y, 32))
    runtime = build / "overworld_wild_runtime_overlay_linked.o"
    runtime_names = ("gOverworldWildRuntimeOverlayEntry", "OverworldWildRuntime_ResolveBaseYAt")
    symbols = elf_helper_bindings(runtime, runtime_names)
    entry, target = (symbols.get(name) for name in runtime_names)
    checked(entry is not None and entry[:3] == (0x023BC800, 52, "OBJECT")
            and entry[3] not in ("ABS", "UND") and target is not None
            and target[0] & 1 and target[1] > 0 and target[2] == "FUNC"
            and target[3] not in ("ABS", "UND"),
            "Wild runtime support callback is not hosted typed Thumb code")
    entry_bytes = elf_bytes_at(runtime, entry[0], entry[1])
    checked(struct.unpack_from("<IHH", entry_bytes) == (0x3152574F, 18, 52)
            and struct.unpack_from("<I", entry_bytes, 24)[0] == target[0],
            "Wild runtime identity or slot 4 support target differs")
    body_contract(entry_bytes, overlay_span(overlays, 156, entry[0], entry[1]))
    body_contract(elf_bytes_at(runtime, target[0] & ~1, target[1]),
                  overlay_span(overlays, 156, target[0] & ~1, target[1]))


def verify_walk_input_tuning(build, linked, overlays):
    owner = build / "player_health_overlay_linked.o"
    names = (TUNING, "OverworldActorWalkPolicy_ReduceInput",
             "OverworldActorWalkPolicy_ResetState")
    symbols = elf_helper_bindings(owner, names)
    helper, caller, reset = (symbols.get(name) for name in names)
    checked(helper is not None and helper[:3] == (WALK_TUNING | 1, 202, "FUNC")
            and helper[3] not in ("ABS", "UND"),
            "private Walk tuning mode/extent differs")
    checked(caller is not None and caller[:3] == (0x01FFF041, 726, "FUNC")
            and caller[3] not in ("ABS", "UND"),
            "resident Walk input entry/extent differs")
    checked(reset is not None and reset[:3] == (0x01FFF001, 40, "FUNC")
            and reset[3] not in ("ABS", "UND"),
            "resident Walk reset entry/extent differs")
    private = section_bytes(owner, ".overworld_field_walk_input_tuning",
                            WALK_TUNING, 0xD0)
    body_contract(private, linked[WALK_TUNING - BASE:WALK_TUNING - BASE + 0xD0])
    body_contract(private, (build / "overworld_field_walk_input_tuning.bin").read_bytes()[:0xD0])
    code = elf_bytes_at(owner, caller[0] & ~1, caller[1])
    call_contract(code, overlay_span(overlays, 161, caller[0] & ~1, caller[1]),
                  caller[0] & ~1, WALK_TUNING)
    reset_code = elf_bytes_at(owner, reset[0] & ~1, reset[1])
    body_contract(reset_code, overlay_span(overlays, 161, reset[0] & ~1, reset[1]))
    # Pure private policy leaves fit the existing Reset/Crash padding. Check
    # typed direct imports and the actual packaged bodies in both code homes.
    runtime = build / "overworld_wild_runtime_overlay_linked.o"
    leaves = (
        ("OverworldActorWalkPolicy_SampleVariance", 0x01FFF028, 22, 24,
         (("OverworldActorWalkPolicy_ReduceChain", 2),
          ("OverworldActorWalkPolicy_ApplyCommand", 1))),
        ("OverworldActorWalkPolicy_SampleChainChance", 0x01FFF35C, 34, 36,
         (("OverworldActorWalkPolicy_ReduceChain", 2),)),
    )
    leaf_names = tuple(row[0] for row in leaves)
    hosted = elf_helper_bindings(owner, leaf_names)
    imported = elf_helper_bindings(runtime, (*leaf_names,
        "OverworldActorWalkPolicy_ReduceChain",
        "OverworldActorWalkPolicy_ApplyCommand"))
    for name, address, size, capacity, callers in leaves:
        binding_contract(hosted.get(name), imported.get(name), address, capacity)
        checked(hosted[name][1] == size,
                "private Walk sampling helper extent differs")
        body_contract(elf_bytes_at(owner, address, size),
                      overlay_span(overlays, 161, address, size))
        for caller_name, count in callers:
            caller = imported.get(caller_name)
            checked(caller is not None and caller[0] & 1 and caller[1] > 0
                    and caller[2] == "FUNC" and caller[3] not in ("ABS", "UND"),
                    "private Walk sampling caller is not hosted Thumb code")
            start, extent = caller[0] & ~1, caller[1]
            code = elf_bytes_at(runtime, start, extent)
            body_contract(code, overlay_span(overlays, 156, start, extent))
            calls = [call for call in packaged_thumb_calls(code, start, start, extent)
                     if call[2] == address]
            checked(len(calls) == count and all(call[1] == "bl" for call in calls),
                    "private Walk sampling caller lost its direct Thumb calls")
    # The division uses the same pinned resident Thumb helper as the inline
    # timing policy. Both directions of this private code split stay Thumb.
    calls = packaged_thumb_calls(private[:helper[1]], WALK_TUNING,
                                  WALK_TUNING, helper[1])
    checked(calls == [(WALK_TUNING + 0x1C, "bl", reset[0] & ~1),
                      (WALK_TUNING + 0xAA, "bl", WALK_TUNING + 0xC8)]
            and private[196:204] == struct.pack("<IHH", 0x023DEE4D, 0x4718, 0x46C0),
            "private Walk tuning call/unsigned-divide inventory differs")
    divide = elf_helper_bindings(build / "linked.o", ("__aeabi_uidiv",)).get("__aeabi_uidiv")
    checked(divide is not None and divide[0] == 0x023DEE4D
            and divide[2] == "FUNC" and divide[3] not in ("ABS", "UND"),
            "private Walk tuning unsigned divide target differs")
    body_contract(elf_bytes_at(build / "linked.o", 0x023DEE4C, divide[1]),
                  overlay_span(overlays, 129, 0x023DEE4C, divide[1]))


def verify_hop_effect_choice(build, overlays):
    owner = build / "player_health_overlay_linked.o"
    chance = "OverworldActorWalkPolicy_SampleChainChance"
    symbols = elf_helper_bindings(owner, (HOP_EFFECT_CHOICE, chance))
    choice = symbols.get(HOP_EFFECT_CHOICE)
    checked(choice is not None
            and choice[:3] == (HOP_EFFECT_CHOICE_ADDR | 1, HOP_EFFECT_CHOICE_SIZE, "FUNC")
            and choice[3] not in ("ABS", "UND"),
            "private Hop effect choice owner/mode/extent differs")
    sampler = symbols.get(chance)
    checked(sampler is not None and sampler[:3] == (0x01FFF35D, 34, "FUNC")
            and sampler[3] not in ("ABS", "UND"),
            "private Hop effect chance owner differs")
    code = elf_bytes_at(owner, HOP_EFFECT_CHOICE_ADDR, HOP_EFFECT_CHOICE_SIZE)
    body_contract(code, overlay_span(overlays, 161,
                                    HOP_EFFECT_CHOICE_ADDR, HOP_EFFECT_CHOICE_SIZE))
    checked(packaged_thumb_calls(code, HOP_EFFECT_CHOICE_ADDR,
                                 HOP_EFFECT_CHOICE_ADDR, HOP_EFFECT_CHOICE_SIZE)
            == [(HOP_EFFECT_CHOICE_ADDR + 22, "bl", 0x01FFF35C)],
            "private Hop effect choice lost its one direct chance call")
    for filename in ("overworld_wild_spawns_overlay_linked.o",
                     "overworld_mount_overlay_linked.o"):
        imported = elf_helper_bindings(build / filename, (HOP_EFFECT_CHOICE,))
        checked(imported.get(HOP_EFFECT_CHOICE)
                == (HOP_EFFECT_CHOICE_ADDR | 1, 0, "FUNC", "ABS"),
                "Hop adapter lacks the exact shared choice Thumb import")


def verify_hop_private_homes(build, linked, overlays):
    """Prove the fully linked private copies and their unchanged fixed bounds."""
    wild = build / "overworld_wild_spawns_overlay_linked.o"
    mount = build / "overworld_mount_overlay_linked.o"
    copies = (
        (wild, ".overworld_field_wild_hop_support", 0x0220833C, 36,
         "overworld_field_wild_hop_support.bin", 1),
        (mount, ".overworld_field_mount_hop_tick", 0x022083B8, 72,
         "overworld_field_mount_hop_tick.bin", 1),
        (mount, ".overworld_mount_private_terrain_idle", 0x01FF9770, 16,
         None, 160),
        (mount, ".overworld_mount_private_inspect", 0x01FFA4E0, 12,
         None, 159),
    )
    for owner, section, address, capacity, binary, overlay_id in copies:
        private = section_bytes(owner, section, address, capacity)
        body_contract(private, overlay_span(overlays, overlay_id, address, capacity))
        if binary is not None:
            body_contract(private, (build / binary).read_bytes())
            body_contract(private, linked[address - BASE:address - BASE + capacity])
    leaves = (
        (wild, "OverworldWildSpawns_GetLookAroundFrames", 0x0220834C, 20, 1,
         "4000022800d80320ff2800d9ff200006000e7047"),
        (mount, "OverworldMount_TickChainHopEffects", 0x022083B8, 68, 1,
         "0d4b1a0000b5b03212788fb0012a11d118680093094b0593094b6a46"
         "0a930423d3850290d6f108fd002803d098300368684698470fb000bd"
         "44c73b02ecf7ff0102003800"),
        (mount, "OverworldMount_HasCurrentPlayer", 0x01FFFB58, 40, 161,
         "074b1b68181e0ad0064a126800209a4205d1136c834202d0186b431e"
         "9841704744c73b0250ff3d02"),
        (mount, "OverworldMount_InspectPolicy", 0x01FFA4E0, 12, 159,
         "10b501000520bff3fbfd10bd"),
        (mount, "OverworldMount_TerrainStreamIsIdle", 0x01FF9770, 16, 160,
         "10b50220c1f372fa01384342584110bd"),
        (mount, "OverworldMount_ReduceRole", 0x023BAB00, 48, 157,
         "30b50400084b87b00093084b03ad01900291684629001b6a9847240a"
         "05342406240e285d07b030bd01000c0000c83b02"),
    )
    for owner, name, address, size, overlay_id, code in leaves:
        symbol = elf_helper_bindings(owner, (name,)).get(name)
        checked(symbol is not None and symbol[:3] == (address | 1, size, "FUNC")
                and symbol[3] not in ("ABS", "UND"),
                "private Hop home owner/mode/extent differs: " + name)
        native = elf_bytes_at(owner, address, size)
        checked(native == bytes.fromhex(code),
                "private Hop home exact guarded body differs: " + name)
        body_contract(native, overlay_span(overlays, overlay_id, address, size))
    checked(linked[0x022083FC - BASE:WALK_OUTPUT - BASE] == bytes(4),
            "private mounted Hop bridge exceeds its zero tail")
    # Authenticate the relocated private Chain import and real Thumb owner.
    # The public Chain entry stays fixed.
    name = "OverworldMount_TryStartCustomMotion"
    hosted = elf_helper_bindings(mount, (name + ".constprop.0",)).get(name + ".constprop.0")
    chain = build / "overworld_mount_chain_overlay_linked.o"
    imported = elf_helper_bindings(chain, (name,)).get(name)
    # B Jump/ledge chain Hops pass their exact distance and stream live when
    # cardinal; mounted Hop locomotion is retired (926 bytes).
    binding_contract(hosted, imported, 0x023BB20C, 926)
    checked(hosted[1] == 926, "private Chain motion owner extent differs")
    body_contract(elf_bytes_at(mount, 0x023BB20C, 926),
                  overlay_span(overlays, 157, 0x023BB20C, 926))


def verify_wild_policy_init(build, linked, overlays):
    owner = build / "overworld_wild_spawns_overlay_linked.o"
    name = "OverworldWildSpawns_InitPolicyCall"
    callers = {
        "OverworldWildSpawns_BindActorPolicyProfile": 1,
        "OverworldWildSpawns_ApplyChainRepositionResult": 1,
        "OverworldWildSpawns_PublishWalkCrash": 1,
        "OverworldWildSpawns_ClearWalkMovementState.constprop.0": 1,
        "OverworldWildSpawns_TryStartAcceleratedWalkStep": 1,
        "OverworldWildSpawns_TryStartWalkStopSkid": 1,
        "OverworldWildSpawns_TryStartChainPauseAction": 1,
        "OverworldWildSpawns_CommitDeferredChainMovementPause": 2,
        "OverworldWildSpawns_HandleFinishedMovementCommand": 1,
        "OverworldWildSpawns_ApplyUniversalChainMovementPause": 1,
    }
    return_ops = "sOverworldWildReturnOps"
    symbols = elf_helper_bindings(owner, (name, *callers, return_ops))
    function = symbols.get(name)
    checked(function is not None and function[:3] == (POLICY_INIT | 1, 36, "FUNC")
            and function[3] not in ("ABS", "UND"),
            "private Wild policy initializer mode/extent differs")
    # The moved terminal Walk uses the same resident initializer through the
    # typed synchronous return ops, in place of its former direct Wild call.
    table = symbols.get(return_ops)
    checked(table is not None and table[1:3] == (60, "OBJECT")
            and table[3] not in ("ABS", "UND"),
            "private Wild initializer return-ops owner/extent differs")
    table_body = elf_bytes_at(owner, table[0], 60)
    checked(struct.unpack_from("<I", table_body, 32)[0] == function[0],
            "private Wild initializer return-ops pointer differs")
    body_contract(table_body, overlay_span(overlays, 149, table[0], 60))
    private = section_bytes(owner, ".overworld_field_wild_policy_init", POLICY_INIT, 0x30)
    body_contract(private, linked[POLICY_INIT - BASE:POLICY_INIT - BASE + 0x30])
    body_contract(private, (build / "overworld_field_walk_input_tuning.bin").read_bytes()[0xD0:0x100])
    checked(packaged_thumb_calls(private[:36], POLICY_INIT, POLICY_INIT, 36)
            == [(POLICY_INIT + 0xC, "bl", 0x023DEEA2)],
            "private Wild initializer lacks its exact direct Thumb memset call")
    resident = elf_helper_bindings(build / "linked.o", ("memset",)).get("memset")
    checked(resident is not None and resident[:3] == (0x023DEEA3, 8, "FUNC")
            and resident[3] not in ("ABS", "UND"),
            "private Wild initializer memset lacks its hosted Thumb ABI")
    body_contract(elf_bytes_at(build / "linked.o", 0x023DEEA2, 8),
                  overlay_span(overlays, 129, 0x023DEEA2, 8))
    for caller_name, count in callers.items():
        caller = symbols.get(caller_name)
        checked(caller is not None and caller[0] & 1 and caller[1] > 0
                and caller[2] == "FUNC" and caller[3] not in ("ABS", "UND"),
                "private Wild initializer caller is not hosted Thumb code")
        start, size = caller[0] & ~1, caller[1]
        code = elf_bytes_at(owner, start, size)
        overlay_id = 149
        if caller_name in RESIDENT_WALK_LEAVES:
            overlay_id = 161
            checked(caller[:3] == RESIDENT_WALK_LEAVES[caller_name],
                    "resident Wild Walk initializer caller moved or changed extent")
        body_contract(code, overlay_span(overlays, overlay_id, start, size))
        calls = [call for call in packaged_thumb_calls(code, start, start, size)
                 if call[2] == POLICY_INIT]
        checked(len(calls) == count and all(kind == "bl" for _, kind, _ in calls),
                "private Wild initializer direct-call inventory differs")


def verify_spawn_orphans(build, linked, overlays):
    owner = build / "pokemon_move_history_overlay_linked.o"
    core = build / "linked.o"
    parent_gate = elf_helper_bindings(core, ("IsOverlayLoaded",)).get("IsOverlayLoaded")
    checked(parent_gate is not None and parent_gate[0] & 1
            and parent_gate[1] > 0 and parent_gate[2] == "FUNC"
            and parent_gate[3] not in ("ABS", "UND"),
            "resident orphan parent-load gate is not hosted Thumb code")
    gate_start, gate_size = parent_gate[0] & ~1, parent_gate[1]
    body_contract(elf_bytes_at(core, gate_start, gate_size),
                  overlay_span(overlays, 129, gate_start, gate_size))
    helper_name = "OverworldWildSpawnIdentity_DeleteOrphans"
    caller_name = "OverworldWildSpawnIdentity_PrepareSlot"
    symbols = elf_helper_bindings(owner, (helper_name, caller_name))
    helper, caller = symbols.get(helper_name), symbols.get(caller_name)
    checked(helper is not None and helper[:3] == (SPAWN_ORPHANS | 1, 86, "FUNC")
            and helper[3] not in ("ABS", "UND")
            and caller is not None and caller[:3] == (0x023C0001, 334, "FUNC")
            and caller[3] not in ("ABS", "UND"),
            "private orphan cleanup or resident validation mode/extent differs")
    private = section_bytes(owner, ".overworld_field_spawn_orphans", SPAWN_ORPHANS, 0x58)
    body_contract(private, linked[SPAWN_ORPHANS - BASE:SPAWN_ORPHANS - BASE + 0x58])
    body_contract(private, (build / "overworld_field_condition.bin").read_bytes())
    start, size = caller[0] & ~1, caller[1]
    code = elf_bytes_at(owner, start, size)
    body_contract(code, overlay_span(overlays, 153, start, size))
    checked(packaged_thumb_calls(code, start, start, size)
            == [(start + 0x7E, "bl", start + 0x14C),
                (start + 0x13E, "bl", SPAWN_ORPHANS)]
            and elf_bytes_at(owner, start + 0x144, 12)
            == struct.pack("<IIHH", parent_gate[0], 2074, 0x4718, 0x46C0),
            "resident orphan validation lacks its exact parent-load gate and Thumb call")
    body_contract(elf_bytes_at(owner, start + 0x144, 12),
                  overlay_span(overlays, 153, start + 0x144, 12))
    checked(packaged_thumb_calls(private[:86], SPAWN_ORPHANS, SPAWN_ORPHANS, 86)
            == [(SPAWN_ORPHANS + 0x12, "bl", SPAWN_ORPHANS + 0x54),
                (SPAWN_ORPHANS + 0x42, "bl", SPAWN_ORPHANS + 0x54)]
            and private[0x4C:0x58]
            == struct.pack("<IIHH", BASE, 0x0205E401, 0x4718, 0x46C0),
            "private orphan cleanup changed its appearance/native deletion callbacks")


def verify_condition_subject(build, linked, overlays):
    capsule = build / "overworld_field_capsule_linked.o"
    actor = build / "overworld_actor_system_overlay_linked.o"
    specs = (
        ("OverworldConditionSubject_Populate", SUBJECT, 186, 192),
        ("OverworldConditionSubject_ClearActor", SUBJECT + 0xC0, 90, 0x60),
        ("OverworldConditionSubject_HandleEquals", SUBJECT + 0x120, 26, 0x40),
    )
    callers = {
        "OverworldBehaviorConditionAdapter_EvaluateActor": (SUBJECT, SUBJECT + 0xC0),
        "OverworldBehaviorConditionAdapter_BuildFrame": (SUBJECT + 0x120,),
        "OverworldBehaviorConditionAdapter_ResolveTarget": (SUBJECT + 0x120,),
        "OverworldBehaviorConditionAdapter_ClearActor": (SUBJECT + 0xC0,),
    }
    names = tuple(row[0] for row in specs)
    hosted = elf_helper_bindings(capsule, names)
    imported = elf_helper_bindings(actor, (*names, *callers))
    for name, address, size, capacity in specs:
        binding_contract(hosted.get(name), imported.get(name), address, capacity)
        checked(hosted[name][1] == size, "condition subject exact function size differs")
        body_contract(elf_bytes_at(capsule, address, capacity),
                      linked[address - BASE:address - BASE + capacity])
    for name, targets in callers.items():
        caller = imported.get(name)
        checked(caller is not None and caller[0] & 1 and caller[1] > 0
                and caller[2] == "FUNC" and caller[3] not in ("ABS", "UND"),
                "condition subject caller is not hosted Thumb code")
        start, size = caller[0] & ~1, caller[1]
        code = elf_bytes_at(actor, start, size)
        body_contract(code, overlay_span(overlays, 158, start, size))
        calls = [call for call in packaged_thumb_calls(code, start, start, size)
                 if SUBJECT <= call[2] < SPAWN_ORPHANS]
        checked(sorted(target for _, kind, target in calls if kind == "bl")
                == sorted(targets) and len(calls) == len(targets),
                "condition subject caller direct Thumb inventory differs")
        if name == ACTOR_EVALUATE:
            checked(calls == [
                (ACTOR_EVALUATE_ADDR + 0x9C, "bl", SUBJECT + 0xC0),
                (ACTOR_EVALUATE_ADDR + 0x166, "bl", SUBJECT),
            ], "condition evaluation lost its exact Clear/Populate Subject calls")
    populate = elf_bytes_at(capsule, SUBJECT, 192)
    clear = elf_bytes_at(capsule, SUBJECT + 0xC0, 96)
    equal = elf_bytes_at(capsule, SUBJECT + 0x120, 26)
    checked(packaged_thumb_calls(populate, SUBJECT, SUBJECT, 186)
            == [(SUBJECT + 0x1C, "bl", SUBJECT + 0xB8)]
            and populate[184:192] == bytes.fromhex("18 47 c0 46 00 00 00 00")
            and packaged_thumb_calls(equal, SUBJECT + 0x120, SUBJECT + 0x120, 26) == [],
            "condition subject terrain callback/equality instruction inventory differs")
    checked(packaged_thumb_calls(clear, SUBJECT + 0xC0, SUBJECT + 0xC0, 90)
            == [(SUBJECT + 0xD4, "bl", SUBJECT + 0x118),
                (SUBJECT + 0xDE, "bl", 0x023DEEA2),
                (SUBJECT + 0xF0, "bl", 0x023DEEA2),
                (SUBJECT + 0x104, "bl", 0x01FFBD00)]
            and clear[76:96] == struct.pack("<IIIHHI",
                0x0201AB0D, 0x998, 0x858, 0x4718, 0x46C0, 0),
            "condition clear native free/memset/resolution inventory differs")
    health = build / "player_health_overlay_linked.o"
    name = "OverworldBehaviorConditionAdapter_ClearResolution"
    resolution = elf_helper_bindings(health, (name,)).get(name)
    binding_contract(resolution, elf_helper_bindings(capsule, (name,)).get(name),
                     0x01FFBD00, 0x100)
    body_contract(elf_bytes_at(health, 0x01FFBD00, resolution[1]),
                  overlay_span(overlays, 161, 0x01FFBD00, resolution[1]))


def verify_throw_binding_refresh(build, linked, overlays):
    selector = build / "overworld_follower_selector_overlay_linked.o"
    actor = build / "overworld_actor_system_overlay_linked.o"
    refresh, current, frame = ("OverworldThrowBinding_Refresh",
        "OverworldThrowBinding_CurrentSpawn",
        "OverworldBehaviorConditionAdapter_BuildFrame")
    reader = "OverworldThrowObservation_BindingPosition"
    symbols = elf_helper_bindings(selector, (refresh, current, frame, reader,
        "OverworldSpawnSpatial_IsCurrentMapObject",
        "OverworldThrowBinding_PlayerX", "OverworldThrowBinding_PlayerY"))
    checked(symbols.get(refresh, ())[:3] == (0x02208601, 166, "FUNC")
            and symbols[refresh][3] not in ("ABS", "UND")
            and symbols.get(current, ())[:3] == (0x022086A9, 68, "FUNC")
            and symbols[current][3] not in ("ABS", "UND"),
            "private binding refresh mode/extent differs")
    private = section_bytes(selector, ".overworld_throw_binding_refresh",
                            0x02208600, 0x100)
    body_contract(private, linked[0x02208600 - BASE:0x02208700 - BASE])
    body_contract(private, (build / "overworld_field_walk_input_tuning.bin").read_bytes()[0x100:0x200])
    body_contract(private, overlay_span(overlays, 1, 0x02208600, 0x100))
    frame_binding = elf_helper_bindings(actor, (frame,)).get(frame)
    binding_contract(frame_binding, symbols.get(frame), 0x023B6930, 0x1D0)
    body_contract(elf_bytes_at(actor, 0x023B6930, frame_binding[1]),
                  overlay_span(overlays, 158, 0x023B6930, frame_binding[1]))
    checked(packaged_thumb_calls(private[:166], 0x02208600, 0x02208600, 166)
            == [(0x0220862C, "bl", 0x022086A4),
                (0x02208658, "bl", 0x023B6930),
                (0x0220867E, "bl", 0x0205C67C),
                (0x02208686, "bl", 0x0205C688)]
            and struct.unpack_from("<I", private, 0x98)[0] == symbols[current][0],
            "binding refresh lost its shared frame/Player owners or current-spawn callback")
    for name, address in (("OverworldThrowBinding_PlayerX", 0x0205C67C),
                          ("OverworldThrowBinding_PlayerY", 0x0205C688)):
        checked(symbols.get(name) == (address | 1, 0, "FUNC", "ABS"),
                "binding Player read lost its typed stock Thumb owner")
    spatial = symbols.get("OverworldSpawnSpatial_IsCurrentMapObject")
    checked(spatial is not None and spatial[:3] == (0x023C2201, 48, "FUNC")
            and spatial[3] not in ("ABS", "UND"),
            "binding current-object owner differs")
    current_code = private[0xA8:0xEC]
    calls = packaged_thumb_calls(current_code, 0x022086A8, 0x022086A8, 68)
    checked(len(calls) == 1 and calls[0][1:] == ("bl", 0x023C2200),
            "binding current-spawn read lost its native manager check")
    body_contract(elf_bytes_at(selector, 0x023C2200, spatial[1]),
                  overlay_span(overlays, 152, 0x023C2200, spatial[1]))
    caller = symbols.get(reader)
    checked(caller is not None and caller[:3] == (0x023C2DA1, 238, "FUNC")
            and caller[3] not in ("ABS", "UND"), "binding reader moved")
    code = elf_bytes_at(selector, 0x023C2DA0, 238)
    checked(code.count(struct.pack("<I", 0x02208601)) == 1,
            "binding reader lacks its exact Field refresh callback")
    body_contract(code, overlay_span(overlays, 152, 0x023C2DA0, 238))


# Overlay 2's water sink pass owns the RefreshAll entry and calls the hosted
# RefreshAll first (src/overworld_follower_release_overlay2/linker.ld).
WATER_SINK_FRAME_PASS = 0x02250001


def verify_package(rom_path):
    build = ROOT / "build"
    capsule = build / "overworld_field_capsule_linked.o"
    selector = build / "overworld_follower_selector_overlay_linked.o"
    symbols = elf_helper_bindings(capsule, (
        "gOverworldActorAppearanceEntry", "__appearance_end", NOTIFY,
        "OverworldActorAppearance_RefreshNative", "OverworldActorAppearance_Forget",
        "OverworldActorAppearance_BeforeParentUnload", "OverworldActorAppearance_Inspect",
        "OverworldActorAppearance_RefreshAll", "OverworldActorAppearance_FieldExit"))
    rom = rom_path.read_bytes()
    overlays = rom_overlays(rom)
    verify_hop_lease(build, overlays)
    verify_cargo_observation(build, overlays)
    verify_notice_blob_host(build, overlays)
    checked(overlays[1][0] == (1, 0x021E5900, 0x24260, 0x3C020,
                              0x02209810, 0x02209814, 1, 0),
            "stock Field file/BSS/init/loader metadata changed")
    verify_stock_field_exit(overlays)
    land_model_task_contract(overlay_span(overlays, 1, LAND_MODEL_TASK, LAND_MODEL_TASK_SIZE))
    linked = elf_bytes_at(capsule, BASE, LIMIT - BASE)
    body_contract(linked, (build / "output_overworld_field_capsule.bin").read_bytes())
    body_contract(linked, overlay_span(overlays, 1, BASE, LIMIT - BASE))
    checked(overlay_span(overlays, 1, LIMIT, 12)
            == bytes.fromhex("a98b1f0205881f023d881f02"),
            "neighboring stock graphics callback list changed")
    table = elf_helper_bindings(build / "field_linked.o", ("gOWTagToFileNum",)).get("gOWTagToFileNum")
    checked(table is not None and table[2] == "OBJECT" and table[3] not in ("ABS", "UND"),
            "current graphics table owner is absent")
    for address in (0x021F92FC, 0x021FA280):
        checked(overlay_span(overlays, 1, address, 4) == struct.pack("<I", table[0]),
                "retired graphics-table reader is no longer repointed")
    checked(symbols.get("gOverworldActorAppearanceEntry", ())[:3]
            == (BASE, 28, "OBJECT") and struct.unpack_from("<IHH", linked)
            == (0x5041574F, 2, 28), "appearance entry identity/size differs")
    for offset, name in enumerate(("OverworldActorAppearance_RefreshNative",
        "OverworldActorAppearance_Forget", "OverworldActorAppearance_BeforeParentUnload",
        "OverworldActorAppearance_Inspect", "OverworldActorAppearance_RefreshAll")):
        function = symbols.get(name)
        checked(function is not None and function[2] == "FUNC" and function[0] & 1
                and (BASE + 28 <= (function[0] & ~1) < ROUTE_BASE_Y if offset < 4
                     else APPEARANCE_EXIT <= (function[0] & ~1) < DELIVERY)
                and function[3] not in ("ABS", "UND")
                and struct.unpack_from("<I", linked, 8 + offset * 4)[0]
                    == (function[0] if offset < 4 else WATER_SINK_FRAME_PASS),
                "appearance callback is not exact hosted Thumb code")
    field_exit = symbols.get("OverworldActorAppearance_FieldExit")
    checked(field_exit is not None and field_exit[0] == APPEARANCE_EXIT | 1
            and field_exit[2] == "FUNC" and field_exit[3] not in ("ABS", "UND")
            and overlay_span(overlays, 1, 0x02206380, 4)
            == struct.pack("<I", APPEARANCE_EXIT | 1),
            "stock Field template does not use the exact appearance Exit hook")
    checked(symbols.get("__appearance_end", (LIMIT,))[0] <= ROUTE_BASE_Y,
            "appearance bytes overlap the private Wild route support")
    verify_appearance_release(build, overlays)
    verify_appearance_rest_copy(build, overlays)
    verify_profile_skid_helpers(build, overlays, rom)
    verify_condition_subject(build, linked, overlays)
    verify_shared_slam_jump(build, overlays, overlay_span)
    verify_throw_binding_refresh(build, linked, overlays)
    verify_wild_route_base_y(build, linked, overlays)
    verify_wild_walk_output(build, linked, overlays)
    verify_walk_input_tuning(build, linked, overlays)
    verify_hop_effect_choice(build, overlays)
    verify_hop_private_homes(build, linked, overlays)
    verify_wild_policy_init(build, linked, overlays)
    verify_spawn_orphans(build, linked, overlays)
    selector_names = (FIND, "OverworldBehaviorCondition_Truth",
        "OverworldBehaviorCondition_SameHandle", "OverworldBehaviorCondition_CanSee",
        "OverworldBehaviorCondition_InRange", "memcpy",
        "OverworldBehaviorConditionService_Get")
    selector_symbols = elf_helper_bindings(selector, selector_names)
    gate = selector_symbols.get("OverworldBehaviorConditionService_Get")
    checked(gate is not None and gate[0] == 0x023C22B9 and gate[1] > 0
            and gate[2] == "FUNC" and gate[3] not in ("ABS", "UND"),
            "condition service lifetime gate differs")
    body_contract(elf_bytes_at(selector, gate[0] & ~1, gate[1]),
                  overlay_span(overlays, 152, gate[0] & ~1, gate[1]))
    checked(not any(name in selector_symbols for name in selector_names[:5]),
            "retired pure Condition code is still hosted in Selector")
    # The appearance entry carries executable pointers. Its core helper
    # imports must keep Thumb metadata and the current packaged code identity.
    core = build / "linked.o"
    for name, target in (("memset", 0x023DEEA2), ("__aeabi_uidiv", 0x023DEE4C),
                         ("__aeabi_uidivmod", 0x023DEE4C)):
        imported = elf_helper_bindings(capsule, (name,)).get(name)
        resident = elf_helper_bindings(core, (name,)).get(name)
        checked(imported == (target | 1, 0, "FUNC", "ABS")
                and resident is not None and resident[0] == target | 1
                and resident[1] > 0 and resident[2] == "FUNC"
                and resident[3] not in ("ABS", "UND"),
                "appearance core import lost its hosted Thumb helper")
        body_contract(elf_bytes_at(core, target, resident[1]),
                      overlay_span(overlays, 129, target, resident[1]))
    for filename, overlay_id, caller_name in CALLERS:
        owner = build / filename
        bindings = elf_helper_bindings(owner, (NOTIFY, caller_name))
        binding_contract(symbols.get(NOTIFY), bindings.get(NOTIFY),
                         DELIVERY, LIMIT - DELIVERY)
        caller = bindings.get(caller_name)
        checked(caller is not None and caller[0] & 1 and caller[1] > 0,
                "effect caller is not hosted Thumb code")
        start, size = caller[0] & ~1, caller[1]
        call_contract(elf_bytes_at(owner, start, size),
                      overlay_span(overlays, overlay_id, start, size), start, DELIVERY)
    print(f"PASS exact stock Field capsule, {len(CALLERS)} typed effect callers, condition subject, Wild route support and walk output")


def verify_host_guard():
    text = (ROOT / "include/overworld_wild_runtime_state_internal.h").read_text()
    start = text.index("static inline void OverworldWildConditions_NotifyWorldEffectInline(")
    opening = text.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    production = text[start:end]
    gate_source = (ROOT / "src/overworld_follower_selector_overlay/overworld_behavior_condition_service.c").read_text()
    gate_start = gate_source.index("OverworldBehaviorConditionService_Get(void)")
    gate_end = gate_source.index("\n}", gate_start) + 2
    production_gate = "static const OverworldBehaviorConditionServiceEntry *\n" + gate_source[gate_start:gate_end]
    # Include the actual private native MAIN-region predicate when present.
    # The old gate can still compile for the retained metadata-read control.
    field_loaded = ""
    if "Service_FieldLoaded(" in gate_source:
        helper_start = gate_source.index("Service_FieldLoaded(")
        helper_end = gate_source.index("\n}", helper_start) + 2
        field_loaded = "static int " + gate_source[helper_start:helper_end]
    prefix = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
#define OVERWORLD_BEHAVIOR_HOST 1
#define OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS 10
#define OVERWORLD_BEHAVIOR_CONDITION_SERVICE_MAGIC 0x4342574F
#define OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_VERSION 10
typedef struct {u16 slot,generation,fieldEpoch,mapGeneration,encounterGeneration,reserved;} OverworldActorHandle;
typedef struct {u32 marker;} Prepared;
typedef struct {Prepared actors[10];} OverworldBehaviorConditionRuntime;
typedef struct {OverworldBehaviorConditionRuntime *conditions;} OverworldWildOverlayRuntimeState;
typedef struct {u8 active; u16 encounterGeneration;} Spawn;
typedef struct {u16 mapGeneration; Spawn spawns[10]; void *movementRuntimeState;} OverworldWildSpawnState;
typedef struct {u32 magic; u16 version,size; void (*notifyWorldEffect)(Prepared *,const OverworldActorHandle *,u32);} OverworldBehaviorConditionServiceEntry;
static OverworldBehaviorConditionServiceEntry service;
static unsigned delivered; static int available=1;
static Prepared *expectedPrepared; static const OverworldActorHandle *expectedSubject;
static void Delivered(Prepared *p,const OverworldActorHandle *h,u32 e)
 {assert(p==expectedPrepared && h==expectedSubject && e==3); ++delivered;}
static const OverworldBehaviorConditionServiceEntry *OverworldBehaviorConditionService_Get(void)
 {return available ? &service : NULL;}
'''
    # Test the actual guest service gate separately from the guard's native
    # getter stub. Its Field1 check is required before returning callable code.
    production_gate = production_gate.replace("OverworldBehaviorConditionService_Get(void)",
                                               "CheckedServiceGet(void)")
    gate_boundaries = r'''
#define OVERLAY_FIELD 1
#define MAX_ACTIVE_OVERLAYS 8
#define TRUE 1
#define FALSE 0
static const OverworldBehaviorConditionServiceEntry *HostServiceTable(void) {return &service;}
#define OVERWORLD_BEHAVIOR_CONDITION_SERVICE_ENTRY HostServiceTable()
typedef struct {u32 id; int active;} PMiLoadedOverlay;
static PMiLoadedOverlay overlayRegions[3][MAX_ACTIVE_OVERLAYS];
static int selectorLoaded=1;
static unsigned metadataReads,regionReads;
static int OverworldFollowerSelector_IsDirectLoaded(void) {return selectorLoaded;}
static PMiLoadedOverlay *__attribute__((unused)) GetLoadedOverlaysInRegion(unsigned region)
 {assert(region==0); ++regionReads; return overlayRegions[region];}
static int __attribute__((unused)) IsOverlayLoaded(unsigned id)
 {assert(id==1); ++metadataReads;
  for(unsigned i=0;i<MAX_ACTIVE_OVERLAYS;++i)
   if(overlayRegions[0][i].id==id && overlayRegions[0][i].active==TRUE) return TRUE;
  return FALSE;}
'''
    driver = r'''
int main(void) {
 OverworldBehaviorConditionRuntime conditions={0};
 OverworldWildOverlayRuntimeState runtime={&conditions};
 OverworldWildSpawnState state={.mapGeneration=4,.movementRuntimeState=&runtime};
 OverworldActorHandle subject={.slot=7,.generation=2,.fieldEpoch=3,.mapGeneration=4,.encounterGeneration=5};
 state.spawns[7]=(Spawn){1,5};
 service=(OverworldBehaviorConditionServiceEntry){0x4342574F,10,sizeof(service),Delivered};
 expectedPrepared=&conditions.actors[7]; expectedSubject=&subject;
 OverworldWildConditions_NotifyWorldEffectInline(&state,&subject,3); assert(delivered==1);
 OverworldWildConditions_NotifyWorldEffectInline(NULL,&subject,3);
 OverworldWildConditions_NotifyWorldEffectInline(&state,NULL,3);
 subject.slot=10; OverworldWildConditions_NotifyWorldEffectInline(&state,&subject,3); subject.slot=7;
 state.movementRuntimeState=NULL; OverworldWildConditions_NotifyWorldEffectInline(&state,&subject,3); state.movementRuntimeState=&runtime;
 state.mapGeneration++; OverworldWildConditions_NotifyWorldEffectInline(&state,&subject,3); state.mapGeneration--;
 state.spawns[7].active=0; OverworldWildConditions_NotifyWorldEffectInline(&state,&subject,3); state.spawns[7].active=1;
 state.spawns[7].encounterGeneration++; OverworldWildConditions_NotifyWorldEffectInline(&state,&subject,3); state.spawns[7].encounterGeneration--;
 runtime.conditions=NULL; OverworldWildConditions_NotifyWorldEffectInline(&state,&subject,3); runtime.conditions=&conditions;
 available=0; OverworldWildConditions_NotifyWorldEffectInline(&state,&subject,3); available=1;
 service.magic++; OverworldWildConditions_NotifyWorldEffectInline(&state,&subject,3); service.magic--;
 service.version++; OverworldWildConditions_NotifyWorldEffectInline(&state,&subject,3); service.version--;
 service.size++; OverworldWildConditions_NotifyWorldEffectInline(&state,&subject,3); service.size--;
 service.notifyWorldEffect=NULL; OverworldWildConditions_NotifyWorldEffectInline(&state,&subject,3); service.notifyWorldEffect=Delivered;
 assert(delivered==1);
 OverworldWildConditions_NotifyWorldEffectInline(&state,&subject,3); assert(delivered==2);
 assert(CheckedServiceGet()==NULL); /* Empty native MAIN table. */
 overlayRegions[1][0]=(PMiLoadedOverlay){1,TRUE};
 overlayRegions[2][0]=(PMiLoadedOverlay){1,TRUE};
 assert(CheckedServiceGet()==NULL); /* Other native regions grant nothing. */
 overlayRegions[0][7]=(PMiLoadedOverlay){2,TRUE};
 assert(CheckedServiceGet()==NULL);
 overlayRegions[0][7]=(PMiLoadedOverlay){1,FALSE};
 assert(CheckedServiceGet()==NULL);
 overlayRegions[0][7].active=2; assert(CheckedServiceGet()==NULL);
 overlayRegions[0][7].active=TRUE; assert(CheckedServiceGet()==&service);
 unsigned before=regionReads;
 selectorLoaded=0; assert(CheckedServiceGet()==NULL); selectorLoaded=1;
 assert(regionReads==before); /* Do not query before direct owner admission. */
 overlayRegions[0][7].active=FALSE; assert(CheckedServiceGet()==NULL);
 overlayRegions[0][0]=(PMiLoadedOverlay){1,TRUE};
 assert(CheckedServiceGet()==&service); /* First and last slots both work. */
 service.version++; assert(CheckedServiceGet()==NULL); service.version--;
 assert(CheckedServiceGet()==&service);
 assert(metadataReads==0);
 puts("PASS original effect delivery guards and exact native MAIN Field lifetime without metadata reads");
}
'''
    with tempfile.TemporaryDirectory(prefix="overworld-field-effect-") as directory:
        source, binary = Path(directory) / "guard.c", Path(directory) / "guard"
        source.write_text(prefix + production + gate_boundaries + field_loaded + production_gate + driver)
        subprocess.run(["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                        str(source), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-only", action="store_true")
    parser.add_argument("--rom", type=Path, default=ROOT / "test.nds")
    args = parser.parse_args()
    package_controls()
    if args.package_only:
        verify_package(args.rom)
    else:
        verify_host_guard()


if __name__ == "__main__":
    main()
