from copy import deepcopy
import unittest

from tools.overworld.devtools_crash_measurement import CrashPresentationMeasurement, BOUNDARY


def fixture():
    handle = dict(value=131079,slot=7,generation=2,encounterGeneration=2,fieldEpoch=2,mapGeneration=2)
    context = dict(mapId=33,fieldEpoch=2,mapGeneration=2)
    old = dict(handle=handle, species=155,role="FOLLOWER",subjectIdentity=2046726716,
        motionPhase="MOVING",motionKind="WALK",motionElapsed=1,motionDuration=2,
        commitSequence=16,origin=dict(x=583,y=397),target=dict(x=582,y=397),logical=dict(x=583,y=397),
        inputOwnership=1,reservationId=12,authorityGeneration=2,engineAnchorGeneration=2,presentationGeneration=2,
        engineObject=dict(x=583,y=397,pos_x=38207488,pos_z=26050560,pos_y=65536,unk88_y=0,flags=0x40001))
    def metadata(frame,timer):
        return dict(known=True,reason="observed",frame=frame,nativeCycle=frame*2,boundary=BOUNDARY,
                    timer=timer,baseX=38174720,baseZ=26050560,objectPointer=0x02040000,handle=deepcopy(handle))
    old["crashPresentation"] = metadata(847,0)
    rows=[]
    # Literal expected lifecycle, independent of production's offset table.
    for i,offset in enumerate((256,-512,512,-256,256,-512,512,-256,256,-512,0)):
        frame=848+i
        actor=deepcopy(old)
        actor.update(motionPhase="IDLE",motionKind="NONE",motionElapsed=2,commitSequence=17,
                     logical=dict(x=582,y=397),inputOwnership=0,reservationId=0)
        actor["engineObject"].update(x=582,pos_x=38174720+offset,pos_z=26050560-offset)
        actor["crashPresentation"]=metadata(frame,10-i)
        rows.append((dict(frame=frame,nativeCycle=frame*2,context=deepcopy(context)),actor))
    initial=dict(frame=847,nativeCycle=1694,context=context)
    return initial,old,rows


