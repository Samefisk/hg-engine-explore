/* Preserve the fixed overlay-2 ABI slots used by follower release. */
OUTPUT_ARCH(arm)
MEMORY {
        rom : ORIGIN = 0x02250114, LENGTH = 0x38C
        ewram : ORIGIN = 0x02250114, LENGTH = 0x38C
}

SECTIONS {
        .text : {
                FILL (0xABCD)
                KEEP(*(.follower_release_tick))
                ASSERT(. <= ORIGIN(rom) + 0x180,
                    "follower release tick exceeds fixed ABI slot");
                . = ORIGIN(rom) + 0x180;
                KEEP(*(.follower_release_render))
                *(.init)
                *(.text)
                *(.ctors)
                *(.dtors)
                *(.rodata)
                *(.fini)
                *(COMMON)
                *(.bss)
                . = ALIGN(4);
        } >rom = 0xff
}
