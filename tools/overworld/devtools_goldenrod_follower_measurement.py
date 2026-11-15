"""Saved-Mankey normal Hop and two normal field rebinds (TKT-0085)."""
from copy import deepcopy
import hashlib

from tools.overworld.devtools_movement_predicates import check_movement_predicate, player_settled_at
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor, validate_field_absence
from tools.overworld.devtools_cadence_measurement import UnmountedCadenceMeasurement, _handle
from tools.overworld.devtools_spawn_outcome_records import need, quality
from tools.overworld.devtools_spawn_priority_measurement import _record
from tools.overworld.normal_play_observer import MotionRecorder, complete_travel

KIND = "goldenrod-follower-hop-rebind-v1"
REQUIREMENT = "current.goldenrod-follower-hop-rebind"
NAME = "follower.goldenrod-hop-rebind"
PID = 2920357538
MIN_FRAMES = 224
BUDGETS = dict(maxSeconds=240, maxFrames=600, noProgressFrames=96, minObservedFrames=MIN_FRAMES)


def wait(name, predicate, frames=16):
    return dict(id=name, op="wait", args=dict(predicate={**predicate, "when": "final"}),
                budget=dict(maxSeconds=30, maxFrames=frames, noProgressFrames=frames))


def step(name, frames, keys, until=None):
    args = dict(frames=frames, keys=keys)
    if until is not None:
        args["until"] = dict(kind="player-field", path="y", operator="eq", value=until, when="final")
    return dict(id=name, op="step", args=args,
        budget=dict(maxSeconds=60, maxFrames=frames, noProgressFrames=min(frames, 96)))


def setup():
    return [wait("saved-start", dict(kind="player-settled-at", map=76, x=358, z=366)),
            wait("saved-follower", dict(kind="follower-settled", species=56, partySlot=2), 64),
            dict(id="bind-saved-mankey", op="bind", args=dict(subject="mankey"),
                 budget=dict(maxSeconds=10, maxFrames=1, noProgressFrames=1))]


def actions():
    return [step("gold-walk", 32, ["DOWN"]), step("gold-rest", 64, []),
            step("route-down", 128, ["DOWN"], 385),
            wait("route-settle", dict(kind="player-settled-at", map=38, x=358, z=385)),
            step("route-rest", 64, []), step("gold-up", 128, ["UP"], 380),
            wait("gold-settle", dict(kind="player-settled-at", map=76, x=358, z=380)),
            step("gold-return-rest", 64, [])]


def validate_recipe(test):
    need(test.get("id") == NAME and test.get("mode") == "normal"
         and test.get("fixture") == dict(rom="test.nds", save="test.sav")
         and test.get("requirements") == [REQUIREMENT]
         and test.get("subjects") == [dict(id="mankey", species=56, role="FOLLOWER", acquire="existing")]
         and test.get("measurements") == [dict(kind=KIND, subject="mankey")]
         and test.get("setup") == setup() and test.get("actions") == actions()
         and test.get("budgets") == BUDGETS
         and test.get("assertions") == [dict(kind="measurement-complete", measurement=KIND, when="final")],
         "Goldenrod follower recipe changed its sealed saved-Mankey normal route")


def source_inputs(root):
    return dict(contractVersion=1, profileSha256=hashlib.sha256(
        (root / "data/overworld_behavior_profiles.json").read_bytes()).hexdigest())


def saved_actor(sample):
    party = [p for p in sample.get("party", []) if p.get("slot") == 2]
    need(len(party) == 1 and party[0].get("species") == 56 and party[0].get("personality") == PID
         and party[0].get("identityVerified") is True and party[0].get("isEgg") is False
         and party[0].get("hp", 0) > 0 and sample.get("selector", {}).get("activeFollowerPartySlot") == 2,
         "Goldenrod follower changed the saved party-slot2 Mankey identity")
    actors = [a for a in sample.get("actors", []) if a.get("active") is True and a.get("role") == "FOLLOWER"]
    need(len(actors) == 1 and actors[0].get("species") == 56 and actors[0].get("subjectIdentity") == PID,
         "Goldenrod follower lacks exactly the saved current Mankey")
    actor = actors[0]
    select_current_actor(sample, actor)
    return actor


