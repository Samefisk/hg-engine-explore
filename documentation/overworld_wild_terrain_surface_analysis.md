# Overworld Wild Pokemon Terrain and Surface Analysis

## Verdict

Expanded terrain support is feasible, and the refactored behavior-profile system is now a much better fit for it than the earlier analysis assumed. Profiles already support any combination of the current terrain bits, per-bit `INHERIT`/`ENABLE`/`DISABLE` semantics, and separate resolved Chill, Active, and Tired lanes.

The next step should therefore extend the existing lane-local terrain masks into a larger surface catalog. It should not add parallel class-policy and override-policy tables.

There are still two distinct problems:

1. **Logical surfaces and movement:** deciding that a Pokemon occupies and can reach a canopy, roof, bridge deck, cliff shelf, water layer, or other surface.
2. **Visual compositing:** rendering the Pokemon above occluding tree or building geometry instead of inside or behind it.

The profile refactor largely solves how allowed destinations should be authored and composed. Correct upper-surface rendering remains the main technical risk.

## Current System After the Profile Refactor

The live behavior blob is version 44 and currently contains:

- 4 behavior classes
- 2 generic class rules
- 113 species-class rules
- 14 ordered override profiles
- 164 shared override members

`OverworldWildBehaviorProfileData` is a 46-byte compact lane. Among its fields are:

```c
u8 chillAllowedTerrainMask;
u8 chillAllowedTerrainOverrideMask;
u8 activeProfile;
u8 tiredProfile;
```

The first terrain byte stores values. The second records which bits are explicit. Each bit consequently has three authoring states:

| Explicit bit | Value bit | Meaning |
|---|---|---|
| 0 | ignored | Inherit |
| 1 | 0 | Disable |
| 1 | 1 | Enable |

An override is composed as:

```c
result = (result & ~explicitMask) | (valueMask & explicitMask);
```

The current seven-bit catalog is `LAND`, `WATER`, `CANOPY`, `GRASS`, `PLAYER`, `PLAYER_FRONT`, and `ROOFTOP`. `LAND` is the inherited default. The old primary/secondary allowed-tile limit has therefore already been removed in this workspace: a lane can enable any subset of these entries.

The `ROOFTOP` implementation is generated from reusable building-model definitions rather than map-specific world coordinates. A build-time tool reads approved `bm_field` model templates, discovers their placements in the land archive through the existing map matrix, samples the rendered roof at every authored tile centre, clips the result at 32×32 block boundaries, and emits a compact land-data directory. Runtime only reads that catalog; it never parses NSBMD geometry or building records.

The generator has an explicit coverage gate for common outdoor building names matching Pokemon Centers, Marts, and house families. The current manifest covers all 35 discovered common model families and all 125 placements in matrix 0, with no exclusions. Their 1,628 authored landing tiles are sampled using exact rational vertical-ray intersections against the highest eligible roof triangle at each tile centre, then rounded upward to Q4 so a sprite cannot sink into the mesh. Equal-height neighbors are coalesced into 606 logical rectangles and 614 block-clipped instances across 59 land-data rows and 13 rectangle templates. Thirty conservative silhouette or continuity nodes in six model families have no triangle directly beneath their centre; those nodes inherit the nearest sampled tile height, and every fallback coordinate is retained in the generated audit report rather than being silently dropped.

The tested Cherrygrove block remains a useful concrete example. Its Pokemon Center is now a dense 5×4 connected roof at block-local `x=18..22`, `y=4..7`: the reviewed flat centre remains `0x4C000`, while the connected rear slope and front eave range down to `0x44000`. Both ordinary `yo_h01` houses are dense 4×3 roofs covering the pitched left half and flat right half, with sampled tile heights from `0x3FD50` to `0x4D8B0`. The nearby `yo_h02` gabled house ranges from `0x41070` to `0x5BD00`. Tile/model sampling uses the actual tile centre, `(tile * 16) + 8`, which fixes the earlier universal two-tile north displacement.

