"""The real old native plan is red; independently legal shorter choices pass."""
from pathlib import Path
import importlib.util,json,gzip,sys,unittest
from copy import deepcopy
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'TICKETS.md').is_file())
sys.path.insert(0,str(ROOT))
import tools.overworld
from tools.overworld.devtools_mounted_hop_clearance_measurement import legal_plan,MountedHopClearanceMeasurement,TOP,GROUND,KIND
from tools.overworld.devtools_mounted_hop_clearance_proof import MountedHopClearanceNegative,validate_negative_result,FAULTS
from tools.overworld.devtools_walk_matrix_observer import decode_motion
F=Path(__file__).resolve().parent/'fixtures/mounted_hop_clearance_3709.json'
FIXTURE=json.loads(F.read_text())

def retained():
 s=deepcopy(FIXTURE['firstHop']);a=s['actors'][0];m=s['pokemonCombat']['targets'][0]['motion']
 return s,a,m,None

class ClearanceChecks(unittest.TestCase):
 def test_actual_3709_six_tile_native_underpass_rejects(self):
  sample,actor,motion,record=retained()
  self.assertEqual(motion,decode_motion(bytes.fromhex(motion['rawHex'])))
  self.assertEqual((motion['plan']['target'],motion['plan']['arcHeightQ4']),([564,375],16))
  with self.assertRaisesRegex(ValueError,'underpasses the crossed native canopy'):legal_plan(motion['plan'])
 def test_legal_shorter_plan_does_not_require_old_far_endpoint(self):
  _,_,motion,_=retained()
  for d in range(1,5):
   plan=deepcopy(motion['plan']);height=TOP if d==4 else GROUND;e=abs(height-GROUND)>>12
   plan.update(target=[558+d,375],distance=d,targetBaseY=height,duration=7+(d-1)*6+(e*7*30)//1600,arcHeightQ4=16+(e*150)//200)
   self.assertEqual(legal_plan(plan)['target'],[558+d,375])
 def test_jump_off_refuses_an_extra_obstacle_arc_and_jump_on_can_clear(self):
  _,_,motion,_=retained();plan=deepcopy(motion['plan']);plan['arcHeightQ4']=255
  with self.assertRaisesRegex(ValueError,'Jump-off'):legal_plan(plan)
  self.assertTrue(legal_plan(plan,True)['checks'])
 def test_wrong_endpoint_support_and_wrong_plan_direction_reject(self):
  _,_,motion,_=retained()
  for field,value,reason in [('targetBaseY',TOP,'support height'),('direction',2,'RIGHT Hop')]:
   plan=deepcopy(motion['plan']);plan[field]=value
   with self.subTest(field=field),self.assertRaisesRegex(ValueError,reason):legal_plan(plan)
 def test_actual_loaded_canopy_arm_and_wrong_support_control(self):
  sample=deepcopy(FIXTURE['baseline']);actor=sample['actors'][0]
  meter=MountedHopClearanceMeasurement(dict(romSha256=sample['romSha256']));meter.arm(sample,actor)
  row=dict(phase='setup',command='bind',snapshot=sample);n=MountedHopClearanceNegative('wrong-support');changed=n.mutate(row,{})
  self.assertTrue(n.applied)
  with self.assertRaisesRegex(ValueError,'canopy footprint/support'):MountedHopClearanceMeasurement(meter.source).arm(changed['snapshot'],actor)
 def test_real_native_pose_and_bytes_are_required(self):
  sample,actor,motion,_=retained();source=dict(romSha256=sample['romSha256'],overlaySha256=sample['pokemonCombat']['identity']['overlaySha256'])
  meter=MountedHopClearanceMeasurement(source);self.assertEqual(meter._native(sample,actor),motion)
  for bad in ('bytes','owner','cycle'):
   s=deepcopy(sample);m=next(t for t in s['pokemonCombat']['targets'] if t['handle']==actor['handle'])
   if bad=='bytes':m['motion']['plan']['arcHeightQ4']+=1
   elif bad=='owner':m['personality']+=1
   else:s['pokemonCombat']['nativeCycle']+=1
   with self.subTest(bad=bad),self.assertRaises(ValueError):meter._native(s,actor)
 def test_positive_proof_cannot_come_from_an_incomplete_baseline(self):
  sample,actor,_,_=retained();m=MountedHopClearanceMeasurement(dict(romSha256=sample['romSha256']))
  self.assertFalse(m.finish()['passed'])
  for fault in FAULTS:
   with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'exact fault'):validate_negative_result(dict(passed=False,failures=['unrelated']),fault)
 def test_unsafe_copy_is_native_coherent_and_fails_the_actual_safety_oracle(self):
  sample,actor,_,_=retained();n=MountedHopClearanceNegative('unsafe-plan');r=n.mutate(dict(phase='observe',samples=[sample]),{})
  self.assertTrue(n.applied);motion=next(t['motion'] for t in r['samples'][0]['pokemonCombat']['targets'] if t['handle']==actor['handle'])
  self.assertEqual(motion,decode_motion(bytes.fromhex(motion['rawHex'])))
  with self.assertRaisesRegex(ValueError,'underpasses the crossed native canopy'):legal_plan(motion['plan'])
 def test_actual_first_hop_is_red_through_native_identity_profile_and_pose_path(self):
  meter=MountedHopClearanceMeasurement(FIXTURE['source']);baseline=deepcopy(FIXTURE['baseline']);meter.arm(baseline,baseline['actors'][0])
  with self.assertRaisesRegex(ValueError,'underpasses the crossed native canopy'):meter._sample(deepcopy(FIXTURE['firstHop']),deepcopy(FIXTURE['startEvents']),deepcopy(FIXTURE['profileCache']))
if __name__=='__main__':unittest.main()
