#include "../../include/overworld_query_code_addon.h"

void LONG_CALL QueryAddon_DC_FlushRange(const void *, u32);
void LONG_CALL QueryAddon_DC_WaitWriteBufferEmpty(void);
void LONG_CALL QueryAddon_IC_InvalidateRange(void *, u32);

void OverworldQueryCodeAddon_FlushData(const void *image, u32 size)
{ QueryAddon_DC_FlushRange(image, size); }
void OverworldQueryCodeAddon_WaitWriteBuffer(void)
{ QueryAddon_DC_WaitWriteBufferEmpty(); }
void OverworldQueryCodeAddon_InvalidateCode(void *image, u32 size)
{ QueryAddon_IC_InvalidateRange(image, size); }
