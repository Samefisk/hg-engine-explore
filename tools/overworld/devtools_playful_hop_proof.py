"""Accepted current Wild Playful one- and two-hop proof."""
from copy import deepcopy

from tools.overworld.devtools_playful_hop_measurement import (
    APPLICATION, FIND_APPLICATION, FIND_PLAYER_CONDITION, PLAYER_CONDITION,
    KIND, REQUIREMENT, need,
)
from tools.overworld.devtools_application_bank import canonical_bank, local_application
from pathlib import Path

CLAIMS = ("live-actor-identity", "profile-resolution", "rendered-motion", "control-release",
          "feedback-effect")
FAULTS = ("wrong-count", "missing-second-hop", "overlap", "displacement",
          "false-first-activation", "heart-draw", "cry-draw",
          "heart-not-visible", "wrong-cry", "missing-prep", "missing-find-playmate", "far-playmate")
NAMES = {
    "live-actor-identity": "same-current-clefairy-both-counts",
    "profile-resolution": "find-playmate-then-adjacent-playful-and-two-rng-draws",
    "rendered-motion": "one-and-two-stock-in-place-hop-arcs",
    "control-release": "stock-command-and-owner-release",
    "feedback-effect": "same-actor-heart-and-cry-shown-and-skipped-for-both-counts",
}


def contract():
    return {claim: [dict(name=NAMES[claim], operator="eq", type="integer",
                         validator="meaningful-observation", expected=1)] for claim in CLAIMS}


def measurements(replay, record):
    result = replay.get("measurements", {}).get(KIND, {})
    outcomes = result.get("outcomes", {})
    one = outcomes.get(1, outcomes.get("1", {}))
    two = outcomes.get(2, outcomes.get("2", {}))
    subject = result.get("subjects", {}).get("clefairy", {}).get("handle")
    need(replay.get("passed") is True and replay.get("failures") == []
         and result.get("passed") is True and result.get("ready") is True
         and result.get("acceptedProof") is False
         and result.get("requirements") == [REQUIREMENT]
         and result.get("observedFrames") == replay.get("observedFrames")
         and result.get("observedFrameUnit") == "completed-game-frame"
         and set(result.get("subjects", {})) == {"clefairy", "passive"}
         and subject and one.get("count") == 1 and two.get("count") == 2
         and one.get("controlFrame", 0) > one.get("selectedFrame", 10**9)
         and two.get("controlFrame", 0) > two.get("selectedFrame", 10**9)
         and one.get("condition", {}).get("conditionId") == PLAYER_CONDITION
         and two.get("condition", {}).get("conditionId") == PLAYER_CONDITION
         and result.get("approach", {}).get("actor") == subject
         and result["approach"].get("condition", {}).get("conditionId") == FIND_PLAYER_CONDITION
         and one.get("fingerprint") and two.get("fingerprint")
         and result.get("admissionSkip", {}).get("actor") == subject,
         "exact current natural Playful sequences or the 60 percent skip are missing")
    presentation = result.get("presentation", {})
    for count in (1, 2):
        count_rows = presentation.get(count, presentation.get(str(count), {}))
        for name in ("heart", "cry"):
            shown = count_rows.get(name, {})
            need(shown.get(True, shown.get("true")) and shown.get(False, shown.get("false")),
                 "independent visible heart and own-cry outcomes are missing for both counts")
    need(record.get("sessionCleanup") == dict(sessionId=record.get("sessionId"), closed=True, errors=[]),
         "owned Playful session cleanup is missing")
    return [dict(claim=claim, name=NAMES[claim], value=1, operator="eq", expected=1, passed=True)
            for claim in CLAIMS]


