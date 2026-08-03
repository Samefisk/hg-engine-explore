/* Overlay 159 */
OUTPUT_ARCH(arm)
MEMORY {
        rom   : ORIGIN = 0x023BF480, LENGTH = 0xF80
        ewram : ORIGIN = 0x023BF480, LENGTH = 0xF80
}
SECTIONS {
        .text : {
                __text_start = .;
                OverworldWildRuntime_GetTimerCount = .;
                *overworld_wild_runtime_timers.o(.text*)
                *(.rodata*)
                *(.data*)
                . = ALIGN(4);
                __text_end = .;
                __bss_start__ = .;
                *(.bss*)
                *(COMMON)
                . = ALIGN(4);
                __bss_end__ = .;
                ASSERT(OverworldWildRuntime_GetTimerCount == ORIGIN(rom),
                    "overlay159 timer entry moved");
                ASSERT(__bss_end__ <= 0x023C0380,
                    "overlay159 exceeded guarded timer shard window");
                _end = __bss_end__;
                __end__ = __bss_end__;
        } > ewram
}
