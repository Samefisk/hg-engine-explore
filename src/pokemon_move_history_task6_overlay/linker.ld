/* Overlay 155 */
OUTPUT_ARCH(arm)
MEMORY {
        /*
         * Boot-resident task-6 transaction helpers occupy the audited gap
         * immediately below resident move-history overlay 153.
         */
        rom     : ORIGIN = 0x023BD400, LENGTH = 0x1000
        ewram   : ORIGIN = 0x023BD400, LENGTH = 0x1000
}

SECTIONS {
        .text : {
                FILL (0xABCD)
                __text_start = . ;
                KEEP(*(.pokemon_move_history_task6_api))
                KEEP(*(.pokemon_move_history_task6_data))
                ASSERT(gPokemonMoveHistoryTask6PartyMenuSignalStorage
                        == ORIGIN(rom) + 0x60,
                    "task-6 private resident data moved");
                KEEP(*(.pokemon_move_history_task6_post_data_api))
                ASSERT(MoveHistoryTask6Entry_ScriptTeachMove
                        == ORIGIN(rom) + 0x64,
                    "task-6 scripted move ABI moved");
                ASSERT(MoveHistoryTask6Entry_GTSPlaceAndSeed
                        == ORIGIN(rom) + 0x68,
                    "task-6 GTS placement ABI moved");
                ASSERT(MoveHistoryTask6Entry_GTSDeleteBoxAndRecord
                        == ORIGIN(rom) + 0x70,
                    "task-6 GTS box removal ABI moved");
                ASSERT(MoveHistoryTask6Entry_GTSRemovePartyAndRecord
                        == ORIGIN(rom) + 0x78,
                    "task-6 GTS party removal ABI moved");
                ASSERT(MoveHistoryTask6Entry_PokewalkerRadioSuccess
                        == ORIGIN(rom) + 0x80,
                    "task-6 Pokewalker first success ABI moved");
                ASSERT(MoveHistoryTask6Entry_PokewalkerRadioSuccessSecond
                        == ORIGIN(rom) + 0x88,
                    "task-6 Pokewalker second success ABI moved");
                ASSERT(MoveHistoryTask6Entry_PokewalkerRecoverAndDiscard
                        == ORIGIN(rom) + 0x90,
                    "task-6 Pokewalker recovery ABI moved");
                ASSERT(MoveHistoryTask6Entry_PokewalkerDiagnosticReturn
                        == ORIGIN(rom) + 0x98,
                    "task-6 Pokewalker diagnostic return ABI moved");
                ASSERT(MoveHistoryTask6Entry_FieldReadyDiagnosticPoll
                        == ORIGIN(rom) + 0xA0,
                    "task-6 field-ready diagnostic poll ABI moved");
                ASSERT(. == ORIGIN(rom) + 0xA8,
                    "task-6 diagnostic mailbox ABI moved");
                KEEP(*(.pokemon_move_history_task6_diagnostic_data))
                ASSERT(. == ORIGIN(rom) + 0xD8,
                    "task-6 diagnostic mailbox size differs");
                KEEP(*(.pokemon_move_history_task6_short_branch_targets))
                ASSERT(MoveHistoryTask6Entry_IsCanonical
                        == ORIGIN(rom) + 0x00,
                    "task-6 canonical validator ABI moved");
                ASSERT(MoveHistoryTask6Entry_DaycareDepositCommit
                        == ORIGIN(rom) + 0x08,
                    "task-6 daycare ABI moved");
                ASSERT(MoveHistoryTask6Entry_TradeReplacePartySlot
                        == ORIGIN(rom) + 0x10,
                    "task-6 trade ABI moved");
                ASSERT(MoveHistoryTask6Entry_HatchClearEgg
                        == ORIGIN(rom) + 0x18,
                    "task-6 hatch ABI moved");
                ASSERT(MoveHistoryTask6Entry_PCStorageGetAndSeed
                        == ORIGIN(rom) + 0x20,
                    "task-6 Pokewalker export ABI moved");
                ASSERT(MoveHistoryTask6Entry_PCStoragePlaceAndSeed
                        == ORIGIN(rom) + 0x28,
                    "task-6 Pokewalker import ABI moved");
                ASSERT(MoveHistoryTask6Entry_ReplacePartyMove
                        == ORIGIN(rom) + 0x30,
                    "task-6 permanent form-move ABI moved");
                ASSERT(MoveHistoryTask6Entry_PlayerPartyAddCommit
                        == ORIGIN(rom) + 0x38,
                    "task-6 party-add ABI moved");
                ASSERT(MoveHistoryTask6Entry_DaycareShiftAndAppend
                        == ORIGIN(rom) + 0x40,
                    "task-6 daycare level-up ABI moved");
                ASSERT(MoveHistoryTask6Entry_CorrectBattleFormMoves
                        == ORIGIN(rom) + 0x48,
                    "task-6 battle form-move ABI moved");
                ASSERT(MoveHistoryTask6Entry_MarkHistoryMove
                        == ORIGIN(rom) + 0x50,
                    "task-6 history candidate marker ABI moved");
                ASSERT(MoveHistoryTask6Entry_AppendCandidate
                        == ORIGIN(rom) + 0x58,
                    "task-6 candidate append ABI moved");
                . = ALIGN(4);
                *(.init)
                *(.text)
                *(.ctors)
                *(.dtors)
                *(.rodata)
                *(.fini)
                *(COMMON)
                __text_end = . ;

                __bss_start__ = . ;
                *(.bss)
                __bss_end__ = . ;
                __task6_pre_private_end = . ;
                ASSERT(__task6_pre_private_end <= ORIGIN(rom) + 0xA80,
                    "task-6 historical region entered private support window");

                . = ORIGIN(rom) + 0xA80;
                __owbd_resident_private_start = . ;
                KEEP(*(.owbd_resident_tables))
                . = ALIGN(4);
                KEEP(*(.owbd_resident_helpers))
                . = ALIGN(4);
                KEEP(*(.owbd_resident_loader))
                . = ALIGN(4);
                __owbd_resident_private_end = . ;
                ASSERT(__owbd_resident_private_end <= ORIGIN(rom) + 0xE00,
                    "behavior support library overlaps sealed task-6 scratch");
                _end = __owbd_resident_private_end ;
                __end__ = __owbd_resident_private_end ;
        } >rom = 0xff
}
