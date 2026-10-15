"""Measure normal Geodude pursuit while its eventual Throw target is walking.

The existing interaction reader proves the current Geodude claim and Player
Trigger while the same bound Cargo walks. Later pursuit and launch retain that
identity. Pickup requires a current accepted moving Cargo, then its exact
native CANCEL/CONTROL return and HELD claim in the next completed frame.
"""

from copy import deepcopy
from pathlib import Path
import struct

from scripts.overworld_behavior_profile_viewer import _stable_condition_id
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.devtools_moving_cargo_pickup import CargoAutonomy, checked_moving_pickup, pickup_motion
from tools.overworld.devtools_application_bank import canonical_bank, global_mask, local_application

from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import engine_binding_identity, select_current_actor
from tools.overworld.devtools_cargo_route_continuity import packets, same_graph, profile
from tools.overworld.devtools_profile_feature_measurement import application_index


KIND = "wild-throw-moving-candidate-v1"
REQUIREMENT = "current.wild-throw-moving-candidate"
SETUP = ("throw-tile", "prepare-passive-follower", "create-passive-follower",
         "spawn-stantler", "bind-stantler",
         "spawn-geodude", "bind-geodude", "walk-stantler-before-notice")
ORDER = ("natural-moving-pickup-and-launch",)
PRE_WALK_LIMIT = 300
LIMIT = 500
PLAYER_TILE = (585, 407)
GEODUDE_TILE = (583, 404)
THROW_APPLICATION = application_index("apply-throw")
_BANK = canonical_bank(Path(__file__).resolve().parents[2])
THROW_APPLICATION_LOCAL = local_application(_BANK, 74, THROW_APPLICATION)
THROW_APPLICATION_BIT = 1 << THROW_APPLICATION_LOCAL
THROW_POSITION_BIT = 1 << local_application(_BANK, 74, application_index("apply-throw-find-position"))
THROW_RELEASE_BIT = 1 << local_application(_BANK, 74, application_index("apply-throw-release"))
TRIGGER_CONDITION = _stable_condition_id("throw", "condition-throw-notices-player")
CARGO_CONDITION = _stable_condition_id("throw", "condition-throw-selects-cargo")
BUBBLE_SOUND_ID = 1501
BUBBLE_PLAY_CALLER = 0x02203C1E  # Sealed three-slot Initialize PlaySE return.
QUIET_BUBBLE_STOP_CALLER = 0x01FFF3C0


def require(value, message):
    if not value:
        raise ValueError(message)


def tile(actor, field):
    point = actor.get(field, {})
    return point.get("x"), point.get("y")


def verify_wander_spawn(receipt, snapshot):
    """Bind the authored input to Stantler's native entry and current actor."""
    value = receipt.get("value", {})
    require(value.get("species") == 234
            and type(value.get("slot")) is int
            and type(value.get("personality")) is int,
            "moving Throw Stantler command identity differs")
    events = [event.get("data", {}) for event in receipt.get("events", [])
              if event.get("kind") == "native-observation"
              and event.get("data", {}).get("observation") == "spawn-prepared"
              and event.get("data", {}).get("slot") == value["slot"]]
    require(len(events) == 1, "moving Throw Stantler native spawn is missing")
    spawn = events[0]
    pair = spawn.get("finalization", {})
    final = pair.get("receipt", {})
    require(pair.get("status") == "matched"
            and final.get("pairEligible") is True
            and spawn.get("returnValue") == final.get("returnValue") == 1
            and final.get("inputPosition") == [585, 403]
            and final.get("inputEncounter") == {
                "personality": value["personality"], "species": 234,
                "form": 0, "level": 5}
            and spawn.get("preparedEncounter") == final.get("preparedEncounter")
            and spawn.get("preparedEncounter") == final.get("inputEncounter")
            and spawn.get("position") == final.get("position")
            and spawn.get("startup") == final.get("startup")
            and spawn.get("worldContext") == final.get("worldContext")
            and final.get("returnWorldContext") == final.get("worldContext")
            and all(spawn.get(key) == final.get(key) for key in (
                "slot", "terrain", "statePointer", "fieldPointer",
                "preparedPointer", "preparedPrefixHex")),
            "moving Throw Stantler native finalization differs")
    world = final["worldContext"]
    require(all(world.get(key) == snapshot.get("context", {}).get(key)
                for key in ("mapId", "fieldEpoch", "mapGeneration")),
            "moving Throw Stantler world differs")
    position = final["position"]
    startup = final["startup"]
    require(isinstance(position, list) and len(position) == 2
            and all(type(n) is int for n in position)
            and startup.get("locomotion") == 7
            and startup.get("origin") == startup.get("target")
            and isinstance(startup.get("target"), list)
            and startup["target"] == position,
            "moving Throw Stantler entry differs")
    raw = bytes.fromhex(final["preparedPrefixHex"])
    require(len(raw) == 30
            and [int.from_bytes(raw[index:index + 4], "little", signed=True)
                 for index in (0, 4)] == position
            and int.from_bytes(raw[12:16], "little") == value["personality"]
            and int.from_bytes(raw[16:18], "little") == 234
            and raw[18:20] == bytes([0, 5])
            and [int.from_bytes(raw[index:index + 2], "little", signed=True)
                 for index in (20, 22)] == startup["target"]
            and [int.from_bytes(raw[index:index + 2], "little", signed=True)
                 for index in (24, 26)] == startup["origin"]
            and raw[28] == 7,
            "moving Throw Stantler raw prepared output differs")
    selected = select_current_actor(snapshot, spawn["publicSubject"])
    actor = next(actor for actor in snapshot["actors"]
                 if actor.get("handle") == selected["handle"])
    require(actor.get("species") == 234
            and actor.get("subjectIdentity") == value["personality"]
            and actor.get("handle", {}).get("slot") == value["slot"]
            and tile(actor, "logical") == tuple(position),
            "moving Throw Stantler public actor differs from native spawn")
    return {"subject": selected, "position": tuple(position)}


