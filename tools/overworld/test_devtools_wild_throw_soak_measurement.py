"""Host copies exercise S5 guards; these tests do not grant native acceptance."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import struct
import sys
import unittest
if __package__ in (None, ""): sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.overworld.devtools_wild_throw_soak_measurement import (
    ACTIONS, CASE, CHECKPOINT_LEGS, GEODUDES, HELD_KEYS, KIND, LEG_FRAME_COUNTS, LEG_FRAMES, MIN_FRAMES, SETUP, SOAK_FRAMES, SUBJECTS,
    WildThrowSoakMeasurement, ground_state, validate_recipe,
)
from tools.overworld.devtools_wild_throw_soak_proof import (
    FAULTS, WildThrowSoakNegative, contract, validate_negative_result,
)
from tools.overworld.devtools_wild_throw_moving_candidate_measurement import (
    THROW_APPLICATION, THROW_APPLICATION_BIT, THROW_RELEASE_BIT, TRIGGER_CONDITION, CARGO_CONDITION,
)
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.test_devtools_cargo_route_continuity import SOURCE, query_event
from tools.overworld.test_devtools_player_health_throw_contact_measurement import actor
from tools.overworld.test_devtools_damage_follower_measurement import motion, native
from tools.overworld.normal_play_observer import MotionRecorder, complete_travel

ROOT = Path(__file__).resolve().parents[2]
SOURCE = dict(SOURCE, helperAddress=0x023C79C4, helperEntrySha256="d"*64)


def binding(target=None, *, player=False):
    raw = bytearray(24); bound = player or target is not None
    if target: raw[:12] = raw_handle(target["handle"])
    raw[12] = 1 if player else 2 if target else 0
    condition = TRIGGER_CONDITION if player else CARGO_CONDITION if target else 0
    struct.pack_into("<HIBBBB", raw, 14, condition, 0, THROW_APPLICATION if bound else 0, 0, int(bound), 0)
    return dict(bound=bound, flags=int(bound), sourceConditionId=condition, sourceApplication=THROW_APPLICATION if bound else 0,
        expiresAt=0, lifetime=0, reason=0, target=dict(kind="PLAYER" if player else "ACTOR" if target else "NONE",
        actor=deepcopy(target["handle"]) if target else None), targetCurrent=bound, rawHex=raw.hex())


def rebind(s, slot, *, player=True, cargo=None):
    row = s["pokemonCombat"]["interactions"]["carriers"][slot]
    row["bindings"] = dict(trigger=binding(player=player), cargo=binding(cargo))
    row["rawBindingsHex"] = (raw_handle(row["handle"]) + bytes.fromhex(row["bindings"]["trigger"]["rawHex"])
        + bytes.fromhex(row["bindings"]["cargo"]["rawHex"])).hex()


def claims(s, *, encoded=0, target=0, carrier=0, recovery=0, owner=1):
    state = s["pokemonCombat"]["interactions"]["throwState"]
    state.update(targetMask=target, carrierMask=carrier, recoveringMask=recovery)
    state["targets"][owner] = encoded
    state["rawHex"] = (bytes(state["targets"]) + struct.pack("<3H", target, carrier, recovery)).hex()
    for row in s["pokemonCombat"]["interactions"]["carriers"]:
        slot = row["slot"]; n = state["targets"][slot]
        row["throw"] = dict(targetRaw=n, targetSlot=(n & 63)-1 if n else None, carried=bool(n & 128), windup=bool(n & 64),
            targeted=bool(target & (1 << slot)), carrier=bool(carrier & (1 << slot)), recovering=bool(recovery & (1 << slot)))


def sample(frame=20, *, foreign=False):
    actors = [actor(70, 0, 700, 391)] + [actor(74, slot, 740+slot, 409) for slot in (1,2,3)] + [actor(155,7,155,408)]
    if foreign: actors.append(actor(74,5,745,405))
    for a in actors:
        a["level"] = 3 if a["handle"]["slot"] == 5 else 100
        if a["species"] == 155: a["role"] = "FOLLOWER"
        a["behaviorFingerprint"] = a["handle"]["slot"] + 100
        a["matchedLayerMask"] = THROW_APPLICATION_BIT if a["species"] == 74 else 0
        a["engineObject"].update(pos_y=65536, unk88_y=0, facing=1, flags=1)
        a["sourceIdentity"] = dict(object=a["engineIdentity"]["pointer"], personality=a["subjectIdentity"], map_id=33,
            species=a["species"], form=0, level=a["level"], active=1, object_id=224+a["handle"]["slot"], encounter_generation=1)
    s = dict(frame=frame, actorFrame=frame, nativeCycle=frame+1000, fieldAvailable=True,
        observationBoundary="main-task-queue-completion", romSha256=SOURCE["romSha256"],
        context=dict(mapId=33,fieldEpoch=1,mapGeneration=1), fieldControl=dict(taskPointer=0,fieldPointer=0x02200000),
        player=dict(x=584,y=407), selector=dict(state=0,rawHeld=34,physicalPressed=34), actors=actors,
        nativeObservation=dict(error=None,coverageComplete=True,eventsDropped=0))
    rows = []; timers = []
    for a in actors:
        rows.append(dict(slot=a["handle"]["slot"],handle=deepcopy(a["handle"]),role=a["role"],available=True))
        timers.append(dict(slot=a["handle"]["slot"],handle=deepcopy(a["handle"]),sourceIdentity=deepcopy(a["sourceIdentity"]),
            movementCooldown=0,movementEmoteTimer=0,movementSpotState=0,movementActorControlMode=0))
    s["pokemonCombat"] = dict(available=True,frame=frame,nativeCycle=frame+1000,observationBoundary=s["observationBoundary"],
        identity=dict(romSha256=SOURCE["romSha256"],overlaySha256=SOURCE["overlaySha256"]),movementTimers=timers,targets=[],
        interactions=dict(schemaVersion=1,available=True,frame=frame,nativeCycle=frame+1000,observationBoundary=s["observationBoundary"],
            identity=dict(romSha256=SOURCE["romSha256"]),fieldSystem=0x02200000,carriers=rows,
            throwState=dict(targets=[0]*10,targetMask=0,carrierMask=0,recoveringMask=0)))
    for i,a in enumerate(actors): rebind(s,i,player=a["species"]==74)
    claims(s)
    return s


def meter(s):
    m = WildThrowSoakMeasurement(SOURCE); m.latest = sample(s["frame"]-1); m.context = deepcopy(s["context"])
    m.subjects = {name:select_current_actor(s,next(a for a in s["actors"] if a["species"]==species
        and (a["handle"]["slot"]==GEODUDES.index(name)+1 if name in GEODUDES else True))) for name,species,_,_ in SUBJECTS}
    m.window_start = s["frame"]
    return m


def health_checkpoint_case(leg):
    s = sample(20 + leg * LEG_FRAMES)
    m = meter(s); m.latest = deepcopy(s)
    m.setup_index = len(SETUP)
    m.action_index = next(i for i,a in enumerate(ACTIONS) if a[0] == f"health-check-{leg:03}")
    m.soak_frames = m.observed_frames = leg * LEG_FRAMES
    m.health_checkpoints = [dict(leg=n,soakFrames=n*LEG_FRAMES,playerHealth={})
        for n in CHECKPOINT_LEGS if n < leg]
    hp = dict(schemaVersion=1,identity=dict(romSha256=SOURCE["romSha256"],overlaySha256=SOURCE["overlaySha256"]),
        frame=s["frame"],nativeCycle=s["nativeCycle"],hp=80,savedHp=80,maxHp=100,recoveryPending=False,
        acceptedHits=1,restFrames=100,protectionFrames=0,lastDamage=20)
    row = dict(phase="observe",action=f"health-check-{leg:03}",command="player-health.observe",
        snapshot=deepcopy(s),receipt=dict(playerHealth=hp))
    return m,row


def query(s, slot, status=0, sequence=1):
    a = next(a for a in s["actors"] if a["handle"]["slot"] == slot)
    e = query_event(s,a,SOURCE["queryImage"],nodes=256,status=0)
    raw = bytearray.fromhex(e["data"]["resultHex"]); raw[104] = raw[138] = status
    e["data"].update(sequence=sequence,resultHex=raw.hex(),returnValue=status,resultStatus=status,
        status=("PENDING","REACHABLE","UNREACHABLE","INVALID","RESOURCE_LIMIT")[status])
    for stage in ("before","after"): e["data"][stage]["workspace"]["compatibility"]["required"] = 0
    return e


def blocked_release_case():
    previous = sample(20)
    carrier, target = previous["actors"][1], previous["actors"][0]
    carrier["matchedLayerMask"] |= THROW_RELEASE_BIT
    for a in (carrier, target):
        a["engineObject"].update(x=586, y=410, pos_x=(586 << 16)+32768, pos_z=(410 << 16)+32768)
    claims(previous, encoded=193, target=1, carrier=2)
    rebind(previous, 1, cargo=target)
    previous["pokemonCombat"]["movementTimers"][0]["movementActorControlMode"] = 1
    current = deepcopy(previous)
    current.update(frame=21, actorFrame=21, nativeCycle=1021)
    current["pokemonCombat"].update(frame=21, nativeCycle=1021)
    current["pokemonCombat"]["interactions"].update(frame=21, nativeCycle=1021)
    claims(current, recovery=2)
    rebind(current, 1, player=False)
    current["pokemonCombat"]["movementTimers"][0]["movementActorControlMode"] = 0
    current["pokemonCombat"]["movementTimers"][1].update(movementEmoteTimer=60, movementSpotState=3)
    target = current["actors"][0]
    value = motion(current, target, origin=(586,410), target=(586,408), reservation=167)
    raw = bytearray.fromhex(value["rawHex"])
    struct.pack_into("<H", raw, 6, target["behaviorFingerprint"] & 65535)
    struct.pack_into("<H", raw, 24, 11)
    raw[28:38] = bytes((0,2,16,0,0,0,0,1,0,0))
    current["pokemonCombat"]["targets"][0]["motion"] = decode_motion(bytes(raw))
    target["motionDuration"] = 11
    events = [native(target, 21, name, a, b, sequence) for name,a,b,sequence in (
        ("INTENT_CREATED",2,1,1838), ("CANDIDATE_REJECTED",0,1,1839),
        ("CONDITIONAL_RESOLVED",49529,72680497,1840), ("INTENT_CREATED",2,1,1841),
        ("PLAN_ACCEPTED",(586 << 16)|408,11,1842), ("MOTION_STARTED",2,11,1843))]
    events[1]["data"]["reason"] = "REJECTED_RESERVED"
    events[2]["data"]["reason"] = 51034
    m = meter(current)
    m.latest = deepcopy(previous)
    m.previous_state = deepcopy(previous["pokemonCombat"]["interactions"]["throwState"])
    own = dict(carrier=deepcopy(carrier["handle"]), cargo=deepcopy(target["handle"]),
        claim=18, pickup=19, launch=None, landed=None, cleanup=None, motion=None, recorder=None, credited=True)
    m.cycles[1] = own
    for a in (previous["actors"][1], target):
        raw = bytearray(216)
        if a["species"] == 74:
            raw[0] = 12; raw[36] = 2; raw[76] = 8
        else:
            raw[0] = 3; raw[12] = 2; raw[20] = 1; raw[21] = 6; raw[36] = 6; raw[48] = 30
        struct.pack_into("<II",raw,188,a["matchedLayerMask"],a["behaviorFingerprint"])
        m.profiles[a["behaviorFingerprint"]] = dict(resolved=True, fingerprint=a["behaviorFingerprint"],
            sourceSha256=SOURCE["profileSha256"], resultHex=raw.hex(), lanes=[raw[:80].hex(),raw[80:160].hex()])
    return m, current, events


def ordinary_carrier_damage_release(kind=1, carrier_hit=False):
    previous = sample(20); carrier, target = previous['actors'][1:3]
    claims(previous, encoded=195, target=4, carrier=2); rebind(previous, 1, cargo=target)
    previous['pokemonCombat']['movementTimers'][2]['movementActorControlMode'] = 1
    value = motion(previous, carrier, kind=kind, elapsed=4,
                   origin=(585,409), target=(586,409), reservation=229)
    raw = bytearray.fromhex(value['rawHex']); raw[3] = raw[28] = 3; raw[29] = 1; raw[34] = 0
    if kind == 2: raw[30] = 16
    previous['pokemonCombat']['targets'][0].update(motion=decode_motion(bytes(raw)),
        currentHp=16, hp=16, hpMirrorMatches=True, hitCount=0, lastDamage=0, knockbackPending=0)
    previous['pokemonCombat']['targets'].append(dict(handle=deepcopy(target['handle']),
        currentHp=100, hp=100, hpMirrorMatches=True, hitCount=0))
    carrier['laneId'] = 0
    current = deepcopy(previous); current.update(frame=21, actorFrame=21, nativeCycle=1021)
    current['pokemonCombat'].update(frame=21, nativeCycle=1021)
    current['pokemonCombat']['interactions'].update(frame=21, nativeCycle=1021)
    claims(current); rebind(current, 1, player=False)
    current['pokemonCombat']['movementTimers'][2]['movementActorControlMode'] = 0
    holder = current['pokemonCombat']['targets'][0]
    raw = bytearray.fromhex(holder['motion']['rawHex']); struct.pack_into('<H', raw, 40, 5)
    holder['motion'] = decode_motion(bytes(raw)); current['actors'][1]['motionElapsed'] = 5
    current['actors'][1]['engineObject']['pos_x'] += 8192
    if carrier_hit: holder.update(currentHp=8, hp=8, hitCount=1, lastDamage=8, knockbackPending=1)
    target = current['actors'][2]
    value = motion(current, target, origin=(585,409), target=(585,408), reservation=232)
    raw = bytearray.fromhex(value['rawHex']); raw[36] = raw[37] = 1
    current['pokemonCombat']['targets'][-1].update(motion=decode_motion(bytes(raw)),
        currentHp=80, hp=80, hpMirrorMatches=True, hitCount=1, lastDamage=20)
    events = [native(target, 21, name, a, b, sequence) for name, a, b, sequence in (
        ('INTENT_CREATED',2,1,210), ('PLAN_ACCEPTED',(585 << 16)|408,8,211), ('MOTION_STARTED',2,8,212))]
    m = meter(current); m.latest = deepcopy(previous)
    m.cycles[1] = dict(carrier=deepcopy(carrier['handle']), cargo=deepcopy(target['handle']),
        claim=18, pickup=19, launch=None, landed=None, cleanup=None, motion=None, recorder=None, credited=True)
    return m, current, events


def queued_carrier_hit_case():
    prior=sample(20); carrier,cargo=prior["actors"][1:3]; carrier["laneId"]=0
    claims(prior,encoded=131,target=4,carrier=2);rebind(prior,1,cargo=cargo)
    prior["pokemonCombat"]["movementTimers"][2]["movementActorControlMode"]=1
    motion(prior,carrier,phase="IDLE",elapsed=8,kind=1)
    carrier["motionKind"]="NONE"
    prior["pokemonCombat"]["targets"][0].update(currentHp=100,hp=100,hpMirrorMatches=True,hitCount=0,lastDamage=0,knockbackPending=0)
    m=meter(prior);m.latest=deepcopy(prior);m.previous_state=deepcopy(prior["pokemonCombat"]["interactions"]["throwState"])
    m.cycles[1]=dict(carrier=deepcopy(carrier["handle"]),cargo=deepcopy(cargo["handle"]),claim=18,pickup=19,
        launch=None,landed=None,cleanup=None,motion=None,recorder=None,credited=True)
    frames=[]
    for frame in range(21,31):
        current=deepcopy(prior);current.update(frame=frame,actorFrame=frame,nativeCycle=frame+1000)
        current["pokemonCombat"].update(frame=frame,nativeCycle=frame+1000)
        current["pokemonCombat"]["interactions"].update(frame=frame,nativeCycle=frame+1000)
        holder=current["actors"][1];forced=frame>=29
        value=motion(current,holder,kind=2 if forced else 1,elapsed=frame-29 if forced else frame-21,
            commit=5 if forced else 4,origin=(586,409) if forced else (585,409),
            target=(586,408) if forced else (586,409),reservation=892 if forced else 887)
        raw=bytearray.fromhex(value["rawHex"]);raw[3]=3;raw[28]=0 if forced else 3;raw[29]=1;raw[34]=0
        raw[35]=1;raw[36]=int(forced);raw[37]=int(forced);raw[50]=0
        hp=current["pokemonCombat"]["targets"][0]
        hp.update(motion=decode_motion(bytes(raw)),currentHp=80,hp=80,hpMirrorMatches=True,
            hitCount=1,lastDamage=20,knockbackPending=0 if forced else 1,knockbackOptions=5,knockbackDirection=0)
        if forced:
            holder["logical"]=dict(x=586,y=409)
            holder["engineObject"].update(pos_x=(586<<16)+32768,pos_z=(409<<16)+32768)
        events=[]
        if frame==21:
            events=[native(holder,frame,event,a,b,n) for event,a,b,n in (
                ("INTENT_CREATED",1,1,100),("PLAN_ACCEPTED",(586<<16)|409,8,101),("MOTION_STARTED",1,8,102))]
        elif frame==29:
            events=[native(holder,frame,event,a,b,n) for event,a,b,n in (
                ("LOGICAL_COMMIT",5,1,200),("MOTION_FINISHED",5,1,201),("CONTROL_RETURNED",0,5,202),
                ("INTENT_CREATED",2,1,203),("PLAN_ACCEPTED",(586<<16)|408,8,204),("MOTION_STARTED",2,8,205))]
        frames.append((current,events))
    return m,frames


def fainted_flight_case():
    prior = sample(20, foreign=True); cargo = prior["actors"][-1]; carrier = prior["actors"][3]
    cargo["laneId"] = 0
    value = motion(prior, cargo, elapsed=7, origin=(583,399), target=(586,402), reservation=274)
    raw = bytearray.fromhex(value["rawHex"])
    struct.pack_into("<H", raw, 24, 12); struct.pack_into("<H", raw, 40, 11); raw[3] = raw[28] = 3; raw[29] = 6; raw[30] = 16; raw[34] = 0
    raw[35] = 1
    health = prior["pokemonCombat"]["targets"][-1]
    health.update(motion=decode_motion(bytes(raw)), currentHp=0, hp=0, hpMirrorMatches=True,
        initialized=1, hpSource="wild-resident", personality=cargo["subjectIdentity"], species=74,
        form=0, level=3, mapId=33, mapGeneration=1, encounterGeneration=1, hitCount=2, lastDamage=8)
    cargo["motionDuration"] = 12; cargo["motionElapsed"] = 11
    prior["pokemonCombat"]["movementTimers"][-1]["movementActorControlMode"] = 1
    prior["pokemonCombat"]["movementTimers"][3].update(movementEmoteTimer=60, movementSpotState=3)
    claims(prior, target=1 << 5, recovery=1 << 3); rebind(prior, 3, player=False)
    start = deepcopy(prior); start.update(frame=9, actorFrame=9, nativeCycle=1009)
    started = start["actors"][-1]; started["motionElapsed"] = 0
    initial = deepcopy(health["motion"]); initial["elapsed"] = 0
    m = meter(prior); m.latest = deepcopy(prior); m.previous_state = deepcopy(prior["pokemonCombat"]["interactions"]["throwState"])
    accepted = m._start(start, started, initial, [native(started,9,"MOTION_STARTED",2,12,100)["data"]])
    m.cycles[3] = dict(carrier=deepcopy(carrier["handle"]), cargo=deepcopy(cargo["handle"]),
        claim=5, pickup=8, launch=9, landed=None, cleanup=None, motion=accepted,
        recorder=MotionRecorder(), credited=True)
    current = deepcopy(prior); current.update(frame=21, actorFrame=21, nativeCycle=1021)
    current["pokemonCombat"].update(frame=21, nativeCycle=1021)
    current["pokemonCombat"]["interactions"].update(frame=21, nativeCycle=1021)
    shell = current["actors"][-1]
    shell.update(identityVerified=False, motionKind="NONE", motionPhase="IDLE", motionElapsed=12,
        reservationId=0, commitSequence=5, logical=dict(x=586,y=402))
    shell.pop("engineObject")
    shell["engineIdentity"].update(pointer=0, in_manager=False, active=False,
        id_lookup=dict(status="complete", eligible_count=0, first_active_pointer=0, matching_objects=[]))
    shell["sourceIdentity"].update(object=0, active=0, personality=0, species=0, form=0, level=0, map_id=1)
    for key in ("targets", "movementTimers"):
        current["pokemonCombat"][key] = [r for r in current["pokemonCombat"][key] if r["handle"] != cargo["handle"]]
    current["pokemonCombat"]["interactions"]["carriers"].pop()
    claims(current, recovery=1 << 3)
    events = [native(shell,21,event,a,b,sequence) for event,a,b,sequence in (
        ("LOGICAL_COMMIT",5,2,200),("MOTION_FINISHED",5,2,201),("CONTROL_RETURNED",0,5,202))]
    for e in events: e["data"]["traceFieldEpoch"] = 1
    next_sample = deepcopy(current); next_sample.update(frame=22, actorFrame=22, nativeCycle=1022)
    next_sample["pokemonCombat"].update(frame=22, nativeCycle=1022)
    next_sample["pokemonCombat"]["interactions"].update(frame=22, nativeCycle=1022)
    next_sample["actors"].pop()
    detach = native(shell,21,"ACTOR_DETACHED",1,cargo["subjectIdentity"],203)
    detach["frame"] = 22; detach["data"]["traceFieldEpoch"] = 1
    return m, current, events, next_sample, [detach]


def primary_faint_case():
    prior=sample(20)
    for a in prior["actors"]:
        value=motion(prior,a,phase="IDLE",elapsed=8,kind=1)
        row=prior["pokemonCombat"]["targets"][-1]
        row.update(personality=a["subjectIdentity"],species=a["species"],form=0,level=100,
            mapId=33,mapGeneration=1,encounterGeneration=1,initialized=1,hpSource="wild-resident",
            currentHp=100,hp=100,maxHp=100,actualMaxHp=100,hpMirrorMatches=True,hitCount=0,lastDamage=0,knockbackPending=0)
        a["motionKind"]="NONE"
    carrier=prior["actors"][2];cargo=prior["actors"][1]
    saved=deepcopy(next(r for r in prior["pokemonCombat"]["targets"] if r["handle"]==carrier["handle"]))
    value=motion(prior,carrier,elapsed=6,kind=1,origin=(586,399),target=(586,400),reservation=994)
    raw=bytearray.fromhex(value["rawHex"]);struct.pack_into("<H",raw,24,7);raw[29]=1;raw[34]=0
    hp=next(r for r in prior["pokemonCombat"]["targets"] if r["handle"]==carrier["handle"])
    hp.update(saved,motion=decode_motion(bytes(raw)),currentHp=1,hp=1,hitCount=9,lastDamage=20)
    carrier["motionDuration"]=7
    current=deepcopy(prior)
    def stamp(s,frame):
        s.update(frame=frame,actorFrame=frame,nativeCycle=frame+1000)
        s["pokemonCombat"].update(frame=frame,nativeCycle=frame+1000)
        s["pokemonCombat"]["interactions"].update(frame=frame,nativeCycle=frame+1000)
    stamp(current,21)
    dying=current["actors"][2];held=current["actors"][1]
    dying.update(motionKind="NONE",motionPhase="IDLE",motionElapsed=7,reservationId=0,commitSequence=5,
        logical=dict(x=586,y=400))
    dying["engineObject"].update(x=586,y=400,pos_x=(586<<16)+32768,pos_z=(400<<16)+32768)
    hp=next(r for r in current["pokemonCombat"]["targets"] if r["handle"]==dying["handle"])
    raw=bytearray.fromhex(hp["motion"]["rawHex"]);struct.pack_into("<H",raw,40,7);raw[50]=1;raw[48]=0
    hp.update(motion=decode_motion(bytes(raw)),currentHp=0,hp=0,hitCount=10,lastDamage=1)
    held["engineObject"].update(x=586,y=400,pos_x=(586<<16)+32768,pos_z=(400<<16)+32768,unk88_y=32768,face_y=32768)
    claims(current,encoded=130,target=2,carrier=4,owner=2);rebind(current,2,cargo=held)
    current["pokemonCombat"]["movementTimers"][1]["movementActorControlMode"]=1
    events=[native(dying,21,event,a,b,n) for event,a,b,n in (
        ("LOGICAL_COMMIT",5,1,200),("MOTION_FINISHED",5,1,201),("CONTROL_RETURNED",0,5,202))]
    for e in events:e["data"]["traceFieldEpoch"]=1
    shell=deepcopy(current);stamp(shell,22)
    missing=shell["actors"][2];missing.pop("engineObject");missing["identityVerified"]=False
    missing["engineIdentity"].update(pointer=0,in_manager=False,active=False,
        id_lookup=dict(status="complete",eligible_count=0,first_active_pointer=0,matching_objects=[]))
    missing["sourceIdentity"].update(object=0,active=0,personality=0,species=0,form=0,level=0,map_id=1)
    for key in ("targets","movementTimers"):
        shell["pokemonCombat"][key]=[r for r in shell["pokemonCombat"][key] if r["handle"]!=dying["handle"]]
    shell["pokemonCombat"]["interactions"]["carriers"].pop(2)
    claims(shell,owner=2)
    shell["pokemonCombat"]["movementTimers"][1]["movementActorControlMode"]=0
    shell["actors"][1]["engineObject"].update(unk88_y=0,face_y=0)
    nxt=deepcopy(shell);stamp(nxt,23);nxt["actors"].pop(2)
    detach=native(dying,22,"ACTOR_DETACHED",1,dying["subjectIdentity"],203)
    detach["frame"]=23;detach["data"]["traceFieldEpoch"]=1
    m=meter(prior);m.latest=deepcopy(prior);m.previous_state=deepcopy(prior["pokemonCombat"]["interactions"]["throwState"])
    return m,current,events,shell,nxt,[detach]


class WildThrowSoakTests(unittest.TestCase):
    def test_exact_five_hp_reads_do_not_advance_or_replace_final_receipt(self):
        for leg in CHECKPOINT_LEGS:
            m,row = health_checkpoint_case(leg)
            m.health_before = dict(hp=100); m.health_after = None
            before = (deepcopy(m.latest),m.soak_frames,m.observed_frames,m.action_index)
            r = m.observe_record(row)
            self.assertEqual(r["failures"],[])
            self.assertEqual((m.latest,m.soak_frames,m.observed_frames),before[:3])
            self.assertEqual(m.action_index,before[3]+1)
            self.assertEqual(m.health_before,dict(hp=100)); self.assertIsNone(m.health_after)
            self.assertEqual(r["playerCheckpoints"][-1],dict(leg=leg,soakFrames=leg*LEG_FRAMES,
                playerHealth=row["receipt"]["playerHealth"]))
            row["receipt"]["playerHealth"]["hp"]=0
            self.assertEqual(r["playerCheckpoints"][-1]["playerHealth"]["hp"],80)
            self.assertEqual(r["completedThrows"],[])

    def test_hp_checkpoint_rejects_false_health_clock_or_action_boundary(self):
        faults=("hp-zero","saved-hp","max-hp","recovery","frame","cycle","rom","overlay",
            "snapshot-frame","snapshot-cycle","snapshot-player","snapshot-actor","snapshot-combat",
            "soak-count","observed-count","missing-prior-check","duplicate-check","wrong-action","wrong-command")
        for fault in faults:
            m,row = health_checkpoint_case(80); hp=row["receipt"]["playerHealth"]
            if fault=="hp-zero":hp["hp"]=hp["savedHp"]=0
            elif fault=="saved-hp":hp["savedHp"]-=1
            elif fault=="max-hp":hp["maxHp"]+=1
            elif fault=="recovery":hp["recoveryPending"]=True
            elif fault=="frame":hp["frame"]-=1
            elif fault=="cycle":hp["nativeCycle"]-=1
            elif fault in ("rom","overlay"):hp["identity"][fault+"Sha256"]="e"*64
            elif fault=="snapshot-frame":row["snapshot"]["frame"]+=1
            elif fault=="snapshot-cycle":row["snapshot"]["nativeCycle"]+=1
            elif fault=="snapshot-player":row["snapshot"]["player"]["x"]+=1
            elif fault=="snapshot-actor":row["snapshot"]["actors"][0]["subjectIdentity"]+=1
            elif fault=="snapshot-combat":row["snapshot"]["pokemonCombat"]["frame"]+=1
            elif fault=="soak-count":m.soak_frames-=1
            elif fault=="observed-count":m.observed_frames-=1
            elif fault=="missing-prior-check":m.health_checkpoints=[]
            elif fault=="duplicate-check":m.health_checkpoints.append(dict(leg=80,soakFrames=1920,playerHealth={}))
            elif fault=="wrong-action":row["action"]="health-check-040"
            else:row["command"]="player-health.repair"
            with self.subTest(fault=fault):
                self.assertTrue(m.observe_record(row)["failures"])
                self.assertIsNone(m.health_after)

    def test_primary_faint_requires_ground_release_then_exact_next_detach_without_credit(self):
        m,hit,events,shell,nxt,detach=primary_faint_case()
        m._primary_lifetimes(hit,events);m.latest=deepcopy(hit)
        m.cycles[2]=dict(carrier=deepcopy(hit["actors"][2]["handle"]),cargo=deepcopy(hit["actors"][1]["handle"]),
            claim=20,pickup=21,launch=None,landed=None,credited=False)
        m._primary_lifetimes(shell,[])
        self.assertNotIn(2,m.cycles);self.assertEqual(m.completed,[])
        self.assertNotIn("geodude-b",m._actors(shell))
        self.assertIsNone(m.primary_retirements["geodude-b"]["detach"])
        m.soak_frames=SOAK_FRAMES;self.assertFalse(m.stage("window-complete"))
        m.latest=deepcopy(shell);m._primary_lifetimes(nxt,detach)
        self.assertIsNotNone(m.primary_retirements["geodude-b"]["detach"])
        self.assertEqual(m.primary_current_frames["geodude-b"],0)
        self.assertEqual(m.primary_healthy_frames["geodude-b"],0)
        self.assertEqual(m.primary_healthy_frames["geodude-a"],3)
        self.assertEqual(m.completed,[]);self.assertEqual(m.recovery_pickups,[])

    def test_primary_faint_rejects_unproved_hit_terminal_source_or_held_release(self):
        faults=("positive-hp","mirror","owner","clock","hit-count","damage","pending","plan","token",
            "early-end","missing-commit","missing-finish","missing-control","terminal-order","terminal-owner",
            "new-start","source","source-map","lookup","native-hp","native-timer","native-binding",
            "retained-claim","held","cargo-owner","cargo-source","cargo-base","cargo-elevated","cargo-position")
        shell_faults=faults[16:]
        for fault in faults:
            m,hit,events,shell,_,_=primary_faint_case()
            hp=next(r for r in hit["pokemonCombat"]["targets"] if r["handle"]==hit["actors"][2]["handle"])
            if fault in shell_faults:m._primary_lifetimes(hit,events);m.latest=deepcopy(hit)
            if fault=="positive-hp":hp.update(currentHp=1,hp=1)
            elif fault=="mirror":hp["hpMirrorMatches"]=False
            elif fault=="owner":hp["personality"]+=1
            elif fault=="clock":hit["pokemonCombat"]["frame"]-=1
            elif fault=="hit-count":hp["hitCount"]-=1
            elif fault=="damage":hp["lastDamage"]=20
            elif fault=="pending":hp["knockbackPending"]=1
            elif fault in ("plan","token"):
                raw=bytearray.fromhex(hp["motion"]["rawHex"])
                struct.pack_into("<h" if fault=="plan" else "<H",raw,12 if fault=="plan" else 26,587 if fault=="plan" else 995)
                hp["motion"]=decode_motion(bytes(raw))
            elif fault=="early-end":hit["actors"][2]["motionElapsed"]-=1
            elif fault.startswith("missing-"):events.pop({"missing-commit":0,"missing-finish":1,"missing-control":2}[fault])
            elif fault=="terminal-order":events[1]["data"]["sequence"]=199
            elif fault=="terminal-owner":events[1]["data"]["actor"]["generation"]+=1
            elif fault=="new-start":events.append(native(hit["actors"][2],21,"MOTION_STARTED",1,7,204))
            elif fault=="source":shell["actors"][2]["sourceIdentity"]["object"]=1
            elif fault=="source-map":shell["actors"][2]["sourceIdentity"]["map_id"]=33
            elif fault=="lookup":shell["actors"][2]["engineIdentity"]["id_lookup"]["eligible_count"]=1
            elif fault=="native-hp":shell["pokemonCombat"]["targets"].append(deepcopy(hp))
            elif fault=="native-timer":shell["pokemonCombat"]["movementTimers"].append(deepcopy(m.latest["pokemonCombat"]["movementTimers"][2]))
            elif fault=="native-binding":shell["pokemonCombat"]["interactions"]["carriers"].append(deepcopy(m.latest["pokemonCombat"]["interactions"]["carriers"][2]))
            elif fault=="retained-claim":claims(shell,encoded=130,target=2,carrier=4,owner=2)
            elif fault=="held":shell["pokemonCombat"]["movementTimers"][1]["movementActorControlMode"]=1
            elif fault=="cargo-owner":shell["actors"][1]["handle"]["generation"]+=1
            elif fault=="cargo-source":shell["actors"][1]["sourceIdentity"]["personality"]+=1
            elif fault=="cargo-base":shell["actors"][1]["engineObject"]["pos_y"]+=4096
            elif fault=="cargo-elevated":shell["actors"][1]["engineObject"]["unk88_y"]=32768
            else:shell["actors"][1]["engineObject"]["pos_x"]+=65536
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                if fault=="positive-hp":
                    m._primary_lifetimes(hit,events);m.latest=deepcopy(hit);m._primary_lifetimes(shell,[])
                else:
                    m._primary_lifetimes(shell,[]) if fault in shell_faults else m._primary_lifetimes(hit,events)

    def test_primary_retirement_requires_detach_and_never_credits_reused_slot(self):
        for fault in ("missing","owner","personality","clock","late","order","old-public","claim","held-row"):
            m,hit,events,shell,nxt,detach=primary_faint_case()
            m._primary_lifetimes(hit,events);m.latest=deepcopy(hit)
            m._primary_lifetimes(shell,[]);m.latest=deepcopy(shell)
            if fault=="missing":detach=[]
            elif fault=="owner":detach[0]["data"]["actor"]["generation"]+=1
            elif fault=="personality":detach[0]["data"]["valueB"]+=1
            elif fault=="clock":detach[0]["data"]["actorFrame"]+=1
            elif fault=="late":nxt["frame"]+=1
            elif fault=="order":detach[0]["data"]["sequence"]=199
            elif fault=="old-public":nxt["actors"].append(deepcopy(shell["actors"][2]))
            elif fault=="claim":claims(nxt,target=4)
            else:nxt["pokemonCombat"]["movementTimers"].append(deepcopy(hit["pokemonCombat"]["movementTimers"][2]))
            with self.subTest(fault=fault),self.assertRaises(ValueError):m._primary_lifetimes(nxt,detach)
        m,hit,events,shell,nxt,detach=primary_faint_case()
        for s,es in ((hit,events),(shell,[]),(nxt,detach)):
            m._primary_lifetimes(s,es);m.latest=deepcopy(s)
        replacement=deepcopy(hit["actors"][2]);replacement["handle"]["generation"]+=1
        replacement["handle"]["value"]+=65536;replacement["subjectIdentity"]+=1
        nxt["actors"].append(replacement)
        m._primary_lifetimes(nxt,[])
        self.assertNotIn("geodude-b",m._actors(nxt));self.assertEqual(m.primary_current_frames["geodude-b"],0)
        # A new native generation may use the old slot after exact DETACH.
        claims(nxt,encoded=130,target=2,carrier=4,owner=2)
        m._primary_lifetimes(nxt,[])
        self.assertEqual(m.primary_current_frames["geodude-b"],0)
        nxt["actors"].pop()
        with self.assertRaisesRegex(ValueError,"distinct current owner"):m._primary_lifetimes(nxt,[])
        nxt["actors"].append(deepcopy(hit["actors"][2]))
        with self.assertRaisesRegex(ValueError,"old full handle"):m._primary_lifetimes(nxt,[])

    def test_two_original_primary_survivors_are_required_for_the_whole_window(self):
        m,hit,events,shell,nxt,detach=primary_faint_case()
        # Initial primary names do not select a species-specific exit rule.
        m.subjects["geodude-a"],m.subjects["geodude-b"]=m.subjects["geodude-b"],m.subjects["geodude-a"]
        for s,es in ((hit,events),(shell,[]),(nxt,detach)):
            m._primary_lifetimes(s,es);m.latest=deepcopy(s)
        self.assertIn("geodude-a",m.primary_retirements)
        m.soak_frames=3
        self.assertEqual(m.result()["survivors"],["geodude-b","geodude-c"])
        m.primary_healthy_frames["geodude-c"]-=1
        self.assertEqual(m.result()["survivors"],["geodude-b"])
        m,hit,events,_,_,_=primary_faint_case()
        a=hit["actors"][3];hp=next(r for r in hit["pokemonCombat"]["targets"] if r["handle"]==a["handle"])
        hp.update(hp=0,currentHp=0,hitCount=1,lastDamage=100)
        with self.assertRaisesRegex(ValueError,"two original primaries"):m._primary_lifetimes(hit,events)

    def test_primary_faint_aborts_landed_recovery_but_preserves_only_earlier_completed_throws(self):
        for late_credit in (False,True):
            m,hit,events,shell,_,_=primary_faint_case()
            m._primary_lifetimes(hit,events);m.latest=deepcopy(hit)
            handle=deepcopy(hit["actors"][2]["handle"]);cargo=deepcopy(hit["actors"][1]["handle"])
            m.cycles[2]=dict(carrier=handle,cargo=cargo,landed=19,cleanup=None,credited=False)
            m.completed=[dict(carrier=deepcopy(handle),cargo=deepcopy(cargo),landed=18,cleanup=21 if late_credit else 19)]
            if late_credit:
                with self.assertRaisesRegex(ValueError,"later completed Throw"):m._primary_lifetimes(shell,[])
            else:
                m._primary_lifetimes(shell,[])
                self.assertEqual(m.cycles,{})
                self.assertEqual(len(m.completed),1);self.assertEqual(m.completed[0]["cleanup"],19)

    def test_controller_retirement_requires_this_exact_measured_primary_shell_or_detach(self):
        from tools.overworld.control import _distance_subject_retired
        m,hit,events,shell,nxt,detach=primary_faint_case()
        subject=deepcopy(m.subjects["geodude-b"])
        current=SimpleNamespace(measurements={KIND:m})
        self.assertFalse(m.primary_subject_retired(hit,subject))
        m._primary_lifetimes(hit,events);m.latest=deepcopy(hit)
        self.assertFalse(m.primary_subject_retired(hit,subject))
        m._primary_lifetimes(shell,[]);m.latest=deepcopy(shell)
        self.assertTrue(m.primary_subject_retired(shell,subject))
        self.assertTrue(_distance_subject_retired(shell,current,subject))
        self.assertFalse(m.primary_subject_retired(nxt,subject))
        for fault in ("early","subject","generation","context","boundary","clock","shell","failed","record"):
            bad=deepcopy(shell);who=deepcopy(subject);copy=deepcopy(m)
            if fault=="early":bad["frame"]-=1
            elif fault=="subject":who["subjectIdentity"]+=1
            elif fault=="generation":who["handle"]["generation"]+=1
            elif fault=="context":bad["context"]["fieldEpoch"]+=1
            elif fault=="boundary":bad["observationBoundary"]="not-complete"
            elif fault=="clock":bad["nativeCycle"]-=1
            elif fault=="shell":bad["actors"][2]["sourceIdentity"]["object"]=1
            elif fault=="failed":copy.failures.append("unproved")
            else:copy.primary_retirements={}
            with self.subTest(fault=fault):
                self.assertFalse(_distance_subject_retired(bad,SimpleNamespace(measurements={KIND:copy}),who))
        self.assertFalse(_distance_subject_retired(shell,SimpleNamespace(measurements={"other":m}),subject))
        m._primary_lifetimes(nxt,detach);m.latest=deepcopy(nxt)
        self.assertTrue(_distance_subject_retired(nxt,current,subject))
        m.primary_retirements["geodude-b"]["detach"]["data"]["valueB"]+=1
        self.assertFalse(m.primary_subject_retired(nxt,subject))

    def test_carrier_hit_waits_only_for_its_exact_accepted_ordinary_primitive(self):
        m,frames=queued_carrier_hit_case()
        for s,events in frames:
            state,rows,timers,actors=ground_state(s,SOURCE)
            m._cycles(s,events,m._actors(s),state,rows,timers,actors)
            m.latest=deepcopy(s);m.previous_state=deepcopy(state)
            if s["frame"]==28:
                m.soak_frames=SOAK_FRAMES
                self.assertFalse(m.stage("window-complete"))
        self.assertTrue(m.stage("window-complete"))
        own=m.cycles[1];queue=own["carrierHit"]["queue"]
        self.assertEqual(queue["deadline"],29);self.assertEqual(queue["completed"],29)
        self.assertEqual(queue["motion"]["returnFrame"],29)
        self.assertEqual(own["carrierDamage"]["motion"]["plan"]["reservationId"],892)
        self.assertEqual(own["carrierDamage"]["motion"]["frame"],29)
        self.assertIsNone(own["launch"]);self.assertIsNone(own["landed"])
        self.assertEqual(m.completed,[])

    def test_queued_holder_may_release_only_after_exact_fresh_cargo_damage(self):
        def run(fault=None):
            m,frames=queued_carrier_hit_case()
            def cargo_hp(s):
                a=s["actors"][2]
                s["pokemonCombat"]["targets"].append(dict(handle=deepcopy(a["handle"]),role=a["role"],
                    currentHp=100,hp=100,hpMirrorMatches=True,hitCount=0,lastDamage=0))
            cargo_hp(m.latest)
            for s,events in frames[:2]:
                cargo_hp(s);state,rows,timers,actors=ground_state(s,SOURCE)
                m._cycles(s,events,m._actors(s),state,rows,timers,actors)
                m.latest=deepcopy(s);m.previous_state=deepcopy(state)
            s,events=frames[2];cargo=s["actors"][2]
            claims(s);rebind(s,1,player=False);s["pokemonCombat"]["movementTimers"][2]["movementActorControlMode"]=0
            value=motion(s,cargo,origin=(585,409),target=(585,408),reservation=893)
            raw=bytearray.fromhex(value["rawHex"]);raw[36]=raw[37]=1
            hp=s["pokemonCombat"]["targets"][-1]
            hp.update(motion=decode_motion(bytes(raw)),currentHp=80,hp=80,hpMirrorMatches=True,hitCount=1,lastDamage=20)
            events=[native(cargo,23,event,a,b,n) for event,a,b,n in (
                ("PLAN_ACCEPTED",(585<<16)|408,8,160),("MOTION_STARTED",2,8,161))]
            if fault=="no-hit":hp["hitCount"]=0
            elif fault=="no-mirror":hp["hpMirrorMatches"]=False
            elif fault=="not-forced":raw[37]=0;hp["motion"]=decode_motion(bytes(raw))
            elif fault=="retained-claim":claims(s,target=4)
            elif fault=="held":s["pokemonCombat"]["movementTimers"][2]["movementActorControlMode"]=1
            elif fault=="no-start":events.pop()
            elif fault=="carrier-replaced":s["actors"][1]["reservationId"]+=1
            state,rows,timers,actors=ground_state(s,SOURCE)
            m._cycles(s,events,m._actors(s),state,rows,timers,actors)
            return m
        m=run();self.assertEqual(m.cycles,{});self.assertEqual(m.completed,[])
        for fault in ("no-hit","no-mirror","not-forced","retained-claim","held","no-start","carrier-replaced"):
            with self.subTest(fault=fault),self.assertRaises(ValueError):run(fault)

    def test_queued_carrier_hit_rejects_changed_wait_or_unordered_forced_start(self):
        faults=("hp","hp-mirror","hit-count","pending","missing-hp","released","direction","options","owner","cargo-owner","source",
            "claim","held","carrier-control","context","elapsed","plan","token","new-intent","new-accepted","new-start",
            "canceled","early-forced","missing-commit","missing-finish","missing-control","wrong-terminal-order",
            "missing-forced-plan","wrong-forced-plan","missing-forced-start","retained-pending","late-forced")
        for fault in faults:
            m,frames=queued_carrier_hit_case()
            terminal=fault in ("missing-commit","missing-finish","missing-control","wrong-terminal-order",
                "missing-forced-plan","wrong-forced-plan","missing-forced-start","retained-pending","late-forced")
            bad_index=8 if terminal else 2
            for index,(s,events) in enumerate(frames):
                if index==bad_index:
                    holder=s["actors"][1];hp=s["pokemonCombat"]["targets"][0]
                    if fault=="hp":hp.update(currentHp=79,hp=79)
                    elif fault=="hp-mirror":hp["hpMirrorMatches"]=False
                    elif fault=="hit-count":hp["hitCount"]+=1
                    elif fault=="pending":hp["knockbackPending"]=0
                    elif fault=="missing-hp":s["pokemonCombat"]["targets"].clear()
                    elif fault=="released":claims(s)
                    elif fault=="direction":hp["knockbackDirection"]=1
                    elif fault=="options":hp["knockbackOptions"]=6
                    elif fault=="owner":holder["handle"]["generation"]+=1
                    elif fault=="cargo-owner":s["actors"][2]["handle"]["generation"]+=1
                    elif fault=="source":holder["sourceIdentity"]["personality"]+=1
                    elif fault=="claim":claims(s,encoded=132,target=4,carrier=2)
                    elif fault=="held":s["pokemonCombat"]["movementTimers"][2]["movementActorControlMode"]=0
                    elif fault=="carrier-control":s["pokemonCombat"]["movementTimers"][1]["movementActorControlMode"]=1
                    elif fault=="context":s["context"]["mapGeneration"]+=1
                    elif fault in ("elapsed","plan","token","early-forced"):
                        raw=bytearray.fromhex(hp["motion"]["rawHex"])
                        if fault=="elapsed":struct.pack_into("<H",raw,40,3);holder["motionElapsed"]=3
                        elif fault=="plan":struct.pack_into("<h",raw,12,587)
                        elif fault=="token":struct.pack_into("<H",raw,26,888)
                        else:raw[2]=2;raw[37]=1;hp["knockbackPending"]=0
                        hp["motion"]=decode_motion(bytes(raw))
                    elif fault in ("new-intent","new-accepted","new-start","canceled"):
                        event={"new-intent":"INTENT_CREATED","new-accepted":"PLAN_ACCEPTED","new-start":"MOTION_STARTED","canceled":"MOTION_CANCELED"}[fault]
                        events.append(native(holder,s["frame"],event,1,8,150))
                    elif fault.startswith("missing-"):
                        event={"missing-commit":"LOGICAL_COMMIT","missing-finish":"MOTION_FINISHED","missing-control":"CONTROL_RETURNED",
                            "missing-forced-plan":"PLAN_ACCEPTED","missing-forced-start":"MOTION_STARTED"}[fault]
                        events[:]=[e for e in events if e["data"]["event"]!=event]
                    elif fault=="wrong-terminal-order":events[1]["data"]["sequence"]=199
                    elif fault=="wrong-forced-plan":events[-2]["data"]["valueB"]+=1
                    elif fault=="retained-pending":hp["knockbackPending"]=1
                    else:s["frame"]+=1;s["actorFrame"]+=1
                    with self.subTest(fault=fault),self.assertRaises(ValueError):
                        state,rows,timers,actors=ground_state(s,SOURCE)
                        m._cycles(s,events,m._actors(s),state,rows,timers,actors)
                    break
                state,rows,timers,actors=ground_state(s,SOURCE)
                m._cycles(s,events,m._actors(s),state,rows,timers,actors)
                m.latest=deepcopy(s);m.previous_state=deepcopy(state)

    def test_fainted_owned_flight_requires_next_frame_detach_and_earns_no_credit(self):
        m,s,events,next_sample,detach = fainted_flight_case()
        state,rows,timers,actors = ground_state(s,SOURCE)
        m._cycles(s,events,m._actors(s),state,rows,timers,actors)
        self.assertIn(3,m.cycles)
        self.assertEqual(m.completed,[])
        self.assertIsNone(m.cycles[3]["landed"])
        m.soak_frames = SOAK_FRAMES; m.previous_state = deepcopy(state)
        self.assertFalse(m.stage("window-complete"))
        m.latest = deepcopy(s)
        state,rows,timers,actors = ground_state(next_sample,SOURCE)
        m._finish_faint_retirements(next_sample,detach,state)
        self.assertNotIn(3,m.cycles)
        self.assertEqual(m.completed,[])
        self.assertEqual(m.recovery_pickups,[])
        self.assertEqual(len(m.fainted_flight_retirements),1)
        self.assertIsNotNone(m.fainted_flight_retirements[0]["detach"])
        self.assertTrue(m.stage("window-complete"))

    def test_unproved_missing_engine_or_faint_terminal_is_rejected(self):
        faults=("hp-positive","hp-mirror","hp-source","hp-clock","hp-owner","prior-source","stale-owner","context","plan","token",
            "early-end","prior-held","prior-claim","prior-commit","missing-commit","missing-finish","missing-control",
            "wrong-order","wrong-owner","wrong-clock","wrong-reason","wrong-commit","wrong-kind","new-start",
            "source","source-map","source-generation","native-lookup","terminal-token","terminal-target",
            "terminal-commit","live-engine","native-hp","held-control","target-row","retained-claim","retained-binding")
        for fault in faults:
            m,s,events,_,_ = fainted_flight_case(); prior=m.latest["actors"][-1]; target=s["actors"][-1]
            hp=m.latest["pokemonCombat"]["targets"][-1]
            if fault=="hp-positive": hp.update(currentHp=1,hp=1)
            elif fault=="hp-mirror": hp["hpMirrorMatches"]=False
            elif fault=="hp-source": hp["hpSource"]="party"
            elif fault=="hp-clock": m.latest["pokemonCombat"]["frame"]-=1
            elif fault=="hp-owner": hp["personality"]+=1
            elif fault=="prior-source": prior["sourceIdentity"]["personality"]+=1
            elif fault=="stale-owner": prior["identityVerified"]=False
            elif fault=="context": s["context"]["mapGeneration"]+=1
            elif fault in ("plan","token","prior-commit"):
                raw=bytearray.fromhex(hp["motion"]["rawHex"])
                if fault=="plan": struct.pack_into("<h",raw,12,587)
                elif fault=="token": struct.pack_into("<H",raw,26,275)
                else: raw[50]=1
                hp["motion"]=decode_motion(bytes(raw))
            elif fault=="early-end": target["motionElapsed"]-=1
            elif fault=="prior-held": m.latest["pokemonCombat"]["movementTimers"][-1]["movementActorControlMode"]=0
            elif fault=="prior-claim": m.previous_state["targetMask"]=0
            elif fault.startswith("missing-"): events.pop({"missing-commit":0,"missing-finish":1,"missing-control":2}[fault])
            elif fault=="wrong-order": events[1]["data"]["sequence"]=199
            elif fault=="wrong-owner": events[1]["data"]["actor"]["generation"]+=1
            elif fault=="wrong-clock": events[1]["data"]["frame"]-=1
            elif fault=="wrong-reason": events[1]["data"]["reason"]="REJECTED_RESERVED"
            elif fault=="wrong-commit": events[0]["data"]["valueA"]+=1
            elif fault=="wrong-kind": events[0]["data"]["valueB"]=1
            elif fault=="new-start": events.append(native(target,21,"MOTION_STARTED",2,12,203))
            elif fault=="source": target["sourceIdentity"]["object"]=1
            elif fault=="source-map": target["sourceIdentity"]["map_id"]=33
            elif fault=="source-generation": target["sourceIdentity"]["encounter_generation"]+=1
            elif fault=="native-lookup": target["engineIdentity"]["id_lookup"]["first_active_pointer"]=1
            elif fault=="terminal-token": target["reservationId"]=274
            elif fault=="terminal-target": target["target"]["x"]+=1
            elif fault=="terminal-commit": target["commitSequence"]-=1
            elif fault=="live-engine": target["engineIdentity"]["pointer"]=prior["engineIdentity"]["pointer"]
            elif fault=="native-hp": s["pokemonCombat"]["targets"].append(deepcopy(hp))
            elif fault=="held-control": s["pokemonCombat"]["movementTimers"].append(deepcopy(m.latest["pokemonCombat"]["movementTimers"][-1]))
            elif fault=="target-row": s["pokemonCombat"]["interactions"]["carriers"].append(deepcopy(m.latest["pokemonCombat"]["interactions"]["carriers"][-1]))
            elif fault=="retained-claim": claims(s,target=1<<5,recovery=1<<3)
            else: rebind(s,3,player=False,cargo=target)
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                state,rows,timers,actors=ground_state(s,SOURCE)
                m._cycles(s,events,m._actors(s),state,rows,timers,actors)

    def test_faint_retirement_rejects_unproved_next_frame_detach(self):
        for fault in ("missing","public-copy","owner","pid","reason","clock","queue","order","late","context","claim","held"):
            m,s,events,nxt,detach=fainted_flight_case()
            state,rows,timers,actors=ground_state(s,SOURCE);m._cycles(s,events,m._actors(s),state,rows,timers,actors)
            m.latest=deepcopy(s)
            if fault=="missing":detach=[]
            elif fault=="public-copy":nxt["actors"].append(deepcopy(s["actors"][-1]))
            elif fault=="owner":detach[0]["data"]["actor"]["generation"]+=1
            elif fault=="pid":detach[0]["data"]["valueB"]+=1
            elif fault=="reason":detach[0]["data"]["reason"]="REJECTED_RESERVED"
            elif fault=="clock":detach[0]["data"]["actorFrame"]+=1
            elif fault=="queue":detach[0]["frame"]-=1
            elif fault=="order":detach[0]["data"]["sequence"]=201
            elif fault=="late":nxt["frame"]+=1
            elif fault=="context":nxt["context"]["mapGeneration"]+=1
            elif fault=="claim":claims(nxt,target=1<<5,recovery=1<<3)
            else:
                row=deepcopy(m.latest["pokemonCombat"]["movementTimers"][-1])
                row.update(handle=deepcopy(s["actors"][-1]["handle"]),movementActorControlMode=1)
                nxt["pokemonCombat"]["movementTimers"].append(row)
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                m._finish_faint_retirements(nxt,detach,nxt["pokemonCombat"]["interactions"]["throwState"])

    def test_only_unclaimed_optional_cargo_can_leave_by_exact_native_distance_cleanup(self):
        old=sample(19); cargo=old["actors"][0]; cargo["engineObject"].update(x=591,y=391)
        old["pokemonCombat"]["targets"]=[dict(handle=deepcopy(cargo["handle"]),currentHp=261,hpMirrorMatches=True)]
        s=deepcopy(old); s.update(frame=20,actorFrame=20,nativeCycle=1020,player=dict(x=587,y=408))
        a=s["actors"][0];a.pop("engineObject");a["identityVerified"]=False
        a["engineIdentity"].update(pointer=0,in_manager=False,active=False,id_lookup=dict(status="complete",eligible_count=0))
        a["sourceIdentity"].update(object=0,active=0,personality=0,species=0,form=0,level=0,map_id=1)
        call=dict(address=SOURCE["helperAddress"],entrySha256=SOURCE["helperEntrySha256"],nonmatchingEntries=0)
        s["nativeObservation"]["calls"]={"distance-maintenance":call}
        before=dict(lastKnownX=[591]+[0]*9,lastKnownY=[391]+[0]*9,farSamples=[1]+[0]*9,
            managerRestoreMask=0,distanceDespawnPendingMask=0,throwState=deepcopy(old["pokemonCombat"]["interactions"]["throwState"]),
            telemetrySequence=0,telemetryWriteIndex=0,telemetryHex=bytes(336).hex())
        after=deepcopy(before);after.update(farSamples=[0]*10,telemetrySequence=1,telemetryWriteIndex=1)
        raw=bytearray(336);struct.pack_into("<IHBB",raw,0,0x4F574450,1,1,0)
        struct.pack_into("<III5H5h6B",raw,16,cargo["engineIdentity"]["pointer"],1,cargo["subjectIdentity"],
            1,33,33,1,1,591,391,587,408,224,3,1,0,17,61,224);after["telemetryHex"]=raw.hex()
        event=dict(frame=20,kind="native-observation",data=dict(observation="distance-maintenance",sequence=1,
            scope="native scheduled distance-maintenance entry/return",acceptedProof=False,diagnosticOnly=True,setupMode="prepared",
            entryActorFrame=20,returnActorFrame=20,entryNativeCycle=1020,returnNativeCycle=1020,
            worldContext=dict(s["context"],fieldPointer=s["fieldControl"]["fieldPointer"],statePointer=0x02230000),
            fieldPointer=s["fieldControl"]["fieldPointer"],statePointer=0x02230000,hardProtectedMask=0,movementDeferredMask=0,
            before=before,after=after))
        def fresh():
            m=meter(old);m.latest=deepcopy(old);return m
        m=fresh();m._optional_cargo_exit(s,[event]);self.assertEqual(m.cargo_exit["telemetry"]["distance"],17)
        self.assertEqual(set(m._actors(s)),set(GEODUDES)|{"passive"});self.assertEqual(m.completed,[])
        from tools.overworld.control import _distance_subject_retired
        current=SimpleNamespace(measurements={KIND:m})
        self.assertTrue(_distance_subject_retired(s,current,m.subjects["cargo"]))
        for name in (*GEODUDES,"passive"):
            self.assertFalse(_distance_subject_retired(s,current,m.subjects[name]))
        for fault in ("subject","handle","clock","meter-failure","missing-delete"):
            changed_meter=deepcopy(m);bad=deepcopy(s);subject=deepcopy(m.subjects["cargo"])
            if fault=="subject":subject["subjectIdentity"]+=1
            elif fault=="handle":changed_meter.cargo_exit["handle"]["generation"]+=1
            elif fault=="clock":bad["frame"]-=1
            elif fault=="meter-failure":changed_meter.failures.append("invalid native DELETE")
            else:changed_meter.cargo_exit=None
            with self.subTest(retirement=fault):
                self.assertFalse(_distance_subject_retired(bad,SimpleNamespace(measurements={KIND:changed_meter}),subject))
        next_sample=deepcopy(s);next_sample.update(frame=21,actorFrame=21,nativeCycle=1021);next_sample["actors"].pop(0)
        detach=native(cargo,20,"ACTOR_DETACHED",1,cargo["subjectIdentity"],2);detach["frame"]=21
        detach["data"]["traceFieldEpoch"]=cargo["handle"]["fieldEpoch"]
        m._optional_cargo_exit(next_sample,[detach]);self.assertIsNotNone(m.cargo_exit["detach"])
        for fault in ("missing-receipt","source","helper-address","helper-hash","claimed","held","moving","cycle",
                      "fainted","telemetry","telemetry-owner","distance","far-sample","protected"):
            bad=deepcopy(s);e=deepcopy(event);n=fresh();events=[e]
            if fault=="missing-receipt":events=[]
            elif fault=="source":bad["actors"][0]["sourceIdentity"]["object"]=1
            elif fault=="helper-address":bad["nativeObservation"]["calls"]["distance-maintenance"]["address"]+=2
            elif fault=="helper-hash":bad["nativeObservation"]["calls"]["distance-maintenance"]["entrySha256"]="e"*64
            elif fault=="claimed":bad["pokemonCombat"]["interactions"]["throwState"]["targets"][1]=129
            elif fault=="held":n.latest["pokemonCombat"]["movementTimers"][0]["movementActorControlMode"]=1
            elif fault=="moving":n.latest["actors"][0]["reservationId"]=1
            elif fault=="cycle":n.cycles[1]=dict(carrier=old["actors"][1]["handle"],cargo=cargo["handle"])
            elif fault=="fainted":n.latest["pokemonCombat"]["targets"][0]["currentHp"]=0
            elif fault=="telemetry":e["data"]["after"]["telemetryHex"]=bytes(336).hex()
            elif fault in ("telemetry-owner","distance"):
                raw=bytearray.fromhex(e["data"]["after"]["telemetryHex"])
                if fault=="telemetry-owner":struct.pack_into("<I",raw,16,cargo["engineIdentity"]["pointer"]+4)
                else:raw[51]=16
                e["data"]["after"]["telemetryHex"]=raw.hex()
            elif fault=="far-sample":e["data"]["before"]["farSamples"][0]=0
            else:e["data"]["hardProtectedMask"]=1
            with self.subTest(fault=fault),self.assertRaises(ValueError):n._optional_cargo_exit(bad,events)
        for fault in ("missing-detach","detach-owner","detach-clock","detach-order","primary"):
            n=fresh();n._optional_cargo_exit(s,[event]);bad=deepcopy(next_sample);e=deepcopy(detach);events=[e]
            if fault=="missing-detach":events=[]
            elif fault=="detach-owner":e["data"]["actor"]["generation"]+=1
            elif fault=="detach-clock":e["data"]["frame"]=e["data"]["actorFrame"]=21
            elif fault=="detach-order":e["data"]["sequence"]=0
            else:bad["actors"].pop(0)
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                n._optional_cargo_exit(bad,events);n._actors(bad)

    def test_registered_recipe_uses_one_5040_frame_window(self):
        from tools.overworld.devtools_test_contract import TestEvaluator,validate_test
        from tools.overworld.proof_adapters import ADAPTERS
        p = ROOT/"tests/overworld/test-recipes"/(CASE+".json"); r = json.loads(p.read_text())
        validate_recipe(r); r = validate_test(r); e = TestEvaluator(r); e.install_measurements({KIND:SOURCE})
        self.assertIsInstance(e.measurements[KIND],WildThrowSoakMeasurement)
        self.assertEqual(sum(a[2]["frames"] for a in ACTIONS if a[1]=="step"),5040)
        legs=[a for a in ACTIONS if a[1]=="step"]
        self.assertEqual(len(legs),210)
        self.assertEqual([a[2]["keys"] for a in legs[:4]],[["B",d] for d in ("LEFT","DOWN","RIGHT","UP")])
        self.assertEqual(HELD_KEYS,(34,130,18,66))
        self.assertEqual(tuple(a[2]["frames"] for a in legs),LEG_FRAME_COUNTS)
        self.assertEqual(LEG_FRAME_COUNTS,(24,32,24,16)*52+(24,24))
        checks=[(i,a) for i,a in enumerate(ACTIONS) if a[0].startswith("health-check-")]
        self.assertEqual([a[0] for _,a in checks],[f"health-check-{n:03}" for n in CHECKPOINT_LEGS])
        for i,a in checks:
            self.assertEqual(a[1:],("player-health.observe",{}))
            leg=int(a[0].rsplit("-",1)[1]);self.assertEqual(ACTIONS[i-1][0],f"soak-{leg:03}")
            self.assertEqual(sum(x[2]["frames"] for x in ACTIONS[:i] if x[1]=="step"),leg*LEG_FRAMES)
        self.assertEqual(ADAPTERS[KIND].proof_level,"S5"); self.assertEqual(ADAPTERS[KIND].contract(),contract())
        registry = json.loads((ROOT/"tools/overworld/runtime_proof_registry.json").read_text())["sharedTests"][CASE]
        self.assertEqual(registry["recipeSha256"],hashlib.sha256(p.read_bytes()).hexdigest())
        for fault in ("timer-write","short-window","low-level","low-passive-level","wrong-turn","long-leg",
                      "missing-check","moved-check","duplicate-check","old-leg-budget"):
            bad = deepcopy(r)
            if fault=="timer-write": bad["setup"].append(dict(id="repair",op="walk-policy.reset",args={}))
            elif fault=="short-window": bad["actions"].pop(2)
            elif fault=="low-level": bad["setup"][6]["args"]["level"]=5
            elif fault=="wrong-turn": bad["actions"][1]["args"]["keys"]=["B","RIGHT"]
            elif fault=="long-leg": bad["actions"][1]["args"]["frames"]=40
            elif fault=="old-leg-budget": bad["actions"][2]["budget"]["maxFrames"]=24
            elif fault in ("missing-check","moved-check","duplicate-check"):
                i=next(i for i,a in enumerate(bad["actions"]) if a["id"]=="health-check-040")
                checkpoint=bad["actions"].pop(i)
                if fault=="moved-check":bad["actions"].insert(i-1,checkpoint)
                elif fault=="duplicate-check":bad["actions"][i:i]=[checkpoint,deepcopy(checkpoint)]
            else:
                for action in bad["setup"][1:3]: action["args"]["level"]=20
            with self.subTest(fault=fault),self.assertRaises(ValueError): validate_recipe(bad)

    def test_recovery_and_grounded_held_faults_use_actual_raw_masks(self):
        for fault in (FAULTS[1],FAULTS[2]):
            s = sample(); m = meter(s)
            if fault.endswith("recovery-pickup-leak"):
                claims(s,encoded=131,target=4,carrier=2);rebind(s,1,cargo=s["actors"][2])
                s["pokemonCombat"]["movementTimers"][2]["movementActorControlMode"]=1
            negative = WildThrowSoakNegative(fault); bad = negative.mutate(dict(phase="observe",samples=[s],events=[]),m.subjects)
            self.assertTrue(negative.applied)
            with self.assertRaises(ValueError) as error: ground_state(bad["samples"][0],SOURCE)
            validate_negative_result(dict(passed=False,failures=[str(error.exception)]),fault)

    def test_stale_claim_cannot_make_ordinary_hop_a_held_flight(self):
        s = sample(); b = s["actors"][2]; claims(s,target=4)
        s["pokemonCombat"]["movementTimers"][2]["movementActorControlMode"]=1
        motion(s,b,origin=(585,409),target=(585,417))
        m=meter(s)
        with self.assertRaisesRegex(ValueError,"grounded HELD"):
            ground_state(s,SOURCE,lambda actor,motion:m._owned_flight(s,[],actor,motion))
        row = s["pokemonCombat"]["targets"][0]; raw = bytearray.fromhex(row["motion"]["rawHex"]); raw[37]=1
        row["motion"]=decode_motion(bytes(raw))
        with self.assertRaisesRegex(ValueError,"grounded HELD"):
            ground_state(s,SOURCE,lambda actor,motion:m._owned_flight(s,[],actor,motion))
        row["handle"]["generation"]+=1
        with self.assertRaisesRegex(ValueError,"current native motion"): ground_state(s,SOURCE)

    def test_pre_tick_lane_change_requires_exact_prior_owner_clock_and_lane(self):
        previous=sample(992);previous['actorFrame']=524;previous['actors'][2]['laneId']=0
        current=sample(993);current['actorFrame']=525;a=current['actors'][2];a['laneId']=2
        m=meter(current);m.latest=previous
        event=native(a,524,'LANE_CHANGED',0,2,439);event['frame']=993
        self.assertEqual(m._events(current,[event],a),[event['data']])
        exact=native(a,525,'MOTION_STARTED',2,12,440);exact['frame']=993
        self.assertEqual(m._events(current,[exact],a),[exact['data']])
        for fault in ('old-start','older-clock','split-clock','wrong-owner','wrong-prior-owner','wrong-prior-lane','wrong-current-lane','wrong-reason'):
            bad=deepcopy(event);prior=deepcopy(previous)
            if fault=='old-start':bad['data']['event']='MOTION_STARTED'
            elif fault=='older-clock':bad['data']['frame']=bad['data']['actorFrame']=523
            elif fault=='split-clock':bad['data']['frame']=523
            elif fault=='wrong-owner':bad['data']['actor']['generation']+=1
            elif fault=='wrong-prior-owner':prior['actors'][2]['handle']['generation']+=1
            elif fault=='wrong-prior-lane':bad['data']['valueA']=1
            elif fault=='wrong-current-lane':bad['data']['valueB']=1
            else:bad['data']['reason']='REJECTED'
            m.latest=prior
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'semantic event owner or clock'):
                m._events(current,[bad],a)

    def test_terminal_owner_blocking_control_and_legitimate_release(self):
        for status,name in ((4,"RESOURCE_LIMIT"),(2,"UNREACHABLE")):
            with self.subTest(status=name):
                s=sample();m=meter(s);state,rows,timers,actors=ground_state(s,SOURCE)
                events=[query(s,1,sequence=1),query(s,2,sequence=2)]
                negative=WildThrowSoakNegative(FAULTS[0]);bad=negative.mutate(dict(phase="observe",samples=[s],events=events),m.subjects)
                self.assertTrue(negative.applied)
                terminal=bad["events"][0]["data"];raw=bytearray.fromhex(terminal["resultHex"])
                raw[104]=raw[138]=status
                terminal.update(resultHex=raw.hex(),returnValue=status,resultStatus=status,status=name)
                with self.assertRaisesRegex(ValueError,"terminal "+name+" owner blocks") as error:
                    for e in bad["events"]:m._query(s,e,rows,timers,actors)
                validate_negative_result(dict(passed=False,failures=[str(error.exception)]),FAULTS[0])
                m=meter(s);terminal=query(s,1,status,1);terminal["data"]["after"]["workspace"]["valid"]=False
                m._query(s,terminal,rows,timers,actors);m._query(s,query(s,2,sequence=2),rows,timers,actors)
                self.assertEqual(m.limit_count,int(status==4));self.assertEqual(m.limits,{})

    def test_terminal_control_requires_one_uninterrupted_current_query_pair(self):
        editor=WildThrowSoakNegative(FAULTS[0]);m=meter(sample(20))
        for frame,slot in ((20,1),(21,2)):
            s=sample(frame);row=dict(phase="observe",samples=[s],events=[query(s,slot,sequence=frame)])
            self.assertIs(editor.mutate(row,m.subjects),row)
            self.assertFalse(editor.applied);self.assertIsNone(editor.terminal)
        s=sample(22);claims(s,recovery=8)
        s["pokemonCombat"]["movementTimers"][3].update(movementEmoteTimer=60,movementSpotState=3)
        interrupted=dict(phase="observe",samples=[s],events=[query(s,1,sequence=22),query(s,3,sequence=23),query(s,2,sequence=24)])
        self.assertIs(editor.mutate(interrupted,m.subjects),interrupted)
        self.assertFalse(editor.applied);self.assertIsNone(editor.terminal)
        pair=dict(phase="observe",samples=[s],events=[query(s,1,sequence=25),query(s,2,sequence=26)])
        work=bytearray.fromhex(pair["events"][0]["data"]["after"]["workspace"]["lastWorkHex"]);work[20]=1
        pair["events"][0]["data"]["after"]["workspace"].update(lastWorkHex=work.hex(),goalQueries=1)
        raw=bytearray.fromhex(pair["events"][0]["data"]["resultHex"]);raw[128]=1
        pair["events"][0]["data"]["resultHex"]=raw.hex()
        changed=editor.mutate(pair,m.subjects);self.assertTrue(editor.applied)
        first,peer=[e["data"] for e in changed["events"]]
        self.assertEqual((first["status"],peer["status"]),("RESOURCE_LIMIT","PENDING"))
        self.assertEqual(first["after"]["workspace"],peer["after"]["workspace"])
        for d in (first,peer):
            self.assertEqual((d["after"]["workspace"]["edgeQueries"],d["after"]["workspace"]["goalQueries"]),(0,0))
            self.assertEqual(bytes.fromhex(d["after"]["workspace"]["lastWorkHex"]),bytes.fromhex(d["resultHex"])[108:136])
        self.assertEqual(first["after"]["queryPointer"],peer["after"]["queryPointer"])
        self.assertEqual(pair["events"][0]["data"]["status"],"PENDING")
        self.assertEqual(pair["events"][0]["data"]["after"]["workspace"]["goalQueries"],1)
        state,rows,timers,actors=ground_state(s,SOURCE)
        with self.assertRaisesRegex(ValueError,"terminal RESOURCE_LIMIT owner blocks") as error:
            for e in changed["events"]:m._query(s,e,rows,timers,actors)
        validate_negative_result(dict(passed=False,failures=[str(error.exception)]),FAULTS[0])

    def test_completed_flight_requires_exact_landing_control(self):
        m=self._flight(1,2)
        self.assertEqual(len(m.completed),1);self.assertEqual(len(m.recovery_pickups),1)
        self.assertEqual(m.completed[0]["landed"],32);self.assertEqual(m.completed[0]["cleanup"],33)

    def test_foreign_carrier_has_the_same_owned_flight_and_landing_guards_without_credit(self):
        m=self._flight(5,1)
        self.assertEqual(m.completed,[]);self.assertEqual(m.recovery_pickups,[]);self.assertEqual(m.cycles,{})

    def test_primary_carrier_cannot_credit_recovering_ambient_geodude(self):
        m=self._flight(1,5)
        self.assertEqual(len(m.completed),1);self.assertEqual(m.recovery_pickups,[])

    def _flight(self, carrier_slot, target_slot):
        foreign=5 in (carrier_slot,target_slot)
        m = meter(sample(20,foreign=foreign))
        copied=WildThrowSoakNegative(FAULTS[3]) if not foreign else None
        for frame in range(20,34):
            s=sample(frame,foreign=foreign)
            a=next(a for a in s["actors"] if a["handle"]["slot"]==carrier_slot)
            b=next(a for a in s["actors"] if a["handle"]["slot"]==target_slot)
            carrier_index=s["actors"].index(a);target_index=s["actors"].index(b)
            target_mask=1<<target_slot;carrier_mask=1<<carrier_slot
            b["commitSequence"]=4;events=[]
            a["engineObject"].update(x=585,y=409)
            if frame<22:
                a["matchedLayerMask"]|=THROW_RELEASE_BIT
                raw=bytearray(216);raw[0]=12;raw[76]=8
                struct.pack_into("<II",raw,188,a["matchedLayerMask"],a["behaviorFingerprint"])
                m.profiles[a["behaviorFingerprint"]]=dict(resolved=True,fingerprint=a["behaviorFingerprint"],
                    sourceSha256=SOURCE["profileSha256"],resultHex=raw.hex(),lanes=[raw[:80].hex(),raw[80:160].hex()])
            if frame==20:claims(s,encoded=target_slot+1,target=target_mask,carrier=carrier_mask,owner=carrier_slot);rebind(s,carrier_index,cargo=b)
            elif frame==21:
                claims(s,encoded=192+target_slot+1,target=target_mask,carrier=carrier_mask,owner=carrier_slot);rebind(s,carrier_index,cargo=b)
                s["pokemonCombat"]["movementTimers"][target_index]["movementActorControlMode"]=1
                m.previous_state=dict(recoveringMask=target_mask)
            else:
                claims(s,target=target_mask if frame<32 else 0,recovery=carrier_mask if frame<33 else 0);rebind(s,carrier_index,player=False)
                t=s["pokemonCombat"]["movementTimers"][carrier_index];t.update(movementEmoteTimer=60 if frame<33 else 0,movementSpotState=2 if frame<33 else 0)
                elapsed=min(frame-22,8);phase="MOVING" if frame<30 else "SETTLING" if frame<32 else "IDLE"
                value=motion(s,b,phase=phase,elapsed=elapsed,commit=4 if frame<30 else 5,origin=(585,409),target=(585,417))
                raw=bytearray.fromhex(value["rawHex"]);struct.pack_into("<H",raw,6,b["behaviorFingerprint"]&65535)
                s["pokemonCombat"]["targets"][0]["motion"]=decode_motion(bytes(raw))
                b["engineObject"]["pos_z"]=(409<<16)+32768+65536*elapsed
                if frame<32:s["pokemonCombat"]["movementTimers"][target_index]["movementActorControlMode"]=1
                if frame==22:events=[native(b,frame,"PLAN_ACCEPTED",(585<<16)|417,8,219),native(b,frame,"MOTION_STARTED",2,8,220)]
                if frame==30:events=[native(b,frame,"LOGICAL_COMMIT",5,2,300)]
                if frame==32:events=[native(b,frame,"MOTION_FINISHED",5,2,320),native(b,frame,"CONTROL_RETURNED",0,5,321)]
            state,rows,timers,actors=ground_state(s,SOURCE,lambda actor,motion:m._owned_flight(s,events,actor,motion));named=m._actors(s)
            if foreign and frame in (21,22):
                faults=("held","binding-owner") if frame==21 else ("missing-start","forced-hop","full-owner","retained-binding","old-held-owner")
                for fault in faults:
                    bad=deepcopy(s);bad_events=deepcopy(events);saved=deepcopy(m.cycles);old=deepcopy(m.previous_state)
                    if fault=="held":bad["pokemonCombat"]["movementTimers"][target_index]["movementActorControlMode"]=0
                    elif fault=="binding-owner":
                        wrong=deepcopy(b);wrong["handle"]["generation"]+=1;rebind(bad,carrier_index,cargo=wrong)
                    elif fault=="missing-start":bad_events=[e for e in bad_events if e["data"]["event"]!="MOTION_STARTED"]
                    elif fault=="forced-hop":
                        row=bad["pokemonCombat"]["targets"][0];raw=bytearray.fromhex(row["motion"]["rawHex"])
                        raw[37]=1;row["motion"]=decode_motion(bytes(raw))
                    elif fault=="full-owner":bad["pokemonCombat"]["targets"][0]["handle"]["generation"]+=1
                    elif fault=="retained-binding":rebind(bad,carrier_index,cargo=b)
                    else:m.previous_state["targets"][carrier_slot]=192+((target_slot+1)%10)+1
                    with self.subTest(carrier=carrier_slot,target=target_slot,fault=fault),self.assertRaises(ValueError):
                        st,rs,ts,acs=ground_state(bad,SOURCE,lambda actor,motion:m._owned_flight(bad,bad_events,actor,motion))
                        m._cycles(bad,bad_events,m._actors(bad),st,rs,ts,acs)
                    m.cycles=saved;m.previous_state=old
            if frame==23:
                wrong=deepcopy(b);wrong["handle"]["generation"]+=1
                self.assertFalse(m._owned_flight(s,events,wrong,m._motion(s,b)))
                wrong=m._motion(s,b);wrong=deepcopy(wrong);wrong["plan"]["target"][1]+=1
                with self.assertRaisesRegex(ValueError,"owned flight plan or full owner"):
                    m._owned_flight(s,events,b,wrong)
            bad=copied.mutate(dict(phase="observe",samples=[s],events=events),m.subjects) if copied else dict(events=[e for e in events if e["data"]["event"]!="CONTROL_RETURNED"])
            if frame==32:
                if copied:self.assertTrue(copied.applied)
                saved=deepcopy(m.cycles)
                with self.assertRaisesRegex(ValueError,"ordered FINISH and CONTROL") as error:m._cycles(s,bad["events"],named,state,rows,timers,actors)
                validate_negative_result(dict(passed=False,failures=[str(error.exception)]),FAULTS[3]);m.cycles=saved
            m._cycles(s,events,named,state,rows,timers,actors);m.previous_state=deepcopy(state);m.latest=deepcopy(s)
            self.assertLessEqual(len(m.cycles),10)
        return m

    def test_reserved_throw_drop_then_own_hop_has_no_flight_credit(self):
        m,s,events = blocked_release_case()
        original = deepcopy(s)
        state,rows,timers,actors = ground_state(s,SOURCE)
        m._cycles(s,events,m._actors(s),state,rows,timers,actors)
        self.assertEqual(s,original)
        self.assertEqual(m.cycles,{})
        self.assertEqual(m.completed,[])
        self.assertEqual(m.recovery_pickups,[])
        self.assertEqual(len(m.blocked_releases),1)
        receipt=m.blocked_releases[0]
        self.assertEqual(receipt["frame"],21)
        self.assertEqual(receipt["cargo"],s["actors"][0]["handle"])
        self.assertEqual(receipt["plan"]["duration"],11)
        self.assertEqual([e["sequence"] for e in receipt["native"]],list(range(1838,1844)))

    def test_reserved_throw_drop_rejects_bad_native_and_held_records(self):
        faults=("missing-rejection","wrong-rejection","rejection-order","native-owner","native-clock","outer-clock",
            "source","prior-source","current-owner","held-control","retained-claim","retained-carrier",
            "retained-binding","prior-held","prior-pair","prior-cycle","prior-profile","profile-source",
            "ordinary-time","ordinary-plan","ordinary-accepted","ordinary-start","forced-hop","real-launch-loss")
        for fault in faults:
            m,s,events=blocked_release_case();target=s["actors"][0]
            if fault=="missing-rejection":events.pop(1)
            elif fault=="wrong-rejection":events[1]["data"]["reason"]="REJECTED_COLLISION"
            elif fault=="rejection-order":events[1]["data"]["sequence"]=1844
            elif fault=="native-owner":events[1]["data"]["actor"]["generation"]+=1
            elif fault=="native-clock":events[1]["data"]["actorFrame"]-=1
            elif fault=="outer-clock":events[1]["frame"]-=1
            elif fault=="source":target["sourceIdentity"]["object"]+=4
            elif fault=="prior-source":m.latest["actors"][0]["sourceIdentity"]["object"]+=4
            elif fault=="current-owner":target["handle"]["generation"]+=1
            elif fault=="held-control":s["pokemonCombat"]["movementTimers"][0]["movementActorControlMode"]=1
            elif fault=="retained-claim":claims(s,target=1,recovery=2)
            elif fault=="retained-carrier":claims(s,carrier=2,recovery=2)
            elif fault=="retained-binding":rebind(s,1,cargo=target)
            elif fault=="prior-held":m.latest["pokemonCombat"]["movementTimers"][0]["movementActorControlMode"]=0
            elif fault=="prior-pair":m.previous_state["targets"][1]=194
            elif fault=="prior-cycle":m.cycles[1]["cargo"]["generation"]+=1
            elif fault=="prior-profile":
                data=m.profiles[m.latest["actors"][1]["behaviorFingerprint"]];raw=bytearray.fromhex(data["resultHex"])
                raw[0]=3;data.update(resultHex=raw.hex(),lanes=[raw[:80].hex(),raw[80:160].hex()])
            elif fault=="profile-source":m.profiles[target["behaviorFingerprint"]]["sourceSha256"]="wrong"
            elif fault=="ordinary-time":
                data=m.profiles[target["behaviorFingerprint"]];raw=bytearray.fromhex(data["resultHex"])
                raw[36]=2;data.update(resultHex=raw.hex(),lanes=[raw[:80].hex(),raw[80:160].hex()])
            elif fault in ("ordinary-plan","forced-hop"):
                row=s["pokemonCombat"]["targets"][0];raw=bytearray.fromhex(row["motion"]["rawHex"])
                if fault=="ordinary-plan":struct.pack_into("<H",raw,6,target["behaviorFingerprint"]&65535 ^ 1)
                else:raw[37]=1
                row["motion"]=decode_motion(bytes(raw))
            elif fault=="ordinary-accepted":events[4]["data"]["valueB"]+=1
            elif fault=="ordinary-start":events[-1]["data"]["valueB"]+=1
            else:events=events[4:]
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                state,rows,timers,actors=ground_state(s,SOURCE,lambda a,motion:m._owned_flight(s,events,a,motion))
                m._cycles(s,events,m._actors(s),state,rows,timers,actors)

    def test_damage_knockback_release_does_not_credit_a_throw_launch(self):
        previous=sample(20);carrier,target=previous['actors'][1:3]
        claims(previous,encoded=131,target=4,carrier=2);rebind(previous,1,cargo=target)
        previous['pokemonCombat']['movementTimers'][2]['movementActorControlMode']=1
        current=sample(21);rebind(current,1,player=False);events=[]
        for actor in current['actors'][1:3]:
            move=motion(current,actor,origin=(585,409),target=(585,408))
            raw=bytearray.fromhex(move['rawHex']);raw[36]=raw[37]=1
            row=current['pokemonCombat']['targets'][-1];row['motion']=decode_motion(bytes(raw))
            row.update(currentHp=80,hp=80,hpMirrorMatches=True,hitCount=1,lastDamage=20)
            previous['pokemonCombat']['targets'].append(dict(handle=deepcopy(actor['handle']),currentHp=100,hitCount=0))
            events.append(native(actor,21,'MOTION_STARTED',2,8,210+actor['handle']['slot']))
        own=dict(carrier=deepcopy(carrier['handle']),cargo=deepcopy(target['handle']),claim=19,pickup=20,
                 launch=None,landed=None,cleanup=None,motion=None,recorder=None,credited=True)
        def check(sample):
            m=meter(sample);m.latest=deepcopy(previous);m.cycles[1]=deepcopy(own)
            state,rows,timers,actors=ground_state(sample,SOURCE)
            m._cycles(sample,events,m._actors(sample),state,rows,timers,actors)
            return m
        m=check(current);self.assertEqual(m.cycles,{});self.assertEqual(m.completed,[])
        for fault in ('missing-damage','missing-hit','unforced-hop','wrong-owner','held-control','retained-claim'):
            bad=deepcopy(current);row=bad['pokemonCombat']['targets'][0]
            if fault=='missing-damage':row['currentHp']=row['hp']=100
            elif fault=='missing-hit':row['hitCount']=0
            elif fault=='unforced-hop':
                raw=bytearray.fromhex(row['motion']['rawHex']);raw[37]=0;row['motion']=decode_motion(bytes(raw))
            elif fault=='wrong-owner':row['handle']['generation']+=1
            elif fault=='held-control':bad['pokemonCombat']['movementTimers'][2]['movementActorControlMode']=1
            else:claims(bad,target=4)
            with self.subTest(fault=fault),self.assertRaises(ValueError):check(bad)

    def test_unlaunched_drop_ends_cycle_before_later_cargo_damage_jump(self):
        previous=sample(20);carrier,target=previous['actors'][1:3]
        claims(previous,encoded=195,target=4,carrier=2);rebind(previous,1,cargo=target)
        previous['pokemonCombat']['movementTimers'][2]['movementActorControlMode']=1
        own=dict(carrier=deepcopy(carrier['handle']),cargo=deepcopy(target['handle']),claim=19,pickup=20,
                 launch=None,landed=None,cleanup=None,motion=None,recorder=None,credited=True)
        released=sample(21);claims(released,recovery=2);rebind(released,1,player=False)
        released['pokemonCombat']['movementTimers'][1].update(movementEmoteTimer=60,movementSpotState=3)
        def check(s):
            m=meter(previous);m.latest=deepcopy(previous);m.cycles[1]=deepcopy(own)
            state,rows,timers,actors=ground_state(s,SOURCE)
            m._cycles(s,[],m._actors(s),state,rows,timers,actors)
            return m
        m=check(released);self.assertEqual(m.cycles,{});self.assertEqual(m.completed,[])
        self.assertEqual(m.recovery_pickups,[])
        for fault in ('held','target-mask','carrier-mask','binding','recovery','owner'):
            bad=deepcopy(released)
            if fault=='held':bad['pokemonCombat']['movementTimers'][2]['movementActorControlMode']=1
            elif fault=='target-mask':claims(bad,target=4,recovery=2)
            elif fault=='carrier-mask':claims(bad,carrier=2,recovery=2)
            elif fault=='binding':rebind(bad,1,cargo=target)
            elif fault=='recovery':bad['pokemonCombat']['movementTimers'][1].update(movementEmoteTimer=0,movementSpotState=0)
            else:bad['pokemonCombat']['interactions']['carriers'][1]['handle']['generation']+=1
            with self.subTest(fault=fault),self.assertRaises(ValueError):check(bad)
        later=sample(22);claims(later,recovery=2);rebind(later,1,player=False)
        later['pokemonCombat']['movementTimers'][1].update(movementEmoteTimer=59,movementSpotState=3)
        victim=later['actors'][2];move=motion(later,victim,origin=(585,409),target=(585,410))
        raw=bytearray.fromhex(move['rawHex']);raw[37]=1
        row=later['pokemonCombat']['targets'][0];row['motion']=decode_motion(bytes(raw))
        row.update(currentHp=80,hp=80,hpMirrorMatches=True,hitCount=1,lastDamage=20)
        events=[native(victim,22,'PLAN_ACCEPTED',(585<<16)|410,8,220),native(victim,22,'MOTION_STARTED',2,8,221)]
        m.latest=deepcopy(released);m.previous_state=deepcopy(released['pokemonCombat']['interactions']['throwState'])
        state,rows,timers,actors=ground_state(later,SOURCE,lambda a,move:m._owned_flight(later,events,a,move))
        self.assertFalse(m._owned_flight(later,events,victim,row['motion']))
        m._cycles(later,events,m._actors(later),state,rows,timers,actors)
        self.assertEqual(m.cycles,{});self.assertEqual(m.completed,[]);self.assertEqual(m.recovery_pickups,[])
        bad=deepcopy(later);bad['pokemonCombat']['movementTimers'][2]['movementActorControlMode']=1
        with self.assertRaisesRegex(ValueError,'grounded HELD'):
            ground_state(bad,SOURCE,lambda a,move:m._owned_flight(bad,events,a,move))

    def test_cargo_only_hit_releases_the_exact_held_claim_without_throw_credit(self):
        previous=sample(20);carrier,target=previous['actors'][1:3]
        claims(previous,encoded=195,target=4,carrier=2);rebind(previous,1,cargo=target)
        previous['pokemonCombat']['movementTimers'][2]['movementActorControlMode']=1
        motion(previous,carrier,phase='IDLE',elapsed=8,commit=5,kind=1)
        carrier['motionKind']='NONE';previous['pokemonCombat']['targets'][0].update(
            currentHp=100,hp=100,hpMirrorMatches=True,hitCount=0)
        previous['pokemonCombat']['targets'].append(dict(handle=deepcopy(target['handle']),currentHp=100,hitCount=0))
        current=deepcopy(previous);current.update(frame=21,actorFrame=21,nativeCycle=1021)
        current['pokemonCombat'].update(frame=21,nativeCycle=1021)
        current['pokemonCombat']['interactions'].update(frame=21,nativeCycle=1021)
        claims(current);rebind(current,1,player=False)
        current['pokemonCombat']['movementTimers'][2]['movementActorControlMode']=0
        target=current['actors'][2];value=motion(current,target,origin=(585,409),target=(585,408))
        raw=bytearray.fromhex(value['rawHex']);raw[36]=raw[37]=1
        current['pokemonCombat']['targets'][-1].update(motion=decode_motion(bytes(raw)),
            currentHp=80,hp=80,hpMirrorMatches=True,hitCount=1,lastDamage=20)
        events=[native(target,21,'PLAN_ACCEPTED',(585<<16)|408,8,210),native(target,21,'MOTION_STARTED',2,8,211)]
        own=dict(carrier=deepcopy(carrier['handle']),cargo=deepcopy(target['handle']),claim=19,pickup=20,
            launch=None,landed=None,cleanup=None,motion=None,recorder=None,credited=True)
        def check(before,after,events):
            m=meter(after);m.latest=deepcopy(before);m.cycles[1]=deepcopy(own)
            state,rows,timers,actors=ground_state(after,SOURCE)
            m._cycles(after,events,m._actors(after),state,rows,timers,actors)
            return m
        m=check(previous,current,events);self.assertEqual(m.cycles,{});self.assertEqual(m.completed,[])
        m=meter(current);m.latest=deepcopy(previous)
        with self.assertRaisesRegex(ValueError,'accepted native START'):
            m._damage_abort(current,events[:-1],current['actors'][1],current['actors'][2])
        for fault in ('unowned-hop','old-held-control','wrong-cargo','cargo-no-hit','cargo-no-damage','cargo-unforced',
                      'carrier-hp-change','carrier-hit-change','carrier-new-start','carrier-held','carrier-reservation',
                      'carrier-plan-change','retained-claim'):
            before=deepcopy(previous);after=deepcopy(current);copied=deepcopy(events)
            cargo=after['pokemonCombat']['targets'][-1];holder=after['pokemonCombat']['targets'][0]
            if fault=='unowned-hop':claims(before)
            elif fault=='old-held-control':before['pokemonCombat']['movementTimers'][2]['movementActorControlMode']=0
            elif fault=='wrong-cargo':rebind(before,1,cargo=before['actors'][3])
            elif fault=='cargo-no-hit':cargo['hitCount']=0
            elif fault=='cargo-no-damage':cargo['currentHp']=cargo['hp']=100
            elif fault=='cargo-unforced':
                raw=bytearray.fromhex(cargo['motion']['rawHex']);raw[37]=0;cargo['motion']=decode_motion(bytes(raw))
            elif fault=='carrier-hp-change':holder['currentHp']=holder['hp']=99
            elif fault=='carrier-hit-change':holder['hitCount']=1
            elif fault=='carrier-new-start':copied.append(native(after['actors'][1],21,'MOTION_STARTED',2,8,212))
            elif fault=='carrier-held':after['pokemonCombat']['movementTimers'][1]['movementActorControlMode']=1
            elif fault=='carrier-reservation':after['actors'][1]['reservationId']=22
            elif fault=='carrier-plan-change':
                raw=bytearray.fromhex(holder['motion']['rawHex']);struct.pack_into('<H',raw,26,22);holder['motion']=decode_motion(bytes(raw))
            else:claims(after,target=4)
            with self.subTest(fault=fault),self.assertRaises(ValueError):check(before,after,copied)

    def test_cargo_hit_drop_keeps_the_exact_ordinary_carrier_move(self):
        for kind in (1, 2):
            for carrier_hit in (False, True):
                with self.subTest(kind=kind, carrier_hit=carrier_hit):
                    m, current, events = ordinary_carrier_damage_release(kind, carrier_hit)
                    original = deepcopy(current)
                    state, rows, timers, actors = ground_state(current, SOURCE)
                    m._cycles(current, events, m._actors(current), state, rows, timers, actors)
                    self.assertEqual(m.cycles, {})
                    self.assertEqual(m.completed, [])
                    self.assertEqual(m.recovery_pickups, [])
                    self.assertEqual(current, original)

    def test_cargo_hit_ordinary_carrier_continuation_rejects_bad_records(self):
        faults = ('frame', 'actor-clock', 'native-clock', 'source', 'prior-source', 'full-owner', 'lane',
            'plan', 'reservation', 'elapsed', 'public-elapsed', 'phase', 'public-commit', 'raw-commit',
            'forced-carrier', 'carrier-held', 'new-start', 'canceled', 'carrier-mirror', 'old-carrier-mirror',
            'carrier-hp', 'carrier-hit', 'missing-pending', 'cargo-hp', 'cargo-hit', 'cargo-unforced',
            'cargo-held', 'retained-claim', 'retained-binding', 'missing-accepted', 'accepted-plan',
            'accepted-order', 'missing-start', 'wrong-start-owner')
        for fault in faults:
            with self.subTest(fault=fault):
                m, s, events = ordinary_carrier_damage_release(carrier_hit=True)
                holder = s['actors'][1]; cargo = s['actors'][2]
                health = s['pokemonCombat']['targets'][0]; target = s['pokemonCombat']['targets'][1]
                raw = bytearray.fromhex(health['motion']['rawHex'])
                if fault == 'frame': s['frame'] += 1
                elif fault == 'actor-clock': s['actorFrame'] += 1
                elif fault == 'native-clock': s['nativeCycle'] = m.latest['nativeCycle']
                elif fault == 'source': holder['sourceIdentity']['personality'] += 1
                elif fault == 'prior-source': m.latest['actors'][1]['sourceIdentity']['personality'] += 1
                elif fault == 'full-owner': holder['handle']['generation'] += 1
                elif fault == 'lane': holder['laneId'] += 1
                elif fault == 'plan': struct.pack_into('<h', raw, 12, 587)
                elif fault == 'reservation': holder['reservationId'] += 1
                elif fault == 'elapsed': struct.pack_into('<H', raw, 40, 6); holder['motionElapsed'] = 6
                elif fault == 'public-elapsed': holder['motionElapsed'] = 6
                elif fault == 'phase': raw[48] = 4; holder['motionPhase'] = 'SETTLING'
                elif fault == 'public-commit': holder['commitSequence'] += 1
                elif fault == 'raw-commit': raw[50] = 1
                elif fault == 'forced-carrier': raw[37] = 1
                elif fault == 'carrier-held': s['pokemonCombat']['movementTimers'][1]['movementActorControlMode'] = 1
                elif fault == 'new-start': events.append(native(holder,21,'MOTION_STARTED',1,8,213))
                elif fault == 'canceled': events.append(native(holder,21,'MOTION_CANCELED',0,0,213))
                elif fault == 'carrier-mirror': health['hpMirrorMatches'] = False
                elif fault == 'old-carrier-mirror': m.latest['pokemonCombat']['targets'][0]['hpMirrorMatches'] = False
                elif fault == 'carrier-hp': health['currentHp'] = health['hp'] = 7
                elif fault == 'carrier-hit': health['hitCount'] = 0
                elif fault == 'missing-pending': health['knockbackPending'] = 0
                elif fault == 'cargo-hp': target['currentHp'] = target['hp'] = 100
                elif fault == 'cargo-hit': target['hitCount'] = 0
                elif fault == 'cargo-unforced':
                    data = bytearray.fromhex(target['motion']['rawHex']); data[37] = 0
                    target['motion'] = decode_motion(bytes(data))
                elif fault == 'cargo-held': s['pokemonCombat']['movementTimers'][2]['movementActorControlMode'] = 1
                elif fault == 'retained-claim': claims(s,target=4)
                elif fault == 'retained-binding': rebind(s,1,cargo=cargo)
                elif fault == 'missing-accepted': events.pop(1)
                elif fault == 'accepted-plan': events[1]['data']['valueB'] += 1
                elif fault == 'accepted-order': events[1]['data']['sequence'] = 213
                elif fault == 'missing-start': events.pop()
                else: events[-1]['data']['actor']['generation'] += 1
                health['motion'] = decode_motion(bytes(raw))
                if fault == 'missing-start':
                    with self.assertRaisesRegex(ValueError, 'admitted forced plan'):
                        m._damage_abort(s,events,holder,cargo)
                    continue
                with self.assertRaises(ValueError):
                    state, rows, timers, actors = ground_state(s,SOURCE)
                    m._cycles(s,events,m._actors(s),state,rows,timers,actors)

    def test_cargo_hit_aborts_while_its_exact_carrier_damage_motion_continues(self):
        old=sample(20);carrier,target=old['actors'][1:3]
        claims(old,encoded=195,target=4,carrier=2);rebind(old,1,cargo=target)
        old['pokemonCombat']['movementTimers'][2]['movementActorControlMode']=1
        for a in (carrier,target):
            motion(old,a,phase='IDLE',elapsed=8,kind=1);a['motionKind']='NONE'
            old['pokemonCombat']['targets'][-1].update(currentHp=100,hp=100,hpMirrorMatches=True,hitCount=0,lastDamage=0)
        def at(frame):
            s=deepcopy(old);s.update(frame=frame,actorFrame=frame,nativeCycle=frame+1000)
            s['pokemonCombat'].update(frame=frame,nativeCycle=frame+1000)
            s['pokemonCombat']['interactions'].update(frame=frame,nativeCycle=frame+1000)
            return s
        hit=at(21);hit['pokemonCombat']['targets'][0].update(currentHp=80,hp=80,hitCount=1,lastDamage=20)
        start=at(22);start['pokemonCombat']['targets'][0].update(currentHp=80,hp=80,hitCount=1,lastDamage=20)
        actor=start['actors'][1];value=motion(start,actor,origin=(585,409),target=(585,408))
        raw=bytearray.fromhex(value['rawHex']);raw[36]=raw[37]=1
        start['pokemonCombat']['targets'].sort(key=lambda r:r['handle']['slot'])
        start['pokemonCombat']['targets'][0].update(motion=decode_motion(bytes(raw)),
            currentHp=80,hp=80,hpMirrorMatches=True,hitCount=1,lastDamage=20)
        started=[native(actor,22,'PLAN_ACCEPTED',(585<<16)|408,8,220),native(actor,22,'MOTION_STARTED',2,8,221)]
        released=deepcopy(start);released.update(frame=23,actorFrame=23,nativeCycle=1023)
        released['pokemonCombat'].update(frame=23,nativeCycle=1023)
        released['pokemonCombat']['interactions'].update(frame=23,nativeCycle=1023)
        claims(released);rebind(released,1,player=False);released['pokemonCombat']['movementTimers'][2]['movementActorControlMode']=0
        raw=bytearray.fromhex(released['pokemonCombat']['targets'][0]['motion']['rawHex']);struct.pack_into('<H',raw,40,1)
        released['pokemonCombat']['targets'][0]['motion']=decode_motion(bytes(raw));released['actors'][1]['motionElapsed']=1
        actor=released['actors'][2];value=motion(released,actor,origin=(585,409),target=(585,408))
        raw=bytearray.fromhex(value['rawHex']);raw[36]=raw[37]=1
        released['pokemonCombat']['targets'][1].update(motion=decode_motion(bytes(raw)),
            currentHp=80,hp=80,hpMirrorMatches=True,hitCount=1,lastDamage=20)
        events=[native(actor,23,'PLAN_ACCEPTED',(585<<16)|408,8,230),native(actor,23,'MOTION_STARTED',2,8,231)]
        own=dict(carrier=deepcopy(carrier['handle']),cargo=deepcopy(target['handle']),claim=19,pickup=20,
            launch=None,landed=None,cleanup=None,motion=None,recorder=None,credited=True)
        def check(fault=None):
            m=meter(old);m.latest=deepcopy(old);m.cycles[1]=deepcopy(own)
            h=deepcopy(hit);s=deepcopy(start);r=deepcopy(released);first=deepcopy(started);last=deepcopy(events)
            if fault=='missing-carrier-hit':h['pokemonCombat']['targets'][0]['hitCount']=0
            elif fault=='missing-carrier-start':first.pop()
            elif fault=='missing-carrier-plan':first.pop(0)
            for current,ev in ((h,[]),(s,first)):
                state,rows,timers,actors=ground_state(current,SOURCE)
                m._cycles(current,ev,m._actors(current),state,rows,timers,actors)
                m.previous_state=deepcopy(state);m.latest=deepcopy(current)
            if fault=='missing-receipt':m.cycles[1].pop('carrierDamage')
            elif fault=='wrong-owner':m.cycles[1]['carrierDamage']['motion']['handle']['generation']+=1
            elif fault=='wrong-hit':m.cycles[1]['carrierDamage']['hit']['after']['currentHp']-=1
            elif fault in ('unforced-carrier','wrong-plan','wrong-elapsed'):
                raw=bytearray.fromhex(r['pokemonCombat']['targets'][0]['motion']['rawHex'])
                if fault=='unforced-carrier':raw[37]=0
                elif fault=='wrong-plan':struct.pack_into('<H',raw,12,410)
                else:struct.pack_into('<H',raw,40,2);r['actors'][1]['motionElapsed']=2
                r['pokemonCombat']['targets'][0]['motion']=decode_motion(bytes(raw))
            elif fault=='canceled':last.append(native(r['actors'][1],23,'MOTION_CANCELED',0,0,232))
            elif fault=='cargo-no-hit':r['pokemonCombat']['targets'][1]['hitCount']=0
            elif fault=='cargo-held':r['pokemonCombat']['movementTimers'][2]['movementActorControlMode']=1
            state,rows,timers,actors=ground_state(r,SOURCE)
            m._cycles(r,last,m._actors(r),state,rows,timers,actors)
            return m
        m=check();self.assertEqual(m.cycles,{});self.assertEqual(m.completed,[])
        for fault in ('missing-carrier-hit','missing-carrier-start','missing-carrier-plan','missing-receipt','wrong-owner',
                      'wrong-hit','unforced-carrier','wrong-plan','wrong-elapsed','canceled','cargo-no-hit','cargo-held'):
            with self.subTest(fault=fault),self.assertRaises(ValueError):check(fault)

    def test_landing_crash_uses_exact_observed_base_after_control(self):
        def fixture():
            m=meter(sample(20));recorder=MotionRecorder();recorder.expected_pause_by_kind['HOP']=0
            for frame in range(20,29):
                s=sample(frame);target=s['actors'][2]
                value=motion(s,target,phase='IDLE' if frame==28 else 'MOVING',elapsed=frame-20,
                    commit=5 if frame==28 else 4,origin=(585,409),target=(585,417))
                raw=bytearray.fromhex(value['rawHex']);raw[3]=raw[34]=0
                s['pokemonCombat']['targets'][0]['motion']=decode_motion(bytes(raw))
                target['engineObject']['pos_z']=(409<<16)+32768+(frame-20)*65536
                if frame==20:
                    start=m._start(s,target,m._motion(s,target),m._events(s,[native(target,frame,'MOTION_STARTED',2,8,200)],target))
                if frame<28:recorder.observe(frame,target,target['engineObject'])
            target['motionKind']='NONE';claims(s,recovery=2)
            s['pokemonCombat']['movementTimers'][1].update(movementEmoteTimer=60,movementSpotState=2)
            timer=s['pokemonCombat']['movementTimers'][2];base=[(n<<16)+32768 for n in (585,417)]
            timer.update(movementCrashShakeTimer=7,movementCrashShakeBaseX=base[0],movementCrashShakeBaseZ=base[1],
                rawCrashShakeHex=struct.pack('<Bii',7,*base).hex())
            target['engineObject'].update(pos_x=base[0]-256,pos_z=base[1]+256)
            events=[native(target,28,event,A,B,sequence) for event,A,B,sequence in (
                ('LOGICAL_COMMIT',5,2,280),('MOTION_FINISHED',5,2,281),('CONTROL_RETURNED',0,5,282),('WORLD_EFFECT',3,1,283))]
            m.cycles[1]=dict(carrier=deepcopy(s['actors'][1]['handle']),cargo=deepcopy(target['handle']),
                claim=18,pickup=19,launch=20,landed=None,cleanup=None,motion=start,recorder=recorder,credited=True)
            return m,s,events
        def check(m,s,events):
            state,rows,timers,actors=ground_state(s,SOURCE)
            m._cycles(s,events,m._actors(s),state,rows,timers,actors)
        m,s,events=fixture();raw=deepcopy(s);check(m,s,events)
        own=m.cycles[1];self.assertEqual(own['landed'],28);self.assertEqual(s,raw)
        self.assertFalse(own['recorder'].failures);self.assertTrue(complete_travel(own['recorder'].completed[0]))
        receipt=own['motion']['landingPresentation']
        self.assertEqual(receipt['rawRender'],[s['actors'][2]['engineObject'][k] for k in ('pos_x','pos_y','pos_z')])
        self.assertEqual(receipt['storedEndpoint'],[(n<<16)+32768 for n in (585,417)])
        for fault in ('missing-base','wrong-base','wrong-timer','raw-bytes','wrong-render','wrong-owner',
                      'wrong-source','wrong-clock','wrong-image','missing-effect','effect-order','missing-control'):
            m,s,events=fixture();timer=s['pokemonCombat']['movementTimers'][2]
            if fault=='missing-base':timer.pop('rawCrashShakeHex')
            elif fault=='wrong-base':
                timer['movementCrashShakeBaseX']+=1
                timer['rawCrashShakeHex']=struct.pack('<Bii',7,timer['movementCrashShakeBaseX'],timer['movementCrashShakeBaseZ']).hex()
            elif fault=='wrong-timer':
                timer['movementCrashShakeTimer']=8
                timer['rawCrashShakeHex']=struct.pack('<Bii',8,timer['movementCrashShakeBaseX'],timer['movementCrashShakeBaseZ']).hex()
            elif fault=='raw-bytes':timer['rawCrashShakeHex']='00'*9
            elif fault=='wrong-render':s['actors'][2]['engineObject']['pos_x']+=1
            elif fault=='wrong-owner':timer['handle']['generation']+=1
            elif fault=='wrong-source':timer['sourceIdentity']['object']+=4
            elif fault=='wrong-clock':s['pokemonCombat']['nativeCycle']+=1
            elif fault=='wrong-image':s['pokemonCombat']['identity']['overlaySha256']='wrong'
            elif fault=='missing-effect':events.pop()
            elif fault=='effect-order':events[-1]['data']['sequence']=281
            else:events=[e for e in events if e['data']['event']!='CONTROL_RETURNED']
            with self.subTest(fault=fault),self.assertRaises(ValueError) as error:check(m,s,events)
            if fault=='missing-control':
                self.assertIn('ordered FINISH and CONTROL',str(error.exception))
                validate_negative_result(dict(passed=False,failures=[str(error.exception)]),FAULTS[3])

    def test_same_used_frame_handoff_only_allows_exact_fresh_deferred_state(self):
        s=sample();state,rows,timers,actors=ground_state(s,SOURCE)
        e=query(s,2);q=e["data"]["after"]["workspace"]
        q.update(stateSubject=None,nodeCount=0,started=False);q["compatibility"]["requestKey"]=0
        before=e["data"]["before"]["workspace"];before["owner"]=deepcopy(s["actors"][1]["handle"])
        meter(s)._query(s,e,rows,timers,actors)
        for wrong in (None,deepcopy(s["actors"][1]["handle"])):
            bad=deepcopy(e);bad["data"]["after"]["workspace"]["compatibility"]["requestKey"]=7
            bad["data"]["after"]["workspace"]["stateSubject"]=wrong
            with self.subTest(wrong=wrong),self.assertRaisesRegex(ValueError,"current query state or work"):
                meter(s)._query(s,bad,rows,timers,actors)

    def test_window_floor_never_uses_setup_frames_or_active_idle_mask(self):
        m=WildThrowSoakMeasurement(SOURCE);m.setup_frames=[600]*len(SETUP)
        self.assertEqual(m.observed_frames,0);self.assertFalse(m.result()["ready"])
        m.soak_frames=SOAK_FRAMES;m.previous_state=dict(targetMask=4,carrierMask=2,recoveringMask=0)
        self.assertTrue(m.stage("window-complete"),"valid active ownership need not be globally idle")
        m.observed_frames=MIN_FRAMES-1;self.assertFalse(m.result()["ready"])

    def test_frame_gap_control_fails_shared_raw_validation(self):
        from tools.overworld.devtools_raw_chunk import validate_raw_chunk
        s=sample();m=meter(s);r=dict(phase="observe",samples=[s],events=[],completedGameFrames=1,observedFieldFrames=1,
            nativeCycles=1,cycleIntervals=[dict(completedGameFrame=s["frame"],cpuNs=1,wallNs=1)])
        negative=WildThrowSoakNegative(FAULTS[4]);bad=negative.mutate(r,m.subjects)
        with self.assertRaisesRegex(ValueError,"raw completed samples skip") as error:validate_raw_chunk(bad,m.latest)
        validate_negative_result(dict(passed=False,failures=[str(error.exception)]),FAULTS[4])


if __name__ == "__main__": unittest.main()
