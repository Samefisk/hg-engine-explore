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

.close
