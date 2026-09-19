"""Unit fixtures for the structural overworld legacy-deletion gate."""

from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

from verify_overworld_roadmap_legacy_deletion import (  # noqa: E402
    ACTOR_BASE,
    ACTOR_COMPAT_ENTRY,
    ACTOR_DEBUG_ENTRY,
    ACTOR_FACADE_ENTRY,
    ACTOR_MOTION_ENTRY,
    ACTOR_MOVEMENT_POLICY_ENTRY,
    ACTOR_POPULATION_ENTRY,
    ACTOR_SYSTEM_OWNER_SOURCE,
    CLIENT_MODULES,
    LEGACY_POPULATION_THUNK,
    MODULES,
    MOTION_BOUNDARY_BRIDGE,
    WILD_MOTION_RECEIPT,
    MOTION_PLANNER_CLIENTS,
    MOUNT_STREAM_CLIENT_SOURCE,
    NATIVE_SHADOW_STOCK_PATCH_SOURCE,
    PRIVATE_WILD_STATE_SOURCE_CLIENTS,
    RETIRED_ENTRIES,
    WALK_OWNER_ENTRY,
    WILD_HELPER_FLEE_FALLBACK_ENTRY,
    WILD_RUNTIME_ENTRY,
    WILD_RUNTIME_ACKNOWLEDGE_CALLBACK_OFFSET,
    WILD_RUNTIME_POPULATION_CALLBACK_OFFSET,
    WILD_NATIVE_SHADOW_OWNER_SOURCE,
    WILD_SPAWNS_ENTRY,
    ModuleSpec,
    Symbol,
    _c_function_body,
    audit_packaging,
    audit_structure,
    parse_nm,
)


def definition(module: str, name: str, address: int, size: int = 8) -> Symbol:
    return Symbol(module, address, size, "T", name)


def write(image: bytearray, base: int, address: int, data: bytes) -> None:
    offset = address - base
    image[offset : offset + len(data)] = data


def entry(magic: int, version: int, size: int, pointers: list[int]) -> bytes:
    return struct.pack("<IHH", magic, version, size) + struct.pack(f"<{len(pointers)}I", *pointers)


def complete_fixture() -> tuple[list[Symbol], dict[str, bytes]]:
    lengths = {
        "actor_system": 0x3670,
        "mount": 0x1C40,
        "wild_spawns": 0xB000,
        "wild_runtime": 0xC00,
        "walk_module": 0x1C00,
        "role_controller": 0x1000,
        "wild_helper": 0x4000,
        "wild_behavior_data": 0x1000,
        "follower_selector": 0x2C00,
        "field": 0x5000,
        "follower_selector_icons": 0x8CC,
        "follower_release": 0x38C,
    }
    specs = {spec.key: spec for spec in MODULES}
    images = {key: bytearray(size) for key, size in lengths.items()}
    symbols: list[Symbol] = []
    actor_names = (
        "OverworldActorSystem_ValidateImpl",
        "OverworldActorSystem_ApplyImpl",
        "OverworldActorSystem_TickImpl",
        "OverworldActorSystem_InspectImpl",
        "OverworldActorSystem_CompatibilityBindImpl",
        "OverworldActorSystem_CompatibilityUnbindImpl",
        "OverworldActorSystem_CompatibilityTransitionImpl",
        "OverworldActorSystem_CompatibilityRecordTraceImpl",
        "OverworldActorSystem_CompatibilityGetContextImpl",
        "ActorSystem_RequestMotion",
        "ActorSystem_EngineBoundary",
        "OverworldActorSystem_PopulationFrameImpl",
        "OverworldActorSystem_PopulationControlImpl",
        "ActorSystem_BuildLookPlan",
        "ActorSystem_ResolveLook",
        "ActorSystem_ChooseWanderDirection",
        "ActorSystem_ReduceWalk",
        "ActorSystem_TerminalWalkBoundary",
        "ActorSystem_FinishMountedWalk",
    )
    addresses: dict[str, int] = {}
    for index, name in enumerate(actor_names):
        address = ACTOR_BASE + 0x200 + index * 0x20
        addresses[name] = address
        symbols.append(definition("actor_system", name, address))
    policy_address = ACTOR_BASE + 0x1000
    symbols.append(Symbol("actor_system", policy_address, 24, "r", "sActorMovementPolicy"))
    write(images["actor_system"], ACTOR_BASE, ACTOR_FACADE_ENTRY, entry(0x5341574F, 1, 24, [addresses[name] | 1 for name in actor_names[:4]]))
    write(images["actor_system"], ACTOR_BASE, ACTOR_COMPAT_ENTRY, entry(0x4341574F, 3, 32, [
        addresses["OverworldActorSystem_CompatibilityBindImpl"] | 1,
        0,
        addresses["OverworldActorSystem_CompatibilityUnbindImpl"] | 1,
        addresses["OverworldActorSystem_CompatibilityTransitionImpl"] | 1,
        addresses["OverworldActorSystem_CompatibilityRecordTraceImpl"] | 1,
        addresses["OverworldActorSystem_CompatibilityGetContextImpl"] | 1,
    ]))
    debug = bytearray(64)
    struct.pack_into("<IHHIII", debug, 0, 0x4C44574F, 1, 64, ACTOR_BASE, ACTOR_BASE + 0x4000, ACTOR_BASE + 0x3670)
    struct.pack_into("<H", debug, 42, 0x990)
    write(images["actor_system"], ACTOR_BASE, ACTOR_DEBUG_ENTRY, debug)
    write(images["actor_system"], ACTOR_BASE, ACTOR_MOTION_ENTRY, entry(0x534D574F, 6, 16, [addresses["ActorSystem_RequestMotion"] | 1, addresses["ActorSystem_EngineBoundary"] | 1]))
    write(images["actor_system"], ACTOR_BASE, ACTOR_POPULATION_ENTRY, entry(0x5450574F, 3, 16, [addresses["OverworldActorSystem_PopulationFrameImpl"] | 1, addresses["OverworldActorSystem_PopulationControlImpl"] | 1]))
    write(images["actor_system"], ACTOR_BASE, ACTOR_MOVEMENT_POLICY_ENTRY, entry(0x504D574F, 4, 16, [policy_address, 0]))
    write(images["actor_system"], ACTOR_BASE, policy_address, struct.pack("<6I", *[addresses[name] | 1 for name in actor_names[13:19]]))
    runtime_base = specs["wild_runtime"].base
    walk_body = runtime_base + 0x200
    symbols.append(definition("wild_runtime", "RenamedWalkOwner", walk_body))
    symbols.append(definition(
        "wild_runtime",
        "OverworldWildRuntime_ApplyMotionBoundary",
        MOTION_BOUNDARY_BRIDGE,
        0x72,
    ))
    pointers = [runtime_base + 0x300 | 1] * 11
    pointers[4] = 0
    pointers[7] = 0
    write(images["wild_runtime"], runtime_base, WILD_RUNTIME_ENTRY, entry(0x3152574F, 16, 52, pointers))
    write(images["wild_runtime"], runtime_base, WALK_OWNER_ENTRY, entry(0x5057574F, 1, 12, [walk_body | 1]))
    struct.pack_into("<I", images["mount"], 0x500, MOTION_BOUNDARY_BRIDGE | 1)
    symbols.append(definition("wild_runtime", "OverworldWildSpawns_AcknowledgeSharedMotion",
                              WILD_MOTION_RECEIPT, 34))
    struct.pack_into("<I", images["wild_runtime"], WILD_MOTION_RECEIPT - runtime_base,
                     MOTION_BOUNDARY_BRIDGE | 1)
    for index in range(11):
        struct.pack_into("<I", images["wild_spawns"], 0x500 + 4 * index, WILD_MOTION_RECEIPT | 1)
    symbols.append(definition(
        "role_controller", "OverworldActorHopPlanner_Plan", 0x023BD4F0, 8
    ))
    symbols.append(definition(
        "role_controller", "OverworldActorTeleportPlanner_Plan", 0x023BD4F8, 8
    ))
    return symbols, {key: bytes(value) for key, value in images.items()}


