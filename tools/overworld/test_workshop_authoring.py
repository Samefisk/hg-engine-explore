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
                # Routines.
                "apply-scavenger",
                "apply-sprint",
                "apply-floaty-bounce",
                "apply-small-bird-hop",
                "apply-erratic-flutter",
                "apply-meander",
                "apply-hop-around",
                "apply-idle",
                "apply-drowsy-wander",
                "apply-perch",
                "apply-rest",
                # Placements.
                "apply-fly-in",
                "apply-canopy-access",
                "apply-flower-bed",
                # Capabilities.
                "apply-notice-player",
                "apply-teleport",
                "apply-stalker",
                "apply-long-hop",
                "apply-canopy-hop",
                "apply-throw",
                "apply-ram",
                "apply-heavy-stomp",
                # Attitudes.
                "apply-startled",
                "apply-ambush",
                "apply-playful",
                "apply-skittish",
                # Style.
                "apply-waddle",
                # Follower/Mount.
                "apply-follower",
                "apply-mounted",
                # Modifiers.
                "apply-asleep",
            ],
        )

    def test_override_profile_classifications_match_behavior_layers(self) -> None:
        profiles = {profile["id"]: profile for profile in self.catalog["profiles"]}
        classifications = [
            profiles[application["profile"]].get("classification")
            for application in self.catalog["applications"]
        ]
        self.assertEqual(
            classifications,
            ["routine"] * 11
            + ["placement"] * 3
            + ["capability"] * 8
            + ["attitude"] * 4
            + ["style"]
            + ["follower-mount"] * 2
            + ["modifier"],
        )
        VIEWER.validate_behavior_catalog(self.catalog)
        invalid = copy.deepcopy(self.catalog)
        invalid["profiles"][4]["classification"] = "behavior"
        with self.assertRaisesRegex(VIEWER.ParseError, "classification is not supported"):
            VIEWER.validate_behavior_catalog(invalid)

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
        for lane_offset in (71, 143):
            self.assertEqual(baseline_profile[lane_offset], original_value)
            self.assertEqual(actual_profile[lane_offset], changed_value)
        self.assertNotEqual(actual["fingerprint"], self.baseline["fingerprint"])

    def test_mount_gait_fields_inherit_and_override_independently(self) -> None:
        defaults = {"mountBounce": 2, "mountStride": 2, "mountSettle": 1, "mountLean": 1}
        mounted_index = next(
            index for index, application in enumerate(self.catalog["applications"])
            if application["id"] == self.catalog["runtimeBindings"]["mountedApplication"]
        )
        mounted_profile = next(profile for profile in self.catalog["profiles"] if profile["id"] == "mounted")
        self.assertFalse(set(defaults) & set(mounted_profile["fields"]))
        request = {**REQUEST, "species": 234, "forcedOverrideMask": 1 << mounted_index}
        baseline = native_resolver.resolve(None, request, root=REPO, executable=self.baseline_executable)
        for field, expected in defaults.items():
            for lane in (0, 1):
                self.assertEqual(resolved_lane_field(baseline, field, lane), expected)

        for field in defaults:
            with self.subTest(field=field):
                changed = copy.deepcopy(self.catalog)
                sprint = next(profile for profile in changed["profiles"] if profile["id"] == "sprint")
                sprint["fields"][field] = {"operator": "replace", "value": 3}
                catalog_path = self.temp / f"{field}-catalog.json"
                catalog_path.write_text(json.dumps(changed) + "\n")
                executable = native_resolver.build(REPO, force=True, catalog=catalog_path, output=self.temp / f"resolver-{field}")
                actual = native_resolver.resolve(None, request, root=REPO, executable=executable)
                for sibling, expected in defaults.items():
                    for lane in (0, 1):
                        self.assertEqual(resolved_lane_field(actual, sibling, lane), 3 if sibling == field else expected)
                before = bytes.fromhex(baseline["profileHex"])
                after = bytes.fromhex(actual["profileHex"])
                self.assertEqual(len(after), 144)
                self.assertEqual([value for index, value in enumerate(after) if index not in (16, 88)],
                                 [value for index, value in enumerate(before) if index not in (16, 88)])
                neighbour = native_resolver.resolve(None, REQUEST, root=REPO, executable=executable)
                self.assertEqual(neighbour["profileHex"], self.baseline["profileHex"])
                self.assertEqual(neighbour["fingerprint"], self.baseline["fingerprint"])

    def test_mount_gait_bounds_and_stride_labels_are_explicit(self) -> None:
        options = VIEWER.build_edit_options({}, [])
        self.assertEqual([option["label"] for option in options["mountStride"]],
                         ["16 px per cycle", "32 px per cycle", "48 px per cycle", "64 px per cycle"])
        for field in ("mountBounce", "mountStride", "mountSettle", "mountLean"):
            for value in (-1, 4):
                invalid = copy.deepcopy(self.catalog)
                profile = next(item for item in invalid["profiles"] if item["id"] == "sprint")
                profile["fields"][field] = {"operator": "replace", "value": value}
                with self.assertRaises((VIEWER.ParseError, ValueError)):
                    VIEWER.validate_behavior_catalog(invalid)
            for operator in ("relative", "atLeast", "atMost"):
                invalid = copy.deepcopy(self.catalog)
                profile = next(item for item in invalid["profiles"] if item["id"] == "sprint")
                profile["fields"][field] = {"operator": operator, "value": 1}
                with self.assertRaises((VIEWER.ParseError, ValueError)):
                    VIEWER.validate_behavior_catalog(invalid)

    def test_sprint_is_applied_to_stantler_and_is_default_off(self) -> None:
        sprint_index = next(
            index
            for index, application in enumerate(self.catalog["applications"])
            if application["id"] == "apply-sprint"
        )
        sprint_bit = 1 << sprint_index
        stantler_request = {**REQUEST, "species": 234}
        sprint = native_resolver.resolve(
            None,
            stantler_request,
            root=REPO,
            executable=self.baseline_executable,
        )
        self.assertEqual(sprint["status"], 0)
        self.assertTrue(sprint["matchedOverrideMask"] & sprint_bit)
        self.assertTrue(sprint["appliedOverrideMask"] & sprint_bit)
        for lane in range(2):
            with self.subTest(mode="sprint", lane=lane):
                self.assertEqual(resolved_lane_field(sprint, "planTurnSkidPath", lane), 1)
                self.assertEqual(resolved_lane_field(sprint, "stopSkid", lane), 1)
                self.assertEqual(resolved_lane_field(sprint, "chainPauseAction", lane), 0)
                self.assertEqual(resolved_lane_field(sprint, "ramAccelerationSteps", lane), 0)
                self.assertEqual(resolved_lane_field(sprint, "hopMinDistance", lane), 2)
                self.assertEqual(resolved_lane_field(sprint, "hopMaxDistance", lane), 2)
                self.assertEqual(resolved_lane_field(sprint, "hopAllowVerticalObstacles", lane), 1)
                self.assertEqual(resolved_lane_field(sprint, "maxWalkSpeed", lane), 4)

        without_sprint = copy.deepcopy(self.catalog)
        sprint_application = without_sprint["applications"][sprint_index]
        members = sprint_application["target"]["members"]
        members[members.index("SPECIES_STANTLER")] = "SPECIES_BULBASAUR"
        catalog_path = self.temp / "sprint-without-stantler.json"
        catalog_path.write_text(json.dumps(without_sprint, indent=2) + "\n")
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
        self.assertFalse(default_off["matchedOverrideMask"] & sprint_bit)
        self.assertFalse(default_off["appliedOverrideMask"] & sprint_bit)
        for lane in range(2):
            with self.subTest(mode="default-off", lane=lane):
                self.assertEqual(
                    resolved_lane_field(default_off, "planTurnSkidPath", lane),
                    0,
                )
                self.assertEqual(
                    resolved_lane_field(default_off, "stopSkid", lane),
                    0,
                )

    def test_walk_authoring_avoids_short_step_pauses_and_one_move_chains(self) -> None:
        profiles = {profile["id"]: profile for profile in self.catalog["profiles"]}
        root = profiles[self.catalog["rootProfile"]]
        self.assertEqual(int(root["fields"]["walkPause"]["value"]), 0)
        self.assertEqual(int(root["fields"]["walkPauseVariance"]["value"]), 0)

        for profile in self.catalog["profiles"]:
            fields = profile["fields"]
            with self.subTest(profile=profile["id"]):
                if "walkPause" in fields:
                    self.assertEqual(int(fields["walkPause"]["value"]), 0)
                if "walkPauseVariance" in fields:
                    self.assertEqual(int(fields["walkPauseVariance"]["value"]), 0)
                if int(fields.get("ramAccelerationSteps", {"value": 0})["value"]) == 1:
                    self.assertEqual(
                        fields.get("chillAction", {}).get("value"),
                        "OW_WILD_BEHAVIOR_LOCOMOTION_HOP",
                        "a one-move Movement Chain must be explicitly Hop, never Walk",
                    )

    def test_meander_randomly_chooses_look_around_or_pause(self) -> None:
        profiles = {profile["id"]: profile for profile in self.catalog["profiles"]}
        meander = profiles["meander"]["fields"]
        self.assertEqual(
            meander["chainPauseAction"]["value"],
            "OW_WILD_BEHAVIOR_CHAIN_PAUSE_RANDOM_CHOICE | "
            "OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_LOOK_AROUND | "
            "OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_PAUSE",
        )
        self.assertEqual(meander["chainPauseActionChance"]["value"], 50)
        self.assertEqual(meander["walkPause"]["value"], 0)
        self.assertEqual(meander["walkPauseVariance"]["value"], 0)

        mareep = native_resolver.resolve(
            None,
            {**REQUEST, "species": 179},
            root=REPO,
            executable=self.baseline_executable,
        )
        expected_actions = 0x80 | (1 << (2 - 1)) | (1 << (6 - 1))
        for lane in range(2):
            with self.subTest(lane=lane):
                self.assertEqual(
                    resolved_lane_field(mareep, "chainPauseAction", lane),
                    expected_actions,
                )
                self.assertEqual(
                    resolved_lane_field(mareep, "chainPauseActionChance", lane),
                    50,
                )
                self.assertEqual(resolved_lane_field(mareep, "walkPause", lane), 0)
                self.assertEqual(
                    resolved_lane_field(mareep, "walkPauseVariance", lane),
                    0,
                )

        deck = VIEWER.build_profile_deck_data()
        combined = next(
            option
            for option in deck["editOptions"]["chainPauseAction"]
            if option["raw"] == meander["chainPauseAction"]["value"]
        )
        self.assertEqual(combined["label"], "Random: Look Around / Pause")

        expressions, _ = VIEWER.parse_define_expressions(VIEWER.DEFINE_SOURCE_FILES)
        macros = VIEWER.evaluate_defines(expressions)
        decoded = VIEWER.native_profile_value(
            macros, "chainPauseAction", expected_actions
        )
        self.assertEqual(decoded["value"], expected_actions)
        self.assertEqual(decoded["label"], "Random: Look Around / Pause")
        self.assertEqual(decoded["raw"], meander["chainPauseAction"]["value"])

    def test_chain_pause_action_sets_are_validated(self) -> None:
        numeric = copy.deepcopy(self.catalog)
        meander = next(
            profile for profile in numeric["profiles"] if profile["id"] == "meander"
        )
        for numeric_value in (162, 130):
            with self.subTest(valid_value=numeric_value):
                meander["fields"]["chainPauseAction"]["value"] = numeric_value
                VIEWER.validate_behavior_catalog(numeric)

        invalid_values = [
            128,
            "OW_WILD_BEHAVIOR_CHAIN_PAUSE_RANDOM_CHOICE | "
            "OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_PAUSE | "
            "OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_PAUSE",
            "OW_WILD_BEHAVIOR_CHAIN_PAUSE_RANDOM_CHOICE | "
            "OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_PAUSE | "
            "OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_UNKNOWN",
            "+162",
            "0b10100010",
            "0o242",
        ]
        for invalid_value in invalid_values:
            with self.subTest(value=invalid_value):
                invalid = copy.deepcopy(self.catalog)
                meander = next(
                    profile
                    for profile in invalid["profiles"]
                    if profile["id"] == "meander"
                )
                meander["fields"]["chainPauseAction"]["value"] = invalid_value
                with self.assertRaises(VIEWER.ParseError):
                    VIEWER.validate_behavior_catalog(invalid)

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

    def test_current_and_v2_outputs_derive_from_v4_catalog(self) -> None:
        self.assertFalse(hasattr(VIEWER, "load_behavior_catalog_v3"))
        self.assertFalse(hasattr(VIEWER, "lower_behavior_catalog_v3"))
        self.assertFalse(hasattr(VIEWER, "lower_behavior_catalog_v2"))
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
  conditionVisionMode,
  createProfileNamedPool,
  moveConditionalProfileCondition,
  removeConditionalProfileCondition,
  resolveProfilePoolSelection,
  setConditionVisionMode,
  sortProfileApplicationsByClassification,
  setProfileClassification,
  setConditionalProfileKind,
  systemOwnershipForApplication,
  updateProfileNamedPool,
}} from {json.dumps(module.as_uri())};

