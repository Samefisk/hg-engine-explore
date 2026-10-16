"""Copied native shapes check the narrow competition proof, not game behavior."""
from copy import deepcopy
import json,struct,unittest
from pathlib import Path
from tools.overworld.devtools_throw_cargo_competition_measurement import (
    ThrowCargoCompetitionMeasurement,validate_recipe,KIND,CASE,SETUP,ACTIONS,
)
from tools.overworld.devtools_throw_cargo_competition_proof import FAULTS,ThrowCargoCompetitionNegative,contract
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_wild_throw_moving_candidate_measurement import (
    TRIGGER_CONDITION,CARGO_CONDITION,THROW_APPLICATION,THROW_APPLICATION_BIT,THROW_RELEASE_BIT,
)
from tools.overworld.test_devtools_player_health_throw_contact_measurement import actor,snapshot,step_row,ROM,OVERLAY
from tools.overworld.test_devtools_wild_throw_moving_candidate_measurement import native_motion
from tools.overworld.test_devtools_cargo_route_continuity import query_event,IMAGE

ROOT=Path(__file__).resolve().parents[2]
SOURCE=dict(contractVersion=2,romSha256=ROM,overlaySha256=OVERLAY,profileSha256='c'*64,queryImage=IMAGE)


def binding(kind=None,target=None):
    raw=(raw_handle(target) if target else bytes(12))+bytes([{'PLAYER':1,'ACTOR':2}.get(kind,0),0])+struct.pack(
        '<HIBBBB',TRIGGER_CONDITION if kind=='PLAYER' else CARGO_CONDITION if kind else 65535,
        0,THROW_APPLICATION if kind else 255,0,int(bool(kind)),0 if kind else 1)
    return dict(bound=bool(kind),targetCurrent=bool(kind),target=dict(kind=kind or 'NONE',actor=deepcopy(target)),
        sourceConditionId=TRIGGER_CONDITION if kind=='PLAYER' else CARGO_CONDITION if kind else 65535,
        expiresAt=0,sourceApplication=THROW_APPLICATION if kind else 255,lifetime=0,flags=int(bool(kind)),
        reason=0 if kind else 1,rawHex=raw.hex())


def sample(frame):
    s=snapshot(frame);s.update(actorFrame=frame);s['player'].update(x=584,y=402);s['fieldControl']['fieldPointer']=0x2200000
    cargo=actor(155,0,700,403);far=actor(74,1,740,403);near=actor(74,2,741,403)
    for a,x in ((cargo,586),(far,581 if frame<4 else 582),(near,585)):
        for k in ('logical','render','origin','target'):a[k]=dict(x=x,y=403)
        a['engineObject'].update(x=x,y=403,pos_x=(x<<16)+32768,pos_z=(403<<16)+32768)
        a['sourceIdentity']=dict(object=a['engineIdentity']['pointer'],personality=a['subjectIdentity'],map_id=33,species=a['species'],form=0,level=5,active=1,object_id=224+a['handle']['slot'],encounter_generation=1)
    far.update(motionKind='WALK',motionPhase='MOVING',motionDuration=8,motionElapsed=1,reservationId=8,target=dict(x=582 if frame<4 else 583,y=403))
    if frame==5:
        cargo.update(motionKind='HOP',motionPhase='MOVING',motionDuration=20,motionElapsed=0,reservationId=9,origin=dict(x=585,y=403),target=dict(x=584,y=402))
        near['matchedLayerMask']=THROW_RELEASE_BIT
    elif frame>=3:
        near['matchedLayerMask']=0
    s['actors']=[cargo,far,near];targets=[0]*10;targets[1]=1 if frame<3 else 0;targets[2]=129 if 3<=frame<5 else 0
    tm=1 if frame<5 else 0;cm=2 if frame<3 else 4 if frame<5 else 0
    state=dict(targets=targets,targetMask=tm,carrierMask=cm,recoveringMask=0,rawHex=(bytes(targets)+struct.pack('<3H',tm,cm,0)).hex())
    rows=[]
    for a in (far,near):
        encoded=targets[a['handle']['slot']]
        b=dict(trigger=binding('PLAYER') if encoded or a==near else binding(),cargo=binding('ACTOR',cargo['handle']) if encoded else binding())
        rows.append(dict(handle=deepcopy(a['handle']),role='WILD',available=True,bindings=b,
            rawBindingsHex=(raw_handle(a['handle'])+bytes.fromhex(b['trigger']['rawHex'])+bytes.fromhex(b['cargo']['rawHex'])).hex(),
            throw=dict(targetRaw=encoded,targetSlot=(encoded&63)-1 if encoded else None,carried=bool(encoded&128),windup=False,targeted=False,carrier=bool(encoded),recovering=False)))
    combat=dict(schemaVersion=1,available=True,frame=frame,nativeCycle=s['nativeCycle'],observationBoundary=s['observationBoundary'],fieldSystem=s['fieldControl']['fieldPointer'],identity=dict(romSha256=ROM,overlaySha256=OVERLAY),targets=[],movementTimers=[],interactions=dict(schemaVersion=1,available=True,frame=frame,nativeCycle=s['nativeCycle'],observationBoundary=s['observationBoundary'],fieldSystem=s['fieldControl']['fieldPointer'],identity=dict(romSha256=ROM),carriers=rows,throwState=state))
    for a in s['actors']:
        combat['targets'].append(dict(handle=deepcopy(a['handle']),role=a['role'],motion=native_motion(a)))
        combat['movementTimers'].append(dict(handle=deepcopy(a['handle']),slot=a['handle']['slot'],sourceIdentity=deepcopy(a['sourceIdentity']),movementActorControlMode=int(a==cargo and frame>=3)))
    s['pokemonCombat']=combat;return s