Dense means every tile in an authored rectangle is a valid roof tile. A 3×4 house therefore exposes all 12 tiles, not a checkerboard or a few hand-selected perch points. Mesh-verified roofs grow from their reviewed flat seed across edge-connected faces with projected area, so connected slopes are included while vertical façades and disconnected signs cannot expand or override the roof. The generator reports 235 nodes added by this component expansion and rejects obsolete partial authored offsets. A pitched roof is stored as several non-overlapping equal-height rectangles that all share the building's `surfaceId`; this preserves continuous movement without adding a runtime height-map decoder. The payload still uses six bytes per land-directory row, ten bytes per clipped height rectangle, and two bytes per reusable width/height template. The complete common-roof catalog is 6,520 bytes. Heights retain exact Q4 precision; one page byte extends the compact height past the old `u16` ceiling. Cross-block fragments store signed deltas to a canonical anchor block, so one building retains the same `surfaceId` and anchor altitude across a seam.

The Bird profile now selects the dedicated `ROOFTOP` spawn destination. Destination selection and allowed terrain are separate, authoritative checks: the destination requests an exact rooftop search, while the resolved Chill lane must explicitly allow `ROOFTOP`. If no authored rooftop exists in range, that spawn attempt fails. It does not retain the pool coordinate, reinterpret canopy as roof, or apply a map-specific fallback. Profiles can select `POOL`, `CANOPY`, `ROOFTOP`, or another destination deliberately, so maps without authored roofs need no exceptional rule.

The current bounded radius-eight rooftop scan considers at most 289 coordinates. Each query returns an exact terrain kind and sampled tile height, and a persistent last-block cache means the sorted land directory is searched only when a query enters another 32×32 block. Chill hopping can land only where the active lane's allowed mask matches the returned terrain kind. If a bird already occupies a roof, a hop target must return the same `surfaceId`, preventing it from hopping directly to an unrelated building or dropping to ground through ordinary wandering. Ground-to-roof entry remains possible. All height rectangles and cross-block fragments belonging to one building share a canonical surface identity. Custom jumps linearly interpolate from the source tile's base height to the destination tile's base height while adding the existing arc, so uphill and downhill hops do not snap at the end. Initial placement and the shared native-movement completion boundary also reapply the sampled surface height. Active and Tired inherit the composed ecology terrain policy unless their linked state profiles explicitly override it, so Bird retains rooftop authority in every state.

For direct MVP testing, the Y-menu follower release throw temporarily ignores all terrain and metatile-behavior blocking when it selects a landing coordinate. A released follower still receives any authored surface height at that coordinate, so throwing a bird onto one of the Cherrygrove roof points places it on the roof plane. This bypass is isolated to the Y-menu release path; ordinary wild spawning and profile-driven movement retain their normal terrain checks.

The runtime `OverworldWildBehaviorProfile` is not one small flat profile. It is a 138-byte composite of three 46-byte lanes:

```text
owner / Chill lane
Active linked lane
Tired linked lane
```

Movement selects one lane in constant time and reads that lane's allowed-terrain mask. Every state other than Active or Tired currently selects the owner/Chill lane. EMOTING does not choose movement destinations, so it does not need a fourth policy lane unless moving emotes are added later.

## Exact Override and State Resolution

The resolution order matters when terrain policy is authored:

1. Ordered generic and species class rules choose a class; later matching rules win.
2. The class's compact lane is copied as the owner lane, and inherited terrain bits resolve against the default `LAND` policy.
3. Every matching override is applied to the owner in table order. The resolver records which overrides matched.
4. The resolved owner's `activeProfile` and `tiredProfile` fields select linked override-profile records, with default Active/Tired fallbacks.
5. Active and Tired each restart from the original class lane and reapply the already-matched overrides, excluding that lane's selected linked profile. Member lists are not scanned again.
6. The selected linked profile is applied once at the end and is authoritative for that state.
7. Owner, Active, and Tired are assembled into the cached runtime composite.

