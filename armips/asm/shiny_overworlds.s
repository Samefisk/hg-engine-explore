.nds
.thumb

.open "base/overlay/overlay_0001.bin", 0x021E5900

.org 0x021F9374
.area 0x36
    ldr r3, =OverworldWildSpawns_LoadOverworldModelResource|1
    bx r3
    .pool
.endarea

.close
