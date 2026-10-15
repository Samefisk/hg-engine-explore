"""Finite natural refill retry and water birth proof from existing raw receipts.

The shared raw chunk validator owns physical queue coverage. The promoted
spawn outcome parser owns exact finalizer/constructor/control attribution.
No profile, population, encounter, RNG, save or player state is changed here.
"""
from copy import deepcopy

from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_movement_predicates import check_movement_predicate
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_spawn_outcome_records import (
    WORLD, inside, loader_identity, need, parse_record, quality)
from tools.overworld.devtools_spawn_surface_measurement import check_natural_water_surface

RETRY = "natural-refill-retry-v1"
WATER = "natural-water-spawn-v1"
KINDS = frozenset((RETRY, WATER))
CASES = {
    RETRY: dict(test="population.failed-series-retry", requirement="current.natural-refill-retry",
        start=(67, 543, 393), frames=(240, 360), segment=60),
    WATER: dict(test="population.natural-water-spawn", requirement="current.natural-water-spawn",
        start=(34, 565, 369), frames=(600,), segment=150),
}
SELECTED = frozenset(("spawn-finalized", "spawn-queued", "spawn-prepared",
    "spawn-object-create", "spawn-landing-height", "entry-native-control"))


# Reuse the normal 35-step fixture before a different-map prepared warp.
# Its 13 declared action budgets add 481 frames to the existing 720 ceiling.
WARMUP_FRAMES = 481
MAX_TOTAL_FRAMES = 720 + WARMUP_FRAMES
TRANSITION_WAIT_FRAMES = 64


def max_total_frames(kind):
    return MAX_TOTAL_FRAMES + (TRANSITION_WAIT_FRAMES + 1 if kind == RETRY else 0)


def warmup_setup():
    # Lazy import avoids the contract module's measurement import cycle.
    from tools.overworld.devtools_test_contract import _d1_warmup_setup
    return _d1_warmup_setup() + [
        dict(id="warmup-current-follower", op="wait",
             args=dict(predicate=dict(kind="actor-present", subject="mankey", when="final")),
             budget=dict(maxSeconds=30, maxFrames=64, noProgressFrames=64)),
        dict(id="warmup-follower-settled", op="wait",
             args=dict(predicate=dict(kind="follower-settled", species=56, partySlot=2, when="final")),
             budget=dict(maxSeconds=30, maxFrames=120, noProgressFrames=120)),
        dict(id="warmup-bind-current-field", op="bind", args=dict(subject="mankey"),
             budget=dict(maxSeconds=10, maxFrames=1, noProgressFrames=1))]


def setup_for(kind):
    map_id, x, z = CASES[kind]["start"]
    return tuple((a["id"], a["op"], a["args"]) for a in warmup_setup()) + (
        ("natural-window", "teleport", dict(map=map_id, x=x, z=z, facing=1)),
        ("current-follower", "wait", dict(predicate=dict(kind="follower-settled", species=56, partySlot=2, when="final"))),
        ("bind-current-field", "bind", dict(subject="mankey")))