This gives the desired profile → state behavior, but with one important authoring rule: Active and Tired profiles are globally shared linked records, not owner-local embedded copies. Editing a shared linked profile changes every owner that references it.

Generic linked state profiles should normally leave surface bits inherited so ecology overrides survive into those lanes. When a state genuinely needs different policy—such as a bird enabling `AIR` only while Active—it should select a dedicated reusable Bird Active profile. Tooling should offer clone/detach-on-write when an author wants a profile-local variant.

The resolver currently records applicable overrides in one `u32`, so it has a ceiling of 32 override-profile indices. The current count is 14. Creating unique linked profiles for every species × state combination would reach that limit quickly; reusable ecology/state profiles and curated member exceptions are more efficient.

## Recommended Evolution of Allowed Terrain

Reuse and widen the existing value/explicit pair inside `OverworldWildBehaviorProfileData`:

```c
typedef u32 OverworldWildSurfaceMask;

typedef struct OverworldWildSurfacePolicy {
    OverworldWildSurfaceMask valueMask;
    OverworldWildSurfaceMask explicitMask;
} OverworldWildSurfacePolicy;
```

The field names should become state-neutral, for example `allowedSurfaceMask` and `allowedSurfaceExplicitMask`; the containing owner, Active, or Tired lane supplies the state meaning. Surface composition should remain special-cased, as current terrain composition already is. A bitset should not participate in the generic numeric exact/relative/minimum/maximum operators.

`u16` is a viable constrained interim format. It can likely use alignment holes in the present records, grow a runtime composite only from 138 to 144 bytes, and leave 14 physical bits if `PLAYER` and `PLAYER_FRONT` temporarily occupy the upper two. However, the candidate catalog already wants more room once distinct water, roof, canopy, air, bridge, and ground surfaces are represented. A one-time move to `u32` avoids replacing one small ceiling with another.

With `u32`, the compact lane is expected to grow from 46 to about 52 bytes and the runtime composite from 138 to about 156 bytes. Exact ABI sizes must be asserted when implemented because padding affects override records. This modest data increase is preferable to a second policy hierarchy and second resolver.

`ALL` should eventually be derived from the defined catalog instead of remaining a hard-coded value. The C header, blob writer, validator, Python viewer, and V2 web editor still duplicate parts of the terrain catalog; they should consume one generated definition so every allowed surface is visible and the copies cannot drift. The rooftop MVP updates both editors to expose all seven current entries, including the previously hidden `PLAYER` bit.

## Physical Surface Catalog

The authoritative location should become `(tileX, tileZ, surfaceId)`, not only `(tileX, tileZ)`. A runtime surface reference can retain native height information and presentation policy:

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

Candidate leaf surfaces include:

- Ground, grass, sand, mud, snow, ice, and cave floor
- Shallow water, deep water, puddle, and magma
- Canopy or branch, roof, cliff shelf, and bridge deck
- Air

`surfaceId` distinguishes disconnected or vertically stacked surfaces of the same kind. For example, a bridge deck and water underneath may share X/Z without sharing `surfaceId`. Waterfall, whirlpool, ledge, climb, takeoff, and landing are better modeled as edge or transition attributes than destination surface kinds.

`PLAYER` and `PLAYER_FRONT` are not physical surfaces. They are dynamic target/occupancy permissions. They may remain compatibility bits during the first widening step, but should ultimately move to a separate destination-permission mask. Candidate resolution must use the player's actual physical surface and height; hard intersection with physical ecology/map masks must not accidentally erase these dynamic permissions.

Every flat map tile should resolve to one exact leaf classification. Broad groups such as `LANDLIKE` should be compile-time mask aliases, not overlapping runtime classifications. The current `LAND` predicate also accepts grass and many other passable terrain behaviors, so enabling `LAND` can presently defeat an attempt to disable `GRASS`. A 256-entry metatile-behavior → leaf-surface-bit table with explicit precedence fixes that and makes a candidate check one lookup and one bit test.

