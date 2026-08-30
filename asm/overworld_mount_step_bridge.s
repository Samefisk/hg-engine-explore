    .syntax unified
    .thumb

    /* Mark the fixed resident entry as Thumb code so direct callers emit one
     * BL, rather than growing overlay 129 with an interworking veneer. */
    .global OverworldMount_PlayerStepBridgeEntry
    .type OverworldMount_PlayerStepBridgeEntry, %function
    .thumb_set OverworldMount_PlayerStepBridgeEntry, 0x023BB6A0
