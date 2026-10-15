"""Copied completed-frame controls for the mounted case of the shared Slam meter."""
from copy import deepcopy
import unittest
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_stomp_slam_measurement import MOUNTED_KIND, ORDER, StompSlamMeasurement, validate_recipe
from tools.overworld.devtools_stomp_slam_mounted_proof import FAULTS, StompSlamMountedNegative, measurements, validate_negative_result
from tools.overworld.test_devtools_stomp_slam_measurement import SOURCE, sample, stream


def mounted_sample(frame, application):
    import struct
    from tools.overworld.normal_play_observer import arc_height
    from tools.overworld.devtools_walk_matrix_observer import PHASES, decode_motion
    value = sample(frame, application)
    elapsed = min(18,max(0,frame-25))
    active = 26 <= frame <= 43
    player = value["player"]
    player.update(y=((player["pos_z"])>>16) if active else 409 if frame>=44 else 407,
                  face_y=32768+arc_height(elapsed,18),face_z=-40960,
                  movement_cmd=62 if active else 0)
    mount=value["actors"][1]
    mount.update(role="MOUNTED",inputOwnership=1,behaviorFingerprint=4242,
                 motionKind="HOP" if active else "NONE",motionPhase="COMMIT_PENDING" if frame==43 else "MOVING" if active else "IDLE",
                 motionElapsed=elapsed,motionDuration=18 if frame>=26 else 0,
                 reservationId=10 if active else 0,commitSequence=int(frame>=44),
                 origin=dict(x=585,y=407),target=dict(x=585,y=409),logical=dict(x=585,y=409 if frame>=44 else 407))
    mount["engineObject"].update({k:player[k] for k in ("pos_x","pos_y","pos_z","unk88_y")})
    mount["engineObject"].update(face_y=player["face_y"]-32768,face_z=0)
    raw=bytearray(52)
    if frame>=26:
        struct.pack_into("<HBBHH4h2iHH",raw,0,1,2,1,1,4242,585,407,585,409,65536,65536,18,10)
        raw[28:38]=bytes((1,2,16,0,0,0,0,2,1,1))
        struct.pack_into("<4H4B",raw,40,elapsed,0,0,int(frame>=44),PHASES.index(mount["motionPhase"]),0,int(frame>=44),0)
    hp=94 if frame>=25 else 114
    value["fieldControl"]["fieldPointer"]=0x02100000
    combat=value["pokemonCombat"]
    combat.update(observationBoundary="main-task-queue-completion",fieldSystem=0x02100000)
    combat["identity"]["descriptorVersion"]=1
    combat["targets"].append(dict(handle=deepcopy(mount["handle"]),species=155,role="MOUNTED",personality=155007,
        hp=hp,currentHp=hp,maxHp=114,actualMaxHp=114,hpSource="party",initialized=1,hpMirrorMatches=True,
        hitCount=int(frame>=25),lastDamage=20 if frame>=25 else 0,immunityFrames=max(0,60-(frame-25)) if frame>=25 else 0,
        knockbackPending=0,motion=decode_motion(bytes(raw))))
    value["party"]=[dict(slot=0,species=155,personality=155007,identityVerified=True,hp=hp,maxHp=114)]
    value["partyObservation"]=dict(frame=frame,boundary="main-task-queue-completion")
    return value


def mounted_stream():
    template=stream()
    app=StompSlamMeasurement(SOURCE).application
    by_frame={r["samples"][0]["frame"]:r for r in template if r.get("samples")}
    health={r["action"]:r for r in template if r.get("command")}
    def hp(frame,index):
        row=deepcopy(health[ORDER[index]])
        row["snapshot"]=mounted_sample(frame,app)
        row["receipt"]["playerHealth"].update(frame=frame,nativeCycle=frame+1000,lastHealthFrame=frame,
            hp=100,savedHp=100,acceptedHits=0,lastDamage=0,protectionFrames=0)
        return row
    rows=[hp(9,0)]
    owner=mounted_sample(9,app)["actors"][1]["handle"]
    def event(frame,name,sequence,a,b):
        return dict(frame=frame,kind="native",data=dict(event=name,actorHandle=owner["value"],
            actor={k:v for k,v in owner.items() if k!="value"},sequence=sequence,actorFrame=frame,reasonId=0,valueA=a,valueB=b))
    for frame in range(10,45):
        row=deepcopy(by_frame[min(frame,43)])
        row["action"]=ORDER[1 if frame<=25 else 3]
        row["samples"]=[mounted_sample(frame,app)]
        row["cycleIntervals"][0]["completedGameFrame"]=frame
        if frame==44:row["events"]=[]
        if frame==26:row["events"] += [event(26,"INTENT_CREATED",250,2,1),event(26,"MOTION_STARTED",251,2,18)]
        if frame==44:row["events"] += [event(44,"LOGICAL_COMMIT",400,1,2),event(44,"MOTION_FINISHED",401,1,2),event(44,"CONTROL_RETURNED",402,1,1)]
        raw=bytearray(216)
        row["profileCache"]["resolvedProfiles"].append(dict(fingerprint=4242,resolved=True,
            sourceSha256=SOURCE["profileSha256"],resultHex=raw.hex()))
        row["profileCache"].update(frame=frame,nativeCycle=frame+1000)
        rows.append(row)
        if frame==25:rows.append(hp(frame,2))
    rows.append(hp(44,4))
    return rows


