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
import math
import operator
import os
import pty
import re
import select
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import threading
import time
import wave
from collections import OrderedDict
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
SNDSEQ_HEADER = ROOT / "include/constants/sndseq.h"
SDAT_INFO_BLOCK = ROOT / "build/sdat/InfoBlock.json"
SDAT_SEQ_DIR = ROOT / "build/sdat/Files/SEQ"
SDAT_BANK_DIR = ROOT / "build/sdat/Files/BANK"
SDAT_WAVARC_DIR = ROOT / "build/sdat/Files/WAVARC"
MOVE_ANIM_DIR = ROOT / "armips/move/move_anim"
MOVES_DATA_SOURCE = ROOT / "armips/data/moves.s"
SOUND_RENDER_SAMPLE_RATE = 44100
SOUND_RENDER_MAX_SECONDS = 16.0
NDS_SOUND_HEARTBEAT_RATE = 33513982.0 / (64.0 * 2728.0)
MOVE_SOUND_FRAME_RATE = 60.0
MOVE_SOUND_MAX_SECONDS = 16.0
MOVE_SOUND_WAITSTATE_FRAMES = 12
MOVE_SOUND_WAITPARTICLE_FRAMES = 20
SSEQ_TICKS_PER_QUARTER = 48

BLOB_BEHAVIOR_FIELD_INDEXES = {
    "sOverworldWildBehaviorClassProfiles": 1,
    "sOverworldWildBehaviorClassRules": 2,
    "sOverworldWildBehaviorSpeciesClassRules": 3,
    "sOverworldWildBehaviorOverrideProfiles": 4,
    "sOverworldWildBehaviorOverrideMembers": 5,
    "sOverworldWildBehaviorOverrideRules": 5,
    "sOverworldWildBehaviorOverrides": 4,
}
OWBD_COUNT_DEFINES = {
    "OWBD_CLASS_PROFILE_COUNT": "sOverworldWildBehaviorClassProfiles",
    "OWBD_CLASS_RULE_COUNT": "sOverworldWildBehaviorClassRules",
    "OWBD_SPECIES_CLASS_RULE_COUNT": "sOverworldWildBehaviorSpeciesClassRules",
}
ENEMY_PARTY_SOURCE = ROOT / "src/field/enemy_party.c"
POKEGRA_MK = ROOT / "data/graphics/pokegra.mk"
POKE_FORM_DATA = ROOT / "data/PokeFormDataTbl.c"
ENCOUNTERS_SOURCE = ROOT / "armips/data/encounters.s"
HEADBUTT_SOURCE = ROOT / "armips/data/headbutt.s"
ENCOUNTER_LOOKUP_SOURCE = ROOT / "data/OverworldWildEncounterLookupData.c"
ENCOUNTER_OVERRIDES_SOURCE = ROOT / "data/OverworldWildEncounterOverrides.json"
MONDATA_SOURCE = ROOT / "armips/data/mondata.s"
BABYMONS_SOURCE = ROOT / "armips/data/babymons.s"
EVODATA_SOURCE = ROOT / "armips/data/evodata.s"
ARMIPS_CONSTANTS = ROOT / "armips/include/constants.s"
ARMIPS_CONFIG = ROOT / "armips/include/config.s"
TEST_NDS = ROOT / "test.nds"
DESMUME_TEST_DSV = Path.home() / "Library/Application Support/DeSmuME/0.9.13/Battery/test.dsv"
DELTA_TEST_DSV = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test.dsv"


def default_test_dsv_path() -> Path:
    for candidate in (DESMUME_TEST_DSV, DELTA_TEST_DSV):
        if candidate.exists():
            return candidate
    return DESMUME_TEST_DSV


TEST_DSV = Path(os.environ.get("HG_ENGINE_TEST_DSV", str(default_test_dsv_path()))).expanduser()
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
OVERWORLD_WILD_SHINY_COUNTER_MAGIC_V1 = 0x4F57
OVERWORLD_WILD_SHINY_COUNTER_MAGIC = 0x4F58
# Sav2_Misc_get uses save-array id 9. The current runtime save header places
# that block at 0x2614; the counter fields live at SAVE_MISC_DATA offsets
# 0x29C/0x29E. Keep this paired with the runtime save-array layout.
OVERWORLD_WILD_SHINY_MISC_SAVE_OFFSET = 0x2614
OVERWORLD_WILD_SHINY_COUNTER_SAVE_OFFSET = OVERWORLD_WILD_SHINY_MISC_SAVE_OFFSET + 0x29C
OVERWORLD_WILD_SHINY_MAGIC_SAVE_OFFSET = OVERWORLD_WILD_SHINY_MISC_SAVE_OFFSET + 0x29E
OVERWORLD_WILD_SAVED_SHINIES_SAVE_OFFSET = OVERWORLD_WILD_SHINY_MISC_SAVE_OFFSET + 0x288
OVERWORLD_WILD_SAVED_SHINY_SIZE = 6
OVERWORLD_WILD_MAX_SAVED_SHINIES = 2
OVERWORLD_WILD_SAVED_SHINY_ACTIVE = 0x80
OVERWORLD_WILD_SAVED_SHINY_TERRAIN_MASK = 0x7F
OVERWORLD_WILD_SPECIES_MASK = 0x7FF
OVERWORLD_WILD_FORM_SHIFT = 11
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
    ENCOUNTER_LOOKUP_SOURCE,
    ENCOUNTER_OVERRIDES_SOURCE,
    MONDATA_SOURCE,
    BABYMONS_SOURCE,
    EVODATA_SOURCE,
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
MACRO_LABEL_CACHE_LOCK = threading.Lock()
MACRO_LABEL_CACHE_MAX_CONTEXTS = 4
MACRO_LABEL_CACHES: OrderedDict[int, tuple[dict[str, int], dict[tuple[str, int | None, str | None], str]]] = OrderedDict()

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
    "alertChance",
    "spawnDestination",
    "attentiveBattle",
    "specialAction",
    "hopAllowNonCardinal",
    "hopMinDistance",
    "hopMaxDistance",
    "hopPause",
    "teleportTime",
    "teleportPause",
    "alertSpecialAction",
    "overworldLimit",
    "spawnDestinationMinDistance",
    "spawnDestinationMaxDistance",
    "ramAccelerationSteps",
    "ramMaxSpeed",
    "chainPauseAction",
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
    "hopTime",
    "attentiveChaseBoostDistance",
    "attentiveChaseBoostSpeed",
    "hopSpinSpeed",
    "spawnHopTime",
    "attentiveHopSpinSpeed",
    "attentiveCircleRadius",
    "attentiveContinueWhenArrived",
    "attentiveAvoidPreviousTile",
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
    "alertChance": "Alert chance",
    "spawnDestination": "Spawn destination",
    "attentiveBattle": "Battle Active",
    "specialAction": "Movement style",
    "hopAllowNonCardinal": "Allow non-cardinal",
    "hopMinDistance": "Min hop distance",
    "hopMaxDistance": "Max hop distance",
    "hopPause": "Hop pause",
    "hopTime": "Hop time",
    "hopSpinSpeed": "Spin speed",
    "spawnHopTime": "Spawn hop time",
    "attentiveHopSpinSpeed": "Spin speed",
    "teleportTime": "Teleport time",
    "teleportPause": "Teleport pause",
    "alertSpecialAction": "Special action",
    "overworldLimit": "Overworld # limit",
    "spawnDestinationMinDistance": "Min distance",
    "spawnDestinationMaxDistance": "Max distance",
    "ramAccelerationSteps": "Chain moves",
    "ramMaxSpeed": "Chain pause",
    "chainPauseAction": "Chain pause action",
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
    "attentiveChaseBoostDistance": "Boost distance",
    "attentiveChaseBoostSpeed": "Boost speed",
    "attentiveCircleRadius": "Circle radius",
    "attentiveContinueWhenArrived": "Continue when arrived",
    "attentiveAvoidPreviousTile": "Avoid previous tile",
}

FIELD_UNITS = {
    "spawnHopTime": "frames",
    "spawnDestinationMinDistance": "tiles",
    "spawnDestinationMaxDistance": "tiles",
    "overworldLimit": "Pokémon",
    "chillSpeed": "speed",
    "hopMinDistance": "tiles",
    "hopMaxDistance": "tiles",
    "hopTime": "frames",
    "hopSpinSpeed": "frames",
    "hopPause": "frames",
    "teleportTime": "frames",
    "teleportPause": "frames",
    "ramAccelerationSteps": "moves",
    "ramMaxSpeed": "frames",
    "alertTime": "frames",
    "alertness": "tiles",
    "alertChance": "%",
    "stamina": "frames",
    "attentiveCircleRadius": "tiles",
    "attentiveSpeed": "speed",
    "attentiveHopMinDistance": "tiles",
    "attentiveHopMaxDistance": "tiles",
    "attentiveHopPause": "frames",
    "attentiveHopSpinSpeed": "frames",
    "attentiveTeleportTime": "frames",
    "attentiveTeleportPause": "frames",
    "attentiveRamAccelerationSteps": "steps",
    "attentiveRamMaxSpeed": "speed",
    "attentiveChaseBoostDistance": "tiles",
    "attentiveChaseBoostSpeed": "speed",
    "tiredSpeed": "speed",
    "tiredHopMinDistance": "tiles",
    "tiredHopMaxDistance": "tiles",
    "tiredHopPause": "frames",
    "tiredTeleportTime": "frames",
    "tiredTeleportPause": "frames",
    "tiredRamAccelerationSteps": "steps",
    "tiredRamMaxSpeed": "speed",
    "restTime": "frames",
    "range": "tiles",
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
    "attentiveBattle": "OW_WILD_BEHAVIOR_BATTLE_TRIGGER_",
    "specialAction": "OW_WILD_BEHAVIOR_LOCOMOTION_",
    "chainPauseAction": "OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_",
    "hopAllowNonCardinal": "OW_WILD_BEHAVIOR_BOOL_",
    "attentiveHopAllowNonCardinal": "OW_WILD_BEHAVIOR_BOOL_",
    "tiredHopAllowNonCardinal": "OW_WILD_BEHAVIOR_BOOL_",
    "attentiveContinueWhenArrived": "OW_WILD_BEHAVIOR_BOOL_",
    "attentiveAvoidPreviousTile": "OW_WILD_BEHAVIOR_BOOL_",
    "alertSpecialAction": "OW_WILD_BEHAVIOR_ALERT_SPECIAL_",
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
    "OW_WILD_BEHAVIOR_TARGET_PLAYER_FRONT",
    "OW_WILD_BEHAVIOR_TARGET_PLAYER_CARDINAL_LINE",
]

CANONICAL_ACTIVE_TARGET_RAWS = [
    *CANONICAL_TARGET_RAWS,
    "OW_WILD_BEHAVIOR_TARGET_CIRCLE_PLAYER",
]

CANONICAL_ALERT_SPECIAL_ACTION_RAWS = [
    "OW_WILD_BEHAVIOR_ALERT_SPECIAL_NONE",
    "OW_WILD_BEHAVIOR_ALERT_SPECIAL_CALL_FOR_HELP",
    "OW_WILD_BEHAVIOR_ALERT_SPECIAL_PICKUP_THROW",
]

CANONICAL_CHAIN_PAUSE_ACTION_RAWS = [
    "OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE",
    "OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE",
    "OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_LOOK_AROUND",
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
    "targetSelector": CANONICAL_ACTIVE_TARGET_RAWS,
    "specialAction": CANONICAL_MOVEMENT_STYLE_RAWS,
    "alertSpecialAction": CANONICAL_ALERT_SPECIAL_ACTION_RAWS,
    "chainPauseAction": CANONICAL_CHAIN_PAUSE_ACTION_RAWS,
    "chillAllowedTile": CANONICAL_ALLOWED_TILE_RAWS,
    "attentiveAllowedTile": CANONICAL_ALLOWED_TILE_RAWS,
    "tiredAllowedTile": CANONICAL_ALLOWED_TILE_RAWS,
    "chillAllowedTile2": CANONICAL_SECONDARY_ALLOWED_TILE_RAWS,
    "attentiveAllowedTile2": CANONICAL_SECONDARY_ALLOWED_TILE_RAWS,
    "tiredAllowedTile2": CANONICAL_SECONDARY_ALLOWED_TILE_RAWS,
    "attentiveHopAllowNonCardinal": ["OW_WILD_BEHAVIOR_BOOL_NO", "OW_WILD_BEHAVIOR_BOOL_YES"],
    "tiredHopAllowNonCardinal": ["OW_WILD_BEHAVIOR_BOOL_NO", "OW_WILD_BEHAVIOR_BOOL_YES"],
    "attentiveContinueWhenArrived": ["OW_WILD_BEHAVIOR_BOOL_NO", "OW_WILD_BEHAVIOR_BOOL_YES"],
    "attentiveAvoidPreviousTile": ["OW_WILD_BEHAVIOR_BOOL_NO", "OW_WILD_BEHAVIOR_BOOL_YES"],
}

PROFILE_OPTION_EXCLUDED_SUFFIXES = (
    "_COUNT",
    "_MAX",
    "_NUM",
    "_LAST",
)

PROFILE_OPTION_FIELD_EXCLUDED_RAWS = {
    "chillAllowedTile": {"OW_WILD_BEHAVIOR_ALLOWED_TILE_NONE"},
    "attentiveAllowedTile": {"OW_WILD_BEHAVIOR_ALLOWED_TILE_NONE"},
    "tiredAllowedTile": {"OW_WILD_BEHAVIOR_ALLOWED_TILE_NONE"},
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
    "OW_WILD_BEHAVIOR_OVERRIDE_ALERT_CHANCE": "alertChance",
    "OW_WILD_BEHAVIOR_OVERRIDE_SPAWN_DESTINATION": "spawnDestination",
    "OW_WILD_BEHAVIOR_OVERRIDE_ATTENTIVE_BATTLE": "attentiveBattle",
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
    "OW_WILD_BEHAVIOR_OVERRIDE3_OVERWORLD_LIMIT": "overworldLimit",
    "OW_WILD_BEHAVIOR_OVERRIDE3_HOP_TIME": "hopTime",
    "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_CHASE_BOOST_DISTANCE": "attentiveChaseBoostDistance",
    "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_CHASE_BOOST_SPEED": "attentiveChaseBoostSpeed",
    "OW_WILD_BEHAVIOR_OVERRIDE3_HOP_SPIN_SPEED": "hopSpinSpeed",
    "OW_WILD_BEHAVIOR_OVERRIDE3_SPAWN_HOP_TIME": "spawnHopTime",
    "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_HOP_SPIN_SPEED": "attentiveHopSpinSpeed",
    "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_CIRCLE_RADIUS": "attentiveCircleRadius",
    "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_CONTINUE_WHEN_ARRIVED": "attentiveContinueWhenArrived",
    "OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_AVOID_PREVIOUS_TILE": "attentiveAvoidPreviousTile",
    "OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_PAUSE_ACTION": "chainPauseAction",
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
RUNTIME_OWNED_CLASS_SYMBOLS = {
    "OW_WILD_BEHAVIOR_CLASS_PICKED_UP",
}
OVERRIDE_PROFILE_NAME_RE = re.compile(r"/\*\s*profile\s*:\s*(.*?)\s*\*/", re.S)
OVERRIDE_PROFILE_NO_TARGET_CLASS_RAW = "0xFE"
OVERRIDE_PROFILE_NO_TARGET_CLASS_VALUE = 0xFE
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
    "alertChance",
    "hopMinDistance",
    "hopMaxDistance",
    "hopPause",
    "hopTime",
    "hopSpinSpeed",
    "spawnHopTime",
    "attentiveHopSpinSpeed",
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
    "overworldLimit",
    "spawnDestinationMinDistance",
    "spawnDestinationMaxDistance",
    "ramAccelerationSteps",
    "ramMaxSpeed",
    "attentiveChaseBoostDistance",
    "attentiveChaseBoostSpeed",
    "attentiveCircleRadius",
}

# Override profiles may transform numeric byte fields produced by earlier
# layers. Signed values adjust the stored byte, while /< and /> impose an
# inclusive lower or upper bound respectively. Exact values remain unprefixed.
RELATIVE_OVERRIDE_PROFILE_FIELDS = frozenset(NUMERIC_PROFILE_FIELDS & set(OVERRIDE_SYMBOL_BY_FIELD))
BOUNDED_OVERRIDE_PROFILE_FIELDS = frozenset({
    "chillSpeed",
    "attentiveSpeed",
    "tiredSpeed",
    "range",
    "hopPause",
    "teleportTime",
    "teleportPause",
    "hopTime",
    "hopSpinSpeed",
    "spawnHopTime",
    "attentiveHopSpinSpeed",
    "ramAccelerationSteps",
    "attentiveHopPause",
    "attentiveTeleportTime",
    "attentiveTeleportPause",
    "attentiveRamAccelerationSteps",
    "tiredHopPause",
    "tiredTeleportTime",
    "tiredTeleportPause",
    "tiredRamAccelerationSteps",
    "attentiveChaseBoostDistance",
    "attentiveChaseBoostSpeed",
    "attentiveCircleRadius",
})
MOVEMENT_SPEED_FIELDS = frozenset({"chillSpeed", "attentiveSpeed", "tiredSpeed"})
RELATIVE_OVERRIDE_DELTA_MIN = -127
RELATIVE_OVERRIDE_DELTA_MAX = 127
RELATIVE_OVERRIDE_RAW_RE = re.compile(r"^[+-]\d+$")
AT_LEAST_OVERRIDE_RAW_RE = re.compile(r"^/<(\d+)$")
AT_MOST_OVERRIDE_RAW_RE = re.compile(r"^/>(\d+)$")


def is_relative_override_raw(field: str, raw: str) -> bool:
    return field in RELATIVE_OVERRIDE_PROFILE_FIELDS and RELATIVE_OVERRIDE_RAW_RE.fullmatch(clean_token(raw)) is not None


def is_at_least_override_raw(field: str, raw: str) -> bool:
    return field in BOUNDED_OVERRIDE_PROFILE_FIELDS and AT_LEAST_OVERRIDE_RAW_RE.fullmatch(clean_token(raw)) is not None


def is_at_most_override_raw(field: str, raw: str) -> bool:
    return field in BOUNDED_OVERRIDE_PROFILE_FIELDS and AT_MOST_OVERRIDE_RAW_RE.fullmatch(clean_token(raw)) is not None


def is_numeric_override_operator_raw(field: str, raw: str) -> bool:
    return is_relative_override_raw(field, raw) or is_at_least_override_raw(field, raw) or is_at_most_override_raw(field, raw)


def relative_override_fields_from_raws(profile_raws: dict[str, str]) -> set[str]:
    return {
        field
        for field, raw in profile_raws.items()
        if is_relative_override_raw(field, raw)
    }


def at_least_override_fields_from_raws(profile_raws: dict[str, str]) -> set[str]:
    return {field for field, raw in profile_raws.items() if is_at_least_override_raw(field, raw)}


def at_most_override_fields_from_raws(profile_raws: dict[str, str]) -> set[str]:
    return {field for field, raw in profile_raws.items() if is_at_most_override_raw(field, raw)}

NUMERIC_PROFILE_FIELD_OPTION_MAX = {
    "chillSpeed": 4,
    "attentiveSpeed": 4,
    "tiredSpeed": 4,
    "alertTime": 255,
    "alertChance": 100,
    "hopMinDistance": 12,
    "hopMaxDistance": 12,
    "hopPause": 255,
    "hopTime": 64,
    "hopSpinSpeed": 15,
    "spawnHopTime": 64,
    "attentiveHopSpinSpeed": 15,
    "teleportTime": 64,
    "teleportPause": 255,
    "overworldLimit": 10,
    "spawnDestinationMinDistance": 8,
    "spawnDestinationMaxDistance": 8,
    "ramAccelerationSteps": 32,
    # Shared storage: Movement Chain reads this as a 0..255-frame pause, while
    # RAM consumers independently clamp it to their 0..4 speed tier.
    "ramMaxSpeed": 255,
    "attentiveChaseBoostDistance": 32,
    "attentiveChaseBoostSpeed": 4,
    "attentiveCircleRadius": 8,
}
NUMERIC_PROFILE_FIELD_OPTION_MIN = {
    "chillSpeed": 1,
    "attentiveSpeed": 1,
    "tiredSpeed": 1,
    "spawnDestinationMinDistance": 1,
    "spawnDestinationMaxDistance": 1,
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

# Unlike the shared chill-state byte above, these state-specific fields are
# exclusively RAM speed tiers.
NUMERIC_PROFILE_FIELD_OPTION_MAX["attentiveRamMaxSpeed"] = 4
NUMERIC_PROFILE_FIELD_OPTION_MAX["tiredRamMaxSpeed"] = 4


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


def _uncached_macro_label(symbol: str, value: int | None, field: str | None, macros: dict[str, int]) -> str:
    label_overrides = {
        "OW_WILD_BEHAVIOR_LOCOMOTION_WANDER": "Walk",
        "OW_WILD_BEHAVIOR_ALERT_SPECIAL_CALL_FOR_HELP": "Call for help",
        "OW_WILD_BEHAVIOR_ALERT_SPECIAL_PICKUP_THROW": "Pick up and throw",
        "OW_WILD_BEHAVIOR_TARGET_PLAYER_CARDINAL_LINE": "Player cardinal line",
        "OW_WILD_BEHAVIOR_CLASS_AGRESSIVE_CHASE": "Aggressive chase",
        "OW_WILD_BEHAVIOR_CLASS_AGGRESSIVE_RAM": "Aggressive ram",
        "OW_WILD_BEHAVIOR_CLASS_CANOPY_HOPPER_2": "Canopy hopper",
        "OW_WILD_BEHAVIOR_CLASS_PHANTOM_STALKER": "Phantom stalker",
        "OW_WILD_BEHAVIOR_CLASS_THROWING": "Throwing",
        "OW_WILD_BEHAVIOR_CLASS_PICKED_UP": "Picked up",
        "OW_WILD_BEHAVIOR_MATCH_CLASS_FORCED_ASLEEP": "Forced asleep",
    }
    if symbol in label_overrides:
        return label_overrides[symbol]
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


def macro_label(symbol: str, value: int | None, field: str | None, macros: dict[str, int]) -> str:
    """Resolve a display label once per parsed macro table.

    A workspace snapshot asks for the same few hundred labels tens of thousands
    of times while expanding per-species profile data.  The parsed macro table
    is immutable for that snapshot, so an identity-scoped cache avoids repeating
    the linear prefix/value search without ever sharing labels across revisions.
    """

    context_key = id(macros)
    label_key = (symbol, value, field)
    with MACRO_LABEL_CACHE_LOCK:
        context = MACRO_LABEL_CACHES.get(context_key)
        if context is not None and context[0] is macros and label_key in context[1]:
            MACRO_LABEL_CACHES.move_to_end(context_key)
            return context[1][label_key]

    label = _uncached_macro_label(symbol, value, field, macros)
    with MACRO_LABEL_CACHE_LOCK:
        context = MACRO_LABEL_CACHES.get(context_key)
        if context is None or context[0] is not macros:
            context = (macros, {})
            MACRO_LABEL_CACHES[context_key] = context
        context[1][label_key] = label
        MACRO_LABEL_CACHES.move_to_end(context_key)
        while len(MACRO_LABEL_CACHES) > MACRO_LABEL_CACHE_MAX_CONTEXTS:
            MACRO_LABEL_CACHES.popitem(last=False)
    return label


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


def canonical_profile_value_raw(value: dict, field: str) -> str:
    evaluated = numeric(value)
    if field in NUMERIC_PROFILE_FIELDS and evaluated is not None:
        if is_relative_override_raw(field, value.get("raw", "")):
            return f"{evaluated:+d}"
        if is_at_least_override_raw(field, value.get("raw", "")):
            return f"/<{evaluated}"
        if is_at_most_override_raw(field, value.get("raw", "")):
            return f"/>{evaluated}"
        return str(evaluated)
    return value.get("raw", "")


def profile_numeric_view(profile: dict[str, dict]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for field, value in profile.items():
        if field in NUMERIC_PROFILE_FIELDS and numeric(value) is not None:
            if is_relative_override_raw(field, value.get("raw", "")):
                raw = f"{numeric(value):+d}"
            elif is_at_least_override_raw(field, value.get("raw", "")):
                raw = f"/<{numeric(value)}"
            elif is_at_most_override_raw(field, value.get("raw", "")):
                raw = f"/>{numeric(value)}"
            else:
                raw = str(numeric(value))
            result[field] = {**value, "raw": raw, "symbol": None, "label": raw}
        else:
            result[field] = copy.deepcopy(value)
    return result


def canonical_profile_change_raw(
    field: str,
    raw: str,
    macros: dict[str, int],
    *,
    allow_relative: bool = False,
) -> str:
    cleaned = clean_token(raw)
    if cleaned == "":
        return ""
    if field not in NUMERIC_PROFILE_FIELDS:
        return cleaned
    if RELATIVE_OVERRIDE_RAW_RE.fullmatch(cleaned):
        if not allow_relative:
            raise ValueError(f"relative values are only valid in override profiles: {field}")
        if field not in RELATIVE_OVERRIDE_PROFILE_FIELDS:
            raise ValueError(f"field cannot use a relative override value: {field}")
        delta = int(cleaned, 10)
        if delta == 0:
            return ""
        if delta < RELATIVE_OVERRIDE_DELTA_MIN or delta > RELATIVE_OVERRIDE_DELTA_MAX:
            raise ValueError(
                f"relative override for {field} must be between {RELATIVE_OVERRIDE_DELTA_MIN:+d} and {RELATIVE_OVERRIDE_DELTA_MAX:+d}"
            )
        return f"{delta:+d}"
    bound_match = AT_LEAST_OVERRIDE_RAW_RE.fullmatch(cleaned) or AT_MOST_OVERRIDE_RAW_RE.fullmatch(cleaned)
    if bound_match:
        if not allow_relative:
            raise ValueError(f"numeric override operators are only valid in override profiles: {field}")
        if field not in BOUNDED_OVERRIDE_PROFILE_FIELDS:
            raise ValueError(f"field cannot use a numeric override operator: {field}")
        threshold = int(bound_match.group(1), 10)
        maximum = NUMERIC_PROFILE_FIELD_OPTION_MAX.get(field, 64)
        minimum = 1 if field in MOVEMENT_SPEED_FIELDS else 0
        if threshold < minimum or threshold > maximum:
            raise ValueError(f"override bound for {field} must be between {minimum} and {maximum}")
        return f"/{cleaned[1]}{threshold}"
    value = make_value(cleaned, field, macros)
    evaluated = numeric(value)
    if evaluated is None:
        raise ValueError(f"invalid numeric value for {field}: {raw}")
    minimum = NUMERIC_PROFILE_FIELD_OPTION_MIN.get(field, 0)
    maximum = NUMERIC_PROFILE_FIELD_OPTION_MAX.get(field, 64)
    if evaluated < minimum or evaluated > maximum:
        raise ValueError(f"value for {field} must be between {minimum} and {maximum}")
    return str(evaluated)


def parse_profile(items: list, macros: dict[str, int]) -> dict[str, dict]:
    if len(items) == 1 and clean_token(str(items[0])) == "0":
        return {
            field: make_value("0", field, macros)
            for field in PROFILE_FIELDS
        }
    if len(items) > len(PROFILE_FIELDS):
        raise ParseError(f"profile has {len(items)} fields, expected {len(PROFILE_FIELDS)}")
    if len(items) < len(PROFILE_FIELDS):
        items = [*items, *(["0"] * (len(PROFILE_FIELDS) - len(items)))]
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
            field = override_fields.get(symbol)
            bits.append(
                {
                    "symbol": symbol,
                    "field": field,
                    "label": FIELD_LABELS.get(field, symbol),
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
    display_raw = " | ".join(bit["symbol"] for bit in bits if bit.get("field")) or "0"
    return {
        "raw": clean_token(raw),
        "displayRaw": display_raw,
        "value": value["value"],
        "bits": bits,
        "labels": [bit["label"] for bit in bits if bit.get("field")],
    }


def parse_behavior_override(items: list, macros: dict[str, int]) -> dict:
    relative_mask_raw = "0"
    relative_mask2_raw = "0"
    relative_mask3_raw = "0"
    at_least_mask_raw = "0"
    at_least_mask2_raw = "0"
    at_least_mask3_raw = "0"
    at_most_mask_raw = "0"
    at_most_mask2_raw = "0"
    at_most_mask3_raw = "0"
    if len(items) == 13 and isinstance(items[3], list):
        mask_raw = str(items[0])
        mask2_raw = str(items[1])
        mask3_raw = str(items[2])
        profile_items = items[3]
        relative_mask_raw = str(items[4])
        relative_mask2_raw = str(items[5])
        relative_mask3_raw = str(items[6])
        at_least_mask_raw = str(items[7])
        at_least_mask2_raw = str(items[8])
        at_least_mask3_raw = str(items[9])
        at_most_mask_raw = str(items[10])
        at_most_mask2_raw = str(items[11])
        at_most_mask3_raw = str(items[12])
    elif len(items) == 7 and isinstance(items[3], list):
        mask_raw = str(items[0])
        mask2_raw = str(items[1])
        mask3_raw = str(items[2])
        profile_items = items[3]
        relative_mask_raw = str(items[4])
        relative_mask2_raw = str(items[5])
        relative_mask3_raw = str(items[6])
    elif len(items) == 2 and isinstance(items[1], list):
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
    relative_mask = parse_mask(relative_mask_raw, macros, OVERRIDE1_FIELDS)
    relative_mask2 = parse_mask(relative_mask2_raw, macros, OVERRIDE2_FIELDS)
    relative_mask3 = parse_mask(relative_mask3_raw, macros, OVERRIDE3_FIELDS)
    at_least_mask = parse_mask(at_least_mask_raw, macros, OVERRIDE1_FIELDS)
    at_least_mask2 = parse_mask(at_least_mask2_raw, macros, OVERRIDE2_FIELDS)
    at_least_mask3 = parse_mask(at_least_mask3_raw, macros, OVERRIDE3_FIELDS)
    at_most_mask = parse_mask(at_most_mask_raw, macros, OVERRIDE1_FIELDS)
    at_most_mask2 = parse_mask(at_most_mask2_raw, macros, OVERRIDE2_FIELDS)
    at_most_mask3 = parse_mask(at_most_mask3_raw, macros, OVERRIDE3_FIELDS)
    profile = parse_profile(profile_items, macros)
    mask_fields = {bit.get("field") for parsed in (mask, mask2, mask3) for bit in parsed["bits"] if bit.get("field")}
    relative_fields = {bit.get("field") for parsed in (relative_mask, relative_mask2, relative_mask3) for bit in parsed["bits"] if bit.get("field")}
    at_least_fields = {bit.get("field") for parsed in (at_least_mask, at_least_mask2, at_least_mask3) for bit in parsed["bits"] if bit.get("field")}
    at_most_fields = {bit.get("field") for parsed in (at_most_mask, at_most_mask2, at_most_mask3) for bit in parsed["bits"] if bit.get("field")}
    for operator_name, operator_fields, supported_fields in (
        ("relative", relative_fields, RELATIVE_OVERRIDE_PROFILE_FIELDS),
        ("at-least", at_least_fields, BOUNDED_OVERRIDE_PROFILE_FIELDS),
        ("at-most", at_most_fields, BOUNDED_OVERRIDE_PROFILE_FIELDS),
    ):
        inactive = sorted(operator_fields - mask_fields)
        if inactive:
            raise ParseError(f"{operator_name} override masks include inactive fields: {', '.join(inactive)}")
        unsupported = sorted(operator_fields - supported_fields)
        if unsupported:
            raise ParseError(f"{operator_name} override masks include non-numeric fields: {', '.join(unsupported)}")
    overlap = (relative_fields & at_least_fields) | (relative_fields & at_most_fields) | (at_least_fields & at_most_fields)
    if overlap:
        raise ParseError(f"override operator masks overlap for: {', '.join(sorted(overlap))}")
    for field in relative_fields:
        stored_raw = clean_token(profile[field].get("raw", ""))
        explicit_delta = re.fullmatch(r"OW_WILD_BEHAVIOR_RELATIVE\(\s*([+-]?\d+)\s*\)", stored_raw)
        stored_value = numeric(profile[field])
        delta = int(explicit_delta.group(1), 10) if explicit_delta else (
            None if stored_value is None else ((stored_value + 128) % 256) - 128
        )
        if delta is None or delta < RELATIVE_OVERRIDE_DELTA_MIN or delta > RELATIVE_OVERRIDE_DELTA_MAX:
            raise ParseError(f"relative override for {field} is outside signed byte range")
        profile[field]["raw"] = f"{delta:+d}"
        profile[field]["value"] = delta
        profile[field]["label"] = f"{delta:+d}"
        profile[field]["symbol"] = None
    for operator, fields, wrapper in (
        ("/<", at_least_fields, "OW_WILD_BEHAVIOR_AT_LEAST"),
        ("/>", at_most_fields, "OW_WILD_BEHAVIOR_AT_MOST"),
    ):
        for field in fields:
            stored_raw = clean_token(profile[field].get("raw", ""))
            explicit_threshold = re.fullmatch(rf"{wrapper}\(\s*(\d+)\s*\)", stored_raw)
            canonical_threshold = re.fullmatch(rf"{re.escape(operator)}(\d+)", stored_raw)
            stored_value = numeric(profile[field])
            threshold = (
                int(explicit_threshold.group(1), 10)
                if explicit_threshold
                else (int(canonical_threshold.group(1), 10) if canonical_threshold else stored_value)
            )
            maximum = NUMERIC_PROFILE_FIELD_OPTION_MAX.get(field, 64)
            minimum = 1 if field in MOVEMENT_SPEED_FIELDS else 0
            if threshold is None or threshold < minimum or threshold > maximum:
                raise ParseError(f"{operator} override for {field} must be between {minimum} and {maximum}")
            profile[field]["raw"] = f"{operator}{threshold}"
            profile[field]["value"] = threshold
            profile[field]["label"] = f"{operator}{threshold}"
            profile[field]["symbol"] = None
    labels = mask["labels"] + mask2["labels"] + mask3["labels"]
    extra_raws = [extra["displayRaw"] for extra in (mask2, mask3) if extra["displayRaw"] != "0"]
    mask_raw_summary = mask["displayRaw"] if not extra_raws else " / ".join([mask["displayRaw"], *extra_raws])
    return {
        "mask": mask,
        "mask2": mask2,
        "mask3": mask3,
        "relativeMask": relative_mask,
        "relativeMask2": relative_mask2,
        "relativeMask3": relative_mask3,
        "relativeFields": sorted(relative_fields),
        "atLeastMask": at_least_mask,
        "atLeastMask2": at_least_mask2,
        "atLeastMask3": at_least_mask3,
        "atLeastFields": sorted(at_least_fields),
        "atMostMask": at_most_mask,
        "atMostMask2": at_most_mask2,
        "atMostMask3": at_most_mask3,
        "atMostFields": sorted(at_most_fields),
        "maskLabels": labels,
        "maskRaw": mask_raw_summary,
        "profile": profile,
    }


def behavior_source_uses_override_members(source: str) -> bool:
    return "sOverworldWildBehaviorOverrideMembers" in source or re.search(r"\boverrideMembers\b", source) is not None


def parse_behavior_override_profiles(source: str, macros: dict[str, int]) -> list[dict]:
    entries = parse_initializer(extract_braced_initializer(source, "sOverworldWildBehaviorOverrideProfiles"))
    member_values = []
    uses_member_model = behavior_source_uses_override_members(source)
    if uses_member_model:
        member_values = [
            make_value(str(raw), None, macros)
            for raw in parse_initializer(extract_braced_initializer(source, "sOverworldWildBehaviorOverrideMembers"))
        ]
    valid_member_values = {
        value
        for symbol, value in macros.items()
        if symbol.startswith("SPECIES_") and symbol != "SPECIES_NONE" and isinstance(value, int)
    }
    disabled_mode = macros.get("OW_WILD_BEHAVIOR_OVERRIDE_TARGET_DISABLED", 0)
    members_mode = macros.get("OW_WILD_BEHAVIOR_OVERRIDE_TARGET_MEMBERS", 1)
    all_mode = macros.get("OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL", 2)
    expected_member_start = 0
    profiles = []
    for order, entry in enumerate(entries, 1):
        if len(entry) in {8, 11, 17} and isinstance(entry[0], list):
            member_start = numeric(make_value(str(entry[1]), None, macros))
            member_count = numeric(make_value(str(entry[2]), None, macros))
            target_mode = make_value(str(entry[3]), None, macros)
            target_mode_value = numeric(target_mode)
            if member_start is None or member_count is None or member_start < 0 or member_count < 0:
                raise ParseError(f"override profile #{order} has invalid member range")
            if member_start > 0xFFFF or member_count > 0xFFFF:
                raise ParseError(f"override profile #{order} member range exceeds u16 storage")
            if member_start != expected_member_start:
                raise ParseError(f"override profile #{order} member slice is not contiguous")
            if target_mode_value not in {disabled_mode, members_mode, all_mode}:
                raise ParseError(f"override profile #{order} has invalid target mode")
            member_end = member_start + member_count
            if member_end > len(member_values) or member_end > 0xFFFF:
                raise ParseError(f"override profile #{order} member range exceeds member table")
            members = member_values[member_start:member_end]
            member_symbols = [str(member.get("symbol") or member.get("raw") or "") for member in members]
            if len(member_symbols) != len(set(member_symbols)):
                raise ParseError(f"override profile #{order} contains duplicate members")
            if any(numeric(member) not in valid_member_values for member in members):
                raise ParseError(f"override profile #{order} contains an invalid Pokemon member")
            if target_mode_value == members_mode and member_count == 0:
                raise ParseError(f"override profile #{order} member target is empty")
            match = parse_match(entry[0], macros)
            unresolved_match_fields = [field for field, value in match.items() if numeric(value) is None]
            if unresolved_match_fields:
                raise ParseError(
                    f"override profile #{order} has invalid shared match value for {', '.join(unresolved_match_fields)}"
                )
            any_species = macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_SPECIES", macros.get("SPECIES_NONE", 0))
            if numeric(match["species"]) != any_species:
                raise ParseError(f"override profile #{order} shared match must use ANY species")
            any_level = macros.get("OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY", 0)
            min_level = numeric(match["minLevel"])
            max_level = numeric(match["maxLevel"])
            if min_level != any_level and max_level != any_level and min_level > max_level:
                raise ParseError(f"override profile #{order} minimum level exceeds maximum level")
            if target_mode_value == all_mode:
                is_global = (
                    numeric(match["groupMask"]) == macros.get("OW_WILD_BEHAVIOR_GROUP_NONE", 0)
                    and numeric(match["terrain"]) == macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_TERRAIN")
                    and min_level == any_level
                    and max_level == any_level
                    and numeric(match["shiny"]) == macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_SHINY")
                    and numeric(match["behaviorClass"]) == macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_CLASS")
                )
                if is_global:
                    raise ParseError(f"override profile #{order} ALL target requires a shared condition")
            expected_member_start = member_end
            profiles.append(
                {
                    "order": order,
                    "profileOrder": order,
                    "kind": "behavior",
                    "match": match,
                    "memberStart": member_start,
                    "memberCount": member_count,
                    "members": members,
                    "memberSymbols": member_symbols,
                    "targetMode": target_mode,
                    "behavior": parse_behavior_override(entry[4:], macros),
                }
            )
            continue
        if uses_member_model:
            raise ParseError(f"override profile #{order} does not use the member target shape")
        profiles.append(
            {
                "order": order,
                "behavior": parse_behavior_override(entry, macros),
            }
        )
    if uses_member_model:
        if expected_member_start == 0:
            sentinel_ok = len(member_values) == 1 and numeric(member_values[0]) == macros.get("SPECIES_NONE", 0)
            if not sentinel_ok:
                raise ParseError("empty override member storage must contain one SPECIES_NONE sentinel")
        elif expected_member_start != len(member_values):
            raise ParseError("override member table contains unreferenced entries")
    return profiles


def parse_behavior_override_rules(source: str, macros: dict[str, int], group_labels: dict[int, dict]) -> list[dict]:
    profiles = parse_behavior_override_profiles(source, macros)
    rules = []
    entries = parse_initializer(extract_braced_initializer(source, "sOverworldWildBehaviorOverrideRules"))
    for order, entry in enumerate(entries, 1):
        if len(entry) != 2:
            raise ParseError("behavior override rule initializer shape changed")
        profile_index = make_value(str(entry[1]), None, macros)
        profile_value = numeric(profile_index)
        if profile_value is None or profile_value < 0 or profile_value >= len(profiles):
            raise ParseError(f"behavior override rule #{order} has invalid profile index")
        override = {
            "order": order,
            "profileOrder": profile_value + 1,
            "profileIndex": profile_index,
            "kind": "behavior",
            "match": parse_match(entry[0], macros),
            "behavior": profiles[profile_value]["behavior"],
        }
        override["summary"] = match_summary(override["match"], macros, group_labels)
        rules.append(override)
    return rules


def parse_behavior_overrides(source: str, macros: dict[str, int], group_labels: dict[int, dict]) -> list[dict]:
    if behavior_source_uses_override_members(source):
        overrides = parse_behavior_override_profiles(source, macros)
        for override in overrides:
            mode = numeric(override["targetMode"])
            if mode == macros.get("OW_WILD_BEHAVIOR_OVERRIDE_TARGET_DISABLED", 0):
                override["summary"] = "Disabled"
            elif mode == macros.get("OW_WILD_BEHAVIOR_OVERRIDE_TARGET_MEMBERS", 1):
                count = len(override["members"])
                override["summary"] = f"{count} member{'s' if count != 1 else ''}"
            else:
                override["summary"] = match_summary(override["match"], macros, group_labels)
        return overrides
    try:
        return parse_behavior_override_rules(source, macros, group_labels)
    except ParseError:
        if "sOverworldWildBehaviorOverrideProfiles" in source or "sOverworldWildBehaviorOverrideRules" in source:
            raise

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
            elif len(entry) == 8:
                behavior = parse_behavior_override(entry[1:], macros)
            elif len(entry) == 14:
                behavior = parse_behavior_override(entry[1:], macros)
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


def sanitize_override_profile_name(name: str) -> str:
    if name is None:
        return ""
    return clean_token(str(name)).replace("*/", "* /")


def override_profile_name_comment(name: str, indent: str) -> str:
    cleaned = sanitize_override_profile_name(name)
    return f"{indent}/* profile: {cleaned} */\n" if cleaned else ""


def override_entry_prefix_start(text: str, segment_start: int, entry_start: int) -> int:
    segment = text[segment_start:entry_start]
    matches = list(OVERRIDE_PROFILE_NAME_RE.finditer(segment))
    if not matches:
        return entry_start
    match = matches[-1]
    if segment[match.end() :].strip():
        return entry_start
    return segment_start + match.start()


def override_entry_replacement_spans(text: str, container_span: tuple[int, int], entry_spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    result = []
    segment_start = container_span[0] + 1
    for entry_start, entry_end in entry_spans:
        result.append((override_entry_prefix_start(text, segment_start, entry_start), entry_end))
        segment_start = entry_end
    return result


def parse_override_profile_entry_names(raw_source: str) -> dict[int, str]:
    profile_span = initializer_brace_span(raw_source, "sOverworldWildBehaviorOverrideProfiles")
    profile_entry_spans = top_level_braced_spans(raw_source, profile_span)
    names: dict[int, str] = {}
    segment_start = profile_span[0] + 1
    for order, (entry_start, entry_end) in enumerate(profile_entry_spans, 1):
        segment = raw_source[segment_start:entry_start]
        matches = list(OVERRIDE_PROFILE_NAME_RE.finditer(segment))
        if matches:
            names[order] = sanitize_override_profile_name(matches[-1].group(1))
        segment_start = entry_end
    return names


def parse_override_profile_names(raw_source: str) -> dict[int, str]:
    if behavior_source_uses_override_members(raw_source):
        return parse_override_profile_entry_names(raw_source)
    try:
        profile_names = parse_override_profile_entry_names(raw_source)
        rule_entries = parse_initializer(extract_braced_initializer(raw_source, "sOverworldWildBehaviorOverrideRules"))
        names: dict[int, str] = {}
        for order, entry in enumerate(rule_entries, 1):
            if len(entry) != 2:
                continue
            profile_index = make_value(str(entry[1]), None, {})
            profile_order = numeric(profile_index)
            if profile_order is not None:
                name = profile_names.get(profile_order + 1, "")
                if name:
                    names[order] = name
        return names
    except ParseError:
        pass

    try:
        override_span = initializer_brace_span(raw_source, "sOverworldWildBehaviorOverrides")
        entry_spans = top_level_braced_spans(raw_source, override_span)
    except ParseError:
        return {}
    names: dict[int, str] = {}
    segment_start = override_span[0] + 1
    for order, (entry_start, entry_end) in enumerate(entry_spans, 1):
        segment = raw_source[segment_start:entry_start]
        matches = list(OVERRIDE_PROFILE_NAME_RE.finditer(segment))
        if matches:
            names[order] = sanitize_override_profile_name(matches[-1].group(1))
        segment_start = entry_end
    return names


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
    extra_raws = [extra["displayRaw"] for extra in (mask2, mask3) if extra["displayRaw"] != "0"]
    return {
        "mask": mask,
        "mask2": mask2,
        "mask3": mask3,
        "maskLabels": mask["labels"] + mask2["labels"] + mask3["labels"],
        "maskRaw": mask["displayRaw"] if not extra_raws else " / ".join([mask["displayRaw"], *extra_raws]),
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
    if chill_behavior == macros.get("OW_WILD_BEHAVIOR_KIND_WANDER"):
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
            primitives["chillTarget"] = make_value("OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER", "chillTarget", macros)
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
            primitives["attentiveTarget"] = make_value("OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER", "attentiveTarget", macros)
    elif active_behavior == macros.get("OW_WILD_BEHAVIOR_KIND_RAM"):
        primitives["activeReaction"] = make_value("OW_WILD_BEHAVIOR_REACTION_CONTACT", "activeReaction", macros)
        if numeric(primitives["attentiveTarget"]) == macros.get("OW_WILD_BEHAVIOR_TARGET_NONE"):
            primitives["attentiveTarget"] = make_value("OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER", "attentiveTarget", macros)
    elif active_behavior == macros.get("OW_WILD_BEHAVIOR_KIND_HEADBUTT_TREE_HOP"):
        primitives["activeReaction"] = make_value("OW_WILD_BEHAVIOR_REACTION_CONTACT", "activeReaction", macros)
        if numeric(primitives["attentiveTarget"]) == macros.get("OW_WILD_BEHAVIOR_TARGET_NONE"):
            primitives["attentiveTarget"] = make_value("OW_WILD_BEHAVIOR_TARGET_TREE_TOP", "attentiveTarget", macros)
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


def profile_option_symbol_allowed(field: str, symbol: str) -> bool:
    if symbol in PROFILE_OPTION_FIELD_EXCLUDED_RAWS.get(field, set()):
        return False
    return not any(symbol.endswith(suffix) for suffix in PROFILE_OPTION_EXCLUDED_SUFFIXES)


def profile_option_symbols_for_prefix(field: str, macros: dict[str, int]) -> list[str]:
    prefix = FIELD_PREFIXES.get(field)
    if not prefix:
        return []
    return sorted(
        (
            symbol
            for symbol in macros
            if symbol.startswith(prefix) and profile_option_symbol_allowed(field, symbol)
        ),
        key=lambda symbol: (macros.get(symbol, 0), symbol),
    )


def build_edit_options(macros: dict[str, int], class_profiles: list[dict[str, dict]]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for field in PROFILE_FIELDS:
        options: list[dict] = []
        seen: set[str] = set()
        if field in CANONICAL_PROFILE_FIELD_RAWS:
            for symbol in CANONICAL_PROFILE_FIELD_RAWS[field]:
                if symbol in macros and profile_option_symbol_allowed(field, symbol):
                    add_value_option(options, seen, symbol, field, macros)
            for symbol in profile_option_symbols_for_prefix(field, macros):
                add_value_option(options, seen, symbol, field, macros)
        elif field in FIELD_PREFIXES:
            for symbol in profile_option_symbols_for_prefix(field, macros):
                add_value_option(options, seen, symbol, field, macros)
        elif field in NUMERIC_PROFILE_FIELDS:
            for value in range(
                NUMERIC_PROFILE_FIELD_OPTION_MIN.get(field, 0),
                NUMERIC_PROFILE_FIELD_OPTION_MAX.get(field, 64) + 1,
            ):
                add_value_option(options, seen, str(value), field, macros)
        if field not in CANONICAL_PROFILE_FIELD_RAWS:
            for profile in class_profiles:
                add_value_option(options, seen, canonical_profile_value_raw(profile[field], field), field, macros)
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
    relative_fields = set(override.get("relativeFields") or [])
    at_least_fields = set(override.get("atLeastFields") or [])
    at_most_fields = set(override.get("atMostFields") or [])
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
        if field in relative_fields:
            before_numeric = numeric(before)
            delta = numeric(after)
            if before_numeric is None or delta is None:
                continue
            field_maximum = NUMERIC_PROFILE_FIELD_OPTION_MAX.get(field, 64)
            field_minimum = NUMERIC_PROFILE_FIELD_OPTION_MIN.get(field, 0)
            resolved = max(field_minimum, min(field_maximum, before_numeric + delta))
            after = make_value(str(resolved), field, {})
            after["label"] = str(resolved)
        elif field in at_least_fields or field in at_most_fields:
            before_numeric = numeric(before)
            threshold = numeric(after)
            if before_numeric is None or threshold is None:
                continue
            field_maximum = NUMERIC_PROFILE_FIELD_OPTION_MAX.get(field, 64)
            if field in at_least_fields:
                resolved = max(before_numeric, threshold)
            else:
                resolved = min(before_numeric, threshold)
            field_minimum = NUMERIC_PROFILE_FIELD_OPTION_MIN.get(field, 0)
            resolved = max(field_minimum, min(field_maximum, resolved))
            after = make_value(str(resolved), field, {})
            after["label"] = str(resolved)
        profile[field] = after
        changes.append(
            {
                "field": field,
                "label": FIELD_LABELS[field],
                "before": before,
                "after": after,
                "relative": field in relative_fields,
                "delta": copy.deepcopy(override["profile"][field]) if field in relative_fields else None,
                "operator": "atLeast" if field in at_least_fields else ("atMost" if field in at_most_fields else ("relative" if field in relative_fields else "absolute")),
                "operand": copy.deepcopy(override["profile"][field]) if field in at_least_fields or field in at_most_fields else None,
            }
        )
    return changes


def behavior_override_field_keys(behavior: dict) -> list[str]:
    fields = []
    seen = set()
    for bit in (
        behavior["mask"]["bits"]
        + behavior.get("mask2", {"bits": []})["bits"]
        + behavior.get("mask3", {"bits": []})["bits"]
    ):
        field = bit.get("field")
        if field and field not in seen:
            seen.add(field)
            fields.append(field)
    return fields


def behavior_override_relative_field_keys(behavior: dict) -> list[str]:
    return list(behavior.get("relativeFields") or [])


def behavior_override_at_least_field_keys(behavior: dict) -> list[str]:
    return list(behavior.get("atLeastFields") or [])


def behavior_override_at_most_field_keys(behavior: dict) -> list[str]:
    return list(behavior.get("atMostFields") or [])


def behavior_override_profile_signature(behavior: dict) -> list[tuple[str, str]]:
    return [
        (field, behavior["profile"][field]["raw"])
        for field in behavior_override_field_keys(behavior)
    ]


def validate_override_profile_groups(variable_overrides: list[dict], override_profile_names: dict[int, str]) -> None:
    groups: dict[str, dict] = {}
    for override in variable_overrides:
        order = override["order"]
        name = override_profile_names.get(order, "")
        if not name:
            continue
        signature = behavior_override_profile_signature(override["behavior"])
        if name not in groups:
            groups[name] = {"order": order, "signature": signature}
            continue
        expected = groups[name]["signature"]
        if signature == expected:
            continue

        # Old split data can contain multiple backend profiles for one displayed
        # override name. Save normalization redirects those rules to one profile,
        # so validation must tolerate the stale shape long enough to repair it.
        continue


def validate_behavior_data_override_profiles(raw_behavior_data: str, macros: dict[str, int], group_labels: dict[int, dict]) -> None:
    behavior_source = strip_c_comments(join_line_continuations(raw_behavior_data))
    variable_overrides = parse_behavior_overrides(behavior_source, macros, group_labels)
    override_profile_names = parse_override_profile_names(raw_behavior_data)
    validate_override_profile_groups(variable_overrides, override_profile_names)


def override_edit_profile(behavior: dict, macros: dict[str, int]) -> dict[str, dict]:
    active_fields = set(behavior_override_field_keys(behavior))
    profile = clone_profile(behavior["profile"])
    for field in PROFILE_FIELDS:
        if field not in active_fields:
            profile[field] = make_value("", field, macros)
    return profile


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
        mask2 = behavior.get("mask2", {"raw": "0", "displayRaw": "0"})
        mask3 = behavior.get("mask3", {"raw": "0", "displayRaw": "0"})
        mask2_raw = mask2.get("displayRaw") or mask2["raw"]
        mask3_raw = mask3.get("displayRaw") or mask3["raw"]
        extra_raws = [extra for extra in (mask2_raw, mask3_raw) if extra != "0"]
        mask_raw = behavior["mask"].get("displayRaw") or behavior["mask"]["raw"]
        raw = mask_raw if not extra_raws else " / ".join([mask_raw, *extra_raws])
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
        if (numeric(profile[max_field]) or 0) < (numeric(profile[min_field]) or 0):
            set_field(max_field, profile[min_field]["raw"])
    if (numeric(profile["spawnDestinationMinDistance"]) or 0) < 1:
        set_field("spawnDestinationMinDistance", "1")
    elif (numeric(profile["spawnDestinationMinDistance"]) or 0) > 8:
        set_field("spawnDestinationMinDistance", "8")
    if (numeric(profile["spawnDestinationMaxDistance"]) or 0) < 1:
        set_field("spawnDestinationMaxDistance", "1")
    elif (numeric(profile["spawnDestinationMaxDistance"]) or 0) > 8:
        set_field("spawnDestinationMaxDistance", "8")
    if (numeric(profile["spawnDestinationMaxDistance"]) or 0) < (numeric(profile["spawnDestinationMinDistance"]) or 0):
        set_field("spawnDestinationMaxDistance", profile["spawnDestinationMinDistance"]["raw"])
    if (numeric(profile["attentiveChaseBoostDistance"]) or 0) > 32:
        set_field("attentiveChaseBoostDistance", "32")
    if (numeric(profile["attentiveChaseBoostSpeed"]) or 0) > 4:
        set_field("attentiveChaseBoostSpeed", "4")
    if (numeric(profile["attentiveCircleRadius"]) or 0) > 8:
        set_field("attentiveCircleRadius", "8")
    for bool_field in (
        "attentiveContinueWhenArrived",
        "attentiveAvoidPreviousTile",
    ):
        if numeric(profile[bool_field]) not in {
            macros.get("OW_WILD_BEHAVIOR_BOOL_NO"),
            macros.get("OW_WILD_BEHAVIOR_BOOL_YES"),
        }:
            set_field(bool_field, "OW_WILD_BEHAVIOR_BOOL_NO")
    if numeric(profile["chillState"]) == macros.get("OW_WILD_BEHAVIOR_KIND_ASLEEP"):
        set_field("tiredState", "OW_WILD_BEHAVIOR_KIND_ASLEEP")
        set_field("stamina", "1")
        set_field("alertness", "0")
        set_field("alertChance", "0")
    elif numeric(profile["tiredState"]) == macros.get("OW_WILD_BEHAVIOR_KIND_ASLEEP"):
        set_field("stamina", "1")
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


def parse_baby_species_map() -> dict[str, str]:
    if not BABYMONS_SOURCE.exists():
        return {}
    text = strip_c_comments(BABYMONS_SOURCE.read_text())
    result: dict[str, str] = {}
    for species_symbol, baby_symbol in re.findall(
        r"\bbabymon\s+(SPECIES_[A-Z0-9_]+)\s*,\s*(SPECIES_[A-Z0-9_]+)",
        text,
    ):
        result[species_symbol] = baby_symbol
    return result


def parse_evolution_edges() -> list[tuple[str, str]]:
    if not EVODATA_SOURCE.exists():
        return []
    text = strip_c_comments(EVODATA_SOURCE.read_text())
    edges: list[tuple[str, str]] = []
    current: str | None = None
    for line in text.splitlines():
        data_match = re.match(r"\s*evodata\s+(SPECIES_[A-Z0-9_]+)\b", line)
        if data_match:
            current = data_match.group(1)
            continue
        if re.match(r"\s*terminateevodata\b", line):
            current = None
            continue
        evo_match = re.match(r"\s*evolution\s+[^,]+,\s*[^,]+,\s*(SPECIES_[A-Z0-9_]+)\b", line)
        if current and evo_match:
            target = evo_match.group(1)
            if target != "SPECIES_NONE":
                edges.append((current, target))
    return edges


def species_family_bases(options: list[dict], baby_by_symbol: dict[str, str], evolution_edges: list[tuple[str, str]]) -> dict[str, str]:
    symbols = {entry["symbol"] for entry in options if entry.get("symbol") and entry.get("symbol") != "SPECIES_NONE"}
    if not symbols:
        return {}
    parent = {symbol: symbol for symbol in symbols}
    value_by_symbol = {entry["symbol"]: entry.get("value", 10**9) for entry in options}

    def find(symbol: str) -> str:
        parent.setdefault(symbol, symbol)
        while parent[symbol] != symbol:
            parent[symbol] = parent[parent[symbol]]
            symbol = parent[symbol]
        return symbol

    def union(left: str, right: str) -> None:
        if left not in symbols or right not in symbols:
            return
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        if (value_by_symbol.get(left_root, 10**9), left_root) <= (value_by_symbol.get(right_root, 10**9), right_root):
            parent[right_root] = left_root
        else:
            parent[left_root] = right_root

    for entry in options:
        symbol = entry.get("symbol")
        base_symbol = entry.get("baseSymbol")
        if symbol and base_symbol:
            union(symbol, base_symbol)
    for species_symbol, baby_symbol in baby_by_symbol.items():
        union(species_symbol, baby_symbol)
    for source, target in evolution_edges:
        union(source, target)

    components: dict[str, list[str]] = {}
    for symbol in symbols:
        components.setdefault(find(symbol), []).append(symbol)
    result: dict[str, str] = {}
    for members in components.values():
        family_base = min(members, key=lambda symbol: (value_by_symbol.get(symbol, 10**9), symbol))
        for member in members:
            result[member] = family_base
    return result


def apply_species_family_metadata(options: list[dict], baby_by_symbol: dict[str, str], evolution_edges: list[tuple[str, str]]) -> None:
    family_base_by_symbol = species_family_bases(options, baby_by_symbol, evolution_edges)
    if not family_base_by_symbol:
        return
    options_by_symbol = {entry["symbol"]: entry for entry in options}
    for entry in options:
        family_base = family_base_by_symbol.get(entry["symbol"], entry.get("baseSymbol") or entry["symbol"])
        entry["familyBaseSymbol"] = family_base
        family_base_entry = options_by_symbol.get(family_base)
        if family_base_entry:
            entry["familyBaseName"] = family_base_entry.get("name", humanize_symbol(family_base, "SPECIES_"))


def build_evolution_families(options: list[dict]) -> list[dict]:
    family_members: dict[str, list[str]] = {}
    for entry in options:
        symbol = entry.get("symbol")
        if not symbol or symbol == "SPECIES_NONE":
            continue
        family_base = entry.get("familyBaseSymbol") or entry.get("baseSymbol") or symbol
        family_members.setdefault(family_base, []).append(symbol)
    options_by_symbol = {entry["symbol"]: entry for entry in options}
    return [
        {
            "baseSymbol": base_symbol,
            "baseName": options_by_symbol.get(base_symbol, {}).get("name", humanize_symbol(base_symbol, "SPECIES_")),
            "members": members,
        }
        for base_symbol, members in sorted(family_members.items(), key=lambda item: options_by_symbol.get(item[0], {}).get("value", 10**9))
    ]


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


def parse_lookup_encounter_area_maps(macros: dict[str, int] | None = None) -> dict[int, list[dict]]:
    if not ENCOUNTER_LOOKUP_SOURCE.exists():
        return {}
    try:
        initializer = parse_initializer(
            extract_braced_initializer(
                ENCOUNTER_LOOKUP_SOURCE.read_text(),
                "gOverworldWildEncounterLookupDataBlob",
            )
        )
    except ParseError:
        return {}
    if len(initializer) < 3 or not isinstance(initializer[1], list) or not isinstance(initializer[2], list):
        return {}
    map_symbols = initializer[1]
    data_ids = initializer[2]
    areas: dict[int, list[dict]] = {}
    for raw_map_symbol, raw_encounter_id in zip(map_symbols, data_ids):
        map_symbol = clean_token(str(raw_map_symbol))
        try:
            encounter_id = int(str(raw_encounter_id), 0)
        except ValueError:
            continue
        map_value = macros.get(map_symbol) if macros else None
        map_entry = {
            "symbol": map_symbol,
            "name": humanize_symbol(map_symbol, "MAP_"),
        }
        if map_value is not None:
            map_entry["value"] = map_value
        areas.setdefault(encounter_id, []).append(map_entry)
    return areas


def parse_encounter_area_maps(source: str, macros: dict[str, int] | None = None) -> dict[int, list[dict]]:
    try:
        entries = parse_initializer(extract_braced_initializer(source, "sOverworldWildEncounterAreas"))
    except ParseError:
        return parse_lookup_encounter_area_maps(macros)
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


def empty_route_encounter_overrides() -> dict:
    return {"version": 1, "routes": {}}


def normalize_route_encounter_overrides(raw: object) -> dict:
    if not isinstance(raw, dict):
        return empty_route_encounter_overrides()
    routes = raw.get("routes")
    if not isinstance(routes, dict):
        return empty_route_encounter_overrides()

    normalized_routes: dict[str, dict] = {}
    for raw_route_id, raw_override in routes.items():
        if not isinstance(raw_override, dict):
            continue
        try:
            route_key = str(int(raw_route_id))
        except Exception:
            continue
        species = clean_token(str(raw_override.get("species") or "")).upper()
        if not species:
            continue
        try:
            form = int(raw_override.get("form") or 0)
        except Exception:
            form = 0
        entries = []
        for raw_entry in raw_override.get("entries") or []:
            if not isinstance(raw_entry, dict):
                continue
            path = clean_token(str(raw_entry.get("path") or ""))
            form_path = clean_token(str(raw_entry.get("formPath") or ""))
            entry_species = clean_token(str(raw_entry.get("species") or "")).upper()
            if not path or not form_path or not entry_species:
                continue
            try:
                entry_form = int(raw_entry.get("form") or 0)
            except Exception:
                entry_form = 0
            entries.append(
                {
                    "path": path,
                    "formPath": form_path,
                    "species": entry_species,
                    "form": max(0, min(31, entry_form)),
                }
            )
        normalized_routes[route_key] = {
            "species": species,
            "form": max(0, min(31, form)),
            "entries": entries,
        }
    return {"version": 1, "routes": normalized_routes}


def read_route_encounter_overrides() -> dict:
    if not ENCOUNTER_OVERRIDES_SOURCE.exists():
        return empty_route_encounter_overrides()
    try:
        return normalize_route_encounter_overrides(json.loads(ENCOUNTER_OVERRIDES_SOURCE.read_text()))
    except Exception:
        return empty_route_encounter_overrides()


def write_route_encounter_overrides(overrides: dict) -> bool:
    normalized = normalize_route_encounter_overrides(overrides)
    if not normalized["routes"]:
        if ENCOUNTER_OVERRIDES_SOURCE.exists():
            ENCOUNTER_OVERRIDES_SOURCE.unlink()
            return True
        return False
    previous = read_route_encounter_overrides()
    if previous == normalized:
        return False
    ENCOUNTER_OVERRIDES_SOURCE.parent.mkdir(parents=True, exist_ok=True)
    ENCOUNTER_OVERRIDES_SOURCE.write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n")
    return True


def attach_route_encounter_overrides(routes: list[dict]) -> None:
    overrides_by_route = read_route_encounter_overrides().get("routes", {})
    for route in routes:
        route["encounterOverride"] = overrides_by_route.get(str(route["id"]))


def parse_route_changes_payload(payload: object) -> dict[int, dict[str, str]]:
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


def parse_route_override_save_payload(payload: object) -> dict[int, dict]:
    raw_overrides = payload.get("overrides", {}) if isinstance(payload, dict) else {}
    if raw_overrides in ({}, None):
        return {}
    if not isinstance(raw_overrides, dict):
        raise ValueError("encounter overrides must be an object")
    parsed: dict[int, dict] = {}
    for raw_route_id, raw_operation in raw_overrides.items():
        try:
            route_id = int(raw_route_id)
        except Exception as exc:
            raise ValueError(f"invalid override route id: {raw_route_id}") from exc
        if not isinstance(raw_operation, dict):
            raise ValueError(f"route {route_id} override changes must be an object")
        action = clean_token(str(raw_operation.get("action") or ""))
        if action == "clear":
            parsed[route_id] = {"action": "clear"}
            continue
        if action != "set":
            raise ValueError(f"route {route_id} override action is invalid")
        species = clean_token(str(raw_operation.get("species") or "")).upper()
        if not species:
            raise ValueError(f"route {route_id} override species is required")
        form = parse_int_range(str(raw_operation.get("form") or "0"), "form", 0, 31)
        entries = []
        for raw_entry in raw_operation.get("entries") or []:
            if not isinstance(raw_entry, dict):
                continue
            path = clean_token(str(raw_entry.get("path") or ""))
            form_path = clean_token(str(raw_entry.get("formPath") or ""))
            entry_species = clean_token(str(raw_entry.get("species") or "")).upper()
            entry_form = parse_int_range(str(raw_entry.get("form") or "0"), "form", 0, 31)
            if not path or not form_path or not entry_species:
                continue
            entries.append(
                {
                    "path": path,
                    "formPath": form_path,
                    "species": entry_species,
                    "form": entry_form,
                }
            )
        parsed[route_id] = {
            "action": "set",
            "species": species,
            "form": form,
            "entries": entries,
        }
    return parsed


def parse_encounter_save_payload(body: bytes) -> tuple[dict[int, dict[str, str]], dict[int, dict[str, dict]]]:
    try:
        payload = json.loads(body.decode())
    except Exception as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    return parse_route_changes_payload(payload), parse_route_override_save_payload(payload)


def parse_route_edit_payload(body: bytes) -> dict[int, dict[str, str]]:
    changes, _ = parse_encounter_save_payload(body)
    return changes


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

    expressions, species_order = parse_define_expressions(
        [path for path in DEFINE_SOURCE_FILES if path.exists()]
    )
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
    changes, override_changes = parse_encounter_save_payload(body)
    if not changes and not override_changes:
        return {"saved": False, "message": "No changes"}
    capabilities = source_capabilities()
    if not capabilities["routes"]["available"]:
        raise ValueError(capabilities["routes"]["reason"])
    if override_changes and not capabilities["routeOverrides"]["available"]:
        raise ValueError(capabilities["routeOverrides"]["reason"])

    raw_overlay = OVERLAY_SOURCE.read_text() if OVERLAY_SOURCE.exists() else ""
    source = strip_c_comments(join_line_continuations(raw_overlay))
    expressions, species_order = parse_define_expressions(
        [path for path in DEFINE_SOURCE_FILES if path.exists()]
    )
    macros = evaluate_defines(expressions)
    species = parse_species(expressions, macros, species_order)
    encounter_species_options = build_encounter_species_options(species, macros)
    species_by_symbol = {entry["symbol"]: entry for entry in encounter_species_options}
    valid_species = {entry["symbol"] for entry in encounter_species_options}
    valid_species.add("SPECIES_NONE")
    headbutt_by_map_id = (
        parse_headbutt_encounters(species_by_symbol, macros)
        if HEADBUTT_SOURCE.exists()
        else {}
    )
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

    saved_overrides = (
        read_route_encounter_overrides()
        if override_changes
        else empty_route_encounter_overrides()
    )
    if override_changes:
        for route_id, operation in override_changes.items():
            if route_id not in route_by_id:
                raise ValueError(f"unknown route id: {route_id}")
            if operation.get("action") == "clear":
                continue
            species = operation.get("species")
            if species not in valid_species or species == "SPECIES_NONE":
                raise ValueError(f"invalid override species: {species}")
            for entry in operation.get("entries") or []:
                species = entry.get("species")
                if species not in valid_species:
                    raise ValueError(f"invalid original override species: {species}")
                species_meta = path_index.get((route_id, entry.get("path")))
                form_meta = path_index.get((route_id, entry.get("formPath")))
                if species_meta is None or form_meta is None:
                    raise ValueError(f"unknown override edit path for {route_id}: {entry.get('path')}")

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

    headbutt_changed = False
    if pending_headbutt_by_line:
        if not HEADBUTT_SOURCE.exists():
            raise ValueError("Headbutt encounter sources are not installed in this workspace")
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

    override_routes = saved_overrides.setdefault("routes", {})
    for route_id, operation in override_changes.items():
        route_key = str(route_id)
        if operation.get("action") == "clear":
            override_routes.pop(route_key, None)
        else:
            override_routes[route_key] = {
                "species": operation["species"],
                "form": operation["form"],
                "entries": operation.get("entries") or [],
            }
    overrides_changed = write_route_encounter_overrides(saved_overrides) if override_changes else False

    changed = encounters_changed or headbutt_changed or overrides_changed
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
                "name": macro_label(symbol, value, None, macros),
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


def match_is_no_target_placeholder(match: dict, macros: dict[str, int]) -> bool:
    any_species = macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_SPECIES", macros.get("SPECIES_NONE", 0))
    return (
        numeric(match["species"]) == any_species
        and numeric(match["groupMask"]) == macros.get("OW_WILD_BEHAVIOR_GROUP_NONE", 0)
        and numeric(match["terrain"]) == macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_TERRAIN")
        and numeric(match["minLevel"]) == macros.get("OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY", 0)
        and numeric(match["maxLevel"]) == macros.get("OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY", 0)
        and numeric(match["shiny"]) == macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_SHINY")
        and numeric(match["behaviorClass"]) == OVERRIDE_PROFILE_NO_TARGET_CLASS_VALUE
    )


def match_summary(match: dict, macros: dict[str, int], group_labels: dict[int, dict]) -> str:
    if match_is_no_target_placeholder(match, macros):
        return "No target"
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


def behavior_override_applies(context: dict, override: dict, macros: dict[str, int]) -> bool:
    if "targetMode" not in override:
        return match_applies(context, override["match"], macros)
    mode = numeric(override["targetMode"])
    if mode == macros.get("OW_WILD_BEHAVIOR_OVERRIDE_TARGET_DISABLED", 0):
        return False
    if not match_applies(context, override["match"], macros):
        return False
    if mode == macros.get("OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL", 2):
        return True
    if mode != macros.get("OW_WILD_BEHAVIOR_OVERRIDE_TARGET_MEMBERS", 1):
        return False
    return any(numeric(member) == context["species"] for member in override.get("members", []))


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
        if behavior_override_applies(context, override, macros):
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
        "encounterLookup": str(ENCOUNTER_LOOKUP_SOURCE.relative_to(ROOT)),
        "encounterOverrides": str(ENCOUNTER_OVERRIDES_SOURCE.relative_to(ROOT)),
        "babymons": str(BABYMONS_SOURCE.relative_to(ROOT)),
    }


def source_capabilities() -> dict[str, dict]:
    """Describe independently usable viewer subsystems for this workspace.

    The Pokédex and encounter sources predate the optional overworld profile
    runtime.  Keep their availability independent so forks without that
    runtime can still use the parts of the workshop backed by their sources.
    """

    def capability(
        required: list[Path] | tuple[Path, ...],
        *,
        optional: list[Path] | tuple[Path, ...] = (),
        label: str,
    ) -> dict:
        missing = [
            str(path.relative_to(ROOT))
            for path in required
            if not path.exists()
        ]
        missing_optional = [
            str(path.relative_to(ROOT))
            for path in optional
            if not path.exists()
        ]
        available = not missing
        return {
            "available": available,
            "writable": available,
            "missingSources": missing,
            "missingOptionalSources": missing_optional,
            "reason": None if available else f"{label} sources are not installed in this workspace",
        }

    pokemon_required = (
        ROOT / "include/config.h",
        MONDATA_SOURCE,
        BABYMONS_SOURCE,
        EVODATA_SOURCE,
        ARMIPS_CONSTANTS,
        ARMIPS_CONFIG,
        ROOT / "asm/include/species.inc",
        ROOT / "asm/include/abilities.inc",
        ROOT / "asm/include/items.inc",
        ROOT / "asm/include/moves.inc",
        ROOT / "data/BaseExperienceTable.c",
        ROOT / "data/HiddenAbilityTable.c",
        ROOT / "data/learnsets/learnsets.json",
    )
    route_required = (
        ENCOUNTERS_SOURCE,
        SPECIES_HEADER,
        MAPS_HEADER,
        ARMIPS_SPECIES_INC,
        ARMIPS_CONSTANTS,
        ARMIPS_CONFIG,
    )
    profile_required = (
        OVERLAY_SOURCE,
        HELPER_SOURCE,
        BEHAVIOR_DATA_SOURCE,
        BEHAVIOR_DATA_HEADER,
        SPAWNS_PUBLIC_HEADER,
        SPAWNS_INTERNAL_HEADER,
    )
    spawn_required = tuple(
        dict.fromkeys(
            [Path(setting["source"]) for setting in SPAWN_SETTING_BY_SYMBOL.values()]
            + [SPECIES_HEADER, ARMIPS_SPECIES_INC, ARMIPS_CONSTANTS, ARMIPS_CONFIG]
        )
    )
    capabilities = {
        "pokemon": capability(
            pokemon_required,
            optional=(POKEGRA_MK, POKE_FORM_DATA),
            label="Pokémon editor",
        ),
        "routes": capability(
            route_required,
            optional=(HEADBUTT_SOURCE, ENCOUNTER_LOOKUP_SOURCE, ENCOUNTER_OVERRIDES_SOURCE),
            label="Route deck",
        ),
        "profiles": capability(profile_required, label="Profile deck"),
        "spawnSettings": capability(spawn_required, label="Overworld spawn settings"),
        "routeOverrides": capability(
            (OVERLAY_SOURCE, HELPER_SOURCE, BEHAVIOR_DATA_HEADER, ENCOUNTER_LOOKUP_SOURCE),
            optional=(ENCOUNTER_OVERRIDES_SOURCE,),
            label="Overworld route-only encounters",
        ),
    }
    if not capabilities["routes"]["available"]:
        capabilities["routeOverrides"].update(
            {
                "available": False,
                "writable": False,
                "reason": "Route-only encounters require an available Route deck",
            }
        )
    return capabilities


def profile_error_payload(exc: Exception | None) -> dict | None:
    if exc is None:
        return None
    message = str(exc).replace(f"{ROOT}{os.sep}", "").replace(str(ROOT), ".")
    return {
        "type": type(exc).__name__,
        "message": message,
    }


def build_route_only_data(
    profile_error: Exception | None = None,
    *,
    include_routes: bool | None = None,
    include_spawn_settings: bool | None = None,
) -> dict:
    raw_overlay = OVERLAY_SOURCE.read_text() if OVERLAY_SOURCE.exists() else ""
    source = strip_c_comments(join_line_continuations(raw_overlay))
    expressions, species_order = parse_define_expressions(
        [path for path in DEFINE_SOURCE_FILES if path.exists()]
    )
    macros = evaluate_defines(expressions)
    macros.update(
        evaluate_armips_equ(
            [path for path in (ARMIPS_CONFIG, ARMIPS_CONSTANTS) if path.exists()]
        )
    )
    terrain_values, destination_values = (
        parse_behavior_data_enums()
        if BEHAVIOR_DATA_HEADER.exists()
        else ({}, {})
    )
    macros.update(terrain_values)
    macros.update(destination_values)

    species = parse_species(expressions, macros, species_order)
    baby_by_symbol = parse_baby_species_map()
    evolution_edges = parse_evolution_edges()
    apply_species_type_metadata(species, parse_species_type_metadata(macros))
    icon_paths = cached_icon_paths()
    for entry in species:
        if entry["value"] in icon_paths:
            entry["iconUrl"] = f"/icons/{entry['value']}.png"
    species_by_symbol = {entry["symbol"]: entry for entry in species}
    apply_regional_form_metadata(species, species_by_symbol, macros)
    apply_species_family_metadata(species, baby_by_symbol, evolution_edges)
    species_by_value = {entry["value"]: entry for entry in species}
    species_options = build_encounter_species_options(species, macros)
    apply_species_family_metadata(species_options, baby_by_symbol, evolution_edges)
    encounter_species_by_symbol = {entry["symbol"]: entry for entry in species_options}
    capabilities = source_capabilities()
    if include_routes is None:
        include_routes = capabilities["routes"]["available"]
    if include_spawn_settings is None:
        include_spawn_settings = capabilities["spawnSettings"]["available"]
    headbutt_by_map_id = (
        parse_headbutt_encounters(encounter_species_by_symbol, macros)
        if include_routes and HEADBUTT_SOURCE.exists()
        else {}
    )
    routes = (
        parse_route_encounters(
            encounter_species_by_symbol,
            macros,
            parse_encounter_area_maps(source, macros),
            headbutt_by_map_id,
        )
        if include_routes and capabilities["routes"]["available"]
        else []
    )
    if routes and capabilities["routeOverrides"]["available"]:
        attach_route_encounter_overrides(routes)
    spawn_settings = (
        parse_spawn_settings(macros, encounter_species_by_symbol)
        if include_spawn_settings and capabilities["spawnSettings"]["available"]
        else []
    )
    profile_capability = dict(capabilities["profiles"])
    profile_capability.update(
        {
            "available": False,
            "writable": False,
            "reason": profile_capability["reason"] or "Profile deck sources could not be parsed",
        }
    )
    capabilities["profiles"] = profile_capability

    return {
        "generatedAt": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "source": data_source_metadata(),
        "capabilities": capabilities,
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
        "evolutionFamilies": build_evolution_families(species_options),
        "typeOptions": build_type_options(macros),
        "spawnSettings": spawn_settings,
        "routes": routes,
    }


def build_data(
    *,
    include_routes: bool | None = None,
    include_spawn_settings: bool | None = None,
) -> dict:
    capabilities = source_capabilities()
    if include_routes is None:
        include_routes = capabilities["routes"]["available"]
    if include_spawn_settings is None:
        include_spawn_settings = capabilities["spawnSettings"]["available"]
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
    override_profile_names = parse_override_profile_names(raw_behavior_data)
    validate_override_profile_groups(variable_overrides, override_profile_names)

    group_species = parse_group_species(source, macros)
    species = parse_species(expressions, macros, species_order)
    baby_by_symbol = parse_baby_species_map()
    evolution_edges = parse_evolution_edges()
    apply_species_type_metadata(species, parse_species_type_metadata(macros))
    icon_paths = cached_icon_paths()
    for entry in species:
        if entry["value"] in icon_paths:
            entry["iconUrl"] = f"/icons/{entry['value']}.png"
    species_by_symbol = {entry["symbol"]: entry for entry in species}
    apply_regional_form_metadata(species, species_by_symbol, macros)
    apply_species_family_metadata(species, baby_by_symbol, evolution_edges)
    species_by_value = {entry["value"]: entry for entry in species}
    species_options = build_encounter_species_options(species, macros)
    apply_species_family_metadata(species_options, baby_by_symbol, evolution_edges)
    encounter_species_by_symbol = {entry["symbol"]: entry for entry in species_options}
    headbutt_by_map_id = (
        parse_headbutt_encounters(encounter_species_by_symbol, macros)
        if include_routes and HEADBUTT_SOURCE.exists()
        else {}
    )
    routes = (
        parse_route_encounters(
            encounter_species_by_symbol,
            macros,
            parse_encounter_area_maps(source, macros),
            headbutt_by_map_id,
        )
        if include_routes and capabilities["routes"]["available"]
        else []
    )
    if routes and capabilities["routeOverrides"]["available"]:
        attach_route_encounter_overrides(routes)
    spawn_settings = (
        parse_spawn_settings(macros, encounter_species_by_symbol)
        if include_spawn_settings and capabilities["spawnSettings"]["available"]
        else []
    )

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
                "profile": profile_numeric_view(profile),
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
        runtime_owned = class_symbol_used_by_runtime(class_label["symbol"])
        classes.append(
            {
                "index": index,
                "symbol": class_label["symbol"],
                "name": class_label["name"],
                "canRename": index != default_class and not runtime_owned,
                "canDelete": index != default_class and not runtime_owned,
                "override": {"mask": parse_mask("0", macros), "profile": profile_numeric_view(class_profile)},
                "profile": profile_numeric_view(profile),
                "primitives": resolve_primitives(profile, primitive_maps, macros),
                "editProfile": profile_numeric_view(class_profile),
                "layers": layers,
                "classRules": targeting_rules,
                "classRuleCount": len(targeting_rules),
                "speciesCount": sum(1 for item in assignments if item["behaviorClass"]["value"] == index),
            }
        )

    for override in variable_overrides:
        order = override["order"]
        runtime_owned_override = order - 1 == macros.get("OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER_POKEMON", -1)
        override_name = override_profile_names.get(order, "")
        override_name = override_name or f"Override #{order}: {override['summary']}"
        matching_count = sum(
            1
            for item in assignments
            if any(hit["order"] == order for hit in (item.get("variableOverrideHits") or []))
        )
        member_symbols = list(override.get("memberSymbols") or [])
        override_profile = override_edit_profile(override["behavior"], macros)
        classes.append(
            {
                "index": f"override:{order}",
                "order": order,
                "orders": [order],
                "kind": "override",
                "isOverrideProfile": True,
                "symbol": f"OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_{order}",
                "name": override_name,
                "customName": override_profile_names.get(order, ""),
                "canRename": not runtime_owned_override,
                "canDelete": not runtime_owned_override,
                "relativeOverridesAllowed": True,
                "numericOverrideOperatorsAllowed": True,
                "override": override["behavior"],
                "profile": profile_numeric_view(override_profile),
                "primitives": {},
                "editProfile": profile_numeric_view(override_profile),
                "layers": [
                    {
                        "kind": "behaviorOverride",
                        "label": f"Override profile #{order}",
                        "changes": [],
                        "mask": behavior_override_mask_summary(override["behavior"]),
                    }
                ],
                "match": override["match"],
                "members": [species_by_symbol[symbol] for symbol in member_symbols if symbol in species_by_symbol],
                "memberSymbols": member_symbols,
                "targetMode": override.get("targetMode"),
                "summary": override["summary"],
                "classRules": [],
                "classRuleCount": 0,
                "speciesCount": matching_count,
            }
        )

    return {
        "generatedAt": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "source": data_source_metadata(),
        "capabilities": capabilities,
        "profilesAvailable": True,
        "profileError": None,
        "fields": [
            {"key": field, "label": FIELD_LABELS[field], "unit": FIELD_UNITS.get(field, "")}
            for field in PROFILE_FIELDS
        ],
        "overrideFieldKeys": sorted(OVERRIDE_SYMBOL_BY_FIELD),
        "numericProfileFieldKeys": sorted(NUMERIC_PROFILE_FIELDS),
        "relativeOverrideFieldKeys": sorted(RELATIVE_OVERRIDE_PROFILE_FIELDS),
        "numericOverrideOperatorFieldKeys": sorted(RELATIVE_OVERRIDE_PROFILE_FIELDS),
        "boundedOverrideOperatorFieldKeys": sorted(BOUNDED_OVERRIDE_PROFILE_FIELDS),
        "numericOverrideOperandMaximums": {
            field: NUMERIC_PROFILE_FIELD_OPTION_MAX.get(field, 64)
            for field in sorted(RELATIVE_OVERRIDE_PROFILE_FIELDS)
        },
        "numericOverrideOperandMinimums": {
            field: 1
            for field in sorted(MOVEMENT_SPEED_FIELDS)
        },
        "relativeOverrideDeltaRange": {
            "min": RELATIVE_OVERRIDE_DELTA_MIN,
            "max": RELATIVE_OVERRIDE_DELTA_MAX,
        },
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
        "defaultProfile": profile_numeric_view(default_profile),
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
        "evolutionFamilies": build_evolution_families(species_options),
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
    with MACRO_LABEL_CACHE_LOCK:
        MACRO_LABEL_CACHES.clear()


def build_workspace_data() -> dict:
    """Assemble independently optional profile, route, and spawn datasets."""

    capabilities = source_capabilities()
    profile_error: Exception | None = None
    payload: dict | None = None
    if capabilities["profiles"]["available"]:
        try:
            payload = build_data(
                include_routes=False,
                include_spawn_settings=False,
            )
        except Exception as exc:
            profile_error = exc
    else:
        profile_error = RuntimeError(capabilities["profiles"]["reason"])

    if payload is None:
        payload = build_route_only_data(
            profile_error,
            include_routes=False,
            include_spawn_settings=False,
        )

    assembled_capabilities = {
        key: dict(value) for key, value in payload["capabilities"].items()
    }

    if capabilities["routes"]["available"]:
        try:
            route_payload = build_route_only_data(
                profile_error,
                include_routes=True,
                include_spawn_settings=False,
            )
            payload["routes"] = route_payload["routes"]
            payload["counts"]["routes"] = len(route_payload["routes"])
            assembled_capabilities["routes"] = route_payload["capabilities"]["routes"]
            assembled_capabilities["routeOverrides"] = route_payload["capabilities"]["routeOverrides"]
        except Exception as exc:
            assembled_capabilities["routes"] = {
                **capabilities["routes"],
                "available": False,
                "writable": False,
                "reason": "Route deck sources could not be parsed",
            }
            assembled_capabilities["routeOverrides"] = {
                **capabilities["routeOverrides"],
                "available": False,
                "writable": False,
                "reason": "Route-only encounters require an available Route deck",
            }
            payload["routeError"] = profile_error_payload(exc)

    if capabilities["spawnSettings"]["available"]:
        try:
            spawn_payload = build_route_only_data(
                profile_error,
                include_routes=False,
                include_spawn_settings=True,
            )
            payload["spawnSettings"] = spawn_payload["spawnSettings"]
            assembled_capabilities["spawnSettings"] = spawn_payload["capabilities"]["spawnSettings"]
        except Exception as exc:
            assembled_capabilities["spawnSettings"] = {
                **capabilities["spawnSettings"],
                "available": False,
                "writable": False,
                "reason": "Overworld spawn settings could not be parsed",
            }
            payload["spawnSettingsError"] = profile_error_payload(exc)

    payload["capabilities"] = assembled_capabilities
    return payload


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
        payload = build_workspace_data()
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


def override_profile_storage_raws(raws: dict[str, str]) -> dict[str, str]:
    """Make numeric operator storage explicit and reviewable in C initializers."""
    result = {}
    for field, raw in raws.items():
        if is_relative_override_raw(field, raw):
            result[field] = f"OW_WILD_BEHAVIOR_RELATIVE({int(raw, 10):+d})"
        elif is_at_least_override_raw(field, raw):
            result[field] = f"OW_WILD_BEHAVIOR_AT_LEAST({int(raw[2:], 10)})"
        elif is_at_most_override_raw(field, raw):
            result[field] = f"OW_WILD_BEHAVIOR_AT_MOST({int(raw[2:], 10)})"
        else:
            result[field] = raw
    return result


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
    return {field: canonical_profile_value_raw(profile[field], field) for field in PROFILE_FIELDS}


def numeric_raw(raw: str, field: str, macros: dict[str, int]) -> int | None:
    return make_value(raw, field, macros)["value"]


def valid_change_options(macros: dict[str, int], class_profiles: list[dict[str, dict]]) -> dict[str, set[str]]:
    options = {
        field: {option["raw"] for option in options}
        for field, options in build_edit_options(macros, class_profiles).items()
    }
    for profile in class_profiles:
        for field in PROFILE_FIELDS:
            value = profile[field]
            if value.get("raw") and value.get("value") is not None:
                options[field].add(canonical_profile_value_raw(value, field))
    # Movement Chain pause reuses ramMaxSpeed as a frame count. The visible RAM
    # controls stay capped as speeds, but saving must accept Chain frame values.
    options["ramMaxSpeed"].update(str(value) for value in range(0, 256))
    return options


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
    if action not in {"create", "duplicate", "rename", "delete"}:
        raise ValueError("profile action must be create, duplicate, rename, or delete")
    result = {"action": action}
    if action in {"duplicate", "rename", "delete"}:
        try:
            result["classIndex"] = int(payload.get("classIndex"))
        except Exception as exc:
            raise ValueError(f"invalid class index: {payload.get('classIndex')}") from exc
    if action in {"create", "duplicate", "rename"}:
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


def replace_class_define_block(raw_source: str, symbols: list[str], old_count: int | None = None) -> str:
    entries = class_define_entries(raw_source)
    if not entries:
        raise ParseError("could not find behavior class defines")
    replace_count = old_count if old_count is not None else len(symbols)
    if len(entries) < replace_count:
        raise ParseError("fewer behavior class defines than expected")
    values = [entry["value"] for entry in entries[:replace_count]]
    if values != list(range(replace_count)):
        raise ParseError("behavior class defines must be consecutive from zero")
    block_start = entries[0]["lineStart"]
    block_end = entries[replace_count - 1]["lineEnd"]
    block_text = raw_source[block_start:block_end]
    for line in block_text.splitlines():
        stripped = line.strip()
        if stripped and not re.fullmatch(r"#\s*define\s+OW_WILD_BEHAVIOR_CLASS_[A-Za-z0-9_]+\s+[0-9]+", stripped):
            raise ParseError("behavior class define block contains non-class defines")
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
    count_defines = dict(OWBD_COUNT_DEFINES)
    if behavior_source_uses_override_members(source):
        count_defines.update(
            {
                "OWBD_OVERRIDE_PROFILE_COUNT": "sOverworldWildBehaviorOverrideProfiles",
                "OWBD_OVERRIDE_MEMBER_COUNT": "sOverworldWildBehaviorOverrideMembers",
            }
        )
    elif "sOverworldWildBehaviorOverrideRules" in raw_source:
        count_defines.update(
            {
                "OWBD_OVERRIDE_PROFILE_COUNT": "sOverworldWildBehaviorOverrideProfiles",
                "OWBD_OVERRIDE_RULE_COUNT": "sOverworldWildBehaviorOverrideRules",
            }
        )
    else:
        count_defines["OWBD_OVERRIDE_COUNT"] = "sOverworldWildBehaviorOverrides"
    counts = {}
    for define, initializer_name in count_defines.items():
        entries = parse_initializer(extract_braced_initializer(source, initializer_name))
        counts[define] = len(entries)
    return counts


def rewrite_behavior_blob_count_defines(raw_header: str, counts: dict[str, int]) -> str:
    updated_header = raw_header
    for define, count in counts.items():
        updated_header = replace_define_value(updated_header, define, count)
    return updated_header


def consolidate_named_override_profiles(raw_source: str, preferred_profile_orders: set[int] | None = None) -> str:
    if (
        "sOverworldWildBehaviorOverrideProfiles" not in raw_source
        or "sOverworldWildBehaviorOverrideRules" not in raw_source
    ):
        return raw_source

    profile_names = parse_override_profile_entry_names(raw_source)
    duplicate_orders_by_name: dict[str, list[int]] = {}
    for order, name in profile_names.items():
        if name:
            duplicate_orders_by_name.setdefault(name, []).append(order)
    duplicate_orders_by_name = {
        name: orders
        for name, orders in duplicate_orders_by_name.items()
        if len(orders) > 1
    }
    if not duplicate_orders_by_name:
        return raw_source

    preferred_profile_orders = preferred_profile_orders or set()
    behavior_source = strip_c_comments(join_line_continuations(raw_source))
    expressions, _ = parse_define_expressions(DEFINE_SOURCE_FILES)
    macros = evaluate_defines(expressions)
    macros.update(evaluate_armips_equ([ARMIPS_CONFIG, ARMIPS_CONSTANTS]))
    terrain_values, destination_values = parse_behavior_data_enums()
    macros.update(terrain_values)
    macros.update(destination_values)
    group_labels = invert_labels(macros, GROUP_PREFIX)

    backend_profiles = parse_behavior_override_profiles(behavior_source, macros)
    existing_overrides = parse_behavior_overrides(behavior_source, macros, group_labels)
    profiles_model = [
        {
            "behavior": profile["behavior"],
            "name": profile_names.get(profile["order"], ""),
        }
        for profile in backend_profiles
    ]
    rules_model = [
        {
            "match": raw_match_values(override["match"]),
            "profileOrder": override["profileOrder"],
            "removed": False,
        }
        for override in existing_overrides
    ]

    canonical_order_by_name: dict[str, int] = {}
    for name, orders in duplicate_orders_by_name.items():
        preferred = next((order for order in orders if order in preferred_profile_orders), None)
        if preferred is not None:
            canonical_order_by_name[name] = preferred
            continue
        referenced = next(
            (
                rule["profileOrder"]
                for rule in rules_model
                if rule.get("profileOrder") in orders and not rule.get("removed")
            ),
            None,
        )
        canonical_order_by_name[name] = referenced if referenced is not None else orders[0]

    for rule in rules_model:
        profile_order = rule["profileOrder"]
        if profile_order < 1 or profile_order > len(profiles_model):
            continue
        name = profiles_model[profile_order - 1].get("name", "")
        canonical_order = canonical_order_by_name.get(name)
        if canonical_order is not None:
            rule["profileOrder"] = canonical_order

    kept_profile_orders = [
        order
        for order, profile in enumerate(profiles_model, 1)
        if canonical_order_by_name.get(profile.get("name", ""), order) == order
    ]
    profile_index_map = {
        profile_order: index
        for index, profile_order in enumerate(kept_profile_orders)
    }
    kept_profiles = [profiles_model[profile_order - 1] for profile_order in kept_profile_orders]

    profile_span = initializer_brace_span(raw_source, "sOverworldWildBehaviorOverrideProfiles")
    rule_span = initializer_brace_span(raw_source, "sOverworldWildBehaviorOverrideRules")
    profile_indent = line_indent_before(raw_source, profile_span[0])
    rule_indent = line_indent_before(raw_source, rule_span[0])
    profile_entry_indent = profile_indent + "    "
    rule_entry_indent = rule_indent + "    "
    profile_entries = ",\n".join(
        format_behavior_override_profile(
            set(behavior_override_field_keys(profile["behavior"])),
            raw_values(profile["behavior"]["profile"]),
            profile_entry_indent,
            profile["name"],
            relative_fields=set(behavior_override_relative_field_keys(profile["behavior"])),
            at_least_fields=set(behavior_override_at_least_field_keys(profile["behavior"])),
            at_most_fields=set(behavior_override_at_most_field_keys(profile["behavior"])),
        )
        for profile in kept_profiles
    )
    rule_entries = ",\n".join(
        format_behavior_override_profile_rule(
            rule["match"],
            profile_index_map[rule["profileOrder"]],
            rule_entry_indent,
        )
        for rule in rules_model
        if not rule["removed"]
    )

    updated_source = raw_source
    for start, end, replacement in sorted(
        [
            (profile_span[0], profile_span[1], f"{{\n{profile_entries}\n{profile_indent}}}"),
            (rule_span[0], rule_span[1], f"{{\n{rule_entries}\n{rule_indent}}}"),
        ],
        key=lambda item: item[0],
        reverse=True,
    ):
        updated_source = updated_source[:start] + replacement + updated_source[end:]
    return updated_source


def write_behavior_data_source(raw_source: str, raw_header: str | None = None) -> None:
    raw_source = consolidate_named_override_profiles(raw_source)
    counts = behavior_blob_counts(raw_source)
    if raw_header is None:
        raw_header = BEHAVIOR_DATA_HEADER.read_text()
    if "OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER_POKEMON" in raw_header:
        follower_orders = [
            order
            for order, name in parse_override_profile_entry_names(raw_source).items()
            if name.casefold() == "follower pokemon"
        ]
        if len(follower_orders) != 1:
            raise ParseError("runtime-owned Follower Pokemon override must exist exactly once")
        raw_header = replace_define_value(
            raw_header,
            "OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER_POKEMON",
            follower_orders[0] - 1,
        )
    BEHAVIOR_DATA_SOURCE.write_text(raw_source)
    BEHAVIOR_DATA_HEADER.write_text(rewrite_behavior_blob_count_defines(raw_header, counts))
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
    if symbol in RUNTIME_OWNED_CLASS_SYMBOLS:
        return True
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
    raw_behavior_header = BEHAVIOR_DATA_HEADER.read_text()
    behavior_source = strip_c_comments(join_line_continuations(raw_behavior_data))
    expressions, species_order = parse_define_expressions(DEFINE_SOURCE_FILES)
    macros = evaluate_defines(expressions)
    macros.update(evaluate_armips_equ([ARMIPS_CONFIG, ARMIPS_CONSTANTS]))
    class_profiles = [
        parse_profile(entry, macros)
        for entry in parse_initializer(extract_braced_initializer(behavior_source, "sOverworldWildBehaviorClassProfiles"))
    ]
    class_entries = class_define_entries(raw_behavior_header)
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
        updated_header = replace_class_define_block(raw_behavior_header, class_symbols + [new_symbol], len(class_profiles))
        updated_source = append_profile_initializer(raw_behavior_data, raw_values(class_profiles[default_class]))
        write_behavior_data_source(updated_source, updated_header)
        membership_result = None
        if pokemon:
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
    if action == "duplicate":
        new_symbol = sanitize_class_symbol(change["name"], set(class_symbols))
        new_index = len(class_profiles)
        updated_header = replace_class_define_block(raw_behavior_header, class_symbols + [new_symbol], len(class_profiles))
        updated_source = append_profile_initializer(raw_behavior_data, raw_values(class_profiles[class_index]))
        write_behavior_data_source(updated_source, updated_header)
        return {
            "saved": True,
            "message": f"Duplicated {humanize_symbol(old_symbol, CLASS_PREFIX)} as {humanize_symbol(new_symbol, CLASS_PREFIX)}",
            "classIndex": new_index,
            "symbol": new_symbol,
        }

    if action == "rename":
        if class_index == default_class:
            raise ValueError("Default profile cannot be renamed")
        if class_symbol_used_by_runtime(old_symbol):
            raise ValueError(f"{humanize_symbol(old_symbol, CLASS_PREFIX)} is referenced by behavior runtime code and cannot be renamed safely")
        new_symbol = sanitize_class_symbol(change["name"], set(class_symbols), old_symbol)
        if new_symbol == old_symbol:
            return {"saved": False, "message": "No code changes needed", "classIndex": class_index, "symbol": old_symbol}
        class_symbols[class_index] = new_symbol
        updated_header = replace_class_define_block(raw_behavior_header, class_symbols, len(class_profiles))
        updated_source = re.sub(rf"\b{re.escape(old_symbol)}\b", new_symbol, raw_behavior_data)
        write_behavior_data_source(updated_source, updated_header)
        return {"saved": True, "message": f"Renamed profile to {humanize_symbol(new_symbol, CLASS_PREFIX)}", "classIndex": class_index, "symbol": new_symbol}

    if class_index == default_class:
        raise ValueError("Default profile cannot be deleted")
    if class_symbol_used_by_runtime(old_symbol):
        raise ValueError(f"{humanize_symbol(old_symbol, CLASS_PREFIX)} is still referenced by behavior runtime code and cannot be deleted safely")
    class_symbols.pop(class_index)
    updated_source = re.sub(rf"\b{re.escape(old_symbol)}\b", "OW_WILD_BEHAVIOR_CLASS_DEFAULT", raw_behavior_data)
    updated_header = replace_class_define_block(raw_behavior_header, class_symbols, len(class_profiles))
    updated_source = remove_profile_initializer(updated_source, class_index, len(class_profiles))
    write_behavior_data_source(updated_source, updated_header)
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
    raw_edits = {}
    raw_renames = {}
    raw_reorder = []
    raw_match_replacements = {}
    raw_target_replacements = {}
    if isinstance(changes, list):
        raw_adds = changes
        raw_removes = []
    elif isinstance(changes, dict):
        raw_adds = changes.get("add", [])
        raw_removes = changes.get("remove", [])
        raw_edits = changes.get("edit", {})
        raw_renames = changes.get("rename", {})
        raw_reorder = changes.get("reorder", [])
        raw_match_replacements = changes.get("replaceMatches", {})
        raw_target_replacements = changes.get("replaceTargets", {})
    else:
        raise ValueError("missing changes list")
    if not isinstance(raw_adds, list):
        raise ValueError("override additions must be a list")
    if not isinstance(raw_removes, list):
        raise ValueError("override removals must be a list")
    if not isinstance(raw_edits, dict):
        raise ValueError("override edits must be an object")
    if not isinstance(raw_renames, dict):
        raise ValueError("override renames must be an object")
    if not isinstance(raw_reorder, list):
        raise ValueError("override reorder must be a list")
    if not isinstance(raw_match_replacements, dict):
        raise ValueError("override match replacements must be an object")
    if not isinstance(raw_target_replacements, dict):
        raise ValueError("override target replacements must be an object")

    def parse_raw_match(raw_match: dict) -> dict[str, str]:
        match_raws = default_behavior_match_raws()
        for match_field in MATCH_FIELDS:
            if match_field in raw_match:
                match_raws[match_field] = clean_token(str(raw_match[match_field]))
        return match_raws

    def target_from_matches(matches: list[dict[str, str]], label: str) -> dict:
        members = []
        shared_match = None
        for match in matches:
            if match.get("behaviorClass") == "0xFE":
                continue
            member = match.get("species", "")
            condition = dict(match)
            condition["species"] = "OW_WILD_BEHAVIOR_MATCH_ANY_SPECIES"
            if shared_match is None:
                shared_match = condition
            elif condition != shared_match:
                raise ValueError(f"{label} has different per-Pokemon conditions and cannot become one profile target")
            if member not in {"", "SPECIES_NONE", "OW_WILD_BEHAVIOR_MATCH_ANY_SPECIES"} and member not in members:
                members.append(member)
        shared_match = shared_match or default_behavior_match_raws()
        default_match = default_behavior_match_raws()
        contextual = any(shared_match[field] != default_match[field] for field in MATCH_FIELDS if field != "species")
        mode = "members" if members else ("all" if contextual else "disabled")
        return {"members": members, "match": shared_match, "targetMode": mode}

    def parse_target(raw_target: dict, label: str) -> dict:
        raw_members = raw_target.get("members", [])
        if not isinstance(raw_members, list):
            raise ValueError(f"{label} members must be a list")
        members = []
        for raw_member in raw_members:
            member = clean_token(str(raw_member)).upper()
            if member and member not in members:
                members.append(member)
        match = parse_raw_match(raw_target.get("match") if isinstance(raw_target.get("match"), dict) else {})
        match["species"] = "OW_WILD_BEHAVIOR_MATCH_ANY_SPECIES"
        raw_mode = clean_token(str(raw_target.get("targetMode", "members" if members else "disabled"))).lower()
        if raw_mode not in {"disabled", "members", "all"}:
            raise ValueError(f"{label} has invalid target mode")
        if raw_mode == "members" and not members:
            raw_mode = "disabled"
        return {"members": members, "match": match, "targetMode": raw_mode}

    parsed_adds = []
    for index, raw_change in enumerate(raw_adds, 1):
        if not isinstance(raw_change, dict):
            raise ValueError(f"override {index} must be an object")
        fields = {}
        if isinstance(raw_change.get("fields"), dict):
            fields = {
                clean_token(str(field)): clean_token(str(raw))
                for field, raw in raw_change["fields"].items()
            }
        else:
            field = clean_token(str(raw_change.get("field", "")))
            raw = clean_token(str(raw_change.get("raw", "")))
            if field:
                fields[field] = raw
        if isinstance(raw_change.get("target"), dict):
            target = parse_target(raw_change["target"], f"override {index}")
        else:
            raw_matches = raw_change.get("matches")
            if isinstance(raw_matches, list):
                matches = [parse_raw_match(raw_match) for raw_match in raw_matches if isinstance(raw_match, dict)]
            else:
                raw_match = raw_change.get("match") if isinstance(raw_change.get("match"), dict) else {}
                matches = [parse_raw_match(raw_match)]
            target = target_from_matches(matches, f"override {index}")
        parsed_adds.append({
            "fields": fields,
            "target": target,
            "name": sanitize_override_profile_name(raw_change.get("name", "")),
        })

    parsed_edits = {}
    for raw_order, raw_fields in raw_edits.items():
        try:
            order = int(raw_order)
        except Exception as exc:
            raise ValueError(f"invalid override edit order: {raw_order}") from exc
        if not isinstance(raw_fields, dict):
            raise ValueError(f"override edit {order} fields must be an object")
        parsed_edits[order] = {
            clean_token(str(field)): clean_token(str(raw))
            for field, raw in raw_fields.items()
        }

    parsed_renames = {}
    for raw_order, raw_name in raw_renames.items():
        try:
            order = int(raw_order)
        except Exception as exc:
            raise ValueError(f"invalid override rename order: {raw_order}") from exc
        parsed_renames[order] = sanitize_override_profile_name(raw_name)

    parsed_removes = []
    for raw_order in raw_removes:
        try:
            order = int(raw_order)
        except Exception as exc:
            raise ValueError(f"invalid override removal order: {raw_order}") from exc
        parsed_removes.append(order)

    parsed_reorder = []
    seen_reorder_orders = set()
    for group_index, raw_group in enumerate(raw_reorder, 1):
        raw_orders = raw_group if isinstance(raw_group, list) else [raw_group]
        group = []
        for raw_order in raw_orders:
            try:
                order = int(raw_order)
            except Exception as exc:
                raise ValueError(f"invalid override reorder order: {raw_order}") from exc
            if order in seen_reorder_orders:
                raise ValueError(f"duplicate override reorder order: {order}")
            seen_reorder_orders.add(order)
            group.append(order)
        if group:
            parsed_reorder.append(group)

    parsed_match_replacements = {}
    for raw_order, raw_matches in raw_match_replacements.items():
        try:
            order = int(raw_order)
        except Exception as exc:
            raise ValueError(f"invalid override match replacement order: {raw_order}") from exc
        if not isinstance(raw_matches, list):
            raise ValueError(f"override match replacement {order} must be a list")
        matches = [parse_raw_match(raw_match) for raw_match in raw_matches if isinstance(raw_match, dict)]
        if len(matches) != len(raw_matches) or not matches:
            raise ValueError(f"override match replacement {order} must include valid match objects")
        parsed_match_replacements[order] = matches

    parsed_target_replacements = {}
    for raw_order, raw_target in raw_target_replacements.items():
        try:
            order = int(raw_order)
        except Exception as exc:
            raise ValueError(f"invalid override target replacement order: {raw_order}") from exc
        if not isinstance(raw_target, dict):
            raise ValueError(f"override target replacement {order} must be an object")
        parsed_target_replacements[order] = parse_target(raw_target, f"override {order}")
    for order, matches in parsed_match_replacements.items():
        if order in parsed_target_replacements:
            raise ValueError(f"override {order} cannot replace matches and target together")
        parsed_target_replacements[order] = target_from_matches(matches, f"override {order}")

    return {
        "add": parsed_adds,
        "edit": parsed_edits,
        "rename": parsed_renames,
        "remove": parsed_removes,
        "reorder": parsed_reorder,
        "replaceMatches": parsed_match_replacements,
        "replaceTargets": parsed_target_replacements,
    }


def canonicalize_named_override_profile_rules(
    profiles_model: list[dict],
    rules_model: list[dict],
    preferred_profile_orders: set[int] | None = None,
) -> None:
    preferred_profile_orders = preferred_profile_orders or set()
    canonical_profile_order_by_name: dict[str, int] = {}
    for rule in rules_model:
        if rule.get("removed"):
            continue
        profile_order = rule.get("profileOrder")
        if not isinstance(profile_order, int) or profile_order < 1 or profile_order > len(profiles_model):
            continue
        name = profiles_model[profile_order - 1].get("name", "")
        if not name:
            continue
        canonical_profile_order = canonical_profile_order_by_name.get(name)
        if canonical_profile_order is None or (
            profile_order in preferred_profile_orders
            and canonical_profile_order not in preferred_profile_orders
        ):
            canonical_profile_order_by_name[name] = profile_order

    for rule in rules_model:
        if rule.get("removed"):
            continue
        profile_order = rule.get("profileOrder")
        if not isinstance(profile_order, int) or profile_order < 1 or profile_order > len(profiles_model):
            continue
        name = profiles_model[profile_order - 1].get("name", "")
        if name:
            rule["profileOrder"] = canonical_profile_order_by_name.get(name, profile_order)


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
    name: str = "",
    relative_fields: set[str] | None = None,
    at_least_fields: set[str] | None = None,
    at_most_fields: set[str] | None = None,
) -> str:
    inner = indent + "    "
    relative_fields = relative_fields or set()
    at_least_fields = at_least_fields or set()
    at_most_fields = at_most_fields or set()
    storage_raws = override_profile_storage_raws(profile_raws)
    return override_profile_name_comment(name, indent) + (
        f"{indent}{{\n"
        f"{inner}{format_match_initializer(match_raws, inner)},\n"
        f"{inner}{format_mask_expression(mask_fields, inner, 1)},\n"
        f"{inner}{format_mask_expression(mask_fields, inner, 2)},\n"
        f"{inner}{format_mask_expression(mask_fields, inner, 3)},\n"
        f"{inner}{format_profile_initializer(storage_raws, inner)},\n"
        f"{inner}{format_mask_expression(relative_fields, inner, 1)},\n"
        f"{inner}{format_mask_expression(relative_fields, inner, 2)},\n"
        f"{inner}{format_mask_expression(relative_fields, inner, 3)},\n"
        f"{inner}{format_mask_expression(at_least_fields, inner, 1)},\n"
        f"{inner}{format_mask_expression(at_least_fields, inner, 2)},\n"
        f"{inner}{format_mask_expression(at_least_fields, inner, 3)},\n"
        f"{inner}{format_mask_expression(at_most_fields, inner, 1)},\n"
        f"{inner}{format_mask_expression(at_most_fields, inner, 2)},\n"
        f"{inner}{format_mask_expression(at_most_fields, inner, 3)},\n"
        f"{indent}}}"
    )


def format_behavior_override_profile(
    mask_fields: set[str],
    profile_raws: dict[str, str],
    indent: str = "    ",
    name: str = "",
    relative_fields: set[str] | None = None,
    at_least_fields: set[str] | None = None,
    at_most_fields: set[str] | None = None,
) -> str:
    inner = indent + "    "
    relative_fields = relative_fields or set()
    at_least_fields = at_least_fields or set()
    at_most_fields = at_most_fields or set()
    storage_raws = override_profile_storage_raws(profile_raws)
    return override_profile_name_comment(name, indent) + (
        f"{indent}{{\n"
        f"{inner}{format_mask_expression(mask_fields, inner, 1)},\n"
        f"{inner}{format_mask_expression(mask_fields, inner, 2)},\n"
        f"{inner}{format_mask_expression(mask_fields, inner, 3)},\n"
        f"{inner}{format_profile_initializer(storage_raws, inner)},\n"
        f"{inner}{format_mask_expression(relative_fields, inner, 1)},\n"
        f"{inner}{format_mask_expression(relative_fields, inner, 2)},\n"
        f"{inner}{format_mask_expression(relative_fields, inner, 3)},\n"
        f"{inner}{format_mask_expression(at_least_fields, inner, 1)},\n"
        f"{inner}{format_mask_expression(at_least_fields, inner, 2)},\n"
        f"{inner}{format_mask_expression(at_least_fields, inner, 3)},\n"
        f"{inner}{format_mask_expression(at_most_fields, inner, 1)},\n"
        f"{inner}{format_mask_expression(at_most_fields, inner, 2)},\n"
        f"{inner}{format_mask_expression(at_most_fields, inner, 3)},\n"
        f"{indent}}}"
    )


def format_behavior_override_member_profile(
    match_raws: dict[str, str],
    member_start: int,
    member_count: int,
    target_mode: str,
    mask_fields: set[str],
    profile_raws: dict[str, str],
    indent: str = "    ",
    name: str = "",
    relative_fields: set[str] | None = None,
    at_least_fields: set[str] | None = None,
    at_most_fields: set[str] | None = None,
) -> str:
    mode_symbol = {
        "disabled": "OW_WILD_BEHAVIOR_OVERRIDE_TARGET_DISABLED",
        "members": "OW_WILD_BEHAVIOR_OVERRIDE_TARGET_MEMBERS",
        "all": "OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL",
    }[target_mode]
    inner = indent + "    "
    relative_fields = relative_fields or set()
    at_least_fields = at_least_fields or set()
    at_most_fields = at_most_fields or set()
    storage_raws = override_profile_storage_raws(profile_raws)
    return override_profile_name_comment(name, indent) + (
        f"{indent}{{\n"
        f"{inner}{format_match_initializer(match_raws, inner)},\n"
        f"{inner}{member_start},\n"
        f"{inner}{member_count},\n"
        f"{inner}{mode_symbol},\n"
        f"{inner}{format_mask_expression(mask_fields, inner, 1)},\n"
        f"{inner}{format_mask_expression(mask_fields, inner, 2)},\n"
        f"{inner}{format_mask_expression(mask_fields, inner, 3)},\n"
        f"{inner}{format_profile_initializer(storage_raws, inner)},\n"
        f"{inner}{format_mask_expression(relative_fields, inner, 1)},\n"
        f"{inner}{format_mask_expression(relative_fields, inner, 2)},\n"
        f"{inner}{format_mask_expression(relative_fields, inner, 3)},\n"
        f"{inner}{format_mask_expression(at_least_fields, inner, 1)},\n"
        f"{inner}{format_mask_expression(at_least_fields, inner, 2)},\n"
        f"{inner}{format_mask_expression(at_least_fields, inner, 3)},\n"
        f"{inner}{format_mask_expression(at_most_fields, inner, 1)},\n"
        f"{inner}{format_mask_expression(at_most_fields, inner, 2)},\n"
        f"{inner}{format_mask_expression(at_most_fields, inner, 3)},\n"
        f"{indent}}}"
    )


def format_behavior_override_profile_rule(
    match_raws: dict[str, str],
    profile_index: int,
    indent: str = "    ",
) -> str:
    inner = indent + "    "
    return (
        f"{indent}{{\n"
        f"{inner}{format_match_initializer(match_raws, inner)},\n"
        f"{inner}{profile_index},\n"
        f"{indent}}}"
    )


def raw_match_values(match: dict[str, dict]) -> dict[str, str]:
    return {field: match[field]["raw"] for field in MATCH_FIELDS}


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
    group_labels = invert_labels(macros, GROUP_PREFIX)

    class_profiles = [
        parse_profile(entry, macros)
        for entry in parse_initializer(extract_braced_initializer(behavior_source, "sOverworldWildBehaviorClassProfiles"))
    ]
    changes = parse_save_payload(body)
    if not changes:
        return {"saved": False, "message": "No changes"}

    changes = {
        class_index: {
            field: canonical_profile_change_raw(field, raw, macros)
            for field, raw in field_changes.items()
        }
        for class_index, field_changes in changes.items()
    }

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
        validate_behavior_data_override_profiles(updated_source, macros, group_labels)
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
    edits = changes["edit"]
    renames = changes["rename"]
    removals = changes["remove"]
    reorder_groups = changes["reorder"]
    match_replacements = changes["replaceMatches"]
    target_replacements = changes["replaceTargets"]
    if not additions and not edits and not renames and not removals and not reorder_groups and not target_replacements:
        return {"saved": False, "message": "No changes"}

    raw_behavior_data = BEHAVIOR_DATA_SOURCE.read_text()
    behavior_source = strip_c_comments(join_line_continuations(raw_behavior_data))
    expressions, species_order = parse_define_expressions(DEFINE_SOURCE_FILES)
    macros = evaluate_defines(expressions)
    macros.update(evaluate_armips_equ([ARMIPS_CONFIG, ARMIPS_CONSTANTS]))
    terrain_values, destination_values = parse_behavior_data_enums()
    macros.update(terrain_values)
    macros.update(destination_values)
    valid_species = {entry["symbol"] for entry in parse_species(expressions, macros, species_order)}
    runtime_owned_override_order = macros.get("OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER_POKEMON", -2) + 1
    if runtime_owned_override_order in removals or runtime_owned_override_order in renames:
        raise ValueError("the runtime-owned Follower Pokemon override cannot be renamed or deleted")

    class_profiles = [
        parse_profile(entry, macros)
        for entry in parse_initializer(extract_braced_initializer(behavior_source, "sOverworldWildBehaviorClassProfiles"))
    ]
    group_labels = invert_labels(macros, GROUP_PREFIX)
    existing_overrides = parse_behavior_overrides(behavior_source, macros, group_labels)
    existing_names = parse_override_profile_names(raw_behavior_data)
    valid_options = valid_change_options(macros, class_profiles)
    for addition in additions:
        addition["fields"] = {
            field: canonical_profile_change_raw(field, raw, macros, allow_relative=True)
            for field, raw in addition["fields"].items()
        }
    edits = {
        order: {
            field: canonical_profile_change_raw(field, raw, macros, allow_relative=True)
            for field, raw in field_changes.items()
        }
        for order, field_changes in edits.items()
    }
    for override in existing_overrides:
        for field in behavior_override_field_keys(override["behavior"]):
            value = override["behavior"]["profile"][field]
            if value.get("raw") and value.get("value") is not None:
                valid_options[field].add(canonical_profile_value_raw(value, field))

    def validate_override_fields(fields: dict[str, str], label: str) -> None:
        for field, raw in fields.items():
            if field not in PROFILE_FIELDS:
                raise ValueError(f"invalid override field: {field}")
            if field not in OVERRIDE_SYMBOL_BY_FIELD:
                raise ValueError(f"field cannot be used in override profiles: {field}")
            if raw and is_numeric_override_operator_raw(field, raw):
                if is_relative_override_raw(field, raw):
                    delta = int(raw, 10)
                    if delta < RELATIVE_OVERRIDE_DELTA_MIN or delta > RELATIVE_OVERRIDE_DELTA_MAX:
                        raise ValueError(f"invalid relative value for {field}: {raw}")
                else:
                    threshold = int(raw[2:], 10)
                    maximum = NUMERIC_PROFILE_FIELD_OPTION_MAX.get(field, 64)
                    minimum = 1 if field in MOVEMENT_SPEED_FIELDS else 0
                    if threshold < minimum or threshold > maximum:
                        raise ValueError(f"invalid override bound for {field}: {raw}")
                continue
            if raw and raw not in valid_options[field]:
                raise ValueError(f"invalid value for {field}: {raw}")

    def validate_override_match(match_raws: dict[str, str], label: str, allow_global: bool = False) -> None:
        match_values = [match_raws[match_field] for match_field in MATCH_FIELDS]
        parsed_match = parse_match(match_values, macros)
        unresolved = [field_name for field_name, value in parsed_match.items() if numeric(value) is None]
        if unresolved:
            raise ValueError(f"{label} has invalid match value for {', '.join(unresolved)}")
        any_species = macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_SPECIES", macros.get("SPECIES_NONE", 0))
        any_class = macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_CLASS", 0)
        any_terrain = macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_TERRAIN", 0)
        any_level = macros.get("OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY", 0)
        any_shiny = macros.get("OW_WILD_BEHAVIOR_MATCH_ANY_SHINY", 0)
        group_none = macros.get("OW_WILD_BEHAVIOR_GROUP_NONE", 0)
        if not allow_global and (
            numeric(parsed_match["species"]) == any_species
            and numeric(parsed_match["groupMask"]) == group_none
            and numeric(parsed_match["terrain"]) == any_terrain
            and numeric(parsed_match["minLevel"]) == any_level
            and numeric(parsed_match["maxLevel"]) == any_level
            and numeric(parsed_match["shiny"]) == any_shiny
            and numeric(parsed_match["behaviorClass"]) == any_class
        ):
            raise ValueError(f"{label} would match every Pokemon; choose a species, group, terrain, type, or class target")
        min_level = numeric(parsed_match["minLevel"])
        max_level = numeric(parsed_match["maxLevel"])
        if min_level != any_level and max_level != any_level and min_level is not None and max_level is not None and min_level > max_level:
            raise ValueError(f"{label} minimum level cannot be greater than maximum level")

    def validate_override_target(target: dict, label: str) -> None:
        mode = target["targetMode"]
        members = target["members"]
        if len(members) != len(set(members)):
            raise ValueError(f"{label} contains duplicate Pokemon members")
        if len(members) > 0xFFFF:
            raise ValueError(f"{label} has too many Pokemon members for u16 storage")
        invalid_members = [member for member in members if member not in valid_species or member == "SPECIES_NONE"]
        if invalid_members:
            raise ValueError(f"{label} contains invalid Pokemon: {', '.join(invalid_members)}")
        if mode == "members" and not members:
            raise ValueError(f"{label} member target must include at least one Pokemon")
        validate_override_match(target["match"], label, allow_global=(mode in {"members", "disabled"}))

    def legacy_matches_from_target(target: dict, label: str) -> list[dict[str, str]]:
        """Losslessly project the v32 target shape onto the pre-v32 row model."""
        validate_override_target(target, label)
        if target["targetMode"] == "disabled":
            disabled_match = default_behavior_match_raws()
            disabled_match["behaviorClass"] = "0xFE"
            return [disabled_match]
        if target["targetMode"] == "all":
            return [dict(target["match"])]
        return [
            {**target["match"], "species": member}
            for member in target["members"]
        ]

    try:
        backend_profiles = parse_behavior_override_profiles(behavior_source, macros)
    except ParseError:
        backend_profiles = []

    if behavior_source_uses_override_members(behavior_source):
        order_inputs = set(removals) | set(edits) | set(renames) | set(target_replacements)
        order_inputs.update(order for group in reorder_groups for order in group)
        for order in order_inputs:
            if order < 1 or order > len(backend_profiles):
                raise ValueError(f"override profile order out of range: {order}")

        def mode_name(value: dict) -> str:
            numeric_mode = numeric(value)
            if numeric_mode == macros.get("OW_WILD_BEHAVIOR_OVERRIDE_TARGET_MEMBERS", 1):
                return "members"
            if numeric_mode == macros.get("OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL", 2):
                return "all"
            return "disabled"

        def behavior_from_fields(fields: dict[str, str]) -> dict:
            profile_raws = {profile_field: "0" for profile_field in PROFILE_FIELDS}
            profile_raws.update(fields)
            relative_fields = relative_override_fields_from_raws(profile_raws)
            at_least_fields = at_least_override_fields_from_raws(profile_raws)
            at_most_fields = at_most_override_fields_from_raws(profile_raws)
            return parse_behavior_override(
                [
                    format_mask_expression(set(fields), "", 1),
                    format_mask_expression(set(fields), "", 2),
                    format_mask_expression(set(fields), "", 3),
                    [profile_raws[field] for field in PROFILE_FIELDS],
                    format_mask_expression(relative_fields, "", 1),
                    format_mask_expression(relative_fields, "", 2),
                    format_mask_expression(relative_fields, "", 3),
                    format_mask_expression(at_least_fields, "", 1),
                    format_mask_expression(at_least_fields, "", 2),
                    format_mask_expression(at_least_fields, "", 3),
                    format_mask_expression(at_most_fields, "", 1),
                    format_mask_expression(at_most_fields, "", 2),
                    format_mask_expression(at_most_fields, "", 3),
                ],
                macros,
            )

        profiles_model = []
        profile_names = parse_override_profile_entry_names(raw_behavior_data)
        for profile in backend_profiles:
            profiles_model.append(
                {
                    "originalOrder": profile["order"],
                    "name": profile_names.get(profile["order"], ""),
                    "behavior": profile["behavior"],
                    "target": {
                        "members": list(profile.get("memberSymbols") or []),
                        "match": raw_match_values(profile["match"]),
                        "targetMode": mode_name(profile["targetMode"]),
                    },
                }
            )

        for order, field_changes in edits.items():
            if order in removals:
                continue
            validate_override_fields(field_changes, f"override {order}")
            behavior = profiles_model[order - 1]["behavior"]
            fields = {
                field: behavior["profile"][field]["raw"]
                for field in behavior_override_field_keys(behavior)
            }
            fields.update(field_changes)
            profiles_model[order - 1]["behavior"] = behavior_from_fields(
                {field: raw for field, raw in fields.items() if raw}
            )

        for order, name in renames.items():
            if order not in removals:
                profiles_model[order - 1]["name"] = name

        for order, target in target_replacements.items():
            if order in removals:
                raise ValueError(f"override {order} cannot be removed and retargeted")
            validate_override_target(target, f"override {order}")
            profiles_model[order - 1]["target"] = target

        next_original_order = len(profiles_model) + 1
        for index, change in enumerate(additions, 1):
            validate_override_fields(change["fields"], f"override addition {index}")
            validate_override_target(change["target"], f"override addition {index}")
            fields = {field: raw for field, raw in change["fields"].items() if raw}
            profiles_model.append(
                {
                    "originalOrder": next_original_order,
                    "name": change.get("name", ""),
                    "behavior": behavior_from_fields(fields),
                    "target": change["target"],
                }
            )
            next_original_order += 1

        active = [profile for profile in profiles_model if profile["originalOrder"] not in set(removals)]
        if reorder_groups:
            active_by_order = {profile["originalOrder"]: profile for profile in active}
            requested = []
            seen = set()
            for group in reorder_groups:
                for order in group:
                    if order in active_by_order and order not in seen:
                        requested.append(active_by_order[order])
                        seen.add(order)
            requested.extend(profile for profile in active if profile["originalOrder"] not in seen)
            active = requested

        if not active:
            raise ValueError("at least one override profile is required; create a replacement before removing the last profile")

        names = [profile["name"].strip().lower() for profile in active if profile["name"].strip()]
        if len(names) != len(set(names)):
            raise ValueError("override profile names must be unique")
        if len(active) > 0xFFFF:
            raise ValueError("too many override profiles for u16 storage")

        profile_span = initializer_brace_span(raw_behavior_data, "sOverworldWildBehaviorOverrideProfiles")
        member_span = initializer_brace_span(raw_behavior_data, "sOverworldWildBehaviorOverrideMembers")
        profile_indent = line_indent_before(raw_behavior_data, profile_span[0])
        member_indent = line_indent_before(raw_behavior_data, member_span[0])
        profile_entry_indent = profile_indent + "    "
        member_entry_indent = member_indent + "    "
        flat_members = []
        profile_entries = []
        for profile in active:
            target = profile["target"]
            if len(flat_members) + len(target["members"]) > 0xFFFF:
                raise ValueError("override member table exceeds u16 storage")
            member_start = len(flat_members)
            flat_members.extend(target["members"])
            profile_entries.append(
                format_behavior_override_member_profile(
                    target["match"],
                    member_start,
                    len(target["members"]),
                    target["targetMode"],
                    set(behavior_override_field_keys(profile["behavior"])),
                    raw_values(profile["behavior"]["profile"]),
                    profile_entry_indent,
                    profile["name"],
                    relative_fields=set(behavior_override_relative_field_keys(profile["behavior"])),
                    at_least_fields=set(behavior_override_at_least_field_keys(profile["behavior"])),
                    at_most_fields=set(behavior_override_at_most_field_keys(profile["behavior"])),
                )
            )
        # Keep the fixed C blob layout standard-compliant even when every
        # profile uses disabled/all targeting and no member slice is referenced.
        stored_members = flat_members or ["SPECIES_NONE"]
        profile_entries_text = ",\n".join(profile_entries)
        member_entries_text = ",\n".join(member_entry_indent + member for member in stored_members)
        formatted_profiles = f"{{\n{profile_entries_text}\n{profile_indent}}}"
        formatted_members = f"{{\n{member_entries_text}\n{member_indent}}}"
        replacements = [
            (profile_span[0], profile_span[1], formatted_profiles),
            (member_span[0], member_span[1], formatted_members),
        ]
        updated_source = raw_behavior_data
        changed = False
        for start, end, replacement in sorted(replacements, key=lambda item: item[0], reverse=True):
            if updated_source[start:end] != replacement:
                changed = True
                updated_source = updated_source[:start] + replacement + updated_source[end:]
        if changed:
            validate_behavior_data_override_profiles(updated_source, macros, group_labels)
            write_behavior_data_source(updated_source)
        total_changes = len(additions) + len(edits) + len(renames) + len(set(removals)) + len(target_replacements) + (1 if reorder_groups else 0)
        label = "override profile change" if total_changes == 1 else "override profile changes"
        return {"saved": changed, "message": f"Saved {total_changes} {label}" if changed else "No code changes needed"}

    # V2 always submits the profile-owned target shape. Older source layouts
    # can still be upgraded/edited safely by projecting that one target into
    # their legacy storage rows at the writer boundary.
    for order, target in target_replacements.items():
        match_replacements[order] = legacy_matches_from_target(target, f"override {order}")

    if backend_profiles:
        profile_names = parse_override_profile_entry_names(raw_behavior_data)

        reorder_orders = {order for group in reorder_groups for order in group}
        for order in set(removals) | set(edits.keys()) | set(renames.keys()) | set(match_replacements.keys()) | reorder_orders:
            if order < 1 or order > len(existing_overrides):
                raise ValueError(f"override order out of range: {order}")
        for order, field_changes in edits.items():
            validate_override_fields(field_changes, f"override {order}")

        profiles_model = [
            {
                "behavior": profile["behavior"],
                "name": profile_names.get(profile["order"], ""),
            }
            for profile in backend_profiles
        ]
        rules_model = [
            {
                "order": override["order"],
                "match": raw_match_values(override["match"]),
                "profileOrder": override["profileOrder"],
                "removed": override["order"] in removals,
            }
            for override in existing_overrides
        ]
        preferred_profile_orders: set[int] = set()
        identity_changed_profile_orders: set[int] = set()

        for order, replacement_matches in match_replacements.items():
            profile_order = existing_overrides[order - 1]["profileOrder"]
            profile_rule_orders = {
                override["order"]
                for override in existing_overrides
                if override["profileOrder"] == profile_order
            }
            if profile_rule_orders.intersection(removals):
                raise ValueError(f"override {order} cannot be removed and have its matches replaced")
            matching_indexes = [
                index
                for index, rule in enumerate(rules_model)
                if rule["profileOrder"] == profile_order
            ]
            if not matching_indexes:
                raise ValueError(f"override {order} has no rules to replace")
            for match_index, match in enumerate(replacement_matches, 1):
                validate_override_match(match, f"override {order}.{match_index}")
            old_orders = [
                rules_model[index].get("order")
                for index in matching_indexes
                if rules_model[index].get("order") is not None
            ]
            insertion_index = matching_indexes[0]
            matching_index_set = set(matching_indexes)
            rules_model = [
                rule
                for index, rule in enumerate(rules_model)
                if index not in matching_index_set
            ]
            replacement_rules = [
                {
                    "order": old_orders[index] if index < len(old_orders) else None,
                    "match": match,
                    "profileOrder": profile_order,
                    "removed": False,
                }
                for index, match in enumerate(replacement_matches)
            ]
            rules_model[insertion_index:insertion_index] = replacement_rules
            preferred_profile_orders.add(profile_order)

        for order, field_changes in edits.items():
            if order in removals:
                continue
            profile_order = existing_overrides[order - 1]["profileOrder"]
            preferred_profile_orders.add(profile_order)
            behavior = profiles_model[profile_order - 1]["behavior"]
            fields = {
                field: behavior["profile"][field]["raw"]
                for field in behavior_override_field_keys(behavior)
            }
            fields.update(field_changes)
            fields = {field: raw for field, raw in fields.items() if raw}
            profile_raws = {profile_field: "0" for profile_field in PROFILE_FIELDS}
            profile_raws.update(fields)
            relative_fields = relative_override_fields_from_raws(profile_raws)
            at_least_fields = at_least_override_fields_from_raws(profile_raws)
            at_most_fields = at_most_override_fields_from_raws(profile_raws)
            profiles_model[profile_order - 1]["behavior"] = parse_behavior_override(
                [
                    format_mask_expression(set(fields.keys()), "", 1),
                    format_mask_expression(set(fields.keys()), "", 2),
                    format_mask_expression(set(fields.keys()), "", 3),
                    [profile_raws[field] for field in PROFILE_FIELDS],
                    format_mask_expression(relative_fields, "", 1),
                    format_mask_expression(relative_fields, "", 2),
                    format_mask_expression(relative_fields, "", 3),
                    format_mask_expression(at_least_fields, "", 1),
                    format_mask_expression(at_least_fields, "", 2),
                    format_mask_expression(at_least_fields, "", 3),
                    format_mask_expression(at_most_fields, "", 1),
                    format_mask_expression(at_most_fields, "", 2),
                    format_mask_expression(at_most_fields, "", 3),
                ],
                macros,
            )

        for order, name in renames.items():
            if order in removals:
                continue
            profile_order = existing_overrides[order - 1]["profileOrder"]
            preferred_profile_orders.add(profile_order)
            profiles_model[profile_order - 1]["name"] = name
            identity_changed_profile_orders.add(profile_order)

        for index, change in enumerate(additions, 1):
            validate_override_fields(change["fields"], f"override {index}")
            fields = {field: raw for field, raw in change["fields"].items() if raw}
            profile_raws = {profile_field: "0" for profile_field in PROFILE_FIELDS}
            profile_raws.update(fields)
            relative_fields = relative_override_fields_from_raws(profile_raws)
            at_least_fields = at_least_override_fields_from_raws(profile_raws)
            at_most_fields = at_most_override_fields_from_raws(profile_raws)
            profiles_model.append(
                {
                    "behavior": parse_behavior_override(
                        [
                            format_mask_expression(set(fields.keys()), "", 1),
                            format_mask_expression(set(fields.keys()), "", 2),
                            format_mask_expression(set(fields.keys()), "", 3),
                            [profile_raws[field] for field in PROFILE_FIELDS],
                            format_mask_expression(relative_fields, "", 1),
                            format_mask_expression(relative_fields, "", 2),
                            format_mask_expression(relative_fields, "", 3),
                            format_mask_expression(at_least_fields, "", 1),
                            format_mask_expression(at_least_fields, "", 2),
                            format_mask_expression(at_least_fields, "", 3),
                            format_mask_expression(at_most_fields, "", 1),
                            format_mask_expression(at_most_fields, "", 2),
                            format_mask_expression(at_most_fields, "", 3),
                        ],
                        macros,
                    ),
                    "name": change.get("name", ""),
                }
            )
            profile_order = len(profiles_model)
            identity_changed_profile_orders.add(profile_order)
            if change.get("name"):
                preferred_profile_orders.add(profile_order)
            addition_matches = legacy_matches_from_target(change["target"], f"override {index}")
            for match_index, match in enumerate(addition_matches, 1):
                validate_override_match(match, f"override {index}.{match_index}")
                rules_model.append(
                    {
                        "match": match,
                        "profileOrder": profile_order,
                        "removed": False,
                    }
                )

        active_profile_orders_by_name: dict[str, set[int]] = {}
        for rule in rules_model:
            if rule["removed"]:
                continue
            profile_order = rule["profileOrder"]
            name = profiles_model[profile_order - 1].get("name", "").strip()
            if name:
                active_profile_orders_by_name.setdefault(name.lower(), set()).add(profile_order)
        duplicate_changed_names = [
            profiles_model[min(profile_orders) - 1].get("name", normalized_name)
            for normalized_name, profile_orders in active_profile_orders_by_name.items()
            if len(profile_orders) > 1 and profile_orders.intersection(identity_changed_profile_orders)
        ]
        if duplicate_changed_names:
            raise ValueError(
                f"override profile names must be unique: {', '.join(sorted(duplicate_changed_names))}"
            )

        if reorder_groups:
            profile_order_by_rule_order = {
                rule["order"]: rule["profileOrder"]
                for rule in rules_model
                if rule.get("order") is not None and not rule["removed"]
            }
            active_rules_by_profile: dict[int, list[dict]] = {}
            active_profile_order: list[int] = []
            for rule in rules_model:
                if rule["removed"]:
                    continue
                profile_order = rule["profileOrder"]
                if profile_order not in active_rules_by_profile:
                    active_rules_by_profile[profile_order] = []
                    active_profile_order.append(profile_order)
                active_rules_by_profile[profile_order].append(rule)

            requested_profile_order = []
            seen_profile_orders = set()
            for group in reorder_groups:
                for order in group:
                    profile_order = profile_order_by_rule_order.get(order)
                    if profile_order is None or profile_order in seen_profile_orders:
                        continue
                    requested_profile_order.append(profile_order)
                    seen_profile_orders.add(profile_order)
            requested_profile_order.extend(
                profile_order
                for profile_order in active_profile_order
                if profile_order not in seen_profile_orders
            )
            rules_model = [
                rule
                for profile_order in requested_profile_order
                for rule in active_rules_by_profile[profile_order]
            ] + [rule for rule in rules_model if rule["removed"]]

        canonicalize_named_override_profile_rules(profiles_model, rules_model, preferred_profile_orders)

        referenced_profile_orders = {
            rule["profileOrder"]
            for rule in rules_model
            if not rule["removed"]
        }
        profile_index_map: dict[int, int] = {}
        kept_profiles = []
        if reorder_groups:
            profile_orders = []
            seen_profile_orders = set()
            for rule in rules_model:
                if rule["removed"]:
                    continue
                profile_order = rule["profileOrder"]
                if profile_order in referenced_profile_orders and profile_order not in seen_profile_orders:
                    profile_orders.append(profile_order)
                    seen_profile_orders.add(profile_order)
            for profile_order in range(1, len(profiles_model) + 1):
                if profile_order in referenced_profile_orders and profile_order not in seen_profile_orders:
                    profile_orders.append(profile_order)
                    seen_profile_orders.add(profile_order)
        else:
            profile_orders = [
                profile_order
                for profile_order in range(1, len(profiles_model) + 1)
                if profile_order in referenced_profile_orders
            ]
        for profile_order in profile_orders:
            profile = profiles_model[profile_order - 1]
            if profile_order not in referenced_profile_orders:
                continue
            profile_index_map[profile_order] = len(kept_profiles)
            kept_profiles.append(profile)

        profile_span = initializer_brace_span(raw_behavior_data, "sOverworldWildBehaviorOverrideProfiles")
        rule_span = initializer_brace_span(raw_behavior_data, "sOverworldWildBehaviorOverrideRules")
        profile_indent = line_indent_before(raw_behavior_data, profile_span[0])
        rule_indent = line_indent_before(raw_behavior_data, rule_span[0])
        profile_entry_indent = profile_indent + "    "
        rule_entry_indent = rule_indent + "    "
        profile_entries = ",\n".join(
            format_behavior_override_profile(
                set(behavior_override_field_keys(profile["behavior"])),
                raw_values(profile["behavior"]["profile"]),
                profile_entry_indent,
                profile["name"],
                relative_fields=set(behavior_override_relative_field_keys(profile["behavior"])),
                at_least_fields=set(behavior_override_at_least_field_keys(profile["behavior"])),
                at_most_fields=set(behavior_override_at_most_field_keys(profile["behavior"])),
            )
            for profile in kept_profiles
        )
        rule_entries = ",\n".join(
            format_behavior_override_profile_rule(
                rule["match"],
                profile_index_map[rule["profileOrder"]],
                rule_entry_indent,
            )
            for rule in rules_model
            if not rule["removed"]
        )
        replacements = [
            (profile_span[0], profile_span[1], f"{{\n{profile_entries}\n{profile_indent}}}"),
            (rule_span[0], rule_span[1], f"{{\n{rule_entries}\n{rule_indent}}}"),
        ]

        updated_source = raw_behavior_data
        changed = False
        for start, end, replacement in sorted(replacements, key=lambda item: item[0], reverse=True):
            if updated_source[start:end] != replacement:
                changed = True
                updated_source = updated_source[:start] + replacement + updated_source[end:]
        if changed:
            validate_behavior_data_override_profiles(updated_source, macros, group_labels)
            write_behavior_data_source(updated_source)
        total_changes = len(additions) + len(edits) + len(renames) + len(set(removals)) + len(match_replacements) + (1 if reorder_groups else 0)
        label = "override profile change" if total_changes == 1 else "override profile changes"
        return {"saved": changed, "message": f"Saved {total_changes} {label}" if changed else "No code changes needed"}

    if match_replacements:
        raise ValueError("override match replacement requires split override profile data")
    if reorder_groups:
        raise ValueError("override profile reordering requires split override profile data")

    def override_rule_from_fields(match_raws: dict[str, str], fields: dict[str, str], name: str = "") -> str:
        profile_raws = {profile_field: "0" for profile_field in PROFILE_FIELDS}
        mask_fields = set()
        for field, raw in fields.items():
            if raw:
                profile_raws[field] = raw
                mask_fields.add(field)
        return format_behavior_override_rule(
            match_raws,
            mask_fields,
            profile_raws,
            name=name,
            relative_fields=relative_override_fields_from_raws(profile_raws),
            at_least_fields=at_least_override_fields_from_raws(profile_raws),
            at_most_fields=at_most_override_fields_from_raws(profile_raws),
        )

    formatted_rules = []
    for index, change in enumerate(additions, 1):
        validate_override_fields(change["fields"], f"override {index}")
        addition_matches = legacy_matches_from_target(change["target"], f"override {index}")
        for match_index, match in enumerate(addition_matches, 1):
            validate_override_match(match, f"override {index}.{match_index}")
            formatted_rules.append(override_rule_from_fields(match, change["fields"], change.get("name", "")))

    override_span = initializer_brace_span(raw_behavior_data, "sOverworldWildBehaviorOverrides")
    override_entry_spans = top_level_braced_spans(raw_behavior_data, override_span)
    override_replacement_spans = override_entry_replacement_spans(raw_behavior_data, override_span, override_entry_spans)
    for order in set(removals) | set(edits.keys()) | set(renames.keys()):
        if order < 1 or order > len(override_entry_spans):
            raise ValueError(f"override order out of range: {order}")
    for order, field_changes in edits.items():
        validate_override_fields(field_changes, f"override {order}")

    override_group_orders: dict[str, list[int]] = {}
    for override in existing_overrides:
        override_name = existing_names.get(override["order"], "")
        if override_name:
            override_group_orders.setdefault(override_name, []).append(override["order"])

    rewrite_orders = set(edits.keys()) | set(renames.keys())
    for order in list(rewrite_orders):
        override_name = existing_names.get(order, "")
        if override_name:
            rewrite_orders.update(override_group_orders.get(override_name, []))

    group_renames = {
        existing_names[order]: name
        for order, name in renames.items()
        if existing_names.get(order)
    }

    def grouped_override_fields(order: int) -> dict[str, str]:
        override_name = existing_names.get(order, "")
        source_orders = override_group_orders.get(override_name, [order]) if override_name else [order]
        primary_behavior = existing_overrides[source_orders[0] - 1]["behavior"]
        active_fields: list[str] = []
        fields: dict[str, str] = {}
        for source_order in source_orders:
            behavior = existing_overrides[source_order - 1]["behavior"]
            for field in behavior_override_field_keys(behavior):
                if field not in active_fields:
                    active_fields.append(field)
        for field in active_fields:
            fields[field] = primary_behavior["profile"][field]["raw"]
        return fields

    replacements: list[tuple[int, int, str]] = []
    for order in sorted(rewrite_orders):
        if order in set(removals):
            continue
        field_changes = edits.get(order, {})
        existing = existing_overrides[order - 1]
        fields = grouped_override_fields(order)
        fields.update(field_changes)
        fields = {field: raw for field, raw in fields.items() if raw}
        entry_span = override_replacement_spans[order - 1]
        profile_indent = line_indent_before(raw_behavior_data, entry_span[0])
        override_name = existing_names.get(order, "")
        replacement = format_behavior_override_rule(
            raw_match_values(existing["match"]),
            set(fields.keys()),
            {**{profile_field: "0" for profile_field in PROFILE_FIELDS}, **fields},
            profile_indent,
            renames.get(order, group_renames.get(override_name, override_name)),
            relative_fields=relative_override_fields_from_raws(fields),
            at_least_fields=at_least_override_fields_from_raws(fields),
            at_most_fields=at_most_override_fields_from_raws(fields),
        )
        replacements.append((entry_span[0], entry_span[1], replacement))
    for order in sorted(set(removals), reverse=True):
        start, end = braced_entry_removal_span(raw_behavior_data, override_replacement_spans[order - 1], override_span)
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
    total_changes = len(formatted_rules) + len(edits) + len(renames) + len(set(removals))
    label = "override profile change" if total_changes == 1 else "override profile changes"
    return {"saved": changed, "message": f"Saved {total_changes} {label}" if changed else "No code changes needed"}


def build_command_args() -> list[str]:
    if sys.platform == "win32":
        return ["cmd.exe", "/c", BUILD_COMMAND]
    return ["/bin/sh", BUILD_COMMAND]


def build_command_env() -> dict[str, str]:
    env = os.environ.copy()
    if sys.platform != "win32":
        paths = [
            "/usr/local/bin",
            "/opt/homebrew/bin",
            "/Applications/Docker.app/Contents/Resources/bin",
            *(env.get("PATH") or os.defpath).split(os.pathsep),
            "/usr/bin",
            "/bin",
            "/usr/sbin",
            "/sbin",
        ]
        deduped_paths = []
        for path in paths:
            if path and path not in deduped_paths:
                deduped_paths.append(path)
        env["PATH"] = os.pathsep.join(deduped_paths)
    return env


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
        env=build_command_env(),
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

    rom_path = str(TEST_NDS)
    configured_command = os.environ.get("NDS_OPEN_COMMAND", "").strip()
    if configured_command:
        # Parse into argv without invoking a shell. Quoted executable paths are
        # therefore supported without allowing shell operators to execute.
        try:
            command = shlex.split(configured_command, posix=os.name != "nt")
        except ValueError as exc:
            raise RuntimeError(f"NDS_OPEN_COMMAND could not be parsed: {exc}") from exc
        if os.name == "nt":
            # Non-POSIX shlex preserves Windows path separators, but also
            # preserves matching outer quotes. Remove only those outer quotes;
            # the argv remains shell-free and embedded characters stay intact.
            command = [
                argument[1:-1]
                if len(argument) >= 2
                and argument[0] == argument[-1]
                and argument[0] in {'"', "'"}
                else argument
                for argument in command
            ]
        if not command or not command[0].strip():
            raise RuntimeError("NDS_OPEN_COMMAND does not contain an executable")
        has_rom_placeholder = any("{rom}" in argument for argument in command)
        command = [argument.replace("{rom}", rom_path) for argument in command]
        if not has_rom_placeholder:
            command.append(rom_path)
        launcher = f"NDS_OPEN_COMMAND ({command[0]})"
        popen_options = {
            "cwd": ROOT,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if os.name == "nt":
            creation_flags = (
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                | getattr(subprocess, "DETACHED_PROCESS", 0)
            )
            if creation_flags:
                popen_options["creationflags"] = creation_flags
        else:
            popen_options["start_new_session"] = True
        try:
            process = subprocess.Popen(command, **popen_options)
        except OSError as exc:
            raise RuntimeError(
                f"ROM launcher '{command[0]}' could not start: {exc}. "
                "Check NDS_OPEN_COMMAND and the emulator path."
            ) from exc
        try:
            return_code = process.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            # Reap the detached emulator after it eventually exits without
            # keeping the HTTP request open for the entire emulator session.
            threading.Thread(target=process.wait, daemon=True).start()
        else:
            if return_code != 0:
                raise RuntimeError(
                    f"ROM launcher '{command[0]}' exited with status {return_code}. "
                    "Check NDS_OPEN_COMMAND and the emulator path."
                )
        return {
            "opened": True,
            "path": rom_path,
            "launcher": launcher,
            "message": f"Requested test.nds open via {launcher}",
        }
    if sys.platform == "darwin":
        command = ["open", rom_path]
        launcher = "macOS open"
    elif os.name == "nt":
        try:
            os.startfile(rom_path)  # type: ignore[attr-defined]
        except OSError as exc:
            raise RuntimeError(
                f"Windows could not open test.nds: {exc}. "
                "Associate .nds files with an emulator or set NDS_OPEN_COMMAND."
            ) from exc
        launcher = "Windows shell"
        return {
            "opened": True,
            "path": rom_path,
            "launcher": launcher,
            "message": f"Requested test.nds open via {launcher}",
        }
    else:
        xdg_open = shutil.which("xdg-open")
        gio = shutil.which("gio")
        if xdg_open:
            command = [xdg_open, rom_path]
            launcher = "xdg-open"
        elif gio:
            command = [gio, "open", rom_path]
            launcher = "gio open"
        else:
            raise RuntimeError(
                "No desktop file opener is available. Install xdg-utils or gio, "
                "or set NDS_OPEN_COMMAND to your emulator command."
            )

    try:
        subprocess.run(command, cwd=ROOT, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"ROM launcher '{command[0]}' was not found. "
            "Install it or set NDS_OPEN_COMMAND to an available emulator command."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"ROM launcher '{command[0]}' exited with status {exc.returncode}. "
            "Check the .nds file association or set NDS_OPEN_COMMAND."
        ) from exc
    return {
        "opened": True,
        "path": rom_path,
        "launcher": launcher,
        "message": f"Requested test.nds open via {launcher}",
    }


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


def reserved_shinies_from_save(save_bytes: bytes | bytearray, copy_base: int, magic_ok: bool) -> list[dict]:
    if not magic_ok:
        return []
    result: list[dict] = []
    for index in range(OVERWORLD_WILD_MAX_SAVED_SHINIES):
        offset = (
            copy_base
            + OVERWORLD_WILD_SAVED_SHINIES_SAVE_OFFSET
            + index * OVERWORLD_WILD_SAVED_SHINY_SIZE
        )
        if offset + OVERWORLD_WILD_SAVED_SHINY_SIZE > len(save_bytes):
            break
        map_id, species_and_form = struct.unpack_from("<HH", save_bytes, offset)
        level = save_bytes[offset + 4]
        terrain_and_active = save_bytes[offset + 5]
        species = species_and_form & OVERWORLD_WILD_SPECIES_MASK
        if not (terrain_and_active & OVERWORLD_WILD_SAVED_SHINY_ACTIVE) or species == 0 or level == 0:
            continue
        result.append(
            {
                "slot": index + 1,
                "mapId": map_id,
                "species": species,
                "form": species_and_form >> OVERWORLD_WILD_FORM_SHIFT,
                "level": level,
                "terrain": terrain_and_active & OVERWORLD_WILD_SAVED_SHINY_TERRAIN_MASK,
            }
        )
    return result


def shiny_counter_payload() -> dict:
    if not TEST_DSV.exists():
        return {
            "exists": False,
            "path": str(TEST_DSV),
            "counter": 0,
            "denominator": OVERWORLD_WILD_SHINY_BASE_ODDS,
            "magicOk": False,
            "reservedShinies": [],
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
    legacy_magic = magic == OVERWORLD_WILD_SHINY_COUNTER_MAGIC_V1
    counter = raw_counter if magic_ok or legacy_magic else 0
    counter = min(counter, OVERWORLD_WILD_SHINY_COUNTER_MAX)
    return {
        "exists": True,
        "path": str(path),
        "counter": counter,
        "rawCounter": raw_counter,
        "magic": magic,
        "magicOk": magic_ok,
        "legacyMagic": legacy_magic,
        "denominator": OVERWORLD_WILD_SHINY_BASE_ODDS - counter,
        "reservedShinies": reserved_shinies_from_save(save_bytes, base, magic_ok),
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
    reserved_offset = base + OVERWORLD_WILD_SAVED_SHINIES_SAVE_OFFSET
    reserved_size = OVERWORLD_WILD_SAVED_SHINY_SIZE * OVERWORLD_WILD_MAX_SAVED_SHINIES
    struct.pack_into("<H", raw, counter_offset, counter)
    struct.pack_into("<H", raw, magic_offset, OVERWORLD_WILD_SHINY_COUNTER_MAGIC)
    raw[reserved_offset:reserved_offset + reserved_size] = b"\0" * reserved_size

    footer_offset = base + SAVE_NORMAL_SLOT_SIZE - SAVE_CHUNK_FOOTER_SIZE
    crc = crc16_ccitt_false(raw[base:footer_offset])
    struct.pack_into("<H", raw, footer_offset + 0xE, crc)
    path.write_bytes(bytes(raw) + extra_bytes)
    return {
        **shiny_counter_payload(),
        "message": f"Shiny counter set to {counter}",
    }


def sound_effect_constants() -> dict[str, int]:
    constants: dict[str, int] = {}
    if not SNDSEQ_HEADER.exists():
        return constants
    for match in re.finditer(
        r"^\s*#define\s+(SEQ_SE_[A-Za-z0-9_]+)\s+(\d+)\s*$",
        SNDSEQ_HEADER.read_text(),
        flags=re.MULTILINE,
    ):
        constants[match.group(1)] = int(match.group(2))
    return constants


SOUND_EFFECT_CATALOG_ALIASES: dict[str, tuple[str, tuple[str, ...], str]] = {
    # These names follow the actual battle capture task and overlay-7 ball
    # animation events. Breakout is indirect: the capture task reuses the
    # Pokémon send-out controller, whose breakout path plays BOWA2.
    "SEQ_SE_DP_NAGERU": (
        "Battle Poké Ball throw",
        ("pokeball", "poke ball", "battle capture", "throw ball"),
        "Battle capture",
    ),
    "SEQ_SE_DP_BOWA4": (
        "Battle Poké Ball opens and draws in target",
        ("pokeball", "poke ball", "battle capture", "ball opens", "draw in pokemon", "pull in pokemon"),
        "Battle capture",
    ),
    "SEQ_SE_DP_BOWA2": (
        "Battle Pokémon reappears / Poké Ball breakout",
        ("pokeball", "poke ball", "battle capture", "capture failed", "breakout", "escape from ball", "reappear"),
        "Battle capture",
    ),
    "SEQ_SE_DP_BOWA": (
        "Battle Poké Ball shake",
        ("pokeball", "poke ball", "battle capture", "ball shake", "capture shake"),
        "Battle capture",
    ),
    "SEQ_SE_DP_GETTING": (
        "Battle Poké Ball capture success click",
        (
            "pokeball",
            "poke ball",
            "poké ball",
            "battle capture",
            "capture success",
            "successful capture",
            "capture click",
            "capture check",
            "capture check sound",
            "capture confirmed",
            "successful catch",
            "gotcha",
            "caught",
        ),
        "Battle capture",
    ),
    # BALL_ANIM_FALL's overlay-7 timed table plays KON at frames 1 and 8,
    # followed by KON2/KON3/KON4 at frames 14/18/20. KON is also the trainer
    # battle deflection sound, so it must not be presented as merely impact 1.
    "SEQ_SE_DP_KON": (
        "Battle Poké Ball landing impacts 1–2 / trainer deflect",
        ("pokeball", "poke ball", "battle capture", "ball landing", "landing impact", "trainer block", "deflect"),
        "Battle capture",
    ),
    "SEQ_SE_DP_KON2": (
        "Battle Poké Ball landing impact 3",
        ("pokeball", "poke ball", "battle capture", "ball landing", "landing impact"),
        "Battle capture",
    ),
    "SEQ_SE_DP_KON3": (
        "Battle Poké Ball landing impact 4",
        ("pokeball", "poke ball", "battle capture", "ball landing", "landing impact"),
        "Battle capture",
    ),
    "SEQ_SE_DP_KON4": (
        "Battle Poké Ball final landing settle",
        ("pokeball", "poke ball", "battle capture", "ball landing", "final settle", "impact"),
        "Battle capture",
    ),
    "SEQ_SE_DP_REAPOKE": (
        "Pokémon reappear",
        ("pokemon reappear", "pokémon reappear", "battle transition"),
        "Pokémon battle",
    ),
    "SEQ_SE_DP_PINPON": (
        "Out of Safari/Sport Balls alert",
        ("out of balls", "safari balls", "sport balls", "warning"),
        "Battle interface",
    ),
    "SEQ_ME_POKEGET": (
        "Pokémon obtained fanfare after capture",
        ("battle capture", "pokemon obtained", "pokémon obtained", "capture success", "gotcha", "caught"),
        "Jingle",
    ),
    "SEQ_GS_WIN2": (
        "Battle capture victory cue",
        ("battle capture", "capture victory", "gotcha", "caught"),
        "Battle capture",
    ),
    "SEQ_SE_PL_KIRAKIRA": (
        "Shiny sparkle",
        ("shiny pokemon", "shiny pokémon", "spawn sparkle"),
        "Overworld",
    ),
    "SEQ_SE_PL_W467109": (
        "Giratina form change",
        ("giratina", "form change", "forme change"),
        "Pokémon state",
    ),
    "SEQ_SE_PL_W363": (
        "Shaymin form change",
        ("shaymin", "form change", "forme change"),
        "Pokémon state",
    ),
}

SOUND_EFFECT_CATALOG_SOURCE_FILES: dict[str, tuple[str, ...]] = {
    "SEQ_SE_DP_NAGERU": ("base/overlay/overlay_0012.bin", "include/constants/sndseq.h"),
    "SEQ_SE_DP_BOWA4": ("base/overlay/overlay_0012.bin", "include/constants/sndseq.h"),
    "SEQ_SE_DP_BOWA2": ("base/overlay/overlay_0012.bin", "include/constants/sndseq.h"),
    "SEQ_SE_DP_BOWA": ("base/overlay/overlay_0007.bin", "include/constants/sndseq.h"),
    "SEQ_SE_DP_GETTING": ("base/overlay/overlay_0012.bin", "include/constants/sndseq.h"),
    "SEQ_SE_DP_KON": ("base/overlay/overlay_0007.bin", "base/overlay/overlay_0012.bin", "include/constants/sndseq.h"),
    "SEQ_SE_DP_KON2": ("base/overlay/overlay_0007.bin", "include/constants/sndseq.h"),
    "SEQ_SE_DP_KON3": ("base/overlay/overlay_0007.bin", "include/constants/sndseq.h"),
    "SEQ_SE_DP_KON4": ("base/overlay/overlay_0007.bin", "include/constants/sndseq.h"),
    "SEQ_SE_DP_PINPON": (
        "data/battle_scripts/subscripts/subscript_0011_THROW_POKEBALL.s",
        "data/battle_scripts/subscripts/subscript_0275_THROW_SAFARI_BALL.s",
    ),
    "SEQ_ME_POKEGET": ("data/text/197.txt", "include/constants/sndseq.h"),
    "SEQ_GS_WIN2": ("base/overlay/overlay_0012.bin", "include/constants/sndseq.h"),
    "SEQ_SE_PL_KIRAKIRA": (
        "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c",
    ),
}


def semantic_sound_alias_label(symbol: str) -> str:
    overworld = symbol.startswith("OW_WILD_")
    stem = symbol.removesuffix("_SE")
    if "_PLAYER_BALL_" in stem:
        stem = "POKE_BALL_" + stem.split("_PLAYER_BALL_", 1)[1]
    elif stem.startswith("OW_WILD_SPAWNER_"):
        stem = stem.removeprefix("OW_WILD_SPAWNER_")
    elif stem.startswith("MAP_"):
        stem = stem.removeprefix("MAP_")
    words = []
    for word in stem.split("_"):
        if word == "POKE":
            words.append("Poké")
        elif word in {"UFO", "PC"}:
            words.append(word)
        else:
            words.append(word.lower())
    label = " ".join(words).capitalize().replace("Poké ball", "Poké Ball")
    return f"Overworld {label}" if overworld else label


def semantic_sound_alias_search_terms(symbol: str, label: str) -> list[str]:
    terms = [label, symbol]
    if re.search(r"(?:^|_)BALL(?:_|$)", symbol):
        terms.extend(("pokeball", "poke ball", "poké ball", "capture"))
    if "CHARGE" in symbol:
        terms.extend(("capture check", "aim pulse"))
    if "BREAKOUT" in symbol:
        terms.extend(("capture failed", "escape from ball"))
    if "CAUGHT" in symbol:
        terms.extend(("capture success", "capture check", "caught"))
    return list(dict.fromkeys(terms))


@lru_cache(maxsize=1)
def source_sound_effect_aliases() -> dict[str, list[dict]]:
    """Return semantic aliases declared by active C sources, grouped by SEQ symbol."""
    aliases: dict[str, dict[str, dict]] = {}
    define_re = re.compile(
        r"^\s*#define\s+([A-Za-z0-9_]+)\s+(SEQ_(?:SE|ME)_[A-Za-z0-9_]+)\s*$",
        flags=re.MULTILINE,
    )
    for source_root in (ROOT / "src", ROOT / "data"):
        if not source_root.exists():
            continue
        paths = sorted(path for pattern in ("*.c", "*.h") for path in source_root.rglob(pattern))
        for path in paths:
            try:
                text = strip_c_comments(join_line_continuations(path.read_text()))
            except (OSError, UnicodeDecodeError):
                continue
            relative = str(path.relative_to(ROOT))
            for alias_symbol, sequence_symbol in define_re.findall(text):
                if alias_symbol.startswith("OW_WILD_") and (
                    "_PLAYER_BALL_" in alias_symbol
                    or "_POKE_BALL_" in alias_symbol
                ):
                    # These are implementation placeholders in the optional
                    # overworld projectile feature, not canonical sound names.
                    continue
                label = semantic_sound_alias_label(alias_symbol)
                category = "Overworld" if alias_symbol.startswith(("OW_WILD_", "MAP_")) else "Source alias"
                by_symbol = aliases.setdefault(sequence_symbol, {})
                alias = by_symbol.setdefault(alias_symbol, {
                    "label": label,
                    "symbol": alias_symbol,
                    "sequenceSymbol": sequence_symbol,
                    "category": category,
                    "kind": "source",
                    "searchTerms": semantic_sound_alias_search_terms(alias_symbol, label),
                    "sourceFiles": [],
                })
                if relative not in alias["sourceFiles"]:
                    alias["sourceFiles"].append(relative)
    return {
        sequence_symbol: sorted(by_symbol.values(), key=lambda alias: (alias["label"], alias["symbol"]))
        for sequence_symbol, by_symbol in aliases.items()
    }


def sound_effect_semantic_aliases() -> dict[str, list[dict]]:
    aliases = source_sound_effect_aliases()
    for sequence_symbol, (label, search_terms, category) in SOUND_EFFECT_CATALOG_ALIASES.items():
        rows = aliases.setdefault(sequence_symbol, [])
        if any(row["label"] == label for row in rows):
            continue
        rows.append({
            "label": label,
            "symbol": sequence_symbol,
            "sequenceSymbol": sequence_symbol,
            "category": category,
            "kind": "catalog",
            "searchTerms": list(search_terms),
            "sourceFiles": list(SOUND_EFFECT_CATALOG_SOURCE_FILES.get(sequence_symbol, ())),
        })
    return aliases


def sound_effect_group_map(info_block: dict) -> dict[int, list[str]]:
    by_id: dict[int, list[str]] = {}
    for group in info_block.get("groupInfo", []):
        name = group.get("name")
        if not name:
            continue
        for entry in group.get("subGroup", []):
            try:
                seq_id = int(entry.get("entry"))
            except (TypeError, ValueError):
                continue
            by_id.setdefault(seq_id, []).append(name)
    return by_id


@lru_cache(maxsize=1)
def move_metadata_by_id() -> dict[int, dict]:
    moves: dict[int, dict] = {}
    if not MOVES_DATA_SOURCE.exists():
        return moves
    constants: dict[str, int] = {}
    if (ROOT / "include/constants/moves.h").exists():
        for match in re.finditer(
            r"^\s*#define\s+(MOVE_[A-Za-z0-9_]+)\s+(\d+)\s*$",
            (ROOT / "include/constants/moves.h").read_text(),
            flags=re.MULTILINE,
        ):
            constants[match.group(1)] = int(match.group(2))
    for match in re.finditer(
        r'^\s*movedata\s+(MOVE_[A-Za-z0-9_]+),\s*"([^"]+)"',
        MOVES_DATA_SOURCE.read_text(),
        flags=re.MULTILINE,
    ):
        symbol, name = match.groups()
        move_id = constants.get(symbol)
        if move_id is None:
            continue
        moves[move_id] = {"id": move_id, "symbol": symbol, "name": name}
    return moves


@lru_cache(maxsize=1)
def move_sound_effect_aliases() -> dict[int, list[dict]]:
    aliases: dict[int, list[dict]] = {}
    moves = move_metadata_by_id()
    if not MOVE_ANIM_DIR.exists():
        return aliases
    command_re = re.compile(r"^\s*(playse|playsepan|playsepanmod|repeatse|waitse|stopse)\s+(.+?)\s*$", re.MULTILINE)
    constants = sound_effect_constants()
    for path in sorted(MOVE_ANIM_DIR.glob("*.s")):
        try:
            move_id = int(path.stem)
        except ValueError:
            continue
        move = moves.get(move_id)
        if not move:
            continue
        text = re.sub(r"//.*", "", path.read_text())
        for command, raw_args in command_re.findall(text):
            args = [part.strip() for part in raw_args.split(",") if part.strip()]
            if not args:
                continue
            raw_seq = args[0]
            if raw_seq.isdigit():
                seq_id = int(raw_seq)
            else:
                seq_id = constants.get(raw_seq)
                if seq_id is None:
                    continue
            aliases.setdefault(seq_id, []).append({
                "moveId": move_id,
                "moveName": move["name"],
                "moveSymbol": move["symbol"],
                "scriptFile": str(path.relative_to(ROOT)),
                "command": command,
                "args": args,
                "commandText": f"{command} {', '.join(args)}",
            })
    for seq_id, rows in aliases.items():
        seen: set[tuple[int, str, str]] = set()
        deduped = []
        for row in rows:
            key = (row["moveId"], row["command"], row["commandText"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        aliases[seq_id] = deduped
    return aliases


def is_extra_sound_sequence_info(name: str, bank: str, file_name: str) -> bool:
    if not name or name.endswith("_END") or file_name == "SEQ_DUMMY.sseq":
        return False
    if name.startswith("SEQ_SE_"):
        return False
    return (
        name in SOUND_EFFECT_CATALOG_ALIASES
        or name.startswith("SEQ_ME_")
        or bank.startswith("BANK_SE_")
    )


def sound_effect_metadata_payload() -> dict:
    constants = sound_effect_constants()
    info_block: dict = {}
    seq_info: list[dict] = []
    groups_by_id: dict[int, list[str]] = {}
    move_aliases_by_seq_id = move_sound_effect_aliases()
    semantic_aliases_by_name = sound_effect_semantic_aliases()
    if SDAT_INFO_BLOCK.exists():
        info_block = json.loads(SDAT_INFO_BLOCK.read_text())
        seq_info = info_block.get("seqInfo", [])
        groups_by_id = sound_effect_group_map(info_block)

    first_id = constants.get("SEQ_SE_PL_W012")
    end_id = constants.get("SEQ_SE_END")
    initial_id = constants.get("SEQ_SE_DP_SELECT")
    rows: list[dict] = []
    included_ids: set[int] = set()

    def is_move_sound_effect_name(name: str) -> bool:
        return bool(
            re.match(r"^SEQ_SE_(?:PL|DP|GS)_W\d", name)
            or name in {
                "SEQ_SE_PL_FIRE",
                "SEQ_SE_PL_WATER",
                "SEQ_SE_PL_ELECTRO",
                "SEQ_SE_PL_WHIP",
            }
        )

    def row_for_sequence(seq_id: int, name: str, info: dict, *, is_sound_effect: bool) -> dict:
        file_name = info.get("fileName") or f"{name}.sseq"
        seq_path = SDAT_SEQ_DIR / file_name
        short_name = name.removeprefix("SEQ_SE_") if name.startswith("SEQ_SE_") else name.removeprefix("SEQ_")
        return {
            "id": seq_id,
            "name": name,
            "shortName": short_name,
            "fileName": file_name,
            "bank": info.get("bnk") or "",
            "player": info.get("ply") or "",
            "volume": info.get("vol"),
            "channelPriority": info.get("cpr"),
            "playerPriority": info.get("ppr"),
            "groups": groups_by_id.get(seq_id, []),
            "hasSseq": seq_path.exists(),
            "sseqBytes": seq_path.stat().st_size if seq_path.exists() else None,
            "isSoundEffect": is_sound_effect,
            "isMoveSoundEffect": is_move_sound_effect_name(name) or bool(move_aliases_by_seq_id.get(seq_id)),
            "moveAliases": move_aliases_by_seq_id.get(seq_id, []),
            "semanticAliases": semantic_aliases_by_name.get(name, []),
            "inTesterRange": (
                first_id is not None
                and end_id is not None
                and first_id <= seq_id < end_id
            ),
        }

    def is_extra_sound_sequence(seq_id: int, info: dict) -> bool:
        name = info.get("name") or ""
        bank = info.get("bnk") or ""
        file_name = info.get("fileName") or ""
        if seq_id in included_ids or name.startswith("SEQ_SE_"):
            return False
        return is_extra_sound_sequence_info(name, bank, file_name)

    for name, seq_id in sorted(constants.items(), key=lambda item: (item[1], item[0])):
        if name == "SEQ_SE_END":
            continue
        info = seq_info[seq_id] if 0 <= seq_id < len(seq_info) else {}
        rows.append(row_for_sequence(seq_id, name, info, is_sound_effect=True))
        included_ids.add(seq_id)

    for seq_id, info in enumerate(seq_info):
        if is_extra_sound_sequence(seq_id, info):
            rows.append(row_for_sequence(seq_id, info["name"], info, is_sound_effect=False))

    return {
        "effects": sorted(rows, key=lambda row: (row["id"], row["name"])),
        "count": len(rows),
        "source": str(SNDSEQ_HEADER.relative_to(ROOT)),
        "infoBlock": str(SDAT_INFO_BLOCK.relative_to(ROOT)) if SDAT_INFO_BLOCK.exists() else None,
        "tester": {
            "first": first_id,
            "end": end_id,
            "initial": initial_id,
        },
    }


ADPCM_INDEX_TABLE = (-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8)
ADPCM_STEP_TABLE = (
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31,
    34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97, 107, 118, 130,
    143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449,
    494, 544, 598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411,
    1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026,
    4428, 4871, 5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442,
    11487, 12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623,
    27086, 29794, 32767,
)


@lru_cache(maxsize=1)
def sdat_info_block() -> dict:
    if not SDAT_INFO_BLOCK.exists():
        raise FileNotFoundError(f"{SDAT_INFO_BLOCK.relative_to(ROOT)} is missing")
    return json.loads(SDAT_INFO_BLOCK.read_text())


@lru_cache(maxsize=1)
def sdat_bank_info_by_name() -> dict[str, dict]:
    return {
        entry.get("name"): entry
        for entry in sdat_info_block().get("bankInfo", [])
        if entry.get("name")
    }


@lru_cache(maxsize=64)
def load_sseq_events(file_name: str) -> list:
    import ndspy.soundSequence as sound_sequence

    path = SDAT_SEQ_DIR / file_name
    if not path.exists():
        raise FileNotFoundError(f"{path.relative_to(ROOT)} is missing")
    sequence = sound_sequence.SSEQ.fromFile(path)
    sequence.parse()
    return sequence.events


@lru_cache(maxsize=64)
def load_sbnk(bank_name: str):
    import ndspy.soundBank as sound_bank

    bank_info = sdat_bank_info_by_name().get(bank_name)
    file_name = (bank_info or {}).get("fileName") or f"{bank_name}.sbnk"
    path = SDAT_BANK_DIR / file_name
    if not path.exists():
        raise FileNotFoundError(f"{path.relative_to(ROOT)} is missing")
    return sound_bank.SBNK.fromFile(path)


@lru_cache(maxsize=128)
def load_wavarc(archive_name: str) -> tuple:
    import ndspy.soundWave as sound_wave
    import ndspy.soundWaveArchive as sound_wave_archive

    swar_path = SDAT_WAVARC_DIR / f"{archive_name}.swar"
    if swar_path.exists():
        return tuple(sound_wave_archive.SWAR.fromFile(swar_path).waves)

    archive_dir = SDAT_WAVARC_DIR / archive_name
    if not archive_dir.exists():
        raise FileNotFoundError(f"Wave archive {archive_name} is missing")

    waves = []
    for swav_path in sorted(archive_dir.glob("*.swav")):
        waves.append(sound_wave.SWAV.fromFile(swav_path))
    return tuple(waves)


@lru_cache(maxsize=512)
def decoded_swav_sample(archive_name: str, wave_id: int) -> tuple[tuple[int, ...], int, bool, int]:
    waves = load_wavarc(archive_name)
    if wave_id < 0 or wave_id >= len(waves):
        raise IndexError(f"{archive_name} does not contain SWAV {wave_id}")
    swav = waves[wave_id]
    samples = decode_swav_samples(swav)
    loop_start = swav_word_offset_to_sample_offset(swav, int(swav.loopOffset))
    return tuple(samples), int(swav.sampleRate), bool(swav.isLooped), loop_start


def decode_swav_samples(swav) -> list[int]:
    wave_type = int(swav.waveType)
    if wave_type == 0:
        samples = [max(-32768, min(32767, (byte if byte < 128 else byte - 256) << 8)) for byte in swav.data]
    elif wave_type == 1:
        sample_count = len(swav.data) // 2
        samples = list(struct.unpack(f"<{sample_count}h", swav.data[: sample_count * 2]))
    elif wave_type == 2:
        samples = decode_adpcm_samples(swav.data)
    else:
        raise ValueError(f"Unsupported SWAV wave type {wave_type}")
    logical_length = swav_word_offset_to_sample_offset(swav, int(swav.totalLength))
    return samples[:logical_length] if logical_length > 0 else samples


def swav_word_offset_to_sample_offset(swav, word_offset: int) -> int:
    word_offset = max(0, int(word_offset))
    wave_type = int(swav.waveType)
    if wave_type == 0:
        return word_offset * 4
    if wave_type == 1:
        return word_offset * 2
    if wave_type == 2:
        return 0 if word_offset == 0 else 1 + (word_offset - 1) * 8
    return word_offset


def decode_adpcm_samples(data: bytes) -> list[int]:
    if len(data) < 4:
        return []
    predictor = struct.unpack_from("<h", data, 0)[0]
    step_index = max(0, min(88, data[2]))
    samples = [predictor]
    for byte in data[4:]:
        for nibble in (byte & 0x0F, byte >> 4):
            step = ADPCM_STEP_TABLE[step_index]
            diff = step >> 3
            if nibble & 1:
                diff += step >> 2
            if nibble & 2:
                diff += step >> 1
            if nibble & 4:
                diff += step
            predictor = predictor - diff if nibble & 8 else predictor + diff
            predictor = max(-32768, min(32767, predictor))
            step_index = max(0, min(88, step_index + ADPCM_INDEX_TABLE[nibble]))
            samples.append(predictor)
    return samples


def note_definition_for_pitch(instrument, pitch: int):
    if instrument is None:
        return None
    if hasattr(instrument, "noteDefinition"):
        return instrument.noteDefinition
    if hasattr(instrument, "noteDefinitions"):
        index = max(0, min(len(instrument.noteDefinitions) - 1, pitch - instrument.firstPitch))
        return instrument.noteDefinitions[index]
    if hasattr(instrument, "regions"):
        for region in instrument.regions:
            if pitch <= region.lastPitch:
                return region.noteDefinition
        return instrument.regions[-1].noteDefinition if instrument.regions else None
    return None


def sseq_track_event_slices(events: list) -> list[list]:
    import ndspy.soundSequence as sound_sequence

    event_index_by_id = {id(event): index for index, event in enumerate(events)}
    starts: list[int] = []
    index = 0
    if events and isinstance(events[0], sound_sequence.DefineTracksSequenceEvent):
        index = 1
    while index < len(events) and isinstance(events[index], sound_sequence.BeginTrackSequenceEvent):
        target = event_index_by_id.get(id(events[index].firstEvent))
        if target is not None:
            starts.append(target)
        index += 1
    if index < len(events) and not isinstance(events[index], sound_sequence.RawDataSequenceEvent):
        starts.append(index)
    if not starts:
        return []
    starts = sorted(set(starts))
    slices: list[list] = []
    for start in starts:
        slices.append(expand_sseq_track_events(events, start, event_index_by_id))
    return slices


def expand_sseq_track_events(events: list, start: int, event_index_by_id: dict[int, int]) -> list:
    import ndspy.soundSequence as sound_sequence

    expanded = []
    call_stack: list[int] = []
    loop_stack: list[tuple[int, int]] = []
    pc = start
    steps = 0
    elapsed_ticks = 0
    max_steps = 20000
    max_ticks = int(SOUND_RENDER_MAX_SECONDS * 240 * SSEQ_TICKS_PER_QUARTER / 60)
    loop_visits: dict[int, int] = {}
    while 0 <= pc < len(events) and steps < max_steps and elapsed_ticks <= max_ticks:
        event = events[pc]
        steps += 1
        if isinstance(event, sound_sequence.RawDataSequenceEvent):
            break
        expanded.append(event)
        if isinstance(event, sound_sequence.BeginLoopSequenceEvent):
            loop_count = int(event.loopCount)
            loop_stack.append((pc + 1, loop_count if loop_count > 0 else 32))
            pc += 1
        elif isinstance(event, sound_sequence.EndLoopSequenceEvent):
            if loop_stack:
                loop_start, remaining = loop_stack[-1]
                if remaining > 1:
                    loop_stack[-1] = (loop_start, remaining - 1)
                    pc = loop_start
                else:
                    loop_stack.pop()
                    pc += 1
            else:
                pc += 1
        elif isinstance(event, sound_sequence.RestSequenceEvent):
            elapsed_ticks += int(event.duration)
            pc += 1
        elif isinstance(event, sound_sequence.CallSequenceEvent):
            target = event_index_by_id.get(id(event.destination))
            if target is None:
                pc += 1
            else:
                call_stack.append(pc + 1)
                pc = target
        elif isinstance(event, sound_sequence.ReturnSequenceEvent):
            if not call_stack:
                break
            pc = call_stack.pop()
        elif isinstance(event, sound_sequence.JumpSequenceEvent):
            target = event_index_by_id.get(id(event.destination))
            if target is None:
                pc += 1
            else:
                loop_visits[target] = loop_visits.get(target, 0) + 1
                if loop_visits[target] > 24:
                    break
                pc = target
        elif isinstance(event, sound_sequence.EndTrackSequenceEvent):
            break
        else:
            pc += 1
    return expanded


def first_sseq_tempo(events: list) -> int:
    import ndspy.soundSequence as sound_sequence

    for event in events:
        if isinstance(event, sound_sequence.TempoSequenceEvent):
            return max(1, int(event.value))
    return 120


def ticks_to_samples(ticks: int, tempo: int) -> int:
    seconds = max(0, ticks) * 60.0 / (max(1, tempo) * SSEQ_TICKS_PER_QUARTER)
    return int(round(seconds * SOUND_RENDER_SAMPLE_RATE))


def frames_to_samples(frames: int | float) -> int:
    seconds = max(0.0, float(frames)) / MOVE_SOUND_FRAME_RATE
    return int(round(seconds * SOUND_RENDER_SAMPLE_RATE))


def sseq_global_tempo_points(track_slices: list[list], initial_tempo: int) -> list[tuple[int, int]]:
    import ndspy.soundSequence as sound_sequence

    points: list[tuple[int, int]] = [(0, max(1, int(initial_tempo)))]
    for track_events in track_slices:
        cursor = 0
        tempo = max(1, int(initial_tempo))
        note_wait = False
        for event in track_events:
            if isinstance(event, sound_sequence.TempoSequenceEvent):
                tempo = max(1, int(event.value))
                points.append((cursor, tempo))
            elif isinstance(event, sound_sequence.RestSequenceEvent):
                cursor += ticks_to_samples(int(event.duration), tempo)
            elif isinstance(event, sound_sequence.NoteSequenceEvent):
                if note_wait:
                    cursor += ticks_to_samples(int(event.duration), tempo)
            elif isinstance(event, sound_sequence.MonoPolySequenceEvent):
                note_wait = bool(int(event.value))
            elif isinstance(event, sound_sequence.EndTrackSequenceEvent):
                break
    points.sort(key=lambda item: item[0])
    deduped: list[tuple[int, int]] = []
    for sample_offset, tempo in points:
        if deduped and deduped[-1][0] == sample_offset:
            deduped[-1] = (sample_offset, tempo)
        else:
            deduped.append((sample_offset, tempo))
    return deduped


def tempo_at_sample(points: list[tuple[int, int]], sample_offset: int, fallback: int) -> int:
    tempo = max(1, int(fallback))
    for point_sample, point_tempo in points:
        if point_sample > sample_offset:
            break
        tempo = max(1, int(point_tempo))
    return tempo


def signed8(value: int) -> int:
    value = int(value) & 0xFF
    return value - 0x100 if value & 0x80 else value


def signed16(value: int) -> int:
    value = int(value) & 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def deterministic_random_value(event) -> int:
    return int(round((int(event.randMin) + int(event.randMax)) / 2))


def nds_sequence_gain(value: int | float) -> float:
    """Convert a Nitro sequence volume byte to its decibel-square gain."""
    normalized = max(0.0, min(1.0, float(value) / 127.0))
    return normalized * normalized


def nds_attack_coefficient(value: int) -> int:
    value = max(0, min(127, int(value)))
    if value < 109:
        return 255 - value
    return (0, 1, 5, 14, 26, 38, 51, 63, 73, 84, 92, 100, 109, 116, 123, 127, 132, 137, 143)[127 - value]


def nds_decay_step(value: int) -> int:
    value = max(0, min(127, int(value)))
    if value == 127:
        return 0xFFFF
    if value == 126:
        return 0x3C00
    if value < 50:
        return value * 2 + 1
    return 0x1E00 // (126 - value)


def nds_sustain_attenuation(value: int) -> int:
    value = max(0, min(127, int(value)))
    if value == 0:
        return -92544
    centibels = max(-722, round(400 * math.log10(value / 127.0)))
    return centibels * 128


def nds_envelope_points(
    note_def,
    key_off_sample: int,
    total_samples: int,
    attack: int | None = None,
    decay: int | None = None,
    sustain: int | None = None,
    release: int | None = None,
) -> list[tuple[int, float]]:
    """Approximate Nitro's 192 Hz attack/decay/sustain/release channel state."""
    attack_coefficient = nds_attack_coefficient(note_def.attack if attack is None else attack)
    decay_step = nds_decay_step(note_def.decay if decay is None else decay)
    sustain_attenuation = nds_sustain_attenuation(note_def.sustain if sustain is None else sustain)
    release_step = nds_decay_step(note_def.release if release is None else release)
    heartbeat_samples = SOUND_RENDER_SAMPLE_RATE / NDS_SOUND_HEARTBEAT_RATE
    attenuation = -92544
    state = "attack"
    points: list[tuple[int, float]] = []
    heartbeat = 0
    while True:
        sample_offset = int(round(heartbeat * heartbeat_samples))
        if sample_offset >= total_samples:
            break
        if sample_offset >= key_off_sample:
            state = "release"
        if state == "attack":
            attenuation = -((-attenuation * attack_coefficient) >> 8)
            if attenuation == 0:
                state = "decay"
        elif state == "decay":
            attenuation = max(sustain_attenuation, attenuation - decay_step)
            if attenuation <= sustain_attenuation:
                state = "sustain"
        elif state == "release":
            attenuation = max(-92544, attenuation - release_step)
        gain = 10 ** (attenuation / 25600.0)
        if state == "release" and attenuation <= -92544:
            gain = 0.0
        points.append((sample_offset, gain))
        if state == "release" and attenuation <= -92544:
            break
        heartbeat += 1
    return points or [(0, 1.0)]


def pitch_at_sample(pitch_points: list[tuple[int, float]], sample_index: int, point_index: int) -> tuple[float, int]:
    while point_index + 1 < len(pitch_points) and sample_index >= pitch_points[point_index + 1][0]:
        point_index += 1
    return pitch_points[point_index][1], point_index


def render_psg_note(
    note_def,
    pitch: float,
    duration_samples: int,
    pitch_points: list[tuple[int, float]] | None = None,
    release_rate: int | None = None,
) -> list[int]:
    import ndspy.soundBank as sound_bank

    if duration_samples <= 0:
        duration_samples = int(0.08 * SOUND_RENDER_SAMPLE_RATE)
    pitch_points = pitch_points or [(0, pitch)]
    release_step = nds_decay_step(note_def.release if release_rate is None else release_rate)
    release_heartbeats = max(1, math.ceil(92544 / max(1, release_step)))
    release_samples = int(math.ceil(release_heartbeats * SOUND_RENDER_SAMPLE_RATE / NDS_SOUND_HEARTBEAT_RATE))
    output_samples = min(
        int(SOUND_RENDER_MAX_SECONDS * SOUND_RENDER_SAMPLE_RATE),
        duration_samples + release_samples,
    )
    if note_def.type == sound_bank.NoteType.PSG_WHITE_NOISE:
        seed = (int(round(pitch * 256)) * 1103515245 + duration_samples) & 0x7FFFFFFF
        out = []
        for _index in range(output_samples):
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            out.append(int(((seed & 0xFFFF) - 32768) * 0.42))
        return out

    duty_options = (0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 0.0)
    duty = duty_options[int(note_def.dutyCycle) & 7]
    out = []
    phase = 0.0
    point_index = 0
    for index in range(output_samples):
        current_pitch, point_index = pitch_at_sample(pitch_points, index, point_index)
        frequency = 440.0 * (2 ** ((current_pitch - 69) / 12))
        phase = (phase + frequency / SOUND_RENDER_SAMPLE_RATE) % 1.0
        out.append(18000 if phase < duty else -18000)
    return out


def render_pcm_note(
    note_def,
    wave_archives: list[str],
    pitch: float,
    duration_samples: int,
    pitch_points: list[tuple[int, float]] | None = None,
    release_rate: int | None = None,
) -> list[int]:
    archive_index = int(note_def.waveArchiveIDID)
    if archive_index < 0 or archive_index >= len(wave_archives) or not wave_archives[archive_index]:
        raise ValueError(f"Instrument uses missing wave archive slot {archive_index}")
    archive_name = wave_archives[archive_index]
    source, source_rate, is_looped, loop_start = decoded_swav_sample(archive_name, int(note_def.waveID))
    if not source:
        return []

    pitch_points = pitch_points or [(0, pitch)]
    initial_pitch = pitch_points[0][1]
    initial_pitch_ratio = 2 ** ((initial_pitch - int(note_def.pitch)) / 12)
    initial_source_step = max(0.01, source_rate * initial_pitch_ratio / SOUND_RENDER_SAMPLE_RATE)
    source_duration = int(len(source) / initial_source_step)
    release_step = nds_decay_step(note_def.release if release_rate is None else release_rate)
    release_heartbeats = max(1, math.ceil(92544 / max(1, release_step)))
    release_samples = int(math.ceil(release_heartbeats * SOUND_RENDER_SAMPLE_RATE / NDS_SOUND_HEARTBEAT_RATE))
    if is_looped:
        out_len = max(duration_samples + release_samples, int(0.035 * SOUND_RENDER_SAMPLE_RATE))
    else:
        # A Nitro note duration marks key-off; it does not truncate a one-shot
        # SWAV. The channel continues through the source while its SBNK release
        # envelope runs. Cutting at duration + 18 ms removed most of short,
        # low-pitched effects such as the successful-capture click.
        out_len = int(SOUND_RENDER_MAX_SECONDS * SOUND_RENDER_SAMPLE_RATE)
    out_len = min(out_len, int(SOUND_RENDER_MAX_SECONDS * SOUND_RENDER_SAMPLE_RATE))

    out = []
    source_pos = 0.0
    loop_start = max(0, min(len(source) - 1, int(loop_start)))
    point_index = 0
    for output_index in range(out_len):
        index = int(source_pos)
        if index >= len(source):
            if is_looped and loop_start < len(source) - 2:
                loop_len = max(1, len(source) - loop_start)
                index = loop_start + ((index - loop_start) % loop_len)
                source_pos = float(index)
            else:
                break
        next_index = min(index + 1, len(source) - 1)
        frac = source_pos - index
        out.append(int(source[index] * (1.0 - frac) + source[next_index] * frac))
        current_pitch, point_index = pitch_at_sample(pitch_points, output_index, point_index)
        pitch_ratio = 2 ** ((current_pitch - int(note_def.pitch)) / 12)
        source_step = max(0.01, source_rate * pitch_ratio / SOUND_RENDER_SAMPLE_RATE)
        source_pos += source_step
    return out


def clamp_pan(value: int) -> int:
    return max(0, min(127, int(value)))


def combine_pan(track_pan: int, note_pan: int) -> int:
    return clamp_pan(int(track_pan) + int(note_pan) - 64)


def stereo_pan_gains(pan: int) -> tuple[float, float]:
    position = clamp_pan(pan) / 127.0
    return math.cos(position * math.pi / 2.0), math.sin(position * math.pi / 2.0)


def mix_note_into(
    mix_left: list[float],
    mix_right: list[float],
    start: int,
    samples: list[int],
    gain: float,
    pan: int,
    control_points: list[tuple[int, float, int]] | None = None,
    envelope_points: list[tuple[int, float]] | None = None,
) -> None:
    if not samples:
        return
    control_points = control_points or [(0, gain, pan)]
    audible_length = len(samples)
    if envelope_points and envelope_points[-1][1] <= 0.0:
        audible_length = min(audible_length, envelope_points[-1][0])
    if audible_length <= 0:
        return
    needed = start + audible_length
    if needed > len(mix_left):
        mix_left.extend([0.0] * (needed - len(mix_left)))
    if needed > len(mix_right):
        mix_right.extend([0.0] * (needed - len(mix_right)))
    control_index = 0
    envelope_index = 0
    for index, sample in enumerate(samples[:audible_length]):
        while control_index + 1 < len(control_points) and index >= control_points[control_index + 1][0]:
            control_index += 1
        while envelope_points and envelope_index + 1 < len(envelope_points) and index >= envelope_points[envelope_index + 1][0]:
            envelope_index += 1
        _, current_gain, current_pan = control_points[control_index]
        left_gain, right_gain = stereo_pan_gains(current_pan)
        envelope = envelope_points[envelope_index][1] if envelope_points else 1.0
        value = sample * current_gain * envelope
        mix_left[start + index] += value * left_gain
        mix_right[start + index] += value * right_gain


def stereo_samples_to_wav(mix_left: list[float], mix_right: list[float], *, max_seconds: float = SOUND_RENDER_MAX_SECONDS) -> bytes:
    max_len = int(max_seconds * SOUND_RENDER_SAMPLE_RATE)
    mix_left = mix_left[:max_len]
    mix_right = mix_right[:max_len]
    length = max(len(mix_left), len(mix_right))
    if len(mix_left) < length:
        mix_left.extend([0.0] * (length - len(mix_left)))
    if len(mix_right) < length:
        mix_right.extend([0.0] * (length - len(mix_right)))
    peak = max(1.0, max(abs(value) for value in mix_left + mix_right))
    scale = min(1.0, 30000.0 / peak)
    pcm = bytearray()
    for left_value, right_value in zip(mix_left, mix_right):
        left_sample = int(max(-32768, min(32767, left_value * scale)))
        right_sample = int(max(-32768, min(32767, right_value * scale)))
        pcm.extend(struct.pack("<hh", left_sample, right_sample))

    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SOUND_RENDER_SAMPLE_RATE)
        wav.writeframes(bytes(pcm))
    return out.getvalue()


def rendered_wav_to_stereo_samples(data: bytes) -> tuple[list[float], list[float]]:
    with wave.open(io.BytesIO(data), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        frame_rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())
    if sample_width != 2:
        raise ValueError("Rendered sound uses an unsupported sample width")
    raw = struct.unpack("<" + "h" * (len(frames) // 2), frames)
    if channels == 1:
        left = [float(value) for value in raw]
        right = left.copy()
    elif channels == 2:
        left = [float(raw[index]) for index in range(0, len(raw), 2)]
        right = [float(raw[index]) for index in range(1, len(raw), 2)]
    else:
        raise ValueError("Rendered sound uses an unsupported channel count")
    if frame_rate != SOUND_RENDER_SAMPLE_RATE:
        raise ValueError("Rendered sound uses an unexpected sample rate")
    return left, right


def external_pan_to_ds_pan(value: int) -> int:
    value = max(-117, min(117, int(value)))
    return int(round((value + 117) * 127 / 234))


def mix_stereo_clip_into(
    mix_left: list[float],
    mix_right: list[float],
    start: int,
    clip_left: list[float],
    clip_right: list[float],
    pan: int = 0,
    stop_sample: int | None = None,
) -> None:
    if not clip_left and not clip_right:
        return
    length = max(len(clip_left), len(clip_right))
    if stop_sample is not None:
        length = min(length, max(0, stop_sample - start))
    if length <= 0:
        return
    needed = start + length
    if needed > len(mix_left):
        mix_left.extend([0.0] * (needed - len(mix_left)))
    if needed > len(mix_right):
        mix_right.extend([0.0] * (needed - len(mix_right)))
    left_gain, right_gain = stereo_pan_gains(external_pan_to_ds_pan(pan))
    for index in range(length):
        left_value = clip_left[index] if index < len(clip_left) else 0.0
        right_value = clip_right[index] if index < len(clip_right) else 0.0
        mix_left[start + index] += left_value * left_gain
        mix_right[start + index] += right_value * right_gain


def note_pitch_points(
    track_events: list,
    start_index: int,
    base_pitch: float,
    start_tempo: int,
    pitch_bend: int,
    pitch_bend_range: int,
    duration_samples: int,
    note_wait: bool = False,
) -> list[tuple[int, float]]:
    import ndspy.soundSequence as sound_sequence

    points: list[tuple[int, float]] = [(0, base_pitch + (pitch_bend * pitch_bend_range / 128.0))]
    elapsed = duration_samples if note_wait else 0
    tempo = start_tempo
    current_bend = pitch_bend
    current_range = pitch_bend_range
    current_note_wait = note_wait
    for event in track_events[start_index + 1:]:
        if elapsed >= duration_samples:
            break
        if isinstance(event, sound_sequence.RestSequenceEvent):
            elapsed += ticks_to_samples(int(event.duration), tempo)
        elif isinstance(event, sound_sequence.NoteSequenceEvent):
            if current_note_wait:
                elapsed += ticks_to_samples(int(event.duration), tempo)
        elif isinstance(event, sound_sequence.TempoSequenceEvent):
            tempo = max(1, int(event.value))
        elif isinstance(event, sound_sequence.MonoPolySequenceEvent):
            current_note_wait = bool(int(event.value))
        elif isinstance(event, sound_sequence.RandomSequenceEvent):
            if event.subType == 0xC4:
                current_bend = signed8(deterministic_random_value(event))
                points.append((min(elapsed, duration_samples), base_pitch + (current_bend * current_range / 128.0)))
            elif event.subType == 0xC5:
                current_range = max(0, deterministic_random_value(event))
                points.append((min(elapsed, duration_samples), base_pitch + (current_bend * current_range / 128.0)))
        elif isinstance(event, sound_sequence.PortamentoRangeSequenceEvent):
            current_range = max(0, int(event.value))
            points.append((min(elapsed, duration_samples), base_pitch + (current_bend * current_range / 128.0)))
        elif isinstance(event, sound_sequence.PortamentoSequenceEvent):
            current_bend = signed8(int(event.value))
            points.append((min(elapsed, duration_samples), base_pitch + (current_bend * current_range / 128.0)))
        elif isinstance(event, sound_sequence.EndTrackSequenceEvent):
            break
    deduped: list[tuple[int, float]] = []
    for sample_offset, pitch in points:
        if deduped and deduped[-1][0] == sample_offset:
            deduped[-1] = (sample_offset, pitch)
        else:
            deduped.append((sample_offset, pitch))
    return deduped


def add_pitch_vibrato_points(
    pitch_points: list[tuple[int, float]],
    duration_samples: int,
    depth: int,
    speed: int,
    vibrato_range: int,
    delay: int,
) -> list[tuple[int, float]]:
    if depth <= 0 or speed <= 0 or vibrato_range <= 0:
        return pitch_points
    heartbeat_samples = SOUND_RENDER_SAMPLE_RATE / NDS_SOUND_HEARTBEAT_RATE
    max_samples = int(SOUND_RENDER_MAX_SECONDS * SOUND_RENDER_SAMPLE_RATE)
    phase = 0
    base_index = 0
    combined = list(pitch_points)
    heartbeat = 0
    while True:
        sample_offset = int(round(heartbeat * heartbeat_samples))
        if sample_offset >= max_samples:
            break
        base_pitch, base_index = pitch_at_sample(pitch_points, sample_offset, base_index)
        if heartbeat < delay:
            adjustment = 0.0
        else:
            sine_value = math.sin((phase / 32768.0) * math.tau) * 127.0
            adjustment_64ths = math.trunc(sine_value * vibrato_range * depth / 256.0)
            adjustment = adjustment_64ths / 64.0
            phase = (phase + (speed << 6)) & 0x7FFF
        combined.append((sample_offset, base_pitch + adjustment))
        heartbeat += 1
    combined.sort(key=lambda item: item[0])
    deduped: list[tuple[int, float]] = []
    for sample_offset, pitch in combined:
        if deduped and deduped[-1][0] == sample_offset:
            deduped[-1] = (sample_offset, pitch)
        else:
            deduped.append((sample_offset, pitch))
    return deduped


def add_sweep_pitch_points(
    pitch_points: list[tuple[int, float]],
    duration_samples: int,
    duration_ticks: int,
    sweep_pitch: int,
) -> list[tuple[int, float]]:
    sweep_pitch = signed16(sweep_pitch)
    duration_ticks = max(0, int(duration_ticks))
    if sweep_pitch == 0 or duration_ticks == 0:
        return pitch_points
    base_index = 0
    combined = list(pitch_points)
    for tick in range(duration_ticks + 1):
        sample_offset = int(round(duration_samples * tick / duration_ticks))
        base_pitch, base_index = pitch_at_sample(pitch_points, sample_offset, base_index)
        adjustment = (sweep_pitch * (duration_ticks - tick) / duration_ticks) / 64.0
        combined.append((sample_offset, base_pitch + adjustment))
    combined.sort(key=lambda item: item[0])
    deduped: list[tuple[int, float]] = []
    for sample_offset, pitch in combined:
        if deduped and deduped[-1][0] == sample_offset:
            deduped[-1] = (sample_offset, pitch)
        else:
            deduped.append((sample_offset, pitch))
    return deduped


def note_control_points(
    track_events: list,
    start_index: int,
    start_tempo: int,
    base_gain: float,
    track_volume: int,
    expression: int,
    pan: int,
    note_pan: int,
    duration_samples: int,
    note_wait: bool = False,
) -> list[tuple[int, float, int]]:
    import ndspy.soundSequence as sound_sequence

    def gain_for(volume: int, expr: int) -> float:
        return base_gain * nds_sequence_gain(volume) * nds_sequence_gain(expr)

    points: list[tuple[int, float, int]] = [(0, gain_for(track_volume, expression), combine_pan(pan, note_pan))]
    elapsed = duration_samples if note_wait else 0
    tempo = start_tempo
    current_volume = track_volume
    current_expression = expression
    current_pan = pan
    current_note_wait = note_wait
    for event in track_events[start_index + 1:]:
        if elapsed >= duration_samples:
            break
        if isinstance(event, sound_sequence.RestSequenceEvent):
            elapsed += ticks_to_samples(int(event.duration), tempo)
        elif isinstance(event, sound_sequence.NoteSequenceEvent):
            if current_note_wait:
                elapsed += ticks_to_samples(int(event.duration), tempo)
        elif isinstance(event, sound_sequence.TempoSequenceEvent):
            tempo = max(1, int(event.value))
        elif isinstance(event, sound_sequence.MonoPolySequenceEvent):
            current_note_wait = bool(int(event.value))
        elif isinstance(event, sound_sequence.RandomSequenceEvent):
            random_value = deterministic_random_value(event)
            if event.subType == 0xC0:
                current_pan = random_value
                points.append((min(elapsed, duration_samples), gain_for(current_volume, current_expression), combine_pan(current_pan, note_pan)))
            elif event.subType == 0xC1:
                current_volume = random_value
                points.append((min(elapsed, duration_samples), gain_for(current_volume, current_expression), combine_pan(current_pan, note_pan)))
            elif event.subType == 0xD5:
                current_expression = random_value
                points.append((min(elapsed, duration_samples), gain_for(current_volume, current_expression), combine_pan(current_pan, note_pan)))
        elif isinstance(event, sound_sequence.TrackVolumeSequenceEvent):
            current_volume = int(event.value)
            points.append((min(elapsed, duration_samples), gain_for(current_volume, current_expression), combine_pan(current_pan, note_pan)))
        elif isinstance(event, sound_sequence.ExpressionSequenceEvent):
            current_expression = int(event.value)
            points.append((min(elapsed, duration_samples), gain_for(current_volume, current_expression), combine_pan(current_pan, note_pan)))
        elif isinstance(event, sound_sequence.PanSequenceEvent):
            current_pan = int(event.value)
            points.append((min(elapsed, duration_samples), gain_for(current_volume, current_expression), combine_pan(current_pan, note_pan)))
        elif isinstance(event, sound_sequence.EndTrackSequenceEvent):
            break
    deduped: list[tuple[int, float, int]] = []
    for sample_offset, gain, point_pan in points:
        if deduped and deduped[-1][0] == sample_offset:
            deduped[-1] = (sample_offset, gain, point_pan)
        else:
            deduped.append((sample_offset, gain, point_pan))
    return deduped


@lru_cache(maxsize=256)
def render_sound_effect_wav(seq_id: int) -> bytes:
    import ndspy.soundBank as sound_bank
    import ndspy.soundSequence as sound_sequence

    seq_info = sdat_info_block().get("seqInfo", [])
    if seq_id < 0 or seq_id >= len(seq_info) or not seq_info[seq_id]:
        raise KeyError(f"No SDAT sequence info for sound effect {seq_id}")

    info = seq_info[seq_id]
    name = info.get("name") or ""
    if not name.startswith("SEQ_SE_") and not is_extra_sound_sequence_info(name, info.get("bnk") or "", info.get("fileName") or ""):
        raise ValueError(f"{name or seq_id} is not included in the sound-effect tester")
    events = load_sseq_events(info["fileName"])
    bank_name = info.get("bnk") or ""
    bank = load_sbnk(bank_name)
    bank_info = sdat_bank_info_by_name().get(bank_name, {})
    wave_archives = [name for name in bank_info.get("wa", [])]
    sequence_volume = info.get("vol")
    sequence_gain = nds_sequence_gain(100 if sequence_volume is None else sequence_volume) * 0.75
    mix_left: list[float] = []
    mix_right: list[float] = []
    global_tempo = first_sseq_tempo(events)
    track_slices = sseq_track_event_slices(events)
    global_tempo_points = sseq_global_tempo_points(track_slices, global_tempo)

    for track_events in track_slices:
        tempo = global_tempo
        instrument_id = 0
        track_volume = 127
        global_volume = 127
        expression = 127
        pan = 64
        pitch_bend = 0
        pitch_bend_range = 2
        transpose = 0
        note_wait = False
        vibrato_depth = 0
        vibrato_speed = 16
        vibrato_range = 1
        vibrato_type = 0
        vibrato_delay = 0
        sweep_pitch = 0
        attack_rate: int | None = None
        decay_rate: int | None = None
        sustain_rate: int | None = None
        release_rate: int | None = None
        cursor = 0
        for event_index, event in enumerate(track_events):
            if isinstance(event, sound_sequence.TempoSequenceEvent):
                tempo = max(1, int(event.value))
            elif isinstance(event, sound_sequence.InstrumentSwitchSequenceEvent):
                instrument_id = int(event.instrumentID)
            elif isinstance(event, sound_sequence.TrackVolumeSequenceEvent):
                track_volume = int(event.value)
            elif isinstance(event, sound_sequence.GlobalVolumeSequenceEvent):
                global_volume = int(event.value)
            elif isinstance(event, sound_sequence.ExpressionSequenceEvent):
                expression = int(event.value)
            elif isinstance(event, sound_sequence.PanSequenceEvent):
                pan = int(event.value)
            elif isinstance(event, sound_sequence.TransposeSequenceEvent):
                transpose = signed8(int(event.value))
            elif isinstance(event, sound_sequence.PortamentoRangeSequenceEvent):
                pitch_bend_range = max(0, int(event.value))
            elif isinstance(event, sound_sequence.PortamentoSequenceEvent):
                pitch_bend = signed8(int(event.value))
            elif isinstance(event, sound_sequence.MonoPolySequenceEvent):
                note_wait = bool(int(event.value))
            elif isinstance(event, sound_sequence.VibratoDepthSequenceEvent):
                vibrato_depth = int(event.value)
            elif isinstance(event, sound_sequence.VibratoSpeedSequenceEvent):
                vibrato_speed = int(event.value)
            elif isinstance(event, sound_sequence.VibratoRangeSequenceEvent):
                vibrato_range = int(event.value)
            elif isinstance(event, sound_sequence.VibratoTypeSequenceEvent):
                vibrato_type = int(event.value)
            elif isinstance(event, sound_sequence.VibratoDelaySequenceEvent):
                vibrato_delay = int(event.value)
            elif isinstance(event, sound_sequence.SweepPitchSequenceEvent):
                sweep_pitch = signed16(int(event.value))
            elif isinstance(event, sound_sequence.AttackRateSequenceEvent):
                attack_rate = int(event.value)
            elif isinstance(event, sound_sequence.DecayRateSequenceEvent):
                decay_rate = int(event.value)
            elif isinstance(event, sound_sequence.SustainRateSequenceEvent):
                sustain_rate = int(event.value)
            elif isinstance(event, sound_sequence.ReleaseRateSequenceEvent):
                release_rate = int(event.value)
            elif isinstance(event, sound_sequence.RandomSequenceEvent):
                random_value = deterministic_random_value(event)
                if event.subType == 0xC0:
                    pan = random_value
                elif event.subType == 0xC1:
                    track_volume = random_value
                elif event.subType == 0xC2:
                    global_volume = random_value
                elif event.subType == 0xC3:
                    transpose = signed8(random_value)
                elif event.subType == 0xC4:
                    pitch_bend = signed8(random_value)
                elif event.subType == 0xC5:
                    pitch_bend_range = max(0, random_value)
                elif event.subType == 0xD5:
                    expression = random_value
            elif isinstance(event, sound_sequence.RestSequenceEvent):
                tempo = tempo_at_sample(global_tempo_points, cursor, tempo)
                cursor += ticks_to_samples(int(event.duration), tempo)
            elif isinstance(event, sound_sequence.NoteSequenceEvent):
                tempo = tempo_at_sample(global_tempo_points, cursor, tempo)
                duration = ticks_to_samples(int(event.duration), tempo)
                if duration <= 0:
                    continue
                if instrument_id >= len(bank.instruments):
                    continue
                base_pitch = max(0, min(127, int(event.pitch) + transpose))
                pitch_points = note_pitch_points(
                    track_events,
                    event_index,
                    base_pitch,
                    tempo,
                    pitch_bend,
                    pitch_bend_range,
                    duration,
                    note_wait,
                )
                pitch_points = add_sweep_pitch_points(
                    pitch_points,
                    duration,
                    int(event.duration),
                    sweep_pitch,
                )
                if vibrato_type == 0:
                    pitch_points = add_pitch_vibrato_points(
                        pitch_points,
                        duration,
                        vibrato_depth,
                        vibrato_speed,
                        vibrato_range,
                        vibrato_delay,
                    )
                effective_pitch = pitch_points[0][1]
                note_def = note_definition_for_pitch(bank.instruments[instrument_id], base_pitch)
                if note_def is None:
                    continue
                if note_def.type == sound_bank.NoteType.PCM:
                    samples = render_pcm_note(
                        note_def,
                        wave_archives,
                        effective_pitch,
                        duration,
                        pitch_points,
                        release_rate,
                    )
                else:
                    samples = render_psg_note(note_def, effective_pitch, duration, pitch_points, release_rate)
                base_gain = (
                    sequence_gain
                    * nds_sequence_gain(global_volume)
                    * nds_sequence_gain(event.velocity)
                )
                control_points = note_control_points(
                    track_events,
                    event_index,
                    tempo,
                    base_gain,
                    track_volume,
                    expression,
                    pan,
                    int(getattr(note_def, "pan", 64)),
                    len(samples),
                    note_wait,
                )
                envelope_points = nds_envelope_points(
                    note_def,
                    duration,
                    len(samples),
                    attack_rate,
                    decay_rate,
                    sustain_rate,
                    release_rate,
                )
                mix_note_into(
                    mix_left,
                    mix_right,
                    cursor,
                    samples,
                    base_gain,
                    combine_pan(pan, int(getattr(note_def, "pan", 64))),
                    control_points,
                    envelope_points,
                )
                if note_wait:
                    cursor += duration

    if not mix_left and not mix_right:
        raise ValueError(f"Sound effect {seq_id} did not render any audio")

    return stereo_samples_to_wav(mix_left, mix_right)


def move_sound_parse_value(raw: str, constants: dict[str, int]) -> int | None:
    raw = raw.strip().strip(",")
    named_values = {"PAN_LEFT": -117, "PAN_RIGHT": 117, "PAN_CENTER": 0}
    if raw in named_values:
        return named_values[raw]
    if raw in constants:
        return constants[raw]
    try:
        return int(raw, 0)
    except ValueError:
        return None


def move_sound_command_schedule(move_id: int) -> tuple[list[dict], list[dict]]:
    path = MOVE_ANIM_DIR / f"{int(move_id):03d}.s"
    if not path.exists():
        path = MOVE_ANIM_DIR / f"{int(move_id)}.s"
    if not path.exists():
        raise KeyError(f"No move animation script for move {move_id}")

    constants = sound_effect_constants()
    text = re.sub(r"//.*", "", path.read_text())
    lines = [line.strip() for line in text.splitlines()]
    schedule: list[dict] = []
    stops: list[dict] = []
    loop_stack: list[dict] = []
    cursor_frames = 0
    pc = 0
    steps = 0
    max_steps = 5000

    def parse_args(line: str) -> tuple[str, list[int | None]]:
        match = re.match(r"^([A-Za-z0-9_]+)\s*(.*)$", line)
        if not match:
            return "", []
        command, raw_args = match.groups()
        args = [move_sound_parse_value(part, constants) for part in raw_args.split(",") if part.strip()]
        return command, args

    while pc < len(lines) and steps < max_steps:
        steps += 1
        command, args = parse_args(lines[pc])
        if not command or command.startswith(".") or command.endswith(":"):
            pc += 1
            continue

        if command == "wait" and args and args[0] is not None:
            cursor_frames += max(0, int(args[0]))
        elif command == "waitstate":
            cursor_frames += MOVE_SOUND_WAITSTATE_FRAMES
        elif command == "waitparticle":
            cursor_frames += MOVE_SOUND_WAITPARTICLE_FRAMES
        elif command == "loop" and args and args[0] is not None:
            loop_stack.append({"start": pc + 1, "remaining": max(0, int(args[0]))})
        elif command == "doloop" and loop_stack:
            current_loop = loop_stack[-1]
            if current_loop["remaining"] > 1:
                current_loop["remaining"] -= 1
                pc = int(current_loop["start"])
                continue
            loop_stack.pop()
        elif command in {"playse", "playsepan", "playsepanmod"} and args and args[0] is not None:
            pan = 0
            if command == "playsepan" and len(args) > 1 and args[1] is not None:
                pan = int(args[1])
            elif command == "playsepanmod" and len(args) > 2:
                start_pan = int(args[1] or 0)
                end_pan = int(args[2] or start_pan)
                pan = int(round((start_pan + end_pan) / 2))
            schedule.append({"seqId": int(args[0]), "pan": pan, "frame": cursor_frames, "command": command})
        elif command == "repeatse" and len(args) >= 4 and args[0] is not None:
            seq_id = int(args[0])
            pan = int(args[1] or 0)
            spacing = max(0, int(args[2] or 0))
            repeat = max(0, int(args[3] or 0))
            for index in range(repeat):
                schedule.append({
                    "seqId": seq_id,
                    "pan": pan,
                    "frame": cursor_frames + spacing * index,
                    "command": command,
                })
        elif command == "waitse" and len(args) >= 3 and args[0] is not None:
            schedule.append({
                "seqId": int(args[0]),
                "pan": int(args[1] or 0),
                "frame": cursor_frames + max(0, int(args[2] or 0)),
                "command": command,
            })
        elif command == "stopse" and args and args[0] is not None:
            stops.append({"seqId": int(args[0]), "frame": cursor_frames})
        elif command == "end" and schedule:
            break
        pc += 1

    if schedule:
        first_frame = min(item["frame"] for item in schedule)
        if first_frame > 0:
            for item in schedule:
                item["frame"] = max(0, int(item["frame"]) - first_frame)
            for stop in stops:
                stop["frame"] = max(0, int(stop["frame"]) - first_frame)

    return schedule, stops


@lru_cache(maxsize=128)
def render_move_sound_effect_wav(move_id: int) -> bytes:
    schedule, stops = move_sound_command_schedule(move_id)
    if not schedule:
        raise ValueError(f"Move {move_id} does not schedule sound effects")

    stop_samples_by_seq: dict[int, list[int]] = {}
    for stop in stops:
        stop_samples_by_seq.setdefault(int(stop["seqId"]), []).append(frames_to_samples(stop["frame"]))
    for stop_samples in stop_samples_by_seq.values():
        stop_samples.sort()

    rendered_cache: dict[int, tuple[list[float], list[float]]] = {}
    mix_left: list[float] = []
    mix_right: list[float] = []
    max_start = int(MOVE_SOUND_MAX_SECONDS * SOUND_RENDER_SAMPLE_RATE)
    for item in sorted(schedule, key=lambda row: row["frame"]):
        start = frames_to_samples(item["frame"])
        if start > max_start:
            continue
        seq_id = int(item["seqId"])
        if seq_id not in rendered_cache:
            rendered_cache[seq_id] = rendered_wav_to_stereo_samples(render_sound_effect_wav(seq_id))
        stop_sample = next((sample for sample in stop_samples_by_seq.get(seq_id, []) if sample > start), None)
        clip_left, clip_right = rendered_cache[seq_id]
        mix_stereo_clip_into(mix_left, mix_right, start, clip_left, clip_right, int(item["pan"]), stop_sample)

    if not mix_left and not mix_right:
        raise ValueError(f"Move {move_id} did not render any audio")
    return stereo_samples_to_wav(mix_left, mix_right, max_seconds=MOVE_SOUND_MAX_SECONDS)


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


def restart_server_soon() -> dict:
    def restart() -> None:
        time.sleep(0.25)
        sys.stdout.flush()
        sys.stderr.flush()
        os.execv(sys.executable, [sys.executable, *sys.argv])

    threading.Thread(target=restart, daemon=True).start()
    return {"ok": True, "message": "Restarting server"}


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
      width: min(420px, calc(100vw - 16px));
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
      border-left: 3px solid transparent;
      background: #fff;
      color: inherit;
      display: grid;
      grid-template-columns: 30px minmax(150px, .9fr) auto minmax(0, 1.5fr);
      gap: 8px;
      align-items: start;
      min-height: 48px;
      padding: 8px 10px 8px 7px;
      text-align: left;
      cursor: pointer;
      contain: layout paint;
      overflow-anchor: none;
      transition: background-color .14s ease, border-color .14s ease;
    }

    .profile-row.override-profile {
      grid-template-columns: 30px 24px minmax(150px, .9fr) auto minmax(0, 1.5fr);
    }

    .profile-row.override-profile.dragging {
      opacity: .55;
    }

    .profile-row.override-profile.drag-over-before {
      box-shadow: inset 0 3px 0 var(--accent);
    }

    .profile-row.override-profile.drag-over-after {
      box-shadow: inset 0 -3px 0 var(--accent);
    }

    .profile-row.active {
      border-left-color: var(--accent);
      background: #fbfefd;
      box-shadow: none;
    }

    .profile-row.override-profile.active.drag-over-before {
      box-shadow: inset 3px 0 0 var(--accent), inset 0 3px 0 var(--accent);
    }

    .profile-row.override-profile.active.drag-over-after {
      box-shadow: inset 3px 0 0 var(--accent), inset 0 -3px 0 var(--accent);
    }

    .profile-row.changed {
      border-left-color: #d97706;
      background: #fff;
    }

    .profile-row.active.changed {
      border-left-color: var(--accent);
      background: #fbfefd;
      box-shadow: inset 0 -2px 0 rgba(217, 119, 6, .32);
    }

    .profile-row.changed:hover {
      background: #fbfdff;
    }

    .profile-row.active.changed:hover {
      background: #f8fdfa;
    }

    .profile-row:focus-visible {
      outline: 2px solid #99d6ca;
      outline-offset: -2px;
    }

    .profile-row > .route-encounter-badge {
      width: 27px;
      height: 27px;
      border-radius: 6px;
      opacity: .9;
    }

    .profile-row-order-controls {
      width: 24px;
      display: grid;
      grid-template-rows: 16px 14px 14px;
      gap: 2px;
      align-self: center;
    }

    .profile-row-drag-handle,
    .profile-row-order-button {
      width: 24px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid transparent;
      border-radius: 5px;
      background: transparent;
      color: #94a3b8;
      padding: 0;
      cursor: pointer;
    }

    .profile-row-drag-handle {
      height: 16px;
      cursor: grab;
    }

    .profile-row-drag-handle:active {
      cursor: grabbing;
    }

    .profile-row-order-button {
      height: 14px;
    }

    .profile-row-drag-handle:hover,
    .profile-row-drag-handle:focus-visible,
    .profile-row-order-button:hover,
    .profile-row-order-button:focus-visible {
      background: var(--accent-soft);
      color: var(--accent-strong);
      outline: 0;
    }

    .profile-row-order-button:disabled {
      opacity: .32;
      cursor: not-allowed;
    }

    .profile-row-order-button svg {
      width: 13px;
      height: 13px;
      stroke: currentColor;
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
      font-weight: 700;
    }

    .profile-row-sub {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
    }

    .profile-row-count {
      justify-self: end;
      min-height: 20px;
      display: inline-flex;
      align-items: center;
      padding: 0;
      border: 0;
      border-radius: 0;
      background: transparent;
      color: var(--muted);
      font-size: 11px;
      font-weight: 650;
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
      border-radius: 5px;
      background: #fff;
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
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
      min-width: min(560px, 100%);
      display: grid;
      grid-template-columns: minmax(132px, 170px) minmax(170px, 1fr) auto;
      align-items: center;
      gap: 6px;
    }

    .profile-add-target-host {
      min-width: 0;
    }

    .profile-add-kind-wrap,
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

    .profile-add-kind-wrap .route-encounter-badge,
    .profile-add-species-wrap .route-encounter-badge {
      width: 26px;
      height: 26px;
      border-radius: 7px;
    }

    .profile-add-kind,
    .profile-add-spawn-pool,
    .profile-add-type,
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

    .profile-add-input.invalid,
    .profile-add-type.invalid {
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
      gap: 10px;
    }

    .profile-architecture-group {
      container-type: inline-size;
      min-width: 0;
      border: 1px solid #dce4ee;
      border-radius: 6px;
      overflow: hidden;
      background: #fff;
    }

    .profile-architecture-head {
      min-height: 34px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding: 5px 10px;
      border-bottom: 1px solid #dce4ee;
      background: #fbfcfe;
      color: var(--ink);
      font-weight: 750;
    }

    .profile-architecture-title {
      min-width: 0;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }

    .profile-architecture-title .route-encounter-badge {
      width: 22px;
      height: 22px;
      border-radius: 6px;
      opacity: .88;
    }

    .profile-architecture-head-actions {
      flex: 0 0 auto;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }

    .profile-architecture-head-actions .count {
      min-width: 32px;
      padding: 0;
      color: #94a3b8;
      font-size: 10px;
      font-weight: 850;
      text-align: center;
      font-variant-numeric: tabular-nums;
    }

    .profile-section-clear {
      width: 24px;
      height: 24px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid transparent;
      border-radius: 6px;
      background: transparent;
      color: #94a3b8;
      cursor: pointer;
    }

    .profile-section-clear:hover,
    .profile-section-clear:focus-visible {
      border-color: #cbd5e1;
      background: #fff;
      color: var(--accent-strong);
      outline: 0;
    }

    .profile-section-clear:disabled {
      opacity: 0;
      pointer-events: none;
    }

    .profile-section-clear svg {
      width: 14px;
      height: 14px;
      stroke: currentColor;
    }

    .profile-field-subgroups {
      display: grid;
      gap: 0;
      background: #fff;
    }

    .profile-field-subgroup + .profile-field-subgroup {
      border-top: 1px solid #dce4ee;
    }

    .profile-subgroup-head {
      min-height: 28px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding: 6px 10px 5px;
      border-top: 1px solid #e2e8f0;
      border-bottom: 1px solid #d7e0ec;
      background: linear-gradient(180deg, #f6f8fb 0%, #eef3f8 100%);
      color: #334155;
      font-size: 10px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: .045em;
    }

    .profile-field-subgroup:first-child .profile-subgroup-head {
      border-top: 0;
    }

    .profile-subgroup-title {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .profile-subgroup-count {
      color: #64748b;
      font-size: 10px;
      font-weight: 800;
      font-variant-numeric: tabular-nums;
    }

    .profile-architecture-fields {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 0;
      background: #fff;
    }

    .profile-architecture-fields .field {
      min-height: 32px;
      display: grid;
      grid-template-columns: minmax(142px, 1fr) minmax(92px, 160px);
      align-items: center;
      gap: 8px;
      padding: 4px 10px 4px 8px;
      border-left: 2px solid transparent;
      background: #fff;
      position: relative;
      transition: background-color .14s ease, border-color .14s ease, box-shadow .14s ease;
    }

    .profile-architecture-fields .field + .field {
      border-top: 1px solid #edf2f7;
    }

    .profile-architecture-fields .field:hover,
    .profile-architecture-fields .field:focus-within {
      z-index: 1;
      background: #fbfdff;
      box-shadow: inset 0 0 0 1px #e2e8f0;
    }

    .profile-architecture-fields .profile-suboption-field {
      background: #fcfdff;
    }

    .profile-architecture-fields .field-label {
      min-width: 0;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      color: #475569;
      font-size: 11px;
      font-weight: 650;
      line-height: 1.15;
      text-transform: none;
      letter-spacing: 0;
    }

    .profile-field-label-text {
      min-width: 0;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
    }

    .profile-field-label-short {
      display: none;
    }

    .profile-field-unit {
      flex: 0 0 auto;
      color: #94a3b8;
      font-size: 10px;
      font-weight: 650;
    }

    .profile-field-state {
      flex: 0 0 auto;
      display: none;
      width: 16px;
      height: 16px;
      align-items: center;
      justify-content: center;
      padding: 0;
    }

    .profile-field-state svg {
      width: 13px;
      height: 13px;
      stroke: currentColor;
    }

    .profile-field-state-icon {
      display: none;
      align-items: center;
      justify-content: center;
    }

    .profile-field-badge {
      flex: 0 0 auto;
      width: 15px;
      height: 15px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      color: #94a3b8;
    }

    .profile-field-badge svg {
      width: 13px;
      height: 13px;
      stroke: currentColor;
    }

    .profile-field-control {
      min-width: 0;
      width: min(100%, 160px);
      display: block;
      justify-self: end;
    }

    .profile-architecture-fields .profile-combo,
    .profile-architecture-fields .profile-number {
      width: 100%;
      min-width: 0;
      height: 28px;
      margin-top: 0;
      border: 1px solid #dfe7f0;
      border-radius: 5px;
      background: #fff;
      color: var(--ink);
      padding: 0 7px;
      font-weight: 650;
      text-overflow: ellipsis;
    }

    .profile-subselect {
      width: 100%;
      min-width: 0;
      height: 28px;
      border: 1px solid #dfe7f0;
      border-radius: 5px;
      background-color: #fff;
      color: var(--ink);
      padding: 0 26px 0 7px;
      font-weight: 650;
    }

    select.control:focus-visible,
    .profile-architecture-fields .profile-combo:focus-visible,
    .profile-architecture-fields .profile-number:focus-visible,
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

    .reserved-shiny-list {
      display: inline-flex;
      align-items: center;
      gap: 3px;
      flex-wrap: wrap;
      min-width: 0;
      max-width: min(460px, 42vw);
    }

    .reserved-shiny-empty {
      color: #9a7a21;
      font-size: 11px;
      font-weight: 800;
      padding: 0 4px;
      white-space: nowrap;
    }

    .reserved-shiny-chip {
      height: 28px;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      min-width: 0;
      max-width: 142px;
      padding: 0 6px;
      border: 1px solid #f3d36a;
      border-radius: 7px;
      background: #fffef7;
      color: #713f12;
      font-size: 11px;
      font-weight: 850;
      cursor: pointer;
      font-family: inherit;
    }

    .reserved-shiny-chip:hover,
    .reserved-shiny-chip:focus-visible {
      border-color: #facc15;
      background: #fef3c7;
      box-shadow: 0 0 0 2px rgba(250, 204, 21, .18);
      outline: none;
    }

    .reserved-shiny-chip .encounter-badge {
      flex: 0 0 auto;
    }

    .reserved-shiny-chip .mon-icon {
      width: 24px;
      height: 24px;
      flex: 0 0 auto;
    }

    .reserved-shiny-name {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .reserved-shiny-level {
      color: #8a6a18;
      font-size: 10px;
      flex: 0 0 auto;
    }

    .reserved-shiny-dialog {
      width: min(640px, calc(100vw - 24px));
      max-height: min(86dvh, 720px);
      border: 1px solid var(--line);
      border-radius: 10px;
      background: #fff;
      color: var(--ink);
      padding: 0;
      box-shadow: 0 18px 48px rgba(15, 23, 42, 0.22);
    }

    .reserved-shiny-dialog::backdrop {
      background: rgba(15, 23, 42, 0.18);
    }

    .reserved-shiny-card {
      display: grid;
      gap: 10px;
      padding: 12px;
      max-height: inherit;
      overflow: hidden;
    }

    .reserved-shiny-head {
      display: grid;
      grid-template-columns: 44px minmax(0, 1fr);
      gap: 8px;
      align-items: center;
    }

    .reserved-shiny-head .mon-icon {
      width: 42px;
      height: 42px;
      image-rendering: pixelated;
      object-fit: contain;
    }

    .reserved-shiny-title {
      min-width: 0;
      display: grid;
      gap: 2px;
    }

    .reserved-shiny-title strong {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .reserved-shiny-title span,
    .reserved-shiny-help {
      color: var(--muted);
      font-size: 12px;
    }

    .reserved-shiny-entries {
      min-height: 0;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }

    .reserved-shiny-entry {
      min-width: 0;
      display: grid;
      grid-template-columns: 28px minmax(0, 1fr) auto;
      gap: 6px;
      align-items: center;
      padding: 6px;
      border-bottom: 1px solid var(--line);
      background: #fff;
      box-shadow: inset 3px 0 0 #facc15;
    }

    .reserved-shiny-entry:last-child {
      border-bottom: 0;
    }

    .reserved-shiny-entry.source-grass {
      background: #f4fdf8;
      box-shadow: inset 3px 0 0 #22c55e;
    }

    .reserved-shiny-entry.source-surf,
    .reserved-shiny-entry.source-fishing {
      background: #eff9ff;
      box-shadow: inset 3px 0 0 #38bdf8;
    }

    .reserved-shiny-entry.source-headbutt {
      background: #edf7ef;
      box-shadow: inset 3px 0 0 #064e3b;
    }

    .reserved-shiny-entry.source-shiny {
      background: #fffbeb;
      box-shadow: inset 3px 0 0 #facc15;
    }

    .reserved-shiny-entry-source {
      display: flex;
      justify-content: center;
      align-items: center;
      min-width: 0;
    }

    .reserved-shiny-entry-source .route-encounter-badge {
      width: 24px;
      height: 24px;
      border-radius: 7px;
    }

    .reserved-shiny-entry-source .mon-icon {
      width: 24px;
      height: 24px;
      image-rendering: pixelated;
      object-fit: contain;
    }

    .reserved-shiny-entry-meta {
      min-width: 0;
      display: grid;
      gap: 2px;
    }

    .reserved-shiny-entry-meta strong {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 13px;
    }

    .reserved-shiny-entry-meta span {
      color: var(--muted);
      font-size: 11px;
      font-weight: 750;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .reserved-shiny-entry-value {
      min-width: 54px;
      height: 28px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 4px;
      border: 1px solid #dbe5f0;
      border-radius: 7px;
      background: #fff;
      color: var(--ink);
      padding: 0 8px;
      font-size: 12px;
      font-weight: 850;
      white-space: nowrap;
    }

    .reserved-shiny-actions {
      display: flex;
      justify-content: flex-end;
      gap: 6px;
    }

    .reserved-shiny-actions .control {
      width: auto;
      min-width: 78px;
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

    .sound-search {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
      padding: 10px;
      border-bottom: 1px solid var(--line);
      background: var(--surface);
    }

    .sound-filter-row {
      grid-column: 1 / -1;
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      min-width: 0;
    }

    .sound-filter.active {
      border-color: #0f766e;
      background: var(--accent-soft);
      color: #0f766e;
    }

    .sound-list {
      display: flex;
      flex-direction: column;
      gap: 4px;
      padding: 8px;
    }

    .sound-row {
      width: 100%;
      border: 1px solid transparent;
      border-radius: 7px;
      background: transparent;
      color: inherit;
      text-align: left;
      display: grid;
      grid-template-columns: 62px minmax(0, 1fr) auto;
      gap: 8px;
      align-items: center;
      padding: 7px 8px;
      cursor: pointer;
    }

    .sound-row:hover,
    .sound-row:focus-visible,
    .sound-row.active {
      border-color: #99f6e4;
      background: #ecfdf5;
      outline: 0;
    }

    .sound-row-id {
      font-variant-numeric: tabular-nums;
      color: var(--muted);
      font-weight: 800;
    }

    .sound-row-name,
    .sound-detail-title {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-weight: 800;
    }

    .sound-row-meta,
    .sound-meta,
    .sound-status {
      color: var(--muted);
      font-size: 12px;
    }

    .sound-row-pill,
    .sound-chip {
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fff;
      color: var(--muted);
      padding: 2px 7px;
      font-size: 11px;
      font-weight: 800;
      white-space: nowrap;
    }

    .sound-detail-panel {
      display: grid;
      grid-template-rows: auto auto minmax(0, 1fr);
      min-height: 0;
    }

    .sound-detail-card {
      display: grid;
      gap: 12px;
      padding: 14px;
      border-bottom: 1px solid var(--line);
      background: var(--surface);
    }

    .sound-detail-head {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: start;
      min-width: 0;
    }

    .sound-detail-title {
      font-size: 20px;
      line-height: 1.15;
    }

    .sound-detail-actions,
    .sound-step-actions,
    .sound-audio-actions {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
    }

    .sound-detail-actions .control,
    .sound-step-actions .control,
    .sound-audio-actions .control {
      height: 30px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      padding: 0 9px;
      white-space: nowrap;
    }

    .sound-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
    }

    .sound-field {
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--surface-2);
      padding: 8px;
    }

    .sound-field-label {
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: .02em;
    }

    .sound-field-value {
      margin-top: 3px;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-weight: 800;
    }

    .sound-waveform {
      width: 100%;
      height: 96px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: linear-gradient(180deg, #f8fafc, #eef2f7);
    }

    .sound-audio-import {
      display: none;
    }

    .sound-status {
      min-height: 18px;
    }

    .field.changed {
      background: #fff8e6;
    }

    .profile-architecture-fields .field.changed {
      border-left-color: #d97706;
      background: #fff;
    }

    .profile-architecture-fields .field.changed:hover,
    .profile-architecture-fields .field.changed:focus-within {
      background: #fffaf0;
      box-shadow: inset 0 0 0 1px #f3d38b;
    }

    .profile-architecture-fields .field.overridden:not(.changed) {
      border-left-color: #5fb7ac;
      background: #fff;
    }

    .profile-architecture-fields .field.overridden:not(.changed):hover,
    .profile-architecture-fields .field.overridden:not(.changed):focus-within {
      background: #f7fbfa;
      box-shadow: inset 0 0 0 1px #c8e3de;
    }

    .profile-architecture-fields .field.inherited:not(.changed) {
      border-left-color: transparent;
      background: #fbfcfe;
    }

    .profile-architecture-fields .field.inherited:not(.changed):hover,
    .profile-architecture-fields .field.inherited:not(.changed):focus-within {
      background: #f8fafc;
      box-shadow: inset 0 0 0 1px #e2e8f0;
    }

    .profile-architecture-fields .field.inherited:not(.changed) .field-label,
    .profile-architecture-fields .field.inherited:not(.changed) .profile-field-unit {
      color: #94a3b8;
    }

    .profile-architecture-fields .field.inherited:not(.changed) .profile-field-state,
    .profile-architecture-fields .field.overridden:not(.changed) .profile-field-state,
    .profile-architecture-fields .field.changed .profile-field-state {
      display: inline-flex;
    }

    .profile-architecture-fields .field.inherited:not(.changed) .profile-field-state {
      color: #94a3b8;
    }

    .profile-architecture-fields .field.inherited:not(.changed) .profile-field-state-inherit {
      display: inline-flex;
    }

    .profile-architecture-fields .field.overridden:not(.changed) .profile-field-state {
      color: #0f766e;
    }

    .profile-architecture-fields .field.overridden:not(.changed) .profile-field-state-custom {
      display: inline-flex;
    }

    .profile-architecture-fields .field.changed .profile-field-state {
      color: #b45309;
    }

    .profile-architecture-fields .field.changed .profile-field-state-edited {
      display: inline-flex;
    }

    .field.inherited:not(.changed) .profile-combo,
    .field.inherited:not(.changed) .profile-number,
    .field.inherited:not(.changed) .profile-subselect {
      color: var(--muted);
    }

    .profile-architecture-fields .field.changed .profile-combo,
    .profile-architecture-fields .field.changed .profile-number,
    .profile-architecture-fields .field.changed .profile-subselect {
      border-color: #e6b95e;
      background: #fff;
    }

    .profile-architecture-fields .field.overridden:not(.changed) .profile-combo,
    .profile-architecture-fields .field.overridden:not(.changed) .profile-number,
    .profile-architecture-fields .field.overridden:not(.changed) .profile-subselect {
      border-color: #b8d9d3;
      background: #ffffff;
    }

    .profile-architecture-fields .profile-combo:hover,
    .profile-architecture-fields .profile-number:hover,
    .profile-subselect:hover {
      border-color: #cbd5e1;
      background: #fff;
    }

    @container (max-width: 320px) {
      .profile-architecture-fields .field {
        grid-template-columns: minmax(112px, 1fr) minmax(86px, 128px);
        gap: 6px;
      }

      .profile-field-control {
        width: min(100%, 128px);
      }

      .profile-field-label-full {
        display: none;
      }

      .profile-field-label-short {
        display: inline;
      }

      .profile-field-state {
        width: 15px;
        height: 15px;
      }
    }

    .profile-combo,
    .profile-number {
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

    .profile-combo.invalid,
    .profile-number.invalid {
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

    .route-override-control {
      cursor: pointer;
    }

    .route-override-control.route-rate-chip {
      flex: 0 0 auto;
    }

    .route-override-control.changed {
      border-color: #e8c66b;
      background: #fff8e6;
    }

    .route-override-control.enabled:not(.changed) {
      border-color: #dbe5f0;
      background: #fff;
    }

    .route-override-control .route-encounter-badge.type-override {
      color: #be123c;
      background: #fff1f2;
      border-color: #f0b2c1;
    }

    .route-override-mon-icons {
      display: inline-flex;
      align-items: center;
      flex-wrap: nowrap;
      gap: 2px;
      min-width: 0;
    }

    .route-override-species-wrap {
      min-width: 0;
      width: 30px;
      height: 30px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      overflow: visible;
    }

    .route-override-species-wrap .mon-icon {
      width: 28px;
      height: 28px;
      image-rendering: pixelated;
      object-fit: contain;
      justify-self: center;
    }

    .route-override-empty-icon {
      border: 1px solid #d8dee8;
      border-radius: 6px;
      background: #f8fafc;
      color: #64748b;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }

    .route-override-empty-icon svg {
      width: 15px;
      height: 15px;
      display: block;
      stroke: currentColor;
    }

    .route-override-dialog .route-override-empty-icon {
      width: 38px;
      height: 38px;
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

    .rule-main-button {
      appearance: none;
      border: 0;
      background: transparent;
      color: inherit;
      cursor: pointer;
      display: block;
      font: inherit;
      padding: 0;
      text-align: left;
      width: 100%;
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
        grid-template-columns: repeat(3, minmax(0, 1fr));
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
      .profile-add-control {
        grid-template-columns: 1fr;
        width: 100%;
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

      .profile-row.override-profile {
        grid-template-columns: 30px 24px minmax(0, 1fr) auto;
      }

      .profile-row-icons {
        grid-column: 1 / -1;
        max-height: 74px;
        padding-left: 38px;
      }

      .profile-row.override-profile .profile-row-icons {
        padding-left: 64px;
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

      .profile-row.override-profile {
        grid-template-columns: 28px 24px minmax(0, 1fr);
      }

      .profile-row-count {
        grid-column: 2;
        justify-self: start;
      }

      .profile-row.override-profile .profile-row-count {
        grid-column: 3;
      }

      .profile-row-icons {
        padding-left: 34px;
      }

      .profile-row.override-profile .profile-row-icons {
        padding-left: 58px;
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

      .profile-architecture-fields .field {
        grid-template-columns: minmax(0, 1fr);
        align-items: stretch;
        gap: 3px;
      }

      .profile-architecture-fields .field-label {
        min-height: 16px;
      }

      .profile-field-label-text {
        white-space: normal;
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

      .sound-detail-head,
      .sound-grid {
        grid-template-columns: minmax(0, 1fr);
      }

      .sound-row {
        grid-template-columns: 54px minmax(0, 1fr);
      }

      .sound-row-pill {
        grid-column: 2;
        justify-self: start;
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
      #routeList,
      #soundList {
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
          <button class="workspace-tab" data-view="sounds" type="button">Sound Effects</button>
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
          <div class="action-group">
            <button id="restartServer" class="control" type="button" title="Restart this web server">
              <span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 3v6h6"/></svg></span>
              <span>Restart server</span>
            </button>
          </div>
          <div class="action-group shiny-counter-group" title="Debug saved shiny spawn counter in test.dsv">
            <span class="shiny-counter-pill">
              <span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.6 5.1L19 10l-5.4 1.9L12 17l-1.6-5.1L5 10l5.4-1.9L12 3Z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z"/><path d="M5 15l.6 1.6L7 17l-1.4.4L5 19l-.6-1.6L3 17l1.4-.4L5 15Z"/></svg></span>
              <span id="shinyCounterValue">--</span>
              <span id="shinyCounterRate" class="muted">pity 1/8192</span>
            </span>
            <button id="refreshShinyCounter" class="control" type="button" title="Refresh shiny counter" aria-label="Refresh shiny counter">
              <span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 3v6h6"/></svg></span>
            </button>
            <button id="resetShinyCounter" class="control" type="button" title="Set shiny counter to 0">0</button>
            <button id="maxShinyCounter" class="control" type="button" title="Set shiny counter to 8191 so the next eligible spawn forces a pity shiny reservation">8191</button>
            <span id="reservedShinyList" class="reserved-shiny-list" title="Reserved pity shinies"></span>
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
    <main id="soundsView" class="view">
      <section class="pane">
        <div class="pane-head">
          <div class="pane-title">Sound Effects</div>
          <div id="soundCount" class="count"></div>
        </div>
        <div class="sound-search">
          <input id="soundSearch" class="control" type="search" placeholder="Search id, name, bank, group">
          <button id="soundRefresh" class="control" type="button">Refresh</button>
          <div class="sound-filter-row" aria-label="Sound effect filters">
            <button class="control sound-filter active" type="button" data-sound-filter="tester">Tester range</button>
            <button class="control sound-filter" type="button" data-sound-filter="moves">Moves</button>
            <button class="control sound-filter" type="button" data-sound-filter="field">Field</button>
            <button class="control sound-filter" type="button" data-sound-filter="battle">Battle</button>
            <button class="control sound-filter" type="button" data-sound-filter="basic">Basic</button>
            <button class="control sound-filter" type="button" data-sound-filter="extra">Extra</button>
            <button class="control sound-filter" type="button" data-sound-filter="all">All</button>
          </div>
        </div>
        <div id="soundList" class="scroll sound-list"></div>
      </section>
      <section class="pane detail sound-detail-panel">
        <div id="soundDetail" class="sound-detail-card"></div>
        <div class="sound-detail-card">
          <div class="sound-audio-actions">
            <button id="soundPlay" class="control primary-action" type="button" title="Render and play the selected sound effect">
              <span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="6 3 20 12 6 21 6 3"/></svg></span>
              <span>Play</span>
            </button>
            <button id="soundPlayRaw" class="control" type="button" title="Play the selected raw SSEQ without move animation timing">
              <span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="8 5 18 12 8 19 8 5"/></svg></span>
              <span>SEQ</span>
            </button>
            <button id="soundAudition" class="control" type="button" title="Play an approximate generated preview, not the real DS sound">
              <span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 10v4h4l5 5V5L6 10H2Z"/><path d="M16 9.5a4 4 0 0 1 0 5"/><path d="M19 7a8 8 0 0 1 0 10"/></svg></span>
              <span>Approx</span>
            </button>
            <button id="soundStop" class="control" type="button" title="Stop playback">
              <span class="action-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="6" width="12" height="12" rx="1"/></svg></span>
              <span>Stop</span>
            </button>
            <button id="soundPrevious" class="control" type="button" title="Previous sound">-1</button>
            <button id="soundNext" class="control" type="button" title="Next sound">+1</button>
            <button id="soundPreviousLarge" class="control" type="button" title="Previous 16 sounds">-16</button>
            <button id="soundNextLarge" class="control" type="button" title="Next 16 sounds">+16</button>
            <label class="control" title="Optional: load alternate WAV/MP3/OGG files named by id or sequence name">
              <span>Import alternate audio</span>
              <input id="soundAudioFiles" class="sound-audio-import" type="file" accept="audio/*,.wav,.ogg,.mp3" multiple>
            </label>
          </div>
          <canvas id="soundWaveform" class="sound-waveform" width="960" height="160" aria-hidden="true"></canvas>
          <div id="soundStatus" class="sound-status"></div>
        </div>
      </section>
    </main>
  </div>
  <div id="profileAddMenu" class="profile-add-menu" hidden></div>
  <div id="profileComboMenu" class="profile-combo-menu" hidden></div>
  <dialog id="routeSwapDialog" class="route-swap-dialog"></dialog>
  <dialog id="routeOverrideDialog" class="route-swap-dialog route-override-dialog"></dialog>
  <dialog id="spawnSettingDialog" class="spawn-setting-dialog"></dialog>
  <dialog id="reservedShinyDialog" class="reserved-shiny-dialog"></dialog>

  <script>
    let appData = null;
    let activeView = localStorage.getItem("owWorkspaceView") || "profiles";
    if (!["profiles", "encounters", "sounds"].includes(activeView)) activeView = "profiles";
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
    let profileFamilyMembersByBaseSymbol = new Map();
    const ALERT_SPECIAL_NONE_RAW = "OW_WILD_BEHAVIOR_ALERT_SPECIAL_NONE";
    const ALERT_SPECIAL_CALL_FOR_HELP_RAW = "OW_WILD_BEHAVIOR_ALERT_SPECIAL_CALL_FOR_HELP";
    const ALERT_SPECIAL_PICKUP_THROW_RAW = "OW_WILD_BEHAVIOR_ALERT_SPECIAL_PICKUP_THROW";
    const ALERT_ACTION_SPECIAL_FIELD = "alertActionSpecialAction";
    const ACTIVE_ACTION_SPECIAL_FIELD = "activeActionSpecialAction";
    const PROFILE_SCOPED_SPECIAL_ACTION_FIELDS = new Set([ALERT_ACTION_SPECIAL_FIELD, ACTIVE_ACTION_SPECIAL_FIELD]);
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
    let profileAddTargetKind = localStorage.getItem("owProfileAddTargetKind") || "pokemon";
    let profileAddSpawnPool = localStorage.getItem("owProfileAddSpawnPool") || "OW_WILD_SPAWN_TERRAIN_LAND";
    let profileAddType = localStorage.getItem("owProfileAddType") || "";
    let profileBulkType = localStorage.getItem("owProfileBulkType") || "";
    let profileOverrideProfileEdits = new Map();
    let profileOverrideNameEdits = new Map();
    let profileOverrideEdits = [];
    let profileOverrideRemoveEdits = new Set();
    let profileOverrideDragClassIndex = null;
    let profileOverrideDraftTargetKind = localStorage.getItem("owProfileOverrideTargetKind") || "type";
    let profileOverrideDraftType = localStorage.getItem("owProfileOverrideType") || "TYPE_FLYING";
    let profileOverrideDraftSpawnPool = localStorage.getItem("owProfileOverrideSpawnPool") || "OW_WILD_SPAWN_TERRAIN_LAND";
    let profileOverrideDraftField = localStorage.getItem("owProfileOverrideField") || "spawnState";
    let profileOverrideDraftRaw = localStorage.getItem("owProfileOverrideRaw") || "";
    let activeProfileComboInput = null;
    let profileComboMenuIndex = 0;
    let encounterEdits = new Map();
    let routeOverrideEdits = new Map();
    let spawnSettingEdits = new Map();
    let encounterSummaryTargetsById = new Map();
    let encounterSummaryTargetSequence = 0;
    let pendingRouteIds = new Set();
    let routeSwapState = null;
    let routeOverrideDialogRouteId = null;
    let routeOverrideRenderLock = false;
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
    const PROFILE_ADD_TARGET_KINDS = [
      { key: "pokemon", label: "Pokemon", icon: "plus", typeClass: "type-test", placeholder: "Pokemon" },
      { key: "spawnPool", label: "Spawn pool", icon: "target", typeClass: "type-placement", placeholder: "Spawn pool" },
      { key: "family", label: "Evo family", icon: "swarm", typeClass: "type-swarm", placeholder: "Family seed" },
      { key: "type", label: "Typing", icon: "target", typeClass: "type-placement", placeholder: "Typing" },
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
    const CIRCLE_PLAYER_TARGET_RAW = "OW_WILD_BEHAVIOR_TARGET_CIRCLE_PLAYER";
    const SPAWN_DESTINATION_FRONT_TYPE = "__SPAWN_DESTINATION_FRONT_OF_PLAYER";
    const SPAWN_DESTINATION_BEHIND_TYPE = "__SPAWN_DESTINATION_BEHIND_PLAYER";
    const SPAWN_DESTINATION_NEXT_TO_PLAYER_RAW = "OW_WILD_SPAWN_DESTINATION_NEXT_TO_PLAYER";
    const SPAWN_STATE_HOP_FROM_OFF_SCREEN_RAW = "OW_WILD_BEHAVIOR_SPAWN_STATE_HOP_FROM_OFF_SCREEN";
    const NUMERIC_PROFILE_FIELD_KEYS = new Set([
      "alertTime",
      "alertness",
      "stamina",
      "restTime",
      "chillSpeed",
      "attentiveSpeed",
      "tiredSpeed",
      "range",
      "alertChance",
      "hopMinDistance",
      "hopMaxDistance",
      "hopPause",
      "hopTime",
      "hopSpinSpeed",
      "spawnHopTime",
      "attentiveHopSpinSpeed",
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
      "overworldLimit",
      "spawnDestinationMinDistance",
      "spawnDestinationMaxDistance",
      "ramAccelerationSteps",
      "ramMaxSpeed",
      "attentiveChaseBoostDistance",
      "attentiveChaseBoostSpeed",
      "attentiveCircleRadius",
    ]);
    const PLAIN_PROFILE_NUMBER_FIELDS = new Set([
      "attentiveChaseBoostDistance",
      "attentiveChaseBoostSpeed",
      "attentiveCircleRadius",
    ]);
    const PROFILE_NUMBER_FIELD_LIMITS = {
      hopSpinSpeed: { min: 0, max: 15 },
      attentiveHopSpinSpeed: { min: 0, max: 15 },
      attentiveChaseBoostDistance: { min: 0, max: 32 },
      attentiveChaseBoostSpeed: { min: 0, max: 4 },
      attentiveCircleRadius: { min: 0, max: 8 },
    };
    const PROFILE_FIELD_HINTS = {
      profileId: "Optional behavior-family label. Most profiles can leave this as Default.",
      chillAllowedTile: "Tile type this Chill behavior may target.",
      attentiveAllowedTile: "Tile type this Active behavior may target.",
      tiredAllowedTile: "Tile type this Tired behavior may target.",
      chillAllowedTile2: "Optional second tile type this Chill behavior may target.",
      attentiveAllowedTile2: "Optional second tile type this Active behavior may target.",
      tiredAllowedTile2: "Optional second tile type this Tired behavior may target.",
      hopTime: "Ticks for a 1-tile hop. Extra tiles are slightly faster; 0 is immediate.",
      spawnHopTime: "Ticks for the forced off-screen spawn hop. 0 is immediate.",
      hopSpinSpeed: "Ticks per 90-degree facing turn during Chill Hop. 0 disables spin. Max 15.",
      attentiveHopSpinSpeed: "Ticks per 90-degree facing turn during Active Hop. 0 disables spin. Max 15.",
      overworldLimit: "Maximum active spawns for this profile or override bucket. 0 is unlimited.",
      attentiveCircleRadius: "Radius around the player for Circle player target. 0 behaves as 1 tile.",
      attentiveContinueWhenArrived: "When Circle player reaches a valid ring tile, keep choosing another ring tile.",
      attentiveAvoidPreviousTile: "Prefer not to step back onto the previous tile when another step is available.",
    };
    const PROFILE_ICON_FAMILIES = {
      behavior: { icon: "target", typeClass: "type-placement" },
      timing: { icon: "clock", typeClass: "type-flow" },
      movement: { icon: "footstep", typeClass: "type-movement" },
      speed: { icon: "speed", typeClass: "type-movement" },
      range: { icon: "ruler", typeClass: "type-placement" },
      condition: { icon: "target", typeClass: "type-placement" },
      trigger: { icon: "dice", typeClass: "type-flow" },
      terrain: { icon: "tree", typeClass: "type-placement" },
      visualAudio: { icon: "music", typeClass: "type-sound" },
      battle: { icon: "swords", typeClass: "type-test" },
      special: { icon: "shield", typeClass: "type-test" },
      capacity: { icon: "hash", typeClass: "type-placement" },
      stamina: { icon: "bolt", typeClass: "type-flow" },
    };
    const PROFILE_SUBGROUP_META = {
      Behavior: { iconFamily: "behavior" },
      Movement: { iconFamily: "movement" },
      Timing: { iconFamily: "timing" },
      Range: { iconFamily: "range" },
      Targeting: { iconFamily: "condition" },
      Terrain: { iconFamily: "terrain" },
      Visual: { iconFamily: "visualAudio" },
      Battle: { iconFamily: "battle" },
      Limits: { iconFamily: "capacity" },
      Special: { iconFamily: "special" },
      Stats: { iconFamily: "stamina" },
    };
    const PROFILE_FIELD_META = {
      spawnState: { label: "Spawn behavior", shortLabel: "Spawn", category: "spawn", subgroup: "Behavior", iconFamily: "movement" },
      spawnHopTime: { label: "Spawn delay", shortLabel: "Delay", unit: "ticks", category: "spawn", subgroup: "Timing", iconFamily: "timing" },
      spawnDestination: { label: "Spawn destination", shortLabel: "Destination", category: "spawn", subgroup: "Range", iconFamily: "condition" },
      spawnDestinationType: { label: "Spawn destination", shortLabel: "Destination", category: "spawn", subgroup: "Range", iconFamily: "condition" },
      spawnDestinationDistance: { label: "Spawn distance", shortLabel: "Distance", unit: "tiles", category: "spawn", subgroup: "Range", iconFamily: "range" },
      spawnDestinationMinDistance: { label: "Minimum spawn distance", shortLabel: "Min distance", unit: "tiles", category: "spawn", subgroup: "Range", iconFamily: "range" },
      spawnDestinationMaxDistance: { label: "Maximum spawn distance", shortLabel: "Max distance", unit: "tiles", category: "spawn", subgroup: "Range", iconFamily: "range" },
      jumpLevel: { label: "Jump height", shortLabel: "Jump", category: "spawn", subgroup: "Movement", iconFamily: "movement" },
      overworldLimit: { label: "Active spawn limit", shortLabel: "Limit", category: "spawn", subgroup: "Limits", iconFamily: "capacity", rowIcon: true },

      chillState: { label: "Chill behavior", shortLabel: "Behavior", category: "chill", subgroup: "Behavior", iconFamily: "behavior" },
      chillTarget: { label: "Chill target", shortLabel: "Target", category: "chill", subgroup: "Targeting", iconFamily: "condition" },
      chillAction: { label: "Chill movement", shortLabel: "Movement", category: "chill", subgroup: "Movement", iconFamily: "movement" },
      chillSpeed: { label: "Chill speed", shortLabel: "Speed", unit: "speed", category: "chill", subgroup: "Movement", iconFamily: "speed" },
      chillAllowedTile: { label: "Allowed tile", shortLabel: "Tile", category: "chill", subgroup: "Terrain", iconFamily: "terrain" },
      chillAllowedTile2: { label: "Second allowed tile", shortLabel: "Tile 2", category: "chill", subgroup: "Terrain", iconFamily: "terrain" },
      hopAllowNonCardinal: { label: "Allow diagonal hops", shortLabel: "Diagonal", category: "chill", subgroup: "Movement", iconFamily: "condition" },
      hopMinDistance: { label: "Minimum hop distance", shortLabel: "Min hop", unit: "tiles", category: "chill", subgroup: "Range", iconFamily: "range" },
      hopMaxDistance: { label: "Maximum hop distance", shortLabel: "Max hop", unit: "tiles", category: "chill", subgroup: "Range", iconFamily: "range" },
      hopTime: { label: "Hop travel time", shortLabel: "Hop time", unit: "ticks", category: "chill", subgroup: "Timing", iconFamily: "timing" },
      hopSpinSpeed: { label: "Hop turn speed", shortLabel: "Spin", unit: "ticks", category: "chill", subgroup: "Timing", iconFamily: "timing" },
      hopPause: { label: "Pause between hops", shortLabel: "Pause", unit: "ticks", category: "chill", subgroup: "Timing", iconFamily: "timing" },
      teleportTime: { label: "Teleport vanish time", shortLabel: "Teleport", unit: "ticks", category: "chill", subgroup: "Timing", iconFamily: "timing" },
      teleportPause: { label: "Teleport pause", shortLabel: "Pause", unit: "ticks", category: "chill", subgroup: "Timing", iconFamily: "timing" },
      ramAccelerationSteps: { label: "Chain move count", shortLabel: "Chain", unit: "moves", category: "chill", subgroup: "Movement", iconFamily: "movement" },
      ramMaxSpeed: { label: "Chain pause", shortLabel: "Pause", unit: "ticks", category: "chill", subgroup: "Timing", iconFamily: "timing" },
      chainPauseAction: { label: "Chain pause action", shortLabel: "Action", category: "chill", subgroup: "Movement", iconFamily: "movement", rowIcon: true },

      alertState: { label: "Alert trigger", shortLabel: "Trigger", category: "alert", subgroup: "Behavior", iconFamily: "condition" },
      alertEmote: { label: "Alert emote", shortLabel: "Emote", category: "alert", subgroup: "Visual", iconFamily: "visualAudio", rowIcon: true },
      alertTime: { label: "Alert duration", shortLabel: "Duration", unit: "ticks", category: "alert", subgroup: "Timing", iconFamily: "timing" },
      alertRange: { label: "Alert range shape", shortLabel: "Range type", category: "alert", subgroup: "Range", iconFamily: "range" },
      alertRangeType: { label: "Alert range shape", shortLabel: "Range type", category: "alert", subgroup: "Range", iconFamily: "range" },
      alertRangeClose: { label: "Close-radius trigger", shortLabel: "Close", category: "alert", subgroup: "Range", iconFamily: "condition" },
      alertness: { label: "Alert trigger range", shortLabel: "Range", unit: "tiles", category: "alert", subgroup: "Range", iconFamily: "range" },
      alertChance: { label: "Alert chance", shortLabel: "Chance", unit: "%", category: "alert", subgroup: "Behavior", iconFamily: "trigger" },
      alertSpecialAction: { label: "Special action", shortLabel: "Action", category: "alert", subgroup: "Special", iconFamily: "special", rowIcon: true },
      alertActionSpecialAction: { label: "Alert action", shortLabel: "Action", category: "alert", subgroup: "Special", iconFamily: "special", rowIcon: true },
      activeActionSpecialAction: { label: "Active action", shortLabel: "Action", category: "attentive", subgroup: "Special", iconFamily: "special", rowIcon: true },

      attentiveState: { label: "Active behavior", shortLabel: "Behavior", category: "attentive", subgroup: "Behavior", iconFamily: "behavior" },
      stamina: { label: "Active stamina", shortLabel: "Stamina", unit: "ticks", category: "attentive", subgroup: "Stats", iconFamily: "stamina" },
      targetSelector: { label: "Active target", shortLabel: "Target", category: "attentive", subgroup: "Targeting", iconFamily: "condition" },
      attentiveCircleRadius: { label: "Circle radius", shortLabel: "Circle", unit: "tiles", category: "attentive", subgroup: "Targeting", iconFamily: "range" },
      attentiveContinueWhenArrived: { label: "Continue when arrived", shortLabel: "Continue", category: "attentive", subgroup: "Targeting", iconFamily: "condition", rowIcon: true },
      attentiveAvoidPreviousTile: { label: "Avoid previous tile", shortLabel: "No backtrack", category: "attentive", subgroup: "Targeting", iconFamily: "condition", rowIcon: true },
      attentiveAction: { label: "Legacy active response", shortLabel: "Legacy", category: "attentive", subgroup: "Special", iconFamily: "special" },
      movementStyle: { label: "Active movement", shortLabel: "Movement", category: "attentive", subgroup: "Movement", iconFamily: "movement" },
      attentiveSpeed: { label: "Active speed", shortLabel: "Speed", unit: "speed", category: "attentive", subgroup: "Movement", iconFamily: "speed" },
      attentiveAllowedTile: { label: "Allowed tile", shortLabel: "Tile", category: "attentive", subgroup: "Terrain", iconFamily: "terrain" },
      attentiveAllowedTile2: { label: "Second allowed tile", shortLabel: "Tile 2", category: "attentive", subgroup: "Terrain", iconFamily: "terrain" },
      attentiveHopAllowNonCardinal: { label: "Allow diagonal hops", shortLabel: "Diagonal", category: "attentive", subgroup: "Movement", iconFamily: "condition" },
      attentiveHopMinDistance: { label: "Minimum hop distance", shortLabel: "Min hop", unit: "tiles", category: "attentive", subgroup: "Range", iconFamily: "range" },
      attentiveHopMaxDistance: { label: "Maximum hop distance", shortLabel: "Max hop", unit: "tiles", category: "attentive", subgroup: "Range", iconFamily: "range" },
      attentiveHopPause: { label: "Pause between hops", shortLabel: "Pause", unit: "ticks", category: "attentive", subgroup: "Timing", iconFamily: "timing" },
      attentiveHopSpinSpeed: { label: "Hop turn speed", shortLabel: "Spin", unit: "ticks", category: "attentive", subgroup: "Timing", iconFamily: "timing" },
      attentiveTeleportTime: { label: "Teleport vanish time", shortLabel: "Teleport", unit: "ticks", category: "attentive", subgroup: "Timing", iconFamily: "timing" },
      attentiveTeleportPause: { label: "Teleport pause", shortLabel: "Pause", unit: "ticks", category: "attentive", subgroup: "Timing", iconFamily: "timing" },
      attentiveRamAccelerationSteps: { label: "RAM acceleration interval", shortLabel: "Accel every", unit: "steps", category: "attentive", subgroup: "Movement", iconFamily: "movement" },
      attentiveRamMaxSpeed: { label: "Maximum ram speed", shortLabel: "Max speed", unit: "speed", category: "attentive", subgroup: "Movement", iconFamily: "speed" },
      attentiveChaseBoostDistance: { label: "Chase boost distance", shortLabel: "Boost dist.", unit: "tiles", category: "attentive", subgroup: "Range", iconFamily: "range" },
      attentiveChaseBoostSpeed: { label: "Chase boost speed", shortLabel: "Boost speed", unit: "speed", category: "attentive", subgroup: "Movement", iconFamily: "speed" },

      attentiveBattle: { label: "Battle Active", shortLabel: "Battle", category: "attentive", subgroup: "Battle", iconFamily: "battle", rowIcon: true },

      tiredState: { label: "Tired behavior", shortLabel: "Behavior", category: "tired", subgroup: "Behavior", iconFamily: "behavior" },
      specialAction: { label: "Tired movement", shortLabel: "Movement", category: "tired", subgroup: "Movement", iconFamily: "movement" },
      tiredSpeed: { label: "Tired speed", shortLabel: "Speed", unit: "speed", category: "tired", subgroup: "Movement", iconFamily: "speed" },
      tiredAllowedTile: { label: "Allowed tile", shortLabel: "Tile", category: "tired", subgroup: "Terrain", iconFamily: "terrain" },
      tiredAllowedTile2: { label: "Second allowed tile", shortLabel: "Tile 2", category: "tired", subgroup: "Terrain", iconFamily: "terrain" },
      tiredHopAllowNonCardinal: { label: "Allow diagonal hops", shortLabel: "Diagonal", category: "tired", subgroup: "Movement", iconFamily: "condition" },
      tiredHopMinDistance: { label: "Minimum hop distance", shortLabel: "Min hop", unit: "tiles", category: "tired", subgroup: "Range", iconFamily: "range" },
      tiredHopMaxDistance: { label: "Maximum hop distance", shortLabel: "Max hop", unit: "tiles", category: "tired", subgroup: "Range", iconFamily: "range" },
      tiredHopPause: { label: "Pause between hops", shortLabel: "Pause", unit: "ticks", category: "tired", subgroup: "Timing", iconFamily: "timing" },
      tiredTeleportTime: { label: "Teleport vanish time", shortLabel: "Teleport", unit: "ticks", category: "tired", subgroup: "Timing", iconFamily: "timing" },
      tiredTeleportPause: { label: "Teleport pause", shortLabel: "Pause", unit: "ticks", category: "tired", subgroup: "Timing", iconFamily: "timing" },
      tiredRamAccelerationSteps: { label: "RAM acceleration interval", shortLabel: "Accel every", unit: "steps", category: "tired", subgroup: "Movement", iconFamily: "movement" },
      tiredRamMaxSpeed: { label: "Maximum ram speed", shortLabel: "Max speed", unit: "speed", category: "tired", subgroup: "Movement", iconFamily: "speed" },
      restTime: { label: "Rest duration", shortLabel: "Rest", unit: "ticks", category: "tired", subgroup: "Timing", iconFamily: "timing" },

      range: { label: "Flee trigger range", shortLabel: "Flee range", unit: "tiles", category: "stats", subgroup: "Range", iconFamily: "range" },
      profileId: { label: "Behavior family", shortLabel: "Family", category: "special", subgroup: "Special", iconFamily: "special", rowIcon: true },
    };
    const PROFILE_DIRECT_EDIT_HIDDEN_FIELDS = new Set([
      "attentiveAction",
      "attentiveAvoidPreviousTile",
      "chainPauseAction",
    ]);
    const PROFILE_SECTION_CLEARABLE_HIDDEN_FIELDS = new Set([
      "chainPauseAction",
    ]);
    const PROFILE_OVERRIDE_BUILDER_HIDDEN_FIELDS = new Set([
      "attentiveAction",
      "attentiveAvoidPreviousTile",
    ]);
    const PROFILE_BEHAVIOR_FIELDS = new Set(["chillState", "attentiveState", "tiredState"]);
    const PROFILE_MOVEMENT_FIELDS = new Set(["chillAction", "movementStyle", "specialAction"]);
    const PROFILE_OPTION_FALLBACKS = {};
    const PROFILE_RAW_DISPLAY_OVERRIDES = {
      OW_WILD_BEHAVIOR_ALERT_SPECIAL_PICKUP_THROW: "Pick up and throw",
      OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE: "None",
      OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE: "Hop in place",
      OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_LOOK_AROUND: "Look around",
      OW_WILD_BEHAVIOR_TARGET_PLAYER_CARDINAL_LINE: "Player cardinal line",
      [CIRCLE_PLAYER_TARGET_RAW]: "Circle player",
    };
    const PROFILE_OVERRIDE_NO_TARGET_CLASS_RAW = "0xFE";
    const PROFILE_FIELD_GROUPS = [
      {
        key: "spawn",
        label: "Spawn",
        icon: "footstep",
        typeClass: "type-movement",
        fields: ["spawnState", "spawnHopTime", "spawnDestination", "spawnDestinationMinDistance", "spawnDestinationMaxDistance", "jumpLevel", "overworldLimit"],
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
          "hopTime",
          "hopSpinSpeed",
          "hopPause",
          "teleportTime",
          "teleportPause",
          "ramAccelerationSteps",
          "ramMaxSpeed",
          "chainPauseAction",
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
          ALERT_ACTION_SPECIAL_FIELD,
        ],
      },
      {
        key: "attentive",
        label: "Active",
        icon: "footstep",
        typeClass: "type-movement",
        fields: [
          "attentiveState",
          "stamina",
          "movementStyle",
          "attentiveSpeed",
          "attentiveAllowedTile",
          "attentiveAllowedTile2",
          "attentiveHopAllowNonCardinal",
          "attentiveHopMinDistance",
          "attentiveHopMaxDistance",
          "attentiveHopPause",
          "attentiveHopSpinSpeed",
          "attentiveTeleportTime",
          "attentiveTeleportPause",
          "attentiveRamAccelerationSteps",
          "attentiveRamMaxSpeed",
          "targetSelector",
          "attentiveCircleRadius",
          "attentiveContinueWhenArrived",
          ACTIVE_ACTION_SPECIAL_FIELD,
          "attentiveBattle",
          "attentiveChaseBoostDistance",
          "attentiveChaseBoostSpeed",
        ],
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
    let isRestartingServer = false;
    let isSettingShinyCounter = false;
    let lastShinyCounterPayload = null;
    let soundEffectsPayload = null;
    let soundEffects = [];
    let filteredSoundEffects = [];
    let selectedSoundEffectId = Number(localStorage.getItem("owSelectedSoundEffectId") || "1500");
    let soundFilter = localStorage.getItem("owSoundFilter") || "tester";
    if (!["tester", "moves", "field", "battle", "basic", "extra", "all"].includes(soundFilter)) soundFilter = "tester";
    let soundAudioFiles = new Map();
    let soundAudioElement = null;
    let soundAudioUrl = null;
    let soundAudioContext = null;
    let soundPlaybackNodes = [];
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
      soundsView: document.getElementById("soundsView"),
      routeSearch: document.getElementById("routeSearch"),
      routeSpawnTypeFilters: document.getElementById("routeSpawnTypeFilters"),
      routeCount: document.getElementById("routeCount"),
      routeList: document.getElementById("routeList"),
      routeGlobalSettings: document.getElementById("routeGlobalSettings"),
      routeDetailHead: document.getElementById("routeDetailHead"),
      routeSpeciesDatalistHost: document.getElementById("routeSpeciesDatalistHost"),
      routeEditor: document.getElementById("routeEditor"),
      soundSearch: document.getElementById("soundSearch"),
      soundRefresh: document.getElementById("soundRefresh"),
      soundCount: document.getElementById("soundCount"),
      soundList: document.getElementById("soundList"),
      soundDetail: document.getElementById("soundDetail"),
      soundPlay: document.getElementById("soundPlay"),
      soundPlayRaw: document.getElementById("soundPlayRaw"),
      soundAudition: document.getElementById("soundAudition"),
      soundStop: document.getElementById("soundStop"),
      soundPrevious: document.getElementById("soundPrevious"),
      soundNext: document.getElementById("soundNext"),
      soundPreviousLarge: document.getElementById("soundPreviousLarge"),
      soundNextLarge: document.getElementById("soundNextLarge"),
      soundAudioFiles: document.getElementById("soundAudioFiles"),
      soundWaveform: document.getElementById("soundWaveform"),
      soundStatus: document.getElementById("soundStatus"),
      saveAllChanges: document.getElementById("saveAllChanges"),
      buildAfterSave: document.getElementById("buildAfterSave"),
      buildRom: document.getElementById("buildRom"),
      openTestNds: document.getElementById("openTestNds"),
      runTestAfterBuild: document.getElementById("runTestAfterBuild"),
      showBuildOutput: document.getElementById("showBuildOutput"),
      restartServer: document.getElementById("restartServer"),
      shinyCounterValue: document.getElementById("shinyCounterValue"),
      shinyCounterRate: document.getElementById("shinyCounterRate"),
      refreshShinyCounter: document.getElementById("refreshShinyCounter"),
      resetShinyCounter: document.getElementById("resetShinyCounter"),
      maxShinyCounter: document.getElementById("maxShinyCounter"),
      reservedShinyList: document.getElementById("reservedShinyList"),
      resetAllEdits: document.getElementById("resetAllEdits"),
      saveStatus: document.getElementById("saveStatus"),
      buildOutputPanel: document.getElementById("buildOutputPanel"),
      buildOutput: document.getElementById("buildOutput"),
      buildTimer: document.getElementById("buildTimer"),
      closeBuildOutput: document.getElementById("closeBuildOutput"),
      profileAddMenu: document.getElementById("profileAddMenu"),
      profileComboMenu: document.getElementById("profileComboMenu"),
      routeSwapDialog: document.getElementById("routeSwapDialog"),
      routeOverrideDialog: document.getElementById("routeOverrideDialog"),
      spawnSettingDialog: document.getElementById("spawnSettingDialog"),
      reservedShinyDialog: document.getElementById("reservedShinyDialog")
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
      if (value.raw && PROFILE_RAW_DISPLAY_OVERRIDES[value.raw]) {
        return PROFILE_RAW_DISPLAY_OVERRIDES[value.raw];
      }
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
        hash: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9h16"/><path d="M4 15h16"/><path d="M10 3 8 21"/><path d="m16 3-2 18"/></svg>`,
        minus: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/></svg>`,
        copy: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="8" y="8" width="11" height="11" rx="2"/><path d="M5 16H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`,
        edit: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="m16.5 3.5 4 4L7 21H3v-4Z"/></svg>`,
        trash: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="m19 6-1 14H6L5 6"/><path d="M10 11v5"/><path d="M14 11v5"/></svg>`,
        eraser: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m7 21-4-4L14 6l4 4L7 21Z"/><path d="m14 6 4 4"/><path d="M7 21h13"/></svg>`,
        bolt: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2 4 14h7l-1 8 10-13h-7Z"/></svg>`,
        flask: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2v6.5L4.6 18.7A2.3 2.3 0 0 0 6.6 22h10.8a2.3 2.3 0 0 0 2-3.3L14 8.5V2"/><path d="M8 2h8"/><path d="M7.6 16h8.8"/></svg>`,
        chevronUp: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m6 15 6-6 6 6"/></svg>`,
        chevronDown: `<svg viewBox="0 0 24 24" fill="none" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>`,
        grip: `<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="9" cy="6" r="1.7"/><circle cx="15" cy="6" r="1.7"/><circle cx="9" cy="12" r="1.7"/><circle cx="15" cy="12" r="1.7"/><circle cx="9" cy="18" r="1.7"/><circle cx="15" cy="18" r="1.7"/></svg>`,
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
      if (activeView === "sounds" && soundEffectsPayload) {
        const source = soundEffectsPayload.infoBlock
          ? `${soundEffectsPayload.source} + ${soundEffectsPayload.infoBlock}`
          : soundEffectsPayload.source;
        return `${source} | ${soundEffectsPayload.count} effects`;
      }
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
      els.soundsView.classList.toggle("active", activeView === "sounds");
      els.profileControls.hidden = activeView !== "profiles";
      els.source.textContent = workspaceSourceText();
      if (activeView === "sounds" && !soundEffectsPayload) {
        loadSoundEffects().catch(error => {
          els.soundStatus.textContent = error.message;
        });
      }
    }

    function soundStatus(message) {
      els.soundStatus.textContent = message || "";
    }

    async function loadSoundEffects() {
      soundStatus("Loading sound effects...");
      const response = await fetch("/sound-effects", { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok || payload.error) {
        throw new Error(payload.error || `Sound effects request failed (${response.status})`);
      }
      soundEffectsPayload = payload;
      soundEffects = payload.effects || [];
      if (!soundEffects.some(effect => effect.id === selectedSoundEffectId)) {
        selectedSoundEffectId = payload.tester?.initial || soundEffects[0]?.id || 0;
      }
      renderSoundFilters();
      renderSoundEffects();
      soundStatus("");
      els.source.textContent = workspaceSourceText();
    }

    function renderSoundFilters() {
      document.querySelectorAll("[data-sound-filter]").forEach(button => {
        const active = button.dataset.soundFilter === soundFilter;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", active ? "true" : "false");
      });
    }

    function soundEffectMatchesFilter(effect) {
      const bank = String(effect.bank || "").toUpperCase();
      const groups = (effect.groups || []).join(" ").toUpperCase();
      if (soundFilter === "all") return true;
      if (soundFilter === "tester") return !!effect.inTesterRange;
      if (soundFilter === "moves") return !!effect.isMoveSoundEffect;
      if (soundFilter === "field") return bank.includes("FIELD") || groups.includes("FIELD");
      if (soundFilter === "battle") return bank.includes("BATTLE") || groups.includes("BATTLE");
      if (soundFilter === "basic") return bank === "BANK_BASIC";
      if (soundFilter === "extra") return !effect.isSoundEffect;
      return true;
    }

    function soundSearchText(effect) {
      const moveAliases = effect.moveAliases || [];
      return [
        effect.id,
        effect.name,
        effect.shortName,
        effect.fileName,
        effect.bank,
        effect.player,
        ...moveAliases.flatMap(alias => [alias.moveName, alias.moveSymbol, alias.scriptFile, alias.command]),
        effect.isMoveSoundEffect ? "move" : "",
        effect.isSoundEffect ? "sound effect" : "extra sequence",
        ...(effect.groups || []),
      ].join(" ").toLowerCase();
    }

    function filteredSoundEffectRows() {
      const query = els.soundSearch.value.trim().toLowerCase();
      return soundEffects.filter(effect => {
        if (query) return soundSearchText(effect).includes(query);
        return soundEffectMatchesFilter(effect);
      });
    }

    function soundEffectById(id) {
      return soundEffects.find(effect => Number(effect.id) === Number(id)) || null;
    }

    function selectedSoundEffect() {
      return soundEffectById(selectedSoundEffectId) || filteredSoundEffects[0] || soundEffects[0] || null;
    }

    function soundGroupLabel(effect) {
      const name = String(effect.name || "");
      const bank = String(effect.bank || "");
      if (effect.isMoveSoundEffect) return "Move";
      if (!effect.isSoundEffect && name.startsWith("SEQ_ME_")) return "ME";
      if (!effect.isSoundEffect && bank === "BANK_GAMEBOY") return "Game Boy";
      if (!effect.isSoundEffect && bank.startsWith("BANK_SE_")) return bank.replace(/^BANK_SE_/, "");
      if (effect.bank === "BANK_BASIC") return "Basic";
      const groups = effect.groups || [];
      if (groups.some(group => group.includes("FIELD"))) return "Field";
      if (groups.some(group => group.includes("BATTLE"))) return "Battle";
      if (groups.length) return groups[0].replace(/^GROUP_SE_/, "");
      return effect.bank || "SE";
    }

    function soundMoveAliasLabel(effect, limit = 2) {
      const aliases = effect.moveAliases || [];
      if (!aliases.length) return "";
      const names = [];
      aliases.forEach(alias => {
        if (alias.moveName && !names.includes(alias.moveName)) names.push(alias.moveName);
      });
      if (names.length <= limit) return names.join(", ");
      return `${names.slice(0, limit).join(", ")} +${names.length - limit}`;
    }

    function soundMoveAliasChips(effect, limit = 8) {
      const aliases = effect.moveAliases || [];
      const names = [];
      aliases.forEach(alias => {
        if (alias.moveName && !names.includes(alias.moveName)) names.push(alias.moveName);
      });
      const visible = names.slice(0, limit).map(name => `<span class="sound-chip">${esc(name)}</span>`).join("");
      const hidden = names.length > limit ? `<span class="sound-chip">+${esc(names.length - limit)} moves</span>` : "";
      return visible + hidden;
    }

    function soundMovePreviewButtons(effect, limit = 8) {
      const aliases = effect.moveAliases || [];
      const moves = [];
      aliases.forEach(alias => {
        if (!alias.moveId || moves.some(move => Number(move.moveId) === Number(alias.moveId))) return;
        moves.push(alias);
      });
      const visible = moves.slice(0, limit).map(alias => `
        <button class="control" type="button" data-move-preview-id="${esc(alias.moveId)}" title="${esc(alias.commandText || alias.command || "Move preview")}">
          ${esc(alias.moveName || alias.moveSymbol || `Move ${alias.moveId}`)}
        </button>
      `).join("");
      const hidden = moves.length > limit ? `<span class="sound-chip">+${esc(moves.length - limit)} moves</span>` : "";
      return visible + hidden;
    }

    function renderSoundRow(effect) {
      const active = Number(effect.id) === Number(selectedSoundEffectId);
      const meta = [effect.bank, effect.player].filter(Boolean).join(" · ");
      const moveLabel = soundMoveAliasLabel(effect);
      const displayName = moveLabel || effect.shortName || effect.name;
      const detailName = moveLabel
        ? `${effect.shortName || effect.name} · ${meta || effect.fileName || ""}`
        : (meta || effect.fileName || "");
      return `
        <button class="sound-row ${active ? "active" : ""}" type="button" data-sound-id="${esc(effect.id)}">
          <span class="sound-row-id">${esc(effect.id)}</span>
          <span>
            <span class="sound-row-name">${esc(displayName)}</span>
            <span class="sound-row-meta">${esc(detailName)}</span>
          </span>
          <span class="sound-row-pill">${esc(soundGroupLabel(effect))}</span>
        </button>
      `;
    }

    function soundField(label, value) {
      return `
        <div class="sound-field">
          <div class="sound-field-label">${esc(label)}</div>
          <div class="sound-field-value" title="${esc(value ?? "")}">${esc(value ?? "--")}</div>
        </div>
      `;
    }

    function importedAudioForEffect(effect) {
      if (!effect) return null;
      const keys = [
        String(effect.id),
        String(effect.id).padStart(4, "0"),
        String(effect.name || "").toUpperCase(),
        String(effect.shortName || "").toUpperCase(),
        String(effect.fileName || "").replace(/\.[^.]+$/, "").toUpperCase(),
      ];
      for (const key of keys) {
        if (soundAudioFiles.has(key)) return soundAudioFiles.get(key);
      }
      return null;
    }

    function renderSoundDetail() {
      const effect = selectedSoundEffect();
      if (!effect) {
        els.soundDetail.innerHTML = `<div class="empty">No sound effects loaded</div>`;
        drawSoundWaveform(null);
        return;
      }
      const groups = (effect.groups || []).map(group => `<span class="sound-chip">${esc(group)}</span>`).join("");
      const moveAliasChips = soundMoveAliasChips(effect);
      const movePreviewButtons = soundMovePreviewButtons(effect);
      const moveAliasText = (effect.moveAliases || []).map(alias => `${alias.moveName} (${alias.moveSymbol}, ${alias.commandText || alias.command})`).join(", ");
      els.soundDetail.innerHTML = `
        <div class="sound-detail-head">
          <div>
            <div class="sound-detail-title">${esc(soundMoveAliasLabel(effect, 4) || effect.name)}</div>
            <div class="sound-meta">ID ${esc(effect.id)} · ${esc(effect.fileName || "no sequence file")} · ${effect.hasSseq ? `${esc(effect.sseqBytes)} bytes` : "missing SSEQ"}</div>
          </div>
          <div class="sound-detail-actions">
            ${effect.inTesterRange ? `<span class="sound-chip">Tester range</span>` : ""}
            ${effect.isMoveSoundEffect ? `<span class="sound-chip">Move</span>` : ""}
            ${effect.isSoundEffect ? `<span class="sound-chip">SEQ_SE</span>` : `<span class="sound-chip">Extra sequence</span>`}
            ${effect.hasSseq ? `<span class="sound-chip">On-demand WAV</span>` : `<span class="sound-chip">Missing sequence</span>`}
          </div>
        </div>
        <div class="sound-grid">
          ${soundField("Bank", effect.bank || "--")}
          ${soundField("Player", effect.player || "--")}
          ${soundField("Volume", effect.volume ?? "--")}
          ${soundField("Priority", [effect.channelPriority, effect.playerPriority].filter(value => value != null).join(" / ") || "--")}
          ${moveAliasText ? soundField("Move aliases", moveAliasText) : ""}
        </div>
        <div class="sound-step-actions">${moveAliasChips || groups || `<span class="sound-chip">Ungrouped</span>`}</div>
        ${movePreviewButtons ? `<div class="sound-step-actions">${movePreviewButtons}</div>` : ""}
      `;
      els.soundPlay.disabled = !effect.hasSseq;
      els.soundPlayRaw.disabled = !effect.hasSseq;
      drawSoundWaveform(effect);
    }

    function renderSoundEffects() {
      filteredSoundEffects = filteredSoundEffectRows();
      els.soundCount.textContent = `${filteredSoundEffects.length} / ${soundEffects.length}`;
      if (!filteredSoundEffects.some(effect => Number(effect.id) === Number(selectedSoundEffectId))) {
        selectedSoundEffectId = filteredSoundEffects[0]?.id || soundEffects[0]?.id || 0;
      }
      els.soundList.innerHTML = filteredSoundEffects.length
        ? filteredSoundEffects.map(renderSoundRow).join("")
        : `<div class="empty">No sound effects match</div>`;
      renderSoundDetail();
    }

    function selectSoundEffect(id, options = {}) {
      const effect = soundEffectById(id);
      if (!effect) return;
      selectedSoundEffectId = effect.id;
      localStorage.setItem("owSelectedSoundEffectId", String(effect.id));
      renderSoundEffects();
      const row = els.soundList.querySelector(`[data-sound-id="${CSS.escape(String(effect.id))}"]`);
      if (row && options.scroll !== false) row.scrollIntoView({ block: "nearest" });
    }

    function stepSoundEffect(delta) {
      if (!filteredSoundEffects.length) return;
      const currentIndex = Math.max(0, filteredSoundEffects.findIndex(effect => Number(effect.id) === Number(selectedSoundEffectId)));
      const nextIndex = (currentIndex + delta + filteredSoundEffects.length * 100) % filteredSoundEffects.length;
      selectSoundEffect(filteredSoundEffects[nextIndex].id);
      if (selectedSoundEffect()?.hasSseq) {
        playSelectedSoundEffect();
      }
    }

    function shouldIgnoreSoundKeyTarget(target) {
      if (!target) return false;
      if (target.isContentEditable) return true;
      return !!target.closest("input, textarea, select");
    }

    function handleSoundKeyNavigation(event) {
      if (activeView !== "sounds" || shouldIgnoreSoundKeyTarget(event.target)) return false;
      if (event.altKey || event.ctrlKey || event.metaKey) return false;
      const stepByKey = {
        ArrowDown: 1,
        ArrowRight: 1,
        ArrowUp: -1,
        ArrowLeft: -1,
        PageDown: 16,
        PageUp: -16,
      };
      const delta = stepByKey[event.key];
      if (!delta || !filteredSoundEffects.length) return false;
      event.preventDefault();
      stepSoundEffect(delta);
      return true;
    }

    function stopSoundPlayback() {
      if (soundAudioElement) {
        soundAudioElement.pause();
        soundAudioElement.currentTime = 0;
      }
      if (soundAudioUrl) {
        URL.revokeObjectURL(soundAudioUrl);
        soundAudioUrl = null;
      }
      soundPlaybackNodes.forEach(node => {
        try {
          if (typeof node.stop === "function") node.stop();
          if (typeof node.disconnect === "function") node.disconnect();
        } catch (error) {
          void error;
        }
      });
      soundPlaybackNodes = [];
    }

    function waveformForEffect(effect) {
      if (!effect) return [];
      const id = Number(effect.id) || 0;
      const name = String(effect.name || "");
      const count = 24;
      return Array.from({ length: count }, (_, index) => {
        const seed = (id * 17 + index * 31 + name.charCodeAt(index % Math.max(1, name.length))) % 97;
        return 0.18 + (seed / 97) * 0.76;
      });
    }

    function drawSoundWaveform(effect) {
      const canvas = els.soundWaveform;
      const ctx = canvas.getContext("2d");
      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "#f8fafc";
      ctx.fillRect(0, 0, width, height);
      ctx.strokeStyle = "#cbd5e1";
      ctx.beginPath();
      ctx.moveTo(0, height / 2);
      ctx.lineTo(width, height / 2);
      ctx.stroke();
      const values = waveformForEffect(effect);
      if (!values.length) return;
      const barWidth = width / values.length;
      ctx.fillStyle = "#0f766e";
      values.forEach((value, index) => {
        const barHeight = Math.max(8, value * height * 0.78);
        const x = index * barWidth + 3;
        const y = (height - barHeight) / 2;
        ctx.fillRect(x, y, Math.max(2, barWidth - 6), barHeight);
      });
    }

    function synthProfileForEffect(effect) {
      const name = String(effect.name || "").toUpperCase();
      const bank = String(effect.bank || "").toUpperCase();
      const id = Number(effect.id) || 0;
      const base = 180 + (id % 36) * 18;
      const waveform = bank === "BANK_BASIC" ? "square" : bank.includes("FIELD") ? "triangle" : "sawtooth";
      const duration = name.includes("DUMMY") ? 0.12 : name.includes("KIRAKIRA") ? 0.7 : name.includes("WATER") ? 0.5 : 0.34;
      const pulses = name.includes("KIRAKIRA") ? 5 : name.includes("TIMER") || name.includes("PINPON") ? 3 : 2;
      return { base, waveform, duration, pulses };
    }

    function playSyntheticSound(effect) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) {
        soundStatus("AudioContext is not available in this browser.");
        return;
      }
      if (!soundAudioContext) soundAudioContext = new AudioContext();
      stopSoundPlayback();
      const ctx = soundAudioContext;
      const profile = synthProfileForEffect(effect);
      const master = ctx.createGain();
      master.gain.value = Math.min(0.42, Math.max(0.08, (Number(effect.volume) || 90) / 255));
      master.connect(ctx.destination);
      soundPlaybackNodes.push(master);
      const start = ctx.currentTime + 0.015;
      for (let i = 0; i < profile.pulses; i++) {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        const pulseStart = start + i * (profile.duration / profile.pulses);
        const pulseDuration = profile.duration / (profile.pulses + 0.8);
        osc.type = profile.waveform;
        osc.frequency.setValueAtTime(profile.base * (1 + i * 0.16), pulseStart);
        osc.frequency.exponentialRampToValueAtTime(Math.max(40, profile.base * (0.8 + (i % 2) * 0.24)), pulseStart + pulseDuration);
        gain.gain.setValueAtTime(0.001, pulseStart);
        gain.gain.exponentialRampToValueAtTime(0.9, pulseStart + 0.015);
        gain.gain.exponentialRampToValueAtTime(0.001, pulseStart + pulseDuration);
        osc.connect(gain);
        gain.connect(master);
        osc.start(pulseStart);
        osc.stop(pulseStart + pulseDuration + 0.02);
        soundPlaybackNodes.push(osc, gain);
      }
      soundStatus(`Approximate preview for ${effect.name}; this is not the real DS sound.`);
    }

    function selectedMovePreviewAlias(effect) {
      return (effect?.moveAliases || []).find(alias => alias.moveId) || null;
    }

    async function playSoundUrl(url, label) {
      stopSoundPlayback();
      soundStatus(`Rendering ${label}...`);
      const renderAbortController = new AbortController();
      const renderTimeout = setTimeout(() => renderAbortController.abort(), 20000);
      try {
        const response = await fetch(url, {
          cache: "no-store",
          signal: renderAbortController.signal,
        });
        if (!response.ok) {
          let message = `Sound render failed (${response.status})`;
          try {
            const payload = await response.json();
            if (payload.error) message = payload.error;
          } catch (error) {
            void error;
          }
          throw new Error(message);
        }
        const audioBlob = await response.blob();
        soundAudioUrl = URL.createObjectURL(audioBlob);
        soundAudioElement = new Audio(soundAudioUrl);
        soundAudioElement.preload = "auto";
        soundAudioElement.addEventListener("ended", () => {
          soundStatus(`Finished ${label}.`);
        }, { once: true });
        await soundAudioElement.play();
        soundStatus(`Playing ${label}.`);
      } catch (error) {
        const message = error.name === "AbortError"
          ? "Render timed out. This sound is probably too long for the tester."
          : error.message;
        soundStatus(`Could not play ${label}: ${message}`);
      } finally {
        clearTimeout(renderTimeout);
      }
    }

    async function playMoveSoundEffect(moveId, label) {
      await playSoundUrl(`/move-sound-effects/${encodeURIComponent(moveId)}.wav`, `${label} move preview`);
    }

    async function playSelectedRawSoundEffect() {
      const effect = selectedSoundEffect();
      if (!effect) return;
      await playSoundUrl(`/sound-effects/${encodeURIComponent(effect.id)}.wav`, `${effect.name} SEQ`);
    }

    async function playSelectedSoundEffect() {
      const effect = selectedSoundEffect();
      if (!effect) return;
      const moveAlias = selectedMovePreviewAlias(effect);
      if (moveAlias) {
        await playMoveSoundEffect(moveAlias.moveId, moveAlias.moveName || effect.name);
        return;
      }
      await playSelectedRawSoundEffect();
    }

    function auditionSelectedSoundEffect() {
      const effect = selectedSoundEffect();
      if (!effect) return;
      playSyntheticSound(effect);
    }

    function soundAudioKey(fileName) {
      return String(fileName || "").replace(/\.[^.]+$/, "").toUpperCase();
    }

    function importSoundAudioFiles(files) {
      let count = 0;
      Array.from(files || []).forEach(file => {
        const key = soundAudioKey(file.name);
        if (!key) return;
        soundAudioFiles.set(key, file);
        count++;
      });
      soundStatus(`${count} audio file${count === 1 ? "" : "s"} loaded.`);
      renderSoundDetail();
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

    function routeOverridePayload() {
      const overrides = {};
      routeOverrideEdits.forEach((edit, routeId) => {
        if (!edit) return;
        if (edit.action === "clear") {
          overrides[routeId] = { action: "clear" };
          return;
        }
        overrides[routeId] = {
          action: "set",
          species: edit.species,
          form: String(edit.form ?? 0),
          entries: (edit.entries || []).map(entry => ({
            path: entry.path,
            formPath: entry.formPath,
            species: entry.species,
            form: String(entry.form ?? 0),
          })),
        };
      });
      return overrides;
    }

    function refreshPendingRouteIds() {
      pendingRouteIds = new Set();
      encounterEdits.forEach((value, key) => {
        const split = key.indexOf(":");
        if (split > 0) pendingRouteIds.add(key.slice(0, split));
      });
      routeOverrideEdits.forEach((value, routeId) => {
        pendingRouteIds.add(String(routeId));
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
      if (!hasPending && routeOverrideEdits.has(routeKey)) {
        hasPending = true;
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
        evolutionFamilies: [],
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
        babymons: "",
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
          <span class="field-label">${esc(profileFieldLabel(field.key))}</span>
          <span class="field-value" title="${esc(profile[field.key]?.raw ?? "")}">${esc(fieldValue(profile[field.key]))}</span>
        </div>
      `).join("");
    }

    function profileFieldBaseLabel(fieldKey) {
      return appData.fields.find(field => field.key === fieldKey)?.label || fieldKey;
    }

    function profileFieldMeta(fieldKey) {
      const meta = PROFILE_FIELD_META[fieldKey] || {};
      const family = PROFILE_ICON_FAMILIES[meta.iconFamily] || PROFILE_ICON_FAMILIES.condition;
      const label = meta.label || profileFieldBaseLabel(fieldKey);
      return {
        key: fieldKey,
        label,
        shortLabel: meta.shortLabel || label,
        unit: meta.unit || "",
        category: meta.category || "",
        subgroup: meta.subgroup || "Other",
        iconFamily: meta.iconFamily || "condition",
        icon: meta.icon || family.icon,
        typeClass: meta.typeClass || family.typeClass,
        hint: meta.hint || PROFILE_FIELD_HINTS[fieldKey] || "",
        inherited: meta.inherited || `${label} inherits from the base profile`,
        rowIcon: !!meta.rowIcon,
      };
    }

    function profileFieldLabel(fieldKey, dense = false) {
      const meta = profileFieldMeta(fieldKey);
      return dense ? meta.shortLabel : meta.label;
    }

    function profileFieldIcon(fieldKey) {
      const meta = profileFieldMeta(fieldKey);
      return [meta.icon, meta.typeClass];
    }

    function profileFieldBadge(fieldKey, label) {
      const meta = profileFieldMeta(fieldKey);
      if (!meta.rowIcon) return "";
      const [icon, typeClass] = profileFieldIcon(fieldKey);
      return `<span class="profile-field-badge ${esc(typeClass)}" title="${esc(label)}" aria-hidden="true">${interfaceIcon(icon)}</span>`;
    }

    function profileFieldLabelMarkup(fieldKey, label, unit = null, shortLabel = null) {
      const meta = profileFieldMeta(fieldKey);
      const unitLabel = unit ?? meta.unit;
      const compactLabel = shortLabel || meta.shortLabel || label;
      return `
        <span class="field-label">
          ${profileFieldBadge(fieldKey, label)}
          <span class="profile-field-label-text profile-field-label-full">${esc(label)}</span>
          <span class="profile-field-label-text profile-field-label-short">${esc(compactLabel)}</span>
          ${unitLabel ? `<span class="profile-field-unit">${esc(unitLabel)}</span>` : ""}
          <span class="profile-field-state">
            <span class="profile-field-state-icon profile-field-state-inherit" role="img" aria-label="Inherited value" title="Inherited from base profile">${interfaceIcon("copy")}</span>
            <span class="profile-field-state-icon profile-field-state-custom" role="img" aria-label="Custom override" title="Custom override">${interfaceIcon("edit")}</span>
            <span class="profile-field-state-icon profile-field-state-edited" role="img" aria-label="Unsaved edit" title="Unsaved edit">${interfaceIcon("bolt")}</span>
          </span>
        </span>
      `;
    }

    function profileFieldControlMarkup(html) {
      return `<span class="profile-field-control">${html}</span>`;
    }

    function profileFieldItem(fieldKey, html, options = {}) {
      return {
        fieldKey,
        subgroup: options.subgroup || profileFieldMeta(fieldKey).subgroup,
        html,
      };
    }

    function profileEditFieldItem(item, fieldKey, options = {}) {
      return profileFieldItem(fieldKey, profileEditField(item, fieldKey, options), options);
    }

    function profileUniqueFieldItems(fieldItems) {
      const seen = new Set();
      return (fieldItems || []).filter(item => {
        const fieldKey = item?.fieldKey;
        if (!fieldKey) return true;
        if (seen.has(fieldKey)) return false;
        seen.add(fieldKey);
        return true;
      });
    }

    function primitiveFieldLabel(fieldKey) {
      return (appData.primitiveFields || []).find(field => field.key === fieldKey)?.label || fieldKey;
    }

    function isOverrideProfileIndex(classIndex) {
      return String(classIndex || "").startsWith("override:");
    }

    function isOverrideProfile(item) {
      return !!item?.isOverrideProfile || isOverrideProfileIndex(item?.index);
    }

    function profileOverrideOrders(itemOrOrder) {
      if (Array.isArray(itemOrOrder?.orders) && itemOrOrder.orders.length) {
        return itemOrOrder.orders.map(order => String(order));
      }
      if (itemOrOrder?.order !== undefined && itemOrOrder?.order !== null) {
        return [String(itemOrOrder.order)];
      }
      if (typeof itemOrOrder === "string" && itemOrOrder.includes(",")) {
        return itemOrOrder.split(",").map(order => order.trim()).filter(Boolean);
      }
      if (itemOrOrder !== undefined && itemOrOrder !== null) {
        return [String(itemOrOrder)];
      }
      return [];
    }

    function profileOverridePrimaryOrder(item) {
      return profileOverrideOrders(item)[0] || "";
    }

    function orderedOverrideProfiles() {
      return (appData?.classes || []).filter(item => isOverrideProfile(item));
    }

    function profileOverrideRowIndex(item) {
      const rows = orderedOverrideProfiles();
      return rows.findIndex(row => String(row.index) === String(item?.index));
    }

    function profileOverrideCanMove(item, delta) {
      const rows = orderedOverrideProfiles();
      const index = profileOverrideRowIndex(item);
      const targetIndex = index + delta;
      return index >= 0 && targetIndex >= 0 && targetIndex < rows.length;
    }

    function profileOverrideOrderControls(item) {
      if (!isOverrideProfile(item)) return "";
      const name = profileDisplayName(item);
      return `
        <span class="profile-row-order-controls" aria-label="Override profile order">
          <span class="profile-row-drag-handle" role="button" tabindex="0" draggable="true" data-action="drag-override-profile" data-class-index="${esc(item.index)}" title="Drag ${esc(name)} to reorder" aria-label="Drag ${esc(name)} to reorder">
            ${interfaceIcon("grip")}
          </span>
          <button class="profile-row-order-button" type="button" data-action="move-override-profile-up" data-class-index="${esc(item.index)}" ${profileOverrideCanMove(item, -1) ? "" : "disabled"} title="Move ${esc(name)} earlier" aria-label="Move ${esc(name)} earlier">
            ${interfaceIcon("chevronUp")}
          </button>
          <button class="profile-row-order-button" type="button" data-action="move-override-profile-down" data-class-index="${esc(item.index)}" ${profileOverrideCanMove(item, 1) ? "" : "disabled"} title="Move ${esc(name)} later" aria-label="Move ${esc(name)} later">
            ${interfaceIcon("chevronDown")}
          </button>
        </span>
      `;
    }

    function profileOverrideIsRemoving(itemOrOrder) {
      const orders = profileOverrideOrders(itemOrOrder);
      return orders.length > 0 && orders.every(order => profileOverrideRemoveEdits.has(order));
    }

    function profileOverrideHitOrdersForAssignment(assignment, itemOrOrder) {
      const orders = new Set(profileOverrideOrders(itemOrOrder));
      if (!orders.size || !assignment) return [];
      return (assignment.variableOverrideHits || assignment.maxSpeedOverrideHits || [])
        .map(hit => String(hit.order))
        .filter(order => orders.has(order));
    }

    function profileOverridePendingName(item) {
      if (!isOverrideProfile(item)) return item?.name || "";
      const key = profileOverridePrimaryOrder(item);
      return profileOverrideNameEdits.has(key) ? profileOverrideNameEdits.get(key) : (item?.name || "");
    }

    function profileDisplayName(item) {
      return isOverrideProfile(item) ? profileOverridePendingName(item) : (item?.name || "");
    }

    function editKey(classIndex, fieldKey) {
      return `${classIndex}|${fieldKey}`;
    }

    function pendingProfileValue(classIndex, fieldKey, fallbackRaw) {
      const key = editKey(classIndex, fieldKey);
      const edits = isOverrideProfileIndex(classIndex) ? profileOverrideProfileEdits : profileEdits;
      return edits.has(key) ? edits.get(key) : fallbackRaw;
    }

    function profileComboRawDisplay(raw) {
      if (PROFILE_RAW_DISPLAY_OVERRIDES[raw]) {
        return PROFILE_RAW_DISPLAY_OVERRIDES[raw];
      }
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
        OW_WILD_BEHAVIOR_KIND_TIRED_EMOTE: "Tired Emote",
        OW_WILD_BEHAVIOR_KIND_NO_VISUAL: "No Visual",
        OW_WILD_BEHAVIOR_LOCOMOTION_NONE: "None",
        OW_WILD_BEHAVIOR_LOCOMOTION_WANDER: "Walk",
        OW_WILD_BEHAVIOR_LOCOMOTION_HOP: "Hop",
        OW_WILD_BEHAVIOR_LOCOMOTION_RAM: "Ram",
        OW_WILD_BEHAVIOR_LOCOMOTION_PHANTOM_TELEPORT: "Phantom Teleport",
        OW_WILD_BEHAVIOR_ALERT_SPECIAL_NONE: "None",
        OW_WILD_BEHAVIOR_ALERT_SPECIAL_CALL_FOR_HELP: "Call for help",
        OW_WILD_BEHAVIOR_ALERT_SPECIAL_PICKUP_THROW: "Pick up and throw",
        OW_WILD_BEHAVIOR_TARGET_NONE: "Behavior default",
        OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER: "Toward player",
        OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER: "Away from player",
        OW_WILD_BEHAVIOR_TARGET_TREE_TOP: "Tree top",
        OW_WILD_BEHAVIOR_TARGET_PLAYFUL_ORBIT: "Toward player (legacy)",
        OW_WILD_BEHAVIOR_TARGET_PLAYER_FRONT: "Player front",
        OW_WILD_BEHAVIOR_TARGET_PLAYER_CARDINAL_LINE: "Player cardinal line",
        OW_WILD_BEHAVIOR_TARGET_CIRCLE_PLAYER: "Circle player",
      };
      if (PROFILE_RAW_DISPLAY_OVERRIDES[option.raw]) {
        return PROFILE_RAW_DISPLAY_OVERRIDES[option.raw];
      }
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
      return raw === ALERT_SPECIAL_CALL_FOR_HELP_RAW;
    }

    function alertSpecialActionPickupThrows(raw) {
      return raw === ALERT_SPECIAL_PICKUP_THROW_RAW;
    }

    function scopedSpecialActionOptions(fieldKey) {
      let allowed = new Set([ALERT_SPECIAL_NONE_RAW, ALERT_SPECIAL_PICKUP_THROW_RAW]);
      if (fieldKey === ALERT_ACTION_SPECIAL_FIELD) {
        allowed = new Set([ALERT_SPECIAL_NONE_RAW, ALERT_SPECIAL_CALL_FOR_HELP_RAW]);
      }
      return profileOptionsWithFallbacks("alertSpecialAction", appData.editOptions.alertSpecialAction || [])
        .filter(option => allowed.has(option.raw));
    }

    function scopedSpecialActionRaw(fieldKey, raw) {
      if (!raw) return "";
      if (fieldKey === ALERT_ACTION_SPECIAL_FIELD) {
        return alertSpecialActionCallsForHelp(raw) ? raw : ALERT_SPECIAL_NONE_RAW;
      }
      return alertSpecialActionPickupThrows(raw) ? raw : ALERT_SPECIAL_NONE_RAW;
    }

    function scopedSpecialActionOwnsRaw(fieldKey, raw) {
      if (!raw) return false;
      if (fieldKey === ALERT_ACTION_SPECIAL_FIELD) return alertSpecialActionCallsForHelp(raw);
      if (fieldKey === ACTIVE_ACTION_SPECIAL_FIELD) return alertSpecialActionPickupThrows(raw);
      return false;
    }

    function scopedSpecialActionCountRaw(fieldKey, raw) {
      return scopedSpecialActionOwnsRaw(fieldKey, raw) ? scopedSpecialActionRaw(fieldKey, raw) : "";
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

    function spawnStateUsesHopTime(raw) {
      const option = profileOptionForRaw("spawnState", raw);
      return raw === SPAWN_STATE_HOP_FROM_OFF_SCREEN_RAW
        || option?.raw === SPAWN_STATE_HOP_FROM_OFF_SCREEN_RAW
        || String(profileComboDisplay("spawnState", raw)).toLowerCase().includes("hop from off screen");
    }

    function movementStyleOptions(fieldKey = "movementStyle") {
      return (appData.editOptions[fieldKey] || appData.editOptions.movementStyle || [])
        .map(option => ({ ...option, label: profileComboOptionDisplay(option, fieldKey) }));
    }

    function targetSelectorOptions(fieldKey = "targetSelector") {
      return profileOptionsWithFallbacks(fieldKey, appData.editOptions[fieldKey] || appData.editOptions.targetSelector || [])
        .map(option => ({ ...option, label: profileComboOptionDisplay(option, "targetSelector") }));
    }

    function profileOptionsWithFallbacks(fieldKey, options) {
      const merged = [...(options || [])];
      const seen = new Set(merged.map(option => option.raw));
      (PROFILE_OPTION_FALLBACKS[fieldKey] || []).forEach(option => {
        if (!seen.has(option.raw)) {
          merged.push(option);
        }
      });
      return merged;
    }

    function profileOptionsForField(fieldKey) {
      if (PROFILE_SCOPED_SPECIAL_ACTION_FIELDS.has(fieldKey)) return scopedSpecialActionOptions(fieldKey);
      if (PROFILE_MOVEMENT_FIELDS.has(fieldKey)) return movementStyleOptions(fieldKey);
      if (fieldKey === "targetSelector" || fieldKey === "chillTarget") return targetSelectorOptions(fieldKey);
      if (fieldKey === ALERT_RANGE_TYPE_FIELD) return alertRangeTypeOptions();
      if (fieldKey === SPAWN_DESTINATION_TYPE_FIELD) return spawnDestinationTypeOptions();
      return profileOptionsWithFallbacks(fieldKey, appData.editOptions[fieldKey] || []);
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

    function profileFieldValueMatchesRaw(fieldKey, raw, expectedRaw) {
      if (raw === expectedRaw) return true;
      const option = profileOptionForRaw(fieldKey, raw);
      if (option?.raw === expectedRaw) return true;
      const expected = profileOptionsForField(fieldKey).find(item => item.raw === expectedRaw);
      return Number.isFinite(expected?.value) && String(raw ?? "") === String(expected.value);
    }

    function targetSelectorIsCirclePlayer(raw) {
      return profileFieldValueMatchesRaw("targetSelector", raw, CIRCLE_PLAYER_TARGET_RAW);
    }

    function profileFieldRerendersSubcontrols(fieldKey) {
      return PROFILE_BEHAVIOR_FIELDS.has(fieldKey)
        || PROFILE_MOVEMENT_FIELDS.has(fieldKey)
        || fieldKey === ALERT_RANGE_TYPE_FIELD
        || fieldKey === "alertSpecialAction"
        || fieldKey === "targetSelector"
        || fieldKey === "spawnState"
        || PROFILE_SCOPED_SPECIAL_ACTION_FIELDS.has(fieldKey)
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
      (appData.fields || []).forEach(field => {
        const fieldKey = field.key;
        const options = profileOptionsForField(fieldKey);
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

    function profileNumberInputValue(item, fieldKey, raw) {
      const text = String(raw ?? "").trim();
      if (!text) return "";
      const direct = Number(text);
      if (Number.isInteger(direct)) return String(direct);
      const current = item.profile[fieldKey];
      if (current && current.raw === raw && Number.isFinite(current.value)) {
        return String(current.value);
      }
      const option = profileOptionForRaw(fieldKey, raw);
      if (option && Number.isFinite(option.value)) {
        return String(option.value);
      }
      return text;
    }

    function profileEditField(item, fieldKey, options = {}) {
      const originalRaw = item.profile[fieldKey]?.raw ?? "0";
      const raw = pendingProfileValue(item.index, fieldKey, originalRaw);
      const changed = raw !== originalRaw;
      const meta = profileFieldMeta(fieldKey);
      const label = options.label || meta.label;
      const inherited = isOverrideProfile(item) && !raw;
      const overridden = isOverrideProfile(item) && !!raw;
      const hint = options.hint || meta.hint || (inherited ? meta.inherited : label);
      const classes = ["field", options.className || "", changed ? "changed" : "", inherited ? "inherited" : "", overridden ? "overridden" : ""].filter(Boolean).join(" ");
      if (options.numberLimits || PLAIN_PROFILE_NUMBER_FIELDS.has(fieldKey)) {
        const limits = options.numberLimits || PROFILE_NUMBER_FIELD_LIMITS[fieldKey] || { min: 0, max: 255 };
        const value = profileNumberInputValue(item, fieldKey, raw);
        const originalValue = profileNumberInputValue(item, fieldKey, originalRaw);
        const numberChanged = value !== originalValue;
        return `
          <label class="${esc(["field", options.className || "", numberChanged ? "changed" : "", inherited ? "inherited" : "", overridden ? "overridden" : ""].filter(Boolean).join(" "))}" data-profile-field="${esc(fieldKey)}" data-profile-subgroup="${esc(options.subgroup || meta.subgroup)}" title="${esc(hint)}">
            ${profileFieldLabelMarkup(fieldKey, label, options.unit, options.shortLabel)}
            ${profileFieldControlMarkup(`<input class="profile-number" type="number" min="${esc(limits.min)}" max="${esc(limits.max)}" step="1" value="${esc(value)}" placeholder="${isOverrideProfile(item) ? "Inherit" : ""}" data-class-index="${esc(item.index)}" data-field="${esc(fieldKey)}" data-original="${esc(originalRaw)}" data-original-value="${esc(originalValue)}" data-min="${esc(limits.min)}" data-max="${esc(limits.max)}" autocomplete="off" title="${esc(hint)}">`)}
          </label>
        `;
      }
      return `
        <label class="${esc(classes)}" data-profile-field="${esc(fieldKey)}" data-profile-subgroup="${esc(options.subgroup || meta.subgroup)}" title="${esc(hint)}">
          ${profileFieldLabelMarkup(fieldKey, label, options.unit, options.shortLabel)}
          ${profileFieldControlMarkup(`<input class="profile-combo" type="text" value="${esc(profileComboDisplay(fieldKey, raw))}" placeholder="${isOverrideProfile(item) ? "Inherit" : ""}" data-class-index="${esc(item.index)}" data-field="${esc(fieldKey)}" data-original="${esc(originalRaw)}" autocomplete="off" role="combobox" aria-autocomplete="list" aria-expanded="false" title="${esc(hint)}">`)}
        </label>
      `;
    }

    function profileEditScopedSpecialActionField(item, fieldKey, label, hint) {
      const sourceRaw = item.profile.alertSpecialAction?.raw ?? ALERT_SPECIAL_NONE_RAW;
      const raw = pendingProfileValue(item.index, "alertSpecialAction", sourceRaw);
      const displayRaw = scopedSpecialActionRaw(fieldKey, raw);
      const scopedRaw = scopedSpecialActionCountRaw(fieldKey, raw);
      const originalScopedRaw = scopedSpecialActionCountRaw(fieldKey, sourceRaw);
      const changed = scopedRaw !== originalScopedRaw;
      const inherited = isOverrideProfile(item) && !scopedRaw;
      const overridden = isOverrideProfile(item) && !!scopedRaw;
      const meta = profileFieldMeta(fieldKey);
      return `
        <label class="field ${changed ? "changed" : ""} ${inherited ? "inherited" : ""} ${overridden ? "overridden" : ""}" data-profile-field="${esc(fieldKey)}" data-profile-subgroup="${esc(meta.subgroup)}" title="${esc(hint || meta.hint || label)}">
          ${profileFieldLabelMarkup(fieldKey, label)}
          ${profileFieldControlMarkup(`<input class="profile-combo" type="text" value="${esc(profileComboDisplay(fieldKey, displayRaw))}" placeholder="${isOverrideProfile(item) ? "Inherit" : ""}" data-class-index="${esc(item.index)}" data-field="${esc(fieldKey)}" data-source-field="alertSpecialAction" data-source-original="${esc(sourceRaw)}" data-original="${esc(originalScopedRaw)}" autocomplete="off" role="combobox" aria-autocomplete="list" aria-expanded="false" title="${esc(hint || label)}">`)}
        </label>
      `;
    }

    function profileEditSpawnDestinationTypeField(item) {
      const originalRaw = item.profile.spawnDestination?.raw ?? "0";
      const raw = pendingProfileValue(item.index, "spawnDestination", originalRaw);
      const changed = raw !== originalRaw;
      const label = "Spawn destination";
      const inherited = isOverrideProfile(item) && !raw;
      const overridden = isOverrideProfile(item) && !!raw;
      const meta = profileFieldMeta(SPAWN_DESTINATION_TYPE_FIELD);
      return `
        <label class="field ${changed ? "changed" : ""} ${inherited ? "inherited" : ""} ${overridden ? "overridden" : ""}" data-profile-field="${esc(SPAWN_DESTINATION_TYPE_FIELD)}" data-profile-subgroup="${esc(meta.subgroup)}" title="${esc(label)}">
          ${profileFieldLabelMarkup(SPAWN_DESTINATION_TYPE_FIELD, label)}
          ${profileFieldControlMarkup(`<input class="profile-combo" type="text" value="${esc(profileComboDisplay(SPAWN_DESTINATION_TYPE_FIELD, raw))}" placeholder="${isOverrideProfile(item) ? "Inherit" : ""}" data-class-index="${esc(item.index)}" data-field="${esc(SPAWN_DESTINATION_TYPE_FIELD)}" data-original="${esc(originalRaw)}" autocomplete="off" role="combobox" aria-autocomplete="list" aria-expanded="false" title="${esc(label)}">`)}
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
      const meta = profileFieldMeta("spawnDestinationDistance");
      const overridden = isOverrideProfile(item) && !!raw;
      return `
        <label class="field profile-suboption-field ${changed ? "changed" : ""} ${overridden ? "overridden" : ""}" data-profile-field="spawnDestinationDistance" data-profile-subgroup="${esc(meta.subgroup)}" title="${esc(label)}">
          ${profileFieldLabelMarkup("spawnDestinationDistance", label)}
          ${profileFieldControlMarkup(`<select class="profile-subselect" data-profile-spawn-destination-distance data-class-index="${esc(item.index)}" data-original="${esc(originalRaw)}" aria-label="${esc(label)}" title="${esc(label)}">
            ${options.map(option => `
              <option value="${esc(option.distance)}"${option.distance === info.distance ? " selected" : ""}>${esc(option.distance)} tile${option.distance === 1 ? "" : "s"}</option>
            `).join("")}
          </select>`)}
        </label>
      `;
    }

    function profileEditSpawnFields(item) {
      const spawnStateOriginalRaw = item.profile.spawnState?.raw ?? "0";
      const spawnStateRaw = pendingProfileValue(item.index, "spawnState", spawnStateOriginalRaw);
      const originalRaw = item.profile.spawnDestination?.raw ?? "0";
      const raw = pendingProfileValue(item.index, "spawnDestination", originalRaw);
      const usesRadius = spawnDestinationUsesRadius(raw);
      const inheritedOverride = isOverrideProfile(item) && !raw;
      const playerDestinationInfo = spawnDestinationPlayerInfo(raw);
      const fields = [
        profileEditFieldItem(item, "spawnState"),
      ];
      if (spawnStateUsesHopTime(spawnStateRaw) || (isOverrideProfile(item) && !spawnStateRaw)) {
        fields.push(profileEditFieldItem(item, "spawnHopTime", {
          className: "profile-suboption-field",
          hint: "Ticks for the forced off-screen spawn hop. 0 is immediate. Hop turn speed is edited under Chill.",
        }));
      }
      fields.push(profileFieldItem(SPAWN_DESTINATION_TYPE_FIELD, profileEditSpawnDestinationTypeField(item)));
      if (playerDestinationInfo) {
        fields.push(profileFieldItem("spawnDestinationDistance", profileEditSpawnDestinationDistanceField(item)));
      } else if (spawnDestinationNeedsDistance(raw) || inheritedOverride) {
        fields.push(profileEditFieldItem(item, "spawnDestinationMinDistance", {
          className: "profile-suboption-field",
          hint: usesRadius ? "Minimum radius around the player" : "Minimum tiles from the player",
        }));
        fields.push(profileEditFieldItem(item, "spawnDestinationMaxDistance", {
          className: "profile-suboption-field",
          hint: usesRadius ? "Maximum radius around the player" : "Maximum tiles from the player",
        }));
      }
      fields.push(profileEditFieldItem(item, "jumpLevel"));
      fields.push(profileEditFieldItem(item, "overworldLimit"));
      return {
        count: fields.length,
        items: fields,
        html: fields.map(field => field.html).join(""),
      };
    }

    function profileEditAlertRangeTypeField(item) {
      const originalRaw = item.profile.alertRange?.raw ?? "0";
      const raw = pendingProfileValue(item.index, "alertRange", originalRaw);
      const changed = raw !== originalRaw;
      const label = "Range type";
      const inherited = isOverrideProfile(item) && !raw;
      const overridden = isOverrideProfile(item) && !!raw;
      const meta = profileFieldMeta(ALERT_RANGE_TYPE_FIELD);
      return `
        <label class="field ${changed ? "changed" : ""} ${inherited ? "inherited" : ""} ${overridden ? "overridden" : ""}" data-profile-field="${esc(ALERT_RANGE_TYPE_FIELD)}" data-profile-subgroup="${esc(meta.subgroup)}" title="${esc(label)}">
          ${profileFieldLabelMarkup(ALERT_RANGE_TYPE_FIELD, label)}
          ${profileFieldControlMarkup(`<input class="profile-combo" type="text" value="${esc(profileComboDisplay(ALERT_RANGE_TYPE_FIELD, raw))}" placeholder="${isOverrideProfile(item) ? "Inherit" : ""}" data-class-index="${esc(item.index)}" data-field="${esc(ALERT_RANGE_TYPE_FIELD)}" data-original="${esc(originalRaw)}" autocomplete="off" role="combobox" aria-autocomplete="list" aria-expanded="false" title="${esc(label)}">`)}
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
      const meta = profileFieldMeta("alertRangeClose");
      const overridden = isOverrideProfile(item) && !!raw;
      return `
        <label class="field profile-suboption-field ${changed ? "changed" : ""} ${overridden ? "overridden" : ""}" data-profile-field="alertRangeClose" data-profile-subgroup="${esc(meta.subgroup)}" title="${esc(label)}">
          ${profileFieldLabelMarkup("alertRangeClose", label)}
          ${profileFieldControlMarkup(`<select class="profile-subselect" data-profile-alert-close-range data-class-index="${esc(item.index)}" data-original="${esc(originalRaw)}" aria-label="${esc(label)}" title="${esc(label)}">
            <option value="0"${closeEnabled ? "" : " selected"}>No</option>
            <option value="1"${closeEnabled ? " selected" : ""}>Yes</option>
          </select>`)}
        </label>
      `;
    }

    function profileEditAlertFields(item) {
      const originalRaw = item.profile.alertRange?.raw ?? "0";
      const raw = pendingProfileValue(item.index, "alertRange", originalRaw);
      const inheritedOverride = isOverrideProfile(item) && !raw;
      const fields = [
        profileEditFieldItem(item, "alertState"),
        profileEditFieldItem(item, "alertEmote"),
        profileEditFieldItem(item, "alertTime"),
        profileFieldItem(ALERT_RANGE_TYPE_FIELD, profileEditAlertRangeTypeField(item)),
      ];
      if (alertRangeSupportsClose(raw)) {
        fields.push(profileFieldItem("alertRangeClose", profileEditAlertCloseRangeField(item)));
      }
      if (alertRangeNeedsLength(raw) || inheritedOverride) {
        fields.push(profileEditFieldItem(item, "alertness", {
          className: "profile-suboption-field",
          hint: "Range length",
        }));
      }
      fields.push(profileEditFieldItem(item, "alertChance"));
      fields.push(profileFieldItem(ALERT_ACTION_SPECIAL_FIELD, profileEditScopedSpecialActionField(
        item,
        ALERT_ACTION_SPECIAL_FIELD,
        profileFieldLabel(ALERT_ACTION_SPECIAL_FIELD),
        "Alert-time special action",
      )));
      return {
        count: fields.length,
        items: fields,
        html: fields.map(field => field.html).join(""),
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
        hopTime: "hopTime",
        hopSpinSpeed: "hopSpinSpeed",
        chainHops: "ramAccelerationSteps",
        chainHopPause: "ramMaxSpeed",
        chainPauseAction: "chainPauseAction",
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
        hopTime: "hopTime",
        hopSpinSpeed: "attentiveHopSpinSpeed",
        chainHops: "ramAccelerationSteps",
        chainHopPause: "ramMaxSpeed",
        chainPauseAction: "chainPauseAction",
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
        hopTime: "hopTime",
        hopSpinSpeed: "hopSpinSpeed",
        chainHops: "ramAccelerationSteps",
        chainHopPause: "ramMaxSpeed",
        chainPauseAction: "chainPauseAction",
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
      const inheritedOverride = isOverrideProfile(item) && !raw;
      const showsChainControls = inheritedOverride || (movementStyleUsesMovement(raw) && !movementStyleUsesRam(raw));
      const fields = [
        profileEditFieldItem(item, fieldKey),
      ];
      if (speedFieldKey && (movementStyleUsesMovement(raw) || inheritedOverride)) {
        fields.push(profileEditFieldItem(item, speedFieldKey, {
          className: "profile-suboption-field",
          hint: `${profileFieldLabel(fieldKey)} speed`,
        }));
      }
      if (movementStyleUsesHop(raw) || inheritedOverride) {
        fields.push(
          profileEditFieldItem(item, suboptionFields.hopAllowNonCardinal, {
            className: "profile-suboption-field",
            hint: "Allow diagonal/non-cardinal hops",
          }),
          profileEditFieldItem(item, suboptionFields.hopMinDistance, {
            className: "profile-suboption-field",
            hint: "Minimum hop distance",
          }),
          profileEditFieldItem(item, suboptionFields.hopMaxDistance, {
            className: "profile-suboption-field",
            hint: "Maximum hop distance",
          }),
          profileEditFieldItem(item, suboptionFields.hopTime, {
            className: "profile-suboption-field",
            hint: "Ticks for a 1-tile hop. Extra tiles are slightly faster; 0 is immediate.",
          }),
          profileEditFieldItem(item, suboptionFields.hopSpinSpeed, {
            className: "profile-suboption-field",
            hint: "Ticks per 90-degree facing turn during Hop. 0 disables spin. Max 15.",
            numberLimits: { min: 0, max: 15 },
          }),
          profileEditFieldItem(item, suboptionFields.hopPause, {
            className: "profile-suboption-field",
            hint: "Ticks to wait after each Hop before the next movement decision. 0 removes the pause.",
          }),
        );
      }
      if (showsChainControls) {
        fields.push(
          profileEditFieldItem(item, suboptionFields.chainHops, {
            className: "profile-suboption-field",
            label: inheritedOverride ? "Chain moves / RAM steps" : "Chain moves",
            shortLabel: inheritedOverride ? "Chain/RAM" : "Chain",
            unit: inheritedOverride ? "" : "moves",
            hint: "Consecutive completed movement steps before applying Chain pause. 0 disables chain pauses.",
            numberLimits: { min: 0, max: 32 },
          }),
          profileEditFieldItem(item, suboptionFields.chainHopPause, {
            className: "profile-suboption-field",
            label: inheritedOverride ? "Chain pause / RAM max" : "Chain pause",
            shortLabel: inheritedOverride ? "Pause/RAM" : "Pause",
            unit: inheritedOverride ? "" : "ticks",
            hint: "Ticks to wait after the Chain move count is reached. 0 keeps chaining without an extra pause.",
            numberLimits: { min: 0, max: 255 },
          }),
          profileEditFieldItem(item, suboptionFields.chainPauseAction, {
            className: "profile-suboption-field",
            hint: "Optional action to play when Chain pause is reached.",
          }),
        );
      }
      if (movementStyleUsesPhantomTeleport(raw) || inheritedOverride) {
        fields.push(
          profileEditFieldItem(item, suboptionFields.teleportTime, {
            className: "profile-suboption-field",
            hint: "Ticks spent hidden/flickering during Phantom Teleport movement",
          }),
          profileEditFieldItem(item, suboptionFields.teleportPause, {
            className: "profile-suboption-field",
            hint: "Ticks to wait after each Phantom Teleport before the next movement decision",
          }),
        );
      }
      if (movementStyleUsesRam(raw) || inheritedOverride) {
        fields.push(
          profileEditFieldItem(item, suboptionFields.ramAccelerationSteps, {
            className: "profile-suboption-field",
            hint: "Completed RAM steps before speed increases by 1. 0 disables acceleration.",
          }),
          profileEditFieldItem(item, suboptionFields.ramMaxSpeed, {
            className: "profile-suboption-field",
            hint: "Highest movement speed RAM can accelerate to. The state speed is the starting speed.",
          }),
        );
      }
      const uniqueFields = profileUniqueFieldItems(fields);
      return {
        count: uniqueFields.length,
        items: uniqueFields,
        html: uniqueFields.map(field => field.html).join(""),
      };
    }

    function profileEditChillFields(item) {
      const movementFields = profileEditMovementFields(item, "chillAction", "chillSpeed", "chill");
      const chillRaw = pendingProfileValue(
        item.index,
        "chillState",
        item.profile.chillState?.raw ?? "0",
      );
      const inheritedOverride = isOverrideProfile(item) && !chillRaw;
      const canSelectTarget = activeBehaviorCanSelectTarget(chillRaw) || inheritedOverride;
      const usesAllowedTile = behaviorUsesAllowedTile(chillRaw) || inheritedOverride;
      const fields = [
        profileEditFieldItem(item, "chillState"),
      ];
      if (canSelectTarget) {
        fields.push(profileEditFieldItem(item, "chillTarget", {
          className: "profile-suboption-field",
          hint: "Where this chill behavior tries to go. Movement style decides how it gets there.",
        }));
      }
      if (usesAllowedTile) {
        fields.push(profileEditFieldItem(item, "chillAllowedTile", {
          className: "profile-suboption-field",
          hint: "Tile type this behavior may target",
        }));
        fields.push(profileEditFieldItem(item, "chillAllowedTile2", {
          className: "profile-suboption-field",
          hint: "Optional second tile type this behavior may target",
        }));
      }
      fields.push(...movementFields.items);
      return {
        count: fields.length,
        items: fields,
        html: fields.map(field => field.html).join(""),
      };
    }

    function profileEditActiveFields(item) {
      const movementFields = profileEditMovementFields(item, "movementStyle", "attentiveSpeed", "attentive");
      const activeRaw = pendingProfileValue(
        item.index,
        "attentiveState",
        item.profile.attentiveState?.raw ?? "0",
      );
      const specialRaw = pendingProfileValue(
        item.index,
        "alertSpecialAction",
        item.profile.alertSpecialAction?.raw ?? ALERT_SPECIAL_NONE_RAW,
      );
      const movementRaw = pendingProfileValue(
        item.index,
        "movementStyle",
        item.profile.movementStyle?.raw ?? "0",
      );
      const targetRaw = pendingProfileValue(
        item.index,
        "targetSelector",
        item.profile.targetSelector?.raw ?? "0",
      );
      const throwSpecialRaw = scopedSpecialActionRaw(ACTIVE_ACTION_SPECIAL_FIELD, specialRaw);
      const inheritedOverride = isOverrideProfile(item) && !activeRaw;
      const canSelectTarget = activeBehaviorCanSelectTarget(activeRaw) || inheritedOverride;
      const usesAllowedTile = behaviorUsesAllowedTile(activeRaw) || inheritedOverride;
      const showsCircleTarget = targetSelectorIsCirclePlayer(targetRaw) || (isOverrideProfile(item) && !targetRaw);
      const showsThrowRange = alertSpecialActionPickupThrows(throwSpecialRaw) || (isOverrideProfile(item) && !throwSpecialRaw);
      const throwRangeSharesHopRange = showsThrowRange && (movementStyleUsesHop(movementRaw) || (isOverrideProfile(item) && !movementRaw));
      const fields = [
        profileEditFieldItem(item, "attentiveState"),
        profileEditFieldItem(item, "stamina"),
      ];
      if (canSelectTarget) {
        fields.push(profileEditFieldItem(item, "targetSelector", {
          className: "profile-suboption-field",
          hint: "Where this behavior tries to go. Movement style decides how it gets there.",
        }));
        if (showsCircleTarget) {
          fields.push(
            profileEditFieldItem(item, "attentiveCircleRadius", {
              className: "profile-suboption-field",
              hint: "Radius around the player for Circle player target. 0 behaves as 1 tile.",
              numberLimits: { min: 0, max: 8 },
            }),
            profileEditFieldItem(item, "attentiveContinueWhenArrived", {
              className: "profile-suboption-field",
              hint: "Keep choosing new circle-ring tiles after reaching one.",
            }),
          );
        }
      }
      if (usesAllowedTile) {
        fields.push(profileEditFieldItem(item, "attentiveAllowedTile", {
          className: "profile-suboption-field",
          hint: "Tile type this behavior may target",
        }));
        fields.push(profileEditFieldItem(item, "attentiveAllowedTile2", {
          className: "profile-suboption-field",
          hint: "Optional second tile type this behavior may target",
        }));
      }
      fields.push(profileFieldItem(ACTIVE_ACTION_SPECIAL_FIELD, profileEditScopedSpecialActionField(
        item,
        ACTIVE_ACTION_SPECIAL_FIELD,
        profileFieldLabel(ACTIVE_ACTION_SPECIAL_FIELD),
        "Active-state special action",
      )));
      if (showsThrowRange) {
        fields.push(profileEditFieldItem(item, "attentiveHopMaxDistance", {
          className: "profile-suboption-field",
          label: throwRangeSharesHopRange ? "Max hop / throw range" : "Throw range",
          shortLabel: throwRangeSharesHopRange ? "Hop/throw" : "Throw",
          hint: throwRangeSharesHopRange
            ? "Maximum hop distance and aligned throw range before throwing the carried Pokemon (1-8)"
            : "Maximum aligned tiles away before throwing the carried Pokemon (1-8)",
        }));
      }
      fields.push(...movementFields.items);
      if (canSelectTarget) {
        fields.push(profileEditFieldItem(item, "attentiveChaseBoostDistance", {
          className: "profile-suboption-field",
          hint: "Minimum target distance before active chase uses boosted speed. 0 disables it.",
        }));
        fields.push(profileEditFieldItem(item, "attentiveChaseBoostSpeed", {
          className: "profile-suboption-field",
          hint: "Active chase speed while the target is at least the boost distance away. 0 disables it.",
        }));
      }
      const uniqueFields = profileUniqueFieldItems(fields);
      return {
        count: uniqueFields.length,
        items: uniqueFields,
        html: uniqueFields.map(field => field.html).join(""),
      };
    }

    function profileEditTiredFields(item) {
      const movementFields = profileEditMovementFields(item, "specialAction", "tiredSpeed", "tired");
      const tiredRaw = pendingProfileValue(
        item.index,
        "tiredState",
        item.profile.tiredState?.raw ?? "0",
      );
      const inheritedOverride = isOverrideProfile(item) && !tiredRaw;
      const usesAllowedTile = behaviorUsesAllowedTile(tiredRaw) || inheritedOverride;
      const fields = [
        profileEditFieldItem(item, "tiredState"),
      ];
      if (usesAllowedTile) {
        fields.push(profileEditFieldItem(item, "tiredAllowedTile", {
          className: "profile-suboption-field",
          hint: "Tile type this behavior may target",
        }));
        fields.push(profileEditFieldItem(item, "tiredAllowedTile2", {
          className: "profile-suboption-field",
          hint: "Optional second tile type this behavior may target",
        }));
      }
      fields.push(...movementFields.items);
      fields.push(profileEditFieldItem(item, "restTime"));
      return {
        count: fields.length,
        items: fields,
        html: fields.map(field => field.html).join(""),
      };
    }

    function profileSectionFieldIsAvailable(fieldKey, availableFields = null) {
      const fieldSet = availableFields || new Set((appData.fields || []).map(field => field.key));
      const storedField = profileStoredFieldKey(fieldKey);
      const hidden = (PROFILE_DIRECT_EDIT_HIDDEN_FIELDS.has(fieldKey)
          || PROFILE_DIRECT_EDIT_HIDDEN_FIELDS.has(storedField))
        && !PROFILE_SECTION_CLEARABLE_HIDDEN_FIELDS.has(fieldKey)
        && !PROFILE_SECTION_CLEARABLE_HIDDEN_FIELDS.has(storedField);
      return fieldSet.has(storedField)
        && !hidden;
    }

    function profileClearableSectionFields(fields) {
      const availableFields = new Set((appData.fields || []).map(field => field.key));
      const clearFields = [];
      const seenFields = new Set();
      const seenStoredFields = new Set();
      Array.from(new Set(fields)).forEach(field => {
        if (!profileSectionFieldIsAvailable(field, availableFields)) return;
        if (PROFILE_SCOPED_SPECIAL_ACTION_FIELDS.has(field)) {
          if (seenFields.has(field)) return;
          seenFields.add(field);
          clearFields.push(field);
          return;
        }
        const storedField = profileStoredFieldKey(field);
        if (seenStoredFields.has(storedField)) return;
        seenStoredFields.add(storedField);
        clearFields.push(field);
      });
      return clearFields;
    }

    function profileStoredFieldKey(fieldKey) {
      if (fieldKey === ALERT_RANGE_TYPE_FIELD || fieldKey === "alertRangeClose") return "alertRange";
      if (fieldKey === SPAWN_DESTINATION_TYPE_FIELD || fieldKey === "spawnDestinationDistance") return "spawnDestination";
      if (PROFILE_SCOPED_SPECIAL_ACTION_FIELDS.has(fieldKey)) return "alertSpecialAction";
      return fieldKey;
    }

    function profileFieldRawForCount(item, fieldKey) {
      const storedField = profileStoredFieldKey(fieldKey);
      const raw = pendingProfileValue(item.index, storedField, item.profile[storedField]?.raw ?? "");
      if (PROFILE_SCOPED_SPECIAL_ACTION_FIELDS.has(fieldKey)) {
        return scopedSpecialActionCountRaw(fieldKey, raw);
      }
      return raw;
    }

    function profileFieldHasOverrideValue(item, fieldKey) {
      if (!isOverrideProfile(item)) return false;
      return String(profileFieldRawForCount(item, fieldKey) ?? "") !== "";
    }

    function profileFieldHasPendingCustomValue(item, fieldKey) {
      const storedField = profileStoredFieldKey(fieldKey);
      const originalRaw = item.profile[storedField]?.raw ?? "";
      const raw = pendingProfileValue(item.index, storedField, originalRaw);
      if (PROFILE_SCOPED_SPECIAL_ACTION_FIELDS.has(fieldKey)) {
        return scopedSpecialActionCountRaw(fieldKey, raw) !== scopedSpecialActionCountRaw(fieldKey, originalRaw);
      }
      return raw !== originalRaw;
    }

    function profileSectionCount(item, fields) {
      const clearableFields = profileClearableSectionFields(fields);
      if (isOverrideProfile(item)) {
        return clearableFields.filter(field => profileFieldHasOverrideValue(item, field)).length;
      }
      return clearableFields.filter(field => profileFieldHasPendingCustomValue(item, field)).length;
    }

    function profileSectionCountLabel(item, fields, visibleCount) {
      const total = profileClearableSectionFields(fields).length || fields.length || visibleCount;
      const active = profileSectionCount(item, fields);
      if (isOverrideProfile(item)) {
        return `${active} / ${total}`;
      }
      return active ? `${active} / ${total}` : String(visibleCount);
    }

    function profileSubgroupLabel(subgroup) {
      return subgroup || "Other";
    }

    function profileRenderFieldSubgroups(fieldItems) {
      const groups = [];
      const byKey = new Map();
      fieldItems.filter(item => item?.html).forEach(item => {
        const key = profileSubgroupLabel(item.subgroup);
        if (!byKey.has(key)) {
          const group = { key, items: [] };
          byKey.set(key, group);
          groups.push(group);
        }
        byKey.get(key).items.push(item);
      });
      return groups.map(group => `
        <div class="profile-field-subgroup" data-profile-subgroup="${esc(group.key)}">
          <div class="profile-subgroup-head">
            <span class="profile-subgroup-title">${esc(group.key)}</span>
            <span class="profile-subgroup-count">${esc(group.items.length)}</span>
          </div>
          <div class="profile-architecture-fields">
            ${group.items.map(item => item.html).join("")}
          </div>
        </div>
      `).join("");
    }

    function profileSectionClearButton(item, label, fields) {
      const clearFields = profileClearableSectionFields(fields);
      if (!isOverrideProfile(item) || !clearFields.length) return "";
      const hasOverrides = profileSectionCount(item, clearFields) > 0;
      return `
        <button class="profile-section-clear" type="button" data-profile-section-clear data-action="clear-profile-section" data-class-index="${esc(item.index)}" data-fields="${esc(clearFields.join(","))}" ${hasOverrides ? "" : "disabled"} title="${esc(`Make ${label} inherit`)}" aria-label="${esc(`Make all ${label} values inherit`)}">
          ${interfaceIcon("eraser")}
        </button>
      `;
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
        const fieldItems = customFields?.items || fields.map(field => profileEditFieldItem(item, field));
        fieldItems.forEach(field => known.add(profileStoredFieldKey(field.fieldKey)));
        const sectionFields = fieldItems.map(field => field.fieldKey);
        const countLabel = profileSectionCountLabel(item, sectionFields, fieldItems.length);
        return `
          <section class="profile-architecture-group profile-architecture-${esc(group.key)}" data-profile-section-fields="${esc(sectionFields.join(","))}">
            <div class="profile-architecture-head">
              <span class="profile-architecture-title">${encounterBadge(group.icon, group.typeClass, group.label)} ${esc(group.label)}</span>
              <span class="profile-architecture-head-actions">
                ${profileSectionClearButton(item, group.label, sectionFields)}
                <span class="count" data-profile-section-count title="${esc(isOverrideProfile(item) ? "Overridden fields / total fields" : "Changed fields / total fields")}">${esc(countLabel)}</span>
              </span>
            </div>
            <div class="profile-field-subgroups">${profileRenderFieldSubgroups(fieldItems)}</div>
          </section>
        `;
      });
      const remaining = appData.fields.filter(field =>
        !known.has(field.key)
        && !PROFILE_DIRECT_EDIT_HIDDEN_FIELDS.has(field.key));
      if (remaining.length) {
        const remainingFields = remaining.map(field => field.key);
        groups.push(`
          <section class="profile-architecture-group profile-architecture-other" data-profile-section-fields="${esc(remainingFields.join(","))}">
            <div class="profile-architecture-head">
              <span class="profile-architecture-title">${encounterBadge("target", "type-placement", "Other")} Other</span>
              <span class="profile-architecture-head-actions">
                ${profileSectionClearButton(item, "Other", remainingFields)}
                <span class="count" data-profile-section-count>${esc(profileSectionCountLabel(item, remainingFields, remaining.length))}</span>
              </span>
            </div>
            <div class="profile-field-subgroups">
              ${profileRenderFieldSubgroups(remaining.map(field => profileEditFieldItem(item, field.key)))}
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
            <span class="field-label">${esc(profileFieldLabel(field.key))}</span>
            <input class="profile-combo" type="text" value="${esc(profileComboDisplay(field.key, raw))}" data-class-index="${esc(item.index)}" data-field="${esc(field.key)}" data-original="${esc(originalRaw)}" autocomplete="off" role="combobox" aria-autocomplete="list" aria-expanded="false">
          </label>
        `;
      }).join("");
    }

    function profileClassChanged(item) {
      if (isOverrideProfile(item)) {
        const orders = profileOverrideOrders(item);
        return appData.fields.some(field =>
          profileOverrideProfileEdits.has(editKey(item.index, field.key))
        ) || orders.some(order => profileOverrideNameEdits.has(order) || profileOverrideRemoveEdits.has(order));
      }
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
      if (isOverrideProfile(item)) {
        return encounterBadge("target", "type-placement", profileDisplayName(item));
      }
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

    function behaviorOverrideMaskLabels(behavior) {
      return behavior?.maskLabels
        || [
          ...(behavior?.mask?.labels || []),
          ...(behavior?.mask2?.labels || []),
          ...(behavior?.mask3?.labels || []),
        ];
    }

    function profileCoreChips(item) {
      if (isOverrideProfile(item)) {
        const mask = item.override ? behaviorOverrideMaskLabels(item.override) : [];
        const chips = [
          ["target", "type-placement", "Match", item.summary || "Override profile"],
          ["dice", "type-flow", "Fields", `${mask.length} active`],
        ];
        return chips.map(([icon, typeClass, label, value]) => `
          <span class="profile-core-chip" title="${esc(label)}: ${esc(value)}">
            ${encounterBadge(icon, typeClass, label)}
            <span class="profile-core-value">${esc(value)}</span>
          </span>
        `).join("");
      }
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
      if (isOverrideProfile(item)) {
        const name = profileDisplayName(item);
        const orders = profileOverrideOrders(item).join(",");
        const removing = profileOverrideIsRemoving(item);
        return `
          <span class="profile-management-actions" aria-label="Override profile actions">
            <button class="profile-management-button" type="button" data-action="create-override-profile" title="New override profile" aria-label="New override profile">
              ${interfaceIcon("target")}
            </button>
            <button class="profile-management-button" type="button" data-action="duplicate-profile" data-class-index="${esc(item.index)}" title="Duplicate ${esc(name)}" aria-label="Duplicate override profile">
              ${interfaceIcon("copy")}
            </button>
            <button class="profile-management-button" type="button" data-action="rename-profile" data-class-index="${esc(item.index)}" title="Rename ${esc(name)}" aria-label="Rename override profile">
              ${interfaceIcon("edit")}
            </button>
            <button class="profile-management-button danger" type="button" data-action="toggle-remove-profile-override" data-override-orders="${esc(orders)}" title="Remove override profile" aria-label="Remove override profile">
              ${interfaceIcon(removing ? "plus" : "trash")}
            </button>
          </span>
        `;
      }
      const renameDisabled = !item || item.canRename === false;
      const deleteDisabled = !item || item.canDelete === false;
      const protectedProfile = item && !profileIsDefaultClass(item.index) && (item.canRename === false || item.canDelete === false);
      const renameTitle = !item
        ? "Rename profile"
        : profileIsDefaultClass(item.index)
        ? "Default profile cannot be renamed"
        : protectedProfile
          ? "This behavior class is referenced by runtime code and cannot be renamed safely"
          : `Rename ${item.name}`;
      const deleteTitle = profileIsDefaultClass(item?.index)
        ? "Default profile cannot be deleted"
        : deleteDisabled
          ? "This behavior class is referenced by runtime code and cannot be deleted safely"
          : `Delete ${item.name}`;
      return `
        <span class="profile-management-actions" aria-label="Profile actions">
          <button class="profile-management-button" type="button" data-action="create-profile" title="New profile from Default" aria-label="New profile from Default">
            ${interfaceIcon("plus")}
          </button>
          <button class="profile-management-button" type="button" data-action="create-override-profile" title="New override profile" aria-label="New override profile">
            ${interfaceIcon("target")}
          </button>
          <button class="profile-management-button" type="button" data-action="convert-profile-to-override" data-class-index="${esc(item?.index ?? "")}" ${!item ? "disabled" : ""} title="${item ? `Create override profile from ${esc(item.name)}` : "Create override profile from this profile"}" aria-label="Create override profile from this profile">
            ${interfaceIcon("bolt")}
          </button>
          <button class="profile-management-button" type="button" data-action="duplicate-profile" data-class-index="${esc(item?.index ?? "")}" ${!item ? "disabled" : ""} title="${item ? `Duplicate ${esc(item.name)}` : "Duplicate profile"}" aria-label="Duplicate profile">
            ${interfaceIcon("copy")}
          </button>
          <button class="profile-management-button" type="button" data-action="rename-profile" data-class-index="${esc(item?.index ?? "")}" ${renameDisabled ? "disabled" : ""} title="${esc(renameTitle)}" aria-label="Rename profile">
            ${interfaceIcon("edit")}
          </button>
          <button class="profile-management-button danger" type="button" data-action="delete-profile" data-class-index="${esc(item?.index ?? "")}" ${deleteDisabled ? "disabled" : ""} title="${esc(deleteTitle)}" aria-label="Delete profile">
            ${interfaceIcon("trash")}
          </button>
        </span>
      `;
    }

    function profileAddTargetKindOption(kind) {
      return PROFILE_ADD_TARGET_KINDS.find(option => option.key === kind) || null;
    }

    function profileValidAddTargetKind(kind = profileAddTargetKind) {
      return profileAddTargetKindOption(kind) ? kind : "pokemon";
    }

    function persistProfileAddDraft() {
      localStorage.setItem("owProfileAddTargetKind", profileAddTargetKind || "");
      localStorage.setItem("owProfileAddSpawnPool", profileAddSpawnPool || "");
      localStorage.setItem("owProfileAddType", profileAddType || "");
    }

    function profileAddTargetKindOptionsHtml(selectedKind) {
      return PROFILE_ADD_TARGET_KINDS.map(option => `
        <option value="${esc(option.key)}"${option.key === selectedKind ? " selected" : ""}>${esc(option.label)}</option>
      `).join("");
    }

    function profileAddSpawnPoolOptionsHtml(selectedRaw) {
      return PROFILE_OVERRIDE_SPAWN_POOLS.map(pool => `
        <option value="${esc(pool.raw)}"${pool.raw === selectedRaw ? " selected" : ""}>${esc(pool.label)}</option>
      `).join("");
    }

    function profileValidAddType(typeSymbol = profileAddType) {
      return profileTypeOption(typeSymbol)?.symbol || ((appData.typeOptions || [])[0]?.symbol || "");
    }

    function profileAddTypeOptionsHtml(selectedType) {
      return (appData.typeOptions || []).map(type => `
        <option value="${esc(type.symbol)}"${type.symbol === selectedType ? " selected" : ""}>${esc(type.name)}</option>
      `).join("");
    }

    function profileAddTargetControlHtml(kind = profileValidAddTargetKind()) {
      const option = profileAddTargetKindOption(kind) || PROFILE_ADD_TARGET_KINDS[0];
      if (option.key === "spawnPool") {
        const selectedPool = profileSpawnPoolOption(profileAddSpawnPool)?.raw || PROFILE_OVERRIDE_SPAWN_POOLS[0].raw;
        return `
          <span class="profile-add-species-wrap">
            ${encounterBadge(option.icon, option.typeClass, option.label)}
            <select class="profile-add-spawn-pool" data-profile-add-spawn-pool aria-label="Spawn pool">
              ${profileAddSpawnPoolOptionsHtml(selectedPool)}
            </select>
          </span>
        `;
      }
      if (option.key === "type") {
        const selectedType = profileValidAddType();
        return `
          <span class="profile-add-species-wrap">
            ${encounterBadge(option.icon, option.typeClass, option.label)}
            <select class="profile-add-type" data-profile-add-type aria-label="Pokemon type">
              ${profileAddTypeOptionsHtml(selectedType)}
            </select>
          </span>
        `;
      }
      return `
        <span class="profile-add-species-wrap">
          ${encounterBadge(option.icon, option.typeClass, option.label)}
          <input class="profile-add-input" type="text" list="profileSpeciesOptions" placeholder="${esc(option.placeholder)}" autocomplete="off" aria-label="${esc(option.label)}">
        </span>
      `;
    }

    function profileAddFieldsHtml(item) {
      const kind = profileValidAddTargetKind();
      const kindOption = profileAddTargetKindOption(kind);
      const name = profileDisplayName(item);
      return `
        <label class="profile-add-kind-wrap" title="Add target kind">
          ${encounterBadge(kindOption?.icon || "target", kindOption?.typeClass || "type-placement", "Target kind")}
          <select class="profile-add-kind" data-profile-add-kind aria-label="Add target kind">
            ${profileAddTargetKindOptionsHtml(kind)}
          </select>
        </label>
        <span class="profile-add-target-host" data-profile-add-target-host>
          ${profileAddTargetControlHtml(kind)}
        </span>
        <button class="control profile-add-button" type="submit" title="Add target to ${esc(name)}">
          ${interfaceIcon("plus")}
          <span>Add</span>
        </button>
      `;
    }

    function profileRowAddControl(item) {
      const name = profileDisplayName(item);
      return `
        <button class="profile-row-add-button" type="button" data-action="quick-add-profile" data-class-index="${esc(item.index)}" aria-label="Add target to ${esc(name)}" title="Add target to ${esc(name)}">
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
      const item = profileClassByIndex(classIndex);
      const overrideHitOrders = isOverrideProfile(item) ? profileOverrideHitOrdersForAssignment(assignment, item) : [];
      const active = species.symbol === selectedSymbol ? " active" : "";
      const pendingOverrideRemoval = overrideHitOrders.some(order => profileOverrideRemoveEdits.has(order));
      const changed = (profileMemberEdits.has(species.symbol) || pendingOverrideRemoval) ? " changed" : "";
      const canRemove = isOverrideProfile(item)
        ? overrideHitOrders.length > 0
        : !profileIsDefaultClass(classIndex);
      const removeTitle = isOverrideProfile(item)
        ? `Remove ${species.name} from ${profileDisplayName(item)}`
        : `Remove ${species.name} from this profile`;
      return `
        <span class="profile-member-item${changed}" data-symbol="${esc(species.symbol)}">
          <button class="profile-member-chip${active}${changed}" type="button" data-symbol="${esc(species.symbol)}" aria-label="View ${esc(species.name)}" title="${esc(species.symbol)}">
            ${iconTag(species, "profile-icon")}
            <span class="profile-member-name">${esc(species.name)}</span>
          </button>
          ${canRemove ? `
            <button class="profile-member-remove" type="button" data-action="remove-profile-member" data-symbol="${esc(species.symbol)}" data-class-index="${esc(classIndex)}" data-override-orders="${esc(overrideHitOrders.join(","))}" aria-label="${esc(removeTitle)}" title="${esc(removeTitle)}">
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
          ${profileAddFieldsHtml(item)}
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
      const name = profileDisplayName(item);
      const title = selected ? `Assign ${selected.name} Pokemon to ${name}` : `Assign Pokemon by type to ${name}`;
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
      const supported = new Set(appData?.overrideFieldKeys || []);
      if (!supported.has(fieldKey)) return null;
      if (PROFILE_OVERRIDE_BUILDER_HIDDEN_FIELDS.has(fieldKey)) return null;
      const field = (appData.fields || []).find(field => field.key === fieldKey) || null;
      return field ? { ...field, label: profileFieldLabel(fieldKey) } : null;
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

    function profileOverrideMatchForSpecies(speciesSymbol) {
      return {
        species: speciesSymbol,
        groupMask: "OW_WILD_BEHAVIOR_GROUP_NONE",
        terrain: "OW_WILD_BEHAVIOR_MATCH_ANY_TERRAIN",
        minLevel: "OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY",
        maxLevel: "OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY",
        shiny: "OW_WILD_BEHAVIOR_MATCH_ANY_SHINY",
        behaviorClass: "OW_WILD_BEHAVIOR_MATCH_ANY_CLASS",
      };
    }

    function profileOverrideMatchForNoTarget() {
      return {
        species: "OW_WILD_BEHAVIOR_MATCH_ANY_SPECIES",
        groupMask: "OW_WILD_BEHAVIOR_GROUP_NONE",
        terrain: "OW_WILD_BEHAVIOR_MATCH_ANY_TERRAIN",
        minLevel: "OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY",
        maxLevel: "OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY",
        shiny: "OW_WILD_BEHAVIOR_MATCH_ANY_SHINY",
        behaviorClass: PROFILE_OVERRIDE_NO_TARGET_CLASS_RAW,
      };
    }

    function profileOverrideRawMatch(match) {
      return {
        species: match?.species?.raw || "OW_WILD_BEHAVIOR_MATCH_ANY_SPECIES",
        groupMask: match?.groupMask?.raw || "OW_WILD_BEHAVIOR_GROUP_NONE",
        terrain: match?.terrain?.raw || "OW_WILD_BEHAVIOR_MATCH_ANY_TERRAIN",
        minLevel: match?.minLevel?.raw || "OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY",
        maxLevel: match?.maxLevel?.raw || "OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY",
        shiny: match?.shiny?.raw || "OW_WILD_BEHAVIOR_MATCH_ANY_SHINY",
        behaviorClass: match?.behaviorClass?.raw || "OW_WILD_BEHAVIOR_MATCH_ANY_CLASS",
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

    function profileFamilyBaseSymbol(species) {
      if (!species) return "";
      if (species.familyBaseSymbol) return species.familyBaseSymbol;
      if (species.baseSymbol) {
        const baseSpecies = profileSpeciesBySymbol.get(species.baseSymbol);
        return baseSpecies?.familyBaseSymbol || species.baseSymbol;
      }
      return species.symbol || "";
    }

    function profileEvolutionFamilySpecies(seedSpecies) {
      const familyBase = profileFamilyBaseSymbol(seedSpecies);
      const members = profileFamilyMembersByBaseSymbol.get(familyBase) || [];
      if (members.length) return members;
      return seedSpecies && seedSpecies.symbol !== "SPECIES_NONE" ? [seedSpecies] : [];
    }

    function uniqueProfileSpecies(speciesList) {
      const seen = new Set();
      const result = [];
      (speciesList || []).forEach(species => {
        if (!species || species.symbol === "SPECIES_NONE" || seen.has(species.symbol)) return;
        seen.add(species.symbol);
        result.push(species);
      });
      return result;
    }

    function profileAddTargetFromForm(form) {
      const kind = profileValidAddTargetKind(form.querySelector("[data-profile-add-kind]")?.value || profileAddTargetKind);
      if (kind === "spawnPool") {
        const pool = profileSpawnPoolOption(form.querySelector("[data-profile-add-spawn-pool]")?.value || profileAddSpawnPool);
        return pool ? { kind, pool, label: pool.label } : null;
      }
      if (kind === "type") {
        const select = form.querySelector("[data-profile-add-type]");
        const type = profileTypeOption(select?.value || profileAddType || profileValidAddType());
        return type ? { kind, type, select, label: `${type.name} typing` } : { kind, select };
      }
      const input = form.querySelector(".profile-add-input");
      const species = profileSpeciesOption(input?.value || "");
      return species ? { kind, species, input, label: kind === "family" ? `${species.name} family` : species.name } : { kind, input };
    }

    function profileAddTargetIsValid(target) {
      if (!target) return false;
      if (target.kind === "spawnPool") return Boolean(target.pool);
      if (target.kind === "type") return Boolean(target.type);
      return Boolean(target.species);
    }

    function profileAddTargetInvalidMessage(target) {
      if (target?.kind === "family") return "Choose a valid family seed Pokemon";
      if (target?.kind === "type") return "Choose a valid Pokemon type";
      return "Choose a valid target";
    }

    function profileAddTargetValue(target) {
      if (target?.kind === "spawnPool") return target.pool?.raw || "";
      if (target?.kind === "type") return target.type?.symbol || "";
      return target?.species?.symbol || "";
    }

    function profileAddTargetMatchCount(target) {
      if (target?.kind === "spawnPool") return profileOverrideSpawnPoolMatches(target.pool).length;
      if (target?.kind === "type") return profileBulkTypeMatches(target.type?.symbol).length;
      return profileOverrideMatchesForAddTarget(target).length;
    }

    function clearProfileAddTargetInput(target) {
      if (target?.input) target.input.value = "";
    }

    function profileAddTargetSpecies(target) {
      if (!target) return [];
      if (target.kind === "spawnPool") {
        return profileOverrideSpawnPoolMatches(target.pool);
      }
      if (target.kind === "type") {
        return profileBulkTypeMatches(target.type?.symbol);
      }
      if (target.kind === "family") {
        return uniqueProfileSpecies(profileEvolutionFamilySpecies(target.species));
      }
      return target.species ? [target.species] : [];
    }

    function profileSpeciesForPendingOverrideEdit(edit) {
      if (!edit) return [];
      if (edit.targetKind === "spawnPool") {
        return profileOverrideSpawnPoolMatches(profileSpawnPoolOption(edit.targetValue));
      }
      if (edit.targetKind === "type") {
        return profileBulkTypeMatches(edit.targetValue);
      }
      if (edit.targetKind === "family") {
        return uniqueProfileSpecies(profileEvolutionFamilySpecies(profileSpeciesOption(edit.targetValue)));
      }
      if (edit.targetKind === "pokemon") {
        const species = profileSpeciesOption(edit.targetValue);
        return species ? [species] : [];
      }
      const species = [];
      (edit.matches || [edit.match]).forEach(match => {
        const symbol = match?.species || "";
        if (!symbol || symbol === "SPECIES_NONE" || symbol.startsWith("OW_WILD_BEHAVIOR_MATCH_ANY_")) return;
        const entry = profileSpeciesBySymbol.get(symbol);
        if (entry) species.push(entry);
      });
      return uniqueProfileSpecies(species);
    }

    function profileAssignableSpeciesForTarget(item, target) {
      return profileAddTargetSpecies(target).filter(species =>
        assignmentsBySymbol.has(species.symbol)
        && String(profilePendingClassValueForSymbol(species.symbol)) !== String(item.index)
      );
    }

    function profileOverrideMatchesForAddTarget(target) {
      if (!target) return [];
      if (target.kind === "spawnPool") {
        return target.pool ? [profileOverrideMatchForSpawnPool(target.pool)] : [];
      }
      if (target.kind === "type") {
        return target.type ? [profileOverrideMatchForType(target.type.symbol)] : [];
      }
      return profileAddTargetSpecies(target).map(species => profileOverrideMatchForSpecies(species.symbol));
    }

    function profileOverrideFieldsForItem(item) {
      const fields = {};
      (appData.fields || []).forEach(field => {
        const originalRaw = item.profile?.[field.key]?.raw ?? "";
        const raw = pendingProfileValue(item.index, field.key, originalRaw);
        if (raw) fields[field.key] = raw;
      });
      return fields;
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
        <option value="${esc(field.key)}"${field.key === selectedField ? " selected" : ""}>${esc(profileFieldLabel(field.key))}</option>
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
        name: `${draft.targetLabel} override`,
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
      markProfilePanelsDirty("profiles", "rules");
      renderActiveProfilePanel(true);
      updateGlobalEditStatus();
    }

    function removeProfileOverrideDraft(id) {
      profileOverrideEdits = profileOverrideEdits.filter(edit => edit.id !== id);
      markProfilePanelsDirty("profiles", "rules");
      renderActiveProfilePanel(true);
      renderDetailHead();
      updateGlobalEditStatus();
    }

    function toggleProfileOverrideRemoval(orderOrOrders) {
      const orders = profileOverrideOrders(orderOrOrders);
      if (!orders.length) return;
      if (orders.every(order => profileOverrideRemoveEdits.has(order))) {
        orders.forEach(order => profileOverrideRemoveEdits.delete(order));
      } else {
        orders.forEach(order => profileOverrideRemoveEdits.add(order));
      }
      markProfilePanelsDirty("profiles", "rules");
      renderActiveProfilePanel(true);
      renderDetailHead();
      updateGlobalEditStatus();
    }

    function profileOverrideChangeCount() {
      return profileOverrideProfileEdits.size + profileOverrideNameEdits.size + profileOverrideEdits.length + profileOverrideRemoveEdits.size;
    }

    function profileOverrideNameChangePayload() {
      const rename = {};
      profileOverrideNameEdits.forEach((name, order) => {
        rename[order] = name;
      });
      return rename;
    }

    function profileOverrideChangePayload() {
      return {
        add: profileOverrideEdits.map(edit => {
          const fields = edit.fields || (edit.field ? { [edit.field]: edit.raw } : {});
          const matches = edit.matches || [edit.match].filter(Boolean);
          return { match: matches[0] || null, matches, fields, name: edit.name || edit.targetName || "" };
        }),
        edit: profileOverrideProfileChangePayload(),
        rename: profileOverrideNameChangePayload(),
        remove: Array.from(profileOverrideRemoveEdits).map(order => Number(order)),
      };
    }

    function profileOverridePendingFieldSummary(edit) {
      if (edit.fields) {
        const count = Object.values(edit.fields).filter(Boolean).length;
        return count ? `${count} field${count === 1 ? "" : "s"}` : "empty layer";
      }
      return edit.fieldLabel ? `${edit.fieldLabel}: ${edit.valueLabel}` : "empty layer";
    }

    function profileOverridePendingHtml() {
      if (!profileOverrideEdits.length) return "";
      return `
        <div class="behavior-override-pending">
          ${profileOverrideEdits.map(edit => `
            <div class="behavior-override-pending-row">
              <div>
                ${encounterBadge("target", "type-placement", "Pending override")}
                <span>${esc(edit.name || edit.targetName || edit.typeName)} -> ${esc(profileOverridePendingFieldSummary(edit))}</span>
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
      const fields = behaviorOverrideMaskLabels(rule.behavior);
      return `
        <div class="rule behavior-override-rule ${removing ? "pending-remove" : ""}">
          <div>
            <div class="rule-top"><span>#${esc(rule.order)} ${esc(rule.summary)}</span><span>${esc(fields.join(", "))}</span></div>
            <div class="muted">${esc(rule.behavior.maskRaw || rule.behavior.mask.raw)}${removing ? " · pending removal" : ""}</div>
          </div>
          <button class="control subtle-action behavior-override-remove" type="button" data-action="toggle-remove-profile-override" data-override-order="${esc(rule.order)}" title="${removing ? "Undo override removal" : "Remove override"}" aria-label="${removing ? "Undo removing override" : "Remove override"} #${esc(rule.order)}">
            ${interfaceIcon(removing ? "plus" : "minus")}
          </button>
        </div>
      `;
    }

    function profileOverrideProfileRuleHtml(item) {
      const removing = profileOverrideIsRemoving(item);
      const fields = behaviorOverrideMaskLabels(item.override);
      const name = profileDisplayName(item);
      return `
        <div class="rule behavior-override-rule ${removing ? "pending-remove" : ""}">
          <button class="rule-main-button" type="button" data-action="select-override-profile" data-class-index="${esc(item.index)}">
            <div class="rule-top"><span>${esc(name)}</span><span>${esc(fields.join(", ") || "No fields")}</span></div>
            <div class="muted">${esc(item.summary || "Override profile")}${removing ? " · pending removal" : ""}</div>
          </button>
          <button class="control subtle-action behavior-override-remove" type="button" data-action="toggle-remove-profile-override" data-override-orders="${esc(profileOverrideOrders(item).join(","))}" title="${removing ? "Undo override removal" : "Remove override profile"}" aria-label="${removing ? "Undo removing override profile" : "Remove override profile"} #${esc(item.order)}">
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

    function uniqueProfileAssignments(assignments) {
      const seen = new Set();
      const result = [];
      (assignments || []).forEach(assignment => {
        const symbol = assignment?.species?.symbol;
        if (!symbol || seen.has(symbol)) return;
        seen.add(symbol);
        result.push(assignment);
      });
      return result;
    }

    function profilePendingOverrideAssignments(profile) {
      if (!isOverrideProfile(profile)) return [];
      const names = new Set([
        profileDisplayName(profile),
        profile.name,
        profile.customName,
      ].filter(Boolean));
      return profileOverrideEdits
        .filter(edit => names.has(edit.name || edit.targetName || ""))
        .flatMap(edit => profileSpeciesForPendingOverrideEdit(edit))
        .map(species => assignmentsBySymbol.get(species.symbol) || { species });
    }

    function profileAssignmentsForClass(classIndex) {
      const profile = profileClassByIndex(classIndex);
      if (isOverrideProfile(profile)) {
        const savedAssignments = appData.assignments.filter(item =>
          profileOverrideHitOrdersForAssignment(item, profile)
            .some(order => !profileOverrideRemoveEdits.has(order))
        );
        return uniqueProfileAssignments([
          ...savedAssignments,
          ...profilePendingOverrideAssignments(profile),
        ]);
      }
      return appData.assignments.filter(item =>
        String(profilePendingClassValueForSymbol(item.species.symbol)) === String(classIndex)
      );
    }

    function profileSavedBaseAssignmentsForClass(classIndex) {
      return appData.assignments.filter(item =>
        String(item.behaviorClass?.value) === String(classIndex)
      );
    }

    function profileClassSearchText(item, assignments) {
      const primitiveText = Object.values(item.primitives || {})
        .map(value => `${value.label || ""} ${value.raw || ""}`)
        .join(" ");
      return [
        profileDisplayName(item),
        item.symbol,
        item.summary || "",
        profilePendingDisplay(item, "profileId"),
        profilePendingDisplay(item, "spawnState"),
        appData.fields.map(field => `${profileFieldLabel(field.key)} ${fieldValue(item.profile[field.key])}`).join(" "),
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
      profileFamilyMembersByBaseSymbol = new Map();
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
        profileOverrideProfileEdits.clear();
        profileOverrideNameEdits.clear();
        profileOverrideEdits = [];
        profileOverrideRemoveEdits.clear();
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
      appData.speciesOptions.forEach(species => {
        if (!species || species.symbol === "SPECIES_NONE") return;
        const familyBase = species.familyBaseSymbol || species.baseSymbol || species.symbol;
        if (!profileFamilyMembersByBaseSymbol.has(familyBase)) {
          profileFamilyMembersByBaseSymbol.set(familyBase, []);
        }
        const members = profileFamilyMembersByBaseSymbol.get(familyBase);
        if (!members.some(member => member.symbol === species.symbol)) {
          members.push(species);
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
        `<option value="${esc(item.index)}">${esc(profileDisplayName(item))} (${esc(item.speciesCount)}${isOverrideProfile(item) ? " affected" : ""})</option>`
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
        const name = profileDisplayName(item);
        return `
        <div class="profile-row ${isOverrideProfile(item) ? "override-profile" : ""} ${active ? "active" : ""} ${profileClassChanged(item) ? "changed" : ""}" role="button" tabindex="0" data-class-index="${esc(item.index)}">
          ${profileClassBadge(item)}
          ${profileOverrideOrderControls(item)}
          <span class="profile-row-main">
            <span class="profile-row-title" title="${esc(profileComboRawDisplay(item.symbol))}">${esc(name)}</span>
            <span class="profile-row-sub">${isOverrideProfile(item) ? esc(item.summary || "Override profile") : `${esc(profilePendingDisplay(item, "profileId"))} · ${esc(profilePendingDisplay(item, "spawnState"))}`}</span>
          </span>
          <span class="profile-row-count">${esc(assigned.length)} ${isOverrideProfile(item) ? "affected" : "Pokemon"}</span>
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
          ${routeOverrideControl(route, true)}
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

    function routeOverrideTargets(route) {
      const targets = [];
      const addTarget = (path, formPath, species, form, encounterable = true) => {
        if (!path || !formPath || !encounterable || species?.symbol === "SPECIES_NONE") return;
        targets.push({
          path,
          formPath,
          originalSymbol: species.symbol,
          originalForm: form ?? 0,
        });
      };

      route.pokemonTables.forEach(table => {
        table.slots.forEach((slot, index) => {
          const level = ["morning", "day", "night"].includes(table.key) ? route.grassLevels[index] : null;
          const levelValue = level ? Number(routePendingValue(route.id, level.path, level.value)) : 1;
          addTarget(slot.path, slot.formPath, slot.species, slot.form, levelValue !== 0);
        });
      });
      route.slotTables.forEach(table => {
        table.slots.forEach(slot => {
          const minLevel = Number(routePendingValue(route.id, slot.paths.minLevel, slot.minLevel));
          addTarget(slot.paths.species, slot.paths.form, slot.species, slot.form, minLevel !== 0);
        });
      });
      (route.headbuttTables || []).forEach(table => {
        table.slots.forEach(slot => {
          const minLevel = Number(routePendingValue(route.id, slot.paths.minLevel, slot.minLevel));
          addTarget(slot.paths.species, slot.paths.form, slot.species, slot.form, minLevel !== 0);
        });
      });
      route.swarms.forEach(swarm => {
        addTarget(swarm.path, swarm.formPath, swarm.species, swarm.form);
      });
      return targets;
    }

    function savedRouteOverride(route) {
      return route?.encounterOverride || null;
    }

    function pendingRouteOverride(routeId) {
      return routeOverrideEdits.get(String(routeId)) || null;
    }

    function routeOverrideState(route) {
      const pending = pendingRouteOverride(route.id);
      if (pending?.action === "clear") return null;
      if (pending?.action === "set") return pending;
      return savedRouteOverride(route);
    }

    function routeOverrideBaselineEntries(route, targets = routeOverrideTargets(route)) {
      const pending = pendingRouteOverride(route.id);
      if (pending?.action === "set" && Array.isArray(pending.entries) && pending.entries.length) {
        return pending.entries;
      }
      const saved = savedRouteOverride(route);
      if (saved?.entries?.length) {
        return saved.entries;
      }
      return targets.map(target => ({
        path: target.path,
        formPath: target.formPath,
        species: target.originalSymbol,
        form: String(target.originalForm ?? 0),
      }));
    }

    function routeOverrideSpecies(route) {
      const state = routeOverrideState(route);
      return state ? routeDisplaySpecies(state.species, state.form || 0) : null;
    }

    function routeOverrideIconTag(species) {
      if (!species || species.symbol === "SPECIES_NONE") {
        return `<span class="mon-icon route-override-empty-icon" data-symbol="SPECIES_NONE" aria-hidden="true">${interfaceIcon("plus")}</span>`;
      }
      return iconTag(species, "mon-icon");
    }

    function routeOverrideControl(route, compact = false) {
      const targets = routeOverrideTargets(route);
      const state = routeOverrideState(route);
      const pending = pendingRouteOverride(route.id);
      const option = routeOverrideSpecies(route);
      const enabled = Boolean(state);
      const changed = Boolean(pending);
      const iconSpecies = option || speciesBySymbol("SPECIES_NONE");
      const layoutClass = compact ? "route-encounter-group" : "route-field route-rate-chip";
      const title = enabled
        ? `Only ${option?.name || routeSpeciesShortSymbol(state.species)} can encounter on ${route.name}`
        : `Set one Pokemon as the only encounter on ${route.name}`;
      return `
        <span class="${layoutClass} route-override-control ${compact ? "compact" : ""} ${enabled ? "enabled" : ""} ${changed ? "changed" : ""}" data-route-override-control="1" data-route-id="${esc(route.id)}" title="${esc(title)}" aria-label="${esc(title)}">
          <span class="route-encounter-icons">
            ${encounterBadge("target", "type-override", "Route override")}
            <span class="route-encounter-text">Route override</span>
          </span>
          <span class="route-encounter-mon-icons route-override-mon-icons">
            <span class="route-override-species-wrap">
              ${routeOverrideIconTag(iconSpecies)}
            </span>
          </span>
        </span>
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
              ${routeOverrideControl(route)}
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
        const [classIndex, fieldKey] = key.split("|");
        if (!changes[classIndex]) changes[classIndex] = {};
        changes[classIndex][fieldKey] = raw;
      });
      return changes;
    }

    function profileOverrideProfileChangePayload() {
      const edit = {};
      profileOverrideProfileEdits.forEach((raw, key) => {
        const [profileKey, fieldKey] = key.split("|");
        const profile = profileClassByIndex(profileKey);
        const orders = profileOverrideOrders(profile).length
          ? profileOverrideOrders(profile)
          : [String(profileKey || "").replace(/^override:/, "")].filter(Boolean);
        orders.forEach(order => {
          if (!edit[order]) edit[order] = {};
          edit[order][fieldKey] = raw;
        });
      });
      return edit;
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
          || PROFILE_SCOPED_SPECIAL_ACTION_FIELDS.has(fieldKey)
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

    function profileControlOriginalCompareValue(input) {
      return input.classList.contains("profile-number")
        ? (input.dataset.originalValue ?? input.dataset.original ?? "")
        : (input.dataset.original ?? "");
    }

    function profileControlDisplayValue(input, raw) {
      if (input.classList.contains("profile-number")) {
        const item = profileClassByIndex(input.dataset.classIndex);
        return item ? profileNumberInputValue(item, input.dataset.field, raw) : String(raw ?? "");
      }
      return profileComboDisplay(input.dataset.field, raw);
    }

    function profileAttributeSelectorValue(value) {
      return String(value ?? "").replace(/\\/g, "\\\\").replace(/"/g, "\\\"");
    }

    function updateProfileControlVisualState(input, raw) {
      const field = input.closest(".field");
      if (!field) return;
      const compareRaw = profileControlOriginalCompareValue(input);
      field.classList.toggle("changed", String(raw ?? "") !== compareRaw);
      field.classList.toggle("inherited", isOverrideProfileIndex(input.dataset.classIndex) && !raw);
      field.classList.toggle("overridden", isOverrideProfileIndex(input.dataset.classIndex) && !!raw);
    }

    function syncDuplicateProfileControls(sourceInput, raw) {
      if (!sourceInput?.dataset?.classIndex || !sourceInput?.dataset?.field) return;
      const classIndex = profileAttributeSelectorValue(sourceInput.dataset.classIndex);
      const fieldKey = profileAttributeSelectorValue(sourceInput.dataset.field);
      const selector = `.profile-combo[data-class-index="${classIndex}"][data-field="${fieldKey}"], .profile-number[data-class-index="${classIndex}"][data-field="${fieldKey}"]`;
      els.profilesTab.querySelectorAll(selector).forEach(input => {
        if (input !== sourceInput) {
          input.value = profileControlDisplayValue(input, raw);
        }
        trackInvalidInput(invalidProfileInputs, input, false);
        updateProfileControlVisualState(input, raw);
      });
    }

    function setProfileEdit(classIndex, fieldKey, raw, originalRaw) {
      const key = editKey(classIndex, fieldKey);
      const edits = isOverrideProfileIndex(classIndex) ? profileOverrideProfileEdits : profileEdits;
      if (raw === originalRaw) {
        edits.delete(key);
      } else {
        edits.set(key, raw);
      }
    }

    function profileScopedSpecialActionOtherField(fieldKey) {
      return fieldKey === ALERT_ACTION_SPECIAL_FIELD ? ACTIVE_ACTION_SPECIAL_FIELD : ALERT_ACTION_SPECIAL_FIELD;
    }

    function profileScopedSpecialActionClearRaw(fieldKey, currentRaw, originalRaw) {
      if (currentRaw === ALERT_SPECIAL_NONE_RAW) {
        return "";
      }
      if (!scopedSpecialActionOwnsRaw(fieldKey, currentRaw)) {
        return currentRaw;
      }
      const otherField = profileScopedSpecialActionOtherField(fieldKey);
      if (scopedSpecialActionOwnsRaw(otherField, originalRaw)
          && !scopedSpecialActionOwnsRaw(fieldKey, originalRaw)) {
        return originalRaw;
      }
      return "";
    }

    function clearProfileFieldToInherit(item, classIndex, fieldKey) {
      if (PROFILE_SCOPED_SPECIAL_ACTION_FIELDS.has(fieldKey)) {
        const sourceField = "alertSpecialAction";
        const originalRaw = item.profile[sourceField]?.raw ?? "";
        const currentRaw = pendingProfileValue(classIndex, sourceField, originalRaw);
        const raw = profileScopedSpecialActionClearRaw(fieldKey, currentRaw, originalRaw);
        setProfileEdit(classIndex, sourceField, raw, originalRaw);
        return;
      }
      const storedField = profileStoredFieldKey(fieldKey);
      setProfileEdit(classIndex, storedField, "", item.profile[storedField]?.raw ?? "");
    }

    function clearProfileSectionToInherit(button) {
      const classIndex = button.dataset.classIndex || "";
      if (!isOverrideProfileIndex(classIndex)) return;
      const item = (appData.classes || []).find(row => String(row.index) === String(classIndex));
      if (!item) return;
      const fields = Array.from(new Set(String(button.dataset.fields || "")
        .split(",")
        .map(field => field.trim())
        .filter(Boolean)));
      if (!fields.length) return;
      const section = button.closest(".profile-architecture-group");
      if (section) {
        section.querySelectorAll(".profile-combo, .profile-number").forEach(input => {
          trackInvalidInput(invalidProfileInputs, input, false);
        });
      }
      fields.forEach(fieldKey => {
        clearProfileFieldToInherit(item, classIndex, fieldKey);
      });
      closeProfileComboMenu();
      button.blur();
      markProfilePanelsDirty("profiles", "selected", "rules");
      renderActiveProfilePanel(true);
      updateProfileComboStatus({ dataset: { classIndex } }, true);
    }

    function commitInheritedProfileBlank(input, sourceField = null, sourceOriginal = null) {
      if (!isOverrideProfileIndex(input.dataset.classIndex) || String(input.value || "").trim() !== "") {
        return false;
      }
      const field = input.closest(".field");
      const targetField = sourceField || input.dataset.field;
      const originalRaw = sourceOriginal ?? input.dataset.original ?? "";
      trackInvalidInput(invalidProfileInputs, input, false);
      setProfileEdit(input.dataset.classIndex, targetField, "", originalRaw);
      syncDuplicateProfileControls(input, "");
      if (field) {
        field.classList.add("inherited");
        field.classList.remove("overridden");
        field.classList.toggle("changed", originalRaw !== "");
      }
      return true;
    }

    function commitAlertRangeTypeCombo(input, normalize = false, forcedOption = null) {
      if (!forcedOption && commitInheritedProfileBlank(input, "alertRange", input.dataset.original)) {
        if (normalize) input.value = "";
        return true;
      }
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
      field.classList.remove("inherited");
      field.classList.toggle("changed", raw !== input.dataset.original);
      field.classList.toggle("overridden", isOverrideProfileIndex(input.dataset.classIndex) && raw !== "");
      return true;
    }

    function commitSpawnDestinationTypeCombo(input, normalize = false, forcedOption = null) {
      if (!forcedOption && commitInheritedProfileBlank(input, "spawnDestination", input.dataset.original)) {
        if (normalize) input.value = "";
        return true;
      }
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
      field.classList.remove("inherited");
      field.classList.toggle("changed", raw !== input.dataset.original);
      field.classList.toggle("overridden", isOverrideProfileIndex(input.dataset.classIndex) && raw !== "");
      return true;
    }

    function commitScopedSpecialActionBlank(input, normalize = false) {
      if (!isOverrideProfileIndex(input.dataset.classIndex) || String(input.value || "").trim() !== "") {
        return false;
      }
      const sourceField = input.dataset.sourceField || "alertSpecialAction";
      const sourceOriginal = input.dataset.sourceOriginal || "";
      const currentSourceRaw = pendingProfileValue(input.dataset.classIndex, sourceField, sourceOriginal);
      const raw = profileScopedSpecialActionClearRaw(input.dataset.field, currentSourceRaw, sourceOriginal);
      const field = input.closest(".field");
      trackInvalidInput(invalidProfileInputs, input, false);
      setProfileEdit(input.dataset.classIndex, sourceField, raw, sourceOriginal);
      if (normalize) input.value = "";
      if (field) {
        const scopedRaw = scopedSpecialActionCountRaw(input.dataset.field, raw);
        const originalScopedRaw = scopedSpecialActionCountRaw(input.dataset.field, sourceOriginal);
        field.classList.toggle("inherited", !scopedRaw);
        field.classList.toggle("changed", scopedRaw !== originalScopedRaw);
        field.classList.toggle("overridden", !!scopedRaw);
      }
      return true;
    }

    function commitScopedSpecialActionCombo(input, normalize = false, forcedOption = null) {
      if (!forcedOption && commitScopedSpecialActionBlank(input, normalize)) {
        return true;
      }
      const option = forcedOption || profileOptionForInput(input.dataset.field, input.value, input.dataset.original);
      const field = input.closest(".field");
      if (!option) {
        trackInvalidInput(invalidProfileInputs, input, true);
        field.classList.remove("changed");
        return false;
      }
      const sourceField = input.dataset.sourceField || "alertSpecialAction";
      const sourceOriginal = input.dataset.sourceOriginal || ALERT_SPECIAL_NONE_RAW;
      const currentSourceRaw = pendingProfileValue(input.dataset.classIndex, sourceField, sourceOriginal);
      let raw = option.raw;
      let preservingOtherScope = false;
      if (raw === ALERT_SPECIAL_NONE_RAW
          && scopedSpecialActionRaw(input.dataset.field, currentSourceRaw) === ALERT_SPECIAL_NONE_RAW) {
        raw = currentSourceRaw;
        preservingOtherScope = isOverrideProfileIndex(input.dataset.classIndex)
          && !scopedSpecialActionOwnsRaw(input.dataset.field, currentSourceRaw);
      }
      if (normalize) {
        input.value = preservingOtherScope ? "" : profileComboDisplay(input.dataset.field, option.raw);
      }
      trackInvalidInput(invalidProfileInputs, input, false);
      setProfileEdit(input.dataset.classIndex, sourceField, raw, sourceOriginal);
      const scopedRaw = scopedSpecialActionCountRaw(input.dataset.field, raw);
      const originalScopedRaw = scopedSpecialActionCountRaw(input.dataset.field, sourceOriginal);
      field.classList.toggle("inherited", isOverrideProfileIndex(input.dataset.classIndex) && !scopedRaw);
      field.classList.toggle("changed", scopedRaw !== originalScopedRaw);
      field.classList.toggle("overridden", isOverrideProfileIndex(input.dataset.classIndex) && !!scopedRaw);
      return true;
    }

    function commitProfileCombo(input, normalize = false, forcedOption = null) {
      if (input.dataset.field === ALERT_RANGE_TYPE_FIELD) {
        return commitAlertRangeTypeCombo(input, normalize, forcedOption);
      }
      if (input.dataset.field === SPAWN_DESTINATION_TYPE_FIELD) {
        return commitSpawnDestinationTypeCombo(input, normalize, forcedOption);
      }
      if (PROFILE_SCOPED_SPECIAL_ACTION_FIELDS.has(input.dataset.field)) {
        return commitScopedSpecialActionCombo(input, normalize, forcedOption);
      }
      if (!forcedOption && commitInheritedProfileBlank(input)) {
        if (normalize) input.value = "";
        return true;
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
      syncDuplicateProfileControls(input, option.raw);
      field.classList.remove("inherited");
      field.classList.toggle("changed", option.raw !== input.dataset.original);
      field.classList.toggle("overridden", isOverrideProfileIndex(input.dataset.classIndex) && option.raw !== "");
      return true;
    }

    function commitProfileNumber(input, normalize = false) {
      if (commitInheritedProfileBlank(input)) {
        if (normalize) input.value = "";
        return true;
      }
      const fieldKey = input.dataset.field;
      const limits = {
        min: Number(input.dataset.min ?? PROFILE_NUMBER_FIELD_LIMITS[fieldKey]?.min ?? 0),
        max: Number(input.dataset.max ?? PROFILE_NUMBER_FIELD_LIMITS[fieldKey]?.max ?? 255),
      };
      const field = input.closest(".field");
      const text = String(input.value ?? "").trim();
      const value = Number(text);
      if (!text || !Number.isInteger(value) || value < limits.min || value > limits.max) {
        trackInvalidInput(invalidProfileInputs, input, true);
        if (field) field.classList.remove("changed");
        return false;
      }
      const raw = String(value);
      if (normalize) {
        input.value = raw;
      }
      trackInvalidInput(invalidProfileInputs, input, false);
      const key = editKey(input.dataset.classIndex, fieldKey);
      const edits = isOverrideProfileIndex(input.dataset.classIndex) ? profileOverrideProfileEdits : profileEdits;
      const originalValue = input.dataset.originalValue ?? input.dataset.original ?? "";
      if (raw === originalValue) {
        edits.delete(key);
      } else {
        edits.set(key, raw);
      }
      syncDuplicateProfileControls(input, raw);
      if (field) {
        field.classList.remove("inherited");
        field.classList.toggle("changed", raw !== originalValue);
        field.classList.toggle("overridden", isOverrideProfileIndex(input.dataset.classIndex) && raw !== "");
      }
      return true;
    }

    function commitAllProfileCombos(normalize = false) {
      const combosValid = Array.from(els.profilesTab.querySelectorAll(".profile-combo"))
        .map(input => commitProfileCombo(input, normalize))
        .every(Boolean);
      const numbersValid = Array.from(els.profilesTab.querySelectorAll(".profile-number"))
        .map(input => commitProfileNumber(input, normalize))
        .every(Boolean);
      return combosValid && numbersValid;
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
      } else if (text.includes("saving") || text.includes("building") || text.includes("opening") || text.includes("restarting")) {
        els.saveStatus.classList.add("status-busy");
      } else if (text.includes("pending")) {
        els.saveStatus.classList.add("status-warning");
      } else if (text.includes("saved") || text.includes("succeeded") || text.includes("opened")) {
        els.saveStatus.classList.add("status-success");
      }
    }

    function updateSaveControls() {
      const busy = isSavingProfiles || isSavingProfileMemberships || isSavingProfileOverrides || isSavingEncounters || isSavingSpawnSettings || isManagingProfiles || isBuilding || isRestartingServer || isSettingShinyCounter;
      const profilesEditable = appData?.profilesAvailable !== false;
      const hasProfileChanges = profilesEditable && (profileEdits.size > 0 || profileMemberEdits.size > 0 || profileOverrideChangeCount() > 0);
      const hasChanges = hasProfileChanges || encounterEdits.size > 0 || routeOverrideEdits.size > 0 || spawnSettingEdits.size > 0;
      const hasInvalid = (profilesEditable && invalidProfileComboCount() > 0) || invalidEncounterInputCount() > 0 || invalidSpawnSettingInputCount() > 0;
      els.saveAllChanges.disabled = busy || !hasChanges || hasInvalid;
      els.buildRom.disabled = busy;
      els.openTestNds.disabled = busy;
      els.restartServer.disabled = busy;
      els.resetAllEdits.disabled = busy || (!hasChanges && !hasInvalid);
      els.refreshShinyCounter.disabled = isSettingShinyCounter;
      els.resetShinyCounter.disabled = isSettingShinyCounter;
      els.maxShinyCounter.disabled = isSettingShinyCounter;
    }

    function reservedShinySpecies(value) {
      return appData?.speciesByValue?.[String(value)]
        || appData?.speciesByValue?.[Number(value)]
        || { value, symbol: `SPECIES_${value}`, name: `Species ${value}` };
    }

    function reservedShinyRouteInfo(mapId) {
      if (!appData?.routes) return { label: `Map ${mapId}`, route: null, map: null };
      const route = appData.routes.find(candidate =>
        Array.isArray(candidate.maps)
          && candidate.maps.some(map => Number(map.value) === Number(mapId))
      );
      if (!route) return { label: `Map ${mapId}`, route: null, map: null };
      const map = route.maps.find(entry => Number(entry.value) === Number(mapId));
      return {
        label: map?.name ? `${route.name} / ${map.name}` : route.name,
        route,
        map
      };
    }

    function reservedShinyRouteName(mapId) {
      return reservedShinyRouteInfo(mapId).label;
    }

    function reservedShinyTerrainInfo(value) {
      const terrain = appData?.labels?.terrains?.[String(value)]
        || appData?.labels?.terrains?.[Number(value)];
      const symbol = terrain?.symbol || "";
      if (symbol.includes("LAND")) return { icon: "leaf", typeClass: "type-grass", sourceClass: "grass", symbol, label: terrain?.name || "Land" };
      if (symbol.includes("SURF")) return { icon: "waves", typeClass: "type-surf", sourceClass: "surf", symbol, label: terrain?.name || "Surf" };
      if (symbol.includes("FISHING")) return { icon: "fish", typeClass: "type-rod", sourceClass: "fishing", symbol, label: terrain?.name || "Fishing" };
      if (symbol.includes("HEADBUTT")) return { icon: "tree", typeClass: "type-headbutt", sourceClass: "headbutt", symbol, label: terrain?.name || "Headbutt" };
      return { icon: "swarm", typeClass: "type-shiny", sourceClass: "shiny", symbol, label: terrain?.name || `Terrain ${value}` };
    }

    function reservedShinyDetailEntry(iconHtml, sourceClass, title, subtitle, valueHtml) {
      return `
        <div class="reserved-shiny-entry source-${esc(sourceClass || "shiny")}">
          <span class="reserved-shiny-entry-source">${iconHtml}</span>
          <span class="reserved-shiny-entry-meta">
            <strong>${esc(title)}</strong>
            <span>${esc(subtitle)}</span>
          </span>
          <span class="reserved-shiny-entry-value">${valueHtml}</span>
        </div>
      `;
    }

    function reservedShinyDetailIcon(icon, typeClass, label) {
      return encounterBadge(icon, typeClass, label);
    }

    function closeReservedShinyDetail() {
      if (!els.reservedShinyDialog) return;
      if (els.reservedShinyDialog.open) {
        els.reservedShinyDialog.close();
      }
      els.reservedShinyDialog.innerHTML = "";
    }

    function openReservedShinyDetail(slot) {
      if (!els.reservedShinyDialog) return;
      const entries = lastShinyCounterPayload?.reservedShinies || [];
      const entry = entries.find(candidate => String(candidate.slot) === String(slot));
      if (!entry) return;
      const species = reservedShinySpecies(entry.species);
      const terrain = reservedShinyTerrainInfo(entry.terrain);
      const routeInfo = reservedShinyRouteInfo(entry.mapId);
      const name = routeSpeciesShortSymbol(species.symbol || species.name || `SPECIES_${entry.species}`);
      const displayName = species.name || name;
      const formText = Number(entry.form) ? `Form ${entry.form}` : "Base form";
      const mapLabel = routeInfo.map?.name || routeInfo.label;
      const routeLabel = routeInfo.route?.name || routeInfo.label;
      const locationSubtitle = mapLabel === routeLabel
        ? `Map ${entry.mapId}`
        : `${mapLabel} · Map ${entry.mapId}`;
      const denominator = Number(lastShinyCounterPayload?.denominator) || 8192;
      const terrainIcon = reservedShinyDetailIcon(terrain.icon, terrain.typeClass, terrain.label);
      const shinyIcon = reservedShinyDetailIcon("swarm", "type-shiny", "Pity shiny");
      const speciesIcon = iconTag(species, "mon-icon");
      const rows = [
        reservedShinyDetailEntry(
          shinyIcon,
          "shiny",
          "Reservation",
          "Pity shiny queue slot",
          `#${esc(entry.slot)}`
        ),
        reservedShinyDetailEntry(
          speciesIcon,
          terrain.sourceClass,
          displayName,
          `Species #${entry.species} · ${formText}`,
          `Lv ${esc(entry.level)}`
        ),
        reservedShinyDetailEntry(
          terrainIcon,
          terrain.sourceClass,
          routeLabel,
          locationSubtitle,
          esc(terrain.label)
        ),
        reservedShinyDetailEntry(
          terrainIcon,
          terrain.sourceClass,
          "Spawn pool",
          `Terrain #${entry.terrain}`,
          esc(terrain.label)
        ),
        reservedShinyDetailEntry(
          shinyIcon,
          "shiny",
          "Current pity odds",
          "Normal shiny roll stays 1/8192",
          `1/${esc(denominator)}`
        )
      ].join("");
      els.reservedShinyDialog.innerHTML = `
        <form class="reserved-shiny-card" method="dialog">
          <div class="reserved-shiny-head">
            ${speciesIcon}
            <div class="reserved-shiny-title">
              <strong>Reserved ${esc(name)}</strong>
              <span>${esc(routeInfo.label)} · ${esc(terrain.label)} · Lv ${esc(entry.level)}</span>
            </div>
          </div>
          <div class="reserved-shiny-entries">${rows}</div>
          <div class="reserved-shiny-help">
            This pity reservation is consumed by the next matching overworld spawn. The queue resets when a reserved shiny is spawned.
          </div>
          <div class="reserved-shiny-actions">
            <button class="control" type="button" data-reserved-shiny-action="close">Close</button>
          </div>
        </form>
      `;
      els.reservedShinyDialog.showModal();
    }

    function renderReservedShinies(payload) {
      if (!els.reservedShinyList) return;
      const entries = payload?.reservedShinies || [];
      if (!payload?.exists) {
        els.reservedShinyList.innerHTML = "";
        return;
      }
      if (!entries.length) {
        els.reservedShinyList.innerHTML = `<span class="reserved-shiny-empty">No reserved</span>`;
        return;
      }
      els.reservedShinyList.innerHTML = entries.map(entry => {
        const species = reservedShinySpecies(entry.species);
        const terrain = reservedShinyTerrainInfo(entry.terrain);
        const name = routeSpeciesShortSymbol(species.symbol || species.name || `SPECIES_${entry.species}`);
        const routeName = reservedShinyRouteName(entry.mapId);
        const title = `Reserved pity shiny #${entry.slot}: ${species.name || name}, Lv ${entry.level}, ${terrain.label}, ${routeName}`;
        return `
          <button class="reserved-shiny-chip" type="button" data-reserved-shiny-slot="${esc(entry.slot)}" title="${esc(title)}">
            ${encounterBadge(terrain.icon, terrain.typeClass, terrain.label)}
            ${iconTag(species, "mon-icon")}
            <span class="reserved-shiny-name">${esc(name)}</span>
            <span class="reserved-shiny-level">Lv ${esc(entry.level)}</span>
          </button>
        `;
      }).join("");
    }

    function applyShinyCounterStatus(payload) {
      lastShinyCounterPayload = payload || null;
      if (!payload || !payload.exists) {
        els.shinyCounterValue.textContent = "--";
        els.shinyCounterRate.textContent = "No save";
        renderReservedShinies(payload);
        return;
      }
      const counter = Number(payload.counter) || 0;
      const denominator = Number(payload.denominator) || 8192;
      els.shinyCounterValue.textContent = String(counter);
      els.shinyCounterRate.textContent = `pity 1/${denominator}`;
      const suffix = payload.magicOk ? "" : (payload.legacyMagic ? " (legacy format)" : " (not initialized)");
      els.shinyCounterValue.title = `Saved shiny spawn counter${suffix}`;
      els.shinyCounterRate.title = `Pity shiny roll: 1 in ${denominator}. Normal shiny roll remains 1 in 8192${suffix}`;
      renderReservedShinies(payload);
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
            ? `Shiny counter: ${result.counter} (pity 1/${result.denominator})`
            : "No test.dsv found";
          setSaveStatus(text, result.exists ? "success" : "warning");
        }
        return result;
      } catch (error) {
        lastShinyCounterPayload = null;
        els.shinyCounterValue.textContent = "--";
        els.shinyCounterRate.textContent = "Load failed";
        renderReservedShinies({ exists: false });
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
        setSaveStatus(`${result.message || "Shiny counter updated"} (pity 1/${result.denominator})`, "success");
      } catch (error) {
        setSaveStatus(`Shiny counter failed: ${error.message}`, "error");
      } finally {
        isSettingShinyCounter = false;
        updateSaveControls();
      }
    }

    async function saveProfileChanges(options = {}) {
      if (isSavingProfiles) return false;
      if (!commitAllProfileCombos(true)) {
        updateSaveControls();
        setSaveStatus(`${invalidProfileComboCount()} invalid value${invalidProfileComboCount() === 1 ? "" : "s"}`);
        return false;
      }
      if (!profileEdits.size) return true;
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
      if (!commitAllProfileCombos(true)) {
        updateSaveControls();
        setSaveStatus(`${invalidProfileComboCount()} invalid value${invalidProfileComboCount() === 1 ? "" : "s"}`);
        return false;
      }
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
        profileOverrideProfileEdits.clear();
        profileOverrideNameEdits.clear();
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

    async function saveProfileOverrideReorder(orderGroups, selectedName = "") {
      if (isSavingProfileOverrides) return false;
      isSavingProfileOverrides = true;
      updateSaveControls();
      setSaveStatus("Reordering override profiles...", "busy");
      try {
        const response = await fetch("/save-profile-overrides", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ changes: { reorder: orderGroups } })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || `HTTP ${response.status}`);
        }
        profileOverrideProfileEdits.clear();
        profileOverrideNameEdits.clear();
        profileOverrideEdits = [];
        profileOverrideRemoveEdits.clear();
        await loadData({ keepStatus: true });
        const selectedProfile = selectedName
          ? (appData.classes || []).find(item => isOverrideProfile(item) && profileDisplayName(item) === selectedName)
          : null;
        if (selectedProfile) {
          selectProfileClass(selectedProfile.index, { tab: "profiles" });
        }
        setSaveStatus(result.message || "Saved", "success");
        return true;
      } catch (error) {
        setSaveStatus(`Reorder failed: ${error.message}`, "error");
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
      if (/docker: command not found/i.test(output)) {
        return "Docker CLI was not found in the build environment";
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

    function sleep(ms) {
      return new Promise(resolve => setTimeout(resolve, ms));
    }

    async function waitForServerReady(timeoutMs = 15000) {
      const started = Date.now();
      while (Date.now() - started < timeoutMs) {
        try {
          const response = await fetch(`/build-status?restartProbe=${Date.now()}`, { cache: "no-store" });
          if (response.ok) return true;
        } catch (error) {
          void error;
        }
        await sleep(350);
      }
      return false;
    }

    async function restartServerAction() {
      if (isRestartingServer) return;
      isRestartingServer = true;
      updateSaveControls();
      setSaveStatus("Restarting server...", "busy");
      try {
        const response = await fetch("/restart-server", { method: "POST" });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || `HTTP ${response.status}`);
        }
        await sleep(650);
        const ready = await waitForServerReady();
        if (!ready) {
          throw new Error("server did not come back in time");
        }
        window.location.reload();
      } catch (error) {
        isRestartingServer = false;
        setSaveStatus(`Restart failed: ${error.message}`, "error");
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
        parts.push(`${profileOverrideChangeCount()} override profile`);
      }
      if (encounterEdits.size) {
        parts.push(`${encounterEdits.size} route`);
      }
      if (routeOverrideEdits.size) {
        parts.push(`${routeOverrideEdits.size} route override`);
      }
      if (spawnSettingEdits.size) {
        parts.push(`${spawnSettingEdits.size} setting`);
      }
      if (!parts.length) return "";
      const total = profileEdits.size + profileMemberEdits.size + profileOverrideChangeCount() + encounterEdits.size + routeOverrideEdits.size + spawnSettingEdits.size;
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

    function updateRouteAfterOverride(route, message = "") {
      syncPendingRouteId(route.id);
      routeOverrideRenderLock = true;
      try {
        renderRouteDetailHead();
        if (String(selectedRouteId) === String(route.id)) {
          renderRouteEditor();
        }
        refreshRouteRow(route.id);
        updateEncounterSaveControls();
        updateGlobalEditStatus();
        if (message) {
          setEncounterSaveStatus(message);
        }
      } finally {
        routeOverrideRenderLock = false;
      }
    }

    function closeRouteOverrideDialog() {
      routeOverrideDialogRouteId = null;
      if (els.routeOverrideDialog.open) {
        els.routeOverrideDialog.close();
      }
      els.routeOverrideDialog.innerHTML = "";
    }

    function setRouteOverrideDialogError(message) {
      const error = els.routeOverrideDialog.querySelector(".route-swap-error");
      if (error) error.textContent = message || "";
    }

    function updateRouteOverrideDialogIcon(input) {
      const species = routeSpeciesOption(input.value) || speciesBySymbol("SPECIES_NONE");
      const icon = els.routeOverrideDialog.querySelector(".route-swap-head .mon-icon");
      if (icon && icon.dataset.symbol !== species.symbol) {
        icon.outerHTML = routeOverrideIconTag(species);
      }
    }

    function renderRouteOverrideDialog(route) {
      const option = routeOverrideSpecies(route);
      const iconSpecies = option || speciesBySymbol("SPECIES_NONE");
      const value = option ? routeSpeciesInputValue(option.symbol) : "";
      const targets = routeOverrideTargets(route);
      const state = routeOverrideState(route);
      const routeLabel = `${route.name} ${routeMapText(route)}`;
      els.routeOverrideDialog.innerHTML = `
        <form class="route-swap-card route-override-card" method="dialog">
          <div class="route-swap-head">
            ${routeOverrideIconTag(iconSpecies)}
            <div class="route-swap-title">
              <strong>Route override</strong>
              <span>${esc(routeLabel)} · ${esc(targets.length)} entr${targets.length === 1 ? "y" : "ies"}</span>
            </div>
          </div>
          <label class="route-swap-field">
            <span>Only encounter</span>
            <input id="routeOverrideInput" class="route-swap-input" type="text" list="routeSpeciesOptions" value="${esc(value)}" autocomplete="off" placeholder="Pokemon"${targets.length ? "" : " disabled"}>
          </label>
          <div class="route-swap-help">Choose one Pokemon to make it the only encounter for this route.</div>
          <div class="route-swap-error" aria-live="polite"></div>
          <div class="route-swap-actions">
            <button class="control highlight-action" type="button" data-route-override-action="clear"${state ? "" : " disabled"}>Turn off</button>
            <button class="control" type="button" data-route-override-action="cancel">Cancel</button>
            <button class="control primary-action" type="submit" data-route-override-action="apply"${targets.length ? "" : " disabled"}>Apply</button>
          </div>
        </form>
      `;
    }

    function openRouteOverrideDialog(routeId) {
      const route = routesById.get(String(routeId));
      if (!route) return false;
      if (String(selectedRouteId) !== String(route.id)) {
        selectRoute(route.id);
      }
      routeOverrideDialogRouteId = String(route.id);
      renderRouteOverrideDialog(route);
      if (!els.routeOverrideDialog.open) {
        els.routeOverrideDialog.showModal();
      }
      const input = els.routeOverrideDialog.querySelector("#routeOverrideInput");
      if (input && !input.disabled) {
        input.focus();
        input.select();
      }
      return true;
    }

    function applyRouteOverrideDialog() {
      const route = routesById.get(String(routeOverrideDialogRouteId));
      const input = els.routeOverrideDialog.querySelector("#routeOverrideInput");
      if (!route || !input) return false;
      const raw = String(input.value || "").trim();
      const option = raw ? routeSpeciesOption(raw) : null;
      input.classList.toggle("invalid", !option || option.symbol === "SPECIES_NONE");
      if (!option || option.symbol === "SPECIES_NONE") {
        setRouteOverrideDialogError("Choose a valid Pokemon.");
        return false;
      }
      if (setRouteOverride(route, option)) {
        closeRouteOverrideDialog();
        return true;
      }
      return false;
    }

    function handleRouteOverrideControlClick(event) {
      const control = event.target.closest("[data-route-override-control]");
      if (!control) return false;
      event.preventDefault();
      event.stopPropagation();
      openRouteOverrideDialog(control.dataset.routeId);
      return true;
    }

    function setRouteOverride(route, option) {
      if (!route || !option || option.symbol === "SPECIES_NONE") return false;
      const targets = routeOverrideTargets(route);
      if (!targets.length) {
        setEncounterSaveStatus(`${route.name} has no encounter slots to override`);
        return false;
      }

      const writeSymbol = routeSpeciesWriteSymbol(option);
      const writeForm = routeSpeciesWriteForm(option);
      const saved = savedRouteOverride(route);
      const pending = pendingRouteOverride(route.id);
      if (saved
          && !pending
          && String(saved.species) === String(writeSymbol)
          && String(saved.form ?? 0) === String(writeForm)) {
        setEncounterSaveStatus("No override changes");
        return false;
      }

      const baselineEntries = routeOverrideBaselineEntries(route, targets);
      targets.forEach(target => {
        setEncounterEdit(route.id, target.path, target.originalSymbol, writeSymbol);
        setEncounterEdit(route.id, target.formPath, target.originalForm, writeForm);
      });
      routeOverrideEdits.set(String(route.id), {
        action: "set",
        species: writeSymbol,
        form: writeForm,
        entries: baselineEntries,
      });
      updateRouteAfterOverride(route, `${route.name} override set to ${routeSpeciesShortSymbol(option.symbol)}`);
      return true;
    }

    function clearRouteOverride(route) {
      if (!route) return false;
      const saved = savedRouteOverride(route);
      const pending = pendingRouteOverride(route.id);
      if (!saved && !pending) return false;

      const targetsByPath = new Map(routeOverrideTargets(route).map(target => [target.path, target]));
      const baselineEntries = routeOverrideBaselineEntries(route);
      baselineEntries.forEach(entry => {
        const target = targetsByPath.get(entry.path);
        const originalSymbol = target?.originalSymbol ?? routePendingValue(route.id, entry.path, entry.species);
        const originalForm = target?.originalForm ?? routePendingValue(route.id, entry.formPath, entry.form);
        setEncounterEdit(route.id, entry.path, originalSymbol, entry.species);
        setEncounterEdit(route.id, entry.formPath, originalForm, entry.form ?? 0);
      });

      if (saved) {
        routeOverrideEdits.set(String(route.id), { action: "clear" });
      } else {
        routeOverrideEdits.delete(String(route.id));
      }
      updateRouteAfterOverride(route, `${route.name} override off`);
      return true;
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
      if (!encounterEdits.size && !routeOverrideEdits.size) return true;
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
          body: JSON.stringify({ changes: routeChangePayload(), overrides: routeOverridePayload() })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result.error || `HTTP ${response.status}`);
        }
        encounterEdits.clear();
        routeOverrideEdits.clear();
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
      if (profilesEditable && !commitAllProfileCombos(true)) {
        updateSaveControls();
        setSaveStatus(`${invalidProfileComboCount()} invalid value${invalidProfileComboCount() === 1 ? "" : "s"}`);
        return false;
      }
      if (!(profilesEditable && (profileEdits.size || profileMemberEdits.size || profileOverrideChangeCount())) && !encounterEdits.size && !routeOverrideEdits.size && !spawnSettingEdits.size) return true;
      const saveProfiles = profilesEditable && profileEdits.size > 0;
      const saveProfileMembers = profilesEditable && profileMemberEdits.size > 0;
      const saveProfileOverrides = profilesEditable && profileOverrideChangeCount() > 0;
      const saveEncounters = encounterEdits.size > 0 || routeOverrideEdits.size > 0;
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
      if (saved && !profileEdits.size && !profileMemberEdits.size && !profileOverrideChangeCount() && !encounterEdits.size && !routeOverrideEdits.size && !spawnSettingEdits.size) {
        await loadData({ keepStatus: true });
        const savedParts = [
          saveProfiles ? "profile" : "",
          saveProfileMembers ? "profile member" : "",
          saveProfileOverrides ? "override profile" : "",
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
      profileOverrideProfileEdits.clear();
      profileOverrideNameEdits.clear();
      profileOverrideEdits = [];
      profileOverrideRemoveEdits.clear();
      encounterEdits.clear();
      routeOverrideEdits.clear();
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
      const name = profileDisplayName(item);
      els.detailHead.innerHTML = `
        <div class="profile-detail-head">
          <div class="profile-detail-top">
            <div class="profile-detail-title">
              ${profileClassBadge(item)}
              <div>
                <h2>${esc(name)}</h2>
                <div class="meta">
                  <span>${esc(profileComboRawDisplay(item.symbol))}</span>
                  <span>${esc(assigned.length)} ${isOverrideProfile(item) ? "affected" : "Pokemon"}</span>
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
          <div class="profile-detail-overview" title="${esc(assigned.length)} Pokemon ${isOverrideProfile(item) ? "match this override profile" : "use this profile"}">
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
      const overrideFields = isOverrideProfile(item) ? behaviorOverrideMaskLabels(item.override) : [];
      const name = profileDisplayName(item);
      els.profilesTab.innerHTML = `
        ${profileDatalistsHtml}
        <div class="profile-focus">
          <article class="card" data-class-index="${esc(item.index)}">
            <div class="card-head profile-focus-head">
              <div class="profile-focus-title" title="${esc(profileComboRawDisplay(item.symbol))}">
                ${profileClassBadge(item)}
                <span>${esc(name)}</span>
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
                <div class="card-title">${isOverrideProfile(item) ? "Affected Pokemon" : "Applied Pokemon"}</div>
                ${profileAddControl(item)}
                <span class="chip neutral">${esc(assigned.length)} ${isOverrideProfile(item) ? "affected" : "Pokemon"}</span>
              </div>
              ${profileMemberStrip(assigned, item)}
            </article>
            <article class="card profile-resolver-card">
              <div class="card-head">
                <div class="card-title">${isOverrideProfile(item) ? "Override" : "Resolver"}</div>
                <span class="chip neutral">${isOverrideProfile(item) ? esc(`${overrideFields.length} fields`) : esc(`${item.classRuleCount || 0} rules`)}</span>
              </div>
              ${isOverrideProfile(item)
                ? `<div class="profile-rule-values"><div class="rule"><div class="rule-top"><span>${esc(item.summary || "Override profile")}</span><span class="muted">${esc(overrideFields.join(", ") || "No fields")}</span></div></div></div>`
                : `<div class="primitive-grid">${profilePrimitiveGroups(item)}</div><div class="profile-rule-values">${profileRuleList(item)}</div>`}
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
      const overrideProfiles = appData.classes.filter(item => isOverrideProfile(item));
      const visibleOverrideProfileCount = overrideProfiles.filter(item => !profileOverrideIsRemoving(item)).length + profileOverrideEdits.length;
      els.rulesTab.innerHTML = `
        <div class="rules">
          <section>
            <div class="pane-head" style="margin:-12px -12px 10px"><div class="pane-title">Class Rules</div><div class="count">${esc(appData.classRules.length)}</div></div>
            <div class="rule-list">
              ${groupedClassRules(appData.classRules).map(classRuleGroupHtml).join("")}
            </div>
          </section>
          <section class="behavior-override-section">
            <div class="pane-head" style="margin:-12px -12px 10px"><div class="pane-title">Override Profiles</div><div class="count">${esc(Math.max(0, visibleOverrideProfileCount))}</div></div>
            <div class="rule-list">
              ${overrideProfiles.map(item => profileOverrideProfileRuleHtml(item)).join("") || `<div class="rule"><div class="muted">No override profiles</div></div>`}
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
      } else if (activeView === "encounters") {
        renderEncounters();
      } else {
        renderSoundFilters();
        renderSoundEffects();
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
        const response = await fetch(`/data.json?ts=${Date.now()}`, { signal: controller.signal, cache: "no-store" });
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
        const selectedProfileStillExists = selectedClassIndex !== null
          && appData.classes.some(item => String(item.index) === String(selectedClassIndex));
        if (!selectedProfileStillExists) {
          if (selectedSymbol && assignmentsBySymbol.has(selectedSymbol)) {
            selectedClassIndex = assignmentsBySymbol.get(selectedSymbol).behaviorClass.value;
          } else if (appData.classes.length) {
            selectedClassIndex = appData.classes[0].index;
          }
        }
        if (selectedRouteId === null && appData.routes.length) {
          selectedRouteId = appData.routes[0].id;
        }
        visibleSpeciesLimit = LIST_PAGE_SIZE;
        render();
        if (lastShinyCounterPayload) {
          renderReservedShinies(lastShinyCounterPayload);
        }
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
    els.reservedShinyList.addEventListener("click", event => {
      const button = event.target.closest("[data-reserved-shiny-slot]");
      if (!button) return;
      event.preventDefault();
      openReservedShinyDetail(button.dataset.reservedShinySlot);
    });
    els.reservedShinyDialog.addEventListener("click", event => {
      if (event.target === els.reservedShinyDialog) {
        closeReservedShinyDetail();
        return;
      }
      const button = event.target.closest("[data-reserved-shiny-action='close']");
      if (!button) return;
      event.preventDefault();
      closeReservedShinyDetail();
    });
    els.reservedShinyDialog.addEventListener("cancel", event => {
      event.preventDefault();
      closeReservedShinyDetail();
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
    els.restartServer.addEventListener("click", () => {
      restartServerAction();
    });
    els.resetAllEdits.addEventListener("click", resetAllEdits);
    document.addEventListener("click", event => {
      const button = event.target.closest("[data-action='clear-profile-section'], [data-action='create-profile'], [data-action='create-override-profile'], [data-action='convert-profile-to-override'], [data-action='duplicate-profile'], [data-action='rename-profile'], [data-action='delete-profile'], [data-action='toggle-remove-profile-override'], [data-action='move-override-profile-up'], [data-action='move-override-profile-down']");
      if (!button || button.disabled) return;
      if (!button.closest("#detailHead, #profilesTab")) return;
      event.preventDefault();
      event.stopPropagation();
      if (button.dataset.action === "clear-profile-section") {
        clearProfileSectionToInherit(button);
      } else if (button.dataset.action === "toggle-remove-profile-override") {
        toggleProfileOverrideRemoval(button.dataset.overrideOrders || button.dataset.overrideOrder);
      } else if (button.dataset.action === "move-override-profile-up") {
        moveOverrideProfile(button.dataset.classIndex, -1);
      } else if (button.dataset.action === "move-override-profile-down") {
        moveOverrideProfile(button.dataset.classIndex, 1);
      } else if (button.dataset.action === "create-profile") {
        createProfileFromPrompt();
      } else if (button.dataset.action === "create-override-profile") {
        createOverrideProfileFromPrompt();
      } else if (button.dataset.action === "convert-profile-to-override") {
        createOverrideProfileFromClassPrompt(button.dataset.classIndex);
      } else if (button.dataset.action === "duplicate-profile") {
        duplicateProfileFromPrompt(button.dataset.classIndex);
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
    els.soundSearch.addEventListener("input", renderSoundEffects);
    els.soundRefresh.addEventListener("click", () => {
      loadSoundEffects().catch(error => {
        soundStatus(error.message);
      });
    });
    document.querySelectorAll("[data-sound-filter]").forEach(button => {
      button.addEventListener("click", () => {
        soundFilter = button.dataset.soundFilter;
        localStorage.setItem("owSoundFilter", soundFilter);
        renderSoundFilters();
        renderSoundEffects();
      });
    });
    els.soundList.addEventListener("click", event => {
      const row = event.target.closest("[data-sound-id]");
      if (!row) return;
      selectSoundEffect(Number(row.dataset.soundId), { scroll: false });
    });
    els.soundList.addEventListener("dblclick", event => {
      const row = event.target.closest("[data-sound-id]");
      if (!row) return;
      selectSoundEffect(Number(row.dataset.soundId), { scroll: false });
      playSelectedSoundEffect();
    });
    els.soundDetail.addEventListener("click", event => {
      const button = event.target.closest("[data-move-preview-id]");
      if (!button) return;
      const moveId = Number(button.dataset.movePreviewId);
      const effect = selectedSoundEffect();
      const alias = (effect?.moveAliases || []).find(row => Number(row.moveId) === moveId);
      playMoveSoundEffect(moveId, alias?.moveName || `Move ${moveId}`);
    });
    els.soundPlay.addEventListener("click", playSelectedSoundEffect);
    els.soundPlayRaw.addEventListener("click", playSelectedRawSoundEffect);
    els.soundAudition.addEventListener("click", auditionSelectedSoundEffect);
    els.soundStop.addEventListener("click", () => {
      stopSoundPlayback();
      soundStatus("Playback stopped.");
    });
    els.soundPrevious.addEventListener("click", () => stepSoundEffect(-1));
    els.soundNext.addEventListener("click", () => stepSoundEffect(1));
    els.soundPreviousLarge.addEventListener("click", () => stepSoundEffect(-16));
    els.soundNextLarge.addEventListener("click", () => stepSoundEffect(16));
    els.soundAudioFiles.addEventListener("change", () => importSoundAudioFiles(els.soundAudioFiles.files));
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
      if (handleRouteOverrideControlClick(event)) return;
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
      if (handleRouteOverrideControlClick(event)) return;
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

    els.routeOverrideDialog.addEventListener("click", event => {
      if (event.target === els.routeOverrideDialog) {
        closeRouteOverrideDialog();
        return;
      }
      const action = event.target.closest("[data-route-override-action]");
      if (!action) return;
      if (action.dataset.routeOverrideAction === "cancel") {
        event.preventDefault();
        closeRouteOverrideDialog();
      } else if (action.dataset.routeOverrideAction === "clear") {
        event.preventDefault();
        const route = routesById.get(String(routeOverrideDialogRouteId));
        if (route && clearRouteOverride(route)) {
          closeRouteOverrideDialog();
        }
      }
    });
    els.routeOverrideDialog.addEventListener("submit", event => {
      event.preventDefault();
      applyRouteOverrideDialog();
    });
    els.routeOverrideDialog.addEventListener("input", event => {
      const input = event.target.closest("#routeOverrideInput");
      if (!input) return;
      input.classList.remove("invalid");
      setRouteOverrideDialogError("");
      updateRouteOverrideDialogIcon(input);
    });
    els.routeOverrideDialog.addEventListener("cancel", event => {
      event.preventDefault();
      closeRouteOverrideDialog();
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
      const dragHandle = event.target.closest("[data-action='drag-override-profile']");
      if (dragHandle) {
        event.preventDefault();
        event.stopPropagation();
        return;
      }
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
      addTargetToCurrentProfile(form);
    });
    els.speciesList.addEventListener("input", event => {
      const input = event.target.closest(".profile-row-add-input");
      if (!input) return;
      input.classList.remove("invalid");
      setSaveStatus(pendingChangeStatus());
    });
    els.speciesList.addEventListener("change", event => {
      handleProfileAddFormChange(event);
    });
    els.speciesList.addEventListener("dragstart", event => {
      const handle = event.target.closest("[data-action='drag-override-profile']");
      if (!handle) return;
      const item = profileClassByIndex(handle.dataset.classIndex);
      if (!isOverrideProfile(item)) return;
      profileOverrideDragClassIndex = String(item.index);
      const row = handle.closest(".profile-row.override-profile");
      if (row) row.classList.add("dragging");
      if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", profileOverrideDragClassIndex);
      }
    });
    els.speciesList.addEventListener("dragover", event => {
      if (!profileOverrideDragClassIndex) return;
      const info = profileOverrideDropInfo(event);
      if (!info) {
        profileOverrideMarkDropTarget(null);
        return;
      }
      event.preventDefault();
      if (event.dataTransfer) {
        event.dataTransfer.dropEffect = "move";
      }
      profileOverrideMarkDropTarget(info);
    });
    els.speciesList.addEventListener("dragleave", event => {
      if (!profileOverrideDragClassIndex) return;
      const related = event.relatedTarget;
      if (!related || !els.speciesList.contains(related)) {
        profileOverrideMarkDropTarget(null);
      }
    });
    els.speciesList.addEventListener("drop", event => {
      if (!profileOverrideDragClassIndex) return;
      const sourceClassIndex = profileOverrideDragClassIndex;
      const info = profileOverrideDropInfo(event);
      event.preventDefault();
      profileOverrideDragClassIndex = null;
      profileOverrideClearDragMarkers();
      if (!info) return;
      moveOverrideProfileToDrop(sourceClassIndex, info.classIndex, info.position);
    });
    els.speciesList.addEventListener("dragend", () => {
      profileOverrideDragClassIndex = null;
      profileOverrideClearDragMarkers();
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
      addTargetToCurrentProfile(form);
    });
    els.profileAddMenu.addEventListener("change", event => {
      handleProfileAddFormChange(event);
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
      if (handleSoundKeyNavigation(event)) return;
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
      return profileEdits.size + profileMemberEdits.size + profileOverrideChangeCount() + encounterEdits.size + routeOverrideEdits.size + spawnSettingEdits.size;
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
      profileOverrideProfileEdits.clear();
      profileOverrideNameEdits.clear();
      profileOverrideEdits = [];
      profileOverrideRemoveEdits.clear();
      encounterEdits.clear();
      routeOverrideEdits.clear();
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

    async function moveOverrideProfile(classIndex, delta) {
      const rows = orderedOverrideProfiles();
      const index = rows.findIndex(row => String(row.index) === String(classIndex));
      const targetIndex = index + delta;
      if (index < 0 || targetIndex < 0 || targetIndex >= rows.length) return;
      const movedProfileName = rows[index].name || profileDisplayName(rows[index]);
      const orderedRows = rows.slice();
      const [moved] = orderedRows.splice(index, 1);
      orderedRows.splice(targetIndex, 0, moved);
      const orderGroups = orderedRows.map(item => profileOverrideOrders(item).map(order => Number(order)));
      const currentGroups = rows.map(item => profileOverrideOrders(item).map(order => Number(order)));
      if (JSON.stringify(orderGroups) === JSON.stringify(currentGroups)) return;
      if (!discardPendingChangesForProfileManagement()) return;
      await saveProfileOverrideReorder(orderGroups, movedProfileName);
    }

    function profileOverrideClearDragMarkers() {
      els.speciesList.querySelectorAll(".profile-row.override-profile.dragging, .profile-row.override-profile.drag-over-before, .profile-row.override-profile.drag-over-after").forEach(row => {
        row.classList.remove("dragging", "drag-over-before", "drag-over-after");
      });
    }

    function profileOverrideDropInfo(event) {
      const row = event.target.closest(".profile-row.override-profile");
      if (!row || !els.speciesList.contains(row)) return null;
      const classIndex = row.dataset.classIndex;
      if (!classIndex || String(classIndex) === String(profileOverrideDragClassIndex)) return null;
      const rect = row.getBoundingClientRect();
      const position = event.clientY < rect.top + rect.height / 2 ? "before" : "after";
      return { row, classIndex, position };
    }

    function profileOverrideMarkDropTarget(info) {
      els.speciesList.querySelectorAll(".profile-row.override-profile.drag-over-before, .profile-row.override-profile.drag-over-after").forEach(row => {
        row.classList.remove("drag-over-before", "drag-over-after");
      });
      if (info?.row) {
        info.row.classList.add(info.position === "before" ? "drag-over-before" : "drag-over-after");
      }
    }

    async function moveOverrideProfileToDrop(sourceClassIndex, targetClassIndex, position) {
      const rows = orderedOverrideProfiles();
      const sourceIndex = rows.findIndex(row => String(row.index) === String(sourceClassIndex));
      const targetIndex = rows.findIndex(row => String(row.index) === String(targetClassIndex));
      if (sourceIndex < 0 || targetIndex < 0 || sourceIndex === targetIndex) return;
      const movedProfileName = rows[sourceIndex].name || profileDisplayName(rows[sourceIndex]);
      const orderedRows = rows.slice();
      const [moved] = orderedRows.splice(sourceIndex, 1);
      let insertIndex = orderedRows.findIndex(row => String(row.index) === String(targetClassIndex));
      if (insertIndex < 0) return;
      if (position === "after") {
        insertIndex++;
      }
      orderedRows.splice(insertIndex, 0, moved);
      const orderGroups = orderedRows.map(item => profileOverrideOrders(item).map(order => Number(order)));
      const currentGroups = rows.map(item => profileOverrideOrders(item).map(order => Number(order)));
      if (JSON.stringify(orderGroups) === JSON.stringify(currentGroups)) return;
      if (!discardPendingChangesForProfileManagement()) return;
      await saveProfileOverrideReorder(orderGroups, movedProfileName);
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
      await manageProfile({ action: "create", name: trimmedName });
    }

    async function createOverrideProfileFromPrompt() {
      if (!discardPendingChangesForProfileManagement()) return;
      const name = window.prompt("Override profile name", "New override profile");
      if (name === null) return;
      const trimmedName = name.trim();
      if (!trimmedName) {
        setSaveStatus("Override profile name is required", "error");
        return;
      }
      profileOverrideEdits.push({
        id: `${Date.now()}-${profileOverrideEdits.length}`,
        name: trimmedName,
        targetKind: "empty",
        targetValue: "SPECIES_NONE",
        targetName: "No target",
        fields: {},
        matches: [profileOverrideMatchForNoTarget()],
        matchCount: 0,
      });
      await saveProfileOverrideChanges();
    }

    async function createOverrideProfileFromClassPrompt(classIndex) {
      const item = profileClassByIndex(classIndex ?? selectedClassIndex);
      if (!item || isOverrideProfile(item)) return;
      if (profileIsDefaultClass(item.index)) {
        setSaveStatus("Default profile cannot be converted because it resolves to every Pokemon. Create an override profile and add targets instead.", "error");
        updateSaveControls();
        return;
      }
      const sourceName = profileDisplayName(item);
      const fields = {};
      Object.entries(profileOverrideFieldsForItem(item)).forEach(([field, raw]) => {
        if (profileOverrideFieldOption(field)) fields[field] = raw;
      });
      if (!Object.keys(fields).length) {
        setSaveStatus(`${sourceName} has no fields that can be used in override profiles`, "error");
        updateSaveControls();
        return;
      }
      const name = window.prompt(`Create override profile from ${sourceName}`, `${sourceName} override`);
      if (name === null) return;
      const trimmedName = name.trim();
      if (!trimmedName) {
        setSaveStatus("Override profile name is required", "error");
        return;
      }
      const assigned = profileSavedBaseAssignmentsForClass(item.index);
      if (!assigned.length) {
        setSaveStatus(`${sourceName} has no saved Pokemon assignments to convert`, "error");
        updateSaveControls();
        return;
      }
      const matches = assigned
        .map(assignment => assignment?.species?.symbol)
        .filter(Boolean)
        .map(symbol => profileOverrideMatchForSpecies(symbol));
      if (!matches.length) {
        setSaveStatus(`${sourceName} has no valid Pokemon symbols to convert`, "error");
        updateSaveControls();
        return;
      }
      if (!discardPendingChangesForProfileManagement()) return;
      profileOverrideEdits.push({
        id: `${Date.now()}-${profileOverrideEdits.length}`,
        name: trimmedName,
        targetKind: "pokemon",
        targetValue: "",
        targetName: `${assigned.length} assigned Pokemon`,
        fields,
        matches,
        matchCount: assigned.length,
      });
      await saveProfileOverrideChanges();
    }

    async function renameProfileFromPrompt(classIndex) {
      const item = profileClassByIndex(classIndex ?? selectedClassIndex);
      if (!item) return;
      if (isOverrideProfile(item)) {
        const currentName = profileDisplayName(item);
        const name = window.prompt(`Rename ${currentName}`, currentName);
        if (name === null) return;
        const trimmedName = name.trim();
        if (!trimmedName) {
          setSaveStatus("Override profile name is required", "error");
          return;
        }
        const orders = profileOverrideOrders(item);
        if (trimmedName === item.name) {
          orders.forEach(order => profileOverrideNameEdits.delete(order));
        } else {
          orders.forEach(order => profileOverrideNameEdits.set(order, trimmedName));
        }
        refreshProfileClassSearchText(item.index);
        markProfilePanelsDirty("profiles", "rules");
        renderClassFilter();
        renderSpeciesList();
        renderDetailHead();
        renderActiveProfilePanel(true);
        updateGlobalEditStatus();
        setSaveStatus(pendingChangeStatus(), "warning");
        return;
      }
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

    async function duplicateProfileFromPrompt(classIndex) {
      const item = profileClassByIndex(classIndex ?? selectedClassIndex);
      if (!item) return;
      if (isOverrideProfile(item)) {
        if (!discardPendingChangesForProfileManagement()) return;
        const currentName = profileDisplayName(item);
        const name = window.prompt(`Duplicate ${currentName} as`, `${currentName} copy`);
        if (name === null) return;
        const trimmedName = name.trim();
        if (!trimmedName) {
          setSaveStatus("Override profile name is required", "error");
          return;
        }
        profileOverrideEdits.push({
          id: `${Date.now()}-${profileOverrideEdits.length}`,
          name: trimmedName,
          targetKind: "override",
          targetValue: item.symbol,
          targetName: currentName,
          fields: profileOverrideFieldsForItem(item),
          matches: (item.matches || [item.match]).map(match => profileOverrideRawMatch(match)),
          matchCount: item.speciesCount || profileAssignmentsForClass(item.index).length,
        });
        await saveProfileOverrideChanges();
        return;
      }
      const name = window.prompt(`Duplicate ${item.name} as`, `${item.name} copy`);
      if (name === null) return;
      const trimmedName = name.trim();
      if (!trimmedName) {
        setSaveStatus("Profile name is required", "error");
        return;
      }
      await manageProfile({ action: "duplicate", classIndex: item.index, name: trimmedName });
    }

    async function deleteProfileWithConfirmation(classIndex) {
      const item = profileClassByIndex(classIndex ?? selectedClassIndex);
      if (!item) return;
      if (profileIsDefaultClass(item.index)) {
        setSaveStatus("Default profile cannot be deleted", "error");
        return;
      }
      if (item.canDelete === false) {
        setSaveStatus(`${item.name} is referenced by behavior runtime code and cannot be deleted safely`, "error");
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
      const name = profileDisplayName(item);
      return `
        <form class="profile-add-menu-form" data-profile-add-form data-profile-add-class="${esc(item.index)}">
          <div class="profile-add-menu-title">
            <span>Add target to ${esc(name)}</span>
            <span class="chip neutral">${esc(profileAssignmentsForClass(item.index).length)} ${isOverrideProfile(item) ? "affected" : "Pokemon"}</span>
          </div>
          <div class="profile-add-control">
            ${profileAddFieldsHtml(item)}
          </div>
          <div class="profile-add-menu-actions">
            <button class="control" type="button" data-action="close-profile-add-menu">Cancel</button>
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
        const input = els.profileAddMenu.querySelector(".profile-add-input, .profile-add-spawn-pool, .profile-add-type");
        if (input) input.focus();
      });
    }

    function refreshProfileAddFormTargets(root = document) {
      root.querySelectorAll("[data-profile-add-form]").forEach(form => {
        const kind = profileValidAddTargetKind();
        const kindSelect = form.querySelector("[data-profile-add-kind]");
        if (kindSelect) kindSelect.value = kind;
        const host = form.querySelector("[data-profile-add-target-host]");
        if (host) host.innerHTML = profileAddTargetControlHtml(kind);
      });
    }

    function handleProfileAddFormChange(event) {
      const kindSelect = event.target.closest("[data-profile-add-kind]");
      const poolSelect = event.target.closest("[data-profile-add-spawn-pool]");
      const typeSelect = event.target.closest("[data-profile-add-type]");
      if (!kindSelect && !poolSelect && !typeSelect) return false;
      const form = event.target.closest("[data-profile-add-form]");
      if (kindSelect) {
        profileAddTargetKind = profileValidAddTargetKind(kindSelect.value);
      }
      if (poolSelect) {
        profileAddSpawnPool = profileSpawnPoolOption(poolSelect.value)?.raw || poolSelect.value;
      }
      if (typeSelect) {
        profileAddType = profileTypeOption(typeSelect.value)?.symbol || typeSelect.value;
      }
      persistProfileAddDraft();
      refreshProfileAddFormTargets(document);
      if (kindSelect && form) {
        const nextInput = form.querySelector(".profile-add-input, .profile-add-spawn-pool, .profile-add-type");
        if (nextInput) nextInput.focus();
      }
      setSaveStatus(pendingChangeStatus());
      return true;
    }

    function addTargetToCurrentProfile(form) {
      const targetClassIndex = form.dataset.profileAddClass;
      const item = targetClassIndex !== undefined ? profileClassByIndex(targetClassIndex) : currentProfileClass();
      if (!item) return;
      const target = profileAddTargetFromForm(form);
      if (!profileAddTargetIsValid(target)) {
        if (target?.input) target.input.classList.add("invalid");
        if (target?.select) target.select.classList.add("invalid");
        setSaveStatus(profileAddTargetInvalidMessage(target), "error");
        updateSaveControls();
        return;
      }
      if (target.input) target.input.classList.remove("invalid");
      if (target.select) target.select.classList.remove("invalid");

      if (isOverrideProfile(item)) {
        const matches = profileOverrideMatchesForAddTarget(target);
        if (!matches.length) {
          setSaveStatus(`No valid ${target.label || "target"} matches found`, "error");
          updateSaveControls();
          return;
        }
        profileOverrideEdits.push({
          id: `${Date.now()}-${profileOverrideEdits.length}`,
          name: profileDisplayName(item),
          targetKind: target.kind,
          targetValue: profileAddTargetValue(target),
          targetName: target.label || "Target",
          fields: profileOverrideFieldsForItem(item),
          matches,
          matchCount: profileAddTargetMatchCount(target),
        });
        selectedClassIndex = item.index;
        closeProfileAddMenu();
        clearProfileAddTargetInput(target);
        refreshAllProfileClassSearchText();
        markProfilePanelsDirty("profiles", "selected", "rules");
        renderSpeciesList();
        renderDetailHead();
        renderActiveProfilePanel(true);
        updateSaveControls();
        setSaveStatus(`Added ${target.label} to ${profileDisplayName(item)}`, "warning");
        return;
      }

      const candidates = profileAssignableSpeciesForTarget(item, target);
      if (!candidates.length) {
        const targetName = target.label || "target";
        clearProfileAddTargetInput(target);
        setSaveStatus(`All ${targetName} Pokemon already use ${item.name}`);
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
      selectedSymbol = candidates[0].symbol;
      selectedClassIndex = item.index;
      closeProfileAddMenu();
      clearProfileAddTargetInput(target);
      appData.classes.forEach(row => {
        row.searchText = profileClassSearchText(row, profileAssignmentsForClass(row.index));
      });
      markProfilePanelsDirty("profiles", "selected");
      renderSpeciesList();
      renderDetailHead();
      renderActiveProfilePanel(true);
      updateSaveControls();
      setSaveStatus(`Added ${candidates.length} ${target.label || "target"} Pokemon to ${item.name}`, "warning");
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
      if (isOverrideProfile(item)) {
        const hitOrders = profileOverrideHitOrdersForAssignment(assignment, item);
        if (!hitOrders.length) {
          setSaveStatus(`${species.name} is not affected by ${profileDisplayName(item)}`);
          updateSaveControls();
          return;
        }
        if (hitOrders.every(order => profileOverrideRemoveEdits.has(order))) {
          hitOrders.forEach(order => profileOverrideRemoveEdits.delete(order));
          setSaveStatus(`Undid removing ${species.name} from ${profileDisplayName(item)}`, "warning");
        } else {
          hitOrders.forEach(order => profileOverrideRemoveEdits.add(order));
          setSaveStatus(`Removed ${species.name} from ${profileDisplayName(item)}`, "warning");
        }
        selectedClassIndex = item.index;
        if (selectedSymbol === symbol) {
          selectedSymbol = null;
        }
        refreshAllProfileClassSearchText();
        markProfilePanelsDirty("profiles", "selected", "rules");
        renderSpeciesList();
        renderDetailHead();
        renderActiveProfilePanel(true);
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
      addTargetToCurrentProfile(form);
    });

    els.profilesTab.addEventListener("input", event => {
      const input = event.target.closest(".profile-add-input");
      if (!input) return;
      input.classList.remove("invalid");
      setSaveStatus(pendingChangeStatus());
    });

    els.profilesTab.addEventListener("change", event => {
      if (handleProfileAddFormChange(event)) return;
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
        toggleProfileOverrideRemoval(removeExistingButton.dataset.overrideOrders || removeExistingButton.dataset.overrideOrder);
        return;
      }
      const selectOverrideButton = event.target.closest("[data-action='select-override-profile']");
      if (selectOverrideButton) {
        event.preventDefault();
        selectProfileClass(selectOverrideButton.dataset.classIndex, { tab: "profiles" });
      }
    });

    function refreshProfileClassSearchText(classIndex) {
      const item = appData.classes.find(row => String(row.index) === String(classIndex));
      if (!item) return;
      item.searchText = profileClassSearchText(item, profileAssignmentsForClass(item.index));
    }

    function updateProfileArchitectureCounts(classIndex) {
      const item = appData.classes.find(row => String(row.index) === String(classIndex));
      if (!item) return;
      els.profilesTab.querySelectorAll("[data-profile-section-fields]").forEach(section => {
        const fields = String(section.dataset.profileSectionFields || "")
          .split(",")
          .map(field => field.trim())
          .filter(Boolean);
        const count = section.querySelector("[data-profile-section-count]");
        if (!count || !fields.length) return;
        const visibleCount = section.querySelectorAll("[data-profile-field]").length;
        count.textContent = profileSectionCountLabel(item, fields, visibleCount);
        const clearButton = section.querySelector("[data-profile-section-clear]");
        if (clearButton) {
          clearButton.disabled = profileSectionCount(item, fields) === 0;
        }
      });
    }

    function updateProfileComboStatus(input = null, refreshOverview = false) {
      if (input?.dataset?.classIndex) {
        refreshProfileClassSearchText(input.dataset.classIndex);
        const item = appData.classes.find(row => String(row.index) === String(input.dataset.classIndex));
        const row = visibleListRow(input.dataset.classIndex);
        if (item && row) {
          row.classList.toggle("changed", profileClassChanged(item));
          const sub = row.querySelector(".profile-row-sub");
          if (sub) sub.textContent = isOverrideProfile(item)
            ? (item.summary || "Override profile")
            : `${profilePendingDisplay(item, "profileId")} · ${profilePendingDisplay(item, "spawnState")}`;
        }
        updateProfileArchitectureCounts(input.dataset.classIndex);
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
    els.profilesTab.addEventListener("input", event => {
      const input = event.target.closest(".profile-number");
      if (!input) return;
      commitProfileNumber(input);
      updateProfileComboStatus(input);
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
      const input = event.target.closest(".profile-number");
      if (!input) return;
      commitProfileNumber(input, true);
      updateProfileComboStatus(input, true);
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
    els.profilesTab.addEventListener("focusout", event => {
      const input = event.target.closest(".profile-number");
      if (!input) return;
      commitProfileNumber(input, true);
      updateProfileComboStatus(input, true);
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
            if path == "/favicon.ico":
                self.send_bytes(b"", "image/x-icon", status=204, cache_control="public, max-age=86400")
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
            sound_audio_match = re.fullmatch(r"/sound-effects/(\d+)\.wav", path)
            if sound_audio_match:
                seq_id = int(sound_audio_match.group(1), 10)
                self.send_bytes(
                    render_sound_effect_wav(seq_id),
                    "audio/wav",
                    cache_control="no-cache",
                )
                return
            move_sound_audio_match = re.fullmatch(r"/move-sound-effects/(\d+)\.wav", path)
            if move_sound_audio_match:
                move_id = int(move_sound_audio_match.group(1), 10)
                self.send_bytes(
                    render_move_sound_effect_wav(move_id),
                    "audio/wav",
                    cache_control="no-cache",
                )
                return
            if path == "/sound-effects":
                self.send_json(sound_effect_metadata_payload())
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
            if path == "/restart-server":
                self.send_json(restart_server_soon())
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


def validate_override_profile_source() -> None:
    raw_behavior_data = BEHAVIOR_DATA_SOURCE.read_text()
    expressions, _ = parse_define_expressions(DEFINE_SOURCE_FILES)
    macros = evaluate_defines(expressions)
    macros.update(evaluate_armips_equ([ARMIPS_CONFIG, ARMIPS_CONSTANTS]))
    terrain_values, destination_values = parse_behavior_data_enums()
    macros.update(terrain_values)
    macros.update(destination_values)
    validate_behavior_data_override_profiles(
        raw_behavior_data,
        macros,
        invert_labels(macros, GROUP_PREFIX),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print parsed overview data as JSON")
    parser.add_argument("--validate-overrides", action="store_true", help="validate grouped override profiles and exit")
    parser.add_argument("--serve", action="store_true", help="serve the interactive browser UI")
    parser.add_argument("--host", default="127.0.0.1", help="host for --serve")
    parser.add_argument("--port", type=int, default=8765, help="port for --serve; use 0 for any free port")
    args = parser.parse_args(argv)

    if args.json:
        json.dump(build_data(), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    if args.validate_overrides:
        validate_override_profile_source()
        return 0
    if args.serve:
        serve(args.host, args.port)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