def actions_for(kind):
    case = CASES[kind]
    actions = []
    for window, total in enumerate(case["frames"]):
        if window:
            actions.extend((("route29-window", "teleport", dict(map=33, x=585, z=406, facing=1)),
                ("route29-current-follower", "wait", dict(predicate=dict(
                    kind="follower-settled", species=56, partySlot=2, when="final"))),
                ("route29-bind-current-field", "bind", dict(subject="mankey"))))
        prefix = "water" if kind == WATER else ("cherrygrove" if window == 0 else "route29")
        actions.extend((f"{prefix}-{i + 1}", "step", dict(frames=case["segment"], keys=[]))
                       for i in range(total // case["segment"]))
    return tuple(actions)


def validate_recipe(test):
    kind = test.get("measurements", [{}])[0].get("kind")
    need(kind in KINDS, "natural spawn recipe kind differs")
    case = CASES[kind]
    need(test.get("id") == case["test"] and test.get("mode") == "prepared"
         and test.get("fixture") == dict(rom="test.nds", save="test.sav")
         and test.get("requirements") == [case["requirement"]]
         and test.get("subjects") == [dict(id="mankey", species=56, role="FOLLOWER", acquire="existing")]
         and test.get("measurements") == [dict(kind=kind, subject="mankey")]
         and test["setup"][:13] == warmup_setup()
         and tuple((a["id"], a["op"], a["args"]) for a in test["setup"]) == setup_for(kind)
         and tuple((a["id"], a["op"], a["args"]) for a in test["actions"]) == actions_for(kind)
         and test.get("assertions") == [dict(kind="measurement-complete", measurement=kind, when="final")]
         and test["budgets"]["minObservedFrames"] == sum(case["frames"])
         and test["budgets"]["maxFrames"] == max_total_frames(kind)
         and test["budgets"]["maxSeconds"] == 240,
         "natural spawn recipe changed its exact neutral trigger or setup")
    if kind == RETRY:
        need(test["actions"][5]["budget"] == dict(maxSeconds=30, maxFrames=TRANSITION_WAIT_FRAMES,
             noProgressFrames=TRANSITION_WAIT_FRAMES)
             and test["actions"][6]["budget"] == dict(maxSeconds=10, maxFrames=1, noProgressFrames=1),
             "natural spawn second-field binding budget differs")


def _record(snapshots, events):
    # This is the complete checked step stream, not the bounded archive ring.
    # Counts describe these arrays exactly; raw coverage is checked first.
    return dict(snapshots=snapshots, events=events, truncated=False, definiteFailures=[],
        counts=dict(snapshotsRetained=len(snapshots), eventsRetained=len(events),
            snapshotsDropped=0, eventsDropped=0, failuresDropped=0, failuresReceived=0))


def retry_witnesses(report, events):
    attempts = report["naturalAttempts"]
    failures, density = [], []
    for event in events:
        data = event.get("data", {})
        entry = data.get("entry", {})
        if data.get("observation") != "entry-native-control":
            continue
        op = entry.get("operation")
        failed = op == 7 and entry.get("outcome") == 2 or (
            op == 8 and entry.get("queryOperation") == 1 and entry.get("prepareResult") == 0)
        delay = entry.get("refillDelay")
        if failed and type(delay) is int and delay > 0:
            field, epoch, generation = loader_identity(data)
            later = next((a for a in attempts if a["startProven"]
                and (a["world"]["fieldPointer"], a["world"]["fieldEpoch"], a["world"]["mapGeneration"])
                    == (field, epoch, generation)
                and a["start"]["sequence"] > data["sequence"]), None)
            if later is not None:
                gap = later["start"]["entryActorFrame"] - data["returnActorFrame"]
                need(gap >= delay, "failed refill ignored its decoded delay")
                if delay != 15:
                    continue
                need(gap < 60, "failed refill did not use its short retry window")
                failures.append(dict(sequence=data["sequence"], delay=delay, actorFrameGap=gap,
                    nextAttemptId=later["spawnAttemptId"], nextSequence=later["start"]["sequence"]))
    for attempt in attempts:
        for control in attempt["controls"]:
            if control["operation"] != 7 or control.get("outcome") != 3:
                continue
            need(len(attempt["creations"]) == 1 and control["refillDelay"] >= 60,
                 "success refill delay lacks its actual constructor")
            later = next((a for a in attempts if a["world"] == attempt["world"]
                and a["startProven"] and a["start"]["sequence"] > control["sequence"]), None)
            if later is not None:
                gap = later["start"]["entryActorFrame"] - control["returnActorFrame"]
                need(gap >= control["refillDelay"], "actual creation used a short refill delay")
                density.append(dict(sequence=control["sequence"], delay=control["refillDelay"],
                    actorFrameGap=gap, handle=deepcopy(attempt["creations"][0]["handle"]),
                    nextAttemptId=later["spawnAttemptId"]))
    return failures, density


def water_witnesses(report, snapshots, events):
    witnesses = []
    constructors = {e["data"]["sequence"]: e for e in events
                    if e.get("data", {}).get("observation") == "spawn-prepared"}
    for attempt in report["naturalAttempts"]:
        if attempt["terrain"] != 1 or len(attempt["creations"]) != 1:
            continue
        creation = attempt["creations"][0]
        if not creation["insideSnapshotWindow"]:
            continue
        spawn = constructors[creation["sequence"]]["data"]
        need(spawn.get("startup", {}).get("locomotion") == 7,
             "natural water birth did not use the shared Appear Hop startup")
        for snapshot in snapshots:
            if snapshot["frame"] <= creation["frame"]:
                continue
            actors = [a for a in snapshot.get("actors", []) if a.get("handle") == creation["handle"]]
            if len(actors) != 1:
                continue
            actor = actors[0]
            engine = actor.get("engineObject", {})
            if actor.get("controllerState") != 0 or actor.get("motionPhase") != "IDLE" \
                    or engine.get("movement_cmd") != 255:
                continue
            landing = check_natural_water_surface(spawn, snapshot, species=creation["species"])
            witnesses.append(dict(spawnAttemptId=attempt["spawnAttemptId"], querySerial=attempt["querySerial"],
                constructorSequence=creation["sequence"], constructorFrame=creation["frame"],
                handle=deepcopy(creation["handle"]), landing=landing))
            break
    return witnesses


class SpawnPriorityMeasurement:
    def __init__(self, test, source):
        validate_recipe(test)
        need(source == dict(contractVersion=1), "natural spawn contract input differs")
        self.test, self.kind = test, test["measurements"][0]["kind"]
        self.case = CASES[self.kind]
        self.latest = None
        self.subject = None
        self.setup_index = self.action_index = self.action_frames = self.observed_frames = 0
        self.window = 0
        self.windows = [dict(snapshots=[], events=[]) for _ in self.case["frames"]]
        self.last_sequence = None
        self.failures, self.outcomes = [], {}
        self.closed = False
        self.follower_identity = None
        self.warmup_identity = None
        self.warmup_boundary = None
        self.warmup_steps, self.warmup_object = 0, None
        self.setup_action_frames = self.warmup_frames = 0
        self.window_transition = None
        self.transition_wait_frames = 0

    def _boundary(self, sample):
        need(sample.get("observationBoundary") == "main-task-queue-completion"
             and sample.get("fieldAvailable") is True
             and sample.get("fieldControl", {}).get("taskPointer") == 0,
             "natural spawn completed field boundary differs")
        quality(_record([sample], []))

    def _setup_ready(self, action):
        predicate = action["args"].get("predicate", action["args"].get("until"))
        if predicate is None:
            return False
        if predicate["kind"] != "actor-present":
            return check_movement_predicate(predicate, self.latest)
        candidates = [a for a in self.latest.get("actors", []) if a.get("active") is True
                      and a.get("role") == "FOLLOWER" and a.get("species") == 56]
        need(len(candidates) <= 1, "natural spawn setup has multiple saved followers")
        if not candidates:
            return False
        select_current_actor(self.latest, candidates[0])
        return True

    def _warmup_native(self, sample, events):
        for event in events:
            data = event.get("data", {})
            if event.get("kind") != "native-observation" or data.get("observation") != "player-step-admitted":
                continue
            count = self.warmup_steps + 1
            if count == 1:
                direction, origin, target = 3, [564, 392], [565, 392]
            elif count <= 7:
                direction, origin, target = 1, [565, 390 + count], [565, 391 + count]
            elif count <= 27:
                direction, origin, target = 3, [557 + count, 398], [558 + count, 398]
            else:
                direction, origin, target = 1, [585, 370 + count], [585, 371 + count]
            pointer = data.get("objectPointer")
            need(count <= 35 and data.get("setupMode") == ("prepared" if sample.get("prepared") else "normal")
                 and data.get("stepIndex") == count and data.get("direction") == direction
                 and data.get("mapId") == (67 if count <= 18 else 33)
                 and data.get("origin") == origin and data.get("target") == target
                 and [data.get("objectBefore", {}).get(k) for k in ("x", "y")] == origin
                 and [data.get("objectAfter", {}).get(k) for k in ("x", "y")] == target
                 and type(pointer) is int and pointer > 0 and data.get("returnValue") == pointer
                 and (self.warmup_object is None or pointer == self.warmup_object),
                 "natural spawn warmup native admission differs from the normal 35-step route")
            self.warmup_steps, self.warmup_object = count, pointer
        need(sample.get("nativeObservation", {}).get("playerStepCount") == self.warmup_steps,
             "natural spawn warmup counter lacks its exact native admissions")

    def _observe_setup(self, row, on_sample):
        actions = self.test["setup"]
        # A wait (or bounded until) that is already true emits no job row.
        while self.setup_index < len(actions) and actions[self.setup_index]["id"] != row.get("action"):
            action = actions[self.setup_index]
            need(action["op"] in ("wait", "step") and self._setup_ready(action),
                 "natural spawn setup order differs")
            self.setup_index += 1
            self.setup_action_frames = 0
        need(self.setup_index < len(actions), "natural spawn setup exceeds its declared actions")
        action = actions[self.setup_index]
        if "samples" in row:
            need(action["op"] in ("step", "wait") and "command" not in row,
                 "natural spawn setup input command differs")
            if "requestedInput" in row:
                need(row["requestedInput"].get("keys") == action["args"].get("keys", []),
                     "natural spawn setup normal input differs")
            for sample, events, _ in validate_raw_chunk(row, self.latest):
                self._boundary(sample)
                self.setup_action_frames += 1
                need(self.setup_action_frames <= action["budget"]["maxFrames"],
                     "natural spawn setup action exceeds its declared frame ceiling")
                if self.setup_index < 13:
                    self._warmup_native(sample, events)
                    self.warmup_frames += 1
                    need(self.warmup_frames <= WARMUP_FRAMES,
                         "natural spawn warmup exceeds its declared frame ceiling")
                self.latest = deepcopy(sample)
                if on_sample:
                    on_sample(sample, 0)
            if self._setup_ready(action) or (action["op"] == "step"
                    and "until" not in action["args"]
                    and self.setup_action_frames == action["args"]["frames"]):
                self.setup_index += 1
                self.setup_action_frames = 0
            return
        need(row.get("command") == action["op"] and action["op"] in ("bind", "teleport"),
             "natural spawn setup command differs")
        sample = row["snapshot"]
        self._boundary(sample)
        if action["op"] == "bind":
            subject = select_current_actor(sample, row["receipt"])
            need((subject["species"], subject["role"]) == (56, "FOLLOWER"),
                 "natural spawn saved follower differs")
            if self.setup_index == 12:
                need(check_movement_predicate(dict(kind="player-settled-at", map=33, x=585, z=406), sample)
                     and check_movement_predicate(dict(kind="player-step-count", operator="eq", value=35), sample)
                     and sample.get("selector", {}).get("physicalPressed") == 0
                     and check_movement_predicate(dict(kind="follower-settled", species=56, partySlot=2), sample),
                     "natural spawn warmup did not finish the normal 35-step Route29 path")
                need(self.warmup_steps == 35 and subject["subjectIdentity"] == self.warmup_identity,
                     "natural spawn warmup changed the saved follower or lost native steps")
                self.warmup_boundary = dict(frame=sample["frame"], context=deepcopy(sample["context"]),
                    player=[585, 406], subject=deepcopy(subject), credited=False)
            else:
                need(subject["subjectIdentity"] == self.warmup_identity
                     and check_movement_predicate(dict(kind="follower-settled", species=56, partySlot=2), sample),
                     "natural spawn warp changed the saved follower or is not settled")
                self.subject, self.follower_identity = subject, subject["subjectIdentity"]
        else:
            map_id, x, z = self.case["start"]
            need(self.warmup_boundary is not None and self.latest["context"]["mapId"] == 33
                 and sample["context"]["mapId"] == map_id
                 and all(sample["context"].get(key) != self.latest["context"].get(key)
                         for key in ("fieldEpoch", "mapGeneration"))
                 and [sample["player"][k] for k in ("x", "y")] == [x, z]
                 and row["receipt"].get("preparedOnly") is True
                 and all(row["receipt"]["snapshot"].get(k) == sample.get(k)
                         for k in ("frame", "nativeCycle", "context"))
                 and row["receipt"].get("setupBoundary", {}).get("eventsDrained") is True
                 and row["receipt"]["setupBoundary"].get("frame") == sample["frame"]
                 and row["receipt"]["setupBoundary"].get("nativeCycle") == sample["nativeCycle"],
                 "natural spawn setup warp lacks its different-map completed receipt")
        self.latest = deepcopy(sample)
        self.setup_index += 1
        self.setup_action_frames = 0
        if on_sample:
            on_sample(sample, 0)

    def _event_coverage(self, event):
        if event.get("kind") == "trace-status":
            data = event.get("data")
            need(isinstance(data, dict)
                 and set(data) == {"code", "traceStream", "diagnosticOnly", "count", "unreadEventsLost"}
                 and data["code"] == "ring-overwrite" and data["diagnosticOnly"] is True
                 and type(data["traceStream"]) is int and data["traceStream"] > 0
                 and type(data["count"]) is int and data["count"] > 0
                 and type(data["unreadEventsLost"]) is int and data["unreadEventsLost"] == 0,
                 "natural spawn raw event coverage is incomplete")
        if event.get("kind") == "native-observation":
            sequence = event["data"].get("sequence")
            need(type(sequence) is int and sequence > 0 and (
                self.last_sequence is None or sequence == self.last_sequence + 1),
                "natural spawn native receipt sequence has a gap or duplicate")
            self.last_sequence = sequence

    def _transition_pose(self, sample):
        need(self.kind == RETRY and self.window == 1 and self.window_transition is not None
             and sample["context"] == self.window_transition["context"]
             and [sample["player"][k] for k in ("x", "y")] == [585, 406]
             and all(sample.get("selector", {}).get(k) == 0
                     for k in ("heldKeys", "newKeys", "physicalPressed", "simulatedKeys")),
             "natural spawn second-field wait changed its scope or neutral input")

    def _observe_transition_wait(self, row, on_sample):
        need("command" not in row and row.get("requestedInput", {}).get("keys") == [],
             "natural spawn second-field wait changed neutral input")
        action = self.test["actions"][self.action_index]
        for sample, events, _ in validate_raw_chunk(row, self.latest):
            self._boundary(sample)
            self._transition_pose(sample)
            self.action_frames += 1
            self.transition_wait_frames += 1
            need(self.action_frames <= TRANSITION_WAIT_FRAMES,
                 "natural spawn second-field wait exceeds its frame ceiling")
            # An absent follower is allowed only in this uncredited wait.
            followers = [a for a in sample["actors"] if a.get("active") is True
                         and a.get("role") == "FOLLOWER"]
            need(len(followers) <= 1, "natural spawn second-field wait has multiple followers")
            if followers:
                actor = select_current_actor(sample, followers[0])
                need((actor["species"], actor["subjectIdentity"]) == (56, self.follower_identity),
                     "natural spawn second-field wait changed its saved follower")
            for event in events:
                self._event_coverage(event)
            self.latest = deepcopy(sample)
            if on_sample:
                on_sample(sample, self.observed_frames)
        if self._setup_ready(action):
            self.action_index += 1
            self.action_frames = 0

    def observe_record(self, row, on_sample=None):
        try:
            if "initialSnapshot" in row:
                need(self.latest is None and row.get("phase") == "setup", "natural spawn initial boundary differs")
                self.latest = deepcopy(row["initialSnapshot"])
                self._boundary(self.latest)
                need(self.latest["context"]["mapId"] == 67
                     and [self.latest["player"][k] for k in ("x", "y")] == [564, 392]
                     and self.latest.get("nativeObservation", {}).get("playerStepCount") == 0,
                     "natural spawn warmup requires the unchanged Cherrygrove start")
                followers = [a for a in self.latest.get("actors", []) if a.get("active") is True
                             and a.get("species") == 56 and a.get("role") == "FOLLOWER"]
                need(len(followers) == 1, "natural spawn warmup lacks its saved Mankey")
                self.warmup_identity = select_current_actor(self.latest, followers[0])["subjectIdentity"]
                return self.result()
            if row.get("phase") == "setup":
                self._observe_setup(row, on_sample)
                return self.result()
            need(self.setup_index == len(setup_for(self.kind)) and row.get("phase") == "observe",
                 "natural spawn observation began before setup")
            # The existing Job emits no row when this exact wait is already true.
            expected = actions_for(self.kind)[self.action_index]
            if row.get("action") != expected[0] and expected[1] == "wait":
                need(self._setup_ready(self.test["actions"][self.action_index]),
                     "natural spawn second-field bind skipped its unsettled follower wait")
                self.action_index += 1
                expected = actions_for(self.kind)[self.action_index]
            need(row.get("action") == expected[0], "natural spawn action order differs")
            if expected[1] == "wait":
                self._observe_transition_wait(row, on_sample)
                return self.result()
            if expected[1] == "bind":
                need(row.get("command") == "bind" and self.action_frames == 0,
                     "natural spawn second-field bind command differs")
                sample = row["snapshot"]
                self._boundary(sample)
                self._transition_pose(sample)
                subject = select_current_actor(sample, row["receipt"])
                need((subject["species"], subject["role"], subject["subjectIdentity"]) ==
                     (56, "FOLLOWER", self.follower_identity)
                     and check_movement_predicate(dict(kind="follower-settled", species=56, partySlot=2), sample),
                     "natural spawn second-field bind changed its saved follower or is not settled")
                self.subject = subject
                self.latest = deepcopy(sample)
                self.window_transition["reboundSubject"] = deepcopy(subject)
                self.window_transition["bindFrame"] = sample["frame"]
                self.action_index += 1
                if on_sample:
                    on_sample(sample, self.observed_frames)
                return self.result()
            if expected[1] == "teleport":
                need(row.get("command") == "teleport" and self.action_frames == 0
                     and row["receipt"].get("preparedOnly") is True
                     and all(row["receipt"]["snapshot"].get(k) == row["snapshot"].get(k)
                             for k in ("frame", "nativeCycle", "context"))
                     and row["receipt"].get("setupBoundary", {}).get("eventsDrained") is True
                     and row["receipt"]["setupBoundary"].get("frame") == row["snapshot"]["frame"]
                     and row["receipt"]["setupBoundary"].get("nativeCycle") == row["snapshot"]["nativeCycle"],
                     "natural spawn warp receipt differs")
                self._boundary(row["snapshot"])
                need(row["snapshot"]["context"]["mapId"] == 33
                     and [row["snapshot"]["player"][k] for k in ("x", "y")] == [585, 406],
                     "natural spawn warp target differs")
                need(self.kind == RETRY and self.window == 0
                     and self.observed_frames == self.case["frames"][0]
                     and self.latest["context"]["mapId"] == self.case["start"][0]
                     and all(row["snapshot"]["context"].get(key) != self.latest["context"].get(key)
                             for key in ("fieldEpoch", "mapGeneration")),
                     "natural spawn second warp lacks its exact different-field transition")
                old_subject = select_current_actor(self.latest, self.subject)
                self.window_transition = dict(frame=row["snapshot"]["frame"],
                    oldContext=deepcopy(self.latest["context"]), context=deepcopy(row["snapshot"]["context"]),
                    subject=deepcopy(old_subject), credited=False)
                self.latest = deepcopy(row["snapshot"])
                self.window += 1
                self.last_sequence = None
                self.subject = None
                self.action_index += 1
                return self.result()
            need("command" not in row and row.get("requestedInput", {}).get("keys") == [],
                 "natural spawn action changed neutral input")
            for sample, events, _ in validate_raw_chunk(row, self.latest):
                self._boundary(sample)
                map_id, x, y = self.case["start"] if self.window == 0 else (33, 585, 406)
                need(sample["context"]["mapId"] == map_id
                     and [sample["player"][k] for k in ("x", "y")] == [x, y]
                     and all(sample.get("selector", {}).get(k) == 0
                             for k in ("heldKeys", "newKeys", "physicalPressed", "simulatedKeys")),
                     "natural spawn window changed map, player or neutral input")
                need(self.subject is not None, "natural spawn window lacks its explicit current follower bind")
                select_current_actor(sample, self.subject)
                w = self.windows[self.window]
                w["snapshots"].append(deepcopy(sample))
                for event in events:
                    self._event_coverage(event)
                    if event.get("kind") == "native-observation":
                        data = event["data"]
                        if data.get("observation") in SELECTED:
                            w["events"].append(deepcopy(event))
                        else:
                            # Preserve complete native clocks/sequence, discard only
                            # unrelated payload fields after coverage validation.
                            w["events"].append(dict(frame=event["frame"], kind="native-observation", data={
                                key:data[key] for key in ("observation", "sequence", "entryActorFrame", "returnActorFrame",
                                                         "entryNativeCycle", "returnNativeCycle")}))
                    elif event.get("kind") == "native" and event.get("data", {}).get("event") == "ACTOR_DETACHED":
                        w["events"].append(deepcopy(event))
                self.observed_frames += 1
                self.action_frames += 1
                need(self.action_frames <= expected[2]["frames"], "natural spawn segment exceeds its frame count")
                self.latest = deepcopy(sample)
                if on_sample:
                    on_sample(sample, self.observed_frames)
            if self.action_frames == expected[2]["frames"]:
                self.action_frames = 0
                self.action_index += 1
        except (ValueError, KeyError, TypeError, IndexError) as error:
            self.failures.append(str(error))
        return self.result()

    def finish(self):
        self.closed = True
        try:
            need(not self.failures and self.action_index == len(actions_for(self.kind))
                 and self.observed_frames == sum(self.case["frames"]), "natural spawn bounded window is incomplete")
            reports = []
            for i, window in enumerate(self.windows):
                need(len(window["snapshots"]) == self.case["frames"][i], "natural spawn window frame count differs")
                reports.append(parse_record(_record(window["snapshots"], window["events"])))
            if self.kind == WATER:
                witnesses = water_witnesses(reports[0], **self.windows[0])
                need(witnesses, "no natural water constructor and completed landing were observed")
                self.outcomes = dict(waterLandings=witnesses)
            else:
                failures, density = [], []
                for report, window in zip(reports, self.windows):
                    f, d = retry_witnesses(report, window["events"])
                    failures.extend(f); density.extend(d)
                need(failures, "no failed-series short retry was observed")
                need(density, "no actual-creation density delay was observed")
                self.outcomes = dict(shortRetries=failures, creationDelays=density)
            self.outcomes["coverage"] = [r["quality"] for r in reports]
        except (ValueError, KeyError, TypeError, IndexError) as error:
            if not self.failures:
                self.failures.append(str(error))
        return self.result()

    def result(self):
        ready = self.closed and not self.failures and bool(self.outcomes)
        return dict(kind=self.kind, requirements=[self.case["requirement"]], acceptedProof=False,
            passed=ready, ready=ready, closed=self.closed, observedFrames=self.observed_frames,
            observedFrameUnit="completed-game-frame", failures=list(self.failures), outcomes=deepcopy(self.outcomes))
