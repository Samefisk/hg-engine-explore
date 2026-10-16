#ifndef OVERWORLD_ACTOR_APPEARANCE_INTERNAL_H
#define OVERWORLD_ACTOR_APPEARANCE_INTERNAL_H

#include "overworld_actor_appearance.h"

/* Called only after the native glue cancels the authenticated Selector.
 * A live foreign callback keeps its record and blocks code unloading. */
BOOL Appearance_ClearForUnload(struct MapObjectMan *currentManager);

#endif