Canopies, roofs, rails, inaccessible cliff shelves, and similar model-defined surfaces need model-local data. The first scalable implementation now uses a land-data directory, compact constant-height fragments, and reusable dense-rectangle templates. Runtime lookup converts the world coordinate to a 32×32 block and local coordinate, reads the block's land-data ID from the existing map matrix, rejects unrelated instances by bounds, then derives `surfaceId`, node index, terrain kind, and height. A persistent block cache stores both successful and empty model lookups, so repeated movement and spawn queries in the same block do not rescan the 59-row sorted directory.

Scaling coverage should remain a build-time authoring/extraction task: inspect each land member's building records, associate recognized geometry with an authored dense footprint, sample its rendered upper surface, and emit only model-local instances. The game should not parse NSBMD geometry during movement. Equal-height coalescing handles pitched and gabled roofs without a runtime decoder; irregular footprints can later add bitmask templates while retaining the same directory and surface identity. A preview overlay should show generated world tiles and sampled heights before approval so coordinate or height mistakes are caught outside the ROM.

## Per-Spawn Policy

Each live spawn should use the same value/explicit representation for each movement lane:

```c
typedef struct OverworldWildSpawnSurfacePolicy {
    OverworldWildSurfacePolicy lane[3]; // Chill, Active, Tired
} OverworldWildSpawnSurfacePolicy;
```

With `u32` masks this costs 24 bytes per live slot, or 240 bytes for all ten slots. With a deliberately limited `u16` catalog it would cost 12 bytes per slot. Static authored overrides can be stored sparsely and expanded into the runtime sidecar.

Apply the spawn policy after complete class/override/linked-lane composition:

```c
requested = (resolvedLaneMask & ~spawn.explicitMask)
          | (spawn.valueMask & spawn.explicitMask);

effectivePhysical = requested
                  & ecology.supportedSurfaceMask
                  & mapAvailableSurfaceMask;
```

Dynamic target permissions must be composed separately once `PLAYER` and `PLAYER_FRONT` are migrated out of the physical catalog.

The final effective mask should be written into or cached beside the resolved lane. A spawn-policy edit needs only a per-slot policy revision and a recomposition of three words. It must not rerun class rules, override member scans, personal-data lookup, or map-surface discovery. Static spawn policy should be applied before validating the initial spawn destination.

An empty effective mask is valid only for an intentionally immobile state. Otherwise authoring validation should report it and runtime AI should idle rather than repeatedly perform a destination search or silently fall back to land.

## Ecology, Capabilities, and Behavior Intent

Battle type alone is too broad. Pidgey and Zubat may both be Flying-type, but they do not necessarily share roof-walking or perching behavior. Magnemite can hover without perching, while Aipom can use a canopy without true flight.

Three concepts should remain separate:

- **Ecology tags** group authored behavior intent: `ARBOREAL`, `ROOF_VISITOR`, `CLIFF_DWELLER`, `SHOREBIRD`, `MARSH_DWELLER`, or `CAVE_FLYER`.
- **Physical capabilities** gate mechanics: `CAN_WALK`, `CAN_HOP`, `CAN_FLY`, `CAN_HOVER`, `CAN_SWIM`, `CAN_WADE`, `CAN_PERCH`, `CAN_CLIMB`, `CAN_BURROW`, `CAN_SLIDE`, or `MAGMA_SAFE`.
- **Surface policy** says where the resolved profile wants the actor to move in Chill, Active, or Tired.

This separation answers how ecology fits the current override system efficiently:

- Use named override profiles and their existing shared member lists as the first authoring-level ecology groups. A species can be in several groups, ordered composition already works, and matching happens only during a cold resolve.
- Keep curated species exceptions in those lists rather than generating one profile per species.
- If a small stable vocabulary needs rule matching, a few of the ten currently spare `groupFlags` bits can represent high-level ecology tags. Existing matching is any-overlap only, so do not force all/none semantics into it.
- Add a separate ecology match mask only if the vocabulary outgrows those spare bits or genuinely needs `any`/`all`/`none` matching. Do not pre-emptively enlarge every match record.
- Never grant intrinsic capabilities through a behavior override. An override may request `ROOF`; a form-aware capability record decides whether that Pokemon can perch, fly, or climb there.

