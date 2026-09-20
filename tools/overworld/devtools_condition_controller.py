"""Live Wild-controller proof for one conditional-profile intent boundary.

The packaged condition-service probe uses copied inputs.  This module is a
separate, controlled runtime witness.  Its fixture changes only the target
predicate of the existing Ambush Plant condition in the disposable emulator
process.  The unchanged Wild controller, condition adapter, resolver, profile,
and motion path remain the code under test.

The native reader records real controller calls.  During the first accepted
conditional Hop it changes only the generation stored in the condition-owned
target reference.  The live target actor is not changed.  The next controller
evaluation must therefore wait for the intent boundary and fail closed with
STALE_TARGET.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import struct


KIND = "live-condition-controller-v1"
REQUIREMENT = "current.live-condition-controller"

SUBJECT_SPECIES = 70  # Weepinbell
SUBJECT_ROLE = "WILD"
TARGET_ROLE = "FOLLOWER"

PROFILE_ID = "ambush-plant-active"
PROFILE_BYTES = 212
PROFILE_DATA_OFFSET = 32

CONDITION_ID = 11350
CONDITION_NAME = "condition-ambush-plant-notices-player"
CONDITION_APPLICATION = 13
CONDITION_SUBJECT_APPLICATION = 12
CONDITION_DURATION = 36
CONDITION_COOLDOWN = 126
CONDITION_BYTES = 48

CONDITION_PLAYER_NOTICED = 0
CONDITION_POKEMON_NOTICED = 1
CONDITION_TIMED = 1
TARGET_PLAYER = 1
TARGET_ACTOR = 2
TARGET_ROLE_FOLLOWER = 1 << 1
RANGE_RADIUS = 4

BEHAVIOR_CHASE = 3
LOCOMOTION_HOP = 2
TARGET_TOWARD = 2
HOP_DURATION = 6
HOP_DISTANCE = 2
HOP_TRAVEL_FRAMES = HOP_DURATION + (HOP_DISTANCE - 1) * (
    HOP_DURATION - (HOP_DURATION >> 2)
)

PREPARED_ACTOR_BYTES = 52
PREPARED_STATE_BYTES = 16
PREPARED_STATE_POINTER_OFFSET = 12
PREPARED_SOURCE_INDICES_OFFSET = 16
TARGET_GENERATION_IN_STATE = 10
RUNTIME_ACTIVE_MASKS_OFFSET = 1920


def require(value, reason):
    if not value:
        raise ValueError("condition controller: " + reason)


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _blob_sections(blob):
    require(isinstance(blob, (bytes, bytearray)) and len(blob) >= 84,
            "behavior blob is truncated")
    magic, version, header_size, blob_size = struct.unpack_from("<IHHI", blob)
    require((magic, version, header_size, blob_size)
            == (0x4F574244, 79, 84, len(blob)),
            "behavior blob header differs")
    sections = {}
    for name, header_offset, expected_stride in (
            ("profiles", 36, PROFILE_BYTES),
            ("conditions", 52, CONDITION_BYTES)):
        offset, count, stride = struct.unpack_from("<IHH", blob, header_offset)
        require(stride == expected_stride and offset % 4 == 0
                and offset + count * stride <= len(blob),
                name + " section differs")
        sections[name] = (offset, count, stride)
    return sections


def _condition_index(blob, sections):
    offset, count, stride = sections["conditions"]
    matches = [index for index in range(count)
               if struct.unpack_from("<H", blob, offset + index * stride + 32)[0]
               == CONDITION_ID]
    require(len(matches) == 1, "Ambush Plant condition is not unique")
    return matches[0]


def _profile_contract(blob, sections):
    offset, count, stride = sections["profiles"]
    require(CONDITION_APPLICATION < count,
            "Ambush Plant conditional profile is missing")
    start = offset + CONDITION_APPLICATION * stride
    raw = blob[start:start + stride]
    require(len(raw) == PROFILE_BYTES
            and raw[17] == 1
            and raw[18] <= _condition_index(blob, sections)
            < raw[18] + raw[19],
            "Ambush Plant conditional profile ownership differs")
    mask = struct.unpack_from("<I", raw, 20)[0]
    required_mask = (1 << 0) | (1 << 12) | (1 << 13)
    profile = raw[PROFILE_DATA_OFFSET:PROFILE_DATA_OFFSET + 68]
    require(mask & required_mask == required_mask
            and profile[0] == BEHAVIOR_CHASE
            and profile[12] == LOCOMOTION_HOP
            and profile[13] == TARGET_TOWARD
            and profile[20] == 1
            and profile[21] == 2
            and profile[36] == HOP_DURATION,
            "Ambush Plant conditional movement profile differs")
    return {
        "id": PROFILE_ID,
        "index": CONDITION_APPLICATION,
        "applicationIndex": CONDITION_APPLICATION,
        "chillState": BEHAVIOR_CHASE,
        "chillAction": LOCOMOTION_HOP,
        "chillTarget": TARGET_TOWARD,
        "hopMinDistance": 1,
        "hopMaxDistance": 2,
        "hopTime": HOP_DURATION,
    }


def build_live_controller_fixture(source):
    """Patch only player-kind/target bytes in one authenticated live blob copy.

    The returned bytes are intended for a disposable emulator process.  The
    receipt lists the exact changed offsets so the command adapter can patch
    and later restore the same live addresses.
    """
    require(isinstance(source, bytes), "source blob must be immutable bytes")
    sections = _blob_sections(source)
    index = _condition_index(source, sections)
    condition_offset = sections["conditions"][0] + index * CONDITION_BYTES
    raw = source[condition_offset:condition_offset + CONDITION_BYTES]
    require(
        struct.unpack_from("<HH", raw, 20)
        == (CONDITION_DURATION, CONDITION_COOLDOWN)
        and struct.unpack_from("<H", raw, 32)[0] == CONDITION_ID
        and raw[34] == CONDITION_APPLICATION
        and raw[35] == 1
        and raw[36] == CONDITION_SUBJECT_APPLICATION
        and raw[37] == CONDITION_PLAYER_NOTICED
        and raw[38] == CONDITION_TIMED
        and raw[39] == TARGET_PLAYER
        and raw[40] == 0
        and raw[42] == RANGE_RADIUS
        and raw[43] == 4
        and raw[44] == 100,
        "authored Ambush Plant condition differs",
    )
    profile = _profile_contract(source, sections)
    patched = bytearray(source)
    changes = (
        (condition_offset + 37, CONDITION_PLAYER_NOTICED,
         CONDITION_POKEMON_NOTICED, "condition-kind"),
        (condition_offset + 39, TARGET_PLAYER, TARGET_ACTOR, "target-kind"),
        (condition_offset + 40, 0, TARGET_ROLE_FOLLOWER, "target-role"),
    )
    for offset, before, after, _name in changes:
        require(patched[offset] == before, "fixture source byte differs")
        patched[offset] = after
    patched = bytes(patched)
    require(sum(a != b for a, b in zip(source, patched)) == len(changes),
            "fixture changed extra catalog bytes")
    return patched, {
        "fixtureVersion": 1,
        "sourceSha256": _sha(source),
        "patchedSha256": _sha(patched),
        "blobBytes": len(source),
        "condition": {
            "id": CONDITION_ID,
            "name": CONDITION_NAME,
            "index": index,
            "applicationIndex": CONDITION_APPLICATION,
            "subjectApplicationIndex": CONDITION_SUBJECT_APPLICATION,
            "activation": "timed",
            "durationFrames": CONDITION_DURATION,
            "cooldownFrames": CONDITION_COOLDOWN,
            "targetKind": "actor",
            "targetRole": TARGET_ROLE,
            "selection": "nearest",
            "rangeKind": "radius",
            "rangeLength": 4,
        },
        "profile": profile,
        "changes": [
            {"offset": offset, "before": before, "after": after, "field": name}
            for offset, before, after, name in changes
        ],
        "scope": ("disposable live behavior blob: three predicate bytes only; "
                  "the conditional profile and all actor state stay unchanged"),
    }


def restore_live_controller_fixture(patched, receipt):
    require(isinstance(patched, bytes)
            and isinstance(receipt, dict)
            and _sha(patched) == receipt.get("patchedSha256"),
            "patched fixture identity differs")
    restored = bytearray(patched)
    for change in receipt.get("changes", []):
        offset = change.get("offset")
        require(type(offset) is int and 0 <= offset < len(restored)
                and restored[offset] == change.get("after"),
                "patched fixture byte differs before restore")
        restored[offset] = change["before"]
    restored = bytes(restored)
    require(_sha(restored) == receipt.get("sourceSha256"),
            "fixture did not restore the source blob")
    return restored


def target_generation_address(state_pointer, prepared_index):
    for value, limit, label in (
            (state_pointer, 0xFFFFFFFF, "state pointer"),
            (prepared_index, 31, "prepared condition index")):
        require(type(value) is int and 0 <= value <= limit, "invalid " + label)
    require(state_pointer % 4 == 0
            and 0x02000000 <= state_pointer < 0x02400000,
            "state pointer is outside main memory")
    return (state_pointer + prepared_index * PREPARED_STATE_BYTES
            + TARGET_GENERATION_IN_STATE)


def stale_generation(generation):
    require(type(generation) is int and 1 <= generation <= 0xFFFF,
            "invalid target generation")
    return 1 if generation == 0xFFFF else generation + 1


def decode_profile(profile_hex):
    try:
        raw = bytes.fromhex(profile_hex)
    except (TypeError, ValueError) as error:
        raise ValueError("condition controller: invalid profile bytes") from error
    require(len(raw) == 144, "resolved profile size differs")
    return {
        "chillState": raw[0],
        "chillSpeed": raw[7],
        "chillAction": raw[12],
        "chillTarget": raw[13],
        "hopMinDistance": raw[20],
        "hopMaxDistance": raw[21],
        "hopTime": raw[36],
    }


def expected_profile():
    return {
        "chillState": BEHAVIOR_CHASE,
        "chillAction": LOCOMOTION_HOP,
        "chillTarget": TARGET_TOWARD,
        "hopMinDistance": 1,
        "hopMaxDistance": 2,
        "hopTime": HOP_DURATION,
    }


def copied(value):
    return deepcopy(value)
