"""Stock bubble and linked VRAM facts at a paused endpoint.

No guest work, memory writes, raw-memory command, or acceptance credit.
Sources: stock overlay_01_021F1348.s, overlay_01_02203A18.s,
lib/asm/nnsys.s and gf_3d_vramman.c. These are exact USA retail seals;
The typed three-slot owner is authenticated against the frozen native owners.
"""
from __future__ import annotations

import hashlib
import struct

from tools.overworld.devtools_field_lifecycle import FIELD_TEMPLATE


READ_BUDGET = 24 * 1024
MAX_RESOURCES = 64
TEXTURE_STATE = 0x021D84E4
PALETTE_STATE = 0x021D8500
DISPATCH = 0x02110924
DISPATCH_WORDS = (0x020B6814, 0x020B68A4, 0x020B6B70, 0x020B6C3C)

# Complete named stock bodies (including literal pools where present).
STOCK_SEALS = (
    (0x021F16EC, 84, "f65c466a47b92fee19509f24240115a27cdb5b17fc71ecdfac3cc2ddec26e412", "field-model-constructor"),
    (0x02024280, 44, "ca3e276e174a568db04e33b62629ecbdeb7b902770285728f40575d29b1b43ef", "model-pool-slot-allocate"),
    (0x0203DF8C, 0x18, "026cbebd5e1a69f6aa98251c518e34e81aff4c1f88156f12146e89d641357bc2", "field-ready"),
    (0x020B6498, 0xC, "4e04ee5e8b0262b528762ebe6bb10dc4fc3c9037cac69eff72906b7667e6ea14", "lnk-manager-init"),
    (0x020B64A4, 0x4C, "505f81d8459680e58481fe06aaa12ecb97cd70726dd8321eacc1a5011a15e43a", "lnk-node-pool-init"),
    (0x020B654C, 0x154, "62b853316f6c7cda9bc6cd5899526fdfa699ab9f2e91ff74b95d118418e30238", "lnk-alloc-aligned"),
    (0x020B66A0, 0x84, "2c3f26c7ab702cd49248985302d88d5501dec6cac6b592be0e1baa4cf0c042b8", "lnk-merge"),
    (0x020B6724, 0x90, "49a94fd782515c35544e53e9d29fd28e2e2aaf706147517a12aaee128653ca18", "lnk-free"),
    (0x020B67BC, 0x58, "87786490276334e1d9cabf49a310be8a54e7c0104b89cd1113885cfc8b74d7ce", "tex-init"),
    (0x020B6814, 0x90, "0fd62c617b0ccbb0c2b501a98e97a769095d511403d2e60a76155d3124c9fe84", "tex-alloc"),
    (0x020B68A4, 0x74, "edeee63cba7bb9f37b088814fabf61c9f8bac9743a770a524d5859d357b387ab", "tex-free"),
    (0x020B6918, 0x1FC, "45c5234b16224970a9c06fa69fb1a418bc0a8f53d6b07f1a5d9885a4eff73a9e", "tex-reset"),
    (0x020B6B1C, 0x54, "6f990c274944333f7553bf0eac54cfd59e5b5fce38962012ff742e3a68fa2fab", "palette-init"),
    (0x020B6B70, 0xCC, "05bddfeb0b19c6a633cb7a2a0872a077301c2bb4a97ef90d650442ae02429a60", "palette-alloc"),
    (0x020B6C3C, 0x44, "654882d8f5a2d94b4237518686e565e85151bfac0384673895dcb0d9fb6ac4d4", "palette-free"),
    (0x020B6C80, 0x5C, "e7bbab02e310ec0bda00d756d7fa498ae733ac69137fdbbb9fe99e10397a5c68", "palette-reset"),
    (0x021F1348, 0x3C, "77a317e4e9468e147fcc84fb4f25fac265262c7dd361c945a7bbb2548b7d41c8", "field-effect-context-init"),
    (0x021F1450, 0x1C, "e1ccfc4428a8cd07ac9f63349310657e5c1948a24d0e97ed45beffcafd14e0ea", "resource-lookup-result"),
    (0x021F146C, 0xC, "bb1682d0987488832b5f33401dd23e84f6ed91972f032adcfee2832722776377", "object-current-context"),
    (0x021F1588, 0x18, "2257995b291b307ef3f75416858521a868219b241e3d3930ed99573830e40830", "resource-lookup"),
    (0x023B85AC, 44, "aad730ba2ba51e6b02e17500ad5b086d3587d72d980ee3cddb28efc343e58be8", "OverworldEmoteSlots_Select"),
    (0x02203C64, 52, "a3cd0d64c5aac6e14e58ad10a8bc3cc07bd5a6b1cef4a1af094cbc5980b7bd3f", "OverworldEmoteSlots_LoadMember"),
    (0x023BA09C, 28, "9c69a93934a288a6b9238f9f27e8285aefe1a6ce274382ccc8e19a85f058382e", "OverworldEmoteSlots_Update"),
    (0x02203B28, 316, "5529dd0bea1f91d2694c3fa340466cedffc78f186db49b1ea29db55e32e4b921", "OverworldEmoteSlots_Initialize"),
    (0x023BA01C, 128, "f1950ff831f0571f620d85623b2412a394d682732f5b349d6f8f8760ad287763", "OverworldEmoteSlots_Prepare"),
    (0x023B87CC, 40, "c06780fd8840c7fce35e364b55f085ba332a7f940596b46a895b34bdaa7c1890", "OverworldEmoteSlots_Retire"),
    (0x02203A20, 22, "358e06e56c93d41c17e097308342ae71020870df03dff8a67b3d67d1b79791cd", "OverworldEmoteSlots_Destroy"),
    (0x02203A60, 84, "dda9a9c0b7ad4fb26a6d574d38d46451ee4910cae7d6f28c017268999df113ba", "OverworldEmoteSlots_Release"),
    (0x023B8540, 108, "d12c3876420b5df3cd2a938aea8fcf6963893acb2860c10efa331536f9618127", "OverworldEmoteSlots_Collect"),
    (0x023B85D8, 20, "fc6a51ccfff979db453bd2bf14a5240951401e3cebc17dffd829071a6aa5a729", "descriptor"),
    (0x023B8798, 52, "ba2c3af26f79d53220a6f8355964efa065ecd8a06c2e8c93c05dfe2fc71ba6a9", "OverworldEmoteSlots_DestroyOwner"),
    (0x023B8728, 112, "ec079ea49fed2258c2d2a0ae301590910518f6ea963eedec9b48a6cf5f1c3eb8", "OverworldEmoteSlots_CreateOwner"),
    (0x023B85EC, 14, "753c10a3de712e0d14b13ab904a7c2723ffa35a8509cef7cb11f54719431d254", "OverworldEmoteSlots_AfterModelAdmission"),
    (0x023B9110, 272, "d1210539d613061cbee646211a77522a3a00605f346cef68ae90575cd1c1ee8d", "OverworldEmoteSlots_Admit"),
    (0x02203A40, 8, "6524593d60960f1d3ff3e2f46471babc38a8aa7f463a74f9555d37ff4b422f73", "redirected owner destructor tail"),
    (0x02203A48, 8, "b2fd034f326d279808b576138192d18c92d67ea5ae944da02f7e1374a845e27f", "stock admission frame"),
    (0x02203AB4, 116, "67dcdada12cfd3c97ad2034c5c7af317108cfe737e2c890bcfd3a00fb4938c39", "stock script start and waiter"),
    (0x02203CA0, 24, "27b883ccbb6757a9a352ec71da9312b7b196195190b8383d9b197252c3aaad7f", "stock unused original effect destructor"),
    (0x02203CB8, 264, "c3e72356a7ebebba70471de002645e33142657a39d07012229b44e7bd6b849d8", "stock update"),
    (0x02203DC0, 56, "9ce365df23548e41a0e269c36471c6cf660054e4dceba797535173b9ee4abb50", "stock draw"),
    (0x02203DF8, 68, "a7186d4f0a61b46c422e7c3c8fbef8c2ed45cbbb377ba2b686e2ed77d9f8ad32", "stock animation frame"),
    (0x02209518, 32, "d8755f2d3773957cb72e555b17303e2d1973c28ceee7951a4182ab51978b5688", "stock descriptor and animation material data"),

)


