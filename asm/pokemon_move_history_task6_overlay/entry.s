.syntax unified
.thumb

.section .pokemon_move_history_task6_api, "ax", %progbits

.global MoveHistoryTask6Entry_IsCanonical
.type MoveHistoryTask6Entry_IsCanonical, %function
MoveHistoryTask6Entry_IsCanonical:
    ldr r3, 1f
    bx r3
    .align 2
1:  .word PokemonMoveHistoryTask6_IsCanonicalImpl + 1

.global MoveHistoryTask6Entry_DaycareDepositCommit
.type MoveHistoryTask6Entry_DaycareDepositCommit, %function
MoveHistoryTask6Entry_DaycareDepositCommit:
    /* Preserve the fourth ARM EABI argument in r3. */
    .syntax divided
    b PokemonMoveHistoryTask6_DaycareDepositCommitImpl
    .syntax unified
    .space 6, 0

.global MoveHistoryTask6Entry_TradeReplacePartySlot
.type MoveHistoryTask6Entry_TradeReplacePartySlot, %function
MoveHistoryTask6Entry_TradeReplacePartySlot:
    ldr r3, 3f
    bx r3
    .align 2
3:  .word PokemonMoveHistoryTask6_TradeReplacePartySlotImpl + 1

.global MoveHistoryTask6Entry_HatchClearEgg
.type MoveHistoryTask6Entry_HatchClearEgg, %function
MoveHistoryTask6Entry_HatchClearEgg:
    ldr r3, 4f
    bx r3
    .align 2
4:  .word PokemonMoveHistoryTask6_HatchClearEggImpl + 1

.global MoveHistoryTask6Entry_PCStorageGetAndSeed
.type MoveHistoryTask6Entry_PCStorageGetAndSeed, %function
MoveHistoryTask6Entry_PCStorageGetAndSeed:
    ldr r3, 5f
    bx r3
    .align 2
5:  .word PokemonMoveHistoryTask6_PCStorageGetAndStageImpl + 1

.global MoveHistoryTask6Entry_PCStoragePlaceAndSeed
.type MoveHistoryTask6Entry_PCStoragePlaceAndSeed, %function
MoveHistoryTask6Entry_PCStoragePlaceAndSeed:
    /* Preserve the fourth ARM EABI argument in r3. */
    .syntax divided
    b PokemonMoveHistoryTask6_PCStoragePlaceAndSeedImpl
    .syntax unified
    .space 6, 0

.global MoveHistoryTask6Entry_ReplacePartyMove
.type MoveHistoryTask6Entry_ReplacePartyMove, %function
MoveHistoryTask6Entry_ReplacePartyMove:
    /* Preserve the fourth ARM EABI argument in r3. */
    .syntax divided
    b PokemonMoveHistoryTask6_SwapPartyPokemonMoveImpl
    .syntax unified
    .space 6, 0

.global MoveHistoryTask6Entry_PlayerPartyAddCommit
.type MoveHistoryTask6Entry_PlayerPartyAddCommit, %function
MoveHistoryTask6Entry_PlayerPartyAddCommit:
    ldr r3, 8f
    bx r3
    .align 2
8:  .word PokemonMoveHistoryTask6_PlayerPartyAddCommitImpl + 1

.global MoveHistoryTask6Entry_DaycareShiftAndAppend
.type MoveHistoryTask6Entry_DaycareShiftAndAppend, %function
MoveHistoryTask6Entry_DaycareShiftAndAppend:
    ldr r3, 9f
    bx r3
    .align 2
9:  .word PokemonMoveHistoryTask6_DaycareShiftAndAppendImpl + 1

.global MoveHistoryTask6Entry_CorrectBattleFormMoves
.type MoveHistoryTask6Entry_CorrectBattleFormMoves, %function
MoveHistoryTask6Entry_CorrectBattleFormMoves:
    ldr r3, 13f
    bx r3
    .align 2
13: .word PokemonMoveHistoryTask6_CorrectBattleFormMovesImpl + 1

.global MoveHistoryTask6Entry_MarkHistoryMove
.type MoveHistoryTask6Entry_MarkHistoryMove, %function
MoveHistoryTask6Entry_MarkHistoryMove:
    /* Preserve the fourth ARM EABI argument in r3. */
    .syntax divided
    b PokemonMoveHistoryTask6_MarkHistoryMoveImpl
    .syntax unified
    .space 6, 0

.global MoveHistoryTask6Entry_AppendCandidate
.type MoveHistoryTask6Entry_AppendCandidate, %function
MoveHistoryTask6Entry_AppendCandidate:
    /* Preserve the fourth ARM EABI argument in r3. */
    .syntax divided
    b PokemonMoveHistoryTask6_AppendCandidateImpl
    .syntax unified
    .space 6, 0

.section .text, "ax", %progbits

.section .pokemon_move_history_task6_post_data_api, "ax", %progbits

.global MoveHistoryTask6Entry_ScriptTeachMove
.type MoveHistoryTask6Entry_ScriptTeachMove, %function
MoveHistoryTask6Entry_ScriptTeachMove:
    /* Preserve the fourth ARM EABI argument in r3. */
    .syntax divided
    b PokemonMoveHistoryTask6_ScriptTeachMoveImpl
    .syntax unified
    .space 2, 0

.global MoveHistoryTask6Entry_GTSPlaceAndSeed
.type MoveHistoryTask6Entry_GTSPlaceAndSeed, %function
MoveHistoryTask6Entry_GTSPlaceAndSeed:
    ldr r3, 18f
    bx r3
    .align 2