def meter():
    m=ThrowCargoCompetitionMeasurement(SOURCE);m.latest=sample(0)
    m.subjects={name:select_current_actor(m.latest,a) for name,a in zip(('cargo','far-geodude','near-geodude'),m.latest['actors'])}
    return m


def events(s):
    if s['frame']==2:return [query_event(s,s['actors'][2],IMAGE,status=1)]
    if s['frame']==5:
        a=s['actors'][0]
        return [dict(frame=5,kind='native',data=dict(event='MOTION_STARTED',valueA=2,valueB=20,actorHandle=a['handle']['value'],actor={k:v for k,v in a['handle'].items() if k!='value'},sequence=50,actorFrame=5))]
    return []


class CompetitionTests(unittest.TestCase):
    def test_same_species_bind_uses_the_exact_native_spawn_identity(self):
        from tools.overworld.devtools_test_contract import TestEvaluator, _handle
        value=json.loads((ROOT/'tests/overworld/test-recipes'/f'{CASE}.json').read_text())
        evaluator=TestEvaluator(value);s=sample(0)
        near=select_current_actor(s,s['actors'][2])
        evaluator.first_handles=set();evaluator.first_subjects=set()
        evaluator.spawn_setup=dict(subject=near)
        evaluator._prepared_attached.add(_handle(near['handle']))
        self.assertEqual(evaluator.bind('near-geodude',s),near)
        stale=deepcopy(s);stale['actors'][2]['handle']['generation']+=1
        with self.assertRaisesRegex(ValueError,'exactly one verified live actor'):
            evaluator.bind('near-geodude',stale)

    def test_natural_competition_held_launch_and_loser_progress(self):
        m=meter()
        for f in range(1,6):m._sample(sample(f),events(sample(f)))
        self.assertTrue(m.result()['ready']);self.assertEqual(m.result()['pickup']['frame'],3)
        self.assertEqual(m.result()['loserResumed']['frame'],4)

    def test_exact_recipe_and_registration(self):
        p=ROOT/'tests/overworld/test-recipes'/f'{CASE}.json';validate_recipe(json.loads(p.read_text()))
        from tools.overworld.proof_adapters import ADAPTERS
        self.assertEqual(ADAPTERS[KIND].recipe_subjects(),json.loads(p.read_text())['subjects'])
        r=json.loads((ROOT/'tools/overworld/runtime_proof_registry.json').read_text())
        self.assertEqual(r['sharedTests'][CASE]['measurementContract'],contract())
        import hashlib
        self.assertEqual(r['sharedTests'][CASE]['recipeSha256'],hashlib.sha256(p.read_bytes()).hexdigest())

    def test_copied_controls_reject_their_changed_native_fact(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                m=meter();negative=ThrowCargoCompetitionNegative(fault);failed=False
                for f in range(1,6):
                    s=sample(f);row=step_row(ACTIONS[0][0],[s]);row['events']=events(s)
                    altered=negative.mutate(row,m.subjects)
                    try:m._sample(altered['samples'][0],altered['events'])
                    except (ValueError,KeyError,StopIteration):failed=True;break
                self.assertTrue(negative.applied);self.assertTrue(failed)

    def test_held_far_owner_is_not_free_cargo(self):
        m=meter();s=sample(3)
        s['pokemonCombat']['interactions']['carriers'][1]['handle']=deepcopy(s['actors'][1]['handle'])
        with self.assertRaises(ValueError):m._sample(s)

    def test_no_near_query_does_not_earn_competition(self):
        m=meter();m._sample(sample(1));m._sample(sample(2));self.assertIsNone(m.competition)
        with self.assertRaisesRegex(ValueError,'farther carrier|competition'):m._sample(sample(3))

if __name__=='__main__':unittest.main()