def _require(ok, reason):
    if not ok:
        raise ValueError(reason)


SLOT_WORDS = ("owner", "object", "effect", "model", "iconFile", "animationFile", "texture", "textureKey", "paletteKey", "state")


def decode_emote_owner(pointer, context, raw):
    """Exact private148-byte layout; active/retiring slots still own resources."""
    _require(isinstance(raw, bytes) and len(raw) == 148, "emote-owner-size-differs")
    words = struct.unpack("<37I", raw)
    owner_context, count, model, animation, texture, task, closing = words[:7]
    _require(owner_context == context and 0 <= count <= 3 and closing in (0, 1)
             and all(v and v % 4 == 0 and 0x02000000 <= v < 0x02400000
                     for v in (model, animation, texture)), "emote-owner-context-assets-or-count-differs")
    slots = []
    for i in range(3):
        slot = dict(zip(SLOT_WORDS, words[7 + i * 10:17 + i * 10]))
        state = slot["state"]
        _require(state in (0, 1, 2, 3), "emote-slot-state-differs")
        if state == 0:
            _require(not any(slot.values()), "emote-free-slot-not-clear")
        else:
            _require(slot["owner"] == pointer and slot["object"] and slot["object"] % 4 == 0,
                     "emote-slot-owner-or-object-differs")
            for name in ("object", "effect", "model", "iconFile", "animationFile", "texture"):
                v = slot[name]
                _require(v == 0 or v % 4 == 0 and 0x02000000 <= v < 0x02400000,
                         "emote-slot-pointer-outside-main-ram")
            if state == 2:
                _require(all(slot[name] for name in SLOT_WORDS[1:9]), "emote-active-slot-resource-missing")
            if state == 3:
                _require(slot["effect"] == slot["model"] == 0, "emote-retiring-slot-still-live")
        slot.update(index=i, pointer=pointer + 28 + i * 40)
        slots.append(slot)
    used = [slot for slot in slots if slot["state"]]
    _require(count == len(used) and (not count or task and task % 4 == 0
             and 0x02000000 <= task < 0x02400000), "emote-count-or-retirement-task-differs")
    for key in ("object", "effect", "model", "iconFile", "animationFile", "texture", "textureKey", "paletteKey"):
        values = [slot[key] for slot in used if slot[key]]
        _require(len(values) == len(set(values)), "emote-shared-slot-" + key)
    return dict(known=True, ownerPointer=pointer, contextPointer=context,
                activeCount=count, slotLimit=3, modelFile=model, animationFile=animation,
                texture=texture, retirementTask=task, closing=closing, slots=slots,
                rawHex=raw.hex())


