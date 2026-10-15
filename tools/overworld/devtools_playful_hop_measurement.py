"""One current Wild Clefairy's natural one- and two-jump Playful pauses."""
from copy import deepcopy
from pathlib import Path
import struct

from tools.overworld.devtools_application_bank import canonical_bank, local_application
from tools.overworld.devtools_profile_feature_measurement import application_index, decode_condition
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor, stock_bubble_admitted

KIND = "playful-in-place-hop-v1"
TEST = "profile.playful.in-place-hop"
REQUIREMENT = "current.playful-in-place-hop"
APPLICATION = application_index("apply-playful")
FIND_APPLICATION = application_index("apply-find-playmate")
FIND_PLAYER_CONDITION = 58853
PLAYER_CONDITION = 19219
CONDITIONS = {PLAYER_CONDITION: "PLAYER"}
BOUNDARY = "main-task-queue-completion"
SETUP = (
    ("open-area", "teleport", {"map": 33, "x": 585, "z": 408, "facing": 0}),
    ("prepare-passive-party", "party", {"slot": 0, "species": 155, "level": 20}),
    ("create-passive-follower", "spawn", {"species": 155, "form": 0, "role": "follower", "slot": 0, "level": 20}),
    ("bind-passive", "bind", {"subject": "passive"}),
    ("spawn-clefairy", "spawn", {"species": 35, "form": 0, "role": "wild", "level": 5, "x": 585, "z": 404}),
    ("bind-clefairy", "bind", {"subject": "clefairy"}),
)


def need(value, reason):
    if not value:
        raise ValueError("Playful hop: " + reason)


def validate_recipe(test):
    need(test["id"] == TEST and test["mode"] == "prepared"
         and test["requirements"] == [REQUIREMENT]
         and test["subjects"] == [dict(id="clefairy", species=35, role="WILD", acquire="spawn"),
                                  dict(id="passive", species=155, role="FOLLOWER", acquire="existing")]
         and test["measurements"] == [dict(kind=KIND, subject="clefairy")]
         and tuple((a["id"], a["op"], a["args"]) for a in test["setup"]) == SETUP
         and [(a["id"], a["op"]) for a in test["actions"]] == [("observe-natural-hops", "wait")]
         and test["actions"][0]["args"] == {"predicate": {
             "kind": "measurement-complete", "measurement": KIND, "when": "final"}}
         and test["budgets"]["maxFrames"] <= 3600
         and test["budgets"]["minObservedFrames"] >= 2,
         "typed recipe differs from the bounded natural setup")


