.nds
.thumb

.open "base/arm9.bin", 0x02000000

// Movement 47 is within the ARM9 movement descriptor table but has a null
// descriptor in vanilla. Point it at the boot-loaded overlay 129 descriptor.
.org 0x020FD2B0
    .word goverworldwildcustommovementdescriptor

.close