def retain_walk_graph(baseline, current):
    """Compatible permits only exact-Cargo ownership fixation, never its loss.

    Nearest-Cargo ranking may restart the graph on a target check; owner,
    static context, policy and storage must still stay current.

    Compare copies only; native receipts stay unchanged. All shared static,
    policy, storage and node checks still run over both entry and return.
    """
    same_receipt = all(baseline.get(k) == current.get(k) for k in
                       ("frame", "actorFrame", "sequence", "queryPointer", "workspace", "before"))
    allocated = same_receipt and baseline["before"] is None
    if allocated:
        receipt = current.get("allocation")
        require(receipt is not None, "moving Throw first graph lacks its zero-entry allocation")
        rows = packets(receipt["sample"], [receipt["event"]],
                       dict(handle=current["workspace"]["owner"], engineObject=receipt["origin"]), receipt["image"],
                       receipt["previousCycle"], pending_ok=True)
        entry = receipt["event"]["data"]["before"]
        require(len(rows) == 1 and entry.get("queryPointer") == 0
                and entry.get("workspace") is None
                and all(rows[0][k] == current[k] for k in rows[0]),
                "moving Throw allocation differs from its current native receipt")
    elif same_receipt:
        baseline = dict(baseline, workspace=baseline["before"])
    base = baseline["workspace"]["compatibility"]["required"]
    before = base if allocated else current["before"]["compatibility"]["required"]
    after = current["workspace"]["compatibility"]["required"]
    require(all(type(n) is int and n in (0, 1) for n in (base, before, after))
            and base <= before <= after, "moving Throw lost exact Cargo ownership")
    if base == 0 and after == 1:
        binding = current.get("cargoBinding")
        require(binding is not None and binding["frame"] == current["frame"]
                and binding["owner"] == current["workspace"]["owner"],
                "moving Throw ownership fixation lacks current Cargo binding")
        validate_route_binding(binding["binding"], "ACTOR", CARGO_CONDITION,
                               baseline["workspace"]["compatibility"]["cargo"])
    expected, observed = deepcopy(baseline), deepcopy(current)
    if allocated:
        observed["before"] = deepcopy(observed["workspace"])
    expected["workspace"]["compatibility"]["required"] = 1
    for stage in (observed["before"], observed["workspace"]):
        stage["compatibility"]["required"] = 1
    same_graph(expected, observed, allow_reset=True)


def validate_route_binding(binding, kind, condition, target=None):
    raw = bytes.fromhex(binding.get("rawHex", ""))
    require(len(raw) == 24 and raw[:12] == (raw_handle(target) if target else bytes(12))
            and raw[12:14] == bytes([2 if kind == "ACTOR" else 1, 0])
            and struct.unpack_from("<HIBBBB", raw, 14) == (condition, 0, THROW_APPLICATION_LOCAL, 0, 1, 0)
            and binding.get("bound") is True and binding.get("targetCurrent") is True
            and binding.get("flags") == 1 and binding.get("reason") == 0
            and binding.get("sourceConditionId") == condition
            and binding.get("sourceApplication") == THROW_APPLICATION
            and binding.get("sourceApplicationLocal") == THROW_APPLICATION_LOCAL
            and binding.get("expiresAt") == binding.get("lifetime") == 0
            and binding.get("target") == dict(kind=kind, actor=target),
            "moving Throw current " + kind + " route binding differs")


def moving_pickup_witness(previous, current, events, source, subjects):
    """Keep Wild binding guards before the shared native handoff check."""
    meter = WildThrowMovingCandidateMeasurement(source)
    meter.subjects = subjects
    meter._boundary(previous); meter._boundary(current)
    before = meter._actor(previous, "stantler"); after = meter._actor(current, "stantler")
    carrier_before = meter._actor(previous, "geodude"); carrier = meter._actor(current, "geodude")
    require(meter._claim(previous, carrier_before, before) is True,
            "moving pickup lacks its previous exact uncarried claim")
    meter._claim(current, carrier, after)
    return checked_moving_pickup(previous, current, events, source,
                                 before, after, carrier_before, carrier)


