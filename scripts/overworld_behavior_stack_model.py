#!/usr/bin/env python3
"""Deterministic host reference for one-state overworld behavior stacks.

This module intentionally performs no engine work.  It composes immutable data,
preflights stack deltas in scratch state, and emits stabilization/presentation
plans for a future runtime or editor to consume.

The public surface is centered on :class:`BehaviorCatalog`,
:class:`StackRuntime`, :func:`resolve_static`, and
:meth:`StackRuntime.apply_stack_delta`.  All public results are JSON friendly
through :func:`to_data`; :func:`catalog_from_dict` accepts both ordinary JSON
scalars and the ``{raw, symbol, value}`` atoms used by the legacy golden export.
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import hashlib
import hmac
import json
import os
import secrets
import subprocess
import sys
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


MAX_RUNTIME_LAYERS = 8
MODEL_SCHEMA = "hg-engine.overworld-behavior.stack-model"
MODEL_SCHEMA_VERSION = 1
GEN_MAX = 0xFFFFFFFF
INITIAL_DATA_INCARCATION = "data-incarnation:1"
CALM_RESET_OWNER_IDS = (101, 110, 111)


def _closed_map_key_token(key: Any) -> tuple[Any, ...]:
    """Return a hash-safe token without hashing/comparing the original key."""

    key_type = type(key)
    if key is None:
        return ("none",)
    if key_type is bool:
        return ("bool", 1 if key else 0)
    if key_type is int:
        return ("int", key)
    if key_type is str:
        return ("str", key)
    if key_type is bytes:
        return ("bytes", key)
    if key_type is tuple:
        return ("tuple", tuple(_closed_map_key_token(item) for item in key))
    for enum_index, (enum_type, members) in enumerate(globals().get("_RUNTIME_GRAPH_ENUM_MEMBERS", ())):
        if key_type is enum_type:
            for member_index, member in enumerate(members):
                if key is member:
                    return ("enum", enum_index, member_index)
            raise TypeError("ClosedMap enum key is not a canonical singleton")
    raise TypeError("ClosedMap key is outside the callback-free closed key domain")


def _closed_map_token_matches(key: Any, token: Any) -> bool:
    """Validate a stored surrogate using exact safe scalar comparisons only."""

    if type(token) is not tuple or not token or type(token[0]) is not str:
        return False
    key_type = type(key)
    tag = token[0]
    if key is None:
        return token == ("none",)
    if key_type is bool:
        return len(token) == 2 and tag == "bool" and type(token[1]) is int and token[1] == (1 if key else 0)
    if key_type is int:
        return len(token) == 2 and tag == "int" and type(token[1]) is int and token[1] == key
    if key_type is str:
        return len(token) == 2 and tag == "str" and type(token[1]) is str and token[1] == key
    if key_type is bytes:
        return len(token) == 2 and tag == "bytes" and type(token[1]) is bytes and token[1] == key
    if key_type is tuple:
        return (
            len(token) == 2 and tag == "tuple" and type(token[1]) is tuple
            and len(token[1]) == len(key)
            and all(_closed_map_token_matches(item, child) for item, child in zip(key, token[1]))
        )
    for enum_index, (enum_type, members) in enumerate(globals().get("_RUNTIME_GRAPH_ENUM_MEMBERS", ())):
        if key_type is enum_type:
            return (
                len(token) == 3 and tag == "enum"
                and type(token[1]) is int and token[1] == enum_index
                and type(token[2]) is int and 0 <= token[2] < len(members)
                and key is members[token[2]]
            )
    return False


class ClosedMap(Mapping[Any, Any]):
    """Callback-free immutable mapping used by all model/runtime storage."""

    __slots__ = ("_items", "_index")

    def __init__(self, source: Any = None):
        if source is None:
            items: tuple[tuple[Any, Any], ...] = ()
        elif type(source) is ClosedMap:
            items = object.__getattribute__(source, "_items")
        elif type(source) is dict:
            items = tuple(source.items())
        elif type(source) in {list, tuple}:
            items = tuple(source)
        else:
            raise TypeError("ClosedMap source must be an exact dict, list, tuple, or ClosedMap")
        index: dict[tuple[Any, ...], tuple[Any, Any]] = {}
        for item in items:
            if type(item) is not tuple or len(item) != 2:
                raise TypeError("ClosedMap entries must be exact key/value tuples")
            key, value = item
            token = _closed_map_key_token(key)
            if token in index:
                raise ValueError("ClosedMap keys must be unique")
            index[token] = (key, value)
        object.__setattr__(self, "_items", items)
        object.__setattr__(self, "_index", index)

    def __iter__(self):
        return (key for key, _value in object.__getattribute__(self, "_items"))

    def __len__(self) -> int:
        return len(object.__getattribute__(self, "_items"))

    def __getitem__(self, key: Any) -> Any:
        return object.__getattribute__(self, "_index")[_closed_map_key_token(key)][1]

    def items(self):
        return object.__getattribute__(self, "_items")

    def keys(self):
        return tuple(key for key, _value in object.__getattribute__(self, "_items"))

    def values(self):
        return tuple(value for _key, value in object.__getattribute__(self, "_items"))

    def get(self, key: Any, default: Any = None) -> Any:
        entry = object.__getattribute__(self, "_index").get(_closed_map_key_token(key))
        return default if entry is None else entry[1]


# Retain the established internal spelling while removing built-in mapping
# proxies and their opaque/custom backing-map callback surface.
MappingProxyType = ClosedMap


def _require_exact_stack_runtime(runtime: Any) -> None:
    """Non-dispatched public trust boundary for runtime-bearing APIs."""

    runtime_type = type(runtime)
    exact_type = globals().get("StackRuntime")
    if exact_type is None or runtime_type is not exact_type:
        raise ModelError(Status.INVALID_HANDLE, "public runtime APIs require an exact StackRuntime instance")


def _nonexact_runtime_delta_failure(runtime: Any, reason: Any) -> "DeltaResult | None":
    """Return a self-independent typed rejection at the public trust boundary."""

    exact_type = globals().get("StackRuntime")
    if exact_type is not None and type(runtime) is exact_type:
        return None
    return DeltaResult(
        False, Status.INVALID_HANDLE, False,
        reason if type(reason) is str else "InvalidRuntime",
        (), ClosedMap(), ClosedMap(), None, (),
        "public runtime APIs require an exact StackRuntime instance",
    )


class Channel(IntEnum):
    STATIC_CONTEXT = 0
    CONTROLLER_STATE = 1
    TEMPORARY_EFFECT = 2
    SCRIPTED_FORCE = 3
    POSSESSION = 4
    SYSTEM_SAFETY = 5


class SemanticRole(str, Enum):
    CALM = "CALM"
    ATTENTIVE = "ATTENTIVE"
    TIRED = "TIRED"
    ASLEEP = "ASLEEP"
    CARRIED = "CARRIED"
    FOLLOWER = "FOLLOWER"
    CUSTOM = "CUSTOM"


class DefinitionKind(str, Enum):
    STATE_CANDIDATE = "STATE_CANDIDATE"
    MODIFIER = "MODIFIER"


class SelectorKind(str, Enum):
    EXACT = "EXACT"
    SEMANTIC = "SEMANTIC"


class OperatorKind(str, Enum):
    SET = "SET"
    ADD = "ADD"
    AT_LEAST = "AT_LEAST"
    AT_MOST = "AT_MOST"
    ADD_AT_LEAST = "ADD_AT_LEAST"
    ADD_AT_MOST = "ADD_AT_MOST"


class LifetimePolicy(str, Enum):
    CLEAR = "CLEAR"
    PRESERVE_LOGICAL = "PRESERVE_LOGICAL"
    SYSTEM = "SYSTEM"


class TimerClock(str, Enum):
    FRAME = "FRAME"
    COMPLETED_MOVEMENT = "COMPLETED_MOVEMENT"


class HiddenPolicy(str, Enum):
    PAUSE_WHILE_HIDDEN = "PAUSE_WHILE_HIDDEN"
    CONTINUE_WHILE_HIDDEN = "CONTINUE_WHILE_HIDDEN"
    EXPIRE_ON_HIDE = "EXPIRE_ON_HIDE"


class RecoveryPolicy(str, Enum):
    REMOVE_SELF = "REMOVE_SELF"
    LEGACY_RETURN_CALM = "LEGACY_RETURN_CALM"
    REVEAL_UNDERLYING = "REVEAL_UNDERLYING"


class TimerDurationPolicy(str, Enum):
    """Source-sensitive timer-duration interpretation at the schema boundary."""

    LEGACY_REST_TIME = "LEGACY_REST_TIME"
    FINITE = "FINITE"
    INDEFINITE = "INDEFINITE"


class TiredOriginKind(IntEnum):
    FLED = 1
    RAM_CRASH = 2
    THROW_RECOVERY = 3


# Frozen phase-0 generated-family registry.  Human-readable owner names are
# diagnostics only; authorization and closure use these stable IDs/fields.
GENERATED_FAMILY_SPECS: Mapping[str, Mapping[str, Any]] = MappingProxyType({
    "STAMINA": MappingProxyType({"origin": None, "owner_id": 102, "owner_name": "stamina", "channel": Channel.TEMPORARY_EFFECT, "priority": 100, "duration": 4, "duration_policy": TimerDurationPolicy.LEGACY_REST_TIME, "clock": TimerClock.FRAME, "hidden_policy": HiddenPolicy.PAUSE_WHILE_HIDDEN, "recovery": RecoveryPolicy.LEGACY_RETURN_CALM, "calm_reset_owner_ids": (101, 110, 111), "recovery_transition_id": 0, "map_policy": LifetimePolicy.PRESERVE_LOGICAL, "battle_policy": LifetimePolicy.CLEAR}),
    "FLED": MappingProxyType({"origin": TiredOriginKind.FLED, "owner_id": 107, "owner_name": "battle-fled", "channel": Channel.TEMPORARY_EFFECT, "priority": 90, "duration": 4, "duration_policy": TimerDurationPolicy.LEGACY_REST_TIME, "clock": TimerClock.FRAME, "hidden_policy": HiddenPolicy.PAUSE_WHILE_HIDDEN, "recovery": RecoveryPolicy.REMOVE_SELF, "calm_reset_owner_ids": (), "recovery_transition_id": 0, "map_policy": LifetimePolicy.PRESERVE_LOGICAL, "battle_policy": LifetimePolicy.CLEAR}),
    "RAM_CRASH": MappingProxyType({"origin": TiredOriginKind.RAM_CRASH, "owner_id": 108, "owner_name": "ram-crash", "channel": Channel.TEMPORARY_EFFECT, "priority": 91, "duration": 4, "duration_policy": TimerDurationPolicy.LEGACY_REST_TIME, "clock": TimerClock.FRAME, "hidden_policy": HiddenPolicy.PAUSE_WHILE_HIDDEN, "recovery": RecoveryPolicy.LEGACY_RETURN_CALM, "calm_reset_owner_ids": (101, 110, 111), "recovery_transition_id": 0, "map_policy": LifetimePolicy.PRESERVE_LOGICAL, "battle_policy": LifetimePolicy.CLEAR}),
    "THROW_RECOVERY": MappingProxyType({"origin": TiredOriginKind.THROW_RECOVERY, "owner_id": 109, "owner_name": "throw-recovery", "channel": Channel.TEMPORARY_EFFECT, "priority": 92, "duration": 4, "duration_policy": TimerDurationPolicy.LEGACY_REST_TIME, "clock": TimerClock.FRAME, "hidden_policy": HiddenPolicy.PAUSE_WHILE_HIDDEN, "recovery": RecoveryPolicy.LEGACY_RETURN_CALM, "calm_reset_owner_ids": (101, 110, 111), "recovery_transition_id": 0, "map_policy": LifetimePolicy.PRESERVE_LOGICAL, "battle_policy": LifetimePolicy.CLEAR}),
})


class StaticActionKind(str, Enum):
    ASSIGN_CONTROLLER = "ASSIGN_CONTROLLER"
    BIND_NODE = "BIND_NODE"
    UNBIND_NODE = "UNBIND_NODE"
    APPLY_STATE_MODIFIER = "APPLY_STATE_MODIFIER"
    APPLY_CONTROLLER_MODIFIER = "APPLY_CONTROLLER_MODIFIER"
    BIND_SPAWN_POLICY = "BIND_SPAWN_POLICY"
    APPLY_SPAWN_POLICY_PATCH = "APPLY_SPAWN_POLICY_PATCH"
    BIND_POPULATION_POLICY = "BIND_POPULATION_POLICY"
    APPLY_POPULATION_POLICY_PATCH = "APPLY_POPULATION_POLICY_PATCH"
    BIND_HOOK_SET = "BIND_HOOK_SET"
    APPLY_CANDIDATE_TIMER_OPERATOR = "APPLY_CANDIDATE_TIMER_OPERATOR"


class DeltaOpKind(str, Enum):
    APPLY = "APPLY"
    REPLACE = "REPLACE"
    REMOVE_REQUIRED = "REMOVE_REQUIRED"
    REMOVE_IF_PRESENT = "REMOVE_IF_PRESENT"
    REMOVE_OWNER_IF_PRESENT = "REMOVE_OWNER_IF_PRESENT"
    REMOVE_POLICY = "REMOVE_POLICY"
    CLEAR = "CLEAR"


class Status(str, Enum):
    OK = "OK"
    IDEMPOTENT = "IDEMPOTENT"
    STALE_NOOP = "STALE_NOOP"
    STALE_HANDLE = "STALE_HANDLE"
    INVALID_HANDLE = "INVALID_HANDLE"
    WRONG_SLOT = "WRONG_SLOT"
    SLOT_GENERATION_MISMATCH = "SLOT_GENERATION_MISMATCH"
    INVALID_DEFINITION = "INVALID_DEFINITION"
    INVALID_GENERATED_WRAPPER = "INVALID_GENERATED_WRAPPER"
    OWNER_NOT_AUTHORIZED = "OWNER_NOT_AUTHORIZED"
    GENERATED_WRAPPER_FAMILY_MISMATCH = "GENERATED_WRAPPER_FAMILY_MISMATCH"
    OWNER_KEY_OCCUPIED = "OWNER_KEY_OCCUPIED"
    DEFINITION_OWNED = "DEFINITION_OWNED"
    INSTANCE_KEY_NOT_ALLOWED = "INSTANCE_KEY_NOT_ALLOWED"
    NOT_FOUND = "NOT_FOUND"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    AMBIGUOUS_SELECTOR = "AMBIGUOUS_SELECTOR"
    AMBIGUOUS_DELTA = "AMBIGUOUS_DELTA"
    CAPACITY_EXCEEDED = "CAPACITY_EXCEEDED"
    INVALID_MODIFIER = "INVALID_MODIFIER"
    INVALID_COMPOSITION = "INVALID_COMPOSITION"
    INVALID_STATIC_DATA = "INVALID_STATIC_DATA"
    INVALID_TRANSLATION = "INVALID_TRANSLATION"
    INACTIVE_SLOT = "INACTIVE_SLOT"
    RUNTIME_EPOCH_RESTARTED = "RUNTIME_EPOCH_RESTARTED"
    DATA_BUSY = "DATA_BUSY"


class ModelError(Exception):
    """A typed, expected contract failure."""

    def __init__(self, status: Status, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def unwrap_atom(value: Any) -> Any:
    """Accept legacy golden atoms as well as plain JSON values."""

    if type(value) is dict:
        keys = tuple(value.keys())
        if any(type(key) is not str for key in keys):
            raise ModelError(Status.INVALID_STATIC_DATA, "JSON object keys must be exact canonical strings")
        if not any(key in ("raw", "symbol") for key in keys):
            return value
        if len(keys) != 3 or set(keys) != {"raw", "symbol", "value"}:
            raise ModelError(Status.INVALID_STATIC_DATA, "legacy atom must have the exact raw/symbol/value shape")
        raw, symbol, unwrapped = value["raw"], value["symbol"], value["value"]
        if type(raw) is not str or symbol is not None and type(symbol) is not str:
            raise ModelError(Status.INVALID_STATIC_DATA, "legacy atom raw/symbol fields are noncanonical")
        if unwrapped is not None and type(unwrapped) not in {bool, int, str}:
            raise ModelError(Status.INVALID_STATIC_DATA, "legacy atom value must be a closed scalar")
        return unwrapped
    return value


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        to_data(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def stable_hash(prefix: str, value: Any, length: int | None = None) -> str:
    digest = hashlib.sha256(canonical_json_bytes(value)).hexdigest()
    if length is not None:
        digest = digest[:length]
    return f"{prefix}:{digest}"


def _deep_freeze(value: Any) -> Any:
    """Make authoring payloads transitively immutable at the catalog boundary."""

    if isinstance(value, Mapping):
        frozen: dict[Any, Any] = {}
        for key, item in value.items():
            frozen_key = _deep_freeze(key)
            try:
                hash(frozen_key)
            except TypeError as exc:
                raise ModelError(Status.INVALID_STATIC_DATA, f"mapping key {type(key).__name__} is not canonically immutable") from exc
            frozen[frozen_key] = _deep_freeze(item)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_deep_freeze(item) for item in value)
    if dataclasses.is_dataclass(value):
        params = getattr(type(value), "__dataclass_params__", None)
        if not params.frozen or globals().get(type(value).__name__) is not type(value):
            raise ModelError(Status.INVALID_STATIC_DATA, f"unsupported dataclass leaf {type(value).__name__}")
        frozen_fields = {
            field_.name: _deep_freeze(getattr(value, field_.name))
            for field_ in dataclasses.fields(value) if field_.init
        }
        try:
            return type(value)(**frozen_fields)
        except (TypeError, ValueError) as exc:
            raise ModelError(Status.INVALID_STATIC_DATA, f"cannot canonicalize dataclass leaf {type(value).__name__}: {exc}") from exc
    if value is None or type(value) in {bool, int, str} or isinstance(value, Enum):
        return value
    raise ModelError(Status.INVALID_STATIC_DATA, f"unsupported mutable/noncanonical leaf {type(value).__name__}")


_TO_DATA_LAST_DATACLASS_SCHEMA: tuple[Any, tuple[str, ...], tuple[Any, ...]] | None = None
_TO_DATA_LAST_ENUM_SCHEMA: tuple[Any, tuple[Any, ...]] | None = None


def _registered_dataclass_storage(value: Any) -> tuple[tuple[str, ...], dict[str, Any]] | None:
    """Return raw closed storage for a registered model dataclass, without descriptors."""

    global _TO_DATA_LAST_DATACLASS_SCHEMA
    value_type = type(value)
    cached = _TO_DATA_LAST_DATACLASS_SCHEMA
    schemas = (cached,) if cached is not None and value_type is cached[0] else globals().get("_RUNTIME_GRAPH_DATACLASS_SCHEMA", ())
    for candidate_type, field_names, expected_carriers in schemas:
        if value_type is not candidate_type:
            continue
        _TO_DATA_LAST_DATACLASS_SCHEMA = (candidate_type, field_names, expected_carriers)
        storage = object.__getattribute__(value, "__dict__")
        if type(storage) is not dict:
            raise ModelError(Status.INVALID_STATIC_DATA, f"{candidate_type.__name__} storage is not an exact dictionary")
        actual_names = tuple(storage.keys())
        if any(type(name) is not str for name in actual_names) or set(actual_names) != set(field_names):
            missing = sorted(name for name in field_names if name not in actual_names)
            extra = sorted(name for name in actual_names if type(name) is str and name not in field_names)
            raise ModelError(Status.INVALID_STATIC_DATA, f"{candidate_type.__name__} storage is not closed (missing={missing}, extra={extra})")
        class_storage = type.__getattribute__(candidate_type, "__dict__")
        absent = globals().get("_ABSENT_CLASS_FIELD")
        for field_name, expected_carrier in zip(field_names, expected_carriers):
            current_carrier = class_storage[field_name] if field_name in class_storage else absent
            if current_carrier is not expected_carrier:
                raise ModelError(Status.INVALID_STATIC_DATA, "model dataclass field descriptor was replaced")
        return field_names, storage
    return None


def _registered_enum_wire_value(value: Any) -> Any:
    """Return a canonical enum wire scalar, or the private absence marker."""

    global _TO_DATA_LAST_ENUM_SCHEMA
    value_type = type(value)
    cached = _TO_DATA_LAST_ENUM_SCHEMA
    schemas = (cached,) if cached is not None and value_type is cached[0] else globals().get("_RUNTIME_GRAPH_ENUM_MEMBERS", ())
    for enum_type, members in schemas:
        if value_type is not enum_type:
            continue
        _TO_DATA_LAST_ENUM_SCHEMA = (enum_type, members)
        if not any(value is member for member in members):
            raise ModelError(Status.INVALID_STATIC_DATA, "forged enum cannot be serialized")
        storage = object.__getattribute__(value, "__dict__")
        if type(storage) is not dict:
            raise ModelError(Status.INVALID_STATIC_DATA, "enum storage is not canonical")
        storage_keys = tuple(storage.keys())
        if any(type(key) is not str for key in storage_keys) or len(storage_keys) != 3 or set(storage_keys) != {"__objclass__", "_name_", "_value_"}:
            raise ModelError(Status.INVALID_STATIC_DATA, "enum storage is not canonical")
        return storage["_name_"] if enum_type in globals().get("_RUNTIME_GRAPH_ENUM_TYPES", ()) and issubclass(enum_type, IntEnum) else storage["_value_"]
    return globals().get("_ABSENT_CLASS_FIELD")


def _canonical_json_key_text(key: Any) -> tuple[str, str]:
    """Encode a closed mapping key without user string/hash/equality dispatch."""

    key_type = type(key)
    if key_type is str:
        return "str", key
    if key_type is int:
        return "int", str(key)
    if key_type is tuple:
        encoded = [_canonical_json_key_text(item) for item in key]
        if any(tag not in {"int", "str"} for tag, _text in encoded):
            raise ModelError(Status.INVALID_STATIC_DATA, "tuple JSON key contains an unsupported member")
        body = ", ".join(repr(text) if tag == "str" else text for tag, text in encoded)
        if len(encoded) == 1:
            body += ","
        return "tuple", f"({body})"
    enum_value = _registered_enum_wire_value(key)
    if enum_value is not globals().get("_ABSENT_CLASS_FIELD") and type(enum_value) in {int, str}:
        return "enum", str(enum_value)
    raise ModelError(Status.INVALID_STATIC_DATA, "mapping key is outside the closed JSON-key domain")


def to_data(value: Any) -> Any:
    """Recursively convert closed model values to deterministic detached data."""

    value_type = type(value)
    if value is None or value_type in {bool, int, float, str}:
        return value
    if value_type in {dict, ClosedMap}:
        items = tuple(value.items()) if value_type is dict else object.__getattribute__(value, "_items")
        encoded: list[tuple[str, str, Any]] = []
        for pair in items:
            if type(pair) is not tuple or len(pair) != 2:
                raise ModelError(Status.INVALID_STATIC_DATA, "mapping entry is not a closed pair")
            tag, text_key = _canonical_json_key_text(pair[0])
            encoded.append((text_key, tag, pair[1]))
        encoded.sort(key=lambda row: (row[0], row[1]))
        normalized: dict[str, Any] = {}
        for text_key, _tag, item in encoded:
            if text_key in normalized:
                raise ModelError(Status.INVALID_STATIC_DATA, f"JSON key stringification collision at {text_key!r}")
            normalized[text_key] = to_data(item)
        return normalized
    if value_type in {list, tuple, deque}:
        return [to_data(item) for item in value]
    if value_type in {set, frozenset}:
        encoded = [(_canonical_type_tag(item), canonical_json_bytes(item), item) for item in value]
        return [to_data(item) for _tag, _encoded, item in sorted(encoded, key=lambda entry: (entry[0], entry[1]))]
    enum_value = _registered_enum_wire_value(value)
    if enum_value is not globals().get("_ABSENT_CLASS_FIELD"):
        return enum_value
    dataclass_storage = _registered_dataclass_storage(value)
    if dataclass_storage is not None:
        field_names, storage = dataclass_storage
        node_selector_type = globals().get("NodeSelector")
        if value_type is node_selector_type:
            kind = storage["kind"]
            if kind is SelectorKind.EXACT:
                return {"kind": kind.value, "controllerId": storage["controller_id"], "nodeId": storage["node_id"]}
            role = storage["role"]
            result = {"kind": kind.value, "role": role.value if role is not None else None}
            if storage["custom_role_id"]:
                result["customRoleId"] = storage["custom_role_id"]
            return result
        if value_type in {globals().get("StaticContext"), globals().get("ContextMatcher")}:
            return {
                _camel(field_name): _extra_to_data(storage[field_name]) if field_name == "extras" else to_data(storage[field_name])
                for field_name in field_names
            }
        return {
            _camel(field_name): to_data(storage[field_name])
            for field_name in field_names if not field_name.startswith("_")
        }
    raise ModelError(Status.INVALID_STATIC_DATA, "value is outside the closed serialization domain")


def _camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in tail)


def _canonical_type_tag(value: Any) -> str:
    if value is None:
        return "00:none"
    if type(value) is bool:
        return "01:bool"
    if type(value) is int:
        return "02:int"
    if type(value) is str:
        return "03:str"
    if isinstance(value, Enum):
        return f"04:enum:{type(value).__module__}.{type(value).__qualname__}"
    if isinstance(value, tuple):
        return "05:tuple"
    if dataclasses.is_dataclass(value):
        return f"06:dataclass:{type(value).__module__}.{type(value).__qualname__}"
    raise ModelError(Status.INVALID_STATIC_DATA, f"unsupported deterministic set member {type(value).__name__}")


def _extra_to_data(value: Any) -> Any:
    if type(value) in {MappingProxyType, dict}:
        items = tuple(value.items()) if type(value) is dict else object.__getattribute__(value, "_items")
        if any(type(pair) is not tuple or len(pair) != 2 for pair in items):
            raise ModelError(Status.INVALID_STATIC_DATA, "extras mapping entries must be exact pairs")
        if any(type(pair[0]) is not str for pair in items):
            raise ModelError(Status.INVALID_STATIC_DATA, "extras mapping keys must be canonical strings")
        return {"$extraType": "map", "entries": [[key, _extra_to_data(item)] for key, item in sorted(items, key=lambda pair: pair[0])]}
    if type(value) is tuple:
        return {"$extraType": "tuple", "items": [_extra_to_data(item) for item in value]}
    if type(value) is frozenset:
        encoded = sorted((canonical_json_bytes(_extra_to_data(item)), item) for item in value)
        return {"$extraType": "frozenset", "items": [_extra_to_data(item) for _encoded, item in encoded]}
    if value is None or type(value) in {bool, int, str}:
        return value
    raise ModelError(Status.INVALID_STATIC_DATA, f"unsupported extras value {type(value).__name__}")


def _decode_canonical_value(value: Any, path: str) -> Any:
    if type(value) is dict:
        keys = tuple(value.keys())
        if any(type(key) is not str for key in keys):
            raise ModelError(Status.INVALID_STATIC_DATA, f"{path} mapping keys must be canonical strings")
        if "$extraType" not in keys:
            return {key: _decode_canonical_value(value[key], f"{path}.{key}") for key in keys}
        tag = value["$extraType"]
        if tag == "map":
            if len(keys) != 2 or set(keys) != {"$extraType", "entries"} or type(value["entries"]) is not list:
                raise ModelError(Status.INVALID_STATIC_DATA, f"{path} has a malformed map envelope")
            result: dict[str, Any] = {}
            previous_key: str | None = None
            for entry in value["entries"]:
                if type(entry) is not list or len(entry) != 2 or type(entry[0]) is not str or entry[0] in result or previous_key is not None and entry[0] <= previous_key:
                    raise ModelError(Status.INVALID_STATIC_DATA, f"{path} map entries are duplicate, unordered, or malformed")
                result[entry[0]] = _decode_canonical_value(entry[1], f"{path}.{entry[0]}")
                previous_key = entry[0]
            return result
        if tag in {"tuple", "frozenset"}:
            if len(keys) != 2 or set(keys) != {"$extraType", "items"} or type(value["items"]) is not list:
                raise ModelError(Status.INVALID_STATIC_DATA, f"{path} has a malformed collection envelope")
            decoded = [_decode_canonical_value(item, f"{path}.items") for item in value["items"]]
            if tag == "tuple":
                return tuple(decoded)
            canonical = [canonical_json_bytes(_extra_to_data(item)) for item in decoded]
            if canonical != sorted(canonical) or len(canonical) != len(set(canonical)):
                raise ModelError(Status.INVALID_STATIC_DATA, f"{path} frozenset items are duplicate or noncanonical")
            try:
                frozen = frozenset(decoded)
            except TypeError as exc:
                raise ModelError(Status.INVALID_STATIC_DATA, f"{path} frozenset contains an unhashable item") from exc
            if len(frozen) != len(decoded):
                raise ModelError(Status.INVALID_STATIC_DATA, f"{path} frozenset collapses typed-equal values")
            return frozen
        raise ModelError(Status.INVALID_STATIC_DATA, f"{path} has an unknown extras envelope")
    if type(value) is list:
        return tuple(_decode_canonical_value(item, f"{path}[]") for item in value)
    if value is None or type(value) in {bool, int, str}:
        return value
    raise ModelError(Status.INVALID_STATIC_DATA, f"{path} contains an unsupported value")


def _freeze_extras(value: Any, path: str = "extras") -> Any:
    if type(value) in {dict, MappingProxyType}:
        items = tuple(value.items()) if type(value) is dict else object.__getattribute__(value, "_items")
        if any(type(pair) is not tuple or len(pair) != 2 for pair in items):
            raise ModelError(Status.INVALID_STATIC_DATA, f"{path} mapping entries must be exact pairs")
        if any(type(pair[0]) is not str for pair in items):
            raise ModelError(Status.INVALID_STATIC_DATA, f"{path} mapping keys must be canonical strings")
        return MappingProxyType(tuple((key, _freeze_extras(item, f"{path}.{key}")) for key, item in items))
    if type(value) in {list, tuple}:
        return tuple(_freeze_extras(item, f"{path}[]") for item in value)
    if type(value) in {set, frozenset}:
        frozen_items = tuple(_freeze_extras(item, f"{path}{{}}") for item in value)
        canonical = [canonical_json_bytes(_extra_to_data(item)) for item in frozen_items]
        if len(canonical) != len(set(canonical)):
            raise ModelError(Status.INVALID_STATIC_DATA, f"{path} set collapses typed-equal values")
        try:
            return frozenset(frozen_items)
        except TypeError as exc:
            raise ModelError(Status.INVALID_STATIC_DATA, f"{path} set contains an unhashable item") from exc
    if value is None or type(value) in {bool, int, str}:
        return value
    raise ModelError(Status.INVALID_STATIC_DATA, f"{path} contains unsupported value {type(value).__name__}")


def _read(data: Mapping[str, Any], snake: str, default: Any = None) -> Any:
    return unwrap_atom(data.get(snake, data.get(_camel(snake), default)))


def _read_raw(data: Mapping[str, Any], snake: str, default: Any = None) -> Any:
    return data.get(snake, data.get(_camel(snake), default))


def _present(data: Mapping[str, Any], snake: str) -> bool:
    return snake in data or _camel(snake) in data


def _mapping(value: Any, path: str, *, allow_none: bool = False, status: Status = Status.INVALID_STATIC_DATA) -> Mapping[str, Any] | None:
    if type(value) is dict and any(type(key) is not str for key in tuple(value.keys())):
        raise ModelError(status, f"{path} keys must be exact canonical strings")
    value = unwrap_atom(value)
    if value is None and allow_none:
        return None
    if type(value) not in {dict, ClosedMap}:
        raise ModelError(status, f"{path} must be an object")
    if any(type(key) is not str for key, _item in _exact_mapping_items(value, path, (str,), status=status)):
        raise ModelError(status, f"{path} keys must be exact canonical strings")
    return value


def _exact_mapping_items(
    value: Any, path: str, allowed_key_types: tuple[type, ...],
    *, status: Status = Status.INVALID_STATIC_DATA,
) -> tuple[tuple[Any, Any], ...]:
    """Snapshot exact mapping storage without virtual mapping dispatch."""

    if type(value) is dict:
        items = tuple(value.items())
    elif type(value) is ClosedMap:
        items = object.__getattribute__(value, "_items")
        index = object.__getattribute__(value, "_index")
        if type(items) is not tuple or type(index) is not dict or len(items) != len(index):
            raise ModelError(status, f"{path} ClosedMap storage is malformed")
        index_items = tuple(index.items())
        for item_pair, index_pair in zip(items, index_items):
            if (
                type(item_pair) is not tuple or len(item_pair) != 2
                or type(index_pair) is not tuple or len(index_pair) != 2
                or type(index_pair[1]) is not tuple or len(index_pair[1]) != 2
                or item_pair[0] is not index_pair[1][0] or item_pair[1] is not index_pair[1][1]
            ):
                raise ModelError(status, f"{path} ClosedMap index is malformed")
            if not _closed_map_token_matches(item_pair[0], index_pair[0]):
                raise ModelError(status, f"{path} ClosedMap index token is malformed")
    else:
        raise ModelError(status, f"{path} must be an exact dict or ClosedMap")
    if any(type(pair) is not tuple or len(pair) != 2 for pair in items):
        raise ModelError(status, f"{path} mapping entries must be exact pairs")
    if any(not any(type(pair[0]) is allowed for allowed in allowed_key_types) for pair in items):
        raise ModelError(status, f"{path} mapping key is outside its exact typed domain")
    return items


def _sequence(value: Any, path: str, *, status: Status = Status.INVALID_STATIC_DATA) -> Sequence[Any]:
    value = unwrap_atom(value)
    if type(value) not in {list, tuple}:
        raise ModelError(status, f"{path} must be an array")
    return value


def _typed_set(value: Any, path: str, parser: Any) -> frozenset[Any]:
    items = _sequence(value, path)
    parsed = [parser(item) for item in items]
    keys = [(_canonical_type_tag(item), canonical_json_bytes(item)) for item in parsed]
    if len(keys) != len(set(keys)):
        raise ModelError(Status.INVALID_STATIC_DATA, f"{path} contains duplicate values")
    return frozenset(parsed)


def _reject_unknown_fields(data: Mapping[str, Any], path: str, field_names: Iterable[str], *, status: Status = Status.INVALID_STATIC_DATA) -> None:
    if type(data) not in {dict, ClosedMap}:
        raise ModelError(status, f"{path} must be an exact object before field validation")
    keys = tuple(key for key, _item in _exact_mapping_items(data, path, (str,), status=status))
    if any(type(key) is not str for key in keys):
        raise ModelError(status, f"{path} keys must be exact canonical strings")
    fields = tuple(field_names)
    if any(type(field_name) is not str for field_name in fields):
        raise ModelError(status, f"{path} field schema is malformed")
    allowed = {name for field_name in fields for name in (field_name, _camel(field_name))}
    unknown = sorted(key for key in keys if key not in allowed)
    if unknown:
        raise ModelError(status, f"{path} carries unknown fields {unknown}")
    conflicts = sorted(field_name for field_name in fields if field_name != _camel(field_name) and field_name in data and _camel(field_name) in data)
    if conflicts:
        raise ModelError(status, f"{path} carries conflicting alias pairs {conflicts}")


def _closed_mapping(value: Any, path: str, field_names: Iterable[str], *, status: Status = Status.INVALID_STATIC_DATA) -> Mapping[str, Any]:
    data = _mapping(value, path, status=status)
    assert data is not None
    _reject_unknown_fields(data, path, field_names, status=status)
    return data


def _enum_value(enum_type: type[Enum], value: Any, path: str, *, status: Status = Status.INVALID_STATIC_DATA) -> Any:
    value = unwrap_atom(value)
    if type(value) is not str:
        raise ModelError(status, f"{path} must be a canonical enum string")
    try:
        return enum_type[value] if issubclass(enum_type, IntEnum) else enum_type(value)
    except (KeyError, ValueError) as exc:
        raise ModelError(status, f"{path} has unknown enum value {value!r}") from exc


def _id(value: Any, path: str) -> int:
    return _u16(value, path, nonzero=True)


def _u16(value: Any, path: str, *, nonzero: bool = False, status: Status = Status.INVALID_STATIC_DATA) -> int:
    value = _integer(value, path, status=status)
    if value < (1 if nonzero else 0) or value > 0xFFFF:
        qualifier = "nonzero " if nonzero else ""
        raise ModelError(status, f"{path} must be a {qualifier}u16")
    return value


def _u8(value: Any, path: str, *, nonzero: bool = False, status: Status = Status.INVALID_STATIC_DATA) -> int:
    value = _integer(value, path, status=status)
    if value < (1 if nonzero else 0) or value > 0xFF:
        raise ModelError(status, f"{path} must be a {'nonzero ' if nonzero else ''}u8")
    return value


def _u32(value: Any, path: str, *, nonzero: bool = False, status: Status = Status.INVALID_HANDLE) -> int:
    value = _integer(value, path, status=status)
    if value < (1 if nonzero else 0) or value > GEN_MAX:
        raise ModelError(status, f"{path} must be a {'nonzero ' if nonzero else ''}u32")
    return value


def _integer(value: Any, path: str, *, status: Status = Status.INVALID_STATIC_DATA) -> int:
    value = unwrap_atom(value)
    if type(value) is not int:
        raise ModelError(status, f"{path} must be an integral JSON/Python integer")
    return value


def _boolean(value: Any, path: str, *, status: Status = Status.INVALID_STATIC_DATA) -> bool:
    value = unwrap_atom(value)
    if type(value) is not bool:
        raise ModelError(status, f"{path} must be a JSON/Python boolean")
    return value


def _symbol(value: Any, path: str, *, status: Status = Status.INVALID_STATIC_DATA) -> str:
    value = unwrap_atom(value)
    if type(value) is not str or not value:
        raise ModelError(status, f"{path} must be a nonempty symbolic string")
    return value


def _authenticator(value: Any, path: str, *, status: Status = Status.INVALID_HANDLE) -> str:
    value = unwrap_atom(value)
    if type(value) is not str or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ModelError(status, f"{path} must be a canonical 256-bit lowercase hexadecimal tag")
    return value


def _handle_authenticator(value: Any, path: str = "handle.authenticator") -> str:
    value = unwrap_atom(value)
    if type(value) is not str or len(value) != 32 or any(char not in "0123456789abcdef" for char in value):
        raise ModelError(Status.INVALID_HANDLE, f"{path} must be a canonical 128-bit lowercase hexadecimal tag")
    return value


def _generation_next(value: int, carrier: str) -> int:
    if value <= 0:
        raise RuntimeError(f"{carrier} is zero")
    if value == GEN_MAX:
        raise ModelError(
            Status.INVALID_STATIC_DATA,
            f"{carrier} wrap requires explicit dependent invalidation",
        )
    return value + 1


@dataclass(frozen=True)
class StaticContext:
    species_id: int = 0
    form: int = 0
    species_group_ids: tuple[int, ...] = ()
    level: int = 1
    terrain: str = "NONE"
    map_id: int = 0
    shiny: bool = False
    assigned_class_id: int = 0
    data_generation: int = 1
    data_incarnation: str = INITIAL_DATA_INCARCATION
    extras: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        integers = (self.species_id, self.form, self.level, self.map_id, self.assigned_class_id, self.data_generation, *self.species_group_ids)
        if any(type(value) is not int for value in integers) or type(self.terrain) is not str or type(self.shiny) is not bool or type(self.data_incarnation) is not str or not self.data_incarnation or not 0 <= self.species_id <= 0xFFFF or not 0 <= self.form <= 0xFFFF or not 1 <= self.level <= 100 or not 0 <= self.map_id <= 0xFFFF or not 0 <= self.assigned_class_id <= 0xFFFF or not 1 <= self.data_generation <= GEN_MAX or any(not 0 <= group <= 0xFFFF for group in self.species_group_ids):
            raise ModelError(Status.INVALID_STATIC_DATA, "static context contains an invalid immutable axis")
        if type(self.extras) not in {dict, MappingProxyType} or any(type(key) is not str for key in self.extras):
            raise ModelError(Status.INVALID_STATIC_DATA, "static context extra keys must be canonical strings")
        object.__setattr__(self, "species_group_ids", tuple(self.species_group_ids))
        object.__setattr__(self, "extras", _freeze_extras(self.extras, "staticContext.extras"))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StaticContext":
        data = _closed_mapping(data, "staticContext", (field_.name for field_ in dataclasses.fields(cls)))
        known = {field_.name for field_ in dataclasses.fields(cls)}
        values = {name: (_read_raw(data, name) if name == "extras" else _read(data, name)) for name in known if (_read_raw(data, name) if name == "extras" else _read(data, name)) is not None}
        values["species_group_ids"] = tuple(_u16(value, "staticContext.speciesGroupId") for value in _sequence(values.get("species_group_ids", ()), "staticContext.speciesGroupIds"))
        raw_extras = values.get("extras", {})
        if type(raw_extras) is not dict:
            raise ModelError(Status.INVALID_STATIC_DATA, "staticContext.extras must be an object or canonical extras envelope")
        values["extras"] = _decode_canonical_value(raw_extras, "staticContext.extras")
        return cls(**values)


@dataclass(frozen=True)
class ContextMatcher:
    species_ids: frozenset[int] = frozenset()
    forms: frozenset[int] = frozenset()
    species_group_ids: frozenset[int] = frozenset()
    level_min: int | None = None
    level_max: int | None = None
    terrains: frozenset[str] = frozenset()
    map_ids: frozenset[int] = frozenset()
    shiny: bool | None = None
    assigned_class_ids: frozenset[int] = frozenset()
    extras: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("species_ids", "forms", "species_group_ids", "terrains", "map_ids", "assigned_class_ids"):
            object.__setattr__(self, name, frozenset(getattr(self, name)))
        numeric_sets = (self.species_ids, self.forms, self.species_group_ids, self.map_ids, self.assigned_class_ids)
        if any(any(type(value) is not int or not 0 <= value <= 0xFFFF for value in values) for values in numeric_sets) or any(type(value) is not str for value in self.terrains):
            raise ModelError(Status.INVALID_STATIC_DATA, "context matcher contains an invalid u16 axis value")
        if self.level_min is not None and (type(self.level_min) is not int or not 1 <= self.level_min <= 100) or self.level_max is not None and (type(self.level_max) is not int or not 1 <= self.level_max <= 100):
            raise ModelError(Status.INVALID_STATIC_DATA, "context matcher level bound is invalid")
        if self.level_min is not None and self.level_max is not None and self.level_min > self.level_max:
            raise ModelError(Status.INVALID_STATIC_DATA, "context matcher level minimum exceeds maximum")
        if self.shiny is not None and type(self.shiny) is not bool:
            raise ModelError(Status.INVALID_STATIC_DATA, "context matcher shiny axis must be boolean")
        if type(self.extras) not in {dict, MappingProxyType} or any(type(key) is not str for key in self.extras):
            raise ModelError(Status.INVALID_STATIC_DATA, "context matcher extra keys must be strings")
        object.__setattr__(self, "extras", _freeze_extras(self.extras, "contextMatcher.extras"))

    def matches(self, context: StaticContext) -> bool:
        checks = (
            not self.species_ids or context.species_id in self.species_ids,
            not self.forms or context.form in self.forms,
            not self.species_group_ids or bool(self.species_group_ids.intersection(context.species_group_ids)),
            self.level_min is None or context.level >= self.level_min,
            self.level_max is None or context.level <= self.level_max,
            not self.terrains or context.terrain in self.terrains,
            not self.map_ids or context.map_id in self.map_ids,
            self.shiny is None or context.shiny == self.shiny,
            not self.assigned_class_ids or context.assigned_class_id in self.assigned_class_ids,
            all(key in context.extras and canonical_json_bytes(_extra_to_data(context.extras[key])) == canonical_json_bytes(_extra_to_data(value)) for key, value in self.extras.items()),
        )
        return all(checks)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "ContextMatcher":
        if data is None:
            return cls()
        data = _closed_mapping(data, "contextMatcher", (field_.name for field_ in dataclasses.fields(cls)))
        sets = ("species_ids", "forms", "species_group_ids", "terrains", "map_ids", "assigned_class_ids")
        values: dict[str, Any] = {}
        for name in sets:
            parser = (lambda item, path=f"contextMatcher.{_camel(name)}": _symbol(item, path)) if name == "terrains" else (lambda item, path=f"contextMatcher.{_camel(name)}": _u16(item, path))
            values[name] = _typed_set(_read(data, name, ()), f"contextMatcher.{_camel(name)}", parser)
        for name in ("level_min", "level_max", "shiny"):
            values[name] = _read(data, name)
        raw_extras = _read_raw(data, "extras", {})
        if type(raw_extras) is not dict:
            raise ModelError(Status.INVALID_STATIC_DATA, "contextMatcher.extras must be an object or canonical extras envelope")
        values["extras"] = _decode_canonical_value(raw_extras, "contextMatcher.extras")
        return cls(**values)


@dataclass(frozen=True)
class StateProfile:
    stable_id: int
    behavior_kind: str
    locomotion: str = "IDLE"
    target: str = "NONE"
    speed: int = 1
    movement_range: int = 0
    allowed_tile: str = "NONE"
    allowed_tile_2: str = "NONE"
    jump_level: str = "NONE"
    ledge_jump: bool = False
    player_adjacent_direction_mask: int = 0
    hop_allow_non_cardinal: bool = False
    hop_min_distance: int = 0
    hop_max_distance: int = 0
    hop_pause: int = 0
    hop_time_per_tile: int = 0
    hop_spin_speed: int = 0
    teleport_time: int = 0
    teleport_pause: int = 0
    ram_acceleration_steps: int = 0
    ram_max_speed: int = 0
    chase_boost_distance: int = 0
    chase_boost_speed: int = 0
    circle_radius: int = 0
    continue_when_arrived: bool = False
    avoid_previous_tile: bool = False
    chain_pause_action: str = "NONE"
    chain_movement_variance: int = 0
    chain_pause_variance: int = 0
    battle_trigger: str = "NONE"
    contact_behavior: str = "NONE"

    def values(self) -> dict[str, Any]:
        result = to_data(self)
        result.pop("stableId")
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StateProfile":
        data = _closed_mapping(data, "stateProfile", (field_.name for field_ in dataclasses.fields(cls)))
        values = {
            field_.name: _read(data, field_.name, field_.default)
            for field_ in dataclasses.fields(cls)
            if _read(data, field_.name, dataclasses.MISSING) is not dataclasses.MISSING
        }
        values["stable_id"] = _id(values["stable_id"], "stateProfile.stableId")
        return cls(**values)


@dataclass(frozen=True)
class ControllerValues:
    alert_mode: str = "NONE"
    alert_emote: str = "NONE"
    alert_presentation_duration: int = 0
    detection_distance: int = 0
    alert_range: str = "NONE"
    alert_chance: int = 0
    stamina: int = 1
    recovery_duration: int = 1
    exhaustion_enabled: bool = True
    allow_reveal_underlying_recovery: bool = False

    def values(self) -> dict[str, Any]:
        return to_data(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "ControllerValues":
        if data is None:
            data = {}
        data = _closed_mapping(data, "controller.defaults", (field_.name for field_ in dataclasses.fields(cls)))
        return cls(**{field_.name: _read(data, field_.name, field_.default) for field_ in dataclasses.fields(cls)})


@dataclass(frozen=True)
class ControllerNode:
    stable_id: int
    role: SemanticRole
    state_profile_id: int | None
    custom_role_id: int = 0

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ControllerNode":
        data = _closed_mapping(data, "controllerNode", (field_.name for field_ in dataclasses.fields(cls)))
        profile = _read(data, "state_profile_id")
        return cls(
            _id(_read(data, "stable_id"), "controllerNode.stableId"),
            _enum_value(SemanticRole, _read(data, "role"), "controllerNode.role"),
            None if profile in (None, 0) else _id(profile, "controllerNode.stateProfileId"),
            _u16(_read(data, "custom_role_id", 0), "controllerNode.customRoleId"),
        )


@dataclass(frozen=True)
class Controller:
    stable_id: int
    base_node_id: int
    nodes: tuple[ControllerNode, ...]
    defaults: ControllerValues = ControllerValues()
    spawn_policy_id: int = 0
    population_policy_id: int = 0
    hook_set_id: int = 0

    def node(self, node_id: int) -> ControllerNode | None:
        return next((node for node in self.nodes if node.stable_id == node_id), None)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Controller":
        data = _closed_mapping(data, "controller", (field_.name for field_ in dataclasses.fields(cls)))
        return cls(
            _id(_read(data, "stable_id"), "controller.stableId"),
            _id(_read(data, "base_node_id"), "controller.baseNodeId"),
            tuple(ControllerNode.from_dict(item) for item in _sequence(_read(data, "nodes", ()), "controller.nodes")),
            ControllerValues.from_dict(_read(data, "defaults", {})),
            _u16(_read(data, "spawn_policy_id", 0), "controller.spawnPolicyId"),
            _u16(_read(data, "population_policy_id", 0), "controller.populationPolicyId"),
            _u16(_read(data, "hook_set_id", 0), "controller.hookSetId"),
        )


@dataclass(frozen=True)
class SpawnPolicy:
    stable_id: int
    presentation: str = "NONE"
    destination: str = "NONE"
    minimum_distance: int = 1
    maximum_distance: int = 1
    hop_time_per_tile: int = 0

    def values(self) -> dict[str, Any]:
        result = to_data(self)
        result.pop("stableId")
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SpawnPolicy":
        data = _closed_mapping(data, "spawnPolicy", (field_.name for field_ in dataclasses.fields(cls)))
        return cls(
            _id(_read(data, "stable_id"), "spawnPolicy.stableId"),
            _symbol(_read(data, "presentation", "NONE"), "spawnPolicy.presentation"), _symbol(_read(data, "destination", "NONE"), "spawnPolicy.destination"),
            _u8(_read(data, "minimum_distance", 1), "spawnPolicy.minimumDistance"), _u8(_read(data, "maximum_distance", 1), "spawnPolicy.maximumDistance"),
            _u8(_read(data, "hop_time_per_tile", 0), "spawnPolicy.hopTimePerTile"),
        )


@dataclass(frozen=True)
class PopulationPolicy:
    stable_id: int
    population_group_id: int
    limit: int = 0

    def values(self) -> dict[str, Any]:
        result = to_data(self)
        result.pop("stableId")
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PopulationPolicy":
        data = _closed_mapping(data, "populationPolicy", (field_.name for field_ in dataclasses.fields(cls)))
        return cls(
            _id(_read(data, "stable_id"), "populationPolicy.stableId"),
            _id(_read(data, "population_group_id"), "populationPolicy.populationGroupId"),
            _u8(_read(data, "limit", 0), "populationPolicy.limit"),
        )


@dataclass(frozen=True)
class HookSet:
    stable_id: int
    hooks: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HookSet":
        data = _closed_mapping(data, "hookSet", (field_.name for field_ in dataclasses.fields(cls)))
        return cls(_id(_read(data, "stable_id"), "hookSet.stableId"), tuple(_symbol(item, "hookSet.hook") for item in _sequence(_read(data, "hooks", ()), "hookSet.hooks")))


@dataclass(frozen=True)
class PolicyPatch:
    stable_id: int
    operations: Mapping[str, "ModifierOperation"]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PolicyPatch":
        data = _closed_mapping(data, "policyPatch", (field_.name for field_ in dataclasses.fields(cls)))
        operations = _mapping(_read(data, "operations", {}), "policyPatch.operations")
        assert operations is not None
        return cls(
            _id(_read(data, "stable_id"), "policyPatch.stableId"),
            {
                _symbol(name, "policyPatch.operationPath"): ModifierOperation.from_dict(item)
                for name, item in _exact_mapping_items(operations, "policyPatch.operations", (str,))
            },
        )


@dataclass(frozen=True)
class NodeSelector:
    kind: SelectorKind
    controller_id: int = 0
    node_id: int = 0
    role: SemanticRole | None = None
    custom_role_id: int = 0

    def __post_init__(self) -> None:
        if type(self.kind) is not SelectorKind or any(type(value) is not int for value in (self.controller_id, self.node_id, self.custom_role_id)):
            raise ModelError(Status.INVALID_STATIC_DATA, "selector discriminant and IDs must be canonical typed values")
        if self.kind is SelectorKind.EXACT:
            if not 1 <= self.controller_id <= 0xFFFF or not 1 <= self.node_id <= 0xFFFF or self.role is not None or self.custom_role_id != 0:
                raise ModelError(Status.INVALID_STATIC_DATA, "EXACT selector payload is outside its closed tagged union")
            return
        if self.controller_id != 0 or self.node_id != 0 or type(self.role) is not SemanticRole or not 0 <= self.custom_role_id <= 0xFFFF:
            raise ModelError(Status.INVALID_STATIC_DATA, "SEMANTIC selector payload is outside its closed tagged union")
        if self.role is SemanticRole.CUSTOM and self.custom_role_id == 0 or self.role is not SemanticRole.CUSTOM and self.custom_role_id != 0:
            raise ModelError(Status.INVALID_STATIC_DATA, "semantic CUSTOM/customRoleId tag pair is noncanonical")

    @classmethod
    def exact(cls, controller_id: int, node_id: int) -> "NodeSelector":
        return cls(SelectorKind.EXACT, controller_id, node_id)

    @classmethod
    def semantic(cls, role: SemanticRole, custom_role_id: int = 0) -> "NodeSelector":
        return cls(SelectorKind.SEMANTIC, role=role, custom_role_id=custom_role_id)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NodeSelector":
        data = _mapping(data, "selector")
        assert data is not None
        _reject_unknown_fields(data, "selector", ("kind", "controller_id", "node_id", "role", "custom_role_id"))
        kind = _enum_value(SelectorKind, _read(data, "kind"), "selector.kind")
        if kind is SelectorKind.EXACT:
            if _present(data, "role") or _present(data, "custom_role_id"):
                raise ModelError(Status.INVALID_STATIC_DATA, "exact selector carries semantic-only payload")
            return cls.exact(_id(_read(data, "controller_id"), "selector.controllerId"), _id(_read(data, "node_id"), "selector.nodeId"))
        if _present(data, "controller_id") or _present(data, "node_id"):
            raise ModelError(Status.INVALID_STATIC_DATA, "semantic selector carries exact-only payload")
        role = _enum_value(SemanticRole, _read(data, "role"), "selector.role")
        custom_role_id = _u16(_read(data, "custom_role_id", 0), "selector.customRoleId", nonzero=role is SemanticRole.CUSTOM)
        if role is not SemanticRole.CUSTOM and custom_role_id != 0:
            raise ModelError(Status.INVALID_STATIC_DATA, "non-CUSTOM semantic selector carries customRoleId")
        return cls.semantic(role, custom_role_id)


@dataclass(frozen=True)
class ModifierOperation:
    kind: OperatorKind
    value: Any
    bound: Any = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ModifierOperation":
        data = _closed_mapping(data, "modifierOperation", (field_.name for field_ in dataclasses.fields(cls)))
        return cls(_enum_value(OperatorKind, _read(data, "kind"), "modifierOperation.kind"), _read(data, "value"), _read(data, "bound"))


@dataclass(frozen=True)
class Modifier:
    stable_id: int
    operations: Mapping[str, ModifierOperation]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Modifier":
        data = _closed_mapping(data, "modifier", (field_.name for field_ in dataclasses.fields(cls)))
        operations = _mapping(_read(data, "operations", {}), "modifier.operations")
        assert operations is not None
        return cls(
            _id(_read(data, "stable_id"), "modifier.stableId"),
            {
                _symbol(name, "modifier.operationPath"): ModifierOperation.from_dict(item)
                for name, item in _exact_mapping_items(operations, "modifier.operations", (str,))
            },
        )


@dataclass(frozen=True)
class Applicability:
    context: ContextMatcher = ContextMatcher()
    controller_ids: frozenset[int] = frozenset()
    state_profile_ids: frozenset[int] = frozenset()
    role_mask: frozenset[SemanticRole] = frozenset()

    def immutable_matches(self, context: StaticContext, controller_id: int) -> bool:
        return self.context.matches(context) and (not self.controller_ids or controller_id in self.controller_ids)

    def modifier_matches(self, context: StaticContext, controller_id: int, profile_id: int, role: SemanticRole) -> bool:
        return (
            self.immutable_matches(context, controller_id)
            and (not self.state_profile_ids or profile_id in self.state_profile_ids)
            and (not self.role_mask or role in self.role_mask)
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "Applicability":
        if data is None:
            data = {}
        data = _closed_mapping(data, "definition.applicability", (field_.name for field_ in dataclasses.fields(cls)))
        context = _read(data, "context", None)
        return cls(
            ContextMatcher.from_dict(context),
            _typed_set(_read(data, "controller_ids", ()), "applicability.controllerIds", lambda value: _u16(value, "applicability.controllerId", nonzero=True)),
            _typed_set(_read(data, "state_profile_ids", ()), "applicability.stateProfileIds", lambda value: _u16(value, "applicability.stateProfileId", nonzero=True)),
            _typed_set(_read(data, "role_mask", ()), "applicability.roleMask", lambda value: _enum_value(SemanticRole, value, "applicability.roleMask")),
        )


@dataclass(frozen=True)
class GeneratedMetadata:
    has_tired_origin_kind: bool = False
    tired_origin_kind: TiredOriginKind | None = None
    has_required_owner_id: bool = False
    required_owner_id: int = 0

    def __post_init__(self) -> None:
        if type(self.has_tired_origin_kind) is not bool or type(self.has_required_owner_id) is not bool:
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "generated metadata presence tags must be booleans")
        if self.has_tired_origin_kind != (type(self.tired_origin_kind) is TiredOriginKind):
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "generated tired origin tag/value is noncanonical")
        if type(self.required_owner_id) is not int or self.has_required_owner_id and not 1 <= self.required_owner_id <= 0xFFFF or not self.has_required_owner_id and self.required_owner_id != 0:
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "generated required owner tag/value is noncanonical")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "GeneratedMetadata":
        if data is None:
            data = {}
        data = _closed_mapping(data, "definition.generated", (field_.name for field_ in dataclasses.fields(cls)), status=Status.INVALID_GENERATED_WRAPPER)
        has_origin = _read(data, "has_tired_origin_kind", False)
        has_owner = _read(data, "has_required_owner_id", False)
        if type(has_origin) is not bool or type(has_owner) is not bool:
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "generated metadata presence tags must be JSON booleans")
        origin = _read(data, "tired_origin_kind")
        if origin is None:
            parsed_origin = None
        elif type(origin) is str:
            parsed_origin = _enum_value(TiredOriginKind, origin, "generated.tiredOriginKind", status=Status.INVALID_GENERATED_WRAPPER)
        else:
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "generated tiredOriginKind must be a canonical name string or null")
        return cls(
            has_origin,
            parsed_origin,
            has_owner,
            _u16(_read(data, "required_owner_id", 0), "generated.requiredOwnerId"),
        )


@dataclass(frozen=True)
class CandidateTimerPolicy:
    duration: int
    clock: TimerClock = TimerClock.FRAME
    hidden_policy: HiddenPolicy = HiddenPolicy.PAUSE_WHILE_HIDDEN
    recovery_policy: RecoveryPolicy = RecoveryPolicy.REMOVE_SELF
    calm_reset_owner_ids: tuple[int, ...] = ()
    recovery_transition_id: int = 0
    duration_policy: TimerDurationPolicy = TimerDurationPolicy.LEGACY_REST_TIME

    def __post_init__(self) -> None:
        if type(self.duration) is not int or not 0 <= self.duration <= 255 or type(self.recovery_transition_id) is not int or not 0 <= self.recovery_transition_id <= 0xFFFF or type(self.clock) is not TimerClock or type(self.hidden_policy) is not HiddenPolicy or type(self.recovery_policy) is not RecoveryPolicy or type(self.duration_policy) is not TimerDurationPolicy:
            raise ModelError(Status.INVALID_STATIC_DATA, "candidate timer scalar fields are noncanonical")
        if type(self.calm_reset_owner_ids) not in {tuple, list} or any(type(owner) is not int or not 1 <= owner <= 0xFFFF for owner in self.calm_reset_owner_ids) or len(self.calm_reset_owner_ids) != len(set(self.calm_reset_owner_ids)):
            raise ModelError(Status.INVALID_STATIC_DATA, "candidate timer calm-reset owners are noncanonical")
        object.__setattr__(self, "calm_reset_owner_ids", tuple(self.calm_reset_owner_ids))
        if self.duration_policy is TimerDurationPolicy.INDEFINITE and self.duration != 255:
            raise ModelError(Status.INVALID_STATIC_DATA, "explicit indefinite timer requires canonical duration 255")
        if self.duration_policy is TimerDurationPolicy.FINITE and self.duration == 255:
            raise ModelError(Status.INVALID_STATIC_DATA, "explicit finite timer cannot carry duration 255")
        if self.recovery_policy is not RecoveryPolicy.LEGACY_RETURN_CALM and self.calm_reset_owner_ids:
            raise ModelError(Status.INVALID_STATIC_DATA, "non-LRC recovery cannot carry calm-reset owners")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "CandidateTimerPolicy | None":
        if data is None:
            return None
        data = _mapping(data, "definition.timer")
        assert data is not None
        _reject_unknown_fields(data, "definition.timer", (
            "duration", "clock", "hidden_policy", "recovery_policy",
            "calm_reset_owner_ids", "recovery_transition_id", "duration_policy",
        ))
        try:
            return cls(
                _u8(_read(data, "duration"), "candidateTimer.duration"),
                _enum_value(TimerClock, _read(data, "clock", TimerClock.FRAME.value), "candidateTimer.clock"),
                _enum_value(HiddenPolicy, _read(data, "hidden_policy", HiddenPolicy.PAUSE_WHILE_HIDDEN.value), "candidateTimer.hiddenPolicy"),
                _enum_value(RecoveryPolicy, _read(data, "recovery_policy", RecoveryPolicy.REMOVE_SELF.value), "candidateTimer.recoveryPolicy"),
                tuple(_u16(value, "candidateTimer.calmResetOwnerId", nonzero=True) for value in _sequence(_read(data, "calm_reset_owner_ids", ()), "candidateTimer.calmResetOwnerIds")),
                _u16(_read(data, "recovery_transition_id", 0), "candidateTimer.recoveryTransitionId"),
                _enum_value(TimerDurationPolicy, _read(data, "duration_policy", TimerDurationPolicy.LEGACY_REST_TIME.value), "candidateTimer.durationPolicy"),
            )
        except (TypeError, ValueError) as exc:
            raise ModelError(Status.INVALID_STATIC_DATA, f"candidate timer carries an unknown enum/discriminator: {exc}") from exc


@dataclass(frozen=True)
class OverrideDefinition:
    stable_id: int
    kind: DefinitionKind
    channel: Channel
    priority: int
    applicability: Applicability = Applicability()
    map_policy: LifetimePolicy = LifetimePolicy.CLEAR
    battle_policy: LifetimePolicy = LifetimePolicy.CLEAR
    allow_multiple_owners: bool = False
    allow_multiple_instances_per_owner: bool = False
    selector: NodeSelector | None = None
    modifier_id: int = 0
    timer: CandidateTimerPolicy | None = None
    generated: GeneratedMetadata = GeneratedMetadata()

    def precedence_key(self, owner_id: int, instance_key: int) -> tuple[int, int, int, int, int]:
        return (int(self.channel), self.priority, self.stable_id, owner_id, instance_key)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "OverrideDefinition":
        data = _closed_mapping(data, "definition", (field_.name for field_ in dataclasses.fields(cls)))
        selector_data = _read(data, "selector")
        if selector_data is not None:
            selector_data = _mapping(selector_data, "definition.selector")
        applicability_data = _read(data, "applicability", None)
        generated_data = _read(data, "generated", None)
        timer_data = _read(data, "timer", None)
        return cls(
            _id(_read(data, "stable_id"), "definition.stableId"),
            _enum_value(DefinitionKind, _read(data, "kind"), "definition.kind"),
            _enum_value(Channel, _read(data, "channel"), "definition.channel"),
            _u8(_read(data, "priority"), "definition.priority"),
            Applicability.from_dict(applicability_data),
            _enum_value(LifetimePolicy, _read(data, "map_policy", LifetimePolicy.CLEAR.value), "definition.mapPolicy"),
            _enum_value(LifetimePolicy, _read(data, "battle_policy", LifetimePolicy.CLEAR.value), "definition.battlePolicy"),
            _boolean(_read(data, "allow_multiple_owners", False), "definition.allowMultipleOwners"),
            _boolean(_read(data, "allow_multiple_instances_per_owner", False), "definition.allowMultipleInstancesPerOwner"),
            NodeSelector.from_dict(selector_data) if selector_data is not None else None,
            _u16(_read(data, "modifier_id", 0), "definition.modifierId"),
            CandidateTimerPolicy.from_dict(timer_data),
            GeneratedMetadata.from_dict(generated_data),
        )


@dataclass(frozen=True)
class StaticAction:
    stable_id: int
    kind: StaticActionKind
    assignment_priority: int = 0
    static_priority: int = 0
    controller_id: int = 0
    node_id: int = 0
    candidate_definition_id: int = 0
    profile_id: int = 0
    modifier_id: int = 0
    spawn_policy_id: int = 0
    spawn_policy_patch_id: int = 0
    population_policy_id: int = 0
    population_policy_patch_id: int = 0
    hook_set_id: int = 0
    role_mask: frozenset[SemanticRole] = frozenset()
    timer_operation: ModifierOperation | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StaticAction":
        data = _closed_mapping(data, "staticAction", (field_.name for field_ in dataclasses.fields(cls)))
        timer = _read(data, "timer_operation")
        if timer is not None:
            timer = _mapping(timer, "staticAction.timerOperation")
        return cls(
            _id(_read(data, "stable_id"), "staticAction.stableId"),
            _enum_value(StaticActionKind, _read(data, "kind"), "staticAction.kind"),
            _u16(_read(data, "assignment_priority", 0), "staticAction.assignmentPriority"), _u16(_read(data, "static_priority", 0), "staticAction.staticPriority"),
            _u16(_read(data, "controller_id", 0), "staticAction.controllerId"), _u16(_read(data, "node_id", 0), "staticAction.nodeId"),
            _u16(_read(data, "candidate_definition_id", 0), "staticAction.candidateDefinitionId"),
            _u16(_read(data, "profile_id", 0), "staticAction.profileId"), _u16(_read(data, "modifier_id", 0), "staticAction.modifierId"),
            _u16(_read(data, "spawn_policy_id", 0), "staticAction.spawnPolicyId"), _u16(_read(data, "spawn_policy_patch_id", 0), "staticAction.spawnPolicyPatchId"),
            _u16(_read(data, "population_policy_id", 0), "staticAction.populationPolicyId"), _u16(_read(data, "population_policy_patch_id", 0), "staticAction.populationPolicyPatchId"),
            _u16(_read(data, "hook_set_id", 0), "staticAction.hookSetId"),
            _typed_set(_read(data, "role_mask", ()), "staticAction.roleMask", lambda item: _enum_value(SemanticRole, item, "staticAction.roleMask")),
            ModifierOperation.from_dict(timer) if timer is not None else None,
        )


@dataclass(frozen=True)
class StaticRule:
    stable_id: int
    matcher: ContextMatcher
    actions: tuple[StaticAction, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StaticRule":
        data = _closed_mapping(data, "staticRule", (field_.name for field_ in dataclasses.fields(cls)))
        return cls(
            _id(_read(data, "stable_id"), "staticRule.stableId"),
            ContextMatcher.from_dict(_read(data, "matcher", {})),
            tuple(StaticAction.from_dict(item) for item in _sequence(_read(data, "actions", ()), "staticRule.actions")),
        )


@dataclass(frozen=True)
class TiredTranslation:
    origin: TiredOriginKind
    destination_controller_id: int
    authored_tired_bound: bool
    definition_id: int


@dataclass(frozen=True)
class BehaviorCatalog:
    state_profiles: dict[int, StateProfile]
    controllers: dict[int, Controller]
    modifiers: dict[int, Modifier]
    definitions: dict[int, OverrideDefinition]
    static_rules: tuple[StaticRule, ...] = ()
    default_controller_id: int = 0
    spawn_policies: dict[int, SpawnPolicy] = field(default_factory=dict)
    population_policies: dict[int, PopulationPolicy] = field(default_factory=dict)
    hook_sets: dict[int, HookSet] = field(default_factory=dict)
    spawn_policy_patches: dict[int, PolicyPatch] = field(default_factory=dict)
    population_policy_patches: dict[int, PolicyPatch] = field(default_factory=dict)
    tired_translations: tuple[TiredTranslation, ...] = ()
    owner_names: dict[int, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self) is not BehaviorCatalog:
            raise ModelError(Status.INVALID_STATIC_DATA, "catalog construction requires an exact BehaviorCatalog")
        try:
            _validate_closed_runtime_graph(self, "catalog.constructorInput")
        except ModelError:
            raise ModelError(Status.INVALID_STATIC_DATA, "catalog constructor mappings are not closed canonical storage") from None
        storage = object.__getattribute__(self, "__dict__")
        registry_types = {
            "state_profiles": StateProfile, "controllers": Controller,
            "modifiers": Modifier, "definitions": OverrideDefinition,
            "spawn_policies": SpawnPolicy, "population_policies": PopulationPolicy,
            "hook_sets": HookSet, "spawn_policy_patches": PolicyPatch,
            "population_policy_patches": PolicyPatch,
        }
        registry_items: dict[str, tuple[tuple[Any, Any], ...]] = {}
        for field_name, value_type in registry_types.items():
            items = _exact_mapping_items(storage[field_name], f"catalog.{_camel(field_name)}", (int,))
            if any(type(item) is not value_type for _key, item in items):
                raise ModelError(Status.INVALID_STATIC_DATA, f"catalog.{_camel(field_name)} contains a noncanonical value")
            registry_items[field_name] = items
        owner_items = _exact_mapping_items(storage["owner_names"], "catalog.ownerNames", (int,))
        if any(type(value) is not str for _key, value in owner_items):
            raise ModelError(Status.INVALID_STATIC_DATA, "catalog.ownerNames contains a noncanonical value")
        for controller in (value for _key, value in registry_items["controllers"]):
            object.__setattr__(controller, "nodes", tuple(controller.nodes))
        for hook_set in (value for _key, value in registry_items["hook_sets"]):
            object.__setattr__(hook_set, "hooks", tuple(hook_set.hooks))
        for definition in (value for _key, value in registry_items["definitions"]):
            applicability = definition.applicability
            object.__setattr__(applicability, "controller_ids", frozenset(applicability.controller_ids))
            object.__setattr__(applicability, "state_profile_ids", frozenset(applicability.state_profile_ids))
            object.__setattr__(applicability, "role_mask", frozenset(applicability.role_mask))
            if definition.timer is not None:
                object.__setattr__(definition.timer, "calm_reset_owner_ids", tuple(definition.timer.calm_reset_owner_ids))
        for rule in storage["static_rules"]:
            object.__setattr__(rule, "actions", tuple(rule.actions))
            for action in rule.actions:
                object.__setattr__(action, "role_mask", frozenset(action.role_mask))
                if action.timer_operation is not None:
                    object.__setattr__(action.timer_operation, "value", _deep_freeze(action.timer_operation.value))
                    object.__setattr__(action.timer_operation, "bound", _deep_freeze(action.timer_operation.bound))
        for modifier in (value for _key, value in registry_items["modifiers"]):
            modifier_operations = _exact_mapping_items(modifier.operations, "modifier.operations", (str,))
            for _path, operation in modifier_operations:
                object.__setattr__(operation, "value", _deep_freeze(operation.value))
                object.__setattr__(operation, "bound", _deep_freeze(operation.bound))
            object.__setattr__(modifier, "operations", ClosedMap(modifier_operations))
        patch_values = tuple(value for _key, value in registry_items["spawn_policy_patches"]) + tuple(value for _key, value in registry_items["population_policy_patches"])
        for patch in patch_values:
            patch_operations = _exact_mapping_items(patch.operations, "policyPatch.operations", (str,))
            for _path, operation in patch_operations:
                object.__setattr__(operation, "value", _deep_freeze(operation.value))
                object.__setattr__(operation, "bound", _deep_freeze(operation.bound))
            object.__setattr__(patch, "operations", ClosedMap(patch_operations))
        for field_name, items in registry_items.items():
            object.__setattr__(self, field_name, ClosedMap(items))
        object.__setattr__(self, "owner_names", ClosedMap(owner_items))
        object.__setattr__(self, "static_rules", tuple(storage["static_rules"]))
        object.__setattr__(self, "tired_translations", tuple(storage["tired_translations"]))
        BehaviorCatalog.validate(self)

    def validate(self) -> None:
        if type(self) is not BehaviorCatalog:
            raise ModelError(Status.INVALID_STATIC_DATA, "catalog validation requires an exact BehaviorCatalog")
        try:
            _validate_closed_runtime_graph(self, "catalog.validateInput")
        except ModelError:
            raise ModelError(Status.INVALID_STATIC_DATA, "catalog validation mappings are not closed canonical storage") from None
        _validate_registry("stateProfiles", self.state_profiles)
        _validate_registry("controllers", self.controllers)
        _validate_registry("modifiers", self.modifiers)
        _validate_registry("definitions", self.definitions)
        _validate_registry("spawnPolicies", self.spawn_policies)
        _validate_registry("populationPolicies", self.population_policies)
        _validate_registry("hookSets", self.hook_sets)
        _validate_registry("spawnPolicyPatches", self.spawn_policy_patches)
        _validate_registry("populationPolicyPatches", self.population_policy_patches)
        if any(type(owner_id) is not int or not 1 <= owner_id <= 0xFFFF or not isinstance(owner_name, str) for owner_id, owner_name in self.owner_names.items()):
            raise ModelError(Status.INVALID_STATIC_DATA, "owner registry IDs must be nonzero u16 values")
        if len(self.owner_names.values()) != len(set(self.owner_names.values())):
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "owner display names must be unique and cannot launder generated authorization")
        for spec in GENERATED_FAMILY_SPECS.values():
            if self.owner_names.get(spec["owner_id"]) != spec["owner_name"]:
                raise ModelError(Status.INVALID_GENERATED_WRAPPER, "frozen generated owner ID/name registry is incomplete")
        if self.default_controller_id and self.default_controller_id not in self.controllers:
            raise ModelError(Status.INVALID_STATIC_DATA, "default controller is missing")
        for profile in self.state_profiles.values():
            _validate_state_profile(profile)
        for modifier in self.modifiers.values():
            if not modifier.operations:
                raise ModelError(Status.INVALID_STATIC_DATA, f"modifier {modifier.stable_id} is empty")
            for path, operation in modifier.operations.items():
                _validate_operation(path, operation, runtime=True)
        for policy in self.spawn_policies.values():
            if type(policy.presentation) is not str or type(policy.destination) is not str or any(type(value) is not int for value in (policy.minimum_distance, policy.maximum_distance, policy.hop_time_per_tile)) or policy.presentation not in SPAWN_PRESENTATIONS or policy.destination not in SPAWN_DESTINATIONS or not 1 <= policy.minimum_distance <= policy.maximum_distance <= 8 or not 0 <= policy.hop_time_per_tile <= 64:
                raise ModelError(Status.INVALID_STATIC_DATA, f"spawn policy {policy.stable_id} is invalid")
        for policy in self.population_policies.values():
            if type(policy.population_group_id) is not int or type(policy.limit) is not int or not 1 <= policy.population_group_id <= 0xFFFF or not 0 <= policy.limit <= 10:
                raise ModelError(Status.INVALID_STATIC_DATA, f"population policy {policy.stable_id} is invalid")
        for hook_set in self.hook_sets.values():
            if len(hook_set.hooks) != len(set(hook_set.hooks)) or any(type(hook) is not str or hook not in HOOK_VALUES for hook in hook_set.hooks):
                raise ModelError(Status.INVALID_STATIC_DATA, f"hook set {hook_set.stable_id} contains invalid hooks")
        for patch in self.spawn_policy_patches.values():
            for path, operation in patch.operations.items():
                if not path.startswith("spawn."):
                    raise ModelError(Status.INVALID_STATIC_DATA, f"spawn patch {patch.stable_id} targets {path}")
                _validate_operation(path, operation, runtime=False)
        for patch in self.population_policy_patches.values():
            for path, operation in patch.operations.items():
                if not path.startswith("population."):
                    raise ModelError(Status.INVALID_STATIC_DATA, f"population patch {patch.stable_id} targets {path}")
                _validate_operation(path, operation, runtime=False)
        for controller in self.controllers.values():
            if type(controller.base_node_id) is not int or controller.stable_id == 0 or len({node.stable_id for node in controller.nodes}) != len(controller.nodes) or any(type(node.stable_id) is not int or not 1 <= node.stable_id <= 0xFFFF for node in controller.nodes):
                raise ModelError(Status.INVALID_STATIC_DATA, "controller/node IDs must be nonzero and unique")
            base = controller.node(controller.base_node_id)
            if base is None or base.state_profile_id is None:
                raise ModelError(Status.INVALID_STATIC_DATA, f"controller {controller.stable_id} base is unbound")
            for node in controller.nodes:
                if type(node.custom_role_id) is not int or node.state_profile_id is not None and type(node.state_profile_id) is not int or not 0 <= node.custom_role_id <= 0xFFFF:
                    raise ModelError(Status.INVALID_STATIC_DATA, f"node {node.stable_id} customRoleId is outside u16")
                if node.role is not SemanticRole.CUSTOM and node.custom_role_id != 0:
                    raise ModelError(Status.INVALID_STATIC_DATA, f"non-CUSTOM node {node.stable_id} has customRoleId")
                if node.role is SemanticRole.CUSTOM and node.custom_role_id == 0:
                    raise ModelError(Status.INVALID_STATIC_DATA, f"CUSTOM node {node.stable_id} requires customRoleId")
                if node.state_profile_id is not None and node.state_profile_id not in self.state_profiles:
                    raise ModelError(Status.INVALID_STATIC_DATA, f"node {node.stable_id} profile is missing")
            _validate_controller_values(controller.defaults)
            if controller.spawn_policy_id not in self.spawn_policies:
                raise ModelError(Status.INVALID_STATIC_DATA, f"controller {controller.stable_id} spawn policy is missing")
            if controller.population_policy_id not in self.population_policies:
                raise ModelError(Status.INVALID_STATIC_DATA, f"controller {controller.stable_id} population policy is missing")
            if controller.hook_set_id not in self.hook_sets:
                raise ModelError(Status.INVALID_STATIC_DATA, f"controller {controller.stable_id} hook set is missing")
        for definition in self.definitions.values():
            if type(definition.priority) is not int or not 0 <= definition.priority <= 0xFF:
                raise ModelError(Status.INVALID_STATIC_DATA, "definition priority is outside u8")
            if definition.channel is Channel.SYSTEM_SAFETY and not (definition.generated.has_tired_origin_kind or definition.generated.has_required_owner_id):
                raise ModelError(Status.INVALID_STATIC_DATA, "ordinary authored definitions cannot use SYSTEM_SAFETY")
            if any(not isinstance(role, SemanticRole) for role in definition.applicability.role_mask) or any(type(controller_id) is not int or controller_id not in self.controllers for controller_id in definition.applicability.controller_ids) or any(type(profile_id) is not int or profile_id not in self.state_profiles for profile_id in definition.applicability.state_profile_ids):
                raise ModelError(Status.INVALID_STATIC_DATA, f"definition {definition.stable_id} applicability is dangling")
            if definition.kind is DefinitionKind.STATE_CANDIDATE:
                if definition.selector is None or definition.modifier_id or definition.applicability.state_profile_ids or definition.applicability.role_mask:
                    raise ModelError(Status.INVALID_STATIC_DATA, "candidate must have selector and no modifier")
                _validate_selector_totality(definition, self.controllers)
                if definition.timer is not None:
                    if type(definition.timer.duration) is not int or type(definition.timer.recovery_transition_id) is not int or type(definition.timer.clock) is not TimerClock or type(definition.timer.hidden_policy) is not HiddenPolicy or type(definition.timer.recovery_policy) is not RecoveryPolicy or type(definition.timer.duration_policy) is not TimerDurationPolicy or not 0 <= definition.timer.duration <= 255 or not 0 <= definition.timer.recovery_transition_id <= 0xFFFF or len(set(definition.timer.calm_reset_owner_ids)) != len(definition.timer.calm_reset_owner_ids) or any(type(owner) is not int or not 1 <= owner <= 0xFFFF for owner in definition.timer.calm_reset_owner_ids):
                        raise ModelError(Status.INVALID_STATIC_DATA, f"definition {definition.stable_id} timer is invalid")
                    if definition.timer.duration_policy is TimerDurationPolicy.INDEFINITE:
                        if definition.timer.duration != 255 or definition.selector is None or not _selector_is_asleep(definition.selector, self.controllers):
                            raise ModelError(Status.INVALID_STATIC_DATA, "explicit indefinite timer requires ASLEEP selector and canonical duration 255")
                    if definition.timer.duration_policy is TimerDurationPolicy.FINITE and definition.timer.duration == 255:
                        raise ModelError(Status.INVALID_STATIC_DATA, "explicit finite timer cannot use the indefinite duration 255")
                    if definition.timer.recovery_policy is RecoveryPolicy.LEGACY_RETURN_CALM and tuple(definition.timer.calm_reset_owner_ids) != CALM_RESET_OWNER_IDS:
                        raise ModelError(Status.INVALID_STATIC_DATA, "LEGACY_RETURN_CALM requires the exact mandatory calm-reset owner batch")
                    if definition.timer.recovery_policy is RecoveryPolicy.LEGACY_RETURN_CALM and definition.selector is not None and _selector_is_asleep(definition.selector, self.controllers):
                        raise ModelError(Status.INVALID_STATIC_DATA, "ASLEEP candidates cannot use tired LEGACY_RETURN_CALM recovery")
            elif definition.modifier_id not in self.modifiers or definition.selector is not None or definition.timer is not None:
                raise ModelError(Status.INVALID_STATIC_DATA, "modifier definition must have one modifier and no selector")
            _validate_generated_definition(definition, self.owner_names)
            if definition.generated.has_tired_origin_kind and definition.selector and definition.selector.kind is SelectorKind.EXACT:
                controller = self.controllers[definition.selector.controller_id]
                node = controller.node(definition.selector.node_id)
                if node is None or node.role is not SemanticRole.CUSTOM:
                    raise ModelError(Status.INVALID_GENERATED_WRAPPER, "generated exact tired fallback must target a CUSTOM node")
        rule_ids = [rule.stable_id for rule in self.static_rules]
        if len(rule_ids) != len(set(rule_ids)) or any(type(rule_id) is not int or not 1 <= rule_id <= 0xFFFF for rule_id in rule_ids):
            raise ModelError(Status.INVALID_STATIC_DATA, "static rule IDs must be nonzero and unique")
        action_ids: set[int] = set()
        ordering_keys: set[tuple[int, int, int, str]] = set()
        for rule in self.static_rules:
            for action in rule.actions:
                scalar_ids = (action.stable_id, action.assignment_priority, action.static_priority, action.controller_id, action.node_id, action.candidate_definition_id, action.profile_id, action.modifier_id, action.spawn_policy_id, action.spawn_policy_patch_id, action.population_policy_id, action.population_policy_patch_id, action.hook_set_id)
                if any(type(value) is not int for value in scalar_ids) or not 1 <= action.stable_id <= 0xFFFF or not 0 <= action.assignment_priority <= 0xFFFF or not 0 <= action.static_priority <= 0xFFFF:
                    raise ModelError(Status.INVALID_STATIC_DATA, "static action ID/priority is outside u16")
                if action.stable_id in action_ids:
                    raise ModelError(Status.INVALID_STATIC_DATA, f"duplicate static action ID {action.stable_id}")
                action_ids.add(action.stable_id)
                priority = action.assignment_priority if action.kind is StaticActionKind.ASSIGN_CONTROLLER else action.static_priority
                order_key = (priority, rule.stable_id, action.stable_id, "assignment" if action.kind is StaticActionKind.ASSIGN_CONTROLLER else "static")
                if order_key in ordering_keys:
                    raise ModelError(Status.INVALID_STATIC_DATA, f"duplicate static ordering key {order_key}")
                ordering_keys.add(order_key)
                self._validate_static_action(action)
        seen: set[tuple[TiredOriginKind, int, bool]] = set()
        for row in self.tired_translations:
            if not isinstance(row.origin, TiredOriginKind) or type(row.destination_controller_id) is not int or type(row.authored_tired_bound) is not bool or type(row.definition_id) is not int:
                raise ModelError(Status.INVALID_STATIC_DATA, "tired translation scalar types are noncanonical")
            key = (row.origin, row.destination_controller_id, row.authored_tired_bound)
            if key in seen:
                raise ModelError(Status.INVALID_STATIC_DATA, f"duplicate tired translation {key}")
            seen.add(key)
            _validate_translation_row(row, self)
        generated_definitions = [definition for definition in self.definitions.values() if definition.generated.has_tired_origin_kind or definition.generated.has_required_owner_id]
        stamina_definitions = [definition for definition in generated_definitions if not definition.generated.has_tired_origin_kind]
        if len(stamina_definitions) != 1 or not any(definition.selector is not None and definition.selector.kind is SelectorKind.SEMANTIC and definition.selector.role is SemanticRole.TIRED and not definition.applicability.controller_ids and _matcher_is_total(definition.applicability.context) for definition in stamina_definitions):
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "phase-0 catalog is missing the generated stamina family")
        for origin in TiredOriginKind:
            origin_definitions = [definition for definition in generated_definitions if definition.generated.tired_origin_kind is origin]
            if not origin_definitions or not any(definition.selector is not None and definition.selector.kind is SelectorKind.SEMANTIC and definition.selector.role is SemanticRole.TIRED and not definition.applicability.controller_ids for definition in origin_definitions):
                raise ModelError(Status.INVALID_GENERATED_WRAPPER, f"phase-0 catalog is missing the complete {origin.name} family")
            expected_keys = {(origin, controller.stable_id, authored_bound) for controller in self.controllers.values() for authored_bound in _reachable_authored_tired_states(self, controller)}
            actual_keys = {key for key in seen if key[0] is origin}
            if actual_keys != expected_keys:
                raise ModelError(Status.INVALID_TRANSLATION, f"{origin.name} translation closure is missing or extraneous")
            referenced_ids = {row.definition_id for row in self.tired_translations if row.origin is origin}
            family_ids = {definition.stable_id for definition in origin_definitions}
            if referenced_ids != family_ids:
                raise ModelError(Status.INVALID_GENERATED_WRAPPER, f"{origin.name} contains unreferenced or missing generated wrappers")
        family_timers: dict[tuple[Any, ...], set[bytes]] = {}
        for definition in self.definitions.values():
            if definition.generated.has_tired_origin_kind or definition.generated.has_required_owner_id:
                family_timers.setdefault(_generated_family(definition.generated), set()).add(canonical_json_bytes(definition.timer))
        if any(len(timers) != 1 for timers in family_timers.values()):
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "generated wrapper family timer/recovery metadata differs")
        fallback_addresses = {
            (target.selector.controller_id, target.selector.node_id): self.controllers[target.selector.controller_id].node(target.selector.node_id).state_profile_id
            for row in self.tired_translations if not row.authored_tired_bound
            for target in (self.definitions[row.definition_id],)
            if target.selector is not None and target.selector.kind is SelectorKind.EXACT
        }
        if any(
            (action.kind is StaticActionKind.UNBIND_NODE or action.kind is StaticActionKind.BIND_NODE and action.profile_id != fallback_addresses[(action.controller_id, action.node_id)])
            for rule in self.static_rules for action in rule.actions if (action.controller_id, action.node_id) in fallback_addresses
        ):
            raise ModelError(Status.INVALID_TRANSLATION, "static data can unbind or rebind an imperative tired fallback node")
        for origin in TiredOriginKind:
            for controller in self.controllers.values():
                for authored_bound in _reachable_authored_tired_states(self, controller):
                    if (origin, controller.stable_id, authored_bound) not in seen:
                        raise ModelError(Status.INVALID_STATIC_DATA, f"missing tired translation {(origin, controller.stable_id, authored_bound)}")

    def _validate_static_action(self, action: StaticAction) -> None:
        if action.kind is StaticActionKind.ASSIGN_CONTROLLER and action.static_priority != 0:
            raise ModelError(Status.INVALID_STATIC_DATA, "assignment action cannot carry staticPriority")
        if action.kind is not StaticActionKind.ASSIGN_CONTROLLER and action.assignment_priority != 0:
            raise ModelError(Status.INVALID_STATIC_DATA, "non-assignment action cannot carry assignmentPriority")
        payload_fields = {
            "controller_id": action.controller_id, "node_id": action.node_id, "profile_id": action.profile_id,
            "candidate_definition_id": action.candidate_definition_id,
            "modifier_id": action.modifier_id, "spawn_policy_id": action.spawn_policy_id,
            "spawn_policy_patch_id": action.spawn_policy_patch_id,
            "population_policy_id": action.population_policy_id,
            "population_policy_patch_id": action.population_policy_patch_id,
            "hook_set_id": action.hook_set_id, "role_mask": action.role_mask,
            "timer_operation": action.timer_operation,
        }
        allowed_payloads = {
            StaticActionKind.ASSIGN_CONTROLLER: {"controller_id"},
            StaticActionKind.BIND_NODE: {"controller_id", "node_id", "profile_id"},
            StaticActionKind.UNBIND_NODE: {"controller_id", "node_id"},
            StaticActionKind.APPLY_STATE_MODIFIER: {"controller_id", "modifier_id", "role_mask"},
            StaticActionKind.APPLY_CONTROLLER_MODIFIER: {"controller_id", "modifier_id"},
            StaticActionKind.BIND_SPAWN_POLICY: {"spawn_policy_id"},
            StaticActionKind.APPLY_SPAWN_POLICY_PATCH: {"spawn_policy_patch_id"},
            StaticActionKind.BIND_POPULATION_POLICY: {"population_policy_id"},
            StaticActionKind.APPLY_POPULATION_POLICY_PATCH: {"population_policy_patch_id"},
            StaticActionKind.BIND_HOOK_SET: {"hook_set_id"},
            StaticActionKind.APPLY_CANDIDATE_TIMER_OPERATOR: {"candidate_definition_id", "timer_operation"},
        }[action.kind]
        extras = [name for name, value in payload_fields.items() if name not in allowed_payloads and value not in (0, None, frozenset())]
        if extras:
            raise ModelError(Status.INVALID_STATIC_DATA, f"{action.kind.value} carries forbidden payload fields {extras}")
        if action.kind is StaticActionKind.ASSIGN_CONTROLLER:
            if action.controller_id not in self.controllers:
                raise ModelError(Status.INVALID_STATIC_DATA, "assignment references missing controller")
            return
        controller = self.controllers.get(action.controller_id) if action.controller_id else None
        if action.kind in {StaticActionKind.BIND_NODE, StaticActionKind.UNBIND_NODE}:
            if controller is None or controller.node(action.node_id) is None:
                raise ModelError(Status.INVALID_STATIC_DATA, "static node action has invalid controller/node address")
        if action.kind is StaticActionKind.BIND_NODE and action.profile_id not in self.state_profiles:
            raise ModelError(Status.INVALID_STATIC_DATA, "static binding references missing profile")
        if action.kind is StaticActionKind.UNBIND_NODE and controller and action.node_id == controller.base_node_id:
            raise ModelError(Status.INVALID_STATIC_DATA, "static action cannot unbind base node")
        if action.kind in {StaticActionKind.APPLY_STATE_MODIFIER, StaticActionKind.APPLY_CONTROLLER_MODIFIER} and action.modifier_id not in self.modifiers:
            raise ModelError(Status.INVALID_STATIC_DATA, "static action references missing modifier")
        if action.kind is StaticActionKind.APPLY_STATE_MODIFIER and any(not path.startswith("state.") for path in self.modifiers[action.modifier_id].operations):
            raise ModelError(Status.INVALID_STATIC_DATA, "state modifier action contains non-state fields")
        if action.kind is StaticActionKind.APPLY_CONTROLLER_MODIFIER and any(not path.startswith("controller.") for path in self.modifiers[action.modifier_id].operations):
            raise ModelError(Status.INVALID_STATIC_DATA, "controller modifier action contains non-controller fields")
        if action.kind is StaticActionKind.BIND_SPAWN_POLICY and action.spawn_policy_id not in self.spawn_policies:
            raise ModelError(Status.INVALID_STATIC_DATA, "static action references missing spawn policy")
        if action.kind is StaticActionKind.APPLY_SPAWN_POLICY_PATCH and action.spawn_policy_patch_id not in self.spawn_policy_patches:
            raise ModelError(Status.INVALID_STATIC_DATA, "static action references missing spawn patch")
        if action.kind is StaticActionKind.BIND_POPULATION_POLICY and action.population_policy_id not in self.population_policies:
            raise ModelError(Status.INVALID_STATIC_DATA, "static action references missing population policy")
        if action.kind is StaticActionKind.APPLY_POPULATION_POLICY_PATCH and action.population_policy_patch_id not in self.population_policy_patches:
            raise ModelError(Status.INVALID_STATIC_DATA, "static action references missing population patch")
        if action.kind is StaticActionKind.BIND_HOOK_SET and action.hook_set_id not in self.hook_sets:
            raise ModelError(Status.INVALID_STATIC_DATA, "static action references missing hook set")
        if action.kind is StaticActionKind.APPLY_CANDIDATE_TIMER_OPERATOR and action.timer_operation is None:
            raise ModelError(Status.INVALID_STATIC_DATA, "static timer action has no operator")
        if action.kind is StaticActionKind.APPLY_CANDIDATE_TIMER_OPERATOR:
            definition = self.definitions.get(action.candidate_definition_id)
            if definition is None or definition.kind is not DefinitionKind.STATE_CANDIDATE or definition.timer is None:
                raise ModelError(Status.INVALID_STATIC_DATA, "static timer action must address one timed candidate definition")
            if definition.timer.duration_policy is TimerDurationPolicy.INDEFINITE:
                raise ModelError(Status.INVALID_STATIC_DATA, "explicit indefinite timer cannot carry a numeric static timer operator")
            assert action.timer_operation is not None
            _apply_timer_source(definition.timer.duration, action.timer_operation)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BehaviorCatalog":
        data = _closed_mapping(data, "catalog", (field_.name for field_ in dataclasses.fields(cls)))

        def registry(name: str, loader: Any) -> dict[int, Any]:
            raw = _read(data, name, [])
            if type(raw) in {dict, ClosedMap}:
                result = []
                for raw_key, raw_item in _exact_mapping_items(raw, f"catalog.{name}", (int, str)):
                    if type(raw_key) is int:
                        registry_id = _u16(raw_key, f"catalog.{name}.key", nonzero=True)
                    elif type(raw_key) is str and raw_key.isascii() and raw_key.isdigit() and str(int(raw_key)) == raw_key:
                        registry_id = _u16(int(raw_key), f"catalog.{name}.key", nonzero=True)
                    else:
                        raise ModelError(Status.INVALID_STATIC_DATA, f"catalog.{name} has a noncanonical object key")
                    item = loader(raw_item)
                    if item.stable_id != registry_id:
                        raise ModelError(Status.INVALID_STATIC_DATA, f"catalog.{name} object key differs from stableId")
                    result.append(item)
            elif type(raw) in {list, tuple}:
                result = [loader(item) for item in _sequence(raw, f"catalog.{name}")]
            else:
                raise ModelError(Status.INVALID_STATIC_DATA, f"catalog.{name} must be an exact registry object or array")
            ids = [item.stable_id for item in result]
            if len(ids) != len(set(ids)):
                raise ModelError(Status.INVALID_STATIC_DATA, f"duplicate stable ID in {name}")
            return {item.stable_id: item for item in result}

        def owner_registry(raw: Mapping[Any, Any]) -> dict[int, str]:
            result: dict[int, str] = {}
            for raw_key, raw_value in _exact_mapping_items(raw, "catalog.ownerNames", (int, str)):
                # JSON object keys are necessarily strings; this is the sole
                # schema-key exception to scalar integer parsing.
                if type(raw_key) is int:
                    owner_id = _u16(raw_key, "ownerNames.ownerId", nonzero=True)
                elif type(raw_key) is str and raw_key.isascii() and raw_key.isdigit() and str(int(raw_key)) == raw_key:
                    owner_id = _u16(int(raw_key), "ownerNames.ownerId", nonzero=True)
                else:
                    raise ModelError(Status.INVALID_STATIC_DATA, "ownerNames key is not a canonical u16 object key")
                owner_name = _symbol(raw_value, "ownerNames.name")
                if owner_id in result:
                    raise ModelError(Status.INVALID_STATIC_DATA, "duplicate ownerNames owner ID")
                result[owner_id] = owner_name
            return result

        translations_list: list[TiredTranslation] = []
        for raw_item in _sequence(_read(data, "tired_translations", ()), "catalog.tiredTranslations"):
            item = _closed_mapping(raw_item, "tiredTranslation", ("origin", "destination_controller_id", "authored_tired_bound", "definition_id"))
            translations_list.append(TiredTranslation(
                _enum_value(TiredOriginKind, _read(item, "origin"), "tiredTranslation.origin"),
                _u16(_read(item, "destination_controller_id"), "tiredTranslation.destinationControllerId", nonzero=True),
                _boolean(_read(item, "authored_tired_bound"), "tiredTranslation.authoredTiredBound"),
                _u16(_read(item, "definition_id"), "tiredTranslation.definitionId", nonzero=True),
            ))
        translations = tuple(translations_list)
        return cls(
            registry("state_profiles", StateProfile.from_dict),
            registry("controllers", Controller.from_dict),
            registry("modifiers", Modifier.from_dict),
            registry("definitions", OverrideDefinition.from_dict),
            tuple(StaticRule.from_dict(item) for item in _sequence(_read(data, "static_rules", ()), "catalog.staticRules")),
            _u16(_read(data, "default_controller_id", 0), "catalog.defaultControllerId"),
            registry("spawn_policies", SpawnPolicy.from_dict),
            registry("population_policies", PopulationPolicy.from_dict),
            registry("hook_sets", HookSet.from_dict),
            registry("spawn_policy_patches", PolicyPatch.from_dict),
            registry("population_policy_patches", PolicyPatch.from_dict),
            translations,
            owner_registry(_mapping(_read(data, "owner_names", {}), "catalog.ownerNames") or {}),
        )


def catalog_from_dict(data: Mapping[str, Any]) -> BehaviorCatalog:
    try:
        if type(data) not in {dict, ClosedMap}:
            raise ModelError(Status.INVALID_STATIC_DATA, "catalog must be an exact dict or ClosedMap object")
        return BehaviorCatalog.from_dict(data)
    except ModelError:
        raise
    except Exception:
        raise ModelError(Status.INVALID_STATIC_DATA, "catalog wire data is hostile or malformed") from None


@dataclass(frozen=True)
class StaticModifierContribution:
    modifier_id: int
    static_priority: int
    rule_id: int
    action_id: int
    role_mask: frozenset[SemanticRole]


@dataclass(frozen=True)
class TimerSourceContribution:
    static_priority: int
    rule_id: int
    action_id: int
    operation: ModifierOperation


@dataclass(frozen=True)
class CandidateTimerSource:
    authored_duration: int
    folded_duration: int
    normalized_duration: int
    indefinite: bool
    zero_derived: bool
    indefinite_origin: str
    resolved_duration_policy: TimerDurationPolicy
    contributions: tuple[TimerSourceContribution, ...] = ()


@dataclass(frozen=True)
class StaticResolution:
    context: StaticContext
    controller_id: int
    node_bindings: Mapping[int, int | None]
    controller_values: ControllerValues
    static_modifiers: tuple[StaticModifierContribution, ...]
    candidate_timer_sources: Mapping[int, CandidateTimerSource]
    spawn_policy_id: int
    population_policy_id: int
    hook_set_id: int
    spawn_policy_values: Mapping[str, Any]
    population_policy_values: Mapping[str, Any]
    controller_provenance: Mapping[str, Any]
    hash: str
    provenance: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_bindings", _deep_freeze(self.node_bindings))
        object.__setattr__(self, "static_modifiers", tuple(self.static_modifiers))
        object.__setattr__(self, "candidate_timer_sources", _deep_freeze(self.candidate_timer_sources))
        object.__setattr__(self, "spawn_policy_values", _deep_freeze(self.spawn_policy_values))
        object.__setattr__(self, "population_policy_values", _deep_freeze(self.population_policy_values))
        object.__setattr__(self, "controller_provenance", _deep_freeze(self.controller_provenance))
        object.__setattr__(self, "provenance", _deep_freeze(self.provenance))


def _resolve_static_impl(catalog: BehaviorCatalog, context: StaticContext) -> StaticResolution:
    matching = [rule for rule in catalog.static_rules if rule.matcher.matches(context)]
    assignments: list[tuple[tuple[int, int, int], StaticAction]] = []
    ordered: list[tuple[tuple[int, int, int], StaticAction]] = []
    seen_keys: set[tuple[int, int, int]] = set()
    seen_assignment_keys: set[tuple[int, int, int]] = set()
    for rule in matching:
        for action in rule.actions:
            if action.kind is StaticActionKind.ASSIGN_CONTROLLER:
                assignment_key = (action.assignment_priority, rule.stable_id, action.stable_id)
                if assignment_key in seen_assignment_keys:
                    raise ModelError(Status.INVALID_STATIC_DATA, f"duplicate assignment action key {assignment_key}")
                seen_assignment_keys.add(assignment_key)
                assignments.append((assignment_key, action))
            else:
                key = (action.static_priority, rule.stable_id, action.stable_id)
                if key in seen_keys:
                    raise ModelError(Status.INVALID_STATIC_DATA, f"duplicate static action key {key}")
                seen_keys.add(key)
                ordered.append((key, action))
    controller_id = max(assignments, key=lambda item: item[0])[1].controller_id if assignments else catalog.default_controller_id
    controller = catalog.controllers.get(controller_id)
    if controller is None:
        raise ModelError(Status.INVALID_STATIC_DATA, "static assignment selected missing controller")
    bindings = {node.stable_id: node.state_profile_id for node in controller.nodes}
    static_modifiers: list[StaticModifierContribution] = []
    timer_work: dict[int, tuple[int, list[TimerSourceContribution]]] = {
        definition.stable_id: (definition.timer.duration, [])
        for definition in catalog.definitions.values() if definition.timer is not None
    }
    spawn_id, population_id, hook_id = controller.spawn_policy_id, controller.population_policy_id, controller.hook_set_id
    spawn_values = catalog.spawn_policies[spawn_id].values()
    population_values = catalog.population_policies[population_id].values()
    policy_provenance: dict[str, Any] = {}
    provenance: dict[str, Any] = {"assignment": max(assignments, default=None, key=lambda item: item[0])[0] if assignments else "default", "actions": []}
    controller_ops: list[tuple[tuple[int, int, int], int]] = []
    for key, action in sorted(ordered):
        if action.controller_id and action.controller_id != controller_id:
            continue
        provenance["actions"].append({"key": key, "kind": action.kind.value, "actionId": action.stable_id})
        if action.kind is StaticActionKind.BIND_NODE:
            if controller.node(action.node_id) is None or action.profile_id not in catalog.state_profiles:
                raise ModelError(Status.INVALID_STATIC_DATA, "invalid static node binding")
            before = bindings[action.node_id]
            bindings[action.node_id] = action.profile_id
            provenance["actions"][-1].update({"before": before, "after": action.profile_id, "payload": {"controllerId": action.controller_id, "nodeId": action.node_id, "profileId": action.profile_id}})
        elif action.kind is StaticActionKind.UNBIND_NODE:
            if action.node_id == controller.base_node_id:
                raise ModelError(Status.INVALID_STATIC_DATA, "base node cannot be unbound")
            before = bindings.get(action.node_id)
            bindings[action.node_id] = None
            provenance["actions"][-1].update({"before": before, "after": None, "payload": {"controllerId": action.controller_id, "nodeId": action.node_id}})
        elif action.kind is StaticActionKind.APPLY_STATE_MODIFIER:
            if action.modifier_id not in catalog.modifiers:
                raise ModelError(Status.INVALID_STATIC_DATA, "missing static state modifier")
            static_modifiers.append(StaticModifierContribution(action.modifier_id, key[0], key[1], key[2], action.role_mask))
        elif action.kind is StaticActionKind.APPLY_CONTROLLER_MODIFIER:
            controller_ops.append((key, action.modifier_id))
        elif action.kind is StaticActionKind.BIND_SPAWN_POLICY:
            before = {"policyId": spawn_id, "values": dict(spawn_values)}
            spawn_id = action.spawn_policy_id
            spawn_values = catalog.spawn_policies[spawn_id].values()
            provenance["actions"][-1].update({"before": before, "after": {"policyId": spawn_id, "values": dict(spawn_values)}})
        elif action.kind is StaticActionKind.APPLY_SPAWN_POLICY_PATCH:
            _fold_policy(spawn_values, catalog.spawn_policy_patches[action.spawn_policy_patch_id], "spawn", f"static:{key}:{action.spawn_policy_patch_id}", policy_provenance)
        elif action.kind is StaticActionKind.BIND_POPULATION_POLICY:
            before = {"policyId": population_id, "values": dict(population_values)}
            population_id = action.population_policy_id
            population_values = catalog.population_policies[population_id].values()
            provenance["actions"][-1].update({"before": before, "after": {"policyId": population_id, "values": dict(population_values)}})
        elif action.kind is StaticActionKind.APPLY_POPULATION_POLICY_PATCH:
            _fold_policy(population_values, catalog.population_policy_patches[action.population_policy_patch_id], "population", f"static:{key}:{action.population_policy_patch_id}", policy_provenance)
        elif action.kind is StaticActionKind.BIND_HOOK_SET:
            hook_id = action.hook_set_id
        elif action.kind is StaticActionKind.APPLY_CANDIDATE_TIMER_OPERATOR:
            if action.timer_operation is None:
                raise ModelError(Status.INVALID_STATIC_DATA, "timer action has no operation")
            definition = catalog.definitions[action.candidate_definition_id]
            assert definition.timer is not None
            before, contributions = timer_work[definition.stable_id]
            timer_work[definition.stable_id] = (
                _apply_timer_source(before, action.timer_operation),
                contributions + [TimerSourceContribution(key[0], key[1], key[2], action.timer_operation)],
            )
    controller_map = controller.defaults.values()
    field_provenance: dict[str, Any] = {}
    for key, modifier_id in controller_ops:
        modifier = catalog.modifiers.get(modifier_id)
        if modifier is None:
            raise ModelError(Status.INVALID_STATIC_DATA, "missing static controller modifier")
        _fold_modifier({}, controller_map, modifier, f"static:{key}:{modifier_id}", field_provenance)
    values = ControllerValues(**{_snake(key): value for key, value in controller_map.items()})
    timer_sources = {
        definition_id: _finalize_timer_source(catalog.definitions[definition_id], catalog, duration, tuple(contributions))
        for definition_id, (duration, contributions) in sorted(timer_work.items())
    }
    if spawn_values and spawn_values["minimumDistance"] > spawn_values["maximumDistance"]:
        raise ModelError(Status.INVALID_COMPOSITION, "static spawn-policy fold produced min greater than max")
    payload = {"context": context, "controllerId": controller_id, "bindings": bindings, "controllerValues": values, "controllerProvenance": field_provenance, "modifiers": static_modifiers, "timers": timer_sources, "spawnPolicyId": spawn_id, "spawnPolicyValues": spawn_values, "populationPolicyId": population_id, "populationPolicyValues": population_values, "hookSetId": hook_id}
    provenance["controllerFields"] = field_provenance
    provenance["policyFields"] = policy_provenance
    return StaticResolution(
        context, controller_id, MappingProxyType(dict(bindings)), values, tuple(static_modifiers), MappingProxyType(dict(timer_sources)),
        spawn_id, population_id, hook_id, _deep_freeze(spawn_values), _deep_freeze(population_values),
        _deep_freeze(field_provenance), stable_hash("static", payload), _deep_freeze(provenance),
    )


def resolve_static(catalog: BehaviorCatalog, context: StaticContext) -> StaticResolution:
    """Resolve immutable static state through a closed, callback-free boundary."""

    if type(catalog) is not BehaviorCatalog or type(context) is not StaticContext:
        raise ModelError(Status.INVALID_STATIC_DATA, "static resolution requires exact BehaviorCatalog and StaticContext values")
    try:
        _validate_closed_runtime_graph((catalog, context), "resolveStatic.inputs")
        BehaviorCatalog.validate(catalog)
        context_storage = object.__getattribute__(context, "__dict__")
        context_snapshot = StaticContext(
            species_id=context_storage["species_id"],
            form=context_storage["form"],
            species_group_ids=context_storage["species_group_ids"],
            level=context_storage["level"],
            terrain=context_storage["terrain"],
            map_id=context_storage["map_id"],
            shiny=context_storage["shiny"],
            assigned_class_id=context_storage["assigned_class_id"],
            data_generation=context_storage["data_generation"],
            data_incarnation=context_storage["data_incarnation"],
            extras=context_storage["extras"],
        )
        return _resolve_static_impl(catalog, context_snapshot)
    except ModelError as exc:
        if exc.status is Status.INVALID_HANDLE:
            raise ModelError(Status.INVALID_STATIC_DATA, "static resolution inputs are not closed canonical values") from None
        raise
    except Exception:
        raise ModelError(Status.INVALID_STATIC_DATA, "static resolution boundary rejected hostile or malformed input") from None


def _snake(name: str) -> str:
    result = []
    for char in name:
        if char.isupper():
            result.extend(("_", char.lower()))
        else:
            result.append(char)
    return "".join(result)


@dataclass(frozen=True)
class FieldSpec:
    family: str
    minimum: int | None = None
    maximum: int | None = None
    allowed: frozenset[Any] = frozenset()


NUMERIC = {
    "state.speed": FieldSpec("numeric", 1, 4),
    "state.movementRange": FieldSpec("numeric", 0, 64),
    "state.playerAdjacentDirectionMask": FieldSpec("mask", 0, 0xF),
    "state.hopMinDistance": FieldSpec("numeric", 0, 12),
    "state.hopMaxDistance": FieldSpec("numeric", 0, 12),
    "state.hopPause": FieldSpec("numeric", 0, 255),
    "state.hopTimePerTile": FieldSpec("numeric", 0, 64),
    "state.hopSpinSpeed": FieldSpec("numeric", 0, 15),
    "state.teleportTime": FieldSpec("numeric", 0, 64),
    "state.teleportPause": FieldSpec("numeric", 0, 255),
    "state.ramAccelerationSteps": FieldSpec("numeric", 0, 32),
    "state.ramMaxSpeed": FieldSpec("numeric", 0, 255),
    "state.chaseBoostDistance": FieldSpec("numeric", 0, 32),
    "state.chaseBoostSpeed": FieldSpec("numeric", 0, 4),
    "state.circleRadius": FieldSpec("numeric", 0, 8),
    "state.chainMovementVariance": FieldSpec("numeric", 0, 32),
    "state.chainPauseVariance": FieldSpec("numeric", 0, 255),
    "controller.alertPresentationDuration": FieldSpec("numeric", 0, 255),
    "controller.detectionDistance": FieldSpec("numeric", 0, 64),
    "controller.alertChance": FieldSpec("numeric", 0, 100),
    "controller.stamina": FieldSpec("numeric", 0, 64),
    "controller.recoveryDuration": FieldSpec("recovery", 0, 255),
    "spawn.minimumDistance": FieldSpec("numeric", 1, 8),
    "spawn.maximumDistance": FieldSpec("numeric", 1, 8),
    "spawn.hopTimePerTile": FieldSpec("numeric", 0, 64),
    "population.limit": FieldSpec("numeric", 0, 10),
}

LOCOMOTION_VALUES = frozenset({"NONE", "IDLE", "WANDER", "CHASE", "FLEE", "HOP", "TELEPORT", "PHANTOM_TELEPORT", "RAM", "CIRCLE", "CARRIED", "FOLLOWER"})
TARGET_VALUES = frozenset({"NONE", "PLAYER", "RANDOM_NEARBY", "NEXT_TO_PLAYER", "AWAY_FROM_PLAYER", "FIXED"})
TILE_VALUES = frozenset({"NONE", "GROUND", "WATER", "CANOPY", "GRASS", "CAVE", "ANY"})
JUMP_VALUES = frozenset({"NONE", "LOW", "MEDIUM", "HIGH"})
TRIGGER_VALUES = frozenset({"NONE", "CONTACT", "INTERACT", "SCRIPT"})
ALERT_VALUES = frozenset({"NONE", "EMOTE", "JUMP", "DIRECT"})
RANGE_VALUES = frozenset({"NONE", "CARDINAL", "RADIAL", "LINE"})
SPAWN_PRESENTATIONS = frozenset({"NONE", "APPEAR", "APPEAR_HOP", "RUN"})
SPAWN_DESTINATIONS = frozenset({"NONE", "RANDOM", "NEAR_PLAYER", "ONE_TILE_BEHIND_PLAYER", "FIXED"})
BEHAVIOR_KIND_VALUES = frozenset({"CALM", "ACTIVE", "ATTENTIVE", "TIRED", "TIRED_EMOTE", "ASLEEP", "CARRIED", "FOLLOWER", "FALLBACK_TIRED", "IDLE"})
HOOK_VALUES = frozenset({"DETECTION_ENTRY_CALL_FOR_HELP", "ACTIVE_ENTRY_TRY_PICKUP_THROW", "ACTIVE_LOOP_TRY_PICKUP_THROW"})

EXACT = {
    "state.locomotion": FieldSpec("enum", allowed=LOCOMOTION_VALUES),
    "state.target": FieldSpec("enum", allowed=TARGET_VALUES),
    "state.allowedTile": FieldSpec("enum", allowed=TILE_VALUES),
    "state.allowedTile2": FieldSpec("enum", allowed=TILE_VALUES),
    "state.jumpLevel": FieldSpec("enum", allowed=JUMP_VALUES),
    "state.ledgeJump": FieldSpec("bool"),
    "state.hopAllowNonCardinal": FieldSpec("bool"),
    "state.continueWhenArrived": FieldSpec("bool"),
    "state.avoidPreviousTile": FieldSpec("bool"),
    "state.chainPauseAction": FieldSpec("enum", allowed=frozenset({"NONE", "LOOK", "WAIT", "TURN"})),
    "state.battleTrigger": FieldSpec("enum", allowed=TRIGGER_VALUES),
    "state.contactBehavior": FieldSpec("enum", allowed=TRIGGER_VALUES),
    "controller.alertMode": FieldSpec("enum", allowed=ALERT_VALUES),
    "controller.alertEmote": FieldSpec("enum", allowed=frozenset({"NONE", "QUESTION", "EXCLAMATION", "SWEAT", "SLEEP"})),
    "controller.alertRange": FieldSpec("enum", allowed=RANGE_VALUES),
    "controller.exhaustionEnabled": FieldSpec("bool"),
    "controller.allowRevealUnderlyingRecovery": FieldSpec("bool"),
    "spawn.presentation": FieldSpec("enum", allowed=SPAWN_PRESENTATIONS),
    "spawn.destination": FieldSpec("enum", allowed=SPAWN_DESTINATIONS),
}
FIELD_SPECS = {**NUMERIC, **EXACT}


def _validate_registry(name: str, registry: Mapping[int, Any]) -> None:
    expected_types = {
        "stateProfiles": StateProfile, "controllers": Controller,
        "modifiers": Modifier, "definitions": OverrideDefinition,
        "spawnPolicies": SpawnPolicy, "populationPolicies": PopulationPolicy,
        "hookSets": HookSet, "spawnPolicyPatches": PolicyPatch,
        "populationPolicyPatches": PolicyPatch,
    }
    expected_type = expected_types[name]
    seen: set[int] = set()
    for key, item in _exact_mapping_items(registry, f"catalog.{name}", (int,)):
        if type(item) is not expected_type:
            raise ModelError(Status.INVALID_STATIC_DATA, f"{name} registry contains a noncanonical value")
        stable_id = object.__getattribute__(item, "__dict__")["stable_id"]
        if type(key) is not int or type(stable_id) is not int or not 1 <= key <= 0xFFFF or stable_id != key or key in seen:
            raise ModelError(Status.INVALID_STATIC_DATA, f"{name} registry key/ID mismatch or duplicate at {key!r}")
        seen.add(key)


def _validate_state_profile(profile: StateProfile) -> None:
    if type(profile.behavior_kind) is not str or profile.behavior_kind not in BEHAVIOR_KIND_VALUES:
        raise ModelError(Status.INVALID_STATIC_DATA, f"profile {profile.stable_id} has invalid behavior kind")
    for name, value in profile.values().items():
        path = f"state.{name}"
        spec = FIELD_SPECS.get(path)
        if spec is None:
            continue
        if spec.family == "bool" and type(value) is not bool:
            raise ModelError(Status.INVALID_STATIC_DATA, f"{path} must be boolean")
        if spec.family in {"numeric", "mask", "recovery"} and (type(value) is not int or not spec.minimum <= value <= spec.maximum):
            raise ModelError(Status.INVALID_STATIC_DATA, f"{path} is outside {spec.minimum}..{spec.maximum}")
        if spec.family == "enum" and (type(value) is not str or spec.allowed and value not in spec.allowed):
            raise ModelError(Status.INVALID_STATIC_DATA, f"{path} has invalid enum value {value!r}")
    if profile.hop_max_distance < profile.hop_min_distance:
        raise ModelError(Status.INVALID_STATIC_DATA, f"profile {profile.stable_id} hop max is below min")
    _validate_state_cross_fields(profile.values(), Status.INVALID_STATIC_DATA)


def _validate_state_cross_fields(values: Mapping[str, Any], status: Status) -> None:
    requirements = {
        "HOP": values["hopTimePerTile"] > 0,
        "TELEPORT": values["teleportTime"] > 0,
        "PHANTOM_TELEPORT": values["teleportTime"] > 0,
        "RAM": values["ramAccelerationSteps"] > 0 and values["ramMaxSpeed"] > 0,
        "CIRCLE": values["circleRadius"] > 0,
    }
    locomotion = values["locomotion"]
    if locomotion in requirements and not requirements[locomotion]:
        raise ModelError(status, f"locomotion {locomotion} lacks required parameters")


def _validate_controller_values(values: ControllerValues) -> None:
    for name, value in values.values().items():
        path = f"controller.{name}"
        spec = FIELD_SPECS[path]
        if spec.family == "bool" and type(value) is not bool:
            raise ModelError(Status.INVALID_STATIC_DATA, f"{path} must be boolean")
        if spec.family in {"numeric", "recovery"} and (type(value) is not int or not spec.minimum <= value <= spec.maximum):
            raise ModelError(Status.INVALID_STATIC_DATA, f"{path} is outside its domain")
        if spec.family == "enum" and (type(value) is not str or spec.allowed and value not in spec.allowed):
            raise ModelError(Status.INVALID_STATIC_DATA, f"{path} has invalid enum value")
    if values.exhaustion_enabled and values.stamina == 0:
        raise ModelError(Status.INVALID_STATIC_DATA, "authored exhaustion-enabled stamina must be nonzero")


def _validate_operation(path: str, operation: ModifierOperation, *, runtime: bool) -> None:
    spec = _field_spec(path, runtime=runtime)
    if operation.kind in {OperatorKind.ADD_AT_LEAST, OperatorKind.ADD_AT_MOST} and operation.bound is None:
        raise ModelError(Status.INVALID_MODIFIER, f"{operation.kind.value} requires a bound")
    if operation.kind not in {OperatorKind.ADD_AT_LEAST, OperatorKind.ADD_AT_MOST} and operation.bound is not None:
        raise ModelError(Status.INVALID_MODIFIER, f"{operation.kind.value} cannot carry a bound")
    if spec.family in {"numeric", "mask", "recovery"}:
        if type(operation.value) is not int:
            raise ModelError(Status.INVALID_MODIFIER, f"{path} operand must be an integer")
        operand = operation.value
        if operation.kind in {OperatorKind.SET, OperatorKind.AT_LEAST, OperatorKind.AT_MOST} and not spec.minimum <= operand <= spec.maximum:
            raise ModelError(Status.INVALID_MODIFIER, f"{path} exact/bound operand is outside its field domain")
        if operation.kind in {OperatorKind.ADD, OperatorKind.ADD_AT_LEAST, OperatorKind.ADD_AT_MOST} and not -0x8000 <= operand <= 0x7FFF:
            raise ModelError(Status.INVALID_MODIFIER, f"{path} relative operand is outside s16")
        if operation.bound is not None and (type(operation.bound) is not int or not spec.minimum <= operation.bound <= spec.maximum):
            raise ModelError(Status.INVALID_MODIFIER, f"{path} compound bound is outside its field domain")
    representative: Any = False if spec.family == "bool" else (next(iter(spec.allowed)) if spec.family == "enum" and spec.allowed else (spec.minimum or 0))
    _apply_operator(representative, operation, spec)


def _validate_selector_totality(definition: OverrideDefinition, controllers: Mapping[int, Controller]) -> None:
    selector = definition.selector
    assert selector is not None
    eligible = [controller for controller in controllers.values() if not definition.applicability.controller_ids or controller.stable_id in definition.applicability.controller_ids]
    if selector.kind is SelectorKind.EXACT:
        if not 1 <= selector.controller_id <= 0xFFFF or not 1 <= selector.node_id <= 0xFFFF or selector.role is not None or selector.custom_role_id != 0:
            raise ModelError(Status.INVALID_STATIC_DATA, f"definition {definition.stable_id} exact selector payload is noncanonical")
        controller = controllers.get(selector.controller_id)
        if controller is None or controller.node(selector.node_id) is None:
            raise ModelError(Status.INVALID_STATIC_DATA, f"definition {definition.stable_id} exact selector is dangling")
        if definition.applicability.controller_ids and selector.controller_id not in definition.applicability.controller_ids:
            raise ModelError(Status.INVALID_STATIC_DATA, f"definition {definition.stable_id} exact selector contradicts controller applicability")
        return
    if selector.controller_id != 0 or selector.node_id != 0 or not isinstance(selector.role, SemanticRole) or not 0 <= selector.custom_role_id <= 0xFFFF:
        raise ModelError(Status.INVALID_STATIC_DATA, f"definition {definition.stable_id} semantic selector payload is noncanonical")
    if selector.role is SemanticRole.CUSTOM and selector.custom_role_id == 0:
        raise ModelError(Status.INVALID_STATIC_DATA, f"definition {definition.stable_id} CUSTOM selector requires customRoleId")
    if selector.role is not SemanticRole.CUSTOM and selector.custom_role_id != 0:
        raise ModelError(Status.INVALID_STATIC_DATA, f"definition {definition.stable_id} non-CUSTOM selector carries customRoleId")
    for controller in eligible:
        potential = [node for node in controller.nodes if node.role is selector.role and (node.role is not SemanticRole.CUSTOM or node.custom_role_id == selector.custom_role_id)]
        if len(potential) > 1:
            raise ModelError(Status.INVALID_STATIC_DATA, f"definition {definition.stable_id} semantic selector can become ambiguous in controller {controller.stable_id}")
        matches = [node for node in controller.nodes if node.state_profile_id is not None and node.role is selector.role and (node.role is not SemanticRole.CUSTOM or node.custom_role_id == selector.custom_role_id)]
        if len(matches) > 1:
            raise ModelError(Status.INVALID_STATIC_DATA, f"definition {definition.stable_id} semantic selector is ambiguous in controller {controller.stable_id}")
        if not matches and definition.applicability.controller_ids:
            raise ModelError(Status.INVALID_STATIC_DATA, f"definition {definition.stable_id} scoped semantic selector has zero matches")


def _selector_is_asleep(selector: NodeSelector, controllers: Mapping[int, Controller]) -> bool:
    if selector.kind is SelectorKind.SEMANTIC:
        return selector.role is SemanticRole.ASLEEP
    controller = controllers.get(selector.controller_id)
    node = controller.node(selector.node_id) if controller else None
    return node is not None and node.role is SemanticRole.ASLEEP


def _finalize_timer_source(
    definition: OverrideDefinition,
    catalog: BehaviorCatalog,
    folded_duration: int,
    contributions: tuple[TimerSourceContribution, ...],
) -> CandidateTimerSource:
    assert definition.timer is not None and definition.selector is not None
    authored = definition.timer.duration
    asleep = _selector_is_asleep(definition.selector, catalog.controllers)
    policy = definition.timer.duration_policy
    zero_derived = policy is TimerDurationPolicy.LEGACY_REST_TIME and asleep and folded_duration == 0
    indefinite = policy is TimerDurationPolicy.INDEFINITE or zero_derived
    if indefinite:
        normalized = 255
        if policy is TimerDurationPolicy.INDEFINITE:
            origin = "EXPLICIT_INDEFINITE"
        else:
            origin = "AUTHORED_ASLEEP_ZERO" if not contributions else "STATIC_RESOLVED_ASLEEP_ZERO"
    else:
        normalized = 254 if folded_duration >= 255 else folded_duration
        if policy is TimerDurationPolicy.LEGACY_REST_TIME and not asleep and normalized == 0:
            normalized = 1
        origin = "NONE"
    resolved_policy = TimerDurationPolicy.INDEFINITE if indefinite else TimerDurationPolicy.FINITE
    return CandidateTimerSource(authored, folded_duration, normalized, indefinite, zero_derived, origin, resolved_policy, contributions)


def _validate_translation_row(row: TiredTranslation, catalog: BehaviorCatalog) -> None:
    controller = catalog.controllers.get(row.destination_controller_id)
    target = catalog.definitions.get(row.definition_id)
    if controller is None or target is None or target.generated.tired_origin_kind is not row.origin:
        raise ModelError(Status.INVALID_STATIC_DATA, "tired translation has dangling/wrong-origin target")
    if target.applicability.controller_ids and controller.stable_id not in target.applicability.controller_ids:
        raise ModelError(Status.INVALID_STATIC_DATA, "tired translation target excludes destination controller")
    if not _matcher_is_total(target.applicability.context):
        raise ModelError(Status.INVALID_TRANSLATION, "tired translation target has a context filter that excludes required destinations")
    if target.generated.has_required_owner_id is not True:
        raise ModelError(Status.INVALID_STATIC_DATA, "tired translation target lacks required owner")
    selector = target.selector
    if row.authored_tired_bound:
        if selector is None or selector.kind is not SelectorKind.SEMANTIC or selector.role is not SemanticRole.TIRED:
            raise ModelError(Status.INVALID_STATIC_DATA, "authored-tired translation must target semantic TIRED")
    else:
        if selector is None or selector.kind is not SelectorKind.EXACT or selector.controller_id != controller.stable_id:
            raise ModelError(Status.INVALID_STATIC_DATA, "fallback translation must target destination exact node")
        node = controller.node(selector.node_id)
        profile = catalog.state_profiles.get(node.state_profile_id) if node and node.state_profile_id is not None else None
        if node is None or node.role is not SemanticRole.CUSTOM or profile is None or profile.behavior_kind != "FALLBACK_TIRED":
            raise ModelError(Status.INVALID_TRANSLATION, "fallback translation exact node must remain bound to its FALLBACK_TIRED profile")


def _reachable_authored_tired_states(catalog: BehaviorCatalog, controller: Controller) -> frozenset[bool]:
    tired_nodes = {node.stable_id for node in controller.nodes if node.role is SemanticRole.TIRED}
    states = {any(node.state_profile_id is not None for node in controller.nodes if node.stable_id in tired_nodes)}
    for rule in catalog.static_rules:
        for action in rule.actions:
            if action.controller_id == controller.stable_id and action.node_id in tired_nodes:
                if action.kind is StaticActionKind.BIND_NODE:
                    states.add(True)
                elif action.kind is StaticActionKind.UNBIND_NODE:
                    states.add(False)
    return frozenset(states)


def _matcher_is_total(matcher: ContextMatcher) -> bool:
    return not any((matcher.species_ids, matcher.forms, matcher.species_group_ids, matcher.terrains, matcher.map_ids, matcher.assigned_class_ids, matcher.extras)) and matcher.level_min is None and matcher.level_max is None and matcher.shiny is None


def _validate_generated_definition(definition: OverrideDefinition, owner_names: Mapping[int, str]) -> None:
    meta = definition.generated
    if type(meta.has_tired_origin_kind) is not bool or type(meta.has_required_owner_id) is not bool:
        raise ModelError(Status.INVALID_GENERATED_WRAPPER, "generated metadata presence tags must be booleans")
    if meta.has_tired_origin_kind and not isinstance(meta.tired_origin_kind, TiredOriginKind):
        raise ModelError(Status.INVALID_GENERATED_WRAPPER, "tired origin is not a closed enum member")
    if meta.has_tired_origin_kind != (meta.tired_origin_kind is not None):
        raise ModelError(Status.INVALID_GENERATED_WRAPPER, "noncanonical tired-origin tag/value pair")
    if type(meta.required_owner_id) is not int:
        raise ModelError(Status.INVALID_GENERATED_WRAPPER, "required owner value must be an integer")
    if not meta.has_required_owner_id and meta.required_owner_id != 0:
        raise ModelError(Status.INVALID_GENERATED_WRAPPER, "absent required-owner tag must carry zero")
    if meta.has_required_owner_id and not 1 <= meta.required_owner_id <= 0xFFFF:
        raise ModelError(Status.INVALID_GENERATED_WRAPPER, "required owner must be a nonzero u16")
    generated = meta.has_tired_origin_kind or meta.has_required_owner_id
    if generated:
        if definition.kind is not DefinitionKind.STATE_CANDIDATE:
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "generated authorization is candidate-only")
        if definition.allow_multiple_owners or definition.allow_multiple_instances_per_owner:
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "generated tired wrappers freeze FALSE/FALSE multiplicity")
        if meta.has_tired_origin_kind and not meta.has_required_owner_id:
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "imperative tired origin requires owner authorization")
        family_name = meta.tired_origin_kind.name if meta.tired_origin_kind else "STAMINA"
        spec = GENERATED_FAMILY_SPECS[family_name]
        if meta.tired_origin_kind is not spec["origin"] or meta.required_owner_id != spec["owner_id"] or definition.channel is not spec["channel"] or definition.priority != spec["priority"]:
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, f"{family_name} differs from the frozen origin/owner/channel/priority registry")
        if definition.selector is None:
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "generated tired wrapper requires selector")
        if meta.tired_origin_kind is None and (definition.selector.kind is not SelectorKind.SEMANTIC or definition.selector.role is not SemanticRole.TIRED):
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "generated stamina wrapper must use semantic TIRED and never fallback")
        if definition.selector.kind is SelectorKind.SEMANTIC and definition.selector.role is not SemanticRole.TIRED:
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "generated semantic tired wrapper must select TIRED")
        expected_timer = CandidateTimerPolicy(
            spec["duration"], spec["clock"], spec["hidden_policy"], spec["recovery"],
            spec["calm_reset_owner_ids"], spec["recovery_transition_id"], spec["duration_policy"],
        )
        if definition.timer != expected_timer:
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, f"{family_name} differs from the frozen duration/clock/hidden/recovery/reset/transition registry")
        if definition.map_policy is not spec["map_policy"] or definition.battle_policy is not spec["battle_policy"]:
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "generated tired wrapper has wrong frozen lifetime policy")
    elif meta.tired_origin_kind is not None or meta.required_owner_id != 0:
        raise ModelError(Status.INVALID_GENERATED_WRAPPER, "ordinary definition has noncanonical generated metadata")


def _apply_timer_source(current: int, operation: ModifierOperation) -> int:
    if type(operation.value) is not int:
        raise ModelError(Status.INVALID_STATIC_DATA, "candidate timer source operand must be an integer")
    operand = operation.value
    if operation.bound is not None:
        raise ModelError(Status.INVALID_STATIC_DATA, "candidate timer source SET/ADD cannot carry a bound")
    if operation.kind is OperatorKind.SET:
        if not 0 <= operand <= 255:
            raise ModelError(Status.INVALID_STATIC_DATA, "candidate timer SET operand is outside u8")
        return operand
    if operation.kind is OperatorKind.ADD:
        if not -0x8000 <= operand <= 0x7FFF:
            raise ModelError(Status.INVALID_STATIC_DATA, "candidate timer ADD operand is outside s16")
        return max(0, min(64, current + operand))
    raise ModelError(Status.INVALID_STATIC_DATA, "candidate timer source allows SET/ADD only")


def _field_spec(path: str, *, runtime: bool = True) -> FieldSpec:
    if path in ("state.behaviorKind", "state.stableId") or path.startswith("topology.") or (runtime and path.startswith(("spawn.", "population."))):
        raise ModelError(Status.INVALID_MODIFIER, f"runtime-forbidden field {path}")
    spec = FIELD_SPECS.get(path)
    if spec is None:
        raise ModelError(Status.INVALID_MODIFIER, f"unknown modifier field {path}")
    return spec


def _apply_operator(current: Any, operation: ModifierOperation, spec: FieldSpec) -> Any:
    if spec.family in {"enum", "bool", "mask"} and operation.kind is not OperatorKind.SET:
        raise ModelError(Status.INVALID_MODIFIER, f"{spec.family} fields support SET only")
    if spec.family == "bool":
        if type(operation.value) is not bool:
            raise ModelError(Status.INVALID_MODIFIER, "boolean operand must be boolean")
        return operation.value
    if spec.family == "mask":
        if type(operation.value) is not int:
            raise ModelError(Status.INVALID_MODIFIER, "mask operand must be integer")
        value = operation.value
        if value < 0 or value > 0xF:
            raise ModelError(Status.INVALID_MODIFIER, "player-adjacent mask contains unknown bits")
        return value
    if spec.family == "enum":
        if not isinstance(operation.value, str) or not operation.value:
            raise ModelError(Status.INVALID_MODIFIER, "enum operand must be a nonempty symbolic string")
        if spec.allowed and operation.value not in spec.allowed:
            raise ModelError(Status.INVALID_MODIFIER, f"enum operand {operation.value!r} is not a listed member")
        return operation.value
    if spec.family == "recovery" and current == 255 and operation.kind is not OperatorKind.SET:
        raise ModelError(Status.INVALID_COMPOSITION, "finite arithmetic cannot leave indefinite recovery sentinel")
    if type(operation.value) is not int:
        raise ModelError(Status.INVALID_MODIFIER, "numeric operand must be integer")
    value = operation.value
    low, high = spec.minimum, spec.maximum
    assert low is not None and high is not None
    if operation.kind is OperatorKind.SET:
        result = value
    elif operation.kind is OperatorKind.ADD:
        result = current + value
    elif operation.kind is OperatorKind.AT_LEAST:
        result = max(current, value)
    elif operation.kind is OperatorKind.AT_MOST:
        result = min(current, value)
    elif operation.kind is OperatorKind.ADD_AT_LEAST:
        assert type(operation.bound) is int
        result = max(max(low, min(high, current + value)), operation.bound)
    elif operation.kind is OperatorKind.ADD_AT_MOST:
        assert type(operation.bound) is int
        result = min(max(low, min(high, current + value)), operation.bound)
    else:  # pragma: no cover - enum exhaustiveness
        raise ModelError(Status.INVALID_MODIFIER, "unsupported operator")
    if spec.family == "recovery" and result == 255:
        return result
    return max(low, min(high, result))


def _fold_modifier(
    state_values: dict[str, Any],
    controller_values: dict[str, Any],
    modifier: Modifier,
    source: str,
    provenance: dict[str, Any],
) -> None:
    for path in sorted(modifier.operations):
        operation = modifier.operations[path]
        spec = _field_spec(path)
        namespace, name = path.split(".", 1)
        target = state_values if namespace == "state" else controller_values
        if name not in target:
            raise ModelError(Status.INVALID_MODIFIER, f"field {path} is not present in its namespace")
        before = target[name]
        after = _apply_operator(before, operation, spec)
        target[name] = after
        item = {
            "source": source,
            "modifierId": modifier.stable_id,
            "operator": operation.kind.value,
            "operand": operation.value,
            "bound": operation.bound,
            "before": before,
            "after": after,
        }
        record = provenance.setdefault(path, {"initial": before, "contributions": [], "normalization": []})
        record["contributions"].append(item)
        if operation.kind is OperatorKind.SET:
            record["lastExactWriter"] = source


def _fold_policy(values: dict[str, Any], patch: PolicyPatch, namespace: str, source: str, provenance: dict[str, Any]) -> None:
    for path in sorted(patch.operations):
        expected_prefix = f"{namespace}."
        if not path.startswith(expected_prefix):
            raise ModelError(Status.INVALID_STATIC_DATA, f"policy patch {patch.stable_id} targets wrong namespace {path}")
        name = path.split(".", 1)[1]
        if name not in values:
            raise ModelError(Status.INVALID_STATIC_DATA, f"policy field {path} is missing")
        operation = patch.operations[path]
        spec = _field_spec(path, runtime=False)
        before = values[name]
        after = _apply_operator(before, operation, spec)
        values[name] = after
        provenance.setdefault(path, {"initial": before, "contributions": [], "normalization": []})["contributions"].append({"source": source, "patchId": patch.stable_id, "operator": operation.kind.value, "before": before, "after": after})


@dataclass(frozen=True)
class Layer:
    definition_id: int
    owner_id: int
    instance_key: int
    entry_generation: int
    generated: GeneratedMetadata

    def key(self) -> tuple[int, int]:
        return self.owner_id, self.instance_key


@dataclass
class CandidateTimer:
    owner_id: int
    instance_key: int
    entry_generation: int
    remaining_ticks: int
    clock: TimerClock
    hidden_policy: HiddenPolicy
    timer_generation: int
    zero_pending: bool = False
    recovery_policy: RecoveryPolicy = RecoveryPolicy.REMOVE_SELF
    calm_reset_owner_ids: tuple[int, ...] = ()
    recovery_transition_id: int = 0
    expiry_plan_generation: int = 1
    armed_definition_id: int = 0
    armed_duration: int = 0
    armed_indefinite: bool = False
    armed_static_hash: str = ""
    armed_source_hash: str = ""
    allocation_authenticator: str = ""
    armed_source: CandidateTimerSource | None = None
    armed_context_authenticator: str = ""

    def key(self) -> tuple[int, int]:
        return self.owner_id, self.instance_key


@dataclass(frozen=True)
class TimerAllocation:
    entry_generation: int
    timer_generation: int
    expiry_plan_generation: int
    armed_definition_id: int
    armed_duration: int
    armed_indefinite: bool
    clock: TimerClock
    hidden_policy: HiddenPolicy
    recovery_policy: RecoveryPolicy
    calm_reset_owner_ids: tuple[int, ...]
    recovery_transition_id: int
    armed_static_hash: str
    armed_source_hash: str
    allocation_authenticator: str
    armed_source: CandidateTimerSource
    armed_context_authenticator: str


@dataclass(frozen=True, order=True)
class ExpiryRemovalTarget:
    """Exact layer identity authorized for one published expiry commit."""

    owner_id: int
    instance_key: int
    entry_generation: int
    definition_id: int
    reason: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExpiryRemovalTarget":
        data = _closed_mapping(
            data, "expiryRemovalTarget", (field_.name for field_ in dataclasses.fields(cls)),
            status=Status.INVALID_HANDLE,
        )
        return cls(
            _u16(_read(data, "owner_id"), "expiryRemovalTarget.ownerId", nonzero=True, status=Status.INVALID_HANDLE),
            _u16(_read(data, "instance_key"), "expiryRemovalTarget.instanceKey", status=Status.INVALID_HANDLE),
            _u32(_read(data, "entry_generation"), "expiryRemovalTarget.entryGeneration", nonzero=True),
            _u16(_read(data, "definition_id"), "expiryRemovalTarget.definitionId", nonzero=True, status=Status.INVALID_HANDLE),
            _symbol(_read(data, "reason"), "expiryRemovalTarget.reason", status=Status.INVALID_HANDLE),
        )


@dataclass(frozen=True)
class ExpiryPlan:
    runtime_epoch: int
    runtime_incarnation: str
    data_generation: int
    data_incarnation: str
    slot_index: int
    slot_generation: int
    static_context_generation: int
    static_context_incarnation: str
    layer_generation: int
    layer_incarnation: str
    owner_id: int
    instance_key: int
    entry_generation: int
    timer_generation: int
    expiry_plan_generation: int
    definition_id: int
    armed_definition_id: int
    armed_static_hash: str
    armed_source_hash: str
    controller_id: int
    node_id: int
    profile_id: int
    resolved_role: SemanticRole
    selector_binding_hash: str
    generated_binding_hash: str
    recovery_transition_id: int
    recovery_policy: RecoveryPolicy
    recovery_action: str
    calm_reset_owner_ids: tuple[int, ...]
    removal_targets: tuple[ExpiryRemovalTarget, ...]
    authenticator: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExpiryPlan":
        data = _closed_mapping(data, "expiryPlan", (field_.name for field_ in dataclasses.fields(cls)), status=Status.INVALID_HANDLE)
        reset_owners = _sequence(_read(data, "calm_reset_owner_ids"), "expiry.calmResetOwnerIds", status=Status.INVALID_HANDLE)
        raw_targets = _sequence(_read(data, "removal_targets"), "expiry.removalTargets", status=Status.INVALID_HANDLE)
        targets = tuple(ExpiryRemovalTarget.from_dict(target) for target in raw_targets)
        if not targets or targets != tuple(sorted(targets)) or len(targets) != len(set(targets)):
            raise ModelError(Status.INVALID_HANDLE, "expiry removal targets must be a nonempty unique canonical tuple")
        return cls(
            _u32(_read(data, "runtime_epoch"), "expiry.runtimeEpoch", nonzero=True), _symbol(_read(data, "runtime_incarnation"), "expiry.runtimeIncarnation", status=Status.INVALID_HANDLE),
            _u32(_read(data, "data_generation"), "expiry.dataGeneration", nonzero=True), _symbol(_read(data, "data_incarnation"), "expiry.dataIncarnation", status=Status.INVALID_HANDLE),
            _u8(_read(data, "slot_index"), "expiry.slotIndex", status=Status.INVALID_HANDLE), _u32(_read(data, "slot_generation"), "expiry.slotGeneration", nonzero=True), _u32(_read(data, "static_context_generation"), "expiry.staticContextGeneration", nonzero=True),
            _authenticator(_read(data, "static_context_incarnation"), "expiry.staticContextIncarnation"), _u32(_read(data, "layer_generation"), "expiry.layerGeneration", nonzero=True),
            _authenticator(_read(data, "layer_incarnation"), "expiry.layerIncarnation"),
            _u16(_read(data, "owner_id"), "expiry.ownerId", nonzero=True, status=Status.INVALID_HANDLE), _u16(_read(data, "instance_key"), "expiry.instanceKey", status=Status.INVALID_HANDLE), _u32(_read(data, "entry_generation"), "expiry.entryGeneration", nonzero=True),
            _u32(_read(data, "timer_generation"), "expiry.timerGeneration", nonzero=True), _u32(_read(data, "expiry_plan_generation"), "expiry.expiryPlanGeneration", nonzero=True),
            _u16(_read(data, "definition_id"), "expiry.definitionId", nonzero=True, status=Status.INVALID_HANDLE), _u16(_read(data, "armed_definition_id"), "expiry.armedDefinitionId", nonzero=True, status=Status.INVALID_HANDLE),
            _symbol(_read(data, "armed_static_hash"), "expiry.armedStaticHash", status=Status.INVALID_HANDLE), _symbol(_read(data, "armed_source_hash"), "expiry.armedSourceHash", status=Status.INVALID_HANDLE),
            _u16(_read(data, "controller_id"), "expiry.controllerId", nonzero=True, status=Status.INVALID_HANDLE), _u16(_read(data, "node_id"), "expiry.nodeId", nonzero=True, status=Status.INVALID_HANDLE), _u16(_read(data, "profile_id"), "expiry.profileId", nonzero=True, status=Status.INVALID_HANDLE),
            _enum_value(SemanticRole, _read(data, "resolved_role"), "expiry.resolvedRole", status=Status.INVALID_HANDLE),
            _symbol(_read(data, "selector_binding_hash"), "expiry.selectorBindingHash", status=Status.INVALID_HANDLE), _symbol(_read(data, "generated_binding_hash"), "expiry.generatedBindingHash", status=Status.INVALID_HANDLE),
            _u16(_read(data, "recovery_transition_id"), "expiry.recoveryTransitionId", status=Status.INVALID_HANDLE),
            _enum_value(RecoveryPolicy, _read(data, "recovery_policy"), "expiry.recoveryPolicy", status=Status.INVALID_HANDLE),
            _symbol(_read(data, "recovery_action"), "expiry.recoveryAction", status=Status.INVALID_HANDLE),
            tuple(_u16(value, "expiry.calmResetOwnerIds", nonzero=True, status=Status.INVALID_HANDLE) for value in reset_owners),
            targets,
            _authenticator(_read(data, "authenticator"), "expiry.authenticator"),
        )


@dataclass(frozen=True)
class MandatoryExpiryRegistry:
    """Closed canonical internal registry; never delegates equality to callers."""

    entries: tuple[tuple[tuple[int, int], ExpiryPlan], ...] = ()

    def __post_init__(self) -> None:
        if type(self.entries) is not tuple:
            raise ModelError(Status.INVALID_HANDLE, "mandatory expiry registry entries must be a tuple")
        previous: tuple[int, int] | None = None
        for item in self.entries:
            if type(item) is not tuple or len(item) != 2 or type(item[0]) is not tuple or len(item[0]) != 2 or type(item[1]) is not ExpiryPlan:
                raise ModelError(Status.INVALID_HANDLE, "mandatory expiry registry entry is malformed")
            key = item[0]
            if any(type(value) is not int for value in key) or not 1 <= key[0] <= 0xFFFF or not 0 <= key[1] <= 0xFFFF or previous is not None and key <= previous:
                raise ModelError(Status.INVALID_HANDLE, "mandatory expiry registry keys are unordered or invalid")
            if key != (item[1].owner_id, item[1].instance_key):
                raise ModelError(Status.INVALID_HANDLE, "mandatory expiry registry key differs from its plan")
            previous = key

    def items(self) -> tuple[tuple[tuple[int, int], ExpiryPlan], ...]:
        return self.entries

    def get(self, key: tuple[int, int]) -> ExpiryPlan | None:
        for candidate, plan in self.entries:
            if candidate[0] == key[0] and candidate[1] == key[1]:
                return plan
        return None

    def __getitem__(self, key: tuple[int, int]) -> ExpiryPlan:
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def __bool__(self) -> bool:
        return bool(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.entries)


@dataclass(frozen=True)
class Handle:
    runtime_epoch: int
    slot_index: int
    slot_generation: int
    owner_id: int
    instance_key: int
    entry_generation: int
    authenticator: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Handle":
        data = _closed_mapping(data, "handle", (field_.name for field_ in dataclasses.fields(cls)), status=Status.INVALID_HANDLE)
        return cls(
            _u32(_read(data, "runtime_epoch"), "handle.runtimeEpoch", nonzero=True), _u8(_read(data, "slot_index"), "handle.slotIndex", status=Status.INVALID_HANDLE),
            _u32(_read(data, "slot_generation"), "handle.slotGeneration", nonzero=True), _u16(_read(data, "owner_id"), "handle.ownerId", nonzero=True, status=Status.INVALID_HANDLE),
            _u16(_read(data, "instance_key"), "handle.instanceKey", status=Status.INVALID_HANDLE), _u32(_read(data, "entry_generation"), "handle.entryGeneration", nonzero=True),
            _handle_authenticator(_read(data, "authenticator")),
        )


@dataclass(frozen=True)
class Winner:
    kind: str
    controller_id: int
    node_id: int
    profile_id: int
    role: SemanticRole
    definition_id: int = 0
    owner_id: int = 0
    instance_key: int = 0
    entry_generation: int = 0
    precedence_key: tuple[int, int, int, int, int] = (0, 0, 0, 0, 0)


@dataclass(frozen=True)
class Composition:
    winner: Winner
    state_values: Mapping[str, Any]
    controller_values: Mapping[str, Any]
    primitives: Mapping[str, Any]
    capabilities: Mapping[str, bool]
    effective_hash: str
    layer_hash: str
    provenance: Mapping[str, Any]
    diagnostics: Mapping[str, Any]
    plans: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        for name in ("state_values", "controller_values", "primitives", "capabilities", "provenance", "diagnostics"):
            object.__setattr__(self, name, _deep_freeze(getattr(self, name)))
        object.__setattr__(self, "plans", _deep_freeze(self.plans))

    def semantic_output(self) -> Mapping[str, Any]:
        return _deep_freeze({
            "identity": {
                "controllerId": self.winner.controller_id,
                "nodeId": self.winner.node_id,
                "profileId": self.winner.profile_id,
                "role": self.winner.role.value,
            },
            "stateValues": self.state_values,
            "controllerValues": self.controller_values,
            "primitives": self.primitives,
            "capabilities": self.capabilities,
        })


def _resolve_selector(selector: NodeSelector, static: StaticResolution, catalog: BehaviorCatalog) -> ControllerNode | None:
    controller = catalog.controllers[static.controller_id]
    if selector.kind is SelectorKind.EXACT:
        if selector.controller_id != controller.stable_id:
            return None
        node = controller.node(selector.node_id)
        if node is None or static.node_bindings.get(node.stable_id) is None:
            return None
        return node
    matches = [
        node for node in controller.nodes
        if static.node_bindings.get(node.stable_id) is not None
        and node.role is selector.role
        and (node.role is not SemanticRole.CUSTOM or node.custom_role_id == selector.custom_role_id)
    ]
    if len(matches) > 1:
        raise ModelError(Status.AMBIGUOUS_SELECTOR, f"semantic selector {selector.role} matched {len(matches)} nodes")
    return matches[0] if matches else None


def _compose_impl(
    catalog: BehaviorCatalog,
    static: StaticResolution,
    layers: Sequence[Layer],
    *,
    previous: Composition | None = None,
) -> Composition:
    _validate_composition_layers(catalog, static, layers)
    controller = catalog.controllers[static.controller_id]
    base_node = controller.node(controller.base_node_id)
    assert base_node is not None
    base_profile_id = static.node_bindings.get(base_node.stable_id)
    if base_profile_id is None:
        raise ModelError(Status.INVALID_COMPOSITION, "resolved base node is unbound")
    candidates: list[tuple[tuple[int, int, int, int, int], Layer, ControllerNode]] = []
    candidate_diagnostics: list[dict[str, Any]] = []
    for layer in layers:
        definition = catalog.definitions.get(layer.definition_id)
        if definition is None:
            raise ModelError(Status.INVALID_DEFINITION, f"definition {layer.definition_id} is missing")
        if definition.kind is not DefinitionKind.STATE_CANDIDATE:
            continue
        applicable = definition.applicability.immutable_matches(static.context, static.controller_id)
        node = _resolve_selector(definition.selector, static, catalog) if applicable else None
        key = definition.precedence_key(layer.owner_id, layer.instance_key)
        candidate_diagnostics.append({"definitionId": definition.stable_id, "ownerId": layer.owner_id, "instanceKey": layer.instance_key, "precedenceKey": key, "applicable": bool(node), "skipReason": None if node else "NOT_APPLICABLE"})
        if node is not None:
            candidates.append((key, layer, node))
    if candidates:
        key, winning_layer, winning_node = max(candidates, key=lambda item: item[0])
        profile_id = static.node_bindings[winning_node.stable_id]
        assert profile_id is not None
        winner = Winner("LAYER", static.controller_id, winning_node.stable_id, profile_id, winning_node.role, winning_layer.definition_id, winning_layer.owner_id, winning_layer.instance_key, winning_layer.entry_generation, key)
    else:
        winner = Winner("BASE", static.controller_id, base_node.stable_id, base_profile_id, base_node.role)
    profile = catalog.state_profiles[winner.profile_id]
    state_values = profile.values()
    controller_values = static.controller_values.values()
    provenance: dict[str, Any] = {}
    for name, value in state_values.items():
        provenance[f"state.{name}"] = {"initial": value, "source": f"profile:{profile.stable_id}", "contributions": [], "normalization": []}
    for name, value in controller_values.items():
        static_record = static.controller_provenance.get(f"controller.{name}")
        provenance[f"controller.{name}"] = to_data(static_record) if static_record else {"initial": value, "source": f"controller:{controller.stable_id}", "contributions": [], "normalization": []}
    modifier_diagnostics: list[dict[str, Any]] = []
    for contribution in static.static_modifiers:
        modifier = catalog.modifiers[contribution.modifier_id]
        if contribution.role_mask and winner.role not in contribution.role_mask:
            modifier_diagnostics.append({"kind": "STATIC", "modifierId": modifier.stable_id, "applied": False, "skipReason": "ROLE_NOT_APPLICABLE"})
            continue
        source = f"static:{contribution.static_priority}:{contribution.rule_id}:{contribution.action_id}:{modifier.stable_id}"
        _fold_modifier(state_values, controller_values, modifier, source, provenance)
        modifier_diagnostics.append({"kind": "STATIC", "modifierId": modifier.stable_id, "applied": True, "precedenceKey": [0, contribution.static_priority, contribution.rule_id, contribution.action_id]})
    runtime_modifiers: list[tuple[tuple[int, int, int, int, int], Layer, OverrideDefinition]] = []
    for layer in layers:
        definition = catalog.definitions[layer.definition_id]
        if definition.kind is DefinitionKind.MODIFIER:
            runtime_modifiers.append((definition.precedence_key(layer.owner_id, layer.instance_key), layer, definition))
    for key, layer, definition in sorted(runtime_modifiers, key=lambda item: item[0]):
        applies = definition.applicability.modifier_matches(static.context, static.controller_id, winner.profile_id, winner.role)
        if applies:
            modifier = catalog.modifiers[definition.modifier_id]
            _fold_modifier(state_values, controller_values, modifier, f"runtime:{key}", provenance)
        modifier_diagnostics.append({"kind": "RUNTIME", "definitionId": definition.stable_id, "ownerId": layer.owner_id, "instanceKey": layer.instance_key, "precedenceKey": key, "applied": applies, "skipReason": None if applies else "FILTER_NOT_APPLICABLE"})
    normalization: list[dict[str, Any]] = []
    if state_values["hopMaxDistance"] < state_values["hopMinDistance"]:
        before = state_values["hopMaxDistance"]
        state_values["hopMaxDistance"] = state_values["hopMinDistance"]
        normalization.append({"field": "state.hopMaxDistance", "rule": "MAX_AT_LEAST_MIN", "before": before, "after": state_values["hopMaxDistance"]})
    if state_values["allowedTile2"] == state_values["allowedTile"] and state_values["allowedTile2"] != "NONE":
        before = state_values["allowedTile2"]
        state_values["allowedTile2"] = "NONE"
        normalization.append({"field": "state.allowedTile2", "rule": "DUPLICATE_SECONDARY_TILE", "before": before, "after": "NONE"})
    if controller_values["exhaustionEnabled"] and controller_values["stamina"] == 0:
        controller_values["stamina"] = 1
        normalization.append({"field": "controller.stamina", "rule": "EXHAUSTION_REQUIRES_STAMINA", "before": 0, "after": 1})
    if controller_values["recoveryDuration"] == 255 and winner.role is not SemanticRole.ASLEEP:
        raise ModelError(Status.INVALID_COMPOSITION, "indefinite recovery is ASLEEP-only")
    if winner.role is SemanticRole.TIRED and controller_values["recoveryDuration"] == 0:
        raise ModelError(Status.INVALID_COMPOSITION, "recoverable non-sleep tired state requires nonzero recovery")
    _validate_state_cross_fields(state_values, Status.INVALID_COMPOSITION)
    for item in normalization:
        provenance[item["field"]]["normalization"].append(item)
    capabilities = {
        "canMove": state_values["locomotion"] not in {"NONE", "IDLE", "CARRIED"},
        "canBattleOnContact": state_values["battleTrigger"] != "NONE",
        "canHop": state_values["hopTimePerTile"] > 0,
        "canTeleport": state_values["teleportTime"] > 0,
        "canRam": state_values["ramMaxSpeed"] > 0,
        "canJumpLedges": bool(state_values["ledgeJump"]),
        "requiresFrameWork": state_values["locomotion"] not in {"NONE", "IDLE"},
    }
    primitives = {
        "locomotion": state_values["locomotion"],
        "target": state_values["target"],
        "reaction": "ASLEEP" if winner.role is SemanticRole.ASLEEP else ("TIRED" if winner.role is SemanticRole.TIRED else "NORMAL"),
        "movementSpeed": state_values["speed"],
        "movementRange": state_values["movementRange"],
    }
    semantic = {"identity": {"controllerId": winner.controller_id, "nodeId": winner.node_id, "profileId": winner.profile_id, "role": winner.role.value}, "stateValues": state_values, "controllerValues": controller_values, "primitives": primitives, "capabilities": capabilities}
    layer_payload = [{"definitionId": layer.definition_id, "ownerId": layer.owner_id, "instanceKey": layer.instance_key, "entryGeneration": layer.entry_generation} for layer in sorted(layers, key=lambda layer: layer.key())]
    effective_hash = stable_hash("effective", semantic)
    plans: list[Mapping[str, Any]] = []
    if previous is not None and previous.effective_hash != effective_hash:
        if previous.winner.node_id != winner.node_id or previous.winner.profile_id != winner.profile_id:
            plans.extend((
                {"phase": "STABILIZE", "action": "RECONCILE_OLD_NODE_RESOURCES", "fromNodeId": previous.winner.node_id},
                {"phase": "POSTCOMMIT", "action": "RUN_NODE_EXIT_ENTRY_HOOKS", "fromNodeId": previous.winner.node_id, "toNodeId": winner.node_id},
            ))
        else:
            plans.append({"phase": "STABILIZE", "action": "RECONCILE_EFFECTIVE_FIELDS"})
        plans.append({"phase": "POSTCOMMIT", "action": "REBUILD_CAPABILITY_AND_FRAME_WORK_MASKS"})
    diagnostics = {"base": {"nodeId": base_node.stable_id, "profileId": base_profile_id}, "candidates": sorted(candidate_diagnostics, key=lambda item: tuple(item["precedenceKey"])), "winner": to_data(winner), "modifiers": modifier_diagnostics, "normalization": normalization}
    return Composition(
        winner, _deep_freeze(state_values), _deep_freeze(controller_values), _deep_freeze(primitives), _deep_freeze(capabilities),
        effective_hash, stable_hash("layers", layer_payload), _deep_freeze(provenance), _deep_freeze(diagnostics), _deep_freeze(plans),
    )


def compose(
    catalog: BehaviorCatalog,
    static: StaticResolution,
    layers: Sequence[Layer],
    *,
    previous: Composition | None = None,
) -> Composition:
    try:
        if type(layers) not in (list, tuple):
            raise ModelError(Status.INVALID_COMPOSITION, "composition layers must be an exact built-in list or tuple")
        layer_snapshot = tuple(layers)
        if type(catalog) is not BehaviorCatalog or type(static) is not StaticResolution or previous is not None and type(previous) is not Composition:
            raise ModelError(Status.INVALID_COMPOSITION, "composition inputs require exact typed catalog/cache values")
        _validate_closed_runtime_graph((catalog, static, layer_snapshot, previous), "compose.inputs")
        BehaviorCatalog.validate(catalog)
        if any(type(layer) is not Layer for layer in layer_snapshot):
            raise ModelError(Status.INVALID_HANDLE, "composition layer snapshot contains a non-Layer value")
        return _compose_impl(catalog, static, layer_snapshot, previous=previous)
    except ModelError:
        raise
    except Exception as exc:
        raise ModelError(Status.INVALID_COMPOSITION, "composition boundary rejected hostile or malformed input") from None


def _validate_composition_layers(catalog: BehaviorCatalog, static: StaticResolution, layers: Sequence[Layer]) -> None:
    if len(layers) > MAX_RUNTIME_LAYERS:
        raise ModelError(Status.CAPACITY_EXCEEDED, f"composition exceeds {MAX_RUNTIME_LAYERS} runtime layers")
    keys: set[tuple[int, int]] = set()
    entries: set[int] = set()
    by_definition: dict[int, list[Layer]] = {}
    for layer in layers:
        identities = (layer.definition_id, layer.owner_id, layer.instance_key, layer.entry_generation)
        if any(type(value) is not int for value in identities) or not 1 <= layer.definition_id <= 0xFFFF or not 1 <= layer.owner_id <= 0xFFFF or not 0 <= layer.instance_key <= 0xFFFF or not 1 <= layer.entry_generation <= GEN_MAX:
            raise ModelError(Status.INVALID_HANDLE, "composition layer identity is outside its typed domain")
        if layer.key() in keys or layer.entry_generation in entries:
            raise ModelError(Status.AMBIGUOUS_DELTA, "composition owner/key and entry generations must be unique")
        keys.add(layer.key())
        entries.add(layer.entry_generation)
        definition = catalog.definitions.get(layer.definition_id)
        if definition is None:
            raise ModelError(Status.INVALID_DEFINITION, f"definition {layer.definition_id} is missing")
        if layer.generated != definition.generated:
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "composition runtime metadata differs from definition")
        if definition.generated.has_required_owner_id and layer.owner_id != definition.generated.required_owner_id:
            raise ModelError(Status.OWNER_NOT_AUTHORIZED, "composition layer owner is not authorized")
        if not definition.allow_multiple_instances_per_owner and layer.instance_key != 0:
            raise ModelError(Status.INSTANCE_KEY_NOT_ALLOWED, "composition layer instanceKey is forbidden")
        if not definition.applicability.immutable_matches(static.context, static.controller_id):
            raise ModelError(Status.NOT_APPLICABLE, "composition layer immutable/controller filter does not match")
        if definition.kind is DefinitionKind.STATE_CANDIDATE and _resolve_selector(definition.selector, static, catalog) is None:
            raise ModelError(Status.NOT_APPLICABLE, "composition candidate selector has no bound target")
        by_definition.setdefault(layer.definition_id, []).append(layer)
    for definition_id, entries_for_definition in by_definition.items():
        definition = catalog.definitions[definition_id]
        owners = {layer.owner_id for layer in entries_for_definition}
        if not definition.allow_multiple_owners and len(owners) > 1:
            raise ModelError(Status.DEFINITION_OWNED, "composition definition is held by multiple owners")
        if not definition.allow_multiple_instances_per_owner and len(entries_for_definition) != len(owners):
            raise ModelError(Status.INSTANCE_KEY_NOT_ALLOWED, "composition definition has multiple per-owner instances")


@dataclass(frozen=True)
class DeltaOperation:
    operation_id: str
    kind: DeltaOpKind
    definition_id: int = 0
    owner_id: int = 0
    instance_key: int = 0
    handle: Handle | None = None
    policy: LifetimePolicy | None = None
    runtime_incarnation: str = ""
    data_generation: int = 0
    data_incarnation: str = ""

    @classmethod
    def apply(cls, operation_id: str, definition_id: int, owner_id: int, instance_key: int = 0) -> "DeltaOperation":
        return cls(operation_id, DeltaOpKind.APPLY, definition_id, owner_id, instance_key)

    @classmethod
    def replace(cls, operation_id: str, definition_id: int, owner_id: int, instance_key: int = 0) -> "DeltaOperation":
        return cls(operation_id, DeltaOpKind.REPLACE, definition_id, owner_id, instance_key)

    @classmethod
    def remove_required(cls, operation_id: str, handle: Handle) -> "DeltaOperation":
        return cls(operation_id, DeltaOpKind.REMOVE_REQUIRED, handle=handle)

    @classmethod
    def remove_if_present(cls, operation_id: str, handle: Handle) -> "DeltaOperation":
        return cls(operation_id, DeltaOpKind.REMOVE_IF_PRESENT, handle=handle)

    @classmethod
    def remove_owner_if_present(cls, operation_id: str, owner_id: int) -> "DeltaOperation":
        return cls(operation_id, DeltaOpKind.REMOVE_OWNER_IF_PRESENT, owner_id=owner_id)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DeltaOperation":
        data = _closed_mapping(data, "deltaOperation", (field_.name for field_ in dataclasses.fields(cls)), status=Status.INVALID_HANDLE)
        handle = _read(data, "handle")
        policy = _read(data, "policy")
        if handle is not None:
            handle = _mapping(handle, "delta.handle", status=Status.INVALID_HANDLE)
        try:
            return cls(
                _symbol(_read(data, "operation_id"), "delta.operationId"), DeltaOpKind(_read(data, "kind")),
                _u16(_read(data, "definition_id", 0), "delta.definitionId", status=Status.INVALID_HANDLE), _u16(_read(data, "owner_id", 0), "delta.ownerId", status=Status.INVALID_HANDLE),
                _u16(_read(data, "instance_key", 0), "delta.instanceKey", status=Status.INVALID_HANDLE), Handle.from_dict(handle) if handle is not None else None,
                LifetimePolicy(policy) if policy is not None else None,
                _symbol(_read(data, "runtime_incarnation"), "delta.runtimeIncarnation", status=Status.INVALID_HANDLE) if _present(data, "runtime_incarnation") else "",
                _u32(_read(data, "data_generation"), "delta.dataGeneration", nonzero=True) if _present(data, "data_generation") else 0,
                _symbol(_read(data, "data_incarnation"), "delta.dataIncarnation", status=Status.INVALID_HANDLE) if _present(data, "data_incarnation") else "",
            )
        except (TypeError, ValueError) as exc:
            raise ModelError(Status.INVALID_HANDLE, f"delta carries an unknown operation/policy discriminant: {exc}") from exc


@dataclass(frozen=True)
class OperationResult:
    operation_id: str
    status: Status
    matched: bool
    handle: Handle | None = None


@dataclass(frozen=True)
class DeltaResult:
    ok: bool
    status: Status
    mutated: bool
    reason: str
    operation_results: tuple[OperationResult, ...]
    generations_before: Mapping[str, int]
    generations_after: Mapping[str, int]
    effective: Composition | None
    plans: tuple[Mapping[str, Any], ...]
    error: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "operation_results", tuple(self.operation_results))
        object.__setattr__(self, "generations_before", _deep_freeze(self.generations_before))
        object.__setattr__(self, "generations_after", _deep_freeze(self.generations_after))
        object.__setattr__(self, "plans", _deep_freeze(self.plans))


def _contained_runtime_delta_failure(runtime: Any, slot_index: Any, reason: Any, exc: Exception) -> DeltaResult:
    """Build a failure result without virtual dispatch or trusting corrupt roots."""

    status = exc.status if type(exc) is ModelError else Status.INVALID_COMPOSITION
    before: Mapping[str, int] = ClosedMap()
    effective: Composition | None = None
    try:
        _require_exact_stack_runtime(runtime)
        StackRuntime._validate_world_integrity(runtime)
        slots = object.__getattribute__(runtime, "slots")
        slot = slots.get(slot_index) if type(slot_index) is int else None
        if type(slot) is SlotRuntime:
            before = ClosedMap({
                "runtimeEpoch": object.__getattribute__(runtime, "runtime_epoch"),
                "slotGeneration": object.__getattribute__(slot, "slot_generation"),
                "staticContextGeneration": object.__getattribute__(slot, "static_context_generation"),
                "layerGeneration": object.__getattribute__(slot, "layer_generation"),
                "effectiveGeneration": object.__getattribute__(slot, "effective_generation"),
            })
            candidate = object.__getattribute__(slot, "composition")
            effective = candidate if type(candidate) is Composition else None
    except Exception:
        before, effective = ClosedMap(), None
    return DeltaResult(
        False, status, False, reason if type(reason) is str else "InvalidRuntimeInput",
        (), before, before, effective, (), "atomic runtime operation rejected",
    )


@dataclass(frozen=True)
class SlotDiagnostics:
    stale_handle_count: int = 0
    duplicate_apply_count: int = 0
    overflow_count: int = 0
    invalid_definition_count: int = 0
    context_no_longer_applicable_count: int = 0
    mandatory_expiry_stale_count: int = 0


@dataclass
class SlotRuntime:
    slot_index: int
    static: StaticResolution | None
    layers: list[Layer]
    timers: dict[tuple[int, int], CandidateTimer]
    slot_generation: int
    static_context_generation: int
    static_context_incarnation: str
    layer_generation: int
    layer_incarnation: str
    layer_incarnation_authenticator: str
    effective_generation: int
    next_entry_generation: int
    next_timer_generation: int
    composition: Composition | None
    timer_allocations: Mapping[tuple[int, int], TimerAllocation] = field(default_factory=lambda: MappingProxyType({}))
    mandatory_expiry_registry: MandatoryExpiryRegistry = field(default_factory=MandatoryExpiryRegistry)
    captured_spawn_policy_id: int = 0
    captured_population_policy_id: int = 0
    captured_spawn_policy_values: Mapping[str, Any] = field(default_factory=dict)
    captured_population_policy_values: Mapping[str, Any] = field(default_factory=dict)
    captured_policy_authenticator: str = ""
    installed_context_authenticator: str = ""
    retained_context_authenticators: tuple[str, ...] = ()
    live: bool = True
    presentation_gate: bool = False
    diagnostics: SlotDiagnostics = field(default_factory=SlotDiagnostics)
    transition_history: deque[Mapping[str, Any]] = field(default_factory=lambda: deque(maxlen=16))

    def generations(self) -> dict[str, int]:
        return {
            "slotGeneration": self.slot_generation,
            "staticContextGeneration": self.static_context_generation,
            "layerGeneration": self.layer_generation,
            "effectiveGeneration": self.effective_generation,
        }


def _validate_closed_runtime_graph(root: Any, path: str = "runtimeGraph") -> None:
    """Callback-free validation of the explicitly closed runtime value domain."""

    active: list[Any] = []
    visited = 0

    def exact_member(value: Any, candidates: tuple[type, ...]) -> type | None:
        value_type = type(value)
        for candidate in candidates:
            if value_type is candidate:
                return candidate
        return None

    def walk(value: Any, current_path: str, depth: int) -> None:
        nonlocal visited
        visited += 1
        if visited > 100001:
            raise ModelError(Status.INVALID_HANDLE, "runtime graph exceeds its object-count bound")
        if depth > 64:
            raise ModelError(Status.INVALID_HANDLE, f"{current_path} exceeds the closed graph depth bound")
        value_type = type(value)
        if value is None or value_type in (bool, int, float, str, bytes):
            return

        enum_type = exact_member(value, _RUNTIME_GRAPH_ENUM_TYPES)
        if enum_type is not None:
            canonical = False
            for candidate_type, members in _RUNTIME_GRAPH_ENUM_MEMBERS:
                if candidate_type is not enum_type:
                    continue
                for member in members:
                    if value is member:
                        canonical = True
                        break
                break
            if not canonical:
                raise ModelError(Status.INVALID_HANDLE, f"{current_path} carries a forged enum value")
            storage = object.__getattribute__(value, "__dict__")
            if type(storage) is not dict or any(type(key) is not str for key in storage) or set(storage) != {"_value_", "_name_", "__objclass__"}:
                raise ModelError(Status.INVALID_HANDLE, f"{current_path} enum storage is not canonical")
            return

        dataclass_type = exact_member(value, _RUNTIME_GRAPH_DATACLASS_TYPES)
        for ancestor in active:
            if value is ancestor:
                raise ModelError(Status.INVALID_HANDLE, f"{current_path} contains a cycle")
        active.append(value)
        try:
            if dataclass_type is not None:
                storage = object.__getattribute__(value, "__dict__")
                field_names: tuple[str, ...] = ()
                expected_carriers: tuple[Any, ...] = ()
                for candidate_type, candidate_fields, candidate_carriers in _RUNTIME_GRAPH_DATACLASS_SCHEMA:
                    if dataclass_type is candidate_type:
                        field_names = candidate_fields
                        expected_carriers = candidate_carriers
                        break
                if type(storage) is not dict or any(type(key) is not str for key in storage) or set(storage) != set(field_names):
                    raise ModelError(Status.INVALID_HANDLE, f"{current_path} dataclass storage is not closed")
                class_storage = type.__getattribute__(dataclass_type, "__dict__")
                for field_name, expected_carrier in zip(field_names, expected_carriers):
                    current_carrier = class_storage[field_name] if field_name in class_storage else _ABSENT_CLASS_FIELD
                    if current_carrier is not expected_carrier:
                        raise ModelError(Status.INVALID_HANDLE, f"{current_path} dataclass field descriptor was replaced")
                if len(field_names) > 100000:
                    raise ModelError(Status.INVALID_HANDLE, "runtime graph container exceeds its element bound")
                for field_name in field_names:
                    walk(storage[field_name], f"{current_path}.{field_name}", depth + 1)
                return
            if value_type is ClosedMap:
                items = object.__getattribute__(value, "_items")
                index = object.__getattribute__(value, "_index")
                if type(items) is not tuple or type(index) is not dict or len(items) != len(index) or len(items) > 100000:
                    raise ModelError(Status.INVALID_HANDLE, f"{current_path} immutable mapping storage is not canonical")
                index_items = tuple(index.items())
                for item_index, pair in enumerate(items):
                    if type(pair) is not tuple or len(pair) != 2:
                        raise ModelError(Status.INVALID_HANDLE, f"{current_path} immutable mapping entry is malformed")
                    walk(pair[0], f"{current_path}.key[{item_index}]", depth + 1)
                    walk(pair[1], f"{current_path}.value[{item_index}]", depth + 1)
                for item_index, (item_pair, index_pair) in enumerate(zip(items, index_items)):
                    if type(index_pair) is not tuple or len(index_pair) != 2:
                        raise ModelError(Status.INVALID_HANDLE, f"{current_path} immutable mapping index entry is malformed")
                    stored_pair = index_pair[1]
                    if type(stored_pair) is not tuple or len(stored_pair) != 2:
                        raise ModelError(Status.INVALID_HANDLE, f"{current_path} immutable mapping index payload is malformed")
                    if item_pair[0] is not stored_pair[0] or item_pair[1] is not stored_pair[1]:
                        raise ModelError(Status.INVALID_HANDLE, f"{current_path} immutable mapping index differs from its canonical entries")
                    if not _closed_map_token_matches(item_pair[0], index_pair[0]):
                        raise ModelError(Status.INVALID_HANDLE, f"{current_path} immutable mapping index token is not canonical")
                return
            if value_type is dict:
                if len(value) > 100000:
                    raise ModelError(Status.INVALID_HANDLE, "runtime graph container exceeds its element bound")
                for item_index, pair in enumerate(value.items()):
                    walk(pair[0], f"{current_path}.key[{item_index}]", depth + 1)
                    walk(pair[1], f"{current_path}.value[{item_index}]", depth + 1)
                return
            if value_type in (list, tuple, deque, frozenset):
                if len(value) > 100000:
                    raise ModelError(Status.INVALID_HANDLE, "runtime graph container exceeds its element bound")
                for item_index, item in enumerate(value):
                    walk(item, f"{current_path}[{item_index}]", depth + 1)
                return
            raise ModelError(Status.INVALID_HANDLE, f"{current_path} carries an unsupported runtime object")
        finally:
            active.pop()

    walk(root, path, 0)


_STACK_RUNTIME_FIELDS = frozenset({
    "_catalog", "data_generation", "_data_incarnation", "_staged_catalog",
    "slot_count", "runtime_epoch", "_secret", "_runtime_incarnation", "slots",
    "_layer_authorities", "_root_anchor", "_secret_authenticator",
})

_ROOT_AUTHORITY_REGISTRY_MAX = 1024
_ROOT_AUTHORITY_REGISTRY: tuple[tuple[Any, bytes], ...] = ()


def _validated_root_authority_registry() -> tuple[tuple[Any, bytes], ...]:
    """Return the closed process-local root registry without user dispatch."""

    registry = _ROOT_AUTHORITY_REGISTRY
    runtime_type = globals().get("StackRuntime")
    if type(registry) is not tuple or len(registry) > _ROOT_AUTHORITY_REGISTRY_MAX:
        raise ModelError(Status.INVALID_HANDLE, "process root-authority registry is malformed or over capacity")
    for index, entry in enumerate(registry):
        entry_type = type(entry[0]) if type(entry) is tuple and len(entry) == 2 else None
        entry_mro = type.__getattribute__(entry_type, "__mro__") if entry_type is not None else ()
        if (
            type(entry) is not tuple or len(entry) != 2
            or runtime_type is None or not any(candidate is runtime_type for candidate in entry_mro)
            or type(entry[1]) is not bytes or len(entry[1]) != 32
        ):
            raise ModelError(Status.INVALID_HANDLE, "process root-authority registry entry is malformed")
        if any(entry[0] is previous[0] for previous in registry[:index]):
            raise ModelError(Status.INVALID_HANDLE, "process root-authority registry contains a duplicate runtime identity")
    return registry


def _external_root_anchor(runtime: Any) -> bytes:
    registry = _validated_root_authority_registry()
    matches = tuple(entry for entry in registry if entry[0] is runtime)
    if len(matches) != 1:
        raise ModelError(Status.INVALID_HANDLE, "runtime has no unique external root authority")
    return matches[0][1]


def _register_external_root_anchor(runtime: Any, anchor: bytes) -> None:
    global _ROOT_AUTHORITY_REGISTRY
    _require_exact_stack_runtime(runtime)
    if type(anchor) is not bytes or len(anchor) != 32:
        raise ModelError(Status.INVALID_HANDLE, "external root authority must be an exact 256-bit value")
    registry = _validated_root_authority_registry()
    if any(entry[0] is runtime for entry in registry):
        raise ModelError(Status.INVALID_HANDLE, "runtime root authority was already registered")
    if len(registry) >= _ROOT_AUTHORITY_REGISTRY_MAX:
        raise ModelError(Status.DATA_BUSY, "process root-authority registry is at capacity")
    _ROOT_AUTHORITY_REGISTRY = registry + ((runtime, anchor),)


def _stage_external_root_anchor_rotation(runtime: Any, old_anchor: bytes, new_anchor: bytes) -> tuple[tuple[Any, bytes], ...]:
    if type(old_anchor) is not bytes or len(old_anchor) != 32 or type(new_anchor) is not bytes or len(new_anchor) != 32:
        raise ModelError(Status.INVALID_HANDLE, "root-authority rotation values are malformed")
    registry = _validated_root_authority_registry()
    replacement_index = -1
    staged: list[tuple[Any, bytes]] = []
    for index, entry in enumerate(registry):
        if entry[0] is runtime:
            if replacement_index != -1 or not hmac.compare_digest(entry[1], old_anchor):
                raise ModelError(Status.INVALID_HANDLE, "root-authority rotation source is stale")
            replacement_index = index
            staged.append((runtime, new_anchor))
        else:
            staged.append(entry)
    if replacement_index == -1:
        raise ModelError(Status.INVALID_HANDLE, "runtime root authority is not registered")
    return tuple(staged)


def _stage_external_root_anchor_removal(runtime: Any) -> tuple[tuple[Any, bytes], ...]:
    registry = _validated_root_authority_registry()
    matches = tuple(index for index, entry in enumerate(registry) if entry[0] is runtime)
    if len(matches) != 1:
        raise ModelError(Status.INVALID_HANDLE, "runtime root authority cannot be uniquely removed")
    target = matches[0]
    return registry[:target] + registry[target + 1:]


def _publish_external_root_authority_registry(staged: tuple[tuple[Any, bytes], ...]) -> None:
    global _ROOT_AUTHORITY_REGISTRY
    # Construction paths call this only after the exact staged tuple has been
    # validated; publication itself is a single callback-free assignment.
    _ROOT_AUTHORITY_REGISTRY = staged


def _rotated_external_root_anchor(anchor: bytes, domain: bytes, runtime_incarnation: str) -> bytes:
    if type(anchor) is not bytes or len(anchor) != 32 or type(domain) is not bytes or type(runtime_incarnation) is not str:
        raise ModelError(Status.INVALID_HANDLE, "root-authority rotation input is malformed")
    return hmac.new(anchor, domain + b":" + runtime_incarnation.encode("ascii"), hashlib.sha256).digest()


def _root_secret_authenticator(
    root_anchor: bytes, secret: bytes, runtime_incarnation: str,
    data_generation: int, data_incarnation: str,
) -> str:
    payload = canonical_json_bytes({
        "domain": "stack-runtime-root-secret-v1",
        "secretHex": secret.hex(),
        "runtimeIncarnation": runtime_incarnation,
        "dataGeneration": data_generation,
        "dataIncarnation": data_incarnation,
    })
    return hmac.new(root_anchor, payload, hashlib.sha256).hexdigest()


def _validate_stack_runtime_root(runtime: Any) -> None:
    """Validate every runtime-owned root and private graph before dereference."""

    _require_exact_stack_runtime(runtime)
    storage = object.__getattribute__(runtime, "__dict__")
    if type(storage) is not dict or any(type(key) is not str for key in storage) or set(storage) != _STACK_RUNTIME_FIELDS:
        raise ModelError(Status.INVALID_HANDLE, "runtime root storage is not the exact closed domain")
    slot_count = storage["slot_count"]
    runtime_epoch = storage["runtime_epoch"]
    data_generation = storage["data_generation"]
    if type(slot_count) is not int or not 1 <= slot_count <= 0x100:
        raise ModelError(Status.INVALID_HANDLE, "runtime slot count is malformed")
    if type(runtime_epoch) is not int or not 1 <= runtime_epoch <= GEN_MAX:
        raise ModelError(Status.INVALID_HANDLE, "runtime epoch is malformed")
    if type(data_generation) is not int or not 1 <= data_generation <= GEN_MAX:
        raise ModelError(Status.INVALID_STATIC_DATA, "behavior-data generation is malformed")
    if type(storage["_secret"]) is not bytes or len(storage["_secret"]) != 32:
        raise ModelError(Status.INVALID_HANDLE, "runtime authentication secret is malformed")
    runtime_incarnation = storage["_runtime_incarnation"]
    data_incarnation = storage["_data_incarnation"]
    if type(runtime_incarnation) is not str or len(runtime_incarnation) != 64 or any(char not in "0123456789abcdef" for char in runtime_incarnation):
        raise ModelError(Status.INVALID_HANDLE, "runtime incarnation must be a canonical lowercase 256-bit tag")
    if data_incarnation != INITIAL_DATA_INCARCATION and (
        type(data_incarnation) is not str or len(data_incarnation) != 64
        or any(char not in "0123456789abcdef" for char in data_incarnation)
    ):
        raise ModelError(Status.INVALID_STATIC_DATA, "behavior-data incarnation is neither the initial sentinel nor a canonical rotated tag")
    root_anchor = storage["_root_anchor"]
    secret_authenticator = storage["_secret_authenticator"]
    if type(root_anchor) is not bytes or len(root_anchor) != 32:
        raise ModelError(Status.INVALID_HANDLE, "runtime root anchor is malformed")
    external_root_anchor = _external_root_anchor(runtime)
    if not hmac.compare_digest(root_anchor, external_root_anchor):
        raise ModelError(Status.INVALID_HANDLE, "runtime root anchor differs from its external process authority")
    if type(secret_authenticator) is not str or len(secret_authenticator) != 64 or any(char not in "0123456789abcdef" for char in secret_authenticator):
        raise ModelError(Status.INVALID_HANDLE, "runtime secret authenticator is malformed")
    expected_secret_authenticator = _root_secret_authenticator(
        external_root_anchor, storage["_secret"], runtime_incarnation,
        data_generation, data_incarnation,
    )
    if not hmac.compare_digest(secret_authenticator, expected_secret_authenticator):
        raise ModelError(Status.INVALID_HANDLE, "runtime secret or root identity was substituted")
    if type(storage["_catalog"]) is not BehaviorCatalog or storage["_staged_catalog"] is not None and type(storage["_staged_catalog"]) is not BehaviorCatalog:
        raise ModelError(Status.INVALID_STATIC_DATA, "runtime behavior catalog storage is malformed")
    if type(storage["slots"]) is not dict:
        raise ModelError(Status.INVALID_HANDLE, "runtime slot table storage is malformed")
    slot_keys = tuple(storage["slots"].keys())
    if any(type(key) is not int for key in slot_keys) or tuple(sorted(slot_keys)) != tuple(range(slot_count)):
        raise ModelError(Status.INVALID_HANDLE, "runtime slot table keys are not canonical")
    if type(storage["_layer_authorities"]) is not ClosedMap:
        raise ModelError(Status.INVALID_HANDLE, "runtime authority table storage is malformed")
    authority_items = object.__getattribute__(storage["_layer_authorities"], "_items")
    if type(authority_items) is not tuple or any(type(pair) is not tuple or len(pair) != 2 or type(pair[0]) is not int for pair in authority_items) or tuple(sorted(pair[0] for pair in authority_items)) != tuple(range(slot_count)):
        raise ModelError(Status.INVALID_HANDLE, "runtime authority table keys are not canonical")
    _validate_closed_runtime_graph((
        storage["_catalog"], storage["_staged_catalog"], storage["slots"],
        storage["_layer_authorities"], slot_count, runtime_epoch, data_generation,
        storage["_secret"], runtime_incarnation, data_incarnation,
        root_anchor, secret_authenticator,
    ), "runtime.root")
    BehaviorCatalog.validate(storage["_catalog"])
    if storage["_staged_catalog"] is not None:
        BehaviorCatalog.validate(storage["_staged_catalog"])


def _clone_runtime_layers(source: Sequence[Layer]) -> list[Layer]:
    """Clone the mutable layer container without audited identity machinery."""

    if type(source) not in (list, tuple) or any(type(layer) is not Layer for layer in source):
        raise ModelError(Status.INVALID_HANDLE, "runtime layer scratch source is not canonical")
    return list(source)


def _clone_runtime_timers(source: Mapping[tuple[int, int], CandidateTimer]) -> dict[tuple[int, int], CandidateTimer]:
    """Clone mutable timers explicitly; ``copy.deepcopy`` audits ``id``."""

    if type(source) is not dict:
        raise ModelError(Status.INVALID_HANDLE, "runtime timer scratch source is not canonical")
    cloned: dict[tuple[int, int], CandidateTimer] = {}
    for key, timer in sorted(source.items()):
        if type(key) is not tuple or len(key) != 2 or any(type(part) is not int for part in key) or type(timer) is not CandidateTimer:
            raise ModelError(Status.INVALID_HANDLE, "runtime timer scratch entry is not canonical")
        cloned[key] = dataclasses.replace(timer)
    return cloned


def _new_inactive_slot(slot_index: int, slot_generation: int) -> SlotRuntime:
    return SlotRuntime(
        slot_index=slot_index, static=None, layers=[], timers={}, slot_generation=slot_generation,
        static_context_generation=1, static_context_incarnation="", layer_generation=1, layer_incarnation="", layer_incarnation_authenticator="", effective_generation=1,
        next_entry_generation=1, next_timer_generation=1, composition=None,
        timer_allocations=MappingProxyType({}), mandatory_expiry_registry=MandatoryExpiryRegistry(),
        captured_spawn_policy_values=MappingProxyType({}), captured_population_policy_values=MappingProxyType({}),
        retained_context_authenticators=(),
        live=False, diagnostics=SlotDiagnostics(), transition_history=deque(maxlen=16),
    )


@dataclass(frozen=True)
class EpochSlotStage:
    layers: list[Layer]
    timers: dict[tuple[int, int], CandidateTimer]
    next_entry_generation: int
    next_timer_generation: int
    layer_generation: int
    layer_incarnation: str
    layer_incarnation_authenticator: str
    composition: Composition
    timer_allocations: Mapping[tuple[int, int], TimerAllocation]
    mandatory_expiry_registry: MandatoryExpiryRegistry


@dataclass(frozen=True)
class LayerIncarnationAuthority:
    runtime_epoch: int
    runtime_incarnation: str
    data_generation: int
    data_incarnation: str
    slot_index: int
    slot_generation: int
    layer_generation: int
    layer_incarnation: str
    authenticator: str


_RUNTIME_GRAPH_DATACLASS_TYPES = (
    StaticContext, ContextMatcher, StateProfile, ControllerValues, ControllerNode,
    Controller, SpawnPolicy, PopulationPolicy, HookSet, PolicyPatch, NodeSelector,
    ModifierOperation, Modifier, Applicability, GeneratedMetadata,
    CandidateTimerPolicy, OverrideDefinition, StaticAction, StaticRule,
    TiredTranslation, BehaviorCatalog, StaticModifierContribution,
    TimerSourceContribution, CandidateTimerSource, StaticResolution, FieldSpec,
    Layer, CandidateTimer, TimerAllocation, ExpiryRemovalTarget, ExpiryPlan,
    MandatoryExpiryRegistry, Handle, Winner, Composition, DeltaOperation,
    OperationResult, DeltaResult, SlotDiagnostics, SlotRuntime, EpochSlotStage,
    LayerIncarnationAuthority,
)
_RUNTIME_GRAPH_ENUM_TYPES = (
    Channel, SemanticRole, DefinitionKind, SelectorKind, OperatorKind,
    LifetimePolicy, TimerClock, HiddenPolicy, RecoveryPolicy,
    TimerDurationPolicy, TiredOriginKind, StaticActionKind, DeltaOpKind, Status,
)
_ABSENT_CLASS_FIELD = object()
_RUNTIME_GRAPH_DATACLASS_SCHEMA = tuple(
    (
        value_type,
        tuple(field_.name for field_ in dataclasses.fields(value_type)),
        tuple(
            type.__getattribute__(value_type, "__dict__")[field_.name]
            if field_.name in type.__getattribute__(value_type, "__dict__")
            else _ABSENT_CLASS_FIELD
            for field_ in dataclasses.fields(value_type)
        ),
    )
    for value_type in _RUNTIME_GRAPH_DATACLASS_TYPES
)
_RUNTIME_GRAPH_ENUM_MEMBERS = tuple(
    (enum_type, tuple(enum_type.__members__.values()))
    for enum_type in _RUNTIME_GRAPH_ENUM_TYPES
)


class StackRuntime:
    """Pure deterministic runtime with atomic scratch/preflight/commit deltas."""

    def __init__(self, catalog: BehaviorCatalog, *, slot_count: int = 10, runtime_epoch: int = 1, handle_secret: str | bytes | None = None, runtime_nonce: str | bytes | None = None):
        _require_exact_stack_runtime(self)
        if type(catalog) is not BehaviorCatalog:
            raise ModelError(Status.INVALID_STATIC_DATA, "runtime requires an exact BehaviorCatalog")
        _validate_closed_runtime_graph(catalog, "runtime.initialCatalog")
        BehaviorCatalog.validate(catalog)
        if type(runtime_epoch) is not int or type(slot_count) is not int or handle_secret is not None and type(handle_secret) not in {str, bytes} or runtime_nonce is not None and type(runtime_nonce) not in {str, bytes} or not 1 <= runtime_epoch <= GEN_MAX or not 1 <= slot_count <= 0x100:
            raise ValueError("runtime_epoch must be nonzero u32 and slot_count positive")
        self._catalog = catalog
        self.data_generation = 1
        self._data_incarnation = INITIAL_DATA_INCARCATION
        self._staged_catalog: BehaviorCatalog | None = None
        self.slot_count = slot_count
        self.runtime_epoch = runtime_epoch
        key_material = secrets.token_bytes(32) if handle_secret is None else (handle_secret.encode("utf-8") if type(handle_secret) is str else handle_secret)
        nonce_material = secrets.token_bytes(32) if runtime_nonce is None else (runtime_nonce.encode("utf-8") if type(runtime_nonce) is str else runtime_nonce)
        self._secret = hmac.new(key_material, b"stack-runtime-key-v1:" + nonce_material, hashlib.sha256).digest()
        self._runtime_incarnation = hashlib.sha256(b"stack-runtime-incarnation-v1:" + nonce_material + self._secret).hexdigest()
        self._root_anchor = secrets.token_bytes(32)
        self._secret_authenticator = _root_secret_authenticator(
            self._root_anchor, self._secret, self._runtime_incarnation,
            self.data_generation, self._data_incarnation,
        )
        self.slots: dict[int, SlotRuntime] = {index: _new_inactive_slot(index, 1) for index in range(slot_count)}
        self._layer_authorities: Mapping[int, LayerIncarnationAuthority | None] = MappingProxyType({index: None for index in range(slot_count)})
        _register_external_root_anchor(self, self._root_anchor)

    @property
    def catalog(self) -> BehaviorCatalog:
        """The active catalog is read-only; activation is a cold staged commit."""
        _require_exact_stack_runtime(self)
        _validate_stack_runtime_root(self)
        return self._catalog

    @property
    def data_incarnation(self) -> str:
        _require_exact_stack_runtime(self)
        _validate_stack_runtime_root(self)
        return self._data_incarnation

    @property
    def runtime_incarnation(self) -> str:
        _require_exact_stack_runtime(self)
        _validate_stack_runtime_root(self)
        return self._runtime_incarnation

    def close(self) -> None:
        """Remove a cold runtime from the process-local authentication domain."""

        _require_exact_stack_runtime(self)
        StackRuntime._validate_world_integrity(self)
        if self._staged_catalog is not None or any(slot.live for slot in self.slots.values()):
            raise ModelError(Status.DATA_BUSY, "runtime root authority can be removed only at a cold boundary")
        staged_registry = _stage_external_root_anchor_removal(self)
        _publish_external_root_authority_registry(staged_registry)

    def stage_catalog(self, catalog: BehaviorCatalog) -> None:
        _require_exact_stack_runtime(self)
        StackRuntime._validate_world_integrity(self)
        if type(catalog) is not BehaviorCatalog:
            raise ModelError(Status.INVALID_STATIC_DATA, "staged behavior data requires an exact BehaviorCatalog")
        _validate_closed_runtime_graph(catalog, "runtime.stagedCatalogInput")
        BehaviorCatalog.validate(catalog)
        object.__setattr__(self, "_staged_catalog", catalog)

    def install_staged_catalog(self) -> int:
        _require_exact_stack_runtime(self)
        StackRuntime._validate_world_integrity(self)
        if self._staged_catalog is None:
            raise ModelError(Status.INVALID_STATIC_DATA, "no behavior catalog is staged")
        if any(slot.live for slot in self.slots.values()):
            raise ModelError(Status.DATA_BUSY, "behavior data can be installed only with zero live or pending work")
        terminal_wrap = self.data_generation == GEN_MAX
        next_generation = 1 if terminal_wrap else self.data_generation + 1
        next_incarnation = hashlib.sha256(self._data_incarnation.encode("ascii") + b":cold-data-activation").hexdigest()
        next_secret = hashlib.sha256(self._secret + b":cold-catalog-activation:" + canonical_json_bytes(self._staged_catalog)).digest()
        next_runtime_incarnation = hashlib.sha256(self._runtime_incarnation.encode("ascii") + b":cold-catalog-activation").hexdigest()
        next_root_anchor = _rotated_external_root_anchor(
            _external_root_anchor(self), b"cold-catalog-activation", next_runtime_incarnation,
        )
        next_secret_authenticator = _root_secret_authenticator(
            next_root_anchor, next_secret, next_runtime_incarnation,
            next_generation, next_incarnation,
        )
        next_slots = {index: _new_inactive_slot(index, slot.slot_generation) for index, slot in sorted(self.slots.items())}
        staged_commit = self._stage_slot_replacements(next_slots)
        # Cold-boundary commit: no handle/cache consumer can survive this point.
        self._publish_slot_replacements(
            staged_commit, secret=next_secret, runtime_incarnation=next_runtime_incarnation,
            secret_authenticator=next_secret_authenticator,
            root_anchor=next_root_anchor,
            catalog=self._staged_catalog, staged_catalog=None,
            data_generation=next_generation, data_incarnation=next_incarnation,
        )
        return next_generation

    def install_slot(self, slot_index: int, context: StaticContext, *, slot_generation: int = 1) -> SlotRuntime:
        _require_exact_stack_runtime(self)
        StackRuntime._validate_world_integrity(self)
        if type(context) is not StaticContext:
            raise ModelError(Status.INVALID_STATIC_DATA, "slot installation requires an exact StaticContext")
        _validate_closed_runtime_graph(context, "runtime.installContext")
        if type(slot_index) is not int or type(slot_generation) is not int or not 0 <= slot_index < self.slot_count or not 1 <= slot_generation <= GEN_MAX:
            raise ValueError("invalid slot index or generation")
        if context.data_generation != self.data_generation or context.data_incarnation != self._data_incarnation:
            raise ModelError(Status.INVALID_STATIC_DATA, "static context behavior-data generation is stale")
        old = self.slots.get(slot_index)
        if old is not None and old.live:
            raise ValueError("slot is already live")
        if old is not None and old.slot_generation != slot_generation and old.slot_generation != 1:
            raise ValueError("new encounter must use the already-invalidated slot generation")
        static = _resolve_static_impl(self.catalog, context)
        composition = _compose_impl(self.catalog, static, ())
        slot = SlotRuntime(
            slot_index=slot_index, static=static, layers=[], timers={}, slot_generation=slot_generation,
            static_context_generation=1, static_context_incarnation="", layer_generation=1, layer_incarnation="", layer_incarnation_authenticator="", effective_generation=1,
            next_entry_generation=1, next_timer_generation=1, composition=composition,
            captured_spawn_policy_id=static.spawn_policy_id,
            captured_population_policy_id=static.population_policy_id,
            captured_spawn_policy_values=static.spawn_policy_values,
            captured_population_policy_values=static.population_policy_values,
        )
        slot.static_context_incarnation = self._initial_static_context_incarnation(slot)
        slot.layer_incarnation = self._initial_layer_incarnation(slot)
        slot.layer_incarnation_authenticator = self._layer_incarnation_authenticator(slot)
        slot.captured_policy_authenticator = self._captured_policy_authenticator(slot)
        slot.installed_context_authenticator = self._installed_context_authenticator(slot)
        slot.retained_context_authenticators = (slot.installed_context_authenticator,)
        self._commit_slot_replacements({slot_index: slot})
        return self.slots[slot_index]

    def destroy_slot(self, slot_index: int) -> None:
        _require_exact_stack_runtime(self)
        try:
            StackRuntime._destroy_slot_impl(self, slot_index)
        except ModelError:
            raise
        except Exception:
            raise ModelError(Status.INVALID_COMPOSITION, "slot destruction staging failed") from None

    def _destroy_slot_impl(self, slot_index: int) -> None:
        StackRuntime._validate_world_integrity(self)
        slot = self._slot(slot_index)
        if not slot.live:
            return
        if slot.slot_generation == GEN_MAX:
            if self.runtime_epoch == GEN_MAX:
                self._commit_terminal_epoch_restart()
                return
            new_epoch, stages = self._stage_global_epoch_rekey(excluded_slots=frozenset({slot_index}))
            replacements = self._build_epoch_replacements(stages, new_epoch)
            replacements[slot_index] = _new_inactive_slot(slot_index, 1)
            staged_commit = self._stage_slot_replacements(replacements, runtime_epoch=new_epoch)
            # Point of no return: publishing the staged epoch/world is assignment-only.
            self._publish_slot_replacements(staged_commit, runtime_epoch=new_epoch)
            return
        else:
            new_slot_generation = slot.slot_generation + 1
        replacement = _new_inactive_slot(slot_index, new_slot_generation)
        self._commit_slot_replacements({slot_index: replacement})

    def _stage_global_epoch_rekey(
        self,
        *,
        target_slot: SlotRuntime | None = None,
        target_layers: Sequence[Layer] | None = None,
        target_timers: Mapping[tuple[int, int], CandidateTimer] | None = None,
        excluded_slots: frozenset[int] = frozenset(),
    ) -> tuple[int, dict[int, EpochSlotStage]]:
        if self.runtime_epoch == GEN_MAX:
            raise ModelError(Status.RUNTIME_EPOCH_RESTARTED, "terminal runtime epoch requires global destructive invalidation")
        StackRuntime._validate_world_integrity(self)
        stages: dict[int, EpochSlotStage] = {}
        new_epoch = self.runtime_epoch + 1
        for index, live_slot in sorted(self.slots.items()):
            if not live_slot.live or index in excluded_slots:
                continue
            if live_slot.static is None or live_slot.composition is None:
                raise ModelError(Status.INVALID_STATIC_DATA, "live slot lacks static/effective cache during epoch rekey")
            layers = _clone_runtime_layers(target_layers if target_slot is live_slot and target_layers is not None else live_slot.layers)
            timers = _clone_runtime_timers(target_timers if target_slot is live_slot and target_timers is not None else live_slot.timers)
            layers, timers, next_entry, next_timer = _rekey_scratch_entries_and_timers(layers, timers)
            new_layer_generation, layer_wrapped = _advance_cache_generation(live_slot.layer_generation) if layers or timers else (live_slot.layer_generation, False)
            new_layer_incarnation = self._rotate_layer_incarnation(live_slot) if layer_wrapped else live_slot.layer_incarnation
            new_layer_incarnation_authenticator = self._layer_incarnation_authenticator(
                live_slot, runtime_epoch=new_epoch, layer_generation=new_layer_generation,
                layer_incarnation=new_layer_incarnation,
            )
            for timer in timers.values():
                self._sign_timer_allocation(live_slot, timer, layer_incarnation=new_layer_incarnation)
            composition = _compose_impl(self.catalog, live_slot.static, layers, previous=live_slot.composition)
            if composition.effective_hash != live_slot.composition.effective_hash:
                raise ModelError(Status.INVALID_COMPOSITION, "epoch-only rekey changed effective output")
            stages[index] = EpochSlotStage(
                layers, timers, next_entry, next_timer, new_layer_generation, new_layer_incarnation,
                new_layer_incarnation_authenticator, composition,
                _timer_allocation_registry(timers),
                self._expiry_registry(
                    live_slot, timers, layers=layers, runtime_epoch=new_epoch,
                    layer_generation=new_layer_generation, layer_incarnation=new_layer_incarnation,
                ),
            )
        return new_epoch, stages

    def _validate_live_slot_integrity(self, slot: SlotRuntime) -> None:
        try:
            self._validate_live_slot_integrity_unchecked(slot)
        except ModelError:
            raise
        except Exception as exc:
            raise ModelError(Status.INVALID_COMPOSITION, f"live slot canonical validation failed: {exc}") from exc

    def _validate_slot_storage_domain(self, slot: SlotRuntime) -> None:
        if type(slot) is not SlotRuntime:
            raise ModelError(Status.INVALID_HANDLE, "slot storage requires the exact SlotRuntime type")
        storage = object.__getattribute__(slot, "__dict__")
        expected_fields = tuple(field_.name for field_ in dataclasses.fields(SlotRuntime))
        if type(storage) is not dict or any(type(key) is not str for key in storage) or tuple(sorted(storage)) != tuple(sorted(expected_fields)):
            raise ModelError(Status.INVALID_HANDLE, "slot storage fields are not the exact closed dataclass domain")
        if type(storage["layers"]) is not list or any(type(layer) is not Layer for layer in storage["layers"]):
            raise ModelError(Status.INVALID_HANDLE, "slot layer storage must be an exact built-in list of Layer values")
        if type(storage["timers"]) is not dict or any(type(key) is not tuple or type(timer) is not CandidateTimer for key, timer in storage["timers"].items()):
            raise ModelError(Status.INVALID_HANDLE, "slot timer storage must be an exact built-in dict of CandidateTimer values")
        if type(storage["timer_allocations"]) is not MappingProxyType or type(storage["mandatory_expiry_registry"]) is not MandatoryExpiryRegistry:
            raise ModelError(Status.INVALID_HANDLE, "slot allocation/expiry storage must use closed canonical registries")
        if type(storage["captured_spawn_policy_values"]) is not MappingProxyType or type(storage["captured_population_policy_values"]) is not MappingProxyType:
            raise ModelError(Status.INVALID_HANDLE, "slot captured policies must use exact immutable mappings")
        if type(storage["retained_context_authenticators"]) is not tuple or type(storage["transition_history"]) is not deque or type(storage["diagnostics"]) is not SlotDiagnostics:
            raise ModelError(Status.INVALID_HANDLE, "slot retained/history/diagnostic storage has an open container domain")
        integer_names = (
            "slot_index", "slot_generation", "static_context_generation", "layer_generation",
            "effective_generation", "next_entry_generation", "next_timer_generation",
            "captured_spawn_policy_id", "captured_population_policy_id",
        )
        if any(type(storage[name]) is not int for name in integer_names):
            raise ModelError(Status.INVALID_HANDLE, "slot scalar generation/identity storage is noncanonical")
        string_names = (
            "static_context_incarnation", "layer_incarnation", "layer_incarnation_authenticator",
            "captured_policy_authenticator", "installed_context_authenticator",
        )
        if any(type(storage[name]) is not str for name in string_names) or type(storage["live"]) is not bool or type(storage["presentation_gate"]) is not bool:
            raise ModelError(Status.INVALID_HANDLE, "slot string/boolean storage is noncanonical")
        if storage["static"] is not None and type(storage["static"]) is not StaticResolution or storage["composition"] is not None and type(storage["composition"]) is not Composition:
            raise ModelError(Status.INVALID_HANDLE, "slot cache storage uses an unsupported runtime type")
        _validate_closed_runtime_graph(slot, f"slot[{storage['slot_index']}]")

    def _validate_live_slot_integrity_unchecked(self, slot: SlotRuntime) -> None:
        self._validate_slot_storage_domain(slot)
        if type(slot.layers) is not list or type(slot.timers) is not dict or not isinstance(slot.timer_allocations, Mapping) or type(slot.mandatory_expiry_registry) is not MandatoryExpiryRegistry or type(slot.transition_history) is not deque or type(slot.diagnostics) is not SlotDiagnostics:
            raise ModelError(Status.INVALID_HANDLE, "live slot indexed registries are malformed")
        _validate_diagnostics(slot.diagnostics)
        for history_item in slot.transition_history:
            self._validate_history_entry(slot, history_item)
        if type(slot.static) is not StaticResolution or type(slot.composition) is not Composition or type(slot.presentation_gate) is not bool:
            raise ModelError(Status.INVALID_HANDLE, "live slot cache/presentation registry is malformed")
        generation_values = (
            slot.slot_generation, slot.static_context_generation, slot.layer_generation,
            slot.effective_generation, slot.next_entry_generation, slot.next_timer_generation,
        )
        if any(type(value) is not int or not 1 <= value <= GEN_MAX for value in generation_values):
            raise ModelError(Status.INVALID_HANDLE, "live slot generation carrier is malformed")
        if slot.static.context.data_generation != self.data_generation or slot.static.context.data_incarnation != self._data_incarnation:
            raise ModelError(Status.INVALID_STATIC_DATA, "live slot static context data identity is stale")
        if type(slot.captured_spawn_policy_id) is not int or type(slot.captured_population_policy_id) is not int or not isinstance(slot.captured_spawn_policy_values, Mapping) or not isinstance(slot.captured_population_policy_values, Mapping):
            raise ModelError(Status.INVALID_HANDLE, "live slot captured policy registry is malformed")
        if slot.captured_spawn_policy_id not in self.catalog.spawn_policies or slot.captured_population_policy_id not in self.catalog.population_policies:
            raise ModelError(Status.INVALID_STATIC_DATA, "live slot captured policy ID is dangling")
        if set(slot.captured_spawn_policy_values) != set(self.catalog.spawn_policies[slot.captured_spawn_policy_id].values()) or set(slot.captured_population_policy_values) != set(self.catalog.population_policies[slot.captured_population_policy_id].values()):
            raise ModelError(Status.INVALID_HANDLE, "live slot captured policy value shape is malformed")
        _authenticator(slot.captured_policy_authenticator, "slot.capturedPolicyAuthenticator")
        if not hmac.compare_digest(slot.captured_policy_authenticator, self._captured_policy_authenticator(slot)):
            raise ModelError(Status.INVALID_HANDLE, "live slot captured policy authentication tag is invalid")
        _authenticator(slot.installed_context_authenticator, "slot.installedContextAuthenticator")
        _authenticator(slot.static_context_incarnation, "slot.staticContextIncarnation")
        _authenticator(slot.layer_incarnation, "slot.layerIncarnation")
        _authenticator(slot.layer_incarnation_authenticator, "slot.layerIncarnationAuthenticator")
        authority = self._layer_authorities.get(slot.slot_index)
        expected_authority = self._layer_authority_for_slot(slot)
        if type(authority) is not LayerIncarnationAuthority or authority != expected_authority or not hmac.compare_digest(slot.layer_incarnation_authenticator, expected_authority.authenticator):
            raise ModelError(Status.INVALID_HANDLE, "live slot layer-incarnation carrier is stale, replayed, or unauthenticated")
        if not hmac.compare_digest(slot.installed_context_authenticator, self._installed_context_authenticator(slot)):
            raise ModelError(Status.INVALID_HANDLE, "live slot installed static-context authentication tag is invalid")
        if type(slot.retained_context_authenticators) is not tuple or any(type(tag) is not str for tag in slot.retained_context_authenticators):
            raise ModelError(Status.INVALID_HANDLE, "live slot retained static-context authentication registry is malformed")
        for tag in slot.retained_context_authenticators:
            _authenticator(tag, "slot.retainedContextAuthenticator")
        expected_context_registry = self._expected_retained_context_authenticators(slot, slot.timers)
        if slot.retained_context_authenticators != expected_context_registry:
            raise ModelError(Status.INVALID_HANDLE, "live slot retained static-context registry is not the exact derived registry")
        for layer in slot.layers:
            self._validate_runtime_layer(layer)
            if layer.entry_generation >= slot.next_entry_generation:
                raise ModelError(Status.INVALID_HANDLE, "layer entry generation is not authenticated by allocation state")
        _validate_composition_layers(self.catalog, slot.static, slot.layers)
        layers_by_key = {layer.key(): layer for layer in slot.layers}
        self._validate_runtime_timer_registry(slot, layers_by_key, slot.static)
        resolved = _resolve_static_impl(self.catalog, slot.static.context)
        if canonical_json_bytes(resolved) != canonical_json_bytes(slot.static):
            raise ModelError(Status.INVALID_COMPOSITION, "live static cache hash does not authenticate its contents")
        recomposed = _compose_impl(self.catalog, slot.static, slot.layers)
        if canonical_json_bytes(recomposed) != canonical_json_bytes(slot.composition) or stable_hash("effective", slot.composition.semantic_output()) != slot.composition.effective_hash:
            raise ModelError(Status.INVALID_COMPOSITION, "live effective/layer cache hash does not authenticate its contents")

    def _build_epoch_replacements(self, stages: Mapping[int, EpochSlotStage], new_epoch: int, *, skip_slot: int | None = None) -> dict[int, SlotRuntime]:
        replacements: dict[int, SlotRuntime] = {}
        for index, stage in sorted(stages.items()):
            if index == skip_slot:
                continue
            slot = self.slots[index]
            history = deque(slot.transition_history, maxlen=16)
            history.append(self._history_entry(slot, {"reason": "RuntimeEpochRekey"}, runtime_epoch=new_epoch, layer_generation=stage.layer_generation, layer_incarnation=stage.layer_incarnation, effective_generation=slot.effective_generation))
            replacements[index] = SlotRuntime(
                slot_index=index, static=slot.static, layers=stage.layers, timers=stage.timers,
                slot_generation=slot.slot_generation, static_context_generation=slot.static_context_generation,
                static_context_incarnation=slot.static_context_incarnation,
                layer_generation=stage.layer_generation, layer_incarnation=stage.layer_incarnation,
                layer_incarnation_authenticator=stage.layer_incarnation_authenticator,
                effective_generation=slot.effective_generation,
                next_entry_generation=stage.next_entry_generation, next_timer_generation=stage.next_timer_generation,
                composition=stage.composition, timer_allocations=stage.timer_allocations,
                mandatory_expiry_registry=stage.mandatory_expiry_registry,
                captured_spawn_policy_id=slot.captured_spawn_policy_id,
                captured_population_policy_id=slot.captured_population_policy_id,
                captured_spawn_policy_values=slot.captured_spawn_policy_values,
                captured_population_policy_values=slot.captured_population_policy_values,
                captured_policy_authenticator=slot.captured_policy_authenticator,
                installed_context_authenticator=slot.installed_context_authenticator,
                retained_context_authenticators=slot.retained_context_authenticators,
                live=True, presentation_gate=slot.presentation_gate, diagnostics=slot.diagnostics,
                transition_history=history,
            )
        return replacements

    def _stage_slot_replacements(
        self,
        replacements: Mapping[int, SlotRuntime],
        *,
        runtime_epoch: int | None = None,
    ) -> tuple[tuple[tuple[int, dict[str, Any]], ...], Mapping[int, LayerIncarnationAuthority | None]]:
        prospective_epoch = self.runtime_epoch if runtime_epoch is None else runtime_epoch
        if type(replacements) is not dict:
            raise ModelError(Status.INVALID_HANDLE, "slot replacements must be an exact built-in dict")
        if prospective_epoch != self.runtime_epoch:
            missing_live = sorted(index for index, slot in self.slots.items() if slot.live and index not in replacements)
            if missing_live:
                raise ModelError(Status.INVALID_HANDLE, f"epoch rekey omitted live slot authorities {missing_live}")
        for index, replacement in sorted(replacements.items()):
            if type(index) is not int or not 0 <= index < self.slot_count:
                raise ModelError(Status.INVALID_HANDLE, "slot replacement index is outside the runtime")
            self._validate_slot_storage_domain(object.__getattribute__(self, "slots")[index])
            self._validate_slot_storage_domain(replacement)
        payloads = {
            index: {
                field_.name: object.__getattribute__(replacement, "__dict__")[field_.name]
                for field_ in dataclasses.fields(SlotRuntime)
            }
            for index, replacement in sorted(replacements.items())
        }
        next_authorities = dict(self._layer_authorities)
        for index, replacement in sorted(replacements.items()):
            if replacement.live:
                authority = self._layer_authority_for_slot(replacement, runtime_epoch=prospective_epoch)
                if not hmac.compare_digest(replacement.layer_incarnation_authenticator, authority.authenticator):
                    raise ModelError(Status.INVALID_HANDLE, "staged slot replacement carries unauthenticated layer authority")
                next_authorities[index] = authority
            else:
                next_authorities[index] = None
        if prospective_epoch != self.runtime_epoch and any(
            authority is not None and authority.runtime_epoch != prospective_epoch
            for authority in next_authorities.values()
        ):
            raise ModelError(Status.INVALID_HANDLE, "prospective epoch authority table is incomplete")
        return tuple(sorted(payloads.items())), MappingProxyType(next_authorities)

    def _publish_slot_replacements(
        self,
        staged: tuple[tuple[tuple[int, dict[str, Any]], ...], Mapping[int, LayerIncarnationAuthority | None]],
        *,
        runtime_epoch: int | None = None,
        secret: bytes | None = None,
        runtime_incarnation: str | None = None,
        secret_authenticator: str | None = None,
        root_anchor: bytes | None = None,
        catalog: BehaviorCatalog | None = None,
        staged_catalog: BehaviorCatalog | None | object = dataclasses.MISSING,
        data_generation: int | None = None,
        data_incarnation: str | None = None,
    ) -> None:
        payloads, staged_authorities = staged
        if type(payloads) is not tuple or type(staged_authorities) is not MappingProxyType:
            raise ModelError(Status.INVALID_HANDLE, "staged publication containers are not closed built-ins")
        field_names = tuple(field_.name for field_ in dataclasses.fields(SlotRuntime))
        for item in payloads:
            if type(item) is not tuple or len(item) != 2 or type(item[0]) is not int or type(item[1]) is not dict or tuple(sorted(item[1])) != tuple(sorted(field_names)):
                raise ModelError(Status.INVALID_HANDLE, "staged slot payload is not an exact closed built-in record")
        prospective_secret = self._secret if secret is None else secret
        prospective_runtime_incarnation = self._runtime_incarnation if runtime_incarnation is None else runtime_incarnation
        prospective_data_generation = self.data_generation if data_generation is None else data_generation
        prospective_data_incarnation = self._data_incarnation if data_incarnation is None else data_incarnation
        prospective_secret_authenticator = self._secret_authenticator if secret_authenticator is None else secret_authenticator
        current_external_root_anchor = _external_root_anchor(self)
        if not hmac.compare_digest(self._root_anchor, current_external_root_anchor):
            raise ModelError(Status.INVALID_HANDLE, "staged publication source root authority is stale")
        prospective_root_anchor = current_external_root_anchor if root_anchor is None else root_anchor
        staged_root_registry = None if root_anchor is None else _stage_external_root_anchor_rotation(
            self, current_external_root_anchor, prospective_root_anchor,
        )
        expected_secret_authenticator = _root_secret_authenticator(
            prospective_root_anchor, prospective_secret, prospective_runtime_incarnation,
            prospective_data_generation, prospective_data_incarnation,
        )
        if type(prospective_secret_authenticator) is not str or not hmac.compare_digest(prospective_secret_authenticator, expected_secret_authenticator):
            raise ModelError(Status.INVALID_HANDLE, "staged root-secret authentication is incomplete")
        slots = object.__getattribute__(self, "slots")
        targets = tuple((slots[index], payload) for index, payload in payloads)
        for slot, payload in targets:
            for field_name in field_names:
                object.__setattr__(slot, field_name, payload[field_name])
        object.__setattr__(self, "_layer_authorities", staged_authorities)
        if secret is not None:
            object.__setattr__(self, "_secret", secret)
        if runtime_incarnation is not None:
            object.__setattr__(self, "_runtime_incarnation", runtime_incarnation)
        if secret_authenticator is not None:
            object.__setattr__(self, "_secret_authenticator", secret_authenticator)
        if root_anchor is not None:
            object.__setattr__(self, "_root_anchor", root_anchor)
        if runtime_epoch is not None:
            object.__setattr__(self, "runtime_epoch", runtime_epoch)
        if catalog is not None:
            object.__setattr__(self, "_catalog", catalog)
        if staged_catalog is not dataclasses.MISSING:
            object.__setattr__(self, "_staged_catalog", staged_catalog)
        if data_generation is not None:
            object.__setattr__(self, "data_generation", data_generation)
        if data_incarnation is not None:
            object.__setattr__(self, "_data_incarnation", data_incarnation)
        if staged_root_registry is not None:
            _publish_external_root_authority_registry(staged_root_registry)

    def _commit_slot_replacements(self, replacements: Mapping[int, SlotRuntime]) -> None:
        staged = self._stage_slot_replacements(replacements)
        self._publish_slot_replacements(staged)

    def _commit_terminal_epoch_restart(self) -> None:
        # Terminal epoch reuse rotates opaque-handle authentication and advances
        # every known slot identity, including inactive/empty slots.  Therefore
        # an epoch/slot/entry payload that repeats can never reproduce old bytes.
        StackRuntime._validate_world_integrity(self)
        new_slot_generations = {
            index: (1 if slot.slot_generation == GEN_MAX else slot.slot_generation + 1)
            for index, slot in sorted(self.slots.items())
        }
        next_slots = {index: _new_inactive_slot(index, generation) for index, generation in sorted(new_slot_generations.items())}
        next_secret = hashlib.sha256(self._secret + b":terminal-runtime-epoch-restart").digest()
        next_runtime_incarnation = hashlib.sha256(self._runtime_incarnation.encode("ascii") + b":terminal-runtime-epoch-restart").hexdigest()
        next_root_anchor = _rotated_external_root_anchor(
            _external_root_anchor(self), b"terminal-runtime-epoch-restart", next_runtime_incarnation,
        )
        next_secret_authenticator = _root_secret_authenticator(
            next_root_anchor, next_secret, next_runtime_incarnation,
            self.data_generation, self._data_incarnation,
        )
        staged_commit = self._stage_slot_replacements(next_slots, runtime_epoch=1)
        self._publish_slot_replacements(
            staged_commit, runtime_epoch=1, secret=next_secret,
            runtime_incarnation=next_runtime_incarnation,
            secret_authenticator=next_secret_authenticator,
            root_anchor=next_root_anchor,
        )

    def _validate_world_integrity(self) -> None:
        _require_exact_stack_runtime(self)
        try:
            _validate_stack_runtime_root(self)
            if type(self.slots) is not dict or set(self.slots) != set(range(self.slot_count)):
                raise ModelError(Status.INVALID_HANDLE, "runtime slot table keys are not the exact canonical index domain")
            if type(self._layer_authorities) is not MappingProxyType or set(self._layer_authorities) != set(range(self.slot_count)):
                raise ModelError(Status.INVALID_HANDLE, "runtime layer-authority table keys are not the exact canonical index domain")
            for index in range(self.slot_count):
                world_slot = self.slots.get(index)
                if world_slot is None:
                    continue
                self._validate_indexed_slot_integrity(index, world_slot)
        except ModelError:
            raise
        except Exception as exc:
            raise ModelError(Status.INVALID_HANDLE, f"indexed world validation failed: {exc}") from exc

    def _validate_indexed_slot_integrity(self, index: int, slot: SlotRuntime) -> None:
        self._validate_slot_storage_domain(slot)
        if type(slot) is not SlotRuntime or type(slot.slot_index) is not int or slot.slot_index != index or type(slot.live) is not bool:
            raise ModelError(Status.INVALID_HANDLE, f"indexed slot {index} identity is malformed")
        if slot.live:
            self._validate_live_slot_integrity(slot)
            return
        if self._layer_authorities.get(index) is not None:
            raise ModelError(Status.INVALID_HANDLE, f"inactive slot {index} retains live layer authority")
        generation_values = (slot.slot_generation, slot.static_context_generation, slot.layer_generation, slot.effective_generation, slot.next_entry_generation, slot.next_timer_generation)
        if any(type(value) is not int or not 1 <= value <= GEN_MAX for value in generation_values):
            raise ModelError(Status.INVALID_HANDLE, f"inactive slot {index} generation carrier is malformed")
        canonical_empty = (
            slot.static is None and slot.composition is None and type(slot.layers) is list and not slot.layers
            and type(slot.timers) is dict and not slot.timers and isinstance(slot.timer_allocations, Mapping) and not slot.timer_allocations
            and type(slot.mandatory_expiry_registry) is MandatoryExpiryRegistry and not slot.mandatory_expiry_registry
            and slot.static_context_generation == slot.layer_generation == slot.effective_generation == 1
            and slot.next_entry_generation == slot.next_timer_generation == 1
            and slot.captured_spawn_policy_id == slot.captured_population_policy_id == 0
            and isinstance(slot.captured_spawn_policy_values, Mapping) and not slot.captured_spawn_policy_values
            and isinstance(slot.captured_population_policy_values, Mapping) and not slot.captured_population_policy_values
            and slot.captured_policy_authenticator == "" and slot.presentation_gate is False
            and slot.installed_context_authenticator == ""
            and slot.static_context_incarnation == ""
            and slot.layer_incarnation == ""
            and slot.layer_incarnation_authenticator == ""
            and slot.retained_context_authenticators == ()
            and type(slot.diagnostics) is SlotDiagnostics and slot.diagnostics == SlotDiagnostics()
            and type(slot.transition_history) is deque and not slot.transition_history
        )
        if not canonical_empty:
            raise ModelError(Status.INVALID_HANDLE, f"inactive slot {index} violates canonical empty invariants")

    def _slot(self, slot_index: int) -> SlotRuntime:
        if type(slot_index) is not int or not 0 <= slot_index < self.slot_count:
            raise ModelError(Status.INVALID_HANDLE, "slot index must be a bounded integer")
        slot = self.slots.get(slot_index)
        if slot is None:
            raise ValueError(f"slot {slot_index} is not installed")
        return slot

    def _auth_payload(self, runtime_epoch: int, slot_index: int, slot_generation: int, owner_id: int, instance_key: int, entry_generation: int, layer_incarnation: str) -> bytes:
        return canonical_json_bytes({
            "domain": "runtime-layer-handle-v2", "runtimeIncarnation": self._runtime_incarnation,
            "dataGeneration": self.data_generation, "dataIncarnation": self._data_incarnation,
            "runtimeEpoch": runtime_epoch, "slotIndex": slot_index, "slotGeneration": slot_generation,
            "layerIncarnation": layer_incarnation,
            "ownerId": owner_id, "instanceKey": instance_key, "entryGeneration": entry_generation,
        })

    def _history_entry(self, slot: SlotRuntime, payload: Mapping[str, Any], *, runtime_epoch: int | None = None, static_context_generation: int | None = None, layer_generation: int | None = None, layer_incarnation: str | None = None, effective_generation: int | None = None) -> Mapping[str, Any]:
        body = {
            "runtimeEpoch": self.runtime_epoch if runtime_epoch is None else runtime_epoch,
            "runtimeIncarnation": self._runtime_incarnation,
            "dataGeneration": self.data_generation, "dataIncarnation": self._data_incarnation,
            "slotIndex": slot.slot_index, "slotGeneration": slot.slot_generation,
            "staticContextGeneration": slot.static_context_generation if static_context_generation is None else static_context_generation,
            "staticContextIncarnation": slot.static_context_incarnation,
            "layerGeneration": slot.layer_generation if layer_generation is None else layer_generation,
            "layerIncarnation": slot.layer_incarnation if layer_incarnation is None else layer_incarnation,
            "effectiveGeneration": slot.effective_generation if effective_generation is None else effective_generation,
            "payload": _deep_freeze(payload),
        }
        tag = hmac.new(self._secret, canonical_json_bytes({"domain": "transition-history-v1", **body}), hashlib.sha256).hexdigest()
        return _deep_freeze({**body, "authenticator": tag})

    def _validate_history_entry(self, slot: SlotRuntime, entry: Any) -> None:
        if type(entry) is not MappingProxyType or set(entry) != {"runtimeEpoch", "runtimeIncarnation", "dataGeneration", "dataIncarnation", "slotIndex", "slotGeneration", "staticContextGeneration", "staticContextIncarnation", "layerGeneration", "layerIncarnation", "effectiveGeneration", "payload", "authenticator"}:
            raise ModelError(Status.INVALID_HANDLE, "transition history entry is not closed canonical data")
        if entry["runtimeIncarnation"] != self._runtime_incarnation or entry["dataGeneration"] != self.data_generation or entry["dataIncarnation"] != self._data_incarnation or entry["slotIndex"] != slot.slot_index or entry["slotGeneration"] != slot.slot_generation:
            raise ModelError(Status.INVALID_HANDLE, "transition history identity is stale or forged")
        for name in ("runtimeEpoch", "staticContextGeneration", "layerGeneration", "effectiveGeneration"):
            if type(entry[name]) is not int or not 1 <= entry[name] <= GEN_MAX:
                raise ModelError(Status.INVALID_HANDLE, "transition history generation is malformed")
        _authenticator(entry["staticContextIncarnation"], "transitionHistory.staticContextIncarnation")
        _authenticator(entry["layerIncarnation"], "transitionHistory.layerIncarnation")
        _authenticator(entry["authenticator"], "transitionHistory.authenticator")
        body = {key: entry[key] for key in entry if key != "authenticator"}
        expected = hmac.new(self._secret, canonical_json_bytes({"domain": "transition-history-v1", **body}), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(entry["authenticator"], expected):
            raise ModelError(Status.INVALID_HANDLE, "transition history authentication failed")

    def _make_handle(self, slot: SlotRuntime, layer: Layer) -> Handle:
        return self._make_handle_at_epoch(slot, layer, self.runtime_epoch)

    def _make_handle_at_epoch(self, slot: SlotRuntime, layer: Layer, runtime_epoch: int) -> Handle:
        return self._make_handle_at_identity(slot, layer, runtime_epoch, slot.layer_incarnation)

    def _make_handle_at_identity(self, slot: SlotRuntime, layer: Layer, runtime_epoch: int, layer_incarnation: str) -> Handle:
        payload = self._auth_payload(runtime_epoch, slot.slot_index, slot.slot_generation, layer.owner_id, layer.instance_key, layer.entry_generation, layer_incarnation)
        auth = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()[:32]
        return Handle(runtime_epoch, slot.slot_index, slot.slot_generation, layer.owner_id, layer.instance_key, layer.entry_generation, auth)

    def _validate_handle_shape(self, slot: SlotRuntime, handle: Handle) -> None:
        identity_values = (handle.runtime_epoch, handle.slot_index, handle.slot_generation, handle.owner_id, handle.instance_key, handle.entry_generation)
        if any(type(value) is not int for value in identity_values) or min(handle.runtime_epoch, handle.slot_generation, handle.owner_id, handle.entry_generation) <= 0 or max(handle.runtime_epoch, handle.slot_generation, handle.entry_generation) > GEN_MAX or not 0 <= handle.instance_key <= 0xFFFF or handle.owner_id > 0xFFFF or not 0 <= handle.slot_index < self.slot_count:
            raise ModelError(Status.INVALID_HANDLE, "handle contains zero/negative identity")
        _handle_authenticator(handle.authenticator)
        payload = self._auth_payload(handle.runtime_epoch, handle.slot_index, handle.slot_generation, handle.owner_id, handle.instance_key, handle.entry_generation, slot.layer_incarnation)
        expected = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(handle.authenticator, expected):
            raise ModelError(Status.INVALID_HANDLE, "handle authenticator is invalid")
        if handle.slot_index != slot.slot_index:
            raise ModelError(Status.WRONG_SLOT, "handle names another slot")

    def _find_handle(self, slot: SlotRuntime, handle: Handle, layers: Sequence[Layer]) -> Layer | None:
        self._validate_handle_shape(slot, handle)
        if handle.runtime_epoch != self.runtime_epoch or handle.slot_generation != slot.slot_generation:
            return None
        return next((layer for layer in layers if layer.owner_id == handle.owner_id and layer.instance_key == handle.instance_key and layer.entry_generation == handle.entry_generation), None)

    def _timer_allocation_authenticator(self, slot: SlotRuntime, timer: CandidateTimer, *, static_context_incarnation: str | None = None, layer_incarnation: str | None = None) -> str:
        context_incarnation = slot.static_context_incarnation if static_context_incarnation is None else static_context_incarnation
        resolved_layer_incarnation = slot.layer_incarnation if layer_incarnation is None else layer_incarnation
        payload = canonical_json_bytes({
            "domain": "candidate-timer-allocation-v1",
            "runtimeIncarnation": self._runtime_incarnation,
            "dataGeneration": self.data_generation, "dataIncarnation": self._data_incarnation,
            "slotIndex": slot.slot_index, "slotGeneration": slot.slot_generation,
            "staticContextIncarnation": context_incarnation,
            "layerIncarnation": resolved_layer_incarnation,
            "ownerId": timer.owner_id, "instanceKey": timer.instance_key,
            "entryGeneration": timer.entry_generation,
            "timerGeneration": timer.timer_generation,
            "expiryPlanGeneration": timer.expiry_plan_generation,
            "armedDefinitionId": timer.armed_definition_id,
            "armedDuration": timer.armed_duration,
            "armedIndefinite": timer.armed_indefinite,
            "armedStaticHash": timer.armed_static_hash,
            "armedSourceHash": timer.armed_source_hash,
            "armedSource": timer.armed_source,
            "armedContextAuthenticator": timer.armed_context_authenticator,
            "clock": timer.clock.value, "hiddenPolicy": timer.hidden_policy.value,
            "recoveryPolicy": timer.recovery_policy.value,
            "calmResetOwnerIds": timer.calm_reset_owner_ids,
            "recoveryTransitionId": timer.recovery_transition_id,
        })
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def _captured_policy_authenticator(self, slot: SlotRuntime) -> str:
        payload = canonical_json_bytes({
            "domain": "captured-creation-policy-v1",
            "runtimeIncarnation": self._runtime_incarnation,
            "dataGeneration": self.data_generation, "dataIncarnation": self._data_incarnation,
            "slotIndex": slot.slot_index, "slotGeneration": slot.slot_generation,
            "spawnPolicyId": slot.captured_spawn_policy_id,
            "spawnPolicyValues": slot.captured_spawn_policy_values,
            "populationPolicyId": slot.captured_population_policy_id,
            "populationPolicyValues": slot.captured_population_policy_values,
        })
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def _initial_static_context_incarnation(self, slot: SlotRuntime) -> str:
        payload = canonical_json_bytes({
            "domain": "static-context-incarnation-v1", "runtimeIncarnation": self._runtime_incarnation,
            "dataGeneration": self.data_generation, "dataIncarnation": self._data_incarnation,
            "slotIndex": slot.slot_index, "slotGeneration": slot.slot_generation,
        })
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def _rotate_static_context_incarnation(self, slot: SlotRuntime) -> str:
        _authenticator(slot.static_context_incarnation, "slot.staticContextIncarnation")
        payload = canonical_json_bytes({
            "domain": "static-context-incarnation-wrap-v1",
            "runtimeIncarnation": self._runtime_incarnation,
            "dataGeneration": self.data_generation, "dataIncarnation": self._data_incarnation,
            "slotIndex": slot.slot_index, "slotGeneration": slot.slot_generation,
            "previous": slot.static_context_incarnation,
        })
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def _initial_layer_incarnation(self, slot: SlotRuntime) -> str:
        payload = canonical_json_bytes({
            "domain": "layer-incarnation-v1", "runtimeIncarnation": self._runtime_incarnation,
            "dataGeneration": self.data_generation, "dataIncarnation": self._data_incarnation,
            "slotIndex": slot.slot_index, "slotGeneration": slot.slot_generation,
        })
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def _rotate_layer_incarnation(self, slot: SlotRuntime) -> str:
        _authenticator(slot.layer_incarnation, "slot.layerIncarnation")
        payload = canonical_json_bytes({
            "domain": "layer-incarnation-wrap-v1", "runtimeIncarnation": self._runtime_incarnation,
            "dataGeneration": self.data_generation, "dataIncarnation": self._data_incarnation,
            "slotIndex": slot.slot_index, "slotGeneration": slot.slot_generation,
            "previous": slot.layer_incarnation,
        })
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def _layer_incarnation_authenticator(
        self,
        slot: SlotRuntime,
        *,
        runtime_epoch: int | None = None,
        layer_generation: int | None = None,
        layer_incarnation: str | None = None,
    ) -> str:
        resolved_epoch = self.runtime_epoch if runtime_epoch is None else runtime_epoch
        resolved_generation = slot.layer_generation if layer_generation is None else layer_generation
        resolved_incarnation = slot.layer_incarnation if layer_incarnation is None else layer_incarnation
        payload = canonical_json_bytes({
            "domain": "authoritative-layer-incarnation-v1",
            "runtimeEpoch": resolved_epoch, "runtimeIncarnation": self._runtime_incarnation,
            "dataGeneration": self.data_generation, "dataIncarnation": self._data_incarnation,
            "slotIndex": slot.slot_index, "slotGeneration": slot.slot_generation,
            "layerGeneration": resolved_generation, "layerIncarnation": resolved_incarnation,
        })
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def _layer_authority_for_slot(
        self,
        slot: SlotRuntime,
        *,
        runtime_epoch: int | None = None,
        layer_generation: int | None = None,
        layer_incarnation: str | None = None,
    ) -> LayerIncarnationAuthority:
        resolved_epoch = self.runtime_epoch if runtime_epoch is None else runtime_epoch
        resolved_generation = slot.layer_generation if layer_generation is None else layer_generation
        resolved_incarnation = slot.layer_incarnation if layer_incarnation is None else layer_incarnation
        return LayerIncarnationAuthority(
            resolved_epoch, self._runtime_incarnation, self.data_generation, self._data_incarnation,
            slot.slot_index, slot.slot_generation, resolved_generation, resolved_incarnation,
            self._layer_incarnation_authenticator(
                slot, runtime_epoch=resolved_epoch, layer_generation=resolved_generation,
                layer_incarnation=resolved_incarnation,
            ),
        )

    def _expected_retained_context_authenticators(
        self,
        slot: SlotRuntime,
        timers: Mapping[tuple[int, int], CandidateTimer],
        *,
        installed_context_authenticator: str | None = None,
    ) -> tuple[str, ...]:
        current = slot.installed_context_authenticator if installed_context_authenticator is None else installed_context_authenticator
        _authenticator(current, "slot.installedContextAuthenticator")
        armed: set[str] = set()
        for key in sorted(timers):
            timer = timers[key]
            if type(timer) is not CandidateTimer or type(timer.armed_context_authenticator) is not str:
                raise ModelError(Status.INVALID_HANDLE, "retained context registry references a malformed timer")
            _authenticator(timer.armed_context_authenticator, "candidateTimer.armedContextAuthenticator")
            if timer.armed_context_authenticator != current:
                armed.add(timer.armed_context_authenticator)
        registry = (current, *sorted(armed))
        if len(registry) > MAX_RUNTIME_LAYERS + 1:
            raise ModelError(Status.INVALID_HANDLE, "retained context registry exceeds its exact runtime bound")
        return registry

    def _installed_context_authenticator(
        self,
        slot: SlotRuntime,
        *,
        static: StaticResolution | None = None,
        static_context_generation: int | None = None,
        static_context_incarnation: str | None = None,
    ) -> str:
        resolved_static = slot.static if static is None else static
        resolved_generation = slot.static_context_generation if static_context_generation is None else static_context_generation
        resolved_incarnation = slot.static_context_incarnation if static_context_incarnation is None else static_context_incarnation
        if resolved_static is None:
            return ""
        payload = canonical_json_bytes({
            "domain": "installed-static-context-v1", "runtimeIncarnation": self._runtime_incarnation,
            "dataGeneration": self.data_generation, "dataIncarnation": self._data_incarnation,
            "slotIndex": slot.slot_index, "slotGeneration": slot.slot_generation,
            "staticContextGeneration": resolved_generation,
            "staticContextIncarnation": resolved_incarnation,
            "context": resolved_static.context, "staticHash": resolved_static.hash,
            "capturedPolicyAuthenticator": slot.captured_policy_authenticator,
        })
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def _sign_timer_allocation(self, slot: SlotRuntime, timer: CandidateTimer, *, static_context_incarnation: str | None = None, layer_incarnation: str | None = None) -> None:
        timer.allocation_authenticator = self._timer_allocation_authenticator(
            slot, timer, static_context_incarnation=static_context_incarnation,
            layer_incarnation=layer_incarnation,
        )

    def _validate_operation_definition(self, definition_id: int, owner_id: int, instance_key: int) -> OverrideDefinition:
        if type(definition_id) is not int or not 1 <= definition_id <= 0xFFFF:
            raise ModelError(Status.INVALID_DEFINITION, "definitionId must be a nonzero u16")
        if type(owner_id) is not int or not 1 <= owner_id <= 0xFFFF:
            raise ModelError(Status.INVALID_HANDLE, "ownerId must be a nonzero u16")
        if type(instance_key) is not int or not 0 <= instance_key <= 0xFFFF:
            raise ModelError(Status.INVALID_HANDLE, "instanceKey must be a u16")
        definition = self.catalog.definitions.get(definition_id)
        if definition is None:
            raise ModelError(Status.INVALID_DEFINITION, f"definition {definition_id} is missing")
        _validate_generated_definition(definition, self.catalog.owner_names)
        meta = definition.generated
        if meta.has_required_owner_id and owner_id != meta.required_owner_id:
            raise ModelError(Status.OWNER_NOT_AUTHORIZED, f"owner {owner_id} is not authorized for definition {definition_id}")
        if (meta.has_tired_origin_kind or meta.has_required_owner_id) and instance_key != 0:
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "generated tired instanceKey must be zero")
        if not definition.allow_multiple_instances_per_owner and instance_key != 0:
            raise ModelError(Status.INSTANCE_KEY_NOT_ALLOWED, "definition requires instanceKey zero")
        return definition

    def _validate_runtime_layer(self, layer: Layer) -> OverrideDefinition:
        definition = self.catalog.definitions.get(layer.definition_id)
        if definition is None:
            raise ModelError(Status.INVALID_DEFINITION, f"runtime layer definition {layer.definition_id} is missing")
        if layer.generated != definition.generated:
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, f"runtime metadata for definition {layer.definition_id} is corrupt")
        self._validate_operation_definition(layer.definition_id, layer.owner_id, layer.instance_key)
        if layer.entry_generation <= 0:
            raise ModelError(Status.INVALID_HANDLE, "runtime entry generation is zero")
        return definition

    def _validate_runtime_timer(
        self,
        slot: SlotRuntime,
        timer: CandidateTimer,
        layers_by_key: Mapping[tuple[int, int], Layer],
        static: StaticResolution,
        allocation: TimerAllocation | None,
        next_timer_generation: int,
    ) -> None:
        integer_fields = (
            timer.owner_id, timer.instance_key, timer.entry_generation, timer.remaining_ticks,
            timer.timer_generation, timer.recovery_transition_id, timer.expiry_plan_generation,
            timer.armed_definition_id, timer.armed_duration,
        )
        if any(type(value) is not int for value in integer_fields) or not 1 <= timer.owner_id <= 0xFFFF or not 0 <= timer.instance_key <= 0xFFFF or not 1 <= timer.entry_generation <= GEN_MAX or not 0 <= timer.remaining_ticks <= 255 or not 1 <= timer.timer_generation <= GEN_MAX or not 1 <= timer.expiry_plan_generation <= GEN_MAX or not 1 <= timer.armed_definition_id <= 0xFFFF or not 0 <= timer.armed_duration <= 255 or not 0 <= timer.recovery_transition_id <= 0xFFFF:
            raise ModelError(Status.INVALID_HANDLE, "candidate timer integer identity/value fields are noncanonical")
        if type(timer.zero_pending) is not bool or type(timer.armed_indefinite) is not bool or type(timer.clock) is not TimerClock or type(timer.hidden_policy) is not HiddenPolicy or type(timer.recovery_policy) is not RecoveryPolicy or type(timer.calm_reset_owner_ids) is not tuple or any(type(owner) is not int or not 1 <= owner <= 0xFFFF for owner in timer.calm_reset_owner_ids):
            raise ModelError(Status.INVALID_HANDLE, "candidate timer boolean/enum/recovery fields are noncanonical")
        layer = layers_by_key.get(timer.key())
        if layer is None or layer.entry_generation != timer.entry_generation:
            raise ModelError(Status.INVALID_HANDLE, "candidate timer has no exact owning runtime layer")
        definition = self.catalog.definitions[layer.definition_id]
        armed_definition = self.catalog.definitions.get(timer.armed_definition_id)
        armed_policy = armed_definition.timer if armed_definition is not None else None
        if armed_policy is None or _generated_family(armed_definition.generated) != _generated_family(definition.generated):
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "candidate timer armed definition is missing or from another family")
        if _generated_family(definition.generated) == ("ordinary",) and armed_definition.stable_id != definition.stable_id:
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "ordinary candidate timer cannot change its armed definition")
        if timer.clock is not armed_policy.clock or timer.hidden_policy is not armed_policy.hidden_policy or timer.recovery_policy is not armed_policy.recovery_policy or timer.calm_reset_owner_ids != armed_policy.calm_reset_owner_ids or timer.recovery_transition_id != armed_policy.recovery_transition_id:
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "candidate timer differs from its armed policy/recovery family")
        if timer.recovery_policy is RecoveryPolicy.REVEAL_UNDERLYING and not static.controller_values.allow_reveal_underlying_recovery:
            raise ModelError(Status.NOT_APPLICABLE, "retained resolved controller policy does not permit REVEAL_UNDERLYING recovery")
        if timer.recovery_policy is RecoveryPolicy.LEGACY_RETURN_CALM and timer.owner_id in timer.calm_reset_owner_ids:
            raise ModelError(Status.INVALID_HANDLE, "LRC expiring owner overlaps its calm-reset owner batch")
        if type(timer.armed_duration) is not int or type(timer.armed_indefinite) is not bool or not 0 <= timer.armed_duration <= 255 or timer.armed_indefinite != (timer.armed_duration == 255):
            raise ModelError(Status.INVALID_HANDLE, "candidate timer armed-source duration/provenance is noncanonical")
        if type(timer.armed_static_hash) is not str or type(timer.armed_source_hash) is not str or type(timer.allocation_authenticator) is not str or type(timer.armed_context_authenticator) is not str:
            raise ModelError(Status.INVALID_HANDLE, "candidate timer armed-source authentication fields are malformed")
        _authenticator(timer.allocation_authenticator, "candidateTimer.allocationAuthenticator")
        if type(timer.armed_source) is not CandidateTimerSource:
            raise ModelError(Status.INVALID_HANDLE, "candidate timer lacks its immutable captured static source")
        _authenticator(timer.armed_context_authenticator, "candidateTimer.armedContextAuthenticator")
        if timer.armed_context_authenticator not in slot.retained_context_authenticators:
            raise ModelError(Status.INVALID_HANDLE, "candidate timer source context was never authenticated for this slot")
        expected_source_hash = stable_hash("timer-source", timer.armed_source)
        if expected_source_hash != timer.armed_source_hash or timer.armed_source.normalized_duration != timer.armed_duration or timer.armed_source.indefinite is not timer.armed_indefinite:
            raise ModelError(Status.INVALID_HANDLE, "candidate timer differs from its immutable captured static source")
        if static.hash == timer.armed_static_hash and (timer.armed_definition_id not in static.candidate_timer_sources or static.candidate_timer_sources[timer.armed_definition_id] != timer.armed_source):
            raise ModelError(Status.INVALID_HANDLE, "candidate timer captured source differs from its installed static context")
        expected_authenticator = self._timer_allocation_authenticator(slot, timer)
        if not hmac.compare_digest(timer.allocation_authenticator, expected_authenticator):
            raise ModelError(Status.INVALID_HANDLE, "candidate timer armed-source allocation tag is invalid")
        if not 0 <= timer.remaining_ticks <= 255 or not 1 <= timer.timer_generation <= GEN_MAX or not 1 <= timer.expiry_plan_generation <= GEN_MAX:
            raise ModelError(Status.INVALID_HANDLE, "candidate timer identity/value is outside its domain")
        expected_allocation = TimerAllocation(
            timer.entry_generation, timer.timer_generation, timer.expiry_plan_generation,
            timer.armed_definition_id, timer.armed_duration, timer.armed_indefinite,
            timer.clock, timer.hidden_policy, timer.recovery_policy,
            timer.calm_reset_owner_ids, timer.recovery_transition_id,
            timer.armed_static_hash, timer.armed_source_hash, timer.allocation_authenticator,
            timer.armed_source, timer.armed_context_authenticator,
        )
        if allocation != expected_allocation or timer.expiry_plan_generation != timer.timer_generation or timer.timer_generation >= next_timer_generation:
            raise ModelError(Status.INVALID_HANDLE, "candidate timer generation is not authenticated by allocation state")
        if timer.zero_pending != (timer.remaining_ticks == 0):
            raise ModelError(Status.INVALID_HANDLE, "candidate timer zero-pending state is noncanonical")
        if timer.armed_indefinite and timer.remaining_ticks != 255 or not timer.armed_indefinite and timer.remaining_ticks > timer.armed_duration:
            raise ModelError(Status.INVALID_HANDLE, "candidate timer remaining duration exceeds its authenticated armed source")

    def _validate_runtime_timer_registry(self, slot: SlotRuntime, layers_by_key: Mapping[tuple[int, int], Layer], static: StaticResolution) -> None:
        timer_keys = list(slot.timers.keys())
        allocation_keys = list(slot.timer_allocations.keys())
        for key in timer_keys + allocation_keys:
            if type(key) is not tuple or len(key) != 2 or any(type(value) is not int for value in key) or not 1 <= key[0] <= 0xFFFF or not 0 <= key[1] <= 0xFFFF:
                raise ModelError(Status.INVALID_HANDLE, "timer registry contains a malformed owner/key")
        timer_keys.sort()
        allocation_keys.sort()
        if allocation_keys != timer_keys:
            raise ModelError(Status.INVALID_HANDLE, "timer allocation registry differs from live timer keys")
        timers = [slot.timers[key] for key in timer_keys]
        if any(type(timer) is not CandidateTimer for timer in timers):
            raise ModelError(Status.INVALID_HANDLE, "timer registry value has the wrong typed shape")
        timer_generations = [timer.timer_generation for timer in timers]
        plan_generations = [timer.expiry_plan_generation for timer in timers]
        if len(timer_generations) != len(set(timer_generations)) or len(plan_generations) != len(set(plan_generations)):
            raise ModelError(Status.INVALID_HANDLE, "live timer allocation generations are not unique")
        for key in timer_keys:
            timer = slot.timers[key]
            if key != timer.key():
                raise ModelError(Status.INVALID_HANDLE, "timer registry key differs from timer identity")
            self._validate_runtime_timer(slot, timer, layers_by_key, static, slot.timer_allocations.get(key), slot.next_timer_generation)
        expected_mandatory = self._expiry_registry(slot, slot.timers, layers=tuple(layers_by_key.values()), static=static)
        if type(slot.mandatory_expiry_registry) is not MandatoryExpiryRegistry or slot.mandatory_expiry_registry.canonical_bytes() != expected_mandatory.canonical_bytes():
            raise ModelError(Status.INVALID_HANDLE, "mandatory expiry registry differs from authenticated zero-pending timers")

    def _expiry_registry(
        self,
        slot: SlotRuntime,
        timers: Mapping[tuple[int, int], CandidateTimer],
        *,
        layers: Sequence[Layer] | None = None,
        static: StaticResolution | None = None,
        runtime_epoch: int | None = None,
        static_context_generation: int | None = None,
        static_context_incarnation: str | None = None,
        layer_generation: int | None = None,
        layer_incarnation: str | None = None,
    ) -> MandatoryExpiryRegistry:
        return _mandatory_expiry_registry(
            self.runtime_epoch if runtime_epoch is None else runtime_epoch,
            self._runtime_incarnation, self.data_generation, self._data_incarnation,
            slot.slot_index, slot.slot_generation, timers, self._secret,
            layers=slot.layers if layers is None else layers,
            static=slot.static if static is None else static, catalog=self.catalog,
            static_context_generation=slot.static_context_generation if static_context_generation is None else static_context_generation,
            static_context_incarnation=slot.static_context_incarnation if static_context_incarnation is None else static_context_incarnation,
            layer_generation=slot.layer_generation if layer_generation is None else layer_generation,
            layer_incarnation=slot.layer_incarnation if layer_incarnation is None else layer_incarnation,
        )

    def _ensure_applicable_for_apply(self, slot: SlotRuntime, definition: OverrideDefinition) -> None:
        if not definition.applicability.immutable_matches(slot.static.context, slot.static.controller_id):
            raise ModelError(Status.NOT_APPLICABLE, "definition immutable/controller filter does not match")
        if definition.kind is DefinitionKind.STATE_CANDIDATE and _resolve_selector(definition.selector, slot.static, self.catalog) is None:
            raise ModelError(Status.NOT_APPLICABLE, "candidate selector has no bound target")
        if definition.timer is not None and definition.timer.recovery_policy is RecoveryPolicy.REVEAL_UNDERLYING and not slot.static.controller_values.allow_reveal_underlying_recovery:
            raise ModelError(Status.NOT_APPLICABLE, "resolved controller policy does not permit REVEAL_UNDERLYING recovery")
        meta = definition.generated
        if meta.has_tired_origin_kind:
            authored_tired_bound = _unique_role_bound(slot.static, self.catalog, SemanticRole.TIRED)
            rows = [
                row for row in self.catalog.tired_translations
                if row.origin is meta.tired_origin_kind
                and row.destination_controller_id == slot.static.controller_id
                and row.authored_tired_bound is authored_tired_bound
            ]
            if len(rows) != 1 or rows[0].definition_id != definition.stable_id:
                raise ModelError(Status.INVALID_TRANSLATION, "imperative generated Apply/Replace selected the wrong exact translation branch")
        elif meta.has_required_owner_id:
            spec = GENERATED_FAMILY_SPECS["STAMINA"]
            if meta.required_owner_id != spec["owner_id"] or definition.selector is None or definition.selector.kind is not SelectorKind.SEMANTIC or definition.selector.role is not SemanticRole.TIRED:
                raise ModelError(Status.INVALID_GENERATED_WRAPPER, "generated stamina must use its canonical semantic bypass")

    def _apply_stack_delta_impl(self, slot_index: int, expected_slot_generation: int, operations: tuple[DeltaOperation, ...], reason: str) -> DeltaResult:
        slot: SlotRuntime | None = None
        before_generations: Mapping[str, int] = MappingProxyType({})
        before_composition: Composition | None = None
        try:
            if type(expected_slot_generation) is not int or not 1 <= expected_slot_generation <= GEN_MAX or type(reason) is not str:
                raise ModelError(Status.INVALID_HANDLE, "delta generation/reason input has the wrong scalar type")
            StackRuntime._validate_world_integrity(self)
            slot = self._slot(slot_index)
            before_generations = self._generations(slot)
            before_composition = slot.composition
            if not slot.live:
                raise ModelError(Status.INACTIVE_SLOT, "slot is inactive")
            if before_composition is None:
                raise ModelError(Status.INACTIVE_SLOT, "inactive slot has no effective composition")
            if expected_slot_generation != slot.slot_generation:
                raise ModelError(Status.SLOT_GENERATION_MISMATCH, "expected slot generation is stale")
            for operation in operations:
                self._validate_delta_operation_shape(operation)
            scratch_layers = _clone_runtime_layers(slot.layers)
            scratch_timers = _clone_runtime_timers(slot.timers)
            op_results: list[OperationResult] = []
            next_entry, next_timer = slot.next_entry_generation, slot.next_timer_generation
            prospective_epoch = self.runtime_epoch
            prospective_layer_incarnation = slot.layer_incarnation
            epoch_stages: dict[int, EpochSlotStage] = {}
            diagnostic_success = SlotDiagnostics()
            snapshot_layers = tuple(slot.layers)
            snapshot_by_key = {layer.key(): layer for layer in snapshot_layers}
            if not 1 <= next_entry <= GEN_MAX or not 1 <= next_timer <= GEN_MAX:
                raise ModelError(Status.INVALID_STATIC_DATA, "entry/timer generation carrier is outside nonzero u32")
            self._reject_ambiguous_operations(slot, operations, snapshot_layers)
            removals: set[tuple[int, int]] = set()
            additions: dict[tuple[int, int], tuple[DeltaOperation, OverrideDefinition, bool]] = {}
            for operation in sorted(operations, key=lambda item: item.operation_id):
                if operation.kind in {DeltaOpKind.APPLY, DeltaOpKind.REPLACE}:
                    definition = self._validate_operation_definition(operation.definition_id, operation.owner_id, operation.instance_key)
                    self._ensure_applicable_for_apply(slot, definition)
                    if definition.timer is not None and definition.timer.recovery_policy is RecoveryPolicy.LEGACY_RETURN_CALM and operation.owner_id in definition.timer.calm_reset_owner_ids:
                        raise ModelError(Status.INVALID_HANDLE, "LRC candidate owner overlaps its mandatory reset-owner batch")
                    key = (operation.owner_id, operation.instance_key)
                    existing = snapshot_by_key.get(key)
                    if operation.kind is DeltaOpKind.APPLY:
                        if existing is not None:
                            if existing.definition_id != definition.stable_id:
                                raise ModelError(Status.OWNER_KEY_OCCUPIED, "Apply cannot replace an occupied owner key")
                            if existing.generated != definition.generated:
                                raise ModelError(Status.INVALID_GENERATED_WRAPPER, "runtime metadata copy differs from definition")
                            diagnostic_success = _diagnostic_increment(diagnostic_success, "duplicate_apply_count")
                            op_results.append(OperationResult(operation.operation_id, Status.IDEMPOTENT, True, self._make_handle(slot, existing)))
                            continue
                    else:
                        if existing is None:
                            raise ModelError(Status.NOT_FOUND, "Replace requires an occupied owner key")
                        old_definition = self.catalog.definitions[existing.definition_id]
                        if _generated_family(old_definition.generated) != _generated_family(definition.generated):
                            raise ModelError(Status.GENERATED_WRAPPER_FAMILY_MISMATCH, "Replace crosses generated wrapper families")
                        removals.add(key)
                    additions[key] = (operation, definition, existing is not None)
                elif operation.kind in {DeltaOpKind.REMOVE_REQUIRED, DeltaOpKind.REMOVE_IF_PRESENT}:
                    if operation.handle is None:
                        raise ModelError(Status.INVALID_HANDLE, "remove operation has no handle")
                    found = self._find_handle(slot, operation.handle, snapshot_layers)
                    if found is None:
                        if operation.kind is DeltaOpKind.REMOVE_REQUIRED:
                            raise ModelError(Status.STALE_HANDLE, "required handle is stale")
                        diagnostic_success = _diagnostic_increment(diagnostic_success, "stale_handle_count")
                        op_results.append(OperationResult(operation.operation_id, Status.STALE_NOOP, False))
                    else:
                        removals.add(found.key())
                        op_results.append(OperationResult(operation.operation_id, Status.OK, True))
                elif operation.kind is DeltaOpKind.REMOVE_OWNER_IF_PRESENT:
                    _u16(operation.owner_id, "removeOwner.ownerId", nonzero=True)
                    matched = [layer for layer in snapshot_layers if layer.owner_id == operation.owner_id]
                    removals.update(layer.key() for layer in matched)
                    op_results.append(OperationResult(operation.operation_id, Status.OK, bool(matched)))
                elif operation.kind is DeltaOpKind.REMOVE_POLICY:
                    if operation.policy is None:
                        raise ModelError(Status.AMBIGUOUS_DELTA, "policy removal has no policy")
                    matched = [layer for layer in snapshot_layers if self.catalog.definitions[layer.definition_id].map_policy is operation.policy]
                    removals.update(layer.key() for layer in matched)
                    op_results.append(OperationResult(operation.operation_id, Status.OK, bool(matched)))
                elif operation.kind is DeltaOpKind.CLEAR:
                    removals.update(layer.key() for layer in snapshot_layers)
                    op_results.append(OperationResult(operation.operation_id, Status.OK, bool(snapshot_layers)))
            scratch_layers = [layer for layer in scratch_layers if layer.key() not in removals]
            for key in removals:
                scratch_timers.pop(key, None)
            # Prove multiplicity, capacity, selector resolution, modifier folding,
            # and effective normalization before a terminal epoch restart can
            # destructively invalidate the world.
            shape_layers = list(scratch_layers)
            used_shape_generations = {layer.entry_generation for layer in shape_layers}
            shape_generation = 1
            for key, (_operation, definition, _replacing) in sorted(additions.items()):
                while shape_generation in used_shape_generations:
                    shape_generation += 1
                shape_layers.append(Layer(definition.stable_id, key[0], key[1], shape_generation, definition.generated))
                used_shape_generations.add(shape_generation)
                shape_generation += 1
            self._validate_final_multiplicity(shape_layers)
            if len(shape_layers) > MAX_RUNTIME_LAYERS:
                raise ModelError(Status.CAPACITY_EXCEEDED, f"runtime capacity is {MAX_RUNTIME_LAYERS}")
            _compose_impl(self.catalog, slot.static, shape_layers, previous=slot.composition)
            for key, (operation, definition, _replacing) in sorted(additions.items()):
                if next_entry == GEN_MAX or (definition.timer is not None and next_timer == GEN_MAX):
                    if self.runtime_epoch == GEN_MAX:
                        self._commit_terminal_epoch_restart()
                        return DeltaResult(
                            True, Status.RUNTIME_EPOCH_RESTARTED, True, reason, (), before_generations,
                            self._generations(slot), None,
                            ({"phase": "COMMIT", "action": "DESTRUCTIVE_GLOBAL_RUNTIME_EPOCH_INVALIDATION_AND_RESTART", "runtimeEpoch": 1},), None,
                        )
                    prospective_epoch, epoch_stages = self._stage_global_epoch_rekey(target_slot=slot, target_layers=scratch_layers, target_timers=scratch_timers)
                    target_stage = epoch_stages[slot.slot_index]
                    scratch_layers = target_stage.layers
                    scratch_timers = target_stage.timers
                    next_entry = target_stage.next_entry_generation
                    next_timer = target_stage.next_timer_generation
                    prospective_layer_incarnation = target_stage.layer_incarnation
                layer = Layer(definition.stable_id, operation.owner_id, operation.instance_key, next_entry, definition.generated)
                next_entry += 1
                scratch_layers.append(layer)
                if definition.timer is not None:
                    source = slot.static.candidate_timer_sources[definition.stable_id]
                    duration = source.normalized_duration
                    timer = CandidateTimer(
                        operation.owner_id, operation.instance_key, layer.entry_generation, duration,
                        definition.timer.clock, definition.timer.hidden_policy, next_timer, duration == 0,
                        definition.timer.recovery_policy, definition.timer.calm_reset_owner_ids,
                        definition.timer.recovery_transition_id, next_timer,
                        definition.stable_id, duration, source.indefinite,
                        slot.static.hash, stable_hash("timer-source", source), "", source,
                        slot.installed_context_authenticator,
                    )
                    self._sign_timer_allocation(slot, timer, layer_incarnation=prospective_layer_incarnation)
                    scratch_timers[key] = timer
                    next_timer += 1
                else:
                    scratch_timers.pop(key, None)
                op_results.append(OperationResult(operation.operation_id, Status.OK, True, self._make_handle_at_identity(slot, layer, prospective_epoch, prospective_layer_incarnation)))
            self._validate_final_multiplicity(scratch_layers)
            if len(scratch_layers) > MAX_RUNTIME_LAYERS:
                raise ModelError(Status.CAPACITY_EXCEEDED, f"runtime capacity is {MAX_RUNTIME_LAYERS}")
            prospective = _compose_impl(self.catalog, slot.static, scratch_layers, previous=slot.composition)
            hide_expiries = _mark_expire_on_hide(scratch_timers, prospective, slot.presentation_gate)
            if prospective_epoch != self.runtime_epoch:
                refreshed_results: list[OperationResult] = []
                by_key = {layer.key(): layer for layer in scratch_layers}
                for result in op_results:
                    if result.handle is not None:
                        refreshed_results.append(dataclasses.replace(result, handle=self._make_handle_at_identity(slot, by_key[(result.handle.owner_id, result.handle.instance_key)], prospective_epoch, prospective_layer_incarnation)))
                    else:
                        refreshed_results.append(result)
                op_results = refreshed_results
            layer_set_changed = scratch_layers != slot.layers or _timer_identity_set(scratch_timers) != _timer_identity_set(slot.timers)
            if not layer_set_changed:
                replacement = dataclasses.replace(slot, diagnostics=_merge_diagnostics(slot.diagnostics, diagnostic_success))
                self._commit_slot_replacements({slot.slot_index: replacement})
                return DeltaResult(True, Status.IDEMPOTENT, False, reason, tuple(sorted(op_results, key=lambda result: result.operation_id)), before_generations, self._generations(slot), slot.composition, (), None)
            old_winner = slot.composition.winner
            new_layer_generation, layer_wrapped = _advance_cache_generation(slot.layer_generation)
            new_layer_incarnation = (
                prospective_layer_incarnation
                if layer_wrapped and prospective_layer_incarnation != slot.layer_incarnation
                else self._rotate_layer_incarnation(slot)
                if layer_wrapped
                else prospective_layer_incarnation
            )
            new_layer_incarnation_authenticator = self._layer_incarnation_authenticator(
                slot, runtime_epoch=prospective_epoch, layer_generation=new_layer_generation,
                layer_incarnation=new_layer_incarnation,
            )
            if layer_wrapped:
                for timer in scratch_timers.values():
                    self._sign_timer_allocation(slot, timer, layer_incarnation=new_layer_incarnation)
                refreshed_results = []
                by_key = {layer.key(): layer for layer in scratch_layers}
                for result in op_results:
                    if result.handle is not None:
                        refreshed_results.append(dataclasses.replace(
                            result,
                            handle=self._make_handle_at_identity(
                                slot,
                                by_key[(result.handle.owner_id, result.handle.instance_key)],
                                prospective_epoch,
                                new_layer_incarnation,
                            ),
                        ))
                    else:
                        refreshed_results.append(result)
                op_results = refreshed_results
            effective_changed = prospective.effective_hash != slot.composition.effective_hash
            new_effective_generation, effective_wrapped = _advance_cache_generation(slot.effective_generation) if effective_changed else (slot.effective_generation, False)
            wrap_plans: list[Mapping[str, Any]] = []
            wrap_plans.extend({"phase": "PRECOMMIT", "action": "QUEUE_EXPIRE_ON_HIDE", **item} for item in hide_expiries)
            if layer_wrapped:
                wrap_plans.append({"phase": "PRECOMMIT", "action": "INVALIDATE_ACTIVE_STACK_PROVENANCE_AND_COMPOSITION_CACHES_FOR_WRAP"})
            if effective_wrapped:
                wrap_plans.append({"phase": "PRECOMMIT", "action": "INVALIDATE_EFFECTIVE_CAPABILITY_COMMAND_ORIGIN_CACHES_FOR_WRAP"})
            staged_allocations = _timer_allocation_registry(scratch_timers)
            staged_expiry = self._expiry_registry(
                slot, scratch_timers, layers=scratch_layers, runtime_epoch=prospective_epoch,
                layer_generation=new_layer_generation, layer_incarnation=new_layer_incarnation,
            )
            staged_context_registry = self._expected_retained_context_authenticators(slot, scratch_timers)
            staged_diagnostics = _merge_diagnostics(slot.diagnostics, diagnostic_success)
            staged_history = deque(slot.transition_history, maxlen=16)
            staged_history.append(self._history_entry(slot, {"reason": reason, "oldWinner": to_data(old_winner), "newWinner": to_data(prospective.winner)}, runtime_epoch=prospective_epoch, layer_generation=new_layer_generation, layer_incarnation=new_layer_incarnation, effective_generation=new_effective_generation))
            target_replacement = SlotRuntime(
                slot_index=slot.slot_index, static=slot.static, layers=scratch_layers, timers=scratch_timers,
                slot_generation=slot.slot_generation, static_context_generation=slot.static_context_generation,
                static_context_incarnation=slot.static_context_incarnation,
                layer_generation=new_layer_generation, layer_incarnation=new_layer_incarnation,
                layer_incarnation_authenticator=new_layer_incarnation_authenticator,
                effective_generation=new_effective_generation,
                next_entry_generation=next_entry, next_timer_generation=next_timer,
                composition=dataclasses.replace(prospective, plans=()), timer_allocations=staged_allocations,
                mandatory_expiry_registry=staged_expiry,
                captured_spawn_policy_id=slot.captured_spawn_policy_id,
                captured_population_policy_id=slot.captured_population_policy_id,
                captured_spawn_policy_values=slot.captured_spawn_policy_values,
                captured_population_policy_values=slot.captured_population_policy_values,
                captured_policy_authenticator=slot.captured_policy_authenticator,
                installed_context_authenticator=slot.installed_context_authenticator,
                retained_context_authenticators=staged_context_registry,
                live=True, presentation_gate=slot.presentation_gate, diagnostics=staged_diagnostics,
                transition_history=staged_history,
            )
            epoch_replacements = self._build_epoch_replacements(epoch_stages, prospective_epoch, skip_slot=slot.slot_index)
            replacements = dict(epoch_replacements)
            replacements[slot.slot_index] = target_replacement
            staged_commit = self._stage_slot_replacements(replacements, runtime_epoch=prospective_epoch)
            # Point of no return: epoch/world publication contains assignments only.
            self._publish_slot_replacements(staged_commit, runtime_epoch=prospective_epoch)
            return DeltaResult(True, Status.OK, True, reason, tuple(sorted(op_results, key=lambda result: result.operation_id)), before_generations, self._generations(slot), prospective, _merge_plans_monotonic(wrap_plans, prospective.plans), None)
        except ModelError as exc:
            return DeltaResult(False, exc.status, False, reason, (), before_generations, before_generations, before_composition, (), exc.message)

    def apply_stack_delta(self, slot_index: int, expected_slot_generation: int, operations: Sequence[DeltaOperation], reason: str) -> DeltaResult:
        """Exception-contained public atomic delta boundary."""

        rejected = _nonexact_runtime_delta_failure(self, reason)
        if rejected is not None:
            return rejected
        try:
            StackRuntime._validate_world_integrity(self)
            if type(operations) not in (list, tuple):
                raise ModelError(Status.INVALID_HANDLE, "delta operations must be an exact built-in list or tuple")
            operation_snapshot = tuple(operations)
            return StackRuntime._apply_stack_delta_impl(self, slot_index, expected_slot_generation, operation_snapshot, reason)
        except Exception as exc:
            return _contained_runtime_delta_failure(self, slot_index, reason, exc)

    def _generations(self, slot: SlotRuntime) -> dict[str, int]:
        return {"runtimeEpoch": self.runtime_epoch, **slot.generations()}

    def bind_delta_operation(self, operation: DeltaOperation) -> DeltaOperation:
        _require_exact_stack_runtime(self)
        StackRuntime._validate_world_integrity(self)
        if type(operation) is not DeltaOperation:
            raise ModelError(Status.INVALID_HANDLE, "only a typed DeltaOperation can be queued")
        if operation.kind in {DeltaOpKind.REMOVE_REQUIRED, DeltaOpKind.REMOVE_IF_PRESENT}:
            return operation
        return dataclasses.replace(
            operation, runtime_incarnation=self._runtime_incarnation,
            data_generation=self.data_generation, data_incarnation=self._data_incarnation,
        )

    def _validate_delta_operation_shape(self, operation: Any) -> None:
        if type(operation) is not DeltaOperation or type(operation.operation_id) is not str or not operation.operation_id or type(operation.kind) is not DeltaOpKind:
            raise ModelError(Status.INVALID_HANDLE, "delta operation/discriminant is not canonical typed data")
        if any(type(value) is not int for value in (operation.definition_id, operation.owner_id, operation.instance_key)):
            raise ModelError(Status.INVALID_HANDLE, "delta operation IDs must be integral scalars")
        if operation.handle is not None and type(operation.handle) is not Handle:
            raise ModelError(Status.INVALID_HANDLE, "delta handle payload is not a typed Handle")
        if operation.policy is not None and type(operation.policy) is not LifetimePolicy:
            raise ModelError(Status.INVALID_HANDLE, "delta policy payload is not a typed LifetimePolicy")
        is_handle_operation = operation.kind in {DeltaOpKind.REMOVE_REQUIRED, DeltaOpKind.REMOVE_IF_PRESENT}
        if is_handle_operation:
            if operation.runtime_incarnation or operation.data_generation or operation.data_incarnation:
                raise ModelError(Status.INVALID_HANDLE, "handle delta must not carry a second request identity")
        elif type(operation.runtime_incarnation) is not str or type(operation.data_generation) is not int or type(operation.data_incarnation) is not str or operation.runtime_incarnation != self._runtime_incarnation or operation.data_generation != self.data_generation or operation.data_incarnation != self._data_incarnation:
            raise ModelError(Status.INVALID_HANDLE, "queued delta behavior-data/runtime incarnation is stale")
        if operation.kind in {DeltaOpKind.APPLY, DeltaOpKind.REPLACE}:
            if operation.handle is not None or operation.policy is not None:
                raise ModelError(Status.INVALID_HANDLE, "Apply/Replace carries another operation's payload")
        elif operation.kind in {DeltaOpKind.REMOVE_REQUIRED, DeltaOpKind.REMOVE_IF_PRESENT}:
            if operation.handle is None or operation.definition_id or operation.owner_id or operation.instance_key or operation.policy is not None:
                raise ModelError(Status.INVALID_HANDLE, "handle removal payload is noncanonical")
        elif operation.kind is DeltaOpKind.REMOVE_OWNER_IF_PRESENT:
            if operation.definition_id or operation.instance_key or operation.handle is not None or operation.policy is not None:
                raise ModelError(Status.INVALID_HANDLE, "owner removal payload is noncanonical")
        elif operation.kind is DeltaOpKind.REMOVE_POLICY:
            if operation.definition_id or operation.owner_id or operation.instance_key or operation.handle is not None or operation.policy is None:
                raise ModelError(Status.INVALID_HANDLE, "policy removal payload is noncanonical")
        elif operation.kind is DeltaOpKind.CLEAR:
            if operation.definition_id or operation.owner_id or operation.instance_key or operation.handle is not None or operation.policy is not None:
                raise ModelError(Status.INVALID_HANDLE, "CLEAR payload is noncanonical")

    def _reject_ambiguous_operations(self, slot: SlotRuntime, operations: Sequence[DeltaOperation], snapshot_layers: Sequence[Layer]) -> None:
        operation_ids = [operation.operation_id for operation in operations]
        if any(not operation_id for operation_id in operation_ids) or len(operation_ids) != len(set(operation_ids)):
            raise ModelError(Status.AMBIGUOUS_DELTA, "operation IDs must be nonempty and unique")
        addressed: set[tuple[int, int]] = set()
        semantic_broad: set[tuple[str, Any]] = set()
        for operation in sorted(operations, key=lambda item: item.operation_id):
            current: set[tuple[int, int]] = set()
            if operation.kind in {DeltaOpKind.APPLY, DeltaOpKind.REPLACE}:
                current = {(operation.owner_id, operation.instance_key)}
            elif operation.kind in {DeltaOpKind.REMOVE_REQUIRED, DeltaOpKind.REMOVE_IF_PRESENT} and operation.handle is not None:
                self._validate_handle_shape(slot, operation.handle)
                current = {(operation.handle.owner_id, operation.handle.instance_key)}
            elif operation.kind is DeltaOpKind.REMOVE_OWNER_IF_PRESENT:
                marker = ("owner", operation.owner_id)
                if marker in semantic_broad:
                    raise ModelError(Status.AMBIGUOUS_DELTA, f"owner {operation.owner_id} is addressed more than once")
                semantic_broad.add(marker)
                current = {layer.key() for layer in snapshot_layers if layer.owner_id == operation.owner_id}
            elif operation.kind is DeltaOpKind.REMOVE_POLICY:
                if operation.policy is None:
                    raise ModelError(Status.AMBIGUOUS_DELTA, "policy removal has no policy")
                marker = ("policy", operation.policy.value)
                if marker in semantic_broad:
                    raise ModelError(Status.AMBIGUOUS_DELTA, f"policy {operation.policy.value} is addressed more than once")
                semantic_broad.add(marker)
                current = {layer.key() for layer in snapshot_layers if self.catalog.definitions[layer.definition_id].map_policy is operation.policy}
            elif operation.kind is DeltaOpKind.CLEAR:
                if len(operations) != 1:
                    raise ModelError(Status.AMBIGUOUS_DELTA, "CLEAR cannot be combined with another operation")
                current = {layer.key() for layer in snapshot_layers}
            overlap = addressed.intersection(current)
            if overlap:
                raise ModelError(Status.AMBIGUOUS_DELTA, f"multiple operations address {sorted(overlap)}")
            addressed.update(current)

    def _validate_final_multiplicity(self, layers: Sequence[Layer]) -> None:
        by_definition: dict[int, list[Layer]] = {}
        for layer in layers:
            by_definition.setdefault(layer.definition_id, []).append(layer)
        for definition_id, entries in by_definition.items():
            definition = self.catalog.definitions[definition_id]
            owners = {entry.owner_id for entry in entries}
            if not definition.allow_multiple_owners and len(owners) > 1:
                raise ModelError(Status.DEFINITION_OWNED, f"definition {definition_id} is held by another owner")
            if not definition.allow_multiple_instances_per_owner:
                if any(entry.instance_key != 0 for entry in entries) or len(entries) != len(owners):
                    raise ModelError(Status.INSTANCE_KEY_NOT_ALLOWED, f"definition {definition_id} disallows per-owner instances")

    def apply(self, slot_index: int, definition_id: int, owner_id: int, instance_key: int = 0, *, reason: str = "Apply") -> DeltaResult:
        rejected = _nonexact_runtime_delta_failure(self, reason)
        if rejected is not None:
            return rejected
        try:
            StackRuntime._validate_world_integrity(self)
            slot = self._slot(slot_index)
            operation = self.bind_delta_operation(DeltaOperation.apply("apply", definition_id, owner_id, instance_key))
            return self.apply_stack_delta(slot_index, slot.slot_generation, (operation,), reason)
        except Exception as exc:
            return _contained_runtime_delta_failure(self, slot_index, reason, exc)

    def replace(self, slot_index: int, owner_id: int, instance_key: int, definition_id: int, *, reason: str = "Replace") -> DeltaResult:
        rejected = _nonexact_runtime_delta_failure(self, reason)
        if rejected is not None:
            return rejected
        try:
            StackRuntime._validate_world_integrity(self)
            slot = self._slot(slot_index)
            operation = self.bind_delta_operation(DeltaOperation.replace("replace", definition_id, owner_id, instance_key))
            return self.apply_stack_delta(slot_index, slot.slot_generation, (operation,), reason)
        except Exception as exc:
            return _contained_runtime_delta_failure(self, slot_index, reason, exc)

    def remove(self, slot_index: int, handle: Handle, *, reason: str = "Remove") -> DeltaResult:
        rejected = _nonexact_runtime_delta_failure(self, reason)
        if rejected is not None:
            return rejected
        try:
            StackRuntime._validate_world_integrity(self)
            slot = self._slot(slot_index)
            result = self.apply_stack_delta(slot_index, slot.slot_generation, (DeltaOperation.remove_if_present("remove", handle),), reason)
        except Exception as exc:
            return _contained_runtime_delta_failure(self, slot_index, reason, exc)
        if result.ok and not result.mutated and result.operation_results and result.operation_results[0].status is Status.STALE_NOOP:
            return dataclasses.replace(result, status=Status.STALE_NOOP)
        return result

    def remove_owner(self, slot_index: int, owner_id: int, *, reason: str = "RemoveOwner") -> DeltaResult:
        rejected = _nonexact_runtime_delta_failure(self, reason)
        if rejected is not None:
            return rejected
        try:
            StackRuntime._validate_world_integrity(self)
            slot = self._slot(slot_index)
            operation = self.bind_delta_operation(DeltaOperation.remove_owner_if_present("removeOwner", owner_id))
            return self.apply_stack_delta(slot_index, slot.slot_generation, (operation,), reason)
        except Exception as exc:
            return _contained_runtime_delta_failure(self, slot_index, reason, exc)

    def clear(self, slot_index: int, *, reason: str = "ClearAllForSlot") -> DeltaResult:
        rejected = _nonexact_runtime_delta_failure(self, reason)
        if rejected is not None:
            return rejected
        try:
            StackRuntime._validate_world_integrity(self)
            slot = self._slot(slot_index)
            operation = self.bind_delta_operation(DeltaOperation("clear", DeltaOpKind.CLEAR))
            return self.apply_stack_delta(slot_index, slot.slot_generation, (operation,), reason)
        except Exception as exc:
            return _contained_runtime_delta_failure(self, slot_index, reason, exc)

    def _convenience_failure(self, slot_index: Any, reason: Any, exc: Exception) -> DeltaResult:
        status = exc.status if isinstance(exc, ModelError) else Status.INVALID_COMPOSITION
        slot = self.slots.get(slot_index) if type(self.slots) is dict and type(slot_index) is int else None
        before = self._generations(slot) if type(slot) is SlotRuntime else {}
        effective = slot.composition if type(slot) is SlotRuntime and type(slot.composition) is Composition else None
        return DeltaResult(False, status, False, reason if type(reason) is str else "InvalidConvenienceInput", (), before, before, effective, (), "convenience delta rejected")

    def _queue_expire_on_hide(self, slot: SlotRuntime) -> None:
        if slot.composition is not None:
            scratch_timers = _clone_runtime_timers(slot.timers)
            _mark_expire_on_hide(scratch_timers, slot.composition, slot.presentation_gate)
            staged_registry = self._expiry_registry(slot, scratch_timers)
            replacement = dataclasses.replace(slot, timers=scratch_timers, mandatory_expiry_registry=staged_registry)
            self._commit_slot_replacements({slot.slot_index: replacement})

    def tick_candidate_timers(self, slot_index: int, ticks: int = 1, *, clock: TimerClock = TimerClock.FRAME, presentation_gate: bool | None = None) -> Mapping[str, Any]:
        _require_exact_stack_runtime(self)
        try:
            StackRuntime._validate_world_integrity(self)
            slot = self._slot(slot_index)
            if not slot.live or slot.composition is None:
                raise ModelError(Status.INACTIVE_SLOT, "cannot tick an inactive slot")
            if type(ticks) is not int or ticks < 0 or type(clock) is not TimerClock:
                raise ModelError(Status.INVALID_HANDLE, "ticks/clock must be canonical typed values")
            if presentation_gate is not None and type(presentation_gate) is not bool:
                raise ModelError(Status.INVALID_HANDLE, "presentation gate override must be an actual boolean")
            if presentation_gate is not None and presentation_gate != slot.presentation_gate:
                raise ModelError(Status.INVALID_HANDLE, "presentation gate is authoritative slot state and cannot be overridden")
            gate = slot.presentation_gate
            before_generations = self._generations(slot)
            scratch_timers = _clone_runtime_timers(slot.timers)
            changes: list[dict[str, Any]] = []
            if not gate:
                winner_key = (slot.composition.winner.owner_id, slot.composition.winner.instance_key) if slot.composition.winner.kind == "LAYER" else None
                for key, timer in sorted(scratch_timers.items()):
                    if timer.clock is not clock or timer.zero_pending or timer.remaining_ticks == 255:
                        continue
                    eligible = timer.hidden_policy is HiddenPolicy.CONTINUE_WHILE_HIDDEN or key == winner_key
                    if timer.hidden_policy is HiddenPolicy.EXPIRE_ON_HIDE and key != winner_key:
                        before = timer.remaining_ticks
                        timer.remaining_ticks, timer.zero_pending = 0, True
                        changes.append({"key": key, "before": before, "after": 0, "zeroPending": True})
                    elif eligible:
                        before = timer.remaining_ticks
                        timer.remaining_ticks = max(0, before - ticks)
                        timer.zero_pending = timer.remaining_ticks == 0
                        if before != timer.remaining_ticks:
                            changes.append({"key": key, "before": before, "after": timer.remaining_ticks, "zeroPending": timer.zero_pending})
            staged_registry = self._expiry_registry(slot, scratch_timers)
            output = {"presentationGate": gate, "changes": changes, "mandatoryExpiry": [to_data(plan) for _key, plan in staged_registry.items()], "generationsBefore": before_generations, "generationsAfter": self._generations(slot)}
            replacement = dataclasses.replace(slot, timers=scratch_timers, mandatory_expiry_registry=staged_registry)
            self._commit_slot_replacements({slot.slot_index: replacement})
            return _deep_freeze(output)
        except ModelError:
            raise
        except Exception:
            raise ModelError(Status.INVALID_COMPOSITION, "timer tick boundary rejected hostile runtime data") from None

    def set_presentation_gate(self, slot_index: int, active: bool) -> Mapping[str, Any]:
        _require_exact_stack_runtime(self)
        try:
            StackRuntime._validate_world_integrity(self)
            slot = self._slot(slot_index)
            if not slot.live or slot.composition is None:
                raise ModelError(Status.INACTIVE_SLOT, "cannot gate an inactive slot")
            if type(active) is not bool:
                raise ModelError(Status.INVALID_HANDLE, "presentation gate must be boolean")
            before = slot.presentation_gate
            scratch_timers = _clone_runtime_timers(slot.timers)
            expired: list[Mapping[str, Any]] = []
            if before and not active:
                expired = _mark_expire_on_hide(scratch_timers, slot.composition, False)
            staged_registry = self._expiry_registry(slot, scratch_timers)
            output = {"before": before, "after": active, "expireOnHide": expired, "mandatoryExpiry": [to_data(plan) for _key, plan in staged_registry.items()], "generations": self._generations(slot)}
            replacement = dataclasses.replace(slot, presentation_gate=active, timers=scratch_timers, mandatory_expiry_registry=staged_registry)
            self._commit_slot_replacements({slot.slot_index: replacement})
            return _deep_freeze(output)
        except ModelError:
            raise
        except Exception:
            raise ModelError(Status.INVALID_COMPOSITION, "presentation gate boundary rejected hostile runtime data") from None

    def pending_expiry_plans(self, slot_index: int) -> list[Mapping[str, Any]]:
        _require_exact_stack_runtime(self)
        StackRuntime._validate_world_integrity(self)
        slot = self._slot(slot_index)
        if not slot.live or slot.static is None:
            return []
        self._validate_runtime_timer_registry(slot, {layer.key(): layer for layer in slot.layers}, slot.static)
        return [to_data(plan) for _key, plan in sorted(slot.mandatory_expiry_registry.items())]

    def commit_expiry(self, plan: ExpiryPlan | Mapping[str, Any]) -> DeltaResult:
        rejected = _nonexact_runtime_delta_failure(self, "MandatoryExpiryInvalidRuntime")
        if rejected is not None:
            return rejected
        try:
            StackRuntime._validate_world_integrity(self)
            if type(plan) is ExpiryPlan:
                plan = ExpiryPlan.from_dict(to_data(plan))
            else:
                if type(plan) is not dict:
                    raise ModelError(Status.INVALID_HANDLE, "expiry plan must be a typed plan or mapping")
                plan = ExpiryPlan.from_dict(plan)
            slot = self._slot(plan.slot_index)
            before = self._generations(slot)
            expected_plan_tag = _expiry_plan_authenticator(self._secret, _expiry_plan_fields(plan))
            if not hmac.compare_digest(plan.authenticator, expected_plan_tag):
                return DeltaResult(True, Status.STALE_NOOP, False, "MandatoryExpiryStaleAuthentication", (), before, before, slot.composition, (), None)
        except Exception as exc:
            status = exc.status if isinstance(exc, ModelError) else Status.INVALID_HANDLE
            return DeltaResult(False, status, False, "MandatoryExpiryInvalidInput", (), {}, {}, None, (), "mandatory expiry input rejected")
        if not slot.live or slot.composition is None:
            return DeltaResult(True, Status.STALE_NOOP, False, "MandatoryExpiryStale", (), before, before, slot.composition, (), None)
        try:
            if slot.static is None:
                raise ModelError(Status.INVALID_STATIC_DATA, "live expiry slot lacks static resolution")
            StackRuntime._validate_world_integrity(self)
            timer = slot.timers.get((plan.owner_id, plan.instance_key))
            layer = next((item for item in slot.layers if item.key() == (plan.owner_id, plan.instance_key)), None)
            registered_plan = slot.mandatory_expiry_registry.get((plan.owner_id, plan.instance_key))
            definition = self.catalog.definitions.get(layer.definition_id) if layer is not None else None
            node = _resolve_selector(definition.selector, slot.static, self.catalog) if definition is not None and definition.selector is not None else None
            profile_id = slot.static.node_bindings.get(node.stable_id) if node is not None else None
            authenticated = (
                plan.runtime_epoch == self.runtime_epoch and plan.runtime_incarnation == self._runtime_incarnation
                and plan.data_generation == self.data_generation and plan.data_incarnation == self._data_incarnation
                and plan.slot_index == slot.slot_index
                and plan.slot_generation == slot.slot_generation and timer is not None and layer is not None
                and timer.zero_pending and timer.entry_generation == plan.entry_generation
                and timer.timer_generation == plan.timer_generation and timer.expiry_plan_generation == plan.expiry_plan_generation
                and timer.recovery_transition_id == plan.recovery_transition_id
                and timer.recovery_policy is plan.recovery_policy
                and plan.recovery_action == _recovery_action(timer.recovery_policy)
                and tuple(timer.calm_reset_owner_ids) == tuple(plan.calm_reset_owner_ids)
                and layer.entry_generation == plan.entry_generation
                and plan.static_context_generation == slot.static_context_generation
                and plan.static_context_incarnation == slot.static_context_incarnation
                and plan.layer_generation == slot.layer_generation
                and plan.layer_incarnation == slot.layer_incarnation
                and plan.definition_id == layer.definition_id
                and plan.armed_definition_id == timer.armed_definition_id
                and plan.armed_static_hash == timer.armed_static_hash and plan.armed_source_hash == timer.armed_source_hash
                and node is not None and profile_id is not None
                and plan.controller_id == slot.static.controller_id and plan.node_id == node.stable_id and plan.profile_id == profile_id and plan.resolved_role is node.role
                and plan.selector_binding_hash == stable_hash("selector-binding", definition.selector)
                and plan.generated_binding_hash == stable_hash("generated-binding", definition.generated)
                and tuple(plan.removal_targets) == _expiry_removal_targets(timer, layer, slot.layers, self.catalog)
                and type(registered_plan) is ExpiryPlan
                and canonical_json_bytes(registered_plan) == canonical_json_bytes(plan)
            )
            expiring_definition = self._validate_runtime_layer(layer) if layer is not None else None
        except Exception as exc:
            status = exc.status if isinstance(exc, ModelError) else Status.INVALID_COMPOSITION
            message = exc.message if isinstance(exc, ModelError) else "canonical expiry preflight rejected hostile runtime data"
            return DeltaResult(False, status, False, "MandatoryExpiryInvalidRuntime", (), before, before, slot.composition, (), message)
        if not authenticated:
            return DeltaResult(True, Status.STALE_NOOP, False, "MandatoryExpiryStale", (), before, before, slot.composition, (), None)
        assert timer is not None and layer is not None and expiring_definition is not None
        live_by_key = {candidate.key(): candidate for candidate in slot.layers}
        operations: list[DeltaOperation] = []
        for target in plan.removal_targets:
            candidate = live_by_key.get((target.owner_id, target.instance_key))
            if candidate is None or candidate.entry_generation != target.entry_generation or candidate.definition_id != target.definition_id:
                return DeltaResult(True, Status.STALE_NOOP, False, "MandatoryExpiryStaleRemovalSnapshot", (), before, before, slot.composition, (), None)
            operations.append(DeltaOperation.remove_required(
                f"expiry.{target.reason}.{target.owner_id}.{target.instance_key}",
                self._make_handle(slot, candidate),
            ))
        result = self.apply_stack_delta(slot.slot_index, slot.slot_generation, operations, "CandidateTimerExpiry")
        tired_exit = plan.resolved_role is SemanticRole.TIRED or expiring_definition.generated.has_required_owner_id or expiring_definition.generated.has_tired_origin_kind or timer.recovery_policy is RecoveryPolicy.LEGACY_RETURN_CALM
        if result.ok and result.mutated and tired_exit:
            route_family = expiring_definition.generated.tired_origin_kind.name if expiring_definition.generated.tired_origin_kind else ("STAMINA" if expiring_definition.generated.has_required_owner_id else "AUTHORED_LEGACY")
            recovery_identity = {
                "routeFamily": route_family,
                "definitionId": expiring_definition.stable_id,
                "recoveryPolicy": timer.recovery_policy.value,
                "recoveryTransitionId": timer.recovery_transition_id,
            }
            extra = (
                {"phase": "STABILIZE", "action": "RESET_TIRED_RAM_CHAIN_COUNTERS_AND_PRESENTATION", **recovery_identity},
                {"phase": "POSTCOMMIT", "action": "APPLY_POST_TIRED_MOVEMENT_COOLDOWN", "frames": 24, **recovery_identity},
            )
            return dataclasses.replace(result, plans=_merge_plans_monotonic(result.plans, extra))
        return result

    def _revalidate_retained_context_impl(self, slot_index: int, new_context: StaticContext, *, reason: str = "RetainedContextRevalidation") -> DeltaResult:
        """Atomically re-resolve static data and preserve only logical entries.

        This is the authenticated internal exception that may translate one
        imperative tired wrapper to the same origin/owner family while keeping
        its entry and timer identity.
        """

        slot = self._slot(slot_index)
        before_generations = self._generations(slot)
        before = slot.composition
        if not slot.live or before is None:
            return DeltaResult(False, Status.INACTIVE_SLOT, False, reason, (), before_generations, before_generations, before, (), "retained revalidation requires a live slot")
        try:
            StackRuntime._validate_world_integrity(self)
            if new_context.data_generation != self.data_generation or new_context.data_incarnation != self._data_incarnation:
                raise ModelError(Status.INVALID_STATIC_DATA, "retained context behavior-data generation is stale")
            if slot.static is None:
                raise ModelError(Status.INVALID_STATIC_DATA, "live retained slot lacks static resolution")
            live_by_key = {layer.key(): layer for layer in slot.layers}
            for layer in slot.layers:
                self._validate_runtime_layer(layer)
            self._validate_runtime_timer_registry(slot, live_by_key, slot.static)
            if new_context == slot.static.context:
                return DeltaResult(True, Status.IDEMPOTENT, False, reason, (), before_generations, before_generations, before, (), None)
            new_static = _resolve_static_impl(self.catalog, new_context)
            scratch_layers: list[Layer] = []
            scratch_timers = _clone_runtime_timers(slot.timers)
            plans: list[Mapping[str, Any]] = [
                {"phase": "STABILIZE", "action": "DISCARD_CONTEXT_BOUND_COMMAND_AND_PRESENTATION_HANDLES"}
            ]
            removed: list[tuple[int, int]] = []
            translated: list[dict[str, Any]] = []
            for layer in slot.layers:
                definition = self.catalog.definitions[layer.definition_id]
                if definition.map_policy is LifetimePolicy.CLEAR:
                    removed.append(layer.key())
                    continue
                if definition.map_policy is LifetimePolicy.SYSTEM:
                    removed.append(layer.key())
                    plans.append({"phase": "POSTCOMMIT", "action": "REQUEST_SYSTEM_LAYER_REEVALUATION", "ownerId": layer.owner_id, "oldDefinitionId": layer.definition_id})
                    continue
                target_definition = definition
                if definition.kind is DefinitionKind.STATE_CANDIDATE and definition.generated.has_tired_origin_kind:
                    authored_tired_bound = _unique_role_bound(new_static, self.catalog, SemanticRole.TIRED)
                    target_definition = self._translation_target(definition, new_static.controller_id, authored_tired_bound)
                    if target_definition.generated != layer.generated:
                        raise ModelError(Status.INVALID_GENERATED_WRAPPER, "retained translation target metadata differs from runtime layer")
                    translated.append({"ownerId": layer.owner_id, "fromDefinitionId": definition.stable_id, "toDefinitionId": target_definition.stable_id, "origin": definition.generated.tired_origin_kind.name})
                if not target_definition.applicability.immutable_matches(new_context, new_static.controller_id):
                    removed.append(layer.key())
                    continue
                if target_definition.kind is DefinitionKind.STATE_CANDIDATE:
                    node = _resolve_selector(target_definition.selector, new_static, self.catalog)
                    if node is None:
                        if definition.generated.has_tired_origin_kind:
                            raise ModelError(Status.INVALID_TRANSLATION, "imperative tired translation resolved to an unbound fallback")
                        removed.append(layer.key())
                        continue
                scratch_layers.append(dataclasses.replace(layer, definition_id=target_definition.stable_id))
            for key in removed:
                scratch_timers.pop(key, None)
            translated_by_key = {layer.key(): layer for layer in scratch_layers}
            for key, timer in scratch_timers.items():
                self._validate_runtime_timer(slot, timer, translated_by_key, new_static, slot.timer_allocations.get(key), slot.next_timer_generation)
            prospective = _compose_impl(self.catalog, new_static, scratch_layers, previous=slot.composition)
            hide_expiries = _mark_expire_on_hide(scratch_timers, prospective, slot.presentation_gate)
            layers_changed = scratch_layers != slot.layers or _timer_identity_set(scratch_timers) != _timer_identity_set(slot.timers)
            new_static_generation, static_wrapped = _advance_cache_generation(slot.static_context_generation)
            new_layer_generation, layer_wrapped = _advance_cache_generation(slot.layer_generation) if layers_changed else (slot.layer_generation, False)
            new_layer_incarnation = self._rotate_layer_incarnation(slot) if layer_wrapped else slot.layer_incarnation
            new_layer_incarnation_authenticator = self._layer_incarnation_authenticator(
                slot, layer_generation=new_layer_generation, layer_incarnation=new_layer_incarnation,
            )
            effective_changed = prospective.effective_hash != slot.composition.effective_hash
            new_effective_generation, effective_wrapped = _advance_cache_generation(slot.effective_generation) if effective_changed else (slot.effective_generation, False)
            new_context_incarnation = self._rotate_static_context_incarnation(slot) if static_wrapped else slot.static_context_incarnation
            new_context_authenticator = self._installed_context_authenticator(
                slot, static=new_static, static_context_generation=new_static_generation,
                static_context_incarnation=new_context_incarnation,
            )
            if static_wrapped or layer_wrapped:
                for timer in scratch_timers.values():
                    self._sign_timer_allocation(
                        slot, timer, static_context_incarnation=new_context_incarnation,
                        layer_incarnation=new_layer_incarnation,
                    )
            new_retained_context_authenticators = self._expected_retained_context_authenticators(
                slot, scratch_timers, installed_context_authenticator=new_context_authenticator,
            )
            if static_wrapped:
                plans.append({"phase": "PRECOMMIT", "action": "INVALIDATE_STATIC_ASSIGNMENT_BINDING_MODIFIER_DESTINATION_CACHES_FOR_WRAP"})
            if layer_wrapped:
                plans.append({"phase": "PRECOMMIT", "action": "INVALIDATE_ACTIVE_STACK_PROVENANCE_AND_COMPOSITION_CACHES_FOR_WRAP"})
            if effective_wrapped:
                plans.append({"phase": "PRECOMMIT", "action": "INVALIDATE_EFFECTIVE_CAPABILITY_COMMAND_ORIGIN_CACHES_FOR_WRAP"})
            plans.extend({"phase": "PRECOMMIT", "action": "QUEUE_EXPIRE_ON_HIDE", **item} for item in hide_expiries)
            plans.append({"phase": "DIAGNOSTIC", "action": "RECORD_DESTINATION_POLICY_SELECTION", "wouldSelectSpawnPolicyId": new_static.spawn_policy_id, "wouldSelectPopulationPolicyId": new_static.population_policy_id, "capturedSpawnPolicyId": slot.captured_spawn_policy_id, "capturedPopulationPolicyId": slot.captured_population_policy_id})
            staged_composition = dataclasses.replace(prospective, plans=())
            staged_allocations = _timer_allocation_registry(scratch_timers)
            staged_expiry = self._expiry_registry(
                slot, scratch_timers, layers=scratch_layers, static=new_static,
                static_context_generation=new_static_generation,
                static_context_incarnation=new_context_incarnation,
                layer_generation=new_layer_generation,
                layer_incarnation=new_layer_incarnation,
            )
            staged_diagnostics = _diagnostic_increment(slot.diagnostics, "context_no_longer_applicable_count", len(removed))
            replacement = dataclasses.replace(
                slot,
                static=new_static,
                static_context_generation=new_static_generation,
                static_context_incarnation=new_context_incarnation,
                installed_context_authenticator=new_context_authenticator,
                retained_context_authenticators=new_retained_context_authenticators,
                layer_generation=new_layer_generation,
                layer_incarnation=new_layer_incarnation,
                layer_incarnation_authenticator=new_layer_incarnation_authenticator,
                effective_generation=new_effective_generation,
                layers=scratch_layers,
                timers=scratch_timers,
                composition=staged_composition,
                timer_allocations=staged_allocations,
                mandatory_expiry_registry=staged_expiry,
                diagnostics=staged_diagnostics,
            )
            staged_commit = self._stage_slot_replacements({slot.slot_index: replacement})
            # Point of no return: retained-context publication is assignment-only.
            self._publish_slot_replacements(staged_commit)
            plans.extend((
                {"phase": "COMMIT", "action": "RETAIN_LOGICAL_LAYER_AND_TIMER_IDENTITIES", "removedKeys": removed, "translations": translated},
                {"phase": "POSTCOMMIT", "action": "CANONICALIZE_RETAINED_PRESENTATION_AND_MOVEMENT"},
            ))
            return DeltaResult(True, Status.OK, True, reason, (), before_generations, self._generations(slot), prospective, _merge_plans_monotonic(plans, prospective.plans), None)
        except Exception as exc:
            status = exc.status if isinstance(exc, ModelError) else Status.INVALID_COMPOSITION
            message = exc.message if isinstance(exc, ModelError) else f"retained revalidation preflight failed: {type(exc).__name__}"
            return DeltaResult(False, status, False, reason, (), before_generations, before_generations, before, (), message)

    def revalidate_retained_context(self, slot_index: int, new_context: StaticContext, *, reason: str = "RetainedContextRevalidation") -> DeltaResult:
        rejected = _nonexact_runtime_delta_failure(self, reason)
        if rejected is not None:
            return rejected
        try:
            StackRuntime._validate_world_integrity(self)
            if type(new_context) is not StaticContext:
                raise ModelError(Status.INVALID_STATIC_DATA, "retained revalidation requires an exact StaticContext")
            _validate_closed_runtime_graph(new_context, "runtime.retainedContextInput")
            return StackRuntime._revalidate_retained_context_impl(self, slot_index, new_context, reason=reason)
        except Exception as exc:
            return _contained_runtime_delta_failure(self, slot_index, reason, exc)

    def _translation_target(self, source: OverrideDefinition, controller_id: int, authored_tired_bound: bool) -> OverrideDefinition:
        origin = source.generated.tired_origin_kind
        rows = [row for row in self.catalog.tired_translations if row.origin is origin and row.destination_controller_id == controller_id and row.authored_tired_bound == authored_tired_bound]
        if len(rows) != 1:
            raise ModelError(Status.INVALID_TRANSLATION, f"expected exactly one tired translation for {(origin, controller_id, authored_tired_bound)}")
        target = self.catalog.definitions.get(rows[0].definition_id)
        if target is None or _generated_family(target.generated) != _generated_family(source.generated) or target.timer != source.timer:
            raise ModelError(Status.INVALID_TRANSLATION, "translation target is missing or from another generated family")
        return target


def _generated_family(meta: GeneratedMetadata) -> tuple[Any, ...]:
    if not meta.has_tired_origin_kind and not meta.has_required_owner_id:
        return ("ordinary",)
    return ("generated", meta.has_tired_origin_kind, meta.tired_origin_kind, meta.has_required_owner_id, meta.required_owner_id)


def _resolved_node_id(definition: OverrideDefinition, static: StaticResolution, catalog: BehaviorCatalog) -> int:
    if definition.selector is None:
        return 0
    node = _resolve_selector(definition.selector, static, catalog)
    return node.stable_id if node else 0


def _timer_identity_set(timers: Mapping[tuple[int, int], CandidateTimer]) -> tuple[Any, ...]:
    return tuple(sorted((key, timer.entry_generation, timer.timer_generation, timer.clock.value, timer.hidden_policy.value, timer.armed_definition_id, timer.armed_duration, timer.armed_indefinite, timer.armed_static_hash, timer.armed_source_hash, timer.armed_context_authenticator, timer.allocation_authenticator, canonical_json_bytes(timer.armed_source)) for key, timer in timers.items()))


def _timer_allocation_registry(timers: Mapping[tuple[int, int], CandidateTimer]) -> Mapping[tuple[int, int], TimerAllocation]:
    return MappingProxyType({
        key: TimerAllocation(
            timer.entry_generation, timer.timer_generation, timer.expiry_plan_generation,
            timer.armed_definition_id, timer.armed_duration, timer.armed_indefinite,
            timer.clock, timer.hidden_policy, timer.recovery_policy,
            timer.calm_reset_owner_ids, timer.recovery_transition_id,
            timer.armed_static_hash, timer.armed_source_hash, timer.allocation_authenticator,
            timer.armed_source, timer.armed_context_authenticator,
        )
        for key, timer in sorted(timers.items())
    })


def _mandatory_expiry_registry(
    runtime_epoch: int,
    runtime_incarnation: str,
    data_generation: int,
    data_incarnation: str,
    slot_index: int,
    slot_generation: int,
    timers: Mapping[tuple[int, int], CandidateTimer],
    secret: bytes,
    *,
    layers: Sequence[Layer] = (),
    static: StaticResolution | None = None,
    catalog: BehaviorCatalog | None = None,
    static_context_generation: int = 1,
    static_context_incarnation: str = "",
    layer_generation: int = 1,
    layer_incarnation: str = "",
) -> MandatoryExpiryRegistry:
    plans: list[tuple[tuple[int, int], ExpiryPlan]] = []
    for key, timer in sorted(timers.items()):
        if not timer.zero_pending:
            continue
        layer = next((candidate for candidate in layers if candidate.key() == key), None)
        if type(layer) is not Layer or static is None or catalog is None:
            raise ModelError(Status.INVALID_HANDLE, "zero-pending timer lacks complete expiry binding context")
        definition = catalog.definitions.get(layer.definition_id)
        node = _resolve_selector(definition.selector, static, catalog) if definition is not None and definition.selector is not None else None
        profile_id = static.node_bindings.get(node.stable_id) if node is not None else None
        if definition is None or node is None or type(profile_id) is not int:
            raise ModelError(Status.INVALID_HANDLE, "zero-pending timer binding cannot resolve an exact candidate destination")
        action = _recovery_action(timer.recovery_policy)
        removal_targets = _expiry_removal_targets(timer, layer, layers, catalog)
        fields = (
            runtime_epoch, runtime_incarnation, data_generation, data_incarnation,
            slot_index, slot_generation, static_context_generation, static_context_incarnation,
            layer_generation, layer_incarnation,
            timer.owner_id, timer.instance_key,
            timer.entry_generation, timer.timer_generation, timer.expiry_plan_generation,
            layer.definition_id, timer.armed_definition_id, timer.armed_static_hash,
            timer.armed_source_hash, static.controller_id, node.stable_id, profile_id,
            node.role, stable_hash("selector-binding", definition.selector),
            stable_hash("generated-binding", definition.generated),
            timer.recovery_transition_id, timer.recovery_policy, action,
            tuple(timer.calm_reset_owner_ids),
            removal_targets,
        )
        plans.append((key, ExpiryPlan(*fields, _expiry_plan_authenticator(secret, fields))))
    return MandatoryExpiryRegistry(tuple(plans))


def _expiry_plan_authenticator(secret: bytes, fields: tuple[Any, ...]) -> str:
    payload = canonical_json_bytes({"domain": "candidate-expiry-plan-v2", "fields": fields})
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def _expiry_plan_fields(plan: ExpiryPlan) -> tuple[Any, ...]:
    return (
        plan.runtime_epoch, plan.runtime_incarnation, plan.data_generation, plan.data_incarnation,
        plan.slot_index, plan.slot_generation, plan.static_context_generation,
        plan.static_context_incarnation, plan.layer_generation, plan.layer_incarnation,
        plan.owner_id, plan.instance_key,
        plan.entry_generation, plan.timer_generation, plan.expiry_plan_generation,
        plan.definition_id, plan.armed_definition_id, plan.armed_static_hash,
        plan.armed_source_hash, plan.controller_id, plan.node_id, plan.profile_id,
        plan.resolved_role, plan.selector_binding_hash, plan.generated_binding_hash,
        plan.recovery_transition_id, plan.recovery_policy, plan.recovery_action,
        tuple(plan.calm_reset_owner_ids),
        tuple(plan.removal_targets),
    )


def _expiry_removal_targets(
    timer: CandidateTimer,
    expiring_layer: Layer,
    layers: Sequence[Layer],
    catalog: BehaviorCatalog,
) -> tuple[ExpiryRemovalTarget, ...]:
    """Freeze the complete destructive authority of a published expiry plan."""

    targets: dict[tuple[int, int], ExpiryRemovalTarget] = {
        expiring_layer.key(): ExpiryRemovalTarget(
            expiring_layer.owner_id, expiring_layer.instance_key,
            expiring_layer.entry_generation, expiring_layer.definition_id,
            "SELF_REQUIRED",
        )
    }
    if timer.recovery_policy is RecoveryPolicy.LEGACY_RETURN_CALM:
        reset_owners = frozenset(owner for owner in timer.calm_reset_owner_ids if owner != timer.owner_id)
        for candidate in sorted(layers, key=lambda item: item.key()):
            if candidate.key() == expiring_layer.key():
                continue
            definition = catalog.definitions.get(candidate.definition_id)
            if definition is None:
                raise ModelError(Status.INVALID_DEFINITION, "expiry recovery snapshot references a missing definition")
            reason = None
            if candidate.owner_id in reset_owners:
                reason = "CALM_RESET_REQUIRED"
            elif definition.kind is DefinitionKind.STATE_CANDIDATE:
                reason = "LATENT_CANDIDATE_REQUIRED"
            if reason is not None:
                targets[candidate.key()] = ExpiryRemovalTarget(
                    candidate.owner_id, candidate.instance_key, candidate.entry_generation,
                    candidate.definition_id, reason,
                )
    return tuple(sorted(targets.values()))


def _recovery_action(policy: RecoveryPolicy) -> str:
    return {
        RecoveryPolicy.REMOVE_SELF: "REMOVE_EXACT_SELF",
        RecoveryPolicy.LEGACY_RETURN_CALM: "REMOVE_EXACT_SELF_AND_CALM_RESET_OWNERS",
        RecoveryPolicy.REVEAL_UNDERLYING: "REVEAL_EXACT_UNDERLYING",
    }[policy]


def _rekey_scratch_entries_and_timers(layers: Sequence[Layer], timers: Mapping[tuple[int, int], CandidateTimer]) -> tuple[list[Layer], dict[tuple[int, int], CandidateTimer], int, int]:
    """Rekey surviving internal identities before generation reuse under a new epoch."""

    rekeyed_layers: list[Layer] = []
    entry_by_key: dict[tuple[int, int], int] = {}
    for generation, layer in enumerate(sorted(layers, key=lambda item: item.key()), start=1):
        entry_by_key[layer.key()] = generation
        rekeyed_layers.append(dataclasses.replace(layer, entry_generation=generation))
    rekeyed_timers: dict[tuple[int, int], CandidateTimer] = {}
    for timer_generation, (key, timer) in enumerate(sorted(timers.items()), start=1):
        rekeyed_timers[key] = dataclasses.replace(
            timer,
            entry_generation=entry_by_key[key],
            timer_generation=timer_generation,
            expiry_plan_generation=timer_generation,
        )
    return rekeyed_layers, rekeyed_timers, len(rekeyed_layers) + 1, len(rekeyed_timers) + 1


def _advance_cache_generation(value: int) -> tuple[int, bool]:
    if not 1 <= value <= GEN_MAX:
        raise ModelError(Status.INVALID_STATIC_DATA, "cache generation is outside nonzero u32")
    return (1, True) if value == GEN_MAX else (value + 1, False)


def _validate_diagnostics(value: Any) -> SlotDiagnostics:
    if type(value) is not SlotDiagnostics:
        raise ModelError(Status.INVALID_HANDLE, "slot diagnostics registry has the wrong type")
    if any(type(getattr(value, field_.name)) is not int or not 0 <= getattr(value, field_.name) <= GEN_MAX for field_ in dataclasses.fields(SlotDiagnostics)):
        raise ModelError(Status.INVALID_HANDLE, "slot diagnostics fields must be bounded nonnegative integers")
    return value


def _merge_diagnostics(target: SlotDiagnostics, delta: SlotDiagnostics) -> SlotDiagnostics:
    _validate_diagnostics(target)
    _validate_diagnostics(delta)
    values = {field_.name: getattr(target, field_.name) + getattr(delta, field_.name) for field_ in dataclasses.fields(SlotDiagnostics)}
    if any(value > GEN_MAX for value in values.values()):
        raise ModelError(Status.INVALID_HANDLE, "slot diagnostics arithmetic overflow")
    return SlotDiagnostics(**values)


def _diagnostic_increment(target: SlotDiagnostics, field_name: str, amount: int = 1) -> SlotDiagnostics:
    if type(amount) is not int or amount < 0 or field_name not in {field_.name for field_ in dataclasses.fields(SlotDiagnostics)}:
        raise ModelError(Status.INVALID_HANDLE, "diagnostic increment is malformed")
    return _merge_diagnostics(target, SlotDiagnostics(**{field_name: amount}))


def _mark_expire_on_hide(timers: Mapping[tuple[int, int], CandidateTimer], composition: Composition, presentation_gate: bool) -> list[Mapping[str, Any]]:
    if presentation_gate:
        return []
    changes: list[Mapping[str, Any]] = []
    winner_key = (composition.winner.owner_id, composition.winner.instance_key) if composition.winner.kind == "LAYER" else None
    for key, timer in sorted(timers.items()):
        if timer.hidden_policy is HiddenPolicy.EXPIRE_ON_HIDE and key != winner_key and not timer.zero_pending:
            before = timer.remaining_ticks
            timer.remaining_ticks = 0
            timer.zero_pending = True
            changes.append({"ownerId": key[0], "instanceKey": key[1], "beforeRemainingTicks": before, "afterRemainingTicks": 0, "timerGeneration": timer.timer_generation})
    return changes


def _merge_plans_monotonic(*groups: Sequence[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:
    phase_rank = {"PRECOMMIT": 0, "STABILIZE": 1, "COMMIT": 2, "POSTCOMMIT": 3, "DIAGNOSTIC": 4}
    indexed = [(phase_rank.get(plan.get("phase", "DIAGNOSTIC"), 4), group_index, item_index, plan) for group_index, group in enumerate(groups) for item_index, plan in enumerate(group)]
    return tuple(plan for _rank, _group, _item, plan in sorted(indexed, key=lambda item: item[:3]))


def _unique_role_bound(static: StaticResolution, catalog: BehaviorCatalog, role: SemanticRole) -> bool:
    controller = catalog.controllers[static.controller_id]
    matches = [node for node in controller.nodes if node.role is role and static.node_bindings.get(node.stable_id) is not None]
    if len(matches) > 1:
        raise ModelError(Status.AMBIGUOUS_SELECTOR, f"destination has {len(matches)} bound {role.value} nodes")
    return len(matches) == 1


def runtime_to_dict(runtime: StackRuntime) -> Mapping[str, Any]:
    _require_exact_stack_runtime(runtime)
    StackRuntime._validate_world_integrity(runtime)
    root_storage = object.__getattribute__(runtime, "__dict__")
    slot_table = root_storage["slots"]
    authority_table = root_storage["_layer_authorities"]
    payload = {
        "schema": MODEL_SCHEMA,
        "schemaVersion": MODEL_SCHEMA_VERSION,
        "dataGeneration": root_storage["data_generation"],
        "dataIncarnation": root_storage["_data_incarnation"],
        "runtimeEpoch": root_storage["runtime_epoch"],
        "runtimeIncarnation": root_storage["_runtime_incarnation"],
        "slots": {
            slot_index: {
                "slotIndex": slot_storage["slot_index"],
                "static": slot_storage["static"],
                "layers": slot_storage["layers"],
                "timers": list(slot_storage["timers"].values()),
                "timerAllocations": slot_storage["timer_allocations"],
                "mandatoryExpiryRegistry": slot_storage["mandatory_expiry_registry"],
                "generations": {
                    "slotGeneration": slot_storage["slot_generation"],
                    "staticContextGeneration": slot_storage["static_context_generation"],
                    "layerGeneration": slot_storage["layer_generation"],
                    "effectiveGeneration": slot_storage["effective_generation"],
                },
                "staticContextIncarnation": slot_storage["static_context_incarnation"],
                "layerIncarnation": slot_storage["layer_incarnation"],
                "layerIncarnationAuthenticator": slot_storage["layer_incarnation_authenticator"],
                "layerAuthority": authority_table.get(slot_index),
                "live": slot_storage["live"],
                "presentationGate": slot_storage["presentation_gate"],
                "capturedSpawnPolicyId": slot_storage["captured_spawn_policy_id"],
                "capturedPopulationPolicyId": slot_storage["captured_population_policy_id"],
                "capturedSpawnPolicyValues": slot_storage["captured_spawn_policy_values"],
                "capturedPopulationPolicyValues": slot_storage["captured_population_policy_values"],
                "capturedPolicyAuthenticator": slot_storage["captured_policy_authenticator"],
                "installedContextAuthenticator": slot_storage["installed_context_authenticator"],
                "retainedContextAuthenticators": slot_storage["retained_context_authenticators"],
                "effective": slot_storage["composition"],
                "diagnostics": slot_storage["diagnostics"],
                "transitionHistory": list(slot_storage["transition_history"]),
            }
            for slot_index, slot in sorted(slot_table.items())
            for slot_storage in (object.__getattribute__(slot, "__dict__"),)
        },
    }
    # Canonical JSON conversion followed by exact JSON decoding is the wire
    # detachment boundary: no runtime container or dataclass reference escapes.
    return json.loads(canonical_json_bytes(payload))


def result_to_dict(result: DeltaResult) -> Mapping[str, Any]:
    if type(result) is not DeltaResult:
        raise ModelError(Status.INVALID_HANDLE, "result serialization requires an exact DeltaResult")
    try:
        _validate_closed_runtime_graph(result, "deltaResult")
        return json.loads(canonical_json_bytes(result))
    except ModelError:
        raise
    except Exception:
        raise ModelError(Status.INVALID_HANDLE, "delta result serialization rejected malformed data") from None


# ------------------------------ self-check fixture ---------------------------


def _fixture_catalog() -> tuple[BehaviorCatalog, dict[str, int]]:
    ids = {
        "owner_awareness": 101, "owner_stamina": 102, "owner_sleep": 103,
        "owner_pickup": 104, "owner_weather": 105, "owner_script": 106,
        "owner_fled": 107, "owner_ram": 108, "owner_throw": 109,
        "calm": 1, "active": 2, "tired": 3, "asleep": 4, "carried": 5,
    }
    profiles = {
        1: StateProfile(1, "CALM", "WANDER", speed=2, movement_range=4, allowed_tile="GROUND", hop_min_distance=1, hop_max_distance=3),
        2: StateProfile(2, "ACTIVE", "CHASE", "PLAYER", 3, 6, "GROUND", hop_min_distance=1, hop_max_distance=4, battle_trigger="CONTACT"),
        3: StateProfile(3, "TIRED_EMOTE", "IDLE", speed=1, allowed_tile="GROUND"),
        4: StateProfile(4, "ASLEEP", "IDLE", speed=1, allowed_tile="GROUND"),
        5: StateProfile(5, "CARRIED", "CARRIED", speed=1),
        11: StateProfile(11, "CALM", "WANDER", speed=2, movement_range=5, allowed_tile="WATER"),
        12: StateProfile(12, "ACTIVE", "FLEE", "PLAYER", 4, 8, "WATER"),
        13: StateProfile(13, "TIRED_EMOTE", "IDLE", speed=1, allowed_tile="WATER"),
        15: StateProfile(15, "FALLBACK_TIRED", "IDLE", speed=1, allowed_tile="WATER"),
    }
    controllers = {
        10: Controller(10, 1, (ControllerNode(1, SemanticRole.CALM, 1), ControllerNode(2, SemanticRole.ATTENTIVE, 2), ControllerNode(3, SemanticRole.TIRED, 3), ControllerNode(4, SemanticRole.ASLEEP, 4), ControllerNode(5, SemanticRole.CARRIED, 5)), ControllerValues(), 1, 1, 1),
        20: Controller(20, 11, (ControllerNode(11, SemanticRole.CALM, 11), ControllerNode(12, SemanticRole.ATTENTIVE, 12), ControllerNode(13, SemanticRole.TIRED, 13), ControllerNode(15, SemanticRole.CUSTOM, 15, 900)), ControllerValues(), 2, 2, 1),
        30: Controller(30, 21, (ControllerNode(21, SemanticRole.CALM, 11), ControllerNode(22, SemanticRole.ATTENTIVE, 12), ControllerNode(25, SemanticRole.CUSTOM, 15, 900)), ControllerValues(), 2, 2, 1),
    }
    modifiers = {
        1: Modifier(1, {"state.speed": ModifierOperation(OperatorKind.ADD, -1)}),
        2: Modifier(2, {"state.speed": ModifierOperation(OperatorKind.SET, 4), "state.hopMaxDistance": ModifierOperation(OperatorKind.AT_MOST, 0)}),
        3: Modifier(3, {"controller.alertChance": ModifierOperation(OperatorKind.ADD_AT_LEAST, -90, 25)}),
    }
    preserve = LifetimePolicy.PRESERVE_LOGICAL
    stamina_meta = GeneratedMetadata(False, None, True, ids["owner_stamina"])
    fled_meta = GeneratedMetadata(True, TiredOriginKind.FLED, True, ids["owner_fled"])
    ram_meta = GeneratedMetadata(True, TiredOriginKind.RAM_CRASH, True, ids["owner_ram"])
    throw_meta = GeneratedMetadata(True, TiredOriginKind.THROW_RECOVERY, True, ids["owner_throw"])
    calm_reset_owners = (ids["owner_awareness"], 110, 111)
    definitions = {
        1: OverrideDefinition(1, DefinitionKind.STATE_CANDIDATE, Channel.CONTROLLER_STATE, 100, selector=NodeSelector.semantic(SemanticRole.ATTENTIVE), map_policy=preserve),
        2: OverrideDefinition(2, DefinitionKind.STATE_CANDIDATE, Channel.TEMPORARY_EFFECT, 100, selector=NodeSelector.semantic(SemanticRole.TIRED), map_policy=preserve, timer=CandidateTimerPolicy(4, hidden_policy=HiddenPolicy.PAUSE_WHILE_HIDDEN, recovery_policy=RecoveryPolicy.LEGACY_RETURN_CALM, calm_reset_owner_ids=calm_reset_owners), generated=stamina_meta),
        3: OverrideDefinition(3, DefinitionKind.STATE_CANDIDATE, Channel.TEMPORARY_EFFECT, 200, allow_multiple_instances_per_owner=True, selector=NodeSelector.semantic(SemanticRole.ASLEEP), map_policy=preserve, timer=CandidateTimerPolicy(2, hidden_policy=HiddenPolicy.CONTINUE_WHILE_HIDDEN)),
        4: OverrideDefinition(4, DefinitionKind.STATE_CANDIDATE, Channel.POSSESSION, 200, selector=NodeSelector.semantic(SemanticRole.CARRIED)),
        5: OverrideDefinition(5, DefinitionKind.MODIFIER, Channel.TEMPORARY_EFFECT, 20, allow_multiple_owners=True, modifier_id=1),
        6: OverrideDefinition(6, DefinitionKind.MODIFIER, Channel.SCRIPTED_FORCE, 10, modifier_id=2),
        7: OverrideDefinition(7, DefinitionKind.MODIFIER, Channel.TEMPORARY_EFFECT, 30, modifier_id=3),
        8: OverrideDefinition(8, DefinitionKind.STATE_CANDIDATE, Channel.TEMPORARY_EFFECT, 90, selector=NodeSelector.semantic(SemanticRole.TIRED), map_policy=preserve, timer=CandidateTimerPolicy(4), generated=fled_meta),
        9: OverrideDefinition(9, DefinitionKind.STATE_CANDIDATE, Channel.TEMPORARY_EFFECT, 90, applicability=Applicability(controller_ids=frozenset({20})), selector=NodeSelector.exact(20, 15), map_policy=preserve, timer=CandidateTimerPolicy(4), generated=fled_meta),
        10: OverrideDefinition(10, DefinitionKind.STATE_CANDIDATE, Channel.TEMPORARY_EFFECT, 90, applicability=Applicability(controller_ids=frozenset({20})), selector=NodeSelector.semantic(SemanticRole.TIRED), map_policy=preserve, timer=CandidateTimerPolicy(4), generated=fled_meta),
        11: OverrideDefinition(11, DefinitionKind.STATE_CANDIDATE, Channel.TEMPORARY_EFFECT, 90, applicability=Applicability(controller_ids=frozenset({30})), selector=NodeSelector.exact(30, 25), map_policy=preserve, timer=CandidateTimerPolicy(4), generated=fled_meta),
        12: OverrideDefinition(12, DefinitionKind.STATE_CANDIDATE, Channel.CONTROLLER_STATE, 50, selector=NodeSelector.semantic(SemanticRole.ATTENTIVE), timer=CandidateTimerPolicy(3, hidden_policy=HiddenPolicy.EXPIRE_ON_HIDE)),
        13: OverrideDefinition(13, DefinitionKind.STATE_CANDIDATE, Channel.TEMPORARY_EFFECT, 210, applicability=Applicability(controller_ids=frozenset({10})), allow_multiple_instances_per_owner=True, selector=NodeSelector.semantic(SemanticRole.ASLEEP), timer=CandidateTimerPolicy(0, hidden_policy=HiddenPolicy.CONTINUE_WHILE_HIDDEN)),
        14: OverrideDefinition(14, DefinitionKind.STATE_CANDIDATE, Channel.TEMPORARY_EFFECT, 80, selector=NodeSelector.semantic(SemanticRole.TIRED), timer=CandidateTimerPolicy(9)),
        15: OverrideDefinition(15, DefinitionKind.STATE_CANDIDATE, Channel.TEMPORARY_EFFECT, 211, applicability=Applicability(controller_ids=frozenset({10})), selector=NodeSelector.semantic(SemanticRole.ASLEEP), timer=CandidateTimerPolicy(255, hidden_policy=HiddenPolicy.CONTINUE_WHILE_HIDDEN)),
        16: OverrideDefinition(16, DefinitionKind.STATE_CANDIDATE, Channel.TEMPORARY_EFFECT, 212, applicability=Applicability(controller_ids=frozenset({10})), selector=NodeSelector.exact(10, 4), timer=CandidateTimerPolicy(255, hidden_policy=HiddenPolicy.CONTINUE_WHILE_HIDDEN)),
        17: OverrideDefinition(17, DefinitionKind.STATE_CANDIDATE, Channel.CONTROLLER_STATE, 49, applicability=Applicability(controller_ids=frozenset({10})), selector=NodeSelector.semantic(SemanticRole.ATTENTIVE), timer=CandidateTimerPolicy(255)),
        20: OverrideDefinition(20, DefinitionKind.STATE_CANDIDATE, Channel.TEMPORARY_EFFECT, 91, selector=NodeSelector.semantic(SemanticRole.TIRED), map_policy=preserve, timer=CandidateTimerPolicy(4, recovery_policy=RecoveryPolicy.LEGACY_RETURN_CALM, calm_reset_owner_ids=calm_reset_owners), generated=ram_meta),
        21: OverrideDefinition(21, DefinitionKind.STATE_CANDIDATE, Channel.TEMPORARY_EFFECT, 91, applicability=Applicability(controller_ids=frozenset({20})), selector=NodeSelector.semantic(SemanticRole.TIRED), map_policy=preserve, timer=CandidateTimerPolicy(4, recovery_policy=RecoveryPolicy.LEGACY_RETURN_CALM, calm_reset_owner_ids=calm_reset_owners), generated=ram_meta),
        22: OverrideDefinition(22, DefinitionKind.STATE_CANDIDATE, Channel.TEMPORARY_EFFECT, 91, applicability=Applicability(controller_ids=frozenset({20})), selector=NodeSelector.exact(20, 15), map_policy=preserve, timer=CandidateTimerPolicy(4, recovery_policy=RecoveryPolicy.LEGACY_RETURN_CALM, calm_reset_owner_ids=calm_reset_owners), generated=ram_meta),
        23: OverrideDefinition(23, DefinitionKind.STATE_CANDIDATE, Channel.TEMPORARY_EFFECT, 91, applicability=Applicability(controller_ids=frozenset({30})), selector=NodeSelector.exact(30, 25), map_policy=preserve, timer=CandidateTimerPolicy(4, recovery_policy=RecoveryPolicy.LEGACY_RETURN_CALM, calm_reset_owner_ids=calm_reset_owners), generated=ram_meta),
        30: OverrideDefinition(30, DefinitionKind.STATE_CANDIDATE, Channel.TEMPORARY_EFFECT, 92, selector=NodeSelector.semantic(SemanticRole.TIRED), map_policy=preserve, timer=CandidateTimerPolicy(4, recovery_policy=RecoveryPolicy.LEGACY_RETURN_CALM, calm_reset_owner_ids=calm_reset_owners), generated=throw_meta),
        31: OverrideDefinition(31, DefinitionKind.STATE_CANDIDATE, Channel.TEMPORARY_EFFECT, 92, applicability=Applicability(controller_ids=frozenset({20})), selector=NodeSelector.semantic(SemanticRole.TIRED), map_policy=preserve, timer=CandidateTimerPolicy(4, recovery_policy=RecoveryPolicy.LEGACY_RETURN_CALM, calm_reset_owner_ids=calm_reset_owners), generated=throw_meta),
        32: OverrideDefinition(32, DefinitionKind.STATE_CANDIDATE, Channel.TEMPORARY_EFFECT, 92, applicability=Applicability(controller_ids=frozenset({20})), selector=NodeSelector.exact(20, 15), map_policy=preserve, timer=CandidateTimerPolicy(4, recovery_policy=RecoveryPolicy.LEGACY_RETURN_CALM, calm_reset_owner_ids=calm_reset_owners), generated=throw_meta),
        33: OverrideDefinition(33, DefinitionKind.STATE_CANDIDATE, Channel.TEMPORARY_EFFECT, 92, applicability=Applicability(controller_ids=frozenset({30})), selector=NodeSelector.exact(30, 25), map_policy=preserve, timer=CandidateTimerPolicy(4, recovery_policy=RecoveryPolicy.LEGACY_RETURN_CALM, calm_reset_owner_ids=calm_reset_owners), generated=throw_meta),
    }
    for index in range(9):
        definition_id = 1200 + index
        definitions[definition_id] = OverrideDefinition(definition_id, DefinitionKind.MODIFIER, Channel.TEMPORARY_EFFECT, index, modifier_id=1)
    rules = (
        StaticRule(3, ContextMatcher(map_ids=frozenset({1})), (StaticAction(3, StaticActionKind.APPLY_CONTROLLER_MODIFIER, static_priority=5, controller_id=10, modifier_id=3),)),
        StaticRule(1, ContextMatcher(map_ids=frozenset({2})), (StaticAction(1, StaticActionKind.ASSIGN_CONTROLLER, assignment_priority=10, controller_id=20),)),
        StaticRule(2, ContextMatcher(map_ids=frozenset({3})), (StaticAction(2, StaticActionKind.ASSIGN_CONTROLLER, assignment_priority=10, controller_id=30),)),
        StaticRule(4, ContextMatcher(map_ids=frozenset({4})), (
            StaticAction(4, StaticActionKind.APPLY_CANDIDATE_TIMER_OPERATOR, static_priority=2, candidate_definition_id=2, timer_operation=ModifierOperation(OperatorKind.ADD, 2)),
            StaticAction(5, StaticActionKind.APPLY_SPAWN_POLICY_PATCH, static_priority=3, spawn_policy_patch_id=1),
            StaticAction(6, StaticActionKind.APPLY_POPULATION_POLICY_PATCH, static_priority=4, population_policy_patch_id=1),
        )),
        StaticRule(5, ContextMatcher(map_ids=frozenset({6})), (StaticAction(7, StaticActionKind.BIND_NODE, static_priority=2, controller_id=10, node_id=1, profile_id=11),)),
        StaticRule(6, ContextMatcher(map_ids=frozenset({9})), (
            StaticAction(8, StaticActionKind.APPLY_SPAWN_POLICY_PATCH, static_priority=1, spawn_policy_patch_id=1),
            StaticAction(9, StaticActionKind.BIND_SPAWN_POLICY, static_priority=2, spawn_policy_id=2),
            StaticAction(10, StaticActionKind.APPLY_SPAWN_POLICY_PATCH, static_priority=3, spawn_policy_patch_id=1),
            StaticAction(11, StaticActionKind.APPLY_POPULATION_POLICY_PATCH, static_priority=1, population_policy_patch_id=1),
            StaticAction(12, StaticActionKind.BIND_POPULATION_POLICY, static_priority=2, population_policy_id=2),
            StaticAction(13, StaticActionKind.APPLY_POPULATION_POLICY_PATCH, static_priority=3, population_policy_patch_id=1),
        )),
        StaticRule(7, ContextMatcher(map_ids=frozenset({10})), (
            StaticAction(14, StaticActionKind.ASSIGN_CONTROLLER, assignment_priority=10, controller_id=20),
            StaticAction(15, StaticActionKind.UNBIND_NODE, static_priority=1, controller_id=20, node_id=13),
        )),
        StaticRule(8, ContextMatcher(map_ids=frozenset({12})), (
            StaticAction(16, StaticActionKind.APPLY_CANDIDATE_TIMER_OPERATOR, static_priority=1, candidate_definition_id=15, timer_operation=ModifierOperation(OperatorKind.SET, 255)),
            StaticAction(17, StaticActionKind.APPLY_CANDIDATE_TIMER_OPERATOR, static_priority=2, candidate_definition_id=16, timer_operation=ModifierOperation(OperatorKind.SET, 255)),
        )),
        StaticRule(9, ContextMatcher(map_ids=frozenset({13})), (
            StaticAction(18, StaticActionKind.APPLY_CANDIDATE_TIMER_OPERATOR, static_priority=1, candidate_definition_id=15, timer_operation=ModifierOperation(OperatorKind.ADD, 0)),
        )),
        StaticRule(10, ContextMatcher(map_ids=frozenset({14})), (
            StaticAction(19, StaticActionKind.APPLY_CANDIDATE_TIMER_OPERATOR, static_priority=1, candidate_definition_id=15, timer_operation=ModifierOperation(OperatorKind.SET, 0)),
            StaticAction(20, StaticActionKind.APPLY_CANDIDATE_TIMER_OPERATOR, static_priority=2, candidate_definition_id=16, timer_operation=ModifierOperation(OperatorKind.SET, 0)),
        )),
    )
    catalog = BehaviorCatalog(profiles, controllers, modifiers, definitions, rules, 10,
        spawn_policies={1: SpawnPolicy(1, maximum_distance=2), 2: SpawnPolicy(2, "APPEAR", "NEAR_PLAYER", 2, 4, 8)},
        population_policies={1: PopulationPolicy(1, 1), 2: PopulationPolicy(2, 2, 5)}, hook_sets={1: HookSet(1)},
        spawn_policy_patches={1: PolicyPatch(1, {"spawn.minimumDistance": ModifierOperation(OperatorKind.ADD, 1)})},
        population_policy_patches={1: PolicyPatch(1, {"population.limit": ModifierOperation(OperatorKind.SET, 3)})},
        tired_translations=(
            TiredTranslation(TiredOriginKind.FLED, 10, True, 8), TiredTranslation(TiredOriginKind.FLED, 20, True, 10), TiredTranslation(TiredOriginKind.FLED, 20, False, 9), TiredTranslation(TiredOriginKind.FLED, 30, False, 11),
            TiredTranslation(TiredOriginKind.RAM_CRASH, 10, True, 20), TiredTranslation(TiredOriginKind.RAM_CRASH, 20, True, 21), TiredTranslation(TiredOriginKind.RAM_CRASH, 20, False, 22), TiredTranslation(TiredOriginKind.RAM_CRASH, 30, False, 23),
            TiredTranslation(TiredOriginKind.THROW_RECOVERY, 10, True, 30), TiredTranslation(TiredOriginKind.THROW_RECOVERY, 20, True, 31), TiredTranslation(TiredOriginKind.THROW_RECOVERY, 20, False, 32), TiredTranslation(TiredOriginKind.THROW_RECOVERY, 30, False, 33),
        ),
        owner_names={ids["owner_stamina"]: "stamina", ids["owner_fled"]: "battle-fled", ids["owner_ram"]: "ram-crash", ids["owner_throw"]: "throw-recovery"})
    return catalog, ids


def run_self_checks() -> list[str]:
    catalog, ids = _fixture_catalog()
    runtime = StackRuntime(catalog)
    slot = runtime.install_slot(0, StaticContext(map_id=1))
    passed: list[str] = []

    def check(name: str, condition: bool) -> None:
        if not condition:
            raise AssertionError(name)
        passed.append(name)

    def raises_status(callback: Any, status: Status) -> bool:
        try:
            callback()
        except ModelError as exc:
            return exc.status is status
        return False

    def rejects_item_assignment(mapping: Mapping[Any, Any], key: Any, value: Any) -> bool:
        try:
            mapping[key] = value  # type: ignore[index]
        except TypeError:
            return True
        return False

    def rejects_attribute_assignment(target: Any, name: str, value: Any) -> bool:
        try:
            setattr(target, name, value)
        except AttributeError:
            return True
        return False

    def semantic_slot_snapshot(target: StackRuntime, index: int = 0) -> bytes:
        current = target.slots[index]
        return canonical_json_bytes({
            "runtimeEpoch": target.runtime_epoch, "runtimeIncarnation": target.runtime_incarnation,
            "dataGeneration": target.data_generation, "dataIncarnation": target.data_incarnation,
            "live": current.live, "static": current.static,
            "layers": current.layers, "timers": current.timers, "timerAllocations": current.timer_allocations,
            "mandatoryExpiryRegistry": current.mandatory_expiry_registry, "slotGeneration": current.slot_generation,
            "staticContextGeneration": current.static_context_generation, "layerGeneration": current.layer_generation,
            "staticContextIncarnation": current.static_context_incarnation,
            "layerIncarnation": current.layer_incarnation,
            "layerIncarnationAuthenticator": current.layer_incarnation_authenticator,
            "layerAuthority": target._layer_authorities.get(index),
            "effectiveGeneration": current.effective_generation, "nextEntryGeneration": current.next_entry_generation,
            "nextTimerGeneration": current.next_timer_generation, "composition": current.composition,
            "capturedSpawnPolicyId": current.captured_spawn_policy_id,
            "capturedPopulationPolicyId": current.captured_population_policy_id,
            "capturedSpawnPolicyValues": current.captured_spawn_policy_values,
            "capturedPopulationPolicyValues": current.captured_population_policy_values,
            "capturedPolicyAuthenticator": current.captured_policy_authenticator,
            "installedContextAuthenticator": current.installed_context_authenticator,
            "retainedContextAuthenticators": current.retained_context_authenticators,
            "presentationGate": current.presentation_gate, "history": list(current.transition_history),
        })

    def force_authenticated_layer_generation(target: StackRuntime, current: SlotRuntime, generation: int) -> None:
        current.layer_generation = generation
        current.layer_incarnation_authenticator = target._layer_incarnation_authenticator(current)
        target._layer_authorities = MappingProxyType({
            **target._layer_authorities,
            current.slot_index: target._layer_authority_for_slot(current),
        })
        current.mandatory_expiry_registry = target._expiry_registry(current, current.timers)

    def force_authenticated_data_generation(target: StackRuntime, generation: int) -> None:
        object.__setattr__(target, "data_generation", generation)
        object.__setattr__(target, "_secret_authenticator", _root_secret_authenticator(
            object.__getattribute__(target, "_root_anchor"),
            object.__getattribute__(target, "_secret"),
            object.__getattribute__(target, "_runtime_incarnation"),
            generation,
            object.__getattribute__(target, "_data_incarnation"),
        ))

    def exact_runtime_internal_snapshot(target: StackRuntime) -> bytes:
        def known_graph_payload(value: Any) -> Any:
            value_type = type(value)
            if value is None or value_type in {bool, int, float, str, bytes}:
                return value.hex() if value_type is bytes else value
            for enum_index, (enum_type, members) in enumerate(_RUNTIME_GRAPH_ENUM_MEMBERS):
                if value_type is enum_type:
                    member_index = next((index for index, member in enumerate(members) if value is member), -1)
                    return ("enum", enum_index, member_index)
            for schema_index, (dataclass_type, field_names, _carriers) in enumerate(_RUNTIME_GRAPH_DATACLASS_SCHEMA):
                if value_type is dataclass_type:
                    storage = object.__getattribute__(value, "__dict__")
                    return (
                        "dataclass", schema_index,
                        tuple((field_name, known_graph_payload(storage[field_name])) for field_name in field_names),
                    )
            if value_type is ClosedMap:
                return ("closedMap", tuple(
                    (known_graph_payload(key), known_graph_payload(item))
                    for key, item in object.__getattribute__(value, "_items")
                ))
            if value_type is dict:
                return ("dict", tuple(
                    (known_graph_payload(key), known_graph_payload(item))
                    for key, item in value.items()
                ))
            if value_type in {list, tuple, deque, set, frozenset}:
                return (value_type.__name__, tuple(known_graph_payload(item) for item in value))
            return ("unsupported-closed-snapshot-value",)

        slot_fields = next(fields for value_type, fields, _carriers in _RUNTIME_GRAPH_DATACLASS_SCHEMA if value_type is SlotRuntime)
        slot_payload = {
            slot_index: {
                field_name: known_graph_payload(object.__getattribute__(slot, "__dict__")[field_name])
                for field_name in slot_fields
            }
            for slot_index, slot in object.__getattribute__(target, "slots").items()
        }
        return canonical_json_bytes({
            "runtimeEpoch": object.__getattribute__(target, "runtime_epoch"),
            "runtimeIncarnation": object.__getattribute__(target, "_runtime_incarnation"),
            "dataGeneration": object.__getattribute__(target, "data_generation"),
            "dataIncarnation": object.__getattribute__(target, "_data_incarnation"),
            "secretHex": object.__getattribute__(target, "_secret").hex(),
            "rootAnchorHex": object.__getattribute__(target, "_root_anchor").hex(),
            "secretAuthenticator": object.__getattribute__(target, "_secret_authenticator"),
            "catalog": known_graph_payload(object.__getattribute__(target, "_catalog")),
            "stagedCatalog": known_graph_payload(object.__getattribute__(target, "_staged_catalog")),
            "slotCount": object.__getattribute__(target, "slot_count"),
            "slots": slot_payload,
            "layerAuthorities": known_graph_payload(object.__getattribute__(target, "_layer_authorities")),
        })

    check("calm-init-and-static-controller-modifier", slot.composition.winner.role is SemanticRole.CALM and not slot.layers and slot.static.controller_values.alert_chance == 25 and slot.static.controller_provenance["controller.alertChance"]["contributions"][0]["modifierId"] == 3)
    active = runtime.apply(0, 1, ids["owner_awareness"])
    check("state-candidate-winner", active.ok and slot.composition.winner.role is SemanticRole.ATTENTIVE)
    rain = runtime.apply(0, 5, ids["owner_weather"])
    tired = runtime.apply(0, 2, ids["owner_stamina"])
    check("stacking-winner-order", tired.ok and slot.composition.winner.role is SemanticRole.TIRED and slot.composition.state_values["speed"] == 1)
    runtime.remove(0, active.operation_results[0].handle)
    check("middle-removal", slot.composition.winner.role is SemanticRole.TIRED and len(slot.layers) == 2)
    runtime.remove(0, rain.operation_results[0].handle)
    check("owner-isolation", len(slot.layers) == 1 and slot.layers[0].owner_id == ids["owner_stamina"])
    duplicate_before = (slot.layer_generation, slot.timers[(ids["owner_stamina"], 0)].remaining_ticks)
    duplicate = runtime.apply(0, 2, ids["owner_stamina"])
    check("apply-idempotency", duplicate.status is Status.IDEMPOTENT and duplicate_before == (slot.layer_generation, slot.timers[(ids["owner_stamina"], 0)].remaining_ticks))
    old_tired_handle = duplicate.operation_results[0].handle
    replaced = runtime.replace(0, ids["owner_stamina"], 0, 2)
    check("replace-restarts-timer", replaced.ok and replaced.operation_results[0].handle.entry_generation != old_tired_handle.entry_generation and slot.timers[(ids["owner_stamina"], 0)].remaining_ticks == 4)
    stale_count_before = slot.diagnostics.stale_handle_count
    stale = runtime.remove(0, old_tired_handle)
    check("stale-optional-handle", stale.status is Status.STALE_NOOP and stale.operation_results[0].status is Status.STALE_NOOP and slot.diagnostics.stale_handle_count == stale_count_before + 1)
    snapshot = canonical_json_bytes(runtime_to_dict(runtime))
    atomic = runtime.apply_stack_delta(0, slot.slot_generation, (DeltaOperation.remove_required("stale", old_tired_handle), runtime.bind_delta_operation(DeltaOperation.apply("new", 5, ids["owner_weather"]))), "atomic-stale")
    check("atomic-required-rejection", atomic.status is Status.STALE_HANDLE and snapshot == canonical_json_bytes(runtime_to_dict(runtime)) and len(slot.layers) == 1)
    # The only permitted failure mutation above is its stale diagnostic counter.
    ambiguous = runtime.apply_stack_delta(0, slot.slot_generation, (runtime.bind_delta_operation(DeltaOperation.apply("a", 5, ids["owner_weather"])), runtime.bind_delta_operation(DeltaOperation.replace("b", 5, ids["owner_weather"]))), "ambiguous")
    check("ambiguous-delta", ambiguous.status is Status.AMBIGUOUS_DELTA and len(slot.layers) == 1)
    unauthorized = runtime.apply(0, 2, ids["owner_weather"])
    check("required-owner-authorization", unauthorized.status is Status.OWNER_NOT_AUTHORIZED)
    runtime.clear(0)
    runtime.apply(0, 6, ids["owner_script"])
    runtime.apply(0, 5, ids["owner_weather"])
    check("modifier-order-and-normalization", slot.composition.state_values["speed"] == 4 and slot.composition.state_values["hopMaxDistance"] == slot.composition.state_values["hopMinDistance"])
    check("field-provenance", len(slot.composition.provenance["state.speed"]["contributions"]) == 2)
    runtime.clear(0)
    runtime.apply(0, 1, ids["owner_awareness"])
    runtime.apply(0, 2, ids["owner_stamina"])
    runtime.apply(0, 3, ids["owner_sleep"], 77)
    runtime.apply(0, 4, ids["owner_pickup"])
    layer_gen = slot.layer_generation
    runtime.tick_candidate_timers(0, 2)
    check("hidden-timers", slot.timers[(ids["owner_stamina"], 0)].remaining_ticks == 4 and slot.timers[(ids["owner_sleep"], 77)].zero_pending and slot.layer_generation == layer_gen)
    sleep_timer = slot.timers[(ids["owner_sleep"], 77)]
    sleep_plan = next(plan for plan in runtime.pending_expiry_plans(0) if plan["ownerId"] == ids["owner_sleep"])
    expired = runtime.commit_expiry(sleep_plan)
    check("forced-sleep-under-carried", expired.ok and slot.composition.winner.role is SemanticRole.CARRIED and (ids["owner_stamina"], 0) in slot.timers)
    runtime.remove_owner(0, ids["owner_pickup"])
    check("reveal-paused-tired", slot.composition.winner.role is SemanticRole.TIRED and slot.timers[(ids["owner_stamina"], 0)].remaining_ticks == 4)
    runtime.clear(0)
    capacity_filled = True
    for index, owner in enumerate(range(200, 208)):
        capacity_filled = capacity_filled and runtime.apply(0, 1200 + index, owner).ok
    overflow_layers = copy.deepcopy(slot.layers)
    overflow = runtime.apply(0, 1208, 999)
    check("fixed-capacity-and-overflow", capacity_filled and overflow.status is Status.CAPACITY_EXCEEDED and slot.layers == overflow_layers and slot.diagnostics.overflow_count == 0)
    runtime.clear(0)
    fled = runtime.apply(0, 8, ids["owner_fled"])
    first_fled_handle = fled.operation_results[0].handle
    generated_replace = runtime.replace(0, ids["owner_fled"], 0, 8)
    handle_before = generated_replace.operation_results[0].handle
    family_mismatch = runtime.replace(0, ids["owner_fled"], 0, 1)
    check("generated-origin-copy", generated_replace.ok and handle_before.entry_generation != first_fled_handle.entry_generation and slot.layers[0].generated.tired_origin_kind is TiredOriginKind.FLED and family_mismatch.status is Status.GENERATED_WRAPPER_FAMILY_MISMATCH and runtime._make_handle(slot, slot.layers[0]) == handle_before)
    timer_before = copy.deepcopy(slot.timers[(ids["owner_fled"], 0)])
    rebound = runtime.revalidate_retained_context(0, StaticContext(map_id=2))
    semantic_ok = rebound.ok and slot.static.controller_id == 20 and slot.layers[0].definition_id == 10 and runtime._make_handle(slot, slot.layers[0]) == handle_before and slot.timers[(ids["owner_fled"], 0)] == timer_before
    fallback = runtime.revalidate_retained_context(0, StaticContext(map_id=3))
    check("retained-semantic-rebinding", semantic_ok and fallback.ok and slot.static.controller_id == 30 and slot.layers[0].definition_id == 11 and runtime._make_handle(slot, slot.layers[0]) == handle_before and slot.timers[(ids["owner_fled"], 0)] == timer_before)
    check("retained-planned-engine-actions", any(plan["action"] == "CANONICALIZE_RETAINED_PRESENTATION_AND_MOVEMENT" for plan in rebound.plans))
    cache_before = slot.generations()
    runtime.tick_candidate_timers(0, 1)
    check("timer-cache-generations", slot.generations() == cache_before)
    roundtrip = catalog_from_dict(to_data(catalog))
    check("serialization-roundtrip", canonical_json_bytes(to_data(roundtrip)) == canonical_json_bytes(to_data(catalog)))
    check("stable-effective-hash", slot.composition.effective_hash == stable_hash("effective", slot.composition.semantic_output()))
    check("fixed-capacity-eight", MAX_RUNTIME_LAYERS == 8)

    # Atomic generation wrap and destructive reset preflight.
    wrap_runtime = StackRuntime(_fixture_catalog()[0])
    wrap_slot = wrap_runtime.install_slot(0, StaticContext(map_id=1))
    force_authenticated_layer_generation(wrap_runtime, wrap_slot, GEN_MAX)
    wrap_slot.effective_generation = GEN_MAX
    wrap_result = wrap_runtime.apply(0, 1, ids["owner_awareness"])
    check("generation-wrap-invalidates-before-atomic-commit", wrap_result.ok and wrap_slot.layer_generation == 1 and wrap_slot.effective_generation == 1 and {plan["action"] for plan in wrap_result.plans}.issuperset({"INVALIDATE_ACTIVE_STACK_PROVENANCE_AND_COMPOSITION_CACHES_FOR_WRAP", "INVALIDATE_EFFECTIVE_CAPABILITY_COMMAND_ORIGIN_CACHES_FOR_WRAP"}))
    rekey_runtime = StackRuntime(_fixture_catalog()[0])
    rekey_slot = rekey_runtime.install_slot(0, StaticContext(map_id=1))
    rekey_other = rekey_runtime.install_slot(1, StaticContext(map_id=1))
    old_rekey_handle = rekey_runtime.apply(0, 5, ids["owner_weather"]).operation_results[0].handle
    old_other_handle = rekey_runtime.apply(1, 1, ids["owner_awareness"]).operation_results[0].handle
    other_layer_generation = rekey_other.layer_generation
    rekey_slot.next_entry_generation = GEN_MAX
    rekey_result = rekey_runtime.apply(0, 5, ids["owner_script"])
    old_rekey_remove = rekey_runtime.remove(0, old_rekey_handle)
    old_other_remove = rekey_runtime.remove(1, old_other_handle)
    entry_rekey_ok = rekey_result.ok and rekey_runtime.runtime_epoch == 2 and len({layer.entry_generation for layer in rekey_slot.layers}) == len(rekey_slot.layers) and rekey_other.layer_generation == other_layer_generation + 1 and rekey_other.live and old_rekey_remove.status is Status.STALE_NOOP and old_other_remove.status is Status.STALE_NOOP
    timer_rekey_runtime = StackRuntime(_fixture_catalog()[0])
    timer_rekey_slot = timer_rekey_runtime.install_slot(0, StaticContext(map_id=1))
    timer_rekey_other = timer_rekey_runtime.install_slot(1, StaticContext(map_id=1))
    timer_rekey_runtime.apply(0, 5, ids["owner_weather"])
    timer_rekey_runtime.apply(1, 3, ids["owner_sleep"], 77)
    timer_rekey_runtime.tick_candidate_timers(1, 2)
    old_mandatory_plan = timer_rekey_runtime.pending_expiry_plans(1)[0]
    timer_rekey_slot.next_timer_generation = GEN_MAX
    timer_rekey_result = timer_rekey_runtime.apply(0, 3, ids["owner_sleep"], 88)
    new_mandatory_plan = timer_rekey_runtime.pending_expiry_plans(1)[0]
    stale_mandatory_plan = timer_rekey_runtime.commit_expiry(old_mandatory_plan)
    timer_rekey_ok = timer_rekey_result.ok and timer_rekey_runtime.runtime_epoch == 2 and timer_rekey_other.live and new_mandatory_plan["runtimeEpoch"] == 2 and canonical_json_bytes(new_mandatory_plan) != canonical_json_bytes(old_mandatory_plan) and stale_mandatory_plan.status is Status.STALE_NOOP
    check("entry-and-timer-wrap-rekey-every-live-slot-and-work", entry_rekey_ok and timer_rekey_ok)
    terminal_runtime = StackRuntime(_fixture_catalog()[0], runtime_epoch=GEN_MAX)
    terminal_slot = terminal_runtime.install_slot(0, StaticContext(map_id=1))
    terminal_other = terminal_runtime.install_slot(1, StaticContext(map_id=1))
    terminal_runtime.apply(1, 1, ids["owner_awareness"])
    terminal_slot.next_entry_generation = GEN_MAX
    terminal_result = terminal_runtime.apply(0, 1, ids["owner_awareness"])
    check("terminal-runtime-epoch-destructive-global-restart", terminal_result.status is Status.RUNTIME_EPOCH_RESTARTED and terminal_runtime.runtime_epoch == 1 and not terminal_slot.live and not terminal_other.live and terminal_slot.static is None and terminal_other.static is None)
    terminal_reject_runtime = StackRuntime(_fixture_catalog()[0], runtime_epoch=GEN_MAX)
    terminal_reject_slot = terminal_reject_runtime.install_slot(0, StaticContext(map_id=1))
    for index, owner_id in enumerate(range(300, 308)):
        terminal_reject_runtime.apply(0, 1200 + index, owner_id)
    terminal_reject_slot.next_entry_generation = GEN_MAX
    terminal_reject_before = semantic_slot_snapshot(terminal_reject_runtime)
    terminal_reject = terminal_reject_runtime.apply(0, 1208, 999)
    check("terminal-epoch-invalid-delta-rejects-before-global-invalidation", terminal_reject.status is Status.CAPACITY_EXCEEDED and terminal_reject_runtime.runtime_epoch == GEN_MAX and terminal_reject_slot.live and semantic_slot_snapshot(terminal_reject_runtime) == terminal_reject_before)
    destructive_runtime = StackRuntime(_fixture_catalog()[0], runtime_epoch=7)
    destructive_slot = destructive_runtime.install_slot(0, StaticContext(map_id=1), slot_generation=GEN_MAX)
    destructive_other = destructive_runtime.install_slot(1, StaticContext(map_id=1))
    destructive_other_handle = destructive_runtime.apply(1, 1, ids["owner_awareness"]).operation_results[0].handle
    destructive_runtime.destroy_slot(0)
    stale_other_after_destroy = destructive_runtime.remove(1, destructive_other_handle)
    check("slot-generation-wrap-rekeys-other-live-slots", destructive_runtime.runtime_epoch == 8 and not destructive_slot.live and destructive_slot.slot_generation == 1 and destructive_other.live and stale_other_after_destroy.status is Status.STALE_NOOP)
    terminal_destroy_runtime = StackRuntime(_fixture_catalog()[0], runtime_epoch=GEN_MAX)
    terminal_destroy_slot = terminal_destroy_runtime.install_slot(0, StaticContext(map_id=1), slot_generation=GEN_MAX)
    terminal_destroy_other = terminal_destroy_runtime.install_slot(1, StaticContext(map_id=1))
    terminal_destroy_runtime.apply(1, 3, ids["owner_sleep"], 77)
    terminal_destroy_runtime.destroy_slot(0)
    check("terminal-slot-wrap-destructive-world-restart", terminal_destroy_runtime.runtime_epoch == 1 and not terminal_destroy_slot.live and not terminal_destroy_other.live and terminal_destroy_slot.static is None and terminal_destroy_other.static is None and not terminal_destroy_other.timers)
    aba_runtime = StackRuntime(_fixture_catalog()[0])
    aba_inactive_slot = aba_runtime.install_slot(0, StaticContext(map_id=1))
    old_aba_handle = aba_runtime.apply(0, 1, ids["owner_awareness"]).operation_results[0].handle
    aba_runtime.destroy_slot(0)
    inactive_generation_before_terminal = aba_inactive_slot.slot_generation
    aba_trigger_slot = aba_runtime.install_slot(1, StaticContext(map_id=1))
    aba_runtime.runtime_epoch = GEN_MAX
    force_authenticated_layer_generation(aba_runtime, aba_trigger_slot, aba_trigger_slot.layer_generation)
    aba_trigger_slot.next_entry_generation = GEN_MAX
    aba_restart = aba_runtime.apply(1, 1, ids["owner_awareness"])
    inactive_generation_after_terminal = aba_inactive_slot.slot_generation
    aba_reinstalled = aba_runtime.install_slot(0, StaticContext(map_id=1), slot_generation=inactive_generation_after_terminal)
    new_aba_handle = aba_runtime.apply(0, 1, ids["owner_awareness"]).operation_results[0].handle
    check("fourth-terminal-epoch-rekeys-inactive-slots-and-handle-auth-no-aba", aba_restart.status is Status.RUNTIME_EPOCH_RESTARTED and inactive_generation_after_terminal != inactive_generation_before_terminal and old_aba_handle != new_aba_handle and aba_runtime.remove(0, old_aba_handle).status is Status.INVALID_HANDLE and aba_reinstalled.live)
    laundering_runtime = StackRuntime(_fixture_catalog()[0])
    laundering_trigger = laundering_runtime.install_slot(0, StaticContext(map_id=1))
    laundering_corrupt = laundering_runtime.install_slot(1, StaticContext(map_id=1))
    laundering_runtime.apply(1, 3, ids["owner_sleep"], 77)
    laundering_runtime.tick_candidate_timers(1, 2)
    corrupt_timer = laundering_corrupt.timers[(ids["owner_sleep"], 77)]
    corrupt_timer.timer_generation = 123
    corrupt_timer.expiry_plan_generation = 123
    laundering_trigger.next_entry_generation = GEN_MAX
    trigger_before = semantic_slot_snapshot(laundering_runtime, 0)
    corrupt_before = semantic_slot_snapshot(laundering_runtime, 1)
    laundering_result = laundering_runtime.apply(0, 1, ids["owner_awareness"])
    check("fourth-global-rekey-rejects-other-slot-corruption-without-laundering", laundering_result.status is Status.INVALID_HANDLE and laundering_runtime.runtime_epoch == 1 and semantic_slot_snapshot(laundering_runtime, 0) == trigger_before and semantic_slot_snapshot(laundering_runtime, 1) == corrupt_before and corrupt_timer.timer_generation == 123)

    # Expiry identity, replay resistance, indefinite timers, and gate semantics.
    replay_runtime = StackRuntime(_fixture_catalog()[0])
    replay_slot = replay_runtime.install_slot(0, StaticContext(map_id=1))
    replay_runtime.apply(0, 3, ids["owner_sleep"], 77)
    replay_runtime.tick_candidate_timers(0, 2)
    old_expiry = replay_runtime.pending_expiry_plans(0)[0]
    replay_runtime.destroy_slot(0)
    replay_slot = replay_runtime.install_slot(0, StaticContext(map_id=1), slot_generation=2)
    replay_runtime.apply(0, 3, ids["owner_sleep"], 77)
    replacement_entry = replay_slot.layers[0].entry_generation
    stale_expiry = replay_runtime.commit_expiry(old_expiry)
    check("expiry-replay-after-slot-reuse", stale_expiry.status is Status.STALE_NOOP and replay_slot.layers[0].entry_generation == replacement_entry)
    indefinite_runtime = StackRuntime(_fixture_catalog()[0])
    indefinite_slot = indefinite_runtime.install_slot(0, StaticContext(map_id=1))
    indefinite_runtime.apply(0, 13, ids["owner_sleep"], 88)
    indefinite_runtime.tick_candidate_timers(0, 200)
    zero_indefinite = indefinite_slot.timers[(ids["owner_sleep"], 88)].remaining_ticks == 255 and not indefinite_slot.timers[(ids["owner_sleep"], 88)].zero_pending
    literal_semantic_runtime = StackRuntime(_fixture_catalog()[0]); literal_semantic_slot = literal_semantic_runtime.install_slot(0, StaticContext(map_id=1))
    literal_semantic_runtime.apply(0, 15, ids["owner_sleep"])
    literal_exact_runtime = StackRuntime(_fixture_catalog()[0]); literal_exact_slot = literal_exact_runtime.install_slot(0, StaticContext(map_id=1))
    literal_exact_runtime.apply(0, 16, ids["owner_sleep"])
    literal_finite_runtime = StackRuntime(_fixture_catalog()[0]); literal_finite_slot = literal_finite_runtime.install_slot(0, StaticContext(map_id=1))
    literal_finite_runtime.apply(0, 17, ids["owner_awareness"])
    check("asleep-zero-sentinel-indefinite-and-literal-255-finite", zero_indefinite and literal_semantic_slot.timers[(ids["owner_sleep"], 0)].remaining_ticks == 254 and literal_exact_slot.timers[(ids["owner_sleep"], 0)].remaining_ticks == 254 and literal_finite_slot.timers[(ids["owner_awareness"], 0)].remaining_ticks == 254)
    authored_sources = resolve_static(_fixture_catalog()[0], StaticContext(map_id=1)).candidate_timer_sources
    folded_set_static = resolve_static(_fixture_catalog()[0], StaticContext(map_id=12))
    folded_add_static = resolve_static(_fixture_catalog()[0], StaticContext(map_id=13))
    folded_zero_static = resolve_static(_fixture_catalog()[0], StaticContext(map_id=14))
    folded_semantic_runtime = StackRuntime(_fixture_catalog()[0]); folded_semantic_slot = folded_semantic_runtime.install_slot(0, StaticContext(map_id=12)); folded_semantic_runtime.apply(0, 15, ids["owner_sleep"])
    folded_exact_runtime = StackRuntime(_fixture_catalog()[0]); folded_exact_slot = folded_exact_runtime.install_slot(0, StaticContext(map_id=12)); folded_exact_runtime.apply(0, 16, ids["owner_sleep"])
    check("timer-source-provenance-distinguishes-resolved-zero-from-literal-and-folded-255", all((
        authored_sources[13].indefinite and authored_sources[13].zero_derived and authored_sources[13].indefinite_origin == "AUTHORED_ASLEEP_ZERO",
        not authored_sources[15].indefinite and authored_sources[15].normalized_duration == 254,
        not authored_sources[16].indefinite and authored_sources[16].normalized_duration == 254,
        not folded_set_static.candidate_timer_sources[15].indefinite and folded_set_static.candidate_timer_sources[15].normalized_duration == 254,
        not folded_set_static.candidate_timer_sources[16].indefinite and folded_set_static.candidate_timer_sources[16].normalized_duration == 254,
        not folded_add_static.candidate_timer_sources[15].indefinite and folded_add_static.candidate_timer_sources[15].normalized_duration == 64,
        folded_zero_static.candidate_timer_sources[15].indefinite and folded_zero_static.candidate_timer_sources[15].normalized_duration == 255 and folded_zero_static.candidate_timer_sources[15].indefinite_origin == "STATIC_RESOLVED_ASLEEP_ZERO",
        folded_zero_static.candidate_timer_sources[16].indefinite and folded_zero_static.candidate_timer_sources[16].normalized_duration == 255,
        folded_semantic_slot.timers[(ids["owner_sleep"], 0)].remaining_ticks == 254,
        folded_exact_slot.timers[(ids["owner_sleep"], 0)].remaining_ticks == 254,
    )))
    static_zero_semantic_runtime = StackRuntime(_fixture_catalog()[0]); static_zero_semantic_slot = static_zero_semantic_runtime.install_slot(0, StaticContext(map_id=14)); static_zero_semantic_runtime.apply(0, 15, ids["owner_sleep"])
    static_zero_exact_runtime = StackRuntime(_fixture_catalog()[0]); static_zero_exact_slot = static_zero_exact_runtime.install_slot(0, StaticContext(map_id=14)); static_zero_exact_runtime.apply(0, 16, ids["owner_sleep"])
    static_zero_semantic_runtime.tick_candidate_timers(0, 40); static_zero_exact_runtime.tick_candidate_timers(0, 40)
    check("fourth-asleep-sentinel-only-resolved-zero-is-indefinite", static_zero_semantic_slot.timers[(ids["owner_sleep"], 0)].remaining_ticks == 255 and static_zero_exact_slot.timers[(ids["owner_sleep"], 0)].remaining_ticks == 255 and literal_semantic_slot.timers[(ids["owner_sleep"], 0)].remaining_ticks == 254 and literal_exact_slot.timers[(ids["owner_sleep"], 0)].remaining_ticks == 254)
    forced_runtime = StackRuntime(_fixture_catalog()[0])
    forced_slot = forced_runtime.install_slot(0, StaticContext(map_id=1))
    forced_runtime.apply(0, 3, ids["owner_sleep"], 77)
    forced_runtime.tick_candidate_timers(0, 2)
    forced_result = forced_runtime.commit_expiry(forced_runtime.pending_expiry_plans(0)[0])
    check("forced-sleep-remove-self-plan", forced_result.ok and not any(plan.get("action") in {"RESET_TIRED_RAM_CHAIN_COUNTERS_AND_PRESENTATION", "APPLY_POST_TIRED_MOVEMENT_COOLDOWN"} for plan in forced_result.plans))
    gate_runtime = StackRuntime(_fixture_catalog()[0])
    gate_slot = gate_runtime.install_slot(0, StaticContext(map_id=1))
    gate_runtime.apply(0, 12, ids["owner_script"])
    gate_runtime.set_presentation_gate(0, True)
    gate_runtime.apply(0, 2, ids["owner_stamina"])
    gate_timer = gate_slot.timers[(ids["owner_script"], 0)]
    override_rejected = raises_status(lambda: gate_runtime.tick_candidate_timers(0, 1, presentation_gate=False), Status.INVALID_HANDLE)
    held_during_gate = gate_timer.remaining_ticks == 3 and not gate_timer.zero_pending
    gate_release = gate_runtime.set_presentation_gate(0, False)
    released_gate_timer = gate_slot.timers[(ids["owner_script"], 0)]
    check("expire-on-hide-authoritative-presentation-gate", override_rejected and held_during_gate and released_gate_timer.remaining_ticks == 0 and released_gate_timer.zero_pending and gate_release["expireOnHide"][0]["beforeRemainingTicks"] == 3)

    # Authored timer sources and typed policy folds.
    timer_runtime = StackRuntime(_fixture_catalog()[0])
    timer_slot = timer_runtime.install_slot(0, StaticContext(map_id=4))
    timer_runtime.apply(0, 2, ids["owner_stamina"])
    duration_nine_runtime = StackRuntime(_fixture_catalog()[0]); duration_nine_slot = duration_nine_runtime.install_slot(0, StaticContext(map_id=4))
    duration_nine_runtime.apply(0, 14, ids["owner_script"])
    check("definition-scoped-timer-sources-sharing-tired-node", timer_slot.timers[(ids["owner_stamina"], 0)].remaining_ticks == 6 and duration_nine_slot.timers[(ids["owner_script"], 0)].remaining_ticks == 9 and timer_slot.static.candidate_timer_sources[2].normalized_duration == 6 and len(timer_slot.static.candidate_timer_sources[2].contributions) == 1 and timer_slot.static.candidate_timer_sources[14].normalized_duration == 9 and not timer_slot.static.candidate_timer_sources[14].contributions)
    check("typed-spawn-population-patches-and-static-hash", timer_slot.static.spawn_policy_values["minimumDistance"] == 2 and timer_slot.static.population_policy_values["limit"] == 3 and timer_slot.static.hash != resolve_static(timer_runtime.catalog, StaticContext(map_id=1)).hash)
    interleaved_static = resolve_static(timer_runtime.catalog, StaticContext(map_id=9))
    check("static-policy-bind-patch-total-order", interleaved_static.spawn_policy_id == 2 and interleaved_static.spawn_policy_values["minimumDistance"] == 3 and interleaved_static.population_policy_id == 2 and interleaved_static.population_policy_values["limit"] == 3)
    binding_static = resolve_static(timer_runtime.catalog, StaticContext(map_id=6))
    binding_record = next(item for item in binding_static.provenance["actions"] if item["kind"] == StaticActionKind.BIND_NODE.value)
    check("binding-provenance-before-after-payload", binding_record["before"] == 1 and binding_record["after"] == 11 and binding_record["payload"]["nodeId"] == 1)

    # Hidden-only cache behavior and retained creation-time policy identity.
    hidden_runtime = StackRuntime(_fixture_catalog()[0])
    hidden_slot = hidden_runtime.install_slot(0, StaticContext(map_id=1))
    hidden_runtime.apply(0, 4, ids["owner_pickup"])
    hidden_effective = (hidden_slot.composition.effective_hash, hidden_slot.effective_generation, hidden_slot.layer_generation)
    hidden_runtime.apply(0, 1, ids["owner_awareness"])
    check("hidden-lower-layer-generation-only", hidden_slot.composition.effective_hash == hidden_effective[0] and hidden_slot.effective_generation == hidden_effective[1] and hidden_slot.layer_generation == hidden_effective[2] + 1)
    immutable_cache_runtime = StackRuntime(_fixture_catalog()[0])
    immutable_cache_slot = immutable_cache_runtime.install_slot(0, StaticContext(map_id=1))
    immutable_cache_runtime.apply(0, 1, ids["owner_awareness"])
    cache_hashes_before = (immutable_cache_slot.static.hash, immutable_cache_slot.composition.effective_hash, immutable_cache_slot.composition.layer_hash)
    cache_generations_before = immutable_cache_slot.generations()
    immutable_binding = rejects_item_assignment(immutable_cache_slot.static.node_bindings, 1, 999)
    immutable_state = rejects_item_assignment(immutable_cache_slot.composition.state_values, "speed", 99)
    immutable_nested_provenance = False
    try:
        immutable_cache_slot.composition.provenance["state.speed"]["contributions"].append({"forged": True})
    except (AttributeError, TypeError):
        immutable_nested_provenance = True
    empty_cache_delta = immutable_cache_runtime.apply_stack_delta(0, immutable_cache_slot.slot_generation, (), "immutable-cache-empty-delta")
    check("fourth-published-static-and-composition-caches-are-deeply-immutable", immutable_binding and immutable_state and immutable_nested_provenance and empty_cache_delta.status is Status.IDEMPOTENT and cache_hashes_before == (immutable_cache_slot.static.hash, immutable_cache_slot.composition.effective_hash, immutable_cache_slot.composition.layer_hash) and cache_generations_before == immutable_cache_slot.generations() and immutable_cache_slot.composition.state_values["speed"] != 99)
    retained_runtime = StackRuntime(_fixture_catalog()[0])
    retained_slot = retained_runtime.install_slot(0, StaticContext(map_id=1))
    retained_runtime.apply(0, 1, ids["owner_awareness"])
    retained_result = retained_runtime.revalidate_retained_context(0, StaticContext(map_id=2))
    check("retained-creation-policy-preservation", retained_result.ok and retained_slot.static.spawn_policy_id == 2 and retained_slot.captured_spawn_policy_id == 1 and retained_slot.captured_population_policy_id == 1 and any(plan.get("wouldSelectSpawnPolicyId") == 2 for plan in retained_result.plans))
    retained_duration_runtime = StackRuntime(_fixture_catalog()[0])
    retained_duration_slot = retained_duration_runtime.install_slot(0, StaticContext(map_id=4))
    retained_duration_runtime.apply(0, 2, ids["owner_stamina"])
    retained_duration_timer = retained_duration_slot.timers[(ids["owner_stamina"], 0)]
    retained_duration_identity = (retained_duration_timer.entry_generation, retained_duration_timer.timer_generation, retained_duration_timer.expiry_plan_generation, retained_duration_slot.timer_allocations[(ids["owner_stamina"], 0)])
    retained_duration_result = retained_duration_runtime.revalidate_retained_context(0, StaticContext(map_id=1))
    retained_duration_after = retained_duration_slot.timers[(ids["owner_stamina"], 0)]
    check("fourth-retained-timer-keeps-running-value-above-destination-default", retained_duration_result.ok and retained_duration_after.remaining_ticks == 6 and retained_duration_identity == (retained_duration_after.entry_generation, retained_duration_after.timer_generation, retained_duration_after.expiry_plan_generation, retained_duration_slot.timer_allocations[(ids["owner_stamina"], 0)]))
    retained_runtime.destroy_slot(0)
    inactive_result = retained_runtime.revalidate_retained_context(0, StaticContext(map_id=3))
    check("destructive-reset-and-inactive-revalidation", inactive_result.status is Status.INACTIVE_SLOT and retained_slot.composition is None and not retained_slot.layers and not retained_slot.timers and not retained_slot.transition_history and retained_slot.diagnostics == SlotDiagnostics())
    destroyed_data = to_data(runtime_to_dict(retained_runtime))["slots"]["0"]
    check("destruction-redacts-static-context-policies-and-provenance", destroyed_data["static"] is None and destroyed_data["effective"] is None and destroyed_data["capturedSpawnPolicyId"] == 0 and destroyed_data["capturedPopulationPolicyId"] == 0 and destroyed_data["transitionHistory"] == [])

    # Generated family validation and corrupt runtime copies.
    generated_owners = {102: "stamina", 107: "battle-fled", 108: "ram-crash", 109: "throw-recovery"}
    generated_valid = True
    for offset, (family_name, origin, owner, recovery) in enumerate((("STAMINA", None, 102, RecoveryPolicy.LEGACY_RETURN_CALM), ("FLED", TiredOriginKind.FLED, 107, RecoveryPolicy.REMOVE_SELF), ("RAM_CRASH", TiredOriginKind.RAM_CRASH, 108, RecoveryPolicy.LEGACY_RETURN_CALM), ("THROW_RECOVERY", TiredOriginKind.THROW_RECOVERY, 109, RecoveryPolicy.LEGACY_RETURN_CALM))):
        family_spec = GENERATED_FAMILY_SPECS[family_name]
        meta = GeneratedMetadata(origin is not None, origin, True, owner)
        definition = OverrideDefinition(40000 + offset, DefinitionKind.STATE_CANDIDATE, Channel.TEMPORARY_EFFECT, family_spec["priority"], selector=NodeSelector.semantic(SemanticRole.TIRED), map_policy=LifetimePolicy.PRESERVE_LOGICAL, timer=CandidateTimerPolicy(family_spec["duration"], family_spec["clock"], family_spec["hidden_policy"], recovery, family_spec["calm_reset_owner_ids"], family_spec["recovery_transition_id"], family_spec["duration_policy"]), generated=meta)
        try:
            _validate_generated_definition(definition, generated_owners)
        except ModelError:
            generated_valid = False
    corrupt_mapping = OverrideDefinition(40010, DefinitionKind.STATE_CANDIDATE, Channel.TEMPORARY_EFFECT, 90, selector=NodeSelector.semantic(SemanticRole.TIRED), map_policy=LifetimePolicy.PRESERVE_LOGICAL, timer=CandidateTimerPolicy(4, recovery_policy=RecoveryPolicy.REMOVE_SELF), generated=GeneratedMetadata(True, TiredOriginKind.FLED, True, 108))
    check("generated-fled-ram-throw-stamina-closed-mappings", generated_valid and raises_status(lambda: _validate_generated_definition(corrupt_mapping, generated_owners), Status.INVALID_GENERATED_WRAPPER))
    corrupt_runtime = StackRuntime(_fixture_catalog()[0])
    corrupt_slot = corrupt_runtime.install_slot(0, StaticContext(map_id=1))
    corrupt_runtime.apply(0, 2, ids["owner_stamina"])
    corrupt_slot.layers[0] = dataclasses.replace(corrupt_slot.layers[0], generated=GeneratedMetadata())
    corrupt_before = semantic_slot_snapshot(corrupt_runtime)
    corrupt_replace = corrupt_runtime.replace(0, ids["owner_stamina"], 0, 2)
    check("corrupt-runtime-generated-metadata-rejected-not-repaired", corrupt_replace.status is Status.INVALID_GENERATED_WRAPPER and semantic_slot_snapshot(corrupt_runtime) == corrupt_before)

    # Every generated origin rebinds by logical family; stamina deliberately bypasses translation.
    rebind_ok = True
    for source_definition, owner_id, bound_target, unbound_target in (
        (8, ids["owner_fled"], 10, 9),
        (20, ids["owner_ram"], 21, 22),
        (30, ids["owner_throw"], 31, 32),
    ):
        family_runtime = StackRuntime(_fixture_catalog()[0])
        family_slot = family_runtime.install_slot(0, StaticContext(map_id=1))
        apply_result = family_runtime.apply(0, source_definition, owner_id)
        original_handle = apply_result.operation_results[0].handle
        original_timer = copy.deepcopy(family_slot.timers[(owner_id, 0)])
        bound_result = family_runtime.revalidate_retained_context(0, StaticContext(map_id=2))
        bound_ok = bound_result.ok and family_slot.layers[0].definition_id == bound_target
        unbound_result = family_runtime.revalidate_retained_context(0, StaticContext(map_id=10))
        rebind_ok = rebind_ok and bound_ok and unbound_result.ok and family_slot.layers[0].definition_id == unbound_target and family_runtime._make_handle(family_slot, family_slot.layers[0]) == original_handle and family_slot.timers[(owner_id, 0)] == original_timer
    stamina_bound_runtime = StackRuntime(_fixture_catalog()[0])
    stamina_bound_slot = stamina_bound_runtime.install_slot(0, StaticContext(map_id=1))
    stamina_bound_runtime.apply(0, 2, ids["owner_stamina"])
    stamina_bound = stamina_bound_runtime.revalidate_retained_context(0, StaticContext(map_id=2))
    stamina_bound_kept = stamina_bound.ok and len(stamina_bound_slot.layers) == 1 and stamina_bound_slot.layers[0].definition_id == 2
    stamina_unbound = stamina_bound_runtime.revalidate_retained_context(0, StaticContext(map_id=10))
    check("generated-fled-ram-throw-rebind-and-stamina-bypass", rebind_ok and stamina_bound_kept and stamina_unbound.ok and not stamina_bound_slot.layers)

    # Generated expiry emits definition/recovery-specific tired plans in monotonic phase order.
    recovery_ok = True
    phase_rank = {"PRECOMMIT": 0, "STABILIZE": 1, "COMMIT": 2, "POSTCOMMIT": 3, "DIAGNOSTIC": 4}
    for definition_id, owner_id, route_family, policy in (
        (2, ids["owner_stamina"], "STAMINA", RecoveryPolicy.LEGACY_RETURN_CALM),
        (8, ids["owner_fled"], "FLED", RecoveryPolicy.REMOVE_SELF),
        (20, ids["owner_ram"], "RAM_CRASH", RecoveryPolicy.LEGACY_RETURN_CALM),
        (30, ids["owner_throw"], "THROW_RECOVERY", RecoveryPolicy.LEGACY_RETURN_CALM),
    ):
        recovery_runtime = StackRuntime(_fixture_catalog()[0])
        recovery_runtime.install_slot(0, StaticContext(map_id=1))
        recovery_runtime.apply(0, definition_id, owner_id)
        recovery_runtime.tick_candidate_timers(0, 4)
        recovery_result = recovery_runtime.commit_expiry(recovery_runtime.pending_expiry_plans(0)[0])
        tired_plans = [plan for plan in recovery_result.plans if plan.get("routeFamily") == route_family]
        ranks = [phase_rank[plan["phase"]] for plan in recovery_result.plans]
        recovery_ok = recovery_ok and recovery_result.ok and ranks == sorted(ranks) and {plan["action"] for plan in tired_plans} == {"RESET_TIRED_RAM_CHAIN_COUNTERS_AND_PRESENTATION", "APPLY_POST_TIRED_MOVEMENT_COOLDOWN"} and all(plan["definitionId"] == definition_id and plan["recoveryPolicy"] == policy.value for plan in tired_plans)
    check("definition-specific-generated-recovery-plans-and-phase-order", recovery_ok)

    # Retained validation authenticates every mutable timer field before scratch translation.
    retained_timer_corruption_ok = True
    for definition_id, owner_id, corruption in (
        (8, ids["owner_fled"], "hidden"),
        (20, ids["owner_ram"], "duration"),
        (30, ids["owner_throw"], "generation"),
        (8, ids["owner_fled"], "identity"),
    ):
        validation_runtime = StackRuntime(_fixture_catalog()[0])
        validation_slot = validation_runtime.install_slot(0, StaticContext(map_id=1))
        validation_runtime.apply(0, definition_id, owner_id)
        timer_key = (owner_id, 0)
        timer = validation_slot.timers[timer_key]
        if corruption == "hidden":
            timer.hidden_policy = HiddenPolicy.CONTINUE_WHILE_HIDDEN
        elif corruption == "duration":
            timer.remaining_ticks = 5
        elif corruption == "generation":
            timer.timer_generation = 0
        else:
            timer.owner_id = owner_id + 1
        corrupt_snapshot = semantic_slot_snapshot(validation_runtime)
        validation_context = StaticContext(map_id=1 if corruption == "hidden" else 2)
        validation_result = validation_runtime.revalidate_retained_context(0, validation_context)
        retained_timer_corruption_ok = retained_timer_corruption_ok and not validation_result.ok and semantic_slot_snapshot(validation_runtime) == corrupt_snapshot
    check("retained-generated-timer-metadata-authentication", retained_timer_corruption_ok)
    forged_generation_ok = True
    for forged_field in ("timerGeneration", "expiryPlanGeneration"):
        forged_runtime = StackRuntime(_fixture_catalog()[0])
        forged_slot = forged_runtime.install_slot(0, StaticContext(map_id=1))
        forged_runtime.apply(0, 20, ids["owner_ram"])
        forged_timer = forged_slot.timers[(ids["owner_ram"], 0)]
        if forged_field == "timerGeneration":
            forged_timer.timer_generation += 1
        else:
            forged_timer.expiry_plan_generation += 1
        forged_before = semantic_slot_snapshot(forged_runtime)
        forged_result = forged_runtime.revalidate_retained_context(0, StaticContext(map_id=2))
        forged_generation_ok = forged_generation_ok and forged_result.status is Status.INVALID_HANDLE and semantic_slot_snapshot(forged_runtime) == forged_before
    forged_plan_runtime = StackRuntime(_fixture_catalog()[0])
    forged_plan_slot = forged_plan_runtime.install_slot(0, StaticContext(map_id=1))
    forged_plan_runtime.apply(0, 8, ids["owner_fled"])
    forged_plan_runtime.tick_candidate_timers(0, 4)
    forged_plan_key = (ids["owner_fled"], 0)
    authentic_plan = forged_plan_slot.mandatory_expiry_registry[forged_plan_key]
    forged_plan_slot.mandatory_expiry_registry = MappingProxyType({forged_plan_key: dataclasses.replace(authentic_plan, expiry_plan_generation=authentic_plan.expiry_plan_generation + 1)})
    forged_plan_before = semantic_slot_snapshot(forged_plan_runtime)
    forged_plan_result = forged_plan_runtime.revalidate_retained_context(0, StaticContext(map_id=2))
    check("retained-timer-generations-authenticate-allocation-entry-and-mandatory-plan", forged_generation_ok and forged_plan_result.status is Status.INVALID_HANDLE and semantic_slot_snapshot(forged_plan_runtime) == forged_plan_before)
    expiry_corrupt_runtime = StackRuntime(_fixture_catalog()[0])
    expiry_corrupt_slot = expiry_corrupt_runtime.install_slot(0, StaticContext(map_id=1))
    expiry_corrupt_runtime.apply(0, 8, ids["owner_fled"])
    expiry_corrupt_runtime.tick_candidate_timers(0, 4)
    captured_valid_expiry = expiry_corrupt_runtime.pending_expiry_plans(0)[0]
    expiry_corrupt_slot.layers[0] = dataclasses.replace(expiry_corrupt_slot.layers[0], generated=GeneratedMetadata())
    expiry_corrupt_before = semantic_slot_snapshot(expiry_corrupt_runtime)
    expiry_diagnostics_before = to_data(expiry_corrupt_slot.diagnostics)
    expiry_call_escaped = False
    try:
        expiry_corrupt_result = expiry_corrupt_runtime.commit_expiry(captured_valid_expiry)
    except ModelError:
        expiry_call_escaped = True
        expiry_corrupt_result = None
    check("fourth-commit-expiry-contains-corrupt-generated-runtime-as-typed-failure", not expiry_call_escaped and expiry_corrupt_result is not None and expiry_corrupt_result.status is Status.INVALID_GENERATED_WRAPPER and not expiry_corrupt_result.mutated and semantic_slot_snapshot(expiry_corrupt_runtime) == expiry_corrupt_before and to_data(expiry_corrupt_slot.diagnostics) == expiry_diagnostics_before)

    # Catalog/input validation and deterministic resolution under permutation.
    clean_catalog, _ = _fixture_catalog()
    clean_data = to_data(clean_catalog)
    source_map_ids = {50}
    source_species_ids = {7}
    source_terrains = {"GRASS"}
    source_extra_axis = [1]
    source_extras = {"axis": source_extra_axis}
    source_actions = [StaticAction(50, StaticActionKind.ASSIGN_CONTROLLER, assignment_priority=20, controller_id=20)]
    source_matcher = ContextMatcher(species_ids=source_species_ids, terrains=source_terrains, map_ids=source_map_ids, extras=source_extras)
    frozen_input_catalog = dataclasses.replace(clean_catalog, static_rules=clean_catalog.static_rules + (
        StaticRule(50, source_matcher, source_actions),  # type: ignore[arg-type]
    ))
    source_map_ids.clear(); source_map_ids.add(51)
    source_species_ids.clear(); source_species_ids.add(8)
    source_terrains.clear(); source_terrains.add("WATER")
    source_extra_axis.append(2); source_extras["new"] = True
    source_actions.clear()
    frozen_resolution = resolve_static(frozen_input_catalog, StaticContext(species_id=7, terrain="GRASS", map_id=50, extras={"axis": [1]}))
    check("deep-freeze-context-matcher-and-external-source-collections", frozen_resolution.controller_id == 20 and source_matcher.map_ids == frozenset({50}) and source_matcher.species_ids == frozenset({7}) and source_matcher.terrains == frozenset({"GRASS"}) and source_matcher.extras == {"axis": (1,)} and len(frozen_input_catalog.static_rules[-1].actions) == 1)
    duplicate_data = copy.deepcopy(clean_data)
    duplicate_profiles = list(duplicate_data["stateProfiles"].values())
    duplicate_data["stateProfiles"] = duplicate_profiles + [copy.deepcopy(duplicate_profiles[0])]
    invalid_domain = copy.deepcopy(clean_data)
    invalid_domain["stateProfiles"]["1"]["speed"] = 9
    invalid_union = copy.deepcopy(clean_data)
    invalid_union["definitions"]["1"]["modifierId"] = 1
    invalid_union["definitions"]["1"]["applicability"]["stateProfileIds"] = [1]
    dangling_selector = copy.deepcopy(clean_data)
    dangling_selector["definitions"]["1"]["selector"] = {"kind": "EXACT", "controllerId": 10, "nodeId": 999}
    missing_ref = copy.deepcopy(clean_data)
    missing_ref["controllers"]["10"]["spawnPolicyId"] = 999
    check("catalog-duplicate-domain-union-selector-reference-validation", all((
        raises_status(lambda: catalog_from_dict(duplicate_data), Status.INVALID_STATIC_DATA),
        raises_status(lambda: catalog_from_dict(invalid_domain), Status.INVALID_STATIC_DATA),
        raises_status(lambda: catalog_from_dict(invalid_union), Status.INVALID_STATIC_DATA),
        raises_status(lambda: catalog_from_dict(dangling_selector), Status.INVALID_STATIC_DATA),
        raises_status(lambda: catalog_from_dict(missing_ref), Status.INVALID_STATIC_DATA),
    )))
    u8_priority = copy.deepcopy(clean_data)
    u8_priority["definitions"]["1"]["priority"] = 256
    check("definition-priority-is-u8-not-u16", raises_status(lambda: catalog_from_dict(u8_priority), Status.INVALID_STATIC_DATA))
    truthy_origin_tag = copy.deepcopy(clean_data)
    truthy_origin_tag["definitions"]["8"]["generated"]["hasTiredOriginKind"] = 2
    numeric_owner_tag = copy.deepcopy(clean_data)
    numeric_owner_tag["definitions"]["8"]["generated"]["hasRequiredOwnerId"] = 1
    check("generated-presence-tags-require-canonical-booleans", raises_status(lambda: catalog_from_dict(truthy_origin_tag), Status.INVALID_GENERATED_WRAPPER) and raises_status(lambda: catalog_from_dict(numeric_owner_tag), Status.INVALID_GENERATED_WRAPPER))
    exact_union_payload = copy.deepcopy(clean_data)
    exact_union_payload["definitions"]["9"]["selector"]["role"] = "CUSTOM"
    noncustom_custom_id = copy.deepcopy(clean_data)
    noncustom_custom_id["definitions"]["1"]["selector"]["customRoleId"] = 1
    custom_id_too_large = copy.deepcopy(clean_data)
    custom_id_too_large["definitions"]["1"]["selector"] = {"kind": "SEMANTIC", "role": "CUSTOM", "customRoleId": 65536}
    custom_id_negative = copy.deepcopy(clean_data)
    custom_id_negative["definitions"]["1"]["selector"] = {"kind": "SEMANTIC", "role": "CUSTOM", "customRoleId": -1}
    semantic_exact_payload = copy.deepcopy(clean_data)
    semantic_exact_payload["definitions"]["1"]["selector"]["controllerId"] = 10
    check("node-selector-custom-role-tagged-union-and-u16-domain", all((
        raises_status(lambda: catalog_from_dict(exact_union_payload), Status.INVALID_STATIC_DATA),
        raises_status(lambda: catalog_from_dict(noncustom_custom_id), Status.INVALID_STATIC_DATA),
        raises_status(lambda: catalog_from_dict(custom_id_too_large), Status.INVALID_STATIC_DATA),
        raises_status(lambda: catalog_from_dict(custom_id_negative), Status.INVALID_STATIC_DATA),
        raises_status(lambda: catalog_from_dict(semantic_exact_payload), Status.INVALID_STATIC_DATA),
    )))
    missing_throw_family = copy.deepcopy(clean_data)
    for definition_id in (30, 31, 32, 33):
        del missing_throw_family["definitions"][str(definition_id)]
    missing_throw_family["tiredTranslations"] = [row for row in missing_throw_family["tiredTranslations"] if row["origin"] != "THROW_RECOVERY"]
    check("phase-zero-generated-families-are-closed-and-mandatory", raises_status(lambda: catalog_from_dict(missing_throw_family), Status.INVALID_GENERATED_WRAPPER))
    unbound_fallback = copy.deepcopy(clean_data)
    unbound_fallback["staticRules"].append({
        "stableId": 100, "matcher": {"mapIds": [50]},
        "actions": [{"stableId": 100, "kind": "UNBIND_NODE", "staticPriority": 1, "controllerId": 20, "nodeId": 15}],
    })
    fallback_runtime = StackRuntime(clean_catalog)
    fallback_slot = fallback_runtime.install_slot(0, StaticContext(map_id=1))
    fallback_runtime.apply(0, 8, ids["owner_fled"])
    fallback_rebind = fallback_runtime.revalidate_retained_context(0, StaticContext(map_id=10))
    check("imperative-fallback-remains-bound-in-all-false-contexts", raises_status(lambda: catalog_from_dict(unbound_fallback), Status.INVALID_TRANSLATION) and fallback_rebind.ok and len(fallback_slot.layers) == 1 and fallback_slot.layers[0].definition_id == 9)
    rebound_fallback_profile = copy.deepcopy(clean_data)
    next(rule for rule in rebound_fallback_profile["staticRules"] if rule["stableId"] == 7)["actions"].append({"stableId": 100, "kind": "BIND_NODE", "staticPriority": 2, "controllerId": 20, "nodeId": 15, "profileId": 1})
    filtered_fallback_definition = copy.deepcopy(clean_data)
    filtered_fallback_definition["definitions"]["9"]["applicability"]["context"] = {"mapIds": [2]}
    check("fourth-fallback-closure-rejects-profile-rebind-and-context-filter", raises_status(lambda: catalog_from_dict(rebound_fallback_profile), Status.INVALID_TRANSLATION) and raises_status(lambda: catalog_from_dict(filtered_fallback_definition), Status.INVALID_TRANSLATION))
    extra_generated_wrapper = copy.deepcopy(clean_data)
    extra_generated_wrapper["definitions"]["1000"] = copy.deepcopy(extra_generated_wrapper["definitions"]["8"])
    extra_generated_wrapper["definitions"]["1000"]["stableId"] = 1000
    wrong_generated_channel = copy.deepcopy(clean_data); wrong_generated_channel["definitions"]["8"]["channel"] = "SYSTEM_SAFETY"
    wrong_generated_priority = copy.deepcopy(clean_data); wrong_generated_priority["definitions"]["10"]["priority"] = 91
    split_generated_owner = copy.deepcopy(clean_data); split_generated_owner["definitions"]["8"]["generated"]["requiredOwnerId"] = ids["owner_ram"]
    duplicate_owner_display = copy.deepcopy(clean_data); duplicate_owner_display["ownerNames"]["999"] = "battle-fled"
    inconsistent_generated_timer = copy.deepcopy(clean_data); inconsistent_generated_timer["definitions"]["10"]["timer"]["duration"] = 5
    extraneous_generated_translation = copy.deepcopy(clean_data); extraneous_generated_translation["tiredTranslations"].append(copy.deepcopy(extraneous_generated_translation["tiredTranslations"][0]))
    check("fourth-generated-family-registry-is-exact-and-closed", all((
        raises_status(lambda: catalog_from_dict(extra_generated_wrapper), Status.INVALID_GENERATED_WRAPPER),
        raises_status(lambda: catalog_from_dict(wrong_generated_channel), Status.INVALID_GENERATED_WRAPPER),
        raises_status(lambda: catalog_from_dict(wrong_generated_priority), Status.INVALID_GENERATED_WRAPPER),
        raises_status(lambda: catalog_from_dict(split_generated_owner), Status.INVALID_GENERATED_WRAPPER),
        raises_status(lambda: catalog_from_dict(duplicate_owner_display), Status.INVALID_GENERATED_WRAPPER),
        raises_status(lambda: catalog_from_dict(inconsistent_generated_timer), Status.INVALID_GENERATED_WRAPPER),
        raises_status(lambda: catalog_from_dict(extraneous_generated_translation), Status.INVALID_STATIC_DATA),
    )))
    missing_translation = copy.deepcopy(clean_data)
    missing_translation["tiredTranslations"] = [row for row in missing_translation["tiredTranslations"] if not (row["destinationControllerId"] == 10 and row["authoredTiredBound"])]
    equal_assignment = copy.deepcopy(clean_data)
    assignment_rule = next(rule for rule in equal_assignment["staticRules"] if rule["stableId"] == 1)
    assignment_rule["actions"].append(copy.deepcopy(assignment_rule["actions"][0]))
    check("translation-coverage-and-equal-assignment-key-validation", raises_status(lambda: catalog_from_dict(missing_translation), Status.INVALID_TRANSLATION) and raises_status(lambda: catalog_from_dict(equal_assignment), Status.INVALID_STATIC_DATA))
    noncanonical_origin = copy.deepcopy(clean_data)
    noncanonical_origin["definitions"]["1"]["generated"] = {"hasTiredOriginKind": False, "tiredOriginKind": "FLED", "hasRequiredOwnerId": False, "requiredOwnerId": 0}
    oversized_priority = copy.deepcopy(clean_data)
    oversized_priority["definitions"]["1"]["priority"] = 0x10000
    oversized_static_priority = copy.deepcopy(clean_data)
    next(rule for rule in oversized_static_priority["staticRules"] if rule["stableId"] == 3)["actions"][0]["staticPriority"] = 0x10000
    oversized_stable_id = copy.deepcopy(clean_data)
    oversized_stable_id["definitions"]["1"]["stableId"] = 0x10000
    ordinary_system_safety = copy.deepcopy(clean_data)
    ordinary_system_safety["definitions"]["1"]["channel"] = "SYSTEM_SAFETY"
    invalid_owner_registry = copy.deepcopy(clean_data)
    invalid_owner_registry["ownerNames"]["0"] = "invalid-owner"
    check("canonical-generated-tags-u16-identities-priorities-and-system-safety", all((
        raises_status(lambda: catalog_from_dict(noncanonical_origin), Status.INVALID_GENERATED_WRAPPER),
        raises_status(lambda: catalog_from_dict(oversized_priority), Status.INVALID_STATIC_DATA),
        raises_status(lambda: catalog_from_dict(oversized_static_priority), Status.INVALID_STATIC_DATA),
        raises_status(lambda: catalog_from_dict(oversized_stable_id), Status.INVALID_STATIC_DATA),
        raises_status(lambda: catalog_from_dict(ordinary_system_safety), Status.INVALID_STATIC_DATA),
        raises_status(lambda: catalog_from_dict(invalid_owner_registry), Status.INVALID_STATIC_DATA),
    )))
    permuted = copy.deepcopy(clean_data)
    permuted["staticRules"].reverse()
    for rule in permuted["staticRules"]:
        rule["actions"].reverse()
    permuted_catalog = catalog_from_dict(permuted)
    original_static = resolve_static(clean_catalog, StaticContext(map_id=4))
    permuted_static = resolve_static(permuted_catalog, StaticContext(map_id=4))
    original_interleaved = resolve_static(clean_catalog, StaticContext(map_id=9))
    permuted_interleaved = resolve_static(permuted_catalog, StaticContext(map_id=9))
    check("serialized-permutation-determinism", original_static.hash == permuted_static.hash and original_interleaved.hash == permuted_interleaved.hash and original_interleaved.spawn_policy_values == permuted_interleaved.spawn_policy_values and original_interleaved.population_policy_values == permuted_interleaved.population_policy_values and compose(clean_catalog, original_static, ()).effective_hash == compose(permuted_catalog, permuted_static, ()).effective_hash)

    immutable_catalog, _ = _fixture_catalog()
    immutable_registry = rejects_item_assignment(immutable_catalog.definitions, 1, immutable_catalog.definitions[1])
    immutable_operations = rejects_item_assignment(immutable_catalog.modifiers[1].operations, "state.speed", ModifierOperation(OperatorKind.SET, 1))
    immutable_context = StaticContext(extras={"nested": [1, 2]})
    immutable_nested = isinstance(immutable_context.extras["nested"], tuple)
    install_runtime = StackRuntime(immutable_catalog)
    install_runtime.install_slot(0, StaticContext(map_id=1))
    install_runtime.stage_catalog(_fixture_catalog()[0])
    busy_install = raises_status(install_runtime.install_staged_catalog, Status.DATA_BUSY)
    busy_generation = install_runtime.data_generation == 1 and install_runtime.slots[0].live
    install_runtime.destroy_slot(0)
    installed_generation = install_runtime.install_staged_catalog()
    stale_data_context = raises_status(lambda: install_runtime.install_slot(0, StaticContext(map_id=1)), Status.INVALID_STATIC_DATA)
    force_authenticated_data_generation(install_runtime, GEN_MAX)
    install_runtime.stage_catalog(_fixture_catalog()[0])
    restarted_data_generation = install_runtime.install_staged_catalog()
    check("deep-catalog-immutability-and-cold-staged-install", immutable_registry and immutable_operations and immutable_nested and busy_install and busy_generation and installed_generation == 2 and stale_data_context and len(install_runtime.slots) == install_runtime.slot_count and all(not item.live for item in install_runtime.slots.values()) and restarted_data_generation == 1)
    bytearray_operand = copy.deepcopy(clean_data)
    bytearray_operand["modifiers"]["1"]["operations"]["state.speed"]["value"] = bytearray(b"1")
    string_operator_operand = copy.deepcopy(clean_data)
    string_operator_operand["modifiers"]["1"]["operations"]["state.speed"]["value"] = "-1"
    mutable_extra_source = [1]
    copied_mutable_extra = ContextMatcher(extras={"axis": mutable_extra_source})
    mutable_extra_source.append(2)
    check("fourth-deep-freeze-rejects-mutable-leaves-and-early-scalar-coercion", all((
        raises_status(lambda: catalog_from_dict(bytearray_operand), Status.INVALID_STATIC_DATA),
        raises_status(lambda: ContextMatcher(extras={"blob": bytearray(b"x")}), Status.INVALID_STATIC_DATA),
        raises_status(lambda: catalog_from_dict(string_operator_operand), Status.INVALID_MODIFIER),
        copied_mutable_extra.extras["axis"] == (1,),
    )))
    activation_runtime = StackRuntime(clean_catalog)
    staged_activation_catalog = _fixture_catalog()[0]
    direct_catalog_assignment = rejects_attribute_assignment(activation_runtime, "catalog", staged_activation_catalog)
    activation_runtime.stage_catalog(staged_activation_catalog)
    activation_generation = activation_runtime.install_staged_catalog()
    check("runtime-catalog-is-private-and-cold-install-is-sole-activation", direct_catalog_assignment and not hasattr(activation_runtime, "replace_catalog") and activation_generation == 2 and activation_runtime.catalog is staged_activation_catalog and len(activation_runtime.slots) == activation_runtime.slot_count and all(not item.live for item in activation_runtime.slots.values()))

    # Public identities, JSON boundary, policy ambiguity, and diagnostic order.
    identity_runtime = StackRuntime(_fixture_catalog()[0])
    identity_slot = identity_runtime.install_slot(0, StaticContext(map_id=1))
    bad_owner = identity_runtime.apply(0, 1, 0)
    bad_instance = identity_runtime.apply(0, 1, ids["owner_awareness"], 0x10000)
    json_collision = raises_status(lambda: to_data({1: "numeric", "1": "text"}), Status.INVALID_STATIC_DATA)
    compose_missing_metadata = {"catalog": clean_data, "context": {"mapId": 1}, "layers": [{"definitionId": 1, "ownerId": ids["owner_awareness"], "instanceKey": 0, "entryGeneration": 1}]}
    compose_bad_generation = copy.deepcopy(compose_missing_metadata)
    compose_bad_generation["layers"][0]["generated"] = to_data(clean_catalog.definitions[1].generated)
    compose_bad_generation["layers"][0]["entryGeneration"] = 0
    check("malformed-runtime-compose-identities-and-json-key-collision", bad_owner.status is Status.INVALID_HANDLE and bad_instance.status is Status.INVALID_HANDLE and not identity_slot.layers and json_collision and raises_status(lambda: _compose_request(compose_missing_metadata), Status.INVALID_HANDLE) and raises_status(lambda: _compose_request(compose_bad_generation), Status.INVALID_HANDLE))
    strict_runtime = StackRuntime(_fixture_catalog()[0]); strict_slot = strict_runtime.install_slot(0, StaticContext(map_id=1))
    bool_apply = strict_runtime.apply(0, True, True, False)
    valid_strict_handle = strict_runtime.apply(0, 1, ids["owner_awareness"]).operation_results[0].handle
    valid_handle_data = to_data(valid_strict_handle)
    valid_handle_roundtrip = Handle.from_dict(valid_handle_data)
    string_priority = copy.deepcopy(clean_data); string_priority["definitions"]["1"]["priority"] = "1"
    fractional_priority = copy.deepcopy(clean_data); fractional_priority["definitions"]["1"]["priority"] = 1.5
    bool_priority = copy.deepcopy(clean_data); bool_priority["definitions"]["1"]["priority"] = True
    string_handle_generation = copy.deepcopy(valid_handle_data); string_handle_generation["entryGeneration"] = str(string_handle_generation["entryGeneration"])
    check("fourth-typed-scalars-reject-bool-string-fraction-and-handle-roundtrips", bool_apply.status is Status.INVALID_HANDLE and len(strict_slot.layers) == 1 and all((
        raises_status(lambda: catalog_from_dict(string_priority), Status.INVALID_STATIC_DATA),
        raises_status(lambda: catalog_from_dict(fractional_priority), Status.INVALID_STATIC_DATA),
        raises_status(lambda: catalog_from_dict(bool_priority), Status.INVALID_STATIC_DATA),
        raises_status(lambda: Handle.from_dict(string_handle_generation), Status.INVALID_HANDLE),
    )) and valid_handle_roundtrip == valid_strict_handle and canonical_json_bytes(valid_handle_roundtrip) == canonical_json_bytes(valid_strict_handle))
    identity_runtime.apply(0, 1, ids["owner_awareness"])
    policy_before = semantic_slot_snapshot(identity_runtime)
    policy_ambiguous = identity_runtime.apply_stack_delta(0, identity_slot.slot_generation, (
        identity_runtime.bind_delta_operation(DeltaOperation.remove_owner_if_present("owner", ids["owner_awareness"])),
        identity_runtime.bind_delta_operation(DeltaOperation("policy", DeltaOpKind.REMOVE_POLICY, policy=LifetimePolicy.PRESERVE_LOGICAL)),
    ), "policy-overlap")
    check("remove-policy-intersection-ambiguity", policy_ambiguous.status is Status.AMBIGUOUS_DELTA and semantic_slot_snapshot(identity_runtime) == policy_before)
    diag_a = StackRuntime(_fixture_catalog()[0], handle_secret="diagnostic-order", runtime_nonce="diagnostic-order-a"); diag_a.install_slot(0, StaticContext(map_id=1))
    diag_b = StackRuntime(_fixture_catalog()[0], handle_secret="diagnostic-order", runtime_nonce="diagnostic-order-a"); diag_b.install_slot(0, StaticContext(map_id=1))
    operations = (diag_a.bind_delta_operation(DeltaOperation.apply("b", 65535, 200)), diag_a.bind_delta_operation(DeltaOperation.apply("a", 1, 0)))
    result_a = diag_a.apply_stack_delta(0, 1, operations, "diagnostic-order")
    operations_b = tuple(diag_b.bind_delta_operation(dataclasses.replace(operation, runtime_incarnation="", data_generation=0, data_incarnation="")) for operation in reversed(operations))
    result_b = diag_b.apply_stack_delta(0, 1, operations_b, "diagnostic-order")
    check("failure-diagnostic-input-order-invariance", result_a.status is result_b.status and to_data(diag_a.slots[0].diagnostics) == to_data(diag_b.slots[0].diagnostics) and semantic_slot_snapshot(diag_a) == semantic_slot_snapshot(diag_b))

    # Fifth-pass adversarial reproductions: authenticated incarnations, strict
    # discriminants, armed timer provenance, and mutation-free public failure.
    plan_aba_runtime = StackRuntime(_fixture_catalog()[0])
    plan_aba_slot = plan_aba_runtime.install_slot(0, StaticContext(map_id=1))
    plan_aba_runtime.apply(0, 3, ids["owner_sleep"], 77)
    plan_aba_runtime.tick_candidate_timers(0, 2)
    plan_a = ExpiryPlan.from_dict(plan_aba_runtime.pending_expiry_plans(0)[0])
    old_runtime_incarnation = plan_aba_runtime.runtime_incarnation
    plan_aba_runtime.runtime_epoch = GEN_MAX
    plan_aba_slot.slot_generation = GEN_MAX
    force_authenticated_layer_generation(plan_aba_runtime, plan_aba_slot, plan_aba_slot.layer_generation)
    plan_aba_slot.next_entry_generation = GEN_MAX
    plan_aba_slot.transition_history = deque(maxlen=16)
    plan_aba_slot.captured_policy_authenticator = plan_aba_runtime._captured_policy_authenticator(plan_aba_slot)
    plan_aba_slot.installed_context_authenticator = plan_aba_runtime._installed_context_authenticator(plan_aba_slot)
    plan_aba_slot.retained_context_authenticators = (plan_aba_slot.installed_context_authenticator,)
    for plan_aba_timer in plan_aba_slot.timers.values():
        plan_aba_timer.armed_context_authenticator = plan_aba_slot.installed_context_authenticator
        plan_aba_runtime._sign_timer_allocation(plan_aba_slot, plan_aba_timer)
    plan_aba_slot.timer_allocations = _timer_allocation_registry(plan_aba_slot.timers)
    plan_aba_slot.mandatory_expiry_registry = _mandatory_expiry_registry(
        plan_aba_runtime.runtime_epoch, plan_aba_runtime.runtime_incarnation,
        plan_aba_runtime.data_generation, plan_aba_runtime.data_incarnation,
        plan_aba_slot.slot_index, plan_aba_slot.slot_generation, plan_aba_slot.timers, plan_aba_runtime._secret,
        layers=plan_aba_slot.layers, static=plan_aba_slot.static, catalog=plan_aba_runtime.catalog,
        static_context_generation=plan_aba_slot.static_context_generation,
        static_context_incarnation=plan_aba_slot.static_context_incarnation,
        layer_generation=plan_aba_slot.layer_generation,
        layer_incarnation=plan_aba_slot.layer_incarnation,
    )
    terminal_plan_restart = plan_aba_runtime.apply(0, 5, ids["owner_weather"])
    plan_aba_runtime.install_slot(0, StaticContext(map_id=1), slot_generation=1)
    plan_aba_runtime.apply(0, 3, ids["owner_sleep"], 77)
    plan_aba_runtime.tick_candidate_timers(0, 2)
    plan_b = ExpiryPlan.from_dict(plan_aba_runtime.pending_expiry_plans(0)[0])
    plan_b_before = semantic_slot_snapshot(plan_aba_runtime)
    stale_plan_a = plan_aba_runtime.commit_expiry(plan_a)
    reused_numeric_identity = (
        plan_a.runtime_epoch, plan_a.slot_index, plan_a.slot_generation, plan_a.owner_id,
        plan_a.instance_key, plan_a.entry_generation, plan_a.timer_generation,
        plan_a.expiry_plan_generation,
    ) == (
        plan_b.runtime_epoch, plan_b.slot_index, plan_b.slot_generation, plan_b.owner_id,
        plan_b.instance_key, plan_b.entry_generation, plan_b.timer_generation,
        plan_b.expiry_plan_generation,
    )
    check("fifth-expiry-plan-incarnation-prevents-terminal-epoch-aba", terminal_plan_restart.status is Status.RUNTIME_EPOCH_RESTARTED and old_runtime_incarnation != plan_aba_runtime.runtime_incarnation and plan_a != plan_b and reused_numeric_identity and stale_plan_a.status is Status.STALE_NOOP and semantic_slot_snapshot(plan_aba_runtime) == plan_b_before and plan_aba_runtime.pending_expiry_plans(0))

    string_kind_runtime = StackRuntime(_fixture_catalog()[0])
    string_kind_slot = string_kind_runtime.install_slot(0, StaticContext(map_id=1))
    first_kind_handle = string_kind_runtime.apply(0, 1, ids["owner_awareness"]).operation_results[0].handle
    string_kind_runtime.replace(0, ids["owner_awareness"], 0, 1)
    string_kind_before = semantic_slot_snapshot(string_kind_runtime)
    malformed_required = DeltaOperation("stale-string", "REMOVE_REQUIRED", handle=first_kind_handle)  # type: ignore[arg-type]
    string_kind_result = string_kind_runtime.apply_stack_delta(0, string_kind_slot.slot_generation, (malformed_required, string_kind_runtime.bind_delta_operation(DeltaOperation.apply("valid-apply", 5, ids["owner_weather"]))), "string-kind-atomic")
    check("fifth-string-delta-kind-cannot-bypass-required-removal", string_kind_result.status is Status.INVALID_HANDLE and semantic_slot_snapshot(string_kind_runtime) == string_kind_before and all(layer.owner_id != ids["owner_weather"] for layer in string_kind_slot.layers))

    terminal_corrupt_runtime = StackRuntime(_fixture_catalog()[0], slot_count=2, runtime_epoch=GEN_MAX)
    terminal_trigger_slot = terminal_corrupt_runtime.install_slot(0, StaticContext(map_id=1))
    terminal_other_slot = terminal_corrupt_runtime.install_slot(1, StaticContext(map_id=1))
    terminal_trigger_slot.next_entry_generation = GEN_MAX
    terminal_other_slot.composition = dataclasses.replace(terminal_other_slot.composition, effective_hash="effective:forged-other-slot")
    terminal_corrupt_before = (semantic_slot_snapshot(terminal_corrupt_runtime, 0), semantic_slot_snapshot(terminal_corrupt_runtime, 1))
    terminal_corrupt_result = terminal_corrupt_runtime.apply(0, 1, ids["owner_awareness"])
    check("fifth-terminal-restart-rejects-other-slot-corruption-atomically", terminal_corrupt_result.status is Status.INVALID_COMPOSITION and terminal_corrupt_runtime.runtime_epoch == GEN_MAX and terminal_corrupt_runtime.slots[0].live and terminal_corrupt_runtime.slots[1].live and terminal_corrupt_before == (semantic_slot_snapshot(terminal_corrupt_runtime, 0), semantic_slot_snapshot(terminal_corrupt_runtime, 1)))

    expiry_cache_runtime = StackRuntime(_fixture_catalog()[0])
    expiry_cache_slot = expiry_cache_runtime.install_slot(0, StaticContext(map_id=1))
    expiry_cache_runtime.apply(0, 3, ids["owner_sleep"], 77)
    expiry_cache_runtime.tick_candidate_timers(0, 2)
    expiry_cache_plan = expiry_cache_runtime.pending_expiry_plans(0)[0]
    expiry_cache_slot.composition = dataclasses.replace(expiry_cache_slot.composition, effective_hash="effective:forged-expiry-cache")
    expiry_cache_before = semantic_slot_snapshot(expiry_cache_runtime)
    expiry_cache_result = expiry_cache_runtime.commit_expiry(expiry_cache_plan)
    check("fifth-expiry-authenticates-complete-static-and-composition-cache", expiry_cache_result.status is Status.INVALID_COMPOSITION and not expiry_cache_result.ok and semantic_slot_snapshot(expiry_cache_runtime) == expiry_cache_before and len(expiry_cache_slot.layers) == 1)

    explicit_timer_data = copy.deepcopy(clean_data)
    explicit_timer_data["definitions"]["13"]["timer"]["duration"] = 255
    explicit_timer_data["definitions"]["13"]["timer"]["durationPolicy"] = TimerDurationPolicy.INDEFINITE.value
    exact_indefinite = copy.deepcopy(explicit_timer_data["definitions"]["16"])
    exact_indefinite["stableId"] = 18
    exact_indefinite["priority"] = 213
    exact_indefinite["timer"]["duration"] = 255
    exact_indefinite["timer"]["durationPolicy"] = TimerDurationPolicy.INDEFINITE.value
    explicit_timer_data["definitions"]["18"] = exact_indefinite
    explicit_timer_catalog = catalog_from_dict(explicit_timer_data)
    explicit_static = resolve_static(explicit_timer_catalog, StaticContext(map_id=1))
    explicit_runtime = StackRuntime(explicit_timer_catalog)
    explicit_runtime.install_slot(0, StaticContext(map_id=1))
    explicit_runtime.apply(0, 13, ids["owner_sleep"], 1)
    finite_zero_data = copy.deepcopy(clean_data)
    finite_zero_data["definitions"]["13"]["timer"]["duration"] = 0
    finite_zero_data["definitions"]["13"]["timer"]["durationPolicy"] = TimerDurationPolicy.FINITE.value
    finite_zero_catalog = catalog_from_dict(finite_zero_data)
    finite_zero_runtime = StackRuntime(finite_zero_catalog)
    finite_zero_runtime.install_slot(0, StaticContext(map_id=1))
    finite_zero_runtime.apply(0, 13, ids["owner_sleep"], 2)
    unknown_indefinite = copy.deepcopy(finite_zero_data); unknown_indefinite["definitions"]["13"]["timer"]["durationPolicy"] = "FOREVER_IF_TRUTHY"
    unknown_indefinite_field = copy.deepcopy(finite_zero_data); unknown_indefinite_field["definitions"]["13"]["timer"]["indefinite"] = True
    invalid_indefinite = copy.deepcopy(finite_zero_data); invalid_indefinite["definitions"]["13"]["timer"]["duration"] = 0; invalid_indefinite["definitions"]["13"]["timer"]["durationPolicy"] = TimerDurationPolicy.INDEFINITE.value
    check("fifth-explicit-indefinite-policy-distinguishes-legacy-and-finite-zero", explicit_static.candidate_timer_sources[13].indefinite and explicit_static.candidate_timer_sources[13].indefinite_origin == "EXPLICIT_INDEFINITE" and explicit_static.candidate_timer_sources[18].indefinite and explicit_runtime.slots[0].timers[(ids["owner_sleep"], 1)].remaining_ticks == 255 and finite_zero_runtime.slots[0].timers[(ids["owner_sleep"], 2)].zero_pending and finite_zero_runtime.slots[0].timers[(ids["owner_sleep"], 2)].remaining_ticks == 0 and resolve_static(finite_zero_catalog, StaticContext(map_id=1)).candidate_timer_sources[13].indefinite is False and raises_status(lambda: catalog_from_dict(unknown_indefinite), Status.INVALID_STATIC_DATA) and raises_status(lambda: catalog_from_dict(unknown_indefinite_field), Status.INVALID_STATIC_DATA) and raises_status(lambda: catalog_from_dict(invalid_indefinite), Status.INVALID_STATIC_DATA))

    armed_runtime = StackRuntime(_fixture_catalog()[0])
    armed_slot = armed_runtime.install_slot(0, StaticContext(map_id=4))
    armed_runtime.apply(0, 2, ids["owner_stamina"])
    armed_runtime.tick_candidate_timers(0, 1)
    armed_rebind = armed_runtime.revalidate_retained_context(0, StaticContext(map_id=1))
    armed_timer = armed_slot.timers[(ids["owner_stamina"], 0)]
    armed_pending = armed_runtime.pending_expiry_plans(0)
    armed_empty = armed_runtime.apply_stack_delta(0, armed_slot.slot_generation, (), "armed-empty-validation")
    check("fifth-retained-timer-authenticates-original-armed-source", armed_rebind.ok and armed_timer.remaining_ticks == 5 and armed_timer.armed_duration == 6 and not armed_timer.armed_indefinite and armed_slot.timer_allocations[(ids["owner_stamina"], 0)].armed_duration == 6 and armed_pending == [] and armed_empty.status is Status.IDEMPOTENT and armed_timer.remaining_ticks == 5)

    tick_corrupt_runtime = StackRuntime(_fixture_catalog()[0])
    tick_corrupt_slot = tick_corrupt_runtime.install_slot(0, StaticContext(map_id=1))
    tick_corrupt_runtime.apply(0, 2, ids["owner_stamina"])
    tick_corrupt_slot.timers[(ids["owner_stamina"], 0)].timer_generation = 123
    tick_corrupt_before = semantic_slot_snapshot(tick_corrupt_runtime)
    tick_corrupt_rejected = raises_status(lambda: tick_corrupt_runtime.tick_candidate_timers(0, 1), Status.INVALID_HANDLE)
    gate_corrupt_runtime = StackRuntime(_fixture_catalog()[0])
    gate_corrupt_slot = gate_corrupt_runtime.install_slot(0, StaticContext(map_id=1))
    gate_corrupt_runtime.apply(0, 2, ids["owner_stamina"])
    gate_corrupt_slot.mandatory_expiry_registry = MappingProxyType({(ids["owner_stamina"], 0): "forged-plan"})  # type: ignore[dict-item]
    gate_corrupt_before = semantic_slot_snapshot(gate_corrupt_runtime)
    gate_corrupt_rejected = raises_status(lambda: gate_corrupt_runtime.set_presentation_gate(0, True), Status.INVALID_HANDLE)
    check("fifth-tick-and-gate-authenticate-before-any-write", tick_corrupt_rejected and semantic_slot_snapshot(tick_corrupt_runtime) == tick_corrupt_before and gate_corrupt_rejected and semantic_slot_snapshot(gate_corrupt_runtime) == gate_corrupt_before and not gate_corrupt_slot.presentation_gate)

    generated_branch_runtime = StackRuntime(_fixture_catalog()[0])
    generated_branch_slot = generated_branch_runtime.install_slot(0, StaticContext(map_id=2))
    wrong_fallback_branch = generated_branch_runtime.apply(0, 9, ids["owner_fled"])
    correct_semantic_branch = generated_branch_runtime.apply(0, 10, ids["owner_fled"])
    stamina_branch_runtime = StackRuntime(_fixture_catalog()[0])
    stamina_branch_runtime.install_slot(0, StaticContext(map_id=1))
    stamina_bypass = stamina_branch_runtime.apply(0, 2, ids["owner_stamina"])
    check("fifth-generated-apply-replace-authenticates-exact-translation-branch", wrong_fallback_branch.status is Status.INVALID_TRANSLATION and len(generated_branch_slot.layers) == 1 and generated_branch_slot.layers[0].definition_id == 10 and correct_semantic_branch.ok and stamina_bypass.ok)

    duration_five_family = copy.deepcopy(clean_data)
    completed_movement_family = copy.deepcopy(clean_data)
    transition_max_family = copy.deepcopy(clean_data)
    for definition_data in duration_five_family["definitions"].values():
        generated_data = definition_data.get("generated", {})
        if generated_data.get("hasTiredOriginKind") and generated_data.get("tiredOriginKind") == "FLED":
            definition_data["timer"]["duration"] = 5
    for definition_data in completed_movement_family["definitions"].values():
        generated_data = definition_data.get("generated", {})
        if generated_data.get("hasTiredOriginKind") and generated_data.get("tiredOriginKind") == "RAM_CRASH":
            definition_data["timer"]["clock"] = TimerClock.COMPLETED_MOVEMENT.value
    for definition_data in transition_max_family["definitions"].values():
        generated_data = definition_data.get("generated", {})
        if generated_data.get("hasTiredOriginKind") and generated_data.get("tiredOriginKind") == "THROW_RECOVERY":
            definition_data["timer"]["recoveryTransitionId"] = 0xFFFF
    check("fifth-generated-family-registry-rejects-uniform-wrong-metadata", raises_status(lambda: catalog_from_dict(duration_five_family), Status.INVALID_GENERATED_WRAPPER) and raises_status(lambda: catalog_from_dict(completed_movement_family), Status.INVALID_GENERATED_WRAPPER) and raises_status(lambda: catalog_from_dict(transition_max_family), Status.INVALID_GENERATED_WRAPPER))

    data_wrap_runtime = StackRuntime(_fixture_catalog()[0])
    stale_generation_one_context = StaticContext(map_id=1, data_generation=1, data_incarnation=data_wrap_runtime.data_incarnation)
    old_data_incarnation = data_wrap_runtime.data_incarnation
    force_authenticated_data_generation(data_wrap_runtime, GEN_MAX)
    data_wrap_runtime.stage_catalog(_fixture_catalog()[0])
    wrapped_data_generation = data_wrap_runtime.install_staged_catalog()
    stale_context_rejected = raises_status(lambda: data_wrap_runtime.install_slot(0, stale_generation_one_context), Status.INVALID_STATIC_DATA)
    fresh_generation_one_context = StaticContext(map_id=1, data_generation=1, data_incarnation=data_wrap_runtime.data_incarnation)
    fresh_data_slot = data_wrap_runtime.install_slot(0, fresh_generation_one_context)
    check("fifth-data-generation-terminal-wrap-uses-nonrepeating-incarnation", wrapped_data_generation == 1 and old_data_incarnation != data_wrap_runtime.data_incarnation and stale_context_rejected and fresh_data_slot.live and fresh_data_slot.static.context.data_incarnation == data_wrap_runtime.data_incarnation)

    malformed_generated_object = copy.deepcopy(clean_data); malformed_generated_object["definitions"]["1"]["generated"] = []
    malformed_applicability_object = copy.deepcopy(clean_data); malformed_applicability_object["definitions"]["1"]["applicability"] = False
    malformed_timer_object = copy.deepcopy(clean_data); malformed_timer_object["definitions"]["1"]["timer"] = []
    malformed_selector_object = copy.deepcopy(clean_data); malformed_selector_object["definitions"]["1"]["selector"] = []
    check("fifth-optional-object-fields-reject-present-malformed-shapes", raises_status(lambda: catalog_from_dict(malformed_generated_object), Status.INVALID_GENERATED_WRAPPER) and raises_status(lambda: catalog_from_dict(malformed_applicability_object), Status.INVALID_STATIC_DATA) and raises_status(lambda: catalog_from_dict(malformed_timer_object), Status.INVALID_STATIC_DATA) and raises_status(lambda: catalog_from_dict(malformed_selector_object), Status.INVALID_STATIC_DATA))

    @dataclass(frozen=True)
    class FrozenMutableLeaf:
        values: list[int]

    frozen_leaf_source = FrozenMutableLeaf([1])
    matcher_leaf_source = FrozenMutableLeaf([3])
    check("fifth-deep-freeze-reconstructs-frozen-dataclass-mutable-leaves", raises_status(lambda: _deep_freeze(frozen_leaf_source), Status.INVALID_STATIC_DATA) and raises_status(lambda: ContextMatcher(extras={"leaf": matcher_leaf_source}), Status.INVALID_STATIC_DATA))

    integer_gate_runtime = StackRuntime(_fixture_catalog()[0])
    integer_gate_slot = integer_gate_runtime.install_slot(0, StaticContext(map_id=1))
    integer_gate_runtime.apply(0, 2, ids["owner_stamina"])
    integer_gate_before = semantic_slot_snapshot(integer_gate_runtime)
    integer_gate_rejected = raises_status(lambda: integer_gate_runtime.tick_candidate_timers(0, 1, presentation_gate=1), Status.INVALID_HANDLE)
    check("fifth-tick-presentation-override-requires-actual-boolean", integer_gate_rejected and semantic_slot_snapshot(integer_gate_runtime) == integer_gate_before and not integer_gate_slot.presentation_gate and integer_gate_slot.timers[(ids["owner_stamina"], 0)].remaining_ticks == 4)

    forged_public_incarnation = dataclasses.replace(plan_a, runtime_incarnation=plan_b.runtime_incarnation)
    forged_public_before = semantic_slot_snapshot(plan_aba_runtime)
    forged_public_result = plan_aba_runtime.commit_expiry(forged_public_incarnation)
    forged_zero_tag = dataclasses.replace(plan_b, authenticator="0" * 64)
    forged_zero_result = plan_aba_runtime.commit_expiry(forged_zero_tag)
    check("sixth-expiry-plan-mac-cannot-be-forged-from-public-incarnation", forged_public_result.status is Status.STALE_NOOP and forged_zero_result.status is Status.STALE_NOOP and semantic_slot_snapshot(plan_aba_runtime) == forged_public_before and plan_aba_runtime.pending_expiry_plans(0) and plan_a.authenticator != plan_b.authenticator)

    canonical_indefinite_policy = CandidateTimerPolicy.from_dict({"duration": 255, "durationPolicy": "INDEFINITE"})
    zero_indefinite_wire = raises_status(lambda: CandidateTimerPolicy.from_dict({"duration": 0, "durationPolicy": "INDEFINITE"}), Status.INVALID_STATIC_DATA)
    finite_255_data = copy.deepcopy(clean_data); finite_255_data["definitions"]["13"]["timer"]["duration"] = 255; finite_255_data["definitions"]["13"]["timer"]["durationPolicy"] = TimerDurationPolicy.FINITE.value
    legacy_zero_source = resolve_static(_fixture_catalog()[0], StaticContext(map_id=1)).candidate_timer_sources[13]
    legacy_literal_source = resolve_static(_fixture_catalog()[0], StaticContext(map_id=1)).candidate_timer_sources[15]
    check("sixth-explicit-indefinite-wire-requires-authored-255", canonical_indefinite_policy is not None and canonical_indefinite_policy.duration == 255 and canonical_indefinite_policy.duration_policy is TimerDurationPolicy.INDEFINITE and zero_indefinite_wire and raises_status(lambda: catalog_from_dict(finite_255_data), Status.INVALID_STATIC_DATA) and explicit_static.candidate_timer_sources[13].authored_duration == 255 and explicit_static.candidate_timer_sources[13].resolved_duration_policy is TimerDurationPolicy.INDEFINITE and legacy_zero_source.normalized_duration == 255 and legacy_zero_source.resolved_duration_policy is TimerDurationPolicy.INDEFINITE and legacy_literal_source.authored_duration == 255 and legacy_literal_source.normalized_duration == 254 and legacy_literal_source.resolved_duration_policy is TimerDurationPolicy.FINITE)

    generated_calm_recovery_ok = True
    for tired_definition, tired_owner in ((20, ids["owner_ram"]), (30, ids["owner_throw"])):
        calm_runtime = StackRuntime(_fixture_catalog()[0])
        calm_slot = calm_runtime.install_slot(0, StaticContext(map_id=1))
        calm_runtime.apply(0, 1, ids["owner_awareness"])
        tired_apply = calm_runtime.apply(0, tired_definition, tired_owner)
        tired_handle = tired_apply.operation_results[0].handle
        calm_runtime.tick_candidate_timers(0, 4)
        calm_expiry = calm_runtime.commit_expiry(calm_runtime.pending_expiry_plans(0)[0])
        result_by_id = {item.operation_id: item for item in calm_expiry.operation_results}
        generated_calm_recovery_ok = generated_calm_recovery_ok and calm_expiry.ok and calm_expiry.mutated and calm_slot.composition.winner.role is SemanticRole.CALM and not calm_slot.layers and any(".SELF_REQUIRED." in operation_id and item.matched for operation_id, item in result_by_id.items()) and any(".CALM_RESET_REQUIRED.101.0" in operation_id and item.matched for operation_id, item in result_by_id.items()) and tired_handle.entry_generation > 0
    check("sixth-ram-and-throw-recovery-clear-generated-calm-reset-owners", generated_calm_recovery_ok)

    forged_armed_ok = True
    for forged_duration, forged_indefinite in ((255, True), (200, False)):
        forged_armed_runtime = StackRuntime(_fixture_catalog()[0])
        forged_armed_slot = forged_armed_runtime.install_slot(0, StaticContext(map_id=4))
        forged_armed_runtime.apply(0, 2, ids["owner_stamina"])
        forged_timer = forged_armed_slot.timers[(ids["owner_stamina"], 0)]
        forged_timer.armed_duration = forged_duration
        forged_timer.armed_indefinite = forged_indefinite
        forged_timer.remaining_ticks = forged_duration
        forged_timer.armed_source_hash = stable_hash("timer-source", {"forgedDuration": forged_duration, "indefinite": forged_indefinite})
        forged_armed_slot.timer_allocations = _timer_allocation_registry(forged_armed_slot.timers)
        forged_armed_before = semantic_slot_snapshot(forged_armed_runtime)
        tick_reject = raises_status(lambda: forged_armed_runtime.tick_candidate_timers(0, 1), Status.INVALID_HANDLE)
        rebind_reject = forged_armed_runtime.revalidate_retained_context(0, StaticContext(map_id=1))
        forged_armed_ok = forged_armed_ok and tick_reject and not rebind_reject.ok and rebind_reject.status is Status.INVALID_HANDLE and semantic_slot_snapshot(forged_armed_runtime) == forged_armed_before
    check("sixth-armed-timer-provenance-requires-private-allocation-mac", forged_armed_ok)

    inactive_world_runtime = StackRuntime(_fixture_catalog()[0], slot_count=2)
    inactive_trigger = inactive_world_runtime.install_slot(0, StaticContext(map_id=1))
    inactive_victim = inactive_world_runtime.install_slot(1, StaticContext(map_id=1))
    inactive_world_runtime.destroy_slot(1)
    inactive_victim.next_entry_generation = 2
    inactive_trigger.next_entry_generation = GEN_MAX
    inactive_world_before = (semantic_slot_snapshot(inactive_world_runtime, 0), semantic_slot_snapshot(inactive_world_runtime, 1))
    inactive_world_result = inactive_world_runtime.apply(0, 1, ids["owner_awareness"])
    captured_world_runtime = StackRuntime(_fixture_catalog()[0], slot_count=2)
    captured_trigger = captured_world_runtime.install_slot(0, StaticContext(map_id=1))
    captured_victim = captured_world_runtime.install_slot(1, StaticContext(map_id=1))
    captured_trigger.next_entry_generation = GEN_MAX
    captured_victim.captured_spawn_policy_values = MappingProxyType({**captured_victim.captured_spawn_policy_values, "maximumDistance": 8})
    captured_world_before = (semantic_slot_snapshot(captured_world_runtime, 0), semantic_slot_snapshot(captured_world_runtime, 1))
    captured_world_result = captured_world_runtime.apply(0, 1, ids["owner_awareness"])
    class ExplodingEmptyMapping(Mapping[Any, Any]):
        def __getitem__(self, key: Any) -> Any:
            raise KeyError(key)

        def __iter__(self) -> Any:
            return iter(())

        def __len__(self) -> int:
            raise TypeError("hostile inactive registry")

    hostile_world_runtime = StackRuntime(_fixture_catalog()[0], slot_count=2)
    hostile_trigger = hostile_world_runtime.install_slot(0, StaticContext(map_id=1))
    hostile_inactive = hostile_world_runtime.install_slot(1, StaticContext(map_id=1))
    hostile_world_runtime.destroy_slot(1)
    hostile_inactive.timer_allocations = ExplodingEmptyMapping()
    hostile_trigger.next_entry_generation = GEN_MAX
    hostile_world_result = hostile_world_runtime.apply(0, 1, ids["owner_awareness"])
    check("sixth-world-auth-covers-inactive-and-captured-policy-registries", inactive_world_result.status is Status.INVALID_HANDLE and inactive_world_before == (semantic_slot_snapshot(inactive_world_runtime, 0), semantic_slot_snapshot(inactive_world_runtime, 1)) and captured_world_result.status is Status.INVALID_HANDLE and captured_world_before == (semantic_slot_snapshot(captured_world_runtime, 0), semantic_slot_snapshot(captured_world_runtime, 1)) and hostile_world_result.status is Status.INVALID_HANDLE and hostile_trigger.live and hostile_inactive.live is False)

    expiry_exception_runtime = StackRuntime(_fixture_catalog()[0])
    expiry_exception_slot = expiry_exception_runtime.install_slot(0, StaticContext(map_id=1))
    expiry_exception_runtime.apply(0, 3, ids["owner_sleep"], 77)
    expiry_exception_runtime.tick_candidate_timers(0, 2)
    expiry_exception_plan = expiry_exception_runtime.pending_expiry_plans(0)[0]
    forged_effective_hash = object()
    expiry_exception_slot.composition = dataclasses.replace(expiry_exception_slot.composition, effective_hash=forged_effective_hash)  # type: ignore[arg-type]
    expiry_exception_layers = copy.deepcopy(expiry_exception_slot.layers)
    expiry_exception_timer = copy.deepcopy(expiry_exception_slot.timers)
    expiry_exception_result = expiry_exception_runtime.commit_expiry(expiry_exception_plan)
    check("sixth-commit-expiry-normalizes-canonicalization-exceptions", not expiry_exception_result.ok and expiry_exception_result.status in {Status.INVALID_COMPOSITION, Status.INVALID_HANDLE} and expiry_exception_slot.composition.effective_hash is forged_effective_hash and expiry_exception_slot.layers == expiry_exception_layers and expiry_exception_slot.timers == expiry_exception_timer)

    deterministic_statuses: list[Status] = []
    for install_order in ((1, 2), (2, 1)):
        ordered_runtime = StackRuntime(_fixture_catalog()[0], slot_count=3)
        ordered_trigger = ordered_runtime.install_slot(0, StaticContext(map_id=1))
        for ordered_index in install_order:
            ordered_runtime.install_slot(ordered_index, StaticContext(map_id=1))
        ordered_runtime.slots[1].captured_policy_authenticator = "0" * 64
        ordered_runtime.slots[2].composition = dataclasses.replace(ordered_runtime.slots[2].composition, effective_hash="effective:later-error")
        ordered_trigger.next_entry_generation = GEN_MAX
        deterministic_statuses.append(ordered_runtime.apply(0, 1, ids["owner_awareness"]).status)
    check("sixth-world-validation-failure-precedence-is-slot-index-deterministic", deterministic_statuses == [Status.INVALID_HANDLE, Status.INVALID_HANDLE])

    hash_seed_code = (
        "import sys; "
        f"sys.path.insert(0, {str(Path(__file__).resolve().parent)!r}); "
        "import overworld_behavior_stack_model as m; "
        "print(m.canonical_json_bytes({-37, '-37'}).decode('utf-8'))"
    )
    seeded_outputs = []
    for seed in ("1", "987654"):
        seeded_environment = dict(os.environ)
        seeded_environment["PYTHONHASHSEED"] = seed
        seeded_outputs.append(subprocess.check_output([sys.executable, "-c", hash_seed_code], env=seeded_environment, text=True).strip())
    check("sixth-heterogeneous-set-hash-is-type-tag-deterministic", seeded_outputs[0] == seeded_outputs[1] == '[-37,"-37"]')

    selector_float_rejected = raises_status(lambda: NodeSelector.exact(10.0, 4.0), Status.INVALID_STATIC_DATA)  # type: ignore[arg-type]
    selector_bool_rejected = raises_status(lambda: NodeSelector.semantic(SemanticRole.CUSTOM, True), Status.INVALID_STATIC_DATA)
    selector_range_rejected = raises_status(lambda: NodeSelector.exact(10, 0x10000), Status.INVALID_STATIC_DATA)
    check("sixth-public-node-selector-enforces-typed-u16-tag-union", selector_float_rejected and selector_bool_rejected and selector_range_rejected)

    unknown_selector_data = copy.deepcopy(clean_data); unknown_selector_data["definitions"]["1"]["selector"]["mystery"] = 1
    unknown_applicability_data = copy.deepcopy(clean_data); unknown_applicability_data["definitions"]["1"]["applicability"]["mystery"] = 1
    unknown_generated_data = copy.deepcopy(clean_data); unknown_generated_data["definitions"]["1"]["generated"]["mystery"] = 1
    alias_timer_data = copy.deepcopy(clean_data); alias_timer_data["definitions"]["3"]["timer"]["duration_policy"] = alias_timer_data["definitions"]["3"]["timer"]["durationPolicy"]
    malformed_registry_data = copy.deepcopy(clean_data); malformed_registry_data["definitions"] = False
    malformed_enum_data = copy.deepcopy(clean_data); malformed_enum_data["definitions"]["1"]["kind"] = "NOT_A_KIND"
    unknown_delta_rejected = raises_status(lambda: DeltaOperation.from_dict({"operationId": "x", "kind": "CLEAR", "mystery": 1}), Status.INVALID_HANDLE)
    check("sixth-json-adapters-are-closed-and-normalize-malformed-errors", raises_status(lambda: catalog_from_dict(unknown_selector_data), Status.INVALID_STATIC_DATA) and raises_status(lambda: catalog_from_dict(unknown_applicability_data), Status.INVALID_STATIC_DATA) and raises_status(lambda: catalog_from_dict(unknown_generated_data), Status.INVALID_GENERATED_WRAPPER) and raises_status(lambda: catalog_from_dict(alias_timer_data), Status.INVALID_STATIC_DATA) and raises_status(lambda: catalog_from_dict(malformed_registry_data), Status.INVALID_STATIC_DATA) and raises_status(lambda: catalog_from_dict(malformed_enum_data), Status.INVALID_STATIC_DATA) and unknown_delta_rejected)

    class MutableHashKey:
        def __init__(self) -> None:
            self.value = 1

        def __hash__(self) -> int:
            return 7

    integer_extra_rejected = raises_status(lambda: StaticContext(extras={1: "bad"}), Status.INVALID_STATIC_DATA)
    matcher_integer_extra_rejected = raises_status(lambda: ContextMatcher(extras={1: "bad"}), Status.INVALID_STATIC_DATA)
    mutable_extra_key = MutableHashKey()
    mutable_extra_rejected = raises_status(lambda: StaticContext(extras={mutable_extra_key: "bad"}), Status.INVALID_STATIC_DATA)
    extras_context = StaticContext(map_id=7, extras={"axis": [1, {"nested": [2]}]})
    extras_roundtrip = StaticContext.from_dict(to_data(extras_context))
    check("sixth-extras-require-canonical-string-keys-and-stable-roundtrip", integer_extra_rejected and matcher_integer_extra_rejected and mutable_extra_rejected and extras_context == extras_roundtrip and canonical_json_bytes(extras_context) == canonical_json_bytes(extras_roundtrip) and extras_context.extras["axis"] == (1, MappingProxyType({"nested": (2,)})))

    # Seventh-pass adversarial reproductions: cold activation domains,
    # replacement-only destruction, complete plan payloads, and closed nested
    # serialization.
    cold_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="seventh-cold-domain")
    cold_slot = cold_runtime.install_slot(0, StaticContext(map_id=1))
    cold_apply = cold_runtime.apply(0, 3, ids["owner_sleep"], 41)
    cold_handle = cold_apply.operation_results[0].handle
    cold_runtime.tick_candidate_timers(0, 2)
    cold_plan = ExpiryPlan.from_dict(cold_runtime.pending_expiry_plans(0)[0])
    cold_identity = (cold_runtime.runtime_incarnation, cold_runtime.data_incarnation)
    cold_runtime.destroy_slot(0)
    cold_runtime.stage_catalog(_fixture_catalog()[0])
    cold_runtime.install_staged_catalog()
    cold_context = StaticContext(map_id=1, data_generation=cold_runtime.data_generation, data_incarnation=cold_runtime.data_incarnation)
    cold_slot_generation = cold_runtime.slots[0].slot_generation
    cold_slot = cold_runtime.install_slot(0, cold_context, slot_generation=cold_slot_generation)
    new_cold_apply = cold_runtime.apply(0, 3, ids["owner_sleep"], 41)
    cold_runtime.tick_candidate_timers(0, 2)
    new_cold_plan = ExpiryPlan.from_dict(cold_runtime.pending_expiry_plans(0)[0])
    old_cold_handle_result = cold_runtime.remove(0, cold_handle)
    old_cold_plan_result = cold_runtime.commit_expiry(cold_plan)
    check("seventh-cold-catalog-activation-rotates-handle-timer-expiry-and-data-domains", cold_identity != (cold_runtime.runtime_incarnation, cold_runtime.data_incarnation) and cold_handle.authenticator != new_cold_apply.operation_results[0].handle.authenticator and cold_plan.authenticator != new_cold_plan.authenticator and old_cold_handle_result.status is Status.INVALID_HANDLE and old_cold_plan_result.status is Status.STALE_NOOP and len(cold_slot.layers) == 1)

    destroy_runtime = StackRuntime(_fixture_catalog()[0], slot_count=2, handle_secret="seventh-destroy")
    destroy_slot = destroy_runtime.install_slot(0, StaticContext(map_id=1))
    destroy_runtime.apply(0, 1, ids["owner_awareness"])
    destroy_before = (destroy_runtime.runtime_epoch, destroy_runtime.runtime_incarnation, destroy_slot.slot_generation, destroy_slot.live, tuple(destroy_slot.layers))
    destroy_runtime.slots[99] = _new_inactive_slot(99, 1)
    destroy_rejected = raises_status(lambda: destroy_runtime.destroy_slot(0), Status.INVALID_HANDLE)
    destroy_after = (destroy_runtime.runtime_epoch, object.__getattribute__(destroy_runtime, "_runtime_incarnation"), destroy_slot.slot_generation, destroy_slot.live, tuple(destroy_slot.layers))
    check("seventh-destroy-and-terminal-cleanup-preflight-exact-slot-domain-before-replacement", destroy_rejected and destroy_before == destroy_after and 99 in destroy_runtime.slots)

    diagnostic_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="seventh-diagnostics")
    diagnostic_slot = diagnostic_runtime.install_slot(0, StaticContext(map_id=1))
    diagnostic_slot.diagnostics = SlotDiagnostics(stale_handle_count="corrupt")  # type: ignore[arg-type]
    diagnostic_before = (tuple(diagnostic_slot.layers), diagnostic_slot.composition, diagnostic_slot.generations(), diagnostic_slot.diagnostics)
    diagnostic_result = diagnostic_runtime.apply(0, 1, ids["owner_awareness"])
    diagnostic_after = (tuple(diagnostic_slot.layers), diagnostic_slot.composition, diagnostic_slot.generations(), diagnostic_slot.diagnostics)
    check("seventh-diagnostics-are-typed-staged-and-cannot-fail-after-commit", not diagnostic_result.ok and diagnostic_result.status is Status.INVALID_HANDLE and diagnostic_before == diagnostic_after)

    foreign_a = StackRuntime(_fixture_catalog()[0])
    foreign_b = StackRuntime(_fixture_catalog()[0])
    foreign_a_slot = foreign_a.install_slot(0, StaticContext(map_id=4))
    foreign_b_slot = foreign_b.install_slot(0, StaticContext(map_id=4))
    foreign_a.apply(0, 2, ids["owner_stamina"])
    foreign_b.apply(0, 2, ids["owner_stamina"])
    foreign_key = (ids["owner_stamina"], 0)
    foreign_b_slot.timers[foreign_key] = copy.deepcopy(foreign_a_slot.timers[foreign_key])
    foreign_b_slot.timer_allocations = MappingProxyType({foreign_key: foreign_a_slot.timer_allocations[foreign_key]})
    foreign_timer_rejected = raises_status(lambda: foreign_b.tick_candidate_timers(0, 1), Status.INVALID_HANDLE)
    check("seventh-default-runtimes-use-independent-mac-domains-and-reject-foreign-allocations", foreign_a.runtime_incarnation != foreign_b.runtime_incarnation and foreign_timer_rejected and foreign_b_slot.timers[foreign_key].remaining_ticks == 6)

    complete_plan_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="seventh-complete-plan")
    complete_plan_runtime.install_slot(0, StaticContext(map_id=1))
    complete_plan_runtime.apply(0, 3, ids["owner_sleep"], 7)
    complete_plan_runtime.tick_candidate_timers(0, 2)
    complete_plan_data = complete_plan_runtime.pending_expiry_plans(0)[0]
    changed_plan_data = copy.deepcopy(complete_plan_data)
    changed_plan_data["recoveryPolicy"] = RecoveryPolicy.LEGACY_RETURN_CALM.value
    changed_plan_data["recoveryAction"] = "REMOVE_EXACT_SELF_AND_CALM_RESET_OWNERS"
    missing_plan_data = copy.deepcopy(complete_plan_data)
    del missing_plan_data["recoveryAction"]
    changed_plan_result = complete_plan_runtime.commit_expiry(changed_plan_data)
    missing_plan_result = complete_plan_runtime.commit_expiry(missing_plan_data)
    check("seventh-expiry-mac-covers-complete-recovery-policy-action-and-metadata", changed_plan_result.status is Status.STALE_NOOP and not missing_plan_result.ok and missing_plan_result.status is Status.INVALID_HANDLE and complete_plan_runtime.pending_expiry_plans(0))

    context_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="seventh-context")
    context_slot = context_runtime.install_slot(0, StaticContext(map_id=1))
    context_slot.static = resolve_static(context_runtime.catalog, StaticContext(map_id=4))
    swapped_context_result = context_runtime.apply(0, 1, ids["owner_awareness"])
    retained_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="seventh-retained-policy")
    retained_context_slot = retained_runtime.install_slot(0, StaticContext(map_id=1))
    retained_context_slot.captured_spawn_policy_values = MappingProxyType({"forged": 1})
    retained_before = (retained_context_slot.static, retained_context_slot.generations(), tuple(retained_context_slot.layers))
    retained_auth_result = retained_runtime.revalidate_retained_context(0, StaticContext(map_id=4))
    retained_after = (retained_context_slot.static, retained_context_slot.generations(), tuple(retained_context_slot.layers))
    check("seventh-installed-context-and-retained-captured-policy-authentication", not swapped_context_result.ok and swapped_context_result.status is Status.INVALID_HANDLE and not retained_auth_result.ok and retained_auth_result.status is Status.INVALID_HANDLE and retained_before == retained_after)

    ordinary_recovery_data = copy.deepcopy(clean_data)
    ordinary_timer = ordinary_recovery_data["definitions"]["12"]["timer"]
    ordinary_timer["recoveryPolicy"] = RecoveryPolicy.LEGACY_RETURN_CALM.value
    ordinary_timer["calmResetOwnerIds"] = list(CALM_RESET_OWNER_IDS)
    ordinary_catalog = catalog_from_dict(ordinary_recovery_data)
    ordinary_runtime = StackRuntime(ordinary_catalog, handle_secret="seventh-ordinary-recovery")
    ordinary_slot = ordinary_runtime.install_slot(0, StaticContext(map_id=1))
    ordinary_runtime.apply(0, 1, ids["owner_awareness"])
    ordinary_runtime.apply(0, 12, 112)
    ordinary_runtime.tick_candidate_timers(0, 3)
    ordinary_expiry = ordinary_runtime.commit_expiry(ordinary_runtime.pending_expiry_plans(0)[0])
    bad_ordinary_data = copy.deepcopy(ordinary_recovery_data)
    bad_ordinary_data["definitions"]["12"]["timer"]["calmResetOwnerIds"] = []
    reveal_without_opt_in = copy.deepcopy(clean_data)
    reveal_without_opt_in["definitions"]["12"]["timer"]["recoveryPolicy"] = RecoveryPolicy.REVEAL_UNDERLYING.value
    reveal_catalog = catalog_from_dict(reveal_without_opt_in)
    reveal_runtime = StackRuntime(reveal_catalog); reveal_runtime.install_slot(0, StaticContext(map_id=1))
    reveal_rejected = reveal_runtime.apply(0, 12, 112)
    check("seventh-ordinary-recovery-policy-requires-reset-batch-opt-in-and-returns-calm", ordinary_expiry.ok and ordinary_slot.composition.winner.role is SemanticRole.CALM and raises_status(lambda: catalog_from_dict(bad_ordinary_data), Status.INVALID_STATIC_DATA) and reveal_rejected.status is Status.NOT_APPLICABLE)

    class HostileDeepcopy:
        def __deepcopy__(self, memo: Any) -> Any:
            raise RuntimeError("hostile deepcopy")

    class HostileMapping(Mapping[str, Any]):
        def __getitem__(self, key: str) -> Any:
            raise RuntimeError("hostile mapping item")

        def __iter__(self) -> Any:
            raise RuntimeError("hostile mapping iterator")

        def __len__(self) -> int:
            return 1

    hostile_apply_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="seventh-hostile-apply")
    hostile_apply_slot = hostile_apply_runtime.install_slot(0, StaticContext(map_id=1))
    hostile_leaf = HostileDeepcopy()
    hostile_apply_slot.layers.append(hostile_leaf)  # type: ignore[arg-type]
    hostile_apply_before = (hostile_apply_slot.generations(), hostile_apply_slot.diagnostics, tuple(hostile_apply_slot.layers))
    hostile_apply_result = hostile_apply_runtime.apply(0, 1, ids["owner_awareness"])
    hostile_apply_after = (hostile_apply_slot.generations(), hostile_apply_slot.diagnostics, tuple(hostile_apply_slot.layers))
    hostile_expiry_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="seventh-hostile-expiry")
    hostile_expiry_runtime.install_slot(0, StaticContext(map_id=1))
    hostile_expiry_result = hostile_expiry_runtime.commit_expiry(HostileMapping())
    hostile_rebind_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="seventh-hostile-rebind")
    hostile_rebind_slot = hostile_rebind_runtime.install_slot(0, StaticContext(map_id=1))
    object.__setattr__(hostile_rebind_slot.composition, "provenance", HostileMapping())
    hostile_rebind_before = hostile_rebind_slot.generations()
    hostile_rebind_result = hostile_rebind_runtime.revalidate_retained_context(0, StaticContext(map_id=4))
    check("seventh-public-atomic-apis-contain-hostile-exceptions-without-mutation", not hostile_apply_result.ok and hostile_apply_before == hostile_apply_after and not hostile_expiry_result.ok and hostile_expiry_result.status is Status.INVALID_HANDLE and not hostile_rebind_result.ok and hostile_rebind_slot.generations() == hostile_rebind_before)

    timer_precedence: list[tuple[Status, str]] = []
    for reverse_timer_order in (False, True):
        precedence_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="seventh-timer-precedence")
        precedence_slot = precedence_runtime.install_slot(0, StaticContext(map_id=1))
        precedence_runtime.apply(0, 12, ids["owner_awareness"])
        precedence_runtime.apply(0, 14, ids["owner_script"])
        low_key, high_key = sorted(precedence_slot.timers)
        precedence_slot.timers[low_key].timer_generation = 0
        precedence_slot.timers[high_key].armed_source_hash = "corrupt-later"
        ordered_keys = [high_key, low_key] if reverse_timer_order else [low_key, high_key]
        precedence_slot.timers = {key: precedence_slot.timers[key] for key in ordered_keys}
        precedence_slot.timer_allocations = MappingProxyType({key: precedence_slot.timer_allocations[key] for key in ordered_keys})
        try:
            precedence_runtime.tick_candidate_timers(0, 1)
        except ModelError as exc:
            timer_precedence.append((exc.status, exc.message))
    check("seventh-timer-validation-precedence-is-owner-key-sorted-not-insertion-ordered", len(timer_precedence) == 2 and timer_precedence[0] == timer_precedence[1] and timer_precedence[0][0] is Status.INVALID_HANDLE)

    closed_compose_base = {"catalog": clean_data, "context": {"mapId": 1}, "layers": []}
    closed_compose_extra = copy.deepcopy(closed_compose_base); closed_compose_extra["mystery"] = 1
    closed_layer_alias = copy.deepcopy(closed_compose_base); closed_layer_alias["layers"] = [{"definitionId": 1, "definition_id": 1, "ownerId": ids["owner_awareness"], "instanceKey": 0, "entryGeneration": 1, "generated": to_data(clean_catalog.definitions[1].generated)}]
    closed_bad_layers = copy.deepcopy(closed_compose_base); closed_bad_layers["layers"] = {}
    atom_smuggle = copy.deepcopy(closed_compose_base); atom_smuggle["context"] = {"raw": "x", "symbol": "x", "value": {"mapId": 1}}
    check("seventh-compose-and-layer-json-are-closed-and-atoms-cannot-smuggle-objects", raises_status(lambda: _compose_request(closed_compose_extra), Status.INVALID_STATIC_DATA) and raises_status(lambda: _compose_request(closed_layer_alias), Status.INVALID_STATIC_DATA) and raises_status(lambda: _compose_request(closed_bad_layers), Status.INVALID_STATIC_DATA) and raises_status(lambda: _compose_request(atom_smuggle), Status.INVALID_STATIC_DATA))

    recursive_key_rejected = raises_status(lambda: StaticContext(extras={"nested": {1: "bad"}}), Status.INVALID_STATIC_DATA)
    recursive_matcher_key_rejected = raises_status(lambda: ContextMatcher(extras={"nested": {2: "bad"}}), Status.INVALID_STATIC_DATA)
    typed_extras = StaticContext(map_id=8, extras={"mixed": frozenset({-37, "-37"}), "nested": {"values": frozenset({1, 2})}})
    typed_extras_data = to_data(typed_extras)
    typed_extras_roundtrip = StaticContext.from_dict(typed_extras_data)
    typed_extra_entries = dict(typed_extras_data["extras"]["entries"])
    check("seventh-recursive-extras-keys-and-typed-set-envelopes-roundtrip-canonically", recursive_key_rejected and recursive_matcher_key_rejected and typed_extras_roundtrip == typed_extras and canonical_json_bytes(typed_extras_roundtrip) == canonical_json_bytes(typed_extras) and typed_extras_data["extras"]["$extraType"] == "map" and typed_extra_entries["mixed"]["$extraType"] == "frozenset")

    # Eighth-pass adversarial reproductions.
    class HostileExpiryDict(dict[Any, Any]):
        compared = False

        def __eq__(self, other: Any) -> bool:
            type(self).compared = True
            raise RuntimeError("hostile expiry equality")

        def __ne__(self, other: Any) -> bool:
            type(self).compared = True
            raise RuntimeError("hostile expiry inequality")

    closed_registry_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="eighth-registry", runtime_nonce="registry")
    closed_registry_slot = closed_registry_runtime.install_slot(0, StaticContext(map_id=1))
    closed_registry_runtime.apply(0, 1, ids["owner_awareness"])
    closed_registry_before = (tuple(closed_registry_slot.layers), closed_registry_slot.generations(), closed_registry_slot.diagnostics)
    closed_registry_slot.mandatory_expiry_registry = HostileExpiryDict()  # type: ignore[assignment]
    closed_registry_result = closed_registry_runtime.clear(0)
    closed_registry_after = (tuple(closed_registry_slot.layers), closed_registry_slot.generations(), closed_registry_slot.diagnostics)
    check("eighth-mandatory-expiry-registry-is-exact-closed-and-never-uses-user-equality", not closed_registry_result.ok and closed_registry_result.status is Status.INVALID_HANDLE and not HostileExpiryDict.compared and closed_registry_before == closed_registry_after)

    world_delta_runtime = StackRuntime(_fixture_catalog()[0], slot_count=2, handle_secret="eighth-world-delta", runtime_nonce="world-delta")
    world_target = world_delta_runtime.install_slot(0, StaticContext(map_id=1))
    world_other = world_delta_runtime.install_slot(1, StaticContext(map_id=1))
    world_target_handle = world_delta_runtime.apply(0, 1, ids["owner_awareness"]).operation_results[0].handle
    object.__setattr__(world_other.composition, "effective_hash", "effective:foreign-corruption")
    world_target_before = (tuple(world_target.layers), world_target.generations(), world_target.diagnostics, world_delta_runtime.runtime_epoch)
    corrupt_clear = world_delta_runtime.clear(0)
    corrupt_remove = world_delta_runtime.remove(0, world_target_handle)
    world_target_after = (tuple(world_target.layers), world_target.generations(), world_target.diagnostics, world_delta_runtime.runtime_epoch)
    expiry_world_runtime = StackRuntime(_fixture_catalog()[0], slot_count=2, handle_secret="eighth-world-expiry", runtime_nonce="world-expiry")
    expiry_world_slot = expiry_world_runtime.install_slot(0, StaticContext(map_id=1))
    expiry_world_other = expiry_world_runtime.install_slot(1, StaticContext(map_id=1))
    expiry_world_runtime.apply(0, 3, ids["owner_sleep"], 5); expiry_world_runtime.tick_candidate_timers(0, 2)
    expiry_world_plan = expiry_world_runtime.pending_expiry_plans(0)[0]
    object.__setattr__(expiry_world_other.composition, "effective_hash", "effective:foreign-expiry-corruption")
    expiry_world_before = (tuple(expiry_world_slot.layers), expiry_world_slot.generations(), expiry_world_slot.diagnostics)
    corrupt_expiry = expiry_world_runtime.commit_expiry(expiry_world_plan)
    check("eighth-every-destructive-delta-and-expiry-preflights-the-complete-world", not corrupt_clear.ok and not corrupt_remove.ok and world_target_before == world_target_after and not corrupt_expiry.ok and expiry_world_before == (tuple(expiry_world_slot.layers), expiry_world_slot.generations(), expiry_world_slot.diagnostics))

    class FlappingDeltaSequence(Sequence[DeltaOperation]):
        target: SlotRuntime | None = None

        def __init__(self, first: DeltaOperation, later: DeltaOperation):
            self.first, self.later, self.iterations, self.callbacks = first, later, 0, 0

        def mutate(self) -> None:
            self.callbacks += 1
            if type(self).target is not None:
                object.__setattr__(type(self).target, "presentation_gate", True)

        def __len__(self) -> int:
            self.mutate()
            return 1

        def __getitem__(self, index: int) -> DeltaOperation:
            self.mutate()
            if index != 0:
                raise IndexError(index)
            return self.later

        def __iter__(self) -> Any:
            self.mutate()
            self.iterations += 1
            return iter((self.first if self.iterations == 1 else self.later,))

    snapshot_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="eighth-snapshot", runtime_nonce="snapshot")
    snapshot_slot = snapshot_runtime.install_slot(0, StaticContext(map_id=1))
    snapshot_apply = snapshot_runtime.bind_delta_operation(DeltaOperation.apply("first", 1, ids["owner_awareness"]))
    snapshot_clear = snapshot_runtime.bind_delta_operation(DeltaOperation("later", DeltaOpKind.CLEAR))
    FlappingDeltaSequence.target = snapshot_slot
    flapping_operations = FlappingDeltaSequence(snapshot_apply, snapshot_clear)
    snapshot_before_hostile_sequence = exact_runtime_internal_snapshot(snapshot_runtime)
    snapshot_result = snapshot_runtime.apply_stack_delta(0, snapshot_slot.slot_generation, flapping_operations, "OnceOnlySnapshot")
    check("eighth-custom-delta-sequence-is-rejected-without-iteration-or-toctou", not snapshot_result.ok and snapshot_result.status is Status.INVALID_HANDLE and flapping_operations.iterations == 0 and flapping_operations.callbacks == 0 and snapshot_slot.presentation_gate is False and not snapshot_slot.layers and exact_runtime_internal_snapshot(snapshot_runtime) == snapshot_before_hostile_sequence)
    FlappingDeltaSequence.target = None

    queued_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="eighth-queued", runtime_nonce="queued")
    queued_slot = queued_runtime.install_slot(0, StaticContext(map_id=1))
    old_queued_operation = queued_runtime.bind_delta_operation(DeltaOperation.apply("queued", 1, ids["owner_awareness"]))
    queued_runtime.destroy_slot(0); queued_runtime.stage_catalog(_fixture_catalog()[0]); queued_runtime.install_staged_catalog()
    queued_context = StaticContext(map_id=1, data_generation=queued_runtime.data_generation, data_incarnation=queued_runtime.data_incarnation)
    queued_slot = queued_runtime.install_slot(0, queued_context, slot_generation=queued_runtime.slots[0].slot_generation)
    stale_queued_result = queued_runtime.apply_stack_delta(0, queued_slot.slot_generation, (old_queued_operation,), "StaleQueuedEnvelope")
    check("eighth-nonhandle-queued-deltas-bind-runtime-and-behavior-data-incarnation", not stale_queued_result.ok and stale_queued_result.status is Status.INVALID_HANDLE and not queued_slot.layers)

    same_key_a = StackRuntime(_fixture_catalog()[0], handle_secret="shared-explicit-key")
    same_key_b = StackRuntime(_fixture_catalog()[0], handle_secret="shared-explicit-key")
    same_key_a_slot = same_key_a.install_slot(0, StaticContext(map_id=4))
    same_key_b_slot = same_key_b.install_slot(0, StaticContext(map_id=1))
    same_key_a_apply = same_key_a.apply(0, 2, ids["owner_stamina"])
    same_key_b.apply(0, 2, ids["owner_stamina"])
    copied_key = (ids["owner_stamina"], 0)
    same_key_b_slot.timers[copied_key] = copy.deepcopy(same_key_a_slot.timers[copied_key])
    same_key_b_slot.timer_allocations = MappingProxyType({copied_key: same_key_a_slot.timer_allocations[copied_key]})
    same_key_timer_rejected = raises_status(lambda: same_key_b.tick_candidate_timers(0, 1), Status.INVALID_HANDLE)
    same_key_handle_result = same_key_b.remove(0, same_key_a_apply.operation_results[0].handle)
    check("eighth-explicit-key-material-still-uses-independent-runtime-nonce-and-context-domains", same_key_a.runtime_incarnation != same_key_b.runtime_incarnation and same_key_timer_rejected and same_key_handle_result.status is Status.INVALID_HANDLE and len(same_key_b_slot.layers) == 1)

    binding_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="eighth-binding", runtime_nonce="binding")
    binding_slot = binding_runtime.install_slot(0, StaticContext(map_id=1))
    binding_runtime.apply(0, 8, ids["owner_fled"]); binding_runtime.tick_candidate_timers(0, 4)
    pre_rebind_plan = ExpiryPlan.from_dict(binding_runtime.pending_expiry_plans(0)[0])
    binding_revalidate = binding_runtime.revalidate_retained_context(0, StaticContext(map_id=2))
    post_rebind_plan = ExpiryPlan.from_dict(binding_runtime.pending_expiry_plans(0)[0])
    stale_pre_rebind = binding_runtime.commit_expiry(pre_rebind_plan)
    translated_survives = len(binding_slot.layers) == 1 and binding_slot.layers[0].definition_id == 10
    current_rebind_expiry = binding_runtime.commit_expiry(post_rebind_plan)
    check("eighth-expiry-plan-mac-covers-definition-static-generation-and-resolved-binding", binding_revalidate.ok and pre_rebind_plan.definition_id == 8 and post_rebind_plan.definition_id == 10 and canonical_json_bytes(pre_rebind_plan) != canonical_json_bytes(post_rebind_plan) and stale_pre_rebind.status is Status.STALE_NOOP and translated_survives and current_rebind_expiry.ok and not binding_slot.layers)

    lrc_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="eighth-lrc", runtime_nonce="lrc")
    lrc_slot = lrc_runtime.install_slot(0, StaticContext(map_id=1))
    lrc_runtime.apply(0, 1, 777); lrc_runtime.apply(0, 2, ids["owner_stamina"]); lrc_runtime.tick_candidate_timers(0, 4)
    lrc_result = lrc_runtime.commit_expiry(lrc_runtime.pending_expiry_plans(0)[0])
    overlap_runtime = StackRuntime(ordinary_catalog); overlap_runtime.install_slot(0, StaticContext(map_id=1))
    overlap_result = overlap_runtime.apply(0, 12, CALM_RESET_OWNER_IDS[0])
    asleep_lrc_data = copy.deepcopy(clean_data); asleep_lrc_data["definitions"]["3"]["timer"]["recoveryPolicy"] = RecoveryPolicy.LEGACY_RETURN_CALM.value; asleep_lrc_data["definitions"]["3"]["timer"]["calmResetOwnerIds"] = list(CALM_RESET_OWNER_IDS)
    non_lrc_reset_data = copy.deepcopy(clean_data); non_lrc_reset_data["definitions"]["3"]["timer"]["calmResetOwnerIds"] = [101]
    reveal_modifier = Modifier(99, {"controller.allowRevealUnderlyingRecovery": ModifierOperation(OperatorKind.SET, True)})
    reveal_rule = StaticRule(99, ContextMatcher(map_ids=frozenset({15})), (StaticAction(99, StaticActionKind.APPLY_CONTROLLER_MODIFIER, static_priority=10, controller_id=10, modifier_id=99),))
    reveal_definition = dataclasses.replace(_fixture_catalog()[0].definitions[14], timer=dataclasses.replace(_fixture_catalog()[0].definitions[14].timer, recovery_policy=RecoveryPolicy.REVEAL_UNDERLYING))
    reveal_static_catalog = dataclasses.replace(_fixture_catalog()[0], modifiers={**_fixture_catalog()[0].modifiers, 99: reveal_modifier}, definitions={**_fixture_catalog()[0].definitions, 14: reveal_definition}, static_rules=(*_fixture_catalog()[0].static_rules, reveal_rule))
    resolved_reveal_runtime = StackRuntime(reveal_static_catalog); resolved_reveal_slot = resolved_reveal_runtime.install_slot(0, StaticContext(map_id=15))
    resolved_reveal_apply = resolved_reveal_runtime.apply(0, 14, ids["owner_script"]); resolved_reveal_runtime.tick_candidate_timers(0, 9)
    resolved_reveal_expiry = resolved_reveal_runtime.commit_expiry(resolved_reveal_runtime.pending_expiry_plans(0)[0])
    resolved_reveal_actions = {plan.get("action") for plan in resolved_reveal_expiry.plans}
    check("eighth-recovery-policies-close-lrc-asleep-overlap-resolved-reveal-and-tired-exit", lrc_result.ok and lrc_slot.composition.winner.role is SemanticRole.CALM and not lrc_slot.layers and overlap_result.status is Status.INVALID_HANDLE and raises_status(lambda: catalog_from_dict(asleep_lrc_data), Status.INVALID_STATIC_DATA) and raises_status(lambda: catalog_from_dict(non_lrc_reset_data), Status.INVALID_STATIC_DATA) and resolved_reveal_apply.ok and resolved_reveal_expiry.ok and {"RESET_TIRED_RAM_CHAIN_COUNTERS_AND_PRESENTATION", "APPLY_POST_TIRED_MOVEMENT_COOLDOWN"}.issubset(resolved_reveal_actions))

    envelope_like_mapping = StaticContext(extras={"payload": {"$extraType": "frozenset", "items": []}})
    envelope_like_roundtrip = StaticContext.from_dict(to_data(envelope_like_mapping))
    duplicate_set_wire = {"mapId": 1, "extras": {"$extraType": "map", "entries": [["set", {"$extraType": "frozenset", "items": [1, 1]}]]}}
    unordered_set_wire = {"mapId": 1, "extras": {"$extraType": "map", "entries": [["set", {"$extraType": "frozenset", "items": [2, 1]}]]}}
    collapsing_set_wire = {"mapId": 1, "extras": {"$extraType": "map", "entries": [["set", {"$extraType": "frozenset", "items": [1, True]}]]}}
    ordered_axis_set_wire = copy.deepcopy(clean_data); ordered_axis_set_wire["controllers"]["10"]["nodes"] = {"$extraType": "frozenset", "items": []}
    check("eighth-extras-wire-is-injective-and-rejects-noncanonical-set-envelopes", envelope_like_roundtrip == envelope_like_mapping and raises_status(lambda: StaticContext.from_dict(duplicate_set_wire), Status.INVALID_STATIC_DATA) and raises_status(lambda: StaticContext.from_dict(unordered_set_wire), Status.INVALID_STATIC_DATA) and raises_status(lambda: StaticContext.from_dict(collapsing_set_wire), Status.INVALID_STATIC_DATA) and raises_status(lambda: catalog_from_dict(ordered_axis_set_wire), Status.INVALID_STATIC_DATA))

    class EvilEquality:
        invoked = False

        def __eq__(self, other: Any) -> bool:
            type(self).invoked = True
            raise RuntimeError("hostile equality")

    @dataclass(frozen=True)
    class ForgedFrozenDataclass:
        value: int

    hostile_extra_rejected = raises_status(lambda: StaticContext(extras={"evil": EvilEquality()}), Status.INVALID_STATIC_DATA)
    forged_extra_rejected = raises_status(lambda: ContextMatcher(extras={"forged": ForgedFrozenDataclass(1)}), Status.INVALID_STATIC_DATA)
    forged_serialize_rejected = raises_status(lambda: to_data(ForgedFrozenDataclass(1)), Status.INVALID_STATIC_DATA)
    check("eighth-extras-use-a-closed-recursive-domain-without-hostile-equality-or-dataclass-trust", hostile_extra_rejected and forged_extra_rejected and forged_serialize_rejected and not EvilEquality.invoked)

    class HostileBoundarySequence(Sequence[Layer]):
        callbacks = 0

        def __len__(self) -> int:
            type(self).callbacks += 1
            return 1

        def __getitem__(self, index: int) -> Layer:
            type(self).callbacks += 1
            raise RuntimeError("hostile sequence")

        def __iter__(self) -> Any:
            type(self).callbacks += 1
            raise RuntimeError("hostile sequence")

    public_boundary_runtime = StackRuntime(_fixture_catalog()[0])
    invalid_convenience = public_boundary_runtime.apply(-1, 1, ids["owner_awareness"])
    invalid_direct = public_boundary_runtime.apply_stack_delta(-1, 1, (), "NegativeSlot")
    hostile_compose_rejected = raises_status(lambda: compose(_fixture_catalog()[0], resolve_static(_fixture_catalog()[0], StaticContext(map_id=1)), HostileBoundarySequence()), Status.INVALID_COMPOSITION)
    hostile_catalog_rejected = raises_status(lambda: catalog_from_dict(HostileExpiryDict()), Status.INVALID_STATIC_DATA)
    hostile_request_rejected = raises_status(lambda: _compose_request(HostileExpiryDict()), Status.INVALID_STATIC_DATA)
    hostile_commit = public_boundary_runtime.commit_expiry(HostileExpiryDict())
    check("eighth-public-boundaries-contain-hostile-inputs-and-preserve-invalid-handle-status", invalid_convenience.status is Status.INVALID_HANDLE and invalid_direct.status is Status.INVALID_HANDLE and hostile_compose_rejected and HostileBoundarySequence.callbacks == 0 and hostile_catalog_rejected and hostile_request_rejected and hostile_commit.status is Status.INVALID_HANDLE)

    p2_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="eighth-p2", runtime_nonce="p2")
    p2_slot = p2_runtime.install_slot(0, StaticContext(map_id=1))
    p2_runtime.apply(0, 12, 202)
    p2_source_timer = p2_slot.timers[(202, 0)]
    p2_timer_map = {
        (202, 0): copy.deepcopy(p2_source_timer),
        (201, 0): dataclasses.replace(copy.deepcopy(p2_source_timer), owner_id=201),
    }
    p2_base_composition = compose(p2_runtime.catalog, p2_slot.static, ())
    p2_hide_order = _mark_expire_on_hide(p2_timer_map, p2_base_composition, False)
    strict_timer_runtime = StackRuntime(_fixture_catalog()[0]); strict_timer_slot = strict_timer_runtime.install_slot(0, StaticContext(map_id=1)); strict_timer_runtime.apply(0, 2, ids["owner_stamina"])
    strict_timer_slot.timers[(ids["owner_stamina"], 0)].zero_pending = 1  # type: ignore[assignment]
    strict_timer_rejected = raises_status(lambda: strict_timer_runtime.tick_candidate_timers(0, 1), Status.INVALID_HANDLE)
    history_runtime = StackRuntime(_fixture_catalog()[0]); history_slot = history_runtime.install_slot(0, StaticContext(map_id=1)); history_runtime.apply(0, 1, ids["owner_awareness"])
    forged_history = dict(history_slot.transition_history[0]); forged_history["layerGeneration"] += 1; history_slot.transition_history[0] = MappingProxyType(forged_history)
    forged_history_result = history_runtime.clear(0)
    generated_false_origin = raises_status(lambda: GeneratedMetadata.from_dict({"hasTiredOriginKind": False, "tiredOriginKind": "FLED", "hasRequiredOwnerId": False, "requiredOwnerId": 0}), Status.INVALID_GENERATED_WRAPPER)
    generated_numeric_origin = raises_status(lambda: GeneratedMetadata.from_dict({"hasTiredOriginKind": True, "tiredOriginKind": 1, "hasRequiredOwnerId": True, "requiredOwnerId": 107}), Status.INVALID_GENERATED_WRAPPER)
    valid_p2_handle = same_key_a_apply.operation_results[0].handle
    malformed_handle_auth = all(raises_status(lambda value=value: Handle.from_dict({**to_data(valid_p2_handle), "authenticator": value}), Status.INVALID_HANDLE) for value in ("a" * 31, "A" * 32, "g" * 32))
    malformed_atoms = all(raises_status(lambda value=value: unwrap_atom(value), Status.INVALID_STATIC_DATA) for value in ({"raw": "x", "value": 1}, {"raw": 1, "symbol": None, "value": 1}, {"raw": "x", "symbol": {}, "value": 1}, {"raw": "x", "symbol": None, "value": 1, "extra": 2}))
    check("eighth-p2-canonical-timer-order-scalars-history-generated-handles-and-atoms", [item["ownerId"] for item in p2_hide_order] == [201, 202] and strict_timer_rejected and not forged_history_result.ok and generated_false_origin and generated_numeric_origin and malformed_handle_auth and malformed_atoms)

    # Ninth-pass authority regressions: expiry commits bind their exact
    # destructive snapshot, context-generation wrap rotates a separate domain,
    # and retained context tags are derived only from current live dependencies.
    recovery_snapshot_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="ninth-recovery-snapshot", runtime_nonce="recovery-snapshot")
    recovery_snapshot_slot = recovery_snapshot_runtime.install_slot(0, StaticContext(map_id=1))
    recovery_snapshot_runtime.apply(0, 2, ids["owner_stamina"])
    recovery_snapshot_runtime.tick_candidate_timers(0, 4)
    pre_sleep_plan = ExpiryPlan.from_dict(recovery_snapshot_runtime.pending_expiry_plans(0)[0])
    sleep_after_plan = recovery_snapshot_runtime.apply(0, 3, ids["owner_sleep"], 77)
    current_snapshot_plan = ExpiryPlan.from_dict(recovery_snapshot_runtime.pending_expiry_plans(0)[0])
    after_sleep_before_expiry = semantic_slot_snapshot(recovery_snapshot_runtime)
    stale_recovery_snapshot = recovery_snapshot_runtime.commit_expiry(pre_sleep_plan)
    check(
        "ninth-expiry-plan-binds-layer-generation-and-exact-recovery-removal-snapshot",
        sleep_after_plan.ok
        and pre_sleep_plan.layer_generation != current_snapshot_plan.layer_generation
        and pre_sleep_plan.removal_targets != current_snapshot_plan.removal_targets
        and stale_recovery_snapshot.status is Status.STALE_NOOP
        and not stale_recovery_snapshot.mutated
        and semantic_slot_snapshot(recovery_snapshot_runtime) == after_sleep_before_expiry
        and {(layer.owner_id, layer.instance_key) for layer in recovery_snapshot_slot.layers}
        == {(ids["owner_stamina"], 0), (ids["owner_sleep"], 77)},
    )

    context_wrap_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="ninth-context-wrap", runtime_nonce="context-wrap")
    context_wrap_slot = context_wrap_runtime.install_slot(0, StaticContext(map_id=1))
    context_wrap_runtime.apply(0, 2, ids["owner_stamina"])
    context_wrap_runtime.tick_candidate_timers(0, 4)
    pre_wrap_plan = ExpiryPlan.from_dict(context_wrap_runtime.pending_expiry_plans(0)[0])
    pre_wrap_context_incarnation = context_wrap_slot.static_context_incarnation

    def force_authenticated_static_generation_max(target_runtime: StackRuntime, target_slot: SlotRuntime) -> None:
        target_slot.static_context_generation = GEN_MAX
        target_slot.installed_context_authenticator = target_runtime._installed_context_authenticator(target_slot)
        target_slot.retained_context_authenticators = target_runtime._expected_retained_context_authenticators(target_slot, target_slot.timers)
        target_slot.mandatory_expiry_registry = target_runtime._expiry_registry(target_slot, target_slot.timers)

    force_authenticated_static_generation_max(context_wrap_runtime, context_wrap_slot)
    first_context_wrap = context_wrap_runtime.revalidate_retained_context(0, StaticContext(map_id=2))
    first_wrapped_incarnation = context_wrap_slot.static_context_incarnation
    force_authenticated_static_generation_max(context_wrap_runtime, context_wrap_slot)
    return_to_original_context = context_wrap_runtime.revalidate_retained_context(0, StaticContext(map_id=1))
    post_wrap_plan = ExpiryPlan.from_dict(context_wrap_runtime.pending_expiry_plans(0)[0])
    post_wrap_before_replay = semantic_slot_snapshot(context_wrap_runtime)
    stale_pre_wrap_plan = context_wrap_runtime.commit_expiry(pre_wrap_plan)
    check(
        "ninth-static-context-wrap-rotates-context-domain-and-stales-prewrap-plan",
        first_context_wrap.ok and return_to_original_context.ok
        and context_wrap_slot.static_context_generation == 1
        and pre_wrap_context_incarnation != first_wrapped_incarnation != context_wrap_slot.static_context_incarnation
        and pre_wrap_plan.static_context_incarnation != post_wrap_plan.static_context_incarnation
        and pre_wrap_plan.authenticator != post_wrap_plan.authenticator
        and stale_pre_wrap_plan.status is Status.STALE_NOOP
        and not stale_pre_wrap_plan.mutated
        and semantic_slot_snapshot(context_wrap_runtime) == post_wrap_before_replay,
    )

    exact_context_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="ninth-context-registry", runtime_nonce="context-registry")
    exact_context_slot = exact_context_runtime.install_slot(0, StaticContext(map_id=1))
    registry_sizes: list[int] = []
    for rebind_index in range(64):
        destination_map = 2 if rebind_index % 2 == 0 else 1
        rebind_result = exact_context_runtime.revalidate_retained_context(0, StaticContext(map_id=destination_map))
        registry_sizes.append(len(exact_context_slot.retained_context_authenticators) if rebind_result.ok else -1)
    injected_tag = "f" * 64
    if injected_tag == exact_context_slot.installed_context_authenticator:
        injected_tag = "e" * 64
    exact_context_slot.retained_context_authenticators = (*exact_context_slot.retained_context_authenticators, injected_tag)
    injected_registry_before = semantic_slot_snapshot(exact_context_runtime)
    injected_registry_result = exact_context_runtime.clear(0)
    check(
        "ninth-retained-context-registry-is-exact-bounded-and-zero-timer-constant",
        registry_sizes == [1] * 64
        and len(exact_context_slot.retained_context_authenticators) == 2
        and max(registry_sizes) <= MAX_RUNTIME_LAYERS + 1
        and not injected_registry_result.ok
        and injected_registry_result.status is Status.INVALID_HANDLE
        and not injected_registry_result.mutated
        and semantic_slot_snapshot(exact_context_runtime) == injected_registry_before,
    )

    layer_wrap_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="layer-wrap-domain", runtime_nonce="layer-wrap-domain")
    layer_wrap_slot = layer_wrap_runtime.install_slot(0, StaticContext(map_id=1))
    layer_wrap_runtime.apply(0, 2, ids["owner_stamina"])
    layer_wrap_runtime.tick_candidate_timers(0, 4)
    pre_layer_wrap_plan = ExpiryPlan.from_dict(layer_wrap_runtime.pending_expiry_plans(0)[0])
    pre_layer_wrap_incarnation = layer_wrap_slot.layer_incarnation
    force_authenticated_layer_generation(layer_wrap_runtime, layer_wrap_slot, GEN_MAX)
    wrap_away = layer_wrap_runtime.apply(0, 5, ids["owner_weather"])
    wrapped_modifier_handle = wrap_away.operation_results[0].handle
    wrap_back = layer_wrap_runtime.remove(0, wrapped_modifier_handle)
    current_layer_wrap_plan = ExpiryPlan.from_dict(layer_wrap_runtime.pending_expiry_plans(0)[0])
    restored_before_old_replay = semantic_slot_snapshot(layer_wrap_runtime)
    stale_pre_layer_wrap = layer_wrap_runtime.commit_expiry(pre_layer_wrap_plan)
    old_plan_left_current_intact = semantic_slot_snapshot(layer_wrap_runtime) == restored_before_old_replay
    current_layer_wrap_commit = layer_wrap_runtime.commit_expiry(current_layer_wrap_plan)

    resign_failure_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="layer-wrap-failure", runtime_nonce="layer-wrap-failure")
    resign_failure_slot = resign_failure_runtime.install_slot(0, StaticContext(map_id=1))
    resign_failure_runtime.apply(0, 2, ids["owner_stamina"])
    resign_failure_runtime.apply(0, 3, ids["owner_sleep"], 77)
    force_authenticated_layer_generation(resign_failure_runtime, resign_failure_slot, GEN_MAX)
    resign_failure_before = (semantic_slot_snapshot(resign_failure_runtime), resign_failure_slot.diagnostics)
    original_sign_timer_allocation = StackRuntime._sign_timer_allocation
    resign_attempts = 0

    def fail_second_layer_wrap_resign(runtime_arg: StackRuntime, slot_arg: SlotRuntime, timer_arg: CandidateTimer, **kwargs: Any) -> None:
        nonlocal resign_attempts
        resign_attempts += 1
        if resign_attempts == 2:
            raise ModelError(Status.INVALID_COMPOSITION, "injected layer-wrap timer re-sign failure")
        original_sign_timer_allocation(runtime_arg, slot_arg, timer_arg, **kwargs)

    StackRuntime._sign_timer_allocation = fail_second_layer_wrap_resign  # type: ignore[method-assign]
    try:
        injected_resign_failure = resign_failure_runtime.apply(0, 5, ids["owner_weather"])
    finally:
        StackRuntime._sign_timer_allocation = original_sign_timer_allocation  # type: ignore[method-assign]
    check(
        "layer-generation-wrap-rotates-auth-domain-and-stales-prewrap-expiry",
        wrap_away.ok and wrap_back.ok
        and layer_wrap_slot.layer_generation == 3
        and pre_layer_wrap_incarnation != current_layer_wrap_plan.layer_incarnation
        and pre_layer_wrap_plan.layer_generation == current_layer_wrap_plan.layer_generation == 2
        and pre_layer_wrap_plan.removal_targets == current_layer_wrap_plan.removal_targets
        and pre_layer_wrap_plan.authenticator != current_layer_wrap_plan.authenticator
        and stale_pre_layer_wrap.status is Status.STALE_NOOP and not stale_pre_layer_wrap.mutated
        and old_plan_left_current_intact
        and current_layer_wrap_commit.ok and current_layer_wrap_commit.mutated and not layer_wrap_slot.layers
        and resign_attempts == 2
        and not injected_resign_failure.ok and injected_resign_failure.status is Status.INVALID_COMPOSITION
        and not injected_resign_failure.mutated
        and (semantic_slot_snapshot(resign_failure_runtime), resign_failure_slot.diagnostics) == resign_failure_before,
    )

    carrier_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="layer-carrier", runtime_nonce="layer-carrier")
    carrier_slot = carrier_runtime.install_slot(0, StaticContext(map_id=1))
    carrier_apply = carrier_runtime.apply(0, 1, ids["owner_awareness"])
    pre_wrap_handle = carrier_apply.operation_results[0].handle
    pre_wrap_incarnation = carrier_slot.layer_incarnation
    pre_wrap_carrier_tag = carrier_slot.layer_incarnation_authenticator
    force_authenticated_layer_generation(carrier_runtime, carrier_slot, GEN_MAX)
    carrier_wrap = carrier_runtime.apply(0, 5, ids["owner_weather"])
    post_wrap_incarnation = carrier_slot.layer_incarnation
    post_wrap_carrier_tag = carrier_slot.layer_incarnation_authenticator
    old_handle_after_wrap = carrier_runtime.remove(0, pre_wrap_handle)

    carrier_slot.layer_incarnation = pre_wrap_incarnation
    replay_only_incarnation_before = (semantic_slot_snapshot(carrier_runtime), carrier_slot.diagnostics)
    replay_only_incarnation = carrier_runtime.remove(0, pre_wrap_handle)
    replay_only_incarnation_unchanged = (semantic_slot_snapshot(carrier_runtime), carrier_slot.diagnostics) == replay_only_incarnation_before
    carrier_slot.layer_incarnation = post_wrap_incarnation

    carrier_slot.layer_incarnation = pre_wrap_incarnation
    carrier_slot.layer_incarnation_authenticator = pre_wrap_carrier_tag
    replay_signed_carrier_before = (semantic_slot_snapshot(carrier_runtime), carrier_slot.diagnostics)
    replay_signed_carrier = carrier_runtime.clear(0)
    replay_signed_carrier_unchanged = (semantic_slot_snapshot(carrier_runtime), carrier_slot.diagnostics) == replay_signed_carrier_before
    carrier_slot.layer_incarnation = post_wrap_incarnation
    carrier_slot.layer_incarnation_authenticator = post_wrap_carrier_tag

    valid_serialization = runtime_to_dict(carrier_runtime)
    carrier_slot.layer_incarnation_authenticator = "0" * 64
    tampered_serialization_before = (semantic_slot_snapshot(carrier_runtime), carrier_slot.diagnostics)
    tampered_serialization_rejected = raises_status(lambda: runtime_to_dict(carrier_runtime), Status.INVALID_HANDLE)
    tampered_delta = carrier_runtime.clear(0)
    tampered_serialization_unchanged = (semantic_slot_snapshot(carrier_runtime), carrier_slot.diagnostics) == tampered_serialization_before
    carrier_slot.layer_incarnation_authenticator = post_wrap_carrier_tag

    foreign_carrier_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="layer-carrier", runtime_nonce="foreign-layer-carrier")
    foreign_carrier_slot = foreign_carrier_runtime.install_slot(0, StaticContext(map_id=1))
    carrier_slot.layer_incarnation = foreign_carrier_slot.layer_incarnation
    carrier_slot.layer_incarnation_authenticator = foreign_carrier_slot.layer_incarnation_authenticator
    foreign_carrier_before = (semantic_slot_snapshot(carrier_runtime), carrier_slot.diagnostics)
    foreign_carrier_result = carrier_runtime.clear(0)
    foreign_carrier_unchanged = (semantic_slot_snapshot(carrier_runtime), carrier_slot.diagnostics) == foreign_carrier_before
    check(
        "authoritative-layer-incarnation-carrier-rejects-replay-tamper-foreign-and-serializes",
        carrier_wrap.ok
        and pre_wrap_incarnation != post_wrap_incarnation
        and pre_wrap_carrier_tag != post_wrap_carrier_tag
        and old_handle_after_wrap.status is Status.INVALID_HANDLE
        and replay_only_incarnation.status is Status.INVALID_HANDLE and not replay_only_incarnation.mutated
        and replay_only_incarnation_unchanged
        and replay_signed_carrier.status is Status.INVALID_HANDLE and not replay_signed_carrier.mutated
        and replay_signed_carrier_unchanged
        and valid_serialization["slots"]["0"]["layerIncarnationAuthenticator"] == post_wrap_carrier_tag
        and tampered_serialization_rejected
        and tampered_delta.status is Status.INVALID_HANDLE and not tampered_delta.mutated
        and tampered_serialization_unchanged
        and foreign_carrier_result.status is Status.INVALID_HANDLE and not foreign_carrier_result.mutated
        and foreign_carrier_unchanged,
    )

    apply_rekey_runtime = StackRuntime(_fixture_catalog()[0], slot_count=2, handle_secret="atomic-apply-rekey", runtime_nonce="atomic-apply-rekey")
    apply_rekey_slot = apply_rekey_runtime.install_slot(0, StaticContext(map_id=1))
    apply_rekey_runtime.install_slot(1, StaticContext(map_id=1))
    apply_rekey_slot.next_entry_generation = GEN_MAX
    apply_rekey_before = exact_runtime_internal_snapshot(apply_rekey_runtime)
    original_apply_authority_builder = StackRuntime._layer_authority_for_slot
    apply_authority_faults = 0

    def fail_apply_prospective_authority(runtime_arg: StackRuntime, slot_arg: SlotRuntime, **kwargs: Any) -> LayerIncarnationAuthority:
        nonlocal apply_authority_faults
        if kwargs.get("runtime_epoch") == 2:
            apply_authority_faults += 1
            raise RuntimeError("injected prospective apply authority failure")
        return original_apply_authority_builder(runtime_arg, slot_arg, **kwargs)

    StackRuntime._layer_authority_for_slot = fail_apply_prospective_authority  # type: ignore[method-assign]
    try:
        failed_apply_rekey = apply_rekey_runtime.apply(0, 5, ids["owner_weather"])
    finally:
        StackRuntime._layer_authority_for_slot = original_apply_authority_builder  # type: ignore[method-assign]
    apply_rekey_unchanged = exact_runtime_internal_snapshot(apply_rekey_runtime) == apply_rekey_before
    successful_apply_rekey = apply_rekey_runtime.apply(0, 5, ids["owner_weather"])
    apply_rekey_runtime._validate_world_integrity()
    check(
        "global-apply-rekey-stages-epoch-and-authority-before-publication",
        apply_authority_faults == 1
        and not failed_apply_rekey.ok and failed_apply_rekey.status is Status.INVALID_COMPOSITION
        and not failed_apply_rekey.mutated and apply_rekey_unchanged
        and successful_apply_rekey.ok and successful_apply_rekey.mutated
        and apply_rekey_runtime.runtime_epoch == 2
        and all(
            authority is None or authority.runtime_epoch == 2
            for authority in apply_rekey_runtime._layer_authorities.values()
        ),
    )

    destroy_rekey_runtime = StackRuntime(_fixture_catalog()[0], slot_count=2, handle_secret="atomic-destroy-rekey", runtime_nonce="atomic-destroy-rekey")
    destroy_rekey_slot = destroy_rekey_runtime.install_slot(0, StaticContext(map_id=1), slot_generation=GEN_MAX)
    destroy_rekey_other = destroy_rekey_runtime.install_slot(1, StaticContext(map_id=1))
    destroy_rekey_runtime.apply(1, 1, ids["owner_awareness"])
    destroy_rekey_before = exact_runtime_internal_snapshot(destroy_rekey_runtime)
    original_destroy_authority_builder = StackRuntime._layer_authority_for_slot
    destroy_authority_faults = 0

    def fail_destroy_prospective_authority(runtime_arg: StackRuntime, slot_arg: SlotRuntime, **kwargs: Any) -> LayerIncarnationAuthority:
        nonlocal destroy_authority_faults
        if kwargs.get("runtime_epoch") == 2:
            destroy_authority_faults += 1
            raise RuntimeError("injected prospective destroy authority failure")
        return original_destroy_authority_builder(runtime_arg, slot_arg, **kwargs)

    StackRuntime._layer_authority_for_slot = fail_destroy_prospective_authority  # type: ignore[method-assign]
    destroy_failure_status = None
    try:
        destroy_rekey_runtime.destroy_slot(0)
    except ModelError as exc:
        destroy_failure_status = exc.status
    StackRuntime._layer_authority_for_slot = original_destroy_authority_builder  # type: ignore[method-assign]
    destroy_rekey_unchanged = exact_runtime_internal_snapshot(destroy_rekey_runtime) == destroy_rekey_before
    destroy_rekey_runtime.destroy_slot(0)
    destroy_rekey_runtime._validate_world_integrity()
    check(
        "global-destroy-rekey-stages-epoch-and-authority-before-publication",
        destroy_authority_faults == 1 and destroy_failure_status is Status.INVALID_COMPOSITION
        and destroy_rekey_unchanged
        and destroy_rekey_runtime.runtime_epoch == 2
        and not destroy_rekey_slot.live and destroy_rekey_slot.slot_generation == 1
        and destroy_rekey_other.live
        and all(
            authority is None or authority.runtime_epoch == 2
            for authority in destroy_rekey_runtime._layer_authorities.values()
        ),
    )

    class HostilePublicationRuntime(StackRuntime):
        blocked_assignment_attempts = 0

        def __setattr__(self, name: str, value: Any) -> None:
            if name in {"runtime_epoch", "_layer_authorities", "_secret", "_runtime_incarnation", "_catalog", "_staged_catalog", "data_generation", "_data_incarnation"}:
                type(self).blocked_assignment_attempts += 1
                raise RuntimeError(f"hostile publication assignment: {name}")
            super().__setattr__(name, value)

    def make_hostile_runtime(target: StackRuntime) -> HostilePublicationRuntime:
        object.__setattr__(target, "__class__", HostilePublicationRuntime)
        return target  # type: ignore[return-value]

    hostile_apply_base = StackRuntime(_fixture_catalog()[0], slot_count=2)
    hostile_apply_slot = hostile_apply_base.install_slot(0, StaticContext(map_id=1))
    hostile_apply_base.install_slot(1, StaticContext(map_id=1))
    hostile_apply_slot.next_entry_generation = GEN_MAX
    hostile_apply = make_hostile_runtime(hostile_apply_base)
    hostile_apply_before = exact_runtime_internal_snapshot(hostile_apply)
    hostile_apply_result = hostile_apply.apply(0, 5, ids["owner_weather"])

    hostile_destroy_base = StackRuntime(_fixture_catalog()[0], slot_count=2)
    hostile_destroy_base.install_slot(0, StaticContext(map_id=1), slot_generation=GEN_MAX)
    hostile_destroy_base.install_slot(1, StaticContext(map_id=1))
    hostile_destroy = make_hostile_runtime(hostile_destroy_base)
    hostile_destroy_before = exact_runtime_internal_snapshot(hostile_destroy)
    hostile_destroy_status = None
    try:
        hostile_destroy.destroy_slot(0)
    except ModelError as exc:
        hostile_destroy_status = exc.status

    hostile_terminal_base = StackRuntime(_fixture_catalog()[0], runtime_epoch=GEN_MAX)
    hostile_terminal_base.install_slot(0, StaticContext(map_id=1), slot_generation=GEN_MAX)
    hostile_terminal = make_hostile_runtime(hostile_terminal_base)
    hostile_terminal_before = exact_runtime_internal_snapshot(hostile_terminal)
    hostile_terminal_status = None
    try:
        hostile_terminal.destroy_slot(0)
    except ModelError as exc:
        hostile_terminal_status = exc.status

    hostile_context_base = StackRuntime(_fixture_catalog()[0])
    hostile_context_base.install_slot(0, StaticContext(map_id=1))
    hostile_context = make_hostile_runtime(hostile_context_base)
    hostile_context_before = exact_runtime_internal_snapshot(hostile_context)
    hostile_context_result = hostile_context.revalidate_retained_context(0, StaticContext(map_id=2))

    hostile_cold_base = StackRuntime(_fixture_catalog()[0])
    hostile_cold_base.stage_catalog(_fixture_catalog()[0])
    hostile_cold = make_hostile_runtime(hostile_cold_base)
    hostile_cold_before = exact_runtime_internal_snapshot(hostile_cold)
    hostile_cold_status = None
    try:
        hostile_cold.install_staged_catalog()
    except ModelError as exc:
        hostile_cold_status = exc.status
    check(
        "public-runtime-boundary-rejects-overridable-publication-subclasses-before-mutation",
        hostile_apply_result.status is Status.INVALID_HANDLE and not hostile_apply_result.mutated
        and exact_runtime_internal_snapshot(hostile_apply) == hostile_apply_before
        and hostile_destroy_status is Status.INVALID_HANDLE
        and exact_runtime_internal_snapshot(hostile_destroy) == hostile_destroy_before
        and hostile_terminal_status is Status.INVALID_HANDLE
        and exact_runtime_internal_snapshot(hostile_terminal) == hostile_terminal_before
        and hostile_context_result.status is Status.INVALID_HANDLE and not hostile_context_result.mutated
        and exact_runtime_internal_snapshot(hostile_context) == hostile_context_before
        and hostile_cold_status is Status.INVALID_HANDLE
        and exact_runtime_internal_snapshot(hostile_cold) == hostile_cold_before
        and HostilePublicationRuntime.blocked_assignment_attempts == 0,
    )
    for hostile_runtime in (hostile_apply, hostile_destroy, hostile_terminal, hostile_context, hostile_cold):
        object.__setattr__(hostile_runtime, "__class__", StackRuntime)

    class HostileSlotFinalizer:
        finalized = False

        def __del__(self) -> None:
            type(self).finalized = True

    finalizer_runtime = StackRuntime(_fixture_catalog()[0])
    finalizer_slot = finalizer_runtime.install_slot(0, StaticContext(map_id=1))
    finalizer_known_before = exact_runtime_internal_snapshot(finalizer_runtime)
    object.__getattribute__(finalizer_slot, "__dict__")["hostile_extra"] = HostileSlotFinalizer()
    finalizer_storage = object.__getattribute__(finalizer_slot, "__dict__")
    finalizer_result = finalizer_runtime.apply(0, 1, ids["owner_awareness"])
    finalized_during_publication = HostileSlotFinalizer.finalized
    finalizer_extra_retained = "hostile_extra" in finalizer_storage
    finalizer_known_unchanged = exact_runtime_internal_snapshot(finalizer_runtime) == finalizer_known_before
    finalizer_storage.pop("hostile_extra")
    finalizer_runtime._validate_world_integrity()
    check(
        "slot-storage-domain-rejects-hostile-finalizer-before-closed-publication",
        finalizer_result.status is Status.INVALID_HANDLE and not finalizer_result.mutated
        and not finalized_during_publication and finalizer_extra_retained
        and finalizer_known_unchanged and HostileSlotFinalizer.finalized,
    )

    hardened_runtime = StackRuntime(_fixture_catalog()[0], slot_count=2, handle_secret="hardened-publication", runtime_nonce="hardened-publication")
    hardened_slot = hardened_runtime.install_slot(0, StaticContext(map_id=1))
    hardened_runtime.install_slot(1, StaticContext(map_id=1))
    hardened_slot.next_entry_generation = GEN_MAX
    hardened_global_apply = hardened_runtime.apply(0, 5, ids["owner_weather"])
    hardened_context = hardened_runtime.revalidate_retained_context(0, StaticContext(map_id=2))
    hardened_serialized_once = canonical_json_bytes(runtime_to_dict(hardened_runtime))
    hardened_serialized_twice = canonical_json_bytes(runtime_to_dict(hardened_runtime))
    hardened_before_injected_stage = exact_runtime_internal_snapshot(hardened_runtime)
    original_hardened_stage = StackRuntime._stage_slot_replacements

    def fail_hardened_stage(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("injected hardened staging failure")

    StackRuntime._stage_slot_replacements = fail_hardened_stage  # type: ignore[method-assign]
    try:
        hardened_staging_failure = hardened_runtime.apply(0, 1, ids["owner_awareness"])
    finally:
        StackRuntime._stage_slot_replacements = original_hardened_stage  # type: ignore[method-assign]
    hardened_stage_unchanged = exact_runtime_internal_snapshot(hardened_runtime) == hardened_before_injected_stage
    hardened_followup = hardened_runtime.apply(0, 1, ids["owner_awareness"])
    hardened_runtime._validate_world_integrity()
    check(
        "exact-runtime-hardened-publication-success-staging-failure-and-serialization",
        hardened_global_apply.ok and hardened_runtime.runtime_epoch == 2
        and hardened_context.ok
        and hardened_serialized_once == hardened_serialized_twice
        and not hardened_staging_failure.ok and hardened_staging_failure.status is Status.INVALID_COMPOSITION
        and not hardened_staging_failure.mutated and hardened_stage_unchanged
        and hardened_followup.ok and hardened_followup.mutated,
    )

    class GuardBypassRuntime(StackRuntime):
        virtual_guard_calls = 0
        virtual_validator_calls = 0

        def _require_exact_runtime(self) -> None:
            type(self).virtual_guard_calls += 1
            object.__setattr__(self, "runtime_epoch", 99)

        def _validate_world_integrity(self) -> None:
            type(self).virtual_validator_calls += 1
            object.__setattr__(self, "runtime_epoch", 98)

    guard_bypass_base = StackRuntime(_fixture_catalog()[0], slot_count=2)
    guard_bypass_base.install_slot(0, StaticContext(map_id=1))
    guard_bypass = guard_bypass_base
    object.__setattr__(guard_bypass, "__class__", GuardBypassRuntime)
    guard_bypass_before = exact_runtime_internal_snapshot(guard_bypass)
    guard_bypass_apply = guard_bypass.apply(0, 1, ids["owner_awareness"])
    guard_bypass_install_status = None
    try:
        guard_bypass.install_slot(1, StaticContext(map_id=1))
    except ModelError as exc:
        guard_bypass_install_status = exc.status
    guard_bypass_serialize_status = None
    try:
        runtime_to_dict(guard_bypass)
    except ModelError as exc:
        guard_bypass_serialize_status = exc.status
    guard_bypass_stage_status = None
    try:
        guard_bypass.stage_catalog(_fixture_catalog()[0])
    except ModelError as exc:
        guard_bypass_stage_status = exc.status
    check(
        "module-level-runtime-guard-cannot-be-overridden-or-side-effect-dispatched",
        guard_bypass_apply.status is Status.INVALID_HANDLE and not guard_bypass_apply.mutated
        and guard_bypass_install_status is Status.INVALID_HANDLE
        and guard_bypass_serialize_status is Status.INVALID_HANDLE
        and guard_bypass_stage_status is Status.INVALID_HANDLE
        and GuardBypassRuntime.virtual_guard_calls == 0
        and GuardBypassRuntime.virtual_validator_calls == 0
        and exact_runtime_internal_snapshot(guard_bypass) == guard_bypass_before,
    )
    object.__setattr__(guard_bypass, "__class__", StackRuntime)

    class NestedRuntimeFinalizer:
        finalized_count = 0

        def __del__(self) -> None:
            type(self).finalized_count += 1

    nested_graph_ok = True
    for target_kind in ("composition", "timer", "diagnostics", "layer", "static", "winner"):
        nested_runtime = StackRuntime(_fixture_catalog()[0])
        nested_slot = nested_runtime.install_slot(0, StaticContext(map_id=1))
        if target_kind == "timer":
            nested_runtime.apply(0, 2, ids["owner_stamina"])
            nested_target = nested_slot.timers[(ids["owner_stamina"], 0)]
        elif target_kind == "layer":
            nested_runtime.apply(0, 1, ids["owner_awareness"])
            nested_target = nested_slot.layers[0]
        elif target_kind == "composition":
            nested_target = nested_slot.composition
        elif target_kind == "diagnostics":
            nested_target = nested_slot.diagnostics
        elif target_kind == "static":
            nested_target = nested_slot.static
        else:
            nested_target = nested_slot.composition.winner
        assert nested_target is not None
        nested_storage = object.__getattribute__(nested_target, "__dict__")
        finalized_before = NestedRuntimeFinalizer.finalized_count
        nested_storage["hostile_extra"] = NestedRuntimeFinalizer()
        nested_known_before = exact_runtime_internal_snapshot(nested_runtime)
        nested_result = nested_runtime.clear(0)
        finalized_during = NestedRuntimeFinalizer.finalized_count != finalized_before
        nested_retained = "hostile_extra" in nested_storage
        nested_known_unchanged = exact_runtime_internal_snapshot(nested_runtime) == nested_known_before
        nested_storage.pop("hostile_extra")
        nested_runtime._validate_world_integrity()
        nested_graph_ok = nested_graph_ok and nested_result.status is Status.INVALID_HANDLE and not nested_result.mutated and not finalized_during and nested_retained and nested_known_unchanged and NestedRuntimeFinalizer.finalized_count == finalized_before + 1
    check(
        "recursive-runtime-graph-rejects-open-nested-dataclasses-before-finalizer-capable-discard",
        nested_graph_ok,
    )

    # Final root-closure pass: the runtime root, catalog and private authority
    # domain are part of the authenticated world, and validation itself is a
    # callback-free operation over an explicit type table.
    root_runtime = StackRuntime(_fixture_catalog()[0], handle_secret="root-closure", runtime_nonce="root-closure")
    root_slot = root_runtime.install_slot(0, StaticContext(map_id=1))
    root_epoch_before = exact_runtime_internal_snapshot(root_runtime)
    object.__setattr__(root_runtime, "runtime_epoch", 0)
    epoch_zero_before = exact_runtime_internal_snapshot(root_runtime)
    epoch_zero_result = root_runtime.apply(0, 1, ids["owner_awareness"])
    epoch_zero_serialize = raises_status(lambda: runtime_to_dict(root_runtime), Status.INVALID_HANDLE)
    epoch_zero_unchanged = exact_runtime_internal_snapshot(root_runtime) == epoch_zero_before
    object.__setattr__(root_runtime, "runtime_epoch", 1)
    catalog_before = root_runtime._catalog.default_controller_id
    object.__setattr__(root_runtime._catalog, "default_controller_id", 0xFFFF)
    catalog_mutation_result = root_runtime.apply(0, 1, ids["owner_awareness"])
    object.__setattr__(root_runtime._catalog, "default_controller_id", catalog_before)
    secret_before = object.__getattribute__(root_runtime, "_secret")
    object.__setattr__(root_runtime, "_secret", b"bad")
    secret_mutation_result = root_runtime.apply(0, 1, ids["owner_awareness"])
    object.__setattr__(root_runtime, "_secret", secret_before)

    class AuthorityFinalizer:
        fired = False

        def __del__(self) -> None:
            type(self).fired = True

    authority = object.__getattribute__(root_runtime, "_layer_authorities").get(0)
    assert type(authority) is LayerIncarnationAuthority
    authority_storage = object.__getattribute__(authority, "__dict__")
    authority_storage["hostile_extra"] = AuthorityFinalizer()
    authority_snapshot = exact_runtime_internal_snapshot(root_runtime)
    authority_result = root_runtime.apply(0, 1, ids["owner_awareness"])
    authority_unchanged = exact_runtime_internal_snapshot(root_runtime) == authority_snapshot
    authority_not_finalized = not AuthorityFinalizer.fired and "hostile_extra" in authority_storage
    authority_storage.pop("hostile_extra")
    StackRuntime._validate_world_integrity(root_runtime)
    check(
        "final-root-catalog-secret-epoch-and-private-authority-graph-is-closed",
        root_epoch_before == exact_runtime_internal_snapshot(root_runtime)
        and epoch_zero_result.status is Status.INVALID_HANDLE and not epoch_zero_result.mutated
        and epoch_zero_serialize and epoch_zero_unchanged
        and catalog_mutation_result.status is Status.INVALID_STATIC_DATA and not catalog_mutation_result.mutated
        and secret_mutation_result.status is Status.INVALID_HANDLE and not secret_mutation_result.mutated
        and authority_result.status is Status.INVALID_HANDLE and not authority_result.mutated
        and authority_unchanged and authority_not_finalized and AuthorityFinalizer.fired
        and not root_slot.layers,
    )

    class AllBoundaryBypass(StackRuntime):
        dispatches = 0

        def _validate_world_integrity(self) -> None:
            type(self).dispatches += 1
            object.__setattr__(self, "runtime_epoch", 77)

        def _convenience_failure(self, *args: Any, **kwargs: Any) -> DeltaResult:
            type(self).dispatches += 1
            object.__setattr__(self, "runtime_epoch", 78)
            raise RuntimeError("virtual failure fallback dispatched")

        def _slot(self, slot_index: int) -> SlotRuntime:
            type(self).dispatches += 1
            object.__setattr__(self, "runtime_epoch", 79)
            raise RuntimeError("virtual slot lookup dispatched")

    boundary_base = StackRuntime(_fixture_catalog()[0])
    boundary_slot = boundary_base.install_slot(0, StaticContext(map_id=1))
    object.__setattr__(boundary_base, "__class__", AllBoundaryBypass)
    boundary_before = exact_runtime_internal_snapshot(boundary_base)
    typed_boundary_results = (
        boundary_base.apply_stack_delta(0, 1, (), "guard"),
        boundary_base.apply(0, 1, ids["owner_awareness"]),
        boundary_base.replace(0, ids["owner_awareness"], 0, 1),
        boundary_base.remove(0, Handle(1, 0, 1, 1, 0, 1, "0" * 64)),
        boundary_base.remove_owner(0, ids["owner_awareness"]),
        boundary_base.clear(0),
        boundary_base.commit_expiry({}),
        boundary_base.revalidate_retained_context(0, StaticContext(map_id=2)),
    )
    raising_boundary_calls = (
        lambda: boundary_base.stage_catalog(_fixture_catalog()[0]),
        lambda: boundary_base.install_staged_catalog(),
        lambda: boundary_base.install_slot(1, StaticContext(map_id=1)),
        lambda: boundary_base.destroy_slot(0),
        lambda: boundary_base.tick_candidate_timers(0),
        lambda: boundary_base.set_presentation_gate(0, True),
        lambda: boundary_base.pending_expiry_plans(0),
        lambda: boundary_base.bind_delta_operation(DeltaOperation("clear", DeltaOpKind.CLEAR)),
        lambda: runtime_to_dict(boundary_base),
        lambda: boundary_base.catalog,
        lambda: boundary_base.data_incarnation,
        lambda: boundary_base.runtime_incarnation,
    )
    boundary_raises = all(raises_status(callback, Status.INVALID_HANDLE) for callback in raising_boundary_calls)
    check(
        "final-every-public-runtime-entry-guards-before-catch-or-self-dispatch",
        all(result.status is Status.INVALID_HANDLE and not result.mutated for result in typed_boundary_results)
        and boundary_raises and AllBoundaryBypass.dispatches == 0
        and exact_runtime_internal_snapshot(boundary_base) == boundary_before
        and boundary_slot.live,
    )
    object.__setattr__(boundary_base, "__class__", StackRuntime)

    class ProbeMeta(type):
        probes = 0

        def __getattribute__(cls, name: str) -> Any:
            if name in {"__dataclass_fields__", "__mro__", "__name__"}:
                ProbeMeta.probes += 1
            return type.__getattribute__(cls, name)

    class HostileReflectionValue(metaclass=ProbeMeta):
        pass

    class HostileProxyBacking(Mapping[str, Any]):
        callbacks = 0

        def __getitem__(self, key: str) -> Any:
            type(self).callbacks += 1
            raise RuntimeError("backing lookup")

        def __iter__(self) -> Any:
            type(self).callbacks += 1
            raise RuntimeError("backing iteration")

        def __len__(self) -> int:
            type(self).callbacks += 1
            raise RuntimeError("backing length")

    audit_gc_events = 0

    def audit_probe(event: str, args: tuple[Any, ...]) -> None:
        nonlocal audit_gc_events
        if event == "gc.get_referents":
            audit_gc_events += 1

    sys.addaudithook(audit_probe)
    reflection_rejected = raises_status(lambda: _validate_closed_runtime_graph(HostileReflectionValue()), Status.INVALID_HANDLE)
    proxy_backing = HostileProxyBacking()
    builtin_proxy = __import__("types").MappingProxyType(proxy_backing)
    proxy_rejected = raises_status(lambda: _validate_closed_runtime_graph(builtin_proxy), Status.INVALID_HANDLE)
    check(
        "final-closed-graph-validation-is-nonreflective-and-never-audits-mapping-proxy-backing",
        reflection_rejected and proxy_rejected and ProbeMeta.probes == 0
        and HostileProxyBacking.callbacks == 0 and audit_gc_events == 0,
    )

    class EnumFinalizer:
        fired = False

        def __del__(self) -> None:
            type(self).fired = True

    forged_calm = str.__new__(SemanticRole, SemanticRole.CALM.value)
    forged_storage = object.__getattribute__(forged_calm, "__dict__")
    forged_storage.update({"_value_": SemanticRole.CALM.value, "_name_": "CALM", "__objclass__": SemanticRole, "hostile_extra": EnumFinalizer()})
    forged_rejected = raises_status(lambda: _validate_closed_runtime_graph(forged_calm), Status.INVALID_HANDLE)
    forged_not_finalized = not EnumFinalizer.fired and "hostile_extra" in forged_storage
    forged_storage.pop("hostile_extra")
    check(
        "final-enum-domain-requires-exact-class-canonical-singleton-and-closed-storage",
        forged_rejected and forged_not_finalized and EnumFinalizer.fired
        and SemanticRole.CALM is SemanticRole.__members__["CALM"],
    )

    atomic_failure_ok = True
    for operation_kind, injected_exception in (
        ("apply", ModelError(Status.INVALID_HANDLE, "typed prospective apply failure")),
        ("apply", RuntimeError("hostile prospective apply failure")),
        ("destroy", ModelError(Status.INVALID_HANDLE, "typed prospective destroy failure")),
        ("destroy", RuntimeError("hostile prospective destroy failure")),
    ):
        failure_runtime = StackRuntime(_fixture_catalog()[0], slot_count=2)
        if operation_kind == "apply":
            failure_slot = failure_runtime.install_slot(0, StaticContext(map_id=1))
            failure_runtime.install_slot(1, StaticContext(map_id=1))
            failure_slot.next_entry_generation = GEN_MAX
        else:
            failure_slot = failure_runtime.install_slot(0, StaticContext(map_id=1), slot_generation=GEN_MAX)
            failure_runtime.install_slot(1, StaticContext(map_id=1))
        failure_before = exact_runtime_internal_snapshot(failure_runtime)
        failure_diagnostics = tuple(slot.diagnostics for slot in failure_runtime.slots.values())
        original_authority_builder = StackRuntime._layer_authority_for_slot

        def injected_authority_builder(runtime_arg: StackRuntime, slot_arg: SlotRuntime, **kwargs: Any) -> LayerIncarnationAuthority:
            if runtime_arg is failure_runtime and kwargs.get("runtime_epoch") == 2:
                raise injected_exception
            return original_authority_builder(runtime_arg, slot_arg, **kwargs)

        StackRuntime._layer_authority_for_slot = injected_authority_builder  # type: ignore[method-assign]
        try:
            if operation_kind == "apply":
                failure_result = failure_runtime.apply(0, 5, ids["owner_weather"])
                failure_status = failure_result.status
                failure_mutated = failure_result.mutated
            else:
                failure_status = None
                try:
                    failure_runtime.destroy_slot(0)
                except ModelError as exc:
                    failure_status = exc.status
                failure_mutated = False
        finally:
            StackRuntime._layer_authority_for_slot = original_authority_builder  # type: ignore[method-assign]
        atomic_failure_ok = atomic_failure_ok and failure_status in {Status.INVALID_HANDLE, Status.INVALID_COMPOSITION} and not failure_mutated and exact_runtime_internal_snapshot(failure_runtime) == failure_before and tuple(slot.diagnostics for slot in failure_runtime.slots.values()) == failure_diagnostics
        StackRuntime._validate_world_integrity(failure_runtime)
    check(
        "final-typed-and-hostile-prospective-rekey-failures-preserve-world-and-diagnostics",
        atomic_failure_ok,
    )

    boundary_count_accepts = True
    try:
        _validate_closed_runtime_graph(tuple(range(100000)), "boundaryCount")
        _validate_closed_runtime_graph(tuple(reversed(range(100000))), "boundaryCountReversed")
        _validate_closed_runtime_graph(tuple(SemanticRole.CALM for _ in range(100000)), "boundaryEnumCount")
    except ModelError:
        boundary_count_accepts = False
    over_scalar_rejected = raises_status(lambda: _validate_closed_runtime_graph(tuple(range(100001)), "overScalarCount"), Status.INVALID_HANDLE)
    over_enum_rejected = raises_status(lambda: _validate_closed_runtime_graph(tuple(SemanticRole.CALM for _ in range(100001)), "overEnumCount"), Status.INVALID_HANDLE)
    check(
        "final-closed-graph-object-bound-counts-every-scalar-and-enum-leaf",
        boundary_count_accepts and over_scalar_rejected and over_enum_rejected,
    )

    audit_mutation_runtime = StackRuntime(
        _fixture_catalog()[0], handle_secret="audit-callback-free",
        runtime_nonce="audit-callback-free",
    )
    audit_mutation_slot = audit_mutation_runtime.install_slot(0, StaticContext(map_id=1))
    audited_identity_events = 0
    mutation_enabled = False

    def audited_identity_mutator(event: str, args: tuple[Any, ...]) -> None:
        nonlocal audited_identity_events
        if event == "builtins.id":
            audited_identity_events += 1
            if mutation_enabled:
                object.__setattr__(audit_mutation_slot, "presentation_gate", True)

    sys.addaudithook(audited_identity_mutator)
    getattr(__import__("builtins"), "id")(None)
    audit_baseline = audited_identity_events
    mutation_enabled = True
    try:
        audit_apply = audit_mutation_runtime.apply(0, 5, ids["owner_weather"])
    finally:
        mutation_enabled = False
    StackRuntime._validate_world_integrity(audit_mutation_runtime)
    check(
        "final-audited-identity-hook-cannot-mutate-runtime-during-callback-free-preflight",
        audit_baseline >= 1 and audited_identity_events == audit_baseline
        and audit_apply.ok and audit_apply.mutated
        and audit_mutation_slot.presentation_gate is False
        and len(audit_mutation_slot.layers) == 1,
    )

    incarnation_rejections_ok = True
    malformed_incarnations = (
        ("_runtime_incarnation", "not-auth"),
        ("_runtime_incarnation", "a" * 63),
        ("_runtime_incarnation", "A" * 64),
        ("_runtime_incarnation", "g" * 64),
        ("_runtime_incarnation", INITIAL_DATA_INCARCATION),
        ("_data_incarnation", "not-auth"),
        ("_data_incarnation", "a" * 63),
        ("_data_incarnation", "A" * 64),
        ("_data_incarnation", "g" * 64),
        ("_data_incarnation", "data-incarnation:2"),
        ("_data_incarnation", "data-incarnation:01"),
    )
    for field_name, malformed_value in malformed_incarnations:
        malformed_runtime = StackRuntime(
            _fixture_catalog()[0], handle_secret="malformed-incarnation",
            runtime_nonce=f"{field_name}:{malformed_value}",
        )
        object.__setattr__(malformed_runtime, field_name, malformed_value)
        malformed_before = exact_runtime_internal_snapshot(malformed_runtime)
        validation_status = None
        try:
            StackRuntime._validate_world_integrity(malformed_runtime)
        except ModelError as exc:
            validation_status = exc.status
        install_context = StaticContext(
            map_id=1,
            data_incarnation=malformed_value if field_name == "_data_incarnation" else INITIAL_DATA_INCARCATION,
        )
        install_status = None
        try:
            malformed_runtime.install_slot(0, install_context)
        except ModelError as exc:
            install_status = exc.status
        malformed_apply = malformed_runtime.apply(0, 1, ids["owner_awareness"])
        serialize_status = None
        try:
            runtime_to_dict(malformed_runtime)
        except ModelError as exc:
            serialize_status = exc.status
        incarnation_rejections_ok = incarnation_rejections_ok and (
            validation_status in {Status.INVALID_HANDLE, Status.INVALID_STATIC_DATA}
            and install_status in {Status.INVALID_HANDLE, Status.INVALID_STATIC_DATA}
            and malformed_apply.status in {Status.INVALID_HANDLE, Status.INVALID_STATIC_DATA}
            and not malformed_apply.mutated
            and serialize_status in {Status.INVALID_HANDLE, Status.INVALID_STATIC_DATA}
            and exact_runtime_internal_snapshot(malformed_runtime) == malformed_before
            and not malformed_runtime.slots[0].live
        )
    check(
        "final-runtime-and-data-incarnations-require-canonical-tags-or-exact-initial-sentinel",
        incarnation_rejections_ok,
    )

    root_substitution_ok = True
    for field_name, substitute in (
        ("_secret", b"s" * 32),
        ("_root_anchor", b"a" * 32),
        ("_secret_authenticator", "b" * 64),
    ):
        substitution_runtime = StackRuntime(
            _fixture_catalog()[0], handle_secret="root-substitution",
            runtime_nonce=f"root-substitution:{field_name}",
        )
        original_value = object.__getattribute__(substitution_runtime, field_name)
        if substitute == original_value:
            substitute = b"z" * 32 if type(substitute) is bytes else "c" * 64
        object.__setattr__(substitution_runtime, field_name, substitute)
        substitution_before = exact_runtime_internal_snapshot(substitution_runtime)
        validate_status = None
        try:
            StackRuntime._validate_world_integrity(substitution_runtime)
        except ModelError as exc:
            validate_status = exc.status
        install_status = None
        try:
            substitution_runtime.install_slot(0, StaticContext(map_id=1))
        except ModelError as exc:
            install_status = exc.status
        substitution_apply = substitution_runtime.apply(0, 1, ids["owner_awareness"])
        serialize_status = None
        try:
            runtime_to_dict(substitution_runtime)
        except ModelError as exc:
            serialize_status = exc.status
        root_substitution_ok = root_substitution_ok and (
            validate_status is Status.INVALID_HANDLE
            and install_status is Status.INVALID_HANDLE
            and substitution_apply.status is Status.INVALID_HANDLE
            and not substitution_apply.mutated
            and serialize_status is Status.INVALID_HANDLE
            and exact_runtime_internal_snapshot(substitution_runtime) == substitution_before
            and not substitution_runtime.slots[0].live
        )
        object.__setattr__(substitution_runtime, field_name, original_value)
        StackRuntime._validate_world_integrity(substitution_runtime)
    check(
        "final-independent-root-anchor-rejects-same-shape-secret-and-anchor-substitution",
        root_substitution_ok,
    )

    root_construction_runtime = StackRuntime(
        _fixture_catalog()[0], handle_secret="root-construction-rotation",
        runtime_nonce="root-construction-rotation",
    )
    initial_root_tag = root_construction_runtime._secret_authenticator
    StackRuntime._validate_world_integrity(root_construction_runtime)
    initial_wire = canonical_json_bytes(runtime_to_dict(root_construction_runtime))
    initial_roundtrip = canonical_json_bytes(json.loads(initial_wire))
    root_construction_runtime.stage_catalog(_fixture_catalog()[0])
    cold_generation = root_construction_runtime.install_staged_catalog()
    cold_root_tag = root_construction_runtime._secret_authenticator
    StackRuntime._validate_world_integrity(root_construction_runtime)
    cold_wire = canonical_json_bytes(runtime_to_dict(root_construction_runtime))
    cold_roundtrip = canonical_json_bytes(json.loads(cold_wire))

    root_terminal_runtime = StackRuntime(
        _fixture_catalog()[0], runtime_epoch=GEN_MAX,
        handle_secret="root-terminal-rotation", runtime_nonce="root-terminal-rotation",
    )
    terminal_initial_tag = root_terminal_runtime._secret_authenticator
    root_terminal_slot = root_terminal_runtime.install_slot(0, StaticContext(map_id=1))
    root_terminal_slot.next_entry_generation = GEN_MAX
    terminal_rotation_result = root_terminal_runtime.apply(0, 5, ids["owner_weather"])
    terminal_rotated_tag = root_terminal_runtime._secret_authenticator
    StackRuntime._validate_world_integrity(root_terminal_runtime)
    terminal_wire = canonical_json_bytes(runtime_to_dict(root_terminal_runtime))
    terminal_roundtrip = canonical_json_bytes(json.loads(terminal_wire))
    check(
        "final-root-authenticator-constructs-rotates-and-serializes-canonically",
        initial_root_tag != cold_root_tag and cold_generation == 2
        and terminal_initial_tag != terminal_rotated_tag
        and terminal_rotation_result.status is Status.RUNTIME_EPOCH_RESTARTED
        and root_terminal_runtime.runtime_epoch == 1
        and initial_wire == initial_roundtrip
        and cold_wire == cold_roundtrip
        and terminal_wire == terminal_roundtrip,
    )

    class MutatingFieldDescriptor:
        callbacks = 0
        target: SlotRuntime | None = None

        def __get__(self, instance: Any, owner: Any = None) -> Any:
            type(self).callbacks += 1
            target = type(self).target
            if type(target) is SlotRuntime:
                object.__setattr__(target, "presentation_gate", True)
            return 0

    descriptor_rejection_ok = True
    descriptor_cases = (
        (Composition, "effective_hash", "apply"),
        (CandidateTimer, "remaining_ticks", "tick"),
        (SlotDiagnostics, "stale_handle_count", "clear"),
        (Layer, "definition_id", "remove_owner"),
    )
    for target_type, field_name, operation_name in descriptor_cases:
        descriptor_runtime = StackRuntime(
            _fixture_catalog()[0], handle_secret="descriptor-rejection",
            runtime_nonce=f"descriptor:{target_type.__name__}:{field_name}",
        )
        descriptor_slot = descriptor_runtime.install_slot(0, StaticContext(map_id=1))
        if target_type is CandidateTimer:
            descriptor_runtime.apply(0, 2, ids["owner_stamina"])
        elif target_type is Layer:
            descriptor_runtime.apply(0, 1, ids["owner_awareness"])
        descriptor_before = exact_runtime_internal_snapshot(descriptor_runtime)
        class_storage = type.__getattribute__(target_type, "__dict__")
        had_carrier = field_name in class_storage
        original_carrier = class_storage[field_name] if had_carrier else _ABSENT_CLASS_FIELD
        MutatingFieldDescriptor.callbacks = 0
        MutatingFieldDescriptor.target = descriptor_slot
        if target_type is Composition:
            descriptor: Any = property(MutatingFieldDescriptor().__get__)
        else:
            descriptor = MutatingFieldDescriptor()
        setattr(target_type, field_name, descriptor)
        rejected_status = None
        rejected_mutated = False
        try:
            if operation_name == "apply":
                rejected = descriptor_runtime.apply(0, 1, ids["owner_awareness"])
                rejected_status, rejected_mutated = rejected.status, rejected.mutated
            elif operation_name == "tick":
                try:
                    descriptor_runtime.tick_candidate_timers(0)
                except ModelError as exc:
                    rejected_status = exc.status
            elif operation_name == "clear":
                rejected = descriptor_runtime.clear(0)
                rejected_status, rejected_mutated = rejected.status, rejected.mutated
            else:
                rejected = descriptor_runtime.remove_owner(0, ids["owner_awareness"])
                rejected_status, rejected_mutated = rejected.status, rejected.mutated
        finally:
            if had_carrier:
                setattr(target_type, field_name, original_carrier)
            else:
                delattr(target_type, field_name)
            MutatingFieldDescriptor.target = None
        descriptor_rejection_ok = descriptor_rejection_ok and (
            rejected_status is Status.INVALID_HANDLE and not rejected_mutated
            and MutatingFieldDescriptor.callbacks == 0
            and descriptor_slot.presentation_gate is False
            and exact_runtime_internal_snapshot(descriptor_runtime) == descriptor_before
        )
        StackRuntime._validate_world_integrity(descriptor_runtime)
    check(
        "final-runtime-dataclass-properties-and-descriptors-reject-without-dispatch",
        descriptor_rejection_ok,
    )

    detached_runtime = StackRuntime(
        _fixture_catalog()[0], handle_secret="detached-runtime-wire",
        runtime_nonce="detached-runtime-wire",
    )
    detached_slot = detached_runtime.install_slot(
        0, StaticContext(map_id=1, extras={"nested": {"value": 7}}),
    )
    detached_runtime.apply(0, 1, ids["owner_awareness"])
    detached_runtime.apply(0, 2, ids["owner_stamina"])
    detached_wire = runtime_to_dict(detached_runtime)
    prior_wire = runtime_to_dict(detached_runtime)
    prior_wire_bytes = canonical_json_bytes(prior_wire)
    detached_runtime_before = exact_runtime_internal_snapshot(detached_runtime)

    def exact_json_wire(value: Any) -> bool:
        if value is None or type(value) in (bool, int, float, str):
            return True
        if type(value) is list:
            return all(exact_json_wire(item) for item in value)
        if type(value) is dict:
            return all(type(key) is str and exact_json_wire(item) for key, item in value.items())
        return False

    detached_slot_wire = detached_wire["slots"]["0"]
    detached_slot_wire["layers"][0]["definitionId"] = 0xFFFF
    detached_slot_wire["timers"][0]["remainingTicks"] = 200
    detached_slot_wire["diagnostics"]["staleHandleCount"] = 99
    detached_slot_wire["effective"]["effectiveHash"] = "forged-effective"
    detached_slot_wire["static"]["context"]["extras"] = {"forged": True}
    detached_slot_wire["layerAuthority"]["authenticator"] = "0" * 64
    detached_slot_wire["capturedSpawnPolicyValues"]["maximumDistance"] = 99
    detached_wire["runtimeIncarnation"] = "forged-root"
    wire_mutation_left_runtime_unchanged = exact_runtime_internal_snapshot(detached_runtime) == detached_runtime_before
    detached_runtime.tick_candidate_timers(0, 1)
    runtime_mutation_left_prior_wire_unchanged = canonical_json_bytes(prior_wire) == prior_wire_bytes
    detached_roundtrip = json.loads(canonical_json_bytes(runtime_to_dict(detached_runtime)))
    check(
        "final-runtime-wire-is-deeply-detached-bidirectionally-and-json-closed",
        exact_json_wire(detached_wire) and exact_json_wire(prior_wire)
        and wire_mutation_left_runtime_unchanged
        and runtime_mutation_left_prior_wire_unchanged
        and detached_roundtrip == runtime_to_dict(detached_runtime)
        and detached_slot.presentation_gate is False,
    )

    class HostileExpiryKey:
        callbacks = 0
        target: SlotRuntime | None = None

        @classmethod
        def mutate(cls) -> None:
            cls.callbacks += 1
            if type(cls.target) is SlotRuntime:
                object.__setattr__(cls.target, "presentation_gate", True)

        def __hash__(self) -> int:
            type(self).mutate()
            return hash("runtimeEpoch")

        def __eq__(self, other: Any) -> bool:
            type(self).mutate()
            return False

        def __str__(self) -> str:
            type(self).mutate()
            return "runtimeEpoch"

    hostile_key_runtime = StackRuntime(
        _fixture_catalog()[0], handle_secret="hostile-expiry-key",
        runtime_nonce="hostile-expiry-key",
    )
    hostile_key_slot = hostile_key_runtime.install_slot(0, StaticContext(map_id=1))
    hostile_key_runtime.apply(0, 3, ids["owner_sleep"], 404)
    hostile_key_runtime.tick_candidate_timers(0, 2)
    hostile_key_plan = dict(hostile_key_runtime.pending_expiry_plans(0)[0])
    hostile_key_plan[HostileExpiryKey()] = "hostile"
    HostileExpiryKey.callbacks = 0
    HostileExpiryKey.target = hostile_key_slot
    hostile_key_before = exact_runtime_internal_snapshot(hostile_key_runtime)
    hostile_key_result = hostile_key_runtime.commit_expiry(hostile_key_plan)
    hostile_key_after = exact_runtime_internal_snapshot(hostile_key_runtime)
    HostileExpiryKey.target = None
    check(
        "stable-hostile-expiry-object-key-rejects-before-hash-equality-or-string-callback",
        hostile_key_result.status is Status.INVALID_HANDLE and not hostile_key_result.mutated
        and HostileExpiryKey.callbacks == 0
        and hostile_key_slot.presentation_gate is False
        and hostile_key_before == hostile_key_after,
    )

    enum_closed_map = ClosedMap(((SemanticRole.CALM, "calm"), (SemanticRole.TIRED, "tired")))
    enum_callback_runtime = StackRuntime(
        _fixture_catalog()[0], handle_secret="closed-map-enum-callback",
        runtime_nonce="closed-map-enum-callback",
    )
    enum_callback_slot = enum_callback_runtime.install_slot(0, StaticContext(map_id=1))
    enum_callback_before = exact_runtime_internal_snapshot(enum_callback_runtime)
    enum_hash_callbacks = 0
    enum_equality_callbacks = 0
    original_enum_hash = SemanticRole.__hash__
    original_enum_equality = SemanticRole.__eq__

    def hostile_enum_hash(value: SemanticRole) -> int:
        nonlocal enum_hash_callbacks
        enum_hash_callbacks += 1
        object.__setattr__(enum_callback_slot, "presentation_gate", True)
        return 1

    def hostile_enum_equality(left: SemanticRole, right: Any) -> bool:
        nonlocal enum_equality_callbacks
        enum_equality_callbacks += 1
        object.__setattr__(enum_callback_slot, "presentation_gate", True)
        return left is right

    SemanticRole.__hash__ = hostile_enum_hash  # type: ignore[assignment]
    SemanticRole.__eq__ = hostile_enum_equality  # type: ignore[assignment]
    enum_closed_map_valid = True
    try:
        _validate_closed_runtime_graph(enum_closed_map, "closedMap.enumKeys")
    except ModelError:
        enum_closed_map_valid = False
    finally:
        SemanticRole.__hash__ = original_enum_hash  # type: ignore[assignment]
        SemanticRole.__eq__ = original_enum_equality  # type: ignore[assignment]
    check(
        "stable-closed-map-validation-compares-index-positionally-without-key-dispatch",
        enum_closed_map_valid and enum_hash_callbacks == 0 and enum_equality_callbacks == 0
        and enum_callback_slot.presentation_gate is False
        and exact_runtime_internal_snapshot(enum_callback_runtime) == enum_callback_before,
    )

    class HostileResolveProxy:
        callbacks = 0
        target: SlotRuntime | None = None

        def __getattribute__(self, name: str) -> Any:
            type(self).callbacks += 1
            target = type(self).target
            if type(target) is SlotRuntime:
                object.__setattr__(target, "presentation_gate", True)
            raise RuntimeError("resolve proxy dispatched")

    resolve_guard_runtime = StackRuntime(
        _fixture_catalog()[0], handle_secret="resolve-static-guard",
        runtime_nonce="resolve-static-guard",
    )
    resolve_guard_slot = resolve_guard_runtime.install_slot(0, StaticContext(map_id=1))
    resolve_guard_before = exact_runtime_internal_snapshot(resolve_guard_runtime)
    HostileResolveProxy.target = resolve_guard_slot
    HostileResolveProxy.callbacks = 0
    hostile_catalog_resolve = raises_status(
        lambda: resolve_static(HostileResolveProxy(), StaticContext(map_id=1)),  # type: ignore[arg-type]
        Status.INVALID_STATIC_DATA,
    )
    hostile_context_resolve = raises_status(
        lambda: resolve_static(_fixture_catalog()[0], HostileResolveProxy()),  # type: ignore[arg-type]
        Status.INVALID_STATIC_DATA,
    )
    HostileResolveProxy.target = None
    check(
        "stable-resolve-static-exact-type-and-closed-graph-guards-precede-all-dereference",
        hostile_catalog_resolve and hostile_context_resolve
        and HostileResolveProxy.callbacks == 0
        and resolve_guard_slot.presentation_gate is False
        and exact_runtime_internal_snapshot(resolve_guard_runtime) == resolve_guard_before,
    )

    class HostileResultProxy:
        callbacks = 0
        target: SlotRuntime | None = None

        def __getattribute__(self, name: str) -> Any:
            type(self).callbacks += 1
            target = type(self).target
            if type(target) is SlotRuntime:
                object.__setattr__(target, "presentation_gate", True)
            raise RuntimeError("result proxy dispatched")

    result_guard_runtime = StackRuntime(
        _fixture_catalog()[0], handle_secret="result-to-dict-guard",
        runtime_nonce="result-to-dict-guard",
    )
    result_guard_slot = result_guard_runtime.install_slot(0, StaticContext(map_id=1))
    valid_result = result_guard_runtime.apply(0, 5, ids["owner_weather"])
    valid_result_wire = result_to_dict(valid_result)
    result_guard_before = exact_runtime_internal_snapshot(result_guard_runtime)
    HostileResultProxy.target = result_guard_slot
    HostileResultProxy.callbacks = 0
    hostile_result_rejected = raises_status(
        lambda: result_to_dict(HostileResultProxy()),  # type: ignore[arg-type]
        Status.INVALID_HANDLE,
    )
    HostileResultProxy.target = None
    check(
        "stable-result-to-dict-requires-closed-exact-result-and-returns-detached-wire",
        hostile_result_rejected and HostileResultProxy.callbacks == 0
        and result_guard_slot.presentation_gate is False
        and exact_runtime_internal_snapshot(result_guard_runtime) == result_guard_before
        and type(valid_result_wire) is dict
        and valid_result_wire["status"] == Status.OK.value,
    )

    class HostileAdjacentKey:
        callbacks = 0
        target: SlotRuntime | None = None

        @classmethod
        def mutate(cls) -> None:
            cls.callbacks += 1
            if type(cls.target) is SlotRuntime:
                object.__setattr__(cls.target, "presentation_gate", True)

        def __hash__(self) -> int:
            type(self).mutate()
            return hash("$extraType")

        def __eq__(self, other: Any) -> bool:
            type(self).mutate()
            return False

        def __lt__(self, other: Any) -> bool:
            type(self).mutate()
            return False

        def __str__(self) -> str:
            type(self).mutate()
            return "$extraType"

    decode_key_runtime = StackRuntime(
        _fixture_catalog()[0], handle_secret="decode-hostile-key",
        runtime_nonce="decode-hostile-key",
    )
    decode_key_slot = decode_key_runtime.install_slot(0, StaticContext(map_id=1))
    decode_key = HostileAdjacentKey()
    malformed_extras = {decode_key: "hostile"}
    HostileAdjacentKey.callbacks = 0
    HostileAdjacentKey.target = decode_key_slot
    decode_key_before = exact_runtime_internal_snapshot(decode_key_runtime)
    decode_key_rejected = raises_status(
        lambda: StaticContext.from_dict({"mapId": 1, "extras": malformed_extras}),
        Status.INVALID_STATIC_DATA,
    )
    HostileAdjacentKey.target = None
    check(
        "adjacent-canonical-extras-decode-screens-hostile-keys-before-envelope-membership",
        decode_key_rejected and HostileAdjacentKey.callbacks == 0
        and decode_key_slot.presentation_gate is False
        and exact_runtime_internal_snapshot(decode_key_runtime) == decode_key_before,
    )

    serialization_key_runtime = StackRuntime(
        _fixture_catalog()[0], handle_secret="serialization-hostile-key",
        runtime_nonce="serialization-hostile-key",
    )
    serialization_key_slot = serialization_key_runtime.install_slot(0, StaticContext(map_id=1))
    hostile_context = StaticContext(map_id=1)
    serialization_key = HostileAdjacentKey()
    hostile_context_extras = {serialization_key: "hostile"}
    object.__setattr__(hostile_context, "extras", hostile_context_extras)
    HostileAdjacentKey.callbacks = 0
    HostileAdjacentKey.target = serialization_key_slot
    serialization_key_before = exact_runtime_internal_snapshot(serialization_key_runtime)
    hostile_to_data_rejected = raises_status(lambda: to_data(hostile_context), Status.INVALID_STATIC_DATA)
    hostile_canonical_rejected = raises_status(lambda: canonical_json_bytes(hostile_context), Status.INVALID_STATIC_DATA)
    hostile_hash_rejected = raises_status(lambda: stable_hash("hostile-context", hostile_context), Status.INVALID_STATIC_DATA)
    HostileAdjacentKey.target = None
    check(
        "adjacent-public-serialization-screens-extras-keys-before-sort-and-json-hash",
        hostile_to_data_rejected and hostile_canonical_rejected and hostile_hash_rejected
        and HostileAdjacentKey.callbacks == 0
        and serialization_key_slot.presentation_gate is False
        and exact_runtime_internal_snapshot(serialization_key_runtime) == serialization_key_before,
    )

    enum_storage_runtime = StackRuntime(
        _fixture_catalog()[0], handle_secret="enum-storage-hostile-key",
        runtime_nonce="enum-storage-hostile-key",
    )
    enum_storage_slot = enum_storage_runtime.install_slot(0, StaticContext(map_id=1))
    enum_storage_before = exact_runtime_internal_snapshot(enum_storage_runtime)
    enum_storage = object.__getattribute__(SemanticRole.CALM, "__dict__")
    enum_storage_key = HostileAdjacentKey()
    enum_storage[enum_storage_key] = "hostile"
    HostileAdjacentKey.callbacks = 0
    HostileAdjacentKey.target = enum_storage_slot
    enum_storage_rejected = raises_status(lambda: to_data(SemanticRole.CALM), Status.INVALID_STATIC_DATA)
    enum_storage_callbacks = HostileAdjacentKey.callbacks
    HostileAdjacentKey.target = None
    enum_storage.pop(enum_storage_key)
    check(
        "adjacent-enum-wire-storage-screens-hostile-keys-before-sorting",
        enum_storage_rejected and enum_storage_callbacks == 0
        and enum_storage_slot.presentation_gate is False
        and exact_runtime_internal_snapshot(enum_storage_runtime) == enum_storage_before,
    )

    constructor_enum_runtime = StackRuntime(
        _fixture_catalog()[0], handle_secret="closed-map-constructor-enum",
        runtime_nonce="closed-map-constructor-enum",
    )
    constructor_enum_slot = constructor_enum_runtime.install_slot(0, StaticContext(map_id=1))
    constructor_enum_before = exact_runtime_internal_snapshot(constructor_enum_runtime)
    constructor_hash_callbacks = 0
    constructor_equality_callbacks = 0
    constructor_original_hash = SemanticRole.__hash__
    constructor_original_equality = SemanticRole.__eq__

    def constructor_hostile_hash(value: SemanticRole) -> int:
        nonlocal constructor_hash_callbacks
        constructor_hash_callbacks += 1
        object.__setattr__(constructor_enum_slot, "presentation_gate", True)
        return 1

    def constructor_hostile_equality(left: SemanticRole, right: Any) -> bool:
        nonlocal constructor_equality_callbacks
        constructor_equality_callbacks += 1
        object.__setattr__(constructor_enum_slot, "presentation_gate", True)
        return left is right

    SemanticRole.__hash__ = constructor_hostile_hash  # type: ignore[assignment]
    SemanticRole.__eq__ = constructor_hostile_equality  # type: ignore[assignment]
    constructed_enum_map: ClosedMap | None = None
    duplicate_enum_rejected = False
    try:
        constructed_enum_map = ClosedMap(((SemanticRole.CALM, "calm"), (SemanticRole.TIRED, "tired")))
        constructed_lookup_ok = constructed_enum_map[SemanticRole.CALM] == "calm"
        try:
            ClosedMap(((SemanticRole.CALM, 1), (SemanticRole.CALM, 2)))
        except ValueError:
            duplicate_enum_rejected = True
    finally:
        SemanticRole.__hash__ = constructor_original_hash  # type: ignore[assignment]
        SemanticRole.__eq__ = constructor_original_equality  # type: ignore[assignment]
    check(
        "adjacent-closed-map-construction-and-lookup-never-hash-or-compare-original-enum-keys",
        type(constructed_enum_map) is ClosedMap and constructed_lookup_ok and duplicate_enum_rejected
        and constructor_hash_callbacks == 0 and constructor_equality_callbacks == 0
        and constructor_enum_slot.presentation_gate is False
        and exact_runtime_internal_snapshot(constructor_enum_runtime) == constructor_enum_before,
    )

    combined_cold_runtime = StackRuntime(
        _fixture_catalog()[0], handle_secret="combined-cold-root-forgery",
        runtime_nonce="combined-cold-root-forgery",
    )
    cold_root_originals = tuple(
        object.__getattribute__(combined_cold_runtime, name)
        for name in ("_secret", "_runtime_incarnation", "_root_anchor", "_secret_authenticator")
    )
    cold_forged_secret = b"S" * 32
    cold_forged_incarnation = "a" * 64
    cold_forged_anchor = b"A" * 32
    cold_forged_tag = _root_secret_authenticator(
        cold_forged_anchor, cold_forged_secret, cold_forged_incarnation,
        combined_cold_runtime.data_generation, combined_cold_runtime._data_incarnation,
    )
    for name, value in zip(
        ("_secret", "_runtime_incarnation", "_root_anchor", "_secret_authenticator"),
        (cold_forged_secret, cold_forged_incarnation, cold_forged_anchor, cold_forged_tag),
    ):
        object.__setattr__(combined_cold_runtime, name, value)
    cold_forged_before = exact_runtime_internal_snapshot(combined_cold_runtime)
    cold_validate_rejected = raises_status(lambda: StackRuntime._validate_world_integrity(combined_cold_runtime), Status.INVALID_HANDLE)
    cold_install_rejected = raises_status(lambda: combined_cold_runtime.install_slot(0, StaticContext(map_id=1)), Status.INVALID_HANDLE)
    cold_apply_result = combined_cold_runtime.apply(0, 1, ids["owner_awareness"])
    cold_serialize_rejected = raises_status(lambda: runtime_to_dict(combined_cold_runtime), Status.INVALID_HANDLE)
    cold_forged_unchanged = exact_runtime_internal_snapshot(combined_cold_runtime) == cold_forged_before
    for name, value in zip(
        ("_secret", "_runtime_incarnation", "_root_anchor", "_secret_authenticator"), cold_root_originals,
    ):
        object.__setattr__(combined_cold_runtime, name, value)
    StackRuntime._validate_world_integrity(combined_cold_runtime)
    check(
        "external-root-authority-rejects-combined-cold-secret-incarnation-anchor-and-tag-forgery",
        cold_validate_rejected and cold_install_rejected and cold_serialize_rejected
        and cold_apply_result.status is Status.INVALID_HANDLE and not cold_apply_result.mutated
        and cold_forged_unchanged and not combined_cold_runtime.slots[0].live,
    )

    combined_live_runtime = StackRuntime(
        _fixture_catalog()[0], handle_secret="combined-live-root-forgery",
        runtime_nonce="combined-live-root-forgery",
    )
    combined_live_slot = combined_live_runtime.install_slot(0, StaticContext(map_id=1))
    combined_live_runtime.apply(0, 1, ids["owner_awareness"])
    live_root_originals = tuple(
        object.__getattribute__(combined_live_runtime, name)
        for name in ("_secret", "_runtime_incarnation", "_root_anchor", "_secret_authenticator")
    )
    live_forged_secret = b"L" * 32
    live_forged_incarnation = "b" * 64
    live_forged_anchor = b"B" * 32
    live_forged_tag = _root_secret_authenticator(
        live_forged_anchor, live_forged_secret, live_forged_incarnation,
        combined_live_runtime.data_generation, combined_live_runtime._data_incarnation,
    )
    for name, value in zip(
        ("_secret", "_runtime_incarnation", "_root_anchor", "_secret_authenticator"),
        (live_forged_secret, live_forged_incarnation, live_forged_anchor, live_forged_tag),
    ):
        object.__setattr__(combined_live_runtime, name, value)
    live_forged_before = exact_runtime_internal_snapshot(combined_live_runtime)
    live_apply_result = combined_live_runtime.apply(0, 5, ids["owner_weather"])
    live_clear_result = combined_live_runtime.clear(0)
    live_serialize_rejected = raises_status(lambda: runtime_to_dict(combined_live_runtime), Status.INVALID_HANDLE)
    live_forged_unchanged = exact_runtime_internal_snapshot(combined_live_runtime) == live_forged_before
    for name, value in zip(
        ("_secret", "_runtime_incarnation", "_root_anchor", "_secret_authenticator"), live_root_originals,
    ):
        object.__setattr__(combined_live_runtime, name, value)
    StackRuntime._validate_world_integrity(combined_live_runtime)
    check(
        "external-root-authority-rejects-combined-live-resigning-without-layer-or-diagnostic-mutation",
        live_apply_result.status is Status.INVALID_HANDLE and not live_apply_result.mutated
        and live_clear_result.status is Status.INVALID_HANDLE and not live_clear_result.mutated
        and live_serialize_rejected and live_forged_unchanged
        and len(combined_live_slot.layers) == 1 and combined_live_slot.presentation_gate is False,
    )

    lifecycle_runtime = StackRuntime(
        _fixture_catalog()[0], handle_secret="external-root-lifecycle",
        runtime_nonce="external-root-lifecycle",
    )
    constructor_external_anchor = _external_root_anchor(lifecycle_runtime)
    constructor_stored_anchor = lifecycle_runtime._root_anchor
    lifecycle_clone = copy.copy(lifecycle_runtime)
    clone_rejected = raises_status(lambda: StackRuntime._validate_world_integrity(lifecycle_clone), Status.INVALID_HANDLE)
    lifecycle_runtime.stage_catalog(_fixture_catalog()[0])
    lifecycle_runtime.install_staged_catalog()
    cold_external_anchor = _external_root_anchor(lifecycle_runtime)
    cold_stored_anchor = lifecycle_runtime._root_anchor
    lifecycle_runtime.runtime_epoch = GEN_MAX
    lifecycle_runtime._secret_authenticator = _root_secret_authenticator(
        lifecycle_runtime._root_anchor, lifecycle_runtime._secret,
        lifecycle_runtime._runtime_incarnation, lifecycle_runtime.data_generation,
        lifecycle_runtime._data_incarnation,
    )
    lifecycle_slot = lifecycle_runtime.install_slot(0, StaticContext(
        map_id=1, data_generation=lifecycle_runtime.data_generation,
        data_incarnation=lifecycle_runtime._data_incarnation,
    ), slot_generation=GEN_MAX)
    lifecycle_slot.next_entry_generation = GEN_MAX
    lifecycle_restart = lifecycle_runtime.apply(0, 5, ids["owner_weather"])
    terminal_external_anchor = _external_root_anchor(lifecycle_runtime)
    terminal_stored_anchor = lifecycle_runtime._root_anchor
    lifecycle_wire = runtime_to_dict(lifecycle_runtime)
    registry_size_before_close = len(_validated_root_authority_registry())
    lifecycle_runtime.close()
    registry_size_after_close = len(_validated_root_authority_registry())
    closed_rejected = raises_status(lambda: runtime_to_dict(lifecycle_runtime), Status.INVALID_HANDLE)
    check(
        "external-root-authority-registers-rotates-excludes-clones-and-serialization-and-closes-cold",
        constructor_external_anchor == constructor_stored_anchor
        and cold_external_anchor == cold_stored_anchor and cold_external_anchor != constructor_external_anchor
        and terminal_external_anchor == terminal_stored_anchor and terminal_external_anchor != cold_external_anchor
        and lifecycle_restart.status is Status.RUNTIME_EPOCH_RESTARTED
        and clone_rejected and "rootAnchor" not in lifecycle_wire and "secretAuthenticator" not in lifecycle_wire
        and registry_size_after_close == registry_size_before_close - 1 and closed_rejected,
    )

    registry_atomic_runtime = StackRuntime(
        _fixture_catalog()[0], handle_secret="external-root-registry-atomic",
        runtime_nonce="external-root-registry-atomic",
    )
    registry_atomic_before = exact_runtime_internal_snapshot(registry_atomic_runtime)
    saved_root_registry = _ROOT_AUTHORITY_REGISTRY
    corrupt_registry_entry = (object(), b"C" * 32)
    globals()["_ROOT_AUTHORITY_REGISTRY"] = saved_root_registry + (corrupt_registry_entry,)
    registry_corruption_rejected = raises_status(
        lambda: StackRuntime._validate_world_integrity(registry_atomic_runtime), Status.INVALID_HANDLE,
    )
    registry_corruption_unchanged = exact_runtime_internal_snapshot(registry_atomic_runtime) == registry_atomic_before
    globals()["_ROOT_AUTHORITY_REGISTRY"] = saved_root_registry
    capacity_entries = tuple(
        (object.__new__(StackRuntime), hashlib.sha256(f"capacity:{index}".encode("ascii")).digest())
        for index in range(_ROOT_AUTHORITY_REGISTRY_MAX)
    )
    globals()["_ROOT_AUTHORITY_REGISTRY"] = capacity_entries
    capacity_registry_identity = _ROOT_AUTHORITY_REGISTRY
    capacity_status = None
    try:
        StackRuntime(_fixture_catalog()[0], handle_secret="capacity", runtime_nonce="capacity")
    except ModelError as exc:
        capacity_status = exc.status
    capacity_unchanged = _ROOT_AUTHORITY_REGISTRY is capacity_registry_identity
    globals()["_ROOT_AUTHORITY_REGISTRY"] = saved_root_registry
    StackRuntime._validate_world_integrity(registry_atomic_runtime)
    check(
        "external-root-authority-registry-corruption-and-capacity-fail-atomically",
        registry_corruption_rejected and registry_corruption_unchanged
        and capacity_status is Status.DATA_BUSY and capacity_unchanged
        and exact_runtime_internal_snapshot(registry_atomic_runtime) == registry_atomic_before,
    )

    class HostileCatalogMapping(Mapping[Any, Any]):
        callbacks = 0
        target: SlotRuntime | None = None

        @classmethod
        def mutate(cls) -> None:
            cls.callbacks += 1
            if type(cls.target) is SlotRuntime:
                object.__setattr__(cls.target, "presentation_gate", True)

        def __getitem__(self, key: Any) -> Any:
            type(self).mutate()
            raise RuntimeError("hostile catalog mapping lookup")

        def __iter__(self) -> Any:
            type(self).mutate()
            raise RuntimeError("hostile catalog mapping iteration")

        def __len__(self) -> int:
            type(self).mutate()
            raise RuntimeError("hostile catalog mapping length")

        def __contains__(self, key: Any) -> bool:
            type(self).mutate()
            return False

        def items(self) -> Any:
            type(self).mutate()
            raise RuntimeError("hostile catalog mapping items")

        def keys(self) -> Any:
            type(self).mutate()
            raise RuntimeError("hostile catalog mapping keys")

        def values(self) -> Any:
            type(self).mutate()
            raise RuntimeError("hostile catalog mapping values")

        def get(self, key: Any, default: Any = None) -> Any:
            type(self).mutate()
            return default

    catalog_mapping_runtime = StackRuntime(
        _fixture_catalog()[0], handle_secret="catalog-mapping-callbacks",
        runtime_nonce="catalog-mapping-callbacks",
    )
    catalog_mapping_slot = catalog_mapping_runtime.install_slot(0, StaticContext(map_id=1))
    catalog_mapping_before = exact_runtime_internal_snapshot(catalog_mapping_runtime)
    constructor_source = _fixture_catalog()[0]
    HostileCatalogMapping.callbacks = 0
    HostileCatalogMapping.target = catalog_mapping_slot
    direct_catalog_rejected = raises_status(
        lambda: BehaviorCatalog(
            HostileCatalogMapping(), constructor_source.controllers,
            constructor_source.modifiers, constructor_source.definitions,
            constructor_source.static_rules, constructor_source.default_controller_id,
            constructor_source.spawn_policies, constructor_source.population_policies,
            constructor_source.hook_sets, constructor_source.spawn_policy_patches,
            constructor_source.population_policy_patches,
            constructor_source.tired_translations, constructor_source.owner_names,
        ),
        Status.INVALID_STATIC_DATA,
    )
    HostileCatalogMapping.target = None
    check(
        "catalog-constructor-rejects-hostile-registry-before-values-or-items-dispatch",
        direct_catalog_rejected and HostileCatalogMapping.callbacks == 0
        and catalog_mapping_slot.presentation_gate is False
        and exact_runtime_internal_snapshot(catalog_mapping_runtime) == catalog_mapping_before,
    )

    hostile_wire = to_data(_fixture_catalog()[0])
    hostile_wire["stateProfiles"] = HostileCatalogMapping()
    HostileCatalogMapping.callbacks = 0
    HostileCatalogMapping.target = catalog_mapping_slot
    decoded_catalog_rejected = raises_status(lambda: catalog_from_dict(hostile_wire), Status.INVALID_STATIC_DATA)
    HostileCatalogMapping.target = None
    check(
        "catalog-from-dict-rejects-hostile-registry-before-mapping-protocol-dispatch",
        decoded_catalog_rejected and HostileCatalogMapping.callbacks == 0
        and catalog_mapping_slot.presentation_gate is False
        and exact_runtime_internal_snapshot(catalog_mapping_runtime) == catalog_mapping_before,
    )

    validation_catalog = _fixture_catalog()[0]
    original_validation_profiles = validation_catalog.state_profiles
    object.__setattr__(validation_catalog, "state_profiles", HostileCatalogMapping())
    HostileCatalogMapping.callbacks = 0
    HostileCatalogMapping.target = catalog_mapping_slot
    validation_catalog_rejected = raises_status(lambda: BehaviorCatalog.validate(validation_catalog), Status.INVALID_STATIC_DATA)
    HostileCatalogMapping.target = None
    object.__setattr__(validation_catalog, "state_profiles", original_validation_profiles)
    BehaviorCatalog.validate(validation_catalog)
    check(
        "catalog-validate-rejects-hostile-live-field-before-complete-registry-traversal",
        validation_catalog_rejected and HostileCatalogMapping.callbacks == 0
        and catalog_mapping_slot.presentation_gate is False
        and exact_runtime_internal_snapshot(catalog_mapping_runtime) == catalog_mapping_before,
    )

    nested_registry_cases: list[dict[str, Any]] = []
    registry_wire_names = (
        "stateProfiles", "controllers", "modifiers", "definitions",
        "spawnPolicies", "populationPolicies", "hookSets",
        "spawnPolicyPatches", "populationPolicyPatches", "ownerNames",
    )
    canonical_catalog_wire = to_data(_fixture_catalog()[0])
    for registry_name in registry_wire_names:
        case = copy.deepcopy(canonical_catalog_wire)
        case[registry_name] = HostileCatalogMapping()
        nested_registry_cases.append(case)
    modifier_operations_case = copy.deepcopy(canonical_catalog_wire)
    next(iter(modifier_operations_case["modifiers"].values()))["operations"] = HostileCatalogMapping()
    nested_registry_cases.append(modifier_operations_case)
    spawn_patch_operations_case = copy.deepcopy(canonical_catalog_wire)
    next(iter(spawn_patch_operations_case["spawnPolicyPatches"].values()))["operations"] = HostileCatalogMapping()
    nested_registry_cases.append(spawn_patch_operations_case)
    population_patch_operations_case = copy.deepcopy(canonical_catalog_wire)
    next(iter(population_patch_operations_case["populationPolicyPatches"].values()))["operations"] = HostileCatalogMapping()
    nested_registry_cases.append(population_patch_operations_case)
    HostileCatalogMapping.callbacks = 0
    HostileCatalogMapping.target = catalog_mapping_slot
    nested_registry_rejections = all(
        raises_status(lambda case=case: catalog_from_dict(case), Status.INVALID_STATIC_DATA)
        for case in nested_registry_cases
    )
    HostileCatalogMapping.target = None
    closed_catalog_wire = ClosedMap(tuple(canonical_catalog_wire.items()))
    closed_catalog_roundtrip = catalog_from_dict(closed_catalog_wire)
    check(
        "catalog-nested-registries-and-operation-maps-are-symmetric-exact-container-boundaries",
        nested_registry_rejections and HostileCatalogMapping.callbacks == 0
        and canonical_json_bytes(closed_catalog_roundtrip) == canonical_json_bytes(_fixture_catalog()[0])
        and catalog_mapping_slot.presentation_gate is False
        and exact_runtime_internal_snapshot(catalog_mapping_runtime) == catalog_mapping_before,
    )
    return passed


def _load_json(path: str) -> Any:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def _write_json(value: Any, compact: bool) -> None:
    if compact:
        sys.stdout.buffer.write(canonical_json_bytes(value) + b"\n")
    else:
        print(json.dumps(to_data(value), ensure_ascii=False, sort_keys=True, indent=2))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pure deterministic one-state stack composer and atomic-layer reference model.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("self-check", help="run the focused built-in contract fixtures")
    check.add_argument("--json", action="store_true", help="emit the result as JSON")
    check.add_argument("--compact", action="store_true", help="use canonical compact JSON with --json")
    compose_parser = subparsers.add_parser("compose", help="compose a catalog/context/layer JSON request")
    compose_parser.add_argument("--input", "-i", default="-", help="request JSON path (default: stdin)")
    compose_parser.add_argument("--compact", action="store_true", help="emit canonical compact JSON")
    return parser.parse_args(argv)


def _compose_request_impl(request: Mapping[str, Any]) -> Composition:
    request = _closed_mapping(request, "composeRequest", ("catalog", "context", "layers"))
    if any(not _present(request, field_name) for field_name in ("catalog", "context", "layers")):
        raise ModelError(Status.INVALID_STATIC_DATA, "composeRequest requires catalog, context, and layers")
    catalog = catalog_from_dict(_read(request, "catalog"))
    static = resolve_static(catalog, StaticContext.from_dict(_read(request, "context")))
    raw_layers = _sequence(_read(request, "layers"), "composeRequest.layers")
    if len(raw_layers) > MAX_RUNTIME_LAYERS:
        raise ModelError(Status.CAPACITY_EXCEEDED, f"compose input exceeds {MAX_RUNTIME_LAYERS} layers")
    layers: list[Layer] = []
    keys: set[tuple[int, int]] = set()
    entry_generations: set[int] = set()
    validator = StackRuntime(catalog, slot_count=1)
    validator.install_slot(0, static.context)
    for index, item in enumerate(raw_layers):
        item = _closed_mapping(item, f"composeRequest.layers[{index}]", ("definition_id", "owner_id", "instance_key", "entry_generation", "generated"))
        if any(not _present(item, field_name) for field_name in ("definition_id", "owner_id", "instance_key", "entry_generation", "generated")):
            raise ModelError(Status.INVALID_HANDLE, f"composeRequest.layers[{index}] lacks a required field")
        definition_id = _id(_read(item, "definition_id"), "layer.definitionId")
        owner_id = _id(_read(item, "owner_id"), "layer.ownerId")
        instance_key = _u16(_read(item, "instance_key"), "layer.instanceKey")
        entry_generation = _u32(_read(item, "entry_generation"), "layer.entryGeneration", nonzero=True)
        if not 1 <= entry_generation <= GEN_MAX or entry_generation in entry_generations:
            raise ModelError(Status.INVALID_HANDLE, "layer entry generations must be nonzero unique u32 values")
        entry_generations.add(entry_generation)
        definition = validator._validate_operation_definition(definition_id, owner_id, instance_key)
        validator._ensure_applicable_for_apply(validator.slots[0], definition)
        if _read(item, "generated") is None:
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "compose runtime layer must carry explicit generated metadata")
        generated = GeneratedMetadata.from_dict(_read(item, "generated"))
        if generated != definition.generated:
            raise ModelError(Status.INVALID_GENERATED_WRAPPER, "compose layer metadata differs from definition")
        key = (owner_id, instance_key)
        if key in keys:
            raise ModelError(Status.AMBIGUOUS_DELTA, f"duplicate compose owner/key {key}")
        keys.add(key)
        layers.append(Layer(definition_id, owner_id, instance_key, entry_generation, generated))
    validator._validate_final_multiplicity(layers)
    return _compose_impl(catalog, static, sorted(layers, key=lambda layer: layer.key()))


def _compose_request(request: Mapping[str, Any]) -> Composition:
    try:
        if type(request) is not dict:
            raise ModelError(Status.INVALID_STATIC_DATA, "compose request must be an exact JSON object")
        return _compose_request_impl(request)
    except ModelError:
        raise
    except Exception:
        raise ModelError(Status.INVALID_COMPOSITION, "compose request boundary rejected hostile or malformed input") from None


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "self-check":
        checks = run_self_checks()
        payload = {"schema": MODEL_SCHEMA, "schemaVersion": MODEL_SCHEMA_VERSION, "passed": True, "count": len(checks), "checks": checks}
        if args.json:
            _write_json(payload, args.compact)
        else:
            print(f"stack model self-check: PASS ({len(checks)} checks)")
            for name in checks:
                print(f"  ok  {name}")
        return 0
    if args.command == "compose":
        _write_json(_compose_request(_load_json(args.input)), args.compact)
        return 0
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ModelError, ValueError, TypeError, KeyError, OSError, json.JSONDecodeError, AssertionError) as exc:
        if isinstance(exc, ModelError):
            print(f"error [{exc.status.value}]: {exc.message}", file=sys.stderr)
        else:
            print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
