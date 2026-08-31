"""Descriptor-driven host observation for the resident overworld actor system."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path
from typing import Any, Callable

from tools.overworld.trace import (
    HEADER as TRACE_HEADER,
    RECORD as TRACE_RECORD,
    TRACE_CAPACITY,
    TRACE_MAGIC,
    TRACE_VERSION,
    decode_trace_bytes,
)
from tools.overworld.validation import (
    ACTOR_SEMANTIC_CHECKS,
    ValidationFailure,
    load_json_document,
)


EVIDENCE_SCHEMA_VERSION = 2
DESCRIPTOR_FORMAT_VERSION = 2

ACTOR_STATE_KEYS = {
    "version",
    "size",
    "handle",
    "subjectIdentity",
    "behaviorFingerprint",
    "matchedLayerMask",
    "lastCommandSequence",
    "commitSequence",
    "authorityGeneration",
    "engineAnchorGeneration",
    "presentationGeneration",
    "logical",
    "render",
    "origin",
    "target",
    "motionElapsed",
    "motionDuration",
    "reservationId",
    "species",
    "form",
    "level",
    "roleId",
    "role",
    "laneId",
    "lane",
    "motionKindId",
    "motionKind",
    "motionPhaseId",
    "motionPhase",
    "inputOwnership",
    "streamState",
    "controllerState",
    "lastIntent",
    "lastDecision",
    "lastCancelReason",
    "active",
    "presentationAttached",
    "index",
}
HANDLE_KEYS = {
    "value",
    "slot",
    "generation",
    "fieldEpoch",
    "mapGeneration",
    "encounterGeneration",
}
POSITION_KEYS = ("logical", "render", "origin", "target")
STRING_ACTOR_KEYS = ("role", "lane", "motionKind", "motionPhase")
BOOLEAN_ACTOR_KEYS = ("active", "presentationAttached")
SIGNED_POSITION_LIMITS = (-0x8000, 0x7FFF)
TRACE_CHECK_EVENTS = {
    "terminal-result": {
        "MOTION_STARTED",
        "MOTION_FINISHED",
        "MOTION_CANCELED",
        "ACTOR_DETACHED",
    },
    "no-commit-after-cancel": {
        "MOTION_STARTED",
        "MOTION_CANCELED",
        "LOGICAL_COMMIT",
    },
    "control-returned": {
        "MOTION_FINISHED",
        "MOTION_CANCELED",
        "ACTOR_DETACHED",
        "CONTROL_RETURNED",
    },
}


def _require_int(value: Any, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValidationFailure(f"{label} must be an integer >= {minimum}")
    return value


def _require_bounded_int(
    value: Any, label: str, minimum: int, maximum: int
) -> int:
    result = _require_int(value, label, minimum) if minimum >= 0 else value
    if (
        isinstance(result, bool)
        or not isinstance(result, int)
        or not minimum <= result <= maximum
    ):
        raise ValidationFailure(
            f"{label} must be an integer between {minimum} and {maximum}"
        )
    return result


def _file_identity(path: Path) -> dict[str, Any]:
    try:
        data = path.read_bytes()
    except FileNotFoundError as error:
        raise ValidationFailure(f"provenance file is missing: {path}") from error
    return {
        "path": path.name,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def build_evidence_provenance(
    *,
    scenario_id: str,
    rom: Path | None,
    save: Path | None,
    seed: int,
) -> dict[str, Any]:
    """Create explicit fixture identity for reusable scenario evidence."""

    if not scenario_id:
        raise ValidationFailure("scenario provenance needs a scenario id")
    _require_bounded_int(seed, "scenario provenance seed", 0, 0xFFFFFFFF)
    return {
        "scenarioId": scenario_id,
        "seed": seed,
        "rom": _file_identity(rom) if rom is not None else None,
        "save": _file_identity(save) if save is not None else None,
    }


def load_debug_descriptor(path: Path) -> dict[str, Any]:
    descriptor = load_json_document(path)
    if (
        not isinstance(descriptor, dict)
        or descriptor.get("formatVersion") != DESCRIPTOR_FORMAT_VERSION
    ):
        raise ValidationFailure(f"{path}: unsupported actor debug descriptor")
    for key in (
        "overlay",
        "facade",
        "state",
        "capacities",
        "structures",
        "publicLayouts",
        "enums",
    ):
        if not isinstance(descriptor.get(key), dict):
            raise ValidationFailure(f"{path}: missing descriptor section: {key}")
    state = descriptor["state"]
    offsets = state.get("offsets")
    if not isinstance(offsets, dict):
        raise ValidationFailure(f"{path}: state offsets are missing")
    for key in ("actors", "traceHeader", "traceEvents"):
        _require_int(offsets.get(key), f"{path}: state.offsets.{key}")
    layouts = descriptor["publicLayouts"]
    for name in ("handle", "actorState"):
        layout = layouts.get(name)
        if not isinstance(layout, dict) or set(layout) != {"format", "size"}:
            raise ValidationFailure(f"{path}: public layout is missing: {name}")
        try:
            calculated_size = struct.calcsize(layout["format"])
        except (TypeError, struct.error) as error:
            raise ValidationFailure(f"{path}: invalid public layout: {name}") from error
        if calculated_size != layout["size"]:
            raise ValidationFailure(f"{path}: public layout size differs: {name}")
        if descriptor["structures"].get(name) != layout["size"]:
            raise ValidationFailure(f"{path}: public layout and structure differ: {name}")
    actor_state_size = layouts["actorState"]["size"]
    if descriptor["structures"].get("traceHeader") != 36:
        raise ValidationFailure(f"{path}: public trace header size is not 36")
    if descriptor["structures"].get("traceEvent") != 32:
        raise ValidationFailure(f"{path}: public trace event size is not 32")
    _require_int(state.get("address"), f"{path}: state.address", 1)
    _require_int(state.get("actorStride"), f"{path}: state.actorStride", actor_state_size)
    _require_int(descriptor["capacities"].get("actors"), f"{path}: capacities.actors", 1)
    trace_capacity = _require_int(
        descriptor["capacities"].get("traceEvents"),
        f"{path}: capacities.traceEvents",
        1,
    )
    if trace_capacity != 32:
        raise ValidationFailure(f"{path}: public trace capacity is not 32")
    if descriptor["facade"].get("version") != 1:
        raise ValidationFailure(f"{path}: unsupported public actor facade")
    return descriptor


class MemoryImage:
    """One address-based view over a raw emulator or actor-state dump."""

    def __init__(self, data: bytes, base_address: int):
        self.data = data
        self.base_address = base_address

    def read(self, address: int, size: int) -> bytes:
        start = address - self.base_address
        end = start + size
        if start < 0 or end > len(self.data):
            raise ValidationFailure(
                f"memory capture does not contain 0x{address:08X}..0x{end + self.base_address:08X}"
            )
        return self.data[start:end]


def configure_runtime_trace(
    read: Callable[[int, int], bytes],
    write: Callable[[int, bytes], None],
    descriptor: dict[str, Any],
    *,
    event_mask: int = 0,
    frame_budget: int = 0xFFFF,
    actor: dict[str, int] | None = None,
) -> None:
    """Arm one bounded trace while a live emulator is paused between frames."""

    _require_bounded_int(event_mask, "trace event mask", 0, 0xFFFFFFFF)
    _require_bounded_int(frame_budget, "trace frame budget", 1, 0xFFFF)
    state = descriptor["state"]
    offsets = state["offsets"]
    header_address = state["address"] + offsets["traceHeader"]
    event_address = state["address"] + offsets["traceEvents"]
    current = TRACE_HEADER.unpack(read(header_address, TRACE_HEADER.size))
    if current[:3] != (TRACE_MAGIC, TRACE_VERSION, TRACE_HEADER.size):
        raise ValidationFailure("live trace header differs from its public descriptor")
    actor_slot = 0xFFFF
    actor_generation = 0
    if actor is not None:
        actor_slot = _require_bounded_int(
            actor.get("slot"), "trace actor slot", 0, descriptor["capacities"]["actors"] - 1
        )
        actor_generation = _require_bounded_int(
            actor.get("generation"), "trace actor generation", 1, 0xFFFF
        )
    write(event_address, bytes(TRACE_CAPACITY * TRACE_RECORD.size))
    write(
        header_address,
        TRACE_HEADER.pack(
            TRACE_MAGIC,
            TRACE_VERSION,
            TRACE_HEADER.size,
            1,
            1,
            0,
            event_mask,
            current[7],
            actor_slot,
            actor_generation,
            frame_budget,
            0,
            0,
            1,
            0,
        ),
    )


def finish_runtime_trace(
    read: Callable[[int, int], bytes],
    write: Callable[[int, bytes], None],
    descriptor: dict[str, Any],
) -> None:
    """Close an armed live trace window before evidence capture."""

    state = descriptor["state"]
    header_address = state["address"] + state["offsets"]["traceHeader"]
    values = list(TRACE_HEADER.unpack(read(header_address, TRACE_HEADER.size)))
    if tuple(values[:3]) != (TRACE_MAGIC, TRACE_VERSION, TRACE_HEADER.size):
        raise ValidationFailure("live trace header differs from its public descriptor")
    values[10] = 0
    values[13] = 0
    write(header_address, TRACE_HEADER.pack(*values))


def _enum_name(
    descriptor: dict[str, Any], enum_name: str, value: int, prefix: str
) -> str:
    values = descriptor["enums"].get(enum_name, {})
    if not isinstance(values, dict):
        return f"{prefix}_{value}"
    for name, enum_value in values.items():
        if enum_value == value:
            return name.removeprefix(prefix + "_")
    return f"{prefix}_{value}"


def _decode_handle(values: tuple[int, ...]) -> dict[str, int]:
    slot, generation, field_epoch, map_generation, encounter_generation, _ = values
    return {
        "value": (generation << 16) | slot,
        "slot": slot,
        "generation": generation,
        "fieldEpoch": field_epoch,
        "mapGeneration": map_generation,
        "encounterGeneration": encounter_generation,
    }


def decode_actor_state(data: bytes, descriptor: dict[str, Any]) -> dict[str, Any]:
    actor_layout = descriptor["publicLayouts"]["actorState"]
    actor_state = struct.Struct(actor_layout["format"])
    if len(data) != actor_state.size:
        raise ValidationFailure("actor snapshot byte count differs from its public ABI")
    values = actor_state.unpack(data)
    version, size = values[:2]
    flags = values[28:44]
    inactive_zero = version == 0 and size == 0 and flags[12] == 0
    if not inactive_zero and (version != 1 or size != actor_state.size):
        raise ValidationFailure(
            f"actor snapshot header differs: version={version} size={size}"
        )
    handle = _decode_handle(values[2:8])
    integers = values[8:16]
    positions = values[16:24]
    shorts = values[24:28]
    role_id, lane_id, motion_kind_id, motion_phase_id = flags[2:6]
    return {
        "version": version,
        "size": size,
        "handle": handle,
        "subjectIdentity": integers[0],
        "behaviorFingerprint": integers[1],
        "matchedLayerMask": integers[2],
        "lastCommandSequence": integers[3],
        "commitSequence": integers[4],
        "authorityGeneration": integers[5],
        "engineAnchorGeneration": integers[6],
        "presentationGeneration": integers[7],
        "logical": {"x": positions[0], "y": positions[1]},
        "render": {"x": positions[2], "y": positions[3]},
        "origin": {"x": positions[4], "y": positions[5]},
        "target": {"x": positions[6], "y": positions[7]},
        "motionElapsed": shorts[0],
        "motionDuration": shorts[1],
        "reservationId": shorts[2],
        "species": shorts[3],
        "form": flags[0],
        "level": flags[1],
        "roleId": role_id,
        "role": _enum_name(
            descriptor, "OverworldActorRole", role_id, "OVERWORLD_ACTOR_ROLE"
        ),
        "laneId": lane_id,
        "lane": _enum_name(
            descriptor, "BehaviorResolutionLane", lane_id, "BEHAVIOR_RESOLUTION_LANE"
        ),
        "motionKindId": motion_kind_id,
        "motionKind": _enum_name(
            descriptor,
            "OverworldActorMotionKind",
            motion_kind_id,
            "OVERWORLD_ACTOR_MOTION",
        ),
        "motionPhaseId": motion_phase_id,
        "motionPhase": _enum_name(
            descriptor,
            "OverworldActorMotionPhase",
            motion_phase_id,
            "OVERWORLD_ACTOR_PHASE",
        ),
        "inputOwnership": flags[6],
        "streamState": flags[7],
        "controllerState": flags[8],
        "lastIntent": flags[9],
        "lastDecision": flags[10],
        "lastCancelReason": flags[11],
        "active": bool(flags[12]),
        "presentationAttached": bool(flags[13]),
    }


def capture_observation(
    read: Callable[[int, int], bytes],
    descriptor: dict[str, Any],
    trace_schema: dict[str, Any],
    *,
    include_inactive: bool = False,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Capture public snapshots and the semantic trace through a memory reader."""

    state = descriptor["state"]
    offsets = state["offsets"]
    state_address = state["address"]
    stride = state["actorStride"]
    actor_state_size = descriptor["publicLayouts"]["actorState"]["size"]
    actors = []
    for index in range(descriptor["capacities"]["actors"]):
        address = state_address + offsets["actors"] + index * stride
        actor = decode_actor_state(read(address, actor_state_size), descriptor)
        actor["index"] = index
        if actor["active"] or include_inactive:
            actors.append(actor)

    header_size = descriptor["structures"]["traceHeader"]
    event_size = descriptor["structures"]["traceEvent"]
    trace_capacity = descriptor["capacities"]["traceEvents"]
    trace_bytes = read(state_address + offsets["traceHeader"], header_size)
    trace_bytes += read(
        state_address + offsets["traceEvents"], event_size * trace_capacity
    )
    trace = decode_trace_bytes(trace_bytes, trace_schema)
    field_epoch = int.from_bytes(
        read(state_address + offsets["fieldEpoch"], 2), "little"
    )
    evidence = {
        "schemaVersion": EVIDENCE_SCHEMA_VERSION,
        "descriptor": {
            "formatVersion": descriptor["formatVersion"],
            "facadeVersion": descriptor["facade"]["version"],
            "overlaySha256": descriptor["overlay"]["sha256"],
            "stateAddress": state_address,
            "actorStride": stride,
        },
        "observation": {
            "fieldEpoch": field_epoch,
            "actors": actors,
            "trace": trace,
        },
    }
    if provenance is not None:
        evidence["provenance"] = provenance
    return evidence


