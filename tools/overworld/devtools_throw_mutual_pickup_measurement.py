"""Prove two current Wild Geodude can pursue each other before one Throw pickup."""
from copy import deepcopy
import struct

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_wild_throw_moving_candidate_measurement import (
    WildThrowMovingCandidateMeasurement, require, tile, validate_route_binding,
    TRIGGER_CONDITION, CARGO_CONDITION, THROW_APPLICATION_BIT, THROW_RELEASE_BIT,
)
from tools.overworld.devtools_moving_cargo_pickup import pickup_motion, checked_moving_pickup
from tools.overworld.devtools_throw_cargo_competition_measurement import ThrowCargoCompetitionMeasurement

KIND = "throw-mutual-pickup-v1"
CASE = "wild.throw-mutual-pickup"
REQUIREMENT = "current.throw-mutual-pickup"
SUBJECTS = (("geodude-a", 74, "WILD", "spawn"),
            ("geodude-b", 74, "WILD", "spawn"))
LIMIT = 180
SETUP = (("pair-tile", "teleport", dict(map=33, x=586, z=406, facing=1)),
         ("prepare-passive-follower", "party", dict(slot=0, species=155, level=20)),
         ("create-passive-follower", "spawn", dict(species=155, form=0,
                                                      role="follower", slot=0, level=20)),
         ("spawn-geodude-a", "spawn", dict(species=74, form=0, role="wild",
                                             level=20, x=584, z=402)),
         ("bind-geodude-a", "bind", dict(subject="geodude-a")),
         ("spawn-geodude-b", "spawn", dict(species=74, form=0, role="wild",
                                             level=20, x=588, z=402)),
         ("bind-geodude-b", "bind", dict(subject="geodude-b")))
ACTIONS = (("normal-mutual-pickup", "step", dict(frames=LIMIT, keys=[], until=dict(
    kind="measurement-complete", measurement=KIND, when="final"))),)


def validate_recipe(test):
    require(test["id"] == CASE and test["mode"] == "prepared"
            and test["requirements"] == [REQUIREMENT]
            and test["subjects"] == [dict(id=n, species=s, role=r, acquire=a)
                                     for n, s, r, a in SUBJECTS]
            and test["measurements"] == [dict(kind=KIND, subject="geodude-a")]
            and tuple((a["id"], a["op"], a["args"]) for a in test["setup"]) == SETUP
            and tuple((a["id"], a["op"], a["args"]) for a in test["actions"]) == ACTIONS
            and test["assertions"] == [dict(kind="measurement-complete", measurement=KIND,
                                             when="final")]
            and test["budgets"] == dict(maxSeconds=180, maxFrames=520,
                                         noProgressFrames=220, minObservedFrames=2),
            "mutual pickup recipe differs from the bounded normal pair")


