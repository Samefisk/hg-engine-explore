"""A current Wild Throw switches free Cargo without canceling accepted motion.

The fixture writes only normal Player, party and spawn setup. The switch,
claim, route, HELD control and launch all come from completed native frames.
"""
from copy import deepcopy
import struct

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.devtools_throw_cargo_competition_measurement import (
    ThrowCargoCompetitionMeasurement, require, tile,
)
from tools.overworld.devtools_wild_throw_moving_candidate_measurement import (
    validate_route_binding, TRIGGER_CONDITION, CARGO_CONDITION, THROW_RELEASE_BIT,
)
from tools.overworld.devtools_moving_cargo_pickup import pickup_motion
from tools.overworld.devtools_follower_throw_measurement import raw_handle

KIND = "throw-cargo-retarget-v1"
CASE = "wild.throw-cargo-retarget"
REQUIREMENT = "current.throw-cargo-retarget"
SUBJECTS = (("geodude", 74, "WILD", "spawn"),
            ("first-cargo", 155, "WILD", "spawn"),
            ("near-cargo", 70, "WILD", "spawn"))
LIMIT = 360
def stage_args(frames, stage):
    return dict(frames=frames, keys=[], until=dict(kind="measurement-stage",
                measurement=KIND, stage=stage, when="final"))

SETUP = (("throw-tile", "teleport", dict(map=33, x=584, z=402, facing=1)),
         ("prepare-passive-follower", "party", dict(slot=0, species=155, level=20)),
         ("create-passive-follower", "spawn", dict(species=155, form=0,
                                                      role="follower", slot=0, level=20)),
         ("spawn-first-cargo", "spawn", dict(species=155, form=0, role="wild",
                                               level=20, x=585, z=402)),
         ("bind-first-cargo", "bind", dict(subject="first-cargo")),
         ("spawn-geodude", "spawn", dict(species=74, form=0, role="wild",
                                           level=20, x=589, z=402)),
         ("bind-geodude", "bind", dict(subject="geodude")),
         ("wait-first-pursuit", "step", stage_args(160, "first-pursuit")),
         ("spawn-near-cargo", "spawn", dict(species=70, form=0, role="wild",
                                              level=20, x=588, z=403)),
         ("bind-near-cargo", "bind", dict(subject="near-cargo")))
ACTIONS = (("normal-cargo-retarget", "step", dict(frames=LIMIT, keys=[], until=dict(
    kind="measurement-complete", measurement=KIND, when="final"))),)


def validate_recipe(test):
    require(test["id"] == CASE and test["mode"] == "prepared"
            and test["requirements"] == [REQUIREMENT]
            and test["subjects"] == [dict(id=n, species=s, role=r, acquire=a)
                                     for n, s, r, a in SUBJECTS]
            and test["measurements"] == [dict(kind=KIND, subject="geodude")]
            and tuple((a["id"], a["op"], a["args"]) for a in test["setup"]) == SETUP
            and tuple((a["id"], a["op"], a["args"]) for a in test["actions"]) == ACTIONS
            and test["assertions"] == [dict(kind="measurement-complete", measurement=KIND,
                                             when="final")]
            and test["budgets"] == dict(maxSeconds=260, maxFrames=760,
                                         noProgressFrames=400, minObservedFrames=2),
            "Cargo retarget recipe differs from its normal bounded trigger")


