"""Native distance maintenance from free chase through a valid protected pickup.

Only the existing authenticated helper receipt, current actor/binding reader,
semantic terminal events and native deletion telemetry supply evidence.
"""
from copy import deepcopy
import struct

from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_throw_cargo_flee_measurement import ThrowCargoFleeMeasurement
from tools.overworld.normal_play_observer import MotionRecorder, complete_travel

ROUTE = "distance-despawn-route29-v1"
CITY = "distance-despawn-cherrygrove-v1"
KINDS = frozenset((ROUTE, CITY))
BOUNDARY = "main-task-queue-completion"
SUBJECTS = (("cargo", 179), ("carrier", 74), ("unrelated", 143))
CASES = {ROUTE: ("population.distance-despawn-route29", 33, 585, 409),
         CITY: ("population.distance-despawn-cherrygrove", 67, 565, 398)}
REMOTE = {ROUTE: (590, 392), CITY: (547, 394)}
CARGO = {ROUTE: (585, 412), CITY: (565, 394)}
CARRIER = {ROUTE: (585, 406), CITY: (565, 395)}
EXIT = {ROUTE: 2, CITY: -2}
KEY = {ROUTE: "DOWN", CITY: "UP"}
MAX_FRAMES = 400


def require(value, message):
    if not value:
        raise ValueError("Distance despawn: " + message)


def requirement(kind):
    require(kind in KINDS, "unknown map case")
    return "current." + CASES[kind][0]


