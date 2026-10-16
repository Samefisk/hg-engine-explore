"""Focused UI-only checks for the PB6 Workshop profile editor."""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
STATIC = REPO / "tools/overworld-viewer-v2/static"


class WorkshopProfileBuildingBlocksTests(unittest.TestCase):
    def test_numeric_divide_uses_the_existing_text_field_and_round_trips(self) -> None:
        source = (STATIC / "profiles.js").read_text()
        # Execute the editor's actual private functions without adding a public
        # UI API or copying their rules into the fixture.
        names = (
            "isRelativeOverrideRaw", "parseNumericOverrideRaw",
            "numericOperatorStateLabel", "numericOperatorVisibleNote",
            "numericOverridePermissions", "isNumericProfileField",
            "numericOverrideAllowed", "numericInputProfile",
            "numericInputPermissions", "relativeFieldDeltaBounds",
            "numericOverrideOperandBounds", "renderProfileSelectOptions",
            "renderProfileValueEditor", "updateNumericOverrideInput",
        )
        bodies = []
        for name in names:
            start = source.index(f"  function {name}(")
            end = source.index("\n  function ", start + 1)
            bodies.append(source[start:end])
        with tempfile.TemporaryDirectory(prefix="workshop-divide-") as raw_temp:
            temp = Path(raw_temp)
            module = temp / "profiles.mjs"
            module.write_text(source + """
export { canonicalAuthoredRaw, canonicalAuthoredFromEditorRaw,
  canonicalApplyAuthored, projectCanonicalProfileDeck };
export function numericEditorFixture(data) {
  const invalidNumericOperatorInputs = new Set();
  const writes = [];
  const profile = { index: 'override:1', kind: 'override', isOverrideProfile: true };
  const findProfile = () => profile;
  const setField = (owner, field, raw) => writes.push({ owner, field, raw });
  const signalDirty = () => {};
  const fieldRaw = () => '34';
  const effectiveFieldCandidates = () => [];
""" + "\n".join(bodies) + """
  return { profile, writes, invalidNumericOperatorInputs,
    parseNumericOverrideRaw, numericOperatorStateLabel,
    numericOperatorVisibleNote, numericOverridePermissions,
    numericOverrideOperandBounds, renderProfileValueEditor,
    updateNumericOverrideInput };
}
""")
            script = temp / "test.mjs"
            script.write_text(f"""
import assert from 'node:assert/strict';
import {{ canonicalAuthoredRaw, canonicalAuthoredFromEditorRaw,
  canonicalApplyAuthored, projectCanonicalProfileDeck,
  canonicalCatalogStructuralErrors, numericEditorFixture }} from {json.dumps(module.as_uri())};
const data = {{
  fields: [{{ key: 'chillSpeed' }}, {{ key: 'stamina' }}, {{ key: 'chillAction' }}],
  numericProfileFieldKeys: ['chillSpeed', 'stamina'],
  numericOverrideOperatorFieldKeys: ['chillSpeed', 'stamina'],
  boundedOverrideOperatorFieldKeys: ['chillSpeed'],
  numericOverrideOperandMinimums: {{ chillSpeed: 1, stamina: 0 }},
  numericOverrideOperandMaximums: {{ chillSpeed: 32, stamina: 255 }},
  relativeOverrideDeltaRange: {{ min: -127, max: 127 }},
}};
const catalog = {{
  catalogVersion: 5, rootProfile: 'root', pools: [], selectors: [],
  profiles: [
    {{ id: 'root', name: 'Root', kind: 'normal', parent: null,
      fields: {{ chillSpeed: {{ operator: 'replace', value: '9' }} }} }},
    {{ id: 'layer', name: 'Layer', kind: 'normal', parent: 'root',
      fields: {{ chillSpeed: {{ operator: 'divide', value: 2 }} }} }},
  ],
  applications: ['follower', 'mounted', 'tired', 'asleep'].map(id => ({{
    id, profile: 'layer', target: {{ mode: 'members', members: ['SPECIES_PICHU'], match: {{}} }}
  }})),
  runtimeBindings: {{ classOrder: [{{ profile: 'root', symbol: 'DEFAULT' }}],
    followerApplication: 'follower', mountedApplication: 'mounted',
    defaultTiredApplication: 'tired', forcedAsleepApplication: 'asleep' }},
}};
assert.deepEqual(canonicalCatalogStructuralErrors(catalog, data), []);
for (const divisor of [1, 2, 127]) {{
  const authored = {{ operator: 'divide', value: divisor }};
  assert.equal(canonicalAuthoredRaw(authored, 'chillSpeed', new Map()), `/${{divisor}}`);
  assert.deepEqual(canonicalAuthoredFromEditorRaw(`/${{divisor}}`, 'chillSpeed', catalog, data), authored);
}}
assert.equal(canonicalApplyAuthored(9, {{ operator: 'divide', value: 2 }}, 'chillSpeed', data), 4);
assert.equal(canonicalApplyAuthored(1, {{ operator: 'divide', value: 127 }}, 'chillSpeed', data), 1);
assert.equal(canonicalApplyAuthored(255, {{ operator: 'divide', value: 1 }}, 'chillSpeed', data), 32);
assert.equal(canonicalApplyAuthored(1, {{ operator: 'divide', value: 127 }}, 'stamina', data), 0);
const projected = projectCanonicalProfileDeck(data, catalog);
const layer = projected.classes.find(item => item.catalogApplicationId === 'follower');
assert.equal(layer.profile.chillSpeed.raw, '/2');
assert.ok(layer.override.atLeastFields.includes('chillSpeed'));
assert.ok(layer.override.atMostFields.includes('chillSpeed'));
assert.deepEqual(layer.override.relativeFields, []);
assert.deepEqual(layer.override.divideFields, ['chillSpeed']);
const inherited = structuredClone(catalog);
inherited.runtimeBindings.classOrder.push({{ profile: 'layer', symbol: 'LAYER' }});
assert.equal(projectCanonicalProfileDeck(data, inherited).classes[1].profile.chillSpeed.value, 4);
for (const value of [0, 128, 2.5, '2', true]) {{
  const bad = structuredClone(catalog);
  bad.profiles[1].fields.chillSpeed.value = value;
  assert.ok(canonicalCatalogStructuralErrors(bad, data).some(error => error.includes('divisor')));
}}
const badRoot = structuredClone(catalog);
badRoot.profiles[0].fields.chillSpeed = {{ operator: 'divide', value: 2 }};
assert.ok(canonicalCatalogStructuralErrors(badRoot, data).some(error => error.includes('root') && error.includes('replace')));
const badField = structuredClone(catalog);
badField.profiles[1].fields.chillAction = {{ operator: 'divide', value: 2 }};
assert.ok(canonicalCatalogStructuralErrors(badField, data).some(error => error.includes('numeric operator')));

const ui = numericEditorFixture(data);
const options = Array.from({{ length: 32 }}, (_, index) => ({{ raw: String(index + 1), label: String(index + 1) }}));
globalThis.document = {{ getElementById: () => ({{ options: options.map(item => ({{ value: item.raw }})) }}) }};
function input(value, field = 'chillSpeed') {{
  const error = {{ textContent: '' }};
  return {{ value, error, attrs: {{}}, dataset: {{ fieldKey: field, fieldInstance: field, profileAllowInherit: 'true' }},
    matches: () => true, getAttribute: () => '',
    setAttribute(name, value) {{ this.attrs[name] = value; }},
    closest: () => ({{ querySelector: () => error }}) }};
}}
for (const [raw, canonical] of [['/2', '/2'], ['/001', '/1'], ['/127', '/127'], ['-2', '-2'], ['/<2', '/<2'], ['/>2', '/>2'], ['+1, /<2', '+1, /<2']]) {{
  const field = input(raw);
  ui.updateNumericOverrideInput(field, ui.profile, {{ render: false }});
  assert.equal(field.attrs['aria-invalid'], 'false', raw);
  assert.equal(ui.writes.at(-1).raw, canonical);
}}
// Divide is allowed on numeric fields which do not allow ordinary bounds.
const stamina = input('/2', 'stamina');
ui.updateNumericOverrideInput(stamina, ui.profile, {{ render: false }});
assert.equal(stamina.attrs['aria-invalid'], 'false');
assert.equal(ui.writes.at(-1).raw, '/2');
for (const [raw, fieldKey, profile] of [
  ['/0', 'chillSpeed', ui.profile], ['/128', 'chillSpeed', ui.profile],
  ['/2.5', 'chillSpeed', ui.profile], ['/-2', 'chillSpeed', ui.profile],
  ['/foo', 'chillSpeed', ui.profile], ['/2', 'chillAction', ui.profile],
  ['/2', 'chillSpeed', {{ index: 0 }}],
]) {{
  const before = ui.writes.length;
  const field = input(raw, fieldKey);
  ui.updateNumericOverrideInput(field, profile, {{ render: false }});
  assert.equal(field.attrs['aria-invalid'], 'true', `${{fieldKey}}:${{raw}}`);
  assert.equal(ui.writes.length, before);
}}
assert.deepEqual(ui.numericOverrideOperandBounds('chillSpeed', options, 'divide'), {{ min: 1, max: 127 }});
assert.match(ui.numericOperatorStateLabel('/2', false, 'chillSpeed'), /divide|Divid/);
assert.match(ui.numericOperatorVisibleNote('/2', 'chillSpeed'), /round down/);
const markup = ui.renderProfileValueEditor(ui.profile, 'chillSpeed', options, '/2', 'speed', 'Speed', 'description');
assert.match(markup, /type="text"/);
assert.match(markup, /value="\/2"/);
assert.match(markup, /1..127/);
assert.ok(!markup.includes('<select'));
assert.ok(!ui.renderProfileValueEditor({{ index: 0 }}, 'chillSpeed', options, '9', 'root', 'Speed', 'description').includes('/2'));
assert.match(ui.renderProfileValueEditor(ui.profile, 'chillAction', [], '', 'action', 'Action', 'description'), /<select/);
""")
            completed = subprocess.run(
                ["node", script], cwd=REPO, check=False, capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_movement_groups_preserve_partial_inactive_and_future_fields(self) -> None:
        with tempfile.TemporaryDirectory(prefix="workshop-movement-groups-") as raw_temp:
            temp = Path(raw_temp)
            module = temp / "profiles.mjs"
            shutil.copyfile(STATIC / "profiles.js", module)
            script = temp / "test.mjs"
            script.write_text(f"""
import assert from 'node:assert/strict';
import {{ movementEditorGroups, walkAccelerationMode, walkAccelerationInputMaximum }} from {json.dumps(module.as_uri())};
for (const [scope, parent, minimum, maximum] of [
  ['chill', 'chillAction', 'hopMinDistance', 'hopMaxDistance'],
  ['tired', 'tiredAction', 'tiredHopMinDistance', 'tiredHopMaxDistance'],
]) {{
  const nodes = [
    {{ field: parent, virtual: 'teleport-options' }},
    {{ field: minimum, inactive: true }}, {{ field: maximum }},
    {{ field: 'walkOptions', virtual: 'walk-options' }},
    ...['mountBounce', 'mountStride', 'mountSettle', 'mountLean'].map(field => ({{ field, inherited: true }})),
    {{ field: 'chainPauseAction' }}, {{ field: 'futureMovementField' }},
  ];
  const sections = movementEditorGroups(nodes, scope);
  const rendered = sections.flatMap(section => section.groups.flatMap(group => group.nodes));
  assert.equal(rendered.length, nodes.length);
  assert.equal(new Set(rendered).size, nodes.length);
  for (const node of nodes) assert.ok(rendered.includes(node));
  const hop = sections.find(section => section.id === 'hop');
  assert.deepEqual(hop.groups[0].nodes.map(node => node.field), [minimum, maximum]);
  assert.equal(hop.groups[0].nodes[0].inactive, true);
  const gait = sections.find(section => section.id === 'walk').groups.find(group => group.label === 'Mounted riding rhythm');
  assert.deepEqual(gait.nodes.map(node => node.field), ['mountBounce', 'mountStride', 'mountSettle', 'mountLean']);
  assert.ok(gait.nodes.every(node => node.inherited));
  assert.deepEqual(sections.find(section => section.id === 'teleport').groups[0].nodes, [nodes[0]]);
  assert.equal(sections.at(-1).id, 'other');
}}
assert.deepEqual(movementEditorGroups([]), []);
assert.equal(walkAccelerationMode('34'), 'linear');
assert.equal(walkAccelerationMode('33'), 'legacy');
assert.equal(walkAccelerationMode('', ['34', '34']), 'linear');
assert.equal(walkAccelerationMode('', ['34', '1']), 'mixed');
assert.equal(walkAccelerationMode('', []), 'legacy');
assert.equal(walkAccelerationInputMaximum('tilesToAccelerate', 'legacy', 255), 32);
assert.equal(walkAccelerationInputMaximum('tilesToAccelerate', 'linear', 255), 255);
assert.equal(walkAccelerationInputMaximum('tilesToAccelerate', 'mixed', 255), 255);
assert.equal(walkAccelerationInputMaximum('walkAccelerationStep', 'legacy', 34), 33);
assert.equal(walkAccelerationInputMaximum('chillSpeed', 'legacy', 32), 32);
""")
            completed = subprocess.run(
                ["node", script], cwd=REPO, check=False, capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_system_profile_with_inherited_movement_keeps_walk_controls_available(self) -> None:
        source = (STATIC / "profiles.js").read_text()
        self.assertIn(
            "movementWalkControlAvailability(raw, inherited, inheritedMovementCandidates)",
            source,
        )
        self.assertIn("append([fields.stopSkid], usesWalkAcceleration);", source)
        with tempfile.TemporaryDirectory(prefix="workshop-mounted-walk-") as raw_temp:
            temp = Path(raw_temp)
            module = temp / "profiles.mjs"
            shutil.copyfile(STATIC / "profiles.js", module)
            script = temp / "test.mjs"
            script.write_text(f"""
import assert from 'node:assert/strict';
import {{ movementWalkControlAvailability }} from {json.dumps(module.as_uri())};

const walk = 'OW_WILD_BEHAVIOR_LOCOMOTION_WANDER';
const hop = 'OW_WILD_BEHAVIOR_LOCOMOTION_HOP';
// Mounted has no target assignment. The editor cannot infer one inherited style.
assert.deepEqual(movementWalkControlAvailability('', true, []), {{ speed: true, walk: true }});
assert.deepEqual(movementWalkControlAvailability('', true, [walk]), {{ speed: true, walk: true }});
assert.deepEqual(movementWalkControlAvailability('', true, [hop]), {{ speed: false, walk: false }});
assert.deepEqual(movementWalkControlAvailability(hop, false, []), {{ speed: false, walk: false }});
assert.deepEqual(movementWalkControlAvailability(walk, false, []), {{ speed: true, walk: true }});
""")
            completed = subprocess.run(
                ["node", script], cwd=REPO, check=False, capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_dom_contract_has_final_tabs_labels_and_controls(self) -> None:
        source = (STATIC / "profiles.js").read_text()
        styles = (STATIC / "v2.css").read_text()

        self.assertIn(
            'const LIFECYCLE_SECTION_IDS = Object.freeze(["spawn", "behavior", "movement", "vision", "tired"]);',
            source,
        )
        self.assertIn("lifecycleSections.unshift(conditionSection);", source)
        for title in ("Conditions", "Spawn", "Behavior", "Movement Style", "Vision", "Tired"):
            self.assertIn(f'title: "{title}"', source)
        self.assertNotIn("Chill", source)
        self.assertNotIn('data-lifecycle-theme="active"', styles)

        expected_classifications = [
            "mood", "routine", "style", "placement", "follower", "capability", "attack", "attitude",
            "follower-mount", "modifier",
        ]
        positions = [source.index(f'value: "{value}"') for value in expected_classifications]
        self.assertEqual(positions, sorted(positions))
        for value in expected_classifications:
            self.assertIn(f'data-profile-classification="{value}"', styles)

        self.assertIn('data-pool-selection', source)
        self.assertIn('data-action="create-named-pool"', source)
        self.assertIn('data-named-pool-field="members"', source)
        self.assertIn('Use current Vision', source)
        self.assertIn('Use custom Vision', source)
        self.assertIn('"when.vision.range" : "when.rangeLength"', source)
        self.assertIn('data-condition-vision-same-tile', source)
        self.assertIn('Same tile awareness', source)
        self.assertIn('setConditionVisionAwareness(condition, key, event.target.checked, catalog.catalogVersion)', source)
        self.assertIn('target-cannot-see-subject', source)
        self.assertIn('The game owns this profile link.', source)
        self.assertIn('data-chain-pause-action', source)
        self.assertIn('CHAIN_PAUSE_RANDOM_CHOICE_RAW', source)
        self.assertIn('one of ${selected.size} is picked at random', source)
        self.assertIn(
            'control.key === "chainPauseAction"\n'
            '                  ? renderChainPauseActionInputs(profile, control.raw, override)',
            source,
        )
        self.assertIn('.pv2-profile-tag.is-system', styles)
        self.assertIn('.pv2-profile-icons button.is-conditional-member', styles)
        self.assertIn('opacity: .55', styles)

    def test_model_helpers_keep_pb6_ownership_and_order(self) -> None:
        with tempfile.TemporaryDirectory(prefix="workshop-pb6-") as raw_temp:
            temp = Path(raw_temp)
            module = temp / "profiles.mjs"
            shutil.copyfile(STATIC / "profiles.js", module)
            script = temp / "test.mjs"
            script.write_text(f"""
import assert from 'node:assert/strict';
import {{
  conditionVisionMode,
  createProfileNamedPool,
  decodeChainPauseActionSelection,
  encodeChainPauseActionSelection,
  resolveProfilePoolSelection,
  setConditionVisionMode,
  setConditionalProfileKind,
  sortProfileApplicationsByClassification,
  systemOwnershipForApplication,
  updateProfileNamedPool,
}} from {json.dumps(module.as_uri())};

const lookAround = 'OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_LOOK_AROUND';
const pause = 'OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_PAUSE';
const randomPauseActions = encodeChainPauseActionSelection([pause, lookAround]);
assert.equal(randomPauseActions,
  'OW_WILD_BEHAVIOR_CHAIN_PAUSE_RANDOM_CHOICE | '
  + 'OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_LOOK_AROUND | '
  + 'OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_PAUSE');
assert.deepEqual(decodeChainPauseActionSelection(randomPauseActions), [lookAround, pause]);
assert.deepEqual(decodeChainPauseActionSelection(162), [lookAround, pause]);
assert.deepEqual(decodeChainPauseActionSelection('0xA2'), [lookAround, pause]);
assert.equal(encodeChainPauseActionSelection([pause]), pause);
assert.equal(encodeChainPauseActionSelection([]), 'OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE');

const classifications = ['mood', 'routine', 'style', 'placement', 'follower', 'capability', 'attack', 'attitude', 'follower-mount', 'modifier'];
const profiles = classifications.flatMap((classification, index) => [
  {{ id: `${{classification}}-a`, classification }},
  ...(index === 0 ? [{{ id: `${{classification}}-b`, classification }}] : []),
]);
const sourceOrder = [
  'modifier-a', 'mood-b', 'routine-a', 'attack-a', 'style-a', 'placement-a', 'mood-a',
  'follower-mount-a', 'attitude-a', 'follower-a', 'capability-a',
];
const sorted = sortProfileApplicationsByClassification({{
  profiles,
  applications: sourceOrder.map((profile) => ({{ id: `apply-${{profile}}`, profile }})),
}});
assert.deepEqual(sorted.applications.map((item) => item.profile), [
  'mood-b', 'mood-a', 'routine-a', 'style-a', 'placement-a', 'follower-a', 'capability-a',
  'attack-a', 'attitude-a', 'follower-mount-a', 'modifier-a',
]);

const created = createProfileNamedPool({{ catalogVersion: 5, pools: [] }}, 'Playful Pokémon', {{
  mode: 'members', match: {{}}, members: ['SPECIES_PICHU'],
}});
assert.equal(created.poolId, 'playful-pokemon');
assert.deepEqual(resolveProfilePoolSelection({{ pool: created.poolId }}, created.catalog).members, ['SPECIES_PICHU']);
const updated = updateProfileNamedPool(created.catalog, created.poolId, {{ name: 'Playmates', members: ['SPECIES_CLEFFA'] }});
assert.equal(updated.pools[0].name, 'Playmates');
assert.deepEqual(updated.pools[0].members, ['SPECIES_CLEFFA']);

const catalog = {{
  catalogVersion: 5,
  rootProfile: 'default',
  pools: [],
  profiles: [
    {{ id: 'default', name: 'Default', parent: null, kind: 'normal', fields: {{}} }},
    {{ id: 'watcher', name: 'Watcher', parent: 'default', kind: 'normal', fields: {{}} }},
    {{ id: 'follower', name: 'Follower', parent: 'default', kind: 'normal', fields: {{}} }},
    {{ id: 'mounted', name: 'Mounted', parent: 'default', kind: 'normal', fields: {{}} }},
  ],
  selectors: [],
  applications: [
    {{ id: 'apply-watcher', profile: 'watcher', target: {{ mode: 'members', match: {{}}, members: ['SPECIES_SENTRET'] }} }},
    {{ id: 'apply-follower', profile: 'follower', target: {{ mode: 'members', match: {{}}, members: ['SPECIES_PIKACHU'] }} }},
    {{ id: 'apply-mounted', profile: 'mounted' }},
  ],
  runtimeBindings: {{ classOrder: [{{ profile: 'default' }}], followerApplication: 'apply-follower', mountedApplication: 'apply-mounted', forcedAsleepApplication: 'apply-asleep' }},
}};
assert.equal(systemOwnershipForApplication(catalog, 'apply-follower'), 'Follower');
assert.equal(systemOwnershipForApplication(catalog, 'apply-mounted'), 'Mounted');
assert.equal(systemOwnershipForApplication(catalog, 'apply-asleep'), 'Asleep');
assert.throws(() => setConditionalProfileKind(catalog, 'apply-follower', 'conditional'), /System-owned/);
assert.throws(() => setConditionalProfileKind(catalog, 'apply-mounted', 'conditional'), /System-owned/);

const conditional = setConditionalProfileKind(catalog, 'apply-watcher', 'conditional');
assert.equal(Object.hasOwn(conditional.applications[0], 'target'), false);
assert.equal(conditional.profiles[1].conditions[0].subjects.members[0], 'SPECIES_SENTRET');
assert.equal(conditionVisionMode(conditional.profiles[1].conditions[0]), 'current');
assert.deepEqual(conditional.profiles[1].conditions[0].when.vision, {{ mode: 'current' }});
const custom = setConditionVisionMode(
  conditional,
  'apply-watcher',
  conditional.profiles[1].conditions[0].id,
  'custom',
);
assert.equal(conditionVisionMode(custom.profiles[1].conditions[0]), 'custom');
assert.deepEqual(custom.profiles[1].conditions[0].when.vision, {{
  mode: 'custom', range: 3, cone: 'forward-90', adjacentAwareness: true,
}});
for (const key of ['rangeKind', 'rangeLength', 'visionOptions']) {{
  assert.equal(Object.hasOwn(custom.profiles[1].conditions[0].when, key), false);
}}

const legacy = JSON.parse(JSON.stringify(custom));
legacy.catalogVersion = 4;
legacy.profiles[1].conditions[0].when = {{
  kind: 'notice-target',
  rangeKind: 'OW_WILD_BEHAVIOR_CONDITION_RANGE_VISION_CURRENT',
  rangeLength: 0,
  chancePercent: 100,
}};
const legacyCustom = setConditionVisionMode(legacy, 'apply-watcher', legacy.profiles[1].conditions[0].id, 'custom');
assert.equal(conditionVisionMode(legacyCustom.profiles[1].conditions[0], 4), 'custom');
assert.equal(legacyCustom.profiles[1].conditions[0].when.rangeLength, 3);
assert.equal(legacyCustom.profiles[1].conditions[0].when.visionOptions, 5);
assert.equal(Object.hasOwn(legacyCustom.profiles[1].conditions[0].when, 'vision'), false);
""")
            completed = subprocess.run(
                ["node", script],
                cwd=REPO,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_same_tile_vision_lowers_only_when_enabled_and_migration_preserves_it(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "workshop_same_tile_viewer", REPO / "scripts/overworld_behavior_profile_viewer.py"
        )
        viewer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(viewer)
        custom_schema = json.loads(
            (REPO / "tools/overworld/schemas/behavior-authoring-v5.schema.json").read_text()
        )["$defs"]["customVision"]
        self.assertNotIn("sameTileAwareness", custom_schema["required"])
        self.assertEqual(custom_schema["properties"]["sameTileAwareness"], {
            "type": "boolean", "default": False,
        })
        for kind in ("notice-target", "notice-player", "target-cannot-see-subject"):
            for cone, cone_bits in (("forward-90", 1), ("forward-line", 2), ("cardinal-lines", 3)):
                when = {
                    "kind": kind, "vision": {
                        "mode": "custom", "range": 1, "cone": cone,
                        "adjacentAwareness": True,
                    }, "chancePercent": 100,
                }
                original = copy.deepcopy(when)
                self.assertEqual(viewer._normalize_v5_condition_when(when, "test")["visionOptions"], cone_bits | 4)
                self.assertEqual(when, original)
                for enabled in (False, True):
                    when["vision"]["sameTileAwareness"] = enabled
                    lowered = viewer._normalize_v5_condition_when(when, "test")
                    self.assertEqual(lowered["visionOptions"], cone_bits | 4 | (8 if enabled else 0))
                    viewer._validate_catalog_condition_when(lowered, "test")
                for invalid in (0, 1, "true", None):
                    when["vision"]["sameTileAwareness"] = invalid
                    with self.assertRaisesRegex(viewer.ParseError, "sameTileAwareness"):
                        viewer._normalize_v5_condition_when(when, "test")
                lowered["visionOptions"] = 16
                with self.assertRaisesRegex(viewer.ParseError, "visionOptions"):
                    viewer._validate_catalog_condition_when(lowered, "test")

        catalog = json.loads((REPO / "data/overworld_behavior_profiles.json").read_text())
        original = copy.deepcopy(catalog)
        self.assertEqual(viewer.migrate_behavior_catalog_v4_to_v5(catalog), catalog)
        self.assertEqual(catalog, original)
        for kind, options in ((kind, options)
                              for kind in ("notice-target", "notice-player", "target-cannot-see-subject")
                              for options in (5, 13)):
            legacy = viewer._normalize_behavior_catalog_v5(catalog)
            # V4 grouped Follower with Mounted, before V5 gave it an early
            # classification. Keep that historical order in the import fixture.
            follower = next(application for application in legacy["applications"]
                            if application["id"] == legacy["runtimeBindings"]["followerApplication"])
            legacy["applications"].remove(follower)
            mounted_index = next(index for index, application in enumerate(legacy["applications"])
                                 if application["id"] == legacy["runtimeBindings"]["mountedApplication"])
            legacy["applications"].insert(mounted_index, follower)
            when = next(profile for profile in legacy["profiles"] if profile["id"] == "playful")["conditions"][0]["when"]
            # This fixture tests legacy Vision, not the current bound-distance
            # predicate. Replace its fields as well as its kind.
            when.clear()
            when.update({"kind": kind, "rangeKind": "OW_WILD_BEHAVIOR_CONDITION_RANGE_VISION_CUSTOM", "rangeLength": 1,
                         "visionOptions": options, "chancePercent": 100})
            if kind == "target-cannot-see-subject":
                when.pop("facts", None)
            else:
                when["facts"] = {"all": [], "none": ["held"]}
            original = copy.deepcopy(legacy)
            migrated = viewer.migrate_behavior_catalog_v4_to_v5(legacy)
            migrated_when = next(profile for profile in migrated["profiles"] if profile["id"] == "playful")["conditions"][0]["when"]
            self.assertEqual(migrated_when["vision"].get("sameTileAwareness", False), bool(options & 8))
            self.assertEqual("sameTileAwareness" in migrated_when["vision"], bool(options & 8))
            self.assertEqual(viewer._normalize_v5_condition_when(migrated_when, "test"), when)
            self.assertEqual(legacy, original)

    def test_same_tile_vision_ui_default_copy_validation_and_checkbox(self) -> None:
        with tempfile.TemporaryDirectory(prefix="workshop-same-tile-") as raw_temp:
            temp = Path(raw_temp)
            module = temp / "profiles.mjs"
            module.write_text((STATIC / "profiles.js").read_text() + "\nexport { conditionVisionHasSameTileAwareness, setConditionVisionAwareness };\n")
            script = temp / "test.mjs"
            script.write_text(f"""
import assert from 'node:assert/strict';
import {{ canonicalCatalogStructuralErrors, conditionVisionHasSameTileAwareness,
  setConditionVisionAwareness, setConditionVisionMode }} from {json.dumps(module.as_uri())};
const catalog = {{ catalogVersion: 5, rootProfile: 'root', pools: [], selectors: [],
  profiles: [{{ id: 'root', name: 'Root', kind: 'normal', parent: null, fields: {{}} }},
    {{ id: 'watcher', name: 'Watcher', kind: 'conditional', parent: 'root', classification: 'capability',
      fields: {{}}, conditions: [{{ id: 'watch', subjects: {{ mode: 'all', match: {{}}, members: [] }},
        when: {{ kind: 'notice-target', vision: {{ mode: 'current' }}, chancePercent: 100 }},
        activation: {{ mode: 'while-true' }}, target: {{ kind: 'player' }} }}] }}],
  applications: [{{ id: 'apply-watcher', profile: 'watcher' }}], runtimeBindings: {{}} }};
const original = JSON.stringify(catalog);
const custom = setConditionVisionMode(catalog, 'apply-watcher', 'watch', 'custom');
assert.equal(JSON.stringify(catalog), original);
const rule = custom.profiles[1].conditions[0];
assert.equal(conditionVisionHasSameTileAwareness(rule, 5), false);
assert.equal(Object.hasOwn(rule.when.vision, 'sameTileAwareness'), false);
const visionErrors = (value) => canonicalCatalogStructuralErrors(value).filter(error => /Vision/.test(error));
assert.deepEqual(visionErrors(custom), []);
setConditionVisionAwareness(rule, 'sameTileAwareness', true, 5);
assert.equal(conditionVisionHasSameTileAwareness(rule, 5), true);
setConditionVisionAwareness(rule, 'adjacentAwareness', false, 5);
assert.equal(rule.when.vision.sameTileAwareness, true);
assert.deepEqual(visionErrors(custom), []);
const copied = setConditionVisionMode(custom, 'apply-watcher', 'watch', 'custom');
assert.equal(copied.profiles[1].conditions[0].when.vision.sameTileAwareness, true);
setConditionVisionAwareness(rule, 'sameTileAwareness', false, 5);
assert.equal(rule.when.vision.adjacentAwareness, false);
assert.equal(conditionVisionHasSameTileAwareness(rule, 5), false);
assert.equal(setConditionVisionMode(custom, 'apply-watcher', 'watch', 'custom')
  .profiles[1].conditions[0].when.vision.sameTileAwareness, false);
for (const invalid of [0, 1, 'true', null]) {{
  rule.when.vision.sameTileAwareness = invalid;
  assert.ok(visionErrors(custom).some(error => /invalid custom Vision/.test(error)));
}}
const current = setConditionVisionMode(custom, 'apply-watcher', 'watch', 'current');
assert.deepEqual(current.profiles[1].conditions[0].when.vision, {{ mode: 'current' }});
assert.throws(() => setConditionVisionAwareness(current.profiles[1].conditions[0], 'sameTileAwareness', true, 5), /Custom Vision/);
const legacy = JSON.parse(original);
legacy.catalogVersion = 4;
const legacyRule = legacy.profiles[1].conditions[0];
legacyRule.when = {{ kind: 'notice-target', rangeKind: 6, rangeLength: 1, visionOptions: 7, chancePercent: 100 }};
setConditionVisionAwareness(legacyRule, 'sameTileAwareness', true, 4);
assert.equal(legacyRule.when.visionOptions, 15);
assert.deepEqual(visionErrors(legacy), []);
assert.equal(conditionVisionHasSameTileAwareness(legacyRule, 4), true);
setConditionVisionAwareness(legacyRule, 'adjacentAwareness', false, 4);
assert.equal(legacyRule.when.visionOptions, 11);
setConditionVisionAwareness(legacyRule, 'sameTileAwareness', false, 4);
assert.equal(legacyRule.when.visionOptions, 3);
legacyRule.when.visionOptions = 16;
assert.ok(visionErrors(legacy).some(error => /custom Vision options/.test(error)));
""")
            completed = subprocess.run(["node", script], cwd=REPO, check=False, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)


if __name__ == "__main__":
    unittest.main()