def mutate(images: dict[str, bytes], module: str) -> tuple[dict[str, bytes], bytearray]:
    changed = dict(images)
    image = bytearray(images[module])
    changed[module] = image  # type: ignore[assignment]
    return changed, image


def kinds(result: dict) -> set[str]:
    return {item["kind"] for item in result["issues"]}


class StructuralLegacyDeletionTests(unittest.TestCase):
    def test_function_body_ignores_later_calls_and_declarations(self) -> None:
        source = """
static void Owner(int value) { if (value) { value++; } }
static void Owner(int value);
static void Client(void) { Owner(1); }
"""

        body = _c_function_body(source, "Owner")

        self.assertIn("value++", body)
        self.assertNotIn("Client", body)

    def test_actor_wild_resident_flag_source_mutation_fails(self) -> None:
        symbols, images = complete_fixture()
        sources = {
            path: "\n"
            for _module, path in PRIVATE_WILD_STATE_SOURCE_CLIENTS
        }
        sources[WILD_NATIVE_SHADOW_OWNER_SOURCE] = "\n"
        sources[NATIVE_SHADOW_STOCK_PATCH_SOURCE] = "\n"
        sources[ACTOR_SYSTEM_OWNER_SOURCE] = """
static void ActorSystem_SyncLegacyActor(void) {}
static void OverworldActorSystem_PopulationFrameImpl(void) {
    gOverworldWildFieldIdleRearmPending |= 1;
}
"""

        self.assertIn(
            "direct-wild-resident-flag-source-reference",
            kinds(audit_structure(
                symbols,
                images,
                private_client_sources=sources,
            )),
        )

    def test_actor_wild_state_type_source_mutation_fails(self) -> None:
        symbols, images = complete_fixture()
        sources = {
            path: "\n"
            for _module, path in PRIVATE_WILD_STATE_SOURCE_CLIENTS
        }
        sources[WILD_NATIVE_SHADOW_OWNER_SOURCE] = "\n"
        sources[NATIVE_SHADOW_STOCK_PATCH_SOURCE] = "\n"
        sources[MOUNT_STREAM_CLIENT_SOURCE] = "\n"
        sources[ACTOR_SYSTEM_OWNER_SOURCE] = """
static void ActorSystem_SyncLegacyActor(OverworldWildSpawnState *state) {}
static void OverworldActorSystem_PopulationFrameImpl(void) {}
"""

        self.assertIn(
            "direct-wild-state-type-source-reference",
            kinds(audit_structure(
                symbols,
                images,
                private_client_sources=sources,
            )),
        )

    def test_mount_private_terrain_stream_source_mutation_fails(self) -> None:
        symbols, images = complete_fixture()
        sources = {
            path: "\n"
            for _module, path in PRIVATE_WILD_STATE_SOURCE_CLIENTS
        }
        sources[WILD_NATIVE_SHADOW_OWNER_SOURCE] = "\n"
        sources[NATIVE_SHADOW_STOCK_PATCH_SOURCE] = "\n"
        sources[ACTOR_SYSTEM_OWNER_SOURCE] = """
static void ActorSystem_SyncLegacyActor(void) {}
static void OverworldActorSystem_PopulationFrameImpl(void) {}
"""
        sources[MOUNT_STREAM_CLIENT_SOURCE] = """
static void Broken(void *manager) {
    if (*((unsigned char *)manager + 0xA0) != 0) {}
}
"""

        self.assertIn(
            "mount-private-terrain-stream-source-reference",
            kinds(audit_structure(
                symbols,
                images,
                private_client_sources=sources,
            )),
        )

    def test_mount_wild_resident_flag_source_mutation_fails(self) -> None:
        symbols, images = complete_fixture()
        sources = {
            path: "\n"
            for _module, path in PRIVATE_WILD_STATE_SOURCE_CLIENTS
        }
        sources[WILD_NATIVE_SHADOW_OWNER_SOURCE] = "\n"
        sources[NATIVE_SHADOW_STOCK_PATCH_SOURCE] = "\n"
        sources[ACTOR_SYSTEM_OWNER_SOURCE] = """
static void ActorSystem_SyncLegacyActor(void) {}
static void OverworldActorSystem_PopulationFrameImpl(void) {}
"""
        sources[MOUNT_STREAM_CLIENT_SOURCE] = (
            "void Resume(void) { "
            "gOverworldWildFieldIdleRearmPending |= 1; }\n"
        )

        self.assertIn(
            "mount-wild-resident-flag-source-reference",
            kinds(audit_structure(
                symbols,
                images,
                private_client_sources=sources,
            )),
        )

    def test_inventory_covers_every_linked_overworld_module(self) -> None:
        self.assertEqual(
            {spec.key for spec in MODULES},
            {
                "actor_system",
                "mount",
                "wild_spawns",
                "wild_runtime",
                "walk_module",
                "role_controller",
                "wild_helper",
                "wild_behavior_data",
                "follower_selector",
                "field",
                "follower_selector_icons",
                "follower_release",
            },
        )

    def test_wild_spawns_package_identity_uses_overlay_149(self) -> None:
        spec = next(item for item in MODULES if item.key == "wild_spawns")
        self.assertEqual((spec.overlay_id, spec.base), (149, 0x023CCFD8))

    def test_complete_contract_passes(self) -> None:
        symbols, images = complete_fixture()
        result = audit_structure(symbols, images)
        self.assertTrue(result["passed"], result["issues"])

    def test_missing_linked_client_fails_closed(self) -> None:
        symbols, images = complete_fixture()
        del images["follower_release"]
        self.assertIn("missing-linked-client", kinds(audit_structure(symbols, images)))

    def test_missing_motion_boundary_client_fails_closed(self) -> None:
        for module in ("mount", "wild_spawns"):
            with self.subTest(module=module):
                symbols, images = complete_fixture()
                images, client = mutate(images, module)
                struct.pack_into("<I", client, 0x500, 0)
                self.assertIn(
                    "invalid-motion-boundary-client",
                    kinds(audit_structure(symbols, images)),
                )

    def test_missing_motion_boundary_bridge_fails_closed(self) -> None:
        symbols, images = complete_fixture()
        symbols = [
            item for item in symbols
            if item.name != "OverworldWildRuntime_ApplyMotionBoundary"
        ]
        self.assertIn(
            "invalid-motion-boundary-bridge",
            kinds(audit_structure(symbols, images)),
        )

    def test_motion_receipt_split_reserves_fail_closed(self) -> None:
        for name, address, size in (
            ("OverworldWildRuntime_ApplyMotionBoundary", MOTION_BOUNDARY_BRIDGE, 0x76),
            ("OverworldWildSpawns_AcknowledgeSharedMotion", WILD_MOTION_RECEIPT, 42),
            ("OverworldWildSpawns_AcknowledgeSharedMotion", WILD_MOTION_RECEIPT + 2, 34),
        ):
            with self.subTest(name=name, address=address, size=size):
                symbols, images = complete_fixture()
                symbols = [item for item in symbols if item.name != name]
                symbols.append(definition("wild_runtime", name, address, size))
                self.assertIn("invalid-motion-boundary-bridge", kinds(audit_structure(symbols, images)))

    def test_motion_receipt_unexpected_clients_fail_closed(self) -> None:
        for module, target in (("wild_spawns", MOTION_BOUNDARY_BRIDGE),
                               ("mount", WILD_MOTION_RECEIPT),
                               ("field", MOTION_BOUNDARY_BRIDGE),
                               ("field", WILD_MOTION_RECEIPT)):
            with self.subTest(module=module, target=target):
                symbols, images = complete_fixture()
                images, client = mutate(images, module)
                struct.pack_into("<I", client, 0x600, target | 1)
                self.assertIn("unexpected-motion-boundary-client", kinds(audit_structure(symbols, images)))

    def test_motion_bridge_runtime_call_must_belong_to_capture_adapter(self) -> None:
        symbols, images = complete_fixture()
        images, runtime = mutate(images, "wild_runtime")
        struct.pack_into("<I", runtime, WILD_MOTION_RECEIPT - WILD_RUNTIME_ENTRY, 0)
        struct.pack_into("<I", runtime, 0x600, MOTION_BOUNDARY_BRIDGE | 1)
        self.assertIn("unexpected-motion-boundary-client", kinds(audit_structure(symbols, images)))

    def test_wrong_motion_owner_pointer_fails(self) -> None:
        symbols, images = complete_fixture()
        images, actor = mutate(images, "actor_system")
        wrong = next(item.address for item in symbols if item.name == "OverworldActorSystem_ApplyImpl")
        struct.pack_into("<I", actor, ACTOR_MOTION_ENTRY - ACTOR_BASE + 8, wrong | 1)
        self.assertIn("wrong-entry-pointer", kinds(audit_structure(symbols, images)))

    def test_nonzero_exported_policy_state_fails(self) -> None:
        symbols, images = complete_fixture()
        images, actor = mutate(images, "actor_system")
        struct.pack_into("<I", actor, ACTOR_MOVEMENT_POLICY_ENTRY - ACTOR_BASE + 12, ACTOR_BASE + 0x3670)
        self.assertIn("exported-private-state", kinds(audit_structure(symbols, images)))

    def test_retired_compatibility_update_pointer_fails(self) -> None:
        symbols, images = complete_fixture()
        images, actor = mutate(images, "actor_system")
        struct.pack_into(
            "<I",
            actor,
            ACTOR_COMPAT_ENTRY - ACTOR_BASE + 12,
            ACTOR_BASE + 0x300 | 1,
        )
        self.assertIn(
            "retired-compatibility-update-pointer",
            kinds(audit_structure(symbols, images)),
        )

    def test_compatibility_context_version_fails(self) -> None:
        symbols, images = complete_fixture()
        images, actor = mutate(images, "actor_system")
        struct.pack_into(
            "<H",
            actor,
            ACTOR_COMPAT_ENTRY - ACTOR_BASE + 4,
            2,
        )
        self.assertIn(
            "wrong-entry-shape",
            kinds(audit_structure(symbols, images)),
        )

    def test_compatibility_context_target_fails(self) -> None:
        symbols, images = complete_fixture()
        images, actor = mutate(images, "actor_system")
        wrong = next(
            item.address for item in symbols
            if item.name == "OverworldActorSystem_CompatibilityBindImpl"
        )
        struct.pack_into(
            "<I",
            actor,
            ACTOR_COMPAT_ENTRY - ACTOR_BASE + 28,
            wrong | 1,
        )
        self.assertIn(
            "wrong-entry-pointer",
            kinds(audit_structure(symbols, images)),
        )

    def test_retired_compatibility_update_body_fails(self) -> None:
        symbols, images = complete_fixture()
        symbols.append(definition(
            "actor_system",
            "OverworldActorSystem_CompatibilityUpdateImpl",
            ACTOR_BASE + 0x300,
        ))
        self.assertIn(
            "retired-compatibility-update-symbol",
            kinds(audit_structure(symbols, images)),
        )

    def test_renamed_direct_owner_reference_fails(self) -> None:
        symbols, images = complete_fixture()
        owner = next(item for item in symbols if item.name == "RenamedWalkOwner")
        images, mount = mutate(images, "mount")
        struct.pack_into("<I", mount, 0x400, owner.address | 1)
        self.assertIn("direct-owner-body-reference", kinds(audit_structure(symbols, images)))

    def test_every_linked_client_is_scanned_for_owner_body_references(self) -> None:
        for module in CLIENT_MODULES:
            with self.subTest(module=module):
                symbols, images = complete_fixture()
                owner = next(
                    item for item in symbols
                    if item.name == "ActorSystem_RequestMotion"
                )
                images, client = mutate(images, module)
                struct.pack_into("<I", client, 0x300, owner.address | 1)
                self.assertIn(
                    "direct-owner-body-reference",
                    kinds(audit_structure(symbols, images)),
                )

    def test_direct_thumb_branch_to_renamed_owner_fails(self) -> None:
        symbols, images = complete_fixture()
        owner = next(item for item in symbols if item.name == "RenamedWalkOwner")
        spec = next(item for item in MODULES if item.key == "mount")
        source = spec.base + 0x400
        symbols.append(definition("mount", "AdapterWithDirectBranch", source, 4))
        delta = owner.address - (source + 4)
        encoded = delta & ((1 << 23) - 1)
        first = 0xF000 | ((encoded >> 12) & 0x07FF)
        second = 0xF800 | ((encoded >> 1) & 0x07FF)
        images, mount = mutate(images, "mount")
        struct.pack_into("<HH", mount, 0x400, first, second)
        result = audit_structure(symbols, images)
        direct = [
            item
            for item in result["issues"]
            if item["kind"] == "direct-owner-body-reference"
        ]
        self.assertTrue(direct, result["issues"])
        self.assertEqual(direct[0]["referenceKind"], "thumb-branch")

    def test_direct_private_state_literal_fails(self) -> None:
        symbols, images = complete_fixture()
        images, mount = mutate(images, "mount")
        struct.pack_into("<I", mount, 0x400, ACTOR_BASE + 0x36A0)
        self.assertIn("direct-private-state-reference", kinds(audit_structure(symbols, images)))

    def test_every_linked_client_is_scanned_for_private_state(self) -> None:
        for module in CLIENT_MODULES:
            with self.subTest(module=module):
                symbols, images = complete_fixture()
                images, client = mutate(images, module)
                struct.pack_into("<I", client, 0x300, ACTOR_BASE + 0x36A0)
                self.assertIn(
                    "direct-private-state-reference",
                    kinds(audit_structure(symbols, images)),
                )

    def test_exported_wild_private_state_fails(self) -> None:
        symbols, images = complete_fixture()
        spec = next(item for item in MODULES if item.key == "wild_spawns")
        symbols.append(
            Symbol(
                "wild_spawns",
                spec.base + 0x9000,
                0x100,
                "B",
                "sOverworldWildSpawnState",
            )
        )

        self.assertIn(
            "exported-wild-private-state",
            kinds(audit_structure(symbols, images)),
        )

    def test_wild_private_state_client_reference_fails(self) -> None:
        symbols, images = complete_fixture()
        wild_spec = next(item for item in MODULES if item.key == "wild_spawns")
        state_address = wild_spec.base + 0x9000
        symbols.append(
            Symbol(
                "wild_spawns",
                state_address,
                0x100,
                "b",
                "sOverworldWildSpawnState",
            )
        )
        images, mount = mutate(images, "mount")
        struct.pack_into("<I", mount, 0x300, state_address)

        self.assertIn(
            "direct-wild-private-state-reference",
            kinds(audit_structure(symbols, images)),
        )

    def test_native_shadow_asm_private_state_source_mutation_fails(self) -> None:
        symbols, images = complete_fixture()
        sources = {
            path: "\n"
            for _module, path in PRIVATE_WILD_STATE_SOURCE_CLIENTS
        }
        path = PRIVATE_WILD_STATE_SOURCE_CLIENTS[0][1]
        sources[path] = "ldr r1, =sOverworldWildSpawnState\n"

        self.assertIn(
            "direct-wild-private-state-source-reference",
            kinds(audit_structure(
                symbols,
                images,
                private_client_sources=sources,
            )),
        )

    def test_walk_private_state_source_mutation_fails(self) -> None:
        symbols, images = complete_fixture()
        sources = {
            path: "\n"
            for _module, path in PRIVATE_WILD_STATE_SOURCE_CLIENTS
        }
        path = PRIVATE_WILD_STATE_SOURCE_CLIENTS[1][1]
        sources[path] = "void *state = &sOverworldWildSpawnState;\n"

        self.assertIn(
            "direct-wild-private-state-source-reference",
            kinds(audit_structure(
                symbols,
                images,
                private_client_sources=sources,
            )),
        )

    def test_native_shadow_unavailable_overlay_mutation_fails(self) -> None:
        symbols, images = complete_fixture()
        sources = {
            path: (REPO / path).read_text()
            for _module, path in PRIVATE_WILD_STATE_SOURCE_CLIENTS
        }
        path = PRIVATE_WILD_STATE_SOURCE_CLIENTS[1][1]
        sources[path] = sources[path].replace(
            "|| !IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION)",
            "",
            1,
        )

        self.assertIn(
            "native-shadow-service-overlay-unchecked",
            kinds(audit_structure(
                symbols,
                images,
                private_client_sources=sources,
            )),
        )

    def test_native_shadow_wrong_in_range_target_mutation_fails(self) -> None:
        symbols, images = complete_fixture()
        sources = {
            path: (REPO / path).read_text()
            for _module, path in PRIVATE_WILD_STATE_SOURCE_CLIENTS
        }
        path = PRIVATE_WILD_STATE_SOURCE_CLIENTS[1][1]
        sources[path] = sources[path].replace(
            "target != (OVERWORLD_WILD_SPAWNS_COPY_NATIVE_SHADOW_VALUE_ADDR | 1u)",
            "(target & ~1u) >= OVERWORLD_WILD_SPAWNS_OVERLAY_END_ADDR",
            1,
        )

        self.assertIn(
            "native-shadow-service-target-not-exact",
            kinds(audit_structure(
                symbols,
                images,
                private_client_sources=sources,
            )),
        )

    def test_native_shadow_asm_value_service_mutation_fails(self) -> None:
        symbols, images = complete_fixture()
        sources = {
            path: (REPO / path).read_text()
            for _module, path in PRIVATE_WILD_STATE_SOURCE_CLIENTS
        }
        path = PRIVATE_WILD_STATE_SOURCE_CLIENTS[0][1]
        sources[path] = sources[path].replace(
            "bl OverworldWalk_CopyNativeShadowValue",
            "nop",
            1,
        )

        self.assertIn(
            "native-shadow-value-service-bypassed",
            kinds(audit_structure(
                symbols,
                images,
                private_client_sources=sources,
            )),
        )

    def test_native_shadow_encounter_generation_mutation_fails(self) -> None:
        symbols, images = complete_fixture()
        sources = {
            path: (REPO / path).read_text()
            for _module, path in PRIVATE_WILD_STATE_SOURCE_CLIENTS
        }
        sources[WILD_NATIVE_SHADOW_OWNER_SOURCE] = (
            REPO / WILD_NATIVE_SHADOW_OWNER_SOURCE
        ).read_text().replace(
            "&& value->encounterGeneration != spawn->encounterGeneration",
            "",
            1,
        )

        self.assertIn(
            "native-shadow-encounter-generation-unchecked",
            kinds(audit_structure(
                symbols,
                images,
                private_client_sources=sources,
            )),
        )

    def test_native_shadow_visibility_token_overwrite_mutation_fails(self) -> None:
        symbols, images = complete_fixture()
        sources = {
            path: (REPO / path).read_text()
            for _module, path in PRIVATE_WILD_STATE_SOURCE_CLIENTS
        }
        path = PRIVATE_WILD_STATE_SOURCE_CLIENTS[0][1]
        sources[path] = sources[path].replace(
            "strh r2, [r4, #0xC]",
            "str r2, [r4, #0xC]",
            1,
        )

        self.assertIn(
            "native-shadow-generation-storage-overwritten",
            kinds(audit_structure(
                symbols,
                images,
                private_client_sources=sources,
            )),
        )

    def test_native_shadow_hidden_state_word_read_mutation_fails(self) -> None:
        symbols, images = complete_fixture()
        sources = {
            path: (REPO / path).read_text()
            for _module, path in PRIVATE_WILD_STATE_SOURCE_CLIENTS
        }
        sources[WILD_NATIVE_SHADOW_OWNER_SOURCE] = (
            REPO / WILD_NATIVE_SHADOW_OWNER_SOURCE
        ).read_text()
        sources[NATIVE_SHADOW_STOCK_PATCH_SOURCE] = (
            REPO / NATIVE_SHADOW_STOCK_PATCH_SOURCE
        ).read_text().replace(
            "ldrh r0, [r2, 0xC]",
            "ldr r0, [r2, 0xC]",
            1,
        )

        self.assertIn(
            "native-shadow-hidden-state-read-too-wide",
            kinds(audit_structure(
                symbols,
                images,
                private_client_sources=sources,
            )),
        )

    def test_native_shadow_object_identity_mutation_fails(self) -> None:
        symbols, images = complete_fixture()
        sources = {
            path: (REPO / path).read_text()
            for _module, path in PRIVATE_WILD_STATE_SOURCE_CLIENTS
        }
        sources[WILD_NATIVE_SHADOW_OWNER_SOURCE] = (
            REPO / WILD_NATIVE_SHADOW_OWNER_SOURCE
        ).read_text().replace("|| spawn->object != object", "", 1)

        self.assertIn(
            "native-shadow-object-identity-unchecked",
            kinds(audit_structure(
                symbols,
                images,
                private_client_sources=sources,
            )),
        )

    def test_native_shadow_manager_identity_mutation_fails(self) -> None:
        symbols, images = complete_fixture()
        sources = {
            path: (REPO / path).read_text()
            for _module, path in PRIVATE_WILD_STATE_SOURCE_CLIENTS
        }
        owner = (REPO / WILD_NATIVE_SHADOW_OWNER_SOURCE).read_text()
        sources[WILD_NATIVE_SHADOW_OWNER_SOURCE] = owner.replace(
            "GetMapObjectByID(fieldSystem->mapObjectMan, spawn->objectId)",
            "spawn->object",
            1,
        )

        self.assertIn(
            "native-shadow-manager-identity-unchecked",
            kinds(audit_structure(
                symbols,
                images,
                private_client_sources=sources,
            )),
        )

    def test_native_shadow_map_generation_mutation_fails(self) -> None:
        symbols, images = complete_fixture()
        sources = {
            path: (REPO / path).read_text()
            for _module, path in PRIVATE_WILD_STATE_SOURCE_CLIENTS
        }
        owner = (REPO / WILD_NATIVE_SHADOW_OWNER_SOURCE).read_text()
        sources[WILD_NATIVE_SHADOW_OWNER_SOURCE] = owner.replace(
            "OVERWORLD_ACTOR_FIELD_CONTEXT_MAP_GENERATION(",
            "(",
            1,
        )

        self.assertIn(
            "native-shadow-map-generation-unchecked",
            kinds(audit_structure(
                symbols,
                images,
                private_client_sources=sources,
            )),
        )

    def test_renamed_function_in_retired_slot_fails(self) -> None:
        symbols, images = complete_fixture()
        retired = next(item for item in RETIRED_ENTRIES if item.module == "walk_module")
        spec = next(item for item in MODULES if item.key == retired.module)
        helper = definition("walk_module", "UnrelatedRenamedFunction", spec.base + 0x800)
        symbols.append(helper)
        images, walk = mutate(images, "walk_module")
        struct.pack_into("<I", walk, retired.address - spec.base, helper.address | 1)
        self.assertIn("retired-entry-shape", kinds(audit_structure(symbols, images)))

    def test_retired_slot_literal_fails_without_old_names(self) -> None:
        symbols, images = complete_fixture()
        images, wild = mutate(images, "wild_spawns")
        struct.pack_into("<I", wild, 0x400, RETIRED_ENTRIES[0].address)
        self.assertIn("retired-entry-reference", kinds(audit_structure(symbols, images)))

    def test_every_linked_client_is_scanned_for_retired_entry_references(self) -> None:
        for module in CLIENT_MODULES:
            with self.subTest(module=module):
                symbols, images = complete_fixture()
                images, client = mutate(images, module)
                struct.pack_into(
                    "<I", client, 0x300, RETIRED_ENTRIES[0].address
                )
                self.assertIn(
                    "retired-entry-reference",
                    kinds(audit_structure(symbols, images)),
                )

    def test_nonzero_retired_slot_fails_without_function_pointer(self) -> None:
        symbols, images = complete_fixture()
        retired = next(
            item
            for item in RETIRED_ENTRIES
            if item.capability == "hop" and item.module == "role_controller"
        )
        images, role = mutate(images, "role_controller")
        role[retired.address - 0x023BD400] = 0x7F
        self.assertIn("retired-entry-not-zero", kinds(audit_structure(symbols, images)))

    def test_staged_hop_task_pointer_table_is_retired(self) -> None:
        symbols, images = complete_fixture()
        retired = next(
            item
            for item in RETIRED_ENTRIES
            if item.label == "staged-Hop task pointers"
        )
        images, behavior = mutate(images, retired.module)
        behavior[retired.address - 0x023C3000] = 1

        self.assertIn(
            "retired-entry-not-zero",
            kinds(audit_structure(symbols, images)),
        )

    def test_mount_cannot_call_private_hop_planner(self) -> None:
        symbols, images = complete_fixture()
        images, mount = mutate(images, "mount")
        struct.pack_into("<I", mount, 0x400, 0x023BD4F1)
        self.assertIn("direct-hop-planner-reference", kinds(audit_structure(symbols, images)))

    def test_wild_cannot_call_private_teleport_planner(self) -> None:
        symbols, images = complete_fixture()
        images, wild = mutate(images, "wild_spawns")
        struct.pack_into("<I", wild, 0x400, 0x023BD4F9)
        self.assertIn(
            "direct-teleport-planner-reference",
            kinds(audit_structure(symbols, images)),
        )

    def test_every_non_owner_client_is_scanned_for_private_planners(self) -> None:
        for module in MOTION_PLANNER_CLIENTS:
            with self.subTest(module=module, planner="hop"):
                symbols, images = complete_fixture()
                images, client = mutate(images, module)
                struct.pack_into("<I", client, 0x300, 0x023BD4F1)
                self.assertIn(
                    "direct-hop-planner-reference",
                    kinds(audit_structure(symbols, images)),
                )
            with self.subTest(module=module, planner="teleport"):
                symbols, images = complete_fixture()
                images, client = mutate(images, module)
                struct.pack_into("<I", client, 0x300, 0x023BD4F9)
                self.assertIn(
                    "direct-teleport-planner-reference",
                    kinds(audit_structure(symbols, images)),
                )

    def test_retired_population_callback_slot_fails(self) -> None:
        symbols, images = complete_fixture()
        images, runtime = mutate(images, "wild_runtime")
        struct.pack_into(
            "<I",
            runtime,
            WILD_RUNTIME_POPULATION_CALLBACK_OFFSET,
            0x023BC901,
        )
        self.assertIn(
            "retired-runtime-callback", kinds(audit_structure(symbols, images))
        )

    def test_retired_acknowledge_callback_slot_fails(self) -> None:
        symbols, images = complete_fixture()
        images, runtime = mutate(images, "wild_runtime")
        struct.pack_into(
            "<I",
            runtime,
            WILD_RUNTIME_ACKNOWLEDGE_CALLBACK_OFFSET,
            0x023BC901,
        )
        self.assertIn(
            "retired-runtime-callback", kinds(audit_structure(symbols, images))
        )

    def test_population_thunk_body_fails_even_without_callback(self) -> None:
        symbols, images = complete_fixture()
        images, runtime = mutate(images, "wild_runtime")
        runtime[0x100 : 0x100 + len(LEGACY_POPULATION_THUNK)] = (
            LEGACY_POPULATION_THUNK
        )
        self.assertIn(
            "retired-population-thunk-body",
            kinds(audit_structure(symbols, images)),
        )

    def test_retired_runtime_callback_symbol_fails(self) -> None:
        symbols, images = complete_fixture()
        symbols.append(definition(
            "wild_runtime", "OverworldWildRuntime_AcknowledgeMotion", 0x023BC900
        ))
        self.assertIn(
            "retired-runtime-callback-symbol",
            kinds(audit_structure(symbols, images)),
        )

    def test_fixed_flee_policy_entry_fails(self) -> None:
        symbols, images = complete_fixture()
        images, helper = mutate(images, "wild_helper")
        spec = next(item for item in MODULES if item.key == "wild_helper")
        struct.pack_into(
            "<I",
            helper,
            WILD_HELPER_FLEE_FALLBACK_ENTRY - spec.base,
            spec.base + 0x500 | 1,
        )
        self.assertIn("retired-entry-not-zero", kinds(audit_structure(symbols, images)))

    def test_legitimate_adapter_names_are_allowed(self) -> None:
        symbols, images = complete_fixture()
        symbols.extend((definition("mount", "OverworldMount_DrainLandStream", 0x023BB900), definition("mount", "OverworldMount_SyncPresentation", 0x023BB920), definition("wild_spawns", "OverworldWildSpawns_IsTileOccupiedByObject", 0x023CE000), definition("wild_spawns", "OverworldWildSpawns_TryNextHopLandingCandidate", 0x023CE020)))
        result = audit_structure(symbols, images)
        self.assertTrue(result["passed"], result["issues"])

    def test_imports_and_absolute_aliases_are_not_definitions(self) -> None:
        parsed = parse_nm("""
                     U ActorSystem_RequestMotion
            023bc001 A RenamedWalkOwner
            023b7000 00000010 T ActorSystem_RequestMotion
            """, "mount")
        self.assertEqual([item.name for item in parsed], ["ActorSystem_RequestMotion"])


