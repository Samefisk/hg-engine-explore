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
.org 0x02250114
.area 0x38C, 0x00
    .incbin "build/output_overworld_follower_release_overlay2.bin"
.endarea
.close
