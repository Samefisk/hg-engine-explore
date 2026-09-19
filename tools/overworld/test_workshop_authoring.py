"""Fail-closed checks for Workshop behavior authoring and host resolution."""

from __future__ import annotations

import copy
import importlib.util
import inspect
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parents[2]
VIEWER_PATH = REPO / "scripts/overworld_behavior_profile_viewer.py"
V2_TOOLS = REPO / "tools/overworld-viewer-v2"
V2_STATIC = V2_TOOLS / "static"
if str(V2_TOOLS) not in sys.path:
    sys.path.insert(0, str(V2_TOOLS))

import native_resolver  # noqa: E402
import reliability  # noqa: E402
import server as v2_server  # noqa: E402


def load_viewer():
    spec = importlib.util.spec_from_file_location("workshop_authoring_test_viewer", VIEWER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {VIEWER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VIEWER = load_viewer()
REQUEST = {
    "species": 0,
    "level": 1,
    "terrain": 0,
    "shiny": 0,
    "groupFlags": 0,
    "behaviorClass": 0,
}


def resolved_lane_field(result: dict, key: str, lane: int) -> int:
    schema = json.loads((REPO / "tools/overworld/behavior_schema.json").read_text())
    field = next(item for item in schema["fields"] if item["key"] == key)
    lane_size = schema["compactSize"]
    raw = bytes.fromhex(result["profileHex"])
    width = {"u8": 1, "u16": 2}[field["cType"]]
    start = lane * lane_size + field["offset"]
    value = int.from_bytes(raw[start:start + width], "little")
    if "bitOffset" in field:
        value >>= field["bitOffset"]
        value &= (1 << field["bitWidth"]) - 1
    return value


class WorkshopAuthoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="workshop-authoring-test-")
        cls.temp = Path(cls.temporary.name)
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.catalog = json.loads(VIEWER.BEHAVIOR_CATALOG_SOURCE.read_text())
        cls.baseline_executable = native_resolver.build(
            REPO,
            force=True,
            output=cls.temp / "resolver-baseline",
        )
        cls.baseline = native_resolver.resolve(
            None,
            REQUEST,
            root=REPO,
            executable=cls.baseline_executable,
        )

    def test_profile_applications_keep_behavior_layer_order(self) -> None:
        self.assertEqual(
            [application["id"] for application in self.catalog["applications"]],
            [
                # Archetypes and their lane helpers.
                "apply-teleport-stalker-override",
                "apply-nervous-scavenger",
                "apply-hopping-scavenger",
                "apply-runner",
                "apply-floaty-bounce",
                "apply-bird",
                "apply-flying-insect",
                "apply-gentle-grazer",
                "apply-test",
                "apply-swaying-plant",
                "apply-swaying-plant-active",
                "apply-swaying-plant-tired",
                "apply-ambush-plant",
                "apply-ambush-plant-active",
                "apply-ambush-plant-tired",
                "apply-default-active",
                "apply-default-tired",
                # Capabilities and their conditional helpers.
                "apply-canopy-hopper",
                "apply-canopy-hop-surface",
                "apply-throwing",
                "apply-flower",
                "apply-bird-rooftop",
                "apply-aggressive-ram-override",
                # Attitudes.
                "apply-playful",
                "apply-skittish",
                "apply-baby-pokemon",
                # No style traits are authored yet.
                # Follower/Mount.
                "apply-follower-pokemon",
                # Modifiers.
                "apply-forced-asleep",
            ],
        )

    def test_checked_in_positional_profile_edits_do_not_change_resolution(self) -> None:
        source = VIEWER.BEHAVIOR_DATA_SOURCE.read_text()
        start, end = VIEWER.initializer_brace_span(
            source, "sOverworldWildBehaviorClassProfiles"
        )
        initializer = source[start:end]
        def poison_numeric_value(match: re.Match[str]) -> str:
            value = int(match.group(2))
            replacement = value + 1 if value < 255 else value - 1
            return f"{match.group(1)}{replacement},{match.group(3)}"

        poisoned_initializer, count = re.subn(
            r"(?m)^(\s*)([0-9]+),(\s*)$",
            poison_numeric_value,
            initializer,
            count=1,
        )
        self.assertEqual(count, 1, "test did not alter a positional class-profile value")
        poisoned_source = self.temp / "poisoned-OverworldWildBehaviorData.c"
        poisoned_source.write_text(
            source[:start] + poisoned_initializer + source[end:]
        )
        executable = native_resolver.build(
            REPO,
            force=True,
            source_template=poisoned_source,
            output=self.temp / "resolver-poisoned-c",
        )
        actual = native_resolver.resolve(
            None, REQUEST, root=REPO, executable=executable
        )
        self.assertEqual(actual, self.baseline)

    def test_named_catalog_change_reaches_canonical_resolver(self) -> None:
        changed = copy.deepcopy(self.catalog)
        root = next(
            profile
            for profile in changed["profiles"]
            if profile["id"] == changed["rootProfile"]
        )
        original_value = int(root["fields"]["walkAccelerationStep"]["value"])
        changed_value = 3 if original_value != 3 else 4
        root["fields"]["walkAccelerationStep"]["value"] = changed_value
        catalog_path = self.temp / "changed-catalog.json"
        catalog_path.write_text(json.dumps(changed, indent=2) + "\n")
        executable = native_resolver.build(
            REPO,
            force=True,
            catalog=catalog_path,
            output=self.temp / "resolver-changed-json",
        )
        actual = native_resolver.resolve(
            None, REQUEST, root=REPO, executable=executable
        )
        baseline_profile = bytes.fromhex(self.baseline["profileHex"])
        actual_profile = bytes.fromhex(actual["profileHex"])
        for lane_offset in (71, 143, 215):
            self.assertEqual(baseline_profile[lane_offset], original_value)
            self.assertEqual(actual_profile[lane_offset], changed_value)
        self.assertNotEqual(actual["fingerprint"], self.baseline["fingerprint"])

    def test_runner_is_applied_to_stantler_and_is_default_off(self) -> None:
        runner_index = next(
            index
            for index, application in enumerate(self.catalog["applications"])
            if application["id"] == "apply-runner"
        )
        runner_bit = 1 << runner_index
        stantler_request = {**REQUEST, "species": 234}
        runner = native_resolver.resolve(
            None,
            stantler_request,
            root=REPO,
            executable=self.baseline_executable,
        )
        self.assertEqual(runner["status"], 0)
        self.assertTrue(runner["matchedOverrideMask"] & runner_bit)
        self.assertTrue(runner["appliedOverrideMask"] & runner_bit)
        for lane in range(3):
            with self.subTest(mode="runner", lane=lane):
                self.assertEqual(resolved_lane_field(runner, "planTurnSkidPath", lane), 1)
                self.assertEqual(resolved_lane_field(runner, "stopSkid", lane), 1)
                self.assertEqual(resolved_lane_field(runner, "chainPauseAction", lane), 7)
                self.assertEqual(resolved_lane_field(runner, "ramAccelerationSteps", lane), 6)
                self.assertEqual(resolved_lane_field(runner, "maxWalkSpeed", lane), 4)

        without_runner = copy.deepcopy(self.catalog)
        runner_application = without_runner["applications"][runner_index]
        members = runner_application["target"]["members"]
        members[members.index("SPECIES_STANTLER")] = "SPECIES_BULBASAUR"
        catalog_path = self.temp / "runner-without-stantler.json"
        catalog_path.write_text(json.dumps(without_runner, indent=2) + "\n")
        executable = native_resolver.build(
            REPO,
            force=True,
            catalog=catalog_path,
            output=self.temp / "resolver-runner-without-stantler",
        )
        default_off = native_resolver.resolve(
            None,
            stantler_request,
            root=REPO,
            executable=executable,
        )
        self.assertEqual(default_off["status"], 0)
        self.assertFalse(default_off["matchedOverrideMask"] & runner_bit)
        self.assertFalse(default_off["appliedOverrideMask"] & runner_bit)
        for lane in range(3):
            with self.subTest(mode="default-off", lane=lane):
                self.assertEqual(
                    resolved_lane_field(default_off, "planTurnSkidPath", lane),
                    0,
                )
                self.assertEqual(
                    resolved_lane_field(default_off, "stopSkid", lane),
                    0,
                )

    def test_invalid_named_catalog_does_not_fall_back_to_generated_c(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        root = next(
            profile
            for profile in catalog["profiles"]
            if profile["id"] == catalog["rootProfile"]
        )
        del root["fields"]["walkPause"]
        catalog_path = self.temp / "invalid-catalog.json"
        catalog_path.write_text(json.dumps(catalog, indent=2) + "\n")
        with self.assertRaisesRegex(RuntimeError, "could not generate resolver input"):
            native_resolver.build(
                REPO,
                force=True,
                catalog=catalog_path,
                output=self.temp / "resolver-invalid-json",
            )

    def test_legacy_and_v2_paths_do_not_call_positional_profile_parsers(self) -> None:
        retired_parsers = (
            "validate_behavior_catalog_sources",
            "parse_profile",
            "parse_full_class_rules",
            "parse_species_class_rules",
            "parse_behavior_overrides",
            "parse_behavior_conditional_states",
            "parse_override_profile_names",
        )
        patches = [
            mock.patch.object(
                VIEWER,
                name,
                side_effect=AssertionError(f"live Workshop called retired parser {name}"),
            )
            for name in retired_parsers
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        legacy = VIEWER.build_data(
            include_routes=False,
            include_spawn_settings=False,
        )
        v2 = reliability.resolve_context(
            VIEWER,
            "SPECIES_BULBASAUR",
            "1",
            "OW_WILD_SPAWN_TERRAIN_LAND",
            "0",
        )
        VIEWER.validate_override_profile_source()
        self.assertEqual(
            len(legacy["variableOverrides"]),
            len(self.catalog["applications"]),
        )
        self.assertEqual(v2["apiVersion"], 2)
        self.assertEqual(v2["selectedProfile"]["id"], self.catalog["rootProfile"])
        self.assertTrue(all(
            layer["kind"] in {"selection", "application"}
            for layer in v2["resolverLayers"]
        ))
        self.assertNotIn("baseProfile", v2)
        self.assertNotIn("matchedOverrideOrders", v2)
        self.assertNotIn("matchedOverrideProfileOrders", v2)

    def test_workshop_groups_match_canonical_spawn_metadata(self) -> None:
        expressions, species_order = VIEWER.parse_define_expressions(
            VIEWER.DEFINE_SOURCE_FILES
        )
        macros = VIEWER.evaluate_defines(expressions)
        species = VIEWER.parse_species(expressions, macros, species_order)
        VIEWER.apply_species_type_metadata(
            species, VIEWER.parse_species_type_metadata(macros)
        )
        canonical_types = VIEWER.parse_species_type_metadata(
            macros,
            canonical_symbols=True,
        )
        by_symbol = {entry["symbol"]: entry for entry in species}
        self.assertEqual(
            VIEWER.canonical_spawn_group_flags(
                by_symbol["SPECIES_GASTLY"], canonical_types
            ),
            0x222,
        )
        self.assertEqual(
            VIEWER.canonical_spawn_group_flags(
                by_symbol["SPECIES_PICHU"], canonical_types
            ),
            0x8001,
        )
        self.assertTrue(canonical_types["SPECIES_MIME_JR"])
        self.assertTrue(
            VIEWER.canonical_spawn_group_flags(
                by_symbol["SPECIES_MIME_JR"], canonical_types
            )
            & VIEWER.spawn_metadata.GROUP_BABY
        )

    def test_move_from_off_screen_is_the_only_state_one_editor_choice(self) -> None:
        data = VIEWER.build_data(
            include_routes=False,
            include_spawn_settings=False,
        )
        options = data["editOptions"]["spawnState"]
        state_one = [option for option in options if option["value"] == 1]
        self.assertEqual(
            state_one,
            [{
                "raw": "OW_WILD_BEHAVIOR_SPAWN_STATE_MOVE_FROM_OFF_SCREEN",
                "label": "Move From Off Screen",
                "value": 1,
            }],
        )
        self.assertFalse(
            any("RUN_FROM_OFF_SCREEN" in option["raw"] for option in options)
        )

    def test_v2_shell_uses_lazy_deck_endpoints_and_one_profile_domain(self) -> None:
        shell = (V2_STATIC / "v2.js").read_text()
        profile_editor = (V2_STATIC / "profiles.js").read_text()
        index = (V2_STATIC / "index.html").read_text()
        self.assertNotIn('api.get("/data.json', shell)
        self.assertIn('/api/v2/decks/${name}', shell)
        self.assertIn('profileCatalog: { catalog:', profile_editor)
        for retired in ("profileMemberships", "profileOverrides"):
            self.assertNotIn(retired, profile_editor)
        self.assertIn('>Base profiles</strong>', index)
        self.assertIn('>Ordered overrides</strong>', index)
        self.assertIn('>Base only</option>', index)
        self.assertIn('>Overrides only</option>', index)

    def test_workshop_conditional_profile_model_round_trips_canonical_data(self) -> None:
        module = self.temp / "profiles-model.mjs"
        shutil.copyfile(V2_STATIC / "profiles.js", module)
        catalog_path = self.temp / "profiles-model-catalog.json"
        catalog_path.write_text(json.dumps(self.catalog))
        authored_path = self.temp / "profiles-model-authored.json"
        script = self.temp / "profiles-model-test.mjs"
        script.write_text(f"""
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {{
  addConditionalProfileCondition,
  canonicalCatalogStructuralErrors,
  moveConditionalProfileCondition,
  removeConditionalProfileCondition,
  setConditionalProfileKind,
}} from {json.dumps(module.as_uri())};

const source = JSON.parse(fs.readFileSync({json.dumps(str(catalog_path))}, 'utf8'));
const classProfiles = new Set(source.runtimeBindings.classOrder.map((item) => item.profile));
const conditionalParents = new Set(source.profiles.filter((item) => item.kind === 'conditional').map((item) => item.parent));
const application = source.applications.find((item) => {{
  const profile = source.profiles.find((candidate) => candidate.id === item.profile);
  return profile?.kind === 'normal' && item.target.mode !== 'disabled'
    && !classProfiles.has(profile.id) && !conditionalParents.has(profile.id);
}});
assert.ok(application, 'fixture needs a normal override with a subject pool');
const originalApplications = source.applications.map((item) => item.id);
const originalProfiles = source.profiles.map((item) => item.id);
const originalSelectors = source.selectors.map((item) => item.id);

let draft = setConditionalProfileKind(source, application.id, 'conditional');
let profile = draft.profiles.find((item) => item.id === application.profile);
let ownerApplication = draft.applications.find((item) => item.id === application.id);
assert.equal(profile.kind, 'conditional');
assert.equal(profile.conditions.length, 1);
assert.equal(profile.conditions[0].subjects.mode, application.target.mode);
assert.deepEqual(profile.conditions[0].subjects.members, application.target.members);
assert.equal(ownerApplication.target.mode, 'disabled');
assert.deepEqual(draft.applications.map((item) => item.id), originalApplications);
assert.deepEqual(draft.profiles.map((item) => item.id), originalProfiles);
assert.deepEqual(draft.selectors.map((item) => item.id), originalSelectors);

const firstId = profile.conditions[0].id;
draft = addConditionalProfileCondition(draft, application.id, firstId);
profile = draft.profiles.find((item) => item.id === application.profile);
assert.equal(profile.conditions.length, 2);
const secondId = profile.conditions[1].id;
assert.notEqual(firstId, secondId);
draft = moveConditionalProfileCondition(draft, application.id, secondId, -1);
profile = draft.profiles.find((item) => item.id === application.profile);
assert.deepEqual(profile.conditions.map((item) => item.id), [secondId, firstId]);
profile.conditions[0].activation = {{ mode: 'timed', durationFrames: 45, cooldownFrames: 90 }};
profile.conditions[0].target = {{ kind: 'actor', roles: ['wild'], selection: 'nearest', groupMask: 'OW_WILD_BEHAVIOR_GROUP_NONE', members: ['SPECIES_PIKACHU'] }};
profile.conditions[0].when = {{ kind: 'notice-target', rangeKind: 'OW_WILD_BEHAVIOR_ALERT_RANGE_RADIUS', rangeLength: 4, chancePercent: 75 }};
assert.deepEqual(canonicalCatalogStructuralErrors(draft, {{ fields: [], numericOverrideOperatorFieldKeys: [], boundedOverrideOperatorFieldKeys: [] }}).filter((error) => /duration|cooldown|target/.test(error)), []);
const authored = JSON.parse(JSON.stringify(draft));
assert.deepEqual(authored.applications.map((item) => item.id), originalApplications);
assert.deepEqual(authored.profiles.map((item) => item.id), originalProfiles);
assert.deepEqual(authored.selectors.map((item) => item.id), originalSelectors);
fs.writeFileSync({json.dumps(str(authored_path))}, JSON.stringify(authored, null, 2) + '\\n');

const tooMany = JSON.parse(JSON.stringify(authored));
const expanded = tooMany.profiles.find((item) => item.id === application.profile);
expanded.conditions = Array.from({{ length: 32 }}, (_, index) => ({{
  ...JSON.parse(JSON.stringify(expanded.conditions[0])),
  id: `condition-limit-${{index + 1}}`,
}}));
assert.ok(canonicalCatalogStructuralErrors(tooMany).some((error) => /at most 32 condition entries/.test(error)));

const invalidFacts = JSON.parse(JSON.stringify(authored));
const invalidCondition = invalidFacts.profiles.find((item) => item.id === application.profile).conditions[0];
invalidCondition.when = {{ kind: 'terrain-motion', terrainMask: 2, terrainOverrideMask: 1, minMovementSpeed: 12, maxMovementSpeed: 4 }};
invalidCondition.target = {{ kind: 'none' }};
const factErrors = canonicalCatalogStructuralErrors(invalidFacts);
assert.ok(factErrors.some((error) => /enabled terrains/.test(error)));
assert.ok(factErrors.some((error) => /reversed Walk-time/.test(error)));

const invalidNotice = JSON.parse(JSON.stringify(authored));
const noticeCondition = invalidNotice.profiles.find((item) => item.id === application.profile).conditions[0];
noticeCondition.when = {{ kind: 'notice-target', rangeKind: 9, rangeLength: 256, chancePercent: 101 }};
const noticeErrors = canonicalCatalogStructuralErrors(invalidNotice);
assert.ok(noticeErrors.some((error) => /notice shape/.test(error)));
assert.ok(noticeErrors.some((error) => /notice range/.test(error)));
assert.ok(noticeErrors.some((error) => /notice chance/.test(error)));

profile.conditions[0].subjects = {{ mode: 'members', match: profile.conditions[1].subjects.match, members: ['SPECIES_PIKACHU'] }};
assert.throws(() => setConditionalProfileKind(draft, application.id, 'normal'), /different subject pools/);
draft = removeConditionalProfileCondition(draft, application.id, secondId);
draft = setConditionalProfileKind(draft, application.id, 'normal');
profile = draft.profiles.find((item) => item.id === application.profile);
assert.equal(profile.kind, 'normal');
assert.equal(Object.hasOwn(profile, 'conditions'), false);
assert.deepEqual(draft.applications.find((item) => item.id === application.id).target, application.target);
assert.throws(() => removeConditionalProfileCondition(setConditionalProfileKind(source, application.id, 'conditional'), application.id, firstId), /at least one condition/);
""")
        completed = subprocess.run(
            ["node", script],
            cwd=REPO,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        generated = subprocess.run(
            [
                sys.executable,
                "scripts/generate_overworld_behavior_catalog.py",
                "--catalog",
                authored_path,
                "--source-output",
                self.temp / "OverworldWildBehaviorData.c",
                "--header-output",
                self.temp / "overworld_wild_behavior_data.h",
            ],
            cwd=REPO,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(generated.returncode, 0, generated.stderr or generated.stdout)

    def test_active_tab_is_removed_and_alert_is_repurposed(self) -> None:
        profile_editor = (V2_STATIC / "profiles.js").read_text()
        self.assertNotIn('title: "Active state"', profile_editor)
        self.assertNotIn('data-lifecycle-tab="active"', profile_editor)
        self.assertIn('title: "Conditions"', profile_editor)
        self.assertIn('Old Active and attentive values', profile_editor)
        self.assertIn(
            "if (resetConditionState) ui.conditionPreview.nextState = [];",
            profile_editor,
        )
        self.assertIn(
            "contextAbortController !== requestController",
            profile_editor,
        )
        self.assertIn(
            "targetSource.target?.candidateId",
            profile_editor,
        )

    def test_profile_commit_uses_focused_runtime_validation(self) -> None:
        validation_source = inspect.getsource(reliability.validate_commit_domains)
        self.assertIn("validate_profile_runtime_resolution", validation_source)
        self.assertNotIn("build_data", validation_source)

    def test_route_library_keeps_continuous_layout_with_cached_rows(self) -> None:
        route_editor = (V2_STATIC / "routes.js").read_text()
        self.assertNotIn("ROUTE_PAGE_SIZE", route_editor)
        self.assertNotIn("data-route-page", route_editor)
        self.assertNotIn("v2-route-pager", route_editor)
        self.assertIn("sourceGroupsCache", route_editor)
        self.assertIn("updateRouteRowStatus", route_editor)

    def test_inactive_decks_warm_without_eager_route_species_options(self) -> None:
        shell = (V2_STATIC / "v2.js").read_text()
        route_editor = (V2_STATIC / "routes.js").read_text()
        self.assertIn("scheduleDeckWarmup", shell)
        self.assertIn("requestIdleCallback", shell)
        self.assertIn("cachedDeckData", shell)
        self.assertIn("data.sourceRevision !== state.revision", shell)
        fetch_deck = shell.split("async function fetchDeckData", 1)[1].split(
            "function cachedDeckData", 1
        )[0]
        self.assertNotIn("state.revision =", fetch_deck)
        self.assertIn('"stale_deck_prefetch" : "deck_revision_changed"', fetch_deck)
        self.assertIn('refreshOnly: ["pokemon", name]', shell)
        self.assertIn("function ensureSpeciesDatalist(populate = false)", route_editor)
        self.assertIn("ensureSpeciesDatalist(true)", route_editor)
        self.assertNotIn("[route-load-profile]", route_editor)
        self.assertIn("if (previousScroll > 0) library.scrollTop = previousScroll", route_editor)

    def test_route_deck_payload_removes_repeated_species_display_metadata(self) -> None:
        species = {
            "symbol": "SPECIES_RATTATA",
            "name": "Rattata",
            "value": 19,
            "iconUrl": "/icons/19.png",
        }
        slot = {"species": copy.deepcopy(species), "path": "pokemon.morning.0"}
        payload = {
            "speciesOptions": [copy.deepcopy(species)],
            "routes": [{
                "id": 1,
                "species": [copy.deepcopy(species)],
                "speciesCount": 1,
                "pokemonTables": [{"slots": [copy.deepcopy(slot)]}],
                "slotTables": [{"slots": [copy.deepcopy(slot)]}],
                "headbuttTables": [{"slots": [copy.deepcopy(slot)]}],
                "swarms": [copy.deepcopy(slot)],
            }],
        }

        projected = v2_server._route_deck_payload(payload)

        route = projected["routes"][0]
        self.assertNotIn("species", route)
        self.assertNotIn("speciesCount", route)
        self.assertEqual(projected["speciesOptions"][0], species)
        for table_name in ("pokemonTables", "slotTables", "headbuttTables"):
            self.assertEqual(
                route[table_name][0]["slots"][0]["species"],
                {"symbol": "SPECIES_RATTATA"},
            )
        self.assertEqual(route["swarms"][0]["species"], {"symbol": "SPECIES_RATTATA"})


if __name__ == "__main__":
    unittest.main()