def small_rom(overlay_id: int, load_address: int, payload: bytes) -> bytes:
    y9_offset = 0x200
    fat_offset = y9_offset + 0x20
    file_offset = fat_offset + 8
    rom = bytearray(file_offset + len(payload))
    struct.pack_into("<II", rom, 0x48, fat_offset, 8)
    struct.pack_into("<II", rom, 0x50, y9_offset, 0x20)
    struct.pack_into("<8I", rom, y9_offset, overlay_id, load_address, len(payload), 0, 0, 0, 0, 0)
    struct.pack_into("<II", rom, fat_offset, file_offset, file_offset + len(payload))
    rom[file_offset:] = payload
    return bytes(rom)


class PackageIdentityTests(unittest.TestCase):
    SPEC = ModuleSpec("fixture", "fixture.o", "fixture.bin", 7, 0x023B0000)
    IMAGE = b"\x10\x20\x30\x40\x50\x60\x70\x80"

    def audit(self, rom: bytes, linked: bytes | None = None, output: bytes | None = None, symbols: list[Symbol] | None = None) -> dict:
        return audit_packaging(rom, [self.SPEC], {"fixture": self.IMAGE if linked is None else linked}, {"fixture": self.IMAGE if output is None else output}, [] if symbols is None else symbols)

    def test_identity_passes(self) -> None:
        result = self.audit(small_rom(7, self.SPEC.base, self.IMAGE), symbols=[Symbol("fixture", self.SPEC.base + 2, 2, "T", "Owner")])
        self.assertTrue(result["passed"], result["issues"])

    def test_stale_rom_fails(self) -> None:
        stale = self.IMAGE[:-1] + b"\x00"
        self.assertIn("output-rom-mismatch", kinds(self.audit(small_rom(7, self.SPEC.base, stale))))

    def test_standalone_overlay_with_extra_packaged_bytes_fails(self) -> None:
        packaged = self.IMAGE + b"\x00"
        self.assertIn(
            "output-rom-mismatch",
            kinds(self.audit(small_rom(7, self.SPEC.base, packaged))),
        )

    def test_linked_output_mismatch_fails(self) -> None:
        self.assertIn("linked-output-mismatch", kinds(self.audit(small_rom(7, self.SPEC.base, self.IMAGE), linked=b"different")))

    def test_wrong_load_address_fails(self) -> None:
        self.assertIn("wrong-overlay-load-address", kinds(self.audit(small_rom(7, self.SPEC.base + 4, self.IMAGE))))

    def test_symbol_outside_package_fails(self) -> None:
        symbol = Symbol("fixture", self.SPEC.base + len(self.IMAGE) + 4, 2, "T", "Owner")
        self.assertIn("symbol-outside-package", kinds(self.audit(small_rom(7, self.SPEC.base, self.IMAGE), symbols=[symbol])))

    def test_fixed_fragment_matches_its_slice_in_packaged_overlay(self) -> None:
        package_base = self.SPEC.base - 2
        fragment = ModuleSpec(
            "fixture",
            "fixture.o",
            "fixture.bin",
            7,
            self.SPEC.base,
            package_base,
        )
        packaged = b"\xAA\xBB" + self.IMAGE + b"\xCC\xDD"
        result = audit_packaging(
            small_rom(7, package_base, packaged),
            [fragment],
            {"fixture": self.IMAGE},
            {"fixture": self.IMAGE},
            [Symbol("fixture", self.SPEC.base + 2, 2, "T", "Owner")],
        )
        self.assertTrue(result["passed"], result["issues"])

    def test_fixed_fragment_mutation_in_packaged_overlay_fails(self) -> None:
        package_base = self.SPEC.base - 2
        fragment = ModuleSpec(
            "fixture",
            "fixture.o",
            "fixture.bin",
            7,
            self.SPEC.base,
            package_base,
        )
        mutated = self.IMAGE[:-1] + b"\x00"
        packaged = b"\xAA\xBB" + mutated + b"\xCC\xDD"
        result = audit_packaging(
            small_rom(7, package_base, packaged),
            [fragment],
            {"fixture": self.IMAGE},
            {"fixture": self.IMAGE},
            [],
        )
        self.assertIn("output-rom-mismatch", kinds(result))

    def test_fixed_fragment_symbol_outside_module_fails(self) -> None:
        package_base = self.SPEC.base - 2
        fragment = ModuleSpec(
            "fixture",
            "fixture.o",
            "fixture.bin",
            7,
            self.SPEC.base,
            package_base,
        )
        packaged = b"\xAA\xBB" + self.IMAGE + b"\xCC\xDD"
        symbol = Symbol(
            "fixture",
            self.SPEC.base + len(self.IMAGE),
            1,
            "T",
            "OutsideFragment",
        )
        result = audit_packaging(
            small_rom(7, package_base, packaged),
            [fragment],
            {"fixture": self.IMAGE},
            {"fixture": self.IMAGE},
            [symbol],
        )
        self.assertIn("symbol-outside-package", kinds(result))


if __name__ == "__main__":
    unittest.main()