A compact intrinsic representation is one dense `u8 ecologyClassId` per species plus sorted form exceptions. A small class dictionary can resolve to:

```c
typedef struct OverworldWildResolvedEcology {
    u32 supportedSurfaceMask;
    u16 transitionCapabilityMask;
    u16 ecologyTags;
} OverworldWildResolvedEcology;
```

Resolve this once from species and form during spawn preparation. The current prepared-spawn path is form-aware, while a later cold behavior-cache path can rebuild type context from base-species personal data. Seeding both behavior and ecology caches from the prepared result avoids duplicate work and prevents this inconsistency.

## Cache and Runtime Efficiency

The runtime already caches a complete 138-byte three-lane profile per slot. A cache hit avoids context construction and member scans, but the profile is still copied by value and movement primitives are recomputed. Spawn preparation has already resolved a form-aware composite, yet slot initialization invalidates the cache, forcing a first-use resolve again.

Recommended changes are:

1. Seed the slot cache directly from the prepared spawn's resolved profile and form-aware ecology.
2. Cache derived movement primitives with the profile, or expose a stable cached lane/view instead of repeatedly copying the whole composite.
3. Cache the ordinary base of canopy profiles and apply only the small dynamic settled/alertness adjustment afterward; the current dynamic canopy path bypasses caching.
4. Include a spawn-policy revision and map-surface generation only when those values can change at runtime.
5. Keep exact flat-surface lookup and authored elevated-surface indices map-local and precomputed.

Candidate evaluation should then be constant work:

```c
allowedMask = cache->effectiveSurfaceMask[state];
candidateBit = mapSurfaceIndex->ResolveLeafBit(x, z, requestedLayer);

if ((allowedMask & candidateBit) == 0)
    return FALSE;

if ((edge->requiredCapabilities & cache->transitionCapabilityMask)
        != edge->requiredCapabilities)
    return FALSE;
```

It must not iterate every enabled surface, rescan behavior members, load personal data, inspect models, reload tree archives, or rediscover a canopy during candidate checks or pathfinding.

## Movement-System Integration

Allowed surfaces answer **where** a Pokemon may choose to go. Existing behavior fields and derived movement primitives answer **why and how** it moves. Permission to use `ROOF` does not make ordinary `WANDER` fly between disconnected buildings.

A destination resolver should return a concrete surface, because multiple layers can share X/Z:

```c
BOOL TryResolveMovementDestination(
    const OverworldWildMovementContext *context,
    int x,
    int z,
    OverworldWildSurfaceRef *destination);
```

A movement attempt should:

1. Select the cached Chill, Active, or Tired lane mask.
2. Resolve candidate surface nodes permitted by that mask.
3. Select an edge whose required capabilities are satisfied.
4. Reserve `(tileX, tileZ, surfaceId)` rather than only X/Z.
5. Dispatch the matching walk, hop, climb, takeoff, flight, landing, drop, swim, wade, burrow, or slide primitive.
6. Use native walking for ordinary same-surface edges where native collision agrees.
7. Reuse the custom jump/interpolation carrier for cross-surface transitions.
8. Commit the new surface only when movement succeeds.

Surface masks govern new destination selection, not instantaneous validity of the actor's current position. If a bird becomes Tired while airborne and Tired disables `AIR`, it should finish the current atomic edge and enter a landing search. It should not teleport or cancel halfway through a movement command.

For birds, a useful lifecycle is:

```text
PERCHED -> TAKEOFF -> AIRBORNE -> CRUISE/SWOOP -> LAND -> PERCHED
```

The first roof feature needs authored perch nodes, takeoff, short flight, and landing. It does not need freeform walking over arbitrary roof models.

