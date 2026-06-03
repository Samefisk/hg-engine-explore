.nds
.thumb

.open "base/arm9.bin", 0x02000000

// Movement 47 is within the ARM9 movement descriptor table but has a null
// descriptor in vanilla. For the current diagnostic checkpoint, alias it to the
// stock movement 3 descriptor so save/map load never depends on overlay 129.
.org 0x020FD2B0
    .word 0x020FD170

.close