class ThrowMutualPickupMeasurement:
    def __init__(self, source):
        require(source["contractVersion"] == 2, "mutual pickup needs sealed Query source")
        self.source = source
        self.latest = None
        self.subjects = {}
        self.passive_subject = None
        self.setup_index = 0
        self.observed_frames = 0
        self.failures = []
        self.helper = WildThrowMovingCandidateMeasurement(source)
        self.first_claim = self.mutual = self.pickup = self.launch = None
        self.held_frames = 0
        self.held_motion = None
        self.waiting = False

    def _boundary(self, sample):
        require(sample.get("observationBoundary") == "main-task-queue-completion"
                and sample.get("fieldAvailable") is True
                and type(sample.get("frame")) is int and type(sample.get("nativeCycle")) is int
                and type(sample.get("actorFrame")) is int
                and sample.get("context", {}).get("mapId") == 33
                and sample.get("fieldControl", {}).get("taskPointer") == 0
                and (sample["player"]["x"], sample["player"]["y"]) == (586, 406),
                "mutual pickup left its normal field boundary")
        if self.passive_subject is not None:
            follower = select_current_actor(sample, self.passive_subject)
            actor = next(a for a in sample["actors"] if a["handle"] == follower["handle"])
            require(actor["species"] == 155 and actor["role"] == "FOLLOWER"
                    and actor["level"] == 20 and actor["active"] is True
                    and actor["presentationAttached"] is True
                    and not actor.get("matchedLayerMask", 0) & THROW_APPLICATION_BIT,
                    "mutual pickup passive follower changed")

    def _actor(self, sample, name):
        handle = select_current_actor(sample, self.subjects[name])["handle"]
        actor = next(a for a in sample["actors"] if a["handle"] == handle)
        require(actor["active"] is True and actor["presentationAttached"] is True
                and actor["role"] == "WILD" and actor["species"] == 74
                and actor["level"] == 20,
                "mutual pickup lost a current full Geodude")
        return actor

    def _rows(self, sample):
        actors = {name: self._actor(sample, name) for name in ("geodude-a", "geodude-b")}
        inter = sample["pokemonCombat"]["interactions"]
        state = inter["throwState"]
        rows = {}
        for name, actor in actors.items():
            target = actors["geodude-b" if name == "geodude-a" else "geodude-a"]
            self.helper._claim(sample, actor, target)
            found = [row for row in inter["carriers"] if row["handle"] == actor["handle"]]
            require(len(found) == 1 and found[0]["available"] is True
                    and found[0]["role"] == "WILD", "mutual pickup carrier row is absent")
            row = found[0]
            raw = bytes.fromhex(row["rawBindingsHex"])
            require(len(raw) == 60 and raw[:12] == raw_handle(actor["handle"])
                    and raw[12:36].hex() == row["bindings"]["trigger"]["rawHex"]
                    and raw[36:60].hex() == row["bindings"]["cargo"]["rawHex"],
                    "mutual pickup raw binding owner differs")
            encoded = state["targets"][actor["handle"]["slot"]]
            require(row["throw"] == dict(targetRaw=encoded,
                    targetSlot=(encoded & 63) - 1 if encoded else None,
                    carried=bool(encoded & 128), windup=bool(encoded & 64),
                    targeted=bool(state["targetMask"] & (1 << actor["handle"]["slot"])),
                    carrier=bool(state["carrierMask"] & (1 << actor["handle"]["slot"])),
                    recovering=bool(state["recoveringMask"] & (1 << actor["handle"]["slot"]))),
                    "mutual pickup decoded native claim differs")
            if encoded:
                require((encoded & 63) == target["handle"]["slot"] + 1,
                        "mutual pickup changed its exact Cargo")
                validate_route_binding(row["bindings"]["trigger"], "PLAYER", TRIGGER_CONDITION)
                validate_route_binding(row["bindings"]["cargo"], "ACTOR",
                                       CARGO_CONDITION, target["handle"])
            rows[name] = (actor, row, encoded)
        return actors, rows, state

    def _sample(self, sample, events=()):
        self._boundary(sample)
        actors, rows, state = self._rows(sample)
        a, ar, ae = rows["geodude-a"]
        b, br, be = rows["geodude-b"]
        a_to_b, b_to_a = b["handle"]["slot"] + 1, a["handle"]["slot"] + 1
        holders = [(name, actor, target, encoded) for name, (actor, _, encoded) in rows.items()
                   for target in [actors["geodude-b" if name == "geodude-a" else "geodude-a"]]
                   if encoded & 128]
        require(len(holders) <= 1, "mutual pickup has two HELD owners")
        if self.first_claim is None and ae == a_to_b:
            motion, control = pickup_motion(sample, a, self.source)
            require(be == 0 and a["motionKind"] == "WALK"
                    and a["motionPhase"] == "MOVING" and a["reservationId"] > 0
                    and motion["plan"]["flags"] == 0
                    and motion["plan"]["reservationId"] == a["reservationId"]
                    and motion["plan"]["kind"] == 1
                    and control["movementActorControlMode"] == 0,
                    "mutual pickup first pursuit is not an accepted Walk")
            self.first_claim = dict(frame=sample["frame"], actor=deepcopy(a),
                                    target=deepcopy(b), row=deepcopy(ar))
        if self.first_claim is not None and self.pickup is None and not holders:
            require(ae == a_to_b and not ae & 192,
                    "mutual pickup dropped a valid incoming pursuit")
            if self.mutual is not None:
                require(be == b_to_a and not be & 192,
                        "mutual pickup dropped a valid outgoing pursuit")
            elif be == b_to_a:
                queries = ThrowCargoCompetitionMeasurement._queries(self, sample, events, b)
                require(queries and any(q["data"]["status"] == "REACHABLE"
                        and q["data"]["after"]["workspace"]["owner"] == b["handle"]
                        and q["data"]["after"]["workspace"]["compatibility"]["cargo"] == a["handle"]
                        and bytes.fromhex(q["data"]["resultHex"])[:24]
                            == raw_handle(b["handle"]) + raw_handle(a["handle"])
                        for q in queries)
                        and sample["frame"] > self.first_claim["frame"]
                        and state["targetMask"] & (1 << a["handle"]["slot"])
                        and state["targetMask"] & (1 << b["handle"]["slot"])
                        and state["carrierMask"] & (1 << a["handle"]["slot"])
                        and state["carrierMask"] & (1 << b["handle"]["slot"]),
                        "mutual pickup lacks two fresh current unheld claims")
                self.mutual = dict(frame=sample["frame"], a=deepcopy(a), b=deepcopy(b),
                                   query=deepcopy(queries[-1]))
        if holders and self.pickup is None:
            name, owner, cargo, encoded = holders[0]
            loser_name = "geodude-b" if name == "geodude-a" else "geodude-a"
            loser, loser_row, loser_encoded = rows[loser_name]
            require(self.mutual is not None and sample["frame"] > self.mutual["frame"]
                    and encoded & 63 == cargo["handle"]["slot"] + 1
                    and loser_encoded == 0 and loser_row["bindings"]["cargo"]["bound"] is False
                    and not state["carrierMask"] & (1 << loser["handle"]["slot"]),
                    "mutual pickup did not give one physical winner full ownership")
            _, control = pickup_motion(sample, cargo, self.source)
            require(control["movementActorControlMode"] == 1
                    and cargo["reservationId"] == 0,
                    "mutual pickup HELD Cargo lacks native control")
            if cargo["motionPhase"] == "CANCELED":
                checked_moving_pickup(self.latest, sample, events, self.source,
                                      self._actor(self.latest, loser_name), cargo,
                                      self._actor(self.latest, name), owner)
                self.held_motion = deepcopy(pickup_motion(sample, cargo, self.source)[0])
            self.pickup = dict(frame=sample["frame"], owner=deepcopy(owner),
                               cargo=deepcopy(cargo), loser=deepcopy(loser),
                               state=deepcopy(state))
        if self.pickup is not None and self.launch is None:
            owner_name = "geodude-a" if self.pickup["owner"]["handle"] == a["handle"] else "geodude-b"
            owner, _, encoded = rows[owner_name]
            cargo = actors["geodude-b" if owner_name == "geodude-a" else "geodude-a"]
            if encoded & 128:
                loser_name = "geodude-b" if owner_name == "geodude-a" else "geodude-a"
                loser_row = rows[loser_name][1]
                require(len(holders) == 1 and holders[0][1]["handle"] == owner["handle"]
                        and encoded & 63 == cargo["handle"]["slot"] + 1
                        and rows[loser_name][2] == 0
                        and loser_row["bindings"]["cargo"]["bound"] is False
                        and cargo["reservationId"] == 0
                        and (cargo["motionPhase"] == "CANCELED" if self.held_motion is not None
                             else cargo["motionKind"] == "NONE" and cargo["motionPhase"] == "IDLE"),
                        "mutual pickup lost its one protected HELD owner")
                current_motion, control = pickup_motion(sample, cargo, self.source)
                require(control["movementActorControlMode"] == 1,
                        "mutual pickup lost HELD native control")
                if self.held_motion is not None:
                    require(current_motion == self.held_motion,
                            "mutual pickup changed the canceled Cargo plan while HELD")
                self.held_frames += 1
            else:
                native = next(row["motion"] for row in sample["pokemonCombat"]["targets"]
                              if row["handle"] == cargo["handle"])
                motion = decode_motion(bytes.fromhex(native["rawHex"]))
                starts = [event for event in events if event.get("kind") == "native"
                          and event.get("data", {}).get("event") == "MOTION_STARTED"
                          and event["data"].get("actorHandle") == cargo["handle"]["value"]]
                require(encoded == 0 and len(starts) == 1
                        and starts[0]["data"]["actor"] == {k: v for k, v in cargo["handle"].items()
                                                           if k != "value"}
                        and cargo["motionKind"] == "HOP" and cargo["motionPhase"] == "MOVING"
                        and motion == native and motion["plan"]["flags"] == 0
                        and motion["plan"]["reservationId"] == cargo["reservationId"] > 0
                        and owner["matchedLayerMask"] & THROW_RELEASE_BIT
                        and self.held_frames >= 2,
                        "mutual pickup lacks its normal exact Cargo launch")
                self.launch = dict(frame=sample["frame"], owner=deepcopy(owner),
                                   cargo=deepcopy(cargo), event=deepcopy(starts[0]))
        self.observed_frames += 1
        require(self.observed_frames <= LIMIT, "mutual pickup exceeded its normal frame window")
        self.latest = deepcopy(sample)

    def observe_record(self, row, on_sample=None):
        try:
            if "initialSnapshot" in row:
                require(self.latest is None and row["phase"] == "setup",
                        "mutual pickup initial boundary differs")
                self.latest = deepcopy(row["initialSnapshot"])
                return self.result()
            if row.get("phase") == "setup":
                name, op, args = SETUP[self.setup_index]
                require(row.get("action") == name and row.get("command") == op,
                        "mutual pickup setup order differs")
                sample = row["snapshot"]
                self._boundary(sample)
                if name == "create-passive-follower":
                    followers = [actor for actor in sample["actors"]
                                 if actor["active"] and actor["role"] == "FOLLOWER"]
                    require(len(followers) == 1
                            and row["receipt"].get("lifecycle") == "prepared-native-follower-lifecycle",
                            "mutual pickup passive follower lifecycle differs")
                    self.passive_subject = select_current_actor(sample, followers[0])
                if op == "bind":
                    self.subjects[args["subject"]] = deepcopy(row["receipt"])
                    self._actor(sample, args["subject"])
                self.latest = deepcopy(sample)
                self.setup_index += 1
                return self.result()
            require(self.setup_index == len(SETUP) and row.get("phase") == "observe"
                    and row.get("action") == ACTIONS[0][0] and "command" not in row,
                    "mutual pickup normal action differs")
            for sample, events, _ in validate_raw_chunk(row, self.latest):
                self._sample(sample, events)
                if on_sample:
                    on_sample(sample, self.observed_frames)
        except (KeyError, TypeError, ValueError, StopIteration, IndexError) as exc:
            self.failures.append(str(exc))
        return self.result()

    def result(self):
        return dict(ready=not self.failures and self.launch is not None,
                    observedFrames=self.observed_frames,
                    observedFrameUnit="completed-game-frame",
                    requirements=[REQUIREMENT], subjects=deepcopy(self.subjects),
                    firstClaim=deepcopy(self.first_claim), mutual=deepcopy(self.mutual),
                    pickup=deepcopy(self.pickup), launch=deepcopy(self.launch),
                    heldFrames=self.held_frames, failures=list(self.failures))

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("mutual pickup ended without two pursuits, one HELD owner and normal launch")
        return dict(passed=self.result()["ready"], failures=list(self.failures))