With only ten wild actors, an O(10) reservation scan remains inexpensive. The necessary correction is comparing surface identity and compatible height, so a Pokemon on a bridge or roof does not block, target, or battle a player underneath. Occupancy, A-button targeting, contact/ram battles, ball targeting, shadows, and save restoration all need the same layer awareness.

## Physical Height and Visual Occlusion

Raising a map object is not sufficient to render a Pokemon on top of a tree canopy. Previous Mankey experiments tried object height, position-vector height, map-object flags, draw modes, callbacks, OAM/depth settings, follower proxies, special-field-object proxies, and late normal-map-object rendering. These remained behind the canopy or interfered with movement.

An attached follower/emote bubble did render above the same canopy. This proves that an above-canopy effect render family exists, although rendering a complete animated Pokemon through it remains unproven.

The most evidence-backed presentation design is:

- Keep a normal map object as the logical actor for identity, movement, collision, encounter state, and battle.
- Hide its normal visual on a visually occluded upper surface.
- Display a synchronized effect-owned Pokemon visual above the canopy or building.
- Synchronize species, form, shiny palette, facing, animation, movement offsets, and visibility.
- Tear the effect visual down on landing, battle, despawn, and map transition.

Accessible roofs, bridges, and terraces with genuine collision geometry may work with a normal elevated map object. Synthetic canopies and inaccessible roofs will probably require the effect-owned presentation path.

## Overlay and Data Constraints

The last linked artifacts in the workspace report approximately:

- Spawner overlay: 45,050 / 45,056 bytes, about 6 bytes free
- Helper overlay: effectively 2 bytes free
- Behavior-code overlay: 3,946 / 4,096 bytes, about 150 bytes free
- Behavior-data blob: 3,344 bytes

These artifacts predate or may not include all uncommitted profile changes, and no build was authorized for this reevaluation. Treat the figures as last-measured constraints, not a newly verified final map.

Substantial map-surface resolution or graph code cannot simply be appended to the current overlays. The implementation must replace legacy allowed-tile/canopy paths, reclaim code, move data-driven lookup into the heap-loaded behavior blob, allocate a new overlay, or deliberately repartition overlays.

The profile data increase is not the dominant cost. Even a `u32` lane policy remains small relative to the existing profile and cache. Duplicate resolvers, permanent compatibility paths, archive work inside movement, and visual infrastructure are the larger risks.

The behavior data version, C definitions, blob writer, validator, Python viewer, and V2 profile editor must change together. Compile-time size and offset assertions should make padding assumptions explicit.

## Example: Roof-Perching Bird

Suppose Pidgey matches an aggressive class, a Bird ecology override, and a Swarm override.

- The aggressive class supplies chase behavior and inherited ground policy.
- The Bird override supplies general perching intent and matches Pidgey through its curated ecology membership.
- Swarm changes group/pursuit behavior while leaving surface bits inherited.
- The owner selects reusable Bird Active and Bird Tired linked profiles.
- Bird Active explicitly enables `AIR`, `ROOF`, and `CANOPY` as needed.
- Bird Tired explicitly disables `AIR` but permits reachable landing surfaces.
- Pidgey's form-aware ecology class supplies `CAN_FLY`, `CAN_PERCH`, and compatible physical surfaces.
- A spawn policy can explicitly disable `ROOF` on a map whose roofs are not authored.

| State | Example effective surfaces | Movement consequence |
|---|---|---|
| Chill | Ground, roof, canopy | Wander locally or remain perched |
| Active | Ground, roof, canopy, air | Walk, take off, fly, or land using graph edges |
| Tired | Ground, roof, canopy | Finish the current flight and seek a legal landing |

This example deliberately uses Bird-specific linked profiles. If the shared Default Active/Tired profiles explicitly force `LAND`, their last-applied masks overwrite earlier Bird terrain choices. Generic defaults should inherit surface policy; intentional state differences belong in reusable dedicated linked profiles.

## Authoring and Validation

