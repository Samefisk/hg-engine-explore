"""Continuous three-Geodude Throw witness over the existing native readers.

Prepared placement earns no subject frames. Native LIMIT observations are
checked when present; this case does not require or claim a native LIMIT repro.
"""
from copy import deepcopy
import struct

from tools.overworld.devtools_damage_follower_measurement import DamageFollowerMeasurement
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_wild_throw_moving_candidate_measurement import (
    THROW_APPLICATION, THROW_APPLICATION_BIT, THROW_POSITION_BIT, THROW_RELEASE_BIT,
    TRIGGER_CONDITION, CARGO_CONDITION, validate_route_binding,
)
from tools.overworld.devtools_cargo_route_continuity import profile
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor, engine_binding_identity
from tools.overworld.devtools_distance_despawn_measurement import DistanceDespawnMeasurement
from tools.overworld.normal_play_observer import MotionRecorder, complete_travel

KIND = "wild-throw-ground-lock-soak-v1"
REQUIREMENT = "current.wild-throw-ground-lock-soak"
CASE = "wild.throw-ground-lock-soak"
BOUNDARY = "main-task-queue-completion"
MIN_FRAMES, SOAK_FRAMES = 5000, 5040
LEG_FRAMES = 24  # Average over each full96-frame cycle and the final48-frame pair.
LEG_FRAME_COUNTS = (24, 32, 24, 16) * 52 + (24, 24)
DIRECTIONS = ("LEFT", "DOWN", "RIGHT", "UP")
HELD_KEYS = (34, 130, 18, 66)
CHECKPOINT_LEGS = (40, 80, 120, 160, 200)
GEODUDES = ("geodude-a", "geodude-b", "geodude-c")
SUBJECTS = tuple((name, 74, "WILD", "spawn") for name in GEODUDES) + (
    ("cargo", 70, "WILD", "spawn"), ("passive", 155, "FOLLOWER", "existing"))
SETUP = (("throw-tile", "teleport", dict(map=33, x=584, z=407, facing=1)),
         ("prepare-passive", "party", dict(slot=0, species=155, level=100)),
         ("create-passive", "spawn", dict(species=155, form=0, role="follower", slot=0, level=100)),
         ("bind-passive", "bind", dict(subject="passive")),
         ("spawn-cargo", "spawn", dict(species=70, form=0, role="wild", level=100, x=591, z=391)),
         ("bind-cargo", "bind", dict(subject="cargo"))) + tuple(
    action for name, x in zip(GEODUDES, (583, 584, 585)) for action in (
        ("spawn-" + name, "spawn", dict(species=74, form=0, role="wild", level=100, x=x, z=409)),
        ("bind-" + name, "bind", dict(subject=name)))) + (
    ("settle-fixture", "step", dict(frames=1, keys=[])),)
ACTIONS = (("before-soak", "player-health.observe", {}),) + tuple(
    action for leg, frames in enumerate(LEG_FRAME_COUNTS, 1)
    for action in ((f"soak-{leg:03}", "step", dict(frames=frames, keys=["B", DIRECTIONS[(leg-1) % 4]])),)
        + (((f"health-check-{leg:03}", "player-health.observe", {}),) if leg in CHECKPOINT_LEGS else ())) + (
    ("after-soak", "player-health.observe", {}),)
BUDGETS = dict(maxSeconds=1800, maxFrames=6800, noProgressFrames=600, minObservedFrames=MIN_FRAMES)


def require(value, reason):
    if not value:
        raise ValueError("Wild Throw soak: " + reason)


def validate_recipe(test):
    require(test["id"] == CASE and test["mode"] == "prepared"
        and test["requirements"] == [REQUIREMENT]
        and test["subjects"] == [dict(id=n, species=s, role=r, acquire=a) for n,s,r,a in SUBJECTS]
        and test["measurements"] == [dict(kind=KIND, subject=GEODUDES[0])]
        and tuple((a["id"], a["op"], a["args"]) for a in test["setup"]) == SETUP
        and tuple((a["id"], a["op"], a["args"]) for a in test["actions"]) == ACTIONS
        and all(a["budget"] == dict(maxSeconds=60, maxFrames=a["args"]["frames"], noProgressFrames=a["args"]["frames"])
                for a in test["actions"] if a["op"] == "step")
        and test["budgets"] == BUDGETS
        and test["assertions"] == [dict(kind="measurement-complete", measurement=KIND, when="final")],
        "exact Lv100 fixture, normal input or continuous window differs")


def ground_state(sample, source, owned_flight=None):
    """Authenticate the shared masks, full owners and native timer rows once."""
    combat = sample["pokemonCombat"]; value = combat["interactions"]
    require(combat.get("available") is True and value.get("available") is True
        and all(row.get("frame") == sample["frame"] and row.get("nativeCycle") == sample["nativeCycle"]
                for row in (combat, value))
        and combat.get("observationBoundary") == value.get("observationBoundary") == BOUNDARY
        and combat.get("identity", {}).get("romSha256") == value.get("identity", {}).get("romSha256") == source["romSha256"]
        and combat["identity"].get("overlaySha256") == source["overlaySha256"]
        and value.get("fieldSystem") == sample["fieldControl"]["fieldPointer"],
        "interaction owner, image or completed boundary differs")
    state = value["throwState"]; raw = bytes.fromhex(state["rawHex"])
    require(len(raw) == 16 and list(raw[:10]) == state["targets"]
        and struct.unpack_from("<3H", raw, 10) == tuple(state[k] for k in ("targetMask", "carrierMask", "recoveringMask"))
        and not (state["targetMask"] | state["carrierMask"] | state["recoveringMask"]) >> 10,
        "raw claim state differs")
    actors = {a["handle"]["slot"]: a for a in sample["actors"] if a.get("active") is True}
    rows = {}; timers = {}
    for row in value["carriers"]:
        if row.get("available") is not True: continue
        slot = row["slot"]; actor = actors.get(slot)
        require(actor is not None and row["handle"] == actor["handle"] and row["role"] == actor["role"]
            and slot not in rows, "binding has no unique full current actor")
        select_current_actor(sample, actor)
        native = bytes.fromhex(row["rawBindingsHex"])
        require(len(native) == 60 and native[:12] == raw_handle(actor["handle"]), "binding raw owner differs")
        for name, offset in (("trigger", 12), ("cargo", 36)):
            binding = row["bindings"][name]; data = native[offset:offset+24]
            require(data.hex() == binding["rawHex"] and bool(data[22]) == binding["bound"], "raw binding flags differ")
            if binding["bound"] and actor["role"] == "WILD" and (actor["species"] == 74 or raw[slot]):
                validate_route_binding(binding, "PLAYER" if name == "trigger" else "ACTOR",
                    TRIGGER_CONDITION if name == "trigger" else CARGO_CONDITION,
                    None if name == "trigger" else binding["target"]["actor"])
                if name == "cargo":
                    target = actors.get(binding["target"]["actor"]["slot"])
                    require(target is not None and target["handle"] == binding["target"]["actor"], "Cargo binding is stale")
        encoded = raw[slot]
        flags = dict(targetRaw=encoded, targetSlot=(encoded & 63)-1 if encoded else None,
            carried=bool(encoded & 128), windup=bool(encoded & 64),
            targeted=bool(state["targetMask"] & (1 << slot)),
            carrier=bool(state["carrierMask"] & (1 << slot)), recovering=bool(state["recoveringMask"] & (1 << slot)))
        require(row["throw"] == flags, "decoded claim flags differ")
        rows[slot] = row
    for timer in combat["movementTimers"]:
        slot = timer["slot"]; actor = actors.get(slot)
        require(actor is not None and timer["handle"] == actor["handle"] and slot not in timers
            and timer["sourceIdentity"] == actor["sourceIdentity"], "timer has no current native source")
        require(all(type(timer[k]) is int and 0 <= timer[k] <= 255 for k in (
            "movementCooldown", "movementEmoteTimer", "movementSpotState"))
            and timer["movementActorControlMode"] in (0, 1), "native timer or control mode differs")
        require(not (state["recoveringMask"] & (1 << slot) and timer["movementEmoteTimer"] == 0
                     and timer["movementSpotState"] == 0), "recovery survives zero timer and CHILL")
        holders = [owner for owner, encoded in enumerate(state["targets"])
                   if encoded & 128 and encoded & 63 == slot + 1]
        flight = False
        if state["targetMask"] & (1 << slot) and actor["motionKind"] == "HOP" \
                and actor["motionPhase"] in ("MOVING", "COMMIT_PENDING", "SETTLING"):
            motion = DamageFollowerMeasurement._motion(None, sample, actor)
            flight = motion["phase"] == actor["motionPhase"] and motion["plan"]["kind"] == 2 \
                and motion["plan"]["fieldEpoch"] == actor["handle"]["fieldEpoch"] \
                and owned_flight is not None and owned_flight(actor, motion)
        require(timer["movementActorControlMode"] == 0 or len(holders) == 1 or flight,
                "grounded HELD actor has no carrier or launched flight")
        require(len(holders) <= 1, "Cargo has more than one carrier")
        if holders:
            require(timer["movementActorControlMode"] == 1 and state["carrierMask"] & (1 << holders[0])
                and state["targetMask"] & (1 << slot), "pickup lost its held owner or claim")
        timers[slot] = timer
    return state, rows, timers, actors


