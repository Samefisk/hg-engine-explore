#include "../../include/types.h"
#include "../../include/debug.h"

#ifdef DEBUG_BATTLE_SCENARIOS

#include "../../include/script.h"
#include "../../include/test_battle.h"

void LONG_CALL TestBattle_TryQueueNextTest(void *fieldSystem)
    __attribute__((section(".test_battle_queue_entry"), used));

void LONG_CALL TestBattle_TryQueueNextTest(void *fieldSystem)
{
    u32 delay;

    if (gTestBattleState & STATE_QUEUED_BIT) {
        return;
    }

    if (TestBattle_StateIsComplete()) {
        delay = (gTestBattleState >> STATE_QUEUE_DELAY_SHIFT)
            & STATE_QUEUE_DELAY_MASK;
        if (delay < STATE_QUEUE_DELAY_FRAMES) {
            gTestBattleState += 1 << STATE_QUEUE_DELAY_SHIFT;
            return;
        }
    }

    gTestBattleState &= ~(STATE_QUEUE_DELAY_MASK << STATE_QUEUE_DELAY_SHIFT);
    gTestBattleState |= STATE_QUEUED_BIT;
    EventSet_Script(fieldSystem, 2073, NULL);
}

#endif // DEBUG_BATTLE_SCENARIOS