The current editors already provide tri-state terrain controls and linked-state editing. They should be evolved rather than replaced:

- Generate and display the complete centralized catalog.
- Show resolved policy and provenance for owner, Active, and Tired.
- Clearly label linked profiles as globally shared.
- Offer clone/detach-on-write for local state variants.
- Allow sparse per-spawn `INHERIT`/`ENABLE`/`DISABLE` policy.
- Distinguish physical surfaces from dynamic player-target permissions.

Validation should report or reject:

- Undefined bits or catalog/version disagreement across tools
- A non-immobile state with an empty effective mask
- A locomotion state with no compatible transition capability
- A flyer with no reachable Tired landing surface
- An initial destination excluded by final spawn policy
- Policy that targets no supported species/form or no surface present on the map
- An elevated surface without height, graph connectivity, or render policy
- Accidental edits to a linked state profile with broad downstream impact
- Override-profile growth approaching the current 32-profile resolver limit

## Terrain and Pokemon Opportunities

| Surface | Suitable Pokemon | Possible behavior |
|---|---|---|
| Tree canopy | Mankey, Aipom, birds, arboreal bugs | Branch hopping, resting, ambushing, dropping to ground |
| Roofs, chimneys, and signs | Small/medium birds, bats, some levitators | Perching, short walks, circling, swooping |
| Cliffs and rock shelves | Rock/Ground species, climbers, birds | Shelf walking, hopping, climbing, dropping |
| Sand and beaches | Sandshrew, Diglett, Hippopotas, crabs, shorebirds | Scuttling, burrowing, emerging |
| Mud, marsh, shallow water | Wooper, Quagsire, Croagunk, Barboach | Wading, splashing, land/water transitions |
| Snow | Ice species, mammals, winter birds | Powder movement, hiding, slower travel |
| Ice | Ice species, seals, penguin-like species | Sliding and controlled momentum |
| Bridges | Birds above, aquatic Pokemon below | Multi-layer occupancy at identical X/Z |
| Caves | Bats, rock Pokemon, spiders, lizards | Hovering, floor movement, authored wall perches |
| Water | Swimmers, amphibians, waterfowl | Swimming, shore transitions, landing on water |
| Magma | Selected Fire/Rock species or hoverers | Slow movement, hovering, no ordinary shadow |
| Tall grass | Small or stalking Pokemon | Partial hiding rather than elevated movement |

## Recommended Implementation Order

1. **Overlay ownership and renderer spike:** decide which legacy code is replaced or which new overlay owns surface logic, then render one fully animated effect-owned Pokemon above a known canopy while retaining a hidden logical map object.
2. **Evolve the existing masks:** choose the final catalog width, rename/widen the lane-local value/explicit masks, generate one catalog for C/validators/editors, separate or quarantine player-target bits, and replace broad OR predicates with exact leaf classification.
3. **Correct linked-state data:** make general Active/Tired profiles inherit surfaces and add a small set of reusable ecology-specific linked profiles where states genuinely differ.
4. **Seed the resolved cache:** carry the prepared form-aware composite and ecology class into slot state, cache primitives, and make canopy's dynamic adjustment cache-friendly.
5. **Layer-aware interactions:** make occupancy, reservations, targeting, and battles surface-aware; prove that actors can coexist on a native bridge deck and below it.
6. **Canopy support:** turn tree-top discovery into cached surface nodes with explicit height and presentation policy.
7. **Roof-bird pilot:** author one roof-perch network and one bird lifecycle using perch, takeoff, flight, and landing.
8. **Flat terrain ecology:** add sand, mud, snow, ice, shallow-water, cave, and cliff behavior through the same catalog and mask system.
9. **Connected elevated networks:** add larger roof, cliff, canopy, and aerial graphs after the basic runtime and rendering paths are proven.

The visual renderer remains the go/no-go experiment for convincing tree-top and inaccessible-roof presentation. The allowed-surface evolution is already compatible with the refactored profile system and can proceed independently.