class WildThrowSoakMeasurement:
    # The established native plan and ordered COMMIT/FINISH/CONTROL checks are
    # shared unchanged. This class adds no movement or attack implementation.
    _motion = DamageFollowerMeasurement._motion
    _start = DamageFollowerMeasurement._start
    _advance = DamageFollowerMeasurement._advance
    _pose = staticmethod(DamageFollowerMeasurement._pose)

    def __init__(self, source):
        require(source["contractVersion"] == 2, "sealed current query source is missing")
        require(type(source.get("helperAddress")) is int and source["helperAddress"]>0
            and isinstance(source.get("helperEntrySha256"),str) and len(source["helperEntrySha256"])==64
            and all(c in "0123456789abcdef" for c in source["helperEntrySha256"]),
                "sealed current distance helper is missing")
        self.source = source
        self.latest = self.context = None
        self.subjects = {}; self.profiles = {}; self.failures = []
        self.setup_index = self.action_index = self.observed_frames = self.soak_frames = 0
        self.action_frames = [0] * len(ACTIONS); self.setup_frames = [0] * len(SETUP)
        self.window_start = self.window_end = None
        self.previous_state = None; self.cycles = {}; self.completed = []
        self.interests = dict.fromkeys(GEODUDES, 0); self.queries = dict.fromkeys(GEODUDES, 0)
        self.motion_returns = dict.fromkeys(GEODUDES, 0)
        self.ground_motions = {}
        self.recovery_pickups = []; self.limits = {}; self.query_count = self.limit_count = 0
        self.last_query_sequence = -1; self.health_before = self.health_after = None
        self.health_checkpoints = []
        self.cargo_exit = None
        self.blocked_releases = []
        self.pending_faint_retirements = {}; self.fainted_flight_retirements = []
        self.primary_zeroes = {}; self.primary_retirements = {}
        self.primary_current_frames = dict.fromkeys(GEODUDES, 0)
        self.primary_healthy_frames = dict.fromkeys(GEODUDES, 0)

    def _boundary(self, sample, fixture=True):
        require(sample.get("fieldAvailable") is True and sample.get("observationBoundary") == BOUNDARY
            and sample.get("romSha256") == self.source["romSha256"]
            and sample.get("fieldControl", {}).get("taskPointer") == 0
            and all(type(sample.get(k)) is int for k in ("frame", "nativeCycle", "actorFrame")),
            "current completed Field boundary is missing")
        if fixture:
            require(sample["context"]["mapId"] == 33 and sample.get("selector", {}).get("state") == 0,
                    "left normal Route29 control")
        if self.context is not None: require(sample["context"] == self.context, "Field context changed")
        native = sample.get("nativeObservation", {})
        require(native.get("error") is None and native.get("coverageComplete") is True
            and native.get("eventsDropped") == 0, "native observation coverage is incomplete")

    def _actors(self, sample):
        result = {}
        for name,species,role,_ in SUBJECTS:
            if name == "cargo" and self.cargo_exit is not None: continue
            if name in self.primary_retirements: continue
            selected = select_current_actor(sample, self.subjects[name])
            actor = next(a for a in sample["actors"] if a["handle"] == selected["handle"])
            require(actor["species"] == species and actor["role"] == role
                and actor["level"] == 100
                and actor.get("presentationAttached") is True, "exact current Lv100 subjects changed")
            result[name] = actor
        require(len({a["handle"]["value"] for a in result.values()}) == len(result), "subjects are not distinct")
        require(not result["passive"]["matchedLayerMask"] & (THROW_APPLICATION_BIT | THROW_POSITION_BIT | THROW_RELEASE_BIT),
                "passive follower selected Throw")
        return result

    def _primary_hp(self, sample, actor):
        combat=sample["pokemonCombat"]; handle=actor["handle"]
        health=[r for r in combat["targets"] if r.get("handle")==handle]
        require(combat.get("available") is True and combat["frame"]==sample["frame"]
            and combat["nativeCycle"]==sample["nativeCycle"] and combat["observationBoundary"]==BOUNDARY
            and combat["identity"]["romSha256"]==self.source["romSha256"]
            and combat["identity"]["overlaySha256"]==self.source["overlaySha256"] and len(health)==1,
                "primary lacks its current native HP owner")
        hp=health[0]
        require(hp.get("hpMirrorMatches") is True and hp.get("initialized")==1
            and hp.get("hpSource")=="wild-resident" and hp.get("personality")==actor["subjectIdentity"]
            and all(hp.get(k)==actor[k] for k in ("species","form","level"))
            and hp.get("mapId")==sample["context"]["mapId"]
            and hp.get("mapGeneration")==handle["mapGeneration"]
            and hp.get("encounterGeneration")==handle["encounterGeneration"]
            and type(hp.get("currentHp")) is int and 0<=hp["currentHp"]==hp.get("hp")<=hp["maxHp"]
            and hp["maxHp"]==hp.get("actualMaxHp") and type(hp.get("hitCount")) is int,
                "primary native HP identity or mirror differs")
        return hp

    def _primary_zero(self, sample, events, actor, hp, record):
        prior=next(a for a in self.latest["actors"] if a["handle"]==actor["handle"])
        select_current_actor(self.latest,prior)
        before=self._primary_hp(self.latest,prior)
        motion=self._motion(sample,actor); old=self._motion(self.latest,prior); native=self._events(sample,events,actor)
        if record is None:
            require(before["currentHp"]>0 and hp["hitCount"]==before["hitCount"]+1
                and hp.get("lastDamage")==before["currentHp"] and hp.get("knockbackPending")==0,
                    "primary faint lacks a fresh accepted native final hit")
            record=dict(hitFrame=sample["frame"],handle=deepcopy(actor["handle"]),
                priorHp=deepcopy(before),zeroHp=deepcopy(hp),terminal=None,
                deadline=sample["frame"]+max(0,old["plan"]["duration"]-old["elapsed"])
                    +(old["plan"]["pauseFrames"] if old["phase"]=="MOVING" else old["settleRemaining"]))
        else:
            require(all(hp[k]==record["zeroHp"][k] for k in ("hp","currentHp","hitCount","lastDamage","knockbackPending")),
                    "primary HP0 receipt changed before native retirement")
        require(sample["actorFrame"]==self.latest["actorFrame"]+1
            and actor["sourceIdentity"]==prior["sourceIdentity"]
            and engine_binding_identity(actor["engineIdentity"])==engine_binding_identity(prior["engineIdentity"])
            and motion["plan"]==old["plan"] and sample["frame"]<=record["deadline"]
            and not any(e.get("event") in ("INTENT_CREATED","PLAN_ACCEPTED","MOTION_STARTED","MOTION_CANCELED") for e in native),
                "primary faint replaced its accepted primitive or native owner")
        if actor["motionPhase"]!="IDLE":
            require(record["terminal"] is None and motion["phase"]==actor["motionPhase"]
                and motion["plan"]["fieldEpoch"]==actor["handle"]["fieldEpoch"]
                and motion["elapsed"]==actor["motionElapsed"] and actor["motionDuration"]==motion["plan"]["duration"],
                    "primary HP0 lacks exact remaining accepted motion")
            edges=[e for e in native if e.get("event") in ("LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED")]
            if motion["phase"]==old["phase"]=="MOVING":
                require(actor["reservationId"]==prior["reservationId"]==motion["plan"]["reservationId"]>0
                    and motion["elapsed"]==old["elapsed"]+1<motion["plan"]["duration"]
                    and actor["commitSequence"]==prior["commitSequence"] and not edges,
                        "primary HP0 changed remaining accepted travel")
            elif old["phase"]=="MOVING" and motion["phase"]=="SETTLING":
                n=prior["commitSequence"]+1
                require(old["elapsed"]==motion["plan"]["duration"]-1 and prior["reservationId"]==motion["plan"]["reservationId"]>0
                    and motion["elapsed"]==motion["plan"]["duration"] and actor["reservationId"]==0
                    and actor["commitSequence"]==n and motion["commitPublished"]==1 and len(edges)==1
                    and edges[0].get("event")=="LOGICAL_COMMIT" and edges[0].get("reason")=="OK"
                    and (edges[0].get("valueA"),edges[0].get("valueB"))==(n,motion["plan"]["kind"])
                    and [actor["logical"][k] for k in ("x","y")]==motion["plan"]["target"]
                    and motion["settleRemaining"]==motion["plan"]["pauseFrames"]>0,
                        "primary HP0 settling lacks its accepted logical COMMIT")
                record["commit"]=deepcopy(edges[0])
            else:
                require(motion["phase"]==old["phase"]=="SETTLING" and motion["commitPublished"]==old["commitPublished"]==1
                    and actor["reservationId"]==prior["reservationId"]==0
                    and actor["commitSequence"]==prior["commitSequence"] and motion["elapsed"]==old["elapsed"]
                    and motion["settleRemaining"]==old["settleRemaining"]-1>0 and not edges,
                        "primary HP0 changed accepted settling")
            return record
        plan=motion["plan"]; terminal=[e for e in native if e.get("event") in (
            "LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED")]
        require(actor["motionKind"]=="NONE" and actor["reservationId"]==0 and motion["phase"]=="IDLE",
                "primary faint did not return its accepted control")
        if prior["motionPhase"]=="MOVING":
            n=prior["commitSequence"]+1
            require(old["elapsed"]==prior["motionElapsed"]==plan["duration"]-1
                and old["commitPublished"]==0 and old["cancelReason"]==0
                and prior["reservationId"]==plan["reservationId"]>0
                and motion["elapsed"]==actor["motionElapsed"]==actor["motionDuration"]==plan["duration"]
                and motion["commitPublished"]==1 and actor["commitSequence"]==n
                and [actor["logical"][k] for k in ("x","y")]==plan["target"]
                and self._pose(actor)[2]==plan["targetBaseY"]
                and [e.get("event") for e in terminal]==["LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED"]
                and [(e.get("valueA"),e.get("valueB")) for e in terminal]==[(n,plan["kind"]),(n,plan["kind"]),(0,n)]
                and all(e.get("reason")=="OK" and e.get("traceFieldEpoch")==actor["handle"]["fieldEpoch"] for e in terminal)
                and terminal[0]["sequence"]<terminal[1]["sequence"]<terminal[2]["sequence"],
                    "primary faint lacks exact accepted COMMIT FINISH CONTROL")
        elif prior["motionPhase"]=="SETTLING":
            n=prior["commitSequence"]
            require(old["settleRemaining"]==1 and old["commitPublished"]==motion["commitPublished"]==1
                and motion["elapsed"]==actor["motionElapsed"]==plan["duration"] and actor["commitSequence"]==n
                and prior["reservationId"]==0
                and [e.get("event") for e in terminal]==["MOTION_FINISHED","CONTROL_RETURNED"]
                and [(e.get("valueA"),e.get("valueB")) for e in terminal]==[(n,plan["kind"]),(0,n)]
                and all(e.get("reason")=="OK" for e in terminal)
                and terminal[0]["sequence"]<terminal[1]["sequence"]
                and self._pose(actor)[2]==plan["targetBaseY"],"primary faint lacks exact settling FINISH CONTROL")
        else:
            require(prior["motionPhase"]=="IDLE" and prior["motionKind"]=="NONE" and prior["reservationId"]==0
                and not terminal and all(actor[k]==prior[k] for k in (
                    "commitSequence","motionElapsed","motionDuration","origin","target","logical")),
                    "idle primary faint changed its last completed motion")
        record.update(terminal=deepcopy(terminal),terminalFrame=sample["frame"],
            terminalActorFrame=sample["actorFrame"],terminalActor=deepcopy(actor),plan=deepcopy(plan),
            lastSequence=max((e["sequence"] for e in native),default=-1))
        return record

    def _primary_lifetimes(self, sample, events):
        healthy=[]
        for name in GEODUDES:
            subject=self.subjects[name];handle=subject["handle"];slot=handle["slot"]
            current=[a for a in sample["actors"] if a["handle"]==handle]
            retired=self.primary_retirements.get(name)
            if retired is not None:
                require(not current,"retired primary returned under its old full handle")
                if retired["detach"] is None:
                    self._faint_released(sample,handle)
                    native=[e for e in events if e.get("kind")=="native" and e.get("data",{}).get("actorHandle")==handle["value"]]
                    require(sample["frame"]==retired["frame"]+1 and sample["actorFrame"]==retired["actorFrame"]+1
                        and len(native)==1,"primary faint lacks adjacent completed-frame DETACH")
                    e=native[0];d=e["data"]
                    require(e["frame"]==sample["frame"] and d.get("event")=="ACTOR_DETACHED" and d.get("reason")=="OK"
                        and d.get("actor")=={k:v for k,v in handle.items() if k!="value"}
                        and d.get("frame")==d.get("actorFrame")==retired["actorFrame"]
                        and d.get("traceFieldEpoch")==handle["fieldEpoch"] and d.get("valueA")==1
                        and d.get("valueB")==subject["subjectIdentity"] and type(d.get("sequence")) is int
                        and d["sequence"]>retired["lastSequence"],"primary faint DETACH owner, clock or order differs")
                    retired["detach"]=deepcopy(e)
                else:
                    combat=sample["pokemonCombat"];value=combat["interactions"];state=value["throwState"]
                    require(not any(r.get("handle")==handle for r in combat["targets"]+combat["movementTimers"]+value["carriers"])
                        and not any(b.get("bound") and b.get("target")==dict(kind="ACTOR",actor=handle)
                            for r in value["carriers"] for b in r["bindings"].values())
                        and not any(e.get("kind")=="native" and e.get("data",{}).get("actorHandle")==handle["value"] for e in events),
                            "retired primary retained its old native owner or binding")
                    if state["targets"][slot] or (state["targetMask"]|state["carrierMask"]|state["recoveringMask"])&(1<<slot) \
                            or any(n and n&63==slot+1 for n in state["targets"]):
                        replacements=[a for a in sample["actors"] if a["handle"]["slot"]==slot and a.get("active") is True]
                        require(len(replacements)==1 and replacements[0]["handle"]!=handle,
                                "retired primary slot claim has no distinct current owner")
                        select_current_actor(sample,replacements[0])
                continue
            require(len(current)==1,"primary disappeared without authenticated native faint cleanup")
            actor=current[0]
            if actor.get("identityVerified") is True:
                select_current_actor(sample,subject);hp=self._primary_hp(sample,actor)
                if hp["currentHp"]>0:
                    require(name not in self.primary_zeroes,"fainted primary became healthy without retirement")
                    healthy.append(name)
                    continue
                self.primary_zeroes[name]=self._primary_zero(sample,events,actor,hp,self.primary_zeroes.get(name))
                for own in self.cycles.values():
                    if handle in (own["carrier"],own["cargo"]):own["credited"]=False
                continue
            zero=self.primary_zeroes.get(name);prior=next(a for a in self.latest["actors"] if a["handle"]==handle)
            require(zero is not None and zero["terminal"] is not None and zero["terminalFrame"]==self.latest["frame"]
                and sample["actorFrame"]==self.latest["actorFrame"]+1,
                    "primary missing identity lacks prior fresh HP0 and completed control")
            engine=actor["engineIdentity"];source=actor["sourceIdentity"];lookup=engine.get("id_lookup",{})
            require(actor.get("active") is True and actor.get("presentationAttached") is True and "engineObject" not in actor
                and all(actor[k]==prior[k] for k in ("subjectIdentity","species","form","level","role","authorityGeneration",
                    "engineAnchorGeneration","presentationGeneration","motionKind","motionPhase","motionElapsed",
                    "motionDuration","reservationId","commitSequence","origin","target","logical"))
                and engine.get("pointer")==0 and engine.get("in_manager") is False and engine.get("active") is False
                and lookup.get("status")=="complete" and lookup.get("eligible_count")==0
                and lookup.get("first_active_pointer")==0 and lookup.get("matching_objects")==[]
                and all(source.get(k)==0 for k in ("object","active","personality","species","form","level"))
                and source.get("map_id")==1 and source.get("object_id")==prior["sourceIdentity"]["object_id"]
                and source.get("encounter_generation")==handle["encounterGeneration"],
                    "primary faint lacks exact cleared native terminal shell")
            self._faint_released(sample,handle)
            old=self.latest["pokemonCombat"]["interactions"]["throwState"]
            state=sample["pokemonCombat"]["interactions"]["throwState"];released=[]
            if old["targets"][slot]&128:
                cargo_slot=(old["targets"][slot]&63)-1
                cargo=next(a for a in self.latest["actors"] if a["handle"]["slot"]==cargo_slot)
                selected=select_current_actor(sample,cargo)
                now=next(a for a in sample["actors"] if a["handle"]==selected["handle"])
                before=next(t for t in self.latest["pokemonCombat"]["movementTimers"] if t["handle"]==cargo["handle"])
                after=next(t for t in sample["pokemonCombat"]["movementTimers"] if t["handle"]==cargo["handle"])
                pose=now["engineObject"];anchor=prior["engineObject"]
                require(before["movementActorControlMode"]==1 and after["movementActorControlMode"]==0
                    and now["sourceIdentity"]==cargo["sourceIdentity"]
                    and engine_binding_identity(now["engineIdentity"])==engine_binding_identity(cargo["engineIdentity"])
                    and all(pose[k]==anchor[k] for k in ("x","y","pos_x","pos_y","pos_z"))
                    and pose["unk88_y"]==0 and not state["targetMask"]&(1<<cargo_slot)
                    and not any(n and n&63==cargo_slot+1 for n in state["targets"])
                    and not any(e.get("event") in ("INTENT_CREATED","PLAN_ACCEPTED","MOTION_STARTED","MOTION_CANCELED")
                        for e in self._events(sample,events,now)),"primary faint did not ground and release its exact HELD Cargo")
                released.append(deepcopy(cargo["handle"]))
            for carrier_slot,n in enumerate(old["targets"]):
                if n&128 and carrier_slot!=slot and n&63!=slot+1:
                    target_slot=(n&63)-1
                    require(state["targets"][carrier_slot]==n and state["carrierMask"]&(1<<carrier_slot)
                        and state["targetMask"]&(1<<target_slot),"primary faint disturbed another owned HELD pair")
            for owner,own in list(self.cycles.items()):
                if handle in (own["carrier"],own["cargo"]):
                    del self.cycles[owner]
            require(all(c["cleanup"]<zero["hitFrame"] for c in self.completed
                if handle in (c["carrier"],c["cargo"])),"primary faint earned a later completed Throw")
            self.ground_motions.pop(name,None)
            record=dict(zero,frame=sample["frame"],actorFrame=sample["actorFrame"],detach=None,
                releasedCargo=released,clearedShell=deepcopy(actor))
            self.primary_retirements[name]=record
        require(len(healthy)>=2,"fewer than two original primaries remain healthy and current")
        for name in healthy:
            self.primary_current_frames[name]+=1;self.primary_healthy_frames[name]+=1

    def primary_subject_retired(self, sample, subject):
        """Expose only this meter's proved initial-owner lifetime to the controller."""
        try:
            if self.failures or self.latest is None: return False
            name=next((n for n in GEODUDES if subject==self.subjects.get(n)),None)
            record=self.primary_retirements.get(name)
            if record is None or record["handle"]!=subject["handle"] or sample["frame"]<record["frame"]:
                return False
            self._boundary(sample)
            if sample["context"]!=self.context or any(sample[k]!=self.latest[k] for k in (
                    "frame","actorFrame","nativeCycle","actors","pokemonCombat","fieldControl")):
                return False
            handle=record["handle"];current=[a for a in sample["actors"] if a["handle"]==handle]
            if sample["frame"]==record["frame"]:
                self._faint_released(sample,handle)
                return current==[record["clearedShell"]] and record["zeroHp"]["currentHp"]==0 \
                    and record["zeroHp"]["personality"]==subject["subjectIdentity"]
            event=record["detach"]
            if event is None or current or event["frame"]!=record["frame"]+1 or sample["frame"]<event["frame"]:
                return False
            data=event["data"]
            return data.get("event")=="ACTOR_DETACHED" and data.get("reason")=="OK" \
                and data.get("actorHandle")==handle["value"] and data.get("actor")=={k:v for k,v in handle.items() if k!="value"} \
                and data.get("frame")==data.get("actorFrame")==record["actorFrame"] \
                and data.get("traceFieldEpoch")==handle["fieldEpoch"] and data.get("valueA")==1 \
                and data.get("valueB")==subject["subjectIdentity"] and data.get("sequence",-1)>record["lastSequence"]
        except (KeyError,TypeError,ValueError):
            return False

    def _optional_cargo_exit(self, sample, events):
        """Only the spare setup Cargo may leave through native distance cleanup."""
        subject=self.subjects["cargo"]; handle=subject["handle"]; slot=handle["slot"]; bit=1<<slot
        current=[a for a in sample["actors"] if a["handle"]==handle]
        if self.cargo_exit is not None:
            require(not current, "distance-removed optional Cargo returned")
            if self.cargo_exit["detach"] is None:
                native=[e for e in events if e.get("kind")=="native" and e.get("data",{}).get("actorHandle")==handle["value"]]
                require(sample["frame"]==self.cargo_exit["frame"]+1 and len(native)==1,
                        "optional Cargo lacks ordered native DETACH")
                e=native[0]; d=e["data"]
                require(e["frame"]==sample["frame"] and d.get("event")=="ACTOR_DETACHED" and d.get("reason")=="OK"
                    and d.get("actor")=={k:v for k,v in handle.items() if k!="value"}
                    and d.get("frame")==d.get("actorFrame")==self.cargo_exit["actorFrame"]
                    and d.get("traceFieldEpoch")==handle["fieldEpoch"] and type(d.get("sequence")) is int
                    and d["sequence"]>self.cargo_exit["lastNativeSequence"]
                    and d.get("valueA")==1 and d.get("valueB")==subject["subjectIdentity"],
                        "optional Cargo DETACH owner, clock or order differs")
                self.cargo_exit["detach"]=deepcopy(e)
            return
        if len(current)==1 and current[0].get("identityVerified") is True: return
        prior=next(a for a in self.latest["actors"] if a["handle"]==select_current_actor(self.latest,subject)["handle"])
        require(len(current)==1 and prior["species"]==70 and prior["role"]=="WILD" and prior["level"]==100
            and prior["motionKind"]=="NONE" and prior["motionPhase"]=="IDLE" and prior["reservationId"]==0
            and not any(c["cargo"]==handle or c["carrier"]==handle for c in self.cycles.values()),
                "optional Cargo vanished while owned or moving")
        actor=current[0]; engine=actor["engineIdentity"]; source=actor["sourceIdentity"]
        require(actor.get("identityVerified") is False and "engineObject" not in actor
            and all(actor[k]==prior[k] for k in ("subjectIdentity","species","role","authorityGeneration","engineAnchorGeneration","presentationGeneration"))
            and actor["motionKind"]=="NONE" and actor["motionPhase"]=="IDLE" and actor["reservationId"]==0
            and engine.get("pointer")==0 and engine.get("in_manager") is False and engine.get("active") is False
            and engine.get("id_lookup",{}).get("status")=="complete" and engine["id_lookup"].get("eligible_count")==0
            and all(source.get(k)==0 for k in ("object","active","personality","species","form","level"))
            and source.get("object_id")==prior["sourceIdentity"]["object_id"]
            and source.get("encounter_generation")==handle["encounterGeneration"],
                "optional Cargo lacks exact cleared native source")
        health=[r for r in self.latest["pokemonCombat"]["targets"] if r["handle"]==handle]
        timers=[r for r in self.latest["pokemonCombat"]["movementTimers"] if r["handle"]==handle]
        require(len(health)==len(timers)==1 and health[0]["currentHp"]>0 and health[0]["hpMirrorMatches"] is True
            and timers[0]["movementActorControlMode"]==0, "optional Cargo was fainted or HELD")
        def free(state):
            return state["targets"][slot]==0 and not any(n and n&63==slot+1 for n in state["targets"]) \
                and not (state["targetMask"]|state["carrierMask"]|state["recoveringMask"])&bit
        for value in (self.latest["pokemonCombat"]["interactions"],sample["pokemonCombat"]["interactions"]):
            require(free(value["throwState"]) and not any(r.get("available") and any(
                b.get("bound") and b.get("target")==dict(kind="ACTOR",actor=handle) for b in r["bindings"].values())
                for r in value["carriers"]), "optional Cargo removal retained a claim")
        receipts=[e for e in events if e.get("kind")=="native-observation" and e.get("data",{}).get("observation")=="distance-maintenance"]
        require(len(receipts)==1, "optional Cargo lacks native distance receipt")
        event=receipts[0]; d=event["data"]; world=d["worldContext"]
        require(event["frame"]==sample["frame"] and d.get("scope")=="native scheduled distance-maintenance entry/return"
            and d.get("acceptedProof") is False and d.get("diagnosticOnly") is True and d.get("setupMode")=="prepared"
            and type(d.get("sequence")) is int and d["sequence"]>0
            and self.latest["actorFrame"]<=d["entryActorFrame"]==d["returnActorFrame"]==sample["actorFrame"]
            and self.latest["nativeCycle"]<=d["entryNativeCycle"]<=d["returnNativeCycle"]<=sample["nativeCycle"]
            and all(world[k]==sample["context"][k] for k in ("mapId","fieldEpoch","mapGeneration"))
            and d["fieldPointer"]==world["fieldPointer"]==sample["fieldControl"]["fieldPointer"]
            and d["statePointer"]==world["statePointer"], "optional Cargo distance owner or clock differs")
        call=sample["nativeObservation"].get("calls",{}).get("distance-maintenance",{})
        require(call.get("address")==self.source["helperAddress"] and call.get("entrySha256")==self.source["helperEntrySha256"]
            and call.get("nonmatchingEntries")==0, "optional Cargo distance helper differs from sealed body")
        before,after=d["before"],d["after"]
        DistanceDespawnMeasurement._state(None,before); telemetry=DistanceDespawnMeasurement._state(None,after)
        step=(after["telemetrySequence"]-before["telemetrySequence"])&65535
        require(0<step<=8, "optional Cargo distance telemetry is missing or overwritten")
        fresh=[]
        for offset in range(1,step+1):
            found=[r for r in telemetry if r["sequence"]==(before["telemetrySequence"]+offset)&65535]
            require(len(found)==1, "optional Cargo distance telemetry sequence differs"); fresh.extend(found)
        deletes=[r for r in fresh if r["slot"]==slot]
        require(len(deletes)==1 and free(before["throwState"]) and free(after["throwState"])
            and not (d["hardProtectedMask"]|d["movementDeferredMask"])&bit
            and before["farSamples"][slot] in (1,2) and after["farSamples"][slot]==0
            and not after["distanceDespawnPendingMask"]&bit, "optional Cargo distance cleanup is protected or unconfirmed")
        r=deletes[0]
        require(r["reason"]==3 and r["action"]==1 and r["contextFlags"]==61
            and r["objectPtr"]==prior["engineIdentity"]["pointer"] and r["objectFlags"]&1
            and r["personality"]==subject["subjectIdentity"] and r["mapId"]==r["spawnMapId"]==33
            and r["mapGeneration"]==handle["mapGeneration"] and r["encounterGeneration"]==handle["encounterGeneration"]
            and r["objectId"]==r["expectedObjectId"]==prior["sourceIdentity"]["object_id"]
            and [r["objectX"],r["objectY"]]==[prior["engineObject"][k] for k in ("x","y")]
            and [r["playerX"],r["playerY"]]==[sample["player"][k] for k in ("x","y")]
            and r["distance"]>16 and max(abs(r["objectX"]-r["playerX"]),abs(r["objectY"]-r["playerY"]))==r["distance"],
                "optional Cargo distance DELETE identity or distance differs")
        self.cargo_exit=dict(frame=sample["frame"],actorFrame=sample["actorFrame"],handle=deepcopy(handle),
            distanceReceipt=deepcopy(event),telemetry=deepcopy(r),detach=None,
            lastNativeSequence=max((e["data"]["sequence"] for e in events if e.get("kind")=="native"),default=0))

    @staticmethod
    def _ready(actor, rows, timers):
        slot = actor["handle"]["slot"]; row = rows[slot]; timer = timers[slot]
        return actor["role"] == "WILD" and actor["species"] == 74 \
            and actor["motionPhase"] == "IDLE" and actor["reservationId"] == 0 \
            and timer["movementActorControlMode"] == timer["movementCooldown"] == timer["movementEmoteTimer"] == 0 \
            and row["bindings"]["trigger"]["bound"] and row["bindings"]["trigger"]["targetCurrent"] \
            and row["bindings"]["trigger"]["target"] == dict(kind="PLAYER", actor=None) \
            and not row["bindings"]["cargo"]["bound"] \
            and not any(row["throw"][k] for k in ("targetRaw", "carrier", "targeted", "recovering"))

    def _query(self, sample, event, rows, timers, actors):
        d = event["data"]; actor = actors[d["slot"]]; raw = bytes.fromhex(d["resultHex"])
        identity = d["imageIdentity"]; after = d["after"]; q = after["workspace"]
        require(event["frame"] == sample["frame"] and d["subject"] == actor["handle"]
            and d["boundary"] == "native-cargo-tick-return"
            and d["entryActorFrame"] == d["returnActorFrame"] == sample["actorFrame"]
            and self.latest["nativeCycle"] < d["entryNativeCycle"] <= d["returnNativeCycle"] <= sample["nativeCycle"]
            and all(identity.get(k) == self.source["queryImage"][k] for k in ("elfSha256", "packageSha256"))
            and type(identity.get("loadedEntry")) is int and identity["loadedEntry"] > 0
            and identity.get("tickEntry", 0) > identity["loadedEntry"] and len(bytes.fromhex(identity["loaderOwner"])) == 28
            and len(raw) == 140 and d["returnValue"] == d["resultStatus"] == raw[138] in range(5)
            and d["status"] == ("PENDING", "REACHABLE", "UNREACHABLE", "INVALID", "RESOURCE_LIMIT")[raw[138]]
            and after["subject"] == after["worldSubject"] == actor["handle"]
            and after["frameValid"] is True and after["worldFrame"] == sample["actorFrame"]
            and type(d["sequence"]) is int and d["sequence"] > self.last_query_sequence,
            "native query image, result, full owner or clock differs")
        require(struct.unpack_from("<H", raw, 124)[0] <= 16 and raw[127] + raw[128] <= 1,
                "native query work budget exceeded")
        self.last_query_sequence = d["sequence"]; self.query_count += 1
        for name in GEODUDES:
            if name not in self.primary_zeroes and self.subjects[name]["handle"] == actor["handle"]: self.queries[name] += 1
        if q is None:
            require(after["queryPointer"] == 0 and raw[138] == 0, "absent workspace granted a route")
            return
        require(type(after["queryPointer"]) is int and after["queryPointer"] > 0
            and 0 <= q["nodeCount"] <= 256, "query workspace extent differs")
        owner = actors.get((q.get("owner") or {}).get("slot"))
        current = owner is not None and owner["handle"] == q["owner"] and q.get("ownerCurrent") is True
        key = (after["queryPointer"], raw_handle(q["owner"]) if q.get("owner") else None)
        if raw[138] in (2, 4):
            self.limit_count += raw[138] == 4
            if current and q["valid"] and self._ready(owner, rows, timers):
                self.limits[key] = (q["stateFrame"], q["nodeCount"], q["storage"], d["status"])
        elif key in self.limits:
            same = self.limits[key][:3] == (q["stateFrame"], q["nodeCount"], q["storage"])
            if not current or not q["valid"] or not same:
                del self.limits[key]
            else:
                require(not (raw[138] == 0 and actor["handle"] != owner["handle"]
                    and self._ready(actor, rows, timers) and self._ready(owner, rows, timers)),
                    "terminal " + self.limits[key][3] + " owner blocks another ready idle unclaimed search")
        if current and q["owner"] == actor["handle"] and q["valid"] and q["stateFrame"] == sample["actorFrame"]:
            fresh_deferred = raw[138] == 0 and q["compatibility"]["requestKey"] == 0 \
                and q["stateSubject"] is None and q["nodeCount"] == 0 and q.get("started") is False \
                and raw[108:136] == bytes(28)
            require((fresh_deferred or q["stateSubject"] == actor["handle"])
                and raw[108:136].hex() == q["lastWorkHex"],
                    "current query state or work receipt differs")

    def _events(self, sample, events, actor):
        result = []
        for event in events:
            d = event.get("data", {})
            if event.get("kind") == "trace-status":
                require(d.get("coverageComplete", True) is True and d.get("unreadEventsLost", 0) == 0,
                        "semantic trace is incomplete")
            if event.get("kind") == "native" and d.get("actorHandle") == actor["handle"]["value"]:
                clock=sample["actorFrame"]
                current=type(d.get("frame")) is int and type(d.get("actorFrame")) is int \
                    and d["frame"]==d["actorFrame"]==clock
                if not current and d.get("event")=="LANE_CHANGED":
                    prior=next((a for a in (self.latest or {}).get("actors",[]) if a["handle"]==actor["handle"]),None)
                    current=prior is not None and type(d.get("frame")) is int and type(d.get("actorFrame")) is int \
                        and d["frame"]==d["actorFrame"]==self.latest.get("actorFrame")==clock-1 \
                        and prior.get("laneId")!=actor.get("laneId") and d.get("reason")=="OK" \
                        and d.get("valueA")==prior.get("laneId") and d.get("valueB")==actor.get("laneId")
                require(d.get("actor") == {k:v for k,v in actor["handle"].items() if k != "value"}
                    and current, "semantic event owner or clock differs")
                result.append(d)
        return result

    def _owned_flight(self, sample, events, target, motion):
        owners=[c for c in self.cycles.values() if c["cargo"]==target["handle"]
                and c["pickup"] is not None and c["landed"] is None]
        if not owners: return False
        require(len(owners)==1, "flight has more than one owned cycle")
        own=owners[0]
        if own["launch"] is not None:
            require(own["motion"]["handle"]==target["handle"] and motion["plan"]==own["motion"]["plan"],
                    "owned flight plan or full owner differs")
            return True
        slot=own["carrier"]["slot"]; cargo=target["handle"]["slot"]
        prior=next((a for a in self.latest["actors"] if a["handle"]==own["carrier"]),None)
        carrier=next((a for a in sample["actors"] if a["handle"]==own["carrier"]),None)
        old=self.previous_state; state=sample["pokemonCombat"]["interactions"]["throwState"]
        row=next((r for r in sample["pokemonCombat"]["interactions"]["carriers"] if r["handle"]==own["carrier"]),None)
        require(prior is not None and carrier is not None and row is not None and old is not None
            and own["pickup"]<sample["frame"] and old["targets"][slot]&0xC0==0xC0
            and old["targets"][slot]&63==cargo+1 and old["carrierMask"]&(1<<slot)
            and old["targetMask"]&(1<<cargo) and state["targets"][slot]==0
            and not state["carrierMask"]&(1<<slot) and state["recoveringMask"]&(1<<slot)
            and state["targetMask"]&(1<<cargo) and not any(row["bindings"][k]["bound"] for k in ("trigger","cargo")),
                "launch lost its exact held carrier/Cargo release")
        lane=profile(self.profiles.get(prior["behaviorFingerprint"]),prior,self.source)
        plan=motion["plan"]; native=self._events(sample,events,target)
        starts=[e for e in native if e.get("event")=="MOTION_STARTED"]
        accepted=[e for e in native if e.get("event")=="PLAN_ACCEPTED"]
        require(prior["matchedLayerMask"]&THROW_RELEASE_BIT and lane[0]==12
            and plan["kind"]==2 and plan["flags"]==0
            and plan["behaviorFingerprint"]==target["behaviorFingerprint"]&65535
            and plan["origin"]==[prior["engineObject"][k] for k in ("x","y")]
            and 0<plan["distance"]<=lane[76] and len(accepted)==len(starts)==1
            and accepted[0]["reason"]=="OK" and accepted[0]["sequence"]<starts[0]["sequence"]
            and accepted[0]["valueA"]==(((plan["target"][0]&65535)<<16)|(plan["target"][1]&65535))
            and accepted[0]["valueB"]==plan["duration"], "launch lacks its current Throw profile and admitted plan")
        self._start(sample,target,motion,native)
        return True

    def _ordinary_carrier_continuation(self, sample, actor, motion, native):
        """A Cargo hit can release a holder before its accepted move ends."""
        prior = next((a for a in self.latest['actors'] if a['handle'] == actor['handle']), None)
        if prior is None or prior['motionPhase'] != 'MOVING' or prior['motionKind'] not in ('WALK', 'HOP'):
            return False
        before = self._motion(self.latest, prior); plan = before['plan']
        if plan['flags'] != 0: return False
        select_current_actor(self.latest, prior); select_current_actor(sample, actor)
        timer = next((t for t in sample['pokemonCombat']['movementTimers'] if t['handle'] == actor['handle']), None)
        require(sample['frame'] == self.latest['frame'] + 1
            and sample['actorFrame'] == self.latest['actorFrame'] + 1
            and sample['nativeCycle'] > self.latest['nativeCycle']
            and prior['sourceIdentity'] == actor['sourceIdentity']
            and engine_binding_identity(prior['engineIdentity']) == engine_binding_identity(actor['engineIdentity'])
            and prior['role'] == actor['role'] == 'WILD' and prior.get('laneId') == actor.get('laneId')
            and motion['plan'] == plan and plan['kind'] in (1, 2)
            and plan['fieldEpoch'] == actor['handle']['fieldEpoch']
            and before['phase'] == motion['phase'] == actor['motionPhase'] == 'MOVING'
            and actor['motionKind'] == prior['motionKind'] == {1:'WALK', 2:'HOP'}[plan['kind']]
            and actor['motionDuration'] == prior['motionDuration'] == plan['duration']
            and prior['reservationId'] == actor['reservationId'] == plan['reservationId'] > 0
            and before['elapsed'] == prior['motionElapsed']
            and motion['elapsed'] == actor['motionElapsed'] == before['elapsed'] + 1 < plan['duration']
            and actor['commitSequence'] == prior['commitSequence']
            and (motion['commitSequence'], motion['commitPublished'], motion['cancelReason'])
                == (before['commitSequence'], before['commitPublished'], before['cancelReason'])
            and before['commitPublished'] == before['cancelReason'] == 0
            and timer is not None and timer['movementActorControlMode'] == 0
            and not any(e.get('event') in ('INTENT_CREATED', 'PLAN_ACCEPTED', 'MOTION_STARTED',
                'MOTION_CANCELED', 'LOGICAL_COMMIT', 'MOTION_FINISHED', 'CONTROL_RETURNED') for e in native),
                'Cargo-hit abort lost its accepted ordinary carrier motion')
        self._pose(prior); self._pose(actor)
        return True

    def _damage_abort(self, sample, events, carrier, target):
        old=self.latest["pokemonCombat"]["interactions"]; state=old["throwState"]
        prior=next((r for r in old["carriers"] if r["handle"]==carrier["handle"]),None)
        held=next((t for t in self.latest["pokemonCombat"]["movementTimers"] if t["handle"]==target["handle"]),None)
        slot=carrier["handle"]["slot"];cargo=target["handle"]["slot"]
        if prior is None or held is None or state["targets"][slot]&128==0 \
                or state["targets"][slot]&63!=cargo+1 or not state["carrierMask"]&(1<<slot) \
                or not state["targetMask"]&(1<<cargo) or held["movementActorControlMode"]!=1 \
                or not prior["bindings"]["cargo"]["bound"] \
                or prior["bindings"]["cargo"]["target"]!=dict(kind="ACTOR",actor=target["handle"]):
            return False
        ordinary_carrier = False
        for actor in (carrier,target):
            before=next((r for r in self.latest["pokemonCombat"]["targets"] if r["handle"]==actor["handle"]),None)
            after=next((r for r in sample["pokemonCombat"]["targets"] if r["handle"]==actor["handle"]),None)
            if before is None or after is None:return False
            native=self._events(sample,events,actor);motion=self._motion(sample,actor)
            unchanged = after.get('currentHp') == before.get('currentHp') and after.get('hitCount') == before.get('hitCount')
            hit = (after.get('hitCount') == before.get('hitCount', -1) + 1
                and after.get('lastDamage', 0) > 0
                and before.get('currentHp', 0) - after.get('currentHp', 0) == after['lastDamage'])
            if actor['handle'] == carrier['handle'] \
                    and before.get('hpMirrorMatches') is True and before.get('currentHp') == before.get('hp') \
                    and after.get('hpMirrorMatches') is True and after.get('currentHp') == after.get('hp') \
                    and (unchanged or (hit and after.get('knockbackPending') == 1)) \
                    and self._ordinary_carrier_continuation(sample, actor, motion, native):
                ordinary_carrier = True
                continue
            if actor["handle"]==carrier["handle"] and after.get("currentHp")==before.get("currentHp") \
                    and after.get("hitCount")==before.get("hitCount"):
                prior_actor=next((a for a in self.latest["actors"] if a["handle"]==actor["handle"]),None)
                timer=next((t for t in sample["pokemonCombat"]["movementTimers"] if t["handle"]==actor["handle"]),None)
                damage=self.cycles.get(slot,{}).get("carrierDamage")
                if damage is not None and motion["plan"]==damage["motion"]["plan"]:
                    require(prior_actor is not None and timer is not None and timer["movementActorControlMode"]==0
                        and after.get("hpMirrorMatches") is True and after.get("currentHp")==after.get("hp")
                        and before["currentHp"]==damage["hit"]["after"]["currentHp"]
                        and before["hitCount"]==damage["hit"]["after"]["hitCount"]
                        and motion["plan"]["kind"]==2 and motion["plan"]["flags"]==1
                        and motion["phase"]==actor["motionPhase"]=="MOVING"
                        and motion["elapsed"]==actor["motionElapsed"]==self._motion(self.latest,prior_actor)["elapsed"]+1
                        and not any(e.get("event") in ("MOTION_STARTED","MOTION_CANCELED") for e in native)
                        and not self._advance(sample,actor,motion,native,damage["motion"]),
                            "Cargo-hit abort lost its accepted carrier damage motion")
                    continue
                if prior_actor is None or timer is None or after.get("hpMirrorMatches") is not True \
                        or after.get("currentHp")!=after.get("hp") or timer["movementActorControlMode"]!=0 \
                        or actor["motionKind"]!="NONE" or not motion["phase"]==actor["motionPhase"]=="IDLE" \
                        or actor["reservationId"]!=0 or motion!=self._motion(self.latest,prior_actor) \
                        or any(e.get("event")=="MOTION_STARTED" for e in native):
                    return False
                continue
            if after.get("hitCount")!=before.get("hitCount",-1)+1 \
                    or after.get("lastDamage",0)<=0 or after.get("hpMirrorMatches") is not True \
                    or after.get("currentHp")!=after.get("hp") \
                    or before.get("currentHp",0)-after.get("currentHp",0)!=after["lastDamage"]:
                return False
            if motion["plan"]["kind"]!=2 or motion["plan"]["flags"]!=1:return False
            if ordinary_carrier:
                accepted = [e for e in native if e.get('event') == 'PLAN_ACCEPTED']
                starts = [e for e in native if e.get('event') == 'MOTION_STARTED']
                plan = motion['plan']
                require(after['lastDamage'] == 20 and len(accepted) == len(starts) == 1
                    and accepted[0].get('reason') == 'OK' and accepted[0]['sequence'] < starts[0]['sequence']
                    and (accepted[0].get('valueA'), accepted[0].get('valueB')) ==
                        (((plan['target'][0] & 65535) << 16) | (plan['target'][1] & 65535), plan['duration']),
                        'Cargo-hit abort lacks its fresh damage and admitted forced plan')
            self._start(sample,actor,motion,native)
        return True

    def _blocked_release(self, sample, events, carrier, target, own):
        """A rejected Throw may drop Cargo before its own same-queue Hop.

        Only the measured native RESERVED rejection path is admitted. The
        released Cargo's ordinary move earns no Throw or landing credit.
        """
        previous = self.latest
        require(previous is not None and sample["frame"] == previous["frame"] + 1
            and sample["actorFrame"] == previous["actorFrame"] + 1
            and sample["nativeCycle"] > previous["nativeCycle"]
            and sample["context"] == previous["context"]
            and sample["fieldControl"]["fieldPointer"] == previous["fieldControl"]["fieldPointer"],
                "blocked Throw release lacks adjacent current boundaries")
        old, old_rows, old_timers, old_actors = ground_state(previous, self.source)
        state, rows, timers, actors = ground_state(sample, self.source)
        slot, cargo = carrier["handle"]["slot"], target["handle"]["slot"]
        require(own["carrier"] == carrier["handle"] and own["cargo"] == target["handle"]
            and own["pickup"] is not None and own["pickup"] < sample["frame"]
            and own["launch"] is None and self.previous_state == old,
                "blocked Throw release lacks its original owned cycle")
        for actor in (carrier, target):
            index = actor["handle"]["slot"]; prior = old_actors.get(index)
            select_current_actor(sample, actor)
            require(prior is not None and actors.get(index) == actor
                and prior["handle"] == actor["handle"]
                and prior["subjectIdentity"] == actor["subjectIdentity"]
                and prior["sourceIdentity"] == actor["sourceIdentity"]
                and engine_binding_identity(prior["engineIdentity"])
                    == engine_binding_identity(actor["engineIdentity"]),
                    "blocked Throw release changed its full current source")
        require(old["targets"][slot] == (192 | (cargo + 1))
            and old["targetMask"] & (1 << cargo) and old["carrierMask"] & (1 << slot)
            and old_timers[cargo]["movementActorControlMode"] == 1
            and old_rows[slot]["bindings"]["cargo"]["target"] == dict(kind="ACTOR", actor=target["handle"])
            and old_rows[slot]["bindings"]["cargo"]["bound"]
            and old_rows[slot]["bindings"]["trigger"]["bound"]
            and state["targets"][slot] == 0 and not state["carrierMask"] & (1 << slot)
            and state["recoveringMask"] & (1 << slot) and not state["targetMask"] & (1 << cargo)
            and not any(n and n & 63 == cargo + 1 for n in state["targets"])
            and not any(rows[slot]["bindings"][key]["bound"] for key in ("trigger", "cargo"))
            and timers[cargo]["movementActorControlMode"] == 0
            and timers[slot]["movementActorControlMode"] == 0,
                "blocked Throw release retained or changed its held pair")
        prior = old_actors[slot]
        release_lane = profile(self.profiles.get(prior["behaviorFingerprint"]), prior, self.source)
        require(prior["matchedLayerMask"] & THROW_RELEASE_BIT and release_lane[0] == 12
            and prior["motionKind"] == "NONE" and prior["motionPhase"] == "IDLE"
            and prior["reservationId"] == 0,
                "blocked Throw release lacks its prior held-release profile")
        require(all(e.get("frame") == sample["frame"] for e in events
            if e.get("kind") == "native" and e.get("data", {}).get("actorHandle") == target["handle"]["value"]),
                "blocked Throw release has a foreign completed-frame record")
        native = self._events(sample, events, target)
        relevant = [e for e in native if e["event"] in ("INTENT_CREATED", "CANDIDATE_REJECTED",
            "CONDITIONAL_RESOLVED", "PLAN_ACCEPTED", "MOTION_STARTED")]
        require([e["event"] for e in relevant] == ["INTENT_CREATED", "CANDIDATE_REJECTED",
            "CONDITIONAL_RESOLVED", "INTENT_CREATED", "PLAN_ACCEPTED", "MOTION_STARTED"]
            and all(type(e.get("sequence")) is int for e in relevant)
            and all(a["sequence"] < b["sequence"] for a, b in zip(relevant, relevant[1:]))
            and all(e.get("reason") == "OK" for e in (relevant[0], relevant[3], relevant[4], relevant[5]))
            and relevant[1].get("reason") == "REJECTED_RESERVED"
            and (relevant[1].get("valueA"), relevant[1].get("valueB")) == (0, 1)
            and all((e.get("valueA"), e.get("valueB")) == (2, 1) for e in (relevant[0], relevant[3]))
            and not any(e["event"] in ("MOTION_CANCELED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED") for e in native),
                "blocked Throw release lacks ordered rejected Throw and ordinary admission")
        motion = self._motion(sample, target); plan = motion["plan"]
        lane = profile(self.profiles.get(target["behaviorFingerprint"]), target, self.source)
        duration = min(65535, lane[36] + (plan["distance"] - 1) * (lane[36] - (lane[36] >> 2))
            + ((abs(plan["targetBaseY"] - plan["startBaseY"]) >> 12) * lane[36] * lane[48]) // 1600)
        require(lane[12] == 2 and lane[36] > 0 and plan["kind"] == 2 and plan["flags"] == 0
            and plan["visibilityPolicy"] == 0 and plan["behaviorFingerprint"] == target["behaviorFingerprint"] & 65535
            and lane[20] <= plan["distance"] <= lane[21]
            and plan["distance"] == max(abs(a - b) for a, b in zip(plan["origin"], plan["target"]))
            and plan["duration"] == duration
            and (relevant[4]["valueA"], relevant[4]["valueB"]) ==
                (((plan["target"][0] & 65535) << 16) | (plan["target"][1] & 65535), duration)
            and self._pose(target) == tuple((v << 16) + 32768 for v in plan["origin"]) + (plan["startBaseY"], 0),
                "blocked Throw release lacks its authentic ordinary Hop plan")
        self._start(sample, target, motion, native)
        return dict(frame=sample["frame"], actorFrame=sample["actorFrame"],
            carrier=deepcopy(carrier["handle"]), cargo=deepcopy(target["handle"]),
            native=deepcopy(relevant), plan=deepcopy(plan))

    def _queued_carrier_pair(self, sample, carrier, own, queue=None, forced=False):
        cargo=next((a for a in sample["actors"] if a["handle"]==own["cargo"]),None)
        require(cargo is not None and carrier["handle"]==own["carrier"], "queued carrier hit lost its full held pair")
        selected=[select_current_actor(sample,a) for a in (carrier,cargo)]
        combat=sample["pokemonCombat"]; value=combat["interactions"]; state=value["throwState"]
        self._boundary(sample)
        require(combat.get("available") is True and combat["frame"]==sample["frame"]
            and combat["nativeCycle"]==sample["nativeCycle"] and combat["observationBoundary"]==BOUNDARY
            and combat["identity"]["romSha256"]==self.source["romSha256"]
            and combat["identity"]["overlaySha256"]==self.source["overlaySha256"],
                "queued carrier hit lacks current native HP boundary")
        slot=carrier["handle"]["slot"]; target=cargo["handle"]["slot"]
        row=next((r for r in value["carriers"] if r["handle"]==carrier["handle"]),None)
        timers=[next((r for r in combat["movementTimers"] if r["handle"]==a["handle"]),None) for a in (carrier,cargo)]
        encoded=state["targets"][slot]
        require(row is not None and row["bindings"]["cargo"]["bound"] and row["bindings"]["cargo"]["targetCurrent"]
            and row["bindings"]["cargo"]["target"]==dict(kind="ACTOR",actor=cargo["handle"])
            and encoded&128 and encoded&63==target+1 and state["carrierMask"]&(1<<slot)
            and state["targetMask"]&(1<<target) and not state["recoveringMask"]&(1<<slot)
            and all(t is not None and t["sourceIdentity"]==a["sourceIdentity"] for t,a in zip(timers,(carrier,cargo)))
            and timers[0]["movementActorControlMode"]==0 and timers[1]["movementActorControlMode"]==1,
                "queued carrier hit lost its authentic CARRIED claim or HELD control")
        if queue is not None:
            require(sample["frame"]==self.latest["frame"]+1 and sample["actorFrame"]==self.latest["actorFrame"]+1
                and sample["nativeCycle"]>self.latest["nativeCycle"] and sample["context"]==self.latest["context"]
                and sample["fieldControl"]["fieldPointer"]==self.latest["fieldControl"]["fieldPointer"]
                and encoded==(queue["encoded"]&~64 if forced else queue["encoded"])
                and carrier.get("laneId")==queue["laneId"]
                and all(a["sourceIdentity"]==source and engine_binding_identity(a["engineIdentity"])==engine
                    and all(selection[k]==identity[k] for k in ("handle","subjectIdentity","species","role",
                        "authorityGeneration","engineAnchorGeneration","presentationGeneration"))
                    for a,selection,source,engine,identity in zip((carrier,cargo),selected,queue["sources"],queue["engines"],queue["owners"])),
                    "queued carrier hit changed full owner, source, claim or boundary")
        return dict(owners=selected,sources=[deepcopy(a["sourceIdentity"]) for a in (carrier,cargo)],
            engines=[engine_binding_identity(a["engineIdentity"]) for a in (carrier,cargo)],encoded=encoded,laneId=carrier.get("laneId"))

    def _queued_carrier_hit(self, sample, events, carrier, own, hit, motion, native):
        queue=hit["queue"]; p=motion["plan"]; forced=p["kind"]==2 and p["flags"]==1
        self._queued_carrier_pair(sample,carrier,own,queue,forced)
        current=next(r for r in sample["pokemonCombat"]["targets"] if r["handle"]==carrier["handle"])
        require(current.get("hpMirrorMatches") is True and current.get("hp")==current.get("currentHp")==hit["after"]["currentHp"]
            and current.get("hitCount")==hit["after"]["hitCount"]
            and current.get("lastDamage")==hit["after"]["lastDamage"]
            and current.get("knockbackDirection")==hit["after"].get("knockbackDirection")
            and current.get("knockbackOptions")==hit["after"].get("knockbackOptions")
            and sample["frame"]<=queue["deadline"], "queued carrier hit changed its HP receipt or exceeded the accepted primitive")
        if forced:
            require(sample["frame"]==queue["deadline"] and current.get("knockbackPending")==0
                and p["direction"]==hit["after"].get("knockbackDirection")
                and self._advance(sample,carrier,motion,native,queue["motion"]),
                    "queued carrier hit forced START preceded exact ordinary control return")
            queue["completed"]=sample["frame"]
            return True
        require(current.get("knockbackPending")==1 and p==queue["motion"]["plan"]
            and not any(e.get("event") in ("INTENT_CREATED","PLAN_ACCEPTED","MOTION_STARTED","MOTION_CANCELED") for e in native),
                "queued carrier hit replaced its accepted ordinary motion or pending queue")
        before_actor=next(a for a in self.latest["actors"] if a["handle"]==carrier["handle"])
        before=self._motion(self.latest,before_actor)
        if motion["phase"]=="MOVING":
            require(self._ordinary_carrier_continuation(sample,carrier,motion,native),
                    "queued carrier hit lost ordinary elapsed progress")
        else:
            require(motion["phase"]==carrier["motionPhase"]=="SETTLING" and motion["elapsed"]==p["duration"]
                and ((before["phase"]=="MOVING" and before["elapsed"]==p["duration"]-1
                    and motion["settleRemaining"]==p["pauseFrames"])
                    or (before["phase"]=="SETTLING" and motion["settleRemaining"]==before["settleRemaining"]-1)),
                    "queued carrier hit lost exact ordinary settle progress")
        require(not self._advance(sample,carrier,motion,native,queue["motion"]),
                "queued carrier hit missed its first legal forced START")
        return False

    def _carried_damage(self, sample, events, carrier, own):
        # PrepareCarrierHit keeps CARRIED while its admitted knockback runs.
        # Keep that hit/START in this same cycle for a later Cargo-hit abort.
        prior=next((r for r in self.latest["pokemonCombat"]["targets"] if r["handle"]==carrier["handle"]),None)
        current=next((r for r in sample["pokemonCombat"]["targets"] if r["handle"]==carrier["handle"]),None)
        queued=(own.get("carrierHit") or {}).get("queue")
        if queued is not None and queued.get("completed") is None:
            require(prior is not None and current is not None, "queued carrier hit lost its exact native HP rows")
        if prior is None or current is None:return
        native=self._events(sample,events,carrier);motion=self._motion(sample,carrier)
        hit=own.get("carrierHit"); queue=(hit or {}).get("queue")
        if queue is not None and queue.get("completed") is None:
            if not self._queued_carrier_hit(sample,events,carrier,own,hit,motion,native): return
        if current.get("hitCount")==prior.get("hitCount",-1)+1 and current.get("lastDamage",0)>0 \
                and current.get("hpMirrorMatches") is True and current.get("hp")==current.get("currentHp") \
                and prior.get("currentHp",0)-current["currentHp"]==current["lastDamage"]:
            own["carrierHit"]=dict(frame=sample["frame"],before=deepcopy(prior),after=deepcopy(current))
            p=motion["plan"]
            if current.get("knockbackPending")==1 and p["kind"] in (1,2) and p["flags"]==0 and motion["phase"]=="MOVING":
                require(prior.get("hpMirrorMatches") is True and prior.get("hp")==prior.get("currentHp"),
                        "queued carrier hit lacks its mirrored prior HP")
                captured=self._queued_carrier_pair(sample,carrier,own)
                starts=[e for e in native if e.get("event")=="MOTION_STARTED"]
                accepted=[e for e in native if e.get("event")=="PLAN_ACCEPTED"]
                if starts:
                    require(len(accepted)==len(starts)==1 and accepted[0].get("reason")=="OK"
                        and accepted[0]["sequence"]<starts[0]["sequence"]
                        and (accepted[0].get("valueA"),accepted[0].get("valueB"))==
                            (((p["target"][0]&65535)<<16)|(p["target"][1]&65535),p["duration"]),
                            "queued carrier hit lacks its admitted ordinary plan")
                    move=self._start(sample,carrier,motion,native)
                else:
                    require(self._ordinary_carrier_continuation(sample,carrier,motion,native),
                            "queued carrier hit lacks current accepted ordinary motion")
                    move=dict(frame=sample["frame"],nativeCycle=sample["nativeCycle"],handle=deepcopy(carrier["handle"]),
                        plan=deepcopy(p),commitBefore=carrier["commitSequence"],startSequence=None,
                        commit=None,returnFrame=None,pose=self._pose(carrier),moved=False)
                captured.update(motion=move,deadline=sample["frame"]+p["duration"]-motion["elapsed"]+p["pauseFrames"],completed=None)
                own["carrierHit"]["queue"]=captured
                return
        hit=own.get("carrierHit")
        starts=[e for e in native if e.get("event")=="MOTION_STARTED"]
        if hit is not None and starts and motion["plan"]["kind"]==2 and motion["plan"]["flags"]==1:
            accepted=[e for e in native if e.get("event")=="PLAN_ACCEPTED"]
            p=motion["plan"]
            require(((hit.get("queue") or {}).get("completed")==sample["frame"]
                    or (hit.get("queue") is None and 0<=sample["frame"]-hit["frame"]<=1))
                and current["currentHp"]==hit["after"]["currentHp"]
                and current["hitCount"]==hit["after"]["hitCount"] and len(accepted)==len(starts)==1
                and accepted[0].get("reason")=="OK" and accepted[0]["sequence"]<starts[0]["sequence"]
                and (accepted[0].get("valueA"),accepted[0].get("valueB"))==
                    (((p["target"][0]&65535)<<16)|(p["target"][1]&65535),p["duration"]),
                        "carried carrier damage lacks its fresh hit and admitted forced plan")
            own["carrierDamage"]=dict(hit=deepcopy(hit),motion=self._start(sample,carrier,motion,native))
        elif own.get("carrierDamage") is not None and own["carrierDamage"]["motion"]["returnFrame"] is None:
            require(not any(e.get("event")=="MOTION_CANCELED" for e in native),"carried carrier damage canceled")
            self._advance(sample,carrier,motion,native,own["carrierDamage"]["motion"])

    def _landing_engine(self, sample, actor, native, own):
        """Use an observed Crash base only after this flight returned control."""
        engine=actor["engineObject"]; plan=own["motion"]["plan"]
        endpoint=[(coordinate<<16)+32768 for coordinate in plan["target"]]
        if [engine["pos_x"],engine["pos_z"]]==endpoint:
            return engine,False
        combat=sample["pokemonCombat"]
        timers=[t for t in combat["movementTimers"] if t["handle"]==actor["handle"]]
        require(len(timers)==1 and timers[0]["slot"]==actor["handle"]["slot"]
            and timers[0]["sourceIdentity"]==actor["sourceIdentity"]
            and combat["available"] is True and combat["frame"]==sample["frame"]
            and combat["nativeCycle"]==sample["nativeCycle"] and combat["observationBoundary"]==BOUNDARY
            and combat["identity"]["romSha256"]==self.source["romSha256"]
            and combat["identity"]["overlaySha256"]==self.source["overlaySha256"],
                "landing Crash base has no current native owner or boundary")
        select_current_actor(sample,actor)
        timer=timers[0]; raw=bytes.fromhex(timer.get("rawCrashShakeHex",""))
        values=tuple(timer.get(k) for k in ("movementCrashShakeTimer","movementCrashShakeBaseX","movementCrashShakeBaseZ"))
        require(len(raw)==9 and all(type(v) is int for v in values)
            and struct.unpack("<Bii",raw)==values and 0<values[0]<=32,
                "landing Crash base lacks exact native timer bytes")
        amplitude=512>>((values[0]&2)>>1); offset=-amplitude if values[0]&1 else amplitude
        motion=self._motion(sample,actor)
        require(list(values[1:])==endpoint and [engine["pos_x"],engine["pos_z"]]==[values[1]+offset,values[2]-offset]
            and engine["pos_y"]==plan["targetBaseY"] and engine["unk88_y"]==0
            and actor["handle"]==own["motion"]["handle"] and motion["plan"]==plan
            and motion["phase"]==actor["motionPhase"]=="IDLE" and actor["motionKind"]=="NONE"
            and motion["elapsed"]==actor["motionElapsed"]==plan["duration"],
                "landing Crash stored endpoint or exact render law differs")
        require(self._advance(sample,actor,motion,native,own["motion"]),
                "landing Crash preceded full flight control return")
        effects=[e for e in native if e.get("event")=="WORLD_EFFECT" and e.get("valueA")==3]
        require(len(effects)==1 and effects[0].get("reason")=="OK" and effects[0].get("valueB")==1
            and effects[0]["sequence"]>own["motion"]["returnSequence"]
            and own["motion"]["commit"]["frame"]==sample["frame"],
                "landing Crash effect did not follow this COMMIT FINISH CONTROL")
        own["motion"]["landingPresentation"]=dict(frame=sample["frame"],nativeCycle=sample["nativeCycle"],
            observationBoundary=BOUNDARY,timer=deepcopy(timer),effect=deepcopy(effects[0]),
            rawRender=[engine[k] for k in ("pos_x","pos_y","pos_z")],storedEndpoint=endpoint)
        return dict(engine,pos_x=values[1],pos_z=values[2]),True

    @staticmethod
    def _faint_released(sample, handle):
        combat=sample["pokemonCombat"]; value=combat["interactions"]; state=value["throwState"]
        slot=handle["slot"]; bit=1<<slot
        require(not any(r.get("handle")==handle for r in combat["targets"]+combat["movementTimers"]+value["carriers"])
            and state["targets"][slot]==0 and not any(n and n&63==slot+1 for n in state["targets"])
            and not (state["targetMask"]|state["carrierMask"]|state["recoveringMask"])&bit
            and not any(b.get("bound") and b.get("target")==dict(kind="ACTOR",actor=handle)
                for r in value["carriers"] for b in r["bindings"].values()),
                "fainted flight retained native HP, HELD control, binding or claim")

    def _faint_retirement(self, sample, events, target, own):
        prior_sample=self.latest; handle=own["cargo"]; plan=own["motion"]["plan"]
        require(not own.get("faintPending") and own["carrier"]["slot"] not in self.pending_faint_retirements
            and len(self.pending_faint_retirements)<10, "fainted flight retirement is duplicate or unbounded")
        self._boundary(prior_sample); self._boundary(sample)
        require(sample["frame"]==prior_sample["frame"]+1 and sample["actorFrame"]==prior_sample["actorFrame"]+1
            and sample["nativeCycle"]>prior_sample["nativeCycle"] and sample["context"]==prior_sample["context"]
            and sample["fieldControl"]["fieldPointer"]==prior_sample["fieldControl"]["fieldPointer"],
                "fainted flight changed completed boundary or Field context")
        selected=select_current_actor(prior_sample, dict(handle=handle,
            subjectIdentity=target["subjectIdentity"],species=target["species"],role=target["role"]))
        prior=next(a for a in prior_sample["actors"] if a["handle"]==selected["handle"])
        motion=self._motion(prior_sample,prior); combat=prior_sample["pokemonCombat"]
        hp=next(r for r in combat["targets"] if r["handle"]==handle)
        require(combat.get("available") is True and combat["frame"]==prior_sample["frame"]
            and combat["nativeCycle"]==prior_sample["nativeCycle"] and combat["observationBoundary"]==BOUNDARY
            and combat["identity"]["romSha256"]==self.source["romSha256"]
            and combat["identity"]["overlaySha256"]==self.source["overlaySha256"]
            and hp.get("currentHp")==hp.get("hp")==0 and hp.get("hpMirrorMatches") is True
            and hp.get("initialized")==1 and hp.get("hpSource")=="wild-resident"
            and hp.get("personality")==prior["subjectIdentity"] and hp.get("species")==prior["species"]
            and hp.get("form")==prior["form"] and hp.get("level")==prior["level"]
            and hp.get("mapId")==prior_sample["context"]["mapId"]
            and hp.get("mapGeneration")==handle["mapGeneration"]
            and hp.get("encounterGeneration")==handle["encounterGeneration"]
            and prior["sourceIdentity"]["object"]==prior["engineIdentity"]["pointer"]>0
            and prior["sourceIdentity"]["active"]==1 and prior["sourceIdentity"]["personality"]==prior["subjectIdentity"]
            and all(prior["sourceIdentity"][k]==prior[k] for k in ("species","form","level"))
            and prior["sourceIdentity"]["map_id"]==prior_sample["context"]["mapId"]
            and prior["sourceIdentity"]["encounter_generation"]==handle["encounterGeneration"],
                "fainted flight lacks fresh mirrored native HP0")
        timer=[r for r in combat["movementTimers"] if r["handle"]==handle]
        require(own["launch"]<sample["frame"] and own["motion"]["handle"]==handle
            and own["motion"]["commit"] is None and own["motion"]["returnFrame"] is None
            and plan["kind"]==2 and plan["flags"]==0 and plan["fieldEpoch"]==handle["fieldEpoch"]
            and plan["reservationId"]==prior["reservationId"]>0 and motion["plan"]==plan
            and motion["phase"]==prior["motionPhase"]=="MOVING" and prior["motionKind"]=="HOP"
            and motion["elapsed"]==prior["motionElapsed"]==plan["duration"]-1
            and prior["motionDuration"]==plan["duration"] and motion["commitPublished"]==0
            and prior["commitSequence"]==own["motion"]["commitBefore"]
            and len(timer)==1 and timer[0]["sourceIdentity"]==prior["sourceIdentity"]
            and timer[0]["movementActorControlMode"]==1
            and self.previous_state["targetMask"]&(1<<handle["slot"]),
                "fainted flight lost its admitted final moving plan or HELD owner")
        native=self._events(sample,events,target); n=own["motion"]["commitBefore"]+1
        require(len(native)==3 and [e.get("event") for e in native]==[
                "LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED"]
            and all(e.get("reason")=="OK" and e.get("traceFieldEpoch")==handle["fieldEpoch"] for e in native)
            and [(e.get("valueA"),e.get("valueB")) for e in native]==[(n,2),(n,2),(0,n)]
            and own["motion"]["startSequence"]<native[0]["sequence"]<native[1]["sequence"]<native[2]["sequence"]
            and all(e["frame"]==sample["frame"] for e in events if e.get("kind")=="native"
                and e.get("data",{}).get("actorHandle")==handle["value"]),
                "fainted flight lacks exact ordered COMMIT FINISH CONTROL")
        engine=target["engineIdentity"]; source=target["sourceIdentity"]; lookup=engine.get("id_lookup",{})
        require(target["handle"]==handle and target.get("identityVerified") is False and "engineObject" not in target
            and target.get("active") is True and target.get("presentationAttached") is True
            and target["role"]==prior["role"]=="WILD"
            and all(target[k]==prior[k] for k in ("subjectIdentity","species","form","level","authorityGeneration",
                "engineAnchorGeneration","presentationGeneration","laneId","origin","target"))
            and [target["origin"][k] for k in ("x","y")]==plan["origin"]
            and [target["target"][k] for k in ("x","y")]==plan["target"]
            and [target["logical"][k] for k in ("x","y")]==plan["target"]
            and target["motionKind"]=="NONE" and target["motionPhase"]=="IDLE"
            and target["motionElapsed"]==target["motionDuration"]==plan["duration"]
            and target["reservationId"]==0 and target["commitSequence"]==n
            and engine.get("pointer")==0 and engine.get("in_manager") is False and engine.get("active") is False
            and lookup.get("status")=="complete" and lookup.get("eligible_count")==0
            and lookup.get("first_active_pointer")==0 and lookup.get("matching_objects")==[]
            and all(source.get(k)==0 for k in ("object","active","personality","species","form","level"))
            and source.get("map_id")==1 and source.get("object_id")==prior["sourceIdentity"]["object_id"]
            and source.get("encounter_generation")==handle["encounterGeneration"],
                "fainted flight lacks exact terminal shell and cleared native source")
        self._faint_released(sample,handle)
        record=dict(frame=sample["frame"],actorFrame=sample["actorFrame"],handle=deepcopy(handle),
            personality=prior["subjectIdentity"],carrier=deepcopy(own["carrier"]),plan=deepcopy(plan),
            priorHp=deepcopy(hp),terminal=deepcopy(native),detach=None)
        self.pending_faint_retirements[own["carrier"]["slot"]]=record
        self.fainted_flight_retirements.append(record)
        own["aborted"]=True; own["faintPending"]=True

    def _finish_faint_retirements(self, sample, events, state):
        if self.pending_faint_retirements:
            self._boundary(sample)
            require(sample["context"]==self.latest["context"]
                and sample["fieldControl"]["fieldPointer"]==self.latest["fieldControl"]["fieldPointer"]
                and sample["nativeCycle"]>self.latest["nativeCycle"], "fainted flight DETACH changed native Field owner")
        for slot,record in list(self.pending_faint_retirements.items()):
            handle=record["handle"]; own=self.cycles.get(slot)
            native=[e for e in events if e.get("kind")=="native" and e.get("data",{}).get("actorHandle")==handle["value"]]
            require(sample["frame"]==record["frame"]+1 and sample["actorFrame"]==record["actorFrame"]+1
                and not any(a["handle"]==handle for a in sample["actors"])
                and own is not None and own["cargo"]==handle and own["carrier"]==record["carrier"]
                and own.get("faintPending") is True and own["landed"] is None and len(native)==1,
                    "fainted flight lacks next completed-frame public absence and DETACH")
            e=native[0]; d=e["data"]
            require(e["frame"]==sample["frame"] and d.get("event")=="ACTOR_DETACHED" and d.get("reason")=="OK"
                and d.get("actor")=={k:v for k,v in handle.items() if k!="value"}
                and d.get("frame")==d.get("actorFrame")==record["actorFrame"]
                and d.get("traceFieldEpoch")==handle["fieldEpoch"] and type(d.get("sequence")) is int
                and d["sequence"]>record["terminal"][-1]["sequence"]
                and d.get("valueA")==1 and d.get("valueB")==record["personality"],
                    "fainted flight DETACH owner, clock, order or personality differs")
            self._faint_released(sample,handle)
            record["detach"]=deepcopy(e)
            del self.cycles[slot]; del self.pending_faint_retirements[slot]

    def _cycles(self, sample, events, named, state, rows, timers, actors):
        primary=[named[name]["handle"] for name in GEODUDES if name in named and name not in self.primary_zeroes]
        require(len(self.cycles)<=10 and all(slot in actors and slot in rows
            and actors[slot]["handle"]==own["carrier"] and actors[slot]["role"]=="WILD"
            for slot,own in self.cycles.items()), "owned cycle lost its full current Wild carrier")
        # Ambient Wild carriers can throw a selected subject too. Their cycles
        # use these same owner/flight/landing checks and earn no positive credit.
        for slot,carrier in actors.items():
            if carrier["role"]!="WILD" or slot not in rows:continue
            row = rows[slot]; flags = row["throw"]
            own = self.cycles.get(slot)
            if flags["targetRaw"]:
                target = actors.get(flags["targetSlot"])
                require(target is not None and flags["carrier"] and state["targetMask"] & (1 << flags["targetSlot"])
                    and row["bindings"]["cargo"]["bound"]
                    and row["bindings"]["cargo"]["target"] == dict(kind="ACTOR", actor=target["handle"]),
                    "current claim lost its exact Cargo")
                if own is None:
                    own = dict(carrier=deepcopy(carrier["handle"]), cargo=deepcopy(target["handle"]),
                        claim=sample["frame"], pickup=None, launch=None, landed=None, cleanup=None,
                        motion=None, recorder=None, credited=self.window_start is not None and carrier["handle"] in primary)
                    self.cycles[slot] = own
                require(own["cargo"] == target["handle"], "owned Cargo changed before cleanup")
                if flags["carried"] and own["pickup"] is None:
                    own["pickup"] = sample["frame"]
                    require(timers[target["handle"]["slot"]]["movementActorControlMode"] == 1,
                            "pickup has no native HELD control")
                    prior = self.previous_state
                    if own["credited"] and target["handle"] in primary and prior and prior["recoveringMask"] & (1 << target["handle"]["slot"]):
                        self.recovery_pickups.append(dict(frame=sample["frame"], actor=deepcopy(target["handle"])))
            if own is None: continue
            target = actors.get(own["cargo"]["slot"])
            require(target is not None and target["handle"] == own["cargo"], "owned Cargo disappeared before cleanup")
            native = self._events(sample, events, target)
            queue=(own.get("carrierHit") or {}).get("queue")
            if queue is not None and queue.get("completed") is None and not flags["carried"]:
                require(own["pickup"] is not None and own["launch"] is None and not flags["targetRaw"]
                    and not flags["carrier"] and not flags["recovering"]
                    and not any(row["bindings"][k]["bound"] for k in ("trigger","cargo"))
                    and not state["targetMask"]&(1<<target["handle"]["slot"])
                    and timers[target["handle"]["slot"]]["movementActorControlMode"]==0
                    and self._damage_abort(sample,events,carrier,target),
                        "queued carrier hit lost CARRIED without authenticated Cargo-hit release")
                own["aborted"]=True;queue["releasedByCargoHit"]=sample["frame"]
                del self.cycles[slot]
                continue
            if flags["carried"] and own["pickup"] is not None and own["launch"] is None:
                self._carried_damage(sample,events,carrier,own)
            if own["pickup"] is not None and own["launch"] is None and not flags["targetRaw"]:
                starts = [e for e in native if e.get("event") == "MOTION_STARTED"]
                require(not flags["carrier"]
                    and not any(row["bindings"][k]["bound"] for k in ("trigger", "cargo")),
                    "picked Cargo lacks native launch and cleared bindings")
                damage_abort=bool(starts) and not flags["recovering"] and self._damage_abort(sample,events,carrier,target)
                blocked_release = bool(starts) and flags["recovering"] and (
                    any(e.get("event") == "CANDIDATE_REJECTED" for e in native)
                    or (not state["targetMask"] & (1 << target["handle"]["slot"])
                        and timers[target["handle"]["slot"]]["movementActorControlMode"] == 0))
                if blocked_release:
                    self.blocked_releases.append(self._blocked_release(sample, events, carrier, target, own))
                if not starts or damage_abort or blocked_release:
                    require(not state["targetMask"] & (1 << target["handle"]["slot"])
                        and timers[target["handle"]["slot"]]["movementActorControlMode"] == 0,
                        "unlaunched release retained held Cargo")
                    own["aborted"] = True
                    # Released Cargo is no longer owned by this cycle. Native
                    # carrier recovery remains checked by ground_state.
                    del self.cycles[slot]
                    continue
                require(flags["recovering"], "native launch lost carrier recovery")
                motion = self._motion(sample, target)
                own["motion"] = self._start(sample, target, motion, native)
                require(self._owned_flight(sample,events,target,motion),
                        "launch is not an admitted owned Cargo Hop")
                own["launch"] = sample["frame"]; own["recorder"] = MotionRecorder()
                own["recorder"].expected_pause_by_kind["HOP"] = motion["plan"]["pauseFrames"]
            if own["launch"] is not None and own["landed"] is None:
                require(not any(e.get("event") == "MOTION_CANCELED" for e in native), "owned flight canceled")
                if "engineObject" not in target:
                    self._faint_retirement(sample,events,target,own)
                    continue
                engine=target["engineObject"]; returned=False
                if target["motionElapsed"]==own["motion"]["plan"]["duration"]:
                    engine,returned=self._landing_engine(sample,target,native,own)
                recorder = own["recorder"]; recorder.observe(sample["frame"], target, engine)
                require(not recorder.failures, "owned flight presentation differs")
                if sample["frame"] != own["launch"] and (returned or self._advance(sample, target, self._motion(sample, target), native, own["motion"])):
                    require(recorder.completed and complete_travel(recorder.completed[-1]), "flight lacks continuous travel and landing control")
                    require(not state["targetMask"] & (1 << target["handle"]["slot"])
                        and timers[target["handle"]["slot"]]["movementActorControlMode"] == 0,
                        "landing retained held control or target claim")
                    own["landed"] = sample["frame"]
            if own["landed"] is not None and not flags["recovering"] and not flags["targetRaw"] and not flags["carrier"]:
                own["cleanup"] = sample["frame"]
                if own["credited"]:
                    self.completed.append({k:deepcopy(v) for k,v in own.items() if k != "recorder"})
                del self.cycles[slot]
            elif own["pickup"] is None and not flags["targetRaw"]:
                require(not row["bindings"]["cargo"]["bound"], "aborted claim retained Cargo binding")
                del self.cycles[slot]

    def _sample(self, sample, events, action):
        self._boundary(sample)
        require(sample["frame"] == self.latest["frame"] + 1 and sample["nativeCycle"] > self.latest["nativeCycle"],
                "continuous completed-frame window has a gap")
        if self.window_start is None: self.window_start = sample["frame"]
        for event in events:
            d = event.get("data", {})
            if event.get("kind") == "native-observation" and d.get("observation") == "behavior-resolved" and d.get("resolved"):
                self.profiles[d["fingerprint"]] = deepcopy(d)
        self._optional_cargo_exit(sample,events)
        self._primary_lifetimes(sample,events)
        named = self._actors(sample); state, rows, timers, actors = ground_state(sample, self.source,
            lambda actor,motion:self._owned_flight(sample,events,actor,motion))
        self._finish_faint_retirements(sample,events,state)
        expected = HELD_KEYS[(int(action.rsplit("-", 1)[1])-1) % 4]
        selector = sample["selector"]
        held = selector.get("rawHeld")
        edge = self.action_frames[self.action_index] == 1 and held == self.latest.get("selector", {}).get("rawHeld") \
            and selector.get("physicalPressed") == expected
        require(held == expected or edge, "normal B+Left/Down/Right/Up input differs")
        for name in GEODUDES:
            if name not in named or name in self.primary_zeroes: continue
            actor = named[name]; slot = actor["handle"]["slot"]
            require(slot in rows and slot in timers, "Geodude lacks native bindings or timers")
            if rows[slot]["bindings"]["trigger"]["bound"]:
                profile(self.profiles.get(actor["behaviorFingerprint"]), actor, self.source)
                self.interests[name] += 1
            native = self._events(sample, events, actor)
            move = self.ground_motions.get(name)
            if move is not None:
                if any(d.get("event") == "MOTION_CANCELED" for d in native):
                    del self.ground_motions[name]
                elif self._advance(sample, actor, self._motion(sample, actor), native, move):
                    self.motion_returns[name] += 1; del self.ground_motions[name]
            if not self.motion_returns[name] and name not in self.ground_motions \
                    and actor["motionKind"] == "WALK" and any(d.get("event") == "MOTION_STARTED" for d in native):
                self.ground_motions[name] = self._start(sample, actor, self._motion(sample, actor), native)
        for event in events:
            if event.get("kind") == "native-observation" and event.get("data", {}).get("observation") == "throw-cargo-query":
                self._query(sample, event, rows, timers, actors)
        self._cycles(sample, events, named, state, rows, timers, actors)
        self.previous_state = deepcopy(state); self.latest = deepcopy(sample)
        self.observed_frames += 1; self.soak_frames += 1
        self.window_end = sample["frame"]

    def stage(self, name):
        return name == "window-complete" and not self.failures and self.soak_frames == SOAK_FRAMES \
            and self.previous_state is not None and not self.pending_faint_retirements \
            and all(n in self.primary_retirements and self.primary_retirements[n]["detach"] is not None for n in self.primary_zeroes) \
            and not any((own.get("carrierHit") or {}).get("queue") is not None
                and own["carrierHit"]["queue"].get("completed") is None for own in self.cycles.values())             and (self.cargo_exit is None or self.cargo_exit["detach"] is not None)

    def _profiles(self, events):
        for event in events:
            d = event.get("data", {})
            if event.get("kind") == "native-observation" and d.get("observation") == "behavior-resolved" and d.get("resolved"):
                self.profiles[d["fingerprint"]] = deepcopy(d)

    def _health(self, row):
        sample = row["snapshot"]; self._boundary(sample)
        value = row["receipt"]["playerHealth"]
        require(all(sample[k] == self.latest[k] for k in ("frame", "nativeCycle", "actors", "player", "pokemonCombat"))
            and value["frame"] == sample["frame"] and value["nativeCycle"] == sample["nativeCycle"]
            and value["identity"]["romSha256"] == self.source["romSha256"]
            and value["identity"]["overlaySha256"] == self.source["overlaySha256"]
            and value["hp"] == value["savedHp"] and 0 < value["hp"] <= value["maxHp"] == 100
            and value["recoveryPending"] is False, "Player is not alive in the same saved native HP record")
        return deepcopy(value)

    def observe_record(self, row, on_sample=None):
        if self.failures: return self.result()
        try:
            if "initialSnapshot" in row:
                require(self.latest is None and row["phase"] == "setup", "initial boundary is misplaced")
                self._boundary(row["initialSnapshot"], False); self.latest = deepcopy(row["initialSnapshot"])
                self._profiles(row.get("initialEvents", []))
                return self.result()
            phase = row["phase"]; sequence = SETUP if phase == "setup" else ACTIONS
            index = self.setup_index if phase == "setup" else self.action_index
            require(phase in ("setup", "observe") and index < len(sequence)
                and (phase == "setup" or self.setup_index == len(SETUP)), "observation order differs")
            name, op, args = sequence[index]; require(row["action"] == name, "action order differs")
            if op == "step":
                counts = self.setup_frames if phase == "setup" else self.action_frames
                for sample, events, _ in validate_raw_chunk(row, self.latest):
                    counts[index] += 1; require(counts[index] <= args["frames"], "action exceeded its frame bound")
                    if phase == "observe": self._sample(sample, events, name)
                    else:
                        self._boundary(sample); self._profiles(events); self.latest = deepcopy(sample)
                    if on_sample is not None: on_sample(sample, self.observed_frames)
                if "until" in args:
                    if not self.stage(args["until"]["stage"]): return self.result()
                elif counts[index] != args["frames"]: return self.result()
            else:
                require(row["command"] == op, "setup or HP command differs")
                sample = row["snapshot"]; self._boundary(sample)
                if op == "bind":
                    selected = select_current_actor(sample, row["receipt"])
                    spec = next(s for s in SUBJECTS if s[0] == args["subject"])
                    require(selected["species"] == spec[1] and selected["role"] == spec[2], "bound a different subject")
                    self.subjects[args["subject"]] = selected
                if op == "player-health.observe":
                    if name == "before-soak": self.health_before = self._health(row)
                    elif name == "after-soak": self.health_after = self._health(row)
                    else:
                        leg = int(name.rsplit("-", 1)[1])
                        require(len(self.health_checkpoints) < len(CHECKPOINT_LEGS)
                            and leg == CHECKPOINT_LEGS[len(self.health_checkpoints)]
                            and self.soak_frames == self.observed_frames == leg * LEG_FRAMES,
                            "Player HP checkpoint is not at its exact continuous frame")
                        self.health_checkpoints.append(dict(leg=leg, soakFrames=self.soak_frames,
                            playerHealth=self._health(row)))
                for event in row.get("events", []) + row.get("receipt", {}).get("events", []):
                    d = event.get("data", {})
                    if d.get("observation") == "behavior-resolved" and d.get("resolved"):
                        self.profiles[d["fingerprint"]] = deepcopy(d)
                self.latest = deepcopy(sample)
            if phase == "setup":
                self.setup_index += 1
                if self.setup_index == len(SETUP): self.context = deepcopy(self.latest["context"])
            else: self.action_index += 1
        except (KeyError, TypeError, ValueError, StopIteration, IndexError) as error:
            self.failures.append(str(error) or type(error).__name__)
        return self.result()

    def result(self):
        survivors=[n for n in GEODUDES if n not in self.primary_zeroes and n not in self.primary_retirements
            and self.primary_current_frames[n]==self.primary_healthy_frames[n]==self.soak_frames]
        ready = not self.failures and self.action_index == len(ACTIONS) and self.soak_frames == SOAK_FRAMES \
            and self.observed_frames >= MIN_FRAMES and self.stage("window-complete") \
            and len(survivors)>=2 \
            and all(self.interests.values()) and all(self.queries.values()) and all(self.motion_returns.values()) \
            and len(self.completed) >= 2 and bool(self.recovery_pickups) and self.health_after is not None \
            and [r["leg"] for r in self.health_checkpoints] == list(CHECKPOINT_LEGS)
        return dict(kind=KIND, requirements=[REQUIREMENT], ready=bool(ready), passed=bool(ready), acceptedProof=False,
            observedFrames=self.observed_frames, observedFrameUnit="completed-game-frame", failures=list(self.failures),
            subjects=deepcopy(self.subjects), windowStart=self.window_start, windowEnd=self.window_end,
            soakFrames=self.soak_frames, interests=dict(self.interests), queries=dict(self.queries),
            motionReturns=dict(self.motion_returns), completedThrows=deepcopy(self.completed),
            recoveryPickups=deepcopy(self.recovery_pickups), queryCount=self.query_count, limitCount=self.limit_count,
            playerBefore=deepcopy(self.health_before), playerAfter=deepcopy(self.health_after),
            playerCheckpoints=deepcopy(self.health_checkpoints),
            optionalCargoExit=deepcopy(self.cargo_exit),blockedReleases=deepcopy(self.blocked_releases),
            faintedFlightRetirements=deepcopy(self.fainted_flight_retirements),
            primaryRetirements=deepcopy(self.primary_retirements),
            primaryCurrentFrames=dict(self.primary_current_frames),primaryHealthyFrames=dict(self.primary_healthy_frames),
            survivors=survivors,
            ownershipCurrent=self.stage("window-complete"), endState=deepcopy(self.previous_state),
            activeThrows=[{k:deepcopy(v) for k,v in own.items() if k != "recorder"} for own in self.cycles.values()])

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("5000 continuous frames, three current searches, repeated Throw/landing, recovery pickup or cleanup proof is missing")
        return self.result()