const source = JSON.parse(fs.readFileSync({json.dumps(str(catalog_path))}, 'utf8'));
const classProfiles = new Set(source.runtimeBindings.classOrder.map((item) => item.profile));
const conditionalParents = new Set(source.profiles.filter((item) => item.kind === 'conditional').map((item) => item.parent));
const application = source.applications.find((item) => {{
  const profile = source.profiles.find((candidate) => candidate.id === item.profile);
  return profile?.kind === 'normal' && item.target?.mode !== 'disabled'
    && item.target
    && !classProfiles.has(profile.id) && !conditionalParents.has(profile.id);
}});
assert.ok(application, 'fixture needs a normal override with a subject pool');
const originalApplications = source.applications.map((item) => item.id);
const originalProfiles = source.profiles.map((item) => item.id);
const originalSelectors = source.selectors.map((item) => item.id);
const originalClassification = source.profiles.find((item) => item.id === application.profile).classification;

const classified = setProfileClassification(source, application.id, 'capability');
assert.equal(classified.profiles.find((item) => item.id === application.profile).classification, 'capability');
assert.equal(source.profiles.find((item) => item.id === application.profile).classification, originalClassification);
const classificationRanks = new Map(['routine', 'placement', 'capability', 'attitude', 'style', 'follower-mount', 'modifier'].map((value, index) => [value, index]));
const classifiedProfiles = new Map(classified.profiles.map((item) => [item.id, item]));
const appliedRanks = classified.applications.map((item) => {{
  const value = classifiedProfiles.get(item.profile).classification;
  return classificationRanks.get(value === 'archetype' ? 'routine' : value) ?? classificationRanks.size;
}});
assert.deepEqual(appliedRanks, [...appliedRanks].sort((left, right) => left - right));
const unclassified = setProfileClassification(classified, application.id, '');
assert.equal(Object.hasOwn(unclassified.profiles.find((item) => item.id === application.profile), 'classification'), false);
assert.throws(() => setProfileClassification(source, application.id, 'behavior'), /not supported/);

