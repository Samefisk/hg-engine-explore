#include "../../include/types.h"

#define FIELD_WORK_RESERVE_BYTES (20u * 1024u + 64u)

/* Field graphics may fill either heap while asynchronous uploads are pending.
 * Keep the stock allocation first; use script/work space only when needed.
 * Heap_Free reads the chosen heap from the normal allocation header. */
void *__attribute__((noinline, section(".overworld_field_model_alloc")))
OverworldFieldModel_AllocTemporary(u32 heapId, u32 size)
{
    void *buffer = sys_AllocMemoryLo(heapId, size);

    if (buffer == NULL) {
        u32 freeBytes = GF_ExpHeap_FndGetTotalFreeSize(11);

        /* Keep script space, including room for both allocation headers,
         * alignment and an unsplittable trailing fragment. */
        if (freeBytes >= FIELD_WORK_RESERVE_BYTES
            && size <= freeBytes - FIELD_WORK_RESERVE_BYTES) {
            buffer = sys_AllocMemoryLo(11, size);
        }
    }
    return buffer;
}