def _first_fit_two(blocks, spares, size, alignment):
    """Dry-run the sealed native first-fit order, not an allocation call.

    A prefix caused by alignment consumes one spare metadata node. An exact
    exhausted block returns one. Preserve head insertion of a prefix, since
    it can change the native first-fit order for the second request.
    """
    free = [list(block) for block in blocks]
    offsets = []
    initial_spares = spares
    for _ in range(2):
        for index, (start, length) in enumerate(free):
            aligned = (start + alignment - 1) & -alignment
            padding = aligned - start
            if padding + size <= length:
                break
        else:
            return {"canAdmit": False, "reason": "no-fitting-block",
                    "requestCount": 2, "requestBytes": size, "alignment": alignment}
        if padding:
            if not spares:
                return {"canAdmit": False, "reason": "alignment-needs-spare-node",
                        "requestCount": 2, "requestBytes": size, "alignment": alignment}
            spares -= 1
            free.insert(0, [start, padding])
            index += 1
        remaining = length - padding - size
        if remaining:
            free[index] = [aligned + size, remaining]
        else:
            free.pop(index)
            spares += 1
        offsets.append(aligned)
    return {"canAdmit": True, "reason": None, "requestCount": 2,
            "requestBytes": size, "alignment": alignment,
            "plannedVramOffsets": offsets, "spareNodesBefore": initial_spares,
            "spareNodesAfter": spares, "dryRunOnly": True}


