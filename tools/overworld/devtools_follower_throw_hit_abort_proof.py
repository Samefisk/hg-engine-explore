"""Accepted native receipts for a hit during Follower Throw's pre-Cargo capture."""

from copy import deepcopy

from tools.overworld.devtools_profile_feature_proof import _spec, need
from tools.overworld.devtools_follower_throw_hit_abort_measurement import (
    KIND, REQUIREMENT, STABLE_FRAMES, NOTICE, CARGO, THROW_APP,
)


CLAIMS = ("live-actor-identity", "profile-resolution", "engine-boundary", "control-release")
FAULTS = tuple(KIND + ":" + name for name in (
    "add-premature-cargo", "remove-real-hit", "retain-active-notice", "wrong-rebound-target"))
CONTRACT = {
    "live-actor-identity": [_spec("hit-abort-current-carrier-and-target", [56, "FOLLOWER", 95, "WILD", 1])],
    "profile-resolution": [_spec("hit-abort-exact-pre-cargo-capture", [NOTICE, 1, 0, 0]),
                           _spec("hit-abort-retired-notice-and-bindings", 1)],
    "engine-boundary": [_spec("hit-abort-actual-party-hp-loss-and-hit", [1, 1, 1])],
    "control-release": [_spec("hit-abort-same-target-rebind", 1),
                        _spec("hit-abort-stable-current-frames", minimum=STABLE_FRAMES)],
}


def contract():
    return deepcopy(CONTRACT)