def capture_memory_file(
    path: Path,
    base_address: int,
    descriptor: dict[str, Any],
    trace_schema: dict[str, Any],
    *,
    include_inactive: bool = False,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    image = MemoryImage(path.read_bytes(), base_address)
    evidence = capture_observation(
        image.read,
        descriptor,
        trace_schema,
        include_inactive=include_inactive,
        provenance=provenance,
    )
    evidence["capture"] = {
        "path": path.name,
        "baseAddress": base_address,
        "size": len(image.data),
        "sha256": hashlib.sha256(image.data).hexdigest(),
    }
    return evidence


def _validate_file_identity(value: Any, label: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"path", "size", "sha256"}:
        raise ValidationFailure(f"{label} file identity keys differ")
    if not isinstance(value["path"], str) or not value["path"]:
        raise ValidationFailure(f"{label}.path must be a non-empty string")
    _require_int(value["size"], f"{label}.size")
    digest = value["sha256"]
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValidationFailure(f"{label}.sha256 must be a lowercase SHA-256")
    return value


def _validate_provenance(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "scenarioId",
        "seed",
        "rom",
        "save",
    }:
        raise ValidationFailure(f"{label} keys differ")
    if not isinstance(value["scenarioId"], str) or not value["scenarioId"]:
        raise ValidationFailure(f"{label}.scenarioId must be a non-empty string")
    _require_bounded_int(value["seed"], f"{label}.seed", 0, 0xFFFFFFFF)
    _validate_file_identity(value["rom"], f"{label}.rom")
    _validate_file_identity(value["save"], f"{label}.save")
    return value


def _validate_actor(actor: Any, index: int, path: Path) -> dict[str, Any]:
    label = f"{path}: actor snapshot {index}"
    if not isinstance(actor, dict) or set(actor) != ACTOR_STATE_KEYS:
        raise ValidationFailure(f"{label} keys differ")
    handle = actor["handle"]
    if not isinstance(handle, dict) or set(handle) != HANDLE_KEYS:
        raise ValidationFailure(f"{label} handle keys differ")
    for key in HANDLE_KEYS:
        maximum = 0xFFFFFFFF if key == "value" else 0xFFFF
        _require_bounded_int(handle[key], f"{label}.handle.{key}", 0, maximum)
    expected_handle = (handle["generation"] << 16) | handle["slot"]
    if handle["value"] != expected_handle:
        raise ValidationFailure(f"{label} handle value differs from slot/generation")

    for key in POSITION_KEYS:
        position = actor[key]
        if not isinstance(position, dict) or set(position) != {"x", "y"}:
            raise ValidationFailure(f"{label}.{key} keys differ")
        for axis in ("x", "y"):
            _require_bounded_int(
                position[axis],
                f"{label}.{key}.{axis}",
                SIGNED_POSITION_LIMITS[0],
                SIGNED_POSITION_LIMITS[1],
            )

    for key in BOOLEAN_ACTOR_KEYS:
        if not isinstance(actor[key], bool):
            raise ValidationFailure(f"{label}.{key} must be a boolean")
    for key in STRING_ACTOR_KEYS:
        if not isinstance(actor[key], str) or not actor[key]:
            raise ValidationFailure(f"{label}.{key} must be a non-empty string")

    nonnegative_keys = ACTOR_STATE_KEYS.difference(
        {"handle", *POSITION_KEYS, *BOOLEAN_ACTOR_KEYS, *STRING_ACTOR_KEYS}
    )
    for key in sorted(nonnegative_keys):
        _require_int(actor[key], f"{label}.{key}")
    if (actor["active"] or actor["version"] != 0) and actor["index"] != handle["slot"]:
        raise ValidationFailure(f"{label} index differs from handle slot")
    return actor


def load_evidence(path: Path, trace_schema: dict[str, Any]) -> dict[str, Any]:
    document = load_json_document(path)
    allowed_keys = {
        "schemaVersion",
        "descriptor",
        "observation",
        "capture",
        "provenance",
    }
    if (
        not isinstance(document, dict)
        or document.get("schemaVersion") != EVIDENCE_SCHEMA_VERSION
        or not set(document).issubset(allowed_keys)
        or not {"schemaVersion", "descriptor", "observation"}.issubset(document)
    ):
        raise ValidationFailure(f"{path}: unsupported actor evidence")
    descriptor_identity = document.get("descriptor")
    if not isinstance(descriptor_identity, dict) or set(descriptor_identity) != {
        "formatVersion",
        "facadeVersion",
        "overlaySha256",
        "stateAddress",
        "actorStride",
    }:
        raise ValidationFailure(f"{path}: descriptor identity keys differ")
    if "capture" in document:
        capture = document["capture"]
        if not isinstance(capture, dict) or set(capture) != {
            "path",
            "baseAddress",
            "size",
            "sha256",
        }:
            raise ValidationFailure(f"{path}: capture identity keys differ")
        _validate_file_identity(
            {
                "path": capture["path"],
                "size": capture["size"],
                "sha256": capture["sha256"],
            },
            f"{path}: capture",
        )
        _require_int(capture["baseAddress"], f"{path}: capture.baseAddress")
    if "provenance" in document:
        _validate_provenance(document["provenance"], f"{path}: provenance")
    observation = document.get("observation")
    if not isinstance(observation, dict) or set(observation) != {
        "fieldEpoch",
        "actors",
        "trace",
    }:
        raise ValidationFailure(f"{path}: observation keys differ")
    actors = observation["actors"]
    if not isinstance(actors, list):
        raise ValidationFailure(f"{path}: actor snapshots are missing")
    seen_indexes: set[int] = set()
    seen_handles: set[int] = set()
    for index, actor in enumerate(actors):
        parsed = _validate_actor(actor, index, path)
        if parsed["index"] in seen_indexes:
            raise ValidationFailure(f"{path}: actor indexes are not unique")
        if parsed["active"] and parsed["handle"]["value"] in seen_handles:
            raise ValidationFailure(f"{path}: active actor handles are not unique")
        seen_indexes.add(parsed["index"])
        if parsed["active"]:
            seen_handles.add(parsed["handle"]["value"])

    trace = observation["trace"]
    if not isinstance(trace, dict) or not isinstance(trace.get("events"), list):
        raise ValidationFailure(f"{path}: semantic trace is missing")
    numeric_event_keys = {
        "sequence",
        "frame",
        "actorHandle",
        "actor",
        "eventId",
        "reasonId",
        "valueA",
        "valueB",
    }
    raw_events = []
    for index, event in enumerate(trace["events"]):
        if not isinstance(event, dict) or set(event) not in (
            numeric_event_keys,
            numeric_event_keys | {"event", "reason"},
        ):
            raise ValidationFailure(f"{path}: trace event {index} has invalid keys")
        raw_events.append({key: event[key] for key in numeric_event_keys})
    raw_trace = {**trace, "events": raw_events}
    observation["trace"] = decode_trace_bytes(
        json.dumps(raw_trace, separators=(",", ":")).encode(), trace_schema
    )
    field_epoch = _require_bounded_int(
        observation["fieldEpoch"], f"{path}: fieldEpoch", 0, 0xFFFF
    )
    if observation["trace"]["header"]["fieldEpoch"] != field_epoch:
        raise ValidationFailure(f"{path}: snapshot and trace field epochs differ")
    return document


def require_descriptor_identity(
    evidence: dict[str, Any], descriptor: dict[str, Any]
) -> None:
    expected = {
        "formatVersion": descriptor["formatVersion"],
        "facadeVersion": descriptor["facade"]["version"],
        "overlaySha256": descriptor["overlay"]["sha256"],
        "stateAddress": descriptor["state"]["address"],
        "actorStride": descriptor["state"]["actorStride"],
    }
    if evidence["descriptor"] != expected:
        raise ValidationFailure(
            "actor evidence was captured with a different runtime descriptor"
        )
    actor_capacity = descriptor["capacities"]["actors"]
    for actor in evidence["observation"]["actors"]:
        if actor["index"] >= actor_capacity:
            raise ValidationFailure("actor evidence contains an out-of-range actor index")
        expected_names = {
            "role": _enum_name(
                descriptor,
                "OverworldActorRole",
                actor["roleId"],
                "OVERWORLD_ACTOR_ROLE",
            ),
            "lane": _enum_name(
                descriptor,
                "BehaviorResolutionLane",
                actor["laneId"],
                "BEHAVIOR_RESOLUTION_LANE",
            ),
            "motionKind": _enum_name(
                descriptor,
                "OverworldActorMotionKind",
                actor["motionKindId"],
                "OVERWORLD_ACTOR_MOTION",
            ),
            "motionPhase": _enum_name(
                descriptor,
                "OverworldActorMotionPhase",
                actor["motionPhaseId"],
                "OVERWORLD_ACTOR_PHASE",
            ),
        }
        for key, expected_name in expected_names.items():
            if actor[key] != expected_name:
                raise ValidationFailure(
                    f"actor evidence {key} name differs from its descriptor id"
                )


def require_scenario_provenance(
    evidence: dict[str, Any], scenario: dict[str, Any], repo: Path
) -> None:
    provenance = evidence.get("provenance")
    if provenance is None:
        raise ValidationFailure("actor scenario evidence has no explicit provenance")
    _validate_provenance(provenance, "actor evidence provenance")
    if provenance["scenarioId"] != scenario["id"]:
        raise ValidationFailure("actor evidence belongs to a different scenario")
    fixture = scenario["fixture"]
    if provenance["seed"] != fixture["seed"]:
        raise ValidationFailure("actor evidence seed differs from the scenario fixture")

    expected_rom = (
        _file_identity(repo / fixture["rom"]) if fixture["rom"] is not None else None
    )
    save_fixture = fixture["save"]
    expected_save = (
        _file_identity(repo / save_fixture["path"])
        if save_fixture is not None
        else None
    )
    for name, expected in (("rom", expected_rom), ("save", expected_save)):
        actual = provenance[name]
        if (actual is None) != (expected is None):
            raise ValidationFailure(
                f"actor evidence {name} provenance differs from the scenario fixture"
            )
        if actual is not None and (
            actual["size"] != expected["size"]
            or actual["sha256"] != expected["sha256"]
        ):
            raise ValidationFailure(
                f"actor evidence {name} hash differs from the scenario fixture"
            )


def _actor_event_windows(events: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    windows: dict[int, list[dict[str, Any]]] = {}
    for event in events:
        windows.setdefault(event["actorHandle"], []).append(event)
    return windows


def _motion_windows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for handle, actor_events in _actor_event_windows(events).items():
        actor_events = sorted(actor_events, key=lambda event: event["sequence"])
        starts = [
            index
            for index, event in enumerate(actor_events)
            if event["event"] == "MOTION_STARTED"
        ]
        previous_terminal = -1
        for position, start in enumerate(starts):
            stop = starts[position + 1] if position + 1 < len(starts) else len(actor_events)
            window_events = actor_events[previous_terminal + 1 : stop]
            terminals = [
                event
                for event in actor_events[start:stop]
                if event["event"] in (
                    "MOTION_FINISHED",
                    "MOTION_CANCELED",
                    "ACTOR_DETACHED",
                )
            ]
            result.append(
                {
                    "actorHandle": handle,
                    "startSequence": actor_events[start]["sequence"],
                    "events": window_events,
                    "terminalCount": len(terminals),
                }
            )
            if terminals:
                terminal_sequence = terminals[-1]["sequence"]
                previous_terminal = next(
                    index
                    for index, event in enumerate(actor_events)
                    if event["sequence"] == terminal_sequence
                )
    return result


def _missing_ordered_events(
    events: list[dict[str, Any]], required: list[str]
) -> list[str]:
    cursor = 0
    missing: list[str] = []
    for name in required:
        while cursor < len(events) and events[cursor]["event"] != name:
            cursor += 1
        if cursor == len(events):
            missing.append(name)
        else:
            cursor += 1
    return missing


def _select_motion_window(
    events: list[dict[str, Any]],
    required: list[str],
    forbidden: list[str],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    candidates = []
    examined = []
    for window in _motion_windows(events):
        missing = _missing_ordered_events(window["events"], required)
        present_forbidden = sorted(
            {
                event["event"]
                for event in window["events"]
                if event["event"] in forbidden
            }
        )
        summary = {
            "actorHandle": window["actorHandle"],
            "startSequence": window["startSequence"],
            "terminalCount": window["terminalCount"],
            "missingRequiredEvents": missing,
            "presentForbiddenEvents": present_forbidden,
        }
        examined.append(summary)
        if window["terminalCount"] == 1 and not missing and not present_forbidden:
            candidates.append(window)
    if len(candidates) == 1:
        selected = candidates[0]
        return selected, {
            "passed": True,
            "actorHandle": selected["actorHandle"],
            "startSequence": selected["startSequence"],
            "candidateCount": 1,
        }
    return None, {
        "passed": False,
        "candidateCount": len(candidates),
        "detail": "no unique complete motion window matched the ordered contract",
        "examined": examined,
    }


def _trace_completeness(
    trace: dict[str, Any],
    selected: dict[str, Any],
    checks: list[str],
    required: list[str],
    forbidden: list[str],
    trace_schema: dict[str, Any],
) -> tuple[bool, str]:
    header = trace["header"]
    failures = []
    if header["count"] == 0:
        failures.append("empty trace")
    if header["overwrittenCount"] != 0 or header["oldestSequence"] != 1:
        failures.append("trace was not clear for the complete window")
    if header["armed"] != 0 or header["filterFramesRemaining"] != 0:
        failures.append("bounded trace window has not finished")

    needed_events = set(required) | set(forbidden)
    for check in checks:
        needed_events.update(TRACE_CHECK_EVENTS.get(check, ()))
    event_ids = {name: int(value) for value, name in trace_schema["events"].items()}
    missing_schema = sorted(name for name in needed_events if name not in event_ids)
    if missing_schema:
        failures.append("trace schema lacks events: " + ", ".join(missing_schema))
    mask = header["filterEventMask"]
    if mask != 0:
        excluded = sorted(
            name
            for name in needed_events
            if name in event_ids and (mask & (1 << event_ids[name])) == 0
        )
        if excluded:
            failures.append("trace filter excluded events: " + ", ".join(excluded))

    selected_event = next(
        event
        for event in selected["events"]
        if event["sequence"] == selected["startSequence"]
    )
    actor_filter = header["filterActor"]
    if actor_filter["slot"] != 0xFFFF and (
        actor_filter["slot"] != selected_event["actor"]["slot"]
        or actor_filter["generation"] != selected_event["actor"]["generation"]
    ):
        failures.append("trace actor filter differs from the selected actor")
    return not failures, "; ".join(failures) if failures else "complete bounded trace"


def evaluate_semantic_checks(
    evidence: dict[str, Any],
    checks: list[str],
    selected: dict[str, Any],
    required: list[str],
    forbidden: list[str],
    trace_schema: dict[str, Any],
) -> list[dict[str, Any]]:
    observation = evidence["observation"]
    actors = observation["actors"]
    trace = observation["trace"]
    events = selected["events"]
    results: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        results.append({"check": name, "passed": passed, "detail": detail})

    for check in checks:
        if check not in ACTOR_SEMANTIC_CHECKS:
            raise ValidationFailure(f"unknown actor semantic check: {check}")
        if check == "trace-window-complete":
            passed, detail = _trace_completeness(
                trace,
                selected,
                checks,
                required,
                forbidden,
                trace_schema,
            )
            add(check, passed, detail)
        elif check == "field-epoch-current":
            stale = [
                actor["index"]
                for actor in actors
                if actor["active"]
                and actor["handle"]["fieldEpoch"] != observation["fieldEpoch"]
            ]
            add(check, not stale, f"staleActorIndexes={stale}")
        elif check == "presentation-attached":
            missing = [
                actor["index"]
                for actor in actors
                if actor["active"] and not actor["presentationAttached"]
            ]
            add(check, not missing, f"missingActorIndexes={missing}")
        elif check == "single-motion-owner":
            reservations = [
                actor["reservationId"]
                for actor in actors
                if actor["active"]
                and actor["motionKind"] != "NONE"
                and actor["reservationId"] != 0
            ]
            duplicates = sorted(
                {
                    reservation
                    for reservation in reservations
                    if reservations.count(reservation) > 1
                }
            )
            add(
                check,
                not duplicates,
                f"duplicateActiveReservationIds={duplicates}",
            )
        elif check == "no-commit-after-cancel":
            failures = []
            canceled = False
            for event in events:
                if event["event"] == "MOTION_STARTED":
                    canceled = False
                elif event["event"] == "MOTION_CANCELED":
                    canceled = True
                elif canceled and event["event"] == "LOGICAL_COMMIT":
                    failures.append(event["sequence"])
            add(check, not failures, f"lateCommits={failures}")
        elif check == "terminal-result":
            starts = sum(event["event"] == "MOTION_STARTED" for event in events)
            terminals = sum(
                event["event"] in (
                    "MOTION_FINISHED",
                    "MOTION_CANCELED",
                    "ACTOR_DETACHED",
                )
                for event in events
            )
            add(
                check,
                starts == 1 and terminals == 1,
                f"starts={starts} terminals={terminals}",
            )
        elif check == "control-returned":
            terminal_sequence = next(
                (
                    event["sequence"]
                    for event in events
                    if event["event"] in (
                        "MOTION_FINISHED",
                        "MOTION_CANCELED",
                        "ACTOR_DETACHED",
                    )
                ),
                None,
            )
            detached = terminal_sequence is not None and any(
                event["event"] == "ACTOR_DETACHED"
                and event["sequence"] == terminal_sequence
                for event in events
            )
            returned = detached or (
                terminal_sequence is not None
                and any(
                    event["event"] == "CONTROL_RETURNED"
                    and event["sequence"] > terminal_sequence
                    for event in events
                )
            )
            add(
                check,
                returned,
                f"terminalSequence={terminal_sequence} controlReturned={returned}",
            )
    return results


def evaluate_scenario_evidence(
    scenario: dict[str, Any],
    evidence: dict[str, Any],
    trace_schema: dict[str, Any],
) -> dict[str, Any]:
    adapter = scenario["adapter"]
    events = evidence["observation"]["trace"]["events"]
    required = scenario["expect"]["requiredEvents"]
    forbidden = scenario["expect"]["forbiddenEvents"]
    selected, selection = _select_motion_window(events, required, forbidden)
    if selected is None:
        missing = required
        present_forbidden = []
        semantic = []
        passed = False
    else:
        missing = _missing_ordered_events(selected["events"], required)
        present_forbidden = sorted(
            {
                event["event"]
                for event in selected["events"]
                if event["event"] in forbidden
            }
        )
        semantic = evaluate_semantic_checks(
            evidence,
            adapter["checks"],
            selected,
            required,
            forbidden,
            trace_schema,
        )
        passed = not missing and not present_forbidden and all(
            item["passed"] for item in semantic
        )
    return {
        "passed": passed,
        "resultKind": "actor-observation",
        "motionWindow": selection,
        "missingRequiredEvents": missing,
        "presentForbiddenEvents": present_forbidden,
        "semanticChecks": semantic,
        "actorCount": len(evidence["observation"]["actors"]),
        "traceEventCount": len(events),
    }


def write_evidence(document: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
