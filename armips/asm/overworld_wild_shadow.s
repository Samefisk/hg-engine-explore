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

.close
