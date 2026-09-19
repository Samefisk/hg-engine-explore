"""Descriptor-driven host observation for the resident overworld actor system."""

from __future__ import annotations

import copy
import hashlib
import json
import struct
from pathlib import Path
from typing import Any, Callable

from tools.overworld.trace import (
    HEADER as TRACE_HEADER,
    RECORD as TRACE_RECORD,
    TRACE_MAGIC,
    TRACE_VERSION,
    decode_trace_bytes,
)
from tools.overworld.validation import (
    ACTOR_SEMANTIC_CHECKS,
    EVENT_KINDS,
    ValidationFailure,
    load_json_document,
)


EVIDENCE_SCHEMA_VERSION = 2
EXECUTION_SCHEMA_VERSION = 2
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
    "presentationState",
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
    "target-reservation-serialized": {
        "PLAN_ACCEPTED",
        "CANDIDATE_REJECTED",
        "MOTION_FINISHED",
        "MOTION_CANCELED",
        "ACTOR_DETACHED",
    },
    "path-advances-before-commit": {
        "PATH_ADVANCED",
        "LOGICAL_COMMIT",
    },
    "mounted-presentation-coordinates-equal": {
        "MOTION_STARTED",
        "MOUNT_PRESENTATION_POSITION",
        "MOUNT_PRESENTATION_STATE",
    },
    "mounted-presentation-facing-locked": {
        "MOTION_STARTED",
        "MOUNT_PRESENTATION_POSITION",
        "MOUNT_PRESENTATION_STATE",
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


def _execution_sequence_digest(events: list[dict[str, Any]]) -> str:
    encoded = json.dumps(
        events, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _trace_event_digest(trace: dict[str, Any]) -> str:
    numeric_events = []
    for event in trace["events"]:
        numeric_events.append(
            {
                key: event[key]
                for key in (
                    "sequence",
                    "frame",
                    "actorHandle",
                    "actor",
                    "eventId",
                    "reasonId",
                    "valueA",
                    "valueB",
                )
            }
        )
    return _execution_sequence_digest(numeric_events)


def _trace_window_record(trace: dict[str, Any]) -> dict[str, Any]:
    header = trace["header"]
    return {
        "oldestSequence": header["oldestSequence"],
        "nextSequence": header["nextSequence"],
        "eventCount": header["count"],
        "fieldEpoch": header["fieldEpoch"],
        "eventsSha256": _trace_event_digest(trace),
    }


def build_execution_record(
    *,
    scenario_id: str,
    declared_events: list[dict[str, Any]],
    completed: bool,
    session: str,
    trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind one capture to its controller session and declared input contract."""

    record = {
        "schemaVersion": EXECUTION_SCHEMA_VERSION,
        "scenarioId": scenario_id,
        "session": session,
        "completed": completed,
        "declaredEvents": declared_events,
        "declarationSha256": _execution_sequence_digest(declared_events),
    }
    if trace is not None:
        record["traceWindow"] = _trace_window_record(trace)
    return _validate_execution_record(record, "execution record")


def _validate_execution_record(value: Any, label: str) -> dict[str, Any]:
    required_keys = {
        "schemaVersion",
        "scenarioId",
        "session",
        "completed",
        "declaredEvents",
        "declarationSha256",
    }
    allowed_keys = required_keys | {"traceWindow"}
    if (
        not isinstance(value, dict)
        or not required_keys.issubset(value)
        or not set(value).issubset(allowed_keys)
    ):
        raise ValidationFailure(f"{label} keys differ")
    if (
        isinstance(value["schemaVersion"], bool)
        or value["schemaVersion"] != EXECUTION_SCHEMA_VERSION
    ):
        raise ValidationFailure(f"{label} schemaVersion is unsupported")
    if not isinstance(value["scenarioId"], str) or not value["scenarioId"]:
        raise ValidationFailure(f"{label}.scenarioId must be a non-empty string")
    session = value["session"]
    if (
        not isinstance(session, str)
        or len(session) != 32
        or any(character not in "0123456789abcdef" for character in session)
    ):
        raise ValidationFailure(f"{label}.session must be a controller nonce")
    if not isinstance(value["completed"], bool):
        raise ValidationFailure(f"{label}.completed must be a boolean")
    events = value["declaredEvents"]
    if not isinstance(events, list):
        raise ValidationFailure(f"{label}.events must be an array")
    previous_at = -1
    for index, event in enumerate(events):
        event_label = f"{label}.events[{index}]"
        if not isinstance(event, dict) or set(event) != {"at", "kind", "value"}:
            raise ValidationFailure(f"{event_label} keys differ")
        at = _require_bounded_int(event["at"], f"{event_label}.at", 0, 0x7FFFFFFF)
        if at < previous_at:
            raise ValidationFailure(f"{label}.events must be ordered")
        previous_at = at
        if event["kind"] not in EVENT_KINDS:
            raise ValidationFailure(f"{event_label}.kind is unsupported")
        if not isinstance(event["value"], str) or not event["value"]:
            raise ValidationFailure(f"{event_label}.value must be a non-empty string")
    expected_digest = _execution_sequence_digest(events)
    if value["declarationSha256"] != expected_digest:
        raise ValidationFailure(
            f"{label}.declarationSha256 differs from its declaredEvents"
        )
    if "traceWindow" in value:
        window = value["traceWindow"]
        window_keys = {
            "oldestSequence",
            "nextSequence",
            "eventCount",
            "fieldEpoch",
            "eventsSha256",
        }
        if not isinstance(window, dict) or set(window) != window_keys:
            raise ValidationFailure(f"{label}.traceWindow keys differ")
        oldest = _require_bounded_int(
            window["oldestSequence"],
            f"{label}.traceWindow.oldestSequence",
            0,
            0xFFFFFFFF,
        )
        next_sequence = _require_bounded_int(
            window["nextSequence"],
            f"{label}.traceWindow.nextSequence",
            0,
            0xFFFFFFFF,
        )
        count = _require_bounded_int(
            window["eventCount"],
            f"{label}.traceWindow.eventCount",
            0,
            0xFFFF,
        )
        _require_bounded_int(
            window["fieldEpoch"], f"{label}.traceWindow.fieldEpoch", 0, 0xFFFF
        )
        if next_sequence < oldest or next_sequence - oldest != count:
            raise ValidationFailure(
                f"{label}.traceWindow sequence bounds differ from its event count"
            )
        digest = window["eventsSha256"]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValidationFailure(
                f"{label}.traceWindow.eventsSha256 must be a lowercase SHA-256"
            )
    return value


def _bind_execution_trace(
    execution: dict[str, Any], trace: dict[str, Any], label: str
) -> dict[str, Any]:
    validated = _validate_execution_record(execution, label)
    expected = _trace_window_record(trace)
    actual = validated.get("traceWindow")
    if actual is not None:
        bounds = ("oldestSequence", "nextSequence", "eventCount", "fieldEpoch")
        if any(actual[key] != expected[key] for key in bounds):
            raise ValidationFailure(f"{label} trace window differs from its capture")
        if actual["eventsSha256"] != expected["eventsSha256"]:
            raise ValidationFailure(f"{label} trace events differ from its capture")
        return validated
    return _validate_execution_record(
        {**validated, "traceWindow": expected}, label
    )


def load_execution_record(path: Path) -> dict[str, Any]:
    return _validate_execution_record(load_json_document(path), str(path))


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
    if descriptor.get("formatVersion") == 2:
        policy_size = _require_int(
            descriptor["structures"].get("actorPolicyState"),
            f"{path}: structures.actorPolicyState",
            1,
        )
        policy_offset = _require_int(
            state.get("actorPolicyOffset"),
            f"{path}: state.actorPolicyOffset",
            actor_state_size,
        )
        if policy_offset + policy_size > state["actorStride"]:
            raise ValidationFailure(f"{path}: actor policy exceeds its actor slot")
    _require_int(descriptor["capacities"].get("actors"), f"{path}: capacities.actors", 1)
    trace_capacity = _require_int(
        descriptor["capacities"].get("traceEvents"),
        f"{path}: capacities.traceEvents",
        1,
    )
    if trace_capacity > 256 or trace_capacity & (trace_capacity - 1) != 0:
        raise ValidationFailure(f"{path}: public trace capacity is invalid")
    if descriptor["facade"].get("version") != 1:
        raise ValidationFailure(f"{path}: unsupported public actor facade")
    return descriptor


def resolve_movement_policy_state(
    descriptor: dict[str, Any], slot: int
) -> dict[str, Any]:
    """Reject obsolete raw movement-policy state access."""

    services = descriptor.get("privateServices")
    if not isinstance(services, list):
        raise ValidationFailure("debug descriptor has no private service table")
    matches = [
        service
        for service in services
        if isinstance(service, dict) and service.get("name") == "movementPolicy"
    ]
    if len(matches) != 1:
        raise ValidationFailure(
            "debug descriptor must expose one movementPolicy service"
        )
    service = matches[0]
    if service.get("status") != "available" or service.get("version") != 4:
        raise ValidationFailure("movementPolicy service is not available at version 4")
    raise ValidationFailure(
        "movementPolicy version 4 keeps actor policy state private"
    )


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
    trace_capacity = descriptor["capacities"]["traceEvents"]
    write(event_address, bytes(trace_capacity * TRACE_RECORD.size))
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
        "presentationState": flags[14],
    }


def capture_observation(
    read: Callable[[int, int], bytes],
    descriptor: dict[str, Any],
    trace_schema: dict[str, Any],
    *,
    include_inactive: bool = False,
    provenance: dict[str, Any] | None = None,
    execution: dict[str, Any] | None = None,
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
    trace = decode_trace_bytes(trace_bytes, trace_schema, trace_capacity)
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
    if execution is not None:
        evidence["execution"] = _bind_execution_trace(
            execution, trace, "actor evidence execution"
        )
    return evidence


def capture_memory_file(
    path: Path,
    base_address: int,
    descriptor: dict[str, Any],
    trace_schema: dict[str, Any],
    *,
    include_inactive: bool = False,
    provenance: dict[str, Any] | None = None,
    execution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    image = MemoryImage(path.read_bytes(), base_address)
    evidence = capture_observation(
        image.read,
        descriptor,
        trace_schema,
        include_inactive=include_inactive,
        provenance=provenance,
        execution=execution,
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
        "execution",
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
    if "execution" in document:
        _validate_execution_record(document["execution"], f"{path}: execution")
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
    if "execution" in document:
        execution = document["execution"]
        if "traceWindow" not in execution:
            raise ValidationFailure(f"{path}: execution has no captured trace window")
        _bind_execution_trace(execution, observation["trace"], f"{path}: execution")
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
    evidence: dict[str, Any],
    scenario: dict[str, Any],
    repo: Path,
    expected_session: str,
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

    execution = evidence.get("execution")
    if execution is None:
        raise ValidationFailure(
            "actor scenario evidence has no completed input execution record"
        )
    _validate_execution_record(execution, "actor evidence execution")
    if not execution["completed"]:
        raise ValidationFailure("actor evidence input execution did not complete")
    if execution["scenarioId"] != scenario["id"]:
        raise ValidationFailure(
            "actor evidence execution belongs to a different scenario"
        )
    if execution["session"] != expected_session:
        raise ValidationFailure(
            "actor evidence belongs to a different controller session"
        )
    if execution["declaredEvents"] != scenario["events"]:
        raise ValidationFailure(
            "actor evidence input declaration differs from the scenario contract"
        )
    if "traceWindow" not in execution:
        raise ValidationFailure(
            "actor evidence execution has no captured trace window"
        )
    _bind_execution_trace(
        execution,
        evidence["observation"]["trace"],
        "actor evidence execution",
    )


def _actor_event_windows(
    events: list[dict[str, Any]],
) -> dict[tuple[int, int, int, int], list[dict[str, Any]]]:
    windows: dict[tuple[int, int, int, int], list[dict[str, Any]]] = {}
    for event in events:
        actor = event["actor"]
        identity = (
            event["actorHandle"],
            actor["fieldEpoch"],
            actor["mapGeneration"],
            actor["encounterGeneration"],
        )
        windows.setdefault(identity, []).append(event)
    return windows


def _motion_windows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for identity, actor_events in _actor_event_windows(events).items():
        handle, _, _, _ = identity
        actor_events = sorted(actor_events, key=lambda event: event["sequence"])
        starts = [
            index
            for index, event in enumerate(actor_events)
            if event["event"] == "MOTION_STARTED"
        ]
        terminals = [
            index
            for index, event in enumerate(actor_events)
            if event["event"] in (
                "MOTION_FINISHED",
                "MOTION_CANCELED",
                "ACTOR_DETACHED",
            )
        ]
        begins = []
        for start in starts:
            previous_terminal = next(
                (
                    index
                    for index in reversed(terminals)
                    if index < start
                ),
                -1,
            )
            begin = previous_terminal + 1
            while (
                begin < start
                and actor_events[begin]["event"] == "CONTROL_RETURNED"
            ):
                begin += 1
            begins.append(begin)
        for position, start in enumerate(starts):
            stop = (
                begins[position + 1]
                if position + 1 < len(starts)
                else len(actor_events)
            )
            window_events = actor_events[begins[position] : stop]
            window_terminals = [
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
                    "actorIdentity": actor_events[start]["actor"],
                    "startSequence": actor_events[start]["sequence"],
                    "events": window_events,
                    "terminalCount": len(window_terminals),
                }
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


def _integer_matches(value: int, matcher: dict[str, int]) -> bool:
    return (
        ("equals" not in matcher or value == matcher["equals"])
        and ("minimum" not in matcher or value >= matcher["minimum"])
        and ("maximum" not in matcher or value <= matcher["maximum"])
    )


def _event_matches(event: dict[str, Any], predicate: dict[str, Any]) -> bool:
    if event["event"] != predicate["event"]:
        return False
    if "reason" in predicate and event["reason"] != predicate["reason"]:
        return False
    return all(
        key not in predicate or _integer_matches(event[key], predicate[key])
        for key in ("valueA", "valueB")
    )


def _match_ordered_assertions(
    events: list[dict[str, Any]], assertions: list[dict[str, Any]]
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    cursor = 0
    matches: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for assertion in assertions:
        while cursor < len(events) and not _event_matches(events[cursor], assertion):
            cursor += 1
        if cursor == len(events):
            missing.append(assertion["id"])
        else:
            matches[assertion["id"]] = events[cursor]
            cursor += 1
    return matches, missing


def _select_motion_windows(
    events: list[dict[str, Any]],
    required: list[str],
    forbidden: list[str],
    ordered_assertions: list[dict[str, Any]],
    expected_count: int,
) -> tuple[list[dict[str, Any]] | None, dict[str, Any]]:
    candidates = []
    targeted = []
    examined = []
    start_predicates = [
        assertion
        for assertion in ordered_assertions
        if assertion["event"] == "MOTION_STARTED"
    ]
    for window in _motion_windows(events):
        start_event = next(
            event
            for event in window["events"]
            if event["sequence"] == window["startSequence"]
        )
        is_target = not start_predicates or all(
            _event_matches(start_event, predicate)
            for predicate in start_predicates
        )
        if is_target:
            targeted.append(window)
        missing = _missing_ordered_events(window["events"], required)
        _, missing_assertions = _match_ordered_assertions(
            window["events"], ordered_assertions
        )
        present_forbidden = sorted(
            {
                event["event"]
                for event in window["events"]
                if event["event"] in forbidden
            }
        )
        summary = {
            "actorHandle": window["actorHandle"],
            "actorIdentity": window["actorIdentity"],
            "startSequence": window["startSequence"],
            "terminalCount": window["terminalCount"],
            "missingRequiredEvents": missing,
            "missingOrderedEventAssertions": missing_assertions,
            "presentForbiddenEvents": present_forbidden,
        }
        examined.append(summary)
        if (
            is_target
            and window["terminalCount"] == 1
            and not missing
            and not missing_assertions
            and not present_forbidden
        ):
            candidates.append(window)
    if len(targeted) == expected_count and len(candidates) == expected_count:
        actor_identities = {
            (
                candidate["actorHandle"],
                candidate["actorIdentity"]["fieldEpoch"],
                candidate["actorIdentity"]["mapGeneration"],
                candidate["actorIdentity"]["encounterGeneration"],
            )
            for candidate in candidates
        }
        if len(actor_identities) != 1:
            return None, {
                "passed": False,
                "candidateCount": len(candidates),
                "targetCount": len(targeted),
                "expectedCount": expected_count,
                "detail": "matching motion windows do not belong to one actor identity",
                "examined": examined,
            }
        return candidates, {
            "passed": True,
            "actorHandle": candidates[0]["actorHandle"],
            "actorIdentity": candidates[0]["actorIdentity"],
            "startSequences": [
                candidate["startSequence"] for candidate in candidates
            ],
            "candidateCount": len(candidates),
            "targetCount": len(targeted),
            "expectedCount": expected_count,
        }
    return None, {
        "passed": False,
        "candidateCount": len(candidates),
        "targetCount": len(targeted),
        "expectedCount": expected_count,
        "detail": "complete matching motion-window count differs from the contract",
        "examined": examined,
    }


def _trace_completeness(
    trace: dict[str, Any],
    selected: dict[str, Any],
    checks: list[str],
    required: list[str],
    forbidden: list[str],
    asserted_events: set[str],
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

    needed_events = set(required) | set(forbidden) | asserted_events
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


def _mounted_presentation_sample_summary(
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    positions = [
        event
        for event in events
        if event["event"] == "MOUNT_PRESENTATION_POSITION"
    ]
    states = [
        event
        for event in events
        if event["event"] == "MOUNT_PRESENTATION_STATE"
    ]
    starts = [event for event in events if event["event"] == "MOTION_STARTED"]
    decoded_states = []
    for event in states:
        packed_faces = event["valueA"]
        packed_sample = event["valueB"]
        decoded_states.append(
            {
                "sequence": event["sequence"],
                "faces": [
                    (packed_faces >> shift) & 0xFF
                    for shift in (0, 8, 16, 24)
                ],
                "elapsed": (packed_sample >> 16) & 0xFFFF,
                "renderEqual": bool(packed_sample & (1 << 15)),
                "logicalEqual": bool(packed_sample & (1 << 14)),
                "duration": (packed_sample >> 8) & 0x3F,
                "motionKind": (packed_sample >> 4) & 0x0F,
                "expectedFacing": packed_sample & 0x0F,
            }
        )
    duration = starts[0]["valueB"] if len(starts) == 1 else None
    observed_elapsed = sorted(
        {
            sample["elapsed"]
            for sample in decoded_states
            if sample["elapsed"] != 0
        }
    )
    expected_elapsed = (
        list(range(1, duration + 1))
        if isinstance(duration, int) and 0 < duration <= 0x3F
        else []
    )
    return {
        "positions": positions,
        "states": decoded_states,
        "paired": len(positions) == len(states)
        and all(
            state["sequence"] == position["sequence"] + 1
            for position, state in zip(positions, decoded_states)
        ),
        "duration": duration,
        "elapsedComplete": bool(expected_elapsed)
        and observed_elapsed == expected_elapsed,
        "observedElapsed": observed_elapsed,
        "expectedElapsed": expected_elapsed,
    }


def evaluate_semantic_checks(
    evidence: dict[str, Any],
    checks: list[str],
    selected: dict[str, Any],
    required: list[str],
    forbidden: list[str],
    asserted_events: set[str],
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
                asserted_events,
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
        elif check == "mounted-presentation-coordinates-equal":
            samples = _mounted_presentation_sample_summary(events)
            positions = samples["positions"]
            states = samples["states"]
            passed = (
                bool(positions)
                and samples["paired"]
                and samples["elapsedComplete"]
                and all(
                    event["valueA"] == event["valueB"]
                    for event in positions
                )
                and all(
                    sample["logicalEqual"] and sample["renderEqual"]
                    for sample in states
                )
            )
            add(
                check,
                passed,
                "samples={} paired={} elapsed={}/{}".format(
                    len(positions),
                    samples["paired"],
                    samples["observedElapsed"],
                    samples["expectedElapsed"],
                ),
            )
        elif check == "mounted-presentation-facing-locked":
            samples = _mounted_presentation_sample_summary(events)
            states = samples["states"]
            expected_facings = {
                sample["expectedFacing"] for sample in states
            }
            passed = (
                bool(states)
                and samples["paired"]
                and samples["elapsedComplete"]
                and len(expected_facings) == 1
                and all(
                    sample["motionKind"] == 4
                    and sample["duration"] == samples["duration"]
                    and all(
                        facing == sample["expectedFacing"]
                        for facing in sample["faces"]
                    )
                    for sample in states
                )
            )
            add(
                check,
                passed,
                "samples={} expectedFacings={} elapsed={}/{}".format(
                    len(states),
                    sorted(expected_facings),
                    samples["observedElapsed"],
                    samples["expectedElapsed"],
                ),
            )
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
        elif check == "target-reservation-serialized":
            active_targets: dict[int, int] = {}
            overlaps = []
            reserved_rejections = 0
            for event in sorted(
                trace["events"], key=lambda item: item["sequence"]
            ):
                handle = event["actorHandle"]
                if event["event"] == "PLAN_ACCEPTED":
                    target = event["valueA"]
                    conflicts = [
                        owner for owner, owned_target in active_targets.items()
                        if owner != handle and owned_target == target
                    ]
                    if conflicts:
                        overlaps.append({
                            "sequence": event["sequence"],
                            "actorHandle": handle,
                            "target": target,
                            "owners": conflicts,
                        })
                    active_targets[handle] = target
                elif (
                    event["event"] == "CANDIDATE_REJECTED"
                    and event["reason"] == "REJECTED_RESERVED"
                ):
                    reserved_rejections += 1
                elif event["event"] in (
                    "MOTION_FINISHED", "MOTION_CANCELED", "ACTOR_DETACHED"
                ):
                    active_targets.pop(handle, None)
            add(
                check,
                not overlaps and reserved_rejections > 0,
                "reservedRejections={} overlaps={}".format(
                    reserved_rejections, overlaps
                ),
            )
        elif check == "path-advances-before-commit":
            advances = [
                event for event in events
                if event["event"] == "PATH_ADVANCED"
            ]
            commits = [
                event for event in events
                if event["event"] == "LOGICAL_COMMIT"
            ]
            advance_ranges = [
                ((event["valueA"] >> 16) & 0xFFFF,
                 event["valueA"] & 0xFFFF)
                for event in advances
            ]
            ordered_ranges = bool(advance_ranges) and all(
                first > 0
                and last >= first
                and (
                    index == 0
                    or first == advance_ranges[index - 1][1] + 1
                )
                for index, (first, last) in enumerate(advance_ranges)
            )
            ordered_before_commit = (
                len(commits) == 1
                and bool(advances)
                and advances[-1]["sequence"] < commits[0]["sequence"]
            )
            add(
                check,
                ordered_ranges and ordered_before_commit,
                "advanceRanges={} commitSequences={}".format(
                    advance_ranges,
                    [event["sequence"] for event in commits],
                ),
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
            returned = terminal_sequence is not None and any(
                event["event"] == "CONTROL_RETURNED"
                and event["sequence"] > terminal_sequence
                for event in events
            )
            add(
                check,
                returned,
                f"terminalSequence={terminal_sequence} controlReturned={returned}",
            )
    return results


def _evaluate_ordered_event_assertions(
    events: list[dict[str, Any]], assertions: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    matches, missing = _match_ordered_assertions(events, assertions)
    results = []
    for assertion in assertions:
        matched = matches.get(assertion["id"])
        results.append(
            {
                "id": assertion["id"],
                "event": assertion["event"],
                "passed": assertion["id"] not in missing,
                "matchedSequence": matched["sequence"] if matched is not None else None,
                "matchedFrame": matched["frame"] if matched is not None else None,
                "matchedReason": matched["reason"] if matched is not None else None,
                "matchedValueA": matched["valueA"] if matched is not None else None,
                "matchedValueB": matched["valueB"] if matched is not None else None,
            }
        )
    return results, matches


def _evaluate_event_count_assertions(
    events: list[dict[str, Any]], assertions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    results = []
    for index, assertion in enumerate(assertions):
        count = sum(_event_matches(event, assertion) for event in events)
        results.append(
            {
                "index": index,
                "event": assertion["event"],
                "minimum": assertion["minimum"],
                "maximum": assertion["maximum"],
                "actual": count,
                "passed": assertion["minimum"] <= count <= assertion["maximum"],
            }
        )
    return results


def _evaluate_frame_timing_assertions(
    matches: dict[str, dict[str, Any]], assertions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    results = []
    for assertion in assertions:
        start = matches.get(assertion["from"])
        finish = matches.get(assertion["to"])
        elapsed = (
            (finish["frame"] - start["frame"]) & 0xFFFFFFFF
            if start is not None and finish is not None
            else None
        )
        passed = (
            elapsed is not None
            and assertion["minimum"] <= elapsed <= assertion["maximum"]
        )
        results.append(
            {
                "from": assertion["from"],
                "to": assertion["to"],
                "minimum": assertion["minimum"],
                "maximum": assertion["maximum"],
                "actualFrames": elapsed,
                "passed": passed,
            }
        )
    return results


def _evaluate_subject_assertions(
    scenario: dict[str, Any],
    evidence: dict[str, Any],
    selection: dict[str, Any],
) -> list[dict[str, Any]]:
    actors = evidence["observation"]["actors"]
    field_epoch = evidence["observation"]["fieldEpoch"]
    results = []
    for subject in scenario.get("subjects", []):
        matches = []
        for actor in actors:
            handle = actor["handle"]
            identity_current = (
                actor["active"] is True
                and actor.get("subjectIdentity", 0) > 0
                and actor.get("authorityGeneration", 0) > 0
                and handle["generation"] > 0
                and handle["fieldEpoch"] == field_epoch
                and handle["mapGeneration"] > 0
                and handle["encounterGeneration"] > 0
                and handle["value"]
                    == ((handle["generation"] << 16) | handle["slot"])
            )
            if (
                identity_current
                and actor["species"] == subject["species"]
                and actor["role"] == subject["role"]
                and (
                    subject["role"] != "MOUNTED"
                    or actor.get("engineAnchorGeneration", 0) > 0
                )
                and (
                    not subject["requirePresentation"]
                    or (
                        actor["presentationAttached"] is True
                        and actor.get("presentationGeneration", 0) > 0
                        and actor.get("presentationState", 0) == 7
                    )
                )
            ):
                matches.append(actor)
        motion_match = True
        if subject["motionActor"]:
            selected_identity = selection.get("actorIdentity", {})
            motion_match = any(
                actor["handle"]["value"] == selection.get("actorHandle")
                and actor["handle"]["fieldEpoch"]
                    == selected_identity.get("fieldEpoch")
                and actor["handle"]["mapGeneration"]
                    == selected_identity.get("mapGeneration")
                and actor["handle"]["encounterGeneration"]
                    == selected_identity.get("encounterGeneration")
                for actor in matches
            )
        passed = (
            subject["minimum"] <= len(matches) <= subject["maximum"]
            and motion_match
        )
        results.append(
            {
                "id": subject["id"],
                "species": subject["species"],
                "role": subject["role"],
                "acquisition": subject["acquisition"],
                "minimum": subject["minimum"],
                "maximum": subject["maximum"],
                "actual": len(matches),
                "motionActor": subject["motionActor"],
                "motionActorMatched": motion_match,
                "actorHandles": [actor["handle"] for actor in matches],
                "passed": passed,
            }
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
    ordered_assertions = scenario["expect"].get("orderedEvents", [])
    count_assertions = scenario["expect"].get("eventCounts", [])
    timing_assertions = scenario["expect"].get("frameTiming", [])
    asserted_events = {
        assertion["event"]
        for assertion in (*ordered_assertions, *count_assertions)
    }
    expected_window_count = adapter.get("motionWindowCount", 1)
    selected_windows, selection = _select_motion_windows(
        events,
        required,
        forbidden,
        ordered_assertions,
        expected_window_count,
    )
    if selected_windows is None:
        missing = required
        present_forbidden = []
        semantic = []
        no_window = "the required motion-window set was not selected"
        ordered_results = [
            {
                "id": assertion["id"],
                "event": assertion["event"],
                "passed": False,
                "detail": no_window,
            }
            for assertion in ordered_assertions
        ]
        count_results = [
            {
                "index": index,
                "event": assertion["event"],
                "passed": False,
                "detail": no_window,
            }
            for index, assertion in enumerate(count_assertions)
        ]
        timing_results = [
            {
                "from": assertion["from"],
                "to": assertion["to"],
                "passed": False,
                "detail": no_window,
            }
            for assertion in timing_assertions
        ]
        passed = False
    else:
        missing = []
        present_forbidden = []
        semantic = []
        ordered_results = []
        count_results = []
        timing_results = []
        for window_index, selected in enumerate(selected_windows):
            missing.extend(
                _missing_ordered_events(selected["events"], required)
            )
            present_forbidden.extend(
                event["event"]
                for event in selected["events"]
                if event["event"] in forbidden
            )
            window_semantic = evaluate_semantic_checks(
                evidence,
                adapter["checks"],
                selected,
                required,
                forbidden,
                asserted_events,
                trace_schema,
            )
            window_ordered, ordered_matches = (
                _evaluate_ordered_event_assertions(
                    selected["events"], ordered_assertions
                )
            )
            window_counts = _evaluate_event_count_assertions(
                selected["events"], count_assertions
            )
            window_timing = _evaluate_frame_timing_assertions(
                ordered_matches, timing_assertions
            )
            semantic.extend(
                {**result, "windowIndex": window_index}
                for result in window_semantic
            )
            ordered_results.extend(
                {**result, "windowIndex": window_index}
                for result in window_ordered
            )
            count_results.extend(
                {**result, "windowIndex": window_index}
                for result in window_counts
            )
            timing_results.extend(
                {**result, "windowIndex": window_index}
                for result in window_timing
            )
        missing = sorted(set(missing))
        present_forbidden = sorted(set(present_forbidden))
        assertion_results = (
            *semantic,
            *ordered_results,
            *count_results,
            *timing_results,
        )
        passed = not missing and not present_forbidden and all(
            item["passed"] for item in assertion_results
        )
    subject_results = _evaluate_subject_assertions(scenario, evidence, selection)
    passed = passed and all(item["passed"] for item in subject_results)
    return {
        "passed": passed,
        "resultKind": "actor-observation",
        "motionWindow": selection,
        "missingRequiredEvents": missing,
        "presentForbiddenEvents": present_forbidden,
        "semanticChecks": semantic,
        "orderedEventAssertions": ordered_results,
        "eventCountAssertions": count_results,
        "frameTimingAssertions": timing_results,
        "subjectAssertions": subject_results,
        "actorCount": len(evidence["observation"]["actors"]),
        "traceEventCount": len(events),
    }


def evaluate_subject_negative_control(
    scenario: dict[str, Any],
    evidence: dict[str, Any],
    trace_schema: dict[str, Any],
) -> dict[str, Any]:
    """Require live subject proof to fail when its public snapshots are removed."""
    subjects = scenario.get("subjects", [])
    if not subjects:
        return {"passed": True, "applied": False, "subjects": []}
    stripped = copy.deepcopy(evidence)
    subject_keys = {
        (subject["species"], subject["role"])
        for subject in subjects
    }
    stripped["observation"]["actors"] = [
        actor
        for actor in stripped["observation"]["actors"]
        if (actor["species"], actor["role"]) not in subject_keys
    ]
    result = evaluate_scenario_evidence(scenario, stripped, trace_schema)
    failed_subjects = [
        assertion["id"]
        for assertion in result["subjectAssertions"]
        if not assertion["passed"] and assertion["actual"] == 0
    ]
    expected_subjects = [subject["id"] for subject in subjects]
    return {
        "passed": not result["passed"] and failed_subjects == expected_subjects,
        "applied": True,
        "subjects": expected_subjects,
        "failedSubjects": failed_subjects,
    }


def evaluate_behavior_negative_control(
    scenario: dict[str, Any],
    evidence: dict[str, Any],
    trace_schema: dict[str, Any],
) -> dict[str, Any]:
    """Require the semantic evaluator to fail when one required behavior is removed."""
    positive = evaluate_scenario_evidence(scenario, evidence, trace_schema)
    selection = positive.get("motionWindow", {})
    actor_handle = selection.get("actorHandle")
    ordered = scenario["expect"].get("orderedEvents", [])
    required = scenario["expect"].get("requiredEvents", [])
    counted = scenario["expect"].get("eventCounts", [])
    target = (
        ordered[-1]["event"]
        if ordered
        else required[-1]
        if required
        else counted[-1]["event"]
        if counted
        else None
    )
    if not positive["passed"] or actor_handle is None or target is None:
        return {
            "passed": False,
            "applied": False,
            "event": target,
            "removed": 0,
            "reason": "positive behavior or a required event was not available",
        }
    mutated = copy.deepcopy(evidence)
    events = mutated["observation"]["trace"]["events"]
    retained = [
        event
        for event in events
        if not (
            event["actorHandle"] == actor_handle
            and event["event"] == target
        )
    ]
    removed = len(events) - len(retained)
    mutated["observation"]["trace"]["events"] = retained
    result = evaluate_scenario_evidence(scenario, mutated, trace_schema)
    return {
        "passed": removed > 0 and not result["passed"],
        "applied": removed > 0,
        "event": target,
        "removed": removed,
    }


def write_evidence(document: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
