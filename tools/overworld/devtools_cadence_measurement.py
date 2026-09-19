"""Pure, bounded replay of the unmounted long-route contract.

Input is the shared job's existing JSONL records plus its sealed typed recipe;
this module owns no input, emulator, filesystem, private reads, or proof grant.
Field-absent setup frames need an explicit bounded doorway contract, a live
departure task and exact settled arrival. They never earn route credit.
Only an authenticated stock object-only collision can suspend unadmitted input
timing for a bounded stationary wait. Unknown or terrain-blocked requests fail;
no blocked frame earns travel credit.

Expected limits: world.unmounted.long-travel-cadence; runtime_cadence's existing
2000/250000ns CPU classifier and 2/2/4 player timing. A retained actor handoff
requires stock-public CONTEXT_CHANGED(old) then ACTOR_REBOUND(new), a completed
old motion or proven cancellation, and the generation relationship in
overworld_actor_transition_model. Cancellation needs a later successful motion
on the rebound handle before route acceptance. Normal setup proves Center/A
healing of the same saved PID and later fresh native HP confirmation; prepared
setup is a separate explicit mode whose setup span earns no route credit.
"""
from collections import deque
from copy import deepcopy

from tools.overworld.devtools_records import HANDLE_FIELDS, select_current_actor, validate_field_absence
from tools.overworld.devtools_movement_predicates import player_settled_at
from tools.overworld.normal_play_observer import MotionRecorder, live_identity
from tools.overworld.runtime_cadence import classify_frame_hitches, classify_player_motion, guest_queue_delay
from tools.overworld.devtools_crash_measurement import CrashPresentationMeasurement
from tools.overworld.devtools_player_collision_wait import PlayerCollisionWait


MIN_ACTIVE = 5000
MIN_TILES, MIN_CELLS, MIN_MAPS, MIN_FOLLOWER_MOTIONS = 80, 3, 2, 16
FRAME_BOUNDARY = "main-task-queue-completion"
DIRECTIONS = {"UP": (0, -1), "DOWN": (0, 1), "LEFT": (-1, 0), "RIGHT": (1, 0)}
KEY_BITS = {"A": 1, "B": 2, "SELECT": 4, "START": 8, "RIGHT": 16,
            "LEFT": 32, "UP": 64, "DOWN": 128, "R": 256, "L": 512, "X": 1024, "Y": 2048}


def _integer(value, name, low=0, high=0xFFFFFFFF):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(name + " is missing or outside its integer bound")
    return value


def _handle(value):
    if not isinstance(value, dict) or set(value) != set(HANDLE_FIELDS):
        raise ValueError("full actor handle missing")
    return tuple(value[key] for key in HANDLE_FIELDS)


def _pose(player):
    return [_integer(player[key], "player." + key, -0x80000000, 0x7FFFFFFF)
            for key in ("pos_x", "pos_z")]


def _tile(player):
    return [_integer(player[key], "player." + key, 0, 32767) for key in ("x", "y")]


def _center(tile):
    return [coordinate * 0x10000 + 0x8000 for coordinate in tile]


