.nds
.thumb

.open "base/arm9.bin", 0x02000000

// Route FlyAnimation's scheduled field task through the C wrapper. The wrapper
// only changes behavior when the Mew warp script arms its one-shot flag.
.org 0x02068708
    .word script_mewflyanimationtask

.close