class PlayfulHopMeasurement:
    def __init__(self, source):
        self.source = source
        self.application_local = local_application(
            canonical_bank(Path(__file__).resolve().parents[2]), 35, APPLICATION)
        self.find_application_local = local_application(
            canonical_bank(Path(__file__).resolve().parents[2]), 35, FIND_APPLICATION)
        self.latest = None
        self.setup_index = self.observed_frames = 0
        self.subjects = {}
        self.active_condition = None
        self.find_condition = None
        self.approach = None
        self.activations = {}
        self.pending_setup_events = []
        self.pending = None
        self.admitted_hearts = {}
        self.outcomes = {}
        self.admission_skip = None
        self.presentation = {count: {name: {True: None, False: None}
                                     for name in ("heart", "cry")} for count in (1, 2)}
        self.failures = []

    def _boundary(self, sample, *, route=True):
        need(sample.get("fieldAvailable") is True
             and sample.get("observationBoundary") == BOUNDARY
             and sample.get("romSha256") == self.source["romSha256"]
             and sample.get("fieldControl", {}).get("taskPointer") == 0,
             "completed current field boundary differs")
        if route:
            need(sample.get("context", {}).get("mapId") == 33, "left Route29")

    def _actor(self, sample, name):
        selected = select_current_actor(sample, self.subjects[name])
        return next(a for a in sample["actors"] if a["handle"] == selected["handle"])

    def _profile(self, sample, actor, cache, lane):
        need(isinstance(cache, dict) and cache.get("frame", -1) >= sample["frame"]
             and cache.get("nativeCycle", -1) >= sample["nativeCycle"]
             and sample.get("nativeObservation", {}).get("coverageComplete") is True
             and sample["nativeObservation"].get("profilesEvicted") == 0
             and actor["behaviorFingerprint"] in sample["nativeObservation"].get("profileFingerprints", []),
             "selected pause lacks coherent resolver coverage")
        rows = [r for r in cache.get("resolvedProfiles", [])
                if r.get("resolved") is True and r.get("fingerprint") == actor["behaviorFingerprint"]]
        need(rows and all(r.get("sourceSha256") == self.source["profileSha256"] for r in rows)
             and len({r.get("resultHex") for r in rows}) == 1,
             "selected pause differs from sealed authored Playful profile")
        result = bytes.fromhex(rows[0]["resultHex"])
        need(len(result) == 216 and struct.unpack_from("<I", result, 192)[0] == actor["behaviorFingerprint"]
             and result[212] == self.application_local and result[213] == 0
             and struct.unpack_from("<H", result, 214)[0] == self.active_condition["conditionId"]
             and lane in (result[:80], result[80:160])
             and lane[31] == 1 and lane[67] == 60
             and ((lane[57] >> 4) & 3) == 1 and lane[43] >> 1 == 50
             and lane[57] >> 6 == 2 and lane[75] >> 6 == 2,
             "selected profile lacks authored 60/50 percent hops and independent 50 percent effects")
        target = bytes(12) + bytes((1, 0))
        need(result[196:210] == target and result[2:4] == bytes(2),
             "Playful profile captured a different full target or kept an entry emote")

    def _stage(self, sample, actor):
        need(self.find_condition is not None and self.find_condition["active"]
             and actor["matchedLayerMask"] & (1 << self.find_application_local),
             "Playful lacks its applied Find Playmate stage")
        distance = max(abs(actor["logical"][key] - sample["player"][key])
                       for key in ("x", "y"))
        need(distance <= 1, "Playful is far from its exact Player playmate")

    def _condition(self, event, sample):
        data = event.get("data", {})
        if event.get("kind") != "native" or data.get("event") != "CONDITIONAL_RESOLVED":
            return
        handle = self.subjects["clefairy"]["handle"]
        if data.get("actorHandle") != handle["value"]:
            return
        self._actor(sample, "clefairy")
        need(data.get("actor") == {k: v for k, v in handle.items() if k != "value"}
             and type(data.get("sequence")) is int, "stale Playful condition owner")
        resolved = decode_condition(event)
        if (resolved["conditionId"] == FIND_PLAYER_CONDITION
                and resolved["application"] == self.find_application_local):
            need(resolved["timed"] and resolved["targetKind"] == 1
                 and resolved["targetSourceApplication"] == self.find_application_local,
                 "Find Playmate has another source or target")
            if resolved["active"]:
                if resolved["triggered"]:
                    need(resolved["truth"], "Playful fresh activation lacks a true source")
                else:
                    need(self.find_condition is not None
                         and all(self.find_condition[key] == resolved[key] for key in
                                 ("activeUntil", "cooldownUntil", "targetKind", "targetSlot")),
                         "Find Playmate retained condition lacks its exact fresh true activation")
            self.find_condition = deepcopy(resolved) if resolved["active"] else None
            return
        if resolved["conditionId"] not in CONDITIONS or resolved["application"] != self.application_local:
            return
        need(resolved["targetSourceApplication"] == self.application_local
             and not resolved["timed"]
             and resolved["targetKind"] == 1,
             "Playful condition source or target kind differs")
        identity = dict(actor=deepcopy(handle), targetKind=resolved["targetKind"],
                        targetSlot=resolved["targetSlot"], targetHandle=None,
                        activeUntil=resolved["activeUntil"], cooldownUntil=resolved["cooldownUntil"])
        condition_id = resolved["conditionId"]
        if resolved["active"]:
            need(resolved["truth"], "Playful fresh activation lacks a true source")
            self._stage(sample, self._actor(sample, "clefairy"))
            if resolved["triggered"]:
                need(resolved["truth"], "Playful fresh activation lacks a true source")
                self.activations[condition_id] = dict(identity=identity,
                    actorFrame=resolved["actorFrame"], sequence=resolved["sequence"])
            else:
                previous = self.activations.get(condition_id)
                need(previous is not None and previous["identity"] == identity
                     and resolved["actorFrame"] >= previous["actorFrame"]
                     and resolved["sequence"] > previous["sequence"],
                     "Playful retained condition lacks its exact fresh true activation")
                previous["actorFrame"] = resolved["actorFrame"]
                previous["sequence"] = resolved["sequence"]
            self.active_condition = deepcopy(resolved)
        else:
            self.activations.pop(condition_id, None)
            if self.active_condition is not None and self.active_condition["conditionId"] == condition_id:
                self.active_condition = None

    def _policy(self, event, sample, actor, cache):
        data = event.get("data", {})
        if (event.get("kind") != "native-observation" or data.get("observation") != "walk-policy"
                or data.get("operation") != 4):
            return
        current = select_current_actor(sample, self.subjects["clefairy"])
        before, after = data.get("publicSubject", {}), data.get("publicSubjectAfter", {})
        if before.get("handle") != current["handle"]:
            need(data.get("slot") != current["handle"]["slot"], "selected policy has stale owner")
            return
        need(all(row.get(key) == current[key] for row in (before, after)
                 for key in ("handle", "species", "role", "subjectIdentity",
                             "authorityGeneration", "engineAnchorGeneration", "presentationGeneration"))
             and data.get("returnValue") == 1,
             "selected policy changed its full current owner")
        request, response = bytes.fromhex(data.get("requestHex", "")), bytes.fromhex(data.get("responseHex", ""))
        need(len(request) == len(response) == 28 and request[:4] == b"\x01\x00\x1c\x00"
             and response[:10] == request[:10]
             and request[8] == current["handle"]["slot"] and request[9] == 4,
             "selected public policy ABI differs")
        lane = bytes.fromhex(data.get("laneHex", ""))
        draws = data.get("rngReturns")
        if response[22] != 1:
            if (response[22] == 0 and self.active_condition is not None
                    and actor["matchedLayerMask"] & (1 << self.application_local)
                    and isinstance(draws, list) and len(draws) == 1
                    and type(draws[0].get("value")) is int):
                self._profile(sample, actor, cache, lane)
                self._stage(sample, actor)
                need(draws[0]["value"] % 100 >= 60,
                     "Playful 60 percent admission skipped after an admitted draw")
                self.admission_skip = dict(frame=sample["frame"], actor=deepcopy(current["handle"]),
                                           condition=deepcopy(self.active_condition), policy=deepcopy(data))
            return
        count = response[23]
        need(count in (1, 2) and self.pending is None and self.active_condition is not None
             and actor["matchedLayerMask"] & (1 << self.application_local),
             "Playful hop count overlaps, lacks active condition, or is out of range")
        self._profile(sample, actor, cache, lane)
        self._stage(sample, actor)
        need(isinstance(draws, list) and len(draws) == 2
             and all(type(draw.get("value")) is int for draw in draws)
             and draws[0]["value"] % 100 < 60
             and (draws[1]["value"] % 100 < 50) == (count == 2),
             "natural 60 percent admission or 50 percent extra-hop draw differs")
        self.pending = dict(count=count, selectedFrame=sample["frame"],
                            condition=deepcopy(self.active_condition),
                            fingerprint=actor["behaviorFingerprint"],
                            tile=None, baseY=None, commit=None, commands=[], arcMax=[],
                            started=False, releasedFrame=None, lastCommand=None, jumpFrames=[],
                            policy=deepcopy(data), sequence=None, decisions=None,
                            stepEvents={}, prepEvents={}, heartDraws=[])

    def _effect_event(self, event, sample):
        data = event.get("data", {})
        if event.get("kind") != "native-observation" or data.get("observation") not in (
                "playful-sequence", "playful-step", "playful-heart", "playful-cry", "playful-heart-draw"):
            return
        current = select_current_actor(sample, self.subjects["clefairy"])
        need(all(data.get("publicSubject", {}).get(key) == current[key]
                 for key in ("handle", "species", "role", "subjectIdentity",
                             "authorityGeneration", "engineAnchorGeneration", "presentationGeneration"))
             and event.get("frame") == sample["frame"],
             "Playful effect has another full owner or frame")
        kind = data["observation"]
        if kind == "playful-heart" and data.get("bubbleId") == 0 \
                and stock_bubble_admitted(data.get("returnValue")):
            self.admitted_hearts.setdefault(data["returnValue"], dict(
                frame=sample["frame"], owner=deepcopy(current)))
        p = self.pending
        if p is None:
            return  # Earlier effects earn no sequence credit without a current draw.
        need(p["selectedFrame"] <= sample["frame"], "Playful effect predates its selection")
        if kind == "playful-heart-draw":
            engine = self._actor(sample, "clefairy")["engineObject"]
            if (data.get("visible") is True and data.get("hidden") != 1
                    and stock_bubble_admitted(data.get("modelPointer"))
                    and data.get("bubbleId") == 0 and p["baseY"] is not None
                    and 0x30 <= engine["movement_cmd"] <= 0x33
                    and engine["pos_y"] + engine["face_y"] + engine["unk88_y"] > p["baseY"]):
                p["heartDraws"].append(dict(frame=sample["frame"], **deepcopy(data)))
            return
        if kind == "playful-step" and data.get("command") == 0x49:
            step_id, pose = data.get("stepId"), data.get("objectPose", {})
            need(type(step_id) is int and step_id > 0 and step_id not in p["prepEvents"]
                 and len(p["prepEvents"]) < p["count"]
                 and p["lastCommand"] in (None, 0x4A)
                 and data.get("returnValue") == 1
                 and data.get("publicSubjectAfter") == data.get("publicSubject")
                 and data.get("heartCalls") == data.get("cryCalls") == 0,
                 "Playful PREP lacks one accepted native ground boundary")
            need(all(type(pose.get(key)) is int for key in
                     ("pos_x", "pos_y", "pos_z", "face_y", "unk88_y"))
                 and [pose["pos_x"], pose["pos_z"]] == [
                     (self._actor(sample, "clefairy")["logical"][key] << 16) + 0x8000
                     for key in ("x", "y")],
                 "Playful PREP moved from its exact tile center")
            base_y = pose["pos_y"] + pose["face_y"] + pose["unk88_y"]
            need(p["baseY"] is None or base_y == p["baseY"],
                 "Playful PREP did not return to its original ground height")
            p["baseY"] = base_y
            p["prepEvents"][step_id] = deepcopy(data)
            p["commands"].append(0x49)
            p["lastCommand"] = 0x49
            return
        if kind == "playful-sequence":
            need(p["sequence"] is None and data.get("returnValue") == 1
                 and data.get("publicSubjectAfter") == data.get("publicSubject"),
                 "Playful effect selection lacks one accepted native sequence")
            draws = data.get("rngReturns")
            need(isinstance(draws, list) and len(draws) == 2
                 and all(type(draw.get("value")) is int for draw in draws),
                 "Playful effect selection lacks two native random draws")
            p["decisions"] = dict(heart=draws[0]["value"] % 100 < 50,
                                  cry=draws[1]["value"] % 100 < 50)
            p["sequence"] = deepcopy(data)
            return
        need(p["sequence"] is not None, "Playful JUMP precedes its accepted effect choice")
        step_id = data.get("stepId")
        need(type(step_id) is int and step_id > 0, "Playful JUMP has no native step ID")
        step = p["stepEvents"].setdefault(step_id, dict(command=None, frame=sample["frame"], heart=[], cry=[]))
        need(step["frame"] == sample["frame"], "Playful effect call escaped its native JUMP frame")
        if kind == "playful-step":
            need(len(p["prepEvents"]) == len(p["stepEvents"]),
                 "Playful JUMP lacks an accepted native PREP boundary")
            need(step["command"] is None and 0x30 <= data.get("command", -1) <= 0x33
                 and data.get("returnValue") == 1
                 and data.get("publicSubjectAfter") == data.get("publicSubject"),
                 "Playful effect is not on one accepted JUMP start")
            step["command"] = data["command"]
        elif kind == "playful-heart":
            need(data.get("bubbleId") == 0 and (data.get("returnValue") == 0
                 or stock_bubble_admitted(data.get("returnValue"))),
                 "Playful heart was not visibly admitted")
            step["heart"].append(deepcopy(data))
        else:
            need(data.get("species") == 35 and data.get("form") == 0,
                 "Playful used another Pokemon cry")
            step["cry"].append(deepcopy(data))

    def _sample(self, sample, events, cache):
        self._boundary(sample)
        actor = self._actor(sample, "clefairy")
        passive = self._actor(sample, "passive")
        need(passive["role"] == "FOLLOWER" and passive["species"] == 155
             and all(row.get("handle") == passive["handle"] for row in sample["actors"]
                     if row.get("active") is True and row.get("role") == "FOLLOWER"),
             "Playful fixture changed its exact passive follower")
        need(actor["species"] == 35 and actor["role"] == "WILD"
             and actor["identityVerified"] is True and actor["presentationAttached"] is True,
             "current Playful Clefairy identity or presentation changed")
        need(all(row.get("handle") == actor["handle"] for row in sample["actors"]
                 if row.get("active") is True and row.get("species") == 35),
             "Playful fixture has another live Clefairy")
        if (self.approach is None and self.find_condition is not None
                and actor["matchedLayerMask"] & (1 << self.find_application_local)
                and not actor["matchedLayerMask"] & (1 << self.application_local)
                and actor["motionKind"] in ("WALK", "HOP")
                and max(abs(actor["logical"][key] - sample["player"][key])
                        for key in ("x", "y")) > 1):
            self.approach = dict(frame=sample["frame"], actor=deepcopy(actor["handle"]),
                                 condition=deepcopy(self.find_condition),
                                 origin=deepcopy(actor["origin"]), target=deepcopy(actor["target"]))
        for event in events:
            if event.get("kind") == "trace-status":
                d = event.get("data", {})
                need(d.get("code") not in ("unread-events-lost", "sequence-reset", "invalid-native-ring", "trace-filter-changed")
                     and d.get("unreadEventsLost", 0) == 0 and d.get("coverageComplete", True) is True,
                     "native semantic trace is incomplete")
            self._condition(event, sample)
            self._policy(event, sample, actor, cache)
            self._effect_event(event, sample)
        p = self.pending
        if p is not None:
            engine = actor["engineObject"]
            timer = next(t for t in sample.get("pokemonCombat", {}).get("movementTimers", [])
                         if t.get("handle") == actor["handle"])
            spot, command = timer["movementSpotState"], engine["movement_cmd"]
            if spot == 1 and p["tile"] is None:
                p["tile"] = [actor["logical"][k] for k in ("x", "y")]
                p["commit"] = actor["commitSequence"]
                if p["baseY"] is None:
                    p["baseY"] = engine["pos_y"] + engine["face_y"] + engine["unk88_y"]
            need(timer.get("sourceIdentity") == actor.get("sourceIdentity")
                 and timer.get("movementActorControlMode") == 0,
                 "in-place Hop changed its source or control owner")
            if p["tile"] is not None:
                need(actor["motionKind"] == "NONE" and actor["motionPhase"] == "IDLE"
                     and actor["reservationId"] == 0 and actor["commitSequence"] == p["commit"]
                     and [actor["logical"][k] for k in ("x", "y")] == p["tile"]
                     and [engine["pos_x"], engine["pos_z"]] == [(v << 16) + 0x8000 for v in p["tile"]],
                     "in-place Hop changed tile, owner, or ordinary motion")
            height = 0 if p["baseY"] is None else engine["pos_y"] + engine["face_y"] + engine["unk88_y"] - p["baseY"]
            # Retail ov01_021F8D80 can apply its two-pixel idle bob before
            # the accepted JUMP's stage-zero initializer clears it. Require
            # that exact renderer byte and native start receipt; later arc
            # samples and all ground valleys remain strictly nonnegative.
            render_words = engine.get("movement_render_words", [])
            stock_start_bob = (height == -8192 and 0x30 <= command <= 0x33
                               and engine.get("movement_step") == 0
                               and len(render_words) > 5 and type(render_words[5]) is int
                               and (render_words[5] >> 8) & 0xFF == 1
                               and any(step["frame"] == sample["frame"]
                                       and step["command"] == command
                                       for step in p["stepEvents"].values()))
            need((height >= 0 or stock_start_bob)
                 and sample["frame"] - p["selectedFrame"] <= 64 * p["count"] + 32,
                 "stock Hop arc or bounded command time differs")
            if stock_start_bob:
                p.setdefault("stockStartBobs", []).append(sample["frame"])
            if spot == 1:
                p["started"] = True
                if timer["movementEmoteTimer"] == 0:
                    # TickSpotEmote restores its saved end state, then resets
                    # that end state to CHILL. A Hop started during EMOTING
                    # therefore releases the stock command one update before
                    # CHILL. Require the whole sequence and that exact idle
                    # boundary; no active JUMP can use this allowance.
                    need(p.get("terminalHandoffFrame") is None
                         and p["lastCommand"] == 0x4A
                         and len(p["prepEvents"]) == len(p["stepEvents"]) == p["count"]
                         and len(p["arcMax"]) == p["count"]
                         and command == 255 and engine["flags"] & 2 == 0 and height == 0,
                         "active Hop lost its authored timer")
                    p["terminalHandoffFrame"] = sample["frame"]
                else:
                    if command in (0x49, 0x3E, 0x4A):
                        need(height == 0, "stock Hop did not return to ground between jumps")
                    if command != p["lastCommand"]:
                        p["commands"].append(command)
                        p["lastCommand"] = command
                        if 0x30 <= command <= 0x33:
                            p["arcMax"].append(height)
                            p["jumpFrames"].append((sample["frame"], command))
                    if 0x30 <= command <= 0x33:
                        need(p["arcMax"], "Hop has no stock jump command")
                        p["arcMax"][-1] = max(p["arcMax"][-1], height)
            elif p["started"] and spot == 0 and p["releasedFrame"] is None:
                need(timer["movementEmoteTimer"] == 0 and engine["flags"] & 2 == 0
                     and height == 0 and p["releasedFrame"] is None
                     and (p.get("terminalHandoffFrame") is None
                          or sample["frame"] == p["terminalHandoffFrame"] + 1),
                     "Hop did not release stock command control")
                p["releasedFrame"] = sample["frame"]
            elif not p["started"]:
                need(spot == 0 and sample["frame"] - p["selectedFrame"] <= 32,
                     "selected Playful pause never started")
            else:
                need(spot == 0 and sample["frame"] - p["releasedFrame"] <= 4,
                     "released Hop did not return routine control")
            if p["releasedFrame"] is not None and command in (0, 1, 2, 3, 255):
                sequence = []
                for _ in range(p["count"]):
                    sequence.extend((0x49, "jump", 0x3E, 0x4A))
                actual = ["jump" if 0x30 <= value <= 0x33 else value for value in p["commands"]]
                need(actual == sequence and len(p["arcMax"]) == p["count"]
                     and all(value > 0 for value in p["arcMax"]),
                     "stock one/two-hop command phases or vertical arcs differ")
                need(p["sequence"] is not None and p["decisions"] is not None
                     and len(p["prepEvents"]) == p["count"]
                     and len(p["stepEvents"]) == p["count"]
                     and sorted((step["frame"], step["command"]) for step in p["stepEvents"].values())
                         == p["jumpFrames"],
                     "Playful stock JUMP lacks an accepted native effect boundary")
                for name in ("heart", "cry"):
                    expected = 1 if p["decisions"][name] else 0
                    need(all(len(step[name]) == expected for step in p["stepEvents"].values()),
                         "Playful effect output differs from its independent random choice")
                    if name == "heart" and expected:
                        admitted = []
                        ordered_steps = sorted(p["stepEvents"].values(), key=lambda step: step["frame"])
                        for index, step in enumerate(ordered_steps):
                            pointer = step["heart"][0]["returnValue"]
                            if stock_bubble_admitted(pointer):
                                admitted.append(pointer)
                            end = ordered_steps[index + 1]["frame"] if index + 1 < len(ordered_steps) else p["releasedFrame"]
                            visible = [draw for draw in p["heartDraws"]
                                       if step["frame"] <= draw["frame"] < end]
                            need(any(draw["effectPointer"] in self.admitted_hearts
                                     and self.admitted_hearts[draw["effectPointer"]]["frame"] <= draw["frame"]
                                     and all(self.admitted_hearts[draw["effectPointer"]]["owner"][key]
                                             == actor[key] for key in
                                             ("handle", "species", "role", "subjectIdentity",
                                              "authorityGeneration", "engineAnchorGeneration",
                                              "presentationGeneration"))
                                     and (not admitted or draw["effectPointer"] == admitted[-1])
                                     for draw in visible),
                                 "Playful heart was not visibly admitted during this JUMP")
                    if self.presentation[p["count"]][name][p["decisions"][name]] is None:
                        self.presentation[p["count"]][name][p["decisions"][name]] = deepcopy(p)
                if p["count"] not in self.outcomes:
                    self.outcomes[p["count"]] = deepcopy(p)
                    self.outcomes[p["count"]]["controlFrame"] = sample["frame"]
                self.pending = None
        self.latest = deepcopy(sample)
        self.observed_frames += 1

    def observe_record(self, row, on_sample=None):
        try:
            if "initialSnapshot" in row:
                need(self.latest is None and row.get("phase") == "setup", "initial boundary differs")
                self._boundary(row["initialSnapshot"], route=False)
                self.latest = deepcopy(row["initialSnapshot"])
                return self.result()
            if row.get("phase") == "setup":
                need(self.setup_index < len(SETUP) and row.get("action") == SETUP[self.setup_index][0]
                     and row.get("command") == SETUP[self.setup_index][1], "setup order differs")
                sample = row["snapshot"]
                self._boundary(sample)
                receipt = row.get("receipt", {})
                if isinstance(receipt, dict):
                    self.pending_setup_events.extend(receipt.get("events", []))
                if row["command"] == "bind":
                    name = SETUP[self.setup_index][2]["subject"]
                    selected = select_current_actor(sample, receipt)
                    expected = {"clefairy": (35, "WILD"), "passive": (155, "FOLLOWER")}[name]
                    need((selected["species"], selected["role"]) == expected,
                         "bound Playful actor identity differs")
                    self.subjects[name] = deepcopy(receipt)
                if self.setup_index + 1 == len(SETUP):
                    for event in self.pending_setup_events:
                        self._condition(event, sample)
                    self.pending_setup_events = []
                self.latest = deepcopy(sample)
                self.setup_index += 1
                return self.result()
            need(self.setup_index == len(SETUP) and row.get("phase") == "observe"
                 and row.get("action") == "observe-natural-hops" and "command" not in row,
                 "normal observation order differs")
            for sample, events, _ in validate_raw_chunk(row, self.latest):
                need(self.observed_frames < 3600, "bounded Playful observation exceeded")
                self._sample(sample, events, row.get("profileCache"))
                if on_sample:
                    on_sample(sample, self.observed_frames)
        except (ValueError, KeyError, TypeError, StopIteration, struct.error) as error:
            self.failures.append(str(error))
        return self.result()

    def result(self):
        ready = (not self.failures and self.approach is not None
                 and self.pending is None and set(self.outcomes) == {1, 2}
                 and self.admission_skip is not None
                 and all(self.presentation[count][name][shown] is not None
                         for count in (1, 2) for name in ("heart", "cry")
                         for shown in (False, True)))
        return dict(kind=KIND, requirements=[REQUIREMENT], ready=ready, passed=ready,
                    acceptedProof=False, observedFrames=self.observed_frames,
                    observedFrameUnit="completed-game-frame", subjects=deepcopy(self.subjects),
                    outcomes=deepcopy(self.outcomes), admissionSkip=deepcopy(self.admission_skip),
                    approach=deepcopy(self.approach),
                    presentation=deepcopy(self.presentation), failures=list(self.failures))

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("Playful hop: bounded natural hop and effect outcomes were not observed")
        return self.result()