const unsortedByTag = {{
  profiles: [
    {{ id: 'capability-a', classification: 'capability' }},
    {{ id: 'untagged', fields: {{ tiredProfile: {{ operator: 'replace', value: 'apply-capability-a' }} }} }},
    {{ id: 'capability-b', classification: 'capability' }},
    {{ id: 'routine', classification: 'routine', kind: 'conditional', conditions: [{{ subjects: {{ application: 'apply-capability-b' }} }}] }},
    {{ id: 'modifier', classification: 'modifier' }},
  ],
  applications: [
    {{ id: 'apply-capability-a', profile: 'capability-a' }},
    {{ id: 'apply-untagged', profile: 'untagged' }},
    {{ id: 'apply-capability-b', profile: 'capability-b' }},
    {{ id: 'apply-routine', profile: 'routine' }},
    {{ id: 'apply-modifier', profile: 'modifier' }},
  ],
}};
const sortedByTag = sortProfileApplicationsByClassification(unsortedByTag);
assert.deepEqual(sortedByTag.applications.map((item) => item.id), [
  'apply-routine',
  'apply-capability-a',
  'apply-capability-b',
  'apply-modifier',
  'apply-untagged',
]);
assert.equal(unsortedByTag.applications[0].id, 'apply-capability-a');
assert.equal(sortedByTag.profiles.find((item) => item.id === 'untagged').fields.tiredProfile.value, 'apply-capability-a');
assert.equal(sortedByTag.profiles.find((item) => item.id === 'routine').conditions[0].subjects.application, 'apply-capability-b');

