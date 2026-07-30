.nds
.thumb

PokemonMoveHistory_ReplaceMove equ 0x023BE480
PokemonMoveHistory_DeleteMoveSlot equ 0x023BE488

/*
 * Task 3 permanent move-history hooks.
 *
 * Each patch is a confirmed commit point from the named vanilla source:
 * - ScrCmd_MonForgetMove: Move Deleter after both confirmations.
 * - evolution scene and battle Task_GetExp: chosen replacement slot only.
 * - overlay 68 state 5: Move Reminder / special tutor confirmed selection.
 *
 * The targets are fixed Thumb entries in boot-resident overlay 153. No call
 * can execute before Main loads overlay 153, and overlay 153 never calls back
 * into dynamic overlays 12 or 68.
 */

.open "base/arm9.bin", 0x02000000

// ScrCmd_MonForgetMove -> MonDeleteMoveSlot(mon, slot)
.org 0x0204DCCC
    bl PokemonMoveHistory_DeleteMoveSlot

/*
 * PartyMonSetMoveInSlot already canonicalizes Party -> PartyPokemon through
 * Party_GetMonByIndex. Its final call has exactly ReplaceMove(box, move, slot)
 * register order because PartyPokemon begins with its BoxPokemon prefix.
 */
.org 0x020542E0
    bl PokemonMoveHistory_ReplaceMove

// Evolution replacement commit -> MonSetMoveInSlot(mon, move, slot)
.org 0x020769F0
    bl PokemonMoveHistory_ReplaceMove

.close

.open "base/overlay/overlay_0012.bin", 0x022378C0

// Task_GetExp STATE_GET_EXP_LEARNED_MOVE.
.org 0x02246344
    bl PokemonMoveHistory_ReplaceMove

.close

.open "base/overlay/overlay_0068.bin", 0x021E5900

/*
 * ov68_021E614C has already resolved the selected move into [sp]. Re-form the
 * canonical ReplaceMove(box, move, slot) arguments in the space occupied by
 * the original move SetMonData call. The following retail PP-up/PP writes are
 * intentionally retained and are idempotent with ReplaceMove.
 */
.org 0x021E6158
.area 0x021E6166 - .
    ldr r0, [r4]
    ldrb r2, [r0, #0x1B]
    ldr r0, [r0]
    ldr r1, [sp]
    bl PokemonMoveHistory_ReplaceMove
.endarea

.close
