# Overworld Wild Pokemon Terrain and Surface Analysis

## Verdict

Expanded terrain support is feasible, and much of the required movement foundation already exists. It should be implemented as a surface/layer system rather than by adding more special cases to the current land, water, grass, and canopy checks.

There are two separate problems:

1. Logical placement and movement: deciding that a Pokemon occupies a tree canopy, roof, bridge deck, cliff, water surface, or other terrain layer.
2. Visual compositing: making the Pokemon render above a tree or building rather than inside or behind it.

Logical surface support is reasonably straightforward. Correct rendering over occluding map geometry is the main technical risk.

## Current System

Spawn terrain currently records the encounter source as land, surf, headbutt, or fishing. Movement profiles separately permit land, water, canopy, grass, the player's tile, or the tile in front of the player.

The existing system already provides useful foundations:

- The Canopy Hopper profile supports canopy and land movement, configurable hop distances, tired returns, and active movement behavior.
- Normal steps, ledges, staged jumps, movement ownership, target reservations, and landing are already implemented.
- Landing can refresh a map object's height from native field collision geometry.
- Native HeartGold map objects retain both an exact world height and a discrete height layer.
- Native object collision permits actors at the same X/Z coordinates when their vertical layers are sufficiently separated.

The custom wild system nevertheless treats most occupancy, targeting, reservations, proximity checks, and battles as two-dimensional. A bird placed on a roof would therefore currently reserve and block the tile below it and could interact or battle through the building.

## Physical Height and Visual Occlusion

Raising a map object is not sufficient to render a Pokemon on top of a tree canopy. Previous Mankey experiments tried object height, position-vector height, map-object flags, draw modes, callbacks, OAM/depth settings, follower proxies, special-field-object proxies, and late calls to the normal map-object renderer. These remained behind the canopy or interfered with movement.

An attached follower/emote bubble did render above the same canopy. This proves that an above-canopy effect render family exists, although rendering a complete animated Pokemon through it remains unproven.

The most evidence-backed presentation design is:

- Keep a normal map object as the logical actor for identity, movement, collision, encounter state, and battle.
- Hide its normal visual while it occupies a visually occluded upper surface.
- Display a synchronized effect-owned Pokemon visual above the canopy or building.
- Synchronize species, form, shiny palette, facing, animation, movement offsets, and visibility.
- Tear the effect visual down on landing, battle, despawn, and map transition.

Accessible roofs, bridges, and terraces with genuine collision geometry may work with a normal elevated map object. Synthetic tree canopies and most inaccessible building roofs will probably require the effect-owned presentation path.

## Surface Model

Every active wild Pokemon should retain a surface reference in addition to its existing tile coordinates:

```c
typedef struct OverworldWildSurfaceRef {
    s16 tileX;
    s16 tileZ;
    fx32 worldY;
    s16 heightLayer;
    u16 surfaceId;
    u8 surfaceKind;
    u8 renderPolicy;
} OverworldWildSurfaceRef;
```

The authoritative location becomes `(tileX, tileZ, surfaceId)`, not only `(tileX, tileZ)`.

Candidate surface kinds include:

- Ground
- Grass
- Sand
- Mud
- Snow
- Ice
- Cave floor
- Shallow water
- Deep water
- Puddle
- Magma
- Canopy or branch
- Roof
- Cliff shelf
- Bridge deck
- Water below bridge
- Air

The exact catalog should be centralized so profiles, movement, spawn overrides, debugging output, and map data all use the same IDs.

`PLAYER` and `PLAYER_FRONT` should not be physical surface kinds. They are dynamic target and occupancy permissions. The player still occupies a real surface such as ground, a bridge deck, or shallow water.

Native terrain predicates can classify grass, water, sand, mud, snow, ice, cave floor, puddles, magma, waterfalls, whirlpools, ledges, and rock-climb terrain. Canopies, roofs, rails, inaccessible cliff shelves, and similar model-defined surfaces will need explicit surface data.

For the first implementation, model-defined surfaces should be authored per map as rectangles, masks, connected nodes, or individual perch points with explicit height and render policy. Automatic extraction from map models can be added after the runtime system is stable.

The fixed-size persistent spawn structure should remain focused on encounter identity. Current surface, height, presentation, and per-spawn surface overrides can initially live in the runtime sidecar state.

## How This Fits the Current Profile Override System

The current profile resolver already has the correct high-level composition model:

