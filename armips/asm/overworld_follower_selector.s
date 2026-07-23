.nds
.thumb

// Vanilla movement already ignores Y. Disable only its registered-item action;
// the custom selector observes physical Y from an independent main-queue
// SysTask and does not patch FieldInput_Update's movement data path.
.open "base/overlay/overlay_0001.bin", 0x021E5900

.if readu16("base/overlay/overlay_0001.bin", 0x00001090) != 0xD104
    .error "FieldInput_Update physical Y item branch changed"
.endif

.org 0x021E6990
    nop

.close
