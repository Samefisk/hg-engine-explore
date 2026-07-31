.nds
.thumb

PokemonMoveHistory_ReplaceMove equ 0x023BE480
PokemonMoveHistory_DeleteMoveSlot equ 0x023BE488
PokemonMoveHistory_PlayerPartyAddCommit equ 0x023BD438
PokemonMoveHistory_DaycareShiftAndAppend equ 0x023BD440
PokemonMoveHistoryTask6_DaycareDepositCommit equ 0x023BD408
PokemonMoveHistoryTask6_TradeReplacePartySlot equ 0x023BD410
PokemonMoveHistoryTask6_HatchClearEgg equ 0x023BD418
PokemonMoveHistoryTask6_PCStorageGetAndSeed equ 0x023BD420
PokemonMoveHistoryTask6_PCStoragePlaceAndSeed equ 0x023BD428
PokemonMoveHistoryTask6_GTSPlaceAndSeed equ 0x023BD468
PokemonMoveHistoryTask6_GTSDeleteBoxAndRecord equ 0x023BD470
PokemonMoveHistoryTask6_GTSRemovePartyAndRecord equ 0x023BD478

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

/*
 * PokeParty_Add's only success tail. Preserve its canonical copy and seal,
 * then let the resident stub advance count and seed only the live player
 * party. Full/cancel paths return earlier and cannot dirty history.
 */
.org 0x02074562
.area 0x0207456C - .
    mov r1, r5
    mov r0, r4
    bl PokemonMoveHistory_PlayerPartyAddCommit
    pop {r3, r4, r5, pc}
.endarea

// Daycare level-up with a full move set: shift oldest, append learned.
.org 0x0206BF98
    bl PokemonMoveHistory_DaycareShiftAndAppend

// Save_Daycare_PutMonIn: canonical copy/remove commit, then seed its owner.
.org 0x0206BF04
    bl PokemonMoveHistoryTask6_DaycareDepositCommit

/*
 * Mon_UpdateRotomForm is a persistent owner mutation. Reject table indices
 * outside retail's six forms before any move/form write, then route every
 * special appliance rewrite through task 3's canonical history APIs.
 */
.org 0x02071EE0
.area 0x02071EF0 - .
    ldr r0, [sp, #0x1C]
    cmp r0, #6
    bhs 0x02071ED6
    mov r5, #0
    lsl r1, r0, #1
    b 0x02071EF0
    nop
    nop
.endarea
.org 0x02071F20
    bl PokemonMoveHistory_ReplaceMove
.org 0x02071F2C
    bl PokemonMoveHistory_DeleteMoveSlot
.org 0x02071F64
    bl PokemonMoveHistory_ReplaceMove
.org 0x02071F80
    bl PokemonMoveHistory_ReplaceMove
.org 0x02071F98
    bl PokemonMoveHistory_ReplaceMove

// Hatch task: clear egg state first, then establish inherited-move baseline.
.org 0x02091156
    bl PokemonMoveHistoryTask6_HatchClearEgg

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

.open "base/overlay/overlay_0023.bin", 0x022598C0

/*
 * NPC trade receive owns the irreversible slot replacement. Preserve the
 * outgoing identity snapshot and seed the new trade identity only after the
 * canonical copy; animation/cancel paths never execute this call.
 */
.org 0x02259B7A
    bl PokemonMoveHistoryTask6_TradeReplacePartySlot

.close

.open "base/overlay/overlay_0112.bin", 0x021E5900

/*
 * Pokéwalker export is an existing-identity transfer. Seed the canonical PC
 * owner before retail serializes and deletes it; the transit copy is never
 * observed.
 */
.org 0x021EE65A
    bl PokemonMoveHistoryTask6_PCStorageGetAndSeed

/*
 * These are the three successful arrival placements. The separate recovery
 * placement at 0x021EC182 is deliberately untouched so failed/cancelled
 * communication remains byte-exact and history-clean.
 */
.org 0x021EE86A
    bl PokemonMoveHistoryTask6_PCStoragePlaceAndSeed
.org 0x021EEB8C
    bl PokemonMoveHistoryTask6_PCStoragePlaceAndSeed
.org 0x021EEC7E
    bl PokemonMoveHistoryTask6_PCStoragePlaceAndSeed

.close

.open "base/overlay/overlay_0065.bin", 0x0221BE20

/*
 * Successful wireless trade commit. Replace the received party slot through
 * the same resident transaction as NPC trade: snapshot outgoing, perform the
 * retail copy, then record outgoing and seed the canonical incoming owner.
 */
.org 0x0221F6C4
.area 0x0221F6D4 - .
    add r0, r7, #0
    add r1, r6, #0
    add r2, r4, #0
    bl PokemonMoveHistoryTask6_TradeReplacePartySlot
    nop
    nop
    nop
.endarea

.close

.open "base/overlay/overlay_0070.bin", 0x022378C0

/*
 * Successful GTS deposit/export removes an existing owner only here. Capture
 * the canonical outgoing owner and record it only after retail removal.
 */
.org 0x02240A0E
    bl PokemonMoveHistoryTask6_GTSDeleteBoxAndRecord
.org 0x02240A44
    bl PokemonMoveHistoryTask6_GTSRemovePartyAndRecord

/*
 * Both GTS receive variants use Party_AddMon when space exists (already
 * covered by the player-party success hook). A full party commits directly
 * to the previously resolved PC slot; replace only those successful retail
 * placement calls so failures/cancel paths remain history-clean.
 */
.org 0x02240B72
    bl PokemonMoveHistoryTask6_GTSPlaceAndSeed
.org 0x02240C76
    bl PokemonMoveHistoryTask6_GTSPlaceAndSeed

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
    nop
.endarea

.close
