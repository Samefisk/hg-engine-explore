.syntax unified
.thumb

.section .pokemon_move_history_api, "ax", %progbits

.global MoveHistoryEntry_Init
.type MoveHistoryEntry_Init, %function
MoveHistoryEntry_Init:
    ldr r3, 1f
    bx r3
    .align 2
1:  .word PokemonMoveHistory_InitImpl + 1

.global MoveHistoryEntry_Load
.type MoveHistoryEntry_Load, %function
MoveHistoryEntry_Load:
    ldr r3, 2f
    bx r3
    .align 2
2:  .word PokemonMoveHistory_LoadImpl + 1

.global MoveHistoryEntry_Reset
.type MoveHistoryEntry_Reset, %function
MoveHistoryEntry_Reset:
    ldr r3, 3f
    bx r3
    .align 2
3:  .word PokemonMoveHistory_ResetImpl + 1

.global MoveHistoryEntry_CaptureSnapshot
.type MoveHistoryEntry_CaptureSnapshot, %function
MoveHistoryEntry_CaptureSnapshot:
    ldr r3, 4f
    bx r3
    .align 2
4:  .word PokemonMoveHistory_CaptureSnapshotImpl + 1

.global MoveHistoryEntry_Seed
.type MoveHistoryEntry_Seed, %function
MoveHistoryEntry_Seed:
    ldr r3, 5f
    bx r3
    .align 2
5:  .word PokemonMoveHistory_SeedImpl + 1

.global MoveHistoryEntry_RecordMove
.type MoveHistoryEntry_RecordMove, %function
MoveHistoryEntry_RecordMove:
    ldr r3, 6f
    bx r3
    .align 2
6:  .word PokemonMoveHistory_RecordMoveImpl + 1

.global MoveHistoryEntry_RecordSnapshot
.type MoveHistoryEntry_RecordSnapshot, %function
MoveHistoryEntry_RecordSnapshot:
    ldr r3, 7f
    bx r3
    .align 2
7:  .word PokemonMoveHistory_RecordSnapshotImpl + 1

.global MoveHistoryEntry_Query
.type MoveHistoryEntry_Query, %function
MoveHistoryEntry_Query:
    /* Query's fourth ARM EABI argument occupies r3; preserve it. */
    .syntax divided
    b PokemonMoveHistory_QueryImpl
    .syntax unified
    .space 6, 0

.global MoveHistoryEntry_CommitIfDirty
.type MoveHistoryEntry_CommitIfDirty, %function
MoveHistoryEntry_CommitIfDirty:
    ldr r3, 9f
    bx r3
    .align 2
9:  .word PokemonMoveHistory_CommitIfDirtyImpl + 1

.global MoveHistoryEntry_LoadAndSeedParty
.type MoveHistoryEntry_LoadAndSeedParty, %function
MoveHistoryEntry_LoadAndSeedParty:
    ldr r3, 10f
    bx r3
    .align 2
10: .word PokemonMoveHistory_LoadAndSeedPartyImpl + 1

.global MoveHistoryEntry_PrepareSave
.type MoveHistoryEntry_PrepareSave, %function
MoveHistoryEntry_PrepareSave:
    ldr r3, 11f
    bx r3
    .align 2
11: .word PokemonMoveHistory_PrepareSaveImpl + 1

.global MoveHistoryEntry_FinishSave
.type MoveHistoryEntry_FinishSave, %function
MoveHistoryEntry_FinishSave:
    ldr r3, 12f
    bx r3
    .align 2
12: .word PokemonMoveHistory_FinishSaveImpl + 1

.global MoveHistoryEntry_CancelSave
.type MoveHistoryEntry_CancelSave, %function
MoveHistoryEntry_CancelSave:
    ldr r3, 13f
    bx r3
    .align 2
13: .word PokemonMoveHistory_CancelSaveImpl + 1

.global MoveHistoryEntry_WriteSaveNow
.type MoveHistoryEntry_WriteSaveNow, %function
MoveHistoryEntry_WriteSaveNow:
    ldr r3, 14f
    bx r3
    .align 2
14: .word PokemonMoveHistory_WriteSaveNowImpl + 1

.global MoveHistoryEntry_SaveGameNormal
.type MoveHistoryEntry_SaveGameNormal, %function
MoveHistoryEntry_SaveGameNormal:
    ldr r3, 15f
    bx r3
    .align 2
15: .word SaveGameNormalImpl + 1