class PlayfulHopNegative:
    def __init__(self, fault):
        need(fault in FAULTS, "unknown copied Playful control")
        self.fault = fault
        self.applied = False
        self.two_selected = False
        self.preps = 0
        self.last_command = None
        self.setup_handle = None
        self.selected_frame = None
        self.jump_frame = None
        bank = canonical_bank(Path(__file__).resolve().parents[2])
        self.find_local = local_application(bank, 35, FIND_APPLICATION)
        self.playful_local = local_application(bank, 35, APPLICATION)

    def mutate(self, row, subjects):
        if row.get("phase") not in ("setup", "observe"):
            return row
        changed = deepcopy(row)
        if changed.get("phase") == "setup" and changed.get("action") == "spawn-clefairy":
            candidate = changed.get("receipt", {}).get("subject", {}).get("handle")
            if isinstance(candidate, dict):
                self.setup_handle = candidate
        actor = subjects.get("clefairy", {}).get("handle", self.setup_handle or {})
        events = (changed.get("receipt", {}).get("events", [])
                  if changed["phase"] == "setup" else changed.get("events", []))
        if self.fault == "missing-prep" and not self.applied:
            for event in list(events):
                data = event.get("data", {})
                if (event.get("kind") == "native-observation"
                        and data.get("observation") == "playful-step"
                        and data.get("publicSubject", {}).get("handle") == actor
                        and data.get("command") == 0x49 and data.get("returnValue") == 1):
                    events.remove(event)
                    self.applied = True
                    break
        if self.fault == "false-first-activation" and not self.applied:
            for event in events:
                data = event.get("data", {})
                if event.get("kind") == "native" and data.get("event") == "CONDITIONAL_RESOLVED" \
                        and data.get("actorHandle") == actor.get("value"):
                    reason = data.get("reasonId", 0)
                    if reason & (1 << 12) and reason & (1 << 13) and reason & (1 << 14):
                        data["reasonId"] = reason & ~(1 << 13)
                        self.applied = True
                        break
        if changed["phase"] == "setup":
            return changed
        if self.fault in ("missing-find-playmate", "far-playmate") and not self.applied:
            for sample in changed.get("samples", []):
                for item in sample.get("actors", []):
                    if (item.get("handle") == actor
                            and item.get("matchedLayerMask", 0) & (1 << self.playful_local)):
                        if self.fault == "missing-find-playmate":
                            item["matchedLayerMask"] &= ~(1 << self.find_local)
                        else:
                            sample["player"]["y"] = item["logical"]["y"] + 10
                        self.applied = True
                        break
                if self.applied:
                    break
        if self.fault in ("heart-draw", "cry-draw", "heart-not-visible", "wrong-cry") and not self.applied:
            for event in events:
                data = event.get("data", {})
                if event.get("kind") != "native-observation" \
                        or data.get("publicSubject", {}).get("handle") != actor:
                    continue
                observation = data.get("observation")
                if self.fault in ("heart-draw", "cry-draw") and observation == "playful-sequence":
                    draws = data.get("rngReturns", [])
                    index = 0 if self.fault == "heart-draw" else 1
                    if len(draws) == 2 and type(draws[index].get("value")) is int:
                        draws[index]["value"] = 99 if draws[index]["value"] % 100 < 50 else 0
                        self.applied = True
                        break
                if self.fault == "heart-not-visible" and observation == "playful-heart":
                    data["returnValue"] = 0
                    self.applied = True
                    break
                if self.fault == "wrong-cry" and observation == "playful-cry":
                    data["species"] = 36
                    self.applied = True
                    break
        for event in list(events):
            data = event.get("data", {})
            if event.get("kind") != "native-observation" or data.get("observation") != "walk-policy" \
                    or data.get("operation") != 4 or data.get("publicSubject", {}).get("handle") != actor:
                continue
            raw = bytearray.fromhex(data.get("responseHex", ""))
            if len(raw) != 28 or raw[22] != 1:
                continue
            if self.fault == "displacement" and self.selected_frame is None:
                self.selected_frame = event.get("frame")
            if self.fault == "wrong-count" and not self.applied:
                raw[23] = 3
                data["responseHex"] = raw.hex()
                self.applied = True
            if self.fault == "overlap" and not self.applied:
                events.append(deepcopy(event))
                self.applied = True
        if self.fault == "missing-second-hop" and not self.applied:
            for event in events:
                data = event.get("data", {})
                if (event.get("kind") != "native-observation"
                        or data.get("publicSubject", {}).get("handle") != actor):
                    continue
                if data.get("observation") == "walk-policy" and data.get("operation") == 4:
                    raw = bytearray.fromhex(data.get("responseHex", ""))
                    if len(raw) == 28 and raw[22] == 1:
                        self.two_selected = raw[23] == 2
                        self.preps = 0
                elif (self.two_selected and data.get("observation") == "playful-step"
                      and data.get("returnValue") == 1):
                    if data.get("command") == 0x49:
                        self.preps += 1
                    elif self.preps == 2 and 0x30 <= data.get("command", -1) <= 0x33:
                        for sample in changed.get("samples", []):
                            if sample.get("frame") == event.get("frame"):
                                for item in sample.get("actors", []):
                                    if item.get("handle") == actor:
                                        item["engineObject"]["movement_cmd"] = 0x34
                                        self.applied = True
                        break
        if self.fault == "displacement" and self.selected_frame is not None:
            for event in events:
                data = event.get("data", {})
                if (self.jump_frame is None and event.get("frame", -1) >= self.selected_frame
                        and data.get("observation") == "playful-step"
                        and data.get("publicSubject", {}).get("handle") == actor
                        and data.get("returnValue") == 1
                        and 0x30 <= data.get("command", -1) <= 0x33):
                    self.jump_frame = event["frame"]
            for sample in changed.get("samples", []):
                for item in sample.get("actors", []):
                    if item.get("handle") != actor:
                        continue
                    engine = item.get("engineObject", {})
                    if not self.applied and self.jump_frame is not None:
                        if (sample.get("frame", -1) > self.jump_frame
                                and item.get("motionKind") == "NONE"
                                and 0x30 <= engine.get("movement_cmd", -1) <= 0x33):
                            item["logical"]["x"] += 1
                            self.applied = True
        return changed


def validate_negative_result(result, fault):
    need(fault in FAULTS and result.get("passed") is False and result.get("failures"),
         "copied Playful control did not reject")
    expected = {"wrong-count": "count overlaps", "missing-second-hop": "stock Hop arc",
                "overlap": "count overlaps", "displacement": "in-place Hop changed",
                "false-first-activation": "fresh activation lacks a true source",
                "heart-draw": "effect output differs",
                "cry-draw": "effect output differs",
                "heart-not-visible": "heart was not visibly admitted",
                "wrong-cry": "another Pokemon cry",
                "missing-prep": "accepted native PREP boundary",
                "missing-find-playmate": "applied Find Playmate stage",
                "far-playmate": "far from its exact Player playmate"}[fault]
    need(any(expected in str(f) for f in result.get("measurements", {}).get(KIND, {}).get("failures", [])),
         "copied Playful control rejected for another reason")
