"""Copied native Rattata data; no game control or ignored-artifact dependency."""
from copy import deepcopy
import struct
import unittest
from tools.overworld.normal_play_observer import arc_height
from tools.overworld.devtools_mounted_rattata_ledge_measurement import KIND,ORDER,SETUP,MountedRattataLedgeMeasurement,validate_recipe
from tools.overworld.devtools_mounted_rattata_ledge_proof import FAULTS,MountedRattataLedgeNegative,measurements,validate_negative_result
from tools.overworld.devtools_walk_matrix_observer import PHASES,decode_motion
from tools.overworld.test_devtools_player_health_throw_contact_measurement import actor

SOURCE=dict(contractVersion=1,romSha256="a"*64,overlaySha256="b"*64,profileSha256="c"*64)


def sample(frame):
    elapsed=min(12,max(0,frame-9))
    mount=actor(19,7,190007,395)
    mount.update(role="MOUNTED",inputOwnership=1,behaviorFingerprint=471845776,
        motionKind="HOP" if 10<=frame<=21 else "NONE",
        motionPhase="MOVING" if 10<=frame<21 else "COMMIT_PENDING" if frame==21 else "IDLE",
        motionElapsed=elapsed,motionDuration=12,reservationId=7 if 10<=frame<=21 else 0,
        commitSequence=3+int(frame>=22),origin=dict(x=590,y=395),target=dict(x=590,y=397),
        logical=dict(x=590,y=397 if frame>=21 else 395),movementPolicy=dict(speed=0,base=0,skid=0,turn=0))
    mount["engineObject"].update(pos_x=(590<<16)+32768,pos_y=65536,
        pos_z=(395<<16)+32768+131072*elapsed//12,face_x=0,face_y=arc_height(elapsed,12),face_z=0,unk88_y=0)
    player=dict(x=590,y=397 if frame>=21 else 395,
        **{k:mount["engineObject"][k] for k in ("pos_x","pos_y","pos_z","face_x","face_y","face_z","unk88_y")})
    player["face_y"]+=32768
    raw=bytearray(52)
    struct.pack_into("<HBBHH4h2iHH",raw,0,1,2,1,1,471845776&65535,590,395,590,397,65536,65536,12,7)
    raw[28:38]=bytes((1,2,16,0,0,0,0,2,0,0))
    struct.pack_into("<4H4B",raw,40,elapsed,0,0,int(frame>=22),PHASES.index(mount["motionPhase"]),0,int(frame>=22),0)
    return dict(frame=frame,nativeCycle=1000+frame,fieldAvailable=True,observationBoundary="main-task-queue-completion",
        romSha256=SOURCE["romSha256"],fieldControl=dict(taskPointer=0),context=dict(mapId=33,fieldEpoch=1,mapGeneration=1),
        actors=[mount],player=player,selector=dict(rawHeld=128 if frame==10 else 0,heldKeys=128 if frame==10 else 0,simulatedKeys=0),
        terrain=dict(cells=[dict(x=590,y=396,loaded=True,behavior=59,collision=True),dict(x=590,y=397,loaded=True,behavior=0,collision=False)]),
        nativeObservation=dict(coverageComplete=True,profilesEvicted=0,profileFingerprints=[471845776]),
        pokemonCombat=dict(schemaVersion=1,available=True,frame=frame,nativeCycle=1000+frame,
            identity=dict(romSha256=SOURCE["romSha256"],overlaySha256=SOURCE["overlaySha256"]),
            targets=[dict(handle=deepcopy(mount["handle"]),species=19,role="MOUNTED",personality=190007,hp=48,
                          hpSource="party",knockbackPending=0,motion=decode_motion(bytes(raw)))]))


def stream():
    owner=sample(9)["actors"][0]["handle"]
    def event(frame,name,seq,a,b):
        return dict(frame=frame,kind="native",data=dict(actorHandle=owner["value"],actor={k:v for k,v in owner.items() if k!="value"},
            event=name,sequence=seq,reasonId=0,valueA=a,valueB=b))
    events={10:[event(10,"INTENT_CREATED",1,2,1),event(10,"MOTION_STARTED",3,2,12)],
            22:[event(22,"LOGICAL_COMMIT",6,4,2),event(22,"MOTION_FINISHED",7,4,2),event(22,"CONTROL_RETURNED",8,1,4)]}
    raw=bytearray(216);raw[87]=6;raw[89]=2;raw[92]=1;raw[100:102]=bytes((1,8));struct.pack_into("<I",raw,192,471845776)
    return [dict(phase="observe",action=ORDER[0 if frame==10 else 1],samples=[sample(frame)],events=events.get(frame,[]),
        completedGameFrames=1,observedFieldFrames=1,nativeCycles=1,cycleIntervals=[dict(completedGameFrame=frame,cpuNs=1,wallNs=1)],
        profileCache=dict(frame=frame,nativeCycle=frame+1000,resolvedProfiles=[dict(resolved=True,fingerprint=471845776,
            sourceSha256=SOURCE["profileSha256"],resultHex=raw.hex())])) for frame in range(10,59)]


def evaluate(rows,negative=None,baseline=None):
    meter=MountedRattataLedgeMeasurement(SOURCE)
    baseline=baseline or sample(9)
    try:meter.arm(baseline,baseline["actors"][0])
    except ValueError as error:meter.failures.append(str(error));return meter.finish()
    meter.setup_index=len(SETUP)
    for row in rows:
        meter.observe_record(negative.mutate(row,{"rattata":meter.subject}) if negative else row)
        if meter.failures:break
    return meter.finish()


class MountedRattataLedgeChecks(unittest.TestCase):
    def test_one_fresh_native_hop_and_exact_input_return(self):
        result=evaluate(stream())
        self.assertTrue(result["passed"],result["failures"])
        self.assertEqual([s["elapsed"] for s in result["hop"]["samples"]],list(range(1,13)))
        self.assertEqual(result["release"]["commitSequence"],4)
        replay=dict(passed=True,failures=[],observedFrames=result["observedFrames"],measurements={KIND:result})
        self.assertEqual(len(measurements(replay,dict(sessionId="owned",sessionCleanup=dict(sessionId="owned",closed=True,errors=[])))),6)

    def test_copied_faults_reject_exact_claim(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                negative=MountedRattataLedgeNegative(fault)
                result=evaluate(stream(),negative)
                self.assertTrue(negative.applied)
                validate_negative_result(result,fault)

    def test_started_with_momentum_or_wrong_ledge_cannot_pass(self):
        for fault in ("speed","ledge"):
            baseline=sample(9)
            if fault=="speed":baseline["actors"][0]["movementPolicy"]["speed"]=6
            else:baseline["terrain"]["cells"][0]["behavior"]=0
            result=evaluate(stream(),baseline=baseline)
            self.assertFalse(result["passed"])

    def test_duplicate_terminal_sequence_cannot_pass(self):
        rows=stream();events=next(r["events"] for r in rows if r["samples"][0]["frame"]==22)
        events[1]["data"]["sequence"]=events[0]["data"]["sequence"]
        result=evaluate(rows)
        self.assertFalse(result["passed"])
        self.assertIn("ordered normal commit",str(result["failures"]))


if __name__=="__main__":unittest.main()
