"""Focused UI-only checks for the PB6 Workshop profile editor."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
STATIC = REPO / "tools/overworld-viewer-v2/static"


class WorkshopProfileBuildingBlocksTests(unittest.TestCase):
    def test_movement_groups_preserve_partial_inactive_and_future_fields(self) -> None:
        with tempfile.TemporaryDirectory(prefix="workshop-movement-groups-") as raw_temp:
            temp = Path(raw_temp)
            module = temp / "profiles.mjs"
            shutil.copyfile(STATIC / "profiles.js", module)
            script = temp / "test.mjs"
            script.write_text(f"""
import assert from 'node:assert/strict';
import {{ movementEditorGroups }} from {json.dumps(module.as_uri())};
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
            "routine", "placement", "capability", "attitude", "style",
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
        self.assertIn('condition.when.vision.adjacentAwareness = event.target.checked', source)
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

const classifications = ['routine', 'placement', 'capability', 'attitude', 'style', 'follower-mount', 'modifier'];
const profiles = classifications.flatMap((classification, index) => [
  {{ id: `${{classification}}-a`, classification }},
  ...(index === 0 ? [{{ id: `${{classification}}-b`, classification }}] : []),
]);
const sourceOrder = [
  'modifier-a', 'routine-b', 'style-a', 'placement-a', 'routine-a',
  'follower-mount-a', 'attitude-a', 'capability-a',
];
const sorted = sortProfileApplicationsByClassification({{
  profiles,
  applications: sourceOrder.map((profile) => ({{ id: `apply-${{profile}}`, profile }})),
}});
assert.deepEqual(sorted.applications.map((item) => item.profile), [
  'routine-b', 'routine-a', 'placement-a', 'capability-a', 'attitude-a',
  'style-a', 'follower-mount-a', 'modifier-a',
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


if __name__ == "__main__":
    unittest.main()