const poolSource = {{ catalogVersion: 5, pools: [] }};
const createdPool = createProfileNamedPool(poolSource, 'Playful Pokémon', {{
  mode: 'members', match: {{
    groupMask: 'OW_WILD_BEHAVIOR_GROUP_NONE', species: 'OW_WILD_BEHAVIOR_MATCH_ANY_SPECIES',
    terrain: 'OW_WILD_BEHAVIOR_MATCH_ANY_TERRAIN', minLevel: 'OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY',
    maxLevel: 'OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY', shiny: 'OW_WILD_BEHAVIOR_MATCH_ANY_SHINY',
    behaviorClass: 'OW_WILD_BEHAVIOR_MATCH_ANY_CLASS',
  }}, members: ['SPECIES_PIKACHU'],
}});
assert.equal(createdPool.poolId, 'playful-pokemon');
assert.deepEqual(resolveProfilePoolSelection({{ pool: createdPool.poolId }}, createdPool.catalog).members, ['SPECIES_PIKACHU']);
const renamedPool = updateProfileNamedPool(createdPool.catalog, createdPool.poolId, {{ name: 'Playmates', members: ['SPECIES_PICHU'] }});
assert.equal(renamedPool.pools[0].name, 'Playmates');
assert.deepEqual(renamedPool.pools[0].members, ['SPECIES_PICHU']);