18: .word PokemonMoveHistoryTask6_GTSPlaceAndSeedImpl + 1

.global MoveHistoryTask6Entry_GTSDeleteBoxAndRecord
.type MoveHistoryTask6Entry_GTSDeleteBoxAndRecord, %function
MoveHistoryTask6Entry_GTSDeleteBoxAndRecord:
    ldr r3, 19f
    bx r3
    .align 2
19: .word PokemonMoveHistoryTask6_GTSDeleteBoxAndRecordImpl + 1

.global MoveHistoryTask6Entry_GTSRemovePartyAndRecord
.type MoveHistoryTask6Entry_GTSRemovePartyAndRecord, %function
MoveHistoryTask6Entry_GTSRemovePartyAndRecord:
    ldr r3, 20f
    bx r3
    .align 2
20: .word PokemonMoveHistoryTask6_GTSRemovePartyAndRecordImpl + 1

.global MoveHistoryTask6Entry_PokewalkerRadioSuccess
.type MoveHistoryTask6Entry_PokewalkerRadioSuccess, %function
MoveHistoryTask6Entry_PokewalkerRadioSuccess:
    ldr r3, 21f
    bx r3
    .align 2
21: .word PokemonMoveHistoryTask6_PokewalkerRadioSuccessImpl + 1

.global MoveHistoryTask6Entry_PokewalkerRadioSuccessSecond
.type MoveHistoryTask6Entry_PokewalkerRadioSuccessSecond, %function
MoveHistoryTask6Entry_PokewalkerRadioSuccessSecond:
    ldr r3, 22f
    bx r3
    .align 2
22: .word PokemonMoveHistoryTask6_PokewalkerRadioSuccessImpl + 1

.global MoveHistoryTask6Entry_PokewalkerRecoverAndDiscard
.type MoveHistoryTask6Entry_PokewalkerRecoverAndDiscard, %function
MoveHistoryTask6Entry_PokewalkerRecoverAndDiscard:
    ldr r3, 23f
    bx r3
    .align 2
23: .word PokemonMoveHistoryTask6_PokewalkerRecoverAndDiscardImpl + 1

.global MoveHistoryTask6Entry_PokewalkerDiagnosticReturn
.type MoveHistoryTask6Entry_PokewalkerDiagnosticReturn, %function
MoveHistoryTask6Entry_PokewalkerDiagnosticReturn:
    /* Retail-unreferenced legacy fail-stop; host PC injection is forbidden. */
24: b 24b
    .space 6, 0

.global MoveHistoryTask6Entry_FieldReadyDiagnosticPoll
.type MoveHistoryTask6Entry_FieldReadyDiagnosticPoll, %function
MoveHistoryTask6Entry_FieldReadyDiagnosticPoll:
    ldr r3, 25f
    bx r3
    .align 2
25: .word PokemonMoveHistoryTask6_FieldReadyDiagnosticPollImpl + 1

.section .text, "ax", %progbits

/*
 * PokeParty_Add reaches this stub only after its canonical copy and seal have
 * succeeded. r0 is the destination Party and r1 is the end of the newly
 * copied PartyPokemon. Enemy and temporary parties retain retail behavior.
 */
.global PokemonMoveHistoryTask6_PlayerPartyAddCommitImpl
.type PokemonMoveHistoryTask6_PlayerPartyAddCommitImpl, %function
PokemonMoveHistoryTask6_PlayerPartyAddCommitImpl:
    push {r4, r5, r6, lr}
    mov r4, r0
    mov r6, r1
    ldr r5, [r4, #4]
    adds r5, #1
    str r5, [r4, #4]
    ldr r3, 10f
    blx r3
    mov r5, r0
    ldr r3, 11f
    blx r3
    cmp r0, r4
    bne 12f
    subs r6, #0xE8
    mov r0, r5
    mov r1, r6
    ldr r3, 15f
    blx r3
12:
    movs r0, #1
    pop {r4, r5, r6, pc}
    .align 2
10: .word 0x020272B1 /* SaveBlock2_get */
11: .word 0x02074905 /* SaveData_GetPlayerPartyPtr */
15: .word PokemonMoveHistory_Seed

/*
 * Daycare's full-set level-up path always shifts one move and appends the
 * learned move. Observe the canonical owner before the infallible retail
 * mutation and record the appended move after it returns.
 */
.global PokemonMoveHistoryTask6_DaycareShiftAndAppendImpl
.type PokemonMoveHistoryTask6_DaycareShiftAndAppendImpl, %function
PokemonMoveHistoryTask6_DaycareShiftAndAppendImpl:
    push {r4, r5, r6, lr}
    mov r4, r0
    mov r5, r1
    ldr r6, 13f
    blx r6
    mov r6, r0
    mov r1, r4
    ldr r3, 16f
    blx r3
    mov r0, r4
    mov r1, r5
    ldr r3, 14f
    blx r3
    mov r0, r6
    mov r1, r4
    mov r2, r5
    ldr r3, 17f
    blx r3
    pop {r4, r5, r6, pc}
    .align 2
13: .word 0x020272B1 /* SaveBlock2_get */
14: .word 0x020713ED /* DeleteMonFirstMoveAndAppend */
16: .word PokemonMoveHistory_Seed
17: .word PokemonMoveHistory_RecordMove
    .space 4, 0