class CrashMeasurementTests(unittest.TestCase):
    def transition_fixture(self):
        meter, old, rows = self.prime()
        for snapshot, actor in rows[:6]:
            meter.observe(snapshot, actor, old); old = actor
        snapshot, actor = deepcopy(rows[6])
        snapshot["context"] = dict(mapId=67,fieldEpoch=3,mapGeneration=3)
        actor["handle"].update(fieldEpoch=3,mapGeneration=3)
        actor["crashPresentation"].update(timer=0,baseX=0,baseZ=0,handle=deepcopy(actor["handle"]))
        actor["engineObject"].update(pos_x=38174720,pos_z=26050560)
        transition = {}
        for key, name, reason, handle, a, b, sequence in (
            ("context","CONTEXT_CHANGED","CONTEXT_LOST",old["handle"],2,3,380),
            ("rebound","ACTOR_REBOUND","OK",actor["handle"],33,67,386)):
            transition[key] = dict(event=name,reason=reason,handle=deepcopy(handle),valueA=a,valueB=b,
                sequence=sequence,traceStream=1,actorFrame=424,frame=snapshot["frame"])
        return meter, old, snapshot, actor, transition

    def test_transition_restores_exact_base_without_fabricated_countdown(self):
        meter, old, snapshot, actor, transition = self.transition_fixture()
        saved = deepcopy((old,snapshot,actor,transition))
        self.assertEqual(meter.observe(snapshot,actor,old,transition=transition),actor["engineObject"])
        self.assertTrue(meter.ready)
        self.assertEqual(meter.proofs[0]["termination"],"transition-restored")
        self.assertEqual(len(meter.proofs[0]["samples"]),6)
        self.assertEqual(meter.proofs[0]["transitionRestoration"],
            dict(snapshot=snapshot,actor=actor,transition=transition))
        self.assertEqual((old,snapshot,actor,transition),saved)

    def test_transition_rejects_missing_stale_changed_or_unrestored_data(self):
        for fault in ("missing","old-frame","wrong-event","wrong-reason","wrong-handle","order","stream",
                      "actor-clock","pid","commit","pose","height","base","timer","pointer","previous","epoch"):
            meter, old, snapshot, actor, transition = self.transition_fixture()
            if fault=="missing": transition=None
            elif fault=="old-frame": transition["context"]["frame"]-=1
            elif fault=="wrong-event": transition["rebound"]["event"]="WORLD_EFFECT"
            elif fault=="wrong-reason": transition["context"]["reason"]="OK"
            elif fault=="wrong-handle": transition["rebound"]["handle"]["generation"]+=1
            elif fault=="order": transition["context"]["sequence"]=387
            elif fault=="stream": transition["context"]["traceStream"]=2
            elif fault=="actor-clock": transition["context"]["actorFrame"]-=1
            elif fault=="pid": actor["subjectIdentity"]+=1
            elif fault=="commit": actor["commitSequence"]+=1
            elif fault=="pose": actor["engineObject"]["pos_x"]+=1
            elif fault=="height": actor["engineObject"]["pos_y"]+=1
            elif fault=="base": actor["crashPresentation"]["baseX"]=38174720
            elif fault=="timer": actor["crashPresentation"]["timer"]=4
            elif fault=="pointer": actor["crashPresentation"]["objectPointer"]+=4
            elif fault=="previous": old["engineObject"]["pos_z"]+=1
            else: actor["handle"]["fieldEpoch"]=4
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                meter.observe(snapshot,actor,old,transition=transition)
            self.assertFalse(meter.ready)

    def prime(self):
        initial,old,rows=fixture(); meter=CrashPresentationMeasurement()
        meter.observe(initial,old,None)
        return meter,old,rows

    def test_exact_lifecycle_keeps_raw_samples_and_waits_for_restore(self):
        meter,old,rows=self.prime(); saved=deepcopy(rows)
        for i,(snapshot,actor) in enumerate(rows):
            engine=meter.observe(snapshot,actor,old)
            self.assertEqual((engine["pos_x"],engine["pos_z"]),(38174720,26050560))
            self.assertEqual(meter.ready,i==10)
            old=actor
        self.assertEqual(rows,saved)
        self.assertEqual(len(meter.proofs),1)
        self.assertEqual(len(meter.proofs[0]["samples"]),11)
        self.assertEqual(meter.proofs[0]["restoredFrame"],858)

    def test_blocked_idle_attempt_keeps_the_same_exact_crash_effect(self):
        initial,old,rows=fixture()
        old.update(motionPhase="IDLE",motionKind="NONE",motionElapsed=2,
                   commitSequence=17,logical=deepcopy(old["target"]),
                   inputOwnership=0,reservationId=0)
        old["engineObject"].update(x=582,pos_x=38174720,pos_z=26050560)
        meter=CrashPresentationMeasurement();meter.observe(initial,old,None)
        for snapshot,actor in rows:
            meter.observe(snapshot,actor,old);old=actor
        self.assertTrue(meter.ready)
        self.assertEqual(meter.proofs[0]["startBoundary"],"blocked-idle")
        self.assertEqual(len(meter.proofs[0]["samples"]),11)

    def test_timer_eleven_preroll_keeps_the_exact_base_before_the_effect(self):
        initial,old,rows=fixture()
        old.update(motionPhase="IDLE",motionKind="NONE",motionElapsed=2,
                   commitSequence=17,logical=deepcopy(old["target"]),
                   inputOwnership=0,reservationId=0)
        old["engineObject"].update(x=582,pos_x=38174720,pos_z=26050560)
        preroll=deepcopy(rows[0][1])
        preroll.update(motionPhase="IDLE",motionKind="NONE",motionElapsed=2,
                       commitSequence=17,logical=deepcopy(old["target"]),
                       inputOwnership=0,reservationId=0)
        preroll["engineObject"].update(x=582,pos_x=38174720,pos_z=26050560)
        preroll["crashPresentation"].update(timer=11,baseX=38174720,baseZ=26050560)
        shifted=[]
        for snapshot,actor in rows:
            snapshot=deepcopy(snapshot);actor=deepcopy(actor)
            snapshot["frame"]+=1;snapshot["nativeCycle"]+=2
            actor["crashPresentation"]["frame"]+=1
            actor["crashPresentation"]["nativeCycle"]+=2
            shifted.append((snapshot,actor))
        meter=CrashPresentationMeasurement();meter.observe(initial,old,None)
        meter.observe(rows[0][0],preroll,old)
        previous=preroll
        for snapshot,actor in shifted:
            meter.observe(snapshot,actor,previous);previous=actor
        self.assertTrue(meter.ready)
        self.assertEqual(meter.proofs[0]["preRollFrame"],848)
        self.assertEqual(len(meter.proofs[0]["samples"]),11)

    def test_start_rejects_wrong_metadata_terminal_base_and_identity(self):
        for fault in ("missing","unknown","frame","cycle","boundary","timer","base","pointer","handle",
                      "old-phase","kind","elapsed","commit","plan","height","context","generation"):
            with self.subTest(fault=fault):
                meter,old,rows=self.prime(); snapshot,actor=rows[0]; data=actor["crashPresentation"]
                if fault=="missing": del actor["crashPresentation"]
                elif fault=="unknown": data["known"]=False
                elif fault=="frame": data["frame"]-=1
                elif fault=="cycle": data["nativeCycle"]-=1
                elif fault=="boundary": data["boundary"]="other"
                elif fault=="timer": data["timer"]=11
                elif fault=="base": data["baseX"]+=1
                elif fault=="pointer": data["objectPointer"]+=4
                elif fault=="handle": data["handle"]["generation"]+=1
                elif fault=="old-phase": old["motionPhase"]="IDLE"
                elif fault=="kind": actor["motionKind"]="WALK"
                elif fault=="elapsed": actor["motionElapsed"]=1
                elif fault=="commit": actor["commitSequence"]+=1
                elif fault=="plan": actor["origin"]["x"]-=1
                elif fault=="height": actor["engineObject"]["pos_y"]+=1
                elif fault=="context": snapshot["context"]["mapId"]=67
                else: actor["presentationGeneration"]+=1
                with self.assertRaises(ValueError): meter.observe(snapshot,actor,old)
                self.assertFalse(meter.ready)

    def test_pending_rejects_restart_clear_motion_context_and_raw_pose_changes(self):
        for fault in ("restart","clear","skip","frame","map","motion","pose","height","inactive","reservation","owner","base"):
            with self.subTest(fault=fault):
                meter,old,rows=self.prime(); meter.observe(*rows[0],old)
                snapshot,actor=rows[1]; data=actor["crashPresentation"]
                if fault=="restart": data["timer"]=10
                elif fault=="clear": data["timer"]=0
                elif fault=="skip": data["timer"]=8
                elif fault=="frame": snapshot["frame"]+=1; data["frame"]+=1
                elif fault=="map": snapshot["context"]["mapId"]=67
                elif fault=="motion": actor["motionPhase"]="MOVING"
                elif fault=="pose": actor["engineObject"]["pos_x"]+=1
                elif fault=="height": actor["engineObject"]["pos_y"]+=1
                elif fault=="inactive": actor["engineObject"]["flags"]=0
                elif fault=="reservation": actor["reservationId"]=1
                elif fault=="owner": data["objectPointer"]+=4
                else: data["baseZ"]+=1
                with self.assertRaises(ValueError): meter.observe(snapshot,actor,rows[0][1])
                with self.assertRaises(ValueError): meter.observe(*rows[2],rows[1][1])
                self.assertFalse(meter.ready)

    def test_inactive_passthrough_still_requires_metadata(self):
        initial,old,_=fixture(); meter=CrashPresentationMeasurement()
        self.assertEqual(meter.observe(initial,old,None),old["engineObject"])
        del old["crashPresentation"]
        with self.assertRaises(ValueError): meter.observe(initial,old,None)

    def test_missing_prior_observation_and_proof_overflow_reject(self):
        _,old,rows=fixture()
        with self.assertRaises(ValueError): CrashPresentationMeasurement().observe(*rows[0],old)
        meter,old,rows=self.prime(); meter.proofs=[{}]*meter.max_proofs
        with self.assertRaises(ValueError): meter.observe(*rows[0],old)

    def test_proof_capacity_tracks_the_current_frame_budget(self):
        self.assertEqual(CrashPresentationMeasurement(max_frames=12000).max_proofs, 6001)
        self.assertEqual(CrashPresentationMeasurement(max_frames=11).max_proofs, 6)
        for value in (0, 65536, True, 1.5):
            with self.assertRaises(ValueError):
                CrashPresentationMeasurement(max_frames=value)

    def test_same_cycle_is_truthful_but_clock_rollback_rejects(self):
        meter,old,rows=self.prime()
        rows[0][0]["nativeCycle"]=1694
        rows[0][1]["crashPresentation"]["nativeCycle"]=1694
        meter.observe(*rows[0],old)
        rows[1][0]["nativeCycle"]=1693
        rows[1][1]["crashPresentation"]["nativeCycle"]=1693
        with self.assertRaises(ValueError): meter.observe(*rows[1],rows[0][1])


if __name__ == "__main__":
    unittest.main()