def setup(kind):
    _, map_id, x, y = CASES[kind]
    cx, cy = CARGO[kind]
    gx, gy = CARRIER[kind]
    rx, ry = REMOTE[kind]
    values = [("distance-tile", "teleport", dict(map=map_id, x=x, z=y, facing=1)),
              ("prepare-passive-follower", "party", dict(slot=0, species=155, level=10)),
              ("create-passive-follower", "spawn", dict(species=155, form=0, role="follower", slot=0, level=10))]
    # Every tile in the vertical Cargo/carrier/player corridor needs native
    # current support; endpoints alone did not prove the Cherrygrove route.
    require(cx == gx == x, "fixture corridor is not vertical")
    for ty in range(min(cy, gy, y), max(cy, gy, y)+1):
        values.append(("terrain-corridor-"+str(ty), "terrain", dict(radius=0, x=x, z=ty)))
    values += [
              ("spawn-cargo", "spawn", dict(species=179, form=0, role="wild", level=5, x=cx, z=cy)),
              ("bind-cargo", "bind", dict(subject="cargo")),
              ("walk-cargo-before-carrier", "step", dict(frames=300, keys=[], until=dict(
                  kind="actor-field", subject="cargo", path="motionKind", operator="eq", value="WALK", when="final"))),
              ("terrain-carrier", "terrain", dict(radius=0, x=gx, z=gy)),
              ("spawn-carrier", "spawn", dict(species=74, form=0, role="wild", level=5, x=gx, z=gy)),
              ("bind-carrier", "bind", dict(subject="carrier")),
              ("natural-cargo-claim", "step", dict(frames=240, keys=[], until=dict(
                  kind="measurement-stage", measurement=kind, stage="claim-bound", when="final")))]
    # Spawn the unrelated actor only after a real current claim is observed.
    for name, tx, ty in (("unrelated", rx, ry), ("first-step", x, y+EXIT[kind]//2), ("second-step", x, y+EXIT[kind])):
        values.append(("terrain-"+name, "terrain", dict(radius=0, x=tx, z=ty)))
    values += [("spawn-unrelated", "spawn", dict(species=143, form=0, role="wild", level=5, x=rx, z=ry)),
               ("bind-unrelated", "bind", dict(subject="unrelated"))]
    return tuple(values)


def actions(kind):
    _, map_id, x, y = CASES[kind]
    delta = EXIT[kind] // 2
    values = []
    # Stop held input as soon as stock movement admits the logical tile.
    # Neutral frames then settle that exact step without admitting a third one.
    def leg(name, target_y):
        values.extend(((name, "step", dict(frames=16, keys=[KEY[kind]], until=dict(
            kind="player-field", path="y", operator="eq", value=target_y, when="final"))),
            (name+"-settle", "step", dict(frames=16, keys=[], until=dict(
                kind="player-settled-at", map=map_id, x=x, z=target_y, when="final")))))
    leg("walk-first-tile", y+delta)
    values.append(("first-scheduled-far-sample", "step", dict(frames=240, keys=[], until=dict(
        kind="measurement-stage", measurement=kind, stage="first-far-sample", when="final"))))
    # A new ordinary step requests the second maintenance cycle. These tiles
    # already have current native terrain receipts in the Cargo corridor.
    leg("request-second-sample", y+2*delta)
    values.append(("scheduled-distance-removal", "step", dict(frames=240, keys=[], until=dict(
        kind="measurement-complete", measurement=kind, when="final"))))
    return tuple(values)


def validate_recipe(test):
    kind = test["measurements"][0]["kind"]
    require(kind in KINDS and test["id"] == CASES[kind][0] and test["mode"] == "prepared"
            and test["requirements"] == [requirement(kind)]
            and test["subjects"] == [dict(id=n, species=s, role="WILD", acquire="spawn") for n,s in SUBJECTS]
            and test["measurements"] == [dict(kind=kind, subject="unrelated")]
            and tuple((a["id"], a["op"], a["args"]) for a in test["setup"]) == setup(kind)
            and tuple((a["id"], a["op"], a["args"]) for a in test["actions"]) == actions(kind)
            and test["assertions"] == [dict(kind="measurement-complete", measurement=kind, when="final")]
            and test["budgets"] == dict(maxSeconds=240, maxFrames=800, noProgressFrames=240, minObservedFrames=2),
            "exact normal-input fixture differs")


def telemetry(state):
    raw = bytes.fromhex(state["telemetryHex"])
    require(len(raw) == 336 and struct.unpack_from("<I", raw)[0] in (0, 0x4F574450)
            and raw[6] < 8 and raw[7] == 0
            and struct.unpack_from("<H", raw, 4)[0] == state["telemetrySequence"]
            and raw[6] == state["telemetryWriteIndex"], "telemetry owner, extent or sequence differs")
    rows = []
    keys = ("objectPtr", "objectFlags", "personality", "sequence", "mapId", "spawnMapId",
            "mapGeneration", "encounterGeneration", "objectX", "objectY", "playerX", "playerY",
            "objectId", "reason", "action", "slot", "distance", "contextFlags", "expectedObjectId")
    for index in range(8):
        rows.append(dict(zip(keys, struct.unpack_from("<III5H5h6B", raw, 16+40*index))))
    return rows


class DistanceDespawnMeasurement:
    def __init__(self, test, source):
        validate_recipe(test)
        self.kind = test["measurements"][0]["kind"]
        self.source = source
        self.map_id = CASES[self.kind][1]
        self.latest = None
        self.context = None
        self.subjects = {}
        self.setup_index = self.action_index = self.observed_frames = 0
        self.failures = []
        self.claim_frame = None
        self.free_chase = None
        self.owner = None
        self.calls = []
        self.far = []
        self.deferred = None
        self.terminal = None
        self.deleted = None
        self.motion_events = []
        self.motion = MotionRecorder()
        self.motion_armed = False
        self.prepared = {}
        self.last_sequence = 0

    def _boundary(self, sample, fixture=True):
        require(sample.get("fieldAvailable") is True and sample.get("observationBoundary") == BOUNDARY
                and sample.get("romSha256") == self.source["romSha256"]
                and sample.get("fieldControl", {}).get("taskPointer") == 0,
                "missing current completed Field or battle")
        if fixture:
            require(sample.get("context", {}).get("mapId") == self.map_id, "left the exact map case")

    def _actor(self, sample, name):
        selected = select_current_actor(sample, self.subjects[name])
        return next(a for a in sample["actors"] if a["handle"] == selected["handle"])

    def _unrelated(self, sample):
        actor = next((a for a in sample["actors"]
                      if a.get("handle") == self.subjects["unrelated"]["handle"]), None)
        if actor is None:
            return None
        if "engineObject" in actor:
            actor = self._actor(sample, "unrelated")
            require(isinstance(actor["engineObject"], dict), "unrelated actor has no current native pose")
            return actor
        # Native DELETE can precede removal of the resident Actor row. Only
        # the exact cleared native owner may reach the fresh DELETE checks.
        engine, source = actor.get("engineIdentity", {}), actor.get("sourceIdentity", {})
        subject = self.subjects["unrelated"]
        require(actor.get("identityVerified") is False
                and all(actor.get(k) == subject.get(k) for k in
                        ("subjectIdentity", "species", "role", "authorityGeneration",
                         "engineAnchorGeneration", "presentationGeneration"))
                and engine.get("pointer") == 0 and engine.get("in_manager") is False
                and engine.get("active") is False
                and all(source.get(k) == 0 for k in ("object", "active", "personality", "species"))
                and actor.get("motionKind") == "NONE" and actor.get("motionPhase") == "IDLE"
                and actor.get("reservationId") == 0,
                "unrelated actor lost its native pose without a cleared owner")
        return None

    def _claim(self, sample):
        cargo = self._actor(sample, "cargo")
        carrier = self._actor(sample, "carrier")
        # The shared admission checks the full current Cargo and native masks
        # before its final free-only result. A later pickup keeps that claim.
        free = ThrowCargoFleeMeasurement._claim(self, sample, cargo, carrier)
        value = sample["pokemonCombat"]["interactions"]
        row = next(r for r in value["carriers"] if r["handle"] == carrier["handle"])
        state = value["throwState"]
        slot = carrier["handle"]["slot"]
        encoded = state["targets"][slot]
        if not free and not (encoded & 128 and (encoded & 63) == cargo["handle"]["slot"]+1):
            return False, cargo, carrier
        expect = dict(targetRaw=encoded, targetSlot=(encoded & 63)-1,
            carried=bool(encoded & 128), windup=bool(encoded & 64),
            targeted=bool(state["targetMask"] & (1 << slot)),
            carrier=bool(state["carrierMask"] & (1 << slot)),
            recovering=bool(state["recoveringMask"] & (1 << slot)))
        require(row.get("throw") == expect and not expect["recovering"]
                and not state["recoveringMask"] & (1 << cargo["handle"]["slot"]),
                "current claim flags differ or entered recovery")
        raw = bytes.fromhex(row["rawBindingsHex"])
        for name, offset, kind in (("trigger", 12, 1), ("cargo", 36, 2)):
            binding = row["bindings"][name]
            data = raw[offset:offset+24]
            require(binding.get("bound") is True and binding.get("targetCurrent") is True
                    and data.hex() == binding.get("rawHex") and data[12:14] == bytes([kind,0])
                    and struct.unpack_from("<HIBBBB", data, 14) ==
                        (binding["sourceConditionId"], binding["expiresAt"], binding["sourceApplication"],
                         binding["lifetime"], binding["flags"], binding["reason"])
                    and binding["flags"] == 1 and binding["reason"] == 0
                    and binding["sourceConditionId"] != 65535 and binding["sourceApplication"] < 32,
                    "Trigger or Cargo binding is missing, stale or malformed")
        require(row["bindings"]["trigger"]["target"] == dict(kind="PLAYER", actor=None)
                and raw[12:24] == bytes(12), "claim no longer has its current Player Trigger")
        if encoded & 128:
            require(cargo["motionKind"] == "NONE" and cargo["motionPhase"] == "IDLE"
                    and cargo["reservationId"] == 0
                    and all(cargo["engineObject"][k] == carrier["engineObject"][k] for k in ("x","y")),
                    "held Cargo has no current native pickup basis or entered flight")
        elif self.claim_frame is None:
            self.claim_frame = sample["frame"]
        return True, cargo, carrier

    def _state(self, value):
        for key in ("lastKnownX", "lastKnownY", "farSamples"):
            require(isinstance(value.get(key), list) and len(value[key]) == 10
                    and all(type(n) is int for n in value[key]), "distance receipt array differs")
        require(all(0 <= n <= 2 for n in value["farSamples"])
                and type(value.get("distanceDespawnPendingMask")) is int
                and not value["distanceDespawnPendingMask"] >> 10
                and value.get("managerRestoreMask") == 0, "distance receipt is not current")
        claim = value["throwState"]
        require(len(claim["targets"]) == 10 and all(type(n) is int and 0 <= n <= 255 for n in claim["targets"])
                and all(type(claim[k]) is int and not claim[k] >> 10
                        for k in ("targetMask", "carrierMask", "recoveringMask")), "native claim width differs")
        return telemetry(value)

    def _receipt(self, sample, event, valid_claim, cargo, carrier):
        d = event["data"]
        require(event["frame"] == sample["frame"] and d.get("scope") == "native scheduled distance-maintenance entry/return"
                and d.get("acceptedProof") is False and d.get("diagnosticOnly") is True
                and d.get("setupMode") == "prepared" and type(d.get("sequence")) is int
                and d["sequence"] > self.last_sequence
                and self.latest["actorFrame"] <= d.get("entryActorFrame", -1) == d.get("returnActorFrame") <= sample["actorFrame"]
                and self.latest["nativeCycle"] <= d.get("entryNativeCycle", -1) <= d.get("returnNativeCycle", -1) <= sample["nativeCycle"],
                "distance maintenance clock, sequence or source differs")
        self.last_sequence = d["sequence"]
        world = d["worldContext"]
        require(all(world.get(k) == sample["context"].get(k) for k in ("mapId", "fieldEpoch", "mapGeneration"))
                and d["fieldPointer"] == world["fieldPointer"] == sample["fieldControl"]["fieldPointer"]
                and d["statePointer"] == world["statePointer"], "distance maintenance belongs to a stale owner")
        owner = {k:d[k] for k in ("fieldPointer", "statePointer", "runtimePointer", "presentationPointer", "telemetryPointer", "resetSlotPointer")}
        if self.owner is None: self.owner = owner
        require(owner == self.owner, "distance maintenance owner or reset callback changed")
        call = sample["nativeObservation"].get("calls", {}).get("distance-maintenance", {})
        require(call.get("address") == self.source["helperAddress"]
                and call.get("entrySha256") == self.source["helperEntrySha256"]
                and call.get("nonmatchingEntries") == 0, "distance helper differs from current sealed body")
        before, after = d["before"], d["after"]
        self._state(before); rows = self._state(after)
        step = (after["telemetrySequence"]-before["telemetrySequence"]) & 65535
        require(step <= 8, "distance deletion receipt was overwritten")
        fresh = []
        for seq_offset in range(1, step+1):
            seq = (before["telemetrySequence"]+seq_offset) & 65535
            found = [r for r in rows if r["sequence"] == seq]
            require(len(found) == 1, "distance deletion telemetry sequence is missing")
            fresh.extend(found)
        slot = self.subjects["unrelated"]["handle"]["slot"]
        bit = 1 << slot
        deletes = [r for r in fresh if r["slot"] == slot]
        prior = next((a for a in (self.latest or {}).get("actors", [])
                      if a.get("handle") == self.subjects["unrelated"]["handle"]), None)
        current = self._unrelated(sample)
        if not valid_claim:
            require(not deletes and not self.far, "Cargo claim ended before distance removal")
            return
        for value in (before, after):
            claim = value["throwState"]
            cb, tb = 1 << carrier["handle"]["slot"], 1 << cargo["handle"]["slot"]
            encoded = claim["targets"][carrier["handle"]["slot"]]
            require((encoded & 63) == cargo["handle"]["slot"]+1
                    and (not encoded & 192 or bool(encoded & 128))
                    and claim["targetMask"] & tb and claim["carrierMask"] & cb
                    and not claim["recoveringMask"] & (cb|tb)
                    and not (claim["targetMask"]|claim["carrierMask"]|claim["recoveringMask"]) & bit,
                    "scheduled receipt has no exact protected Cargo claim")
            require(d["hardProtectedMask"] & (cb|tb) == cb|tb
                    and value["farSamples"][carrier["handle"]["slot"]] == 0
                    and value["farSamples"][cargo["handle"]["slot"]] == 0
                    and not value["distanceDespawnPendingMask"] & (cb|tb),
                    "carrier or Cargo lost hard protection")
        require(not any(r["slot"] in (cargo["handle"]["slot"], carrier["handle"]["slot"]) for r in fresh),
                "carrier or Cargo received deletion telemetry")
        require(not d["hardProtectedMask"] & bit, "unrelated actor was protected by a Cargo claim")
        self.calls.append(deepcopy(event))
        if current is None:
            require(len(deletes) == 1 and prior is not None, "unrelated actor vanished without exact distance deletion")
            prior = self._actor(self.latest, "unrelated")
            require(isinstance(prior.get("engineObject"), dict), "deleted actor lacks its prior native pose")
            record = deletes[0]
            require(record["reason"] == 3 and record["action"] == 1 and record["contextFlags"] == 61
                    and record["objectPtr"] == prior["engineIdentity"]["pointer"]
                    and record["personality"] == prior["subjectIdentity"]
                    and record["mapId"] == record["spawnMapId"] == self.map_id
                    and record["mapGeneration"] == self.context["mapGeneration"]
                    and record["encounterGeneration"] == prior["handle"]["encounterGeneration"]
                    and record["objectId"] == record["expectedObjectId"] == 0xE0+slot
                    and [record["objectX"],record["objectY"]] == [prior["engineObject"][k] for k in ("x","y")]
                    and record["objectFlags"] & 1 and record["distance"] > 16
                    and max(abs(record["objectX"]-record["playerX"]), abs(record["objectY"]-record["playerY"])) == record["distance"]
                    and not d["movementDeferredMask"] & bit
                    and prior["motionPhase"] == "IDLE" and prior["reservationId"] == 0,
                    "distance deletion has wrong identity, distance or motion owner")
            count = before["farSamples"][slot]
            if count == 1:
                require(len(self.far) == 1, "distance sample history is incomplete")
                self.far.append(dict(frame=sample["frame"], sequence=d["sequence"],
                    distance=[abs(record["objectX"]-record["playerX"]), abs(record["objectY"]-record["playerY"])],
                    before=1, after=2, confirmedBy="exact distance DELETE_OBJECT receipt"))
            if self.deferred is None and self.motion.current is None:
                self.terminal = dict(frame=self.latest["frame"], actor=deepcopy(prior), motion=None)
            require(len(self.far) == 2 and count in (1,2) and self.terminal is not None
                    and self.terminal["frame"] < sample["frame"]
                    and (self.deferred is None or self.deferred["frame"] <= self.terminal["frame"]),
                    "distance deletion lacks two scheduled samples and a native idle terminal")
            require(after["farSamples"][slot] == 0 and not after["distanceDespawnPendingMask"] & bit,
                    "removed actor retained distance state")
            self.deleted = dict(frame=sample["frame"], handle=deepcopy(prior["handle"]), telemetry=deepcopy(record), receiptSequence=d["sequence"])
            return
        self._actor(sample, "unrelated")
        require(not deletes, "live actor contradicts its deletion telemetry")
        x,y = after["lastKnownX"][slot],after["lastKnownY"][slot]
        dx,dy = abs(x-sample["player"]["x"]),abs(y-sample["player"]["y"])
        if max(dx,dy) <= 16:
            require(after["farSamples"][slot] == 0 and not after["distanceDespawnPendingMask"] & bit,
                    "return in range retained far samples")
            require(not self.far, "unrelated actor returned in range before the declared two-sample window")
            return
        count = before["farSamples"][slot]
        if count == 0:
            pair = sample["pokemonCombat"]["interactions"]
            row = next(r for r in pair["carriers"] if r["handle"] == carrier["handle"])
            base = cargo["handle"]["slot"]+1
            require(self.claim_frame is not None and row["throw"]["targetRaw"] == base
                    and all(value["throwState"]["targets"][carrier["handle"]["slot"]] == base
                            for value in (before,after)), "first far sample lacks its free chase witness")
            self.free_chase = dict(frame=sample["frame"], carrier=deepcopy(carrier["handle"]),
                cargo=deepcopy(cargo["handle"]), bindings=deepcopy(row["bindings"]),
                native=deepcopy(pair["throwState"]))
        expected = min(count+1,2)
        require(after["farSamples"][slot] == expected
                and bool(after["distanceDespawnPendingMask"] & bit) == (expected==2),
                "scheduled far sample did not advance exactly once")
        if count < 2:
            require(count == len(self.far), "distance sample history is incomplete")
            self.far.append(dict(frame=sample["frame"], sequence=d["sequence"], distance=[dx,dy], before=count, after=expected))
        if d["movementDeferredMask"] & bit:
            require(prior is not None and prior["motionKind"] in ("WALK", "HOP", "REPOSITION")
                    and prior["motionPhase"] in ("PLANNED", "MOVING", "COMMIT_PENDING", "SETTLING")
                    and (prior["motionPhase"] not in ("PLANNED", "MOVING") or prior["reservationId"] != 0),
                    "deferred receipt lacks its accepted native motion")
            # Only the second far sample makes deletion pending. Earlier
            # completed travel cannot be the terminal of this accepted owner.
            if expected == 2 and self.deferred is None:
                if self.terminal is not None and self.terminal["frame"] < sample["frame"]:
                    self.terminal = None
                self.deferred = dict(frame=sample["frame"], handle=deepcopy(prior["handle"]),
                    origin=deepcopy(prior["origin"]), target=deepcopy(prior["target"]),
                    kind=prior["motionKind"], duration=prior["motionDuration"], reservationId=prior["reservationId"])

    def _sample(self, sample, events):
        self._boundary(sample)
        require(sample["context"] == self.context, "Field context changed during distance proof")
        observation = sample.get("nativeObservation", {})
        require(observation.get("coverageComplete") is True and observation.get("error") is None
                and observation.get("eventsDropped") == 0, "native distance observation is incomplete")
        valid_claim,cargo,carrier = self._claim(sample)
        if self.far and self.deleted is None:
            require(valid_claim, "Cargo claim ended before distance removal")
        unrelated = self._unrelated(sample)
        native = [e["data"] for e in events if e.get("kind") == "native"
                  and e.get("data", {}).get("actor") == {k:v for k,v in self.subjects["unrelated"]["handle"].items() if k!="value"}]
        require(not any(e.get("event") == "MOTION_CANCELED" for e in native), "accepted motion was cancelled to remove the actor")
        self.motion_events.extend(dict(e, gameFrame=sample["frame"]) for e in native)
        if unrelated is not None:
            self.motion_armed |= unrelated["motionPhase"] == "IDLE" or (
                unrelated["motionPhase"] == "MOVING" and unrelated["motionElapsed"] in (0,1))
            if self.motion_armed:
                self.motion.observe(sample["frame"], unrelated, unrelated["engineObject"])
                require(not self.motion.failures, "ordinary actor's native travel is incomplete")
            for motion in self.motion.completed:
                if motion["kind"] != "WALK" or motion["origin"] == motion["target"]:
                    continue
                if self.deferred is not None and (motion["origin"] != [self.deferred["origin"][k] for k in ("x","y")]
                        or motion["target"] != [self.deferred["target"][k] for k in ("x","y")]
                        or not motion["startFrame"] <= self.deferred["frame"] <= motion["finishFrame"]):
                    continue
                names = {e["event"] for e in self.motion_events if motion["startFrame"] <= e["gameFrame"] <= motion["finishFrame"]}
                require(complete_travel(motion) and {"INTENT_CREATED", "MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"} <= names,
                        "accepted motion lacks exact native commit and control return")
                self.terminal = dict(frame=motion["finishFrame"], motion=deepcopy(motion))
        rows = [e for e in events if e.get("kind") == "native-observation" and e.get("data", {}).get("observation") == "distance-maintenance"]
        require(len(rows) <= 1, "more than one scheduled distance call in one completed queue")
        for event in rows: self._receipt(sample,event,valid_claim,cargo,carrier)
        if unrelated is None:
            require(self.deleted is not None, "unrelated actor vanished without exact distance deletion")
        if self.deferred and self.terminal and not self.deleted and unrelated is not None:
            require(unrelated["motionPhase"] == "IDLE", "confirmed actor started follow-on movement before removal")
        self.latest = deepcopy(sample)
        self.observed_frames += 1
        require(self.observed_frames <= MAX_FRAMES, "bounded distance window exceeded")

    def observe_record(self, row, on_sample=None):
        try:
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase") == "setup", "initial boundary differs")
                self._boundary(row["initialSnapshot"],False); self.latest = deepcopy(row["initialSnapshot"])
                return self.result()
            if row.get("phase") == "setup":
                required = setup(self.kind)
                require(self.setup_index < len(required) and row.get("action") == required[self.setup_index][0], "setup order differs")
                action, command, args = required[self.setup_index]
                if command == "step":
                    require("command" not in row, "pre-claim Cargo Walk must use normal frames")
                    for sample, _, _ in validate_raw_chunk(row, self.latest):
                        self._boundary(sample); self._actor(sample,"cargo")
                        if action == "natural-cargo-claim": self._claim(sample)
                        self.latest = deepcopy(sample)
                        if on_sample: on_sample(sample,self.observed_frames)
                    if action == "natural-cargo-claim":
                        if self._claim(self.latest)[0]: self.setup_index += 1
                    elif self._actor(self.latest,"cargo")["motionKind"] == "WALK": self.setup_index += 1
                    return self.result()
                require(row.get("command") == command, "setup command differs")
                sample = row["snapshot"]; self._boundary(sample)
                if command == "terrain":
                    value = row["receipt"]["terrain"]; cells = value["cells"]
                    require(value["observation"]["context"] == sample["context"] and len(cells) == 1
                            and cells[0].get("x") == args["x"] and cells[0].get("y",cells[0].get("z")) == args["z"]
                            and cells[0].get("loaded") is True and cells[0].get("collision") is False
                            and cells[0].get("surface",{}).get("known") is True
                            and cells[0]["surface"].get("present") is False, "fixture lacks current loaded clear support")
                    if action in ("terrain-first-step", "terrain-second-step"):
                        follower = select_current_actor(sample,self.prepared["passive-follower"])
                        current = next(a for a in sample["actors"] if a["handle"] == follower["handle"])
                        require([current["engineObject"][k] for k in ("x","y")] != [args["x"],args["z"]],
                                "normal exit enters the passive follower tile")
                elif command == "party":
                    current = [p for p in sample.get("party",[]) if p.get("slot") == 0]
                    require(len(current) == 1 and current[0].get("identityVerified") is True
                            and current[0].get("species") == 155 and current[0].get("level") == 10
                            and current[0].get("isEgg") is False, "passive party preparation differs")
                elif action == "create-passive-follower":
                    current = [a for a in sample["actors"] if a.get("role") == "FOLLOWER" and a.get("species") == 155]
                    require(len(current) == 1, "passive current follower is missing")
                    follower = select_current_actor(sample,current[0])
                    party = next(p for p in sample["party"] if p["slot"] == 0)
                    require(follower["handle"]["slot"] == 7 and follower["subjectIdentity"] == party["personality"],
                            "passive follower is not the prepared party owner")
                    self.prepared["passive-follower"] = deepcopy(follower)
                elif command == "spawn":
                    require(action != "spawn-unrelated" or self._claim(sample)[0],
                            "unrelated actor spawned without the current Cargo claim")
                    from tools.overworld.devtools_test_contract import _wild_spawn_setup
                    value = _wild_spawn_setup(row["receipt"],sample,species=args["species"],locomotion=7)
                    require(value["destination"] == [args["x"],args["z"]], "native finalized position differs from fixture")
                    self.prepared[action[6:]] = value["subject"]
                elif command == "bind":
                    name = args["subject"]; subject = select_current_actor(sample,row["receipt"])
                    require((subject["species"],subject["role"]) == (dict(SUBJECTS)[name],"WILD")
                            and subject["handle"] == self.prepared[name]["handle"]
                            and subject["subjectIdentity"] == self.prepared[name]["subjectIdentity"], "bound native subject differs")
                    self.subjects[name] = deepcopy(row["receipt"])
                self.latest = deepcopy(sample); self.setup_index += 1
                if self.setup_index == len(required): self.context = deepcopy(sample["context"])
                return self.result()
            require(self.setup_index == len(setup(self.kind)) and row.get("phase") == "observe"
                    and "command" not in row, "observation order differs")
            ids = [a[0] for a in actions(self.kind)]
            require(row.get("action") in ids, "undeclared input after setup")
            idx = ids.index(row["action"])
            # A proved first far sample can make this neutral wait consume
            # zero frames, so it has no raw row between settle and request.
            completed_far_wait = (row["action"] == "request-second-sample"
                and self.action_index == ids.index("walk-first-tile-settle")
                and self.stage("first-far-sample"))
            require(self.action_index <= idx <= self.action_index+1 or completed_far_wait,
                    "normal input stages skip or reverse")
            if row["action"] == "request-second-sample" and self.action_index != idx:
                require(self.stage("first-far-sample"), "second request precedes the first scheduled far sample")
                require(self.latest["player"]["x"] == CASES[self.kind][2]
                        and self.latest["player"]["y"] == CASES[self.kind][3]+EXIT[self.kind]//2,
                        "second request does not start on its exact corridor tile")
            self.action_index = idx
            for sample,events,_ in validate_raw_chunk(row,self.latest):
                self._sample(sample,events)
                if on_sample: on_sample(sample,self.observed_frames)
        except (ValueError,KeyError,TypeError,StopIteration,struct.error) as error:
            self.failures.append(str(error))
        return self.result()

    def stage(self,name):
        require(name in ("claim-bound", "first-far-sample"), "unknown distance stage")
        if name == "claim-bound":
            return not self.failures and self.claim_frame is not None
        return (not self.failures and self.claim_frame is not None
                and len(self.far) == 1 and self.far[0]["before"] == 0
                and self.far[0]["after"] == 1 and self.deleted is None)

    def result(self):
        ready = not self.failures and self.free_chase is not None and self.deleted is not None and len(self.far)==2 and self.terminal is not None
        return dict(kind=self.kind, requirements=[requirement(self.kind)], ready=ready, passed=ready,
                    acceptedProof=False, observedFrames=self.observed_frames,
                    observedFrameUnit="completed-game-frame", subjects=deepcopy(self.subjects),
                    claimFrame=self.claim_frame, freeChaseWitness=deepcopy(self.free_chase), farSamples=deepcopy(self.far), deferredMotion=deepcopy(self.deferred),
                    terminal=deepcopy(self.terminal), deletion=deepcopy(self.deleted), calls=deepcopy(self.calls),
                    failures=list(self.failures))

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("Distance despawn: no claim-backed two-sample terminal deletion")
        return self.result()
