.nds
.thumb

// Retire the disabled vanilla follower-interaction graph while preserving the
// live field allocator/free ABI immediately after it.
.open "base/overlay/overlay_0002.bin", 0x02245B80
.org 0x0224EF80
.area 0x14, 0x00
    mov r0, 1
    bx lr
.endarea
.org 0x0224EF98
.area 0x8CC, 0x00
    .incbin "build/output_overworld_follower_selector_icons_overlay2.bin"
.endarea
// The retired graph from 0x0224F8FC hosts the Wild water sink, followed by
// the release presentation slots at their original 0x02250114 base and the
// water sink tail in the retired FollowMon_PlaceholdersSet span up to the
// live field allocator at 0x02250780.
.org 0x0224F8FC
.area 0xE84, 0x00
    .incbin "build/output_overworld_follower_release_overlay2.bin"
.endarea
.close
