"""Focused native Slam/HP controls; no emulator, planner, or product writes."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import unittest

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_stomp_slam_measurement import KIND, ORDER, SETUP, DURATION, RISE, HANG, DROP, PEAK, MAX_DISTANCE, StompSlamMeasurement, validate_recipe
from tools.overworld.devtools_stomp_slam_proof import FAULTS, StompSlamNegative, measurements, validate_negative_result
from tools.overworld.devtools_walk_matrix_observer import PHASES, decode_motion
from tools.overworld.test_devtools_player_health_throw_contact_measurement import actor

ROOT = Path(__file__).resolve().parents[2]
SOURCE = dict(contractVersion=1, romSha256="a" * 64, overlaySha256="b" * 64, profileSha256="c" * 64)


def sample(frame, application):
    elapsed = min(DURATION, max(0, frame - 10))
    snorlax = actor(143, 0, 143000, 401)
    snorlax.update(inputOwnership=0, behaviorFingerprint=1717, matchedLayerMask=1 << application,
                   motionKind="HOP" if 10 <= frame < 26 else "NONE",
                   motionPhase="MOVING" if 10 <= frame < 26 else "IDLE",
                   motionElapsed=elapsed, motionDuration=DURATION if frame >= 10 else 0,
                   reservationId=9 if 10 <= frame < 26 else 0, commitSequence=int(frame >= 26))
    snorlax["origin"] = dict(x=585, y=401)
    snorlax["target"] = dict(x=585, y=407)
    snorlax["logical"] = dict(x=585, y=407 if frame >= 26 else 401)
    q = min(4096, (elapsed << 12) // RISE)
    height = PEAK * (2*q - ((q*q)>>12) if elapsed <= RISE else 4096 if elapsed <= RISE+HANG else ((DURATION-elapsed) << 12) // DROP)
    snorlax["engineObject"].update(pos_x=(585<<16)+32768, pos_y=65536,
        pos_z=(401<<16)+32768+int(393216*min(elapsed,RISE)/RISE),
        face_x=0, face_y=0, face_z=0, unk88_y=height)
    passive = actor(155, 7, 155007, 408)
    passive["role"] = "FOLLOWER"
    passive["engineObject"].update(pos_y=65536, face_x=0, face_y=0, face_z=0, unk88_y=0)
    jump_elapsed = min(18, max(0, frame - 25))
    jump_height = 16 * 4096 * min(jump_elapsed,18-jump_elapsed) // 9
    player = dict(x=585, y=409 if frame >= 43 else 407,
                  pos_x=(585<<16)+32768, pos_y=65536,
                  pos_z=(407<<16)+32768+int(131072*jump_elapsed/18),
                  face_x=0, face_y=jump_height, face_z=0, unk88_y=0,
                  movement_cmd=62 if 26 <= frame < 43 else 0)
    raw = bytearray(52)
    struct.pack_into("<HBBHH4h2iHH",raw,0,1,2,1,1,1717,585,401,585,407,65536,65536,DURATION,9)
    raw[28:38] = bytes((1,MAX_DISTANCE,PEAK,RISE,HANG,0,0,1,1,2))
    struct.pack_into("<4H4B",raw,40,elapsed,0,MAX_DISTANCE if frame>=26 else 0,int(frame>=26),
                     PHASES.index(snorlax["motionPhase"]),0,int(frame>=26),0)
    return dict(frame=frame,nativeCycle=frame+1000,fieldAvailable=True,romSha256=SOURCE["romSha256"],
        observationBoundary="main-task-queue-completion",context=dict(mapId=33,fieldEpoch=1,mapGeneration=1),
        fieldControl=dict(taskPointer=0),actors=[snorlax,passive],player=player,
        nativeObservation=dict(coverageComplete=True,profilesEvicted=0,profileFingerprints=[1717]),
        pokemonCombat=dict(schemaVersion=1,available=True,frame=frame,nativeCycle=frame+1000,
            identity=dict(romSha256=SOURCE["romSha256"],overlaySha256=SOURCE["overlaySha256"]),
            targets=[dict(handle=deepcopy(snorlax["handle"]),species=143,role="WILD",personality=143000,
                          hp=100,currentHp=100,maxHp=100,hpSource="wild-resident",knockbackPending=0,
                          motion=decode_motion(bytes(raw)))],
            movementTimers=[dict(handle=deepcopy(snorlax["handle"]),movementActorControlMode=0)]))


def health(frame, application):
    hp = 80 if frame >= 25 else 100
    return dict(phase="observe",action=ORDER[0 if frame==9 else 2 if frame==25 else 4],
        command="player-health.observe",snapshot=sample(frame,application),receipt=dict(playerHealth=dict(
            schemaVersion=1,identity=dict(descriptorVersion=1,overlayId=161,romSha256=SOURCE["romSha256"],
                                         overlaySha256=SOURCE["overlaySha256"]),
            frame=frame,nativeCycle=frame+1000,hp=hp,savedHp=hp,maxHp=100,
            frameActive=False,recoveryPending=False,acceptedHits=int(frame>=25),lastDamage=20 if frame>=25 else 0,
            protectionFrames=max(0,60-(frame-25)) if frame>=25 else 0,lastHealthFrame=frame)))


def stream():
    meter = StompSlamMeasurement(SOURCE)
    app = meter.application
    initial = sample(9, app)
    owner = initial["actors"][0]["handle"]
    profile = bytearray(216)
    profile[0],profile[2],profile[12],profile[13],profile[79] = 3,2,2,10,10
    profile[20:22] = bytes((1,MAX_DISTANCE))
    profile[72:75] = bytes((1,16,20))
    struct.pack_into("<I",profile,192,1717)
    profile[196:210] = bytes(12)+bytes((1,0))
    profile[212] = app
    struct.pack_into("<H",profile,214,meter.condition_id)
    def event(frame,name,sequence,**extra):
        data=dict(event=name,actorHandle=owner["value"],actor={k:v for k,v in owner.items() if k!="value"},
                  sequence=sequence,actorFrame=frame,valueA=0,valueB=0,reasonId=0)
        data.update(extra)
        return dict(frame=frame,kind="native",data=data)
    events={10:[event(10,"CONDITIONAL_RESOLVED",100,valueA=meter.condition_id,
                reasonId=app|(app<<5)|(1<<10)|(1<<12)|(1<<13)|(1<<14)|(1<<15),valueB=190|(310<<16)),
                event(10,"INTENT_CREATED",101),event(10,"MOTION_STARTED",102,valueA=2,valueB=DURATION)],
            26:[event(26,"LOGICAL_COMMIT",310,valueA=1,valueB=2),
                event(26,"MOTION_FINISHED",311,valueA=1,valueB=2),event(26,"CONTROL_RETURNED",312,valueB=1)]}
    rows=[health(9,app)]
    for frame in range(10,44):
        rows.append(dict(phase="observe",action=ORDER[1 if frame<=25 else 3],samples=[sample(frame,app)],
            events=events.get(frame,[]),completedGameFrames=1,observedFieldFrames=1,nativeCycles=1,
            cycleIntervals=[dict(completedGameFrame=frame,cpuNs=1,wallNs=1)],
            profileCache=dict(frame=frame,nativeCycle=frame+1000,resolvedProfiles=[dict(
                fingerprint=1717,resolved=True,sourceSha256=SOURCE["profileSha256"],resultHex=profile.hex())])))
        if frame==25:
            rows.append(health(frame,app))
    rows.append(health(43,app))
    return rows


def successor_stream():
    rows=stream()
    release=[deepcopy(e) for row in rows for e in row.get("events", []) if e["data"]["event"]
             in ("LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")]
    for e in release:
        e["frame"]=e["data"]["actorFrame"]=26
    start=deepcopy(release[-1])
    start["data"].update(event="MOTION_STARTED",sequence=314,valueA=2,valueB=DURATION)
    intent=deepcopy(start)
    intent["data"].update(event="INTENT_CREATED",sequence=313)
    for row in rows:
        if row.get("samples") and row["samples"][0]["frame"]==26:
            row["events"]=release+[intent,start]
        elif row.get("samples") and row["samples"][0]["frame"]==27:
            row["events"]=[]
        for s in row.get("samples", [])+([row["snapshot"]] if "snapshot" in row else []):
            if s["frame"]<26:continue
            a=s["actors"][0]
            elapsed=min(DURATION,s["frame"]-26)
            a.update(motionKind="HOP",motionPhase="MOVING",motionElapsed=elapsed,motionDuration=DURATION,
                     reservationId=10,commitSequence=1,origin=dict(x=585,y=407),target=dict(x=585,y=408),
                     logical=dict(x=585,y=407))
            a["engineObject"].update(pos_z=(407<<16)+32768+int(65536*min(elapsed,RISE)/RISE),
                unk88_y=PEAK*(2*((elapsed<<12)//RISE) - ((((elapsed<<12)//RISE)**2)>>12) if elapsed<=RISE else 4096 if elapsed<=RISE+HANG else ((DURATION-elapsed)<<12)//DROP))
            target=s["pokemonCombat"]["targets"][0]
            raw=bytearray.fromhex(target["motion"]["rawHex"])
            struct.pack_into("<4h",raw,8,585,407,585,408)
            struct.pack_into("<H",raw,26,10)
            raw[29]=1
            struct.pack_into("<4H4B",raw,40,elapsed,0,0,0,PHASES.index("MOVING"),0,0,0)
            target["motion"]=decode_motion(bytes(raw))
    return rows


def settled_stream(pause=30, successor=False):
    template = stream()
    app = StompSlamMeasurement(SOURCE).application
    commit_frame, release_frame = 10 + DURATION, 10 + DURATION + pause
    by_frame = {row["samples"][0]["frame"]: row for row in template if row.get("samples")}
    terminal_events = deepcopy(by_frame[commit_frame]["events"])
    successor_boundary = next(row for row in successor_stream()
                              if row.get("samples") and row["samples"][0]["frame"] == commit_frame)
    rows = [health(9, app)]
    for frame in range(10, release_frame + 1):
        row = deepcopy(by_frame[min(frame, 43)])
        row["samples"] = [sample(frame, app)]
        row["action"] = ORDER[1 if frame <= 25 else 3]
        row["events"] = deepcopy(by_frame[frame]["events"]) if frame < commit_frame else []
        row["cycleIntervals"][0]["completedGameFrame"] = frame
        row["profileCache"].update(frame=frame, nativeCycle=frame+1000)
        profile = row["profileCache"]["resolvedProfiles"][0]
        cache = bytearray.fromhex(profile["resultHex"])
        cache[22] = pause
        profile["resultHex"] = cache.hex()
        body = row["samples"][0]["actors"][0]
        target = row["samples"][0]["pokemonCombat"]["targets"][0]
        raw = bytearray.fromhex(target["motion"]["rawHex"])
        raw[34] = pause
        if commit_frame <= frame < release_frame:
            body.update(motionKind="HOP", motionPhase="SETTLING")
            struct.pack_into("<H", raw, 42, release_frame-frame)
            raw[48] = PHASES.index("SETTLING")
        if frame == commit_frame:
            row["events"] = [deepcopy(terminal_events[0])]
        if frame == release_frame:
            row["events"] += deepcopy(terminal_events[1:])
            for event in row["events"]:
                event["frame"] = event["data"]["actorFrame"] = frame
        target["motion"] = decode_motion(bytes(raw))
        if frame == release_frame and successor:
            successor_sample = successor_boundary["samples"][0]
            row["samples"][0]["actors"][0] = deepcopy(successor_sample["actors"][0])
            target["motion"] = deepcopy(successor_sample["pokemonCombat"]["targets"][0]["motion"])
            starts = deepcopy(successor_boundary["events"][-2:])
            for event in starts:
                event["frame"] = event["data"]["actorFrame"] = frame
            row["events"] += starts
        rows.append(row)
        if frame == 25:
            rows.append(health(frame, app))
    terminal = health(release_frame, app)
    terminal["snapshot"] = deepcopy(rows[-1]["samples"][0])
    rows.append(terminal)
    return rows


def evaluate(rows, negative=None):
    meter=StompSlamMeasurement(SOURCE)
    meter.latest=sample(9,meter.application)
    meter.setup_index=len(SETUP)
    meter.subjects={name:select_current_actor(meter.latest,a)
                    for name,a in zip(("snorlax","passive"),meter.latest["actors"])}
    for row in rows:
        if row.get("action")=="after-landing" and meter.action_index!=4:
            break
        meter.observe_record(negative.mutate(row,meter.subjects) if negative else row)
        if meter.failures:
            break
    return meter.finish(),meter


class StompSlamChecks(unittest.TestCase):
    def test_split_commit_exact_thirty_frame_settle_and_release(self):
        for successor in (False, True):
            result, _ = evaluate(settled_stream(successor=successor))
            self.assertTrue(result["passed"], result["failures"])
            release = result["slamRelease"]
            self.assertEqual([row["frame"] for row in release["settleSamples"]], list(range(26, 56)))
            self.assertEqual([event["frame"] for event in release["events"]], [26, 56, 56])
            self.assertEqual(result["completedMotion"]["finishFrame"], 56)
            replay = dict(passed=True, failures=[], observedFrames=result["observedFrames"], measurements={KIND:result})
            self.assertEqual(len(measurements(replay, dict(sessionId="private",
                sessionCleanup=dict(sessionId="private", closed=True, errors=[])))), 5)

    def test_stock_model_step_dip_preserves_physical_base_through_release(self):
        for successor in (False, True):
            rows = settled_stream(successor=successor)
            for row in rows:
                for current in row.get("samples", []) + ([row["snapshot"]] if "snapshot" in row else []):
                    if 26 < current["frame"] <= 56:
                        current["actors"][0]["engineObject"]["face_y"] = -8192
            result, _ = evaluate(rows)
            self.assertTrue(result["passed"], result["failures"])
            release = result["slamRelease"]
            settle = release["settleSamples"]
            self.assertEqual([row["frame"] for row in settle], list(range(26, 56)))
            self.assertEqual([event["frame"] for event in release["events"]], [26, 56, 56])
            self.assertTrue(all(row["terminalPose"]["pos_y"] == 65536
                               and row["terminalPose"]["unk88_y"] == 0 for row in settle))
            self.assertEqual(settle[0]["terminalPose"]["face_y"], 0)
            self.assertEqual(release["terminalPose"]["face_y"], -8192)
            self.assertEqual(release["terminalPose"]["pos_y"], 65536)
            self.assertEqual(release["terminalPose"]["unk88_y"], 0)
            replay = dict(passed=True, failures=[], observedFrames=result["observedFrames"], measurements={KIND:result})
            self.assertEqual(len(measurements(replay, dict(sessionId="private",
                sessionCleanup=dict(sessionId="private", closed=True, errors=[])))), 5)

    def test_stock_step_dip_cannot_hide_wrong_base_offsets_or_terminal_pose(self):
        controls = [(fault, frame) for frame in (30, 56)
                    for fault in ("wrong-base", "raised", "other-dip", "shared-offset", "horizontal")]
        controls += [("dip-at-commit", 26), ("dip-in-flight", 15)]
        for fault, frame in controls:
            rows = settled_stream()
            row = next(r for r in rows if r.get("samples") and r["samples"][0]["frame"] == frame)
            engine = row["samples"][0]["actors"][0]["engineObject"]
            engine["face_y"] = -8192
            if fault == "wrong-base": engine["pos_y"] += 8192
            elif fault == "raised": engine["face_y"] = 8192
            elif fault == "other-dip": engine["face_y"] = -4096
            elif fault == "shared-offset": engine["unk88_y"] = 1
            elif fault == "horizontal": engine["face_x"] = 1
            result, _ = evaluate(rows)
            with self.subTest(fault=fault, frame=frame): self.assertFalse(result["passed"])

    def test_settle_cannot_change_plan_pose_owner_timer_or_commit(self):
        for fault in ("timer", "plan", "pose", "owner", "duplicate-commit", "early-release", "missing-release", "missing-frame"):
            rows = settled_stream()
            row = next(r for r in rows if r.get("samples") and r["samples"][0]["frame"] == 30)
            current = row["samples"][0]
            if fault in ("timer", "plan"):
                target = current["pokemonCombat"]["targets"][0]
                raw = bytearray.fromhex(target["motion"]["rawHex"])
                if fault == "timer":
                    struct.pack_into("<H", raw, 42, 1)
                else:
                    raw[29] -= 1
                target["motion"] = decode_motion(bytes(raw))
            elif fault == "pose":
                current["actors"][0]["engineObject"]["unk88_y"] = 1
            elif fault == "owner":
                current["pokemonCombat"]["movementTimers"][0]["movementActorControlMode"] = 1
            elif fault in ("duplicate-commit", "early-release"):
                terminal = next(r for r in rows if r.get("samples") and r["samples"][0]["frame"] == (26 if fault == "duplicate-commit" else 56))
                row["events"] = deepcopy(terminal["events"])
                for event in row["events"]:
                    event["frame"] = event["data"]["actorFrame"] = 30
            elif fault == "missing-release":
                next(r for r in rows if r.get("samples") and r["samples"][0]["frame"] == 56)["events"] = []
            else:
                rows.remove(row)
            result, _ = evaluate(rows)
            self.assertFalse(result["passed"], fault)

    def test_commit_only_terminal_is_valid_incomplete_prefix(self):
        rows = settled_stream()
        rows = rows[:next(i for i, row in enumerate(rows) if row.get("samples")
                         and row["samples"][0]["frame"] == 26) + 1]
        meter = StompSlamMeasurement(SOURCE)
        meter.latest = sample(9, meter.application)
        meter.setup_index = len(SETUP)
        meter.subjects = {name:select_current_actor(meter.latest, body)
                         for name, body in zip(("snorlax", "passive"), meter.latest["actors"])}
        for row in rows:
            meter.observe_record(row)
        self.assertEqual(meter.failures, [])
        self.assertIsNotNone(meter.completed)
        self.assertIsNone(meter.release)
        self.assertFalse(meter.result()["ready"])

    def test_complete_native_arc_shared_hit_and_jump2(self):
        result,_=evaluate(stream())
        self.assertTrue(result["passed"],result["failures"])
        self.assertEqual(result["contact"]["elapsed"],15)
        self.assertEqual([s["elapsed"] for s in result["slam"]["samples"]],list(range(DURATION+1)))
        self.assertEqual(result["playerJump"]["samples"][-1]["height"],0)
        replay=dict(passed=True,failures=[],observedFrames=result["observedFrames"],measurements={KIND:result})
        self.assertEqual(len(measurements(replay,dict(sessionId="private",sessionCleanup=dict(sessionId="private",closed=True,errors=[])))),5)

    def test_copied_faults_reject_their_named_claim(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                negative=StompSlamNegative(fault)
                result,_=evaluate(stream(),negative)
                self.assertTrue(negative.applied)
                self.assertFalse(result["passed"])
                validate_negative_result(result,fault)

    def test_zero_pause_successor_supplies_real_terminal_pose(self):
        result,_=evaluate(successor_stream())
        self.assertTrue(result["passed"],result["failures"])
        self.assertEqual([s["elapsed"] for s in result["slam"]["samples"]],list(range(DURATION)))
        self.assertEqual(result["completedMotion"]["travelEnd"]["observedBy"],"successor-origin")
        self.assertEqual(result["completedMotion"]["terminalNativeMotion"]["elapsed"],0)
        self.assertEqual(result["slamRelease"]["commitSequence"],1)
        self.assertEqual([e["event"] for e in result["slamRelease"]["events"]],
                         ["LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED"])

    def test_successor_terminal_needs_adjacent_pose_ordered_release_and_one_commit(self):
        for fault in ("missing-release", "duplicate-sequence", "wrong-pose", "second-commit", "early-successor"):
            rows=successor_stream()
            row=next(r for r in rows if r.get("samples") and r["samples"][0]["frame"]==26)
            if fault=="missing-release":row["events"].pop(2)
            elif fault=="duplicate-sequence":row["events"][1]["data"]["sequence"]=row["events"][0]["data"]["sequence"]
            elif fault=="wrong-pose":row["samples"][0]["actors"][0]["engineObject"]["unk88_y"]=1
            elif fault=="second-commit":row["samples"][0]["actors"][0]["commitSequence"]=2
            else:rows.remove(next(r for r in rows if r.get("samples") and r["samples"][0]["frame"]==25))
            result,_=evaluate(rows)
            self.assertFalse(result["passed"],fault)

    def test_no_native_bytes_and_foreign_owner_cannot_pass(self):
        for field,value in (("knockbackPending",1),("role","FOLLOWER"),("personality",777)):
            rows=stream()
            rows[1]["samples"][0]["pokemonCombat"]["targets"][0][field]=value
            result,_=evaluate(rows)
            self.assertFalse(result["passed"])
            self.assertIn("same free living Wild",str(result["failures"]))
        rows=stream()
        rows[1]["samples"][0]["pokemonCombat"]["targets"][0]["motion"]["rawHex"]="00"
        result,_=evaluate(rows)
        self.assertFalse(result["passed"])

    def test_missing_frame_and_native_pose_do_not_get_synthesized(self):
        rows=stream()
        del rows[7]
        result,_=evaluate(rows)
        self.assertFalse(result["passed"])
        rows=stream()
        rows[1]["samples"][0]["actors"][0]["engineObject"].pop("pos_y")
        result,_=evaluate(rows)
        self.assertFalse(result["passed"])

    def test_recipe_keeps_normal_setup_and_no_forced_state(self):
        recipe=json.loads((ROOT/'tests/overworld/test-recipes/profile.stomp-slam.player-contact.json').read_text())
        validate_recipe(recipe)
        changed=deepcopy(recipe)
        changed["actions"][1]["args"]["keys"]=["DOWN"]
        with self.assertRaises(ValueError):validate_recipe(changed)

    def test_another_attacking_body_cannot_supply_the_hp_receipt(self):
        rows=stream()
        for row in rows:
            if not row.get("samples"):
                continue
            frame=row["samples"][0]["frame"]
            if frame not in (24,25):
                continue
            passive=row["samples"][0]["actors"][1]
            passive.update(behaviorFingerprint=2727)
            passive["engineObject"].update(pos_z=(407<<16)+32768+(65536 if frame==24 else 0))
            profile=bytearray(216)
            profile[72]=1
            row["profileCache"]["resolvedProfiles"].append(dict(resolved=True,fingerprint=2727,
                sourceSha256=SOURCE["profileSha256"],resultHex=profile.hex()))
        result,_=evaluate(rows)
        self.assertFalse(result["passed"])
        self.assertIn("another attacking body",str(result["failures"]))


if __name__=="__main__":unittest.main()