const visionCatalog = {{
  catalogVersion: 5,
  rootProfile: 'root',
  pools: [],
  profiles: [
    {{ id: 'root', name: 'Default', parent: null, kind: 'normal', fields: {{}} }},
    {{ id: 'watcher', name: 'Watcher', parent: 'root', kind: 'conditional', fields: {{}}, conditions: [{{ id: 'watch', subjects: {{ mode: 'all', match: {{}} , members: [] }}, when: {{ kind: 'notice-target', vision: {{ mode: 'current' }}, chancePercent: 100 }}, activation: {{ mode: 'while-true' }}, target: {{ kind: 'player' }} }}] }},
    {{ id: 'follower', name: 'Follower', parent: 'root', kind: 'normal', fields: {{}} }},
  ],
  selectors: [],
  applications: [{{ id: 'apply-watcher', profile: 'watcher' }}, {{ id: 'apply-follower', profile: 'follower', target: {{ mode: 'members', match: {{}}, members: ['SPECIES_PIKACHU'] }} }}],
  runtimeBindings: {{ classOrder: [{{ profile: 'root' }}], speciesSelectors: [], followerApplication: 'apply-follower', defaultTiredApplication: 'apply-follower', forcedAsleepApplication: 'missing' }},
}};
const customVision = setConditionVisionMode(visionCatalog, 'apply-watcher', 'watch', 'custom');
assert.equal(conditionVisionMode(customVision.profiles[1].conditions[0]), 'custom');
assert.deepEqual(customVision.profiles[1].conditions[0].when.vision, {{ mode: 'custom', range: 3, cone: 'forward-90', adjacentAwareness: true }});
assert.equal(Object.hasOwn(customVision.profiles[1].conditions[0].when, 'rangeKind'), false);
assert.equal(Object.hasOwn(customVision.profiles[1].conditions[0].when, 'rangeLength'), false);
assert.equal(Object.hasOwn(customVision.profiles[1].conditions[0].when, 'visionOptions'), false);
const currentVision = setConditionVisionMode(customVision, 'apply-watcher', 'watch', 'current');
assert.deepEqual(currentVision.profiles[1].conditions[0].when.vision, {{ mode: 'current' }});
assert.equal(systemOwnershipForApplication(visionCatalog, 'apply-follower'), 'Follower');
assert.throws(() => setConditionalProfileKind(visionCatalog, 'apply-follower', 'conditional'), /System-owned/);