class WildThrowMovingCandidateMeasurement:
    def __init__(self, source):
        self.source = source
        self.latest = None
        self.subjects = {}
        self.passive_subject = None
        self.stantler_spawn_position = None
        self.pre_notice_walk_frame = None
        self.setup_index = 0
        self.observed_frames = 0
        self.moving_candidate_frame = None
        self.walk_pursuit_frame = None
        self.launch_frame = None
        self.pickup_witness = None
        self.quiet_bubble_pairs = []
        self.sound_sequence = -1
        self.failures = []
        self.route_latest = self.route_alert = self.route_witness = None
        self.route_profiles = {}
        self.autonomy = CargoAutonomy(source) if source["contractVersion"] == 2 else None

    def _profiles(self, events):
        for event in events:
            data = event.get("data", {})
            if event.get("kind") == "native-observation" and data.get("observation") == "behavior-resolved" \
                    and data.get("resolved") is True:
                self.route_profiles[data["fingerprint"]] = deepcopy(data)

    def _autonomy(self, sample, events):
        if self.autonomy is None or "stantler" not in self.subjects:
            return
        actor = self._actor(sample, "stantler")
        targets = sample.get("pokemonCombat", {}).get("interactions", {}).get("throwState", {}).get("targets", [])
        codes = [v for v in targets if v & 63 == actor["handle"]["slot"] + 1]
        self.autonomy.observe(sample, actor, events, self.route_profiles,
                              claimed=bool(codes), held=any(v & 128 for v in codes))

    def _boundary(self, snapshot, fixture=True):
        require(isinstance(snapshot, dict)
                and snapshot.get("observationBoundary") == "main-task-queue-completion"
                and snapshot.get("fieldAvailable") is True
                and type(snapshot.get("frame")) is int
                and type(snapshot.get("nativeCycle")) is int,
                "moving Throw needs a completed game boundary")
        require(isinstance(snapshot.get("context"), dict)
                and (not fixture or snapshot["context"].get("mapId") == 33)
                and isinstance(snapshot.get("player"), dict)
                and snapshot.get("fieldControl", {}).get("taskPointer") == 0,
                "moving Throw left normal Route 29 field control")
        if fixture:
            require((snapshot["player"].get("x"), snapshot["player"].get("y"))
                    == PLAYER_TILE, "player left the Throw fixture")
        if self.passive_subject is not None:
            self._passive(snapshot)
        if "romSha256" in snapshot:
            require(snapshot["romSha256"] == self.source["romSha256"],
                    "moving Throw ROM identity differs")

    def _actor(self, snapshot, subject):
        require(subject in self.subjects, "moving Throw subject was not bound")
        selected = select_current_actor(snapshot, self.subjects[subject])
        actor = next(actor for actor in snapshot["actors"]
                     if actor.get("handle") == selected["handle"])
        require(actor.get("active") is True
                and actor.get("presentationAttached") is True
                and actor.get("role") == "WILD"
                and actor.get("species") == (234 if subject == "stantler" else 74),
                "moving Throw actor is not the current visible Wild subject")
        return actor

    def _passive(self, snapshot):
        selected = select_current_actor(snapshot, self.passive_subject)
        actor = next(a for a in snapshot["actors"] if a["handle"] == selected["handle"])
        require(actor.get("species") == 155 and actor.get("level") == 20
                and actor.get("role") == "FOLLOWER" and actor.get("handle", {}).get("slot") == 7
                and actor.get("active") is True and actor.get("presentationAttached") is True
                and not set(global_mask(_BANK, 155, actor.get("matchedLayerMask", 0))) &
                    {application_index(n) for n in ("apply-throw", "apply-throw-find-position", "apply-throw-release")},
                "moving Throw passive follower changed or selected Throw")
        return actor

    def _claim(self, sample, geo, cargo):
        combat = sample.get("pokemonCombat", {}); value = combat.get("interactions", {})
        require(combat.get("available") is True and combat.get("frame") == sample["frame"]
                and combat.get("nativeCycle") == sample["nativeCycle"]
                and combat.get("identity", {}).get("romSha256") == self.source["romSha256"]
                and combat["identity"].get("overlaySha256") == self.source["overlaySha256"]
                and value.get("schemaVersion") == 1 and value.get("available") is True
                and value.get("frame") == sample["frame"] and value.get("nativeCycle") == sample["nativeCycle"]
                and value.get("observationBoundary") == "main-task-queue-completion"
                and value.get("fieldSystem") == sample["fieldControl"].get("fieldPointer")
                and value.get("identity", {}).get("romSha256") == self.source["romSha256"],
                "moving Throw claim is absent, stale or unauthenticated")
        rows = [r for r in value.get("carriers", []) if r.get("handle") == geo["handle"]]
        require(len(rows) == 1 and rows[0].get("available") is True and rows[0].get("role") == "WILD",
                "moving Throw claim has no current Geodude owner")
        row = rows[0]; raw = bytes.fromhex(row.get("rawBindingsHex", ""))
        require(len(raw) == 60 and raw[:12] == raw_handle(geo["handle"]),
                "moving Throw binding owner differs")
        state = value["throwState"]; native = bytes.fromhex(state["rawHex"])
        require(len(native) == 16 and list(native[:10]) == state["targets"]
                and struct.unpack_from("<3H", native, 10) ==
                    (state["targetMask"], state["carrierMask"], state["recoveringMask"])
                and not (state["targetMask"] | state["carrierMask"] | state["recoveringMask"]) & ~0x3FF,
                "moving Throw raw claim masks differ")
        encoded = native[geo["handle"]["slot"]]
        expect = dict(targetRaw=encoded, targetSlot=((encoded&63)-1 if encoded else None),
            carried=bool(encoded&128), windup=bool(encoded&64),
            targeted=bool(state["targetMask"]&(1 << geo["handle"]["slot"])),
            carrier=bool(state["carrierMask"]&(1 << geo["handle"]["slot"])),
            recovering=bool(state["recoveringMask"]&(1 << geo["handle"]["slot"])))
        require(row.get("throw") == expect, "moving Throw decoded claim differs")
        if not encoded or (encoded&63) != cargo["handle"]["slot"] + 1:
            return False
        for key, start, kind, condition in (("trigger", 12, "PLAYER", TRIGGER_CONDITION),
                                            ("cargo", 36, "ACTOR", CARGO_CONDITION)):
            bound = row["bindings"][key]; data = raw[start:start+24]
            require(data.hex() == bound.get("rawHex") and data[12:14] == bytes([1 if kind == "PLAYER" else 2,0])
                    and struct.unpack_from("<HIBBBB", data, 14) ==
                        (bound["sourceConditionId"],bound["expiresAt"],bound["sourceApplicationLocal"],
                         bound["lifetime"],bound["flags"],bound["reason"])
                    and bound["bound"] is True and bound["flags"] == 1 and bound["targetCurrent"] is True
                    and bound["sourceConditionId"] == condition and bound["sourceApplication"] == THROW_APPLICATION
                    and bound["sourceApplicationLocal"] == THROW_APPLICATION_LOCAL
                    and bound["expiresAt"] == 0 and bound["lifetime"] == 0 and bound["reason"] == 0
                    and bound["target"] == dict(kind=kind, actor=None if kind == "PLAYER" else cargo["handle"])
                    and data[:12] == (bytes(12) if kind == "PLAYER" else raw_handle(cargo["handle"])),
                    "moving Throw current " + key + " binding differs")
        require(state["targetMask"] & (1 << cargo["handle"]["slot"])
                and state["carrierMask"] & (1 << geo["handle"]["slot"])
                and not state["recoveringMask"] & (1 << geo["handle"]["slot"]),
                "moving Throw lacks its exact native Cargo claim")
        return not encoded & 192

    def _bubble_sounds(self, sample, events):
        # Native call clocks can precede the final zero-queue cycle. Both
        # synchronous calls must still belong to this one completed frame.
        pending = None
        for event in events:
            data = event.get("data", {})
            kind = data.get("observation")
            if event.get("kind") != "native-observation" or kind not in ("sound-play", "sound-stop"):
                continue
            stock_play = kind == "sound-play" and data.get("caller") == BUBBLE_PLAY_CALLER
            quiet_stop = kind == "sound-stop" and data.get("caller") == QUIET_BUBBLE_STOP_CALLER
            if not stock_play and not quiet_stop:
                continue
            require(event.get("frame") == sample["frame"]
                    and type(sample.get("actorFrame")) is int
                    and all(type(data.get(key)) is int for key in (
                        "sequence", "entryActorFrame", "returnActorFrame",
                        "entryNativeCycle", "returnNativeCycle"))
                    and data["entryActorFrame"] == data["returnActorFrame"] == sample["actorFrame"]
                    and self.latest["nativeCycle"] < data["entryNativeCycle"]
                    <= data["returnNativeCycle"] <= sample["nativeCycle"]
                    and data["sequence"] > self.sound_sequence
                    and data.get("sequenceId") == BUBBLE_SOUND_ID,
                    "moving Throw bubble sound has a wrong ID, clock or order")
            self.sound_sequence = data["sequence"]
            if stock_play:
                require(pending is None, "moving Throw bubble sound lacks its synchronous quiet stop")
                pending = data
            else:
                if pending is None:
                    # Stock ov01_02203A48 returns before its initializer when
                    # the bubble effect is already active. ShowQuiet still
                    # calls StopSE. Authenticate that call above, but award no
                    # sound-pair credit and keep the real pair requirement.
                    require(self.quiet_bubble_pairs,
                            "moving Throw bubble sound lacks its synchronous quiet stop")
                    continue
                require(pending["returnNativeCycle"] <= data["entryNativeCycle"]
                        and data["entryActorFrame"] == pending["entryActorFrame"],
                        "moving Throw bubble sound lacks its synchronous quiet stop")
                self.quiet_bubble_pairs.append({
                    "frame": sample["frame"], "actorFrame": data["entryActorFrame"],
                    "nativeCycle": data["entryNativeCycle"],
                    "previousNativeCycle": self.latest["nativeCycle"],
                    "completedNativeCycle": sample["nativeCycle"],
                    "playEntryNativeCycle": pending["entryNativeCycle"],
                    "playReturnNativeCycle": pending["returnNativeCycle"],
                    "stopEntryNativeCycle": data["entryNativeCycle"],
                    "stopReturnNativeCycle": data["returnNativeCycle"],
                    "playSequence": pending["sequence"], "stopSequence": data["sequence"],
                    "sequenceId": BUBBLE_SOUND_ID, "playCaller": BUBBLE_PLAY_CALLER,
                    "stopCaller": QUIET_BUBBLE_STOP_CALLER})
                pending = None
        require(pending is None, "moving Throw bubble sound lacks its synchronous quiet stop")

    def _route_binding(self, sample, actor, key, kind, condition, target=None):
        # Reuse the existing atomic interaction/owner/raw-mask validation.
        self._claim(sample, actor, self._actor(sample, "stantler"))
        row = next(r for r in sample["pokemonCombat"]["interactions"]["carriers"]
                   if r["handle"] == actor["handle"])
        binding = row["bindings"][key]
        if not binding.get("bound"):
            return None
        raw = bytes.fromhex(row["rawBindingsHex"])
        offset = 12 if key == "trigger" else 36
        require(raw[offset:offset+24].hex() == binding["rawHex"],
                "moving Throw raw route binding differs")
        validate_route_binding(binding, kind, condition, target)
        return dict(frame=sample["frame"], owner=deepcopy(actor["handle"]), binding=deepcopy(binding))

    def _route_walk(self, sample, events, actor, alert, current):
        frame = sample["frame"]
        walk = alert.get("walk")
        own = [e for e in events if e.get("kind") == "native"
               and e.get("data", {}).get("actorHandle") == actor["handle"]["value"]
               and e["data"].get("event") in ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")]
        if walk is None:
            if actor.get("motionKind") != "WALK" or actor.get("motionPhase") != "MOVING" \
                    or actor.get("motionElapsed") != 0:
                return
            starts = [e for e in own if e["data"]["event"] == "MOTION_STARTED"]
            require(len(starts) == 1 and starts[0]["data"].get("valueA") == 1
                    and starts[0]["data"].get("valueB") == actor["motionDuration"] == 8
                    and alert["reachableFrame"] is not None
                    and 0 <= frame-alert["reachableFrame"] <= 1 and alert["baseline"] is not None,
                    "moving Throw did not admit a native Walk after its current reachable route")
            require(sum(abs(a-b) for a,b in zip(tile(actor,"origin"),tile(actor,"target"))) == 1,
                    "moving Throw first Walk is not one native tile")
            walk = dict(startFrame=frame, returnFrame=frame+8, duration=8,
                commitBefore=actor["commitSequence"], commitAfter=actor["commitSequence"]+1,
                handle=deepcopy(actor["handle"]), subjectIdentity=actor["subjectIdentity"],
                origin=list(tile(actor,"origin")), target=list(tile(actor,"target")),
                nativeStart=deepcopy(starts[0]), lifecycle=[], samples=[], queries=[])
            alert["walk"] = walk
        require(current, "moving Throw lacks a current route read during Walk or return")
        for row in current:
            retain_walk_graph(alert["baseline"], row)
            walk["queries"].append(deepcopy(row))
        elapsed = frame-walk["startFrame"]
        require(0 <= elapsed <= 8, "moving Throw first Walk return was delayed")
        for event in own:
            data = event["data"]
            require(event["frame"] == frame and data.get("actorFrame") == sample["actorFrame"]
                    and data.get("actor") == {k:v for k,v in actor["handle"].items() if k != "value"},
                    "moving Throw Walk lifecycle owner or clock differs")
            if data["event"] == "MOTION_STARTED" and elapsed:
                continue  # A new accepted Walk may start after this one's return.
            walk["lifecycle"].append(deepcopy(event))
        pose = [actor["engineObject"]["pos_x"],actor["engineObject"]["pos_z"]]
        if elapsed < 8:
            require(actor.get("motionKind") == "WALK" and actor.get("motionPhase") == "MOVING"
                    and actor.get("motionElapsed") == elapsed and actor.get("motionDuration") == 8
                    and list(tile(actor,"origin")) == walk["origin"]
                    and list(tile(actor,"target")) == walk["target"]
                    and actor["commitSequence"] == walk["commitBefore"],
                    "moving Throw first accepted Walk changed before completion")
        else:
            require(actor["commitSequence"] >= walk["commitAfter"]
                    and list(tile(actor,"logical")) == walk["target"]
                    and pose == [(n<<16)+32768 for n in walk["target"]],
                    "moving Throw first Walk lacks its exact native landing")
        walk["samples"].append(dict(frame=frame,elapsed=elapsed,pose=pose))
        if elapsed == 8:
            expected=[("MOTION_STARTED",1,8),("LOGICAL_COMMIT",walk["commitAfter"],1),
                      ("MOTION_FINISHED",walk["commitAfter"],1),("CONTROL_RETURNED",0,walk["commitAfter"])]
            require([(e["data"]["event"],e["data"]["valueA"],e["data"]["valueB"])
                     for e in walk["lifecycle"]] == expected
                    and all(a["data"]["sequence"] < b["data"]["sequence"]
                            for a,b in zip(walk["lifecycle"],walk["lifecycle"][1:])),
                    "moving Throw first Walk lacks exact native commit and control return")
            self.route_witness = dict(**deepcopy(alert), searchStartFrame=walk["startFrame"],
                                      nativeStart=deepcopy(walk["nativeStart"]))

    def _route_sample(self, sample, events, actor):
        if self.source["contractVersion"] != 2 or self.route_witness is not None:
            return
        for event in events:
            data = event.get("data", {})
            if event.get("kind") == "native-observation" and data.get("observation") == "behavior-resolved" \
                    and data.get("resolved") is True:
                self.route_profiles[data["fingerprint"]] = deepcopy(data)
        # The current initial Notice is allowed to precede graph allocation.
        # Pending still authenticates its complete native owner/clock/budget.
        previous_cycle = self.latest["nativeCycle"] if self.latest else None
        current = packets(sample, events, actor, self.source["queryImage"], previous_cycle, pending_ok=True)
        native = [e for e in events if e.get("kind") == "native-observation"
                  and e.get("data",{}).get("observation") == "throw-cargo-query"
                  and e["data"].get("slot") == actor["handle"]["slot"]]
        timers = [r for r in sample["pokemonCombat"].get("movementTimers", []) if r.get("handle") == actor["handle"]]
        require(len(timers) == 1, "moving Throw lacks current carrier alert/cooldown clocks")
        timer = timers[0]
        cargo = bool(actor["matchedLayerMask"] & THROW_APPLICATION_BIT)
        if self.route_alert is None and cargo and timer["movementEmoteTimer"]:
            resolved = self.route_profiles.get(actor["behaviorFingerprint"])
            lane = profile(resolved, actor, self.source)
            require(lane[3] == timer["movementEmoteTimer"] == 20 and lane[7] == 8 and lane[36] == 2,
                    "moving Throw Cargo alert or authored half-speed profile differs")
            baseline = current[-1] if current else self.route_latest
            prepared = baseline is not None and baseline["workspace"]["compatibility"]["required"] == 1 \
                and baseline["workspace"]["nodeCount"] >= 2
            initial = None
            if not prepared:
                empty = [e for e in native if e["data"]["before"].get("queryPointer") == 0
                         and e["data"]["after"].get("queryPointer") == 0
                         and e["data"]["before"].get("workspace") is None
                         and e["data"]["after"].get("workspace") is None]
                require(len(empty) == 1 and baseline is None,
                        "moving Throw lacks its exact initial unprepared Notice query")
                notice = self._route_binding(sample,actor,"trigger","PLAYER",TRIGGER_CONDITION)
                require(notice is not None and empty[0]["data"]["sequence"] < resolved["sequence"]
                        and resolved["entryActorFrame"] == resolved["returnActorFrame"] == sample["actorFrame"]
                        and previous_cycle < resolved["entryNativeCycle"] <= resolved["returnNativeCycle"] <= sample["nativeCycle"],
                        "moving Throw initial Pending did not capture Player and Search at Notice")
                initial = dict(sample={k:sample[k] for k in ("frame","actorFrame","nativeCycle")},
                    previousCycle=previous_cycle,event=deepcopy(empty[0]),notice=notice)
                baseline = None
            self.route_alert = dict(mode="prepared" if prepared else "initial-pending",
                startFrame=sample["frame"], endFrame=sample["frame"]+20,
                profile=deepcopy(resolved), initialPending=initial, alertClocks=[],
                queryImage=deepcopy(self.source["queryImage"]),
                baseline=deepcopy(baseline), postAlert=None, reachableFrame=None, resumedFrame=None, routeReceipts=[])
        alert = self.route_alert
        if alert is not None:
            frame = sample["frame"]
            require(frame >= alert["startFrame"], "moving Throw alert clock reversed")
            if frame <= alert["endFrame"]:
                expected=max(0,alert["endFrame"]-frame)
                require(timer["movementEmoteTimer"] == expected,
                        "moving Throw changed its authored Cargo alert clock")
                alert["alertClocks"].append(dict(frame=frame,timer=expected))
            if frame >= alert["endFrame"]:
                if alert["resumedFrame"] is None:
                    require(frame <= alert["endFrame"]+1 and native and timer["movementEmoteTimer"] == 0,
                            "moving Throw route work did not resume at its authored alert end")
                    alert["resumedFrame"] = frame
                for row in current:
                    require(row["workspace"]["compatibility"]["cargo"] == self.subjects["stantler"]["handle"],
                            "moving Throw route names a different Cargo")
                    row["cargoBinding"] = self._route_binding(sample,actor,"cargo","ACTOR",CARGO_CONDITION,
                        self.subjects["stantler"]["handle"]) if alert["mode"]=="initial-pending" else None
                    if alert["baseline"] is None:
                        if row["before"] is None:
                            event = next(e for e in native if e["data"]["sequence"] == row["sequence"])
                            row["allocation"] = dict(event=deepcopy(event),
                                sample={k:sample[k] for k in ("frame","actorFrame","nativeCycle")},
                                previousCycle=previous_cycle, image=deepcopy(self.source["queryImage"]),
                                origin={k:actor["engineObject"][k] for k in ("x","y")})
                        alert["baseline"] = deepcopy(row)
                    retain_walk_graph(alert["baseline"],row)
                    if alert["routeReceipts"]:
                        retain_walk_graph(alert["routeReceipts"][-1],row)
                    alert["routeReceipts"].append(deepcopy(row))
                    if alert["postAlert"] is None:
                        alert["postAlert"] = deepcopy(row)
                    if row["status"] == "REACHABLE" and row["hasNextStep"] and alert["reachableFrame"] is None:
                        alert["reachableFrame"] = frame
                self._route_walk(sample,events,actor,alert,current)
        if current:
            self.route_latest = deepcopy(current[-1])

    def _sample(self, sample, events=()):
        self._boundary(sample)
        source = self._actor(sample, "geodude")
        target = self._actor(sample, "stantler")
        self._profiles(events)
        self._autonomy(sample, events)
        self._route_sample(sample, events, source)
        self.observed_frames += 1
        require(self.observed_frames <= LIMIT, "moving Throw exceeded its frame limit")
        throw_active = bool(source.get("matchedLayerMask", 0)
                            & THROW_APPLICATION_BIT)
        claimed = self._claim(sample, source, target) if throw_active else False
        if (self.moving_candidate_frame is None
                and throw_active
                and claimed
                and target.get("motionKind") == "WALK"
                and target.get("motionPhase") == "MOVING"
                and type(target.get("motionElapsed")) is int
                and type(target.get("motionDuration")) is int
                and 0 < target["motionElapsed"] < target["motionDuration"]):
            self.moving_candidate_frame = sample["frame"]
        if (self.walk_pursuit_frame is None
                and self.moving_candidate_frame is not None
                and throw_active
                and source.get("motionKind") == "WALK"
                and source.get("motionPhase") == "MOVING"
                and sum(abs(a - b) for a, b in zip(
                    tile(source, "target"), tile(target, "logical")))
                    < sum(abs(a - b) for a, b in zip(
                        tile(source, "origin"), tile(target, "logical")))):
            self.walk_pursuit_frame = sample["frame"]
        relation = sample.get("pokemonCombat", {}).get("interactions", {}).get("throwState", {}).get("targets", [])
        if (self.pickup_witness is None and len(relation) == 10
                and relation[source["handle"]["slot"]] & 128):
            self.pickup_witness = moving_pickup_witness(self.latest, sample, events, self.source, self.subjects)
        if (target.get("motionKind") == "HOP"
                and source.get("matchedLayerMask", 0) & THROW_RELEASE_BIT):
            require(self.launch_frame is None
                    and self.moving_candidate_frame is not None
                    and self.walk_pursuit_frame is not None
                    and self.moving_candidate_frame <= self.walk_pursuit_frame
                    and self.walk_pursuit_frame < sample["frame"]
                    and self.pickup_witness is not None
                    and self.pickup_witness["frame"] < sample["frame"]
                    and source.get("matchedLayerMask", 0) & THROW_RELEASE_BIT
                    and target.get("motionPhase") == "MOVING"
                    and tile(target, "origin") == tile(source, "logical")
                    and tile(target, "target") == PLAYER_TILE
                    and type(target.get("motionDuration")) is int
                    and target["motionDuration"] > 1,
                    "Stantler was not launched after moving Throw selection and pursuit")
            self.launch_frame = sample["frame"]
        self.latest = deepcopy(sample)

    def observe_record(self, row, on_sample=None):
        try:
            require(isinstance(row, dict), "moving Throw proof row is missing")
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase") == "setup",
                        "moving Throw initial boundary is misplaced")
                self._boundary(row["initialSnapshot"], fixture=False)
                self._profiles(row.get("initialEvents", []))
                self.latest = deepcopy(row["initialSnapshot"])
                return self.result()
            require(self.latest is not None, "moving Throw initial boundary is missing")
            if row.get("phase") == "setup":
                require(self.setup_index < len(SETUP)
                        and row.get("action") == SETUP[self.setup_index],
                        "moving Throw setup differs")
                if row["action"] == "walk-stantler-before-notice":
                    require("command" not in row,
                            "pre-Notice Stantler Walk must use normal frames")
                    samples = validate_raw_chunk(row, self.latest)
                    require(1 <= len(samples) <= PRE_WALK_LIMIT,
                            "pre-Notice Stantler Walk exceeded its frame limit")
                    for sample, events, _ in samples:
                        self._boundary(sample)
                        self._profiles(events)
                        self._autonomy(sample, events)
                        self._bubble_sounds(sample, events)
                        self._actor(sample, "stantler")
                        self.latest = deepcopy(sample)
                        if on_sample is not None:
                            on_sample(sample, self.observed_frames)
                    target = self._actor(self.latest, "stantler")
                    if (target.get("motionKind") == "WALK"
                            and target.get("motionPhase") == "MOVING"
                            and type(target.get("motionDuration")) is int
                            and target["motionDuration"] > 1):
                        self.pre_notice_walk_frame = self.latest["frame"]
                        self.setup_index += 1
                    return self.result()
                require(row.get("command") ==
                        ("teleport", "party", "spawn", "spawn", "bind", "spawn", "bind", "step")
                        [self.setup_index], "moving Throw setup command differs")
                snapshot = row["snapshot"]
                self._boundary(snapshot)
                self._profiles(row.get("events", []) + row.get("receipt", {}).get("events", []))
                require(snapshot["frame"] >= self.latest["frame"],
                        "moving Throw setup clock reversed")
                if row["command"] == "party":
                    members = [m for m in snapshot.get("party", []) if m.get("slot") == 0]
                    require(len(members) == 1 and members[0].get("identityVerified") is True
                            and members[0].get("species") == 155 and members[0].get("level") == 20
                            and members[0].get("isEgg") is False,
                            "moving Throw passive party preparation differs")
                if row["action"] == "create-passive-follower":
                    receipt = row["receipt"]; requested = receipt.get("requestedSubject", {})
                    require(receipt.get("lifecycle") == "prepared-native-follower-lifecycle"
                            and all(requested.get(k) == v for k,v in
                                    dict(slot=0,role="FOLLOWER",species=155,form=0,level=20).items())
                            and type(requested.get("personality")) is int,
                            "moving Throw passive native follower receipt differs")
                    members = [m for m in snapshot.get("party", []) if m.get("slot") == 0]
                    actors = [a for a in snapshot["actors"] if a.get("role") == "FOLLOWER"
                              and a.get("active") is True]
                    require(len(actors) == len(members) == 1 and members[0].get("identityVerified") is True
                            and members[0].get("species") == 155 and members[0].get("level") == 20
                            and members[0].get("isEgg") is False
                            and members[0].get("personality") == actors[0].get("subjectIdentity") == requested["personality"],
                            "moving Throw passive follower is not the prepared party owner")
                    self.passive_subject = select_current_actor(snapshot, actors[0]); self._passive(snapshot)
                elif row["command"] == "spawn":
                    value = row.get("receipt", {}).get("value", {})
                    require(value.get("species") == (234 if row["action"] == "spawn-stantler" else 74)
                            and type(value.get("slot")) is int
                            and type(value.get("personality")) is int,
                            "moving Throw native spawn identity differs")
                    if row["action"] == "spawn-stantler":
                        self.stantler_spawn_position = verify_wander_spawn(
                            row["receipt"], snapshot)["position"]
                if row["command"] == "bind":
                    subject = "stantler" if row["action"] == "bind-stantler" else "geodude"
                    self.subjects[subject] = deepcopy(row["receipt"])
                    actor = self._actor(snapshot, subject)
                    require(tile(actor, "logical") == self.stantler_spawn_position
                            if subject == "stantler" else
                            tile(actor, "logical") == GEODUDE_TILE,
                            "moving Throw subject left its prepared native spawn")
                self._autonomy(snapshot, row.get("events", []))
                self.latest = deepcopy(snapshot)
                self.setup_index += 1
                return self.result()
            require(self.setup_index == len(SETUP)
                    and row.get("phase") == "observe"
                    and row.get("action") == ORDER[0]
                    and "command" not in row
                    and self.launch_frame is None,
                    "moving Throw action differs")
            for sample, events, _ in validate_raw_chunk(row, self.latest):
                require(self.launch_frame is None,
                        "moving Throw step ran past its first launch frame")
                self._bubble_sounds(sample, events)
                self._sample(sample, events)
                if on_sample is not None:
                    on_sample(sample, self.observed_frames)
        except (KeyError, TypeError, ValueError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def result(self):
        ready = (not self.failures and self.setup_index == len(SETUP)
                 and self.pre_notice_walk_frame is not None
                 and self.moving_candidate_frame is not None
                 and self.walk_pursuit_frame is not None
                 and self.launch_frame is not None
                 and self.pickup_witness is not None
                 and bool(self.quiet_bubble_pairs)
                 and (self.autonomy is None or self.autonomy.result()["ready"])
                 and (self.source["contractVersion"] == 1 or self.route_witness is not None))
        return {"ready": ready, "observedFrames": self.observed_frames,
                "observedFrameUnit": "completed-game-frame",
                "preNoticeWalkFrame": self.pre_notice_walk_frame,
                "movingCandidateFrame": self.moving_candidate_frame,
                "walkPursuitFrame": self.walk_pursuit_frame,
                "launchFrame": self.launch_frame,
                "movingPickup": deepcopy(self.pickup_witness),
                "cargoAutonomy": self.autonomy.result() if self.autonomy is not None else None,
                "quietBubbleSoundPairs": deepcopy(self.quiet_bubble_pairs),
                "subjects": deepcopy(self.subjects),
                "routeContinuity": deepcopy(self.route_witness),
                "failures": list(self.failures)}

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("moving Throw ended without walking pursuit, moving pickup, launch and quiet bubble sound proof")
        return {"passed": self.result()["ready"], "failures": list(self.failures)}
