.nds
.thumb

.open "base/arm9.bin", 0x02000000

// Movement 47 is within the ARM9 movement descriptor table but has a null
// descriptor in vanilla. For the current diagnostic checkpoint, alias it to the
// stock no-op movement 0 descriptor so stale movement-47 objects cannot run
// uninitialized stock movement state after loading old saves.
.org 0x020FD2B0
    .word 0x020FCEC8

.close
