.text
.align 1
.force_thumb
.syntax unified

.global PokemonMoveHistory_OverlayMemset
.thumb_func
.type PokemonMoveHistory_OverlayMemset, %function
PokemonMoveHistory_OverlayMemset:
    push {lr}
    blx 0x020E5B44
    pop {pc}
.size PokemonMoveHistory_OverlayMemset, . - PokemonMoveHistory_OverlayMemset

.global PokemonMoveHistory_OverlayMemcpy
.thumb_func
.type PokemonMoveHistory_OverlayMemcpy, %function
PokemonMoveHistory_OverlayMemcpy:
    push {lr}
    blx 0x020E5AD8
    pop {pc}
.size PokemonMoveHistory_OverlayMemcpy, . - PokemonMoveHistory_OverlayMemcpy
