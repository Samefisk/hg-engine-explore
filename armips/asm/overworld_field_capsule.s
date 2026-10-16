.nds
.thumb

// Both stock graphics-table readers now point at gOWTagToFileNum. Keep the
// original overlay file/table/BSS/init and the following callback list intact.
.open "base/overlay/overlay_0001.bin", 0x021E5900
// The native parent must drain tint/recall callbacks before freeing graphics.
// Keep its stock init/exec and all stock exit instructions unchanged.
// Keep the stock Land model main-queue task, cursor, completion and cancel
// path. Bound only each first/continued sequential read to 4 KB. Both stock
// MOV instructions feed the unchanged <<12, comparisons and byte progress.
.if readu16("base/overlay/overlay_0001.bin", 0x00010D54) != 0x200E && readu16("base/overlay/overlay_0001.bin", 0x00010D54) != 0x2001
    .error "Land model first-read quantum changed"
.endif
.if readu16("base/overlay/overlay_0001.bin", 0x00010D86) != 0x200E && readu16("base/overlay/overlay_0001.bin", 0x00010D86) != 0x2001
    .error "Land model continued-read quantum changed"
.endif
.org 0x021F6654
.area 2
    mov r0, #1
.endarea
.org 0x021F6686
.area 2
    mov r0, #1
.endarea

.org 0x02206380
    .word 0x02208701
.org 0x022074A8
.area 0x1524, 0x00
    .incbin "build/output_overworld_field_capsule.bin"
.endarea
.close
