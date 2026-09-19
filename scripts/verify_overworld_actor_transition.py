#!/usr/bin/env python3
"""Build and run the deterministic host proof for actor field transitions."""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def function_body(source: str, name: str, last: bool = False) -> str:
    start = source.rindex(name) if last else source.index(name)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise SystemExit(f"unterminated function: {name}")


def verify_adapter_contracts() -> None:
    field = (ROOT / "src/field/map_teleport.c").read_text()
    wild = (
        ROOT
        / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
    ).read_text()
    helper = (
        ROOT
        / "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c"
    ).read_text()
    mount = (
        ROOT
        / "src/overworld_mount_overlay/overworld_mount_overlay.c"
    ).read_text()
    headers = (
        ROOT / "include/overworld_wild_spawns_internal.h"
    ).read_text() + (ROOT / "include/overworld_wild_helper.h").read_text() + (
        ROOT / "include/overworld_mount.h"
    ).read_text()

    required = {
        "field actor transition driver": (
            field,
            "OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->transition(&call)",
        ),
        "wild typed transition adapter": (
            wild,
            "OverworldWildSpawns_ApplyTransitionWork(",
        ),
        "mount typed transition adapter": (
            mount,
            "OverworldMount_Transition(",
        ),
        "field-to-mount typed transition call": (
            field,
            "OVERWORLD_MOUNT_OVERLAY_ENTRY->transition(call)",
        ),
        "helper typed presentation adapter": (
            helper,
            "OverworldWildHelper_ApplyPresentationCommand(",
        ),
        "fixed wild callback slot": (headers, "applyTransitionWork;"),
        "fixed helper callback slot": (headers, "applyPresentationCommand;"),
        "fixed mount callback slot": (
            headers,
            "BOOL (*transition)(const OverworldActorTransitionCall *call);",
        ),
    }
    for name, (source, marker) in required.items():
        if marker not in source:
            raise SystemExit(f"missing {name}: {marker}")

    forbidden = (
        "prepareMapHeaderChange",
        "normalizeThrowPresentation",
        "THROW_PRESENTATION_TRANSITION_SUSPEND",
        "THROW_PRESENTATION_TRANSITION_RESUME",
        "THROW_PRESENTATION_TRANSITION_DISCARD",
        "prepareMapTransition",
        "OW_WILD_MAP_HEADER_CHANGE_",
        "ApplyMountTransitionCompatibility",
    )
    combined = field + wild + helper + mount + headers
    for marker in forbidden:
        if marker in combined:
            raise SystemExit(f"legacy transition protocol remains: {marker}")
    if "OVERWORLD_MOUNT_OVERLAY_ENTRY->transition(call)" in wild:
        raise SystemExit("wild adapter still proxies the mount transition")

    rebind = function_body(
        wild, "OverworldWildSpawns_RebindRetainedSpawnObject("
    )
    rebind_markers = (
        "GetMapObjectByID(fieldSystem->mapObjectMan, spawn->objectId)",
        "OverworldWildSpawns_IsCurrentMapObject(fieldSystem, object)",
        "OVERWORLD_ACTOR_INSPECT_ACTOR_INDEX",
        "OverworldActorTransition_RetainedHandleMatches(",
        "snapshot.actor.subjectIdentity != spawn->personality",
        "object->id != spawn->objectId",
        "object->scriptId != OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT",
    )
    for marker in rebind_markers:
        if marker not in rebind:
            raise SystemExit(f"wild retained-pointer validation omits: {marker}")
        mutant = rebind.replace(marker, "RETIRED_VALIDATION", 1)
        if all(required in mutant for required in rebind_markers):
            raise SystemExit(
                f"wild retained-pointer validation mutant survived: {marker}"
            )
    apply_transition = function_body(
        wild, "OverworldWildSpawns_ApplyTransitionWork(", last=True
    )
    rebind_call = apply_transition.index(
        "OverworldWildSpawns_RebindRetainedSpawnObject("
    )
    first_dereference = apply_transition.index("object->unkC")
    if rebind_call >= first_dereference:
        raise SystemExit("wild rebind dereferences the old object before validation")
    for marker in (
        "fieldSystem == NULL || state == NULL || call == NULL",
        "fieldSystem->mapObjectMan == NULL",
        "((MapObjectMan *)fieldSystem->mapObjectMan)->objects == NULL",
        "call->currentMapId != fieldSystem->location->mapId",
    ):
        if marker not in apply_transition:
            raise SystemExit(f"wild transition outer guard omits: {marker}")

    field_transition = function_body(
        field, "OverworldFieldService_OnMapHeaderChangedImpl("
    )
    field_markers = (
        "OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext()",
        "call.previousFieldContext = sOverworldFieldTransition.sequence",
        "call.work == OVERWORLD_ACTOR_TRANSITION_WORK_REBIND",
        "OVERWORLD_ACTOR_TRANSITION_DISPOSITION_DISCARD",
    )
    for marker in field_markers:
        if marker not in field_transition:
            raise SystemExit(f"field transition contract omits: {marker}")
    if "state->mapGeneration" in field_transition:
        raise SystemExit("field transition still trusts Wild map generation")

    transition_model = (
        ROOT / "lib/overworld/overworld_actor_transition_model.c"
    ).read_text()
    for marker in (
        "call->previousFieldContext != currentFieldContext",
        "call->mapIdentity != state->mapIdentity",
        "call->disposition != state->disposition",
    ):
        if marker not in transition_model:
            raise SystemExit(f"actor transition owner omits: {marker}")

    cancel_shared_motion = function_body(
        wild, "OverworldWildSpawns_CancelSharedMotion(", last=True
    )

    def has_mounted_cancel_guard(body: str) -> bool:
        return (
            "slot == OW_WILD_FOLLOWER_SLOT" in body
            and "OVERWORLD_MOUNT_OVERLAY_ENTRY->isActive()" in body
            and "return;" in body
            and "OVERWORLD_ACTOR_BOUNDARY_CANCEL" in body
        )

    mounted_guard = has_mounted_cancel_guard(cancel_shared_motion)
    if not mounted_guard:
        raise SystemExit(
            "wild transition cleanup can cancel actor-owned mounted motion"
        )
    cancel_mutant = cancel_shared_motion.replace(
        "OVERWORLD_MOUNT_OVERLAY_ENTRY->isActive()",
        "FALSE",
        1,
    )
    if has_mounted_cancel_guard(cancel_mutant):
        raise SystemExit("mounted-motion cancel guard mutation survived")


