.include "asm/include/battle_commands.inc"

.data

_000:
    PrintMagmaArmorHeatedAttackMessage BATTLER_CATEGORY_MSG_BATTLER_TEMP
    Wait
    WaitButtonABTime 30
    End