class ThrowCargoRetargetMeasurement(ThrowCargoCompetitionMeasurement):
    def __init__(self, source):
        super().__init__(source)
        require(source["contractVersion"] == 2, "Cargo retarget needs sealed Query source")
        self.first_claim = self.near_query = self.near_route = self.switch = self.pickup = self.launch = None
        self.first_plan = None
        self.first_plan_finished = False
        self.held_frames = 0
        self.held_owners = []
        self.pending_spawn = None

    def _actor(self, sample, name):
        handle = select_current_actor(sample, self.subjects[name])["handle"]
        actor = next(a for a in sample["actors"] if a["handle"] == handle)
        require(actor["active"] is True and actor["presentationAttached"] is True
                and actor["role"] == "WILD"
                and actor["species"] == (74 if name == "geodude" else 70 if name == "near-cargo" else 155),
                "Cargo retarget lost a current full actor")
        return actor

    def _claim(self, sample, geodude, cargo):
        return self.helper._claim(sample, geodude, cargo)

    def _motion(self, sample, geodude):
        motion, control = pickup_motion(sample, geodude, self.source)
        require(control["movementActorControlMode"] == 0
                and motion == decode_motion(bytes.fromhex(motion["rawHex"])),
                "Cargo retarget changed ordinary native motion/control")
        return motion

    def _route_score(self, query, geodude, cargo):
        data = query["data"]
        raw = bytes.fromhex(data["resultHex"])
        origin = struct.unpack_from("<hh", raw, 24)
        standing = struct.unpack_from("<hh", raw, 48)
        reach = data["after"]["workspace"]["compatibility"]["pickupDistance"]
        require(raw[:12] == raw_handle(geodude["handle"])
                and raw[12:24] == raw_handle(cargo["handle"])
                and origin == tile(geodude, "logical")
                and standing != tile(cargo, "logical")
                and max(abs(standing[0]-tile(cargo,"logical")[0]),
                        abs(standing[1]-tile(cargo,"logical")[1])) <= reach
                and reach == 1,
                "Cargo retarget native route lacks its current pickup standing pose")
        return dict(origin=origin, standing=standing,
                    score=max(abs(origin[0]-standing[0]), abs(origin[1]-standing[1])),
                    pickupDistance=reach)

    def _sample(self, sample, events=(), *, observed=True):
        self._boundary(sample)
        geodude = self._actor(sample, "geodude")
        first = self._actor(sample, "first-cargo")
        near = self._actor(sample, "near-cargo") if "near-cargo" in self.subjects else None
        interaction = sample["pokemonCombat"]["interactions"]
        relation = interaction["throwState"]["targets"][geodude["handle"]["slot"]]
        first_raw, near_raw = first["handle"]["slot"] + 1, (
            near["handle"]["slot"] + 1 if near is not None else 0)
        require(relation == 0 or (relation & 63) in (
                    (first_raw,) if near is None else (first_raw, near_raw)),
                "Cargo retarget selected a different actor, including the passive follower")
        require(self.switch is None or (relation & 63) != first_raw,
                "Cargo retarget returned to the released first Cargo")
        self._claim(sample, geodude, first)
        if near is not None:
            self._claim(sample, geodude, near)
            holders = [r for r in interaction["carriers"]
                       if r["throw"]["carried"]
                       and r["throw"]["targetSlot"] == near["handle"]["slot"]]
            require(len(holders) <= 1 and (not holders or holders[0]["handle"] == geodude["handle"]),
                    "Cargo retarget has another HELD owner")
        row = next(r for r in interaction["carriers"] if r["handle"] == geodude["handle"])
        motion = self._motion(sample, geodude)
        native_events = [e for e in events if e.get("kind") == "native"
                         and e.get("data", {}).get("actorHandle") == geodude["handle"]["value"]]
        require(all(e.get("frame") == sample["frame"]
                    and e["data"].get("actor") == {k: v for k, v in geodude["handle"].items() if k != "value"}
                    and e["data"].get("event") not in ("MOTION_CANCELED", "ACTOR_REBOUND", "CONTEXT_CHANGED")
                    for e in native_events),
                "Cargo retarget canceled or rebound the accepted current movement")
        if self.first_claim is None and relation == first_raw:
            plan = motion["plan"]
            require(geodude["motionPhase"] == motion["phase"] == "MOVING"
                    and geodude["motionKind"] == "WALK" and plan["version"] == 1
                    and plan["kind"] == 1 and plan["flags"] == 0
                    and plan["reservationId"] == geodude["reservationId"] > 0
                    and plan["origin"] == [589, 403] and plan["target"] == [589, 402]
                    and 0 <= motion["elapsed"] <= plan["duration"] - 2,
                    "Cargo retarget first claim lacks the accepted northward Walk")
            first_queries = [q for q in self._queries(sample, events, geodude)
                             if q["data"]["status"] == "REACHABLE"
                             and q["data"]["after"]["workspace"]["compatibility"]["cargo"]
                                == first["handle"]]
            require(first_queries, "Cargo retarget first claim lacks its native Cargo route")
            first_route = self._route_score(first_queries[0], geodude, first)
            require(first_route["score"] == 3,
                    "Cargo retarget first pickup standing distance differs")
            validate_route_binding(row["bindings"]["trigger"], "PLAYER", TRIGGER_CONDITION)
            validate_route_binding(row["bindings"]["cargo"], "ACTOR", CARGO_CONDITION,
                                   first["handle"])
            self.first_claim = dict(frame=sample["frame"], actor=deepcopy(geodude),
                                    cargo=deepcopy(first), trigger=deepcopy(row["bindings"]["trigger"]),
                                    route=first_route)
            self.first_plan = deepcopy(plan)
        if self.first_plan is not None and not self.first_plan_finished:
            same = motion["plan"]["reservationId"] == self.first_plan["reservationId"]
            finished = any(e["data"].get("event") == "MOTION_FINISHED"
                           and e["data"].get("reason") == "OK"
                           and e["data"].get("valueB") == 1
                           and e["data"].get("actorFrame") == sample["actorFrame"]
                           for e in native_events)
            require((same and motion["plan"] == self.first_plan
                     and motion["phase"] not in ("CANCELED", "INVALID")) or finished,
                    "Cargo retarget changed the accepted Walk before its normal finish")
            self.first_plan_finished = finished
        if near is not None:
            queries = self._queries(sample, events, geodude)
            near_queries = [q for q in queries if q["data"]["status"] == "REACHABLE"
                            and q["data"]["after"]["workspace"]["compatibility"]["cargo"]
                            == near["handle"]]
            if near_queries and self.near_query is None:
                near_route = self._route_score(near_queries[0], geodude, near)
                near_route["oldLower"] = max(0, max(
                    abs(near_route["origin"][0]-tile(first,"logical")[0]),
                    abs(near_route["origin"][1]-tile(first,"logical")[1]))
                    - near_route["pickupDistance"])
                self.near_route = near_route
                self.near_query = deepcopy(near_queries[0])
            if self.switch is None and (relation & 63) == near_raw:
                require(self.first_claim is not None and self.near_query is not None
                        and self.near_route is not None
                        and self.first_claim["frame"] < sample["frame"]
                        and self.near_route["score"] < self.first_claim["route"]["score"]
                        and self.near_route["score"] + 1 <= self.near_route["oldLower"],
                        "Cargo retarget did not choose a nearer reachable current Cargo")
                state = interaction["throwState"]
                require(relation in (near_raw, near_raw | 128)
                        and self._claim(sample, geodude, near) is (not bool(relation & 128))
                        and row["bindings"]["trigger"] == self.first_claim["trigger"]
                        and not state["targetMask"] & (1 << first["handle"]["slot"])
                        and state["targetMask"] & (1 << near["handle"]["slot"]),
                        "Cargo retarget kept the old claim or changed Player Interest")
                if relation & 128:
                    # Capture and atomic pickup can complete in one native frame.
                    # Prove that Cargo was free at the preceding exact boundary;
                    # the current raw owner/control receipt proves the transfer.
                    prior_near = self._actor(self.latest, "near-cargo")
                    prior_holders = [r for r in self.latest["pokemonCombat"]["interactions"]["carriers"]
                                     if r["throw"]["carried"]
                                     and r["throw"]["targetSlot"] == near["handle"]["slot"]]
                    require(self.latest["frame"] + 1 == sample["frame"]
                            and prior_near["handle"] == near["handle"] and not prior_holders
                            and pickup_motion(self.latest, prior_near, self.source)[1]["movementActorControlMode"] == 0
                            and pickup_motion(sample, near, self.source)[1]["movementActorControlMode"] == 1
                            and len(holders) == 1
                            and self.near_query["frame"] == sample["frame"],
                            "Cargo retarget selected an already HELD Cargo")
                else:
                    require(pickup_motion(sample, near, self.source)[1]["movementActorControlMode"] == 0,
                            "Cargo retarget selected an already HELD Cargo")
                self.switch = dict(frame=sample["frame"], actor=deepcopy(geodude),
                                   first=deepcopy(first), near=deepcopy(near),
                                   query=deepcopy(self.near_query), route=deepcopy(self.near_route),
                                   motion=deepcopy(motion))
            if relation & 128 and (relation & 63) == near_raw:
                require(self.switch is not None and row["bindings"]["cargo"]["target"]
                        == dict(kind="ACTOR", actor=near["handle"])
                        and len(holders) == 1,
                        "Cargo retarget HELD a different owner or stale Cargo")
                if self.pickup is None:
                    self.pickup = dict(frame=sample["frame"], actor=deepcopy(geodude),
                                       near=deepcopy(near))
                self.held_frames += 1
                self.held_owners.append(dict(frame=sample["frame"],
                                             actor=deepcopy(geodude["handle"]),
                                             cargo=deepcopy(near["handle"])))
                require(next(r for r in sample["pokemonCombat"]["movementTimers"]
                             if r["handle"] == near["handle"])["movementActorControlMode"] == 1,
                        "Cargo retarget lost HELD control before launch")
            if self.pickup is not None and self.launch is None and not (relation & 128):
                cargo_motion = next(r["motion"] for r in sample["pokemonCombat"]["targets"]
                                    if r["handle"] == near["handle"])
                starts = [e for e in events if e.get("kind") == "native"
                          and e["data"].get("event") == "MOTION_STARTED"
                          and e["data"].get("actorHandle") == near["handle"]["value"]]
                require(relation == 0 and len(starts) == 1
                        and near["motionKind"] == "HOP" and near["motionPhase"] == "MOVING"
                        and cargo_motion == decode_motion(bytes.fromhex(cargo_motion["rawHex"]))
                        and cargo_motion["plan"]["flags"] == 0
                        and cargo_motion["plan"]["reservationId"] == near["reservationId"] > 0
                        and geodude["matchedLayerMask"] & THROW_RELEASE_BIT
                        and self.held_frames >= 2,
                        "Cargo retarget lacks the same Cargo normal launch")
                self.launch = dict(frame=sample["frame"], cargo=deepcopy(near),
                                   event=deepcopy(starts[0]))
        if observed:
            self.observed_frames += 1
        require(self.observed_frames <= LIMIT, "Cargo retarget exceeded its bounded window")
        self.latest = deepcopy(sample)

    def observe_record(self, row, on_sample=None):
        try:
            if "initialSnapshot" in row:
                require(self.latest is None and row["phase"] == "setup",
                        "Cargo retarget initial boundary differs")
                self.latest = deepcopy(row["initialSnapshot"])
                return self.result()
            if row.get("phase") == "setup":
                name, op, args = SETUP[self.setup_index]
                require(row.get("action") == name, "Cargo retarget setup order differs")
                if op == "step":
                    for sample, events, _ in validate_raw_chunk(row, self.latest):
                        self._sample(sample, events, observed=False)
                        if on_sample: on_sample(sample, self.observed_frames)
                    if self.stage("first-pursuit"): self.setup_index += 1
                    return self.result()
                require(row.get("command") == op, "Cargo retarget setup command differs")
                sample = row["snapshot"]
                self._boundary(sample)
                if name == "create-passive-follower":
                    actors = [a for a in sample["actors"] if a["active"] and a["role"] == "FOLLOWER"]
                    require(len(actors) == 1 and row["receipt"].get("lifecycle")
                            == "prepared-native-follower-lifecycle",
                            "Cargo retarget passive follower lifecycle differs")
                    self.passive_subject = select_current_actor(sample, actors[0])
                if op == "bind":
                    self.subjects[args["subject"]] = deepcopy(row["receipt"])
                    self._actor(sample, args["subject"])
                    if name == "bind-near-cargo":
                        require(self.pending_spawn is not None
                                and sample == self.pending_spawn["sample"],
                                "Cargo retarget near bind skipped its spawn boundary")
                        prior = self.pending_spawn["previous"]
                        self.latest = prior
                        self._sample(self.pending_spawn["sample"],
                                     self.pending_spawn["events"], observed=False)
                        self.pending_spawn = None
                if name == "spawn-near-cargo":
                    events = row["receipt"].get("events")
                    require(type(events) is list and sample["frame"] == self.latest["frame"] + 1
                            and all(e.get("frame") == sample["frame"] for e in events)
                            and row["receipt"].get("setupBoundary", {}).get("eventsDrained") is True,
                            "Cargo retarget near spawn lacks its adjacent retained native events")
                    self.pending_spawn = dict(sample=deepcopy(sample), events=deepcopy(events),
                                              previous=deepcopy(self.latest))
                self.latest = deepcopy(sample)
                self.setup_index += 1
                return self.result()
            require(self.setup_index == len(SETUP) and row.get("phase") == "observe"
                    and row.get("action") == ACTIONS[0][0] and "command" not in row,
                    "Cargo retarget normal action differs")
            for sample, events, _ in validate_raw_chunk(row, self.latest):
                self._sample(sample, events)
                if on_sample: on_sample(sample, self.observed_frames)
        except (KeyError, TypeError, ValueError, StopIteration, IndexError) as exc:
            self.failures.append(str(exc))
        return self.result()

    def stage(self, name):
        return not self.failures and name == "first-pursuit" and self.first_claim is not None

    def result(self):
        return dict(ready=not self.failures and self.switch is not None and self.pickup is not None
                    and self.launch is not None and self.first_plan_finished,
                    observedFrames=self.observed_frames, observedFrameUnit="completed-game-frame",
                    requirements=[REQUIREMENT], subjects=deepcopy(self.subjects),
                    firstClaim=deepcopy(self.first_claim), nearQuery=deepcopy(self.near_query),
                    switch=deepcopy(self.switch), pickup=deepcopy(self.pickup),
                    launch=deepcopy(self.launch), firstPlanFinished=self.first_plan_finished,
                    heldFrames=self.held_frames, heldOwners=deepcopy(self.held_owners),
                    failures=list(self.failures))

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("Cargo retarget ended before the current switch, normal Walk finish, HELD and launch")
        return dict(passed=self.result()["ready"], failures=list(self.failures))
