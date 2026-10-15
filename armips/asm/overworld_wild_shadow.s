.nds
.thumb

// Every stock native-shadow creation route passes the same four arguments.
// Filtering at these call sites prevents a later terrain callback from racing
// the authored-surface policy maintained by the overworld wild overlay.
.open "base/arm9.bin", 0x02000000

overworld_wild_native_shadow_filter equ 0x023BF36C

.org 0x0205FFD2
    bl overworld_wild_native_shadow_filter

.org 0x02060062
    bl overworld_wild_native_shadow_filter

.org 0x020603F2
    bl overworld_wild_native_shadow_filter

// sub_020601A4 clears unk94 on every stock move-start and tile-enter update.
// Wild motion sets BIT_MOVE_START each frame, so the clear would run before
// the draw and erase the water sink that the Wild owner keeps in unk94. Keep
// it for wild object IDs E0-E9; every other object is still cleared. Stock
// code never writes a nonzero unk94, so only Wild presentation is affected.
.org 0x020601A4
.area 0x18, 0x00
    ldr r1, [r0, #8]            // object->id
    sub r1, #0xE0
    cmp r1, #9
    bls @@keepWildSink
    mov r1, #0
    add r0, #0x94               // &object->unk94
    str r1, [r0]
    str r1, [r0, #4]
    str r1, [r0, #8]
@@keepWildSink:
    bx lr
.endarea

// sub_0206039C raises the stock shallow-water splash (MAPOBJECTFLAG_UNK26)
// and clears its flag on every other tile. Wild motion reaches it each frame
// with a stock tile behavior, so the clear would delete the splash that the
// water sink keeps on a submerged Wild body. Wild IDs E0-E9 keep the flag;
// OverworldWaterSink_Update clears it when they leave water. Shallow water
// and every other object behave as stock.
.org 0x0206039C
.area 0x34, 0x00
    push {r4, lr}
    add r4, r0, #0
    add r0, r1, #0
    bl 0x0205B7A4               // MetatileBehavior_IsShallowWater
    cmp r0, #0
    bne @@shallow
    ldr r1, [r4, #8]            // object->id
    sub r1, #0xE0
    cmp r1, #9
    bls @@done
@@setFlag:
    add r1, r0, #0
    add r0, r4, #0
    bl 0x0205F7EC               // MapObject_SetFlag26
@@done:
    pop {r4, pc}
@@shallow:
    ldr r0, [r4]                // object->flags
    lsl r0, r0, #5              // MAPOBJECTFLAG_UNK26
    bmi @@done
    add r0, r4, #0
    mov r1, #1
    bl 0x021FF4FC               // shallow-water splash
    mov r0, #1
    b @@setFlag
.endarea

// sub_02060020 (the BIT_JUMP_START terrain update) clears the same flag
// through sub_020603D0. Wild hops set BIT_JUMP_START every frame, so a
// submerged hop would get a new splash each frame while the old ones stay
// alive and fill the field-effect pool. Route it through the filter above
// with a non-shallow behavior: other objects are still cleared.
.org 0x02060074
    mov r1, #0
.org 0x0206007A
    bl 0x0206039C

// sub_020601BC (move start) and sub_02060274 (move end) raise the tall-grass
// rustle. Wild motion starts a move each frame, so route both calls through
// overlay 2's gate (OVERWORLD_WATER_SINK_GRASS_ADDR): one rustle per tile
// entered, none while airborne. Other objects pass straight through to
// ov01_021FF070.
.org 0x020601EA
    bl 0x022500B0
.org 0x020602A2
    bl 0x022500B0

// sub_0205DA34 (player step collision) ends with "add r0, r4, #0; pop
// {r3-r7, pc}". Overlay 2's water sink takes that return (player object in
// r6, facing in r7): a deep-water step is open while riding a Water Runner
// mount, or while already standing on deep water without surfing.
.org 0x0205DAA2
    bl 0x022504A0

.close

// Both stock native-shadow variants test UNK9/UNK20 immediately before
// updating their field effect.  Route that visibility decision through the
// resident policy as well, so a later movement command cannot make an
// already-created shadow visible on an authored no-shadow surface.
.open "base/overlay/overlay_0001.bin", 0x021E5900

overworld_wild_native_shadow_visibility_filter equ 0x023BF39C
overworld_wild_native_shadow_position_filter equ 0x023BF3BC

.org 0x021FD752
    bl overworld_wild_native_shadow_visibility_filter

.org 0x021FD950
    bl overworld_wild_native_shadow_visibility_filter

.org 0x021FD76E
    bl overworld_wild_native_shadow_position_filter

.org 0x021FD96C
    bl overworld_wild_native_shadow_position_filter

// The stock hidden-state stores share their word with the encounter token.
// Store only the low half so hiding a shadow cannot erase its identity.
.org 0x021FD766
    strh r0, [r4, 0xC]

.org 0x021FD964
    strh r0, [r4, 0xC]

// The matching draw callbacks must also read only the hidden-state half.
// Otherwise the nonzero encounter token in the high half is mistaken for a
// hidden shadow (or prevents the hidden variant from being recognized).
.org 0x021FD7DC
    ldrh r0, [r2, 0xC]

.org 0x021FD840
    ldrh r0, [r2, 0xC]

.org 0x021FD986
    ldrh r1, [r4, 0xC]

// The circle shadow can fail to get a model from the bounded field pool.
// The stock code stores that result at +0x24, then marks +0xC ready even
// when it is NULL. Its draw and destroy callbacks then use a NULL model.
// Models are allocated on the main-RAM heap (0x02000000..0x023FFFFF).
// Convert that pointer to the stock exact 0/1 ready flag in the same slot:
// NULL stays not ready, so the existing update retries model admission.
.org 0x021FDD8A
    lsr r0, r0, 25

// The shallow-water splash draw (ov01_021FF658) hands its waterline position
// to sub_02023E50 with the task work in r5. Overlay 2's water sink lowers it
// for a submerged Wild body (OVERWORLD_WATER_SINK_SPLASH_ADDR); every other
// splash is passed through unchanged.
.org 0x021FF6A8
    bl 0x0224FFF0

// The reflection draw (ov01_021FDBCC) does the same with its record. The
// water sink anchors a submerged Wild body's cropped reflection on the body's
// waterline (OVERWORLD_WATER_SINK_MIRROR_ADDR); others stay stock.
.org 0x021FDC48
    bl 0x0224FFF8

.close