1. Ordered generic class rules select a behavior class.
2. Ordered species-class rules can replace that class; later matches win.
3. The selected class profile becomes the numeric base profile.
4. All matching override profiles are applied in authored table order.
5. Later overrides can replace values written by earlier overrides.

The current data contains four class profiles, two generic class rules, 113 species-class rules, eleven ordered override profiles, and 155 shared override members. Resolution is cached per live slot, so these tables are normally scanned only during spawn initialization or cache invalidation.

Terrain policy should reuse that exact resolver pass. It should not introduce a second hierarchy or independently rescan species and override member lists.

The existing `OverworldWildBehaviorProfile` should remain the compact 72-byte numeric profile. Its override machinery treats every field as a byte and supports exact, relative, minimum, and maximum operations. Surface bitsets have different enable/disable semantics, and inserting word-sized arrays into this frequently copied structure would increase stack traffic, profile-cache copies, every override record, and the complexity of the generic byte-field override code.

Instead, store surface data in parallel records indexed exactly like the existing profile data:

```c
typedef u32 OverworldWildSurfaceMask;

typedef enum OverworldWildSurfacePolicyState {
    OW_WILD_SURFACE_POLICY_CHILL,
    OW_WILD_SURFACE_POLICY_ACTIVE,
    OW_WILD_SURFACE_POLICY_TIRED,
    OW_WILD_SURFACE_POLICY_STATE_COUNT
} OverworldWildSurfacePolicyState;

typedef struct OverworldWildClassSurfacePolicy {
    OverworldWildSurfaceMask allowed[OW_WILD_SURFACE_POLICY_STATE_COUNT];
} OverworldWildClassSurfacePolicy;

typedef struct OverworldWildOverrideSurfaceDelta {
    OverworldWildSurfaceMask enable[OW_WILD_SURFACE_POLICY_STATE_COUNT];
    OverworldWildSurfaceMask disable[OW_WILD_SURFACE_POLICY_STATE_COUNT];
} OverworldWildOverrideSurfaceDelta;
```

Each class profile owns three absolute masks. Each existing override profile owns three enable masks and three disable masks. Whenever an override matches, its numeric profile fields and its surface delta are applied in the same ordered loop:

```c
resolved[state] |= overrideDelta->enable[state];
resolved[state] &= ~overrideDelta->disable[state];
```

Disable wins when one override accidentally contains the same bit in both fields. A later matching override can deliberately re-enable that surface, matching the current last-write-wins ordering. This is ordered composition, not an inferred general-to-specific ranking.

EMOTING currently cannot select a movement destination. It should retain the surface and policy of the state that started the emote instead of paying for a fourth independent movement mask. If moving emotes are added later, it can become a fourth policy state without changing the surface catalog.

## Per-Spawn Surface Overrides

Every live spawn can carry the same three-state enable/disable delta in the runtime sidecar:

```c
typedef struct OverworldWildSpawnSurfaceDelta {
    OverworldWildSurfaceMask enable[OW_WILD_SURFACE_POLICY_STATE_COUNT];
    OverworldWildSurfaceMask disable[OW_WILD_SURFACE_POLICY_STATE_COUNT];
} OverworldWildSpawnSurfaceDelta;
```

This lets one spawn differ from other Pokemon using the same behavior profile. Examples include disabling roofs on a map whose building geometry is not authored, restricting a scripted bird to ground while an event is active, or permitting a particular arboreal spawn to descend to land.

The full three-state delta costs 24 bytes per slot, or 240 bytes for all ten wild slots. That is small enough to provide the requested state-specific spawn control. If later measurement shows those overrides are almost always state-independent, they can be compacted to one shared enable/disable pair per slot.

Changing a spawn delta should only increment a per-slot policy revision and rebuild that slot's three cached masks. It must not rerun the behavior-class, member-list, or numeric profile resolver.

The static and spawn deltas resolve as:

```c
policyMask = resolvedProfileSurfaceMask[state];
policyMask |= spawnDelta->enable[state];
policyMask &= ~spawnDelta->disable[state];
effectiveMask = policyMask
    & resolvedEcology.supportedSurfaceMask
    & mapAvailableSurfaceMask;
```

The last two masks are hard constraints. A spawn override can express stronger or weaker behavior intent, but it cannot manufacture a roof that is absent from the map or give an incapable Pokemon the physical ability to occupy it.

An empty effective mask is valid for an intentionally immobile state. The AI must enter an idle/cooldown path rather than repeatedly searching or silently falling back to land.