class UnmountedCadenceMeasurement:
    """Feed initialSnapshot, bind, and raw shared step chunks in file order."""
    def __init__(self, test, *, max_frames, setup_transitions=(), diagnostic_continue_host_hitches=False,
                 accept_host_cpu_hitches=False):
        if type(diagnostic_continue_host_hitches) is not bool:
            raise ValueError("diagnostic_continue_host_hitches must be boolean")
        if type(accept_host_cpu_hitches) is not bool:
            raise ValueError("accept_host_cpu_hitches must be boolean")
        if accept_host_cpu_hitches and not diagnostic_continue_host_hitches:
            raise ValueError("host CPU acceptance requires retained host diagnostics")
        self.diagnostic_continue_host_hitches = diagnostic_continue_host_hitches
        self.accept_host_cpu_hitches = accept_host_cpu_hitches
        self.host_cpu_first = self.host_cpu_worst = None
        self.diagnostic_route_complete = False
        self.max_frames = _integer(max_frames, "max_frames", 1, 65535)
        self.mode = test.get("mode")
        if self.mode not in ("normal", "prepared") or test.get("fixture", {}).get("save") != "test.sav":
            raise ValueError("cadence requires the unchanged declared normal test.sav fixture")
        specs = [item for item in test.get("subjects", [])
                 if item.get("species") == 155 and item.get("role") == "FOLLOWER"]
        if len(specs) != 1:
            raise ValueError("cadence needs exactly one declared FOLLOWER Cyndaquil")
        self.subject_id = specs[0]["id"]
        self.actions = {}
        for phase, name in (("setup", "setup"), ("observe", "actions")):
            for action in test.get(name, []):
                key = (phase, action["id"])
                if key in self.actions or action["op"] not in ("step", "wait", "assert", "bind", "party", "spawn"):
                    raise ValueError("cadence accepts only distinct normal input/read-only actions")
                if action["op"] in ("party", "spawn"):
                    args = action["args"]
                    if self.mode != "prepared" or phase != "setup":
                        raise ValueError("prepared commands are restricted to declared setup")
                    if action["op"] == "party" and (set(args) - {"slot", "hp", "status"} or args.get("slot") != 1
                            or not {"hp", "status"}.intersection(args)):
                        raise ValueError("cadence party setup may change only saved slot1 HP/status")
                    if action["op"] == "spawn" and (set(args) - {"slot", "species", "role", "form", "level"}
                            or args.get("slot") != 1 or args.get("species") != 155 or args.get("role", "").upper() != "FOLLOWER"
                            or args.get("form", 0) != 0 or args.get("level", 5) != 5):
                        raise ValueError("cadence spawn setup requires the saved slot1 FOLLOWER Cyndaquil")
                keys = action["args"].get("keys", [])
                if not isinstance(keys, list) or len(keys) != len(set(keys)) or any(k not in KEY_BITS for k in keys) \
                        or "SELECT" in keys:
                    raise ValueError("invalid normal input or forbidden mount button")
                self.actions[key] = deepcopy(action)
        self.setup_transitions = {}
        for spec in setup_transitions:
            if not isinstance(spec, dict) or set(spec) - {"action", "departure", "arrival", "maxFrames", "reveal", "automaticSteps"} \
                    or not {"action", "departure", "arrival", "maxFrames"} <= set(spec):
                raise ValueError("setup transition requires an exact doorway contract")
            action = self.actions.get(("setup", spec["action"]))
            if action is None or action["op"] not in ("step", "wait") or spec["action"] in self.setup_transitions:
                raise ValueError("setup transition must name one distinct input/wait action")
            for endpoint in ("departure", "arrival"):
                point = spec[endpoint]
                if not isinstance(point, dict) or set(point) != {"map", "x", "z"}:
                    raise ValueError("setup transition endpoint needs map/x/z")
                _integer(point["map"], endpoint + " map", 0, 539)
                for axis in ("x", "z"): _integer(point[axis], endpoint + axis, 0, 32767)
            if spec["departure"]["map"] == spec["arrival"]["map"]:
                raise ValueError("setup transition must change map")
            automatic = spec.get("automaticSteps", [])
            if not isinstance(automatic, list) or len(automatic) > 2 \
                    or any(type(step) is not str or step not in ("entry-up", "exit-down") for step in automatic) \
                    or len(set(automatic)) != len(automatic) \
                    or automatic and action["op"] != "wait" \
                    or "exit-down" in automatic and "reveal" not in spec:
                raise ValueError("automatic doorway steps require exact neutral stock entry/exit contracts")
            if "reveal" in spec:
                reveal, arrival = spec["reveal"], spec["arrival"]
                if not isinstance(reveal, dict) or set(reveal) != {"map", "x", "z"} \
                        or any(type(v) is not int for v in reveal.values()) \
                        or reveal != {"map": arrival["map"], "x": arrival["x"], "z": arrival["z"] - 1}:
                    raise ValueError("setup reveal must be the exact stock one-tile DOWN arrival")
            _integer(spec["maxFrames"], "setup transition frame bound", 1, 600)
            self.setup_transitions[spec["action"]] = deepcopy(spec)
        self.pending_transition = None
        self.completed_setup_transitions = []
        self.absent_setup_frames = 0
        self.closed = False
        self.failures, self.gaps = [], []
        self.latest = self.saved_mon = self.subject = self.actor = None
        self.first_hashes = None
        self.frames = self.observed_frames = self.native_cycles = self.active_frames = 0
        self.native_sequence = self.player_step_count = 0
        self.trace_sequences = {}
        self.cpu, self.route_cpu = [], []
        self.hitches = classify_frame_hitches([], 2000, 250000)
        self.last_cpu_check = 0
        self.follower_trace = deque(maxlen=256)
        self.recorder = MotionRecorder()
        self.crash_presentation = CrashPresentationMeasurement(max_frames=self.max_frames)
        self.follower_motions = self.player_motions = 0
        self.last_follower_terminal = None
        self.step = None
        self.last_action = None
        self.last_keys = []
        self.tiles, self.cells, self.maps = set(), set(), set()
        self.held_tiles = self.held_cells = self.held_maps = 0
        self.held_run = 0
        self.last_motion_keys = None
        self.handoffs, self.motion_tail = [], deque(maxlen=16)
        self.setup = {"initialEligible": False, "centerInteraction": None,
                      "healingObserved": None, "healed": None,
                      "exitedCenter": None, "menuOpened": None, "highlighted": None,
                      "confirmed": None, "bound": None}
        self.initial_getters = set()
        self.released_since_motion = True
        self.initial_frame = None
        self.player_pointer = None
        self.player_collision_wait = PlayerCollisionWait()
        self.player_collisions = []
        self.prepared_commands = []
        self.prepared_seen = False

    def _fail(self, code, detail=None, *, gap=False, frame=None):
        if not self.failures:
            observed_frame = frame if frame is not None else (None if self.latest is None else self.latest["frame"])
            self.failures.append({"code": code, "frame": observed_frame,
                                  "detail": deepcopy(detail)})
        if gap and code not in self.gaps:
            self.gaps.append(code)

    def _party(self, snapshot):
        party, proof = snapshot.get("party"), snapshot.get("partyObservation", {})
        if not isinstance(party, list) or not 2 <= len(party) <= 6 \
                or proof.get("frame") != snapshot["frame"] or proof.get("boundary") != FRAME_BOUNDARY:
            raise ValueError("current coherent saved party observation missing")
        if any(mon.get("slot") != index for index, mon in enumerate(party)):
            raise ValueError("party slot layout differs")
        mon = party[1]
        if mon.get("identityVerified") is not True or mon.get("species") != 155 or mon.get("isEgg") is not False:
            raise ValueError("saved party1 is not a verified non-egg Cyndaquil")
        for key in ("personality", "level", "maxHp"):
            _integer(mon.get(key), "party1." + key, 1)
        _integer(mon.get("hp"), "party1.hp", 0, mon["maxHp"])
        _integer(mon.get("status"), "party1.status")
        if self.saved_mon and any(mon.get(key) != self.saved_mon.get(key)
                                  for key in ("personality", "species", "form", "level", "maxHp")):
            raise ValueError("saved party1 subject changed")
        return mon, proof.get("nativeGetterChecks", [])

    def _snapshot(self, snapshot, *, initial=False, command_boundary=False):
        if not isinstance(snapshot, dict) or snapshot.get("observationBoundary") != FRAME_BOUNDARY \
                or type(snapshot.get("prepared")) is not bool or type(snapshot.get("fieldAvailable")) is not bool \
                or self.mode == "normal" and snapshot["prepared"] \
                or self.prepared_seen and not snapshot["prepared"]:
            raise ValueError("missing coherent normal field snapshot")
        if snapshot["prepared"] and not self.prepared_seen and not (initial or command_boundary):
            raise ValueError("prepared state appeared without a retained setup command")
        frame = _integer(snapshot.get("frame"), "completed frame")
        if self.latest and not command_boundary and frame != self.latest["frame"] + 1:
            raise ValueError("completed field frame missing, duplicated, or reordered; no transition exemption")
        hashes = tuple(snapshot.get(key) for key in ("romSha256", "sourceSaveSha256"))
        if any(not isinstance(value, str) or len(value) != 64 for value in hashes) \
                or self.first_hashes and hashes != self.first_hashes:
            raise ValueError("ROM/save identity missing or changed")
        self.first_hashes = hashes
        if snapshot.get("fieldAvailable") is not False and (not isinstance(snapshot.get("actors"), list) or len(snapshot["actors"]) > 10 \
                or any(a.get("active") is True and a.get("role") == "MOUNTED" for a in snapshot["actors"])):
            raise ValueError("unmounted subject condition failed")
        observation = snapshot.get("nativeObservation", {})
        if observation.get("installedBeforeBoot") is not True or observation.get("coverageComplete") is not True \
                or any(observation.get(key) not in (0, None) for key in ("eventsDropped", "profilesEvicted", "error")) \
                or observation.get("pendingUnframedEvents") != 0 or observation.get("pendingPlayerSteps") != 0 \
                or observation.get("playerStepFrame") != frame:
            raise ValueError("native observation coverage missing or incoherent")
        if initial:
            self.prepared_seen = snapshot["prepared"]
            self.initial_frame = frame
            self.native_sequence = _integer(observation.get("sequence"), "native sequence")
            self.player_step_count = _integer(observation.get("playerStepCount"), "player step count")
        elif observation.get("sequence") != self.native_sequence or observation.get("playerStepCount") != self.player_step_count:
            raise ValueError("native receipt or admitted player step missing")
        if snapshot.get("fieldAvailable") is False:
            if initial:
                raise ValueError("initial field is absent")
            validate_field_absence(snapshot)
            if snapshot["observationErrors"]:
                raise ValueError("field absence observer errors")
            return None, []
        mon, getters = self._party(snapshot)
        if initial:
            self.saved_mon = deepcopy(mon)
            self.setup["initialEligible"] = mon["hp"] > 0 and mon["status"] == 0
            self.initial_getters = {(g.get("slot"), g.get("field"), g.get("native"), g.get("decoded")) for g in getters}
        _pose(snapshot["player"])
        _tile(snapshot["player"])
        _integer(snapshot.get("nativeCycle"), "native cycle")
        _integer(snapshot.get("context", {}).get("mapId"), "current map", 0, 539)
        return mon, getters

    def _setup_transition(self, snapshot, phase, action, admissions):
        absent = snapshot.get("fieldAvailable") is False
        pending = self.pending_transition
        spec = self.setup_transitions.get(action["id"]) if phase == "setup" else None
        if not absent and pending is None and spec is None:
            return
        if spec is None or self.subject is not None:
            raise ValueError("field absence is outside an authored unbound setup transition")
        automatic = None
        if admissions:
            automatic = UnmountedCadenceMeasurement._automatic_setup_step(self, snapshot, spec, admissions)
        def at(row, point):
            return row.get("fieldAvailable") is True and row.get("context", {}).get("mapId") == point["map"] \
                and _tile(row["player"]) == [point["x"], point["z"]]
        def live_task(row):
            task = row.get("fieldControl", {}).get("taskPointer")
            return type(task) is int and 0x02000000 <= task <= 0x023FFFFF and task % 4 == 0
        if pending is None:
            if any(item["action"] == action["id"] for item in self.completed_setup_transitions):
                if not absent and at(snapshot, spec["arrival"]):
                    return
                raise ValueError("completed setup transition repeated or left its arrival")
            departure = spec["departure"]
            previous = next((row for row in (self.latest, snapshot) if at(row, departure) and live_task(row)), None)
            if previous is None:
                if not absent and snapshot.get("context", {}).get("mapId") == departure["map"]:
                    return  # Stock automatic doorway step has not reached its exact departure yet.
                raise ValueError("setup transition lacks the exact live doorway departure task")
            pending = {"action": action["id"], "departureFrame": previous["frame"],
                       "departureTask": previous["fieldControl"]["taskPointer"],
                       "absentFrames": 0, "unreadyPlayerFrames": 0, "spec": deepcopy(spec)}
            self.pending_transition = pending
        if pending["action"] != action["id"] or snapshot["frame"] - pending["departureFrame"] > spec["maxFrames"]:
            raise ValueError("setup transition changed action or exceeded its frame bound")
        if automatic is not None:
            completed = pending.setdefault("automaticSteps", [])
            if any(row["kind"] == automatic["kind"] for row in completed):
                raise ValueError("automatic doorway step repeated")
            completed.append(automatic)
        if absent:
            pending["absentFrames"] += 1
            self.absent_setup_frames += 1
            return
        arrival = spec["arrival"]
        if at(snapshot, spec["departure"]) and live_task(snapshot):
            return  # The same bounded doorway task may wait with a live field.
        player = snapshot.get("player", {})
        empty_fields = ("flags", "x", "y", "x_prev", "y_prev", "pos_x", "pos_y", "pos_z",
                        "unk88_y", "movement_cmd", "movement_step", "facing")
        if live_task(snapshot) and snapshot.get("context", {}).get("mapId") in (
                spec["departure"]["map"], arrival["map"]) \
                and all(type(player.get(key)) is int and player[key] == 0 for key in empty_fields):
            pending["unreadyPlayerFrames"] += 1
            return  # Retain the exact zero-object native row, never arrival/control credit.
        reveal = spec.get("reveal")
        if reveal is not None and snapshot["context"]["mapId"] == reveal["map"] \
                and _tile(snapshot["player"]) == [reveal["x"], reveal["z"]]:
            return  # Stock doorway reveal, before its automatic STEP_DOWN.
        if snapshot["context"]["mapId"] != arrival["map"] or _tile(snapshot["player"]) != [arrival["x"], arrival["z"]]:
            raise ValueError("setup transition returned at the wrong map or tile")
        if player_settled_at(snapshot, arrival["map"], arrival["x"], arrival["z"]):
            if sorted(row["kind"] for row in pending.get("automaticSteps", [])) != sorted(spec.get("automaticSteps", [])):
                raise ValueError("authored automatic doorway step receipt missing")
            self.completed_setup_transitions.append({**pending, "arrivalFrame": snapshot["frame"]})
            self.pending_transition = None

    def _automatic_setup_step(self, snapshot, spec, admissions):
        """Only the authored stock held STEP_UP/STEP_DOWN, never free input."""
        if len(admissions) != 1 or snapshot.get("fieldAvailable") is not True \
                or self.latest.get("fieldAvailable") is not True:
            raise ValueError("automatic doorway step has missing field or multiple admissions")
        receipt = admissions[0]
        before, after = receipt.get("objectBefore", {}), receipt.get("objectAfter", {})
        _integer(receipt.get("direction"), "automatic doorway direction", 0, 1)
        _integer(before.get("pos_y"), "automatic doorway height", -0x80000000, 0x7FFFFFFF)
        for key in ("movement_cmd", "movement_step", "facing"):
            _integer(before.get(key), "automatic doorway " + key, 0, 255)
        current, previous = snapshot.get("fieldControl", {}), self.latest.get("fieldControl", {})
        task = _integer(current.get("taskPointer"), "automatic doorway task", 0x02000000, 0x023FFFFC)
        pointer = _integer(receipt.get("objectPointer"), "automatic doorway player", 0x02000000, 0x023FFF00)
        if task & 3 or pointer & 3 or receipt.get("returnValue") != pointer \
                or any(current.get(key) != previous.get(key) for key in ("fieldPointer", "taskPointer")) \
                or type(current.get("fieldPointer")) is not int \
                or not 0x02000000 <= current["fieldPointer"] <= 0x023FFF90 or current["fieldPointer"] & 3:
            raise ValueError("automatic doorway step lacks same live field/task/player ownership")
        for kind in spec.get("automaticSteps", []):
            point = spec["departure"] if kind == "entry-up" else spec["arrival"]
            direction = 0 if kind == "entry-up" else 1
            target = [point["x"], point["z"]]
            origin = [point["x"], point["z"] + (1 if direction == 0 else -1)]
            if receipt.get("direction") == direction and receipt.get("origin") == origin \
                    and receipt.get("target") == target:
                break
        else:
            raise ValueError("player admission is not an authored automatic doorway step")
        expected_after = deepcopy(before)
        expected_after.update(x=target[0], y=target[1])
        actor_frame = _integer(snapshot.get("actorFrame"), "automatic doorway actor clock")
        native_cycle = _integer(snapshot.get("nativeCycle"), "automatic doorway native clock")
        if receipt.get("mapId") != point["map"] \
                or any(row.get("context", {}).get("mapId") != point["map"] for row in (self.latest, snapshot)) \
                or _tile(self.latest["player"]) != origin or _tile(snapshot["player"]) != target \
                or _tile(before) != origin or _pose(before) != _center(origin) \
                or [before.get("x_prev"), before.get("y_prev")] != origin \
                or after != expected_after or before.get("movement_cmd") != 12 + direction \
                or before.get("movement_step") != 0 or before.get("facing") != direction \
                or any(type(receipt.get(key)) is not int or receipt[key] != actor_frame
                       for key in ("entryActorFrame", "returnActorFrame")) \
                or any(type(receipt.get(key)) is not int or receipt[key] != native_cycle
                       for key in ("entryNativeCycle", "returnNativeCycle")):
            raise ValueError("automatic doorway native receipt differs from exact step/clock/pose")
        player = snapshot["player"]
        start, end, pose = _center(origin), _center(target), _pose(player)
        if any(not min(a,b) <= p <= max(a,b) for a,b,p in zip(start,end,pose)) \
                or player.get("pos_y") != before.get("pos_y") \
                or [player.get("x_prev"),player.get("y_prev")] != origin \
                or player.get("facing") != direction or player.get("movement_cmd") != 12 + direction:
            raise ValueError("automatic doorway completed pose differs from the same native step")
        return {"kind":kind,"frame":snapshot["frame"],"taskPointer":task,"receipt":deepcopy(receipt)}

    def _setup_frame(self, snapshot, keys, mon, getters):
        selector = snapshot.get("selector", {})
        map_id = snapshot["context"]["mapId"]
        # Fresh completed-frame gSystem edges, not a requested button alone.
        new = _integer(selector.get("newKeys"), "selector newKeys")
        if map_id == 69 and "A" in keys and new & KEY_BITS["A"]:
            self.setup["centerInteraction"] = {"frame": snapshot["frame"], "map": map_id,
                "tile": _tile(snapshot["player"]), "facing": snapshot["player"].get("facing")}
        if not self.setup["initialEligible"] and not self.setup["healed"] and mon["hp"] == mon["maxHp"] and mon["status"] == 0:
            if self.setup["healingObserved"] is None:
                if map_id != 69 or not self.setup["centerInteraction"]:
                    self._fail("normal-center-healing-provenance-gap", gap=True)
                    return
                # The nurse writes HP without calling the observed getter.
                # Retain that Center observation; a later normal selector read
                # may supply the separate, fresh native confirmation outdoors.
                self.setup["healingObserved"] = {"frame": snapshot["frame"], "map": map_id,
                    "personality": mon["personality"], "hp": mon["hp"], "maxHp": mon["maxHp"],
                    "interaction": deepcopy(self.setup["centerInteraction"])}
            healed_frame = self.setup["healingObserved"]["frame"]
            matching = [g for g in getters if g.get("slot") == 1 and g.get("field") == "hp"
                and g.get("passed") is True and g.get("native") == g.get("decoded") == mon["maxHp"]
                and type(g.get("native")) is int and type(g.get("decoded")) is int
                and g.get("boundary") == "natural-GetMonData-return"
                and g.get("personality") == mon["personality"] and g.get("species") == 155
                and type(g.get("frame")) is int and healed_frame <= g["frame"] <= snapshot["frame"]
                and type(g.get("decodedAtFrame")) is int and healed_frame <= g["decodedAtFrame"] <= g["frame"]]
            if matching:
                self.setup["healed"] = {"frame": snapshot["frame"], "personality": mon["personality"],
                    "hp": mon["hp"], "maxHp": mon["maxHp"], "nativeGetter": deepcopy(matching[0])}
        if self.setup["healingObserved"] and map_id != 69 and self.setup["exitedCenter"] is None:
            self.setup["exitedCenter"] = snapshot["frame"]
        if "Y" in keys and new & KEY_BITS["Y"] and selector.get("state") == 2:
            self.setup["menuOpened"] = snapshot["frame"]
        if self.setup["menuOpened"] and selector.get("state") == 2 and selector.get("highlight") == 1:
            self.setup["highlighted"] = snapshot["frame"]
        if self.setup["highlighted"] and "Y" in keys and new & KEY_BITS["Y"] \
                and selector.get("state") != 2 and selector.get("highlight") == 1:
            self.setup["confirmed"] = snapshot["frame"]

    def _trace_status(self, data, events, frame, snapshot):
        stream = data.get("traceStream")
        if type(stream) is not int or stream not in self.trace_sequences \
                or stream != max(self.trace_sequences) or data.get("diagnosticOnly") is not True:
            raise ValueError("trace or field coverage incomplete")
        if data.get("code") == "ring-overwrite":
            # Ring reuse is independent of unread loss. Native sequence
            # continuity still has to hold after this notice.
            valid = set(data) == {"code", "traceStream", "diagnosticOnly", "count", "unreadEventsLost"} \
                and type(data.get("count")) is int and 1 <= data["count"] <= self.trace_sequences[stream] \
                and type(data.get("unreadEventsLost")) is int and data["unreadEventsLost"] == 0
        elif data.get("code") == "field-epoch-changed":
            old, new = (self.latest or {}).get("context", {}), (snapshot or {}).get("context", {})
            previous, current = data.get("previousEpoch"), data.get("fieldEpoch")
            valid = set(data) == {"code", "traceStream", "diagnosticOnly", "previousEpoch", "fieldEpoch", "sequenceReset"} \
                and data.get("sequenceReset") is False \
                and type(previous) is int and 1 <= previous <= 65535 \
                and type(current) is int and current == ((previous + 1) & 0xFFFF or 1) \
                and (self.latest or {}).get("fieldAvailable") is True \
                and (snapshot or {}).get("fieldAvailable") is True \
                and self.latest.get("frame") == frame - 1 and snapshot.get("frame") == frame \
                and type(old.get("fieldEpoch")) is int and old["fieldEpoch"] == previous \
                and type(new.get("fieldEpoch")) is int and new["fieldEpoch"] == current \
                and type(old.get("mapGeneration")) is int and 1 <= old["mapGeneration"] <= 65535 \
                and type(new.get("mapGeneration")) is int \
                and new["mapGeneration"] == ((old["mapGeneration"] + 1) & 0xFFFF or 1)
            notice_index = next(i for i, e in enumerate(events) if e.get("data") is data)
            witnesses = [(i, e.get("data", {})) for i, e in enumerate(events)
                         if e.get("kind") == "native" and e.get("frame") == frame]
            def matching_witness(index, event):
                actor = event.get("actor", {})
                handle = {"value": event.get("actorHandle"), **actor}
                # CONTEXT_CHANGED is written before header publication. A
                # writer-return drain can read it under the old header; a
                # later drain reads it under the new one. SemanticTrace emits
                # the epoch notice before that later batch's native events.
                capture_epoch = previous if index < notice_index else current
                return event.get("event") == "CONTEXT_CHANGED" \
                    and all(type(event.get(key)) is int for key in ("traceStream", "traceFieldEpoch", "valueA", "valueB")) \
                    and event["traceStream"] == stream and event["traceFieldEpoch"] == capture_epoch \
                    and event["valueA"] == previous and event["valueB"] == current \
                    and set(handle) == set(HANDLE_FIELDS) and all(type(v) is int for v in handle.values()) \
                    and 0 <= handle["slot"] < 10 and 1 <= handle["generation"] <= 65535 \
                    and 0 <= handle["encounterGeneration"] <= 65535 \
                    and handle["value"] == (handle["generation"] << 16 | handle["slot"]) \
                    and actor["fieldEpoch"] == previous and actor["mapGeneration"] == old["mapGeneration"]
            valid = valid and any(matching_witness(index, event) for index, event in witnesses)
        else:
            valid = False
        if not valid:
            raise ValueError("trace or field coverage incomplete")

    def _events(self, events, frame, snapshot=None):
        admissions = []
        self.player_collisions = []
        if not isinstance(events, list) or len(events) > 2048:
            raise ValueError("frame event list invalid")
        for event in events:
            if event.get("frame") != frame or not isinstance(event.get("data"), dict):
                raise ValueError("event outside completed frame")
            data = event["data"]
            if event.get("kind") == "trace-status":
                self._trace_status(data, events, frame, snapshot)
            elif event.get("kind") == "native-observation":
                if data.get("sequence") != self.native_sequence + 1 or data.get("setupMode") != ("prepared" if self.prepared_seen else "normal"):
                    raise ValueError("native observations missing, reordered, or prepared")
                self.native_sequence += 1
                if data.get("observation") == "spawn-metadata":
                    args = data.get("arguments")
                    if not isinstance(args, list) or len(args) != 4 \
                            or any(type(value) is not int or not 0 <= value <= 0xFFFFFFFF for value in args) \
                            or data.get("returnValue") not in (0, 1):
                        raise ValueError("spawn metadata timing receipt invalid")
                    # Normal base-form encounters are covered by the dense
                    # metadata table. A cache miss sends them back to file I/O.
                    # Alternate-form fallback remains a separate contract.
                    if args[0] != 0 and args[1] == 0 and data["returnValue"] == 0:
                        self._fail("spawn-metadata-unavailable", {"species": args[0], "form": args[1]}, frame=frame)
                        return admissions
                elif data.get("observation") == "player-step-admitted":
                    if data.get("stepIndex") != self.player_step_count + 1:
                        raise ValueError("player step callback missing or duplicated")
                    self.player_step_count += 1
                    admissions.append(data)
                elif data.get("observation") == "player-collision":
                    if snapshot is None or data.get("callerReturn") != 0x0205D4C6 \
                            or data.get("returnValue") != data.get("collisionMask"):
                        raise ValueError("stock walking collision caller/result missing")
                    entry = _integer(data.get("entryNativeCycle"), "collision entry cycle", 1)
                    returned = _integer(data.get("returnNativeCycle"), "collision return cycle", entry)
                    if not self.latest["nativeCycle"] <= entry <= returned <= snapshot["nativeCycle"]:
                        raise ValueError("walking collision outside completed frame")
                    before, after = data.get("objectBefore", {}), data.get("objectAfter", {})
                    if any(key not in before or key not in after or before[key] != after[key]
                           for key in ("x", "y", "x_prev", "y_prev", "pos_x", "pos_y", "pos_z")):
                        raise ValueError("walking collision changed native player pose")
                    pointer = _integer(data.get("objectPointer"), "collision player pointer", 0x02000000, 0x023FFED4)
                    if pointer & 3 or self.player_pointer is not None and pointer != self.player_pointer \
                            and not any(h["rebound"]["frame"] >= frame - 1 for h in self.handoffs):
                        raise ValueError("walking collision player changed without handoff")
                    self.player_collisions.append({**deepcopy(data), "frame": frame})
            elif event.get("kind") == "native":
                stream = _integer(data.get("traceStream"), "trace stream", 1)
                if data.get("sequence") != self.trace_sequences.get(stream, 0) + 1:
                    raise ValueError("semantic trace missing or duplicated")
                if len(self.trace_sequences) > 64:
                    raise ValueError("trace stream capacity exceeded")
                self.trace_sequences[stream] = data["sequence"]
                handle = {"value": data.get("actorHandle"), **data.get("actor", {})}
                _handle(handle)
                if handle["slot"] == 7:
                    self.follower_trace.append({**deepcopy(data), "frame": frame, "handle": handle})
        return admissions

    def _bind(self, snapshot, receipt):
        if self.pending_transition is not None:
            raise ValueError("follower binding precedes proved setup arrival")
        mon, getters = self._party(snapshot)
        if mon["hp"] <= 0 or mon["status"] != 0:
            self._fail("eligible-follower-current-party-gap", gap=True)
            return
        if self.mode == "normal" and not self.setup["initialEligible"] and not (self.setup["healed"] and self.setup["exitedCenter"]):
            self._fail("normal-healing-getter-or-exit-gap", gap=True)
            return
        if (self.mode == "normal" and not self.setup["confirmed"]) or snapshot.get("selector", {}).get("activeFollowerPartySlot") != 1 \
                or self.mode == "prepared" and not any(row["command"] == "spawn" for row in self.prepared_commands):
            self._fail("normal-Y-selection-provenance-gap", gap=True)
            return
        if not any(g.get("slot") == 1 and g.get("field") == "hp" and g.get("passed") is True
                   and g.get("personality") == mon["personality"] and g.get("species") == 155
                   and g.get("native") == g.get("decoded") == mon["hp"]
                   and g.get("boundary") == "natural-GetMonData-return"
                   and type(g.get("frame")) is int and self.initial_frame <= g["frame"] <= snapshot["frame"]
                   and (self.mode == "normal" or g["frame"] > self.prepared_commands[0]["startFrame"])
                   for g in getters):
            self._fail("eligible-follower-native-HP-evidence-gap", gap=True)
            return
        selected = select_current_actor(snapshot, receipt)
        if selected["species"] != 155 or selected["role"] != "FOLLOWER" \
                or selected["subjectIdentity"] != mon["personality"] or selected["handle"]["slot"] != 7:
            raise ValueError("follower is not the same saved party1 Cyndaquil")
        actor = next(a for a in snapshot["actors"] if a.get("handle") == selected["handle"])
        if actor["motionPhase"] != "IDLE":
            self._fail("follower-bind-before-initial-motion-terminal", gap=True)
            return
        self.crash_presentation.observe(snapshot, actor, None)
        self.subject, self.actor = selected, deepcopy(actor)
        self.setup["bound"] = snapshot["frame"]

    def _canceled_follower_handoff(self, snapshot, actor, context, rebound):
        """Retain the observed partial WALK; cancellation is not completion."""
        old, motion = self.actor, self.recorder.current
        frame = snapshot["frame"]
        if motion is None or old["motionPhase"] != "MOVING" or actor["motionPhase"] != "CANCELED" \
                or old["motionKind"] != "WALK" or actor.get("lastCancelReason") != 16 \
                or any(actor.get(k) != old.get(k) for k in
                       ("motionKind", "motionElapsed", "motionDuration", "origin", "target", "logical",
                        "commitSequence", "behaviorFingerprint", "authorityGeneration",
                        "engineAnchorGeneration", "presentationGeneration")) \
                or not old["reservationId"] or motion["handle"] != old["handle"] \
                or motion["commitBefore"] != actor["commitSequence"] \
                or motion["duration"] != old["motionDuration"] \
                or motion["origin"] != _tile(old["origin"]) or motion["target"] != _tile(old["target"]) \
                or motion["fingerprint"] != actor["behaviorFingerprint"] \
                or not motion["samples"] or motion["samples"][-1]["frame"] != frame - 1 \
                or motion["samples"][-1]["elapsed"] != old["motionElapsed"] \
                or actor["engineObject"].get("pos_y") != motion["samples"][-1]["render"][1] \
                or not 0 <= old["motionElapsed"] < old["motionDuration"] \
                or len(context) != 1 or len(rebound) != 1:
            raise ValueError("canceled follower handoff plan or partial samples differ")
        if actor["logical"] != actor["target"]:
            if old["logical"] != old["origin"] \
                    or _tile(old["engineObject"]) != _tile(old["origin"]):
                raise ValueError("canceled follower origin was not its unchanged engine tile")
            # Shared Walk interpolation may have traveled part of a tile
            # without publishing a logical advance. Validate each retained
            # sample against exact signed integer interpolation before allowing
            # NORMALIZE_SLOT to restore the unchanged current engine tile.
            start, end = _center(motion["origin"]), _center(motion["target"])
            delta = [end[i] - start[i] for i in (0, 1)]
            # This route admits one-tile Walks. Their first axis crossing is
            # at half duration (OverworldMotion_PathProgress); after that,
            # retaining the origin would itself be a missed logical advance.
            if max(abs(d) for d in delta) != 0x10000 \
                    or old["motionElapsed"] * 2 >= motion["duration"] \
                    or any(e["handle"] == old["handle"] and e["event"] == "PATH_ADVANCED"
                           and motion["startFrame"] <= e["frame"] <= frame
                           for e in self.follower_trace):
                raise ValueError("canceled follower origin contradicts its path advance")
            for sample in motion["samples"]:
                expected = [start[i] + (1 if delta[i] >= 0 else -1)
                            * (abs(delta[i]) * sample["elapsed"] // motion["duration"])
                            for i in (0, 1)]
                if [sample["render"][0], sample["render"][2]] != expected:
                    raise ValueError("canceled follower partial Walk differs from exact travel")
        self._canceled_follower_pose(actor)
        start = [e for e in self.follower_trace if e["handle"] == old["handle"]
                 and e["event"] == "MOTION_STARTED" and e["frame"] == motion["startFrame"]
                 and e.get("valueA") == 1 and e.get("valueB") == motion["duration"]]
        canceled = [e for e in self.follower_trace if e["handle"] == old["handle"]
                    and e["frame"] == frame and e["event"] == "MOTION_CANCELED"]
        control = [e for e in self.follower_trace if e["handle"] == old["handle"]
                   and e["frame"] == frame and e["event"] == "CONTROL_RETURNED"]
        if len(start) != 1 or len(canceled) != 1 or len(control) != 1:
            raise ValueError("canceled follower handoff terminal trace missing or duplicated")
        ordered = [start[0], canceled[0], control[0], context[0], rebound[0]]
        if any(e.get("reasonId") != 16 or e.get("reason") != "CONTEXT_LOST"
               for e in (canceled[0], control[0], context[0])) \
                or rebound[0].get("reasonId") != 0 or rebound[0].get("reason") != "OK" \
                or any(e["frame"] != frame for e in ordered[1:]) \
                or any(type(e.get("actorFrame")) is not int or e["actorFrame"] != snapshot["actorFrame"]
                       for e in ordered[1:]) \
                or len({e["traceStream"] for e in ordered}) != 1 \
                or any(a["sequence"] >= b["sequence"] for a, b in zip(ordered, ordered[1:])) \
                or canceled[0].get("valueA") != 1 or canceled[0].get("valueB") != actor["commitSequence"] \
                or control[0].get("valueA") != 0 or control[0].get("valueB") != actor["commitSequence"] \
                or any(e["handle"] == old["handle"] and e["event"] in ("LOGICAL_COMMIT", "MOTION_FINISHED")
                       and start[0]["sequence"] < e["sequence"] <= rebound[0]["sequence"]
                       for e in self.follower_trace):
            raise ValueError("canceled follower handoff terminal trace disagrees")
        proof = {"motion": deepcopy(motion), "start": deepcopy(start[0]),
                 "cancel": deepcopy(canceled[0]), "control": deepcopy(control[0]),
                 "terminal": {"frame": frame, "actor": deepcopy(actor)}}
        # This exact canceled terminal closes the record without invoking
        # MotionRecorder's successful commit/travel oracle or adding credit.
        self.recorder.current = None
        self.recorder.last_sample_key = None
        return proof

    @staticmethod
    def _canceled_follower_pose(actor):
        engine = actor["engineObject"]
        flags = _integer(engine.get("flags"), "canceled follower flags")
        logical = _tile(actor["logical"])
        # CancelActor does not commit or advance a tile. NORMALIZE_SLOT
        # centers the current engine tile; a canceled Walk can therefore
        # return to its proved logical origin, not its planned target.
        at_unmoved_origin = logical == _tile(actor["origin"]) and _tile(engine) == logical \
            and [engine.get("x_prev"), engine.get("y_prev")] == logical
        if actor.get("inputOwnership") != 0 or actor.get("reservationId") != 0 \
                or not flags & 1 or flags & 2 or flags & 0x10 and not flags & 0x20 \
                or logical != _tile(actor["target"]) and not at_unmoved_origin \
                or _tile(engine) != logical or [engine.get("x_prev"), engine.get("y_prev")] != logical \
                or _pose(engine) != _center(_tile(actor["logical"])) or engine.get("unk88_y") != 0:
            raise ValueError("canceled follower handoff lacks canonical control and pose")

    def _follower(self, snapshot):
        matches = [a for a in snapshot["actors"] if a.get("active") is True and a.get("handle", {}).get("slot") == 7]
        if len(matches) != 1:
            raise ValueError("exact follower is absent or duplicated")
        actor = matches[0]
        select_current_actor(snapshot, actor)
        if not live_identity(actor, actor.get("sourceIdentity", {}), actor.get("engineIdentity", {}),
                species=155, role="FOLLOWER", current_epoch=snapshot["context"]["fieldEpoch"]) \
                or actor["subjectIdentity"] != self.saved_mon["personality"] \
                or any(actor.get(key) != self.saved_mon[key] or actor.get("sourceIdentity", {}).get(key) != self.saved_mon[key]
                       for key in ("form", "level")):
            raise ValueError("follower native identity or saved personality changed")
        flags = _integer(actor["engineObject"].get("flags"), "follower engine flags")
        if not flags & (1 << 18):
            if not self.failures:
                self._fail("follower-pass-through-lost", {"frame": snapshot["frame"],
                    "handle": actor["handle"], "flags": flags}, frame=snapshot["frame"])
            return
        old = self.actor
        crash_transition = None
        if actor["handle"] != self.subject["handle"]:
            old_h, new_h = old["handle"], actor["handle"]
            stable = ("value", "slot", "generation", "encounterGeneration")
            context = [e for e in self.follower_trace if e["event"] == "CONTEXT_CHANGED" and e["handle"] == old_h
                       and e.get("valueA") == old_h["fieldEpoch"] and e.get("valueB") == new_h["fieldEpoch"]]
            rebound = [e for e in self.follower_trace if e["event"] == "ACTOR_REBOUND" and e["handle"] == new_h
                       and e.get("valueA") == self.latest["context"]["mapId"]
                       and e.get("valueB") == snapshot["context"]["mapId"]]
            if any(old_h[k] != new_h[k] for k in stable) \
                    or any(new_h[k] != ((old_h[k] + 1) & 0xFFFF or 1) for k in ("fieldEpoch", "mapGeneration")) \
                    or not context or not rebound or not self.latest["frame"] <= context[-1]["frame"] <= rebound[-1]["frame"] <= snapshot["frame"] \
                    or actor["commitSequence"] != old["commitSequence"]:
                self._fail("retained-follower-handoff-evidence-gap", {"before": old_h, "after": new_h}, gap=True)
                return
            canceled = None
            if old["motionPhase"] == "MOVING" and actor["motionPhase"] == "CANCELED":
                canceled = self._canceled_follower_handoff(snapshot, actor, context, rebound)
            elif self.recorder.current is not None or old["motionPhase"] != "IDLE" or not self.last_follower_terminal:
                raise ValueError("retained follower handoff is neither idle nor a proven canceled WALK")
            if len(self.handoffs) >= 64:
                raise ValueError("handoff bound exceeded")
            self.handoffs.append({"before": deepcopy(self.subject), "after": select_current_actor(snapshot, actor),
                                  "context": context[-1], "rebound": rebound[-1], "oldTerminal": self.last_follower_terminal})
            if canceled is not None:
                self.handoffs[-1]["canceledMotion"] = canceled
            crash_transition = {"context": context[-1], "rebound": rebound[-1]}
            self.subject = select_current_actor(snapshot, actor)
        elif any(actor[k] != self.subject[k] for k in ("authorityGeneration", "engineAnchorGeneration", "presentationGeneration")):
            raise ValueError("follower presentation generation changed without a proven handoff")
        if actor["motionPhase"] == "CANCELED" and self.handoffs and "canceledMotion" in self.handoffs[-1]:
            terminal = self.handoffs[-1]["canceledMotion"]["terminal"]["actor"]
            if any(actor.get(k) != terminal.get(k) for k in
                   ("handle", "origin", "target", "logical", "commitSequence", "motionElapsed", "motionDuration",
                    "lastCancelReason", "behaviorFingerprint")) \
                    or actor["motionKind"] not in ("NONE", terminal["motionKind"]) \
                    or actor["engineObject"].get("pos_y") != terminal["engineObject"].get("pos_y"):
                raise ValueError("canceled follower changed before its next motion")
            self._canceled_follower_pose(actor)
        motion_engine = self.crash_presentation.observe(snapshot, actor, old, transition=crash_transition)
        self.recorder.observe(snapshot["frame"], actor, motion_engine)
        if self.recorder.failures:
            detail = deepcopy(self.recorder.failures[0])
            if len(self.recorder.failures) > 1:
                detail["additionalFailures"] = deepcopy(self.recorder.failures[1:])
            self._fail("follower-motion-invalid", detail, frame=snapshot["frame"])
            return
        if self.recorder.current and len(self.recorder.current["samples"]) > 4096:
            raise ValueError("follower motion sample bound exceeded")
        for motion in self.recorder.completed:
            selected = [e for e in self.follower_trace if e["handle"] == motion["handle"]
                        and motion["startFrame"] <= e["frame"] <= motion["finishFrame"]]
            kind = {"WALK": 1, "HOP": 2, "TELEPORT": 3, "REPOSITION": 5}[motion["kind"]]
            checks = {
                "start": [e for e in selected if e["event"] == "MOTION_STARTED" and e["frame"] == motion["startFrame"]
                          and e.get("valueA") == kind and e.get("valueB") == motion["duration"]],
                "commit": [e for e in selected if e["event"] == "LOGICAL_COMMIT" and e.get("valueA") == motion["commitAfter"]],
                "finish": [e for e in selected if e["event"] == "MOTION_FINISHED" and e.get("valueA") == motion["commitAfter"]],
                "control": [e for e in selected if e["event"] == "CONTROL_RETURNED" and e.get("valueA") == 0 and e.get("valueB") == motion["commitAfter"]]}
            if any(len(values) != 1 for values in checks.values()):
                self._fail("follower-terminal-trace-gap", {key: len(value) for key, value in checks.items()}, gap=True)
                return
            self.follower_motions += 1
            self.last_follower_terminal = {"frame": motion["finishFrame"], "handle": motion["handle"],
                                          "commit": motion["commitAfter"], "events": checks}
            for handoff in self.handoffs:
                if "canceledMotion" in handoff and "recoveryTerminal" not in handoff \
                        and motion["handle"] == handoff["after"]["handle"] \
                        and motion["startFrame"] > handoff["rebound"]["frame"]:
                    handoff["recoveryTerminal"] = deepcopy(self.last_follower_terminal)
        self.recorder.completed.clear()
        if actor["motionPhase"] == "IDLE":
            engine = motion_engine
            flags = _integer(engine.get("flags"), "follower engine flags")
            if actor.get("inputOwnership") != 0 or actor.get("reservationId") != 0 \
                    or not flags & 1 or flags & 2 or flags & 0x10 and not flags & 0x20 \
                    or _pose(engine) != _center([actor["logical"]["x"], actor["logical"]["y"]]) \
                    or engine.get("unk88_y") != 0:
                self._fail("follower-idle-control-or-pose-mismatch")
        self.actor = deepcopy(actor)

    def _finish_player(self, snapshot):
        step = self.step
        result = classify_player_motion(step["samples"], step["start"], step["targetRender"],
            maximum_acceptance_frames=2, maximum_start_frames=2, maximum_settle_frames=4)
        if any(result[key] for key in ("acceptanceStall", "startStall", "interiorStalls", "renderRegressions", "settleStall")) \
                or not result["reachedTarget"] or step["callbacks"] != 1:
            self._fail("player-cadence-failed", result)
            return
        self.player_motions += 1
        # Only frames with measured accepted render progress count. Setup,
        # initial wait, frozen frames, and settle time cannot pad the S5 floor.
        self.active_frames += sum(s["accepted"] and s["progress"] for s in step["samples"])
        previous_tile = tuple(step["origin"])
        target_tile = tuple(step["target"])
        self.tiles.update((previous_tile, target_tile))
        previous_cell = (previous_tile[0] // 32, previous_tile[1] // 32)
        current_cell = (target_tile[0] // 32, target_tile[1] // 32)
        self.cells.update((previous_cell, current_cell))
        self.maps.update((step["startMap"], snapshot["context"]["mapId"]))
        continued = self.last_motion_keys == step["keys"] and not step["released"]
        self.held_run = self.held_run + 1 if continued else 1
        self.held_tiles += self.held_run >= 2
        self.held_cells += continued and previous_cell != current_cell
        self.held_maps += continued and step["startMap"] != snapshot["context"]["mapId"]
        self.last_motion_keys = step["keys"]
        self.motion_tail.append({"startFrame": step["startFrame"], "finishFrame": snapshot["frame"],
                                 "origin": step["origin"], "target": step["target"],
                                 "inputPhase": deepcopy(step["inputPhase"]), **result})
        self.step = None
        self.released_since_motion = False

    def _player(self, snapshot, keys, admissions):
        directions = [key for key in keys if key in DIRECTIONS]
        if len(directions) > 1:
            raise ValueError("normal stock-player cadence requires one cardinal input")
        if not directions:
            self.released_since_motion = True
        if self.step is None and directions:
            origin = _tile(self.latest["player"])
            delta = DIRECTIONS[directions[0]]
            target = [origin[i] + delta[i] for i in (0, 1)]
            self.step = {"origin": origin, "target": target, "start": _pose(self.latest["player"]),
                "targetRender": _center(target), "startFrame": snapshot["frame"], "startMap": self.latest["context"]["mapId"],
                "keys": directions, "samples": [], "callbacks": 0, "accepted": False,
                "inputPhase": [], "inputConsumed": False, "turnFrames": 0,
                "inputContext": deepcopy(self.latest["context"]),
                "initialFacing": self.latest["player"].get("facing"),
                "initialHeight": self.latest["player"].get("pos_y"),
                "released": self.released_since_motion}
        if len(admissions) > 1 or admissions and self.step is None:
            raise ValueError("unrequested or multiple player tile admissions")
        if self.step is not None and not self.step["accepted"]:
            step = self.step
            direction = step["keys"][0]
            facing = ("UP", "DOWN", "LEFT", "RIGHT").index(direction)
            mask = {"UP": 64, "DOWN": 128, "LEFT": 32, "RIGHT": 16}[direction]
            held = _integer(snapshot.get("selector", {}).get("heldKeys"), "stock held keys")
            player = snapshot["player"]
            stationary = _tile(player) == step["origin"] and _pose(player) == step["start"] \
                and player.get("pos_y") == step["initialHeight"]
            flags = _integer(player.get("flags"), "stock player flags")
            same_context = all(snapshot["context"].get(k) == step["inputContext"].get(k)
                               for k in ("mapId", "fieldEpoch", "mapGeneration"))
            if not step["inputConsumed"] and held & 0xF0 != mask:
                # A command can arrive after stock's keypad poll. Keep that
                # one completed queue, but do not call it consumed input.
                if step["inputPhase"] or admissions or not stationary or held & 0xF0 \
                        or not same_context or not flags & 1 or flags & 2 \
                        or player.get("facing") != step["initialFacing"]:
                    raise ValueError("player input was not consumed at the next stock poll")
                step["inputPhase"].append({"frame": snapshot["frame"], "phase": "awaiting-input"})
                return
            if held & 0xF0 != mask:
                raise ValueError("player consumed direction changed before admission")
            step["inputConsumed"] = True
            command = player.get("movement_cmd")
            if command in range(40, 44) and (step["turnFrames"] < 3 or player.get("movement_step") != 2):
                # Stock Cmd040..043: timer 2+1, then Step1 runs in the same
                # update. Completed states are step1, step1, step2/finished.
                n = step["turnFrames"] + 1
                if n > 3 or step["initialFacing"] == facing or command != 40 + facing \
                        or not same_context or not flags & 1 or flags & 2 \
                        or player.get("facing") != facing or not stationary or admissions \
                        or player.get("movement_step") != (2 if n == 3 else 1) \
                        or bool(flags & 0x20) != (n == 3) or not flags & 0x10:
                    raise ValueError("stock player turn phase is malformed or prolonged")
                step["turnFrames"] = n
                step["inputPhase"].append({"frame": snapshot["frame"], "phase": "stock-turn",
                    "command": command, "step": player["movement_step"], "flags": flags})
                return
            if step["turnFrames"] not in (0, 3):
                raise ValueError("stock player turn ended before its exact terminal")
        if self.player_collisions or self.player_collision_wait.active is not None:
            if self.step is None or self.step["accepted"]:
                raise ValueError("walking collision outside unadmitted request")
            if self.player_collision_wait.observe(snapshot, self.step, self.player_collisions,
                                                  admitted=bool(admissions)):
                # Exclude only a proved stationary object-blocked frame. Keep
                # prior admission-delay samples, and keep CPU/follower checks.
                self.step["inputPhase"].append({"frame": snapshot["frame"],
                                               "phase": "object-collision-wait"})
                return
        if admissions:
            receipt = admissions[0]
            pointer = _integer(receipt.get("objectPointer"), "current native player pointer", 0x02000000, 0x023FFFFF)
            before, after = receipt.get("objectBefore", {}), receipt.get("objectAfter", {})
            if self.step["callbacks"] or receipt.get("origin") != self.step["origin"] or receipt.get("target") != self.step["target"] \
                    or pointer & 3 or _pose(before) != self.step["start"] or _tile(before) != self.step["origin"] \
                    or _pose(after) != self.step["start"] or _tile(after) != self.step["target"] \
                    or [after.get("x_prev"), after.get("y_prev")] != self.step["origin"] \
                    or receipt.get("mapId") != self.step["startMap"]:
                raise ValueError("player callback does not match the requested exact tile")
            if self.player_pointer is not None and self.player_pointer != pointer \
                    and not any(h["rebound"]["frame"] >= self.step["startFrame"] - 1 for h in self.handoffs):
                raise ValueError("native player object changed without observed field handoff")
            self.player_pointer = pointer
            self.step["callbacks"] = 1
            self.step["accepted"] = True
        if self.step is None:
            return
        step = self.step
        render = _pose(snapshot["player"])
        previous = step["samples"][-1]["render"] if step["samples"] else step["start"]
        delta = [step["targetRender"][i] - step["start"][i] for i in (0, 1)]
        if any((delta[i] == 0 and render[i] != step["start"][i])
               or not min(step["start"][i], step["targetRender"][i]) <= render[i] <= max(step["start"][i], step["targetRender"][i])
               for i in (0, 1)):
            self._fail("player-render-outside-requested-cardinal-segment")
            return
        progress = sum((render[i] - previous[i]) * delta[i] for i in (0, 1))
        step["samples"].append({"accepted": step["accepted"], "render": render, "progress": progress > 0})
        n = len(step["samples"])
        if n > 1024:
            raise ValueError("player motion sample bound exceeded")
        if not step["accepted"] and n > 2:
            self._fail("player-input-not-admitted", {"origin": step["origin"], "target": step["target"]})
            return
        changes = [i for i, sample in enumerate(step["samples"], 1) if sample["progress"]]
        accepted = next((i for i, sample in enumerate(step["samples"], 1) if sample["accepted"]), None)
        if accepted and not changes and n - accepted > 2:
            self._fail("player-render-start-stall")
            return
        if progress < 0 or changes and progress == 0 and render != step["targetRender"]:
            self._fail("player-render-reversal" if progress < 0 else "player-render-stall")
            return
        if render == step["targetRender"]:
            if player_settled_at(snapshot, snapshot["context"]["mapId"], *step["target"]):
                self._finish_player(snapshot)
            elif changes and n - changes[-1] > 4:
                self._fail("player-settle-stall")

    def _prepared_setup_command(self, record, action):
        op, receipt, snapshot = record["command"], record.get("receipt", {}), record.get("snapshot", {})
        if self.mode != "prepared" or record.get("phase") != "setup" or action["op"] != op \
                or self.subject is not None or self.observed_frames or self.pending_transition is not None \
                or len(self.prepared_commands) >= 2 \
                or any(row["command"] == op for row in self.prepared_commands):
            raise ValueError("prepared command is repeated or outside unbound setup")
        boundary = receipt.get("setupBoundary", {})
        watermarks = boundary.get("traceSequences")
        if boundary.get("eventsDrained") is not True or not isinstance(watermarks, dict) or len(watermarks) > 64 \
                or not isinstance(receipt.get("events"), list) or snapshot.get("prepared") is not True \
                or boundary.get("frame") != snapshot.get("frame") or boundary.get("nativeCycle") != snapshot.get("nativeCycle"):
            raise ValueError("prepared command lacks drained setup boundary")
        if any(receipt.get("snapshot", {}).get(key) != snapshot.get(key) for key in
               ("frame", "nativeCycle", "party", "partyObservation", "actors", "context", "prepared")):
            raise ValueError("prepared command endpoint differs from retained readback")
        frame = _integer(snapshot.get("frame"), "prepared endpoint frame")
        delta = frame - self.latest["frame"]
        cycle = _integer(snapshot.get("nativeCycle"), "prepared endpoint native cycle")
        if delta < 0 or delta > action["budget"]["maxFrames"] or self.frames + delta > self.max_frames \
                or cycle < self.latest["nativeCycle"]:
            raise ValueError("prepared setup span exceeds its clock/budget bound")
        mon, _ = self._party(snapshot)
        if op == "party":
            args = action["args"]
            if receipt.get("value", {}).get("slot") != 1 or receipt.get("value", {}).get("action") != "edit" \
                    or receipt.get("party") != snapshot["party"] or receipt.get("personality") != mon["personality"] \
                    or any(mon[key] != (mon["maxHp"] if value == "max" else value)
                           for key,value in args.items() if key in ("hp", "status")):
                raise ValueError("prepared party edit does not match requested same-Pokemon readback")
        else:
            expected = {"slot":1,"role":"FOLLOWER",**{key:mon[key] for key in ("species","personality","form","level")}}
            if receipt.get("lifecycle") != "prepared-native-follower-lifecycle" or receipt.get("preparedOnly") is not True \
                    or receipt.get("requestedSubject") != expected or mon["hp"] <= 0 or mon["status"] != 0:
                raise ValueError("prepared follower receipt differs from saved Pokemon")
        traces = {}
        for stream, sequence in watermarks.items():
            if not isinstance(stream, str) or not stream.isdecimal() or str(int(stream)) != stream:
                raise ValueError("invalid prepared trace stream watermark")
            traces[_integer(int(stream), "prepared trace stream", 1)] = _integer(sequence, "prepared trace sequence")
        if any(traces.get(stream, -1) < sequence for stream,sequence in self.trace_sequences.items()):
            raise ValueError("prepared trace watermark rolled back")
        observation = snapshot.get("nativeObservation", {})
        sequence = _integer(observation.get("sequence"), "prepared native watermark", self.native_sequence)
        steps = _integer(observation.get("playerStepCount"), "prepared player watermark", self.player_step_count)
        self.native_sequence, self.player_step_count = sequence, steps
        self._snapshot(snapshot, command_boundary=True)
        self.prepared_seen = True
        self.trace_sequences = traces
        self.frames += delta
        self.prepared_commands.append({"action":action["id"],"command":op,
            "startFrame":self.latest["frame"],"endFrame":frame,"excludedFrames":delta,
            "scope":"prepared setup span; no movement/CPU credit","receipt":deepcopy(receipt)})
        self.latest = deepcopy(snapshot)

    def observe_record(self, record, *, frame_callback=None, full_report=True):
        report = self.result if full_report else self.progress_result
        if self.closed or self.failures:
            return report()
        try:
            if not isinstance(record, dict):
                raise ValueError("shared stream record must be an object")
            if "initialSnapshot" in record:
                if self.latest is not None:
                    raise ValueError("duplicate initial snapshot")
                self._snapshot(record["initialSnapshot"], initial=True)
                self.latest = deepcopy(record["initialSnapshot"])
                if frame_callback:
                    frame_callback(self.latest, (), self)
                return report()
            if self.latest is None:
                raise ValueError("shared initial snapshot missing")
            phase = record.get("phase")
            action = self.actions.get((phase, record.get("action")))
            if action is None:
                raise ValueError("record does not name a sealed recipe action")
            if record.get("command") in ("party", "spawn"):
                self._prepared_setup_command(record, action)
                if frame_callback:
                    frame_callback(self.latest, (), self)
                return report()
            if record.get("command") == "skip":
                if not action.get("skipIf") or self.pending_transition is not None:
                    raise ValueError("unapproved action skip")
                return report()
            if record.get("command") == "bind":
                if action["op"] != "bind" or action["args"].get("subject") != self.subject_id \
                        or record["snapshot"]["frame"] != self.latest["frame"]:
                    raise ValueError("unexpected follower binding record")
                self._bind(record["snapshot"], record["receipt"])
                return report()
            if action["op"] not in ("step", "wait") or "command" in record:
                raise ValueError("unexpected execution or prepared command")
            if self.last_action != (phase, action["id"]):
                self.released_since_motion = True  # shared jobs release at each action boundary
            self.last_action = (phase, action["id"])
            keys = action["args"].get("keys", [])
            from tools.overworld.devtools_raw_chunk import validate_raw_chunk
            rows = validate_raw_chunk(record, self.latest)
            if self.frames + len(rows) > self.max_frames:
                raise ValueError("completed-frame budget exceeded")
            for snapshot, sample_events, finished_intervals in rows:
                for interval in finished_intervals:
                    self.cpu.append(interval["cpuNs"])
                    if phase == "observe": self.route_cpu.append(interval["cpuNs"])
                self.native_cycles += len(finished_intervals)
                if len(self.cpu) > self.max_frames * 6 + 120:
                    raise ValueError("native cycle storage bound exceeded")
                admissions = self._events(sample_events, snapshot["frame"], snapshot)
                mon, getters = self._snapshot(snapshot)
                self._setup_transition(snapshot, phase, action, admissions)
                self.frames += 1
                if self.frames > self.max_frames:
                    raise ValueError("completed-frame budget exceeded")
                if snapshot.get("fieldAvailable") is False:
                    self.latest = deepcopy(snapshot)
                    if frame_callback:
                        frame_callback(self.latest, sample_events, self)
                    continue
                if phase == "setup" and self.mode == "normal":
                    self._setup_frame(snapshot, keys, mon, getters)
                elif phase == "observe":
                    if self.subject is None:
                        raise ValueError("route observation precedes exact follower binding")
                    # This saved-fixture route's source-confirmed outdoor
                    # headers are Route29, Route30 and Cherrygrove. Do not
                    # silently count an unclassified interior as outdoor.
                    if snapshot["context"]["mapId"] not in (33, 34, 67):
                        self._fail("outdoor-route-map-classification-gap", snapshot["context"], gap=True)
                        break
                    self.observed_frames += 1
                    queue_delay = guest_queue_delay(self.latest, snapshot)
                    if queue_delay is not None:
                        self._fail("guest-main-queue-delay", queue_delay)
                        self.latest = deepcopy(snapshot)
                        break
                    self._follower(snapshot)
                    if not self.failures: self._player(snapshot, keys, admissions)
                self.latest = deepcopy(snapshot)
                if self.failures: break
                if len(self.route_cpu) >= 16 and len(self.route_cpu) - self.last_cpu_check >= 128:
                    self._cpu_check()
                if self.failures: break
                if frame_callback:
                    frame_callback(self.latest, sample_events, self)
            if len(self.route_cpu) >= 16 and len(self.route_cpu) - self.last_cpu_check >= 128:
                self._cpu_check()
        except (ValueError, KeyError, TypeError, IndexError, AttributeError) as error:
            self._fail("cadence-observation-invalid", str(error))
        return report()

    def _cpu_check(self):
        self.hitches = classify_frame_hitches(self.route_cpu, 2000, 250000)
        self.last_cpu_check = len(self.route_cpu)
        if self.hitches["hitchCount"]:
            if not self.diagnostic_continue_host_hitches:
                self._fail("host-process-cpu-hitch", self.hitches)
            else:
                receipt = dict(code="host-process-cpu-hitch", frame=None if self.latest is None else self.latest["frame"],
                    detail=deepcopy(self.hitches))
                if self.host_cpu_first is None:
                    self.host_cpu_first = receipt
                if self.host_cpu_worst is None or self.hitches["maximumNs"] > self.host_cpu_worst["detail"]["maximumNs"]:
                    self.host_cpu_worst = receipt

    def _host_diagnostic(self, route_ready):
        if not self.diagnostic_continue_host_hitches:
            return {}
        return dict(diagnosticContinueHostHitches=True, routeWindowReady=route_ready or self.diagnostic_route_complete,
            hostCpuViolation=deepcopy(self.host_cpu_first),
            hostCpuWorst=deepcopy(self.host_cpu_worst), hostCpuLatest=deepcopy(self.hitches))

    def progress_result(self):
        """Detached current status; no copies of retained proof history."""
        ready = not self.failures and self.active_frames >= MIN_ACTIVE and len(self.tiles) >= MIN_TILES \
            and len(self.cells) >= MIN_CELLS and len(self.maps) >= MIN_MAPS \
            and self.follower_motions >= MIN_FOLLOWER_MOTIONS and bool(self.handoffs) \
            and all("canceledMotion" not in h or "recoveryTerminal" in h for h in self.handoffs) \
            and all((self.held_tiles, self.held_cells, self.held_maps)) \
            and self.step is None and self.recorder.current is None and self.crash_presentation.ready \
            and self.player_collision_wait.ready
        return {"state": "failed" if self.failures else "passed" if self.closed and ready else "running",
                "passed": self.closed and ready, "ready": ready, "acceptedProof": False,
                "subject": deepcopy(self.subject), "failures": deepcopy(self.failures),
                **self._host_diagnostic(ready)}

    def result(self):
        ready = self.progress_result()["ready"]
        return {"state": "failed" if self.failures else "passed" if self.closed and ready else "running",
            "passed": self.closed and ready, "ready": ready, "acceptedProof": False,
            **self._host_diagnostic(ready),
            "fixtureMode": self.mode,
            "sampledFrames": self.frames, "observedFrames": self.observed_frames,
            "activeMovementFrames": self.active_frames, "nativeCycles": self.native_cycles,
            "absentSetupFrames": self.absent_setup_frames,
            "setupTransitions": deepcopy(self.completed_setup_transitions),
            "preparedSetup": deepcopy(self.prepared_commands),
            "distinctTiles": len(self.tiles), "streamingCells": len(self.cells), "maps": sorted(self.maps),
            "routeTiles": [list(tile) for tile in sorted(self.tiles)],
            "routeCells": [list(cell) for cell in sorted(self.cells)],
            "cpuSamples": list(self.route_cpu),
            "routeNativeCycles": len(self.route_cpu),
            "settledSnapshot": deepcopy(self.latest),
            "lastFollowerTerminal": deepcopy(self.last_follower_terminal),
            "playerCollisionWaits": deepcopy(self.player_collision_wait.proofs),
            "terminalState": {"playerInFlight": self.step is not None,
                "playerCollisionWaitPending": not self.player_collision_wait.ready,
                "followerInFlight": self.recorder.current is not None,
                "crashPresentationPending": not self.crash_presentation.ready,
                "setupTransitionPending": self.pending_transition is not None},
            "playerMotions": self.player_motions, "followerMotions": self.follower_motions,
            "heldMultiTileSegments": self.held_tiles, "heldCellCrossings": self.held_cells, "heldMapCrossings": self.held_maps,
            "subject": deepcopy(self.subject), "setup": deepcopy(self.setup),
            "handoffs": deepcopy(self.handoffs), "cpu": deepcopy(self.hitches),
            "crashPresentations": deepcopy(self.crash_presentation.proofs),
            "motionTail": deepcopy(list(self.motion_tail)), "failures": deepcopy(self.failures), "evidenceGaps": self.gaps[:],
            "limits": {"activeFrames": MIN_ACTIVE, "tiles": MIN_TILES, "cells": MIN_CELLS, "maps": MIN_MAPS,
                       "followerMotions": MIN_FOLLOWER_MOTIONS, "inputFrames": 2, "renderStartFrames": 2,
                       "settleFrames": 4, "cpuRatioPerMille": 2000, "cpuExtraNs": 250000},
            "scope": "pure shared-stream cadence measurement; controller acceptance and live calibration remain separate"}

    def finish(self):
        if not self.closed:
            self._cpu_check()
            if self.diagnostic_continue_host_hitches:
                self.diagnostic_route_complete = self.progress_result()["ready"]
            if not self.failures and self.pending_transition is not None:
                self._fail("setup-transition-arrival-missing", self.pending_transition, gap=True)
            if not self.failures and not self.result()["ready"]:
                self._fail("long-route-measurement-incomplete", {"activeFrames": self.active_frames,
                    "tiles": len(self.tiles), "cells": len(self.cells), "maps": len(self.maps),
                    "followerMotions": self.follower_motions, "heldCrossings": [self.held_cells, self.held_maps],
                    "playerInFlight": self.step is not None, "followerInFlight": self.recorder.current is not None,
                    "crashPresentationPending": not self.crash_presentation.ready,
                    "handoffRecoveryPending": any("canceledMotion" in h and "recoveryTerminal" not in h for h in self.handoffs)})
            if self.diagnostic_continue_host_hitches and not self.accept_host_cpu_hitches and not self.failures:
                if self.host_cpu_first is not None:
                    first = self.host_cpu_first
                    self._fail(first["code"], first["detail"], frame=first["frame"])
                else:
                    self._fail("diagnostic-cadence-not-proof", "host-hitch continuation cannot grant terminal proof")
            self.closed = True
        return self.result()
