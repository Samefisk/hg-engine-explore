/*
 * Overworld Viewer V2 — profile workspace
 *
 * This module owns its DOM and draft state. It intentionally depends only on
 * the documented data.json model and injected API/callbacks, so the profile
 * editor can evolve independently from the legacy viewer implementation.
 */

const DEFAULT_MATCH = Object.freeze({
  groupMask: "OW_WILD_BEHAVIOR_GROUP_NONE",
  species: "OW_WILD_BEHAVIOR_MATCH_ANY_SPECIES",
  terrain: "OW_WILD_BEHAVIOR_MATCH_ANY_TERRAIN",
  minLevel: "OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY",
  maxLevel: "OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY",
  shiny: "OW_WILD_BEHAVIOR_MATCH_ANY_SHINY",
  behaviorClass: "OW_WILD_BEHAVIOR_MATCH_ANY_CLASS",
});

const CONDITIONAL_PROFILE_NONE = "OW_WILD_BEHAVIOR_CONDITIONAL_PROFILE_NONE";
const CONDITION_ON_ROOFTOP = "OW_WILD_BEHAVIOR_CONDITION_ON_ROOFTOP_OR_SIGNPOST";
const LEGACY_CONDITION_ON_ROOFTOP = "OW_WILD_BEHAVIOR_CONDITION_ON_ROOFTOP";
const CONDITION_ON_ROOFTOP_BIT = 1;
const CONDITIONAL_DEFAULT_TERRAIN_BITS = 64 | 128;
const CONDITIONAL_MOVEMENT_SPEED_MAX = 4;
const CONDITIONAL_PROFILE_NONE_VALUE = 0xFF;
const CONDITIONS_LIFECYCLE_SECTION_ID = "conditions";
const CONDITIONAL_LIFECYCLE_SECTION_PREFIX = "conditional:";

const TARGET_KINDS = Object.freeze([
  ["pokemon", "Pokémon"],
  ["family", "Evolution family"],
  ["type", "Typing"],
  ["spawnPool", "Spawn pool"],
]);

const SPAWN_POOLS = Object.freeze([
  { key: "land", label: "Land", raw: "OW_WILD_SPAWN_TERRAIN_LAND", tableKeys: ["morning", "day", "night", "hoenn", "sinnoh"], swarmKeys: ["landSwarm"] },
  { key: "surf", label: "Surf", raw: "OW_WILD_SPAWN_TERRAIN_SURF", tableKeys: ["surf"], swarmKeys: ["surfSwarm"] },
  { key: "fish", label: "Fishing", raw: "OW_WILD_SPAWN_TERRAIN_FISHING", tableKeys: ["oldRod", "goodRod", "superRod"], swarmKeys: ["nightFish", "fishSwarm"] },
  { key: "headbutt", label: "Headbutt", raw: "OW_WILD_SPAWN_TERRAIN_HEADBUTT", tableKeys: ["headbuttNormal", "headbuttSpecial"], swarmKeys: [] },
]);

const MATCH_FIELDS = Object.freeze([
  ["species", "Pokémon"],
  ["groupMask", "Group mask"],
  ["terrain", "Terrain"],
  ["minLevel", "Minimum level"],
  ["maxLevel", "Maximum level"],
  ["shiny", "Shiny"],
  ["behaviorClass", "Base profile"],
]);

const PROFILE_FIELD_RANGES = Object.freeze([
  Object.freeze({ min: "spawnDestinationMinDistance", max: "spawnDestinationMaxDistance", label: "Spawn distance", unit: "tiles" }),
  Object.freeze({ min: "hopMinDistance", max: "hopMaxDistance", label: "Hop distance", unit: "tiles" }),
  Object.freeze({ min: "attentiveHopMinDistance", max: "attentiveHopMaxDistance", label: "Hop distance", unit: "tiles" }),
  Object.freeze({ min: "tiredHopMinDistance", max: "tiredHopMaxDistance", label: "Hop distance", unit: "tiles" }),
]);

const COUPLED_OVERRIDE_FIELD_GROUPS = Object.freeze([
  Object.freeze(["chillAllowedTerrainMask", "chillAllowedTerrainOverrideMask"]),
  Object.freeze(["spawnDestinationMask", "spawnDestinationOverrideMask"]),
]);

const TERRAIN_POLICY_CONFIGS = Object.freeze({
  allowed: Object.freeze({
    valueField: "chillAllowedTerrainMask",
    explicitField: "chillAllowedTerrainOverrideMask",
    label: "Allowed terrains",
    note: "Set each terrain independently",
    ariaLabel: "Allowed terrain policy",
  }),
  spawn: Object.freeze({
    valueField: "spawnDestinationMask",
    explicitField: "spawnDestinationOverrideMask",
    label: "Spawn destinations",
    note: "Set each destination independently",
    ariaLabel: "Spawn destination policy",
  }),
});

const HIDDEN_PROFILE_EDITOR_FIELDS = Object.freeze([
  "spawnDestination",
]);

const PROFILE_FIELD_RANGE_BY_MIN = new Map(PROFILE_FIELD_RANGES.map((range) => [range.min, range]));

const PROFILE_FIELD_COMPOSITES = Object.freeze({
  "alert-response": Object.freeze({
    id: "alert-response",
    label: "Alert response",
    fields: Object.freeze([
      Object.freeze({ key: "alertState", label: "Mode", unit: "" }),
      Object.freeze({ key: "alertEmote", label: "Emote", unit: "" }),
      Object.freeze({ key: "alertTime", label: "Time", unit: "frames" }),
      Object.freeze({ key: "alertChance", label: "Chance", unit: "%" }),
    ]),
  }),
  "active-chase-boost": Object.freeze({
    id: "active-chase-boost",
    label: "Chase boost",
    fields: Object.freeze([
      Object.freeze({ key: "attentiveChaseBoostDistance", label: "Distance", unit: "tiles" }),
      Object.freeze({ key: "attentiveChaseBoostSpeed", label: "Speed", unit: "speed" }),
    ]),
  }),
  "active-target-tiles": Object.freeze({
    id: "active-target-tiles",
    label: "Target & tiles",
    fields: Object.freeze([
      Object.freeze({ key: "targetSelector", label: "Target", unit: "" }),
      Object.freeze({ key: "attentiveAllowedTile", label: "Allowed tile", unit: "" }),
      Object.freeze({ key: "attentiveAllowedTile2", label: "Allowed tile 2", unit: "" }),
    ]),
  }),
  "movement-chain": Object.freeze({
    id: "movement-chain",
    label: "Movement chain",
    fields: Object.freeze([
      Object.freeze({ key: "ramAccelerationSteps", label: "Moves", unit: "moves" }),
      Object.freeze({ key: "chainMovementVariance", label: "Move variance", unit: "moves", note: "Adds a random 0 through this value to each new movement chain" }),
      Object.freeze({ key: "ramMaxSpeed", label: "Pause", unit: "frames" }),
      Object.freeze({ key: "chainPauseVariance", label: "Pause variance", unit: "frames", note: "Adds a random 0 through this value to passive and Look around pauses, or to the total Reposition jumps duration; ignored by Reposition steps, Reposition skids, and successful Hop in place actions" }),
      Object.freeze({ key: "chainPauseAction", label: "Pause action", unit: "" }),
      Object.freeze({ key: "chainRepositionJumpCount", label: "Reposition moves", unit: "moves", note: "Number of fixed-facing random jumps, steps, or skids. Steps and skids finish the pause after the final move" }),
      Object.freeze({ key: "chainRepositionSpeed", label: "Reposition speed", unit: "speed", note: "Movement speed for Reposition steps and skids; jumps use Hop timing" }),
      Object.freeze({ key: "chainRepositionDistance", label: "Skid distance", unit: "tiles", note: "Tiles travelled by each Reposition skid" }),
      Object.freeze({ key: "chainRepositionDust", label: "Skid dust", unit: "", note: "Play a dust particle on every tile crossed by a Reposition skid" }),
      Object.freeze({ key: "chainRepositionAllowCardinal", label: "Cardinal directions", unit: "", note: "Allow up, down, left, and right Reposition directions" }),
      Object.freeze({ key: "chainRepositionAllowDiagonal", label: "Diagonal directions", unit: "", note: "Allow diagonal Reposition directions" }),
    ]),
  }),
  "movement-chain-or-ram": Object.freeze({
    id: "movement-chain-or-ram",
    label: "Shared Chain / RAM tuning",
    fields: Object.freeze([
      Object.freeze({
        key: "ramAccelerationSteps",
        label: "Move count / RAM interval",
        unit: "moves / steps",
        note: "Chain move count or RAM acceleration interval, depending on the inherited movement style. Zero disables both behaviors",
      }),
      Object.freeze({
        key: "chainMovementVariance",
        label: "Chain variance",
        unit: "moves",
        note: "Adds a random 0 through this value when a movement chain begins; ignored by RAM",
      }),
      Object.freeze({
        key: "ramMaxSpeed",
        label: "Pause / max speed",
        unit: "frames / speed tier",
        note: "Chain pause duration or RAM maximum speed, depending on the inherited movement style",
      }),
      Object.freeze({
        key: "chainPauseVariance",
        label: "Pause variance",
        unit: "frames",
        note: "Adds a random 0 through this value to passive and Look around pauses, or to the total Reposition jumps duration; ignored by RAM, Reposition steps, Reposition skids, and successful Hop in place actions",
      }),
      Object.freeze({
        key: "chainPauseAction",
        label: "Chain pause action",
        unit: "",
        note: "Ignored when the inherited movement style uses RAM",
      }),
      Object.freeze({
        key: "chainRepositionJumpCount",
        label: "Reposition moves",
        unit: "moves",
        note: "Number of fixed-facing random surrounding-tile jumps, steps, or skids",
      }),
      Object.freeze({
        key: "chainRepositionSpeed",
        label: "Reposition speed",
        unit: "speed",
        note: "Movement speed for Reposition steps and skids; jumps use Hop timing",
      }),
      Object.freeze({ key: "chainRepositionDistance", label: "Skid distance", unit: "tiles", note: "Tiles travelled by each Reposition skid" }),
      Object.freeze({ key: "chainRepositionDust", label: "Skid dust", unit: "", note: "Play a dust particle on every tile crossed by a Reposition skid" }),
      Object.freeze({ key: "chainRepositionAllowCardinal", label: "Cardinal directions", unit: "", note: "Allow up, down, left, and right Reposition directions" }),
      Object.freeze({ key: "chainRepositionAllowDiagonal", label: "Diagonal directions", unit: "", note: "Allow diagonal Reposition directions" }),
    ]),
  }),
  "hop-path-chill": Object.freeze({
    id: "hop-path-chill",
    label: "Hop path",
    range: Object.freeze({ min: "hopMinDistance", max: "hopMaxDistance", label: "Hop distance", unit: "tiles" }),
    fields: Object.freeze([
      Object.freeze({ key: "hopAllowNonCardinal", label: "Diagonal hops", unit: "", note: "Allows non-cardinal directions" }),
      Object.freeze({ key: "hopAllowVerticalObstacles", label: "Cross vertical obstacles", unit: "", note: "Off rejects intersecting arcs. On raises the arc enough to clear catalogued vertical obstacles" }),
      Object.freeze({ key: "hopMinDistance", label: "Min distance", unit: "tiles" }),
      Object.freeze({ key: "hopMaxDistance", label: "Max distance", unit: "tiles" }),
    ]),
  }),
  "hop-path-active": Object.freeze({
    id: "hop-path-active",
    label: "Hop path",
    range: Object.freeze({ min: "attentiveHopMinDistance", max: "attentiveHopMaxDistance", label: "Hop distance", unit: "tiles" }),
    fields: Object.freeze([
      Object.freeze({ key: "attentiveHopAllowNonCardinal", label: "Diagonal hops", unit: "", note: "Allows non-cardinal directions" }),
      Object.freeze({ key: "hopAllowVerticalObstacles", label: "Cross vertical obstacles", unit: "", note: "Shared policy from the linked profile. On raises intersecting arcs to clear catalogued obstacles" }),
      Object.freeze({ key: "attentiveHopMinDistance", label: "Min distance", unit: "tiles" }),
      Object.freeze({ key: "attentiveHopMaxDistance", label: "Max distance", unit: "tiles" }),
    ]),
  }),
  "hop-path-tired": Object.freeze({
    id: "hop-path-tired",
    label: "Hop path",
    range: Object.freeze({ min: "tiredHopMinDistance", max: "tiredHopMaxDistance", label: "Hop distance", unit: "tiles" }),
    fields: Object.freeze([
      Object.freeze({ key: "tiredHopAllowNonCardinal", label: "Diagonal hops", unit: "", note: "Allows non-cardinal directions" }),
      Object.freeze({ key: "hopAllowVerticalObstacles", label: "Cross vertical obstacles", unit: "", note: "Shared policy from the linked profile. On raises intersecting arcs to clear catalogued obstacles" }),
      Object.freeze({ key: "tiredHopMinDistance", label: "Min distance", unit: "tiles" }),
      Object.freeze({ key: "tiredHopMaxDistance", label: "Max distance", unit: "tiles" }),
    ]),
  }),
  "hop-timing-chill": Object.freeze({
    id: "hop-timing-chill",
    label: "Hop timing",
    fields: Object.freeze([
      Object.freeze({ key: "hopTime", label: "Travel time", unit: "frames/tile", note: "Shared by all movement states. Zero is immediate" }),
      Object.freeze({ key: "hopElevationTimeScale", label: "Elevation time scaling", unit: "%", note: "Added airtime for elevation changes. 0 disables it; 100 matches travel speed; higher values feel heavier" }),
      Object.freeze({ key: "hopElevationArcScale", label: "Elevation arc scaling", unit: "%", note: "Added arc height for elevation changes. 0 keeps the level-jump arc; 100 clears the higher endpoint; higher values feel floatier" }),
      Object.freeze({ key: "hopPause", label: "Pause", unit: "frames", note: "Chill only. Zero removes the pause" }),
      Object.freeze({ key: "hopSpinSpeed", label: "Spin interval", unit: "frames/turn", note: "Shared by Chill and Tired. Zero disables spinning" }),
      Object.freeze({ key: "hopSwayWidth", label: "Horizontal sway", unit: "px", note: "Side-to-side drift during each hop. Zero disables sway" }),
    ]),
  }),
  "hop-timing-active": Object.freeze({
    id: "hop-timing-active",
    label: "Hop timing",
    fields: Object.freeze([
      Object.freeze({ key: "hopTime", label: "Travel time", unit: "frames/tile", note: "Shared by all movement states. Zero is immediate" }),
      Object.freeze({ key: "hopElevationTimeScale", label: "Elevation time scaling", unit: "%", note: "Added airtime for elevation changes. 0 disables it; 100 matches travel speed; higher values feel heavier" }),
      Object.freeze({ key: "hopElevationArcScale", label: "Elevation arc scaling", unit: "%", note: "Added arc height for elevation changes. 0 keeps the level-jump arc; 100 clears the higher endpoint; higher values feel floatier" }),
      Object.freeze({ key: "attentiveHopPause", label: "Pause", unit: "frames", note: "Active only. Zero removes the pause" }),
      Object.freeze({ key: "attentiveHopSpinSpeed", label: "Spin interval", unit: "frames/turn", note: "Active only. Zero disables spinning" }),
      Object.freeze({ key: "hopSwayWidth", label: "Horizontal sway", unit: "px", note: "Shared setting from the linked profile. Zero disables sway" }),
    ]),
  }),
  "hop-timing-tired": Object.freeze({
    id: "hop-timing-tired",
    label: "Hop timing",
    fields: Object.freeze([
      Object.freeze({ key: "hopTime", label: "Travel time", unit: "frames/tile", note: "Shared by all movement states. Zero is immediate" }),
      Object.freeze({ key: "hopElevationTimeScale", label: "Elevation time scaling", unit: "%", note: "Added airtime for elevation changes. 0 disables it; 100 matches travel speed; higher values feel heavier" }),
      Object.freeze({ key: "hopElevationArcScale", label: "Elevation arc scaling", unit: "%", note: "Added arc height for elevation changes. 0 keeps the level-jump arc; 100 clears the higher endpoint; higher values feel floatier" }),
      Object.freeze({ key: "tiredHopPause", label: "Pause", unit: "frames", note: "Tired only. Zero removes the pause" }),
      Object.freeze({ key: "hopSpinSpeed", label: "Spin interval", unit: "frames/turn", note: "Shared by Chill and Tired. Zero disables spinning" }),
      Object.freeze({ key: "hopSwayWidth", label: "Horizontal sway", unit: "px", note: "Shared setting from the linked profile. Zero disables sway" }),
    ]),
  }),
  "teleport-timing-chill": Object.freeze({
    id: "teleport-timing-chill",
    label: "Teleport timing",
    fields: Object.freeze([
      Object.freeze({ key: "teleportTime", label: "Travel time", unit: "frames", note: "Zero is immediate" }),
      Object.freeze({ key: "teleportPause", label: "Post-teleport pause", unit: "frames", note: "Zero removes the pause" }),
    ]),
  }),
  "teleport-timing-active": Object.freeze({
    id: "teleport-timing-active",
    label: "Teleport timing",
    fields: Object.freeze([
      Object.freeze({ key: "attentiveTeleportTime", label: "Travel time", unit: "frames", note: "Zero is immediate" }),
      Object.freeze({ key: "attentiveTeleportPause", label: "Post-teleport pause", unit: "frames", note: "Zero removes the pause" }),
    ]),
  }),
  "teleport-timing-tired": Object.freeze({
    id: "teleport-timing-tired",
    label: "Teleport timing",
    fields: Object.freeze([
      Object.freeze({ key: "tiredTeleportTime", label: "Travel time", unit: "frames", note: "Zero is immediate" }),
      Object.freeze({ key: "tiredTeleportPause", label: "Post-teleport pause", unit: "frames", note: "Zero removes the pause" }),
    ]),
  }),
  "ram-tuning-chill": Object.freeze({
    id: "ram-tuning-chill",
    label: "RAM tuning",
    fields: Object.freeze([
      Object.freeze({ key: "ramAccelerationSteps", label: "Accelerate every", unit: "steps", note: "Zero disables acceleration. Shared with Movement Chain move count" }),
      Object.freeze({ key: "ramMaxSpeed", label: "Max speed", unit: "speed tier", note: "Zero or a value below starting speed keeps the starting speed. Shared with Movement Chain pause frames" }),
    ]),
  }),
  "ram-tuning-active": Object.freeze({
    id: "ram-tuning-active",
    label: "RAM tuning",
    fields: Object.freeze([
      Object.freeze({ key: "attentiveRamAccelerationSteps", label: "Accelerate every", unit: "steps", note: "Zero disables acceleration" }),
      Object.freeze({ key: "attentiveRamMaxSpeed", label: "Max speed", unit: "speed tier", note: "Zero or a value below starting speed keeps the starting speed" }),
    ]),
  }),
  "ram-tuning-tired": Object.freeze({
    id: "ram-tuning-tired",
    label: "RAM tuning",
    fields: Object.freeze([
      Object.freeze({ key: "tiredRamAccelerationSteps", label: "Accelerate every", unit: "steps", note: "Zero disables acceleration" }),
      Object.freeze({ key: "tiredRamMaxSpeed", label: "Max speed", unit: "speed tier", note: "Zero or a value below starting speed keeps the starting speed" }),
    ]),
  }),
});

const FIELD_SECTIONS = Object.freeze([
  {
    id: "spawn",
    title: "Spawn",
    hint: "Entry behavior, destination, distance, and population limits.",
    fields: [
      "spawnState", "spawnHopTime", "spawnHopSwayWidth", "spawnDestinationMask", "spawnDestinationOverrideMask",
      "spawnDestinationMinDistance", "spawnDestinationMaxDistance", "jumpLevel", "overworldLimit",
    ],
    nodes: [
      { kind: "branch", field: "spawnState", branch: "spawn-state" },
      { kind: "branch", field: "spawnDestinationMask", branch: "spawn-destination", virtual: "spawn-destination-policy" },
      { kind: "fields", fields: ["jumpLevel", "overworldLimit"] },
    ],
  },
  {
    id: "chill",
    title: "Chill state",
    hint: "Default behavior and movement before the Pokémon becomes alert.",
    sharedMovement: true,
    subtabs: Object.freeze([
      Object.freeze({ id: "behavior", label: "Behavior" }),
      Object.freeze({ id: "movement", label: "Movement style" }),
    ]),
    fields: [
      "chillState", "chillTarget", "chillAllowedTerrainMask", "chillAllowedTerrainOverrideMask",
      "chillAction", "chillSpeed", "hopAllowNonCardinal", "hopMinDistance",
      "hopAllowVerticalObstacles", "hopMaxDistance", "hopTime", "hopElevationTimeScale", "hopElevationArcScale", "hopSpinSpeed", "hopSwayWidth", "hopPause", "teleportTime",
      "teleportPause", "ramAccelerationSteps", "chainMovementVariance", "ramMaxSpeed", "chainPauseVariance", "chainPauseAction",
      "chainRepositionJumpCount",
      "chainRepositionSpeed",
      "chainRepositionDistance", "chainRepositionDust",
      "chainRepositionAllowCardinal", "chainRepositionAllowDiagonal",
      "tilesToAccelerate", "maxWalkSpeed",
      "battleTrigger", "chaseBoostDistance", "chaseBoostSpeed",
      "circleRadius", "continueWhenArrived", "avoidPreviousTile", "playerAdjacentDirectionMasks",
      "alertSpecialAction",
    ],
    nodes: [
      { kind: "branch", field: "chillState", branch: "chill-behavior", subtab: "behavior" },
      {
        kind: "fields",
        fields: [
          "battleTrigger", "chaseBoostDistance", "chaseBoostSpeed",
          "circleRadius", "continueWhenArrived", "avoidPreviousTile",
        ],
        subtab: "behavior",
      },
      { kind: "branch", field: "alertSpecialAction", branch: "scoped-action", scope: "active", virtual: "scoped-action" },
      { kind: "branch", field: "chillAction", branch: "movement", scope: "chill", subtab: "movement" },
    ],
  },
  {
    id: "alert",
    title: "Alert",
    hint: "Detection, reaction, range, and alert-time action.",
    scopedAction: "alert",
    fields: [
      "alertState", "alertEmote", "alertTime", "alertness", "alertRange", "alertChance",
      "alertSpecialAction",
    ],
    nodes: [
      { kind: "fields", composite: "alert-response", fields: ["alertState", "alertEmote", "alertTime", "alertChance"] },
      { kind: "branch", field: "alertRange", branch: "alert-range", virtual: "alert-range-type" },
      { kind: "branch", field: "alertSpecialAction", branch: "scoped-action", scope: "alert", virtual: "scoped-action" },
    ],
  },
  {
    id: "active",
    title: "Active state",
    hint: "Choose the override profile applied while this Pokémon is active.",
    stateProfileField: "activeProfile",
    fields: ["stamina", "activeProfile"],
  },
  {
    id: "tired",
    title: "Tired state",
    hint: "Choose the override profile applied while this Pokémon is tired.",
    stateProfileField: "tiredProfile",
    fields: ["restTime", "tiredProfile"],
  },
  {
    id: "stats",
    title: "Stats",
    hint: "Shared behavior distances and thresholds.",
    fields: ["range"],
    nodes: [{ kind: "fields", fields: ["range"] }],
  },
  {
    id: "special",
    title: "Special",
    hint: "Behavior-family metadata used by engine integrations.",
    fields: ["profileId"],
    nodes: [{ kind: "fields", fields: ["profileId"] }],
  },
]);

const LIFECYCLE_SECTION_IDS = Object.freeze(["spawn", "chill", "alert", "active", "tired"]);
const LIFECYCLE_SECTION_ID_SET = new Set(LIFECYCLE_SECTION_IDS);
const LIFECYCLE_TAB_SUMMARY_FIELDS = Object.freeze({
  chill: Object.freeze([
    Object.freeze({ field: "chillState", tabId: "behavior" }),
    Object.freeze({ field: "chillAction", tabId: "movement" }),
  ]),
  active: Object.freeze([
    Object.freeze({ field: "activeProfile", profileReference: true }),
  ]),
  tired: Object.freeze([
    Object.freeze({ field: "tiredProfile", profileReference: true }),
  ]),
});

// Active and Tired now execute another profile's Chill state. Keep the Chill
// value catalog broad enough to author values that previously appeared only in
// the state-specific editors, while retaining the existing stored field names.
const LINKED_CHILL_OPTION_SOURCES = Object.freeze({
  chillState: Object.freeze(["attentiveState", "tiredState"]),
  chillTarget: Object.freeze(["targetSelector"]),
  chillAction: Object.freeze(["movementStyle", "specialAction"]),
  chillSpeed: Object.freeze(["attentiveSpeed", "tiredSpeed"]),
  hopAllowNonCardinal: Object.freeze(["attentiveHopAllowNonCardinal", "tiredHopAllowNonCardinal"]),
  hopMinDistance: Object.freeze(["attentiveHopMinDistance", "tiredHopMinDistance"]),
  hopMaxDistance: Object.freeze(["attentiveHopMaxDistance", "tiredHopMaxDistance"]),
  hopPause: Object.freeze(["attentiveHopPause", "tiredHopPause"]),
  hopSpinSpeed: Object.freeze(["attentiveHopSpinSpeed"]),
  teleportTime: Object.freeze(["attentiveTeleportTime", "tiredTeleportTime"]),
  teleportPause: Object.freeze(["attentiveTeleportPause", "tiredTeleportPause"]),
  ramAccelerationSteps: Object.freeze(["attentiveRamAccelerationSteps", "tiredRamAccelerationSteps"]),
  ramMaxSpeed: Object.freeze(["attentiveRamMaxSpeed", "tiredRamMaxSpeed"]),
});

const TARGETABLE_BEHAVIORS = Object.freeze(new Set([
  "OW_WILD_BEHAVIOR_KIND_CHASE",
  "OW_WILD_BEHAVIOR_KIND_FLEE",
  "OW_WILD_BEHAVIOR_KIND_PLAYFUL",
  "OW_WILD_BEHAVIOR_KIND_RAM",
  "OW_WILD_BEHAVIOR_KIND_HEADBUTT_TREE_HOP",
]));

const TILE_BEHAVIORS = Object.freeze(new Set([
  "OW_WILD_BEHAVIOR_KIND_WANDER",
  ...TARGETABLE_BEHAVIORS,
]));

const LOCOMOTION = Object.freeze({
  none: "OW_WILD_BEHAVIOR_LOCOMOTION_NONE",
  wander: "OW_WILD_BEHAVIOR_LOCOMOTION_WANDER",
  hop: "OW_WILD_BEHAVIOR_LOCOMOTION_HOP",
  ram: "OW_WILD_BEHAVIOR_LOCOMOTION_RAM",
  teleport: "OW_WILD_BEHAVIOR_LOCOMOTION_PHANTOM_TELEPORT",
  turnAround: "OW_WILD_BEHAVIOR_LOCOMOTION_TURN_AROUND",
});

const CHAIN_LOCOMOTIONS = Object.freeze(new Set([
  LOCOMOTION.wander,
  LOCOMOTION.hop,
  LOCOMOTION.teleport,
]));

const RAW_LABEL_OVERRIDES = Object.freeze({
  [LOCOMOTION.wander]: "Walk",
  [LOCOMOTION.turnAround]: "Turn Around",
  "OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_JUMPS": "Reposition jumps",
  "OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_STEPS": "Reposition steps",
  "OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_SKIDS": "Reposition skids",
});

const MOVEMENT_FIELDS = Object.freeze({
  chill: Object.freeze({
    speed: "chillSpeed",
    maxWalkSpeed: "maxWalkSpeed",
    walkAcceleration: "tilesToAccelerate",
    hopPath: Object.freeze({ composite: "hop-path-chill", fields: Object.freeze(["hopAllowNonCardinal", "hopAllowVerticalObstacles", "hopMinDistance", "hopMaxDistance"]) }),
    hopTiming: Object.freeze({ composite: "hop-timing-chill", fields: Object.freeze(["hopTime", "hopElevationTimeScale", "hopElevationArcScale", "hopPause", "hopSpinSpeed", "hopSwayWidth"]) }),
    chain: ["ramAccelerationSteps", "chainMovementVariance", "ramMaxSpeed", "chainPauseVariance", "chainPauseAction", "chainRepositionJumpCount", "chainRepositionSpeed", "chainRepositionDistance", "chainRepositionDust", "chainRepositionAllowCardinal", "chainRepositionAllowDiagonal"],
    teleportTiming: Object.freeze({ composite: "teleport-timing-chill", fields: Object.freeze(["teleportTime", "teleportPause"]) }),
    ramTuning: Object.freeze({ composite: "ram-tuning-chill", fields: Object.freeze(["ramAccelerationSteps", "ramMaxSpeed"]) }),
  }),
  active: Object.freeze({
    speed: "attentiveSpeed",
    maxWalkSpeed: "maxWalkSpeed",
    walkAcceleration: "tilesToAccelerate",
    hopPath: Object.freeze({ composite: "hop-path-active", fields: Object.freeze(["attentiveHopAllowNonCardinal", "hopAllowVerticalObstacles", "attentiveHopMinDistance", "attentiveHopMaxDistance"]) }),
    hopTiming: Object.freeze({ composite: "hop-timing-active", fields: Object.freeze(["hopTime", "hopElevationTimeScale", "hopElevationArcScale", "attentiveHopPause", "attentiveHopSpinSpeed", "hopSwayWidth"]) }),
    chain: ["ramAccelerationSteps", "chainMovementVariance", "ramMaxSpeed", "chainPauseVariance", "chainPauseAction", "chainRepositionJumpCount", "chainRepositionSpeed", "chainRepositionDistance", "chainRepositionDust", "chainRepositionAllowCardinal", "chainRepositionAllowDiagonal"],
    teleportTiming: Object.freeze({ composite: "teleport-timing-active", fields: Object.freeze(["attentiveTeleportTime", "attentiveTeleportPause"]) }),
    ramTuning: Object.freeze({ composite: "ram-tuning-active", fields: Object.freeze(["attentiveRamAccelerationSteps", "attentiveRamMaxSpeed"]) }),
  }),
  tired: Object.freeze({
    speed: "tiredSpeed",
    maxWalkSpeed: "maxWalkSpeed",
    walkAcceleration: "tilesToAccelerate",
    hopPath: Object.freeze({ composite: "hop-path-tired", fields: Object.freeze(["tiredHopAllowNonCardinal", "hopAllowVerticalObstacles", "tiredHopMinDistance", "tiredHopMaxDistance"]) }),
    hopTiming: Object.freeze({ composite: "hop-timing-tired", fields: Object.freeze(["hopTime", "hopElevationTimeScale", "hopElevationArcScale", "tiredHopPause", "hopSpinSpeed", "hopSwayWidth"]) }),
    chain: ["ramAccelerationSteps", "chainMovementVariance", "ramMaxSpeed", "chainPauseVariance", "chainPauseAction", "chainRepositionJumpCount", "chainRepositionSpeed", "chainRepositionDistance", "chainRepositionDust", "chainRepositionAllowCardinal", "chainRepositionAllowDiagonal"],
    teleportTiming: Object.freeze({ composite: "teleport-timing-tired", fields: Object.freeze(["tiredTeleportTime", "tiredTeleportPause"]) }),
    ramTuning: Object.freeze({ composite: "ram-tuning-tired", fields: Object.freeze(["tiredRamAccelerationSteps", "tiredRamMaxSpeed"]) }),
  }),
});

const CIRCLE_PLAYER_TARGET = "OW_WILD_BEHAVIOR_TARGET_CIRCLE_PLAYER";
const NEXT_TO_PLAYER_TARGET = "OW_WILD_BEHAVIOR_TARGET_NEXT_TO_PLAYER";
const SPAWN_HOP_FROM_OFF_SCREEN = "OW_WILD_BEHAVIOR_SPAWN_STATE_HOP_FROM_OFF_SCREEN";
const ALERT_SPECIAL = Object.freeze({
  none: "OW_WILD_BEHAVIOR_ALERT_SPECIAL_NONE",
  call: "OW_WILD_BEHAVIOR_ALERT_SPECIAL_CALL_FOR_HELP",
  throw: "OW_WILD_BEHAVIOR_ALERT_SPECIAL_PICKUP_THROW",
});

const ANY_MATCH_PREFIXES = Object.freeze([
  "OW_WILD_BEHAVIOR_MATCH_ANY_",
  "OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY",
  "OW_WILD_BEHAVIOR_GROUP_NONE",
]);