def observe_emote_vram_diagnostics(session):
    result = {"known": False, "diagnosticOnly": True, "acceptedProof": False,
              "boundary": "paused-native-cycle-end", "frame": session.completed_frames,
              "nativeCycle": session.rt.EXECUTED_FRAME_COUNT,
              "readBudgetBytes": READ_BUDGET, "bytesRead": 0, "codeIdentity": []}

    def span(address, size):
        _require(type(address) is int and type(size) is int and size > 0
                 and address % 4 == 0 and 0x02000000 <= address <= 0x02400000 - size,
                 "invalid-main-ram-span")

    def charge(size):
        _require(result["bytesRead"] + size <= READ_BUDGET, "read-budget-exceeded")
        result["bytesRead"] += size

    def read(address, size):
        span(address, size)
        charge(size)
        data = session.read(address, size)
        _require(isinstance(data, bytes) and len(data) == size, "short-read")
        return data

    def word(address):
        return struct.unpack("<I", read(address, 4))[0]

    def nodes(head, work, work_size, seen, *, spare, capacity, alignment):
        blocks, previous, count = [], 0, 0
        while head:
            _require(count < work_size // 16 and len(seen) < work_size // 16,
                     "node-limit-exceeded")
            _require(head not in seen and work <= head <= work + work_size - 16
                     and (head - work) % 16 == 0, "node-outside-work-buffer-or-cycle")
            seen.add(head)
            # Stock pool pop does not reset the new head's previous link.
            # The spare chain owns only its next link; do not invent a prev
            # invariant that would reject valid native allocator state.
            if spare:
                following = word(head + 12)
            else:
                start, size, prev, following = struct.unpack("<4I", read(head, 16))
                _require(prev == previous and size > 0 and start % alignment == 0
                         and size % alignment == 0 and start < capacity
                         and size <= capacity - start, "invalid-free-block")
                blocks.append((start, size))
            previous, head = head, following
            count += 1
        if not spare:
            ordered = sorted(blocks)
            _require(all(a + n <= b for (a, n), (b, _) in zip(ordered, ordered[1:])),
                     "overlapping-free-blocks")
        return blocks, count

    try:
        for address, size, digest, name in STOCK_SEALS:
            charge(size)
            code = session.packaged_code(address, size)  # validates live/package identity
            _require(isinstance(code, bytes) and len(code) == size
                     and hashlib.sha256(code).hexdigest() == digest,
                     "stock-code-identity-differs:" + name)
            result["codeIdentity"].append({"name": name, "address": address,
                                           "size": size, "sha256": digest})

        # Reuse the named current field pointer, count its native four-byte read.
        charge(4)
        field = session.field_pointer()
        span(field, 0x70)
        field_refs = (word(field), word(field + 0x44), word(field + 0x6C))
        control, context, ready = field_refs
        _require(ready == 1, "field-not-ready")
        control_raw = read(control, 16)
        manager, application, paused, exiting = struct.unpack("<4I", control_raw)
        _require(application == paused == exiting == 0, "field-control-not-active")
        manager_raw = read(manager, 40)
        manager_values = struct.unpack("<10I", manager_raw)
        _require(manager_values[:4] == FIELD_TEMPLATE and manager_values[4:7] == (2, 0, field),
                 "field-manager-owner-or-phase-differs")

        context_raw = read(context, 0x24)
        context_values = struct.unpack("<9I", context_raw)
        heap, resource_count, parent, table = (context_values[i] for i in (0, 1, 4, 5))
        _require(heap == 4 and parent == field and 0 < resource_count <= MAX_RESOURCES,
                 "effect-context-owner-or-count-differs")
        # The stock constructor reaches the current native model manager via
        # context+0x20/state+0x0C. Its sealed allocator owns capacity+8/count+0xD4.
        # Read counts only; no slot scan, allocation, or guest work is performed.
        model_state = context_values[8]
        _require(model_state != 0, "model-pool-state-absent")
        model_state_raw = read(model_state, 0x24)
        model_values = struct.unpack("<9I", model_state_raw)
        pool = model_values[3]
        _require(model_values[0] == 4 and (model_values[1] & 0xFFFF) == 48,
                 "model-pool-config-differs")
        _require(pool != 0, "model-pool-manager-absent")
        span(pool, 0xD8)
        pool_header_raw = read(pool, 12)
        capacity = struct.unpack_from("<I", pool_header_raw, 8)[0]
        pool_count_raw = read(pool + 0xD4, 4)
        allocated = struct.unpack("<I", pool_count_raw)[0]
        _require(capacity == 48 and 0 <= allocated <= capacity,
                 "model-pool-capacity-or-count-differs")
        table_raw = read(table, resource_count * 8)
        entries = list(struct.iter_unpack("<2I", table_raw))
        owners = [pointer for resource, pointer in entries if resource == 0x12]
        _require(len(owners) == 1, "bubble-owner-resource-not-unique")
        owner = owners[0]
        owner_raw = read(owner, 148)
        bubble = decode_emote_owner(owner, context, owner_raw)
        busy = bubble["activeCount"]

        dispatch_raw = read(DISPATCH, 16)
        _require(struct.unpack("<4I", dispatch_raw) == DISPATCH_WORDS,
                 "current-vram-allocator-is-not-sealed-linked-mode")
        tex_raw = read(TEXTURE_STATE, 28)
        tex_head, tex4_head, tex_spares, tex_capacity, tex4_capacity, tex_work, tex_work_size = \
            struct.unpack("<7I", tex_raw)
        _require((tex_capacity, tex4_capacity, tex4_head, tex_work_size) == (0x40000, 0, 0, 4096),
                 "field-texture-allocator-config-differs")
        span(tex_work, tex_work_size)
        palette_raw = read(PALETTE_STATE, 20)
        pal_head, pal_spares, pal_capacity, pal_work, pal_work_size = struct.unpack("<5I", palette_raw)
        _require((pal_capacity, pal_work_size) == (0x8000, 16384),
                 "field-palette-allocator-config-differs")
        span(pal_work, pal_work_size)
        _require(tex_work + tex_work_size <= pal_work or pal_work + pal_work_size <= tex_work,
                 "allocator-work-buffers-overlap")
        tex_seen = set()
        tex_blocks, tex_count = nodes(tex_head, tex_work, tex_work_size, tex_seen,
            spare=False, capacity=tex_capacity, alignment=16)
        _, tex_spare_count = nodes(tex_spares, tex_work, tex_work_size, tex_seen,
            spare=True, capacity=tex_capacity, alignment=16)
        pal_seen = set()
        pal_blocks, pal_count = nodes(pal_head, pal_work, pal_work_size, pal_seen,
            spare=False, capacity=pal_capacity, alignment=8)
        _, pal_spare_count = nodes(pal_spares, pal_work, pal_work_size, pal_seen,
            spare=True, capacity=pal_capacity, alignment=8)

        def summary(blocks, count, spares, requested, minimum_alignment):
            return {"known": True, "capacityBytes": 0x40000 if requested == 512 else 0x8000,
                    "freeBlockCount": count, "spareNodeCount": spares,
                    "totalFreeBytes": sum(size for _, size in blocks),
                    "largestFreeBytes": max((size for _, size in blocks), default=0),
                    "largestUsableBytes": max((max(0, size - ((-start) % minimum_alignment))
                        for start, size in blocks), default=0),
                    "additionalTwoSlots": _first_fit_two(blocks, spares, requested, minimum_alignment)}

        # Never publish partial free-space/fit facts after an owner change.
        _require(read(DISPATCH, 16) == dispatch_raw and read(TEXTURE_STATE, 28) == tex_raw
                 and read(PALETTE_STATE, 20) == palette_raw,
                 "allocator-owner-changed")
        _require(read(pool, 12) == pool_header_raw
                 and read(pool + 0xD4, 4) == pool_count_raw
                 and read(model_state, 0x24) == model_state_raw,
                 "model-pool-owner-or-count-changed")
        _require(read(owner, 148) == owner_raw and read(table, resource_count * 8) == table_raw
                 and read(context, 0x24) == context_raw and read(manager, 40) == manager_raw
                 and read(control, 16) == control_raw,
                 "field-or-bubble-owner-changed")
        _require((word(field), word(field + 0x44), word(field + 0x6C)) == field_refs,
                 "current-field-references-changed")
        charge(4)
        _require(session.field_pointer() == field and session.completed_frames == result["frame"]
                 and session.rt.EXECUTED_FRAME_COUNT == result["nativeCycle"],
                 "paused-endpoint-changed")
        texture = summary(tex_blocks, tex_count, tex_spare_count, 512, 16)
        palette = summary(pal_blocks, pal_count, pal_spare_count, 32, 16)
        result.update(known=True, reason=None, fieldPointer=field, contextPointer=context,
            bubble=bubble,
            modelPool={"known": True, "pointer": pool, "statePointer": model_state,
                "capacity": capacity, "allocatedCount": allocated,
                "freeSlots": capacity - allocated, "exhausted": allocated == capacity,
                "scope": "current native model-slot counts; diagnostic only"},
            texture=texture, palette=palette,
            canAdmitTwoAdditionalIndependentSlots=(texture["additionalTwoSlots"]["canAdmit"]
                and palette["additionalTwoSlots"]["canAdmit"]))
    except Exception as error:
        result["reason"] = str(error)[:240]
    return result
