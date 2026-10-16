#!/usr/bin/env python3
"""Authenticate and transport the three-slot stock emote owner.

Actor remains boot-resident. Only its three named Overlay1 sections are copied;
stock script/update/draw/animation owners and all existing entries stay fixed.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import struct

if __package__:
    from .pack_overworld_combat_capsules import section_bytes
    from .verify_pokemon_move_history_capture import (
        bytes_at, elf_bytes_at, elf_helper_bindings, packaged_thumb_calls,
    )
else:
    from pack_overworld_combat_capsules import section_bytes
    from verify_pokemon_move_history_capture import (
        bytes_at, elf_bytes_at, elf_helper_bindings, packaged_thumb_calls,
    )

ACTOR_BASE, ACTOR_SIZE, ACTOR_BSS = 0x023B65C0, 0x3BB0, 0x988
DESCRIPTOR_WORDS = (0x68, 0x02203B29, 0x02203A21, 0x023BA09D, 0x02203DC1)
HOOKS = ((0x02203A18, "OverworldEmoteSlots_CreateOwner"),
         (0x02203A38, "OverworldEmoteSlots_DestroyOwner"),
         (0x02203A58, "OverworldEmoteSlots_AfterModelAdmission"))
STOCK_BASE = 35543296

STOCK_SIZE = 148064

STOCK_BSS = 245792
STOCK_STATIC_INIT = (0x02209810, 0x02209814)

SECTIONS = [('.overworld_emote_initialize',
  35666728,
  376,
  376,
  '762311ceed6af8f315e53b089ef236819f04088581c561642e88431f5be54062',
  '33bb88c558207a8e0d4a3c6c60c3ba557ee0e193cf5c83c2cfffe2d6a2eeac3f'),
 ('.overworld_emote_release',
  35666528,
  84,
  84,
  'dda9a9c0b7ad4fb26a6d574d38d46451ee4910cae7d6f28c017268999df113ba',
  'fe101e0782150cd744895d1e3f6c1fd4636aaac0f095f0dd89fae49c01e02f55'),
 ('.overworld_emote_destroy',
  35666464,
  24,
  22,
  '358e06e56c93d41c17e097308342ae71020870df03dff8a67b3d67d1b79791cd',
  '6d86f136277183998f0bc134fb2232af13909f2104bb1099c6e209c41ae2d689')]

OWNERS = {'OverworldEmoteSlots_Select': (37455277,
                                44,
                                'FUNC',
                                'aad730ba2ba51e6b02e17500ad5b086d3587d72d980ee3cddb28efc343e58be8'),
 'OverworldEmoteSlots_LoadMember': (35667045,
                                    52,
                                    'FUNC',
                                    'a3cd0d64c5aac6e14e58ad10a8bc3cc07bd5a6b1cef4a1af094cbc5980b7bd3f'),
 'OverworldEmoteSlots_Update': (37462173,
                                28,
                                'FUNC',
                                '9c69a93934a288a6b9238f9f27e8285aefe1a6ce274382ccc8e19a85f058382e'),
 'OverworldEmoteSlots_Initialize': (35666729,
                                    316,
                                    'FUNC',
                                    '5529dd0bea1f91d2694c3fa340466cedffc78f186db49b1ea29db55e32e4b921'),
 'OverworldEmoteSlots_Prepare': (37462045,
                                 128,
                                 'FUNC',
                                 'f1950ff831f0571f620d85623b2412a394d682732f5b349d6f8f8760ad287763'),
 'OverworldEmoteSlots_Retire': (37455821,
                                40,
                                'FUNC',
                                'c06780fd8840c7fce35e364b55f085ba332a7f940596b46a895b34bdaa7c1890'),
 'OverworldEmoteSlots_Destroy': (35666465,
                                 22,
                                 'FUNC',
                                 '358e06e56c93d41c17e097308342ae71020870df03dff8a67b3d67d1b79791cd'),
 'OverworldEmoteSlots_Release': (35666529,
                                 84,
                                 'FUNC',
                                 'dda9a9c0b7ad4fb26a6d574d38d46451ee4910cae7d6f28c017268999df113ba'),
 'OverworldEmoteSlots_Collect': (37455169,
                                 108,
                                 'FUNC',
                                 'd12c3876420b5df3cd2a938aea8fcf6963893acb2860c10efa331536f9618127'),
 'descriptor': (37455320,
                20,
                'OBJECT',
                'fc6a51ccfff979db453bd2bf14a5240951401e3cebc17dffd829071a6aa5a729'),
 'OverworldEmoteSlots_DestroyOwner': (37455769,
                                      52,
                                      'FUNC',
                                      'ba2c3af26f79d53220a6f8355964efa065ecd8a06c2e8c93c05dfe2fc71ba6a9'),
 'OverworldEmoteSlots_CreateOwner': (37455657,
                                     112,
                                     'FUNC',
                                     'ec079ea49fed2258c2d2a0ae301590910518f6ea963eedec9b48a6cf5f1c3eb8'),
 'OverworldEmoteSlots_AfterModelAdmission': (37455341,
                                             14,
                                             'FUNC',
                                             '753c10a3de712e0d14b13ab904a7c2723ffa35a8509cef7cb11f54719431d254'),
 'OverworldEmoteSlots_Admit': (37458193,
                               272,
                               'FUNC',
                               'd1210539d613061cbee646211a77522a3a00605f346cef68ae90575cd1c1ee8d')}

IMPORTS = {'GF_CreateNewVramTransferTask': (33687001, 'FUNC'),
 'GF_GetNumPendingVramTransferTasks': (33687097, 'FUNC'),
 'MapObject_CopyFacingVector': (33945965, 'FUNC'),
 'MapObject_CopyPositionVector': (33945925, 'FUNC'),
 'MapObject_GetID': (33944141, 'FUNC'),
 'MapObject_GetMapID': (33944149, 'FUNC'),
 'MapObject_GetPriority': (33944889, 'FUNC'),
 'NNS_G3dGetTex': (34356048, 'FUNC'),
 'NNS_G3dMdlSetMdlFogEnableFlagAll': (34354904, 'FUNC'),
 'NNS_GfdDefaultFuncAllocPlttVram': (34670892, 'OBJECT'),
 'NNS_GfdDefaultFuncAllocTexVram': (34670884, 'OBJECT'),
 'NNS_GfdDefaultFuncFreePlttVram': (34670896, 'OBJECT'),
 'NNS_GfdDefaultFuncFreeTexVram': (34670888, 'OBJECT'),
 'OverworldEmoteSlots_StockMemset': (34495300, 'FUNC'),
 'PlaySE': (33579085, 'FUNC'),
 'SysTask_CreateOnVWaitQueue': (33612661, 'FUNC'),
 'SysTask_Destroy': (33612689, 'FUNC'),
 'ov01_021F141C': (35591197, 'FUNC'),
 'ov01_021F1448': (35591241, 'FUNC'),
 'ov01_021F1450': (35591249, 'FUNC'),
 'ov01_021F149C': (35591325, 'FUNC'),
 'ov01_021F14A8': (35591337, 'FUNC'),
 'ov01_021F1640': (35591745, 'FUNC'),
 'ov01_021F16EC': (35591917, 'FUNC'),
 'ov01_02203CB8': (35667129, 'FUNC'),
 'ov01_02203DC0': (35667393, 'FUNC'),
 'ov01_0220952C': (35689772, 'OBJECT'),
 'sub_02020838': (33687609, 'FUNC'),
 'sub_02020888': (33687689, 'FUNC'),
 'sub_020209AC': (33687981, 'FUNC'),
 'sub_02023DA4': (33701285, 'FUNC'),
 'sub_02023EA4': (33701541, 'FUNC'),
 'sub_02023F90': (33701777, 'FUNC'),
 'sub_02026E18': (33713689, 'FUNC'),
 'sub_02068B0C': (33983245, 'FUNC'),
 'sub_02068D98': (33983897, 'FUNC'),
 'sub_02068DB8': (33983929, 'FUNC'),
 'MIi_CpuClear32': (34424812, 'FUNC')}

CALLS = {'OverworldEmoteSlots_Select': [],
 'OverworldEmoteSlots_LoadMember': [(35667052, 'blx_reg', 3),
                                    (35667062, 'blx_reg', 3),
                                    (35667076, 'blx_reg', 3)],
 'OverworldEmoteSlots_Update': [(37462182, 'blx_reg', 3), (37462188, 'blx_reg', 3)],
 'OverworldEmoteSlots_Initialize': [(35666738, 'blx_reg', 3),
                                    (35666750, 'bl', 35667096),
                                    (35666782, 'blx_reg', 7),
                                    (35666790, 'blx_reg', 3),
                                    (35666800, 'blx_reg', 3),
                                    (35666832, 'blx_reg', 3),
                                    (35666840, 'blx_reg', 3),
                                    (35666856, 'blx_reg', 7),
                                    (35666890, 'blx_reg', 3),
                                    (35666896, 'blx_reg', 3),
                                    (35666904, 'blx_reg', 3),
                                    (35666922, 'blx_reg', 3),
                                    (35666934, 'blx_reg', 4),
                                    (35666952, 'blx_reg', 3),
                                    (35666962, 'blx_reg', 4),
                                    (35666972, 'blx_reg', 3)],
 'OverworldEmoteSlots_Prepare': [(37462056, 'bl', 35667044),
                                 (37462068, 'bl', 35667044),
                                 (37462086, 'blx_reg', 3),
                                 (37462108, 'blx_reg', 3),
                                 (37462126, 'blx_reg', 3),
                                 (37462144, 'blx_reg', 3)],
 'OverworldEmoteSlots_Retire': [(37455842, 'blx_reg', 3)],
 'OverworldEmoteSlots_Destroy': [(35666480, 'bl', 37455820)],
 'OverworldEmoteSlots_Release': [(35666542, 'blx_reg', 3),
                                 (35666554, 'blx_reg', 3),
                                 (35666564, 'blx_reg', 3),
                                 (35666574, 'blx_reg', 3),
                                 (35666586, 'blx_reg', 3)],
 'OverworldEmoteSlots_Collect': [(37455176, 'blx_reg', 3),
                                 (37455192, 'bl', 35666528),
                                 (37455206, 'bl', 35666528),
                                 (37455224, 'bl', 35666528),
                                 (37455238, 'blx_reg', 3),
                                 (37455252, 'blx_reg', 5),
                                 (37455256, 'blx_reg', 5),
                                 (37455260, 'blx_reg', 5)],
 'OverworldEmoteSlots_DestroyOwner': [(37455792, 'blx_reg', 3),
                                      (37455798, 'blx_reg', 5),
                                      (37455802, 'blx_reg', 5),
                                      (37455806, 'blx_reg', 5)],
 'OverworldEmoteSlots_CreateOwner': [(37455666, 'blx_reg', 3),
                                     (37455676, 'bl', 37462376),
                                     (37455686, 'bl', 35667044),
                                     (37455696, 'bl', 35667044),
                                     (37455718, 'blx_reg', 5),
                                     (37455726, 'blx_reg', 5),
                                     (37455730, 'blx_reg', 5),
                                     (37455738, 'blx_reg', 3)],
 'OverworldEmoteSlots_AfterModelAdmission': [(37455346, 'bl', 37458192)],
 'OverworldEmoteSlots_Admit': [(37458206, 'blx_reg', 3),
                               (37458240, 'bl', 37455276),
                               (37458260, 'bl', 37462376),
                               (37458284, 'bl', 37462044),
                               (37458298, 'blx_reg', 3),
                               (37458306, 'blx_reg', 3),
                               (37458342, 'blx_reg', 3),
                               (37458362, 'blx_reg', 6),
                               (37458370, 'bl', 37455820),
                               (37458376, 'blx_reg', 3),
                               (37458384, 'bl', 35666528),
                               (37458398, 'blx_reg', 3),
                               (37458412, 'blx_reg', 3)]}

STOCK_SEALS = [(35666496,
  8,
  '6524593d60960f1d3ff3e2f46471babc38a8aa7f463a74f9555d37ff4b422f73',
  'redirected owner destructor tail'),
 (35666504,
  8,
  'b2fd034f326d279808b576138192d18c92d67ea5ae944da02f7e1374a845e27f',
  'stock admission frame'),
 (35666612,
  116,
  '67dcdada12cfd3c97ad2034c5c7af317108cfe737e2c890bcfd3a00fb4938c39',
  'stock script start and waiter'),
 (35667104,
  24,
  '27b883ccbb6757a9a352ec71da9312b7b196195190b8383d9b197252c3aaad7f',
  'stock unused original effect destructor'),
 (35667128, 264, 'c3e72356a7ebebba70471de002645e33142657a39d07012229b44e7bd6b849d8', 'stock update'),
 (35667392, 56, '9ce365df23548e41a0e269c36471c6cf660054e4dceba797535173b9ee4abb50', 'stock draw'),
 (35667448,
  68,
  'a7186d4f0a61b46c422e7c3c8fbef8c2ed45cbbb377ba2b686e2ed77d9f8ad32',
  'stock animation frame'),
 (35689752,
  32,
  'd8755f2d3773957cb72e555b17303e2d1973c28ceee7951a4182ab51978b5688',
  'stock descriptor and animation material data')]

SDK_SEALS = [(34424812, 28, '234da5c7e8e76dbad0ffa50de07656f92dea67450b7905091f3e46d53bcdcaf5', 'whole-slot clear'),
 (34495300, 20, '1bd80632456971c08c1131ba63a0a0951f613e94bb6074310a7ab050d15f3e07', 'resident memset'),
 (33687096,
  28,
  '1e51a5923bec99a80e41e91973624dd3cc89987e3a8f417e35c6fcabb574f206',
  'pending transfer count')]

ALLOCATOR_DISPATCH = (34298300, 34298308, 34298316, 34298324)

MODEL_GUARD = (37617565, 48, '252b1bad483bb512bef5b55d765ce317123e17ccbcd12e65bccffdfef9b37b58')


def require(value, reason):
    if not value:
        raise ValueError("emote slots: " + reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def owner_contract(bindings, bodies):
    for name, (address, size, kind, sealed) in OWNERS.items():
        actual = bindings.get(name)
        require(actual is not None and actual[:3] == (address, size, kind)
                and actual[3].isdigit() and int(actual[3]) > 0,
                name + " typed owner/mode/extent differs")
        require(digest(bodies[name]) == sealed, name + " complete body differs")
        if kind == "FUNC":
            require(packaged_thumb_calls(bodies[name], address & ~1,
                        address & ~1, size) == CALLS[name],
                    name + " exact native calls differ")
    require(struct.unpack("<5I", bodies["descriptor"]) == DESCRIPTOR_WORDS,
            "native descriptor/callback ownership differs")
    for name, (address, kind) in IMPORTS.items():
        require(bindings.get(name) == (address, 0, kind, "ABS"),
                name + " typed native import/mode differs")


def source_contract(linked):
    bindings = elf_helper_bindings(linked, (*OWNERS, *IMPORTS))
    bodies = {name: elf_bytes_at(linked, address & ~1, size)
              for name, (address, size, _kind, _hash) in OWNERS.items()}
    owner_contract(bindings, bodies)
    segments = {}
    for section, address, cap, used, sealed, _original in SECTIONS:
        payload = section_bytes(linked, section, address, cap)
        require(digest(payload[:used]) == sealed and payload[used:] == bytes(cap-used),
                section + " exact extent/body/filler differs")
        segments[section] = payload
    # Link-generated ARM veneers are private named functions, not a Wild import.
    for address, encoded in ((0x02203C98, "7847fde7a887fbea"),
                             (0x023BA168, "7847fde774aef4ea")):
        require(elf_bytes_at(linked, address, 8) == bytes.fromhex(encoded),
                "resident stock memset interworking veneer differs")
    return bindings, bodies, segments


def redirect(address):
    # Exact aligned eight-byte r2 redirect produced by existing make.py:Hook.
    return bytes.fromhex("004a1047") + struct.pack("<I", address | 1)


def protected_contract(stock, stock_base, arm9, arm9_base, bindings, model_guard):
    require(stock_base == STOCK_BASE and len(stock) == STOCK_SIZE,
            "stock Overlay1 loaded range changed")
    for address, size, sealed, label in STOCK_SEALS:
        require(digest(bytes_at(stock, stock_base, address, size)) == sealed,
                label + " body/data differs")
    for address, name in HOOKS:
        require(bytes_at(stock, stock_base, address, 8) == redirect(bindings[name][0]),
                name + " native hook target/frame differs")
    require(bytes_at(stock, stock_base, 0x02203A50, 8) == redirect(MODEL_GUARD[0]),
            "existing model admission hook differs")
    require(model_guard == (MODEL_GUARD[0], MODEL_GUARD[1], "FUNC", model_guard[3])
            and model_guard[3].isdigit() and int(model_guard[3]) > 0,
            "existing model admission typed owner/mode differs")
    for address, size, sealed, label in SDK_SEALS:
        require(digest(bytes_at(arm9, arm9_base, address, size)) == sealed,
                label + " named ARM9 owner differs")
    require(struct.unpack("<4I", bytes_at(arm9, arm9_base, 0x02110924, 16))
            == ALLOCATOR_DISPATCH, "native texture/palette dispatch differs")


def package_contract(linked, core_linked, stock, stock_base, actor, actor_base,
                     arm9, arm9_base, allow_original=False):
    bindings, bodies, segments = source_contract(linked)
    require(actor_base == ACTOR_BASE and len(actor) == ACTOR_SIZE,
            "Actor loaded range differs")
    require(actor == elf_bytes_at(linked, ACTOR_BASE, ACTOR_SIZE),
            "Actor image differs from linked source")
    model = elf_helper_bindings(core_linked, ("OverworldBubbleEffect_ModelAdmissionGuard",))
    guard = model.get("OverworldBubbleEffect_ModelAdmissionGuard")
    require(guard is not None, "model admission owner missing")
    require(digest(elf_bytes_at(core_linked, MODEL_GUARD[0] & ~1, MODEL_GUARD[1]))
            == MODEL_GUARD[2], "existing model admission complete body differs")
    protected_contract(stock, stock_base, arm9, arm9_base, bindings, guard)
    for section, address, cap, _used, _sealed, original in SECTIONS:
        actual = bytes_at(stock, stock_base, address, cap)
        require(actual == segments[section] or allow_original and digest(actual) == original,
                section + " packaged source/copy differs")
    return segments


def metadata_contract(rows):
    for number, base, size, bss in ((1, STOCK_BASE, STOCK_SIZE, STOCK_BSS),
                                  (158, ACTOR_BASE, ACTOR_SIZE, ACTOR_BSS)):
        row = rows[number]
        init = STOCK_STATIC_INIT if number == 1 else (0, 0)
        require(row == (number, base, size, bss, *init, number, 0),
                "Overlay" + str(number) + " exact metadata/lifetime differs")


def install_emote_slots(build, stock_path, actor_path, table_path, arm9_path):
    table = table_path.read_bytes()
    require(len(table) >= 159 * 32, "overlay table truncated")
    metadata_contract({n: struct.unpack_from("<8I", table, n*32) for n in (1,158)})
    stock, actor, arm9 = stock_path.read_bytes(), actor_path.read_bytes(), arm9_path.read_bytes()
    linked = build / "overworld_actor_system_overlay_linked.o"
    segments = package_contract(linked, build/"linked.o", stock, STOCK_BASE,
                                actor, ACTOR_BASE, arm9, 0x02000000, True)
    patched = bytearray(stock)
    for section, address, cap, _used, _hash, _original in SECTIONS:
        patched[address-STOCK_BASE:address-STOCK_BASE+cap] = segments[section]
    package_contract(linked, build/"linked.o", bytes(patched), STOCK_BASE,
                     actor, ACTOR_BASE, arm9, 0x02000000)
    # Compare the rest byte for byte; replacement never changes an overlay extent.
    for i, (before, after) in enumerate(zip(stock, patched)):
        require(before == after or any(a-STOCK_BASE <= i < a-STOCK_BASE+c
                                      for _s,a,c,_u,_h,_o in SECTIONS),
                "copy changed an unrelated stock byte")
    for section, _address, _cap, _used, _hash, _original in SECTIONS:
        (build / (section[1:] + ".bin")).write_bytes(segments[section])
    receipt = {"schema": "overworld-emote-slots-v1", "slotCount": 3,
               "actorLinkedSha256": digest(linked.read_bytes()),
               "stockOverlaySha256": digest(patched),
               "actorOverlaySha256": digest(actor),
               "sections": {name: digest(body) for name, body in segments.items()}}
    (build/"overworld_emote_slots.package.json").write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    if bytes(patched) != stock:
        temporary = stock_path.with_suffix(stock_path.suffix + ".emote.tmp")
        temporary.write_bytes(patched)
        temporary.replace(stock_path)
    return receipt


def verify_packaged_emote_slots(build, arm9_base, arm9, overlays):
    require(digest(bytes_at(overlays[129].data, overlays[129].ram_address,
                             MODEL_GUARD[0] & ~1, MODEL_GUARD[1])) == MODEL_GUARD[2],
            "packaged original model admission guard differs")
    metadata_contract({n: (c.overlay_id,c.ram_address,c.ram_size,c.bss_size,
                          c.static_init_start,c.static_init_end,c.file_id,c.flags)
                       for n in (1,158) for c in (overlays[n],)})
    segments = package_contract(build/"overworld_actor_system_overlay_linked.o",
                    build/"linked.o", overlays[1].data, STOCK_BASE,
                    overlays[158].data, ACTOR_BASE, arm9, arm9_base)
    for name, body in segments.items():
        require((build/(name[1:]+".bin")).read_bytes() == body,
                name + " extracted sealed output differs")
    receipt = json.loads((build/"overworld_emote_slots.package.json").read_text())
    require(receipt == {"schema": "overworld-emote-slots-v1", "slotCount": 3,
        "actorLinkedSha256": digest((build/"overworld_actor_system_overlay_linked.o").read_bytes()),
        "stockOverlaySha256": digest(overlays[1].data),
        "actorOverlaySha256": digest(overlays[158].data),
        "sections": {name: digest(body) for name, body in segments.items()}},
        "source/copy/package receipt differs")
    controls = copied_owner_controls(*source_contract(build/"overworld_actor_system_overlay_linked.o")[:2])
    return {"slotCount": 3, "copiedNativeRejections": controls, "authenticatedOwnerBodies": len(OWNERS),
            "typedNativeImports": len(IMPORTS), "stockSpansUnchanged": len(STOCK_SEALS)}


def seal_final_package(build, base):
    """Seal after the normal Field patches; retain the complete final image hash."""
    table = (base / "overarm9.bin").read_bytes()
    metadata_contract({n: struct.unpack_from("<8I", table, n * 32) for n in (1, 158)})
    stock = (base / "overlay/overlay_0001.bin").read_bytes()
    actor = (base / "overlay/overlay_0158.bin").read_bytes()
    linked = build / "overworld_actor_system_overlay_linked.o"
    segments = package_contract(linked, build / "linked.o", stock, STOCK_BASE,
                                actor, ACTOR_BASE, (base / "arm9.bin").read_bytes(),
                                0x02000000)
    receipt = {"schema": "overworld-emote-slots-v1", "slotCount": 3,
               "actorLinkedSha256": digest(linked.read_bytes()),
               "stockOverlaySha256": digest(stock),
               "actorOverlaySha256": digest(actor),
               "sections": {name: digest(body) for name, body in segments.items()}}
    (build / "overworld_emote_slots.package.json").write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + "\n")


def copied_owner_controls(bindings, bodies):
    """One current-native fixture; copied missing ownership/mode/byte faults fail."""
    owner_contract(bindings, bodies)
    checked = 0
    for name in OWNERS:
        for label in ("missing", "wrong-mode", "wrong-extent", "wrong-type", "body"):
            wrong_bindings, wrong_bodies = dict(bindings), dict(bodies)
            value = wrong_bindings[name]
            if label == "missing": del wrong_bindings[name]
            elif label == "wrong-mode": wrong_bindings[name] = (value[0] ^ 1, *value[1:])
            elif label == "wrong-extent": wrong_bindings[name] = (value[0], value[1]+2, *value[2:])
            elif label == "wrong-type": wrong_bindings[name] = (*value[:2], "NOTYPE", value[3])
            else:
                changed = bytearray(wrong_bodies[name]); changed[0] ^= 1
                wrong_bodies[name] = bytes(changed)
            try: owner_contract(wrong_bindings, wrong_bodies)
            except ValueError: checked += 1
            else: raise ValueError("emote slots: copied " + name + "/" + label + " was accepted")
    for name in IMPORTS:
        wrong = dict(bindings); address,size,_kind,section = wrong[name]
        wrong[name] = (address,size,"NOTYPE",section)
        try: owner_contract(wrong, bodies)
        except ValueError: checked += 1
        else: raise ValueError("emote slots: untyped copied import was accepted: " + name)
    return checked


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seal-final-package", action="store_true", required=True)
    parser.parse_args()
    seal_final_package(Path("build"), Path("base"))
