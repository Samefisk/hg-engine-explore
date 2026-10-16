"""Two bounded retained-surface witnesses; no emulator or guest writes.

The existing terrain reader supplies the expected absolute catalog height.
The existing prepared receipt binds the real Fly In target, not the requested
spawn coordinate. Restoration credit comes only from completed native poses.
"""
from copy import deepcopy

from tools.overworld.devtools_movement_predicates import player_settled_at
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import HANDLE_FIELDS, select_current_actor
from tools.overworld.devtools_wild_transition_measurement import same_actor_lifetime
from tools.overworld.spawn_identity import live_spawn_flags

ROOF = "wild-roof-rebind-height-v1"
SIGN = "wild-signpost-rebind-height-v1"
CONFIG = {
    ROOF: dict(id="world.transition.wild-roof-height", subject="hoothoot", species=163,
               oldMap=67, newMap=33, surfaceType="rooftop", surfaceId=9303,
               terrainArgs={"x": 568, "z": 404, "radius": 2}, recovery=[576, 400],
               requirement="current.retained-roof-height"),
    SIGN: dict(id="world.transition.wild-signpost-height", subject="pidgey", species=16,
               oldMap=33, newMap=67, surfaceType="signpost", surfaceId=9313,
               terrainArgs={"x": 581, "z": 397, "radius": 0}, recovery=[575, 400],
               requirement="current.retained-signpost-height"),
}


def need(value, reason):
    if not value:
        raise ValueError("retained surface: " + reason)


def next_generation(value):
    return (value + 1) & 0xFFFF or 1