const RAM_LOCOMOTION = "OW_WILD_BEHAVIOR_LOCOMOTION_RAM";

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function humanizeRaw(value) {
  const raw = String(value ?? "");
  if (!raw) return "Not set";
  return raw
    .replace(/^OW_WILD_BEHAVIOR_/, "")
    .replace(/^OW_WILD_SPAWNER_/, "")
    .replace(/^OW_WILD_SPAWN_/, "")
    .replace(/^SPECIES_/, "")
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function valueRaw(value) {
  if (value && typeof value === "object") return String(value.raw ?? value.symbol ?? value.value ?? "");
  return String(value ?? "");
}

function valueLabel(value) {
  const raw = valueRaw(value);
  if (RAW_LABEL_OVERRIDES[raw]) return RAW_LABEL_OVERRIDES[raw];
  if (value && typeof value === "object") {
    return String(value.label ?? value.name ?? humanizeRaw(value.raw ?? value.symbol ?? value.value));
  }
  return humanizeRaw(value);
}

function unique(values) {
  return [...new Set(values.filter((value) => value !== undefined && value !== null && value !== ""))];
}

function isOverrideProfile(profile) {
  return Boolean(profile?.isOverrideProfile || profile?.kind === "override" || String(profile?.index ?? "").startsWith("override:"));
}

function ordersFor(profile) {
  if (Array.isArray(profile?.orders) && profile.orders.length) return profile.orders.map(Number);
  if (profile?.order !== undefined && profile?.order !== null) return [Number(profile.order)];
  const fromIndex = String(profile?.index ?? "").replace(/^override:/, "");
  return fromIndex && Number.isFinite(Number(fromIndex)) ? [Number(fromIndex)] : [];
}

function baseProfileKey(profile) {
  return `base:${profile?.symbol || profile?.name || profile?.index}`;
}

function overrideProfileKey(profile) {
  const named = String(profile?.customName || "").trim();
  if (named) return `override:name:${named}`;
  const signature = ordersFor(profile).join(",") || profile?.symbol || profile?.index;
  return `override:profile:${signature}`;
}

function profileKey(profile) {
  return profile?.draftId ? `draft:${profile.draftId}` : (isOverrideProfile(profile) ? overrideProfileKey(profile) : baseProfileKey(profile));
}

function normalizeData(input) {
  const data = input && typeof input === "object" ? input : {};
  return {
    fields: [],
    overrideFieldKeys: [],
    numericProfileFieldKeys: [],
    relativeOverrideFieldKeys: [],
    numericOverrideOperatorFieldKeys: [],
    boundedOverrideOperatorFieldKeys: [],
    numericOverrideOperandMaximums: {},
    numericOverrideOperandMinimums: {},
    relativeOverrideDeltaRange: { min: -127, max: 127 },
    editOptions: {},
    labels: {},
    classes: [],
    assignments: [],
    speciesOptions: [],
    typeOptions: [],
    conditionalStates: [],
    defaultClassIndex: 0,
    profilesAvailable: true,
    profileError: null,
    ...data,
  };
}

function mapOfMaps() {
  return new Map();
}

function newDraftStore() {
  return {
    version: 2,
    baseFields: mapOfMaps(),
    overrideFields: mapOfMaps(),
    memberships: new Map(),
    overrideNames: new Map(),
    overrideTargets: new Map(),
    conditionalStates: null,
    removedOverrides: new Set(),
    newOverrides: [],
    overrideOrder: [],
  };
}

function draftEntryList(value, label) {
  if (!Array.isArray(value)) throw new TypeError(`${label} must be an array.`);
  const keys = new Set();
  return value.map((entry) => {
    if (!Array.isArray(entry) || entry.length !== 2 || typeof entry[0] !== "string") {
      throw new TypeError(`${label} contains an invalid entry.`);
    }
    if (keys.has(entry[0])) throw new TypeError(`${label} contains a duplicate key.`);
    keys.add(entry[0]);
    return entry;
  });
}

function cloneDraftJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function cloneRawMatch(match) {
  const result = { ...DEFAULT_MATCH };
  for (const [field] of MATCH_FIELDS) result[field] = valueRaw(match?.[field]) || result[field];
  return result;
}

function cloneTarget(target = {}) {
  return {
    members: unique((target.members || []).map((member) => valueRaw(member?.symbol || member)).filter(Boolean)),
    match: cloneRawMatch(target.match),
    targetMode: ["disabled", "members", "all"].includes(target.targetMode) ? target.targetMode : "disabled",
  };
}

function createDraftId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

/**
 * Create the standalone profiles workspace.
 *
 * `api` may be a function or expose request/fetch/get/post methods. All source
 * access remains behind that injected boundary; this module never calls the
 * global fetch implementation directly.
 */
export function createProfilesController({
  state = {},
  api,
  elements = {},
  setStatus = () => {},
  markDirty = () => {},
  confirmAction,
  reportSelection = () => {},
  openPokemonRecord = () => false,
} = {}) {
  const root = elements.profilesView || elements.root || elements.container || elements.profiles;
  if (!(root instanceof Element)) throw new TypeError("createProfilesController requires elements.profilesView");
  if (!api) throw new TypeError("createProfilesController requires an injected api");

  let data = normalizeData(state.profileData || state.data || state.appData);
  const drafts = state.profileDrafts?.version === 2 ? state.profileDrafts : newDraftStore();
  if (!("conditionalStates" in drafts)) drafts.conditionalStates = null;
  state.profileDrafts = drafts;
  const invalidNumericOperatorInputs = new Set();
  let formulaRefreshTimer = null;
  const legacyLifecycleSections = state.profileLifecycleSections instanceof Map
    ? state.profileLifecycleSections
    : null;
  const legacyBranchTabs = state.profileBranchTabs instanceof Map
    ? state.profileBranchTabs
    : null;
  const initialProfileKey = String(state.selectedProfileKey || "");
  state.profileLifecycleSection = String(
    state.profileLifecycleSection || legacyLifecycleSections?.get(initialProfileKey) || "",
  );
  const branchTabSelections = state.profileModeTabs instanceof Map
    ? state.profileModeTabs
    : new Map(legacyBranchTabs?.get(initialProfileKey) || []);
  state.profileModeTabs = branchTabSelections;
  delete state.profileConditionalStateDrafts;
  delete state.profileLifecycleSections;
  delete state.profileBranchTabs;

  const ui = {
    search: "",
    kind: "all",
    selectedKey: state.selectedProfileKey || "",
    openSections: new Set(["identity"]),
    context: {
      species: "",
      terrain: "",
      level: "20",
      shiny: false,
    },
    contextResult: null,
    contextError: "",
    contextBusy: false,
    targetKind: "pokemon",
    targetValue: "",
    memberQuery: "",
    draggedKey: "",
    selectionHint: "",
    pendingLifecycleProfiles: [],
    resolverReturnFocus: null,
    busy: false,
    destroyed: false,
  };
  let contextAbortController = null;
  let dialogSubmit = null;

  const listElement = elements.profileLibrary;
  const editorElement = elements.profileInspector;
  const contextElement = elements.profileResolution;
  const workbenchElement = elements.profileWorkbench;
  const resolverDrawerElement = elements.profileResolverDrawer;
  const resolverOpenElement = elements.openProfileResolver;
  if (![listElement, editorElement, contextElement, workbenchElement, resolverDrawerElement, resolverOpenElement].every((element) => element instanceof Element)) {
    throw new TypeError("Profile controller requires its library, inspector, workbench, and resolver elements");
  }
  root.classList.add("profile-controller-ready", "pv2");
  listElement.classList.add("pv2-profile-list");
  editorElement.classList.add("pv2-editor");
  contextElement.classList.add("pv2-context");
  elements.resolveContext.dataset.action = "resolve-context";
  const announcerElement = document.createElement("p");
  announcerElement.className = "sr-only profile-position-announcer";
  announcerElement.setAttribute("aria-live", "polite");
  announcerElement.setAttribute("aria-atomic", "true");
  root.append(announcerElement);
  const dialogElement = document.createElement("dialog");
  dialogElement.className = "profile-dialog pv2-dialog";
  dialogElement.dataset.profileDialog = "";
  root.append(dialogElement);

  function status(message, kind = "info") {
    setStatus(String(message || ""), kind);
  }

  function announce(message) {
    announcerElement.textContent = "";
    requestAnimationFrame(() => { announcerElement.textContent = String(message || ""); });
  }

  async function requestJson(path, options = {}) {
    const method = String(options.method || "GET").toUpperCase();
    let result;
    if (typeof api === "function") {
      result = await api(path, options);
    } else if (typeof api.request === "function") {
      result = await api.request(path, options);
    } else if (typeof api.fetch === "function") {
      result = await api.fetch(path, options);
    } else if (method === "GET" && typeof api.get === "function") {
      result = await api.get(path, options);
    } else if (method === "POST" && typeof api.post === "function") {
      const payload = typeof options.body === "string" ? JSON.parse(options.body || "{}") : options.body;
      result = await api.post(path, payload, options);
    } else {
      throw new TypeError(`Injected api cannot ${method} ${path}`);
    }

    if (result instanceof Response) {
      const body = await result.json();
      if (!result.ok) throw new Error(body?.error || `HTTP ${result.status}`);
      return body;
    }
    if (result?.ok === false && result?.error) throw new Error(result.error);
    return result?.data !== undefined && result?.response !== undefined ? result.data : result;
  }

  function apiGet(path, options = {}) {
    return requestJson(path, { ...options, method: "GET" });
  }

  function apiPost(path, payload, options = {}) {
    return requestJson(path, {
      ...options,
      method: "POST",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      body: JSON.stringify(payload),
    });
  }

  function baseProfiles() {
    return data.classes.filter((profile) => !isOverrideProfile(profile));
  }

  function savedOverrideProfiles() {
    return data.classes.filter(isOverrideProfile);
  }

  function newOverrideProfiles() {
    return drafts.newOverrides.map((draft) => ({
      ...draft,
      index: `draft:${draft.draftId}`,
      kind: "override",
      isOverrideProfile: true,
      symbol: `DRAFT_OVERRIDE_${draft.draftId}`,
      orders: [],
      profile: Object.fromEntries(Object.entries(draft.fields).map(([field, raw]) => [field, { raw }])),
      editProfile: Object.fromEntries(Object.entries(draft.fields).map(([field, raw]) => [field, { raw }])),
      target: cloneTarget(draft.target),
      memberSymbols: [...draft.target.members],
      members: speciesEntries().filter((species) => draft.target.members.includes(species.symbol)),
      speciesCount: draft.target.targetMode === "members" ? draft.target.members.length : 0,
    }));
  }

  function orderedSavedOverrides() {
    const saved = savedOverrideProfiles();
    if (!drafts.overrideOrder.length) return saved;
    const byKey = new Map(saved.map((profile) => [profileKey(profile), profile]));
    const ordered = drafts.overrideOrder.map((key) => byKey.get(key)).filter(Boolean);
    for (const profile of saved) if (!ordered.includes(profile)) ordered.push(profile);
    return ordered;
  }

  function overrideProfiles() {
    return [...orderedSavedOverrides(), ...newOverrideProfiles()];
  }

  function allProfiles() {
    return [...baseProfiles(), ...overrideProfiles()];
  }

  function stateReferenceProfiles() {
    return orderedSavedOverrides().filter((profile) => (
      !drafts.removedOverrides.has(profileKey(profile)) && ordersFor(profile).length
    ));
  }

  function stateReferenceRaw(profile) {
    const order = ordersFor(profile)[0];
    return Number.isFinite(order) ? String(order - 1) : "";
  }

  function stateReferenceProfile(raw) {
    if (String(raw ?? "").trim() === "") return null;
    const expected = Number(raw);
    if (!Number.isFinite(expected)) return null;
    return stateReferenceProfiles().find((profile) => ordersFor(profile).includes(expected + 1)) || null;
  }

  function laneReferenceProfiles() {
    return stateReferenceProfiles();
  }

  function laneReferenceProfile(raw) {
    if (String(raw ?? "").trim() === "") return null;
    const expected = Number(raw);
    if (!Number.isFinite(expected)) return null;
    return laneReferenceProfiles().find((profile) => ordersFor(profile).includes(expected + 1)) || null;
  }

  function normalConditionalProfile(profile) {
    return isOverrideProfile(profile)
      && !profile?.draftId
      && !drafts.removedOverrides.has(profileKey(profile));
  }

  function conditionalProfileCandidates(parentProfile) {
    return savedOverrideProfiles().filter((candidate) => (
      normalConditionalProfile(candidate) && profileKey(candidate) !== profileKey(parentProfile)
    ));
  }

  function conditionStorageNumber(raw) {
    const value = valueRaw(raw).trim();
    if (value === CONDITION_ON_ROOFTOP || value === LEGACY_CONDITION_ON_ROOFTOP) {
      return CONDITION_ON_ROOFTOP_BIT;
    }
    const numeric = Number(value);
    return Number.isInteger(numeric) && numeric >= 0 ? numeric : null;
  }

  function conditionBits(raw) {
    return conditionStorageNumber(raw) ?? 0;
  }

  function conditionalProfileIsNone(raw) {
    const value = valueRaw(raw).trim();
    return !value || value === CONDITIONAL_PROFILE_NONE || Number(value) === CONDITIONAL_PROFILE_NONE_VALUE;
  }

  function conditionalProfileForRaw(raw) {
    if (conditionalProfileIsNone(raw)) return null;
    const expected = Number(valueRaw(raw));
    if (!Number.isFinite(expected)) return null;
    return savedOverrideProfiles().find((profile) => ordersFor(profile).includes(expected + 1)) || null;
  }

  function conditionalMovementSpeed(raw) {
    const numeric = Number(valueRaw(raw));
    return Number.isInteger(numeric) && numeric >= 0 && numeric <= CONDITIONAL_MOVEMENT_SPEED_MAX ? numeric : 0;
  }

  function conditionalStateKey(terrainMaskOrEntry, terrainOverrideMask, minMovementSpeed, maxMovementSpeed) {
    const entry = terrainMaskOrEntry && typeof terrainMaskOrEntry === "object"
      ? terrainMaskOrEntry
      : { terrainMask: terrainMaskOrEntry, terrainOverrideMask, minMovementSpeed, maxMovementSpeed };
    const explicit = terrainPolicyMaskNumber(entry.terrainOverrideMask);
    const accepted = terrainPolicyMaskNumber(entry.terrainMask) & explicit;
    return `${accepted}:${explicit}:${conditionalMovementSpeed(entry.minMovementSpeed)}:${conditionalMovementSpeed(entry.maxMovementSpeed)}`;
  }

  function cloneConditionalState(entry = {}) {
    let explicit = terrainPolicyMaskNumber(entry.terrainOverrideMask);
    let accepted = terrainPolicyMaskNumber(entry.terrainMask) & explicit;
    if ((entry.terrainMask === undefined || entry.terrainMask === null)
        && (entry.terrainOverrideMask === undefined || entry.terrainOverrideMask === null)) {
      const legacyMask = conditionBits(entry.conditionMask) & 0xFF;
      if (legacyMask & CONDITION_ON_ROOFTOP_BIT) {
        explicit = CONDITIONAL_DEFAULT_TERRAIN_BITS;
        accepted = conditionBits(entry.conditionValue) & CONDITION_ON_ROOFTOP_BIT
          ? CONDITIONAL_DEFAULT_TERRAIN_BITS
          : 0;
      }
    }
    return {
      parentKey: String(entry.parentKey || ""),
      overrideKey: entry.overrideKey ? String(entry.overrideKey) : null,
      terrainMask: String(accepted),
      terrainOverrideMask: String(explicit),
      minMovementSpeed: String(conditionalMovementSpeed(entry.minMovementSpeed)),
      maxMovementSpeed: String(conditionalMovementSpeed(entry.maxMovementSpeed)),
    };
  }

  function sourceConditionalStates() {
    return (Array.isArray(data.conditionalStates) ? data.conditionalStates : []).map((entry) => {
      const parent = conditionalProfileForRaw(entry?.parentProfile);
      const linked = conditionalProfileForRaw(entry?.referencedProfile ?? entry?.overrideProfile);
      return cloneConditionalState({
        parentKey: parent ? profileKey(parent) : "",
        overrideKey: linked ? profileKey(linked) : null,
        terrainMask: entry?.terrainMask,
        terrainOverrideMask: entry?.terrainOverrideMask,
        minMovementSpeed: entry?.minMovementSpeed,
        maxMovementSpeed: entry?.maxMovementSpeed,
        conditionMask: entry?.conditionMask,
        conditionValue: entry?.conditionValue,
      });
    }).filter((entry) => entry.parentKey);
  }

  function currentConditionalStates() {
    return (drafts.conditionalStates === null ? sourceConditionalStates() : drafts.conditionalStates)
      .map(cloneConditionalState);
  }

  function conditionalStatesEqual(left, right) {
    return JSON.stringify(left.map(cloneConditionalState)) === JSON.stringify(right.map(cloneConditionalState));
  }

  function setConditionalStates(entries) {
    const normalized = entries.map(cloneConditionalState);
    drafts.conditionalStates = conditionalStatesEqual(normalized, sourceConditionalStates()) ? null : normalized;
  }

  function updateConditionalState(parentKey, stateKey, updater) {
    let updated = null;
    const next = currentConditionalStates().map((entry) => {
      if (entry.parentKey !== parentKey || conditionalStateKey(entry) !== stateKey) return entry;
      updated = cloneConditionalState(updater(cloneConditionalState(entry)));
      return updated;
    });
    if (!updated) return null;
    const duplicate = next.some((entry) => entry !== updated
      && entry.parentKey === parentKey
      && conditionalStateKey(entry) === conditionalStateKey(updated));
    if (duplicate) return false;
    setConditionalStates(next);
    return updated;
  }

  function conditionalStatesFor(profile) {
    const parentKey = profileKey(profile);
    return currentConditionalStates()
      .filter((entry) => entry.parentKey === parentKey)
      .map((entry) => ({
        ...entry,
        linkedConditionalProfile: entry.overrideKey ? findProfile(entry.overrideKey) : null,
      }));
  }

  function conditionalStatesChangedFor(profile) {
    if (drafts.conditionalStates === null) return false;
    const parentKey = profileKey(profile);
    const forParent = (entries) => entries.filter((entry) => entry.parentKey === parentKey).map(cloneConditionalState);
    return !conditionalStatesEqual(forParent(currentConditionalStates()), forParent(sourceConditionalStates()));
  }

  function conditionalLifecycleBaseId(entry) {
    return `${CONDITIONAL_LIFECYCLE_SECTION_PREFIX}${conditionalStateKey(entry).replaceAll(":", "-")}`;
  }

  function findProfile(key = ui.selectedKey) {
    return allProfiles().find((profile) => profileKey(profile) === key) || null;
  }

  function backingNewOverride(profile) {
    if (!profile?.draftId) return null;
    return drafts.newOverrides.find((draft) => draft.draftId === profile.draftId) || null;
  }

  function nameFor(profile) {
    if (!profile) return "";
    if (profile.draftId) return profile.name;
    return drafts.overrideNames.get(profileKey(profile)) ?? profile.name ?? profile.symbol ?? "Profile";
  }

  function overrideNameAvailable(name, excludedProfile = null) {
    const normalized = String(name || "").trim().toLowerCase();
    if (!normalized) return false;
    const excludedKey = excludedProfile ? profileKey(excludedProfile) : "";
    return !overrideProfiles().some((profile) => profile !== excludedProfile
      && (!excludedKey || profileKey(profile) !== excludedKey)
      && nameFor(profile).trim().toLowerCase() === normalized
      && !drafts.removedOverrides.has(profileKey(profile)));
  }

  function uniqueOverrideName(preferred) {
    const base = String(preferred || "New override profile").trim() || "New override profile";
    if (overrideNameAvailable(base)) return base;
    let suffix = 2;
    while (!overrideNameAvailable(`${base} ${suffix}`)) suffix += 1;
    return `${base} ${suffix}`;
  }

  function rawFieldMap(profile) {
    const result = {};
    for (const field of data.fields) {
      const raw = valueRaw(profile?.editProfile?.[field.key] ?? profile?.profile?.[field.key]);
      if (raw) result[field.key] = raw;
    }
    return result;
  }

  function fieldDraftMap(profile, create = false) {
    const store = isOverrideProfile(profile) ? drafts.overrideFields : drafts.baseFields;
    const key = profileKey(profile);
    if (!store.has(key) && create) store.set(key, new Map());
    return store.get(key) || null;
  }

  function fieldRaw(profile, fieldKey) {
    if (profile?.draftId) return String(profile.fields?.[fieldKey] ?? "");
    const pending = fieldDraftMap(profile);
    if (pending?.has(fieldKey)) return pending.get(fieldKey);
    return valueRaw(profile?.editProfile?.[fieldKey] ?? profile?.profile?.[fieldKey]);
  }

  function originalFieldRaw(profile, fieldKey) {
    return valueRaw(profile?.editProfile?.[fieldKey] ?? profile?.profile?.[fieldKey]);
  }

  function setField(profile, fieldKey, raw) {
    const next = String(raw ?? "");
    if (profile.draftId) {
      const draft = backingNewOverride(profile);
      const fields = draft?.fields || profile.fields;
      if (next) fields[fieldKey] = next;
      else delete fields[fieldKey];
      profile.fields = fields;
      return;
    }
    const map = fieldDraftMap(profile, true);
    if (next === originalFieldRaw(profile, fieldKey)) map.delete(fieldKey);
    else map.set(fieldKey, next);
    if (!map.size) (isOverrideProfile(profile) ? drafts.overrideFields : drafts.baseFields).delete(profileKey(profile));
  }

  function sourceTarget(profile) {
    if (profile?.draftId) return cloneTarget(profile.target);
    const modeValue = Number(profile?.targetMode?.value);
    const modeRaw = valueRaw(profile?.targetMode);
    const targetMode = modeValue === 1 || modeRaw.includes("MEMBERS")
      ? "members"
      : (modeValue === 2 || modeRaw.includes("ALL") ? "all" : "disabled");
    return cloneTarget({
      members: profile?.memberSymbols || (profile?.members || []).map((member) => member.symbol),
      match: profile?.match,
      targetMode,
    });
  }

  function targetFor(profile) {
    if (profile?.draftId) return cloneTarget(profile.target);
    return cloneTarget(drafts.overrideTargets.get(profileKey(profile)) || sourceTarget(profile));
  }

  function setTarget(profile, target) {
    const normalized = cloneTarget(target);
    normalized.match.species = DEFAULT_MATCH.species;
    if (normalized.targetMode === "members" && !normalized.members.length) normalized.targetMode = "disabled";
    if (profile.draftId) {
      const draft = backingNewOverride(profile);
      if (draft) draft.target = cloneTarget(normalized);
      profile.target = normalized;
      return;
    }
    const saved = sourceTarget(profile);
    if (JSON.stringify(normalized) === JSON.stringify(saved)) drafts.overrideTargets.delete(profileKey(profile));
    else drafts.overrideTargets.set(profileKey(profile), normalized);
  }

  function baseByIndex(index) {
    return baseProfiles().find((profile) => String(profile.index) === String(index)) || null;
  }

  function originalBaseForSpecies(symbol) {
    const assignment = data.assignments.find((item) => item?.species?.symbol === symbol);
    return baseByIndex(assignment?.behaviorClass?.value);
  }

  function pendingBaseKeyForSpecies(symbol) {
    return drafts.memberships.get(symbol) || profileKey(originalBaseForSpecies(symbol));
  }

  function membersFor(profile) {
    const key = profileKey(profile);
    return data.assignments.filter((assignment) => pendingBaseKeyForSpecies(assignment?.species?.symbol) === key);
  }

  function setMembership(symbol, targetProfile) {
    const original = originalBaseForSpecies(symbol);
    const targetKey = profileKey(targetProfile);
    if (original && profileKey(original) === targetKey) drafts.memberships.delete(symbol);
    else drafts.memberships.set(symbol, targetKey);
  }

  function speciesEntries() {
    return data.assignments
      .map((assignment) => assignment?.species)
      .filter((species) => species?.symbol && species.symbol !== "SPECIES_NONE");
  }

  function compactLookup(value) {
    return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
  }

  function speciesForInput(value) {
    const needle = compactLookup(value);
    if (!needle) return null;
    const options = [...speciesEntries(), ...(data.speciesOptions || [])];
    return options.find((species) => unique([
      species.symbol,
      species.name,
      ...(species.aliases || []),
    ]).some((candidate) => compactLookup(candidate) === needle)) || null;
  }

  function typeGroupSymbol(typeSymbol) {
    return `OW_WILD_BEHAVIOR_GROUP_TYPE_${String(typeSymbol || "").replace(/^TYPE_/, "")}`;
  }

  function routeSpeciesForPool(pool) {
    if (!pool) return [];
    const liveSymbols = state.controllers?.routes?.speciesSymbolsForPool?.(pool.tableKeys, pool.swarmKeys);
    if (Array.isArray(liveSymbols)) {
      const symbols = new Set(liveSymbols);
      return speciesEntries().filter((species) => symbols.has(species.symbol));
    }
    const symbols = new Set();
    const add = (species, form = 0) => {
      const base = species?.baseSymbol || species?.symbol;
      const option = (data.speciesOptions || []).find((candidate) =>
        (candidate.baseSymbol || candidate.symbol) === base && Number(candidate.form || 0) === Number(form || 0));
      const symbol = option?.symbol || species?.symbol;
      if (symbol && symbol !== "SPECIES_NONE") symbols.add(symbol);
    };
    (data.routes || []).forEach((route) => {
      [...(route.pokemonTables || []), ...(route.slotTables || []), ...(route.headbuttTables || [])]
        .filter((table) => pool.tableKeys.includes(table.key))
        .forEach((table) => (table.slots || []).forEach((slot) => add(slot.species, slot.form)));
      (route.swarms || [])
        .filter((swarm) => pool.swarmKeys.includes(swarm.key))
        .forEach((swarm) => add(swarm.species, swarm.form));
    });
    return speciesEntries().filter((species) => symbols.has(species.symbol));
  }

  function familyEntries() {
    const byBase = new Map();
    speciesEntries().forEach((species) => {
      const base = species.familyBaseSymbol || species.symbol;
      if (!byBase.has(base)) byBase.set(base, []);
      byBase.get(base).push(species);
    });
    return [...byBase.entries()].map(([symbol, members]) => ({
      symbol,
      name: members.find((species) => species.symbol === symbol)?.name || members[0]?.familyBaseName || humanizeRaw(symbol),
      members,
    }));
  }

  function targetOptions(kind) {
    if (kind === "type") return (data.typeOptions || []).map((type) => ({ value: type.symbol, label: type.name }));
    if (kind === "spawnPool") return SPAWN_POOLS.map((pool) => ({ value: pool.raw, label: pool.label }));
    if (kind === "family") return familyEntries().map((family) => ({ value: family.symbol, label: `${family.name} family` }));
    return speciesEntries().map((species) => ({ value: species.symbol, label: species.name }));
  }

  function normalizedTargetValue(kind = ui.targetKind) {
    const options = targetOptions(kind);
    if (options.some((option) => option.value === ui.targetValue)) return ui.targetValue;
    return options[0]?.value || "";
  }

  function targetCandidates(kind = ui.targetKind, value = normalizedTargetValue(kind)) {
    if (kind === "type") {
      return speciesEntries().filter((species) => (species.types || []).some((type) => type.symbol === value));
    }
    if (kind === "spawnPool") {
      return routeSpeciesForPool(SPAWN_POOLS.find((pool) => pool.raw === value));
    }
    if (kind === "family") {
      return familyEntries().find((family) => family.symbol === value)?.members || [];
    }
    const species = speciesEntries().find((entry) => entry.symbol === value);
    return species ? [species] : [];
  }

  function matchCanTargetAssignment(match, assignment) {
    if (!match) return false;
    const pendingBase = findProfile(pendingBaseKeyForSpecies(assignment.species?.symbol));
    const baseSymbol = pendingBase?.symbol || assignment.behaviorClass?.symbol;
    if (match.behaviorClass !== DEFAULT_MATCH.behaviorClass && match.behaviorClass !== baseSymbol) return false;
    if (match.groupMask && match.groupMask !== DEFAULT_MATCH.groupMask && match.groupMask !== "OW_WILD_BEHAVIOR_GROUP_NONE") {
      const dynamicType = (data.typeOptions || []).find((type) => typeGroupSymbol(type.symbol) === match.groupMask);
      if (dynamicType) {
        if (!(assignment.species?.types || []).some((type) => type.symbol === dynamicType.symbol)) return false;
        return true;
      }
      const group = (data.groups || []).find((entry) => entry.group?.symbol === match.groupMask);
      if (!group?.species?.some((species) => species.symbol === assignment.species?.symbol)) return false;
    }
    return true;
  }

  function potentialAssignmentsFor(profile) {
    if (!isOverrideProfile(profile)) return [];
    const target = targetFor(profile);
    if (target.targetMode === "disabled") return [];
    const memberSet = new Set(target.members);
    return data.assignments.filter((assignment) =>
      (target.targetMode === "all" || memberSet.has(assignment.species?.symbol))
      && matchCanTargetAssignment(target.match, assignment));
  }

  function matchingContextFor(profile, assignment) {
    const target = targetFor(profile);
    const match = target.match;
    if (target.targetMode === "disabled" || !matchCanTargetAssignment(match, assignment)) return null;
    const currentLevel = Number(ui.context.level || 1);
    const minimum = match.minLevel === DEFAULT_MATCH.minLevel ? 1 : Number(match.minLevel);
    const maximum = match.maxLevel === DEFAULT_MATCH.maxLevel ? 100 : Number(match.maxLevel);
    return {
      species: assignment.species?.symbol,
      terrain: match.terrain === DEFAULT_MATCH.terrain ? ui.context.terrain : match.terrain,
      level: String(Math.min(maximum, Math.max(minimum, currentLevel))),
      shiny: match.shiny === DEFAULT_MATCH.shiny ? ui.context.shiny : String(match.shiny) === "1",
    };
  }

  function savedOrderKeys() {
    return savedOverrideProfiles().map(profileKey);
  }

  function currentOrderKeys() {
    return orderedSavedOverrides().map(profileKey);
  }

  function orderChanged() {
    return JSON.stringify(currentOrderKeys()) !== JSON.stringify(savedOrderKeys());
  }

  function hasChanges() {
    return Boolean(
      drafts.baseFields.size
      || drafts.overrideFields.size
      || drafts.memberships.size
      || drafts.overrideNames.size
      || drafts.overrideTargets.size
      || drafts.conditionalStates !== null
      || drafts.removedOverrides.size
      || drafts.newOverrides.length
      || orderChanged()
    );
  }

  function changeCount() {
    const nestedSize = (store) => [...store.values()].reduce((total, fields) => total + fields.size, 0);
    return nestedSize(drafts.baseFields)
      + nestedSize(drafts.overrideFields)
      + drafts.memberships.size
      + drafts.overrideNames.size
      + drafts.overrideTargets.size
      + (drafts.conditionalStates === null ? 0 : 1)
      + drafts.removedOverrides.size
      + drafts.newOverrides.length
      + (orderChanged() ? 1 : 0);
  }

  function signalDirty() {
    const dirty = hasChanges();
    state.profileDirty = dirty;
    state.selectedProfileKey = ui.selectedKey;
    markDirty();
  }

  function fieldLabel(fieldKey) {
    return data.fields.find((field) => field.key === fieldKey)?.label || humanizeRaw(fieldKey);
  }

  function runtimeMatchRelation(priorMatch, currentMatch) {
    const prior = cloneRawMatch(priorMatch);
    const current = cloneRawMatch(currentMatch);
    const exactDimensionRelation = (priorValue, currentValue, wildcard) => {
      const priorAny = priorValue === wildcard;
      const currentAny = currentValue === wildcard;
      if (!priorAny && !currentAny && priorValue !== currentValue) return "disjoint";
      if (priorAny || (!currentAny && priorValue === currentValue)) return "covers-current";
      return "partial";
    };
    const terrainRelation = exactDimensionRelation(
      prior.terrain,
      current.terrain,
      DEFAULT_MATCH.terrain,
    );
    const shinyRelation = exactDimensionRelation(
      prior.shiny,
      current.shiny,
      DEFAULT_MATCH.shiny,
    );
    if (terrainRelation === "disjoint" || shinyRelation === "disjoint") return "disjoint";

    const levelRange = (match) => {
      const minimum = match.minLevel === DEFAULT_MATCH.minLevel ? 1 : Number(match.minLevel);
      const maximum = match.maxLevel === DEFAULT_MATCH.maxLevel ? 100 : Number(match.maxLevel);
      return [Number.isFinite(minimum) ? minimum : 1, Number.isFinite(maximum) ? maximum : 100];
    };
    const [priorMin, priorMax] = levelRange(prior);
    const [currentMin, currentMax] = levelRange(current);
    if (priorMax < currentMin || priorMin > currentMax) return "disjoint";
    return terrainRelation === "covers-current"
      && shinyRelation === "covers-current"
      && priorMin <= currentMin
      && priorMax >= currentMax
      ? "covers-current"
      : "partial";
  }

  function effectiveFieldCandidates(profile, fieldKey) {
    const ownValue = fieldRaw(profile, fieldKey);
    if (ownValue || !isOverrideProfile(profile)) return ownValue ? [ownValue] : [];

    const ordered = overrideProfiles()
      .filter((candidate) => !drafts.removedOverrides.has(profileKey(candidate)));
    const currentIndex = ordered.findIndex((candidate) => profileKey(candidate) === profileKey(profile));
    const earlier = currentIndex < 0 ? [] : ordered.slice(0, currentIndex);
    const currentMatch = targetFor(profile).match;
    const earlierCoverage = earlier.map((candidate) => ({
      profile: candidate,
      species: new Set(potentialAssignmentsFor(candidate)
        .map((assignment) => assignment?.species?.symbol)
        .filter(Boolean)),
    }));
    const resolved = new Set();

    potentialAssignmentsFor(profile).forEach((assignment) => {
      const species = assignment?.species?.symbol;
      const base = findProfile(pendingBaseKeyForSpecies(species));
      let values = new Set([fieldRaw(base, fieldKey)].filter(Boolean));
      earlierCoverage.forEach((entry) => {
        if (!species || !entry.species.has(species)) return;
        const replacement = fieldRaw(entry.profile, fieldKey);
        if (!replacement) return;
        const relation = runtimeMatchRelation(targetFor(entry.profile).match, currentMatch);
        if (relation === "disjoint") return;
        if (relation === "covers-current") values = new Set([replacement]);
        else values.add(replacement);
      });
      values.forEach((value) => resolved.add(value));
    });
    return [...resolved];
  }

  function canUseRamLocomotion(profile) {
    return effectiveFieldCandidates(profile, "chillAction").includes(RAM_LOCOMOTION);
  }

  function fieldLabelForProfile(profile, fieldKey, context = {}) {
    if (context.label) return context.label;
    if (!['ramAccelerationSteps', 'ramMaxSpeed'].includes(fieldKey)) return fieldLabel(fieldKey);
    const parentRaw = context.parentField ? fieldRaw(profile, context.parentField) : "";
    const ambiguous = context.ambiguous || (isOverrideProfile(profile) && !parentRaw);
    const usesRam = context.parentField === "chillAction" && parentRaw === RAM_LOCOMOTION;
    if (fieldKey === "ramAccelerationSteps") {
      if (ambiguous) return "Chain moves / RAM steps";
      return usesRam ? "RAM acceleration steps" : "Chain moves";
    }
    if (ambiguous) return "Chain pause / RAM max";
    return usesRam ? "RAM max speed" : "Chain pause";
  }

  function fieldUnitForProfile(profile, fieldKey, context = {}) {
    if (context.unit !== undefined) return context.unit;
    if (!["ramAccelerationSteps", "ramMaxSpeed"].includes(fieldKey)) {
      return data.fields.find((field) => field.key === fieldKey)?.unit || "";
    }
    const parentRaw = context.parentField ? fieldRaw(profile, context.parentField) : "";
    const ambiguous = context.ambiguous || (isOverrideProfile(profile) && !parentRaw);
    const usesRam = context.parentField === "chillAction" && parentRaw === RAM_LOCOMOTION;
    if (fieldKey === "ramAccelerationSteps") {
      if (ambiguous) return "moves / steps";
      return usesRam ? "steps" : "moves";
    }
    if (ambiguous) return "frames / speed";
    return usesRam ? "speed" : "frames";
  }

  function fieldOptions(fieldKey, currentRaw = "", profile = null, context = {}) {
    let options = [...(data.editOptions?.[fieldKey] || [])];
    const optionRaws = new Set(options.map(valueRaw));
    (LINKED_CHILL_OPTION_SOURCES[fieldKey] || []).forEach((sourceField) => {
      (data.editOptions?.[sourceField] || []).forEach((option) => {
        const raw = valueRaw(option);
        if (!raw || optionRaws.has(raw)) return;
        optionRaws.add(raw);
        options.push(option);
      });
    });
    let usesRam = false;
    if (typeof context.ramMode === "boolean") usesRam = context.ramMode;
    else if (!context.ambiguous && profile && context.parentField) {
      usesRam = context.parentField === "chillAction" && fieldRaw(profile, context.parentField) === RAM_LOCOMOTION;
    } else if (!context.ambiguous && profile) {
      usesRam = canUseRamLocomotion(profile);
    }
    if (fieldKey === "ramMaxSpeed" && !usesRam) {
      for (let value = 0; value <= 255; value += 1) {
        const raw = String(value);
        if (!options.some((option) => valueRaw(option) === raw)) options.push({ raw, label: raw, value });
      }
    }
    if (context.chainRamDual && ["ramAccelerationSteps", "ramMaxSpeed"].includes(fieldKey)) {
      options = options.map((option) => {
        const raw = valueRaw(option);
        const numeric = Number(raw);
        if (!Number.isFinite(numeric)) return option;
        if (fieldKey === "ramAccelerationSteps") {
          return {
            ...option,
            label: numeric === 0
              ? "0 — disables Chain pauses and RAM acceleration"
              : `${raw} moves / steps`,
          };
        }
        if (numeric === 0) return { ...option, label: "0 — no Chain pause; RAM stays at starting speed" };
        if (numeric <= 4) return { ...option, label: `${raw} frame${numeric === 1 ? "" : "s"} / speed tier ${raw}` };
        return { ...option, label: `${raw} frames — RAM clamps to speed tier 4` };
      });
    }
    if (fieldKey === "ramMaxSpeed" && usesRam) {
      options = options
        .filter((option) => Number(valueRaw(option)) <= 4 || valueRaw(option) === currentRaw)
        .map((option) => Number(valueRaw(option)) > 4
          ? { ...option, label: `${valueRaw(option)} — RAM clamps to 4; Chain pause ${valueRaw(option)} frames` }
          : option);
    }
    if (currentRaw && !isNumericOverrideRaw(currentRaw) && !options.some((option) => valueRaw(option) === currentRaw)) {
      options.push({
        raw: currentRaw,
        label: fieldKey === "ramMaxSpeed" && usesRam && Number(currentRaw) > 4
          ? `${currentRaw} — RAM clamps to 4; Chain pause ${currentRaw} frames`
          : humanizeRaw(currentRaw),
      });
    }
    return options;
  }

  function isRelativeOverrideRaw(raw) {
    return /^[+-]\d+$/.test(String(raw || ""));
  }

  function parseNumericOverrideRaw(raw) {
    const value = String(raw || "").trim();
    const compound = value.match(/^([+-]\d+)\s*,\s*\/([<>])(\d+)$/);
    if (compound) {
      const adjust = { kind: "adjust", operand: Number(compound[1]) };
      const bound = { kind: compound[2] === "<" ? "atLeast" : "atMost", operand: Number(compound[3]) };
      return { kind: "compound", operations: [adjust, bound], adjust, bound };
    }
    if (isRelativeOverrideRaw(value)) {
      const operation = { kind: "adjust", operand: Number(value) };
      return { ...operation, operations: [operation] };
    }
    const bound = value.match(/^\/([<>])(\d+)$/);
    if (!bound) return null;
    const operation = { kind: bound[1] === "<" ? "atLeast" : "atMost", operand: Number(bound[2]) };
    return { ...operation, operations: [operation] };
  }

  function isNumericOverrideRaw(raw) {
    return Boolean(parseNumericOverrideRaw(raw));
  }

  function numericOperatorStateLabel(raw, changed) {
    const operator = parseNumericOverrideRaw(raw);
    if (!operator) return "";
    if (operator.kind === "compound") {
      const direction = operator.bound.kind === "atLeast" ? "no less than" : "no greater than";
      return `${changed ? "Edited compound formula" : "Adjusts the earlier stored value"} by ${operator.adjust.operand > 0 ? "+" : ""}${operator.adjust.operand}, then limits it to ${direction} ${operator.bound.operand}`;
    }
    if (operator.kind === "adjust") {
      return `${changed ? "Edited adjustment" : "Adjusts earlier stored value"} by ${raw}; the stored result is clamped to this field's valid range`;
    }
    if (operator.kind === "atLeast") {
      return `${changed ? "Edited minimum" : "Raises the earlier stored value"} to no less than ${operator.operand}`;
    }
    return `${changed ? "Edited maximum" : "Lowers the earlier stored value"} to no greater than ${operator.operand}`;
  }

  function numericOperatorVisibleNote(raw) {
    const operator = parseNumericOverrideRaw(raw);
    if (!operator) return "";
    if (operator.kind === "compound") {
      const bound = operator.bound.kind === "atLeast"
        ? `at least ${operator.bound.operand} (/<${operator.bound.operand})`
        : `at most ${operator.bound.operand} (/>${operator.bound.operand})`;
      return `adjust ${operator.adjust.operand > 0 ? "+" : ""}${operator.adjust.operand}, then ${bound}`;
    }
    if (operator.kind === "adjust") return `adjust ${raw}`;
    return operator.kind === "atLeast"
      ? `at least ${operator.operand} (/<${operator.operand})`
      : `at most ${operator.operand} (/>${operator.operand})`;
  }

  function numericOverridePermissions(profile, fieldKey) {
    const numericFields = data.numericProfileFieldKeys?.length
      ? data.numericProfileFieldKeys
      : (data.numericOverrideOperatorFieldKeys?.length
        ? data.numericOverrideOperatorFieldKeys
        : data.relativeOverrideFieldKeys);
    const boundedFields = data.boundedOverrideOperatorFieldKeys || [];
    const profileAllows = isOverrideProfile(profile)
      && profile?.numericOverrideOperatorsAllowed !== false
      && profile?.relativeOverridesAllowed !== false;
    return {
      adjust: profileAllows && numericFields.includes(fieldKey),
      bounds: profileAllows && boundedFields.includes(fieldKey),
    };
  }

  function isNumericProfileField(fieldKey) {
    const numericFields = data.numericProfileFieldKeys?.length
      ? data.numericProfileFieldKeys
      : data.numericOverrideOperatorFieldKeys;
    return numericFields.includes(fieldKey);
  }

  function numericOverrideAllowed(profile, fieldKey, kind = null, permissions = null) {
    const resolvedPermissions = permissions || numericOverridePermissions(profile, fieldKey);
    if (kind === "adjust") return resolvedPermissions.adjust;
    if (kind === "atLeast" || kind === "atMost") return resolvedPermissions.bounds;
    if (kind === "compound") return resolvedPermissions.adjust && resolvedPermissions.bounds;
    return resolvedPermissions.adjust || resolvedPermissions.bounds;
  }

  function numericInputProfile(input, fallbackProfile = null) {
    const owningKey = input?.dataset?.profileKey || "";
    return owningKey ? findProfile(owningKey) : fallbackProfile;
  }

  function controlProfile(control, fallbackProfile = null) {
    const owner = control?.closest?.("[data-profile-key]") || control;
    const owningKey = owner?.dataset?.profileKey || "";
    return owningKey ? findProfile(owningKey) : fallbackProfile;
  }

  function numericInputPermissions(input, profile, fieldKey) {
    if (input?.dataset?.numericAdjust !== undefined && input?.dataset?.numericBounds !== undefined) {
      return {
        adjust: input.dataset.numericAdjust === "true",
        bounds: input.dataset.numericBounds === "true",
      };
    }
    return numericOverridePermissions(profile, fieldKey);
  }

  function relativeFieldDeltaBounds() {
    return {
      min: Number(data.relativeOverrideDeltaRange?.min ?? -127),
      max: Number(data.relativeOverrideDeltaRange?.max ?? 127),
    };
  }

  function numericOverrideOperandBounds(fieldKey, options, kind) {
    if (kind === "adjust") return relativeFieldDeltaBounds();
    const optionMaximum = Math.max(0, ...options.map((option) => Number(valueRaw(option))).filter(Number.isFinite));
    const fieldMaximum = Number(data.numericOverrideOperandMaximums?.[fieldKey] ?? optionMaximum ?? 64);
    const minimum = Number(data.numericOverrideOperandMinimums?.[fieldKey] ?? 0);
    return { min: minimum, max: Math.min(fieldMaximum, optionMaximum || fieldMaximum) };
  }

  function renderProfileSelectOptions(options, selectedRaw, allowInherit = false) {
    const selected = String(selectedRaw || "");
    const renderOptions = (items) => items.map((option) => {
      const optionRaw = valueRaw(option);
      return `<option value="${escapeHtml(optionRaw)}" ${optionRaw === selected ? "selected" : ""}>${escapeHtml(valueLabel(option))}</option>`;
    }).join("");
    const inherit = allowInherit ? `<option value="" ${selected ? "" : "selected"}>Inherit</option>` : "";
    return `${inherit}${renderOptions(options)}`;
  }

  function renderProfileValueEditor(profile, fieldKey, options, selectedRaw, instance, label, descriptionId, allowInherit = isOverrideProfile(profile), attributes = "") {
    const permissions = numericOverridePermissions(profile, fieldKey);
    if (!isNumericProfileField(fieldKey)) {
      return `<select class="field-control" data-profile-value data-profile-key="${escapeHtml(profileKey(profile))}" data-field-key="${escapeHtml(fieldKey)}" data-field-instance="${escapeHtml(instance)}" ${attributes}>
        ${renderProfileSelectOptions(options, selectedRaw, allowInherit, permissions)}
      </select>`;
    }
    const listId = `pv2-numeric-options-${String(instance).replace(/[^a-zA-Z0-9_-]/g, "-")}`;
    const errorId = `pv2-numeric-error-${String(instance).replace(/[^a-zA-Z0-9_-]/g, "-")}`;
    const syntax = [permissions.adjust ? "+2 or -1" : "", permissions.bounds ? "/<2 or />2" : "", permissions.adjust && permissions.bounds ? "+1, /<2" : ""].filter(Boolean).join(", ");
    const title = syntax
      ? `Clear to inherit. Type an exact value, ${syntax}.`
      : (allowInherit
        ? "Clear to inherit, or type an exact whole-number value."
        : "Type an exact whole-number value.");
    return `<span class="pv2-numeric-combobox">
      <input class="field-control" type="text" inputmode="text" autocomplete="off" spellcheck="false" list="${escapeHtml(listId)}" value="${escapeHtml(selectedRaw)}" placeholder="${allowInherit ? "Inherit" : "Value"}" title="${escapeHtml(title)}" aria-errormessage="${escapeHtml(errorId)}" data-profile-value data-profile-numeric-entry data-profile-key="${escapeHtml(profileKey(profile))}" data-profile-allow-inherit="${allowInherit ? "true" : "false"}" data-numeric-adjust="${permissions.adjust ? "true" : "false"}" data-numeric-bounds="${permissions.bounds ? "true" : "false"}" data-field-key="${escapeHtml(fieldKey)}" data-field-instance="${escapeHtml(instance)}" ${attributes}>
      <datalist id="${escapeHtml(listId)}">
        ${allowInherit ? `<option value="Inherit"></option>` : ""}
        ${options.map((option) => `<option value="${escapeHtml(valueRaw(option))}" label="${escapeHtml(valueLabel(option))}"></option>`).join("")}
      </datalist>
      <small id="${escapeHtml(errorId)}" class="pv2-numeric-error" role="status" aria-live="polite"></small>
    </span>`;
  }

  function alertRangeBaseRaw(raw) {
    return String(raw || "").replace(/_CLOSE_RADIUS$/, "");
  }

  function alertRangeIsClose(raw) {
    return /_CLOSE_RADIUS$/.test(String(raw || ""));
  }

  function alertRangeTypeOptions() {
    const seen = new Map();
    (data.editOptions?.alertRange || []).forEach((option) => {
      const baseRaw = alertRangeBaseRaw(valueRaw(option));
      if (seen.has(baseRaw)) return;
      const baseOption = (data.editOptions?.alertRange || []).find((candidate) => valueRaw(candidate) === baseRaw) || option;
      const label = valueLabel(baseOption).replace(/\s*\+\s*close radius$/i, "");
      seen.set(baseRaw, { ...baseOption, raw: baseRaw, label });
    });
    return [...seen.values()];
  }

  function alertRangeSupportsClose(raw) {
    const baseRaw = alertRangeBaseRaw(raw);
    return (data.editOptions?.alertRange || []).some((option) => (
      alertRangeBaseRaw(valueRaw(option)) === baseRaw && alertRangeIsClose(valueRaw(option))
    ));
  }

  function alertRangeRawWithClose(raw, close) {
    const baseRaw = alertRangeBaseRaw(raw);
    const options = data.editOptions?.alertRange || [];
    if (!close) return valueRaw(options.find((option) => valueRaw(option) === baseRaw)) || baseRaw;
    return valueRaw(options.find((option) => (
      alertRangeBaseRaw(valueRaw(option)) === baseRaw && alertRangeIsClose(valueRaw(option))
    ))) || baseRaw;
  }

  function scopedActionOwns(scope, raw) {
    return scope === "alert" ? raw === ALERT_SPECIAL.call : raw === ALERT_SPECIAL.throw;
  }

  function scopedActionIsKnown(raw) {
    return ["", ALERT_SPECIAL.none, ALERT_SPECIAL.call, ALERT_SPECIAL.throw].includes(String(raw || ""));
  }

  function scopedActionRaw(scope, raw) {
    if (!raw) return "";
    if (!scopedActionIsKnown(raw)) return raw;
    return scopedActionOwns(scope, raw) ? raw : ALERT_SPECIAL.none;
  }

  function scopedActionCountRaw(scope, raw) {
    return raw === ALERT_SPECIAL.none || !scopedActionIsKnown(raw) || scopedActionOwns(scope, raw) ? raw : "";
  }

  function scopedActionClearRaw(scope, currentRaw, originalRaw) {
    if (currentRaw === ALERT_SPECIAL.none) return "";
    if (!scopedActionIsKnown(currentRaw)) return "";
    if (!scopedActionOwns(scope, currentRaw)) return currentRaw;
    const otherScope = scope === "alert" ? "active" : "alert";
    if (scopedActionOwns(otherScope, originalRaw) && !scopedActionOwns(scope, originalRaw)) return originalRaw;
    return "";
  }

  function activeActionShowsThrowRange(profile) {
    const raw = fieldRaw(profile, "alertSpecialAction");
    const displayRaw = scopedActionRaw("active", raw);
    return raw === ALERT_SPECIAL.throw || (isOverrideProfile(profile) && !displayRaw);
  }

  function profileSearchText(profile) {
    const assignments = isOverrideProfile(profile) ? potentialAssignmentsFor(profile) : membersFor(profile);
    const members = assignments.flatMap((item) => [
      item.species?.name,
      item.species?.symbol,
      item.species?.familyBaseName,
      ...(item.species?.types || []).flatMap((type) => [type.name, type.symbol]),
      ...(item.groups || []),
    ]);
    const targetValues = isOverrideProfile(profile) ? Object.values(targetFor(profile).match).map(humanizeRaw) : [];
    const fields = data.fields.flatMap((field) => [field.label, fieldRaw(profile, field.key), valueLabel(profile?.profile?.[field.key])]);
    const rules = (profile.classRules || []).flatMap((rule) => [rule.summary, rule.className]);
    const primitives = Object.values(profile.primitives || {}).flatMap((primitive) => [valueRaw(primitive), valueLabel(primitive)]);
    return [nameFor(profile), profile.symbol, profile.summary, ...members, ...targetValues, ...fields, ...rules, ...primitives]
      .filter(Boolean).join(" ").toLowerCase();
  }

  function visibleProfiles(profiles, kind) {
    const query = ui.search.trim().toLowerCase();
    if (ui.kind !== "all" && ui.kind !== kind) return [];
    return profiles.filter((profile) => !query || profileSearchText(profile).includes(query));
  }

  function filtered() {
    return Boolean(ui.search.trim() || ui.kind !== "all");
  }

  function profilePreviewSpecies(profile, override = false, limit = 20) {
    let candidates;
    if (override) {
      const target = targetFor(profile);
      if (target.targetMode === "disabled") {
        candidates = [];
      } else if (target.targetMode === "all") {
        candidates = potentialAssignmentsFor(profile).map((assignment) => assignment.species).filter(Boolean);
      } else {
        const bySymbol = new Map(speciesEntries().map((species) => [species.symbol, species]));
        candidates = target.members.map((symbol) => bySymbol.get(symbol)).filter(Boolean);
      }
    } else {
      candidates = membersFor(profile).map((assignment) => assignment.species).filter(Boolean);
    }
    return [...new Map(candidates.map((species) => [species.symbol, species])).values()]
      .filter((species) => species.iconUrl)
      .slice(0, limit);
  }

  function renderProfileRow(profile, index, total, override = false) {
    const key = profileKey(profile);
    const selected = key === ui.selectedKey;
    const removed = drafts.removedOverrides.has(key);
    const changed = profile.draftId
      || fieldDraftMap(profile)?.size
      || drafts.overrideNames.has(key)
      || drafts.overrideTargets.has(key)
      || conditionalStatesChangedFor(profile)
      || removed;
    const dragEnabled = override && !profile.draftId && !filtered() && !ui.busy;
    const orderControls = override
      ? `<span class="profile-row-drag-handle" role="button" tabindex="${dragEnabled ? "0" : "-1"}" draggable="${dragEnabled}" data-reorder-handle data-profile-key="${escapeHtml(key)}" aria-label="Reorder ${escapeHtml(nameFor(profile))}" title="${dragEnabled ? "Drag or use keyboard controls" : "Clear filters to reorder"}"><span class="profile-index" aria-hidden="true">${String(index + 1).padStart(2, "0")}</span><span class="pv2-drag-grip" aria-hidden="true">⋮⋮</span></span>`
      : "";
    const previewSpecies = profilePreviewSpecies(profile, override);
    const previewIcons = previewSpecies.length ? `
      <span class="pv2-profile-icons" aria-label="Open Pokémon records">
        ${previewSpecies.map((species) => `<button type="button" data-action="open-pokemon" data-species="${escapeHtml(species.symbol)}" aria-label="Open ${escapeHtml(species.name)} in Pokémon Editor"><img src="${escapeHtml(species.iconUrl)}" alt="" width="16" height="16" loading="lazy" decoding="async" draggable="false"></button>`).join("")}
      </span>` : "";
    return `
      <li class="profile-row pv2-profile-row${selected ? " is-active is-selected" : ""}${removed ? " is-removed" : ""}${changed ? " is-changed" : ""}${override ? " override-profile" : ""}" data-profile-row data-profile-key="${escapeHtml(key)}">
        ${orderControls}
        <button class="profile-select pv2-profile-select" type="button" data-action="select-profile" data-profile-key="${escapeHtml(key)}" aria-current="${selected ? "true" : "false"}">
          <span class="pv2-profile-heading">
            <span class="pv2-profile-copy">
              <strong>${escapeHtml(nameFor(profile))}</strong>
            </span>
          </span>
        </button>
        ${previewIcons}
        ${removed ? `<button type="button" data-action="delete-profile" data-profile-key="${escapeHtml(key)}">Undo removal</button>` : ""}
      </li>`;
  }

  function renderList() {
    const bases = visibleProfiles(baseProfiles(), "base");
    const overrides = visibleProfiles(overrideProfiles(), "override");
    const filterMessage = filtered() ? `<p class="order-help pv2-filter-note">Reordering is paused while the library is filtered.</p>` : `<p class="order-help">Drag the dotted grip; keyboard reordering is also supported. Later matching layers apply last.</p>`;
    listElement.innerHTML = `
      ${ui.kind !== "override" ? `
        <section class="profile-group profile-group--base pv2-library-group" data-profile-group="base" aria-labelledby="pv2-base-heading">
          <header><span><i aria-hidden="true">B</i><strong id="pv2-base-heading">Base profiles</strong></span><small>${bases.length}</small></header>
          <ul class="profile-list" data-profile-list="base">${bases.map((profile, index) => renderProfileRow(profile, index, bases.length)).join("") || `<li class="empty-state empty-state--small">No base profiles match this filter.</li>`}</ul>
        </section>` : ""}
      ${ui.kind !== "base" ? `
        <section class="profile-group profile-group--overrides pv2-library-group" data-profile-group="overrides" aria-labelledby="pv2-override-heading">
          <header><span><i aria-hidden="true">O</i><strong id="pv2-override-heading">Ordered overrides</strong></span><small>${overrides.length}</small></header>
          ${filterMessage}
          <ol class="profile-list override-deck" data-profile-list="overrides">${overrides.map((profile, index) => renderProfileRow(profile, index, overrides.length, true)).join("") || `<li class="empty-state empty-state--small">No override profiles match this filter.</li>`}</ol>
        </section>` : ""}
    `;
  }

  function profileCanEditField(profile, fieldKey) {
    const known = data.fields.some((field) => field.key === fieldKey);
    if (!known) return false;
    return !isOverrideProfile(profile) || new Set(data.overrideFieldKeys || []).has(fieldKey);
  }

  function explicitInactiveNode(profile, fieldKey, active, extra = {}) {
    if (active) return { field: fieldKey, ...extra };
    const pending = profile.draftId
      ? Object.prototype.hasOwnProperty.call(profile.fields || {}, fieldKey)
      : Boolean(fieldDraftMap(profile)?.has(fieldKey));
    if (pending || (isOverrideProfile(profile) && fieldRaw(profile, fieldKey))) {
      return { field: fieldKey, inactive: true, ...extra };
    }
    return null;
  }

  function behaviorBranch(profile, branch) {
    const definitions = {
      "chill-behavior": {
        parent: "chillState",
        target: "chillTarget",
        tiles: ["chillAllowedTerrainMask"],
      },
      "active-behavior": {
        parent: "attentiveState",
        target: "targetSelector",
        tiles: ["attentiveAllowedTile", "attentiveAllowedTile2"],
        chase: ["attentiveChaseBoostDistance", "attentiveChaseBoostSpeed"],
      },
      "tired-behavior": {
        parent: "tiredState",
        tiles: ["tiredAllowedTile", "tiredAllowedTile2"],
      },
    };
    const definition = definitions[branch];
    if (!definition) return { nodes: [], context: "" };
    const raw = fieldRaw(profile, definition.parent);
    const inherited = isOverrideProfile(profile) && !raw;
    const canTarget = inherited || TARGETABLE_BEHAVIORS.has(raw);
    const usesTiles = inherited || TILE_BEHAVIORS.has(raw);
    const nodes = [];
    if (definition.target) {
      const targetRaw = fieldRaw(profile, definition.target);
      const targetInherited = isOverrideProfile(profile) && !targetRaw;
      const targetChildren = [];
      if (definition.target === "targetSelector") {
        targetChildren.push(...["attentiveCircleRadius", "attentiveContinueWhenArrived"]
          .map((field) => explicitInactiveNode(profile, field, targetInherited || targetRaw === CIRCLE_PLAYER_TARGET))
          .filter(Boolean));
      }
      if (["targetSelector", "chillTarget"].includes(definition.target)) {
        const targetCandidates = targetInherited
          ? effectiveFieldCandidates(profile, definition.target)
          : [targetRaw];
        const usesPlayerAdjacentTarget = targetCandidates.includes(NEXT_TO_PLAYER_TARGET);
        const directions = explicitInactiveNode(
          profile,
          "playerAdjacentDirectionMasks",
          usesPlayerAdjacentTarget,
          {
            virtual: "player-adjacent-directions",
          },
        );
        if (directions) targetChildren.push(directions);
      }
      const targetNode = targetChildren.length && !canTarget
        ? { field: definition.target, inactive: true, children: targetChildren }
        : explicitInactiveNode(profile, definition.target, canTarget, { children: targetChildren });
      if (targetNode) {
        if (branch === "active-behavior") targetNode.composite = "active-target-tiles";
        nodes.push(targetNode);
      }
    }
    (definition.tiles || []).forEach((field) => {
      const node = explicitInactiveNode(profile, field, usesTiles, {
        composite: branch === "active-behavior" && definition.target ? "active-target-tiles" : "",
        virtual: field === "chillAllowedTerrainMask" ? "allowed-terrain-policy" : "",
      });
      if (node) nodes.push(node);
    });
    (definition.chase || []).forEach((field) => {
      const node = explicitInactiveNode(profile, field, canTarget, { composite: "active-chase-boost" });
      if (node) nodes.push(node);
    });
    const onlyInactive = nodes.length && nodes.every((node) => node.inactive);
    return {
      nodes,
      context: inherited
        ? "Available while behavior inherits."
        : (onlyInactive ? "Stored suboptions are inactive for the selected behavior." : (nodes.length ? "Options used by the selected behavior." : "This behavior has no additional options.")),
      inherited,
    };
  }

  function movementBranch(profile, parentField, scope, showInactiveUnset = false) {
    const fields = MOVEMENT_FIELDS[scope];
    if (!fields) return { nodes: [], context: "" };
    const raw = fieldRaw(profile, parentField);
    const inherited = isOverrideProfile(profile) && !raw;
    const inheritedMovementCandidates = inherited
      ? effectiveFieldCandidates(profile, parentField)
      : [];
    const inheritedHasRam = inheritedMovementCandidates.includes(LOCOMOTION.ram);
    const inheritedHasChain = inheritedMovementCandidates.some((candidate) => CHAIN_LOCOMOTIONS.has(candidate));
    const inheritedMovementRam = inheritedMovementCandidates.length > 0
      && inheritedMovementCandidates.every((candidate) => candidate === LOCOMOTION.ram);
    // An override with no current coverage has no inherited value to inspect.
    // Keep the shared controls available: membership may be enabled later, and
    // hiding them makes it impossible to prepare this layer beforehand.
    const inheritedMovementUnknown = inherited && inheritedMovementCandidates.length === 0;
    const inheritedMovementAmbiguous = inherited
      && (inheritedMovementUnknown || (inheritedHasRam && inheritedHasChain));
    const usesMovementSpeed = inherited
      ? inheritedMovementCandidates.some((candidate) => candidate === LOCOMOTION.wander || candidate === LOCOMOTION.ram)
      : raw === LOCOMOTION.wander || raw === LOCOMOTION.ram;
    const usesWalkAcceleration = inherited
      ? inheritedMovementCandidates.includes(LOCOMOTION.wander)
      : raw === LOCOMOTION.wander;
    const nodes = new Map();
    const ambiguous = inherited || !raw || raw === LOCOMOTION.none;
    const append = (fieldKeys, active, extra = {}) => {
      let appended = false;
      fieldKeys.forEach((field) => {
        const presentation = {
          parentField,
          ambiguous,
          ...extra,
          beforeLabel: appended ? "" : extra.beforeLabel,
        };
        const candidate = explicitInactiveNode(profile, field, active, presentation)
          || (showInactiveUnset && profileCanEditField(profile, field)
            ? { field, inactive: !active, ...presentation }
            : null);
        if (!candidate) return;
        appended = true;
        const existing = nodes.get(field);
        if (!existing || (existing.inactive && !candidate.inactive)) nodes.set(field, candidate);
      });
    };
    append([fields.speed], usesMovementSpeed, { label: "Movement speed" });
    if (fields.maxWalkSpeed) {
      append([fields.maxWalkSpeed], usesWalkAcceleration, {
        label: "Max speed",
        unit: "speed",
      });
    }
    if (fields.walkAcceleration) {
      append([fields.walkAcceleration], usesWalkAcceleration, {
        label: "Tiles to accelerate",
        unit: "tiles",
      });
    }
    const throwUsesStandaloneRange = scope === "active"
      && activeActionShowsThrowRange(profile)
      && !inherited
      && raw !== LOCOMOTION.hop;
    const hopPathFields = throwUsesStandaloneRange
      ? fields.hopPath.fields.filter((field) => field !== "attentiveHopMaxDistance")
      : fields.hopPath.fields;
    append(hopPathFields, inherited || raw === LOCOMOTION.hop, {
      beforeLabel: "Hop options",
      composite: fields.hopPath.composite,
    });
    append(fields.hopTiming.fields, inherited || raw === LOCOMOTION.hop, { composite: fields.hopTiming.composite });
    if (showInactiveUnset) {
      append(fields.chain, inherited || CHAIN_LOCOMOTIONS.has(raw) || raw === LOCOMOTION.ram, {
        composite: "movement-chain-or-ram",
        chainRamDual: true,
        ramMode: raw === LOCOMOTION.ram,
      });
    } else if (inheritedMovementRam || (inherited && inheritedHasRam && !inheritedHasChain)) {
      append(fields.ramTuning.fields, true, { composite: fields.ramTuning.composite, ramMode: true });
      const inactiveChainFields = scope === "chill"
        ? ["chainMovementVariance", "chainPauseVariance", "chainPauseAction", "chainRepositionJumpCount", "chainRepositionSpeed", "chainRepositionDistance", "chainRepositionDust", "chainRepositionAllowCardinal", "chainRepositionAllowDiagonal"]
        : fields.chain;
      append(inactiveChainFields, false, { composite: "movement-chain" });
    } else if (inheritedMovementAmbiguous) {
      if (scope === "chill") {
        append(fields.chain, true, {
          composite: "movement-chain-or-ram",
          chainRamDual: true,
          ramMode: inheritedMovementCandidates.includes(LOCOMOTION.ram),
        });
      } else {
        // Active and Tired RAM tuning use state-specific fields, while their
        // chain settings remain shared. Unknown/mixed inheritance needs both
        // groups rather than mislabeled Chill RAM controls.
        append(fields.chain, true, { composite: "movement-chain" });
        append(fields.ramTuning.fields, true, {
          composite: fields.ramTuning.composite,
          ramMode: true,
        });
      }
    } else if (inherited) {
      append(fields.chain, inheritedHasChain, { composite: "movement-chain" });
      append(fields.ramTuning.fields, false, { composite: fields.ramTuning.composite });
    } else {
      append(fields.chain, CHAIN_LOCOMOTIONS.has(raw), { composite: "movement-chain" });
    }
    append(fields.teleportTiming.fields, inherited || raw === LOCOMOTION.teleport, { composite: fields.teleportTiming.composite });
    if (!showInactiveUnset && !inherited && !inheritedMovementRam && !inheritedMovementAmbiguous) {
      append(fields.ramTuning.fields, raw === LOCOMOTION.ram, {
        composite: fields.ramTuning.composite,
        ramMode: raw === LOCOMOTION.ram,
      });
    }
    const option = fieldOptions(parentField, raw, profile).find((candidate) => valueRaw(candidate) === raw);
    return {
      nodes: [...nodes.values()],
      context: showInactiveUnset
        ? "All Chill movement settings are available for this linked state profile."
        : inherited
        ? "Available while movement style inherits."
        : (raw === LOCOMOTION.none
          ? (nodes.size ? "Stored suboptions are inactive while movement is None." : "None has no movement suboptions.")
          : `${valueLabel(option || raw)} movement settings.`),
      inherited,
    };
  }

  function branchChildren(profile, descriptor) {
    if (["chill-behavior", "active-behavior", "tired-behavior"].includes(descriptor.branch)) {
      return behaviorBranch(profile, descriptor.branch);
    }
    const raw = fieldRaw(profile, descriptor.field);
    const inherited = isOverrideProfile(profile) && !raw;
    if (descriptor.branch === "movement") {
      return movementBranch(profile, descriptor.field, descriptor.scope, descriptor.showInactiveUnset);
    }
    if (descriptor.branch === "scoped-action") {
      const showsThrowRange = descriptor.scope === "active" && activeActionShowsThrowRange(profile);
      const movementRaw = fieldRaw(profile, "movementStyle");
      const sharedWithHop = movementRaw === LOCOMOTION.hop || (isOverrideProfile(profile) && !movementRaw);
      return {
        nodes: showsThrowRange && !sharedWithHop ? [{
          field: "attentiveHopMaxDistance",
          label: "Throw range",
        }] : [],
        context: showsThrowRange && sharedWithHop
          ? "Throw range uses the Hop distance maximum below."
          : (showsThrowRange
            ? "Maximum aligned throw distance for the active action."
            : "This action has no additional options."),
        inherited: isOverrideProfile(profile) && !scopedActionCountRaw(descriptor.scope, raw),
      };
    }
    if (descriptor.branch === "spawn-state") {
      const usesHopTime = inherited || raw === SPAWN_HOP_FROM_OFF_SCREEN
        || valueLabel(fieldOptions(descriptor.field, raw, profile).find((option) => valueRaw(option) === raw)).toLowerCase().includes("hop from off screen");
      const nodes = [
        explicitInactiveNode(profile, "spawnHopTime", usesHopTime),
        explicitInactiveNode(profile, "spawnHopSwayWidth", usesHopTime),
      ].filter(Boolean);
      return {
        nodes,
        context: inherited
          ? "Available while spawn state inherits."
          : (usesHopTime ? "Timing and sway for the forced off-screen hop." : (nodes.length ? "Stored spawn-hop settings are inactive for this behavior." : "This spawn behavior has no additional timing.")),
        inherited,
      };
    }
    if (descriptor.branch === "spawn-destination") {
      const destinationPolicy = TERRAIN_POLICY_CONFIGS.spawn;
      const destinationInherited = isOverrideProfile(profile)
        && terrainPolicyMaskNumber(fieldRaw(profile, destinationPolicy.explicitField)) === 0;
      return {
        nodes: ["spawnDestinationMinDistance", "spawnDestinationMaxDistance"].map((field) => ({ field })),
        context: "Minimum and maximum distance used by Player tile and Player front destinations.",
        inherited: destinationInherited,
      };
    }
    if (descriptor.branch === "alert-range") {
      const needsLength = inherited || (!/_NONE$/.test(raw) && !/_TERRAIN_ONLY$/.test(raw));
      const nodes = [];
      if (raw && alertRangeSupportsClose(raw)) nodes.push({ field: "alertRange", virtual: "alert-range-close" });
      const lengthNode = explicitInactiveNode(profile, "alertness", needsLength);
      if (lengthNode) nodes.push(lengthNode);
      return {
        nodes,
        context: inherited
          ? "Available while range type inherits."
          : (needsLength ? "Length used by the selected range shape." : (nodes.length ? "Stored range length is inactive for this shape." : "The selected range shape has no length option.")),
        inherited,
      };
    }
    return { nodes: [], context: "", inherited };
  }

  function renderSelectField(profile, fieldKey, presentation, selectOptions, selectedRaw, stateRaw, originalStateRaw) {
    const override = isOverrideProfile(profile);
    const changed = profile.draftId ? Boolean(stateRaw) : stateRaw !== originalStateRaw;
    const contextBase = presentation.contextBase !== undefined
      ? presentation.contextBase
      : (override ? ui.contextResult?.baseProfile?.[fieldKey] : null);
    const contextBaseRaw = valueRaw(contextBase);
    const hasContextBase = contextBase !== null && contextBase !== undefined && contextBaseRaw !== "";
    const hasOverride = Boolean(stateRaw);
    const state = override
      ? (changed ? "changed" : (hasOverride ? "override" : "inherited"))
      : (changed ? "changed" : "saved");
    let stateLabel = override
      ? (changed
        ? (hasOverride ? "Edited override" : "Will inherit")
        : (hasOverride ? "Overrides base" : "Inherited"))
      : (changed ? "Edited value" : "Saved value");
    const numericOperator = parseNumericOverrideRaw(stateRaw);
    if (override && numericOperator) stateLabel = numericOperatorStateLabel(stateRaw, changed);
    if (presentation.inactive) stateLabel = `${stateLabel}; currently inactive`;
    const instance = presentation.instance || fieldKey;
    const label = fieldLabelForProfile(profile, fieldKey, presentation);
    const allowInherit = presentation.allowInherit ?? override;
    const baseLabel = hasContextBase
      ? (presentation.baseLabel ? presentation.baseLabel(contextBaseRaw) : valueLabel(contextBase))
      : "";
    const unit = fieldUnitForProfile(profile, fieldKey, presentation);
    const descriptionId = `pv2-field-description-${instance.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
    const description = [
      unit ? `Unit: ${unit}.` : "",
      `Status: ${stateLabel}.`,
      hasContextBase ? `Context class base value: ${baseLabel}.` : "",
    ].filter(Boolean).join(" ");
    const stateMarkup = `<span id="${escapeHtml(descriptionId)}" class="sr-only">${escapeHtml(description)}</span>`;
    const visibleMeta = [
      unit ? `<span class="pv2-field-unit" aria-hidden="true">${escapeHtml(unit)}</span>` : "",
      override && numericOperator ? `<span class="pv2-field-note pv2-field-note--operator" aria-hidden="true">${escapeHtml(numericOperatorVisibleNote(stateRaw))}</span>` : "",
      presentation.inactive ? `<span class="pv2-field-note" aria-hidden="true">inactive</span>` : "",
      hasContextBase ? `<span class="field-base base-value pv2-field-base" aria-hidden="true">(${escapeHtml(baseLabel)})</span>` : "",
    ].filter(Boolean).join("");
    const metaMarkup = visibleMeta
      ? `<small class="pv2-field-meta">${stateMarkup}${visibleMeta}</small>`
      : stateMarkup;
    const tabIndex = Number.isInteger(presentation.tabIndex) ? ` tabindex="${presentation.tabIndex}"` : "";
    return `
      <div class="field-row profile-field pv2-field${changed ? " is-changed" : ""}${override && hasOverride ? " is-overridden" : ""}${override && !hasOverride ? " is-inherited" : ""}${presentation.depth ? " is-suboption" : ""}${presentation.parent ? " is-parent-option" : ""}${presentation.inactive ? " is-inactive" : ""}" data-profile-key="${escapeHtml(profileKey(profile))}" data-field-row="${escapeHtml(fieldKey)}" data-field-state="${state}" data-field-depth="${presentation.depth || 0}">
        <span class="field-copy pv2-field-copy">
          <strong>${escapeHtml(label)}</strong>
          ${metaMarkup}
        </span>
        <span class="pv2-value-control">
          ${renderProfileValueEditor(
            profile,
            fieldKey,
            selectOptions,
            selectedRaw,
            instance,
            label,
            descriptionId,
            allowInherit,
            `${presentation.compound ? `data-profile-compound="${escapeHtml(presentation.compound)}"` : ""}${presentation.scope ? ` data-compound-scope="${escapeHtml(presentation.scope)}"` : ""}${tabIndex} aria-label="${escapeHtml(label)}" aria-describedby="${escapeHtml(descriptionId)}"`,
          )}
        </span>
      </div>`;
  }

  function renderFieldControl(profile, fieldKey, presentation = {}) {
    const raw = fieldRaw(profile, fieldKey);
    const original = originalFieldRaw(profile, fieldKey);
    return renderSelectField(
      profile,
      fieldKey,
      presentation,
      fieldOptions(fieldKey, raw, profile, presentation),
      raw,
      raw,
      original,
    );
  }

  function fieldNumericValue(fieldKey, raw) {
    if (raw === null || raw === undefined || raw === "") return NaN;
    const option = (data.editOptions?.[fieldKey] || []).find((candidate) => valueRaw(candidate) === String(raw));
    return Number(option?.value ?? raw);
  }

  function profileFieldRangeError(profile, range) {
    const minimumRaw = fieldRaw(profile, range.min);
    const maximumRaw = fieldRaw(profile, range.max);
    const standaloneThrowRange = range.max === "attentiveHopMaxDistance"
      && activeActionShowsThrowRange(profile)
      && fieldRaw(profile, "movementStyle")
      && fieldRaw(profile, "movementStyle") !== LOCOMOTION.hop;
    if (standaloneThrowRange) return "";
    if (isNumericOverrideRaw(minimumRaw) || isNumericOverrideRaw(maximumRaw)) return "";

    let pairs = [{ minimumRaw, maximumRaw }];
    if (isOverrideProfile(profile) && (!minimumRaw || !maximumRaw)) {
      const baseKeys = unique(potentialAssignmentsFor(profile)
        .map((assignment) => pendingBaseKeyForSpecies(assignment?.species?.symbol))
        .filter(Boolean));
      pairs = baseKeys.map((key) => {
        const baseProfile = findProfile(key);
        return {
          minimumRaw: minimumRaw || fieldRaw(baseProfile, range.min),
          maximumRaw: maximumRaw || fieldRaw(baseProfile, range.max),
        };
      });
    }

    if (pairs.some((pair) => isNumericOverrideRaw(pair.minimumRaw) || isNumericOverrideRaw(pair.maximumRaw))) return "";

    const invalid = pairs.some((pair) => {
      const minimum = fieldNumericValue(range.min, pair.minimumRaw);
      const maximum = fieldNumericValue(range.max, pair.maximumRaw);
      return Number.isFinite(minimum) && Number.isFinite(maximum) && minimum > maximum;
    });
    return invalid ? `${range.label}: minimum cannot exceed maximum.` : "";
  }

  function renderRangeFieldControl(profile, rangeNode, presentation = {}) {
    const override = isOverrideProfile(profile);
    const rangeError = profileFieldRangeError(profile, rangeNode.range);
    const errorId = `pv2-range-error-${String(presentation.instance || rangeNode.range.min).replace(/[^a-zA-Z0-9_-]/g, "-")}`;
    const controls = [
      { role: "Minimum", shortLabel: "Min", node: rangeNode.minNode, fieldKey: rangeNode.range.min },
      { role: "Maximum", shortLabel: "Max", node: rangeNode.maxNode, fieldKey: rangeNode.range.max },
    ].map((control) => {
      const raw = fieldRaw(profile, control.fieldKey);
      const original = originalFieldRaw(profile, control.fieldKey);
      const contextBase = override ? ui.contextResult?.baseProfile?.[control.fieldKey] : null;
      const contextBaseRaw = valueRaw(contextBase);
      const hasContextBase = contextBase !== null && contextBase !== undefined && contextBaseRaw !== "";
      const changed = profile.draftId ? Boolean(raw) : raw !== original;
      const hasOverride = Boolean(raw);
      const inactive = Boolean(presentation.parentInactive || control.node?.inactive);
      const state = override
        ? (changed ? "changed" : (hasOverride ? "override" : "inherited"))
        : (changed ? "changed" : "saved");
      let stateLabel = override
        ? (changed
          ? (hasOverride ? "Edited override" : "Will inherit")
          : (hasOverride ? "Overrides base" : "Inherited"))
        : (changed ? "Edited value" : "Saved value");
      if (override && isNumericOverrideRaw(raw)) stateLabel = numericOperatorStateLabel(raw, changed);
      if (inactive) stateLabel = `${stateLabel}; currently inactive`;
      const instance = `${presentation.instance}:${control.fieldKey}`;
      const descriptionId = `pv2-field-description-${instance.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
      const baseLabel = hasContextBase ? valueLabel(contextBase) : "";
      const description = [
        rangeNode.range.unit ? `Unit: ${rangeNode.range.unit}.` : "",
        `Status: ${stateLabel}.`,
        hasContextBase ? `Base value: ${baseLabel}.` : "",
      ].filter(Boolean).join(" ");
      return {
        ...control,
        raw,
        changed,
        hasOverride,
        inactive,
        state,
        instance,
        descriptionId,
        description,
        hasContextBase,
        baseLabel,
        operatorNote: numericOperatorVisibleNote(raw),
        options: fieldOptions(control.fieldKey, raw, profile, control.node || {}),
      };
    });
    const changed = controls.some((control) => control.changed);
    const hasOverride = controls.some((control) => control.hasOverride);
    const inherited = override && controls.every((control) => !control.hasOverride);
    const inactive = controls.some((control) => control.inactive);
    const baseLabels = controls.map((control) => control.hasContextBase ? control.baseLabel : "—");
    const hasContextBase = controls.some((control) => control.hasContextBase);
    const rangeState = override
      ? (changed ? "changed" : (hasOverride ? "override" : "inherited"))
      : (changed ? "changed" : "saved");
    return `
      <div class="field-row profile-field pv2-field pv2-range-field${changed ? " is-changed" : ""}${override && hasOverride ? " is-overridden" : ""}${inherited ? " is-inherited" : ""}${presentation.depth ? " is-suboption" : ""}${presentation.parent ? " is-parent-option" : ""}${inactive ? " is-inactive" : ""}${rangeError ? " is-invalid" : ""}" data-profile-key="${escapeHtml(profileKey(profile))}" data-field-row="${escapeHtml(`${rangeNode.range.min}:${rangeNode.range.max}`)}" data-field-state="${rangeState}" data-field-depth="${presentation.depth || 0}">
        <span class="field-copy pv2-field-copy">
          <strong>${escapeHtml(rangeNode.range.label)}</strong>
          <small class="pv2-field-meta">
            ${rangeNode.range.unit ? `<span class="pv2-field-unit">${escapeHtml(rangeNode.range.unit)}</span>` : ""}
            ${controls.some((control) => control.operatorNote) ? `<span class="pv2-field-note">resolved pairs normalize after ordered layers</span>` : ""}
            ${inactive ? `<span class="pv2-field-note">inactive</span>` : ""}
            ${hasContextBase ? `<span class="field-base base-value pv2-field-base">(${escapeHtml(baseLabels.join("–"))})</span>` : ""}
          </small>
        </span>
        <span class="pv2-range-controls" role="group" aria-label="${escapeHtml(rangeNode.range.label)}">
          ${controls.map((control) => `
            <div class="pv2-range-control" data-range-state="${escapeHtml(control.state)}">
              <span>${escapeHtml(control.shortLabel)}${control.operatorNote ? `<small class="pv2-field-note">${escapeHtml(control.operatorNote)}</small>` : ""}</span>
              <span id="${escapeHtml(control.descriptionId)}" class="sr-only">${escapeHtml(control.description)}</span>
              <span class="pv2-value-control">
                ${renderProfileValueEditor(
                  profile,
                  control.fieldKey,
                  control.options,
                  control.raw,
                  control.instance,
                  `${rangeNode.range.label}, ${control.role.toLowerCase()}`,
                  control.descriptionId,
                  override,
                  `aria-label="${escapeHtml(`${rangeNode.range.label}, ${control.role.toLowerCase()}`)}" aria-describedby="${escapeHtml(`${control.descriptionId}${rangeError ? ` ${errorId}` : ""}`)}" aria-invalid="${Boolean(rangeError)}"`,
                )}
              </span>
            </div>`).join("")}
          ${rangeError ? `<small id="${escapeHtml(errorId)}" class="pv2-range-error">${escapeHtml(rangeError)}</small>` : ""}
        </span>
      </div>`;
  }

  function renderCompositeFieldControl(profile, compositeNode, presentation = {}) {
    const override = isOverrideProfile(profile);
    const rangeError = compositeNode.composite.range
      ? profileFieldRangeError(profile, compositeNode.composite.range)
      : "";
    const rangeErrorId = `pv2-range-error-${String(presentation.instance || compositeNode.composite.id).replace(/[^a-zA-Z0-9_-]/g, "-")}`;
    const controls = compositeNode.composite.fields.map((definition) => {
      const node = compositeNode.nodes.find((candidate) => candidate.field === definition.key) || {};
      const raw = fieldRaw(profile, definition.key);
      const original = originalFieldRaw(profile, definition.key);
      const contextBase = override ? ui.contextResult?.baseProfile?.[definition.key] : null;
      const contextBaseRaw = valueRaw(contextBase);
      const hasContextBase = contextBase !== null && contextBase !== undefined && contextBaseRaw !== "";
      const changed = profile.draftId ? Boolean(raw) : raw !== original;
      const hasOverride = Boolean(raw);
      const inactive = Boolean(presentation.parentInactive || node.inactive);
      const state = override
        ? (changed ? "changed" : (hasOverride ? "override" : "inherited"))
        : (changed ? "changed" : "saved");
      let stateLabel = override
        ? (changed
          ? (hasOverride ? "Edited override" : "Will inherit")
          : (hasOverride ? "Overrides base" : "Inherited"))
        : (changed ? "Edited value" : "Saved value");
      if (override && isNumericOverrideRaw(raw)) stateLabel = numericOperatorStateLabel(raw, changed);
      if (inactive) stateLabel = `${stateLabel}; currently inactive`;
      const instance = `${presentation.instance}:${definition.key}`;
      const descriptionId = `pv2-field-description-${instance.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
      const baseLabel = hasContextBase ? valueLabel(contextBase) : "";
      const rangeMember = Boolean(compositeNode.composite.range
        && [compositeNode.composite.range.min, compositeNode.composite.range.max].includes(definition.key));
      const description = [
        definition.unit ? `Unit: ${definition.unit}.` : "",
        definition.note ? `${definition.note}.` : "",
        `Status: ${stateLabel}.`,
        hasContextBase ? `Base value: ${baseLabel}.` : "",
      ].filter(Boolean).join(" ");
      return {
        ...definition,
        node,
        raw,
        changed,
        hasOverride,
        inactive,
        state,
        instance,
        descriptionId,
        description,
        hasContextBase,
        baseLabel,
        operatorNote: numericOperatorVisibleNote(raw),
        rangeMember,
        options: fieldOptions(definition.key, raw, profile, node),
      };
    });
    const changed = controls.some((control) => control.changed);
    const hasOverride = controls.some((control) => control.hasOverride);
    const inherited = override && controls.every((control) => !control.hasOverride);
    const inactive = controls.some((control) => control.inactive);
    const compositeState = override
      ? (changed ? "changed" : (hasOverride ? "override" : "inherited"))
      : (changed ? "changed" : "saved");
    return `
      <div class="field-row profile-field pv2-field pv2-composite-field${changed ? " is-changed" : ""}${override && hasOverride ? " is-overridden" : ""}${inherited ? " is-inherited" : ""}${presentation.depth ? " is-suboption" : ""}${inactive ? " is-inactive" : ""}${rangeError ? " is-invalid" : ""}" data-profile-key="${escapeHtml(profileKey(profile))}" data-field-row="${escapeHtml(compositeNode.composite.id)}" data-field-state="${compositeState}" data-field-depth="${presentation.depth || 0}">
        <span class="field-copy pv2-field-copy"><strong>${escapeHtml(compositeNode.composite.label)}</strong>${inactive ? `<small class="pv2-field-meta"><span class="pv2-field-note">inactive</span></small>` : ""}</span>
        <span class="pv2-composite-controls" role="group" aria-label="${escapeHtml(compositeNode.composite.label)}" style="--composite-columns:${controls.length}">
          ${controls.map((control) => `
            <div class="pv2-composite-control" data-composite-state="${escapeHtml(control.state)}">
              <span><b>${escapeHtml(control.label)}</b>${control.unit ? `<small>${escapeHtml(control.unit)}</small>` : ""}${control.operatorNote ? `<small class="pv2-field-note">${escapeHtml(control.operatorNote)}</small>` : ""}${control.hasContextBase ? `<small class="field-base base-value pv2-field-base">(${escapeHtml(control.baseLabel)})</small>` : ""}</span>
              <span id="${escapeHtml(control.descriptionId)}" class="sr-only">${escapeHtml(control.description)}</span>
              <span class="pv2-value-control">
                ${renderProfileValueEditor(
                  profile,
                  control.key,
                  control.options,
                  control.raw,
                  control.instance,
                  `${compositeNode.composite.label}, ${control.label.toLowerCase()}`,
                  control.descriptionId,
                  override,
                  `aria-label="${escapeHtml(`${compositeNode.composite.label}, ${control.label.toLowerCase()}`)}" aria-describedby="${escapeHtml(`${control.descriptionId}${rangeError && control.rangeMember ? ` ${rangeErrorId}` : ""}`)}" aria-invalid="${Boolean(rangeError && control.rangeMember)}"`,
                )}
              </span>
            </div>`).join("")}
          ${rangeError ? `<small id="${escapeHtml(rangeErrorId)}" class="pv2-range-error">${escapeHtml(rangeError)}</small>` : ""}
        </span>
      </div>`;
  }

  function projectComposite(composite, nodes) {
    const availableFields = new Set(nodes.map((node) => node.field));
    const fields = composite.fields.filter((field) => availableFields.has(field.key));
    const { range, ...projected } = composite;
    const keepsRange = range && availableFields.has(range.min) && availableFields.has(range.max);
    return {
      ...projected,
      fields,
      ...(keepsRange ? { range } : {}),
    };
  }

  function consolidateSiblingComposites(nodes) {
    const siblings = (nodes || []).filter(Boolean);
    const byField = new Map(siblings.map((node) => [node.field, node]));
    const consumed = new Set();
    const standaloneNode = (node) => {
      const { composite: _composite, ...standalone } = node;
      return standalone;
    };
    return siblings.flatMap((node) => {
      if (consumed.has(node.field) || !node.composite) return consumed.has(node.field) ? [] : [node];
      const composite = PROFILE_FIELD_COMPOSITES[node.composite];
      if (!composite) return [standaloneNode(node)];
      const compositeNodes = composite.fields
        .map((field) => byField.get(field.key))
        .filter((candidate) => candidate?.composite === composite.id);
      if (compositeNodes.length < 2) return [standaloneNode(node)];
      if (node.field !== compositeNodes[0].field) return [];
      compositeNodes.slice(1).forEach((candidate) => consumed.add(candidate.field));
      return [{
        composite: projectComposite(composite, compositeNodes),
        nodes: compositeNodes,
        children: compositeNodes.flatMap((candidate) => candidate.children || []),
      }];
    });
  }

  function consolidateSiblingRanges(nodes) {
    const siblings = (nodes || []).filter(Boolean);
    const byField = new Map(siblings.map((node) => [node.field, node]));
    const consumed = new Set();
    return siblings.flatMap((node) => {
      if (consumed.has(node.field)) return [];
      const range = PROFILE_FIELD_RANGE_BY_MIN.get(node.field);
      const maxNode = range ? byField.get(range.max) : null;
      if (!range || !maxNode) return [node];
      consumed.add(range.max);
      return [{ range, minNode: node, maxNode, beforeLabel: node.beforeLabel || maxNode.beforeLabel || "" }];
    });
  }

  function consolidateSiblingControls(nodes) {
    return consolidateSiblingRanges(consolidateSiblingComposites(nodes));
  }

  function playerAdjacentMaskNumber(raw) {
    const option = (data.editOptions?.playerAdjacentDirectionMasks || [])
      .find((candidate) => valueRaw(candidate) === String(raw || ""));
    const value = Number(option?.value ?? raw);
    return Number.isInteger(value) && value >= 0 && value <= 15 ? value : 15;
  }

  function playerAdjacentMask(raw) {
    const mask = playerAdjacentMaskNumber(raw) & 0xF;
    return mask || 0xF;
  }

  function playerAdjacentEffectiveMasks(profile, raw) {
    if (raw) return [playerAdjacentMask(raw)];
    const candidates = isOverrideProfile(profile)
      ? effectiveFieldCandidates(profile, "playerAdjacentDirectionMasks")
      : [originalFieldRaw(profile, "playerAdjacentDirectionMasks")];
    const masks = [...new Set(candidates.filter(Boolean).map(playerAdjacentMask))];
    return masks.length ? masks : [0xF];
  }

  function allowedTerrainCatalog() {
    const configured = Array.isArray(data.allowedTerrains) ? data.allowedTerrains : [];
    if (configured.length) return configured.filter((terrain) => Number(terrain.bit) > 0);
    return [
      { key: "land", label: "Land", raw: "OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND", bit: 1 },
      { key: "water", label: "Water", raw: "OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER", bit: 2 },
      { key: "canopy", label: "Canopy", raw: "OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY", bit: 4 },
      { key: "grass", label: "Grass", raw: "OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_GRASS", bit: 8 },
      { key: "player", label: "Player tile", raw: "OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER", bit: 16 },
      { key: "player-front", label: "Player front", raw: "OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER_FRONT", bit: 32 },
      { key: "rooftop", label: "Rooftop", raw: "OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ROOFTOP", bit: 64 },
      { key: "signpost", label: "Signpost", raw: "OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SIGNPOST", bit: 128 },
      { key: "mailbox", label: "Mailbox", raw: "OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_MAILBOX", bit: 256 },
      { key: "flowerbed", label: "Flowerbed", raw: "OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_FLOWERBED", bit: 512 },
    ];
  }

  function terrainPolicyAllMask() {
    return allowedTerrainCatalog().reduce((mask, terrain) => mask | Number(terrain.bit || 0), 0);
  }

  function terrainPolicyMaskNumber(raw) {
    const allMask = terrainPolicyAllMask();
    const cleaned = String(raw || "").trim();
    if (!cleaned) return 0;
    const numeric = Number(cleaned);
    if (Number.isInteger(numeric)) return numeric & allMask;
    if (cleaned.includes("ALLOWED_TERRAIN_ALL")) return allMask;
    const parts = cleaned.replace(/[()]/g, "").split("|").map((part) => part.trim());
    return parts.reduce((mask, part) => {
      const terrain = allowedTerrainCatalog().find((candidate) => candidate.raw === part);
      return mask | Number(terrain?.bit || 0);
    }, 0) & allMask;
  }

  function terrainPolicyState(valueMask, explicitMask, bit) {
    if (!(explicitMask & bit)) return "inherit";
    return valueMask & bit ? "on" : "off";
  }

  function nextTerrainPolicyState(state) {
    if (state === "inherit") return "on";
    if (state === "on") return "off";
    return "inherit";
  }

  function allowedTerrainIcon(key) {
    const paths = {
      land: '<path d="M4 19h16M6 16l4-7 3 4 2-3 3 6H6Z"/>',
      water: '<path d="M3 9c2.2 0 2.2 1.5 4.5 1.5S9.8 9 12 9s2.2 1.5 4.5 1.5S18.8 9 21 9M3 14c2.2 0 2.2 1.5 4.5 1.5S9.8 14 12 14s2.2 1.5 4.5 1.5S18.8 14 21 14"/>',
      canopy: '<path d="M12 20v-7M8 20h8M7.5 13a4 4 0 0 1 .8-7.9A4.5 4.5 0 0 1 17 7a3.5 3.5 0 0 1-.5 6H7.5Z"/>',
      grass: '<path d="M5 20c0-5 1-8 4-12 0 5-1 8-4 12Zm7 0c0-7 0-11 2-16 1 6 1 10-2 16Zm4 0c0-4 1-7 4-10 0 5-1 8-4 10Z"/>',
      player: '<circle cx="12" cy="7" r="2.5"/><path d="M8 20v-3.5a4 4 0 0 1 8 0V20"/>',
      "player-front": '<circle cx="12" cy="7" r="2.5"/><path d="M8 20v-3.5a4 4 0 0 1 8 0V20M12 4V1m0 0L9.8 3.2M12 1l2.2 2.2"/>',
      rooftop: '<path d="M3 12 12 5l9 7M5 11v8h14v-8M9 19v-5h6v5"/>',
      signpost: '<path d="M5 5h14v9H5zM12 14v7M9 21h6"/>',
      mailbox: '<path d="M4 10a6 6 0 0 1 12 0v7H4zM16 10h4v7h-4M8 7v10M11 4h4v4h-4"/>',
      flowerbed: '<path d="M4 14h16l-2 7H6l-2-7Zm3 0V9m5 5V6m5 8V9M5 9c2-2 4-2 5 0-1 2-3 3-5 0Zm5-3c2-3 4-3 5 0-1 2-4 3-5 0Zm5 3c2-2 4-2 5 0-1 2-3 3-5 0Z"/>',
    };
    return `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">${paths[key] || paths.land}</svg>`;
  }

  function setTerrainPolicyState(profile, policyId, bit, state) {
    const policy = TERRAIN_POLICY_CONFIGS[policyId];
    if (!policy) return;
    const allMask = terrainPolicyAllMask();
    let valueMask = terrainPolicyMaskNumber(fieldRaw(profile, policy.valueField));
    let explicitMask = terrainPolicyMaskNumber(fieldRaw(profile, policy.explicitField));
    if (state === "inherit") {
      explicitMask &= ~bit;
      valueMask &= ~bit;
    } else {
      explicitMask |= bit;
      if (state === "on") valueMask |= bit;
      else valueMask &= ~bit;
    }
    if (isOverrideProfile(profile) && !explicitMask) {
      // Spawn overrides retain an explicit zero pair so a hidden legacy
      // spawnDestination cannot be projected back into the unified policy.
      // A zero explicit mask still renders and merges as fully inherited.
      setField(profile, policy.valueField, policyId === "spawn" ? "0" : "");
      setField(profile, policy.explicitField, policyId === "spawn" ? "0" : "");
    } else {
      setField(profile, policy.valueField, String(valueMask & allMask));
      setField(profile, policy.explicitField, String(explicitMask & allMask));
    }
  }

  function renderTerrainPolicy(profile, node, presentation, policyId) {
    const policy = TERRAIN_POLICY_CONFIGS[policyId];
    if (!policy) return "";
    const valueRawValue = fieldRaw(profile, policy.valueField);
    const explicitRawValue = fieldRaw(profile, policy.explicitField);
    const valueMask = terrainPolicyMaskNumber(valueRawValue);
    const explicitMask = terrainPolicyMaskNumber(explicitRawValue);
    const originalValue = originalFieldRaw(profile, policy.valueField);
    const originalExplicit = originalFieldRaw(profile, policy.explicitField);
    const changed = profile.draftId
      ? Boolean(valueRawValue || explicitRawValue)
      : valueRawValue !== originalValue || explicitRawValue !== originalExplicit;
    const inherited = isOverrideProfile(profile) && explicitMask === 0;
    const state = changed ? "changed" : (inherited ? "inherited" : (isOverrideProfile(profile) ? "override" : "saved"));
    return `
      <div class="field-row profile-field pv2-field pv2-terrain-policy-field${changed ? " is-changed" : ""}${inherited ? " is-inherited" : ""}${presentation.depth ? " is-suboption" : ""}${presentation.inactive ? " is-inactive" : ""}" data-profile-key="${escapeHtml(profileKey(profile))}" data-field-row="${policy.valueField}" data-field-state="${state}" data-field-depth="${presentation.depth || 0}">
        <span class="field-copy pv2-field-copy"><strong>${escapeHtml(policy.label)}</strong><small class="pv2-field-meta"><span class="pv2-field-note">${escapeHtml(policy.note)}</span>${presentation.inactive ? `<span class="pv2-field-note">inactive</span>` : ""}</small></span>
        <span class="pv2-terrain-policy" role="group" aria-label="${escapeHtml(policy.ariaLabel)}">
          ${allowedTerrainCatalog().map((terrain) => {
            const bit = Number(terrain.bit);
            const terrainState = terrainPolicyState(valueMask, explicitMask, bit);
            const nextState = nextTerrainPolicyState(terrainState);
            return `<button type="button" class="pv2-terrain-toggle is-${terrainState}" data-action="set-terrain-policy" data-profile-key="${escapeHtml(profileKey(profile))}" data-terrain-policy="${escapeHtml(policyId)}" data-terrain-label="${escapeHtml(terrain.label)}" data-terrain-bit="${bit}" data-terrain-state="${terrainState}" data-next-terrain-state="${nextState}" aria-label="${escapeHtml(`${policy.label}, ${terrain.label}: ${terrainState}. Click for ${nextState}.`)}" title="${escapeHtml(`${terrain.label} · ${terrainState}`)}">${allowedTerrainIcon(terrain.key)}<span>${escapeHtml(terrain.label)}</span><small class="sr-only">${escapeHtml(terrainState)}</small></button>`;
          }).join("")}
        </span>
      </div>`;
  }

  function renderPlayerAdjacentDirections(profile, node, presentation) {
    const fieldKey = node.field;
    const raw = fieldRaw(profile, fieldKey);
    const original = originalFieldRaw(profile, fieldKey);
    const masks = playerAdjacentEffectiveMasks(profile, raw);
    const anyMask = masks.reduce((combined, candidate) => combined | candidate, 0);
    const everyMask = masks.reduce((combined, candidate) => combined & candidate, 0xF);
    const mixed = masks.length > 1;
    const override = isOverrideProfile(profile);
    const changed = profile.draftId ? Boolean(raw) : raw !== original;
    const inherited = override && !raw;
    const state = override
      ? (changed ? "changed" : (inherited ? "inherited" : "override"))
      : (changed ? "changed" : "saved");
    const directions = [
      [1, "Behind player"],
      [0, "Front of player"],
      [2, "Left of player"],
      [3, "Right of player"],
    ];
    return `
      <div class="field-row profile-field pv2-field pv2-direction-field${changed ? " is-changed" : ""}${inherited ? " is-inherited" : ""}${presentation.depth ? " is-suboption" : ""}${presentation.inactive ? " is-inactive" : ""}" data-profile-key="${escapeHtml(profileKey(profile))}" data-field-row="${fieldKey}" data-field-state="${state}" data-field-depth="${presentation.depth || 0}">
        <span class="field-copy pv2-field-copy"><strong>Position relative to player</strong><small class="pv2-field-meta"><span class="pv2-field-note">shared by Next to player targets${mixed ? " · mixed inherited values" : ""}</span>${presentation.inactive ? `<span class="pv2-field-note">inactive</span>` : ""}</small></span>
        <span class="pv2-direction-options" role="group" aria-label="Allowed positions relative to player">
          ${directions.map(([bit, label]) => {
            const directionMixed = Boolean((anyMask & (1 << bit)) && !(everyMask & (1 << bit)));
            return `<label class="pv2-direction-option${directionMixed ? " is-mixed" : ""}"><input type="checkbox" data-player-adjacent-direction data-profile-key="${escapeHtml(profileKey(profile))}" data-field-key="${fieldKey}" data-direction-bit="${bit}" ${everyMask & (1 << bit) ? "checked" : ""} ${directionMixed ? `data-direction-mixed aria-label="${label}, mixed inherited value"` : ""}><span>${label}${directionMixed ? " ·" : ""}</span></label>`;
          }).join("")}
          ${override ? `<button type="button" class="pv2-direction-inherit" data-action="inherit-player-adjacent-directions" data-profile-key="${escapeHtml(profileKey(profile))}" ${inherited ? "disabled" : ""}>Inherit</button>` : ""}
        </span>
      </div>`;
  }

  function renderVirtualFieldControl(profile, node, presentation = {}) {
    const fieldKey = node.field;
    const raw = fieldRaw(profile, fieldKey);
    const original = originalFieldRaw(profile, fieldKey);
    if (node.virtual === "player-adjacent-directions") {
      return renderPlayerAdjacentDirections(profile, node, presentation);
    }
    if (node.virtual === "allowed-terrain-policy") {
      return renderTerrainPolicy(profile, node, presentation, "allowed");
    }
    if (node.virtual === "spawn-destination-policy") {
      return renderTerrainPolicy(profile, node, presentation, "spawn");
    }
    if (node.virtual === "alert-range-type") {
      return renderSelectField(profile, fieldKey, {
        ...presentation,
        label: "Range type",
        compound: node.virtual,
        baseLabel: (baseRaw) => valueLabel(alertRangeTypeOptions().find((option) => valueRaw(option) === alertRangeBaseRaw(baseRaw)) || alertRangeBaseRaw(baseRaw)),
      }, alertRangeTypeOptions(), alertRangeBaseRaw(raw), raw, original);
    }
    if (node.virtual === "alert-range-close") {
      return renderSelectField(profile, fieldKey, {
        ...presentation,
        label: "Close range",
        compound: node.virtual,
        allowInherit: false,
        baseLabel: (baseRaw) => alertRangeIsClose(baseRaw) ? "Yes" : "No",
      }, [{ raw: "0", label: "No" }, { raw: "1", label: "Yes" }], alertRangeIsClose(raw) ? "1" : "0", raw, original);
    }
    if (node.virtual === "scoped-action") {
      const scope = node.scope;
      const scopedRaw = scopedActionCountRaw(scope, raw);
      const originalScopedRaw = scopedActionCountRaw(scope, original);
      const displayRaw = scopedActionRaw(scope, raw);
      const actionRaw = scope === "alert" ? ALERT_SPECIAL.call : ALERT_SPECIAL.throw;
      const actionOption = (data.editOptions?.alertSpecialAction || []).find((option) => valueRaw(option) === actionRaw) || { raw: actionRaw };
      const noneOption = (data.editOptions?.alertSpecialAction || []).find((option) => valueRaw(option) === ALERT_SPECIAL.none) || { raw: ALERT_SPECIAL.none, label: "None" };
      const unknownOption = raw && !scopedActionIsKnown(raw)
        ? { raw, label: `Unsupported stored action · ${valueLabel(raw)}` }
        : null;
      const contextBaseRaw = valueRaw(ui.contextResult?.baseProfile?.alertSpecialAction);
      return renderSelectField(profile, fieldKey, {
        ...presentation,
        label: scope === "alert" ? "Alert action" : "Active action",
        compound: node.virtual,
        scope,
        contextBase: contextBaseRaw,
        baseLabel: (baseRaw) => !scopedActionIsKnown(baseRaw)
          ? `Unsupported stored action · ${valueLabel(baseRaw)}`
          : valueLabel(scopedActionOwns(scope, baseRaw) ? actionOption : noneOption),
      }, [noneOption, actionOption, unknownOption].filter(Boolean), displayRaw, scopedRaw, originalScopedRaw);
    }
    return renderFieldControl(profile, fieldKey, presentation);
  }

  function renderHierarchyNode(profile, node, sectionId, path, depth = 0, parentInactive = false) {
    if (!node) return "";
    if (node.composite && Array.isArray(node.nodes)) {
      const editableNodes = node.nodes.filter((candidate) => profileCanEditField(profile, candidate.field));
      if (editableNodes.length !== node.nodes.length) {
        if (editableNodes.length >= 2) {
          return renderHierarchyNode(profile, {
            ...node,
            composite: projectComposite(node.composite, editableNodes),
            nodes: editableNodes,
            children: editableNodes.flatMap((candidate) => candidate.children || []),
          }, sectionId, `${path}.available`, depth, parentInactive);
        }
        return editableNodes
          .map((candidate, index) => renderHierarchyNode(profile, candidate, sectionId, `${path}.available-${index}`, depth, parentInactive))
          .join("");
      }
      const beforeMarkup = node.nodes[0]?.beforeLabel
        ? `<h4 class="pv2-suboption-divider">${escapeHtml(node.nodes[0].beforeLabel)}</h4>`
        : "";
      const compositeControl = renderCompositeFieldControl(profile, node, {
        depth,
        parentInactive,
        instance: `${sectionId}:${path}:${node.composite.id}`,
      });
      const compositeInactive = Boolean(parentInactive || node.nodes.some((candidate) => candidate.inactive));
      const childMarkup = consolidateSiblingControls(node.children || [])
        .map((child, index) => renderHierarchyNode(profile, child, sectionId, `${path}.child-${index}`, depth + 1, compositeInactive))
        .filter(Boolean)
        .join("");
      if (!childMarkup) return `${beforeMarkup}${compositeControl}`;
      return `${beforeMarkup}
        <div class="pv2-option-group${depth ? " is-nested" : ""}" data-option-parent="${escapeHtml(node.nodes[0]?.field || node.composite.id)}" data-option-depth="${depth}">
          <div class="pv2-option-parent">${compositeControl}</div>
          <div class="pv2-suboptions" role="group" aria-label="${escapeHtml(`${node.composite.label} suboptions`)}">
            <div class="pv2-suboption-grid">${childMarkup}</div>
          </div>
        </div>`;
    }
    if (node.range) {
      const canEditMinimum = profileCanEditField(profile, node.range.min);
      const canEditMaximum = profileCanEditField(profile, node.range.max);
      if (!canEditMinimum || !canEditMaximum) {
        const availableNode = canEditMinimum ? node.minNode : (canEditMaximum ? node.maxNode : null);
        return availableNode ? renderHierarchyNode(profile, availableNode, sectionId, `${path}.available`, depth, parentInactive) : "";
      }
      const beforeMarkup = node.beforeLabel
        ? `<h4 class="pv2-suboption-divider">${escapeHtml(node.beforeLabel)}</h4>`
        : "";
      return `${beforeMarkup}${renderRangeFieldControl(profile, node, {
        depth,
        parentInactive,
        instance: `${sectionId}:${path}:range`,
      })}`;
    }
    if (!profileCanEditField(profile, node.field)) return "";
    const inactive = Boolean(parentInactive || node.inactive);
    const instance = `${sectionId}:${path}:${node.field}`;
    const childMarkup = consolidateSiblingControls(node.children || [])
      .map((child, index) => renderHierarchyNode(profile, child, sectionId, `${path}.${index}`, depth + 1, inactive))
      .filter(Boolean)
      .join("");
    const renderControl = node.virtual ? renderVirtualFieldControl : renderFieldControl;
    const contextId = node.context ? `pv2-branch-context-${instance.replace(/[^a-zA-Z0-9_-]/g, "-")}` : "";
    const control = renderControl(profile, node.virtual ? node : node.field, {
      ...node,
      depth,
      inactive,
      instance,
      parent: Boolean(childMarkup) || depth === 0,
    });
    const beforeMarkup = node.beforeLabel ? `<h4 class="pv2-suboption-divider">${escapeHtml(node.beforeLabel)}</h4>` : "";
    if (!childMarkup) return `${beforeMarkup}${control}`;
    return `${beforeMarkup}
      <div class="pv2-option-group${depth ? " is-nested" : ""}" data-option-parent="${escapeHtml(node.field)}" data-option-depth="${depth}">
        <div class="pv2-option-parent">${control}</div>
        <div class="pv2-suboptions" role="group" aria-label="${escapeHtml(fieldLabelForProfile(profile, node.field))} suboptions"${contextId ? ` aria-describedby="${escapeHtml(contextId)}"` : ""}>
          ${node.context ? `<p id="${escapeHtml(contextId)}" class="pv2-branch-context">${escapeHtml(node.context)}</p>` : ""}
          <div class="pv2-suboption-grid">${childMarkup}</div>
        </div>
      </div>`;
  }

  function branchParts(profile, descriptor) {
    if (!profileCanEditField(profile, descriptor.field)) return null;
    const branch = branchChildren(profile, descriptor);
    const children = branch.nodes.filter((node) => profileCanEditField(profile, node.field));
    return {
      branch,
      children,
      rootNode: {
        field: descriptor.field,
        children,
        context: branch.context,
        virtual: descriptor.virtual,
        scope: descriptor.scope,
      },
    };
  }

  function renderBranch(profile, descriptor, sectionId, index) {
    const parts = branchParts(profile, descriptor);
    if (!parts) return "";
    const markup = renderHierarchyNode(profile, parts.rootNode, sectionId, `branch-${index}`);
    if (!markup) return "";
    if (!parts.children.length) return `<div class="pv2-root-field-grid">${markup}</div>`;
    return `
      <div class="pv2-branch-wrap${parts.branch.inherited ? " is-inherited-branch" : ""}">
        ${markup}
      </div>`;
  }

  function renderBranchTabSelect(profile, descriptor, sectionId, tabId, active) {
    const parts = branchParts(profile, descriptor);
    if (!parts) return "";
    const renderControl = parts.rootNode.virtual ? renderVirtualFieldControl : renderFieldControl;
    return renderControl(profile, parts.rootNode.virtual ? parts.rootNode : parts.rootNode.field, {
      ...parts.rootNode,
      depth: 0,
      instance: `${sectionId}:mode-tab-${tabId}:${descriptor.field}`,
      parent: true,
      tabIndex: active ? 0 : -1,
    });
  }

  function renderBranchTabBody(profile, descriptor, sectionId, path) {
    const parts = branchParts(profile, descriptor);
    if (!parts) return "";
    const childMarkup = consolidateSiblingControls(parts.children)
      .map((child, index) => renderHierarchyNode(profile, child, sectionId, `${path}.${index}`, 1))
      .filter(Boolean)
      .join("");
    const contextId = parts.branch.context
      ? `pv2-mode-context-${`${sectionId}-${path}`.replace(/[^a-zA-Z0-9_-]/g, "-")}`
      : "";
    return `
      <div class="pv2-mode-tab-branch${parts.branch.inherited ? " is-inherited-branch" : ""}">
        ${childMarkup ? `<div class="pv2-mode-tab-suboptions" role="group" aria-label="${escapeHtml(`${fieldLabelForProfile(profile, descriptor.field)} suboptions`)}"${contextId ? ` aria-describedby="${escapeHtml(contextId)}"` : ""}>
          ${parts.branch.context ? `<p id="${escapeHtml(contextId)}" class="pv2-branch-context">${escapeHtml(parts.branch.context)}</p>` : ""}
          <div class="pv2-suboption-grid">${childMarkup}</div>
        </div>` : (parts.branch.context ? `<p class="pv2-branch-context">${escapeHtml(parts.branch.context)}</p>` : "")}
      </div>`;
  }

  function renderFieldsDescriptor(profile, section, descriptor, index, prefix = "fields") {
    const markup = consolidateSiblingControls((descriptor.fields || [])
      .filter((field) => profileCanEditField(profile, field))
      .map((field) => ({ field, composite: descriptor.composite || "" })))
      .map((node, fieldIndex) => node.composite
        ? renderCompositeFieldControl(profile, node, { instance: `${section.id}:${prefix}-${index}.${fieldIndex}:${node.composite.id}` })
        : (node.range
          ? renderRangeFieldControl(profile, node, { instance: `${section.id}:${prefix}-${index}.${fieldIndex}:range` })
          : renderFieldControl(profile, node.field, {
          instance: `${section.id}:${prefix}-${index}.${fieldIndex}:${node.field}`,
        })))
      .join("");
    return markup ? `<div class="pv2-root-field-grid">${markup}</div>` : "";
  }

  function selectedModeTab(sectionId, tabs) {
    const stored = branchTabSelections.get(sectionId);
    return tabs.find((tab) => tab.id === stored) || tabs[0];
  }

  function renderModeTabs(profile, section, descriptors) {
    const tabs = (section.subtabs || []).map((tab) => {
      const tabDescriptors = descriptors.filter((descriptor) => descriptor.subtab === tab.id);
      const parentDescriptor = tabDescriptors.find((descriptor) => descriptor.kind === "branch");
      return { ...tab, descriptors: tabDescriptors, parentDescriptor };
    }).filter((tab) => tab.parentDescriptor && profileCanEditField(profile, tab.parentDescriptor.field));
    if (tabs.length < 2) return "";
    const selected = selectedModeTab(section.id, tabs);
    const tabHeaders = tabs.map((tab) => {
      const active = tab.id === selected.id;
      return `<div class="pv2-mode-tab${active ? " is-active" : ""}">
        <button type="button" role="tab" id="pv2-mode-tab-${escapeHtml(section.id)}-${escapeHtml(tab.id)}" aria-controls="pv2-mode-panel-${escapeHtml(section.id)}-${escapeHtml(tab.id)}" aria-selected="${active}" tabindex="${active ? "0" : "-1"}" data-action="select-mode-tab" data-mode-tab="${escapeHtml(tab.id)}" data-mode-tab-section="${escapeHtml(section.id)}">${escapeHtml(tab.label)}</button>
        <div class="pv2-mode-tab-select" data-mode-tab-select="${escapeHtml(tab.id)}" data-mode-tab-section="${escapeHtml(section.id)}">${renderBranchTabSelect(profile, tab.parentDescriptor, section.id, tab.id, active)}</div>
      </div>`;
    }).join("");
    const tabPanels = tabs.map((tab) => {
      const active = tab.id === selected.id;
      const content = active ? tab.descriptors.map((descriptor, index) => {
        if (descriptor.kind === "branch") return renderBranchTabBody(profile, descriptor, section.id, `mode-${tab.id}-${index}`);
        return renderFieldsDescriptor(profile, section, descriptor, index, `mode-${tab.id}-fields`);
      }).join("") : "";
      return `<section class="pv2-mode-tabpanel" role="tabpanel" id="pv2-mode-panel-${escapeHtml(section.id)}-${escapeHtml(tab.id)}" aria-labelledby="pv2-mode-tab-${escapeHtml(section.id)}-${escapeHtml(tab.id)}" data-mode-tabpanel="${escapeHtml(tab.id)}" ${active ? "" : "hidden"}>${content}</section>`;
    }).join("");
    return `<div class="pv2-mode-tabs-workspace"><div class="pv2-mode-tabs" role="tablist" aria-label="${escapeHtml(`${section.title} options`)}">${tabHeaders}</div>${tabPanels}</div>`;
  }

  function renderSectionContent(profile, section) {
    if (!section.nodes) {
      return `<div class="pv2-root-field-grid">${section.fields.map((field, index) => renderFieldControl(profile, field, { instance: `${section.id}:field-${index}:${field}` })).join("")}</div>`;
    }
    const tabbedDescriptors = section.nodes.filter((descriptor) => descriptor.subtab);
    const standaloneDescriptors = section.nodes.filter((descriptor) => !descriptor.subtab);
    const modeTabs = tabbedDescriptors.length ? renderModeTabs(profile, section, tabbedDescriptors) : "";
    const standalone = standaloneDescriptors.map((descriptor, index) => {
      if (descriptor.kind === "branch") return renderBranch(profile, descriptor, section.id, `standalone-${index}`);
      return renderFieldsDescriptor(profile, section, descriptor, index);
    }).join("");
    if (modeTabs) return `${modeTabs}${standalone}`;
    return [...tabbedDescriptors, ...standaloneDescriptors].map((descriptor, index) => {
      if (descriptor.kind === "branch") return renderBranch(profile, descriptor, section.id, index);
      return renderFieldsDescriptor(profile, section, descriptor, index);
    }).join("");
  }

  function renderStateProfileReference(profile, section) {
    const fieldKey = section.stateProfileField;
    const raw = fieldRaw(profile, fieldKey);
    const original = originalFieldRaw(profile, fieldKey);
    const changed = profile.draftId ? Boolean(raw) : raw !== original;
    const override = isOverrideProfile(profile);
    const linkedProfile = laneReferenceProfile(raw);
    const references = laneReferenceProfiles();
    const missing = Boolean(raw && !linkedProfile);
    const selectOptions = references.map((candidate) => {
      const candidateRaw = stateReferenceRaw(candidate);
      const order = ordersFor(candidate)[0];
      return `<option value="${escapeHtml(candidateRaw)}" ${candidateRaw === raw ? "selected" : ""}>${escapeHtml(nameFor(candidate))} · #${escapeHtml(order)}</option>`;
    }).join("");
    const emptyOption = override
      ? `<option value="" ${raw ? "" : "selected"}>Inherit</option>`
      : `<option value="" ${raw ? "" : "selected"} disabled>Select an override profile</option>`;
    const missingOption = missing
      ? `<option value="${escapeHtml(raw)}" selected disabled>Unavailable override profile · #${escapeHtml(Number(raw) + 1)}</option>`
      : "";
    const state = changed ? "changed" : (override ? (raw ? "override" : "inherited") : "saved");
    const chillSection = FIELD_SECTIONS.find((candidate) => candidate.id === "chill");
    const stateValueField = fieldKey === "activeProfile" ? "stamina" : "restTime";
    const stateValueLabel = fieldKey === "activeProfile" ? "Active stamina" : "Tired rest time";
    const linkedFields = linkedProfile && chillSection
      ? sectionFields(chillSection, linkedProfile).filter((field) => field !== "stamina" && field !== "restTime")
      : [];
    const linkedSection = chillSection ? {
      ...chillSection,
      id: `${section.id}-linked-chill`,
      fields: linkedFields,
      nodes: chillSection.nodes?.map((descriptor) => {
        const linkedDescriptor = descriptor.fields ? {
          ...descriptor,
          fields: descriptor.fields.filter((field) => field !== "stamina" && field !== "restTime"),
        } : { ...descriptor };
        if (descriptor.branch === "movement") linkedDescriptor.showInactiveUnset = true;
        return linkedDescriptor;
      }),
    } : null;
    return `<div class="pv2-state-profile-link${changed ? " is-changed" : ""}${missing ? " is-missing" : ""}" data-profile-key="${escapeHtml(profileKey(profile))}" data-field-state="${escapeHtml(state)}">
      <div class="pv2-state-owned-value">
        <p><strong>${escapeHtml(stateValueLabel)}</strong><small>Stored on ${escapeHtml(nameFor(profile))}; this value does not come from the selected override profile.</small></p>
        <div class="pv2-root-field-grid">${profileCanEditField(profile, stateValueField) ? renderFieldControl(profile, stateValueField, { instance: `${section.id}:state-value:${stateValueField}`, label: stateValueField === "stamina" ? "Stamina" : "Rest time" }) : ""}</div>
      </div>
      <label class="pv2-state-profile-picker">
        <span><strong>Override profile</strong><small>Applied whenever this Pokémon is ${escapeHtml(section.id)}.</small></span>
        <select class="field-control" data-state-profile-reference data-profile-key="${escapeHtml(profileKey(profile))}" data-field-key="${escapeHtml(fieldKey)}" aria-label="${escapeHtml(`${section.title} override profile`)}" aria-invalid="${missing}">
          ${emptyOption}${missingOption}${selectOptions}
        </select>
      </label>
      ${linkedProfile && linkedSection ? `<div class="pv2-linked-chill-editor" data-linked-profile-key="${escapeHtml(profileKey(linkedProfile))}">
        <header><span><strong>${escapeHtml(nameFor(linkedProfile))} · Chill state</strong><small>These are the selected override profile's Chill values. Editing them updates that override everywhere it is referenced.</small></span><em>Linked globally</em></header>
        ${linkedFields.length ? renderSectionContent(linkedProfile, linkedSection) : `<p class="pv2-linked-state-empty">This override profile has no editable Chill fields.</p>`}
      </div>` : `<p class="pv2-linked-state-empty">${missing ? "The referenced override profile is unavailable. Choose a replacement before saving." : "Choose an override profile to edit the Chill values used by this state."}</p>`}
    </div>`;
  }

  function sectionFields(section, profile) {
    const known = new Set(data.fields.map((field) => field.key));
    const allowed = new Set(data.overrideFieldKeys || []);
    return unique(section.fields.filter((field) => known.has(field) && (!isOverrideProfile(profile) || allowed.has(field))));
  }

  function sectionFieldRaw(section, profile, fieldKey) {
    const raw = fieldRaw(profile, fieldKey);
    if (fieldKey === "alertSpecialAction" && section?.scopedAction) {
      return scopedActionCountRaw(section.scopedAction, raw);
    }
    return raw;
  }

  function clearSectionField(section, profile, fieldKey) {
    if (fieldKey === "alertSpecialAction" && section?.scopedAction) {
      const raw = scopedActionClearRaw(section.scopedAction, fieldRaw(profile, fieldKey), originalFieldRaw(profile, fieldKey));
      setField(profile, fieldKey, raw);
      return;
    }
    setField(profile, fieldKey, "");
  }

  function unsectionedFields(profile) {
    const sectioned = new Set(FIELD_SECTIONS.flatMap((section) => section.fields));
    const hidden = new Set(HIDDEN_PROFILE_EDITOR_FIELDS);
    const allowed = new Set(data.overrideFieldKeys || []);
    return data.fields
      .map((field) => field.key)
      .filter((field) => !sectioned.has(field)
        && !hidden.has(field)
        && (!isOverrideProfile(profile) || allowed.has(field)));
  }

  function sectionCountInfo(section, override) {
    if (section.conditionPanel || section.conditionalStatePanel) {
      const noun = section.conditionPanel ? "state" : "override";
      return {
        compact: String(section.overrideCount),
        spoken: `${section.overrideCount} ${noun}${section.overrideCount === 1 ? "" : "s"}`,
      };
    }
    return {
      compact: override ? `${section.overrideCount}/${section.fields.length}` : String(section.fields.length),
      spoken: override
        ? `${section.overrideCount} of ${section.fields.length} fields overridden`
        : `${section.fields.length} fields`,
    };
  }

  function renderSectionToolbar(section, profile) {
    const sourceSection = section.sourceSectionId || section.id;
    return `<div class="pv2-section-toolbar"><span>Only set values override; the rest inherit.${section.sharedMovement ? " Shared movement values can affect other states." : ""}</span><button class="pv2-section-inherit" type="button" data-action="clear-section" data-profile-key="${escapeHtml(profileKey(profile))}" data-section="${escapeHtml(sourceSection)}" data-focus-section="${escapeHtml(section.id)}" aria-label="Make all ${escapeHtml(section.title)} values inherit" ${section.overrideCount ? "" : "disabled"}>Inherit all</button></div>`;
  }

  function renderAccordionSection(profile, section, override) {
    const count = sectionCountInfo(section, override);
    const expanded = ui.openSections.has(section.id);
    return `
      <details class="field-section pv2-field-section" data-section-id="${escapeHtml(section.id)}" ${expanded ? "open" : ""}>
        <summary>
          <span><strong>${escapeHtml(section.title)}</strong><small>${escapeHtml(section.hint)}</small></span>
          <em><span aria-hidden="true">${escapeHtml(count.compact)}</span><span class="sr-only">${escapeHtml(count.spoken)}</span></em>
        </summary>
        ${override && expanded ? renderSectionToolbar(section, profile) : ""}
        ${expanded ? `<div class="profile-fields pv2-field-hierarchy">${renderSectionContent(profile, section)}</div>` : ""}
      </details>`;
  }

  function conditionalTerrainNames(mask) {
    return allowedTerrainCatalog()
      .filter((terrain) => mask & Number(terrain.bit))
      .map((terrain) => terrain.label);
  }

  function conditionalStateSummary(entry) {
    const explicit = terrainPolicyMaskNumber(entry.terrainOverrideMask);
    const accepted = terrainPolicyMaskNumber(entry.terrainMask) & explicit;
    const excluded = explicit & ~accepted;
    const acceptedNames = conditionalTerrainNames(accepted);
    const excludedNames = conditionalTerrainNames(excluded);
    const terrainParts = [];
    if (acceptedNames.length) terrainParts.push(acceptedNames.join(" or "));
    if (excludedNames.length) terrainParts.push(`not ${excludedNames.join(" or ")}`);
    const minSpeed = conditionalMovementSpeed(entry.minMovementSpeed);
    const maxSpeed = conditionalMovementSpeed(entry.maxMovementSpeed);
    const speed = !minSpeed && !maxSpeed
      ? ""
      : (minSpeed === maxSpeed ? `speed ${minSpeed}` : `speed ${minSpeed}–${maxSpeed}`);
    return [...terrainParts, speed].filter(Boolean).join(" and ") || "No conditions";
  }

  function renderConditionalTerrainPolicy(profile, conditionalState) {
    const valueMask = terrainPolicyMaskNumber(conditionalState.terrainMask);
    const explicitMask = terrainPolicyMaskNumber(conditionalState.terrainOverrideMask);
    const stateKey = conditionalStateKey(conditionalState);
    return `<div class="pv2-conditional-terrain">
      <span><strong>Tiles</strong><small>Green accepts any selected tile, red excludes it, grey ignores it.</small></span>
      <span class="pv2-terrain-policy" role="group" aria-label="Conditional terrain policy">
        ${allowedTerrainCatalog().map((terrain) => {
          const bit = Number(terrain.bit);
          const terrainState = terrainPolicyState(valueMask, explicitMask, bit);
          const nextState = nextTerrainPolicyState(terrainState);
          return `<button type="button" class="pv2-terrain-toggle is-${terrainState}" data-action="set-conditional-terrain" data-profile-key="${escapeHtml(profileKey(profile))}" data-condition-state-key="${escapeHtml(stateKey)}" data-terrain-label="${escapeHtml(terrain.label)}" data-terrain-bit="${bit}" data-next-terrain-state="${nextState}" aria-label="${escapeHtml(`Condition, ${terrain.label}: ${terrainState}. Click for ${nextState}.`)}" title="${escapeHtml(`${terrain.label} · ${terrainState}`)}">${allowedTerrainIcon(terrain.key)}<span>${escapeHtml(terrain.label)}</span><small class="sr-only">${escapeHtml(terrainState)}</small></button>`;
        }).join("")}
      </span>
    </div>`;
  }

  function conditionalSpeedMode(entry) {
    const min = conditionalMovementSpeed(entry.minMovementSpeed);
    const max = conditionalMovementSpeed(entry.maxMovementSpeed);
    if (!min && !max) return "any";
    return min === max ? "exact" : "range";
  }

  function movementSpeedOptions(selected) {
    return Array.from({ length: CONDITIONAL_MOVEMENT_SPEED_MAX }, (_, index) => index + 1)
      .map((speed) => `<option value="${speed}" ${speed === selected ? "selected" : ""}>${speed}</option>`)
      .join("");
  }

  function renderConditionalSpeed(profile, conditionalState) {
    const stateKey = conditionalStateKey(conditionalState);
    const mode = conditionalSpeedMode(conditionalState);
    const min = conditionalMovementSpeed(conditionalState.minMovementSpeed) || 1;
    const max = conditionalMovementSpeed(conditionalState.maxMovementSpeed) || (mode === "range" ? CONDITIONAL_MOVEMENT_SPEED_MAX : min);
    return `<div class="pv2-conditional-speed">
      <span><strong>Movement speed</strong><small>Match the resolved Chill speed before this conditional override: any, exact, or an inclusive range.</small></span>
      <label><span>Match</span><select class="field-control" data-condition-speed-mode data-profile-key="${escapeHtml(profileKey(profile))}" data-condition-state-key="${escapeHtml(stateKey)}"><option value="any" ${mode === "any" ? "selected" : ""}>Any</option><option value="exact" ${mode === "exact" ? "selected" : ""}>Exact</option><option value="range" ${mode === "range" ? "selected" : ""}>Range</option></select></label>
      ${mode !== "any" ? `<label><span>${mode === "exact" ? "Speed" : "Minimum"}</span><select class="field-control" data-condition-speed-min data-profile-key="${escapeHtml(profileKey(profile))}" data-condition-state-key="${escapeHtml(stateKey)}">${movementSpeedOptions(min)}</select></label>` : ""}
      ${mode === "range" ? `<label><span>Maximum</span><select class="field-control" data-condition-speed-max data-profile-key="${escapeHtml(profileKey(profile))}" data-condition-state-key="${escapeHtml(stateKey)}">${movementSpeedOptions(max)}</select></label>` : ""}
    </div>`;
  }

  function renderConditionsPanel(profile) {
    const states = conditionalStatesFor(profile);
    const configuredStates = states.map((conditionalState) => {
      const child = conditionalState.linkedConditionalProfile;
      const stateKey = conditionalStateKey(conditionalState);
      return `<li class="pv2-conditional-state-card"><header><span><strong>${escapeHtml(conditionalStateSummary(conditionalState))}</strong><small>${escapeHtml(child ? nameFor(child) : "Inherit")}</small></span><button type="button" data-action="remove-conditional-state" data-condition-state-key="${escapeHtml(stateKey)}">Remove state</button></header>${renderConditionalTerrainPolicy(profile, conditionalState)}${renderConditionalSpeed(profile, conditionalState)}</li>`;
    }).join("");
    return `<div class="pv2-state-profile-link pv2-condition-profile-link" data-profile-key="${escapeHtml(profileKey(profile))}">
      <div class="pv2-state-owned-value">
        <p><strong>Conditional states</strong><small>Add a state here. Its tab will then let you select an override profile.</small></p>
        ${configuredStates ? `<ul class="member-list pv2-member-list">${configuredStates}</ul>` : `<p class="pv2-linked-state-empty">No conditional states have been added.</p>`}
      </div>
      <div class="pv2-state-profile-picker" data-condition-add-row>
        <span><strong>Add conditional state</strong><small>Starts with Rooftop and Signpost accepted; adjust any tile or speed after adding.</small></span>
        <button type="button" data-action="add-conditional-state">Add state</button>
      </div>
    </div>`;
  }

  function renderConditionalLinkedProfile(parentProfile, section) {
    const child = section.linkedConditionalProfile;
    const references = conditionalProfileCandidates(parentProfile, child);
    const selectOptions = references.map((candidate) => {
      const key = profileKey(candidate);
      const order = ordersFor(candidate)[0];
      const suffix = Number.isFinite(order) ? ` · #${order}` : " · unsaved";
      const current = child && key === profileKey(child);
      return `<option value="${escapeHtml(key)}" ${current ? "selected" : ""}>${escapeHtml(nameFor(candidate))}${escapeHtml(suffix)}</option>`;
    }).join("");
    return `<div class="pv2-state-profile-link" data-profile-key="${escapeHtml(profileKey(parentProfile))}">
      <label class="pv2-state-profile-picker">
        <span><strong>Override profile</strong><small>Applied whenever ${escapeHtml(nameFor(parentProfile))} matches ${escapeHtml(section.conditionSummary)}.</small></span>
        <select class="field-control" data-condition-profile-reference data-current-child-key="${escapeHtml(child ? profileKey(child) : "")}" data-condition-state-key="${escapeHtml(section.conditionStateKey)}" data-condition-section-id="${escapeHtml(section.id)}" aria-label="${escapeHtml(`${section.title} override profile`)}">
          <option value="">Inherit</option>
          ${selectOptions}
        </select>
      </label>
      ${child ? `<div class="pv2-linked-chill-editor" data-linked-profile-key="${escapeHtml(profileKey(child))}">
        <header><span><strong>${escapeHtml(nameFor(child))} · Chill state</strong><small>These are the selected override profile's Chill values. Editing them updates that override everywhere it is referenced.</small></span><em>Linked globally</em></header>
        ${section.fields.length ? renderSectionContent(child, section) : `<p class="pv2-linked-state-empty">This override profile has no editable Chill fields.</p>`}
      </div>` : `<p class="pv2-linked-state-empty">Choose an override profile to author this conditional Chill state.</p>`}
    </div>`;
  }

  function lifecycleTabSummaryParts(profile, section) {
    if (section.conditionPanel) {
      const count = conditionalStatesFor(profile).length;
      return [{ field: "conditionMask", tabId: "", label: count ? `${count} state${count === 1 ? "" : "s"}` : "None", available: false }];
    }
    if (section.conditionalStatePanel) {
      return [{ field: "conditionalState", tabId: "", label: section.linkedConditionalProfile ? nameFor(section.linkedConditionalProfile) : "Inherit", available: false }];
    }
    const descriptors = LIFECYCLE_TAB_SUMMARY_FIELDS[section.id];
    if (!descriptors) return [];
    return descriptors.map(({ field, tabId, profileReference }) => {
      const raw = fieldRaw(profile, field);
      let label;
      if (profileReference && raw) {
        const linkedProfile = laneReferenceProfile(raw);
        label = linkedProfile ? nameFor(linkedProfile) : `Unavailable #${Number(raw) + 1}`;
      } else if (raw) {
        const option = fieldOptions(field, raw, profile).find((candidate) => valueRaw(candidate) === raw);
        label = valueLabel(option || raw);
      } else {
        label = isOverrideProfile(profile) ? "Inherit" : "Not set";
      }
      return {
        field,
        tabId,
        label,
        available: !profileReference && section.subtabs?.some((tab) => tab.id === tabId) && profileCanEditField(profile, field),
      };
    });
  }

  function renderLifecycleTabs(profile, sections, override) {
    if (!sections.length) return "";
    const storedSection = state.profileLifecycleSection;
    const preferred = sections.find((section) => section.id === storedSection)
      || sections.find((section) => section.id === "spawn")
      || sections[0];
    const tabs = sections.map((section) => {
      const selected = section.id === preferred.id;
      const count = sectionCountInfo(section, override);
      const label = section.title.replace(/ state$/i, "");
      const sectionProfile = section.linkedConditionalProfile || profile;
      const summarySection = section.conditionalStatePanel ? { ...section, id: "chill" } : section;
      const summaryParts = lifecycleTabSummaryParts(sectionProfile, summarySection);
      const summary = summaryParts.map((part) => part.label).join(" / ");
      const summaryNav = summaryParts.length ? `<span class="pv2-lifecycle-summary-nav" role="group" aria-label="${escapeHtml(`${section.title} shortcuts`)}">${summaryParts.map((part, index) => `${index ? `<i aria-hidden="true">/</i>` : ""}${part.available
        ? `<button type="button" tabindex="${selected ? "0" : "-1"}" data-action="select-lifecycle-mode" data-lifecycle-section="${escapeHtml(section.id)}" data-mode-target="${escapeHtml(part.tabId)}" aria-label="${escapeHtml(`Open ${section.title} ${part.tabId === "behavior" ? "Behavior" : "Movement style"} options (${part.label})`)}">${escapeHtml(part.label)}</button>`
        : `<span>${escapeHtml(part.label)}</span>`}`).join("")}</span>` : "";
      return `<div class="pv2-lifecycle-tab-shell${selected ? " is-selected" : ""}" data-lifecycle-theme="${escapeHtml(section.id)}" role="presentation"><button class="pv2-lifecycle-tab" type="button" role="tab" id="pv2-lifecycle-tab-${escapeHtml(section.id)}" aria-controls="pv2-lifecycle-panel-${escapeHtml(section.id)}" aria-selected="${selected}" aria-label="${escapeHtml([section.title, summary, count.spoken].filter(Boolean).join(", "))}" tabindex="${selected ? "0" : "-1"}" data-action="select-lifecycle-tab" data-lifecycle-tab="${escapeHtml(section.id)}"><span aria-hidden="true"><strong>${escapeHtml(label)}</strong></span><em aria-hidden="true">${escapeHtml(count.compact)}</em></button>${summaryNav}</div>`;
    }).join("");
    const panels = sections.map((section) => {
      const selected = section.id === preferred.id;
      const sectionProfile = section.linkedConditionalProfile || profile;
      const body = section.conditionPanel
        ? renderConditionsPanel(profile)
        : (section.conditionalStatePanel
          ? renderConditionalLinkedProfile(profile, section)
          : (section.stateProfileField ? renderStateProfileReference(profile, section) : renderSectionContent(profile, section)));
      return `<section class="pv2-lifecycle-tabpanel" role="tabpanel" id="pv2-lifecycle-panel-${escapeHtml(section.id)}" aria-labelledby="pv2-lifecycle-tab-${escapeHtml(section.id)}" data-section-id="${escapeHtml(section.id)}" ${selected ? "" : "hidden"}>
        ${selected ? `<p class="pv2-lifecycle-hint">${escapeHtml(section.hint)}</p>${override && !section.conditionPanel && section.linkedConditionalProfile ? renderSectionToolbar(section, sectionProfile) : (!section.conditionalStatePanel && override && !section.conditionPanel ? renderSectionToolbar(section, sectionProfile) : "")}<div class="profile-fields pv2-field-hierarchy">${body}</div>` : ""}
      </section>`;
    }).join("");
    return `<div class="pv2-lifecycle-workspace"><div class="pv2-lifecycle-tabs" role="tablist" aria-label="Profile lifecycle" style="--lifecycle-tab-count:${sections.length}">${tabs}</div>${panels}</div>`;
  }

  function renderFieldSections(profile) {
    const override = isOverrideProfile(profile);
    const sections = FIELD_SECTIONS.map((section) => {
      const fields = sectionFields(section, profile);
      return { ...section, fields, overrideCount: fields.filter((field) => sectionFieldRaw(section, profile, field)).length };
    });
    const other = unsectionedFields(profile);
    if (other.length) sections.push({
      id: "advanced",
      title: "Advanced",
      hint: "Additional engine-level controls.",
      fields: other,
      overrideCount: other.filter((field) => fieldRaw(profile, field)).length,
    });
    const visibleSections = sections.filter((section) => section.fields.length);
    const lifecycleSections = LIFECYCLE_SECTION_IDS
      .map((id) => visibleSections.find((section) => section.id === id))
      .filter(Boolean);
    if (normalConditionalProfile(profile)) {
      const conditionCount = conditionalStatesFor(profile).length;
      lifecycleSections.unshift({
        id: CONDITIONS_LIFECYCLE_SECTION_ID,
        title: "Conditions",
        hint: "Add and remove conditional states for this profile.",
        fields: [],
        overrideCount: conditionCount,
        conditionPanel: true,
      });
    }
    const chillSection = FIELD_SECTIONS.find((section) => section.id === "chill");
    if (chillSection) {
      conditionalStatesFor(profile).forEach((conditionalState) => {
        const child = conditionalState.linkedConditionalProfile;
        const fields = child ? sectionFields(chillSection, child) : [];
        const conditionTitle = conditionalStateSummary(conditionalState);
        const baseId = conditionalLifecycleBaseId(conditionalState);
        lifecycleSections.push({
          ...chillSection,
          id: baseId,
          title: conditionTitle,
          hint: child
            ? `Conditional Chill state using the separate ${nameFor(child)} override profile.`
            : "Choose the override profile used by this conditional state.",
          fields,
          overrideCount: child ? fields.filter((field) => sectionFieldRaw(chillSection, child, field)).length : 0,
          sourceSectionId: "chill",
          linkedConditionalProfile: child,
          conditionalStatePanel: true,
          conditionStateKey: conditionalStateKey(conditionalState),
          conditionSummary: conditionTitle,
        });
      });
    }
    const secondarySections = visibleSections.filter((section) => !LIFECYCLE_SECTION_ID_SET.has(section.id));
    const rendered = [
      renderLifecycleTabs(profile, lifecycleSections, override),
      ...secondarySections.map((section) => renderAccordionSection(profile, section, override)),
    ].filter(Boolean).join("");
    return rendered || `<p class="empty-state empty-state--small">No editable fields are available for this profile.</p>`;
  }

  function sectionNavigationTarget(sectionId) {
    if (!sectionId) return null;
    if (LIFECYCLE_SECTION_ID_SET.has(sectionId)
        || sectionId === CONDITIONS_LIFECYCLE_SECTION_ID
        || sectionId.startsWith(CONDITIONAL_LIFECYCLE_SECTION_PREFIX)) {
      return editorElement.querySelector(`[data-lifecycle-tab="${CSS.escape(sectionId)}"]`);
    }
    return editorElement.querySelector(`details[data-section-id="${CSS.escape(sectionId)}"] > summary`);
  }

  function focusSectionNavigation(sectionId) {
    const target = sectionNavigationTarget(sectionId);
    target?.focus({ preventScroll: true });
    if (target?.matches("[data-lifecycle-tab]")) target.scrollIntoView({ block: "nearest", inline: "nearest" });
  }

  function selectLifecycleTab(sectionId, focus = true) {
    if (!LIFECYCLE_SECTION_ID_SET.has(sectionId)
        && sectionId !== CONDITIONS_LIFECYCLE_SECTION_ID
        && !sectionId.startsWith(CONDITIONAL_LIFECYCLE_SECTION_PREFIX)) return;
    if (!findProfile()) return;
    state.profileLifecycleSection = sectionId;
    renderEditor();
    if (focus) focusSectionNavigation(sectionId);
  }

  function selectModeTab(sectionId, tabId, focus = true) {
    const profile = findProfile();
    const section = FIELD_SECTIONS.find((candidate) => candidate.id === sectionId)
      || (sectionId.endsWith("-linked-chill")
        || sectionId.startsWith(CONDITIONAL_LIFECYCLE_SECTION_PREFIX)
        ? FIELD_SECTIONS.find((candidate) => candidate.id === "chill")
        : null);
    if (!profile || !section?.subtabs?.some((tab) => tab.id === tabId)) return;
    branchTabSelections.set(sectionId, tabId);
    renderEditor();
    if (focus) {
      editorElement.querySelector(`[data-mode-tab-section="${CSS.escape(sectionId)}"][data-mode-tab="${CSS.escape(tabId)}"]`)?.focus({ preventScroll: true });
    }
  }

  function selectLifecycleMode(sectionId, tabId, focus = true) {
    if (!LIFECYCLE_SECTION_ID_SET.has(sectionId)
        && !sectionId.startsWith(CONDITIONAL_LIFECYCLE_SECTION_PREFIX)) return;
    const profile = findProfile();
    const section = FIELD_SECTIONS.find((candidate) => candidate.id === sectionId)
      || (sectionId.startsWith(CONDITIONAL_LIFECYCLE_SECTION_PREFIX)
        ? FIELD_SECTIONS.find((candidate) => candidate.id === "chill")
        : null);
    if (!profile || !section?.subtabs?.some((tab) => tab.id === tabId)) return;
    state.profileLifecycleSection = sectionId;
    branchTabSelections.set(sectionId, tabId);
    renderEditor();
    if (focus) {
      const target = editorElement.querySelector(`[data-mode-tab-section="${CSS.escape(sectionId)}"][data-mode-tab="${CSS.escape(tabId)}"]`);
      if (target) {
        target.focus({ preventScroll: true });
        target.scrollIntoView({ block: "nearest", inline: "nearest" });
      } else {
        focusSectionNavigation(sectionId);
      }
    }
  }

  function matchSuggestions(field) {
    const existing = data.classes.map((profile) => valueRaw(profile.match?.[field])).filter(Boolean);
    if (field === "species") return unique([DEFAULT_MATCH.species, ...data.assignments.map((item) => item?.species?.symbol), ...existing]);
    if (field === "terrain") return unique([DEFAULT_MATCH.terrain, ...Object.values(data.labels?.terrains || {}).map((item) => item.symbol), ...existing]);
    if (field === "groupMask") return unique([
      DEFAULT_MATCH.groupMask,
      ...Object.values(data.labels?.groups || {}).map((item) => item.symbol),
      ...(data.typeOptions || []).map((type) => typeGroupSymbol(type.symbol)),
      ...existing,
    ]);
    if (field === "behaviorClass") return unique([DEFAULT_MATCH.behaviorClass, ...baseProfiles().map((profile) => profile.symbol), ...existing]);
    if (field === "shiny") return unique([DEFAULT_MATCH.shiny, "0", "1", ...existing]);
    return unique([DEFAULT_MATCH[field], ...Array.from({ length: 101 }, (_, index) => String(index)), ...existing]);
  }

  function isAnyMatchValue(field, raw) {
    return raw === DEFAULT_MATCH[field]
      || (["minLevel", "maxLevel"].includes(field) && String(raw) === "0")
      || (field === "groupMask" && raw === "OW_WILD_BEHAVIOR_GROUP_NONE");
  }

  function matchErrors(match, allowGlobal = false) {
    const errors = [];
    const allowed = new Map(MATCH_FIELDS.map(([field]) => [field, new Set(matchSuggestions(field))]));
    MATCH_FIELDS.forEach(([field, label]) => {
      const raw = String(match?.[field] || "");
      const numeric = ["minLevel", "maxLevel"].includes(field) && /^\d+$/.test(raw);
      if (!raw || (!allowed.get(field).has(raw) && !numeric)) errors.push(`${label} has an unknown value`);
      if (numeric && Number(raw) > 100) errors.push(`${label} must be between 0 and 100`);
    });
    const min = isAnyMatchValue("minLevel", match.minLevel) ? null : Number(match.minLevel);
    const max = isAnyMatchValue("maxLevel", match.maxLevel) ? null : Number(match.maxLevel);
    if (Number.isFinite(min) && Number.isFinite(max) && min > max) errors.push("Minimum level is greater than maximum level");
    if (!allowGlobal && MATCH_FIELDS.every(([field]) => isAnyMatchValue(field, match[field]))) {
      errors.push("All-Pokémon targeting requires at least one shared condition");
    }
    return errors;
  }

  function profileValidationErrors() {
    const baseKeys = new Set(baseProfiles().map(profileKey));
    const overrideKeys = new Set(savedOverrideProfiles().map(profileKey));
    const speciesSymbols = new Set(data.assignments.map((item) => item.species?.symbol).filter(Boolean));
    const errors = [];
    if (invalidNumericOperatorInputs.size) errors.push("Finish entering every numeric override operator before saving");
    for (const key of drafts.baseFields.keys()) {
      if (!baseKeys.has(key)) errors.push(`A drafted base profile no longer exists in the latest source (${key})`);
    }
    for (const store of [drafts.overrideFields, drafts.overrideNames, drafts.overrideTargets]) {
      for (const key of store.keys()) {
        if (!overrideKeys.has(key)) errors.push(`A drafted override profile no longer exists in the latest source (${key})`);
      }
    }
    for (const key of drafts.removedOverrides) {
      if (!overrideKeys.has(key)) errors.push(`A drafted override removal no longer matches the latest source (${key})`);
    }
    for (const [species, target] of drafts.memberships) {
      if (!speciesSymbols.has(species)) errors.push(`A drafted profile member no longer exists in the latest source (${species})`);
      if (!baseKeys.has(target)) errors.push(`A drafted membership target no longer exists in the latest source (${target})`);
    }
    for (const key of drafts.overrideOrder) {
      if (!overrideKeys.has(key)) errors.push(`A reordered override profile no longer exists in the latest source (${key})`);
    }
    allProfiles().forEach((profile) => {
      if (drafts.removedOverrides.has(profileKey(profile))) return;
      ["activeProfile", "tiredProfile"].forEach((fieldKey) => {
        if (!profileCanEditField(profile, fieldKey)) return;
        const raw = fieldRaw(profile, fieldKey);
        if (raw && !laneReferenceProfile(raw)) {
          errors.push(`${nameFor(profile)} — ${fieldKey === "activeProfile" ? "Active" : "Tired"} override profile #${Number(raw) + 1} is unavailable`);
        }
      });
    });
    allProfiles().forEach((profile) => {
      if (!profile.draftId && !fieldDraftMap(profile)?.size) return;
      const editedFields = profile.draftId
        ? new Map(Object.entries(profile.fields || {}))
        : (fieldDraftMap(profile) || new Map());
      editedFields.forEach((raw, fieldKey) => {
        const operator = parseNumericOverrideRaw(raw);
        if (!operator) return;
        const options = fieldOptions(fieldKey, raw, profile, {});
        for (const operation of operator.operations) {
          if (!numericOverrideAllowed(profile, fieldKey, operation.kind)) {
            errors.push(`${nameFor(profile)} — ${fieldLabelForProfile(profile, fieldKey)} cannot use numeric override operators`);
            break;
          }
          const bounds = numericOverrideOperandBounds(fieldKey, options, operation.kind);
          if (!Number.isInteger(operation.operand) || operation.operand < bounds.min || operation.operand > bounds.max) {
            errors.push(`${nameFor(profile)} — ${fieldLabelForProfile(profile, fieldKey)} ${operation.kind === "adjust" ? "adjustment" : "bound"} must be between ${bounds.min} and ${bounds.max}`);
            break;
          }
        }
      });
      PROFILE_FIELD_RANGES.forEach((range) => {
        const error = profileFieldRangeError(profile, range);
        if (error) errors.push(`${nameFor(profile)} — ${error}`);
      });
      if (!canUseRamLocomotion(profile)) return;
      const raw = fieldRaw(profile, "ramMaxSpeed");
      if (isNumericOverrideRaw(raw)) return;
      const option = (data.editOptions?.ramMaxSpeed || []).find((candidate) => valueRaw(candidate) === raw);
      const numeric = Number(option?.value ?? raw);
      if (Number.isFinite(numeric) && numeric > 4) errors.push(`${nameFor(profile)} RAM max speed must be between 0 and 4`);
    });
    const seenNames = new Set();
    const activeOverrides = overrideProfiles().filter((profile) => !drafts.removedOverrides.has(profileKey(profile)));
    if (!activeOverrides.length) errors.push("Create a replacement before removing the last override profile");
    if (activeOverrides.length > 32) errors.push("The runtime supports at most 32 ordered override profiles");
    activeOverrides.forEach((profile) => {
      const name = nameFor(profile).trim().toLowerCase();
      if (!name || seenNames.has(name)) errors.push("Override profile names must be unique");
      seenNames.add(name);
      const target = targetFor(profile);
      const shouldValidateTarget = profile.draftId || drafts.overrideTargets.has(profileKey(profile));
      if (!shouldValidateTarget) return;
      if (target.targetMode === "members" && !target.members.length) errors.push(`${nameFor(profile)} needs at least one member`);
      const knownSpecies = new Set(speciesEntries().map((species) => species.symbol));
      if (target.members.some((symbol) => !knownSpecies.has(symbol))) errors.push(`${nameFor(profile)} contains an unknown Pokémon member`);
      errors.push(...matchErrors(target.match, target.targetMode !== "all"));
    });
    const seenConditionalStates = new Set();
    currentConditionalStates().forEach((conditionalState) => {
      const parent = findProfile(conditionalState.parentKey);
      const linked = conditionalState.overrideKey ? findProfile(conditionalState.overrideKey) : null;
      const allTerrainBits = terrainPolicyAllMask();
      const explicit = Number(valueRaw(conditionalState.terrainOverrideMask));
      const accepted = Number(valueRaw(conditionalState.terrainMask));
      const minSpeed = conditionalMovementSpeed(conditionalState.minMovementSpeed);
      const maxSpeed = conditionalMovementSpeed(conditionalState.maxMovementSpeed);
      const signature = `${conditionalState.parentKey}:${conditionalStateKey(conditionalState)}`;
      if (!parent || !normalConditionalProfile(parent)) errors.push("A conditional state has an unavailable parent override profile");
      if (conditionalState.overrideKey && (!linked || !normalConditionalProfile(linked))) errors.push(`${nameFor(parent) || "A conditional state"} has an unavailable override profile`);
      if (!Number.isInteger(explicit) || explicit < 0 || explicit & ~allTerrainBits
          || !Number.isInteger(accepted) || accepted < 0 || accepted & ~allTerrainBits || accepted & ~explicit) {
        errors.push(`${nameFor(parent) || "A conditional state"} has an invalid tile condition`);
      }
      if ((!minSpeed && maxSpeed) || (minSpeed && !maxSpeed) || minSpeed > maxSpeed) errors.push(`${nameFor(parent) || "A conditional state"} has an invalid movement speed range`);
      if (!explicit && !minSpeed && !maxSpeed) errors.push(`${nameFor(parent) || "A conditional state"} needs at least one tile or movement speed condition`);
      if (seenConditionalStates.has(signature)) errors.push(`${nameFor(parent) || "A profile"} has the same conditional state more than once`);
      seenConditionalStates.add(signature);
    });
    return unique(errors);
  }

  function staleDraftEntries() {
    const baseKeys = new Set(baseProfiles().map(profileKey));
    const overrideKeys = new Set(savedOverrideProfiles().map(profileKey));
    const speciesSymbols = new Set(data.assignments.map((item) => item.species?.symbol).filter(Boolean));
    const entries = new Map();
    const addProfile = (key, kind) => entries.set(`profile|${key}`, {
      id: `profile|${key}`,
      label: String(key).replace(/^(?:base|override:name|override:profile):/, ""),
      detail: `${kind} profile no longer exists in the latest source`,
    });
    for (const key of drafts.baseFields.keys()) if (!baseKeys.has(key)) addProfile(key, "Base");
    for (const store of [drafts.overrideFields, drafts.overrideNames, drafts.overrideTargets]) {
      for (const key of store.keys()) if (!overrideKeys.has(key)) addProfile(key, "Override");
    }
    for (const key of drafts.removedOverrides) if (!overrideKeys.has(key)) addProfile(key, "Override");
    for (const [species, target] of drafts.memberships) {
      if (!speciesSymbols.has(species) || !baseKeys.has(target)) entries.set(`membership|${species}`, {
        id: `membership|${species}`,
        label: humanizeRaw(species),
        detail: !speciesSymbols.has(species) ? "Pokémon no longer exists in the latest source" : "Membership target no longer exists in the latest source",
      });
    }
    for (const key of drafts.overrideOrder) {
      if (!overrideKeys.has(key)) entries.set(`order|${key}`, {
        id: `order|${key}`,
        label: String(key).replace(/^(?:override:name|override:profile):/, ""),
        detail: "Reordered override no longer exists in the latest source",
      });
    }
    return [...entries.values()];
  }

  function renderStaleDraftRecovery() {
    const entries = staleDraftEntries();
    if (!entries.length) return "";
    return `<section class="pv2-stale-drafts" data-stale-drafts tabindex="-1" aria-labelledby="pv2-stale-drafts-title">
      <header><div><p class="eyebrow">Preserved draft recovery</p><h3 id="pv2-stale-drafts-title">Unmatched edits</h3></div><span>${entries.length}</span></header>
      <p>These edits no longer have a source target. They remain untouched until you discard them individually.</p>
      <ul>${entries.map((entry) => `<li><span><strong>${escapeHtml(entry.label)}</strong><small>${escapeHtml(entry.detail)}</small></span><button class="is-danger" type="button" data-action="discard-stale-draft" data-stale-draft-id="${escapeHtml(entry.id)}">Discard this edit</button></li>`).join("")}</ul>
    </section>`;
  }

  async function discardStaleDraft(id) {
    const [kind, ...parts] = String(id || "").split("|");
    const key = parts.join("|");
    if (!kind || !key || !staleDraftEntries().some((entry) => entry.id === id)) return;
    const confirmed = await askConfirmation("Discard only this unmatched draft edit? All other pending edits will remain.", {
      title: "Discard unmatched edit?",
      confirmLabel: "Discard this edit",
      dangerous: true,
    });
    if (!confirmed) return;
    if (kind === "profile") dropProfileDraft(key);
    else if (kind === "membership") drafts.memberships.delete(key);
    else if (kind === "order") drafts.overrideOrder = drafts.overrideOrder.filter((item) => item !== key);
    renderAll();
    announce("Unmatched draft edit discarded. Other pending edits remain.");
  }

  function renderTargetBuilder(profile, mode = "override") {
    const kind = ui.targetKind;
    const value = normalizedTargetValue(kind);
    ui.targetValue = value;
    const candidates = targetCandidates(kind, value);
    const targetOptionsHtml = targetOptions(kind).map((option) => `
      <option value="${escapeHtml(option.value)}" ${option.value === value ? "selected" : ""}>${escapeHtml(option.label)}</option>`).join("");
    const assignable = mode === "base"
      ? candidates.filter((species) => pendingBaseKeyForSpecies(species.symbol) !== profileKey(profile))
      : candidates.filter((species) => !targetFor(profile).members.includes(species.symbol));
    const canApply = assignable.length > 0;
    const preview = candidates.slice(0, 14).map((species) => species.iconUrl
      ? `<img src="${escapeHtml(species.iconUrl)}" alt="${escapeHtml(species.name)}" loading="lazy">`
      : `<span>${escapeHtml(species.name?.slice(0, 1) || "?")}</span>`).join("");
    return `
      <section class="pv2-target-builder" aria-label="${mode === "base" ? "Assign profile members" : "Add override members"}">
        <header><div><strong>${mode === "base" ? "Assign a target set" : "Add Pokémon to this profile"}</strong><small>${mode === "base" ? "Move matching Pokémon into this base profile." : "Shortcuts expand to explicit members of this single override layer."}</small></div><em>${assignable.length} available</em></header>
        <div class="pv2-target-controls">
          <label><span>Target kind</span><select data-target-kind>${TARGET_KINDS.map(([key, label]) => `<option value="${key}" ${key === kind ? "selected" : ""}>${label}</option>`).join("")}</select></label>
          <label><span>Target</span><select data-target-value>${targetOptionsHtml}</select></label>
          <button type="button" data-action="add-target" ${canApply ? "" : "disabled"}>${mode === "base" ? `Assign ${assignable.length}` : `Add ${assignable.length}`}</button>
        </div>
        <div class="pv2-target-preview" aria-label="Target preview">${preview || `<small>No Pokémon match this target.</small>`}${candidates.length > 14 ? `<b>+${candidates.length - 14}</b>` : ""}</div>
      </section>`;
  }

  function addTarget(profile) {
    const kind = ui.targetKind;
    const value = normalizedTargetValue(kind);
    if (!value) return;
    if (isOverrideProfile(profile)) {
      const target = targetFor(profile);
      const additions = targetCandidates(kind, value).map((species) => species.symbol);
      const previousCount = target.members.length;
      target.members = unique([...target.members, ...additions]);
      if (target.targetMode === "disabled" && target.members.length) target.targetMode = "members";
      setTarget(profile, target);
      ui.openSections.add("override-target");
      status(`Added ${target.members.length - previousCount} member${target.members.length - previousCount === 1 ? "" : "s"} to ${nameFor(profile)}.`, "warning");
    } else {
      const candidates = targetCandidates(kind, value)
        .filter((species) => pendingBaseKeyForSpecies(species.symbol) !== profileKey(profile));
      candidates.forEach((species) => setMembership(species.symbol, profile));
      status(`Assigned ${candidates.length} Pokémon to ${nameFor(profile)}.`, "warning");
    }
    renderEditor();
    renderList();
    signalDirty();
  }

  function renderOverrideTarget(profile) {
    const target = targetFor(profile);
    const expanded = ui.openSections.has("override-target");
    const conditionFields = MATCH_FIELDS.filter(([field]) => !["species", "minLevel", "maxLevel"].includes(field));
    const levelFields = MATCH_FIELDS.filter(([field]) => ["minLevel", "maxLevel"].includes(field));
    const datalists = [...conditionFields, ...levelFields].map(([field]) => `
      <datalist id="pv2-match-${escapeHtml(field)}">${matchSuggestions(field).map((raw) => `<option value="${escapeHtml(raw)}">${escapeHtml(humanizeRaw(raw))}</option>`).join("")}</datalist>`).join("");
    const query = ui.memberQuery.trim().toLowerCase();
    const bySymbol = new Map(speciesEntries().map((species) => [species.symbol, species]));
    const members = target.members.map((symbol) => bySymbol.get(symbol) || { symbol, name: humanizeRaw(symbol) });
    const visibleMembers = members.filter((species) => !query || [
      species.name,
      species.symbol,
      species.familyBaseName,
      ...(species.types || []).flatMap((type) => [type.name, type.symbol]),
    ].filter(Boolean).join(" ").toLowerCase().includes(query)).slice(0, 160);
    const modeLabel = target.targetMode === "all" ? "All matching Pokémon" : (target.targetMode === "disabled" ? "Disabled" : `${members.length} members`);
    const conditionErrors = matchErrors(target.match, target.targetMode !== "all");
    const minimumLevel = isAnyMatchValue("minLevel", target.match.minLevel) ? null : Number(target.match.minLevel);
    const maximumLevel = isAnyMatchValue("maxLevel", target.match.maxLevel) ? null : Number(target.match.maxLevel);
    const levelRangeError = Number.isFinite(minimumLevel) && Number.isFinite(maximumLevel) && minimumLevel > maximumLevel
      ? "Minimum level is greater than maximum level"
      : "";
    const levelRangeErrorId = `pv2-level-range-error-${profileKey(profile).replace(/[^a-zA-Z0-9_-]/g, "-")}`;
    return `
      <details class="membership-section pv2-membership pv2-override-target" data-section-id="override-target" ${expanded ? "open" : ""}>
        <summary><span><strong>Members</strong><small>One member set, evaluated as one override layer.</small></span><em>${escapeHtml(modeLabel)}</em></summary>
        ${expanded ? `<div class="pv2-override-target-body">
          ${renderTargetBuilder(profile, "override")}
          <div class="pv2-target-mode">
            <label><span>Target mode</span><select data-target-mode>
              <option value="disabled" ${target.targetMode === "disabled" ? "selected" : ""}>Disabled</option>
              <option value="members" ${target.targetMode === "members" ? "selected" : ""}>Explicit members</option>
              <option value="all" ${target.targetMode === "all" ? "selected" : ""}>All Pokémon matching shared conditions</option>
            </select></label>
            <small>Changing modes never creates additional backend rules.</small>
          </div>
          ${target.targetMode === "all" ? `<p class="pv2-member-note">This profile targets every Pokémon that passes the shared conditions below. Saved members are retained if you switch back.</p>` : `
            <label class="pv2-member-search"><span>Find current members</span><input type="search" value="${escapeHtml(ui.memberQuery)}" data-member-search placeholder="Name, symbol, family, or type"></label>
            <ul class="member-list pv2-member-list">
              ${visibleMembers.map((species) => `<li><span>${species.iconUrl ? `<img src="${escapeHtml(species.iconUrl)}" alt="" loading="lazy">` : ""}<strong>${escapeHtml(species.name)}</strong><small>${escapeHtml(species.symbol)}</small></span><button type="button" data-action="remove-override-member" data-species="${escapeHtml(species.symbol)}">Remove</button></li>`).join("") || `<li class="empty-state empty-state--small">${members.length ? "No members match this search." : "No members yet. Add Pokémon above to activate member targeting."}</li>`}
            </ul>
            ${members.length > visibleMembers.length ? `<p class="pv2-member-note">Showing ${visibleMembers.length} of ${members.length}. Search to narrow this list.</p>` : ""}
          `}
          <details class="pv2-shared-conditions${conditionErrors.length ? " is-invalid" : ""}" data-section-id="override-conditions" ${ui.openSections.has("override-conditions") || conditionErrors.length ? "open" : ""}>
            <summary><span><strong>Shared conditions</strong><small>These conditions are checked once, together with membership.</small></span><em>${conditionErrors.length ? "Needs attention" : "Optional"}</em></summary>
            <div class="match-grid pv2-match-grid">
              ${conditionFields.slice(0, 2).map(([field, label]) => `<label><span>${escapeHtml(label)}</span><input data-target-condition="${field}" list="pv2-match-${field}" value="${escapeHtml(target.match[field])}" autocomplete="off"></label>`).join("")}
              <fieldset class="pv2-match-range${levelRangeError ? " is-invalid" : ""}">
                <legend><span>Level range</span><small>levels</small></legend>
                <span class="pv2-match-range-controls">
                  ${levelFields.map(([field]) => `<label><span>${field === "minLevel" ? "Min" : "Max"}</span><input data-target-condition="${field}" list="pv2-match-${field}" value="${escapeHtml(target.match[field])}" autocomplete="off" aria-label="${field === "minLevel" ? "Minimum level" : "Maximum level"}" aria-invalid="${Boolean(levelRangeError)}"${levelRangeError ? ` aria-describedby="${escapeHtml(levelRangeErrorId)}"` : ""}></label>`).join("")}
                </span>
                ${levelRangeError ? `<span id="${escapeHtml(levelRangeErrorId)}" class="sr-only">${escapeHtml(levelRangeError)}</span>` : ""}
              </fieldset>
              ${conditionFields.slice(2).map(([field, label]) => `<label><span>${escapeHtml(label)}</span><input data-target-condition="${field}" list="pv2-match-${field}" value="${escapeHtml(target.match[field])}" autocomplete="off"></label>`).join("")}
            </div>
            ${conditionErrors.length ? `<p class="pv2-condition-error">${escapeHtml(conditionErrors[0])}</p>` : `<p class="pv2-member-note">Conditions use AND logic. They narrow this one profile; they do not become separate rules.</p>`}
          </details>
          ${datalists}
        </div>` : ""}
      </details>`;
  }

  function renderMembershipManager(profile) {
    const members = membersFor(profile);
    const isDefault = String(profile.index) === String(data.defaultClassIndex);
    const expanded = ui.openSections.has("member-list");
    const query = ui.memberQuery.trim().toLowerCase();
    const visibleMembers = members.filter((assignment) => !query || [
      assignment.species?.name,
      assignment.species?.symbol,
      assignment.species?.familyBaseName,
      ...(assignment.species?.types || []).flatMap((type) => [type.name, type.symbol]),
    ].filter(Boolean).join(" ").toLowerCase().includes(query)).slice(0, 160);
    return `
      <details class="pv2-member-manager" data-section-id="member-list" ${expanded ? "open" : ""}>
        <summary><span><strong>Manage assigned Pokémon</strong><small>Search or move individual Pokémon back to Default.</small></span><em>${members.length}</em></summary>
        ${expanded ? `
        <label class="pv2-member-search"><span>Find current members</span><input type="search" value="${escapeHtml(ui.memberQuery)}" data-member-search placeholder="Name, symbol, family, or type"></label>
        <ul class="member-list pv2-member-list">
          ${visibleMembers.map((assignment) => `<li><span>${assignment.species?.iconUrl ? `<img src="${escapeHtml(assignment.species.iconUrl)}" alt="" loading="lazy">` : ""}<strong>${escapeHtml(assignment.species?.name)}</strong><small>${escapeHtml(assignment.species?.symbol)}</small></span><button type="button" data-action="remove-member" data-species="${escapeHtml(assignment.species?.symbol)}" ${isDefault ? "disabled title=\"Default members cannot be unassigned\"" : ""}>${isDefault ? "Default" : "Move to Default"}</button></li>`).join("") || `<li class="empty-state empty-state--small">No members match this search.</li>`}
        </ul>
        ${members.length > visibleMembers.length ? `<p class="pv2-member-note">Showing ${visibleMembers.length} of ${members.length}. Search to narrow this list.</p>` : ""}
        ` : ""}
      </details>`;
  }

  function renderMembershipControl(profile) {
    const members = membersFor(profile);
    const expanded = ui.openSections.has("membership");
    const label = `Assign Pokémon — ${members.length} assigned`;
    return `
      <details class="pv2-member-control" data-section-id="membership" ${expanded ? "open" : ""}>
        <summary aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}"><span aria-hidden="true">+</span><span class="sr-only">${escapeHtml(label)}</span></summary>
        ${expanded ? `<div class="pv2-member-popover">
          ${renderTargetBuilder(profile, "base")}
          ${renderMembershipManager(profile)}
        </div>` : ""}
      </details>`;
  }

  function renderAffected(profile) {
    const affected = potentialAssignmentsFor(profile);
    const expanded = ui.openSections.has("affected");
    return `
      <details class="membership-section pv2-affected" data-section-id="affected" ${expanded ? "open" : ""}>
        <summary><span><strong>Potential coverage</strong><small>Pokémon that can match this one layer in at least one valid context.</small></span><em>${affected.length}</em></summary>
        ${expanded ? `<ul class="member-list pv2-member-list">
          ${affected.slice(0, 160).map((assignment) => `<li><span>${assignment.species?.iconUrl ? `<img src="${escapeHtml(assignment.species.iconUrl)}" alt="" loading="lazy">` : ""}<strong>${escapeHtml(assignment.species?.name)}</strong><small>${escapeHtml(assignment.species?.symbol)}</small></span><button type="button" data-action="inspect-species" data-species="${escapeHtml(assignment.species?.symbol)}">Resolve match</button></li>`).join("") || `<li class="empty-state empty-state--small">No Pokémon can currently match this layer.</li>`}
        </ul>${affected.length > 160 ? `<p class="pv2-member-note">Showing the first 160 of ${affected.length} possible Pokémon.</p>` : ""}` : ""}
      </details>`;
  }

  function renderResolvedContextIndicator() {
    if (!ui.contextResult) return "";
    const speciesName = data.assignments.find((assignment) => assignment.species?.symbol === ui.context.species)?.species?.name
      || ui.contextResult.context?.species?.name
      || humanizeRaw(ui.context.species);
    const terrainName = Object.values(data.labels?.terrains || {}).find((terrain) => terrain.symbol === ui.context.terrain)?.name
      || humanizeRaw(ui.context.terrain);
    const label = `${speciesName} · ${terrainName} · Lv ${ui.context.level}`;
    return `<div class="pv2-context-indicator"><span><strong>Resolved context active</strong><small>${escapeHtml(label)}</small></span><button type="button" data-action="open-context-resolver">Review</button></div>`;
  }

  function renderEditor() {
    // Any editor rerender discards transient, invalid number text. Valid values
    // have already been copied into the draft by the input handler.
    invalidNumericOperatorInputs.clear();
    const profile = findProfile();
    if (!profile) {
      editorElement.innerHTML = `${renderStaleDraftRecovery()}<div class="empty-state"><span class="empty-state__glyph" aria-hidden="true">◇</span><h2>Select a profile</h2><p>Choose a base or override profile from the library.</p></div>`;
      return;
    }
    const key = profileKey(profile);
    const override = isOverrideProfile(profile);
    const removed = drafts.removedOverrides.has(key);
    const headerSpecies = profilePreviewSpecies(profile, override, 20);
    const headerIcons = headerSpecies.length || !override ? `
      <div class="pv2-editor-icons">
        ${override ? "" : renderMembershipControl(profile)}
        ${headerSpecies.map((species) => `<button type="button" data-action="open-pokemon" data-species="${escapeHtml(species.symbol)}" aria-label="Open ${escapeHtml(species.name)} in Pokémon Editor"><img src="${escapeHtml(species.iconUrl)}" alt="" width="20" height="20" decoding="async" draggable="false"></button>`).join("")}
      </div>` : "";
    const actions = `
      ${!override && String(profile.index) !== String(data.defaultClassIndex) ? `<button type="button" data-action="convert-base-to-override" data-profile-key="${escapeHtml(key)}">Make override</button>` : ""}
      <button type="button" data-action="rename-profile" data-profile-key="${escapeHtml(key)}" ${profile.canRename === false ? "disabled" : ""}>Rename</button>
      <button type="button" data-action="duplicate-profile" data-profile-key="${escapeHtml(key)}">Duplicate</button>
      <button class="is-danger" type="button" data-action="delete-profile" data-profile-key="${escapeHtml(key)}" ${profile.canDelete === false ? "disabled" : ""}>${removed ? "Undo removal" : "Delete"}</button>`;
    editorElement.innerHTML = `
      ${renderStaleDraftRecovery()}
      <header class="inspector-header v2-inspector-header pv2-editor-head">
        <div class="pv2-editor-identity">
          <div class="pv2-editor-title-copy"><p class="eyebrow">${override ? "Ordered override" : "Base profile"}</p><h2>${escapeHtml(nameFor(profile))}</h2><p>${escapeHtml(profile.symbol || "New unsaved override")}</p></div>
          ${headerIcons}
        </div>
        <div class="inspector-actions pv2-editor-actions">${actions}</div>
      </header>
      ${renderResolvedContextIndicator()}
      ${removed ? `<div class="removal-note pv2-removal-note"><strong>Marked for removal.</strong><span>This profile remains visible until the transaction commits.</span></div>` : ""}
      ${override ? `${renderOverrideTarget(profile)}${renderAffected(profile)}` : ""}
      <section class="profile-field-editor pv2-fields" aria-labelledby="pv2-fields-title">
        <header><div><p class="eyebrow pv2-eyebrow">Focused field editor</p><h3 id="pv2-fields-title">${override ? "Overridden values" : "Profile values"}</h3></div><span>${data.fields.length} available fields</span></header>
        ${renderFieldSections(profile)}
      </section>`;
    editorElement.querySelectorAll("[data-direction-mixed]").forEach((input) => {
      input.indeterminate = true;
    });
  }

  function ensureContextDefaults() {
    const symbols = new Set(data.assignments.map((item) => item?.species?.symbol));
    if (!symbols.has(ui.context.species)) ui.context.species = data.assignments[0]?.species?.symbol || "";
    const terrains = Object.values(data.labels?.terrains || {});
    const terrainSymbols = new Set(terrains.map((item) => item.symbol));
    if (!terrainSymbols.has(ui.context.terrain)) {
      ui.context.terrain = terrains.find((item) => /_LAND$/.test(item.symbol))?.symbol || terrains[0]?.symbol || "";
    }
  }

  function renderContextResult() {
    if (ui.contextBusy) return `<div class="empty-state empty-state--small"><h2>Resolving…</h2><p>Reading the saved source layers.</p></div>`;
    if (ui.contextError) return `<div class="empty-state empty-state--small is-error"><h2>Resolution unavailable</h2><p>${escapeHtml(ui.contextError)}</p></div>`;
    const result = ui.contextResult;
    if (!result) return `<div class="empty-state empty-state--small"><span class="scan-grid" aria-hidden="true"></span><h2>Choose a subject</h2><p>Resolve a Pokémon and terrain to preview exact saved order and field provenance.</p></div>`;
    const layers = result.resolverLayers || [];
    const matchedOverrideIndexes = layers
      .map((layer, index) => (layer.kind === "override" && layer.matched ? index : -1))
      .filter((index) => index >= 0);
    const finalMatchedOverrideIndex = matchedOverrideIndexes.at(-1);
    const indexedLayers = layers.map((layer, index) => ({ layer, index }));
    const appliedLayers = indexedLayers.filter(({ layer }) => layer.kind === "base" || layer.matched);
    const skippedLayers = indexedLayers.filter(({ layer }) => layer.kind === "override" && !layer.matched);
    const renderLayer = ({ layer, index }) => `<li class="resolution-layer ${layer.matched ? "is-matched" : "is-skipped"}${index === finalMatchedOverrideIndex ? " is-applied-last" : ""}"><span>${String(index + 1).padStart(2, "0")}</span><div><strong>${escapeHtml(layer.name)}</strong><small>${escapeHtml(layer.summary || layer.kind)}</small></div><em>${index === finalMatchedOverrideIndex ? "applied last" : (layer.matched ? "applied" : "skipped")}</em></li>`;
    const allFields = unique([...Object.keys(result.baseProfile || {}), ...Object.keys(result.resolvedProfile || {})]);
    const changed = allFields.filter((field) => valueRaw(result.baseProfile?.[field]) !== valueRaw(result.resolvedProfile?.[field]));
    const classHits = result.classRuleHits || [];
    const runtimeLayers = result.runtimeLayers || [];
    const normalizations = result.normalizations || [];
    const primitives = Object.entries(result.resolvedPrimitives || {});
    const runtimeChangeCount = runtimeLayers.reduce((total, layer) => total + (layer.changes || []).length, 0);
    return `
      <div class="resolution-result">
        <header class="resolution-summary"><div><small>Resolved subject</small><strong>${escapeHtml(result.context?.species?.name || ui.context.species)} · Lv ${escapeHtml(result.context?.level || ui.context.level)}</strong></div><span class="result-chip">${matchedOverrideIndexes.length} matched</span></header>
        <section><h3>Applied layer order</h3><ol class="resolution-layers">${appliedLayers.map(renderLayer).join("")}</ol>
          ${skippedLayers.length ? `<details class="pv2-skipped-layers"><summary>Skipped layers <small>${skippedLayers.length}</small></summary><ol class="resolution-layers">${skippedLayers.map(renderLayer).join("")}</ol></details>` : ""}
        </section>
        <section><h3>Base → effective by field</h3><ul class="resolution-fields">
          ${changed.map((field) => `<li><strong>${escapeHtml(fieldLabel(field))}</strong><span class="base-value">(${escapeHtml(valueLabel(result.baseProfile?.[field]))})</span><i aria-hidden="true">→</i><b>${escapeHtml(valueLabel(result.resolvedProfile?.[field]))}</b></li>`).join("") || `<li class="pv2-empty">No field changes in this context.</li>`}
        </ul></section>
        <details class="pv2-diagnostics">
          <summary><span>Runtime diagnostics</span><small>${runtimeChangeCount} field writes · ${classHits.length} class match${classHits.length === 1 ? "" : "es"}</small></summary>
          <div class="pv2-diagnostic-stack">
            <section><h4>Class selection</h4><ul class="pv2-diagnostic-list">
              ${classHits.map((hit) => `<li><span>#${escapeHtml(hit.order)}</span><strong>${escapeHtml(hit.summary)}</strong><small>${escapeHtml(hit.className)}</small></li>`).join("") || `<li class="pv2-empty">No class rules matched.</li>`}
            </ul></section>
            <section><h4>Runtime layer writes</h4><ol class="pv2-runtime-layers">
              ${runtimeLayers.map((layer, index) => `<li><header><span>${String(index + 1).padStart(2, "0")}</span><strong>${escapeHtml(layer.label)}</strong><small>${(layer.changes || []).length} fields</small></header>${(layer.changes || []).length ? `<ul>${layer.changes.map((change) => `<li><strong>${escapeHtml(change.label || fieldLabel(change.field))}</strong><span class="base-value">(${escapeHtml(valueLabel(change.before))})</span><i aria-hidden="true">→</i><b>${escapeHtml(valueLabel(change.after))}</b></li>`).join("")}</ul>` : `<p>No runtime writes.</p>`}</li>`).join("") || `<li class="pv2-empty">No runtime layers returned.</li>`}
            </ol></section>
            ${normalizations.length ? `<section><h4>Normalizations</h4><ul class="pv2-diagnostic-list">${normalizations.map((item) => `<li><strong>${escapeHtml(item.label || fieldLabel(item.field))}</strong><small>${escapeHtml(item.reason || item.summary || `${valueLabel(item.before)} → ${valueLabel(item.after)}`)}</small></li>`).join("")}</ul></section>` : ""}
            ${primitives.length ? `<section><h4>Resolved engine primitives</h4><dl class="pv2-primitives">${primitives.map(([key, value]) => `<div><dt>${escapeHtml(humanizeRaw(String(key).replace(/([a-z])([A-Z])/g, "$1_$2")))}</dt><dd>${escapeHtml(valueLabel(value))}</dd></div>`).join("")}</dl></section>` : ""}
          </div>
        </details>
        <details class="pv2-full-profile">
          <summary><span>Full effective profile</span><small>${allFields.length} fields</small></summary>
          <dl>${allFields.map((field) => `<div><dt>${escapeHtml(fieldLabel(field))}</dt><dd>${escapeHtml(valueLabel(result.resolvedProfile?.[field]))}<small>(${escapeHtml(valueLabel(result.baseProfile?.[field]))})</small></dd></div>`).join("")}</dl>
        </details>
      </div>`;
  }

  function renderContextControls() {
    ensureContextDefaults();
    const terrains = Object.values(data.labels?.terrains || {}).sort((left, right) => Number(left.value) - Number(right.value));
    elements.profileContextSpecies.innerHTML = data.assignments.map((assignment) => `<option value="${escapeHtml(assignment.species?.symbol)}" ${assignment.species?.symbol === ui.context.species ? "selected" : ""}>${escapeHtml(assignment.species?.name)}</option>`).join("");
    elements.profileContextTerrain.innerHTML = terrains.map((terrain) => `<option value="${escapeHtml(terrain.symbol)}" ${terrain.symbol === ui.context.terrain ? "selected" : ""}>${escapeHtml(terrain.name)}</option>`).join("");
    elements.profileContextLevel.value = ui.context.level;
    elements.profileContextShiny.checked = ui.context.shiny;
    elements.resolveContext.disabled = ui.contextBusy || !ui.context.species || !ui.context.terrain;
  }

  function renderContext() {
    renderContextControls();
    contextElement.innerHTML = `
      <header class="panel-heading"><span><small>Context scan</small><strong>Resolution</strong></span><span class="result-chip">${ui.contextResult ? "Saved source" : "Not run"}</span></header>
      ${renderContextResult()}`;
  }

  function openContextResolver() {
    const focused = document.activeElement;
    const toolDisclosure = resolverOpenElement.closest("details");
    const toolSummary = toolDisclosure?.querySelector("summary");
    ui.resolverReturnFocus = focused instanceof HTMLElement && root.contains(focused)
      ? (toolDisclosure?.contains(focused) ? toolSummary : focused)
      : (toolSummary || resolverOpenElement);
    toolDisclosure?.removeAttribute("open");
    resolverDrawerElement.hidden = false;
    workbenchElement.classList.add("is-resolver-open");
    resolverOpenElement.setAttribute("aria-expanded", "true");
    requestAnimationFrame(() => elements.profileContextSpecies.focus({ preventScroll: true }));
  }

  function closeContextResolver() {
    resolverDrawerElement.hidden = true;
    workbenchElement.classList.remove("is-resolver-open");
    resolverOpenElement.setAttribute("aria-expanded", "false");
    const fallbackFocus = resolverOpenElement.closest("details")?.querySelector("summary") || resolverOpenElement;
    const returnFocus = ui.resolverReturnFocus?.isConnected ? ui.resolverReturnFocus : fallbackFocus;
    ui.resolverReturnFocus = null;
    requestAnimationFrame(() => returnFocus.focus({ preventScroll: true }));
  }

  function renderAll() {
    if (ui.destroyed) return;
    if (!ui.selectedKey || !findProfile(ui.selectedKey)) {
      const hinted = allProfiles().find((profile) => nameFor(profile) === ui.selectionHint);
      const nextKey = profileKey(hinted || baseProfiles().find((profile) => String(profile.index) === String(data.defaultClassIndex)) || allProfiles()[0] || {});
      ui.selectedKey = nextKey;
    }
    renderList();
    renderEditor();
    renderContext();
    signalDirty();
  }

  function setSelected(key, { focus = false, report = true } = {}) {
    if (!findProfile(key)) return;
    ui.selectedKey = key;
    ui.selectionHint = nameFor(findProfile(key));
    renderList();
    renderEditor();
    signalDirty();
    if (report) reportSelection("profiles", key, ui.selectionHint);
    if (focus) {
      editorElement.tabIndex = -1;
      requestAnimationFrame(() => editorElement.focus({ preventScroll: true }));
    }
  }

  function moveOverride(key, delta) {
    if (filtered()) {
      status("Clear search and kind filters before reordering overrides.", "warning");
      return;
    }
    const ordered = orderedSavedOverrides();
    const index = ordered.findIndex((profile) => profileKey(profile) === key);
    const target = index + delta;
    if (index < 0 || target < 0 || target >= ordered.length) return;
    const [moved] = ordered.splice(index, 1);
    ordered.splice(target, 0, moved);
    drafts.overrideOrder = ordered.map(profileKey);
    renderList();
    signalDirty();
    announce(`${nameFor(moved)} moved to position ${target + 1} of ${ordered.length}.`);
  }

  function moveOverrideTo(sourceKey, targetKey, after) {
    if (filtered() || sourceKey === targetKey) return;
    const ordered = orderedSavedOverrides();
    const sourceIndex = ordered.findIndex((profile) => profileKey(profile) === sourceKey);
    const targetIndex = ordered.findIndex((profile) => profileKey(profile) === targetKey);
    if (sourceIndex < 0 || targetIndex < 0) return;
    const [moved] = ordered.splice(sourceIndex, 1);
    let insertion = ordered.findIndex((profile) => profileKey(profile) === targetKey);
    if (after) insertion += 1;
    ordered.splice(insertion, 0, moved);
    drafts.overrideOrder = ordered.map(profileKey);
    renderList();
    signalDirty();
    announce(`${nameFor(moved)} moved to position ${insertion + 1} of ${ordered.length}.`);
  }

  async function askConfirmation(message, options = {}) {
    if (typeof confirmAction === "function") {
      return Boolean(await confirmAction({ message, danger: Boolean(options.dangerous), ...options }));
    }
    return globalThis.confirm(message);
  }

  function openDialog({ title, submitLabel = "Save", fields, onSubmit, danger = false }) {
    dialogSubmit = onSubmit;
    dialogElement.innerHTML = `
      <form method="dialog" data-dialog-form>
        <header><p class="pv2-eyebrow">Profile action</p><h2>${escapeHtml(title)}</h2></header>
        <div class="pv2-dialog-fields">${fields}</div>
        <footer><button type="button" data-action="close-dialog">Cancel</button><button class="${danger ? "is-danger" : "is-primary"}" type="submit">${escapeHtml(submitLabel)}</button></footer>
      </form>`;
    if (typeof dialogElement.showModal === "function") dialogElement.showModal();
    else dialogElement.setAttribute("open", "");
    requestAnimationFrame(() => dialogElement.querySelector("input, textarea, select")?.focus());
  }

  function closeDialog() {
    dialogSubmit = null;
    if (typeof dialogElement.close === "function") dialogElement.close();
    else dialogElement.removeAttribute("open");
  }

  function rekeyBaseDraft(oldKey, newKey) {
    if (oldKey === newKey) return;
    if (drafts.baseFields.has(oldKey)) {
      drafts.baseFields.set(newKey, drafts.baseFields.get(oldKey));
      drafts.baseFields.delete(oldKey);
    }
    for (const [species, target] of drafts.memberships) if (target === oldKey) drafts.memberships.set(species, newKey);
    if (ui.selectedKey === oldKey) ui.selectedKey = newKey;
  }

  function rewriteDraftBehaviorClass(oldSymbol, newSymbol) {
    if (!oldSymbol || !newSymbol || oldSymbol === newSymbol) return;
    drafts.overrideTargets.forEach((target, key) => {
      const rewritten = cloneTarget(target);
      if (rewritten.match.behaviorClass === oldSymbol) rewritten.match.behaviorClass = newSymbol;
      drafts.overrideTargets.set(key, rewritten);
    });
    drafts.newOverrides.forEach((draft) => {
      if (draft.target.match.behaviorClass === oldSymbol) draft.target.match.behaviorClass = newSymbol;
    });
  }

  function dropProfileDraft(key) {
    drafts.baseFields.delete(key);
    drafts.overrideFields.delete(key);
    drafts.overrideNames.delete(key);
    drafts.overrideTargets.delete(key);
    drafts.removedOverrides.delete(key);
    drafts.overrideOrder = drafts.overrideOrder.filter((item) => item !== key);
    for (const [species, target] of drafts.memberships) if (target === key) drafts.memberships.delete(species);
  }

  async function manageBaseProfile(payload, currentProfile = null) {
    if (ui.busy) return;
    ui.busy = true;
    status(`${humanizeRaw(payload.action)} profile…`, "busy");
    renderList();
    try {
      const oldKey = currentProfile ? profileKey(currentProfile) : "";
      const oldSymbol = currentProfile?.symbol || "";
      const fallbackSymbol = baseByIndex(data.defaultClassIndex)?.symbol || "OW_WILD_BEHAVIOR_CLASS_DEFAULT";
      const result = await apiPost("/manage-profiles", payload);
      if (payload.action === "rename" && result?.symbol) {
        rekeyBaseDraft(oldKey, `base:${result.symbol}`);
        rewriteDraftBehaviorClass(oldSymbol, result.symbol);
      }
      if (payload.action === "delete") rewriteDraftBehaviorClass(oldSymbol, fallbackSymbol);
      if (payload.action === "delete") dropProfileDraft(oldKey);
      if (typeof state.reloadData === "function") await state.reloadData({ keepStatus: true });
      else refresh(await apiGet("/data.json", { cache: "no-store" }));
      if (result?.symbol) setSelected(`base:${result.symbol}`);
      status(result?.message || "Profile structure saved.", "success");
    } catch (error) {
      status(`Profile action failed: ${error.message}`, "error");
    } finally {
      ui.busy = false;
      renderAll();
    }
  }

  function createBaseDialog() {
    openDialog({
      title: "Create base profile",
      submitLabel: "Create profile",
      fields: `
        <label><span>Name</span><input name="name" required maxlength="80" autocomplete="off"></label>
        <label><span>Initial Pokémon (optional)</span><textarea name="pokemon" rows="4" placeholder="Mankey, Primeape"></textarea><small>Comma or line separated species names/symbols.</small></label>`,
      onSubmit: (form) => {
        const formData = new FormData(form);
        const name = String(formData.get("name") || "").trim();
        const rawPokemon = String(formData.get("pokemon") || "").split(/[\n,;]+/).map((item) => item.trim()).filter(Boolean);
        const resolved = rawPokemon.map(speciesForInput);
        const invalid = rawPokemon.filter((_, index) => !resolved[index]);
        if (invalid.length) {
          status(`Unknown Pokémon: ${invalid.join(", ")}`, "error");
          return;
        }
        const pokemon = unique(resolved.map((species) => species.symbol));
        return manageBaseProfile({ action: "create", name, pokemon });
      },
    });
  }

  function createProfileDialog() {
    openDialog({
      title: "Create profile",
      submitLabel: "Continue",
      fields: `
        <label><span>Profile kind</span><select name="kind"><option value="base">Base profile</option><option value="override">Ordered override</option></select></label>
        <p>Base profiles assign a complete behavior to Pokémon. Each ordered override is one layer with one member set and optional shared conditions.</p>`,
      onSubmit: (form) => {
        const kind = String(new FormData(form).get("kind") || "base");
        if (kind === "override") createOverrideDialog();
        else createBaseDialog();
      },
    });
  }

  function createOverrideDialog(source = null) {
    const suggestedName = uniqueOverrideName(source ? `${nameFor(source)} copy` : "New override profile");
    openDialog({
      title: source ? `Duplicate ${nameFor(source)}` : "Create override profile",
      submitLabel: source ? "Duplicate override" : "Create draft",
      fields: `<label><span>Name</span><input name="name" required maxlength="80" value="${escapeHtml(suggestedName)}" autocomplete="off"></label>`,
      onSubmit: (form) => {
        const name = String(new FormData(form).get("name") || "").trim();
        if (!overrideNameAvailable(name)) {
          status(`An override named ${name} already exists. Names identify layers and must be unique.`, "error");
          return;
        }
        const draft = {
          draftId: createDraftId(),
          name,
          fields: source ? Object.fromEntries(data.fields.map((field) => [field.key, fieldRaw(source, field.key)]).filter(([, raw]) => raw)) : {},
          target: source ? targetFor(source) : { members: [], match: { ...DEFAULT_MATCH }, targetMode: "disabled" },
        };
        drafts.newOverrides.push(draft);
        ui.selectedKey = `draft:${draft.draftId}`;
        ui.selectionHint = name;
        status("Override draft created. Add only the fields it should replace.", "warning");
        renderAll();
      },
    });
  }

  function createOverrideFromBase(profile) {
    if (!profile || isOverrideProfile(profile) || String(profile.index) === String(data.defaultClassIndex)) return;
    const members = membersFor(profile);
    if (!members.length) {
      status(`${nameFor(profile)} has no Pokémon to target.`, "error");
      return;
    }
    const name = uniqueOverrideName(`${nameFor(profile)} override`);
    const fields = {};
    const allowed = new Set(data.overrideFieldKeys || []);
    data.fields.forEach((field) => {
      const raw = fieldRaw(profile, field.key);
      if (allowed.has(field.key) && raw) fields[field.key] = raw;
    });
    const draft = {
      draftId: createDraftId(),
      name,
      fields,
      target: {
        members: members.map((assignment) => assignment.species.symbol),
        match: { ...DEFAULT_MATCH },
        targetMode: "members",
      },
    };
    drafts.newOverrides.push(draft);
    ui.selectedKey = `draft:${draft.draftId}`;
    ui.selectionHint = name;
    ui.openSections.add("override-target");
    renderAll();
    status(`Created ${name} with ${members.length} member targets. The base profile is unchanged.`, "warning");
  }

  function renameDialog(profile) {
    openDialog({
      title: `Rename ${nameFor(profile)}`,
      fields: `<label><span>Name</span><input name="name" required maxlength="80" value="${escapeHtml(nameFor(profile))}" autocomplete="off"></label>`,
      onSubmit: (form) => {
        const name = String(new FormData(form).get("name") || "").trim();
        if (isOverrideProfile(profile)) {
          if (!overrideNameAvailable(name, profile)) {
            status(`An override named ${name} already exists. Names identify layers and must be unique.`, "error");
            return;
          }
          if (profile.draftId) {
            const draft = backingNewOverride(profile);
            if (draft) draft.name = name;
            profile.name = name;
          }
          else if (name === profile.name) drafts.overrideNames.delete(profileKey(profile));
          else drafts.overrideNames.set(profileKey(profile), name);
          ui.selectionHint = name;
          renderAll();
          status("Override rename added to the draft transaction.", "warning");
          return;
        }
        return manageBaseProfile({ action: "rename", classIndex: profile.index, name }, profile);
      },
    });
  }

  function duplicateProfile(profile) {
    if (isOverrideProfile(profile)) {
      createOverrideDialog(profile);
      return;
    }
    openDialog({
      title: `Duplicate ${nameFor(profile)}`,
      submitLabel: "Duplicate profile",
      fields: `<label><span>Name</span><input name="name" required maxlength="80" value="${escapeHtml(`${nameFor(profile)} copy`)}" autocomplete="off"></label>`,
      onSubmit: (form) => manageBaseProfile({ action: "duplicate", classIndex: profile.index, name: String(new FormData(form).get("name") || "").trim() }, profile),
    });
  }

  async function deleteProfile(profile) {
    const key = profileKey(profile);
    if (profile.draftId) {
      drafts.newOverrides = drafts.newOverrides.filter((item) => item.draftId !== profile.draftId);
      if (ui.selectedKey === key) ui.selectedKey = "";
      renderAll();
      return;
    }
    if (isOverrideProfile(profile)) {
      if (profile.canDelete === false) return;
      if (drafts.removedOverrides.has(key)) drafts.removedOverrides.delete(key);
      else if (await askConfirmation(`Remove ${nameFor(profile)} when changes are saved?`, { dangerous: true, confirmLabel: "Remove override" })) drafts.removedOverrides.add(key);
      renderAll();
      return;
    }
    if (String(profile.index) === String(data.defaultClassIndex) || profile.canDelete === false) return;
    const count = membersFor(profile).length;
    const confirmed = await askConfirmation(`Delete ${nameFor(profile)}? ${count} Pokémon will fall back to Default.`, { dangerous: true, confirmLabel: "Delete profile" });
    if (confirmed) await manageBaseProfile({ action: "delete", classIndex: profile.index }, profile);
  }

  function changeTargetCondition(profile, field, raw) {
    const target = targetFor(profile);
    if (!Object.hasOwn(DEFAULT_MATCH, field) || field === "species") return;
    target.match[field] = String(raw || DEFAULT_MATCH[field]);
    setTarget(profile, target);
    renderList();
    signalDirty();
  }

  async function resolveContext() {
    if (!ui.context.species || !ui.context.terrain || ui.contextBusy) return;
    contextAbortController?.abort();
    contextAbortController = new AbortController();
    ui.contextBusy = true;
    ui.contextError = "";
    renderContext();
    try {
      const query = new URLSearchParams({
        species: ui.context.species,
        terrain: ui.context.terrain,
        level: ui.context.level,
        shiny: ui.context.shiny ? "1" : "0",
      });
      ui.contextResult = typeof api.resolve === "function"
        ? await api.resolve(Object.fromEntries(query), { signal: contextAbortController.signal })
        : await apiGet(`/api/v2/resolve?${query}`, { cache: "no-store", signal: contextAbortController.signal });
      ui.contextError = "";
      renderEditor();
    } catch (error) {
      if (error.name !== "AbortError") ui.contextError = `Could not resolve this context: ${error.message}`;
    } finally {
      ui.contextBusy = false;
      contextAbortController = null;
      renderContext();
    }
  }

  function onClick(event) {
    const modeTabShell = event.target.closest(".pv2-mode-tab");
    if (modeTabShell && root.contains(modeTabShell) && !event.target.closest(".pv2-mode-tab-select")) {
      const modeTab = modeTabShell.querySelector("[data-mode-tab]");
      if (modeTab) {
        selectModeTab(modeTab.dataset.modeTabSection, modeTab.dataset.modeTab);
        return;
      }
    }
    const target = event.target.closest("[data-action]");
    if (!target || !root.contains(target)) return;
    const action = target.dataset.action;
    const key = target.dataset.profileKey || ui.selectedKey;
    const profile = findProfile(key);
    if (action === "open-context-resolver") openContextResolver();
    else if (action === "close-context-resolver") closeContextResolver();
    else if (action === "select-profile") setSelected(key);
    else if (action === "open-pokemon") {
      openPokemonRecord(target.dataset.species, {
        view: "profiles",
        selection: ui.selectedKey,
        label: nameFor(findProfile()),
      });
    }
    else if (action === "select-lifecycle-tab") selectLifecycleTab(target.dataset.lifecycleTab);
    else if (action === "select-lifecycle-mode") selectLifecycleMode(target.dataset.lifecycleSection, target.dataset.modeTarget);
    else if (action === "select-mode-tab") selectModeTab(target.dataset.modeTabSection, target.dataset.modeTab);
    else if (action === "add-conditional-state" && profile) {
      const conditionalState = cloneConditionalState({
        parentKey: profileKey(profile),
        overrideKey: null,
        terrainMask: CONDITIONAL_DEFAULT_TERRAIN_BITS,
        terrainOverrideMask: CONDITIONAL_DEFAULT_TERRAIN_BITS,
        minMovementSpeed: 0,
        maxMovementSpeed: 0,
      });
      const duplicate = conditionalStatesFor(profile).some((candidate) => (
        conditionalStateKey(candidate) === conditionalStateKey(conditionalState)
      ));
      if (duplicate) {
        status("The default Rooftop / Signpost condition already exists. Adjust it before adding another.", "warning");
        return;
      }
      setConditionalStates([
        ...currentConditionalStates(),
        conditionalState,
      ]);
      state.profileLifecycleSection = conditionalLifecycleBaseId(conditionalState);
      renderEditor(); renderList(); signalDirty();
      focusSectionNavigation(state.profileLifecycleSection);
      announce("Rooftop or Signpost state added. Adjust its tile or speed conditions, then choose its override profile.");
    }
    else if (action === "remove-conditional-state" && profile) {
      const stateKey = target.dataset.conditionStateKey || "";
      setConditionalStates(currentConditionalStates().filter((entry) => !(
        entry.parentKey === profileKey(profile)
        && conditionalStateKey(entry) === stateKey
      )));
      state.profileLifecycleSection = CONDITIONS_LIFECYCLE_SECTION_ID;
      renderEditor(); renderList(); signalDirty();
      focusSectionNavigation(CONDITIONS_LIFECYCLE_SECTION_ID);
      announce("Conditional state removed.");
    }
    else if (action === "set-conditional-terrain" && profile) {
      const stateKey = target.dataset.conditionStateKey || "";
      const bit = Number(target.dataset.terrainBit);
      const terrainState = target.dataset.nextTerrainState;
      if (!Number.isInteger(bit) || bit <= 0 || !["inherit", "off", "on"].includes(terrainState)) return;
      const updated = updateConditionalState(profileKey(profile), stateKey, (entry) => {
        let valueMask = terrainPolicyMaskNumber(entry.terrainMask);
        let explicitMask = terrainPolicyMaskNumber(entry.terrainOverrideMask);
        if (terrainState === "inherit") {
          explicitMask &= ~bit;
          valueMask &= ~bit;
        } else {
          explicitMask |= bit;
          if (terrainState === "on") valueMask |= bit;
          else valueMask &= ~bit;
        }
        return { ...entry, terrainMask: String(valueMask), terrainOverrideMask: String(explicitMask) };
      });
      if (updated === false) {
        status("That change would duplicate another conditional state.", "warning");
        return;
      }
      if (!updated) return;
      state.profileLifecycleSection = CONDITIONS_LIFECYCLE_SECTION_ID;
      renderEditor(); renderList(); signalDirty();
      const selector = `[data-action="set-conditional-terrain"][data-condition-state-key="${CSS.escape(conditionalStateKey(updated))}"][data-terrain-bit="${bit}"]`;
      editorElement.querySelector(selector)?.focus({ preventScroll: true });
      announce(`${target.dataset.terrainLabel || "Terrain"} will be ${terrainState} for this condition after saving.`);
    }
    else if (action === "inherit-player-adjacent-directions" && profile) {
      setField(profile, "playerAdjacentDirectionMasks", "");
      renderEditor(); renderList(); signalDirty();
      announce("Next-to-player side settings will inherit after saving.");
    }
    else if (action === "set-terrain-policy" && profile) {
      const policyId = target.dataset.terrainPolicy;
      const bit = Number(target.dataset.terrainBit);
      const terrainState = target.dataset.nextTerrainState;
      if (!TERRAIN_POLICY_CONFIGS[policyId]
        || !Number.isInteger(bit)
        || bit <= 0
        || !["inherit", "off", "on"].includes(terrainState)) return;
      setTerrainPolicyState(profile, policyId, bit, terrainState);
      renderEditor(); renderList(); signalDirty();
      const selector = `[data-action="set-terrain-policy"][data-profile-key="${CSS.escape(profileKey(profile))}"][data-terrain-policy="${CSS.escape(policyId)}"][data-terrain-bit="${bit}"]`;
      editorElement.querySelector(selector)?.focus({ preventScroll: true });
      announce(`${target.dataset.terrainLabel || "Terrain"} in ${TERRAIN_POLICY_CONFIGS[policyId].label.toLowerCase()} will be ${terrainState} after saving.`);
    }
    else if (action === "move-up") moveOverride(key, -1);
    else if (action === "move-down") moveOverride(key, 1);
    else if (action === "create-base") createBaseDialog();
    else if (action === "create-override") createOverrideDialog();
    else if (action === "new-profile") createProfileDialog();
    else if (action === "convert-base-to-override" && profile) createOverrideFromBase(profile);
    else if (action === "rename-profile" && profile) renameDialog(profile);
    else if (action === "duplicate-profile" && profile) duplicateProfile(profile);
    else if (action === "delete-profile" && profile) deleteProfile(profile);
    else if (action === "discard-stale-draft") discardStaleDraft(target.dataset.staleDraftId);
    else if (action === "close-dialog") closeDialog();
    else if (action === "add-target" && profile) addTarget(profile);
    else if (action === "inspect-species") {
      const assignment = data.assignments.find((item) => item.species?.symbol === target.dataset.species);
      const context = assignment && profile ? matchingContextFor(profile, assignment) : null;
      if (context) Object.assign(ui.context, context);
      else ui.context.species = target.dataset.species;
      renderContextControls();
      openContextResolver();
      resolveContext();
    }
    else if (action === "clear-section" && profile) {
      event.preventDefault();
      event.stopPropagation();
      const section = FIELD_SECTIONS.find((candidate) => candidate.id === target.dataset.section);
      const fields = section ? sectionFields(section, profile) : (target.dataset.section === "advanced" ? unsectionedFields(profile) : []);
      const clearedCount = fields.filter((field) => sectionFieldRaw(section, profile, field)).length;
      fields.forEach((field) => clearSectionField(section, profile, field));
      renderEditor(); renderList(); signalDirty();
      focusSectionNavigation(target.dataset.focusSection || target.dataset.section);
      announce(`${section?.title || "Advanced"}: ${clearedCount} override value${clearedCount === 1 ? "" : "s"} will inherit after saving.`);
    }
    else if (action === "remove-override-member" && profile) {
      const overrideTarget = targetFor(profile);
      overrideTarget.members = overrideTarget.members.filter((symbol) => symbol !== target.dataset.species);
      if (!overrideTarget.members.length && overrideTarget.targetMode === "members") overrideTarget.targetMode = "disabled";
      setTarget(profile, overrideTarget); renderEditor(); renderList(); signalDirty();
    } else if (action === "add-member" && profile) {
      const symbol = editorElement.querySelector("[data-member-select]")?.value;
      if (symbol) setMembership(symbol, profile);
      renderEditor(); renderList(); signalDirty();
    } else if (action === "remove-member" && profile) {
      const fallback = baseByIndex(data.defaultClassIndex);
      if (fallback) setMembership(target.dataset.species, fallback);
      renderEditor(); renderList(); signalDirty();
    } else if (action === "resolve-context") resolveContext();
  }

  function updateNumericOverrideInput(input, fallbackProfile, { render = true } = {}) {
    if (!input.matches("[data-profile-numeric-entry]")) return false;
    const profile = numericInputProfile(input, fallbackProfile);
    if (!profile) {
      input.setAttribute("aria-invalid", "true");
      const staleError = input.closest(".pv2-numeric-combobox")?.querySelector(".pv2-numeric-error");
      if (staleError) staleError.textContent = "This field is no longer active. Reopen its profile before editing.";
      return true;
    }
    const fieldKey = input.dataset.fieldKey;
    const fieldInstance = input.dataset.fieldInstance;
    const permissions = numericInputPermissions(input, profile, fieldKey);
    const invalidKey = `${profileKey(profile)}|${fieldKey}|${fieldInstance}`;
    const error = input.closest(".pv2-numeric-combobox")?.querySelector(".pv2-numeric-error");
    const rawInput = input.value.trim();
    const raw = /^inherit$/i.test(rawInput) ? "" : rawInput;
    const fail = (message) => {
      invalidNumericOperatorInputs.add(invalidKey);
      input.setAttribute("aria-invalid", "true");
      if (error) error.textContent = message;
      signalDirty();
      return true;
    };
    if (!raw) {
      if (input.dataset.profileAllowInherit !== "true") return fail("A whole-number value is required.");
      invalidNumericOperatorInputs.delete(invalidKey);
      input.setAttribute("aria-invalid", "false");
      if (error) error.textContent = "";
      input.value = "";
      setField(profile, fieldKey, "");
      if (!render) {
        signalDirty();
        return true;
      }
      renderEditor(); renderList(); signalDirty();
      return true;
    }
    const list = document.getElementById(input.getAttribute("list") || "");
    const exactRawValues = new Set([...(list?.options || [])]
      .map((option) => String(option.value))
      .filter((value) => value && value.toLowerCase() !== "inherit"));
    const exactOptions = [...exactRawValues]
      .map((value) => Number(value))
      .filter(Number.isFinite)
      .map((value) => ({ raw: String(value) }));
    const operator = parseNumericOverrideRaw(raw);
    let canonical = raw;
    if (operator) {
      for (const operation of operator.operations) {
        if (!numericOverrideAllowed(profile, fieldKey, operation.kind, permissions)) {
          return fail(permissions.adjust
            ? "Use +N or -N for this field; bound formulas are unavailable."
            : "Formulas are not available for this value.");
        }
        const bounds = numericOverrideOperandBounds(fieldKey, exactOptions, operation.kind);
        if (!Number.isInteger(operation.operand) || operation.operand < bounds.min || operation.operand > bounds.max) {
          return fail(`${operation.kind === "adjust" ? "Adjustment" : "Bound"} must be between ${bounds.min} and ${bounds.max}.`);
        }
      }
      if (operator.kind === "compound") {
        const adjust = operator.adjust.operand > 0 ? `+${operator.adjust.operand}` : String(operator.adjust.operand);
        const bound = operator.bound.kind === "atLeast" ? `/<${operator.bound.operand}` : `/>${operator.bound.operand}`;
        canonical = operator.adjust.operand === 0 ? bound : `${adjust}, ${bound}`;
      } else {
        canonical = operator.kind === "adjust"
          ? (operator.operand === 0 ? "" : (operator.operand > 0 ? `+${operator.operand}` : String(operator.operand)))
          : (operator.kind === "atLeast" ? `/<${operator.operand}` : `/>${operator.operand}`);
      }
    } else {
      const exact = Number(raw);
      const exactNumbers = [...exactRawValues].map(Number).filter(Number.isFinite);
      const optionMinimum = exactNumbers.length ? Math.min(...exactNumbers) : 0;
      const optionMaximum = exactNumbers.length ? Math.max(...exactNumbers) : 64;
      const minimum = Number(data.numericOverrideOperandMinimums?.[fieldKey] ?? optionMinimum);
      const maximum = Number(data.numericOverrideOperandMaximums?.[fieldKey] ?? optionMaximum);
      if (!Number.isInteger(exact) || exact < minimum || exact > maximum) {
        const formulaExamples = [permissions.adjust ? "+2 or -1" : "", permissions.bounds ? "/<2 or />2" : "", permissions.adjust && permissions.bounds ? "+1, /<2" : ""]
          .filter(Boolean)
          .join(", ");
        return fail(`Value must be a whole number between ${minimum} and ${maximum}${formulaExamples ? `, or a formula such as ${formulaExamples}` : ""}.`);
      }
      canonical = String(exact);
    }
    invalidNumericOperatorInputs.delete(invalidKey);
    input.setAttribute("aria-invalid", "false");
    if (error) error.textContent = "";
    input.value = canonical;
    setField(profile, fieldKey, canonical);
    if (!render) {
      signalDirty();
      return true;
    }
    renderEditor(); renderList(); signalDirty();
    const focusTarget = editorElement.querySelector(`[data-profile-numeric-entry][data-field-instance="${CSS.escape(fieldInstance)}"]`);
    focusTarget?.focus({ preventScroll: true });
    focusTarget?.select();
    return true;
  }

  function onInput(event) {
    if (updateNumericOverrideInput(event.target, findProfile(), { render: false })) {
      if (formulaRefreshTimer !== null) window.clearTimeout(formulaRefreshTimer);
      formulaRefreshTimer = null;
      return;
    } else if (event.target === elements.profileSearch) {
      ui.search = event.target.value;
      renderList();
    } else if (event.target.matches("[data-member-search]")) {
      ui.memberQuery = event.target.value;
      const profile = findProfile();
      if (profile) {
        renderEditor();
        const input = editorElement.querySelector("[data-member-search]");
        input?.focus();
        input?.setSelectionRange(ui.memberQuery.length, ui.memberQuery.length);
      }
    }
  }

  function refreshAfterFormulaCommit(delay = 0) {
    if (formulaRefreshTimer !== null) window.clearTimeout(formulaRefreshTimer);
    formulaRefreshTimer = window.setTimeout(() => {
      formulaRefreshTimer = null;
      const active = document.activeElement;
      const fieldInstance = active?.dataset?.fieldInstance || "";
      const isFormula = Boolean(active?.matches?.("[data-profile-numeric-entry]"));
      const isValue = Boolean(active?.matches?.("[data-profile-value]"));
      const selectionStart = isFormula ? active.selectionStart : null;
      const selectionEnd = isFormula ? active.selectionEnd : null;
      renderEditor();
      renderList();
      if (!fieldInstance || (!isFormula && !isValue)) return;
      const selector = `${isFormula ? "[data-profile-numeric-entry]" : "[data-profile-value]"}[data-field-instance="${CSS.escape(fieldInstance)}"]`;
      const replacement = editorElement.querySelector(selector);
      replacement?.focus({ preventScroll: true });
      if (isFormula && Number.isInteger(selectionStart) && Number.isInteger(selectionEnd)) {
        replacement?.setSelectionRange(selectionStart, selectionEnd);
      }
    }, delay);
  }

  function onChange(event) {
    const profile = findProfile();
    if (event.target === elements.profileKindFilter) {
      ui.kind = event.target.value;
      renderList();
      return;
    }
    if (event.target.matches("[data-target-kind]")) {
      ui.targetKind = event.target.value;
      ui.targetValue = "";
      renderEditor();
      return;
    }
    if (event.target.matches("[data-target-value]")) {
      ui.targetValue = event.target.value;
      renderEditor();
      return;
    }
    if (event.target.matches("[data-state-profile-reference]")) {
      const owner = controlProfile(event.target, profile);
      if (!owner) return;
      const fieldKey = event.target.dataset.fieldKey;
      setField(owner, fieldKey, event.target.value);
      renderEditor(); renderList(); signalDirty();
      editorElement.querySelector(`[data-state-profile-reference][data-field-key="${CSS.escape(fieldKey)}"]`)?.focus({ preventScroll: true });
      return;
    }
    if (event.target.matches("[data-condition-profile-reference]") && profile) {
      const replacement = findProfile(event.target.value);
      if (replacement && !conditionalProfileCandidates(profile)
        .some((candidate) => profileKey(candidate) === profileKey(replacement))) {
        status("That override profile cannot be used for this conditional state.", "warning");
        renderEditor();
        return;
      }
      const stateKey = event.target.dataset.conditionStateKey || "";
      setConditionalStates(currentConditionalStates().map((entry) => (
        entry.parentKey === profileKey(profile)
          && conditionalStateKey(entry) === stateKey
          ? { ...entry, overrideKey: replacement ? profileKey(replacement) : null }
          : entry
      )));
      state.profileLifecycleSection = event.target.dataset.conditionSectionId
        || `${CONDITIONAL_LIFECYCLE_SECTION_PREFIX}${stateKey.replaceAll(":", "-")}`;

      renderEditor(); renderList(); signalDirty();
      const childKey = replacement ? profileKey(replacement) : "";
      editorElement.querySelector(`[data-condition-profile-reference][data-current-child-key="${CSS.escape(childKey)}"]`)?.focus({ preventScroll: true });
      return;
    }
    if (event.target.matches("[data-condition-speed-mode], [data-condition-speed-min], [data-condition-speed-max]") && profile) {
      const stateKey = event.target.dataset.conditionStateKey || "";
      const updated = updateConditionalState(profileKey(profile), stateKey, (entry) => {
        if (event.target.matches("[data-condition-speed-mode]")) {
          if (event.target.value === "any") return { ...entry, minMovementSpeed: "0", maxMovementSpeed: "0" };
          if (event.target.value === "range") return { ...entry, minMovementSpeed: "1", maxMovementSpeed: String(CONDITIONAL_MOVEMENT_SPEED_MAX) };
          return { ...entry, minMovementSpeed: "1", maxMovementSpeed: "1" };
        }
        const speed = conditionalMovementSpeed(event.target.value);
        if (event.target.matches("[data-condition-speed-min]")) {
          if (conditionalSpeedMode(entry) === "exact") return { ...entry, minMovementSpeed: String(speed), maxMovementSpeed: String(speed) };
          const maximum = Math.max(speed, conditionalMovementSpeed(entry.maxMovementSpeed));
          return { ...entry, minMovementSpeed: String(speed), maxMovementSpeed: String(maximum) };
        }
        const minimum = Math.min(speed, conditionalMovementSpeed(entry.minMovementSpeed));
        return { ...entry, minMovementSpeed: String(minimum), maxMovementSpeed: String(speed) };
      });
      if (updated === false) {
        status("That change would duplicate another conditional state.", "warning");
        renderEditor();
        return;
      }
      if (!updated) return;
      state.profileLifecycleSection = CONDITIONS_LIFECYCLE_SECTION_ID;
      renderEditor(); renderList(); signalDirty();
      const attribute = event.target.matches("[data-condition-speed-mode]")
        ? "data-condition-speed-mode"
        : (event.target.matches("[data-condition-speed-min]") ? "data-condition-speed-min" : "data-condition-speed-max");
      editorElement.querySelector(`[${attribute}][data-condition-state-key="${CSS.escape(conditionalStateKey(updated))}"]`)?.focus({ preventScroll: true });
      return;
    }
    if (updateNumericOverrideInput(event.target, profile, { render: false })) {
      if (event.target.getAttribute("aria-invalid") !== "true") refreshAfterFormulaCommit();
      return;
    }
    if (event.target.matches("[data-player-adjacent-direction]")) {
      const owner = controlProfile(event.target, profile);
      if (!owner) return;
      const bit = Number(event.target.dataset.directionBit);
      const currentRaw = fieldRaw(owner, "playerAdjacentDirectionMasks");
      const inheritedMasks = playerAdjacentEffectiveMasks(owner, currentRaw);
      let value = inheritedMasks.reduce((combined, candidate) => combined | candidate, 0);
      value = event.target.checked ? (value | (1 << bit)) : (value & ~(1 << bit));
      if (!value) {
        event.target.checked = true;
        status("Next to player needs at least one allowed side.", "warning");
        return;
      }
      setField(owner, "playerAdjacentDirectionMasks", String(value));
      renderEditor(); renderList(); signalDirty();
      if (inheritedMasks.length > 1) {
        announce("Mixed inherited sides are now one shared explicit mask.");
      }
      const selector = `[data-player-adjacent-direction][data-profile-key="${CSS.escape(profileKey(owner))}"][data-direction-bit="${bit}"]`;
      editorElement.querySelector(selector)?.focus({ preventScroll: true });
      return;
    }
    if (event.target.matches("[data-profile-value]:not([data-profile-numeric-entry])")) {
      const owner = controlProfile(event.target, profile);
      if (!owner) return;
      const fieldKey = event.target.dataset.fieldKey;
      const fieldInstance = event.target.dataset.fieldInstance;
      invalidNumericOperatorInputs.delete(`${profileKey(owner)}|${fieldKey}|${fieldInstance}`);
      const compound = event.target.dataset.profileCompound;
      const scope = event.target.dataset.compoundScope;
      const parentGroup = event.target.closest("[data-option-parent]");
      const parentField = parentGroup?.dataset.optionParent;
      const sectionId = event.target.closest("[data-section-id]")?.dataset.sectionId;
      const modeTabSelect = event.target.closest("[data-mode-tab-select]");
      const wasParentControl = Boolean(event.target.closest(".pv2-option-parent"));
      const beforeChildren = parentGroup?.querySelectorAll(":scope > .pv2-suboptions [data-profile-value]").length || 0;
      const currentRaw = fieldRaw(owner, fieldKey);
      let nextRaw = event.target.value;
      if (compound === "alert-range-type" && nextRaw) {
        nextRaw = alertRangeRawWithClose(nextRaw, alertRangeSupportsClose(nextRaw) && alertRangeIsClose(currentRaw));
      } else if (compound === "alert-range-close") {
        nextRaw = alertRangeRawWithClose(currentRaw, nextRaw === "1");
      } else if (compound === "scoped-action") {
        if (!nextRaw && isOverrideProfile(owner)) {
          nextRaw = scopedActionClearRaw(scope, currentRaw, originalFieldRaw(owner, fieldKey));
        } else if (nextRaw === ALERT_SPECIAL.none && scopedActionRaw(scope, currentRaw) === ALERT_SPECIAL.none) {
          nextRaw = currentRaw;
        }
      }
      if (modeTabSelect) {
        branchTabSelections.set(modeTabSelect.dataset.modeTabSection, modeTabSelect.dataset.modeTabSelect);
      }
      setField(owner, fieldKey, nextRaw);
      renderEditor(); renderList(); signalDirty();
      const focusTarget = fieldInstance
        ? editorElement.querySelector(`[data-profile-value][data-field-instance="${CSS.escape(fieldInstance)}"]`)
        : null;
      const fieldFallback = editorElement.querySelector(`[data-profile-value][data-field-key="${CSS.escape(fieldKey)}"]`);
      const parentFallback = sectionId && parentField
        ? editorElement.querySelector(`[data-section-id="${CSS.escape(sectionId)}"] [data-option-parent="${CSS.escape(parentField)}"] > .pv2-option-parent [data-profile-value]`)
        : null;
      const sectionFallback = sectionNavigationTarget(sectionId);
      (focusTarget || fieldFallback || parentFallback || sectionFallback)?.focus({ preventScroll: true });
      if (wasParentControl && sectionId && parentField) {
        const afterGroup = editorElement.querySelector(`[data-section-id="${CSS.escape(sectionId)}"] [data-option-parent="${CSS.escape(parentField)}"]`);
        const afterChildren = afterGroup?.querySelectorAll(":scope > .pv2-suboptions [data-profile-value]").length || 0;
        if (afterChildren !== beforeChildren) {
          announce(`${fieldLabelForProfile(owner, fieldKey)} now shows ${afterChildren} suboption${afterChildren === 1 ? "" : "s"}.`);
        }
      }
      return;
    }
    if (event.target.matches("[data-target-mode]") && profile) {
      const target = targetFor(profile);
      target.targetMode = event.target.value;
      setTarget(profile, target);
      renderEditor(); renderList(); signalDirty();
      return;
    }
    if (event.target.matches("[data-target-condition]") && profile) {
      const field = event.target.dataset.targetCondition;
      changeTargetCondition(profile, field, event.target.value);
      renderEditor();
      editorElement.querySelector(`[data-target-condition="${CSS.escape(field)}"]`)?.focus({ preventScroll: true });
      return;
    }
    if (event.target === elements.profileContextSpecies) ui.context.species = event.target.value;
    else if (event.target === elements.profileContextTerrain) ui.context.terrain = event.target.value;
    else if (event.target === elements.profileContextLevel) ui.context.level = event.target.value;
    else if (event.target === elements.profileContextShiny) ui.context.shiny = event.target.checked;
  }

  function onFocusOut(event) {
    if (!event.target.matches("[data-profile-numeric-entry]")) return;
    if (event.target.getAttribute("aria-invalid") !== "true") refreshAfterFormulaCommit();
  }

  function onToggle(event) {
    const section = event.target;
    if (!(section instanceof HTMLDetailsElement) || !section.matches("details[data-section-id]")) return;
    const wasOpen = ui.openSections.has(section.dataset.sectionId);
    if (section.open) {
      ui.openSections.add(section.dataset.sectionId);
      const rendersOnOpen = ["membership", "member-list", "affected", "override-target", "advanced"].includes(section.dataset.sectionId)
        || FIELD_SECTIONS.some((candidate) => candidate.id === section.dataset.sectionId);
      if (!wasOpen && rendersOnOpen) {
        const sectionId = section.dataset.sectionId;
        requestAnimationFrame(() => {
          renderEditor();
          focusSectionNavigation(sectionId);
        });
      }
    } else {
      ui.openSections.delete(section.dataset.sectionId);
    }
  }

  async function onSubmit(event) {
    if (!event.target.matches("[data-dialog-form]")) return;
    event.preventDefault();
    const submit = dialogSubmit;
    closeDialog();
    if (submit) await submit(event.target);
  }

  function onKeyDown(event) {
    const expressionInput = event.target.closest("[data-profile-numeric-entry]");
    if (expressionInput && event.key === "Enter") {
      event.preventDefault();
      updateNumericOverrideInput(expressionInput, findProfile());
      return;
    }
    if (expressionInput && event.key === "Escape") {
      event.preventDefault();
      const fieldInstance = expressionInput.dataset.fieldInstance;
      const profile = numericInputProfile(expressionInput, findProfile());
      if (profile) invalidNumericOperatorInputs.delete(`${profileKey(profile)}|${expressionInput.dataset.fieldKey}|${fieldInstance}`);
      renderEditor();
      editorElement.querySelector(`[data-profile-numeric-entry][data-field-instance="${CSS.escape(fieldInstance)}"]`)?.focus({ preventScroll: true });
      announce("Value restored to its last valid state.");
      return;
    }
    if (event.key === "Escape" && !resolverDrawerElement.hidden) {
      event.preventDefault();
      closeContextResolver();
      return;
    }
    const lifecycleTab = event.target.closest("[data-lifecycle-tab]");
    if (lifecycleTab && ["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      const tabs = [...(lifecycleTab.closest('[role="tablist"]')?.querySelectorAll("[data-lifecycle-tab]") || [])];
      const index = tabs.indexOf(lifecycleTab);
      if (index < 0 || !tabs.length) return;
      event.preventDefault();
      const nextIndex = event.key === "Home"
        ? 0
        : (event.key === "End"
          ? tabs.length - 1
          : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length);
      selectLifecycleTab(tabs[nextIndex].dataset.lifecycleTab);
      return;
    }
    const modeTab = event.target.closest("[data-mode-tab]");
    if (modeTab && ["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      const tabs = [...(modeTab.closest('[role="tablist"]')?.querySelectorAll("[data-mode-tab]") || [])];
      const index = tabs.indexOf(modeTab);
      if (index < 0 || !tabs.length) return;
      event.preventDefault();
      const nextIndex = event.key === "Home"
        ? 0
        : (event.key === "End"
          ? tabs.length - 1
          : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length);
      selectModeTab(modeTab.dataset.modeTabSection, tabs[nextIndex].dataset.modeTab);
      return;
    }
    const handle = event.target.closest("[data-reorder-handle]");
    if (!handle || !["ArrowUp", "ArrowDown"].includes(event.key)) return;
    event.preventDefault();
    moveOverride(handle.dataset.profileKey, event.key === "ArrowUp" ? -1 : 1);
    listElement.querySelector(`[data-reorder-handle][data-profile-key="${CSS.escape(handle.dataset.profileKey)}"]`)?.focus();
  }

  function onDragStart(event) {
    const handle = event.target.closest("[data-reorder-handle]");
    if (!handle || filtered()) return;
    ui.draggedKey = handle.dataset.profileKey;
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", ui.draggedKey);
    handle.closest("[data-profile-row]")?.classList.add("is-dragging");
  }

  function onDragOver(event) {
    const row = event.target.closest("[data-profile-row]");
    if (!row?.classList.contains("override-profile") || !ui.draggedKey || row.dataset.profileKey === ui.draggedKey) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    listElement.querySelectorAll(".is-drop-before, .is-drop-after").forEach((item) => item.classList.remove("is-drop-before", "is-drop-after"));
    const rect = row.getBoundingClientRect();
    row.classList.add(event.clientY < rect.top + rect.height / 2 ? "is-drop-before" : "is-drop-after");
  }

  function onDrop(event) {
    const row = event.target.closest("[data-profile-row]");
    if (!row?.classList.contains("override-profile") || !ui.draggedKey) return;
    event.preventDefault();
    const rect = row.getBoundingClientRect();
    moveOverrideTo(ui.draggedKey, row.dataset.profileKey, event.clientY >= rect.top + rect.height / 2);
    onDragEnd();
  }

  function onDragEnd() {
    ui.draggedKey = "";
    listElement.querySelectorAll(".is-dragging, .is-drop-before, .is-drop-after").forEach((item) => item.classList.remove("is-dragging", "is-drop-before", "is-drop-after"));
  }

  function completeCoupledOverrideFieldEdits(profile, fieldEdits) {
    const completed = new Map(fieldEdits);
    for (const fields of COUPLED_OVERRIDE_FIELD_GROUPS) {
      if (!fields.some((field) => completed.has(field))) continue;
      for (const field of fields) completed.set(field, fieldRaw(profile, field));
    }
    return completed;
  }

  root.addEventListener("click", onClick);
  root.addEventListener("input", onInput);
  root.addEventListener("change", onChange);
  root.addEventListener("focusout", onFocusOut);
  root.addEventListener("toggle", onToggle, true);
  root.addEventListener("submit", onSubmit);
  root.addEventListener("keydown", onKeyDown);
  root.addEventListener("dragstart", onDragStart);
  root.addEventListener("dragover", onDragOver);
  root.addEventListener("drop", onDrop);
  root.addEventListener("dragend", onDragEnd);

  function serializedConditionalStates() {
    return currentConditionalStates().flatMap((entry) => {
      const parent = findProfile(entry.parentKey);
      if (!parent || drafts.removedOverrides.has(entry.parentKey)) return [];
      const linked = entry.overrideKey && !drafts.removedOverrides.has(entry.overrideKey)
        ? findProfile(entry.overrideKey)
        : null;
      const parentProfile = Number(stateReferenceRaw(parent));
      const overrideProfile = linked ? Number(stateReferenceRaw(linked)) : CONDITIONAL_PROFILE_NONE_VALUE;
      if (!Number.isInteger(parentProfile) || !Number.isInteger(overrideProfile)) return [];
      return [{
        parentProfile,
        overrideProfile,
        terrainMask: terrainPolicyMaskNumber(entry.terrainMask),
        terrainOverrideMask: terrainPolicyMaskNumber(entry.terrainOverrideMask),
        minMovementSpeed: conditionalMovementSpeed(entry.minMovementSpeed),
        maxMovementSpeed: conditionalMovementSpeed(entry.maxMovementSpeed),
      }];
    });
  }

  function overridePayload() {
    const add = [];
    const edit = {};
    const rename = {};
    const replaceTargets = {};
    const remove = new Set();

    for (const profile of savedOverrideProfiles()) {
      const key = profileKey(profile);
      const orders = ordersFor(profile);
      const replacingTarget = drafts.overrideTargets.has(key) && !drafts.removedOverrides.has(key);
      if (drafts.removedOverrides.has(key)) orders.forEach((order) => remove.add(order));
      if (drafts.removedOverrides.has(key)) continue;

      if (replacingTarget) {
        replaceTargets[orders[0]] = targetFor(profile);
      }

      const fieldEdits = drafts.overrideFields.get(key);
      if (fieldEdits?.size) {
        const serializedFields = Object.fromEntries(completeCoupledOverrideFieldEdits(profile, fieldEdits));
        for (const order of orders) edit[order] = serializedFields;
      }
      if (drafts.overrideNames.has(key)) {
        for (const order of orders) rename[order] = drafts.overrideNames.get(key);
      }
    }

    for (const draft of drafts.newOverrides) {
      add.push({ name: draft.name, fields: { ...draft.fields }, target: cloneTarget(draft.target) });
    }

    const reorder = orderChanged() ? orderedSavedOverrides().map((profile) => ordersFor(profile)) : [];
    const conditionalStatesChanged = drafts.conditionalStates !== null
      || currentConditionalStates().some((entry) => (
        drafts.removedOverrides.has(entry.parentKey)
        || (entry.overrideKey && drafts.removedOverrides.has(entry.overrideKey))
      ));
    const payload = {
      add,
      edit,
      rename,
      replaceTargets,
      remove: [...remove],
      reorder,
      ...(conditionalStatesChanged ? { conditionalStates: serializedConditionalStates() } : {}),
    };
    return add.length || Object.keys(edit).length || Object.keys(rename).length || Object.keys(replaceTargets).length
      || remove.size || reorder.length || conditionalStatesChanged ? { changes: payload } : null;
  }

  function commitPayload() {
    const profileChanges = {};
    for (const [key, fields] of drafts.baseFields) {
      const profile = baseProfiles().find((item) => profileKey(item) === key);
      if (profile && fields.size) profileChanges[profile.index] = Object.fromEntries(fields);
    }

    const membershipChanges = {};
    for (const [symbol, targetKey] of drafts.memberships) {
      const target = baseProfiles().find((profile) => profileKey(profile) === targetKey);
      const original = originalBaseForSpecies(symbol);
      if (target && (!original || String(target.index) !== String(original.index))) membershipChanges[symbol] = target.index;
    }

    return {
      profiles: Object.keys(profileChanges).length ? { changes: profileChanges } : null,
      profileMemberships: Object.keys(membershipChanges).length ? { changes: membershipChanges } : null,
      profileOverrides: overridePayload(),
    };
  }

  function committedDomains(value) {
    if (!value) return new Set(["profiles", "profileMemberships", "profileOverrides"]);
    if (Array.isArray(value)) return new Set(value);
    if (Array.isArray(value.changedDomains)) return new Set(value.changedDomains);
    if (typeof value === "string") return new Set([value]);
    return new Set(Object.keys(value).filter((key) => value[key]));
  }

  function clearCommitted(committed = null) {
    const domains = committedDomains(committed);
    ui.selectionHint = nameFor(findProfile());
    if (domains.has("profileOverrides")) {
      ui.pendingLifecycleProfiles = overrideProfiles()
        .filter((profile) => ui.selectedKey === profileKey(profile))
        .map((profile) => ({ key: profileKey(profile), name: nameFor(profile), selected: true }));
    }
    if (domains.has("profiles")) drafts.baseFields.clear();
    if (domains.has("profileMemberships")) drafts.memberships.clear();
    if (domains.has("profileOverrides")) {
      drafts.overrideFields.clear();
      drafts.overrideNames.clear();
      drafts.overrideTargets.clear();
      drafts.conditionalStates = null;
      drafts.removedOverrides.clear();
      drafts.newOverrides = [];
      drafts.overrideOrder = [];
    }
    renderAll();
  }

  function reset() {
    ui.selectionHint = nameFor(findProfile());
    ui.pendingLifecycleProfiles = [];
    drafts.baseFields.clear();
    drafts.overrideFields.clear();
    drafts.memberships.clear();
    drafts.overrideNames.clear();
    drafts.overrideTargets.clear();
    drafts.conditionalStates = null;
    drafts.removedOverrides.clear();
    drafts.newOverrides = [];
    drafts.overrideOrder = [];
    status("Profile drafts reset.", "info");
    renderAll();
  }

  function pruneDrafts() {
    // Keep unmatched draft keys so validation can surface source deletions, but
    // discard edits that the refreshed source now satisfies. This is important
    // after conflict recovery: an idempotent save must not stay permanently dirty.
    const profilesByKey = new Map([...baseProfiles(), ...savedOverrideProfiles()].map((profile) => [profileKey(profile), profile]));
    for (const store of [drafts.baseFields, drafts.overrideFields]) {
      for (const [key, fields] of store) {
        const profile = profilesByKey.get(key);
        if (!profile) continue;
        for (const [fieldKey, raw] of fields) {
          if (String(raw) === originalFieldRaw(profile, fieldKey)) fields.delete(fieldKey);
        }
        if (!fields.size) store.delete(key);
      }
    }
    for (const [key, name] of drafts.overrideNames) {
      const profile = profilesByKey.get(key);
      if (profile && String(name) === String(profile.name || profile.symbol || "")) drafts.overrideNames.delete(key);
    }
    for (const [key, target] of drafts.overrideTargets) {
      const profile = profilesByKey.get(key);
      if (profile && JSON.stringify(cloneTarget(target)) === JSON.stringify(sourceTarget(profile))) drafts.overrideTargets.delete(key);
    }
    if (drafts.conditionalStates !== null && conditionalStatesEqual(drafts.conditionalStates, sourceConditionalStates())) {
      drafts.conditionalStates = null;
    }
  }

  function refresh(nextData) {
    if (!nextData || typeof nextData !== "object") return;
    ui.selectionHint = ui.selectionHint || nameFor(findProfile());
    data = normalizeData(nextData);
    state.profileData = data;
    if (ui.pendingLifecycleProfiles.length) {
      const overridesByName = new Map(savedOverrideProfiles().map((profile) => [nameFor(profile).trim().toLowerCase(), profile]));
      for (const pending of ui.pendingLifecycleProfiles) {
        const promoted = overridesByName.get(pending.name.trim().toLowerCase());
        if (!promoted) continue;
        const promotedKey = profileKey(promoted);
        if (pending.selected) {
          ui.selectedKey = promotedKey;
          ui.selectionHint = nameFor(promoted);
        }
      }
      ui.pendingLifecycleProfiles = [];
    }
    pruneDrafts();
    ui.contextResult = null;
    ui.contextError = data.profilesAvailable === false ? (data.profileError?.message || "Profiles are unavailable in this source state.") : "";
    renderAll();
  }

  function exportDraft() {
    const mapOfMaps = (store) => [...store].map(([key, fields]) => [key, [...fields]]);
    return {
      version: 2,
      baseFields: mapOfMaps(drafts.baseFields),
      overrideFields: mapOfMaps(drafts.overrideFields),
      memberships: [...drafts.memberships],
      overrideNames: [...drafts.overrideNames],
      overrideTargets: [...drafts.overrideTargets].map(([key, target]) => [key, cloneTarget(target)]),
      conditionalStates: drafts.conditionalStates === null ? null : drafts.conditionalStates.map(cloneConditionalState),
      removedOverrides: [...drafts.removedOverrides],
      newOverrides: cloneDraftJson(drafts.newOverrides),
      overrideOrder: [...drafts.overrideOrder],
    };
  }

  function prepareDraftImport(snapshot) {
    if (!snapshot || typeof snapshot !== "object" || ![1, 2].includes(snapshot.version)) {
      throw new TypeError("Profile draft backup version is not supported.");
    }
    const mapOfMaps = (value, label) => new Map(draftEntryList(value, label).map(([key, entries]) => [
      key,
      new Map(draftEntryList(entries, `${label}.${key}`).map(([field, raw]) => {
        if (typeof raw !== "string") throw new TypeError(`${label}.${key}.${field} must be text.`);
        return [field, raw];
      })),
    ]));
    const stringMap = (value, label) => new Map(draftEntryList(value, label).map(([key, raw]) => {
      if (typeof raw !== "string") throw new TypeError(`${label}.${key} must be text.`);
      return [key, raw];
    }));
    const importedTarget = (target, label) => {
      if (!target || typeof target !== "object" || Array.isArray(target)
          || !Array.isArray(target.members) || !target.match || typeof target.match !== "object"
          || !["disabled", "members", "all"].includes(target.targetMode)) {
        throw new TypeError(`${label} is malformed.`);
      }
      const species = new Set(speciesEntries().map((entry) => entry.symbol));
      if (!target.members.every((member) => typeof member === "string" && species.has(member))) {
        throw new TypeError(`${label} contains an unknown Pokémon.`);
      }
      for (const [field] of MATCH_FIELDS) {
        if (typeof target.match[field] !== "string") throw new TypeError(`${label}.${field} must be text.`);
      }
      return cloneTarget(target);
    };
    const importedConditionalStates = snapshot.conditionalStates === undefined || snapshot.conditionalStates === null
      ? null
      : (() => {
        if (!Array.isArray(snapshot.conditionalStates)) throw new TypeError("Profile conditionalStates must be an array.");
        return snapshot.conditionalStates.map((entry, index) => {
          if (!entry || typeof entry !== "object" || Array.isArray(entry)
              || typeof entry.parentKey !== "string"
              || (entry.overrideKey !== null && typeof entry.overrideKey !== "string")) {
            throw new TypeError(`Profile conditionalStates.${index} is malformed.`);
          }
          if (snapshot.version >= 2) {
            const numericFields = ["terrainMask", "terrainOverrideMask", "minMovementSpeed", "maxMovementSpeed"];
            if (numericFields.some((field) => !Number.isInteger(Number(entry[field])))) {
              throw new TypeError(`Profile conditionalStates.${index} has invalid condition values.`);
            }
            const explicit = Number(entry.terrainOverrideMask);
            const accepted = Number(entry.terrainMask);
            const minSpeed = Number(entry.minMovementSpeed);
            const maxSpeed = Number(entry.maxMovementSpeed);
            if (explicit < 0 || accepted < 0 || (accepted & ~explicit)
                || minSpeed < 0 || maxSpeed > CONDITIONAL_MOVEMENT_SPEED_MAX
                || ((!minSpeed && maxSpeed) || (minSpeed && !maxSpeed) || minSpeed > maxSpeed)) {
              throw new TypeError(`Profile conditionalStates.${index} has an invalid tile or movement speed condition.`);
            }
          }
          return cloneConditionalState(entry);
        });
      })();
    if (!Array.isArray(snapshot.removedOverrides) || !snapshot.removedOverrides.every((key) => typeof key === "string")) {
      throw new TypeError("Profile removedOverrides must contain profile keys.");
    }
    if (!Array.isArray(snapshot.overrideOrder) || !snapshot.overrideOrder.every((key) => typeof key === "string")) {
      throw new TypeError("Profile overrideOrder must contain profile keys.");
    }
    if (!Array.isArray(snapshot.newOverrides)) throw new TypeError("Profile newOverrides must be an array.");
    const overrideTargets = new Map(draftEntryList(snapshot.overrideTargets, "Profile overrideTargets").map(([key, target]) => [key, importedTarget(target, `Profile overrideTargets.${key}`)]));
    const newOverrides = snapshot.newOverrides.map((draft) => {
      if (!draft || typeof draft !== "object" || Array.isArray(draft)
          || typeof draft.draftId !== "string" || typeof draft.name !== "string"
          || !draft.fields || typeof draft.fields !== "object" || Array.isArray(draft.fields)) {
        throw new TypeError("Profile newOverrides contains an invalid draft.");
      }
      for (const [field, raw] of Object.entries(draft.fields)) {
        if (typeof raw !== "string") throw new TypeError(`Profile new override ${draft.draftId}.${field} must be text.`);
      }
      return { ...cloneDraftJson(draft), target: importedTarget(draft.target, `Profile new override ${draft.draftId}.target`) };
    });
    if (new Set(snapshot.removedOverrides).size !== snapshot.removedOverrides.length
        || new Set(snapshot.overrideOrder).size !== snapshot.overrideOrder.length
        || new Set(newOverrides.map((draft) => draft.draftId)).size !== newOverrides.length) {
      throw new TypeError("Profile draft backup contains duplicate identities.");
    }
    const baseFields = mapOfMaps(snapshot.baseFields, "Profile baseFields");
    const overrideFields = mapOfMaps(snapshot.overrideFields, "Profile overrideFields");
    const memberships = stringMap(snapshot.memberships, "Profile memberships");
    const overrideNames = stringMap(snapshot.overrideNames, "Profile overrideNames");
    const knownFields = new Set(data.fields.map((field) => field.key));
    const knownBaseKeys = new Set(baseProfiles().map(profileKey));
    const knownOverrideKeys = new Set(savedOverrideProfiles().map(profileKey));
    if (importedConditionalStates?.some((entry) => (
      !knownOverrideKeys.has(entry.parentKey)
      || (entry.overrideKey && !knownOverrideKeys.has(entry.overrideKey))
    ))) {
      throw new TypeError("Profile conditionalStates refers to an unknown override profile.");
    }
    for (const [key, fields] of [...baseFields, ...overrideFields]) {
      const knownKeys = baseFields.has(key) ? knownBaseKeys : knownOverrideKeys;
      if (!knownKeys.has(key) || [...fields.keys()].some((field) => !knownFields.has(field))) {
        throw new TypeError("Profile draft backup refers to an unknown profile or field.");
      }
    }
    for (const [species, targetKey] of memberships) {
      if (!speciesEntries().some((entry) => entry.symbol === species) || !knownBaseKeys.has(targetKey)) {
        throw new TypeError("Profile membership backup refers to an unknown Pokémon or base profile.");
      }
    }
    if ([...overrideNames.keys(), ...overrideTargets.keys(), ...snapshot.removedOverrides, ...snapshot.overrideOrder]
      .some((key) => !knownOverrideKeys.has(key))) {
      throw new TypeError("Profile draft backup refers to an unknown override profile.");
    }
    if (newOverrides.some((draft) => Object.keys(draft.fields).some((field) => !knownFields.has(field)))) {
      throw new TypeError("Profile new override refers to an unknown field.");
    }
    return {
      version: 2,
      baseFields,
      overrideFields,
      memberships,
      overrideNames,
      overrideTargets,
      conditionalStates: importedConditionalStates,
      removedOverrides: new Set(snapshot.removedOverrides),
      newOverrides,
      overrideOrder: [...snapshot.overrideOrder],
    };
  }

  function applyDraftImport(prepared) {
    Object.assign(drafts, prepared);
    invalidNumericOperatorInputs.clear();
    ui.selectionHint = nameFor(findProfile());
    pruneDrafts();
    renderAll();
  }

  function destroy() {
    if (ui.destroyed) return;
    ui.destroyed = true;
    if (formulaRefreshTimer !== null) window.clearTimeout(formulaRefreshTimer);
    contextAbortController?.abort();
    root.removeEventListener("click", onClick);
    root.removeEventListener("input", onInput);
    root.removeEventListener("change", onChange);
    root.removeEventListener("focusout", onFocusOut);
    root.removeEventListener("toggle", onToggle, true);
    root.removeEventListener("submit", onSubmit);
    root.removeEventListener("keydown", onKeyDown);
    root.removeEventListener("dragstart", onDragStart);
    root.removeEventListener("dragover", onDragOver);
    root.removeEventListener("drop", onDrop);
    root.removeEventListener("dragend", onDragEnd);
    root.classList.remove("profile-controller-ready", "pv2");
    listElement.classList.remove("pv2-profile-list");
    editorElement.classList.remove("pv2-editor");
    contextElement.classList.remove("pv2-context");
    announcerElement.remove();
    dialogElement.remove();
    listElement.replaceChildren();
    editorElement.replaceChildren();
    contextElement.replaceChildren();
  }

  if (data.profilesAvailable === false) {
    ui.contextError = data.profileError?.message || "Profiles are unavailable in this source state.";
  }
  renderAll();

  return Object.freeze({
    hasChanges,
    changeCount,
    hasInvalid: () => profileValidationErrors().length > 0,
    validationCount: () => profileValidationErrors().length,
    validationMessage: () => profileValidationErrors()[0] || "",
    focusFirstInvalid: () => {
      const target = editorElement.querySelector("[data-stale-drafts], [aria-invalid='true']") || editorElement;
      target.tabIndex = -1;
      requestAnimationFrame(() => target.focus({ preventScroll: true }));
    },
    commitPayload,
    exportDraft,
    prepareDraftImport,
    applyDraftImport,
    clearCommitted,
    reset,
    refresh,
    navigationContext: () => ({ selection: ui.selectedKey, label: nameFor(findProfile()) }),
    restoreSelection: (key, options = {}) => setSelected(key, { ...options, report: false }),
    destroy,
  });
}
