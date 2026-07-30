/* Overlay 153 */
OUTPUT_ARCH(arm)
MEMORY {

        /*
         * Boot-resident move-history code occupies the otherwise unused gap
         * after every stock overlay and before custom overlay 152.
         */
        rom     : ORIGIN = 0x023BE400, LENGTH = 0x2000
        ewram   : ORIGIN = 0x023BE400, LENGTH = 0x2000
}

SECTIONS {
        .text : {

                FILL (0xABCD)

                __text_start = . ;
                KEEP(*(.pokemon_move_history_api))
                /*
                 * These entries must preserve r3 (and, for candidates, the
                 * stacked fifth argument), so keep their implementations
                 * within range of the fixed-width Thumb-1 branches.
                 */
                KEEP(*(.pokemon_move_history_short_branch_targets))
                ASSERT(MoveHistoryEntry_Init == ORIGIN(rom) + 0x00,
                    "move-history Init ABI moved");
                ASSERT(MoveHistoryEntry_Load == ORIGIN(rom) + 0x08,
                    "move-history Load ABI moved");
                ASSERT(MoveHistoryEntry_Reset == ORIGIN(rom) + 0x10,
                    "move-history Reset ABI moved");
                ASSERT(MoveHistoryEntry_CaptureSnapshot == ORIGIN(rom) + 0x18,
                    "move-history CaptureSnapshot ABI moved");
                ASSERT(MoveHistoryEntry_Seed == ORIGIN(rom) + 0x20,
                    "move-history Seed ABI moved");
                ASSERT(MoveHistoryEntry_RecordMove == ORIGIN(rom) + 0x28,
                    "move-history RecordMove ABI moved");
                ASSERT(MoveHistoryEntry_RecordSnapshot == ORIGIN(rom) + 0x30,
                    "move-history RecordSnapshot ABI moved");
                ASSERT(MoveHistoryEntry_Query == ORIGIN(rom) + 0x38,
                    "move-history Query ABI moved");
                ASSERT(MoveHistoryEntry_CommitIfDirty == ORIGIN(rom) + 0x40,
                    "move-history CommitIfDirty ABI moved");
                ASSERT(MoveHistoryEntry_LoadAndSeedParty == ORIGIN(rom) + 0x48,
                    "move-history LoadAndSeedParty ABI moved");
                ASSERT(MoveHistoryEntry_PrepareSave == ORIGIN(rom) + 0x50,
                    "move-history PrepareSave ABI moved");
                ASSERT(MoveHistoryEntry_FinishSave == ORIGIN(rom) + 0x58,
                    "move-history FinishSave ABI moved");
                ASSERT(MoveHistoryEntry_CancelSave == ORIGIN(rom) + 0x60,
                    "move-history CancelSave ABI moved");
                ASSERT(MoveHistoryEntry_WriteSaveNow == ORIGIN(rom) + 0x68,
                    "move-history WriteSaveNow ABI moved");
                ASSERT(MoveHistoryEntry_SaveGameNormal == ORIGIN(rom) + 0x70,
                    "move-history SaveGameNormal ABI moved");
                ASSERT(MoveHistoryEntry_BuildRelearnCandidates
                        == ORIGIN(rom) + 0x78,
                    "move-relearn candidate ABI moved");
                ASSERT(MoveHistoryEntry_ReplaceMove
                        == ORIGIN(rom) + 0x80,
                    "move-history ReplaceMove ABI moved");
                ASSERT(MoveHistoryEntry_DeleteMoveSlot
                        == ORIGIN(rom) + 0x88,
                    "move-history DeleteMoveSlot ABI moved");
                . = ALIGN(4);
                *(.init)
                *(.text)
                *(.ctors)
                *(.dtors)
                *(.rodata)
                *(.fini)
                *(COMMON)
                __text_end  = . ;

                __bss_start__ = . ;
                *(.bss)
                __bss_end__ = . ;
                ASSERT(__bss_end__ + 0x1000 <= ORIGIN(rom) + LENGTH(rom),
                    "move-history overlay exceeds guarded code envelope");
        _end = __bss_end__ ;
        __end__ = __bss_end__ ;
        } >rom = 0xff
}
