.nds
.thumb

SummaryMoveRelearn_Entry equ 0x023C0408

/*
 * This retail case block has only one four-byte BL available. The generic
 * hooks mechanism's total-function trampoline is intentionally not used.
 * gOverlayTemplate_PokemonSummary owns overlay 154 and completes its load
 * before this main-state callback can execute.
 */
.open "base/arm9.bin", 0x02000000

.org 0x02088494
    bl SummaryMoveRelearn_Entry

.close
