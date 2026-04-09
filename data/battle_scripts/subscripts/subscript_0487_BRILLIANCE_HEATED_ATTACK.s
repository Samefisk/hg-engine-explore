.include "asm/include/battle_commands.inc"

.data

_000:
    PrintBrillianceHeatedAttackMessage BATTLER_CATEGORY_ATTACKER
    Wait
    WaitButtonABTime 30
    End