## Ecology Tags, Physical Capabilities, and Profile Intent

Battle type is too broad for terrain eligibility. Pidgey and Zubat can both fly, but they do not necessarily share roof-walking or perching behavior. Magnemite can hover without perching. Aipom can occupy a canopy without true flight.

Three concepts must remain separate:

- **Ecology tags** identify authored species groups and allow override profiles to target them: `ARBOREAL`, `ROOF_VISITOR`, `CLIFF_DWELLER`, `SHOREBIRD`, `MARSH_DWELLER`, or `CAVE_FLYER`.
- **Physical capabilities** describe available mechanics: `CAN_WALK`, `CAN_HOP`, `CAN_FLY`, `CAN_HOVER`, `CAN_SWIM`, `CAN_WADE`, `CAN_PERCH`, `CAN_CLIMB`, `CAN_BURROW`, `CAN_SLIDE`, or `MAGMA_SAFE`.
- **Surface policy** describes where the resolved behavior profile wants this actor to move in CHILL, ACTIVE, or TIRED state.

Ecology and capability data are intrinsic species/form metadata. Behavior overrides may match those tags, but should not grant intrinsic capabilities; otherwise an override could change the property that caused itself to match.

If ecology targeting is needed, extend the existing behavior context and match with separate `any`, `all`, and `none` ecology masks. Do not reuse the current `groupFlags`: 22 of its 32 bits are already assigned, and its only matching rule is "any bit overlaps."

For readable authoring and compact runtime data, species can be assigned named tags in source data and compiled into an ecology class:

```c
typedef struct OverworldWildResolvedEcology {
    u32 supportedSurfaceMask;
    u16 supportedTransitionMask;
    u16 ecologyTags;
} OverworldWildResolvedEcology;
```

A compact implementation can store one `u8 ecologyClassId` per base species plus sorted `{ species, form, classId }` exceptions. A small class dictionary then supplies the resolved structure above. This is approximately one kilobyte for the dense species index plus the dictionary and exceptions, rather than expanding the existing spawn metadata record for every species and form.

Ecology must be resolved with both species and form during spawn preparation, then copied into the slot cache. The current type-based path can rebuild a runtime context without the form on an initial cache miss; the new ecology path must not repeat that inconsistency. Prepared spawn data should seed the runtime resolved-policy cache directly.

## Runtime Cache and Hot-Path Cost

The system has at most ten wild slots. Active movement is updated every frame, but otherwise-idle AI is already distributed with a round-robin cursor so only one idle slot receives decision work per frame.

Each slot should cache:

- The three surface masks after class and ordered override-profile resolution.
- The three final masks after the spawn delta and hard constraints.
- Resolved ecology tags, supported surfaces, and transition capabilities.
- A spawn-policy revision and map-surface generation.

The expected cache and spawn-delta cost is only a few hundred bytes across all ten slots. The important saving is CPU and code structure: no behavior table scan, member-list scan, personal-data lookup, model scan, or archive-backed tree search occurs inside candidate evaluation.

The movement hot path becomes:

```c
allowedMask = cache->effectiveSurfaceMask[state];
if ((allowedMask & OW_WILD_SURFACE_BIT(candidate->surfaceKind)) == 0) {
    return FALSE;
}
if ((edge->requiredCapabilities & cache->supportedTransitionMask)
        != edge->requiredCapabilities) {
    return FALSE;
}
```

This is faster than iterating a list of enabled surfaces. The catalog can expose every terrain checkbox to the profile editor while runtime validation remains one 32-bit surface test and one transition-capability test.

Every coordinate must resolve to an exact leaf surface such as `GROUND`, `GRASS`, `SAND`, or `SNOW`. Broad authoring groups such as `LANDLIKE` should be compile-time mask aliases, not additional classifications placed on the same tile. This lets a profile enable all landlike surfaces and still explicitly disable grass or mud.

Legacy `LAND` currently means almost any unblocked non-water, non-headbutt tile. Its migration mask must initially expand to the complete compatible ground family, including sand, snow, mud, and cave floor, or existing Pokemon will silently lose movement permissions.

## Movement Integration

Allowed surfaces answer where a Pokemon may choose to go. They do not by themselves select how it gets there. The current movement profile and derived primitives remain responsible for intent and locomotion.

A bird can therefore have `AIR | ROOF | CANOPY` in its ACTIVE policy and possess `CAN_FLY | CAN_PERCH`, but it still needs flight/perch locomotion primitives. A normal WANDER primitive should not magically interpret roof permission as permission to fly between disconnected buildings.

