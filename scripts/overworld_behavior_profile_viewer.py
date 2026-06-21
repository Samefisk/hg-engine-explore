#!/usr/bin/env python3
"""Serve a dynamic overview of overworld wild behavior profiles.

The viewer keeps the C tables as the source of truth.  It parses the current
runtime overlay and behavior-data overlay on every /data.json request, resolves
class rules and variable overrides in the same order as the runtime resolver,
and exposes the result to a small browser UI.
"""

from __future__ import annotations

import argparse
import ast
import copy
import datetime as _dt
import gzip
import hashlib
import io
import json
import operator
import os
import pty
import re
import select
import shlex
import signal
import struct
import subprocess
import sys
import threading
import time
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OVERLAY_SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
HELPER_SOURCE = ROOT / "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c"
BEHAVIOR_DATA_SOURCE = ROOT / "data/OverworldWildBehaviorData.c"
BEHAVIOR_DATA_HEADER = ROOT / "include/overworld_wild_behavior_data.h"
SPECIES_HEADER = ROOT / "include/constants/species.h"
MAPS_HEADER = ROOT / "include/constants/maps.h"
ARMIPS_SPECIES_INC = ROOT / "asm/include/species.inc"
SPAWNS_PUBLIC_HEADER = ROOT / "include/overworld_wild_spawns.h"
SPAWNS_INTERNAL_HEADER = ROOT / "include/overworld_wild_spawns_internal.h"

BLOB_BEHAVIOR_FIELD_INDEXES = {
    "sOverworldWildBehaviorClassProfiles": 1,
    "sOverworldWildBehaviorClassRules": 2,
    "sOverworldWildBehaviorSpeciesClassRules": 3,
    "sOverworldWildBehaviorOverrides": 4,
}
OWBD_COUNT_DEFINES = {
    "OWBD_CLASS_PROFILE_COUNT": "sOverworldWildBehaviorClassProfiles",
    "OWBD_CLASS_RULE_COUNT": "sOverworldWildBehaviorClassRules",
    "OWBD_SPECIES_CLASS_RULE_COUNT": "sOverworldWildBehaviorSpeciesClassRules",
    "OWBD_OVERRIDE_COUNT": "sOverworldWildBehaviorOverrides",
}
ENEMY_PARTY_SOURCE = ROOT / "src/field/enemy_party.c"
POKEGRA_MK = ROOT / "data/graphics/pokegra.mk"
POKE_FORM_DATA = ROOT / "data/PokeFormDataTbl.c"
ENCOUNTERS_SOURCE = ROOT / "armips/data/encounters.s"
HEADBUTT_SOURCE = ROOT / "armips/data/headbutt.s"
MONDATA_SOURCE = ROOT / "armips/data/mondata.s"
ARMIPS_CONSTANTS = ROOT / "armips/include/constants.s"
ARMIPS_CONFIG = ROOT / "armips/include/config.s"
TEST_NDS = ROOT / "test.nds"
DEFAULT_TEST_DSV = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test.dsv"
TEST_DSV = Path(os.environ.get("HG_ENGINE_TEST_DSV", str(DEFAULT_TEST_DSV))).expanduser()
BUILD_COMMAND = "./docker-makerom.cmd"
BUILD_OUTPUT_LIMIT = 60000
BUILD_STARTUP_TIMEOUT_SECONDS = 45
BUILD_STARTUP_TIMEOUT_CODE = 124
DSV_RAW_SAVE_SIZE = 0x80000
SAVE_COPY_BASES = (0x0, 0x40000)
SAVE_NORMAL_SLOT_SIZE = 0xFFA0
SAVE_CHUNK_FOOTER_SIZE = 0x10
SAVE_CHUNK_MAGIC = 0x20060623
OVERWORLD_WILD_SHINY_BASE_ODDS = 8192
OVERWORLD_WILD_SHINY_COUNTER_MAX = OVERWORLD_WILD_SHINY_BASE_ODDS - 1
OVERWORLD_WILD_SHINY_COUNTER_MAGIC = 0x4F57
# Sav2_Misc_get uses save-array id 9. Its block starts at 0x2064 and the
# counter fields live at SAVE_MISC_DATA offsets 0x29C/0x29E.
OVERWORLD_WILD_SHINY_COUNTER_SAVE_OFFSET = 0x2064 + 0x29C
OVERWORLD_WILD_SHINY_MAGIC_SAVE_OFFSET = 0x2064 + 0x29E
BUILD_LOCK = threading.Lock()
BUILD_STATE_LOCK = threading.Lock()
BUILD_STATE = {
    "running": False,
    "startedAt": None,
    "endedAt": None,
    "command": BUILD_COMMAND,
    "output": "",
    "latestLine": "",
    "ok": None,
    "code": None,
    "error": None,
    "open": None,
    "openError": None,
    "testNdsExists": TEST_NDS.exists(),
    "testNdsPath": str(TEST_NDS),
}
DATA_SOURCE_FILES = (
    OVERLAY_SOURCE,
    HELPER_SOURCE,
    BEHAVIOR_DATA_SOURCE,
    BEHAVIOR_DATA_HEADER,
    SPECIES_HEADER,
    MAPS_HEADER,
    SPAWNS_PUBLIC_HEADER,
    SPAWNS_INTERNAL_HEADER,
    ENEMY_PARTY_SOURCE,
    ARMIPS_SPECIES_INC,
    POKEGRA_MK,
    POKE_FORM_DATA,
    ENCOUNTERS_SOURCE,
    HEADBUTT_SOURCE,
    MONDATA_SOURCE,
    ARMIPS_CONSTANTS,
    ARMIPS_CONFIG,
)
DEFINE_SOURCE_FILES = [
    SPECIES_HEADER,
    MAPS_HEADER,
    SPAWNS_PUBLIC_HEADER,
    SPAWNS_INTERNAL_HEADER,
    BEHAVIOR_DATA_HEADER,
    OVERLAY_SOURCE,
    HELPER_SOURCE,
    BEHAVIOR_DATA_SOURCE,
    ENEMY_PARTY_SOURCE,
]
DATA_CACHE_LOCK = threading.Lock()
DATA_JSON_CACHE = {
    "key": None,
    "body": b"",
    "gzip": b"",
    "etag": "",
}

PROFILE_FIELDS = [
    "chillState",
    "alertState",
    "alertEmote",
    "alertTime",
    "alertness",
    "attentiveState",
    "stamina",
    "tiredState",
    "restTime",
    "chillSpeed",
    "attentiveSpeed",
    "tiredSpeed",
    "range",
    "jumpLevel",
    "profileId",
    "spawnState",
    "chillAction",
    "chillTarget",
    "alertRange",
    "attentiveAction",
    "targetSelector",
    "movementStyle",
    "chillCooldown",
    "attentiveCooldown",
    "alertChance",
    "spawnDestination",
    "chillBattle",
    "alertBattle",
    "attentiveBattle",
    "tiredBattle",
    "specialAction",
    "hopAllowNonCardinal",
    "hopMinDistance",
    "hopMaxDistance",
    "hopPause",
    "teleportTime",
    "teleportPause",
    "alertSpecialAction",
    "alertCallSpawnAmount",
    "alertCallSpawnState",
    "spawnDestinationMinDistance",
    "spawnDestinationMaxDistance",
    "ramAccelerationSteps",
    "ramMaxSpeed",
    "chillAllowedTile",
    "attentiveAllowedTile",
    "tiredAllowedTile",
    "chillAllowedTile2",
    "attentiveAllowedTile2",
    "tiredAllowedTile2",
    "attentiveHopAllowNonCardinal",
    "attentiveHopMinDistance",
    "attentiveHopMaxDistance",
    "attentiveHopPause",
    "attentiveTeleportTime",
    "attentiveTeleportPause",
    "attentiveRamAccelerationSteps",
    "attentiveRamMaxSpeed",
    "tiredHopAllowNonCardinal",
    "tiredHopMinDistance",
    "tiredHopMaxDistance",
    "tiredHopPause",
    "tiredTeleportTime",
    "tiredTeleportPause",
    "tiredRamAccelerationSteps",
    "tiredRamMaxSpeed",
]

MATCH_FIELDS = [
    "groupMask",
    "species",
    "terrain",
    "minLevel",
    "maxLevel",
    "shiny",
    "behaviorClass",
]

FIELD_LABELS = {
    "chillState": "Behavior",
    "alertState": "Alert mode",
    "alertEmote": "Alert emote",
    "alertTime": "Time",
    "alertness": "Range length",
    "attentiveState": "Behavior",
    "stamina": "Stamina",
    "tiredState": "Behavior",
    "restTime": "Rest",
    "chillSpeed": "Speed",
    "attentiveSpeed": "Speed",
    "tiredSpeed": "Speed",
    "range": "Range",
    "jumpLevel": "Jump",
    "profileId": "Behavior family",
    "spawnState": "Spawn state",
    "chillAction": "Movement style",
    "chillTarget": "Target",
    "alertRange": "Range type",
    "attentiveAction": "Legacy response",
    "targetSelector": "Target",
    "movementStyle": "Movement style",
    "chillCooldown": "Chill cooldown",
    "attentiveCooldown": "Active cooldown",
    "alertChance": "Alert chance",
    "spawnDestination": "Spawn destination",
    "chillBattle": "Chill",
    "alertBattle": "Alert",
    "attentiveBattle": "Active",
    "tiredBattle": "Tired",
    "specialAction": "Movement style",
    "hopAllowNonCardinal": "Allow non-cardinal",
    "hopMinDistance": "Min hop distance",
    "hopMaxDistance": "Max hop distance",
    "hopPause": "Hop pause",
    "teleportTime": "Teleport time",
    "teleportPause": "Teleport pause",
    "alertSpecialAction": "Special action",
    "alertCallSpawnAmount": "Spawn amount",
    "alertCallSpawnState": "Spawn state",
    "spawnDestinationMinDistance": "Min distance",
    "spawnDestinationMaxDistance": "Max distance",
    "ramAccelerationSteps": "Accelerate every",
    "ramMaxSpeed": "Max speed",
    "chillAllowedTile": "Allowed tile",
    "attentiveAllowedTile": "Allowed tile",
    "tiredAllowedTile": "Allowed tile",
    "chillAllowedTile2": "Allowed tile 2",
    "attentiveAllowedTile2": "Allowed tile 2",
    "tiredAllowedTile2": "Allowed tile 2",
    "attentiveHopAllowNonCardinal": "Allow non-cardinal",
    "attentiveHopMinDistance": "Min hop distance",
    "attentiveHopMaxDistance": "Max hop distance",
    "attentiveHopPause": "Hop pause",
    "attentiveTeleportTime": "Teleport time",
    "attentiveTeleportPause": "Teleport pause",
    "attentiveRamAccelerationSteps": "Accelerate every",
    "attentiveRamMaxSpeed": "Max speed",
    "tiredHopAllowNonCardinal": "Allow non-cardinal",
    "tiredHopMinDistance": "Min hop distance",
    "tiredHopMaxDistance": "Max hop distance",
    "tiredHopPause": "Hop pause",
    "tiredTeleportTime": "Teleport time",
    "tiredTeleportPause": "Teleport pause",
    "tiredRamAccelerationSteps": "Accelerate every",
    "tiredRamMaxSpeed": "Max speed",
}

PRIMITIVE_FIELDS = [
    "spawnLocomotion",
    "chillLocomotion",
    "chillTarget",
    "alertLogic",
    "alertReaction",
    "attentiveLocomotion",
    "attentiveTarget",
    "activeReaction",
    "tiredReaction",
]

PRIMITIVE_FIELD_LABELS = {
    "spawnLocomotion": "Spawn locomotion",
    "chillLocomotion": "Chill locomotion",
    "chillTarget": "Chill target",
    "alertLogic": "Range logic",
    "alertReaction": "Alert reaction",
    "attentiveLocomotion": "Active locomotion",
    "attentiveTarget": "Active target",
    "activeReaction": "Active reaction",
    "tiredReaction": "Tired reaction",
}

FIELD_PREFIXES = {
    "chillState": "OW_WILD_BEHAVIOR_KIND_",
    "alertState": "OW_WILD_BEHAVIOR_ALERT_STATE_",
    "alertEmote": "OW_WILD_SPAWNER_BUBBLE_ID_",
    "attentiveState": "OW_WILD_BEHAVIOR_KIND_",
    "tiredState": "OW_WILD_BEHAVIOR_KIND_",
    "jumpLevel": "OW_WILD_BEHAVIOR_JUMP_LEVEL_",
    "profileId": "OW_WILD_BEHAVIOR_PROFILE_",
    "spawnState": "OW_WILD_BEHAVIOR_SPAWN_STATE_",
    "chillAction": "OW_WILD_BEHAVIOR_LOCOMOTION_",
    "alertRange": "OW_WILD_BEHAVIOR_ALERT_RANGE_",
    "attentiveAction": "OW_WILD_BEHAVIOR_ATTENTIVE_ACTION_",
    "targetSelector": "OW_WILD_BEHAVIOR_TARGET_",
    "chillAllowedTile": "OW_WILD_BEHAVIOR_ALLOWED_TILE_",
    "attentiveAllowedTile": "OW_WILD_BEHAVIOR_ALLOWED_TILE_",
    "tiredAllowedTile": "OW_WILD_BEHAVIOR_ALLOWED_TILE_",
    "chillAllowedTile2": "OW_WILD_BEHAVIOR_ALLOWED_TILE_",
    "attentiveAllowedTile2": "OW_WILD_BEHAVIOR_ALLOWED_TILE_",
    "tiredAllowedTile2": "OW_WILD_BEHAVIOR_ALLOWED_TILE_",
    "movementStyle": "OW_WILD_BEHAVIOR_LOCOMOTION_",
    "spawnDestination": "OW_WILD_SPAWN_DESTINATION_",
    "chillBattle": "OW_WILD_BEHAVIOR_BATTLE_TRIGGER_",
    "alertBattle": "OW_WILD_BEHAVIOR_BATTLE_TRIGGER_",
    "attentiveBattle": "OW_WILD_BEHAVIOR_BATTLE_TRIGGER_",
    "tiredBattle": "OW_WILD_BEHAVIOR_BATTLE_TRIGGER_",
    "specialAction": "OW_WILD_BEHAVIOR_LOCOMOTION_",
    "hopAllowNonCardinal": "OW_WILD_BEHAVIOR_BOOL_",
    "attentiveHopAllowNonCardinal": "OW_WILD_BEHAVIOR_BOOL_",
    "tiredHopAllowNonCardinal": "OW_WILD_BEHAVIOR_BOOL_",
    "alertSpecialAction": "OW_WILD_BEHAVIOR_ALERT_SPECIAL_",
    "alertCallSpawnState": "OW_WILD_BEHAVIOR_ALERT_CALL_SPAWN_STATE_",
    "spawnLocomotion": "OW_WILD_BEHAVIOR_LOCOMOTION_",
    "chillLocomotion": "OW_WILD_BEHAVIOR_LOCOMOTION_",
    "chillTarget": "OW_WILD_BEHAVIOR_TARGET_",
    "alertLogic": "OW_WILD_BEHAVIOR_ALERT_LOGIC_",
    "alertReaction": "OW_WILD_BEHAVIOR_REACTION_",
    "attentiveLocomotion": "OW_WILD_BEHAVIOR_LOCOMOTION_",
    "attentiveTarget": "OW_WILD_BEHAVIOR_TARGET_",
    "activeReaction": "OW_WILD_BEHAVIOR_REACTION_",
    "tiredReaction": "OW_WILD_BEHAVIOR_REACTION_",
}

CANONICAL_BEHAVIOR_RAWS = [
    "OW_WILD_BEHAVIOR_KIND_NONE",
    "OW_WILD_BEHAVIOR_KIND_IDLE",
    "OW_WILD_BEHAVIOR_KIND_WANDER",
    "OW_WILD_BEHAVIOR_KIND_CHASE",
    "OW_WILD_BEHAVIOR_KIND_FLEE",
    "OW_WILD_BEHAVIOR_KIND_PLAYFUL",
    "OW_WILD_BEHAVIOR_KIND_RAM",
    "OW_WILD_BEHAVIOR_KIND_HEADBUTT_TREE_HOP",
    "OW_WILD_BEHAVIOR_KIND_ASLEEP",
    "OW_WILD_BEHAVIOR_KIND_SINGING",
    "OW_WILD_BEHAVIOR_KIND_TIRED_EMOTE",
    "OW_WILD_BEHAVIOR_KIND_NO_VISUAL",
]

CANONICAL_MOVEMENT_STYLE_RAWS = [
    "OW_WILD_BEHAVIOR_LOCOMOTION_NONE",
    "OW_WILD_BEHAVIOR_LOCOMOTION_WANDER",
    "OW_WILD_BEHAVIOR_LOCOMOTION_HOP",
    "OW_WILD_BEHAVIOR_LOCOMOTION_RAM",
    "OW_WILD_BEHAVIOR_LOCOMOTION_PHANTOM_TELEPORT",
]

CANONICAL_TARGET_RAWS = [
    "OW_WILD_BEHAVIOR_TARGET_NONE",
    "OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY",
    "OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER",
    "OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER",
    "OW_WILD_BEHAVIOR_TARGET_TREE_TOP",
    "OW_WILD_BEHAVIOR_TARGET_PLAYFUL_ORBIT",
    "OW_WILD_BEHAVIOR_TARGET_PLAYER_FRONT",
    "OW_WILD_BEHAVIOR_TARGET_SWARM",
]

CANONICAL_ALERT_SPECIAL_ACTION_RAWS = [
    "OW_WILD_BEHAVIOR_ALERT_SPECIAL_NONE",
    "OW_WILD_BEHAVIOR_ALERT_SPECIAL_CALL_FOR_HELP",
]

CANONICAL_ALERT_CALL_SPAWN_STATE_RAWS = [
    "OW_WILD_BEHAVIOR_ALERT_CALL_SPAWN_STATE_CHILL",
    "OW_WILD_BEHAVIOR_ALERT_CALL_SPAWN_STATE_ALERT",
    "OW_WILD_BEHAVIOR_ALERT_CALL_SPAWN_STATE_ACTIVE",
    "OW_WILD_BEHAVIOR_ALERT_CALL_SPAWN_STATE_TIRED",
]

CANONICAL_ALLOWED_TILE_RAWS = [
    "OW_WILD_BEHAVIOR_ALLOWED_TILE_LAND",
    "OW_WILD_BEHAVIOR_ALLOWED_TILE_WATER",
    "OW_WILD_BEHAVIOR_ALLOWED_TILE_CANOPY",
    "OW_WILD_BEHAVIOR_ALLOWED_TILE_GRASS",
    "OW_WILD_BEHAVIOR_ALLOWED_TILE_PLAYER",
    "OW_WILD_BEHAVIOR_ALLOWED_TILE_PLAYER_FRONT",
]

CANONICAL_SECONDARY_ALLOWED_TILE_RAWS = [
    "OW_WILD_BEHAVIOR_ALLOWED_TILE_NONE",
    *CANONICAL_ALLOWED_TILE_RAWS,
]

CANONICAL_PROFILE_FIELD_RAWS = {
    "chillState": CANONICAL_BEHAVIOR_RAWS,
    "attentiveState": CANONICAL_BEHAVIOR_RAWS,
    "tiredState": CANONICAL_BEHAVIOR_RAWS,
    "chillAction": CANONICAL_MOVEMENT_STYLE_RAWS,
    "chillTarget": CANONICAL_TARGET_RAWS,
    "movementStyle": CANONICAL_MOVEMENT_STYLE_RAWS,
    "targetSelector": CANONICAL_TARGET_RAWS,
    "specialAction": CANONICAL_MOVEMENT_STYLE_RAWS,
    "alertSpecialAction": CANONICAL_ALERT_SPECIAL_ACTION_RAWS,
    "alertCallSpawnState": CANONICAL_ALERT_CALL_SPAWN_STATE_RAWS,
    "chillAllowedTile": CANONICAL_ALLOWED_TILE_RAWS,
    "attentiveAllowedTile": CANONICAL_ALLOWED_TILE_RAWS,
    "tiredAllowedTile": CANONICAL_ALLOWED_TILE_RAWS,
    "chillAllowedTile2": CANONICAL_SECONDARY_ALLOWED_TILE_RAWS,
    "attentiveAllowedTile2": CANONICAL_SECONDARY_ALLOWED_TILE_RAWS,
    "tiredAllowedTile2": CANONICAL_SECONDARY_ALLOWED_TILE_RAWS,
    "attentiveHopAllowNonCardinal": ["OW_WILD_BEHAVIOR_BOOL_NO", "OW_WILD_BEHAVIOR_BOOL_YES"],
    "tiredHopAllowNonCardinal": ["OW_WILD_BEHAVIOR_BOOL_NO", "OW_WILD_BEHAVIOR_BOOL_YES"],
}

OVERRIDE1_FIELDS = {
    "OW_WILD_BEHAVIOR_OVERRIDE_CHILL_STATE": "chillState",
    "OW_WILD_BEHAVIOR_OVERRIDE_ALERT_STATE": "alertState",
    "OW_WILD_BEHAVIOR_OVERRIDE_ALERT_EMOTE": "alertEmote",
    "OW_WILD_BEHAVIOR_OVERRIDE_ALERT_TIME": "alertTime",
    "OW_WILD_BEHAVIOR_OVERRIDE_ALERTNESS": "alertness",
    "OW_WILD_BEHAVIOR_OVERRIDE_ATTENTIVE_STATE": "attentiveState",
    "OW_WILD_BEHAVIOR_OVERRIDE_STAMINA": "stamina",
    "OW_WILD_BEHAVIOR_OVERRIDE_TIRED_STATE": "tiredState",
    "OW_WILD_BEHAVIOR_OVERRIDE_REST_TIME": "restTime",
    "OW_WILD_BEHAVIOR_OVERRIDE_NORMAL_SPEED": "chillSpeed",
    "OW_WILD_BEHAVIOR_OVERRIDE_MAX_SPEED": "attentiveSpeed",
    "OW_WILD_BEHAVIOR_OVERRIDE_CHILL_SPEED": "chillSpeed",
    "OW_WILD_BEHAVIOR_OVERRIDE_ATTENTIVE_SPEED": "attentiveSpeed",
    "OW_WILD_BEHAVIOR_OVERRIDE_TIRED_SPEED": "tiredSpeed",
    "OW_WILD_BEHAVIOR_OVERRIDE_RANGE": "range",
    "OW_WILD_BEHAVIOR_OVERRIDE_JUMP_LEVEL": "jumpLevel",
    "OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_ID": "profileId",
    "OW_WILD_BEHAVIOR_OVERRIDE_SPAWN_STATE": "spawnState",
    "OW_WILD_BEHAVIOR_OVERRIDE_CHILL_ACTION": "chillAction",
    "OW_WILD_BEHAVIOR_OVERRIDE_ALERT_RANGE": "alertRange",
    "OW_WILD_BEHAVIOR_OVERRIDE_TARGET_SELECTOR": "targetSelector",
    "OW_WILD_BEHAVIOR_OVERRIDE_MOVEMENT_STYLE": "movementStyle",
    "OW_WILD_BEHAVIOR_OVERRIDE_CHILL_COOLDOWN": "chillCooldown",
    "OW_WILD_BEHAVIOR_OVERRIDE_ATTENTIVE_COOLDOWN": "attentiveCooldown",
    "OW_WILD_BEHAVIOR_OVERRIDE_ALERT_CHANCE": "alertChance",
    "OW_WILD_BEHAVIOR_OVERRIDE_SPAWN_DESTINATION": "spawnDestination",
    "OW_WILD_BEHAVIOR_OVERRIDE_CHILL_BATTLE": "chillBattle",
    "OW_WILD_BEHAVIOR_OVERRIDE_ALERT_BATTLE": "alertBattle",
    "OW_WILD_BEHAVIOR_OVERRIDE_ATTENTIVE_BATTLE": "attentiveBattle",
    "OW_WILD_BEHAVIOR_OVERRIDE_TIRED_BATTLE": "tiredBattle",
    "OW_WILD_BEHAVIOR_OVERRIDE_SPECIAL_ACTION": "specialAction",
    "OW_WILD_BEHAVIOR_OVERRIDE_HOP_ALLOW_NON_CARDINAL": "hopAllowNonCardinal",
    "OW_WILD_BEHAVIOR_OVERRIDE_HOP_MIN_DISTANCE": "hopMinDistance",
    "OW_WILD_BEHAVIOR_OVERRIDE_HOP_MAX_DISTANCE": "hopMaxDistance",
}

OVERRIDE2_FIELDS = {
    "OW_WILD_BEHAVIOR_OVERRIDE2_HOP_PAUSE": "hopPause",
    "OW_WILD_BEHAVIOR_OVERRIDE2_TELEPORT_TIME": "teleportTime",
    "OW_WILD_BEHAVIOR_OVERRIDE2_TELEPORT_PAUSE": "teleportPause",
    "OW_WILD_BEHAVIOR_OVERRIDE2_ALERT_SPECIAL_ACTION": "alertSpecialAction",
    "OW_WILD_BEHAVIOR_OVERRIDE2_ALERT_CALL_SPAWN_AMOUNT": "alertCallSpawnAmount",
    "OW_WILD_BEHAVIOR_OVERRIDE2_SPAWN_DESTINATION_MIN_DISTANCE": "spawnDestinationMinDistance",
    "OW_WILD_BEHAVIOR_OVERRIDE2_SPAWN_DESTINATION_MAX_DISTANCE": "spawnDestinationMaxDistance",
    "OW_WILD_BEHAVIOR_OVERRIDE2_RAM_ACCELERATION_STEPS": "ramAccelerationSteps",
    "OW_WILD_BEHAVIOR_OVERRIDE2_RAM_MAX_SPEED": "ramMaxSpeed",
    "OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_ALLOWED_TILE": "chillAllowedTile",
    "OW_WILD_BEHAVIOR_OVERRIDE2_ATTENTIVE_ALLOWED_TILE": "attentiveAllowedTile",
    "OW_WILD_BEHAVIOR_OVERRIDE2_TIRED_ALLOWED_TILE": "tiredAllowedTile",
    "OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_ALLOWED_TILE_2": "chillAllowedTile2",
    "OW_WILD_BEHAVIOR_OVERRIDE2_ATTENTIVE_ALLOWED_TILE_2": "attentiveAllowedTile2",
    "OW_WILD_BEHAVIOR_OVERRIDE2_TIRED_ALLOWED_TILE_2": "tiredAllowedTile2",
    "OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_TARGET": "chillTarget",
}

OVERRIDE3_FIELDS = {
    "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_HOP_ALLOW_NON_CARDINAL": "attentiveHopAllowNonCardinal",
    "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_HOP_MIN_DISTANCE": "attentiveHopMinDistance",
    "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_HOP_MAX_DISTANCE": "attentiveHopMaxDistance",
    "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_HOP_PAUSE": "attentiveHopPause",
    "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_TELEPORT_TIME": "attentiveTeleportTime",
    "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_TELEPORT_PAUSE": "attentiveTeleportPause",
    "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_RAM_ACCELERATION_STEPS": "attentiveRamAccelerationSteps",
    "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_RAM_MAX_SPEED": "attentiveRamMaxSpeed",
    "OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_HOP_ALLOW_NON_CARDINAL": "tiredHopAllowNonCardinal",
    "OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_HOP_MIN_DISTANCE": "tiredHopMinDistance",
    "OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_HOP_MAX_DISTANCE": "tiredHopMaxDistance",
    "OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_HOP_PAUSE": "tiredHopPause",
    "OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_TELEPORT_TIME": "tiredTeleportTime",
    "OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_TELEPORT_PAUSE": "tiredTeleportPause",
    "OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_RAM_ACCELERATION_STEPS": "tiredRamAccelerationSteps",
    "OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_RAM_MAX_SPEED": "tiredRamMaxSpeed",
    "OW_WILD_BEHAVIOR_OVERRIDE3_ALERT_CALL_SPAWN_STATE": "alertCallSpawnState",
}

OVERRIDE_FIELDS = {**OVERRIDE1_FIELDS, **OVERRIDE2_FIELDS, **OVERRIDE3_FIELDS}

OVERRIDE_SYMBOL_BY_FIELD = {
    field: symbol
    for symbol, field in OVERRIDE_FIELDS.items()
}

OVERRIDE_WORD_BY_FIELD = {
    **{field: 1 for field in OVERRIDE1_FIELDS.values()},
    **{field: 2 for field in OVERRIDE2_FIELDS.values()},
    **{field: 3 for field in OVERRIDE3_FIELDS.values()},
}

CLASS_PREFIX = "OW_WILD_BEHAVIOR_CLASS_"
GROUP_PREFIX = "OW_WILD_BEHAVIOR_GROUP_"
TERRAIN_PREFIX = "OW_WILD_SPAWN_TERRAIN_"
DESTINATION_PREFIX = "OW_WILD_SPAWN_DESTINATION_"
PROFILE_PREFIX = "OW_WILD_BEHAVIOR_PROFILE_"
TYPE_PREFIX = "TYPE_"
POKEMON_TYPE_ORDER = [
    "TYPE_NORMAL",
    "TYPE_FIGHTING",
    "TYPE_FLYING",
    "TYPE_POISON",
    "TYPE_GROUND",
    "TYPE_ROCK",
    "TYPE_BUG",
    "TYPE_GHOST",
    "TYPE_STEEL",
    "TYPE_FAIRY",
    "TYPE_FIRE",
    "TYPE_WATER",
    "TYPE_GRASS",
    "TYPE_ELECTRIC",
    "TYPE_PSYCHIC",
    "TYPE_ICE",
    "TYPE_DRAGON",
    "TYPE_DARK",
    "TYPE_TYPELESS",
    "TYPE_STELLAR",
]

ENCOUNTER_RATE_FIELDS = [
    ("walkrate", "Walking"),
    ("surfrate", "Surfing"),
    ("rocksmashrate", "Rock smash"),
    ("oldrodrate", "Old rod"),
    ("goodrodrate", "Good rod"),
    ("superrodrate", "Super rod"),
]

GRASS_SLOT_WEIGHTS = [20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1]
SURF_SLOT_WEIGHTS = [60, 30, 5, 4, 1]
FISHING_SLOT_WEIGHTS = [60, 30, 5, 4, 1]
ROCK_SMASH_SLOT_WEIGHTS = [50, 50]
SOUND_SLOT_WEIGHTS = [50, 50]
HEADBUTT_NORMAL_SLOT_COUNT = 12
HEADBUTT_SPECIAL_SLOT_COUNT = 6
HEADBUTT_NORMAL_SLOT_WEIGHTS = [100 / HEADBUTT_NORMAL_SLOT_COUNT] * HEADBUTT_NORMAL_SLOT_COUNT
HEADBUTT_SPECIAL_SLOT_WEIGHTS = [100 / HEADBUTT_SPECIAL_SLOT_COUNT] * HEADBUTT_SPECIAL_SLOT_COUNT

ENCOUNTER_POKEMON_TABLES = {
    "morning": ("Morning", 12),
    "day": ("Day", 12),
    "night": ("Night", 12),
    "hoenn": ("Hoenn sound", 2),
    "sinnoh": ("Sinnoh sound", 2),
}

ENCOUNTER_SLOT_TABLES = {
    "surf": ("Surf", 5, SURF_SLOT_WEIGHTS),
    "rockSmash": ("Rock smash", 2, ROCK_SMASH_SLOT_WEIGHTS),
    "oldRod": ("Old rod", 5, FISHING_SLOT_WEIGHTS),
    "goodRod": ("Good rod", 5, FISHING_SLOT_WEIGHTS),
    "superRod": ("Super rod", 5, FISHING_SLOT_WEIGHTS),
}

HEADBUTT_TABLES = {
    "headbuttNormal": ("Headbutt", HEADBUTT_NORMAL_SLOT_COUNT, HEADBUTT_NORMAL_SLOT_WEIGHTS, "normalTreeCount"),
    "headbuttSpecial": ("Special trees", HEADBUTT_SPECIAL_SLOT_COUNT, HEADBUTT_SPECIAL_SLOT_WEIGHTS, "specialTreeCount"),
}

ENCOUNTER_SWARM_FIELDS = {
    "landSwarm": "Grass swarm",
    "surfSwarm": "Surf swarm",
    "nightFish": "Good rod swarm",
    "fishSwarm": "Super rod swarm",
}

ENCOUNTER_COMMENT_TABLES = {
    "morning encounter slots": ("pokemon", "morning"),
    "day encounter slots": ("pokemon", "day"),
    "night encounter slots": ("pokemon", "night"),
    "hoenn encounter slots": ("pokemon", "hoenn"),
    "sinnoh encounter slots": ("pokemon", "sinnoh"),
    "surf encounters": ("slot", "surf"),
    "rock smash encounters": ("slot", "rockSmash"),
    "old rod encounters": ("slot", "oldRod"),
    "good rod encounters": ("slot", "goodRod"),
    "super rod encounters": ("slot", "superRod"),
    "swarm grass": ("swarm", "landSwarm"),
    "swarm surf": ("swarm", "surfSwarm"),
    "swarm good rod": ("swarm", "nightFish"),
    "swarm super rod": ("swarm", "fishSwarm"),
}

SPAWN_SETTING_GROUPS = [
    {
        "key": "testSpawns",
        "label": "Test Spawns",
        "settings": [
            {
                "symbol": "__TEST_SPAWNS__",
                "label": "Test spawns",
                "kind": "testSpawn",
                "source": ENEMY_PARTY_SOURCE,
                "fields": [
                    {"symbol": "ENABLE_WILD_TEST_HARNESS", "label": "Enabled", "kind": "boolean", "min": 0, "max": 1, "source": ENEMY_PARTY_SOURCE, "role": "enabled"},
                    {"symbol": "WILD_TEST_SPECIES", "label": "Pokemon", "kind": "species", "source": ENEMY_PARTY_SOURCE, "role": "species"},
                    {"symbol": "WILD_TEST_LEVEL", "label": "Level", "kind": "number", "min": 1, "max": 100, "source": ENEMY_PARTY_SOURCE, "role": "level"},
                ],
            }
        ],
    },
    {
        "key": "capacity",
        "label": "Visible Spawn Capacity",
        "settings": [
            {"symbol": "OW_WILD_GRASS_MAX_SPAWNS", "label": "Grass max spawns", "min": 0, "max": 10, "source": SPAWNS_INTERNAL_HEADER},
            {"symbol": "OW_WILD_SURF_MAX_SPAWNS", "label": "Surf max spawns", "min": 0, "max": 10, "source": SPAWNS_INTERNAL_HEADER},
            {"symbol": "OW_WILD_HEADBUTT_MAX_SPAWNS", "label": "Headbutt max spawns", "min": 0, "max": 10, "source": SPAWNS_INTERNAL_HEADER},
            {"symbol": "OW_WILD_FISH_MAX_SPAWNS", "label": "Fishing max spawns", "min": 0, "max": 10, "source": SPAWNS_INTERNAL_HEADER},
            {"symbol": "OW_WILD_MAX_SAVED_SHINIES", "label": "Saved shiny slots", "min": 0, "max": 50, "source": SPAWNS_INTERNAL_HEADER},
        ],
    },
    {
        "key": "spawnFlow",
        "label": "Spawn Flow",
        "settings": [
            {"symbol": "OW_WILD_REFILL_COOLDOWN_STEPS", "label": "Refill cooldown steps", "min": 0, "max": 255, "source": OVERLAY_SOURCE},
            {"symbol": "OW_WILD_HEADBUTT_SPAWN_CHANCE_PERCENT", "label": "Headbutt spawn chance", "min": 0, "max": 100, "source": OVERLAY_SOURCE, "suffix": "%"},
            {"symbol": "OW_WILD_HEADBUTT_REFILL_ATTEMPT_COOLDOWN", "label": "Headbutt attempt cooldown", "min": 0, "max": 255, "source": OVERLAY_SOURCE},
            {"symbol": "OW_WILD_FISHING_SPAWN_CHANCE_PERCENT", "label": "Fishing spawn chance", "min": 0, "max": 100, "source": OVERLAY_SOURCE, "suffix": "%"},
            {"symbol": "OW_WILD_FISHING_REFILL_ATTEMPT_COOLDOWN", "label": "Fishing attempt cooldown", "min": 0, "max": 255, "source": OVERLAY_SOURCE},
            {"symbol": "OW_WILD_HELPER_RANDOM_TIME_TABLE_CHANCE_PERCENT", "label": "Random time table chance", "min": 0, "max": 100, "source": HELPER_SOURCE, "suffix": "%"},
            {"symbol": "OVERWORLD_WILD_SHINY_BASE_ODDS", "label": "Base shiny odds denominator", "min": 1, "max": 65535, "source": SPAWNS_PUBLIC_HEADER},
        ],
    },
    {
        "key": "placement",
        "label": "Placement",
        "settings": [
            {"symbol": "OW_WILD_SPAWN_MIN_DISTANCE", "label": "Spawn min distance", "min": 0, "max": 64, "source": OVERLAY_SOURCE},
            {"symbol": "OW_WILD_SPAWN_MAX_DISTANCE", "label": "Spawn max distance", "min": 0, "max": 64, "source": OVERLAY_SOURCE},
            {"symbol": "OW_WILD_DESPAWN_DISTANCE", "label": "Despawn distance", "min": 0, "max": 128, "source": OVERLAY_SOURCE},
            {"symbol": "OW_WILD_SPAWN_MIN_MON_DISTANCE", "label": "Min distance between Pokemon", "min": 0, "max": 64, "source": OVERLAY_SOURCE},
        ],
    },
    {
        "key": "ambient",
        "label": "Ambient Cries",
        "settings": [
            {"symbol": "OW_WILD_AMBIENT_CRY_MIN_COOLDOWN_STEPS", "label": "Min cooldown steps", "min": 0, "max": 999, "source": OVERLAY_SOURCE},
            {"symbol": "OW_WILD_AMBIENT_CRY_RANDOM_COOLDOWN_STEPS", "label": "Random cooldown steps", "min": 0, "max": 999, "source": OVERLAY_SOURCE},
            {"symbol": "OW_WILD_AMBIENT_CRY_MAX_COOLDOWN_TICK", "label": "Max cooldown tick", "min": 0, "max": 255, "source": OVERLAY_SOURCE},
        ],
    },
    {
        "key": "movement",
        "label": "Movement Defaults",
        "settings": [
            {"symbol": "OW_WILD_SPAWNER_MOVEMENT_DECISION_COOLDOWN", "label": "Decision cooldown", "min": 0, "max": 255, "source": OVERLAY_SOURCE},
            {"symbol": "OW_WILD_SPAWNER_MOVEMENT_RANGE", "label": "Movement range", "min": 0, "max": 255, "source": OVERLAY_SOURCE},
            {"symbol": "OW_WILD_SPAWNER_MOVEMENT_BURST_UPDATE_STEPS", "label": "Burst update steps", "min": 0, "max": 255, "source": OVERLAY_SOURCE},
            {"symbol": "OW_WILD_SPAWNER_MOVEMENT_SPEED_DEFAULT", "label": "Default movement speed", "min": 0, "max": 10, "source": OVERLAY_SOURCE},
            {"symbol": "OW_WILD_SPAWNER_BATTLE_SETTLE_FRAMES", "label": "Battle settle frames", "min": 0, "max": 255, "source": OVERLAY_SOURCE},
            {"symbol": "OW_WILD_FLEE_GRACE_STEPS", "label": "Flee grace steps", "min": 0, "max": 255, "source": OVERLAY_SOURCE},
        ],
    },
]


def iter_spawn_setting_definitions():
    seen: set[str] = set()
    for group in SPAWN_SETTING_GROUPS:
        for setting in group["settings"]:
            definitions = setting.get("fields") if setting.get("kind") == "testSpawn" else [setting]
            for definition in definitions:
                symbol = definition["symbol"]
                if symbol in seen:
                    continue
                seen.add(symbol)
                yield symbol, definition


SPAWN_SETTING_BY_SYMBOL = {
    symbol: setting
    for symbol, setting in iter_spawn_setting_definitions()
}

NUMERIC_PROFILE_FIELDS = {
    "alertTime",
    "alertness",
    "stamina",
    "restTime",
    "chillSpeed",
    "attentiveSpeed",
    "tiredSpeed",
    "range",
    "chillCooldown",
    "attentiveCooldown",
    "alertChance",
    "hopMinDistance",
    "hopMaxDistance",
    "hopPause",
    "teleportTime",
    "teleportPause",
    "attentiveHopMinDistance",
    "attentiveHopMaxDistance",
    "attentiveHopPause",
    "attentiveTeleportTime",
    "attentiveTeleportPause",
    "attentiveRamAccelerationSteps",
    "attentiveRamMaxSpeed",
    "tiredHopMinDistance",
    "tiredHopMaxDistance",
    "tiredHopPause",
    "tiredTeleportTime",
    "tiredTeleportPause",
    "tiredRamAccelerationSteps",
    "tiredRamMaxSpeed",
    "alertCallSpawnAmount",
    "spawnDestinationMinDistance",
    "spawnDestinationMaxDistance",
    "ramAccelerationSteps",
    "ramMaxSpeed",
}

COMMON_NUMERIC_FIELD_SYMBOLS = {
    "alertTime": [
        "OW_WILD_SPAWNER_ALERT_TIME_AUTO",
        "OW_WILD_SPAWNER_SPOT_EMOTE_SPEECH_FRAMES",
        "OW_WILD_SPAWNER_SPOT_EMOTE_FRAMES_PER_JUMP",
    ],
    "alertness": [
        "OW_WILD_SPAWNER_SPOT_RANGE",
        "OW_WILD_SPAWNER_CLOSE_ALERT_RADIUS",
        "OW_WILD_SPAWNER_ONIX_RAM_ALERTNESS",
        "OW_WILD_SPAWNER_CANOPY_HOPPER_TREE_ALERT_RADIUS",
    ],
    "chillSpeed": [
        "OW_WILD_SPAWNER_MOVEMENT_SPEED_DEFAULT",
        "OW_WILD_SPAWNER_MOVEMENT_SPEED_1",
        "OW_WILD_SPAWNER_MOVEMENT_SPEED_2",
        "OW_WILD_SPAWNER_MOVEMENT_SPEED_3",
        "OW_WILD_SPAWNER_MOVEMENT_SPEED_4",
        "OW_WILD_SPAWNER_PIDGEY_MOVEMENT_SPEED",
        "OW_WILD_SPAWNER_ONIX_RAM_START_SPEED",
    ],
    "attentiveSpeed": [
        "OW_WILD_SPAWNER_MOVEMENT_SPEED_DEFAULT",
        "OW_WILD_SPAWNER_MOVEMENT_SPEED_1",
        "OW_WILD_SPAWNER_MOVEMENT_SPEED_2",
        "OW_WILD_SPAWNER_MOVEMENT_SPEED_3",
        "OW_WILD_SPAWNER_MOVEMENT_SPEED_4",
        "OW_WILD_SPAWNER_PIDGEY_MOVEMENT_SPEED",
        "OW_WILD_SPAWNER_ONIX_RAM_START_SPEED",
    ],
    "tiredSpeed": [
        "OW_WILD_SPAWNER_MOVEMENT_SPEED_DEFAULT",
        "OW_WILD_SPAWNER_MOVEMENT_SPEED_1",
        "OW_WILD_SPAWNER_MOVEMENT_SPEED_2",
        "OW_WILD_SPAWNER_MOVEMENT_SPEED_3",
        "OW_WILD_SPAWNER_MOVEMENT_SPEED_4",
        "OW_WILD_SPAWNER_PIDGEY_MOVEMENT_SPEED",
        "OW_WILD_SPAWNER_ONIX_RAM_START_SPEED",
    ],
    "range": [
        "OW_WILD_SPAWNER_MOVEMENT_RANGE",
        "OW_WILD_SPAWNER_PLAYFUL_RANGE",
        "OW_WILD_SPAWNER_PHANTOM_STALK_RANGE",
        "OW_WILD_SPAWNER_ONIX_RAM_RANGE",
        "OW_WILD_SPAWNER_CANOPY_HOPPER_RANGE",
    ],
    "chillCooldown": [
        "OW_WILD_SPAWNER_CHILL_WANDER_COOLDOWN_FRAMES",
        "OW_WILD_SPAWNER_CANOPY_HOPPER_COOLDOWN_FRAMES",
    ],
    "attentiveCooldown": [
        "OW_WILD_SPAWNER_CANOPY_HOPPER_ATTENTIVE_COOLDOWN_FRAMES",
        "OW_WILD_SPAWNER_CANOPY_HOPPER_COOLDOWN_FRAMES",
    ],
    "hopMinDistance": [
        "OW_WILD_SPAWNER_CANOPY_HOPPER_LONG_JUMP_MIN_TILES",
        "OW_WILD_SPAWNER_MOVEMENT_DISTANCE_STEP",
    ],
    "hopMaxDistance": [
        "OW_WILD_SPAWNER_CANOPY_HOPPER_LONG_JUMP_MAX_TILES",
        "OW_WILD_SPAWNER_CANOPY_HOPPER_MAX_HOP_TILES",
    ],
    "hopPause": [
        "OW_WILD_SPAWNER_CANOPY_HOPPER_COOLDOWN_FRAMES",
        "OW_WILD_SPAWNER_CHILL_WANDER_COOLDOWN_FRAMES",
    ],
    "teleportTime": [
        "OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_MOVE_FRAMES",
    ],
    "teleportPause": [
        "OW_WILD_SPAWNER_PHANTOM_STALK_POST_TELEPORT_COOLDOWN_FRAMES",
    ],
    "alertCallSpawnAmount": [
        "OW_WILD_SPAWNER_SWARM_MAX_EXTRA_SPAWNS",
    ],
    "spawnDestinationMinDistance": [
        "OW_WILD_SPAWNER_MOVEMENT_DISTANCE_STEP",
    ],
    "spawnDestinationMaxDistance": [
        "OW_WILD_SPAWNER_MOVEMENT_DISTANCE_STEP",
    ],
    "ramAccelerationSteps": [
        "OW_WILD_SPAWNER_ONIX_RAM_SPEED_UP_TILES",
    ],
    "ramMaxSpeed": [
        "OW_WILD_SPAWNER_MOVEMENT_SPEED_1",
        "OW_WILD_SPAWNER_MOVEMENT_SPEED_2",
        "OW_WILD_SPAWNER_MOVEMENT_SPEED_3",
        "OW_WILD_SPAWNER_MOVEMENT_SPEED_4",
        "OW_WILD_SPAWNER_ONIX_RAM_MAX_SPEED",
    ],
}

for _profile_field, _source_field in {
    "attentiveHopMinDistance": "hopMinDistance",
    "tiredHopMinDistance": "hopMinDistance",
    "attentiveHopMaxDistance": "hopMaxDistance",
    "tiredHopMaxDistance": "hopMaxDistance",
    "attentiveHopPause": "hopPause",
    "tiredHopPause": "hopPause",
    "attentiveTeleportTime": "teleportTime",
    "tiredTeleportTime": "teleportTime",
    "attentiveTeleportPause": "teleportPause",
    "tiredTeleportPause": "teleportPause",
    "attentiveRamAccelerationSteps": "ramAccelerationSteps",
    "tiredRamAccelerationSteps": "ramAccelerationSteps",
    "attentiveRamMaxSpeed": "ramMaxSpeed",
    "tiredRamMaxSpeed": "ramMaxSpeed",
}.items():
    COMMON_NUMERIC_FIELD_SYMBOLS[_profile_field] = COMMON_NUMERIC_FIELD_SYMBOLS[_source_field]

NUMERIC_PROFILE_FIELD_OPTION_MAX = {
    "alertTime": 255,
    "alertChance": 100,
    "hopMinDistance": 12,
    "hopMaxDistance": 12,
    "hopPause": 255,
    "teleportTime": 64,
    "teleportPause": 255,
    "alertCallSpawnAmount": 3,
    "spawnDestinationMinDistance": 8,
    "spawnDestinationMaxDistance": 8,
    "ramAccelerationSteps": 32,
    "ramMaxSpeed": 4,
}

for _profile_field, _source_field in {
    "attentiveHopMinDistance": "hopMinDistance",
    "tiredHopMinDistance": "hopMinDistance",
    "attentiveHopMaxDistance": "hopMaxDistance",
    "tiredHopMaxDistance": "hopMaxDistance",
    "attentiveHopPause": "hopPause",
    "tiredHopPause": "hopPause",
    "attentiveTeleportTime": "teleportTime",
    "tiredTeleportTime": "teleportTime",
    "attentiveTeleportPause": "teleportPause",
    "tiredTeleportPause": "teleportPause",
    "attentiveRamAccelerationSteps": "ramAccelerationSteps",
    "tiredRamAccelerationSteps": "ramAccelerationSteps",
    "attentiveRamMaxSpeed": "ramMaxSpeed",
    "tiredRamMaxSpeed": "ramMaxSpeed",
}.items():
    NUMERIC_PROFILE_FIELD_OPTION_MAX[_profile_field] = NUMERIC_PROFILE_FIELD_OPTION_MAX[_source_field]


class ParseError(RuntimeError):
    pass


def join_line_continuations(text: str) -> str:
    return text.replace("\\\r\n", " ").replace("\\\n", " ")


def strip_c_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//.*", "", text)


def clean_token(token: str) -> str:
    return re.sub(r"\s+", " ", token.strip())


DEFINE_RE = re.compile(
    r"^[ \t]*#define[ \t]+([A-Za-z_]\w*)(\([^)]*\))?[ \t]+([^\n]+?)[ \t]*$",
    re.M,
)


def parse_define_expressions(paths: list[Path]) -> tuple[dict[str, str], list[str]]:
    expressions: dict[str, str] = {}
    species_order: list[str] = []
    for path in paths:
        text = strip_c_comments(join_line_continuations(path.read_text()))
        for match in DEFINE_RE.finditer(text):
            name, args, expr = match.groups()
            if args is not None:
                continue
            expr = clean_token(expr)
            if not expr:
                continue
            expressions[name] = expr
            if path == SPECIES_HEADER and name.startswith("SPECIES_"):
                species_order.append(name)
    return expressions, species_order


def parse_armips_equ_expressions(paths: list[Path]) -> dict[str, str]:
    expressions: dict[str, str] = {}
    for path in paths:
        text = strip_c_comments(join_line_continuations(path.read_text()))
        for raw_line in text.splitlines():
            line = clean_token(raw_line)
            if not line:
                continue
            match = re.match(r"^\.equ\s+([A-Za-z_]\w*)\s*,\s*(.+)$", line)
            if not match:
                match = re.match(r"^([A-Za-z_]\w*)\s+equ\s+(.+)$", line)
            if not match:
                match = re.match(r"^\.definelabel\s+([A-Za-z_]\w*)\s*,\s*(.+)$", line)
            if match:
                name, expr = match.groups()
                expressions[name] = clean_token(expr)
    return expressions


BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.floordiv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.LShift: operator.lshift,
    ast.RShift: operator.rshift,
    ast.BitOr: operator.or_,
    ast.BitAnd: operator.and_,
    ast.BitXor: operator.xor,
}
UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Invert: operator.invert,
}


def normalize_c_expr(expr: str) -> str:
    expr = expr.strip()
    expr = re.sub(r"\bTRUE\b", "1", expr)
    expr = re.sub(r"\bFALSE\b", "0", expr)
    expr = re.sub(r"(?<=\d)[uUlL]+\b", "", expr)
    expr = re.sub(r"\((?:u|s)?(?:8|16|32|64|int|long|BOOL)\)", "", expr)
    return expr


def eval_c_expr(expr: str, values: dict[str, int]) -> int:
    expr = normalize_c_expr(expr)
    tree = ast.parse(expr, mode="eval")

    def walk(node: ast.AST) -> int:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return int(node.value)
        if isinstance(node, ast.Name):
            if node.id not in values:
                raise KeyError(node.id)
            return int(values[node.id])
        if isinstance(node, ast.BinOp) and type(node.op) in BIN_OPS:
            return int(BIN_OPS[type(node.op)](walk(node.left), walk(node.right)))
        if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY_OPS:
            return int(UNARY_OPS[type(node.op)](walk(node.operand)))
        raise ValueError(f"unsupported expression: {expr}")

    return walk(tree)


def evaluate_defines(expressions: dict[str, str]) -> dict[str, int]:
    values: dict[str, int] = {"TRUE": 1, "FALSE": 0}
    pending = dict(expressions)
    for _ in range(len(pending) + 1):
        changed = False
        for name, expr in list(pending.items()):
            try:
                values[name] = eval_c_expr(expr, values)
            except Exception:
                continue
            del pending[name]
            changed = True
        if not changed:
            break
    return values


def evaluate_armips_equ(paths: list[Path]) -> dict[str, int]:
    return evaluate_defines(parse_armips_equ_expressions(paths))


def split_top_level_csv(raw: str) -> list[str]:
    parts: list[str] = []
    token: list[str] = []
    depth = 0
    for char in raw:
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        if char == "," and depth == 0:
            parts.append(clean_token("".join(token)))
            token.clear()
            continue
        token.append(char)
    if token:
        parts.append(clean_token("".join(token)))
    return parts


def trim_wrapping_parens(expr: str) -> str:
    expr = clean_token(expr)
    while expr.startswith("(") and expr.endswith(")"):
        depth = 0
        wraps = True
        for idx, char in enumerate(expr):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0 and idx != len(expr) - 1:
                    wraps = False
                    break
        if not wraps:
            break
        expr = clean_token(expr[1:-1])
    return expr


def split_ternary_expr(expr: str) -> tuple[str, str, str] | None:
    depth = 0
    question = -1
    for idx, char in enumerate(expr):
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == "?" and depth == 0:
            question = idx
            break
    if question < 0:
        return None
    depth = 0
    for idx in range(question + 1, len(expr)):
        char = expr[idx]
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == ":" and depth == 0:
            return (
                trim_wrapping_parens(expr[:question]),
                trim_wrapping_parens(expr[question + 1 : idx]),
                trim_wrapping_parens(expr[idx + 1 :]),
            )
    return None


def resolve_ternary_expr(expr: str, values: dict[str, int]) -> str:
    expr = trim_wrapping_parens(expr)
    split = split_ternary_expr(expr)
    if not split:
        return expr
    condition, when_true, when_false = split
    branch = when_true if eval_c_expr(condition, values) else when_false
    return resolve_ternary_expr(branch, values)


def extract_braced_initializer(text: str, name: str) -> str:
    start = text.find(name)
    if start < 0:
        span = behavior_blob_field_span(text, name)
        if span is None:
            raise ParseError(f"could not find {name}")
        return text[span[0] : span[1]]
    brace = text.find("{", start)
    if brace < 0:
        raise ParseError(f"could not find initializer for {name}")
    depth = 0
    for idx in range(brace, len(text)):
        char = text[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[brace : idx + 1]
    raise ParseError(f"unterminated initializer for {name}")


def parse_initializer(src: str):
    root: list = []
    stack: list[list] = [root]
    token: list[str] = []
    paren_depth = 0

    def flush() -> None:
        value = clean_token("".join(token))
        token.clear()
        if value:
            stack[-1].append(value)

    for char in src:
        if char == "(":
            paren_depth += 1
            token.append(char)
        elif char == ")":
            paren_depth -= 1
            token.append(char)
        elif char == "{" and paren_depth == 0:
            flush()
            child: list = []
            stack[-1].append(child)
            stack.append(child)
        elif char == "}" and paren_depth == 0:
            flush()
            if len(stack) == 1:
                raise ParseError("initializer has too many closing braces")
            stack.pop()
        elif char == "," and paren_depth == 0:
            flush()
        else:
            token.append(char)

    flush()
    if len(stack) != 1:
        raise ParseError("initializer has unclosed braces")
    if len(root) != 1 or not isinstance(root[0], list):
        raise ParseError("initializer root was not a single list")
    return root[0]


def parse_enum_values(text: str, enum_name: str) -> dict[str, int]:
    pattern = re.compile(rf"typedef\s+enum\s+{re.escape(enum_name)}\s*\{{(.*?)\}}", re.S)
    match = pattern.search(text)
    if not match:
        return {}
    result: dict[str, int] = {}
    value = 0
    for raw_item in match.group(1).split(","):
        item = clean_token(raw_item)
        if not item:
            continue
        if "=" in item:
            name, raw_value = [part.strip() for part in item.split("=", 1)]
            value = int(raw_value, 0)
        else:
            name = item
        result[name] = value
        value += 1
    return result


def parse_behavior_data_enums() -> tuple[dict[str, int], dict[str, int]]:
    source = strip_c_comments(join_line_continuations(BEHAVIOR_DATA_HEADER.read_text()))
    return (
        parse_enum_values(source, "OverworldWildSpawnTerrain"),
        parse_enum_values(source, "OverworldWildSpawnDestination"),
    )


def humanize_symbol(symbol: str, prefix: str | None = None) -> str:
    text = symbol
    if prefix and text.startswith(prefix):
        text = text[len(prefix) :]
    elif text.startswith("SPECIES_"):
        text = text[len("SPECIES_") :]
    text = text.replace("_", " ").strip()
    return " ".join(part.capitalize() for part in text.split())


def macro_label(symbol: str, value: int | None, field: str | None, macros: dict[str, int]) -> str:
    if symbol == "OW_WILD_SPAWN_DESTINATION_POOL":
        return "Pool default"
    if symbol == "OW_WILD_SPAWN_DESTINATION_NEXT_TO_PLAYER":
        return "Next to player"
    if symbol == "OW_WILD_SPAWN_DESTINATION_FRONT_OF_PLAYER":
        return "1 tile in front of player"
    if symbol == "OW_WILD_SPAWN_DESTINATION_FIVE_TILES_BEHIND_PLAYER":
        return "5 tiles behind player"
    match = re.fullmatch(
        r"OW_WILD_SPAWN_DESTINATION_(ONE|TWO|THREE|FOUR|FIVE)_TILES?_(FRONT_OF|BEHIND)_PLAYER",
        symbol,
    )
    if match:
        words = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}
        distance = words[match.group(1)]
        direction = "in front of" if match.group(2) == "FRONT_OF" else "behind"
        tile = "tile" if distance == 1 else "tiles"
        return f"{distance} {tile} {direction} player"
    if field in FIELD_PREFIXES and value is not None:
        prefix = FIELD_PREFIXES[field]
        candidates = [name for name, num in macros.items() if name.startswith(prefix) and num == value]
        if candidates:
            return humanize_symbol(sorted(candidates, key=len)[0], prefix)
    if symbol.startswith(CLASS_PREFIX):
        return humanize_symbol(symbol, CLASS_PREFIX)
    if symbol.startswith(GROUP_PREFIX):
        return humanize_symbol(symbol, GROUP_PREFIX)
    if symbol.startswith(TERRAIN_PREFIX):
        return humanize_symbol(symbol, TERRAIN_PREFIX)
    if symbol.startswith(PROFILE_PREFIX):
        return humanize_symbol(symbol, PROFILE_PREFIX)
    if symbol.startswith("SPECIES_"):
        return humanize_symbol(symbol, "SPECIES_")
    if symbol.startswith("OW_WILD_BEHAVIOR_MATCH_ANY_"):
        return "Any"
    if symbol == "OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY":
        return "Any"
    return humanize_symbol(symbol)


def make_value(raw: str, field: str | None, macros: dict[str, int]) -> dict:
    raw = clean_token(raw)
    value = None
    try:
        value = eval_c_expr(raw, macros)
    except Exception:
        pass

    symbol = raw if re.fullmatch(r"[A-Za-z_]\w*", raw) else None
    if symbol:
        label = macro_label(symbol, value, field, macros)
    elif value is not None:
        label = str(value)
    else:
        label = raw

    if symbol and value is not None and not symbol.startswith(("OW_WILD_BEHAVIOR_", "OW_WILD_SPAWNER_BUBBLE_ID_", "OW_WILD_SPAWN_DESTINATION_", "SPECIES_")):
        label = f"{label} ({value})"

    return {
        "raw": raw,
        "symbol": symbol,
        "value": value,
        "label": label,
    }


def numeric(value: dict) -> int | None:
    return value.get("value")


def parse_profile(items: list, macros: dict[str, int]) -> dict[str, dict]:
    if len(items) == 1 and clean_token(str(items[0])) == "0":
        return {
            field: make_value("0", field, macros)
            for field in PROFILE_FIELDS
        }
    if len(items) != len(PROFILE_FIELDS):
        raise ParseError(f"profile has {len(items)} fields, expected {len(PROFILE_FIELDS)}")
    return {
        field: make_value(str(items[idx]), field, macros)
        for idx, field in enumerate(PROFILE_FIELDS)
    }


def parse_mask(raw: str, macros: dict[str, int], override_fields: dict[str, str] | None = None) -> dict:
    if override_fields is None:
        override_fields = OVERRIDE1_FIELDS
    value = make_value(raw, None, macros)
    symbols = re.findall(r"\bOW_WILD_BEHAVIOR_OVERRIDE[23]?_[A-Z0-9_]+\b", raw)
    bits = []
    if symbols:
        for symbol in symbols:
            if symbol not in override_fields:
                continue
            bits.append(
                {
                    "symbol": symbol,
                    "field": override_fields.get(symbol),
                    "label": FIELD_LABELS.get(override_fields.get(symbol, ""), symbol),
                    "value": macros.get(symbol),
                }
            )
    elif value["value"] is not None:
        for symbol, field in override_fields.items():
            bit_value = macros.get(symbol)
            if bit_value is not None and value["value"] & bit_value:
                bits.append(
                    {
                        "symbol": symbol,
                        "field": field,
                        "label": FIELD_LABELS[field],
                        "value": bit_value,
                    }
                )
    return {
        "raw": clean_token(raw),
        "value": value["value"],
        "bits": bits,
        "labels": [bit["label"] for bit in bits if bit.get("field")],
    }


def parse_behavior_override(items: list, macros: dict[str, int]) -> dict:
    if len(items) == 2 and isinstance(items[1], list):
        mask_raw = str(items[0])
        mask2_raw = "0"
        mask3_raw = "0"
        profile_items = items[1]
    elif len(items) == 3 and isinstance(items[2], list):
        mask_raw = str(items[0])
        mask2_raw = str(items[1])
        mask3_raw = "0"
        profile_items = items[2]
    elif len(items) == 4 and isinstance(items[3], list):
        mask_raw = str(items[0])
        mask2_raw = str(items[1])
        mask3_raw = str(items[2])
        profile_items = items[3]
    else:
        raise ParseError("behavior override initializer shape changed")
    mask = parse_mask(mask_raw, macros, OVERRIDE1_FIELDS)
    mask2 = parse_mask(mask2_raw, macros, OVERRIDE2_FIELDS)
    mask3 = parse_mask(mask3_raw, macros, OVERRIDE3_FIELDS)
    labels = mask["labels"] + mask2["labels"] + mask3["labels"]
    extra_raws = [extra["raw"] for extra in (mask2, mask3) if extra["raw"] != "0"]
    mask_raw_summary = mask["raw"] if not extra_raws else " / ".join([mask["raw"], *extra_raws])
    return {
        "mask": mask,
        "mask2": mask2,
        "mask3": mask3,
        "maskLabels": labels,
        "maskRaw": mask_raw_summary,
        "profile": parse_profile(profile_items, macros),
    }


def parse_behavior_overrides(source: str, macros: dict[str, int], group_labels: dict[int, dict]) -> list[dict]:
    overrides = []
    try:
        entries = parse_initializer(extract_braced_initializer(source, "sOverworldWildBehaviorOverrides"))
        for order, entry in enumerate(entries, 1):
            if len(entry) == 3:
                behavior = parse_behavior_override([entry[1], entry[2]], macros)
            elif len(entry) == 4:
                behavior = parse_behavior_override([entry[1], entry[2], entry[3]], macros)
            elif len(entry) == 5:
                behavior = parse_behavior_override([entry[1], entry[2], entry[3], entry[4]], macros)
            else:
                raise ParseError("behavior override initializer shape changed")
            override = {
                "order": order,
                "kind": "behavior",
                "match": parse_match(entry[0], macros),
                "behavior": behavior,
            }
            override["summary"] = match_summary(override["match"], macros, group_labels)
            overrides.append(override)
        return overrides
    except ParseError:
        if "sOverworldWildBehaviorMaxSpeedOverrides" not in source:
            raise

    for order, entry in enumerate(parse_initializer(extract_braced_initializer(source, "sOverworldWildBehaviorMaxSpeedOverrides")), 1):
        if len(entry) != 2:
            raise ParseError("max-speed override initializer shape changed")
        override = {
            "order": order,
            "kind": "attentiveSpeed",
            "match": parse_match(entry[0], macros),
            "behavior": make_single_field_behavior_override("attentiveSpeed", str(entry[1]), macros),
        }
        override["summary"] = match_summary(override["match"], macros, group_labels)
        overrides.append(override)
    return overrides


def make_single_field_behavior_override(field: str, raw: str, macros: dict[str, int]) -> dict:
    symbol = OVERRIDE_SYMBOL_BY_FIELD[field]
    profile = parse_profile(["0"], macros)
    profile[field] = make_value(raw, field, macros)
    mask_raw = symbol if OVERRIDE_WORD_BY_FIELD.get(field) == 1 else "0"
    mask2_raw = symbol if OVERRIDE_WORD_BY_FIELD.get(field) == 2 else "0"
    mask3_raw = symbol if OVERRIDE_WORD_BY_FIELD.get(field) == 3 else "0"
    mask = parse_mask(mask_raw, macros, OVERRIDE1_FIELDS)
    mask2 = parse_mask(mask2_raw, macros, OVERRIDE2_FIELDS)
    mask3 = parse_mask(mask3_raw, macros, OVERRIDE3_FIELDS)
    extra_raws = [extra["raw"] for extra in (mask2, mask3) if extra["raw"] != "0"]
    return {
        "mask": mask,
        "mask2": mask2,
        "mask3": mask3,
        "maskLabels": mask["labels"] + mask2["labels"] + mask3["labels"],
        "maskRaw": mask["raw"] if not extra_raws else " / ".join([mask["raw"], *extra_raws]),
        "profile": profile,
    }


def parse_value_table(source: str, name: str, field: str, macros: dict[str, int]) -> list[dict]:
    return [
        make_value(str(entry), field, macros)
        for entry in parse_initializer(extract_braced_initializer(source, name))
    ]


def parse_pair_table(source: str, name: str, fields: tuple[str, str], macros: dict[str, int]) -> list[dict]:
    result = []
    for entry in parse_initializer(extract_braced_initializer(source, name)):
        if not isinstance(entry, list) or len(entry) != 2:
            raise ParseError(f"{name} initializer shape changed")
        result.append(
            {
                fields[0]: make_value(str(entry[0]), fields[0], macros),
                fields[1]: make_value(str(entry[1]), fields[1], macros),
            }
        )
    return result


def parse_primitive_maps(source: str, macros: dict[str, int]) -> dict[str, list]:
    return {
        "spawnLocomotionBySpawnState": parse_value_table(
            source,
            "sOverworldWildSpawnLocomotionBySpawnState",
            "spawnLocomotion",
            macros,
        ),
        "alertPrimitivesByRange": parse_pair_table(
            source,
            "sOverworldWildAlertPrimitivesByRange",
            ("alertLogic", "alertReaction"),
            macros,
        ),
    }


def indexed_primitive(table: list, index: int | None) -> dict | None:
    if index is None or index < 0 or index >= len(table):
        return None
    return table[index]


def resolve_primitives(profile: dict[str, dict], primitive_maps: dict[str, list], macros: dict[str, int]) -> dict[str, dict]:
    primitives = {
        "spawnLocomotion": make_value("OW_WILD_BEHAVIOR_LOCOMOTION_NONE", "spawnLocomotion", macros),
        "chillLocomotion": make_value("OW_WILD_BEHAVIOR_LOCOMOTION_NONE", "chillLocomotion", macros),
        "chillTarget": make_value("OW_WILD_BEHAVIOR_TARGET_NONE", "chillTarget", macros),
        "alertLogic": make_value("OW_WILD_BEHAVIOR_ALERT_LOGIC_NONE", "alertLogic", macros),
        "alertReaction": make_value("OW_WILD_BEHAVIOR_REACTION_NONE", "alertReaction", macros),
        "attentiveLocomotion": make_value("OW_WILD_BEHAVIOR_LOCOMOTION_NONE", "attentiveLocomotion", macros),
        "attentiveTarget": make_value("OW_WILD_BEHAVIOR_TARGET_NONE", "attentiveTarget", macros),
        "activeReaction": make_value("OW_WILD_BEHAVIOR_REACTION_NONE", "activeReaction", macros),
        "tiredReaction": make_value("OW_WILD_BEHAVIOR_REACTION_NONE", "tiredReaction", macros),
    }

    spawn = indexed_primitive(primitive_maps["spawnLocomotionBySpawnState"], numeric(profile["spawnState"]))
    if spawn:
        primitives["spawnLocomotion"] = spawn

    chill_behavior = numeric(profile["chillState"])
    primitives["chillTarget"] = copy.deepcopy(profile["chillTarget"])
    if chill_behavior in {
        macros.get("OW_WILD_BEHAVIOR_KIND_WANDER"),
        macros.get("OW_WILD_BEHAVIOR_KIND_SINGING"),
    }:
        primitives["chillLocomotion"] = copy.deepcopy(profile["chillAction"])
        if numeric(primitives["chillTarget"]) == macros.get("OW_WILD_BEHAVIOR_TARGET_NONE"):
            primitives["chillTarget"] = make_value("OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY", "chillTarget", macros)
    elif chill_behavior == macros.get("OW_WILD_BEHAVIOR_KIND_CHASE"):
        primitives["chillLocomotion"] = copy.deepcopy(profile["chillAction"])
        if numeric(primitives["chillTarget"]) == macros.get("OW_WILD_BEHAVIOR_TARGET_NONE"):
            primitives["chillTarget"] = make_value("OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER", "chillTarget", macros)
    elif chill_behavior == macros.get("OW_WILD_BEHAVIOR_KIND_FLEE"):
        primitives["chillLocomotion"] = copy.deepcopy(profile["chillAction"])
        if numeric(primitives["chillTarget"]) == macros.get("OW_WILD_BEHAVIOR_TARGET_NONE"):
            primitives["chillTarget"] = make_value("OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER", "chillTarget", macros)
    elif chill_behavior == macros.get("OW_WILD_BEHAVIOR_KIND_PLAYFUL"):
        primitives["chillLocomotion"] = copy.deepcopy(profile["chillAction"])
        if numeric(primitives["chillTarget"]) == macros.get("OW_WILD_BEHAVIOR_TARGET_NONE"):
            primitives["chillTarget"] = make_value("OW_WILD_BEHAVIOR_TARGET_PLAYFUL_ORBIT", "chillTarget", macros)
    elif chill_behavior == macros.get("OW_WILD_BEHAVIOR_KIND_RAM"):
        primitives["chillLocomotion"] = copy.deepcopy(profile["chillAction"])
        if numeric(primitives["chillTarget"]) == macros.get("OW_WILD_BEHAVIOR_TARGET_NONE"):
            primitives["chillTarget"] = make_value("OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER", "chillTarget", macros)
    elif chill_behavior == macros.get("OW_WILD_BEHAVIOR_KIND_HEADBUTT_TREE_HOP"):
        primitives["chillLocomotion"] = copy.deepcopy(profile["chillAction"])
        if numeric(primitives["chillTarget"]) == macros.get("OW_WILD_BEHAVIOR_TARGET_NONE"):
            primitives["chillTarget"] = make_value("OW_WILD_BEHAVIOR_TARGET_TREE_TOP", "chillTarget", macros)

    primitives["attentiveLocomotion"] = copy.deepcopy(profile["movementStyle"])
    primitives["attentiveTarget"] = copy.deepcopy(profile["targetSelector"])
    active_behavior = numeric(profile["attentiveState"])
    if active_behavior == macros.get("OW_WILD_BEHAVIOR_KIND_CHASE"):
        primitives["activeReaction"] = make_value("OW_WILD_BEHAVIOR_REACTION_CONTACT", "activeReaction", macros)
        if numeric(primitives["attentiveTarget"]) == macros.get("OW_WILD_BEHAVIOR_TARGET_NONE"):
            primitives["attentiveTarget"] = make_value("OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER", "attentiveTarget", macros)
    elif active_behavior == macros.get("OW_WILD_BEHAVIOR_KIND_FLEE"):
        primitives["activeReaction"] = make_value("OW_WILD_BEHAVIOR_REACTION_FLEE", "activeReaction", macros)
        if numeric(primitives["attentiveTarget"]) == macros.get("OW_WILD_BEHAVIOR_TARGET_NONE"):
            primitives["attentiveTarget"] = make_value("OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER", "attentiveTarget", macros)
    elif active_behavior == macros.get("OW_WILD_BEHAVIOR_KIND_PLAYFUL"):
        primitives["activeReaction"] = make_value("OW_WILD_BEHAVIOR_REACTION_EMOTE", "activeReaction", macros)
        if numeric(primitives["attentiveTarget"]) == macros.get("OW_WILD_BEHAVIOR_TARGET_NONE"):
            primitives["attentiveTarget"] = make_value("OW_WILD_BEHAVIOR_TARGET_PLAYFUL_ORBIT", "attentiveTarget", macros)
    elif active_behavior == macros.get("OW_WILD_BEHAVIOR_KIND_RAM"):
        primitives["activeReaction"] = make_value("OW_WILD_BEHAVIOR_REACTION_CONTACT", "activeReaction", macros)
        if numeric(primitives["attentiveTarget"]) == macros.get("OW_WILD_BEHAVIOR_TARGET_NONE"):
            primitives["attentiveTarget"] = make_value("OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER", "attentiveTarget", macros)
    elif active_behavior == macros.get("OW_WILD_BEHAVIOR_KIND_HEADBUTT_TREE_HOP"):
        primitives["activeReaction"] = make_value("OW_WILD_BEHAVIOR_REACTION_CONTACT", "activeReaction", macros)
        if numeric(primitives["attentiveTarget"]) == macros.get("OW_WILD_BEHAVIOR_TARGET_NONE"):
            primitives["attentiveTarget"] = make_value("OW_WILD_BEHAVIOR_TARGET_TREE_TOP", "attentiveTarget", macros)
    elif active_behavior == macros.get("OW_WILD_BEHAVIOR_KIND_SINGING"):
        primitives["activeReaction"] = make_value("OW_WILD_BEHAVIOR_REACTION_EMOTE", "activeReaction", macros)

    if (numeric(profile["alertness"]) or 0) != 0 and (numeric(profile["alertChance"]) or 0) != 0:
        alert = indexed_primitive(primitive_maps["alertPrimitivesByRange"], numeric(profile["alertRange"]))
        if alert:
            primitives["alertLogic"] = alert["alertLogic"]
            primitives["alertReaction"] = alert["alertReaction"]

    if numeric(profile["tiredState"]) != macros.get("OW_WILD_BEHAVIOR_KIND_NONE"):
        primitives["tiredReaction"] = make_value("OW_WILD_BEHAVIOR_REACTION_TIRED", "tiredReaction", macros)

    return primitives


def value_option(raw: str, field: str, macros: dict[str, int]) -> dict:
    value = make_value(raw, field, macros)
    return {
        "raw": value["raw"],
        "label": value["label"],
        "value": value["value"],
    }


def add_value_option(options: list[dict], seen: set[str], raw: str, field: str, macros: dict[str, int]) -> None:
    raw = clean_token(raw)
    if not raw or raw in seen:
        return
    options.append(value_option(raw, field, macros))
    seen.add(raw)


def build_edit_options(macros: dict[str, int], class_profiles: list[dict[str, dict]]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for field in PROFILE_FIELDS:
        options: list[dict] = []
        seen: set[str] = set()
        if field in CANONICAL_PROFILE_FIELD_RAWS:
            for symbol in CANONICAL_PROFILE_FIELD_RAWS[field]:
                if symbol in macros:
                    add_value_option(options, seen, symbol, field, macros)
        elif field in FIELD_PREFIXES:
            prefix = FIELD_PREFIXES[field]
            symbols = sorted(
                (symbol for symbol in macros if symbol.startswith(prefix)),
                key=lambda symbol: (macros.get(symbol, 0), symbol),
            )
            for symbol in symbols:
                add_value_option(options, seen, symbol, field, macros)
        elif field in NUMERIC_PROFILE_FIELDS:
            for value in range(0, NUMERIC_PROFILE_FIELD_OPTION_MAX.get(field, 64) + 1):
                add_value_option(options, seen, str(value), field, macros)
            for symbol in COMMON_NUMERIC_FIELD_SYMBOLS.get(field, []):
                if symbol in macros:
                    add_value_option(options, seen, symbol, field, macros)
        if field not in CANONICAL_PROFILE_FIELD_RAWS:
            for profile in class_profiles:
                add_value_option(options, seen, profile[field]["raw"], field, macros)
        result[field] = options
    return result


def parse_match(items: list, macros: dict[str, int]) -> dict[str, dict]:
    if len(items) != len(MATCH_FIELDS):
        raise ParseError(f"match has {len(items)} fields, expected {len(MATCH_FIELDS)}")
    return {
        field: make_value(str(items[idx]), field, macros)
        for idx, field in enumerate(MATCH_FIELDS)
    }


def parse_full_class_rules(
    behavior_source: str,
    macros: dict[str, int],
    group_labels: dict[int, dict],
    class_labels: dict[int, dict],
) -> list[dict]:
    class_rules = []
    for order, entry in enumerate(parse_initializer(extract_braced_initializer(behavior_source, "sOverworldWildBehaviorClassRules")), 1):
        if len(entry) != 2:
            raise ParseError("class rule initializer shape changed")
        behavior_class = make_value(str(entry[1]), "behaviorClass", macros)
        rule = {
            "order": order,
            "match": parse_match(entry[0], macros),
            "behaviorClass": behavior_class,
            "storage": "full",
        }
        rule["summary"] = match_summary(rule["match"], macros, group_labels)
        rule["className"] = class_labels.get(numeric(behavior_class) or -1, {"name": behavior_class["label"]})["name"]
        class_rules.append(rule)
    return class_rules


def parse_species_class_rules(
    behavior_source: str,
    macros: dict[str, int],
    group_labels: dict[int, dict],
    class_labels: dict[int, dict],
    order_offset: int = 0,
) -> list[dict]:
    try:
        entries = parse_initializer(extract_braced_initializer(behavior_source, "sOverworldWildBehaviorSpeciesClassRules"))
    except ParseError:
        return []
    class_rules = []
    for index, entry in enumerate(entries, 1):
        if len(entry) != 2:
            raise ParseError("compact species class rule initializer shape changed")
        match_raws = default_behavior_match_raws()
        match_raws["species"] = clean_token(str(entry[0]))
        behavior_class = make_value(str(entry[1]), "behaviorClass", macros)
        rule = {
            "order": order_offset + index,
            "match": parse_match([match_raws[field] for field in MATCH_FIELDS], macros),
            "behaviorClass": behavior_class,
            "storage": "species",
        }
        rule["summary"] = match_summary(rule["match"], macros, group_labels)
        rule["className"] = class_labels.get(numeric(behavior_class) or -1, {"name": behavior_class["label"]})["name"]
        class_rules.append(rule)
    return class_rules


def parse_behavior_class_rules(
    behavior_source: str,
    macros: dict[str, int],
    group_labels: dict[int, dict],
    class_labels: dict[int, dict],
) -> list[dict]:
    class_rules = parse_full_class_rules(behavior_source, macros, group_labels, class_labels)
    class_rules.extend(parse_species_class_rules(behavior_source, macros, group_labels, class_labels, len(class_rules)))
    return class_rules


def clone_profile(profile: dict[str, dict]) -> dict[str, dict]:
    return copy.deepcopy(profile)


def merge_profile(profile: dict[str, dict], override: dict) -> list[dict]:
    changes = []
    for bit in (
        override["mask"]["bits"]
        + override.get("mask2", {"bits": []})["bits"]
        + override.get("mask3", {"bits": []})["bits"]
    ):
        field = bit.get("field")
        if not field:
            continue
        before = profile[field]
        after = copy.deepcopy(override["profile"][field])
        profile[field] = after
        changes.append(
            {
                "field": field,
                "label": FIELD_LABELS[field],
                "before": before,
                "after": after,
            }
        )
    return changes


def behavior_override_mask_summary(behavior: dict) -> dict:
    labels = behavior.get("maskLabels")
    if labels is None:
        labels = (
            behavior["mask"]["labels"]
            + behavior.get("mask2", {"labels": []})["labels"]
            + behavior.get("mask3", {"labels": []})["labels"]
        )
    raw = behavior.get("maskRaw")
    if raw is None:
        mask2_raw = behavior.get("mask2", {"raw": "0"})["raw"]
        mask3_raw = behavior.get("mask3", {"raw": "0"})["raw"]
        extra_raws = [extra for extra in (mask2_raw, mask3_raw) if extra != "0"]
        raw = behavior["mask"]["raw"] if not extra_raws else " / ".join([behavior["mask"]["raw"], *extra_raws])
    return {"labels": labels, "raw": raw}


def normalize_profile(profile: dict[str, dict], macros: dict[str, int]) -> list[dict]:
    changes = []

    def set_field(field: str, raw: str) -> None:
        before = profile[field]
        after = make_value(raw, field, macros)
        if before.get("raw") == after.get("raw") and before.get("value") == after.get("value"):
            return
        profile[field] = after
        changes.append(
            {
                "field": field,
                "label": FIELD_LABELS[field],
                "before": before,
                "after": after,
            }
        )

    if numeric(profile["attentiveSpeed"]) == 0:
        set_field("attentiveSpeed", "OW_WILD_SPAWNER_MOVEMENT_SPEED_DEFAULT")
    if numeric(profile["chillSpeed"]) == 0:
        set_field("chillSpeed", "OW_WILD_SPAWNER_MOVEMENT_SPEED_DEFAULT")
    if numeric(profile["tiredSpeed"]) == 0:
        set_field("tiredSpeed", profile["chillSpeed"]["raw"])
    for allow_field, min_field, max_field in (
        ("hopAllowNonCardinal", "hopMinDistance", "hopMaxDistance"),
        ("attentiveHopAllowNonCardinal", "attentiveHopMinDistance", "attentiveHopMaxDistance"),
        ("tiredHopAllowNonCardinal", "tiredHopMinDistance", "tiredHopMaxDistance"),
    ):
        if numeric(profile[allow_field]) not in {
            macros.get("OW_WILD_BEHAVIOR_BOOL_NO"),
            macros.get("OW_WILD_BEHAVIOR_BOOL_YES"),
        }:
            set_field(allow_field, "OW_WILD_BEHAVIOR_BOOL_YES")
        if numeric(profile[min_field]) == 0:
            set_field(min_field, "1")
        if numeric(profile[max_field]) == 0:
            set_field(max_field, profile[min_field]["raw"])
        if (numeric(profile[max_field]) or 0) < (numeric(profile[min_field]) or 0):
            set_field(max_field, profile[min_field]["raw"])
    if numeric(profile["spawnDestinationMinDistance"]) == 0:
        set_field("spawnDestinationMinDistance", "1")
    elif (numeric(profile["spawnDestinationMinDistance"]) or 0) > 8:
        set_field("spawnDestinationMinDistance", "8")
    if numeric(profile["spawnDestinationMaxDistance"]) == 0:
        set_field("spawnDestinationMaxDistance", "5")
    elif (numeric(profile["spawnDestinationMaxDistance"]) or 0) > 8:
        set_field("spawnDestinationMaxDistance", "8")
    if (numeric(profile["spawnDestinationMaxDistance"]) or 0) < (numeric(profile["spawnDestinationMinDistance"]) or 0):
        set_field("spawnDestinationMaxDistance", profile["spawnDestinationMinDistance"]["raw"])
    for teleport_time_field, teleport_pause_field in (
        ("teleportTime", "teleportPause"),
        ("attentiveTeleportTime", "attentiveTeleportPause"),
        ("tiredTeleportTime", "tiredTeleportPause"),
    ):
        if numeric(profile[teleport_time_field]) == 0:
            set_field(teleport_time_field, "OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_MOVE_FRAMES")
        if numeric(profile[teleport_pause_field]) == 0:
            set_field(teleport_pause_field, "OW_WILD_SPAWNER_PHANTOM_STALK_POST_TELEPORT_COOLDOWN_FRAMES")
    if numeric(profile["chillState"]) == macros.get("OW_WILD_BEHAVIOR_KIND_ASLEEP"):
        set_field("tiredState", "OW_WILD_BEHAVIOR_KIND_ASLEEP")
        set_field("stamina", "1")
        set_field("restTime", "0")
        set_field("alertness", "0")
        set_field("alertChance", "0")
    elif numeric(profile["tiredState"]) == macros.get("OW_WILD_BEHAVIOR_KIND_ASLEEP"):
        set_field("stamina", "1")
        set_field("restTime", "0")
    if (
        (
            numeric(profile["attentiveState"]) != macros.get("OW_WILD_BEHAVIOR_KIND_NONE")
            or numeric(profile["targetSelector"]) != macros.get("OW_WILD_BEHAVIOR_TARGET_NONE")
            or numeric(profile["movementStyle"]) != macros.get("OW_WILD_BEHAVIOR_LOCOMOTION_NONE")
            or numeric(profile["attentiveBattle"]) != macros.get("OW_WILD_BEHAVIOR_BATTLE_TRIGGER_NONE")
        )
        and numeric(profile["tiredState"]) != macros.get("OW_WILD_BEHAVIOR_KIND_NONE")
        and numeric(profile["stamina"]) == 0
    ):
        set_field("stamina", "1")
    if (
        numeric(profile["tiredState"]) != macros.get("OW_WILD_BEHAVIOR_KIND_NONE")
        and numeric(profile["tiredState"]) != macros.get("OW_WILD_BEHAVIOR_KIND_ASLEEP")
        and numeric(profile["restTime"]) == 0
    ):
        set_field("restTime", "1")
    return changes


def parse_group_species(source: str, macros: dict[str, int]) -> dict[int, list[str]]:
    match = re.search(
        r"static\s+u32\s+OverworldWildSpawns_GetBehaviorGroupFlags\s*\([^)]*\)\s*\{(.*?)\n\}",
        source,
        flags=re.S,
    )
    if not match:
        return {}
    groups: dict[int, list[str]] = {}
    for cases, group_expr in re.findall(
        r"((?:\s*case\s+SPECIES_[A-Z0-9_]+\s*:\s*)+)flags\s*\|=\s*([^;]+);",
        match.group(1),
        flags=re.S,
    ):
        symbols = [
            symbol
            for symbol in re.findall(r"\bOW_WILD_BEHAVIOR_GROUP_[A-Z0-9_]+\b", group_expr)
            if symbol != "OW_WILD_BEHAVIOR_GROUP_NONE"
        ]
        case_species = re.findall(r"case\s+(SPECIES_[A-Z0-9_]+)\s*:", cases)
        for group_symbol in symbols:
            group_value = macros.get(group_symbol)
            if group_value is None:
                continue
            groups.setdefault(group_value, [])
            groups[group_value].extend(case_species)
    return groups


def type_group_symbol(type_symbol: str) -> str:
    return f"OW_WILD_BEHAVIOR_GROUP_TYPE_{type_symbol.removeprefix(TYPE_PREFIX)}"


def species_type_group_flags(species: dict | None, macros: dict[str, int]) -> int:
    if not species:
        return 0
    flags = 0
    for entry in species.get("types", []):
        symbol = entry.get("symbol")
        if not symbol:
            continue
        flags |= macros.get(type_group_symbol(symbol), 0)
    return flags


def parse_species(expressions: dict[str, str], macros: dict[str, int], species_order: list[str]) -> list[dict]:
    result = []
    seen_values: set[int] = set()
    for symbol in species_order:
        if symbol == "SPECIES_NONE" or symbol.endswith("_START"):
            continue
        value = macros.get(symbol)
        if value is None or value in seen_values:
            continue
        seen_values.add(value)
        result.append(
            {
                "symbol": symbol,
                "name": humanize_symbol(symbol, "SPECIES_"),
                "value": value,
            }
        )
    return result


def type_entry(symbol: str, macros: dict[str, int]) -> dict:
    return {
        "symbol": symbol,
        "name": humanize_symbol(symbol, TYPE_PREFIX),
        "value": macros.get(symbol),
    }


def build_type_options(macros: dict[str, int]) -> list[dict]:
    options = []
    seen: set[str] = set()
    for symbol in POKEMON_TYPE_ORDER:
        if symbol in macros and symbol not in seen:
            options.append(type_entry(symbol, macros))
            seen.add(symbol)
    return options


def parse_species_type_metadata(macros: dict[str, int]) -> dict[str, list[dict]]:
    if not MONDATA_SOURCE.exists():
        return {}
    text = strip_c_comments(join_line_continuations(MONDATA_SOURCE.read_text()))
    result: dict[str, list[dict]] = {}
    current_symbol: str | None = None
    type_symbols_by_value = {
        macros[symbol]: symbol
        for symbol in POKEMON_TYPE_ORDER
        if symbol in macros
    }
    for raw_line in text.splitlines():
        line = clean_token(raw_line)
        if not line:
            continue
        match = re.match(r'^mondata\s+(SPECIES_[A-Z0-9_]+)\s*,', line)
        if match:
            current_symbol = match.group(1)
            continue
        if current_symbol is None or not line.startswith("types "):
            continue
        parts = split_top_level_csv(line[len("types ") :])
        species_types = []
        seen_values: set[int] = set()
        for raw_type in parts[:2]:
            try:
                resolved = resolve_ternary_expr(raw_type, macros)
                value = eval_c_expr(resolved, macros)
            except Exception:
                continue
            symbol = resolved if re.fullmatch(r"TYPE_[A-Z0-9_]+", resolved) else type_symbols_by_value.get(value)
            if not symbol or value in seen_values:
                continue
            seen_values.add(value)
            species_types.append(type_entry(symbol, macros))
        result[current_symbol] = species_types
    return result


def apply_species_type_metadata(species: list[dict], type_metadata: dict[str, list[dict]]) -> None:
    for entry in species:
        entry["types"] = copy.deepcopy(type_metadata.get(entry["symbol"], []))


def parse_armips_species_values(macros: dict[str, int]) -> dict[str, int]:
    expressions: dict[str, str] = {}
    for raw_line in ARMIPS_SPECIES_INC.read_text().splitlines():
        line = raw_line.split("//", 1)[0].strip()
        match = re.match(r"^\.equ\s+(SPECIES_[A-Z0-9_]+)\s*,\s*(.+)$", line)
        if not match:
            continue
        symbol, expr = match.groups()
        expressions[symbol] = clean_token(expr)

    values = dict(macros)
    pending = dict(expressions)
    for _ in range(len(pending) + 1):
        changed = False
        for symbol, expr in list(pending.items()):
            try:
                values[symbol] = eval_c_expr(expr, values)
            except Exception:
                continue
            del pending[symbol]
            changed = True
        if not changed:
            break
    return {symbol: values[symbol] for symbol in expressions if symbol in values}


def build_encounter_species_options(species: list[dict], macros: dict[str, int]) -> list[dict]:
    icon_paths = cached_icon_paths()
    species_by_symbol = {entry["symbol"]: entry for entry in species}
    species_by_value = {entry["value"]: entry for entry in species}
    armips_values = parse_armips_species_values(macros)
    options = [species_entry_for_symbol("SPECIES_NONE", species_by_symbol, macros)]
    seen_symbols = {"SPECIES_NONE"}

    for symbol, value in armips_values.items():
        if symbol == "SPECIES_NONE" or symbol.endswith("_START") or symbol in seen_symbols:
            continue
        canonical = species_by_value.get(value)
        if canonical is not None:
            entry = dict(canonical)
            entry["symbol"] = symbol
            if canonical["symbol"] != symbol:
                entry["canonicalSymbol"] = canonical["symbol"]
                entry["aliases"] = [canonical["symbol"]]
        else:
            entry = {
                "symbol": symbol,
                "name": humanize_symbol(symbol, "SPECIES_"),
                "value": value,
            }
            if value in icon_paths:
                entry["iconUrl"] = f"/icons/{value}.png"
        seen_symbols.add(symbol)
        options.append(entry)
    apply_regional_form_metadata(options, species_by_symbol, macros)
    return options


def parse_poke_form_specs(macros: dict[str, int]) -> list[dict]:
    if not POKE_FORM_DATA.exists():
        return []
    text = strip_c_comments(POKE_FORM_DATA.read_text())
    specs = []
    entry_re = re.compile(r"\[\s*(SPECIES_[A-Z0-9_]+)\s*\]\s*=\s*\{(.*?)\}", re.S)
    for match in entry_re.finditer(text):
        base_symbol = match.group(1)
        body = match.group(2)
        symbols = re.findall(r"SPECIES_[A-Z0-9_]+", body)
        form_index = 1
        for symbol in symbols:
            if symbol == base_symbol:
                continue
            specs.append(
                {
                    "baseSymbol": base_symbol,
                    "symbol": symbol,
                    "form": form_index,
                }
            )
            form_index += 1
    return specs


def regional_form_region(symbol: str, value: int | None, macros: dict[str, int]) -> str | None:
    ranges = [
        ("Alolan", "SPECIES_ALOLAN_REGIONAL_START", "MAX_ALOLAN_REGIONAL_NUM"),
        ("Galarian", "SPECIES_GALARIAN_REGIONAL_START", "MAX_GALARIAN_REGIONAL_NUM"),
        ("Hisuian", "SPECIES_HISUIAN_REGIONAL_START", "MAX_HISUIAN_REGIONAL_NUM"),
        ("Paldean", "SPECIES_PALDEAN_FORMS_START", "MAX_SPECIES_PALDEAN_FORM_NUM"),
    ]
    if value is not None:
        for label, start_symbol, end_symbol in ranges:
            start = macros.get(start_symbol)
            end = macros.get(end_symbol)
            if start is not None and end is not None and start <= value <= end:
                return label
    if "_ALOLAN" in symbol or "_ALOLA_" in symbol:
        return "Alolan"
    if "_GALARIAN" in symbol:
        return "Galarian"
    if "_HISUIAN" in symbol:
        return "Hisuian"
    if "_PALDEAN" in symbol:
        return "Paldean"
    return None


def regional_form_aliases(base_name: str, form_name: str, region: str | None, form: int) -> list[str]:
    aliases = {f"{base_name} form {form}", f"{form_name} form {form}"}
    if not region:
        return sorted(aliases)
    suffix = form_name
    base_prefix = f"{base_name} "
    if suffix.startswith(base_prefix):
        suffix = suffix[len(base_prefix) :]
    if suffix.lower() == region.lower():
        aliases.add(f"{region} {base_name}")
    else:
        aliases.add(f"{region} {base_name} {suffix}")
    if not form_name.lower().endswith(region.lower()):
        aliases.add(f"{region} {form_name}")
    return sorted(aliases)


def apply_regional_form_metadata(options: list[dict], species_by_symbol: dict[str, dict], macros: dict[str, int]) -> None:
    options_by_symbol = {entry["symbol"]: entry for entry in options}
    for spec in parse_poke_form_specs(macros):
        symbol = spec["symbol"]
        base_symbol = spec["baseSymbol"]
        entry = options_by_symbol.get(symbol)
        base_entry = species_by_symbol.get(base_symbol)
        if entry is None or base_entry is None:
            continue
        region = regional_form_region(symbol, entry.get("value"), macros)
        if region is None:
            continue
        entry["baseSymbol"] = base_symbol
        entry["form"] = spec["form"]
        entry["formRegion"] = region
        aliases = set(entry.get("aliases", []))
        aliases.update(regional_form_aliases(base_entry["name"], entry["name"], region, spec["form"]))
        entry["aliases"] = sorted(aliases)


def species_entry_for_symbol(symbol: str, species_by_symbol: dict[str, dict], macros: dict[str, int]) -> dict:
    if symbol in species_by_symbol:
        return species_by_symbol[symbol]
    if symbol == "SPECIES_NONE":
        return {
            "symbol": "SPECIES_NONE",
            "name": "None",
            "value": macros.get("SPECIES_NONE", 0),
        }
    return {
        "symbol": symbol,
        "name": humanize_symbol(symbol, "SPECIES_") if symbol.startswith("SPECIES_") else symbol,
        "value": macros.get(symbol),
    }


def parse_encounter_area_maps(source: str, macros: dict[str, int] | None = None) -> dict[int, list[dict]]:
    try:
        entries = parse_initializer(extract_braced_initializer(source, "sOverworldWildEncounterAreas"))
    except ParseError:
        return {}
    areas: dict[int, list[dict]] = {}
    for entry in entries:
        if len(entry) != 2:
            continue
        map_symbol = clean_token(str(entry[0]))
        try:
            encounter_id = int(str(entry[1]), 0)
        except ValueError:
            continue
        map_value = macros.get(map_symbol) if macros else None
        map_entry = {
            "symbol": map_symbol,
            "name": humanize_symbol(map_symbol, "MAP_"),
        }
        if map_value is not None:
            map_entry["value"] = map_value
        areas.setdefault(encounter_id, []).append(
            map_entry
        )
    return areas


def parse_headbutt_encounters(
    species_by_symbol: dict[str, dict],
    macros: dict[str, int],
) -> dict[int, dict]:
    raw = HEADBUTT_SOURCE.read_text(encoding="latin-1")
    lines = raw.splitlines()
    by_map_id: dict[int, dict] = {}
    current: dict | None = None
    slot_count = 0
    header_pattern = re.compile(r"^headbuttheader\s+(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?://\s*(.*))?$")
    encounter_pattern = re.compile(
        r"^(headbuttencounter|headbuttencounterwithform)\s+(SPECIES_[A-Z0-9_]+)\s*,\s*(?:(\d+)\s*,\s*)?(\d+)\s*,\s*(\d+)\s*$"
    )

    def finish_current() -> None:
        nonlocal current, slot_count
        if current is None:
            return
        has_trees = current["normalTreeCount"] > 0 or current["specialTreeCount"] > 0
        has_slots = any(table["slots"] for table in current["_tablesByKey"].values())
        if has_trees or has_slots:
            for key, (_, expected, _, _) in HEADBUTT_TABLES.items():
                count = len(current["_tablesByKey"][key]["slots"])
                if count != expected:
                    raise ParseError(
                        f"headbuttheader {current['mapId']} {key} has {count} slots, expected {expected}"
                    )
            current["tables"] = [current["_tablesByKey"][key] for key in HEADBUTT_TABLES]
            del current["_tablesByKey"]
            by_map_id[current["mapId"]] = current
        current = None
        slot_count = 0

    for line_no, line in enumerate(lines):
        stripped = line.strip()
        header_match = header_pattern.match(stripped)
        if header_match:
            finish_current()
            map_id = int(header_match.group(1), 10)
            normal_tree_count = int(header_match.group(2), 10)
            special_tree_count = int(header_match.group(3), 10)
            label = clean_token(header_match.group(4) or "")
            current = {
                "mapId": map_id,
                "name": label or f"Map {map_id}",
                "normalTreeCount": normal_tree_count,
                "specialTreeCount": special_tree_count,
                "_tablesByKey": {
                    key: {
                        "key": key,
                        "label": label_text,
                        "weights": weights,
                        "treeCount": normal_tree_count if tree_count_key == "normalTreeCount" else special_tree_count,
                        "slots": [],
                    }
                    for key, (label_text, _, weights, tree_count_key) in HEADBUTT_TABLES.items()
                },
            }
            slot_count = 0
            continue
        if stripped == ".close":
            finish_current()
            continue
        if current is None:
            continue
        match = encounter_pattern.match(stripped)
        if not match:
            continue
        macro, species_symbol, form_raw, min_level_raw, max_level_raw = match.groups()
        if macro == "headbuttencounter" and form_raw is not None:
            raise ParseError(f"headbuttheader {current['mapId']} has a malformed headbutt form line")
        if slot_count < HEADBUTT_NORMAL_SLOT_COUNT:
            key = "headbuttNormal"
            slot_index = slot_count
        elif slot_count < HEADBUTT_NORMAL_SLOT_COUNT + HEADBUTT_SPECIAL_SLOT_COUNT:
            key = "headbuttSpecial"
            slot_index = slot_count - HEADBUTT_NORMAL_SLOT_COUNT
        else:
            raise ParseError(f"headbuttheader {current['mapId']} has too many headbutt encounter slots")
        table = current["_tablesByKey"][key]
        table["slots"].append(
            {
                "slot": slot_index + 1,
                "weight": table["weights"][slot_index] if slot_index < len(table["weights"]) else None,
                "species": make_encounter_species(species_symbol, species_by_symbol, macros),
                "form": int(form_raw or "0", 10),
                "minLevel": int(min_level_raw, 10),
                "maxLevel": int(max_level_raw, 10),
                "paths": {
                    "species": f"headbutt.{current['mapId']}.{key}.{slot_index}.species",
                    "form": f"headbutt.{current['mapId']}.{key}.{slot_index}.form",
                    "minLevel": f"headbutt.{current['mapId']}.{key}.{slot_index}.minLevel",
                    "maxLevel": f"headbutt.{current['mapId']}.{key}.{slot_index}.maxLevel",
                },
                "line": line_no,
            }
        )
        slot_count += 1
    finish_current()
    return by_map_id


def headbutt_tables_for_route(maps: list[dict], headbutt_by_map_id: dict[int, dict]) -> list[dict]:
    tables: list[dict] = []
    for map_entry in maps:
        map_value = map_entry.get("value")
        if map_value is None:
            continue
        headbutt = headbutt_by_map_id.get(int(map_value))
        if not headbutt:
            continue
        for table in headbutt["tables"]:
            has_species = any(slot["species"]["symbol"] != "SPECIES_NONE" for slot in table["slots"])
            if table.get("treeCount", 0) <= 0 and not has_species:
                continue
            route_table = copy.deepcopy(table)
            route_table["mapId"] = headbutt["mapId"]
            route_table["mapName"] = map_entry.get("name") or headbutt["name"]
            route_table["mapSymbol"] = map_entry.get("symbol")
            tables.append(route_table)
    return tables


def split_csv_numbers(raw: str, expected: int, label: str) -> list[int]:
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != expected:
        raise ParseError(f"{label} has {len(parts)} values, expected {expected}")
    try:
        return [int(part, 0) for part in parts]
    except ValueError as exc:
        raise ParseError(f"{label} contains a non-numeric value") from exc


def make_encounter_species(symbol: str, species_by_symbol: dict[str, dict], macros: dict[str, int]) -> dict:
    species = dict(species_entry_for_symbol(symbol, species_by_symbol, macros))
    if species.get("value") in cached_icon_paths():
        species["iconUrl"] = f"/icons/{species['value']}.png"
    return species


def form_species_by_base_form(species_by_symbol: dict[str, dict]) -> dict[tuple[str, int], dict]:
    return {
        (entry["baseSymbol"], int(entry["form"])): entry
        for entry in species_by_symbol.values()
        if entry.get("baseSymbol") and entry.get("form") is not None
    }


def route_species_summary(route: dict, form_species: dict[tuple[str, int], dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []

    def add(species: dict, form: int = 0) -> None:
        display_species = form_species.get((species["symbol"], int(form or 0)), species)
        symbol = display_species["symbol"]
        if symbol == "SPECIES_NONE" or symbol in seen:
            return
        seen.add(symbol)
        result.append(display_species)

    for table in route["pokemonTables"]:
        for slot in table["slots"]:
            add(slot["species"], slot.get("form", 0))
    for table in route["slotTables"]:
        for slot in table["slots"]:
            add(slot["species"], slot.get("form", 0))
    for table in route.get("headbuttTables", []):
        for slot in table["slots"]:
            add(slot["species"], slot.get("form", 0))
    for swarm in route["swarms"]:
        add(swarm["species"], swarm.get("form", 0))
    return result


def parse_route_encounters(
    species_by_symbol: dict[str, dict],
    macros: dict[str, int],
    encounter_area_maps: dict[int, list[dict]],
    headbutt_by_map_id: dict[int, dict] | None = None,
) -> list[dict]:
    raw = ENCOUNTERS_SOURCE.read_text()
    lines = raw.splitlines()
    form_species = form_species_by_base_form(species_by_symbol)
    routes: list[dict] = []
    route: dict | None = None
    current_table: tuple[str, str] | None = None
    table_counts: dict[str, int] = {}
    route_header = re.compile(r"^encounterdata\s+(\d+)\s*(?://\s*(.*))?$")

    def finish_route() -> None:
        if route is None:
            return
        missing_rates = [key for key, _ in ENCOUNTER_RATE_FIELDS if key not in route["_ratesByKey"]]
        if missing_rates:
            raise ParseError(f"encounterdata {route['id']} missing rates: {', '.join(missing_rates)}")
        if len(route["grassLevels"]) != len(GRASS_SLOT_WEIGHTS):
            raise ParseError(f"encounterdata {route['id']} has an invalid walklevels line")
        for key, (_, expected) in ENCOUNTER_POKEMON_TABLES.items():
            count = len(route["_pokemonTablesByKey"][key]["slots"])
            if count != expected:
                raise ParseError(f"encounterdata {route['id']} {key} has {count} slots, expected {expected}")
        for key, (_, expected, _) in ENCOUNTER_SLOT_TABLES.items():
            count = len(route["_slotTablesByKey"][key]["slots"])
            if count != expected:
                raise ParseError(f"encounterdata {route['id']} {key} has {count} slots, expected {expected}")
        if len(route["swarms"]) != len(ENCOUNTER_SWARM_FIELDS):
            raise ParseError(f"encounterdata {route['id']} has {len(route['swarms'])} swarm slots")
        route["rates"] = [route["_ratesByKey"][key] for key, _ in ENCOUNTER_RATE_FIELDS]
        route["pokemonTables"] = [route["_pokemonTablesByKey"][key] for key in ENCOUNTER_POKEMON_TABLES]
        route["slotTables"] = [route["_slotTablesByKey"][key] for key in ENCOUNTER_SLOT_TABLES]
        route["headbuttTables"] = headbutt_tables_for_route(route["maps"], headbutt_by_map_id or {})
        route["species"] = route_species_summary(route, form_species)
        route["speciesCount"] = len(route["species"])
        del route["_ratesByKey"]
        del route["_pokemonTablesByKey"]
        del route["_slotTablesByKey"]
        routes.append(route)

    def new_route(route_id: int, name: str) -> dict:
        return {
            "id": route_id,
            "name": name or f"Encounter data {route_id}",
            "maps": encounter_area_maps.get(route_id, []),
            "rates": [],
            "_ratesByKey": {},
            "grassLevels": [],
            "pokemonTables": [],
            "_pokemonTablesByKey": {
                key: {
                    "key": key,
                    "label": label,
                    "weights": GRASS_SLOT_WEIGHTS if key in {"morning", "day", "night"} else SOUND_SLOT_WEIGHTS,
                    "slots": [],
                }
                for key, (label, _) in ENCOUNTER_POKEMON_TABLES.items()
            },
            "slotTables": [],
            "headbuttTables": [],
            "_slotTablesByKey": {
                key: {
                    "key": key,
                    "label": label,
                    "weights": weights,
                    "slots": [],
                }
                for key, (label, _, weights) in ENCOUNTER_SLOT_TABLES.items()
            },
            "swarms": [],
            "species": [],
            "speciesCount": 0,
        }

    for line_no, line in enumerate(lines):
        header_match = route_header.match(line.strip())
        if header_match:
            finish_route()
            route_id = int(header_match.group(1), 10)
            route = new_route(route_id, clean_token(header_match.group(2) or ""))
            current_table = None
            table_counts = {}
            continue
        if route is None:
            continue
        stripped = line.strip()
        if stripped == ".close":
            finish_route()
            route = None
            current_table = None
            table_counts = {}
            continue
        if stripped.startswith("//"):
            comment = stripped[2:].strip().lower()
            current_table = ENCOUNTER_COMMENT_TABLES.get(comment)
            continue
        for key, label in ENCOUNTER_RATE_FIELDS:
            match = re.match(rf"^{key}\s+(\d+)\s*$", stripped)
            if match:
                route["_ratesByKey"][key] = {
                    "key": key,
                    "label": label,
                    "value": int(match.group(1), 10),
                    "path": f"rate.{key}",
                    "line": line_no,
                }
                break
        else:
            walklevels = re.match(r"^walklevels\s+(.+)$", stripped)
            if walklevels:
                levels = split_csv_numbers(walklevels.group(1), len(GRASS_SLOT_WEIGHTS), f"encounterdata {route['id']} walklevels")
                route["grassLevels"] = [
                    {
                        "slot": index + 1,
                        "weight": GRASS_SLOT_WEIGHTS[index],
                        "value": level,
                        "path": f"grassLevels.{index}",
                        "line": line_no,
                    }
                    for index, level in enumerate(levels)
                ]
                continue
            pokemon_match = re.match(r"^(pokemon|monwithform)\s+(SPECIES_[A-Z0-9_]+)(?:\s*,\s*(\d+))?\s*$", stripped)
            if pokemon_match and current_table:
                kind, key = current_table
                macro = pokemon_match.group(1)
                species = make_encounter_species(pokemon_match.group(2), species_by_symbol, macros)
                form = int(pokemon_match.group(3) or "0", 10)
                if macro == "pokemon" and pokemon_match.group(3) is not None:
                    raise ParseError(f"encounterdata {route['id']} has a malformed pokemon form line")
                if kind == "pokemon":
                    table = route["_pokemonTablesByKey"][key]
                    slot_index = len(table["slots"])
                    table["slots"].append(
                        {
                            "slot": slot_index + 1,
                            "weight": table["weights"][slot_index] if slot_index < len(table["weights"]) else None,
                            "species": species,
                            "form": form,
                            "path": f"pokemon.{key}.{slot_index}",
                            "formPath": f"pokemon.{key}.{slot_index}.form",
                            "line": line_no,
                        }
                    )
                elif kind == "swarm":
                    route["swarms"].append(
                        {
                            "key": key,
                            "label": ENCOUNTER_SWARM_FIELDS[key],
                            "species": species,
                            "form": form,
                            "path": f"swarm.{key}",
                            "formPath": f"swarm.{key}.form",
                            "line": line_no,
                        }
                    )
                continue
            encounter_match = re.match(
                r"^(encounter|encounterwithform)\s+(SPECIES_[A-Z0-9_]+)\s*,\s*(?:(\d+)\s*,\s*)?(\d+)\s*,\s*(\d+)\s*$",
                stripped,
            )
            if encounter_match and current_table and current_table[0] == "slot":
                _, key = current_table
                table = route["_slotTablesByKey"][key]
                slot_index = len(table["slots"])
                macro = encounter_match.group(1)
                form = int(encounter_match.group(3) or "0", 10)
                if macro == "encounter" and encounter_match.group(3) is not None:
                    raise ParseError(f"encounterdata {route['id']} has a malformed encounter form line")
                table["slots"].append(
                    {
                        "slot": slot_index + 1,
                        "weight": table["weights"][slot_index] if slot_index < len(table["weights"]) else None,
                        "species": make_encounter_species(encounter_match.group(2), species_by_symbol, macros),
                        "form": form,
                        "minLevel": int(encounter_match.group(4), 10),
                        "maxLevel": int(encounter_match.group(5), 10),
                        "paths": {
                            "species": f"slot.{key}.{slot_index}.species",
                            "form": f"slot.{key}.{slot_index}.form",
                            "minLevel": f"slot.{key}.{slot_index}.minLevel",
                            "maxLevel": f"slot.{key}.{slot_index}.maxLevel",
                        },
                        "line": line_no,
                    }
                )
                table_counts[key] = table_counts.get(key, 0) + 1
    finish_route()
    return routes


def parse_route_edit_payload(body: bytes) -> dict[int, dict[str, str]]:
    try:
        payload = json.loads(body.decode())
    except Exception as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    changes = payload.get("changes") if isinstance(payload, dict) else None
    if not isinstance(changes, dict):
        raise ValueError("missing changes object")
    parsed: dict[int, dict[str, str]] = {}
    for raw_route_id, raw_changes in changes.items():
        try:
            route_id = int(raw_route_id)
        except Exception as exc:
            raise ValueError(f"invalid route id: {raw_route_id}") from exc
        if not isinstance(raw_changes, dict):
            raise ValueError(f"route {route_id} changes must be an object")
        parsed[route_id] = {clean_token(str(path)): clean_token(str(value)) for path, value in raw_changes.items()}
    return parsed


def parse_int_range(raw: str, label: str, minimum: int, maximum: int) -> int:
    try:
        value = int(clean_token(raw), 10)
    except ValueError as exc:
        raise ValueError(f"{label} must be a number") from exc
    if value < minimum or value > maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return value


def line_ending(line: str) -> str:
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    return ""


def find_define_setting(path: Path, symbol: str) -> dict:
    pattern = re.compile(rf"^([ \t]*#define[ \t]+{re.escape(symbol)}[ \t]+)([^/\n]+?)([ \t]*(?://.*)?)$")
    for line_no, line in enumerate(path.read_text().splitlines()):
        match = pattern.match(line)
        if match:
            return {
                "line": line_no,
                "prefix": match.group(1),
                "raw": clean_token(match.group(2)),
                "suffix": match.group(3),
            }
    raise ParseError(f"could not find #define {symbol} in {path.relative_to(ROOT)}")


def parse_spawn_setting_definition(setting: dict, macros: dict[str, int], group: dict) -> dict:
    source_path = setting["source"]
    define = find_define_setting(source_path, setting["symbol"])
    value = make_value(define["raw"], None, macros)
    return {
        "symbol": setting["symbol"],
        "label": setting["label"],
        "kind": setting.get("kind", "number"),
        "role": setting.get("role", ""),
        "raw": define["raw"],
        "value": value["value"],
        "symbolValue": value.get("symbol"),
        "min": setting.get("min"),
        "max": setting.get("max"),
        "suffix": setting.get("suffix", ""),
        "source": str(source_path.relative_to(ROOT)),
        "groupKey": group["key"],
        "groupLabel": group["label"],
    }


def parse_spawn_settings(macros: dict[str, int], species_by_symbol: dict[str, dict] | None = None) -> list[dict]:
    groups = []
    for group in SPAWN_SETTING_GROUPS:
        parsed_settings = []
        for setting in group["settings"]:
            if setting.get("kind") == "testSpawn":
                parsed_fields = [
                    parse_spawn_setting_definition(field, macros, group)
                    for field in setting.get("fields", [])
                ]
                fields_by_role = {field.get("role"): field for field in parsed_fields}
                species_field = fields_by_role.get("species", {})
                species_symbol = species_field.get("symbolValue") or species_field.get("raw") or "SPECIES_NONE"
                species = make_encounter_species(species_symbol, species_by_symbol or {}, macros)
                parsed_settings.append(
                    {
                        "symbol": setting["symbol"],
                        "label": setting["label"],
                        "kind": "testSpawn",
                        "source": str(setting["source"].relative_to(ROOT)),
                        "groupKey": group["key"],
                        "groupLabel": group["label"],
                        "fields": parsed_fields,
                        "testSpawn": {
                            "enabled": int(fields_by_role.get("enabled", {}).get("value") or 0),
                            "speciesSymbol": species_symbol,
                            "species": species,
                            "level": int(fields_by_role.get("level", {}).get("value") or 1),
                        },
                    }
                )
                continue
            parsed_settings.append(parse_spawn_setting_definition(setting, macros, group))
        groups.append(
            {
                "key": group["key"],
                "label": group["label"],
                "settings": parsed_settings,
            }
        )
    return groups


def parse_spawn_setting_payload(body: bytes) -> dict[str, str]:
    try:
        payload = json.loads(body.decode())
    except Exception as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    changes = payload.get("changes") if isinstance(payload, dict) else None
    if not isinstance(changes, dict):
        raise ValueError("missing changes object")
    parsed: dict[str, str] = {}
    for raw_symbol, raw_value in changes.items():
        symbol = clean_token(str(raw_symbol))
        if symbol not in SPAWN_SETTING_BY_SYMBOL:
            raise ValueError(f"invalid spawn setting: {symbol}")
        parsed[symbol] = clean_token(str(raw_value))
    return parsed


def apply_spawn_setting_changes(body: bytes) -> dict:
    changes = parse_spawn_setting_payload(body)
    if not changes:
        return {"saved": False, "message": "No changes"}

    expressions, species_order = parse_define_expressions(DEFINE_SOURCE_FILES)
    macros = evaluate_defines(expressions)
    species = parse_species(expressions, macros, species_order)
    valid_species = {
        entry["symbol"]
        for entry in build_encounter_species_options(species, macros)
    }
    current_values: dict[str, int] = {}
    define_info: dict[str, dict] = {}
    for symbol, setting in SPAWN_SETTING_BY_SYMBOL.items():
        define = find_define_setting(setting["source"], symbol)
        define_info[symbol] = define
        if setting.get("kind") == "species":
            continue
        value = make_value(define["raw"], None, macros)["value"]
        if value is None:
            raise ValueError(f"{symbol} is not numeric")
        current_values[symbol] = value

    updated_values = dict(current_values)
    parsed_changes: dict[str, int | str] = {}
    for symbol, raw_value in changes.items():
        setting = SPAWN_SETTING_BY_SYMBOL[symbol]
        if setting.get("kind") == "species":
            normalized = clean_token(str(raw_value)).upper()
            if normalized and not normalized.startswith("SPECIES_"):
                normalized = f"SPECIES_{normalized}"
            if normalized not in valid_species:
                raise ValueError(f"{setting['label']} must be a valid Pokemon")
            parsed_changes[symbol] = normalized
            continue
        value = parse_int_range(raw_value, setting["label"], setting["min"], setting["max"])
        parsed_changes[symbol] = value
        updated_values[symbol] = value

    if updated_values["OW_WILD_SPAWN_MIN_DISTANCE"] > updated_values["OW_WILD_SPAWN_MAX_DISTANCE"]:
        raise ValueError("Spawn min distance cannot be greater than spawn max distance")
    if updated_values["OW_WILD_DESPAWN_DISTANCE"] < updated_values["OW_WILD_SPAWN_MAX_DISTANCE"]:
        raise ValueError("Despawn distance must be at least spawn max distance")

    lines_by_path: dict[Path, list[str]] = {}
    changed = False
    for symbol, value in parsed_changes.items():
        setting = SPAWN_SETTING_BY_SYMBOL[symbol]
        source_path = setting["source"]
        if source_path not in lines_by_path:
            lines_by_path[source_path] = source_path.read_text().splitlines(True)
        lines = lines_by_path[source_path]
        line_no = define_info[symbol]["line"]
        ending = line_ending(lines[line_no])
        line_without_ending = lines[line_no][: len(lines[line_no]) - len(ending)] if ending else lines[line_no]
        pattern = re.compile(rf"^([ \t]*#define[ \t]+{re.escape(symbol)}[ \t]+)([^/\s]+)(.*)$")
        match = pattern.match(line_without_ending)
        if not match:
            raise ParseError(f"could not rewrite #define {symbol}")
        replacement = f"{match.group(1)}{value}{match.group(3)}{ending}"
        if lines[line_no] != replacement:
            lines[line_no] = replacement
            changed = True

    if changed:
        for source_path, lines in lines_by_path.items():
            source_path.write_text("".join(lines))
        invalidate_data_cache()
    return {"saved": changed, "message": "Saved" if changed else "No code changes needed"}


def apply_encounter_changes(body: bytes) -> dict:
    changes = parse_route_edit_payload(body)
    if not changes:
        return {"saved": False, "message": "No changes"}

    raw_overlay = OVERLAY_SOURCE.read_text()
    source = strip_c_comments(join_line_continuations(raw_overlay))
    expressions, species_order = parse_define_expressions(DEFINE_SOURCE_FILES)
    macros = evaluate_defines(expressions)
    species = parse_species(expressions, macros, species_order)
    encounter_species_options = build_encounter_species_options(species, macros)
    species_by_symbol = {entry["symbol"]: entry for entry in encounter_species_options}
    valid_species = {entry["symbol"] for entry in encounter_species_options}
    valid_species.add("SPECIES_NONE")
    headbutt_by_map_id = parse_headbutt_encounters(species_by_symbol, macros)
    routes = parse_route_encounters(
        species_by_symbol,
        macros,
        parse_encounter_area_maps(source, macros),
        headbutt_by_map_id,
    )
    route_by_id = {route["id"]: route for route in routes}
    path_index: dict[tuple[int, str], dict] = {}

    for route in routes:
        for rate in route["rates"]:
            path_index[(route["id"], rate["path"])] = {"kind": "rate", "item": rate}
        for level in route["grassLevels"]:
            path_index[(route["id"], level["path"])] = {"kind": "grassLevel", "item": level, "route": route}
        for table in route["pokemonTables"]:
            for slot in table["slots"]:
                path_index[(route["id"], slot["path"])] = {"kind": "pokemon", "field": "species", "item": slot}
                path_index[(route["id"], slot["formPath"])] = {"kind": "pokemon", "field": "form", "item": slot}
        for table in route["slotTables"]:
            for slot in table["slots"]:
                for field, path in slot["paths"].items():
                    path_index[(route["id"], path)] = {"kind": "slot", "field": field, "item": slot}
        for table in route.get("headbuttTables", []):
            for slot in table["slots"]:
                for field, path in slot["paths"].items():
                    path_index[(route["id"], path)] = {"kind": "headbuttSlot", "field": field, "item": slot}
        for swarm in route["swarms"]:
            path_index[(route["id"], swarm["path"])] = {"kind": "pokemon", "field": "species", "item": swarm}
            path_index[(route["id"], swarm["formPath"])] = {"kind": "pokemon", "field": "form", "item": swarm}

    pending_by_line: dict[int, dict] = {}
    pending_headbutt_by_line: dict[int, dict] = {}
    for route_id, route_changes in changes.items():
        if route_id not in route_by_id:
            raise ValueError(f"unknown route id: {route_id}")
        for path, raw_value in route_changes.items():
            meta = path_index.get((route_id, path))
            if meta is None:
                raise ValueError(f"unknown route edit path for {route_id}: {path}")
            kind = meta["kind"]
            item = meta["item"]
            line_no = item["line"]
            pending_target = pending_headbutt_by_line if kind == "headbuttSlot" else pending_by_line
            pending = pending_target.setdefault(line_no, {"kind": kind, "item": item, "values": {}})
            if kind == "rate":
                pending["values"]["value"] = parse_int_range(raw_value, "rate", 0, 100)
            elif kind == "grassLevel":
                pending["values"][item["path"]] = parse_int_range(raw_value, "grass level", 0, 100)
            elif kind == "pokemon":
                field = meta["field"]
                if field == "species":
                    if raw_value not in valid_species:
                        raise ValueError(f"invalid species: {raw_value}")
                    pending["values"]["species"] = raw_value
                else:
                    pending["values"]["form"] = parse_int_range(raw_value, "form", 0, 31)
            elif kind == "slot":
                field = meta["field"]
                if field == "species":
                    if raw_value not in valid_species:
                        raise ValueError(f"invalid species: {raw_value}")
                    pending["values"]["species"] = raw_value
                elif field == "form":
                    pending["values"]["form"] = parse_int_range(raw_value, "form", 0, 31)
                else:
                    pending["values"][field] = parse_int_range(raw_value, field, 0, 100)
            elif kind == "headbuttSlot":
                field = meta["field"]
                if field == "species":
                    if raw_value not in valid_species:
                        raise ValueError(f"invalid species: {raw_value}")
                    pending["values"]["species"] = raw_value
                elif field == "form":
                    pending["values"]["form"] = parse_int_range(raw_value, "form", 0, 31)
                else:
                    pending["values"][field] = parse_int_range(raw_value, field, 0, 100)

    lines = ENCOUNTERS_SOURCE.read_text().splitlines(True)
    for line_no, pending in pending_by_line.items():
        item = pending["item"]
        ending = line_ending(lines[line_no])
        kind = pending["kind"]
        values = pending["values"]
        if kind == "rate":
            value = values.get("value", item["value"])
            lines[line_no] = f"{item['key']} {value}{ending}"
        elif kind == "grassLevel":
            route = pending["route"]
            levels = [level["value"] for level in route["grassLevels"]]
            for path, value in values.items():
                index = int(path.rsplit(".", 1)[1])
                levels[index] = value
            lines[line_no] = f"walklevels {', '.join(str(level) for level in levels)}{ending}"
        elif kind == "pokemon":
            species = values.get("species", item["species"]["symbol"])
            form = values.get("form", item.get("form", 0))
            if form:
                lines[line_no] = f"monwithform {species}, {form}{ending}"
            else:
                lines[line_no] = f"pokemon {species}{ending}"
        elif kind == "slot":
            species = values.get("species", item["species"]["symbol"])
            form = values.get("form", item.get("form", 0))
            min_level = values.get("minLevel", item["minLevel"])
            max_level = values.get("maxLevel", item["maxLevel"])
            if min_level > max_level:
                raise ValueError(f"min level cannot be greater than max level on line {line_no + 1}")
            if form:
                lines[line_no] = f"encounterwithform {species}, {form}, {min_level}, {max_level}{ending}"
            else:
                lines[line_no] = f"encounter {species}, {min_level}, {max_level}{ending}"

    updated = "".join(lines)
    encounters_changed = updated != ENCOUNTERS_SOURCE.read_text()
    if encounters_changed:
        ENCOUNTERS_SOURCE.write_text(updated)

    headbutt_lines = HEADBUTT_SOURCE.read_text(encoding="latin-1").splitlines(True)
    for line_no, pending in pending_headbutt_by_line.items():
        item = pending["item"]
        ending = line_ending(headbutt_lines[line_no])
        values = pending["values"]
        species = values.get("species", item["species"]["symbol"])
        form = values.get("form", item.get("form", 0))
        min_level = values.get("minLevel", item["minLevel"])
        max_level = values.get("maxLevel", item["maxLevel"])
        if min_level > max_level:
            raise ValueError(f"min level cannot be greater than max level on line {line_no + 1}")
        if form:
            headbutt_lines[line_no] = f"    headbuttencounterwithform {species}, {form}, {min_level}, {max_level}{ending}"
        else:
            headbutt_lines[line_no] = f"    headbuttencounter {species}, {min_level}, {max_level}{ending}"
    headbutt_updated = "".join(headbutt_lines)
    headbutt_changed = headbutt_updated != HEADBUTT_SOURCE.read_text(encoding="latin-1")
    if headbutt_changed:
        HEADBUTT_SOURCE.write_text(headbutt_updated, encoding="latin-1")

    changed = encounters_changed or headbutt_changed
    if changed:
        invalidate_data_cache()
    return {"saved": changed, "message": "Saved" if changed else "No code changes needed"}


def parse_icon_paths() -> dict[int, Path]:
    if not POKEGRA_MK.exists():
        return {}
    icon_paths: dict[int, Path] = {}
    pattern = re.compile(r"build/pokemonicon/1_(\d+)\.NCGR:\s+([^\s]+/icon\.png)")
    for line in POKEGRA_MK.read_text().splitlines():
        match = pattern.search(line)
        if not match:
            continue
        species_value = int(match.group(1), 10)
        icon_path = ROOT / match.group(2)
        if icon_path.exists():
            icon_paths[species_value] = icon_path
    return icon_paths


@lru_cache(maxsize=1)
def cached_icon_paths() -> dict[int, Path]:
    return parse_icon_paths()


def render_icon_png(icon_path: Path) -> bytes:
    with Image.open(icon_path) as image:
        frame_size = min(image.width, image.height)
        frame = image.crop((0, 0, image.width, frame_size))
        if frame.mode == "P":
            alpha = frame.point(lambda index: 0 if index == 0 else 255, "L")
            frame = frame.convert("RGBA")
            frame.putalpha(alpha)
        else:
            frame = frame.convert("RGBA")
        output = io.BytesIO()
        frame.save(output, format="PNG")
        return output.getvalue()


@lru_cache(maxsize=2048)
def cached_render_icon_png(icon_path: str) -> bytes:
    return render_icon_png(Path(icon_path))


def invert_labels(macros: dict[str, int], prefix: str) -> dict[int, dict]:
    result = {}
    for symbol, value in macros.items():
        if symbol.startswith(prefix):
            result[value] = {
                "symbol": symbol,
                "name": humanize_symbol(symbol, prefix),
                "value": value,
            }
    return dict(sorted(result.items()))


def match_applies(context: dict, match: dict, macros: dict[str, int]) -> bool:
    any_species = macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_SPECIES", macros.get("SPECIES_NONE", 0))
    if numeric(match["species"]) != any_species and numeric(match["species"]) != context["species"]:
        return False
    if numeric(match["groupMask"]) != macros.get("OW_WILD_BEHAVIOR_GROUP_NONE", 0):
        if (context["groupFlags"] & (numeric(match["groupMask"]) or 0)) == 0:
            return False
    if numeric(match["terrain"]) != macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_TERRAIN"):
        if numeric(match["terrain"]) != context["terrain"]:
            return False
    if numeric(match["minLevel"]) != macros.get("OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY", 0):
        if context["level"] < (numeric(match["minLevel"]) or 0):
            return False
    if numeric(match["maxLevel"]) != macros.get("OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY", 0):
        if context["level"] > (numeric(match["maxLevel"]) or 0):
            return False
    if numeric(match["shiny"]) != macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_SHINY"):
        if numeric(match["shiny"]) != context["shiny"]:
            return False
    if numeric(match["behaviorClass"]) != macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_CLASS"):
        if numeric(match["behaviorClass"]) != context["behaviorClass"]:
            return False
    return True


def match_summary(match: dict, macros: dict[str, int], group_labels: dict[int, dict]) -> str:
    parts = []
    any_species = macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_SPECIES", macros.get("SPECIES_NONE", 0))
    if numeric(match["species"]) != any_species:
        parts.append(match["species"]["label"])
    if numeric(match["groupMask"]) != macros.get("OW_WILD_BEHAVIOR_GROUP_NONE", 0):
        group = group_labels.get(numeric(match["groupMask"]) or -1)
        parts.append(group["name"] if group else match["groupMask"]["label"])
    if numeric(match["terrain"]) != macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_TERRAIN"):
        parts.append(f"terrain {match['terrain']['label']}")
    min_level = numeric(match["minLevel"])
    max_level = numeric(match["maxLevel"])
    if min_level != macros.get("OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY", 0) or max_level != macros.get("OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY", 0):
        lo = str(min_level) if min_level else "any"
        hi = str(max_level) if max_level else "any"
        parts.append(f"level {lo}-{hi}")
    if numeric(match["shiny"]) != macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_SHINY"):
        parts.append("shiny" if numeric(match["shiny"]) else "not shiny")
    if numeric(match["behaviorClass"]) != macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_CLASS"):
        parts.append(f"class {match['behaviorClass']['label']}")
    return ", ".join(parts) if parts else "All Pokemon"


def class_for_context(context: dict, class_rules: list[dict], class_count: int, macros: dict[str, int]) -> tuple[int, list[dict]]:
    behavior_class = macros.get("OW_WILD_BEHAVIOR_CLASS_DEFAULT", 0)
    hits = []
    for rule in class_rules:
        context["behaviorClass"] = behavior_class
        if match_applies(context, rule["match"], macros):
            behavior_class = numeric(rule["behaviorClass"]) or 0
            hits.append(rule)
    if behavior_class >= class_count:
        behavior_class = macros.get("OW_WILD_BEHAVIOR_CLASS_DEFAULT", 0)
    return behavior_class, hits


def resolve_profile_for_context(
    context: dict,
    class_profiles: list[dict[str, dict]],
    variable_overrides: list[dict],
    macros: dict[str, int],
) -> tuple[dict[str, dict], list[dict], list[dict], list[dict]]:
    class_index = context["behaviorClass"]
    if class_index >= len(class_profiles):
        class_index = macros.get("OW_WILD_BEHAVIOR_CLASS_DEFAULT", 0)
    profile = clone_profile(class_profiles[class_index])
    layers = [{"kind": "class", "label": f"Class profile #{class_index}", "changes": []}]
    variable_hits = []
    for override in variable_overrides:
        if match_applies(context, override["match"], macros):
            changes = merge_profile(profile, override["behavior"])
            variable_hits.append(override)
            layers.append(
                {
                    "kind": "behaviorOverride",
                    "label": f"Behavior override #{override['order']}",
                    "changes": changes,
                    "mask": behavior_override_mask_summary(override["behavior"]),
                }
            )
    normalizations = normalize_profile(profile, macros)
    if normalizations:
        layers.append({"kind": "normalization", "label": "Runtime fallback", "changes": normalizations})
    return profile, layers, variable_hits, normalizations


def group_flags_for_species(
    symbol: str,
    group_species: dict[int, list[str]],
    species_by_symbol: dict[str, dict] | None = None,
    macros: dict[str, int] | None = None,
) -> int:
    flags = 0
    for group, symbols in group_species.items():
        if symbol in symbols:
            flags |= group
    if species_by_symbol is not None and macros is not None:
        flags |= species_type_group_flags(species_by_symbol.get(symbol), macros)
    return flags


def data_source_metadata() -> dict[str, str]:
    return {
        "overlay": str(OVERLAY_SOURCE.relative_to(ROOT)),
        "helper": str(HELPER_SOURCE.relative_to(ROOT)),
        "behaviorData": str(BEHAVIOR_DATA_SOURCE.relative_to(ROOT)),
        "behaviorDataHeader": str(BEHAVIOR_DATA_HEADER.relative_to(ROOT)),
        "species": str(SPECIES_HEADER.relative_to(ROOT)),
        "spawnPublic": str(SPAWNS_PUBLIC_HEADER.relative_to(ROOT)),
        "spawnInternal": str(SPAWNS_INTERNAL_HEADER.relative_to(ROOT)),
        "wildTest": str(ENEMY_PARTY_SOURCE.relative_to(ROOT)),
        "icons": str(POKEGRA_MK.relative_to(ROOT)),
        "encounters": str(ENCOUNTERS_SOURCE.relative_to(ROOT)),
        "headbutt": str(HEADBUTT_SOURCE.relative_to(ROOT)),
    }


def profile_error_payload(exc: Exception | None) -> dict | None:
    if exc is None:
        return None
    return {
        "type": type(exc).__name__,
        "message": str(exc),
    }


def build_route_only_data(profile_error: Exception | None = None) -> dict:
    raw_overlay = OVERLAY_SOURCE.read_text()
    source = strip_c_comments(join_line_continuations(raw_overlay))
    expressions, species_order = parse_define_expressions(DEFINE_SOURCE_FILES)
    macros = evaluate_defines(expressions)
    macros.update(evaluate_armips_equ([ARMIPS_CONFIG, ARMIPS_CONSTANTS]))
    terrain_values, destination_values = parse_behavior_data_enums()
    macros.update(terrain_values)
    macros.update(destination_values)

    species = parse_species(expressions, macros, species_order)
    apply_species_type_metadata(species, parse_species_type_metadata(macros))
    icon_paths = cached_icon_paths()
    for entry in species:
        if entry["value"] in icon_paths:
            entry["iconUrl"] = f"/icons/{entry['value']}.png"
    species_by_symbol = {entry["symbol"]: entry for entry in species}
    apply_regional_form_metadata(species, species_by_symbol, macros)
    species_by_value = {entry["value"]: entry for entry in species}
    species_options = build_encounter_species_options(species, macros)
    encounter_species_by_symbol = {entry["symbol"]: entry for entry in species_options}
    headbutt_by_map_id = parse_headbutt_encounters(encounter_species_by_symbol, macros)
    routes = parse_route_encounters(
        encounter_species_by_symbol,
        macros,
        parse_encounter_area_maps(source, macros),
        headbutt_by_map_id,
    )
    spawn_settings = parse_spawn_settings(macros, encounter_species_by_symbol)

    return {
        "generatedAt": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "source": data_source_metadata(),
        "profilesAvailable": False,
        "profileError": profile_error_payload(profile_error),
        "fields": [],
        "counts": {
            "species": 0,
            "classes": 0,
            "classRules": 0,
            "maxSpeedOverrides": 0,
            "variableOverrides": 0,
            "routes": len(routes),
        },
        "labels": {
            "classes": {},
            "groups": {},
            "terrains": {
                value: {"symbol": name, "name": humanize_symbol(name, TERRAIN_PREFIX), "value": value}
                for name, value in terrain_values.items()
            },
            "destinations": {
                value: {"symbol": name, "name": macro_label(name, value, "spawnDestination", macros), "value": value}
                for name, value in destination_values.items()
            },
        },
        "editOptions": {},
        "defaultClassIndex": 0,
        "defaultProfile": None,
        "primitiveFields": [{"key": field, "label": PRIMITIVE_FIELD_LABELS[field]} for field in PRIMITIVE_FIELDS],
        "primitiveMaps": {},
        "classes": [],
        "classRules": [],
        "maxSpeedOverrides": [],
        "variableOverrides": [],
        "groups": [],
        "assignments": [],
        "speciesByValue": species_by_value,
        "speciesOptions": species_options,
        "typeOptions": build_type_options(macros),
        "spawnSettings": spawn_settings,
        "routes": routes,
    }


def build_data() -> dict:
    raw_overlay = OVERLAY_SOURCE.read_text()
    source = strip_c_comments(join_line_continuations(raw_overlay))
    raw_behavior_data = BEHAVIOR_DATA_SOURCE.read_text()
    behavior_source = strip_c_comments(join_line_continuations(raw_behavior_data))
    expressions, species_order = parse_define_expressions(DEFINE_SOURCE_FILES)
    macros = evaluate_defines(expressions)
    macros.update(evaluate_armips_equ([ARMIPS_CONFIG, ARMIPS_CONSTANTS]))
    terrain_values, destination_values = parse_behavior_data_enums()
    macros.update(terrain_values)
    macros.update(destination_values)

    class_labels = invert_labels(macros, CLASS_PREFIX)
    group_labels = invert_labels(macros, GROUP_PREFIX)
    terrain_labels = {value: {"symbol": name, "name": humanize_symbol(name, TERRAIN_PREFIX), "value": value} for name, value in terrain_values.items()}
    destination_labels = {value: {"symbol": name, "name": macro_label(name, value, "spawnDestination", macros), "value": value} for name, value in destination_values.items()}
    primitive_maps = parse_primitive_maps(source, macros)

    class_profiles = [
        parse_profile(entry, macros)
        for entry in parse_initializer(extract_braced_initializer(behavior_source, "sOverworldWildBehaviorClassProfiles"))
    ]
    default_class = macros.get("OW_WILD_BEHAVIOR_CLASS_DEFAULT", 0)
    default_profile = class_profiles[default_class]
    class_rules = parse_behavior_class_rules(behavior_source, macros, group_labels, class_labels)

    variable_overrides = parse_behavior_overrides(behavior_source, macros, group_labels)

    group_species = parse_group_species(source, macros)
    species = parse_species(expressions, macros, species_order)
    apply_species_type_metadata(species, parse_species_type_metadata(macros))
    icon_paths = cached_icon_paths()
    for entry in species:
        if entry["value"] in icon_paths:
            entry["iconUrl"] = f"/icons/{entry['value']}.png"
    species_by_symbol = {entry["symbol"]: entry for entry in species}
    apply_regional_form_metadata(species, species_by_symbol, macros)
    species_by_value = {entry["value"]: entry for entry in species}
    species_options = build_encounter_species_options(species, macros)
    encounter_species_by_symbol = {entry["symbol"]: entry for entry in species_options}
    headbutt_by_map_id = parse_headbutt_encounters(encounter_species_by_symbol, macros)
    routes = parse_route_encounters(
        encounter_species_by_symbol,
        macros,
        parse_encounter_area_maps(source, macros),
        headbutt_by_map_id,
    )
    spawn_settings = parse_spawn_settings(macros, encounter_species_by_symbol)

    assignments = []
    default_terrain = macros.get("OW_WILD_SPAWN_TERRAIN_LAND", 0)
    for entry in species:
        context = {
            "species": entry["value"],
            "symbol": entry["symbol"],
            "level": 1,
            "terrain": default_terrain,
            "shiny": 0,
            "groupFlags": group_flags_for_species(entry["symbol"], group_species, species_by_symbol, macros),
            "behaviorClass": macros.get("OW_WILD_BEHAVIOR_CLASS_DEFAULT", 0),
        }
        behavior_class, class_hits = class_for_context(context, class_rules, len(class_profiles), macros)
        context["behaviorClass"] = behavior_class
        profile, layers, variable_hits, _ = resolve_profile_for_context(
            context,
            class_profiles,
            variable_overrides,
            macros,
        )
        max_speed_hits = [
            {"order": override["order"], "summary": override["summary"], "fields": behavior_override_mask_summary(override["behavior"])["labels"]}
            for override in variable_hits
        ]
        group_names = [
            label["name"]
            for group, label in group_labels.items()
            if context["groupFlags"] & group and group != macros.get("OW_WILD_BEHAVIOR_GROUP_NONE", 0)
        ]
        class_label = class_labels.get(behavior_class, {"symbol": str(behavior_class), "name": str(behavior_class)})
        assignments.append(
            {
                "species": entry,
                "groups": group_names,
                "behaviorClass": class_label,
                "profile": profile,
                "primitives": resolve_primitives(profile, primitive_maps, macros),
                "profileId": profile["profileId"],
                "classRuleHits": [{"order": rule["order"], "summary": rule["summary"], "className": rule["className"]} for rule in class_hits],
                "maxSpeedOverrideHits": max_speed_hits,
                "variableOverrideHits": max_speed_hits,
                "layers": layers,
            }
        )

    classes = []
    for index, class_profile in enumerate(class_profiles):
        class_label = class_labels.get(index, {"symbol": str(index), "name": f"Class {index}", "value": index})
        targeting_rules = [
            {"order": rule["order"], "summary": rule["summary"], "behaviorClass": rule["behaviorClass"]}
            for rule in class_rules
            if numeric(rule["behaviorClass"]) == index
        ]
        context = {
            "species": macros.get("SPECIES_NONE", 0),
            "level": 1,
            "terrain": default_terrain,
            "shiny": 0,
            "groupFlags": 0,
            "behaviorClass": index,
        }
        profile, layers, _, _ = resolve_profile_for_context(
            context,
            class_profiles,
            [],
            macros,
        )
        classes.append(
            {
                "index": index,
                "symbol": class_label["symbol"],
                "name": class_label["name"],
                "canRename": index != default_class,
                "canDelete": index != default_class and not class_symbol_used_by_runtime(class_label["symbol"]),
                "override": {"mask": parse_mask("0", macros), "profile": class_profile},
                "profile": profile,
                "primitives": resolve_primitives(profile, primitive_maps, macros),
                "editProfile": class_profile,
                "layers": layers,
                "classRules": targeting_rules,
                "classRuleCount": len(targeting_rules),
                "speciesCount": sum(1 for item in assignments if item["behaviorClass"]["value"] == index),
            }
        )

    return {
        "generatedAt": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "source": data_source_metadata(),
        "profilesAvailable": True,
        "profileError": None,
        "fields": [{"key": field, "label": FIELD_LABELS[field]} for field in PROFILE_FIELDS],
        "counts": {
            "species": len(assignments),
            "classes": len(classes),
            "classRules": len(class_rules),
            "maxSpeedOverrides": len(variable_overrides),
            "variableOverrides": len(variable_overrides),
            "routes": len(routes),
        },
        "labels": {
            "classes": class_labels,
            "groups": group_labels,
            "terrains": terrain_labels,
            "destinations": destination_labels,
        },
        "editOptions": build_edit_options(macros, class_profiles),
        "defaultClassIndex": default_class,
        "defaultProfile": default_profile,
        "primitiveFields": [{"key": field, "label": PRIMITIVE_FIELD_LABELS[field]} for field in PRIMITIVE_FIELDS],
        "primitiveMaps": primitive_maps,
        "classes": classes,
        "classRules": class_rules,
        "maxSpeedOverrides": variable_overrides,
        "variableOverrides": variable_overrides,
        "groups": [
            {
                "group": group_labels.get(group, {"name": str(group), "symbol": str(group), "value": group}),
                "species": [species_by_symbol[symbol] for symbol in symbols if symbol in species_by_symbol],
            }
            for group, symbols in sorted(group_species.items())
        ],
        "assignments": assignments,
        "speciesByValue": species_by_value,
        "speciesOptions": species_options,
        "typeOptions": build_type_options(macros),
        "spawnSettings": spawn_settings,
        "routes": routes,
    }


def data_source_key() -> tuple[tuple[str, int | None, int | None], ...]:
    key = []
    for path in DATA_SOURCE_FILES:
        try:
            stat = path.stat()
        except FileNotFoundError:
            key.append((str(path.relative_to(ROOT)), None, None))
        else:
            key.append((str(path.relative_to(ROOT)), stat.st_mtime_ns, stat.st_size))
    return tuple(key)


def invalidate_data_cache() -> None:
    with DATA_CACHE_LOCK:
        DATA_JSON_CACHE.update({"key": None, "body": b"", "gzip": b"", "etag": ""})
    cached_icon_paths.cache_clear()
    cached_render_icon_png.cache_clear()


def cached_data_json() -> dict[str, bytes | str]:
    key = data_source_key()
    with DATA_CACHE_LOCK:
        if DATA_JSON_CACHE["key"] == key:
            return {
                "body": DATA_JSON_CACHE["body"],
                "gzip": DATA_JSON_CACHE["gzip"],
                "etag": DATA_JSON_CACHE["etag"],
            }
        cached_icon_paths.cache_clear()
        try:
            payload = build_data()
        except Exception as exc:
            payload = build_route_only_data(exc)
        body = json.dumps(payload, separators=(",", ":")).encode()
        gzip_body = gzip.compress(body, compresslevel=6)
        etag = f'"{hashlib.sha1(body).hexdigest()}"'
        DATA_JSON_CACHE.update({"key": key, "body": body, "gzip": gzip_body, "etag": etag})
        return {"body": body, "gzip": gzip_body, "etag": etag}


def matching_brace_end(text: str, start: int) -> int:
    depth = 0
    for idx in range(start, len(text)):
        char = text[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return idx + 1
    raise ParseError("unterminated braced initializer")


def initializer_brace_span(text: str, name: str) -> tuple[int, int]:
    start = text.find(name)
    if start < 0:
        span = behavior_blob_field_span(text, name)
        if span is None:
            raise ParseError(f"could not find {name}")
        return span
    brace = text.find("{", start)
    if brace < 0:
        raise ParseError(f"could not find initializer for {name}")
    return brace, matching_brace_end(text, brace)


def top_level_braced_spans(text: str, span: tuple[int, int]) -> list[tuple[int, int]]:
    start, end = span
    entries = []
    depth = 0
    entry_start = -1
    for idx in range(start + 1, end - 1):
        char = text[idx]
        if char == "{":
            if depth == 0:
                entry_start = idx
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and entry_start >= 0:
                entries.append((entry_start, idx + 1))
                entry_start = -1
    return entries


def behavior_blob_field_span(text: str, name: str) -> tuple[int, int] | None:
    field_index = BLOB_BEHAVIOR_FIELD_INDEXES.get(name)
    if field_index is None:
        return None
    blob_start = text.find("gOverworldWildBehaviorDataBlob")
    if blob_start < 0:
        return None
    brace = text.find("{", blob_start)
    if brace < 0:
        return None
    field_spans = top_level_braced_spans(text, (brace, matching_brace_end(text, brace)))
    if field_index >= len(field_spans):
        return None
    return field_spans[field_index]


def nested_profile_span(text: str, entry_span: tuple[int, int]) -> tuple[int, int]:
    start, end = entry_span
    depth = 0
    for idx in range(start, end):
        char = text[idx]
        if char == "{":
            if depth == 1:
                return idx, matching_brace_end(text, idx)
            depth += 1
        elif char == "}":
            depth -= 1
    raise ParseError("could not find class override profile initializer")


def line_indent_before(text: str, index: int) -> str:
    line_start = text.rfind("\n", 0, index) + 1
    prefix = text[line_start:index]
    match = re.match(r"[ \t]*", prefix)
    return match.group(0) if match else ""


def format_profile_initializer(raws: dict[str, str], indent: str) -> str:
    value_indent = indent + "    "
    values = ",\n".join(f"{value_indent}{raws[field]}" for field in PROFILE_FIELDS)
    return f"{{\n{values},\n{indent}}}"


def format_mask_expression(mask_fields: set[str], indent: str, word: int = 1) -> str:
    symbols = [
        OVERRIDE_SYMBOL_BY_FIELD[field]
        for field in PROFILE_FIELDS
        if field in mask_fields and OVERRIDE_WORD_BY_FIELD.get(field) == word
    ]
    if not symbols:
        return "0"
    continuation_indent = indent + "    "
    return symbols[0] + "".join(f"\n{continuation_indent}| {symbol}" for symbol in symbols[1:])


def raw_values(profile: dict[str, dict]) -> dict[str, str]:
    return {field: profile[field]["raw"] for field in PROFILE_FIELDS}


def numeric_raw(raw: str, field: str, macros: dict[str, int]) -> int | None:
    return make_value(raw, field, macros)["value"]


def valid_change_options(macros: dict[str, int], class_profiles: list[dict[str, dict]]) -> dict[str, set[str]]:
    return {
        field: {option["raw"] for option in options}
        for field, options in build_edit_options(macros, class_profiles).items()
    }


def parse_save_payload(body: bytes) -> dict[int, dict[str, str]]:
    try:
        payload = json.loads(body.decode())
    except Exception as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    changes = payload.get("changes") if isinstance(payload, dict) else None
    if not isinstance(changes, dict):
        raise ValueError("missing changes object")
    parsed: dict[int, dict[str, str]] = {}
    for raw_index, raw_fields in changes.items():
        try:
            class_index = int(raw_index)
        except Exception as exc:
            raise ValueError(f"invalid class index: {raw_index}") from exc
        if not isinstance(raw_fields, dict):
            raise ValueError(f"class {class_index} changes must be an object")
        parsed[class_index] = {}
        for field, raw in raw_fields.items():
            if field not in PROFILE_FIELDS:
                raise ValueError(f"invalid field: {field}")
            parsed[class_index][field] = clean_token(str(raw))
    return parsed


def parse_profile_membership_payload(body: bytes) -> dict[str, int]:
    try:
        payload = json.loads(body.decode())
    except Exception as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    changes = payload.get("changes") if isinstance(payload, dict) else None
    if not isinstance(changes, dict):
        raise ValueError("missing changes object")
    parsed: dict[str, int] = {}
    for raw_symbol, raw_class_index in changes.items():
        symbol = clean_token(str(raw_symbol)).upper()
        if symbol and not symbol.startswith("SPECIES_"):
            symbol = f"SPECIES_{symbol}"
        try:
            class_index = int(raw_class_index)
        except Exception as exc:
            raise ValueError(f"invalid class index for {symbol}: {raw_class_index}") from exc
        parsed[symbol] = class_index
    return parsed


def parse_profile_management_payload(body: bytes) -> dict:
    try:
        payload = json.loads(body.decode())
    except Exception as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("profile management payload must be an object")
    action = clean_token(str(payload.get("action", ""))).lower()
    if action not in {"create", "rename", "delete"}:
        raise ValueError("profile action must be create, rename, or delete")
    result = {"action": action}
    if action in {"rename", "delete"}:
        try:
            result["classIndex"] = int(payload.get("classIndex"))
        except Exception as exc:
            raise ValueError(f"invalid class index: {payload.get('classIndex')}") from exc
    if action in {"create", "rename"}:
        name = clean_token(str(payload.get("name", "")))
        if not name:
            raise ValueError("profile name is required")
        result["name"] = name
    if action == "create":
        raw_pokemon = payload.get("pokemon", [])
        if isinstance(raw_pokemon, str):
            raw_pokemon = re.split(r"[\n,]+", raw_pokemon)
        if not isinstance(raw_pokemon, list):
            raise ValueError("pokemon must be a list")
        pokemon = []
        for raw_symbol in raw_pokemon:
            symbol = clean_token(str(raw_symbol)).upper()
            if symbol and not symbol.startswith("SPECIES_"):
                symbol = f"SPECIES_{symbol}"
            if symbol:
                pokemon.append(symbol)
        result["pokemon"] = pokemon
    return result


def class_define_entries(raw_source: str) -> list[dict]:
    entries = []
    for match in DEFINE_RE.finditer(raw_source):
        name, args, expr = match.groups()
        if args is not None or not name.startswith(CLASS_PREFIX):
            continue
        try:
            value = int(clean_token(expr), 0)
        except Exception:
            continue
        line_start = raw_source.rfind("\n", 0, match.start()) + 1
        line_end = raw_source.find("\n", match.end())
        if line_end < 0:
            line_end = len(raw_source)
        else:
            line_end += 1
        entries.append(
            {
                "symbol": name,
                "value": value,
                "lineStart": line_start,
                "lineEnd": line_end,
            }
        )
    entries.sort(key=lambda entry: entry["value"])
    return entries


def validate_class_define_entries(entries: list[dict], class_profile_count: int) -> None:
    if len(entries) < class_profile_count:
        raise ParseError("fewer behavior class defines than profile entries")
    values = [entry["value"] for entry in entries[:class_profile_count]]
    if values != list(range(class_profile_count)):
        raise ParseError("behavior class defines must be consecutive from zero")


def replace_class_define_block(raw_source: str, symbols: list[str]) -> str:
    entries = class_define_entries(raw_source)
    if not entries:
        raise ParseError("could not find behavior class defines")
    block_start = entries[0]["lineStart"]
    block_end = entries[-1]["lineEnd"]
    block = "".join(f"#define {symbol} {index}\n" for index, symbol in enumerate(symbols))
    return raw_source[:block_start] + block + raw_source[block_end:]


def replace_define_value(raw_source: str, symbol: str, value: int) -> str:
    pattern = re.compile(rf"(?m)^(\s*#\s*define\s+{re.escape(symbol)}\s+)([0-9]+)(\s*(?://[^\n]*)?)$")
    updated, count = pattern.subn(rf"\g<1>{value}\g<3>", raw_source, count=1)
    if count != 1:
        raise ParseError(f"could not find {symbol}")
    return updated


def behavior_blob_counts(raw_source: str) -> dict[str, int]:
    source = strip_c_comments(join_line_continuations(raw_source))
    counts = {}
    for define, initializer_name in OWBD_COUNT_DEFINES.items():
        entries = parse_initializer(extract_braced_initializer(source, initializer_name))
        counts[define] = len(entries)
    return counts


def rewrite_behavior_blob_count_defines(raw_header: str, counts: dict[str, int]) -> str:
    updated_header = raw_header
    for define, count in counts.items():
        updated_header = replace_define_value(updated_header, define, count)
    return updated_header


def write_behavior_data_source(raw_source: str) -> None:
    counts = behavior_blob_counts(raw_source)
    BEHAVIOR_DATA_SOURCE.write_text(raw_source)
    BEHAVIOR_DATA_HEADER.write_text(rewrite_behavior_blob_count_defines(BEHAVIOR_DATA_HEADER.read_text(), counts))
    invalidate_data_cache()


def sanitize_class_symbol(name: str, existing_symbols: set[str], current_symbol: str | None = None) -> str:
    suffix = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
    if not suffix:
        suffix = "CUSTOM_PROFILE"
    if suffix[0].isdigit():
        suffix = f"PROFILE_{suffix}"
    base = f"{CLASS_PREFIX}{suffix}"
    symbol = base
    counter = 2
    while symbol in existing_symbols and symbol != current_symbol:
        symbol = f"{base}_{counter}"
        counter += 1
    return symbol


def class_symbol_used_by_runtime(symbol: str) -> bool:
    source = OVERLAY_SOURCE.read_text()
    symbol_define = re.compile(rf"^\s*#\s*define\s+{re.escape(symbol)}(?:\s|$)")
    runtime_source = "".join(
        line
        for line in source.splitlines(keepends=True)
        if symbol_define.match(line) is None
    )
    return re.search(rf"\b{re.escape(symbol)}\b", runtime_source) is not None


def append_profile_initializer(raw_behavior_data: str, profile_raws: dict[str, str]) -> str:
    class_array_span = initializer_brace_span(raw_behavior_data, "sOverworldWildBehaviorClassProfiles")
    insert_at = class_array_span[1] - 1
    entry_text = "    " + format_profile_initializer(profile_raws, "    ") + ",\n"
    return raw_behavior_data[:insert_at] + entry_text + raw_behavior_data[insert_at:]


def remove_profile_initializer(raw_behavior_data: str, class_index: int, class_profile_count: int) -> str:
    class_array_span = initializer_brace_span(raw_behavior_data, "sOverworldWildBehaviorClassProfiles")
    class_entry_spans = top_level_braced_spans(raw_behavior_data, class_array_span)
    if len(class_entry_spans) != class_profile_count:
        raise ParseError("class profile entry count changed")
    delete_start, delete_end = braced_entry_removal_span(raw_behavior_data, class_entry_spans[class_index], class_array_span)
    return raw_behavior_data[:delete_start] + raw_behavior_data[delete_end:]


def validate_profile_management_species(symbols: list[str], valid_species: set[str]) -> list[str]:
    if not symbols:
        raise ValueError("choose at least one Pokemon for the new profile")
    result = []
    seen = set()
    for symbol in symbols:
        if symbol not in valid_species:
            raise ValueError(f"invalid Pokemon: {symbol}")
        if symbol not in seen:
            seen.add(symbol)
            result.append(symbol)
    return result


def apply_profile_management_change(body: bytes) -> dict:
    change = parse_profile_management_payload(body)
    raw_behavior_data = BEHAVIOR_DATA_SOURCE.read_text()
    behavior_source = strip_c_comments(join_line_continuations(raw_behavior_data))
    expressions, species_order = parse_define_expressions(DEFINE_SOURCE_FILES)
    macros = evaluate_defines(expressions)
    macros.update(evaluate_armips_equ([ARMIPS_CONFIG, ARMIPS_CONSTANTS]))
    class_profiles = [
        parse_profile(entry, macros)
        for entry in parse_initializer(extract_braced_initializer(behavior_source, "sOverworldWildBehaviorClassProfiles"))
    ]
    class_entries = class_define_entries(raw_behavior_data)
    validate_class_define_entries(class_entries, len(class_profiles))
    class_symbols = [entry["symbol"] for entry in class_entries[: len(class_profiles)]]
    default_class = macros.get("OW_WILD_BEHAVIOR_CLASS_DEFAULT", 0)
    if default_class < 0 or default_class >= len(class_profiles):
        default_class = 0

    action = change["action"]
    if action == "create":
        species = parse_species(expressions, macros, species_order)
        valid_species = {entry["symbol"] for entry in species}
        pokemon = validate_profile_management_species(change.get("pokemon", []), valid_species)
        new_symbol = sanitize_class_symbol(change["name"], set(class_symbols))
        new_index = len(class_profiles)
        updated_source = replace_class_define_block(raw_behavior_data, class_symbols + [new_symbol])
        updated_source = append_profile_initializer(updated_source, raw_values(class_profiles[default_class]))
        write_behavior_data_source(updated_source)
        membership_result = apply_profile_membership_changes(
            json.dumps({"changes": {symbol: new_index for symbol in pokemon}}).encode()
        )
        return {
            "saved": True,
            "message": f"Created {humanize_symbol(new_symbol, CLASS_PREFIX)}",
            "classIndex": new_index,
            "symbol": new_symbol,
            "membership": membership_result,
        }

    class_index = change["classIndex"]
    if class_index < 0 or class_index >= len(class_profiles):
        raise ValueError(f"class index out of range: {class_index}")
    old_symbol = class_symbols[class_index]
    if action == "rename":
        if class_index == default_class:
            raise ValueError("Default profile cannot be renamed")
        new_symbol = sanitize_class_symbol(change["name"], set(class_symbols), old_symbol)
        if new_symbol == old_symbol:
            return {"saved": False, "message": "No code changes needed", "classIndex": class_index, "symbol": old_symbol}
        class_symbols[class_index] = new_symbol
        updated_source = replace_class_define_block(raw_behavior_data, class_symbols)
        updated_source = re.sub(rf"\b{re.escape(old_symbol)}\b", new_symbol, updated_source)
        write_behavior_data_source(updated_source)
        return {"saved": True, "message": f"Renamed profile to {humanize_symbol(new_symbol, CLASS_PREFIX)}", "classIndex": class_index, "symbol": new_symbol}

    if class_index == default_class:
        raise ValueError("Default profile cannot be deleted")
    if class_symbol_used_by_runtime(old_symbol):
        raise ValueError(f"{humanize_symbol(old_symbol, CLASS_PREFIX)} is still referenced by runtime code and cannot be deleted safely")
    class_symbols.pop(class_index)
    updated_source = re.sub(rf"\b{re.escape(old_symbol)}\b", "OW_WILD_BEHAVIOR_CLASS_DEFAULT", raw_behavior_data)
    updated_source = replace_class_define_block(updated_source, class_symbols)
    updated_source = remove_profile_initializer(updated_source, class_index, len(class_profiles))
    write_behavior_data_source(updated_source)
    return {"saved": True, "message": f"Deleted {humanize_symbol(old_symbol, CLASS_PREFIX)}", "classIndex": default_class}


def default_behavior_match_raws() -> dict[str, str]:
    return {
        "species": "OW_WILD_BEHAVIOR_MATCH_ANY_SPECIES",
        "groupMask": "OW_WILD_BEHAVIOR_GROUP_NONE",
        "terrain": "OW_WILD_BEHAVIOR_MATCH_ANY_TERRAIN",
        "minLevel": "OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY",
        "maxLevel": "OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY",
        "shiny": "OW_WILD_BEHAVIOR_MATCH_ANY_SHINY",
        "behaviorClass": "OW_WILD_BEHAVIOR_MATCH_ANY_CLASS",
    }


def parse_profile_override_payload(body: bytes) -> dict[str, list]:
    try:
        payload = json.loads(body.decode())
    except Exception as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    changes = payload.get("changes") if isinstance(payload, dict) else None
    if isinstance(changes, list):
        raw_adds = changes
        raw_removes = []
    elif isinstance(changes, dict):
        raw_adds = changes.get("add", [])
        raw_removes = changes.get("remove", [])
    else:
        raise ValueError("missing changes list")
    if not isinstance(raw_adds, list):
        raise ValueError("override additions must be a list")
    if not isinstance(raw_removes, list):
        raise ValueError("override removals must be a list")

    parsed_adds = []
    for index, raw_change in enumerate(raw_adds, 1):
        if not isinstance(raw_change, dict):
            raise ValueError(f"override {index} must be an object")
        field = clean_token(str(raw_change.get("field", "")))
        raw = clean_token(str(raw_change.get("raw", "")))
        raw_match = raw_change.get("match") if isinstance(raw_change.get("match"), dict) else {}
        match_raws = default_behavior_match_raws()
        for match_field in MATCH_FIELDS:
            if match_field in raw_match:
                match_raws[match_field] = clean_token(str(raw_match[match_field]))
        parsed_adds.append({"field": field, "raw": raw, "match": match_raws})

    parsed_removes = []
    for raw_order in raw_removes:
        try:
            order = int(raw_order)
        except Exception as exc:
            raise ValueError(f"invalid override removal order: {raw_order}") from exc
        parsed_removes.append(order)
    return {"add": parsed_adds, "remove": parsed_removes}


def simple_species_class_rule(rule: dict, macros: dict[str, int]) -> str | None:
    match = rule["match"]
    species = match["species"].get("symbol")
    if not species or not species.startswith("SPECIES_") or species == "SPECIES_NONE":
        return None
    if numeric(match["species"]) == macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_SPECIES", macros.get("SPECIES_NONE", 0)):
        return None
    checks = [
        ("groupMask", macros.get("OW_WILD_BEHAVIOR_GROUP_NONE", 0)),
        ("terrain", macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_TERRAIN", 0)),
        ("minLevel", macros.get("OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY", 0)),
        ("maxLevel", macros.get("OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY", 0)),
        ("shiny", macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_SHINY", 0)),
        ("behaviorClass", macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_CLASS", 0)),
    ]
    for field, expected in checks:
        if numeric(match[field]) != expected:
            return None
    return species


def format_behavior_class_rule(species_symbol: str, class_symbol: str, indent: str = "    ") -> str:
    inner = indent + "    "
    value = inner + "    "
    return (
        f"{indent}{{\n"
        f"{inner}{{\n"
        f"{value}OW_WILD_BEHAVIOR_GROUP_NONE,\n"
        f"{value}{species_symbol},\n"
        f"{value}OW_WILD_BEHAVIOR_MATCH_ANY_TERRAIN,\n"
        f"{value}OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY,\n"
        f"{value}OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY,\n"
        f"{value}OW_WILD_BEHAVIOR_MATCH_ANY_SHINY,\n"
        f"{value}OW_WILD_BEHAVIOR_MATCH_ANY_CLASS,\n"
        f"{inner}}},\n"
        f"{inner}{class_symbol},\n"
        f"{indent}}}"
    )


def format_behavior_species_class_rule(species_symbol: str, class_symbol: str, indent: str = "    ") -> str:
    return f"{indent}{{{species_symbol}, {class_symbol}}}"


def format_match_initializer(raws: dict[str, str], indent: str) -> str:
    value_indent = indent + "    "
    values = ",\n".join(f"{value_indent}{raws[field]}" for field in MATCH_FIELDS)
    return f"{{\n{values},\n{indent}}}"


def format_behavior_override_rule(
    match_raws: dict[str, str],
    mask_fields: set[str],
    profile_raws: dict[str, str],
    indent: str = "    ",
) -> str:
    inner = indent + "    "
    return (
        f"{indent}{{\n"
        f"{inner}{format_match_initializer(match_raws, inner)},\n"
        f"{inner}{format_mask_expression(mask_fields, inner, 1)},\n"
        f"{inner}{format_mask_expression(mask_fields, inner, 2)},\n"
        f"{inner}{format_mask_expression(mask_fields, inner, 3)},\n"
        f"{inner}{format_profile_initializer(profile_raws, inner)},\n"
        f"{indent}}}"
    )


def braced_entry_removal_span(text: str, entry_span: tuple[int, int], container_span: tuple[int, int]) -> tuple[int, int]:
    start, end = entry_span
    delete_end = end
    container_end = container_span[1] - 1
    while delete_end < container_end and text[delete_end] in " \t":
        delete_end += 1
    if delete_end < container_end and text[delete_end] == ",":
        delete_end += 1
    if delete_end < len(text) and text[delete_end] == "\r":
        delete_end += 1
    if delete_end < len(text) and text[delete_end] == "\n":
        delete_end += 1
    return start, delete_end


def apply_profile_changes(body: bytes) -> dict:
    raw_behavior_data = BEHAVIOR_DATA_SOURCE.read_text()
    behavior_source = strip_c_comments(join_line_continuations(raw_behavior_data))
    expressions, _ = parse_define_expressions([SPECIES_HEADER, BEHAVIOR_DATA_HEADER, OVERLAY_SOURCE, BEHAVIOR_DATA_SOURCE])
    macros = evaluate_defines(expressions)
    _, destination_values = parse_behavior_data_enums()
    macros.update(destination_values)

    class_profiles = [
        parse_profile(entry, macros)
        for entry in parse_initializer(extract_braced_initializer(behavior_source, "sOverworldWildBehaviorClassProfiles"))
    ]
    changes = parse_save_payload(body)
    if not changes:
        return {"saved": False, "message": "No changes"}

    valid_options = valid_change_options(macros, class_profiles)
    for class_index, field_changes in changes.items():
        if class_index < 0 or class_index >= len(class_profiles):
            raise ValueError(f"class index out of range: {class_index}")
        for field, raw in field_changes.items():
            if raw not in valid_options[field]:
                raise ValueError(f"invalid value for {field}: {raw}")

    replacements: list[tuple[int, int, str]] = []
    class_array_span = initializer_brace_span(raw_behavior_data, "sOverworldWildBehaviorClassProfiles")
    class_entry_spans = top_level_braced_spans(raw_behavior_data, class_array_span)
    if len(class_entry_spans) != len(class_profiles):
        raise ParseError("class profile entry count changed")

    for class_index, field_changes in changes.items():
        profile_raws = raw_values(class_profiles[class_index])
        profile_raws.update(field_changes)
        entry_span = class_entry_spans[class_index]
        profile_indent = line_indent_before(raw_behavior_data, entry_span[0])
        replacements.append((entry_span[0], entry_span[1], format_profile_initializer(profile_raws, profile_indent)))

    updated_source = raw_behavior_data
    changed = False
    for start, end, replacement in sorted(replacements, key=lambda item: item[0], reverse=True):
        if updated_source[start:end] != replacement:
            changed = True
            updated_source = updated_source[:start] + replacement + updated_source[end:]
    if changed:
        write_behavior_data_source(updated_source)
    return {"saved": changed, "message": "Saved" if changed else "No code changes needed"}


def apply_profile_membership_changes(body: bytes) -> dict:
    changes = parse_profile_membership_payload(body)
    if not changes:
        return {"saved": False, "message": "No changes"}

    raw_overlay = OVERLAY_SOURCE.read_text()
    source = strip_c_comments(join_line_continuations(raw_overlay))
    raw_behavior_data = BEHAVIOR_DATA_SOURCE.read_text()
    behavior_source = strip_c_comments(join_line_continuations(raw_behavior_data))
    expressions, species_order = parse_define_expressions(DEFINE_SOURCE_FILES)
    macros = evaluate_defines(expressions)
    macros.update(evaluate_armips_equ([ARMIPS_CONFIG, ARMIPS_CONSTANTS]))
    _, destination_values = parse_behavior_data_enums()
    macros.update(destination_values)
    species = parse_species(expressions, macros, species_order)
    apply_species_type_metadata(species, parse_species_type_metadata(macros))
    valid_species = {entry["symbol"] for entry in species}
    species_by_symbol = {entry["symbol"]: entry for entry in species}
    class_labels = invert_labels(macros, CLASS_PREFIX)
    group_labels = invert_labels(macros, GROUP_PREFIX)
    class_profiles = [
        parse_profile(entry, macros)
        for entry in parse_initializer(extract_braced_initializer(behavior_source, "sOverworldWildBehaviorClassProfiles"))
    ]
    full_class_rules = parse_full_class_rules(behavior_source, macros, group_labels, class_labels)
    species_class_rules = parse_species_class_rules(behavior_source, macros, group_labels, class_labels, len(full_class_rules))
    class_rules = full_class_rules + species_class_rules
    group_species = parse_group_species(source, macros)
    default_terrain = macros.get("OW_WILD_SPAWN_TERRAIN_LAND", 0)

    for symbol, class_index in changes.items():
        if symbol not in valid_species:
            raise ValueError(f"invalid Pokemon: {symbol}")
        if class_index < 0 or class_index >= len(class_profiles):
            raise ValueError(f"class index out of range: {class_index}")

    class_rule_span = initializer_brace_span(raw_behavior_data, "sOverworldWildBehaviorClassRules")
    class_rule_entry_spans = top_level_braced_spans(raw_behavior_data, class_rule_span)
    if len(class_rule_entry_spans) != len(full_class_rules):
        raise ParseError("class rule entry count changed")
    species_rule_span = initializer_brace_span(raw_behavior_data, "sOverworldWildBehaviorSpeciesClassRules")
    species_rule_entry_spans = top_level_braced_spans(raw_behavior_data, species_rule_span)
    if len(species_rule_entry_spans) != len(species_class_rules):
        raise ParseError("compact species class rule entry count changed")

    direct_rule_by_species: dict[str, tuple[str, tuple[int, int]]] = {}
    for index, rule in enumerate(full_class_rules):
        symbol = simple_species_class_rule(rule, macros)
        if symbol:
            direct_rule_by_species[symbol] = ("full", class_rule_entry_spans[index])
    for index, rule in enumerate(species_class_rules):
        symbol = simple_species_class_rule(rule, macros)
        if symbol:
            direct_rule_by_species[symbol] = ("species", species_rule_entry_spans[index])

    replacements: list[tuple[int, int, str]] = []
    appended_rules: list[str] = []
    for symbol, class_index in changes.items():
        entry = species_by_symbol[symbol]
        context = {
            "species": entry["value"],
            "symbol": symbol,
            "level": 1,
            "terrain": default_terrain,
            "shiny": 0,
            "groupFlags": group_flags_for_species(symbol, group_species, species_by_symbol, macros),
            "behaviorClass": macros.get("OW_WILD_BEHAVIOR_CLASS_DEFAULT", 0),
        }
        current_class, _ = class_for_context(context, class_rules, len(class_profiles), macros)
        if current_class == class_index:
            continue
        class_symbol = class_labels.get(class_index, {"symbol": str(class_index)})["symbol"]
        if symbol in direct_rule_by_species:
            storage, span = direct_rule_by_species[symbol]
            replacement = (
                format_behavior_species_class_rule(symbol, class_symbol)
                if storage == "species"
                else format_behavior_class_rule(symbol, class_symbol)
            )
            replacements.append((span[0], span[1], replacement))
        else:
            appended_rules.append(format_behavior_species_class_rule(symbol, class_symbol))

    if appended_rules:
        insert_at = species_rule_span[1] - 1
        replacements.append((insert_at, insert_at, "".join(f"{rule},\n" for rule in appended_rules)))

    updated_source = raw_behavior_data
    changed = False
    for start, end, replacement in sorted(replacements, key=lambda item: item[0], reverse=True):
        if updated_source[start:end] != replacement:
            changed = True
            updated_source = updated_source[:start] + replacement + updated_source[end:]
    if changed:
        write_behavior_data_source(updated_source)
    return {"saved": changed, "message": "Saved" if changed else "No code changes needed"}


def apply_profile_override_changes(body: bytes) -> dict:
    changes = parse_profile_override_payload(body)
    additions = changes["add"]
    removals = changes["remove"]
    if not additions and not removals:
        return {"saved": False, "message": "No changes"}

    raw_behavior_data = BEHAVIOR_DATA_SOURCE.read_text()
    behavior_source = strip_c_comments(join_line_continuations(raw_behavior_data))
    expressions, _ = parse_define_expressions(DEFINE_SOURCE_FILES)
    macros = evaluate_defines(expressions)
    macros.update(evaluate_armips_equ([ARMIPS_CONFIG, ARMIPS_CONSTANTS]))
    terrain_values, destination_values = parse_behavior_data_enums()
    macros.update(terrain_values)
    macros.update(destination_values)

    class_profiles = [
        parse_profile(entry, macros)
        for entry in parse_initializer(extract_braced_initializer(behavior_source, "sOverworldWildBehaviorClassProfiles"))
    ]
    valid_options = valid_change_options(macros, class_profiles)
    formatted_rules = []
    for index, change in enumerate(additions, 1):
        field = change["field"]
        raw = change["raw"]
        if field not in PROFILE_FIELDS:
            raise ValueError(f"invalid override field: {field}")
        if field not in OVERRIDE_SYMBOL_BY_FIELD:
            raise ValueError(f"field cannot be used in specific overrides: {field}")
        if raw not in valid_options[field]:
            raise ValueError(f"invalid value for {field}: {raw}")

        match_values = [change["match"][match_field] for match_field in MATCH_FIELDS]
        parsed_match = parse_match(match_values, macros)
        unresolved = [field_name for field_name, value in parsed_match.items() if numeric(value) is None]
        if unresolved:
            raise ValueError(f"override {index} has invalid match value for {', '.join(unresolved)}")
        min_level = numeric(parsed_match["minLevel"])
        max_level = numeric(parsed_match["maxLevel"])
        any_level = macros.get("OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY", 0)
        if min_level != any_level and max_level != any_level and min_level is not None and max_level is not None and min_level > max_level:
            raise ValueError(f"override {index} minimum level cannot be greater than maximum level")

        profile_raws = {profile_field: "0" for profile_field in PROFILE_FIELDS}
        profile_raws[field] = raw
        formatted_rules.append(
            format_behavior_override_rule(change["match"], {field}, profile_raws)
        )

    override_span = initializer_brace_span(raw_behavior_data, "sOverworldWildBehaviorOverrides")
    override_entry_spans = top_level_braced_spans(raw_behavior_data, override_span)
    if removals:
        for order in removals:
            if order < 1 or order > len(override_entry_spans):
                raise ValueError(f"override order out of range: {order}")

    replacements: list[tuple[int, int, str]] = []
    for order in sorted(set(removals), reverse=True):
        start, end = braced_entry_removal_span(raw_behavior_data, override_entry_spans[order - 1], override_span)
        replacements.append((start, end, ""))
    if formatted_rules:
        insert_at = override_span[1] - 1
        replacements.append((insert_at, insert_at, "".join(f"{rule},\n" for rule in formatted_rules)))

    updated_source = raw_behavior_data
    changed = False
    for start, end, replacement in sorted(replacements, key=lambda item: item[0], reverse=True):
        if updated_source[start:end] != replacement:
            changed = True
            updated_source = updated_source[:start] + replacement + updated_source[end:]
    if changed:
        write_behavior_data_source(updated_source)
    total_changes = len(formatted_rules) + len(set(removals))
    label = "override change" if total_changes == 1 else "override changes"
    return {"saved": changed, "message": f"Saved {total_changes} {label}" if changed else "No code changes needed"}


def build_command_args() -> list[str]:
    if sys.platform == "win32":
        return ["cmd.exe", "/c", BUILD_COMMAND]
    root = shlex.quote(str(ROOT))
    return [
        "/bin/sh",
        "-lc",
        "docker run --rm "
        f"--mount type=bind,source={root},destination=/hg-engine "
        "--mount type=volume,source=hg-engine-venv,destination=/tmp/hg-engine-venv "
        "--mount type=volume,source=hg-engine-pip-cache,destination=/tmp/pip-cache "
        "-e PIP_CACHE_DIR=/tmp/pip-cache "
        "hg-engine /bin/bash -lc 'cd /hg-engine && make -j$(nproc) VENV=/tmp/hg-engine-venv'; "
        'build_status=$?; '
        'if [ "$build_status" -eq 0 ]; then ./scripts/copy-test-nds-to-delta.sh || exit $?; fi; '
        'exit "$build_status"',
    ]


ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def latest_terminal_line(output: str) -> str:
    clean = ANSI_ESCAPE_RE.sub("", output).replace("\r", "\n")
    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def elapsed_label(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def update_build_state(**changes) -> None:
    with BUILD_STATE_LOCK:
        BUILD_STATE.update(changes)


def append_build_output(text: str) -> None:
    if not text:
        return
    with BUILD_STATE_LOCK:
        output = (BUILD_STATE.get("output") or "") + text
        output = output[-BUILD_OUTPUT_LIMIT:]
        BUILD_STATE["output"] = output
        BUILD_STATE["latestLine"] = latest_terminal_line(output)


def build_status_payload() -> dict:
    with BUILD_STATE_LOCK:
        payload = dict(BUILD_STATE)
    started_at = payload.get("startedAt")
    ended_at = payload.get("endedAt")
    if started_at is None:
        elapsed = 0.0
    else:
        elapsed = (ended_at or time.time()) - started_at
    payload["elapsed"] = elapsed
    payload["elapsedLabel"] = elapsed_label(elapsed)
    payload["testNdsExists"] = TEST_NDS.exists()
    payload["testNdsPath"] = str(TEST_NDS)
    return payload


def terminate_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            process.terminate()
        else:
            os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            if sys.platform == "win32":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=3)


def run_command_with_pty(command: list[str], on_output=None, startup_timeout: int | None = None) -> tuple[int, str]:
    master_fd, slave_fd = pty.openpty()
    output = bytearray()
    started_at = time.time()
    saw_output = False
    timed_out = False

    def capture_chunk(chunk: bytes) -> None:
        output.extend(chunk)
        if len(output) > BUILD_OUTPUT_LIMIT * 2:
            del output[: len(output) - BUILD_OUTPUT_LIMIT]
        if on_output:
            on_output(chunk.decode(errors="replace"))

    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
        start_new_session=sys.platform != "win32",
    )
    os.close(slave_fd)
    try:
        while True:
            ready, _, _ = select.select([master_fd], [], [], 0.2)
            if master_fd in ready:
                try:
                    chunk = os.read(master_fd, 4096)
                except OSError:
                    chunk = b""
                if chunk:
                    saw_output = True
                    capture_chunk(chunk)
            if (
                startup_timeout is not None
                and not saw_output
                and process.poll() is None
                and time.time() - started_at >= startup_timeout
            ):
                timed_out = True
                capture_chunk(
                    (
                        f"\nBuild failed: Docker produced no terminal output for "
                        f"{startup_timeout}s. Docker Desktop may be stuck before starting the container.\n"
                    ).encode()
                )
                terminate_process_tree(process)
            if process.poll() is not None:
                while True:
                    try:
                        chunk = os.read(master_fd, 4096)
                    except OSError:
                        break
                    if not chunk:
                        break
                    capture_chunk(chunk)
                break
    finally:
        os.close(master_fd)
    text = output.decode(errors="replace")
    code = BUILD_STARTUP_TIMEOUT_CODE if timed_out else process.returncode
    return code or 0, text[-BUILD_OUTPUT_LIMIT:]


def open_test_nds() -> dict:
    if not TEST_NDS.exists():
        raise FileNotFoundError("test.nds does not exist yet")
    if sys.platform == "darwin":
        command = ["open", str(TEST_NDS)]
    else:
        command = ["xdg-open", str(TEST_NDS)]
    subprocess.run(command, cwd=ROOT, check=True)
    return {"opened": True, "path": str(TEST_NDS)}


def crc16_ccitt_false(data: bytes | bytearray | memoryview) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def shiny_counter_slot_footer(save_bytes: bytes | bytearray, copy_base: int) -> dict:
    footer_offset = copy_base + SAVE_NORMAL_SLOT_SIZE - SAVE_CHUNK_FOOTER_SIZE
    if footer_offset < 0 or footer_offset + SAVE_CHUNK_FOOTER_SIZE > len(save_bytes):
        return {
            "copyBase": copy_base,
            "valid": False,
            "error": "save copy is outside the raw save image",
        }
    count, size, magic, slot, crc = struct.unpack_from("<IIIHH", save_bytes, footer_offset)
    crc_data = save_bytes[copy_base:footer_offset]
    expected_crc = crc16_ccitt_false(crc_data)
    valid = (
        size == SAVE_NORMAL_SLOT_SIZE
        and magic == SAVE_CHUNK_MAGIC
        and slot == 0
        and crc == expected_crc
    )
    return {
        "copyBase": copy_base,
        "valid": valid,
        "count": count,
        "size": size,
        "magic": magic,
        "slot": slot,
        "crc": crc,
        "expectedCrc": expected_crc,
    }


def load_test_dsv_bytes() -> tuple[Path, bytes, bytes]:
    path = TEST_DSV
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist")
    data = path.read_bytes()
    if len(data) < DSV_RAW_SAVE_SIZE:
        raise ValueError(f"{path} is too small to be a raw DS save")
    return path, data[:DSV_RAW_SAVE_SIZE], data[DSV_RAW_SAVE_SIZE:]


def choose_active_shiny_counter_copy(save_bytes: bytes | bytearray) -> dict:
    copies = [shiny_counter_slot_footer(save_bytes, base) for base in SAVE_COPY_BASES]
    valid_copies = [copy for copy in copies if copy.get("valid")]
    if not valid_copies:
        raise ValueError("could not find a valid normal save slot in test.dsv")
    active = max(valid_copies, key=lambda copy: copy.get("count", 0))
    return {"active": active, "copies": copies}


def shiny_counter_payload() -> dict:
    if not TEST_DSV.exists():
        return {
            "exists": False,
            "path": str(TEST_DSV),
            "counter": 0,
            "denominator": OVERWORLD_WILD_SHINY_BASE_ODDS,
            "magicOk": False,
        }
    path, save_bytes, extra_bytes = load_test_dsv_bytes()
    del extra_bytes
    selected = choose_active_shiny_counter_copy(save_bytes)
    active = selected["active"]
    base = active["copyBase"]
    counter_offset = base + OVERWORLD_WILD_SHINY_COUNTER_SAVE_OFFSET
    magic_offset = base + OVERWORLD_WILD_SHINY_MAGIC_SAVE_OFFSET
    raw_counter = struct.unpack_from("<H", save_bytes, counter_offset)[0]
    magic = struct.unpack_from("<H", save_bytes, magic_offset)[0]
    magic_ok = magic == OVERWORLD_WILD_SHINY_COUNTER_MAGIC
    counter = raw_counter if magic_ok else 0
    counter = min(counter, OVERWORLD_WILD_SHINY_COUNTER_MAX)
    return {
        "exists": True,
        "path": str(path),
        "counter": counter,
        "rawCounter": raw_counter,
        "magic": magic,
        "magicOk": magic_ok,
        "denominator": OVERWORLD_WILD_SHINY_BASE_ODDS - counter,
        "activeCopyBase": base,
        "activeSaveCount": active.get("count"),
        "copies": selected["copies"],
    }


def set_shiny_counter(counter: int) -> dict:
    if not isinstance(counter, int):
        raise ValueError("counter must be an integer")
    if counter < 0 or counter > OVERWORLD_WILD_SHINY_COUNTER_MAX:
        raise ValueError(f"counter must be between 0 and {OVERWORLD_WILD_SHINY_COUNTER_MAX}")
    path, save_bytes, extra_bytes = load_test_dsv_bytes()
    raw = bytearray(save_bytes)
    selected = choose_active_shiny_counter_copy(raw)
    active = selected["active"]
    base = active["copyBase"]
    counter_offset = base + OVERWORLD_WILD_SHINY_COUNTER_SAVE_OFFSET
    magic_offset = base + OVERWORLD_WILD_SHINY_MAGIC_SAVE_OFFSET
    struct.pack_into("<H", raw, counter_offset, counter)
    struct.pack_into("<H", raw, magic_offset, OVERWORLD_WILD_SHINY_COUNTER_MAGIC)

    footer_offset = base + SAVE_NORMAL_SLOT_SIZE - SAVE_CHUNK_FOOTER_SIZE
    crc = crc16_ccitt_false(raw[base:footer_offset])
    struct.pack_into("<H", raw, footer_offset + 0xE, crc)
    path.write_bytes(bytes(raw) + extra_bytes)
    return {
        **shiny_counter_payload(),
        "message": f"Shiny counter set to {counter}",
    }


def run_build(open_after: bool = False) -> dict:
    if not BUILD_LOCK.acquire(blocking=False):
        raise RuntimeError("Build already running")
    try:
        code, output = run_command_with_pty(build_command_args(), startup_timeout=BUILD_STARTUP_TIMEOUT_SECONDS)
        result = {
            "ok": code == 0,
            "code": code,
            "command": BUILD_COMMAND,
            "output": output,
            "testNdsExists": TEST_NDS.exists(),
            "testNdsPath": str(TEST_NDS),
        }
        if code == 0 and open_after:
            result["open"] = open_test_nds()
        return result
    finally:
        BUILD_LOCK.release()


def run_build_job(open_after: bool) -> None:
    try:
        code, output = run_command_with_pty(
            build_command_args(),
            append_build_output,
            startup_timeout=BUILD_STARTUP_TIMEOUT_SECONDS,
        )
        open_result = None
        open_error = None
        if code == 0 and open_after:
            append_build_output("\nOpening test.nds...\n")
            try:
                open_result = open_test_nds()
                append_build_output("Opened test.nds.\n")
            except Exception as exc:  # pragma: no cover - surfaced in browser during local use
                open_error = str(exc)
                append_build_output(f"Open failed: {open_error}\n")
        with BUILD_STATE_LOCK:
            final_output = BUILD_STATE.get("output") or output
        update_build_state(
            running=False,
            endedAt=time.time(),
            ok=code == 0,
            code=code,
            output=final_output,
            latestLine=latest_terminal_line(final_output),
            open=open_result,
            openError=open_error,
            testNdsExists=TEST_NDS.exists(),
            testNdsPath=str(TEST_NDS),
        )
    except Exception as exc:  # pragma: no cover - surfaced in browser during local use
        append_build_output(f"\nBuild failed: {exc}\n")
        update_build_state(
            running=False,
            endedAt=time.time(),
            ok=False,
            code=None,
            error=str(exc),
            testNdsExists=TEST_NDS.exists(),
            testNdsPath=str(TEST_NDS),
        )
    finally:
        BUILD_LOCK.release()


def start_build_job(open_after: bool = False) -> dict:
    if not BUILD_LOCK.acquire(blocking=False):
        raise RuntimeError("Build already running")
    update_build_state(
        running=True,
        startedAt=time.time(),
        endedAt=None,
        command=BUILD_COMMAND,
        output=f"Starting Docker build via {BUILD_COMMAND}...\n",
        latestLine="Starting Docker build...",
        ok=None,
        code=None,
        error=None,
        open=None,
        openError=None,
        testNdsExists=TEST_NDS.exists(),
        testNdsPath=str(TEST_NDS),
    )
    thread = threading.Thread(target=run_build_job, args=(open_after,), daemon=True)
    thread.start()
    return build_status_payload()


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Overworld Behaviour Profiles</title>
  <style>
    :root {
      --bg: #f3f5f7;
      --surface: #ffffff;
      --surface-2: #f8fafc;
      --ink: #151b23;
      --muted: #64748b;
      --line: #d8dee8;
      --accent: #0f766e;
      --accent-soft: #dff4ef;
      --warn: #9a3412;
      --focus: #2563eb;
      --shadow: 0 12px 30px rgb(15 23 42 / 9%);
      --time-morning-ink: #c2410c;
      --time-morning-bg: #fff7ed;
      --time-morning-border: #fed7aa;
      --time-morning-accent: #f97316;
      --time-day-ink: #ca8a04;
      --time-day-bg: #fefce8;
      --time-day-border: #fde68a;
      --time-day-accent: #eab308;
      --time-night-ink: #4338ca;
      --time-night-bg: #eef2ff;
      --time-night-border: #c7d2fe;
      --time-night-accent: #6366f1;
    }

    * { box-sizing: border-box; }

    [hidden] { display: none !important; }

    body {
      margin: 0;
      width: 100%;
      background: var(--bg);
      color: var(--ink);
      font: 13px/1.42 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      overflow: hidden;
    }

    button, input, select {
      font: inherit;
    }

    select {
      -webkit-appearance: none;
      appearance: none;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%2364758b' d='M3 4.5h6L6 8z'/%3E%3C/svg%3E");
      background-position: right 8px center;
      background-repeat: no-repeat;
      background-size: 12px 12px;
    }

    html,
    body {
      height: 100%;
    }

    .app {
      height: 100vh;
      height: 100dvh;
      width: 100%;
      max-width: 100vw;
      min-height: 0;
      min-width: 0;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      overflow: hidden;
    }

    header {
      background: var(--surface);
      border-bottom: 1px solid var(--line);
      padding: 12px 16px;
      position: sticky;
      top: 0;
      z-index: 5;
      width: 100%;
      max-width: 100vw;
      min-width: 0;
      overflow: hidden;
    }

    .bar {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      width: 100%;
      min-width: 0;
    }

    .primary-bar {
      margin-bottom: 8px;
    }

    .header-controls {
      gap: 8px;
    }

    .title {
      font-size: 16px;
      font-weight: 700;
      margin-right: 10px;
      white-space: nowrap;
    }

    .workspace-tabs {
      display: inline-flex;
      flex: 1 1 360px;
      flex-wrap: wrap;
      gap: 4px;
      padding: 3px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface-2);
      min-width: 0;
      max-width: 100%;
    }

    .workspace-tab {
      height: 28px;
      border: 0;
      border-radius: 6px;
      background: transparent;
      color: var(--muted);
      cursor: pointer;
      font-weight: 750;
      padding: 0 10px;
      white-space: nowrap;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .workspace-tab.active {
      background: #fff;
      color: var(--ink);
      box-shadow: inset 0 0 0 1px var(--line);
    }

    .source {
      color: var(--muted);
      margin-right: auto;
      white-space: nowrap;
      min-width: 0;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .control {
      height: 32px;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--ink);
      border-radius: 6px;
      padding: 0 9px;
      min-width: 0;
    }

    input.control { width: min(360px, 48vw); }
    select.control {
      width: 180px;
      padding-right: 26px;
      background-color: #fff;
    }

    button.control {
      cursor: pointer;
      font-weight: 650;
    }

    button.control:hover,
    .row:hover,
    .profile-row:hover {
      border-color: #b6c2d2;
      background: #fbfdff;
    }

    main.view {
      display: grid;
      grid-template-columns: minmax(260px, 34%) minmax(520px, 1fr);
      gap: 12px;
      padding: 12px;
      min-height: 0;
      min-width: 0;
      width: 100%;
      max-width: 100vw;
      overflow: hidden;
    }

    .view {
      display: none !important;
    }

    .view.active {
      display: grid !important;
    }

    #encountersView {
      grid-template-rows: minmax(0, 1fr);
    }

    .pane {
      min-height: 0;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
      display: flex;
      flex-direction: column;
      min-width: 0;
    }

    .pane-head {
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      background: var(--surface-2);
    }

    .pane-title {
      font-weight: 700;
    }

    .route-pane-head {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr) auto;
      align-items: center;
      gap: 8px;
      padding: 7px 10px;
      min-height: 44px;
    }

    .route-pane-head .pane-title,
    .route-pane-head .count {
      white-space: nowrap;
    }

    .count {
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }

    .scroll {
      overflow: auto;
      min-height: 0;
      overscroll-behavior: contain;
      -webkit-overflow-scrolling: touch;
    }

    .profiles {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 10px;
      padding: 10px;
    }

    .card {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      overflow: hidden;
      contain: layout paint;
    }

    .card-head {
      padding: 9px 10px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      flex-wrap: wrap;
      min-height: 50px;
    }

    .card-title {
      font-weight: 750;
      flex: 1 1 180px;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .profile-icons {
      display: flex;
      align-items: flex-start;
      justify-content: flex-start;
      gap: 4px;
      flex: 1 1 100%;
      max-width: 100%;
      overflow: visible;
      flex-wrap: wrap;
      padding: 2px 0 0;
    }

    .profile-icon-button {
      width: 30px;
      height: 30px;
      border: 0;
      border-radius: 4px;
      background: transparent;
      padding: 0;
      cursor: pointer;
      flex: 0 0 auto;
    }

    .profile-icon-button:hover,
    .profile-icon-button:focus-visible {
      background: var(--accent-soft);
      outline: 1px solid #99d6ca;
    }

    .profile-icon-button.active {
      background: #d4f0e8;
      box-shadow: inset 0 0 0 1px var(--accent);
    }

    .profile-row-add-button {
      width: 30px;
      height: 30px;
      flex: 0 0 auto;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid #bde2d9;
      border-radius: 7px;
      background: #f0fbf8;
      color: var(--accent-strong);
      cursor: pointer;
    }

    .profile-row-add-button:hover,
    .profile-row-add-button:focus-visible {
      background: #dff5ef;
      outline: 1px solid #99d6ca;
    }

    .profile-row-add-button svg {
      width: 15px;
      height: 15px;
      stroke: currentColor;
    }

    .profile-add-menu {
      position: fixed;
      z-index: 80;
      width: min(320px, calc(100vw - 16px));
      border: 1px solid #cbd7e6;
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 16px 40px rgba(15, 23, 42, .16);
      padding: 8px;
    }

    .profile-add-menu[hidden] {
      display: none;
    }

    .profile-add-menu-form {
      display: grid;
      gap: 7px;
    }

    .profile-add-menu-title {
      min-width: 0;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      color: var(--ink);
      font-size: 12px;
      font-weight: 850;
    }

    .profile-add-menu-title span {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .profile-add-menu-actions {
      display: flex;
      justify-content: flex-end;
      gap: 6px;
    }

    .profile-add-menu-actions .control {
      min-height: 30px;
      height: 30px;
    }

    .profile-combo-menu {
      position: fixed;
      z-index: 90;
      width: min(340px, calc(100vw - 16px));
      max-height: min(300px, calc(100vh - 18px));
      overflow: auto;
      padding: 4px;
      border: 1px solid #cbd7e6;
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 16px 40px rgba(15, 23, 42, .16);
    }

    .profile-combo-menu[hidden] {
      display: none;
    }

    .profile-combo-option {
      width: 100%;
      min-height: 32px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      border: 0;
      border-radius: 6px;
      background: transparent;
      color: var(--ink);
      padding: 5px 7px;
      text-align: left;
      cursor: pointer;
    }

    .profile-combo-option:hover,
    .profile-combo-option:focus-visible,
    .profile-combo-option.active {
      background: #edf7f4;
      outline: none;
    }

    .profile-combo-option-main {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-weight: 850;
    }

    .profile-combo-option-value {
      flex: 0 0 auto;
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      font-variant-numeric: tabular-nums;
    }

    .profile-icon {
      width: 100%;
      height: 100%;
      image-rendering: pixelated;
      object-fit: contain;
      display: block;
    }

    .profile-row {
      width: 100%;
      border: 0;
      border-bottom: 1px solid var(--line);
      background: #fff;
      color: inherit;
      display: grid;
      grid-template-columns: 30px minmax(150px, .9fr) auto minmax(0, 1.5fr);
      gap: 8px;
      align-items: start;
      min-height: 48px;
      padding: 8px 10px;
      text-align: left;
      cursor: pointer;
      contain: layout paint;
      overflow-anchor: none;
    }

    .profile-row.active {
      background: #edf7f4;
      box-shadow: inset 3px 0 0 var(--accent);
    }

    .profile-row.changed {
      background: #fff8e6;
    }

    .profile-row:focus-visible {
      outline: 2px solid #99d6ca;
      outline-offset: -2px;
    }

    .profile-row > .route-encounter-badge {
      width: 28px;
      height: 28px;
      border-radius: 7px;
    }

    .profile-row-main {
      min-width: 0;
      display: grid;
      gap: 2px;
    }

    .profile-row-title {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-weight: 800;
    }

    .profile-row-sub {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }

    .profile-row-count {
      justify-self: end;
      min-height: 24px;
      display: inline-flex;
      align-items: center;
      padding: 1px 8px;
      border: 1px solid #dbe5f0;
      border-radius: 999px;
      background: #f8fafc;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      white-space: nowrap;
      font-variant-numeric: tabular-nums;
    }

    .profile-row-icons,
    .profile-member-strip,
    .profile-detail-overview {
      min-width: 0;
      display: flex;
      align-items: center;
      justify-content: flex-start;
      flex-wrap: wrap;
      gap: 3px;
    }

    .profile-row-icons {
      overflow: hidden;
      max-height: 64px;
      padding-top: 1px;
    }

    .profile-more {
      min-width: 28px;
      height: 22px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0 6px;
      border: 1px solid #dbe5f0;
      border-radius: 6px;
      background: #fff;
      color: var(--muted);
      font-size: 11px;
      font-weight: 850;
      font-variant-numeric: tabular-nums;
    }

    .profile-detail-head {
      width: 100%;
      min-width: 0;
      display: grid;
      gap: 8px;
    }

    .profile-detail-top {
      min-width: 0;
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 10px;
    }

    .profile-detail-title {
      min-width: 0;
      display: grid;
      grid-template-columns: 36px minmax(0, 1fr);
      gap: 8px;
      align-items: center;
    }

    .profile-detail-title .route-encounter-badge {
      width: 34px;
      height: 34px;
      border-radius: 8px;
    }

    .profile-detail-title .route-encounter-badge svg {
      width: 21px;
      height: 21px;
    }

    .profile-detail-title h2 {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .profile-detail-tools {
      flex: 0 0 auto;
      display: flex;
      align-items: center;
      justify-content: flex-end;
      flex-wrap: wrap;
      gap: 6px;
    }

    .profile-management-actions {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }

    .profile-management-button {
      width: 28px;
      height: 28px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 0;
      border-radius: 6px;
      background: transparent;
      color: var(--muted);
      cursor: pointer;
    }

    .profile-management-button:hover,
    .profile-management-button:focus-visible {
      background: var(--accent-soft);
      color: var(--accent-strong);
      outline: 1px solid #99d6ca;
    }

    .profile-management-button.danger:hover,
    .profile-management-button.danger:focus-visible {
      background: #fff1f2;
      color: #b91c1c;
      outline-color: #fecdd3;
    }

    .profile-management-button:disabled {
      opacity: .38;
      cursor: not-allowed;
    }

    .profile-management-button svg {
      width: 16px;
      height: 16px;
      stroke: currentColor;
    }

    .profile-core-chip {
      min-width: 0;
      min-height: 24px;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 1px 7px 1px 2px;
      border: 1px solid #dbe5f0;
      border-radius: 999px;
      background: #fff;
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      white-space: nowrap;
    }

    .profile-core-chip .route-encounter-badge {
      width: 21px;
      height: 21px;
      border-radius: 6px;
    }

    .profile-core-chip .route-encounter-badge svg {
      width: 14px;
      height: 14px;
    }

    .profile-core-value {
      min-width: 0;
      max-width: 210px;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .profile-detail-overview {
      padding: 5px;
      border: 1px solid #dbe5f0;
      border-radius: 8px;
      background: #f8fffc;
    }

    .profile-detail-overview .profile-icon-button,
    .profile-member-strip .profile-icon-button {
      width: 30px;
      height: 30px;
    }

    .profile-focus {
      display: grid;
      gap: 10px;
    }

    .profile-focus-head {
      align-items: center;
      min-height: 42px;
    }

    .profile-focus-title {
      min-width: 0;
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 800;
    }

    .profile-focus-title .route-encounter-badge {
      width: 26px;
      height: 26px;
      border-radius: 7px;
    }

    .profile-member-card .card-head {
      min-height: 38px;
    }

    .profile-add-control {
      min-width: min(420px, 100%);
      display: grid;
      grid-template-columns: minmax(170px, 1fr) auto;
      align-items: center;
      gap: 6px;
    }

    .profile-add-species-wrap {
      min-width: 0;
      height: 32px;
      display: grid;
      grid-template-columns: 28px minmax(0, 1fr);
      align-items: center;
      gap: 5px;
      padding: 1px 7px 1px 2px;
      border: 1px solid #dbe5f0;
      border-radius: 7px;
      background: #fff;
    }

    .profile-add-species-wrap .route-encounter-badge {
      width: 26px;
      height: 26px;
      border-radius: 7px;
    }

    .profile-add-input {
      width: 100%;
      min-width: 0;
      height: 28px;
      border: 0;
      background: transparent;
      color: var(--ink);
      font-weight: 750;
      outline: 0;
    }

    .profile-add-input.invalid {
      color: #b91c1c;
      background: #fff1f2;
      border-radius: 5px;
    }

    .profile-add-button.control {
      min-width: 76px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
    }

    .profile-add-button svg {
      width: 15px;
      height: 15px;
      stroke: currentColor;
    }

    .profile-bulk-assign {
      display: grid;
      grid-template-columns: minmax(170px, 220px) minmax(0, 1fr) auto;
      align-items: center;
      gap: 6px;
      padding: 6px 8px;
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      background: #f8fbff;
    }

    .profile-bulk-select-wrap {
      min-width: 0;
      height: 32px;
      display: grid;
      grid-template-columns: 28px minmax(0, 1fr);
      align-items: center;
      gap: 5px;
      padding: 1px 7px 1px 2px;
      border: 1px solid #dbe5f0;
      border-radius: 7px;
      background: #fff;
    }

    .profile-bulk-select-wrap .route-encounter-badge {
      width: 26px;
      height: 26px;
      border-radius: 7px;
    }

    .profile-bulk-type {
      width: 100%;
      min-width: 0;
      height: 28px;
      border: 0;
      background: transparent;
      color: var(--ink);
      font-weight: 850;
      outline: 0;
      padding: 0 22px 0 0;
    }

    .profile-bulk-preview {
      min-width: 0;
      display: flex;
      align-items: center;
      gap: 3px;
      overflow: hidden;
    }

    .profile-bulk-preview .profile-icon {
      width: 26px;
      height: 26px;
      flex: 0 0 auto;
      image-rendering: pixelated;
    }

    .profile-bulk-empty {
      color: var(--muted);
      font-size: 12px;
      font-weight: 750;
    }

    .profile-bulk-assign-button.control {
      min-width: 88px;
      min-height: 32px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
      font-weight: 850;
    }

    .profile-bulk-assign-button svg {
      width: 15px;
      height: 15px;
      stroke: currentColor;
    }

    .behavior-override-section {
      grid-column: 1 / -1;
    }

    .behavior-override-builder {
      display: grid;
      grid-template-columns: minmax(112px, 145px) minmax(130px, 180px) minmax(120px, 180px) minmax(150px, 220px) minmax(0, 1fr) auto;
      align-items: center;
      gap: 6px;
      margin-bottom: 8px;
      padding: 7px;
      border: 1px solid #dbe5f0;
      border-radius: 8px;
      background: #f8fbff;
    }

    .behavior-override-select {
      min-width: 0;
      height: 32px;
      border: 1px solid #d5e0ee;
      border-radius: 7px;
      background-color: #fff;
      color: var(--ink);
      font-weight: 850;
      padding: 0 26px 0 8px;
    }

    .behavior-override-preview {
      min-width: 0;
      display: flex;
      align-items: center;
      gap: 3px;
      overflow: hidden;
    }

    .behavior-override-preview .profile-icon {
      width: 26px;
      height: 26px;
      flex: 0 0 auto;
      image-rendering: pixelated;
    }

    .behavior-override-add.control {
      min-height: 32px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
      font-weight: 850;
      white-space: nowrap;
    }

    .behavior-override-pending {
      display: grid;
      gap: 6px;
      margin-bottom: 8px;
    }

    .behavior-override-pending-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: center;
      gap: 8px;
      border: 1px solid #b7e1d9;
      border-radius: 8px;
      background: #effcf9;
      padding: 7px 8px;
      font-weight: 850;
    }

    .behavior-override-pending-row .meta {
      margin-left: 6px;
      font-weight: 700;
    }

    .behavior-override-rule {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: center;
      gap: 8px;
    }

    .behavior-override-rule.pending-remove {
      border-color: #fecaca;
      background: #fff1f2;
      opacity: .82;
    }

    .behavior-override-rule.pending-remove .rule-top,
    .behavior-override-rule.pending-remove .muted {
      text-decoration: line-through;
      text-decoration-thickness: 2px;
      text-decoration-color: #f87171;
    }

    .behavior-override-remove.control {
      width: 32px;
      min-width: 32px;
      height: 32px;
      padding: 0;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      color: #b91c1c;
    }

    .behavior-override-remove.control svg {
      width: 16px;
      height: 16px;
      stroke: currentColor;
    }

    .profile-member-strip {
      padding: 8px;
      background: #fff;
    }

    .profile-member-item {
      min-width: 156px;
      max-width: 210px;
      height: 34px;
      display: inline-grid;
      grid-template-columns: minmax(0, 1fr) 28px;
      align-items: stretch;
      gap: 3px;
      flex: 0 0 auto;
    }

    .profile-member-chip {
      min-width: 0;
      width: 100%;
      height: 34px;
      display: inline-grid;
      grid-template-columns: 30px minmax(0, 1fr);
      align-items: center;
      gap: 6px;
      padding: 2px 8px 2px 2px;
      border: 1px solid #dbe5f0;
      border-radius: 7px;
      background: #fff;
      color: var(--ink);
      cursor: pointer;
      font: inherit;
      text-align: left;
    }

    .profile-member-chip:hover,
    .profile-member-chip:focus-visible {
      border-color: #99d6ca;
      background: #f0fdfa;
      outline: 0;
    }

    .profile-member-chip.active {
      border-color: #99d6ca;
      background: #e6f7f3;
      box-shadow: inset 0 0 0 1px var(--accent);
    }

    .profile-member-chip.changed {
      border-color: #f2d486;
      background: #fff8e6;
    }

    .profile-member-item.changed .profile-member-chip {
      border-color: #f2d486;
      background: #fff8e6;
    }

    .profile-member-chip .profile-icon {
      width: 30px;
      height: 30px;
    }

    .profile-member-name {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 12px;
      font-weight: 850;
      text-transform: uppercase;
    }

    .profile-member-remove {
      width: 28px;
      height: 34px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid #f3c7c7;
      border-radius: 7px;
      background: #fff7f7;
      color: #b91c1c;
      cursor: pointer;
    }

    .profile-member-remove:hover,
    .profile-member-remove:focus-visible {
      border-color: #fca5a5;
      background: #fee2e2;
      outline: 0;
    }

    .profile-member-remove svg {
      width: 14px;
      height: 14px;
      stroke: currentColor;
    }

    .chip {
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: #115e59;
      padding: 2px 8px;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }

    .chip.neutral {
      background: #eef2f7;
      color: var(--muted);
    }

    .field-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 1px;
      background: var(--line);
    }

    .profile-architecture-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 8px;
    }

    .profile-architecture-group {
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: #fff;
    }

    .profile-architecture-head {
      min-height: 34px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding: 4px 7px;
      border-bottom: 1px solid var(--line);
      background: #f8fafc;
      color: var(--ink);
      font-weight: 850;
    }

    .profile-architecture-title {
      min-width: 0;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }

    .profile-architecture-title .route-encounter-badge {
      width: 24px;
      height: 24px;
      border-radius: 7px;
    }

    .profile-architecture-fields {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 1px;
      background: var(--line);
    }

    .profile-architecture-fields .field {
      min-height: 38px;
      display: grid;
      grid-template-columns: 30px minmax(0, 1fr);
      align-items: center;
      gap: 6px;
      padding: 4px 7px;
      background: #fff;
    }

    .profile-architecture-fields .profile-suboption-field {
      min-height: 34px;
      padding-left: 18px;
      background: #f8fbff;
      box-shadow: inset 3px 0 0 #d7e5f5;
    }

    .profile-architecture-fields .field-label {
      position: absolute;
      width: 1px;
      height: 1px;
      overflow: hidden;
      clip: rect(0 0 0 0);
      white-space: nowrap;
    }

    .profile-field-badge {
      width: 30px;
      height: 30px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }

    .profile-field-badge .route-encounter-badge {
      width: 26px;
      height: 26px;
      border-radius: 7px;
    }

    .profile-architecture-fields .profile-combo {
      width: 100%;
      min-width: 0;
      height: 28px;
      margin-top: 0;
      border: 1px solid #dbe5f0;
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      padding: 0 7px;
      font-weight: 800;
      text-overflow: ellipsis;
    }

    .profile-subselect {
      width: 100%;
      min-width: 0;
      height: 28px;
      border: 1px solid #dbe5f0;
      border-radius: 6px;
      background-color: #fff;
      color: var(--ink);
      padding: 0 26px 0 7px;
      font-weight: 800;
    }

    select.control:focus-visible,
    .profile-subselect:focus-visible,
    .behavior-override-select:focus-visible,
    .profile-bulk-type:focus-visible {
      outline: 2px solid rgba(37, 99, 235, 0.35);
      outline-offset: 1px;
    }

    .profile-resolver-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      gap: 10px;
    }

    .profile-resolver-card .primitive-grid {
      margin-bottom: 8px;
    }

    .primitive-grid,
    .profile-rule-list {
      display: grid;
      gap: 5px;
    }

    .primitive-group {
      display: grid;
      grid-template-columns: 30px minmax(0, 1fr);
      gap: 6px;
      align-items: start;
      padding: 5px;
      border: 1px solid #dbe5f0;
      border-radius: 8px;
      background: #fff;
    }

    .primitive-values,
    .profile-rule-values {
      min-width: 0;
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 4px;
    }

    .primitive-chip,
    .profile-rule-chip {
      min-width: 0;
      max-width: 100%;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      min-height: 22px;
      border: 1px solid #dbe5f0;
      border-radius: 7px;
      background: #f8fafc;
      padding: 1px 6px;
      color: var(--ink);
      font-size: 11px;
      font-weight: 750;
    }

    .primitive-chip strong {
      color: var(--muted);
      font-weight: 800;
    }

    .profile-rule-chip {
      background: #f7fdf9;
      border-color: #cfe5df;
    }

    .field {
      background: #fff;
      padding: 7px 8px;
      min-width: 0;
    }

    .field-label {
      display: block;
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .02em;
    }

    .field-value {
      display: block;
      margin-top: 2px;
      font-weight: 650;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .profile-toolbar {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      padding: 10px;
      border-bottom: 1px solid var(--line);
      background: var(--surface-2);
      position: sticky;
      top: 0;
      z-index: 1;
    }

    .global-actions {
      margin-top: 8px;
      padding: 6px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #f8fafc;
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
      min-width: 0;
    }

    .action-groups {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
      flex: 0 1 auto;
      min-width: 0;
    }

    .action-group {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      flex-wrap: nowrap;
      min-width: 0;
      padding: 2px;
      border: 1px solid #e2e8f0;
      border-radius: 7px;
      background: #fff;
    }

    .shiny-counter-group {
      background: #fffbeb;
      border-color: #fde68a;
    }

    .shiny-counter-pill {
      height: 28px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 0 8px;
      border: 1px solid #facc15;
      border-radius: 7px;
      background: #fff7d1;
      color: #713f12;
      font-size: 12px;
      font-weight: 850;
      white-space: nowrap;
    }

    .shiny-counter-pill .muted {
      color: #8a6a18;
      font-weight: 750;
    }

    .shiny-counter-group .control {
      min-width: 28px;
      padding-inline: 7px;
      border-color: #f3d36a;
      background: #fffef7;
      color: #713f12;
      font-weight: 850;
    }

    .global-actions .control {
      height: 28px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      padding: 0 8px;
      white-space: nowrap;
    }

    .action-icon {
      width: 15px;
      height: 15px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex: 0 0 auto;
    }

    .action-icon svg {
      width: 15px;
      height: 15px;
      display: block;
      stroke: currentColor;
    }

    .primary-action {
      border-color: #0f766e;
      background: #0f766e;
      color: #fff;
    }

    .primary-action:hover {
      border-color: #115e59;
      background: #115e59;
    }

    .subtle-action {
      background: transparent;
    }

    .control:disabled {
      cursor: not-allowed;
      opacity: .55;
    }

    .save-status {
      display: flex;
      align-items: center;
      gap: 6px;
      flex: 1 1 180px;
      margin-left: auto;
      min-width: 0;
      max-width: 360px;
      min-height: 28px;
      padding: 4px 8px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #fff;
      color: var(--muted);
      font-weight: 650;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .save-status:empty {
      display: none;
    }

    .save-status:empty + .subtle-action {
      margin-left: auto;
    }

    .save-status::before {
      content: "";
      width: 7px;
      height: 7px;
      border-radius: 999px;
      background: #94a3b8;
      flex: 0 0 auto;
    }

    .save-status.status-success {
      border-color: #bbf7d0;
      background: #f0fdf4;
      color: #166534;
    }

    .save-status.status-success::before {
      background: #16a34a;
    }

    .save-status.status-error {
      border-color: #fecdd3;
      background: #fff1f2;
      color: #991b1b;
    }

    .save-status.status-error::before {
      background: #e11d48;
    }

    .save-status.status-busy {
      border-color: #bfdbfe;
      background: #eff6ff;
      color: #1d4ed8;
    }

    .save-status.status-busy::before {
      background: #2563eb;
    }

    .save-status.status-warning {
      border-color: #fde68a;
      background: #fffbeb;
      color: #92400e;
    }

    .save-status.status-warning::before {
      background: #f59e0b;
    }

    .switch-control {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 28px;
      padding: 0 7px;
      border: 1px solid transparent;
      border-radius: 7px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
      white-space: nowrap;
    }

    .switch-control:hover {
      border-color: var(--line);
      background: #f8fafc;
    }

    .switch-control input {
      position: absolute;
      opacity: 0;
      pointer-events: none;
    }

    .switch-track {
      width: 29px;
      height: 16px;
      border-radius: 999px;
      background: #cbd5e1;
      position: relative;
      flex: 0 0 auto;
      transition: background .14s ease;
    }

    .switch-track::after {
      content: "";
      position: absolute;
      top: 2px;
      left: 2px;
      width: 12px;
      height: 12px;
      border-radius: 999px;
      background: #fff;
      box-shadow: 0 1px 2px rgb(15 23 42 / 18%);
      transition: transform .14s ease;
    }

    .switch-control input:checked + .switch-track {
      background: #0f766e;
    }

    .switch-control input:checked + .switch-track::after {
      transform: translateX(13px);
    }

    .switch-control input:focus-visible + .switch-track {
      outline: 2px solid #99d6ca;
      outline-offset: 2px;
    }

    .switch-label {
      min-width: 0;
    }

    .toggle-control {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: var(--muted);
      font-weight: 650;
      min-height: 32px;
      white-space: nowrap;
    }

    .toggle-control input {
      margin: 0;
    }

    .build-output-panel {
      margin: 8px 0 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: #111827;
      box-shadow: 0 12px 28px rgb(15 23 42 / 18%);
    }

    .build-output-panel[hidden] {
      display: none;
    }

    .build-output-head {
      min-height: 34px;
      padding: 5px 8px 5px 10px;
      border-bottom: 1px solid rgb(148 163 184 / 28%);
      background: #111827;
      color: #e5e7eb;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }

    .build-output-title {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
      font-weight: 750;
    }

    .build-output-title .action-icon {
      color: #93c5fd;
    }

    .build-timer {
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      padding: 0 7px;
      border: 1px solid rgb(147 197 253 / 45%);
      border-radius: 999px;
      background: rgb(37 99 235 / 18%);
      color: #bfdbfe;
      font: 12px/1.4 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-variant-numeric: tabular-nums;
    }

    .build-output-close {
      width: 26px;
      height: 26px;
      border: 1px solid rgb(148 163 184 / 35%);
      border-radius: 6px;
      background: rgb(15 23 42 / 85%);
      color: #e5e7eb;
      cursor: pointer;
      font-weight: 800;
      line-height: 1;
    }

    .build-output-close:hover,
    .build-output-close:focus-visible {
      border-color: #93c5fd;
      background: #1e293b;
      outline: none;
    }

    .build-log {
      margin: 0;
      padding: 10px;
      max-height: min(30vh, 260px);
      overflow: auto;
      background: #0f172a;
      color: #e5e7eb;
      border: 0;
      border-radius: 0;
      font: 12px/1.4 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      white-space: pre-wrap;
    }

    .build-log[hidden] {
      display: none;
    }

    .field.changed {
      background: #fff8e6;
    }

    .profile-combo {
      width: 100%;
      height: 28px;
      margin-top: 3px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      font-weight: 650;
      min-width: 0;
      padding: 0 7px;
    }

    .profile-combo.invalid {
      border-color: #dc2626;
      background: #fff1f2;
    }

    .row {
      width: 100%;
      border: 0;
      border-bottom: 1px solid var(--line);
      background: #fff;
      color: inherit;
      display: grid;
      grid-template-columns: 38px 64px minmax(120px, 1fr) minmax(120px, 150px);
      gap: 8px;
      align-items: center;
      min-height: 50px;
      padding: 8px 10px;
      text-align: left;
      cursor: pointer;
      contain: layout paint;
      overflow-anchor: none;
    }

    .row.active {
      background: #edf7f4;
      box-shadow: inset 3px 0 0 var(--accent);
    }

    .list-more {
      padding: 10px;
      display: flex;
      justify-content: center;
      background: #fff;
    }

    .num {
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }

    .mon-icon {
      width: 32px;
      height: 32px;
      image-rendering: pixelated;
      object-fit: contain;
      display: block;
      max-width: 100%;
      max-height: 100%;
      justify-self: center;
    }

    .row > .mon-icon {
      width: 36px;
      height: 36px;
      justify-self: center;
    }

    .name {
      font-weight: 700;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .class-name {
      color: var(--muted);
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .detail {
      display: grid;
      grid-template-rows: auto auto 1fr;
      min-height: 0;
    }

    .detail-head {
      padding: 14px;
      border-bottom: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: flex-start;
    }

    .detail-title {
      display: grid;
      grid-template-columns: 48px minmax(0, 1fr);
      gap: 10px;
      align-items: center;
      min-width: 0;
    }

    .detail-icon {
      width: 44px;
      height: 44px;
      image-rendering: pixelated;
      object-fit: contain;
      display: block;
      max-width: 100%;
      max-height: 100%;
      justify-self: center;
    }

    .detail h2,
    .route-detail h2 {
      margin: 0;
      font-size: 20px;
      line-height: 1.1;
      letter-spacing: 0;
    }

    .meta {
      color: var(--muted);
      margin-top: 4px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .tabs {
      display: flex;
      gap: 6px;
      padding: 8px;
      border-bottom: 1px solid var(--line);
      background: var(--surface-2);
    }

    .tab {
      height: 30px;
      border: 1px solid transparent;
      border-radius: 6px;
      background: transparent;
      padding: 0 10px;
      cursor: pointer;
      font-weight: 700;
      color: var(--muted);
    }

    .tab.active {
      background: #fff;
      border-color: var(--line);
      color: var(--ink);
    }

    .tab-panel {
      display: none;
      overflow: auto;
      min-height: 0;
      padding: 12px;
      overscroll-behavior: contain;
      -webkit-overflow-scrolling: touch;
      contain: layout paint;
    }

    .tab-panel.active { display: block; }

    .timeline {
      display: grid;
      gap: 8px;
    }

    .step {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 9px 10px;
    }

    .step-title {
      font-weight: 750;
      display: flex;
      justify-content: space-between;
      gap: 8px;
      flex-wrap: wrap;
    }

    .changes {
      margin-top: 6px;
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

    .change {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface-2);
      padding: 3px 6px;
      font-size: 12px;
    }

    .rules {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .route-search {
      padding: 10px;
      border-bottom: 1px solid var(--line);
      background: #fff;
      display: grid;
      gap: 8px;
    }

    .route-search .control {
      width: 100%;
    }

    .route-spawn-filters {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 6px;
    }

    .route-spawn-filter {
      border: 1px solid #d7e1ee;
      border-radius: 7px;
      background: #fff;
      color: var(--muted);
      width: 34px;
      height: 34px;
      padding: 0;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      font: inherit;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0;
    }

    .route-spawn-filter .route-encounter-badge {
      width: 20px;
      height: 20px;
    }

    .route-spawn-filter .route-encounter-badge svg {
      width: 14px;
      height: 14px;
    }

    .route-spawn-filter.active {
      border-color: #9cc8bd;
      background: #eef9f6;
      color: #0f766e;
      box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.08);
    }

    .route-spawn-filter.spawn-headbutt-normal.active,
    .route-spawn-filter.spawn-headbutt-special.active {
      border-color: #0f5132;
      background: #e8f4eb;
      color: #064e3b;
      box-shadow: inset 0 0 0 1px rgba(6, 78, 59, 0.14);
    }

    .route-spawn-filter:not(.active) .route-encounter-badge {
      opacity: 0.56;
    }

    .route-spawn-filter:focus-visible {
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }

    .route-row {
      width: 100%;
      border: 0;
      border-bottom: 1px solid var(--line);
      background: #fff;
      color: inherit;
      display: grid;
      grid-template-columns: 56px minmax(0, 1fr);
      gap: 8px 10px;
      align-items: start;
      padding: 10px;
      text-align: left;
      cursor: pointer;
      contain: layout paint;
      overflow-anchor: none;
    }

    .route-row.active {
      background: #edf7f4;
      box-shadow: inset 3px 0 0 var(--accent);
    }

    .route-id {
      color: var(--muted);
      font-variant-numeric: tabular-nums;
      font-weight: 700;
    }

    .route-name {
      font-weight: 750;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .route-sub {
      color: var(--muted);
      margin-top: 2px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .route-icons {
      display: flex;
      grid-column: 2;
      justify-content: flex-start;
      flex-wrap: wrap;
      gap: 6px;
      max-width: 100%;
      overflow: visible;
      padding-top: 2px;
    }

    #routeList {
      overflow-anchor: none;
      scroll-behavior: auto;
    }

    .route-row[hidden],
    .route-encounter-group[hidden],
    .route-list-empty[hidden] {
      display: none !important;
    }

    .route-encounter-group {
      display: inline-grid;
      grid-template-columns: auto minmax(0, 1fr);
      align-items: center;
      gap: 4px;
      max-width: 100%;
      min-height: 30px;
      padding: 3px 5px;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      background: #fff;
    }

    .route-encounter-group.route-search-match-group {
      border-color: #f59e0b;
      background: #fffbeb;
      box-shadow: inset 0 0 0 1px rgba(245, 158, 11, 0.18);
    }

    .route-encounter-icons {
      display: inline-flex;
      align-items: center;
      gap: 2px;
      min-width: 0;
      color: #475569;
    }

    .route-encounter-badge {
      width: 22px;
      height: 22px;
      border: 1px solid #d8dee8;
      border-radius: 5px;
      background: #f8fafc;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex: 0 0 auto;
    }

    .route-encounter-badge svg {
      width: 15px;
      height: 15px;
      display: block;
      stroke: currentColor;
    }

    .route-encounter-badge.type-grass {
      color: #15803d;
      background: #f0fdf4;
    }

    .route-encounter-badge.type-surf {
      color: #0369a1;
      background: #eff6ff;
    }

    .route-encounter-badge.type-rock {
      color: #854d0e;
      background: #fffbeb;
    }

    .route-encounter-badge.type-headbutt {
      color: #064e3b;
      background: #e8f4eb;
      border-color: #0f5132;
    }

    .route-encounter-badge.special-headbutt {
      color: #022c22;
      background: #d9f0df;
      border-color: #064e3b;
    }

    .route-encounter-badge.type-rod {
      color: #0369a1;
      background: #e0f2fe;
    }

    .route-encounter-badge.type-sound {
      color: #6d28d9;
      background: #f5f3ff;
    }

    .route-encounter-badge.type-swarm {
      color: #be123c;
      background: #fff1f2;
    }

    .route-encounter-badge.type-flow {
      color: #6d28d9;
      background: #f5f3ff;
    }

    .route-encounter-badge.type-placement {
      color: #b45309;
      background: #fffbeb;
    }

    .route-encounter-badge.type-movement {
      color: #475569;
      background: #f8fafc;
    }

    .route-encounter-badge.type-shiny {
      color: #be123c;
      background: #fff1f2;
    }

    .route-encounter-badge.type-test {
      color: #0f766e;
      background: #ecfeff;
    }

    .route-encounter-badge.time-morning {
      color: var(--time-morning-ink);
      background: var(--time-morning-bg);
      border-color: var(--time-morning-border);
    }

    .route-encounter-badge.time-day {
      color: var(--time-day-ink);
      background: var(--time-day-bg);
      border-color: var(--time-day-border);
    }

    .route-encounter-badge.time-night {
      color: var(--time-night-ink);
      background: var(--time-night-bg);
      border-color: var(--time-night-border);
    }

    .route-encounter-text {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }

    .route-encounter-mon-icons {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 2px;
      min-width: 0;
    }

    .route-encounter-mon-icons .mon-icon {
      width: 22px;
      height: 22px;
      border-radius: 4px;
      background: #fff;
      flex: 0 0 auto;
    }

    .swap-mon-button {
      width: 28px;
      height: 28px;
      border: 1px solid transparent;
      border-radius: 6px;
      background: transparent;
      padding: 0;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      flex: 0 0 auto;
    }

    .swap-mon-button:hover,
    .swap-mon-button:focus-visible {
      border-color: #99d6ca;
      background: #e6f7f3;
      outline: 0;
    }

    .swap-mon-button.route-search-match {
      border-color: #f59e0b;
      background: #fff7ed;
      box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.18);
    }

    .swap-mon-button.route-search-match .mon-icon {
      filter: drop-shadow(0 1px 0 rgba(146, 64, 14, 0.35));
    }

    .swap-mon-button .mon-icon {
      width: 26px;
      height: 26px;
      image-rendering: pixelated;
      object-fit: contain;
      pointer-events: none;
    }

    .route-row > .chip.neutral {
      grid-column: 2;
      justify-self: start;
    }

    .route-row:focus-visible {
      outline: 2px solid #99d6ca;
      outline-offset: -2px;
    }

    .route-filtered-chip {
      display: none;
    }

    .route-row.no-enabled-groups .route-filtered-chip {
      display: inline-flex;
    }

    .route-detail {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      min-height: 0;
    }

    .route-global-settings {
      justify-self: stretch;
      min-width: 0;
      max-width: 100%;
      overflow: hidden;
      overscroll-behavior: contain;
      -webkit-overflow-scrolling: touch;
    }

    .route-global-settings:empty {
      display: none;
    }

    .route-editor {
      padding: 12px;
      display: grid;
      align-content: start;
      grid-auto-rows: max-content;
      gap: 12px;
    }

    .route-section {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      overflow: hidden;
      contain: layout paint;
    }

    .collapsible-section > summary {
      cursor: pointer;
      list-style: none;
      user-select: none;
    }

    .collapsible-button {
      width: 100%;
      border: 0;
      color: inherit;
      cursor: pointer;
      font: inherit;
      text-align: left;
      user-select: none;
    }

    .collapsible-button:focus-visible {
      outline: 2px solid #99d6ca;
      outline-offset: -2px;
    }

    .collapsible-section > summary::-webkit-details-marker {
      display: none;
    }

    .collapsible-title {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
    }

    .collapse-caret {
      width: 18px;
      height: 18px;
      border: 1px solid var(--line);
      border-radius: 5px;
      background: #fff;
      flex: 0 0 auto;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }

    .collapse-caret::before {
      content: "";
      width: 0;
      height: 0;
      border-top: 4px solid transparent;
      border-bottom: 4px solid transparent;
      border-left: 6px solid var(--muted);
      transform-origin: 3px 4px;
      transition: transform .12s ease;
    }

    .collapsible-section[open] > summary .collapse-caret::before,
    .collapsible-section.is-open > .collapsible-head .collapse-caret::before {
      transform: rotate(90deg);
    }

    .collapsible-section:not([open]) > summary,
    .collapsible-section.is-collapsed > .collapsible-head {
      border-bottom: 0;
    }

    .collapsible-body {
      min-width: 0;
    }

    .route-section-head {
      min-height: 38px;
      padding: 8px 10px;
      border-bottom: 1px solid var(--line);
      background: var(--surface-2);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }

    .route-section-title {
      font-weight: 750;
      min-width: 0;
    }

    .rates-grid,
    .swarm-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(128px, 1fr));
      gap: 1px;
      background: var(--line);
    }

    .spawn-settings-toolbar {
      min-width: 0;
      max-width: 100%;
    }

    .spawn-settings-content {
      display: flex;
      align-items: center;
      flex-wrap: nowrap;
      gap: 4px;
      padding: 2px;
      min-width: 0;
      max-width: 100%;
      overflow-x: auto;
      overflow-y: hidden;
      scrollbar-width: thin;
      scrollbar-color: #b6c2d2 transparent;
      background: transparent;
    }

    .spawn-settings-content::-webkit-scrollbar {
      height: 5px;
    }

    .spawn-settings-content::-webkit-scrollbar-thumb {
      border-radius: 999px;
      background: #b6c2d2;
    }

    .spawn-settings-row {
      min-width: 0;
      max-width: none;
      flex: 0 0 auto;
      display: inline-flex;
      align-items: center;
      gap: 3px;
      padding: 2px;
      border: 1px solid #d7e1ee;
      border-radius: 9px;
      background: #fff;
    }

    .spawn-group-icon {
      width: 24px;
      height: 24px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }

    .spawn-group-icon .route-encounter-badge,
    .spawn-setting-chip .route-encounter-badge {
      width: 23px;
      height: 23px;
      border-radius: 6px;
    }

    .spawn-group-icon .route-encounter-badge svg,
    .spawn-setting-chip .route-encounter-badge svg {
      width: 15px;
      height: 15px;
    }

    .spawn-settings-chips {
      min-width: 0;
      display: inline-flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 3px;
    }

    .spawn-setting-chip.route-field {
      min-width: 0;
      min-height: 28px;
      display: inline-flex;
      align-items: center;
      gap: 3px;
      padding: 1px 6px 1px 2px;
      border: 1px solid #dbe5f0;
      border-radius: 7px;
      background: #fff;
      color: var(--ink);
      cursor: pointer;
      font: inherit;
    }

    .spawn-setting-chip.route-field:hover {
      border-color: #99d6ca;
      box-shadow: 0 1px 4px rgb(15 23 42 / 8%);
    }

    .spawn-setting-chip.route-field:focus-visible {
      outline: 2px solid #99d6ca;
      outline-offset: 2px;
    }

    .spawn-setting-chip.changed {
      background: #fff8e6;
      border-color: #f2d486;
    }

    .spawn-setting-value {
      min-width: 18px;
      color: var(--ink);
      font-size: 13px;
      font-weight: 850;
      font-variant-numeric: tabular-nums;
      line-height: 1;
      text-align: center;
      white-space: nowrap;
    }

    .spawn-setting-chip .mon-icon {
      width: 24px;
      height: 24px;
      flex: 0 0 auto;
      object-fit: contain;
      image-rendering: pixelated;
    }

    .route-field {
      background: #fff;
      min-width: 0;
      padding: 7px 8px;
    }

    .route-field.changed,
    .route-table td.changed {
      background: #fff8e6;
    }

    .route-input {
      width: 100%;
      height: 28px;
      margin-top: 3px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      font-weight: 650;
      min-width: 0;
      padding: 0 7px;
    }

    .route-input.invalid {
      border-color: #dc2626;
      background: #fff1f2;
    }

    .setting-symbol {
      color: var(--muted);
      display: block;
      font-size: 11px;
      line-height: 1.2;
      margin-top: 2px;
      overflow-wrap: anywhere;
      white-space: normal;
    }

    .spawn-setting-dialog {
      width: min(440px, calc(100vw - 24px));
      border: 1px solid var(--line);
      border-radius: 10px;
      background: #fff;
      color: var(--ink);
      padding: 0;
      box-shadow: 0 18px 48px rgba(15, 23, 42, 0.22);
    }

    .spawn-setting-dialog::backdrop {
      background: rgba(15, 23, 42, 0.18);
    }

    .spawn-setting-card {
      display: grid;
      gap: 10px;
      padding: 12px;
    }

    .spawn-setting-dialog-head {
      min-width: 0;
      display: grid;
      grid-template-columns: 34px minmax(0, 1fr);
      gap: 8px;
      align-items: center;
    }

    .spawn-setting-dialog-head .route-encounter-badge {
      width: 32px;
      height: 32px;
      border-radius: 8px;
    }

    .spawn-setting-dialog-title {
      min-width: 0;
      display: grid;
      gap: 2px;
    }

    .spawn-setting-dialog-title strong {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .spawn-setting-dialog-title span,
    .spawn-setting-help,
    .spawn-setting-error {
      color: var(--muted);
      font-size: 12px;
    }

    .spawn-setting-field-dialog {
      display: grid;
      gap: 4px;
    }

    .spawn-setting-field-dialog span {
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: .02em;
      text-transform: uppercase;
    }

    .spawn-setting-dialog-input {
      width: 100%;
      height: 34px;
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 0 9px;
      color: var(--ink);
      font-weight: 750;
    }

    .spawn-setting-dialog-input.invalid {
      border-color: #dc2626;
      background: #fff1f2;
    }

    .spawn-setting-test-grid {
      display: grid;
      gap: 8px;
    }

    .spawn-setting-toggle-row {
      min-height: 38px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #f8fafc;
      font-weight: 800;
    }

    .spawn-setting-toggle-row input {
      width: 42px;
      height: 24px;
      accent-color: var(--accent);
      cursor: pointer;
    }

    .spawn-setting-species-wrap {
      display: grid;
      grid-template-columns: 32px minmax(0, 1fr);
      gap: 8px;
      align-items: center;
    }

    .spawn-setting-species-wrap .mon-icon {
      width: 30px;
      height: 30px;
      object-fit: contain;
      image-rendering: pixelated;
    }

    .spawn-setting-error {
      min-height: 16px;
      color: #b91c1c;
    }

    .spawn-setting-dialog-actions {
      display: flex;
      justify-content: flex-end;
      gap: 6px;
    }

    .spawn-setting-dialog-actions .control {
      width: auto;
      min-width: 78px;
    }

    .route-table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }

    .route-table th,
    .route-table td {
      border-bottom: 1px solid var(--line);
      padding: 8px 6px;
      text-align: left;
      vertical-align: middle;
    }

    .route-table th {
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      background: #fbfdff;
    }

    .route-table tr:last-child td {
      border-bottom: 0;
    }

    .route-table .slot-cell {
      width: 54px;
      color: var(--muted);
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }

    .route-table .weight-cell {
      width: 58px;
      color: var(--muted);
      font-variant-numeric: tabular-nums;
    }

    .route-table .level-cell {
      width: 84px;
    }

    .species-input-wrap {
      display: grid;
      grid-template-columns: 38px minmax(0, 1fr) 58px;
      gap: 8px;
      align-items: center;
      min-height: 38px;
    }

    .species-input-wrap .mon-icon {
      width: 36px;
      height: 36px;
    }

    .grass-slot-list {
      display: grid;
      gap: 8px;
      padding: 10px;
      background: #f8fafc;
    }

    .grass-slot-card {
      border: 1px solid #d8e1ee;
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
      overflow: hidden;
    }

    .grass-weight-bar {
      height: 4px;
      background: linear-gradient(90deg, #15803d var(--grass-rate), #e2e8f0 var(--grass-rate));
    }

    .grass-slot-main {
      display: grid;
      grid-template-columns: minmax(124px, 148px) minmax(0, 1fr);
      min-width: 0;
    }

    .grass-slot-meta {
      border-right: 1px solid var(--line);
      background: #fbfdff;
      padding: 8px;
      display: grid;
      grid-template-columns: 38px 44px minmax(48px, 1fr);
      gap: 6px;
      align-content: start;
      align-items: stretch;
    }

    .grass-stat {
      min-width: 0;
      padding: 5px;
      border: 1px solid #e2e8f0;
      border-radius: 7px;
      background: #fff;
    }

    .grass-stat-label,
    .grass-time-title {
      display: block;
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: .02em;
      line-height: 1.1;
      text-transform: uppercase;
    }

    .grass-slot-meta .grass-stat-label,
    .grass-slot-meta .grass-time-title {
      font-size: 9px;
    }

    .grass-stat strong {
      display: block;
      margin-top: 4px;
      color: var(--ink);
      font-size: 17px;
      font-variant-numeric: tabular-nums;
      line-height: 1;
    }

    .grass-level-control.route-field {
      border: 1px solid #e2e8f0;
      border-radius: 7px;
      padding: 5px;
      background: #fff;
    }

    .grass-level-control .route-input {
      height: 26px;
      margin-top: 3px;
      font-size: 13px;
      padding: 0 5px;
    }

    .grass-time-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 1px;
      min-width: 0;
      background: var(--line);
    }

    .grass-time-cell.route-field {
      display: grid;
      align-content: start;
      gap: 6px;
      min-width: 0;
      min-height: 92px;
      padding: 8px;
      background: #fff;
    }

    .grass-time-head {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr) 46px;
      align-items: center;
      gap: 7px;
      min-width: 0;
    }

    .grass-time-head .route-encounter-badge {
      width: 21px;
      height: 21px;
    }

    .grass-time-cell .species-input-wrap {
      grid-template-columns: 34px minmax(0, 1fr);
      grid-template-areas: "icon species";
      gap: 4px 7px;
      min-height: 32px;
    }

    .grass-time-cell .species-input-wrap .mon-icon {
      grid-area: icon;
      align-self: center;
      width: 30px;
      height: 30px;
    }

    .grass-time-cell .route-input {
      height: 30px;
      margin-top: 0;
      font-size: 13px;
      font-weight: 750;
    }

    .grass-time-cell .route-species-combo {
      grid-area: species;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }

    .grass-time-cell .route-form {
      width: 46px;
      justify-self: end;
    }

    .grass-time-cell.changed,
    .grass-level-control.changed {
      background: #fff8e6;
    }

    .encounter-slot-list {
      display: grid;
      gap: 8px;
      padding: 10px;
      background: #f8fafc;
    }

    .encounter-slot-card {
      border: 1px solid #d8e1ee;
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
      overflow: hidden;
    }

    .encounter-weight-bar {
      height: 4px;
      background: linear-gradient(90deg, var(--slot-accent, #0f766e) var(--slot-rate), #e2e8f0 var(--slot-rate));
    }

    .encounter-slot-main {
      display: grid;
      grid-template-columns: minmax(82px, 96px) minmax(0, 1fr);
      min-width: 0;
    }

    .encounter-slot-main.with-levels {
      grid-template-columns: minmax(82px, 96px) minmax(0, 1fr) minmax(116px, 132px);
    }

    .encounter-slot-meta {
      border-right: 1px solid var(--line);
      background: #fbfdff;
      padding: 8px;
      display: grid;
      grid-template-columns: 38px minmax(38px, 1fr);
      gap: 6px;
      align-items: stretch;
    }

    .encounter-stat {
      min-width: 0;
      padding: 5px;
      border: 1px solid #e2e8f0;
      border-radius: 7px;
      background: #fff;
    }

    .encounter-stat-label,
    .encounter-species-title {
      display: block;
      color: var(--muted);
      font-size: 9px;
      font-weight: 800;
      letter-spacing: .02em;
      line-height: 1.1;
      text-transform: uppercase;
    }

    .encounter-stat strong {
      display: block;
      margin-top: 4px;
      color: var(--ink);
      font-size: 17px;
      font-variant-numeric: tabular-nums;
      line-height: 1;
    }

    .encounter-species-cell.route-field {
      display: grid;
      align-content: start;
      gap: 6px;
      min-width: 0;
      min-height: 86px;
      padding: 8px;
      background: #fff;
    }

    .encounter-species-head {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 46px;
      align-items: center;
      gap: 7px;
      min-width: 0;
    }

    .encounter-species-cell .species-input-wrap {
      grid-template-columns: 32px minmax(0, 1fr);
      grid-template-areas: "icon species";
      gap: 4px 7px;
      min-height: 32px;
    }

    .encounter-species-cell .species-input-wrap .mon-icon {
      grid-area: icon;
      align-self: center;
      width: 30px;
      height: 30px;
    }

    .encounter-species-cell .route-input {
      height: 30px;
      margin-top: 0;
      font-size: 13px;
      font-weight: 750;
    }

    .encounter-species-cell .route-species-combo {
      grid-area: species;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }

    .encounter-species-cell .route-form {
      width: 46px;
      justify-self: end;
    }

    .encounter-levels {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 1px;
      border-left: 1px solid var(--line);
      background: var(--line);
      min-width: 0;
    }

    .encounter-level-control.route-field {
      display: grid;
      align-content: start;
      gap: 4px;
      min-width: 0;
      padding: 7px;
      background: #fff;
    }

    .encounter-level-control .route-input {
      height: 30px;
      margin-top: 0;
      font-size: 13px;
      padding: 0 5px;
    }

    .encounter-species-cell.changed,
    .encounter-level-control.changed {
      background: #fff8e6;
    }

    .route-form {
      padding: 0 5px;
    }

    .status-line {
      color: var(--muted);
      min-width: 0;
    }

    .rule-list {
      display: grid;
      gap: 8px;
    }

    .rule {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 9px;
    }

    .rule-top {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 5px;
      font-weight: 750;
    }

    .class-rule-group {
      display: grid;
      gap: 8px;
      padding: 8px;
    }

    .class-rule-group-head {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: center;
      gap: 10px;
    }

    .class-rule-group-title {
      min-width: 0;
      display: flex;
      align-items: baseline;
      gap: 8px;
      flex-wrap: wrap;
      font-weight: 850;
    }

    .class-rule-group-title .muted {
      font-size: 13px;
      font-weight: 750;
    }

    .class-rule-members {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 5px;
    }

    .class-rule-member {
      min-width: 0;
      min-height: 30px;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 2px 7px 2px 3px;
      border: 1px solid #dbe5f0;
      border-radius: 8px;
      background: #f8fbff;
      color: var(--ink);
      font-size: 13px;
      font-weight: 800;
    }

    .class-rule-member .profile-icon-button {
      width: 26px;
      height: 26px;
    }

    .class-rule-member-order {
      color: var(--muted);
      font-weight: 900;
    }

    .class-rule-member-summary {
      max-width: 220px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .class-rule-member.compact {
      width: 30px;
      min-height: 30px;
      justify-content: center;
      padding: 2px;
    }

    .class-rule-member.compact .profile-icon-button {
      width: 26px;
      height: 26px;
    }

    .muted { color: var(--muted); }

    .empty {
      padding: 24px;
      color: var(--muted);
      text-align: center;
    }

    @media (max-width: 900px), (max-width: 1180px) and (orientation: portrait) {
      html {
        height: 100%;
        overflow: hidden;
      }

      body {
        height: 100%;
        min-height: 0;
        overflow: hidden;
      }

      .app {
        height: 100vh;
        height: 100dvh;
        min-height: 0;
        overflow: hidden;
      }

      header {
        padding: 8px;
        overflow: visible;
      }

      .bar {
        gap: 6px;
      }

      .primary-bar {
        display: grid;
        grid-template-columns: auto minmax(0, 1fr);
        align-items: center;
        margin-bottom: 6px;
      }

      .title {
        margin-right: 0;
      }

      .workspace-tabs {
        width: 100%;
        flex: none;
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .workspace-tab {
        height: 32px;
        padding: 0 8px;
        font-size: 12px;
      }

      .source {
        grid-column: 1 / -1;
        width: 100%;
        order: 3;
        font-size: 12px;
      }

      .header-controls {
        display: grid;
        grid-template-columns: minmax(0, 1fr);
      }

      main.view {
        grid-template-columns: 1fr;
        grid-template-rows: none;
        align-content: start;
        gap: 10px;
        padding: 8px;
        min-height: 0;
        overflow-x: hidden;
        overflow-y: auto;
        overscroll-behavior: contain;
        -webkit-overflow-scrolling: touch;
      }

      #encountersView {
        grid-template-rows: none;
        grid-auto-rows: max-content;
        align-content: start;
      }

      .pane {
        box-shadow: 0 6px 18px rgb(15 23 42 / 7%);
      }

      #speciesList,
      #routeList {
        max-height: min(34dvh, 360px);
      }

      .route-global-settings {
        overflow: visible;
      }

      .route-detail {
        display: grid;
        grid-template-rows: auto minmax(0, 1fr);
        min-height: min(58dvh, 620px);
      }

      .route-editor.scroll,
      .tab-panel.active {
        overflow: auto;
      }

      .detail-head {
        padding: 10px;
        align-items: flex-start;
      }

      .detail h2,
      .route-detail h2 {
        font-size: 18px;
      }

      .meta {
        gap: 6px;
        font-size: 12px;
      }

      .rules {
        grid-template-columns: 1fr;
      }

      .behavior-override-builder {
        grid-template-columns: 1fr;
      }

      .behavior-override-preview {
        min-height: 30px;
      }

      input.control,
      select.control {
        width: 100%;
      }
      .card-head {
        align-items: flex-start;
        flex-direction: column;
      }
      .profile-icons {
        max-width: 100%;
        justify-content: flex-start;
      }
      .profiles {
        grid-template-columns: minmax(0, 1fr);
      }

      .row {
        grid-template-columns: 38px 54px minmax(0, 1fr);
      }
      .row > .mon-icon,
      .row > .num {
        grid-row: 1 / span 2;
        align-self: center;
      }
      .row .class-name {
        grid-column: 3;
      }

      .profile-row {
        grid-template-columns: 30px minmax(0, 1fr) auto;
        gap: 6px;
      }

      .profile-row-icons {
        grid-column: 1 / -1;
        max-height: 74px;
        padding-left: 38px;
      }

      .profile-detail-top {
        display: grid;
        gap: 8px;
      }

      .profile-detail-tools {
        justify-content: flex-start;
      }

      .profile-detail-overview {
        flex-wrap: nowrap;
        overflow-x: auto;
        padding-bottom: 4px;
      }

      .profile-detail-overview .profile-icon-button {
        flex: 0 0 auto;
      }

      .profile-member-strip {
        max-height: 230px;
        overflow: auto;
      }

      .profile-add-control {
        width: 100%;
        min-width: 0;
        grid-template-columns: minmax(0, 1fr) auto;
      }

      .profile-bulk-assign {
        grid-template-columns: minmax(0, 1fr) auto;
      }

      .profile-bulk-preview {
        grid-column: 1 / -1;
        order: 3;
      }

      .route-search {
        padding: 8px;
      }

      .route-spawn-filters {
        flex-wrap: nowrap;
        overflow-x: auto;
        padding-bottom: 2px;
        scroll-snap-type: x proximity;
      }

      .route-spawn-filter {
        flex: 0 0 auto;
        scroll-snap-align: start;
      }

      .encounter-summary-row {
        grid-template-columns: minmax(82px, 96px) minmax(0, 1fr);
        gap: 4px;
        min-height: 38px;
        padding: 4px;
      }

      .encounter-summary-source {
        grid-template-columns: 26px minmax(0, 1fr);
        gap: 4px;
      }

      .encounter-summary-source .route-encounter-badge {
        width: 24px;
        height: 24px;
      }

      .encounter-summary-source .route-encounter-badge svg {
        width: 16px;
        height: 16px;
      }

      .encounter-summary-pokemon {
        --encounter-summary-min-width: 64px;
      }

      .encounter-summary-chip {
        gap: 4px;
        padding: 3px 5px 3px 3px;
      }

      .encounter-summary-name {
        max-width: 92px;
        font-size: 11px;
      }

      .encounter-summary-species-input {
        font-size: 11px;
      }

      .route-row {
        grid-template-columns: 44px minmax(0, 1fr);
        padding: 9px;
      }

      .route-icons {
        grid-column: 1 / -1;
        flex-wrap: nowrap;
        overflow-x: auto;
        padding-bottom: 2px;
      }

      .route-encounter-group {
        flex: 0 0 auto;
      }

      .route-encounter-mon-icons .mon-icon {
        width: 20px;
        height: 20px;
      }

      .spawn-settings-content {
        padding: 5px;
        gap: 4px;
      }

      .route-section-head {
        min-height: 42px;
        padding: 8px;
      }

      .rates-grid,
      .swarm-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
        padding: 8px;
        background: #fff;
      }

      .rates-grid .route-field,
      .swarm-grid .route-field {
        border: 1px solid var(--line);
        border-radius: 7px;
      }

      .route-table {
        display: block;
        min-width: 0;
      }

      .route-table thead {
        display: none;
      }

      .route-table tbody {
        display: grid;
        gap: 8px;
        padding: 8px;
        background: #fff;
      }

      .route-table tr {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
        padding: 8px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: #fff;
      }

      .route-table.grass-table tr {
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }

      .route-table.pokemon-slot-table tr {
        grid-template-columns: 54px 56px minmax(0, 1fr);
      }

      .route-table.encounter-slot-table tr {
        grid-template-columns: 54px 56px minmax(0, 1fr) 68px 68px;
      }

      .route-table th,
      .route-table td {
        border-bottom: 0;
      }

      .route-table td {
        display: grid;
        gap: 4px;
        min-width: 0;
        padding: 0;
      }

      .route-table td::before {
        content: attr(data-label);
        color: var(--muted);
        font-size: 11px;
        font-weight: 750;
        text-transform: uppercase;
        letter-spacing: .02em;
      }

      .route-table td[data-label="Pokemon"],
      .route-table td[data-label="Morning"],
      .route-table td[data-label="Day"],
      .route-table td[data-label="Night"] {
        grid-column: 1 / -1;
      }

      .route-table.grass-table td[data-label="Morning"],
      .route-table.grass-table td[data-label="Day"],
      .route-table.grass-table td[data-label="Night"],
      .route-table.pokemon-slot-table td[data-label="Pokemon"],
      .route-table.encounter-slot-table td[data-label="Pokemon"] {
        grid-column: auto;
      }

      .route-table .slot-cell,
      .route-table .weight-cell,
      .route-table .level-cell {
        width: auto;
      }

      .route-section,
      .spawn-settings-section {
        overflow: visible;
      }

      .species-input-wrap {
        grid-template-columns: 32px minmax(0, 1fr) 50px;
        gap: 6px;
        min-height: 34px;
      }

      .species-input-wrap .mon-icon {
        width: 30px;
        height: 30px;
      }

      .route-input {
        height: 32px;
        margin-top: 0;
      }

      .grass-slot-list {
        gap: 8px;
        padding: 8px;
      }

      .grass-slot-main {
        grid-template-columns: minmax(124px, 148px) minmax(0, 1fr);
      }

      .grass-slot-meta {
        border-right: 1px solid var(--line);
        border-bottom: 0;
        grid-template-columns: 38px 44px minmax(48px, 1fr);
      }

      .grass-level-control.route-field {
        grid-column: auto;
      }

      .grass-time-cell.route-field {
        min-height: 88px;
        padding: 7px;
      }

      .grass-time-cell .species-input-wrap {
        grid-template-columns: 32px minmax(0, 1fr);
        gap: 6px;
      }

      .encounter-slot-list {
        gap: 8px;
        padding: 8px;
      }

      .encounter-slot-main {
        grid-template-columns: minmax(82px, 96px) minmax(0, 1fr);
      }

      .encounter-slot-main.with-levels {
        grid-template-columns: minmax(82px, 96px) minmax(0, 1fr) minmax(112px, 124px);
      }

      .encounter-slot-meta {
        border-right: 1px solid var(--line);
        border-bottom: 0;
      }

      .encounter-species-cell.route-field {
        min-height: 82px;
        padding: 7px;
      }

      .encounter-species-cell .species-input-wrap {
        grid-template-columns: 30px minmax(0, 1fr);
        gap: 6px;
      }

      .encounter-species-cell .species-input-wrap .mon-icon {
        width: 28px;
        height: 28px;
      }

      .global-actions {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        align-items: start;
        gap: 6px;
        margin-top: 6px;
        padding: 5px;
      }

      .action-groups {
        width: 100%;
        display: grid;
        grid-template-columns: minmax(0, 1fr);
        gap: 6px;
      }

      .action-group {
        width: 100%;
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 4px;
      }

      .global-actions .control {
        width: 100%;
        height: 32px;
        padding: 0 8px;
      }

      .switch-control {
        width: 100%;
        justify-content: center;
        min-height: 32px;
        padding: 0 6px;
      }

      .global-actions .subtle-action {
        width: 38px;
        margin-left: 0;
      }

      .global-actions .subtle-action span:not(.action-icon) {
        display: none;
      }

      .save-status {
        grid-column: 1 / -1;
        flex: 1 1 100%;
        max-width: none;
      }
    }

    @media (max-width: 700px) {
      .primary-bar {
        grid-template-columns: minmax(0, 1fr);
      }

      .route-swap-entry {
        grid-template-columns: 54px minmax(0, 1fr);
        gap: 5px;
        padding: 5px;
      }

      .route-swap-entry-control {
        grid-template-columns: 28px minmax(0, 1fr);
        gap: 5px;
      }

      .route-swap-entry-control .mon-icon {
        width: 28px;
        height: 28px;
      }

      .profile-row {
        grid-template-columns: 28px minmax(0, 1fr);
      }

      .profile-row-count {
        grid-column: 2;
        justify-self: start;
      }

      .profile-row-icons {
        padding-left: 34px;
      }

      .profile-member-item {
        min-width: 118px;
        max-width: none;
      }

      .profile-architecture-grid,
      .profile-resolver-grid {
        grid-template-columns: minmax(0, 1fr);
      }

      .profile-architecture-fields {
        grid-template-columns: minmax(0, 1fr);
      }

      .route-swap-levels {
        grid-column: 2 / -1;
        flex-wrap: wrap;
      }

      .route-swap-level-field {
        height: 26px;
        grid-template-columns: auto 36px;
      }

      .route-swap-level-input {
        width: 36px;
        height: 22px;
      }

      .encounter-summary-pokemon {
        --encounter-summary-min-width: 44px;
        overflow: hidden;
      }

      .encounter-summary-chip {
        min-width: 0;
      }

      .route-table.grass-table tr,
      .route-table.pokemon-slot-table tr,
      .route-table.encounter-slot-table tr {
        grid-template-columns: minmax(0, 1fr);
      }

      .route-table td,
      .route-table.grass-table td[data-label="Morning"],
      .route-table.grass-table td[data-label="Day"],
      .route-table.grass-table td[data-label="Night"],
      .route-table.pokemon-slot-table td[data-label="Pokemon"],
      .route-table.encounter-slot-table td[data-label="Pokemon"] {
        grid-column: 1 / -1;
      }

      .species-input-wrap {
        grid-template-columns: 32px minmax(0, 1fr) 50px;
        gap: 6px;
      }

      .grass-slot-main {
        grid-template-columns: minmax(0, 1fr);
      }

      .grass-slot-meta {
        border-right: 0;
        border-bottom: 1px solid var(--line);
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }

      .grass-time-grid {
        grid-template-columns: minmax(0, 1fr);
      }

      .grass-level-control.route-field {
        grid-column: auto;
      }

      .encounter-slot-main,
      .encounter-slot-main.with-levels {
        grid-template-columns: minmax(0, 1fr);
      }

      .encounter-slot-meta {
        border-right: 0;
        border-bottom: 1px solid var(--line);
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .encounter-levels {
        border-left: 0;
        border-top: 1px solid var(--line);
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }

    @media (min-width: 701px) and (max-width: 900px), (min-width: 701px) and (max-width: 1180px) and (orientation: portrait) {
      .global-actions {
        display: flex;
        align-items: center;
      }

      .action-groups {
        width: auto;
        display: flex;
        flex-wrap: wrap;
      }

      .action-group {
        width: auto;
        display: inline-flex;
        flex-wrap: nowrap;
      }

      .global-actions .control,
      .switch-control {
        width: auto;
      }

      .global-actions .subtle-action {
        width: auto;
      }

      .global-actions .subtle-action span:not(.action-icon) {
        display: inline;
      }
    }

    @media (max-width: 560px) {
      header {
        padding: 6px;
      }

      .workspace-tab {
        font-size: 11px;
        padding: 0 6px;
      }

      .global-actions {
        grid-template-columns: minmax(0, 1fr);
      }

      .global-actions .subtle-action {
        width: 100%;
      }

      .global-actions .subtle-action span:not(.action-icon) {
        display: inline;
      }

      #speciesList,
      #routeList {
        max-height: min(36dvh, 340px);
      }

      .rates-grid,
      .swarm-grid {
        grid-template-columns: minmax(0, 1fr);
      }
    }

    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }

    .route-detail > .detail-head {
      display: block;
      padding: 8px 10px;
      background: #fff;
    }

    .route-detail-head-main {
      min-width: 0;
      display: grid;
      gap: 5px;
    }

    .route-detail-title-line {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 10px;
      min-width: 0;
    }

    .route-detail-title-copy {
      min-width: 0;
      display: grid;
      gap: 2px;
    }

    .route-detail-title-line h2 {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .route-detail-status {
      flex: 0 0 auto;
    }

    .route-detail-head-tools {
      min-width: 0;
      display: flex;
      align-items: flex-start;
      justify-content: flex-end;
      flex-wrap: wrap;
      gap: 6px;
    }

    .route-header-rates {
      min-width: 0;
      display: flex;
      align-items: center;
      justify-content: flex-end;
      flex-wrap: wrap;
      gap: 5px;
    }

    .route-rate-chip.route-field {
      min-width: 0;
      min-height: 32px;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 2px 4px 2px 3px;
      border: 1px solid #dbe5f0;
      border-radius: 8px;
      background: #fff;
    }

    .route-rate-chip.changed {
      border-color: #e8c66b;
    }

    .route-rate-chip .route-encounter-badge {
      width: 26px;
      height: 26px;
      border-radius: 7px;
      flex: 0 0 auto;
    }

    .route-rate-chip .route-encounter-badge svg {
      width: 17px;
      height: 17px;
    }

    .route-rate-chip .route-input {
      width: 42px;
      height: 24px;
      margin-top: 0;
      padding: 0 2px;
      text-align: center;
      font-size: 12px;
      font-weight: 800;
      font-variant-numeric: tabular-nums;
    }

    .route-detail > .detail-head .meta {
      margin-top: 0;
      font-size: 12px;
      gap: 6px;
    }

    .route-detail-overview {
      min-width: 0;
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 6px;
      overflow: hidden;
    }

    .route-overview-pill {
      min-width: 0;
      min-height: 36px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid #dbe5f0;
      border-radius: 8px;
      background: #fff;
      padding: 3px 6px 3px 4px;
      flex: 0 1 auto;
    }

    .route-overview-pill.route-search-match-group {
      border-color: #f59e0b;
      background: #fffbeb;
      box-shadow: inset 0 0 0 1px rgba(245, 158, 11, 0.18);
    }

    .route-overview-pill.overview-grass {
      background: #f0fdf4;
      border-color: #b7dccc;
    }

    .route-overview-pill.overview-morning {
      background: var(--time-morning-bg);
      border-color: var(--time-morning-border);
    }

    .route-overview-pill.overview-day {
      background: var(--time-day-bg);
      border-color: var(--time-day-border);
    }

    .route-overview-pill.overview-night {
      background: var(--time-night-bg);
      border-color: var(--time-night-border);
    }

    .route-overview-pill.overview-surf,
    .route-overview-pill.overview-old-rod,
    .route-overview-pill.overview-good-rod,
    .route-overview-pill.overview-super-rod {
      background: #eff8ff;
      border-color: #c1ddf1;
    }

    .route-overview-pill.overview-rock-smash {
      background: #fffbeb;
      border-color: #d8d1c7;
    }

    .route-overview-pill.overview-headbutt-normal {
      background: #edf7ef;
      border-color: #0f5132;
    }

    .route-overview-pill.overview-headbutt-special {
      background: #e3f3e8;
      border-color: #064e3b;
    }

    .route-overview-pill.overview-hoenn,
    .route-overview-pill.overview-sinnoh {
      background: #f5f3ff;
      border-color: #cfc1fa;
    }

    .route-overview-pill.overview-swarms {
      background: #fff1f2;
      border-color: #f2bfd4;
    }

    .route-detail-overview .route-encounter-badge {
      width: 28px;
      height: 28px;
      border-radius: 7px;
    }

    .route-detail-overview .route-encounter-badge svg {
      width: 18px;
      height: 18px;
    }

    .route-overview-icons {
      min-width: 0;
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 3px;
    }

    .route-overview-icons .mon-icon {
      width: 28px;
      height: 28px;
      image-rendering: pixelated;
      object-fit: contain;
      flex: 0 0 auto;
    }

    .route-overview-icons .swap-mon-button,
    .route-encounter-mon-icons .swap-mon-button {
      width: 30px;
      height: 30px;
    }

    .route-overview-icons .swap-mon-button .mon-icon,
    .route-encounter-mon-icons .swap-mon-button .mon-icon {
      width: 28px;
      height: 28px;
    }

    .route-encounter-mon-icons .mon-icon {
      width: 24px;
      height: 24px;
    }

    .route-editor {
      padding: 8px;
      gap: 8px;
      background: #f8fafc;
    }

    .route-editor-layout {
      min-width: 0;
      min-height: 0;
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 8px;
      align-items: start;
    }

    .route-editor-primary,
    .route-editor-secondary {
      min-width: 0;
      display: grid;
      align-content: start;
      gap: 8px;
    }

    .route-compact-section .route-section-head {
      min-height: 32px;
      padding: 5px 8px;
    }

    .route-compact-section .route-section-title {
      font-size: 13px;
    }

    .route-compact-section .count {
      font-size: 12px;
    }

    .compact-rate-grid {
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 5px;
      padding: 6px;
      background: #fff;
    }

    .compact-rate-field.route-field {
      display: grid;
      grid-template-columns: 26px minmax(0, 1fr) 52px;
      align-items: center;
      gap: 5px;
      min-width: 0;
      padding: 3px 5px;
      border: 1px solid #dbe5f0;
      border-radius: 7px;
      background: #fff;
    }

    .compact-rate-field .route-encounter-badge {
      width: 24px;
      height: 24px;
      border-radius: 6px;
    }

    .compact-rate-field .rate-label {
      min-width: 0;
      color: var(--muted);
      font-size: 10px;
      font-weight: 800;
      overflow: hidden;
      text-overflow: ellipsis;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .compact-rate-field .route-input {
      height: 24px;
      margin-top: 0;
      padding: 0 4px;
      text-align: center;
      font-size: 12px;
    }

    .flat-editor-list {
      min-width: 0;
      display: grid;
      background: #fff;
    }

    .flat-encounter-row {
      position: relative;
      min-width: 0;
      display: grid;
      grid-template-columns: 44px 118px minmax(0, 1fr);
      align-items: center;
      gap: 7px;
      min-height: 38px;
      padding: 3px 6px;
      border-bottom: 1px solid var(--line);
      background: #fff;
      overflow: hidden;
    }

    .flat-encounter-row:last-child {
      border-bottom: 0;
    }

    .grass-editor-row::before {
      content: "";
      position: absolute;
      top: 0;
      left: 0;
      width: var(--grass-rate);
      height: 3px;
      background: #15803d;
      border-radius: 0 999px 999px 0;
    }

    .row-index {
      color: var(--muted);
      font-size: 16px;
      font-weight: 850;
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }

    .row-title {
      min-width: 0;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .compact-stats strong {
      font-size: 15px;
      line-height: 1;
      white-space: nowrap;
    }

    .compact-level-field.route-field {
      height: 26px;
      display: inline-grid;
      grid-template-columns: 18px 42px;
      align-items: center;
      gap: 2px;
      padding: 0 3px;
      border: 1px solid #dbe5f0;
      border-radius: 7px;
      background: #fff;
    }

    .compact-level-field > span {
      color: var(--muted);
      font-size: 10px;
      font-weight: 850;
      text-align: center;
    }

    .compact-level-field .route-input {
      height: 22px;
      margin-top: 0;
      padding: 0 2px;
      border: 0;
      background: transparent;
      text-align: center;
      font-size: 12px;
    }

    .row-groups {
      min-width: 0;
      display: flex;
      align-items: center;
      gap: 5px;
      overflow: hidden;
    }

    .grass-time-groups {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 5px;
      overflow: visible;
    }

    .compact-pill.route-field {
      min-width: 0;
      display: grid;
      grid-template-columns: 26px minmax(0, 1fr);
      align-items: center;
      gap: 4px;
      min-height: 30px;
      padding: 2px 4px;
      border: 1px solid #dbe5f0;
      border-radius: 8px;
      background: #fff;
    }

    .compact-pill.changed,
    .compact-rate-field.changed,
    .compact-level-field.changed {
      background: #fff8e6;
      border-color: #f2d486;
    }

    .compact-time-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }

    .compact-pill .route-encounter-badge {
      width: 24px;
      height: 24px;
      border-radius: 7px;
    }

    .compact-pill .route-encounter-badge svg {
      width: 16px;
      height: 16px;
    }

    .compact-species-control {
      min-width: 0;
      min-height: 26px;
      display: grid;
      grid-template-columns: 26px minmax(72px, 1fr) 32px;
      align-items: center;
      gap: 4px;
    }

    .compact-species-control .mon-icon {
      width: 26px;
      height: 26px;
      image-rendering: pixelated;
      object-fit: contain;
    }

    .compact-species-control .route-input {
      height: 24px;
      margin-top: 0;
      padding: 0 5px;
      font-size: 12px;
      font-weight: 850;
    }

    .compact-species-control .route-species-combo {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }

    .compact-species-control .route-form {
      width: 32px;
      padding: 0 2px;
      text-align: center;
    }

    .grass-time-cell .compact-species-control {
      grid-template-columns: 26px minmax(72px, 1fr) 32px;
      grid-template-areas: none;
    }

    .grass-time-cell .compact-species-control .mon-icon,
    .grass-time-cell .compact-species-control .route-species-combo {
      grid-area: auto;
    }

    .grass-time-cell .compact-species-control .mon-icon {
      width: 26px;
      height: 26px;
    }

    .grass-time-cell .compact-species-control .route-form {
      width: 32px;
      justify-self: auto;
    }

    .source-editor-list {
      gap: 0;
    }

    .source-editor-row {
      --source-rate: 0%;
      --source-accent: #0f766e;
    }

    .source-editor-row::before {
      content: "";
      position: absolute;
      top: 0;
      left: 0;
      width: var(--source-rate);
      height: 3px;
      background: var(--source-accent);
      border-radius: 0 999px 999px 0;
    }

    .source-surf,
    .source-old-rod,
    .source-good-rod,
    .source-super-rod {
      --source-accent: #0284c7;
    }

    .source-rock-smash {
      --source-accent: #b45309;
    }

    .source-headbutt-normal {
      --source-accent: #064e3b;
    }

    .source-headbutt-special {
      --source-accent: #022c22;
    }

    .source-hoenn,
    .source-sinnoh {
      --source-accent: #7c3aed;
    }

    .source-swarms {
      --source-accent: #db2777;
    }

    .source-row-title {
      display: grid;
      grid-template-columns: 26px minmax(42px, auto);
      justify-content: start;
    }

    .source-row-title.with-label {
      grid-template-columns: 26px minmax(56px, auto);
    }

    .source-row-title .route-encounter-badge {
      width: 26px;
      height: 26px;
      border-radius: 7px;
    }

    .source-row-title .route-encounter-badge svg {
      width: 17px;
      height: 17px;
    }

    .source-row-label {
      min-width: 0;
      overflow: hidden;
      color: var(--muted);
      font-size: 12px;
      font-weight: 850;
      text-overflow: ellipsis;
      text-transform: capitalize;
      white-space: nowrap;
    }

    .source-entry-groups {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      overflow: visible;
    }

    .source-entry-cell.route-field {
      min-width: 0;
      min-height: 30px;
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      align-items: center;
      gap: 5px;
      padding: 2px 4px;
      border: 1px solid #dbe5f0;
      border-radius: 8px;
      background: #fff;
    }

    .source-entry-cell.has-levels {
      grid-template-columns: minmax(0, 1fr) auto;
    }

    .source-surf .source-entry-cell,
    .source-old-rod .source-entry-cell,
    .source-good-rod .source-entry-cell,
    .source-super-rod .source-entry-cell {
      background: #eff8ff;
      border-color: #c1ddf1;
    }

    .source-rock-smash .source-entry-cell {
      background: #fffbeb;
      border-color: #d8d1c7;
    }

    .source-headbutt-normal .source-entry-cell {
      background: #edf7ef;
      border-color: #0f5132;
    }

    .source-headbutt-special .source-entry-cell {
      background: #e3f3e8;
      border-color: #064e3b;
    }

    .source-hoenn .source-entry-cell,
    .source-sinnoh .source-entry-cell {
      background: #f5f3ff;
      border-color: #cfc1fa;
    }

    .source-swarms .source-entry-cell {
      background: #fff1f2;
      border-color: #f2bfd4;
    }

    .source-entry-cell.changed {
      background: #fff8e6;
      border-color: #f2d486;
    }

    .value-chip {
      height: 18px;
      min-width: 0;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid #dbe5f0;
      border-radius: 6px;
      background: #fff;
      color: var(--muted);
      padding: 0 4px;
      font: 850 10px/1 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      white-space: nowrap;
    }

    .value-chip.slot {
      color: var(--ink);
    }

    .value-chip.pct {
      color: #0f766e;
    }

    .value-chip.source-label {
      min-width: 44px;
      color: var(--muted);
      text-transform: capitalize;
    }

    .source-level-controls {
      min-width: 0;
      display: inline-flex;
      align-items: center;
      gap: 2px;
    }

    .level-dash {
      color: var(--muted);
      font-size: 10px;
      font-weight: 850;
    }

    .compact-number-control {
      height: 22px;
      min-width: 0;
      display: inline-flex;
      align-items: center;
      gap: 2px;
      border: 1px solid #dbe5f0;
      border-radius: 6px;
      background: #fff;
      padding: 0 2px;
    }

    .compact-number-control > span:not(.sr-only) {
      min-width: 10px;
      color: var(--muted);
      font-size: 10px;
      font-weight: 850;
      text-align: center;
    }

    .compact-number-control .route-input {
      width: 30px;
      height: 20px;
      margin-top: 0;
      padding: 0 2px;
      border: 0;
      background: transparent;
      text-align: center;
      font-size: 12px;
    }

    .source-entry-cell .compact-species-control {
      grid-template-columns: 24px minmax(70px, 1fr) 28px;
    }

    .source-entry-cell .compact-species-control .mon-icon {
      width: 24px;
      height: 24px;
    }

    .source-entry-cell .compact-species-control .route-input {
      height: 22px;
      font-size: 11px;
    }

    .source-entry-cell .compact-species-control .route-form {
      width: 28px;
    }

    .encounter-summary-list {
      min-width: 0;
      display: grid;
      gap: 1px;
      background: var(--line);
    }

    .encounter-summary-row {
      min-width: 0;
      display: grid;
      grid-template-columns: minmax(108px, 132px) minmax(0, 1fr);
      align-items: center;
      gap: 6px;
      min-height: 42px;
      padding: 5px 6px;
      background: #fff;
    }

    .encounter-summary-source {
      min-width: 0;
      display: grid;
      grid-template-columns: 30px minmax(0, 1fr);
      align-items: center;
      gap: 6px;
    }

    .encounter-summary-source .route-encounter-badge {
      width: 28px;
      height: 28px;
      border-radius: 7px;
    }

    .encounter-summary-source .route-encounter-badge svg {
      width: 18px;
      height: 18px;
    }

    .encounter-summary-source-copy {
      min-width: 0;
      display: grid;
      gap: 1px;
    }

    .encounter-summary-title {
      min-width: 0;
      overflow: hidden;
      color: var(--ink);
      font-size: 12px;
      font-weight: 850;
      line-height: 1.05;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .encounter-summary-sub {
      color: var(--muted);
      font-size: 10px;
      font-weight: 750;
      line-height: 1.05;
      white-space: nowrap;
    }

    .encounter-summary-pokemon {
      --encounter-summary-min-width: 72px;
      min-width: 0;
      display: flex;
      align-items: stretch;
      align-content: flex-start;
      flex-wrap: nowrap;
      gap: 5px;
      overflow: hidden;
    }

    .encounter-summary-chip {
      --encounter-rate-width: 100%;
      --encounter-compact-width: var(--encounter-summary-min-width);
      flex: 0 1 clamp(var(--encounter-summary-min-width), var(--encounter-rate-width), 100%);
      width: clamp(var(--encounter-summary-min-width), var(--encounter-rate-width), 100%);
      min-width: 0;
      min-height: 46px;
      display: grid;
      grid-template-columns: 48px minmax(0, 1fr);
      align-items: stretch;
      gap: 6px;
      border: 1px solid #dbe5f0;
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      padding: 3px 7px 3px 4px;
      cursor: pointer;
      font: inherit;
      text-align: left;
      overflow: hidden;
      container: encounter-chip / inline-size;
    }

    .encounter-summary-chip:hover,
    .encounter-summary-chip:focus-visible {
      border-color: #99d6ca;
      box-shadow: 0 1px 5px rgb(15 23 42 / 10%);
      outline: 0;
    }

    .encounter-summary-chip.changed {
      background: #fff8e6;
      border-color: #f2d486;
    }

    .encounter-summary-chip.route-search-match {
      border-color: #f59e0b;
      background: #fffbeb;
      box-shadow: inset 0 0 0 1px rgba(245, 158, 11, 0.18);
    }

    .encounter-summary-chip.empty {
      color: var(--muted);
      border-style: dashed;
    }

    .encounter-summary-chip .mon-icon {
      width: 28px;
      height: 28px;
      image-rendering: pixelated;
      object-fit: contain;
    }

    .encounter-summary-chip .mon-icon:not(img) {
      width: 28px;
      height: 28px;
      border: 1px solid #dbe5f0;
      border-radius: 7px;
      background: #f8fafc;
    }

    .encounter-summary-meter {
      min-width: 0;
      min-height: 0;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      align-items: center;
      justify-items: center;
      gap: 1px;
      align-self: stretch;
    }

    .encounter-summary-body {
      min-width: 0;
      display: flex;
      align-items: center;
    }

    .encounter-summary-chip.rate-small,
    .encounter-summary-chip.rate-tiny {
      flex-basis: clamp(46px, var(--encounter-compact-width), 118px);
      width: clamp(46px, var(--encounter-compact-width), 118px);
      grid-template-columns: minmax(0, 1fr);
      justify-items: center;
      padding-inline: 3px;
    }

    .encounter-summary-chip.rate-small .encounter-summary-body,
    .encounter-summary-chip.rate-tiny .encounter-summary-body {
      display: none;
    }

    .encounter-summary-name {
      min-width: 0;
      max-width: 128px;
      overflow: hidden;
      font-size: 12px;
      font-weight: 850;
      line-height: 1.05;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .encounter-summary-species-input {
      width: 100%;
      min-width: 0;
      height: 26px;
      border: 1px solid transparent;
      border-radius: 6px;
      background: transparent;
      color: var(--ink);
      padding: 0 4px;
      font: 850 12px/1 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      text-transform: uppercase;
      overflow: hidden;
      text-overflow: ellipsis;
      cursor: text;
    }

    .encounter-summary-species-input:hover {
      border-color: #dbe5f0;
      background: #fff;
    }

    .encounter-summary-species-input:focus {
      border-color: #99d6ca;
      background: #fff;
      outline: 2px solid rgb(153 214 202 / 35%);
    }

    .encounter-summary-species-input.invalid {
      border-color: #dc2626;
      background: #fff1f2;
    }

    .encounter-summary-rate {
      min-width: 0;
      height: auto;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 0;
      border-radius: 0;
      background: transparent;
      color: #0f766e;
      padding: 0;
      font: 900 10px/1 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      white-space: nowrap;
    }

    .encounter-summary-levels {
      min-width: 0;
      overflow: hidden;
      color: var(--muted);
      font-size: 9px;
      font-weight: 850;
      line-height: 1;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    @container encounter-chip (max-width: 124px) {
      .encounter-summary-species-input {
        display: none;
      }

      .encounter-summary-body {
        display: none;
      }

    }

    .encounter-summary-row.summary-grass {
      background: #f7fdf9;
    }

    .encounter-summary-row.summary-morning {
      background: var(--time-morning-bg);
      box-shadow: inset 3px 0 0 var(--time-morning-accent);
    }

    .encounter-summary-row.summary-day {
      background: var(--time-day-bg);
      box-shadow: inset 3px 0 0 var(--time-day-accent);
    }

    .encounter-summary-row.summary-night {
      background: var(--time-night-bg);
      box-shadow: inset 3px 0 0 var(--time-night-accent);
    }

    .encounter-summary-row.summary-surf,
    .encounter-summary-row.summary-old-rod,
    .encounter-summary-row.summary-good-rod,
    .encounter-summary-row.summary-super-rod {
      background: #f4fbff;
    }

    .encounter-summary-row.summary-rock-smash {
      background: #fffdf4;
    }

    .encounter-summary-row.summary-headbutt-normal {
      background: #edf7ef;
    }

    .encounter-summary-row.summary-headbutt-special {
      background: #e3f3e8;
    }

    .encounter-summary-row.summary-hoenn,
    .encounter-summary-row.summary-sinnoh {
      background: #faf7ff;
    }

    .encounter-summary-row.summary-swarms {
      background: #fff7fa;
    }

    .encounter-summary-empty {
      color: var(--muted);
      font-size: 12px;
      font-weight: 750;
    }

    .route-swap-dialog {
      width: min(640px, calc(100vw - 24px));
      max-height: min(86dvh, 760px);
      border: 1px solid var(--line);
      border-radius: 10px;
      background: #fff;
      color: var(--ink);
      padding: 0;
      box-shadow: 0 18px 48px rgba(15, 23, 42, 0.22);
    }

    .route-swap-dialog::backdrop {
      background: rgba(15, 23, 42, 0.18);
    }

    .route-swap-card {
      display: grid;
      gap: 10px;
      padding: 12px;
      max-height: inherit;
      overflow: hidden;
    }

    .route-swap-head {
      display: grid;
      grid-template-columns: 40px minmax(0, 1fr);
      gap: 8px;
      align-items: center;
    }

    .route-swap-head .mon-icon {
      width: 38px;
      height: 38px;
      image-rendering: pixelated;
      object-fit: contain;
    }

    .route-swap-title {
      min-width: 0;
      display: grid;
      gap: 2px;
    }

    .route-swap-title strong {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .route-swap-title span,
    .route-swap-help,
    .route-swap-error {
      color: var(--muted);
      font-size: 12px;
    }

    .route-swap-field {
      display: grid;
      gap: 4px;
    }

    .route-swap-field span {
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: .02em;
      text-transform: uppercase;
    }

    .route-swap-input {
      width: 100%;
      height: 34px;
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 0 9px;
      color: var(--ink);
      font-weight: 750;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }

    .route-swap-input.invalid {
      border-color: #dc2626;
      background: #fff1f2;
    }

    .route-swap-actions {
      display: flex;
      justify-content: flex-end;
      gap: 6px;
    }

    .route-swap-actions .control {
      width: auto;
      min-width: 78px;
    }

    .route-swap-actions .highlight-action {
      border-color: #99d6ca;
      background: #ecfdf5;
      color: #0f766e;
    }

    .route-swap-error {
      min-height: 16px;
      color: #b91c1c;
    }

    .route-swap-entries {
      min-height: 0;
      max-height: min(42dvh, 360px);
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }

    .route-swap-entry {
      min-width: 0;
      display: grid;
      grid-template-columns: 28px 70px minmax(0, 1fr);
      gap: 6px;
      align-items: center;
      padding: 4px 6px;
      border-bottom: 1px solid var(--line);
      background: #fff;
      box-shadow: inset 3px 0 0 transparent;
    }

    .route-swap-entry:last-child {
      border-bottom: 0;
    }

    .route-swap-entry.source-grass {
      background: #f4fdf8;
      box-shadow: inset 3px 0 0 #22c55e;
    }

    .route-swap-entry.source-morning {
      background: var(--time-morning-bg);
      box-shadow: inset 3px 0 0 var(--time-morning-accent);
    }

    .route-swap-entry.source-day {
      background: var(--time-day-bg);
      box-shadow: inset 3px 0 0 var(--time-day-accent);
    }

    .route-swap-entry.source-night {
      background: var(--time-night-bg);
      box-shadow: inset 3px 0 0 var(--time-night-accent);
    }

    .route-swap-entry.highlighted {
      outline: 2px solid #0f766e;
      outline-offset: -2px;
      background-image: linear-gradient(90deg, rgba(15, 118, 110, .12), rgba(15, 118, 110, 0));
    }

    .route-swap-entry.source-surf,
    .route-swap-entry.source-oldRod,
    .route-swap-entry.source-goodRod,
    .route-swap-entry.source-superRod {
      background: #eff9ff;
      box-shadow: inset 3px 0 0 #38bdf8;
    }

    .route-swap-entry.source-rockSmash {
      background: #fffaf0;
      box-shadow: inset 3px 0 0 #d97706;
    }

    .route-swap-entry.source-headbuttNormal {
      background: #edf7ef;
      box-shadow: inset 3px 0 0 #064e3b;
    }

    .route-swap-entry.source-headbuttSpecial {
      background: #e3f3e8;
      box-shadow: inset 3px 0 0 #022c22;
    }

    .route-swap-entry.source-hoenn,
    .route-swap-entry.source-sinnoh {
      background: #faf5ff;
      box-shadow: inset 3px 0 0 #a855f7;
    }

    .route-swap-entry.source-swarms {
      background: #fff1f4;
      box-shadow: inset 3px 0 0 #f43f5e;
    }

    .route-swap-entry-source {
      min-width: 0;
      display: flex;
      justify-content: center;
      align-items: center;
    }

    .route-swap-entry-source .route-encounter-badge {
      width: 24px;
      height: 24px;
      border-radius: 7px;
    }

    .route-swap-entry-source .route-encounter-badge svg {
      width: 16px;
      height: 16px;
    }

    .route-swap-entry-meta {
      min-width: 0;
      display: grid;
      gap: 2px;
    }

    .route-swap-entry-meta strong {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 13px;
    }

    .route-swap-entry-meta span {
      color: var(--muted);
      font-size: 11px;
      font-weight: 750;
      white-space: nowrap;
    }

    .route-swap-entry-control {
      min-width: 0;
      display: grid;
      grid-template-columns: 30px minmax(0, 1fr) auto;
      gap: 6px;
      align-items: center;
    }

    .route-swap-entry-control .mon-icon {
      width: 30px;
      height: 30px;
      image-rendering: pixelated;
      object-fit: contain;
    }

    .route-swap-entry-input {
      width: 100%;
      height: 30px;
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 0 7px;
      color: var(--ink);
      font-weight: 750;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    }

    .route-swap-entry-input.invalid {
      border-color: #dc2626;
      background: #fff1f2;
    }

    .route-swap-levels {
      min-width: 0;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }

    .route-swap-level-field {
      height: 30px;
      min-width: 0;
      display: inline-grid;
      grid-template-columns: auto 42px;
      align-items: center;
      gap: 3px;
      border: 1px solid #dbe5f0;
      border-radius: 7px;
      background: #fff;
      padding: 0 4px;
    }

    .route-swap-level-field > span {
      color: var(--muted);
      font-size: 10px;
      font-weight: 850;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .route-swap-level-input {
      width: 42px;
      height: 24px;
      border: 0;
      background: transparent;
      color: var(--ink);
      padding: 0 2px;
      text-align: center;
      font-weight: 850;
      font-variant-numeric: tabular-nums;
    }

    .route-swap-level-input.invalid {
      color: #b91c1c;
      background: #fff1f2;
      border-radius: 5px;
    }

    @media (min-width: 1800px) {
      .route-editor-layout {
        grid-template-columns: minmax(700px, 1.25fr) minmax(420px, .75fr);
      }
    }

    @media (max-width: 1320px) {
      .compact-rate-grid {
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
    }

    @media (max-width: 760px) {
      .route-detail > .detail-head {
        padding: 8px;
      }

      .route-detail-title-line h2 {
        font-size: 18px;
      }

      .route-detail-title-line {
        flex-wrap: wrap;
      }

      .route-detail-head-tools {
        width: 100%;
        justify-content: flex-start;
      }

      .route-header-rates {
        flex: 1 1 100%;
        justify-content: flex-start;
        flex-wrap: nowrap;
        overflow-x: auto;
        padding-bottom: 2px;
        overscroll-behavior-x: contain;
      }

      .route-rate-chip.route-field {
        flex: 0 0 auto;
      }

      .route-detail-overview {
        flex-wrap: nowrap;
        overflow-x: auto;
        padding-bottom: 2px;
        overscroll-behavior-x: contain;
      }

      .route-overview-pill {
        flex: 0 0 auto;
      }

      .compact-rate-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .flat-encounter-row {
        grid-template-columns: 38px minmax(0, 1fr);
        gap: 5px;
        padding: 5px;
      }

      .row-groups {
        grid-column: 1 / -1;
      }

      .grass-time-groups {
        grid-template-columns: minmax(0, 1fr);
      }

      .source-entry-cell.has-levels {
        grid-template-columns: minmax(0, 1fr);
      }

      .source-entry-cell.has-levels .source-level-controls {
        padding-left: 28px;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div class="bar primary-bar">
        <div class="title">Overworld Wild Tools</div>
        <nav class="workspace-tabs" aria-label="Editor tabs">
          <button class="workspace-tab active" data-view="profiles" type="button">Overworld Behaviour Profiles</button>
          <button class="workspace-tab" data-view="encounters" type="button">Route Encounters</button>
        </nav>
        <div id="source" class="source"></div>
      </div>
      <div id="profileControls" class="bar header-controls">
        <input id="search" class="control" type="search" placeholder="Search profile, class, Pokemon, rule">
        <select id="classFilter" class="control"></select>
        <button id="refresh" class="control" type="button">Refresh</button>
      </div>
      <div id="globalActions" class="bar global-actions">
        <div class="action-groups">
          <div class="action-group">
            <button id="saveAllChanges" class="control primary-action" type="button" title="Save changes">
              <span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z"/><path d="M17 21v-8H7v8"/><path d="M7 3v5h8"/></svg></span>
              <span>Save</span>
            </button>
            <label class="switch-control">
              <input id="buildAfterSave" type="checkbox">
              <span class="switch-track" aria-hidden="true"></span>
              <span class="switch-label">Auto build</span>
            </label>
          </div>
          <div class="action-group">
            <button id="buildRom" class="control" type="button" title="Build ROM">
              <span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 12-8.5 8.5a2.1 2.1 0 0 1-3-3L12 9"/><path d="m17.6 15.6 3-3a2.1 2.1 0 0 0 0-3L14.5 3.5l-3 3 6.1 6.1"/><path d="m7.5 14.5 2 2"/></svg></span>
              <span>Build</span>
            </button>
            <button id="openTestNds" class="control" type="button" title="Open test.nds">
              <span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v2"/><path d="M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-6H8l-2 2H3"/></svg></span>
              <span>Open NDS</span>
            </button>
            <label class="switch-control">
              <input id="runTestAfterBuild" type="checkbox">
              <span class="switch-track" aria-hidden="true"></span>
              <span class="switch-label">Auto run</span>
            </label>
            <label class="switch-control" title="Show terminal output automatically during builds">
              <input id="showBuildOutput" type="checkbox">
              <span class="switch-track" aria-hidden="true"></span>
              <span class="switch-label">Show log</span>
            </label>
          </div>
          <div class="action-group shiny-counter-group" title="Debug saved shiny spawn counter in test.dsv">
            <span class="shiny-counter-pill">
              <span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.6 5.1L19 10l-5.4 1.9L12 17l-1.6-5.1L5 10l5.4-1.9L12 3Z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z"/><path d="M5 15l.6 1.6L7 17l-1.4.4L5 19l-.6-1.6L3 17l1.4-.4L5 15Z"/></svg></span>
              <span id="shinyCounterValue">--</span>
              <span id="shinyCounterRate" class="muted">1/8192</span>
            </span>
            <button id="refreshShinyCounter" class="control" type="button" title="Refresh shiny counter" aria-label="Refresh shiny counter">
              <span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 3v6h6"/></svg></span>
            </button>
            <button id="resetShinyCounter" class="control" type="button" title="Set shiny counter to 0">0</button>
            <button id="maxShinyCounter" class="control" type="button" title="Set shiny counter to 8191 so the next eligible spawn is shiny">8191</button>
          </div>
        </div>
        <span id="saveStatus" class="save-status"></span>
        <button id="resetAllEdits" class="control subtle-action" type="button" title="Reset unsaved edits">
          <span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 3v6h6"/></svg></span>
          <span>Reset</span>
        </button>
      </div>
      <div id="buildOutputPanel" class="build-output-panel" hidden>
        <div class="build-output-head">
          <div class="build-output-title">
            <span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m7 8 4 4-4 4"/><path d="M13 16h4"/><rect x="3" y="4" width="18" height="16" rx="2"/></svg></span>
            <span>Build output</span>
            <span id="buildTimer" class="build-timer">0:00</span>
          </div>
          <button id="closeBuildOutput" class="build-output-close" type="button" aria-label="Hide build output" title="Hide build output">x</button>
        </div>
        <pre id="buildOutput" class="build-log"></pre>
      </div>
    </header>
    <main id="profilesView" class="view active">
      <section class="pane">
        <div class="pane-head">
          <div class="pane-title">Profiles</div>
          <div id="speciesCount" class="count"></div>
        </div>
        <div id="speciesList" class="scroll"></div>
      </section>
      <section class="pane detail">
        <div id="detailHead" class="detail-head"></div>
        <div class="tabs">
          <button class="tab active" data-tab="profiles" type="button">Profiles</button>
          <button class="tab" data-tab="selected" type="button">Selected</button>
          <button class="tab" data-tab="rules" type="button">Rule Order</button>
        </div>
        <div id="profilesTab" class="tab-panel active"></div>
        <div id="selectedTab" class="tab-panel"></div>
        <div id="rulesTab" class="tab-panel"></div>
      </section>
    </main>
    <main id="encountersView" class="view">
      <section class="pane">
        <div class="pane-head route-pane-head">
          <div class="pane-title">Routes</div>
          <div id="routeGlobalSettings" class="route-global-settings" aria-label="Global overworld spawn settings"></div>
          <div id="routeCount" class="count"></div>
        </div>
        <div class="route-search">
          <div id="routeSpawnTypeFilters" class="route-spawn-filters" aria-label="Spawn type filters"></div>
          <input id="routeSearch" class="control" type="search" placeholder="Search route, map, Pokemon, type">
        </div>
        <div id="routeList" class="scroll"></div>
      </section>
      <section class="pane route-detail">
        <div id="routeDetailHead" class="detail-head"></div>
        <div id="routeSpeciesDatalistHost"></div>
        <div id="routeEditor" class="route-editor scroll"></div>
      </section>
    </main>
  </div>
  <div id="profileAddMenu" class="profile-add-menu" hidden></div>
  <div id="profileComboMenu" class="profile-combo-menu" hidden></div>
  <dialog id="routeSwapDialog" class="route-swap-dialog"></dialog>
  <dialog id="spawnSettingDialog" class="spawn-setting-dialog"></dialog>

  <script>
    let appData = null;
    let activeView = localStorage.getItem("owWorkspaceView") || "profiles";
    if (!["profiles", "encounters"].includes(activeView)) activeView = "profiles";
    let selectedSymbol = null;
    let selectedClassIndex = null;
    let selectedRouteId = null;
    let activeTab = "profiles";
    let hasLoadedData = false;
    let dataLoadGeneration = 0;
    let dataLoadAbortController = null;
    let visibleSpeciesLimit = 160;
    let filterRenderFrame = null;
    let routeFilterRenderFrame = null;
    let routeEditorRenderFrame = null;
    let routeEditStatusFrame = null;
    let routeEditStatusNeedsHeadRender = false;
    let globalEditStatusFrame = null;
    let routeMarkerFrame = null;
    let pendingRouteMarkerIds = new Set();
    let assignmentsBySymbol = new Map();
    let profileAssignmentsByClass = new Map();
    let routesById = new Map();
    let spawnSettingsBySymbol = new Map();
    let routeSpeciesBySymbol = new Map();
    let routeSpeciesByName = new Map();
    let routeSpeciesByCompactName = new Map();
    let routeSpeciesByBaseForm = new Map();
    let profileSpeciesBySymbol = new Map();
    let profileSpeciesByName = new Map();
    let profileSpeciesByCompactName = new Map();
    let profileOptionLookupByField = new Map();
    let visibleSpeciesRowsBySymbol = new Map();
    let visibleProfileRowsByClass = new Map();
    let profileIconButtonsBySymbol = new Map();
    let invalidProfileInputs = new Set();
    let invalidEncounterInputs = new Set();
    let invalidSpawnSettingInputs = new Set();
    let profileDatalistsHtml = "";
    let profileSpeciesDatalistHtml = "";
    let routeSpeciesDatalistHtml = "";
    let routeSpeciesDatalistRendered = false;
    let renderedProfilePanels = new Set();
    let dirtyProfilePanels = new Set(["profiles", "selected", "rules"]);
    let profileEdits = new Map();
    let profileMemberEdits = new Map();
    let profileQuickAddClassIndex = null;
    let profileBulkType = localStorage.getItem("owProfileBulkType") || "";
    let profileOverrideEdits = [];
    let profileOverrideRemoveEdits = new Set();
    let profileOverrideDraftTargetKind = localStorage.getItem("owProfileOverrideTargetKind") || "type";
    let profileOverrideDraftType = localStorage.getItem("owProfileOverrideType") || "TYPE_FLYING";
    let profileOverrideDraftSpawnPool = localStorage.getItem("owProfileOverrideSpawnPool") || "OW_WILD_SPAWN_TERRAIN_LAND";
    let profileOverrideDraftField = localStorage.getItem("owProfileOverrideField") || "spawnState";
    let profileOverrideDraftRaw = localStorage.getItem("owProfileOverrideRaw") || "";
    let activeProfileComboInput = null;
    let profileComboMenuIndex = 0;
    let encounterEdits = new Map();
    let spawnSettingEdits = new Map();
    let encounterSummaryTargetsById = new Map();
    let encounterSummaryTargetSequence = 0;
    let pendingRouteIds = new Set();
    let routeSwapState = null;
    const ROUTE_COLLAPSE_STORAGE_KEY = "owRouteCollapsedSections";
    const ROUTE_SPAWN_FILTER_STORAGE_KEY = "owRouteSpawnTypeFilters";
    const ROUTE_GRASS_FILTER_MIGRATION_KEY = "owRouteSpawnTypeFiltersGrassMigrated";
    const ROUTE_HEADBUTT_FILTER_MIGRATION_KEY = "owRouteSpawnTypeFiltersHeadbuttMigrated";
    const ROUTE_SPAWN_FILTERS = [
      { key: "grass", label: "Grass", defaultOn: true },
      { key: "morning", label: "Grass AM", defaultOn: true },
      { key: "day", label: "Grass Day", defaultOn: true },
      { key: "night", label: "Grass Night", defaultOn: true },
      { key: "surf", label: "Surf", defaultOn: true },
      { key: "rockSmash", label: "Rock smash", defaultOn: true },
      { key: "headbuttNormal", label: "Headbutt", defaultOn: true },
      { key: "headbuttSpecial", label: "Special trees", defaultOn: true },
      { key: "oldRod", label: "Old rod", defaultOn: true },
      { key: "goodRod", label: "Good rod", defaultOn: true },
      { key: "superRod", label: "Super rod", defaultOn: true },
      { key: "hoenn", label: "Hoenn sound", defaultOn: false },
      { key: "sinnoh", label: "Sinnoh sound", defaultOn: false },
      { key: "swarms", label: "Swarms", defaultOn: false },
    ];
    const PROFILE_OVERRIDE_TARGET_KINDS = [
      { key: "type", label: "Type" },
      { key: "spawnPool", label: "Spawn pool" },
    ];
    const PROFILE_OVERRIDE_SPAWN_POOLS = [
      { key: "land", label: "Land", raw: "OW_WILD_SPAWN_TERRAIN_LAND", icon: "leaf", typeClass: "type-grass", routeGroups: ["grass", "morning", "day", "night", "hoenn", "sinnoh", "swarms"] },
      { key: "surf", label: "Surf", raw: "OW_WILD_SPAWN_TERRAIN_SURF", icon: "waves", typeClass: "type-surf", routeGroups: ["surf"] },
      { key: "fish", label: "Fish", raw: "OW_WILD_SPAWN_TERRAIN_FISHING", icon: "fish", typeClass: "type-rod", routeGroups: ["oldRod", "goodRod", "superRod"] },
      { key: "headbutt", label: "Headbutt", raw: "OW_WILD_SPAWN_TERRAIN_HEADBUTT", icon: "tree", typeClass: "type-headbutt", routeGroups: ["headbuttNormal", "headbuttSpecial"] },
    ];
    const ROUTE_SPAWN_FILTER_KEYS = new Set(ROUTE_SPAWN_FILTERS.map(filter => filter.key));
    const ALERT_RANGE_TYPE_FIELD = "alertRangeType";
    const SPAWN_DESTINATION_TYPE_FIELD = "spawnDestinationType";
    const SPAWN_DESTINATION_FRONT_TYPE = "__SPAWN_DESTINATION_FRONT_OF_PLAYER";
    const SPAWN_DESTINATION_BEHIND_TYPE = "__SPAWN_DESTINATION_BEHIND_PLAYER";
    const SPAWN_DESTINATION_NEXT_TO_PLAYER_RAW = "OW_WILD_SPAWN_DESTINATION_NEXT_TO_PLAYER";
    const NUMERIC_PROFILE_FIELD_KEYS = new Set([
      "alertTime",
      "alertness",
      "stamina",
      "restTime",
      "chillSpeed",
      "attentiveSpeed",
      "tiredSpeed",
      "range",
      "chillCooldown",
      "attentiveCooldown",
      "alertChance",
      "hopMinDistance",
      "hopMaxDistance",
      "hopPause",
      "teleportTime",
      "teleportPause",
      "attentiveHopMinDistance",
      "attentiveHopMaxDistance",
      "attentiveHopPause",
      "attentiveTeleportTime",
      "attentiveTeleportPause",
      "attentiveRamAccelerationSteps",
      "attentiveRamMaxSpeed",
      "tiredHopMinDistance",
      "tiredHopMaxDistance",
      "tiredHopPause",
      "tiredTeleportTime",
      "tiredTeleportPause",
      "tiredRamAccelerationSteps",
      "tiredRamMaxSpeed",
      "alertCallSpawnAmount",
      "spawnDestinationMinDistance",
      "spawnDestinationMaxDistance",
      "ramAccelerationSteps",
      "ramMaxSpeed",
    ]);
    const PROFILE_FIELD_HINTS = {
      profileId: "Special behavior-family flag used by profile-specific runtime logic. Most profiles can leave this as Default.",
      chillAllowedTile: "Tile type this Chill behavior may target.",
      attentiveAllowedTile: "Tile type this Active behavior may target.",
      tiredAllowedTile: "Tile type this Tired behavior may target.",
      chillAllowedTile2: "Optional second tile type this Chill behavior may target.",
      attentiveAllowedTile2: "Optional second tile type this Active behavior may target.",
      tiredAllowedTile2: "Optional second tile type this Tired behavior may target.",
    };
    const PROFILE_DIRECT_EDIT_HIDDEN_FIELDS = new Set(["attentiveAction"]);
    const PROFILE_OVERRIDE_BUILDER_HIDDEN_FIELDS = new Set([
      "attentiveAction",
    ]);
    const PROFILE_BEHAVIOR_FIELDS = new Set(["chillState", "attentiveState", "tiredState"]);
    const PROFILE_MOVEMENT_FIELDS = new Set(["chillAction", "movementStyle", "specialAction"]);
    const PROFILE_TARGET_SELECTOR_RAWS = [
      "OW_WILD_BEHAVIOR_TARGET_NONE",
      "OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY",
      "OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER",
      "OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER",
      "OW_WILD_BEHAVIOR_TARGET_TREE_TOP",
      "OW_WILD_BEHAVIOR_TARGET_PLAYFUL_ORBIT",
      "OW_WILD_BEHAVIOR_TARGET_PLAYER_FRONT",
      "OW_WILD_BEHAVIOR_TARGET_SWARM",
    ];
    const PROFILE_FIELD_GROUPS = [
      {
        key: "spawn",
        label: "Spawn",
        icon: "footstep",
        typeClass: "type-movement",
        fields: ["spawnState", "spawnDestination", "spawnDestinationMinDistance", "spawnDestinationMaxDistance", "jumpLevel"],
      },
      {
        key: "chill",
        label: "Chill",
        icon: "leaf",
        typeClass: "type-grass",
        fields: [
          "chillState",
          "chillTarget",
          "chillAction",
          "chillSpeed",
          "chillAllowedTile",
          "chillAllowedTile2",
          "hopAllowNonCardinal",
          "hopMinDistance",
          "hopMaxDistance",
          "hopPause",
          "teleportTime",
          "teleportPause",
          "ramAccelerationSteps",
          "ramMaxSpeed",
          "chillCooldown",
        ],
      },
      {
        key: "alert",
        label: "Alert",
        icon: "target",
        typeClass: "type-placement",
        fields: [
          "alertState",
          "alertEmote",
          "alertTime",
          "alertRange",
          "alertness",
          "alertChance",
          "alertSpecialAction",
          "alertCallSpawnAmount",
          "alertCallSpawnState",
        ],
      },
      {
        key: "attentive",
        label: "Active",
        icon: "footstep",
        typeClass: "type-movement",
        fields: [
          "attentiveState",
          "movementStyle",
          "attentiveSpeed",
          "attentiveAllowedTile",
          "attentiveAllowedTile2",
          "attentiveHopAllowNonCardinal",
          "attentiveHopMinDistance",
          "attentiveHopMaxDistance",
          "attentiveHopPause",
          "attentiveTeleportTime",
          "attentiveTeleportPause",
          "attentiveRamAccelerationSteps",
          "attentiveRamMaxSpeed",
          "targetSelector",
          "attentiveCooldown",
        ],
      },
      {
        key: "battle",
        label: "Battle",
        icon: "swords",
        typeClass: "type-test",
        fields: ["chillBattle", "alertBattle", "attentiveBattle", "tiredBattle"],
      },
      {
        key: "tired",
        label: "Tired",
        icon: "clock",
        typeClass: "type-flow",
        fields: [
          "tiredState",
          "specialAction",
          "tiredSpeed",
          "tiredAllowedTile",
          "tiredAllowedTile2",
          "tiredHopAllowNonCardinal",
          "tiredHopMinDistance",
          "tiredHopMaxDistance",
          "tiredHopPause",
          "tiredTeleportTime",
          "tiredTeleportPause",
          "tiredRamAccelerationSteps",
          "tiredRamMaxSpeed",
          "restTime",
          "stamina",
        ],
      },
      {
        key: "stats",
        label: "Stats",
        icon: "speed",
        typeClass: "type-flow",
        fields: ["range"],
      },
      {
        key: "special",
        label: "Special",
        icon: "shield",
        typeClass: "type-test",
        fields: ["profileId"],
      },
    ];
    const PRIMITIVE_GROUPS = [
      { key: "spawn", label: "Spawn", icon: "footstep", typeClass: "type-movement", fields: ["spawnLocomotion"] },
      { key: "chill", label: "Chill", icon: "leaf", typeClass: "type-grass", fields: ["chillLocomotion", "chillTarget"] },
      { key: "alert", label: "Alert", icon: "target", typeClass: "type-placement", fields: ["alertLogic", "alertReaction"] },
      { key: "active", label: "Active", icon: "bolt", typeClass: "type-flow", fields: ["attentiveLocomotion", "attentiveTarget", "activeReaction", "tiredReaction"] },
    ];
    let collapsedSections = readCollapsedSections();
    let routeSpawnTypeFilters = readRouteSpawnTypeFilters();
    let isSavingProfiles = false;
    let isSavingProfileMemberships = false;
    let isSavingProfileOverrides = false;
    let isSavingEncounters = false;
    let isSavingSpawnSettings = false;
    let isManagingProfiles = false;
    let isBuilding = false;
    let isSettingShinyCounter = false;
    let buildAfterSave = localStorage.getItem("owProfileBuildAfterSave") === "1";
    let runTestNdsAfterBuild = localStorage.getItem("owProfileRunTestAfterBuild") === "1";
    let autoShowBuildOutput = localStorage.getItem("owProfileAutoShowBuildOutput") !== "0";
    let buildPollTimer = null;
    let buildOutputManuallyHidden = false;
    const LIST_PAGE_SIZE = 160;

    const els = {
      source: document.getElementById("source"),
      profileControls: document.getElementById("profileControls"),
      search: document.getElementById("search"),
      classFilter: document.getElementById("classFilter"),
      refresh: document.getElementById("refresh"),
      speciesCount: document.getElementById("speciesCount"),
      speciesList: document.getElementById("speciesList"),
      detailHead: document.getElementById("detailHead"),
      profilesTab: document.getElementById("profilesTab"),
      selectedTab: document.getElementById("selectedTab"),
      rulesTab: document.getElementById("rulesTab"),
      profilesView: document.getElementById("profilesView"),
      encountersView: document.getElementById("encountersView"),
      routeSearch: document.getElementById("routeSearch"),
      routeSpawnTypeFilters: document.getElementById("routeSpawnTypeFilters"),
      routeCount: document.getElementById("routeCount"),
      routeList: document.getElementById("routeList"),
      routeGlobalSettings: document.getElementById("routeGlobalSettings"),
      routeDetailHead: document.getElementById("routeDetailHead"),
      routeSpeciesDatalistHost: document.getElementById("routeSpeciesDatalistHost"),
      routeEditor: document.getElementById("routeEditor"),
      saveAllChanges: document.getElementById("saveAllChanges"),
      buildAfterSave: document.getElementById("buildAfterSave"),
      buildRom: document.getElementById("buildRom"),
      openTestNds: document.getElementById("openTestNds"),
      runTestAfterBuild: document.getElementById("runTestAfterBuild"),
      showBuildOutput: document.getElementById("showBuildOutput"),
      shinyCounterValue: document.getElementById("shinyCounterValue"),
      shinyCounterRate: document.getElementById("shinyCounterRate"),
      refreshShinyCounter: document.getElementById("refreshShinyCounter"),
      resetShinyCounter: document.getElementById("resetShinyCounter"),
      maxShinyCounter: document.getElementById("maxShinyCounter"),
      resetAllEdits: document.getElementById("resetAllEdits"),
      saveStatus: document.getElementById("saveStatus"),
      buildOutputPanel: document.getElementById("buildOutputPanel"),
      buildOutput: document.getElementById("buildOutput"),
      buildTimer: document.getElementById("buildTimer"),
      closeBuildOutput: document.getElementById("closeBuildOutput"),
      profileAddMenu: document.getElementById("profileAddMenu"),
      profileComboMenu: document.getElementById("profileComboMenu"),
      routeSwapDialog: document.getElementById("routeSwapDialog"),
      spawnSettingDialog: document.getElementById("spawnSettingDialog")
    };

    els.buildAfterSave.checked = buildAfterSave;
    els.runTestAfterBuild.checked = runTestNdsAfterBuild;
    els.showBuildOutput.checked = autoShowBuildOutput;

    function esc(value) {
      return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      })[char]);
    }

    function readCollapsedSections() {
      try {
        const stored = localStorage.getItem(ROUTE_COLLAPSE_STORAGE_KEY);
        if (!stored) return new Set(["spawn-settings"]);
        const parsed = JSON.parse(stored || "[]");
        return new Set(Array.isArray(parsed) ? parsed : []);
      } catch (error) {
        return new Set(["spawn-settings"]);
      }
    }

    function saveCollapsedSections() {
      localStorage.setItem(ROUTE_COLLAPSE_STORAGE_KEY, JSON.stringify([...collapsedSections].sort()));
    }

    function collapseOpenAttr(key) {
      return collapsedSections.has(key) ? "" : " open";
    }

    function collapsibleSummary(title, metaHtml = "", headClass = "route-section-head", titleClass = "route-section-title") {
      return `
        <summary class="${headClass} collapsible-head">
          <span class="collapsible-title">
            <span class="collapse-caret" aria-hidden="true"></span>
            <span class="${titleClass}">${esc(title)}</span>
          </span>
          ${metaHtml}
        </summary>
      `;
    }

    function collapsibleButtonSummary(title, metaHtml = "", expanded = true, headClass = "route-section-head", titleClass = "route-section-title") {
      return `
        <button class="${headClass} collapsible-head collapsible-button" type="button" data-collapse-toggle aria-expanded="${expanded ? "true" : "false"}">
          <span class="collapsible-title">
            <span class="collapse-caret" aria-hidden="true"></span>
            <span class="${titleClass}">${esc(title)}</span>
          </span>
          ${metaHtml}
        </button>
      `;
    }

    function collapsibleRouteSection(key, title, metaHtml, bodyHtml, extraClass = "") {
      const classes = ["route-section", "collapsible-section", extraClass].filter(Boolean).join(" ");
      return `
        <details class="${esc(classes)}" data-collapse-key="${esc(key)}"${collapseOpenAttr(key)}>
          ${collapsibleSummary(title, metaHtml)}
          <div class="collapsible-body">${bodyHtml}</div>
        </details>
      `;
    }

    function customCollapsibleRouteSection(key, title, metaHtml, bodyHtml, extraClass = "") {
      const collapsed = collapsedSections.has(key);
      const classes = ["route-section", "collapsible-section", collapsed ? "is-collapsed" : "is-open", extraClass].filter(Boolean).join(" ");
      return `
        <section class="${esc(classes)}" data-collapse-key="${esc(key)}">
          ${collapsibleButtonSummary(title, metaHtml, !collapsed)}
          <div class="collapsible-body"${collapsed ? " hidden" : ""}>${bodyHtml}</div>
        </section>
      `;
    }

    function isCollapseSectionOpen(section) {
      if (section instanceof HTMLDetailsElement) {
        return section.open;
      }
      return !section.classList.contains("is-collapsed");
    }

    function syncCollapsedSection(section) {
      if (!section.dataset.collapseKey) return;
      if (isCollapseSectionOpen(section)) {
        collapsedSections.delete(section.dataset.collapseKey);
      } else {
        collapsedSections.add(section.dataset.collapseKey);
      }
      saveCollapsedSections();
    }

    function toggleCustomCollapsedSection(section) {
      const open = section.classList.contains("is-collapsed");
      section.classList.toggle("is-collapsed", !open);
      section.classList.toggle("is-open", open);
      const body = section.querySelector(":scope > .collapsible-body");
      if (body) body.hidden = !open;
      const button = section.querySelector(":scope > [data-collapse-toggle]");
      if (button) button.setAttribute("aria-expanded", open ? "true" : "false");
      syncCollapsedSection(section);
    }

    function bindCollapseHandlers(container) {
      container.querySelectorAll("details[data-collapse-key]").forEach(section => {
        section.addEventListener("toggle", () => syncCollapsedSection(section));
      });
      container.querySelectorAll("[data-collapse-toggle]").forEach(button => {
        button.addEventListener("click", () => {
          const section = button.closest("[data-collapse-key]");
          if (section) toggleCustomCollapsedSection(section);
        });
      });
    }

    function fieldValue(value) {
      if (!value) return "";
      if (value.symbol && value.value !== null && value.value !== undefined && !value.symbol.startsWith("OW_WILD_BEHAVIOR_") && !value.symbol.startsWith("SPECIES_")) {
        return `${value.label}`;
      }
      return value.label ?? value.raw ?? "";
    }

    function iconTag(species, className) {
      const symbol = species.symbol || species.name || "";
      if (!species.iconUrl) {
        return `<span class="${className}" data-symbol="${esc(symbol)}" aria-hidden="true"></span>`;
      }
      return `<img class="${className}" data-symbol="${esc(symbol)}" src="${esc(species.iconUrl)}" alt="${esc(species.name)} icon" loading="lazy" decoding="async">`;
    }

    function interfaceIcon(name) {
      const icons = {
        leaf: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 20A7 7 0 0 1 4 13c0-5 5-9 15-9 0 10-4 15-9 15Z"/><path d="M4 20c4-4 8-7 15-16"/></svg>`,
        sunrise: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v5"/><path d="m4.9 4.9 3.5 3.5"/><path d="M2 12h3"/><path d="M19 12h3"/><path d="m15.6 8.4 3.5-3.5"/><path d="M6 17a6 6 0 0 1 12 0"/><path d="M3 21h18"/></svg>`,
        sun: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.9 4.9 1.4 1.4"/><path d="m17.7 17.7 1.4 1.4"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.3 17.7-1.4 1.4"/><path d="m19.1 4.9-1.4 1.4"/></svg>`,
        moon: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 14.5A7.5 7.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5Z"/></svg>`,
        waves: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 8c2 0 2-2 4-2s2 2 4 2 2-2 4-2 2 2 4 2 2-2 4-2"/><path d="M2 14c2 0 2-2 4-2s2 2 4 2 2-2 4-2 2 2 4 2 2-2 4-2"/><path d="M2 20c2 0 2-2 4-2s2 2 4 2 2-2 4-2 2 2 4 2 2-2 4-2"/></svg>`,
        tree: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22v-6"/><path d="M8 22h8"/><path d="M17 8.5a5 5 0 0 0-10 0 4 4 0 0 0 1.1 7.8h7.8A4 4 0 0 0 17 8.5Z"/><path d="m9.5 13 2.5 3 2.5-3"/></svg>`,
        hammer: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 12-8.5 8.5a2.1 2.1 0 0 1-3-3L12 9"/><path d="m17.6 15.6 3-3a2.1 2.1 0 0 0 0-3L14.5 3.5l-3 3 6.1 6.1"/><path d="m7.5 14.5 2 2"/></svg>`,
        fish: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6.5 12c2-3.5 5.2-5 9.5-5 2.5 0 4.5 2.2 6 5-1.5 2.8-3.5 5-6 5-4.3 0-7.5-1.5-9.5-5Z"/><path d="M2 9.5 6.5 12 2 14.5Z"/><circle cx="17" cy="12" r="1"/></svg>`,
        music: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>`,
        swarm: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.8 4.2L18 9l-4.2 1.8L12 15l-1.8-4.2L6 9l4.2-1.8Z"/><path d="M19 14l.9 2.1L22 17l-2.1.9L19 20l-.9-2.1L16 17l2.1-.9Z"/><path d="M5 14l.9 2.1L8 17l-2.1.9L5 20l-.9-2.1L2 17l2.1-.9Z"/></svg>`,
        hoenn: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 5v14"/><path d="M18 5v14"/><path d="M6 12h12"/></svg>`,
        sinnoh: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 7a5 5 0 0 0-5-3H9a4 4 0 0 0 0 8h6a4 4 0 0 1 0 8h-3a5 5 0 0 1-5-3"/></svg>`,
        clock: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>`,
        dice: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="3"/><circle cx="9" cy="9" r="1"/><circle cx="15" cy="9" r="1"/><circle cx="9" cy="15" r="1"/><circle cx="15" cy="15" r="1"/></svg>`,
        ruler: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m4 16 12-12 4 4L8 20Z"/><path d="m8 12 2 2"/><path d="m11 9 2 2"/><path d="m14 6 2 2"/></svg>`,
        target: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 2v3"/><path d="M12 19v3"/><path d="M2 12h3"/><path d="M19 12h3"/></svg>`,
        footstep: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 13c-1.7 1-2.5 2.6-2 4 .6 1.7 2.9 2.4 4.5 1.2 1.3-1 1.7-2.9.9-4.2-.8-1.4-2.1-1.8-3.4-1Z"/><path d="M14 5c-1.3 1.1-1.6 3-.7 4.2.9 1.3 2.8 1.5 4.1.4 1.4-1.2 1.6-3.2.5-4.4-1-1.2-2.6-1.3-3.9-.2Z"/></svg>`,
        speed: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 15a7 7 0 1 0-14 0"/><path d="m12 15 4-5"/><path d="M8 15h8"/></svg>`,
        swords: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m14.5 17.5 3 3 3-3-3-3"/><path d="M3 21 21 3"/><path d="m6.5 17.5-3 3-3-3 3-3"/><path d="M3 3l18 18"/></svg>`,
        shield: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/></svg>`,
        plus: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>`,
        minus: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/></svg>`,
        edit: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="m16.5 3.5 4 4L7 21H3v-4Z"/></svg>`,
        trash: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="m19 6-1 14H6L5 6"/><path d="M10 11v5"/><path d="M14 11v5"/></svg>`,
        bolt: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2 4 14h7l-1 8 10-13h-7Z"/></svg>`,
        flask: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2v6.5L4.6 18.7A2.3 2.3 0 0 0 6.6 22h10.8a2.3 2.3 0 0 0 2-3.3L14 8.5V2"/><path d="M8 2h8"/><path d="M7.6 16h8.8"/></svg>`,
        dot1: `<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="4"/></svg>`,
        dot2: `<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="8" cy="12" r="3"/><circle cx="16" cy="12" r="3"/></svg>`,
        dot3: `<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="6" cy="12" r="2.7"/><circle cx="12" cy="12" r="2.7"/><circle cx="18" cy="12" r="2.7"/></svg>`,
      };
      return icons[name] || "";
    }

    function encounterBadge(icon, className, label) {
      return `<span class="route-encounter-badge ${esc(className)}" title="${esc(label)}" aria-hidden="true">${interfaceIcon(icon)}</span>`;
    }

    function routeEncounterIconSet(group) {
      if (group.key === "grass") {
        return encounterBadge("leaf", "type-grass", "Grass");
      } else if (["morning", "day", "night"].includes(group.key)) {
        if (group.key === "morning") return encounterBadge("sunrise", "type-grass time-morning", "Grass morning");
        if (group.key === "day") return encounterBadge("sun", "type-grass time-day", "Grass day");
        if (group.key === "night") return encounterBadge("moon", "type-grass time-night", "Grass night");
      } else if (group.key === "hoenn") {
        return encounterBadge("hoenn", "type-sound", "Hoenn sound");
      } else if (group.key === "sinnoh") {
        return encounterBadge("sinnoh", "type-sound", "Sinnoh sound");
      } else if (group.key === "surf") {
        return encounterBadge("waves", "type-surf", "Surf");
      } else if (group.key === "rockSmash") {
        return encounterBadge("hammer", "type-rock", "Rock smash");
      } else if (group.key === "headbuttNormal") {
        return encounterBadge("tree", "type-headbutt", "Headbutt");
      } else if (group.key === "headbuttSpecial") {
        return encounterBadge("tree", "type-headbutt special-headbutt", "Special headbutt trees");
      } else if (["oldRod", "goodRod", "superRod"].includes(group.key)) {
        if (group.key === "oldRod") return encounterBadge("dot1", "type-rod", "Old rod");
        if (group.key === "goodRod") return encounterBadge("dot2", "type-rod", "Good rod");
        if (group.key === "superRod") return encounterBadge("dot3", "type-rod", "Super rod");
      } else if (group.key === "swarms") {
        return encounterBadge("swarm", "type-swarm", "Swarms");
      }
      return "";
    }

    function defaultRouteSpawnTypeFilters() {
      return new Set(ROUTE_SPAWN_FILTERS.filter(filter => filter.defaultOn).map(filter => filter.key));
    }

    function readRouteSpawnTypeFilters() {
      const defaults = defaultRouteSpawnTypeFilters();
      try {
        const stored = localStorage.getItem(ROUTE_SPAWN_FILTER_STORAGE_KEY);
        if (!stored) return defaults;
        const keys = JSON.parse(stored);
        if (!Array.isArray(keys)) return defaults;
        const selected = new Set(keys.filter(key => ROUTE_SPAWN_FILTER_KEYS.has(key)));
        if (!keys.includes("grass") && localStorage.getItem(ROUTE_GRASS_FILTER_MIGRATION_KEY) !== "1") {
          selected.add("grass");
          localStorage.setItem(ROUTE_GRASS_FILTER_MIGRATION_KEY, "1");
        }
        if (localStorage.getItem(ROUTE_HEADBUTT_FILTER_MIGRATION_KEY) !== "1") {
          selected.add("headbuttNormal");
          selected.add("headbuttSpecial");
          localStorage.setItem(ROUTE_HEADBUTT_FILTER_MIGRATION_KEY, "1");
        }
        return selected;
      } catch {
        return defaults;
      }
    }

    function saveRouteSpawnTypeFilters() {
      localStorage.setItem(ROUTE_SPAWN_FILTER_STORAGE_KEY, JSON.stringify(Array.from(routeSpawnTypeFilters)));
    }

    function routeSpawnFilterButton(filter) {
      const active = routeSpawnTypeFilters.has(filter.key);
      const iconSet = routeEncounterIconSet({ key: filter.key, title: filter.label, label: filter.label });
      const filterClass = routeGroupClassName(filter.key);
      return `
        <button class="route-spawn-filter spawn-${esc(filterClass)} ${active ? "active" : ""}" type="button" data-spawn-filter="${esc(filter.key)}" aria-label="${esc(filter.label)}" aria-pressed="${active ? "true" : "false"}" title="${esc(filter.label)}">
          <span class="route-encounter-icons">${iconSet}</span>
        </button>
      `;
    }

    function renderRouteSpawnTypeFilters() {
      els.routeSpawnTypeFilters.innerHTML = ROUTE_SPAWN_FILTERS.map(routeSpawnFilterButton).join("");
    }

    function workspaceSourceText() {
      if (!appData) return "";
      const updated = new Date(appData.generatedAt).toLocaleString();
      const source = activeView === "encounters"
        ? `${appData.source.encounters} + ${appData.source.headbutt}`
        : appData.source.overlay;
      return `${source} | ${updated}`;
    }

    function renderWorkspaceTabs() {
      document.querySelectorAll(".workspace-tab").forEach(tab => {
        tab.classList.toggle("active", tab.dataset.view === activeView);
      });
      els.profilesView.classList.toggle("active", activeView === "profiles");
      els.encountersView.classList.toggle("active", activeView === "encounters");
      els.profileControls.hidden = activeView !== "profiles";
      els.source.textContent = workspaceSourceText();
    }

    function routeEditKey(routeId, path) {
      return `${routeId}:${path}`;
    }

    function routePendingValue(routeId, path, fallback) {
      const key = routeEditKey(routeId, path);
      return encounterEdits.has(key) ? encounterEdits.get(key) : String(fallback ?? "");
    }

    function routeBaseFormKey(symbol, form) {
      return `${String(symbol || "")}:${String(form ?? 0)}`;
    }

    function routeChangePayload() {
      const changes = {};
      encounterEdits.forEach((value, key) => {
        const split = key.indexOf(":");
        const routeId = key.slice(0, split);
        const path = key.slice(split + 1);
        if (!changes[routeId]) changes[routeId] = {};
        changes[routeId][path] = value;
      });
      return changes;
    }

    function refreshPendingRouteIds() {
      pendingRouteIds = new Set();
      encounterEdits.forEach((value, key) => {
        const split = key.indexOf(":");
        if (split > 0) pendingRouteIds.add(key.slice(0, split));
      });
    }

    function syncPendingRouteId(routeId) {
      if (routeId === null || routeId === undefined) return;
      const routeKey = String(routeId);
      const prefix = `${routeKey}:`;
      let hasPending = false;
      for (const key of encounterEdits.keys()) {
        if (key.startsWith(prefix)) {
          hasPending = true;
          break;
        }
      }
      if (hasPending) {
        pendingRouteIds.add(routeKey);
      } else {
        pendingRouteIds.delete(routeKey);
      }
    }

    function routeSpeciesOption(text) {
      const value = String(text || "").trim();
      if (!value) return null;
      const upper = value.toUpperCase();
      const prefixed = upper.startsWith("SPECIES_") ? upper : `SPECIES_${upper}`;
      const compact = value.toLowerCase().replace(/[^a-z0-9]/g, "");
      return routeSpeciesBySymbol.get(value)
        || routeSpeciesBySymbol.get(upper)
        || routeSpeciesBySymbol.get(prefixed)
        || routeSpeciesByName.get(value.toLowerCase())
        || routeSpeciesByCompactName.get(compact)
        || null;
    }

    function routeSpeciesShortSymbol(symbol) {
      return String(symbol || "").replace(/^SPECIES_/, "");
    }

    function routeSpeciesWriteSymbol(option) {
      return option?.baseSymbol || option?.symbol || "";
    }

    function routeSpeciesWriteForm(option) {
      return String(option?.baseSymbol ? option.form ?? 0 : 0);
    }

    function routeDisplaySpecies(symbol, form = 0) {
      const formKey = routeBaseFormKey(symbol, form);
      return routeSpeciesByBaseForm.get(formKey) || routeSpeciesOption(symbol) || speciesBySymbol(symbol);
    }

    function routeSpeciesInputValue(symbol, form = null) {
      const option = form === null
        ? (routeSpeciesOption(symbol) || speciesBySymbol(symbol))
        : routeDisplaySpecies(symbol, form);
      return routeSpeciesShortSymbol(option.symbol || symbol);
    }

    function routeSpeciesDatalist() {
      return `
        <datalist id="routeSpeciesOptions">
          ${appData.speciesOptions.map(species => `
            <option value="${esc(routeSpeciesShortSymbol(species.symbol))}" label="${esc(species.name)}"></option>
          `).join("")}
        </datalist>
      `;
    }

    function renderRouteSpeciesDatalist() {
      if (routeSpeciesDatalistRendered) return;
      els.routeSpeciesDatalistHost.innerHTML = routeSpeciesDatalistHtml;
      routeSpeciesDatalistRendered = true;
    }

    function normalizeAppData(data) {
      const normalized = {
        fields: [],
        counts: {},
        labels: {},
        editOptions: {},
        defaultClassIndex: 0,
        defaultProfile: null,
        primitiveFields: [],
        primitiveMaps: {},
        classes: [],
        classRules: [],
        maxSpeedOverrides: [],
        variableOverrides: [],
        groups: [],
        assignments: [],
        speciesByValue: {},
        speciesOptions: [],
        typeOptions: [],
        spawnSettings: [],
        routes: [],
        profilesAvailable: true,
        profileError: null,
        ...data,
      };
      normalized.source = {
        overlay: "",
        species: "",
        spawnInternal: "",
        wildTest: "",
        icons: "",
        encounters: "",
        ...(data.source || {}),
      };
      return normalized;
    }

    function profileUnavailableMessage() {
      const message = appData?.profileError?.message || "Overworld behaviour profiles could not be parsed.";
      return `
        <div class="empty">
          <strong>Profiles unavailable</strong><br>
          Route encounters are still loaded. ${esc(message)}
        </div>
      `;
    }

    function speciesBySymbol(symbol) {
      return routeSpeciesBySymbol.get(symbol) || { symbol, name: symbol, value: null };
    }

    function routeDisplaySpeciesForPath(routeId, path, fallbackSpecies) {
      const raw = routePendingValue(routeId, path, fallbackSpecies.symbol);
      return routeSpeciesOption(raw) || speciesBySymbol(raw) || fallbackSpecies;
    }

    function routeDisplaySpeciesForEntry(routeId, path, fallbackSpecies, formPath, fallbackForm) {
      const raw = routePendingValue(routeId, path, fallbackSpecies.symbol);
      const formRaw = routePendingValue(routeId, formPath, fallbackForm);
      return routeDisplaySpecies(raw, formRaw);
    }

    function speciesFormInputAttrs(formPath, form) {
      return `data-form-path="${esc(formPath)}" data-form-original="${esc(form)}"`;
    }

    function routeSpeciesInput(routeId, path, species, label, formPath, form) {
      const raw = routePendingValue(routeId, path, species.symbol);
      const formRaw = routePendingValue(routeId, formPath, form);
      const changed = raw !== species.symbol || String(formRaw) !== String(form);
      const option = routeDisplaySpecies(raw, formRaw);
      return `
        <label class="route-field ${changed ? "changed" : ""}">
          <span class="field-label">${esc(label)}</span>
          <span class="species-input-wrap">
            ${iconTag(option, "mon-icon")}
            <input class="route-input route-species-combo" type="text" list="routeSpeciesOptions" value="${esc(routeSpeciesInputValue(raw, formRaw))}" data-route-id="${esc(routeId)}" data-path="${esc(path)}" data-original="${esc(species.symbol)}" ${speciesFormInputAttrs(formPath, form)} autocomplete="off">
            <input class="route-input route-number route-form" type="number" min="0" max="31" step="1" value="${esc(formRaw)}" data-kind="form" data-route-id="${esc(routeId)}" data-path="${esc(formPath)}" data-original="${esc(form)}" title="Form">
          </span>
        </label>
      `;
    }

    function routeNumberInput(routeId, path, value, label, kind, min = 0, max = 100) {
      const raw = routePendingValue(routeId, path, value);
      const changed = String(raw) !== String(value);
      return `
        <label class="route-field ${changed ? "changed" : ""}">
          <span class="field-label">${esc(label)}</span>
          <input class="route-input route-number" type="number" min="${esc(min)}" max="${esc(max)}" step="1" value="${esc(raw)}" data-kind="${esc(kind)}" data-route-id="${esc(routeId)}" data-path="${esc(path)}" data-original="${esc(value)}">
        </label>
      `;
    }

    function spawnSettingEditKey(symbol) {
      return symbol;
    }

    function pendingSpawnSettingValue(symbol, fallback) {
      const key = spawnSettingEditKey(symbol);
      return spawnSettingEdits.has(key) ? spawnSettingEdits.get(key) : String(fallback ?? "");
    }

    function spawnSettingChangePayload() {
      const changes = {};
      spawnSettingEdits.forEach((value, symbol) => {
        changes[symbol] = value;
      });
      return changes;
    }

    function spawnSettingGroupIcon(group) {
      const icons = {
        capacity: ["leaf", "type-grass"],
        testSpawns: ["flask", "type-test"],
        spawnFlow: ["clock", "type-flow"],
        placement: ["target", "type-placement"],
        ambient: ["music", "type-sound"],
        movement: ["footstep", "type-movement"],
      };
      const [icon, typeClass] = icons[group.key] || ["target", "type-movement"];
      return encounterBadge(icon, typeClass, group.label);
    }

    function spawnSettingIcon(setting) {
      const symbol = String(setting.symbol || "");
      let icon = "target";
      let typeClass = "type-movement";
      if (setting.kind === "testSpawn" || symbol.includes("WILD_TEST") || symbol.includes("TEST_SPAWNS")) {
        icon = "flask";
        typeClass = "type-test";
      } else if (symbol.includes("SHINY")) {
        icon = "swarm";
        typeClass = "type-shiny";
      } else if (symbol.includes("CHANCE") || symbol.includes("RANDOM")) {
        icon = "dice";
        typeClass = "type-flow";
      } else if (symbol.includes("COOLDOWN") || symbol.includes("REFILL") || symbol.includes("TICK")) {
        icon = "clock";
        typeClass = "type-flow";
      } else if (symbol.includes("GRASS")) {
        icon = "leaf";
        typeClass = "type-grass";
      } else if (symbol.includes("SURF")) {
        icon = "waves";
        typeClass = "type-surf";
      } else if (symbol.includes("HEADBUTT")) {
        icon = "tree";
        typeClass = "type-headbutt";
      } else if (symbol.includes("FISH")) {
        icon = "fish";
        typeClass = "type-rod";
      } else if (symbol.includes("AMBIENT")) {
        icon = "music";
        typeClass = "type-sound";
      } else if (symbol.includes("ATTEMPTS")) {
        icon = "dice";
        typeClass = "type-placement";
      } else if (symbol.includes("DISTANCE")) {
        icon = "ruler";
        typeClass = "type-placement";
      } else if (symbol.includes("BURST")) {
        icon = "bolt";
        typeClass = "type-movement";
      } else if (symbol.includes("SPEED")) {
        icon = "speed";
        typeClass = "type-movement";
      } else if (symbol.includes("BATTLE")) {
        icon = "shield";
        typeClass = "type-movement";
      } else if (symbol.includes("FLEE")) {
        icon = "footstep";
        typeClass = "type-movement";
      } else if (symbol.includes("RANGE")) {
        icon = "target";
        typeClass = "type-movement";
      }
      return encounterBadge(icon, typeClass, setting.label);
    }

    function spawnSettingField(setting, role) {
      return (setting.fields || []).find(field => field.role === role) || null;
    }

    function spawnSettingDisplayValue(setting) {
      if (setting.kind === "testSpawn") {
        const enabledField = spawnSettingField(setting, "enabled");
        const speciesField = spawnSettingField(setting, "species");
        const levelField = spawnSettingField(setting, "level");
        const enabled = pendingSpawnSettingValue(enabledField?.symbol, enabledField?.value) === "1";
        if (!enabled) return "Off";
        const speciesSymbol = pendingSpawnSettingValue(speciesField?.symbol, speciesField?.symbolValue || setting.testSpawn?.speciesSymbol || "SPECIES_NONE");
        const species = routeSpeciesOption(speciesSymbol) || speciesBySymbol(speciesSymbol);
        const level = pendingSpawnSettingValue(levelField?.symbol, levelField?.value || setting.testSpawn?.level || 1);
        return `${routeSpeciesShortSymbol(species.symbol || speciesSymbol)} L${level}`;
      }
      return `${pendingSpawnSettingValue(setting.symbol, setting.value)}${setting.suffix || ""}`;
    }

    function spawnSettingChip(setting) {
      if (setting.kind === "testSpawn") {
        const changed = (setting.fields || []).some(field =>
          spawnSettingEdits.has(spawnSettingEditKey(field.symbol))
        );
        const enabledField = spawnSettingField(setting, "enabled");
        const speciesField = spawnSettingField(setting, "species");
        const enabled = pendingSpawnSettingValue(enabledField?.symbol, enabledField?.value) === "1";
        const speciesSymbol = pendingSpawnSettingValue(speciesField?.symbol, speciesField?.symbolValue || setting.testSpawn?.speciesSymbol || "SPECIES_NONE");
        const species = routeSpeciesOption(speciesSymbol) || speciesBySymbol(speciesSymbol);
        const sprite = enabled ? iconTag(species, "mon-icon") : "";
        return `
          <button class="route-field spawn-setting-chip ${changed ? "changed" : ""}" type="button" data-spawn-setting-symbol="${esc(setting.symbol)}" title="${esc(setting.label)}: ${esc(spawnSettingDisplayValue(setting))}" aria-label="Edit ${esc(setting.label)}">
            ${spawnSettingIcon(setting)}
            ${sprite}
            <span class="spawn-setting-value">${esc(spawnSettingDisplayValue(setting))}</span>
          </button>
        `;
      }
      const raw = pendingSpawnSettingValue(setting.symbol, setting.value);
      const changed = String(raw) !== String(setting.value);
      return `
        <button class="route-field spawn-setting-chip ${changed ? "changed" : ""}" type="button" data-spawn-setting-symbol="${esc(setting.symbol)}" title="${esc(setting.label)}: ${esc(raw)}${esc(setting.suffix || "")} • ${esc(setting.symbol)}" aria-label="Edit ${esc(setting.label)}">
          ${spawnSettingIcon(setting)}
          <span class="spawn-setting-value">${esc(raw)}${esc(setting.suffix || "")}</span>
        </button>
      `;
    }

    function spawnSettingsGroupRow(group) {
      return `
        <div class="spawn-settings-row">
          <span class="spawn-group-icon" title="${esc(group.label)}" aria-label="${esc(group.label)}">${spawnSettingGroupIcon(group)}</span>
          <div class="spawn-settings-chips">
            ${group.settings.map(spawnSettingChip).join("")}
          </div>
        </div>
      `;
    }

    function profileIconButton(assignment) {
      const species = assignment.species;
      const active = species.symbol === selectedSymbol ? " active" : "";
      return `
        <button class="profile-icon-button${active}" type="button" data-symbol="${esc(species.symbol)}" aria-label="View ${esc(species.name)}" title="${esc(species.name)}">
          ${iconTag(species, "profile-icon")}
        </button>
      `;
    }

    function profileFields(profile) {
      return appData.fields
        .filter(field => !PROFILE_DIRECT_EDIT_HIDDEN_FIELDS.has(field.key))
        .map(field => `
        <div class="field">
          <span class="field-label">${esc(field.label)}</span>
          <span class="field-value" title="${esc(profile[field.key]?.raw ?? "")}">${esc(fieldValue(profile[field.key]))}</span>
        </div>
      `).join("");
    }

    function profileFieldLabel(fieldKey) {
      return appData.fields.find(field => field.key === fieldKey)?.label || fieldKey;
    }

    function profileFieldIcon(fieldKey) {
      const icons = {
        alertChance: ["dice", "type-flow"],
        alertEmote: ["music", "type-sound"],
        alertRange: ["target", "type-placement"],
        alertRangeClose: ["target", "type-placement"],
        alertRangeType: ["target", "type-placement"],
        alertState: ["target", "type-placement"],
        alertSpecialAction: ["swarm", "type-swarm"],
        alertTime: ["clock", "type-flow"],
        alertness: ["ruler", "type-placement"],
        alertCallSpawnAmount: ["plus", "type-swarm"],
        alertCallSpawnState: ["footstep", "type-swarm"],
        attentiveAllowedTile: ["target", "type-placement"],
        attentiveAllowedTile2: ["target", "type-placement"],
        attentiveAction: ["bolt", "type-movement"],
        attentiveBattle: ["swords", "type-test"],
        attentiveCooldown: ["clock", "type-flow"],
        attentiveHopAllowNonCardinal: ["target", "type-placement"],
        attentiveHopMinDistance: ["ruler", "type-placement"],
        attentiveHopMaxDistance: ["ruler", "type-placement"],
        attentiveHopPause: ["clock", "type-flow"],
        attentiveRamAccelerationSteps: ["footstep", "type-movement"],
        attentiveRamMaxSpeed: ["speed", "type-movement"],
        attentiveSpeed: ["speed", "type-movement"],
        attentiveState: ["footstep", "type-movement"],
        attentiveTeleportTime: ["clock", "type-flow"],
        attentiveTeleportPause: ["clock", "type-flow"],
        chillAction: ["footstep", "type-movement"],
        chillAllowedTile: ["target", "type-placement"],
        chillAllowedTile2: ["target", "type-placement"],
        chillBattle: ["swords", "type-test"],
        chillCooldown: ["clock", "type-flow"],
        chillSpeed: ["speed", "type-movement"],
        chillState: ["leaf", "type-grass"],
        chillTarget: ["target", "type-placement"],
        alertBattle: ["swords", "type-test"],
        hopAllowNonCardinal: ["target", "type-placement"],
        hopMinDistance: ["ruler", "type-placement"],
        hopMaxDistance: ["ruler", "type-placement"],
        hopPause: ["clock", "type-flow"],
        jumpLevel: ["footstep", "type-movement"],
        movementStyle: ["footstep", "type-movement"],
        profileId: ["shield", "type-test"],
        ramAccelerationSteps: ["footstep", "type-movement"],
        ramMaxSpeed: ["speed", "type-movement"],
        range: ["ruler", "type-placement"],
        restTime: ["clock", "type-flow"],
        spawnDestination: ["target", "type-placement"],
        spawnDestinationDistance: ["ruler", "type-placement"],
        spawnDestinationMinDistance: ["minus", "type-placement"],
        spawnDestinationMaxDistance: ["plus", "type-placement"],
        spawnDestinationType: ["target", "type-placement"],
        spawnState: ["footstep", "type-movement"],
        specialAction: ["footstep", "type-movement"],
        stamina: ["bolt", "type-flow"],
        targetSelector: ["target", "type-placement"],
        teleportTime: ["clock", "type-flow"],
        teleportPause: ["clock", "type-flow"],
        tiredBattle: ["swords", "type-test"],
        tiredAllowedTile: ["target", "type-placement"],
        tiredAllowedTile2: ["target", "type-placement"],
        tiredHopAllowNonCardinal: ["target", "type-placement"],
        tiredHopMinDistance: ["ruler", "type-placement"],
        tiredHopMaxDistance: ["ruler", "type-placement"],
        tiredHopPause: ["clock", "type-flow"],
        tiredRamAccelerationSteps: ["footstep", "type-movement"],
        tiredRamMaxSpeed: ["speed", "type-movement"],
        tiredSpeed: ["speed", "type-movement"],
        tiredState: ["clock", "type-flow"],
        tiredTeleportTime: ["clock", "type-flow"],
        tiredTeleportPause: ["clock", "type-flow"],
      };
      return icons[fieldKey] || ["target", "type-placement"];
    }

    function profileFieldBadge(fieldKey, label) {
      const [icon, typeClass] = profileFieldIcon(fieldKey);
      return `<span class="profile-field-badge">${encounterBadge(icon, typeClass, label)}</span>`;
    }

    function primitiveFieldLabel(fieldKey) {
      return (appData.primitiveFields || []).find(field => field.key === fieldKey)?.label || fieldKey;
    }

    function editKey(classIndex, fieldKey) {
      return `${classIndex}:${fieldKey}`;
    }

    function pendingProfileValue(classIndex, fieldKey, fallbackRaw) {
      const key = editKey(classIndex, fieldKey);
      return profileEdits.has(key) ? profileEdits.get(key) : fallbackRaw;
    }

    function profileComboRawDisplay(raw) {
      return String(raw ?? "")
        .replace(/^OW_WILD_BEHAVIOR_KIND_/, "")
        .replace(/^OW_WILD_BEHAVIOR_LOCOMOTION_/, "")
        .replace(/^OW_WILD_BEHAVIOR_/, "");
    }

    function profileComboLabelDisplay(option) {
      return String(option?.label || "")
        .replace(/^Ow Wild Behavior /, "")
        .replace(/^Ow Wild Spawner /, "")
        .replace(/^Ow Wild /, "")
        .replace(/^Battle Trigger /, "");
    }

    function profileComboOptionDisplay(option, fieldKey = "") {
      if (!option) return "";
      if (fieldKey === ALERT_RANGE_TYPE_FIELD) {
        return alertRangeBaseDisplay(option.raw);
      }
      if (fieldKey === SPAWN_DESTINATION_TYPE_FIELD) {
        return spawnDestinationTypeDisplay(option.raw);
      }
      if (NUMERIC_PROFILE_FIELD_KEYS.has(fieldKey) && option.value !== null && option.value !== undefined) {
        return String(option.value);
      }
      const displayOverrides = {
        OW_WILD_BEHAVIOR_KIND_NONE: "None",
        OW_WILD_BEHAVIOR_KIND_IDLE: "Idle",
        OW_WILD_BEHAVIOR_KIND_WANDER: "Wander",
        OW_WILD_BEHAVIOR_KIND_CHASE: "Chase",
        OW_WILD_BEHAVIOR_KIND_FLEE: "Flee",
        OW_WILD_BEHAVIOR_KIND_PLAYFUL: "Playful",
        OW_WILD_BEHAVIOR_KIND_RAM: "Ram",
        OW_WILD_BEHAVIOR_KIND_HEADBUTT_TREE_HOP: "Headbutt Tree Hop",
        OW_WILD_BEHAVIOR_KIND_ASLEEP: "Asleep",
        OW_WILD_BEHAVIOR_KIND_SINGING: "Singing",
        OW_WILD_BEHAVIOR_KIND_TIRED_EMOTE: "Tired Emote",
        OW_WILD_BEHAVIOR_KIND_NO_VISUAL: "No Visual",
        OW_WILD_BEHAVIOR_LOCOMOTION_NONE: "None",
        OW_WILD_BEHAVIOR_LOCOMOTION_WANDER: "Walk",
        OW_WILD_BEHAVIOR_LOCOMOTION_HOP: "Hop",
        OW_WILD_BEHAVIOR_LOCOMOTION_RAM: "Ram",
        OW_WILD_BEHAVIOR_LOCOMOTION_PHANTOM_TELEPORT: "Phantom Teleport",
        OW_WILD_BEHAVIOR_ALERT_SPECIAL_NONE: "None",
        OW_WILD_BEHAVIOR_ALERT_SPECIAL_CALL_FOR_HELP: "Call for help",
        OW_WILD_BEHAVIOR_ALERT_CALL_SPAWN_STATE_CHILL: "Chill",
        OW_WILD_BEHAVIOR_ALERT_CALL_SPAWN_STATE_ALERT: "Alert",
        OW_WILD_BEHAVIOR_ALERT_CALL_SPAWN_STATE_ACTIVE: "Active",
        OW_WILD_BEHAVIOR_ALERT_CALL_SPAWN_STATE_TIRED: "Tired",
        OW_WILD_BEHAVIOR_TARGET_NONE: "Behavior default",
        OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER: "Toward player",
        OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER: "Away from player",
        OW_WILD_BEHAVIOR_TARGET_TREE_TOP: "Tree top",
        OW_WILD_BEHAVIOR_TARGET_PLAYFUL_ORBIT: "Playful orbit",
        OW_WILD_BEHAVIOR_TARGET_PLAYER_FRONT: "Player front",
        OW_WILD_BEHAVIOR_TARGET_SWARM: "Swarm",
      };
      if (displayOverrides[option.raw]) {
        return displayOverrides[option.raw];
      }
      if (String(option.raw || "").startsWith("OW_WILD_")) {
        let display = profileComboLabelDisplay(option) || profileComboRawDisplay(option.raw);
        if (fieldKey === "alertRange") {
          const alertRangeLabels = {
            "None": "None",
            "Facing Line": "Facing line",
            "Facing Line Close Radius": "Facing line + close radius",
            "Cardinal Line": "Cardinal line",
            "Radius": "Radius",
            "Terrain Only": "Terrain only",
          };
          display = alertRangeLabels[display] || display;
        }
        return display.replace(/^Bubble Id /, "");
      }
      return profileComboRawDisplay(option.raw);
    }

    function alertRangeIsCloseRaw(raw) {
      return /_CLOSE_RADIUS$/.test(String(raw || ""));
    }

    function alertRangeBaseRaw(raw) {
      return String(raw || "").replace(/_CLOSE_RADIUS$/, "");
    }

    function alertRangeBaseDisplay(raw) {
      const option = (appData.editOptions.alertRange || []).find(item => item.raw === raw)
        || (appData.editOptions.alertRange || []).find(item => item.raw === alertRangeBaseRaw(raw));
      return (profileComboOptionDisplay(option, "alertRange") || profileComboRawDisplay(alertRangeBaseRaw(raw)))
        .replace(/\s*\+\s*close radius$/i, "");
    }

    function alertRangeTypeOptions() {
      const seen = new Map();
      (appData.editOptions.alertRange || []).forEach(option => {
        const baseRaw = alertRangeBaseRaw(option.raw);
        if (seen.has(baseRaw)) return;
        const baseOption = (appData.editOptions.alertRange || []).find(item => item.raw === baseRaw) || option;
        seen.set(baseRaw, {
          ...baseOption,
          raw: baseRaw,
          label: alertRangeBaseDisplay(option.raw),
          value: baseOption.value ?? option.value,
        });
      });
      return Array.from(seen.values()).sort((a, b) => {
        if (Number.isFinite(a.value) && Number.isFinite(b.value) && a.value !== b.value) {
          return a.value - b.value;
        }
        return profileComboOptionDisplay(a, ALERT_RANGE_TYPE_FIELD)
          .localeCompare(profileComboOptionDisplay(b, ALERT_RANGE_TYPE_FIELD));
      });
    }

    function alertRangeTypeOptionForRaw(raw) {
      const baseRaw = alertRangeBaseRaw(raw);
      return alertRangeTypeOptions().find(option => option.raw === baseRaw) || null;
    }

    function alertRangeSupportsClose(raw) {
      const baseRaw = alertRangeBaseRaw(raw);
      return (appData.editOptions.alertRange || []).some(option =>
        alertRangeBaseRaw(option.raw) === baseRaw && alertRangeIsCloseRaw(option.raw));
    }

    function alertRangeRawWithClose(raw, closeEnabled) {
      const baseRaw = alertRangeBaseRaw(raw);
      if (!closeEnabled) {
        return (appData.editOptions.alertRange || []).find(option => option.raw === baseRaw)?.raw || baseRaw;
      }
      return (appData.editOptions.alertRange || []).find(option =>
        alertRangeBaseRaw(option.raw) === baseRaw && alertRangeIsCloseRaw(option.raw))?.raw
        || baseRaw;
    }

    function alertRangeNeedsLength(raw) {
      const baseRaw = alertRangeBaseRaw(raw);
      return !/_NONE$/.test(baseRaw) && !/_TERRAIN_ONLY$/.test(baseRaw);
    }

    function alertSpecialActionCallsForHelp(raw) {
      return raw === "OW_WILD_BEHAVIOR_ALERT_SPECIAL_CALL_FOR_HELP";
    }

    function spawnDestinationPlayerInfo(raw) {
      const value = String(raw || "");
      if (value === "OW_WILD_SPAWN_DESTINATION_FRONT_OF_PLAYER") {
        return { kind: "front", distance: 1 };
      }
      if (value === "OW_WILD_SPAWN_DESTINATION_FIVE_TILES_BEHIND_PLAYER") {
        return { kind: "behind", distance: 5 };
      }
      const match = value.match(/^OW_WILD_SPAWN_DESTINATION_(ONE|TWO|THREE|FOUR|FIVE)_TILES?_(FRONT_OF|BEHIND)_PLAYER$/);
      if (!match) return null;
      const distances = { ONE: 1, TWO: 2, THREE: 3, FOUR: 4, FIVE: 5 };
      return {
        kind: match[2] === "FRONT_OF" ? "front" : "behind",
        distance: distances[match[1]],
      };
    }

    function spawnDestinationTypeKeyForRaw(raw) {
      const info = spawnDestinationPlayerInfo(raw);
      if (!info) return raw;
      return info.kind === "front" ? SPAWN_DESTINATION_FRONT_TYPE : SPAWN_DESTINATION_BEHIND_TYPE;
    }

    function spawnDestinationTypeDisplay(raw) {
      if (raw === SPAWN_DESTINATION_FRONT_TYPE) return "Front of player";
      if (raw === SPAWN_DESTINATION_BEHIND_TYPE) return "Behind player";
      if (raw === SPAWN_DESTINATION_NEXT_TO_PLAYER_RAW) return "Next to player";
      return profileComboOptionDisplay(profileOptionForRaw("spawnDestination", raw), "spawnDestination")
        || profileComboRawDisplay(raw);
    }

    function spawnDestinationDistanceOptions(typeKey) {
      const kind = typeKey === SPAWN_DESTINATION_FRONT_TYPE
        ? "front"
        : typeKey === SPAWN_DESTINATION_BEHIND_TYPE
          ? "behind"
          : "";
      if (!kind) return [];
      const options = [];
      (appData.editOptions.spawnDestination || []).forEach(option => {
        const info = spawnDestinationPlayerInfo(option.raw);
        if (!info || info.kind !== kind) return;
        options.push({ ...option, distance: info.distance });
      });
      return options.sort((a, b) => a.distance - b.distance);
    }

    function spawnDestinationTypeOptions() {
      const options = [];
      (appData.editOptions.spawnDestination || []).forEach(option => {
        if (spawnDestinationPlayerInfo(option.raw)) return;
        options.push(option);
      });
      if (spawnDestinationDistanceOptions(SPAWN_DESTINATION_FRONT_TYPE).length) {
        options.push({ raw: SPAWN_DESTINATION_FRONT_TYPE, label: "Front of player", value: null });
      }
      if (spawnDestinationDistanceOptions(SPAWN_DESTINATION_BEHIND_TYPE).length) {
        options.push({ raw: SPAWN_DESTINATION_BEHIND_TYPE, label: "Behind player", value: null });
      }
      return options;
    }

    function spawnDestinationTypeOptionForRaw(raw) {
      const typeKey = spawnDestinationTypeKeyForRaw(raw);
      return spawnDestinationTypeOptions().find(option => option.raw === typeKey) || null;
    }

    function spawnDestinationRawForType(typeKey, preferredDistance = null) {
      const distanceOptions = spawnDestinationDistanceOptions(typeKey);
      if (!distanceOptions.length) {
        return profileOptionForRaw("spawnDestination", typeKey)?.raw || typeKey;
      }
      const exact = distanceOptions.find(option => String(option.distance) === String(preferredDistance));
      if (exact) return exact.raw;
      const fallbackDistance = typeKey === SPAWN_DESTINATION_BEHIND_TYPE ? 5 : 1;
      return distanceOptions.find(option => option.distance === fallbackDistance)?.raw
        || distanceOptions[0].raw;
    }

    function spawnDestinationNeedsDistance(raw) {
      return !!spawnDestinationPlayerInfo(raw)
        || raw === SPAWN_DESTINATION_NEXT_TO_PLAYER_RAW;
    }

    function spawnDestinationUsesRadius(raw) {
      return raw === SPAWN_DESTINATION_NEXT_TO_PLAYER_RAW;
    }

    function movementStyleOptions(fieldKey = "movementStyle") {
      return (appData.editOptions[fieldKey] || appData.editOptions.movementStyle || [])
        .map(option => ({ ...option, label: profileComboOptionDisplay(option, fieldKey) }));
    }

    function targetSelectorOptions() {
      const byRaw = new Map((appData.editOptions.targetSelector || []).map(option => [option.raw, option]));
      return PROFILE_TARGET_SELECTOR_RAWS
        .map(raw => byRaw.get(raw))
        .filter(Boolean)
        .map(option => ({ ...option, label: profileComboOptionDisplay(option, "targetSelector") }));
    }

    function profileOptionsForField(fieldKey) {
      if (PROFILE_MOVEMENT_FIELDS.has(fieldKey)) return movementStyleOptions(fieldKey);
      if (fieldKey === "targetSelector" || fieldKey === "chillTarget") return targetSelectorOptions();
      if (fieldKey === ALERT_RANGE_TYPE_FIELD) return alertRangeTypeOptions();
      if (fieldKey === SPAWN_DESTINATION_TYPE_FIELD) return spawnDestinationTypeOptions();
      return appData.editOptions[fieldKey] || [];
    }

    function profileOptionForRaw(fieldKey, raw) {
      if (fieldKey === ALERT_RANGE_TYPE_FIELD) return alertRangeTypeOptionForRaw(raw);
      if (fieldKey === SPAWN_DESTINATION_TYPE_FIELD) return spawnDestinationTypeOptionForRaw(raw);
      const option = profileOptionsForField(fieldKey).find(item => item.raw === raw) || null;
      if (PROFILE_MOVEMENT_FIELDS.has(fieldKey)) {
        return option;
      }
      return option || (appData.editOptions[fieldKey] || []).find(item => item.raw === raw) || null;
    }

    function profileFieldRerendersSubcontrols(fieldKey) {
      return PROFILE_BEHAVIOR_FIELDS.has(fieldKey)
        || PROFILE_MOVEMENT_FIELDS.has(fieldKey)
        || fieldKey === ALERT_RANGE_TYPE_FIELD
        || fieldKey === "alertSpecialAction"
        || fieldKey === SPAWN_DESTINATION_TYPE_FIELD;
    }

    function profileComboDisplay(fieldKey, raw) {
      return profileComboOptionDisplay(profileOptionForRaw(fieldKey, raw), fieldKey) || profileComboRawDisplay(raw);
    }

    function datalistId(fieldKey) {
      return `profile-options-${fieldKey}`;
    }

    function datalistOptionsHtml(fieldKey) {
      const options = profileOptionsForField(fieldKey);
      return options.map(option => `
        <option value="${esc(profileComboOptionDisplay(option, fieldKey))}"></option>
      `).join("");
    }

    function profileDatalists() {
      return appData.fields.map(field => `
        <datalist id="${esc(datalistId(field.key))}">
          ${datalistOptionsHtml(field.key)}
        </datalist>
      `).join("");
    }

    function profileSpeciesDatalist() {
      return `
        <datalist id="profileSpeciesOptions">
          ${appData.speciesOptions
            .filter(species => species.symbol !== "SPECIES_NONE")
            .map(species => `
            <option value="${esc(routeSpeciesShortSymbol(species.symbol))}" label="${esc(species.name)}"></option>
          `).join("")}
        </datalist>
      `;
    }

    function buildProfileOptionLookup() {
      const lookup = new Map();
      Object.entries(appData.editOptions || {}).forEach(([fieldKey, options]) => {
        const byRaw = new Map();
        const byRawLower = new Map();
        const byDisplayLower = new Map();
        const byLabelLower = new Map();
        options.forEach(option => {
          const rawDisplay = profileComboRawDisplay(option.raw);
          const display = profileComboOptionDisplay(option, fieldKey);
          byRaw.set(option.raw, option);
          byRawLower.set(String(option.raw).toLowerCase(), option);
          const displayLower = String(display).toLowerCase();
          const rawDisplayLower = String(rawDisplay).toLowerCase();
          const labelLower = String(option.label).toLowerCase();
          if (!byDisplayLower.has(displayLower)) byDisplayLower.set(displayLower, option);
          if (!byDisplayLower.has(rawDisplayLower)) byDisplayLower.set(rawDisplayLower, option);
          if (!byLabelLower.has(labelLower)) byLabelLower.set(labelLower, option);
        });
        lookup.set(fieldKey, { byRaw, byRawLower, byDisplayLower, byLabelLower });
      });
      return lookup;
    }

    function profileEditField(item, fieldKey, options = {}) {
      const originalRaw = item.profile[fieldKey]?.raw ?? "0";
      const raw = pendingProfileValue(item.index, fieldKey, originalRaw);
      const changed = raw !== originalRaw;
      const label = options.label || profileFieldLabel(fieldKey);
      const hint = options.hint || PROFILE_FIELD_HINTS[fieldKey] || label;
      const classes = ["field", options.className || "", changed ? "changed" : ""].filter(Boolean).join(" ");
      return `
        <label class="${esc(classes)}" title="${esc(hint)}">
          ${profileFieldBadge(fieldKey, label)}
          <span class="field-label">${esc(label)}</span>
          <input class="profile-combo" type="text" value="${esc(profileComboDisplay(fieldKey, raw))}" data-class-index="${esc(item.index)}" data-field="${esc(fieldKey)}" data-original="${esc(originalRaw)}" autocomplete="off" role="combobox" aria-autocomplete="list" aria-expanded="false" title="${esc(hint)}">
        </label>
      `;
    }

    function profileEditSpawnDestinationTypeField(item) {
      const originalRaw = item.profile.spawnDestination?.raw ?? "0";
      const raw = pendingProfileValue(item.index, "spawnDestination", originalRaw);
      const changed = raw !== originalRaw;
      const label = "Spawn destination";
      return `
        <label class="field ${changed ? "changed" : ""}" title="${esc(label)}">
          ${profileFieldBadge(SPAWN_DESTINATION_TYPE_FIELD, label)}
          <span class="field-label">${esc(label)}</span>
          <input class="profile-combo" type="text" value="${esc(profileComboDisplay(SPAWN_DESTINATION_TYPE_FIELD, raw))}" data-class-index="${esc(item.index)}" data-field="${esc(SPAWN_DESTINATION_TYPE_FIELD)}" data-original="${esc(originalRaw)}" autocomplete="off" role="combobox" aria-autocomplete="list" aria-expanded="false" title="${esc(label)}">
        </label>
      `;
    }

    function profileEditSpawnDestinationDistanceField(item) {
      const originalRaw = item.profile.spawnDestination?.raw ?? "0";
      const raw = pendingProfileValue(item.index, "spawnDestination", originalRaw);
      const info = spawnDestinationPlayerInfo(raw);
      if (!info) return "";
      const typeKey = spawnDestinationTypeKeyForRaw(raw);
      const options = spawnDestinationDistanceOptions(typeKey);
      if (!options.length) return "";
      const changed = raw !== originalRaw;
      const label = "Spawn distance";
      return `
        <label class="field profile-suboption-field ${changed ? "changed" : ""}" title="${esc(label)}">
          ${profileFieldBadge("spawnDestinationDistance", label)}
          <span class="field-label">${esc(label)}</span>
          <select class="profile-subselect" data-profile-spawn-destination-distance data-class-index="${esc(item.index)}" data-original="${esc(originalRaw)}" aria-label="${esc(label)}" title="${esc(label)}">
            ${options.map(option => `
              <option value="${esc(option.distance)}"${option.distance === info.distance ? " selected" : ""}>${esc(option.distance)} tile${option.distance === 1 ? "" : "s"}</option>
            `).join("")}
          </select>
        </label>
      `;
    }

    function profileEditSpawnFields(item) {
      const originalRaw = item.profile.spawnDestination?.raw ?? "0";
      const raw = pendingProfileValue(item.index, "spawnDestination", originalRaw);
      const usesRadius = spawnDestinationUsesRadius(raw);
      const fields = [
        profileEditField(item, "spawnState"),
        profileEditSpawnDestinationTypeField(item),
      ];
      if (spawnDestinationNeedsDistance(raw)) {
        fields.push(profileEditField(item, "spawnDestinationMinDistance", {
          className: "profile-suboption-field",
          label: "Min distance",
          hint: usesRadius ? "Minimum radius around the player" : "Minimum tiles from the player",
        }));
        fields.push(profileEditField(item, "spawnDestinationMaxDistance", {
          className: "profile-suboption-field",
          label: "Max distance",
          hint: usesRadius ? "Maximum radius around the player" : "Maximum tiles from the player",
        }));
      }
      fields.push(profileEditField(item, "jumpLevel"));
      return {
        count: fields.length,
        html: fields.join(""),
      };
    }

    function profileEditAlertRangeTypeField(item) {
      const originalRaw = item.profile.alertRange?.raw ?? "0";
      const raw = pendingProfileValue(item.index, "alertRange", originalRaw);
      const changed = raw !== originalRaw;
      const label = "Range type";
      return `
        <label class="field ${changed ? "changed" : ""}" title="${esc(label)}">
          ${profileFieldBadge(ALERT_RANGE_TYPE_FIELD, label)}
          <span class="field-label">${esc(label)}</span>
          <input class="profile-combo" type="text" value="${esc(profileComboDisplay(ALERT_RANGE_TYPE_FIELD, raw))}" data-class-index="${esc(item.index)}" data-field="${esc(ALERT_RANGE_TYPE_FIELD)}" data-original="${esc(originalRaw)}" autocomplete="off" role="combobox" aria-autocomplete="list" aria-expanded="false" title="${esc(label)}">
        </label>
      `;
    }

    function profileEditAlertCloseRangeField(item) {
      const originalRaw = item.profile.alertRange?.raw ?? "0";
      const raw = pendingProfileValue(item.index, "alertRange", originalRaw);
      if (!alertRangeSupportsClose(raw)) return "";
      const changed = raw !== originalRaw;
      const label = "Close range";
      const closeEnabled = alertRangeIsCloseRaw(raw);
      return `
        <label class="field profile-suboption-field ${changed ? "changed" : ""}" title="${esc(label)}">
          ${profileFieldBadge("alertRangeClose", label)}
          <span class="field-label">${esc(label)}</span>
          <select class="profile-subselect" data-profile-alert-close-range data-class-index="${esc(item.index)}" data-original="${esc(originalRaw)}" aria-label="${esc(label)}" title="${esc(label)}">
            <option value="0"${closeEnabled ? "" : " selected"}>No</option>
            <option value="1"${closeEnabled ? " selected" : ""}>Yes</option>
          </select>
        </label>
      `;
    }

    function profileEditAlertFields(item) {
      const originalRaw = item.profile.alertRange?.raw ?? "0";
      const raw = pendingProfileValue(item.index, "alertRange", originalRaw);
      const originalSpecialRaw = item.profile.alertSpecialAction?.raw ?? "0";
      const specialRaw = pendingProfileValue(item.index, "alertSpecialAction", originalSpecialRaw);
      const fields = [
        profileEditField(item, "alertState"),
        profileEditField(item, "alertEmote"),
        profileEditField(item, "alertTime"),
        profileEditAlertRangeTypeField(item),
      ];
      if (alertRangeSupportsClose(raw)) {
        fields.push(profileEditAlertCloseRangeField(item));
      }
      if (alertRangeNeedsLength(raw)) {
        fields.push(profileEditField(item, "alertness", {
          className: "profile-suboption-field",
          label: "Range length",
          hint: "Range length",
        }));
      }
      fields.push(profileEditField(item, "alertChance"));
      fields.push(profileEditField(item, "alertSpecialAction"));
      if (alertSpecialActionCallsForHelp(specialRaw)) {
        fields.push(profileEditField(item, "alertCallSpawnAmount", {
          className: "profile-suboption-field",
          label: "Spawn amount",
          hint: "Number of same-species helpers to spawn when alert starts",
        }));
        fields.push(profileEditField(item, "alertCallSpawnState", {
          className: "profile-suboption-field",
          label: "Spawn state",
          hint: "Behavior state helpers enter after spawning",
        }));
      }
      return {
        count: fields.length,
        html: fields.join(""),
      };
    }

    function movementStyleUsesHop(raw) {
      return raw === "OW_WILD_BEHAVIOR_LOCOMOTION_HOP";
    }

    function movementStyleUsesPhantomTeleport(raw) {
      return raw === "OW_WILD_BEHAVIOR_LOCOMOTION_PHANTOM_TELEPORT";
    }

    function movementStyleUsesRam(raw) {
      return raw === "OW_WILD_BEHAVIOR_LOCOMOTION_RAM";
    }

    function activeBehaviorCanSelectTarget(raw) {
      return [
        "OW_WILD_BEHAVIOR_KIND_CHASE",
        "OW_WILD_BEHAVIOR_KIND_FLEE",
        "OW_WILD_BEHAVIOR_KIND_PLAYFUL",
        "OW_WILD_BEHAVIOR_KIND_RAM",
        "OW_WILD_BEHAVIOR_KIND_HEADBUTT_TREE_HOP",
      ].includes(raw);
    }

    function behaviorUsesAllowedTile(raw) {
      return [
        "OW_WILD_BEHAVIOR_KIND_WANDER",
        "OW_WILD_BEHAVIOR_KIND_CHASE",
        "OW_WILD_BEHAVIOR_KIND_FLEE",
        "OW_WILD_BEHAVIOR_KIND_PLAYFUL",
        "OW_WILD_BEHAVIOR_KIND_RAM",
        "OW_WILD_BEHAVIOR_KIND_HEADBUTT_TREE_HOP",
        "OW_WILD_BEHAVIOR_KIND_SINGING",
      ].includes(raw);
    }

    function movementStyleUsesMovement(raw) {
      return raw && raw !== "OW_WILD_BEHAVIOR_LOCOMOTION_NONE";
    }

    const PROFILE_MOVEMENT_SUBOPTION_FIELDS = {
      chill: {
        hopAllowNonCardinal: "hopAllowNonCardinal",
        hopMinDistance: "hopMinDistance",
        hopMaxDistance: "hopMaxDistance",
        hopPause: "hopPause",
        teleportTime: "teleportTime",
        teleportPause: "teleportPause",
        ramAccelerationSteps: "ramAccelerationSteps",
        ramMaxSpeed: "ramMaxSpeed",
      },
      attentive: {
        hopAllowNonCardinal: "attentiveHopAllowNonCardinal",
        hopMinDistance: "attentiveHopMinDistance",
        hopMaxDistance: "attentiveHopMaxDistance",
        hopPause: "attentiveHopPause",
        teleportTime: "attentiveTeleportTime",
        teleportPause: "attentiveTeleportPause",
        ramAccelerationSteps: "attentiveRamAccelerationSteps",
        ramMaxSpeed: "attentiveRamMaxSpeed",
      },
      tired: {
        hopAllowNonCardinal: "tiredHopAllowNonCardinal",
        hopMinDistance: "tiredHopMinDistance",
        hopMaxDistance: "tiredHopMaxDistance",
        hopPause: "tiredHopPause",
        teleportTime: "tiredTeleportTime",
        teleportPause: "tiredTeleportPause",
        ramAccelerationSteps: "tiredRamAccelerationSteps",
        ramMaxSpeed: "tiredRamMaxSpeed",
      },
    };

    function profileEditMovementFields(item, fieldKey, speedFieldKey = null, suboptionKey = "chill") {
      const originalRaw = item.profile[fieldKey]?.raw ?? "0";
      const raw = pendingProfileValue(item.index, fieldKey, originalRaw);
      const suboptionFields = PROFILE_MOVEMENT_SUBOPTION_FIELDS[suboptionKey] || PROFILE_MOVEMENT_SUBOPTION_FIELDS.chill;
      const fields = [
        profileEditField(item, fieldKey),
      ];
      if (speedFieldKey && movementStyleUsesMovement(raw)) {
        fields.push(profileEditField(item, speedFieldKey, {
          className: "profile-suboption-field",
          label: "Speed",
          hint: `${profileFieldLabel(fieldKey)} speed`,
        }));
      }
      if (movementStyleUsesHop(raw)) {
        fields.push(
          profileEditField(item, suboptionFields.hopAllowNonCardinal, {
            className: "profile-suboption-field",
            label: "Non-cardinal",
            hint: "Allow diagonal/non-cardinal hops",
          }),
          profileEditField(item, suboptionFields.hopMinDistance, {
            className: "profile-suboption-field",
            label: "Min distance",
            hint: "Minimum hop distance",
          }),
          profileEditField(item, suboptionFields.hopMaxDistance, {
            className: "profile-suboption-field",
            label: "Max distance",
            hint: "Maximum hop distance",
          }),
          profileEditField(item, suboptionFields.hopPause, {
            className: "profile-suboption-field",
            label: "Pause",
            hint: "Frames to wait after each Hop before the next movement decision. 0 keeps the existing/default pause.",
          }),
        );
      }
      if (movementStyleUsesPhantomTeleport(raw)) {
        fields.push(
          profileEditField(item, suboptionFields.teleportTime, {
            className: "profile-suboption-field",
            label: "Teleport time",
            hint: "Frames spent hidden/flickering during Phantom Teleport movement",
          }),
          profileEditField(item, suboptionFields.teleportPause, {
            className: "profile-suboption-field",
            label: "Pause time",
            hint: "Frames to wait after each Phantom Teleport before the next movement decision",
          }),
        );
      }
      if (movementStyleUsesRam(raw)) {
        fields.push(
          profileEditField(item, suboptionFields.ramAccelerationSteps, {
            className: "profile-suboption-field",
            label: "Accelerate every",
            hint: "Completed RAM steps before speed increases by 1. 0 disables acceleration.",
          }),
          profileEditField(item, suboptionFields.ramMaxSpeed, {
            className: "profile-suboption-field",
            label: "Max speed",
            hint: "Highest movement speed RAM can accelerate to. The state speed is the starting speed.",
          }),
        );
      }
      return {
        count: fields.length,
        html: fields.join(""),
      };
    }

    function profileEditChillFields(item) {
      const movementFields = profileEditMovementFields(item, "chillAction", "chillSpeed", "chill");
      const chillRaw = pendingProfileValue(
        item.index,
        "chillState",
        item.profile.chillState?.raw ?? "0",
      );
      const fields = [
        profileEditField(item, "chillState", { label: "Behavior" }),
      ];
      if (activeBehaviorCanSelectTarget(chillRaw)) {
        fields.push(profileEditField(item, "chillTarget", {
          className: "profile-suboption-field",
          label: "Target",
          hint: "Where this chill behavior tries to go. Movement style decides how it gets there.",
        }));
      }
      if (behaviorUsesAllowedTile(chillRaw)) {
        fields.push(profileEditField(item, "chillAllowedTile", {
          className: "profile-suboption-field",
          label: "Allowed tile",
          hint: "Tile type this behavior may target",
        }));
        fields.push(profileEditField(item, "chillAllowedTile2", {
          className: "profile-suboption-field",
          label: "Also allowed",
          hint: "Optional second tile type this behavior may target",
        }));
      }
      fields.push(movementFields.html);
      fields.push(profileEditField(item, "chillCooldown"));
      return {
        count: 2 + movementFields.count + (activeBehaviorCanSelectTarget(chillRaw) ? 1 : 0) + (behaviorUsesAllowedTile(chillRaw) ? 2 : 0),
        html: fields.join(""),
      };
    }

    function profileEditActiveFields(item) {
      const movementFields = profileEditMovementFields(item, "movementStyle", "attentiveSpeed", "attentive");
      const activeRaw = pendingProfileValue(
        item.index,
        "attentiveState",
        item.profile.attentiveState?.raw ?? "0",
      );
      const fields = [
        profileEditField(item, "attentiveState", { label: "Behavior" }),
      ];
      if (activeBehaviorCanSelectTarget(activeRaw)) {
        fields.push(profileEditField(item, "targetSelector", {
          className: "profile-suboption-field",
          label: "Target",
          hint: "Where this behavior tries to go. Movement style decides how it gets there.",
        }));
      }
      if (behaviorUsesAllowedTile(activeRaw)) {
        fields.push(profileEditField(item, "attentiveAllowedTile", {
          className: "profile-suboption-field",
          label: "Allowed tile",
          hint: "Tile type this behavior may target",
        }));
        fields.push(profileEditField(item, "attentiveAllowedTile2", {
          className: "profile-suboption-field",
          label: "Also allowed",
          hint: "Optional second tile type this behavior may target",
        }));
      }
      fields.push(movementFields.html);
      fields.push(profileEditField(item, "attentiveCooldown"));
      return {
        count: 2 + movementFields.count + (activeBehaviorCanSelectTarget(activeRaw) ? 1 : 0) + (behaviorUsesAllowedTile(activeRaw) ? 2 : 0),
        html: fields.join(""),
      };
    }

    function profileEditTiredFields(item) {
      const movementFields = profileEditMovementFields(item, "specialAction", "tiredSpeed", "tired");
      const tiredRaw = pendingProfileValue(
        item.index,
        "tiredState",
        item.profile.tiredState?.raw ?? "0",
      );
      const fields = [
        profileEditField(item, "tiredState", { label: "Behavior" }),
      ];
      if (behaviorUsesAllowedTile(tiredRaw)) {
        fields.push(profileEditField(item, "tiredAllowedTile", {
          className: "profile-suboption-field",
          label: "Allowed tile",
          hint: "Tile type this behavior may target",
        }));
        fields.push(profileEditField(item, "tiredAllowedTile2", {
          className: "profile-suboption-field",
          label: "Also allowed",
          hint: "Optional second tile type this behavior may target",
        }));
      }
      fields.push(movementFields.html);
      fields.push(profileEditField(item, "restTime"));
      fields.push(profileEditField(item, "stamina"));
      return {
        count: 3 + movementFields.count + (behaviorUsesAllowedTile(tiredRaw) ? 2 : 0),
        html: fields.join(""),
      };
    }

    function profileEditFieldGroups(item) {
      const known = new Set();
      const groups = PROFILE_FIELD_GROUPS.map(group => {
        const fields = group.fields.filter(field =>
          !PROFILE_DIRECT_EDIT_HIDDEN_FIELDS.has(field)
          && appData.fields.some(item => item.key === field));
        fields.forEach(field => known.add(field));
        if (!fields.length) return "";
        const spawnFields = group.key === "spawn" ? profileEditSpawnFields(item) : null;
        const chillFields = group.key === "chill" ? profileEditChillFields(item) : null;
        const alertFields = group.key === "alert" ? profileEditAlertFields(item) : null;
        const activeFields = group.key === "attentive" ? profileEditActiveFields(item) : null;
        const tiredFields = group.key === "tired" ? profileEditTiredFields(item) : null;
        const customFields = spawnFields || chillFields || alertFields || activeFields || tiredFields;
        return `
          <section class="profile-architecture-group profile-architecture-${esc(group.key)}">
            <div class="profile-architecture-head">
              <span class="profile-architecture-title">${encounterBadge(group.icon, group.typeClass, group.label)} ${esc(group.label)}</span>
              <span class="count">${esc(customFields ? customFields.count : fields.length)}</span>
            </div>
            <div class="profile-architecture-fields">
              ${customFields ? customFields.html : fields.map(field => profileEditField(item, field)).join("")}
            </div>
          </section>
        `;
      });
      const remaining = appData.fields.filter(field =>
        !known.has(field.key)
        && !PROFILE_DIRECT_EDIT_HIDDEN_FIELDS.has(field.key));
      if (remaining.length) {
        groups.push(`
          <section class="profile-architecture-group profile-architecture-other">
            <div class="profile-architecture-head">
              <span class="profile-architecture-title">${encounterBadge("target", "type-placement", "Other")} Other</span>
              <span class="count">${esc(remaining.length)}</span>
            </div>
            <div class="profile-architecture-fields">
              ${remaining.map(field => profileEditField(item, field.key)).join("")}
            </div>
          </section>
        `);
      }
      return groups.join("");
    }

    function profilePrimitiveGroups(item) {
      const primitives = item.primitives || {};
      if (!Object.keys(primitives).length) {
        return `<div class="empty">No primitive data</div>`;
      }
      return PRIMITIVE_GROUPS.map(group => {
        const chips = group.fields
          .filter(field => primitives[field])
          .map(field => `
            <span class="primitive-chip" title="${esc(primitiveFieldLabel(field))}: ${esc(primitives[field]?.raw || "")}">
              <strong>${esc(primitiveFieldLabel(field).replace(/^(Spawn|Chill|Alert|Attentive|Active|Tired) /, ""))}</strong>
              ${esc(fieldValue(primitives[field]))}
            </span>
          `).join("");
        if (!chips) return "";
        return `
          <div class="primitive-group primitive-${esc(group.key)}">
            ${encounterBadge(group.icon, group.typeClass, group.label)}
            <div class="primitive-values">${chips}</div>
          </div>
        `;
      }).join("");
    }

    function profileRuleList(item) {
      const rules = item.classRules || [];
      if (!rules.length) {
        return `<div class="empty">No direct class rules target this profile</div>`;
      }
      return `
        <div class="profile-rule-list">
          ${rules.map(rule => `
            <span class="profile-rule-chip" title="${esc(rule.behaviorClass?.raw || "")}">
              #${esc(rule.order)} ${esc(rule.summary)}
            </span>
          `).join("")}
        </div>
      `;
    }

    function profileEditFields(item) {
      return appData.fields.map(field => {
        const originalRaw = item.profile[field.key]?.raw ?? "0";
        const raw = pendingProfileValue(item.index, field.key, originalRaw);
        const changed = raw !== originalRaw;
        return `
          <label class="field ${changed ? "changed" : ""}">
            <span class="field-label">${esc(field.label)}</span>
            <input class="profile-combo" type="text" value="${esc(profileComboDisplay(field.key, raw))}" data-class-index="${esc(item.index)}" data-field="${esc(field.key)}" data-original="${esc(originalRaw)}" autocomplete="off" role="combobox" aria-autocomplete="list" aria-expanded="false">
          </label>
        `;
      }).join("");
    }

    function profileClassChanged(item) {
      const fieldChanged = appData.fields.some(field =>
        profileEdits.has(editKey(item.index, field.key))
      );
      if (fieldChanged) return true;
      for (const [symbol, classIndex] of profileMemberEdits.entries()) {
        const originalClass = assignmentsBySymbol.get(symbol)?.behaviorClass?.value;
        if (String(classIndex) === String(item.index) || String(originalClass) === String(item.index)) {
          return true;
        }
      }
      return false;
    }

    function profilePendingDisplay(item, fieldKey) {
      const originalRaw = item.profile[fieldKey]?.raw ?? "0";
      const raw = pendingProfileValue(item.index, fieldKey, originalRaw);
      return profileComboDisplay(fieldKey, raw);
    }

    function profileClassBadge(item) {
      const spawn = String(profilePendingDisplay(item, "spawnState") || "").toLowerCase();
      const profile = String(profilePendingDisplay(item, "profileId") || "").toLowerCase();
      if (spawn.includes("off screen") || spawn.includes("run")) {
        return encounterBadge("footstep", "type-movement", item.name);
      }
      if (profile.includes("wander") || profile.includes("roam")) {
        return encounterBadge("footstep", "type-movement", item.name);
      }
      if (profile.includes("idle") || profile.includes("calm")) {
        return encounterBadge("clock", "type-flow", item.name);
      }
      return encounterBadge("shield", "type-test", item.name);
    }

    function profileCoreChips(item) {
      const chips = [
        ["shield", "type-test", "Family", profilePendingDisplay(item, "profileId")],
        ["target", "type-placement", "Spawn", profilePendingDisplay(item, "spawnState")],
        ["speed", "type-movement", "Speed", `${profilePendingDisplay(item, "chillSpeed")} / ${profilePendingDisplay(item, "attentiveSpeed")} / ${profilePendingDisplay(item, "tiredSpeed")}`],
        ["ruler", "type-placement", "Range", profilePendingDisplay(item, "range")]
      ];
      return chips.map(([icon, typeClass, label, value]) => `
        <span class="profile-core-chip" title="${esc(label)}: ${esc(value)}">
          ${encounterBadge(icon, typeClass, label)}
          <span class="profile-core-value">${esc(value)}</span>
        </span>
      `).join("");
    }

    function profileManagementActions(item) {
      const renameDisabled = !item || item.canRename === false;
      const deleteDisabled = !item || item.canDelete === false;
      const deleteTitle = profileIsDefaultClass(item?.index)
        ? "Default profile cannot be deleted"
        : deleteDisabled
          ? "This profile is referenced by runtime code and cannot be deleted safely"
          : `Delete ${item.name}`;
      return `
        <span class="profile-management-actions" aria-label="Profile actions">
          <button class="profile-management-button" type="button" data-action="create-profile" title="New profile from Default" aria-label="New profile from Default">
            ${interfaceIcon("plus")}
          </button>
          <button class="profile-management-button" type="button" data-action="rename-profile" data-class-index="${esc(item?.index ?? "")}" ${renameDisabled ? "disabled" : ""} title="${renameDisabled ? "Default profile cannot be renamed" : `Rename ${esc(item.name)}`}" aria-label="Rename profile">
            ${interfaceIcon("edit")}
          </button>
          <button class="profile-management-button danger" type="button" data-action="delete-profile" data-class-index="${esc(item?.index ?? "")}" ${deleteDisabled ? "disabled" : ""} title="${esc(deleteTitle)}" aria-label="Delete profile">
            ${interfaceIcon("trash")}
          </button>
        </span>
      `;
    }

    function profileRowAddControl(item) {
      return `
        <button class="profile-row-add-button" type="button" data-action="quick-add-profile" data-class-index="${esc(item.index)}" aria-label="Add Pokemon to ${esc(item.name)}" title="Add Pokemon to ${esc(item.name)}">
          ${interfaceIcon("plus")}
        </button>
      `;
    }

    function profileIconStrip(assignments, limit = 42, profileItem = null) {
      const iconLimit = profileItem ? Math.max(0, limit - 1) : limit;
      const shown = assignments.slice(0, iconLimit);
      const rest = assignments.length - shown.length;
      return `
        ${shown.map(profileIconButton).join("")}
        ${profileItem ? profileRowAddControl(profileItem) : ""}
        ${rest > 0 ? `<span class="profile-more">+${esc(rest)}</span>` : ""}
      `;
    }

    function profileMemberChip(assignment, classIndex) {
      const species = assignment.species;
      const active = species.symbol === selectedSymbol ? " active" : "";
      const changed = profileMemberEdits.has(species.symbol) ? " changed" : "";
      const canRemove = !profileIsDefaultClass(classIndex);
      return `
        <span class="profile-member-item${changed}" data-symbol="${esc(species.symbol)}">
          <button class="profile-member-chip${active}${changed}" type="button" data-symbol="${esc(species.symbol)}" aria-label="View ${esc(species.name)}" title="${esc(species.symbol)}">
            ${iconTag(species, "profile-icon")}
            <span class="profile-member-name">${esc(species.name)}</span>
          </button>
          ${canRemove ? `
            <button class="profile-member-remove" type="button" data-action="remove-profile-member" data-symbol="${esc(species.symbol)}" data-class-index="${esc(classIndex)}" aria-label="Remove ${esc(species.name)} from this profile" title="Remove ${esc(species.name)} from this profile">
              ${interfaceIcon("minus")}
            </button>
          ` : ""}
        </span>
      `;
    }

    function profileMemberStrip(assignments, item, limit = 96) {
      const shown = assignments.slice(0, limit);
      const rest = assignments.length - shown.length;
      if (!assignments.length) {
        return `<div class="empty">No Pokemon currently resolve to this profile.</div>`;
      }
      return `
        <div class="profile-member-strip">
          ${shown.map(assignment => profileMemberChip(assignment, item.index)).join("")}
          ${rest > 0 ? `<span class="profile-more">+${esc(rest)}</span>` : ""}
        </div>
      `;
    }

    function profileAddControl(item) {
      return `
        <form class="profile-add-control" data-profile-add-form>
          <span class="profile-add-species-wrap">
            ${encounterBadge("plus", "type-test", "Add Pokemon")}
            <input class="profile-add-input" type="text" list="profileSpeciesOptions" placeholder="Add Pokemon" autocomplete="off" aria-label="Add Pokemon to ${esc(item.name)}">
          </span>
          <button class="control profile-add-button" type="submit" title="Add Pokemon to ${esc(item.name)}">
            ${interfaceIcon("plus")}
            <span>Add</span>
          </button>
        </form>
      `;
    }

    function profileTypeOption(typeSymbol) {
      return (appData.typeOptions || []).find(type => type.symbol === typeSymbol) || null;
    }

    function profileValidBulkType() {
      return profileTypeOption(profileBulkType) ? profileBulkType : "";
    }

    function profileSpeciesHasType(species, typeSymbol) {
      return (species.types || []).some(type => type.symbol === typeSymbol);
    }

    function profileBulkTypeMatches(typeSymbol) {
      if (!typeSymbol) return [];
      return appData.assignments
        .map(assignment => assignment.species)
        .filter(species => species.symbol !== "SPECIES_NONE" && profileSpeciesHasType(species, typeSymbol));
    }

    function profileBulkAssignableSpecies(item, typeSymbol) {
      return profileBulkTypeMatches(typeSymbol).filter(species =>
        String(profilePendingClassValueForSymbol(species.symbol)) !== String(item.index)
      );
    }

    function profileBulkTypeOptionsHtml(selectedType) {
      return `
        <option value="">Type</option>
        ${(appData.typeOptions || []).map(type => `
          <option value="${esc(type.symbol)}"${type.symbol === selectedType ? " selected" : ""}>${esc(type.name)}</option>
        `).join("")}
      `;
    }

    function profileBulkPreviewHtml(matches, assignable) {
      if (!profileValidBulkType()) {
        return `<span class="profile-bulk-empty">Choose a type to preview matching Pokemon</span>`;
      }
      if (!matches.length) {
        return `<span class="profile-bulk-empty">No matching Pokemon</span>`;
      }
      const preview = matches.slice(0, 28);
      const rest = matches.length - preview.length;
      const moving = assignable.length;
      return `
        ${preview.map(species => iconTag(species, "profile-icon")).join("")}
        ${rest > 0 ? `<span class="profile-more">+${esc(rest)}</span>` : ""}
        <span class="chip neutral">${esc(matches.length)} match${matches.length === 1 ? "" : "es"}</span>
        <span class="chip">${esc(moving)} move${moving === 1 ? "" : "s"}</span>
      `;
    }

    function profileBulkAssignControl(item) {
      const selectedType = profileValidBulkType();
      const matches = profileBulkTypeMatches(selectedType);
      const assignable = profileBulkAssignableSpecies(item, selectedType);
      const selected = profileTypeOption(selectedType);
      const title = selected ? `Assign ${selected.name} Pokemon to ${item.name}` : `Assign Pokemon by type to ${item.name}`;
      return `
        <div class="profile-bulk-assign">
          <label class="profile-bulk-select-wrap" title="Assign Pokemon by type">
            ${encounterBadge("target", "type-placement", "Assign by type")}
            <select class="profile-bulk-type" data-profile-bulk-type aria-label="Pokemon type">
              ${profileBulkTypeOptionsHtml(selectedType)}
            </select>
          </label>
          <div class="profile-bulk-preview">${profileBulkPreviewHtml(matches, assignable)}</div>
          <button class="control profile-bulk-assign-button primary-action" type="button" data-action="bulk-assign-type" data-class-index="${esc(item.index)}" ${assignable.length ? "" : "disabled"} title="${esc(title)}">
            ${interfaceIcon("plus")}
            <span>${esc(assignable.length ? `Assign ${assignable.length}` : "Assign")}</span>
          </button>
        </div>
      `;
    }

    function profileOverrideTargetKindOption(kind) {
      return PROFILE_OVERRIDE_TARGET_KINDS.find(option => option.key === kind) || null;
    }

    function profileValidOverrideTargetKind() {
      return profileOverrideTargetKindOption(profileOverrideDraftTargetKind)
        ? profileOverrideDraftTargetKind
        : "type";
    }

    function profileValidOverrideType() {
      return profileTypeOption(profileOverrideDraftType) ? profileOverrideDraftType : ((appData.typeOptions || [])[0]?.symbol || "");
    }

    function profileSpawnPoolOption(raw) {
      return PROFILE_OVERRIDE_SPAWN_POOLS.find(pool => pool.raw === raw || pool.key === raw) || null;
    }

    function profileValidOverrideSpawnPool() {
      return profileSpawnPoolOption(profileOverrideDraftSpawnPool)?.raw || PROFILE_OVERRIDE_SPAWN_POOLS[0].raw;
    }

    function profileOverrideFieldOption(fieldKey) {
      if (PROFILE_OVERRIDE_BUILDER_HIDDEN_FIELDS.has(fieldKey)) return null;
      return (appData.fields || []).find(field => field.key === fieldKey) || null;
    }

    function profileValidOverrideField() {
      return profileOverrideFieldOption(profileOverrideDraftField)
        ? profileOverrideDraftField
        : (profileOverrideFieldOption("spawnState")
          ? "spawnState"
          : ((appData.fields || []).find(field => !PROFILE_OVERRIDE_BUILDER_HIDDEN_FIELDS.has(field.key))?.key || ""));
    }

    function profileValidOverrideRaw(fieldKey = profileValidOverrideField()) {
      const options = profileOptionsForField(fieldKey);
      if (options.some(option => option.raw === profileOverrideDraftRaw)) return profileOverrideDraftRaw;
      return options[0]?.raw || "";
    }

    function persistProfileOverrideDraft() {
      localStorage.setItem("owProfileOverrideTargetKind", profileOverrideDraftTargetKind || "");
      localStorage.setItem("owProfileOverrideType", profileOverrideDraftType || "");
      localStorage.setItem("owProfileOverrideSpawnPool", profileOverrideDraftSpawnPool || "");
      localStorage.setItem("owProfileOverrideField", profileOverrideDraftField || "");
      localStorage.setItem("owProfileOverrideRaw", profileOverrideDraftRaw || "");
    }

    function normalizeProfileOverrideDraft() {
      profileOverrideDraftTargetKind = profileValidOverrideTargetKind();
      profileOverrideDraftType = profileValidOverrideType();
      profileOverrideDraftSpawnPool = profileValidOverrideSpawnPool();
      profileOverrideDraftField = profileValidOverrideField();
      profileOverrideDraftRaw = profileValidOverrideRaw(profileOverrideDraftField);
      persistProfileOverrideDraft();
      const targetKind = profileOverrideTargetKindOption(profileOverrideDraftTargetKind);
      const type = profileTypeOption(profileOverrideDraftType);
      const spawnPool = profileSpawnPoolOption(profileOverrideDraftSpawnPool);
      return {
        targetKind: profileOverrideDraftTargetKind,
        targetKindLabel: targetKind?.label || "Type",
        targetValue: profileOverrideDraftTargetKind === "spawnPool" ? profileOverrideDraftSpawnPool : profileOverrideDraftType,
        targetLabel: profileOverrideDraftTargetKind === "spawnPool" ? (spawnPool?.label || "Spawn pool") : (type?.name || "Type"),
        typeSymbol: profileOverrideDraftType,
        type,
        spawnPool,
        fieldKey: profileOverrideDraftField,
        field: profileOverrideFieldOption(profileOverrideDraftField),
        raw: profileOverrideDraftRaw,
        value: profileOptionForRaw(profileOverrideDraftField, profileOverrideDraftRaw),
      };
    }

    function typeGroupSymbol(typeSymbol) {
      return `OW_WILD_BEHAVIOR_GROUP_TYPE_${String(typeSymbol || "").replace(/^TYPE_/, "")}`;
    }

    function profileOverrideMatchForType(typeSymbol) {
      return {
        species: "OW_WILD_BEHAVIOR_MATCH_ANY_SPECIES",
        groupMask: typeGroupSymbol(typeSymbol),
        terrain: "OW_WILD_BEHAVIOR_MATCH_ANY_TERRAIN",
        minLevel: "OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY",
        maxLevel: "OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY",
        shiny: "OW_WILD_BEHAVIOR_MATCH_ANY_SHINY",
        behaviorClass: "OW_WILD_BEHAVIOR_MATCH_ANY_CLASS",
      };
    }

    function profileOverrideMatchForSpawnPool(pool) {
      return {
        species: "OW_WILD_BEHAVIOR_MATCH_ANY_SPECIES",
        groupMask: "OW_WILD_BEHAVIOR_GROUP_NONE",
        terrain: pool?.raw || "OW_WILD_BEHAVIOR_MATCH_ANY_TERRAIN",
        minLevel: "OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY",
        maxLevel: "OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY",
        shiny: "OW_WILD_BEHAVIOR_MATCH_ANY_SHINY",
        behaviorClass: "OW_WILD_BEHAVIOR_MATCH_ANY_CLASS",
      };
    }

    function profileOverrideMatchForTarget(draft) {
      return draft.targetKind === "spawnPool"
        ? profileOverrideMatchForSpawnPool(draft.spawnPool)
        : profileOverrideMatchForType(draft.typeSymbol);
    }

    function profileOverrideSpawnPoolMatches(pool) {
      if (!pool?.routeGroups?.length || !appData?.routes?.length) return [];
      const routeGroupKeys = new Set(pool.routeGroups);
      const seen = new Set();
      const matches = [];
      appData.routes.forEach(route => {
        routeEncounterGroups(route).forEach(group => {
          if (!routeGroupKeys.has(group.key)) return;
          group.species.forEach(species => {
            if (!species || species.symbol === "SPECIES_NONE" || seen.has(species.symbol)) return;
            seen.add(species.symbol);
            matches.push(species);
          });
        });
      });
      return matches;
    }

    function profileOverridePreviewHtml(draft) {
      if (draft.targetKind === "spawnPool") {
        const pool = draft.spawnPool;
        if (!pool) {
          return `<span class="profile-bulk-empty">Choose a spawn pool</span>`;
        }
        const matches = profileOverrideSpawnPoolMatches(pool);
        const preview = matches.slice(0, 34);
        const rest = matches.length - preview.length;
        return `
          ${encounterBadge(pool.icon, pool.typeClass, pool.label)}
          <span class="chip">${esc(pool.label)}</span>
          ${preview.map(species => iconTag(species, "profile-icon")).join("")}
          ${rest > 0 ? `<span class="profile-more">+${esc(rest)}</span>` : ""}
          <span class="chip neutral">${esc(matches.length ? `${matches.length} seen in routes` : "terrain match")}</span>
        `;
      }
      if (!draft.typeSymbol) {
        return `<span class="profile-bulk-empty">Choose a type</span>`;
      }
      const matches = profileBulkTypeMatches(draft.typeSymbol);
      if (!matches.length) {
        return `<span class="profile-bulk-empty">No matching Pokemon</span>`;
      }
      const preview = matches.slice(0, 34);
      const rest = matches.length - preview.length;
      return `
        ${preview.map(species => iconTag(species, "profile-icon")).join("")}
        ${rest > 0 ? `<span class="profile-more">+${esc(rest)}</span>` : ""}
        <span class="chip neutral">${esc(matches.length)} match${matches.length === 1 ? "" : "es"}</span>
      `;
    }

    function profileOverrideTargetKindOptionsHtml(selectedKind) {
      return PROFILE_OVERRIDE_TARGET_KINDS.map(option => `
        <option value="${esc(option.key)}"${option.key === selectedKind ? " selected" : ""}>${esc(option.label)}</option>
      `).join("");
    }

    function profileOverrideTargetOptionsHtml(draft) {
      if (draft.targetKind === "spawnPool") {
        return PROFILE_OVERRIDE_SPAWN_POOLS.map(pool => `
          <option value="${esc(pool.raw)}"${pool.raw === draft.targetValue ? " selected" : ""}>${esc(pool.label)}</option>
        `).join("");
      }
      return (appData.typeOptions || []).map(type => `
        <option value="${esc(type.symbol)}"${type.symbol === draft.typeSymbol ? " selected" : ""}>${esc(type.name)}</option>
      `).join("");
    }

    function profileOverrideFieldOptionsHtml(selectedField) {
      return (appData.fields || [])
        .filter(field => !PROFILE_OVERRIDE_BUILDER_HIDDEN_FIELDS.has(field.key))
        .map(field => `
        <option value="${esc(field.key)}"${field.key === selectedField ? " selected" : ""}>${esc(field.label)}</option>
      `).join("");
    }

    function profileOverrideValueOptionsHtml(fieldKey, selectedRaw) {
      return profileOptionsForField(fieldKey).map(option => `
        <option value="${esc(option.raw)}"${option.raw === selectedRaw ? " selected" : ""}>${esc(profileComboOptionDisplay(option, fieldKey))}</option>
      `).join("");
    }

    function profileOverrideBuilderHtml() {
      const draft = normalizeProfileOverrideDraft();
      const matches = draft.targetKind === "spawnPool"
        ? [draft.spawnPool].filter(Boolean)
        : profileBulkTypeMatches(draft.typeSymbol);
      const title = draft.field && draft.value && draft.targetLabel
        ? `Override ${draft.field.label} for ${draft.targetLabel}`
        : "Choose a type, field, and value";
      return `
        <div class="behavior-override-builder">
          <select class="behavior-override-select" data-profile-override-target-kind aria-label="Override target kind" title="Override target kind">
            ${profileOverrideTargetKindOptionsHtml(draft.targetKind)}
          </select>
          <select class="behavior-override-select" data-profile-override-target aria-label="Override target" title="Override target">
            ${profileOverrideTargetOptionsHtml(draft)}
          </select>
          <select class="behavior-override-select" data-profile-override-field aria-label="Override field" title="Override field">
            ${profileOverrideFieldOptionsHtml(draft.fieldKey)}
          </select>
          <select class="behavior-override-select" data-profile-override-value aria-label="Override value" title="Override value">
            ${profileOverrideValueOptionsHtml(draft.fieldKey, draft.raw)}
          </select>
          <div class="behavior-override-preview">${profileOverridePreviewHtml(draft)}</div>
          <button class="control primary-action behavior-override-add" type="button" data-action="add-profile-override" ${matches.length && draft.raw ? "" : "disabled"} title="${esc(title)}">
            ${interfaceIcon("plus")}
            <span>Add rule</span>
          </button>
        </div>
      `;
    }

    function addProfileOverrideDraft() {
      const draft = normalizeProfileOverrideDraft();
      if ((draft.targetKind === "spawnPool" ? !draft.spawnPool : !draft.type) || !draft.field || !draft.value) {
        setSaveStatus("Choose a valid target, field, and value", "error");
        updateSaveControls();
        return;
      }
      const matches = draft.targetKind === "spawnPool"
        ? [draft.spawnPool]
        : profileBulkTypeMatches(draft.typeSymbol);
      if (!matches.length && draft.targetKind !== "spawnPool") {
        setSaveStatus(`No ${draft.type.name} Pokemon found`, "error");
        updateSaveControls();
        return;
      }
      profileOverrideEdits.push({
        id: `${Date.now()}-${profileOverrideEdits.length}`,
        targetKind: draft.targetKind,
        targetValue: draft.targetValue,
        targetName: draft.targetLabel,
        field: draft.fieldKey,
        fieldLabel: draft.field.label,
        raw: draft.raw,
        valueLabel: profileComboOptionDisplay(draft.value, draft.fieldKey),
        match: profileOverrideMatchForTarget(draft),
        matchCount: draft.targetKind === "spawnPool"
          ? profileOverrideSpawnPoolMatches(draft.spawnPool).length
          : matches.length,
      });
      markProfilePanelsDirty("rules");
      renderActiveProfilePanel(true);
      updateGlobalEditStatus();
    }

    function removeProfileOverrideDraft(id) {
      profileOverrideEdits = profileOverrideEdits.filter(edit => edit.id !== id);
      markProfilePanelsDirty("rules");
      renderActiveProfilePanel(true);
      updateGlobalEditStatus();
    }

    function toggleProfileOverrideRemoval(order) {
      const key = String(order);
      if (profileOverrideRemoveEdits.has(key)) {
        profileOverrideRemoveEdits.delete(key);
      } else {
        profileOverrideRemoveEdits.add(key);
      }
      markProfilePanelsDirty("rules");
      renderActiveProfilePanel(true);
      updateGlobalEditStatus();
    }

    function profileOverrideChangeCount() {
      return profileOverrideEdits.length + profileOverrideRemoveEdits.size;
    }

    function profileOverrideChangePayload() {
      return {
        add: profileOverrideEdits.map(edit => ({
          match: edit.match,
          field: edit.field,
          raw: edit.raw,
        })),
        remove: Array.from(profileOverrideRemoveEdits).map(order => Number(order)),
      };
    }

    function profileOverridePendingHtml() {
      if (!profileOverrideEdits.length) return "";
      return `
        <div class="behavior-override-pending">
          ${profileOverrideEdits.map(edit => `
            <div class="behavior-override-pending-row">
              <div>
                ${encounterBadge("target", "type-placement", "Pending override")}
                <span>${esc(edit.targetName || edit.typeName)} -> ${esc(edit.fieldLabel)}: ${esc(edit.valueLabel)}</span>
                <span class="meta">${esc(edit.targetKind === "spawnPool" ? "spawn pool" : `${edit.matchCount} Pokemon`)}</span>
              </div>
              <button class="control subtle-action" type="button" data-action="remove-profile-override" data-override-id="${esc(edit.id)}" title="Remove pending override">Remove</button>
            </div>
          `).join("")}
        </div>
      `;
    }

    function profileOverrideRuleHtml(rule) {
      const removing = profileOverrideRemoveEdits.has(String(rule.order));
      return `
        <div class="rule behavior-override-rule ${removing ? "pending-remove" : ""}">
          <div>
            <div class="rule-top"><span>#${esc(rule.order)} ${esc(rule.summary)}</span><span>${esc((rule.behavior.maskLabels || rule.behavior.mask.labels || []).join(", "))}</span></div>
            <div class="muted">${esc(rule.behavior.maskRaw || rule.behavior.mask.raw)}${removing ? " · pending removal" : ""}</div>
          </div>
          <button class="control subtle-action behavior-override-remove" type="button" data-action="toggle-remove-profile-override" data-override-order="${esc(rule.order)}" title="${removing ? "Undo override removal" : "Remove override"}" aria-label="${removing ? "Undo removing override" : "Remove override"} #${esc(rule.order)}">
            ${interfaceIcon(removing ? "plus" : "minus")}
          </button>
        </div>
      `;
    }

    function classRuleIdentity(rule) {
      const behaviorClass = rule?.behaviorClass || {};
      return behaviorClass.value ?? behaviorClass.raw ?? rule?.className ?? "";
    }

    function classRuleOrderLabel(rules) {
      const first = rules[0]?.order;
      const last = rules[rules.length - 1]?.order;
      if (rules.length <= 1 || String(first) === String(last)) return `#${first}`;
      const numericFirst = Number(first);
      const numericLast = Number(last);
      if (Number.isFinite(numericFirst) && Number.isFinite(numericLast) && numericLast - numericFirst + 1 === rules.length) {
        return `#${first}-${last}`;
      }
      return `${rules.length} rules`;
    }

    function groupedClassRules(rules) {
      const groups = [];
      rules.forEach(rule => {
        const key = classRuleIdentity(rule);
        const current = groups[groups.length - 1];
        if (current && current.key === key) {
          current.rules.push(rule);
        } else {
          groups.push({ key, rules: [rule] });
        }
      });
      return groups;
    }

    function classRuleSpecies(rule) {
      const species = rule?.match?.species;
      const symbol = species?.symbol || "";
      if (!symbol || symbol === "SPECIES_NONE" || symbol.startsWith("OW_WILD_BEHAVIOR_MATCH_ANY_")) return null;
      return profileSpeciesBySymbol.get(symbol) || {
        symbol,
        name: species.label || profileComboRawDisplay(symbol),
        iconUrl: species.iconUrl || "",
      };
    }

    function classRuleMemberHtml(rule, compact = false) {
      const species = classRuleSpecies(rule);
      if (species) {
        if (compact) {
          return `
            <span class="class-rule-member compact" title="#${esc(rule.order)} ${esc(species.name)}">
              ${profileIconButton({ species })}
            </span>
          `;
        }
        return `
          <span class="class-rule-member" title="#${esc(rule.order)} ${esc(species.name)}">
            <span class="class-rule-member-order">#${esc(rule.order)}</span>
            ${profileIconButton({ species })}
            <span class="class-rule-member-summary">${esc(species.name)}</span>
          </span>
        `;
      }
      return `
        <span class="class-rule-member" title="#${esc(rule.order)} ${esc(rule.summary)}">
          <span class="class-rule-member-order">#${esc(rule.order)}</span>
          <span class="class-rule-member-summary">${esc(rule.summary)}</span>
        </span>
      `;
    }

    function classRuleGroupHtml(group) {
      const rules = group.rules;
      const first = rules[0];
      const compactMembers = rules.length > 12;
      if (rules.length === 1) {
        return `
          <div class="rule">
            <div class="rule-top"><span>#${esc(first.order)} ${esc(first.summary)}</span><span>${esc(first.className)}</span></div>
            <div class="muted">${esc(first.behaviorClass.raw)}</div>
          </div>
        `;
      }
      return `
        <div class="rule class-rule-group">
          <div class="class-rule-group-head">
            <div class="class-rule-group-title">
              <span>${esc(classRuleOrderLabel(rules))} ${esc(first.className)}</span>
              <span class="muted">${esc(rules.length)} rule${rules.length === 1 ? "" : "s"}</span>
            </div>
            <span class="chip neutral">${esc(first.className)}</span>
          </div>
          <div class="class-rule-members">
            ${rules.map(rule => classRuleMemberHtml(rule, compactMembers)).join("")}
          </div>
          <div class="muted">${esc(first.behaviorClass.raw)}</div>
        </div>
      `;
    }

    function profileSpeciesOption(text) {
      const value = String(text || "").trim();
      if (!value) return null;
      const upper = value.toUpperCase();
      const prefixed = upper.startsWith("SPECIES_") ? upper : `SPECIES_${upper}`;
      const compact = value.toLowerCase().replace(/[^a-z0-9]/g, "");
      return profileSpeciesBySymbol.get(value)
        || profileSpeciesBySymbol.get(upper)
        || profileSpeciesBySymbol.get(prefixed)
        || profileSpeciesByName.get(value.toLowerCase())
        || profileSpeciesByCompactName.get(compact)
        || null;
    }

    function profilePendingClassValueForSymbol(symbol) {
      if (profileMemberEdits.has(symbol)) {
        return Number(profileMemberEdits.get(symbol));
      }
      return assignmentsBySymbol.get(symbol)?.behaviorClass?.value;
    }

    function profileDefaultClassIndex() {
      const defaultIndex = Number(appData.defaultClassIndex);
      if (Number.isFinite(defaultIndex)) return defaultIndex;
      return appData.classes[0]?.index ?? 0;
    }

    function profileIsDefaultClass(classIndex) {
      return String(classIndex) === String(profileDefaultClassIndex());
    }

    function profileAssignmentsForClass(classIndex) {
      return appData.assignments.filter(item =>
        String(profilePendingClassValueForSymbol(item.species.symbol)) === String(classIndex)
      );
    }

    function profileClassSearchText(item, assignments) {
      const primitiveText = Object.values(item.primitives || {})
        .map(value => `${value.label || ""} ${value.raw || ""}`)
        .join(" ");
      return [
        item.name,
        item.symbol,
        profilePendingDisplay(item, "profileId"),
        profilePendingDisplay(item, "spawnState"),
        appData.fields.map(field => `${field.label} ${fieldValue(item.profile[field.key])}`).join(" "),
        (item.classRules || []).map(rule => rule.summary).join(" "),
        primitiveText,
        assignments.map(assignmentSearchText).join(" ")
      ].join(" ").toLowerCase();
    }

    function assignmentSearchText(item) {
      return [
        item.species.name,
        item.species.symbol,
        item.behaviorClass.name,
        item.behaviorClass.symbol,
        item.groups.join(" "),
        item.classRuleHits.map(rule => rule.summary).join(" "),
        (item.maxSpeedOverrideHits || item.variableOverrideHits || []).map(rule => rule.summary).join(" ")
      ].join(" ").toLowerCase();
    }

    function compactSearchText(value) {
      return String(value || "").toLowerCase().replace(/[^a-z0-9]/g, "");
    }

    function speciesTypeSearchTerms(species) {
      return (species?.types || []).flatMap(type => {
        const name = type.name || "";
        const symbol = type.symbol || "";
        const shortSymbol = symbol.replace(/^TYPE_/, "");
        return [
          name,
          symbol,
          shortSymbol,
          `${name} type`,
          `type ${name}`,
          `${shortSymbol} type`,
          `type ${shortSymbol}`,
        ];
      });
    }

    function speciesSearchText(species) {
      return [
        species.name,
        species.symbol,
        (species.aliases || []).join(" "),
        speciesTypeSearchTerms(species).join(" "),
      ].join(" ").toLowerCase();
    }

    function routeTypeSearchMatch(query) {
      const raw = String(query || "").trim().toLowerCase();
      if (!raw || !appData?.typeOptions?.length) return null;
      const stripped = raw.replace(/^(type|typing)\s*[:=]\s*/, "").trim();
      const compact = compactSearchText(stripped);
      return appData.typeOptions.find(type => {
        const name = type.name || "";
        const symbol = type.symbol || "";
        const shortSymbol = symbol.replace(/^TYPE_/, "");
        const terms = [
          name,
          symbol,
          shortSymbol,
          `${name} type`,
          `type ${name}`,
          `${shortSymbol} type`,
          `type ${shortSymbol}`,
          `type:${name}`,
          `type:${shortSymbol}`,
          `typing:${name}`,
          `typing:${shortSymbol}`,
        ];
        return terms.some(term => {
          const lower = String(term || "").toLowerCase();
          return lower === raw || lower === stripped || compactSearchText(lower) === compact;
        });
      }) || null;
    }

    function routeSearchInfo(query = els.routeSearch?.value || "") {
      const normalized = String(query || "").trim().toLowerCase();
      return {
        query: normalized,
        type: routeTypeSearchMatch(normalized),
      };
    }

    function speciesHasType(species, typeSymbol) {
      return (species?.types || []).some(type => type.symbol === typeSymbol);
    }

    function routeSpeciesMatchesSearch(species, searchInfo = routeSearchInfo()) {
      const info = typeof searchInfo === "string" ? routeSearchInfo(searchInfo) : searchInfo;
      if (!info?.query || !species || species.symbol === "SPECIES_NONE") return false;
      if (info.type) return speciesHasType(species, info.type.symbol);
      return speciesSearchText(species).includes(info.query);
    }

    function routeGroupHasSearchMatch(group, searchInfo = routeSearchInfo()) {
      const info = typeof searchInfo === "string" ? routeSearchInfo(searchInfo) : searchInfo;
      if (!info?.query) return false;
      return (group.species || []).some(species => routeSpeciesMatchesSearch(species, info));
    }

    function routeIdentitySearchText(route) {
      return [
        route.id,
        route.name,
        route.maps.map(map => `${map.name} ${map.symbol}`).join(" ")
      ].join(" ").toLowerCase();
    }

    function routeGroupSearchText(group) {
      return [
        group.key,
        group.label,
        group.title,
        group.species.map(speciesSearchText).join(" ")
      ].join(" ").toLowerCase();
    }

    function routeSearchText(route) {
      return [
        routeIdentitySearchText(route),
        routeEncounterGroups(route).map(routeGroupSearchText).join(" ")
      ].join(" ").toLowerCase();
    }

    function prepareData() {
      assignmentsBySymbol = new Map();
      profileAssignmentsByClass = new Map(appData.classes.map(item => [item.index, []]));
      routesById = new Map();
      routeSpeciesBySymbol = new Map();
      routeSpeciesByName = new Map();
      routeSpeciesByCompactName = new Map();
      routeSpeciesByBaseForm = new Map();
      profileSpeciesBySymbol = new Map();
      profileSpeciesByName = new Map();
      profileSpeciesByCompactName = new Map();
      spawnSettingsBySymbol = new Map();
      profileOptionLookupByField = buildProfileOptionLookup();
      profileDatalistsHtml = profileDatalists();
      profileSpeciesDatalistHtml = "";
      routeSpeciesDatalistHtml = routeSpeciesDatalist();
      routeSpeciesDatalistRendered = false;
      renderedProfilePanels.clear();
      dirtyProfilePanels = new Set(["profiles", "selected", "rules"]);
      invalidProfileInputs.clear();
      invalidEncounterInputs.clear();
      invalidSpawnSettingInputs.clear();
      visibleSpeciesRowsBySymbol.clear();
      visibleProfileRowsByClass.clear();
      profileIconButtonsBySymbol.clear();
      if (!appData.profilesAvailable) {
        profileEdits.clear();
        profileMemberEdits.clear();
        selectedSymbol = null;
        selectedClassIndex = null;
      }
      appData.speciesOptions.forEach(species => {
        routeSpeciesBySymbol.set(species.symbol, species);
        routeSpeciesBySymbol.set(routeSpeciesShortSymbol(species.symbol).toUpperCase(), species);
        (species.aliases || []).forEach(alias => {
          routeSpeciesBySymbol.set(alias, species);
          routeSpeciesBySymbol.set(routeSpeciesShortSymbol(alias).toUpperCase(), species);
          routeSpeciesByCompactName.set(routeSpeciesShortSymbol(alias).toLowerCase().replace(/[^a-z0-9]/g, ""), species);
        });
        routeSpeciesByName.set(species.name.toLowerCase(), species);
        routeSpeciesByCompactName.set(species.name.toLowerCase().replace(/[^a-z0-9]/g, ""), species);
        routeSpeciesByCompactName.set(routeSpeciesShortSymbol(species.symbol).toLowerCase().replace(/[^a-z0-9]/g, ""), species);
        if (species.symbol !== "SPECIES_NONE") {
          profileSpeciesBySymbol.set(species.symbol, species);
          profileSpeciesBySymbol.set(routeSpeciesShortSymbol(species.symbol).toUpperCase(), species);
          profileSpeciesByName.set(species.name.toLowerCase(), species);
          profileSpeciesByCompactName.set(species.name.toLowerCase().replace(/[^a-z0-9]/g, ""), species);
          profileSpeciesByCompactName.set(routeSpeciesShortSymbol(species.symbol).toLowerCase().replace(/[^a-z0-9]/g, ""), species);
          (species.aliases || []).forEach(alias => {
            profileSpeciesBySymbol.set(alias, species);
            profileSpeciesBySymbol.set(routeSpeciesShortSymbol(alias).toUpperCase(), species);
            profileSpeciesByCompactName.set(routeSpeciesShortSymbol(alias).toLowerCase().replace(/[^a-z0-9]/g, ""), species);
          });
        }
        if (species.baseSymbol && species.form !== undefined && species.form !== null) {
          routeSpeciesByBaseForm.set(routeBaseFormKey(species.baseSymbol, species.form), species);
        }
      });
      appData.spawnSettings.forEach(group => {
        group.settings.forEach(setting => {
          spawnSettingsBySymbol.set(setting.symbol, setting);
          (setting.fields || []).forEach(field => {
            spawnSettingsBySymbol.set(field.symbol, { ...field, parentSymbol: setting.symbol });
          });
        });
      });
      appData.assignments.forEach(item => {
        item.searchText = assignmentSearchText(item);
        assignmentsBySymbol.set(item.species.symbol, item);
        profileSpeciesBySymbol.set(item.species.symbol, item.species);
        profileSpeciesBySymbol.set(routeSpeciesShortSymbol(item.species.symbol).toUpperCase(), item.species);
        profileSpeciesByName.set(item.species.name.toLowerCase(), item.species);
        profileSpeciesByCompactName.set(item.species.name.toLowerCase().replace(/[^a-z0-9]/g, ""), item.species);
        profileSpeciesByCompactName.set(routeSpeciesShortSymbol(item.species.symbol).toLowerCase().replace(/[^a-z0-9]/g, ""), item.species);
        (item.species.aliases || []).forEach(alias => {
          profileSpeciesBySymbol.set(alias, item.species);
          profileSpeciesBySymbol.set(routeSpeciesShortSymbol(alias).toUpperCase(), item.species);
          profileSpeciesByCompactName.set(routeSpeciesShortSymbol(alias).toLowerCase().replace(/[^a-z0-9]/g, ""), item.species);
        });
        if (!profileAssignmentsByClass.has(item.behaviorClass.value)) {
          profileAssignmentsByClass.set(item.behaviorClass.value, []);
        }
        profileAssignmentsByClass.get(item.behaviorClass.value).push(item);
      });
      profileSpeciesDatalistHtml = profileSpeciesDatalist();
      appData.classes.forEach(item => {
        const assignments = profileAssignmentsForClass(item.index);
        item.searchText = profileClassSearchText(item, assignments);
      });
      appData.routes.forEach(route => {
        route.encounterGroups = routeEncounterGroups(route);
        route.identitySearchText = routeIdentitySearchText(route);
        route.groupSearchTextByKey = new Map(route.encounterGroups.map(group => [group.key, routeGroupSearchText(group)]));
        route.searchText = routeSearchText(route);
        routesById.set(String(route.id), route);
      });
      refreshPendingRouteIds();
    }

    function filteredAssignments() {
      const query = els.search.value.trim().toLowerCase();
      const classValue = els.classFilter.value;
      return appData.assignments.filter(item => {
        if (classValue !== "all" && String(item.behaviorClass.value) !== classValue) return false;
        return !query || item.searchText.includes(query);
      });
    }

    function filteredProfileClasses() {
      const query = els.search.value.trim().toLowerCase();
      const classValue = els.classFilter.value;
      return appData.classes.filter(item => {
        if (classValue !== "all" && String(item.index) !== classValue) return false;
        return !query || item.searchText.includes(query);
      });
    }

    function renderClassFilter() {
      const previousValue = hasLoadedData ? els.classFilter.value : "all";
      els.classFilter.innerHTML = `<option value="all">All profiles</option>` + appData.classes.map(item =>
        `<option value="${esc(item.index)}">${esc(item.name)} (${esc(item.speciesCount)})</option>`
      ).join("");
      const values = new Set([...els.classFilter.options].map(option => option.value));
      els.classFilter.value = values.has(previousValue) ? previousValue : "all";
      els.classFilter.disabled = !appData.profilesAvailable;
      els.search.disabled = !appData.profilesAvailable;
    }

    function renderSpeciesList() {
      if (!appData.profilesAvailable) {
        els.speciesCount.textContent = "Unavailable";
        visibleSpeciesRowsBySymbol.clear();
        visibleProfileRowsByClass.clear();
        els.speciesList.innerHTML = profileUnavailableMessage();
        return;
      }
      const rows = filteredProfileClasses();
      els.speciesCount.textContent = `${rows.length} / ${appData.classes.length}`;
      if (!rows.length) {
        visibleSpeciesRowsBySymbol.clear();
        visibleProfileRowsByClass.clear();
        els.speciesList.innerHTML = profileSpeciesDatalistHtml + `<div class="empty">No matches</div>`;
        return;
      }
      if (selectedClassIndex === null || !appData.classes.some(item => String(item.index) === String(selectedClassIndex))) {
        selectedClassIndex = rows[0].index;
      }
      if (!rows.some(row => String(row.index) === String(selectedClassIndex))) {
        selectedClassIndex = rows[0].index;
      }
      const visibleRows = rows.slice(0, visibleSpeciesLimit);
      els.speciesList.innerHTML = profileSpeciesDatalistHtml + visibleRows.map(item => {
        const assigned = profileAssignmentsForClass(item.index);
        const active = String(item.index) === String(selectedClassIndex);
        return `
        <div class="profile-row ${active ? "active" : ""} ${profileClassChanged(item) ? "changed" : ""}" role="button" tabindex="0" data-class-index="${esc(item.index)}">
          ${profileClassBadge(item)}
          <span class="profile-row-main">
            <span class="profile-row-title" title="${esc(profileComboRawDisplay(item.symbol))}">${esc(item.name)}</span>
            <span class="profile-row-sub">${esc(profilePendingDisplay(item, "profileId"))} · ${esc(profilePendingDisplay(item, "spawnState"))}</span>
          </span>
          <span class="profile-row-count">${esc(assigned.length)} Pokemon</span>
          <span class="profile-row-icons" title="${esc(assigned.length)} Pokemon">
            ${profileIconStrip(assigned, item.index === 0 ? 32 : 54, item)}
          </span>
        </div>
      `}).join("") + (rows.length > visibleRows.length ? `
        <div class="list-more">
          <button class="control" type="button" data-action="show-more">Show More</button>
        </div>
      ` : "");
      visibleSpeciesRowsBySymbol.clear();
      visibleProfileRowsByClass = new Map(
        Array.from(els.speciesList.querySelectorAll(".profile-row")).map(row => [String(row.dataset.classIndex), row])
      );
      updateProfileIconSelection();
    }

    function filteredRoutes() {
      if (!appData?.routes) return [];
      const query = els.routeSearch.value.trim().toLowerCase();
      return appData.routes.filter(route => routeFilterState(route, query).visible);
    }

    function routeHasPending(routeId) {
      return pendingRouteIds.has(String(routeId));
    }

    function uniqueEncounterSpecies(entries, speciesGetter) {
      const seen = new Set();
      const species = [];
      entries.forEach(entry => {
        const item = speciesGetter(entry);
        if (!item || item.symbol === "SPECIES_NONE" || seen.has(item.symbol)) return;
        seen.add(item.symbol);
        species.push(item);
      });
      return species;
    }

    function speciesIntersection(lists) {
      if (!lists.length || lists.some(list => !list.length)) return [];
      const allSymbols = lists.map(list => new Set(list.map(species => species.symbol)));
      return lists[0].filter(species => allSymbols.every(symbols => symbols.has(species.symbol)));
    }

    function speciesWithout(species, removedSymbols) {
      return species.filter(item => !removedSymbols.has(item.symbol));
    }

    function routeEncounterGroups(route) {
      if (Array.isArray(route.encounterGroups) && !routeHasPending(route.id)) return route.encounterGroups;
      const pokemonLabels = {
        grass: "Grass",
        morning: "Grass AM",
        day: "Grass Day",
        night: "Grass Night",
        hoenn: "Hoenn sound",
        sinnoh: "Sinnoh sound",
      };
      const slotLabels = {
        surf: "Surf",
        rockSmash: "Rock smash",
        headbuttNormal: "Headbutt",
        headbuttSpecial: "Special trees",
        oldRod: "Old rod",
        goodRod: "Good rod",
        superRod: "Super rod",
      };
      const groups = [];
      const routeId = route.id;
      const pokemonSpecies = slot => routeDisplaySpeciesForEntry(routeId, slot.path, slot.species, slot.formPath, slot.form);
      const encounterSpecies = slot => routeDisplaySpeciesForEntry(routeId, slot.paths.species, slot.species, slot.paths.form, slot.form);
      const swarmSpeciesForRoute = swarm => routeDisplaySpeciesForEntry(routeId, swarm.path, swarm.species, swarm.formPath, swarm.form);
      const grassTimeKeys = ["morning", "day", "night"];
      const grassTables = new Map();
      route.pokemonTables.forEach(table => {
        if (!grassTimeKeys.includes(table.key)) return;
        grassTables.set(table.key, uniqueEncounterSpecies(table.slots, pokemonSpecies));
      });
      const commonGrassSpecies = speciesIntersection(grassTimeKeys.map(key => grassTables.get(key) || []));
      const commonGrassSymbols = new Set(commonGrassSpecies.map(species => species.symbol));

      if (commonGrassSpecies.length) {
        groups.push({
          key: "grass",
          label: pokemonLabels.grass,
          title: "Grass",
          species: commonGrassSpecies
        });
      }

      route.pokemonTables.forEach(table => {
        const baseSpecies = grassTables.get(table.key) || uniqueEncounterSpecies(table.slots, pokemonSpecies);
        const species = grassTimeKeys.includes(table.key) ? speciesWithout(baseSpecies, commonGrassSymbols) : baseSpecies;
        if (!species.length) return;
        groups.push({
          key: table.key,
          label: pokemonLabels[table.key] || table.label,
          title: table.label,
          species
        });
      });

      route.slotTables.forEach(table => {
        const species = uniqueEncounterSpecies(table.slots, encounterSpecies);
        if (!species.length) return;
        groups.push({
          key: table.key,
          label: slotLabels[table.key] || table.label,
          title: table.label,
          species
        });
      });

      ["headbuttNormal", "headbuttSpecial"].forEach(key => {
        const headbuttSlots = (route.headbuttTables || [])
          .filter(table => table.key === key)
          .flatMap(table => table.slots);
        const species = uniqueEncounterSpecies(headbuttSlots, encounterSpecies);
        if (!species.length) return;
        groups.push({
          key,
          label: slotLabels[key],
          title: slotLabels[key],
          species
        });
      });

      const swarmSpecies = uniqueEncounterSpecies(route.swarms, swarmSpeciesForRoute);
      if (swarmSpecies.length) {
        groups.push({
          key: "swarms",
          label: "Swarms",
          title: "Swarm encounters",
          species: swarmSpecies
        });
      }

      return groups;
    }

    function enabledRouteEncounterGroups(route) {
      return routeEncounterGroups(route).filter(group => routeSpawnTypeFilters.has(group.key));
    }

    function routeFilterState(route, query = els.routeSearch.value.trim().toLowerCase()) {
      const searchInfo = typeof query === "string" ? routeSearchInfo(query) : query;
      const allGroups = routeEncounterGroups(route);
      const enabledGroups = allGroups.filter(group => routeSpawnTypeFilters.has(group.key));
      const identityMatches = searchInfo.query && (route.identitySearchText || routeIdentitySearchText(route)).includes(searchInfo.query);
      const groupMatches = searchInfo.query
        ? enabledGroups.some(group => {
          if (searchInfo.type) return routeGroupHasSearchMatch(group, searchInfo);
          const groupText = routeHasPending(route.id)
            ? routeGroupSearchText(group)
            : (route.groupSearchTextByKey?.get(group.key) || routeGroupSearchText(group));
          return groupText.includes(searchInfo.query);
        })
        : false;
      return {
        allGroups,
        enabledGroups,
        searchInfo,
        visible: enabledGroups.length ? (!searchInfo.query || identityMatches || groupMatches) : Boolean(identityMatches)
      };
    }

    function setRouteGroupVisibility(groupKey, visible) {
      els.routeList.querySelectorAll(`.route-encounter-group[data-group-key="${groupKey}"]`).forEach(group => {
        group.hidden = !visible;
      });
    }

    function syncAllRouteGroupVisibility() {
      els.routeList.querySelectorAll(".route-encounter-group[data-group-key]").forEach(group => {
        group.hidden = !routeSpawnTypeFilters.has(group.dataset.groupKey);
      });
    }

    function syncRouteRowSearchHighlights(row, route, searchInfo) {
      const groupsByKey = new Map(routeEncounterGroups(route).map(group => [group.key, group]));
      row.querySelectorAll(".route-encounter-group[data-group-key]").forEach(groupEl => {
        const group = groupsByKey.get(groupEl.dataset.groupKey);
        groupEl.classList.toggle("route-search-match-group", Boolean(group && routeGroupHasSearchMatch(group, searchInfo)));
      });
      row.querySelectorAll(".swap-mon-button[data-species-symbol]").forEach(button => {
        const species = routeSpeciesOption(button.dataset.speciesSymbol) || speciesBySymbol(button.dataset.speciesSymbol);
        button.classList.toggle("route-search-match", routeSpeciesMatchesSearch(species, searchInfo));
      });
    }

    function syncRouteEditorSearchHighlights(searchInfo = routeSearchInfo()) {
      document.querySelectorAll(".encounter-summary-chip[data-species-symbol]").forEach(chip => {
        const species = routeSpeciesOption(chip.dataset.speciesSymbol) || speciesBySymbol(chip.dataset.speciesSymbol);
        chip.classList.toggle("route-search-match", routeSpeciesMatchesSearch(species, searchInfo));
      });
    }

    function routeIconStrip(route) {
      const allGroups = routeEncounterGroups(route);
      if (!allGroups.length) {
        return `<span class="chip neutral">Empty</span>`;
      }
      const searchInfo = routeSearchInfo();
      return `
        <div class="route-icons" title="${esc(route.speciesCount)} Pokemon">
          <span class="chip neutral route-filtered-chip">Filtered</span>
          ${allGroups.map(group => `
            <span class="route-encounter-group ${routeGroupHasSearchMatch(group, searchInfo) ? "route-search-match-group" : ""}" data-group-key="${esc(group.key)}" title="${esc(group.label)}: ${esc(group.species.map(species => species.name).join(", "))}" aria-label="${esc(group.label)}">
              <span class="route-encounter-icons">
                ${routeEncounterIconSet(group)}
                <span class="route-encounter-text">${esc(group.label)}</span>
              </span>
              <span class="route-encounter-mon-icons">
                ${group.species.map(species => routeSpeciesSwapButton(route.id, species, searchInfo)).join("")}
              </span>
            </span>
          `).join("")}
        </div>
      `;
    }

    function syncRouteRowFilterState(row, route, query) {
      const searchInfo = routeSearchInfo(query);
      const state = routeFilterState(route, searchInfo);
      row.hidden = !state.visible;
      row.classList.toggle("no-enabled-groups", Boolean(state.allGroups.length && !state.enabledGroups.length));
      row.classList.toggle("active", String(route.id) === String(selectedRouteId));
      syncRouteRowSearchHighlights(row, route, searchInfo);
      return state.visible;
    }

    function applyRouteListFilters() {
      const query = els.routeSearch.value.trim().toLowerCase();
      let visibleCount = 0;
      els.routeList.querySelectorAll(".route-row").forEach(row => {
        const route = routesById.get(String(row.dataset.routeId));
        if (!route) return;
        if (syncRouteRowFilterState(row, route, query)) visibleCount += 1;
      });
      els.routeCount.textContent = `${visibleCount} / ${appData.routes.length}`;
      const empty = els.routeList.querySelector(".route-list-empty");
      if (empty) {
        empty.hidden = visibleCount > 0;
      }
      return false;
    }

    function routeMapText(route) {
      return route.maps.length ? route.maps.map(map => map.symbol).join(", ") : "No mapped area";
    }

    function routeGroupClassName(key) {
      return String(key || "")
        .replace(/[A-Z]/g, match => `-${match.toLowerCase()}`)
        .replace(/[^a-z0-9-]/gi, "-")
        .replace(/^-+|-+$/g, "")
        .toLowerCase();
    }

    function routeSpeciesSwapButton(routeId, species, searchInfo = routeSearchInfo()) {
      if (!species || species.symbol === "SPECIES_NONE") return "";
      const matchClass = routeSpeciesMatchesSearch(species, searchInfo) ? " route-search-match" : "";
      return `
        <button class="swap-mon-button${matchClass}" type="button" data-route-swap="1" data-route-id="${esc(routeId)}" data-species-symbol="${esc(species.symbol)}" aria-label="Swap ${esc(species.name)} on this route" title="Swap ${esc(species.name)} on this route">
          ${iconTag(species, "mon-icon")}
        </button>
      `;
    }

    function routeOverviewStrip(route) {
      const groups = routeEncounterGroups(route);
      if (!groups.length) return "";
      const searchInfo = routeSearchInfo();
      return `
        <div class="route-detail-overview" aria-label="Encounter overview">
          ${groups.map(group => `
            <span class="route-overview-pill overview-${esc(routeGroupClassName(group.key))} ${routeGroupHasSearchMatch(group, searchInfo) ? "route-search-match-group" : ""}" title="${esc(group.label)}: ${esc(group.species.map(species => species.name).join(", "))}">
              ${routeEncounterIconSet(group)}
              <span class="route-overview-icons">
                ${group.species.map(species => routeSpeciesSwapButton(route.id, species, searchInfo)).join("")}
              </span>
            </span>
          `).join("")}
        </div>
      `;
    }

    function routeRowHtml(route) {
      const mapText = routeMapText(route);
      const changed = routeHasPending(route.id);
      return `
        <div class="route-row ${String(route.id) === String(selectedRouteId) ? "active" : ""}" role="button" tabindex="0" data-route-id="${esc(route.id)}">
          <span class="route-id">#${esc(route.id)}</span>
          <span>
            <span class="route-name" title="${esc(route.name)}">${esc(route.name)}</span>
            <span class="route-sub">${esc(mapText)}${changed ? " · edited" : ""}</span>
          </span>
          ${routeIconStrip(route)}
        </div>
      `;
    }

    function renderRouteList() {
      if (!appData.routes.length) {
        els.routeCount.textContent = `0 / 0`;
        els.routeList.innerHTML = `<div class="empty">No routes</div>`;
        return false;
      }
      const previousRouteId = selectedRouteId;
      if (selectedRouteId === null || !routesById.has(String(selectedRouteId))) {
        selectedRouteId = appData.routes[0].id;
      }
      els.routeList.innerHTML = appData.routes.map(routeRowHtml).join("") + `<div class="empty route-list-empty" hidden>No routes</div>`;
      syncAllRouteGroupVisibility();
      applyRouteListFilters();
      return String(previousRouteId) !== String(selectedRouteId);
    }

    function visibleRouteRow(routeId) {
      return els.routeList.querySelector(`.route-row[data-route-id="${String(routeId)}"]`);
    }

    function updateSelectedRouteRow(previousRouteId) {
      const previousRow = previousRouteId === null || previousRouteId === undefined ? null : visibleRouteRow(previousRouteId);
      if (previousRow) {
        previousRow.classList.remove("active");
      }
      const row = visibleRouteRow(selectedRouteId);
      if (row) {
        row.classList.add("active");
      }
    }

    function updateRouteEditedMarker(routeId) {
      const row = visibleRouteRow(routeId);
      const route = routesById.get(String(routeId));
      if (!row || !route) return;
      const routeSub = row.querySelector(".route-sub");
      if (routeSub) {
        routeSub.textContent = `${routeMapText(route)}${routeHasPending(route.id) ? " · edited" : ""}`;
      }
      if (String(route.id) === String(selectedRouteId)) {
        const chip = els.routeDetailHead.querySelector(".chip");
        if (chip) chip.textContent = routeHasPending(route.id) ? "Edited" : "Source";
      }
    }

    function refreshRouteRow(routeId) {
      const row = visibleRouteRow(routeId);
      const route = routesById.get(String(routeId));
      if (!row || !route) return;
      const wrapper = document.createElement("div");
      wrapper.innerHTML = routeRowHtml(route).trim();
      const nextRow = wrapper.firstElementChild;
      row.replaceWith(nextRow);
      syncRouteRowFilterState(nextRow, route, els.routeSearch.value.trim().toLowerCase());
      syncAllRouteGroupVisibility();
      applyRouteListFilters();
    }

    function scheduleRouteMarkerUpdate(routeId) {
      if (routeId === null || routeId === undefined) return;
      pendingRouteMarkerIds.add(String(routeId));
      if (routeMarkerFrame) return;
      routeMarkerFrame = requestAnimationFrame(() => {
        routeMarkerFrame = null;
        const routeIds = Array.from(pendingRouteMarkerIds);
        pendingRouteMarkerIds.clear();
        routeIds.forEach(updateRouteEditedMarker);
      });
    }

    function currentRoute() {
      return routesById.get(String(selectedRouteId)) || appData.routes[0];
    }

    function renderRouteDetailHead() {
      const route = currentRoute();
      if (!route) {
        els.routeDetailHead.innerHTML = "";
        return;
      }
      const mapText = routeMapText(route);
      els.routeDetailHead.innerHTML = `
        <div class="route-detail-head-main">
          <div class="route-detail-title-line">
            <div class="route-detail-title-copy">
              <h2>${esc(route.name)}</h2>
              <div class="meta">
                <span>Encounter data #${esc(route.id)}</span>
                <span>${esc(mapText)}</span>
              </div>
            </div>
            <div class="route-detail-head-tools">
              ${routeHeaderRates(route)}
              <div class="chip route-detail-status">${esc(routeHasPending(route.id) ? "Edited" : "Source")}</div>
            </div>
          </div>
          ${routeOverviewStrip(route)}
        </div>
      `;
    }

    function routeChangedClass(routeId, path, original) {
      return routePendingValue(routeId, path, original) !== String(original) ? " changed" : "";
    }

    function routeSpeciesCell(routeId, path, species, formPath, form, label = "Pokemon") {
      const raw = routePendingValue(routeId, path, species.symbol);
      const formRaw = routePendingValue(routeId, formPath, form);
      const option = routeDisplaySpecies(raw, formRaw);
      const changed = raw !== species.symbol || String(formRaw) !== String(form);
      return `
        <td class="${changed ? "changed" : ""}" data-label="${esc(label)}">
          <span class="species-input-wrap">
            ${iconTag(option, "mon-icon")}
            <input class="route-input route-species-combo" type="text" list="routeSpeciesOptions" value="${esc(routeSpeciesInputValue(raw, formRaw))}" data-route-id="${esc(routeId)}" data-path="${esc(path)}" data-original="${esc(species.symbol)}" ${speciesFormInputAttrs(formPath, form)} autocomplete="off">
            <input class="route-input route-number route-form" type="number" min="0" max="31" step="1" value="${esc(formRaw)}" data-kind="form" data-route-id="${esc(routeId)}" data-path="${esc(formPath)}" data-original="${esc(form)}" title="Form">
          </span>
        </td>
      `;
    }

    function routeNumberCell(routeId, path, value, kind, label = "") {
      const raw = routePendingValue(routeId, path, value);
      const changed = String(raw) !== String(value);
      return `
        <td class="${changed ? "changed" : ""}" data-label="${esc(label || kind)}">
          <input class="route-input route-number" type="number" min="0" max="100" step="1" value="${esc(raw)}" data-kind="${esc(kind)}" data-route-id="${esc(routeId)}" data-path="${esc(path)}" data-original="${esc(value)}">
        </td>
      `;
    }

    function routeValueChanged(routeId, path, original) {
      return routePendingValue(routeId, path, original) !== String(original ?? "");
    }

    function speciesControlChanged(routeId, path, species, formPath, form) {
      return routeValueChanged(routeId, path, species.symbol)
        || routeValueChanged(routeId, formPath, form);
    }

    function rateEncounterIconSet(rate) {
      const key = String(rate.key || rate.label || "").toLowerCase();
      if (key.includes("walk")) return encounterBadge("leaf", "type-grass", rate.label);
      if (key.includes("surf")) return encounterBadge("waves", "type-surf", rate.label);
      if (key.includes("rock")) return encounterBadge("hammer", "type-rock", rate.label);
      if (key.includes("old")) return encounterBadge("dot1", "type-rod", rate.label);
      if (key.includes("good")) return encounterBadge("dot2", "type-rod", rate.label);
      if (key.includes("super")) return encounterBadge("dot3", "type-rod", rate.label);
      return "";
    }

    function compactNumberControl(routeId, path, value, label, kind, min = 0, max = 100, className = "") {
      const raw = routePendingValue(routeId, path, value);
      const changed = String(raw) !== String(value);
      const labelHtml = label
        ? `<span>${esc(label)}</span>`
        : `<span class="sr-only">${esc(kind)}</span>`;
      return `
        <label class="compact-number-control ${esc(className)} ${changed ? "changed" : ""}">
          ${labelHtml}
          <input class="route-input route-number" type="number" min="${esc(min)}" max="${esc(max)}" step="1" value="${esc(raw)}" data-kind="${esc(kind)}" data-route-id="${esc(routeId)}" data-path="${esc(path)}" data-original="${esc(value)}">
        </label>
      `;
    }

    function compactSpeciesControl(routeId, path, species, formPath, form) {
      const raw = routePendingValue(routeId, path, species.symbol);
      const formRaw = routePendingValue(routeId, formPath, form);
      const option = routeDisplaySpecies(raw, formRaw);
      return `
        <span class="species-input-wrap compact-species-control">
          ${iconTag(option, "mon-icon")}
          <input class="route-input route-species-combo" type="text" list="routeSpeciesOptions" value="${esc(routeSpeciesInputValue(raw, formRaw))}" data-route-id="${esc(routeId)}" data-path="${esc(path)}" data-original="${esc(species.symbol)}" ${speciesFormInputAttrs(formPath, form)} autocomplete="off">
          <input class="route-input route-number route-form" type="number" min="0" max="31" step="1" value="${esc(formRaw)}" data-kind="form" data-route-id="${esc(routeId)}" data-path="${esc(formPath)}" data-original="${esc(form)}" title="Form">
        </span>
      `;
    }

    function compactRateField(routeId, rate) {
      const raw = routePendingValue(routeId, rate.path, rate.value);
      const changed = String(raw) !== String(rate.value);
      return `
        <label class="route-field compact-rate-field ${changed ? "changed" : ""}">
          ${rateEncounterIconSet(rate)}
          <span class="rate-label">${esc(rate.label)}</span>
          <input class="route-input route-number" type="number" min="0" max="100" step="1" value="${esc(raw)}" data-kind="rate" data-route-id="${esc(routeId)}" data-path="${esc(rate.path)}" data-original="${esc(rate.value)}">
        </label>
      `;
    }

    function routeHeaderRateField(routeId, rate) {
      const raw = routePendingValue(routeId, rate.path, rate.value);
      const changed = String(raw) !== String(rate.value);
      return `
        <label class="route-field route-rate-chip ${changed ? "changed" : ""}" title="${esc(rate.label)}">
          ${rateEncounterIconSet(rate)}
          <input class="route-input route-number" type="number" min="0" max="100" step="1" value="${esc(raw)}" data-kind="rate" data-route-id="${esc(routeId)}" data-path="${esc(rate.path)}" data-original="${esc(rate.value)}" aria-label="${esc(rate.label)} rate">
        </label>
      `;
    }

    function routeHeaderRates(route) {
      if (!route.rates?.length) return "";
      return `
        <div class="route-header-rates" aria-label="Encounter rates">
          ${route.rates.map(rate => routeHeaderRateField(route.id, rate)).join("")}
        </div>
      `;
    }

    function renderRates(route) {
      return collapsibleRouteSection(
        "route:rates",
        "Encounter Rates",
        "",
        `
          <div class="compact-rate-grid">
            ${route.rates.map(rate => compactRateField(route.id, rate)).join("")}
          </div>
        `,
        "route-compact-section rates-compact-section"
      );
    }

    function renderSpawnSettings() {
      const count = appData.spawnSettings.reduce((total, group) => total + group.settings.length, 0);
      return `
        <div class="spawn-settings-toolbar" title="Global overworld spawn settings: ${esc(count)} settings">
          <div class="spawn-settings-content">
            ${appData.spawnSettings.map(spawnSettingsGroupRow).join("")}
          </div>
        </div>
      `;
    }

    function setSpawnSettingDialogError(message) {
      const error = els.spawnSettingDialog.querySelector(".spawn-setting-error");
      if (error) error.textContent = message || "";
    }

    function closeSpawnSettingDialog() {
      const input = els.spawnSettingDialog.querySelector("#spawnSettingDialogInput");
      if (input?.dataset?.symbol) {
        markSpawnSettingInvalid(input.dataset.symbol, false, input);
      }
      if (els.spawnSettingDialog.open) {
        els.spawnSettingDialog.close();
      }
      els.spawnSettingDialog.innerHTML = "";
      updateGlobalEditStatus();
    }

    function renderSpawnSettingDialog(setting) {
      if (setting.kind === "testSpawn") {
        return renderTestSpawnDialog(setting);
      }
      const raw = pendingSpawnSettingValue(setting.symbol, setting.value);
      const suffixText = setting.suffix ? ` (${setting.suffix})` : "";
      return `
        <form class="spawn-setting-card" method="dialog">
          <div class="spawn-setting-dialog-head">
            ${spawnSettingIcon(setting)}
            <div class="spawn-setting-dialog-title">
              <strong>${esc(setting.label)}</strong>
              <span>${esc(setting.groupLabel || "")} • ${esc(setting.symbol)}</span>
            </div>
          </div>
          <label class="spawn-setting-field-dialog">
            <span>Value${esc(suffixText)}</span>
            <input id="spawnSettingDialogInput" class="spawn-setting-dialog-input spawn-setting-input" type="number" min="${esc(setting.min)}" max="${esc(setting.max)}" step="1" value="${esc(raw)}" data-symbol="${esc(setting.symbol)}" data-original="${esc(setting.value)}" autocomplete="off">
          </label>
          <div class="spawn-setting-help">${esc(setting.min)}-${esc(setting.max)} • ${esc(setting.source)}</div>
          <div class="spawn-setting-error"></div>
          <div class="spawn-setting-dialog-actions">
            <button class="control" type="button" data-spawn-setting-action="cancel">Cancel</button>
            <button class="control primary-action" type="submit" data-spawn-setting-action="apply">Apply</button>
          </div>
        </form>
      `;
    }

    function renderTestSpawnDialog(setting) {
      const enabledField = spawnSettingField(setting, "enabled");
      const speciesField = spawnSettingField(setting, "species");
      const levelField = spawnSettingField(setting, "level");
      const enabledRaw = pendingSpawnSettingValue(enabledField.symbol, enabledField.value);
      const speciesSymbol = pendingSpawnSettingValue(speciesField.symbol, speciesField.symbolValue || speciesField.raw);
      const species = routeSpeciesOption(speciesSymbol) || speciesBySymbol(speciesSymbol);
      const levelRaw = pendingSpawnSettingValue(levelField.symbol, levelField.value);
      return `
        <form class="spawn-setting-card" method="dialog" data-test-spawn-dialog="true">
          <div class="spawn-setting-dialog-head">
            ${spawnSettingIcon(setting)}
            <div class="spawn-setting-dialog-title">
              <strong>${esc(setting.label)}</strong>
              <span>${esc(setting.groupLabel || "")} • ${esc(setting.source)}</span>
            </div>
          </div>
          <div class="spawn-setting-test-grid">
            <label class="spawn-setting-toggle-row">
              <span>Enabled</span>
              <input id="spawnTestEnabledInput" type="checkbox" ${enabledRaw === "1" ? "checked" : ""} data-symbol="${esc(enabledField.symbol)}" data-original="${esc(enabledField.value)}">
            </label>
            <label class="spawn-setting-field-dialog">
              <span>Pokemon</span>
              <span class="species-input-wrap spawn-setting-species-wrap">
                ${iconTag(species, "mon-icon")}
                <input id="spawnTestSpeciesInput" class="spawn-setting-dialog-input spawn-setting-species-input" type="text" list="routeSpeciesOptions" value="${esc(routeSpeciesInputValue(species.symbol || speciesSymbol))}" data-symbol="${esc(speciesField.symbol)}" data-original="${esc(speciesField.symbolValue || speciesField.raw)}" autocomplete="off">
              </span>
            </label>
            <label class="spawn-setting-field-dialog">
              <span>Level</span>
              <input id="spawnTestLevelInput" class="spawn-setting-dialog-input" type="number" min="${esc(levelField.min)}" max="${esc(levelField.max)}" step="1" value="${esc(levelRaw)}" data-symbol="${esc(levelField.symbol)}" data-original="${esc(levelField.value)}" autocomplete="off">
            </label>
          </div>
          <div class="spawn-setting-help">Changes ${esc(enabledField.symbol)}, ${esc(speciesField.symbol)}, and ${esc(levelField.symbol)}</div>
          <div class="spawn-setting-error"></div>
          <div class="spawn-setting-dialog-actions">
            <button class="control" type="button" data-spawn-setting-action="cancel">Cancel</button>
            <button class="control primary-action" type="submit" data-spawn-setting-action="apply">Apply</button>
          </div>
        </form>
      `;
    }

    function openSpawnSettingDialog(symbol) {
      const setting = spawnSettingsBySymbol.get(symbol);
      if (!setting) return;
      renderRouteSpeciesDatalist();
      els.spawnSettingDialog.innerHTML = renderSpawnSettingDialog(setting);
      if (!els.spawnSettingDialog.open) {
        els.spawnSettingDialog.showModal();
      }
      const input = els.spawnSettingDialog.querySelector("#spawnSettingDialogInput, #spawnTestSpeciesInput");
      if (input) {
        input.focus();
        input.select();
      }
    }

    function applySpawnSettingDialog() {
      const testForm = els.spawnSettingDialog.querySelector("[data-test-spawn-dialog]");
      if (testForm) {
        return applyTestSpawnDialog();
      }
      const input = els.spawnSettingDialog.querySelector("#spawnSettingDialogInput");
      if (!input) return false;
      const setting = spawnSettingsBySymbol.get(input.dataset.symbol);
      if (!setting) return false;
      const validation = validateSpawnSettingValue(setting, input.value);
      if (!validation.valid) {
        markSpawnSettingInvalid(setting.symbol, true, input);
        setSpawnSettingDialogError(validation.message);
        updateGlobalEditStatus();
        return false;
      }
      commitSpawnSettingValue(setting.symbol, input.value, input);
      closeSpawnSettingDialog();
      renderRouteGlobalSettings();
      updateGlobalEditStatus();
      return true;
    }

    function applyTestSpawnDialog() {
      const enabledInput = els.spawnSettingDialog.querySelector("#spawnTestEnabledInput");
      const speciesInput = els.spawnSettingDialog.querySelector("#spawnTestSpeciesInput");
      const levelInput = els.spawnSettingDialog.querySelector("#spawnTestLevelInput");
      const speciesSetting = spawnSettingsBySymbol.get(speciesInput?.dataset.symbol);
      const levelSetting = spawnSettingsBySymbol.get(levelInput?.dataset.symbol);
      if (!enabledInput || !speciesInput || !levelInput || !speciesSetting || !levelSetting) return false;
      const speciesValidation = validateSpawnSettingValue(speciesSetting, speciesInput.value);
      const levelValidation = validateSpawnSettingValue(levelSetting, levelInput.value);
      if (!speciesValidation.valid || !levelValidation.valid) {
        speciesInput.classList.toggle("invalid", !speciesValidation.valid);
        levelInput.classList.toggle("invalid", !levelValidation.valid);
        setSpawnSettingDialogError(speciesValidation.message || levelValidation.message);
        updateGlobalEditStatus();
        return false;
      }
      commitSpawnSettingValue(enabledInput.dataset.symbol, enabledInput.checked ? "1" : "0", enabledInput);
      commitSpawnSettingValue(speciesInput.dataset.symbol, speciesValidation.normalized, speciesInput);
      commitSpawnSettingValue(levelInput.dataset.symbol, levelInput.value, levelInput);
      closeSpawnSettingDialog();
      renderRouteGlobalSettings();
      updateGlobalEditStatus();
      return true;
    }

    function pokemonTableByKey(route, key) {
      return route.pokemonTables.find(table => table.key === key);
    }

    function grassRatePercent(weight) {
      const value = Number(weight);
      if (!Number.isFinite(value)) return 0;
      return Math.max(0, Math.min(100, value));
    }

    function grassLevelControl(routeId, level) {
      const raw = routePendingValue(routeId, level.path, level.value);
      const changed = String(raw) !== String(level.value);
      return `
        <label class="route-field grass-level-control compact-level-field ${changed ? "changed" : ""}">
          <span>Lv</span>
          <input class="route-input route-number" type="number" min="0" max="100" step="1" value="${esc(raw)}" data-kind="level" data-route-id="${esc(routeId)}" data-path="${esc(level.path)}" data-original="${esc(level.value)}">
        </label>
      `;
    }

    function grassTimeField(routeId, table, index, key, title, icon) {
      const slot = table.slots[index];
      const raw = routePendingValue(routeId, slot.path, slot.species.symbol);
      const formRaw = routePendingValue(routeId, slot.formPath, slot.form);
      const changed = raw !== slot.species.symbol || String(formRaw) !== String(slot.form);
      return `
        <div class="route-field compact-pill grass-time-cell grass-time-${esc(key)} ${changed ? "changed" : ""}">
          <span class="compact-time-badge">
            ${encounterBadge(icon, `type-grass time-${key}`, title)}
          </span>
          ${compactSpeciesControl(routeId, slot.path, slot.species, slot.formPath, slot.form)}
        </div>
      `;
    }

    function encounterStat(label, value) {
      return `
        <div class="encounter-stat">
          <span class="encounter-stat-label">${esc(label)}</span>
          <strong>${esc(value)}</strong>
        </div>
      `;
    }

    function encounterSpeciesField(routeId, path, species, formPath, form, label = "Pokemon") {
      const raw = routePendingValue(routeId, path, species.symbol);
      const formRaw = routePendingValue(routeId, formPath, form);
      const option = routeDisplaySpecies(raw, formRaw);
      const changed = raw !== species.symbol || String(formRaw) !== String(form);
      return `
        <div class="route-field encounter-species-cell ${changed ? "changed" : ""}">
          <span class="encounter-species-head">
            <span class="encounter-species-title">${esc(label)}</span>
            <input class="route-input route-number route-form" type="number" min="0" max="31" step="1" value="${esc(formRaw)}" data-kind="form" data-route-id="${esc(routeId)}" data-path="${esc(formPath)}" data-original="${esc(form)}" title="Form">
          </span>
          <span class="species-input-wrap">
            ${iconTag(option, "mon-icon")}
            <input class="route-input route-species-combo" type="text" list="routeSpeciesOptions" value="${esc(routeSpeciesInputValue(raw, formRaw))}" data-route-id="${esc(routeId)}" data-path="${esc(path)}" data-original="${esc(species.symbol)}" ${speciesFormInputAttrs(formPath, form)} autocomplete="off">
          </span>
        </div>
      `;
    }

    function encounterNumberField(routeId, path, value, label, kind, min = 0, max = 100) {
      const raw = routePendingValue(routeId, path, value);
      const changed = String(raw) !== String(value);
      return `
        <label class="route-field encounter-level-control ${changed ? "changed" : ""}">
          <span class="encounter-stat-label">${esc(label)}</span>
          <input class="route-input route-number" type="number" min="${esc(min)}" max="${esc(max)}" step="1" value="${esc(raw)}" data-kind="${esc(kind)}" data-route-id="${esc(routeId)}" data-path="${esc(path)}" data-original="${esc(value)}">
        </label>
      `;
    }

    function formatEncounterRate(value) {
      const number = Number(value);
      if (!Number.isFinite(number)) return "";
      return Number.isInteger(number) ? String(number) : number.toFixed(1).replace(/\.0$/, "");
    }

    function levelRangeLabel(minLevel, maxLevel) {
      const min = String(minLevel ?? "");
      const max = String(maxLevel ?? "");
      if (!min && !max) return "";
      return min === max || !max ? `Lv ${min}` : `Lv ${min}-${max}`;
    }

    function summarySpeciesLabel(species) {
      if (!species || species.symbol === "SPECIES_NONE") return "NONE";
      return routeSpeciesShortSymbol(species.symbol);
    }

    function aggregateEncounterEntries(entries) {
      const groups = new Map();
      entries.forEach((entry, index) => {
        const symbol = entry.species?.symbol || "SPECIES_NONE";
        if (!groups.has(symbol)) {
          groups.set(symbol, {
            symbol,
            species: entry.species || speciesBySymbol(symbol),
            rate: 0,
            hasRate: false,
            entries: [],
            levels: new Set(),
            changed: false,
            firstIndex: index,
          });
        }
        const group = groups.get(symbol);
        if (entry.hasRate !== false && entry.rate !== null && entry.rate !== undefined && entry.rate !== "") {
          const rate = Number(entry.rate);
          if (Number.isFinite(rate)) {
            group.rate += rate;
            group.hasRate = true;
          }
        }
        if (entry.levelLabel) group.levels.add(entry.levelLabel);
        group.changed = group.changed || Boolean(entry.changed);
        group.entries.push(entry);
      });
      return Array.from(groups.values()).sort((a, b) => {
        if (a.hasRate || b.hasRate) return b.rate - a.rate || a.firstIndex - b.firstIndex;
        return a.firstIndex - b.firstIndex;
      });
    }

    function encounterAggregateTitle(group, sourceLabel) {
      const rate = group.hasRate ? `${formatEncounterRate(group.rate)}%` : `${group.entries.length} entr${group.entries.length === 1 ? "y" : "ies"}`;
      const entries = group.entries.map(entry => {
        const parts = [];
        if (entry.slot !== "" && entry.slot !== null && entry.slot !== undefined) parts.push(`#${entry.slot}`);
        if (entry.rate !== "" && entry.rate !== null && entry.rate !== undefined) parts.push(`${entry.rate}%`);
        if (entry.levelLabel) parts.push(entry.levelLabel);
        return parts.join(" ");
      }).filter(Boolean).join(", ");
      return `${summarySpeciesLabel(group.species)} on ${sourceLabel}: ${rate}${entries ? ` • ${entries}` : ""}`;
    }

    function compactEncounterLevelText(levelList) {
      if (!levelList.length) return "";
      const compact = levelList
        .slice(0, 4)
        .map(level => String(level).replace(/^Lv\s*/i, ""))
        .join(",");
      return `${compact}${levelList.length > 4 ? ` +${levelList.length - 4}` : ""}`;
    }

    function encounterSummaryRateValue(group) {
      if (!group.hasRate) return 28;
      const rate = Number(group.rate);
      if (!Number.isFinite(rate)) return 28;
      return Math.max(0, Math.min(100, rate));
    }

    function encounterSummaryRateClass(rateValue) {
      if (rateValue <= 8) return "rate-tiny";
      if (rateValue <= 18) return "rate-small";
      if (rateValue <= 34) return "rate-medium";
      return "rate-large";
    }

    function encounterSummaryCompactWidth(rateValue) {
      if (rateValue <= 0) return 46;
      return Math.round(42 + (rateValue * 4));
    }

    function registerEncounterSummaryTargets(routeId, group) {
      const id = `encounter-summary-${routeId}-${encounterSummaryTargetSequence++}`;
      encounterSummaryTargetsById.set(id, group.entries.map(entry => ({
        path: entry.path,
        formPath: entry.formPath,
        originalSymbol: entry.originalSymbol,
        originalForm: entry.originalForm,
      })).filter(entry => entry.path && entry.formPath));
      return id;
    }

    function encounterSummaryChip(routeId, group, sourceLabel) {
      const rateText = group.hasRate ? `${formatEncounterRate(group.rate)}%` : `${group.entries.length}x`;
      const levelList = Array.from(group.levels);
      const levelText = compactEncounterLevelText(levelList);
      const emptyClass = group.symbol === "SPECIES_NONE" ? " empty" : "";
      const targetId = registerEncounterSummaryTargets(routeId, group);
      const sourceKey = group.entries.find(entry => entry.sourceKey)?.sourceKey || "";
      const rateValue = encounterSummaryRateValue(group);
      const rateClass = encounterSummaryRateClass(rateValue);
      const compactWidth = encounterSummaryCompactWidth(rateValue);
      const searchMatchClass = routeSpeciesMatchesSearch(group.species) ? " route-search-match" : "";
      return `
        <div class="encounter-summary-chip ${esc(rateClass)}${emptyClass}${searchMatchClass} ${group.changed ? "changed" : ""}" style="--encounter-rate-width:${esc(rateValue)}%;--encounter-compact-width:${esc(compactWidth)}px" data-route-swap="1" data-route-id="${esc(routeId)}" data-species-symbol="${esc(group.symbol)}" data-swap-target-id="${esc(targetId)}" data-swap-source-key="${esc(sourceKey)}" title="${esc(encounterAggregateTitle(group, sourceLabel))}" aria-label="Edit ${esc(summarySpeciesLabel(group.species))} on ${esc(sourceLabel)}">
          <span class="encounter-summary-meter">
            <span class="encounter-summary-rate">${esc(rateText)}</span>
            ${iconTag(group.species, "mon-icon")}
            ${levelText ? `<span class="encounter-summary-levels">${esc(levelText)}</span>` : ""}
          </span>
          <span class="encounter-summary-body">
            <input class="encounter-summary-species-input" type="text" list="routeSpeciesOptions" value="${esc(routeSpeciesInputValue(group.species.symbol))}" data-summary-target-id="${esc(targetId)}" data-route-id="${esc(routeId)}" data-current-symbol="${esc(group.symbol)}" autocomplete="off" aria-label="Change ${esc(summarySpeciesLabel(group.species))} on ${esc(sourceLabel)}">
          </span>
        </div>
      `;
    }

    function encounterSummarySource(group, subtitle) {
      return `
        <div class="encounter-summary-source">
          ${routeEncounterIconSet(group)}
          <span class="encounter-summary-source-copy">
            <span class="encounter-summary-title">${esc(group.label)}</span>
            <span class="encounter-summary-sub">${esc(subtitle)}</span>
          </span>
        </div>
      `;
    }

    function encounterSummaryRow(route, group, entries, subtitle = "") {
      const aggregates = aggregateEncounterEntries(entries);
      const sourceLabel = group.label;
      return `
        <article class="encounter-summary-row summary-${esc(routeGroupClassName(group.key))}">
          ${encounterSummarySource(group, subtitle || `${entries.length} slots`)}
          <div class="encounter-summary-pokemon">
            ${aggregates.length
              ? aggregates.map(aggregate => encounterSummaryChip(route.id, aggregate, sourceLabel)).join("")
              : `<span class="encounter-summary-empty">No encounters</span>`}
          </div>
        </article>
      `;
    }

    function grassSummaryEntries(route, table) {
      if (!table) return [];
      return table.slots.map((slot, index) => {
        const level = route.grassLevels[index];
        const rate = slot.weight ?? level?.weight ?? 0;
        const levelRaw = level ? routePendingValue(route.id, level.path, level.value) : "";
        return {
          species: routeDisplaySpeciesForEntry(route.id, slot.path, slot.species, slot.formPath, slot.form),
          path: slot.path,
          formPath: slot.formPath,
          originalSymbol: slot.species.symbol,
          originalForm: slot.form,
          sourceKey: table.key,
          slot: slot.slot,
          rate,
          levelLabel: levelRaw !== "" ? `Lv ${levelRaw}` : "",
          changed: speciesControlChanged(route.id, slot.path, slot.species, slot.formPath, slot.form)
            || (level ? routeValueChanged(route.id, level.path, level.value) : false),
        };
      });
    }

    function sourceSlotSummaryEntries(route, table) {
      return table.slots.map(slot => {
        const minRaw = routePendingValue(route.id, slot.paths.minLevel, slot.minLevel);
        const maxRaw = routePendingValue(route.id, slot.paths.maxLevel, slot.maxLevel);
        return {
          species: routeDisplaySpeciesForEntry(route.id, slot.paths.species, slot.species, slot.paths.form, slot.form),
          path: slot.paths.species,
          formPath: slot.paths.form,
          originalSymbol: slot.species.symbol,
          originalForm: slot.form,
          sourceKey: table.key,
          slot: slot.slot,
          rate: slot.weight,
          levelLabel: levelRangeLabel(minRaw, maxRaw),
          changed: sourceSlotChanged(route.id, slot),
        };
      });
    }

    function pokemonSlotSummaryEntries(route, table) {
      return table.slots.map(slot => ({
        species: routeDisplaySpeciesForEntry(route.id, slot.path, slot.species, slot.formPath, slot.form),
        path: slot.path,
        formPath: slot.formPath,
        originalSymbol: slot.species.symbol,
        originalForm: slot.form,
        sourceKey: table.key,
        slot: slot.slot,
        rate: slot.weight,
        levelLabel: "",
        changed: sourcePokemonChanged(route.id, slot),
      }));
    }

    function swarmSummaryEntries(route) {
      return route.swarms.map((swarm, index) => ({
        species: routeDisplaySpeciesForEntry(route.id, swarm.path, swarm.species, swarm.formPath, swarm.form),
        path: swarm.path,
        formPath: swarm.formPath,
        originalSymbol: swarm.species.symbol,
        originalForm: swarm.form,
        sourceKey: "swarms",
        slot: index + 1,
        rate: "",
        hasRate: false,
        levelLabel: String(swarm.label || "").replace(/ swarm$/i, ""),
        changed: speciesControlChanged(route.id, swarm.path, swarm.species, swarm.formPath, swarm.form),
      }));
    }

    function renderGrassTable(route) {
      const morning = pokemonTableByKey(route, "morning");
      const day = pokemonTableByKey(route, "day");
      const night = pokemonTableByKey(route, "night");
      return collapsibleRouteSection(
        "route:grass",
        "Grass",
        `<div class="count">12 slots</div>`,
        `
          <div class="encounter-summary-list grass-summary-list">
            ${encounterSummaryRow(route, { key: "morning", label: "Morning" }, grassSummaryEntries(route, morning), "12 slots")}
            ${encounterSummaryRow(route, { key: "day", label: "Day" }, grassSummaryEntries(route, day), "12 slots")}
            ${encounterSummaryRow(route, { key: "night", label: "Night" }, grassSummaryEntries(route, night), "12 slots")}
          </div>
        `,
        "route-compact-section grass-compact-section"
      );
    }

    function renderPokemonSlotTable(route, key) {
      const table = pokemonTableByKey(route, key);
      return collapsibleRouteSection(
        `route:pokemon:${key}`,
        table.label,
        `<div class="count">${esc(table.slots.length)} slots</div>`,
        `
          <div class="encounter-slot-list pokemon-slot-list">
            ${table.slots.map(slot => `
              <article class="encounter-slot-card" style="--slot-rate:${esc(grassRatePercent(slot.weight ?? 0))}%; --slot-accent:#6d28d9">
                <div class="encounter-weight-bar" aria-hidden="true"></div>
                <div class="encounter-slot-main">
                  <div class="encounter-slot-meta">
                    ${encounterStat("Slot", slot.slot)}
                    ${encounterStat("Rate", `${slot.weight ?? ""}%`)}
                  </div>
                  ${encounterSpeciesField(route.id, slot.path, slot.species, slot.formPath, slot.form)}
                </div>
              </article>
            `).join("")}
          </div>
        `
      );
    }

    function renderEncounterSlotTable(route, table) {
      return collapsibleRouteSection(
        `route:slot:${table.key || table.label}`,
        table.label,
        `<div class="count">${esc(table.slots.length)} slots</div>`,
        `
          <div class="encounter-slot-list encounter-slot-list-with-levels">
            ${table.slots.map(slot => `
              <article class="encounter-slot-card" style="--slot-rate:${esc(grassRatePercent(slot.weight ?? 0))}%; --slot-accent:#0369a1">
                <div class="encounter-weight-bar" aria-hidden="true"></div>
                <div class="encounter-slot-main with-levels">
                  <div class="encounter-slot-meta">
                    ${encounterStat("Slot", slot.slot)}
                    ${encounterStat("Rate", `${slot.weight ?? ""}%`)}
                  </div>
                  ${encounterSpeciesField(route.id, slot.paths.species, slot.species, slot.paths.form, slot.form)}
                  <div class="encounter-levels">
                    ${encounterNumberField(route.id, slot.paths.minLevel, slot.minLevel, "Min", "level")}
                    ${encounterNumberField(route.id, slot.paths.maxLevel, slot.maxLevel, "Max", "level")}
                  </div>
                </div>
              </article>
            `).join("")}
          </div>
        `
      );
    }

    function renderSwarms(route) {
      return collapsibleRouteSection(
        "route:swarms",
        "Swarms",
        "",
        `
          <div class="swarm-grid">
            ${route.swarms.map(swarm => routeSpeciesInput(route.id, swarm.path, swarm.species, swarm.label, swarm.formPath, swarm.form)).join("")}
          </div>
        `
      );
    }

    function sourceTableByKey(route, key) {
      return route.slotTables.find(table => table.key === key);
    }

    function sourceChipClass(key) {
      return `source-${routeGroupClassName(key)}`;
    }

    function sourceSlotChanged(routeId, slot) {
      return speciesControlChanged(routeId, slot.paths.species, slot.species, slot.paths.form, slot.form)
        || routeValueChanged(routeId, slot.paths.minLevel, slot.minLevel)
        || routeValueChanged(routeId, slot.paths.maxLevel, slot.maxLevel);
    }

    function sourcePokemonChanged(routeId, slot) {
      return speciesControlChanged(routeId, slot.path, slot.species, slot.formPath, slot.form);
    }

    function sourceRowTitle(group, value, label = "") {
      return `
        <div class="row-title compact-stats source-row-title ${label ? "with-label" : ""}" title="${esc(group.label || label || "")}">
          ${routeEncounterIconSet(group)}
          ${label ? `<span class="source-row-label">${esc(label)}</span>` : `<strong>${esc(value)}</strong>`}
        </div>
      `;
    }

    function sourceSlotRow(routeId, table, slot) {
      const changed = sourceSlotChanged(routeId, slot);
      return `
        <article class="flat-encounter-row source-editor-row ${esc(sourceChipClass(table.key))}" style="--source-rate:${esc(grassRatePercent(slot.weight ?? 0))}%">
          <div class="row-index">#${esc(slot.slot)}</div>
          ${sourceRowTitle({ key: table.key, label: table.label }, `${slot.weight ?? ""}%`)}
          <div class="row-groups source-entry-groups">
            <div class="route-field compact-pill source-entry-cell has-levels ${changed ? "changed" : ""}">
              ${compactSpeciesControl(routeId, slot.paths.species, slot.species, slot.paths.form, slot.form)}
              <span class="source-level-controls">
                ${compactNumberControl(routeId, slot.paths.minLevel, slot.minLevel, "Lv", "level", 0, 100, "level-min")}
                <span class="level-dash">-</span>
                ${compactNumberControl(routeId, slot.paths.maxLevel, slot.maxLevel, "", "level", 0, 100, "level-max")}
              </span>
            </div>
          </div>
        </article>
      `;
    }

    function sourcePokemonRow(routeId, table, slot) {
      const changed = sourcePokemonChanged(routeId, slot);
      return `
        <article class="flat-encounter-row source-editor-row ${esc(sourceChipClass(table.key))}" style="--source-rate:${esc(grassRatePercent(slot.weight ?? 0))}%">
          <div class="row-index">#${esc(slot.slot)}</div>
          ${sourceRowTitle({ key: table.key, label: table.label }, `${slot.weight ?? ""}%`)}
          <div class="row-groups source-entry-groups">
            <div class="route-field compact-pill source-entry-cell ${changed ? "changed" : ""}">
              ${compactSpeciesControl(routeId, slot.path, slot.species, slot.formPath, slot.form)}
            </div>
          </div>
        </article>
      `;
    }

    function sourceSwarmRow(routeId, swarm, index) {
      const changed = speciesControlChanged(routeId, swarm.path, swarm.species, swarm.formPath, swarm.form);
      const label = String(swarm.label || "Swarm")
        .replace(/ swarm$/i, "")
        .replace("Good rod", "Good")
        .replace("Super rod", "Super");
      return `
        <article class="flat-encounter-row source-editor-row source-swarms" style="--source-rate:100%">
          <div class="row-index">#${esc(index + 1)}</div>
          ${sourceRowTitle({ key: "swarms", label: swarm.label || "Swarms" }, "", label)}
          <div class="row-groups source-entry-groups">
            <div class="route-field compact-pill source-entry-cell ${changed ? "changed" : ""}">
              ${compactSpeciesControl(routeId, swarm.path, swarm.species, swarm.formPath, swarm.form)}
            </div>
          </div>
        </article>
      `;
    }

    function renderOtherSourcesPanel(route) {
      const rows = [];
      ["surf", "oldRod", "goodRod", "superRod", "rockSmash"].forEach(key => {
        const table = sourceTableByKey(route, key);
        if (!table || !table.slots.length) return;
        rows.push(encounterSummaryRow(
          route,
          { key: table.key, label: table.label },
          sourceSlotSummaryEntries(route, table),
          `${table.slots.length} slots`
        ));
      });

      const visibleHeadbuttTables = (route.headbuttTables || []).filter(table =>
        table.slots.length
          && (Number(table.treeCount || 0) > 0 || table.slots.some(slot => slot.species?.symbol !== "SPECIES_NONE"))
      );
      visibleHeadbuttTables.forEach(table => {
        const treeCount = Number(table.treeCount || 0);
        rows.push(encounterSummaryRow(
          route,
          { key: table.key, label: table.label },
          sourceSlotSummaryEntries(route, table),
          `${treeCount} tree${treeCount === 1 ? "" : "s"}`
        ));
      });

      rows.push(["hoenn", "sinnoh"].map(key => {
        const table = pokemonTableByKey(route, key);
        if (!table || !table.slots.length) return "";
        return encounterSummaryRow(
          route,
          { key: table.key, label: table.label },
          pokemonSlotSummaryEntries(route, table),
          `${table.slots.length} slots`
        );
      }).join(""));

      if (route.swarms.length) {
        rows.push(encounterSummaryRow(
          route,
          { key: "swarms", label: "Swarms" },
          swarmSummaryEntries(route),
          `${route.swarms.length} overlays`
        ));
      }

      const slotCount = route.slotTables.reduce((total, table) => total + table.slots.length, 0)
        + visibleHeadbuttTables.reduce((total, table) => total + table.slots.length, 0)
        + route.pokemonTables.filter(table => ["hoenn", "sinnoh"].includes(table.key)).reduce((total, table) => total + table.slots.length, 0)
        + route.swarms.length;
      return collapsibleRouteSection(
        "route:sources",
        "Other Sources",
        `<div class="count">${esc(slotCount)} slots</div>`,
        `<div class="encounter-summary-list source-summary-list">${rows.join("")}</div>`,
        "route-compact-section source-compact-section"
      );
    }

    function routeSpeciesSwapTargets(route, sourceSymbol) {
      const targets = [];
      const addTarget = (path, formPath, originalSpecies, originalForm, meta = {}) => {
        if (!path) return;
        const currentBaseSymbol = routePendingValue(route.id, path, originalSpecies.symbol);
        const currentForm = routePendingValue(route.id, formPath, originalForm);
        const currentSpecies = routeDisplaySpecies(currentBaseSymbol, currentForm);
        if (currentSpecies.symbol === sourceSymbol) {
          targets.push({
            path,
            formPath,
            originalSymbol: originalSpecies.symbol,
            originalForm,
            currentSymbol: currentSpecies.symbol,
            currentBaseSymbol,
            currentForm,
            currentSpecies,
            ...meta
          });
        }
      };

      route.pokemonTables.forEach(table => {
        table.slots.forEach((slot, index) => {
          const isGrassTime = ["morning", "day", "night"].includes(table.key);
          const grassLevel = isGrassTime ? route.grassLevels[index] : null;
          const levelValue = grassLevel ? routePendingValue(route.id, grassLevel.path, grassLevel.value) : "";
          addTarget(slot.path, slot.formPath, slot.species, slot.form, {
            id: `${table.key}:${index}`,
            source: isGrassTime ? `Grass ${table.label}` : table.label,
            sourceKey: table.key,
            sourceLabel: isGrassTime ? `Grass ${table.label}` : table.label,
            slot: slot.slot,
            rate: slot.weight,
            level: grassLevel ? levelValue : null,
            levelLabel: grassLevel ? `Lv ${levelValue}` : "",
            levelPath: grassLevel ? grassLevel.path : "",
            originalLevel: grassLevel ? grassLevel.value : "",
          });
        });
      });
      route.slotTables.forEach(table => {
        table.slots.forEach((slot, index) => {
          const minLevel = routePendingValue(route.id, slot.paths.minLevel, slot.minLevel);
          const maxLevel = routePendingValue(route.id, slot.paths.maxLevel, slot.maxLevel);
          const level = levelRangeLabel(minLevel, maxLevel);
          addTarget(slot.paths.species, slot.paths.form, slot.species, slot.form, {
            id: `${table.key}:${index}`,
            source: table.label,
            sourceKey: table.key,
            sourceLabel: table.label,
            slot: slot.slot,
            rate: slot.weight,
            level: level,
            levelLabel: level,
            minLevelPath: slot.paths.minLevel,
            maxLevelPath: slot.paths.maxLevel,
            originalMinLevel: slot.minLevel,
            originalMaxLevel: slot.maxLevel,
            currentMinLevel: minLevel,
            currentMaxLevel: maxLevel,
          });
        });
      });
      (route.headbuttTables || []).forEach(table => {
        table.slots.forEach((slot, index) => {
          const minLevel = routePendingValue(route.id, slot.paths.minLevel, slot.minLevel);
          const maxLevel = routePendingValue(route.id, slot.paths.maxLevel, slot.maxLevel);
          const level = levelRangeLabel(minLevel, maxLevel);
          addTarget(slot.paths.species, slot.paths.form, slot.species, slot.form, {
            id: `${table.key}:${table.mapId}:${index}`,
            source: table.label,
            sourceKey: table.key,
            sourceLabel: table.label,
            slot: slot.slot,
            rate: slot.weight,
            level: level,
            levelLabel: level,
            minLevelPath: slot.paths.minLevel,
            maxLevelPath: slot.paths.maxLevel,
            originalMinLevel: slot.minLevel,
            originalMaxLevel: slot.maxLevel,
            currentMinLevel: minLevel,
            currentMaxLevel: maxLevel,
          });
        });
      });
      route.swarms.forEach((swarm, index) => addTarget(swarm.path, swarm.formPath, swarm.species, swarm.form, {
        id: `swarm:${index}`,
        source: swarm.label,
        sourceKey: "swarms",
        sourceLabel: "Swarms",
        slot: "",
        rate: "",
        level: "",
        levelLabel: "",
      }));
      return targets;
    }

    function closeRouteSpeciesSwap() {
      routeSwapState = null;
      if (els.routeSwapDialog.open) {
        els.routeSwapDialog.close();
      }
      els.routeSwapDialog.innerHTML = "";
    }

    function routeSwapTargetLabel(target, includeSlot = true) {
      const parts = [];
      if (includeSlot && target.slot !== "" && target.slot !== null && target.slot !== undefined) {
        parts.push(`#${target.slot}`);
      }
      if (target.rate !== "" && target.rate !== null && target.rate !== undefined) {
        parts.push(`${formatEncounterRate(target.rate)}%`);
      }
      if (target.levelLabel) {
        parts.push(target.levelLabel);
      }
      return parts.join(" · ");
    }

    function routeSwapLevelControls(target) {
      if (target.levelPath) {
        return `
          <span class="route-swap-levels">
            <label class="route-swap-level-field">
              <span>Lv</span>
              <input class="route-swap-level-input" type="number" min="0" max="100" step="1" value="${esc(target.level)}" data-level-role="single" data-path="${esc(target.levelPath)}" data-original="${esc(target.originalLevel)}">
            </label>
          </span>
        `;
      }
      if (target.minLevelPath && target.maxLevelPath) {
        return `
          <span class="route-swap-levels">
            <label class="route-swap-level-field">
              <span>Min</span>
              <input class="route-swap-level-input" type="number" min="0" max="100" step="1" value="${esc(target.currentMinLevel)}" data-level-role="min" data-path="${esc(target.minLevelPath)}" data-original="${esc(target.originalMinLevel)}">
            </label>
            <label class="route-swap-level-field">
              <span>Max</span>
              <input class="route-swap-level-input" type="number" min="0" max="100" step="1" value="${esc(target.currentMaxLevel)}" data-level-role="max" data-path="${esc(target.maxLevelPath)}" data-original="${esc(target.originalMaxLevel)}">
            </label>
          </span>
        `;
      }
      return "";
    }

    function routeSwapSourceClass(target) {
      const key = String(target.sourceKey || "other");
      const known = new Set(["grass", "morning", "day", "night", "surf", "oldRod", "goodRod", "superRod", "rockSmash", "headbuttNormal", "headbuttSpecial", "hoenn", "sinnoh", "swarms"]);
      return known.has(key) ? `source-${key}` : "source-other";
    }

    function routeSwapEntryPrimary(target) {
      if (target.rate !== "" && target.rate !== null && target.rate !== undefined) {
        return `${formatEncounterRate(target.rate)}%`;
      }
      return target.levelLabel || "Entry";
    }

    function routeSwapEntrySecondary(target) {
      if (target.rate !== "" && target.rate !== null && target.rate !== undefined) {
        return target.levelLabel || "";
      }
      return "";
    }

    function routeSwapEntryRow(target, index) {
      const currentSpecies = target.currentSpecies || speciesBySymbol(target.currentSymbol);
      const sourceLabel = target.sourceLabel || target.source || "";
      const secondary = routeSwapEntrySecondary(target);
      return `
        <label class="route-swap-entry ${esc(routeSwapSourceClass(target))} ${target.highlighted ? "highlighted" : ""}" data-swap-entry="${esc(index)}" data-path="${esc(target.path)}" data-form-path="${esc(target.formPath)}" data-original="${esc(target.originalSymbol)}" data-original-form="${esc(target.originalForm)}" ${target.highlighted ? 'data-highlighted="true"' : ""}>
          <span class="route-swap-entry-source" title="${esc(sourceLabel)}" aria-label="${esc(sourceLabel)}">
            ${routeEncounterIconSet({ key: target.sourceKey, label: sourceLabel })}
          </span>
          <span class="route-swap-entry-meta">
            <strong>${esc(routeSwapEntryPrimary(target))}</strong>
            ${secondary ? `<span>${esc(secondary)}</span>` : ""}
          </span>
          <span class="route-swap-entry-control">
            ${iconTag(currentSpecies, "mon-icon")}
            <input class="route-swap-entry-input" type="text" list="routeSpeciesOptions" value="${esc(routeSpeciesInputValue(target.currentSymbol))}" data-path="${esc(target.path)}" data-form-path="${esc(target.formPath)}" data-original="${esc(target.originalSymbol)}" data-original-form="${esc(target.originalForm)}" data-current="${esc(target.currentSymbol)}" data-current-symbol="${esc(target.currentBaseSymbol)}" data-current-form="${esc(target.currentForm)}" autocomplete="off">
            ${routeSwapLevelControls(target)}
          </span>
        </label>
      `;
    }

    function routeSwapContextFromButton(button) {
      const targetId = button?.dataset?.swapTargetId || "";
      const targetEntries = targetId ? encounterSummaryTargetsById.get(targetId) || [] : [];
      return {
        sourceKey: button?.dataset?.swapSourceKey || "",
        highlightPaths: new Set(targetEntries.map(entry => entry.path).filter(Boolean)),
      };
    }

    function routeSwapGroupedTargets(targets) {
      const order = ["morning", "day", "night", "surf", "oldRod", "goodRod", "superRod", "rockSmash", "headbuttNormal", "headbuttSpecial", "hoenn", "sinnoh", "swarms"];
      const orderIndex = new Map(order.map((key, index) => [key, index]));
      const groups = new Map();
      targets.forEach((target, index) => {
        const key = target.sourceKey || target.source || "other";
        if (!groups.has(key)) {
          groups.set(key, {
            key,
            label: target.sourceLabel || target.source || "Other",
            targets: [],
            firstIndex: index,
          });
        }
        groups.get(key).targets.push({ ...target, swapIndex: index });
      });
      return Array.from(groups.values()).sort((a, b) => {
        const aOrder = orderIndex.has(a.key) ? orderIndex.get(a.key) : 1000 + a.firstIndex;
        const bOrder = orderIndex.has(b.key) ? orderIndex.get(b.key) : 1000 + b.firstIndex;
        return aOrder - bOrder;
      });
    }

    function routeSwapGroupSection(group) {
      return group.targets.map(target => routeSwapEntryRow(target, target.swapIndex)).join("");
    }

    function renderRouteSwapDialog(route, sourceSpecies, targets) {
      const routeLabel = `${route.name} ${routeMapText(route)}`;
      const groups = routeSwapGroupedTargets(targets);
      const highlightedCount = targets.filter(target => target.highlighted).length;
      els.routeSwapDialog.innerHTML = `
        <form class="route-swap-card" method="dialog">
          <div class="route-swap-head">
            ${iconTag(sourceSpecies, "mon-icon")}
            <div class="route-swap-title">
              <strong>Swap ${esc(routeSpeciesShortSymbol(sourceSpecies.symbol))}</strong>
              <span>${esc(routeLabel)} · ${esc(targets.length)} entr${targets.length === 1 ? "y" : "ies"}</span>
            </div>
          </div>
          <label class="route-swap-field">
            <span>Replace all with</span>
            <input id="routeSwapInput" class="route-swap-input" type="text" list="routeSpeciesOptions" autocomplete="off" placeholder="Pokemon">
          </label>
          <div class="route-swap-entries">
            ${groups.map(routeSwapGroupSection).join("")}
          </div>
          <div class="route-swap-help">Leave the top field empty to edit only selected entries. Regional choices update the form value; levels can be edited per entry; rates stay unchanged.</div>
          <div class="route-swap-error" aria-live="polite"></div>
          <div class="route-swap-actions">
            <button class="control" type="button" data-route-swap-action="cancel">Cancel</button>
            ${highlightedCount ? `<button class="control highlight-action" type="submit" data-route-swap-action="apply-highlighted" title="Swap ${esc(highlightedCount)} highlighted entr${highlightedCount === 1 ? "y" : "ies"}">Swap highlighted</button>` : ""}
            <button class="control primary-action" type="submit" data-route-swap-action="apply">Swap</button>
          </div>
        </form>
      `;
    }

    function openRouteSpeciesSwap(routeId, sourceSymbol, context = {}) {
      const route = routesById.get(String(routeId));
      if (!route || !sourceSymbol) return;
      if (String(selectedRouteId) !== String(route.id)) {
        selectRoute(route.id);
      }
      const sourceSpecies = routeSpeciesOption(sourceSymbol) || speciesBySymbol(sourceSymbol);
      const highlightPaths = context.highlightPaths instanceof Set
        ? context.highlightPaths
        : new Set(context.highlightPaths || []);
      const highlightSourceKey = context.sourceKey || "";
      const targets = routeSpeciesSwapTargets(route, sourceSpecies.symbol).map(target => ({
        ...target,
        highlighted: highlightPaths.size
          ? highlightPaths.has(target.path)
          : Boolean(highlightSourceKey && target.sourceKey === highlightSourceKey),
      }));
      if (!targets.length) {
        setEncounterSaveStatus(`No ${routeSpeciesShortSymbol(sourceSpecies.symbol)} entries on ${route.name}`);
        return;
      }
      routeSwapState = {
        routeId: String(route.id),
        sourceSymbol: sourceSpecies.symbol,
      };
      renderRouteSwapDialog(route, sourceSpecies, targets);
      if (!els.routeSwapDialog.open) {
        els.routeSwapDialog.showModal();
      }
      const input = els.routeSwapDialog.querySelector("#routeSwapInput");
      if (input) {
        input.focus();
      }
    }

    function setRouteSwapError(message) {
      const error = els.routeSwapDialog.querySelector(".route-swap-error");
      if (error) error.textContent = message || "";
    }

    function updateRouteSwapEntryIcon(input) {
      const row = input.closest(".route-swap-entry");
      if (!row) return;
      const option = routeSpeciesOption(input.value);
      input.classList.toggle("invalid", Boolean(input.value.trim() && !option));
      if (!option) return;
      const icon = row.querySelector(".mon-icon");
      if (icon && icon.dataset.symbol !== option.symbol) {
        icon.outerHTML = iconTag(option, "mon-icon");
      }
    }

    function routeSwapInputSpecies(input) {
      const option = routeSpeciesOption(input.value);
      input.classList.toggle("invalid", !option);
      return option;
    }

    function routeSwapEntryValue(entryInput, bulkSpecies = null) {
      const raw = String(entryInput.value || "").trim();
      if (!raw && bulkSpecies) {
        entryInput.classList.remove("invalid");
        return bulkSpecies;
      }
      const option = routeSwapInputSpecies(entryInput);
      if (!option) return null;
      if (bulkSpecies && option.symbol === entryInput.dataset.current) {
        return bulkSpecies;
      }
      return option;
    }

    function routeSwapReadLevelInput(input) {
      const raw = String(input.value || "").trim();
      const value = Number(raw);
      const min = Number(input.min || 0);
      const max = Number(input.max || 100);
      const valid = raw !== "" && Number.isInteger(value) && value >= min && value <= max;
      input.classList.toggle("invalid", !valid);
      return {
        valid,
        input,
        path: input.dataset.path,
        original: input.dataset.original || "0",
        value: String(value),
        role: input.dataset.levelRole || "",
      };
    }

    function routeSwapLevelUpdates(row) {
      const inputs = Array.from(row.querySelectorAll(".route-swap-level-input"));
      if (!inputs.length) return { invalid: 0, updates: [] };
      const levels = inputs.map(routeSwapReadLevelInput);
      let invalid = levels.filter(level => !level.valid).length;
      const minLevel = levels.find(level => level.role === "min");
      const maxLevel = levels.find(level => level.role === "max");
      if (minLevel && maxLevel && minLevel.valid && maxLevel.valid && Number(minLevel.value) > Number(maxLevel.value)) {
        minLevel.input.classList.add("invalid");
        maxLevel.input.classList.add("invalid");
        invalid += 1;
      }
      const updates = invalid
        ? []
        : levels
          .filter(level => level.path && String(level.value) !== String(level.original))
          .map(level => ({
            path: level.path,
            original: level.original,
            value: level.value,
          }));
      return { invalid, updates };
    }

    function applyRouteSpeciesSwap(options = {}) {
      if (!routeSwapState) return false;
      const highlightedOnly = Boolean(options.highlightedOnly);
      const route = routesById.get(String(routeSwapState.routeId));
      const input = els.routeSwapDialog.querySelector("#routeSwapInput");
      if (!route || !input) return false;
      const bulkRaw = String(input.value || "").trim();
      const bulkReplacement = bulkRaw ? routeSpeciesOption(bulkRaw) : null;
      input.classList.toggle("invalid", Boolean(bulkRaw && !bulkReplacement));
      if (bulkRaw && !bulkReplacement) {
        setRouteSwapError("Choose a valid Pokemon for the bulk replacement.");
        return false;
      }

      const allEntryRows = Array.from(els.routeSwapDialog.querySelectorAll(".route-swap-entry"));
      const entryRows = highlightedOnly
        ? allEntryRows.filter(row => row.dataset.highlighted === "true")
        : allEntryRows;
      if (highlightedOnly && !entryRows.length) {
        setRouteSwapError("No highlighted entries.");
        return false;
      }
      const updates = [];
      let invalidCount = 0;
      let changedEntryCount = 0;
      entryRows.forEach(row => {
        const entryInput = row.querySelector(".route-swap-entry-input");
        if (!entryInput) return;
        const replacement = routeSwapEntryValue(entryInput, bulkReplacement);
        if (!replacement) {
          invalidCount += 1;
          return;
        }
        const currentSymbol = entryInput.dataset.current;
        const path = entryInput.dataset.path;
        const formPath = entryInput.dataset.formPath;
        const originalSymbol = entryInput.dataset.original;
        const originalForm = entryInput.dataset.originalForm || "0";
        const writeSymbol = routeSpeciesWriteSymbol(replacement);
        const writeForm = routeSpeciesWriteForm(replacement);
        let entryChanged = false;
        if (!(!bulkReplacement && replacement.symbol === routeSwapState.sourceSymbol) && replacement.symbol !== currentSymbol) {
          updates.push({ path, original: originalSymbol, value: writeSymbol });
          updates.push({ path: formPath, original: originalForm, value: writeForm });
          entryChanged = true;
        }
        const levelResult = routeSwapLevelUpdates(row);
        invalidCount += levelResult.invalid;
        if (levelResult.updates.length) {
          updates.push(...levelResult.updates);
          entryChanged = true;
        }
        if (entryChanged) changedEntryCount += 1;
      });

      if (invalidCount) {
        setRouteSwapError(`${invalidCount} invalid entr${invalidCount === 1 ? "y" : "ies"}.`);
        return false;
      }
      if (!updates.length) {
        setRouteSwapError(highlightedOnly ? "No highlighted entries changed." : "No entries changed.");
        return false;
      }

      updates.forEach(update => {
        setEncounterEdit(route.id, update.path, update.original, update.value);
      });
      syncPendingRouteId(route.id);
      closeRouteSpeciesSwap();
      renderRouteDetailHead();
      renderRouteEditor();
      refreshRouteRow(route.id);
      updateEncounterSaveControls();
      updateGlobalEditStatus();
      const scope = highlightedOnly ? " highlighted" : "";
      setEncounterSaveStatus(`Updated ${changedEntryCount}${scope} entr${changedEntryCount === 1 ? "y" : "ies"} on ${route.name}`);
      return true;
    }

    function commitEncounterSummarySpeciesInput(input) {
      const route = routesById.get(String(input.dataset.routeId));
      const targets = encounterSummaryTargetsById.get(input.dataset.summaryTargetId) || [];
      if (!route || !targets.length) return false;
      const raw = String(input.value || "").trim();
      if (!raw) {
        input.value = routeSpeciesInputValue(input.dataset.currentSymbol);
        input.classList.remove("invalid");
        return false;
      }
      const replacement = routeSpeciesOption(raw);
      if (!replacement) {
        input.classList.add("invalid");
        setEncounterSaveStatus("Choose a valid Pokemon");
        updateEncounterSaveControls();
        return false;
      }

      const writeSymbol = routeSpeciesWriteSymbol(replacement);
      const writeForm = routeSpeciesWriteForm(replacement);
      let changedCount = 0;
      targets.forEach(target => {
        const currentSymbol = routePendingValue(route.id, target.path, target.originalSymbol);
        const currentForm = routePendingValue(route.id, target.formPath, target.originalForm);
        if (String(currentSymbol) === String(writeSymbol) && String(currentForm) === String(writeForm)) {
          return;
        }
        setEncounterEdit(route.id, target.path, target.originalSymbol, writeSymbol);
        setEncounterEdit(route.id, target.formPath, target.originalForm, writeForm);
        changedCount += 1;
      });

      if (!changedCount) {
        input.value = routeSpeciesInputValue(input.dataset.currentSymbol);
        input.classList.remove("invalid");
        setEncounterSaveStatus("No entries changed");
        return false;
      }

      syncPendingRouteId(route.id);
      renderRouteDetailHead();
      renderRouteEditor();
      refreshRouteRow(route.id);
      updateEncounterSaveControls();
      updateGlobalEditStatus();
      setEncounterSaveStatus(`Updated ${changedCount} entr${changedCount === 1 ? "y" : "ies"} on ${route.name}`);
      return true;
    }

    function renderRouteEditor() {
      const route = currentRoute();
      invalidEncounterInputs.clear();
      encounterSummaryTargetsById.clear();
      encounterSummaryTargetSequence = 0;
      if (!route) {
        els.routeEditor.innerHTML = `<div class="empty">No route selected</div>`;
        return;
      }
      els.routeEditor.innerHTML = `
        <div class="route-editor-layout">
          <div class="route-editor-primary">
            ${renderGrassTable(route)}
          </div>
          <div class="route-editor-secondary">
            ${renderOtherSourcesPanel(route)}
          </div>
        </div>
      `;
      bindCollapseHandlers(els.routeEditor);
      els.routeEditor.scrollTop = 0;
      updateEncounterSaveControls();
    }

    function scheduleRouteEditorRender() {
      if (routeEditorRenderFrame) {
        cancelAnimationFrame(routeEditorRenderFrame);
      }
      routeEditorRenderFrame = requestAnimationFrame(() => {
        routeEditorRenderFrame = null;
        renderRouteEditor();
      });
    }

    function renderRouteGlobalSettings() {
      invalidSpawnSettingInputs.clear();
      els.routeGlobalSettings.innerHTML = renderSpawnSettings();
    }

    function renderEncounters() {
      renderRouteSpeciesDatalist();
      renderRouteSpawnTypeFilters();
      renderRouteList();
      renderRouteGlobalSettings();
      renderRouteDetailHead();
      renderRouteEditor();
      updateEncounterSaveControls();
    }

    function selectRoute(routeId) {
      if (!routesById.has(String(routeId))) return;
      if (String(selectedRouteId) === String(routeId)) return;
      const previousRouteId = selectedRouteId;
      selectedRouteId = Number(routeId);
      updateSelectedRouteRow(previousRouteId);
      renderRouteDetailHead();
      scheduleRouteEditorRender();
    }

    function currentAssignment() {
      return assignmentsBySymbol.get(selectedSymbol) || null;
    }

    function currentProfileClass() {
      if (!appData?.classes?.length) return null;
      if (selectedClassIndex !== null) {
        const item = appData.classes.find(row => String(row.index) === String(selectedClassIndex));
        if (item) return item;
      }
      const assignment = assignmentsBySymbol.get(selectedSymbol);
      if (assignment) {
        selectedClassIndex = profilePendingClassValueForSymbol(selectedSymbol);
        return appData.classes.find(row => String(row.index) === String(selectedClassIndex)) || appData.classes[0];
      }
      selectedClassIndex = appData.classes[0].index;
      return appData.classes[0];
    }

    function updateProfileIconSelection() {
      profileIconButtonsBySymbol.clear();
      document.querySelectorAll(".profile-icon-button[data-symbol], .profile-member-chip[data-symbol]").forEach(button => {
        const buttons = profileIconButtonsBySymbol.get(button.dataset.symbol) || [];
        buttons.push(button);
        profileIconButtonsBySymbol.set(button.dataset.symbol, buttons);
      });
      profileIconButtonsBySymbol.forEach((buttons, symbol) => {
        buttons.forEach(button => button.classList.toggle("active", symbol === selectedSymbol));
      });
    }

    function visibleListRow(classIndex) {
      return visibleProfileRowsByClass.get(String(classIndex)) || null;
    }

    function updateSelectedListRow(previousClassIndex) {
      const previousRow = previousClassIndex !== null && previousClassIndex !== undefined ? visibleListRow(previousClassIndex) : null;
      if (previousRow) {
        previousRow.classList.remove("active");
      }
      const row = visibleListRow(selectedClassIndex);
      if (row) {
        row.classList.add("active");
      }
    }

    function ensureSelectedListRowRendered() {
      const rows = filteredProfileClasses();
      const selectedIndex = rows.findIndex(row => String(row.index) === String(selectedClassIndex));
      if (selectedIndex < 0) return false;
      if (selectedIndex >= visibleSpeciesLimit || !visibleListRow(selectedClassIndex)) {
        visibleSpeciesLimit = Math.min(rows.length, Math.ceil((selectedIndex + 1) / LIST_PAGE_SIZE) * LIST_PAGE_SIZE);
        renderSpeciesList();
        return true;
      }
      return false;
    }

    function renderSelectedPokemon() {
      renderDetailHead();
      markProfilePanelsDirty("selected");
      renderActiveProfilePanel();
      updateProfileIconSelection();
    }

    function revealActiveListRow() {
      const row = els.speciesList.querySelector(".profile-row.active");
      if (row) {
        row.scrollIntoView({ block: "nearest" });
      }
    }

    function selectProfileClass(classIndex, options = {}) {
      const item = appData.classes.find(row => String(row.index) === String(classIndex));
      if (!item) return;
      const previousClassIndex = selectedClassIndex;
      selectedClassIndex = item.index;
      if (options.tab) {
        activeTab = options.tab;
      }
      if (!ensureSelectedListRowRendered()) {
        updateSelectedListRow(previousClassIndex);
      }
      revealActiveListRow();
      markProfilePanelsDirty("profiles", "selected");
      renderDetailHead();
      renderTabs();
      renderActiveProfilePanel();
      updateProfileIconSelection();
    }

    function selectSpecies(symbol, options = {}) {
      const assignment = assignmentsBySymbol.get(symbol);
      if (!assignment) return;
      const previousClassIndex = selectedClassIndex;
      selectedSymbol = symbol;
      selectedClassIndex = profilePendingClassValueForSymbol(symbol);
      if (options.tab) {
        activeTab = options.tab;
      }
      if (!ensureSelectedListRowRendered()) {
        updateSelectedListRow(previousClassIndex);
      }
      revealActiveListRow();
      renderSelectedPokemon();
      renderTabs();
    }

    function profileChangePayload() {
      const changes = {};
      profileEdits.forEach((raw, key) => {
        const [classIndex, fieldKey] = key.split(":");
        if (!changes[classIndex]) changes[classIndex] = {};
        changes[classIndex][fieldKey] = raw;
      });
      return changes;
    }

    function profileMembershipChangePayload() {
      const changes = {};
      profileMemberEdits.forEach((classIndex, symbol) => {
        changes[symbol] = classIndex;
      });
      return changes;
    }

    function profileOptionForInput(fieldKey, text, preferredRaw = null) {
      const value = String(text || "").trim();
      if (PROFILE_MOVEMENT_FIELDS.has(fieldKey)
          || PROFILE_BEHAVIOR_FIELDS.has(fieldKey)
          || fieldKey === ALERT_RANGE_TYPE_FIELD
          || fieldKey === SPAWN_DESTINATION_TYPE_FIELD) {
        const options = profileOptionsForField(fieldKey);
        const lower = value.toLowerCase();
        const preferred = preferredRaw
          ? options.find(option => option.raw === preferredRaw
            || option.raw === alertRangeBaseRaw(preferredRaw)
            || option.raw === spawnDestinationTypeKeyForRaw(preferredRaw))
          : null;
        if (preferred) {
          const preferredTerms = [
            preferred.raw,
            profileComboRawDisplay(preferred.raw),
            profileComboOptionDisplay(preferred, fieldKey),
            preferred.label,
          ].map(item => String(item || "").trim().toLowerCase());
          if (preferredTerms.includes(lower)) return preferred;
        }
        return options.find(option => [
          option.raw,
          profileComboRawDisplay(option.raw),
          profileComboOptionDisplay(option, fieldKey),
          option.label,
        ].some(item => String(item || "").trim().toLowerCase() === lower)) || null;
      }
      const lookup = profileOptionLookupByField.get(fieldKey);
      if (!lookup) return null;
      const lower = value.toLowerCase();
      const preferred = preferredRaw ? lookup.byRaw.get(preferredRaw) : null;
      if (preferred) {
        const preferredTerms = [
          preferred.raw,
          profileComboRawDisplay(preferred.raw),
          profileComboOptionDisplay(preferred, fieldKey),
          preferred.label,
        ].map(item => String(item || "").trim().toLowerCase());
        if (preferredTerms.includes(lower)) {
          return preferred;
        }
      }
      return lookup.byRaw.get(value)
        || lookup.byRawLower.get(lower)
        || lookup.byDisplayLower.get(lower)
        || lookup.byLabelLower.get(lower)
        || null;
    }

    function trackInvalidInput(set, input, invalid) {
      if (invalid) {
        set.add(input);
      } else {
        set.delete(input);
      }
      input.classList.toggle("invalid", invalid);
    }

    function setProfileEdit(classIndex, fieldKey, raw, originalRaw) {
      const key = editKey(classIndex, fieldKey);
      if (raw === originalRaw) {
        profileEdits.delete(key);
      } else {
        profileEdits.set(key, raw);
      }
    }

    function commitAlertRangeTypeCombo(input, normalize = false, forcedOption = null) {
      const option = forcedOption || profileOptionForInput(ALERT_RANGE_TYPE_FIELD, input.value, input.dataset.original);
      const field = input.closest(".field");
      if (!option) {
        trackInvalidInput(invalidProfileInputs, input, true);
        field.classList.remove("changed");
        return false;
      }
      const currentRaw = pendingProfileValue(input.dataset.classIndex, "alertRange", input.dataset.original);
      const closeEnabled = alertRangeSupportsClose(option.raw) && alertRangeIsCloseRaw(currentRaw);
      const raw = alertRangeRawWithClose(option.raw, closeEnabled);
      if (normalize) {
        input.value = profileComboDisplay(ALERT_RANGE_TYPE_FIELD, raw);
      }
      trackInvalidInput(invalidProfileInputs, input, false);
      setProfileEdit(input.dataset.classIndex, "alertRange", raw, input.dataset.original);
      field.classList.toggle("changed", raw !== input.dataset.original);
      return true;
    }

    function commitSpawnDestinationTypeCombo(input, normalize = false, forcedOption = null) {
      const option = forcedOption || profileOptionForInput(SPAWN_DESTINATION_TYPE_FIELD, input.value, input.dataset.original);
      const field = input.closest(".field");
      if (!option) {
        trackInvalidInput(invalidProfileInputs, input, true);
        field.classList.remove("changed");
        return false;
      }
      const currentRaw = pendingProfileValue(input.dataset.classIndex, "spawnDestination", input.dataset.original);
      const currentInfo = spawnDestinationPlayerInfo(currentRaw);
      const targetType = option.raw;
      const preferredDistance = currentInfo && spawnDestinationTypeKeyForRaw(currentRaw) === targetType
        ? currentInfo.distance
        : null;
      const raw = spawnDestinationRawForType(targetType, preferredDistance);
      if (normalize) {
        input.value = profileComboDisplay(SPAWN_DESTINATION_TYPE_FIELD, raw);
      }
      trackInvalidInput(invalidProfileInputs, input, false);
      setProfileEdit(input.dataset.classIndex, "spawnDestination", raw, input.dataset.original);
      field.classList.toggle("changed", raw !== input.dataset.original);
      return true;
    }

    function commitProfileCombo(input, normalize = false, forcedOption = null) {
      if (input.dataset.field === ALERT_RANGE_TYPE_FIELD) {
        return commitAlertRangeTypeCombo(input, normalize, forcedOption);
      }
      if (input.dataset.field === SPAWN_DESTINATION_TYPE_FIELD) {
        return commitSpawnDestinationTypeCombo(input, normalize, forcedOption);
      }
      const option = forcedOption || profileOptionForInput(input.dataset.field, input.value, input.dataset.original);
      const field = input.closest(".field");
      if (!option) {
        trackInvalidInput(invalidProfileInputs, input, true);
        field.classList.remove("changed");
        return false;
      }
      if (normalize) {
        input.value = profileComboDisplay(input.dataset.field, option.raw);
      }
      trackInvalidInput(invalidProfileInputs, input, false);
      setProfileEdit(input.dataset.classIndex, input.dataset.field, option.raw, input.dataset.original);
      field.classList.toggle("changed", option.raw !== input.dataset.original);
      return true;
    }

    function commitAllProfileCombos(normalize = false) {
      return Array.from(els.profilesTab.querySelectorAll(".profile-combo"))
        .map(input => commitProfileCombo(input, normalize))
        .every(Boolean);
    }

    function invalidProfileComboCount() {
      return invalidProfileInputs.size;
    }

    function setProfileComboExpanded(input, expanded) {
      if (input) input.setAttribute("aria-expanded", expanded ? "true" : "false");
    }

    function profileComboSearchTerms(option, fieldKey) {
      return [
        profileComboOptionDisplay(option, fieldKey),
        profileComboRawDisplay(option?.raw),
        option?.label,
        option?.raw,
      ].map(value => String(value || "").toLowerCase()).filter(Boolean);
    }

    function profileComboOptionsForInput(input) {
      const options = profileOptionsForField(input.dataset.field);
      const limit = input.dataset.field === "alertEmote" ? 32 : 12;
      const query = input.dataset.comboFilter === "1"
        ? String(input.value || "").trim().toLowerCase()
        : "";
      const ranked = options
        .map(option => {
          const terms = profileComboSearchTerms(option, input.dataset.field);
          let score = 3;
          if (!query) {
            score = 2;
          } else if (terms.some(term => term === query)) {
            score = 0;
          } else if (terms.some(term => term.startsWith(query))) {
            score = 1;
          } else if (terms.some(term => term.includes(query))) {
            score = 2;
          }
          return { option, score };
        })
        .filter(item => item.score < 3)
        .sort((a, b) => {
          if (a.score !== b.score) return a.score - b.score;
          if (NUMERIC_PROFILE_FIELD_KEYS.has(input.dataset.field)
              && Number.isFinite(a.option.value)
              && Number.isFinite(b.option.value)
              && a.option.value !== b.option.value) {
            return a.option.value - b.option.value;
          }
          return profileComboOptionDisplay(a.option, input.dataset.field)
            .localeCompare(profileComboOptionDisplay(b.option, input.dataset.field));
        });
      const deduped = [];
      const seen = new Map();
      ranked.forEach(item => {
        const display = profileComboOptionDisplay(item.option, input.dataset.field);
        const key = NUMERIC_PROFILE_FIELD_KEYS.has(input.dataset.field)
          ? display.toLowerCase()
          : item.option.raw;
        if (!seen.has(key)) {
          seen.set(key, deduped.length);
          deduped.push(item);
          return;
        }
        if (input.dataset.original && item.option.raw === input.dataset.original) {
          deduped[seen.get(key)] = item;
        }
      });
      return deduped
        .slice(0, limit)
        .map(item => item.option);
    }

    function placeProfileComboMenu(input) {
      const menu = els.profileComboMenu;
      const gap = 4;
      const margin = 8;
      const sourceRect = input.getBoundingClientRect();
      menu.style.width = `${Math.min(Math.max(sourceRect.width, 220), window.innerWidth - margin * 2)}px`;
      const rect = menu.getBoundingClientRect();
      let left = Math.min(window.innerWidth - rect.width - margin, Math.max(margin, sourceRect.left));
      let top = sourceRect.bottom + gap;
      if (top + rect.height + margin > window.innerHeight) {
        top = sourceRect.top - rect.height - gap;
      }
      top = Math.min(window.innerHeight - rect.height - margin, Math.max(margin, top));
      menu.style.left = `${left}px`;
      menu.style.top = `${top}px`;
    }

    function closeProfileComboMenu() {
      setProfileComboExpanded(activeProfileComboInput, false);
      activeProfileComboInput = null;
      profileComboMenuIndex = 0;
      els.profileComboMenu.hidden = true;
      els.profileComboMenu.innerHTML = "";
    }

    function renderProfileComboMenu(input, keepIndex = false) {
      if (!input || !input.isConnected || !profileOptionsForField(input.dataset.field).length) {
        closeProfileComboMenu();
        return;
      }
      const options = profileComboOptionsForInput(input);
      if (!options.length) {
        closeProfileComboMenu();
        return;
      }
      activeProfileComboInput = input;
      profileComboMenuIndex = keepIndex
        ? Math.max(0, Math.min(profileComboMenuIndex, options.length - 1))
        : 0;
      els.profileComboMenu.innerHTML = options.map((option, index) => {
        const active = index === profileComboMenuIndex ? " active" : "";
        const value = !NUMERIC_PROFILE_FIELD_KEYS.has(input.dataset.field)
          && option.value !== undefined
          && option.value !== null
          ? `#${option.value}`
          : "";
        return `
          <button class="profile-combo-option${active}" type="button" data-index="${esc(index)}" data-raw="${esc(option.raw)}">
            <span class="profile-combo-option-main">${esc(profileComboOptionDisplay(option, input.dataset.field))}</span>
            ${value ? `<span class="profile-combo-option-value">${esc(value)}</span>` : ""}
          </button>
        `;
      }).join("");
      els.profileComboMenu.hidden = false;
      setProfileComboExpanded(input, true);
      placeProfileComboMenu(input);
    }

    function chooseProfileComboOption(raw) {
      const input = activeProfileComboInput;
      if (!input) return;
      const option = profileOptionForRaw(input.dataset.field, raw);
      if (!option) return;
      const rerenderSubcontrols = profileFieldRerendersSubcontrols(input.dataset.field);
      input.value = profileComboDisplay(input.dataset.field, option.raw);
      commitProfileCombo(input, false, option);
      updateProfileComboStatus(input, true);
      closeProfileComboMenu();
      if (rerenderSubcontrols) {
        markProfilePanelsDirty("profiles", "selected");
        renderActiveProfilePanel(true);
        return;
      }
      input.focus();
    }

    function moveProfileComboMenu(delta) {
      if (!activeProfileComboInput) return;
      const options = profileComboOptionsForInput(activeProfileComboInput);
      if (!options.length) return;
      profileComboMenuIndex = (profileComboMenuIndex + delta + options.length) % options.length;
      renderProfileComboMenu(activeProfileComboInput, true);
    }

    function setSaveStatus(message, kind = "") {
      els.saveStatus.textContent = message || "";
      els.saveStatus.title = message || "";
      els.saveStatus.classList.remove("status-success", "status-error", "status-busy", "status-warning");
      const text = String(message || "").toLowerCase();
      if (!text) return;
      if (kind) {
        els.saveStatus.classList.add(`status-${kind}`);
      } else if (text.includes("failed") || text.includes("invalid")) {
        els.saveStatus.classList.add("status-error");
      } else if (text.includes("saving") || text.includes("building") || text.includes("opening")) {
        els.saveStatus.classList.add("status-busy");
      } else if (text.includes("pending")) {
        els.saveStatus.classList.add("status-warning");
      } else if (text.includes("saved") || text.includes("succeeded") || text.includes("opened")) {
        els.saveStatus.classList.add("status-success");
      }
    }

    function updateSaveControls() {
      const busy = isSavingProfiles || isSavingProfileMemberships || isSavingProfileOverrides || isSavingEncounters || isSavingSpawnSettings || isManagingProfiles || isBuilding || isSettingShinyCounter;
      const profilesEditable = appData?.profilesAvailable !== false;
      const hasProfileChanges = profilesEditable && (profileEdits.size > 0 || profileMemberEdits.size > 0 || profileOverrideChangeCount() > 0);
      const hasChanges = hasProfileChanges || encounterEdits.size > 0 || spawnSettingEdits.size > 0;
      const hasInvalid = (profilesEditable && invalidProfileComboCount() > 0) || invalidEncounterInputCount() > 0 || invalidSpawnSettingInputCount() > 0;
      els.saveAllChanges.disabled = busy || !hasChanges || hasInvalid;
      els.buildRom.disabled = busy;
      els.openTestNds.disabled = busy;
      els.resetAllEdits.disabled = busy || (!hasChanges && !hasInvalid);
      els.refreshShinyCounter.disabled = isSettingShinyCounter;
      els.resetShinyCounter.disabled = isSettingShinyCounter;
      els.maxShinyCounter.disabled = isSettingShinyCounter;
    }

    function applyShinyCounterStatus(payload) {
      if (!payload || !payload.exists) {
        els.shinyCounterValue.textContent = "--";
        els.shinyCounterRate.textContent = "No save";
        return;
      }
      const counter = Number(payload.counter) || 0;
      const denominator = Number(payload.denominator) || 8192;
      els.shinyCounterValue.textContent = String(counter);
      els.shinyCounterRate.textContent = `1/${denominator}`;
      const suffix = payload.magicOk ? "" : " (not initialized)";
      els.shinyCounterValue.title = `Saved shiny spawn counter${suffix}`;
      els.shinyCounterRate.title = `Current shiny odds: 1 in ${denominator}${suffix}`;
    }

    async function loadShinyCounter(options = {}) {
      try {
        const response = await fetch(`/shiny-counter?ts=${Date.now()}`);
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || `HTTP ${response.status}`);
        }
        applyShinyCounterStatus(result);
        if (options.report) {
          const text = result.exists
            ? `Shiny counter: ${result.counter} (1/${result.denominator})`
            : "No test.dsv found";
          setSaveStatus(text, result.exists ? "success" : "warning");
        }
        return result;
      } catch (error) {
        els.shinyCounterValue.textContent = "--";
        els.shinyCounterRate.textContent = "Load failed";
        if (options.report) {
          setSaveStatus(`Shiny counter failed: ${error.message}`, "error");
        }
        return null;
      }
    }

    async function setShinyCounter(counter) {
      if (isSettingShinyCounter) return;
      isSettingShinyCounter = true;
      updateSaveControls();
      setSaveStatus(`Setting shiny counter to ${counter}...`, "busy");
      try {
        const response = await fetch("/shiny-counter", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ counter })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || `HTTP ${response.status}`);
        }
        applyShinyCounterStatus(result);
        setSaveStatus(`${result.message || "Shiny counter updated"} (1/${result.denominator})`, "success");
      } catch (error) {
        setSaveStatus(`Shiny counter failed: ${error.message}`, "error");
      } finally {
        isSettingShinyCounter = false;
        updateSaveControls();
      }
    }

    async function saveProfileChanges(options = {}) {
      if (isSavingProfiles) return false;
      if (!profileEdits.size) return true;
      if (!commitAllProfileCombos(true)) {
        updateSaveControls();
        setSaveStatus(`${invalidProfileComboCount()} invalid value${invalidProfileComboCount() === 1 ? "" : "s"}`);
        return false;
      }
      isSavingProfiles = true;
      updateSaveControls();
      setSaveStatus("Saving...");
      try {
        const response = await fetch("/save-profiles", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ changes: profileChangePayload() })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || `HTTP ${response.status}`);
        }
        profileEdits.clear();
        setSaveStatus(result.message || "Saved");
        if (options.reload !== false) {
          await loadData({ keepStatus: true });
          setSaveStatus(result.message || "Saved");
        }
        return true;
      } catch (error) {
        setSaveStatus(`Save failed: ${error.message}`);
        return false;
      } finally {
        isSavingProfiles = false;
        updateSaveControls();
      }
    }

    async function saveProfileMembershipChanges(options = {}) {
      if (isSavingProfileMemberships) return false;
      if (!profileMemberEdits.size) return true;
      isSavingProfileMemberships = true;
      updateSaveControls();
      setSaveStatus("Saving...");
      try {
        const response = await fetch("/save-profile-memberships", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ changes: profileMembershipChangePayload() })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || `HTTP ${response.status}`);
        }
        profileMemberEdits.clear();
        setSaveStatus(result.message || "Saved");
        if (options.reload !== false) {
          await loadData({ keepStatus: true });
          setSaveStatus(result.message || "Saved");
        }
        return true;
      } catch (error) {
        setSaveStatus(`Save failed: ${error.message}`);
        return false;
      } finally {
        isSavingProfileMemberships = false;
        updateSaveControls();
      }
    }

    async function saveProfileOverrideChanges(options = {}) {
      if (isSavingProfileOverrides) return false;
      if (!profileOverrideChangeCount()) return true;
      isSavingProfileOverrides = true;
      updateSaveControls();
      setSaveStatus("Saving...");
      try {
        const response = await fetch("/save-profile-overrides", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ changes: profileOverrideChangePayload() })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || `HTTP ${response.status}`);
        }
        profileOverrideEdits = [];
        profileOverrideRemoveEdits.clear();
        setSaveStatus(result.message || "Saved");
        if (options.reload !== false) {
          await loadData({ keepStatus: true });
          setSaveStatus(result.message || "Saved");
        }
        return true;
      } catch (error) {
        setSaveStatus(`Save failed: ${error.message}`);
        return false;
      } finally {
        isSavingProfileOverrides = false;
        updateSaveControls();
      }
    }

    function formatBuildElapsed(seconds) {
      const totalSeconds = Math.max(0, Math.floor(Number(seconds) || 0));
      const minutes = Math.floor(totalSeconds / 60);
      const rest = totalSeconds % 60;
      const hours = Math.floor(minutes / 60);
      const displayMinutes = minutes % 60;
      if (hours) return `${hours}:${String(displayMinutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
      return `${displayMinutes}:${String(rest).padStart(2, "0")}`;
    }

    function setBuildOutputVisible(visible) {
      els.buildOutputPanel.hidden = !visible;
    }

    function setBuildOutput(text, options = {}) {
      const output = text || "";
      els.buildOutput.textContent = output;
      if (options.show && output && !buildOutputManuallyHidden) {
        setBuildOutputVisible(true);
        els.buildOutput.scrollTop = els.buildOutput.scrollHeight;
      } else if (!output && !isBuilding) {
        setBuildOutputVisible(false);
      }
    }

    function buildStatusLine(status) {
      const elapsed = status.elapsedLabel || formatBuildElapsed(status.elapsed);
      const latest = (status.latestLine || "").trim();
      if (status.running) {
        return latest ? `${elapsed} ${latest}` : `${elapsed} Starting build...`;
      }
      const failure = buildFailureSummary(status);
      if (status.error) {
        return `Build failed: ${failure || status.error}`;
      }
      if (status.ok) {
        if (status.openError) return `Build succeeded, open failed: ${status.openError}`;
        if (status.open?.opened) return `Build succeeded and test.nds opened (${elapsed})`;
        return `Build succeeded (${elapsed})`;
      }
      if (status.code !== null && status.code !== undefined) {
        return failure
          ? `Build failed (${status.code}): ${failure} (${elapsed})`
          : `Build failed (${status.code}) after ${elapsed}`;
      }
      return "";
    }

    function buildFailureSummary(status) {
      const output = `${status.error || ""}\n${status.output || ""}\n${status.latestLine || ""}`.trim();
      if (!output) return "";
      if (output.includes("Cannot connect to the Docker daemon")) {
        return "Docker daemon is not running";
      }
      if (output.includes("Exec format error")) {
        return "Build script could not be executed directly";
      }
      if (/permission denied/i.test(output)) {
        return "Permission denied while running the build";
      }
      if (/no such file or directory/i.test(output)) {
        return "Build command or one of its files was not found";
      }
      const noisy = new Set([
        "See 'docker run --help'.",
      ]);
      const lines = output
        .replace(/\r/g, "\n")
        .split("\n")
        .map(line => line.trim())
        .filter(Boolean)
        .filter(line => !noisy.has(line));
      const important = [...lines].reverse().find(line =>
        /error|failed|cannot|denied|missing|not found|daemon|docker/i.test(line)
      );
      return important || lines[lines.length - 1] || "";
    }

    function applyBuildStatus(status) {
      isBuilding = Boolean(status.running);
      els.buildTimer.textContent = status.elapsedLabel || formatBuildElapsed(status.elapsed);
      const output = status.output || "";
      const shouldShowOutput = autoShowBuildOutput && (isBuilding || output);
      setBuildOutput(output, { show: shouldShowOutput });
      const line = buildStatusLine(status);
      if (line) {
        const kind = isBuilding ? "busy" : (status.ok ? "success" : "error");
        setSaveStatus(line, kind);
      }
      updateSaveControls();
    }

    function stopBuildPolling() {
      if (buildPollTimer) {
        clearTimeout(buildPollTimer);
        buildPollTimer = null;
      }
    }

    async function pollBuildStatus() {
      stopBuildPolling();
      try {
        const response = await fetch(`/build-status?ts=${Date.now()}`);
        const status = await response.json();
        if (!response.ok) {
          throw new Error(status.error || `HTTP ${response.status}`);
        }
        applyBuildStatus(status);
        if (status.running) {
          buildPollTimer = setTimeout(pollBuildStatus, 500);
        }
      } catch (error) {
        isBuilding = false;
        setSaveStatus(`Build status failed: ${error.message}`, "error");
        updateSaveControls();
      }
    }

    async function runBuildAction() {
      if (isBuilding) return;
      isBuilding = true;
      buildOutputManuallyHidden = false;
      updateSaveControls();
      setSaveStatus("0:00 Starting build...", "busy");
      els.buildTimer.textContent = "0:00";
      setBuildOutput("");
      if (autoShowBuildOutput) {
        setBuildOutputVisible(true);
      }
      try {
        const response = await fetch("/build", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ runAfter: runTestNdsAfterBuild })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || `HTTP ${response.status}`);
        }
        applyBuildStatus(result);
        pollBuildStatus();
      } catch (error) {
        isBuilding = false;
        setSaveStatus(`Build failed: ${error.message}`, "error");
        updateSaveControls();
      }
    }

    async function openTestNdsAction() {
      if (isBuilding) return;
      isBuilding = true;
      updateSaveControls();
      setSaveStatus("Opening test.nds...");
      try {
        const response = await fetch("/open-test-nds", { method: "POST" });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || `HTTP ${response.status}`);
        }
        setSaveStatus("Opened test.nds");
      } catch (error) {
        setSaveStatus(`Open failed: ${error.message}`);
      } finally {
        isBuilding = false;
        updateSaveControls();
      }
    }

    function setEncounterSaveStatus(message) {
      setSaveStatus(message);
    }

    function invalidEncounterInputCount() {
      return invalidEncounterInputs.size;
    }

    function invalidSpawnSettingInputCount() {
      return invalidSpawnSettingInputs.size;
    }

    function pendingChangeStatus() {
      const parts = [];
      if (profileEdits.size) {
        parts.push(`${profileEdits.size} profile`);
      }
      if (profileMemberEdits.size) {
        parts.push(`${profileMemberEdits.size} profile member`);
      }
      if (profileOverrideChangeCount()) {
        parts.push(`${profileOverrideChangeCount()} behavior override`);
      }
      if (encounterEdits.size) {
        parts.push(`${encounterEdits.size} route`);
      }
      if (spawnSettingEdits.size) {
        parts.push(`${spawnSettingEdits.size} setting`);
      }
      if (!parts.length) return "";
      const total = profileEdits.size + profileMemberEdits.size + profileOverrideChangeCount() + encounterEdits.size + spawnSettingEdits.size;
      return `${parts.join(" + ")} pending change${total === 1 ? "" : "s"}`;
    }

    function updateGlobalEditStatus() {
      updateSaveControls();
      const invalidCount = invalidProfileComboCount() + invalidEncounterInputCount() + invalidSpawnSettingInputCount();
      if (invalidCount) {
        setSaveStatus(`${invalidCount} invalid value${invalidCount === 1 ? "" : "s"}`);
      } else {
        setSaveStatus(pendingChangeStatus());
      }
    }

    function scheduleGlobalEditStatus() {
      if (globalEditStatusFrame) return;
      globalEditStatusFrame = requestAnimationFrame(() => {
        globalEditStatusFrame = null;
        updateGlobalEditStatus();
      });
    }

    function updateEncounterSaveControls() {
      updateSaveControls();
    }

    function validateSpawnSettingValue(setting, raw) {
      if (setting?.kind === "species") {
        const option = routeSpeciesOption(raw);
        if (!option) return { valid: false, message: "Choose a valid Pokemon" };
        return { valid: true, value: option.symbol, normalized: option.symbol, message: "" };
      }
      const text = String(raw ?? "").trim();
      if (!text) return { valid: false, message: "Value is required" };
      const value = Number(text);
      if (!Number.isInteger(value)) return { valid: false, message: "Use a whole number" };
      if (setting?.kind === "boolean" && value !== 0 && value !== 1) {
        return { valid: false, message: "Use on or off" };
      }
      if (value < Number(setting.min) || value > Number(setting.max)) {
        return { valid: false, message: `Use ${setting.min}-${setting.max}` };
      }
      return { valid: true, value, normalized: String(value), message: "" };
    }

    function markSpawnSettingInvalid(symbol, invalid, input = null) {
      if (invalid) {
        invalidSpawnSettingInputs.add(symbol);
      } else {
        invalidSpawnSettingInputs.delete(symbol);
      }
      if (input) {
        input.classList.toggle("invalid", invalid);
      }
    }

    function commitSpawnSettingValue(symbol, raw, input = null) {
      const setting = spawnSettingsBySymbol.get(symbol);
      if (!setting) return false;
      const validation = validateSpawnSettingValue(setting, raw);
      if (!validation.valid) {
        markSpawnSettingInvalid(symbol, true, input);
        return false;
      }
      markSpawnSettingInvalid(symbol, false, input);
      const key = spawnSettingEditKey(symbol);
      const original = setting.kind === "species" ? (setting.symbolValue || setting.raw) : setting.value;
      if (validation.normalized === String(original)) {
        spawnSettingEdits.delete(key);
      } else {
        spawnSettingEdits.set(key, validation.normalized);
      }
      if (input?.classList?.contains("spawn-setting-species-input")) {
        const option = routeSpeciesOption(validation.normalized);
        if (option) updateSpeciesInputIcon(input, option);
      }
      return true;
    }

    function commitSpawnSettingInput(input) {
      return commitSpawnSettingValue(input.dataset.symbol, input.value, input);
    }

    function commitAllSpawnSettingInputs() {
      let valid = true;
      spawnSettingEdits.forEach((raw, symbol) => {
        const setting = spawnSettingsBySymbol.get(symbol);
        if (!setting || !validateSpawnSettingValue(setting, raw).valid) {
          invalidSpawnSettingInputs.add(symbol);
          valid = false;
        } else {
          invalidSpawnSettingInputs.delete(symbol);
        }
      });
      return valid;
    }

    function updateRouteInputContainerState(container) {
      if (!container) return;
      const changed = Array.from(container.querySelectorAll(".route-input")).some(input =>
        input.classList.contains("spawn-setting-input")
          ? spawnSettingEdits.has(spawnSettingEditKey(input.dataset.symbol))
          : encounterEdits.has(routeEditKey(input.dataset.routeId, input.dataset.path))
      );
      container.classList.toggle("changed", changed);
    }

    function routeFormInputForSpeciesInput(input) {
      const explicitPath = input.dataset.formPath;
      const wrapper = input.closest(".species-input-wrap");
      if (!wrapper) return null;
      if (explicitPath) {
        const explicit = Array.from(wrapper.querySelectorAll(".route-form")).find(item => item.dataset.path === explicitPath);
        if (explicit) return explicit;
      }
      return wrapper.querySelector(".route-form");
    }

    function setEncounterEdit(routeId, path, original, value) {
      if (!path) return;
      const key = routeEditKey(routeId, path);
      if (String(value) === String(original)) {
        encounterEdits.delete(key);
      } else {
        encounterEdits.set(key, String(value));
      }
    }

    function updateSpeciesInputIcon(input, option) {
      const field = input.closest(".route-field") || input.closest("td");
      if (!field || !option) return;
      const iconHost = input.closest(".species-input-wrap") || field.querySelector(".species-input-wrap");
      if (!iconHost) return;
      const existingIcon = iconHost.querySelector(".mon-icon");
      if (existingIcon && existingIcon.dataset.symbol !== option.symbol) {
        if (existingIcon instanceof HTMLImageElement && option.iconUrl) {
          existingIcon.dataset.symbol = option.symbol;
          existingIcon.src = option.iconUrl;
          existingIcon.alt = `${option.name} icon`;
        } else {
          existingIcon.outerHTML = iconTag(option, "mon-icon");
        }
      }
    }

    function syncSpeciesControlDisplayFromInputs(input) {
      const formInput = routeFormInputForSpeciesInput(input);
      const symbol = routePendingValue(input.dataset.routeId, input.dataset.path, input.dataset.original);
      const form = formInput
        ? routePendingValue(formInput.dataset.routeId, formInput.dataset.path, formInput.dataset.original)
        : 0;
      const option = routeDisplaySpecies(symbol, form);
      input.value = routeSpeciesInputValue(option.symbol);
      updateSpeciesInputIcon(input, option);
      return option;
    }

    function commitRouteSpeciesInput(input, normalize = false) {
      const option = routeSpeciesOption(input.value);
      const field = input.closest(".route-field") || input.closest("td");
      if (!option) {
        trackInvalidInput(invalidEncounterInputs, input, true);
        if (field) field.classList.remove("changed");
        return false;
      }
      if (normalize) {
        input.value = routeSpeciesShortSymbol(option.symbol);
      }
      trackInvalidInput(invalidEncounterInputs, input, false);
      const writeSymbol = routeSpeciesWriteSymbol(option);
      const writeForm = routeSpeciesWriteForm(option);
      const formInput = routeFormInputForSpeciesInput(input);
      setEncounterEdit(input.dataset.routeId, input.dataset.path, input.dataset.original, writeSymbol);
      if (formInput) {
        formInput.value = writeForm;
        setEncounterEdit(formInput.dataset.routeId, formInput.dataset.path, formInput.dataset.original, writeForm);
      }
      syncPendingRouteId(input.dataset.routeId);
      if (field) {
        updateRouteInputContainerState(field);
        updateSpeciesInputIcon(input, option);
      }
      scheduleRouteMarkerUpdate(input.dataset.routeId);
      return true;
    }

    function commitRouteNumberInput(input) {
      if (String(input.value).trim() === "") {
        trackInvalidInput(invalidEncounterInputs, input, true);
        const emptyField = input.closest(".route-field") || input.closest("td");
        if (emptyField) emptyField.classList.remove("changed");
        return false;
      }
      const value = Number(input.value);
      const field = input.closest(".route-field") || input.closest("td");
      const valid = Number.isInteger(value) && value >= Number(input.min) && value <= Number(input.max);
      if (!valid) {
        trackInvalidInput(invalidEncounterInputs, input, true);
        if (field) field.classList.remove("changed");
        return false;
      }
      trackInvalidInput(invalidEncounterInputs, input, false);
      const normalized = String(value);
      const key = routeEditKey(input.dataset.routeId, input.dataset.path);
      if (normalized === input.dataset.original) {
        encounterEdits.delete(key);
      } else {
        encounterEdits.set(key, normalized);
      }
      syncPendingRouteId(input.dataset.routeId);
      if (input.classList.contains("route-form")) {
        const wrapper = input.closest(".species-input-wrap");
        const speciesInput = wrapper ? wrapper.querySelector(".route-species-combo") : null;
        if (speciesInput) {
          syncSpeciesControlDisplayFromInputs(speciesInput);
        }
      }
      updateRouteInputContainerState(field);
      scheduleRouteMarkerUpdate(input.dataset.routeId);
      return true;
    }

    function commitRouteInput(input, normalize = false) {
      if (input.classList.contains("route-species-combo")) {
        return commitRouteSpeciesInput(input, normalize);
      }
      if (input.classList.contains("route-number")) {
        return commitRouteNumberInput(input);
      }
      return true;
    }

    function commitAllRouteInputs(normalize = false) {
      return [
        ...Array.from(els.routeDetailHead.querySelectorAll(".route-input:not(.spawn-setting-input)")),
        ...Array.from(els.routeEditor.querySelectorAll(".route-input:not(.spawn-setting-input)")),
      ]
        .map(input => commitRouteInput(input, normalize))
        .every(Boolean);
    }

    function updateEncounterEditStatus(renderHead = true) {
      if (renderHead) {
        renderRouteDetailHead();
      }
      updateGlobalEditStatus();
    }

    function scheduleEncounterEditStatus(renderHead = true) {
      routeEditStatusNeedsHeadRender = routeEditStatusNeedsHeadRender || renderHead;
      if (routeEditStatusFrame) return;
      routeEditStatusFrame = requestAnimationFrame(() => {
        routeEditStatusFrame = null;
        const renderScheduledHead = routeEditStatusNeedsHeadRender;
        routeEditStatusNeedsHeadRender = false;
        updateEncounterEditStatus(renderScheduledHead);
      });
    }

    async function saveEncounterChanges(options = {}) {
      if (isSavingEncounters) return false;
      if (!encounterEdits.size) return true;
      if (!commitAllRouteInputs(true)) {
        updateEncounterEditStatus();
        return false;
      }
      isSavingEncounters = true;
      updateEncounterSaveControls();
      setEncounterSaveStatus("Saving...");
      try {
        const response = await fetch("/save-encounters", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ changes: routeChangePayload() })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || `HTTP ${response.status}`);
        }
        encounterEdits.clear();
        pendingRouteIds.clear();
        setEncounterSaveStatus(result.message || "Saved");
        if (options.reload !== false) {
          await loadData({ keepStatus: true });
          setEncounterSaveStatus(result.message || "Saved");
        }
        return true;
      } catch (error) {
        setEncounterSaveStatus(`Save failed: ${error.message}`);
        return false;
      } finally {
        isSavingEncounters = false;
        updateEncounterSaveControls();
      }
    }

    async function saveSpawnSettingChanges(options = {}) {
      if (isSavingSpawnSettings) return false;
      if (!spawnSettingEdits.size) return true;
      if (!commitAllSpawnSettingInputs()) {
        updateGlobalEditStatus();
        return false;
      }
      isSavingSpawnSettings = true;
      updateSaveControls();
      setSaveStatus("Saving...");
      try {
        const response = await fetch("/save-spawn-settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ changes: spawnSettingChangePayload() })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || `HTTP ${response.status}`);
        }
        spawnSettingEdits.clear();
        setSaveStatus(result.message || "Saved");
        if (options.reload !== false) {
          await loadData({ keepStatus: true });
          setSaveStatus(result.message || "Saved");
        }
        return true;
      } catch (error) {
        setSaveStatus(`Save failed: ${error.message}`);
        return false;
      } finally {
        isSavingSpawnSettings = false;
        updateSaveControls();
      }
    }

    async function saveAllChanges() {
      if (isSavingProfiles || isSavingProfileMemberships || isSavingProfileOverrides || isSavingEncounters || isSavingSpawnSettings || isManagingProfiles || isBuilding) return false;
      const profilesEditable = appData?.profilesAvailable !== false;
      if (!(profilesEditable && (profileEdits.size || profileMemberEdits.size || profileOverrideChangeCount())) && !encounterEdits.size && !spawnSettingEdits.size) return true;
      const saveProfiles = profilesEditable && profileEdits.size > 0;
      const saveProfileMembers = profilesEditable && profileMemberEdits.size > 0;
      const saveProfileOverrides = profilesEditable && profileOverrideChangeCount() > 0;
      const saveEncounters = encounterEdits.size > 0;
      const saveSpawnSettings = spawnSettingEdits.size > 0;
      let saved = true;
      if (saveProfiles) {
        saved = await saveProfileChanges({ reload: false });
      }
      if (saved && saveProfileMembers) {
        saved = await saveProfileMembershipChanges({ reload: false });
      }
      if (saved && saveProfileOverrides) {
        saved = await saveProfileOverrideChanges({ reload: false });
      }
      if (saved && saveEncounters) {
        saved = await saveEncounterChanges({ reload: false });
      }
      if (saved && saveSpawnSettings) {
        saved = await saveSpawnSettingChanges({ reload: false });
      }
      if (saved && !profileEdits.size && !profileMemberEdits.size && !profileOverrideChangeCount() && !encounterEdits.size && !spawnSettingEdits.size) {
        await loadData({ keepStatus: true });
        const savedParts = [
          saveProfiles ? "profile" : "",
          saveProfileMembers ? "profile member" : "",
          saveProfileOverrides ? "behavior override" : "",
          saveEncounters ? "route" : "",
          saveSpawnSettings ? "spawn setting" : "",
        ].filter(Boolean);
        setSaveStatus(savedParts.length > 1 ? `Saved ${savedParts.join(" and ")} changes` : "Saved");
      }
      return saved;
    }

    function resetAllEdits() {
      profileEdits.clear();
      profileMemberEdits.clear();
      profileOverrideEdits = [];
      profileOverrideRemoveEdits.clear();
      encounterEdits.clear();
      spawnSettingEdits.clear();
      pendingRouteIds.clear();
      invalidProfileInputs.clear();
      invalidEncounterInputs.clear();
      invalidSpawnSettingInputs.clear();
      closeSpawnSettingDialog();
      setSaveStatus("");
      setBuildOutput("");
      markProfilePanelsDirty("profiles", "selected", "rules");
      renderActiveWorkspace();
      updateSaveControls();
    }

    function renderDetailHead() {
      if (appData && !appData.profilesAvailable) {
        els.detailHead.innerHTML = `
          <div>
            <h2>Profiles unavailable</h2>
            <div class="meta">Route encounters are still available. ${esc(appData.profileError?.message || "")}</div>
          </div>
        `;
        return;
      }
      const item = currentProfileClass();
      if (!item) {
        els.detailHead.innerHTML = "";
        return;
      }
      const assigned = profileAssignmentsForClass(item.index);
      els.detailHead.innerHTML = `
        <div class="profile-detail-head">
          <div class="profile-detail-top">
            <div class="profile-detail-title">
              ${profileClassBadge(item)}
              <div>
                <h2>${esc(item.name)}</h2>
                <div class="meta">
                  <span>${esc(profileComboRawDisplay(item.symbol))}</span>
                  <span>${esc(assigned.length)} Pokemon</span>
                  ${profileClassChanged(item) ? `<span>edited</span>` : ""}
                </div>
              </div>
            </div>
            <div class="profile-detail-tools">
              ${profileManagementActions(item)}
              ${profileCoreChips(item)}
              <div class="chip">${esc(profileClassChanged(item) ? "Edited" : "Source")}</div>
            </div>
          </div>
          <div class="profile-detail-overview" title="${esc(assigned.length)} Pokemon use this profile">
            ${profileIconStrip(assigned, item.index === 0 ? 48 : 96, item)}
          </div>
        </div>
      `;
      updateProfileIconSelection();
    }

    function renderProfiles() {
      invalidProfileInputs.clear();
      if (appData && !appData.profilesAvailable) {
        els.profilesTab.innerHTML = profileUnavailableMessage();
        updateSaveControls();
        return;
      }
      const item = currentProfileClass();
      if (!item) {
        els.profilesTab.innerHTML = `<div class="empty">No profile selected</div>`;
        return;
      }
      const assigned = profileAssignmentsForClass(item.index);
      els.profilesTab.innerHTML = `
        ${profileDatalistsHtml}
        <div class="profile-focus">
          <article class="card" data-class-index="${esc(item.index)}">
            <div class="card-head profile-focus-head">
              <div class="profile-focus-title" title="${esc(profileComboRawDisplay(item.symbol))}">
                ${profileClassBadge(item)}
                <span>${esc(item.name)}</span>
              </div>
              <div class="profile-detail-tools">
                ${profileManagementActions(item)}
                ${profileCoreChips(item)}
                <span class="chip">${esc(profileClassChanged(item) ? "Edited" : "Source")}</span>
              </div>
            </div>
            <div class="profile-architecture-grid">${profileEditFieldGroups(item)}</div>
          </article>
          <div class="profile-resolver-grid">
            <article class="card profile-member-card">
              <div class="card-head">
                <div class="card-title">Applied Pokemon</div>
                ${profileAddControl(item)}
                <span class="chip neutral">${esc(assigned.length)} Pokemon</span>
              </div>
              ${profileBulkAssignControl(item)}
              ${profileMemberStrip(assigned, item)}
            </article>
            <article class="card profile-resolver-card">
              <div class="card-head">
                <div class="card-title">Resolver</div>
                <span class="chip neutral">${esc(item.classRuleCount || 0)} rules</span>
              </div>
              <div class="primitive-grid">${profilePrimitiveGroups(item)}</div>
              <div class="profile-rule-values">${profileRuleList(item)}</div>
            </article>
          </div>
        </div>
      `;
      updateProfileIconSelection();
      updateSaveControls();
    }

    function renderSelected() {
      if (appData && !appData.profilesAvailable) {
        els.selectedTab.innerHTML = profileUnavailableMessage();
        return;
      }
      const item = currentAssignment();
      if (!item) {
        els.selectedTab.innerHTML = `<div class="empty">No Pokemon selected</div>`;
        return;
      }
      const ruleSteps = [
        ...item.classRuleHits.map(rule => ({
          label: `Class rule #${rule.order}`,
          right: rule.className,
          changes: [rule.summary]
        })),
        ...(item.maxSpeedOverrideHits || item.variableOverrideHits || []).map(rule => ({
          label: `Behavior override #${rule.order}`,
          right: rule.fields.join(", "),
          changes: [rule.summary]
        }))
      ];
      const layers = item.layers.map(layer => `
        <div class="step">
          <div class="step-title">
            <span>${esc(layer.label)}</span>
            ${layer.mask ? `<span class="muted">${esc(layer.mask.labels.join(", ") || "No fields")}</span>` : ""}
          </div>
          <div class="changes">
            ${(layer.changes || []).length ? layer.changes.map(change => `
              <span class="change">${esc(change.label)}: ${esc(fieldValue(change.before))} -> ${esc(fieldValue(change.after))}</span>
            `).join("") : `<span class="change">No field changes</span>`}
          </div>
        </div>
      `).join("");
      els.selectedTab.innerHTML = `
        <div class="rules" style="margin-bottom:12px">
          <article class="card">
            <div class="card-head"><div class="card-title">Resolved Profile</div><span class="chip">${esc(item.profileId.label)}</span></div>
            <div class="field-grid">${profileFields(item.profile)}</div>
          </article>
          <article class="card">
            <div class="card-head"><div class="card-title">Resolved Primitives</div><span class="chip neutral">Runtime</span></div>
            <div class="primitive-grid">${profilePrimitiveGroups(item)}</div>
          </article>
          <div class="rule-list">
            ${ruleSteps.length ? ruleSteps.map(step => `
              <div class="rule">
                <div class="rule-top"><span>${esc(step.label)}</span><span class="muted">${esc(step.right)}</span></div>
                <div>${esc(step.changes.join(", "))}</div>
              </div>
            `).join("") : `<div class="rule"><div class="muted">Default class only</div></div>`}
          </div>
        </div>
        <div class="timeline">${layers}</div>
      `;
    }

    function renderRules() {
      if (!appData) {
        els.rulesTab.innerHTML = `<div class="empty">Loading behavior profiles...</div>`;
        return;
      }
      if (!appData.profilesAvailable) {
        els.rulesTab.innerHTML = profileUnavailableMessage();
        return;
      }
      const overrideRules = appData.variableOverrides || appData.maxSpeedOverrides || [];
      els.rulesTab.innerHTML = `
        <div class="rules">
          <section>
            <div class="pane-head" style="margin:-12px -12px 10px"><div class="pane-title">Class Rules</div><div class="count">${esc(appData.classRules.length)}</div></div>
            <div class="rule-list">
              ${groupedClassRules(appData.classRules).map(classRuleGroupHtml).join("")}
            </div>
          </section>
          <section class="behavior-override-section">
            <div class="pane-head" style="margin:-12px -12px 10px"><div class="pane-title">Specific Overrides</div><div class="count">${esc(Math.max(0, overrideRules.length - profileOverrideRemoveEdits.size) + profileOverrideEdits.length)}</div></div>
            ${profileOverrideBuilderHtml()}
            ${profileOverridePendingHtml()}
            <div class="rule-list">
              ${overrideRules.map(profileOverrideRuleHtml).join("") || `<div class="rule"><div class="muted">No specific behavior overrides</div></div>`}
            </div>
          </section>
        </div>
      `;
      updateProfileIconSelection();
    }

    function renderTabs() {
      document.querySelectorAll(".tab").forEach(tab => {
        tab.classList.toggle("active", tab.dataset.tab === activeTab);
      });
      document.querySelectorAll(".tab-panel").forEach(panel => panel.classList.remove("active"));
      document.getElementById(`${activeTab}Tab`).classList.add("active");
    }

    function markProfilePanelsDirty(...panels) {
      panels.forEach(panel => dirtyProfilePanels.add(panel));
    }

    function renderActiveProfilePanel(force = false) {
      if (force || dirtyProfilePanels.has(activeTab) || !renderedProfilePanels.has(activeTab)) {
        if (activeTab === "profiles") {
          renderProfiles();
        } else if (activeTab === "selected") {
          renderSelected();
        } else if (activeTab === "rules") {
          renderRules();
        }
        dirtyProfilePanels.delete(activeTab);
        renderedProfilePanels.add(activeTab);
      }
    }

    function renderProfilesWorkspace() {
      renderSpeciesList();
      renderDetailHead();
      renderTabs();
      renderActiveProfilePanel();
    }

    function renderActiveWorkspace() {
      if (activeView === "profiles") {
        renderProfilesWorkspace();
      } else {
        renderEncounters();
      }
    }

    function render() {
      renderWorkspaceTabs();
      renderActiveWorkspace();
    }

    function renderFilterResults() {
      visibleSpeciesLimit = LIST_PAGE_SIZE;
      renderSpeciesList();
      markProfilePanelsDirty("profiles", "selected");
      renderDetailHead();
      renderActiveProfilePanel();
    }

    function scheduleFilterRender() {
      if (filterRenderFrame) {
        cancelAnimationFrame(filterRenderFrame);
      }
      filterRenderFrame = requestAnimationFrame(() => {
        filterRenderFrame = null;
        renderFilterResults();
      });
    }

    function renderRouteFilterResults() {
      if (!appData?.routes) return;
      const selectedChanged = applyRouteListFilters();
      renderRouteDetailHead();
      if (selectedChanged) {
        renderRouteEditor();
      }
      syncRouteEditorSearchHighlights();
    }

    function scheduleRouteFilterRender() {
      if (routeFilterRenderFrame) {
        cancelAnimationFrame(routeFilterRenderFrame);
      }
      routeFilterRenderFrame = requestAnimationFrame(() => {
        routeFilterRenderFrame = null;
        renderRouteFilterResults();
      });
    }

    async function loadData(options = {}) {
      const generation = dataLoadGeneration + 1;
      dataLoadGeneration = generation;
      if (dataLoadAbortController) {
        dataLoadAbortController.abort();
      }
      const controller = new AbortController();
      dataLoadAbortController = controller;
      els.refresh.disabled = true;
      try {
        const response = await fetch("/data.json", { signal: controller.signal });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        if (generation !== dataLoadGeneration) return false;
        appData = normalizeAppData(data);
        prepareData();
        renderClassFilter();
        hasLoadedData = true;
        if (!selectedSymbol && appData.assignments.length) {
          selectedSymbol = appData.assignments[0].species.symbol;
        }
        if (selectedSymbol && assignmentsBySymbol.has(selectedSymbol)) {
          selectedClassIndex = assignmentsBySymbol.get(selectedSymbol).behaviorClass.value;
        }
        if (selectedClassIndex === null && appData.classes.length) {
          selectedClassIndex = appData.classes[0].index;
        }
        if (selectedRouteId === null && appData.routes.length) {
          selectedRouteId = appData.routes[0].id;
        }
        visibleSpeciesLimit = LIST_PAGE_SIZE;
        render();
        if (!options.keepStatus) {
          setEncounterSaveStatus("");
        }
        return true;
      } catch (error) {
        if (error.name === "AbortError") return false;
        setSaveStatus(`Load failed: ${error.message}`, "error");
        throw error;
      } finally {
        if (generation === dataLoadGeneration) {
          dataLoadAbortController = null;
          els.refresh.disabled = false;
        }
      }
    }

    document.querySelectorAll(".workspace-tab").forEach(tab => {
      tab.addEventListener("click", () => {
        activeView = tab.dataset.view;
        localStorage.setItem("owWorkspaceView", activeView);
        renderWorkspaceTabs();
        if (hasLoadedData) {
          renderActiveWorkspace();
        }
      });
    });
    els.search.addEventListener("input", scheduleFilterRender);
    els.classFilter.addEventListener("change", renderFilterResults);
    els.refresh.addEventListener("click", () => {
      loadData().catch(() => {});
      loadShinyCounter().catch(() => {});
    });
    els.refreshShinyCounter.addEventListener("click", () => {
      loadShinyCounter({ report: true }).catch(() => {});
    });
    els.resetShinyCounter.addEventListener("click", () => {
      setShinyCounter(0);
    });
    els.maxShinyCounter.addEventListener("click", () => {
      setShinyCounter(8191);
    });
    els.saveAllChanges.addEventListener("click", () => {
      saveAllChanges().then(saved => {
        if (saved && buildAfterSave) {
          runBuildAction();
        }
      });
    });
    els.buildRom.addEventListener("click", () => {
      runBuildAction();
    });
    els.openTestNds.addEventListener("click", () => {
      openTestNdsAction();
    });
    els.resetAllEdits.addEventListener("click", resetAllEdits);
    document.addEventListener("click", event => {
      const button = event.target.closest("[data-action='create-profile'], [data-action='rename-profile'], [data-action='delete-profile']");
      if (!button || button.disabled) return;
      if (!button.closest("#detailHead, #profilesTab")) return;
      event.preventDefault();
      event.stopPropagation();
      if (button.dataset.action === "create-profile") {
        createProfileFromPrompt();
      } else if (button.dataset.action === "rename-profile") {
        renameProfileFromPrompt(button.dataset.classIndex);
      } else if (button.dataset.action === "delete-profile") {
        deleteProfileWithConfirmation(button.dataset.classIndex);
      }
    });
    els.buildAfterSave.addEventListener("change", () => {
      buildAfterSave = els.buildAfterSave.checked;
      localStorage.setItem("owProfileBuildAfterSave", buildAfterSave ? "1" : "0");
    });
    els.runTestAfterBuild.addEventListener("change", () => {
      runTestNdsAfterBuild = els.runTestAfterBuild.checked;
      localStorage.setItem("owProfileRunTestAfterBuild", runTestNdsAfterBuild ? "1" : "0");
    });
    els.showBuildOutput.addEventListener("change", () => {
      autoShowBuildOutput = els.showBuildOutput.checked;
      localStorage.setItem("owProfileAutoShowBuildOutput", autoShowBuildOutput ? "1" : "0");
      if (autoShowBuildOutput && els.buildOutput.textContent) {
        buildOutputManuallyHidden = false;
        setBuildOutputVisible(true);
        els.buildOutput.scrollTop = els.buildOutput.scrollHeight;
      } else if (!autoShowBuildOutput) {
        buildOutputManuallyHidden = true;
        setBuildOutputVisible(false);
      }
    });
    els.closeBuildOutput.addEventListener("click", () => {
      buildOutputManuallyHidden = true;
      setBuildOutputVisible(false);
    });
    els.routeSearch.addEventListener("input", scheduleRouteFilterRender);
    els.routeSpawnTypeFilters.addEventListener("click", event => {
      const button = event.target.closest("[data-spawn-filter]");
      if (!button) return;
      const key = button.dataset.spawnFilter;
      if (!ROUTE_SPAWN_FILTER_KEYS.has(key)) return;
      const active = !routeSpawnTypeFilters.has(key);
      if (routeSpawnTypeFilters.has(key)) {
        routeSpawnTypeFilters.delete(key);
      } else {
        routeSpawnTypeFilters.add(key);
      }
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
      saveRouteSpawnTypeFilters();
      setRouteGroupVisibility(key, active);
      scheduleRouteFilterRender();
    });
    els.routeList.addEventListener("click", event => {
      const swapButton = event.target.closest("[data-route-swap]");
      if (swapButton) {
        event.preventDefault();
        event.stopPropagation();
        openRouteSpeciesSwap(swapButton.dataset.routeId, swapButton.dataset.speciesSymbol, routeSwapContextFromButton(swapButton));
        return;
      }
      const row = event.target.closest(".route-row");
      if (row) {
        selectRoute(row.dataset.routeId);
      }
    });
    els.routeList.addEventListener("keydown", event => {
      const row = event.target.closest(".route-row");
      if (!row || event.target.closest("[data-route-swap]")) return;
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectRoute(row.dataset.routeId);
      }
    });
    els.routeDetailHead.addEventListener("click", event => {
      const swapButton = event.target.closest("[data-route-swap]");
      if (!swapButton) return;
      event.preventDefault();
      event.stopPropagation();
      openRouteSpeciesSwap(swapButton.dataset.routeId, swapButton.dataset.speciesSymbol, routeSwapContextFromButton(swapButton));
    });
    els.detailHead.addEventListener("click", event => {
      const quickAdd = event.target.closest("[data-action='quick-add-profile']");
      if (quickAdd) {
        event.preventDefault();
        event.stopPropagation();
        openProfileAddMenu(quickAdd.dataset.classIndex, quickAdd.getBoundingClientRect());
        return;
      }
      const button = event.target.closest(".profile-icon-button, .profile-member-chip");
      if (!button) return;
      event.preventDefault();
      event.stopPropagation();
      selectSpecies(button.dataset.symbol, { tab: "selected" });
    });
    els.routeSwapDialog.addEventListener("click", event => {
      if (event.target === els.routeSwapDialog) {
        closeRouteSpeciesSwap();
        return;
      }
      const action = event.target.closest("[data-route-swap-action]");
      if (!action) return;
      if (action.dataset.routeSwapAction === "cancel") {
        event.preventDefault();
        closeRouteSpeciesSwap();
      }
    });
    els.routeSwapDialog.addEventListener("submit", event => {
      event.preventDefault();
      const action = event.submitter?.dataset?.routeSwapAction || "apply";
      applyRouteSpeciesSwap({ highlightedOnly: action === "apply-highlighted" });
    });
    els.routeSwapDialog.addEventListener("input", event => {
      if (event.target.closest("#routeSwapInput")) {
        setRouteSwapError("");
      }
      const entryInput = event.target.closest(".route-swap-entry-input");
      if (entryInput) {
        setRouteSwapError("");
        updateRouteSwapEntryIcon(entryInput);
      }
      const levelInput = event.target.closest(".route-swap-level-input");
      if (levelInput) {
        setRouteSwapError("");
        levelInput.classList.remove("invalid");
      }
    });
    els.routeSwapDialog.addEventListener("cancel", event => {
      event.preventDefault();
      closeRouteSpeciesSwap();
    });

    els.routeGlobalSettings.addEventListener("click", event => {
      const button = event.target.closest("[data-spawn-setting-symbol]");
      if (!button) return;
      openSpawnSettingDialog(button.dataset.spawnSettingSymbol);
    });

    els.spawnSettingDialog.addEventListener("click", event => {
      if (event.target === els.spawnSettingDialog) {
        closeSpawnSettingDialog();
        return;
      }
      const action = event.target.closest("[data-spawn-setting-action]");
      if (!action) return;
      if (action.dataset.spawnSettingAction === "cancel") {
        event.preventDefault();
        closeSpawnSettingDialog();
      }
    });
    els.spawnSettingDialog.addEventListener("submit", event => {
      event.preventDefault();
      applySpawnSettingDialog();
    });
    els.spawnSettingDialog.addEventListener("input", event => {
      const input = event.target.closest("#spawnSettingDialogInput");
      if (input) {
        markSpawnSettingInvalid(input.dataset.symbol, false, input);
        setSpawnSettingDialogError("");
        scheduleGlobalEditStatus();
        return;
      }
      const speciesInput = event.target.closest("#spawnTestSpeciesInput");
      if (speciesInput) {
        speciesInput.classList.remove("invalid");
        const option = routeSpeciesOption(speciesInput.value);
        if (option) updateSpeciesInputIcon(speciesInput, option);
        setSpawnSettingDialogError("");
        return;
      }
      const testInput = event.target.closest("#spawnTestEnabledInput, #spawnTestLevelInput");
      if (testInput) {
        testInput.classList.remove("invalid");
        setSpawnSettingDialogError("");
      }
    });
    els.spawnSettingDialog.addEventListener("cancel", event => {
      event.preventDefault();
      closeSpawnSettingDialog();
    });

    function handleRouteEditEvent(event, normalize = false, renderHead = true) {
      const input = event.target.closest(".route-input");
      if (!input || input.classList.contains("spawn-setting-input")) return false;
      commitRouteInput(input, normalize);
      scheduleEncounterEditStatus(renderHead);
      return true;
    }

    els.routeDetailHead.addEventListener("input", event => {
      handleRouteEditEvent(event, false, false);
    });
    els.routeDetailHead.addEventListener("change", event => {
      handleRouteEditEvent(event, true, false);
    });
    els.routeDetailHead.addEventListener("focusout", event => {
      handleRouteEditEvent(event, true, false);
    });

    els.routeEditor.addEventListener("input", event => {
      const summaryInput = event.target.closest(".encounter-summary-species-input");
      if (summaryInput) {
        summaryInput.classList.remove("invalid");
        return;
      }
      const settingInput = event.target.closest(".spawn-setting-input");
      if (settingInput) {
        commitSpawnSettingInput(settingInput);
        scheduleGlobalEditStatus();
        return;
      }
      handleRouteEditEvent(event);
    });
    els.routeEditor.addEventListener("change", event => {
      const summaryInput = event.target.closest(".encounter-summary-species-input");
      if (summaryInput) {
        commitEncounterSummarySpeciesInput(summaryInput);
        return;
      }
      const settingInput = event.target.closest(".spawn-setting-input");
      if (settingInput) {
        commitSpawnSettingInput(settingInput);
        scheduleGlobalEditStatus();
        return;
      }
      handleRouteEditEvent(event, true);
    });
    els.routeEditor.addEventListener("focusout", event => {
      const settingInput = event.target.closest(".spawn-setting-input");
      if (settingInput) {
        commitSpawnSettingInput(settingInput);
        scheduleGlobalEditStatus();
        return;
      }
      handleRouteEditEvent(event, true);
    });
    els.routeEditor.addEventListener("focusin", event => {
      const summaryInput = event.target.closest(".encounter-summary-species-input");
      if (summaryInput) {
        setTimeout(() => summaryInput.select(), 0);
      }
    });
    els.routeEditor.addEventListener("keydown", event => {
      const summaryInput = event.target.closest(".encounter-summary-species-input");
      if (!summaryInput) return;
      if (event.key === "Enter") {
        event.preventDefault();
        commitEncounterSummarySpeciesInput(summaryInput);
      } else if (event.key === "Escape") {
        event.preventDefault();
        summaryInput.value = routeSpeciesInputValue(summaryInput.dataset.currentSymbol);
        summaryInput.classList.remove("invalid");
        summaryInput.blur();
      }
    });
    els.routeEditor.addEventListener("click", event => {
      if (event.target.closest(".encounter-summary-species-input")) return;
      const swapButton = event.target.closest("[data-route-swap]");
      if (!swapButton) return;
      event.preventDefault();
      event.stopPropagation();
      openRouteSpeciesSwap(swapButton.dataset.routeId, swapButton.dataset.speciesSymbol, routeSwapContextFromButton(swapButton));
    });
    els.speciesList.addEventListener("click", event => {
      const more = event.target.closest("[data-action='show-more']");
      if (more) {
        visibleSpeciesLimit += LIST_PAGE_SIZE;
        renderSpeciesList();
        return;
      }
      const quickAdd = event.target.closest("[data-action='quick-add-profile']");
      if (quickAdd) {
        event.preventDefault();
        event.stopPropagation();
        const previousClassIndex = selectedClassIndex;
        const anchorRect = quickAdd.getBoundingClientRect();
        selectedClassIndex = Number(quickAdd.dataset.classIndex);
        activeTab = "profiles";
        if (!ensureSelectedListRowRendered()) {
          updateSelectedListRow(previousClassIndex);
        }
        markProfilePanelsDirty("profiles");
        renderDetailHead();
        renderTabs();
        renderActiveProfilePanel();
        openProfileAddMenu(quickAdd.dataset.classIndex, anchorRect);
        return;
      }
      const profileButton = event.target.closest(".profile-icon-button");
      if (profileButton) {
        event.preventDefault();
        event.stopPropagation();
        selectSpecies(profileButton.dataset.symbol, { tab: "selected" });
        return;
      }
      const row = event.target.closest(".profile-row");
      if (row) {
        selectProfileClass(row.dataset.classIndex, { tab: "profiles" });
      }
    });
    els.speciesList.addEventListener("keydown", event => {
      const row = event.target.closest(".profile-row");
      if (!row || event.target.closest("button, input, form")) return;
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectProfileClass(row.dataset.classIndex, { tab: "profiles" });
      }
    });
    els.speciesList.addEventListener("submit", event => {
      const form = event.target.closest("[data-profile-add-form]");
      if (!form) return;
      event.preventDefault();
      event.stopPropagation();
      addPokemonToCurrentProfile(form);
    });
    els.speciesList.addEventListener("input", event => {
      const input = event.target.closest(".profile-row-add-input");
      if (!input) return;
      input.classList.remove("invalid");
      setSaveStatus(pendingChangeStatus());
    });
    els.profileAddMenu.addEventListener("click", event => {
      event.stopPropagation();
      const close = event.target.closest("[data-action='close-profile-add-menu']");
      if (close) {
        event.preventDefault();
        closeProfileAddMenu();
      }
    });
    els.profileAddMenu.addEventListener("submit", event => {
      const form = event.target.closest("[data-profile-add-form]");
      if (!form) return;
      event.preventDefault();
      event.stopPropagation();
      addPokemonToCurrentProfile(form);
    });
    els.profileAddMenu.addEventListener("input", event => {
      const input = event.target.closest(".profile-add-input");
      if (!input) return;
      input.classList.remove("invalid");
      setSaveStatus(pendingChangeStatus());
    });
    els.profileComboMenu.addEventListener("mousedown", event => {
      if (event.target.closest(".profile-combo-option")) {
        event.preventDefault();
      }
    });
    els.profileComboMenu.addEventListener("click", event => {
      const option = event.target.closest(".profile-combo-option");
      if (!option) return;
      event.preventDefault();
      chooseProfileComboOption(option.dataset.raw);
    });
    document.addEventListener("click", event => {
      if (els.profileAddMenu.hidden) return;
      if (event.target.closest("#profileAddMenu") || event.target.closest("[data-action='quick-add-profile']")) return;
      closeProfileAddMenu();
    });
    document.addEventListener("click", event => {
      if (els.profileComboMenu.hidden) return;
      if (event.target.closest("#profileComboMenu") || event.target.closest(".profile-combo")) return;
      closeProfileComboMenu();
    });
    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && !els.profileAddMenu.hidden) {
        closeProfileAddMenu();
      }
      if (event.key === "Escape" && !els.profileComboMenu.hidden) {
        closeProfileComboMenu();
      }
    });
    window.addEventListener("resize", () => {
      if (activeProfileComboInput && !els.profileComboMenu.hidden) {
        placeProfileComboMenu(activeProfileComboInput);
      }
    });
    window.addEventListener("scroll", () => {
      if (activeProfileComboInput && !els.profileComboMenu.hidden) {
        placeProfileComboMenu(activeProfileComboInput);
      }
    }, true);
    els.profilesTab.addEventListener("click", event => {
      const removeMemberButton = event.target.closest("[data-action='remove-profile-member']");
      if (removeMemberButton) {
        event.preventDefault();
        event.stopPropagation();
        removePokemonFromProfile(removeMemberButton.dataset.symbol, removeMemberButton.dataset.classIndex);
        return;
      }
      const button = event.target.closest(".profile-icon-button, .profile-member-chip");
      if (button) {
        selectSpecies(button.dataset.symbol, { tab: "selected" });
      }
    });

    function profileClassByIndex(classIndex) {
      return appData.classes.find(row => String(row.index) === String(classIndex)) || null;
    }

    function pendingProfileManagementChangeCount() {
      return profileEdits.size + profileMemberEdits.size + profileOverrideChangeCount() + encounterEdits.size + spawnSettingEdits.size;
    }

    function discardPendingChangesForProfileManagement() {
      const count = pendingProfileManagementChangeCount();
      if (!count) return true;
      const ok = window.confirm(
        `This profile structure change reloads the data and will discard ${count} pending unsaved change${count === 1 ? "" : "s"}. Continue?`
      );
      if (!ok) return false;
      profileEdits.clear();
      profileMemberEdits.clear();
      profileOverrideEdits = [];
      profileOverrideRemoveEdits.clear();
      encounterEdits.clear();
      spawnSettingEdits.clear();
      pendingRouteIds.clear();
      invalidProfileInputs.clear();
      invalidEncounterInputs.clear();
      invalidSpawnSettingInputs.clear();
      closeProfileAddMenu();
      closeSpawnSettingDialog();
      updateSaveControls();
      return true;
    }

    function profilePromptSpeciesList(text) {
      const rawParts = String(text || "")
        .split(/[\n,;]+/)
        .map(part => part.trim())
        .filter(Boolean);
      const pokemon = [];
      const seen = new Set();
      const invalid = [];
      rawParts.forEach(part => {
        const species = profileSpeciesOption(part);
        if (!species) {
          invalid.push(part);
          return;
        }
        if (!seen.has(species.symbol)) {
          seen.add(species.symbol);
          pokemon.push(species);
        }
      });
      return { pokemon, invalid };
    }

    async function manageProfile(payload, options = {}) {
      if (isManagingProfiles) return false;
      if (!discardPendingChangesForProfileManagement()) return false;
      isManagingProfiles = true;
      updateSaveControls();
      setSaveStatus("Saving profile structure...", "busy");
      try {
        const response = await fetch("/manage-profiles", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || `HTTP ${response.status}`);
        }
        const nextClassIndex = result.classIndex;
        const nextSymbol = options.selectedSymbol || null;
        if (nextSymbol) {
          selectedSymbol = nextSymbol;
        } else if (payload.action === "delete") {
          selectedSymbol = null;
        }
        await loadData({ keepStatus: true });
        if (nextClassIndex !== undefined && profileClassByIndex(nextClassIndex)) {
          selectProfileClass(nextClassIndex, { tab: "profiles" });
        }
        if (nextSymbol && assignmentsBySymbol.has(nextSymbol)) {
          selectSpecies(nextSymbol, { tab: "profiles" });
        }
        setSaveStatus(result.message || "Saved", "success");
        return true;
      } catch (error) {
        setSaveStatus(`Profile change failed: ${error.message}`, "error");
        return false;
      } finally {
        isManagingProfiles = false;
        updateSaveControls();
      }
    }

    async function createProfileFromPrompt() {
      const defaultName = selectedSymbol ? `${profileSpeciesBySymbol.get(selectedSymbol)?.name || "Pokemon"} profile` : "";
      const name = window.prompt("New profile name", defaultName);
      if (name === null) return;
      const trimmedName = name.trim();
      if (!trimmedName) {
        setSaveStatus("Profile name is required", "error");
        return;
      }
      const defaultPokemon = selectedSymbol ? (profileSpeciesBySymbol.get(selectedSymbol)?.name || selectedSymbol) : "";
      const pokemonText = window.prompt("Pokemon assigned to the new profile (comma separated)", defaultPokemon);
      if (pokemonText === null) return;
      const { pokemon, invalid } = profilePromptSpeciesList(pokemonText);
      if (invalid.length) {
        setSaveStatus(`Unknown Pokemon: ${invalid.join(", ")}`, "error");
        return;
      }
      if (!pokemon.length) {
        setSaveStatus("Choose at least one Pokemon for the new profile", "error");
        return;
      }
      await manageProfile(
        { action: "create", name: trimmedName, pokemon: pokemon.map(species => species.symbol) },
        { selectedSymbol: pokemon[0]?.symbol }
      );
    }

    async function renameProfileFromPrompt(classIndex) {
      const item = profileClassByIndex(classIndex ?? selectedClassIndex);
      if (!item) return;
      if (item.canRename === false) {
        setSaveStatus("Default profile cannot be renamed", "error");
        return;
      }
      const name = window.prompt(`Rename ${item.name}`, item.name);
      if (name === null) return;
      const trimmedName = name.trim();
      if (!trimmedName) {
        setSaveStatus("Profile name is required", "error");
        return;
      }
      await manageProfile({ action: "rename", classIndex: item.index, name: trimmedName });
    }

    async function deleteProfileWithConfirmation(classIndex) {
      const item = profileClassByIndex(classIndex ?? selectedClassIndex);
      if (!item) return;
      if (profileIsDefaultClass(item.index)) {
        setSaveStatus("Default profile cannot be deleted", "error");
        return;
      }
      if (item.canDelete === false) {
        setSaveStatus(`${item.name} is referenced by runtime code and cannot be deleted safely`, "error");
        return;
      }
      const assigned = profileAssignmentsForClass(item.index);
      const warning = [
        `Delete ${item.name}?`,
        `${assigned.length} Pokemon currently resolve to it and will fall back to Default.`,
        "This rewrites the behavior data source."
      ].join("\n\n");
      if (!window.confirm(warning)) return;
      const typed = window.prompt(`Type ${item.name} to confirm deletion`);
      if (typed !== item.name) {
        setSaveStatus("Delete cancelled");
        return;
      }
      await manageProfile({ action: "delete", classIndex: item.index });
    }

    function closeProfileAddMenu() {
      profileQuickAddClassIndex = null;
      els.profileAddMenu.hidden = true;
      els.profileAddMenu.innerHTML = "";
    }

    function renderProfileAddMenu(item) {
      return `
        <form class="profile-add-menu-form" data-profile-add-form data-profile-add-class="${esc(item.index)}">
          <div class="profile-add-menu-title">
            <span>Add Pokemon to ${esc(item.name)}</span>
            <span class="chip neutral">${esc(profileAssignmentsForClass(item.index).length)} Pokemon</span>
          </div>
          <span class="profile-add-species-wrap">
            ${encounterBadge("plus", "type-test", "Add Pokemon")}
            <input class="profile-add-input" type="text" list="profileSpeciesOptions" placeholder="Pokemon" autocomplete="off" aria-label="Add Pokemon to ${esc(item.name)}">
          </span>
          <div class="profile-add-menu-actions">
            <button class="control" type="button" data-action="close-profile-add-menu">Cancel</button>
            <button class="control primary-action profile-add-button" type="submit" title="Add Pokemon to ${esc(item.name)}">
              ${interfaceIcon("plus")}
              <span>Add</span>
            </button>
          </div>
        </form>
      `;
    }

    function placeProfileAddMenu(anchorRect) {
      const menu = els.profileAddMenu;
      const gap = 6;
      const margin = 8;
      const rect = menu.getBoundingClientRect();
      const sourceRect = anchorRect || {
        left: window.innerWidth / 2 - rect.width / 2,
        right: window.innerWidth / 2 + rect.width / 2,
        top: window.innerHeight / 2,
        bottom: window.innerHeight / 2,
      };
      let left = Math.min(window.innerWidth - rect.width - margin, Math.max(margin, sourceRect.left));
      let top = sourceRect.bottom + gap;
      if (top + rect.height + margin > window.innerHeight) {
        top = sourceRect.top - rect.height - gap;
      }
      top = Math.min(window.innerHeight - rect.height - margin, Math.max(margin, top));
      menu.style.left = `${left}px`;
      menu.style.top = `${top}px`;
    }

    function openProfileAddMenu(classIndex, anchorRect = null) {
      const item = profileClassByIndex(classIndex);
      if (!item) return;
      profileQuickAddClassIndex = String(item.index);
      els.profileAddMenu.innerHTML = renderProfileAddMenu(item);
      els.profileAddMenu.hidden = false;
      placeProfileAddMenu(anchorRect);
      requestAnimationFrame(() => {
        const input = els.profileAddMenu.querySelector(".profile-add-input");
        if (input) input.focus();
      });
    }

    function addPokemonToCurrentProfile(form) {
      const input = form.querySelector(".profile-add-input");
      const targetClassIndex = form.dataset.profileAddClass;
      const item = targetClassIndex !== undefined ? profileClassByIndex(targetClassIndex) : currentProfileClass();
      if (!input || !item) return;
      const species = profileSpeciesOption(input.value);
      if (!species) {
        input.classList.add("invalid");
        setSaveStatus("Choose a valid Pokemon", "error");
        updateSaveControls();
        return;
      }
      input.classList.remove("invalid");
      const currentClass = profilePendingClassValueForSymbol(species.symbol);
      if (String(currentClass) === String(item.index)) {
        input.value = "";
        setSaveStatus(`${species.name} already uses ${item.name}`);
        updateSaveControls();
        return;
      }
      const originalClass = assignmentsBySymbol.get(species.symbol)?.behaviorClass?.value;
      if (String(originalClass) === String(item.index)) {
        profileMemberEdits.delete(species.symbol);
      } else {
        profileMemberEdits.set(species.symbol, String(item.index));
      }
      selectedSymbol = species.symbol;
      selectedClassIndex = item.index;
      closeProfileAddMenu();
      input.value = "";
      appData.classes.forEach(row => {
        row.searchText = profileClassSearchText(row, profileAssignmentsForClass(row.index));
      });
      markProfilePanelsDirty("profiles", "selected");
      renderSpeciesList();
      renderDetailHead();
      renderActiveProfilePanel(true);
      updateSaveControls();
      setSaveStatus(`Added ${species.name} to ${item.name}`, "warning");
    }

    function refreshAllProfileClassSearchText() {
      appData.classes.forEach(row => {
        row.searchText = profileClassSearchText(row, profileAssignmentsForClass(row.index));
      });
    }

    function removePokemonFromProfile(symbol, classIndex) {
      const item = profileClassByIndex(classIndex);
      const assignment = assignmentsBySymbol.get(symbol);
      const species = assignment?.species || profileSpeciesBySymbol.get(symbol);
      if (!item || !assignment || !species) {
        setSaveStatus("Pokemon could not be removed from this profile", "error");
        updateSaveControls();
        return;
      }
      if (profileIsDefaultClass(item.index)) {
        setSaveStatus("Default profile Pokemon cannot be removed");
        updateSaveControls();
        return;
      }
      const pendingClass = profilePendingClassValueForSymbol(symbol);
      if (String(pendingClass) !== String(item.index)) {
        setSaveStatus(`${species.name} no longer uses ${item.name}`);
        updateSaveControls();
        return;
      }
      const originalClass = assignment.behaviorClass?.value;
      const defaultIndex = profileDefaultClassIndex();
      if (profileMemberEdits.has(symbol) && String(originalClass) !== String(item.index)) {
        profileMemberEdits.delete(symbol);
        setSaveStatus(`Undid moving ${species.name} to ${item.name}`, "warning");
      } else if (String(originalClass) === String(defaultIndex)) {
        profileMemberEdits.delete(symbol);
        setSaveStatus(`${species.name} already resolves to the default profile`);
      } else {
        profileMemberEdits.set(symbol, String(defaultIndex));
        setSaveStatus(`Removed ${species.name} from ${item.name}`, "warning");
      }
      selectedClassIndex = item.index;
      if (selectedSymbol === symbol) {
        selectedSymbol = null;
      }
      refreshAllProfileClassSearchText();
      markProfilePanelsDirty("profiles", "selected");
      renderSpeciesList();
      renderDetailHead();
      renderActiveProfilePanel(true);
      updateSaveControls();
    }

    function assignPokemonTypeToProfile(classIndex, typeSymbol) {
      const item = profileClassByIndex(classIndex);
      const type = profileTypeOption(typeSymbol);
      if (!item || !type) {
        setSaveStatus("Choose a valid Pokemon type", "error");
        updateSaveControls();
        return;
      }
      const candidates = profileBulkAssignableSpecies(item, type.symbol);
      if (!candidates.length) {
        setSaveStatus(`All ${type.name} Pokemon already use ${item.name}`);
        updateSaveControls();
        return;
      }
      candidates.forEach(species => {
        const originalClass = assignmentsBySymbol.get(species.symbol)?.behaviorClass?.value;
        if (String(originalClass) === String(item.index)) {
          profileMemberEdits.delete(species.symbol);
        } else {
          profileMemberEdits.set(species.symbol, String(item.index));
        }
      });
      selectedClassIndex = item.index;
      if (!selectedSymbol || candidates.some(species => species.symbol === selectedSymbol)) {
        selectedSymbol = candidates[0].symbol;
      }
      appData.classes.forEach(row => {
        row.searchText = profileClassSearchText(row, profileAssignmentsForClass(row.index));
      });
      markProfilePanelsDirty("profiles", "selected");
      renderSpeciesList();
      renderDetailHead();
      renderActiveProfilePanel(true);
      updateSaveControls();
      setSaveStatus(`Assigned ${candidates.length} ${type.name} Pokemon to ${item.name}`, "warning");
    }

    els.profilesTab.addEventListener("submit", event => {
      const form = event.target.closest("[data-profile-add-form]");
      if (!form) return;
      event.preventDefault();
      addPokemonToCurrentProfile(form);
    });

    els.profilesTab.addEventListener("input", event => {
      const input = event.target.closest(".profile-add-input");
      if (!input) return;
      input.classList.remove("invalid");
      setSaveStatus(pendingChangeStatus());
    });

    els.profilesTab.addEventListener("change", event => {
      const select = event.target.closest("[data-profile-bulk-type]");
      if (!select) return;
      profileBulkType = select.value;
      localStorage.setItem("owProfileBulkType", profileBulkType);
      renderActiveProfilePanel(true);
      setSaveStatus(pendingChangeStatus());
    });

    els.profilesTab.addEventListener("click", event => {
      const button = event.target.closest("[data-action='bulk-assign-type']");
      if (!button) return;
      event.preventDefault();
      assignPokemonTypeToProfile(button.dataset.classIndex, profileValidBulkType());
    });

    els.rulesTab.addEventListener("change", event => {
      const targetKindSelect = event.target.closest("[data-profile-override-target-kind]");
      const targetSelect = event.target.closest("[data-profile-override-target]");
      const fieldSelect = event.target.closest("[data-profile-override-field]");
      const valueSelect = event.target.closest("[data-profile-override-value]");
      if (!targetKindSelect && !targetSelect && !fieldSelect && !valueSelect) return;
      if (targetKindSelect) {
        profileOverrideDraftTargetKind = targetKindSelect.value;
      }
      if (targetSelect) {
        if (profileValidOverrideTargetKind() === "spawnPool") {
          profileOverrideDraftSpawnPool = targetSelect.value;
        } else {
          profileOverrideDraftType = targetSelect.value;
        }
      }
      if (fieldSelect) {
        profileOverrideDraftField = fieldSelect.value;
        profileOverrideDraftRaw = profileValidOverrideRaw(profileOverrideDraftField);
      }
      if (valueSelect) {
        profileOverrideDraftRaw = valueSelect.value;
      }
      persistProfileOverrideDraft();
      markProfilePanelsDirty("rules");
      renderActiveProfilePanel(true);
      setSaveStatus(pendingChangeStatus());
    });

    els.rulesTab.addEventListener("click", event => {
      const addButton = event.target.closest("[data-action='add-profile-override']");
      if (addButton) {
        event.preventDefault();
        addProfileOverrideDraft();
        return;
      }
      const removeButton = event.target.closest("[data-action='remove-profile-override']");
      if (removeButton) {
        event.preventDefault();
        removeProfileOverrideDraft(removeButton.dataset.overrideId);
        return;
      }
      const removeExistingButton = event.target.closest("[data-action='toggle-remove-profile-override']");
      if (removeExistingButton) {
        event.preventDefault();
        toggleProfileOverrideRemoval(removeExistingButton.dataset.overrideOrder);
      }
    });

    function refreshProfileClassSearchText(classIndex) {
      const item = appData.classes.find(row => String(row.index) === String(classIndex));
      if (!item) return;
      item.searchText = profileClassSearchText(item, profileAssignmentsForClass(item.index));
    }

    function updateProfileComboStatus(input = null, refreshOverview = false) {
      if (input?.dataset?.classIndex) {
        refreshProfileClassSearchText(input.dataset.classIndex);
        const item = appData.classes.find(row => String(row.index) === String(input.dataset.classIndex));
        const row = visibleListRow(input.dataset.classIndex);
        if (item && row) {
          row.classList.toggle("changed", profileClassChanged(item));
          const sub = row.querySelector(".profile-row-sub");
          if (sub) sub.textContent = `${profilePendingDisplay(item, "profileId")} · ${profilePendingDisplay(item, "spawnState")}`;
        }
      }
      if (refreshOverview) {
        renderDetailHead();
      }
      scheduleGlobalEditStatus();
    }

    function commitAlertCloseRangeSelect(select) {
      const originalRaw = select.dataset.original;
      const currentRaw = pendingProfileValue(select.dataset.classIndex, "alertRange", originalRaw);
      const raw = alertRangeRawWithClose(currentRaw, select.value === "1");
      setProfileEdit(select.dataset.classIndex, "alertRange", raw, originalRaw);
      updateProfileComboStatus({ dataset: { classIndex: select.dataset.classIndex } }, true);
      markProfilePanelsDirty("profiles", "selected");
      renderActiveProfilePanel(true);
    }

    function commitSpawnDestinationDistanceSelect(select) {
      const originalRaw = select.dataset.original;
      const currentRaw = pendingProfileValue(select.dataset.classIndex, "spawnDestination", originalRaw);
      const typeKey = spawnDestinationTypeKeyForRaw(currentRaw);
      const raw = spawnDestinationRawForType(typeKey, select.value);
      setProfileEdit(select.dataset.classIndex, "spawnDestination", raw, originalRaw);
      updateProfileComboStatus({ dataset: { classIndex: select.dataset.classIndex } }, true);
      markProfilePanelsDirty("profiles", "selected");
      renderActiveProfilePanel(true);
    }

    els.profilesTab.addEventListener("input", event => {
      const input = event.target.closest(".profile-combo");
      if (!input) return;
      input.dataset.comboFilter = "1";
      commitProfileCombo(input);
      updateProfileComboStatus(input);
      renderProfileComboMenu(input);
    });
    els.profilesTab.addEventListener("change", event => {
      const input = event.target.closest(".profile-combo");
      if (!input) return;
      commitProfileCombo(input, true);
      updateProfileComboStatus(input, true);
      if (profileFieldRerendersSubcontrols(input.dataset.field)) {
        closeProfileComboMenu();
        markProfilePanelsDirty("profiles", "selected");
        renderActiveProfilePanel(true);
      }
    });
    els.profilesTab.addEventListener("change", event => {
      const select = event.target.closest("[data-profile-alert-close-range]");
      if (!select) return;
      commitAlertCloseRangeSelect(select);
    });
    els.profilesTab.addEventListener("change", event => {
      const select = event.target.closest("[data-profile-spawn-destination-distance]");
      if (!select) return;
      commitSpawnDestinationDistanceSelect(select);
    });
    els.profilesTab.addEventListener("focusout", event => {
      const input = event.target.closest(".profile-combo");
      if (!input) return;
      commitProfileCombo(input, true);
      updateProfileComboStatus(input, true);
      delete input.dataset.comboFilter;
      if (profileFieldRerendersSubcontrols(input.dataset.field)) {
        closeProfileComboMenu();
        markProfilePanelsDirty("profiles", "selected");
        renderActiveProfilePanel(true);
        return;
      }
      setTimeout(() => {
        if (activeProfileComboInput === input && !els.profileComboMenu.contains(document.activeElement)) {
          closeProfileComboMenu();
        }
      }, 80);
    });
    els.profilesTab.addEventListener("focusin", event => {
      const input = event.target.closest(".profile-combo");
      if (!input) return;
      input.dataset.comboFilter = "0";
      renderProfileComboMenu(input);
    });
    els.profilesTab.addEventListener("click", event => {
      const input = event.target.closest(".profile-combo");
      if (!input) return;
      input.dataset.comboFilter = "0";
      renderProfileComboMenu(input);
    });
    els.profilesTab.addEventListener("keydown", event => {
      const input = event.target.closest(".profile-combo");
      if (!input) return;
      if (event.key === "ArrowDown") {
        event.preventDefault();
        if (els.profileComboMenu.hidden || activeProfileComboInput !== input) {
          if (input.dataset.comboFilter !== "1") input.dataset.comboFilter = "0";
          renderProfileComboMenu(input);
        } else {
          moveProfileComboMenu(1);
        }
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        if (els.profileComboMenu.hidden || activeProfileComboInput !== input) {
          if (input.dataset.comboFilter !== "1") input.dataset.comboFilter = "0";
          renderProfileComboMenu(input);
        } else {
          moveProfileComboMenu(-1);
        }
      } else if (event.key === "Enter" && !els.profileComboMenu.hidden && activeProfileComboInput === input) {
        const option = els.profileComboMenu.querySelector(`.profile-combo-option[data-index="${profileComboMenuIndex}"]`);
        if (option) {
          event.preventDefault();
          chooseProfileComboOption(option.dataset.raw);
        }
      } else if (event.key === "Escape" && activeProfileComboInput === input) {
        event.preventDefault();
        closeProfileComboMenu();
        input.blur();
      }
    });
    document.querySelectorAll(".tab").forEach(tab => {
      tab.addEventListener("click", () => {
        activeTab = tab.dataset.tab;
        renderTabs();
        renderActiveProfilePanel();
      });
    });

    loadData().then(() => {
      loadShinyCounter().catch(() => {});
      pollBuildStatus();
    }).catch(error => {
      els.detailHead.innerHTML = `<div><h2>Could not load data</h2><div class="meta">${esc(error.message)}</div></div>`;
      els.refresh.disabled = false;
    });
  </script>
</body>
</html>
"""


class ViewerHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def send_bytes(
        self,
        body: bytes,
        content_type: str,
        status: int = 200,
        cache_control: str = "no-store",
        content_encoding: str | None = None,
        etag: str | None = None,
        vary: str | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", cache_control)
        if content_encoding:
            self.send_header("Content-Encoding", content_encoding)
        if etag:
            self.send_header("ETag", etag)
        if vary:
            self.send_header("Vary", vary)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_not_modified(self, etag: str) -> None:
        self.send_response(304)
        self.send_header("Cache-Control", "no-cache")
        self.send_header("ETag", etag)
        self.send_header("Vary", "Accept-Encoding")
        self.end_headers()

    def send_json(self, payload: dict, status: int = 200) -> None:
        self.send_bytes(
            json.dumps(payload, separators=(",", ":")).encode(),
            "application/json; charset=utf-8",
            status=status,
        )

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path in ("/", "/index.html"):
                self.send_bytes(HTML.encode(), "text/html; charset=utf-8")
                return
            icon_match = re.fullmatch(r"/icons/(\d+)\.png", path)
            if icon_match:
                icon_path = cached_icon_paths().get(int(icon_match.group(1), 10))
                if icon_path is not None:
                    self.send_bytes(
                        cached_render_icon_png(str(icon_path)),
                        "image/png",
                        cache_control="public, max-age=86400",
                    )
                    return
                self.send_bytes(b"icon not found\n", "text/plain; charset=utf-8", status=404)
                return
            if path == "/data.json":
                cached = cached_data_json()
                etag = str(cached["etag"])
                if self.headers.get("If-None-Match") == etag:
                    self.send_not_modified(etag)
                    return
                accepts_gzip = "gzip" in self.headers.get("Accept-Encoding", "")
                body = cached["gzip"] if accepts_gzip else cached["body"]
                self.send_bytes(
                    body,
                    "application/json; charset=utf-8",
                    cache_control="no-cache",
                    content_encoding="gzip" if accepts_gzip else None,
                    etag=etag,
                    vary="Accept-Encoding",
                )
                return
            if path == "/build-status":
                self.send_json(build_status_payload())
                return
            if path == "/shiny-counter":
                self.send_json(shiny_counter_payload())
                return
            self.send_bytes(b"not found\n", "text/plain; charset=utf-8", status=404)
        except Exception as exc:  # pragma: no cover - surfaced in browser during local use
            body = json.dumps({"error": str(exc)}, indent=2).encode()
            self.send_bytes(body, "application/json; charset=utf-8", status=500)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length)
            if path == "/save-profiles":
                self.send_json(apply_profile_changes(body))
                return
            if path == "/save-profile-memberships":
                self.send_json(apply_profile_membership_changes(body))
                return
            if path == "/manage-profiles":
                self.send_json(apply_profile_management_change(body))
                return
            if path == "/save-profile-overrides":
                self.send_json(apply_profile_override_changes(body))
                return
            if path == "/save-encounters":
                self.send_json(apply_encounter_changes(body))
                return
            if path == "/save-spawn-settings":
                self.send_json(apply_spawn_setting_changes(body))
                return
            if path == "/build":
                payload = json.loads(body.decode() or "{}")
                self.send_json(start_build_job(bool(payload.get("runAfter"))))
                return
            if path == "/open-test-nds":
                self.send_json(open_test_nds())
                return
            if path == "/shiny-counter":
                payload = json.loads(body.decode() or "{}")
                if "counter" not in payload:
                    raise ValueError("counter is required")
                self.send_json(set_shiny_counter(int(payload["counter"])))
                return
            self.send_json({"error": "not found"}, status=404)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, status=400)
        except FileNotFoundError as exc:
            self.send_json({"error": str(exc)}, status=404)
        except Exception as exc:  # pragma: no cover - surfaced in browser during local use
            self.send_json({"error": str(exc)}, status=500)


def serve(host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), ViewerHandler)
    actual_host, actual_port = server.server_address
    print(f"Overworld behaviour profile viewer: http://{actual_host}:{actual_port}")
    server.serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print parsed overview data as JSON")
    parser.add_argument("--serve", action="store_true", help="serve the interactive browser UI")
    parser.add_argument("--host", default="127.0.0.1", help="host for --serve")
    parser.add_argument("--port", type=int, default=8765, help="port for --serve; use 0 for any free port")
    args = parser.parse_args(argv)

    if args.json:
        json.dump(build_data(), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    if args.serve:
        serve(args.host, args.port)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