let draft = setConditionalProfileKind(source, application.id, 'conditional');
let profile = draft.profiles.find((item) => item.id === application.profile);
let ownerApplication = draft.applications.find((item) => item.id === application.id);
assert.equal(profile.kind, 'conditional');
assert.equal(profile.conditions.length, 1);
assert.equal(profile.conditions[0].subjects.mode, application.target.mode);
assert.deepEqual(profile.conditions[0].subjects.members, application.target.members);
assert.equal(Object.hasOwn(ownerApplication, 'target'), false);
assert.deepEqual(draft.applications.map((item) => item.id), originalApplications);
assert.deepEqual(draft.profiles.map((item) => item.id), originalProfiles);
assert.deepEqual(draft.selectors.map((item) => item.id), originalSelectors);

const firstId = profile.conditions[0].id;
const cleanDraft = addConditionalProfileCondition(
  setConditionalProfileKind(source, application.id, 'conditional'),
  application.id,
);
const cleanProfile = cleanDraft.profiles.find((item) => item.id === application.profile);
const cleanRule = cleanProfile.conditions.at(-1);
assert.deepEqual(cleanRule.subjects, {{ mode: 'members', match: {{
  groupMask: 'OW_WILD_BEHAVIOR_GROUP_NONE',
  species: 'OW_WILD_BEHAVIOR_MATCH_ANY_SPECIES',
  terrain: 'OW_WILD_BEHAVIOR_MATCH_ANY_TERRAIN',
  minLevel: 'OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY',
  maxLevel: 'OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY',
  shiny: 'OW_WILD_BEHAVIOR_MATCH_ANY_SHINY',
  behaviorClass: 'OW_WILD_BEHAVIOR_MATCH_ANY_CLASS',
}}, members: [] }});
assert.equal(cleanRule.when.kind, 'notice-target');
assert.deepEqual(cleanRule.when.vision, {{ mode: 'current' }});
assert.equal(Object.hasOwn(cleanRule.when, 'rangeKind'), false);
assert.deepEqual(cleanRule.activation, {{ mode: 'while-true' }});
assert.deepEqual(cleanRule.target, {{ kind: 'player' }});
draft = addConditionalProfileCondition(draft, application.id, firstId);
profile = draft.profiles.find((item) => item.id === application.profile);
assert.equal(profile.conditions.length, 2);
const secondId = profile.conditions[1].id;
assert.notEqual(firstId, secondId);
const duplicated = JSON.parse(JSON.stringify(profile.conditions[1]));
duplicated.id = firstId;
assert.deepEqual(duplicated, profile.conditions[0]);
draft = moveConditionalProfileCondition(draft, application.id, secondId, -1);
profile = draft.profiles.find((item) => item.id === application.profile);
assert.deepEqual(profile.conditions.map((item) => item.id), [secondId, firstId]);
profile.conditions[0].activation = {{ mode: 'timed', durationFrames: 45, cooldownFrames: 90 }};
profile.conditions[0].target = {{ kind: 'actor', roles: ['wild'], selection: 'nearest', groupMask: 'OW_WILD_BEHAVIOR_GROUP_NONE', members: ['SPECIES_PIKACHU'] }};
profile.conditions[0].when = {{ kind: 'notice-target', vision: {{ mode: 'custom', range: 4, cone: 'forward-90', adjacentAwareness: false }}, chancePercent: 75 }};
const authoredErrors = canonicalCatalogStructuralErrors(draft, {{ fields: [], numericOverrideOperatorFieldKeys: [], boundedOverrideOperatorFieldKeys: [] }});
assert.deepEqual(authoredErrors.filter((error) => /duration|cooldown|target|Vision|notice/.test(error)), []);
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
noticeCondition.when = {{ kind: 'notice-target', vision: {{ mode: 'custom', range: 33, cone: 'wide', adjacentAwareness: 'yes' }}, chancePercent: 101 }};
const noticeErrors = canonicalCatalogStructuralErrors(invalidNotice);
assert.ok(noticeErrors.some((error) => /invalid custom Vision/.test(error)));
assert.ok(noticeErrors.some((error) => /notice chance/.test(error)));