The packed primary/secondary allowed-tile byte should be replaced at its callers by one cached `u32` destination mask. Candidate classification should occur once, followed by a bit test. It must not loop through all enabled surface kinds.

The current boolean landing validator should evolve into a resolver that returns the concrete destination surface because a bridge deck and the water below can share X/Z:

```c
BOOL TryResolveMovementDestination(
    const OverworldWildMovementContext *context,
    int x,
    int z,
    OverworldWildSurfaceRef *destination);
```

A movement attempt should then:

1. Select the cached effective mask for CHILL, ACTIVE, or TIRED.
2. Resolve candidate surface nodes permitted by that mask.
3. Select an edge whose required traversal capabilities are satisfied.
4. Reserve the destination `surfaceId` rather than only X/Z.
5. Dispatch walk, hop, climb, takeoff, flight, landing, drop, swim, wade, burrow, or slide locomotion.
6. Use native walking for ordinary same-surface edges where native collision agrees.
7. Reuse the custom jump/interpolation carrier for cross-surface hops and landings.
8. Commit the destination surface only after the movement succeeds.

Surface masks govern destination selection, not instantaneous validity of the actor's current position. If a bird becomes TIRED while airborne and TIRED disables AIR, it must finish its current atomic transition and enter a landing search. It must not be teleported, cancelled halfway through a movement command, or declared invalid while still airborne.

For birds, a useful lifecycle is:

```text
PERCHED -> TAKEOFF -> AIRBORNE -> CRUISE/SWOOP -> LAND -> PERCHED
```

The first roof implementation should use authored perch nodes, takeoff, short flight, and landing. Full freeform walking across arbitrary roof models is not necessary for the initial feature.

Reservations can be simplified to one current and one reserved `SurfaceRef` per slot plus a valid bitmask. With only ten actors, an O(10) reservation scan is inexpensive; the essential correction is comparing `surfaceId` and height rather than rejecting every identical X/Z coordinate.

Occupancy, A-button targeting, contact battles, ram battles, player-ball targeting, shadows, and save restoration must also become surface- or height-aware. A Pokemon on a roof must not block or directly battle a player below it.

## Map and Pathfinding Efficiency

Flat terrain should use a 256-entry metatile-behavior classification table so the behavior byte maps directly to a leaf surface kind and attributes. Model-defined canopy and roof surfaces should be discovered or loaded once per map and indexed by tile.

Elevated surfaces should use compact node IDs and precomputed adjacency lists. A small graph can use bitsets for visited and occupied nodes, making planning bounded O(V + E). The current tree-top path should not reload archives, inspect models, or rediscover canopy structure inside breadth-first search or per-frame movement.

Per-frame jump, flight, or effect-visual interpolation should read the destination selected at movement start. It should never query or classify terrain every animation frame.

## Overlay and Data-Size Constraint

The mask operations and runtime cache are cheap, but code placement is a serious constraint. The current spawner overlay occupies approximately 45,050 bytes of a 45,056-byte region, leaving about six bytes of linker slack. The helper overlay has roughly ten bytes free, and the behavior-data overlay roughly 150 bytes.

This feature cannot be added as a second generic layer beside the existing allowed-tile and Mankey-specific implementation. It must replace and remove legacy paths, reclaim code, move substantial new surface logic to a newly allocated overlay, or deliberately repartition existing overlays. Overlay map size must be checked after each implementation stage.

The behavior data itself is modest. Parallel policies for four class profiles and eleven overrides cost approximately 312 bytes for the three moving states. Full per-spawn three-state deltas cost 240 runtime bytes. The danger is duplicated code and permanent migration paths, not the masks themselves.

The behavior data version, blob header, validator, builder, and profile viewer must change together. A one-release migration should translate primary/secondary allowed tiles to masks, verify parity, and then remove the six legacy allowed-tile fields and matching code instead of retaining two permanent systems.

The encounter-source field remains separate. A Pokemon may originate from a HEADBUTT encounter while its behavior permits canopy, ground, and air. Spawn origin describes how the encounter was produced; surface policy describes where the actor may move afterward.

## Example: Roof-Perching Bird with Other Overrides

Suppose Pidgey matches an aggressive behavior class, the Bird override, and the Swarm override.

