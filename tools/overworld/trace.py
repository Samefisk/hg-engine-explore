"""Decode the versioned overworld semantic trace format."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

from tools.overworld.validation import ValidationFailure, load_json_document


TRACE_MAGIC = b"OWTR"
TRACE_VERSION = 1
TRACE_CAPACITY = 32
HEADER = struct.Struct("<4sHHIIIIHHHHBBBB")
RECORD = struct.Struct("<II6HHHII")


def load_trace_schema(path: Path) -> dict[str, Any]:
    document = load_json_document(path)
    expected = {"schemaVersion", "magic", "header", "record", "events", "reasons"}
    if not isinstance(document, dict) or set(document) != expected:
        raise ValidationFailure(f"{path}: trace schema keys differ")
    if document["schemaVersion"] != TRACE_VERSION or document["magic"] != "OWTR":
        raise ValidationFailure(f"{path}: unsupported trace schema")
    if document["header"] != {"format": HEADER.format, "size": HEADER.size}:
        raise ValidationFailure(f"{path}: trace header layout differs")
    if document["record"] != {"format": RECORD.format, "size": RECORD.size}:
        raise ValidationFailure(f"{path}: trace record layout differs")
    for key in ("events", "reasons"):
        mapping = document[key]
        if not isinstance(mapping, dict) or not mapping:
            raise ValidationFailure(f"{path}: {key} must be a non-empty object")
        for numeric, name in mapping.items():
            if not numeric.isdigit() or not isinstance(name, str) or not name:
                raise ValidationFailure(f"{path}: {key} mapping is invalid")
    return document


def _name(mapping: dict[str, str], value: int, prefix: str) -> str:
    return mapping.get(str(value), f"{prefix}_{value}")


def _decode_binary(data: bytes, schema: dict[str, Any]) -> dict[str, Any]:
    if len(data) < HEADER.size:
        raise ValidationFailure("trace is shorter than its header")
    (
        magic,
        version,
        header_size,
        oldest_sequence,
        next_sequence,
        overwritten_count,
        filter_event_mask,
        field_epoch,
        filter_actor_slot,
        filter_actor_generation,
        filter_frames_remaining,
        write_index,
        count,
        armed,
        _reserved,
    ) = HEADER.unpack_from(data)
    if magic != TRACE_MAGIC or version != TRACE_VERSION:
        raise ValidationFailure("trace magic or version differs")
    if header_size != HEADER.size:
        raise ValidationFailure("trace layout differs from schema")
    if count > TRACE_CAPACITY or next_sequence < oldest_sequence:
        raise ValidationFailure("trace header counters are invalid")
    required_size = header_size + TRACE_CAPACITY * RECORD.size
    if len(data) != required_size:
        raise ValidationFailure(
            f"trace size is {len(data)}, expected {required_size}"
        )
    records = []
    for index in range(TRACE_CAPACITY):
        values = RECORD.unpack_from(data, header_size + index * RECORD.size)
        sequence = values[0]
        if not oldest_sequence <= sequence < next_sequence:
            continue
        records.append(values)
    records.sort(key=lambda item: item[0])
    if len(records) != count:
        raise ValidationFailure(
            f"trace contains {len(records)} live records, header declares {count}"
        )
    events = [
        {
            "sequence": values[0],
            "frame": values[1],
            "actorHandle": (values[3] << 16) | values[2],
            "actor": {
                "slot": values[2],
                "generation": values[3],
                "fieldEpoch": values[4],
                "mapGeneration": values[5],
                "encounterGeneration": values[6],
            },
            "eventId": values[8],
            "event": _name(schema["events"], values[8], "EVENT"),
            "reasonId": values[9],
            "reason": _name(schema["reasons"], values[9], "REASON"),
            "valueA": values[10],
            "valueB": values[11],
        }
        for values in records
    ]
    return {
        "schemaVersion": version,
        "header": {
            "capacity": TRACE_CAPACITY,
            "count": count,
            "oldestSequence": oldest_sequence,
            "nextSequence": next_sequence,
            "overwrittenCount": overwritten_count,
            "fieldEpoch": field_epoch,
            "filterEventMask": filter_event_mask,
            "filterActor": {
                "slot": filter_actor_slot,
                "generation": filter_actor_generation,
            },
            "filterFramesRemaining": filter_frames_remaining,
            "writeIndex": write_index,
            "armed": armed,
        },
        "events": events,
    }


def _decode_json(data: bytes, schema: dict[str, Any]) -> dict[str, Any]:
    try:
        document = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationFailure(f"invalid JSON trace: {error}") from error
    if not isinstance(document, dict) or set(document) != {
        "schemaVersion",
        "header",
        "events",
    }:
        raise ValidationFailure("JSON trace top-level keys differ")
    if document["schemaVersion"] != TRACE_VERSION:
        raise ValidationFailure("JSON trace version differs")
    header_keys = {
        "capacity",
        "count",
        "oldestSequence",
        "nextSequence",
        "overwrittenCount",
        "fieldEpoch",
        "filterEventMask",
        "filterActor",
        "filterFramesRemaining",
        "writeIndex",
        "armed",
    }
    if not isinstance(document["header"], dict) or set(document["header"]) != header_keys:
        raise ValidationFailure("JSON trace header keys differ")
    if not isinstance(document["events"], list):
        raise ValidationFailure("JSON trace header or events differ")
    scalar_header = {key: value for key, value in document["header"].items()
                     if key != "filterActor"}
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in scalar_header.values()
    ):
        raise ValidationFailure("JSON trace header values must be non-negative integers")
    filter_actor = document["header"]["filterActor"]
    if not isinstance(filter_actor, dict) or set(filter_actor) != {"slot", "generation"}:
        raise ValidationFailure("JSON trace filterActor keys differ")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0
           for value in filter_actor.values()):
        raise ValidationFailure("JSON trace filterActor values must be non-negative integers")
    header = document["header"]
    if (
        header["count"] > header["capacity"]
        or header["nextSequence"] < header["oldestSequence"]
        or header["nextSequence"] - header["oldestSequence"] != header["count"]
        or header["count"] != len(document["events"])
    ):
        raise ValidationFailure("JSON trace header counters differ from its event window")
    normalized = []
    required = {
        "sequence",
        "frame",
        "actorHandle",
        "actor",
        "eventId",
        "reasonId",
        "valueA",
        "valueB",
    }
    for index, event in enumerate(document["events"]):
        if not isinstance(event, dict) or set(event) != required:
            raise ValidationFailure(f"JSON trace event {index} keys differ")
        actor = event.get("actor")
        if not isinstance(actor, dict) or set(actor) != {
            "slot", "generation", "fieldEpoch", "mapGeneration",
            "encounterGeneration",
        }:
            raise ValidationFailure(f"JSON trace event {index} actor keys differ")
        values = [event[key] for key in required if key != "actor"] + list(actor.values())
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise ValidationFailure(f"JSON trace event {index} values must be integers")
        normalized.append(
            {
                **event,
                "event": _name(schema["events"], event["eventId"], "EVENT"),
                "reason": _name(schema["reasons"], event["reasonId"], "REASON"),
            }
        )
    normalized.sort(key=lambda event: event["sequence"])
    if [event["sequence"] for event in normalized] != list(
        range(header["oldestSequence"], header["nextSequence"])
    ):
        raise ValidationFailure("JSON trace event sequence is not contiguous")
    return {**document, "events": normalized}


def decode_trace(path: Path, schema: dict[str, Any]) -> dict[str, Any]:
    data = path.read_bytes()
    stripped = data.lstrip()
    return _decode_json(data, schema) if stripped.startswith(b"{") else _decode_binary(data, schema)


def filter_events(
    document: dict[str, Any], actor: int | None, event_name: str | None
) -> dict[str, Any]:
    events = document["events"]
    if actor is not None:
        events = [event for event in events if event["actorHandle"] == actor]
    if event_name is not None:
        events = [event for event in events if event["event"] == event_name]
    return {**document, "events": events}
