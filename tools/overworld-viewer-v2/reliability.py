"""Reliability primitives for the V2 overworld behavior editor.

The legacy viewer remains the source of truth for parsing and writing the game
sources.  This module adds the guarantees an editor needs around those calls:
content revisions, one-writer transactions with rollback, and context-accurate
profile resolution.
"""

from __future__ import annotations

import hashlib
import json
import os
import fcntl
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Any, Callable


MUTATION_LOCK = threading.RLock()
SERVER_RESTARTING = threading.Event()
STABLE_READ_CACHE: dict[str, tuple[str, Any]] = {}


class RevisionConflict(ValueError):
    """Raised when an edit was based on an out-of-date source revision."""

    def __init__(self, expected: str, current: str):
        super().__init__("Sources changed since this editor loaded. Reload before saving.")
        self.expected = expected
        self.current = current


class SourceReadConflict(RuntimeError):
    """Raised when external edits prevent a coherent source snapshot."""


@contextmanager
def workspace_guard(root: Path):
    """Serialize V2 readers/writers across threads and V2 server processes."""

    root_digest = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:20]
    lock_path = Path(tempfile.gettempdir()) / f"overworld-viewer-v2-{root_digest}.lock"
    with MUTATION_LOCK:
        with lock_path.open("a+b") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def begin_restart() -> None:
    """Reject new source writes once a process restart has been scheduled."""

    SERVER_RESTARTING.set()


def mutation_source_paths(legacy: ModuleType, root: Path) -> tuple[Path, ...]:
    """Return all files that any profile, encounter, or setting save can write."""

    paths = {
        legacy.BEHAVIOR_DATA_SOURCE,
        legacy.BEHAVIOR_DATA_HEADER,
        legacy.ENCOUNTERS_SOURCE,
        legacy.HEADBUTT_SOURCE,
        legacy.ENCOUNTER_OVERRIDES_SOURCE,
    }
    paths.update(Path(setting["source"]) for setting in legacy.SPAWN_SETTING_BY_SYMBOL.values())
    return tuple(
        sorted(
            (Path(path).resolve() for path in paths),
            key=lambda path: path.relative_to(root).as_posix(),
        )
    )


def revision_source_paths(legacy: ModuleType, root: Path) -> tuple[Path, ...]:
    """Return every parsed source so a revision represents the full data model."""

    paths = {Path(path).resolve() for path in legacy.DATA_SOURCE_FILES}
    paths.update(mutation_source_paths(legacy, root))
    return tuple(sorted(paths, key=lambda path: path.relative_to(root).as_posix()))


