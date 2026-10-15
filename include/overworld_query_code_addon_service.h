#ifndef OVERWORLD_QUERY_CODE_ADDON_SERVICE_H
#define OVERWORLD_QUERY_CODE_ADDON_SERVICE_H
#include "overworld_query_code_addon.h"

/* Private Selector tail, after the unchanged public Condition table/gate.
 * Check that gate before reading this entry. Parent Field owns the loaded code
 * and must drain this state before Selector or World-heap teardown. */
#define OVERWORLD_QUERY_CODE_ADDON_SERVICE_ADDR 0x023C22F0
#define OVERWORLD_QUERY_CODE_ADDON_STATE_ADDR 0x023C2308
#define OVERWORLD_QUERY_CODE_ADDON_SERVICE_MAGIC 0x53444F57 /* WODS */
/* Stable resident table ABI; the loaded package has its own version. */
#define OVERWORLD_QUERY_CODE_ADDON_SERVICE_VERSION 2
typedef struct OverworldQueryCodeAddonServiceEntry {
    u32 magic;
    u16 version, size;
    OverworldQueryCodeAddonState *state;
    OverworldQueryCodeAddonStatus (*load)(const OverworldQueryCodeAddonOwner *,
        const OverworldQueryCodeAddonOps *, u32, u32);
    const OverworldQueryCodeAddonEntry *(*acquire)(const OverworldQueryCodeAddonOwner *);
    OverworldQueryCodeAddonStatus (*unload)(const OverworldQueryCodeAddonOps *, void *);
} OverworldQueryCodeAddonServiceEntry;
extern OverworldQueryCodeAddonState gOverworldQueryCodeAddonState;
extern const OverworldQueryCodeAddonServiceEntry gOverworldQueryCodeAddonServiceEntry;

OverworldBehaviorConditionStatus OverworldQueryCodeAddon_ConditionPrepare(
    const void *, u32, const OverworldWildBehaviorContext *, const OverworldActorHandle *,
    OverworldBehaviorConditionPreparedActor *);
OverworldBehaviorConditionStatus OverworldQueryCodeAddon_ConditionEvaluate(
    const void *, u32, OverworldBehaviorConditionPreparedActor *,
    const OverworldBehaviorConditionWorldView *, const OverworldBehaviorConditionCandidate *,
    u8, u32, OverworldBehaviorConditionScratch *, OverworldBehaviorConditionResult *);
BOOL OverworldQueryCodeAddon_ResolverCall(OverworldBehaviorResolverCall *);
void OverworldQueryCodeAddon_ConditionNotify(OverworldBehaviorConditionPreparedActor *,
    const OverworldActorHandle *, u32);
#ifndef OVERWORLD_ACTOR_SYSTEM_HOST
typedef char QueryAddonServiceMustRemain24[sizeof(OverworldQueryCodeAddonServiceEntry)==24?1:-1];
#endif
#endif