class HopWindow:
    """The same complete-travel predicate is used for the retained red window."""
    def __init__(self):
        self.recorder = MotionRecorder()
        self.latest = None

    def observe(self, sample, actor, owner_lane=None):
        self.latest = sample
        if owner_lane is None:
            profiles = [p for p in sample["nativeObservation"].get("resolvedProfiles", [])
                        if p.get("fingerprint") == actor["behaviorFingerprint"]]
            need(len(profiles) == 1, "Goldenrod follower lacks its current Hop mask")
            owner_lane = bytes.fromhex(profiles[0]["lanes"][0])
        need(len(owner_lane) == 80 and int.from_bytes(owner_lane[32:34], "little") & 0x3FF,
             "Goldenrod follower current Hop mask has no permitted destination")
        self.recorder.observe(sample["frame"], actor, actor["engineObject"])
        need(not self.recorder.failures, "Goldenrod follower Hop travel differs: " + repr(self.recorder.failures))

    def completed(self, label):
        motions = [m for m in self.recorder.completed if m["kind"] == "HOP"
                   and m["origin"] != m["target"] and complete_travel(m)
                   and m.get("commitFrame") is not None and m.get("finishFrame") is not None]
        need(motions, label + " lacks a completed shared Hop")
        return [dict(handle=deepcopy(m["handle"]), origin=m["origin"], target=m["target"],
            startFrame=m["startFrame"], commitFrame=m["commitFrame"], duration=m["duration"],
            travelFrames=len(m["samples"])) for m in motions]


def initial_hop_witness(snapshots):
    quality(_record(snapshots, []))
    need(len(snapshots) >= 97 and player_settled_at(snapshots[0], 76, 358, 366)
         and player_settled_at(snapshots[-1], 76, 358, 374), "Goldenrod first walk endpoints differ")
    window = HopWindow()
    profiles = {}
    for sample in snapshots:
        actor = saved_actor(sample)
        profiles.update({p["fingerprint"]: p for p in sample["nativeObservation"].get("resolvedProfiles", [])})
        fingerprint = actor["behaviorFingerprint"]
        need(fingerprint in profiles and fingerprint in sample["nativeObservation"].get("profileFingerprints", []),
             "Goldenrod follower lacks its current Hop mask")
        window.observe(sample, actor, bytes.fromhex(profiles[fingerprint]["lanes"][0]))
    return window.completed("Goldenrod initial walk")