def measurements(replay, record):
    result = replay.get("measurements", {}).get(KIND, {})
    need(replay.get("passed") is True and replay.get("failures") == []
         and result.get("passed") is True and result.get("ready") is True
         and result.get("failures") == [] and result.get("requirements") == [REQUIREMENT],
         "Follower Throw hit-abort replay failed")
    need(record.get("sessionCleanup") == {"sessionId": record.get("sessionId"),
                                          "closed": True, "errors": []},
         "Follower Throw hit-abort session cleanup is missing")
    captured, hit, cleared, rebound = (result.get(name) for name in
                                       ("captured", "hit", "cleared", "rebound"))
    need(all(isinstance(row, dict) for row in (captured, hit, cleared, rebound))
         and captured["frame"] < hit["frame"] <= cleared["frame"] < rebound["frame"]
         and result.get("postFrames", 0) >= STABLE_FRAMES,
         "Follower Throw hit-abort stage order differs")
    owner = result["subjects"]["mankey"]["handle"]
    cargo = result["subjects"]["onix"]["handle"]
    need(result["subject"] == result["subjects"]["mankey"]
         and all(row["mankey"]["handle"] == owner
                 and row["onix"]["handle"] == cargo
                 for row in (captured, hit, cleared, rebound))
         and captured["captured"] is True and rebound["currentTrigger"] is True
         and captured["carrier"]["bindings"]["trigger"]["targetCurrent"] is True
         and captured["carrier"]["bindings"]["trigger"]["target"]
            == {"kind": "ACTOR", "actor": cargo}
         and not captured["carrier"]["bindings"]["cargo"]["bound"]
         and not captured["carrier"]["throw"]["carrier"]
         and not captured["carrier"]["throw"]["carried"]
         and not hit["carrier"]["throw"]["carried"]
         and not cleared["carrier"]["bindings"]["trigger"]["bound"]
         and not cleared["carrier"]["bindings"]["cargo"]["bound"]
         and not cleared["carrier"]["throw"]["carrier"]
         and not cleared["notice"]["flags"] & 1
         and rebound["carrier"]["bindings"]["trigger"]["target"]
            == {"kind": "ACTOR", "actor": cargo},
         "Follower Throw hit-abort native binding or owner receipts differ")
    before = next((row for row in result.get("observations", [])
                   if row["frame"] == hit["frame"] - 1), None)
    damage = before["target"]["currentHp"] - hit["target"]["currentHp"] if isinstance(before, dict) else 0
    need(isinstance(before, dict) and before["captured"] is True
         and before["target"]["hpSource"] == hit["target"]["hpSource"] == "party"
         and before["target"]["hpMirrorMatches"] is hit["target"]["hpMirrorMatches"] is True
         and before["target"]["maxHp"] == hit["target"]["maxHp"]
         and 0 < damage <= before["target"]["currentHp"]
         and damage <= max(1, before["target"]["maxHp"] // 2)
         and hit["target"]["hitCount"] - before["target"]["hitCount"] == 1
         and hit["target"]["lastDamage"] == damage,
         "Follower Throw lacks a real pre-Cargo party hit")
    actual = {
        "hit-abort-current-carrier-and-target": [56, captured["mankey"]["role"],
                                                 95, captured["onix"]["role"], 1],
        "hit-abort-exact-pre-cargo-capture": [captured["carrier"]["bindings"]["trigger"]["sourceConditionId"],
                                              int(bool(captured["notice"]["flags"] & 1)),
                                              int(bool(captured["carrier"]["bindings"]["cargo"]["bound"])),
                                              int(bool(captured["carrier"]["throw"]["carrier"]))],
        "hit-abort-retired-notice-and-bindings": int(not cleared["notice"]["flags"] & 1),
        "hit-abort-actual-party-hp-loss-and-hit": [int(damage > 0),
                                                   hit["target"]["hitCount"] - before["target"]["hitCount"],
                                                   int(hit["target"]["lastDamage"] == damage)],
        "hit-abort-same-target-rebind": int(rebound["carrier"]["bindings"]["trigger"]["target"]["actor"] == cargo),
        "hit-abort-stable-current-frames": result["postFrames"],
    }
    rows = []
    for claim, specs in CONTRACT.items():
        for spec in specs:
            value = actual[spec["name"]]
            expected = spec.get("expected", spec.get("minimum"))
            need(value == expected if spec["operator"] == "eq" else value >= expected,
                 "Follower Throw hit-abort metric differs: " + spec["name"])
            rows.append({"claim": claim, "name": spec["name"], "value": deepcopy(value),
                         "operator": spec["operator"], "expected": deepcopy(expected),
                         "passed": True})
    return rows


class FollowerThrowHitAbortNegative:
    def __init__(self, fault):
        need(fault in FAULTS, "unknown hit-abort copied-data fault")
        self.fault = fault.rsplit(":", 1)[1]
        self.applied = False
        self.previous = None
        self.hit_frame = None
        self.cleared = False

    @staticmethod
    def _selected(sample, subjects):
        mankey = subjects.get("mankey", {}).get("handle")
        onix = subjects.get("onix", {}).get("handle")
        combat = sample.get("pokemonCombat", {})
        interaction = combat.get("interactions", {})
        appearance = sample.get("pokemonAppearance", {})
        if (not isinstance(mankey, dict) or not isinstance(onix, dict)
                or combat.get("frame") != sample.get("frame")
                or interaction.get("frame") != sample.get("frame")
                or appearance.get("frame") != sample.get("frame")):
            return None
        targets = [t for t in combat.get("targets", []) if t.get("handle") == mankey]
        carriers = [c for c in interaction.get("carriers", []) if c.get("handle") == mankey]
        item = appearance.get("conditions", {}).get(str(mankey["slot"]))
        if (len(targets) != 1 or len(carriers) != 1
                or not isinstance(item, dict)
                or item.get("owner", {}).get("actor", {}).get("handle") != mankey):
            return None
        notices = [s for s in item.get("states", [])
                   if s.get("conditionId") == NOTICE and s.get("application") == THROW_APP]
        if len(notices) != 1:
            return None
        return targets[0], carriers[0], notices[0], onix

    def mutate(self, row, subjects):
        if self.applied and self.fault not in ("add-premature-cargo", "retain-active-notice"):
            return row
        changed = deepcopy(row)
        for sample in changed.get("samples", []):
            selected = self._selected(sample, subjects)
            if selected is None:
                continue
            target, carrier, notice, onix = selected
            frame = sample.get("frame")
            trigger = carrier["bindings"]["trigger"]
            capture = (notice.get("flags", 0) & 1) != 0 \
                and trigger.get("bound") is True \
                and trigger.get("targetCurrent") is True \
                and trigger.get("target") == {"kind": "ACTOR", "actor": onix} \
                and carrier["bindings"]["cargo"].get("bound") is False \
                and carrier["throw"].get("carrier") is False
            previous = self.previous
            hit = previous is not None and previous["capture"] \
                and target.get("hitCount") == previous["hitCount"] + 1 \
                and previous["hp"] > target.get("currentHp", previous["hp"]) \
                and target.get("lastDamage") == previous["hp"] - target["currentHp"]
            if hit and self.hit_frame is None:
                self.hit_frame = frame
            if (self.hit_frame is not None and (notice.get("flags", 0) & 1) == 0
                    and trigger.get("bound") is False
                    and carrier["bindings"]["cargo"].get("bound") is False):
                self.cleared = True
            self.previous = {"capture": capture, "hitCount": target.get("hitCount"),
                             "hp": target.get("currentHp")}
            if (self.fault == "add-premature-cargo" and capture
                    and self.hit_frame is None):
                carrier["bindings"]["cargo"].update(
                    bound=True, targetCurrent=True, sourceConditionId=CARGO,
                    sourceApplication=THROW_APP,
                    target=deepcopy(trigger["target"]))
            elif self.fault == "remove-real-hit" and hit:
                target["hitCount"] = previous["hitCount"]
            elif (self.fault == "retain-active-notice"
                  and self.hit_frame is not None and frame <= self.hit_frame + 40
                  and (notice.get("flags", 0) & 1) == 0):
                notice["flags"] |= 1
            elif (self.fault == "wrong-rebound-target" and self.cleared
                  and frame > self.hit_frame and capture):
                trigger["target"]["actor"]["generation"] += 1
            else:
                continue
            self.applied = True
            return changed
        return row


def validate_negative_result(result, fault):
    need(fault in FAULTS and result.get("passed") is False and bool(result.get("failures")),
         "Follower Throw hit-abort copied-data control did not fail")
