"""Real prepared query generator with host memory; no live selection proof."""
import json
import struct
import unittest
from unittest.mock import patch

from tools.overworld.devtools_mounted_hop_candidate_probe import (
    MountedHopCandidateProbe, candidate_order, authenticate, LANDING, SEARCH, STATE_ADDRESS)
from tools.overworld.test_devtools_mount_walk_fixture import session
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_runtime import _elf_code, _elf_function_extent

MODULE='tools.overworld.devtools_mounted_hop_candidate_probe'


def prepared():
    s=session();s.actor['species']=56
    s.put(STATE_ADDRESS+84,struct.pack('<H',56))
    s.pose.update(x=589,y=398,pos_x=(589<<16)+0x8000,pos_z=(398<<16)+0x8000)
    s.actor['engineObject'].update(s.pose)
    raw=bytearray(s.read(STATE_ADDRESS,184));raw[20]=2;raw[27]=1;raw[28]=1;raw[29]=3
    s.put(STATE_ADDRESS,raw)
    s.subject=select_current_actor(s._snapshot(),s.actor)
    return s


class CandidateProbeTests(unittest.TestCase):
    def guards(self):
        for name in ('tools.overworld.devtools_mount_walk_fixture.authenticate_mount', MODULE+'.authenticate_mount'):
            p=patch(name,return_value={'stateAddress':STATE_ADDRESS});p.start();self.addCleanup(p.stop)
        p=patch(MODULE+'.authenticate',return_value={'authenticated':True});p.start();self.addCleanup(p.stop)

    def start(self,s):
        p=MountedHopCandidateProbe(s,s.subject);s.native_bridge_active=True
        return p,p.recipe(s.native_trampoline['address']+0x200,lambda n,a:(n,a))

    def test_exact_real_query_order_and_allowed_lists(self):
        self.guards();s=prepared();p,g=self.start(s)
        expected=[(589,395),(589,396),(589,397),(590,395),(588,395),(590,396),(588,396),
                  (591,395),(587,395),(592,395),(586,395),(591,396),(587,396),(590,397),(588,397)]
        request=next(g)
        for i,target in enumerate(expected):
            self.assertEqual(request,('mount_hop_landing',target))
            answer=int(target in ((590,395),(592,395)))
            if i<len(expected)-1:request=g.send(answer)
            else:
                with self.assertRaises(StopIteration) as stop:g.send(answer)
        result=stop.exception.value
        self.assertEqual(result['orderedNearTargets'],[[590,395]])
        self.assertEqual(result['equalDiagonalTargets'],[[592,395]])
        self.assertEqual(result['before'],result['after']);self.assertFalse(s.writes)
        self.assertFalse(result['acceptedProof']);json.dumps(result)
        result['origin'][0]=0;self.assertEqual(p.origin,[589,398])
        with self.assertRaisesRegex(Exception,'single-use'):next(p.recipe(0,lambda *x:x))

    def test_changed_frame_policy_actor_input_and_mount_rejected(self):
        self.guards()
        for fault in ('frame','policy','actor','input','mount','return'):
            with self.subTest(fault=fault):
                s=prepared();p,g=self.start(s);next(g)
                if fault=='frame':s.completed_frames+=1
                elif fault=='policy':s.put(s.policy_address+1,b'\xff')
                elif fault=='actor':s.actor['authorityGeneration']+=1
                elif fault=='input':s.inputs['heldKeys']=1
                elif fault=='mount':s.put(STATE_ADDRESS+8,b'\xff')
                with self.assertRaises(Exception):g.send(2 if fault=='return' else 0)
                self.assertFalse(s.writes)

    def test_wrong_subject_and_profile_rejected(self):
        self.guards()
        for fault in ('species','locomotion','mode'):
            s=prepared()
            if fault=='species':s.actor['species']=155
            elif fault=='locomotion':s.put(STATE_ADDRESS+20,b'\x01')
            else:s.put(STATE_ADDRESS+27,b'\xff')
            with self.subTest(fault=fault),self.assertRaises(Exception):MountedHopCandidateProbe(s,s.subject)

    def test_profile_bounds_and_direction_filter(self):
        profile=bytearray(72);profile[19:22]=bytes((1,0,255))
        minimum,maximum,rows=candidate_order([100,100],profile)
        self.assertEqual((minimum,maximum),(1,16));self.assertLessEqual(len(rows),288)
        profile[19]=0;self.assertTrue(all(r['kind']=='straight' for r in candidate_order([100,100],profile)[2]))
        profile[19]=2;self.assertTrue(all(r['kind']!='straight' for r in candidate_order([100,100],profile)[2]))

    def test_full_current_landing_and_search_code_authentication(self):
        s=prepared();path=s.rt.REPO/'build/overworld_mount_overlay_linked.o';regions=[]
        s.rt.linked_symbol=lambda symbols,name:symbols[name]
        s.rt.MOUNT_SYMBOLS={'sOverworldMountState':STATE_ADDRESS}
        for name in (LANDING,SEARCH):
            address,size=_elf_function_extent(path,name);code=_elf_code(path,address,size)
            s.rt.MOUNT_SYMBOLS[name]=address;regions.append((address,code));s.put(address,code)
        s.target=lambda name:s.rt.MOUNT_SYMBOLS[LANDING]
        s.packaged_code=lambda address,size:next((b[address-a:address-a+size] for a,b in regions if a<=address and address+size<=a+len(b)),b'')
        proof=authenticate(s);self.assertIn(SEARCH,proof);self.assertIn(LANDING,proof)
        for name in (LANDING,SEARCH):
            address=s.rt.MOUNT_SYMBOLS[name];original=s.read(address,1);s.put(address,bytes([original[0]^255]))
            with self.assertRaisesRegex(Exception,'whole linked/package/live'):authenticate(s)
            s.put(address,original)
        s.target=lambda name:0
        with self.assertRaisesRegex(Exception,'target differs'):authenticate(s)


if __name__=='__main__':unittest.main()