def compile_and_run(
    compiler: list[str], directory: Path, include_dir: Path, suffix: str,
    quiet: bool = False, model_path: Path | None = None,
) -> None:
    executable = directory / f"overworld-actor-transition-{suffix}"
    command = compiler + [
        "-std=c99",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-pedantic",
        "-DOVERWORLD_ACTOR_SYSTEM_HOST=1",
        "-I",
        str(include_dir),
        "-I",
        str(ROOT / "include"),
        str(model_path or (
            ROOT / "lib/overworld/overworld_actor_transition_model.c"
        )),
        str(ROOT / "tools/overworld_actor_transition_harness.c"),
        "-o",
        str(executable),
    ]
    subprocess.run(command, cwd=ROOT, check=True, timeout=30)
    subprocess.run(
        [str(executable)],
        cwd=ROOT,
        check=True,
        timeout=30,
        stdout=subprocess.PIPE if quiet else None,
        stderr=subprocess.PIPE if quiet else None,
        text=quiet,
    )


def main() -> int:
    compiler = shlex.split(os.environ.get("CC", "cc"))
    if not compiler:
        raise SystemExit("CC must name a C compiler")
    with tempfile.TemporaryDirectory(prefix="overworld-transition-") as directory:
        temp = Path(directory)
        compile_and_run(compiler, temp, ROOT / "include", "baseline")
        header = (ROOT / "include/overworld_actor_transition_model.h").read_text()
        mutations = {
            "field-epoch": (
                "handle->fieldEpoch == call->nextFieldEpoch",
                "handle->fieldEpoch != call->nextFieldEpoch",
            ),
            "map-generation": (
                "handle->mapGeneration == call->nextMapGeneration",
                "handle->mapGeneration != call->nextMapGeneration",
            ),
            "encounter-generation": (
                "handle->encounterGeneration == encounterGeneration",
                "handle->encounterGeneration != encounterGeneration",
            ),
        }
        for name, (old, new) in mutations.items():
            if header.count(old) != 1:
                raise SystemExit(f"mutation anchor changed: {name}")
            include_dir = temp / name
            include_dir.mkdir()
            (include_dir / "overworld_actor_transition_model.h").write_text(
                header.replace(old, new)
            )
            try:
                compile_and_run(compiler, temp, include_dir, name, quiet=True)
            except subprocess.CalledProcessError:
                continue
            raise SystemExit(f"transition host mutant survived: {name}")
        model = (
            ROOT / "lib/overworld/overworld_actor_transition_model.c"
        ).read_text()
        model_mutations = {
            "owner-map-generation": (
                "call->previousFieldContext != currentFieldContext",
                "call->previousFieldContext == currentFieldContext",
            ),
            "preserve-failure-fallback": (
                "call->disposition != state->disposition",
                "call->disposition == state->disposition",
            ),
        }
        for name, (old, new) in model_mutations.items():
            if model.count(old) != 1:
                raise SystemExit(f"model mutation anchor changed: {name}")
            mutant = temp / f"{name}.c"
            mutant.write_text(model.replace(old, new))
            try:
                compile_and_run(
                    compiler,
                    temp,
                    ROOT / "include",
                    name,
                    quiet=True,
                    model_path=mutant,
                )
            except subprocess.CalledProcessError:
                continue
            raise SystemExit(f"transition model mutant survived: {name}")
    verify_adapter_contracts()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