def source_entry(path: Path, root: Path) -> dict[str, str | int | bool | None]:
    relative_path = path.relative_to(root).as_posix()
    try:
        body = path.read_bytes()
    except FileNotFoundError:
        return {"path": relative_path, "exists": False, "size": None, "sha256": None}
    return {
        "path": relative_path,
        "exists": True,
        "size": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def workspace_metadata(legacy: ModuleType, root: Path) -> dict[str, Any]:
    """Describe the workspace with a deterministic, content-based revision."""

    sources = [source_entry(path, root) for path in revision_source_paths(legacy, root)]
    revision_input = "".join(
        f"{entry['path']}\0{entry['sha256'] or 'missing'}\n" for entry in sources
    ).encode("utf-8")
    mutation_paths = {
        path.relative_to(root).as_posix() for path in mutation_source_paths(legacy, root)
    }
    return {
        "apiVersion": 2,
        "workspaceName": root.name,
        "workspaceRoot": str(root),
        "sourceRevision": f"sha256:{hashlib.sha256(revision_input).hexdigest()}",
        "sourceFiles": sources,
        "mutationSources": [entry for entry in sources if entry["path"] in mutation_paths],
        "missingSources": [entry["path"] for entry in sources if not entry["exists"]],
    }


def current_revision(legacy: ModuleType, root: Path) -> str:
    return str(workspace_metadata(legacy, root)["sourceRevision"])


def stable_source_read(
    legacy: ModuleType,
    root: Path,
    reader: Callable[[], Any],
    attempts: int = 3,
    cache_key: str | None = None,
    refresh_legacy_cache: bool = False,
) -> tuple[Any, str]:
    """Read and parse a source snapshot whose revision stayed unchanged."""

    before = ""
    after = ""
    for _ in range(attempts):
        before = current_revision(legacy, root)
        cached = STABLE_READ_CACHE.get(cache_key) if cache_key else None
        if cached is not None and cached[0] == before:
            return cached[1], before
        if refresh_legacy_cache:
            # The legacy cache key uses mtime and size; invalidating on a V2
            # revision miss also catches a same-size, preserved-mtime edit.
            legacy.invalidate_data_cache()
        value = reader()
        after = current_revision(legacy, root)
        if before == after:
            if cache_key:
                STABLE_READ_CACHE[cache_key] = (after, value)
            return value, after
    raise SourceReadConflict(
        f"Sources changed repeatedly while reading ({before} -> {after}). Reload and try again."
    )


def _run_build_job_guarded(legacy: ModuleType, root: Path, open_after: bool) -> None:
    entered_legacy_job = False
    try:
        with workspace_guard(root):
            entered_legacy_job = True
            legacy.run_build_job(open_after)
    except Exception as exc:  # pragma: no cover - lock/filesystem failure
        if entered_legacy_job:
            raise
        legacy.append_build_output(f"\nBuild failed before start: {exc}\n")
        legacy.update_build_state(
            running=False,
            endedAt=time.time(),
            ok=False,
            code=None,
            error=str(exc),
            testNdsExists=legacy.TEST_NDS.exists(),
            testNdsPath=str(legacy.TEST_NDS),
        )
        if legacy.BUILD_LOCK.locked():
            legacy.BUILD_LOCK.release()


def start_build_job(legacy: ModuleType, root: Path, open_after: bool = False) -> dict[str, Any]:
    """Start a legacy build while holding the cross-process source lock."""

    if not legacy.BUILD_LOCK.acquire(blocking=False):
        raise RuntimeError("Build already running")
    legacy.update_build_state(
        running=True,
        startedAt=time.time(),
        endedAt=None,
        command=legacy.BUILD_COMMAND,
        output=f"Starting Docker build via {legacy.BUILD_COMMAND}...\n",
        latestLine="Starting Docker build...",
        ok=None,
        code=None,
        error=None,
        open=None,
        openError=None,
        testNdsExists=legacy.TEST_NDS.exists(),
        testNdsPath=str(legacy.TEST_NDS),
    )
    thread = threading.Thread(
        target=_run_build_job_guarded,
        args=(legacy, root, open_after),
        daemon=True,
    )
    thread.start()
    return legacy.build_status_payload()


def _snapshot(paths: tuple[Path, ...]) -> dict[Path, bytes | None]:
    return {path: path.read_bytes() if path.exists() else None for path in paths}


def _atomic_write(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.v2-{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(body)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _restore(snapshot: dict[Path, bytes | None]) -> list[str]:
    errors: list[str] = []
    for path, body in snapshot.items():
        try:
            if body is None:
                path.unlink(missing_ok=True)
            else:
                _atomic_write(path, body)
        except Exception as exc:  # pragma: no cover - only filesystem failure
            errors.append(f"{path}: {exc}")
    return errors


def _rollback(legacy: ModuleType, snapshot: dict[Path, bytes | None], original: Exception) -> None:
    """Attempt every restore, always invalidate caches, and preserve both errors."""

    errors: list[str] = []
    try:
        errors = _restore(snapshot)
    finally:
        legacy.invalidate_data_cache()
    if errors:
        details = "; ".join(errors)
        raise RuntimeError(
            f"Transaction failed ({original}); rollback also failed for: {details}"
        ) from original


def _as_body(payload: Any) -> bytes:
    if not isinstance(payload, dict):
        raise ValueError("each change set must be an object")
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _validate_revision(legacy: ModuleType, root: Path, expected: str | None) -> str:
    if SERVER_RESTARTING.is_set():
        raise ValueError("The V2 server is restarting. Reload the editor when it returns.")
    current = current_revision(legacy, root)
    if not expected:
        raise ValueError("A source revision is required. Reload the V2 editor and try again.")
    if expected != current:
        raise RevisionConflict(expected, current)
    return current


MUTATION_HANDLERS: dict[str, str] = {
    "/save-profiles": "apply_profile_changes",
    "/save-profile-memberships": "apply_profile_membership_changes",
    "/manage-profiles": "apply_profile_management_change",
    "/save-profile-overrides": "apply_profile_override_changes",
    "/save-encounters": "apply_encounter_changes",
    "/save-spawn-settings": "apply_spawn_setting_changes",
}


def transactional_mutation(
    legacy: ModuleType,
    root: Path,
    path: str,
    body: bytes,
    expected_revision: str | None,
) -> dict[str, Any]:
    """Run one legacy mutation with optimistic locking and full rollback."""

    handler_name = MUTATION_HANDLERS.get(path)
    if handler_name is None:
        raise ValueError(f"unsupported mutation endpoint: {path}")
    handler: Callable[[bytes], dict[str, Any]] = getattr(legacy, handler_name)
    sources = mutation_source_paths(legacy, root)
    # The legacy build job owns BUILD_LOCK for its entire lifetime. Take it
    # before the workspace guard so reads remain available while a save waits.
    with legacy.BUILD_LOCK:
        with workspace_guard(root):
            previous_revision = _validate_revision(legacy, root, expected_revision)
            snapshot = _snapshot(sources)
            try:
                result = dict(handler(body))
                legacy.validate_override_profile_source()
                legacy.build_data()
                next_revision = current_revision(legacy, root)
            except Exception as exc:
                _rollback(legacy, snapshot, exc)
                raise
            result.update(
                {
                    "apiVersion": 2,
                    "previousRevision": previous_revision,
                    "sourceRevision": next_revision,
                    "transaction": "committed",
                }
            )
            return result


COMMIT_STEPS: tuple[tuple[str, str], ...] = (
    ("profiles", "apply_profile_changes"),
    ("profileMemberships", "apply_profile_membership_changes"),
    ("profileOverrides", "apply_profile_override_changes"),
    ("encounters", "apply_encounter_changes"),
    ("spawnSettings", "apply_spawn_setting_changes"),
)


def transactional_commit(legacy: ModuleType, root: Path, body: bytes) -> dict[str, Any]:
    """Commit every pending editor domain as one all-or-nothing transaction."""

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("commit payload must be an object")
    expected_revision = payload.get("sourceRevision")
    requested = [(key, handler) for key, handler in COMMIT_STEPS if payload.get(key) is not None]
    if not requested:
        raise ValueError("commit contains no changes")

    sources = mutation_source_paths(legacy, root)
    with legacy.BUILD_LOCK:
        with workspace_guard(root):
            previous_revision = _validate_revision(legacy, root, expected_revision)
            snapshot = _snapshot(sources)
            results: dict[str, dict[str, Any]] = {}
            try:
                for key, handler_name in requested:
                    handler: Callable[[bytes], dict[str, Any]] = getattr(legacy, handler_name)
                    results[key] = dict(handler(_as_body(payload[key])))
                legacy.validate_override_profile_source()
                # A complete parse catches cross-domain inconsistencies before the
                # transaction is accepted. Any failure restores every source file.
                legacy.build_data()
                next_revision = current_revision(legacy, root)
            except Exception as exc:
                _rollback(legacy, snapshot, exc)
                raise

            changed_domains = [key for key, result in results.items() if result.get("saved")]
            return {
                "apiVersion": 2,
                "saved": bool(changed_domains),
                "message": "Saved as one transaction" if changed_domains else "No code changes needed",
                "domains": results,
                "changedDomains": changed_domains,
                "previousRevision": previous_revision,
                "sourceRevision": next_revision,
                "transaction": "committed",
            }


def _parse_bool(value: str | None) -> int:
    return 1 if str(value or "").strip().lower() in {"1", "true", "yes", "shiny"} else 0


def _stable_layer_id(name: str, override: dict[str, Any], occurrence: int) -> str:
    match = {
        key: override["match"][key].get("raw")
        for key in getattr(override.get("match"), "keys", lambda: [])()
    }
    behavior = override.get("behavior", {})
    profile = behavior.get("profile", {}) if isinstance(behavior, dict) else {}
    signature = {
        "name": name,
        "occurrence": occurrence,
        "match": match,
        "mask": behavior.get("mask", {}),
        "profile": {key: value.get("raw") for key, value in profile.items()},
    }
    digest = hashlib.sha256(
        json.dumps(signature, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    return f"override:{digest}"


def resolve_context(
    legacy: ModuleType,
    species_symbol: str,
    level_value: str | None,
    terrain_value: str | None,
    shiny_value: str | None,
) -> dict[str, Any]:
    """Resolve one real runtime context and expose the complete layer stack."""

    raw_overlay = legacy.OVERLAY_SOURCE.read_text()
    source = legacy.strip_c_comments(legacy.join_line_continuations(raw_overlay))
    raw_behavior_data = legacy.BEHAVIOR_DATA_SOURCE.read_text()
    behavior_source = legacy.strip_c_comments(legacy.join_line_continuations(raw_behavior_data))
    expressions, species_order = legacy.parse_define_expressions(legacy.DEFINE_SOURCE_FILES)
    macros = legacy.evaluate_defines(expressions)
    macros.update(legacy.evaluate_armips_equ([legacy.ARMIPS_CONFIG, legacy.ARMIPS_CONSTANTS]))
    terrain_values, destination_values = legacy.parse_behavior_data_enums()
    macros.update(terrain_values)
    macros.update(destination_values)
    primitive_maps = legacy.parse_primitive_maps(source, macros)

    class_labels = legacy.invert_labels(macros, legacy.CLASS_PREFIX)
    group_labels = legacy.invert_labels(macros, legacy.GROUP_PREFIX)
    class_profiles = [
        legacy.parse_profile(entry, macros)
        for entry in legacy.parse_initializer(
            legacy.extract_braced_initializer(
                behavior_source, "sOverworldWildBehaviorClassProfiles"
            )
        )
    ]
    class_rules = legacy.parse_behavior_class_rules(
        behavior_source, macros, group_labels, class_labels
    )
    variable_overrides = legacy.parse_behavior_overrides(
        behavior_source, macros, group_labels
    )
    override_names = legacy.parse_override_profile_names(raw_behavior_data)
    group_species = legacy.parse_group_species(source, macros)
    species = legacy.parse_species(expressions, macros, species_order)
    legacy.apply_species_type_metadata(species, legacy.parse_species_type_metadata(macros))
    species_by_symbol = {entry["symbol"]: entry for entry in species}

    symbol = str(species_symbol or "").strip().upper()
    if symbol and not symbol.startswith("SPECIES_"):
        symbol = f"SPECIES_{symbol}"
    species_entry = species_by_symbol.get(symbol)
    if species_entry is None:
        raise ValueError(f"unknown Pokemon species: {species_symbol}")
    try:
        level = int(level_value or 1)
    except ValueError as exc:
        raise ValueError("level must be a number from 1 to 100") from exc
    if not 1 <= level <= 100:
        raise ValueError("level must be from 1 to 100")

    default_terrain = macros.get("OW_WILD_SPAWN_TERRAIN_LAND", 0)
    terrain_raw = str(terrain_value or "").strip()
    if not terrain_raw:
        terrain = default_terrain
    elif terrain_raw in terrain_values:
        terrain = terrain_values[terrain_raw]
    else:
        try:
            terrain = int(terrain_raw, 0)
        except ValueError as exc:
            raise ValueError(f"unknown terrain: {terrain_raw}") from exc
    if terrain not in set(terrain_values.values()):
        raise ValueError(f"unknown terrain value: {terrain}")

    context = {
        "species": species_entry["value"],
        "symbol": symbol,
        "level": level,
        "terrain": terrain,
        "shiny": _parse_bool(shiny_value),
        "groupFlags": legacy.group_flags_for_species(
            symbol, group_species, species_by_symbol, macros
        ),
        "behaviorClass": macros.get("OW_WILD_BEHAVIOR_CLASS_DEFAULT", 0),
    }
    behavior_class, class_hits = legacy.class_for_context(
        context, class_rules, len(class_profiles), macros
    )
    context["behaviorClass"] = behavior_class
    base_profile = legacy.clone_profile(class_profiles[behavior_class])

    resolver_layers: list[dict[str, Any]] = [
        {
            "id": f"class:{class_labels.get(behavior_class, {}).get('symbol', behavior_class)}",
            "kind": "base",
            "order": 0,
            "name": class_labels.get(behavior_class, {}).get("name", f"Class {behavior_class}"),
            "matched": True,
            "applied": True,
            "summary": "Base profile",
            "changes": [],
        }
    ]
    working_profile = legacy.clone_profile(base_profile)
    matched_override_orders: list[int] = []
    runtime_layers: list[dict[str, Any]] = [
        {"kind": "class", "label": f"Class profile #{behavior_class}", "changes": []}
    ]
    for override in variable_overrides:
        profile_order = int(override["order"])
        name = override_names.get(profile_order, "") or f"Override profile #{profile_order}"
        matched = legacy.behavior_override_applies(context, override, macros)
        if matched:
            matched_override_orders.append(profile_order)
        changes = (
            legacy.merge_profile(working_profile, override["behavior"])
            if matched
            else []
        )
        if matched:
            runtime_layers.append(
                {
                    "kind": "behaviorOverride",
                    "label": name,
                    "changes": changes,
                    "mask": legacy.behavior_override_mask_summary(override["behavior"]),
                }
            )
        members = override.get("memberSymbols") or []
        matched_member = symbol if matched and symbol in members else ""
        resolver_layers.append(
            {
                "id": _stable_layer_id(name, override, profile_order),
                "kind": "override",
                "order": profile_order,
                "name": name,
                "matched": matched,
                "applied": matched,
                "summary": (
                    f"Matched member {species_entry['name']}"
                    if matched_member
                    else override.get("summary", "Shared context")
                ),
                "memberCount": len(members),
                "matchedMember": matched_member,
                "match": override["match"],
                "fields": legacy.behavior_override_mask_summary(override["behavior"])["labels"],
                "changes": changes,
            }
        )

    normalizations = legacy.normalize_profile(working_profile, macros)
    if normalizations:
        runtime_layers.append(
            {"kind": "normalization", "label": "Runtime fallback", "changes": normalizations}
        )
    resolved_profile = working_profile

    terrain_symbol = next(
        (key for key, value in terrain_values.items() if value == terrain), str(terrain)
    )
    class_label = class_labels.get(
        behavior_class,
        {"symbol": str(behavior_class), "name": f"Class {behavior_class}", "value": behavior_class},
    )
    group_names = [
        label["name"]
        for group, label in group_labels.items()
        if group and context["groupFlags"] & group
    ]
    return {
        "apiVersion": 2,
        "sourceRevision": current_revision(legacy, legacy.ROOT),
        "resolutionOrder": "top-to-bottom",
        "lastAppliesLast": True,
        "context": {
            "species": species_entry,
            "level": level,
            "terrain": {"symbol": terrain_symbol, "value": terrain},
            "shiny": bool(context["shiny"]),
            "groups": group_names,
        },
        "behaviorClass": class_label,
        "classRuleHits": [
            {
                "order": rule["order"],
                "summary": rule["summary"],
                "className": rule["className"],
            }
            for rule in class_hits
        ],
        "baseProfile": legacy.profile_numeric_view(base_profile),
        "resolvedProfile": legacy.profile_numeric_view(resolved_profile),
        "resolvedPrimitives": legacy.resolve_primitives(resolved_profile, primitive_maps, macros),
        "resolverLayers": resolver_layers,
        "matchedOverrideOrders": matched_override_orders,
        "matchedOverrideProfileOrders": matched_override_orders,
        "normalizations": normalizations,
        "runtimeLayers": runtime_layers,
    }
