#include "../../include/overworld_field_terrain_internal.h"

/* Field owns this stateless loader check. Only its code lives in the unused
 * HP161 tail; it adds no HP state, motion policy, or second stream clock. */
void __attribute__((noinline, used, section(".overworld_field_empty_axis")))
OverworldFieldTerrainStream_RetireEmptyAxis(
    void *manager, const s32 *position)
{
    s32 *sample = (s32 *)((u8 *)manager + 0xD0);
    s32 *high = *(s32 **)((u8 *)manager + 0xE0);
    s32 *low = *(s32 **)((u8 *)manager + 0xE4);
    u8 direction = *((u8 *)manager + 0xEC);
    s32 *sampleAxis = sample;
    const s32 *playerAxis = position;

    if ((direction & 1) == 0) {
        sampleAxis += 2;
        playerAxis += 2;
    }
    /* Retire only a rolled-back stock step at the unchanged sampled tile.
     * The new watcher must still be sampled by the stock loader. */
    if (*(u32 *)((u8 *)manager + 0xE8) == 1
        && direction >= 1 && direction <= 4
        && sample[0] == position[0]
        && sample[2] == position[2]
        && ((high == sampleAxis && low == playerAxis)
            || (low == sampleAxis && high == playerAxis))) {
        *(u32 *)((u8 *)manager + 0xE8) = 0;
        *(s32 **)((u8 *)manager + 0xE0) = NULL;
        *(s32 **)((u8 *)manager + 0xE4) = NULL;
    }
}