def evaluate(rows, negative=None):
    meter=StompSlamMeasurement(SOURCE,kind=MOUNTED_KIND,passive_role="MOUNTED")
    meter.latest=mounted_sample(9,meter.application)
    meter.setup_index=len(meter.setup)
    meter.subjects={name:select_current_actor(meter.latest,a)
                    for name,a in zip(("snorlax","passive"),meter.latest["actors"])}
    for row in rows:
        if row.get("action")=="after-landing" and meter.action_index!=4:break
        meter.observe_record(negative.mutate(row,meter.subjects) if negative else row)
        if meter.failures:break
    return meter.finish(),meter


class MountedSlamChecks(unittest.TestCase):
    def test_same_shared_slam_restores_mount_and_rider(self):
        result,_=evaluate(mounted_stream())
        self.assertTrue(result["passed"],result["failures"])
        self.assertEqual(result["contact"]["elapsed"],15)
        self.assertEqual(result["beforeHP"]["hp"],result["contactHP"]["hp"])
        self.assertEqual(result["beforeMountHP"]["hp"]-result["contactMountHP"]["hp"],20)
        self.assertEqual([v["elapsed"] for v in result["mountedJump"]["samples"]],list(range(1,19)))
        self.assertEqual(result["mountedTerminal"]["face_y"],0)
        self.assertEqual(result["playerJump"]["samples"][-1]["pose"]["face_y"],32768)
        replay=dict(passed=True,failures=[],observedFrames=result["observedFrames"],measurements={MOUNTED_KIND:result})
        self.assertEqual(len(measurements(replay,dict(sessionId="private",sessionCleanup=dict(sessionId="private",closed=True,errors=[])))),5)

    def test_shared_copied_faults_and_mounted_owner_faults(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                negative=StompSlamMountedNegative(fault)
                result,_=evaluate(mounted_stream(),negative)
                self.assertTrue(negative.applied)
                validate_negative_result(result,fault)

    def test_drifted_mount_or_rider_height_does_not_finish(self):
        for key in ("face_y","unk88_y"):
            rows=mounted_stream()
            row=next(r for r in rows if r.get("samples") and r["samples"][0]["frame"]==42)
            row["samples"][0]["actors"][1]["engineObject"][key]+=1
            result,_=evaluate(rows)
            self.assertFalse(result["passed"])

    def test_orphan_auto_walk_before_contact_is_rejected(self):
        rows=mounted_stream()
        row=next(r for r in rows if r.get("samples") and r["samples"][0]["frame"]==12)
        actor=row["samples"][0]["actors"][1]
        actor.update(motionKind="WALK",motionPhase="MOVING")
        result,_=evaluate(rows)
        self.assertFalse(result["passed"])
        self.assertIn("queued forced Jump2",str(result["failures"]))

    def test_mounted_recipe_cannot_use_follower_case(self):
        from tools.overworld.test_devtools_stomp_slam_measurement import ROOT
        import json
        recipe=json.loads((ROOT/"tests/overworld/test-recipes/profile.stomp-slam.player-contact.json").read_text())
        recipe.update(id="profile.stomp-slam.mounted-player-contact", requirements=["current.stomp-slam-mounted-player-contact"])
        recipe["subjects"][1]["role"]="MOUNTED"
        recipe["measurements"][0]["kind"]=MOUNTED_KIND
        recipe["setup"][2]["id"]="create-passive-mount"
        recipe["setup"][2]["args"]["role"]="mounted"
        for action in recipe["actions"]:
            if "until" in action["args"]:action["args"]["until"]["measurement"]=MOUNTED_KIND
        recipe["assertions"][0]["measurement"]=MOUNTED_KIND
        validate_recipe(recipe,MOUNTED_KIND,"MOUNTED")
        with self.assertRaises(ValueError):validate_recipe(recipe)
        with self.assertRaises(ValueError):StompSlamMeasurement(SOURCE,kind=MOUNTED_KIND)


if __name__=="__main__":unittest.main()