const mixedNotice = JSON.parse(JSON.stringify(authored));
const mixedCondition = mixedNotice.profiles.find((item) => item.id === application.profile).conditions[0];
mixedCondition.when.rangeKind = 'OW_WILD_BEHAVIOR_CONDITION_RANGE_VISION_CUSTOM';
mixedCondition.when.rangeLength = 8;
mixedCondition.when.visionOptions = 5;
assert.ok(canonicalCatalogStructuralErrors(mixedNotice).some((error) => /must use the V5 Vision shape/.test(error)));

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
        self.assertNotIn('Old Active and atten' + 'tive values', profile_editor)
        self.assertNotIn('"active' + 'Profile"', profile_editor)
        self.assertNotIn('"atten' + 'tiveState"', profile_editor)
        self.assertNotIn('conditional' + 'States', profile_editor)
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

    def test_conditions_editor_uses_rule_first_user_language(self) -> None:
        profile_editor = (V2_STATIC / "profiles.js").read_text()
        self.assertIn("lifecycleSections.unshift(conditionSection);", profile_editor)
        self.assertIn(
            "sections.find((section) => section.id === CONDITIONS_LIFECYCLE_SECTION_ID)",
            profile_editor,
        )
        self.assertIn("When does this profile apply?", profile_editor)
        self.assertIn("Always applies", profile_editor)
        self.assertIn("Only when a rule is active", profile_editor)
        self.assertIn("Pokémon affected", profile_editor)
        self.assertIn("Activation rules", profile_editor)
        self.assertIn("Higher rules win.", profile_editor)
        self.assertIn("Stay active", profile_editor)
        self.assertIn("Can trigger again after", profile_editor)
        self.assertIn("Technical values", profile_editor)
        self.assertIn(
            "conditions.map((condition, sourceIndex) => ({ condition, sourceIndex })).reverse()",
            profile_editor,
        )
        self.assertNotIn("renderProfileKindControl", profile_editor)
        self.assertNotIn("Accepted terrain mask", profile_editor)
        self.assertNotIn("Checked terrain mask", profile_editor)
        self.assertNotIn("Duration (frames)", profile_editor)
        self.assertNotIn("Cooldown (frames)", profile_editor)

    def test_profile_building_block_tabs_use_the_final_order(self) -> None:
        profile_editor = (V2_STATIC / "profiles.js").read_text()
        profile_styles = (V2_STATIC / "v2.css").read_text()
        self.assertIn('id: "behavior",\n    title: "Behavior"', profile_editor)
        self.assertIn('id: "movement",\n    title: "Movement Style"', profile_editor)
        self.assertIn('id: "vision",\n    title: "Vision"', profile_editor)
        self.assertIn('id: "tired",\n    title: "Tired"', profile_editor)
        self.assertIn(
            'const LIFECYCLE_SECTION_IDS = Object.freeze(["spawn", "behavior", "movement", "vision", "tired"]);',
            profile_editor,
        )
        self.assertNotIn('title: "Chill state"', profile_editor)
        self.assertNotIn("Chill", profile_editor)
        self.assertNotIn("subtabs:", profile_editor)
        self.assertIn('data-lifecycle-theme="behavior"', profile_styles)
        self.assertIn('data-lifecycle-theme="movement"', profile_styles)
        self.assertIn('data-lifecycle-theme="vision"', profile_styles)
        self.assertNotIn('data-lifecycle-theme="chill"', profile_styles)
        self.assertNotIn('data-lifecycle-theme="active"', profile_styles)

    def test_override_profile_tags_keep_classification_separate_from_conditions(self) -> None:
        profile_editor = (V2_STATIC / "profiles.js").read_text()
        profile_styles = (V2_STATIC / "v2.css").read_text()
        self.assertIn('label: "Routine"', profile_editor)
        self.assertIn('label: "Placement"', profile_editor)
        self.assertIn('label: "Capability"', profile_editor)
        self.assertIn('label: "Attitude"', profile_editor)
        self.assertIn('label: "Style"', profile_editor)
        self.assertIn('label: "Follower/Mount"', profile_editor)
        self.assertIn('label: "Modifier"', profile_editor)
        self.assertIn('profile.catalogKind === "conditional"', profile_editor)
        self.assertIn('data-profile-tag="conditional"', profile_editor)
        self.assertIn('data-profile-classification="${escapeHtml(classification)}"', profile_editor)
        self.assertIn('name="classification"', profile_editor)
        self.assertIn('profileClassificationLabel(classificationFor(profile))', profile_editor)
        self.assertIn("sortProfileApplicationsByClassification", profile_editor)
        self.assertIn("classificationOrderDraft(sourceCatalog)", profile_editor)
        self.assertIn("function renderOverrideClassificationGroups", profile_editor)
        self.assertIn('class="pv2-profile-classification-divider"', profile_editor)
        self.assertIn("Profiles are grouped by type.", profile_editor)
        self.assertIn("Sets its order group", profile_editor)
        self.assertNotIn("Visual tag only", profile_editor)
        self.assertIn("function conditionalPreviewSpecies", profile_editor)
        self.assertIn('class="${conditional ? "is-conditional-member" : ""}"', profile_editor)
        self.assertIn('.pv2-profile-tag.is-conditional', profile_styles)
        self.assertIn('.pv2-profile-tag.is-system', profile_styles)
        self.assertIn('.pv2-profile-icons button.is-conditional-member', profile_styles)
        self.assertIn('opacity: .55', profile_styles)
        self.assertIn('.pv2-profile-row.override-profile[data-profile-classification="routine"]', profile_styles)
        self.assertIn('.pv2-profile-row.override-profile[data-profile-classification="placement"]', profile_styles)
        self.assertIn('.pv2-profile-classification-divider[data-profile-classification="routine"]', profile_styles)
        self.assertIn('.pv2-profile-classification-divider[data-profile-classification="placement"]', profile_styles)
        self.assertIn('position: sticky', profile_styles)

    def test_pb6_controls_cover_pools_vision_and_system_ownership(self) -> None:
        profile_editor = (V2_STATIC / "profiles.js").read_text()
        self.assertIn('data-pool-selection', profile_editor)
        self.assertIn('data-action="create-named-pool"', profile_editor)
        self.assertIn('data-named-pool-field="members"', profile_editor)
        self.assertIn('Use current Vision', profile_editor)
        self.assertIn('Use custom Vision', profile_editor)
        self.assertIn('target-cannot-see-subject', profile_editor)
        self.assertIn('profile.catalogKind === "conditional" && ["visionRange", "visionCone", "visionAdjacentAwareness"]', profile_editor)
        self.assertIn('systemOwnershipForApplication', profile_editor)
        self.assertIn('The game owns this profile link.', profile_editor)
        self.assertIn('application?.target?.pool ? "" : renderOverrideTarget(profile)', profile_editor)

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