class GoldenrodFollowerMeasurement:
    def __init__(self, test, source):
        validate_recipe(test)
        need(set(source) == {"contractVersion", "profileSha256"} and source["contractVersion"] == 1
             and isinstance(source["profileSha256"], str) and len(source["profileSha256"]) == 64,
             "Goldenrod follower source identity is missing")
        self.test, self.source = test, source
        self.latest = self.subject = None
        self.setup_index = self.action_index = self.action_frames = self.observed_frames = 0
        self.failures, self.rebinds, self.hops = [], [], {}
        self.context_index, self.context = 0, None
        self.field_absence_pending = False
        self.profiles, self.owner_lane = {}, None
        self.window, self.closed, self.last_sequence = HopWindow(), False, None
        self.trace_sequences, self.transition_notice = {}, None

    def _events(self, events, sample):
        for event in events:
            data = event.get("data", {})
            need(event.get("frame") == sample["frame"] and isinstance(data, dict),
                 "Goldenrod follower event differs from its completed frame")
            if event.get("kind") == "trace-status":
                UnmountedCadenceMeasurement._trace_status(self, data, events, sample["frame"], sample)
                if data.get("code") == "field-epoch-changed":
                    self.transition_notice = deepcopy(sample["context"])
            elif event.get("kind") == "native":
                stream, sequence = data.get("traceStream"), data.get("sequence")
                need(type(stream) is int and stream > 0 and type(sequence) is int
                     and sequence == self.trace_sequences.get(stream, 0) + 1,
                     "Goldenrod follower semantic trace has a gap or duplicate")
                _handle({"value": data.get("actorHandle"), **data.get("actor", {})})
                self.trace_sequences[stream] = sequence
                need(len(self.trace_sequences) <= 64, "Goldenrod follower trace stream bound exceeded")
            elif event.get("kind") == "native-observation":
                sequence = data.get("sequence")
                need(type(sequence) is int and sequence > 0 and (
                    self.last_sequence is None or sequence == self.last_sequence + 1),
                    "Goldenrod follower native receipt has a gap or duplicate")
                self.last_sequence = sequence
                if data.get("observation") == "behavior-resolved":
                    self._remember_profiles([data])
            else:
                raise ValueError("Goldenrod follower unknown raw event")

    def _remember_profiles(self, receipts):
        need(isinstance(receipts, list) and len(receipts) <= 64,
             "Goldenrod follower profile receipt cache is invalid")
        for receipt in receipts:
            if receipt.get("resolved") is not True:
                continue
            fingerprint = receipt.get("fingerprint")
            need(type(fingerprint) is int and fingerprint > 0,
                 "Goldenrod follower profile fingerprint is missing")
            previous = self.profiles.get(fingerprint)
            need(previous is None or previous.get("lanes") == receipt.get("lanes"),
                 "Goldenrod follower fingerprint names changed profile bytes")
            self.profiles[fingerprint] = deepcopy(receipt)
        need(len(self.profiles) <= 64, "Goldenrod follower profile receipt cache exceeded its bound")

    def _boundary(self, sample):
        quality(_record([sample], []))
        if sample.get("fieldAvailable") is False:
            validate_field_absence(sample)
            need(sample.get("prepared") is False, "Goldenrod follower field absence was prepared")
            self.field_absence_pending = True
            return None
        need(sample.get("prepared") is False and sample.get("fieldAvailable") is True
             and sample.get("fieldControl", {}).get("taskPointer") == 0,
             "Goldenrod follower lost normal field control")
        actor = saved_actor(sample)
        self._remember_profiles(sample["nativeObservation"].get("resolvedProfiles", []))
        profile = self.profiles.get(actor.get("behaviorFingerprint"))
        need(profile is not None and profile.get("resolved") is True
             and profile.get("sourceSha256") == self.source["profileSha256"]
             and actor.get("behaviorFingerprint") in sample["nativeObservation"].get("profileFingerprints", []),
             "Goldenrod follower lacks its current resolved shared Hop profile")
        lane = bytes.fromhex(profile.get("lanes", [""])[0])
        need(len(lane) == 80 and lane[12] == 2,
             "Goldenrod follower lacks its current resolved shared Hop profile")
        need(int.from_bytes(lane[32:34], "little") & 0x3FF,
             "Goldenrod follower current Hop mask has no permitted destination")
        self.owner_lane = lane
        context = sample["context"]
        need(not self.field_absence_pending or context != self.context,
             "Goldenrod follower field absence lacks its native rebind")
        self.field_absence_pending = False
        if self.context is None:
            need(context.get("mapId") == 76, "Goldenrod follower changed its saved start map")
        elif context != self.context:
            need(self.context_index < 2 and context.get("mapId") == (38, 76)[self.context_index]
                 and self.transition_notice == context
                 and all(context.get(k) != self.context.get(k) for k in ("fieldEpoch", "mapGeneration"))
                 and self.subject is not None and actor["handle"] != self.subject["handle"]
                 and not any(a.get("active") is True and a.get("handle") == self.subject["handle"]
                             for a in sample.get("actors", [])),
                 "Goldenrod follower rebind kept a stale handle or unexpected context")
            self.rebinds.append(dict(before=deepcopy(self.subject), after=select_current_actor(sample, actor),
                fromMap=self.context["mapId"], toMap=context["mapId"], frame=sample["frame"]))
            self.context_index += 1
            self.window = HopWindow()
            self.transition_notice = None
        self.context = deepcopy(context)
        if self.subject is not None:
            self.subject = select_current_actor(sample, actor)
        return actor

    def _ready(self, action):
        return action["op"] == "wait" and check_movement_predicate(action["args"]["predicate"], self.latest)

    def observe_record(self, row, on_sample=None):
        if self.failures or self.closed:
            return self.result()
        try:
            if "initialSnapshot" in row:
                need(self.latest is None and row.get("phase") == "setup", "Goldenrod follower initial boundary differs")
                self.latest = deepcopy(row["initialSnapshot"]); self._boundary(self.latest)
                need(player_settled_at(self.latest, 76, 358, 366), "Goldenrod follower saved start differs")
                return self.result()
            setup_phase = row.get("phase") == "setup"
            route = self.test["setup"] if setup_phase else self.test["actions"]
            index = self.setup_index if setup_phase else self.action_index
            while index < len(route) and route[index]["id"] != row.get("action") and self._ready(route[index]):
                index += 1
            if setup_phase: self.setup_index = index
            else: self.action_index = index
            need(index < len(route) and route[index]["id"] == row.get("action")
                 and (setup_phase or row.get("phase") == "observe" and self.setup_index == len(self.test["setup"])),
                 "Goldenrod follower action order or command differs")
            action = route[index]
            if row.get("command") is not None:
                need(setup_phase and action["op"] == row["command"] == "bind" and "samples" not in row,
                     "Goldenrod follower permits no setup mutation or extra command")
                sample = row["snapshot"]; actor = self._boundary(sample)
                need(select_current_actor(sample, row["receipt"]) == select_current_actor(sample, actor),
                     "Goldenrod follower full bind differs")
                self.subject = select_current_actor(sample, actor)
                self.latest = deepcopy(sample); self.setup_index += 1
                if on_sample: on_sample(sample, self.observed_frames)
                return self.result()
            keys = action["args"].get("keys", [])
            need(row.get("requestedInput", {}).get("keys") == keys,
                 "Goldenrod follower requested input differs from its normal route")
            for sample, events, _ in validate_raw_chunk(row, self.latest):
                self._events(events, sample)
                actor = self._boundary(sample)
                self.action_frames += 1
                need(self.action_frames <= action["budget"]["maxFrames"], "Goldenrod follower action frame budget exceeded")
                if not setup_phase:
                    need(self.subject is not None, "Goldenrod follower lacks its saved full bind")
                    if actor is None:
                        need(action["id"] in ("route-down", "gold-up"),
                             "Goldenrod follower lost field readiness outside a normal seam")
                    else:
                        self.window.observe(sample, actor, self.owner_lane)
                    self.observed_frames += 1
                self.latest = deepcopy(sample)
                if on_sample: on_sample(sample, self.observed_frames)
            complete = self._ready(action) if action["op"] == "wait" else (
                self.latest.get("player", {}).get("y") == action["args"]["until"]["value"] if "until" in action["args"]
                else self.action_frames == action["args"]["frames"])
            if complete:
                if not setup_phase and action["id"] in ("gold-rest", "route-rest", "gold-return-rest"):
                    stage = ("gold-rest", "route-rest", "gold-return-rest").index(action["id"])
                    map_id, z = ((76, 374), (38, 385), (76, 380))[stage]
                    need(self.context_index == stage and player_settled_at(self.latest, map_id, 358, z),
                         "Goldenrod follower checkpoint lacks settled player control")
                    actor = saved_actor(self.latest)
                    need(actor.get("motionPhase") == "IDLE" and actor.get("inputOwnership") == 0,
                         "Goldenrod follower checkpoint did not return control")
                    self.hops[str(stage)] = self.window.completed(("Goldenrod initial walk", "Route34", "Goldenrod return")[stage])
                if setup_phase: self.setup_index += 1
                else: self.action_index += 1
                self.action_frames = 0
        except (ValueError, KeyError, TypeError, IndexError) as error:
            self.failures.append(str(error))
        return self.result()

    def finish(self):
        self.closed = True
        if not self.ready and not self.failures:
            self.failures.append("Goldenrod follower normal route is incomplete")
        return self.result()

    @property
    def ready(self):
        return not self.failures and self.action_index == len(self.test["actions"]) and set(self.hops) == {"0", "1", "2"} \
            and len(self.rebinds) == 2 and self.observed_frames >= MIN_FRAMES

    def result(self):
        return dict(kind=KIND, requirements=[REQUIREMENT], passed=self.ready, ready=self.ready, closed=self.closed,
            acceptedProof=False, observedFrames=self.observed_frames, failures=list(self.failures),
            subject=deepcopy(self.subject), rebinds=deepcopy(self.rebinds), hops=deepcopy(self.hops),
            source=deepcopy(self.source), mode=self.test["mode"], partySlot=2)
