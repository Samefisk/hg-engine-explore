"""Focused Workshop controls use the actual C condition and binding owners."""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'tools/overworld-viewer-v2'))
import reliability

spec = importlib.util.spec_from_file_location('binding_preview_viewer', REPO / 'scripts/overworld_behavior_profile_viewer.py')
VIEWER = importlib.util.module_from_spec(spec)
spec.loader.exec_module(VIEWER)

class WorkshopBindingTests(unittest.TestCase):
    def payload(self):
        catalog = json.loads((REPO / 'data/overworld_behavior_profiles.json').read_text())
        profile = next(p for p in catalog['profiles'] if p['id'] == 'playful')
        original = copy.deepcopy(next(p for p in catalog['profiles'] if p['id'] == 'find-playmate')['conditions'][0])
        original.pop('binding', None)
        next(a for a in catalog['applications'] if a['id'] == 'apply-find-playmate')['enabled'] = False
        trigger = copy.deepcopy(original)
        trigger.update(id='test-trigger', subjectRoles=['follower'], binding={
            'name': 'trigger', 'lifetime': 'frames', 'durationFrames': 1000,
            'contributeProfile': False})
        trigger['target'] = {'kind': 'actor', 'roles': ['wild'], 'selection': 'nearest',
            'groupMask': 'OW_WILD_BEHAVIOR_GROUP_NONE', 'members': ['SPECIES_CLEFABLE']}
        cargo = copy.deepcopy(original)
        cargo.update(id='test-cargo', subjectRoles=['follower'],
            when={'kind': 'actor-facts', 'facts': {'all': ['trigger-valid'], 'none': ['held']}},
            activation={'mode': 'while-true'}, usesBinding='trigger', binding={
                'name': 'cargo', 'lifetime': 'frames', 'durationFrames': 20,
                'contributeProfile': True}, failure={'response': 'drop-and-clear', 'retryFrames': 32})
        cargo['target'] = {'kind': 'actor', 'roles': ['wild'], 'selection': 'nearest',
            'groupMask': 'OW_WILD_BEHAVIOR_GROUP_NONE', 'members': ['SPECIES_CLEFABLE', 'SPECIES_PIDGEY'],
            'mustBeReachableForPickup': True, 'pickupReach': {'tiles': 1, 'heightUnits': 16}}
        use = copy.deepcopy(cargo)
        use.update(id='test-use-cargo', usesBinding='cargo')
        del use['binding']
        use['when']['facts']['all'] = ['reserved']
        profile['conditions'] = [trigger, cargo, use]
        return {'profileCatalog': {'catalog': catalog}, 'subject': {
            'species': 'SPECIES_CLEFAIRY', 'role': 'follower', 'level': 20,
            'terrain': 'OW_WILD_SPAWN_TERRAIN_LAND', 'shiny': False, 'behaviorClass': 'auto'},
            'observation': {'frame': 100, 'x': 10, 'y': 10, 'facing': 3,
                'terrainMask': 1, 'movementSpeed': 8, 'player': {'valid': False, 'x': 13, 'y': 10},
                'actorFacts': [], 'pickupEligible': ['trigger-a', 'cargo-b']},
            'candidates': [{'id': 'trigger-a', 'species': 'SPECIES_CLEFABLE', 'role': 'wild',
                'x': 11, 'y': 10}, {'id': 'cargo-b', 'species': 'SPECIES_PIDGEY', 'role': 'wild',
                'x': 30, 'y': 30}], 'conditionState': []}

    def preview(self, payload):
        return reliability.resolve_conditional_preview(VIEWER, payload)['conditionEvaluation']

    def advance(self, payload, evaluation, frame):
        payload['conditionState'] = evaluation['nextState']
        payload['bindings'] = evaluation['bindings']
        payload['bindingOwner'] = evaluation['bindingOwner']
        payload['observation']['frame'] = frame

    def test_exact_capture_separate_cargo_movement_and_expiry(self):
        payload = self.payload()
        first = self.preview(payload)
        self.assertEqual(first['bindings']['trigger']['target']['candidateId'], 'trigger-a')
        self.assertEqual(first['bindings']['trigger']['source']['conditionId'], 'test-trigger')
        self.assertFalse(first['bindings']['cargo']['bound'])
        self.advance(payload, first, 101)
        payload['observation']['actorFacts'] = ['trigger-valid']
        second = self.preview(payload)
        self.assertEqual(second['bindings']['cargo']['target']['candidateId'], 'cargo-b')
        self.assertEqual(second['bindings']['trigger']['target'], first['bindings']['trigger']['target'])
        self.advance(payload, second, 102)
        payload['candidates'][1].update(x=50, y=50)
        payload['observation']['actorFacts'] = ['trigger-valid', 'reserved']
        third = self.preview(payload)
        cargo_entry = next(e for e in third['entries'] if e['conditionId'] == 'test-cargo')
        self.assertTrue(cargo_entry['active'])
        self.assertEqual(third['bindings']['cargo']['target'], second['bindings']['cargo']['target'])
        self.advance(payload, third, 122)
        expired = self.preview(payload)
        self.assertEqual(expired['bindings']['cargo']['reason'], 7)
        self.assertTrue(expired['bindings']['cargo']['bound'])
        self.assertFalse(next(e for e in expired['entries'] if e['conditionId'] == 'test-use-cargo')['active'])

    def test_lost_trigger_keeps_identity_and_never_binds_replacement(self):
        payload = self.payload()
        first = self.preview(payload)
        self.advance(payload, first, 101)
        payload['candidates'][0]['handle'] = {'slot': 1, 'generation': 2,
            'fieldEpoch': 1, 'mapGeneration': 1, 'encounterGeneration': 1}
        payload['observation']['actorFacts'] = ['trigger-valid']
        lost = self.preview(payload)
        self.assertEqual(lost['bindings']['trigger']['reason'], 6)
        self.assertEqual(lost['bindings']['trigger']['target']['handle']['generation'], 1)
        self.assertFalse(lost['bindings']['cargo']['bound'])
        payload['subject']['handle'] = {**first['bindingOwner'], 'generation': 2}
        stale_owner = self.preview(payload)
        self.assertEqual(stale_owner['bindings']['trigger']['reason'], 5)
        self.assertEqual(stale_owner['bindingOwner'], first['bindingOwner'])
        self.assertFalse(stale_owner['bindings']['cargo']['bound'])

    def test_subject_role_gate_and_follower_profile_are_native(self):
        payload = self.payload()
        payload['subject']['role'] = 'wild'
        wild = self.preview(payload)
        self.assertFalse(wild['bindings']['trigger']['bound'])
        payload['subject']['role'] = 'follower'
        result = reliability.resolve_conditional_preview(VIEWER, payload)
        self.assertTrue(result['conditionEvaluation']['bindings']['trigger']['bound'])
        self.assertIn('apply-follower', result['appliedApplicationIds'])

    def test_damage_event_and_exact_interest_authoring(self):
        catalog = self.payload()['profileCatalog']['catalog']
        VIEWER.validate_behavior_catalog(catalog)
        normalized = VIEWER._normalize_behavior_catalog_v5(catalog)
        pickup = next(p for p in normalized['profiles'] if p['id'] == 'throw')
        conditions = {c['id']: c for c in pickup['conditions']}
        exact = conditions['condition-throw-picks-up-object-of-interest']
        wild = conditions['condition-throw-selects-cargo']
        self.assertEqual(VIEWER._catalog_condition_options(exact, 'exact')[5], 3)
        self.assertEqual(VIEWER._catalog_condition_options(wild, 'wild')[5], 1)
        self.assertEqual(wild['subjectRoles'], ['wild'])
        self.assertEqual(exact['subjectRoles'], ['follower'])
        damage = conditions['condition-throw-player-damaged']
        self.assertEqual(damage['when']['kind'], 'player-damaged')
        self.assertNotIn('vision', damage['when'])
        self.assertTrue(damage['binding']['contributeProfile'])
        self.assertEqual(conditions['condition-throw-search-pending']['target'], {'kind': 'none'})
        self.assertEqual(conditions['condition-throw-search-pending']['usesBinding'], 'trigger')
        for bad in ('wrong-capture', 'wrong-target', 'vision', 'player', 'timed'):
            with self.subTest(bad=bad):
                candidate = copy.deepcopy(catalog)
                profile = next(p for p in candidate['profiles'] if p['id'] == 'throw')
                entries = {c['id']: c for c in profile['conditions']}
                exact = entries['condition-throw-picks-up-object-of-interest']
                damage = entries['condition-throw-player-damaged']
                if bad == 'wrong-capture': exact['binding']['name'] = 'trigger'
                elif bad == 'wrong-target': exact['target'] = {'kind': 'none'}
                elif bad == 'vision': damage['when']['vision'] = {'mode': 'current'}
                elif bad == 'player': damage['target'] = {'kind': 'player'}
                else: damage['activation'] = {'mode': 'timed', 'durationFrames': 10, 'cooldownFrames': 20}
                with self.assertRaises(VIEWER.ParseError):
                    VIEWER.validate_behavior_catalog(candidate)

    def test_ui_fields_keep_metadata_and_reject_non_bool(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node is required for the existing Workshop module check')
        with tempfile.TemporaryDirectory() as directory:
            module = Path(directory) / 'profiles.mjs'
            module.write_bytes((REPO / 'tools/overworld-viewer-v2/static/profiles.js').read_bytes())
            script = """
import assert from 'node:assert/strict';
import {setAdvancedConditionField as set, canonicalCatalogStructuralErrors as errors, renderConditionBindingSummary as bindingSummary, sortProfileApplicationsByClassification as sortApps} from MODULE;
const catalog=CATALOG;
const p=catalog.profiles.find(p=>p.id==='playful');
const c=p.conditions[0];
c.when={kind:'actor-facts',facts:{all:['trigger-valid'],none:[]}};
c.activation={mode:'while-true'};
c.target={kind:'actor',roles:['wild'],selection:'nearest',groupMask:'OW_WILD_BEHAVIOR_GROUP_NONE',members:['SPECIES_PIDGEY']};
c.subjectRoles=['follower'];
set(c,'binding.name','cargo'); set(c,'binding.lifetime','frames');
set(c,'binding.durationFrames',20); set(c,'binding.contributeProfile',false);
set(c,'usesBinding','trigger'); set(c,'target.mustBeReachableForPickup',true);
set(c,'target.pickupReach.tiles',2); set(c,'target.pickupReach.heightUnits',24);
set(c,'failure.response','drop-and-clear'); set(c,'failure.retryFrames',32);
const fields=Object.keys(catalog.profiles.find(p=>p.id===catalog.rootProfile).fields);
const input={fields:fields.map(key=>({key})),numericOverrideOperatorFieldKeys:fields,boundedOverrideOperatorFieldKeys:fields};
assert.deepEqual(errors(catalog,input),[]);
set(c,'usesBinding','object-of-interest-itself');
assert.equal(c.usesBinding,'object-of-interest-itself');
assert.deepEqual(errors(catalog,input),[]);
const exact=JSON.parse(JSON.stringify(c)); exact.binding.name='trigger';
assert.ok(errors({...catalog,profiles:catalog.profiles.map(p=>p.id==='playful'?{...p,conditions:[exact]}:p)},input).some(e=>e.includes('must capture Cargo')));
assert.throws(()=>set(exact,'usesBinding','object-of-interest-itself'));
c.when={kind:'player-damaged'}; assert.deepEqual(errors(catalog,input),[]);
c.when.vision={mode:'current'}; assert.ok(errors(catalog,input).some(e=>e.includes('no Vision'))); delete c.when.vision;
c.target.kind='player'; assert.ok(errors(catalog,input).some(e=>e.includes('player-damaged actor event'))); c.target.kind='actor';
c.activation={mode:'timed',durationFrames:10,cooldownFrames:20}; assert.ok(errors(catalog,input).some(e=>e.includes('player-damaged actor event'))); c.activation={mode:'while-true'};
c.when={kind:'actor-facts',facts:{all:['trigger-valid'],none:[]}};set(c,'usesBinding','trigger');
c.binding.contributeProfile='false'; assert.ok(errors(catalog,input).some(e=>e.includes('binding settings'))); c.binding.contributeProfile=false;
assert.equal(c.binding.contributeProfile,false); assert.equal(c.target.pickupReach.heightUnits,24);
const copy=JSON.parse(JSON.stringify(c)); set(copy,'failure.retryFrames',33);
assert.deepEqual(copy.binding,c.binding); assert.equal(copy.usesBinding,'trigger');
assert.throws(()=>set(c,'binding.contributeProfile','false'));
assert.throws(()=>set(c,'target.mustBeReachableForPickup',1));
set(c,'binding.lifetime','until-clear'); assert.equal('durationFrames' in c.binding,false);
set(c,'binding.name',''); assert.equal('binding' in c,false);
assert.equal(c.failure.retryFrames,32); assert.equal(c.target.pickupReach.tiles,2);
assert.equal(bindingSummary(null),'');
const html=bindingSummary({trigger:{bound:true,reason:6,target:{kind:'actor',candidateId:'<old>'},source:{conditionId:'capture'}},cargo:{bound:false,reason:1}});
assert.ok(html.startsWith('<section><h3>Saved target bindings</h3>'));
assert.ok(html.includes('&lt;old&gt;')); assert.ok(html.includes('target lost'));
assert.ok(html.includes('<dt>Cargo</dt><dd>Empty</dd>'));
const order=['routine','style','placement','follower','capability','attitude','follower-mount','modifier'];
const shuffled={profiles:order.map(id=>({id,classification:id})),applications:[...order].reverse().map(id=>({id,profile:id}))};
assert.deepEqual(sortApps(shuffled).applications.map(a=>a.id),order);


""".replace('MODULE', json.dumps(module.as_uri())).replace('CATALOG', json.dumps(self.payload()['profileCatalog']['catalog']))
            completed = subprocess.run([node, '--input-type=module', '-e', script], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)

if __name__ == '__main__':
    unittest.main()