- The aggressive class supplies its existing numeric chase behavior and base ground policy.
- The Bird override enables roof and canopy while CHILL, enables air, roof, and canopy while ACTIVE, and disables air while TIRED.
- The Swarm override adjusts numeric pursuit and group behavior without needing to replace the Bird surface policy.
- Pidgey's ecology class supplies `CAN_FLY`, `CAN_PERCH`, and `ROOF_VISITOR` compatibility.
- A map-specific spawn delta can disable roof if that map has no safe authored roof network.

The final policy might be:

| State | Desired surfaces | Movement implication |
|---|---|---|
| Chill | Ground, roof, canopy | Wander locally or remain perched |
| Active | Ground, roof, canopy, air | Chase by walking, taking off, flying, or landing |
| Tired | Ground, roof, canopy | Finish current flight and seek a legal landing |

Disconnected roof networks remain disconnected even though both contain `ROOF` surfaces. Surface masks permit the destination kind; graph edges determine whether that particular destination is reachable.

## Authoring and Validation

Class profiles should display an ordinary on/off surface grid for CHILL, ACTIVE, and TIRED. Override profiles and individual spawns should display a tri-state grid: `INHERIT`, `ENABLE`, or `DISABLE` for every surface in each state.

The data tools should report resolved policy provenance and reject or warn about:

- The same surface enabled and disabled in one delta.
- A movement state whose effective mask is empty unless explicitly marked immobile.
- A locomotion state with no compatible traversal capability.
- A flyer whose TIRED state has no reachable landing surface.
- A spawn destination excluded by its initial resolved policy.
- A policy enabling surfaces that no targeted species can support.
- A nonzero policy containing no surfaces present on the target map.
- An elevated destination with no render policy or authored/native height.

## Terrain and Pokemon Opportunities

| Surface | Suitable Pokemon | Possible behavior |
|---|---|---|
| Tree canopy | Mankey, Aipom, birds, arboreal bugs | Branch hopping, resting, ambushing, dropping to ground |
| Roofs, chimneys, and signs | Small or medium birds, bats, some levitators | Perching, short walks, circling, swooping |
| Cliffs and rock shelves | Rock/Ground species, climbers, birds | Shelf walking, hopping, climbing, dropping |
| Sand and beaches | Sandshrew, Diglett, Hippopotas, crabs, shorebirds | Scuttling, burrowing, emerging |
| Mud, marsh, and shallow water | Wooper, Quagsire, Croagunk, Barboach | Wading, splashing, land/water transitions |
| Snow | Ice species, mammals, winter birds | Powder movement, hiding, slower travel |
| Ice | Ice species, seals, penguin-like species | Sliding and controlled momentum |
| Bridges | Birds above, aquatic Pokemon below | Multi-layer occupancy at identical X/Z |
| Caves | Bats, rock Pokemon, spiders, lizards | Hovering, floor movement, authored wall perches |
| Water | Swimmers, amphibians, waterfowl | Swimming, shore transitions, landing on water |
| Magma | Selected Fire/Rock species or hoverers | Slow movement, hovering, no ordinary shadow |
| Tall grass | Small or stalking Pokemon | Partial hiding rather than elevated movement |

## Recommended Implementation Order

1. **Overlay ownership and renderer spike:** Decide which legacy code is replaced or which new overlay owns surface logic, then render one fully animated effect-owned Mankey above a known Route 29 canopy while retaining a hidden logical map object.
2. **One-step policy migration:** Add the surface catalog and parallel class/override policy tables, translate every existing primary/secondary pair, update the data tools, and remove the legacy fields and matching path in the same feature branch.
3. **Ecology and resolved cache:** Add form-aware ecology classes, seed the slot cache during spawn preparation, and verify that candidate checks use only cached masks and capabilities.
4. **Layer-aware interactions:** Make occupancy, reservations, proximity, and battles surface-aware, then prove that actors can coexist on a native bridge deck and below it.
5. **Canopy support:** Convert current tree-top detection into cached canopy surfaces with explicit height and presentation policy.
6. **Roof-bird pilot:** Add one map with authored roof perches and one bird profile using perch, takeoff, swoop, and landing.
7. **Flat terrain ecology:** Add sand, mud, snow, ice, shallow-water, cave, and cliff behaviors through the same catalog and mask system.
8. **Connected elevated networks:** Add larger roof, cliff, canopy, and aerial surface graphs after the basic runtime and rendering paths are proven.

The effect renderer remains the go/no-go experiment for convincing tree-top and inaccessible-roof presentation. The allowed-surface mask evolution is independent and can be implemented safely before every terrain type is available.