class WildSurfaceRebindMeasurement:
    def __init__(self, test, *, max_frames):
        self.kind = test["measurements"][0]["kind"]
        need(self.kind in CONFIG, "unknown witness")
        self.config = CONFIG[self.kind]
        c = self.config
        need(test.get("id") == c["id"] and test.get("mode") == "prepared"
             and test.get("fixture") == {"rom": "test.nds", "save": "test.sav"}
             and test.get("subjects") == [{"id": c["subject"], "species": c["species"],
                                          "role": "WILD", "acquire": "spawn"}],
             "fixture or exact subject differs")
        need(type(max_frames) is int and 1 <= max_frames <= 840, "frame bound differs")
        self.max_frames = max_frames
        self.actions = {(phase, a["id"]): a for phase, name in
                        (("setup", "setup"), ("observe", "actions")) for a in test[name]}
        self.latest = self.initial = self.terminal = self.subject = None
        self.initial_subject = self.spawn = self.surface = None
        self.events = []
        self.frames = self.ground_frames = 0
        self.changed = self.settled = self.closed = False
        self.change_frame = self.sign_commit_frame = None
        self.failures = []

    def _actor(self, snapshot):
        candidates = [a for a in snapshot.get("actors", []) if a.get("active") is True
                      and a.get("subjectIdentity") == self.initial_subject["subjectIdentity"]
                      and same_actor_lifetime(a.get("handle", {}), self.initial_subject["handle"])]
        need(len(candidates) == 1, "same actor lifetime is missing or duplicated")
        actor = candidates[0]
        selected = select_current_actor(snapshot, actor)
        c, source, engine = self.config, actor["sourceIdentity"], actor["engineIdentity"]
        need(actor["role"] == "WILD" and actor["species"] == c["species"]
             and live_spawn_flags(source["active"])
             and source["personality"] == actor["subjectIdentity"] and source["species"] == c["species"]
             and source["object"] == engine["pointer"] and source["map_id"] == snapshot["context"]["mapId"]
             and engine["active"] is True and engine["in_manager"] is True
             and engine["object_map_id"] == engine["current_map_id"] == snapshot["context"]["mapId"]
             and engine["script_id"] == 2074, "native binding differs")
        old = self.initial["actors"] if self.initial else []
        if old:
            prior = next(a for a in old if a["handle"] == self.initial_subject["handle"])["engineIdentity"]
            need(all(engine[k] == prior[k] for k in ("pointer", "current_manager", "object_id")),
                 "retained native object or manager changed")
        self.subject = deepcopy(selected)
        return actor

    def arm(self, snapshot, selected):
        need(self.initial is None and self.spawn is not None, "binding lacks its native spawn receipt")
        self.initial_subject = select_current_actor(snapshot, selected)
        actor = self._actor(snapshot)
        p, startup = self.spawn["publicSubject"], self.spawn["startup"]
        need(p["handle"] == actor["handle"] and p["subjectIdentity"] == actor["subjectIdentity"]
             and startup["locomotion"] == 9 and startup["target"] == [actor["target"][k] for k in ("x", "y")]
             and startup["origin"] == [actor["origin"][k] for k in ("x", "y")]
             and actor["motionKind"] == "FLY_IN" and actor["motionPhase"] == "MOVING"
             and actor["motionDuration"] == 144 and 0 <= actor["motionElapsed"] < 144
             and snapshot["context"]["mapId"] == self.config["oldMap"]
             and all(self.spawn["worldContext"][k] == snapshot["context"][k]
                     for k in ("mapId", "fieldEpoch", "mapGeneration")),
             "real Fly In admission differs")
        self.initial = deepcopy(snapshot)
        self.latest = deepcopy(snapshot)

    def capture_surface(self, terrain, snapshot):
        actor = self._actor(snapshot)
        observation = terrain["observation"]
        target = [actor["target"][k] for k in ("x", "y")]
        need(observation["context"] == snapshot["context"]
             and observation["lastCompletedGameFrame"] == snapshot["frame"]
             and observation["nativeCycle"] == snapshot["nativeCycle"], "terrain read clock/context differs")
        cells = [cell for cell in terrain["cells"] if [cell["x"], cell["z"]] == target]
        need(len(cells) == 1 and cells[0]["loaded"] is True, "actual Fly In target is not loaded")
        cell, c = cells[0], self.config
        surface = cell["surface"]
        need(surface["known"] is True and surface["present"] is True
             and surface["finalHeightKnown"] is True and surface["heightMode"] == "absolute"
             and surface["type"] == c["surfaceType"] and surface["surfaceId"] == c["surfaceId"]
             and type(surface["heightFx32"]) is int
             and surface["heightFx32"] == self.spawn["startup"]["targetBaseY"]
             and cell["provenance"]["fieldPointer"] == snapshot["fieldControl"]["fieldPointer"],
             "actual target lacks its authenticated absolute surface height")
        need(self.surface is None, "duplicate target surface read")
        self.surface = deepcopy(cell)

    def _ground(self, actor, *, canceled_fly_in=False):
        target = self.spawn["startup"]["target"]
        pose = actor["engineObject"]
        need([pose["x"], pose["y"]] == target
             and [pose["pos_x"], pose["pos_z"]] == [(n << 16) + 0x8000 for n in target]
             and pose["pos_y"] == self.surface["surface"]["heightFx32"]
             and pose["unk88_y"] == 0 and pose["unk94_y"] == 0,
             "native target ground height/pose differs")
        need((actor["motionKind"] == "NONE" and actor["motionPhase"] in ("IDLE", "CANCELED")
              or canceled_fly_in and actor["motionKind"] == "FLY_IN"
                 and actor["motionPhase"] == "CANCELED")
             and actor["reservationId"] == 0, "retained actor has active motion")

    def observe(self, snapshot, events):
        if self.failures or self.closed:
            return self.result()
        try:
            need(self.initial is not None and self.surface is not None, "target-height admission is missing")
            need(snapshot["frame"] == self.latest["frame"] + 1
                 and snapshot["observationBoundary"] == "main-task-queue-completion"
                 and snapshot["nativeCycle"] >= self.latest["nativeCycle"], "completed queue clock gap")
            native = snapshot["nativeObservation"]
            need(native["installedBeforeBoot"] is True and native["coverageComplete"] is True
                 and native["error"] is None and native["eventsDropped"] == native["profilesEvicted"] == 0,
                 "native observation coverage is incomplete")
            actor = self._actor(snapshot)
            for event in events:
                if event.get("kind") != "native":
                    continue
                d = event["data"]
                if d.get("actorHandle") != self.initial_subject["handle"]["value"]:
                    continue
                handle = {"value": d["actorHandle"], **d["actor"]}
                need(set(handle) == set(HANDLE_FIELDS)
                     and same_actor_lifetime(handle, self.initial_subject["handle"]), "event actor lifetime differs")
                if d["event"] in ("MOTION_CANCELED", "CONTEXT_CHANGED", "ACTOR_REBOUND"):
                    need(event["frame"] == snapshot["frame"], "transition event frame differs")
                    expected = actor["handle"] if d["event"] == "ACTOR_REBOUND" else self.initial_subject["handle"]
                    need(handle == expected, "transition trace uses a stale field handle")
                    self.events.append(deepcopy(event))
            context = snapshot["context"]
            old = self.initial["context"]
            if context != old:
                expected = dict(mapId=self.config["newMap"], fieldEpoch=next_generation(old["fieldEpoch"]),
                                mapGeneration=next_generation(old["mapGeneration"]))
                need(context == expected, "owner context did not advance exactly once")
                if not self.changed:
                    prior = self._actor(self.latest)
                    if self.kind == ROOF:
                        need(prior["motionKind"] == "FLY_IN" and prior["motionPhase"] == "MOVING"
                             and prior["motionElapsed"] < prior["motionDuration"], "map change missed active Fly In")
                    else:
                        need(self.settled, "signpost changed map before settling")
                    self.changed = True
                    self.change_frame = snapshot["frame"]
                    # _actor(latest) resolves the previous full context; bind
                    # the current one again before returning this sample.
                    actor = self._actor(snapshot)
                canceled_fly_in = self.kind == ROOF and self.ground_frames == 0
                if canceled_fly_in and actor["motionKind"] == "FLY_IN":
                    # Cancel publishes phase immediately; the next Actor tick
                    # clears the old public kind. The role already grounds the
                    # native body before that first completed queue returns.
                    need(actor["origin"] == prior["origin"] and actor["target"] == prior["target"]
                         and actor["motionElapsed"] == prior["motionElapsed"]
                         and actor["motionDuration"] == prior["motionDuration"] == 144
                         and actor["inputOwnership"] == 0
                         and any(e["frame"] == snapshot["frame"]
                                 and e["data"]["event"] == "MOTION_CANCELED"
                                 and e["data"]["reason"] == "CONTEXT_LOST"
                                 and e["data"]["valueA"] == 6 for e in self.events),
                         "first canceled Fly In lacks its unchanged native plan/trace")
                self._ground(actor, canceled_fly_in=canceled_fly_in)
                self.ground_frames += 1
                need(self.ground_frames == 1 or actor["logical"] == actor["target"],
                     "public target did not settle on the next completed queue")
                self.terminal = deepcopy(snapshot)
            elif self.kind == SIGN and actor["motionKind"] == "NONE" and actor["motionPhase"] == "IDLE":
                self._ground(actor)
                if actor["logical"] == actor["target"]:
                    self.settled = True
                else:
                    # Fly In ACK commits after the role's view was filled. Its
                    # public logical tile is copied from native xCurr/yCurr on
                    # the next queue; retain exactly that one commit boundary.
                    initial_actor = next(a for a in self.initial["actors"]
                                         if a["handle"] == self.initial_subject["handle"])
                    terminal_events = [e for e in events if e.get("kind") == "native"
                                 and e["data"].get("actorHandle") == actor["handle"]["value"]
                                 and e["data"].get("event") in
                                     ("LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")]
                    terminals = [e["data"] for e in terminal_events]
                    seq = actor["commitSequence"]
                    need(self.sign_commit_frame is None
                         and actor["logical"] == actor["origin"]
                         and [actor["origin"][k] for k in ("x", "y")] == self.spawn["startup"]["origin"]
                         and actor["motionElapsed"] == actor["motionDuration"] == 144
                         and seq == initial_actor["commitSequence"] + 1
                         and all(e["frame"] == snapshot["frame"]
                                 and {"value": e["data"]["actorHandle"], **e["data"]["actor"]}
                                     == actor["handle"] for e in terminal_events)
                         and [(e["event"], e["reason"], e["valueA"], e["valueB"]) for e in terminals]
                             == [("LOGICAL_COMMIT", "OK", seq, 6),
                                 ("MOTION_FINISHED", "OK", seq, 6),
                                 ("CONTROL_RETURNED", "OK", 0, seq)],
                         "signpost never committed its own target")
                    self.sign_commit_frame = snapshot["frame"]
            if self.sign_commit_frame is not None and snapshot["frame"] > self.sign_commit_frame:
                need(self.settled, "signpost public target did not settle on the next completed queue")
            self.frames += 1
            need(self.frames <= self.max_frames, "completed frame bound exceeded")
            self.latest = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def observe_record(self, record, *, frame_callback=None, full_report=True):
        try:
            if "initialSnapshot" in record:
                need(self.latest is None, "duplicate initial snapshot")
                self.latest = deepcopy(record["initialSnapshot"])
            else:
                action = self.actions[(record["phase"], record["action"])]
                command = record.get("command")
                if command is not None:
                    need(record["phase"] == "setup" and action["op"] == command,
                         "unexpected setup command")
                    snapshot, receipt = record["snapshot"], record["receipt"]
                    if command == "spawn":
                        found = [e["data"] for e in receipt["events"] if e.get("kind") == "native-observation"
                                 and e.get("data", {}).get("observation") == "spawn-prepared"
                                 and e["data"].get("preparedEncounter", {}).get("species") == self.config["species"]]
                        need(len(found) == 1 and found[0]["returnValue"] == 1
                             and found[0]["setupMode"] == "prepared", "native spawn receipt differs")
                        self.spawn = deepcopy(found[0])
                    elif command == "bind":
                        self.arm(snapshot, receipt)
                    elif command == "terrain":
                        need(action["args"] == self.config["terrainArgs"], "terrain box differs")
                        self.capture_surface(receipt["terrain"], snapshot)
                    else:
                        need(command == "teleport" and self.initial is None, "setup command after binding")
                    self.latest = deepcopy(snapshot)
                else:
                    need(action["op"] in ("step", "wait"), "unsupported observation action")
                    for snapshot, events, _ in validate_raw_chunk(record, self.latest):
                        if self.initial is None:
                            self.latest = deepcopy(snapshot)
                        else:
                            self.observe(snapshot, events)
                        if self.failures:
                            break
                        if frame_callback:
                            frame_callback(snapshot, events, self)
            return self.result()
        except (ValueError, KeyError, TypeError, IndexError) as error:
            self.failures.append(str(error))
            return self.result()

    def stage(self, name):
        need(name == "settled-on-signpost", "unknown stage")
        return self.kind == SIGN and self.settled and not self.failures

    @property
    def ready(self):
        names = [e["data"]["event"] for e in self.events]
        canceled = [e for e in self.events if e["data"]["event"] == "MOTION_CANCELED"]
        context = [e for e in self.events if e["data"]["event"] == "CONTEXT_CHANGED"]
        rebound = [e for e in self.events if e["data"]["event"] == "ACTOR_REBOUND"]
        expected = (["MOTION_CANCELED"] if self.kind == ROOF else []) + ["CONTEXT_CHANGED", "ACTOR_REBOUND"]
        trace_ok = (names == expected
                    and all(e["frame"] == self.change_frame for e in self.events)
                    and all(e["data"]["reason"] == "CONTEXT_LOST" for e in canceled + context)
                    and [context[0]["data"][k] for k in ("valueA", "valueB")]
                        == [self.initial["context"]["fieldEpoch"],
                            next_generation(self.initial["context"]["fieldEpoch"])]
                    and rebound[0]["data"]["reason"] == "OK"
                    and [rebound[0]["data"][k] for k in ("valueA", "valueB")]
                        == [self.config["oldMap"], self.config["newMap"]])
        return bool(not self.failures and self.changed and self.ground_frames >= 4 and trace_ok
                    and player_settled_at(self.latest, self.config["newMap"], *self.config["recovery"]))

    def finish(self):
        if not self.ready and not self.failures:
            self.failures.append("retained surface: height, transition trace or recovery witness is incomplete")
        self.closed = True
        return self.result()

    def result(self):
        return dict(kind=self.kind, requirements=[self.config["requirement"]], acceptedProof=False,
                    passed=self.closed and self.ready, ready=self.ready, closed=self.closed,
                    observedFrames=self.frames, failures=deepcopy(self.failures), subject=deepcopy(self.subject),
                    initialSubject=deepcopy(self.initial_subject), initial=deepcopy(self.initial),
                    terminal=deepcopy(self.terminal), spawn=deepcopy(self.spawn), surface=deepcopy(self.surface),
                    transitionEvents=deepcopy(self.events), groundFrames=self.ground_frames,
                    scope="one same-manager retained absolute surface; no spawn or stream pacing claim")
