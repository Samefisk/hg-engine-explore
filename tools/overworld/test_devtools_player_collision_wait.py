"""Pure collision-policy tests over native player snapshot layouts."""
from copy import deepcopy
import unittest

from tools.overworld.devtools_player_collision_wait import PlayerCollisionWait


def sample(frame=10, mask=2):
    player = dict(x=585,y=406,x_prev=585,y_prev=406,pos_x=585*65536+32768,
                  pos_z=406*65536+32768,pos_y=65536,flags=0x11,facing=0,movement_cmd=28,movement_step=1)
    context = dict(mapId=33,fieldEpoch=2,mapGeneration=2)
    snapshot = dict(frame=frame,nativeCycle=frame*2,fieldAvailable=True,
        observationBoundary="main-task-queue-completion",context=context,player=player,
        selector={"heldKeys":64},actors=[{"active":True,"role":"FOLLOWER"}])
    step = dict(origin=[585,406],target=[585,405],start=[player["pos_x"],player["pos_z"]],
        targetRender=[player["pos_x"],405*65536+32768],keys=["UP"],startMap=33,startFrame=10,
        initialHeight=65536,inputContext=deepcopy(context),accepted=False)
    receipt = dict(objectPointer=0x022B302C,direction=0,origin=step["origin"],target=step["target"],
        collisionMask=mask,context={**context,"fieldPointer":0x022B0000,"statePointer":0x023D0000},
        frame=frame,nativeCycle=frame*2,returnNativeCycle=frame*2,
        objectBefore=deepcopy(player),objectAfter=deepcopy(player))
    return snapshot,step,receipt


class PlayerCollisionWaitTests(unittest.TestCase):
    def test_exact_block_then_clear_excludes_only_wait_and_does_not_mutate_input(self):
        meter = PlayerCollisionWait()
        s,step,r = sample(); before=deepcopy((s,step,r))
        self.assertTrue(meter.observe(s,step,[r]))
        self.assertFalse(meter.ready)
        self.assertEqual((s,step,r),before)
        for frame in range(11,14):
            s,step,_=sample(frame); self.assertTrue(meter.observe(s,step,[]))
        s,step,r=sample(14,0)
        self.assertFalse(meter.observe(s,step,[r]))
        self.assertTrue(meter.ready)
        self.assertEqual(meter.proofs[0]["waitingFrames"],4)
        self.assertEqual(meter.proofs[0]["endFrame"],14)
        self.assertFalse(step["accepted"])

    def test_clear_and_real_admission_same_frame(self):
        meter=PlayerCollisionWait();s,step,r=sample();meter.observe(s,step,[r])
        s,step,r=sample(11,0)
        s["player"].update(y=405,pos_z=s["player"]["pos_z"]-8192)
        self.assertFalse(meter.observe(s,step,[r],admitted=True))
        self.assertTrue(meter.ready)

    def test_missing_receipt_outside_wait_does_not_suspend_watchdog(self):
        meter=PlayerCollisionWait();s,step,_=sample()
        self.assertFalse(meter.observe(s,step,[]))
        self.assertEqual(meter.proofs,[])

    def test_stock_bump_gap_eighteen_is_allowed_nineteen_is_latched_failure(self):
        meter=PlayerCollisionWait();s,step,r=sample();meter.observe(s,step,[r])
        for frame in range(11,29):
            s,step,_=sample(frame);self.assertTrue(meter.observe(s,step,[]))
        s,step,r=sample(29)
        with self.assertRaisesRegex(ValueError,"eighteen frames"):meter.observe(s,step,[])
        with self.assertRaises(ValueError):meter.observe(s,step,[r])
        self.assertFalse(meter.ready)

    def test_120_frames_limit_is_not_healed_by_fresh_receipts(self):
        meter=PlayerCollisionWait()
        for frame in range(10,130):
            s,step,r=sample(frame);self.assertTrue(meter.observe(s,step,[r]))
        s,step,r=sample(130)
        with self.assertRaisesRegex(ValueError,"120 frames"):meter.observe(s,step,[r])

    def test_clear_after_exact_120_waiting_frames_is_valid(self):
        meter=PlayerCollisionWait()
        for frame in range(10,130):
            s,step,r=sample(frame);meter.observe(s,step,[r])
        s,step,r=sample(130,0)
        self.assertFalse(meter.observe(s,step,[r]))
        self.assertEqual(meter.proofs[0]["waitingFrames"],120)

    def test_wrong_evidence_cannot_start_wait(self):
        mutations = {
            "mask":lambda s,t,r:r.__setitem__("collisionMask",1),
            "combined-mask":lambda s,t,r:r.__setitem__("collisionMask",3),
            "bool-mask":lambda s,t,r:r.__setitem__("collisionMask",True),
            "stale":lambda s,t,r:r.__setitem__("frame",9),
            "future-cycle":lambda s,t,r:r.__setitem__("nativeCycle",21),
            "null":lambda s,t,r:r.__setitem__("objectPointer",0),
            "alignment":lambda s,t,r:r.__setitem__("objectPointer",0x022B302D),
            "direction":lambda s,t,r:r.__setitem__("direction",1),
            "target":lambda s,t,r:r.__setitem__("target",[585,407]),
            "context":lambda s,t,r:r["context"].__setitem__("fieldEpoch",3),
            "receipt-pose":lambda s,t,r:r["objectAfter"].__setitem__("pos_x",1),
            "player-pose":lambda s,t,r:s["player"].__setitem__("pos_x",1),
            "tile":lambda s,t,r:s["player"].__setitem__("x",584),
            "height":lambda s,t,r:s["player"].__setitem__("pos_y",0),
            "inactive":lambda s,t,r:s["player"].__setitem__("flags",0),
            "disabled":lambda s,t,r:s["player"].__setitem__("flags",3),
            "input":lambda s,t,r:s["selector"].__setitem__("heldKeys",0),
            "mounted":lambda s,t,r:s["actors"][0].__setitem__("role","MOUNTED"),
            "missing-field":lambda s,t,r:s.__setitem__("fieldAvailable",False),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                s,t,r=sample();mutate(s,t,r)
                with self.assertRaises(ValueError):PlayerCollisionWait().observe(s,t,[r])

    def test_active_wait_preserves_owner_request_and_dense_frames(self):
        for fault in ("pointer","skip","context","step","admitted","duplicate"):
            with self.subTest(fault=fault):
                meter=PlayerCollisionWait();s,t,r=sample();meter.observe(s,t,[r])
                s,t,r=sample(12 if fault=="skip" else 11)
                if fault=="pointer":r["objectPointer"]+=4
                if fault=="context":s["context"]["fieldEpoch"]+=1
                if fault=="step":t["startFrame"]+=1
                with self.assertRaises(ValueError):
                    meter.observe(s,t,[r,r] if fault=="duplicate" else [r],admitted=fault=="admitted")

    def test_native_read_can_precede_completed_boundary_in_same_frame(self):
        meter=PlayerCollisionWait();s,t,r=sample();r.update(nativeCycle=19,returnNativeCycle=19)
        self.assertTrue(meter.observe(s,t,[r]))
        s,t,r=sample(11);r.update(nativeCycle=20,returnNativeCycle=20)
        self.assertTrue(meter.observe(s,t,[r]))


if __name__=="__main__":unittest.main()
